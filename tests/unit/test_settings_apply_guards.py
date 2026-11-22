"""Presence-guard recognition for the settings validators (source text only).

The validators accept either the HCJsonFields.Has gate or an HCJsonSchema.HCApply*
call, and refuse a binding that has neither or lacks its registry gate. Establishes
nothing about DayZ behaviour.
"""
import json
import re
import unittest

from tools.validate import enforce_json, settings_consistency as sc

GUARDED = 'if (HCJsonFields.Has(text, "Cap")) { Cap = decoded.Cap; }'
SCHEMA = 'Cap = HCJsonSchema.HCApplyInt(text, "Cap", decoded.Cap, Cap);'
GATED = 'Cap = HCRegistryInt("Cap", HCJsonSchema.HCApplyInt(text, "Cap", decoded.Cap, Cap), Cap, 1, 9);'
UNGUARDED = 'Cap = decoded.Cap;'


class ApplyBindingTests(unittest.TestCase):
    def test_both_presence_guarded_forms_are_found(self):
        for line in (GUARDED, SCHEMA, GATED):
            self.assertEqual(sc.find_apply('    ' + line + '\n', 'Cap', 'Cap', 'decoded', 'text'), '    ' + line)

    def test_unguarded_or_other_key_is_not_found(self):
        self.assertIsNone(sc.find_apply(UNGUARDED, 'Cap', 'Cap', 'decoded', 'text'))
        self.assertIsNone(sc.find_apply(SCHEMA, 'Other', 'Other', 'decoded', 'text'))
        self.assertIsNone(sc.find_apply(SCHEMA.replace('"Cap"', '"Cap2"'), 'Cap', 'Cap', 'decoded', 'text'))

    def test_apply_errors_require_the_range_gate_for_non_bool(self):
        row = {'type': 'int', 'min': 1, 'max': 9}
        gate = lambda key, r: rf'HCRegistryInt\("{key}",.*, {r["min"]}, {r["max"]}\);'
        self.assertEqual(sc.apply_errors('X', GATED, 'Cap', row, 'Cap', 'decoded', 'text', gate), [])
        self.assertEqual(len(sc.apply_errors('X', SCHEMA, 'Cap', row, 'Cap', 'decoded', 'text', gate)), 1)
        self.assertEqual(len(sc.apply_errors('X', UNGUARDED, 'Cap', row, 'Cap', 'decoded', 'text', gate)), 1)
        self.assertEqual(sc.apply_errors('X', SCHEMA, 'Cap', {'type': 'bool'}, 'Cap', 'decoded', 'text', gate), [])


class PresenceKeyTests(unittest.TestCase):
    def test_schema_apply_counts_as_a_presence_check(self):
        self.assertEqual(enforce_json.present_keys(SCHEMA + GUARDED + GATED), ['Cap', 'Cap', 'Cap'])
        self.assertEqual(enforce_json.present_keys('config.X = HCJsonSchema.HCApplyBool(raw, "On", d.On, config.X);'), ['On'])

    def test_unrelated_calls_do_not(self):
        self.assertEqual(enforce_json.present_keys(UNGUARDED + ' Other.HCApplyInt(text, "Cap", 1, 2);'), [])

    def test_loaders_include_the_schema_loader(self):
        self.assertTrue(enforce_json.LOAD.search('HCJsonSchemaLoader<HCHearthConfig>.HCLoadData(text, decoded, error)'))


RETIRED_SOURCE = (
    'class HCSettings {\n'
    '    static void HCRetiredKey(string content, string key) {}\n'
    '    static void HCApplyLegacy(string content, HCSettings settings)\n    {\n'
    '        HCRetiredKey(content, "OldFlag");\n    }\n}\n')


class RetiredSettingsTests(unittest.TestCase):
    def check(self, images, source=RETIRED_SOURCE, rules=(), fields=()):
        return sc.check_retired_settings(source, images, dict.fromkeys(rules), dict.fromkeys(fields))

    def test_clean_profiles_pass(self):
        self.assertEqual([], self.check([('operator', {'A': 1, 'AILimits': {'B': 2}})]))

    def test_retired_key_in_a_shipped_profile_is_flagged_at_any_depth(self):
        errors = self.check([('operator', {'OldFlag': True}), ('config', {'AILimits': {'OldFlag': 1}}), ('ok', {})])
        self.assertEqual(['operator: retired key OldFlag must not ship', 'config: retired key OldFlag must not ship'], errors)

    def test_retired_key_must_not_be_registered_or_decoded(self):
        self.assertEqual(1, len(self.check([], rules=['OldFlag'])))
        self.assertEqual(1, len(self.check([], rules=['Scope.OldFlag'])))
        self.assertEqual(1, len(self.check([], fields=['OldFlag'])))

    def test_declaration_requires_the_logging_helper(self):
        source = RETIRED_SOURCE.replace('static void HCRetiredKey(string content, string key) {}', '')
        self.assertEqual(['Retired settings keys are declared but HCRetiredKey is not defined'], self.check([], source))

    def test_no_declaration_means_nothing_is_retired(self):
        self.assertEqual([], self.check([('operator', {'OldFlag': 1})], 'class HCSettings {}'))

    def test_the_real_tree_declares_and_does_not_ship_its_retired_keys(self):
        source = sc.NATIVE.read_text()
        keys = set(re.findall(r'^        HCRetiredKey\(content, "(\w+)"\);', source, re.M))
        self.assertTrue(keys)
        for path in sc.SHIPPED:
            self.assertEqual([], [k for k in keys if k in sc.flatten(json.loads(path.read_text()))])


WILDLIFE_RULES = {
    'WildlifeProviders.TickMs': {'key': 'WildlifeProviders.TickMs', 'type': 'int', 'default': 5000, 'min': 1,
                                 'max': 60000, 'owner': 'HCWildlifeProviderConfig'},
    'WildlifeProviders.MinPlayerDistanceM': {'key': 'WildlifeProviders.MinPlayerDistanceM', 'type': 'float',
                                             'default': 200.0, 'min': 100, 'max': 1000,
                                             'owner': 'HCWildlifeProviderConfig'},
    'WildlifeProviders.Enabled': {'key': 'WildlifeProviders.Enabled', 'type': 'bool', 'default': True, 'min': 0,
                                  'max': 1, 'owner': 'HCWildlifeProviderConfig'},
}
WILDLIFE_JSON = {'TickMs': 5000, 'MinPlayerDistanceM': 200.0, 'Enabled': True}
WILDLIFE_SOURCE = (
    'class HCWildlifeProviderConfig\n{\n    bool Enabled;\n    int TickMs;\n    float MinPlayerDistanceM;\n'
    '    string WorldName;\n}\n'
    'class HCWildlifeProviders\n{\n'
    '    static bool HCValid(HCWildlifeProviderConfig config)\n    {\n'
    '        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.TickMs", config.TickMs)) { return false; }\n'
    '        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.MinPlayerDistanceM", config.MinPlayerDistanceM)) { return false; }\n'
    '        return true;\n    }\n'
    '    bool Probe() { return HCOperatorSettingsRegistry.HCValid("WildlifeProviders.TickMs", 1); }\n}\n')


class WildlifeProviderTests(unittest.TestCase):
    def check(self, rules=None, provider=None, source=None):
        return sc.check_wildlife_providers(
            dict(WILDLIFE_RULES) if rules is None else rules,
            dict(WILDLIFE_JSON) if provider is None else provider,
            WILDLIFE_SOURCE if source is None else source)

    def test_matching_registry_json_dto_and_bindings_pass(self):
        self.assertEqual([], self.check())

    def test_json_default_missing_or_wrong_type_is_flagged(self):
        self.assertEqual(['Wildlife provider default/type differs for WildlifeProviders.TickMs'],
                         self.check(provider={**WILDLIFE_JSON, 'TickMs': 5001}))
        self.assertEqual(['Wildlife provider default/type differs for WildlifeProviders.MinPlayerDistanceM'],
                         self.check(provider={**WILDLIFE_JSON, 'MinPlayerDistanceM': 200}))
        missing = {k: v for k, v in WILDLIFE_JSON.items() if k != 'Enabled'}
        self.assertEqual(['Wildlife provider JSON missing WildlifeProviders.Enabled'], self.check(provider=missing))

    def test_numeric_scalar_needs_its_registry_binding(self):
        source = WILDLIFE_SOURCE.replace('HCValid("WildlifeProviders.TickMs", config.TickMs)', 'HCValid("TickMs", config.TickMs)')
        errors = self.check(source=source)
        self.assertIn('Wildlife provider validation binding differs for WildlifeProviders.TickMs', errors)

    def test_binding_must_name_a_registered_key_and_read_its_own_field(self):
        wrong_field = WILDLIFE_SOURCE.replace('config.TickMs)) {', 'config.MinPlayerDistanceM)) {', 1)
        self.assertIn('Wildlife provider validation reads the wrong field for WildlifeProviders.TickMs', self.check(source=wrong_field))
        unregistered = {k: v for k, v in WILDLIFE_RULES.items() if k != 'WildlifeProviders.TickMs'}
        errors = self.check(rules=unregistered)
        self.assertIn('Wildlife provider validates unregistered key WildlifeProviders.TickMs', errors)

    def test_registry_row_needs_its_owner_and_a_same_typed_dto_field(self):
        wrong_owner = {k: dict(v) for k, v in WILDLIFE_RULES.items()}
        wrong_owner['WildlifeProviders.Enabled']['owner'] = 'HCSettings'
        self.assertEqual(['Wildlife provider owner differs for WildlifeProviders.Enabled'], self.check(rules=wrong_owner))
        retyped = WILDLIFE_SOURCE.replace('    int TickMs;', '    float TickMs;')
        self.assertIn('Wildlife provider DTO field/type differs for WildlifeProviders.TickMs', self.check(source=retyped))
        dropped = WILDLIFE_SOURCE.replace('    bool Enabled;\n', '')
        self.assertEqual(['Wildlife provider DTO field/type differs for WildlifeProviders.Enabled'], self.check(source=dropped))

    def test_the_real_tree_passes_and_a_synthetic_registry_skips_the_real_files(self):
        rows = sc.load_registry(include_scoped=True)
        rules = {r['key']: r for r in rows if r['key'].startswith(sc.WILDLIFE_PREFIX)}
        self.assertTrue(rules)
        self.assertEqual([], sc.check_wildlife_providers(rules))
        self.assertEqual([], [e for e in sc.check_consistency(registry=[r for r in rows if r['key'] not in rules])
                              if 'Wildlife' in e])


if __name__ == '__main__':
    unittest.main()
