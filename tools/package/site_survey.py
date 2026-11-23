"""Site survey: probe input writer and result importer (wh-sites W2, owner 2026-11-22).

Why: composed sites need terrain, surface and obstacle facts that offline data lacks (sites-design.md 2.2,
2.6). The diag-only probe mods/HollowCountry/scripts/4_World/Debug/HCSiteSurveyProbe.c samples them inside
the engine; this tool writes its input and imports its result. Offline numbers here never establish DayZ
behaviour: the imported data is diag evidence for the planner (W4 composer, W5 validator), nothing more.

Commands (read-only unless named; all deterministic; `agent-run --memory 2G -- python3 -B -m tools.package.site_survey`):
  candidates   write config/sites/survey/candidates.json + format.json from the committed road graph
               [--max-candidates N] [--min-spacing M] [--straight-spacing M] [--road-spacing M] [--extra FILE]
  write-input  write the probe input JSON (outside the repo; it may carry class names) --out PATH
               [--pieces FILE] [--calibrate-file FILE --calibrate-at X,Z] [--calibrate-spacing M]
               [--hold-seconds S] [--slice-ms MS] [--units-per-tick N] [--no-survey]
  import       import a probe result into config/sites/survey/ --input PATH --result PATH
  check        verify the committed survey directory (sizes, hashes, shapes); exit 1 on a fault

Run the probe (lead only, DayZDiag or a test server, never Devon's server): copy the input to
$profile:HollowCountry/survey/probe_input.json, start the server with the launch parameter -hcSiteSurvey
(or create the empty file $profile:HollowCountry/survey/arm.flag before boot). The probe waits 30 s, reads the
input, samples a bounded number of work units per tick, and writes $profile:HollowCountry/survey/
probe_result.json (via probe_result.json.part). It prints "[HC SiteSurvey] state=done ..." when finished.
Copy probe_result.json back and run `import`.

Frame: x east, z north, compass yaw (0 = +z, 90 = +x), metres; the same frame as map_overlay.py.

Probe input (JSON; every key is a field of HCSiteSurveyInput in the probe, no others):
  schema 1, kind "hc-site-survey-input", input_id (first 16 hex of sha256 of the canonical content without it)
  grid_m 8, window_m 80, cell_m 4      sample grid spacing, window edge, collision cell edge
  box_height_m 2.5, box_lift_m 0.4     collision box height above the lifted base
  shrink_m 0.2                         pieces are tested with each side shrunk by this
  hold_seconds, slice_ms, units_per_tick   probe pacing (hold = how long calibration objects stay)
  calibrate_x, calibrate_z, calibrate_spacing_m   calibration row origin (row runs along +x)
  roads    flat [x, z, yaw, ...]        road samples (yaw = undirected road axis 0..179)
  centres  flat [x, z, ...]             candidate centres
  pieces   flat [x, z, yaw, hx, hz, h, ...]   hard pieces: centre, yaw (local +z = front), half sizes, height
  piece_ids [str, ...]                  one id per piece
  calibrate [class, ...]                classes to spawn at yaw 0 (names live only in the input, never committed)

Probe result (JSON written by the probe):
  schema, kind "hc-site-survey-result", input_id, world, params{grid_n, cell_n, ...}, done true
  roads        rows [index, "ccc", road_y_dm, ground_y_dm]; ccc = surface legend code at the road point, 2 m left,
               2 m right (0-9a-z index into surface_legend; z = overflow); y in decimetres
  centres      rows {i, h, s, w, t, b, tr}: grid_n x grid_n points, row-major, row 0 = south edge, column 0 = west
               edge, points at centre - window/2 + k * grid_m. h = ground height dm (comma list), s = slope percent
               (comma list), w = string of 0/1/2 (dry/pond/sea), t = surface code string, b / tr = collision bitmaps on
               cell_n x cell_n cells (cell k spans centre - window/2 + k * cell_m): any static geometry / trees and bushes only;
               row-major rows, each row hex digits of 4 cells, high bit first, padded with zeros
  pieces       rows {i, id, y[4 corners + centre, cm], w, spread, hit, n[trees, buildings, other]}; corners are
               back-left, back-right, front-right, front-left; hit = an oriented box, sides shrunk by shrink_m, touches
               static geometry
  calibration  rows {i, x, y, z, spawned} (dm); the spawned objects are deleted after hold_seconds
  surface_legend [engine surface names]; stats{...}

Imported into config/sites/survey/ in the contract of tools/validate/site_rules.py (input 5), kind
"hollow-country-site-survey" version 1; each part replaces its file only when the result carries it; the committed
total stays under 5 MB:
  roads.json   {road_samples: [[x, z, "asphalt|gravel|dirt"]]}  surface at the road point; unclassified names are dropped
  cells.json   {cells: {size_m, samples: [[x, z, slope_pct, water01]]}}  the 8 m grid of every candidate; water01 is 1 for pond or sea
  pieces.json  {pieces: {id: {corners_y [m], center_y, slope_pct, water, collides}}}  slope from the corner heights
  manifest.json  counts, sha256, input ids per part, surface classification, unclassified and dropped counts
The contract has no room for collision bitmaps, grid heights, road height, the two side surfaces, sea versus pond or the
per-category hit tally; those stay in the raw probe result (never committed). candidates.json and format.json are the
probe input data and share the directory. Surface classes: a asphalt, g gravel, d dirt, o other (dropped from roads.json).
"""
import argparse
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SURVEY_DIR = 'config/sites/survey'
ROAD_GRAPH = 'mission/hollow-country/ai/road-graph.compact.json'
SCHEMA = 1
INPUT_KIND = 'hc-site-survey-input'
RESULT_KIND = 'hc-site-survey-result'
SURVEY_KIND = 'hollow-country-site-survey'
SURVEY_VERSION = 1
SURFACE_NAMES = {'a': 'asphalt', 'g': 'gravel', 'd': 'dirt'}
MAX_TOTAL_BYTES = 5 * 1024 * 1024
KINDS = ('junction', 'dead_end', 'straight', 'extra')
KIND_QUOTA = (('dead_end', 0.2), ('junction', 0.45), ('straight', 0.35))
PARAMS = {'grid_m': 8.0, 'window_m': 80.0, 'cell_m': 4.0, 'box_height_m': 2.5, 'box_lift_m': 0.4, 'shrink_m': 0.2}
DEFAULTS = {'max_candidates': 1000, 'min_spacing_m': 150.0, 'straight_spacing_m': 400.0, 'road_spacing_m': 40.0}
PACING = {'hold_seconds': 300.0, 'slice_ms': 4.0, 'units_per_tick': 64}
CODES = '0123456789abcdefghijklmnopqrstuvwxyz'
LEGEND_MAX = 35
# first match wins; engine surface names are unobserved offline, so the importer lists every name it could not place
SURFACE_RULES = (('a', ('asphalt', 'concrete', 'tarmac')), ('g', ('gravel', 'pebbl')),
                 ('d', ('dirt', 'mud', 'soil', 'ground')))
ID_RE = re.compile(r'^[A-Za-z0-9_.:\-]{1,64}$')
CLASS_RE = re.compile(r'^[A-Za-z0-9_]{1,96}$')


class SurveyError(Exception):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def sha256_text(text):
    return hashlib.sha256(text.encode('ascii')).hexdigest()


def r1(value):
    return round(float(value), 1)


# ---------------------------------------------------------------- road graph

def load_graph(repo):
    d = json.loads((Path(repo) / ROAD_GRAPH).read_bytes())
    pos, off, edges = d['Positions'], d['Offsets'], d['Edges']
    count = d['NodeCount']
    nodes = [(pos[3 * i], pos[3 * i + 2]) for i in range(count)]
    nbrs = [sorted(set(edges[off[i]:off[i + 1]]) - {i}) for i in range(count)]
    return nodes, nbrs


def bearing(a, b):
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360.0


def axis_yaw(nodes, nbrs, i):
    """Undirected road axis 0..179 at node i (degree 1: to its neighbour; 3+: the most collinear neighbour pair)."""
    near = nbrs[i]
    if not near:
        return 0
    if len(near) == 1:
        return int(bearing(nodes[i], nodes[near[0]]) % 180.0)
    best = None
    for a in range(len(near)):
        for b in range(a + 1, len(near)):
            diff = abs((bearing(nodes[i], nodes[near[a]]) - bearing(nodes[i], nodes[near[b]]) + 180.0) % 360.0 - 180.0)
            if best is None or diff > best[0]:
                best = (diff, near[a], near[b])
    return int(bearing(nodes[best[1]], nodes[best[2]]) % 180.0)


class Spacer:
    """Greedy minimum-distance filter over a hash grid."""

    def __init__(self, spacing):
        self.spacing, self.cells = float(spacing), defaultdict(list)

    def free(self, x, z):
        s = self.spacing
        cx, cz = int(x // s), int(z // s)
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                for px, pz in self.cells.get((cx + a, cz + b), ()):
                    if (px - x) ** 2 + (pz - z) ** 2 < s * s:
                        return False
        return True

    def add(self, x, z):
        self.cells[(int(x // self.spacing), int(z // self.spacing))].append((x, z))


def thin_nodes(nodes, spacing):
    """Node indices (ascending) with no earlier kept node closer than spacing."""
    spacer, kept = Spacer(spacing), []
    for i, (x, z) in enumerate(nodes):
        if spacer.free(x, z):
            spacer.add(x, z)
            kept.append(i)
    return kept


def road_samples(repo, spacing):
    nodes, nbrs = load_graph(repo)
    return [(r1(nodes[i][0]), r1(nodes[i][1]), axis_yaw(nodes, nbrs, i)) for i in thin_nodes(nodes, spacing)]


def stable_key(x, z):
    return hashlib.sha1(('%d,%d' % (round(x), round(z))).encode('ascii')).hexdigest()


def read_extras(path):
    rows = json.loads(Path(path).read_text())
    if not isinstance(rows, list):
        raise SurveyError('extras must be a JSON list of {"x","z","tag"}')
    out = []
    for row in rows:
        tag = str(row.get('tag', 'extra'))
        if not ID_RE.match(tag) or not all(isinstance(row.get(k), (int, float)) for k in ('x', 'z')):
            raise SurveyError('bad extra row: %r' % (row,))
        out.append((r1(row['x']), r1(row['z']), tag))
    return out


def build_candidates(repo, max_candidates, min_spacing, straight_spacing, extras=()):
    """Rows [x, z, kind_index, yaw(, tag)]; extras first, then dead ends, junctions, straights under quotas."""
    nodes, nbrs = load_graph(repo)
    spacer = Spacer(min_spacing)
    rows = []
    for x, z, tag in extras:
        rows.append([x, z, KINDS.index('extra'), 0, tag])
        spacer.add(x, z)
    if len(rows) > max_candidates:
        raise SurveyError('extras exceed max-candidates')
    pools = {'dead_end': [], 'junction': [], 'straight': []}
    for i, near in enumerate(nbrs):
        if len(near) == 1:
            pools['dead_end'].append(i)
        elif len(near) >= 3:
            pools['junction'].append(i)
    straight = Spacer(straight_spacing)
    for i, near in enumerate(nbrs):
        if len(near) == 2 and straight.free(*nodes[i]):
            straight.add(*nodes[i])
            pools['straight'].append(i)
    allowed = len(rows)
    for kind, share in KIND_QUOTA:
        allowed = max_candidates if kind == KIND_QUOTA[-1][0] else min(max_candidates, allowed + int(max_candidates * share))
        pool = sorted(pools[kind], key=lambda i: stable_key(*nodes[i]))
        for i in pool:
            if len(rows) >= allowed:
                break
            x, z = nodes[i]
            if spacer.free(x, z):
                spacer.add(x, z)
                rows.append([round(x), round(z), KINDS.index(kind), axis_yaw(nodes, nbrs, i)])
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows


def format_doc():
    return {'schema': SCHEMA, 'params': PARAMS, 'pacing_defaults': PACING, 'kinds': list(KINDS),
            'candidate_row': ['x', 'z', 'kind_index', 'road_yaw', 'tag?'],
            'surface_rules': [[cls, list(words)] for cls, words in SURFACE_RULES], 'legend_codes': CODES,
            'grid_n': grid_n(), 'cell_n': cell_n(), 'defaults': DEFAULTS}


def grid_n(params=None):
    p = params or PARAMS
    return int(round(p['window_m'] / p['grid_m'])) + 1


def cell_n(params=None):
    p = params or PARAMS
    return int(round(p['window_m'] / p['cell_m']))


def dump_file(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = canonical(doc) + '\n'
    path.write_text(text, encoding='ascii', newline='\n')
    return text


def cmd_candidates(repo, args):
    extras = read_extras(args.extra) if args.extra else []
    rows = build_candidates(repo, args.max_candidates, args.min_spacing, args.straight_spacing, extras)
    out = Path(repo) / SURVEY_DIR
    doc = {'schema': SCHEMA, 'kinds': list(KINDS), 'road_spacing_m': args.road_spacing,
           'source': ROAD_GRAPH, 'rows': rows}
    size = len(dump_file(out / 'candidates.json', doc))
    dump_file(out / 'format.json', format_doc())
    print('candidates=%d bytes=%d' % (len(rows), size))
    return 0


# ---------------------------------------------------------------- probe input

def read_pieces(path):
    rows = json.loads(Path(path).read_text())
    if not isinstance(rows, list) or len(rows) > 4000:
        raise SurveyError('pieces must be a JSON list of at most 4000 rows')
    ids, flat = [], []
    for row in rows:
        pid = str(row.get('id', ''))
        if not ID_RE.match(pid) or pid in ids:
            raise SurveyError('bad or duplicate piece id: %r' % pid)
        values = [row.get(k) for k in ('x', 'z', 'yaw', 'hx', 'hz', 'h')]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            raise SurveyError('piece %s needs numeric x z yaw hx hz h' % pid)
        if not (0 < values[3] <= 60 and 0 < values[4] <= 60 and 0 < values[5] <= 30):
            raise SurveyError('piece %s half sizes or height out of range' % pid)
        ids.append(pid)
        flat.extend([r1(values[0]), r1(values[1]), r1(values[2] % 360.0), r1(values[3]), r1(values[4]), r1(values[5])])
    return ids, flat


def read_calibrate(path):
    names = json.loads(Path(path).read_text())
    if not isinstance(names, list) or len(names) > 64 or any(not CLASS_RE.match(str(n)) for n in names):
        raise SurveyError('calibrate file must be a JSON list of at most 64 class names')
    return [str(n) for n in names]


def build_input(repo, pieces=None, calibrate=None, calibrate_at=None, calibrate_spacing=30.0, survey=True,
                hold_seconds=None, slice_ms=None, units_per_tick=None):
    survey_dir = Path(repo) / SURVEY_DIR
    doc = json.loads((survey_dir / 'candidates.json').read_text())
    roads, centres = [], []
    if survey:
        for x, z, yaw in road_samples(repo, doc['road_spacing_m']):
            roads.extend([x, z, float(yaw)])
        for row in doc['rows']:
            centres.extend([float(row[0]), float(row[1])])
    ids, flat = pieces if pieces else ([], [])
    names = list(calibrate or [])
    if names and not calibrate_at:
        raise SurveyError('--calibrate-at X,Z is required with --calibrate-file')
    body = dict(PARAMS)
    body.update({'schema': SCHEMA, 'kind': INPUT_KIND,
                 'hold_seconds': float(PACING['hold_seconds'] if hold_seconds is None else hold_seconds),
                 'slice_ms': float(PACING['slice_ms'] if slice_ms is None else slice_ms),
                 'units_per_tick': int(PACING['units_per_tick'] if units_per_tick is None else units_per_tick),
                 'calibrate_x': float(calibrate_at[0]) if names else 0.0,
                 'calibrate_z': float(calibrate_at[1]) if names else 0.0,
                 'calibrate_spacing_m': float(calibrate_spacing if names else 0.0),
                 'roads': roads, 'centres': centres, 'pieces': flat, 'piece_ids': ids, 'calibrate': names})
    body['input_id'] = sha256_text(canonical(body))[:16]
    return body


def cmd_write_input(repo, args):
    at = None
    if args.calibrate_at:
        parts = args.calibrate_at.split(',')
        if len(parts) != 2:
            raise SurveyError('--calibrate-at wants X,Z')
        at = (float(parts[0]), float(parts[1]))
    doc = build_input(repo, read_pieces(args.pieces) if args.pieces else None,
                      read_calibrate(args.calibrate_file) if args.calibrate_file else None, at,
                      args.calibrate_spacing, not args.no_survey, args.hold_seconds, args.slice_ms, args.units_per_tick)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, sort_keys=True, separators=(',', ':')) + '\n', encoding='ascii', newline='\n')
    print('input_id=%s roads=%d centres=%d pieces=%d calibrate=%d bytes=%d' % (
        doc['input_id'], len(doc['roads']) // 3, len(doc['centres']) // 2, len(doc['piece_ids']),
        len(doc['calibrate']), out.stat().st_size))
    return 0


# ---------------------------------------------------------------- result import

def classify_surface(name):
    low = name.lower()
    for cls, words in SURFACE_RULES:
        if any(w in low for w in words):
            return cls
    return 'o'


def legend_class(legend, code):
    index = CODES.find(code)
    if index < 0 or index >= len(legend):
        return 'o'
    return classify_surface(legend[index])


def hex_rows(text, count):
    """Decode bitmap rows (see module docstring) to count x count booleans."""
    width = (count + 3) // 4
    if len(text) != width * count:
        raise SurveyError('bitmap length %d, wanted %d' % (len(text), width * count))
    out = []
    for r in range(count):
        bits = ''.join('{:04b}'.format(int(c, 16)) for c in text[r * width:(r + 1) * width])
        out.append([b == '1' for b in bits[:count]])
    return out


def check_centre(row, gn, cn):
    n, width = gn * gn, (cn + 3) // 4 * cn
    heights = [int(v) for v in row['h'].split(',')] if isinstance(row['h'], str) else list(row['h'])
    slopes = [int(v) for v in row['s'].split(',')] if isinstance(row['s'], str) else list(row['s'])
    if len(heights) != n or len(slopes) != n or len(row['w']) != n or len(row['t']) != n:
        raise SurveyError('centre %s grid lengths do not match %dx%d' % (row['i'], gn, gn))
    if len(row['b']) != width or len(row['tr']) != width:
        raise SurveyError('centre %s bitmap lengths do not match %dx%d cells' % (row['i'], cn, cn))
    if set(row['w']) - set('012'):
        raise SurveyError('centre %s water string has a bad character' % row['i'])
    return heights, slopes


def load_json(path):
    return json.loads(Path(path).read_text())


def slope_of(corners, hx, hz):
    """Steepest edge slope in percent of a piece footprint from its four corner heights (m): BL, BR, FR, FL."""
    bl, br, fr, fl = corners
    run_x, run_z = max(2.0 * hx, 0.1), max(2.0 * hz, 0.1)
    return round(100.0 * max(abs(br - bl) / run_x, abs(fr - fl) / run_x, abs(fl - bl) / run_z, abs(fr - br) / run_z), 1)


def contract_doc(**body):
    doc = {'kind': SURVEY_KIND, 'version': SURVEY_VERSION}
    doc.update(body)
    return doc


def import_result(repo, input_path, result_path):
    """Convert a raw probe result into the contract of tools/validate/site_rules.py (input 5):
    roads.json {road_samples}, cells.json {cells}, pieces.json {pieces}, all kind hollow-country-site-survey.
    Raw facts the contract cannot carry (collision bitmaps, grid heights, road height, side surfaces, sea vs pond) stay
    in the probe result file and are not committed."""
    inp, res = load_json(input_path), load_json(result_path)
    if inp.get('kind') != INPUT_KIND or res.get('kind') != RESULT_KIND or res.get('schema') != SCHEMA:
        raise SurveyError('input or result kind/schema mismatch')
    if res.get('input_id') != inp.get('input_id') or not res.get('done'):
        raise SurveyError('result is not a finished run of this input')
    legend = list(res.get('surface_legend', []))
    if len(legend) > LEGEND_MAX + 1:
        raise SurveyError('surface legend too long')
    params = res.get('params', {})
    gn, cn = grid_n(inp), cell_n(inp)
    if params.get('grid_n') != gn or params.get('cell_n') != cn:
        raise SurveyError('probe grid does not match input parameters')
    survey_dir = Path(repo) / SURVEY_DIR
    manifest_path = survey_dir / 'manifest.json'
    manifest = load_json(manifest_path) if manifest_path.exists() else {'schema': SCHEMA, 'parts': {}}
    outputs = {}
    dropped = {}
    n_roads, n_centres = len(inp['roads']) // 3, len(inp['centres']) // 2
    if n_roads or n_centres:
        if len(res['roads']) != n_roads or len(res['centres']) != n_centres:
            raise SurveyError('row counts differ from the input')
        samples = []
        for k, (i, codes, _road_y, _ground_y) in enumerate(res['roads']):
            if i != k or len(codes) != 3:
                raise SurveyError('road row %d is out of order or malformed' % k)
            surface = SURFACE_NAMES.get(legend_class(legend, codes[0]))
            if surface is None:
                dropped['road_samples_unclassified'] = dropped.get('road_samples_unclassified', 0) + 1
                continue
            x, z = inp['roads'][3 * k:3 * k + 2]
            samples.append([x, z, surface])
        outputs['roads'] = contract_doc(road_samples=samples)
        cells = []
        half = inp['window_m'] / 2.0
        for k, row in enumerate(res['centres']):
            if row['i'] != k:
                raise SurveyError('centre row %d is out of order' % k)
            _heights, slopes = check_centre(row, gn, cn)
            x0, z0 = inp['centres'][2 * k:2 * k + 2]
            for r in range(gn):
                for c in range(gn):
                    at = r * gn + c
                    cells.append([r1(x0 - half + c * inp['grid_m']), r1(z0 - half + r * inp['grid_m']), slopes[at],
                                  1 if row['w'][at] != '0' else 0])
        outputs['cells'] = contract_doc(cells={'size_m': inp['grid_m'], 'samples': cells})
    if inp['piece_ids']:
        if len(res['pieces']) != len(inp['piece_ids']):
            raise SurveyError('piece rows differ from the input')
        pieces = {}
        for k, row in enumerate(res['pieces']):
            if row['i'] != k or row['id'] != inp['piece_ids'][k] or len(row['y']) != 5 or len(row['n']) != 3:
                raise SurveyError('piece row %d does not match the input' % k)
            corners = [v / 100.0 for v in row['y'][:4]]
            hx, hz = inp['pieces'][6 * k + 3:6 * k + 5]
            pieces[row['id']] = {'corners_y': corners, 'center_y': row['y'][4] / 100.0, 'slope_pct': slope_of(corners, hx, hz),
                                 'water': bool(row['w']), 'collides': bool(row['hit'])}
        outputs['pieces'] = contract_doc(pieces=pieces)
    calib = res.get('calibration', [])
    parts = manifest['parts']
    written = {}
    for part, doc in outputs.items():
        text = canonical(doc) + '\n'
        written[part] = text
        rows = len(doc.get('road_samples') or doc.get('pieces') or (doc.get('cells') or {}).get('samples') or [])
        parts[part] = {'input_id': inp['input_id'], 'sha256': sha256_text(text), 'bytes': len(text), 'rows': rows}
    if inp['calibrate']:
        parts['calibration'] = {'input_id': inp['input_id'], 'rows': len(calib),
                                'spawned': sum(1 for c in calib if c.get('spawned'))}
    if 'cells' in written or 'roads' in written:
        manifest['world'] = res.get('world', '')
        manifest['surface_legend'] = legend
        manifest['surface_classes'] = {name: classify_surface(name) for name in legend}
        manifest['unclassified'] = sorted(name for name in legend if classify_surface(name) == 'o')
        manifest['dropped'] = dropped
    total = sum(p.get('bytes', 0) for p in parts.values())
    if total >= MAX_TOTAL_BYTES:
        raise SurveyError('survey data would be %d bytes, over the 5 MB cap; lower --max-candidates' % total)
    for part, text in written.items():
        (survey_dir / (part + '.json')).write_text(text, encoding='ascii', newline='\n')
    dump_file(manifest_path, manifest)
    print('imported=%s bytes=%d unclassified=%d dropped=%s' % (','.join(sorted(written)) or 'calibration-only', total,
                                                              len(manifest.get('unclassified', [])), json.dumps(dropped)))
    return 0


# ---------------------------------------------------------------- committed data

def load_survey(repo=ROOT):
    """Committed survey as site_rules reads it: {'candidates', 'roads', 'cells', 'pieces', 'manifest'} (missing = None)."""
    base = Path(repo) / SURVEY_DIR
    out = {}
    for name in ('candidates', 'roads', 'cells', 'pieces', 'manifest'):
        path = base / (name + '.json')
        out[name] = load_json(path) if path.exists() else None
    return out


def cmd_check(repo, _args):
    base = Path(repo) / SURVEY_DIR
    faults, total = [], 0
    for path in sorted(base.glob('*.json')):
        total += path.stat().st_size
    if total >= MAX_TOTAL_BYTES:
        faults.append('survey directory is %d bytes, cap is under 5 MB' % total)
    if not (base / 'candidates.json').exists() or not (base / 'format.json').exists():
        faults.append('candidates.json and format.json are required')
    else:
        if load_json(base / 'format.json') != json.loads(canonical(format_doc())):
            faults.append('format.json is stale; run candidates')
        doc = load_json(base / 'candidates.json')
        if doc.get('schema') != SCHEMA or any(len(r) not in (4, 5) or r[2] >= len(KINDS) for r in doc['rows']):
            faults.append('candidates.json rows are malformed')
    for part in ('roads', 'cells', 'pieces'):
        if (base / (part + '.json')).exists():
            doc = load_json(base / (part + '.json'))
            if doc.get('kind') != SURVEY_KIND or doc.get('version') != SURVEY_VERSION:
                faults.append('%s.json is not kind %s version %d' % (part, SURVEY_KIND, SURVEY_VERSION))
    manifest_path = base / 'manifest.json'
    if manifest_path.exists():
        for part, info in load_json(manifest_path)['parts'].items():
            path = base / (part + '.json')
            if 'sha256' in info and (not path.exists() or sha256_text(path.read_text()) != info['sha256']):
                faults.append('%s.json does not match the manifest' % part)
    for fault in faults:
        print('FAULT: ' + fault)
    print('survey_bytes=%d faults=%d' % (total, len(faults)))
    return 1 if faults else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--repo', default=str(ROOT))
    sub = parser.add_subparsers(dest='command', required=True)
    cand = sub.add_parser('candidates')
    cand.add_argument('--max-candidates', type=int, default=DEFAULTS['max_candidates'])
    cand.add_argument('--min-spacing', type=float, default=DEFAULTS['min_spacing_m'])
    cand.add_argument('--straight-spacing', type=float, default=DEFAULTS['straight_spacing_m'])
    cand.add_argument('--road-spacing', type=float, default=DEFAULTS['road_spacing_m'])
    cand.add_argument('--extra')
    inp = sub.add_parser('write-input')
    inp.add_argument('--out', required=True)
    inp.add_argument('--pieces')
    inp.add_argument('--calibrate-file')
    inp.add_argument('--calibrate-at')
    inp.add_argument('--calibrate-spacing', type=float, default=30.0)
    inp.add_argument('--hold-seconds', type=float)
    inp.add_argument('--slice-ms', type=float)
    inp.add_argument('--units-per-tick', type=int)
    inp.add_argument('--no-survey', action='store_true', help='pieces/calibration only: no roads or centres')
    imp = sub.add_parser('import')
    imp.add_argument('--input', required=True)
    imp.add_argument('--result', required=True)
    sub.add_parser('check')
    args = parser.parse_args(argv)
    try:
        if args.command == 'candidates':
            return cmd_candidates(args.repo, args)
        if args.command == 'write-input':
            return cmd_write_input(args.repo, args)
        if args.command == 'import':
            return import_result(args.repo, args.input, args.result)
        return cmd_check(args.repo, args)
    except (SurveyError, OSError, ValueError, KeyError) as exc:
        print('site_survey: %s' % exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
