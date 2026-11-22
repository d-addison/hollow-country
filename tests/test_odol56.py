"""Synthetic byte-fixture tests for the clean-room ODOL56 reader.

Every model here is assembled by the small writer below from plain Python values;
expectations are those same values, never decoded game data.
"""
import struct
import unittest

from tools.audit import odol56


def cstr(text):
    return text.encode('latin-1') + b'\0'


def u32(*values):
    return struct.pack('<%dI' % len(values), *values)


def lzo_literals(raw):
    """Smallest valid LZO1X stream: one literal run and the end marker."""
    marker = bytes([0x11, 0, 0])
    if len(raw) <= 238:
        return bytes([len(raw) + 17]) + raw + marker
    extra = len(raw) - 3 - 15
    zeros = (extra - 1) // 255
    return b'\0' + b'\0' * zeros + bytes([extra - 255 * zeros]) + raw + marker


def array_bytes(code, values):
    """CompressedArray as the reader expects it (LZO when 1024 bytes or more)."""
    raw = struct.pack('<%d%s' % (len(values), code), *values)
    body = lzo_literals(raw) if len(raw) >= odol56.LZO_THRESHOLD else raw
    return u32(len(values)) + body


def fill_bytes(values):
    """CompressedFillArray of u32: a single repeated value or the full list."""
    if len(set(values)) == 1:
        return u32(len(values)) + b'\1' + u32(values[0])
    raw = struct.pack('<%dI' % len(values), *values)
    body = lzo_literals(raw) if len(raw) >= odol56.LZO_THRESHOLD else raw
    return u32(len(values)) + b'\0' + body


def pack_normal(normal):
    value = 0
    for shift, part in zip((0, 10, 20), normal):
        value |= (round(part * odol56.PACKED_NORMAL_SCALE) & 0x3FF) << shift
    return value


class Spec:
    """Plain description of one LOD; defaults give a valid single-triangle LOD."""

    def __init__(self, resolution=1.0, vertices=None, faces=None, normals=None, textures=(),
                 proxies=(), selections=(), properties=None, sections=(), bbox=None,
                 local_to_bone=(), refs=None, extra_block=False):
        self.resolution = resolution
        self.vertices = vertices if vertices is not None else [(0., 0., 0.), (1., 0., 0.), (0., 0., 2.)]
        self.faces = faces if faces is not None else [[0, 1, 2]]
        self.normals = normals if normals is not None else [(0., 1., 0.)] * len(self.vertices)
        self.textures = list(textures)
        self.proxies = list(proxies)        # (path, 12 floats, sequence, selection, bone, section)
        self.selections = list(selections)  # (name, faces, vertices, weights, sectional)
        self.properties = properties or {}
        self.sections = list(sections)      # (first face, end face, texture, material index, material)
        self.bbox = bbox or ((0., 0., 0.), (1., 0., 2.), (.5, 0., 1.), 1.5)
        self.local_to_bone = list(local_to_bone)   # LOD-local bone number -> skeleton bone index
        self.refs = refs or [[] for _ in self.vertices]  # per vertex: [(local bone number, weight byte)]
        self.extra_block = extra_block             # emit the optional 8-bytes-per-vertex array


def lod_bytes(spec):
    out = bytearray(u32(len(spec.proxies)))
    for path, matrix, sequence, selection, bone, section in spec.proxies:
        out += cstr(path) + struct.pack('<12f', *matrix) + struct.pack('<IIiI', sequence, selection, bone, section)
    out += u32(len(spec.local_to_bone), *spec.local_to_bone)
    out += u32(len(spec.local_to_bone))
    for _ in spec.local_to_bone:                         # inverse table is not decoded
        out += u32(0)
    out += u32(len(spec.vertices)) + bytes(12)
    low, high, centre, radius = spec.bbox
    out += struct.pack('<10f', *low, *high, *centre, radius)
    out += u32(len(spec.textures)) + b''.join(cstr(t) for t in spec.textures)
    corners = [struct.pack('<B%dH' % len(f), len(f), *f) for f in spec.faces]
    out += u32(len(spec.faces), sum(len(c) + 1 for c in corners)) + b'\0\0' + b''.join(corners)
    offsets = [0]
    for face in spec.faces:
        offsets.append(offsets[-1] + 2 * len(face) + 2)
    out += u32(len(spec.sections))
    for first, last, texture, material_index, material in spec.sections:
        out += u32(offsets[first], offsets[last]) + bytes(12) + struct.pack('<h', texture) + bytes(4)
        out += struct.pack('<i', material_index) + (cstr(material) if material_index == -1 else b'') + u32(0)
    out += u32(len(spec.selections))
    for name, faces, vertices, weights, sectional in spec.selections:
        out += cstr(name) + array_bytes('H', faces) + bytes(4) + bytes([int(sectional)])
        out += array_bytes('I', []) + array_bytes('H', vertices) + array_bytes('B', weights)
    out += u32(len(spec.properties))
    for key, value in spec.properties.items():
        out += cstr(key) + cstr(value)
    out += u32(0) + u32(0, 0, 0) + b'\0'                 # frames, colours, flags, bone flag
    count = len(spec.vertices)
    rest = bytearray(fill_bytes([0] * count) + bytes(16) + fill_bytes([0] * count) + u32(1))
    flat = [c for v in spec.vertices for c in v]
    raw = struct.pack('<%df' % len(flat), *flat)
    rest += u32(count) + (lzo_literals(raw) if len(raw) >= odol56.LZO_THRESHOLD else raw)
    rest += fill_bytes([pack_normal(n) for n in spec.normals])
    if spec.extra_block:
        extra = bytes(8 * count)
        rest += u32(count) + (lzo_literals(extra) if len(extra) >= odol56.LZO_THRESHOLD else extra)
    else:
        rest += u32(0)
    rest += u32(count)
    records = b''
    for refs in spec.refs:
        pairs = b''.join(bytes([local, weight]) for local, weight in refs[:4]).ljust(8, b'\0')
        records += u32(len(refs)) + pairs
    rest += lzo_literals(records) if len(records) >= odol56.LZO_THRESHOLD else records
    rest += u32(0)
    return bytes(out) + u32(4 + len(rest)) + bytes(rest)


def model_bytes(specs, centre=(1., 2., 3.), version=56, skeleton=('', 0, ()), stored=None):
    count = len(specs)
    head = b'ODOL' + u32(version, count) + struct.pack('<%df' % count, *[s.resolution for s in specs])
    head += bytes(96) + struct.pack('<3f', *centre) + bytes(103)
    name, discrete, bones = skeleton
    head += struct.pack('<f', 3.4028234663852886e38) + b'\0' + cstr(name)
    if name:
        head += bytes([discrete]) + u32(len(bones)) + b''.join(cstr(b) + cstr(parent) for b, parent in bones)
    head += bytes(20)
    table_size = 9 * count
    blobs = [lod_bytes(s) for s in specs]
    total = len(head) + table_size + sum(len(b) for b in blobs)
    # LODs are normally stored in reverse order; `stored` lists spec indices in file order.
    order = list(stored) if stored is not None else list(range(count - 1, -1, -1))
    starts, ends, cursor = [0] * count, [0] * count, len(head) + table_size
    for index in order:
        starts[index] = cursor
        cursor += len(blobs[index])
        ends[index] = cursor
    assert max(ends) == total
    body = b''.join(blobs[i] for i in order)
    flags = bytes([1] * count)
    return head + u32(*starts) + u32(*ends) + flags + body


class LzoTests(unittest.TestCase):
    def test_literal_run_and_end_marker(self):
        raw = bytes(range(200))
        stream = lzo_literals(raw) + b'trailing'
        out, after = odol56.lzo1x_decompress(stream, 0, len(raw))
        self.assertEqual(out, raw)
        self.assertEqual(stream[after:], b'trailing')

    def test_long_literal_run_uses_extended_length(self):
        raw = bytes(i % 251 for i in range(3000))
        self.assertEqual(odol56.lzo1x_decompress(lzo_literals(raw), 0, len(raw))[0], raw)

    def test_back_reference_and_overlapping_copy(self):
        marker = bytes([0x11, 0, 0])
        stream = bytes([17 + 4]) + b'abcd' + bytes([0x6C, 0]) + marker
        self.assertEqual(odol56.lzo1x_decompress(stream, 0, 8)[0], b'abcdabcd')
        stream = bytes([17 + 1]) + b'a' + bytes([0x80, 0]) + marker
        self.assertEqual(odol56.lzo1x_decompress(stream, 0, 6)[0], b'a' * 6)

    def test_wrong_size_truncation_and_bad_distance_are_typed(self):
        raw = bytes(range(40))
        good = lzo_literals(raw)
        for stream, expected in ((good, len(raw) + 1), (good[:-2], len(raw)), (b'', 1),
                                 (bytes([17 + 1]) + b'a' + bytes([0x80, 9]) + bytes([0x11, 0, 0]), 6)):
            with self.assertRaises(odol56.UnsupportedCompression):
                odol56.lzo1x_decompress(stream, 0, expected)


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.near = Spec(
            resolution=1.0,
            vertices=[(0., 0., 0.), (1., 0., 0.), (0., 0., 2.), (1., 0., 2.)],
            faces=[[0, 1, 2], [1, 3, 2]],
            normals=[(0., 1., 0.), (1., 0., 0.), (0., 0., -1.), (-1., 0., 0.)],
            textures=['a\\one.paa', 'a\\two.paa'],
            proxies=[('a\\chair.p3d', tuple(float(i) for i in range(12)), 1, 2, -1, 3)],
            selections=[('doors', [1], [0, 1], [255, 128], False), ('roof', [0, 1], [], [], True)],
            properties={'lodnoshadow': '1'},
            sections=[(0, 1, 0, -1, 'a\\mat.rvmat'), (1, 2, 1, 4, '')],
            bbox=((0., 0., 0.), (1., 0., 2.), (.5, 0., 1.), 2.25))
        self.far = Spec(resolution=1e13, vertices=[(5., 5., 5.), (6., 5., 5.), (5., 6., 5.)])
        self.data = model_bytes([self.near, self.far], centre=(1.5, 2.5, 3.5))
        self.model = odol56.read_odol(self.data)

    def test_header_table_and_resolutions(self):
        model = self.model
        self.assertEqual(model.version, 56)
        single = lambda value: struct.unpack('<f', struct.pack('<f', value))[0]
        self.assertEqual(model.resolutions, [single(self.near.resolution), single(self.far.resolution)])
        self.assertEqual(tuple(model.bounding_center), (1.5, 2.5, 3.5))
        self.assertEqual(model.lod_ends[0], len(self.data))
        self.assertEqual(model.lod_ends[1], model.lod_starts[0])
        self.assertEqual(model.permanent, [True, True])
        self.assertIs(model.lod_by_resolution(self.far.resolution), model.lods[1])
        self.assertIsNone(model.lod_by_resolution(123.0))
        self.assertEqual(model.failed_lods, {})

    def test_lod_geometry_and_bounds(self):
        lod = self.model.lods[0]
        self.assertEqual([tuple(v) for v in lod.vertices], self.near.vertices)
        self.assertEqual(lod.faces, self.near.faces)
        self.assertEqual(lod.textures, self.near.textures)
        low, high, centre, radius = self.near.bbox
        self.assertEqual((tuple(lod.bbox_min), tuple(lod.bbox_max), tuple(lod.bbox_center), lod.bbox_radius),
                         (low, high, centre, radius))
        for got, want in zip(lod.normals, self.near.normals):
            for a, b in zip(got, want):
                self.assertAlmostEqual(a, b, delta=1.0 / odol56.PACKED_NORMAL_SCALE)
        self.assertEqual(lod.properties, self.near.properties)

    def test_sections_proxies_and_selections(self):
        lod = self.model.lods[0]
        self.assertEqual([(s.face_start, s.face_end, s.texture_index, s.material_index, s.material)
                          for s in lod.sections], self.near.sections)
        proxy, = lod.proxies
        path, matrix, sequence, selection, bone, section = self.near.proxies[0]
        self.assertEqual((proxy.path, tuple(proxy.matrix), proxy.sequence, proxy.selection, proxy.bone, proxy.section),
                         (path, matrix, sequence, selection, bone, section))
        doors = lod.selection('DOORS')
        self.assertEqual((doors.faces, doors.vertices), ([1], [0, 1]))
        # a stored weight byte b is min(1, (255 - b) / 254)
        self.assertAlmostEqual(doors.weights[0], 0.0)
        self.assertAlmostEqual(doors.weights[1], 127 / 254.0)
        self.assertFalse(doors.sectional)
        roof = lod.selection('roof')
        # A sectional selection without stored vertices stays empty (no derived vertices).
        self.assertEqual((roof.faces, roof.vertices, roof.weights, roof.sectional), ([0, 1], [], [], True))
        self.assertIsNone(lod.selection('missing'))

    def test_zero_face_lod_and_single_lod(self):
        empty = Spec(faces=[], vertices=[(0., 0., 0.), (1., 1., 1.)])
        model = odol56.read_odol(model_bytes([empty]))
        self.assertEqual((model.lods[0].faces, len(model.lods[0].vertices)), ([], 2))

    def test_large_arrays_use_lzo(self):
        count = 120                         # 12 * count >= LZO threshold
        vertices = [(float(i), float(i % 7), -float(i)) for i in range(count)]
        faces = [[i, (i + 1) % count, (i + 2) % count] for i in range(count)]
        names = [('big', list(range(count)), list(range(count)), [i % 256 for i in range(count)], False)]
        spec = Spec(vertices=vertices, faces=faces, selections=names,
                    normals=[(0., 1., 0.)] * count)
        self.assertGreaterEqual(12 * count, odol56.LZO_THRESHOLD)
        lod = odol56.read_odol(model_bytes([spec])).lods[0]
        self.assertEqual([tuple(v) for v in lod.vertices], vertices)
        self.assertEqual(lod.faces, faces)
        self.assertEqual(lod.selection('big').faces, names[0][1])

    def test_lod_order_in_file_need_not_be_reversed(self):
        specs = [Spec(resolution=1.0), Spec(resolution=2.0, vertices=self.far.vertices),
                 Spec(resolution=3.0, vertices=[(7., 7., 7.), (8., 7., 7.), (7., 8., 7.)])]
        for stored in ([0, 1, 2], [1, 0, 2], [2, 0, 1]):
            model = odol56.read_odol(model_bytes(specs, stored=stored))
            self.assertEqual([[tuple(v) for v in lod.vertices] for lod in model.lods],
                             [spec.vertices for spec in specs])
            self.assertEqual(max(model.lod_ends), len(model_bytes(specs, stored=stored)))

    def test_stream_wrapper_matches_function(self):
        import io
        again = odol56.OdolFile.read(io.BytesIO(self.data))
        self.assertEqual(again.lod_starts, self.model.lod_starts)

    def test_vertex_data_is_independent_of_other_lods(self):
        self.assertEqual([tuple(v) for v in self.model.lods[1].vertices], self.far.vertices)


class SkeletonTests(unittest.TestCase):
    BONES = [('doors1', ''), ('doors2', ''), ('doors3', 'doors1')]
    VERTICES = [(float(i), 0., 0.) for i in range(6)]

    def build(self, refs, local_to_bone, selections, **options):
        spec = Spec(vertices=self.VERTICES, faces=[[0, 1, 2]], normals=[(0., 1., 0.)] * 6,
                    selections=selections, local_to_bone=local_to_bone, refs=refs, **options)
        data = model_bytes([spec], skeleton=('SkeletonDoors', 1, self.BONES))
        return odol56.read_odol(data)

    def test_skeleton_names_are_read(self):
        model = self.build(None, [], [])
        self.assertEqual(model.skeleton, 'SkeletonDoors')
        self.assertEqual(model.bones, self.BONES)
        plain = odol56.read_odol(model_bytes([Spec()]))
        self.assertEqual((plain.skeleton, plain.bones), ('', []))

    def test_bound_vertices_follow_local_bone_numbers_to_selection_names(self):
        # local numbers 0,1,2 map to skeleton bones 2,0,1: not the selection order
        local_to_bone = [2, 0, 1]
        selections = [('doors2', [], [], [], False), ('doors1', [], [], [], False),
                      ('doors3', [], [], [], False), ('unrelated', [], [], [], False)]
        refs = [[(0, 255)], [(0, 255)], [(1, 255)], [(2, 128)], [], [(2, 255), (1, 64)]]
        model = self.build(refs, local_to_bone, selections)
        by_bone = {}
        for vertex, vertex_refs in enumerate(refs):
            for local, weight in vertex_refs:
                by_bone.setdefault(self.BONES[local_to_bone[local]][0], []).append((vertex, weight / 255.0))
        lod = model.lods[0]
        for name in ('doors1', 'doors2', 'doors3'):
            got = lod.selection(name)
            self.assertEqual(list(zip(got.vertices, got.weights)), by_bone[name])
        self.assertEqual(lod.selection('unrelated').vertices, [])

    def test_bound_vertices_replace_stored_ones_and_optional_block_is_skipped(self):
        refs = [[(0, 255)]] * 3 + [[]] * 3
        stored = [('doors1', [], [4, 5], [255, 255], False)]
        model = self.build(refs, [0], stored, extra_block=True)
        self.assertEqual(model.lods[0].selection('doors1').vertices, [0, 1, 2])
        big = Spec(vertices=[(float(i), 0., 0.) for i in range(140)], faces=[[0, 1, 2]],
                   normals=[(0., 1., 0.)] * 140, extra_block=True)
        self.assertGreaterEqual(8 * 140, odol56.LZO_THRESHOLD)
        self.assertEqual(len(odol56.read_odol(model_bytes([big])).lods[0].vertices), 140)

    def test_reference_outside_skeleton_fails_closed(self):
        selections = [('doors1', [], [], [], False)]
        for local_to_bone, refs in (([], [[(0, 255)]] + [[]] * 5), ([7], [[(0, 255)]] + [[]] * 5),
                                    ([0], [[(3, 255)]] + [[]] * 5)):
            with self.assertRaises(odol56.MalformedModel):
                self.build(refs, local_to_bone, selections)

    def test_missing_skeleton_marker_fails_closed(self):
        data = bytearray(model_bytes([Spec()]))
        at = data.find(struct.pack('<f', 3.4028234663852886e38))
        self.assertGreater(at, 0)
        data[at:at + 4] = bytes(4)
        with self.assertRaises(odol56.MalformedModel):
            odol56.read_odol(bytes(data))


class FailClosedTests(unittest.TestCase):
    def setUp(self):
        self.data = model_bytes([Spec(), Spec(resolution=2.0)])

    def test_unknown_versions_and_magic(self):
        for version in (28, 54, 57, 70):
            with self.assertRaises(odol56.UnsupportedVersion):
                odol56.read_odol(model_bytes([Spec()], version=version))
        with self.assertRaises(odol56.UnsupportedVersion):
            odol56.read_odol(b'MLOD' + self.data[4:])
        with self.assertRaises(odol56.UnsupportedVersion):
            odol56.read_odol(b'')

    def test_every_error_is_an_odol_error_and_a_value_error(self):
        self.assertTrue(issubclass(odol56.UnsupportedVersion, odol56.OdolError))
        self.assertTrue(issubclass(odol56.UnsupportedCompression, odol56.OdolError))
        self.assertTrue(issubclass(odol56.MalformedModel, odol56.OdolError))
        self.assertTrue(issubclass(odol56.OdolError, ValueError))

    def test_bad_lod_counts_and_missing_table(self):
        for count in (0, odol56.MAX_LODS + 1):
            with self.assertRaises(odol56.MalformedModel):
                odol56.read_odol(self.data[:8] + u32(count) + self.data[12:])
        with self.assertRaises(odol56.MalformedModel):
            odol56.read_odol(self.data[:40])
        with self.assertRaises(odol56.MalformedModel):
            odol56.read_odol(self.data + b'x')      # file size no longer matches the table

    def test_truncations_never_escape_as_other_exceptions(self):
        for cut in range(0, len(self.data), 7):
            try:
                odol56.read_odol(self.data[:cut])
            except odol56.OdolError:
                pass

    def test_corrupt_lzo_is_unsupported_compression(self):
        count = 120
        spec = Spec(vertices=[(float(i), 0., 0.) for i in range(count)],
                    faces=[[0, 1, 2]], normals=[(0., 1., 0.)] * count)
        data = bytearray(model_bytes([spec]))
        marker = bytes([0x11, 0, 0])
        # Damage the end marker of the position array: the stream no longer terminates.
        raw = struct.pack('<%df' % (3 * count), *[c for i in range(count) for c in (float(i), 0., 0.)])
        start = bytes(data).find(raw)
        self.assertGreater(start, 0)
        end = start + len(raw) + len(marker)
        self.assertEqual(bytes(data[end - 3:end]), marker)
        data[end - 3:end] = bytes([0x11, 0x55, 0x55])
        with self.assertRaises(odol56.UnsupportedCompression):
            odol56.read_odol(bytes(data))

    def test_failed_lod_is_recorded_only_when_not_strict(self):
        data = bytearray(self.data)
        model = odol56.read_header(bytes(data))
        # Break the second stored LOD (index 0 sits last) by wiping its polygon block.
        lod = odol56.read_odol(bytes(data)).lods[1]
        self.assertEqual(lod.index, 1)
        start, end = model.lod_starts[1], model.lod_ends[1]
        data[start:end] = bytes(end - start)
        with self.assertRaises(odol56.OdolError):
            odol56.read_odol(bytes(data))
        loose = odol56.read_odol(bytes(data), strict=False)
        self.assertEqual(sorted(loose.failed_lods), [1])
        self.assertEqual([lod.index for lod in loose.lods], [0])

    def test_selection_pointing_outside_the_lod_fails(self):
        for selection in (('bad', [9], [0], [255], False), ('bad', [0], [9], [255], False)):
            with self.assertRaises(odol56.OdolError):
                odol56.read_odol(model_bytes([Spec(selections=[selection])]))

    def test_frames_are_refused_not_misread(self):
        spec = Spec()
        data = bytearray(model_bytes([spec]))
        end = odol56.read_header(bytes(data)).lod_ends[0]
        # The size-of-rest field is the last u32 before the rest data; locate it by
        # its value (bytes from its own start to the end of the LOD).
        rest = next(i for i in range(end - 4, 0, -1) if struct.unpack_from('<I', data, i)[0] == end - i)
        # frames count, two colours, flags and the bone flag precede it: 4 + 12 + 1 bytes.
        index = rest - 17
        self.assertEqual(bytes(data[index:rest]), u32(0) + u32(0, 0, 0) + b'\0')
        data[index:index + 4] = u32(1)
        with self.assertRaises(odol56.MalformedModel):
            odol56.read_odol(bytes(data))


if __name__ == '__main__':
    unittest.main()
