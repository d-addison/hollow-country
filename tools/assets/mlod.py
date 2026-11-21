"""Stdlib-only canonical Asset IR and deterministic MLOD/P3DM codec.

Public layout references (community documentation, not sample/source models):
https://community.bistudio.com/wiki/P3D_File_Format_-_MLOD
https://community.bistudio.com/wiki/P3D_Lod_Faces
https://community.bistudio.com/wiki/P3D_Named_Selections

All integers are little-endian uint32, coordinates/UV/mass/resolution float32.
IR coordinates are model-local metres: X right, Y up, Z forward. Faces preserve
caller order: use CCW as seen from outside, with right-hand cross-product outward
normals. CW faces are representable with explicit normals; no implicit winding,
axis or UV-V conversion occurs. Native handedness/culling remains unverified
until P0-6. Normals are per corner; absent normals request flat face normals.

LODs are keyed by resolution: Visual N in [0, 1000), Geometry 1e13, Memory 1e15,
View Geometry 6e15, Fire Geometry 7e15, Shadow 1e4. Special keys are canonicalised
back from float32 on read. Geometry masses are a separate per-vertex tuple,
encoded as #Mass#, never a string property. Other properties (autocenter, class,
etc.) are ASCII key/value strings. Named selections contain point/face indices,
with binary membership only (selected points have weight 1, encoded byte 1).
Fractional selection weights and animation/editor tags are unsupported.

UNVERIFIED: proxy triangle vertex order/orientation has no established native
proof here. Proxy IR records intent, but both Proxy entries and proxy: selection
names are refused by the codec until P0-6. Nonzero LOD flags (unknown semantics)
are refused. This is offline tooling, not DayZ/Binarize acceptance. The reader
is deliberately only for this writer's subset, not a general MLOD importer.

Determinism: LODs, selections and properties are sorted; vertex/face/corner order
is meaningful and retained. Name, physical intent and source precision are not
stored by MLOD; read_mlod takes physical intent from its caller. No dependencies
on the neighbouring licence gate or package initializer.
"""
from dataclasses import asdict, dataclass, field
import math
import re
import struct

GEOMETRY = 1e13
MEMORY = 1e15
VIEW_GEOMETRY = 6e15
FIRE_GEOMETRY = 7e15
SHADOW = 1e4
SPECIAL_RESOLUTIONS = (GEOMETRY, MEMORY, VIEW_GEOMETRY, FIRE_GEOMETRY, SHADOW)
MAX_POINTS = 65535
MAX_FACES = 65535
MAX_LODS = 64
MAX_TAGS = 4096
MAX_BYTES = 128 * 1024 * 1024
OWN_PREFIX = 'HollowCountry'
Vec3 = tuple[float, float, float]
UV = tuple[float, float]


@dataclass(frozen=True)
class Vertex:
    position: Vec3
    flags: int = 0


@dataclass(frozen=True)
class Face:
    vertices: tuple[int, ...]
    uv: tuple[UV, ...]
    texture: str = ''
    material: str = ''  # rvmat virtual path
    normals: tuple[Vec3, ...] = ()
    flags: int = 0


@dataclass(frozen=True)
class Selection:
    vertices: tuple[int, ...] = ()
    faces: tuple[int, ...] = ()


@dataclass(frozen=True)
class Proxy:
    model: str
    triangle: tuple[int, int, int]
    instance: int = 1


@dataclass(frozen=True)
class LOD:
    vertices: tuple[Vertex, ...] = ()
    faces: tuple[Face, ...] = ()
    selections: dict[str, Selection] = field(default_factory=dict)
    properties: dict[str, str] = field(default_factory=dict)
    masses: tuple[float, ...] = ()
    proxies: tuple[Proxy, ...] = ()


@dataclass(frozen=True)
class Asset:
    lods: dict[float, LOD]
    physical: bool = True


def _ascii(value, limit=1023, empty=True):
    if not isinstance(value, str) or (not empty and not value):
        raise ValueError('expected ASCII string')
    try:
        raw = value.encode('ascii')
    except UnicodeEncodeError:
        raise ValueError('non-ASCII string') from None
    if len(raw) > limit or any(b < 32 or b > 126 for b in raw):
        raise ValueError('string exceeds limit or contains control characters')
    return raw


def virtual_path(value):
    """Admit empty/untextured or DZ/owned virtual paths; never OS paths.

    Backslashes are required; traversal, roots, drive letters, alternate streams,
    repeated separators and procedural texture expressions are refused.
    """
    _ascii(value)
    if not value:
        return value
    parts = value.split('\\')
    if (len(parts) < 2 or parts[0].casefold() not in {'dz', OWN_PREFIX.casefold()}
            or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', part)
                   or part in {'.', '..'} for part in parts)):
        raise ValueError('expected DZ or HollowCountry virtual path')
    return value


def _f32(value):
    try:
        result = struct.unpack('<f', struct.pack('<f', value))[0]
    except (OverflowError, struct.error, TypeError):
        raise ValueError('expected finite float32') from None
    if not math.isfinite(result):
        raise ValueError('expected finite float32')
    return result


def _resolution(value):
    value = _f32(value)
    for special in SPECIAL_RESOLUTIONS:
        if value == _f32(special):
            return special
    if 0 <= value < 1000:
        return value
    raise ValueError('unsupported LOD resolution')


def _uint(value):
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError('expected uint32')


def _vector(value, size):
    if len(value) != size:
        raise ValueError('invalid vector dimension')
    return tuple(_f32(v) for v in value)


def _indices(values, count):
    if any(type(i) is not int or not 0 <= i < count for i in values):
        raise ValueError('index outside LOD table')
    if len(set(values)) != len(values):
        raise ValueError('duplicate index')


def _normals(face, lod):
    if face.normals:
        if len(face.normals) != len(face.vertices):
            raise ValueError('one normal required per face corner')
        normals = tuple(_vector(n, 3) for n in face.normals)
        if any(sum(v*v for v in n) == 0 for n in normals):
            raise ValueError('zero normal')
        return normals
    a, b, c = (lod.vertices[i].position for i in face.vertices[:3])
    u = tuple(b[i] - a[i] for i in range(3))
    v = tuple(c[i] - a[i] for i in range(3))
    cross = (u[1]*v[2] - u[2]*v[1], u[2]*v[0] - u[0]*v[2],
             u[0]*v[1] - u[1]*v[0])
    length = math.hypot(*cross)
    if not math.isfinite(length) or length == 0:
        raise ValueError('degenerate face needs valid geometry')
    return (tuple(x / length for x in cross),) * len(face.vertices)


def validate(asset):
    """Validate the supported subset before producing bytes; no filesystem IO."""
    if not 1 <= len(asset.lods) <= MAX_LODS:
        raise ValueError('LOD count outside bound')
    keys = [_resolution(r) for r in asset.lods]
    if len(set(keys)) != len(keys):
        raise ValueError('LOD resolutions collide in float32')
    geometry = next((lod for r, lod in asset.lods.items()
                     if _resolution(r) == GEOMETRY), None)
    if asset.physical and (geometry is None or not geometry.vertices or not geometry.faces):
        raise ValueError('physical object requires nonempty Geometry LOD')
    for resolution, lod in asset.lods.items():
        if len(lod.vertices) > MAX_POINTS or len(lod.faces) > MAX_FACES:
            raise ValueError('LOD exceeds point/face bound (65535)')
        if lod.proxies:
            raise ValueError('proxy triangle order unverified until P0-6')
        if len(lod.selections) + len(lod.properties) + 3 > MAX_TAGS:
            raise ValueError('too many tags')
        for vertex in lod.vertices:
            _vector(vertex.position, 3)
            _uint(vertex.flags)
        for face in lod.faces:
            if len(face.vertices) not in (3, 4) or len(face.uv) != len(face.vertices):
                raise ValueError('faces require three/four vertices and matching UVs')
            _indices(face.vertices, len(lod.vertices))
            for uv in face.uv:
                _vector(uv, 2)
            virtual_path(face.texture)
            virtual_path(face.material)
            _uint(face.flags)
            _normals(face, lod)
        for name, selection in lod.selections.items():
            _ascii(name, empty=False)
            if '#' in name or name.casefold().startswith('proxy:'):
                raise ValueError('reserved or unverified selection name')
            _indices(selection.vertices, len(lod.vertices))
            _indices(selection.faces, len(lod.faces))
        for name, value in lod.properties.items():
            _ascii(name, 63, empty=False)
            _ascii(value, 63)
            if '#' in name:
                raise ValueError('special tags must not be string properties')
        if _resolution(resolution) == GEOMETRY:
            if len(lod.masses) != len(lod.vertices):
                raise ValueError('Geometry requires per-vertex #Mass#')
            masses = [_f32(m) for m in lod.masses]
            if any(m < 0 for m in masses) or (masses and sum(masses) <= 0):
                raise ValueError('Geometry mass must be nonnegative with positive total')
        elif lod.masses:
            raise ValueError('#Mass# is Geometry-only')


def _tag(name, payload):
    return b'\x01' + _ascii(name) + b'\0' + struct.pack('<I', len(payload)) + payload


def write_mlod(asset):
    """Return deterministic MLOD version 257 bytes. Never writes a game asset."""
    validate(asset)
    out = bytearray(struct.pack('<4sII', b'MLOD', 257, len(asset.lods)))
    for resolution, lod in sorted(asset.lods.items()):
        normals = [n for face in lod.faces for n in _normals(face, lod)]
        out.extend(struct.pack('<4s6I', b'P3DM', 28, 256, len(lod.vertices),
                               len(normals), len(lod.faces), 0))
        for vertex in lod.vertices:
            out.extend(struct.pack('<3fI', *vertex.position, vertex.flags))
        for normal in normals:
            out.extend(struct.pack('<3f', *normal))
        normal_index = 0
        uv_data = bytearray(struct.pack('<I', 0))
        for face in lod.faces:
            out.extend(struct.pack('<I', len(face.vertices)))
            for index, uv in zip(face.vertices, face.uv):
                out.extend(struct.pack('<II2f', index, normal_index, *uv))
                uv_data.extend(struct.pack('<2f', *uv))
                normal_index += 1
            if len(face.vertices) == 3:
                out.extend(bytes(16))
            out.extend(struct.pack('<I', face.flags))
            out.extend(_ascii(face.texture) + b'\0' + _ascii(face.material) + b'\0')
        out.extend(b'TAGG')
        out.extend(_tag('#UVSet#', uv_data))
        for name, selection in sorted(lod.selections.items()):
            payload = bytearray(len(lod.vertices) + len(lod.faces))
            for index in selection.vertices:
                payload[index] = 1
            for index in selection.faces:
                payload[len(lod.vertices) + index] = 1
            out.extend(_tag(name, payload))
        for name, value in sorted(lod.properties.items()):
            out.extend(_tag('#Property#', _ascii(name).ljust(64, b'\0')
                            + _ascii(value).ljust(64, b'\0')))
        if _resolution(resolution) == GEOMETRY:
            out.extend(_tag('#Mass#', struct.pack('<' + 'f'*len(lod.masses), *lod.masses)))
        out.extend(_tag('#EndOfFile#', b''))
        out.extend(struct.pack('<f', resolution))
        if len(out) > MAX_BYTES:
            raise ValueError('MLOD byte bound exceeded')
    return bytes(out)


class _Reader:
    def __init__(self, data):
        self.data = data
        self.offset = 0

    def take(self, size):
        if size < 0 or self.offset + size > len(self.data):
            raise ValueError('truncated MLOD')
        result = self.data[self.offset:self.offset + size]
        self.offset += size
        return result

    def unpack(self, fmt):
        return struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))

    def string(self):
        end = self.data.find(b'\0', self.offset, self.offset + 1024)
        if end < 0:
            raise ValueError('unterminated MLOD string')
        raw = self.take(end - self.offset + 1)[:-1]
        try:
            value = raw.decode('ascii')
        except UnicodeDecodeError:
            raise ValueError('non-ASCII MLOD string') from None
        _ascii(value)
        return value


def _property_string(raw):
    head, separator, tail = raw.partition(b'\0')
    if not separator or any(tail):
        raise ValueError('invalid fixed property string')
    try:
        return head.decode('ascii')
    except UnicodeDecodeError:
        raise ValueError('non-ASCII property') from None


def read_mlod(data, *, physical=True):
    """Read our output subset, refusing malformed/unknown records and trailing data.

    physical is caller metadata; it cannot be inferred from the file header.
    No external models, compressed ODOLs or editor tags are imported.
    """
    if len(data) > MAX_BYTES:
        raise ValueError('MLOD byte bound exceeded')
    reader = _Reader(data)
    signature, version, count = reader.unpack('4sII')
    if signature != b'MLOD' or version != 257 or not 1 <= count <= MAX_LODS:
        raise ValueError('unsupported MLOD header')
    lods = {}
    for _ in range(count):
        signature, major, minor, np, nn, nf, flags = reader.unpack('4s6I')
        if ((signature, major, minor, flags) != (b'P3DM', 28, 256, 0)
                or np > MAX_POINTS or nf > MAX_FACES or nn > MAX_FACES*4):
            raise ValueError('unsupported P3DM header/counts/flags')
        vertices = []
        for _ in range(np):
            x, y, z, flags = reader.unpack('3fI')
            vertices.append(Vertex((x, y, z), flags))
        normals = [reader.unpack('3f') for _ in range(nn)]
        faces = []
        expected_uv = bytearray(struct.pack('<I', 0))
        for _ in range(nf):
            corners, = reader.unpack('I')
            if corners not in (3, 4):
                raise ValueError('invalid face size')
            indices, face_normals, uv = [], [], []
            for _ in range(corners):
                pi, ni, u, v = reader.unpack('II2f')
                if pi >= np or ni >= nn:
                    raise ValueError('face index outside table')
                indices.append(pi)
                face_normals.append(normals[ni])
                uv.append((u, v))
                expected_uv.extend(struct.pack('<2f', u, v))
            if corners == 3 and reader.take(16) != bytes(16):
                raise ValueError('nonzero triangle padding')
            flags, = reader.unpack('I')
            texture, material = reader.string(), reader.string()
            faces.append(Face(tuple(indices), tuple(uv), texture, material,
                              tuple(face_normals), flags))
        if reader.take(4) != b'TAGG':
            raise ValueError('missing TAGG marker')
        selections, properties, masses = {}, {}, ()
        seen_uv = seen_mass = False
        for _ in range(MAX_TAGS):
            if reader.take(1) != b'\x01':
                raise ValueError('unsupported inactive tag')
            name = reader.string()
            size, = reader.unpack('I')
            payload = reader.take(size)
            if name == '#EndOfFile#':
                if size:
                    raise ValueError('nonempty end tag')
                break
            if name == '#UVSet#':
                if seen_uv or payload != expected_uv:
                    raise ValueError('unsupported or mismatching UV set')
                seen_uv = True
            elif name == '#Mass#':
                if seen_mass or size != np*4:
                    raise ValueError('invalid mass tag')
                masses = struct.unpack('<' + 'f'*np, payload)
                seen_mass = True
            elif name == '#Property#':
                if size != 128:
                    raise ValueError('invalid property size')
                key, value = _property_string(payload[:64]), _property_string(payload[64:])
                if key in properties:
                    raise ValueError('duplicate property')
                properties[key] = value
            elif '#' in name or name.casefold().startswith('proxy:'):
                raise ValueError('unsupported or unverified tag')
            else:
                if name in selections or size != np + nf or any(b not in (0, 1) for b in payload):
                    raise ValueError('invalid binary selection')
                selections[name] = Selection(tuple(i for i in range(np) if payload[i]),
                                             tuple(i for i in range(nf) if payload[np+i]))
        else:
            raise ValueError('missing end tag within bound')
        if not seen_uv:
            raise ValueError('missing UV set zero')
        resolution = _resolution(reader.unpack('f')[0])
        if seen_mass != (resolution == GEOMETRY):
            raise ValueError('mass tag must occur exactly in Geometry')
        if resolution in lods:
            raise ValueError('duplicate LOD resolution')
        lods[resolution] = LOD(tuple(vertices), tuple(faces), selections, properties, masses)
    if reader.offset != len(data):
        raise ValueError('trailing MLOD bytes')
    asset = Asset(lods, physical)
    validate(asset)
    return asset


def structure_dump(data, *, physical=True):
    """Return a JSON-compatible, float32-decoded structure for golden assertions."""
    asset = read_mlod(data, physical=physical)
    return {'signature': 'MLOD', 'version': 257, 'lods': [
        {'signature': 'P3DM', 'major': 28, 'minor': 256, 'resolution': resolution,
         **asdict(lod)} for resolution, lod in sorted(asset.lods.items())]}
