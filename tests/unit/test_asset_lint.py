"""Synthetic HC_TestCube checks; no binaries stored, no native acceptance."""
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from tests.unit.test_mlod_writer import hc_test_cube
from tools.assets import mlod, provenance
from tools.assets.model_cfg import emit_model_cfg
from tools.package import build_assets_addon as builder, pbo
from tools.validate import asset_lint


class AssetLintTests(unittest.TestCase):
    def setUp(self):
        self.cube = hc_test_cube()
        self.sources = {p for lod in self.cube.lods.values() for f in lod.faces
                        for p in (f.texture, f.material) if p}
        self.model_cfg = emit_model_cfg('HC_TestCube', ['body'])
        self.config = 'class Cube { hiddenSelections[]={"body"}; memoryPoint="origin"; };'

    def check(self, cube=None, **kwargs):
        options = dict(model_cfg=self.model_cfg, config=self.config, sources=self.sources)
        options.update(kwargs)
        return asset_lint.lint(cube or self.cube, **options)

    def changed(self, resolution, **kwargs):
        return replace(self.cube, lods={**self.cube.lods,
                                      resolution: replace(self.cube.lods[resolution], **kwargs)})

    def fails(self, rule, cube=None, **kwargs):
        result = self.check(cube, **kwargs)
        self.assertFalse(result['valid'])
        self.assertIn(rule, {f['id'] for f in result['findings']}, result)

    def test_cube_and_written_mlod_pass(self):
        for cube in (self.cube, mlod.read_mlod(mlod.write_mlod(self.cube))):
            self.assertTrue(self.check(cube)['valid'], self.check(cube))
        document = json.loads(json.dumps(asdict(self.cube)))
        self.assertTrue(self.check(asset_lint.asset_from_ir(document))['valid'])

    def test_geometry_required(self):
        self.fails('HC-A001', replace(self.cube, lods={0.: self.cube.lods[0.]}))

    def test_open_and_reversed_shells(self):
        geo = self.cube.lods[mlod.GEOMETRY]
        self.fails('HC-A002', self.changed(mlod.GEOMETRY, faces=geo.faces[:-1],
                                         selections={'component01': mlod.Selection(tuple(range(len(geo.vertices))))}))
        faces = (replace(geo.faces[0], vertices=geo.faces[0].vertices[::-1]), *geo.faces[1:])
        self.fails('HC-A002', self.changed(mlod.GEOMETRY, faces=faces))

    def test_convex_components_named_and_nondegenerate(self):
        geo = self.cube.lods[mlod.GEOMETRY]
        self.fails('HC-A003', self.changed(mlod.GEOMETRY, selections={}))
        vertices = (replace(geo.vertices[0], position=(0., 0., 0.)), *geo.vertices[1:])
        self.fails('HC-A003', self.changed(mlod.GEOMETRY, vertices=vertices))
        faces = tuple(replace(f, vertices=f.vertices[::-1]) for f in geo.faces)
        self.fails('HC-A003', self.changed(mlod.GEOMETRY, faces=faces))

    def test_mass(self):
        for masses in ((), (0.,)*len(self.cube.lods[mlod.GEOMETRY].vertices)):
            self.fails('HC-A004', self.changed(mlod.GEOMETRY, masses=masses))

    def test_sections_and_config_selections(self):
        self.fails('HC-A005', model_cfg=emit_model_cfg('HC_TestCube', ['absent']))
        self.fails('HC-A005', config='class Cube { hiddenSelections[]={"absent"}; };')

    def test_damage_and_hitpoint_parity(self):
        fire = replace(self.cube.lods[mlod.GEOMETRY], masses=(),
                       selections={'body': self.cube.lods[0.].selections['body']})
        # Faces are Geometry quads, so use point membership only.
        fire = replace(fire, selections={'body': mlod.Selection(tuple(range(len(fire.vertices))))})
        cube = replace(self.cube, lods={**self.cube.lods, mlod.FIRE_GEOMETRY: fire})
        config = 'class Cube { class DamageSystem { class DamageZones { class Body { componentNames[]={"body"}; }; }; }; };'
        self.assertTrue(self.check(cube, config=config)['valid'])
        self.fails('HC-A006', cube, config=config.replace('"body"', '"absent"'))
        hit = 'class Cube { class HitPoints { class HitBody { name="body"; }; }; };'
        self.assertTrue(self.check(cube, config=hit)['valid'])
        self.fails('HC-A006', cube, config=hit.replace('"body"', '"absent"'))

    def test_memory(self):
        self.fails('HC-A007', config='class Cube { memoryPoints[]={"absent"}; };')
        self.fails('HC-A007', config='class Cube { memoryPoint="body"; };')

    def test_paths_allowed_and_resolved(self):
        self.fails('HC-A008', sources=[])
        self.fails('HC-A008', sources='not-an-inventory')
        self.fails('HC-A008', config=r'class Cube { hiddenSelectionsTextures[]={"Other\bad.paa"}; };')
        lod = self.cube.lods[0.]
        for path in (r'Other\data\test.paa', r'DZ\..\test.paa'):
            self.fails('HC-A008', self.changed(0., faces=(replace(lod.faces[0], texture=path), *lod.faces[1:])))

    def test_weights(self):
        vertices = self.cube.lods[0.].vertices
        weights = {'0': [{'root': 1.} for _ in vertices]}
        self.assertTrue(self.check(skin_weights=weights)['valid'])
        for row in ({'root': .5}, {str(i): .2 for i in range(5)}, {'root': float('nan')}, {'root': -1.}):
            self.fails('HC-A009', skin_weights={'0': [row for _ in vertices]})
        self.fails('HC-A009', model_cfg='class CfgModels { class Cube { skeletonName="Rig"; }; };')

    def test_bad_ir_and_config(self):
        lod = self.cube.lods[0.]
        self.fails('HC-A010', self.changed(0., faces=(replace(lod.faces[0], vertices=(999, 1, 2, 3)), *lod.faces[1:])))
        self.fails('HC-A010', config='#include "unexpanded.hpp"')
        self.fails('HC-A010', config='class Broken {')

    def test_cli_json_and_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model = root / 'HC_TestCube.p3d'
            model.write_bytes(mlod.write_mlod(self.cube))
            (root / 'model.cfg').write_text(self.model_cfg)
            (root / 'config.cpp').write_text(self.config)
            (root / 'sources.json').write_text(json.dumps(sorted(self.sources)))
            args = [str(model), '--model-cfg', str(root / 'model.cfg'), '--config', str(root / 'config.cpp'), '--sources', str(root / 'sources.json')]
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(asset_lint.main(args + ['--json']), 0)
            self.assertTrue(json.loads(output.getvalue())['valid'])
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(asset_lint.main(args), 0)
            self.assertIn('asset_lint: pass', output.getvalue())


class AssetBuilderTests(unittest.TestCase):
    def fixture(self, root, *, waived=(), model=None):
        source = root / 'source'
        candidate = root / 'candidate'
        source.mkdir()
        candidate.mkdir()
        payloads = {'config.cpp': b'class CfgPatches { class HollowCountryAssets { units[]={}; weapons[]={}; requiredAddons[]={"DZ_Data"}; }; };',
                    '$PBOPREFIX$': builder.PREFIX.encode(),
                    'NOTICE.txt': b'Synthetic addon notice',
                    'HC_TestCube.p3d': mlod.write_mlod(hc_test_cube()) if model is None else model}
        inputs = []
        for name, data in payloads.items():
            (candidate / name).write_bytes(data)
            if not name.endswith('.p3d'):
                (source / name).write_bytes(data)
            inputs.append(dict(source='own-work:synthetic', path=name, sha256=provenance.digest(data),
                               licence_id='CC0-1.0', licence_path='licence.txt',
                               licence_sha256=provenance.digest(b'Synthetic test licence'), attribution=''))
        (candidate / 'licence.txt').write_bytes(b'Synthetic test licence')
        doc = provenance.build_provenance(asset='HC_TestCube', inputs=inputs, toolchain=[],
                                          origin='own-work', root=candidate, waived=waived)
        (candidate / 'provenance.json').write_text(json.dumps(doc))
        files = {p.name: provenance.digest(p.read_bytes()) for p in candidate.iterdir()}
        raw = json.dumps({'files': files}, sort_keys=True).encode()
        (candidate / 'manifest.json').write_bytes(raw)
        (candidate / 'candidate.sha256').write_text(provenance.digest(raw))
        plan = {'inputs': [{'candidate': 'candidate', 'members': {n: n for n in payloads}}]}
        return source, candidate, plan, payloads

    def test_admitted_bytes_pack_deterministically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, _, plan, payloads = self.fixture(root)
            first = builder.build(plan, plan_dir=root, source=source, out=root / 'one', allow_mlod=True)
            second = builder.build(plan, plan_dir=root, source=source, out=root / 'two', allow_mlod=True)
            self.assertEqual(first, second)
            blob = (root / 'one/addons/HollowCountryAssets.pbo').read_bytes()
            expected = {n: d for n, d in payloads.items() if n != '$PBOPREFIX$'}
            self.assertEqual(blob, pbo.pack(expected, prefix=builder.PREFIX))
            self.assertEqual(set(first['files']), set(expected))
            with self.assertRaisesRegex(ValueError, 'assets.output_exists'):
                builder.build(plan, plan_dir=root, source=source, out=root / 'one', allow_mlod=True)

    def test_sealed_odol_build_and_corrupt_odol_refusal(self):
        from tests.test_odol56 import Spec, model_bytes
        raw = model_bytes([Spec()])
        for model, valid in ((raw, True), (raw[:-1], False)):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source, _, plan, payloads = self.fixture(root, model=model)
                if valid:
                    report = builder.build(plan, plan_dir=root, source=source, out=root / 'out')
                    self.assertEqual(report['format'], 'ODOL56')
                    self.assertFalse(report['engine_verified'])
                    blob = (root / 'out/addons/HollowCountryAssets.pbo').read_bytes()
                    self.assertEqual(blob, pbo.pack({k: v for k, v in payloads.items()
                                                    if k != '$PBOPREFIX$'}, prefix=builder.PREFIX))
                else:
                    with self.assertRaises(ValueError):
                        builder.build(plan, plan_dir=root, source=source, out=root / 'out')
                    self.assertFalse((root / 'out').exists())

    def test_default_refuses_mlod_and_unknown_magic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, _, plan, _ = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'binarized_odol_required'):
                builder.build(plan, plan_dir=root, source=source, out=root / 'out')
        for raw in (b'unknown', b'ODOL', b'MLOD'):
            with self.assertRaises(ValueError):
                builder.model_format(raw)
        from unittest.mock import patch
        with patch.object(builder.odol56, 'read_odol') as read:
            self.assertEqual(builder.model_format(b'ODOLsynthetic'), 'ODOL56')
            read.assert_called_once_with(b'ODOLsynthetic')

    def test_waiver_tamper_and_missing_admission_refused(self):
        for mode in ('waiver', 'tamper', 'source', 'missing', 'collision', 'traversal'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source, candidate, plan, _ = self.fixture(root, waived=['pending'] if mode == 'waiver' else ())
                members = plan['inputs'][0]['members']
                if mode == 'tamper':
                    (candidate / 'HC_TestCube.p3d').write_bytes(b'changed')
                if mode == 'source':
                    (source / 'config.cpp').write_bytes(b'changed')
                if mode == 'missing':
                    del members['config.cpp']
                if mode == 'collision':
                    members['CONFIG.cpp'] = 'config.cpp'
                if mode == 'traversal':
                    members['../bad.p3d'] = 'HC_TestCube.p3d'
                with self.assertRaises(ValueError):
                    builder.build(plan, plan_dir=root, source=source, out=root / 'out', allow_mlod=True)
                self.assertFalse((root / 'out').exists())


OWN_CO = 'HollowCountry\\data\\hc_testcube_co.paa'
OWN_NOHQ = 'HollowCountry\\data\\hc_testcube_nohq.paa'
OWN_RVMAT = 'HollowCountry\\data\\hc_testcube.rvmat'


def paa(kind=b'\x01\xff', width=64, height=64, taggs=2):
    data = kind
    for name in (b'CGVA', b'SFFO')[:taggs]:
        data += b'GGAT' + name + (4).to_bytes(4, 'little') + bytes(4)
    return data + bytes(2) + width.to_bytes(2, 'little') + height.to_bytes(2, 'little') + bytes(3) + bytes(16)


class ExtensionTests(unittest.TestCase):
    """Mesh, texture and rig extensions on top of the synthetic HC_TestCube."""

    def setUp(self):
        self.cube = hc_test_cube()
        geometry = self.cube.lods[mlod.GEOMETRY]
        # The shared fixture's visual LOD is deliberately open; build a closed one.
        faces = tuple(replace(f, texture=OWN_CO, material=r'DZ\data\data\default.rvmat') for f in geometry.faces)
        body = mlod.Selection(tuple(range(8)), tuple(range(len(faces))))
        self.closed = replace(self.cube, lods={**self.cube.lods, 0.: replace(
            self.cube.lods[0.], faces=faces, selections={'body': body})})
        self.sources = {OWN_CO, OWN_NOHQ, OWN_RVMAT, r'DZ\data\data\default.rvmat'}
        self.model_cfg = emit_model_cfg('HC_TestCube', ['body'])
        self.config = 'class Cube { hiddenSelections[]={"body"}; memoryPoint="origin"; };'

    def check(self, asset=None, **kwargs):
        options = dict(model_cfg=self.model_cfg, config=self.config, sources=self.sources)
        options.update(kwargs)
        return asset_lint.lint(asset or self.closed, **options)

    def ids(self, asset=None, **kwargs):
        return {f['id'] for f in self.check(asset, **kwargs)['findings']}

    def with_visual(self, **changes):
        return replace(self.closed, lods={**self.closed.lods, 0.: replace(self.closed.lods[0.], **changes)})

    def triangulated(self):
        lod = self.closed.lods[0.]
        faces = tuple(replace(f, vertices=t, uv=tuple(f.uv[f.vertices.index(i)] for i in t))
                      for f in lod.faces for t in asset_lint._triangles(f))
        return self.with_visual(faces=faces, selections={'body': mlod.Selection(tuple(range(8)), tuple(range(len(faces))))})

    def test_baseline_closed_cube_passes_every_policy(self):
        policy = {'triangles_only': True, 'closed_visual': True, 'expected_bbox': [[-.5]*3, [.5]*3]}
        self.assertTrue(self.check(self.triangulated(), policy=policy)['valid'])
        self.assertEqual(self.ids(policy={'closed_visual': True}), set())

    def test_policy_input_is_closed(self):
        self.assertIn('HC-A010', self.ids(policy={'surprise': True}))
        self.assertIn('HC-A010', self.ids(policy=[]))

    def test_degenerate_and_nonfinite_triangles(self):
        lod = self.closed.lods[0.]
        face = mlod.Face((0, 8, 1), ((0., 0.), (.5, 0.), (1., 0.)), OWN_CO, r'DZ\data\data\default.rvmat')

        def with_sliver(offset, **extra):
            vertices = lod.vertices + (mlod.Vertex((0., -.5 + offset, -.5)),)
            return self.with_visual(vertices=vertices, faces=lod.faces + (replace(face, **extra),))
        # Exactly collinear faces are refused by the codec; slivers below the area floor are ours.
        self.assertIn('HC-A010', self.ids(with_sliver(0.)))
        self.assertIn('HC-A011', self.ids(with_sliver(1e-13)))
        self.assertIn('HC-A011', self.ids(with_sliver(0., normals=((0., 0., 1.),) * 3)))
        self.assertNotIn('HC-A011', self.ids(with_sliver(1e-3)))
        nan = (mlod.Vertex((float('nan'), 0., 0.)),) + lod.vertices[1:]
        self.assertIn('HC-A010', self.ids(self.with_visual(vertices=nan)))

    def test_triangles_only_and_open_visual_shells(self):
        self.assertIn('HC-A011', self.ids(policy={'triangles_only': True}))
        lod = self.closed.lods[0.]
        open_shell = self.with_visual(faces=lod.faces[:-1], selections={})
        self.assertIn('HC-A011', self.ids(open_shell, policy={'closed_visual': True}))
        non_physical = replace(open_shell, physical=False)
        self.assertNotIn('HC-A011', self.ids(non_physical, policy={'closed_visual': True}))

    def test_bounding_box_and_pivot(self):
        self.assertNotIn('HC-A011', self.ids(policy={'expected_bbox': [[-.5]*3, [.5]*3]}))
        self.assertNotIn('HC-A011', self.ids(policy={'expected_bbox': [[-.503]*3, [.5]*3]}))
        self.assertIn('HC-A011', self.ids(policy={'expected_bbox': [[0]*3, [1]*3]}))
        self.assertIn('HC-A011', self.ids(policy={'expected_bbox': [[-.51]*3, [.5]*3]}))
        self.assertNotIn('HC-A011', self.ids(policy={'expected_bbox': [[-.51]*3, [.5]*3], 'bbox_tolerance': .02}))
        for bad in ([[0]*3], 'x', [[0]*3, [float('nan')]*3], [[0]*3, [1]*3, [2]*3]):
            self.assertIn('HC-A010', self.ids(policy={'expected_bbox': bad}))

    def test_material_count_and_lod_reduction(self):
        lod = self.closed.lods[0.]
        materials = [r'DZ\data\data\m%d.rvmat' % i for i in range(4)]
        faces = tuple(replace(f, material=materials[i % len(materials)]) for i, f in enumerate(lod.faces))
        self.assertIn('HC-A012', self.ids(self.with_visual(faces=faces), sources=self.sources | set(materials)))
        self.assertNotIn('HC-A012', self.ids(self.with_visual(faces=lod.faces)))
        verts = tuple(mlod.Vertex(p) for p in ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.), (0., 0., 1.)))
        uv = ((0., 0.), (1., 0.), (0., 1.))
        tetra = mlod.LOD(verts, tuple(mlod.Face(t, uv, OWN_CO, r'DZ\data\data\default.rvmat') for t in
                                      ((0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2))),
                         {'body': mlod.Selection((0, 1, 2, 3))})
        reduced = replace(self.closed, lods={**self.closed.lods, 1.: tetra})
        self.assertNotIn('HC-A012', self.ids(reduced))
        same = replace(self.closed, lods={**self.closed.lods, 1.: self.closed.lods[0.]})
        self.assertIn('HC-A012', self.ids(same))

    def test_uv_overlap_is_opt_in(self):
        self.assertIn('HC-A011', self.ids(policy={'uv_overlap': True}))
        lod = self.closed.lods[0.]
        faces = tuple(replace(f, uv=tuple(((n % 3 + u) / 3, (n // 3 + v) / 2) for u, v in f.uv))
                      for n, f in enumerate(lod.faces))
        self.assertNotIn('HC-A011', self.ids(self.with_visual(faces=faces), policy={'uv_overlap': True}))

    def test_paa_header_parser(self):
        self.assertEqual(asset_lint.paa_info(paa()), ('DXT1', 64, 64))
        self.assertEqual(asset_lint.paa_info(paa(b'\x05\xff', 128, 32, taggs=0)), ('DXT5', 128, 32))
        # The high bit of the stored width marks LZO compression, not size.
        self.assertEqual(asset_lint.paa_info(paa(width=64 | 0x8000))[1], 64)
        for bad in (b'', b'\x00\x00' + bytes(20), paa()[:20], paa()[:-18], 'str'):
            with self.assertRaises(ValueError):
                asset_lint.paa_info(bad)

    def test_textures(self):
        rvmat = {OWN_RVMAT: 'class Stage1 { texture="%s"; };' % OWN_NOHQ}
        good = {OWN_CO: paa(), OWN_NOHQ: paa(b'\x05\xff')}
        self.assertTrue(self.check(textures=good, rvmats=rvmat)['valid'], self.check(textures=good, rvmats=rvmat))
        cases = {
            'magic': {**good, OWN_CO: b'\x00\x00' + bytes(30)},
            'size': {**good, OWN_CO: paa(width=48)},
            'zero': {**good, OWN_CO: paa(height=0)},
            'normal': {**good, OWN_NOHQ: paa(b'\x01\xff')},
            'unreferenced': {**good, 'HollowCountry\\data\\extra_co.paa': paa()},
            'unshipped': {OWN_NOHQ: good[OWN_NOHQ]},
        }
        for label, textures in cases.items():
            findings = self.ids(textures=textures, rvmats=rvmat, sources=self.sources | {'HollowCountry\\data\\extra_co.paa'})
            self.assertIn('HC-A013', findings, label)
        self.assertIn('HC-A013', self.ids(textures={r'C:\x_co.paa': paa()}))
        self.assertIn('HC-A013', self.ids(textures=[]))

    def test_rvmat_stage_paths(self):
        stage = lambda value: {OWN_RVMAT: 'class Stage1 { texture="%s"; };' % value}
        self.assertNotIn('HC-A014', self.ids(rvmats=stage(OWN_NOHQ)))
        self.assertNotIn('HC-A014', self.ids(rvmats=stage('#(argb,8,8,3)color(0,0,0,0,DT)')))
        self.assertNotIn('HC-A014', self.ids(rvmats=stage('#(ai,64,64,1)fresnel(1.3,7)')))
        for bad in ('HollowCountry\\data\\absent_co.paa', r'C:\evil_co.paa', r'DZ\..\x_co.paa', '#(argb,8,8,3)exec(1)'):
            self.assertIn('HC-A014', self.ids(rvmats=stage(bad)), bad)
        self.assertIn('HC-A008', self.ids(rvmats={OWN_RVMAT.replace('.rvmat', '_x.rvmat'): ''}))
        self.assertIn('HC-A014', self.ids(rvmats=[]))
        self.assertIn('HC-A010', self.ids(rvmats={OWN_RVMAT: 'texture = $unknown;'}))

    def test_packer_rvmat_text_is_accepted(self):
        from tools.assets import pbr_pack
        prefix = 'HollowCountry\\test\\cube'
        paths = {prefix + suffix for suffix in ('_nohq.paa', '_as.paa', '_smdi.paa')}
        findings = self.ids(rvmats={OWN_RVMAT: pbr_pack.rvmat(prefix)}, sources=self.sources | paths)
        self.assertNotIn('HC-A014', findings)
        self.assertNotIn('HC-A010', findings)

    def rig(self, **overrides):
        weights = {'0': [{'Head': 1.0}] * 4 + [{'Spine': 1.0}] * 4}
        # The fixture's vertices 0-3 are on z=-.5, 4-7 on z=+.5.
        rig = {'bones': ['Head', 'Spine'],
               'skeleton': {'Spine': {'parent': None, 'pivot': [0, 0, 0]},
                            'Head': {'parent': 'Spine', 'pivot': [0, 0, 10]}},
               'poses': {'rest': {}, 'turn': {'Head': [[0, 1, 0], 5]}}}
        rig.update(overrides)
        return self.check(skin_weights=weights, rig=rig)

    def test_rig_bone_allowlist_and_stretch(self):
        self.assertTrue(self.rig()['valid'], self.rig())
        self.assertIn('HC-A015', {f['id'] for f in self.rig(bones=['Spine'])['findings']})
        far = {'Spine': {'parent': None, 'pivot': [0, 0, 0]}, 'Head': {'parent': 'Spine', 'pivot': [9, 9, 9]}}
        pose = {'flip': {'Head': [[1, 0, 0], 170]}}
        self.assertIn('HC-A015', {f['id'] for f in self.rig(skeleton=far, poses=pose)['findings']})

    def test_rig_inputs_fail_closed(self):
        loop = {'Head': {'parent': 'Spine', 'pivot': [0, 0, 0]}, 'Spine': {'parent': 'Head', 'pivot': [0, 0, 0]}}
        for override in ({'skeleton': loop}, {'poses': {'bad': {'Nope': [[0, 1, 0], 1]}}},
                         {'poses': {'bad': {'Head': [[0, 0, 0], 1]}}}, {'poses': {}}, {'skeleton': None},
                         {'unknown': 1}):
            self.assertIn('HC-A015', {f['id'] for f in self.rig(**override)['findings']}, override)
        self.assertIn('HC-A015', self.ids(rig={'bones': ['Head']}, skin_weights={'0': [{'Spine': 1.0}] * 8}))
        self.assertIn('HC-A015', self.ids(rig='x'))

    def test_cli_options_read_local_files_only(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            ir = base / 'cube.json'
            ir.write_text(json.dumps(asdict(self.closed)))
            (base / 'cfg.cpp').write_text(self.config)
            (base / 'model.cfg').write_text(self.model_cfg)
            (base / 'sources.json').write_text(json.dumps(sorted(self.sources)))
            (base / 'policy.json').write_text('{"closed_visual": true}')
            (base / 'co.paa').write_bytes(paa())
            (base / 'textures.json').write_text(json.dumps({OWN_CO: str(base / 'co.paa')}))
            args = [str(ir), '--model-cfg', str(base / 'model.cfg'), '--config', str(base / 'cfg.cpp'),
                    '--sources', str(base / 'sources.json'), '--json', '--policy', str(base / 'policy.json'),
                    '--textures', str(base / 'textures.json')]
            out = StringIO()
            with redirect_stdout(out):
                code = asset_lint.main(args)
            self.assertEqual((code, json.loads(out.getvalue())), (0, {'valid': True, 'findings': []}))
            (base / 'co.paa').write_bytes(paa(width=48))
            out = StringIO()
            with redirect_stdout(out):
                code = asset_lint.main(args)
            self.assertEqual(code, 1)
            self.assertIn('HC-A013', out.getvalue())
            self.assertNotIn(temp, out.getvalue())


if __name__ == '__main__':
    unittest.main()
