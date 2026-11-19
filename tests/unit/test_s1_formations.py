"""s1-formations: context-driven formation and movement style for HC AI groups.

Synthetic fixtures only. The authored Enforce bodies are executed through the
repository's offline translator with explicit stand-ins for the engine and
Expansion ports. Nothing here establishes DayZ or Expansion behaviour.
"""
import json
import math
import re
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr, translate

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIFormations.c'
SHIPPED = ROOT / 'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-formations.json'


class HStr(EStr):
    """Synthetic string.Hash (EnString.c:223 is a native noncryptographic hash)."""
    def Hash(self):
        return zlib.crc32(self.encode()) - 2 ** 31


def class_consts(text, class_name):
    start = re.search(r'\bclass ' + class_name + r'\b[^{]*\{', text)
    assert start, 'missing authored class ' + class_name
    consts = {}
    for kind, name, value in re.findall(
            r'^    static const (int|float|string) (\w+) = ([^;]+);', text[start.end():], re.M):
        if kind == 'string':
            consts[name] = EStr(json.loads(value))
        elif kind == 'int':
            consts[name] = int(value)
        else:
            consts[name] = float(value)
    return consts


def prepared_source():
    text = SOURCE.read_text()
    text = re.sub(r'([\w.\[\]()]+)\.ToString\(\)', r'str(\1)', text)
    text = text.replace('protected ', '').replace('override ', '').replace('static const', 'static_const')
    text = re.sub(r'(?:array|map)<[^>;]*>', 'HCArray', text)
    text = re.sub(r'\b(?:eAIGroup|eAIBase|DayZPlayerImplement) (\w+)', r'HCActor \1', text)
    text = text.replace('static_const', 'static const')
    return text


def shipped_config(**changes):
    raw = json.loads(SHIPPED.read_text())
    raw['RoadSurfaces'] = EArray(EStr(item) for item in raw['RoadSurfaces'])
    raw.update(changes)
    return N(**raw)


def math_env():
    return N(Floor=math.floor, Acos=math.acos, Sqrt=math.sqrt, Sin=math.sin, Cos=math.cos,
             AbsFloat=abs, Min=min, Max=max, DEG2RAD=math.pi / 180.0, RAD2DEG=180.0 / math.pi,
             Clamp=lambda v, lo, hi: max(lo, min(hi, v)))


def rules():
    text = prepared_source()
    env = dict(Math=math_env(), EArray=EArray, HCArray=EArray)
    env['HCXAIFormationRules'] = N(**class_consts(text, 'HCXAIFormationRules'))
    translate(text, 'HCXAIFormationRules', env)
    consts = class_consts(text, 'HCXAIFormationRules')
    api = N(**consts)
    for name in ('SeedOf', 'Mix', 'Unit', 'SignedUnit', 'Context', 'Spacing', 'BaseX', 'BaseZ',
                 'SlotX', 'SlotZ', 'JogPercent', 'IsJog', 'TurnDegrees', 'IsJunction',
                 'PauseRoll', 'PauseSeconds', 'LookDegrees', 'IsRoadSurface', 'ConfigProblem'):
        setattr(api, name, env[name])
    return api


R = None


def api():
    global R
    if R is None:
        R = rules()
    return R


class FormationChoice(unittest.TestCase):
    def test_context_selects_the_human_formation_for_the_situation(self):
        r, cfg = api(), shipped_config()
        near, town = cfg.NearBuildingRadius, cfg.TownRadius
        table = [
            ('open ground is a wedge', (False, False, False, -1.0), r.MODE_WEDGE),
            ('a road is a column', (False, False, True, -1.0), r.MODE_COLUMN),
            ('a town is staggered', (False, False, False, town - 1.0), r.MODE_STAGGER),
            ('beside a building is tight', (False, False, False, near - 1.0), r.MODE_TIGHT),
            ('under fire is spread', (True, False, False, -1.0), r.MODE_SPREAD),
            ('after contact is a regroup', (False, True, False, -1.0), r.MODE_REGROUP),
            ('fire beats a road', (True, False, True, 3.0), r.MODE_SPREAD),
            ('regroup beats a road', (False, True, True, 3.0), r.MODE_REGROUP),
            ('a road beats a town', (False, False, True, near - 1.0), r.MODE_COLUMN),
            ('far from a house is open', (False, False, False, town + 50.0), r.MODE_WEDGE),
        ]
        for label, (combat, regroup, road, house), expected in table:
            with self.subTest(label):
                self.assertEqual(expected, r.Context(combat, regroup, road, house, near, town))

    def test_formation_shapes_are_humanlike_and_ordered_by_context(self):
        r, cfg = api(), shipped_config(SpacingJitter=0.0)
        self.assertEqual((0.0, 0.0), (r.SlotX(cfg, r.MODE_WEDGE, 0, 7), r.SlotZ(cfg, r.MODE_WEDGE, 0, 7)))
        column = [r.SlotZ(cfg, r.MODE_COLUMN, i, 7) for i in range(1, 6)]
        self.assertEqual(sorted(column, reverse=True), column, 'a column trails back one rank per member')
        self.assertTrue(all(abs(r.SlotX(cfg, r.MODE_COLUMN, i, 7)) <= cfg.ColumnLane for i in range(1, 6)))
        wedge_x = [abs(r.SlotX(cfg, r.MODE_WEDGE, i, 7)) for i in (1, 3, 5)]
        self.assertEqual(sorted(wedge_x), wedge_x, 'a wedge widens with each rank')
        self.assertLess(r.SlotX(cfg, r.MODE_WEDGE, 1, 7) * r.SlotX(cfg, r.MODE_WEDGE, 2, 7), 0, 'wedge wings oppose')
        self.assertLess(r.Spacing(cfg, r.MODE_TIGHT), r.Spacing(cfg, r.MODE_STAGGER))
        self.assertLess(r.Spacing(cfg, r.MODE_STAGGER), r.Spacing(cfg, r.MODE_SPREAD))
        self.assertLess(r.Spacing(cfg, r.MODE_REGROUP), r.Spacing(cfg, r.MODE_WEDGE))
        spread = max(abs(r.SlotX(cfg, r.MODE_SPREAD, i, 7)) for i in range(1, 6))
        tight = max(abs(r.SlotX(cfg, r.MODE_TIGHT, i, 7)) for i in range(1, 6))
        self.assertGreater(spread, 2 * tight, 'under fire the group fans out wider than beside a building')

    def test_zero_jitter_is_exactly_the_base_shape(self):
        r, cfg = api(), shipped_config(SpacingJitter=0.0)
        for mode in range(6):
            for index in range(0, 6):
                self.assertEqual(r.BaseX(cfg, mode, index), r.SlotX(cfg, mode, index, 12345))
                self.assertEqual(r.BaseZ(cfg, mode, index), r.SlotZ(cfg, mode, index, 12345))


class SeededJitter(unittest.TestCase):
    def test_jitter_is_bounded_deterministic_and_varies_by_seed(self):
        r, cfg = api(), shipped_config()
        values = set()
        for seed in range(1, 300):
            for mode in range(6):
                spacing = r.Spacing(cfg, mode)
                for index in range(1, 9):
                    x = r.SlotX(cfg, mode, index, seed)
                    z = r.SlotZ(cfg, mode, index, seed)
                    bound = cfg.SpacingJitter * spacing + 1e-6
                    self.assertLessEqual(abs(x - r.BaseX(cfg, mode, index)), bound)
                    self.assertLessEqual(abs(z - r.BaseZ(cfg, mode, index)), bound)
                    self.assertEqual(x, r.SlotX(cfg, mode, index, seed))
                    if mode == r.MODE_WEDGE:
                        values.add(round(x, 4))
        self.assertGreater(len(values), 200, 'different seeds and members must not share one offset')

    def test_leader_never_jitters_and_unit_stays_in_range(self):
        r, cfg = api(), shipped_config(SpacingJitter=0.5)
        for seed in range(-50, 50):
            self.assertEqual(0.0, r.SlotX(cfg, r.MODE_WEDGE, 0, seed))
            for salt in range(0, 40):
                self.assertGreaterEqual(r.Unit(seed, salt), 0.0)
                self.assertLess(r.Unit(seed, salt), 1.0)
                self.assertGreaterEqual(r.SignedUnit(seed, salt), -1.0)
                self.assertLess(r.SignedUnit(seed, salt), 1.0)

    def test_seed_is_non_negative_and_stable_for_a_site_id(self):
        r = api()
        first = r.SeedOf(HStr('site:alpha'))
        self.assertGreaterEqual(first, 0)
        self.assertEqual(first, r.SeedOf(HStr('site:alpha')))
        self.assertNotEqual(first, r.SeedOf(HStr('site:bravo')))

    def test_mix_never_overflows_a_32_bit_int(self):
        r = api()
        for seed in (0, 1, 2 ** 31 - 1, 12345678):
            for salt in (0, 1, 999, 2 ** 31 - 1):
                value = r.Mix(seed, salt)
                self.assertTrue(0 <= value < 46337)

    def test_pace_mix_follows_the_configured_share(self):
        r, cfg = api(), shipped_config()
        for percent in (0, 25, 50, 100):
            cfg.JogPercentOpen = percent
            jogs = sum(1 for seed in range(1, 400) for index in range(1, 6)
                       if r.IsJog(cfg, r.MODE_WEDGE, seed, index, 3))
            share = jogs / (399.0 * 5)
            with self.subTest(percent=percent):
                self.assertLess(abs(share - percent / 100.0), 0.05)
        cfg.JogPercentOpen = 50
        self.assertEqual(r.IsJog(cfg, r.MODE_WEDGE, 9, 2, 3), r.IsJog(cfg, r.MODE_WEDGE, 9, 2, 3))
        epochs = {r.IsJog(cfg, r.MODE_WEDGE, 9, 2, epoch) for epoch in range(0, 40)}
        self.assertEqual({True, False}, epochs, 'a member changes pace between epochs')

    def test_regroup_jogs_and_buildings_walk(self):
        r, cfg = api(), shipped_config()
        self.assertGreater(r.JogPercent(cfg, r.MODE_REGROUP), r.JogPercent(cfg, r.MODE_WEDGE))
        self.assertLess(r.JogPercent(cfg, r.MODE_TIGHT), r.JogPercent(cfg, r.MODE_COLUMN))


class JunctionsAndPauses(unittest.TestCase):
    def test_turn_degrees_and_junction_threshold(self):
        r, cfg = api(), shipped_config(JunctionTurnDegrees=50.0)
        self.assertAlmostEqual(0.0, r.TurnDegrees(0, 0, 0, 10, 0, 20), places=3)
        self.assertAlmostEqual(90.0, r.TurnDegrees(0, 0, 0, 10, 10, 10), places=3)
        self.assertAlmostEqual(180.0, r.TurnDegrees(0, 0, 0, 10, 0, 0), places=3)
        self.assertEqual(0.0, r.TurnDegrees(0, 0, 0, 0, 5, 5), 'a zero-length leg is not a turn')
        self.assertTrue(r.IsJunction(cfg, 90.0))
        self.assertFalse(r.IsJunction(cfg, 20.0))

    def test_pause_roll_is_seeded_bounded_and_respects_chance(self):
        r, cfg = api(), shipped_config(PauseChancePercent=0)
        self.assertFalse(any(r.PauseRoll(cfg, s, k) for s in range(50) for k in range(20)))
        cfg.PauseChancePercent = 100
        self.assertTrue(all(r.PauseRoll(cfg, s, k) for s in range(50) for k in range(20)))
        cfg.PauseChancePercent = 20
        hits = sum(1 for s in range(1, 300) for k in range(10) if r.PauseRoll(cfg, s, k))
        self.assertLess(abs(hits / 2990.0 - 0.20), 0.05)
        for s in range(1, 100):
            for k in range(10):
                seconds = r.PauseSeconds(cfg, s, k)
                self.assertTrue(cfg.PauseMinSeconds <= seconds <= cfg.PauseMaxSeconds)

    def test_road_surface_prefix_match(self):
        r, cfg = api(), shipped_config(RoadSurfaces=EArray([EStr('cp_asphalt')]))
        self.assertTrue(r.IsRoadSurface(cfg, EStr('cp_asphalt1')))
        self.assertFalse(r.IsRoadSurface(cfg, EStr('cp_grass')))
        self.assertFalse(r.IsRoadSurface(cfg, EStr('')))


class ConfigRanges(unittest.TestCase):
    def test_shipped_defaults_are_on_and_valid(self):
        cfg = shipped_config()
        self.assertFalse(cfg.Disabled, 'on by default')
        self.assertEqual('', api().ConfigProblem(cfg))

    def test_every_range_is_enforced_by_name(self):
        r = api()
        bad = {
            'SchemaVersion': 9, 'GroupsPerTick': 0, 'RefreshSeconds': 1, 'MinMembers': 1,
            'NearBuildingRadius': 0.5, 'TownRadius': 9999.0, 'RegroupSeconds': 0, 'ThreatPercent': 0,
            'ColumnSpacing': 0.1, 'WedgeSpacing': 99.0, 'StaggerSpacing': 0.0, 'TightSpacing': 0.2,
            'SpreadSpacing': 500.0, 'RegroupSpacing': 0.0, 'ColumnLane': -1.0, 'WedgeWidth': 9.0,
            'StaggerWidth': 0.0, 'SpreadDepth': 5.0, 'LookOutDegrees': 400.0, 'SpacingJitter': 0.9,
            'JogPercentRoad': 101, 'JogPercentOpen': -1, 'JogPercentTown': 200, 'JogPercentTight': -5,
            'JogPercentRegroup': 101, 'PaceEpochSeconds': 1, 'PauseChancePercent': 101,
            'PauseMinSeconds': 0, 'PauseMaxSeconds': 9999, 'PauseCooldownSeconds': 0,
            'JunctionTurnDegrees': 1.0, 'JunctionRadius': 0.0, 'JunctionPauseSeconds': 0,
        }
        for field, value in bad.items():
            with self.subTest(field=field):
                problem = r.ConfigProblem(shipped_config(**{field: value}))
                self.assertIn(field, problem)

    def test_cross_field_rules_and_surface_list(self):
        r = api()
        self.assertIn('PauseMaxSeconds', r.ConfigProblem(shipped_config(PauseMinSeconds=20, PauseMaxSeconds=10)))
        self.assertIn('TownRadius', r.ConfigProblem(shipped_config(NearBuildingRadius=60.0, TownRadius=40.0)))
        self.assertIn('RoadSurfaces', r.ConfigProblem(shipped_config(RoadSurfaces=EArray([EStr('')]))))
        self.assertIn('RoadSurfaces', r.ConfigProblem(shipped_config(RoadSurfaces=EArray([EStr('x')] * 20))))

    def test_zero_filled_json_is_refused_not_trusted(self):
        zero = {key: (EArray() if isinstance(value, list) else (type(value)(0) if not isinstance(value, bool) else False))
                for key, value in json.loads(SHIPPED.read_text()).items()}
        self.assertNotEqual('', api().ConfigProblem(N(**zero)))


# ---------------------------------------------------------------------------
# Controller: synthetic Expansion group/member ports (no engine behaviour).
# ---------------------------------------------------------------------------

class Member:
    """Strict stand-in: any call outside the admitted surface raises AttributeError."""
    def __init__(self, index, flags, log):
        self.index, self.flags, self.log = index, flags, log
        self.speed, self.threat_speed, self.halted, self.alive = 1, 3, False, True
        self.m_eAI_Halt = False
        self.threat = 0.0

    def IsAlive(self): return self.alive
    def GetPosition(self): return self.flags.position
    def GetThreatToSelf(self, ignore=False): return self.threat
    def GetMovementSpeedLimit(self): return self.speed
    def GetMovementSpeedLimitUnderThreat(self): return self.threat_speed

    def SetMovementSpeedLimits(self, speed, under=-1):
        self.speed = speed
        self.log.append(('speed', self.index, speed, under))

    def eAI_SetHalt(self, halt):
        self.m_eAI_Halt = halt
        self.halted = halt
        self.log.append(('halt', self.index, halt))

    def Expansion_GetMovementSpeed(self): return self.flags.moving


def group_fixture(size=4, waypoints=None, current=0):
    flags = N(now=1000, combat=False, position=(0.0, 0.0, 0.0), moving=2.0, surface=EStr('cp_grass'),
              players=1, budget=True, house=None, ticks=0, takes=0)
    log = []
    members = [Member(i, flags, log) for i in range(size)]
    installed = []
    wps = EArray(waypoints or [])
    group = N(Count=lambda: len(members), GetMember=lambda i: members[i],
              IsInCombat=lambda: flags.combat, GetFormationLeader=lambda: members[0],
              GetWaypoints=lambda: wps, m_CurrentWaypointIndex=current,
              SetFormation=lambda form: installed.append(form) or log.append(('formation', form)),
              GetFormation=lambda: installed[-1] if installed else None)
    return group, members, flags, log, installed


def site_fixture(group, name='site-a', house=None):
    patrol = N(m_Group=group, m_HCPendingMembers=0)
    return N(Patrol=patrol, Completed=False, Transient=False, ProposalId=HStr(name),
             HouseObject=house, HCStyle=None)


def make_controller(states, flags, cfg=None, logs=None):
    text = prepared_source()
    logs = [] if logs is None else logs
    cfg = cfg or shipped_config()
    r = api()
    styles = {}

    def new_style():
        return N(GroupRef=None, FormRef=None, Seed=0, Evals=0, NextEvalAt=0, NextPauseAt=0, PauseUntil=0,
                 RegroupUntil=0, Mode=-1, PaceEpoch=0, PaceEpochStart=0, LastJunction=-1,
                 Halted=EArray(), Foreign=False)

    def new_form():
        form = N(mode=-1, seed=0, cfg=None)
        form.HCConfigure = lambda c, s: (setattr(form, 'cfg', c), setattr(form, 'seed', s))
        form.HCSetMode = lambda m: setattr(form, 'mode', m)
        return form

    director = N(Phase=lambda: 'run', States=lambda: EArray(states))
    status_log = type('StatusLog', (list,), {})()

    def take(consumer, cost):
        flags.takes += 1
        return flags.budget

    owner = N(HCObserve=lambda *a: status_log.append(('observe',) + a),
              HCCounters=lambda *a: status_log.append(('counters',) + a))
    env = dict(
        Math=math_env(), EArray=EArray, HCArray=EArray, Print=logs.append, str=str,
        GetGame=lambda: N(IsServer=lambda: True, GetTickTime=lambda: float(flags.now)),
        HCPerfPlayers=N(HCGet=lambda: EArray([object()] * flags.players)),
        HCXAISiteDirector=N(Active=lambda: director),
        HCServer=N(HCTickWork=lambda: N(HCTakeFor=take)),
        HCWorldClock=N(UTC=lambda: flags.now),
        HCXAIGroupStyle=new_style, HCXAIStyleFormation=new_form,
        HCOperationalStatus=lambda: N(HCPublish=lambda s, why: setattr(status_log, 'last', (s, why)),
                                      HCState=lambda: getattr(status_log, 'last', ('x', ''))[0],
                                      HCReason=lambda: getattr(status_log, 'last', ('', 'y'))[1]),
        HCOperationalContributors=N(HCRegisterOwner=lambda name: owner),
        HCV2Admission=N(Line=lambda f, p, g, q: 'admission %s %s' % (f, p)),
        vector=N(Distance=lambda a, b: math.dist(a, b)),
        HCXAIFormationRules=r,
        HCXAIFormationController=N(**class_consts(text, 'HCXAIFormationController')),
        eAIBase=N(Cast=lambda actor: actor),
        eAIMovementSpeed=N(WALK=1, JOG=2),
        HCActor=object,
    )
    env['HCXAIFormationRules'] = r
    names = ('Open', 'Close', 'Step', 'ReleasePass', 'StepGroup', 'ApplyPace', 'BeginPause',
             'ReleaseStyle', 'HoldEnded', 'JunctionIndex', 'HCRefuse', 'HCGetOperationalStatus',
             'Observe', 'ForgetStyle', 'ContextOf', 'Due', 'ConsiderPause', 'ApplyFormation')
    translate(text, 'HCXAIFormationController', env, only=names)
    worker = N(m_Enabled=False, m_Closed=False, m_Cursor=0, m_Config=None, m_Refusal='',
               m_Managed=0, m_Refused=0, m_Worked=0, m_Pauses=0, m_Junctions=0, m_LoadProblem='',
               m_Holding=EArray(), m_Owner=None, m_Requested=False, m_ConfigProblem='', m_ObserveAt=0)
    worker.SurfaceAt = lambda at: flags.surface
    for name in names:
        setattr(worker, name, lambda *a, name=name: env[name](worker, *a))
    return worker, cfg, logs, status_log


def run_steps(worker, flags, count, seconds=1):
    for _ in range(count):
        flags.now += seconds
        worker.Step()


class ControllerFormation(unittest.TestCase):
    def build(self, size=4, **cfg_changes):
        group, members, flags, log, installed = group_fixture(size)
        state = site_fixture(group)
        cfg = shipped_config(**cfg_changes)
        worker, cfg, logs, status = make_controller([state], flags, cfg)
        worker.Open(cfg, '', True)
        return worker, group, members, flags, log, installed, state, logs, status

    def test_open_logs_one_admission_line_and_installs_nothing_yet(self):
        worker, group, members, flags, log, installed, state, logs, status = self.build()
        self.assertEqual(1, len([l for l in logs if 'admission' in l]))
        self.assertEqual([], installed)

    def test_first_step_installs_one_formation_and_it_follows_context(self):
        worker, group, members, flags, log, installed, state, logs, status = self.build()
        r = api()
        run_steps(worker, flags, 3, cfg_seconds(worker))
        self.assertEqual(1, len(installed), 'one formation per group, never reinstalled each step')
        self.assertEqual(r.MODE_WEDGE, installed[0].mode)
        flags.surface = EStr('cp_asphalt1')
        run_steps(worker, flags, 3, cfg_seconds(worker))
        self.assertEqual(r.MODE_COLUMN, installed[0].mode)
        flags.combat = True
        run_steps(worker, flags, 3, cfg_seconds(worker))
        self.assertEqual(r.MODE_SPREAD, installed[0].mode)
        flags.combat = False
        run_steps(worker, flags, 1, cfg_seconds(worker))
        self.assertEqual(r.MODE_REGROUP, installed[0].mode, 'regroup after contact')
        flags.now += worker.m_Config.RegroupSeconds + 5
        run_steps(worker, flags, 2, cfg_seconds(worker))
        self.assertEqual(r.MODE_COLUMN, installed[0].mode, 'back to the road column once regrouped')
        self.assertEqual(1, len(installed))

    def test_building_context_uses_the_group_site_house_distance(self):
        group, members, flags, log, installed = group_fixture(3)
        house = N(GetPosition=lambda: (10.0, 0.0, 0.0))
        state = site_fixture(group, house=house)
        worker, cfg, logs, status = make_controller([state], flags)
        worker.Open(cfg, '', True)
        r = api()
        run_steps(worker, flags, 2, cfg.RefreshSeconds)
        self.assertEqual(r.MODE_TIGHT, installed[0].mode)
        flags.position = (cfg.TownRadius - 5.0 + 10.0, 0.0, 0.0)
        run_steps(worker, flags, 2, cfg.RefreshSeconds)
        self.assertEqual(r.MODE_STAGGER, installed[0].mode)

    def test_speed_mix_stays_walk_or_jog_and_keeps_the_under_threat_limit(self):
        group, members, flags, log, installed = group_fixture(8)
        state = site_fixture(group)
        worker, cfg, logs, status = make_controller([state], flags, shipped_config(JogPercentOpen=50, PauseChancePercent=0))
        worker.Open(cfg, '', True)
        run_steps(worker, flags, 3, cfg.RefreshSeconds)
        speeds = [e for e in log if e[0] == 'speed']
        self.assertTrue(speeds)
        self.assertTrue(all(e[2] in (1, 2) for e in speeds), 'walk or jog only, never sprint')
        self.assertTrue(all(e[3] == 3 for e in speeds), 'the native under-threat limit is passed through')
        self.assertEqual({1, 2}, {m.speed for m in members}, 'a mixed pace across the group')

    def test_no_pace_change_while_the_group_is_in_combat(self):
        group, members, flags, log, installed = group_fixture(4)
        state = site_fixture(group)
        flags.combat = True
        worker, cfg, logs, status = make_controller([state], flags)
        worker.Open(cfg, '', True)
        run_steps(worker, flags, 4, cfg.RefreshSeconds)
        self.assertEqual([], [e for e in log if e[0] in ('speed', 'halt')])

    def test_pace_is_deterministic_for_a_given_site(self):
        outcomes = []
        for _ in range(2):
            group, members, flags, log, installed = group_fixture(6)
            state = site_fixture(group, 'site-fixed')
            worker, cfg, logs, status = make_controller([state], flags, shipped_config(PauseChancePercent=0))
            worker.Open(cfg, '', True)
            run_steps(worker, flags, 4, cfg.RefreshSeconds)
            outcomes.append([m.speed for m in members])
        self.assertEqual(outcomes[0], outcomes[1])


def cfg_seconds(worker):
    return worker.m_Config.RefreshSeconds


class ControllerPauses(unittest.TestCase):
    def build(self, waypoints=None, **cfg_changes):
        group, members, flags, log, installed = group_fixture(4, waypoints=waypoints, current=1)
        state = site_fixture(group)
        defaults = dict(PauseChancePercent=100)
        defaults.update(cfg_changes)
        worker, cfg, logs, status = make_controller([state], flags, shipped_config(**defaults))
        worker.Open(cfg, '', True)
        return worker, group, members, flags, log, cfg, logs

    def test_random_pause_halts_everyone_then_releases_on_time_and_cools_down(self):
        worker, group, members, flags, log, cfg, logs = self.build()
        run_steps(worker, flags, 2, cfg.RefreshSeconds)
        self.assertTrue(all(m.halted for m in members), 'a pause is a native halt of the whole group')
        halts = [e for e in log if e[0] == 'halt']
        self.assertEqual(4, len([e for e in halts if e[2]]))
        flags.now += cfg.PauseMaxSeconds + 1
        worker.Step()
        self.assertFalse(any(m.halted for m in members), 'released when the pause expires')
        count = len([e for e in log if e[0] == 'halt' and e[2]])
        run_steps(worker, flags, 3, cfg.RefreshSeconds)
        self.assertEqual(count, len([e for e in log if e[0] == 'halt' and e[2]]), 'cooldown blocks an immediate repeat')

    def test_combat_or_threat_releases_a_pause_on_the_next_step(self):
        worker, group, members, flags, log, cfg, logs = self.build()
        run_steps(worker, flags, 2, cfg.RefreshSeconds)
        self.assertTrue(members[1].halted)
        flags.combat = True
        worker.Step()
        self.assertFalse(any(m.halted for m in members), 'a halted AI must never stand under fire')
        flags.combat = False
        run_steps(worker, flags, 2, cfg.RefreshSeconds)
        members[2].threat = 0.9
        run_steps(worker, flags, 1, 0)
        self.assertFalse(members[2].halted)

    def test_close_releases_every_hold(self):
        worker, group, members, flags, log, cfg, logs = self.build()
        run_steps(worker, flags, 2, cfg.RefreshSeconds)
        self.assertTrue(members[0].halted)
        worker.Close()
        self.assertFalse(any(m.halted for m in members))

    def test_a_native_halt_set_elsewhere_is_never_taken_over_or_cleared(self):
        worker, group, members, flags, log, cfg, logs = self.build()
        members[1].m_eAI_Halt = True
        members[1].halted = True
        run_steps(worker, flags, 2, cfg.RefreshSeconds)
        flags.now += cfg.PauseMaxSeconds + 1
        worker.Step()
        self.assertTrue(members[1].halted, 'a halt this controller did not set is left alone')
        self.assertFalse(any(e == ('halt', 1, True) or e == ('halt', 1, False) for e in log))

    def test_stationary_leader_is_not_paused(self):
        worker, group, members, flags, log, cfg, logs = self.build()
        flags.moving = 0.0
        run_steps(worker, flags, 4, cfg.RefreshSeconds)
        self.assertFalse(any(e[0] == 'halt' for e in log))

    def test_no_pause_in_combat_regroup_or_spread(self):
        worker, group, members, flags, log, cfg, logs = self.build()
        flags.combat = True
        run_steps(worker, flags, 3, cfg.RefreshSeconds)
        flags.combat = False
        run_steps(worker, flags, 1, 1)
        self.assertFalse(any(e[0] == 'halt' and e[2] for e in log), 'no pause during or right after contact')

    def test_leader_pauses_at_a_turn_vertex_but_not_on_a_straight_route(self):
        turn = [(0.0, 0.0, 0.0), (0.0, 0.0, 50.0), (50.0, 0.0, 50.0)]
        worker, group, members, flags, log, cfg, logs = self.build(turn, PauseChancePercent=0)
        flags.position = (0.0, 0.0, 49.0)
        run_steps(worker, flags, 1, cfg.RefreshSeconds)
        self.assertTrue(all(m.halted for m in members), 'junction pause')
        self.assertEqual(1, worker.m_Junctions)
        flags.now += cfg.JunctionPauseSeconds + 1
        worker.Step()
        run_steps(worker, flags, 3, cfg.RefreshSeconds)
        self.assertEqual(1, worker.m_Junctions, 'one pause per visit of the same vertex')
        straight = [(0.0, 0.0, 0.0), (0.0, 0.0, 50.0), (0.0, 0.0, 100.0)]
        worker, group, members, flags, log, cfg, logs = self.build(straight, PauseChancePercent=0)
        flags.position = (0.0, 0.0, 49.0)
        run_steps(worker, flags, 4, cfg.RefreshSeconds)
        self.assertFalse(any(e[0] == 'halt' for e in log))

    def test_far_from_the_vertex_is_not_a_junction(self):
        turn = [(0.0, 0.0, 0.0), (0.0, 0.0, 50.0), (50.0, 0.0, 50.0)]
        worker, group, members, flags, log, cfg, logs = self.build(turn, PauseChancePercent=0)
        flags.position = (0.0, 0.0, 10.0)
        run_steps(worker, flags, 3, cfg.RefreshSeconds)
        self.assertFalse(any(e[0] == 'halt' for e in log))


class ControllerBounds(unittest.TestCase):
    def many(self, count, **changes):
        flags = N(now=1000, combat=False, position=(0.0, 0.0, 0.0), moving=2.0, surface=EStr('cp_grass'),
                  players=1, budget=True, takes=0)
        states, groups = [], []
        for index in range(count):
            group, members, f, log, installed = group_fixture(3)
            members[0].flags = flags
            for m in members:
                m.flags = flags
            groups.append((group, installed))
            states.append(site_fixture(group, 'site-%d' % index))
        worker, cfg, logs, status = make_controller(states, flags, shipped_config(**changes))
        worker.Open(cfg, '', True)
        return worker, flags, states, groups, cfg, logs, status

    def test_a_cursor_serves_a_few_groups_per_tick_and_rotates(self):
        worker, flags, states, groups, cfg, logs, status = self.many(9, GroupsPerTick=2, PauseChancePercent=0)
        flags.now += cfg.RefreshSeconds
        worker.Step()
        self.assertEqual(2, sum(1 for g, i in groups if i))
        flags.now += 0
        for _ in range(5):
            worker.Step()
        self.assertEqual(9, sum(1 for g, i in groups if i), 'every group is reached by the rotating cursor')
        self.assertLessEqual(flags.takes, 2 * 6)

    def test_shared_budget_refusal_stops_the_pass_and_keeps_the_cursor(self):
        worker, flags, states, groups, cfg, logs, status = self.many(5, GroupsPerTick=4, PauseChancePercent=0)
        flags.budget = False
        worker.Step()
        self.assertEqual(0, sum(1 for g, i in groups if i))
        self.assertEqual(0, worker.m_Cursor)
        flags.budget = True
        flags.now += cfg.RefreshSeconds
        worker.Step()
        self.assertEqual(4, sum(1 for g, i in groups if i))

    def test_no_players_or_disabled_or_closed_is_a_cheap_no_op(self):
        worker, flags, states, groups, cfg, logs, status = self.many(3)
        flags.players = 0
        flags.now += cfg.RefreshSeconds
        worker.Step()
        self.assertEqual(0, flags.takes)
        flags.players = 1
        worker.Close()
        worker.Step()
        self.assertEqual(0, flags.takes)
        self.assertEqual(0, sum(1 for g, i in groups if i))

    def test_disabled_config_is_an_opt_out_with_an_off_status(self):
        flags = N(now=1000, combat=False, position=(0.0, 0.0, 0.0), moving=2.0, surface=EStr('cp_grass'),
                  players=1, budget=True, takes=0)
        group, members, f, log, installed = group_fixture(3)
        worker, cfg, logs, status = make_controller([site_fixture(group)], flags, shipped_config(Disabled=True))
        worker.Open(cfg, '', True)
        worker.Step()
        self.assertEqual(0, flags.takes)
        self.assertEqual([], installed)
        self.assertEqual('off', worker.HCGetOperationalStatus().HCState())
        self.assertEqual(1, len([l for l in logs if 'admission' in l and 'False' in l]))

    def test_invalid_config_refuses_with_a_named_reason_and_runs_nothing(self):
        flags = N(now=1000, combat=False, position=(0.0, 0.0, 0.0), moving=2.0, surface=EStr('cp_grass'),
                  players=1, budget=True, takes=0)
        group, members, f, log, installed = group_fixture(3)
        worker, cfg, logs, status = make_controller([site_fixture(group)], flags, shipped_config(JunctionRadius=0.0))
        worker.Open(cfg, '', True)
        worker.Step()
        state = worker.HCGetOperationalStatus()
        self.assertEqual('refused', state.HCState())
        self.assertIn('JunctionRadius', state.HCReason())
        self.assertEqual([], installed)

    def test_unreadable_config_is_refused_not_silently_defaulted(self):
        flags = N(now=1000, combat=False, position=(0.0, 0.0, 0.0), moving=2.0, surface=EStr('cp_grass'),
                  players=1, budget=True, takes=0)
        group, members, f, log, installed = group_fixture(3)
        worker, cfg, logs, status = make_controller([site_fixture(group)], flags)
        worker.Open(None, 'config_unreadable', True)
        worker.Step()
        self.assertEqual('refused', worker.HCGetOperationalStatus().HCState())
        self.assertEqual([], installed)

    def test_status_is_derived_from_observed_groups_not_hardcoded(self):
        worker, flags, states, groups, cfg, logs, status = self.many(2, PauseChancePercent=0)
        self.assertEqual('requested', worker.HCGetOperationalStatus().HCState())
        flags.now += cfg.RefreshSeconds
        worker.Step()
        self.assertEqual('ready', worker.HCGetOperationalStatus().HCState())

    def test_pending_members_and_missing_leader_are_skipped_without_effects(self):
        flags = N(now=1000, combat=False, position=(0.0, 0.0, 0.0), moving=2.0, surface=EStr('cp_grass'),
                  players=1, budget=True, takes=0)
        group, members, f, log, installed = group_fixture(3)
        state = site_fixture(group)
        state.Patrol.m_HCPendingMembers = 2
        worker, cfg, logs, status = make_controller([state], flags)
        worker.Open(cfg, '', True)
        run_steps(worker, flags, 3, cfg.RefreshSeconds)
        self.assertEqual([], installed)
        self.assertEqual([], log)

    def test_a_formation_replaced_by_another_owner_is_refused_once_not_fought(self):
        group, members, flags, log, installed = group_fixture(3)
        state = site_fixture(group)
        worker, cfg, logs, status = make_controller([state], flags, shipped_config(PauseChancePercent=0))
        worker.Open(cfg, '', True)
        run_steps(worker, flags, 2, cfg.RefreshSeconds)
        self.assertEqual(1, len(installed))
        installed.append(N(foreign=True))
        run_steps(worker, flags, 6, cfg.RefreshSeconds)
        self.assertEqual(2, len(installed), 'the controller does not re-take a formation another owner installed')
        self.assertEqual(1, len([l for l in logs if 'formation_replaced' in l]), 'refusal logs once per change')


class SourceContract(unittest.TestCase):
    def setUp(self):
        self.text = SOURCE.read_text()

    def test_no_teleport_or_position_write_is_authored(self):
        for forbidden in ('SetPosition', 'SetOrigin', 'Teleport', 'OverrideTargetPosition', 'dBodySet'):
            self.assertNotIn(forbidden, self.text)

    def test_uses_the_shared_core_budget_and_status_owner(self):
        for needle in ('HCTickWork', 'HCTakeFor', 'HCOperationalContributors.HCRegisterOwner',
                       'HCV2Admission.Line', 'HCProfileDefaults', 'HCPerfPlayers.HCGet'):
            self.assertIn(needle, self.text)

    def test_expansion_calls_are_cited_with_file_and_line(self):
        for needle in ('eAIFormation.c', 'eAIGroup.c', 'eAIBase.c'):
            self.assertIn(needle, self.text)

    def test_shipped_json_lists_every_tunable_the_validator_names(self):
        raw = json.loads(SHIPPED.read_text())
        fields = re.findall(r'RangeProblem\("(\w+)"', self.text)
        self.assertGreaterEqual(len(fields), 25)
        for field in fields:
            self.assertIn(field, raw)
        dto = re.search(r'class HCXAIFormationConfig\s*\{(.*?)\n\}', self.text, re.S).group(1)
        for field in re.findall(r'^\s+(?:ref )?[\w<>]+ (\w+)\s*[;=]', dto, re.M):
            self.assertIn(field, raw)


if __name__ == '__main__':
    unittest.main()
