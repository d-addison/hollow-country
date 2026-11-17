"""Actor-free, disposable startup control. This module NEVER launches DayZ.

prepare_probe(stock,freshdest,scripts_root,mode='stock-ce',run_id=None).
The stock factory and all stock behavior are retained except that the explicit
ce-disabled-control mode omits ONLY ce.InitOffline(). No gameplay acceptance.
SYSTEM callbacks are registered, never invoked manually. Native watchdog 60s;
an external <=180s supervisor is mandatory because blocked native calls cannot
be preempted by script. Receipts are observations, not engine authentication.
"""
from pathlib import Path, PurePosixPath
import re
import secrets

from tools.setup import diagnostic_mission as staging
from tools.setup.fuel_siphon_probe import _safe
from tools.setup.infected_death_probe import _read, _sha, _encode, _decode_json, _number

MARKER='.hc-native-startup-probe.json'
RESULT='hc-native-startup-result.json'
KIND='native-actor-free-startup-control'
MAX_JSON_BYTES=256*1024
MAX_OUTER_SECONDS=180
MODES=('stock-ce','ce-disabled-control')
LIFECYCLE=('INIT_ENTER','INIT_EXIT','MAIN_ENTER','CREATE_HIVE_ENTER',
    'CREATE_HIVE_EXIT','CE_INIT_ENTER','CE_INIT_EXIT','MAIN_EXIT','START_ENTER','START_EXIT')
INTERFACES={
    '3_Game/Hive/Hive.c': ('proto native void InitOffline();','proto native Hive CreateHive();'),
    '5_Mission/mission/missionServer.c': ('override void OnInit()', 'super.OnInit();',
        'override void OnMissionStart()', 'super.OnMissionStart();'),
    '3_Game/DayZGame.c': ('GetCallQueue(CALL_CATEGORY_SYSTEM).Tick(timeslice)',
        'GetUpdateQueue(CALL_CATEGORY_SYSTEM).Invoke(timeslice)'),
    '2_GameLib/tools.c': ('void CallLater(func fn, int delay = 0, bool repeat = false',
        'void Remove(func fn)', 'bool Insert(func fn'),
    '3_Game/Global/Game.c': ('GetTickTime()', 'GetWorldName( out string world_name )',
        'GetVersion( out string version )', 'IsServer()'),
    '3_Game/tools/JsonFileLoader.c': ('static bool SaveFile(string filename, T data, out string errorMessage)',),
}


def inspect_interfaces(root):
    records={}
    for name,tokens in INTERFACES.items():
        data=_read(_safe(Path(root)/name),2*1024*1024)
        text=' '.join(data.decode('utf-8-sig').split())
        if any(' '.join(token.split()) not in text for token in tokens):
            raise ValueError('installed interface mismatch: '+name)
        records[name]=dict(bytes=len(data),sha256=_sha(data))
    return records


def _mask(text):
    # Preserve offsets/newlines while removing comments and string literals.
    pattern=r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"'
    masked=re.sub(pattern,lambda m:''.join('\n' if c=='\n' else ' ' for c in m[0]),text)
    if '/*' in masked or '"' in masked or '\x00' in text:
        raise ValueError('unterminated or unsupported lexical input')
    return masked


def _block(masked, opening):
    depth=0
    for index in range(opening,len(masked)):
        if masked[index]=='{': depth+=1
        if masked[index]=='}':
            depth-=1
            if depth==0: return index
    raise ValueError('unbalanced stock block')


def _instrument(data,mode,run_id):
    text=data.decode('utf-8-sig'); masked=_mask(text)
    if 'HCStartup' in text or '#' in masked:
        raise ValueError('instrumented/preprocessed mission forbidden')
    mains=list(re.finditer(r'\bvoid\s+main\s*\(\s*\)\s*\{',masked))
    missions=list(re.finditer(r'\bclass\s+CustomMission\s*:\s*MissionServer\s*\{',masked))
    if len(mains)!=1 or len(missions)!=1:
        raise ValueError('one stock main and CustomMission required')
    if len(staging._FACTORY.findall(masked.encode()))!=1 or len(re.findall(r'\bCreateCustomMission\s*\(',masked))!=1:
        raise ValueError('exact stock factory required')
    mopen=mains[0].end()-1; mend=_block(masked,mopen)
    copen=missions[0].end()-1; cend=_block(masked,copen)
    if re.search(r'\b(?:OnInit|OnMissionStart|OnMissionFinish)\s*\(',masked[copen:cend]):
        raise ValueError('existing lifecycle override needs explicit review')
    # Restrict to the inspected stock statement pair; do not parse arbitrary code.
    native=re.compile(r'\bHive\s+ce\s*=\s*CreateHive\s*\(\s*\)\s*;\s*'
        r'if\s*\(\s*ce\s*\)\s*(?:\{\s*)?ce\s*\.\s*InitOffline\s*\(\s*\)\s*;\s*(?:\})?')
    matches=list(native.finditer(masked,mopen+1,mend))
    if len(matches)!=1 or len(re.findall(r'\bCreateHive\s*\(',masked))!=1 or len(re.findall(r'\bInitOffline\s*\(',masked))!=1:
        raise ValueError('exact stock Hive/CreateHive/InitOffline pair required')
    match=matches[0]
    # Preserve the exact CreateHive statement and keep comments outside the pair.
    statement_end=text.index(';',match.start())+1
    create=text[match.start():statement_end]
    ce='HCStartupControl.Mark("CE_INIT_OMITTED");'
    if mode=='stock-ce':
        ce='HCStartupControl.Mark("CE_INIT_ENTER");\n        ce.InitOffline();\n        HCStartupControl.Mark("CE_INIT_EXIT");'
    replacement='HCStartupControl.Mark("CREATE_HIVE_ENTER");\n    '+create+'\n    HCStartupControl.HiveObserved(ce);\n    HCStartupControl.Mark("CREATE_HIVE_EXIT");\n    if (ce)\n    {\n        '+ce+'\n    }\n    '
    edits=[(mopen+1,mopen+1,'\n    HCStartupControl.Begin();\n    HCStartupControl.Mark("MAIN_ENTER");\n'),
           (match.start(),match.end(),replacement),
           (mend,mend,'\n    HCStartupControl.Mark("MAIN_EXIT");\n'),
           (copen+1,copen+1,LIFECYCLE_HOOK)]
    for start,end,replacement in sorted(edits,reverse=True):
        text=text[:start]+replacement+text[end:]
    return (text+HOOK.replace('@RUN@',run_id).replace('@MODE@',mode)).encode()


def prepare_probe(stock,freshdest,scripts_root,mode='stock-ce',run_id=None):
    run_id=secrets.token_hex(16) if run_id is None else run_id
    if mode not in MODES or type(run_id) is not str or not re.fullmatch('[0-9a-f]{32}',run_id):
        raise ValueError('fixed mode and hexadecimal nonce required')
    stock,freshdest,scripts_root=map(_safe,(stock,freshdest,scripts_root))
    for other in (stock,scripts_root):
        if freshdest==other or freshdest in other.parents or other in freshdest.parents:
            raise ValueError('overlapping paths forbidden')
    if not stock.is_dir() or freshdest.exists(): raise ValueError('fresh destination required')
    interfaces=inspect_interfaces(scripts_root)
    files,dirs,total=staging._inventory(stock)
    if any(p.parts[0].startswith(('storage','profiles')) for p in [p for p,_ in files]+dirs):
        raise ValueError('runtime storage forbidden')
    if any(p.name.startswith(('.hc-','hc-')) for p,_ in files):
        raise ValueError('previous probe forbidden')
    # Bind every read to the inventory identity; bound actual retained bytes,
    # including growth races, before allocating the next snapshot.
    if len(files) + len(dirs) + 1 > staging.MAX_ENTRIES:
        raise ValueError('manifest entry reserve exceeded')
    snapshots = {}
    actual_total = 0
    for relative, identity in files:
        source = stock / relative
        staging._unchanged(source, identity)
        limit = min(staging.MAX_FILE_BYTES, staging.MAX_TOTAL_BYTES - actual_total)
        if str(relative) == 'init.c':
            limit = min(limit, staging.MAX_INIT_BYTES)
        data = _read(source, limit)
        staging._unchanged(source, identity)
        actual_total += len(data)
        if actual_total > staging.MAX_TOTAL_BYTES:
            raise ValueError('actual snapshot total budget exceeded')
        snapshots[str(relative)] = data
    original = snapshots.get('init.c', b'')
    if not original or len(original) > staging.MAX_INIT_BYTES:
        raise ValueError('bounded stock init required')
    emitted = _instrument(original, mode, run_id)
    if len(emitted) > staging.MAX_FILE_BYTES:
        raise ValueError('generated init budget exceeded')
    manifest = dict(schema=1, kind=KIND, run_id=run_id, mode=mode,
        native_watchdog_seconds=60, max_outer_seconds=MAX_OUTER_SECONDS,
        max_owned_entities=0, gameplay_acceptance=False, interfaces=interfaces,
        directories=[str(p) for p in sorted(dirs)], files={})
    for relative, data in sorted(snapshots.items()):
        output = emitted if relative == 'init.c' else data
        manifest['files'][relative] = dict(
            source_sha256=_sha(data), sha256=_sha(output), bytes=len(output))
    encoded = _encode(manifest)
    emitted_total = actual_total - len(original) + len(emitted) + len(encoded)
    if len(encoded) > MAX_JSON_BYTES or emitted_total > staging.MAX_TOTAL_BYTES:
        raise ValueError('generated mission/manifest total budget exceeded')
    # No destination exists until all input and emitted-byte budgets pass.
    freshdest.mkdir(parents=True, exist_ok=False)
    for relative in sorted(dirs, key=lambda p: (len(p.parts), str(p))):
        (freshdest / relative).mkdir()
    for relative, data in sorted(snapshots.items()):
        output = emitted if relative == 'init.c' else data
        path = _safe(freshdest / relative)
        with path.open('xb') as stream:
            stream.write(output)
        if _read(path, len(output)) != output:
            raise ValueError('staging readback failed')
    with (freshdest / MARKER).open('xb') as stream:
        stream.write(encoded)
    if _read(freshdest / MARKER, MAX_JSON_BYTES) != encoded:
        raise ValueError('manifest readback failed')
    return manifest


def _relative(name, directory=False):
    if type(name) is not str:
        raise ValueError('staged path must be text')
    relative = PurePosixPath(name)
    if (not name or not relative.parts or relative.is_absolute()
            or '..' in relative.parts or '\\' in name or ':' in name
            or str(relative) != name):
        raise ValueError('invalid staged path')
    maximum = staging.MAX_DEPTH if directory else staging.MAX_DEPTH + 1
    if len(relative.parts) > maximum:
        raise ValueError('staged depth budget')
    return relative


def validate_mission(mission, *, expected_sha256=None):
    """Bounded point-in-time tree verification, not filesystem authentication."""
    mission = _safe(mission)
    manifest_data = _read(mission / MARKER, MAX_JSON_BYTES)
    if expected_sha256 is not None and _sha(manifest_data) != expected_sha256:
        raise ValueError('staged manifest drift')
    manifest = _decode_json(manifest_data)
    if (type(manifest.get('schema')) is not int or manifest['schema'] != 1
            or manifest.get('kind') != KIND or manifest.get('mode') not in MODES
            or type(manifest.get('run_id')) is not str
            or not re.fullmatch('[0-9a-f]{32}', manifest['run_id'])):
        raise ValueError('staged manifest mismatch')
    files = manifest.get('files')
    directories = manifest.get('directories', [])
    if (type(files) is not dict or not 1 <= len(files) < staging.MAX_ENTRIES
            or 'init.c' not in files or MARKER in files
            or type(directories) is not list
            or len(files) + len(directories) + 1 > staging.MAX_ENTRIES):
        raise ValueError('bounded staged inventory required')
    expected_dirs = set()
    for name in directories:
        _relative(name, directory=True)
        if name in expected_dirs:
            raise ValueError('duplicate staged directory')
        expected_dirs.add(name)
    total = len(manifest_data)
    for name, row in files.items():
        _relative(name)
        if type(row) is not dict:
            raise ValueError('staged file record required')
        size = row.get('bytes')
        if type(size) is not int or not 0 <= size <= staging.MAX_FILE_BYTES:
            raise ValueError('staged size budget')
        if type(row.get('sha256')) is not str or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('staged digest required')
        total += size
        if total > staging.MAX_TOTAL_BYTES:
            raise ValueError('staged total budget')
    # _inventory bounds traversal count/depth/bytes and rejects links/special
    # nodes. Exact sets include empty directories and the reserved marker.
    actual_files, actual_dirs, _ = staging._inventory(mission)
    if ({str(p) for p, _ in actual_files} != set(files) | {MARKER}
            or {str(p) for p in actual_dirs} != expected_dirs):
        raise ValueError('unlisted or missing staged node')
    for relative, identity in actual_files:
        path = mission / relative
        staging._unchanged(path, identity)
        if str(relative) == MARKER:
            if _read(path, MAX_JSON_BYTES) != manifest_data:
                raise ValueError('manifest changed during verification')
        else:
            row = files[str(relative)]
            if _sha(_read(path, row['bytes'])) != row['sha256']:
                raise ValueError('staged source drift')
        staging._unchanged(path, identity)
    return manifest, manifest_data


def _flag(value,expected):
    if type(value) not in (bool,int) or value not in (0,1) or bool(value)!=expected:
        raise ValueError('native bool flag mismatch')


def validate_result(path,mission,*,outer_timed_out,outer_elapsed_seconds,_snapshot=None):
    if outer_timed_out is not False: raise ValueError('actual non-timeout outcome required')
    _number(outer_elapsed_seconds,0,MAX_OUTER_SECONDS)
    manifest, manifest_data = validate_mission(mission)
    _safe(path)
    data=_read(path,MAX_JSON_BYTES) if _snapshot is None else _snapshot
    if type(data) is not bytes or len(data)>MAX_JSON_BYTES: raise ValueError('bounded receipt snapshot required')
    row=_decode_json(data)
    if type(row.get('schema')) is not int or row['schema']!=1 or row.get('kind')!=KIND:
        raise ValueError('receipt schema mismatch')
    if row.get('run_id')!=manifest.get('run_id') or row.get('mode')!=manifest['mode']:
        raise ValueError('receipt nonce/mode mismatch')
    for field,expected in (('server_context',True),('complete',True),('failed',False),
        ('callbacks_detached',True),('ce_present',True),('gameplay_acceptance',False)):
        _flag(row.get(field),expected)
    if row.get('reason')!='' or type(row.get('entities_created')) is not int or row['entities_created']!=0:
        raise ValueError('failed or entity-bearing receipt')
    for field in ('world','engine_version'):
        if type(row.get(field)) is not str or not 1<=len(row[field])<=128: raise ValueError('native provenance required')
    _number(row.get('elapsed_seconds'),0,60)
    for kind,maximum in (('frame',1024),('queue',128)):
        entries=row.get(kind+'_entries'); exits=row.get(kind+'_exits')
        if type(entries) is not int or not 2<=entries<=maximum or type(exits) is not int or exits!=entries:
            raise ValueError('actual balanced callback observations required')
    ordinals=row.get('queue_update_ordinals')
    if type(ordinals) is not list or len(ordinals)!=2 or any(type(n) is not int for n in ordinals) or not 0<=ordinals[0]<ordinals[1]<row['frame_entries']:
        raise ValueError('two distinct actual update intervals required')
    events=row.get('events')
    if type(events) is not list or not 1<=len(events)<=64 or any(type(e) is not str for e in events):
        raise ValueError('bounded checkpoint events required')
    required=list(LIFECYCLE)
    if row['mode']=='ce-disabled-control':
        required[required.index('CE_INIT_ENTER')]='CE_INIT_OMITTED'; required.remove('CE_INIT_EXIT')
    allowed=set(required)|{'QUEUE_ENTER','QUEUE_EXIT','UPDATE_ENTER','UPDATE_EXIT'}
    if any(e not in allowed for e in events) or any(events.count(e)!=1 for e in required):
        raise ValueError('lifecycle checkpoint evidence incomplete')
    for start,end in (('INIT_ENTER','INIT_EXIT'),('MAIN_ENTER','MAIN_EXIT'),
                      ('START_ENTER','START_EXIT'),('CREATE_HIVE_ENTER','CREATE_HIVE_EXIT')):
        if events.index(start)>=events.index(end): raise ValueError('checkpoint order invalid')
    mainchain=['MAIN_ENTER','CREATE_HIVE_ENTER','CREATE_HIVE_EXIT']
    mainchain+=['CE_INIT_OMITTED'] if row['mode']=='ce-disabled-control' else ['CE_INIT_ENTER','CE_INIT_EXIT']
    mainchain+=['MAIN_EXIT']
    if [events.index(e) for e in mainchain]!=sorted(events.index(e) for e in mainchain):
        raise ValueError('stock main checkpoints reordered')
    for kind in ('QUEUE','UPDATE'):
        if [e for e in events if e.startswith(kind+'_')]!=[kind+'_ENTER',kind+'_EXIT']*2:
            raise ValueError('real balanced queue/update markers required')
    return dict(schema=1,kind=KIND,run_id=row['run_id'],mode=row['mode'],
        startup_control_complete=True,gameplay_acceptance=False,
        receipt_sha256=_sha(data),receipt=row,mission_manifest_sha256=_sha(manifest_data))


LIFECYCLE_HOOK='''
    override void OnInit()
    {
        HCStartupControl.Begin();
        HCStartupControl.Mark("INIT_ENTER");
        super.OnInit();
        HCStartupControl.Mark("INIT_EXIT");
    }
    override void OnMissionStart()
    {
        HCStartupControl.Mark("START_ENTER");
        super.OnMissionStart();
        HCStartupControl.Mark("START_EXIT");
    }
    override void OnMissionFinish()
    {
        HCStartupControl.Interrupt();
        super.OnMissionFinish();
    }
'''

HOOK='''
// DISPOSABLE actor-free startup control; NEVER gameplay acceptance.
class HCStartupReceipt
{
    int schema = 1;
    string kind = "native-actor-free-startup-control";
    string run_id = "@RUN@";
    string mode = "@MODE@";
    bool server_context;
    string world;
    string engine_version;
    bool complete;
    bool failed;
    string reason;
    ref array<string> events = new array<string>;
    int frame_entries;
    int frame_exits;
    int queue_entries;
    int queue_exits;
    ref array<int> queue_update_ordinals = new array<int>;
    float elapsed_seconds;
    bool callbacks_detached;
    bool ce_present;
    bool gameplay_acceptance = false;
    int entities_created = 0;
}
class HCStartupControl
{
    static ref HCStartupReceipt State;
    static bool Armed;
    static bool Done;
    static float Started;
    static float LastTime;
    static void Begin()
    {
        if (State || Done) return;
        if (FileExist("$profile:hc-native-startup-result.json"))
        {
            Done = true;
            Print("[HC Startup Probe] FAIL stale receipt run=@RUN@");
            return;
        }
        State = new HCStartupReceipt;
        State.server_context = GetGame().IsServer();
        GetGame().GetWorldName(State.world);
        GetGame().GetVersion(State.engine_version);
        Started = GetGame().GetTickTime();
        LastTime = Started;
        Save();
        if (Done) return;
        Armed = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCStartupQueue, 100, true);
        GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(HCStartupFrame);
    }
    static void Detach()
    {
        if (Armed)
        {
            Armed = false;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCStartupQueue);
            GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCStartupFrame);
        }
        State.callbacks_detached = true;
    }
    static void Save()
    {
        if (!State) return;
        string error;
        if (!JsonFileLoader<HCStartupReceipt>.SaveFile("$profile:hc-native-startup-result.json", State, error))
        {
            Done = true;
            State.failed = true;
            State.complete = false;
            State.reason = "receipt-write-failed";
            Detach();
            Print("[HC Startup Probe] FAIL receipt-write-failed run=@RUN@");
        }
    }
    static void Fail(string reason)
    {
        if (!State || Done) return;
        Done = true;
        State.failed = true;
        State.reason = reason;
        Detach();
        Save();
        Print("[HC Startup Probe] FAIL " + reason + " run=@RUN@");
    }
    static bool Check()
    {
        if (!State || Done) return false;
        float now = GetGame().GetTickTime();
        State.elapsed_seconds = now - Started;
        if (now != now || now < LastTime || State.elapsed_seconds > 60 || State.frame_entries > 1024 || State.queue_entries > 128)
        {
            Fail("watchdog-or-clock-or-callback-cap");
            return false;
        }
        LastTime = now;
        return true;
    }
    static void Mark(string checkpoint)
    {
        if (!State || State.complete) return;
        if (State.events.Count() >= 64)
        {
            Fail("event-cap");
            return;
        }
        State.events.Insert(checkpoint);
        Print("[HC Startup Probe] " + checkpoint + " run=@RUN@");
        // Preserve a real late native return even after watchdog failure. It
        // remains a FAILED receipt; callbacks cannot convert it to success.
        if (!Done && !Check()) return;
        Save();
    }
    static void HiveObserved(Hive hiveInstance)
    {
        if (!State || Done) return;
        State.ce_present = hiveInstance != null;
        if (!hiveInstance) Fail("CreateHive-returned-null");
    }
    static bool Has(string checkpoint)
    {
        return State.events.Find(checkpoint) >= 0;
    }
    static void CompleteIfReady()
    {
        if (!Check()) return;
        if (State.frame_entries < 2 || State.frame_entries != State.frame_exits) return;
        if (State.queue_entries < 2 || State.queue_entries != State.queue_exits) return;
        if (State.queue_update_ordinals.Count() != 2) return;
        if (State.queue_update_ordinals[1] >= State.frame_exits) return;
        if (!Has("MAIN_EXIT") || !Has("INIT_EXIT") || !Has("START_EXIT") || !State.ce_present || !State.server_context) return;
        Done = true;
        State.complete = true;
        Detach();
        Save();
        if (!State.failed) Print("[HC Startup Probe] COMPLETE run=@RUN@ startup-control-only");
    }
    static void HCStartupQueue()
    {
        if (!Check()) return;
        State.queue_entries++;
        bool record = false;
        int count = State.queue_update_ordinals.Count();
        if (count == 0) record = true;
        else if (count == 1 && State.frame_exits > State.queue_update_ordinals[0]) record = true;
        if (record)
        {
            State.queue_update_ordinals.Insert(State.frame_exits);
            Mark("QUEUE_ENTER");
        }
        State.queue_exits++;
        if (record) Mark("QUEUE_EXIT");
        CompleteIfReady();
    }
    static void HCStartupFrame(float timeslice)
    {
        if (!Check()) return;
        State.frame_entries++;
        if (State.frame_entries <= 2) Mark("UPDATE_ENTER");
        State.frame_exits++;
        if (State.frame_entries <= 2) Mark("UPDATE_EXIT");
        CompleteIfReady();
    }
    static void Interrupt()
    {
        Fail("mission-finish-before-completion");
    }
}
'''
