# SPDX-License-Identifier: BSD-3-Clause
"""FLIP perceptual difference (LDR-FLIP) and heatmap for the render check (WD-41-3).

Licence: BSD-3-Clause. This is a Python/numpy port of the LDR-FLIP pipeline of the
NVIDIA FLIP reference implementation (https://github.com/NVlabs/flip, src/cpp/FLIP.h),
whose licence allows redistribution and modification with the notice below retained.
Algorithm: Andersson, Nilsson, Akenine-Moller, Oskarsson, Astrom, Fairchild,
"FLIP: A Difference Evaluator for Alternating Images", HPG 2020. HDR-FLIP, tone mapping
and the command-line tool are not ported; only 8-bit sRGB inputs are supported. The
magma heatmap uses 16 anchor colours of the CC0 matplotlib/viridis magma map, linearly
interpolated.

Copyright (c) 2020-2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of
conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list
of conditions and the following disclaimer in the documentation and/or other materials
provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be
used to endorse or promote products derived from this software without specific prior
written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Scope: offline evidence about rendered mesh previews only. A FLIP score never claims
engine equivalence (engine_verified is always false). numpy is required; when it is not
importable the check refuses with `flip.numpy_required` instead of skipping. The
threshold is a provisional review budget, not a measured value.
"""
import argparse
import json
import math
from pathlib import Path
import sys

from tools.assets.pbr_pack import Image, decode_image
from tools.assets.provenance import Refusal

VIEWS = ('front', 'back', 'left', 'right', 'top', 'bottom')
SCHEMA = 'flip-diff.v1'
# 0.7 m viewing distance, 3840 px wide 0.7 m monitor: the reference tool default.
DEFAULT_PPD = 0.7 * (3840.0 / 0.7) * math.pi / 180.0
MAX_MEAN_FLIP = 0.05
MAX_PIXELS = 2 * 1024 * 1024
# Reference tool constants (gqc, gpc, gpt, gw, gqf) and CSF Gaussian parameters.
GQC, GPC, GPT, GW, GQF = 0.7, 0.4, 0.95, 0.082, 0.5
CSF_A1, CSF_B1 = (1.0, 1.0, 34.1), (0.0047, 0.0053, 0.04)
CSF_A2, CSF_B2 = (0.0, 0.0, 13.5), (1.0e-5, 1.0e-5, 0.025)
ILLUMINANT = (0.950428545, 1.0, 1.088900371)
MAGMA = ((0, 0, 4), (11, 9, 36), (32, 17, 75), (59, 15, 112), (87, 21, 126), (114, 31, 129),
         (140, 41, 129), (168, 50, 125), (196, 60, 117), (222, 73, 104), (241, 96, 93),
         (250, 127, 94), (254, 159, 109), (254, 191, 132), (253, 222, 160), (252, 253, 191))


def _numpy():
    try:
        import numpy
    except ImportError:
        raise Refusal('flip.numpy_required') from None
    return numpy


def _linear(np, srgb):
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


def _rgb_to_xyz(np, rgb):
    matrix = np.array([[10135552.0, 8788810.0, 4435075.0],
                       [2613072.0 * 2, 8788810.0 * 2, 887015.0 * 2],
                       [1425312.0 / 3.0, 8788810.0 / 3.0, 70074185.0 / 3.0]]) / 24577794.0
    return rgb @ matrix.T


def _xyz_to_rgb(np, xyz):
    matrix = np.array([[3.241003275, -1.537398934, -0.498615861],
                       [-0.969224334, 1.875930071, 0.041554224],
                       [0.055639423, -0.204011202, 1.057148933]])
    return xyz @ matrix.T


def _xyz_to_lab(np, xyz):
    delta = 6.0 / 29.0
    scaled = xyz / np.array(ILLUMINANT)
    f = np.where(scaled > delta ** 3, np.cbrt(scaled), scaled / (3.0 * delta * delta) + 4.0 / 29.0)
    return np.stack((116.0 * f[..., 1] - 16.0, 500.0 * (f[..., 0] - f[..., 1]),
                     200.0 * (f[..., 1] - f[..., 2])), axis=-1)


def _xyz_to_ycxcz(np, xyz):
    scaled = xyz / np.array(ILLUMINANT)
    return np.stack((116.0 * scaled[..., 1] - 16.0, 500.0 * (scaled[..., 0] - scaled[..., 1]),
                     200.0 * (scaled[..., 1] - scaled[..., 2])), axis=-1)


def _ycxcz_to_xyz(np, ycxcz):
    y = (ycxcz[..., 0] + 16.0) / 116.0
    x = y + ycxcz[..., 1] / 500.0
    z = y - ycxcz[..., 2] / 200.0
    return np.stack((x, y, z), axis=-1) * np.array(ILLUMINANT)


def _hunt_hyab(np, ref_lab, test_lab):
    """Hunt-adjusted HyAB distance between two CIELab images (or pixels)."""
    def hunt(lab):
        return np.stack((lab[..., 0], 0.01 * lab[..., 0] * lab[..., 1],
                         0.01 * lab[..., 0] * lab[..., 2]), axis=-1)
    a, b = hunt(ref_lab), hunt(test_lab)
    return (np.abs(a[..., 0] - b[..., 0])
            + np.sqrt((a[..., 1] - b[..., 1]) ** 2 + (a[..., 2] - b[..., 2]) ** 2))


def _correlate(np, data, weights, axis):
    """out[i] = sum_k w[k] * data[clamp(i + k - r)] along axis (edge replicated)."""
    radius = len(weights) // 2
    pad = [(0, 0)] * data.ndim
    pad[axis] = (radius, radius)
    padded = np.pad(data, pad, mode='edge')
    length = data.shape[axis]
    out = np.zeros(data.shape, dtype=np.float64)
    for k, weight in enumerate(weights):
        index = [slice(None)] * data.ndim
        index[axis] = slice(k, k + length)
        out += weight * padded[tuple(index)]
    return out


def _spatial_filters(np, ppd):
    radius = int(math.ceil(3.0 * math.sqrt(max(CSF_B1 + CSF_B2) / (2.0 * math.pi ** 2)) * ppd))
    x2 = (np.arange(-radius, radius + 1) / ppd) ** 2

    def gaussian(a, b):
        return a * math.sqrt(math.pi / b) * np.exp(-math.pi ** 2 * x2 / b)

    def gaussian_sqrt(a, b):
        return math.sqrt(a * math.sqrt(math.pi / b)) * np.exp(-math.pi ** 2 * x2 / b)
    y_filter = gaussian(CSF_A1[0], CSF_B1[0])
    cx_filter = gaussian(CSF_A1[1], CSF_B1[1])
    cz1 = gaussian_sqrt(CSF_A1[2], CSF_B1[2])
    cz2 = gaussian_sqrt(CSF_A2[2], CSF_B2[2])
    norm = 1.0 / math.sqrt(cz1.sum() ** 2 + cz2.sum() ** 2)
    return y_filter / y_filter.sum(), cx_filter / cx_filter.sum(), cz1 * norm, cz2 * norm


def _feature_filters(np, ppd):
    std = 0.5 * GW * ppd
    radius = int(math.ceil(3.0 * std))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    g = np.exp(-(x * x) / (2.0 * std * std))
    dg = -x * g
    ddg = (x * x / (std * std) - 1.0) * g
    g = g / g.sum()
    dg = np.where(dg > 0, dg / dg[dg > 0].sum(), dg / -dg[dg < 0].sum())
    ddg = np.where(ddg > 0, ddg / ddg[ddg > 0].sum(), ddg / -ddg[ddg < 0].sum())
    return g, dg, ddg


def _max_distance(np):
    labs = [_xyz_to_lab(np, _rgb_to_xyz(np, np.array(rgb, dtype=np.float64)))
            for rgb in ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0))]
    return float(_hunt_hyab(np, labs[0], labs[1]) ** GQC)


def _color_error(np, ref, test, ppd):
    y_f, cx_f, cz1, cz2 = _spatial_filters(np, ppd)
    cmax = _max_distance(np)
    pccmax = GPC * cmax

    def filtered(image):
        across = (_correlate(np, image[..., 0], y_f, 1), _correlate(np, image[..., 1], cx_f, 1),
                  _correlate(np, image[..., 2], cz1, 1), _correlate(np, image[..., 2], cz2, 1))
        return np.stack((_correlate(np, across[0], y_f, 0), _correlate(np, across[1], cx_f, 0),
                         _correlate(np, across[2], cz1, 0) + _correlate(np, across[3], cz2, 0)), axis=-1)

    def to_lab(ycxcz):
        rgb = np.clip(_xyz_to_rgb(np, _ycxcz_to_xyz(np, ycxcz)), 0.0, 1.0)
        return _xyz_to_lab(np, _rgb_to_xyz(np, rgb))
    diff = _hunt_hyab(np, to_lab(filtered(ref)), to_lab(filtered(test))) ** GQC
    return np.where(diff < pccmax, diff * (GPT / pccmax),
                    GPT + ((diff - pccmax) / (cmax - pccmax)) * (1.0 - GPT))


def _features(np, y_norm, filters):
    g, dg, ddg = filters
    dx = _correlate(np, _correlate(np, y_norm, dg, 1), g, 0)
    ddx = _correlate(np, _correlate(np, y_norm, ddg, 1), g, 0)
    dy = _correlate(np, _correlate(np, y_norm, g, 1), dg, 0)
    ddy = _correlate(np, _correlate(np, y_norm, g, 1), ddg, 0)
    return np.sqrt(dx * dx + dy * dy), np.sqrt(ddx * ddx + ddy * ddy)


def _array(np, image):
    if not isinstance(image, Image):
        raise ValueError('flip.image_required')
    if image.width * image.height > MAX_PIXELS:
        raise ValueError('flip.size')
    raw = np.frombuffer(image.rgba, dtype=np.uint8).reshape(image.height, image.width, 4)
    return _linear(np, raw[..., :3].astype(np.float64) / 255.0)


def error_map(reference, candidate, *, ppd=DEFAULT_PPD):
    """LDR-FLIP error image in [0, 1] (numpy array, height x width), 0 = identical."""
    np = _numpy()
    if (type(ppd) not in (int, float) or isinstance(ppd, bool) or not math.isfinite(ppd)
            or not 1.0 <= ppd <= 500.0):
        raise ValueError('flip.ppd')
    if not isinstance(reference, Image) or not isinstance(candidate, Image):
        raise ValueError('flip.image_required')
    if (reference.width, reference.height) != (candidate.width, candidate.height):
        raise ValueError('flip.dimensions')
    ref_ycc = _xyz_to_ycxcz(np, _rgb_to_xyz(np, _array(np, reference)))
    test_ycc = _xyz_to_ycxcz(np, _rgb_to_xyz(np, _array(np, candidate)))
    colour = _color_error(np, ref_ycc, test_ycc, ppd)
    filters = _feature_filters(np, ppd)
    ref_edge, ref_point = _features(np, ref_ycc[..., 0] / 116.0 + 16.0 / 116.0, filters)
    test_edge, test_point = _features(np, test_ycc[..., 0] / 116.0 + 16.0 / 116.0, filters)
    feature = (np.maximum(np.abs(ref_edge - test_edge), np.abs(ref_point - test_point))
               / math.sqrt(2.0)) ** GQF
    return np.clip(colour, 0.0, None) ** (1.0 - feature)


def heatmap(errors):
    """Magma-coloured RGBA Image of an error map (values clamped to [0, 1])."""
    np = _numpy()
    anchors = np.array(MAGMA, dtype=np.float64)
    position = np.clip(errors, 0.0, 1.0) * (len(MAGMA) - 1)
    low = np.floor(position).astype(np.int64)
    high = np.minimum(low + 1, len(MAGMA) - 1)
    frac = (position - low)[..., None]
    rgb = np.rint(anchors[low] * (1.0 - frac) + anchors[high] * frac).astype(np.uint8)
    height, width = errors.shape
    rgba = np.concatenate((rgb, np.full((height, width, 1), 255, dtype=np.uint8)), axis=-1)
    return Image(width, height, rgba.tobytes())


def metric(reference, candidate, *, ppd=DEFAULT_PPD):
    np = _numpy()
    errors = error_map(reference, candidate, ppd=ppd)
    return {'mean_flip': float(errors.mean()), 'max_flip': float(errors.max()),
            'p95_flip': float(np.percentile(errors, 95)), 'pixels': int(errors.size)}


def compare(reference, candidate, *, max_mean=MAX_MEAN_FLIP, ppd=DEFAULT_PPD):
    """reference/candidate: {view: image bytes}. Pass when every view's mean FLIP error
    is at most max_mean (provisional review budget)."""
    if (type(max_mean) not in (int, float) or isinstance(max_mean, bool)
            or not math.isfinite(max_mean) or not 0 <= max_mean <= 1):
        raise ValueError('flip.threshold')
    if set(reference) != set(VIEWS) or set(candidate) != set(VIEWS):
        raise ValueError('flip.six_views_required')
    views = {view: metric(decode_image(reference[view]), decode_image(candidate[view]), ppd=ppd)
             for view in VIEWS}
    return {'schema': SCHEMA, 'metric': 'ldr_flip_mean', 'max_mean': max_mean, 'ppd': ppd,
            'pass': all(v['mean_flip'] <= max_mean for v in views.values()),
            'views': views, 'engine_verified': False}


def selftest():
    image = Image(2, 2, bytes((10, 10, 10, 255) * 4))
    other = Image(2, 2, bytes((250, 250, 250, 255) * 4))
    if metric(image, image)['mean_flip'] != 0.0 or metric(image, other)['mean_flip'] <= 0.1:
        raise AssertionError('flip selftest')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--views', type=Path, help='directory of six candidate views')
    parser.add_argument('--reference', type=Path, help='directory of six reference views')
    parser.add_argument('--max-mean', type=float, default=MAX_MEAN_FLIP)
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest()
            print('{"valid": true}')
            return 0
        if not (args.views and args.reference):
            parser.error('--views and --reference (or --selftest) required')
        from tools.assets import render_check
        report = compare(render_check.read_views(args.reference), render_check.read_views(args.views),
                         max_mean=args.max_mean)
        print(json.dumps({'valid': report['pass'], 'report': report}, sort_keys=True))
        return 0 if report['pass'] else 1
    except (Refusal, ValueError, OSError) as exc:
        print(json.dumps({'valid': False, 'reason': str(exc) if isinstance(exc, (Refusal, ValueError)) else 'flip.io'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
