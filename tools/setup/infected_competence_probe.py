"""Stage/validate disposable server-only infected observations (#18/#19); never launch.

stage --destination DIR [--trials-json FILE] [--native-scripts CACHE]
survey --mapgrouppos STOCK_XML --output trials.json [--classes CLASS ...]
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
from collections import Counter
import copy
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

try:
    from . import diagnostic_mission as dm
    from . import probe_runtime as rt
    from . import ce_probe as ce
except ImportError:
    import diagnostic_mission as dm
    import probe_runtime as rt
    import ce_probe as ce

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
    'crawl_health_only': ('server_observable', 'LeftLeg health-only decrease and IsCrawling endpoints; hit-path not exercised, no crawl-transition inference.'),
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
    ('3_Game/Global/Game.c', 1176, 'SurfaceY'),
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
        if trial.get('fixture_status') not in ('unqualified-candidate', 'operator-surveyed', 'stock-derived'):
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


def survey(stock_path, *, classes=None, class_limit=3, per_class=1, spawn_offset_m=3.0):
    """Read stock placements only; derived candidates still require runtime qualification.

    RPY means roll/pitch/yaw in degrees; yaw is component 2. Offset is a candidate
    bearing, not an assertion about the building's door or a reachable nav position.
    """
    _integer(class_limit, 1, MAX_TRIALS, 'class limit')
    _integer(per_class, 1, MAX_TRIALS, 'per class')
    if type(spawn_offset_m) not in (float, int) or not math.isfinite(spawn_offset_m) or not 1 <= spawn_offset_m <= 10:
        raise ValueError('spawn offset must be finite and within 1..10m')
    data = rt._read_bounded(Path(stock_path), ce.MAX_XML_BYTES)
    placements = ce.parse_placements(data)
    if classes is not None and (not classes or len(set(classes)) != len(classes)):
        raise ValueError('unique selected classes required')
    selected = sorted(placements if classes is None else classes)[:class_limit]
    if classes is not None and set(classes) - placements.keys():
        raise ValueError('missing selected classes')
    if not selected:
        raise ValueError('no selected placements')
    rotations = {}
    for node in ET.fromstring(data).iter('group'):
        name = node.get('name')
        if name not in selected:
            continue
        position = tuple(float(value) for value in node.get('pos').split())
        tokens = (node.get('rpy') or '').split()
        try:
            rotation = tuple(float(value) for value in tokens)
        except ValueError as error:
            raise ValueError('finite rpy triple required') from error
        if len(rotation) != 3 or not all(math.isfinite(value) and abs(value) <= 360 for value in rotation):
            raise ValueError('finite rpy triple required')
        key = (name, position)
        if key in rotations and rotations[key] != rotation:
            raise ValueError('ambiguous placement rpy')
        rotations[key] = rotation
    trials = []
    for name in selected:
        for position in ce.select_placements(placements[name], per_class):
            yaw = math.radians(rotations[name, position][2])
            spawn = [position[0] + spawn_offset_m * math.sin(yaw), position[1],
                     position[2] + spawn_offset_m * math.cos(yaw)]
            for kind, (state, reason) in KINDS.items():
                trials.append(dict(id=f't{len(trials):03}', kind=kind, support_state=state, reason=reason,
                                   structure=name, position=spawn.copy(), structure_position=list(position),
                                   fixture_status='stock-derived'))
    return dict(schema=1, kind='infected-competence-trials', trials=check_trials(trials),
                survey=dict(stock_sha256=rt.sha256(data),
                            selection=dict(classes=selected, class_limit=class_limit, per_class=per_class,
                                           spawn_offset_m=spawn_offset_m, yaw_component='rpy[2] degrees',
                                           kinds=list(KINDS))))


def _survey_trials(document):
    if (set(document) != {'schema', 'kind', 'trials', 'survey'} or document.get('schema') != 1 or
            document.get('kind') != 'infected-competence-trials'):
        raise ValueError('unknown survey document')
    metadata = document['survey']
    if (not isinstance(metadata, dict) or set(metadata) != {'stock_sha256', 'selection'} or
            not re.fullmatch(r'[0-9a-f]{64}', str(metadata.get('stock_sha256', '')))):
        raise ValueError('invalid stock survey provenance')
    selection = metadata['selection']
    if (not isinstance(selection, dict) or set(selection) != {'classes', 'class_limit', 'per_class',
                                                            'spawn_offset_m', 'yaw_component', 'kinds'} or
            selection.get('yaw_component') != 'rpy[2] degrees' or selection.get('kinds') != list(KINDS)):
        raise ValueError('invalid stock survey selection')
    _integer(selection['class_limit'], 1, MAX_TRIALS, 'class limit')
    _integer(selection['per_class'], 1, MAX_TRIALS, 'per class')
    names = selection['classes']
    if (not isinstance(names, list) or not names or any(not isinstance(name, str) for name in names) or
            len(set(names)) != len(names) or len(names) > selection['class_limit'] or
            not 1 <= _finite(selection['spawn_offset_m']) <= 10):
        raise ValueError('invalid stock survey selection')
    trials = check_trials(document['trials'])
    if any(t['fixture_status'] != 'stock-derived' or t['structure'] not in names for t in trials):
        raise ValueError('stock survey trial mismatch')
    return trials, copy.deepcopy(metadata)


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
    string anchor_authored_y;
    string anchor_surface_y;
    string spawn_authored_y;
    string spawn_surface_y;
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
    protected float m_LegBefore;
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
        // Allow a bounded vertical-origin tolerance on slopes; ambiguity still refuses.
        GetGame().GetObjectsAtPosition3D(anchor, 5.0, nearby, proxyCargos);
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
        m_Trial.anchor_authored_y = anchor[1].ToString();
        m_Trial.spawn_authored_y = spawnPoint[1].ToString();
        anchor[1] = GetGame().SurfaceY(anchor[0], anchor[2]);
        spawnPoint[1] = GetGame().SurfaceY(spawnPoint[0], spawnPoint[2]);
        m_Trial.anchor_surface_y = anchor[1].ToString();
        m_Trial.spawn_surface_y = spawnPoint[1].ToString();
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
        if (m_Trial.kind == "limb_damage" || m_Trial.kind == "crawl_health_only")
        {
            float legHealth = m_Actor.GetHealth("LeftLeg", "Health");
            if (legHealth <= 0 || legHealth > 10000)
            {
                m_Trial.reason = "invalid_initial_leg_health";
                HCICNext();
                return;
            }
            m_LegBefore = legHealth;
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
        if (m_Trial.kind == "limb_damage" || m_Trial.kind == "crawl_health_only")
        {
            float currentLegHealth = m_Actor.GetHealth("LeftLeg", "Health");
            if (currentLegHealth >= m_LegBefore)
            {
                m_Trial.reason = "left_leg_health_did_not_fall";
                HCICNext();
                return;
            }
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
        if (m_Trial.support_state == "client_required")
            m_Trial.elapsed_ms = 0;
        else
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


def stage(source_runtime, destination, *, trials=None, start_delay_s=DEFAULT_START_DELAY_S,
          per_trial_ms=DEFAULT_PER_TRIAL_MS, native_scripts=DEFAULT_NATIVE,
          battleye_sha256=rt.BATTLEYE_SHA256, now=None, _wsl_parent=None):
    _registration()  # Refuse before any destination mutation; never self-register.
    fixture_survey = None
    if isinstance(trials, dict):
        trials, fixture_survey = _survey_trials(trials)
    trials = check_trials(default_trials() if trials is None else trials)
    if any(t['fixture_status'] == 'stock-derived' for t in trials) and fixture_survey is None:
        raise ValueError('stock-derived trials require survey provenance document')
    hook = render_hook(trials, start_delay_s, per_trial_ms)
    evidence = verify_native(native_scripts)
    problems = rt.lint_hook(hook.decode('ascii'), native_types=rt.native_type_names(native_scripts),
                            explicit_numbers=True)
    if problems:
        raise ValueError('generated hook violates native compile rules: ' + '; '.join(problems[:3]))
    context = rt.begin(source_runtime, destination, parent=WSL_PARENT if _wsl_parent is None else _wsl_parent,
                       battleye_sha256=battleye_sha256)
    config = context['source']['config_bytes']
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
    built['staged'] = [dict(path=name, sha256=rt._hash_file(Path(destination) / name)[0], bytes=size)
                       for name, size in sorted(dm.walk_plain(destination).items())]
    built['mission_files'].append(dict(path=HASH_NAME, sha256=rt.sha256(hash_data), bytes=64,
                                       source_sha256=None, origin='authored-hook-hash'))
    plan = rt.plan_header(PLAN_KIND, now, before={'acceptance': 'PENDING'})
    plan.update(rt.plan_runtime_fields(context, built))
    plan.update(trials=trials, native_evidence=evidence, mission_files=built['mission_files'],
                staged_files=built['staged'])
    if fixture_survey is not None:
        plan['fixture_survey'] = fixture_survey
    plan['probe'] = dict(mode='server-only-no-clients', clients=0, max_live_entities=1,
                         max_spawned_entities=sum(t['support_state'] == 'server_observable' for t in trials),
                         max_output_bytes=MAX_OUTPUT_BYTES, max_query_objects=MAX_QUERY_OBJECTS,
                         max_doors=MAX_DOORS, start_delay_s=start_delay_s, per_trial_ms=per_trial_ms,
                         wait_minutes=max(5, math.ceil((start_delay_s * 1000 + len(trials) *
                                                      (per_trial_ms + 1100) + 40000) / 60000) + 3),
                         hook_sha256=rt.sha256(hook), hook_bytes=len(hook),
                         observations_kind=OBSERVATIONS_KIND, output_relative_path=OUTPUT_RELATIVE,
                         sentinel_relative_path=SENTINEL_RELATIVE)
    plan['config_treatment'] = dict(unchanged=True, source_sha256=rt.sha256(context['source']['config_bytes']),
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
        if any(t['fixture_status'] == 'stock-derived' for t in plan['trials']):
            _survey_trials(dict(schema=1, kind='infected-competence-trials', trials=plan['trials'],
                                survey=plan.get('fixture_survey')))
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
    if (rt.sha256(config) != plan['config_treatment']['staged_sha256'] or
            plan['config_treatment']['staged_sha256'] != plan['config_treatment']['source_sha256'] or
            plan['config_treatment'].get('unchanged') is not True):
        raise ValueError('staged config mismatch')
    if rt._read_bounded(root / SENTINEL_RELATIVE, 128).strip() != b'status=complete':
        raise ValueError('incomplete sentinel')
    document = _json(root / OUTPUT_RELATIVE, MAX_OUTPUT_BYTES)
    if (not isinstance(document, dict) or type(document.get('schema')) is not int or
            document.get('schema') != 1 or document.get('kind') != OBSERVATIONS_KIND):
        raise ValueError('unknown observations document')
    if set(document) != {'schema', 'kind', 'hook_sha256', 'status', 'world', 'version',
                         'clients', 'spawned', 'deleted', 'trials'}:
        raise ValueError('unknown or missing document fields')
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
                        'spawned', 'deleted', 'elapsed_ms', 'samples', 'doors', 'geometry',
                        'anchor_authored_y', 'anchor_surface_y', 'spawn_authored_y', 'spawn_surface_y'}:
            raise ValueError('unknown or missing trial record fields')
        if any(row.get(key) != trial[key] for key in ('id', 'kind', 'support_state')):
            raise ValueError('trial identity/support mismatch')
        client = trial['support_state'] == 'client_required'
        if type(row.get('observed')) is not bool:
            raise ValueError('explicit observed flag required')
        _integer(row.get('spawned'), 0, 1, 'trial spawned')
        _integer(row.get('deleted'), 0, 1, 'trial deleted')
        if row.get('status') == 'completed':
            _integer(row.get('elapsed_ms'), 0, plan['probe']['per_trial_ms'] + 1000, 'trial elapsed')
        else:
            cap = len(plan['trials']) * (plan['probe']['per_trial_ms'] + 1100) + 30000
            _integer(row.get('elapsed_ms'), 0, cap, 'trial elapsed')
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
            if any(row[field] != '' for field in ('anchor_authored_y', 'anchor_surface_y',
                                                'spawn_authored_y', 'spawn_surface_y')):
                raise ValueError('client_required trial cannot contain terrain observations')
            if (row['observed'] or row.get('status') != 'client_required' or row['spawned'] or
                    row['samples'] or row['doors'] or row['geometry'] or row['elapsed_ms']):
                raise ValueError('client_required trial cannot be observed')
            if row['reason'] != trial['reason']:
                raise ValueError('client-required reason mismatch')
            counts['client_required'] += 1
            continue
        for prefix, position_key in (('anchor', 'structure_position'), ('spawn', 'position')):
            # Enforce float/ToString round trips are not Python double identities.
            if not math.isclose(_finite(row[prefix + '_authored_y']), trial[position_key][1],
                                rel_tol=0, abs_tol=0.01):
                raise ValueError('authored terrain height mismatch')
            _finite(row[prefix + '_surface_y'])
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
            if set(sample) != {'mind', 'target', 'crawling', 'alive', 'left', 'right', 'position'}:
                raise ValueError('unknown or missing sample fields')
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
        if status == 'completed' and trial['kind'] in ('limb_damage', 'crawl_health_only'):
            if _finite(row['samples'][1]['left']) >= _finite(row['samples'][0]['left']):
                raise ValueError('completed left-leg health must fall')
        for index, door in enumerate(row['doors']):
            if (not isinstance(door, dict) or set(door) != {'index', 'opened', 'locked'} or
                    door.get('index') != index or any(
                    type(door.get(field)) is not bool for field in ('opened', 'locked'))):
                raise ValueError('invalid door observation')
    _integer(document.get('spawned'), 0, MAX_TRIALS, 'total spawned')
    _integer(document.get('deleted'), 0, MAX_TRIALS, 'total deleted')
    if document.get('spawned') != spawned or document.get('deleted') != deleted:
        raise ValueError('run cleanup totals mismatch')
    paths = set()
    for row in rows:
        if row['status'] == 'completed':
            paths.add('leg_health_only' if row['kind'] in ('limb_damage', 'crawl_health_only')
                      else 'spawn_state_geometry_door_reads')
    fixture_counts = dict(Counter(trial['fixture_status'] for trial in plan['trials']))
    fixture_limitations = []
    if fixture_counts.get('unqualified-candidate'):
        fixture_limitations.append(f"{fixture_counts['unqualified-candidate']} trials used unqualified-candidate fixtures; "
                                   'not the #18 building/angle denominator')
    return dict(kind=OBSERVATIONS_KIND, runtime_acceptance='PENDING', hook_sha256=expected_sha,
                fixture_status_counts=fixture_counts,
                completed_observation_paths=sorted(paths, reverse=True),
                denominator=counts, spawned=spawned, deletion_calls=deleted,
                limitations=fixture_limitations + ['synthetic/offline validation does not establish DayZ behavior',
                             'trial counts are repetitions, not distinct coverage; shared paths reported once',
                             'limb/crawl health-only stimulus: hit-path not exercised; no crawl-transition inference',
                             'two endpoint samples only; deletion calls require native residual checks',
                             'player LOS/wall attacks/audibility require separate two-client trials'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    surveying = commands.add_parser('survey')
    surveying.add_argument('--mapgrouppos', required=True)
    surveying.add_argument('--output', required=True)
    surveying.add_argument('--classes', nargs='+')
    surveying.add_argument('--class-limit', type=int, default=3)
    surveying.add_argument('--per-class', type=int, default=1)
    surveying.add_argument('--spawn-offset-m', type=float, default=3.0)
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
        if args.command == 'survey':
            document = survey(args.mapgrouppos, classes=args.classes, class_limit=args.class_limit,
                              per_class=args.per_class, spawn_offset_m=args.spawn_offset_m)
            dm.create_exclusive(Path(args.output), (json.dumps(document, indent=2) + '\n').encode('ascii'))
            print(f'wrote stock-derived candidates only: {args.output}; runtime qualification PENDING')
        elif args.command == 'stage':
            if not args.trials_json:
                print('WARNING: --trials-json omitted; default fixtures are unqualified-candidate, '
                      'not the #18 building/angle denominator', file=sys.stderr)
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
