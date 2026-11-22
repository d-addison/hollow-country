# SPDX-License-Identifier: MIT
"""Clean-room reader for binarised P3D models (ODOL, version 56).

Written from observation of installed model bytes only. No third-party reader
source was consulted. The reader is deliberately narrow: it decodes what the
audit and generation tools need and refuses everything else with a typed error.

Decoded per model: LOD list with resolutions and address table, the bounding
centre, and for every LOD the proxy table, vertex positions, vertex normals,
polygons, sections, texture list, named selections (faces, vertices, weights),
properties and bounding box. Memory points, Geometry, Fire Geometry and Paths
are ordinary LODs here (identified by their resolution value, see
lod_by_resolution): memory points are the vertices of the memory LOD and the
named selections that group them.

Selection semantics: faces and vertices are the stored index lists. A stored
weight byte b means min(1, (255 - b) / 254); selections without stored weights
get 1.0 per vertex. Selections
that name a skeleton bone (doors, character bones) take their vertices and
weights from the per-vertex bone references at the end of the LOD, which replace
any vertices stored in the selection record. The per-vertex data array that
precedes them, and the skeleton animation tables, are not decoded.

Not decoded: material (rvmat) bodies, UV and tangent data, animation data and
frames. The material
block is skipped by anchoring on the polygon block that follows it, and a LOD is
accepted only when the whole chain from the polygon block to the end of the LOD
parses exactly and uniquely. Anything else raises OdolError (fail closed).

Layout notes, all little endian:

  file    "ODOL", u32 version (56), u32 LOD count n, n f32 resolutions, a model
          info block of variable length whose bounding centre sits 96 bytes
          after the resolution list, followed at a fixed offset (211 bytes after
          the list) by the skeleton (largest f32, flag byte, name, and for a named
          skeleton a u8 flag, u32 bone count and bone/parent NUL strings), then
          the LOD address table: n u32 starts,
          n u32 ends, n permanent flag bytes. The LOD ranges tile the rest of
          the file (usually stored in reverse order, not always).
  LOD     proxy table (u32 count, then NUL path, 12 f32 matrix, 4 u32 each),
          two bone index tables (LOD-local bone -> skeleton bone, and its
          inverse), u32 vertex count, 12 reserved bytes, bounding
          box min/max/centre as f32 triples, f32 radius, texture list
          (u32 count, NUL strings), material block (skipped), polygons
          (u32 count, u32 byte size, u16, then u8 n + n u16 indices per face),
          sections, named selections, properties, frames (must be empty), two
          u32 colours, u32 flags, u8, and u32 size-of-rest. The size-of-rest
          field counts from its own first byte to the end of the LOD.
  rest    vertex flags, one UV set with a u32 set count, optional extra UV
          sets, then vertex positions (f32 x3) and packed normals (u32,
          10/10/10 signed), an optional 8-bytes-per-vertex array, the per-vertex
          bone references (u32 n, four u8 bone/u8 weight pairs) and a closing
          u32 zero. Arrays of 1024 bytes or more are LZO1X compressed.
"""
from __future__ import annotations

import struct

VERSION = 56
LZO_THRESHOLD = 1024
MAX_LODS = 64
MAX_COUNT = 1 << 22
MAX_PROXIES = 4096
MAX_FACE_CORNERS = 16

PACKED_NORMAL_SCALE = 511.0


class OdolError(ValueError):
    """Base class of every failure raised by this reader."""


class UnsupportedVersion(OdolError):
    """The file is not an ODOL version this reader understands."""


class UnsupportedCompression(OdolError):
    """A compressed block could not be decoded as LZO1X of the expected size."""


class MalformedModel(OdolError):
    """The bytes do not parse as the documented layout."""


# --------------------------------------------------------------------------
# LZO1X block decoder
# --------------------------------------------------------------------------

def lzo1x_decompress(src, pos, expected):
    """Decode one LZO1X stream starting at src[pos].

    Returns (bytes, position after the end marker). The stream must produce
    exactly `expected` bytes; anything else raises UnsupportedCompression.
    """
    out = bytearray()
    end = len(src)
    ip = pos

    def fail(reason):
        raise UnsupportedCompression('lzo: ' + reason)

    def extend_length(base):
        nonlocal ip
        total = base
        while True:
            if ip >= end:
                fail('truncated length')
            byte = src[ip]
            ip += 1
            if byte:
                return total + byte
            total += 255

    if ip >= end:
        fail('empty stream')
    state = 0
    first = src[ip]
    if first > 17:
        count = first - 17
        ip += 1
        if ip + count > end:
            fail('truncated literal run')
        out += src[ip:ip + count]
        ip += count
        state = 4 if count >= 4 else count
    while True:
        if ip >= end:
            fail('truncated stream')
        opcode = src[ip]
        ip += 1
        if opcode < 16:
            if state == 0:
                length = opcode + 3 if opcode else extend_length(15) + 3
                if ip + length > end:
                    fail('truncated literal run')
                out += src[ip:ip + length]
                ip += length
                state = 4
                continue
            if ip >= end:
                fail('truncated match')
            high = src[ip]
            ip += 1
            if state == 4:
                distance = 2049 + (opcode >> 2) + (high << 2)
                length = 3
            else:
                distance = 1 + (opcode >> 2) + (high << 2)
                length = 2
            trail = opcode & 3
        elif opcode >= 64:
            if ip >= end:
                fail('truncated match')
            high = src[ip]
            ip += 1
            distance = 1 + ((opcode >> 2) & 7) + (high << 3)
            length = (opcode >> 5) + 1
            trail = opcode & 3
        elif opcode >= 32:
            length = opcode & 31
            length = extend_length(31) if not length else length
            if ip + 2 > end:
                fail('truncated match')
            value = src[ip] | (src[ip + 1] << 8)
            ip += 2
            distance = 1 + (value >> 2)
            length += 2
            trail = value & 3
        else:
            length = opcode & 7
            length = extend_length(7) if not length else length
            if ip + 2 > end:
                fail('truncated match')
            value = src[ip] | (src[ip + 1] << 8)
            ip += 2
            distance = ((opcode & 8) << 11) + (value >> 2)
            if distance == 0:
                if len(out) != expected:
                    fail('size %d, expected %d' % (len(out), expected))
                return bytes(out), ip
            distance += 16384
            length += 2
            trail = value & 3
        if distance > len(out):
            fail('distance before start')
        if len(out) + length + trail > expected:
            fail('output beyond expected size')
        start = len(out) - distance
        if distance >= length:
            out += out[start:start + length]
        else:
            for index in range(length):
                out.append(out[start + index])
        if trail:
            if ip + trail > end:
                fail('truncated literal tail')
            out += src[ip:ip + trail]
            ip += trail
        state = trail


# --------------------------------------------------------------------------
# Cursor
# --------------------------------------------------------------------------

class Cursor:
    """Bounds-checked reader over data[pos:end]."""

    __slots__ = ('data', 'pos', 'end')

    def __init__(self, data, pos, end):
        self.data, self.pos, self.end = data, pos, end

    def take(self, size):
        if size < 0 or self.pos + size > self.end:
            raise MalformedModel('read past end of block')
        start = self.pos
        self.pos += size
        return start

    def u8(self):
        return self.data[self.take(1)]

    def u32(self):
        return struct.unpack_from('<I', self.data, self.take(4))[0]

    def floats(self, count):
        return struct.unpack_from('<%df' % count, self.data, self.take(4 * count))

    def cstring(self, limit=4096):
        stop = self.data.find(b'\0', self.pos, min(self.end, self.pos + limit))
        if stop < 0:
            raise MalformedModel('unterminated string')
        text = bytes(self.data[self.pos:stop]).decode('latin-1')
        self.pos = stop + 1
        return text

    def count(self, limit=MAX_COUNT):
        value = self.u32()
        if value > limit:
            raise MalformedModel('count %d outside bound' % value)
        return value

    def array(self, code):
        """u32 count then count elements; LZO1X when the payload is large."""
        size = struct.calcsize('<' + code)
        count = self.count()
        raw = self.payload(count * size)
        return list(struct.unpack('<%d%s' % (count, code), raw))

    def payload(self, nbytes):
        if nbytes >= LZO_THRESHOLD:
            raw, self.pos = lzo1x_decompress(self.data[:self.end], self.pos, nbytes)
            return raw
        return bytes(self.data[self.take(nbytes):self.pos])

    def fill_array(self, code):
        """u32 count, u8 default-fill flag, then one element or count elements."""
        size = struct.calcsize('<' + code)
        count = self.count()
        flag = self.u8()
        if flag > 1:
            raise MalformedModel('fill flag %d' % flag)
        if flag:
            one = struct.unpack_from('<' + code, self.data, self.take(size))[0]
            return [one] * count
        raw = self.payload(count * size)
        return list(struct.unpack('<%d%s' % (count, code), raw))


# --------------------------------------------------------------------------
# Model objects (mutable: consumers re-centre vertices and filter LODs)
# --------------------------------------------------------------------------

class Selection:
    def __init__(self, name, faces, vertices, weights, sectional):
        self.name = name
        self.faces = faces
        self.vertices = vertices
        self.weights = weights
        self.sectional = sectional


class Section:
    def __init__(self, face_start, face_end, texture_index, material_index, material):
        self.face_start = face_start
        self.face_end = face_end
        self.texture_index = texture_index
        self.material_index = material_index
        self.material = material


class Proxy:
    def __init__(self, path, matrix, sequence, selection, bone, section):
        self.path = path
        self.matrix = matrix
        self.sequence = sequence
        self.selection = selection
        self.bone = bone
        self.section = section


class Lod:
    def __init__(self, index, resolution):
        self.index = index
        self.resolution = resolution
        self.proxies = []
        self.textures = []
        self.vertices = []
        self.normals = []
        self.faces = []
        self.sections = []
        self.named_selections = []
        self.properties = {}
        self.bbox_min = self.bbox_max = self.bbox_center = (0.0, 0.0, 0.0)
        self.bbox_radius = 0.0

    def selection(self, name):
        for item in self.named_selections:
            if item.name.lower() == name.lower():
                return item
        return None


class OdolFile:
    def __init__(self):
        self.version = VERSION
        self.resolutions = []
        self.lod_starts = []
        self.lod_ends = []
        self.permanent = []
        self.bounding_center = (0.0, 0.0, 0.0)
        self.skeleton = ''
        self.bones = []
        self.lods = []
        self.failed_lods = {}

    @classmethod
    def read(cls, stream, strict=True):
        return read_odol(stream.read(), strict=strict)

    def lod_by_resolution(self, resolution, rel_tol=1e-6):
        for lod in self.lods:
            if abs(lod.resolution - resolution) <= rel_tol * max(abs(resolution), 1.0):
                return lod
        return None


# --------------------------------------------------------------------------
# File header
# --------------------------------------------------------------------------

def _tiles(starts, ends, data_start, size):
    """True when the [start, end) ranges tile data_start..size without gaps."""
    if any(s >= e for s, e in zip(starts, ends)):
        return False
    order = sorted(range(len(starts)), key=lambda i: starts[i])
    if starts[order[0]] < data_start or ends[order[-1]] != size:
        return False
    return all(ends[a] == starts[b] for a, b in zip(order, order[1:]))


def _address_table(data, count, search_from):
    """Find and validate the LOD address table; returns (offset, starts, ends).

    The table is n starts, n ends, n permanent flags. The LOD ranges tile the
    rest of the file; the stored order is usually reversed but not always, so the
    entry whose end equals the file size can sit at any index.
    """
    size = len(data)
    pattern = struct.pack('<I', size)
    found = set()
    probe = data.find(pattern, search_from + 4 * count)
    while probe >= 0:
        for slot in range(count):
            table = probe - 4 * (count + slot)
            if table < search_from:
                break
            starts = struct.unpack_from('<%dI' % count, data, table)
            ends = struct.unpack_from('<%dI' % count, data, table + 4 * count)
            data_start = table + 9 * count
            if ends[slot] == size and data_start <= size and _tiles(starts, ends, data_start, size):
                found.add((table, starts, ends))
        probe = data.find(pattern, probe + 1)
    if len(found) != 1:
        raise MalformedModel('LOD address table %s' % ('not found' if not found else 'ambiguous'))
    return found.pop()


SKELETON_MARKER = struct.pack('<f', 3.4028234663852886e38)
SKELETON_OFFSET = 108 + 103     # from the end of the LOD resolution list


def _read_skeleton(data, base, limit):
    """Skeleton name and bone names; a model without one has an empty name.

    A fixed marker (largest f32) and a 0/1 flag byte precede the name. A named skeleton
    continues with a u8 flag, u32 bone count and (bone, parent) NUL strings.
    """
    at = base + SKELETON_OFFSET
    if data[at:at + 4] != SKELETON_MARKER or data[at + 4:at + 5] not in (b'\0', b'\1'):
        raise MalformedModel('skeleton marker not found')
    cur = Cursor(data, at + 5, limit)
    name = cur.cstring(256)
    bones = []
    if name:
        if cur.u8() > 1:
            raise MalformedModel('skeleton flag')
        for _ in range(cur.count(4096)):
            bones.append((cur.cstring(256), cur.cstring(256)))
    return name, bones


def read_header(data):
    if len(data) < 16 or data[:4] != b'ODOL':
        raise UnsupportedVersion('not an ODOL file')
    version, count = struct.unpack_from('<II', data, 4)
    if version != VERSION:
        raise UnsupportedVersion('ODOL version %d' % version)
    if not 0 < count <= MAX_LODS:
        raise MalformedModel('LOD count %d' % count)
    model = OdolFile()
    model.version = version
    base = 12 + 4 * count
    if base + 96 + 12 > len(data):
        raise MalformedModel('truncated header')
    model.resolutions = list(struct.unpack_from('<%df' % count, data, 12))
    model.bounding_center = struct.unpack_from('<3f', data, base + 96)
    table, starts, ends = _address_table(data, count, base + 108)
    model.lod_starts, model.lod_ends = list(starts), list(ends)
    model.permanent = [bool(v) for v in data[table + 8 * count:table + 9 * count]]
    model.skeleton, model.bones = _read_skeleton(data, base, table)
    return model


# --------------------------------------------------------------------------
# LOD
# --------------------------------------------------------------------------

def _read_proxies(cur):
    proxies = []
    for _ in range(cur.count(MAX_PROXIES)):
        path = cur.cstring(1024)
        matrix = cur.floats(12)
        sequence, selection, bone, section = struct.unpack_from('<IIiI', cur.data, cur.take(16))
        proxies.append(Proxy(path, matrix, sequence, selection, bone, section))
    return proxies


def _read_bone_tables(cur):
    """Two index tables, empty on static models. The first maps this LOD's local
    bone numbers to skeleton bone indices; the second is its inverse (skeleton
    bone -> local numbers) and is not needed. Returns the first table."""
    local_to_bone = [cur.u32() for _ in range(cur.count(MAX_COUNT))]
    for _ in range(cur.count(MAX_COUNT)):
        for _ in range(cur.count(MAX_COUNT)):
            cur.u32()
    return local_to_bone


def _try_polygons(data, pos, end, vertex_count):
    """Parse a polygon block header at pos; returns (faces, after) or None."""
    if pos + 10 > end:
        return None
    count, size, zero = struct.unpack_from('<IIH', data, pos)
    if zero or count > MAX_COUNT or size < 8 * count or size > 2 * (MAX_FACE_CORNERS + 1) * count:
        return None
    cursor = pos + 10
    faces = []
    total = 0
    for _ in range(count):
        if cursor >= end:
            return None
        corners = data[cursor]
        if not 3 <= corners <= MAX_FACE_CORNERS:
            return None
        cursor += 1
        if cursor + 2 * corners > end:
            return None
        face = list(struct.unpack_from('<%dH' % corners, data, cursor))
        if max(face) >= vertex_count:
            return None
        cursor += 2 * corners
        total += 2 * corners + 2
        faces.append(face)
    if total != size:
        return None
    return faces, cursor


def _read_sections(cur, faces):
    sections = []
    offsets = [0]
    for face in faces:
        offsets.append(offsets[-1] + 2 * len(face) + 2)
    where = {value: index for index, value in enumerate(offsets)}
    for _ in range(cur.count(65536)):
        begin, finish = cur.u32(), cur.u32()
        if begin not in where or finish not in where or finish < begin:
            raise MalformedModel('section outside polygon block')
        cur.take(12)                    # min bone, bone count, reserved
        texture = struct.unpack_from('<h', cur.data, cur.take(2))[0]
        cur.take(4)                     # common face flags
        material_index = struct.unpack_from('<i', cur.data, cur.take(4))[0]
        material = cur.cstring(1024) if material_index == -1 else ''
        cur.take(4 * cur.count(64))     # per-stage area values
        sections.append(Section(where[begin], where[finish], texture, material_index, material))
    return sections


def _read_selections(cur, polygons, vertex_count):
    face_count = len(polygons)
    selections = []
    for _ in range(cur.count(65536)):
        name = cur.cstring(1024)
        faces = cur.array('H')
        cur.take(4)                     # always zero
        sectional = cur.u8()
        if sectional > 1:
            raise MalformedModel('sectional flag')
        cur.array('I')                  # section indices (empty unless sectional)
        vertices = cur.array('H')
        weights = cur.array('B')
        if faces and max(faces) >= face_count:
            raise MalformedModel('selection face index')
        if vertices and max(vertices) >= vertex_count:
            raise MalformedModel('selection vertex index')
        if weights and len(weights) != len(vertices):
            raise MalformedModel('selection weight count')
        weights = [min(1.0, (255 - w) / 254.0) for w in weights] if weights else [1.0] * len(vertices)
        selections.append(Selection(name, faces, vertices, weights, bool(sectional)))
    return selections


def _read_properties(cur):
    props = {}
    for _ in range(cur.count(4096)):
        name = cur.cstring(1024)
        props[name] = cur.cstring(4096)
    return props


def _chain_after_polygons(data, pos, end, faces, vertex_count):
    """Parse sections .. size-of-rest. Returns a result tuple or None."""
    try:
        cur = Cursor(data, pos, end)
        sections = _read_sections(cur, faces)
        selections = _read_selections(cur, faces, vertex_count)
        props = _read_properties(cur)
        if cur.u32():
            return None                 # frames are not supported
        cur.take(4 + 4 + 4 + 1)         # colours, flags, bone-reference flag
        rest = cur.pos
        if cur.u32() != end - rest:
            return None
        return sections, selections, props, rest
    except (MalformedModel, UnsupportedCompression, struct.error):
        return None


def _rest_arrays(data, rest, end, vertex_count):
    cur = Cursor(data, rest + 4, end)
    try:
        flags = cur.fill_array('I')
        cur.take(16)                    # UV bounds of the first set
        cur.fill_array('I')
        sets = cur.count(16)
        if not sets or len(flags) != vertex_count:
            raise MalformedModel('vertex flag or UV set count')
        for _ in range(sets - 1):
            cur.take(16)
            cur.fill_array('I')
        count = cur.count()
        if count != vertex_count:
            raise MalformedModel('position count')
        positions = struct.unpack('<%df' % (3 * count), cur.payload(12 * count))
        packed = cur.fill_array('I')
    except struct.error as exc:
        raise MalformedModel(str(exc))
    if len(packed) != vertex_count:
        raise MalformedModel('normal count')
    vertices = [tuple(positions[3 * i:3 * i + 3]) for i in range(count)]
    return vertices, [_unpack_normal(v) for v in packed], cur


def _selection_refs(cur, vertex_count):
    """Per-vertex selection references that follow the normals.

    An optional array of 8 bytes per vertex (not decoded; its count is 0 or the
    vertex count), then an optional array of 12 bytes per vertex (count 0 or the
    vertex count): u32 n, four (u8 selection
    index, u8 weight) pairs of which the first n count. Animated selections (doors,
    bones) list their vertices here rather than in the selection record. A u32
    zero closes the LOD. Returns [(vertex, selection, weight)].
    """
    if cur.count() not in (0, vertex_count):
        raise MalformedModel('vertex data count')
    cur.pos -= 4
    skipped = cur.count()
    cur.payload(8 * skipped)
    bound = cur.count()
    if bound not in (0, vertex_count):
        raise MalformedModel('selection reference count')
    raw = cur.payload(12 * bound)
    if cur.u32() or cur.pos != cur.end:
        raise MalformedModel('unexpected data after selection references')
    refs = []
    for vertex in range(bound):
        used, pairs = struct.unpack_from('<I8s', raw, 12 * vertex)
        if used > 4:
            raise MalformedModel('selection reference size')
        for slot in range(used):
            refs.append((vertex, pairs[2 * slot], pairs[2 * slot + 1]))
    return refs


def _unpack_normal(value):
    parts = []
    for shift in (0, 10, 20):
        part = (value >> shift) & 0x3FF
        if part & 0x200:
            part -= 0x400
        parts.append(max(-1.0, part / PACKED_NORMAL_SCALE))
    return tuple(parts)


def _apply_refs(model, selections, local_to_bone, refs):
    """Give each selection that names a skeleton bone the vertices bound to it."""
    by_name = {}
    for item in selections:
        by_name.setdefault(item.name.lower(), []).append(item)
    bound = {}
    for vertex, local, weight in refs:
        if local >= len(local_to_bone) or local_to_bone[local] >= len(model.bones):
            raise MalformedModel('bone reference outside skeleton')
        name = model.bones[local_to_bone[local]][0].lower()
        for item in by_name.get(name, ()):
            bound.setdefault(id(item), (item, []))[1].append((vertex, weight / 255.0))
    for item, pairs in bound.values():
        item.vertices = [v for v, _ in pairs]
        item.weights = [w for _, w in pairs]


def read_lod(data, model, index):
    start, end = model.lod_starts[index], model.lod_ends[index]
    lod = Lod(index, model.resolutions[index])
    cur = Cursor(data, start, end)
    lod.proxies = _read_proxies(cur)
    local_to_bone = _read_bone_tables(cur)
    vertex_count = cur.count()
    cur.take(12)
    lod.bbox_min = cur.floats(3)
    lod.bbox_max = cur.floats(3)
    lod.bbox_center = cur.floats(3)
    lod.bbox_radius = cur.floats(1)[0]
    for _ in range(cur.count(65536)):
        lod.textures.append(cur.cstring(1024))
    results = []
    for pos in range(cur.pos, end - 10):
        parsed = _try_polygons(data, pos, end, vertex_count)
        if parsed is None:
            continue
        faces, after = parsed
        chain = _chain_after_polygons(data, after, end, faces, vertex_count)
        if chain is not None:
            results.append((faces, chain))
    if not results:
        raise MalformedModel('LOD %d: polygon chain not found' % index)
    # A real polygon block wins over the empty-block reading that runs of zero
    # bytes inside the tail also satisfy. Without any faces the empty block that
    # starts first is the real one: false readings only start inside its tail.
    solid = [r for r in results if r[0]]
    if solid:
        results = solid
        first = results[0]
        if any(r[0] != first[0] or r[1][1:3] != first[1][1:3] for r in results):
            raise MalformedModel('LOD %d: polygon chain ambiguous' % index)
    faces, (sections, selections, props, rest) = results[0]
    lod.faces, lod.sections, lod.named_selections, lod.properties = faces, sections, selections, props
    lod.vertices, lod.normals, cur = _rest_arrays(data, rest, end, vertex_count)
    _apply_refs(model, selections, local_to_bone, _selection_refs(cur, vertex_count))
    return lod


def read_odol(data, strict=True):
    """Parse a whole model. With strict=False, LODs that fail are recorded in
    failed_lods (index -> error) and omitted instead of failing the model."""
    data = bytes(data)
    model = read_header(data)
    for index in range(len(model.resolutions)):
        try:
            model.lods.append(read_lod(data, model, index))
        except OdolError as exc:
            if strict:
                raise
            model.failed_lods[index] = exc
    return model
