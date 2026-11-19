"""E1: world incident registry, native sources and group response.

Spec -> plan -> task: every AI reaction starts from ONE bounded registry of
perceivable world incidents (vanilla gas zones, helicopter wrecks, world-ledger
facts) and from nothing else. Authored Enforce bodies run through the existing
restricted translation ports. All handles, groups, items and coordinates here are
SYNTHETIC; no offline result establishes DayZ, Expansion or CE behavior.

TDD command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_e1_incidents -v
"""
import math
import re
from pathlib import Path
from types import MethodType, SimpleNamespace as N
import unittest

from tests.unit.test_group_server import EArray
from tests.unit import test_map_layers as _layers
from tests.unit.test_map_layers import methods, translate


class EStr(_layers.EStr):
    # Native string.ToLower() lowercases in place (EnString.c); synthetic fixtures are already lowercase.
    def ToLower(self):
        assert self == self.lower()
        return len(self)


ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/World'
XAI = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'
CORE = WORLD / 'HCWorldIncidents.c'
SOURCES = WORLD / 'HCIncidentSources.c'
RESPONSE = XAI / 'HCXAIIncidentResponse.c'


def text(path):
    """Authored source with the translator's two blind spots adapted: `protected` and array fields."""
    source = path.read_text().replace('    protected ', '    ')
    return re.sub(r'^    (?:ref )?array<[^;=(]*> (\w+)(\s*[=;])', r'    Arr \1\2', source, flags=re.M)


def dist_sq(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3))


def base_env(logs=None):
    logs = [] if logs is None else logs
    return dict(
        str=str, Print=logs.append,
        vector=N(DistanceSq=dist_sq, Distance=lambda a, b: math.sqrt(dist_sq(a, b))),
        Vector=lambda x, y, z: [x, y, z],
        Math=N(Sqrt=math.sqrt, Max=max, Min=min, Floor=math.floor, Ceil=math.ceil, AbsFloat=abs),
        HCWorldLimits=N(Token=lambda value: bool(value) and len(value) <= 32, Position=lambda point: 0 <= point[0] <= 15360 and 0 <= point[2] <= 15360),
        EStr=EStr)


def bind(source, cls, env, only=None, **fields):
    """Translate one authored class and bind its methods to a synthetic instance."""
    table, _ = methods(source, cls)
    translate(source, cls, env, only=only)
    obj = N(**fields)
    for name, (static, _, _) in table.items():
        if only and name not in only:
            continue
        setattr(obj, name, env[name] if static else MethodType(env[name], obj))
    return obj


# --------------------------------------------------------------- core registry

def incident_row():
    return N(Id=0, Kind=EStr(''), Response=EStr(''), Position=[0, 0, 0], Radius=0.0, StartAt=0,
             ExpiresAt=0, SoundRange=0.0, SoundSeconds=0, VisualRange=0.0, Severity=0,
             RadioFact=EStr(''), Faction=EStr(''), Anchor=None, Anchored=False, Responders=0,
             Reported=False)


def kind_row():
    return N(Kind=EStr(''), FactKind=EStr(''), Response=EStr(''), Radius=0.0, SoundRange=0.0,
             SoundSeconds=0, VisualRange=0.0, LifetimeSeconds=0, Severity=0, RadioFact=EStr(''))


POLICY_METHODS = ['HCAddKind', 'HCDefaults', 'HCFind', 'HCFindFact', 'HCRange', 'HCResponseKnown', 'HCKindValid', 'HCValid']


def policy(**overrides):
    env = base_env()
    env.update(HCWorldIncidentKind=kind_row)
    obj = bind(text(CORE), 'HCWorldIncidentPolicy', env, only=POLICY_METHODS, Version=1, MaxIncidents=32,
               SweepPerTick=4, MaxResponders=1, MergeMeters=5.0, Kinds=EArray())
    obj.HCDefaults()
    for key, value in overrides.items():
        setattr(obj, key, value)
    obj.valid = env['HCValid']
    return obj


def registry(now=1000, maxima=32, sweep=4, responders=1, world=None, budget=True, **extra):
    logs = []
    env = base_env(logs)
    pol = policy(MaxIncidents=maxima, SweepPerTick=sweep, MaxResponders=responders)
    calls = []
    world = world or N(NearestPlace=lambda position: EStr('place-a'),
                       AddFact=lambda kind, place, severity: calls.append((kind, place, severity)) or True)
    env.update(HCWorldIncident=incident_row, HCWorldModule=N(Get=lambda: world),
               HCWorldIncidentPolicy=N(HCGet=lambda: pol),
               HCWorkBudget=lambda: N(), GetGame=lambda: N(IsServer=lambda: True, GetTime=lambda: now * 1000),
               HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda consumer, cost: budget)),
               HCWorldIncidents=N(WORK_ID=28, HCNowSeconds=lambda: now), HCNowSeconds=lambda: now)
    env.update(extra)
    obj = bind(text(CORE), 'HCWorldIncidents', env,
               only=['HCAdd', 'HCFindSame', 'HCRetireAnchor', 'HCRetireId', 'HCCount', 'HCRowAt', 'HCById', 'HCPerceives',
                     'HCClaim', 'HCRelease', 'HCSweep', 'HCEvict', 'HCRadio', 'HCNoteFact', 'HCRemoveAt', 'HCGone'],
               m_Policy=pol, m_Rows=EArray(), m_NextId=1, m_Cursor=0, m_Running=True, m_Off=False, m_Refused=0,
               m_FullLogged=False)
    obj.logs, obj.facts, obj.pol, obj.world = logs, calls, pol, world
    return obj


def anchor(deleted=False):
    handle = N(deleted=deleted)
    handle.IsPendingDeletion = lambda: handle.deleted
    return handle


class PolicyBehavior(unittest.TestCase):
    def test_defaults_are_valid_and_named(self):
        pol = policy()
        self.assertTrue(pol.valid(pol))
        kinds = {row.Kind for row in pol.Kinds}
        for name in ('gas_static', 'gas_dynamic', 'gas_local', 'crash', 'crash_cold', 'scene', 'raid', 'horde'):
            self.assertIn(name, kinds)
        self.assertIsNone(pol.HCFind('not_a_kind'))
        self.assertEqual('scene', pol.HCFindFact('scene_started').Kind)
        self.assertIsNone(pol.HCFindFact('party_passed'), 'abstract ledger memory is not a physical incident')

    def test_invalid_policies_never_uncap_work(self):
        def invalid(**change):
            pol = policy(**change)
            return not pol.valid(pol)
        self.assertTrue(invalid(Version=2))
        self.assertTrue(invalid(MaxIncidents=0))
        self.assertTrue(invalid(MaxIncidents=65))
        self.assertTrue(invalid(SweepPerTick=0))
        self.assertTrue(invalid(SweepPerTick=17))
        self.assertTrue(invalid(MaxResponders=0))
        self.assertTrue(invalid(Kinds=EArray()))
        broken = policy()
        broken.Kinds[0].VisualRange = float('nan')
        self.assertFalse(broken.valid(broken))
        broken = policy()
        broken.Kinds[0].SoundRange = -1.0
        self.assertFalse(broken.valid(broken))
        broken = policy()
        broken.Kinds[0].Response = EStr('teleport')
        self.assertFalse(broken.valid(broken))
        broken = policy()
        broken.Kinds[1].Kind = broken.Kinds[0].Kind
        self.assertFalse(broken.valid(broken), 'duplicate kind rows')
        broken = policy()
        broken.Kinds[0].Severity = 4
        self.assertFalse(broken.valid(broken))
        broken = policy()
        broken.Kinds[0].RadioFact = broken.Kinds[3].FactKind or EStr('scene_started')
        self.assertFalse(broken.valid(broken), 'a relayed fact may not re-enter as a subscribed fact')


class RegistryBehavior(unittest.TestCase):
    def test_add_uses_row_defaults_and_expiry(self):
        reg = registry(now=1000)
        gas = reg.HCAdd('gas_dynamic', [100, 0, 100], 0.0, 0, None, 1000)
        self.assertGreater(gas, 0)
        row = reg.HCById(gas)
        self.assertEqual('gas_dynamic', row.Kind)
        self.assertEqual('avoid', row.Response)
        self.assertGreater(row.Radius, 0)
        permanent = reg.HCAdd('gas_static', [900, 0, 900], 80.0, 0, None, 1000)
        self.assertEqual(0, reg.HCById(permanent).ExpiresAt, 'static zones live until their entity is deleted')
        self.assertEqual(80.0, reg.HCById(permanent).Radius)
        timed = reg.HCAdd('crash', [10, 0, 10], 0.0, 500, None, 1000)
        self.assertEqual(1500, reg.HCById(timed).ExpiresAt)
        self.assertEqual(0, reg.HCAdd('not_a_kind', [0, 0, 0], 0.0, 0, None, 1000))
        self.assertEqual(1, reg.m_Refused)

    def test_same_anchor_or_same_place_never_duplicates(self):
        reg = registry()
        wreck = anchor()
        first = reg.HCAdd('crash', [10, 0, 10], 0.0, 0, wreck, 1000)
        self.assertEqual(first, reg.HCAdd('crash', [10, 0, 10], 0.0, 0, wreck, 1001))
        loose = reg.HCAdd('scene', [500, 0, 500], 0.0, 0, None, 1000)
        self.assertEqual(loose, reg.HCAdd('scene', [500.5, 0, 500], 0.0, 0, None, 1002))
        self.assertEqual(2, reg.HCCount())

    def test_ring_is_capped_evicts_oldest_transient_and_refuses_when_all_permanent(self):
        reg = registry(maxima=3)
        old = reg.HCAdd('crash', [0, 0, 0], 0.0, 100, None, 1000)
        mid = reg.HCAdd('crash', [50, 0, 0], 0.0, 300, None, 1000)
        fixed = reg.HCAdd('gas_static', [900, 0, 900], 80.0, 0, None, 1000)
        self.assertEqual(3, reg.HCCount())
        extra = reg.HCAdd('crash', [200, 0, 0], 0.0, 300, None, 1001)
        self.assertGreater(extra, 0)
        self.assertEqual(3, reg.HCCount())
        self.assertIsNone(reg.HCById(old), 'earliest expiry is evicted first')
        self.assertIsNotNone(reg.HCById(mid))
        self.assertIsNotNone(reg.HCById(fixed))
        full = registry(maxima=2)
        full.HCAdd('gas_static', [0, 0, 0], 80.0, 0, None, 1000)
        full.HCAdd('gas_static', [900, 0, 0], 80.0, 0, None, 1000)
        self.assertEqual(0, full.HCAdd('crash', [5, 0, 5], 0.0, 100, None, 1000), 'permanent rows are never evicted')
        self.assertEqual(2, full.HCCount())

    def test_sweep_is_bounded_and_retires_expired_or_lost_anchors(self):
        reg = registry(sweep=2)
        for index in range(5):
            reg.HCAdd('crash', [index * 100, 0, 0], 0.0, 10, None, 1000)
        reg.HCSweep(1020)
        self.assertEqual(3, reg.HCCount(), 'at most SweepPerTick rows are examined per call')
        reg.HCSweep(1020)
        reg.HCSweep(1020)
        self.assertEqual(0, reg.HCCount())
        wreck = anchor()
        reg = registry()
        reg.HCAdd('crash', [0, 0, 0], 0.0, 0, wreck, 1000)
        reg.HCSweep(1001)
        self.assertEqual(1, reg.HCCount())
        wreck.deleted = True
        reg.HCSweep(1002)
        self.assertEqual(0, reg.HCCount(), 'a deleted anchor retires its incident')

    def test_retire_by_anchor_and_id(self):
        reg = registry()
        wreck = anchor()
        reg.HCAdd('crash', [0, 0, 0], 0.0, 0, wreck, 1000)
        other = reg.HCAdd('scene', [900, 0, 0], 0.0, 0, None, 1000)
        reg.HCRetireAnchor(wreck)
        self.assertEqual(1, reg.HCCount())
        reg.HCRetireId(other)
        self.assertEqual(0, reg.HCCount())
        reg.HCRetireAnchor(None)

    def test_perception_needs_a_member_in_sound_or_visual_range(self):
        reg = registry()
        gas = reg.HCById(reg.HCAdd('gas_static', [0, 0, 0], 120.0, 0, None, 1000))
        edge = 120.0 + gas.VisualRange
        self.assertTrue(reg.HCPerceives(gas, [edge - 1, 0, 0], 1000))
        self.assertFalse(reg.HCPerceives(gas, [edge + 1, 0, 0], 1000), 'silent gas is seen, never heard')
        crash = reg.HCById(reg.HCAdd('crash', [5000, 0, 5000], 0.0, 0, None, 1000))
        near_sound = [5000 + crash.SoundRange - 1, 0, 5000]
        self.assertTrue(reg.HCPerceives(crash, near_sound, 1000 + crash.SoundSeconds))
        self.assertFalse(reg.HCPerceives(crash, near_sound, 1001 + crash.SoundSeconds), 'sound fades after its window')
        self.assertTrue(reg.HCPerceives(crash, [5000 + crash.VisualRange - 1, 0, 5000], 5000),
                        'smoke stays visible after the sound has faded')
        self.assertFalse(reg.HCPerceives(crash, [5000 + crash.SoundRange + 1, 0, 5000], 1000))
        cold = reg.HCById(reg.HCAdd('crash_cold', [9000, 0, 9000], 0.0, 0, None, 1000))
        self.assertLess(cold.VisualRange, crash.VisualRange, 'a wreck that is not smoking is seen from less far')

    def test_responder_claims_are_bounded_per_incident(self):
        reg = registry(responders=1)
        row = reg.HCById(reg.HCAdd('crash', [0, 0, 0], 0.0, 0, None, 1000))
        self.assertTrue(reg.HCClaim(row))
        self.assertFalse(reg.HCClaim(row), 'MaxResponders caps simultaneous investigators')
        reg.HCRelease(row.Id)
        self.assertTrue(reg.HCClaim(row))
        reg.HCRelease(row.Id)
        reg.HCRelease(row.Id)
        self.assertEqual(0, row.Responders)

    def test_ledger_facts_publish_only_subscribed_physical_kinds(self):
        reg = registry()
        self.assertEqual(0, reg.HCNoteFact('party_passed', [0, 0, 0], 0, EStr('')))
        found = reg.HCNoteFact('scene_started', [700, 0, 700], 1, EStr('locals'))
        self.assertGreater(found, 0)
        self.assertEqual('scene', reg.HCById(found).Kind)
        self.assertEqual(1, reg.HCById(found).Severity)
        self.assertEqual('locals', reg.HCById(found).Faction, 'the holdout faction rides on the incident for reinforcement')
        again = reg.HCNoteFact('scene_started', [700.5, 0, 700], 2, EStr(''))
        self.assertEqual(found, again, 'the same scene is one incident')
        self.assertEqual(2, reg.HCById(found).Severity, 'a worse report raises severity')
        self.assertEqual('locals', reg.HCById(found).Faction)
        off = registry()
        off.m_Off = True
        self.assertEqual(0, off.HCNoteFact('scene_started', [1, 0, 1], 1, EStr('')), 'operator opt-out publishes nothing')

    def test_radio_relay_is_once_per_incident_and_needs_a_known_place(self):
        reg = registry()
        zone = reg.HCAdd('gas_dynamic', [100, 0, 100], 120.0, 600, None, 1000)
        self.assertEqual([('DANGER', 'place-a', reg.HCById(zone).Severity)], reg.facts)
        reg.HCAdd('gas_dynamic', [100, 0, 100], 120.0, 600, None, 1001)
        self.assertEqual(1, len(reg.facts), 're-publication is not relayed again')
        lost = registry(world=N(NearestPlace=lambda position: EStr(''), AddFact=lambda *args: self.fail('no place')))
        self.assertGreater(lost.HCAdd('gas_dynamic', [100, 0, 100], 120.0, 600, None, 1000), 0)
        absent = registry()
        absent.world = None
        silent = registry(HCWorldModule=N(Get=lambda: None))
        self.assertGreater(silent.HCAdd('crash', [5, 0, 5], 0.0, 0, None, 1000), 0)
        self.assertFalse(any('radio' in line and 'AI' in line for line in reg.logs))


def module(marker=False, server=True, pol=True, line_sink=None):
    logs = [] if line_sink is None else line_sink
    env = base_env(logs)
    published = []
    status = N(HCPublish=lambda state, reason: published.append((state, reason)))

    def derive(target, started, refusal, fault, ready):
        if started:
            target.HCPublish('ready', ready)
        elif refusal != '':
            target.HCPublish('refused', refusal)
        else:
            target.HCPublish('off', 'not_started_or_disabled')

    env.update(FileExist=lambda path: marker and path.endswith('acceptance/world_incidents.disable'),
               GetGame=lambda: N(IsServer=lambda: server, GetTime=lambda: 5000),
               HCWorldIncidentPolicy=N(HCGet=lambda: policy() if pol else None),
               HCV2Admission=N(Line=lambda feature, preference, gate, qualified:
                               'ADMIT ' + feature + ' pref=' + str(preference) + ' gate=' + gate),
               HCModuleReadiness=N(HCDerive=derive))
    owner = bind(text(CORE), 'HCWorldIncidents', env, only=['HCStart', 'HCStatus'],
                 m_Policy=None, m_Running=False, m_Off=False, m_Refusal=EStr(''), m_Status=status)
    owner.logs, owner.published = logs, published
    return owner


class ModuleBehavior(unittest.TestCase):
    def test_default_on_admission_line_and_honest_readiness(self):
        owner = module()
        owner.HCStart()
        self.assertTrue(owner.m_Running)
        self.assertTrue(any('ADMIT world_incidents pref=True' in line and 'runtime=PENDING' in line for line in owner.logs))
        owner.HCStatus()
        self.assertEqual('ready', owner.published[-1][0])
        self.assertTrue(any('radio_relay=player_only' in line for line in owner.logs),
                        'the missing AI radio receiver is named once, never hidden')

    def test_operator_opt_out_policy_fault_and_non_server_never_report_ready(self):
        off = module(marker=True)
        off.HCStart()
        self.assertFalse(off.m_Running)
        off.HCStatus()
        self.assertEqual('off', off.published[-1][0])
        self.assertTrue(any('pref=False' in line for line in off.logs))
        bad = module(pol=False)
        bad.HCStart()
        bad.HCStatus()
        self.assertEqual(('refused', 'incident_policy_invalid'), bad.published[-1])
        remote = module(server=False)
        remote.HCStart()
        remote.HCStatus()
        self.assertEqual('refused', remote.published[-1][0])

    def test_module_wiring_is_the_shared_framework(self):
        source = text(CORE)
        self.assertIn('modded class HCModuleRegistry', source)
        self.assertIn('Register(HCWorldIncidents.HCGet())', source)
        self.assertIn('override HCOperationalStatus HCGetOperationalStatus()', source)
        self.assertIn('HCModuleReadiness.HCDerive(', source)
        self.assertIn('acceptance/world_incidents.disable', source)


class TickBehavior(unittest.TestCase):
    def test_tick_sweeps_only_with_budget(self):
        denied = registry(budget=False)
        denied.HCAdd('crash', [0, 0, 0], 0.0, 1, None, 1000)
        self.assertEqual(1, denied.HCCount())
        source = text(CORE)
        match = re.search(r'override void OnTick\(float deltaTime\)\s*\{', source)
        self.assertIsNotNone(match, 'OnTick must exist')
        body = source[match.end():source.index('override void OnStop')]
        self.assertIn('HCTakeFor(HCWorldIncidents.WORK_ID', body, 'shared tick budget, qualified static const')
        self.assertIn('HCSweep', body)


# --------------------------------------------------------------- native sources

def sources(server=True, order=None):
    order = [] if order is None else order
    published = []
    env = base_env()
    env.update(GetGame=lambda: N(IsServer=lambda: server),
               HCWorldIncidents=N(HCPublish=lambda kind, pos, radius, life, handle: published.append((kind, pos, radius, life)) or 1,
                                  HCRetire=lambda handle: order.append('retire')),
               ContaminatedArea_Local=N(Cast=lambda area: area if area.family == 'local' else None),
               ContaminatedArea_Static=N(Cast=lambda area: area if area.family == 'static' else None),
               ContaminatedArea_DynamicBase=N(Cast=lambda area: area if area.family in ('local', 'dynamic') else None))
    obj = bind(text(SOURCES), 'HCIncidentSources', env, only=['HCZone', 'HCCrashKind', 'HCCrash'])
    obj.published, obj.order = published, order
    return obj


def zone(family, remaining=0.0):
    return N(family=family, m_Position=[10, 0, 20], m_Radius=120.0, GetRemainingTime=lambda: remaining)


class SourceBehavior(unittest.TestCase):
    def test_static_dynamic_and_local_gas_use_their_real_lifecycle(self):
        src = sources()
        src.HCZone(zone('static'))
        src.HCZone(zone('dynamic', 600.9))
        src.HCZone(zone('local', 360.0))
        self.assertEqual(('gas_static', [10, 0, 20], 120.0, 0), src.published[0])
        self.assertEqual(('gas_dynamic', [10, 0, 20], 120.0, 600), src.published[1])
        self.assertEqual(('gas_local', [10, 0, 20], 120.0, 360), src.published[2])

    def test_client_and_null_publish_nothing(self):
        src = sources(server=False)
        src.HCZone(zone('static'))
        src.HCZone(None)
        self.assertEqual([], src.published)

    def test_crash_kind_separates_cold_wreck_and_never_creates_a_crash(self):
        src = sources()
        smoking = N(IsKindOf=lambda name: False, GetPosition=lambda: [5, 0, 6])
        cold = N(IsKindOf=lambda name: name == 'Wreck_Mi8', GetPosition=lambda: [7, 0, 8])
        src.HCCrash(smoking)
        src.HCCrash(cold)
        self.assertEqual(('crash', [5, 0, 6], 0.0, 0), src.published[0])
        self.assertEqual('crash_cold', src.published[1][0])
        self.assertNotIn('SpawnDE', text(SOURCES), 'HC never creates a native crash (developer-only API)')

    def test_hooks_call_super_first(self):
        source = text(SOURCES)
        for cls, method, after in (('ContaminatedArea_Base', 'InitZoneServer', 'HCIncidentSources.HCZone'),
                                   ('ContaminatedArea_Base', 'EEDelete', 'HCWorldIncidents.HCRetire'),
                                   ('CrashBase', 'EEOnCECreate', 'HCIncidentSources.HCCrash'),
                                   ('CrashBase', 'EEDelete', 'HCWorldIncidents.HCRetire'),
                                   ('HCWorldModule', 'AddFact', 'HCWorldIncidents.HCPublishFact')):
            declared = re.search(r'modded class ' + cls + r'\b.*?\n\{(.*?)\n\}', source, re.S)
            self.assertIsNotNone(declared, cls)
            hook = re.search(r'override \w+ ' + method + r'\([^)]*\)\s*\{(.*?)\n    \}', declared[1], re.S)
            self.assertIsNotNone(hook, cls + '.' + method)
            self.assertLess(hook[1].index('super.' + method), hook[1].index(after), cls + '.' + method)


# --------------------------------------------------------------- group response

CONSTS = N(ONCE='ONCE', HALT='HALT', PATROL='PATROL')


def member(position, masked=False, filtered=True, alive=True):
    obj = N(position=list(position), alive=alive, masked=masked, filtered=filtered)
    obj.GetPosition = lambda: obj.position
    obj.IsAlive = lambda: obj.alive
    return obj


def protection(kind, slot, man, consider_filter):
    """Synthetic PluginTransmissionAgents.GetProtectionLevelEx: a worn mask with a valid filter protects."""
    return 0.9 if man.masked and man.filtered else 0.0


def group(positions, route=(), masked=None, combat=False, faction='fa'):
    masked = masked or [False] * len(positions)
    members = [member(pos, flag) for pos, flag in zip(positions, masked)]
    state = N(route=EArray([list(p) for p in route]), behaviour='PATROL', combat=combat, members=members, faction=faction)
    state.GetWaypoints = lambda: state.route
    state.ClearWaypoints = lambda: state.route.clear()
    state.AddWaypoint = lambda point: state.route.append(list(point))
    state.SetWaypointBehaviour = lambda value: setattr(state, 'behaviour', value)
    state.GetWaypointBehaviour = lambda: state.behaviour
    state.IsInCombat = lambda: state.combat
    state.Count = lambda: len(state.members)
    state.GetMember = lambda index: state.members[index]
    state.GetFaction = lambda: state.faction
    return state


def lease_row():
    return N(Group=None, IncidentId=0, Response=EStr(''), Phase=EStr(''), Target=[0, 0, 0], Placed=0, Until=0,
             Deadline=0, Saved=EArray(), Behavior='PATROL')


def response_row():
    return N(Response=EStr(''), StandoffMeters=0.0, AllyStandoffMeters=0.0, HoldSeconds=0, InspectMeters=0.0,
             InspectSeconds=0, ApproachSeconds=0)


RANGE = N(HCRange=lambda value, low, high: value == value and low <= value <= high)
POLICY_FIELDS = dict(Version=1, MaxLeases=2, StepsPerTick=2, LeashMeters=900.0, CooldownSeconds=300, MaxCooldowns=8,
                     ArriveMeters=15.0, ProtectionLevel=0.5, MaxRoutePoints=32)


def response_policy(**change):
    env = base_env()
    env.update(HCXAIIncidentRow=response_row, HCWorldIncidentPolicy=RANGE)
    fields = dict(POLICY_FIELDS, **change)
    rows = fields.pop('Rows', EArray())
    obj = bind(text(RESPONSE), 'HCXAIIncidentPolicy', env, only=['HCAddRow', 'HCDefaults', 'HCFindRow', 'HCRowValid', 'HCValid'],
               Rows=rows, **fields)
    if 'Rows' not in change:
        obj.HCDefaults()
    obj.valid = env['HCValid']
    return obj


RESPONDER_METHODS = ['HCAccept', 'HCLeaseFor', 'HCCooling', 'HCCool', 'HCBest', 'HCEligible', 'HCPerceived', 'HCAlive',
                     'HCProtected', 'HCAllProtected', 'HCMargin', 'HCAvoidMode', 'HCKeep', 'HCLegHits', 'HCStartLease',
                     'HCBorrow', 'HCWalk', 'HCVet', 'HCStandoff', 'HCRadial', 'HCInside', 'HCUsable', 'HCStep',
                     'HCAdvance', 'HCInspect', 'HCArrived', 'HCMine', 'HCFinish', 'HCRestore', 'HCLead', 'HCFlat']


def responder(now=1000, rows=(), max_leases=2, sea=False, world_registry=None, budget=True, **extra):
    logs = []
    env = base_env(logs)
    reg = world_registry or registry(now=now)
    for kind, position, radius, life in rows:
        reg.HCAdd(kind, position, radius, life, None, now)
    env.update(eAIGroup=N(), eAIWaypointBehavior=CONSTS, DEF_CHEMICAL=2, InventorySlots=N(MASK=20),
               PluginTransmissionAgents=N(GetProtectionLevelEx=protection),
               GetGame=lambda: N(IsServer=lambda: True, GetTime=lambda: now * 1000,
                                 SurfaceY=lambda x, z: 0.0, SurfaceIsSea=lambda x, z: sea, SurfaceIsPond=lambda x, z: False),
               HCWorldIncidents=N(HCGet=lambda: reg, WORK_ID=28),
               HCXFactions=N(Id=lambda faction: faction, HCWorldId=lambda value: value),
               HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda consumer, cost: budget)),
               HCXAIIncidentResponse=N(WORK_ID=29),
               HCXAIIncidentLease=lease_row,
               HCXAIIncidentCooldown=lambda: N(Group=None, Until=0))
    env.update(extra)
    pol = response_policy(MaxLeases=max_leases)
    obj = bind(text(RESPONSE), 'HCXAIIncidentResponse', env, only=RESPONDER_METHODS,
               m_Policy=pol, m_Leases=EArray(), m_Cooldowns=EArray(), m_Cursor=0, m_Running=True)
    obj.logs, obj.reg, obj.pol = logs, reg, pol
    obj.HCNote = lambda what, lease: logs.append(what)
    return obj


class ResponseBehavior(unittest.TestCase):
    def test_gas_inside_leaves_by_the_shortest_radial_path_to_a_point_outside(self):
        run = responder(rows=[('gas_static', [0, 0, 0], 100.0, 0)])
        crew = group([[50, 0, 0], [55, 0, 5]], route=[[60, 0, 0], [400, 0, 0]])
        self.assertTrue(run.HCAccept(crew, [300, 0, 0], 1000))
        lease = run.m_Leases[0]
        self.assertEqual('move', lease.Phase)
        self.assertEqual('ONCE', crew.behaviour)
        self.assertEqual(1, len(crew.route))
        target = crew.route[0]
        self.assertGreaterEqual(math.sqrt(dist_sq(target, [0, 0, 0])), 100 + 30 - 0.01)
        self.assertGreater(target[0], 100, 'exits through the side the group is already on')
        self.assertEqual([[60, 0, 0], [400, 0, 0]], [list(p) for p in lease.Saved], 'the patrol is saved for restore')

    def test_gas_on_the_route_is_vetted_without_moving_the_group(self):
        run = responder(rows=[('gas_static', [0, 0, 0], 100.0, 0)])
        crew = group([[180, 0, 0]], route=[[40, 0, 0], [400, 0, 0]])
        self.assertTrue(run.HCAccept(crew, [300, 0, 0], 1000))
        self.assertEqual('vet', run.m_Leases[0].Phase)
        self.assertEqual([[400, 0, 0]], [list(p) for p in crew.route], 'only waypoints outside radius+margin remain')
        self.assertEqual('PATROL', crew.behaviour)

    def test_protected_groups_ignore_gas_and_one_bare_face_does_not(self):
        run = responder(rows=[('gas_static', [0, 0, 0], 100.0, 0)])
        protected = group([[50, 0, 0], [52, 0, 0]], route=[[400, 0, 0]], masked=[True, True])
        self.assertFalse(run.HCAccept(protected, [300, 0, 0], 1000))
        self.assertEqual(0, len(run.m_Leases))
        mixed = group([[50, 0, 0], [52, 0, 0]], route=[[400, 0, 0]], masked=[True, False])
        self.assertTrue(run.HCAccept(mixed, [300, 0, 0], 1000))
        spent = responder(rows=[('gas_static', [0, 0, 0], 100.0, 0)])
        spent_crew = group([[50, 0, 0]], route=[[400, 0, 0]], masked=[True])
        spent_crew.members[0].filtered = False
        self.assertTrue(spent.HCAccept(spent_crew, [300, 0, 0], 1000), 'a mask without a valid filter is not protection')

    def test_crash_standoff_watch_inspect_then_restore_and_cooldown(self):
        run = responder(rows=[('crash', [1000, 0, 1000], 0.0, 0)])
        crew = group([[1400, 0, 1000]], route=[[1500, 0, 1000]])
        self.assertTrue(run.HCAccept(crew, [1450, 0, 1000], 1000))
        lease = run.m_Leases[0]
        stand = crew.route[0]
        reach = math.sqrt(dist_sq(stand, [1000, 0, 1000]))
        self.assertAlmostEqual(run.pol.HCFindRow('investigate').StandoffMeters, reach, delta=0.5)
        self.assertGreater(reach, run.pol.HCFindRow('investigate').InspectMeters, 'never the wreck position')
        self.assertEqual(1, run.reg.HCById(lease.IncidentId).Responders)
        crew.members[0].position = [stand[0], 0, stand[2]]
        run.HCAdvance(lease, 1030)
        self.assertEqual('hold', lease.Phase)
        run.HCAdvance(lease, 1031)
        self.assertEqual('hold', lease.Phase)
        run.HCAdvance(lease, 1031 + run.pol.HCFindRow('investigate').HoldSeconds)
        self.assertEqual('inspect', lease.Phase)
        look = crew.route[0]
        self.assertAlmostEqual(run.pol.HCFindRow('investigate').InspectMeters, math.sqrt(dist_sq(look, [1000, 0, 1000])), delta=0.5)
        self.assertGreater(run.pol.HCFindRow('investigate').InspectMeters, 0)
        run.HCAdvance(lease, 5000)
        self.assertEqual(0, len(run.m_Leases))
        self.assertEqual([[1500, 0, 1000]], [list(p) for p in crew.route], 'previous patrol restored')
        self.assertEqual('PATROL', crew.behaviour)
        self.assertEqual(0, run.reg.HCById(lease.IncidentId).Responders)
        self.assertFalse(run.HCAccept(crew, [1450, 0, 1000], 5001), 'cooldown holds the group back')
        self.assertTrue(run.HCAccept(crew, [1450, 0, 1000], 5000 + run.pol.CooldownSeconds + 1))

    def test_incident_must_be_perceived_by_a_member_and_inside_the_home_leash(self):
        run = responder(rows=[('crash', [1000, 0, 1000], 0.0, 0)], now=3000)
        deaf = group([[9000, 0, 9000]], route=[[9100, 0, 9000]])
        self.assertFalse(run.HCAccept(deaf, [9000, 0, 9000], 3000), 'no member can see or hear it')
        far_home = group([[1400, 0, 1000]], route=[[1500, 0, 1000]])
        self.assertFalse(run.HCAccept(far_home, [9000, 0, 9000], 3000), 'outside the home leash')
        self.assertEqual(0, len(run.m_Leases))

    def test_lease_cap_and_combat_and_dead_groups_release_cleanly(self):
        run = responder(rows=[('crash', [1000, 0, 1000], 0.0, 0), ('crash', [1100, 0, 1000], 0.0, 0)], max_leases=1)
        first = group([[1400, 0, 1000]], route=[[1500, 0, 1000]])
        second = group([[1400, 0, 1100]], route=[[1500, 0, 1100]])
        self.assertTrue(run.HCAccept(first, [1400, 0, 1000], 1000))
        self.assertFalse(run.HCAccept(second, [1400, 0, 1100], 1000), 'MaxLeases is a hard cap')
        first.combat = True
        run.HCAdvance(run.m_Leases[0], 1001)
        self.assertEqual(0, len(run.m_Leases), 'combat returns control to the native controller')
        self.assertEqual([[1500, 0, 1000]], [list(p) for p in first.route])
        third = group([[1400, 0, 1000]], route=[[1500, 0, 1000]])
        run.m_Cooldowns.clear()
        self.assertTrue(run.HCAccept(third, [1400, 0, 1000], 1002))
        third.members[0].alive = False
        run.HCAdvance(run.m_Leases[0], 1003)
        self.assertEqual(0, len(run.m_Leases))

    def test_retired_incident_ends_the_lease_and_restores_the_route(self):
        run = responder(rows=[('gas_dynamic', [0, 0, 0], 100.0, 600)])
        crew = group([[50, 0, 0]], route=[[400, 0, 0]])
        self.assertTrue(run.HCAccept(crew, [300, 0, 0], 1000))
        lease = run.m_Leases[0]
        run.reg.HCRetireId(lease.IncidentId)
        run.HCAdvance(lease, 1010)
        self.assertEqual(0, len(run.m_Leases))
        self.assertEqual([[400, 0, 0]], [list(p) for p in crew.route])

    def test_horde_makes_a_group_withdraw_away_from_it(self):
        run = responder(rows=[('horde', [0, 0, 0], 80.0, 0)])
        crew = group([[150, 0, 0]], route=[[40, 0, 0]])
        self.assertTrue(run.HCAccept(crew, [150, 0, 0], 1000))
        target = crew.route[0]
        self.assertGreater(math.sqrt(dist_sq(target, [0, 0, 0])), 150, 'moves further from the horde, not into it')

    def test_allied_faction_reinforces_closer_than_a_neutral_watcher(self):
        run = responder(rows=[('raid', [1000, 0, 1000], 0.0, 0)])
        run.reg.HCById(1).Faction = EStr('fa')
        ally = group([[1400, 0, 1000]], route=[[1500, 0, 1000]], faction='fa')
        self.assertTrue(run.HCAccept(ally, [1400, 0, 1000], 1000))
        ally_reach = math.sqrt(dist_sq(ally.route[0], [1000, 0, 1000]))
        neutral_run = responder(rows=[('raid', [1000, 0, 1000], 0.0, 0)])
        outsider = group([[1400, 0, 1000]], route=[[1500, 0, 1000]], faction='fb')
        self.assertTrue(neutral_run.HCAccept(outsider, [1400, 0, 1000], 1000))
        self.assertLess(ally_reach, math.sqrt(dist_sq(outsider.route[0], [1000, 0, 1000])))

    def test_unusable_target_refuses_without_touching_the_route(self):
        run = responder(rows=[('crash', [1000, 0, 1000], 0.0, 0)], sea=True)
        crew = group([[1400, 0, 1000]], route=[[1500, 0, 1000]])
        self.assertFalse(run.HCAccept(crew, [1400, 0, 1000], 1000))
        self.assertEqual([[1500, 0, 1000]], [list(p) for p in crew.route])
        self.assertEqual(0, run.reg.HCById(1).Responders, 'a refused offer releases its claim')

    def test_one_incident_claim_per_responder_cap(self):
        run = responder(rows=[('crash', [1000, 0, 1000], 0.0, 0)], max_leases=3)
        one = group([[1400, 0, 1000]], route=[[1500, 0, 1000]])
        two = group([[1400, 0, 1100]], route=[[1500, 0, 1100]])
        self.assertTrue(run.HCAccept(one, [1400, 0, 1000], 1000))
        self.assertFalse(run.HCAccept(two, [1400, 0, 1100], 1000), 'registry MaxResponders=1')


class ResponsePolicyAndModule(unittest.TestCase):
    def test_policy_defaults_valid_and_bad_rows_refused(self):
        good = response_policy()
        self.assertTrue(good.valid(good))
        for response in ('avoid', 'investigate', 'react', 'flee'):
            self.assertIsNotNone(good.HCFindRow(response))
        self.assertGreater(good.HCFindRow('investigate').InspectMeters, 0)
        self.assertLess(good.HCFindRow('react').AllyStandoffMeters, good.HCFindRow('react').StandoffMeters)
        for change in (dict(Version=2), dict(MaxLeases=0), dict(MaxLeases=17), dict(StepsPerTick=0), dict(StepsPerTick=9),
                       dict(LeashMeters=float('nan')), dict(LeashMeters=10.0), dict(CooldownSeconds=-1), dict(MaxCooldowns=0),
                       dict(ArriveMeters=0.0), dict(ProtectionLevel=1.5), dict(MaxRoutePoints=0), dict(Rows=EArray())):
            bad = response_policy(**change)
            self.assertFalse(bad.valid(bad), str(change))
        bad = response_policy()
        bad.Rows[0].StandoffMeters = -5.0
        self.assertFalse(bad.valid(bad))
        bad = response_policy()
        bad.Rows[0].ApproachSeconds = 5
        self.assertFalse(bad.valid(bad), 'an approach window under 30 s cannot finish a walk')
        bad = response_policy()
        bad.Rows[1].Response = bad.Rows[0].Response
        self.assertFalse(bad.valid(bad), 'duplicate response rows')
        bad = response_policy()
        bad.Rows[0].Response = EStr('teleport')
        self.assertFalse(bad.valid(bad), 'unknown response')

    def test_offer_refuses_when_the_module_is_not_running(self):
        source = text(RESPONSE)
        self.assertIn('static bool HCOffer(eAIGroup group, vector home)', source)
        match = re.search(r'static bool HCOffer\(eAIGroup group, vector home\)\s*\{(.*?)\n    \}', source, re.S)
        self.assertIn('s_Instance', match[1])
        self.assertIn('m_Running', match[1])
        self.assertIn('return false', match[1])

    def test_module_uses_shared_framework_and_marker_opt_out(self):
        source = text(RESPONSE)
        self.assertIn('HCTakeFor(HCXAIIncidentResponse.WORK_ID', source)
        self.assertIn('acceptance/incident_response.disable', source)
        self.assertIn('HCV2Admission.Line(', source)
        self.assertIn('HCModuleReadiness.HCDerive(', source)
        self.assertIn('runtime=PENDING', source)
        self.assertIn('modded class HCModuleRegistry', source)
        owners = [m.start() for m in re.finditer(r'\.ClearWaypoints\(\)', source)]
        self.assertEqual(3, len(owners), 'the live waypoint array is only cleared in the walk, vet and restore steps')
        for forbidden in ('CreateObject', 'SpawnEntity', 'SetPosition(', 'OverrideTargetPosition'):
            code = re.sub(r'//[^\n]*', '', source)
            self.assertNotIn(forbidden, code, 'no spawn, teleport or target override: ' + forbidden)


class Hygiene(unittest.TestCase):
    def test_no_forbidden_names_or_home_paths(self):
        for path in (CORE, SOURCES, RESPONSE):
            source = path.read_text()
            for banned in ('snafu', '2646817942', '2291785308', '2792982069', '/home/'):
                self.assertNotIn(banned, source.lower() if banned.isalpha() else source, path.name)


if __name__ == '__main__':
    unittest.main()
