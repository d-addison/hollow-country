"""Site composer (offline): candidates + survey + archetypes + class geometry -> composed map-overlay layers.

    python3 -B -m tools.package.site_composer plan   [--report FILE] [--accept-unmeasured KEY,KEY]
    python3 -B -m tools.package.site_composer pieces --out FILE      # missing survey boxes, for site_survey write-input
    python3 -B -m tools.package.site_composer write                  # layers + profile (refuses while pieces are pending)
    python3 -B -m tools.package.site_composer check                  # rebuild and compare with the committed layers

What it does, per candidate of config/sites/survey/candidates.json (stable sha order): for every archetype with a
placeable frame it builds the frame (road tangent or approach), evaluates the location predicates, places each part
with its operator, derives the yaw from `align`/`faces` and the class front, makes the guard slots, and then runs the
real rule engine (tools.validate.site_rules R1-R5, R7, R8) on the result. The first archetype that passes and keeps
R6 (spacing, 1 km cell, max_per_map, totals) is placed. Nothing is relaxed: every candidate that is not placed gets
one binding rule (R1-R8, MO = map_overlay clearance, calibration_pending, unmeasured, validator_gap, pending) and the
report prints the count per rule. A missing input makes the composer refuse with the reasons; it never skips.

Two passes over the survey: a placed site whose hard pieces have no survey entry yet is `pending`. `pieces` writes
the request for exactly those boxes (the `--pieces` file of tools.package.site_survey write-input); after the native
probe and `site_survey import` the plan is re-run. `write` refuses while any piece is pending.

Determinism (R8): every choice is seeded by a sha256 of stable text (candidate position, archetype, part, index),
positions and yaw are rounded to 0.1, layers are written with sorted keys, so a rebuild is byte-identical.
`rebuild_bytes(root)` is the hook tools.validate.site_rules calls for that comparison.
"""
import argparse
import copy
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.package import map_overlay
from tools.validate import site_rules as sr

ROOT = Path(__file__).resolve().parents[2]
LAYER_DIR = 'config/map-overlays/layers'
PROFILE = 'config/map-overlays/profile.json'
SURVEY_DIR = 'config/sites/survey'
LAYER_PREFIX = 'composed-'
SCHEMA = 1
HALF = sr.ROAD_WIDTH_M / 2.0
ROUND = 1
PIECE_ROWS_MAX = 4000
RETAIN_ZONE_M = 400.0
JUNCTION_STEP_M = 14.0
APPROACH_OFFSETS = (22.0, 30.0, 36.0)
APPROACH_TRIES = 4
FRAME_RULES = {
    'road': ('toward_settlement', 'into_town', 'toward_protected', 'travel_direction', 'toward_larger_road'),
    'approach': ('toward_road_access', 'toward_dirt_road', 'from_road_into_camp', 'along_access_track'),
}
# location keys the survey and stock cannot measure (no tree, height or view data): the archetype is excluded
# unless the lead names the key with --accept-unmeasured (recorded in the layer metadata).
UNMEASURED_KEYS = ('cover_within_m', 'tree_free_radius_m', 'forest_edge', 'hidden_from_road', 'crest',
                   'highest_flat_within_m', 'water_m_max', 'slope_pct')
NEVER_BYPASS = ('frame_view', 'frame_fall_line', 'frame_building', 'op_on_slope', 'reverse_slope')
OWN_KEYS = ('at_junction', 'base_m', 'near_any', 'medical_building_m', 'no_vanilla_within_m', 'road_access_m_max',
            'min_chain_m', 'bend_or_grade', 'prefer_water_m')
STAGES = ('static', 'R1', 'R6', 'R2', 'R3', 'R4', 'R5', 'R7', 'R8', 'MO', 'pending', 'placed')
GAP_FACES = re.compile(r"faces '(\w+)' but no object of part '(\w+)' exists")
LITTER_CLEAR_M = 1.3
LITTER_DOOR_M = 2.3


class Refusal(Exception):
    """A required input is missing: the composer stops and lists every reason."""

    def __init__(self, reasons):
        super().__init__('; '.join(reasons))
        self.reasons = list(reasons)


class Reject(Exception):
    """One candidate/archetype attempt failed on a named rule."""

    def __init__(self, rule, text):
        super().__init__('%s %s' % (rule, text))
        self.rule, self.text = rule, text


# ---------------------------------------------------------------- small helpers

def H(*parts):
    digest = hashlib.sha256('|'.join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:8], 'big')


def U(*parts):
    return H(*parts) / float(1 << 64)


def rnd(v):
    return round(float(v), ROUND) + 0.0


def canon(doc):
    return (json.dumps(doc, indent=1, sort_keys=True) + '\n').encode()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def sinr(deg):
    return math.sin(math.radians(deg))


def cosr(deg):
    return math.cos(math.radians(deg))


def bearing_of(ax, az, bx, bz):
    return sr.bearing(bx - ax, bz - az)


class Index:
    """Grid index over (x, z, payload) points with a ring-search nearest."""

    def __init__(self, points, cell=250.0):
        self.cell = cell
        self.grid = defaultdict(list)
        for p in points:
            self.grid[(int(p[0] // cell), int(p[1] // cell))].append(p)

    def within(self, x, z, radius):
        r = int(radius // self.cell) + 1
        cx, cz = int(x // self.cell), int(z // self.cell)
        out = []
        for i in range(cx - r, cx + r + 1):
            for j in range(cz - r, cz + r + 1):
                for p in self.grid.get((i, j), ()):
                    if math.hypot(p[0] - x, p[1] - z) <= radius:
                        out.append(p)
        return out

    def nearest(self, x, z, limit=6000.0):
        cx, cz = int(x // self.cell), int(z // self.cell)
        best = None
        for r in range(int(limit // self.cell) + 2):
            for i in range(cx - r, cx + r + 1):
                for j in range(cz - r, cz + r + 1):
                    if max(abs(i - cx), abs(j - cz)) != r:
                        continue
                    for p in self.grid.get((i, j), ()):
                        d = math.hypot(p[0] - x, p[1] - z)
                        if best is None or d < best[0]:
                            best = (d, p)
            if best is not None and best[0] <= r * self.cell:
                break
        return best if best is not None and best[0] <= limit else None


class FastSurvey(sr.Survey):
    """Survey with an indexed road-sample lookup (the base class scans every sample)."""

    def __init__(self, base):
        self.__dict__.update(base.__dict__)
        self._road_index = defaultdict(list)
        for r in self.roads:
            self._road_index[(int(r[0] // 64), int(r[1] // 64))].append(r)

    def surface_at(self, x, z, radius=12.0):
        best = None
        for i in range(int(x // 64) - 1, int(x // 64) + 2):
            for j in range(int(z // 64) - 1, int(z // 64) + 2):
                for r in self._road_index.get((i, j), ()):
                    d = math.hypot(r[0] - x, r[1] - z)
                    if d <= radius and (best is None or d < best[0]):
                        best = (d, r[2])
        return None if best is None else best[1]


class FastChecker(sr.Checker):
    """site_rules.Checker whose stock predicates use the world indexes (R4 reads a local stock window)."""

    def __init__(self, inputs, world):
        super().__init__(inputs)
        self.world = world

    def r1_stock(self, site, loc, out):
        x, z = site.origin[0], site.origin[2]
        edge, military = self.world.edge_m(x, z), self.world.military_m(x, z)
        if 'settlement_edge_m' in loc:
            lo, hi = loc['settlement_edge_m']
            if edge is None or not lo <= edge <= hi:
                out.add(site.id, 'R1', 'settlement edge %s m outside %s-%s m' % (sr._r(edge), lo, hi))
        if 'military_m' in loc:
            lo, hi = loc['military_m']
            if military is None or not lo <= military <= hi:
                out.add(site.id, 'R1', 'military base %s m outside %s-%s m' % (sr._r(military), lo, hi))
        for zone in loc.get('not_in') or ():
            if zone == 'military' and military is not None and military < sr.MILITARY_CORE_M:
                out.add(site.id, 'R1', 'inside a military area (%.0f m from a military group)' % military)
            elif zone == 'town_core' and edge is not None and edge < sr.TOWN_CORE_M:
                out.add(site.id, 'R1', 'inside a town core (%.0f m from a house)' % edge)
            elif zone not in ('military', 'town_core'):
                out.add(site.id, 'R1', 'unsupported not_in zone %r' % zone)


class Legacy:
    """What the old layers contribute: zone ids to keep and object positions to stay clear of."""

    def __init__(self, zones=None, points=None):
        self.zones = sorted(zones or [], key=lambda z: z['id'])
        self.points = list(points or [])


class World:
    """Every input the composer reads; the unit tests build it from fixtures."""

    def __init__(self, inputs, candidates, legacy=None, limits=None, raw_geometry=None, survey_digest=''):
        self.inp = inputs
        self.roads = inputs.roads
        if not isinstance(inputs.survey, FastSurvey):
            inputs.survey = FastSurvey(inputs.survey)
        self.survey = inputs.survey
        self.legacy = legacy or Legacy()
        self.limits = map_overlay.limits_of({'limits': limits or {}})
        self.raw = (raw_geometry or {}).get('classes') or {}
        self.survey_digest = survey_digest
        rows = []
        for c in candidates:
            rows.append((float(c[0]), float(c[1]), int(c[2]), float(c[3])))
        self.candidates = sorted(rows, key=lambda c: (H('cand', rnd(c[0]), rnd(c[1])), c[0], c[1]))
        self.houses = Index([(h[1], h[3], h) for h in inputs.settlement_houses()])
        self.military = Index([(m[1], m[3], m) for m in inputs.military_rows()])
        self.fuel = Index([(r[1], r[3], r) for r in inputs.stock if 'FuelStation' in r[0]])
        self.medical = Index([(r[1], r[3], r) for r in inputs.stock if r[0].startswith(('Land_Medical', 'Land_Hospital'))])
        self.stock_idx = Index([(r[1], r[3], r) for r in inputs.stock])
        self.legacy_idx = Index([(p[0], p[1], p) for p in self.legacy.points])
        nodes = inputs.roads.nodes
        self.junction_idx = Index([(nodes[n][0], nodes[n][2], n) for n in inputs.roads.junctions])

    def edge_m(self, x, z):
        hit = self.houses.nearest(x, z)
        return None if hit is None else hit[0]

    def military_m(self, x, z):
        hit = self.military.nearest(x, z)
        return None if hit is None else hit[0]

    def height_of(self, cls):
        b = ((self.raw.get(cls) or {}).get('bounds') or {})
        try:
            if isinstance(b.get('size_m'), list) and len(b['size_m']) == 3:
                h = float(b['size_m'][1])
            else:
                h = float(b['geometry_max_m'][1]) - float(b['geometry_min_m'][1])
        except (TypeError, ValueError, IndexError, KeyError):
            return 2.0
        return min(max(h, 0.1), 30.0)


# ---------------------------------------------------------------- loading

def load_world(root=ROOT, mission=None):
    root = Path(root)
    reasons = []
    cpath = root / SURVEY_DIR / 'candidates.json'
    candidates = []
    if not cpath.is_file():
        reasons.append('candidates missing (%s/candidates.json; run site_survey candidates)' % SURVEY_DIR)
    else:
        candidates = read_json(cpath).get('rows') or []
        if not candidates:
            reasons.append('candidates.json has no rows')
    try:
        inp = sr.load_inputs(root, mission, composed=False)
    except (OSError, ValueError) as exc:
        raise Refusal(reasons + ['inputs unreadable: %s' % type(exc).__name__])
    if inp.roads is None:
        reasons.append('road graph missing (mission/hollow-country/ai/road-graph.compact.json)')
    if inp.geometry is None:
        reasons.append('class geometry missing (config/sites/class-geometry.json)')
    if not inp.archetypes:
        reasons.append('no archetypes under config/sites/archetypes')
    survey_ok = inp.survey is not None
    if not survey_ok or not inp.survey.roads:
        reasons.append('survey road samples missing (%s/roads.json; run site_survey import)' % SURVEY_DIR)
    if not survey_ok or not inp.survey.cells:
        reasons.append('survey cells missing (%s/cells.json; run site_survey import)' % SURVEY_DIR)
    if inp.stock is None:
        reasons.append('stock mapgrouppos.xml not found (pass --mission or set HC_CE_MISSION)')
    if reasons:
        raise Refusal(reasons)
    raw = read_json(root / 'config/sites/class-geometry.json')
    legacy, limits = load_legacy(root)
    digest = hashlib.sha256()
    for name in ('roads', 'cells', 'pieces'):
        path = root / SURVEY_DIR / (name + '.json')
        digest.update(path.read_bytes() if path.is_file() else b'-')
    return World(inp, candidates, legacy, limits, raw, digest.hexdigest()[:16])


def load_legacy(root):
    """(Legacy, profile limits): zone ids and object positions of the enabled non-composed layers."""
    root = Path(root)
    directory = root / 'config/map-overlays'
    if not (directory / 'profile.json').is_file() or not (directory / 'classes.json').is_file():
        return Legacy(), {}
    source = map_overlay.load_source(directory)
    enabled = set(source.profile.get('enabled') or [])
    zones, points = [], []
    for layer in source.layers:
        if layer.get('id') in enabled and not str(layer.get('id')).startswith(LAYER_PREFIX):
            for site in layer.get('sites') or []:
                pos = map_overlay.site_pos(site)
                if isinstance(site, dict) and site.get('zone_id') and isinstance(pos, list) and len(pos) == 3:
                    zones.append({'id': site['zone_id'], 'role': site.get('zone_role'), 'pos': [pos[0], pos[2]]})
            for item in map_overlay.expand_layer(source, layer):
                if isinstance(item, dict) and isinstance(item.get('pos'), list) and len(item['pos']) == 3:
                    points.append((item['pos'][0], item['pos'][2]))
    return Legacy(zones, points), source.profile.get('limits') or {}


# ---------------------------------------------------------------- static analysis of an archetype

def usable(inp, cls, need_front):
    geo = inp.geo(cls)
    if geo is None:
        return 'no_geometry'
    if need_front and not geo.symmetric and (geo.front is None or geo.source == 'calibration_pending'):
        return 'calibration_pending'
    return None


def class_list(part):
    c = part.get('class')
    return [c] if isinstance(c, str) else list(c or [])


class Static:
    """Per-archetype facts that do not depend on the candidate."""

    def __init__(self, world, ident, arch, accept):
        self.id, self.arch = ident, arch
        self.parts = [p for p in arch.get('parts') or [] if isinstance(p, dict) and 'id' in p]
        self.frame_kind = (arch.get('frame') or {}).get('kind')
        self.forward_rule = (arch.get('frame') or {}).get('forward')
        self.loc = arch.get('location') or {}
        self.blocked = None
        self.cmap = {}
        self.variants = [None]
        self.zones = {z['id']: z for z in arch.get('zones') or [] if isinstance(z, dict) and 'id' in z}
        inp = world.inp
        if self.frame_kind not in FRAME_RULES:
            self.blocked = ('unmeasured', 'frame_%s: needs terrain or building data the survey does not carry' %
                            self.frame_kind)
            return
        if self.forward_rule not in FRAME_RULES[self.frame_kind]:
            self.blocked = ('unsupported', 'frame forward %r' % self.forward_rule)
            return
        keys = [k for k in UNMEASURED_KEYS if k in self.loc and k not in accept]
        if keys:
            self.blocked = ('unmeasured', ','.join(keys))
            return
        for z in self.zones.values():
            if z.get('dir') in ('uphill', 'downhill') and 'zone_dir' not in accept:
                self.blocked = ('unmeasured', 'zone_dir:%s' % z['dir'])
                return
        variants = sorted({p['variant'] for p in self.parts if p.get('variant')})
        pending, nogeo, bad = set(), set(), []
        usable_variant = {v: True for v in variants}
        for p in self.parts:
            if p.get('op') == 'on_slope':
                self.blocked = ('unmeasured', 'op_on_slope')
                return
            if p.get('reverse_slope'):
                self.blocked = ('unmeasured', 'reverse_slope')
                return
            if p.get('op') not in sr.OPS:
                self.blocked = ('unsupported', 'operator %r' % p.get('op'))
                return
            need_front = p.get('op') != 'scatter'
            ok = [c for c in class_list(p) if usable(inp, c, need_front) is None]
            self.cmap[p['id']] = ok
            if ok:
                continue
            for c in class_list(p):
                (pending if usable(inp, c, need_front) == 'calibration_pending' else nogeo).add(c)
            if p.get('variant'):
                usable_variant[p['variant']] = False
            elif not p.get('optional'):
                bad.append(p['id'])
        if bad:
            what = []
            if pending:
                what.append('calibration_pending:' + ','.join(sorted(pending)))
            if nogeo:
                what.append('no_geometry:' + ','.join(sorted(nogeo)))
            self.blocked = ('calibration_pending' if pending else 'no_geometry', ' '.join(what))
            return
        self.variants = [None] + [v for v in variants if usable_variant[v]]
        anchors = [p for p in self.parts if p.get('anchor')]
        if len(anchors) != 1:
            self.blocked = ('unsupported', 'archetype declares %d anchors' % len(anchors))

    def part(self, pid):
        return next(p for p in self.parts if p['id'] == pid)

    def sanitised(self, variant, relax_edge):
        """The archetype as the rule engine can read it: only supported predicates, only the chosen variant."""
        a = copy.deepcopy(self.arch)
        loc = {k: v for k, v in self.loc.items() if k in sr.LOCATION_KEYS}
        if isinstance(loc.get('road'), dict):
            loc['road'] = {k: v for k, v in loc['road'].items() if k in sr.ROAD_KEYS}
        if relax_edge:
            loc.pop('settlement_edge_m', None)
        a['location'] = loc
        a['parts'] = [p for p in a['parts'] if not p.get('variant') or p['variant'] == variant]
        return a


# ---------------------------------------------------------------- frames and location

class Frame:
    def __init__(self, kind, origin, forward):
        self.kind, self.origin, self.forward = kind, origin, forward
        self.sin, self.cos = sinr(forward), cosr(forward)

    def pt(self, s, t):
        return self.origin[0] + s * self.sin + t * self.cos, self.origin[2] + s * self.cos - t * self.sin

    def st(self, x, z):
        dx, dz = x - self.origin[0], z - self.origin[2]
        return dx * self.sin + dz * self.cos, dx * self.cos - dz * self.sin


def make_frames(world, st, cand):
    """[(Frame, protected_bearing or None)] for one candidate, in deterministic order (road: one; approach: up to 4)."""
    roads = world.roads
    cx, cz = cand[0], cand[1]
    if st.frame_kind == 'road':
        if st.loc.get('at_junction'):
            hit = world.junction_idx.nearest(cx, cz, 40.0)
            if hit is None:
                raise Reject('R1', 'at_junction: no junction node within 40 m of the candidate')
            node = hit[1][2]
            nbrs = roads.nbrs[node]
            n = nbrs[H('edge', cand[0], cand[1], st.id) % len(nbrs)]
            a, b = roads.nodes[node], roads.nodes[n]
            length = math.hypot(b[0] - a[0], b[2] - a[2])
            step = min(JUNCTION_STEP_M, length / 2.0)
            ox, oz = a[0] + (b[0] - a[0]) * step / length, a[2] + (b[2] - a[2]) * step / length
            toward = sr.bearing(a[0] - ox, a[2] - oz)
        else:
            near = roads.nearest(cx, cz, 60.0)
            if near is None:
                raise Reject('R1', 'no road within 60 m of the candidate')
            ox, oz, toward = near[1][0], near[1][2], None
        ox, oz = rnd(ox), rnd(oz)
        hit = roads.nearest(ox, oz, 10.0)
        if hit is None:
            raise Reject('R1', 'no road at the frame origin')
        tangent, oy = hit[2], hit[1][1]
        desired, protected = toward, None
        rule = st.forward_rule
        if desired is None:
            if rule in ('toward_settlement', 'into_town'):
                h = world.houses.nearest(ox, oz)
                desired = None if h is None else bearing_of(ox, oz, h[1][0], h[1][1])
            elif rule == 'toward_protected':
                m = world.military.nearest(ox, oz)
                desired = None if m is None else bearing_of(ox, oz, m[1][0], m[1][1])
                protected = desired
            elif rule == 'toward_larger_road':
                j = world.junction_idx.nearest(ox, oz)
                desired = None if j is None else bearing_of(ox, oz, j[1][0], j[1][1])
            else:
                desired = tangent if H('dir', cand[0], cand[1], st.id) % 2 else (tangent + 180.0) % 360.0
            if desired is None:
                raise Reject('R1', 'forward rule %s has nothing to point at' % rule)
        elif rule == 'toward_protected':
            m = world.military.nearest(ox, oz)
            protected = None if m is None else bearing_of(ox, oz, m[1][0], m[1][1])
        fwd = tangent if sr.adiff(tangent, desired) <= 90.0 else (tangent + 180.0) % 360.0
        frame = Frame('road', [ox, rnd(oy), oz], rnd(fwd) % 360.0)
        return [(frame, None if protected is None else rnd(protected) % 360.0)]
    # approach: offset from the road point, both sides, hash order
    road = roads.nearest(cx, cz, 60.0)
    if road is None:
        raise Reject('R1', 'no road within 60 m of the candidate')
    options = [(d, side) for d in APPROACH_OFFSETS for side in (1.0, -1.0)]
    options.sort(key=lambda o: H('app', cand[0], cand[1], st.id, o[0], o[1]))
    frames = []
    for d, side in options[:APPROACH_TRIES]:
        ox = rnd(road[1][0] + side * d * cosr(road[2]))
        oz = rnd(road[1][2] - side * d * sinr(road[2]))
        q = roads.nearest(ox, oz, 400.0)
        if q is None:
            continue
        toward_road = bearing_of(ox, oz, q[1][0], q[1][2])
        fwd = toward_road if st.forward_rule in ('toward_road_access', 'toward_dirt_road') else \
            (toward_road + 180.0) % 360.0
        frames.append((Frame('approach', [ox, rnd(q[1][1]), oz], rnd(fwd) % 360.0), None))
    return frames


def own_predicates(world, st, frame):
    """(relax_settlement_edge, reason or None): the location keys the rule engine does not know."""
    loc = st.loc
    ox, oz = frame.origin[0], frame.origin[2]
    relax = False
    base_ok = edge_ok = True
    if 'base_m' in loc:
        lo, hi = loc['base_m']
        d = world.military_m(ox, oz)
        base_ok = d is not None and lo <= d <= hi
    if loc.get('near_any') and 'base_m' in loc and 'settlement_edge_m' in loc:
        lo, hi = loc['settlement_edge_m']
        d = world.edge_m(ox, oz)
        edge_ok = d is not None and lo <= d <= hi
        if not (base_ok or edge_ok):
            return False, 'R1', 'neither a settlement edge %s-%s m nor a base %s-%s m is near' % (
                lo, hi, loc['base_m'][0], loc['base_m'][1])
        relax = True
    elif not base_ok:
        return False, 'R1', 'military base %s m outside %s-%s m' % (sr._r(world.military_m(ox, oz)), *loc['base_m'])
    if 'no_vanilla_within_m' in loc:
        for kind, radius in sorted(loc['no_vanilla_within_m'].items()):
            idx = world.fuel if kind == 'fuel_station' else None
            if idx is None:
                return False, 'R1', 'unsupported no_vanilla_within_m kind %r' % kind
            if idx.within(ox, oz, float(radius)):
                return False, 'R1', 'a vanilla %s lies within %s m' % (kind, radius)
    if 'road_access_m_max' in loc:
        hit = world.roads.nearest(ox, oz, 2000.0)
        if hit is None or hit[0] > loc['road_access_m_max']:
            return False, 'R1', 'road access %s m above %s m' % (sr._r(hit and hit[0]), loc['road_access_m_max'])
    if 'min_chain_m' in (loc.get('road') or {}):
        d = world.roads.nearest_junction(ox, oz)
        need = float(loc['road']['min_chain_m']) / 2.0
        if d is not None and d < need:
            return False, 'R1', 'junction %.0f m away, the chain needs %.0f m each side' % (d, need)
    return relax, None, None


# ---------------------------------------------------------------- placing parts

class Build:
    """Places the parts of one archetype in one frame. Raises Reject on a rule the geometry cannot satisfy."""

    def __init__(self, world, st, site_id, frame, variant, protected):
        self.w, self.inp, self.st = world, world.inp, st
        self.site, self.f, self.variant, self.protected = site_id, frame, variant, protected
        self.parts = {p['id']: p for p in st.parts}
        self.placed = defaultdict(list)
        self.all = []
        self.zones = {}
        self.hard_polys = []
        self.stock_polys = []
        x, z = frame.origin[0], frame.origin[2]
        for _x, _z, row in world.stock_idx.within(x, z, 260.0):
            geo = self.inp.geometry.get(row[0]) if self.inp.geometry else None
            if geo is not None:
                self.stock_polys.append(geo.corners(row[1], row[3], row[4]))

    # -- naming, classes, geometry
    def geo(self, cls):
        return self.inp.geo(cls)

    def poly(self, o):
        return self.geo(o.cls).corners(o.x, o.z, o.yaw)

    def hard(self, cls):
        return self.inp.is_hard(cls)

    def count(self, pid, part):
        want = part.get('count', 1)
        if isinstance(want, int):
            return want
        return want[0] + H('count', self.site, pid) % (want[1] - want[0] + 1)

    def pick(self, pid, n):
        classes = self.st.cmap[pid]
        return classes[H('class', self.site, pid, n) % len(classes)]

    def front_of(self, o):
        geo = self.geo(o.cls)
        if geo.symmetric or geo.front is None:
            return None
        return (o.yaw + geo.front) % 360.0

    def add(self, pid, cls, x, z, yaw, src):
        n = len(self.placed[pid]) + 1
        o = sr.Obj('%s-%s-%d' % (self.site, pid, n), cls, rnd(x), 0.0, rnd(z), rnd(yaw) % 360.0, 'none', pid, src)
        self.placed[pid].append(o)
        self.all.append(o)
        if self.hard(cls):
            self.hard_polys.append((o, self.poly(o)))
        return o

    # -- bearings
    def road_tangent_at(self, x, z):
        hit = self.w.roads.nearest(x, z, 80.0)
        return None if hit is None else hit[2]

    def axis_bearing(self, x, z):
        """Bearing from (x, z) toward the frame axis: the road centreline, else the line through the origin."""
        if self.f.kind == 'road':
            hit = self.w.roads.nearest(x, z, 200.0)
            if hit is not None and hit[0] > 0.3:
                return bearing_of(x, z, hit[1][0], hit[1][2])
        _s, t = self.f.st(x, z)
        if abs(t) < 0.3:
            return (self.f.forward + 90.0) % 360.0
        return (self.f.forward - 90.0) % 360.0 if t > 0 else (self.f.forward + 90.0) % 360.0

    def centre_of(self, ref):
        if ref in (None, 'origin'):
            return self.f.origin[0], self.f.origin[2]
        pool = self.placed.get(ref)
        if not pool:
            raise Reject('R7', 'part %s depends on %s which has no object' % ('?', ref))
        return sum(o.x for o in pool) / len(pool), sum(o.z for o in pool) / len(pool)

    def nearest_of(self, ref, x, z):
        pool = self.placed.get(ref) or []
        return min(pool, key=lambda p: math.hypot(p.x - x, p.z - z)) if pool else None

    def target(self, part, faces, x, z):
        """Bearing an object at (x, z) must face, or None when the target is not available."""
        f = self.f.forward
        if faces == 'forward':
            return f
        if faces == '-forward':
            return (f + 180.0) % 360.0
        if faces == 'axis':
            return self.axis_bearing(x, z)
        if faces in ('of', 'outward'):
            ref = part.get('of')
            near = self.nearest_of(ref, x, z)
            cx, cz = (near.x, near.z) if near is not None else (self.f.origin[0], self.f.origin[2])
            if near is None and ref not in (None, 'origin'):
                return None
            b = bearing_of(x, z, cx, cz)
            return (b + 180.0) % 360.0 if faces == 'outward' else b
        near = self.nearest_of(faces, x, z)
        if near is None:
            return bearing_of(x, z, self.f.origin[0], self.f.origin[2])
        return bearing_of(x, z, near.x, near.z)

    def tol_front(self, cls, op):
        if op == 'row':
            return sr.TOL_ROW
        return sr.TOL_DEFENSIVE if self.inp.role(cls) in sr.DEFENSIVE_ROLES else sr.TOL_SOCIAL

    def constraints(self, pid, part, cls, x, z, jitter=0.0):
        cons = []
        op = part.get('op')
        faces = part.get('faces') or {'facing': 'of', 'ring': 'of'}.get(op)
        if faces is not None:
            b = self.target(part, faces, x, z)
            if b is not None:
                src = faces if faces in ('forward', 'outward') else 'forward' if faces == '-forward' else 'faces'
                cons.append(('front', b, self.tol_front(cls, op), src))
        align = part.get('align')
        if align == 'road':
            t = self.road_tangent_at(x, z)
            if t is None:
                raise Reject('R3', 'aligns to the road but no road within 80 m of %s' % pid)
            cons.append(('axis', t, sr.TOL_ROW + jitter, 'road'))
        elif align == 'anchor':
            anchor = next(p['id'] for p in self.st.parts if p.get('anchor'))
            pool = self.placed.get(anchor)
            if pool and pool[0].part != pid:
                cons.append(('axis', self.long_axis(pool[0]), sr.TOL_ROW + jitter, 'anchor'))
        if part.get('angle_deg') is not None and op != 'in_lane':
            cons.append(('front', (self.f.forward + float(part['angle_deg'])) % 360.0, sr.TOL_ROW, 'road'))
        return cons

    def long_axis(self, o):
        geo = self.geo(o.cls)
        front = o.yaw + (geo.front or 0.0)
        return front % 360.0 if geo.sz >= geo.sx else (front + 90.0) % 360.0

    def solve(self, cls, cons, pid, n):
        geo = self.geo(cls)
        no_front = geo.symmetric or geo.front is None
        f_off = 0.0 if no_front else geo.front
        f0 = geo.front or 0.0
        cands = []
        for kind, val, _tol, src in cons:
            if kind == 'front':
                cands.append((val - f_off, src))
            elif kind == 'yaw':
                cands.append((val, src))
            else:
                y0 = val - f0 - (0.0 if geo.sz >= geo.sx else 90.0)
                cands += [(y0, src), (y0 + 180.0, src)]
        if not cands:
            return U('yaw', self.site, pid, n) * 360.0, 'authored'

        def worst(yaw):
            w = 0.0
            for kind, val, tol, _src in cons:
                if kind == 'front':
                    e = 0.0 if no_front else sr.adiff((yaw + geo.front) % 360.0, val)
                elif kind == 'yaw':
                    e = sr.adiff(yaw, val)
                else:
                    ax = (yaw + f0) % 360.0 if geo.sz >= geo.sx else (yaw + f0 + 90.0) % 360.0
                    e = sr.fold(ax, val)
                w = max(w, e / tol)
            return w
        best = min(range(len(cands)), key=lambda i: (round(worst(cands[i][0]), 6), i))
        return cands[best][0] % 360.0, cands[best][1]

    def put(self, pid, part, x, z, n=None, jitter=0.0, extra=None):
        """One object of a part at (x, z) with the yaw its constraints give."""
        n = len(self.placed[pid]) + 1 if n is None else n
        cls = self.pick(pid, n)
        cons = self.constraints(pid, part, cls, x, z, jitter) + list(extra or [])
        yaw, src = self.solve(cls, cons, pid, n)
        return self.add(pid, cls, x, z, yaw, src)

    def t_range(self, cls, x, z, yaw):
        ts = [self.f.st(px, pz)[1] for px, pz in self.geo(cls).corners(x, z, yaw)]
        return min(ts), max(ts)

    # -- orchestration
    def order(self):
        parts = [p for p in self.st.parts if not p.get('variant') or p['variant'] == self.variant]
        ids = {p['id'] for p in parts}
        anchor = next(p['id'] for p in parts if p.get('anchor'))
        queue = [p['id'] for p in parts if p['id'] != anchor and p.get('op') != 'scatter']
        queue += [p['id'] for p in parts if p.get('op') == 'scatter']
        done, order, pending = set(), [anchor], list(queue)
        done.add(anchor)
        while pending:
            progressed = False
            for pid in list(pending):
                p = self.parts[pid]
                deps = [d for d in (p.get('of'), p.get('stack_on')) if d and d != 'origin']
                if p.get('op') == 'scatter':
                    zone = self.st.zones.get(p.get('zone')) or {}
                    deps = [zone['of']] if zone.get('of') not in (None, 'origin') else []
                if all(d in done or d not in ids for d in deps):
                    order.append(pid)
                    done.add(pid)
                    pending.remove(pid)
                    progressed = True
            if not progressed:
                raise Reject('R7', 'parts %s depend on each other' % ','.join(pending))
        return order

    def run(self):
        for pid in self.order():
            part = self.parts[pid]
            if not self.st.cmap.get(pid):
                continue
            if part.get('optional') and part.get('of') not in (None, 'origin') and not self.placed.get(part['of']):
                continue
            getattr(self, 'op_' + part['op'])(pid, part)
        self.assign_loot()

    # -- operators
    def op_in_lane(self, pid, part):
        if self.f.kind != 'road':
            raise Reject('R2', 'in_lane needs a road frame')
        t = {'right': HALF / 2.0, 'left': -HALF / 2.0}.get(part.get('lane'), 0.0)
        for k in range(self.count(pid, part)):
            n = k + 1
            x, z = self.f.pt(float(part['s']) + 4.0 * k, t)
            jit = float(part.get('jitter_deg', 0.0))
            extra = []
            if part.get('angle_deg') is not None:
                angle = float(part['angle_deg']) + jit * (2.0 * U('jit', self.site, pid, n) - 1.0)
                extra.append(('front', (self.f.forward + angle) % 360.0, sr.TOL_ROW, 'road'))
            elif not part.get('align'):
                extra.append(('axis', self.f.forward, sr.TOL_ROW, 'road'))
            self.put(pid, part, x, z, n, jit, extra)

    def op_across_lane(self, pid, part):
        if self.f.kind != 'road':
            raise Reject('R2', 'across_lane needs a road frame')
        count, gap = self.count(pid, part), float(part.get('gap_m', sr.PASSABLE_M))
        left = count // 2 if count > 1 else 1
        s = float(part['s'])
        cursor = -HALF
        for k in range(count):
            n = k + 1
            cls = self.pick(pid, n)
            cons = [('axis', (self.f.forward + 90.0) % 360.0, sr.TOL_ROW, 'road')]
            x0, z0 = self.f.pt(s, 0.0)
            faces = part.get('faces')
            if faces:
                b = self.target(part, faces, x0, z0)
                if b is not None:
                    cons.append(('front', b, self.tol_front(cls, 'across_lane'), 'forward' if 'forward' in faces
                                 else 'faces'))
            yaw, src = self.solve(cls, cons, pid, n)
            lo, hi = self.t_range(cls, x0, z0, yaw)
            if k == left:
                cursor = cursor + gap - 1.1
            start = cursor + 1.1 if k > 0 else cursor
            x, z = self.f.pt(s, start - lo)
            self.add(pid, cls, x, z, yaw, src)
            cursor = start + (hi - lo)

    def op_shoulder(self, pid, part):
        sign = -1.0 if part.get('side') == 'left' else 1.0
        offset, s = float(part['offset_m']), float(part['s'])
        n = len(self.placed[pid]) + 1
        cls = self.pick(pid, n)
        if self.f.kind != 'road':
            x, z = self.f.pt(s, sign * offset)
            self.put(pid, part, x, z)
            return
        t = sign * (HALF + offset + 2.0)
        yaw = src = None
        for _ in range(3):
            x, z = self.f.pt(s, t)
            cons = self.constraints(pid, part, cls, x, z)
            yaw, src = self.solve(cls, cons, pid, n)
            lo, hi = self.t_range(cls, x, z, yaw)
            near = lo if sign > 0 else -hi
            t += sign * ((HALF + offset) - near)
        x, z = self.f.pt(s, t)
        self.add(pid, cls, x, z, yaw, src)

    def op_offroad(self, pid, part):
        sign = {'left': -1.0, 'right': 1.0}.get(part.get('side'), 0.0)
        x, z = self.f.pt(float(part['s']), sign * float(part.get('offset_m', 0.0)))
        self.put(pid, part, x, z)

    def direction(self, how, ref_obj):
        """Bearing from an object toward the named side of it (front/back/left/right/forward/road_side)."""
        base = self.front_of(ref_obj)
        base = ref_obj.yaw % 360.0 if base is None else base
        if how in ('front', 'forward'):
            return base
        if how in ('back', 'behind'):
            return (base + 180.0) % 360.0
        if how == 'left':
            return (base - 90.0) % 360.0
        if how == 'right':
            return (base + 90.0) % 360.0
        return self.axis_bearing(ref_obj.x, ref_obj.z)

    def op_row(self, pid, part):
        count, spacing = self.count(pid, part), float(part['spacing_m'])
        if part.get('of'):
            cx, cz = self.centre_of(part['of'])
            ref = self.nearest_of(part['of'], cx, cz)
            d = self.direction(part.get('from', 'front'), ref)
            cx, cz = cx + float(part['dist_m']) * sinr(d), cz + float(part['dist_m']) * cosr(d)
            run = (d + 90.0) % 360.0
        else:
            sign = {'left': -1.0, 'right': 1.0}.get(part.get('side'), 0.0)
            cx, cz = self.f.pt(float(part['s']), sign * float(part.get('offset_m', 0.0)))
            run = self.f.forward if part.get('run', 'forward') == 'forward' else (self.f.forward + 90.0) % 360.0
        cls = self.pick(pid, 1)
        yaw, src = self.solve(cls, self.constraints(pid, part, cls, cx, cz), pid, 1)
        for k in range(count):
            off = (k - (count - 1) / 2.0) * spacing
            n = len(self.placed[pid]) + 1
            self.add(pid, self.pick(pid, n), cx + off * sinr(run), cz + off * cosr(run), yaw, src)

    def op_ring(self, pid, part):
        centre = part.get('centre')
        if isinstance(centre, dict):
            sign = {'left': -1.0, 'right': 1.0}.get(centre.get('side'), 0.0)
            cx, cz = self.f.pt(float(centre.get('s', 0.0)), sign * float(centre.get('offset_m', 0.0)))
        elif part.get('of') in (None, 'origin'):
            cx, cz = self.f.origin[0], self.f.origin[2]
        else:
            ref = (self.placed.get(part['of']) or [None])[0]
            if ref is None:
                raise Reject('R7', 'ring %s: part %s has no object' % (pid, part['of']))
            cx, cz = ref.x, ref.z
        mid = {'forward': self.f.forward, 'back': self.f.forward + 180.0, '-forward': self.f.forward + 180.0,
               'left': self.f.forward - 90.0, 'right': self.f.forward + 90.0}.get(part.get('centre_on'),
                                                                                  self.f.forward)
        count, arc, r = self.count(pid, part), float(part['arc_deg']), float(part['r_m'])
        step = 0.0 if count < 2 else (arc / (count - 1) if arc < 360.0 else arc / count)
        for k in range(count):
            a = mid - (arc / 2.0 if count > 1 and arc < 360.0 else 0.0) + k * step
            if count > 1 and arc >= 360.0:
                a = mid + k * step
            self.put(pid, part, cx + r * sinr(a), cz + r * cosr(a))

    def op_facing(self, pid, part):
        ref = (self.placed.get(part['of']) or [None])[0]
        if ref is None:
            raise Reject('R7', 'facing %s: part %s has no object' % (pid, part['of']))
        d = self.direction(part.get('from', 'front'), ref)
        self.put(pid, part, ref.x + float(part['dist_m']) * sinr(d), ref.z + float(part['dist_m']) * cosr(d))

    def op_beside(self, pid, part):
        pool = self.placed.get(part['of']) or []
        if not pool:
            raise Reject('R7', '%s %s: part %s has no object' % (part['op'], pid, part['of']))
        ref = pool[-1] if part.get('instance') == 'last' else pool[0]
        how = 'back' if part['op'] == 'behind' else part.get('side', 'right')
        d = self.direction(how, ref)
        dist = float(part.get('dist_m', 0.0))
        count = self.count(pid, part)
        for k in range(count):
            lat = (k - (count - 1) / 2.0) * (max(self.geo(self.pick(pid, k + 1)).sx, 1.0) + 2.0) if count > 1 else 0.0
            x = ref.x + dist * sinr(d) + lat * sinr(d + 90.0)
            z = ref.z + dist * cosr(d) + lat * cosr(d + 90.0)
            if part.get('stack_on'):
                top = (self.placed.get(part['stack_on']) or [ref])[0]
                x, z = top.x, top.z
            cons = []
            inherit = self.front_of(ref)
            cls = self.pick(pid, k + 1)
            geo = self.geo(cls)
            if inherit is not None and not geo.symmetric and geo.front is not None:
                cons.append(('front', inherit, sr.TOL_INHERIT, 'anchor'))
            else:
                cons.append(('yaw', ref.yaw, sr.TOL_INHERIT, 'anchor'))
            self.put(pid, part, x, z, k + 1, 0.0, cons)

    op_behind = op_beside

    def zone_shape(self, zid):
        z = self.st.zones.get(zid)
        if z is None:
            raise Reject('R4', 'scatter zone %r is not declared' % zid)
        cx, cz = self.centre_of(z.get('of'))
        r = float(z['r_m'])
        shape = z.get('shape', 'disc')
        if shape == 'disc':
            return z, (cx, cz), r, lambda u1, u2: (u1 * 2 * math.pi, math.sqrt(u2) * r * 0.95, cx, cz, None)
        dirs = {'forward': self.f.forward, '-forward': self.f.forward + 180.0, 'left': self.f.forward - 90.0,
                'right': self.f.forward + 90.0}
        d = dirs.get(z.get('dir'))
        if d is None:
            d = self.axis_bearing(cx, cz) if z.get('dir') == 'toward_road' else bearing_of(
                self.f.origin[0], self.f.origin[2], cx, cz)
        d %= 360.0
        if shape == 'cone':
            half = float(z.get('arc_deg', 90.0)) / 2.0
            pts = [(cx, cz)] + [(cx + r * sinr(d + a), cz + r * cosr(d + a)) for a in range(-int(half), int(half) + 1, 5)]
            mx, mz = cx + r / 2.0 * sinr(d), cz + r / 2.0 * cosr(d)
            rad = max(math.hypot(px - mx, pz - mz) for px, pz in pts) + 0.2
            return z, (mx, mz), rad, lambda u1, u2: ((d - half + u1 * 2 * half) * math.pi / 180.0,
                                                      math.sqrt(u2) * r * 0.97, cx, cz, 'cone')
        w = float(z.get('width_m', 6.0))
        mx, mz = cx + r / 2.0 * sinr(d), cz + r / 2.0 * cosr(d)
        rad = math.hypot(r / 2.0, w / 2.0) + 0.2
        return z, (mx, mz), rad, lambda u1, u2: (d, u1 * r * 0.97, cx, cz, ('strip', (u2 - 0.5) * w * 0.9, d))

    def op_scatter(self, pid, part):
        zid = part.get('zone')
        _z, centre, radius, sampler = self.zone_shape(zid)
        self.zones[zid] = {'centre': [rnd(centre[0]), rnd(centre[1])], 'radius_m': rnd(radius + 0.1)}
        want = self.count(pid, part)
        lo = part['count'] if isinstance(part.get('count'), int) else part['count'][0]
        gap = float(part.get('min_gap_m', 0.0)) + 0.2
        doors = []
        for o, _poly in self.hard_polys:
            doors += self.doors_of(o)
        chosen = []
        for k in range(80):
            if len(chosen) >= want:
                break
            u1, u2 = U('sx', self.site, pid, k), U('sz', self.site, pid, k)
            a, rad, ax, az, extra = sampler(u1, u2)
            if extra is None:
                x, zz = ax + rad * math.sin(a), az + rad * math.cos(a)
            elif extra == 'cone':
                x, zz = ax + rad * math.sin(a), az + rad * math.cos(a)
            else:
                _k, lat, d = extra
                x, zz = ax + rad * sinr(d) + lat * sinr(d + 90.0), az + rad * cosr(d) + lat * cosr(d + 90.0)
            x, zz = rnd(x), rnd(zz)
            cls = self.pick(pid, len(chosen) + 1)
            yaw = U('syaw', self.site, pid, k) * 360.0
            poly = self.geo(cls).corners(x, zz, yaw)
            if self.f.kind == 'road' and abs(self.f.st(x, zz)[1]) < HALF + 0.6:
                continue
            if any(math.hypot(x - c.x, zz - c.z) < gap for c in chosen):
                continue
            if any(sr.poly_gap(poly, hp) < LITTER_CLEAR_M for _o, hp in self.hard_polys):
                continue
            if any(sr.poly_point_gap(poly, dx, dz) < LITTER_DOOR_M for dx, dz in doors):
                continue
            if any(sr.poly_gap(poly, sp) < 0.5 for sp in self.stock_polys):
                continue
            chosen.append(self.add(pid, cls, x, zz, yaw, 'authored'))
        if len(chosen) < lo:
            for o in chosen:
                self.all.remove(o)
            self.placed[pid] = []
            raise Reject('R4', 'scatter %s: room for %d of %d litter pieces in zone %s' % (pid, len(chosen), lo, zid))

    def doors_of(self, o):
        ck = sr.Checker(self.inp)
        return ck.doors(o)

    # -- loot and guard slots
    def assign_loot(self):
        rows = []
        for p in self.st.parts:
            if p.get('loot') != 'proto':
                continue
            for o in self.placed.get(p['id'], []):
                if p.get('anchor') or self.inp.kind(o.cls) in ('container', 'tent'):
                    rows.append((0 if p.get('anchor') else 1, o))
        rows.sort(key=lambda r: r[0])
        for _rank, o in rows[:sr.PROTO_ROWS[1]]:
            o.loot = 'proto'
        if not any(o.loot == 'proto' for o in self.all):
            raise Reject('R7', 'no object can carry the proto loot row')

    def guard_slots(self):
        slots = []
        for p in self.st.parts:
            if not p.get('guard_post'):
                continue
            for o in self.placed.get(p['id'], []):
                front = self.front_of(o)
                if front is None:
                    raise Reject('R7', 'guard post %s has no front bearing' % o.id)
                geo = self.geo(o.cls)
                aligned = sr.adiff(front, o.yaw) < 45 or sr.adiff(front, o.yaw + 180) < 45
                half = geo.sz / 2.0 if aligned else geo.sx / 2.0
                depth = half - 1.5
                faces = p.get('faces') or 'forward'
                target = self.target(p, faces, o.x, o.z)
                if target is None:
                    target = front
                slots.append({'part': p['id'], 'pos': [rnd(o.x + depth * sinr(front)), 0.0,
                                                       rnd(o.z + depth * cosr(front))],
                              'facing_deg': rnd(target) % 360.0})
        return slots


# ---------------------------------------------------------------- one attempt

class Result:
    def __init__(self, st, site, objects, pending, zone_pos):
        self.st, self.site, self.objects, self.pending, self.origin = st, site, objects, pending, zone_pos


class Plan:
    def __init__(self, world, accept):
        self.world, self.accept = world, sorted(accept)
        self.results = []
        self.rows = []
        self.statics = {}
        self.gaps = Counter()
        self.retired = []
        self.kept = []
        self.cap_blocked = Counter()

    @property
    def pending(self):
        ids = []
        for r in self.results:
            ids += r.pending
        return ids


def site_id_for(st, cand):
    words = st.id.split('-')
    abbr = ''.join(w[:3] for w in words)[:9]
    return '%s_%06x' % (re.sub('[^a-z0-9]', '', abbr), H('site', rnd(cand[0]), rnd(cand[1]), st.id) % (1 << 24))


def entry_for(site_id, st, frame, protected, build, slots, variant):
    entry = {'id': site_id, 'archetype': st.id,
             'frame': {'kind': frame.kind, 'origin': [frame.origin[0], rnd(frame.origin[1]), frame.origin[2]],
                       'forward_yaw_deg': frame.forward},
             'guard_slots': slots}
    if protected is not None:
        entry['protected_bearing_deg'] = protected
    if build.zones:
        entry['zones'] = build.zones
    if variant:
        entry['variant'] = variant
    return entry


def object_rows(site_id, build, survey):
    rows = []
    for o in build.all:
        piece = survey.pieces.get(o.id)
        y = piece.get('center_y') if isinstance(piece, dict) and isinstance(piece.get('center_y'), (int, float)) \
            else 0.0
        rows.append({'id': o.id, 'class': o.cls, 'pos': [o.x, rnd(y), o.z], 'yaw': o.yaw, 'loot': o.loot,
                     'site': site_id, 'part': o.part, 'customString': 'hcsite:%s:%s' % (site_id, o.part),
                     'ypr': [o.yaw, 0.0, 0.0], 'yaw_source': o.yaw_source})
    return rows


def evaluate(world, st, entry, rows, variant, relax):
    """Run the real rule engine on one composed site; returns (real findings, pending ids, validator gaps)."""
    ox, oz = entry['frame']['origin'][0], entry['frame']['origin'][2]
    inp = copy.copy(world.inp)
    inp.archetypes = {st.id: st.sanitised(variant, relax)}
    inp.stock = [p[2] for p in world.stock_idx.within(ox, oz, 260.0)]
    ck = FastChecker(inp, world)
    site = sr.composed_sites({'sites': [entry], 'objects': rows})[0]
    out = sr.Findings()
    for rule in (ck.r0, ck.r1, ck.r2, ck.r3, ck.r4, ck.r5, ck.r7, ck.r8):
        rule(site, out)
    part_ids = {p['id'] for p in st.parts}
    real, pending, gaps = [], [], []
    for _s, rule, text in out.rows:
        m = GAP_FACES.search(text) if rule == 'R3' else None
        if rule == 'R5' and text.endswith('has no survey entry'):
            pending.append(text.split()[0])
        elif m and (m.group(2) in ('origin', 'axis') or m.group(2) not in part_ids):
            gaps.append('faces:%s' % m.group(1))
        else:
            real.append((rule, text))
    return real, pending, gaps


class Attempt:
    def __init__(self, st, rule, text, stage=None):
        self.st, self.rule, self.text = st, rule, text
        self.stage = STAGES.index(stage or (rule if rule in STAGES else 'static'))


def r6_check(plan, st, origin, selected_state):
    """R6 against what is already placed; returns (rule text) or None."""
    ox, oz = origin[0], origin[2]
    density = st.arch.get('density') or {}
    for r in plan.results:
        d = math.hypot(ox - r.site['frame']['origin'][0], oz - r.site['frame']['origin'][2])
        need, why = sr.SPACING_M, 'any'
        if r.st.id == st.id and float(density.get('min_same_m', 0.0)) > need:
            need, why = float(density['min_same_m']), 'same'
        if d < need:
            return 'spacing', '%.0f m from %s (%s %s sites need %.0f m)' % (d, r.site['id'], why, st.id, need)
    if (int(ox // sr.CELL_M), int(oz // sr.CELL_M)) in selected_state['cells']:
        return 'cell', 'shares a 1 km cell with another site'
    cap = density.get('max_per_map')
    if cap is not None and selected_state['count'][st.id] >= cap:
        return 'cap', 'max_per_map %d for %s reached' % (cap, st.id)
    if len(plan.results) >= sr.MAX_SITES:
        return 'cap', 'site cap %d reached' % sr.MAX_SITES
    return None


def mo_check(world, rows):
    """map_overlay's own clearances (stricter than R4): vanilla rows and old objects."""
    vanilla = world.limits['piece_vanilla_clearance_m']
    spacing = world.limits['min_spacing_m']
    for r in rows:
        x, z = r['pos'][0], r['pos'][2]
        hit = world.stock_idx.within(x, z, vanilla)
        if hit:
            return '%s is %.1f m from vanilla %s (map_overlay needs %.0f m)' % (
                r['id'], math.hypot(hit[0][0] - x, hit[0][1] - z), hit[0][2][0], vanilla)
        old = world.legacy_idx.within(x, z, spacing)
        if old:
            return '%s is within %.0f m of an existing overlay object' % (r['id'], spacing)
    return None


def try_archetype(plan, st, cand, state):
    """First passing variant of one candidate/archetype: a Result or an Attempt (the deepest failure)."""
    world = plan.world
    best = None

    def fail(rule, text, stage=None):
        nonlocal best
        a = Attempt(st, rule, text, stage)
        if best is None or a.stage > best.stage:
            best = a
    try:
        frames = make_frames(world, st, cand)
    except Reject as exc:
        return Attempt(st, exc.rule, exc.text)
    if not frames:
        return Attempt(st, 'R1', 'no approach frame has a road in reach')
    for frame, protected in frames:
        relax, rule, text = own_predicates(world, st, frame)
        if rule:
            fail(rule, text)
            continue
        site_id = site_id_for(st, cand)
        for variant in st.variants:
            if variant and U('variant', site_id, variant) >= 1.0 / (len(st.variants)):
                continue
            skeleton = {'id': site_id, 'archetype': st.id, 'frame': {'kind': frame.kind, 'origin': frame.origin,
                                                                      'forward_yaw_deg': frame.forward}}
            real, _pend, _gaps = evaluate(world, st, skeleton, [], variant, relax)
            r1 = [t for r, t in real if r == 'R1']
            if r1:
                fail('R1', r1[0])
                continue
            why = r6_check(plan, st, frame.origin, state)
            if why:
                fail('R6', '%s: %s' % why)
                if why[0] == 'cap':
                    plan.cap_blocked[st.id] += 1
                continue
            build = Build(world, st, site_id, frame, variant, protected)
            try:
                build.run()
                slots = build.guard_slots()
            except Reject as exc:
                fail(exc.rule, exc.text)
                continue
            entry = entry_for(site_id, st, frame, protected, build, slots, variant)
            rows = object_rows(site_id, build, world.survey)
            real, pend, gaps = evaluate(world, st, entry, rows, variant, relax)
            plan.gaps.update(gaps)
            if real:
                rule, text = sorted(real, key=lambda r: sr.RULES.index(r[0]))[0]
                fail(rule, text)
                continue
            if len(plan.results) and state['objects'] + len(rows) > sr.MAX_OBJECTS:
                fail('R6', 'object cap %d reached' % sr.MAX_OBJECTS)
                plan.cap_blocked['objects'] += 1
                continue
            proto = sum(1 for r in rows if r['loot'] == 'proto')
            if state['rows'] + proto > sr.MAX_ROWS:
                fail('R6', 'CE row cap %d reached' % sr.MAX_ROWS)
                plan.cap_blocked['rows'] += 1
                continue
            mo = mo_check(world, rows)
            if mo:
                fail('MO', mo)
                continue
            return Result(st, entry, rows, pend, frame.origin)
    return best


# ---------------------------------------------------------------- the plan

def compose(world, accept=()):
    accept = set(accept)
    plan = Plan(world, accept)
    arch_ids = sorted(world.inp.archetypes)
    statics = {a: Static(world, a, world.inp.archetypes[a], accept) for a in arch_ids}
    plan.statics = statics
    state = {'cells': set(), 'count': Counter(), 'objects': 0, 'rows': 0}
    for cand in world.candidates:
        attempts = []
        placed = None
        live = []
        for a in arch_ids:
            st = statics[a]
            if st.blocked:
                attempts.append(Attempt(st, st.blocked[0], '%s' % st.blocked[1], 'static'))
            else:
                live.append(st)

        def fill(st):
            cap = (st.arch.get('density') or {}).get('max_per_map') or 1
            return (state['count'][st.id] / float(cap), H('order', cand[0], cand[1], st.id))
        for st in sorted(live, key=fill):
            res = try_archetype(plan, st, cand, state)
            if isinstance(res, Result):
                placed = res
                break
            attempts.append(res)
        if placed is not None:
            plan.results.append(placed)
            state['cells'].add((int(placed.origin[0] // sr.CELL_M), int(placed.origin[2] // sr.CELL_M)))
            state['count'][placed.st.id] += 1
            state['objects'] += len(placed.objects)
            state['rows'] += sum(1 for r in placed.objects if r['loot'] == 'proto')
            plan.rows.append({'x': cand[0], 'z': cand[1], 'placed': placed.site['id'], 'binding': None,
                              'archetype': placed.st.id, 'pending': len(placed.pending)})
        else:
            top = max(attempts, key=lambda a: (a.stage, -arch_ids.index(a.st.id)))
            plan.rows.append({'x': cand[0], 'z': cand[1], 'placed': None, 'binding': top.rule,
                              'archetype': top.st.id, 'text': top.text[:160],
                              'attempts': {a.st.id: a.rule for a in attempts}})
    retain_zones(plan)
    plan.results.sort(key=lambda r: r.site['id'])
    return plan


def retain_zones(plan):
    """Design 3.2 step 5: an old military zone id moves to the nearest new site of a zone-role archetype within
    400 m (needs two guard slots); old zones with no such site are listed as retired."""
    claimed = set()
    for zone in plan.world.legacy.zones:
        best = None
        for r in plan.results:
            if r.site['id'] in claimed or not r.st.arch.get('zone_role') or len(r.site['guard_slots']) < 2:
                continue
            o = r.site['frame']['origin']
            d = math.hypot(o[0] - zone['pos'][0], o[2] - zone['pos'][1])
            if d <= RETAIN_ZONE_M and (best is None or (d, r.site['id']) < best[0]):
                best = ((d, r.site['id']), r)
        if best is None:
            plan.retired.append(zone)
            continue
        r = best[1]
        claimed.add(r.site['id'])
        r.site['zone_id'] = zone['id']
        r.site['zone_role'] = r.st.arch['zone_role']
        plan.kept.append((zone['id'], r.site['id'], round(best[0][0], 1)))


# ---------------------------------------------------------------- output

def layer_docs(plan):
    """{relative path: layer document} for the plan, one layer per archetype."""
    by_arch = defaultdict(list)
    for r in plan.results:
        by_arch[r.st.id].append(r)
    docs = {}
    for arch_id in sorted(by_arch):
        group = by_arch[arch_id]
        objects = sorted((o for r in group for o in r.objects), key=lambda o: o['id'])
        doc = {'kind': map_overlay.LAYER_KIND, 'id': LAYER_PREFIX + arch_id, 'version': 1,
               'status': 'runtime-unverified',
               'purpose': 'Composed %s sites: %s' % (arch_id, str(plan.statics[arch_id].arch.get('story', '')).strip()
                                                      or 'authored story'),
               'composer': {'schema': SCHEMA, 'accepted_unmeasured': plan.accept,
                            'survey': plan.world.survey_digest},
               'sites': [r.site for r in sorted(group, key=lambda r: r.site['id'])], 'objects': objects}
        docs['%s/%s%s.json' % (LAYER_DIR, LAYER_PREFIX, arch_id)] = doc
    return docs


def layer_bytes(plan):
    return {path: canon(doc) for path, doc in layer_docs(plan).items()}


def committed_accept(root):
    for path in sorted((Path(root) / LAYER_DIR).glob(LAYER_PREFIX + '*.json')):
        meta = read_json(path).get('composer') or {}
        return list(meta.get('accepted_unmeasured') or [])
    return []


def rebuild_bytes(root):
    """Hook of tools.validate.site_rules (R8): {relative path: bytes} of a fresh build from the repo inputs."""
    plan = compose(load_world(root), committed_accept(root))
    if plan.pending:
        raise Refusal(['%d survey pieces are pending' % len(plan.pending)])
    return layer_bytes(plan)


def pieces_request(plan):
    rows = []
    for r in plan.results:
        for o in r.objects:
            if o['id'] not in r.pending:
                continue
            geo = plan.world.inp.geo(o['class'])
            cx, cz = sr.local_to_world(o['pos'][0], o['pos'][2], o['yaw'], geo.cx, geo.cz)
            rows.append({'id': o['id'], 'x': rnd(cx), 'z': rnd(cz), 'yaw': o['yaw'],
                         'hx': rnd(min(max(geo.sx / 2.0, 0.1), 60.0)), 'hz': rnd(min(max(geo.sz / 2.0, 0.1), 60.0)),
                         'h': rnd(plan.world.height_of(o['class']))})
    return rows


def profile_update(root, plan, docs):
    """The profile with the composed layers enabled and the limits raised (never lowered) to hold them."""
    path = Path(root) / PROFILE
    profile = read_json(path)
    enabled = [i for i in profile.get('enabled', []) if not i.startswith(LAYER_PREFIX)]
    layer_ids = sorted(d['id'] for d in docs.values())
    profile['enabled'] = enabled + layer_ids
    limits = profile.setdefault('limits', {})
    source = map_overlay.load_source(Path(root) / 'config/map-overlays')
    old_objects = old_loot = 0
    for layer in source.layers:
        if layer.get('id') in enabled:
            expanded = map_overlay.expand_layer(source, layer)
            old_objects += len(expanded)
            old_loot += sum(1 for o in expanded if isinstance(o, dict) and o.get('loot') == 'proto')
    new_objects = sum(len(d['objects']) for d in docs.values())
    new_loot = sum(1 for d in docs.values() for o in d['objects'] if o['loot'] == 'proto')
    wants = {'max_objects_total': old_objects + new_objects,
             'max_objects_per_layer': max([len(d['objects']) for d in docs.values()] or [0]),
             'max_loot_total': old_loot + new_loot,
             'max_loot_per_layer': max([sum(1 for o in d['objects'] if o['loot'] == 'proto')
                                        for d in docs.values()] or [0])}
    merged = map_overlay.limits_of(profile)
    for key, value in wants.items():
        if value > merged[key]:
            limits[key] = value
    return (json.dumps(profile, indent=2) + '\n').encode()


def write_plan(root, plan):
    if plan.pending:
        raise Refusal(['%d survey pieces are pending; run pieces, probe, site_survey import, then plan again'
                       % len(plan.pending)])
    root = Path(root)
    docs = layer_docs(plan)
    stale = [p for p in (root / LAYER_DIR).glob(LAYER_PREFIX + '*.json')
             if '%s/%s' % (LAYER_DIR, p.name) not in docs]
    for path, doc in docs.items():
        (root / path).write_bytes(canon(doc))
    for p in stale:
        p.unlink()
    (root / PROFILE).write_bytes(profile_update(root, plan, docs))
    return sorted(docs)


# ---------------------------------------------------------------- reporting

def report_lines(plan):
    rows = plan.rows
    placed = [r for r in rows if r['placed']]
    rejected = [r for r in rows if not r['placed']]
    lines = ['site_composer: candidates=%d placed=%d rejected=%d pending_pieces=%d accepted_unmeasured=%s' % (
        len(rows), len(placed), len(rejected), len(plan.pending), ','.join(plan.accept) or 'none')]
    by_arch = Counter(r['archetype'] for r in placed)
    lines.append('site_composer: placed by archetype: ' + (' '.join('%s=%d' % kv for kv in sorted(by_arch.items()))
                                                           or 'none'))
    rules = Counter(r['binding'] for r in rejected)
    lines.append('site_composer: binding rule per rejected candidate: ' + (
        ' '.join('%s=%d' % kv for kv in sorted(rules.items())) or 'none'))
    for ident, st in sorted(plan.statics.items()):
        if st.blocked:
            lines.append('site_composer: archetype %s not placeable: %s: %s' % (ident, st.blocked[0], st.blocked[1]))
    if plan.cap_blocked:
        lines.append('site_composer: R6 cap blocked: ' + ' '.join('%s=%d' % kv for kv in sorted(plan.cap_blocked.items())))
    if plan.gaps:
        lines.append('site_composer: validator gaps filtered (composer placed by the doc rule): ' + ' '.join(
            '%s=%d' % kv for kv in sorted(plan.gaps.items())))
    if plan.kept or plan.retired:
        lines.append('site_composer: military zones kept=%d retired=%d (retired: %s)' % (
            len(plan.kept), len(plan.retired), ','.join(z['id'] for z in plan.retired) or 'none'))
    return lines


def full_report(plan):
    return {'schema': SCHEMA, 'summary': report_lines(plan), 'candidates': plan.rows,
            'kept_zones': [{'zone': z, 'site': s, 'moved_m': d} for z, s, d in plan.kept],
            'retired_zones': plan.retired,
            'blocked': {i: list(st.blocked) for i, st in sorted(plan.statics.items()) if st.blocked}}


# ---------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('plan', 'pieces', 'write', 'check'))
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--mission', type=Path, default=None, help='pristine mission dir with mapgrouppos.xml')
    parser.add_argument('--accept-unmeasured', default='', help='comma list of unmeasurable location keys to accept')
    parser.add_argument('--report', type=Path, default=None, help='plan: write the per-candidate JSON report here')
    parser.add_argument('--out', type=Path, default=None, help='pieces: the request file for site_survey write-input')
    args = parser.parse_args(argv)
    accept = sorted({k for k in args.accept_unmeasured.split(',') if k})
    if set(accept) & set(NEVER_BYPASS):
        print('site_composer: REFUSED: %s can never be accepted' % ','.join(sorted(set(accept) & set(NEVER_BYPASS))))
        return 2
    try:
        if args.command == 'check':
            built = rebuild_bytes(args.repo)
            have = {str(p.relative_to(args.repo)): p.read_bytes()
                    for p in sorted((args.repo / LAYER_DIR).glob(LAYER_PREFIX + '*.json'))}
            diff = sorted(set(built) ^ set(have)) + sorted(k for k in built if k in have and built[k] != have[k])
            print('site_composer: check layers=%d differing=%d%s' % (len(built), len(diff),
                                                                      (' ' + ','.join(diff)) if diff else ''))
            return 1 if diff else 0
        plan = compose(load_world(args.repo, args.mission), accept or committed_accept(args.repo))
        for line in report_lines(plan):
            print(line)
        if args.command == 'plan':
            if args.report:
                args.report.write_bytes(canon(full_report(plan)))
            return 0
        if args.command == 'pieces':
            rows = pieces_request(plan)
            if len(rows) > PIECE_ROWS_MAX:
                print('site_composer: %d boxes missing; writing the first %d, repeat after the import'
                      % (len(rows), PIECE_ROWS_MAX))
                rows = rows[:PIECE_ROWS_MAX]
            if args.out is None:
                print('site_composer: REFUSED: pieces needs --out')
                return 2
            args.out.write_text(json.dumps(rows, indent=1) + '\n')
            print('site_composer: pieces=%d written' % len(rows))
            return 0
        names = write_plan(args.repo, plan)
        print('site_composer: wrote %d layers; run tools.validate.site_rules and map_overlay check' % len(names))
        return 0
    except Refusal as exc:
        print('site_composer: REFUSED')
        for reason in exc.reasons:
            print('  - ' + reason)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
