"""Read-only reader for rapified config.bin inside an installed addon PBO.

Test support only. It reads locally installed vanilla addons from the machine's
own server install cache so tests can cite native config values. It copies no
data into the repository and is never used at runtime.
"""
import struct


def pbo_files(blob):
    pos = 0
    entries = []

    def cstr():
        nonlocal pos
        end = blob.index(b'\0', pos)
        text = blob[pos:end].decode('latin1')
        pos = end + 1
        return text

    while True:
        name = cstr()
        method, _original, _reserved, _stamp, size = struct.unpack_from('<5I', blob, pos)
        pos += 20
        if name == '' and method == 0x56657273:  # 'Vers' property header
            while cstr():
                cstr()
            continue
        if name == '':
            break
        entries.append((name, size))
    files = {}
    for name, size in entries:
        files[name] = blob[pos:pos + size]
        pos += size
    return files


class _Rap:
    def __init__(self, data):
        self.b = data

    def cint(self, p):
        value = shift = 0
        while True:
            c = self.b[p]
            p += 1
            value |= (c & 0x7F) << shift
            shift += 7
            if not c & 0x80:
                return value, p

    def cstr(self, p):
        end = self.b.index(b'\0', p)
        return self.b[p:end].decode('latin1'), end + 1

    def array(self, p):
        count, p = self.cint(p)
        out = []
        for _ in range(count):
            kind = self.b[p]
            p += 1
            if kind == 0:
                value, p = self.cstr(p)
            elif kind == 1:
                value, p = struct.unpack_from('<f', self.b, p)[0], p + 4
            elif kind == 2:
                value, p = struct.unpack_from('<i', self.b, p)[0], p + 4
            elif kind == 3:
                value, p = self.array(p)
            else:
                raise ValueError('unsupported array element type')
            out.append(value)
        return out, p

    def body(self, p):
        parent, p = self.cstr(p)
        count, p = self.cint(p)
        node = {'__parent__': parent}
        for _ in range(count):
            kind = self.b[p]
            p += 1
            if kind == 0:
                name, p = self.cstr(p)
                offset = struct.unpack_from('<I', self.b, p)[0]
                p += 4
                node[name] = self.body(offset)
            elif kind == 1:
                sub = self.b[p]
                name, p = self.cstr(p + 1)
                if sub == 0:
                    node[name], p = self.cstr(p)
                elif sub == 1:
                    node[name], p = struct.unpack_from('<f', self.b, p)[0], p + 4
                else:
                    node[name], p = struct.unpack_from('<i', self.b, p)[0], p + 4
            elif kind == 2:
                name, p = self.cstr(p)
                node[name + '[]'], p = self.array(p)
            elif kind in (3, 4):
                name, p = self.cstr(p)
                node[name] = {'__extern__' if kind == 3 else '__delete__': True}
            elif kind == 5:
                name, p = self.cstr(p + 4)
                node[name + '[]+'], p = self.array(p)
            else:
                raise ValueError('unsupported config entry type')
        return node


def load_config(pbo_bytes):
    """Return the rapified config.bin of a PBO as nested dicts."""
    data = pbo_files(pbo_bytes)['config.bin']
    if data[:4] != b'\0raP':
        raise ValueError('config.bin is not rapified')
    return _Rap(data).body(16)
