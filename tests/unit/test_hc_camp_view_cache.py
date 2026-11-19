"""#190 camps: routine view cache and sentry refusal rate limit.

Synthetic ports execute the authored HCRoutineView/HCRefuse bodies. Nothing here
is DayZ evidence: native JSON cost, group/emote behaviour and log volume remain
runtime=PENDING.
"""
from types import SimpleNamespace as N
import unittest

from tests.unit.test_hc_ai_camps import authored_holdouts, synthetic_state
from tests.unit.test_hc_camp_followups import synthetic_routine


class SetList(list):
    def __bool__(self): return True
    def Insert(self, item): self.append(item)
    def Count(self): return len(self)
    def Set(self, index, item): self[index] = item


def view_fixture():
    state = synthetic_state()
    module, logs, writes, status, clock = authored_holdouts(state)
    module.m_Ready = True
    module.m_ViewHomes = SetList()
    module.m_ViewKeys = SetList()
    builds = []

    def snapshot(index):
        ledger = state.Rows[index].Ledger
        builds.append(index)
        return N(**vars(ledger))
    module.Snapshot = snapshot
    row = state.Rows[0]
    row.Ledger.FactionId = 'synthetic-faction'  # Explicit DTO fields the fixture omits.
    row.Ledger.CacheRef = 'synthetic-cache'
    identity = N(HCGeneration=lambda: 7, HCPartyId=lambda: row.Camp.Party,
                 HCCampId=lambda: 'camp:' + row.Ledger.Id,
                 HCHomeId=lambda: row.Ledger.PlaceId,
                 HCRouteId=lambda: 'stationary:' + row.Ledger.Id,
                 HCCargoId=lambda: 'cargo:' + row.Ledger.Id)
    return module, state, builds, identity


class RoutineViewCache(unittest.TestCase):
    def test_two_steps_without_a_row_change_build_the_snapshot_once(self):
        module, state, builds, identity = view_fixture()
        first = module.HCRoutineView(identity)
        second = module.HCRoutineView(identity)
        self.assertIsNotNone(first)
        self.assertEqual(1, len(builds), 'unchanged row must not rebuild the JSON snapshot')
        self.assertEqual(first.Home.Id, second.Home.Id)

    def test_every_row_change_the_view_exposes_invalidates_the_cache(self):
        module, state, builds, identity = view_fixture()
        module.HCRoutineView(identity)
        ledger = state.Rows[0].Ledger
        for field, value in (('State', 'ALERT'), ('Occupants', 2), ('Since', 5),
                             ('ReoccupyAfter', 9), ('Routine', 'LOCKOUT'),
                             ('CacheRef', 'other-cache'), ('HousePos', [2, 0, 2])):
            with self.subTest(field=field):
                before = len(builds)
                setattr(ledger, field, value)
                view = module.HCRoutineView(identity)
                self.assertEqual(before + 1, len(builds))
                self.assertEqual(value, getattr(view.Home, field))
                module.HCRoutineView(identity)
                self.assertEqual(before + 1, len(builds))

    def test_cache_is_bounded_by_the_row_count(self):
        module, state, builds, identity = view_fixture()
        for _ in range(5): module.HCRoutineView(identity)
        self.assertEqual(len(state.Rows), len(module.m_ViewHomes))
        self.assertEqual(len(state.Rows), len(module.m_ViewKeys))

    def test_failed_snapshot_is_not_cached(self):
        module, state, builds, identity = view_fixture()
        module.Snapshot = lambda index: builds.append(index)
        self.assertIsNone(module.HCRoutineView(identity))
        self.assertIsNone(module.HCRoutineView(identity))
        self.assertEqual(2, len(builds))


class SentryRefusalRateLimit(unittest.TestCase):
    def cycle(self, worker, flags, cfg, site):
        for _ in range(site.PatrolCount):
            worker.Step()
        flags.now += cfg.RoleSeconds
        worker.Step()  # Relief boundary.

    def test_refusal_logs_once_per_camp_until_the_reason_changes(self):
        worker, flags, site, view, requests, logs, reads, cfg = synthetic_routine()
        site.PatrolCount = 3
        for _ in range(8): self.cycle(worker, flags, cfg, site)
        sentry = [line for line in logs if 'ROUTINE_TARGET_CLEAR_UNAVAILABLE' in line and 'state=refused' in line]
        self.assertEqual(1, len(sentry), 'sentry refusal must not repeat every role cycle')
        self.assertGreaterEqual(len(requests), 8, 'rest role stays admitted')

    def test_changed_reason_logs_again_and_summary_is_bounded(self):
        worker, flags, site, view, requests, logs, reads, cfg = synthetic_routine()
        site.PatrolCount = 3
        for _ in range(60): self.cycle(worker, flags, cfg, site)
        summaries = [line for line in logs if 'refusal_repeats=' in line]
        self.assertGreaterEqual(len(summaries), 1)
        self.assertLessEqual(len(summaries), 6)
        self.assertTrue(all('ROUTINE_TARGET_CLEAR_UNAVAILABLE' in line for line in summaries))
        site.HCCampRefusal = 'OTHER'
        before = len(logs)
        self.cycle(worker, flags, cfg, site)
        self.assertTrue(any('ROUTINE_TARGET_CLEAR_UNAVAILABLE' in line and 'state=refused' in line
                            for line in logs[before:]))


if __name__ == '__main__':
    unittest.main()
