"""Offline tests for original asset tooling. No Blender/native process is run."""
import copy
from dataclasses import replace
import itertools
import json
import math
from pathlib import Path
import subprocess
import struct
import zlib
import tempfile
import unittest
from unittest.mock import patch

from tools.assets import blender_ops_script, blender_runner, finisher, mlod
from tools.assets import ops_runner, pbr_pack, provenance, visual_diff


def recipe():
    return {'schema': 'ops.v1', 'name': 'fixture', 'ops': [
        {'op': 'primitive', 'id': 'body', 'kind': 'box', 'size': [1, 1, 1]}]}


def cube(size=(1, 1, 1)):
    vertices = [tuple(s[i]*size[i]/2 for i in range(3))
                for s in itertools.product((-1, 1), repeat=3)]
    quads = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
    faces = [{'vertices': list(q), 'uv': [[0, 0], [1, 0], [1, 1], [0, 1]],
              'texture': '', 'material': ''} for q in quads]
    return {'schema': 'neutral.v1', 'vertices': vertices, 'faces': faces,
            'selections': {'body': {'vertices': list(range(len(vertices))),
                                     'faces': list(range(len(faces)))}},
            'points': {'center': [0, 0, 0]}, 'proxies': []}


class OpsTests(unittest.TestCase):
    def test_example_and_every_operation(self):
        example = provenance.ROOT / 'assets_src/test/hc_testcube.ops.json'
        ops_runner.validate(provenance.load_json(example.read_bytes()))
        data = recipe()
        data['ops'] += [
            {'op': 'primitive', 'id': 'cut', 'kind': 'cylinder', 'size': [0.5]*3},
            {'op': 'boolean', 'target': 'body', 'operand': 'cut', 'mode': 'DIFFERENCE'},
            {'op': 'bevel', 'target': 'body', 'width': 0.01, 'segments': 1},
            {'op': 'array', 'target': 'body', 'count': 2, 'offset': [2, 0, 0]},
            {'op': 'mirror', 'target': 'body', 'axis': 'X'},
            {'op': 'transform', 'target': 'body', 'translate': [0]*3,
             'rotate': [0]*3, 'scale': [1]*3},
            {'op': 'uv-unwrap', 'target': 'body'},
            {'op': 'material-slot', 'target': 'body', 'texture': '', 'material': ''},
            {'op': 'named-selection', 'target': 'body', 'name': 'body'},
            {'op': 'memory-point', 'name': 'center', 'position': [0]*3},
            {'op': 'proxy', 'model': 'HollowCountry\\test\\proxy.p3d',
             'position': [0]*3, 'rotation': [0]*3, 'instance': 1}]
        validated = ops_runner.validate(data)
        self.assertEqual(validated, data)
        validated['ops'].clear()
        self.assertTrue(data['ops'])

    def test_closed_schema_and_numerics(self):
        mutations = [lambda r: r.update(extra=True),
                     lambda r: r.update(schema='ops.v2'),
                     lambda r: r['ops'][0].update(python='forbidden'),
                     lambda r: r['ops'][0].update(op='raw_bpy'),
                     lambda r: r['ops'][0].update(op=[]),
                     lambda r: r['ops'][0].update(size=[float('nan')]*3),
                     lambda r: r['ops'][0].update(size=[True]*3),
                     lambda r: r['ops'][0].update(size=[0]*3),
                     lambda r: r['ops'][0].update(id='../bad')]
        for mutate in mutations:
            data = recipe()
            mutate(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                ops_runner.validate(data)

    def test_references_and_expansion_limit(self):
        for operation in ({'op': 'uv-unwrap', 'target': 'missing'},
                          {'op': 'boolean', 'target': 'body', 'operand': 'body', 'mode': 'UNION'}):
            data = recipe()
            data['ops'].append(operation)
            with self.assertRaises(ValueError):
                ops_runner.validate(data)
        data = recipe()
        while len(data['ops']) <= ops_runner.MAX_OPS:
            data['ops'].append({'op': 'array', 'target': 'body', 'count': 32, 'offset': [1, 0, 0]})
            try:
                ops_runner.validate(data)
            except ValueError:
                break
        else:
            self.fail('expansion accepted past bound')
        with self.assertRaises(ValueError):
            ops_runner.validate({**recipe(), 'ops': recipe()['ops'] * (ops_runner.MAX_OPS + 1)})

    def test_arguments_are_data_and_axes_preserve_orientation(self):
        args = ops_runner.script_arguments('recipe with spaces.json', 'mesh.json', render=True)
        self.assertEqual(args[args.index('--recipe')+1], 'recipe with spaces.json')
        axes = [blender_ops_script.canonical(v) for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
        self.assertGreater(finisher.dot(finisher.cross(axes[0], axes[1]), axes[2]), 0)


class FinisherTests(unittest.TestCase):
    def test_roundtrip_budget_memory_and_convex_mass(self):
        mesh = cube()
        expected_triangles = sum(len(f['vertices'])-2 for f in mesh['faces'])
        asset = finisher.finish({0: mesh}, budgets={0: expected_triangles}, mass=23)
        self.assertEqual(len(asset.lods[0].faces), expected_triangles)
        self.assertEqual(asset.lods[mlod.MEMORY].vertices[0].position, tuple(mesh['points']['center']))
        self.assertAlmostEqual(sum(asset.lods[mlod.GEOMETRY].masses), 23)
        self.assertEqual(mlod.write_mlod(asset), mlod.write_mlod(finisher.finish(
            {0: copy.deepcopy(mesh)}, budgets={0: expected_triangles}, mass=23)))
        decoded = mlod.read_mlod(mlod.write_mlod(asset))
        self.assertEqual(set(decoded.lods), set(asset.lods))
        with self.assertRaisesRegex(ValueError, 'triangle_budget'):
            finisher.finish({0: mesh}, budgets={0: expected_triangles-1})

    def test_weld_degenerate_remapping_and_normal_repair(self):
        mesh = cube()
        original = finisher.clean(mesh)
        duplicate = len(mesh['vertices'])
        mesh['vertices'].append(mesh['vertices'][0])
        mesh['faces'][0]['vertices'][0] = duplicate
        # Reverse one face and its UVs; normal repair must preserve association.
        mesh['faces'][1]['vertices'].reverse()
        mesh['faces'][1]['uv'].reverse()
        mesh['faces'].append({'vertices': [0, 0, 1], 'uv': [[0, 0]]*3,
                              'texture': '', 'material': ''})
        mesh['selections']['welded'] = {'vertices': [duplicate], 'faces': [len(mesh['faces'])-1]}
        result = finisher.clean(mesh)
        self.assertEqual(len(result.vertices), len(original.vertices))
        self.assertEqual(len(result.faces), len(original.faces))
        self.assertEqual(result.selections['welded'].faces, ())
        self.assertEqual(len(result.selections['welded'].vertices), 1)
        for face in result.faces:
            center = tuple(sum(result.vertices[j].position[i] for j in face.vertices)/3 for i in range(3))
            self.assertGreater(finisher.dot(face.normals[0], center), 0)
            self.assertAlmostEqual(math.hypot(*face.normals[0]), 1)

    def test_thin_open_bad_uv_and_proxy_refused(self):
        with self.assertRaisesRegex(ValueError, 'thin_shell'):
            finisher.clean(cube((1, 1, 0.00001)))
        data = cube()
        data['faces'].pop()
        data['selections']['body']['faces'] = list(range(len(data['faces'])))
        with self.assertRaisesRegex(ValueError, 'nonmanifold_or_open'):
            finisher.clean(data)
        self.assertTrue(finisher.clean(data, closed=False).faces)
        data = cube()
        data['faces'][0]['uv'].pop()
        with self.assertRaisesRegex(ValueError, 'neutral.uv'):
            finisher.clean(data)
        data = cube()
        data['proxies'] = [{'model': 'HollowCountry\\test\\proxy.p3d'}]
        with self.assertRaisesRegex(ValueError, 'proxy_unverified'):
            finisher.clean(data)

    def test_surface_interval_and_work_bound(self):
        lod = finisher.clean(cube())
        self.assertEqual(finisher.hausdorff(lod, lod)['upper'], 0)
        displacement = (2, 0, 0)
        shifted = replace(lod, vertices=tuple(mlod.Vertex(tuple(a+b for a, b in zip(v.position, displacement)))
                                               for v in lod.vertices))
        report = finisher.hausdorff(lod, shifted)
        self.assertLessEqual(report['lower'], math.hypot(*displacement) + 1e-10)
        self.assertGreaterEqual(report['upper'], math.hypot(*displacement))
        huge = replace(lod, faces=lod.faces * 100)
        with self.assertRaisesRegex(ValueError, 'distance_work_limit'):
            finisher.hausdorff(huge, huge)
        mesh = cube()
        with self.assertRaisesRegex(ValueError, 'lod_distance'):
            finisher.finish({0: mesh, 1: cube((0.5, 0.5, 0.5))},
                            budgets={0: len(lod.faces), 1: len(lod.faces)}, lod_distance=0)

    def test_touching_collision_boxes_keep_separate_components(self):
        primitives = [{'kind': 'box', 'center': [x, 0, 0], 'size': [1, 1, 1]} for x in (0, 1)]
        lod = finisher.box_hulls(primitives, mass=10)
        self.assertEqual(len(lod.selections), len(primitives))
        memberships = [set(s.vertices) for s in lod.selections.values()]
        self.assertFalse(memberships[0] & memberships[1])
        mlod.validate(mlod.Asset({mlod.GEOMETRY: lod}))


class ImageTests(unittest.TestCase):
    def test_tga_roundtrip_and_origins(self):
        pixels = bytes(range(4*3*4))
        image = pbr_pack.Image(4, 3, pixels)
        encoded = pbr_pack.encode_tga(image)
        self.assertEqual(pbr_pack.decode_tga(encoded), image)
        # Reverse storage order in both dimensions; descriptor marks bottom-right.
        header = bytearray(encoded[:18])
        header[17] = 8 | 16
        samples = [encoded[i:i+4] for i in range(18, len(encoded), 4)]
        other = bytes(header) + b''.join(reversed(samples))
        self.assertEqual(pbr_pack.decode_tga(other), image)
        for raw in (b'', encoded[:-1], encoded + b'unknown metadata'):
            with self.assertRaises(ValueError):
                pbr_pack.decode_tga(raw)

    def test_png_filters_bounds_and_crc(self):
        image = pbr_pack.Image(3, 2, bytes(range(3*2*4)))
        def chunk(tag, payload):
            return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', zlib.crc32(tag+payload))
        header = chunk(b'IHDR', struct.pack('>IIBBBBB', image.width, image.height, 8, 6, 0, 0, 0))
        for kind in range(5):
            raw, previous = bytearray(), bytes(image.width*4)
            for row in range(image.height):
                line = image.rgba[row*image.width*4:(row+1)*image.width*4]
                raw.append(kind)
                for i, value in enumerate(line):
                    a = line[i-4] if i >= 4 else 0
                    b = previous[i]
                    c = previous[i-4] if i >= 4 else 0
                    if kind == 4:
                        estimate = a+b-c
                        predictor = min((a, b, c), key=lambda v: abs(estimate-v))
                    else:
                        predictor = (0, a, b, (a+b)//2)[kind]
                    raw.append((value-predictor) & 255)
                previous = line
            png = b'\x89PNG\r\n\x1a\n' + header + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
            with self.subTest(filter=kind):
                self.assertEqual(pbr_pack.decode_image(png), image)
                damaged = bytearray(png)
                damaged[-1] ^= 1
                with self.assertRaises(ValueError):
                    pbr_pack.decode_image(bytes(damaged))
        bomb = b'\x89PNG\r\n\x1a\n' + header + chunk(b'IDAT', zlib.compress(bytes(len(image.rgba)*100))) + chunk(b'IEND', b'')
        with self.assertRaisesRegex(ValueError, 'raster_size'):
            pbr_pack.decode_image(bomb)

    def test_pack_channels_dimensions_and_scalar_refusal(self):
        image = pbr_pack.Image(1, 1, bytes((128, 128, 128, 255)))
        maps = dict.fromkeys(pbr_pack.MAPS, image)
        packed = pbr_pack.pack_pixels(maps)
        self.assertEqual(packed['co'], maps['base_color'])
        self.assertEqual(packed['nohq'], maps['normal'])
        self.assertEqual(packed['smdi'].rgba[2], 255 - maps['roughness'].rgba[0])
        self.assertEqual(packed['as'].rgba, maps['ao'].rgba)
        maps['ao'] = pbr_pack.Image(1, 1, bytes((0, 1, 2, 255)))
        with self.assertRaisesRegex(ValueError, 'scalar_map'):
            pbr_pack.pack_pixels(maps)
        maps['ao'] = pbr_pack.Image(2, 1, image.rgba*2)
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            pbr_pack.pack_pixels(maps)

    def test_diff_metrics_and_six_view_report(self):
        black = pbr_pack.Image(1, 1, bytes((0, 0, 0, 255)))
        white = pbr_pack.Image(1, 1, bytes((255, 255, 255, 255)))
        self.assertEqual(visual_diff.metric(black, black)['rmse'], 0)
        expected = sum((a-b)**2 for a, b in zip(black.rgba, white.rgba))/len(black.rgba)
        self.assertAlmostEqual(visual_diff.metric(black, white)['rmse'], math.sqrt(expected)/255)
        views = dict.fromkeys(visual_diff.VIEWS, pbr_pack.encode_tga(black))
        report = visual_diff.compare(views, views)
        self.assertTrue(report['pass'])
        self.assertEqual(set(report['views']), set(visual_diff.VIEWS))
        changed = dict(views)
        changed[visual_diff.VIEWS[0]] = pbr_pack.encode_tga(white)
        self.assertFalse(visual_diff.compare(views, changed)['pass'])
        with self.assertRaisesRegex(ValueError, 'six_views'):
            visual_diff.compare({}, views)
        with self.assertRaises(ValueError):
            visual_diff.compare(views, views, threshold=float('nan'))


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        scratch = blender_runner.build_directory(provenance.ROOT / 'build/asset-tests')
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.candidate = self.root / 'candidate'
        self.candidate.mkdir()
        image = pbr_pack.Image(1, 1, bytes((128, 128, 128, 255)))
        self.sources, records = {}, []
        licence = b'Synthetic original CC0 fixture licence text'
        (self.candidate / 'licence.txt').write_bytes(licence)
        for key in sorted(pbr_pack.MAPS):
            filename = key + '.tga'
            raw = pbr_pack.encode_tga(image)
            (self.candidate / filename).write_bytes(raw)
            self.sources[key] = filename
            records.append(dict(source='own-work:fixture', path=filename, sha256=provenance.digest(raw),
                                licence_id='CC0-1.0', licence_path='licence.txt',
                                licence_sha256=provenance.digest(licence), attribution='Synthetic fixture'))
        self.document = provenance.build_provenance(asset='cube', inputs=records, toolchain=[],
                                                    origin='own-work', root=self.candidate)
        self.seal()

    def seal(self):
        (self.candidate / 'provenance.json').write_text(json.dumps(self.document), encoding='utf-8')
        files = {p.name: provenance.digest(p.read_bytes()) for p in self.candidate.iterdir()
                 if p.name not in ('manifest.json', 'candidate.sha256')}
        raw = json.dumps({'files': files}, sort_keys=True).encode()
        (self.candidate / 'manifest.json').write_bytes(raw)
        (self.candidate / 'candidate.sha256').write_text(provenance.digest(raw), encoding='ascii')

    def pack(self):
        return pbr_pack.pack(self.candidate, self.sources, self.root / 'packed',
                             asset_name='cube', virtual_prefix='HollowCountry\\test\\cube')

    def test_real_sealed_gate_pack_and_tamper_refusal(self):
        report = self.pack()
        for filename, expected in report['files'].items():
            self.assertEqual(provenance.digest((self.root / 'packed' / filename).read_bytes()), expected)
        self.assertIn('unverified', report['normal_green'])
        self.assertIn('_co.paa', report['texture'])
        (self.candidate / self.sources['ao']).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'licence_not_shippable'):
            self.pack()

    def test_false_claim_and_unpinned_map_refused(self):
        self.document['inputs'][0]['licence_id'] = 'CC-BY-NC-4.0'
        self.seal()
        with self.assertRaisesRegex(ValueError, 'licence_not_shippable'):
            self.pack()
        self.document['inputs'][0]['licence_id'] = 'CC0-1.0'
        self.seal()
        self.sources['ao'] = 'licence.txt'
        with self.assertRaisesRegex(ValueError, 'source_not_pinned'):
            self.pack()

    def test_output_existing_and_outside_build_refuse(self):
        self.pack()
        with self.assertRaisesRegex(ValueError, 'output_exists'):
            self.pack()
        with self.assertRaisesRegex(blender_runner.BlenderRefusal, 'outside_build'):
            blender_runner.build_directory(provenance.ROOT / 'assets_src')


class RunnerTests(unittest.TestCase):
    def test_missing_and_validation_never_launch(self):
        with patch.object(blender_runner.shutil, 'which', return_value=None), patch.object(
                blender_runner.subprocess, 'run') as run:
            with self.assertRaisesRegex(blender_runner.BlenderRefusal, 'not_found'):
                blender_runner.locate({'blender': 'nonexistent-hc-blender'}, environ={})
            with self.assertRaises(ValueError):
                blender_runner.build({'schema': 'invalid'})
            run.assert_not_called()

    def test_env_config_precedence(self):
        with patch.object(blender_runner.shutil, 'which', side_effect=lambda v: '/fake/' + v):
            path = blender_runner.locate({'blender': 'config'}, environ={'HC_BLENDER': 'env'})
            self.assertEqual(path.name, 'env')

    def test_native_subprocess_flags_timeout_and_private_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            completed = subprocess.CompletedProcess([], 0, 'private stdout', 'private stderr')
            with patch.object(blender_runner.subprocess, 'run', return_value=completed) as run:
                result = blender_runner._execute(Path('/fake/blender'), Path('script.py'),
                                                 ['--recipe', 'recipe.json'], directory, 10)
                self.assertEqual(result.stdout, completed.stdout)
                command = run.call_args.args[0]
                for flag in ('-b', '--factory-startup', '--disable-autoexec', '-P', '--'):
                    self.assertIn(flag, command)
                self.assertEqual(run.call_args.kwargs['cwd'], directory)
                self.assertEqual(run.call_args.kwargs['timeout'], 10)
            with patch.object(blender_runner.subprocess, 'run', side_effect=subprocess.TimeoutExpired([], 10)):
                with self.assertRaisesRegex(blender_runner.BlenderRefusal, 'timeout'):
                    blender_runner._execute(Path('/fake/blender'), Path('script.py'), [], directory, 10)

    def test_failure_logs_are_private_and_timeout_bounds_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            completed = subprocess.CompletedProcess([], 1, 'private output', 'private diagnostic')
            with patch.object(blender_runner.subprocess, 'run', return_value=completed):
                with self.assertRaises(blender_runner.BlenderRefusal) as caught:
                    blender_runner._execute(Path('/fake/blender'), Path('script.py'), [], Path(temp), 10)
                self.assertEqual(caught.exception.stdout, completed.stdout)
                self.assertNotIn(completed.stderr, str(caught.exception))
        for timeout in (0, float('nan'), 1000, True):
            with self.assertRaisesRegex(blender_runner.BlenderRefusal, 'timeout_invalid'):
                blender_runner.build(recipe(), timeout=timeout)

    def test_build_boundary_and_cleanup_with_fake_child(self):
        directories = []
        def fake(executable, script, arguments, directory, timeout):
            directories.append(directory)
            output = Path(arguments[arguments.index('--output')+1])
            output.write_text(json.dumps(cube()), encoding='utf-8')
            self.assertTrue((directory / 'tools/assets/ops_runner.py').is_file())
            return subprocess.CompletedProcess([], 0, '', '')
        with patch.object(blender_runner, 'locate', return_value=Path('/fake/blender')), patch.object(
                blender_runner, '_execute', side_effect=fake):
            result = blender_runner.build(recipe())
        self.assertEqual(result.mesh, json.loads(json.dumps(cube())))
        self.assertTrue(all(not d.exists() for d in directories))
        def injected(executable, script, arguments, directory, timeout):
            output = Path(arguments[arguments.index('--output')+1])
            output.write_text(json.dumps({**cube(), 'shippable': True}), encoding='utf-8')
            return subprocess.CompletedProcess([], 0, '', '')
        with patch.object(blender_runner, 'locate', return_value=Path('/fake/blender')), patch.object(
                blender_runner, '_execute', side_effect=injected):
            with self.assertRaisesRegex(blender_runner.BlenderRefusal, 'output_invalid'):
                blender_runner.build(recipe())

    def test_windows_uses_winproc_and_converts_paths_without_launch(self):
        from tools.setup import winproc
        result = winproc.Result(0, 'captured', '', 1)
        with tempfile.TemporaryDirectory() as temp, patch.object(
                blender_runner, '_windows_path', side_effect=lambda p: 'Z:\\synthetic\\' + Path(p).name), patch.object(
                winproc, 'run', return_value=result) as run:
            actual = blender_runner._execute(Path('/fake/blender.exe'), Path('script.py'),
                ['--recipe', 'recipe.json', '--output', 'mesh.json'], Path(temp), 10)
            self.assertEqual(actual, result)
            self.assertEqual(run.call_args.args[0], 'powershell')
            self.assertEqual(run.call_args.kwargs['attempts'], 1)
            command = run.call_args.args[1][0]
            self.assertIn('WaitForExit', command)
            self.assertIn('Kill()', command)
            self.assertIn('--factory-startup', command)

    def test_every_module_offline_selftest(self):
        for module in (ops_runner, blender_runner, blender_ops_script, finisher, pbr_pack, visual_diff):
            with self.subTest(module=module.__name__):
                module.selftest()


if __name__ == '__main__':
    unittest.main()
