"""Offline admission checks for operator settings, not Enforce execution."""
import copy
import json
from pathlib import Path
import unittest
from tools.validate.runtime import validate_settings

ROOT = Path(__file__).resolve().parents[2]

class RuntimeSettingsTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads((ROOT / 'config/hollow-country-settings.json').read_text())

    def test_shipped_settings_are_valid_and_all_features_default_off(self):
        self.assertEqual([], validate_settings(self.value))
        self.assertTrue(all(v is False for k, v in self.value.items() if k.startswith('Enable')))

    def test_wrong_schema_unknown_fields_and_missing_limits_fail(self):
        for name, value in [('SchemaVersion', 2), ('ExtraCommand', 'anything')]:
            changed = dict(self.value, **{name: value})
            self.assertTrue(validate_settings(changed))
        for key in self.value:
            changed = dict(self.value)
            del changed[key]
            self.assertTrue(validate_settings(changed), key)

    def test_feature_flags_are_booleans_not_truthy_strings_or_numbers(self):
        for key in self.value:
            if key.startswith('Enable'):
                for bad in (1, 'false', None, []):
                    self.assertTrue(validate_settings(dict(self.value, **{key: bad})))

    def test_zero_negative_unbounded_and_nonintegral_budgets_fail(self):
        for key in self.value:
            if key.startswith(('Max', 'Tick')):
                for bad in (-1, 0, True, 1.5, '10', 100000000):
                    self.assertTrue(validate_settings(dict(self.value, **{key: bad})), (key, bad))

    def test_search_requires_interiors_and_hordes_chains_require_infected(self):
        for key in ('EnableSearch', 'EnableHordes', 'EnableAlertChains'):
            self.assertTrue(validate_settings(dict(self.value, **{key: True})))
        changed = copy.deepcopy(self.value)
        for key in changed:
            if key.startswith('Enable'): changed[key] = True
        self.assertEqual([], validate_settings(changed))

if __name__ == '__main__':
    unittest.main()
