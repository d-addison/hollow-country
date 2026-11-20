"""#224: combined authored refresh/picker methods over explicit synthetic stock.

Native ports, UTC and persistence are fixture adapters; this proves no DayZ behavior.
HCSearchRefresh.c is outside this worker's write scope. The exact required guard
edit is applied ONLY to the local fixture copy below, pending lead integration.
"""
import unittest
from types import SimpleNamespace as N

from tests.legacy import test_auditsearch_reservations as reservations
from tests.legacy import test_hc_tick_budget_fixes as fixes
from tests.legacy import test_search_economy_houses as houses


class PickRefreshTests(unittest.TestCase):
    def setUp(self):
        self.h = reservations.install(houses.Harness())
        env = self.h.env
        self.refresh = fixes.RefreshHarness(rows=0, per_tick_pool=32)
        module = self.refresh.env['HCSearchRefreshModule']
        timer = self.refresh.module
        # Synthetic map out-parameter port (nested Key() exceeds the small
        # translator's map.Find adapter); no timing/readiness policy is replaced.
        def find_row(scope, site):
            index = timer.m_Index.get(timer.Key(scope, site))
            if not timer.Active() or index is None:
                return None
            return timer.m_State.Rows[index]
        timer.FindRow = find_row
        # Only default-argument syntax is adapted: the existing translator cannot
        # retain defaults. Mark dispatch still executes the authored timer owner.
        env['HCSearchRefreshModule'] = N(
            Mark=lambda scope, site, only=False: module.Mark(scope, fixes.SyntheticId(site), only),
            Ready=module.Ready, ForgetCompacted=module.ForgetCompacted)
        env['_Base_HCSearchHouses'] = env['HCSearchHouses']
        env['_Base_HCSearchHouseJournal'] = env['HCSearchHouseJournal']
        source = (houses.LOOT / 'HCSearchRefresh.c').read_text()
        # Exact requested integration edit, never mutate the out-of-scope source.
        source = source.replace('&& !SessionOfSite(hit.SiteId)',
                                '&& HCRefreshPreparationAllowed(hit, player)')
        for code in fixes.ModdedLinkTranslator(source, only=(
                'HCSearchHouses', 'HCSearchHouseJournal')).classes():
            exec(code, env)
        for name in ('HCSearchHouses', 'HCSearchHouseJournal'):
            fixes.HouseBudgetCase.chain_init(env[name], env['_Base_' + name])
        self.h.houses = env['HCSearchHouses']()
        self.h.houses.Start(self.h.settings)
        self.h.houses_binding.houses = self.h.houses
        self.house = self.h.house()
        self.actor = self.h.player('synthetic_ai')
        self.actor.GetIdentity = lambda: None
        self.actor.position = houses.site_world(self.house, houses.SITE_A)
        self.authority = N(HCValid=lambda actor, ident: actor is self.actor and ident == 'synthetic_party')
        self.first = self.h.food(1, houses.site_world(self.house, houses.SITE_A))

    def reserve(self):
        return self.h.houses.HCReservePicker(self.actor, self.house, 1, 'synthetic_party', self.authority)

    def commit(self, token):
        self.h.world.now += 6.5
        self.assertTrue(self.h.houses.HCCommitReservation(token))
        self.assertFalse(self.h.houses.HCCommitReservation(token))
        self.h.houses.HCReleasePicker(token)

    def exhaust_then_due(self):
        token = self.reserve()
        self.assertIsNotNone(token)
        self.commit(token)
        self.second = self.h.food(2, houses.site_world(self.house, houses.SITE_A))
        self.assertIsNone(self.reserve(), 'new stock must wait for the shared refresh timer')
        self.refresh.utc += 5 * 86400
        self.refresh.minute()

    def test_picker_revisit_refreshes_new_stock_once_and_keeps_contention_lock(self):
        self.exhaust_then_due()
        token = self.reserve()
        self.assertIsNotNone(token, 'owning provisional picker must be allowed to prepare due refresh')
        self.assertIs(self.second, self.h.houses.HCPickerItem(token))
        self.assertIsNone(self.reserve())
        human = self.h.player('human')
        action = self.h.action(human, self.house, [0., 1., 0.], [0., 1., 1.])
        self.h.houses.Begin(action)
        self.assertEqual(1, self.h.houses.SessionCount())
        self.commit(token)
        self.assertEqual([self.first, self.second], self.actor.cargo)
        self.assertEqual(2, len(self.h.moves()))
        self.assertIsNone(self.reserve())
        self.refresh.utc += 5 * 86400
        self.refresh.minute()
        self.assertIsNone(self.reserve(), 'refresh cannot rediscover already transferred stock')
        self.assertEqual(2, len(self.h.moves()))
        self.assertEqual([], self.h.rt.created)

    def test_refresh_ownership_excludes_other_actors_and_selected_rows(self):
        # Hold a real provisional reservation inside authored Prepare/preflight.
        original_prepare = self.h.houses.Prepare
        checks = []
        def prepare(slot, hit, actor):
            token = self.h.houses.SessionOfSite(hit.SiteId)
            self.assertEqual(-1, token.Row)
            checks.append(self.h.houses.HCRefreshPreparationAllowed(hit, actor))
            other = self.h.player('other')
            self.assertFalse(self.h.houses.HCRefreshPreparationAllowed(hit, other))
            self.assertFalse(self.h.houses.Admit(other, hit))
            valid = self.authority.HCValid
            self.authority.HCValid = lambda *args: False
            self.assertFalse(self.h.houses.HCRefreshPreparationAllowed(hit, actor))
            self.authority.HCValid = valid
            token.Row = 0
            self.assertFalse(self.h.houses.HCRefreshPreparationAllowed(hit, actor))
            token.Row = -1
            return original_prepare(slot, hit, actor)
        self.h.houses.Prepare = prepare
        token = self.reserve()
        self.assertIsNotNone(token)
        self.assertEqual([True], checks)
        hit = self.h.houses.HCResolvePicker(self.actor, self.house, 1)
        self.assertFalse(self.h.houses.HCRefreshPreparationAllowed(hit, self.actor))
        self.h.houses.HCReleasePicker(token)
        self.assertTrue(self.h.houses.HCRefreshPreparationAllowed(hit, self.actor))

    def test_human_revisit_keeps_the_same_refresh_behavior(self):
        self.exhaust_then_due()
        human = self.h.player('human')
        action = self.h.action(human, self.house, [0., 1., 0.], [0., 1., 1.])
        self.h.houses.Begin(action)
        self.assertEqual(1, self.h.houses.SessionCount())
        self.assertIsNone(self.reserve())
        self.h.world.now += 6.5
        self.h.houses.Commit(action)
        self.assertEqual([self.second], human.cargo)
        self.assertEqual(2, len(self.h.moves()))


if __name__ == '__main__':
    unittest.main()
