"""#212 selection regression: authored policy, explicit synthetic claims/scans.
Offline translation supplies no DayZ visibility, inventory or runtime evidence.
"""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from tests.unit.test_admin_test_kit import Cell, base_scope, compile_authored
from tests.unit.test_group_server import EArray
from tests.unit.test_w57_claimtargets import ADMIN, CAMPS, NOW, anchor, claim, policy_scope


class ClaimSelection(unittest.TestCase):
    def build(self, visit=(0, 0), probe=(0, 0), hidden=(False, False), cap=32, budget=True):
        rows = EArray([claim(1, 10), claim(2, 20)])
        for index, row in enumerate(rows):
            row.Anchor = anchor()
            row.Anchor.AnchorKind = 'claim'
            row.Anchor.Position = row.Position
            row.Anchor.LastVisit = visit[index]
            row.Anchor.LastProbe = probe[index]
        scans = [NS(Storage=True, Hidden=lambda burning, value=value: value) for value in hidden]
        owner = NS(m_Running=True, m_LastUtc=NOW, m_Data=NS(Camps=EArray(), Claims=rows))
        self.scanned, self.reserved = [], []
        def scan(candidate, reason, budgeted):
            index = next(i for i, row in enumerate(rows) if row.Anchor is candidate)
            self.scanned.append((index, budgeted))
            return scans[index]
        def reserve(count, reason):
            self.reserved.append(count)
            reason.value = 'CLAIM_SELECTION_WORK_BUDGET'
            return budget
        owner.HCReadClaimScan = scan
        owner.HCReserveClaimSelection = reserve
        owner.HCEncounterCount = lambda: len(rows)
        owner.HCEncounterTarget = lambda index, now: rows[index].Anchor
        scope = base_scope(HCAILimits=NS(Get=lambda: NS(MaxCamps=cap)),
                           HCWorldClock=NS(UTC=lambda: NOW), HCCampProbes=policy_scope())
        fn = compile_authored(ADMIN, 'HCCampModule', 'HCAdminSelectCamp', scope,
            ('HCEncounterCount', 'HCEncounterTarget', 'HCReadClaimScan', 'HCReserveClaimSelection'))
        owner.HCAdminSelectCamp = lambda pos, reason, kind: fn(owner, pos, reason, kind)
        return owner, rows, fn

    def test_nearer_visit_cooldown_does_not_mask_farther_claim(self):
        owner, rows, fn = self.build(visit=(NOW, 0), probe=(0, NOW))
        self.assertIs(rows[1].Anchor, fn(owner, (0, 0, 0), Cell(), 1))
        self.assertIs(owner.m_ClaimSelectionTarget, rows[1].Anchor)
        self.assertEqual([(0, True), (1, True)], self.scanned)
        self.assertEqual([2], self.reserved)

    def test_nearer_probe_cooldown_does_not_mask_farther_claim(self):
        owner, rows, fn = self.build(visit=(0, NOW), probe=(NOW, 0))
        self.assertIs(rows[1].Anchor, fn(owner, (0, 0, 0), Cell(), 2))

    def test_both_cooling_down_have_kind_specific_named_refusal(self):
        for kind, expected in ((1, 'CLAIM_VISIT_COOLDOWN'), (2, 'CLAIM_PROBE_COOLDOWN')):
            with self.subTest(kind=kind):
                owner, _, fn = self.build(visit=(NOW, NOW), probe=(NOW, NOW))
                reason = Cell()
                self.assertIsNone(fn(owner, (0, 0, 0), reason, kind))
                self.assertEqual(expected, reason.value)
                self.assertIsNone(owner.m_ClaimSelectionTarget)

    def test_hidden_nearer_claim_does_not_mask_farther_claim(self):
        owner, rows, fn = self.build(hidden=(True, False))
        self.assertIs(rows[1].Anchor, fn(owner, (0, 0, 0), Cell(), 1))

    def test_caps_and_budget_refuse_before_scanning(self):
        for options, expected in ((dict(cap=1), 'claim-configured-cap-exceeded'),
                                  (dict(budget=False), 'CLAIM_SELECTION_WORK_BUDGET')):
            owner, _, fn = self.build(**options)
            reason = Cell()
            self.assertIsNone(fn(owner, (0, 0, 0), reason, 1))
            self.assertEqual(expected, reason.value)
            self.assertEqual([], self.scanned)

    def test_arrival_passes_kind_to_selection_and_preserves_cooldowns(self):
        for raid in (False, True):
            owner, rows, _ = self.build(visit=(NOW, 0), probe=(NOW, 0))
            calls = []
            owner.HCAdminRequestArrival = lambda target, kind, reason: calls.append((target, kind)) or True
            arrival = compile_authored(ADMIN, 'HCCampModule', 'HCAdminArrival', base_scope(),
                                      ('HCAdminSelectCamp', 'HCAdminRequestArrival'))
            self.assertTrue(arrival(owner, (0, 0, 0), raid, Cell()))
            self.assertEqual([(rows[1].Anchor, raid)], calls)
            self.assertEqual((NOW, NOW), (rows[0].Anchor.LastVisit, rows[0].Anchor.LastProbe))

