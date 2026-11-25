"""Six orthographic Blender TGA views and a bounded stdlib image difference.

Metric: RGBA byte-space normalized MAE, RMSE and maximum error. This is not a
perceptual measure and not an engine equivalence claim; the perceptual FLIP gate
and heatmap live in tools.validate.flip_diff and are wired in by render_check. Compare captures with identical framing,
renderer, colour settings and Blender version. build renders use fixed settings;
recipe-dependent auto framing means separately built models can hide scale
changes, so mesh/LOD checks remain necessary.
"""
import json
import math
from pathlib import Path

from tools.assets import blender_runner
from tools.assets.pbr_pack import Image, decode_image

VIEWS = ('front', 'back', 'left', 'right', 'top', 'bottom')


def metric(reference, candidate):
    if not isinstance(reference, Image) or not isinstance(candidate, Image):
        raise ValueError('diff.image_required')
    if (reference.width, reference.height) != (candidate.width, candidate.height):
        raise ValueError('diff.dimensions')
    total, squared, maximum, changed = 0, 0, 0, 0
    for i in range(0, len(reference.rgba), 4):
        pixel_changed = False
        for x, y in zip(reference.rgba[i:i+4], candidate.rgba[i:i+4]):
            error = abs(x-y)
            total += error
            squared += error*error
            maximum = max(maximum, error)
            pixel_changed |= error > 0
        changed += int(pixel_changed)
    samples = len(reference.rgba)
    return {'mae': total/samples/255, 'rmse': math.sqrt(squared/samples)/255,
            'max_error': maximum/255, 'changed_pixels': changed,
            'pixels': reference.width*reference.height}


def compare(reference, candidate, *, threshold=0.01):
    if (type(threshold) not in (int, float) or not math.isfinite(threshold)
            or not 0 <= threshold <= 1):
        raise ValueError('diff.threshold')
    if set(reference) != set(VIEWS) or set(candidate) != set(VIEWS):
        raise ValueError('diff.six_views_required')
    results = {view: metric(decode_image(reference[view]), decode_image(candidate[view])) for view in VIEWS}
    return {'schema': 'visual-diff.v1', 'metric': 'rgba_byte_rmse', 'threshold': threshold,
            'pass': all(result['rmse'] <= threshold for result in results.values()),
            'views': results, 'engine_verified': False}


def palette_distance(images, references):
    """Foreground-weighted mean nearest-colour CIE76 Delta E (D65 sRGB).

    Deterministic 4-bit RGB histogram; the 16 most frequent reference bins form
    the palette (ties use ascending RGB). Black background is excluded. This
    is a style metric, with thresholds calibrated by the lead, not an engine gate.
    """
    from tools.validate.flip_diff import _numpy
    np = _numpy()
    def histogram(items):
        counts = np.zeros(4096, dtype=np.int64)
        for image in items:
            rgb = np.frombuffer(image.rgba, dtype=np.uint8).reshape(-1, 4)
            rgb = rgb[(rgb[:, 3] > 127) & (rgb[:, :3].max(axis=1) > 8), :3].astype(np.int64)
            bins = rgb // 16
            counts += np.bincount(bins[:, 0]*256 + bins[:, 1]*16 + bins[:, 2], minlength=4096)
        if not counts.any():
            raise ValueError('score.empty_palette')
        return counts
    def lab(indices):
        rgb = np.stack((indices // 256, indices // 16 % 16, indices % 16), axis=1)
        rgb = (rgb * 16 + 7.5) / 255
        linear = np.where(rgb <= 0.04045, rgb/12.92, ((rgb+0.055)/1.055)**2.4)
        xyz = linear @ np.array([[.4124564, .2126729, .0193339],
                                 [.3575761, .7151522, .1191920],
                                 [.1804375, .0721750, .9503041]])
        xyz /= np.array([.95047, 1., 1.08883])
        f = np.where(xyz > (6/29)**3, np.cbrt(xyz), xyz/(3*(6/29)**2) + 4/29)
        return np.stack((116*f[:, 1]-16, 500*(f[:, 0]-f[:, 1]),
                         200*(f[:, 1]-f[:, 2])), axis=1)
    weights, ref = histogram(images), histogram(references)
    occupied = np.flatnonzero(weights)
    palette = np.array(sorted(np.flatnonzero(ref), key=lambda i: (-int(ref[i]), int(i)))[:16])
    distances = np.linalg.norm(lab(occupied)[:, None, :] - lab(palette)[None, :, :], axis=2).min(axis=1)
    return float(np.average(distances, weights=weights[occupied]))


def render_request(recipe, *, config=None, timeout=120):
    """Request all six views in one isolated external Blender invocation."""
    result = blender_runner.build(recipe, config=config, timeout=timeout, render=True)
    if set(result.renders) != set(VIEWS):
        raise ValueError('diff.render_views_missing')
    for raw in result.renders.values():
        decode_image(raw)
    return result.renders


def write_report(report, directory):
    directory = blender_runner.build_directory(directory)
    path = directory / 'visual-diff.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    return path


def selftest():
    image = Image(1, 1, b'\x00\x00\x00\xff')
    assert metric(image, image)['rmse'] == 0
    other = Image(1, 1, b'\xff\xff\xff\xff')
    assert metric(image, other)['mae'] == 0.75


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true', required=True)
    parser.parse_args()
    selftest()
    print('{"valid": true}')
