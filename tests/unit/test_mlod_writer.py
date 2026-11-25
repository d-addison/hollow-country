"""Original synthetic geometry only. Offline codec tests are not native proof."""
from dataclasses import asdict, replace
import json
import struct
import unittest
from unittest.mock import patch

from tools.assets.mlod import (
    Asset, Face, FIRE_GEOMETRY, GEOMETRY, LOD, MAX_POINTS, MEMORY, Proxy,
    Selection, SHADOW, Vertex, VIEW_GEOMETRY, read_mlod, structure_dump,
    virtual_path, write_mlod,
)
from tools.assets.model_cfg import emit_model_cfg
from tools.audit import pbo_config


def hc_test_cube():
    """HC_TestCube: original unit box, convex component and two memory points.

    All six quad loops are outward CCW in right-hand cross-product convention.
    One visual quad is split to exercise both triangle padding and quad records.
    """
    vertices = tuple(Vertex(p) for p in (
        (-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5),
        (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)))
    loops = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 4, 7, 3),
             (1, 2, 6, 5), (0, 1, 5, 4), (3, 7, 6, 2))
    uv = ((0., 0.), (1., 0.), (1., 1.), (0., 1.))
    geometry_faces = tuple(Face(loop, uv) for loop in loops)
    visual_loops = (loops[0][:3], (loops[0][0], loops[0][2], loops[0][3]), *loops[1:])
    visual_faces = tuple(Face(loop, uv[:len(loop)],
                              r'HollowCountry\data\hc_testcube_co.paa',
                              r'DZ\data\data\default.rvmat') for loop in visual_loops)
    return Asset({
        0.: LOD(vertices, visual_faces,
                {'body': Selection(tuple(range(len(vertices))), tuple(range(len(visual_faces))))}),
        GEOMETRY: LOD(vertices, geometry_faces,
                      {'component01': Selection(tuple(range(len(vertices))),
                                                tuple(range(len(geometry_faces))))},
                      {'autocenter': '0', 'class': 'house'}, (1.25,)*len(vertices)),
        MEMORY: LOD((Vertex((0., 0., 0.)), Vertex((0., .5, 0.))),
                    selections={'origin': Selection((0,)), 'top': Selection((1,))}),
    })


class MLODWriterTests(unittest.TestCase):
    def test_cube_round_trip_geometry_uv_material_mass_and_selections(self):
        cube = hc_test_cube()
        raw = write_mlod(cube)
        restored = read_mlod(raw)
        self.assertEqual(set(restored.lods), set(cube.lods))
        for resolution, expected in cube.lods.items():
            actual = restored.lods[resolution]
            self.assertEqual(actual.vertices, expected.vertices)
            self.assertEqual(actual.selections, expected.selections)
            self.assertEqual(actual.properties, expected.properties)
            self.assertEqual(actual.masses, expected.masses)
            for wanted, face in zip(expected.faces, actual.faces, strict=True):
                self.assertEqual(replace(face, normals=()), wanted)
                # Normals point out of this convex box: dot(normal, centroid)>0.
                center = tuple(sum(expected.vertices[i].position[a] for i in face.vertices)
                               / len(face.vertices) for a in range(3))
                for normal in face.normals:
                    self.assertGreater(sum(n*c for n, c in zip(normal, center)), 0)
        self.assertEqual(write_mlod(restored), raw)

    def test_determinism_including_mapping_order(self):
        cube = hc_test_cube()
        reordered = Asset({r: replace(lod,
                            properties=dict(reversed(list(lod.properties.items()))),
                            selections=dict(reversed(list(lod.selections.items()))))
                           for r, lod in reversed(list(cube.lods.items()))})
        self.assertEqual(write_mlod(cube), write_mlod(cube))
        self.assertEqual(write_mlod(cube), write_mlod(reordered))

    def test_documented_memory_layout_golden_and_structure(self):
        # Independent tiny wire fixture from the documented field layout.
        vertex = Vertex((1., 2., 3.))
        lod = LOD((vertex,), selections={'anchor': Selection((0,))},
                  properties={'autocenter': '0'})
        asset = Asset({MEMORY: lod}, physical=False)
        golden = (struct.pack('<4sII', b'MLOD', 257, len(asset.lods))
                  + struct.pack('<4s6I', b'P3DM', 28, 256, len(lod.vertices), 0, 0, 0)
                  + struct.pack('<3fI', *vertex.position, vertex.flags)
                  + b'TAGG'
                  + b'\x01#UVSet#\0' + struct.pack('<II', 4, 0)
                  + b'\x01anchor\0' + struct.pack('<I', len(lod.vertices)) + b'\x01'
                  + b'\x01#Property#\0' + struct.pack('<I', 128)
                  + b'autocenter'.ljust(64, b'\0') + b'0'.ljust(64, b'\0')
                  + b'\x01#EndOfFile#\0' + struct.pack('<If', 0, MEMORY))
        self.assertEqual(write_mlod(asset), golden)
        expected = {'signature': 'MLOD', 'version': 257, 'lods': [
            {'signature': 'P3DM', 'major': 28, 'minor': 256,
             'resolution': MEMORY, **asdict(lod)}]}
        self.assertEqual(structure_dump(golden, physical=False), expected)
        json.dumps(structure_dump(golden, physical=False), allow_nan=False)

    def test_all_supported_resolution_keys_survive_float32(self):
        cube = hc_test_cube()
        lods = dict(cube.lods)
        for resolution in (1., 2., SHADOW, FIRE_GEOMETRY, VIEW_GEOMETRY):
            lods[resolution] = cube.lods[0.]
        result = read_mlod(write_mlod(Asset(lods)))
        self.assertEqual(set(result.lods), set(lods))

    def test_float32_precision_and_explicit_cw_normals(self):
        # CW order is retained; explicit normals are never silently inverted.
        lod = LOD((Vertex((0., 0., 0.)), Vertex((0., .1, 0.)), Vertex((.1, 0., 0.))),
                  (Face((0, 1, 2), ((0., 0.), (.1, .2), (.3, .4)),
                        normals=((0., 0., -1.),)*3),))
        raw = write_mlod(Asset({0.: lod}, physical=False))
        restored = read_mlod(raw, physical=False)
        self.assertEqual(restored.lods[0.].faces[0].vertices, lod.faces[0].vertices)
        self.assertEqual(restored.lods[0.].faces[0].normals, lod.faces[0].normals)
        self.assertEqual(write_mlod(restored), raw)

    def test_bad_paths_are_refused_in_each_face_field(self):
        paths = ('/tmp/texture.paa', r'C:\temp\texture.paa', r'\\server\share\t.paa',
                 r'\DZ\data\t.paa', 'DZ/data/t.paa', r'DZ\..\t.paa',
                 r'DZ\\data\t.paa', r'OtherMod\t.paa', r'HollowCountry\data\t:bad.paa',
                 'DZ\\data\\bad\0.paa', '#(argb,8,8,3)color(1,1,1,1)',
                 r'HollowCountryEvil\t.paa')
        for path in paths:
            for field in ('texture', 'material'):
                with self.subTest(path=path, field=field):
                    cube = hc_test_cube()
                    lod = cube.lods[0.]
                    cube.lods[0.] = replace(lod, faces=(replace(lod.faces[0], **{field: path}),))
                    with self.assertRaises(ValueError):
                        write_mlod(cube)
        for path in ('', r'DZ\data\test.paa', r'HollowCountry\data\test.rvmat', r'HollowCountryAssets\data\test.paa'):
            self.assertEqual(virtual_path(path), path)

    def test_sharp_edges_validation_and_tag_roundtrip(self):
        visual = replace(hc_test_cube().lods[0], sharp_edges=((0, 1), (1, 2)))
        raw = write_mlod(Asset({0: visual}, physical=False))
        restored = read_mlod(raw, physical=False)
        self.assertEqual(restored.lods[0].sharp_edges, visual.sharp_edges)
        self.assertEqual(write_mlod(restored), raw)
        for edges in (((0, 0),), ((0, MAX_POINTS),), ((0,),), ((0, 1), (1, 0))):
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                write_mlod(Asset({0: replace(visual, sharp_edges=edges)}, physical=False))
        marker = raw.index(b'#SharpEdges#') + len(b'#SharpEdges#') + 1
        malformed = raw[:marker] + struct.pack('<I', 7) + raw[marker+4:]
        with self.assertRaisesRegex(ValueError, 'invalid sharp edges tag'):
            read_mlod(malformed, physical=False)

    def test_point_bound_and_boundary(self):
        point = Vertex((0., 0., 0.))
        with self.assertRaisesRegex(ValueError, '65535'):
            write_mlod(Asset({MEMORY: LOD((point,)*(MAX_POINTS+1))}, physical=False))
        asset = Asset({MEMORY: LOD((point,)*MAX_POINTS)}, physical=False)
        self.assertEqual(len(read_mlod(write_mlod(asset), physical=False).lods[MEMORY].vertices),
                         MAX_POINTS)

    def test_missing_and_empty_geometry_refused_for_physical_object(self):
        cube = hc_test_cube()
        del cube.lods[GEOMETRY]
        with self.assertRaisesRegex(ValueError, 'nonempty Geometry'):
            write_mlod(cube)
        for empty in (LOD(), LOD(vertices=(Vertex((0., 0., 0.)),), masses=(1.,))):
            with self.subTest(empty=empty), self.assertRaisesRegex(ValueError, 'nonempty Geometry'):
                write_mlod(Asset({GEOMETRY: empty}))

    def test_invalid_ir_refusals(self):
        cube = hc_test_cube()
        visual = cube.lods[0.]
        bad_lods = (
            replace(visual, faces=(replace(visual.faces[0], vertices=(0, 0, 1)),)),
            replace(visual, faces=(replace(visual.faces[0], vertices=(0, 1, MAX_POINTS)),)),
            replace(visual, faces=(replace(visual.faces[0], uv=()),)),
            replace(visual, faces=(replace(visual.faces[0], normals=((0., 0., 0.),)*3),)),
            replace(visual, vertices=(Vertex((float('nan'), 0., 0.)),)),
            replace(visual, selections={'body': Selection((MAX_POINTS,))}),
            replace(visual, selections={'#Mass#': Selection()}),
            replace(visual, properties={'class': 'x'*64}),
            replace(visual, properties={'#Mass#': '1'}),
            replace(visual, masses=(1.,)*len(visual.vertices)),
            replace(visual, proxies=(Proxy(r'HollowCountry\test.p3d', (0, 1, 2)),)),
            replace(visual, selections={'proxy:HollowCountry\\test.001': Selection((0, 1, 2))}),
        )
        for lod in bad_lods:
            with self.subTest(lod=lod), self.assertRaises(ValueError):
                write_mlod(Asset({0.: lod}, physical=False))
        geometry = cube.lods[GEOMETRY]
        for masses in ((), (-1.,)*len(geometry.vertices), (0.,)*len(geometry.vertices)):
            with self.subTest(masses=masses), self.assertRaises(ValueError):
                write_mlod(Asset({GEOMETRY: replace(geometry, masses=masses)}))
        for lods in ({}, {-1.: LOD()}, {12345.: LOD()}, {1.: LOD(), 1.+1e-9: LOD()}):
            with self.subTest(lods=lods), self.assertRaises(ValueError):
                write_mlod(Asset(lods, physical=False))

    def test_reader_rejects_truncation_trailing_data_and_bad_records(self):
        raw = write_mlod(hc_test_cube())
        for end in range(len(raw)):
            with self.subTest(end=end), self.assertRaises(ValueError):
                read_mlod(raw[:end])
        corruptions = [raw + b'X', b'ODOL' + raw[4:], raw[:4] + struct.pack('<I', 0) + raw[8:]]
        for marker, replacement in ((b'TAGG', b'FAIL'), (b'#UVSet#', b'#Other#'),
                                     (b'#Mass#', b'#Fail#'), (b'#EndOfFile#', b'#WrongName#')):
            corruptions.append(raw.replace(marker, replacement, 1))
        for data in corruptions:
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                read_mlod(data)


def parse_model_cfg(text):
    # Extend the audit parser's field projection for this test only. Its real
    # tokenizer/grammar still reads the emitted config, with no source pins.
    with patch.object(pbo_config, 'SCALAR_FIELDS',
                      (*pbo_config.SCALAR_FIELDS, 'isDiscrete', 'skeletonInherit',
                       'skeletonName', 'sectionsInherit')), patch.object(
                           pbo_config, 'ARRAY_FIELDS',
                           (*pbo_config.ARRAY_FIELDS, 'skeletonBones', 'sections')):
        return pbo_config.parse_text_config(text, ['CfgSkeletons', 'CfgModels'])


class ModelCfgTests(unittest.TestCase):
    def test_static_cfg_parses_as_expected(self):
        sections = tuple(hc_test_cube().lods[0.].selections)
        text = emit_model_cfg('HC_TestCube', sections)
        rows = parse_model_cfg(text)
        skeleton = rows['CfgSkeletons']['Default']
        self.assertEqual(skeleton['skeletonBones'], [])
        self.assertEqual(skeleton['skeletonInherit'], '')
        self.assertEqual(skeleton['isDiscrete'], 1)
        model = rows['CfgModels']['HC_TestCube']
        self.assertEqual(model['sections'], sorted(sections))
        self.assertEqual(model['sectionsInherit'], '')
        self.assertEqual(model['skeletonName'], '')
        self.assertEqual(emit_model_cfg('HC_TestCube', ['top', 'body']),
                         emit_model_cfg('HC_TestCube', ['body', 'top']))
        empty = parse_model_cfg(emit_model_cfg('HC_Empty'))
        self.assertEqual(empty['CfgModels']['HC_Empty']['sections'], [])

    def test_cfg_identifier_and_section_injection_refused(self):
        for name in ('default', '1cube', '../cube', 'cube.p3d', 'cube; class Bad {}'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                emit_model_cfg(name)
        for sections in ('body', ['body', 'BODY'], ['bad";};'], [''], ['a'*64], [None]):
            with self.subTest(sections=sections), self.assertRaises(ValueError):
                emit_model_cfg('HC_TestCube', sections)


if __name__ == '__main__':
    unittest.main()
