"""Offline admission checks for operator settings, not Enforce execution."""
import copy
import json
import re
from pathlib import Path
import unittest
from tools.validate.runtime import validate_settings
from tests.unit.test_group_server import execute_member

ROOT = Path(__file__).resolve().parents[2]

class RuntimeSettingsTests(unittest.TestCase):
    def test_native_settings_reader_is_bounded_before_json_parsing(self):
        source = (ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
        match = re.search(r'static bool AcceptDocumentLength\(int length\)\s*\{\s*return ([^;]+);', source)
        self.assertIsNotNone(match)
        expression = match[1].replace('&&', ' and ')
        self.assertRegex(expression, r'^[a-z0-9 ><=&]+$')
        for length, expected in ((-1, False), (0, False), (1, True), (16384, True), (16385, False), (100000000, False)):
            self.assertEqual(expected, eval(expression, {'__builtins__': {}}, {'length': length}))
        self.assertIn('ReadFile(handle, content, 16385);', source)
        self.assertIn('AcceptDocumentLength(content.Length())', source)
        self.assertNotIn('JsonFileLoader<HCSettings>.LoadFile', source)

    def setUp(self):
        self.value = json.loads((ROOT / 'config/hollow-country-settings.json').read_text())

    def test_shipped_settings_are_valid_and_all_feature_preferences_default_on(self):
        self.assertEqual([], validate_settings(self.value))
        flags = {k: v for k, v in self.value.items() if k.startswith('Enable')}
        self.assertEqual(8, len(flags))
        self.assertTrue(all(v is True for v in flags.values()), flags)
        source = (ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
        native = dict(re.findall(r'bool (Enable\w+) = (true|false);', source))
        self.assertEqual(set(flags), set(native))
        self.assertEqual({'true'}, set(native.values()))

    def test_explicit_disable_is_preserved_and_groups_are_independent(self):
        disabled = dict(self.value)
        for key in disabled:
            if key.startswith('Enable'):
                disabled[key] = False
        self.assertEqual([], validate_settings(disabled))
        self.assertEqual([], validate_settings(dict(disabled, EnableGroups=True)))
        self.assertEqual([], validate_settings(dict(self.value, EnableGroups=False)))
        for invalid in ('true', 1, None):
            self.assertTrue(validate_settings(dict(self.value, EnableGroups=invalid)))

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
        for child, parent in (('EnableSearch', 'EnableInteriors'),
                              ('EnableHordes', 'EnableInfected'),
                              ('EnableAlertChains', 'EnableInfected')):
            self.assertTrue(validate_settings(dict(self.value, **{child: True, parent: False})))
        changed = copy.deepcopy(self.value)
        for key in changed:
            if key.startswith('Enable'): changed[key] = True
        self.assertEqual([], validate_settings(changed))

    def test_native_startup_selftest_agrees_with_enabled_defaults_and_dependency_rejection(self):
        source=(ROOT/'mods/HollowCountry/scripts/4_World/Core/HCNativeSelfTests.c').read_text()
        defaults=dict(self.value)
        validations=[]
        class NativeSettings:
            def __init__(self):vars(self).update(defaults)
            @staticmethod
            def AcceptDocumentLength(length):return 0 < length <= 16384
            def Validate(self,error):
                result=not validate_settings(vars(self))
                validations.append((dict(vars(self)),result))
                return result
        source=source.replace('HCSettings settings =','HCGroupNative settings =')
        self.assertTrue(execute_member(source,'Run',dict(HCSettings=NativeSettings,Print=lambda text:None),None))
        self.assertTrue(any(v['EnableSearch'] and not v['EnableInteriors'] and not ok for v,ok in validations))
        self.assertTrue(any(v['SchemaVersion']==2 and not ok for v,ok in validations))

if __name__ == '__main__':
    unittest.main()
