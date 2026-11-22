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
    def fixture(self, root, *, waived=()):
        source = root / 'source'
        candidate = root / 'candidate'
        source.mkdir()
        candidate.mkdir()
        payloads = {'config.cpp': b'class CfgPatches { class HollowCountryAssets { units[]={}; weapons[]={}; requiredAddons[]={"DZ_Data"}; }; };',
                    '$PBOPREFIX$': builder.PREFIX.encode(),
                    'HC_TestCube.p3d': mlod.write_mlod(hc_test_cube())}
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
            first = builder.build(plan, plan_dir=root, source=source, out=root / 'one')
            second = builder.build(plan, plan_dir=root, source=source, out=root / 'two')
            self.assertEqual(first, second)
            blob = (root / 'one/addons/HollowCountryAssets.pbo').read_bytes()
            expected = {n: d for n, d in payloads.items() if n != '$PBOPREFIX$'}
            self.assertEqual(blob, pbo.pack(expected, prefix=builder.PREFIX))
            self.assertEqual(set(first['files']), set(expected))
            with self.assertRaisesRegex(ValueError, 'assets.output_exists'):
                builder.build(plan, plan_dir=root, source=source, out=root / 'one')

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
                    builder.build(plan, plan_dir=root, source=source, out=root / 'out')
                self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
