"""Blender subprocess entry point, the sole bpy boundary.

All selections cover the target object at export time (including modifiers).
Memory points/proxies are model-space metadata, independent of object transforms.
--selftest is deliberately importable/runnable in ordinary Python without Blender.
"""
import argparse
import json
import math
from pathlib import Path
import sys

# The runner copies the tiny tools package beside this script into its temp dir.
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools.assets.ops_runner import validate, MAX_ELEMENTS
from tools.assets.provenance import load_json


def canonical(point):
    return [float(point[0]), float(point[2]), -float(point[1])]


def execute(recipe, output, render=False):
    import bpy
    from mathutils import Vector

    if bpy.app.version[:2] != (5, 2):
        raise ValueError('blender.version_requires_5_2')
    recipe = validate(recipe)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    objects, labels, points, proxies = {}, {}, {}, []

    def active(obj):
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    def apply(obj, modifier):
        active(obj)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        if len(obj.data.vertices) > MAX_ELEMENTS or len(obj.data.polygons) > MAX_ELEMENTS:
            raise ValueError('blender.mesh_limit')

    for op in recipe['ops']:
        kind = op['op']
        obj = objects.get(op.get('target'))
        if kind == 'primitive':
            segments = op.get('segments', 16)
            if op['kind'] == 'box':
                bpy.ops.mesh.primitive_cube_add(size=1)
            elif op['kind'] == 'cylinder':
                bpy.ops.mesh.primitive_cylinder_add(vertices=segments, radius=0.5, depth=1)
            else:
                bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=segments, radius=0.5)
            obj = bpy.context.object
            obj.name = op['id']
            obj.scale = op['size']
            active(obj)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            objects[op['id']], labels[op['id']] = obj, set()
        elif kind == 'transform':
            active(obj)
            obj.location = op['translate']
            obj.rotation_euler = [math.radians(v) for v in op['rotate']]
            obj.scale = op['scale']
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        elif kind == 'boolean':
            operand = objects.pop(op['operand'])
            mod = obj.modifiers.new('hc_boolean', 'BOOLEAN')
            mod.operation, mod.object, mod.solver = op['mode'], operand, 'EXACT'
            apply(obj, mod)
            labels[op['target']].update(labels.pop(op['operand']))
            bpy.data.objects.remove(operand, do_unlink=True)
        elif kind == 'bevel':
            mod = obj.modifiers.new('hc_bevel', 'BEVEL')
            mod.width, mod.segments = op['width'], op['segments']
            apply(obj, mod)
        elif kind == 'array':
            mod = obj.modifiers.new('hc_array', 'ARRAY')
            mod.count, mod.use_relative_offset, mod.use_constant_offset = op['count'], False, True
            mod.constant_offset_displace = op['offset']
            apply(obj, mod)
        elif kind == 'mirror':
            mod = obj.modifiers.new('hc_mirror', 'MIRROR')
            mod.use_axis = tuple(axis == op['axis'] for axis in 'XYZ')
            apply(obj, mod)
        elif kind == 'uv-unwrap':
            active(obj)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
            bpy.ops.object.mode_set(mode='OBJECT')
        elif kind == 'material-slot':
            material = bpy.data.materials.new('hc_material')
            material['hc_texture'], material['hc_material'] = op['texture'], op['material']
            obj.data.materials.append(material)
            for face in obj.data.polygons:
                face.material_index = len(obj.data.materials) - 1
        elif kind == 'named-selection':
            labels[op['target']].add(op['name'])
        elif kind == 'memory-point':
            points[op['name']] = canonical(op['position'])
        elif kind == 'proxy':
            proxies.append({**op, 'position': canonical(op['position'])})
    vertices, faces, selections = [], [], {}
    for ident, obj in sorted(objects.items()):
        # Triangulate ngons deterministically, retaining quad faces where possible.
        mod = obj.modifiers.new('hc_triangulate', 'TRIANGULATE')
        mod.min_vertices = 5
        apply(obj, mod)
        mesh = obj.data
        start_v, start_f = len(vertices), len(faces)
        vertices.extend(canonical(obj.matrix_world @ v.co) for v in mesh.vertices)
        uv = mesh.uv_layers.active
        for polygon in mesh.polygons:
            material = (mesh.materials[polygon.material_index]
                        if polygon.material_index < len(mesh.materials) else None)
            faces.append({'vertices': [start_v + i for i in polygon.vertices],
                          'uv': [list(uv.data[i].uv) if uv else [0, 0]
                                 for i in polygon.loop_indices],
                          'texture': material.get('hc_texture', '') if material else '',
                          'material': material.get('hc_material', '') if material else ''})
        for label in sorted(labels[ident]):
            selection = selections.setdefault(label, {'vertices': [], 'faces': []})
            selection['vertices'].extend(range(start_v, len(vertices)))
            selection['faces'].extend(range(start_f, len(faces)))
    if len(vertices) > MAX_ELEMENTS or len(faces) > MAX_ELEMENTS:
        raise ValueError('blender.mesh_limit')
    result = {'schema': 'neutral.v1', 'vertices': vertices, 'faces': faces,
              'selections': selections, 'points': points, 'proxies': proxies}
    Path(output).write_text(json.dumps(result, sort_keys=True, allow_nan=False), encoding='utf-8')
    if render:
        scene = bpy.context.scene
        scene.render.engine = 'BLENDER_WORKBENCH'
        scene.render.resolution_x = scene.render.resolution_y = 256
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'TARGA_RAW'
        scene.display.shading.light = 'STUDIO'
        scene.display.shading.color_type = 'SINGLE'
        scene.display.shading.single_color = (0.65, 0.65, 0.65)
        scene.display.shading.show_shadows = False
        scene.display.shading.show_cavity = False
        scene.display.shading.background_type = 'WORLD'
        scene.world.color = (0.05, 0.05, 0.05)
        coords = [obj.matrix_world @ Vector(corner) for obj in objects.values() for corner in obj.bound_box]
        low = Vector(tuple(min(v[i] for v in coords) for i in range(3)))
        high = Vector(tuple(max(v[i] for v in coords) for i in range(3)))
        center = (low + high) / 2
        radius = max((high - low).length, 0.01)
        camera_data = bpy.data.cameras.new('hc_camera')
        camera = bpy.data.objects.new('hc_camera', camera_data)
        scene.collection.objects.link(camera)
        camera_data.type, camera_data.ortho_scale = 'ORTHO', radius * 1.2
        camera_data.clip_end = radius * 10
        camera_data.clip_start = radius / 1000
        scene.camera = camera
        for view, direction in {'front': (0, -1, 0), 'back': (0, 1, 0),
                                'left': (-1, 0, 0), 'right': (1, 0, 0),
                                'top': (0, 0, 1), 'bottom': (0, 0, -1)}.items():
            camera.location = center + Vector(direction) * radius * 2
            camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = str(Path(output).with_name(view + '.tga'))
            bpy.ops.render.render(write_still=True)


def selftest():
    assert canonical((1, 2, 3)) == [1.0, 3.0, -2.0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--recipe', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else None)
    if args.selftest:
        selftest()
        print('{"valid": true}')
    elif args.recipe and args.output:
        execute(load_json(args.recipe.read_bytes()), args.output, args.render)
    else:
        parser.error('--recipe and --output required')


if __name__ == '__main__':
    main()
