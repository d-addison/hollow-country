"""SearchDensityScale < 1 trims the legacy interior pilot instead of rejecting it (#190 P2).

The scaled MaxActiveInteriors can fall below the manifest candidate count. The
authored trim helper runs through the restricted member translator; the source
scans bind ValidateConfig to it. Synthetic fixtures only; offline tests never
establish DayZ behavior.
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from tests.legacy.test_group_server import EArray, execute_member

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'mods/HollowCountry/scripts/4_World/Interiors/HCInteriorModule.c'
DOCS = ROOT / 'docs/FRIEND_SERVER.md'


def native_text(source):
    return re.sub(r'(\w+)\.ToString\(\)', r'str(\1)', source)


class InteriorDensityTrimTests(unittest.TestCase):
    def trim(self, count, cap):
        source = native_text(MODULE.read_text())
        logs = []
        candidates = EArray(NS(SlotId=slot) for slot in range(count))
        module = NS()
        dropped = execute_member(source, 'HCTrimCandidatesToCap', dict(Print=logs.append), module, candidates, cap)
        return candidates, dropped, logs

    def test_cap_below_candidate_count_keeps_lowest_slots_and_logs_count(self):
        candidates, dropped, logs = self.trim(5, 2)
        self.assertEqual([0, 1], [row.SlotId for row in candidates])
        self.assertEqual(3, dropped)
        self.assertEqual(1, len(logs))
        for token in ('kept=2', 'dropped=3', 'cap=2', 'runtime=PENDING'):
            self.assertIn(token, logs[0])

    def test_cap_at_or_above_candidate_count_changes_nothing_and_is_silent(self):
        for count, cap in ((1, 1), (1, 6), (12, 12)):
            with self.subTest(count=count, cap=cap):
                candidates, dropped, logs = self.trim(count, cap)
                self.assertEqual(count, len(candidates))
                self.assertEqual(0, dropped)
                self.assertEqual([], logs)

    def test_validate_config_trims_after_stable_sort_and_no_longer_rejects_on_the_cap(self):
        text = MODULE.read_text()
        start = text.index('bool ValidateConfig(')
        body = text[start:text.index('HCInteriorManifest AllocateManifest', start)]
        self.assertNotIn('Count() > settings.HCSearchCap("MaxActiveInteriors"', body)
        self.assertIn('HCTrimCandidatesToCap(sorted, settings.HCSearchCap("MaxActiveInteriors", settings.MaxActiveInteriors))', body)
        self.assertLess(body.index('sorted.Insert(candidate)'), body.index('HCTrimCandidatesToCap('))
        # Startup work is judged on the trimmed list, never the pre-trim count.
        self.assertLess(body.index('HCTrimCandidatesToCap('), body.index('MaxTickWorkItems'))

    def test_friend_doc_explains_trim_and_the_scale_above_one_ceiling(self):
        text = ' '.join(DOCS.read_text().split())
        self.assertIn('trims the legacy pilot', text)
        self.assertIn('hard-cap', text)
        self.assertIn('barely changes interiors', text)


if __name__ == '__main__':
    unittest.main()
