"""Synthetic trees prove each cap rule; the real tree must satisfy the same rules."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.audit import gapcov_regions
from tools.validate import json_loader_caps as caps

STORE = 'class HCWorldStore\n{\n    static const int MAX_BYTES = %d;\n}\n'
DEFAULTS = 'class HCProfileDefaults\n{\n    static const int MAX_BYTES = %d;\n}\n'
ROAD = 'mission/hollow-country/ai/road-graph.compact.json'
CARAVAN = 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAICaravanAdapter.c'


class JsonLoaderCapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hc-synthetic-json-caps-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.put(caps.WORLD_STORE, STORE % 1000)
        self.put(caps.PROFILE_DEFAULTS, DEFAULTS % 1200)

    def put(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())

    def mission(self, name, size, reader=None):
        self.put(caps.MISSION + name, b'x' * size)
        if reader:
            self.put('mods/Native/scripts/4_World/Reader.c', reader)

    def errors(self, names):
        return caps.check(self.root, names)[0]

    def test_budget_boundary_is_integer_exact(self):
        cap = 1000
        limit = cap * caps.LIMIT_PERCENT // 100
        self.assertTrue(caps.within_budget(limit, cap))
        self.assertFalse(caps.within_budget(limit + 1, cap))

    def test_one_shot_cap_is_the_smaller_native_reader(self):
        self.assertEqual(1000, caps.one_shot_cap(self.root))
        self.put(caps.PROFILE_DEFAULTS, DEFAULTS % 500)
        self.assertEqual(500, caps.one_shot_cap(self.root))

    def test_missing_cap_constant_is_an_error_not_a_pass(self):
        self.put(caps.WORLD_STORE, 'class HCWorldStore {}\n')
        with self.assertRaises(ValueError):
            caps.one_shot_cap(self.root)

    def test_native_read_mission_file_fails_above_limit(self):
        limit = 1000 * caps.LIMIT_PERCENT // 100
        self.mission('ai/sites.json', limit + 1, 'string p = "$mission:hollow-country/ai/sites.json";')
        self.mission('ai/ok.json', limit, 'string q = "$mission:hollow-country/ai/ok.json";')
        errors = self.errors(['ai/sites.json', 'ai/ok.json'])
        self.assertEqual(1, len(errors))
        self.assertIn('ai/sites.json', errors[0])
        self.assertIn('cap=1000', errors[0])

    def test_unreferenced_mission_file_has_no_loader_cap(self):
        self.mission('loot-points/big.json', 5000, 'string p = "$mission:hollow-country/ai/other.json";')
        self.assertEqual([], self.errors(['loot-points/big.json']))
        self.assertNotIn(caps.MISSION + 'loot-points/big.json', caps.loader_caps(self.root, ['loot-points/big.json']))

    def test_directory_literal_covers_computed_paths(self):
        self.mission('interiors/templates/t-0001.json', 900,
                     'string p = "$mission:hollow-country/interiors/templates/" + name;')
        self.assertEqual(1, len(self.errors(['interiors/templates/t-0001.json'])))

    def test_bounded_read_literal_declares_its_own_cap(self):
        self.mission('travel/index.json', 300,
                     'this.HCReadBounded("$mission:hollow-country/travel/index.json", 4096, content);')
        self.put('mods/Native/scripts/4_World/Reader.c',
                 'this.HCReadBounded("$mission:hollow-country/travel/index.json", 200, content);')
        errors = self.errors(['travel/index.json'])
        self.assertEqual(1, len(errors))
        self.assertIn('cap=200', errors[0])
        self.assertIn('HCReadBounded', errors[0])

    def test_streamed_loader_cap_is_parsed_from_its_source(self):
        size = 3000
        roomy = size * 100 // caps.LIMIT_PERCENT + 1
        self.put(ROAD, b'x' * size)
        self.put(CARAVAN, 'if (m_CompactBytes > %d) { fail; }\n' % roomy)
        self.assertEqual([], caps.check(self.root, ['ai/road-graph.compact.json'])[0])
        self.put(CARAVAN, 'if (m_CompactBytes > %d) { fail; }\n' % size)
        errors = caps.check(self.root, ['ai/road-graph.compact.json'])[0]
        self.assertEqual(1, len(errors))
        self.assertIn('cap=%d' % size, errors[0])

    def test_streamed_loader_without_cap_pattern_fails_loudly(self):
        self.put(ROAD, b'x' * 10)
        self.put(CARAVAN, 'nothing here\n')
        with self.assertRaises(ValueError):
            caps.check(self.root, ['ai/road-graph.compact.json'])

    def test_addon_defaults_and_settings_template_use_the_one_shot_cap(self):
        self.put('mods/Addon/data/defaults/expansion-ai-sites.json', b'x' * 900)
        self.put('mods/Addon/data/defaults/loadouts/small.json', b'x' * 10)
        self.put(caps.SETTINGS_TEMPLATE, b'x' * 900)
        errors = self.errors([])
        self.assertEqual(2, len(errors))
        self.assertTrue(any('expansion-ai-sites.json' in text for text in errors))
        self.assertTrue(any(caps.SETTINGS_TEMPLATE in text for text in errors))

    def test_shipped_tree_stays_inside_every_loader_cap(self):
        errors, checked = caps.check()
        self.assertEqual([], errors)
        self.assertGreater(checked, 0)

    def test_sites_policy_carries_no_offline_only_data(self):
        policy = json.loads((caps.ROOT / 'mission/hollow-country/ai/sites.json').read_text())
        self.assertFalse(set(gapcov_regions.DERIVED_KEYS) & set(policy['HC43']))
        mirror = caps.ROOT / 'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-sites.json'
        self.assertEqual((caps.ROOT / 'mission/hollow-country/ai/sites.json').read_bytes(), mirror.read_bytes())


class SplitDerivedTests(unittest.TestCase):
    def test_keys_leave_the_manifest_and_are_returned(self):
        manifest = {'Localities': [1], 'Regions': {'a': 1}, 'AdditionalWorlds': [{'w': 1}]}
        derived = gapcov_regions.split_derived(manifest, None)
        self.assertEqual({'Localities': [1]}, manifest)
        self.assertEqual({'Regions': {'a': 1}, 'AdditionalWorlds': [{'w': 1}]}, derived)

    def test_sidecar_supplies_keys_absent_from_the_manifest(self):
        manifest = {'Localities': [1]}
        previous = {'Regions': {'old': 1}, 'AdditionalWorlds': [{'w': 2}]}
        derived = gapcov_regions.split_derived(manifest, previous)
        self.assertEqual({'Localities': [1]}, manifest)
        self.assertEqual(previous, derived)

    def test_inline_keys_win_over_the_sidecar(self):
        manifest = {'AdditionalWorlds': [{'w': 'inline'}]}
        derived = gapcov_regions.split_derived(manifest, {'AdditionalWorlds': [{'w': 'old'}], 'Regions': {'r': 1}})
        self.assertEqual([{'w': 'inline'}], derived['AdditionalWorlds'])
        self.assertEqual({'r': 1}, derived['Regions'])


if __name__ == '__main__':
    unittest.main()
