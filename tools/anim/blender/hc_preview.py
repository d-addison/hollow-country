"""Blender background render of a Hollow Country clip preview (stand-in mannequin, our own geometry).

Qualified on Blender 5.2.4 LTS (2026-11-21, headless render). Preview only, never engine playback.

    blender.exe -b --factory-startup --python tools/anim/blender/hc_preview.py -- \
        build/anims/preview/hc_sit_wall_idle.json <out_dir> hc-sit-wall-idle

Reads the joint-position JSON written by tools/anim/build_infected_clips.py and builds one
cylinder per segment plus a sphere head, keyframed per frame (no skinning, no game meshes).
It renders a 640x480 3/4 view to <out_dir>/<name>-34-blender.mp4 (FFmpeg output). Convert the
MP4 to a GIF with ffmpeg or ImageMagick if needed.

Add --strip [N] (default 8) to skip the video and render N evenly spaced keyframes (first and
last included) as PNG stills plus one contact sheet, for deterministic visual diffing:

    blender.exe -b --factory-startup --python tools/anim/blender/hc_preview.py -- \
        build/anims/preview/hc_sit_wall_idle.json <out_dir> hc-sit-wall-idle --strip 8

Outputs: <out_dir>/<name>-34-fNNN.png (one per keyframe, NNN = 1-based frame number) and
<out_dir>/<name>-34-sheet.png (tiles left to right, top to bottom, 4 columns). The frame
selection and sheet layout are pure functions (strip_frames, sheet_layout) so they are unit
tested without Blender; the render itself needs a real Blender run. Engine axes are Y up / +Z forward /
left-handed; Blender is Z up / right-handed, so engine (x, y, z) maps to Blender (x, z, y)
(swapping two axes flips the handedness).
"""
import json
import math
import os
import sys

try:
    import bpy  # noqa: E402  (Blender only)
    from mathutils import Vector  # noqa: E402
except ImportError:  # plain Python: the pure helpers below stay importable for unit tests
    bpy = None
    Vector = None

STRIP_DEFAULT_FRAMES = 8
STRIP_COLUMNS = 4
RES_X, RES_Y = 640, 480


def strip_frames(frame_count, count):
    """1-based frame numbers for a contact sheet: evenly spaced, first and last included, unique, ascending."""
    if frame_count < 1:
        return []
    count = max(1, min(int(count), frame_count))
    if count == 1:
        return [1]
    picked = []
    for i in range(count):
        frame = 1 + (i * (frame_count - 1) + (count - 1) // 2) // (count - 1)
        if not picked or frame != picked[-1]:
            picked.append(frame)
    return picked


def sheet_layout(count, columns=STRIP_COLUMNS):
    """(columns, rows) for count tiles, filled left to right then top to bottom."""
    columns = max(1, min(columns, count)) if count > 0 else 1
    rows = (count + columns - 1) // columns if count > 0 else 0
    return columns, rows


def tile_origin(index, columns, rows, tile_w, tile_h):
    """Bottom-left pixel (x, y) of tile `index` in a Blender image (rows are stored bottom-up)."""
    col, row = index % columns, index // columns
    return col * tile_w, (rows - 1 - row) * tile_h


def parse_args(argv):
    """argv is everything after Blender's '--': src out_dir name [--strip [N]]. Returns (src, out_dir, name, strip_n)."""
    args = list(argv)
    strip_n = 0
    if '--strip' in args:
        at = args.index('--strip')
        strip_n = STRIP_DEFAULT_FRAMES
        del args[at]
        if at < len(args) and args[at].isdigit():
            strip_n = int(args.pop(at))
            if strip_n < 1:
                raise ValueError('--strip needs at least one frame')
    if len(args) != 3:
        raise ValueError('usage: <src.json> <out_dir> <name> [--strip [N]]')
    return args[0], args[1], args[2], strip_n


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


def render_strip(scene, out_dir, name, frame_count, count):
    """Render `count` keyframes to PNG stills and assemble one contact sheet. Returns the sheet path."""
    import numpy as np  # bundled with Blender

    if hasattr(scene.render.image_settings, 'media_type'):
        scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.view_settings.view_transform = 'Standard'
    if hasattr(scene.eevee, 'taa_render_samples'):
        scene.eevee.taa_render_samples = 16  # fixed sample count keeps stills repeatable
    frames = strip_frames(frame_count, count)
    columns, rows = sheet_layout(len(frames))
    sheet = np.zeros((rows * RES_Y, columns * RES_X, 4), dtype=np.float32)
    for i, frame in enumerate(frames):
        scene.frame_set(frame)
        still = os.path.join(out_dir, '%s-34-f%03d.png' % (name, frame))
        scene.render.filepath = still
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(still)
        w, h = img.size
        pixels = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(pixels)
        x, y = tile_origin(i, columns, rows, RES_X, RES_Y)
        sheet[y:y + h, x:x + w, :] = pixels.reshape(h, w, 4)
        bpy.data.images.remove(img)
    out = bpy.data.images.new(name + '-sheet', columns * RES_X, rows * RES_Y, alpha=False)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = os.path.join(out_dir, name + '-34-sheet.png')
    out.file_format = 'PNG'
    out.save()
    print('wrote', out.filepath_raw, 'frames', frames)
    return out.filepath_raw


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    src, out_dir, name, strip_n = parse_args(argv)
    with open(src) as h:
        data = json.load(h)
    frames, segments, fps = data['frames'], data['segments'], data.get('fps', 30)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = fps
    scene.frame_start, scene.frame_end = 1, len(frames)
    scene.render.resolution_x, scene.render.resolution_y = RES_X, RES_Y
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in \
        [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
    os.makedirs(out_dir, exist_ok=True)
    if not strip_n:
        # Blender 5.x lists FFMPEG only after selecting the video media type.
        if hasattr(scene.render.image_settings, 'media_type'):
            scene.render.image_settings.media_type = 'VIDEO'
        scene.render.image_settings.file_format = 'FFMPEG'
        scene.render.ffmpeg.format = 'MPEG4'
        scene.render.ffmpeg.codec = 'H264'
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
        if 'Skull' in fr:   # follows the head's rotation (builder JSON with head points)
            head.location = to_blender(fr['Head']).lerp(to_blender(fr['Skull']), 0.78)
        else:
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
    if strip_n:
        render_strip(scene, out_dir, name, len(frames), strip_n)
        return
    bpy.ops.render.render(animation=True)
    print('wrote', scene.render.filepath)


if __name__ == '__main__':
    main()
