"""Owner revisit smoke: authored timing policy, SYNTHETIC UTC/ids, no engine proof.

Scope: EnableWorld search-state refresh; existing CE handles remain the supply.
This uses the existing source-method runner without extending its translator.
"""
import json
import unittest
from types import SimpleNamespace

from tests.unit.test_search_economy import invoke


class SyntheticId(str):
    def Length(self):
        return len(self)


class LootRefreshSmoke(unittest.TestCase):
    def test_revisit_after_jittered_real_days_survives_timestamp_roundtrip(self):
        intervals = set()
        for number in range(32):
            site = SyntheticId("synthetic_house_site_" + str(number))
            interval = invoke("HCSearchRefresh.c", "Interval", {}, None, site)
            intervals.add(interval)
            self.assertGreaterEqual(interval, 2 * 86400)
            self.assertLessEqual(interval, 4 * 86400)
            self.assertEqual(interval, invoke("HCSearchRefresh.c", "Interval", {}, None, site))
            # Explicit synthetic persisted timestamp; downtime uses UTC, not game time.
            record = json.loads(json.dumps({"SearchedUtc": 1_800_000_000}))
            searched = record["SearchedUtc"]
            def due(now):
                return invoke("HCSearchRefresh.c", "Due", {}, SimpleNamespace(), searched, now, interval)
            self.assertFalse(due(searched + 86400))
            self.assertFalse(due(searched + interval - 1))
            self.assertTrue(due(searched + interval))
            self.assertTrue(due(searched + 5 * 86400))
            self.assertFalse(due(searched - 1))
        self.assertGreater(len(intervals), 1)
