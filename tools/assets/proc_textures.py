"""Original seeded lantern PBR maps; stdlib only, no downloads or native tools.

Images and lantern recipes are original Hollow Country work dedicated to CC0-1.0
by assets_src/lantern/LICENSE.txt. Outputs are confined to ignored build/.
Each material is an immutable sealed provenance.v2 candidate for pbr_pack.pack.
Flame emission is staged through pbr_pack.rvmat by the lantern build helper;
this generator supplies the unchanged five-map packer input layout.
"""
import argparse
import json
import math
from pathlib import Path
import random

from tools.assets.blender_runner import BlenderRefusal, build_directory
from tools.assets.pbr_pack import Image, encode_tga
from tools.assets.provenance import build_provenance, digest

ROOT = Path(__file__).resolve().parents[2]
MATERIALS = ('tin', 'wire', 'wax', 'flame')
MAP_NAMES = ('base_color', 'normal', 'roughness', 'metallic', 'ao')


def generate(material, *, size=256, seed=349):
    """Return five matching RGBA Image maps; scalar channels are grayscale."""
    if material not in MATERIALS or type(size) is not int or not 4 <= size <= 1024:
        raise ValueError('texture.material_or_size')
    if type(seed) is not int or not 0 <= seed <= 2**32-1:
        raise ValueError('texture.seed')
    rng = random.Random(seed + MATERIALS.index(material))
    buffers = {key: bytearray() for key in MAP_NAMES}
    for y in range(size):
        for x in range(size):
            noise = rng.randrange(-12, 13)
            wave = math.sin(x*math.tau/size*7)*math.sin(y*math.tau/size*5)
            if material == 'tin':
                rust = wave + noise/25 > 0.18
                colour = (106+noise, 55+noise//2, 28+noise//3) if rust else (118+noise, 121+noise, 116+noise)
                rough, metal = (220, 20) if rust else (165, 210)
            elif material == 'wire':
                colour, rough, metal = (73+noise, 76+noise, 74+noise), 185, 220
            elif material == 'wax':
                colour, rough, metal = (222+noise//2, 207+noise//2, 167+noise//2), 210, 0
            else:
                # Opaque flame mesh carries a warm vertical colour gradient.
                heat = 1-y/(size-1)
                colour, rough, metal = (255, round(90+150*heat), round(12+105*heat)), 255, 0
            values = {'base_color': colour, 'normal': (128, 128, 255),
                      'roughness': (rough,)*3, 'metallic': (metal,)*3, 'ao': (255,)*3}
            for key, rgb in values.items():
                buffers[key].extend((*rgb, 255))
    return {key: Image(size, size, bytes(value)) for key, value in buffers.items()}


def write_candidates(output, *, size=256, seed=349):
    """No overwrite; provenance pins each generated map and its authored recipe."""
    # Validate before creating output directories.
    images = {material: generate(material, size=size, seed=seed) for material in MATERIALS}
    target = build_directory(Path(output))
    if any((target / material).exists() for material in MATERIALS):
        raise ValueError('texture.output_exists')
    licence = (ROOT / 'assets_src/lantern/LICENSE.txt').read_bytes()
    recipe = json.dumps({'schema': 'lantern-textures.v1', 'seed': seed, 'size': size}, sort_keys=True).encode()
    for material, maps in images.items():
        folder = target / material
        folder.mkdir()
        payloads = {key+'.tga': encode_tga(image) for key, image in maps.items()}
        payloads.update({'LICENSE.txt': licence, 'generator.py': Path(__file__).read_bytes(),
                         'recipe.json': recipe})
        for filename, data in payloads.items():
            (folder / filename).write_bytes(data)
        inputs = [{'name': material+' '+key, 'source': 'original:hollow-country/lantern/'+material,
                   'path': key+'.tga', 'sha256': digest(payloads[key+'.tga']),
                   'licence_id': 'CC0-1.0', 'licence_path': 'LICENSE.txt',
                   'licence_sha256': digest(licence),
                   'attribution': 'Original Hollow Country procedural texture; no external pixels.'}
                  for key in MAP_NAMES]
        document = build_provenance(asset='lantern_'+material, inputs=inputs, toolchain=[],
                                    origin='original:seeded-procedural', root=folder)
        if not document['shippable']:
            raise ValueError('texture.provenance_refused')
        payloads['provenance.json'] = json.dumps(document, sort_keys=True, indent=2).encode()
        (folder / 'provenance.json').write_bytes(payloads['provenance.json'])
        manifest = json.dumps({'files': {key: digest(data) for key, data in sorted(payloads.items())}}, sort_keys=True).encode()
        (folder / 'manifest.json').write_bytes(manifest)
        (folder / 'candidate.sha256').write_text(digest(manifest)+'\n')
    return {material: {key: key+'.tga' for key in MAP_NAMES} for material in MATERIALS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, default=256)
    parser.add_argument('--seed', type=int, default=349)
    args = parser.parse_args()
    try:
        result = write_candidates(args.output, size=args.size, seed=args.seed)
    except (OSError, ValueError, BlenderRefusal):
        print('{"valid": false, "reason": "texture.generation_refused"}')
        return 1
    print(json.dumps({'valid': True, 'maps': result}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
