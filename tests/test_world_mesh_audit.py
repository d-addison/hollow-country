"""Synthetic world-mesh inputs only; no installed assets or native processes."""
import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.audit import world_mesh_audit as audit


def lod(resolution, vertices=(), faces=(), selections=(), sections=()):
    return NS(resolution=resolution, vertices=list(vertices), faces=list(faces),
              named_selections=list(selections), sections=list(sections), index=0)


def model(*lods, center=(0, 0, 0)):
    return NS(lods=list(lods), bounding_center=center)


def cube(low=(-.2, 0, -.2), high=(.2, .4, .2)):
    vertices = list(audit.corners((low, high)))
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return lod(audit.GEOMETRY, vertices, faces)


def prop(geometry=None, visuals=None, view=True):
    geometry = geometry if geometry is not None else cube()
    lods = [geometry]
    if view:
        lods.append(lod(audit.VIEW_GEOMETRY, geometry.vertices, geometry.faces))
    lods.extend(visuals if visuals is not None else [lod(1, geometry.vertices, geometry.faces)])
    return model(*lods)


class Installed:
    visual_available = True

    def __init__(self, models):
        self.models = models

    def model(self, name, host=False):
        return self.models.get(name)


class WorldMeshAuditTests(unittest.TestCase):
    def write(self, root, path, data):
        path = root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def test_discovery_all_data_families_and_transforms(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prefix = 'config/map-overlays/'
            piece = {'class': 'Crate', 'dx': 2, 'dz': 0, 'dy': .5, 'yaw': 15, 'loot': 'none'}
            self.write(root, prefix+'profile.json', {'enabled_layers': []})
            self.write(root, prefix+'classes.json', {'classes': {'Crate': {}}})
            self.write(root, prefix+'compositions.json', {
                'kind': 'hollow-country-overlay-compositions', 'compositions': {
                    'camp': {'theme': 'camp', 'purpose': 'test', 'pieces': [piece]}}})
            site = {'id': 's1', 'composition': 'camp', 'pos': [10, 4, 20], 'heading': 90}
            self.write(root, prefix+'layers/test.json', {'id': 'test', 'objects': [], 'sites': [site]})
            slot = {'Id': 1, 'Type': 'Shelf', 'Position': [1, 2, 3], 'Orientation': [90, 0, 0]}
            self.write(root, 'mission/hollow-country/interiors/templates/t-0000.json', {
                'BuildingClass': 'House', 'PropSlots': [slot]})
            slots = [[-3, 0, 0], [-3, 0, -3], [-3, 0, 3]]
            self.write(root, 'mission/hollow-country/travel/auditshelter_scenes.json', {
                'Scenes': [{'Id': 'rest', 'BuildingClass': 'Barn', 'Slots': slots}]})
            native = {'name': 'Barrel', 'pos': [5, 1, 6], 'ypr': [45, 10, 5], 'scale': 2}
            self.write(root, 'mission/world/hollow-country-props.json', {'Objects': [native]})
            rows = audit.discover(root)
            self.assertEqual(len(rows), len([piece])+len([slot])+len(slots)+len([native]))
            expanded = next(r for r in rows if r.classname == piece['class'])
            self.assertEqual(expanded.position, (10., 4.5, 18.))
            self.assertEqual(expanded.orientation, (105., 0., 0.))
            self.assertEqual(next(r for r in rows if r.classname == 'Shelf').host, 'House')
            self.assertEqual({r.classname for r in rows if r.terrain}, set(audit.SHELTER_PROPS))
            barrel = next(r for r in rows if r.classname == native['name'])
            self.assertEqual(barrel.orientation, tuple(native['ypr']))
            self.assertEqual(barrel.scale, native['scale'])
            self.assertEqual(rows, audit.discover(root))

    def test_invalid_transform_refuses_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write(root, 'mission/objects.json', {'Objects': [
                {'name': 'Bad', 'pos': [0, 0, 0], 'ypr': [math.inf, 0, 0]}]})
            with self.assertRaises(ValueError):
                audit.discover(root)

    def test_geometry_bounds_and_lowest_vertex_include_unreferenced_vertex(self):
        mesh = cube()
        mesh.vertices.append((2, -3, 4))
        obj = model(mesh, center=(1, 2, 3))
        box, triangles = audit.geometry(obj)
        points = [tuple(v[i]+obj.bounding_center[i] for i in range(3)) for v in mesh.vertices]
        self.assertEqual(box, audit.bounds(points))
        self.assertEqual(box[0][1], min(p[1] for p in points))
        self.assertEqual(len(triangles), sum(len(f)-2 for f in mesh.faces))

    def test_rotated_scaled_box_and_touching(self):
        box = ((0, 0, 0), (2, 1, 1))
        row = audit.Placement('g', 'a', 'P', (10, 2, 20), (90, 0, 0), 2)
        actual = audit.placed_box(box, row)
        for a, b in zip(actual, ((10, 2, 16), (12, 4, 20))):
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y)
        self.assertFalse(audit.overlaps(box, ((2, 0, 0), (3, 1, 1))))
        self.assertTrue(audit.overlaps(box, ((1, 0, 0), (3, 1, 1))))

    def test_host_triangle_uses_surface_not_enclosing_building_box(self):
        tri = ((-5, 0, -5), (5, 0, -5), (0, 0, 5))
        self.assertFalse(audit.triangle_box(tri, ((-.2, 0, -.2), (.2, .4, .2))))
        self.assertTrue(audit.triangle_box(tri, ((-.2, -.1, -.2), (.2, .4, .2))))
        self.assertFalse(audit.triangle_box(tri, ((8, -.1, 8), (9, .4, 9))))

    def test_door_swept_cylinder_and_height(self):
        door = ((0, 0, 0), (0, 0, 1))
        r, sweep = audit.POLICY['door_radius_m'], audit.POLICY['door_sweep_each_way_m']
        for sign in (-1, 1):
            z = sign * sweep
            self.assertTrue(audit.door_intersects(((-.1, 0, z-.1), (.1, 1, z+.1)), door))
        self.assertFalse(audit.door_intersects(((r+.01, 0, -.1), (r+1, 1, .1)), door))
        self.assertFalse(audit.door_intersects(((-.1, 2, -.1), (.1, 3, .1)), door))
        # Rounded capsule end: a point inside the square envelope can still be outside.
        d = r * .9
        self.assertFalse(audit.door_intersects(((d, 0, sweep+d), (d+.1, 1, sweep+d+.1)), door))
        tilted = ((0, 0, 0), (math.sqrt(.5), 0, math.sqrt(.5)))
        self.assertTrue(audit.door_intersects(((.8, 0, .8), (1, 1, 1)), tilted))

    def test_door_selection_normal_and_missing_direction(self):
        selection = NS(name='door1', vertices=[0, 1, 2, 3], faces=[0])
        mesh = lod(audit.GEOMETRY, [(-.5, 0, 0), (.5, 0, 0), (.5, 2, 0), (-.5, 2, 0)],
                   [(0, 1, 2, 3)], [selection])
        doors, skipped = audit.doors(model(mesh))
        self.assertFalse(skipped)
        self.assertEqual([d[0] for d in doors], [selection.name])
        self.assertAlmostEqual(abs(doors[0][1][1][2]), 1)
        selection.vertices, selection.faces = [0], []
        self.assertEqual(audit.doors(model(mesh))[1], [selection.name])

    def test_class_findings_lod_selection_sections_and_stable_report(self):
        base = cube((1, .3, 1), (2, 1, 2))
        cost = audit.POLICY['lowest_visual_triangles'] + 1
        visual = lod(0, base.vertices, [(0, 1, 2)] * cost,
                     sections=[None] * (audit.POLICY['lowest_visual_sections'] + 1))
        # A cheap distant LOD cannot hide the nearest visual LOD's cost.
        obj = prop(base, [lod(10, base.vertices, [(0, 1, 2)]), visual], view=False)
        rows = [audit.Placement('g', 'b', 'P'), audit.Placement('g', 'a', 'P')]
        result = audit.audit(rows, Installed({'P': obj}))
        codes = {f['reason'] for f in result['findings']}
        self.assertTrue({'PIVOT_OFFSET', 'FLOATING_ORIGIN', 'VIEW_GEOMETRY_EMPTY_OR_MISSING',
                         'VISUAL_TRIANGLE_COST', 'VISUAL_SECTION_COST', 'PIECE_AABB_OVERLAP'} <= codes)
        self.assertEqual(result['classes'][0]['lowest_visual_triangles'], cost)
        self.assertEqual(result['checked'], len({'P'}))
        # Sort input in the API as well as the inventory to make pair witnesses stable.
        self.assertEqual(result, audit.audit(list(reversed(rows)), Installed({'P': obj})))

    def test_missing_models_lods_and_section_api_are_explicit_skips(self):
        visual = lod(5, [(0, 0, 0)], [])
        del visual.sections
        obj = model(lod(audit.VIEW_GEOMETRY), visual)
        result = audit.audit([audit.Placement('g', 'a', 'P'), audit.Placement('g', 'b', 'Missing')],
                             Installed({'P': obj}))
        self.assertEqual({s['reason'] for s in result['skipped']},
                         {'MODEL_UNRESOLVED', 'GEOMETRY_LOD_EMPTY_OR_MISSING', 'SECTION_COUNT_UNAVAILABLE'})
        self.assertTrue(any(f['reason'] == 'VIEW_GEOMETRY_EMPTY_OR_MISSING' for f in result['findings']))

    def test_server_visuals_not_accepted(self):
        installed = Installed({'P': prop()})
        installed.visual_available = False
        result = audit.audit([audit.Placement('g', 'a', 'P')], installed)
        self.assertIn('FULL_CLIENT_VISUALS_REQUIRED', {s['reason'] for s in result['skipped']})
        self.assertNotIn('lowest_visual_triangles', result['classes'][0])

    def test_host_collision_and_door_report_each_placement(self):
        sel = NS(name='door1', vertices=[0, 1, 2, 3], faces=[0])
        host = model(lod(audit.GEOMETRY, [(-1, 0, 0), (1, 0, 0), (1, 2, 0), (-1, 2, 0)],
                         [(0, 1, 2, 3)], [sel]))
        rows = [audit.Placement('room', 'a', 'P', host='House')]
        result = audit.audit(rows, Installed({'P': prop(), 'House': host}))
        codes = {f['reason'] for f in result['findings']}
        self.assertIn('HOST_GEOMETRY_ENCROACHMENT', codes)
        self.assertIn('DOOR_APRON_INTERSECTION', codes)
        for f in result['findings']:
            if f['reason'] in ('HOST_GEOMETRY_ENCROACHMENT', 'DOOR_APRON_INTERSECTION'):
                self.assertEqual(f['host'], rows[0].host)
                self.assertEqual(f['key'], rows[0].key)

    def test_shelter_terrain_unknown_and_missing_host_do_not_pass_clearance(self):
        rows = [audit.Placement('rest', 'a', 'P', host='Missing', terrain=True)]
        result = audit.audit(rows, Installed({'P': prop()}))
        self.assertTrue({'LIVE_TERRAIN_AND_SHELTER_RETRIES_REQUIRED', 'HOST_GEOMETRY_UNAVAILABLE',
                         'DOOR_SELECTION_UNAVAILABLE_OR_INCOMPLETE'} <= {s['reason'] for s in result['skipped']})
        self.assertFalse(any(f['reason'] == 'HOST_GEOMETRY_ENCROACHMENT' for f in result['findings']))

    def paths_host(self):
        # One level corridor along Z at floor height and one stair flight along X=3.
        stair_rise = audit.POLICY['stair_min_slope'] * 3 * 2
        vertices = [(0, 0, -2), (0, 0, 2), (3, 0, 0), (3, stair_rise, 3)]
        return model(lod(audit.GEOMETRY), lod(audit.PATHS, vertices, [(0, 1), (2, 3)]))

    def test_paths_lod_level_and_stair_segments_are_classified(self):
        segments = audit.path_segments(self.paths_host())
        self.assertEqual([seg[2] for seg in segments], [False, True])
        self.assertIsNone(audit.path_segments(model(lod(audit.GEOMETRY))))

    def test_paths_lod_blocking_findings_per_kind_and_clear_placements(self):
        rise = audit.POLICY['stair_min_slope'] * 3 * 2
        # Stair feet at z=1.5 are rise/2 high: a box in the column blocks, a box above the whole flight's head height does not.
        on_corridor = audit.Placement('room', 'level', 'P', host='House')
        on_stair = audit.Placement('room', 'stair', 'P', position=(3, rise / 2, 1.5), host='House')
        overhead = audit.Placement('room', 'high', 'P', position=(3, rise + audit.POLICY['door_height_m'] + .1, 1.5),
                                   host='House')
        clear = audit.Placement('room', 'clear', 'P', position=(8, 0, 8), host='House')
        result = audit.audit([on_corridor, on_stair, overhead, clear],
                             Installed({'P': prop(), 'House': self.paths_host()}))
        by_key = {}
        for f in result['findings']:
            if f['reason'] in ('STAIR_PATH_INTERSECTION', 'PATH_LOD_INTERSECTION'):
                by_key.setdefault(f['key'], set()).add(f['reason'])
                self.assertEqual(f['host'], 'House')
                self.assertGreaterEqual(f['segments'], 1)
        self.assertEqual(by_key, {'level': {'PATH_LOD_INTERSECTION'}, 'stair': {'STAIR_PATH_INTERSECTION'}})
        self.assertEqual(result['hosts'], [{'classname': 'House', 'placements': 4, 'paths_lod': True,
                                            'path_segments': 2, 'stair_segments': 1}])

    def test_low_box_is_stepped_over_and_host_without_paths_is_recorded_not_skipped(self):
        low = audit.POLICY['path_step_over_m'] / 2
        flat = prop(cube((-.2, 0, -.2), (.2, low, .2)))
        rows = [audit.Placement('room', 'rug', 'P', host='House')]
        result = audit.audit(rows, Installed({'P': flat, 'House': self.paths_host()}))
        self.assertFalse(any('PATH' in f['reason'] for f in result['findings']))
        bare = audit.audit(rows, Installed({'P': prop(), 'House': model(lod(audit.GEOMETRY))}))
        self.assertEqual(bare['hosts'][0]['paths_lod'], False)
        self.assertFalse(any(s['reason'].startswith('PATH') for s in bare['skipped']))

    def test_shelter_terrain_rows_get_no_path_verdict(self):
        rows = [audit.Placement('rest', 'a', 'P', host='House', terrain=True)]
        result = audit.audit(rows, Installed({'P': prop(), 'House': self.paths_host()}))
        self.assertFalse(any('PATH' in f['reason'] for f in result['findings']))

    def test_catalog_bounds_cover_unplaced_classes_and_reserve_status(self):
        big = prop(cube((-2, 0, -4), (2, 3, 4)))
        catalog = {'Placed': {'footprint_reserve_m': [4, 8]}, 'Unplaced': {'footprint_reserve_m': [1, 1]},
                   'NoReserve': {}, 'Gone': {}, 'NoGeometry': {}}
        installed = Installed({'Placed': big, 'Unplaced': big, 'NoReserve': big,
                               'NoGeometry': model(lod(audit.VIEW_GEOMETRY))})
        result = audit.audit([audit.Placement('g', 'a', 'Placed')], installed, catalog)
        self.assertEqual(result['checked'], 1)  # unplaced catalogue classes are not audited as placements
        self.assertEqual(set(result['catalog_bounds']), {'Unplaced', 'NoReserve'})
        unmeasured = {s['classname'] for s in result['skipped'] if s['reason'] == 'CLASS_BOUNDS_UNMEASURED'}
        self.assertEqual(unmeasured, {'Gone', 'NoGeometry'})
        update = audit.bounds_update(result, catalog)
        self.assertFalse(update['applied'])
        self.assertEqual(update['unmeasured'], ['Gone', 'NoGeometry'])
        self.assertEqual({n: r['reserve_status'] for n, r in update['classes'].items()},
                         {'Placed': 'RESERVE_COVERS_MEASURED', 'Unplaced': 'RESERVE_BELOW_MEASURED',
                          'NoReserve': 'NO_RESERVE'})
        self.assertEqual(update['classes']['Placed']['footprint_m'], [4.0, 8.0])
        self.assertEqual(update['classes']['Placed']['size_m'], [4.0, 3.0, 8.0])
        self.assertEqual(update, audit.bounds_update(result, catalog))

    def test_bounds_out_is_written_by_main_without_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write(root, 'config/map-overlays/classes.json', {'classes': {'Crate': {}}})
            addons = root / 'Addons'
            addons.mkdir()
            (addons / 'a.pbo').touch()
            out = root / 'bounds.json'
            output = io.StringIO()
            installed = Installed({'Crate': prop(cube((-1, 0, -2), (1, 1, 2)))})
            with patch.object(audit, 'discover', return_value=[]), \
                    patch.object(audit, 'Installed', return_value=installed), \
                    contextlib.redirect_stdout(output):
                code = audit.main(['--repo', str(root), '--addons', str(addons),
                                   '--bounds-out', str(out), '--report', str(root / 'r.json')])
            self.assertEqual(code, 0)
            written = json.loads(out.read_text())
            self.assertEqual(written['classes']['Crate']['footprint_m'], [2.0, 4.0])
            self.assertNotIn(str(root), out.read_text())

    def test_missing_dependencies_permissive_and_strict_and_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'report.json'
            args = ['--repo', str(root), '--addons', str(root/'absent'), '--report', str(target)]
            for strict in (False, True):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = audit.main(args + (['--require-installed'] if strict else []))
                result = json.loads(target.read_text())
                self.assertEqual(code, int(strict))
                self.assertEqual(result['checked'], 0)
                self.assertEqual({s['reason'] for s in result['skipped']}, {'INSTALLED_ADDONS_UNAVAILABLE'})
                self.assertIn('world_mesh_audit: pass checked=0 findings=0 skipped=1', output.getvalue())
                self.assertNotIn(str(root), output.getvalue()+target.read_text())
                self.assertIn('preland', result['wiring_needed'])

    def test_partial_reader_result_is_never_complete_evidence(self):
        obj = prop()
        obj.failed_lods = [1]
        rows = [audit.Placement('g', 'a', 'P', host='House')]
        host = model(cube())
        host.failed_lods = [2]
        result = audit.audit(rows, Installed({'P': obj, 'House': host}))
        self.assertTrue({'READER_PARTIAL_LODS', 'HOST_READER_PARTIAL_LODS'} <=
                        {s['reason'] for s in result['skipped']})

    def test_installed_index_inherited_models_and_frame_convention(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archives = [root/'structures_test.pbo', root/'gear_test.pbo']
            for path in archives:
                path.touch()
            classes = {'Parent': {'model': 'prefix/mesh'}, 'Prop': {'parent': 'Parent'},
                       'Land_Building': {'parent': 'Parent'}}
            def index(path):
                return {'prefix': path.stem, 'entries': [{'name': 'mesh.p3d'}]}
            decoded = []
            def decode(data):
                obj = prop()
                obj.bounding_center = (1, 2, 3)
                decoded.append(obj)
                return obj
            with patch.object(audit.odol56, 'read_odol', side_effect=decode) as read_odol, \
                    patch.object(audit.pbo, 'read_pbo_index', side_effect=index) as read_index, \
                    patch.object(audit.pbo, 'read_configs', return_value={'CfgVehicles': classes}), \
                    patch.object(audit.pbo, 'read_member', return_value=b'synthetic'):
                installed = audit.Installed(root)
                self.assertEqual({call.args[0] for call in read_index.call_args_list}, set(archives))
                installed.classes['Parent']['model'] = 'gear_test/mesh'
                self.assertEqual(installed.model('Prop').bounding_center, (1, 2, 3))
                self.assertEqual(installed.model('Land_Building').bounding_center, (0, 0, 0))
                self.assertEqual(installed.model('Prop', host=True).bounding_center, (0, 0, 0))
                self.assertIsNone(installed.model('Missing'))
                read_odol.assert_called_with(b'synthetic')

    def test_undecodable_model_raises_without_private_diagnostic(self):
        installed = audit.Installed.__new__(audit.Installed)
        key = audit.pbo.normalize_path('prefix/mesh.p3d')
        installed.classes, installed.members = {}, {key: ('private-archive', {}, 'mesh.p3d')}
        with patch.object(audit.pbo, 'read_member', return_value=b'not a model'):
            with self.assertRaises(ValueError) as caught:
                installed.model('prefix/mesh.p3d')
        self.assertNotIn('private-archive', str(caught.exception))

    def test_invalid_available_reader_fails_without_private_diagnostic(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'input.pbo').touch()
            output = io.StringIO()
            with patch.object(audit, 'Installed', side_effect=ValueError('private-folder-name')):
                with contextlib.redirect_stdout(output):
                    code = audit.main(['--repo', str(root), '--addons', str(root)])
            self.assertEqual(code, 1)
            self.assertNotIn('private-folder-name', output.getvalue())
            self.assertIn('INVALID_INPUT_OR_READER', output.getvalue())


if __name__ == '__main__':
    unittest.main()
