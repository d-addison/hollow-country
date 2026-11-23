"""Behavior of overlay compositions (reusable authored layouts), site planning, the report and the map image.

Every fixture here is SYNTHETIC: real class names, invented positions and heights. Offline tests never establish
DayZ behavior: spawning, ground contact, orientation convention, model sizes and loot stay pending native testing.
"""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.package import map_overlay as mo  # noqa: E402

SOURCE = REPO / 'config/map-overlays'

CLASSES = {
    'kind': 'hollow-country-overlay-classes',
    'provenance': {'source': 'synthetic test allowlist', 'method': 'invented', 'verified': 'none'},
    'classes': {
        'StaticObj_Misc_BagFence_3m': {'pbo': 'structures_military.pbo', 'kind': 'prop', 'loot_group': False,
                                       'role': 'wall', 'length_m': 3.0},
        'Land_Mil_GuardShed': {'pbo': 'structures_military.pbo', 'kind': 'building', 'loot_group': True,
                               'role': 'shed'},
        'Land_Container_1Mo': {'pbo': 'structures_industrial.pbo', 'kind': 'container', 'loot_group': True,
                               'role': 'container', 'length_m': 12.0},
    },
}
COMPOSITIONS = {
    'kind': 'hollow-country-overlay-compositions',
    'compositions': {
        'mini-post': {
            'theme': 'checkpoint', 'purpose': 'synthetic two-wall post with a guard shed and a clear lane',
            'clear': [{'x': [-1.5, 1.5], 'z': [-12.0, 12.0]}],
            'pieces': [
                {'class': 'StaticObj_Misc_BagFence_3m', 'dx': -4.0, 'dz': 0.0, 'yaw': 0.0, 'loot': 'none'},
                {'class': 'StaticObj_Misc_BagFence_3m', 'dx': 4.0, 'dz': 0.0, 'yaw': 0.0, 'loot': 'none'},
                {'class': 'Land_Mil_GuardShed', 'dx': 9.0, 'dz': -3.0, 'yaw': 90.0, 'loot': 'proto'},
            ],
        },
    },
}
PROFILE = {
    'kind': 'hollow-country-overlay-profile',
    'enabled': ['post-v1'],
    'limits': {'map_size': 15360, 'max_objects_total': 40, 'max_objects_per_layer': 20, 'min_spacing_m': 6.0,
               'vanilla_clearance_m': 8.0, 'piece_spacing_m': 1.0, 'piece_vanilla_clearance_m': 12.0,
               'flat_radius_m': 60.0, 'flat_spread_m': 1.2, 'flat_min_rows': 3, 'flat_site_tolerance_m': 0.8,
               'max_loot_total': 6, 'max_loot_per_layer': 4},
}


def site(ident='s01', cx=2000.0, cz=3000.0, y=50.0, heading=0.0, comp='mini-post'):
    return {'id': ident, 'composition': comp, 'pos': [cx, y, cz], 'heading': heading, 'area': 'synthetic',
            'y_basis': 'synthetic'}


def layer(sites=None, ident='post-v1', **extra):
    data = {'kind': 'hollow-country-map-overlay', 'id': ident, 'version': 1, 'purpose': 'synthetic sites',
            'status': 'runtime-unverified', 'theme': 'checkpoint', 'objects': [],
            'sites': sites if sites is not None else [site()]}
    data.update(extra)
    return data


def source(layers=None, profile=None, comps=None, classes=None):
    return mo.Source(copy.deepcopy(profile or PROFILE), copy.deepcopy(classes or CLASSES),
                     [copy.deepcopy(l) for l in (layers if layers is not None else [layer()])],
                     copy.deepcopy(comps or COMPOSITIONS))


def flat_rows(cx, cz, y=50.0, count=12, spread=0.0):
    """Synthetic vanilla rows on a ring 40 m out (far from every piece), at height y."""
    rows = []
    for i in range(count):
        angle = 2 * math.pi * i / count
        rows.append(('Land_House_1W12_Brown', cx + 40.0 * math.sin(angle), y + spread * (i % 2),
                     cz + 40.0 * math.cos(angle)))
    return rows


class Expand(unittest.TestCase):
    def test_heading_zero_maps_offsets_to_east_and_north(self):
        objects = mo.expand_layer(source(), layer())
        by = {o['id']: o for o in objects}
        self.assertEqual(sorted(by), ['s01-p01', 's01-p02', 's01-p03'])
        self.assertEqual(by['s01-p01']['pos'], [1996.0, 50.0, 3000.0])
        self.assertEqual(by['s01-p02']['pos'], [2004.0, 50.0, 3000.0])
        self.assertEqual(by['s01-p03']['pos'], [2009.0, 50.0, 2997.0])
        self.assertEqual(by['s01-p03']['yaw'], 90.0)
        self.assertEqual(by['s01-p03']['loot'], 'proto')
        self.assertTrue(all(o['site'] == 's01' for o in objects))

    def test_heading_ninety_turns_forward_to_east_and_adds_to_yaw(self):
        objects = {o['id']: o for o in mo.expand_layer(source(), layer([site(heading=90.0)]))}
        # offset (dx=9, dz=-3) at compass heading 90: forward is east, right is south
        self.assertAlmostEqual(objects['s01-p03']['pos'][0], 2000.0 - 3.0, places=5)
        self.assertAlmostEqual(objects['s01-p03']['pos'][2], 3000.0 - 9.0, places=5)
        self.assertEqual(objects['s01-p03']['yaw'], 180.0)
        self.assertEqual(objects['s01-p01']['yaw'], 90.0)

    def test_expansion_is_deterministic_and_keeps_explicit_objects(self):
        explicit = {'id': 'x01', 'class': 'Land_Container_1Mo', 'pos': [100.0, 10.0, 100.0], 'yaw': 0.0,
                    'loot': 'proto', 'area': 'synthetic'}
        data = layer()
        data['objects'] = [explicit]
        a = mo.expand_layer(source([data]), data)
        self.assertEqual(a, mo.expand_layer(source([data]), copy.deepcopy(data)))
        self.assertEqual(a[0]['id'], 'x01')
        self.assertEqual(len(a), 4)

    def test_unknown_composition_and_duplicate_site_ids_are_reported(self):
        errors = mo.validate(source([layer([site(comp='nope')])]))
        self.assertTrue(any('composition' in e and 'nope' in e for e in errors), errors)
        errors = mo.validate(source([layer([site('s01'), site('s01', cx=2200.0)])]))
        self.assertTrue(any('site id' in e for e in errors), errors)

    def test_bad_heading_or_position_is_reported(self):
        for bad in ({'heading': float('nan')}, {'heading': 'north'}):
            data = site()
            data.update(bad)
            self.assertTrue(any('heading' in e for e in mo.validate(source([layer([data])]))), bad)
        data = site(cx=-5.0)
        self.assertTrue(any('bounds' in e for e in mo.validate(source([layer([data])]))))


class SiteValidation(unittest.TestCase):
    def errors(self, layers=None, rows=None, **kwargs):
        return mo.validate(source(layers), vanilla=rows, **kwargs)

    def test_valid_site_has_no_errors_on_flat_ground(self):
        self.assertEqual(self.errors(rows=flat_rows(2000.0, 3000.0)), [])

    def test_every_piece_is_checked_against_vanilla_not_just_the_centre(self):
        rows = flat_rows(2000.0, 3000.0) + [('Land_Mil_Barracks2', 2009.0, 50.0, 2990.0)]  # 7 m from the shed piece
        errors = self.errors(rows=rows)
        self.assertTrue(any('s01-p03' in e and 'Land_Mil_Barracks2' in e for e in errors), errors)
        self.assertFalse(any('s01-p01' in e and 'vanilla' in e for e in errors), errors)

    def test_pieces_in_one_site_may_be_close_but_other_sites_keep_the_spacing(self):
        close_inside = layer([site(), site('s02', cx=2100.0)])
        self.assertEqual(self.errors([close_inside]), [])
        touching = layer([site(), site('s02', cx=2004.0 + 3.0)])  # s02 wall lands 3 m from s01 wall
        errors = self.errors([touching])
        self.assertTrue(any('spacing' in e and 's01' in e and 's02' in e for e in errors), errors)

    def test_pieces_of_one_site_cannot_share_a_position(self):
        comps = copy.deepcopy(COMPOSITIONS)
        comps['compositions']['mini-post']['pieces'][1].update(dx=-4.0)
        errors = mo.validate(source(comps=comps))
        self.assertTrue(any('duplicate' in e or 'spacing' in e for e in errors), errors)

    def test_whole_footprint_must_be_flat(self):
        # one ring row near the shed piece sits 3 m higher: the footprint spans too much height
        rows = flat_rows(2000.0, 3000.0)
        rows[0] = (rows[0][0], rows[0][1], 53.0, rows[0][3])
        errors = self.errors(rows=rows)
        self.assertTrue(any('flat' in e for e in errors), errors)

    def test_each_piece_needs_its_own_height_support_near_the_site_height(self):
        # shed piece stands 9 m east of the centre; give it only far-away neighbours at another height
        rows = flat_rows(2000.0, 3000.0)
        rows = [r for r in rows if r[1] < 2020.0] + [('Land_House_1W12_Brown', 2060.0 + 2 * i, 56.0, 2990.0)
                                                   for i in range(4)]
        errors = self.errors(rows=rows)
        self.assertTrue(any('flat' in e and 's01-p03' in e for e in errors), errors)

    def test_site_height_must_match_the_footprint_support(self):
        errors = self.errors([layer([site(y=58.0)])], rows=flat_rows(2000.0, 3000.0))
        self.assertTrue(any('flat' in e and 'height' in e for e in errors), errors)

    def test_pivot_dy_does_not_move_the_flat_basis(self):
        # #336: a piece's pivot compensation (dy) raises its spawn height, not the ground it stands on
        comps = copy.deepcopy(COMPOSITIONS)
        comps['compositions']['mini-post']['pieces'][2]['dy'] = 1.1
        self.assertEqual(mo.validate(source(comps=comps), vanilla=flat_rows(2000.0, 3000.0)), [])
        self.assertIsNotNone(mo.place_site(source(comps=comps), 'mini-post', 2000.0, 3000.0, 0.0,
                                           flat_rows(2000.0, 3000.0)))
        # the site height itself is still checked against the support
        errors = mo.validate(source([layer([site(y=58.0)])], comps=comps), vanilla=flat_rows(2000.0, 3000.0))
        self.assertTrue(any('flat' in e and 'height' in e for e in errors), errors)

    def test_clear_lane_is_enforced_inside_a_composition(self):
        comps = copy.deepcopy(COMPOSITIONS)
        comps['compositions']['mini-post']['pieces'][0].update(dx=0.5)
        errors = mo.validate(source(comps=comps))
        self.assertTrue(any('clear' in e and 'mini-post' in e for e in errors), errors)

    def test_loot_caps_keep_loot_scarce(self):
        comps = copy.deepcopy(COMPOSITIONS)
        pieces = comps['compositions']['mini-post']['pieces']
        pieces.append({'class': 'Land_Mil_GuardShed', 'dx': 9.0, 'dz': 6.0, 'yaw': 90.0, 'loot': 'proto'})
        sites = [site('s%02d' % n, cx=2000.0 + 60.0 * n) for n in range(3)]
        errors = mo.validate(source([layer(sites)], comps=comps))
        self.assertTrue(any('loot' in e and 'cap' in e for e in errors), errors)  # 6 loot > per-layer 4

    def test_loot_on_a_class_without_a_loot_group_is_refused_offline(self):
        comps = copy.deepcopy(COMPOSITIONS)
        comps['compositions']['mini-post']['pieces'][0]['loot'] = 'proto'
        errors = mo.validate(source(comps=comps))
        self.assertTrue(any('loot group' in e and 'StaticObj_Misc_BagFence_3m' in e for e in errors), errors)

    def test_composition_structure_errors_are_reported_not_raised(self):
        comps = copy.deepcopy(COMPOSITIONS)
        del comps['compositions']['mini-post']['purpose']
        comps['compositions']['mini-post']['pieces'][0]['class'] = 'Land_Not_Real'
        errors = mo.validate(source(comps=comps))
        self.assertTrue(any('purpose' in e for e in errors), errors)
        self.assertTrue(any('Land_Not_Real' in e and 'allowlist' in e for e in errors), errors)

    def test_compose_includes_site_pieces_in_spawner_and_loot_rows(self):
        files = mo.compose(source())
        spawner = json.loads(files['objects/post-v1.json'])
        self.assertEqual(len(spawner['Objects']), 3)
        text = files['mapgrouppos.additions.xml'].decode()
        self.assertEqual(text.count('<group name="Land_Mil_GuardShed"'), 1)
        self.assertNotIn('BagFence', text)  # props without a loot group get no CE row
        manifest = json.loads(files['manifest.json'])
        self.assertEqual(manifest['layers'][0]['sites'], 1)
        self.assertEqual(manifest['layers'][0]['objects'], 3)


class PlaceSite(unittest.TestCase):
    def setUp(self):
        self.src = source()

    def test_places_on_flat_ground_with_support_height(self):
        placed = mo.place_site(self.src, 'mini-post', 2000.0, 3000.0, 0.0, flat_rows(2000.0, 3000.0))
        self.assertEqual(placed['composition'], 'mini-post')
        self.assertEqual(placed['pos'], [2000.0, 50.0, 3000.0])
        self.assertIn('vanilla rows', placed['y_basis'])

    def test_refuses_slope_clearance_and_lack_of_support(self):
        sloped = flat_rows(2000.0, 3000.0, spread=3.0)
        self.assertIsNone(mo.place_site(self.src, 'mini-post', 2000.0, 3000.0, 0.0, sloped))
        blocked = flat_rows(2000.0, 3000.0) + [('Land_Mil_Barracks2', 1996.0, 50.0, 3004.0)]
        self.assertIsNone(mo.place_site(self.src, 'mini-post', 2000.0, 3000.0, 0.0, blocked))
        self.assertIsNone(mo.place_site(self.src, 'mini-post', 2000.0, 3000.0, 0.0, flat_rows(2000.0, 3000.0)[:2]))

    def test_refuses_pieces_that_overlap_already_taken_positions(self):
        taken = [(2005.0, 3000.0)]
        self.assertIsNone(mo.place_site(self.src, 'mini-post', 2000.0, 3000.0, 0.0,
                                        flat_rows(2000.0, 3000.0), taken=taken))


def base_rows(cx, cz, y=50.0):
    """A synthetic base (12 barracks in a block) with a ring of houses 500 m to the east."""
    rows = [('Land_Mil_Barracks2', cx + 22.0 * (i % 4), y, cz + 22.0 * (i // 4)) for i in range(12)]
    rows += [('Land_House_1W12_Brown', cx + 500.0 + 15.0 * i, y, cz + 10.0 * (i % 3)) for i in range(10)]
    return rows


class PlanLayers(unittest.TestCase):
    def setUp(self):
        self.profile = copy.deepcopy(PROFILE)
        self.profile['limits'].update(max_objects_total=200, max_objects_per_layer=80, max_loot_total=40,
                                      max_loot_per_layer=20)
        self.profile['enabled'] = ['military-outposts-v1']
        self.comps = json.loads((SOURCE / 'compositions.json').read_text())
        self.classes = json.loads((SOURCE / 'classes.json').read_text())
        self.src = mo.Source(self.profile, self.classes, [], self.comps)
        self.rows = base_rows(2000.0, 3000.0)

    def test_outposts_face_outward_toward_the_nearest_settlement(self):
        layers = mo.plan_layers(self.src, self.rows, per_cluster=3, max_outposts=4)
        outposts = layers['military-outposts-v1']
        self.assertGreaterEqual(len(outposts['sites']), 1)
        for placed in outposts['sites']:
            if placed['composition'] == 'comms-post':
                self.assertTrue(placed['pos'][0] < 2033.0, placed)  # behind the block, away from the houses
            else:
                self.assertTrue(placed['pos'][0] > 2033.0, placed)  # east of the block, toward the houses
            self.assertLess(abs(mo.wrap(placed['heading'] - 90.0)), 60.0, placed)

    def test_planned_layers_validate_against_the_same_vanilla_rows_and_are_deterministic(self):
        layers = mo.plan_layers(self.src, self.rows, per_cluster=3, max_outposts=4)
        again = mo.plan_layers(self.src, list(reversed(self.rows)), per_cluster=3, max_outposts=4)
        self.assertEqual(layers, again)
        self.profile['enabled'] = sorted(layers)
        src = mo.Source(self.profile, self.classes, list(layers.values()), self.comps)
        self.assertEqual(mo.validate(src, vanilla=self.rows), [])

    def test_roadside_posts_anchor_on_standalone_guardhouses(self):
        rows = self.rows + [('Land_Mil_Guardhouse1', 3000.0 + 4.0 * i, 50.0, 6000.0 + 3.0 * i) for i in range(1)]
        rows += [('Land_House_1W12_Brown', 3000.0 + 30.0 * i, 50.0, 6030.0) for i in range(8)]
        layers = mo.plan_layers(self.src, rows, per_cluster=3, max_outposts=4)
        roadside = layers['roadside-checkpoints-v1']
        self.assertEqual(len(roadside['sites']), 1)
        self.assertLess(math.hypot(roadside['sites'][0]['pos'][0] - 3000.0, roadside['sites'][0]['pos'][2] - 6000.0),
                        60.0)


class ReportAndImage(unittest.TestCase):
    def test_report_lists_each_site_with_centre_theme_pieces_and_loot(self):
        text = mo.report(source(), as_text=True)
        self.assertIn('post-v1', text)
        self.assertIn('s01', text)
        self.assertIn('checkpoint', text)
        self.assertIn('2000', text)
        data = mo.report(source())
        row = data['layers'][0]['sites'][0]
        self.assertEqual((row['pieces'], row['loot']), (3, 1))
        self.assertEqual(data['totals'], {'objects': 3, 'loot': 1, 'sites': 1})

    def test_png_is_a_valid_deterministic_image_and_marks_additions(self):
        rows = flat_rows(2000.0, 3000.0) + [('Land_Mil_Barracks2', 2300.0, 50.0, 3300.0)]
        a = mo.render_png(source(), rows, size=200, window=None)
        self.assertEqual(a[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(a, mo.render_png(source(), rows, size=200, window=None))
        zoom = mo.render_png(source(), rows, size=120, window=(2000.0, 3000.0, 40.0))
        self.assertEqual(zoom[:8], b'\x89PNG\r\n\x1a\n')
        self.assertNotEqual(a, zoom)


class ShippedComposition(unittest.TestCase):
    def setUp(self):
        self.source = mo.load_source(SOURCE)

    def test_shipped_source_validates_offline(self):
        self.assertEqual(mo.validate(self.source), [])

    def test_all_named_compositions_exist_and_read_as_designed_areas(self):
        names = set(self.source.compositions['compositions'])
        self.assertTrue({'checkpoint', 'forward-outpost', 'supply-dump', 'field-hospital', 'mg-nest', 'comms-post',
                         'tent-camp'} <= names, names)
        for name, comp in self.source.compositions['compositions'].items():
            self.assertGreaterEqual(len(comp['pieces']), 6, name)
            self.assertLessEqual(len(comp['pieces']), 24, name)
            self.assertTrue(comp['purpose'].strip() and comp['theme'].strip(), name)
            roles = {self.source.classes['classes'][p['class']].get('role') for p in comp['pieces']}
            self.assertGreaterEqual(len(roles), 3, (name, roles))  # perimeter, cover and a focus, not one repeat
            self.assertTrue(any(p['loot'] == 'proto' for p in comp['pieces']) or name in ('mg-nest', 'checkpoint',
                                                                                             'comms-post'), name)

    def test_shipped_layers_exist_each_themed_and_within_budget(self):
        layers = {l['id']: l for l in self.source.layers}
        for ident in ('military-tents-v1', 'military-outposts-v1', 'supply-dumps-v1', 'roadside-checkpoints-v1'):
            self.assertIn(ident, layers)
            self.assertEqual(layers[ident]['status'], 'runtime-unverified')
            self.assertTrue(layers[ident].get('theme'), ident)
            self.assertIn(ident, self.source.profile['enabled'])
        data = mo.report(self.source)
        self.assertLessEqual(data['totals']['objects'], self.source.profile['limits']['max_objects_total'])
        self.assertLessEqual(data['totals']['loot'], self.source.profile['limits']['max_loot_total'])
        for entry in data['layers']:
            self.assertLessEqual(entry['loot'], self.source.profile['limits']['max_loot_per_layer'], entry['id'])

    def test_loot_only_uses_vanilla_groups_and_no_firearm_classes(self):
        for layer_data in self.source.layers:
            for obj in mo.expand_layer(self.source, layer_data):
                info = self.source.classes['classes'][obj['class']]
                if obj['loot'] == 'proto':
                    self.assertTrue(info.get('loot_group'), obj)
                self.assertNotIn('weapon', obj['class'].lower())

    def test_shipped_classes_record_provenance_for_props(self):
        provenance = self.source.classes['provenance']
        text = json.dumps(provenance)
        for pbo in ('structures_military.pbo', 'structures_industrial.pbo', 'structures_wrecks.pbo'):
            self.assertIn(pbo, text)
        for name, info in self.source.classes['classes'].items():
            self.assertIn(info['kind'], ('prop', 'building', 'container', 'tent', 'wreck'), name)
            self.assertIsInstance(info['loot_group'], bool, name)
        self.assertLess(len(self.source.classes['classes']), 120)

    def test_no_banned_strings_or_home_paths_in_shipped_files(self):
        banned = ('snafu', 'tactical' + 'flava', '2646817942', '2291785308', '2792982069', '/home/', '/mnt/')
        for path in sorted(SOURCE.rglob('*.json')):
            text = path.read_text().lower()
            for word in banned:
                self.assertNotIn(word, text, path.name)

    def test_cli_report_succeeds(self):
        done = subprocess.run([sys.executable, '-I', str(REPO / 'tools/package/map_overlay.py'), 'report'],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('military-outposts-v1', done.stdout)


if __name__ == '__main__':
    unittest.main()
