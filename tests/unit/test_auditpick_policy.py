"""#144 scavenging runs / #150 season-aware camp needs: authored HCPickPolicy and HCPickDanger.

Behavioural over explicit SYNTHETIC fakes (translator syntax only). Offline tests never
establish DayZ behaviour; runtime acceptance is PENDING.

TDD receipt (2026-11-19):
RED:  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_auditpick_policy -v  (before World/auditpick_*.c existed)
      FileNotFoundError: .../World/auditpick_Policy.c (module import of the harness fails)
GREEN: same command, all tests OK.
"""
import re
import unittest

from tests.unit.test_map_layers import EStr
from tests.unit import test_auditpick_harness as h


def route(survey, index=0):
    return survey.Routes[index]


class NeedAndSeason(unittest.TestCase):
    def setUp(self):
        self.native = h.Native()
        self.policy = h.policy(self.native)
        self.survey = h.shipped_survey()

    def test_need_target_scales_with_the_season_phase(self):
        s = self.survey
        base = s.RunNeedStashItems
        for phase, pct in ((0, s.RunNeedPercentSpring), (1, s.RunNeedPercentSummer),
                           (2, s.RunNeedPercentAutumn), (3, s.RunNeedPercentWinter)):
            self.assertEqual(base * pct // 100, self.policy.NeedTarget(s, phase), phase)
        self.assertGreater(self.policy.NeedTarget(s, 3), self.policy.NeedTarget(s, 1), 'winter wants more than summer')

    def test_unavailable_phase_keeps_the_neutral_scale(self):
        self.assertEqual(self.survey.RunNeedStashItems, self.policy.NeedTarget(self.survey, -1))

    def test_a_run_needs_a_stash_below_the_seasonal_target_and_never_on_a_guess(self):
        s = self.survey
        winter = self.policy.NeedTarget(s, 3)
        summer = self.policy.NeedTarget(s, 1)
        self.assertTrue(self.policy.NeedsSupplies(s, winter - 1, 3))
        self.assertFalse(self.policy.NeedsSupplies(s, winter, 3))
        # The same stash is enough in summer but short in winter.
        self.assertFalse(self.policy.NeedsSupplies(s, summer, 1))
        self.assertTrue(self.policy.NeedsSupplies(s, summer, 3))
        self.assertFalse(self.policy.NeedsSupplies(s, -1, 3), 'unreadable stash claims no need')

    def test_season_phase_is_a_read_only_query_of_the_weather_owner(self):
        self.native.season = 2
        self.assertEqual(2, self.policy.SeasonPhase())
        self.assertEqual(['phase'], self.native.weather_calls)
        self.native.weather = False
        self.assertEqual(-1, self.policy.SeasonPhase(), 'no weather authority is unavailable, not spring')

    def test_source_only_calls_the_read_accessor(self):
        text = h.POLICY.read_text()
        self.assertIn('HCSeasonPhaseCode()', text)
        for banned in ('SetPhase', 'HCAdvance', 'HCSetSeason', 'HCStep(', 'OnTick'):
            self.assertNotIn(banned, text)


class PartyBoundsAndCaps(unittest.TestCase):
    def setUp(self):
        self.policy = h.policy()
        self.survey = h.shipped_survey()

    def test_two_to_four_members_are_admitted(self):
        for members in (2, 3, 4):
            self.assertEqual('', self.policy.PartyRefusal(self.survey, members), members)
        self.assertEqual('PICKER_PARTY_TOO_SMALL', self.policy.PartyRefusal(self.survey, 1))
        self.assertEqual('PICKER_PARTY_TOO_LARGE', self.policy.PartyRefusal(self.survey, 5))
        self.assertEqual('PICKER_PARTY_TOO_LARGE', self.policy.PartyRefusal(self.survey, 6))

    def test_bounds_come_from_the_survey_not_the_code(self):
        survey = h.shipped_survey(RunMinMembers=3, RunMaxMembers=3)
        self.assertEqual('PICKER_PARTY_TOO_SMALL', self.policy.PartyRefusal(survey, 2))
        self.assertEqual('', self.policy.PartyRefusal(survey, 3))
        self.assertEqual('PICKER_PARTY_TOO_LARGE', self.policy.PartyRefusal(survey, 4))

    def test_named_world_and_camp_caps(self):
        r = route(self.survey)
        self.assertEqual('', self.policy.CapRefusal(self.survey, r, 0, 0))
        self.assertEqual('PICKER_WORLD_RUN_CAP', self.policy.CapRefusal(self.survey, r, self.survey.RunMaxActiveRuns, 0))
        self.assertEqual('PICKER_CAMP_PARTY_CAP', self.policy.CapRefusal(self.survey, r, 0, self.survey.RunMaxPartiesPerCamp))

    def test_active_phases_count_as_runs(self):
        for phase in ('leaving', 'returning', 'acquiring', 'depositing'):
            self.assertTrue(self.policy.ActiveTrip(phase), phase)
        for phase in ('idle', 'returned', 'lost', 'quarantined'):
            self.assertFalse(self.policy.ActiveTrip(phase), phase)


class SurveyRunFields(unittest.TestCase):
    def setUp(self):
        self.policy = h.policy()

    def test_the_shipped_survey_is_usable(self):
        self.assertEqual('', self.policy.RunRefusal(h.shipped_survey()))

    def test_each_defect_is_named(self):
        cases = (
            ('PICKER_SURVEY_RUN_MEMBERS', dict(RunMinMembers=0)),
            ('PICKER_SURVEY_RUN_MEMBERS', dict(RunMinMembers=5, RunMaxMembers=4)),
            ('PICKER_SURVEY_RUN_HOUSES', dict(RunMaxHousesPerRun=7, RunMaxHouseAttempts=6)),
            ('PICKER_SURVEY_RUN_HOUSES', dict(RunMaxHouseCandidates=0)),
            ('PICKER_SURVEY_RUN_HOUSES', dict(RunMaxHouseCandidates=129)),
            ('PICKER_SURVEY_RUN_HOUSES', dict(RunHouseSearchRadiusMeters=0.0)),
            ('PICKER_SURVEY_RUN_HOUSES', dict(RunHouseSearchRadiusMeters=401.0)),
            ('PICKER_SURVEY_RUN_HOUSES', dict(RunHouseSearchSeconds=0.0)),
            ('PICKER_SURVEY_RUN_HOUSES', dict(RunHouseWalkSeconds=6.0)),
            ('PICKER_SURVEY_RUN_NEED', dict(RunNeedStashItems=0)),
            ('PICKER_SURVEY_RUN_NEED', dict(RunNeedRecheckSeconds=0)),
            ('PICKER_SURVEY_RUN_NEED', dict(RunNeedPercentWinter=0)),
            ('PICKER_SURVEY_RUN_NEED_BEYOND_SCAN', dict(RunNeedStashItems=11)),
            ('PICKER_SURVEY_RUN_DANGER', dict(RunDangerHeatAvoid=0.0)),
            ('PICKER_SURVEY_RUN_DANGER', dict(RunDangerHeatAvoid=1.5)),
            ('PICKER_SURVEY_RUN_DANGER', dict(RunDangerClueSeconds=0)),
            ('PICKER_SURVEY_RUN_DANGER', dict(RunCombatAbortSeconds=0)),
            ('PICKER_SURVEY_RUN_CAPS', dict(RunMaxActiveRuns=0)),
            ('PICKER_SURVEY_RUN_CAPS', dict(RunMaxPartiesPerCamp=0)),
        )
        for expected, changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(expected, self.policy.RunRefusal(h.shipped_survey(**changes)))

    def test_two_routes_in_one_camp_exceed_the_per_camp_cap(self):
        survey = h.shipped_survey()
        survey.Routes[1].LocalityId = survey.Routes[0].LocalityId
        self.assertEqual('PICKER_SURVEY_CAMP_PARTY_CAP', self.policy.RunRefusal(survey))
        survey = h.shipped_survey(RunMaxPartiesPerCamp=2)
        survey.Routes[1].LocalityId = survey.Routes[0].LocalityId
        self.assertEqual('', self.policy.RunRefusal(survey))

    def test_opt_out_file_turns_the_runs_off(self):
        native = h.Native()
        policy = h.policy(native)
        self.assertTrue(policy.Enabled())
        native.opted_out = True
        self.assertFalse(policy.Enabled())


class RemembersDangerFromClues(unittest.TestCase):
    def setUp(self):
        self.native = h.Native()
        self.policy = h.policy(self.native)
        self.survey = h.shipped_survey()
        self.danger = h.danger()
        self.route = route(self.survey)

    def verdict(self, now):
        return self.policy.RouteDanger(self.survey, self.danger, self.route, now)

    def test_a_fresh_own_clue_refuses_then_expires(self):
        s = self.survey
        self.assertEqual('', self.verdict(1000))
        self.danger.HCNote(EStr(self.route.RouteId), EStr('COMBAT'), 1000, s.RunDangerClueSeconds, s.RunDangerMaxClues)
        self.assertEqual('PICKER_ROUTE_DANGER_COMBAT', self.verdict(1000 + s.RunDangerClueSeconds - 1))
        self.assertEqual('', self.verdict(1000 + s.RunDangerClueSeconds), 'danger memory expires')

    def test_a_clue_on_another_route_does_not_close_this_one(self):
        s = self.survey
        self.danger.HCNote(EStr('route:elsewhere'), EStr('LOSS'), 1000, s.RunDangerClueSeconds, s.RunDangerMaxClues)
        self.assertEqual('', self.verdict(1001))

    def test_remembered_noise_at_a_waypoint_refuses_below_threshold_it_does_not(self):
        point = self.route.Waypoints[2]
        self.native.heat[(point.X, point.Y, point.Z)] = self.survey.RunDangerHeatAvoid - 0.01
        self.assertEqual('', self.verdict(1000))
        self.native.heat[(point.X, point.Y, point.Z)] = self.survey.RunDangerHeatAvoid
        self.assertEqual('PICKER_ROUTE_DANGER_NOISE', self.verdict(1000))

    def test_clue_table_is_capped_and_repeats_refresh_in_place(self):
        s = self.survey
        for index in range(s.RunDangerMaxClues + 5):
            self.danger.HCNote(EStr('route:r%d' % index), EStr('LOSS'), 1000 + index, s.RunDangerClueSeconds, s.RunDangerMaxClues)
        self.assertEqual(s.RunDangerMaxClues, self.danger.HCCount())
        self.assertEqual('', self.danger.HCFresh(EStr('route:r0'), 1100, s.RunDangerClueSeconds), 'oldest clue dropped')
        before = self.danger.HCCount()
        self.danger.HCNote(EStr('route:r20'), EStr('LOSS'), 1500, s.RunDangerClueSeconds, s.RunDangerMaxClues)
        self.assertEqual(before, self.danger.HCCount())

    def test_deferred_refusals_rearm_on_the_recheck_interval(self):
        for refusal in ('PICKER_NO_SUPPLY_NEED', 'PICKER_ROUTE_DANGER_COMBAT', 'PICKER_ROUTE_DANGER_NOISE'):
            self.assertTrue(self.policy.Deferred(EStr(refusal)), refusal)
        for refusal in ('PICKER_PARTY_COOLDOWN', 'PICKER_TRIP_ACTIVE', ''):
            self.assertFalse(self.policy.Deferred(EStr(refusal)), refusal)

    def test_no_live_player_position_is_ever_read(self):
        # Danger memory is own clues + remembered noise cells only: the three authored
        # files never reach a player list, identity or live player position.
        for path in (h.POLICY, h.DANGER, h.HOUSES):
            text = re.sub(r'//[^\n]*', '', path.read_text())
            for banned in ('GetPlayers', 'HCPerfPlayers', 'GetIdentity', 'GetPlayer(', 'PlayerList'):
                self.assertNotIn(banned, text, path.name)


class ShippedFileGuards(unittest.TestCase):
    RUN_FIELDS = ('RunMinMembers', 'RunMaxMembers', 'RunMaxHousesPerRun', 'RunMaxHouseAttempts',
                  'RunMaxHouseCandidates', 'RunHouseSearchRadiusMeters', 'RunHouseSearchSeconds',
                  'RunHouseWalkSeconds', 'RunNeedStashItems', 'RunNeedPercentSpring', 'RunNeedPercentSummer',
                  'RunNeedPercentAutumn', 'RunNeedPercentWinter', 'RunNeedRecheckSeconds', 'RunDangerHeatAvoid',
                  'RunDangerClueSeconds', 'RunDangerMaxClues', 'RunCombatAbortSeconds', 'RunMaxPartiesPerCamp',
                  'RunMaxActiveRuns')

    def test_every_run_limit_is_present_and_a_missing_one_is_refused_by_the_loader_guard(self):
        import json
        from tests.unit.test_hc_pickers_survey import ShippedSurveyFieldPresence, SURVEY
        present = ShippedSurveyFieldPresence.present()
        data = json.loads(SURVEY.read_text())
        for field in self.RUN_FIELDS:
            self.assertIn(field, data, field)
        self.assertTrue(present(json.dumps(data, indent=2)))
        for field in self.RUN_FIELDS:
            broken = dict(data)
            del broken[field]
            self.assertFalse(present(json.dumps(broken, indent=2)), 'native zero-fill would hide ' + field)

    def test_loader_checks_the_run_limits_only_after_the_route_elements(self):
        text = h.PICKERS.read_text()
        load = text[text.index('static HCPickerSurvey HCLoad'):]
        self.assertLess(load.index('survey.HCRefusal()'), load.index('HCPickPolicy.RunRefusal(survey)'))


if __name__ == '__main__':
    unittest.main()
