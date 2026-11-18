"""Blender background render of a Hollow Country clip preview (stand-in mannequin, our own geometry).

UNTESTED: written while Windows interop was down, so Blender has not run this yet.

    blender.exe -b --factory-startup --python tools/anim/blender/hc_preview.py -- \
        build/anims/preview/hc_sit_wall_idle.json <out_dir> hc-sit-wall-idle

Reads the joint-position JSON written by tools/anim/build_infected_clips.py and builds one
cylinder per segment plus a sphere head, keyframed per frame (no skinning, no game meshes).
It renders a 640x480 3/4 view to <out_dir>/<name>-34-blender.mp4 (FFmpeg output). Convert the
MP4 to a GIF with ffmpeg or ImageMagick if needed. Engine axes are Y up / +Z forward /
left-handed; Blender is Z up / right-handed, so engine (x, y, z) maps to Blender (x, z, y)
(swapping two axes flips the handedness).
"""
import json
import math
import os
import sys

import bpy  # noqa: E402  (Blender only)
from mathutils import Vector  # noqa: E402


def to_blender(p):
    # engine (x right, y up, z forward, left-handed) -> Blender (x right, y forward, z up, right-handed)
    return Vector((p[0], p[2], p[1]))


def segment_radius(a):
    if 'Leg' in a:
        return 0.06
    if 'Arm' in a:
        return 0.042
    if a.startswith('Spine') or a == 'Pelvis':
        return 0.1
    return 0.035


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    src, out_dir, name = argv[0], argv[1], argv[2]
    with open(src) as h:
        data = json.load(h)
    frames, segments, fps = data['frames'], data['segments'], data.get('fps', 30)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = fps
    scene.frame_start, scene.frame_end = 1, len(frames)
    scene.render.resolution_x, scene.render.resolution_y = 640, 480
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in \
        [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    os.makedirs(out_dir, exist_ok=True)
    scene.render.filepath = os.path.join(out_dir, name + '-34-blender.mp4')

    mat = bpy.data.materials.new('hc_skin')
    mat.diffuse_color = (0.55, 0.6, 0.45, 1)
    bpy.ops.mesh.primitive_plane_add(size=6)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.38, 0.6))
    wall = bpy.context.object
    wall.scale = (1.8, 0.1, 1.2)

    parts = []
    for a, b in segments:
        bpy.ops.mesh.primitive_cylinder_add(radius=segment_radius(a), depth=1.0, vertices=12)
        ob = bpy.context.object
        ob.data.materials.append(mat)
        parts.append((ob, a, b))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1)
    head = bpy.context.object
    head.data.materials.append(mat)

    for i, fr in enumerate(frames):
        for ob, a, b in parts:
            pa, pb = to_blender(fr[a]), to_blender(fr[b])
            d = pb - pa
            ob.location = (pa + pb) / 2
            ob.rotation_mode = 'QUATERNION'
            ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized() if d.length else Vector((0, 0, 1)))
            ob.scale = (1, 1, max(d.length, 1e-3))
            ob.keyframe_insert('location', frame=i + 1)
            ob.keyframe_insert('rotation_quaternion', frame=i + 1)
            ob.keyframe_insert('scale', frame=i + 1)
        head.location = to_blender(fr['Head']) + Vector((0, 0.02, 0.07))
        head.keyframe_insert('location', frame=i + 1)

    cam_data = bpy.data.cameras.new('cam')
    cam = bpy.data.objects.new('cam', cam_data)
    scene.collection.objects.link(cam)
    cam.location = to_blender((1.75, 1.15, 2.05))
    target = to_blender((0.0, 0.45, 0.12))
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (target - cam.location).to_track_quat('-Z', 'Y')
    cam_data.angle = math.radians(42)
    scene.camera = cam
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    scene.collection.objects.link(sun)
    bpy.ops.render.render(animation=True)
    print('wrote', scene.render.filepath)


if __name__ == '__main__':
    main()
