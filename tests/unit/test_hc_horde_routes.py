"""HC-46: one behavioral scenario through authored Enforce/restricted ports.

Explicit synthetic positions, ownership, observer and IO ports are not native
path/perception/persistence evidence. Trace: owner Wave 3 HC-46 / #121; HC-11 owns
canonical spec/plan/tasks (absent from this dispatched checkout).

Actual RED, before implementation (2026-11-18):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_horde_routes -v
AssertionError: 699 not less than or equal to 130 : a route must never renew the original noise expiry
Ran 1 test; FAILED (failures=1).
GREEN: same command, Ran 1 test; OK (recorded after implementing this slice).
"""
import copy
import json
from pathlib import Path
import re
from types import MethodType, SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import EArray, translate
from tests.unit.test_horde_stimulus import SyntheticClue

ROOT = Path(__file__).resolve().parents[2]
INFECTED = ROOT / 'mods/HollowCountry/scripts/4_World/Infected'
MIGRATION = INFECTED / 'HCHordeMigration.c'


class Vec(list):
    """Synthetic native vector arithmetic, no gameplay decisions."""
    def __add__(self, other): return Vec(x+y for x, y in zip(self, other))
    def __mul__(self, scale): return Vec(x*scale for x in self)


class NativeActor:
    """Synthetic engine handles compare by identity, never DTO field equality."""
    def __init__(self, position): self.position = position


def authored(path, name, env, owner, member=False):
    # Reuse the existing syntax-only restricted translator. These are type,
    # native output-slot and native field spellings, never alternate policies.
    text = path.read_text()
    text = re.sub(r'\b(HCHorde\w+|HCInfectedClue|HCInfectedActor|HCNativeInfectedPack|HCInfectedModule|AIAgent|HCHordeRecord)\b',
                  lambda m: 'HCEvent' + m[1], text)
    renamed_env = {re.sub(r'\b(HCHorde\w+|HCInfectedClue|HCInfectedActor|HCNativeInfectedPack|HCInfectedModule|AIAgent|HCHordeRecord)\b',
                         lambda m: 'HCEvent' + m[1], key): value for key, value in env.items()}
    text = re.sub(r'\bs_(\w+)\b', r'm_static_\1', text)
    text = re.sub(r'\bGroup\b', 'm_NativeGroup', text)
    text = re.sub(r'\b(RouteEnd|RouteResult|RoutePlanned|RouteCompleted|RoutePurpose)\b', r'm_\1', text)
    text = text.replace('vector centroid;', 'vector centroid = Vector(0, 0, 0);')
    text = re.sub(r'(\b[\w.]+)\+\+;', r'\1 += 1;', text)
    text = re.sub(r'(\b[\w.]+)--;', r'\1 -= 1;', text)
    return translate(text, name, renamed_env, 'HCEvent' + owner, member)


def bind(target, path, owner, names, env):
    for name in names:
        setattr(target, name, MethodType(authored(path, name, env, owner, True), target))
    return target


class HordeRoutes(unittest.TestCase):
    def test_finite_observed_route_preserves_cohort_and_refuses_replay(self):
        manifest = json.loads((ROOT / 'mission/hollow-country/infected/route-surveys.json').read_text())
        cfg = N(**manifest['Defaults'])
        distance = lambda a, b: sum((x-y)**2 for x, y in zip(a, b))
        env = dict(Math=N(Min=min, Max=max), Vector=lambda x,y,z: Vec([x,y,z]),
                   vector=N(DistanceSq=distance), HCHordeRouteDefaults=lambda: N(**manifest['Defaults']),
                   HCInfectedStore=N(ValidPosition=lambda point: len(point) == 3 and all(abs(v) < 1e6 for v in point)),
                   HCHordeMigration=N(Active=lambda: True), Print=lambda text: None)
        routes = N(m_static_Document=None, m_static_Reason='not loaded')
        env['HCHordeRoutes'] = routes
        bind(routes, MIGRATION, 'HCHordeRoutes', ('Defaults', 'ValidDefaults', 'ValidSurvey', 'HCBind', 'Select', 'Reason', 'HCClear'), env)
        stimulus = N()
        env['HCHordeStimulus'] = stimulus
        stimulus.HCRouteNoise = authored(INFECTED/'HCHordeStimulus.c', 'HCRouteNoise', env, 'HCHordeStimulus')
        recovery = N()
        recovery.HCRouteRoster = authored(INFECTED/'HCHordeRecovery.c', 'HCRouteRoster', env, 'HCHordeRecovery')
        env['HCHordeRecovery'] = recovery
        # Wave 16: the shipped manifest now admits its offline-derived routes
        # (runtime acceptance stays PENDING); an unsurveyed-only document still
        # refuses with the named pending reason.
        shipped = EArray(N(**{**r, 'Nodes': EArray(Vec(n) for n in r['Nodes'])}) for r in manifest['Routes'])
        document = N(SchemaVersion=1, WorldName='chernarusplus', Enabled=True, Defaults=cfg, Routes=shipped)
        self.assertTrue(routes.HCBind(document, 'chernarusplus'))
        self.assertEqual('SURVEY_SOURCE_READY_NATIVE_PENDING', routes.Reason())
        document.Routes = EArray([N(Id='x', Place='x', Surveyed=False, Evidence='', Nodes=EArray())])
        self.assertFalse(routes.HCBind(document, 'chernarusplus'))
        self.assertEqual('ROUTE_SURVEY_PENDING', routes.Reason())
        self.assertFalse(manifest['production_enabled'])
        self.assertTrue(manifest['pending_regional_coverage'])
        # Nothing in this fixture is a real Vybor survey.
        points = EArray([Vec([10,0,20]), Vec([60,0,20]), Vec([110,0,20])])
        route = N(Id='synthetic-corridor', Place='synthetic', Surveyed=True,
                  Evidence='SYNTHETIC-NOT-NATIVE', Nodes=points)
        document.Routes = EArray([route])
        self.assertTrue(routes.HCBind(document, 'chernarusplus'))
        document.Enabled = False
        self.assertFalse(routes.HCBind(document, 'chernarusplus'))
        self.assertEqual('ROUTE_OPERATOR_OFF', routes.Reason())
        document.Enabled = True
        self.assertTrue(routes.HCBind(document, 'chernarusplus'))
        for field, value in (('MaxMembers',7), ('MaxHops',3), ('CueRangeMetres',float('inf')),
                             ('ArrivalMetres',float('nan')), ('CooldownSeconds',0)):
            invalid = copy.copy(cfg); setattr(invalid, field, value)
            self.assertFalse(routes.ValidDefaults(invalid), field)
        clue = SyntheticClue(observed=99, expires=129)
        clue.Origin = points[-1]
        self.assertIs(route, routes.Select(points[0], clue))
        self.assertIsNone(routes.Select(Vec([999,0,999]), clue))
        roster = EArray([NativeActor(points[0]), NativeActor(points[0])])
        native_group = object()
        for actor in roster:
            actor.GetPosition = lambda a=actor: a.position
            actor.IsAlive = lambda: True
            actor.GetAIAgent = lambda: N(GetGroup=lambda: native_group)
            actor.GetMindStateSynced = lambda: 0
            actor.GetHealth = lambda *args: 1
        releases, logs, paths, tokens = [], [], [], [1]
        def token():
            if not tokens[0]: return False
            tokens[0] -= 1; return True
        quiet = [True]  # Explicit SYNTHETIC admission, NOT the current native gate.
        env.update(HCObserverTransitionGate=N(V2Quiet=lambda *args: quiet[0]),
                   HCInfectedModule=N(Instance=N(HCV2DriftRouteToken=token)),
                   DayZInfectedConstants=N(MINDSTATE_CHASE=2, MINDSTATE_FIGHT=3))
        def pack():
            ctx = N(m_V2Drift=False, m_Search=False, m_Releasing=False, m_NativeGroup=native_group,
                    m_V2Cooldown=0, m_V2LastEvidence=-1, m_Members=EArray(roster),
                    m_RoutePlan=EArray(), m_HCRoute=None, m_HCRouteConfig=None, m_HCRouteMembers=EArray(),
                    m_RouteEnd=points[-1], m_RoutePlanned=1, m_RouteCompleted=0,
                    Release=lambda: releases.append(True) or True)
            # Inherited native ports cannot be executed by an offline test.
            ports = dict(env, Release=ctx.Release, HCVarietyWalkerHerd=lambda: None,
                         Reachable=lambda *args: paths.append(args) or False)
            bind(ctx, MIGRATION, 'HCNativeInfectedPack', ('V2Remember', 'V2End', 'V2Tick'), ports)
            ctx.HCRouteLog = lambda phase, state: logs.append((phase,state))
            return ctx
        ctx = pack()
        before = tuple(ctx.m_Members)
        ctx.V2Remember(1, clue, 100)
        self.assertTrue(ctx.m_V2Drift)
        self.assertEqual(129, ctx.m_V2Deadline)
        self.assertEqual(before, tuple(ctx.m_Members))
        # A repeated receipt, expired receipt, excessive hops and cooldown are
        # checked by the shipped admission handler, not a Python route model.
        for change in ('replay', 'expired', 'hops', 'cooldown', 'cap', 'off'):
            p = pack(); cue = copy.copy(clue); now = 100
            if change == 'replay': p.m_V2LastEvidence = cue.Observed
            if change == 'expired': now = cue.Expires
            if change == 'hops': cue.Hops = 3
            if change == 'cooldown': p.m_V2Cooldown = 180
            if change == 'cap': p.m_Members = EArray(roster * 4)
            if change == 'off': document.Enabled = False
            p.V2Remember(1, cue, now)
            self.assertFalse(p.m_V2Drift, change)
            document.Enabled = True
        self.assertFalse(recovery.HCRouteRoster(2, 6, 3, False))
        self.assertFalse(recovery.HCRouteRoster(2, 6, 2, True))
        # Every member must reach the actual last native waypoint. A centroid
        # or the leading member cannot complete a route while another lags.
        ctx.m_V2Segment = True; ctx.m_HCRouteNode = 2
        ctx.m_V2BestDistance = -1; ctx.m_V2Progress = 100
        roster[0].position = points[-1]
        roster[1].position = points[0]
        self.assertTrue(ctx.V2Tick(101))
        self.assertTrue(ctx.m_V2Drift)
        self.assertEqual([], releases)
        roster[1].position = points[-1]
        self.assertFalse(ctx.V2Tick(102))
        self.assertEqual(2, ctx.m_RouteResult)
        self.assertIn(('reached','off'), logs)
        self.assertGreaterEqual(ctx.m_V2Cooldown, 102 + cfg.CooldownSeconds)
        self.assertEqual(before, tuple(ctx.m_Members))
        for reason in ('expired', 'roster', 'substitution', 'observer', 'path'):
            roster[0].position = roster[1].position = points[0]
            p = pack(); p.V2Remember(1, clue, 100)
            if reason == 'roster': p.m_Members.Remove(1)
            if reason == 'substitution': p.m_Members[1] = copy.copy(roster[1])
            quiet[0] = reason != 'observer'
            tokens[0] = 1
            self.assertFalse(p.V2Tick(129 if reason == 'expired' else 101), reason)
            self.assertFalse(p.m_V2Drift)
            self.assertEqual(6 if reason in ('roster','substitution','path') else 5, p.m_RouteResult)
        self.assertEqual(1, len(paths))  # failed path spends one shared token
        self.assertEqual(0, tokens[0])
        self.assertIn(('OBSERVER_QUIET_CONTRACT_REFUSED','refused'), logs)
        routes.HCClear()
        self.assertIsNone(routes.Defaults())
        self.assertEqual('ROUTE_OWNER_STOPPED', routes.Reason())

    def test_survey_manifest_is_read_from_the_shipped_mission_folder(self):
        # Review RED (2026-11-18): HCLoad read $profile:HollowCountry/infected/route-surveys.json, a
        # path nothing installs, so a surveyed route could never activate.
        from tools.package import pbo
        paths = re.findall(r'"\$(\w+):([^"]*route-surveys\.json)"', MIGRATION.read_text())
        self.assertEqual([('mission', 'hollow-country/infected/route-surveys.json')], paths)
        self.assertIn('infected/route-surveys.json', pbo.MISSION_FILES)
        self.assertTrue((ROOT / 'mission' / paths[0][1]).is_file())


if __name__ == '__main__':
    unittest.main()
