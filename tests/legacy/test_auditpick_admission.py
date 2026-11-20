"""#144/#150 admission: need gate with the season phase, route danger, caps and party size.

Executes the authored HCPickers.HCTryParty / HCBeginSurveyed / HCPartyRefusal and the lifecycle hook
over the existing SYNTHETIC picker fixtures (PickerStarts / PickerLifecycle). Nothing observes DayZ.

TDD receipt (2026-11-19):
RED:  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_auditpick_admission -v (source changes hidden)
GREEN: same command, all tests OK.
"""
import unittest
from types import SimpleNamespace as N

from tests.legacy import test_auditpick_harness as h
from tests.legacy.test_hc_picker_starts import PickerStarts, PickerLifecycle
from tests.legacy.test_hc_pickers_survey import method

PHASE_NAMES = {0: 'spring', 1: 'summer', 2: 'autumn', 3: 'winter'}


def runs_on(f, native, stash=None):
    """Turn the #144 gates on over the existing start fixture; returns the fixture."""
    module = f.module
    shipped = h.shipped_survey()
    for key, value in vars(shipped).items():
        if key.startswith('Run'):
            setattr(module.m_Survey, key, value)
    module.m_Survey.Routes = shipped.Routes
    module.m_RunsOn = True
    module.m_Danger = h.danger()
    policy = h.policy(native)
    scope = dict(HCPickPolicy=policy, GetGame=lambda: N(IsServer=lambda: True),
                 HCAIPartyIdentity=N(HCValid=lambda i: i is not None),
                 HCServer=N(HCTickWork=lambda: N(HCTake=lambda cost: True)),
                 vector=N(DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))),
                 HCSeasonVisualPolicy=N(HCPhaseName=lambda code: PHASE_NAMES.get(code, 'unavailable')),
                 Print=native.prints.append)
    begin = method('HCPickers', 'HCBeginSurveyed', members=('HCPublishReadiness',),
                   HCSearchSupplyRegistry=f.module.m_Trip.m_IO and N(PersistentId=lambda entity: 'id'), **scope)
    module.HCBeginSurveyed = lambda *a: begin(module, *a)
    try_party = method('HCPickers', 'HCTryParty', members=('HCBeginSurveyed',), **scope)
    module.HCTryParty = lambda *a: try_party(module, *a)
    if stash is not None:
        f.trip.m_IO.HCStashItems = lambda: stash[0]
    return f


class DangerAndCaps(unittest.TestCase):
    def setUp(self):
        self.native = h.Native()
        self.f = runs_on(PickerStarts().fixture(), self.native, [0])
        self.module = self.f.module
        self.route_id = str(self.f.identity.HCRouteId())

    def try_party(self, now=1000):
        return self.module.HCTryParty(self.f.identity, 'lease:synthetic', self.f.actor, now, 0)

    def test_a_remembered_clue_refuses_before_any_journal_write_then_expires(self):
        survey = self.module.m_Survey
        self.module.m_Danger.HCNote(h.EStr(self.route_id), h.EStr('COMBAT'), 1000, survey.RunDangerClueSeconds,
                                    survey.RunDangerMaxClues)
        self.assertEqual('PICKER_ROUTE_DANGER_COMBAT', self.try_party(1000))
        self.assertEqual([], self.f.effects, 'no clear, checkpoint or begin while the route is remembered as dangerous')
        self.assertEqual('', self.try_party(1000 + survey.RunDangerClueSeconds))

    def test_remembered_noise_on_the_route_refuses(self):
        route = self.module.m_Survey.HCFind(self.route_id)
        point = route.Waypoints[0]
        self.native.heat[(point.X, point.Y, point.Z)] = 1.0
        self.assertEqual('PICKER_ROUTE_DANGER_NOISE', self.try_party())
        self.assertEqual([], self.f.effects)

    def test_another_partys_live_run_is_named_by_the_world_cap(self):
        row = self.f.state
        row.Phase, row.PartyId, row.RouteId = 'returning', 'party:other', 'route:other'
        self.assertEqual('PICKER_WORLD_RUN_CAP', self.try_party())
        row.PartyId = self.f.identity.HCPartyId()
        self.assertEqual('PICKER_TRIP_ACTIVE', self.try_party(), 'the same party keeps the plain active refusal')

    def test_with_runs_off_nothing_changes(self):
        self.module.m_RunsOn = False
        self.module.m_Danger.HCNote(h.EStr(self.route_id), h.EStr('COMBAT'), 1000, 3600, 16)
        self.f.state.Phase, self.f.state.PartyId = 'returning', 'party:other'
        self.assertEqual('PICKER_TRIP_ACTIVE', self.try_party())
        self.f.state.Phase = 'idle'
        self.assertEqual('', self.try_party())


class NeedFollowsTheSeason(unittest.TestCase):
    def begin(self, stash, season):
        native = h.Native()
        native.season = season
        value = [stash]
        f = runs_on(PickerStarts().fixture(), native, value)
        result = f.module.HCTryParty(f.identity, 'lease:synthetic', f.actor, 1000, 0)
        return result, f, native

    def test_the_same_stash_is_enough_in_summer_and_short_in_winter(self):
        shipped = h.shipped_survey()
        summer = shipped.RunNeedStashItems * shipped.RunNeedPercentSummer // 100
        winter = shipped.RunNeedStashItems * shipped.RunNeedPercentWinter // 100
        self.assertLess(summer, winter)
        result, f, native = self.begin(summer, 1)
        self.assertEqual('PICKER_NO_SUPPLY_NEED', result)
        self.assertEqual([], [e for e in f.effects if isinstance(e, tuple)], 'no journal departure without a need')
        self.assertIn('clear', f.effects, 'the bound handles are released again')
        result, f, native = self.begin(summer, 3)
        self.assertEqual('', result)
        starts = [p for p in native.prints if 'run start' in p]
        self.assertEqual(1, len(starts))
        self.assertIn('season=winter', starts[0])
        self.assertIn('stash=%d' % summer, starts[0])
        self.assertIn('target=%d' % winter, starts[0])
        self.assertIn('runtime=PENDING', starts[0])

    def test_unavailable_season_keeps_the_neutral_target_and_unreadable_stash_never_runs(self):
        base = h.shipped_survey().RunNeedStashItems
        self.assertEqual('', self.begin(base - 1, -1)[0])
        self.assertEqual('PICKER_NO_SUPPLY_NEED', self.begin(base, -1)[0])
        self.assertEqual('PICKER_NO_SUPPLY_NEED', self.begin(-1, 3)[0])

    def test_opt_out_never_gates_on_need(self):
        native = h.Native()
        f = runs_on(PickerStarts().fixture(), native, [999])
        f.module.m_RunsOn = False
        self.assertEqual('', f.module.HCTryParty(f.identity, 'lease:synthetic', f.actor, 1000, 0))


class PartySizeAndRecheck(unittest.TestCase):
    def module(self, runs=True):
        survey = h.shipped_survey()
        module = N(m_Survey=survey, m_RunsOn=runs)
        policy = h.policy()
        part = method('HCPickers', 'HCPartyRefusal', HCPickPolicy=policy)
        recheck = method('HCPickers', 'HCRecheckSeconds')
        module.HCPartyRefusal = lambda members: part(module, members)
        module.HCRecheckSeconds = lambda: recheck(module)
        return module

    def test_member_bounds_and_the_recheck_interval_come_from_the_survey(self):
        module = self.module()
        self.assertEqual(['PICKER_PARTY_TOO_SMALL'] + [''] * 5 + ['PICKER_PARTY_TOO_LARGE'],
                         [str(module.HCPartyRefusal(count)) for count in range(1, 8)])
        self.assertEqual(module.m_Survey.RunNeedRecheckSeconds, module.HCRecheckSeconds())
        self.assertEqual('', self.module(False).HCPartyRefusal(1), 'opt-out leaves party size alone')

    def test_lifecycle_refuses_a_small_party_once_by_name_and_rearms_later(self):
        f = PickerLifecycle().fixture()
        f.f.module.m_RunsOn = True
        f.f.module.m_Survey = h.shipped_survey()
        module = self.module()
        f.f.module.HCPartyRefusal = module.HCPartyRefusal
        f.f.module.HCRecheckSeconds = module.HCRecheckSeconds
        f.f.step(1000)
        f.f.step(1001)
        self.assertEqual([], [e for e in f.f.effects if isinstance(e, tuple)])
        small = [line for line in f.logs if 'PICKER_PARTY_TOO_SMALL' in line]
        self.assertEqual(1, len(small), 'named once per change, not once per visit')
        self.assertEqual(1000 + module.m_Survey.RunNeedRecheckSeconds, f.state.HCPickerEligibleAt,
                         'the recheck is armed once, later visits inside it do not push it out')


if __name__ == '__main__':
    unittest.main()
