"""Search must never spin and stop without a reason (owner playtest 2026-11-18, synthetic fixtures).

On the friend's server "Search storage" showed on cabinets, the progress ring cycled once and
nothing happened. Two silent paths caused it:
  1. The client previewed every legacy pilot cabinet class (HCInteriorCatalog.SearchType), and
     template furnishing places those classes in every furnished building, but the server pilot
     only knows its own sites and grants nothing before acceptance, so it refused silently.
  2. House search refusals (service not ready, busy site, capacity, journal) told nobody.
These tests run authored Enforce through the existing translators; they are not DayZ proof.
"""
import unittest
from types import SimpleNamespace as N

from tests.legacy import test_search_economy_houses as houses
from tests.legacy import test_search_preview_sites as preview
from tests.legacy.test_search_economy_houses import FakeAction, FakeHouse, FakeTarget, site_world, SITE_A


class HouseRefusalTests(houses.HouseCase):
    def far_attempt(self):
        house = self.h.house()
        player = self.h.player()
        self.h.food(1, site_world(house, SITE_A))
        # 2.6 m from the site centre: the server geometry refuses.
        action = self.h.action(player, house, [0., 1., 0.], [0., 1., 2.6])
        return house, player, action

    def test_server_refusal_tells_the_player_why_once_per_window(self):
        _, player, action = self.far_attempt()
        self.assertFalse(self.h.hook.CanStart(player, action.m_Target))
        self.assertEqual(['Nothing to search at this spot.'], player.messages)
        self.assertFalse(self.h.hook.CanStart(player, action.m_Target))
        self.assertEqual(1, len(player.messages), 'refusal message must be rate limited')
        self.h.world.now += 5.1
        self.assertFalse(self.h.hook.CanStart(player, action.m_Target))
        self.assertEqual(2, len(player.messages))

    def test_refusal_is_logged_with_reason_and_class_but_no_player_id(self):
        _, player, action = self.far_attempt()
        self.h.hook.CanStart(player, action.m_Target)
        lines = [line for line in self.h.rt.log if 'refused reason=' in str(line)]
        self.assertEqual(1, len(lines), self.h.rt.log)
        self.assertIn('reason=no_site', lines[0])
        self.assertIn('class=' + houses.SYNTH, lines[0])
        self.assertNotIn('actor_a', lines[0])

    def test_busy_site_tells_the_second_player(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        first = self.h.player('actor_a')
        self.h.houses.Begin(self.h.action(first, house, [0., 1., 0.], [0., 1., 1.]))
        self.assertEqual(1, self.h.houses.SessionCount())
        second = self.h.player('actor_b')
        action = self.h.action(second, house, [0., 1., 0.], [0., 1., 1.])
        self.assertFalse(self.h.hook.CanStart(second, action.m_Target))
        self.assertEqual(['Someone is already searching here.'], second.messages)

    def test_service_fault_tells_the_player(self):
        _, player, action = self.far_attempt()
        player.position = list(action.m_Target.GetObject().ModelToWorld([0., 1., 1.]))
        self.h.houses.m_Fault = True
        self.assertFalse(self.h.hook.CanStart(player, action.m_Target))
        self.assertEqual(['Search unavailable: the search service is not ready on this server.'], player.messages)
        self.assertIn('reason=service', ' '.join(str(line) for line in self.h.rt.log))

    def test_begin_without_a_session_is_never_silent(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        player = self.h.player()
        action = self.h.action(player, house, [0., 1., 0.], [0., 1., 1.])
        self.assertTrue(self.h.hook.CanStart(player, action.m_Target))
        self.h.houses.m_Fault = True  # The journal failed between the start check and Begin.
        self.h.hook.BeginSearch(action)
        self.assertEqual(0, self.h.houses.SessionCount())
        self.assertEqual(1, len(player.messages), 'a Begin that opens no session must say why')

    def test_different_reason_in_same_window_is_reported(self):
        _, player, action = self.far_attempt()
        self.assertFalse(self.h.hook.CanStart(player, action.m_Target))
        self.h.houses.m_Fault = True
        self.assertFalse(self.h.hook.CanStart(player, action.m_Target))
        self.assertEqual(2, len(player.messages))
        lines = [line for line in self.h.rt.log if 'refused reason=' in str(line)]
        self.assertEqual(2, len(lines))

    def test_admitted_start_says_nothing(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        player = self.h.player()
        action = self.h.action(player, house, [0., 1., 0.], [0., 1., 1.])
        self.assertTrue(self.h.hook.CanStart(player, action.m_Target))
        self.assertEqual([], player.messages)


class PilotCabinetPreviewTests(unittest.TestCase):
    def harness(self, accepted):
        h = preview.Harness(self)
        rules = h.env['HCInteriorRules']
        h.env['HCInteriorRules'] = N(**{**vars(rules), 'SearchAccepted': lambda: accepted})
        catalog = houses.Harness().pilot_types
        h.env['HCInteriorCatalog'] = N(SearchType=lambda cls: cls in catalog)
        cabinet = FakeHouse('StaticObj_Furniture_case_a', [100., 0., 100.])
        target = FakeTarget(cabinet, [100., 1., 100.5])
        target.GetComponentIndex = lambda: 0
        return h, target

    def test_furnished_cabinet_does_not_offer_search_before_pilot_acceptance(self):
        h, target = self.harness(False)
        self.assertFalse(h.preview(target), 'the server grants nothing here; the client must not promise a search')

    def test_accepted_pilot_cabinet_still_previews_by_reach(self):
        h, target = self.harness(True)
        self.assertTrue(h.preview(target))


if __name__ == '__main__':
    unittest.main()
