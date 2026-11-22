"""Synthetic documents for the install-time variety overlay; no DayZ behaviour is established here."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import optional_overlays as overlays, variety_optional as vo

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / 'mission/hollow-country/optional' / vo.RELATIVE


def type_row(name, **extra):
    row = {'name': name, 'nominal': 3, 'lifetime': 100, 'restock': 0, 'min': 1, 'quantmin': -1, 'quantmax': -1,
           'cost': 100, 'flags': {'count_in_cargo': '0', 'crafted': '0'}, 'category': 'food', 'tags': ['shelves'],
           'usage': ['Town'], 'value': ['Tier1']}
    row.update(extra)
    return row


def setting(identifier, root, target, **content):
    return {'id': identifier, 'root': root, 'target': target, 'reason': 'r', 'content': content or {'Key': 1}}


def document(**packs):
    return {'schema': 1, 'kind': vo.KIND, 'packs': packs}


def dump(data):
    return json.dumps(data).encode()


class Overlay:
    """The two helpers optional_overlays hands to append_types."""
    @staticmethod
    def unique_append(parent, node):
        if any(n.get('name') == node.get('name') for n in parent):
            raise ValueError('duplicate')
        parent.append(node)


class Parsing(unittest.TestCase):
    def test_wrong_kind_schema_or_shape_is_refused(self):
        good = document(a={'folder': '@a', 'types': [], 'settings': []})
        for change in ({'kind': 'other'}, {'schema': 2}, {'packs': []}):
            with self.assertRaises(ValueError):
                vo.parse(dump({**good, **change}))
        self.assertEqual(set(vo.parse(dump(good))), {'a'})

    def test_shipped_document_names_the_packs_in_sorted_order(self):
        ids = vo.pack_ids(SHIPPED)
        self.assertEqual(list(ids), sorted(ids))
        self.assertEqual(vo.overlay_packs(SHIPPED), tuple(('Variety_' + i, i) for i in ids))

    def test_missing_document_means_no_packs(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.assertEqual(vo.pack_ids(Path(scratch) / 'none.json'), ())


class Rows(unittest.TestCase):
    def test_element_carries_every_authored_field_in_order(self):
        row = type_row('Thing', tags=['t1', 't2'], usage=['U1', 'U2'], value=['V1'])
        node = vo._element(row)
        self.assertEqual(node.get('name'), 'Thing')
        self.assertEqual([c.tag for c in node][:len(vo.ORDER)], list(vo.ORDER))
        self.assertEqual([c.get('name') for c in node.findall('usage')], row['usage'])
        self.assertEqual([c.get('name') for c in node.findall('tag')], row['tags'])
        self.assertEqual(node.find('category').get('name'), row['category'])
        self.assertEqual(dict(node.find('flags').attrib), row['flags'])

    def test_a_row_without_a_category_has_no_category_node(self):
        self.assertIsNone(vo._element(type_row('Thing', category=None)).find('category'))

    def test_only_loaded_packs_add_rows_and_none_loaded_adds_nothing(self):
        data = document(**{'1': {'folder': '@a', 'types': [type_row('A1'), type_row('A2')], 'settings': []},
                           '2': {'folder': '@b', 'types': [type_row('B1')], 'settings': []}})
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / vo.RELATIVE
            path.write_bytes(dump(data))
            types = ET.Element('types')
            self.assertEqual(vo.append_types({'Other': 1}, path, types, lambda p: p.read_bytes(), Overlay), 0)
            self.assertEqual(len(types), 0)
            added = vo.append_types({'Variety_2': 1}, path, types, lambda p: p.read_bytes(), Overlay)
            self.assertEqual((added, [n.get('name') for n in types]), (1, ['B1']))

    def test_empty_or_over_budget_pack_is_refused(self):
        for rows in ([], [type_row('X%d' % i) for i in range(vo.MAX_ROWS + 1)]):
            data = document(**{'1': {'folder': '@a', 'types': rows, 'settings': []}})
            with tempfile.TemporaryDirectory() as scratch:
                path = Path(scratch) / vo.RELATIVE
                path.write_bytes(dump(data))
                with self.assertRaises(ValueError):
                    vo.append_types({'Variety_1': 1}, path, ET.Element('types'), lambda p: p.read_bytes(), Overlay)

    def test_duplicate_names_are_refused_by_the_shared_helper(self):
        data = document(**{'1': {'folder': '@a', 'types': [type_row('A'), type_row('A')], 'settings': []}})
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / vo.RELATIVE
            path.write_bytes(dump(data))
            with self.assertRaises(ValueError):
                vo.append_types({'Variety_1': 1}, path, ET.Element('types'), lambda p: p.read_bytes(), Overlay)


class Settings(unittest.TestCase):
    def setUp(self):
        self.document = document(**{
            '1': {'folder': '@a', 'types': [type_row('A')], 'settings': [
                setting('m', 'mission', 'Dir/file.json', Alpha=1), setting('p', 'profile', 'Gebs/p.json', Beta=0)]},
            '2': {'folder': '@b', 'types': [type_row('B')], 'settings': [
                setting('q', 'profile', 'Other/Sub/q.json', Gamma=[1])]}})
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.path = Path(self.scratch.name) / vo.RELATIVE
        self.path.write_bytes(dump(self.document))

    def test_targets_and_profile_files_come_from_the_document_by_root(self):
        self.assertEqual(vo.mission_targets(self.path), {'Dir/file.json'})
        files = vo.profile_files(self.path)
        self.assertEqual(set(files), {'Gebs/p.json', 'Other/Sub/q.json'})
        self.assertEqual(json.loads(files['Gebs/p.json']), {'Beta': 0})
        self.assertTrue(files['Gebs/p.json'].endswith(b'\n'))

    def test_bytes_are_deterministic(self):
        self.assertEqual(vo.profile_files(self.path), vo.profile_files(self.path))

    def test_mission_settings_cover_loaded_packs_only_and_skip_existing_files(self):
        mission = Path(self.scratch.name) / 'mission'
        read = lambda p: p.read_bytes()
        self.assertEqual(vo.mission_settings({'Variety_2': 1}, self.path, read, mission), [])
        rows = vo.mission_settings({'Variety_1': 1}, self.path, read, mission)
        self.assertEqual([t for t, _ in rows], ['Dir/file.json'])
        self.assertEqual(json.loads(rows[0][1]), {'Alpha': 1})
        (mission / 'Dir').mkdir(parents=True)
        (mission / 'Dir/file.json').write_bytes(b'{"own": 1}')
        self.assertEqual(vo.mission_settings({'Variety_1': 1}, self.path, read, mission), [])

    def test_unsafe_targets_roots_and_empty_content_are_refused(self):
        for change in ({'target': '../x.json'}, {'target': '/abs/x.json'}, {'target': 'x.json'},
                       {'target': 'a\\b/x.json'}, {'target': 'a/b.txt'}, {'root': 'elsewhere'}, {'content': {}},
                       {'content': []}):
            data = copy.deepcopy(self.document)
            data['packs']['1']['settings'][0].update(change)
            with self.assertRaises(ValueError, msg=str(change)):
                vo.parse(dump(data))


class Planning(unittest.TestCase):
    def test_every_shipped_mission_target_is_an_allowed_overlay_target(self):
        for target in vo.mission_targets(SHIPPED):
            self.assertTrue(overlays.allowed(target), target)

    def test_targets_that_are_not_shipped_are_not_allowed(self):
        for target in ('cfgweather.xml', 'Other/never-shipped.json', '../escape.json'):
            self.assertFalse(overlays.allowed(target), target)

    def test_profile_targets_are_never_overlay_targets(self):
        for target in vo.profile_files(SHIPPED):
            self.assertFalse(overlays.allowed(target), target)


if __name__ == '__main__':
    unittest.main()
