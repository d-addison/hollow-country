"""Lead integration of camp theft: one admission, shared status, registry rows.

Synthetic source checks only; nothing here establishes DayZ behavior.
"""
import json
import unittest
from pathlib import Path

from tools.validate import settings_consistency as sc

ROOT = Path(__file__).resolve().parents[2]


class CampTheftIntegrationTests(unittest.TestCase):



    def test_theft_config_rows_are_registered_and_consistent(self):
        rows = {r['key']: r for r in json.loads(sc.REGISTRY.read_text()) if r['owner'] == 'HCTheftConfig'}
        self.assertEqual(set(rows), {'CampTheft.Version', 'CampTheft.MaxAttemptsPerDay', 'CampTheft.MaxAttendancePlayers',
                                     'CampTheft.AttendanceRangeMeters', 'CampTheft.ObserverRangeMeters'})
        self.assertEqual((rows['CampTheft.MaxAttemptsPerDay']['default'], rows['CampTheft.MaxAttemptsPerDay']['max']), (1, 6))
        self.assertEqual(sc.check_consistency(), [])

    def test_registry_drift_in_theft_default_is_rejected(self):
        rows = json.loads(sc.REGISTRY.read_text())
        for row in rows:
            if row['key'] == 'CampTheft.ObserverRangeMeters':
                row['default'] = 600
        native = sc.NATIVE.read_text()
        errors = sc.check_consistency(registry=rows, native=native)
        self.assertIn('CampTheft default/type differs for ObserverRangeMeters', errors)


if __name__ == '__main__':
    unittest.main()
