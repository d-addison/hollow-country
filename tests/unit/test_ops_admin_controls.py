"""Execute authored admin adapters with explicit synthetic service collaborators."""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from tests.unit.test_admin_test_kit import compile_authored, base_scope, Cell
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
DIRECTORS = ROOT / 'mods/HollowCountry/scripts/4_World/Admin/HCAdminDirectors.c'


class CampControls(unittest.TestCase):
    def run_tier(self, tier, commit=True, running=True):
        camp = NS(Tier=1)
        calls = []
        owner = NS(m_Running=running, HCAdminSelectCamp=lambda pos, reason: camp,
                   Commit=lambda now: calls.append(now) or commit)
        scope = base_scope(HCWorldClock=NS(UTC=lambda: 100))
        fn = compile_authored(DIRECTORS, 'HCCampModule', 'HCAdminTier', scope,
                              ('HCAdminSelectCamp', 'Commit'))
        reason = Cell()
        result = fn(owner, None, tier, reason)
        return result, reason.value, camp, calls

    def test_tier_uses_normal_commit_and_no_world_facts(self):
        result, reason, camp, calls = self.run_tier(3)
        self.assertTrue(result)
        self.assertEqual(camp.Tier, 3)
        self.assertEqual(calls, [100])
        self.assertIn('runtime=PENDING', reason)

    def test_invalid_tier_or_inactive_has_no_write(self):
        for tier, running in ((-1, True), (4, True), (3, False)):
            result, _, camp, calls = self.run_tier(tier, running=running)
            self.assertFalse(result)
            self.assertEqual(camp.Tier, 1)
            self.assertEqual(calls, [])

    def test_failed_commit_restores_in_memory_tier(self):
        result, reason, camp, calls = self.run_tier(3, commit=False)
        self.assertFalse(result)
        self.assertEqual(camp.Tier, 1)
        self.assertEqual(reason, 'camp-tier-persistence-refused')

    def test_arrivals_refuse_specific_missing_body_hook_without_world_mutation(self):
        for raid, expected in ((False, 'HCRequestVisitorParty'), (True, 'HCRequestRaidParty')):
            owner = NS(HCAdminSelectCamp=lambda pos, reason: NS())
            fn = compile_authored(DIRECTORS, 'HCCampModule', 'HCAdminArrival',
                                  base_scope(), ('HCAdminSelectCamp',))
            reason = Cell()
            self.assertFalse(fn(owner, None, raid, reason))
            self.assertIn(expected, reason.value)
            self.assertIn('runtime=PENDING', reason.value)

    def test_dormant_refuses_missing_transition_without_creating_body(self):
        fn = compile_authored(DIRECTORS, 'HCInfectedModule', 'HCAdminDormant', base_scope())
        reason = Cell()
        self.assertFalse(fn(NS(), None, reason))
        self.assertIn('HCRequestFreshDormant', reason.value)
        self.assertIn('runtime=PENDING', reason.value)


class CampSelection(unittest.TestCase):
    def test_nearest_scan_is_bounded_by_config_and_shared_work(self):
        camps = EArray([NS(Position=9), NS(Position=2)])
        for limit, credit, now, expected in ((2, 2, 100, camps[1]),
                                             (1, 2, 100, None),
                                             (2, 1, 100, None),
                                             (2, 2, 49, None)):
            remaining = [credit]
            def take(cost):
                remaining[0] -= cost
                return remaining[0] >= 0
            scope = base_scope(HCAILimits=NS(Get=lambda: NS(MaxCamps=limit)),
                               HCWorldClock=NS(UTC=lambda: now),
                               HCServer=NS(Get=lambda: NS(HCTickWork=lambda: NS(HCTake=take))),
                               vector=NS(DistanceSq=lambda a, b: (a-b)**2))
            fn = compile_authored(DIRECTORS, 'HCCampModule', 'HCAdminSelectCamp', scope)
            reason = Cell()
            owner = NS(m_Running=True, m_Data=NS(Camps=camps), m_LastUtc=50)
            self.assertIs(fn(owner, 0, reason), expected)


class CommandRouting(unittest.TestCase):
    def test_new_controls_use_owner_and_opt_out_without_bypassing_existing_queue(self):
        module = ROOT / 'mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c'
        calls = []
        camp = NS(HCAdminTier=lambda pos, value, reason: calls.append(('tier', value)) or True,
                  HCAdminArrival=lambda pos, raid, reason: calls.append(('arrival', raid)) or False)
        fn = compile_authored(module, 'HCAdminModule', 'HCOperatorCommand',
                              base_scope(HCCampModule=NS(Get=lambda: camp)), modded=False)
        owner = NS(m_OperatorControls=True)
        reason = Cell()
        self.assertTrue(fn(owner, None, 'camptier', 3, reason))
        self.assertFalse(fn(owner, None, 'campvisit', 0, reason))
        self.assertFalse(fn(owner, None, 'campraid', 0, reason))
        self.assertEqual(calls, [('tier', 3), ('arrival', False), ('arrival', True)])
        owner.m_OperatorControls = False
        calls.clear()
        self.assertFalse(fn(owner, None, 'camptier', 1, reason))
        self.assertEqual(reason.value, 'AdminControls.disable')
        self.assertEqual(calls, [])
        reason.value = 'module-unavailable'
        self.assertFalse(fn(owner, None, 'unknown', 0, reason))
        self.assertEqual(reason.value, 'module-unavailable')
