"""Six-view contact sheet and silhouette checks over rendered asset views.

The pure-Python part (silhouette masks, IoU, contact sheet, golden pins) needs
no Blender or GPU. Views come from visual_diff.render_request (one isolated
external Blender run, lead-only) or from directories holding front/back/left/
right/top/bottom .tga or .png files. Verdicts are offline mesh evidence only:
engine_verified is always false and never replaces a native in-game check.

Goldens are never stored in git: a manifest pins each view by sha256 and the
image bytes live in a local directory outside the repository.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import zlib

from tools.assets import blender_runner, visual_diff
from tools.assets.pbr_pack import Image, decode_image
from tools.assets.provenance import SHA256, Refusal, digest

VIEWS = visual_diff.VIEWS
MIN_IOU = 0.92
BACKGROUND_TOLERANCE = 8
MAX_VIEW_BYTES = 8 * 1024 * 1024
GOLDEN_SCHEMA = 'render-golden.v1'


def silhouette(image, *, tolerance=BACKGROUND_TOLERANCE):
    """Foreground mask: alpha when the render has transparency, else distance
    from the top-left corner colour (the renders frame the model with margin)."""
    if (not isinstance(image, Image) or type(tolerance) is not int
            or not 0 <= tolerance <= 255):
        raise ValueError('render.silhouette_input')
    px = image.rgba
    alphas = px[3::4]
    mask = bytearray(image.width * image.height)
    if min(alphas) < 255 and max(alphas) > 0:
        for i, a in enumerate(alphas):
            mask[i] = 1 if a > 127 else 0
    else:
        ref = px[0:3]
        for i in range(len(mask)):
            r, g, b = px[4*i:4*i+3]
            mask[i] = 1 if max(abs(r-ref[0]), abs(g-ref[1]), abs(b-ref[2])) > tolerance else 0
    return image.width, image.height, bytes(mask)


def iou(a, b):
    if a[:2] != b[:2]:
        raise ValueError('render.dimensions')
    inter = union = 0
    for x, y in zip(a[2], b[2]):
        inter += x & y
        union += x | y
    if not union:
        raise ValueError('render.empty_silhouette')
    return inter / union


def compare_silhouettes(reference, candidate, *, min_iou=MIN_IOU):
    """reference/candidate: {view: image bytes}. Per-view IoU against min_iou."""
    if type(min_iou) not in (int, float) or not 0 < min_iou <= 1:
        raise ValueError('render.threshold')
    if set(reference) != set(VIEWS) or set(candidate) != set(VIEWS):
        raise ValueError('render.six_views_required')
    views = {}
    for view in VIEWS:
        views[view] = iou(silhouette(decode_image(reference[view])),
                          silhouette(decode_image(candidate[view])))
    return {'schema': 'render-check.v1', 'metric': 'silhouette_iou', 'min_iou': min_iou,
            'pass': all(v >= min_iou for v in views.values()), 'views': views,
            'engine_verified': False}


def _png(width, height, rgba):
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body))
    rows = b''.join(b'\x00' + rgba[y*width*4:(y+1)*width*4] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def contact_sheet(views, *, columns=3):
    """Deterministic PNG grid in VIEWS order; all views must share dimensions."""
    if set(views) != set(VIEWS) or type(columns) is not int or not 1 <= columns <= len(VIEWS):
        raise ValueError('render.six_views_required')
    images = [decode_image(views[v]) for v in VIEWS]
    w, h = images[0].width, images[0].height
    if any((i.width, i.height) != (w, h) for i in images):
        raise ValueError('render.dimensions')
    rows = -(-len(images) // columns)
    if w * columns * h * rows > 16 * 1024 * 1024:
        raise ValueError('render.sheet_size')
    sheet = bytearray(w * columns * h * rows * 4)
    stride = w * columns * 4
    for n, image in enumerate(images):
        ox, oy = (n % columns) * w * 4, (n // columns) * h
        for y in range(h):
            start = (oy + y) * stride + ox
            sheet[start:start + w*4] = image.rgba[y*w*4:(y+1)*w*4]
    return _png(w * columns, h * rows, bytes(sheet))


def pin_goldens(views):
    """Manifest to commit; the image bytes stay in a local directory outside git."""
    if set(views) != set(VIEWS):
        raise ValueError('render.six_views_required')
    for raw in views.values():
        decode_image(raw)
    return {'schema': GOLDEN_SCHEMA, 'views': {v: digest(views[v]) for v in VIEWS}}


def check_goldens(views, manifest, goldens, *, min_iou=MIN_IOU, threshold=0.01):
    """goldens: {view: bytes} read from the external store. Every golden must match
    its pinned sha256 before it is used; mismatch is a refusal, never a pass."""
    if (not isinstance(manifest, dict) or set(manifest) != {'schema', 'views'}
            or manifest['schema'] != GOLDEN_SCHEMA or not isinstance(manifest['views'], dict)
            or set(manifest['views']) != set(VIEWS)):
        raise Refusal('render.golden_manifest')
    for view in VIEWS:
        pinned = manifest['views'][view]
        if not isinstance(pinned, str) or not SHA256.fullmatch(pinned):
            raise Refusal('render.golden_manifest')
        if view not in goldens or digest(goldens[view]) != pinned:
            raise Refusal('render.golden_digest')
    report = compare_silhouettes(goldens, views, min_iou=min_iou)
    report['pixel_diff'] = visual_diff.compare(goldens, views, threshold=threshold)
    report['pass'] = report['pass'] and report['pixel_diff']['pass']
    return report


def read_views(directory):
    """Read <view>.tga|png from a directory; links, specials and big files refused."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise Refusal('render.directory')
    views = {}
    for view in VIEWS:
        found = [directory / (view + ext) for ext in ('.tga', '.png') if (directory / (view + ext)).exists()]
        if len(found) != 1 or found[0].is_symlink() or not found[0].is_file():
            raise Refusal('render.view_missing')
        if found[0].stat().st_size > MAX_VIEW_BYTES:
            raise Refusal('render.view_size')
        views[view] = found[0].read_bytes()
    return views


def render(recipe, *, config=None, timeout=120):
    """One isolated external Blender run (lead-only; never used by unit tests)."""
    return visual_diff.render_request(recipe, config=config, timeout=timeout)


def selftest():
    image = Image(2, 1, bytes((10, 10, 10, 255, 200, 200, 200, 255)))
    assert iou(silhouette(image), silhouette(image)) == 1
    raw = {v: _png(2, 1, image.rgba) for v in VIEWS}
    assert decode_image(contact_sheet(raw)).width == 6


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--views', type=Path, help='directory of six candidate views')
    parser.add_argument('--reference', type=Path, help='directory of six reference views')
    parser.add_argument('--min-iou', type=float, default=MIN_IOU)
    parser.add_argument('--sheet', type=Path, help='write contact sheet PNG under build/')
    args = parser.parse_args(argv)
    if args.selftest:
        selftest()
        print('{"valid": true}')
        return 0
    if not args.views:
        parser.error('--views or --selftest required')
    try:
        views = read_views(args.views)
        result = {'valid': True}
        if args.reference:
            report = compare_silhouettes(read_views(args.reference), views, min_iou=args.min_iou)
            result = {'valid': report['pass'], 'report': report}
        if args.sheet:
            out = blender_runner.build_directory(args.sheet.parent) / args.sheet.name
            with out.open('xb') as stream:
                stream.write(contact_sheet(views))
        print(json.dumps(result, sort_keys=True))
        return 0 if result['valid'] else 1
    except (Refusal, ValueError, OSError, blender_runner.BlenderRefusal) as exc:
        print(json.dumps({'valid': False, 'reason': str(exc) if isinstance(exc, (Refusal, ValueError, blender_runner.BlenderRefusal)) else 'render.io'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
