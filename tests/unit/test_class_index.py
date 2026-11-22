"""Class-name index tests on synthetic PBOs; static file evidence, never engine behaviour."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.unit.test_pbo_config import klass, pbo, rap
from tools.validate import class_index


def config(**roots):
    return pbo({'config.bin': rap(klass('', **{name: klass('', **rows) for name, rows in roots.items()}))})


class ClassIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_vanilla_sources_include_dlc_folders_but_not_tool_containers(self):
        self.write('DayZ/Addons/base.pbo', config())
        self.write('DayZ/nasdara/addons/dlc.pbo', config())
        self.write('DayZ/sakhal/Addons/dlc2.pbo', config())
        self.write('DayZ/!Workshop/@mod/addons/skipped.pbo', config())
        self.write('DayZ/empty/addons/readme.txt', b'x')
        sources = class_index.vanilla_sources(self.root / 'DayZ/Addons')
        self.assertEqual(['vanilla', 'vanilla:nasdara', 'vanilla:sakhal'], [s for s, _ in sources])

    def test_names_parents_and_scope_only_and_later_sources_refine(self):
        base = self.write('a/base.pbo', config(
            CfgVehicles=dict(Car=dict(__parent__='', scope=0, model='secret\\model.p3d'),
                             Ext=None),
            CfgAmmo=dict(Bullet_A=klass('', hit=5))))
        mod = self.write('b/mod.pbo', config(
            CfgVehicles=dict(Car=klass(''), Truck=klass('Car', scope=2))))
        data = class_index.build_index([('vanilla', [base]), ('123', [mod])])
        vehicles = data['classes']['CfgVehicles']
        self.assertEqual({'Car', 'Truck'}, set(vehicles))  # forward declarations are not definitions
        self.assertEqual({'parent': None, 'scope': 0, 'source': 'vanilla'}, vehicles['Car'])
        self.assertEqual({'parent': 'car', 'scope': 2, 'source': '123'}, vehicles['Truck'])
        self.assertIn('Bullet_A', data['classes']['CfgAmmo'])
        self.assertNotIn('secret', json.dumps(data))
        self.assertEqual(['vanilla', '123'], data['coverage'])

    def test_unreadable_archive_makes_the_source_uncovered(self):
        good = self.write('a/good.pbo', config(CfgVehicles=dict(Car=klass(''))))
        bad = self.write('b/bad.pbo', b'not a pbo')
        data = class_index.build_index([('vanilla', [good]), ('9', [bad])])
        self.assertEqual(['vanilla'], data['coverage'])
        self.assertEqual('bad.pbo', data['sources'][1]['unreadable'][0]['archive'])

    def test_manifest_dependencies_exclude_published_items_and_keep_rank_order(self):
        manifest = self.write('m.json', json.dumps({'mods': [
            {'id': '2', 'rank': 20, 'folder': '@B'}, {'id': '9', 'rank': 80, 'folder': '@HC', 'publish': True},
            {'id': '1', 'rank': 10, 'folder': '@A'}]}).encode())
        self.assertEqual(['1', '2'], [m['id'] for m in class_index.manifest_dependencies(manifest)])

    def test_declared_dependency_without_addons_is_an_error(self):
        self.write('DayZ/Addons/base.pbo', config())
        manifest = self.write('m.json', json.dumps({'mods': [{'id': '1', 'rank': 1, 'folder': '@A'}]}).encode())
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            class_index.declared_sources(self.root / 'DayZ/Addons', self.root / 'ws', manifest)
        self.write('ws/1/addons/a.pbo', config(CfgVehicles=dict(Car=klass(''))))
        sources = class_index.declared_sources(self.root / 'DayZ/Addons', self.root / 'ws', manifest)
        self.assertEqual(['vanilla', '1'], [s for s, _ in sources])

    def test_write_is_confined_to_the_cache_root_and_load_validates(self):
        with patch.object(class_index, 'DEFAULT_CACHE', self.root / 'cache/class-index.json'):
            with self.assertRaises(ValueError):
                class_index.write_index({}, self.root / 'elsewhere.json')
            data = {'schema': class_index.SCHEMA, 'coverage': ['vanilla'],
                    'classes': {'CfgVehicles': {'Car': {'parent': None, 'scope': 2, 'source': 'vanilla'}}}}
            class_index.write_index(data, self.root / 'cache/class-index.json')
        stored = json.loads((self.root / 'cache/class-index.json').read_text())
        self.assertEqual({'CfgVehicles': {'Car': {'parent': None, 'scope': 2}}},
                         class_index.load_rows(stored, ['CfgVehicles', 'CfgAmmo']))
        with self.assertRaises(ValueError):
            class_index.load_rows({'schema': 99}, ['CfgVehicles'])


if __name__ == '__main__':
    unittest.main()
