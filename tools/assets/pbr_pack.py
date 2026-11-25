"""Stdlib PBR -> DayZ TGA staging + rvmat, gated by sealed provenance.v2.

Inputs: 8-bit noninterlaced PNG or uncompressed truecolor/grayscale TGA
for base_color, normal, roughness, metallic, ao. All sizes must match; scalar maps
must be grayscale. Output is TGA for later ImageToPAA conversion, never PAA.

_co preserves source sRGB/alpha; other maps are linear byte data. _nohq preserves
normal RGB, INCLUDING GREEN: convention UNVERIFIED until lead P0-6. No implicit
flip is presented as correct. _smdi=(255, specular, 255-roughness), where specular
is a documented approximation: lerp(0.04, max(base_color_linear), metallic).
_as=(AO,AO,AO). No metallic workflow equivalence or DayZ shader proof is claimed.

Channel references (design only; no sample data/code):
https://community.bistudio.com/wiki/HQ_Normal_Maps
https://community.bistudio.com/wiki/Arma:_Texture_Naming_Rules
"""
from dataclasses import dataclass
import json
from pathlib import Path
import struct
import zlib

from tools.assets import licence_gate
from tools.assets.blender_runner import build_directory
from tools.assets.mlod import OWN_PREFIXES, virtual_path
from tools.assets.ops_runner import name
from tools.assets.provenance import digest, load_json, read_regular, verify_candidate

MAX_PIXELS = 4 * 1024 * 1024
MAPS = {'base_color', 'normal', 'roughness', 'metallic', 'ao'}


@dataclass(frozen=True)
class Image:
    width: int
    height: int
    rgba: bytes

    def __post_init__(self):
        if (type(self.width) is not int or type(self.height) is not int
                or not 1 <= self.width <= 4096 or not 1 <= self.height <= 4096
                or self.width*self.height > MAX_PIXELS or not isinstance(self.rgba, bytes)
                or len(self.rgba) != self.width*self.height*4):
            raise ValueError('image.size_or_pixels')


def decode_tga(data):
    if len(data) < 18:
        raise ValueError('image.truncated')
    ident, cmap, kind, cfirst, clen, cdepth, x, y, width, height, depth, desc = struct.unpack(
        '<BBBHHBHHHHBB', data[:18])
    if (cmap or cfirst or clen or cdepth or kind not in (2, 3)
            or (kind == 2 and depth not in (24, 32)) or (kind == 3 and depth != 8)
            or desc & 0xC0 or (desc & 15) not in ((0, 8) if depth == 32 else (0,))
            or not 1 <= width <= 4096 or not 1 <= height <= 4096
            or width*height > MAX_PIXELS):
        raise ValueError('image.unsupported_tga')
    stride, start = depth // 8, 18 + ident
    end = start + width*height*stride
    if end > len(data):
        raise ValueError('image.truncated')
    # Permit the standard empty TGA 2 footer only; no extension/developer metadata.
    tail = data[end:]
    if tail and tail != bytes(8) + b'TRUEVISION-XFILE.\x00':
        raise ValueError('image.unsupported_tga_metadata')
    pixels = bytearray(width*height*4)
    for row in range(height):
        for column in range(width):
            offset = start + (row*width + column)*stride
            sample = data[offset:offset+stride]
            rgba = (sample[0],)*3 + (255,) if kind == 3 else (
                sample[2], sample[1], sample[0], sample[3] if depth == 32 else 255)
            dest_y = row if desc & 32 else height - row - 1
            dest_x = width - column - 1 if desc & 16 else column
            dest = (dest_y*width + dest_x)*4
            pixels[dest:dest+4] = bytes(rgba)
    return Image(width, height, bytes(pixels))


def decode_png(data):
    """Strict bounded 8-bit PNG subset; reject APNG, palettes and interlacing."""
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) > 32*1024*1024:
        raise ValueError('image.unsupported_png')
    offset, header, compressed, ended, seen_data = 8, None, bytearray(), False, False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError('image.truncated_png')
        length = struct.unpack('>I', data[offset:offset+4])[0]
        tag = data[offset+4:offset+8]
        end = offset + length + 12
        if end > len(data):
            raise ValueError('image.truncated_png')
        payload = data[offset+8:end-4]
        crc = struct.unpack('>I', data[end-4:end])[0]
        if zlib.crc32(tag + payload) & 0xffffffff != crc:
            raise ValueError('image.png_crc')
        if header is None and tag != b'IHDR':
            raise ValueError('image.png_header')
        if tag == b'IHDR':
            if header is not None or length != 13:
                raise ValueError('image.png_header')
            width, height, depth, colour, compression, filtering, interlace = struct.unpack('>IIBBBBB', payload)
            if (not 1 <= width <= 4096 or not 1 <= height <= 4096 or width*height > MAX_PIXELS
                    or depth != 8 or colour not in (0, 2, 4, 6) or compression or filtering or interlace):
                raise ValueError('image.unsupported_png')
            header = (width, height, colour)
        elif tag == b'IDAT':
            if ended:
                raise ValueError('image.png_nonconsecutive_data')
            seen_data = True
            compressed.extend(payload)
        elif tag == b'IEND':
            if length or not seen_data or end != len(data):
                raise ValueError('image.png_end')
            break
        else:
            if tag in (b'acTL', b'fcTL', b'fdAT', b'tRNS') or not tag[0] & 32:
                raise ValueError('image.unsupported_png_chunk')
            ended |= seen_data
        offset = end
    else:
        raise ValueError('image.png_end')
    width, height, colour = header
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[colour]
    stride = width * channels
    expected = height*(stride+1)
    decoder = zlib.decompressobj()
    try:
        raw = decoder.decompress(bytes(compressed), expected+1)
    except zlib.error:
        raise ValueError('image.png_compression') from None
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('image.png_raster_size')
    previous, pixels = bytearray(stride), bytearray()
    for row in range(height):
        start = row*(stride+1)
        kind, line = raw[start], bytearray(raw[start+1:start+1+stride])
        if kind > 4:
            raise ValueError('image.png_filter')
        for i in range(stride):
            left = line[i-channels] if i >= channels else 0
            above = previous[i]
            diagonal = previous[i-channels] if i >= channels else 0
            if kind == 0:
                predictor = 0
            elif kind == 1:
                predictor = left
            elif kind == 2:
                predictor = above
            elif kind == 3:
                predictor = (left+above)//2
            else:
                estimate = left + above - diagonal
                choices = (left, above, diagonal)
                predictor = min(choices, key=lambda value: abs(estimate-value))
            line[i] = (line[i] + predictor) & 255
        for i in range(0, stride, channels):
            sample = line[i:i+channels]
            if colour in (0, 4):
                pixels.extend((sample[0],)*3 + (sample[1] if colour == 4 else 255,))
            else:
                pixels.extend(tuple(sample[:3]) + (sample[3] if colour == 6 else 255,))
        previous = line
    return Image(width, height, bytes(pixels))


def decode_image(data):
    return decode_png(data) if data.startswith(b'\x89PNG') else decode_tga(data)


def encode_tga(image):
    header = struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0,
                         image.width, image.height, 32, 40)
    pixels = bytearray(len(image.rgba))
    for i in range(0, len(pixels), 4):
        r, g, b, a = image.rgba[i:i+4]
        pixels[i:i+4] = bytes((b, g, r, a))
    return header + pixels


def pack_pixels(maps):
    """Pure byte transform, not an admission API; pack() gates all file writes."""
    if set(maps) != MAPS or any(not isinstance(v, Image) for v in maps.values()):
        raise ValueError('pack.maps')
    base = maps['base_color']
    if any((v.width, v.height) != (base.width, base.height) for v in maps.values()):
        raise ValueError('pack.dimensions')
    smdi, ambient = bytearray(), bytearray()
    for i in range(0, len(base.rgba), 4):
        scalar = {}
        for key in ('roughness', 'metallic', 'ao'):
            r, g, b, alpha = maps[key].rgba[i:i+4]
            if r != g or g != b or alpha != 255:
                raise ValueError('pack.scalar_map_required')
            scalar[key] = r
        # Source colour remains sRGB in _co; only the scalar specular estimate
        # linearizes it. This is an approximation requiring material review.
        colour = max(base.rgba[i:i+3]) / 255
        linear = colour/12.92 if colour <= 0.04045 else ((colour+0.055)/1.055)**2.4
        metallic = scalar['metallic']/255
        specular = round(255 * (0.04*(1-metallic) + linear*metallic))
        smdi.extend((255, specular, 255-scalar['roughness'], 255))
        ambient.extend((scalar['ao'],)*3 + (255,))
    return {'co': base, 'nohq': maps['normal'],
            'smdi': Image(base.width, base.height, bytes(smdi)),
            'as': Image(base.width, base.height, bytes(ambient))}


def rvmat(prefix):
    """Conservative Super shader staging; native material acceptance is pending.

    _co binds on mlod.Face.texture, not an rvmat stage. PAA paths describe the
    later converter output; this packer never claims those files already exist.
    """
    virtual_path(prefix + '_co.paa')
    if prefix.split('\\')[0].casefold() not in {p.casefold() for p in OWN_PREFIXES}:
        raise ValueError('pack.owned_prefix_required')
    text = ('// UNVERIFIED normal green convention and shader: lead P0-6 required\n'
            'ambient[]={1,1,1,1};\ndiffuse[]={1,1,1,1};\n'
            'forcedDiffuse[]={0,0,0,0};\nemmisive[]={0,0,0,1};\n'
            'specular[]={1,1,1,1};\nspecularPower=100;\n'
            'PixelShaderID="Super";\nVertexShaderID="Super";\n')
    textures = [prefix + '_nohq.paa', '#(argb,8,8,3)color(0,0,0,0,DT)',
                '#(argb,8,8,3)color(0,0,0,0,MC)', prefix + '_as.paa',
                prefix + '_smdi.paa', '#(ai,64,64,1)fresnel(1.3,7)',
                '#(argb,8,8,3)color(0,0,0,0,CO)']
    for index, texture in enumerate(textures, 1):
        text += (f'class Stage{index}\n{{\n    texture="{texture}";\n'
                 '    uvSource="tex";\n};\n')
    return text


def rvmat_on(prefix, *, emissive=(1, 1, 1, 1)):
    """On/off material swap pattern: DZ gear/tools/data/flashlight_glass_on.rvmat.

    The vanilla path is cited by 4_World/Entities/ItemBase/Flashlight.c:8-11
    in the installed scripts-1.30.164289 snapshot. Its rvmat contents have not
    been inspected here. Super + emmisive[] (BI spelling) and this intensity
    are unverified until the lead's native load; no light entity is created.
    """
    from tools.assets.ops_runner import number
    if not isinstance(emissive, (list, tuple)) or len(emissive) != 4:
        raise ValueError('pack.emissive_rgba')
    values = tuple(number(v, 0, 100) for v in emissive)
    colour = ','.join(format(v, '.9g') for v in values)
    return ('// Emissive shader parameters unverified until the lead native load; '
            'vanilla swap pattern: dz/gear/tools/data/flashlight_glass_on.rvmat\n'
            + rvmat(prefix).replace('emmisive[]={0,0,0,1};',
                                    'emmisive[]={' + colour + '};'))


def pack(candidate, sources, output, *, asset_name, virtual_prefix, emissive=None):
    """Immutable sealed candidate required; only pinned input components are maps.

    Re-audits real bytes, not a supplied verdict dict. Callers must keep candidate
    immutable throughout; this function cannot provide OS-level isolation.
    """
    candidate = Path(candidate).resolve()
    if not licence_gate.audit(candidate / 'provenance.json')['shippable']:
        raise ValueError('pack.licence_not_shippable')
    manifest = verify_candidate(candidate)
    document = load_json(read_regular(candidate, 'provenance.json'))
    pinned_inputs = {entry['path']: entry['sha256'] for entry in document['inputs']}
    if not isinstance(sources, dict) or set(sources) != MAPS:
        raise ValueError('pack.maps')
    maps = {}
    for key, relative in sources.items():
        if not isinstance(relative, str) or relative not in pinned_inputs:
            raise ValueError('pack.source_not_pinned_input')
        raw = read_regular(candidate, relative)
        if digest(raw) != pinned_inputs[relative] or digest(raw) != manifest.get(relative):
            raise ValueError('pack.source_changed')
        maps[key] = decode_image(raw)
    name(asset_name)
    material = rvmat(virtual_prefix)
    if virtual_prefix.rsplit('\\', 1)[-1] != asset_name:
        raise ValueError('pack.virtual_basename_mismatch')
    packed = pack_pixels(maps)
    target = Path(output).resolve()
    if target == candidate or candidate in target.parents or target in candidate.parents:
        raise ValueError('pack.output_overlaps_candidate')
    target = build_directory(target)
    payloads = {asset_name + '_' + suffix + '.tga': encode_tga(image)
                for suffix, image in packed.items()}
    payloads[asset_name + '.rvmat'] = material.encode('ascii')
    if emissive is not None:
        payloads[asset_name + '_on.rvmat'] = rvmat_on(virtual_prefix, emissive=emissive).encode('ascii')
    report = {'schema': 'pbr-pack.v1', 'licence_gate': document['licence_gate'],
              'normal_green': 'unverified_preserved_P0_6',
              'material_conversion': 'approximation_unverified',
              'texture': virtual_prefix + '_co.paa',
              'files': {key: digest(value) for key, value in sorted(payloads.items())}}
    payloads[asset_name + '.pack.json'] = json.dumps(report, sort_keys=True, indent=2).encode('utf-8')
    # Refuse links and existing outputs, avoiding accidental destructive writes.
    if any((target / filename).exists() or (target / filename).is_symlink() for filename in payloads):
        raise ValueError('pack.output_exists')
    for filename, data in payloads.items():
        with (target / filename).open('xb') as stream:
            stream.write(data)
    return report


def selftest():
    image = Image(1, 1, bytes((128, 128, 128, 255)))
    assert decode_tga(encode_tga(image)) == image
    packed = pack_pixels(dict.fromkeys(MAPS, image))
    assert packed['smdi'].rgba[0] == 255
    assert 'UNVERIFIED' in rvmat('HollowCountry\\test\\cube')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true', required=True)
    parser.parse_args()
    selftest()
    print('{"valid": true}')
