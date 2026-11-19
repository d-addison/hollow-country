"""Offline settings admission; synthetic native ports never establish DayZ behavior.

Wave 8 trace: #168 request 6 + #158 -> shared registry/scale/status work package.
Spec: scale search/interior admission budgets together, preserve operator choices,
zero/missing = identity, reject metadata drift, leave inventory/yield unchanged.
Plan/tasks: RED authored cap/status + registry check -> checked compiled registry
-> scaled reader caps -> single-state publication -> operator table -> regression.
The requested central spec paths are absent; lead owns central trace reconciliation.
Actual RED command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_runtime_settings.DensityRegistryTests test_interior_templates_runtime.InteriorTemplatesRuntimeTests.test_status_publishes_one_selected_state_and_recognizes_legacy_owner -v
RED: ModuleNotFoundError: No module named 'tools.validate.settings_consistency'
RED status: ready legacy_pilot_admitted_runtime_pending != off template_owner_not_running.
Focused cap RED (same command restricted to the density test):
AssertionError: Missing authored method HCValid
Final GREEN commands/results are retained in .banso-writer/report.md and the
Banso commit body. Runtime/production acceptance remains PENDING.
"""
import copy
import json
import re
from pathlib import Path
import unittest
from tools.validate.runtime import validate_settings
from tests.unit.test_group_server import execute_member

ROOT = Path(__file__).resolve().parents[2]
V2_FLAGS = ('EnableGrade', 'EnableAmbientLife', 'EnableSignsOfLife', 'EnableTravel', 'EnableWorld', 'EnableLeads',
            'EnableCamps', 'EnableEncounters',
            'EnableInfectedVariety', 'EnableDebugSnapshot', 'EnableAdminMap', 'EnableCampRespawn', 'EnableTeamPing', 'EnableVehicleFlip', 'EnableMealBuffs', 'EnableForage', 'EnableProgression', 'EnableGroupScaling')

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
        self.assertEqual(27, len(flags))
        # EnableTapedPackMounts (#58) is a default-off gate switch; every other preference is on.
        self.assertIs(False, flags.pop('EnableTapedPackMounts'))
        self.assertTrue(all(v is True for v in flags.values()), flags)
        source = (ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
        native = dict(re.findall(r'bool (Enable\w+) = (true|false);', source))
        self.assertEqual('false', native.pop('EnableTapedPackMounts'))
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
            if key in V2_FLAGS or key == 'EnableTapedPackMounts' or key in ('AILimits', 'ClientPresentationMask', 'MaxFamiliarityRows', 'SearchDensityScale'):
                continue
            changed = dict(self.value)
            del changed[key]
            self.assertTrue(validate_settings(changed), key)

    def test_optional_presentation_mask_accepts_only_ints_0_through_15(self):
        from tests.unit.test_hc_client_controls import install, SETTINGS
        from types import SimpleNamespace as N
        from tools.validate.runtime import LIMITS
        value = dict(self.value)
        value.pop('ClientPresentationMask', None)
        self.assertEqual([], validate_settings(value))
        for mask in range(16):
            with self.subTest(mask=mask):
                self.assertEqual([], validate_settings(dict(value, ClientPresentationMask=mask)))
        for mask in (-1, 16, True, False, 1.5, '15', None):
            self.assertTrue(validate_settings(dict(value, ClientPresentationMask=mask)), mask)
        self.assertNotIn('ClientPresentationMask', LIMITS)
        self.assertEqual(15, self.value.get('ClientPresentationMask'))
        env = dict(HCAILimits=lambda: N(Validate=lambda: None), Print=lambda line: None)
        env['HCAILimits'].Use = lambda limits: None
        install(SETTINGS, env, 'HCClientPresentationSettings', ('HCValidMask',))
        from tests.unit.settings_registry_fixture import install_registry
        install_registry(env)
        native = install(ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c',
                         env, 'HCSettings', ('Validate',))()
        self.assertEqual(15, native.ClientPresentationMask)
        for mask in range(-1, 17):
            native.ClientPresentationMask = mask
            self.assertEqual(0 <= mask <= 15, native.Validate(''), mask)
        self.assertIn('ClientPresentationMask outside 0..15',
                      (ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text())

    def test_v1_settings_file_without_v2_preferences_loads_with_v2_defaults_on(self):
        # LC-T001 / SA-15: an operator's existing V1 settings.json stays valid and gets every V2 feature on.
        v1 = {k: v for k, v in self.value.items() if k not in V2_FLAGS}
        self.assertEqual([], validate_settings(v1))
        source = (ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
        native = dict(re.findall(r'bool (Enable\w+) = (true|false);', source))
        for key in V2_FLAGS:
            self.assertEqual('true', native.get(key), key)
            self.assertIs(True, self.value.get(key), key)
            for bad in (1, 'true', None):
                self.assertTrue(validate_settings(dict(v1, **{key: bad})), (key, bad))
            self.assertEqual([], validate_settings(dict(v1, **{key: False})), key)
        # Native load zeroes scalars. Execute the authored absent-key migration;
        # explicit operator false/zero must survive it.
        from tests.unit.test_v1_combined_flags import Profile
        legacy = dict(v1)
        legacy.pop('ClientPresentationMask', None)
        legacy.pop('MaxFurnishedProps', None)
        profile = Profile(legacy)
        decoded = profile.decode('synthetic')
        for key in V2_FLAGS:
            self.assertIs(True, getattr(decoded, key), key)
        self.assertEqual((15, 1500), (decoded.ClientPresentationMask, decoded.MaxFurnishedProps))
        explicit = Profile(dict(legacy, EnableWorld=False, ClientPresentationMask=0, MaxFurnishedProps=0)).decode('synthetic')
        self.assertEqual((False, 0, 0), (explicit.EnableWorld, explicit.ClientPresentationMask, explicit.MaxFurnishedProps))
        self.assertRegex(source, r'HCSettings settings = new HCSettings\(\);[\s\S]*LoadBounded\(path, settings, error\)')

    def test_feature_flags_are_booleans_not_truthy_strings_or_numbers(self):
        for key in self.value:
            if key.startswith('Enable'):
                for bad in (1, 'false', None, []):
                    self.assertTrue(validate_settings(dict(self.value, **{key: bad})))

    def test_zero_negative_unbounded_and_nonintegral_budgets_fail(self):
        for key in self.value:
            if key.startswith(('Max', 'Tick', 'Infected')):
                for bad in (-1, 0, True, 1.5, '10', 100000000):
                    if bad == 0 and key in ('MaxFurnishedProps', 'MaxFamiliarityRows') and bad is not True:
                        continue
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

    def test_interior_template_budgets_ship_with_contract_defaults_and_bounds(self):
        # docs/INTERIOR_TEMPLATES_CONTRACT.md section 8: lead-owned budgets for the building fan-out.
        expected = {'MaxFurnishedProps': (1500, 0, 2000), 'MaxBoundSearchSites': (256, 1, 1024),
                    'InfectedBindRadius': (30, 5, 60), 'MaxBindQueriesPerTick': (2, 1, 8)}
        from tools.validate.runtime import LIMITS
        for key, (default, low, high) in expected.items():
            self.assertEqual(default, self.value.get(key), key)
            self.assertEqual((low, high), LIMITS.get(key), key)
            self.assertEqual([], validate_settings(dict(self.value, **{key: low})), key)
            self.assertEqual([], validate_settings(dict(self.value, **{key: high})), key)
            self.assertTrue(validate_settings(dict(self.value, **{key: low - 1})), key)
            self.assertTrue(validate_settings(dict(self.value, **{key: high + 1})), key)

    def test_native_int_defaults_and_bounds_match_the_operator_validator(self):
        from tools.validate.runtime import LIMITS
        source = (ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
        defaults = {k: int(v) for k, v in re.findall(r'^\s*int (\w+) = (-?\d+);', source, re.M)}
        for key, (low, high) in LIMITS.items():
            self.assertEqual(self.value[key], defaults.get(key), key)
            from tools.validate.runtime import RULES
            self.assertEqual((low, high), (RULES[key]['min'], RULES[key]['max']), key)
            self.assertIn(f'HCOperatorSettingsRegistry.HCValid("{key}", {key})', source)

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

class DensityRegistryTests(unittest.TestCase):
    def test_density_scales_four_budgets_without_mutating_operator_choices(self):
        from types import SimpleNamespace as N
        from tests.unit.settings_registry_fixture import attach_density, install_registry, SETTINGS
        from tests.unit.test_hc_client_controls import install
        attach_density(N(SearchDensityScale=0))
        defaults = json.loads((ROOT / 'config/hollow-country-settings.json').read_text())
        logs = []
        env = dict(Print=logs.append, tostr=str, HCAILimits=lambda: N(Validate=lambda: None))
        env['HCAILimits'].Use = lambda limits: None
        install_registry(env)
        native = install(SETTINGS, env, 'HCSettings', ('Validate',))()
        keys = ('MaxBoundSearchSites', 'MaxActiveInteriors', 'MaxPropsPerInterior', 'MaxFurnishedProps')
        for scale, caps in ((0, (256, 12, 5, 1500)), (0.5, (128, 6, 2, 750)),
                            (1, (256, 12, 5, 1500)), (2, (512, 24, 10, 2000))):
            settings = attach_density(N(**dict(defaults, SearchDensityScale=scale)))
            self.assertEqual(caps, tuple(settings.HCSearchCap(k, getattr(settings, k)) for k in keys))
            self.assertEqual(tuple(defaults[k] for k in keys), tuple(getattr(settings,k) for k in keys))
        settings = attach_density(N(SearchDensityScale=2))
        self.assertEqual((1024, 32, 20, 2000), tuple(settings.HCSearchCap(k, 999999) for k in keys))
        self.assertEqual(0, settings.HCSearchCap('MaxFurnishedProps', 0))
        settings.SearchDensityScale = 0.5
        self.assertEqual(1, settings.HCSearchCap('MaxPropsPerInterior', 1))
        for invalid in (-1, 0.25, 2.01):
            logs.clear()
            native.SearchDensityScale = invalid
            self.assertTrue(native.Validate(''))
            self.assertEqual(0, native.SearchDensityScale)
            self.assertEqual(1, sum('invalid SearchDensityScale' in line for line in logs))
        self.assertEqual([], validate_settings(dict(defaults, SearchDensityScale=0.5)))
        for bad in (True, '1', None, -1, 0.25, 2.01, float('nan'), float('inf')):
            self.assertTrue(validate_settings(dict(defaults, SearchDensityScale=bad)), bad)

        # Given synthetic native CE handles, the real search readers must
        # consume the scaled caps; neither reader may keep an unscaled budget.
        from tests.unit.test_search_economy_houses import Harness, SITE_A, site_world
        for mode in ('sites', 'active'):
            for scale, expected in ((0.5, 1), (1, 2), (2, 3)):
                harness = Harness(SearchDensityScale=scale, MaxBindQueriesPerTick=8,
                                  MaxBoundSearchSites=2 if mode == 'sites' else 1024,
                                  MaxActiveInteriors=2 if mode == 'active' else 32)
                for index in range(3):
                    house = harness.house(position=(1000. + 100. * index, 0., 1000.))
                    harness.food(index + 1, site_world(house, SITE_A))
                    player = harness.player('synthetic-density-' + str(index))
                    action = harness.action(player, house, [0., 1., 0.], [0., 1., 1.])
                    harness.houses.Begin(action)
                self.assertEqual(expected, harness.houses.m_Journal.SiteCount(), (mode, scale))
                if mode == 'active': self.assertEqual(expected, harness.houses.ActiveCount())
                self.assertEqual([], harness.moves(), 'density must never move/duplicate inventory')
        from tests.unit.test_v1_combined_flags import Profile
        legacy = dict(defaults)
        legacy.pop('SearchDensityScale')
        profile = Profile(legacy)
        admitted = profile.load()
        self.assertEqual(1.0, admitted.HCEffectiveSearchDensity())
        self.assertEqual([], profile.writes, 'loading must preserve operator profile bytes')
        effective = [line for line in profile.logs if line.startswith('[HC Settings] effective ')]
        registered = json.loads((ROOT / 'tools/validate/shared_settings.json').read_text())
        self.assertEqual({row['key'] for row in registered if row['type'] != 'object' and not row['key'].startswith('Performance.')},
                         {line.split(' effective ')[1].split('=')[0] for line in effective})
        self.assertEqual(len({row['key'] for row in registered if row['type'] != 'object' and not row['key'].startswith('Performance.')}), len(effective))

    def test_registry_detects_key_default_range_and_runtime_drift(self):
        from tools.validate.settings_consistency import check_consistency
        source = (ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
        registry = json.loads((ROOT / 'tools/validate/shared_settings.json').read_text())
        shipped = json.loads((ROOT / 'config/hollow-country-settings.json').read_text())
        self.assertEqual([], check_consistency())
        for mutation in ('extra', 'missing', 'default', 'range', 'native-default', 'native-range', 'nested'):
            rows, settings, native = copy.deepcopy(registry), copy.deepcopy(shipped), source
            if mutation == 'extra': settings['SyntheticUnexpected'] = 1
            if mutation == 'missing': settings.pop('MaxBoundSearchSites')
            if mutation == 'default': settings['MaxBoundSearchSites'] = 257
            if mutation == 'range':
                next(row for row in rows if row['key'] == 'MaxBoundSearchSites')['max'] = 2048
            if mutation == 'native-default': native = native.replace('int MaxBoundSearchSites = 256;', 'int MaxBoundSearchSites = 257;')
            if mutation == 'native-range': native = native.replace('HCValid("MaxBoundSearchSites", MaxBoundSearchSites)', 'HCValid("MaxActiveInteriors", MaxBoundSearchSites)')
            if mutation == 'nested': settings['AILimits']['SyntheticUnexpected'] = 1
            self.assertTrue(check_consistency(registry=rows, shipped=settings, native=native), mutation)


if __name__ == '__main__':
    unittest.main()
