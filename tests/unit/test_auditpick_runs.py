"""#144 scavenging runs: bounded house stage, danger clues and combat abort (HCPickRunner/HCStep).

SYNTHETIC ports and a SYNTHETIC reservation port; nothing here observes DayZ, the walk
port or worker D's reservation. Runtime acceptance is PENDING.

TDD receipt (2026-11-19):
RED:  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_auditpick_runs -v
      (source changes hidden) -> see the commit message for the recorded failure lines.
GREEN: same command, all tests OK.
"""
import re
import unittest
from copy import deepcopy
from types import MethodType, SimpleNamespace as N

from tests.unit.test_map_layers import EStr, translate
from tests.unit.test_group_server import EArray
from tests.unit import test_auditpick_harness as h

RUNNER = h.HOUSES
PICKERS = h.ROOT / 'mods/HollowCountry/scripts/4_World/World/HCPickers.c'
METHODS = ('HCReset', 'HCDropToken', 'HCRun', 'HCAbort', 'HCEnd', 'HCHouseStage', 'HCGap',
           'HCNearest', 'HCPickNext', 'HCWalkStep', 'HCSearchStep', 'HCGoBack', 'HCBackStep')


class FakeHouses:
    """Synthetic HCPickHousePort that records order and can refuse or fail commits."""
    def __init__(self, refusal='', reserve=True, commit=True):
        self.refusal, self.allow_reserve, self.allow_commit = refusal, reserve, commit
        self.calls = []

    def HCRefusal(self):
        return EStr(self.refusal)

    def HCReserve(self, actor, target, actor_id):
        self.calls.append(('reserve', str(target.Key), str(actor_id)))
        return N(key=target.Key) if self.allow_reserve else None

    def HCCommit(self, token):
        self.calls.append(('commit', str(token.key)))
        return self.allow_commit

    def HCRelease(self, token):
        self.calls.append(('release', str(token.key)))

    def HCItem(self, token):
        return N(GetType=lambda: EStr('Apple'))


class FakePort:
    """Synthetic walk port: position moves only when a test says so."""
    def __init__(self, native, survey, houses):
        self.Survey, self.Houses, self.Danger = survey, houses, h.danger()
        self.Source = N(GetPosition=lambda: (0.0, 0.0, 0.0))
        self.pos = (0.0, 0.0, 0.0)
        self.Actor = N(GetPosition=lambda: self.pos)
        self.at_source, self.live, self.current = True, True, True
        self.members, self.combat, self.walk_ok = 3, False, True
        self.walks = []

    def HCAtSource(self):
        return self.at_source and sum(v * v for v in self.pos) <= 9.0
    def HCLive(self): return self.live
    def HCPartyCurrent(self, row): return self.current
    def HCPartyMembers(self): return self.members
    def HCPartyInCombat(self): return self.combat
    def HCActorKey(self): return EStr('actor-1')

    def HCWalkTo(self, point):
        self.walks.append(tuple(point))
        return self.walk_ok


class Rig:
    def __init__(self, houses=None, survey=None, native=None, sites=None):
        self.native = native or h.Native()
        self.survey = survey or h.shipped_survey(RunHouseSearchSeconds=6.0)
        self.houses = houses or FakeHouses()
        self.port = FakePort(self.native, self.survey, self.houses)
        self.row = N(LeaseId=EStr('lease'), Generation=1, PartyId=EStr('party'), RouteId=EStr('route:r1'))
        self.sites = sites if sites is not None else [('h1', (10.0, 0.0, 0.0)), ('h2', (30.0, 0.0, 0.0)),
                                                       ('h3', (50.0, 0.0, 0.0)), ('h4', (70.0, 0.0, 0.0))]
        env = self.native.env()
        env['HCPickPolicy'] = h.policy(self.native)
        env['HCPickRunner'] = N(HOLD=EStr('HOLD'))
        scans = []
        def find(centre, radius, maxTargets, maxObjects, targets):
            scans.append((tuple(centre), radius, maxTargets))
            for key, point in self.sites:
                targets.Insert(N(Key=EStr(key), Point=point, Dwelling=None, SiteId=1))
        env['HCPickHouseScan'] = N(HCFind=find)
        self.scans = scans
        self.runner = N(TripKey=EStr(''), Stage=EStr(''), CombatSince=-1, Searched=0, Attempts=0,
                        CurrentIndex=-1, StageAt=0, BackIssued=False, GapLogged=EStr(''), HouseToken=None,
                        Targets=EArray(), Visited=EArray())
        source = re.sub(r'^    ref array<', '    ref Array<', RUNNER.read_text(), flags=re.M)
        h._bind(source, 'HCPickRunner', self.runner, METHODS, env)

    def tick(self, seconds=0.0, returning=False):
        self.native.tick += seconds
        return str(self.runner.HCRun(self.port, returning, self.row))

    def lines(self, text):
        return [p for p in self.native.prints if text in p]


def danger_for(rig):
    """What the admission policy says about the run's route after the run ended."""
    quiet = N(HCPosition=lambda: (9.0e5, 0.0, 9.0e5))
    route = N(RouteId=rig.row.RouteId, Waypoints=[quiet])
    return str(h.policy(rig.native).RouteDanger(rig.survey, rig.port.Danger, route, rig.native.utc))


class HouseStage(unittest.TestCase):
    def test_nothing_starts_until_the_party_is_at_the_source(self):
        rig = Rig()
        rig.port.at_source = False
        self.assertEqual('', rig.tick())
        self.assertEqual([], rig.scans)
        self.assertEqual([], rig.port.walks)

    def test_reserve_wait_commit_release_in_order_and_houses_are_capped(self):
        rig = Rig()
        survey = rig.survey
        self.assertEqual('HOLD', rig.tick())              # scan + first pick (nearest, h1)
        self.assertEqual((10.0, 0.0, 0.0), rig.port.walks[-1])
        self.assertEqual([], rig.houses.calls, 'no reservation before arrival')
        rig.port.pos = (10.0, 0.0, 0.0)
        self.assertEqual('HOLD', rig.tick(1))             # arrive -> reserve
        self.assertEqual([('reserve', 'h1', 'actor-1')], rig.houses.calls)
        self.assertEqual('HOLD', rig.tick(survey.RunHouseSearchSeconds - 1))
        self.assertEqual(1, len(rig.houses.calls), 'commit waits for the search time')
        self.assertEqual('HOLD', rig.tick(1))             # search time elapsed -> commit, release
        self.assertEqual(['reserve', 'commit', 'release'], [c[0] for c in rig.houses.calls])
        self.assertEqual(1, rig.runner.Searched)
        # Visit houses until the per-run cap, then head back.
        for key, point in (('h2', (30.0, 0.0, 0.0)), ('h3', (50.0, 0.0, 0.0))):
            rig.tick(0)
            self.assertEqual(point, rig.port.walks[-1], key)
            rig.port.pos = point
            rig.tick(1)
            rig.tick(survey.RunHouseSearchSeconds)
        self.assertEqual(survey.RunMaxHousesPerRun, rig.runner.Searched)
        rig.tick(0)
        self.assertEqual('back', str(rig.runner.Stage))
        rig.tick(0)
        self.assertEqual((0.0, 0.0, 0.0), rig.port.walks[-1], 'the last leg is back to the source')
        self.assertNotIn('h4', [c[1] for c in rig.houses.calls], 'no fourth house')
        self.assertEqual(survey.RunMaxHousesPerRun, len(rig.lines('outcome=searched')))
        rig.port.pos = (0.0, 0.0, 0.0)
        self.assertEqual('', rig.tick(1), 'back at the source the normal acquire follows')
        self.assertEqual('done', str(rig.runner.Stage))
        self.assertEqual(0, len(rig.houses.calls) - 3 * survey.RunMaxHousesPerRun)

    def test_visits_the_nearest_unvisited_house_first(self):
        rig = Rig(sites=[('far', (90.0, 0.0, 0.0)), ('near', (12.0, 0.0, 0.0))])
        rig.tick()
        self.assertEqual((12.0, 0.0, 0.0), rig.port.walks[0])

    def test_a_failed_commit_releases_the_token_and_is_not_counted(self):
        rig = Rig(houses=FakeHouses(commit=False), sites=[('h1', (10.0, 0.0, 0.0))])
        rig.tick()
        rig.port.pos = (10.0, 0.0, 0.0)
        rig.tick(1)
        rig.tick(rig.survey.RunHouseSearchSeconds)
        self.assertEqual(['reserve', 'commit', 'release'], [c[0] for c in rig.houses.calls])
        self.assertEqual(0, rig.runner.Searched)
        self.assertEqual(1, len(rig.lines('outcome=refused')))

    def test_a_refused_reservation_skips_the_house_and_attempts_are_bounded(self):
        rig = Rig(houses=FakeHouses(reserve=False))
        survey = rig.survey
        for step in range(40):
            if str(rig.runner.Stage) == 'back':
                break
            rig.tick(0)
            rig.port.pos = rig.port.walks[-1] if rig.port.walks else rig.port.pos
            rig.tick(1)
        self.assertEqual('back', str(rig.runner.Stage))
        self.assertLessEqual(rig.runner.Attempts, survey.RunMaxHouseAttempts)
        self.assertEqual(0, rig.runner.Searched)
        self.assertEqual([c for c in rig.houses.calls if c[0] != 'reserve'], [])

    def test_an_unbound_port_is_named_once_and_the_normal_run_continues(self):
        rig = Rig(houses=FakeHouses(refusal='PICKER_HOUSE_PORT_UNBOUND'))
        self.assertEqual('', rig.tick())
        self.assertEqual('', rig.tick(1))
        self.assertEqual(1, len(rig.lines('run houses=skipped reason=PICKER_HOUSE_PORT_UNBOUND')))
        self.assertEqual([], rig.port.walks)
        self.assertEqual([], rig.houses.calls)

    def test_a_walk_that_never_arrives_gives_up_on_that_house(self):
        rig = Rig(sites=[('h1', (10.0, 0.0, 0.0))])
        rig.tick()
        self.assertEqual('walk', str(rig.runner.Stage))
        rig.tick(rig.survey.RunHouseWalkSeconds + 1)
        self.assertEqual('pick', str(rig.runner.Stage))
        self.assertEqual([], rig.houses.calls, 'never reserved without arriving')

    def test_back_leg_that_never_arrives_aborts_without_a_teleport(self):
        rig = Rig(sites=[])
        rig.tick()                       # scan finds nothing -> straight to the back stage
        self.assertEqual('back', str(rig.runner.Stage))
        rig.port.pos = (40.0, 0.0, 0.0)
        rig.tick(1)
        self.assertEqual((0.0, 0.0, 0.0), rig.port.walks[-1])
        self.assertEqual('RUN_ABORT_BACK_TIMEOUT', rig.tick(rig.survey.RunHouseWalkSeconds + 1))
        self.assertEqual(1, len(rig.lines('run end')))

    def test_returning_leg_drops_any_token_and_runs_no_house_stage(self):
        rig = Rig()
        rig.tick()
        rig.port.pos = (10.0, 0.0, 0.0)
        rig.tick(1)
        self.assertIsNotNone(rig.runner.HouseToken)
        self.assertEqual('', rig.tick(0, returning=True))
        self.assertIsNone(rig.runner.HouseToken)
        self.assertEqual('release', rig.houses.calls[-1][0])


class LeaseAndCarrierAreCheckedBeforeEveryCall(unittest.TestCase):
    def test_lost_lease_or_carrier_aborts_before_any_house_call(self):
        for attr in ('current', 'live'):
            with self.subTest(attr=attr):
                rig = Rig()
                setattr(rig.port, attr, False)
                self.assertEqual('RUN_ABORT_LEASE', rig.tick())
                self.assertEqual([], rig.houses.calls)
                self.assertEqual([], rig.port.walks)

    def test_lease_lost_mid_stage_releases_the_reservation(self):
        rig = Rig()
        rig.tick()
        rig.port.pos = (10.0, 0.0, 0.0)
        rig.tick(1)
        rig.port.current = False
        self.assertEqual('RUN_ABORT_LEASE', rig.tick(rig.survey.RunHouseSearchSeconds))
        self.assertEqual(['reserve', 'release'], [c[0] for c in rig.houses.calls])
        self.assertNotIn('commit', [c[0] for c in rig.houses.calls])


class CombatAbortPolicy(unittest.TestCase):
    def test_combat_holds_then_aborts_after_the_survey_seconds_with_a_clue(self):
        rig = Rig()
        survey = rig.survey
        rig.tick()
        rig.port.pos = (10.0, 0.0, 0.0)
        rig.tick(1)
        rig.port.combat = True
        walks = len(rig.port.walks)
        self.assertEqual('HOLD', rig.tick(1))
        self.assertEqual('HOLD', rig.tick(survey.RunCombatAbortSeconds - 2))
        self.assertEqual(walks, len(rig.port.walks), 'no new movement while fighting')
        self.assertNotIn('commit', [c[0] for c in rig.houses.calls], 'no transfer while fighting')
        self.assertEqual('RUN_ABORT_COMBAT', rig.tick(2))
        self.assertEqual('release', rig.houses.calls[-1][0], 'reservation released on abort')
        self.assertEqual('PICKER_ROUTE_DANGER_COMBAT', danger_for(rig))
        self.assertEqual(1, len(rig.lines('run end')))

    def test_short_combat_that_ends_resets_the_timer(self):
        rig = Rig()
        rig.tick()
        rig.port.combat = True
        rig.tick(5)
        rig.port.combat = False
        rig.tick(1)
        self.assertEqual(-1, rig.runner.CombatSince)
        rig.port.combat = True
        self.assertEqual('HOLD', rig.tick(rig.survey.RunCombatAbortSeconds - 1))

    def test_a_party_below_the_minimum_ends_the_run_and_remembers_a_loss(self):
        rig = Rig()
        rig.tick()
        rig.port.members = rig.survey.RunMinMembers - 1
        self.assertEqual('RUN_ABORT_PARTY_BROKEN', rig.tick(1))
        self.assertEqual('PICKER_ROUTE_DANGER_LOSS', danger_for(rig))

    def test_unknown_membership_never_aborts(self):
        rig = Rig()
        rig.port.members = -1
        self.assertNotEqual('RUN_ABORT_PARTY_BROKEN', rig.tick())

    def test_opt_out_file_leaves_the_existing_single_item_trip_alone(self):
        native = h.Native()
        native.opted_out = True
        rig = Rig(native=native)
        rig.port.combat = True
        self.assertEqual('', rig.tick(1000))
        self.assertEqual([], rig.houses.calls)


class TripStepKeepsCustody(unittest.TestCase):
    """The real HCStep over the real runner: an abort is a plain loss, cargo stays put."""
    def fixture(self, rig):
        state = N(Version=1, Phase=EStr('leaving'), PartyId=EStr('party'), CargoId=EStr('cargo'), Generation=1,
                  LeaseId=EStr('lease'), SourceId=EStr('source'), ActorId=EStr('actor'), HomeId=EStr('home'),
                  ItemId=EStr('item'), CargoOwner=EStr('source'), Refusal=EStr(''), RouteId=EStr('route:r1'))
        saved, moves = [], []
        port = rig.port
        port.HCOwner = lambda: EStr('source')
        port.HCAtHome = lambda: False
        port.HCMove = lambda returning, row: moves.append(returning)
        port.HCRunHold = lambda returning, row: rig.runner.HCRun(port, returning, row)
        trip = N(m_State=state, m_IO=port, m_Ready=True, m_Busy=False, HCLog=lambda: None,
                 HCCheckpoint=lambda: saved.append(deepcopy(state)) or True)
        source = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', PICKERS.read_text())
        env = dict(HCPickRunner=N(HOLD=EStr('HOLD')))
        translate(source, 'HCScavengeTrip', env, only=('HCStep', 'HCLose'))
        for name in ('HCStep', 'HCLose'):
            setattr(trip, name, MethodType(env[name], trip))
        trip.HCLose.__func__.__globals__['HCPickRunner'] = env['HCPickRunner']
        return trip, state, saved, moves

    def test_hold_does_nothing_and_abort_loses_the_trip_without_moving_cargo(self):
        rig = Rig()
        trip, state, saved, moves = self.fixture(rig)
        trip.HCStep()
        self.assertEqual('leaving', state.Phase, 'house stage holds the leg')
        rig.port.combat = True
        trip.HCStep()
        rig.native.tick += rig.survey.RunCombatAbortSeconds
        trip.HCStep()
        self.assertEqual(('lost', 'RUN_ABORT_COMBAT'), (str(state.Phase), str(state.Refusal)))
        self.assertEqual('source', state.CargoOwner, 'cargo stays with its real owner, nothing deleted or refunded')
        self.assertEqual([], moves, 'no custody move was attempted')
        self.assertEqual('lost', saved[-1].Phase, 'loss is checkpointed through the existing journal')

    def test_a_normal_run_still_acquires_after_the_house_stage(self):
        rig = Rig(houses=FakeHouses(refusal='PICKER_HOUSE_PORT_UNBOUND'))
        trip, state, saved, moves = self.fixture(rig)
        trip.HCStep()
        self.assertEqual([False], moves, 'unbound house port keeps the vanilla acquire behaviour')


if __name__ == '__main__':
    unittest.main()
