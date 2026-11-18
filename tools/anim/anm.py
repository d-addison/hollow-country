"""Enfusion/DayZ .anm (FORM ANIM SET6) reader and writer. Standard library only. Our own code.

Layout (reverse engineered; cross-checked against the arma-file-formats-rs documentation of
SET6/SET7 and round-tripped byte for byte on installed DayZ 1.30 clips by tests/unit/test_anim_anm.py
when the game is installed):

    FORM <u32 BE size> ANIM SET6 <u32 BE size>
      FPS\\0 <u32 BE 4> <u32 LE fps>
      HEAD <u32 BE size>   per bone:
          f32 t_min, f32 t_range, f32 q_min, f32 q_range, f32 s_min, f32 s_range,
          u16 frames, u16 t_keys, u16 q_keys, u16 s_keys, u8 flags, u8 name_len, name bytes
      DATA <u32 BE size>   per bone, tracks in order t, s, q:
          keys x u16 frame numbers, then keys x components x u16
          (DayZ 1.30 clips use flags 0 and always store frame numbers; the SET7-style
          "key on every frame" flag bits 0x10 t / 0x20 q / 0x40 s are honoured when reading)
      (optional chunks such as EVN1/EVN2/CPRP are kept verbatim)

    value = min + u16 * range / 65535   (one min/range per track, shared by its components)
    Transforms are parent-local, engine axes (Y up, metres), quaternions x y z w.

No game data is embedded here; tests read installed clips only when present.
"""
import struct

QMAX = 65535


class Track:
    def __init__(self, comps, frames=None, values=None):
        self.comps = comps
        self.frames = frames or []     # frame index per key
        self.values = values or []     # list of tuples (comps floats)


class Bone:
    def __init__(self, name):
        self.name = name
        self.flags = 0
        self.t = Track(3)
        self.q = Track(4)
        self.s = Track(3)
        self.ranges = None   # (t_min, t_range, q_min, q_range, s_min, s_range) as read


class Anim:
    def __init__(self, fps=30, frames=1):
        self.fps = fps
        self.frames = frames
        self.bones = []
        self.extra = []      # (tag, bytes) chunks after DATA kept verbatim

    def bone(self, name):
        for b in self.bones:
            if b.name == name:
                return b
        return None


def _chunks(data, pos, end):
    while pos < end:
        tag = data[pos:pos + 4]
        size = struct.unpack_from('>I', data, pos + 4)[0]
        yield tag, data[pos + 8:pos + 8 + size]
        pos += 8 + size


def read(data):
    if data[:4] != b'FORM' or data[8:12] != b'ANIM' or data[12:16] != b'SET6':
        raise ValueError('not a SET6 ANIM: %r' % data[:16])
    set_size = struct.unpack_from('>I', data, 16)[0]
    anim = Anim()
    head = body = None
    for tag, chunk in _chunks(data, 20, 20 + set_size):
        if tag == b'FPS\0':
            anim.fps = struct.unpack('<I', chunk)[0]
        elif tag == b'HEAD':
            head = chunk
        elif tag == b'DATA':
            body = chunk
        else:
            anim.extra.append((tag, chunk))
    pos = 0
    frames_seen = 0
    while pos < len(head):
        ranges = struct.unpack_from('<6f', head, pos)
        frames, tk, qk, sk, flags, nlen = struct.unpack_from('<4HBB', head, pos + 24)
        name = head[pos + 34:pos + 34 + nlen].decode('latin-1')
        pos += 34 + nlen
        b = Bone(name)
        b.flags, b.ranges = flags, ranges
        b.t.frames, b.q.frames, b.s.frames = tk, qk, sk   # counts for now
        b._frames = frames
        frames_seen = max(frames_seen, frames)
        anim.bones.append(b)
    anim.frames = frames_seen
    pos = 0
    for b in anim.bones:
        rmin = b.ranges
        for track, mn, rg, bit in ((b.t, rmin[0], rmin[1], 0x10), (b.s, rmin[4], rmin[5], 0x40),
                                   (b.q, rmin[2], rmin[3], 0x20)):
            keys = track.frames
            if not (b.flags & bit):
                fr = list(struct.unpack_from('<%dH' % keys, body, pos))
                pos += 2 * keys
            else:
                fr = list(range(keys))
            n = keys * track.comps
            raw = struct.unpack_from('<%dH' % n, body, pos)
            pos += 2 * n
            track.frames = fr
            track.values = [tuple(mn + raw[k * track.comps + c] * rg / QMAX for c in range(track.comps))
                            for k in range(keys)]
            track.raw = raw
    if pos != len(body):
        raise ValueError('DATA size mismatch: used %d of %d' % (pos, len(body)))
    return anim


def _quant(values, mn, rg):
    if rg <= 0:
        return [0 for _ in values]
    return [max(0, min(QMAX, int((v - mn) * QMAX / rg + 0.5))) for v in values]


def _track_range(track, empty_range):
    flat = [c for v in track.values for c in v]
    if not flat:
        return empty_range
    mn, mx = min(flat), max(flat)
    return mn, mx - mn


def write(anim):
    """Encode an Anim. Tracks keep exactly the keys given (no key reduction).

    A bone read by read() and left unchanged (``raw`` still attached and ``ranges`` set) is
    re-encoded from its stored ranges and raw u16 values, so read() -> write() is byte exact.
    New tracks get min/range from their values; an empty scale track uses (1, 1) like DayZ clips.
    """
    head = bytearray()
    body = bytearray()
    frames = anim.frames
    for b in anim.bones:
        exact = b.ranges is not None and all(hasattr(t, 'raw') for t in (b.t, b.q, b.s))
        if exact:
            ranges = list(b.ranges)
        else:
            ranges = list(_track_range(b.t, (0.0, 0.0)) + _track_range(b.q, (0.0, 1.0))
                          + _track_range(b.s, (1.0, 1.0)))
        name = b.name.encode('latin-1')
        head += struct.pack('<6f', *ranges)
        head += struct.pack('<4HBB', frames, len(b.t.values), len(b.q.values), len(b.s.values),
                            b.flags, len(name)) + name
        for track, mn, rg, bit in ((b.t, ranges[0], ranges[1], 0x10), (b.s, ranges[4], ranges[5], 0x40),
                                   (b.q, ranges[2], ranges[3], 0x20)):   # data order t, s, q
            keys = len(track.values)
            if not (b.flags & bit):
                body += struct.pack('<%dH' % keys, *track.frames)
            raw = track.raw if exact else _quant([c for v in track.values for c in v], mn, rg)
            body += struct.pack('<%dH' % len(raw), *raw)
    chunks = (b'FPS\0' + struct.pack('>I', 4) + struct.pack('<I', anim.fps)
              + b'HEAD' + struct.pack('>I', len(head)) + bytes(head)
              + b'DATA' + struct.pack('>I', len(body)) + bytes(body))
    for tag, chunk in anim.extra:
        chunks += tag + struct.pack('>I', len(chunk)) + chunk
    inner = b'SET6' + struct.pack('>I', len(chunks)) + chunks
    return b'FORM' + struct.pack('>I', len(inner) + 4) + b'ANIM' + inner
