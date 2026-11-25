"""Bounded offline scoring of pre-rendered, fixed-scale asset candidates.

No renderer/native process is launched. An external agent/lead renders each candidate before
submitting it; max_renders charges every submitted PNG (including retries).
The wall budget covers this scoring invocation, not earlier Blender work. A
lead rendering driver must also bound Blender by its remaining render deadline.

Each directory contains views.json:
 {"schema":"asset-views.v1", "projection":"orthographic", "background":"black",
  "metres_per_pixel":0.001, "views":{"front":"front.png", "side":"side.png",
  "top":"top.png", "three_quarter":"three_quarter.png"},
  "polycounts":{"0":1000,"1":500}}
Reference uses lod_budgets instead of polycounts, and also has
 "palette":["palette.png"],
 "thresholds":{"silhouette_iou":0.92,"edge_f1":0.8,"palette_delta_e":12}.
Edge/palette thresholds are provisional examples; require explicit calibration.
polycounts are triangle counts from the mesh exporter, not inferred from PNGs.
Camera orientation, origin and fixed scale must match; no alignment/resizing.
Outputs stay under build/. Offline evidence only: engine_verified is always false.
"""
import argparse
import json
import math
import multiprocessing
from pathlib import Path
import time

from tools.assets import blender_runner, render_check, visual_diff
from tools.assets.pbr_pack import decode_png
from tools.assets.provenance import Refusal, load_json, read_regular

VIEWS = ('front', 'side', 'top', 'three_quarter')
MAX_JSON_BYTES = 65536


class Deadline(TimeoutError):
    pass


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def read_bounded(directory, name, limit):
    data = read_regular(directory, name)
    if len(data) > limit:
        raise ValueError('score.input_size')
    return data


def read_manifest(directory, *, reference=False):
    directory = Path(directory)
    doc = load_json(read_bounded(directory, 'views.json', MAX_JSON_BYTES))
    common = {'schema', 'projection', 'background', 'metres_per_pixel', 'views'}
    fields = {'lod_budgets', 'palette', 'thresholds'} if reference else {'polycounts'}
    if (not isinstance(doc, dict) or set(doc) != common | fields
            or doc['schema'] != 'asset-views.v1' or doc['projection'] != 'orthographic'
            or doc['background'] != 'black' or not positive(doc['metres_per_pixel'])
            or not isinstance(doc['views'], dict) or set(doc['views']) != set(VIEWS)):
        raise ValueError('score.manifest')
    counts = doc['lod_budgets' if reference else 'polycounts']
    if (not isinstance(counts, dict) or not 1 <= len(counts) <= 64
            or any(not isinstance(k, str) or not k or type(v) is not int
                   or not (1 if reference else 0) <= v <= 1_000_000_000
                   for k, v in counts.items())):
        raise ValueError('score.lod_counts')
    if reference:
        thresholds = doc['thresholds']
        if (not isinstance(thresholds, dict)
                or set(thresholds) != {'silhouette_iou', 'edge_f1', 'palette_delta_e'}
                or any(not positive(v) for v in thresholds.values())
                or thresholds['silhouette_iou'] > 1 or thresholds['edge_f1'] > 1
                or not isinstance(doc['palette'], list) or not 1 <= len(doc['palette']) <= 16):
            raise ValueError('score.reference_settings')
    return doc


def read_png(directory, name):
    if not isinstance(name, str) or Path(name).suffix != '.png':
        raise ValueError('score.png_required')
    return decode_png(read_bounded(Path(directory), name, render_check.MAX_VIEW_BYTES))


def score(reference, candidate, *, check_deadline=lambda: None):
    """Score one directory pair without Blender; all scores are deterministic."""
    check_deadline()
    ref = read_manifest(reference, reference=True)
    cur = read_manifest(candidate)
    if cur['metres_per_pixel'] != ref['metres_per_pixel']:
        raise ValueError('score.scale_mismatch')
    if set(cur['polycounts']) != set(ref['lod_budgets']):
        raise ValueError('score.lods_mismatch')
    thresholds = ref['thresholds']
    palette = []
    for name in ref['palette']:
        check_deadline()
        palette.append(read_png(reference, name))
    views, metrics = {}, []
    for view in VIEWS:
        check_deadline()
        a, b = read_png(reference, ref['views'][view]), read_png(candidate, cur['views'][view])
        masks = render_check.black_silhouette(a), render_check.black_silhouette(b)
        values = {'silhouette_iou': render_check.iou(*masks),
                  'edge_f1': render_check.edge_f1(a, b),
                  'palette_delta_e': visual_diff.palette_distance([b], palette)}
        views[view] = values
        for name, value in values.items():
            # Positive deficit fails; normalize for comparable actionable ranking.
            deficit = ((value / thresholds[name] - 1) if name == 'palette_delta_e'
                       else (thresholds[name] - value) / thresholds[name])
            metrics.append({'view': view, 'metric': name, 'value': value,
                            'threshold': thresholds[name], 'deficit': deficit})
    lods = {}
    for lod, budget in sorted(ref['lod_budgets'].items()):
        count = cur['polycounts'][lod]
        lods[lod] = {'triangles': count, 'budget': budget, 'pass': count <= budget}
        metrics.append({'view': None, 'lod': lod, 'metric': 'polycount',
                        'value': count, 'threshold': budget, 'deficit': count / budget - 1})
    check_deadline()
    worst = max(metrics, key=lambda row: row['deficit'])
    return {'schema': 'asset-score.v1', 'engine_verified': False,
            'pass': worst['deficit'] <= 0, 'views': views, 'lods': lods,
            'worst': worst, 'metrics': metrics}


def _score_worker(connection, reference, candidate):
    try:
        connection.send((True, score(reference, candidate)))
    except (OSError, ValueError):
        connection.send((False, 'score.refused'))
    finally:
        connection.close()


def score_bounded(reference, candidate, seconds):
    """A cancellable Python-only worker enforces the remaining wall deadline.

    Spawn avoids inheriting renderer state. No Blender/native tools are started.
    """
    context = multiprocessing.get_context('spawn')
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_score_worker, args=(send, reference, candidate))
    started = time.monotonic()
    try:
        process.start()
        send.close()
        if not receive.poll(max(0, seconds - (time.monotonic() - started))):
            raise Deadline('score.wall_budget')
        try:
            valid, result = receive.recv()
        except EOFError:
            raise ValueError('score.worker_failed') from None
        if not valid:
            raise ValueError(result)
        return result
    finally:
        receive.close()
        send.close()
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join()


def run_loop(reference, candidates, *, max_iterations=6, max_seconds=120,
             max_renders=24, clock=time.monotonic, scorer=None):
    """Evaluate successive pre-rendered edits, stopping after two stale rounds.

    Improvement means any normalized deficit drops by > .01 relative to its
    best prior value. Best candidate minimizes worst deficit, then mean deficit;
    ties keep the earliest candidate. Rendering is deliberately outside this tool.
    No more than max_renders PNG submissions are admitted, four per iteration.
    Default scoring runs in a cancellable Python child with the remaining wall
    deadline. Injected scorers must honor check_deadline. An over-budget result
    can never pass. Does not launch or cancel external rendering processes.
    """
    if (type(max_iterations) is not int or not 1 <= max_iterations <= 100
            or type(max_renders) is not int or not 0 <= max_renders <= 400
            or not positive(max_seconds)):
        raise ValueError('score.budget')
    if not isinstance(candidates, (list, tuple)):
        raise ValueError('score.candidate_sequence')
    deadline = clock() + max_seconds
    def check():
        if clock() >= deadline:
            raise Deadline('score.wall_budget')
    reports, best, best_key, prior = [], None, None, None
    stale = renders = 0
    reason = 'candidates_exhausted'
    iterator = iter(candidates)
    while True:
        if len(reports) >= max_iterations:
            reason = 'iteration_budget'
            break
        if renders + len(VIEWS) > max_renders:
            reason = 'render_budget'
            break
        try:
            check()
            candidate = next(iterator)
            renders += len(VIEWS)
            report = (score_bounded(reference, candidate, max(0, deadline-clock()))
                      if scorer is None else scorer(reference, candidate, check_deadline=check))
            check()
        except StopIteration:
            break
        except Deadline:
            reason = 'wall_budget'
            break
        reports.append(report)
        deficits = [m['deficit'] for m in report['metrics']]
        key = (max(deficits), sum(deficits)/len(deficits))
        if best_key is None or key < best_key:
            best, best_key = len(reports), key
        if report['pass']:
            reason = 'pass'
            break
        if prior is None:
            prior = deficits
        else:
            if len(prior) != len(deficits):
                raise ValueError('score.metric_set_changed')
            stale = 0 if any(a-b > .01 for a, b in zip(prior, deficits)) else stale + 1
            prior = [min(a, b) for a, b in zip(prior, deficits)]
            if stale >= 2:
                reason = 'no_improvement'
                break
    selected = reports[best-1] if best is not None else None
    return {'schema': 'asset-score-loop.v1', 'engine_verified': False,
            'pass': reason == 'pass', 'stop_reason': reason,
            'iterations': len(reports), 'renders_charged': renders,
            'best_iteration': best, 'worst': selected['worst'] if selected else None,
            'budgets': {'iterations': max_iterations, 'seconds': max_seconds, 'renders': max_renders},
            'reports': reports}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, nargs='+', required=True)
    parser.add_argument('--max-iterations', type=int, default=6)
    parser.add_argument('--max-seconds', type=float, default=120)
    parser.add_argument('--max-renders', type=int, default=24)
    parser.add_argument('--out', type=Path, required=True, help='fresh JSON file under build/')
    args = parser.parse_args(argv)
    try:
        report = run_loop(args.reference, args.candidates, max_iterations=args.max_iterations,
                          max_seconds=args.max_seconds, max_renders=args.max_renders)
        directory = blender_runner.build_directory(args.out.parent)
        target = directory / args.out.name
        with target.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n')
        print(json.dumps(report, sort_keys=True, allow_nan=False))
        return 0 if report['pass'] else 1
    except (OSError, ValueError, Refusal, blender_runner.BlenderRefusal):
        # Never echo local paths, manifest contents or private image names.
        print(json.dumps({'pass': False, 'engine_verified': False, 'reason': 'score.refused'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
