"""Behavior of the map overlay layers framework (authored object layers for Chernarus+).

Every fixture here is SYNTHETIC: class names reuse real DayZ names but the positions, mission files and
prototype groups are invented for the tests and never describe the real map. Offline tests never establish
DayZ behavior; spawning, floating or clipping, and CE loot on the added tents stay pending native testing.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.package import map_overlay as mo  # noqa: E402

SOURCE = REPO / 'config/map-overlays'

CLASSES = {
    'kind': 'hollow-country-overlay-classes',
    'provenance': {'source': 'synthetic test allowlist', 'method': 'invented', 'verified': 'none'},
    'classes': {
        'Land_Mil_Tent_Big1_1': {'pbo': 'structures_military.pbo'},
        'Land_Mil_Tent_Big1_2': {'pbo': 'structures_military.pbo'},
        'Land_Medical_Tent_Big': {'pbo': 'structures_residential.pbo'},
    },
}
PROFILE = {
    'kind': 'hollow-country-overlay-profile',
    'enabled': ['alpha-v1'],
    'limits': {'map_size': 15360, 'max_objects_total': 20, 'max_objects_per_layer': 10,
               'min_spacing_m': 6.0, 'vanilla_clearance_m': 8.0},
}


def obj(ident, cls='Land_Mil_Tent_Big1_1', x=2000.0, y=100.0, z=3000.0, yaw=0.0, loot='proto'):
    return {'id': ident, 'class': cls, 'pos': [x, y, z], 'yaw': yaw, 'loot': loot, 'area': 'synthetic'}


def layer(ident='alpha-v1', objects=None, **extra):
    data = {
        'kind': 'hollow-country-map-overlay', 'id': ident, 'version': 1,
        'purpose': 'synthetic test layer', 'status': 'runtime-unverified',
        'objects': objects if objects is not None else [obj('t01'), obj('t02', x=2030.0)],
    }
    data.update(extra)
    return data


def source(layers=None, profile=None, classes=None):
    layers = layers if layers is not None else [layer()]
    return mo.Source(copy.deepcopy(profile or PROFILE), copy.deepcopy(classes or CLASSES),
                     [copy.deepcopy(item) for item in layers])


POS_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<map>
    <group name="Land_Mil_Barracks2" pos="2000.000000 100.000000 3000.000000" rpy="-0.000000 0.000000 10.000000" a="80.000000" />
    <group name="Land_House_1W12_Brown" pos="2500.000000 101.000000 3500.000000" rpy="-0.000000 0.000000 -70.000000" a="160.000000" />
</map>
'''
PROTO_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<prototype>
\t<group name="Land_Mil_Tent_Big1_1" lootmax="11"><usage name="Military" /></group>
\t<group name="Land_Mil_Tent_Big1_2" lootmax="11"><usage name="Military" /></group>
</prototype>
'''
GAMEPLAY = '''{
\t"version": 123,
\t"WorldsData": {
\t\t"lightingConfig": 0,
\t\t"objectSpawnersArr": [],
\t\t"environmentMinTemps": [-5, -4]
\t}
}
'''
CORE = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<economycore>\n</economycore>\n'


def mission(root, gameplay=GAMEPLAY, pos=POS_XML, proto=PROTO_XML):
    root = Path(root) / 'mission'
    root.mkdir()
    (root / 'cfgeconomycore.xml').write_text(CORE)
    (root / 'cfggameplay.json').write_text(gameplay)
    (root / 'mapgrouppos.xml').write_text(pos)
    (root / 'mapgroupproto.xml').write_text(proto)
    return root


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(Path(root).rglob('*')) if p.is_file()}


class LayerValidation(unittest.TestCase):
    def errors(self, layers, **kwargs):
        return mo.validate(source(layers), **kwargs)

    def test_valid_layer_has_no_errors(self):
        self.assertEqual(self.errors([layer()]), [])

    def test_unknown_class_is_refused(self):
        errors = self.errors([layer(objects=[obj('t01', cls='Land_Not_A_Real_Class')])])
        self.assertTrue(any('Land_Not_A_Real_Class' in e and 'allowlist' in e for e in errors), errors)

    def test_position_outside_map_is_refused(self):
        for x, z in ((-1.0, 100.0), (100.0, 15360.5), (float('nan'), 100.0)):
            errors = self.errors([layer(objects=[obj('t01', x=x, z=z)])])
            self.assertTrue(any('bounds' in e or 'finite' in e for e in errors), (x, z, errors))

    def test_min_spacing_is_enforced_inside_and_across_layers(self):
        close = [obj('t01'), obj('t02', x=2003.0)]
        self.assertTrue(any('spacing' in e for e in self.errors([layer(objects=close)])))
        other = layer('beta-v1', [obj('b01', x=2003.0)])
        errors = self.errors([layer(objects=[obj('t01')]), other])
        self.assertTrue(any('spacing' in e and 'alpha-v1' in e and 'beta-v1' in e for e in errors), errors)

    def test_exact_duplicates_are_reported_as_duplicates(self):
        errors = self.errors([layer(objects=[obj('t01'), obj('t02')])])
        self.assertTrue(any('duplicate' in e for e in errors), errors)

    def test_duplicate_object_ids_and_layer_ids_are_refused(self):
        errors = self.errors([layer(objects=[obj('t01'), obj('t01', x=2100.0)])])
        self.assertTrue(any('object id' in e for e in errors), errors)
        errors = self.errors([layer(), layer()])
        self.assertTrue(any('layer id' in e for e in errors), errors)

    def test_per_layer_cap_comes_from_profile_and_layer(self):
        many = [obj('t%02d' % i, x=2000.0 + 10 * i) for i in range(11)]
        self.assertTrue(any('cap' in e for e in self.errors([layer(objects=many)])))
        capped = layer(objects=[obj('t01'), obj('t02', x=2030.0)], limits={'max_objects': 1})
        self.assertTrue(any('cap' in e for e in self.errors([capped])))

    def test_total_cap_is_enforced(self):
        layers = []
        for n in range(3):
            layers.append(layer('l%d-v1' % n, [obj('o%d_%d' % (n, i), x=100.0 + 500 * n + 10 * i) for i in range(8)]))
        errors = self.errors(layers)
        self.assertTrue(any('total' in e and 'cap' in e for e in errors), errors)

    def test_vanilla_clearance_uses_supplied_positions(self):
        vanilla = [('Land_Mil_Barracks2', 2004.0, 100.0, 3000.0)]
        errors = self.errors([layer(objects=[obj('t01')])], vanilla=vanilla)
        self.assertTrue(any('vanilla' in e and 'Land_Mil_Barracks2' in e for e in errors), errors)
        far = [('Land_Mil_Barracks2', 2040.0, 100.0, 3000.0)]
        self.assertEqual(self.errors([layer(objects=[obj('t01')])], vanilla=far), [])

    def test_loot_intent_needs_a_prototype_group(self):
        wanted = layer(objects=[obj('t01', cls='Land_Medical_Tent_Big')])
        errors = self.errors([wanted], proto_names={'Land_Mil_Tent_Big1_1'})
        self.assertTrue(any('prototype' in e and 'Land_Medical_Tent_Big' in e for e in errors), errors)
        quiet = layer(objects=[obj('t01', cls='Land_Medical_Tent_Big', loot='none')])
        self.assertEqual(self.errors([quiet], proto_names={'Land_Mil_Tent_Big1_1'}), [])

    def test_structural_problems_are_reported_not_raised(self):
        bad = layer()
        bad['version'] = 0
        bad['purpose'] = ''
        bad['objects'][0]['yaw'] = 'north'
        bad['objects'][1]['loot'] = 'sometimes'
        bad['kind'] = 'other'
        errors = self.errors([bad])
        for word in ('version', 'purpose', 'yaw', 'loot', 'kind'):
            self.assertTrue(any(word in e for e in errors), (word, errors))

    def test_unverified_status_must_be_declared(self):
        bad = layer()
        del bad['status']
        self.assertTrue(any('status' in e for e in self.errors([bad])))


class Compose(unittest.TestCase):
    def test_spawner_file_uses_the_engine_schema(self):
        files = mo.compose(source())
        spawner = json.loads(files['objects/alpha-v1.json'])
        self.assertEqual(list(spawner), ['Objects'])
        first = spawner['Objects'][0]
        self.assertEqual(set(first), {'name', 'pos', 'ypr', 'scale', 'enableCEPersistency', 'customString'})
        self.assertEqual(first['name'], 'Land_Mil_Tent_Big1_1')
        self.assertEqual(first['pos'], [2000.0, 100.0, 3000.0])
        self.assertEqual(first['ypr'], [0.0, 0.0, 0.0])
        self.assertEqual(first['scale'], 1.0)
        self.assertIs(first['enableCEPersistency'], False)

    def test_mapgrouppos_rows_follow_the_vanilla_angle_relation(self):
        # Vanilla rows satisfy a = wrap(90 - rpy_z) (checked on the installed mission, never committed).
        files = mo.compose(source([layer(objects=[obj('t01', yaw=180.0), obj('t02', x=2030.0, yaw=0.0),
                                                  obj('t03', x=2060.0, yaw=-90.0, loot='none')])]))
        text = files['mapgrouppos.additions.xml'].decode()
        self.assertIn('<group name="Land_Mil_Tent_Big1_1" pos="2000.000000 100.000000 3000.000000" '
                      'rpy="0.000000 0.000000 -90.000000" a="180.000000" />', text)
        self.assertIn('pos="2030.000000 100.000000 3000.000000" rpy="0.000000 0.000000 90.000000" a="0.000000"', text)
        self.assertNotIn('2060.000000', text)  # loot none: placed, but no CE group row
        self.assertIn('hollow-country-overlays alpha-v1', text)

    def test_output_is_deterministic_and_ordered(self):
        a = source([layer(objects=[obj('t02', x=2030.0), obj('t01')])])
        b = source([layer(objects=[obj('t01'), obj('t02', x=2030.0)])])
        fa, fb = mo.compose(a), mo.compose(b)
        self.assertEqual(fa, fb)
        self.assertEqual(fa, mo.compose(a))
        names = [o['name'] for o in json.loads(fa['objects/alpha-v1.json'])['Objects']]
        self.assertEqual(names, sorted(names))
        xs = [o['pos'][0] for o in json.loads(fa['objects/alpha-v1.json'])['Objects']]
        self.assertEqual(xs, [2000.0, 2030.0])  # ordered by object id, not file order

    def test_manifest_hashes_every_output(self):
        files = mo.compose(source())
        manifest = json.loads(files['manifest.json'])
        self.assertEqual(manifest['kind'], 'hollow-country-overlay-manifest')
        self.assertEqual(manifest['status'], 'runtime-unverified')
        self.assertEqual(manifest['layers'][0]['id'], 'alpha-v1')
        self.assertEqual(manifest['layers'][0]['objects'], 2)
        for name, digest in manifest['outputs'].items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(), digest, name)
        self.assertEqual(set(manifest['outputs']), set(files) - {'manifest.json'})

    def test_only_enabled_layers_are_composed_in_profile_order(self):
        profile = copy.deepcopy(PROFILE)
        profile['enabled'] = ['beta-v1', 'alpha-v1']
        layers = [layer('alpha-v1'), layer('beta-v1', [obj('b01', x=3000.0)]), layer('gamma-v1', [obj('g', x=4000.0)])]
        files = mo.compose(source(layers, profile))
        self.assertEqual(sorted(n for n in files if n.startswith('objects/')),
                         ['objects/alpha-v1.ground.json', 'objects/alpha-v1.json',
                          'objects/beta-v1.ground.json', 'objects/beta-v1.json'])
        manifest = json.loads(files['manifest.json'])
        self.assertEqual([l['id'] for l in manifest['layers']], ['beta-v1', 'alpha-v1'])

    def test_compose_refuses_an_invalid_source(self):
        with self.assertRaises(ValueError):
            mo.compose(source([layer(objects=[obj('t01', cls='Nope')])]))


GROUND = {
    'kind': 'hollow-country-overlay-ground-contact',
    'classes': {
        'Land_Mil_Tent_Big1_1': {'contact_low_m': 0.0, 'geometry_low_m': -0.8},
        'Land_Mil_Tent_Big1_2': {'contact_low_m': -0.4, 'geometry_low_m': -0.4},
        'Land_Medical_Tent_Big': {'contact_low_m': 0.3, 'geometry_low_m': 0.3},
    },
    'unmeasured': [],
}


def grounded(objects, ground=GROUND):
    src = source([layer(objects=objects)])
    src.ground = copy.deepcopy(ground)
    return src


class GroundContact(unittest.TestCase):
    """wh-ground: the visible bottom must sit within 0.15 m of the ground (offline half of HCGroundSnap.Place)."""

    def test_classification_uses_the_authored_embed_as_allowance(self):
        self.assertEqual(mo.ground_class(0.0, 0.0), 'OK')
        self.assertEqual(mo.ground_class(-0.4, 0.0), 'OK')        # the model embeds itself 0.4 m by design
        self.assertEqual(mo.ground_class(-0.4, -0.1), 'OK')       # the pivot may sink 0.15 m below the ground
        self.assertEqual(mo.ground_class(-0.4, -0.2), 'sunk')
        self.assertEqual(mo.ground_class(0.3, 0.0), 'floating')   # visible bottom 0.3 m above the pivot
        self.assertEqual(mo.ground_class(0.3, -0.3), 'OK')
        self.assertEqual(mo.ground_class(0.0, 0.2), 'floating')

    def test_validate_reports_floating_sunk_and_unknown_classes(self):
        objects = [obj('t01', cls='Land_Medical_Tent_Big'), obj('t02', x=2030.0, cls='Land_Mil_Tent_Big1_1'),
                   obj('t03', x=2060.0, cls='Land_Mil_Tent_Big1_2')]
        errors = mo.validate(grounded(objects))
        self.assertTrue(any('t01' in e and 'floating' in e for e in errors), errors)
        self.assertFalse(any('t02' in e or 't03' in e for e in errors), errors)
        unknown = mo.validate(grounded([obj('t01', cls='Land_Mil_Tent_Big1_1')], {'classes': {}, 'unmeasured': []}))
        self.assertTrue(any('no ground-contact data' in e for e in unknown), unknown)
        listed = mo.validate(grounded([obj('t01', cls='Land_Mil_Tent_Big1_1')],
                                      {'classes': {}, 'unmeasured': ['Land_Mil_Tent_Big1_1']}))
        self.assertFalse(any('ground' in e for e in listed), listed)

    def test_composition_dy_is_judged_against_the_class_contact(self):
        src = grounded([])
        src.compositions = {'kind': mo.COMPOSITIONS_KIND, 'compositions': {'c': {'pieces': [
            {'class': 'Land_Medical_Tent_Big', 'loot': 'none', 'dx': 0, 'dz': 0, 'yaw': 0, 'dy': -0.3}]}}}
        src.layers[0]['sites'] = [{'id': 's1', 'composition': 'c', 'pos': [2000.0, 100.0, 3000.0], 'heading': 0.0,
                                   'area': 'synthetic'}]
        self.assertFalse([e for e in mo.validate(src) if 'floating' in e or 'sunk' in e])
        src.compositions['compositions']['c']['pieces'][0]['dy'] = 0.0
        self.assertTrue([e for e in mo.validate(src) if 'floating' in e])

    def test_compose_writes_an_index_aligned_ground_sidecar(self):
        files = mo.compose(grounded([obj('t02', x=2030.0, cls='Land_Mil_Tent_Big1_2', loot='none'),
                                     obj('t01', cls='Land_Mil_Tent_Big1_1')]))
        side = json.loads(files['objects/alpha-v1.ground.json'])
        spawner = json.loads(files['objects/alpha-v1.json'])
        self.assertEqual(len(side['Ground']), len(spawner['Objects']))
        self.assertEqual(side['Ground'][0], {'pivot': 0.0, 'embed': 0.0, 'loot': 1})
        self.assertEqual(side['Ground'][1], {'pivot': 0.0, 'embed': 0.4, 'loot': 0})
        self.assertEqual(files['objects/alpha-v1.ground.json'], mo.compose(grounded([
            obj('t02', x=2030.0, cls='Land_Mil_Tent_Big1_2', loot='none'),
            obj('t01', cls='Land_Mil_Tent_Big1_1')]))['objects/alpha-v1.ground.json'])
        self.assertIn('objects/alpha-v1.ground.json', json.loads(files['manifest.json'])['outputs'])

    def test_repository_layers_are_all_within_tolerance(self):
        real = mo.load_source(SOURCE)
        self.assertIsNotNone(real.ground)
        self.assertEqual(mo.ground_table(real)[2], [])
        # The pre-wh-ground runtime put the geometry bottom on the ground; the tents, camo nets and the BMP
        # wreck then floated. That reference must keep being reported so the data cannot regress unnoticed.
        floating = mo.ground_table(real, 'geometry')[2]
        self.assertTrue(any(row[2] == 'StaticObj_Mil_CamoNet_Side_east' for row in floating))
        report = mo.ground_report(real)
        self.assertIn('outside tolerance: 0', report)


class InstallRollback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Clear of the synthetic vanilla barracks at (2000, 3000): the install path checks real clearance.
        self.src = source([layer(objects=[obj('t01', x=2100.0), obj('t02', x=2130.0)])])
        self.root = mission(self.tmp.name)

    def test_install_patches_both_files_and_rollback_is_byte_exact(self):
        before = tree_bytes(self.root)
        mo.install(self.src, self.root)
        gameplay = json.loads((self.root / 'cfggameplay.json').read_text())
        self.assertEqual(gameplay['WorldsData']['objectSpawnersArr'], ['hollow-country-overlays/objects/alpha-v1.json'])
        self.assertEqual(gameplay['version'], 123)
        self.assertEqual(gameplay['WorldsData']['environmentMinTemps'], [-5, -4])
        spawner = json.loads((self.root / 'hollow-country-overlays/objects/alpha-v1.json').read_text())
        self.assertEqual(len(spawner['Objects']), 2)
        pos = (self.root / 'mapgrouppos.xml').read_text()
        self.assertTrue(pos.startswith(POS_XML[:POS_XML.index('</map>')]))
        self.assertEqual(pos.count('<group name="Land_Mil_Tent_Big1_1"'), 2)
        self.assertTrue(pos.rstrip().endswith('</map>'))
        manifest = json.loads((self.root / 'hollow-country-overlays/manifest.json').read_text())
        self.assertEqual(manifest['layers'][0]['id'], 'alpha-v1')
        mo.rollback(self.root)
        self.assertEqual(tree_bytes(self.root), before)

    def test_install_keeps_existing_object_spawner_entries(self):
        gameplay = GAMEPLAY.replace('"objectSpawnersArr": []', '"objectSpawnersArr": ["other/mine.json"]')
        root = mission(self._sub('b'), gameplay=gameplay)
        mo.install(self.src, root)
        arr = json.loads((root / 'cfggameplay.json').read_text())['WorldsData']['objectSpawnersArr']
        self.assertEqual(arr, ['other/mine.json', 'hollow-country-overlays/objects/alpha-v1.json'])
        mo.rollback(root)
        self.assertEqual((root / 'cfggameplay.json').read_text(), gameplay)

    def _sub(self, name):
        path = Path(self.tmp.name) / name
        path.mkdir()
        return path

    def test_second_install_is_refused_without_changes(self):
        mo.install(self.src, self.root)
        after = tree_bytes(self.root)
        with self.assertRaises(ValueError):
            mo.install(self.src, self.root)
        self.assertEqual(tree_bytes(self.root), after)

    def test_invalid_layer_changes_nothing(self):
        before = tree_bytes(self.root)
        bad = source([layer(objects=[obj('t01', x=2004.0)])])  # inside the 8 m clearance of the vanilla barracks
        with self.assertRaises(ValueError) as caught:
            mo.install(bad, self.root)
        self.assertIn('vanilla', str(caught.exception))
        self.assertEqual(tree_bytes(self.root), before)

    def test_missing_gameplay_or_pos_file_is_refused_without_changes(self):
        (self.root / 'cfggameplay.json').unlink()
        before = tree_bytes(self.root)
        with self.assertRaises(ValueError):
            mo.install(self.src, self.root)
        self.assertEqual(tree_bytes(self.root), before)

    def test_rollback_refuses_drift_and_changes_nothing(self):
        mo.install(self.src, self.root)
        (self.root / 'cfggameplay.json').write_text('{"version": 124, "WorldsData": {"objectSpawnersArr": []}}\n')
        before = tree_bytes(self.root)
        with self.assertRaises(ValueError):
            mo.rollback(self.root)
        self.assertEqual(tree_bytes(self.root), before)

    def test_rollback_without_install_is_refused(self):
        with self.assertRaises(ValueError):
            mo.rollback(self.root)

    def test_rollback_inputs_name_the_two_patched_files(self):
        self.assertEqual(set(mo.INPUTS), {'cfggameplay.json', 'mapgrouppos.xml'})

    def test_install_refuses_a_steam_installation_path(self):
        steam = Path(self.tmp.name) / 'steamapps' / 'mission'
        steam.mkdir(parents=True)
        (steam / 'cfgeconomycore.xml').write_text(CORE)
        with self.assertRaises(ValueError):
            mo.install(self.src, steam)


class VanillaReaders(unittest.TestCase):
    def test_read_vanilla_streams_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = mission(tmp)
            groups = mo.read_vanilla(root)
            self.assertEqual(groups[0], ('Land_Mil_Barracks2', 2000.0, 100.0, 3000.0))
            self.assertEqual(len(groups), 2)
            self.assertEqual(mo.read_proto_names(root), {'Land_Mil_Tent_Big1_1', 'Land_Mil_Tent_Big1_2'})

    def test_server_class_check_reads_installed_addons(self):
        with tempfile.TemporaryDirectory() as tmp:
            addons = Path(tmp) / 'addons'
            addons.mkdir()
            (addons / 'structures_military.pbo').write_bytes(b'\0Land_Mil_Tent_Big1_1\0Land_Mil_Tent_Big1_2\0')
            (addons / 'structures_residential.pbo').write_bytes(b'\0Land_Other\0')
            missing = mo.missing_classes_in_server(Path(tmp), CLASSES)
            self.assertEqual(missing, ['Land_Medical_Tent_Big'])


class SuggestSites(unittest.TestCase):
    def synthetic_base(self, cx, cz, tents=0, count=8):
        rows = []
        for i in range(count):
            rows.append(('Land_Mil_Barracks2', cx + 25.0 * (i % 4), 50.0, cz + 25.0 * (i // 4)))
        for i in range(tents):
            rows.append(('Land_Mil_Tent_Big1_1', cx + 100.0 + 12 * i, 50.0, cz))
        return rows

    def test_only_tent_poor_clusters_get_sites_and_rules_hold(self):
        rows = (self.synthetic_base(2000.0, 2000.0) + self.synthetic_base(9000.0, 9000.0, tents=6)
                + [('Land_House_1W12_Brown', 5000.0, 10.0, 5000.0)])
        sites = mo.suggest_sites(rows, per_cluster=2, max_total=12)
        self.assertEqual(len(sites), 2)
        for site in sites:
            self.assertLess(abs(site['pos'][0] - 2000.0), 400.0)
            for _name, x, y, z in rows:
                self.assertGreaterEqual(((site['pos'][0] - x) ** 2 + (site['pos'][2] - z) ** 2) ** 0.5, 12.0)
            self.assertIn(site['yaw'], (0.0, 180.0))
        self.assertGreaterEqual(((sites[0]['pos'][0] - sites[1]['pos'][0]) ** 2
                                 + (sites[0]['pos'][2] - sites[1]['pos'][2]) ** 2) ** 0.5, 15.0)
        self.assertEqual(sites, mo.suggest_sites(list(reversed(rows)), per_cluster=2, max_total=12))

    def test_max_total_caps_the_result(self):
        rows = []
        for n in range(5):
            rows += self.synthetic_base(1000.0 + 1500.0 * n, 2000.0)
        self.assertEqual(len(mo.suggest_sites(rows, per_cluster=2, max_total=3)), 3)

    def test_sloped_candidates_are_skipped(self):
        rows = self.synthetic_base(2000.0, 2000.0)
        rows = [(n, x, 50.0 + 9.0 * (i % 2), z) for i, (n, x, _y, z) in enumerate(rows)]
        self.assertEqual(mo.suggest_sites(rows, per_cluster=2, max_total=12), [])


class ShippedLayer(unittest.TestCase):
    def setUp(self):
        self.source = mo.load_source(SOURCE)

    def test_shipped_source_validates_offline(self):
        self.assertEqual(mo.validate(self.source), [])

    def test_example_layer_is_small_authored_and_marked_unverified(self):
        by_id = {l['id']: l for l in self.source.layers}
        tents = by_id['military-tents-v1']
        self.assertTrue(6 <= len(tents['objects']) <= 12, len(tents['objects']))
        self.assertEqual(tents['status'], 'runtime-unverified')
        self.assertIn('military-tents-v1', self.source.profile['enabled'])
        self.assertTrue(tents['basis']['rule'])
        self.assertRegex(tents['basis']['inventory']['mapgrouppos_sha256'], r'^[0-9a-f]{64}$')
        for item in tents['objects']:
            self.assertIn(item['yaw'], (0.0, 180.0))
            self.assertEqual(item['loot'], 'proto')
            self.assertTrue(item['y_basis'])

    def test_allowlist_records_provenance_and_is_not_a_dump(self):
        self.assertIn('structures_military.pbo', json.dumps(self.source.classes['provenance']))
        self.assertLess(len(self.source.classes['classes']), 120)  # an allowlist of reviewed names, not a dump

    def test_shipped_files_carry_no_banned_strings_or_home_paths(self):
        banned = ('snafu', 'tactical' + 'flava', '2646817942', '2291785308', '2792982069', '/home/', '/mnt/')
        for path in sorted(SOURCE.rglob('*')):
            if path.is_file():
                text = path.read_text().lower()
                for word in banned:
                    self.assertNotIn(word, text, (path.name, word))

    def test_shipped_compose_is_deterministic(self):
        self.assertEqual(mo.compose(self.source), mo.compose(mo.load_source(SOURCE)))

    def test_cli_validate_succeeds(self):
        done = subprocess.run([sys.executable, '-I', str(REPO / 'tools/package/map_overlay.py'), 'validate'],
                              capture_output=True, text=True, cwd=REPO)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('military-tents-v1', done.stdout)


if __name__ == '__main__':
    unittest.main()
