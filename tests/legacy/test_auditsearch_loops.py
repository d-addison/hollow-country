"""#197: execute the authored maintenance loops together, synthetic stock only."""
import unittest
from tests.legacy import test_hc_tick_budget_fixes as fixtures


class MaintenanceIsolationTests(unittest.TestCase):
    def test_recycle_and_compaction_each_progress_in_the_same_exhausted_tick(self):
        fixture = fixtures.HouseBudgetCase()
        fixture.with_refresh_mods()
        far = fixture.settled_houses(3)
        service = fixture.h.houses
        service.m_Journal.PruneLegacyTombstones = lambda limit: True
        budget = fixtures.spent_budget()
        fixtures.route_budget(fixture.h.env, budget)
        service.RecycleSpentBindings(far)
        self.assertEqual(2, len(service.m_Slots))
        service.CompactSettled()
        self.assertEqual(1, service.m_CompactNext, 'compaction starved behind active recycling')
        self.assertEqual(3, budget.HCStarved(), 'active, detached and compact each get their own forced unit')
        service.CompactSettled()
        self.assertEqual(1, service.m_CompactNext, 'same consumer cannot force a second unit')


if __name__ == '__main__':
    unittest.main()
