"""Prepare one owned fuel fixture in a disposable NORMAL-server mission; never run.

prepare_probe(source,destination,scripts_root,*,x,z,rate_ml,cap_ml,fuel_liters,
car_class,vessel_class,actor_class='SurvivorM_Mirek',outer_timeout_seconds=90,
run_id=None,mode='stock-ce'). Coordinates, rate, cap and fixture fuel are operator supplied.
Native factory/CustomMission chain preserved; fresh external destination only.
Installed declaration hashes are recorded, never installed asset contents.

One new car is explicitly drained/filled with bounded FIXTURE fuel, not harvested
from a wreck/world object. One identity-less CreatePlayer and one CreateInHands
vessel are attempted ONCE. Actor placement derives from the native refill point
and car origin, with a 0.65m outward fixture offset and actual surface height.
No geometry is certified: native action reach/View+Fire LOS must accept it.
Selection-derived component indices are verified with GetActionComponentNameList.
No guessed component 0, teleport of existing players, production hooks or sync.

Direct server OnStart/Finish/End calls exercise the action transfer seam, NOT
player-input/animation dispatch. The explicit trusted one-shot permit is consumed
by the action before debit. A second TransferDiagnostic call must refuse without
changing quantities. Owned deletion must be observed on a later tick. Failed or
aborted callbacks cannot retry the transfer; subsequent ticks attempt cleanup.
No catch/rollback/refund or invented Enforce exception API is used.

Internal watchdog <=60s, <=20000 frames/1000 ticks, 2s deletion window. Scheduling
may stall: a GLOBAL EXTERNAL wall-clock timeout <=180s is mandatory, enforced by
the caller/harness, not this generator. Default remains 90s; a longer startup
allowance must be explicit. The native watchdog remains <=60s and deletion
window remains 2s. validate_result requires actual timeout
and elapsed evidence, rejects absent callbacks, partial cleanup and conservation
mismatch. Exact serialized decimal conservation is required; lossy JSON rounding
is unresolved evidence, never papered over by a permissive epsilon.

Stock CE remains the default. Explicit ce-disabled-control omits ONLY the stock
ce.InitOffline() call, preserving CreateHive and subsequent stock context. Both
modes are diagnostic observations, never gameplay or CE acceptance. Receipts
and manifests without mode attribution are rejected.

Receipts are operator-supplied observations, not engine authentication. Positive
results do not prove save/crash atomicity, clients, full family coverage, gameplay
dispatch, production eligibility or production enablement. No engine is launched.

TDD: initial 12-test run RED (missing module). Recovery-order regression also RED:
CallLater offset 828 followed the first native fixture call at 724. Install both
queues and save the initial partial receipt BEFORE that call. Passing command:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_fuel_siphon_probe -v
All fixtures are synthetic. Declaration inspection is not runtime acceptance.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import re
import secrets

from tools.setup import diagnostic_mission as staging
from tools.setup.infected_death_probe import _read, _sha, _encode, _json, _number, _decode_json, _native_bool
from tools.setup.infected_death_probe import _safe as _base_safe

MODES = ('stock-ce', 'ce-disabled-control')
MAX_OUTER_SECONDS = 180
MARKER = '.hc-fuel-siphon-probe.json'
RESULT = 'hc-fuel-siphon-result.json'
KIND = 'native-owned-fuel-siphon-observation'
INTERFACES = {
    '3_Game/Hive/Hive.c': ('proto native void InitOffline();', 'proto native Hive CreateHive();'),
    '3_Game/Global/Game.c': ('CreatePlayer(PlayerIdentity identity, string name, vector pos, float radius, string spec)',
        'CreateObjectEx(', 'ObjectDelete(', 'GetTickTime()', 'GetPlayerIndentities('),
    '3_Game/Entities/Object.c': ('GetActionComponentNameList(int componentIndex, TStringArray nameList, string geometry = "")',
        'GetActionComponentsForSelectionName(int level, string selectionName, TIntArray componentIndices)',
        'GetViewGeometryLevel()', 'SetPosition(vector vPos)', 'IsAlive()', 'IsDamageDestroyed()', 'GetPosition()'),
    '3_Game/Systems/Inventory/HumanInventory.c': ('CreateInHands(string typeName)',),
    '3_Game/Vehicles/Car.c': ('GetFluidCapacity(CarFluid fluid)', 'GetFluidFraction(CarFluid fluid)',
        'void LeakAll(CarFluid fluid)', 'void Fill(CarFluid fluid, float amount)', 'float GetSpeedometerAbsolute()', 'EngineIsOn()'),
    '3_Game/Vehicles/Transport.c': ('string GetActionCompNameFuel()', 'float GetActionDistanceFuel()', 'vector GetRefillPointPosWS()'),
    '4_World/Entities/ItemBase.c': ('bool SetQuantity(float value, bool destroy_config = true', 'bool IsOpen()', 'bool IsLiquidContainer()', 'override float GetQuantity()', 'override bool HasQuantity()', 'override int GetLiquidType()', 'override int GetQuantityMax()'),
    '4_World/Classes/UserActionsComponent/ActionTargets.c': (
        'void ActionTarget(Object object, Object parent, int componentIndex, vector cursorHitPos, float utility',),
    '4_World/Classes/UserActionsComponent/ActionComponents/CAContinuousFillFuel.c': (
        'm_EmptySpace = (fuelCapacity - currentFuel) * 1000', 'm_SpentQuantity * 0.001'),
    '3_Game/Global/DayZPhysics.c': ('RaycastRV(vector begPos, vector endPos, out vector contactPos, out vector contactDir, out int contactComponent,',
        '/*out*/ set<Object> results = NULL, Object with = NULL, Object ignore = NULL,',
        'bool sorted = false,  bool ground_only = false,  int iType = ObjIntersectView, float radius = 0.0, CollisionFlags flags = CollisionFlags.NEARESTCONTACT);'),
    '4_World/Static/MiscGameplayFunctions.c': ('static vector GetPlayerHeadPosition(notnull PlayerBase player)', 'float headHeight = GetPlayerHeadHeight(player);'),
    '4_World/Static/Liquid.c': ('static bool CanFillContainer(ItemBase container, int liquid_type, bool ignore_fullness_check = false)',),
    '4_World/Entities/ManBase/PlayerBase.c': ('override bool IsRestrained()', 'ItemBase GetItemInHands()'),
    '4_World/Entities/DayZPlayerImplement.c': ('bool IsInVehicle()', 'm_MovementState.m_CommandTypeId == DayZPlayerConstants.COMMANDID_VEHICLE'),
    '3_Game/Entities/Man.c': ('bool IsUnconscious();',),
    '3_Game/Entities/EntityAI.c': ('int GetQuantityMax()',),
    '3_Game/tools/JsonFileLoader.c': ('static bool SaveFile(string filename, T data, out string errorMessage)',),
}


# Diagnostic shape bounds only; no value here grants action eligibility.
PREFLIGHT_BOOLEANS = (
    'attempted complete actor_present donor_present vessel_present actor_alive '
    'actor_unconscious actor_restrained actor_in_vehicle actor_has_identity '
    'target_is_donor target_has_parent vessel_held vessel_destroyed vessel_open '
    'vessel_has_quantity vessel_is_liquid_container gasoline_compatible '
    'donor_destroyed donor_engine_on component_names_truncated').split()
PREFLIGHT_VECTORS = ('actor_position head_position donor_position refill_position').split()
PREFLIGHT_NUMBERS = (
    'actor_refill_distance_sq head_refill_distance_sq raw_reach clamped_reach '
    'donor_speed_abs donor_capacity_liters donor_fraction vessel_quantity vessel_maximum').split()
PREFLIGHT_STRINGS = ('actor_class donor_class vessel_class held_class fuel_selection').split()
RAY_FIELDS = set(('geometry attempted complete hit component_index hit_count hits_truncated '
    'contact_known contact normal endpoint_distance_sq hits').split())


def _preflight_vector(value):
    if type(value) is str:
        if len(value) > 128: raise ValueError('bounded native vector required')
        parts = value.split()
        if len(parts) != 3: raise ValueError('three native coordinates required')
        try: value = [float(part) for part in parts]
        except ValueError as exc: raise ValueError('numeric native vector required') from exc
    if type(value) is not list or len(value) != 3:
        raise ValueError('three native coordinates required')
    for coordinate in value: _number(coordinate, -1e12, 1e12)


def _preflight_integer(value, low=-1, high=2147483647):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('bounded native diagnostic integer required')


def _preflight_text(value):
    if type(value) is not str or len(value) > 128:
        raise ValueError('bounded native diagnostic string required')


def validate_preflight(row):
    """Validate shape/limits, including failed observations; NEVER infer eligibility."""
    fields = set(PREFLIGHT_BOOLEANS + PREFLIGHT_VECTORS + PREFLIGHT_NUMBERS +
                 PREFLIGHT_STRINGS + ['schema', 'captured_ms', 'liquid_type',
                 'component_index', 'component_result', 'component_names', 'rays'])
    if type(row) is not dict or set(row) != fields:
        raise ValueError('exact preflight schema required')
    if type(row['schema']) is not int or row['schema'] != 1:
        raise ValueError('preflight schema 1 required')
    flags = {key: _native_bool(row[key]) for key in PREFLIGHT_BOOLEANS}
    _preflight_integer(row['captured_ms'], 0)
    for key in ('liquid_type', 'component_index', 'component_result'):
        _preflight_integer(row[key])
    for key in PREFLIGHT_VECTORS: _preflight_vector(row[key])
    for key in PREFLIGHT_NUMBERS: _number(row[key], -1e12, 1e12)
    for key in PREFLIGHT_STRINGS: _preflight_text(row[key])
    names = row['component_names']
    if type(names) is not list or len(names) > 64:
        raise ValueError('bounded component names required')
    for name in names: _preflight_text(name)
    rays = row['rays']
    if type(rays) is not list or len(rays) > 2:
        raise ValueError('at most View and Fire observations required')
    observed = []
    all_complete = True
    for ray in rays:
        if type(ray) is not dict or set(ray) != RAY_FIELDS:
            raise ValueError('exact ray observation schema required')
        if ray['geometry'] not in ('view', 'fire') or ray['geometry'] in observed:
            raise ValueError('distinct known ray geometry required')
        observed.append(ray['geometry'])
        rf = {key: _native_bool(ray[key]) for key in
              ('attempted', 'complete', 'hit', 'hits_truncated', 'contact_known')}
        _preflight_integer(ray['component_index'])
        _preflight_integer(ray['hit_count'], 0, 1000000)
        _preflight_vector(ray['contact']); _preflight_vector(ray['normal'])
        _number(ray['endpoint_distance_sq'], -1, 1e12)
        hits = ray['hits']
        if type(hits) is not list or len(hits) > 16 or len(hits) > ray['hit_count']:
            raise ValueError('bounded ray hit witness required')
        if not rf['hits_truncated'] and len(hits) != ray['hit_count']:
            raise ValueError('unexplained missing ray hits')
        if not rf['hit'] and (rf['contact_known'] or ray['hit_count']):
            raise ValueError('miss cannot claim hit/contact evidence')
        for hit in hits:
            if type(hit) is not dict or set(hit) != {'class_name', 'is_donor'}:
                raise ValueError('exact hit witness required')
            _preflight_text(hit['class_name']); _native_bool(hit['is_donor'])
        all_complete = all_complete and rf['attempted'] and rf['complete'] and not rf['hits_truncated']
    complete = (flags['attempted'] and flags['complete'] and not flags['component_names_truncated']
                and all(flags[key] for key in ('actor_present','donor_present','vessel_present'))
                and observed == ['view', 'fire'] and all_complete)
    return dict(diagnostic_status='observation_only', observation_complete=bool(complete),
                eligibility_acceptance=False, production_acceptance=False, runtime_acceptance=False)


def _safe(path):
    path = _base_safe(path)
    if any((ancestor/'.git').exists() for ancestor in (path, *path.parents)):
        raise ValueError('probe files must be outside every Git checkout')
    return path


def inspect_interfaces(root):
    records = {}
    for name, tokens in INTERFACES.items():
        data = _read(Path(root)/name, 2*1024*1024)
        text = ' '.join(data.decode('utf-8-sig').split())
        if any(' '.join(token.split()) not in text for token in tokens):
            raise ValueError('installed interface mismatch: '+name)
        records[name] = dict(sha256=_sha(data), bytes=len(data))
    return records


def _options(x, z, rate_ml, cap_ml, fuel_liters, car_class, vessel_class, actor_class,
             outer_timeout_seconds, run_id):
    for value in (x, z): _number(value, 1, 100000)
    for value, high in ((rate_ml,10000), (cap_ml,1000), (fuel_liters,100)):
        _number(value, 0, high)
        if value <= 0 or float(format(value,'.6f')) <= 0:
            raise ValueError('positive value representable at emitted precision required')
    for value in (car_class, vessel_class, actor_class):
        if type(value) is not str or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,95}',value):
            raise ValueError('bounded native class identifier required')
    if type(outer_timeout_seconds) is not int or not 15 <= outer_timeout_seconds <= MAX_OUTER_SECONDS:
        raise ValueError(f'explicit external timeout 15..{MAX_OUTER_SECONDS} seconds required')
    if type(run_id) is not str or not re.fullmatch('[0-9a-f]{32}',run_id):
        raise ValueError('fresh hexadecimal run ID required')


def _mode(mode):
    if type(mode) is not str or mode not in MODES:
        raise ValueError('fixed fuel CE mode required')
    return mode


def _attribution(row):
    mode = _mode(row.get('mode'))
    if (type(row.get('ce_disabled_control')) is not bool
            or row['ce_disabled_control'] != (mode == 'ce-disabled-control')
            or row.get('gameplay_acceptance') is not False
            or row.get('ce_acceptance') is not False):
        raise ValueError('explicit diagnostic CE attribution required')
    return mode


def _ce_control(data, mode):
    """Remove only the inspected stock call; no arbitrary mission rewriting."""
    if _mode(mode) == 'stock-ce':
        return data
    # Local import avoids startup_probe's existing import of this module's _safe.
    from tools.setup.native_startup_probe import _mask, _block
    text = data.decode('utf-8')
    masked = _mask(text)
    if '#' in masked:
        raise ValueError('preprocessed CE control needs explicit review')
    mains = list(re.finditer(r'\bvoid\s+main\s*\(\s*\)\s*\{', masked))
    if len(mains) != 1:
        raise ValueError('one stock main required')
    opening = mains[0].end() - 1
    end = _block(masked, opening)
    native = re.compile(r'\bHive\s+ce\s*=\s*CreateHive\s*\(\s*\)\s*;\s*'
        r'if\s*\(\s*ce\s*\)\s*(?P<brace>\{)?\s*'
        r'(?P<call>ce\s*\.\s*InitOffline\s*\(\s*\)\s*;)')
    matches = list(native.finditer(masked, opening + 1, end))
    if (len(matches) != 1 or len(re.findall(r'\bCreateHive\s*\(', masked)) != 1
            or len(re.findall(r'\bInitOffline\s*\(', masked)) != 1):
        raise ValueError('exact stock Hive/CreateHive/InitOffline pair required')
    match = matches[0]
    start, stop = match.span('call')
    # An unbraced if must keep an empty statement block; never capture the next
    # stock statement or date-reset block as its new conditional body.
    replacement = '' if match.group('brace') else '{}'
    return (text[:start] + replacement + text[stop:]).encode('utf-8')


def prepare_probe(source, destination, scripts_root, *, x, z, rate_ml, cap_ml, fuel_liters,
                  car_class, vessel_class, actor_class='SurvivorM_Mirek',
                  outer_timeout_seconds=90, run_id=None, mode='stock-ce'):
    _mode(mode)
    run_id = secrets.token_hex(16) if run_id is None else run_id
    _options(x,z,rate_ml,cap_ml,fuel_liters,car_class,vessel_class,actor_class,outer_timeout_seconds,run_id)
    x,z,rate_ml,cap_ml,fuel_liters = (float(format(v,'.6f')) for v in (x,z,rate_ml,cap_ml,fuel_liters))
    source, destination = _safe(source), _safe(destination)
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('overlapping source/destination')
    if not source.is_dir() or destination.exists(): raise ValueError('fresh destination required')
    interfaces = inspect_interfaces(scripts_root)
    files, directories, total = staging._inventory(source)
    for relative, _ in files:
        if relative.name.startswith('.hc-') or relative.name.startswith('hc-'):
            raise ValueError('previous instrumentation/result forbidden')
    if any(relative.parts[0].startswith('storage_') for relative in directories):
        raise ValueError('runtime storage forbidden')
    original = _read(source/'init.c', staging.MAX_INIT_BYTES)
    if any(token in original for token in (b'HCDisposable', b'HCNativeAutotest', b'HCInfectedDeath', b'HCFuelSiphon')):
        raise ValueError('instrumented source forbidden')
    if len(re.findall(rb'class\s+CustomMission\s*:\s*MissionServer\b',original)) != 1:
        raise ValueError('stock CustomMission chain required')
    generated, count = staging._FACTORY.subn(rb'\g<1>HCFuelSiphonProbeMission\g<2>', _ce_control(original, mode))
    if count != 1 or len(re.findall(rb'\bCreateCustomMission\s*\(',original)) != 1:
        raise ValueError('exact stock factory required')
    substitutions = dict(RUN=run_id,MODE=mode,
        CE_DISABLED='true' if mode == 'ce-disabled-control' else 'false',X=format(x,'.6f'),Z=format(z,'.6f'),
        RATE=format(rate_ml,'.6f'),CAP=format(cap_ml,'.6f'),FUEL=format(fuel_liters,'.6f'),
        CAR=car_class,VESSEL=vessel_class,ACTOR=actor_class,
        DEADLINE=str(min(60,outer_timeout_seconds-5)))
    hook = HOOK
    for key,value in substitutions.items(): hook=hook.replace('@'+key+'@',value)
    generated += hook.encode()
    marker = dict(schema=1,kind=KIND,run_id=run_id,mode=mode,
        ce_disabled_control=mode == 'ce-disabled-control',gameplay_acceptance=False,
        ce_acceptance=False,spawn_xz=[x,z],rate_ml=rate_ml,
        cap_ml=cap_ml,fuel_liters=fuel_liters,car_class=car_class,vessel_class=vessel_class,
        actor_class=actor_class,outer_timeout_seconds=outer_timeout_seconds,
        outer_timeout_required=True,max_owned=dict(car=1,vessel=1,actor=1),
                runtime_acceptance='pending',preflight_schema=1,interfaces=interfaces,source_root=str(source),
        mission_path=str(destination),source_bytes=total,files={})
    destination.mkdir(parents=True,exist_ok=False)
    for relative in directories: (destination/relative).mkdir(exist_ok=False)
    for relative, info in files:
        src,dst=source/relative,destination/relative
        _safe(src); staging._unchanged(src,info)
        data=_read(src,staging.MAX_FILE_BYTES)
        staged=generated if relative.as_posix()=='init.c' else data
        with dst.open('xb') as stream: stream.write(staged)
        staging._unchanged(src,info)
        if _read(dst,staging.MAX_FILE_BYTES)!=staged: raise ValueError('staged readback mismatch')
        marker['files'][relative.as_posix()]=dict(source_sha256=_sha(data),staged_sha256=_sha(staged),bytes=len(staged))
    with (destination/MARKER).open('xb') as stream: stream.write(_encode(marker))
    return marker


def validate_result(path, mission, *, outer_timed_out, outer_elapsed_seconds):
    """Check correlated observations; NEVER authenticates native execution."""
    if type(outer_timed_out) is not bool or outer_timed_out:
        raise ValueError('actual non-timed-out external outcome required')
    mission=_safe(mission); marker=_json(mission/MARKER)
    if type(marker.get('schema')) is not int or marker['schema']!=1 or marker.get('kind')!=KIND:
        raise ValueError('prepared marker mismatch')
    mode = _attribution(marker)
    if type(marker.get('preflight_schema')) is not int or marker['preflight_schema'] != 1:
        raise ValueError('prepared preflight schema required')
    spawn=marker.get('spawn_xz')
    if type(spawn) is not list or len(spawn)!=2: raise ValueError('spawn pair required')
    _options(*spawn,marker.get('rate_ml'),marker.get('cap_ml'),marker.get('fuel_liters'),
        marker.get('car_class'),marker.get('vessel_class'),marker.get('actor_class'),
        marker.get('outer_timeout_seconds'),marker.get('run_id'))
    _number(outer_elapsed_seconds,0,marker['outer_timeout_seconds'])
    files=marker.get('files')
    if type(files) is not dict or not 1<=len(files)<=staging.MAX_ENTRIES or 'init.c' not in files:
        raise ValueError('bounded staged inventory required')
    for name,record in files.items():
        if (type(name) is not str or not name or '\\' in name or ':' in name or name.startswith('/')
                or any(part in {'','..','.'} for part in name.split('/'))):
            raise ValueError('invalid staged relative path')
        if type(record) is not dict or _sha(_read(_safe(mission/name),staging.MAX_FILE_BYTES))!=record.get('staged_sha256'):
            raise ValueError('staged source drift')
    # Parse and pin the same bounded snapshot. A later replacement must never
    # supply the digest for an earlier validated receipt. The shared decoder
    # preserves duplicate-key, nonfinite, UTF-8 and object-root rejection.
    receipt_bytes=_read(_safe(path),256*1024)
    value=_decode_json(receipt_bytes)
    if (type(value.get('schema')) is not int or value['schema']!=1 or value.get('kind')!=KIND
            or value.get('run_id')!=marker['run_id'] or value.get('reason')!=''
            or value.get('diagnostic_status')!='observed_exact_transfer_nondurable'):
        raise ValueError('incomplete/failed/stale native receipt')
    if (value.get('mode') != mode or _native_bool(value.get('ce_disabled_control'))
            != (mode == 'ce-disabled-control')):
        raise ValueError('native receipt CE mode mismatch')
    if not validate_preflight(value.get('preflight'))['observation_complete']:
        raise ValueError('complete bounded preflight observations required')
    for field in ('complete','server_context','car_spawned','actor_spawned','vessel_spawned',
            'start_valid','finish_valid','end_pair_valid','sampled','transfer_attempted',
            'lock_released','replay_refused','replay_unchanged','conservation_observed',
            'gasoline_confirmed','cleanup_requested','car_deleted','actor_deleted','vessel_deleted'):
        if not _native_bool(value.get(field)): raise ValueError('missing observed '+field)
    for field in ('failed','actor_has_identity','production_acceptance','durable_acceptance',
                  'gameplay_acceptance','ce_acceptance'):
        if _native_bool(value.get(field)): raise ValueError('invalid claim/context '+field)
    for field in ('start_calls','finish_calls','end_calls','replay_calls','component_result'):
        if type(value.get(field)) is not int or value[field]!=1: raise ValueError('one actual callback/attempt required')
    for field,low,high in (('ticks',2,1000),('frames',0,20000),('max_observed_clients',0,0),('component_index',0,1000000)):
        if type(value.get(field)) is not int or not low<=value[field]<=high: raise ValueError('bounded native telemetry required')
    for field in ('world','engine_version'):
        if type(value.get(field)) is not str or not 1<=len(value[field])<=128: raise ValueError('actual engine/world identity required')
    for field in ('car_class','vessel_class','actor_class'):
        if value.get(field)!=marker[field]: raise ValueError('actual fixture class mismatch')
    names=value.get('component_names'); selection=value.get('fuel_selection')
    if (type(selection) is not str or not 1<=len(selection)<=128 or type(names) is not list
            or not 1<=len(names)<=64 or any(type(n) is not str or len(n)>128 for n in names)
            or selection not in names): raise ValueError('verified native refill component required')
    elapsed=_number(value.get('elapsed_seconds'),1,min(60,marker['outer_timeout_seconds']-5)+3)
    if elapsed>outer_elapsed_seconds: raise ValueError('outer elapsed shorter than receipt')
    start=_number(value.get('start_ms'),0,2147483647)
    finish=_number(value.get('finish_ms'),0,2147483647)
    if not 1000<=finish-start<=8000: raise ValueError('actual bounded callback wait required')
    numeric={}
    for field,high in (('donor_capacity_liters',100000),('donor_before_liters',100000),
            ('donor_after_liters',100000),('vessel_before_ml',100000000),('vessel_after_ml',100000000),
            ('vessel_max_ml',100000000),('planned_ml',1000),('debit_ml',1000),('credit_ml',1000)):
        number=_number(value.get(field),0,high)
        numeric[field]=Decimal(str(number))
    n=numeric; cap=Decimal(str(marker['cap_ml'])); rate=Decimal(str(marker['rate_ml']))
    gain=n['vessel_after_ml']-n['vessel_before_ml']
    loss=(n['donor_before_liters']-n['donor_after_liters'])*1000
    if (not 0<n['credit_ml']==n['debit_ml']==gain==loss<=n['planned_ml']<=min(cap,rate)
            or n['vessel_before_ml']!=0 or n['vessel_after_ml']>n['vessel_max_ml']
            or n['donor_before_liters']>n['donor_capacity_liters']
            or n['donor_before_liters']>Decimal(str(marker['fuel_liters']))):
        raise ValueError('nonconserving/rounded/unbounded native quantities')
    return dict(inprocess_observation_complete=True,production_acceptance=False,
        mode=mode,ce_disabled_control=mode == 'ce-disabled-control',
        gameplay_acceptance=False,ce_acceptance=False,
        durable_acceptance=False,client_acceptance=False,full_family_coverage=False,
        runtime_acceptance='pending',run_id=marker['run_id'],receipt_sha256=_sha(receipt_bytes))


HOOK = r'''

// Disposable owned fixture ONLY. Direct server callbacks, not player input.

// Read-only snapshot BEFORE ValidateLive. Unknown/partial values grant nothing.
class HCFuelSiphonRayHit
{
    string class_name;
    bool is_donor;
}
class HCFuelSiphonRayObservation
{
    string geometry;
    bool attempted;
    bool complete;
    bool hit;
    int component_index = -1;
    int hit_count;
    bool hits_truncated;
    bool contact_known;
    vector contact;
    vector normal;
    float endpoint_distance_sq = -1;
    ref array<ref HCFuelSiphonRayHit> hits = new array<ref HCFuelSiphonRayHit>;
}
class HCFuelSiphonPreflight
{
    int schema = 1;
    bool attempted;
    bool complete;
    int captured_ms = -1;
    bool actor_present;
    bool donor_present;
    bool vessel_present;
    bool actor_alive;
    bool actor_unconscious;
    bool actor_restrained;
    bool actor_in_vehicle;
    bool actor_has_identity;
    bool target_is_donor;
    bool target_has_parent;
    bool vessel_held;
    bool vessel_destroyed;
    bool vessel_open;
    bool vessel_has_quantity;
    bool vessel_is_liquid_container;
    bool gasoline_compatible;
    bool donor_destroyed;
    bool donor_engine_on;
    string actor_class;
    string donor_class;
    string vessel_class;
    string held_class;
    vector actor_position;
    vector head_position;
    vector donor_position;
    vector refill_position;
    float actor_refill_distance_sq = -1;
    float head_refill_distance_sq = -1;
    float raw_reach = -1;
    float clamped_reach = -1;
    float donor_speed_abs = -1;
    float donor_capacity_liters = -1;
    float donor_fraction = -1;
    float vessel_quantity = -1;
    float vessel_maximum = -1;
    int liquid_type = -1;
    int component_index = -1;
    int component_result = -1;
    string fuel_selection;
    bool component_names_truncated;
    ref array<string> component_names = new array<string>;
    ref array<ref HCFuelSiphonRayObservation> rays = new array<ref HCFuelSiphonRayObservation>;
}

class HCFuelSiphonReceipt
{
    int schema = 1;
    string kind = "native-owned-fuel-siphon-observation";
    string run_id = "@RUN@";
    string mode = "@MODE@";
    bool ce_disabled_control = @CE_DISABLED@;
    bool gameplay_acceptance = false;
    bool ce_acceptance = false;
    ref HCFuelSiphonPreflight preflight;
    string world;
    string engine_version;
    bool server_context;
    bool complete;
    bool failed;
    string reason;
    int ticks;
    int frames;
    float elapsed_seconds;
    int max_observed_clients;
    string car_class;
    string vessel_class;
    string actor_class;
    bool car_spawned;
    bool vessel_spawned;
    bool actor_spawned;
    bool actor_has_identity;
    int component_index = -1;
    int component_result = -1;
    string fuel_selection;
    ref array<string> component_names = new array<string>;
    int start_calls;
    int finish_calls;
    int end_calls;
    int replay_calls;
    bool start_valid;
    bool finish_valid;
    bool end_pair_valid;
    bool sampled;
    bool transfer_attempted;
    bool lock_released;
    string diagnostic_status;
    bool replay_refused;
    bool replay_unchanged;
    bool conservation_observed;
    float fixture_fuel_liters = @FUEL@;
    float donor_capacity_liters;
    float donor_before_liters;
    float donor_after_liters;
    float vessel_before_ml;
    float vessel_after_ml;
    float vessel_max_ml;
    float planned_ml;
    float debit_ml;
    float credit_ml;
    int start_ms;
    int finish_ms;
    bool gasoline_confirmed;
    bool cleanup_requested;
    bool car_deleted;
    bool actor_deleted;
    bool vessel_deleted;
    bool production_acceptance = false;
    bool durable_acceptance = false;
}

class HCFuelSiphonProbeMission : CustomMission
{
    protected ref HCFuelSiphonReceipt m_Receipt;
    protected Object m_CarObject;
    protected Object m_ActorObject;
    protected Object m_VesselObject;
    protected CarScript m_Car;
    protected PlayerBase m_Actor;
    protected ItemBase m_Vessel;
    protected ref HCActionSiphonFuel m_Action;
    protected ref HCSiphonDiagnosticData m_Data;
    protected ref ActionTarget m_Target;
    protected int m_Phase;
    protected bool m_Done;
    protected bool m_DeletesIssued;
    protected float m_Started;
    protected float m_LastTick;
    protected float m_StageStarted;
    protected float m_CleanupStarted;
    protected float m_NextFrameTick;

    override void OnInit()
    {
        super.OnInit();
        if (m_Receipt || m_Done)
            return;
        if (FileExist("$profile:hc-fuel-siphon-result.json"))
        {
            m_Done = true;
            Print("[HC Siphon Probe] FAIL stale receipt; fresh profile required");
            return;
        }
        m_Receipt = new HCFuelSiphonReceipt;
        m_Receipt.server_context = GetGame().IsServer();
        GetGame().GetWorldName(m_Receipt.world);
        GetGame().GetVersion(m_Receipt.engine_version);
        m_Started = GetGame().GetTickTime();
        m_LastTick = m_Started;
        Print("[HC Siphon Probe] BEGIN run=@RUN@ direct-server-callbacks NONDURABLE");
        // Arm recovery before any native spawn/callback may abort this method.
        if (!HCSiphonSave()) HCSiphonCleanup("receipt-write-failed");
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCSiphonTick, 100, true);
        GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(HCSiphonFrame);
        HCSiphonTick();
    }

    bool HCSiphonSave()
    {
        string error;
        if (JsonFileLoader<HCFuelSiphonReceipt>.SaveFile("$profile:hc-fuel-siphon-result.json", m_Receipt, error))
            return true;
        m_Receipt.failed = true;
        m_Receipt.complete = false;
        m_Receipt.reason = "receipt-write-failed";
        Print("[HC Siphon Probe] FAIL receipt-write-failed " + error);
        return false;
    }

    void HCSiphonDetach()
    {
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCSiphonTick);
        GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCSiphonFrame);
    }

    bool HCSiphonComponent()
    {
        array<int> indices = new array<int>;
        m_Receipt.fuel_selection = m_Car.GetActionCompNameFuel();
        m_Car.GetActionComponentsForSelectionName(m_Car.GetViewGeometryLevel(), m_Receipt.fuel_selection, indices);
        if (indices.Count() < 1 || indices.Count() > 64 || m_Receipt.fuel_selection == "")
            return false;
        foreach (int componentIndex : indices)
        {
            if (componentIndex < 0)
                continue;
            array<string> names = new array<string>;
            int namedResult = m_Car.GetActionComponentNameList(componentIndex, names);
            if (namedResult != 1 || names.Count() > 64)
                continue;
            if (names.Find(m_Receipt.fuel_selection) >= 0)
            {
                m_Receipt.component_index = componentIndex;
                m_Receipt.component_result = namedResult;
                m_Receipt.component_names = names;
                return true;
            }
        }
        return false;
    }

    void HCSiphonSpawn(float now)
    {
        // Phase 4 survives an aborted native callback: no retry/spawn on next tick.
        m_Phase = 4;
        vector position = "@X@ 0 @Z@";
        float worldSize = GetGame().GetWorld().GetWorldSize();
        if (position[0] >= worldSize || position[2] >= worldSize)
        {
            HCSiphonCleanup("coordinates-outside-world");
            return;
        }
        position[1] = GetGame().SurfaceY(position[0], position[2]);
        if (!GetGame().ConfigIsExisting("CfgVehicles @CAR@") || !GetGame().ConfigIsExisting("CfgVehicles @VESSEL@") || !GetGame().ConfigIsExisting("CfgVehicles @ACTOR@"))
        {
            HCSiphonCleanup("fixture-native-class-unavailable");
            return;
        }
        m_CarObject = GetGame().CreateObjectEx("@CAR@", position, ECE_PLACE_ON_SURFACE);
        m_Car = CarScript.Cast(m_CarObject);
        if (!m_Car || m_Car.IsDamageDestroyed())
        {
            HCSiphonCleanup("intact-script-car-spawn-failed");
            return;
        }
        m_Receipt.car_spawned = true;
        m_Receipt.car_class = m_Car.GetType();
        m_Receipt.donor_capacity_liters = m_Car.GetFluidCapacity(CarFluid.FUEL);
        if (!HCFuelTransferPolicy.FiniteNonNegative(m_Receipt.donor_capacity_liters) || m_Receipt.donor_capacity_liters < @FUEL@ || m_Car.EngineIsOn())
        {
            HCSiphonCleanup("fixture-fuel-capacity-or-engine");
            return;
        }
        // Only the NEW owned fixture is initialized. Not wreck/world fuel.
        m_Car.LeakAll(CarFluid.FUEL);
        if (m_Car.GetFluidFraction(CarFluid.FUEL) != 0)
        {
            HCSiphonCleanup("fixture-drain-unconfirmed");
            return;
        }
        m_Car.Fill(CarFluid.FUEL, @FUEL@);
        if (!HCSiphonComponent())
        {
            HCSiphonCleanup("native-refill-component-unavailable");
            return;
        }
        vector refillPoint = m_Car.GetRefillPointPosWS();
        vector outward = refillPoint - m_Car.GetPosition();
        outward[1] = 0;
        if (!HCActionSiphonFuel.FiniteVector(refillPoint) || outward.Length() <= 0.01)
        {
            HCSiphonCleanup("native-refill-placement-unresolved");
            return;
        }
        outward.Normalize();
        vector actorPosition = refillPoint + outward * 0.65;
        actorPosition[1] = GetGame().SurfaceY(actorPosition[0], actorPosition[2]);
        m_ActorObject = GetGame().CreatePlayer(null, "@ACTOR@", actorPosition, 0, "NONE");
        m_Actor = PlayerBase.Cast(m_ActorObject);
        if (!m_Actor || !m_Actor.IsAlive() || m_Actor.GetIdentity())
        {
            HCSiphonCleanup("offline-owned-PlayerBase-unavailable");
            return;
        }
        m_Receipt.actor_spawned = true;
        m_Receipt.actor_class = m_Actor.GetType();
        m_Receipt.actor_has_identity = m_Actor.GetIdentity() != null;
        m_VesselObject = m_Actor.GetHumanInventory().CreateInHands("@VESSEL@");
        m_Vessel = ItemBase.Cast(m_VesselObject);
        if (!m_Vessel || m_Actor.GetItemInHands() != m_Vessel || !m_Vessel.HasQuantity() || !m_Vessel.IsLiquidContainer())
        {
            HCSiphonCleanup("native-held-liquid-vessel-unavailable");
            return;
        }
        m_Receipt.vessel_spawned = true;
        m_Receipt.vessel_class = m_Vessel.GetType();
        m_Vessel.SetQuantity(0, false);
        if (!m_Vessel || m_Vessel.GetQuantity() != 0 || !Liquid.CanFillContainer(m_Vessel, LIQUID_GASOLINE))
        {
            HCSiphonCleanup("empty-gasoline-compatibility-unconfirmed");
            return;
        }
        m_StageStarted = now;
        m_Phase = 1;
        if (!HCSiphonSave()) HCSiphonCleanup("receipt-write-failed");
    }
'''

HOOK += r'''


    void HCSiphonObserveRay(HCFuelSiphonPreflight preflight, int geometry, string label)
    {
        HCFuelSiphonRayObservation observation = new HCFuelSiphonRayObservation;
        observation.geometry = label;
        observation.attempted = true;
        preflight.rays.Insert(observation);
        // Persist attempted/not-complete before entering the native call.
        if (!HCSiphonSave()) return;
        vector contact;
        vector normal;
        int component = -1;
        set<Object> hits = new set<Object>;
        observation.hit = DayZPhysics.RaycastRV(preflight.head_position, preflight.refill_position, contact, normal, component, hits, null, m_Actor, true, false, geometry);
        observation.component_index = component;
        observation.hit_count = hits.Count();
        observation.contact = contact;
        observation.normal = normal;
        observation.contact_known = observation.hit && HCActionSiphonFuel.FiniteVector(contact);
        if (observation.contact_known)
            observation.endpoint_distance_sq = vector.DistanceSq(contact, preflight.refill_position);
        observation.hits_truncated = hits.Count() > 16;
        int index = 0;
        while (index < hits.Count() && index < 16)
        {
            HCFuelSiphonRayHit witness = new HCFuelSiphonRayHit;
            Object hitObject = hits[index];
            if (hitObject)
            {
                witness.class_name = hitObject.GetType();
                witness.is_donor = hitObject == m_Car;
            }
            if (witness.class_name.Length() <= 128)
                observation.hits.Insert(witness);
            else
                observation.hits_truncated = true;
            index++;
        }
        observation.complete = true;
    }

    void HCSiphonPreflight()
    {
        // Only read owned fixture state and physics; do not normalize eligibility.
        HCFuelSiphonPreflight observation = new HCFuelSiphonPreflight;
        m_Receipt.preflight = observation;
        observation.attempted = true;
        observation.captured_ms = GetGame().GetTime();
        if (!HCSiphonSave()) return;
        observation.actor_present = m_Actor != null;
        observation.donor_present = m_Car != null;
        observation.vessel_present = m_Vessel != null;
        if (!m_Actor || !m_Car || !m_Vessel || !m_Target) return;
        observation.actor_class = m_Actor.GetType();
        observation.donor_class = m_Car.GetType();
        observation.vessel_class = m_Vessel.GetType();
        observation.actor_alive = m_Actor.IsAlive();
        observation.actor_unconscious = m_Actor.IsUnconscious();
        observation.actor_restrained = m_Actor.IsRestrained();
        observation.actor_in_vehicle = m_Actor.IsInVehicle();
        observation.actor_has_identity = m_Actor.GetIdentity() != null;
        observation.actor_position = m_Actor.GetPosition();
        observation.head_position = MiscGameplayFunctions.GetPlayerHeadPosition(m_Actor);
        observation.donor_position = m_Car.GetPosition();
        observation.refill_position = m_Car.GetRefillPointPosWS();
        observation.raw_reach = m_Car.GetActionDistanceFuel();
        observation.clamped_reach = observation.raw_reach;
        if (observation.clamped_reach > 2.0) observation.clamped_reach = 2.0;
        observation.actor_refill_distance_sq = vector.DistanceSq(observation.actor_position, observation.refill_position);
        observation.head_refill_distance_sq = vector.DistanceSq(observation.head_position, observation.refill_position);
        observation.donor_destroyed = m_Car.IsDamageDestroyed();
        observation.donor_engine_on = m_Car.EngineIsOn();
        observation.donor_speed_abs = m_Car.GetSpeedometerAbsolute();
        observation.donor_capacity_liters = m_Car.GetFluidCapacity(CarFluid.FUEL);
        observation.donor_fraction = m_Car.GetFluidFraction(CarFluid.FUEL);
        ItemBase held = m_Actor.GetItemInHands();
        observation.vessel_held = held == m_Vessel;
        if (held) observation.held_class = held.GetType();
        observation.vessel_destroyed = m_Vessel.IsDamageDestroyed();
        observation.vessel_open = m_Vessel.IsOpen();
        observation.vessel_has_quantity = m_Vessel.HasQuantity();
        observation.vessel_is_liquid_container = m_Vessel.IsLiquidContainer();
        observation.vessel_quantity = m_Vessel.GetQuantity();
        observation.vessel_maximum = m_Vessel.GetQuantityMax();
        observation.liquid_type = m_Vessel.GetLiquidType();
        observation.gasoline_compatible = Liquid.CanFillContainer(m_Vessel, LIQUID_GASOLINE);
        observation.target_is_donor = m_Target.GetObject() == m_Car;
        observation.target_has_parent = m_Target.GetParent() != null;
        observation.component_index = m_Target.GetComponentIndex();
        observation.fuel_selection = m_Car.GetActionCompNameFuel();
        array<string> names = new array<string>;
        observation.component_result = m_Car.GetActionComponentNameList(observation.component_index, names);
        observation.component_names_truncated = names.Count() > 64;
        int index = 0;
        while (index < names.Count() && index < 64)
        {
            if (names[index].Length() <= 128) observation.component_names.Insert(names[index]);
            else observation.component_names_truncated = true;
            index++;
        }
        if (!HCSiphonSave()) return;
        // Same origin/endpoints/ignore/options as the action; these are additional
        // observations, not the action's later ray results or an eligibility override.
        HCSiphonObserveRay(observation, ObjIntersectView, "view");
        if (m_Receipt.failed || !HCSiphonSave()) return;
        HCSiphonObserveRay(observation, ObjIntersectFire, "fire");
        if (m_Receipt.failed) return;
        observation.complete = observation.rays.Count() == 2 && observation.rays[0].complete && observation.rays[1].complete;
    }

    void HCSiphonStart(float now)
    {
        m_Phase = 4;
        if (!HCActionSiphonFuel.ConfigureDiagnostic(true, @RATE@, 1.0, @CAP@, true))
        {
            HCSiphonCleanup("trusted-one-shot-configuration-refused");
            return;
        }
        m_Target = new ActionTarget(m_Car, null, m_Receipt.component_index, m_Car.GetRefillPointPosWS(), 0);
        m_Action = new HCActionSiphonFuel;
        m_Data = HCSiphonDiagnosticData.Cast(m_Action.CreateActionData());
        if (!m_Data)
        {
            HCSiphonCleanup("action-data-unavailable");
            return;
        }
        m_Data.m_Player = m_Actor;
        m_Data.m_Target = m_Target;
        m_Data.m_MainItem = m_Vessel;
        m_Data.m_Action = m_Action;
        HCSiphonPreflight();
        if (m_Receipt.failed || !HCSiphonSave())
        {
            HCSiphonCleanup("receipt-write-failed");
            return;
        }
        // ValidateLive remains authoritative and performs its OWN later native rays.
        m_Receipt.start_valid = HCActionSiphonFuel.ValidateLive(m_Actor, m_Target, m_Vessel);
        if (!m_Receipt.start_valid)
        {
            HCSiphonCleanup("start-native-range-LOS-or-eligibility-refused");
            return;
        }
        m_Receipt.start_calls++;
        if (!HCSiphonSave())
        {
            HCSiphonCleanup("receipt-write-failed");
            return;
        }
        m_Action.OnStartServer(m_Data);
        m_Receipt.start_ms = m_Data.StartedMs;
        if (!m_Data.LockHeld || m_Data.DiagnosticStatus != "observing")
        {
            HCSiphonCleanup("start-reservation-not-observed");
            return;
        }
        m_Phase = 2;
        m_StageStarted = now;
    }

    bool HCSiphonPairReady()
    {
        if (!m_Actor || !m_Car || !m_Vessel || !m_Data || !m_Target)
            return false;
        if (!m_Actor.IsAlive() || m_Actor.IsUnconscious() || m_Actor.IsRestrained() || m_Actor.IsInVehicle())
            return false;
        if (m_Actor.GetItemInHands() != m_Vessel || m_Data.m_MainItem != m_Vessel || m_Target.GetObject() != m_Car)
            return false;
        if (m_Car.IsDamageDestroyed() || m_Car.EngineIsOn() || m_Car.GetSpeedometerAbsolute() != 0 || m_Vessel.IsDamageDestroyed())
            return false;
        return m_Vessel.GetLiquidType() == LIQUID_GASOLINE;
    }

    void HCSiphonFinishTransfer()
    {
        m_Phase = 4;
        m_Receipt.finish_valid = m_Action.ActionConditionContinue(m_Data);
        if (!m_Receipt.finish_valid)
        {
            HCSiphonCleanup("finish-revalidation-refused");
            return;
        }
        m_Receipt.donor_capacity_liters = m_Car.GetFluidCapacity(CarFluid.FUEL);
        m_Receipt.donor_before_liters = m_Receipt.donor_capacity_liters * m_Car.GetFluidFraction(CarFluid.FUEL);
        m_Receipt.vessel_before_ml = m_Vessel.GetQuantity();
        m_Receipt.vessel_max_ml = m_Vessel.GetQuantityMax();
        m_Receipt.finish_ms = GetGame().GetTime();
        m_Receipt.finish_calls++;
        if (!HCSiphonSave())
        {
            HCSiphonCleanup("receipt-write-failed");
            return;
        }
        m_Action.OnFinishProgressServer(m_Data);
        m_Receipt.sampled = m_Data.Sampled;
        m_Receipt.transfer_attempted = m_Data.TransferAttempted;
        m_Receipt.diagnostic_status = m_Data.DiagnosticStatus;
        m_Receipt.planned_ml = m_Data.PlannedMl;
        m_Receipt.debit_ml = m_Data.RequestedDebitMl;
        m_Receipt.credit_ml = m_Data.RequestedCreditMl;
        if (!m_Car || !m_Vessel)
        {
            HCSiphonCleanup("endpoint-lost-before-probe-readback");
            return;
        }
        m_Receipt.donor_after_liters = m_Car.GetFluidCapacity(CarFluid.FUEL) * m_Car.GetFluidFraction(CarFluid.FUEL);
        m_Receipt.vessel_after_ml = m_Vessel.GetQuantity();
        m_Receipt.gasoline_confirmed = m_Vessel.GetLiquidType() == LIQUID_GASOLINE;
        float gainMl = m_Receipt.vessel_after_ml - m_Receipt.vessel_before_ml;
        float lostMl = HCFuelTransferPolicy.ExactMilliliters(m_Receipt.donor_before_liters - m_Receipt.donor_after_liters);
        m_Receipt.conservation_observed = gainMl > 0 && gainMl == lostMl && gainMl == m_Receipt.credit_ml;
        m_Receipt.replay_calls++;
        m_Receipt.replay_refused = !HCActionSiphonFuel.TransferDiagnostic(m_Data);
        float replayDonor = m_Car.GetFluidCapacity(CarFluid.FUEL) * m_Car.GetFluidFraction(CarFluid.FUEL);
        m_Receipt.replay_unchanged = replayDonor == m_Receipt.donor_after_liters && m_Vessel.GetQuantity() == m_Receipt.vessel_after_ml;
        m_Receipt.end_pair_valid = HCSiphonPairReady();
        // Do not rearm consumed permit for an identity-less actor's End.
        m_Receipt.end_calls++;
        m_Action.OnEndServer(m_Data);
        m_Receipt.lock_released = !m_Data.LockHeld;
        if (!m_Receipt.sampled || !m_Receipt.transfer_attempted || m_Receipt.diagnostic_status != "observed_exact_transfer_nondurable" || !m_Receipt.conservation_observed)
            HCSiphonCleanup("transfer-not-exactly-observed");
        else if (!m_Receipt.replay_refused || !m_Receipt.replay_unchanged || !m_Receipt.end_pair_valid || !m_Receipt.lock_released)
            HCSiphonCleanup("replay-or-end-revalidation-failed");
        else
            HCSiphonCleanup("");
    }

    void HCSiphonCleanup(string reason)
    {
        if (reason != "")
        {
            m_Receipt.failed = true;
            if (m_Receipt.reason == "") m_Receipt.reason = reason;
        }
        if (!m_Receipt.cleanup_requested)
        {
            m_Receipt.cleanup_requested = true;
            m_CleanupStarted = GetGame().GetTickTime();
        }
        m_Phase = 3;
    }

    void HCSiphonDeleteOwned()
    {
        if (m_Data && m_Action && m_Receipt.end_calls == 0)
        {
            m_Receipt.end_calls++;
            m_Action.OnEndServer(m_Data);
            m_Receipt.lock_released = !m_Data.LockHeld;
        }
        HCActionSiphonFuel.ConfigureDiagnostic(false, 0, 0, 0, false);
        if (m_DeletesIssued)
            return;
        m_DeletesIssued = true;
        if (m_VesselObject) GetGame().ObjectDelete(m_VesselObject);
        if (m_ActorObject) GetGame().ObjectDelete(m_ActorObject);
        if (m_CarObject) GetGame().ObjectDelete(m_CarObject);
        // Leave weak references intact: null on a LATER tick is observation.
    }

    void HCSiphonTerminal()
    {
        m_Done = true;
        HCSiphonDetach();
        m_Receipt.elapsed_seconds = GetGame().GetTickTime() - m_Started;
        m_Receipt.complete = !m_Receipt.failed && m_Receipt.car_deleted && m_Receipt.actor_deleted && m_Receipt.vessel_deleted && m_Receipt.transfer_attempted && m_Receipt.conservation_observed;
        if (HCSiphonSave() && m_Receipt.complete)
            Print("[HC Siphon Probe] COMPLETE run=@RUN@ nondurable only");
        else
            Print("[HC Siphon Probe] FAIL run=@RUN@ reason=" + m_Receipt.reason);
    }

    void HCSiphonTick()
    {
        if (m_Done) return;
        m_Receipt.ticks++;
        float now = GetGame().GetTickTime();
        array<PlayerIdentity> identities = new array<PlayerIdentity>;
        GetGame().GetPlayerIndentities(identities);
        if (identities.Count() > m_Receipt.max_observed_clients)
            m_Receipt.max_observed_clients = identities.Count();
        if (!m_Receipt.server_context || identities.Count() > 0)
            HCSiphonCleanup("isolated-server-without-clients-required");
        if (!(now >= 0) || now < m_LastTick || now - m_Started > @DEADLINE@ || m_Receipt.ticks > 1000 || m_Receipt.frames > 20000)
            HCSiphonCleanup("internal-deadline-clock-or-budget");
        m_LastTick = now;
        if (m_Phase == 4) HCSiphonCleanup("native-callback-interrupted");
        if (m_Phase == 0) HCSiphonSpawn(now);
        if (m_Phase == 1 && now - m_StageStarted >= 1) HCSiphonStart(now);
        if (m_Phase == 2 && now - m_StageStarted >= 1) HCSiphonFinishTransfer();
        if (m_Phase == 3)
        {
            if (!m_DeletesIssued)
            {
                HCSiphonDeleteOwned();
                return;
            }
            m_Receipt.car_deleted = !m_CarObject;
            m_Receipt.actor_deleted = !m_ActorObject;
            m_Receipt.vessel_deleted = !m_VesselObject;
            if (!m_CarObject && !m_ActorObject && !m_VesselObject)
                HCSiphonTerminal();
            else if (now - m_CleanupStarted > 2)
            {
                m_Receipt.failed = true;
                m_Receipt.reason = "owned-deletion-unconfirmed";
                HCSiphonTerminal();
            }
        }
    }

    void HCSiphonFrame(float timeslice)
    {
        if (m_Done) return;
        m_Receipt.frames++;
        float now = GetGame().GetTickTime();
        if (now < m_LastTick || now >= m_NextFrameTick)
        {
            m_NextFrameTick = now + 0.25;
            HCSiphonTick();
        }
    }

    override void OnMissionFinish()
    {
        HCSiphonDetach();
        if (m_Receipt && !m_Done)
        {
            HCSiphonCleanup("mission-ended-before-observed-cleanup");
            HCSiphonDeleteOwned();
            m_Receipt.complete = false;
            HCSiphonSave();
        }
        super.OnMissionFinish();
    }
}
'''


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    prepare=commands.add_parser('prepare')
    for field in ('source','out','scripts'): prepare.add_argument('--'+field,type=Path,required=True)
    for field in ('x','z','rate-ml','cap-ml','fuel-liters'): prepare.add_argument('--'+field,type=float,required=True)
    for field in ('car-class','vessel-class'): prepare.add_argument('--'+field,required=True)
    prepare.add_argument('--actor-class',default='SurvivorM_Mirek')
    prepare.add_argument('--mode',choices=MODES,default='stock-ce')
    prepare.add_argument('--outer-timeout-seconds',type=int,default=90)
    validate=commands.add_parser('validate')
    validate.add_argument('--result',type=Path,required=True)
    validate.add_argument('--mission',type=Path,required=True)
    validate.add_argument('--outer-elapsed-seconds',type=float,required=True)
    validate.add_argument('--outer-outcome',choices=('completed','timed-out'),required=True)
    args=vars(parser.parse_args(argv)); command=args.pop('command')
    if command=='prepare':
        source=args.pop('source'); destination=args.pop('out'); scripts=args.pop('scripts')
        result=prepare_probe(source,destination,scripts,**args)
    else:
        path=args.pop('result'); mission=args.pop('mission'); outcome=args.pop('outer_outcome')
        result=validate_result(path,mission,outer_timed_out=outcome=='timed-out',**args)
    print(json.dumps(result,sort_keys=True,indent=2,allow_nan=False))


if __name__=='__main__': main()
