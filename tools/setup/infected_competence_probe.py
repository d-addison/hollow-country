"""Stage/validate disposable server-only infected observations (#18/#19); never launch.

stage --destination DIR [--trials-json FILE] [--native-scripts CACHE]
validate DIR (or report DIR) refuses incomplete, unbound and unsupported receipts.

Default coordinates are UNQUALIFIED authored candidates, not measured building fixtures.
Replace them with surveyed vanilla structure/spawn positions using --trials-json. A missing
or ambiguous structure, crowded query, blocked spawn footprint or native target produces
inconclusive, never a competence pass. Two endpoint samples describe state, not the whole
trajectory. DecreaseHealth is a deliberate diagnostic stimulus, NOT a production correction
or a hit callback: absence of crawl after it cannot establish an inherited injury defect.

No HC addon required; native behavior is inherited. No client trials execute here. No door,
AI movement, collision, sound, target or animation controller is installed. Engine calls are
synchronous: the queued watchdog cannot interrupt a hung call. Outer process timeout and
actual cleanup/compile/config semantics still require coordinator-owned native testing.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import re
import sys

try:
    from . import diagnostic_mission as dm
    from . import probe_runtime as rt
except ImportError:
    import diagnostic_mission as dm
    import probe_runtime as rt

PURPOSE = PLAN_KIND = 'infected-competence-probe'
PLAN_NAME = 'infected-competence-probe-plan.json'
PROBE_DIRECTORY = 'HCInfectedCompetence'
OBSERVATIONS_KIND = 'infected-competence-observations'
OUTPUT_RELATIVE = 'profiles/HCInfectedCompetence/observations.json'
SENTINEL_RELATIVE = 'profiles/HCInfectedCompetence/complete.txt'
HASH_NAME = 'hc-infected-hook-sha.txt'
HASH_RELATIVE = 'mpmissions/' + rt.MISSION_NAME + '/' + HASH_NAME
LAUNCHER_ROW = (PLAN_NAME, PROBE_DIRECTORY, 'observations.json')
PURPOSE_ROW = ('disposable-infected-competence-probe', None,
               ['server mode', 'fresh storage and profiles', 'no clients',
                'inspect observation completeness separately from startup'])
DEFAULT_NATIVE = Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
WSL_PARENT = Path('/mnt/d/HollowCountryLocal')
MAX_TRIALS = 100
MAX_OUTPUT_BYTES = 262144
MAX_QUERY_OBJECTS = 128
MAX_DOORS = 16
DEFAULT_START_DELAY_S = 30
DEFAULT_PER_TRIAL_MS = 5000
KINDS = {
    'spawn_lifecycle': ('server_observable', 'Native spawn/state/delete at authored fixed position.'),
    'mind_no_target': ('server_observable', 'Two native mind-state samples; target presence invalidates no-target control.'),
    'door_state': ('server_observable', 'Read existing door open/locked state only; no contact or opening inference.'),
    'footprint_geometry': ('server_observable', 'Four short view-geometry rays at spawn height; not LOS acquisition or full collision proof.'),
    'limb_damage': ('server_observable', 'One LeftLeg DecreaseHealth stimulus; before/after limb health and alive state.'),
    'crawl_transition': ('server_observable', 'One LeftLeg health decrease; before/after IsCrawling, without forcing transition or hit callback.'),
    'player_los_chase': ('client_required', 'Requires a real connected player and paired LOS/chase observations; server-only has no target.'),
    'player_wall_attack': ('client_required', 'Requires real player damage/attack observations through walls with two clients.'),
    'audible_pursuit': ('client_required', 'Requires two clients hearing pursuit on surfaces, at distance and through occlusion.'),
}

# Every called native/script API, pinned to the user-supplied cache. No native source copied.
# verify_native refuses drift at these exact lines; citations are exported in each plan.
NATIVE = [
    ('2_GameLib/gameLib.c', 4, 'GetGame'),
    ('5_Mission/mission/missionServer.c', 85, 'OnInit'),
    ('3_Game/gameplay.c', 702, 'OnMissionFinish'),
    ('3_Game/Global/Game.c', 1120, 'IsServer'),
    ('3_Game/Global/Game.c', 1166, 'GetPlayerIndentities'),
    ('3_Game/Global/Game.c', 1535, 'GetTime'),
    ('3_Game/Global/Game.c', 1550, 'GetCallQueue'),
    ('3_Game/Global/Game.c', 932, 'GetWorldName'),
    ('3_Game/Global/Game.c', 942, 'GetVersion'),
    ('2_GameLib/tools.c', 61, 'CallLater'),
    ('3_Game/Global/Game.c', 703, 'CreateObjectEx'),
    ('3_Game/Global/Game.c', 705, 'ObjectDelete'),
    ('3_Game/Global/Game.c', 930, 'GetObjectsAtPosition3D'),
    ('3_Game/Entities/Object.c', 287, 'GetPosition'),
    ('3_Game/Entities/Object.c', 467, 'GetType'),
    ('3_Game/Entities/Object.c', 517, 'IsAlive'),
    ('3_Game/Entities/Object.c', 994, 'GetHealth'),
    ('3_Game/Entities/Object.c', 1034, 'DecreaseHealth'),
    ('3_Game/Entities/DayZInfected.c', 107, 'GetInputController'),
    ('3_Game/Entities/DayZInfectedInputController.c', 9, 'GetMindState'),
    ('3_Game/Entities/DayZInfectedInputController.c', 10, 'GetTargetEntity'),
    ('4_World/Entities/Creatures/Infected/ZombieBase.c', 1090, 'IsCrawling'),
    ('3_Game/Entities/Building.c', 31, 'GetDoorCount'),
    ('3_Game/Entities/Building.c', 34, 'IsDoorOpen'),
    ('3_Game/Entities/Building.c', 55, 'IsDoorLocked'),
    ('3_Game/Global/DayZPhysics.c', 199, 'RaycastRV'),
    ('1_Core/proto/EnScript.c', 94, 'Cast'),
    ('1_Core/proto/EnScript.c', 380, 'Count'),
    ('1_Core/proto/EnScript.c', 399, 'Get'),
    ('1_Core/proto/EnScript.c', 407, 'Insert'),
    ('1_Core/proto/EnMath3D.c', 18, 'Vector'),
    ('1_Core/proto/EnConvert.c', 30, 'ToString'),
    ('1_Core/proto/EnConvert.c', 115, 'ToString'),
    ('1_Core/proto/EnConvert.c', 138, 'ToString'),
    ('1_Core/proto/EnString.c', 199, 'Length'),
    ('1_Core/proto/EnSystem.c', 397, 'FileExist'),
    ('1_Core/proto/EnSystem.c', 417, 'OpenFile'),
    ('1_Core/proto/EnSystem.c', 425, 'ReadFile'),
    ('1_Core/proto/EnSystem.c', 443, 'CloseFile'),
    ('1_Core/proto/EnSystem.c', 462, 'FPrint'),
    ('1_Core/proto/EnSystem.c', 481, 'FPrintln'),
    ('1_Core/proto/EnSystem.c', 525, 'MakeDirectory'),
    ('3_Game/tools/JsonFileLoader.c', 85, 'MakeData'),
    ('5_Mission/GUI/ScriptConsole.c', 72, '$mission:'),
    ('3_Game/CE/CentralEconomy.c', 38, 'ECE_PLACE_ON_SURFACE'),
    ('3_Game/CE/CentralEconomy.c', 18, 'ECE_INITAI'),
]


def verify_native(cache):
    result = []
    for relative, line, api in NATIVE:
        lines = (Path(cache) / relative).read_text().splitlines()
        if len(lines) < line or api not in lines[line - 1]:
            raise ValueError(f'native API evidence missing/drift: {relative}:{line} {api}')
        result.append(dict(api=api, file=relative, line=line))
    return result


def default_trials():
    return [dict(id=f't{index:03}', kind=kind, support_state=state, reason=reason,
                 structure='Land_House_1W01', position=[6500.0, 0.0, 2500.0],
                 structure_position=[6505.0, 0.0, 2500.0], fixture_status='unqualified-candidate')
            for index, (kind, (state, reason)) in enumerate(KINDS.items())]


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer {low}..{high}')
    return value


def check_trials(trials):
    if not isinstance(trials, list) or not 1 <= len(trials) <= MAX_TRIALS:
        raise ValueError('trials must contain 1..100 explicit trials')
    ids = set()
    for trial in trials:
        if not isinstance(trial, dict) or trial.get('kind') not in KINDS:
            raise ValueError('unknown trial kind')
        if trial.get('support_state') != KINDS[trial['kind']][0]:
            raise ValueError('trial support state mismatch')
        for name in ('id', 'structure'):
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', str(trial.get(name, ''))):
                raise ValueError('trial identifier/structure must be plain identifiers')
        if trial['id'] in ids:
            raise ValueError('duplicate trial id')
        ids.add(trial['id'])
        if trial.get('reason') != KINDS[trial['kind']][1]:
            raise ValueError('explicit canonical support reason required')
        if trial.get('fixture_status') not in ('unqualified-candidate', 'operator-surveyed'):
            raise ValueError('explicit fixture status required')
        for name in ('position', 'structure_position'):
            position = trial.get(name)
            if not isinstance(position, list) or len(position) != 3:
                raise ValueError('three-coordinate position required')
            for axis, value in enumerate(position):
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError('finite numeric position required')
                if not (0 <= value <= 15360 if axis != 1 else -100 <= value <= 2000):
                    raise ValueError('position outside Chernarus bounds')
        if sum((a - b) ** 2 for a, b in zip(trial['position'], trial['structure_position'])) > 400:
            raise ValueError('spawn must be within 20m of chosen structure anchor')
    return copy.deepcopy(trials)


HOOK_TEMPLATE = r'''
// Hollow Country DISPOSABLE infected competence probe. Runtime acceptance PENDING.
// One owned entity at a time. Two endpoint samples; no player competence inference.
class HCICSample
{
    int mind = -1;
    bool target;
    bool crawling;
    bool alive;
    string left;
    string right;
    string position;
}
class HCICDoor
{
    int index;
    bool opened;
    bool locked;
}
class HCICTrial
{
    string id;
    string kind;
    string support_state;
    string status = "inconclusive";
    string reason;
    bool observed;
    int spawned;
    int deleted;
    int elapsed_ms;
    ref array<ref HCICSample> samples = new array<ref HCICSample>;
    ref array<ref HCICDoor> doors = new array<ref HCICDoor>;
    ref array<int> geometry = new array<int>;
}
class HCICReceipt
{
    int schema = 1;
    string kind = "infected-competence-observations";
    string hook_sha256;
    string status = "partial";
    string world;
    string version;
    int clients;
    int spawned;
    int deleted;
    ref array<ref HCICTrial> trials = new array<ref HCICTrial>;
}
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_Started;
    protected bool m_Done;
    protected bool m_Ready;
    protected int m_Index;
    protected int m_TrialBegin;
    protected int m_Begin;
    protected Object m_Owned;
    protected ZombieBase m_Actor;
    protected ref HCICReceipt m_Receipt;
    protected ref HCICTrial m_Trial;

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_Started)
            return;
        m_Started = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICBegin, @@START@@, false);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICWatchdog, @@WATCHDOG@@, false);
    }

    override void OnMissionFinish()
    {
        HCICCleanup();
        if (m_Ready && !m_Done)
            HCICFinish("partial");
        super.OnMissionFinish();
    }

    bool HCICNoClients()
    {
        array<PlayerIdentity> identities = new array<PlayerIdentity>;
        GetGame().GetPlayerIndentities(identities);
        if (identities.Count() != 0)
        {
            m_Receipt.clients = identities.Count();
            HCICFinish("partial");
            return false;
        }
        return true;
    }

    void HCICBegin()
    {
        if (m_Done)
            return;
        string directory = "$profile:HCInfectedCompetence";
        if (FileExist(directory))
        {
            m_Done = true;
            return;
        }
        if (!MakeDirectory(directory))
        {
            m_Done = true;
            return;
        }
        m_Receipt = new HCICReceipt;
        FileHandle hashFile = OpenFile("$mission:hc-infected-hook-sha.txt", FileMode.READ);
        if (!hashFile)
        {
            m_Done = true;
            return;
        }
        string hookHash;
        int readCount = ReadFile(hashFile, hookHash, 64);
        CloseFile(hashFile);
        if (readCount != 64 || hookHash.Length() != 64)
        {
            m_Done = true;
            return;
        }
        m_Receipt.hook_sha256 = hookHash;
        string worldName;
        string buildName;
        GetGame().GetWorldName(worldName);
        GetGame().GetVersion(buildName);
        m_Receipt.world = worldName;
        m_Receipt.version = buildName;
        m_Ready = true;
        m_Begin = GetGame().GetTime();
        HCICStep();
    }

    void HCICSetup(int sequence, out string structureName, out vector anchor, out vector spawnPoint)
    {
@@CASES@@
    }

    Building HCICStructure(string expected, vector anchor)
    {
        array<Object> nearby = new array<Object>;
        array<CargoBase> proxyCargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(anchor, 2.0, nearby, proxyCargos);
        if (nearby.Count() > 128 || proxyCargos.Count() > 128)
            return null;
        Building chosen;
        int matches = 0;
        for (int scanIndex = 0; scanIndex < nearby.Count() && scanIndex < 128; scanIndex++)
        {
            Building candidate = Building.Cast(nearby.Get(scanIndex));
            if (candidate && candidate.GetType() == expected)
            {
                chosen = candidate;
                matches = matches + 1;
            }
        }
        if (matches != 1)
            return null;
        return chosen;
    }

    bool HCICGeometry(vector spawnPoint)
    {
        bool clear = true;
        vector rayBegin = spawnPoint + Vector(0, 0.8, 0);
        for (int rayIndex = 0; rayIndex < 4; rayIndex++)
        {
            vector rayOffset = Vector(0.6, 0, 0);
            if (rayIndex == 1)
                rayOffset = Vector(-0.6, 0, 0);
            if (rayIndex == 2)
                rayOffset = Vector(0, 0, 0.6);
            if (rayIndex == 3)
                rayOffset = Vector(0, 0, -0.6);
            vector rayEnd = rayBegin + rayOffset;
            vector contactPoint;
            vector contactDirection;
            int contactComponent;
            bool hit = DayZPhysics.RaycastRV(rayBegin, rayEnd, contactPoint, contactDirection, contactComponent);
            int hitValue = 0;
            if (hit)
            {
                hitValue = 1;
                clear = false;
            }
            m_Trial.geometry.Insert(hitValue);
        }
        return clear;
    }

    bool HCICSampleActor()
    {
        if (!m_Actor || !m_Actor.IsAlive())
            return false;
        DayZInfectedInputController nativeInput = m_Actor.GetInputController();
        if (!nativeInput)
            return false;
        HCICSample sampleRow = new HCICSample;
        sampleRow.mind = nativeInput.GetMindState();
        if (nativeInput.GetTargetEntity())
            sampleRow.target = true;
        sampleRow.crawling = m_Actor.IsCrawling();
        sampleRow.alive = m_Actor.IsAlive();
        sampleRow.left = m_Actor.GetHealth("LeftLeg", "Health").ToString();
        sampleRow.right = m_Actor.GetHealth("RightLeg", "Health").ToString();
        vector actualPoint = m_Actor.GetPosition();
        sampleRow.position = actualPoint.ToString();
        m_Trial.samples.Insert(sampleRow);
        if (sampleRow.target)
            return false;
        return true;
    }

    void HCICStep()
    {
        if (m_Done)
            return;
        if (!HCICNoClients())
            return;
        if (GetGame().GetTime() - m_Begin > @@CAP@@)
        {
            HCICFinish("partial");
            return;
        }
        if (m_Index >= @@COUNT@@)
        {
            HCICFinish("complete");
            return;
        }
        m_Trial = new HCICTrial;
        string structureName;
        vector anchor;
        vector spawnPoint;
        HCICSetup(m_Index, structureName, anchor, spawnPoint);
        m_Receipt.trials.Insert(m_Trial);
        m_TrialBegin = GetGame().GetTime();
        if (m_Trial.support_state == "client_required")
        {
            m_Trial.status = "client_required";
            HCICNext();
            return;
        }
        Building structure = HCICStructure(structureName, anchor);
        if (!structure)
        {
            m_Trial.reason = "structure_missing_ambiguous_or_query_budget";
            HCICNext();
            return;
        }
        if (!HCICGeometry(spawnPoint))
        {
            m_Trial.reason = "footprint_ray_hit";
            HCICNext();
            return;
        }
        m_Owned = GetGame().CreateObjectEx("ZmbF_JournalistNormal_Blue", spawnPoint, ECE_PLACE_ON_SURFACE|ECE_INITAI);
        if (m_Owned)
        {
            m_Trial.spawned = 1;
            m_Receipt.spawned = m_Receipt.spawned + 1;
        }
        m_Actor = ZombieBase.Cast(m_Owned);
        if (!HCICSampleActor())
        {
            m_Trial.reason = "spawn_controller_or_no_target_control_failed";
            HCICNext();
            return;
        }
        if (m_Trial.kind == "door_state")
        {
            int doorCount = structure.GetDoorCount();
            if (doorCount < 1 || doorCount > 16)
            {
                m_Trial.reason = "door_budget_or_no_doors";
                HCICNext();
                return;
            }
            for (int doorIndex = 0; doorIndex < doorCount && doorIndex < 16; doorIndex++)
            {
                HCICDoor doorRow = new HCICDoor;
                doorRow.index = doorIndex;
                doorRow.opened = structure.IsDoorOpen(doorIndex);
                doorRow.locked = structure.IsDoorLocked(doorIndex);
                m_Trial.doors.Insert(doorRow);
            }
        }
        if (m_Trial.kind == "limb_damage" || m_Trial.kind == "crawl_transition")
        {
            float legHealth = m_Actor.GetHealth("LeftLeg", "Health");
            if (legHealth <= 0 || legHealth > 10000)
            {
                m_Trial.reason = "invalid_initial_leg_health";
                HCICNext();
                return;
            }
            m_Actor.DecreaseHealth("LeftLeg", "Health", legHealth);
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICObserve, @@PER_TRIAL@@, false);
    }

    void HCICObserve()
    {
        if (m_Done)
            return;
        if (!HCICNoClients())
            return;
        int elapsed = GetGame().GetTime() - m_TrialBegin;
        if (elapsed > @@PER_TRIAL@@ + 1000)
        {
            m_Trial.reason = "trial_time_budget";
            HCICNext();
            return;
        }
        if (!HCICSampleActor())
        {
            m_Trial.reason = "actor_dead_missing_or_target_present";
            HCICNext();
            return;
        }
        m_Trial.observed = true;
        m_Trial.status = "completed";
        m_Trial.reason = "two_endpoint_samples_only";
        HCICNext();
    }

    void HCICCleanup()
    {
        if (m_Owned)
        {
            GetGame().ObjectDelete(m_Owned);
            m_Receipt.deleted = m_Receipt.deleted + 1;
            if (m_Trial)
                m_Trial.deleted = m_Trial.deleted + 1;
        }
        m_Owned = null;
        m_Actor = null;
    }

    void HCICNext()
    {
        HCICCleanup();
        m_Trial.elapsed_ms = GetGame().GetTime() - m_TrialBegin;
        m_Index = m_Index + 1;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICStep, 100, false);
    }

    void HCICWatchdog()
    {
        if (m_Ready && !m_Done)
            HCICFinish("partial");
        m_Done = true;
    }

    void HCICFinish(string outcome)
    {
        if (m_Done)
            return;
        HCICCleanup();
        m_Done = true;
        m_Receipt.status = outcome;
        string outputData;
        string outputError;
        if (!JsonFileLoader<HCICReceipt>.MakeData(m_Receipt, outputData, outputError, false))
            return;
        if (outputData.Length() > 262144)
            return;
        FileHandle outputFile = OpenFile("$profile:HCInfectedCompetence/observations.json", FileMode.WRITE);
        if (!outputFile)
            return;
        FPrint(outputFile, outputData);
        CloseFile(outputFile);
        FileHandle sentinelFile = OpenFile("$profile:HCInfectedCompetence/complete.txt", FileMode.WRITE);
        if (!sentinelFile)
            return;
        FPrintln(sentinelFile, "status=" + outcome);
        CloseFile(sentinelFile);
    }
}
'''


def render_hook(trials=None, start_delay_s=DEFAULT_START_DELAY_S, per_trial_ms=DEFAULT_PER_TRIAL_MS):
    trials = check_trials(default_trials() if trials is None else trials)
    _integer(start_delay_s, 5, 600, 'start delay')
    _integer(per_trial_ms, 1000, 60000, 'per trial ms')
    cases = []
    for index, trial in enumerate(trials):
        # Inputs validated as identifiers/fixed canonical ASCII reasons before interpolation.
        cases.extend([f'        if (sequence == {index})', '        {'])
        for field in ('id', 'kind', 'support_state', 'reason'):
            cases.append(f'            m_Trial.{field} = "{trial[field]}";')
        cases.append(f'            structureName = "{trial["structure"]}";')
        for field, variable in (('structure_position', 'anchor'), ('position', 'spawnPoint')):
            numbers = ', '.join(format(float(v), '.6f') for v in trial[field])
            cases.append(f'            {variable} = Vector({numbers});')
        cases.extend(['            return;', '        }'])
    cap = len(trials) * (per_trial_ms + 1100) + 30000
    text = HOOK_TEMPLATE
    for key, value in dict(CASES='\n'.join(cases), COUNT=len(trials), START=start_delay_s * 1000,
                           PER_TRIAL=per_trial_ms, CAP=cap,
                           WATCHDOG=start_delay_s * 1000 + cap + 10000).items():
        text = text.replace('@@' + key + '@@', str(value))
    if '@@' in text or not text.isascii():
        raise ValueError('unresolved or non-ASCII hook')
    if rt.max_statement_plus(text) > 8:
        raise ValueError('hook exceeds eight binary plus operators per statement')
    return text.encode('ascii')


def _registration():
    if dm._PURPOSES.get(PURPOSE) != PURPOSE_ROW or rt.LAUNCHER_PROBES.get(PURPOSE) != LAUNCHER_ROW:
        raise ValueError('infected-competence-probe shared registration missing; coordinator integration required')


def _no_clients_config(data):
    # Mask comments/strings without shifting offsets; refuse duplicate or nonliteral settings.
    text = data.decode('ascii')
    masked = re.sub(r'"(?:[^"\\]|\\.)*"|/\*.*?\*/|//[^\n]*',
                    lambda m: ' ' * len(m[0]), text, flags=re.S)
    mentions = list(re.finditer(r'\bmaxPlayers\b', masked))
    matches = list(re.finditer(r'\bmaxPlayers\s*=\s*\d+\s*;', masked))
    if len(mentions) != 1 or len(matches) != 1:
        raise ValueError('source config must have one literal maxPlayers setting for no-client staging')
    match = matches[0]
    return (text[:match.start()] + 'maxPlayers = 0;' + text[match.end():]).encode('ascii')


def stage(source_runtime, destination, *, trials=None, start_delay_s=DEFAULT_START_DELAY_S,
          per_trial_ms=DEFAULT_PER_TRIAL_MS, native_scripts=DEFAULT_NATIVE,
          battleye_sha256=rt.BATTLEYE_SHA256, now=None, _wsl_parent=None):
    _registration()  # Refuse before any destination mutation; never self-register.
    trials = check_trials(default_trials() if trials is None else trials)
    hook = render_hook(trials, start_delay_s, per_trial_ms)
    evidence = verify_native(native_scripts)
    problems = rt.lint_hook(hook.decode('ascii'), native_types=rt.native_type_names(native_scripts),
                            explicit_numbers=True)
    if problems:
        raise ValueError('generated hook violates native compile rules: ' + '; '.join(problems[:3]))
    context = rt.begin(source_runtime, destination, parent=WSL_PARENT if _wsl_parent is None else _wsl_parent,
                       battleye_sha256=battleye_sha256)
    config = _no_clients_config(context['source']['config_bytes'])
    built = rt.build_runtime(context, hook, purpose=PURPOSE)
    # Authored hash sidecar avoids a self-referential embedded hook hash. Native reads exactly 64 bytes.
    # Extend the isolated mission manifest and staged inventory explicitly; shared helpers stay unchanged.
    hash_data = rt.sha256(hook).encode('ascii')
    dm.create_exclusive(Path(destination) / HASH_RELATIVE, hash_data)
    manifest = built['manifest']
    manifest['files'][HASH_NAME] = dict(source_sha256=None, staged_sha256=rt.sha256(hash_data),
                                      source_bytes=0, staged_bytes=len(hash_data), origin='authored-hook-hash')
    marker = built['mission_dest'] / dm.MARKER_NAME
    dm.unlink_at(marker)
    dm.create_exclusive(marker, (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    dm._require_staged_tree(built['mission_dest'], manifest)
    dm.unlink_at(Path(destination) / 'serverDZ.cfg')
    dm.create_exclusive(Path(destination) / 'serverDZ.cfg', config)
    built['staged_hash']['serverDZ.cfg'] = rt.sha256(config)
    built['staged'] = [dict(path=name, sha256=rt._hash_file(Path(destination) / name)[0], bytes=size)
                       for name, size in sorted(dm.walk_plain(destination).items())]
    built['mission_files'].append(dict(path=HASH_NAME, sha256=rt.sha256(hash_data), bytes=64,
                                       source_sha256=None, origin='authored-hook-hash'))
    plan = rt.plan_header(PLAN_KIND, now, before={'acceptance': 'PENDING'})
    plan.update(rt.plan_runtime_fields(context, built))
    plan.update(trials=trials, native_evidence=evidence, mission_files=built['mission_files'],
                staged_files=built['staged'])
    plan['probe'] = dict(mode='server-only-no-clients', clients=0, max_live_entities=1,
                         max_spawned_entities=sum(t['support_state'] == 'server_observable' for t in trials),
                         max_output_bytes=MAX_OUTPUT_BYTES, max_query_objects=MAX_QUERY_OBJECTS,
                         max_doors=MAX_DOORS, start_delay_s=start_delay_s, per_trial_ms=per_trial_ms,
                         wait_minutes=max(5, math.ceil((start_delay_s * 1000 + len(trials) *
                                                      (per_trial_ms + 1100) + 40000) / 60000) + 3),
                         hook_sha256=rt.sha256(hook), hook_bytes=len(hook),
                         observations_kind=OBSERVATIONS_KIND, output_relative_path=OUTPUT_RELATIVE,
                         sentinel_relative_path=SENTINEL_RELATIVE)
    plan['config_treatment'] = dict(maxPlayers=0, source_sha256=rt.sha256(context['source']['config_bytes']),
                                    staged_sha256=rt.sha256(config))
    return rt.write_plan(context['destination'], PLAN_NAME, plan)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _json(path, limit):
    return json.loads(rt._read_bounded(path, limit), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def validate_plan(plan):
    if not isinstance(plan, dict) or plan.get('kind') != PLAN_KIND or plan.get('schema_version') != 1:
        raise ValueError('unknown plan')
    try:
        settings = plan['probe']
        hook = render_hook(plan['trials'], settings['start_delay_s'], settings['per_trial_ms'])
        if settings['hook_sha256'] != rt.sha256(hook) or settings['hook_bytes'] != len(hook):
            raise ValueError('hook-sha mismatch in plan')
        if settings['mode'] != 'server-only-no-clients' or settings['clients'] != 0:
            raise ValueError('no-client plan required')
    except (KeyError, TypeError) as error:
        raise ValueError('malformed hook plan') from error
    return hook


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('numeric sample required')
    try:
        number = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError('numeric sample required') from error
    if not math.isfinite(number):
        raise ValueError('nonfinite sample')
    return number


def validate(runtime):
    """Validate source/receipt binding and coverage, never promote native acceptance.

    Deletion counters attest ObjectDelete calls, not a verified residual-world census.
    Receipts are not authenticated against a malicious operator; hashes bind staged bytes.
    """
    root = Path(runtime)
    plan = _json(root / PLAN_NAME, 1024 * 1024)
    hook = validate_plan(plan)
    expected_sha = rt.sha256(hook)
    if rt._read_bounded(root / HASH_RELATIVE, 64) != expected_sha.encode('ascii'):
        raise ValueError('hook-sha sidecar mismatch')
    initial = root / 'mpmissions' / rt.MISSION_NAME / 'init.c'
    init_bytes = rt._read_bounded(initial, dm.MAX_INIT_BYTES + dm.MAX_HOOK_BYTES)
    if not init_bytes.endswith(hook):
        raise ValueError('staged hook-sha mismatch')
    pinned_init = next((entry for entry in plan['staged_files']
                        if entry['path'] == 'mpmissions/' + rt.MISSION_NAME + '/init.c'), None)
    if not pinned_init or rt.sha256(init_bytes) != pinned_init['sha256']:
        raise ValueError('staged hook init hash mismatch')
    config = rt._read_bounded(root / 'serverDZ.cfg', rt.MAX_CONFIG_BYTES)
    if config != _no_clients_config(config) or rt.sha256(config) != plan['config_treatment']['staged_sha256']:
        raise ValueError('no-client config mismatch')
    if rt._read_bounded(root / SENTINEL_RELATIVE, 128).strip() != b'status=complete':
        raise ValueError('incomplete sentinel')
    document = _json(root / OUTPUT_RELATIVE, MAX_OUTPUT_BYTES)
    if (not isinstance(document, dict) or type(document.get('schema')) is not int or
            document.get('schema') != 1 or document.get('kind') != OBSERVATIONS_KIND):
        raise ValueError('unknown observations document')
    if document.get('hook_sha256') != expected_sha:
        raise ValueError('receipt hook-sha mismatch')
    if (document.get('status') != 'complete' or type(document.get('clients')) is not int or
            document.get('clients') != 0):
        raise ValueError('incomplete or client-contaminated run')
    if (str(document.get('world', '')).lower() != 'chernarusplus' or
            not re.search(r'(?<![\d.])1\.30\.164289(?![\d.])', str(document.get('version', '')))):
        raise ValueError('pinned Chernarus/build receipt required')
    rows = document.get('trials')
    if not isinstance(rows, list) or len(rows) != len(plan['trials']):
        raise ValueError('incomplete trial denominator')
    counts = dict(attempted=0, completed=0, inconclusive=0, client_required=0)
    spawned = deleted = 0
    for row, trial in zip(rows, plan['trials']):
        if not isinstance(row, dict) or row.get('kind') not in KINDS:
            raise ValueError('unknown trial kind')
        if set(row) != {'id', 'kind', 'support_state', 'status', 'reason', 'observed',
                        'spawned', 'deleted', 'elapsed_ms', 'samples', 'doors', 'geometry'}:
            raise ValueError('unknown or missing trial record fields')
        if any(row.get(key) != trial[key] for key in ('id', 'kind', 'support_state')):
            raise ValueError('trial identity/support mismatch')
        client = trial['support_state'] == 'client_required'
        if type(row.get('observed')) is not bool:
            raise ValueError('explicit observed flag required')
        _integer(row.get('spawned'), 0, 1, 'trial spawned')
        _integer(row.get('deleted'), 0, 1, 'trial deleted')
        _integer(row.get('elapsed_ms'), 0, plan['probe']['per_trial_ms'] + 1000, 'trial elapsed')
        if row['spawned'] != row['deleted']:
            raise ValueError('incomplete cleanup')
        spawned += row['spawned']
        deleted += row['deleted']
        for field, maximum in (('samples', 2), ('doors', MAX_DOORS), ('geometry', 4)):
            if not isinstance(row.get(field), list) or len(row[field]) > maximum:
                raise ValueError('bounded sample/door/geometry arrays required')
        if not isinstance(row.get('reason'), str) or not 1 <= len(row['reason']) <= 256:
            raise ValueError('explicit bounded outcome reason required')
        if client:
            if (row['observed'] or row.get('status') != 'client_required' or row['spawned'] or
                    row['samples'] or row['doors'] or row['geometry'] or row['elapsed_ms']):
                raise ValueError('client_required trial cannot be observed')
            if row['reason'] != trial['reason']:
                raise ValueError('client-required reason mismatch')
            counts['client_required'] += 1
            continue
        counts['attempted'] += 1
        status = row.get('status')
        if status not in ('completed', 'inconclusive') or row['observed'] != (status == 'completed'):
            raise ValueError('invalid trial outcome')
        if status == 'completed':
            if (row['spawned'] != 1 or len(row['samples']) != 2 or row['geometry'] != [0, 0, 0, 0] or
                    row['elapsed_ms'] < plan['probe']['per_trial_ms']):
                raise ValueError('completed trial needs owned spawn, clear rays and two timed samples')
            if trial['kind'] == 'door_state' and not row['doors']:
                raise ValueError('completed door trial needs door state')
        if trial['kind'] != 'door_state' and row['doors']:
            raise ValueError('door records outside door-state trial')
        counts[status] += 1
        for sample in row['samples']:
            if not isinstance(sample, dict):
                raise ValueError('invalid sample')
            for flag in ('target', 'crawling', 'alive'):
                if type(sample.get(flag)) is not bool:
                    raise ValueError('invalid native bool sample')
            if status == 'completed' and (sample['target'] or not sample['alive']):
                raise ValueError('completed no-target control contaminated')
            _integer(sample.get('mind'), -1, 100, 'mind state')
            for leg in ('left', 'right'):
                if not 0 <= _finite(sample.get(leg)) <= 10000:
                    raise ValueError('invalid limb sample')
            position = sample.get('position')
            if not isinstance(position, str) or len(position) > 128:
                raise ValueError('bounded position sample required')
            coordinates = position.replace('<', '').replace('>', '').replace(',', ' ').split()
            if len(coordinates) != 3:
                raise ValueError('three native position coordinates required')
            for coordinate in coordinates:
                _finite(coordinate)
        for ray in row['geometry']:
            _integer(ray, 0, 1, 'geometry ray')
        for index, door in enumerate(row['doors']):
            if not isinstance(door, dict) or door.get('index') != index or any(
                    type(door.get(field)) is not bool for field in ('opened', 'locked')):
                raise ValueError('invalid door observation')
    _integer(document.get('spawned'), 0, MAX_TRIALS, 'total spawned')
    _integer(document.get('deleted'), 0, MAX_TRIALS, 'total deleted')
    if document.get('spawned') != spawned or document.get('deleted') != deleted:
        raise ValueError('run cleanup totals mismatch')
    return dict(kind=OBSERVATIONS_KIND, runtime_acceptance='PENDING', hook_sha256=expected_sha,
                denominator=counts, spawned=spawned, deletion_calls=deleted,
                limitations=['synthetic/offline validation does not establish DayZ behavior',
                             'two endpoint samples only; deletion calls require native residual checks',
                             'player LOS/wall attacks/audibility require separate two-client trials'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    staging = commands.add_parser('stage')
    staging.add_argument('--destination', required=True)
    staging.add_argument('--source-runtime', default=rt.DEFAULT_SOURCE_RUNTIME)
    staging.add_argument('--trials-json')
    staging.add_argument('--native-scripts', default=str(DEFAULT_NATIVE))
    staging.add_argument('--start-delay-s', type=int, default=DEFAULT_START_DELAY_S)
    staging.add_argument('--per-trial-ms', type=int, default=DEFAULT_PER_TRIAL_MS)
    for name in ('validate', 'report'):
        commands.add_parser(name).add_argument('runtime')
    args = parser.parse_args(argv)
    try:
        if args.command == 'stage':
            trials = _json(args.trials_json, 128 * 1024) if args.trials_json else None
            result = stage(args.source_runtime, args.destination, trials=trials,
                           native_scripts=args.native_scripts, start_delay_s=args.start_delay_s,
                           per_trial_ms=args.per_trial_ms)
            print(f'staged only: {Path(args.destination) / PLAN_NAME}')
            print('hook_sha256=' + result['probe']['hook_sha256'])
        else:
            print(json.dumps(validate(args.runtime), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'infected_competence_probe: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
