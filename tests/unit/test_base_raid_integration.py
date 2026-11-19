"""Lead integration of the warned base raid: budget id, registry, bundle, readiness.

Synthetic source checks only; nothing here establishes DayZ behavior.
"""
import json
import re
import unittest
from pathlib import Path

from tools.setup import friend_bundle
from tools.validate import settings_consistency as sc

ROOT = Path(__file__).resolve().parents[2]
BUDGET = ROOT / 'mods/HollowCountry/scripts/4_World/Core/HCUnitBudget.c'
RAID = ROOT / 'mods/HollowCountry/scripts/4_World/Camps/HCBaseRaid.c'


class BaseRaidIntegrationTests(unittest.TestCase):
    def test_base_raid_has_its_own_tick_budget_consumer(self):
        consts = dict(re.findall(r'static const int (HC_WORK_\w+) = (\d+);', BUDGET.read_text()))
        self.assertEqual('12', consts.get('HC_WORK_BASE_RAID'))
        self.assertEqual('13', consts['HC_WORK_CONSUMERS'])

    def test_base_raid_config_rows_are_registered_and_consistent(self):
        rows = {r['key']: r for r in json.loads(sc.REGISTRY.read_text()) if r['owner'] == 'HCBaseRaidConfig'}
        self.assertEqual(12, len(rows))
        self.assertEqual((300, 60, 600), tuple(rows['BaseRaid.WarningSeconds'][k] for k in ('default', 'min', 'max')))
        self.assertIn('HCBaseRaidConfig', sc.EXTERNAL_OWNERS)
        self.assertEqual([], sc.check_consistency())

    def test_registry_drift_in_a_raid_default_is_rejected(self):
        rows = json.loads(sc.REGISTRY.read_text())
        for row in rows:
            if row['key'] == 'BaseRaid.NoticeRangeMeters':
                row['default'] = 41
        self.assertIn('BaseRaid default/type differs for NoticeRangeMeters', sc.check_consistency(registry=rows))

    def test_friend_bundle_carries_camp_encounter_configs(self):
        for name in ('HollowCountry/base-raid-config.json', 'HollowCountry/camp-theft-config.json'):
            with self.subTest(name=name):
                self.assertIn(name, friend_bundle.PROFILE_INCLUDE)

    def test_readiness_is_off_when_the_parent_probe_feature_is_disabled(self):
        status = RAID.read_text().split('static HCOperationalStatus HCGetOperationalStatus()', 1)[1].split('static bool HCRecipients', 1)[0]
        self.assertIn('if (!HCCampProbes.HCEnabled()) { s_Status.HCPublish("off", "camp_probes_operator_disabled"); return s_Status; }', status)
        self.assertLess(status.index('HCCampProbes.HCEnabled()'), status.index('"ready"'))


if __name__ == '__main__':
    unittest.main()
