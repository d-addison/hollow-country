"""Lead-run lantern stages. Author starts Blender; never run it in a worker.

Each output stays under build/. Native conversion/binarisation is deliberately
separate. Current codec limitations fail closed at finish/materials, not waived.
"""
import argparse
import json
from pathlib import Path

from tools.assets import blender_runner, finisher, mlod, pbr_pack
from tools.assets.provenance import load_json

SOURCE = Path(__file__).resolve().parent
RECIPES = ('lod0', 'lod1', 'lod2', 'geometry', 'view', 'fire', 'shadow')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def author(output):
    output = blender_runner.build_directory(output)
    for stem in RECIPES:
        recipe = load_json((SOURCE/(stem+'.ops.json')).read_bytes())
        result = blender_runner.build(recipe, render=False)
        write_json(output/(stem+'.neutral.json'), result.mesh)
        # The current runner only returns neutral.v1. Recover the same object face
        # ranges from authored object selections before its temporary sidecar dies.
        shading = {op['target']: {'smooth': op['enabled'], 'sharp_angle': op['sharp_angle'],
                   'faces': result.mesh['selections'][op['target']]['faces']}
                   for op in recipe['ops'] if op['op'] == 'smooth-shading'}
        write_json(output/(stem+'.shading.json'), {'schema':'shading.v1','objects':shading})


def finish(output):
    output = blender_runner.build_directory(output)
    # Refuse before silently emitting another prefix while the codec worker lands.
    try:
        mlod.virtual_path('HollowCountryAssets\\lantern\\tin_co.paa')
    except ValueError:
        raise ValueError('lantern.codec_assets_prefix_required') from None
    settings = load_json((SOURCE/'finish.json').read_bytes())
    bindings = load_json((SOURCE/'materials.json').read_bytes())
    meshes = {}
    for level in range(3):
        mesh = load_json((output/f'lod{level}.neutral.json').read_bytes())
        for selection, material in bindings.items():
            for index in mesh['selections'][selection]['faces']:
                mesh['faces'][index]['texture'] = 'HollowCountryAssets\\lantern\\'+material+'_co.paa'
                mesh['faces'][index]['material'] = 'HollowCountryAssets\\lantern\\'+material+'.rvmat'
        can, rim = mesh['selections']['can'], mesh['selections']['rim']
        for key in ['vertices','faces']:
            can[key] = sorted(set(can[key]+rim[key]))
        meshes[level] = mesh
    asset = finisher.finish(meshes, budgets={int(k):v for k,v in settings['visual_budgets'].items()},
                            geometry_primitives=settings['geometry_primitives'], mass=settings['mass_kg'],
                            min_thickness=settings['minimum_thickness_m'],
                            merge_distance=settings['merge_distance_m'], lod_distance=settings['hausdorff_upper_m'])
    # Existing clean()/box_hulls() API: explicit special LODs, no inferred engine API.
    for stem, resolution in [('view',mlod.VIEW_GEOMETRY),('fire',mlod.FIRE_GEOMETRY),('shadow',mlod.SHADOW)]:
        mesh = load_json((output/(stem+'.neutral.json')).read_bytes())
        asset.lods[resolution] = finisher.clean(mesh, min_thickness=settings['minimum_thickness_m'])
    mlod.validate(asset)
    (output/'hc_tincanlantern.p3d').write_bytes(mlod.write_mlod(asset))
    (output/'hc_tincanlantern.model.cfg').write_bytes((SOURCE.parents[1]/'mods/HollowCountryAssets/model.cfg').read_bytes())


def materials(output, candidates):
    output = blender_runner.build_directory(output)
    try:
        pbr_pack.rvmat('HollowCountryAssets\\lantern\\tin')
    except ValueError:
        raise ValueError('lantern.pbr_assets_prefix_required') from None
    for material in ['tin','wire','wax','flame']:
        maps = {key:key+'.tga' for key in pbr_pack.MAPS}
        pbr_pack.pack(candidates/material, maps, output, asset_name=material,
                      virtual_prefix='HollowCountryAssets\\lantern\\'+material)
    # Derive through pbr_pack's current rvmat API, with an explicit, checked edit.
    # Native Super/emission acceptance stays pending; never commit .rvmat bytes.
    off = pbr_pack.rvmat('HollowCountryAssets\\lantern\\flame')
    marker = 'emmisive[]={0,0,0,1};'
    if off.count(marker) != 1:
        raise ValueError('lantern.emissive_template_changed')
    (output/'flame_on.rvmat').write_text(off.replace(marker,'emmisive[]={1,0.65,0.28,1};'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['author','finish','materials'])
    parser.add_argument('--output', type=Path, default=Path('build/lantern/mesh'))
    parser.add_argument('--candidates', type=Path, default=Path('build/lantern/textures'))
    args = parser.parse_args()
    try:
        if args.stage == 'author': author(args.output)
        elif args.stage == 'finish': finish(args.output)
        else: materials(args.output,args.candidates)
    except (ValueError, blender_runner.BlenderRefusal) as exc:
        print(json.dumps({'valid': False, 'reason': str(exc)[:160]}))
        return 1
    except OSError:
        print('{"valid": false, "reason": "lantern.io_refused"}')
        return 1
    print('{"valid": true, "engine_verified": false}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
