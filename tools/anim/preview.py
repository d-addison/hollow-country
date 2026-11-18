"""Offline stick-mannequin preview of authored clips (stdlib renderer + optional ImageMagick GIF).

This is NOT DayZ and NOT skinned: it draws the joint positions that our own FK computes from
the clip, as capsules, from a 3/4 and a side camera. Use it to judge the pose and the loop; only
DayZ shows the skinned infected (docs/ANIMATION_PIPELINE.md).

    python3 tools/anim/preview.py --out <dir> --name hc-sit-wall-idle build/anims/preview/hc_sit_wall_idle.json
    python3 tools/anim/preview.py --out <dir> --name hc-sit-sequence --blend 15 \
        build/anims/preview/reference_stand.json:0:1 build/anims/preview/hc_sit_wall_idle.json:0:105 \
        build/anims/preview/hc_sit_wall_getup.json build/anims/preview/reference_stand.json:0:1:12

A source is FILE[:FIRST:END[:HOLD]] (frames FIRST..END-1, last one held HOLD extra frames).
``--blend N`` cross-fades joint positions over N frames between sources (an approximation of
the graph transition blend). Writes PPM frames to a temporary folder and, when ImageMagick
``convert`` is on PATH, <name>-34.gif and <name>-side.gif (640x480).
"""
import argparse
import array
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

W, H = 1280, 960            # rendered at 2x, ImageMagick halves it (cheap antialiasing)
UP = (0.0, 1.0, 0.0)
SKIN = (150, 160, 128)
LEFT = (118, 128, 100)
RIGHT = (176, 184, 150)
WALL = (92, 80, 70)
GROUND = (58, 64, 52)
GRID = (78, 86, 70)
CAMERAS = {
    '34': ((1.75, 1.15, 2.05), (0.0, 0.45, 0.12), 42.0),
    'side': ((2.6, 0.75, 0.15), (0.0, 0.45, 0.12), 40.0),
}
# --tall: framing that also fits the standing frames (sequences that start or end standing)
TALL_CAMERAS = {
    '34': ((2.3, 1.45, 2.7), (0.0, 0.8, 0.12), 46.0),
    'side': ((3.3, 1.0, 0.15), (0.0, 0.8, 0.12), 44.0),
}


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


class Camera:
    """Left-handed engine axes (X right, Y up, Z forward), so the right vector is up x forward."""

    def __init__(self, eye, target, fov):
        self.eye = eye
        self.f = _norm(_sub(target, eye))
        self.r = _norm(_cross(UP, self.f))
        self.u = _cross(self.f, self.r)
        self.k = (H / 2) / math.tan(math.radians(fov) / 2)

    def project(self, p):
        d = _sub(p, self.eye)
        z = _dot(d, self.f)
        z = max(z, 0.05)
        return (W / 2 + self.k * _dot(d, self.r) / z, H / 2 - self.k * _dot(d, self.u) / z, z)


def _segment_radius(a, b):
    if 'Leg' in a or 'UpLeg' in a:
        return 0.06
    if 'Foot' in a:
        return 0.04
    if 'Arm' in a or 'ForeArm' in a:
        return 0.042
    if 'Hand' in a:
        return 0.03
    if a.startswith('Spine') or a == 'Pelvis':
        return 0.11 if b != 'LeftUpLeg' and b != 'RightUpLeg' else 0.07
    if a == 'Neck':
        return 0.05
    return 0.05


def _color(a, b):
    if b.startswith('Left') or a.startswith('Left'):
        return LEFT
    if b.startswith('Right') or a.startswith('Right'):
        return RIGHT
    return SKIN


class Canvas:
    def __init__(self, background):
        self.rgb = bytearray(background)
        self.z = array.array('f', [1e9]) * (W * H)

    def capsule(self, p0, p1, r0, r1, color):
        x0, y0, z0 = p0
        x1, y1, z1 = p1
        rr = max(r0, r1)
        minx, maxx = int(max(min(x0, x1) - rr, 0)), int(min(max(x0, x1) + rr + 1, W - 1))
        miny, maxy = int(max(min(y0, y1) - rr, 0)), int(min(max(y0, y1) + rr + 1, H - 1))
        dx, dy = x1 - x0, y1 - y0
        ll = dx * dx + dy * dy or 1e-6
        rgb, zb = self.rgb, self.z
        cr, cg, cb = color
        for y in range(miny, maxy + 1):
            row = y * W
            for x in range(minx, maxx + 1):
                t = ((x - x0) * dx + (y - y0) * dy) / ll
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                px, py = x0 + dx * t - x, y0 + dy * t - y
                rad = r0 + (r1 - r0) * t
                d2 = px * px + py * py
                if d2 > rad * rad:
                    continue
                zz = z0 + (z1 - z0) * t
                i = row + x
                if zz >= zb[i]:
                    continue
                zb[i] = zz
                s = 1.0 - 0.45 * d2 / (rad * rad) + 0.12 * (-px - py) / (rad + 1)
                s = 0.3 if s < 0.3 else (1.15 if s > 1.15 else s)
                j = 3 * i
                rgb[j] = min(255, int(cr * s))
                rgb[j + 1] = min(255, int(cg * s))
                rgb[j + 2] = min(255, int(cb * s))


def _background(cam, wall):
    rgb = bytearray(W * H * 3)
    for y in range(H):
        g = int(28 + 22 * y / H)
        rgb[y * W * 3:(y + 1) * W * 3] = bytes((g, g + 2, g + 6)) * W
    c = Canvas(bytes(rgb))
    # ground quad as dense thin capsules (simple and good enough for a preview)
    for i in range(-12, 13):
        a, b = cam.project((i * 0.25, 0.0, -1.5)), cam.project((i * 0.25, 0.0, 3.0))
        c.capsule(a, b, 1.2, 1.2, GRID)
        a, b = cam.project((-3.0, 0.0, i * 0.25 + 0.75)), cam.project((3.0, 0.0, i * 0.25 + 0.75))
        c.capsule(a, b, 1.2, 1.2, GRID)
    if wall:
        for k in range(0, 40):
            y = k * 0.03
            a, b = cam.project((-0.9, y, -0.33)), cam.project((0.9, y, -0.33))
            c.capsule(a, b, 6.0, 6.0, WALL if k % 8 else (80, 70, 62))
    c.z = array.array('f', [1e9]) * (W * H)
    return bytes(c.rgb)


def render(frame, segments, cam, background):
    c = Canvas(background)
    for a, b in segments:
        pa, pb = cam.project(frame[a]), cam.project(frame[b])
        r = _segment_radius(a, b)
        c.capsule(pa, pb, cam.k * r / pa[2], cam.k * r / pb[2], _color(a, b))
    head = cam.project(frame['Head'])
    neck = frame['Head']
    top = cam.project((neck[0], neck[1] + 0.09, neck[2] + 0.02))
    c.capsule(head, top, cam.k * 0.075 / head[2], cam.k * 0.095 / top[2], SKIN)
    for foot in ('LeftFoot', 'RightFoot'):
        p = frame[foot]
        q = cam.project((p[0], 0.0, p[2]))
        c.capsule(q, q, cam.k * 0.05 / q[2], cam.k * 0.05 / q[2], (40, 44, 36))  # contact shadow
    return c.rgb


def load_sources(specs, blend):
    frames, segments, fps = [], None, 30
    for spec in specs:
        parts = spec.split(':')
        with open(parts[0]) as h:
            data = json.load(h)
        segments = [tuple(s) for s in data['segments']]
        fps = data.get('fps', 30)
        src = data['frames']
        first = int(parts[1]) if len(parts) > 1 else 0
        end = int(parts[2]) if len(parts) > 2 else len(src)
        hold = int(parts[3]) if len(parts) > 3 else 0
        chunk = src[first:end] + [src[end - 1]] * hold
        if frames and blend:
            a, b = frames[-1], chunk[0]
            for i in range(1, blend + 1):
                t = i / (blend + 1)
                t = t * t * (3 - 2 * t)
                frames.append({k: [x + (y - x) * t for x, y in zip(a[k], b[k])] for k in a})
        frames.extend(chunk)
    return frames, segments, fps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('sources', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--blend', type=int, default=0)
    ap.add_argument('--no-wall', action='store_true')
    ap.add_argument('--tall', action='store_true', help='frame standing poses too')
    ap.add_argument('--label', default='offline Python stick preview - our FK of the clip - not DayZ')
    args = ap.parse_args(argv)
    frames, segments, fps = load_sources(args.sources, args.blend)
    os.makedirs(args.out, exist_ok=True)
    tool = shutil.which('convert')
    for view, (eye, target, fov) in (TALL_CAMERAS if args.tall else CAMERAS).items():
        cam = Camera(eye, target, fov)
        bg = _background(cam, not args.no_wall)
        tmp = tempfile.mkdtemp(prefix='hc-preview-')
        for i, fr in enumerate(frames):
            with open(os.path.join(tmp, 'f%04d.ppm' % i), 'wb') as h:
                h.write(b'P6 %d %d 255\n' % (W, H))
                h.write(render(fr, segments, cam, bg))
        target_gif = os.path.join(args.out, '%s-%s.gif' % (args.name, view))
        if tool:
            delay = max(2, int(round(100.0 / fps * 2)))   # every second frame -> 15 fps GIF
            ppms = sorted(os.path.join(tmp, f) for f in os.listdir(tmp))[::2]
            subprocess.run([tool, '-delay', str(delay), '-loop', '0'] + ppms +
                           ['-resize', '50%', '-fill', '#d8d8c8', '-pointsize', '15', '-gravity', 'south',
                            '-annotate', '+0+8', '%s | %s view' % (args.label, view),
                            '+dither', '-colors', '64', '-layers', 'OptimizeFrame', target_gif], check=True)
            shutil.rmtree(tmp)
            print('wrote %s (%d bytes, %d frames)' % (target_gif, os.path.getsize(target_gif), len(ppms)))
        else:
            print('ImageMagick convert not found; frames left in', tmp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
