"""Offline validator for composed map-overlay sites (rules R1-R8 of the sites design, section 4.3).

Run (read-only, nothing is written):
    python3 -B -m tools.validate.site_rules                    # gate: composed layers + archetypes
    python3 -B -m tools.validate.site_rules --report-current   # today's layers; prints failures, never gates

A composed site is judged by eight rules; any finding fails the site and any failing site fails the run.
Offline numbers never establish DayZ behaviour; they only prove the authored geometry is internally coherent.
A missing input is a failure, never a skip: no road graph, no archetype, no class geometry, no survey entry or
no stock mission rows (when a rule needs them) each produce a finding.

Rules (finding lines start with the rule code):
  R0 input contract (schema, missing inputs)         R5 ground contact (survey corners, slope, water)
  R1 location predicates of the archetype            R6 density (spacing, km cell, totals)
  R2 road relation (frame, lane, shoulder, 6 m)      R7 story (declared parts, roles, loot, guard slots)
  R3 facing (faces/align/row/ring/inherit)           R8 determinism (no sweep yaw; rebuild bytes equal)
  R4 clearance (boxes, stock buildings, doors, fire)

Frames: x east, z north, compass yaw (0 = +z, 90 = +x), the frame of tools/package/map_overlay.py. A model-local
point (lx, lz) is placed at x = px + lx*cos(yaw) + lz*sin(yaw), z = pz - lx*sin(yaw) + lz*cos(yaw) (the same maths as
map_overlay.piece_world). The "front" of an object points along bearing = yaw + front_yaw_deg of its class.
A road frame has "right" = clockwise from forward; signed lateral offset t is positive to the right.

INPUT CONTRACT (the composer, W4, writes these; W1/W2/W3 files are read with the shapes below)

1. Composed layers: config/map-overlays/layers/composed-*.json, kind hollow-country-map-overlay.
   "sites": [{"id": "c001", "archetype": "bandit-roadblock",
              "frame": {"kind": "road|approach|view|fall_line|building", "origin": [x, y, z],
                        "forward_yaw_deg": f},
              "protected_bearing_deg": b,        # optional: bearing from the origin to the protected place;
                                                 #   when present every defensive part must face >= 90 deg away
              "fall_line_deg": d,                # optional: downhill bearing (needed by align fall_line/contour)
              "view_yaw_deg": v,                 # optional: view sector centre (faces: view)
              "zones": {"camp": {"centre": [x, z], "radius_m": r}},   # optional: scatter zones
              "guard_slots": [{"part": "nest", "pos": [x, y, z], "facing_deg": a}]}]
   "objects": [{"id": "c001-nest-1", "class": "...", "pos": [x, y, z], "yaw": deg, "loot": "none|proto",
                "site": "c001", "part": "nest", "customString": "hcsite:c001:nest",
                "yaw_source": "road|anchor|contour|fall_line|faces|forward|outward|view|authored"}]
   `site`/`part` may be recovered from customString (hcsite:<site>:<part>). yaw_source is mandatory; a value
   starting with "sweep" or "first_fit" fails R8.
2. Archetypes: config/sites/archetypes/<id>.json (design 2.3): kind hollow-country-site-archetype, id, story, frame,
   location, parts[], density, optional "blocking": true, "allowed_roles": [...], "forbidden_roles": [...].
   Part keys used here: id, anchor, class (str or list), loot, op, side, s, offset_m, gap_m, count, faces, of,
   dist_m, r_m, spacing_m, lane, align, jitter_deg, zone, min_gap_m, stack_on, guard_post, optional.
   Operators are the closed set OPS. Location predicates are the closed set LOCATION_KEYS; an unknown predicate fails.
3. Class geometry (W1): config/sites/class-geometry.json {"classes": {name: {"bounds": {"geometry_min_m": [x,y,z],
   "geometry_max_m": [x,y,z], "footprint_m": [w, l]}, "symmetric": bool, "front_yaw_deg": f,
   "front_source": "odol_memory|calibration|calibration_pending", "door_aprons": [[lx, lz]]}}}. Directional classes
   (symmetric false) need a numeric front_yaw_deg; calibration_pending fails R3. Class kind and role come from
   config/map-overlays/classes.json. Containers get door points at both ends of the long axis unless door_aprons
   is given. Stock building classes may be listed too; one with no geometry is treated as a 16 m circle.
4. Road graph: mission/hollow-country/ai/road-graph.compact.json (Positions x,y,z per node, CSR Offsets/Edges).
5. Survey (W2): config/sites/survey/*.json, merged: {"kind": "hollow-country-site-survey", "version": 1,
   "road_samples": [[x, z, "asphalt|gravel|dirt"]],
   "cells": {"size_m": 8, "samples": [[x, z, slope_pct, water01]]},
   "pieces": {"<object id>": {"corners_y": [a, b, c, d], "center_y": y, "slope_pct": s, "water": false,
                              "collides": false}}}
6. Stock mapgrouppos.xml of a pristine mission (--mission, HC_CE_MISSION, or the wiring_audit default cache path);
   rows are (class, x, y, z, yaw). Needed by the settlement/military predicates of R1 and the building clearance of R4.
7. Determinism hook (R8): tools.package.site_composer.rebuild_bytes(root) -> {relative path: bytes}. Composed layers
   with no such hook fail R8.

Report-current mode adapts today's layers (sites + compositions, no archetypes): R1 fails every site as "no location
intent"; R2/R3/R4/R6/R7/R8 run on the expanded pieces with the composition heading as the frame; class geometry falls
back to the authoring footprint_reserve_m (labelled), and a front yaw of 0.
"""
import argparse
import copy
import importlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path
import re
import statistics
import sys
import xml.etree.ElementTree as ET

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[2]
RULES = ('R0', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8')
OPS = ('in_lane', 'across_lane', 'shoulder', 'offroad', 'row', 'ring', 'facing', 'beside', 'behind', 'scatter',
       'on_slope')
LOCATION_KEYS = ('road', 'junction_m', 'settlement_edge_m', 'military_m', 'road_distance_m', 'not_in',
                 'slope_pct_max', 'near_water_m')
ROAD_KEYS = ('surface', 'straight_m', 'max_turn_deg', 'max_grade_pct')
FRAME_KINDS = ('road', 'approach', 'view', 'fall_line', 'building')

ROAD_WIDTH_M = 7.0          # carriageway width (the compositions assume a seven metre passage)
PASSABLE_M = 3.5
AXIS_TOL_DEG = 10.0
ORIGIN_ROAD_M = 3.0
OFFROAD_CLEAR_M = 6.0       # non-road archetypes: every hard piece this far from any centreline
OFFROAD_OP_M = 8.0
SHOULDER_M = (0.5, 6.0)
IN_LANE_TOL_M = 1.5
APRON_M = 1.0
STOCK_APRON_M = 4.0
STOCK_UNKNOWN_CLEAR_M = 16.0
DOOR_APRON_M = 2.0
FIRE_CANVAS_M = 5.0
SPREAD_STRICT_M = 0.35      # tents, containers, towers, sheds
SPREAD_LOOSE_M = 0.6        # wrecks, nests, other hard pieces
HARD_SLOPE_PCT = 6.0
TOL_ROW, TOL_SOCIAL, TOL_DEFENSIVE, TOL_INHERIT = 10.0, 15.0, 20.0, 10.0
RING_RADIUS_TOL_M = 1.0
ROW_SPACING_TOL_M = 0.5
SPACING_M = 300.0
CELL_M = 1000.0
MAX_SITES, MAX_OBJECTS, MAX_ROWS = 75, 1800, 300
PROTO_ROWS = (1, 4)
SETTLEMENT_LINK_M, SETTLEMENT_MIN_HOUSES, TOWN_CORE_M, MILITARY_CORE_M = 80.0, 6, 60.0, 150.0
HOUSE_PREFIXES = ('Land_House', 'Land_Village', 'Land_City', 'Land_Office', 'Land_Shop', 'Land_Panelak',
                  'Land_School', 'Land_Hospital', 'Land_Farm', 'Land_Barn')
MILITARY_PREFIXES = ('Land_Mil_', 'Land_Tisy_', 'Land_Medical_Tent')
SOFT_ROLES = ('scene dressing', 'furnishing', 'net')
STRICT_KINDS = ('tent', 'container', 'building')
STRICT_ROLES = ('tent', 'container', 'tower', 'shed')
DEFENSIVE_ROLES = ('nest', 'wall', 'fence', 'barrier', 'tower')
HARD_KINDS = ('tent', 'container', 'building', 'wreck')
# report-current: the audit's road-bound kits, the kits whose lane is meant to be blocked, and the defensive names.
LEGACY_ROAD_BOUND = ('checkpoint', 'abandoned-checkpoint', 'bandit-roadblock', 'police-blockade', 'quarantine-post',
                     'crashed-convoy')
LEGACY_BLOCKING = ('bandit-roadblock', 'crashed-convoy')
BAD_YAW_SOURCES = ('sweep', 'first_fit')
CUSTOM = re.compile(r'^hcsite:([^:]+):(.+)$')
MISSION_DEFAULT = '~/.cache/hollow-country/wine-server-20261116/mpmissions/dayzOffline.chernarusplus'
ROAD_CELL = 64.0


# ---- small maths ---------------------------------------------------------------------------------------------

def adiff(a, b):
    """Directed angle between two bearings, 0..180."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def fold(a, b):
    """Angle between two undirected axes, 0..90."""
    d = adiff(a, b)
    return 180.0 - d if d > 90.0 else d


def bearing(dx, dz):
    return math.degrees(math.atan2(dx, dz)) % 360.0


def local_to_world(px, pz, yaw, lx, lz):
    r = math.radians(yaw)
    s, c = math.sin(r), math.cos(r)
    return px + lx * c + lz * s, pz - lx * s + lz * c


def pt_seg(px, pz, ax, az, bx, bz):
    vx, vz = bx - ax, bz - az
    ll = vx * vx + vz * vz
    t = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - ax) * vx + (pz - az) * vz) / ll))
    return math.hypot(px - (ax + t * vx), pz - (az + t * vz))


def _cross(ax, az, bx, bz, cx, cz):
    return (bx - ax) * (cz - az) - (bz - az) * (cx - ax)


def seg_cross(a, b, c, d):
    d1, d2 = _cross(*a, *b, *c), _cross(*a, *b, *d)
    d3, d4 = _cross(*c, *d, *a), _cross(*c, *d, *b)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0


def poly_contains(poly, x, z):
    signs = []
    for k in range(len(poly)):
        a, b = poly[k], poly[(k + 1) % len(poly)]
        signs.append(_cross(*a, *b, x, z))
    return all(v >= 0 for v in signs) or all(v <= 0 for v in signs)


def poly_edges(poly):
    return [(poly[k], poly[(k + 1) % len(poly)]) for k in range(len(poly))]


def _sat_overlap(p, q):
    for poly in (p, q):
        for (ax, az), (bx, bz) in poly_edges(poly):
            nx, nz = -(bz - az), bx - ax
            lo1 = min(nx * x + nz * z for x, z in p)
            hi1 = max(nx * x + nz * z for x, z in p)
            lo2 = min(nx * x + nz * z for x, z in q)
            hi2 = max(nx * x + nz * z for x, z in q)
            if hi1 < lo2 or hi2 < lo1:
                return False
    return True


def poly_gap(p, q):
    """0 when two convex polygons overlap, else the smallest distance between them."""
    if _sat_overlap(p, q):
        return 0.0
    best = math.inf
    for a, other in ((p, q), (q, p)):
        for x, z in a:
            for (ax, az), (bx, bz) in poly_edges(other):
                best = min(best, pt_seg(x, z, ax, az, bx, bz))
    return best


def poly_seg_gap(poly, a, b):
    if poly_contains(poly, *a) or poly_contains(poly, *b):
        return 0.0
    best = math.inf
    for e in poly_edges(poly):
        if seg_cross(a, b, *e):
            return 0.0
        for x, z in e:
            best = min(best, pt_seg(x, z, a[0], a[1], b[0], b[1]))
    for x, z in (a, b):
        for (ax, az), (bx, bz) in poly_edges(poly):
            best = min(best, pt_seg(x, z, ax, az, bx, bz))
    return best


def poly_point_gap(poly, x, z):
    if poly_contains(poly, x, z):
        return 0.0
    return min(pt_seg(x, z, ax, az, bx, bz) for (ax, az), (bx, bz) in poly_edges(poly))


def poly_centre(poly):
    return sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)


def poly_radius(poly):
    cx, cz = poly_centre(poly)
    return max(math.hypot(x - cx, z - cz) for x, z in poly)


# ---- inputs --------------------------------------------------------------------------------------------------

class RoadGraph:
    def __init__(self, nodes, links):
        self.nodes = [tuple(float(v) for v in n) for n in nodes]
        self.nbrs = [sorted(set(l) - {i}) for i, l in enumerate(links)]
        self.degree = [len(n) for n in self.nbrs]
        self.segs = sorted({(min(i, j), max(i, j)) for i, ns in enumerate(self.nbrs) for j in ns})
        self.grid = defaultdict(list)
        for n, (i, j) in enumerate(self.segs):
            a, b = self.nodes[i], self.nodes[j]
            for cx in range(int(min(a[0], b[0]) // ROAD_CELL), int(max(a[0], b[0]) // ROAD_CELL) + 1):
                for cz in range(int(min(a[2], b[2]) // ROAD_CELL), int(max(a[2], b[2]) // ROAD_CELL) + 1):
                    self.grid[(cx, cz)].append(n)
        self.junctions = [i for i, d in enumerate(self.degree) if d >= 3]

    @classmethod
    def from_file(cls, path):
        data = json.loads(Path(path).read_bytes())
        p, o, e = data['Positions'], data['Offsets'], data['Edges']
        count = data['NodeCount']
        return cls([(p[3 * i], p[3 * i + 1], p[3 * i + 2]) for i in range(count)],
                   [e[o[i]:o[i + 1]] for i in range(count)])

    def segments_near(self, x, z, radius):
        found = set()
        r = int(radius // ROAD_CELL) + 1
        bx, bz = int(x // ROAD_CELL), int(z // ROAD_CELL)
        for cx in range(bx - r, bx + r + 1):
            for cz in range(bz - r, bz + r + 1):
                found.update(self.grid.get((cx, cz), ()))
        return [self.segs[n] for n in sorted(found)]

    def nearest(self, x, z, radius=400.0):
        """(distance, (qx, qy, qz), tangent bearing i->j, i, j) of the nearest centreline point, or None."""
        best = None
        for i, j in self.segments_near(x, z, radius):
            a, b = self.nodes[i], self.nodes[j]
            d = pt_seg(x, z, a[0], a[2], b[0], b[2])
            if best is None or d < best[0]:
                vx, vz = b[0] - a[0], b[2] - a[2]
                ll = vx * vx + vz * vz
                t = 0.0 if ll == 0 else max(0.0, min(1.0, ((x - a[0]) * vx + (z - a[2]) * vz) / ll))
                best = (d, (a[0] + t * vx, a[1] + t * (b[1] - a[1]), a[2] + t * vz), bearing(vx, vz), i, j)
        return best if best and best[0] <= radius else None

    def nearest_junction(self, x, z):
        best = None
        for n in self.junctions:
            d = math.hypot(self.nodes[n][0] - x, self.nodes[n][2] - z)
            if best is None or d < best:
                best = d
        return best

    def reach(self, prev, cur, travelled, ref, window, max_turn, max_grade):
        """Metres of straight, gentle road reachable from the start point towards `cur` (capped at window)."""
        while travelled < window:
            a, b = self.nodes[prev], self.nodes[cur]
            length = math.hypot(b[0] - a[0], b[2] - a[2])
            if length > 0:
                if max_turn is not None and fold(bearing(b[0] - a[0], b[2] - a[2]), ref) > max_turn:
                    return travelled
                if max_grade is not None and abs(b[1] - a[1]) / length * 100.0 > max_grade:
                    return travelled
            onward = [n for n in self.nbrs[cur] if n != prev]
            if len(self.nbrs[cur]) != 2 or not onward:
                return travelled
            prev, cur = cur, onward[0]
            c = self.nodes[cur]
            travelled += math.hypot(c[0] - b[0], c[2] - b[2])
        return window


class Geo:
    def __init__(self, cx, cz, sx, sz, front=None, symmetric=False, source='', doors=None, reserve=False):
        self.cx, self.cz, self.sx, self.sz = cx, cz, sx, sz
        self.front, self.symmetric, self.source, self.doors, self.reserve = front, symmetric, source, doors, reserve

    def corners(self, px, pz, yaw):
        hx, hz = self.sx / 2.0, self.sz / 2.0
        return [local_to_world(px, pz, yaw, self.cx + lx, self.cz + lz)
                for lx, lz in ((-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz))]


def parse_geometry(data, classes):
    """{class: Geo} from class-geometry.json plus kind/role context; unreadable rows are left out."""
    out = {}
    for name, row in ((data or {}).get('classes') or {}).items():
        if not isinstance(row, dict):
            continue
        b = row.get('bounds') or {}
        lo, hi = b.get('geometry_min_m'), b.get('geometry_max_m')
        try:
            if lo and hi:
                sx, sz = float(hi[0]) - float(lo[0]), float(hi[2]) - float(lo[2])
                cx, cz = (float(hi[0]) + float(lo[0])) / 2.0, (float(hi[2]) + float(lo[2])) / 2.0
            else:
                sx, sz = (float(v) for v in b['footprint_m'])
                cx = cz = 0.0
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        front = row.get('front_yaw_deg')
        front = float(front) if isinstance(front, (int, float)) and not isinstance(front, bool) else None
        out[name] = Geo(cx, cz, sx, sz, front, bool(row.get('symmetric')), str(row.get('front_source', '')),
                        row.get('door_aprons'))
    return out


def reserve_geometry(classes):
    """Authoring footprint_reserve_m as geometry (report-current fallback only; front assumed 0)."""
    out = {}
    for name, row in (classes or {}).items():
        res = row.get('footprint_reserve_m')
        if isinstance(res, list) and len(res) == 2:
            out[name] = Geo(0.0, 0.0, float(res[0]), float(res[1]), 0.0, False, 'footprint_reserve_m', None, True)
    return out


class Survey:
    def __init__(self, files):
        self.roads, self.cells, self.pieces, self.cell_m = [], [], {}, 8.0
        for data in files:
            self.roads += [r for r in data.get('road_samples') or [] if isinstance(r, list) and len(r) >= 3]
            block = data.get('cells') or {}
            self.cell_m = float(block.get('size_m', self.cell_m))
            self.cells += [c for c in block.get('samples') or [] if isinstance(c, list) and len(c) >= 4]
            self.pieces.update(data.get('pieces') or {})
        self._cell_index = defaultdict(list)
        for c in self.cells:
            self._cell_index[(int(c[0] // 64), int(c[1] // 64))].append(c)

    def _near(self, x, z, radius):
        r = int(radius // 64) + 1
        for cx in range(int(x // 64) - r, int(x // 64) + r + 1):
            for cz in range(int(z // 64) - r, int(z // 64) + r + 1):
                for c in self._cell_index.get((cx, cz), ()):
                    d = math.hypot(c[0] - x, c[1] - z)
                    if d <= radius:
                        yield d, c

    def slope_at(self, x, z):
        best = min(self._near(x, z, self.cell_m), default=None, key=lambda t: t[0])
        return None if best is None else float(best[1][2])

    def pond_within(self, x, z, radius):
        return any(c[3] for _d, c in self._near(x, z, radius))

    def surface_at(self, x, z, radius=12.0):
        best = None
        for r in self.roads:
            d = math.hypot(r[0] - x, r[1] - z)
            if d <= radius and (best is None or d < best[0]):
                best = (d, r[2])
        return None if best is None else best[1]


class Inputs:
    """Everything the rules read; every field is injectable (the unit tests build it from fixtures)."""

    def __init__(self, roads=None, classes=None, geometry=None, archetypes=None, survey=None, stock=None,
                 rebuild=None, allow_reserve=False, composed_files=None):
        self.roads, self.classes, self.archetypes = roads, classes or {}, archetypes or {}
        self.geometry, self.survey, self.stock, self.rebuild = geometry, survey, stock, rebuild
        self.allow_reserve = allow_reserve
        self.composed_files = composed_files or []
        self._reserve = reserve_geometry(self.classes) if allow_reserve else {}
        self._settlements = None
        self._military = None

    # -- class helpers
    def kind(self, cls):
        return (self.classes.get(cls) or {}).get('kind', '')

    def role(self, cls):
        return (self.classes.get(cls) or {}).get('role', '')

    def is_hard(self, cls):
        return self.role(cls) not in SOFT_ROLES

    def geo(self, cls):
        if self.geometry is not None and cls in self.geometry:
            return self.geometry[cls]
        return self._reserve.get(cls)

    # -- stock mission derived sets
    def settlement_houses(self):
        if self._settlements is None:
            houses = [r for r in self.stock or () if r[0].startswith(HOUSE_PREFIXES)]
            index = defaultdict(list)
            for r in houses:
                index[(int(r[1] // SETTLEMENT_LINK_M), int(r[3] // SETTLEMENT_LINK_M))].append(r)
            seen, keep = set(), []
            for start in houses:
                if id(start) in seen:
                    continue
                seen.add(id(start))
                stack, members = [start], []
                while stack:
                    r = stack.pop()
                    members.append(r)
                    for cx in range(int(r[1] // SETTLEMENT_LINK_M) - 1, int(r[1] // SETTLEMENT_LINK_M) + 2):
                        for cz in range(int(r[3] // SETTLEMENT_LINK_M) - 1, int(r[3] // SETTLEMENT_LINK_M) + 2):
                            for o in index.get((cx, cz), ()):
                                if id(o) not in seen and math.hypot(o[1] - r[1], o[3] - r[3]) <= SETTLEMENT_LINK_M:
                                    seen.add(id(o))
                                    stack.append(o)
                if len(members) >= SETTLEMENT_MIN_HOUSES:
                    keep += members
            self._settlements = keep
        return self._settlements

    def military_rows(self):
        if self._military is None:
            self._military = [r for r in self.stock or () if r[0].startswith(MILITARY_PREFIXES)]
        return self._military


def _json(path):
    return json.loads(Path(path).read_bytes())


def read_stock(mission):
    rows = []
    for _event, el in ET.iterparse(str(Path(mission) / 'mapgrouppos.xml')):
        if el.tag == 'group':
            x, y, z = (float(v) for v in el.get('pos').split())
            rows.append((el.get('name'), x, y, z, float(el.get('a', '0') or 0)))
            el.clear()
    return rows


def stock_mission(explicit=None):
    for candidate in (explicit, os.environ.get('HC_CE_MISSION'), MISSION_DEFAULT):
        if candidate:
            path = Path(candidate).expanduser()
            if (path / 'mapgrouppos.xml').is_file():
                return path
    return None


def load_inputs(root=ROOT, mission=None, composed=True, allow_reserve=False):
    root = Path(root)
    layers = sorted((root / 'config/map-overlays/layers').glob('composed-*.json')) if composed else []
    roads_path = root / 'mission/hollow-country/ai/road-graph.compact.json'
    classes = _json(root / 'config/map-overlays/classes.json').get('classes', {})
    # With no composed sites nothing reads the road graph or the stock mission: skip the slow loads.
    roads = RoadGraph.from_file(roads_path) if (layers or not composed) and roads_path.is_file() else None
    gpath = root / 'config/sites/class-geometry.json'
    geometry = parse_geometry(_json(gpath), classes) if gpath.is_file() else None
    archetypes = {}
    for path in sorted((root / 'config/sites/archetypes').glob('*.json')):
        archetypes[path.stem] = _json(path)
    files = sorted((root / 'config/sites/survey').glob('*.json'))
    survey = Survey([_json(p) for p in files]) if files else None
    path = stock_mission(mission) if layers or not composed else None   # no composed sites: nothing reads it
    stock = read_stock(path) if path else None
    hook = None
    try:
        hook = getattr(importlib.import_module('tools.package.site_composer'), 'rebuild_bytes', None)
    except ImportError:
        hook = None
    return Inputs(roads, classes, geometry, archetypes, survey, stock, hook, allow_reserve, layers)


# ---- sites ---------------------------------------------------------------------------------------------------

class Obj:
    def __init__(self, ident, cls, x, y, z, yaw, loot='none', part=None, yaw_source=None):
        self.id, self.cls, self.x, self.y, self.z, self.yaw = ident, cls, x, y, z, yaw
        self.loot, self.part, self.yaw_source = loot, part, yaw_source


class Site:
    def __init__(self, ident, archetype, origin, forward, kind='road', objects=None, legacy=False):
        self.id, self.archetype, self.origin, self.forward, self.kind = ident, archetype, origin, forward, kind
        self.objects = objects or []
        self.legacy = legacy
        self.extra = {}
        self.errors = []
        self.guard_slots = []


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def parse_site(entry, objects):
    errors = []
    frame = entry.get('frame') if isinstance(entry.get('frame'), dict) else {}
    origin, fwd = frame.get('origin'), frame.get('forward_yaw_deg')
    if not (isinstance(origin, list) and len(origin) == 3 and all(_num(v) for v in origin)):
        errors.append('frame.origin missing or not [x, y, z]')
        origin = [0.0, 0.0, 0.0]
    if not _num(fwd):
        errors.append('frame.forward_yaw_deg missing')
        fwd = 0.0
    kind = frame.get('kind')
    if kind not in FRAME_KINDS:
        errors.append('frame.kind %r not in %s' % (kind, '|'.join(FRAME_KINDS)))
    site = Site(entry.get('id'), entry.get('archetype'), [float(v) for v in origin], float(fwd), kind, objects)
    site.errors = errors
    site.extra = {k: entry[k] for k in ('protected_bearing_deg', 'fall_line_deg', 'view_yaw_deg', 'zones')
                  if k in entry}
    slots = entry.get('guard_slots') or []
    site.guard_slots = slots if isinstance(slots, list) else []
    return site


def parse_object(item, errors):
    ident = item.get('id')
    pos = item.get('pos')
    if not (isinstance(pos, list) and len(pos) == 3 and all(_num(v) for v in pos)) or not _num(item.get('yaw')) \
            or not isinstance(item.get('class'), str):
        errors.append('object %s: needs class, pos [x, y, z] and yaw' % ident)
        return None
    site, part = item.get('site'), item.get('part')
    m = CUSTOM.match(item.get('customString') or '')
    if m:
        site, part = site or m.group(1), part or m.group(2)
    return Obj(ident, item['class'], float(pos[0]), float(pos[1]), float(pos[2]), float(item['yaw']),
               item.get('loot', 'none'), part, item.get('yaw_source')), site


def composed_sites(layer):
    """[Site] from one composed layer document; schema problems land on Site.errors / layer-level site '*'."""
    sites = []
    by_site = defaultdict(list)
    stray = []
    for item in layer.get('objects') or []:
        parsed = parse_object(item, stray)
        if parsed:
            by_site[parsed[1]].append(parsed[0])
    declared = set()
    for entry in layer.get('sites') or []:
        site = parse_site(entry, by_site.get(entry.get('id'), []))
        declared.add(site.id)
        sites.append(site)
    for ident in sorted(k for k in by_site if k not in declared):
        stray.append('objects reference undeclared site %r' % ident)
    if stray:
        holder = Site('*', None, [0.0, 0.0, 0.0], 0.0, None)
        holder.errors = stray
        sites.append(holder)
    return sites


def legacy_sites(root, inputs):
    """report-current: today's layers (sites + compositions + loose objects) as legacy Sites."""
    from tools.package import map_overlay
    source = map_overlay.load_source(Path(root) / 'config/map-overlays')
    sites, loose = [], []
    for layer in source.layers:
        expanded = map_overlay.expand_layer(source, layer)
        by_site = defaultdict(list)
        for item in expanded:
            if not isinstance(item, dict) or 'pos' not in item:
                continue
            obj = Obj(item.get('id'), item['class'], item['pos'][0], item['pos'][1], item['pos'][2],
                      float(item.get('yaw', 0.0)), item.get('loot', 'none'))
            if item.get('site'):
                by_site[item['site']].append(obj)
            else:
                loose.append(obj)
        for entry in layer.get('sites') or []:
            comp = entry.get('composition')
            site = Site('%s/%s' % (layer['id'], entry['id']), comp, list(entry['pos']), float(entry['heading']),
                        'road' if comp in LEGACY_ROAD_BOUND else 'approach', by_site.get(entry['id'], []), True)
            site.extra['heading'] = float(entry['heading'])
            sites.append(site)
    for obj in loose:
        site = Site(obj.id, 'single-object', [obj.x, obj.y, obj.z], obj.yaw, 'approach', [obj], True)
        site.extra['heading'] = None
        sites.append(site)
    return sites


# ---- rules ---------------------------------------------------------------------------------------------------

class Findings:
    def __init__(self):
        self.rows = []

    def add(self, site, rule, text):
        self.rows.append((site, rule, text))


class Checker:
    def __init__(self, inputs):
        self.inp = inputs
        self.roads = inputs.roads

    # -- per-site context
    def archetype(self, site):
        if site.legacy:
            return {'id': site.archetype, 'frame': {'kind': site.kind}, 'location': {}, 'parts': [],
                    'blocking': site.archetype in LEGACY_BLOCKING}
        return self.inp.archetypes.get(site.archetype)

    def parts(self, arch):
        return {p['id']: p for p in (arch.get('parts') or []) if isinstance(p, dict) and 'id' in p}

    def poly(self, obj):
        geo = self.inp.geo(obj.cls)
        return None if geo is None else geo.corners(obj.x, obj.z, obj.yaw)

    def front(self, obj):
        """Front bearing of an object, or None when the class is symmetric (any facing) / unknown."""
        geo = self.inp.geo(obj.cls)
        if geo is None or geo.symmetric or geo.front is None:
            return None
        return (obj.yaw + geo.front) % 360.0

    def long_axis(self, obj):
        geo = self.inp.geo(obj.cls)
        if geo is None:
            return obj.yaw % 360.0
        front = obj.yaw + (geo.front or 0.0)
        return front % 360.0 if geo.sz >= geo.sx else (front + 90.0) % 360.0

    def road_frame(self, site):
        """(tangent bearing oriented along forward, d, q) at the frame origin, or None."""
        if self.roads is None:
            return None
        hit = self.roads.nearest(site.origin[0], site.origin[2], 400.0)
        if hit is None:
            return None
        tangent = hit[2]
        if adiff(tangent, site.forward) > 90.0:
            tangent = (tangent + 180.0) % 360.0
        return tangent, hit[0], hit[1]

    @staticmethod
    def st(site_origin, tangent, x, z):
        r = math.radians(tangent)
        dx, dz = x - site_origin[0], z - site_origin[2]
        return dx * math.sin(r) + dz * math.cos(r), dx * math.cos(r) - dz * math.sin(r)

    # ------------------------------------------------------------------------------------------ R0
    def r0(self, site, out):
        for e in site.errors:
            out.add(site.id, 'R0', e)
        if site.legacy:
            return
        if self.archetype(site) is None:
            out.add(site.id, 'R0', 'archetype %r has no file under config/sites/archetypes' % site.archetype)

    # ------------------------------------------------------------------------------------------ R1
    def r1(self, site, out):
        arch = self.archetype(site)
        if site.legacy:
            out.add(site.id, 'R1', 'legacy site: no archetype or location intent (round-robin kit, hash order)')
            return
        if arch is None:
            return
        loc = arch.get('location')
        if not isinstance(loc, dict):
            out.add(site.id, 'R1', 'archetype has no location block')
            return
        x, z = site.origin[0], site.origin[2]
        for key in sorted(loc):
            if key not in LOCATION_KEYS and not key.startswith('_') and key not in ('note', 'notes', 'comment'):
                out.add(site.id, 'R1', 'unsupported location predicate %r' % key)
        road = loc.get('road')
        needs_roads = road is not None or any(k in loc for k in ('junction_m', 'road_distance_m'))
        if needs_roads and self.roads is None:
            out.add(site.id, 'R1', 'road graph missing; road predicates cannot be checked')
        elif isinstance(road, dict):
            self.r1_road(site, road, out)
        if self.roads is not None and 'junction_m' in loc:
            d = self.roads.nearest_junction(x, z)
            lo, hi = loc['junction_m']
            if d is None or not lo <= d <= hi:
                out.add(site.id, 'R1', 'nearest junction %s m outside %s-%s m' % (_r(d), lo, hi))
        if self.roads is not None and 'road_distance_m' in loc:
            hit = self.roads.nearest(x, z, 2000.0)
            lo, hi = loc['road_distance_m']
            if hit is None or not lo <= hit[0] <= hi:
                out.add(site.id, 'R1', 'road distance %s m outside %s-%s m' % (_r(hit and hit[0]), lo, hi))
        needs_stock = 'settlement_edge_m' in loc or 'military_m' in loc or bool(loc.get('not_in'))
        if needs_stock and self.inp.stock is None:
            out.add(site.id, 'R1', 'stock mapgrouppos missing; settlement/military predicates cannot be checked')
        elif needs_stock:
            self.r1_stock(site, loc, out)
        if 'slope_pct_max' in loc:
            slope = None if self.inp.survey is None else self.inp.survey.slope_at(x, z)
            if slope is None:
                out.add(site.id, 'R1', 'no survey slope sample at the frame origin')
            elif slope > loc['slope_pct_max']:
                out.add(site.id, 'R1', 'slope %.1f%% above %s%%' % (slope, loc['slope_pct_max']))
        if 'near_water_m' in loc:
            if self.inp.survey is None:
                out.add(site.id, 'R1', 'no survey; near_water_m cannot be checked')
            elif not self.inp.survey.pond_within(x, z, loc['near_water_m']):
                out.add(site.id, 'R1', 'no water sample within %s m' % loc['near_water_m'])

    def r1_road(self, site, road, out):
        x, z = site.origin[0], site.origin[2]
        for key in sorted(road):
            if key not in ROAD_KEYS and not key.startswith('_'):
                out.add(site.id, 'R1', 'unsupported road predicate %r' % key)
        hit = self.roads.nearest(x, z, 60.0)
        if hit is None:
            out.add(site.id, 'R1', 'no road within 60 m of the frame origin')
            return
        if 'surface' in road:
            surface = None if self.inp.survey is None else self.inp.survey.surface_at(hit[1][0], hit[1][2])
            if surface is None:
                out.add(site.id, 'R1', 'no survey road sample near the frame origin (surface unknown)')
            elif surface not in road['surface']:
                out.add(site.id, 'R1', 'road surface %s not in %s' % (surface, road['surface']))
        if any(k in road for k in ('straight_m', 'max_turn_deg', 'max_grade_pct')):
            window = float(road.get('straight_m', 40.0)) / 2.0
            turn, grade = road.get('max_turn_deg'), road.get('max_grade_pct')
            _d, q, bear, i, j = hit
            a, b = self.roads.nodes[i], self.roads.nodes[j]
            ahead = self.roads.reach(i, j, math.hypot(b[0] - q[0], b[2] - q[2]), bear, window, turn, grade)
            behind = self.roads.reach(j, i, math.hypot(a[0] - q[0], a[2] - q[2]), bear, window, turn, grade)
            if min(ahead, behind) < window - 1e-6:
                out.add(site.id, 'R1', 'straight run %.0f m ahead / %.0f m behind, needs %.0f m each side within '
                        'turn %s deg grade %s%%' % (ahead, behind, window, turn, grade))

    def r1_stock(self, site, loc, out):
        x, z = site.origin[0], site.origin[2]
        houses = self.inp.settlement_houses()
        edge = min((math.hypot(h[1] - x, h[3] - z) for h in houses), default=None)
        military = min((math.hypot(m[1] - x, m[3] - z) for m in self.inp.military_rows()), default=None)
        if 'settlement_edge_m' in loc:
            lo, hi = loc['settlement_edge_m']
            if edge is None or not lo <= edge <= hi:
                out.add(site.id, 'R1', 'settlement edge %s m outside %s-%s m' % (_r(edge), lo, hi))
        if 'military_m' in loc:
            lo, hi = loc['military_m']
            if military is None or not lo <= military <= hi:
                out.add(site.id, 'R1', 'military base %s m outside %s-%s m' % (_r(military), lo, hi))
        for zone in loc.get('not_in') or ():
            if zone == 'military' and military is not None and military < MILITARY_CORE_M:
                out.add(site.id, 'R1', 'inside a military area (%.0f m from a military group)' % military)
            elif zone == 'town_core' and edge is not None and edge < TOWN_CORE_M:
                out.add(site.id, 'R1', 'inside a town core (%.0f m from a house)' % edge)
            elif zone not in ('military', 'town_core'):
                out.add(site.id, 'R1', 'unsupported not_in zone %r' % zone)

    # ------------------------------------------------------------------------------------------ R2
    def r2(self, site, out):
        arch = self.archetype(site)
        if arch is None:
            return
        if self.roads is None:
            out.add(site.id, 'R2', 'road graph missing')
            return
        parts = self.parts(arch)
        polys = {o.id: self.poly(o) for o in site.objects}
        road_bound = (arch.get('frame') or {}).get('kind', site.kind) == 'road'
        frame = self.road_frame(site)
        if road_bound:
            if frame is None or frame[1] > ORIGIN_ROAD_M:
                out.add(site.id, 'R2', 'frame origin %s m from the nearest centreline (max %.0f m)'
                        % (_r(frame and frame[1]), ORIGIN_ROAD_M))
            elif fold(frame[0], site.forward) > AXIS_TOL_DEG:
                out.add(site.id, 'R2', 'frame axis %.0f deg off the road tangent (max %.0f)'
                        % (fold(frame[0], site.forward), AXIS_TOL_DEG))
            if frame is not None and frame[1] <= ORIGIN_ROAD_M:
                self.r2_lane(site, arch, frame, polys, out)
                self.r2_ops(site, parts, frame, polys, out)
        for o in site.objects:
            part = parts.get(o.part) or {}
            if not self.inp.is_hard(o.cls) or polys.get(o.id) is None:
                continue
            if road_bound and part.get('op') in ('in_lane', 'across_lane', 'shoulder', 'offroad'):
                continue
            if road_bound and not site.legacy:
                continue
            if not road_bound or site.legacy:
                if not road_bound and part.get('op') in ('in_lane', 'across_lane', 'shoulder'):
                    continue
                gap = self.road_gap(polys[o.id])
                if gap < OFFROAD_CLEAR_M:
                    out.add(site.id, 'R2', '%s (%s) is %.1f m from a road centreline (hard pieces need %.0f m)'
                            % (o.id, o.cls, gap, OFFROAD_CLEAR_M))

    def road_gap(self, poly, cap=60.0):
        cx, cz = poly_centre(poly)
        best = math.inf
        for i, j in self.roads.segments_near(cx, cz, poly_radius(poly) + cap):
            a, b = self.roads.nodes[i], self.roads.nodes[j]
            best = min(best, poly_seg_gap(poly, (a[0], a[2]), (b[0], b[2])))
        return best

    def r2_lane(self, site, arch, frame, polys, out):
        if arch.get('blocking'):
            return
        tangent = frame[0]
        half = ROAD_WIDTH_M / 2.0
        spans = []
        for o in site.objects:
            if not self.inp.is_hard(o.cls) or polys[o.id] is None:
                continue
            spans.append([self.st(site.origin, tangent, x, z) for x, z in polys[o.id]])
        if not spans:
            return
        lo = min(s for poly in spans for s, _t in poly)
        hi = max(s for poly in spans for s, _t in poly)
        worst, at = math.inf, None
        s = lo
        while s <= hi:
            ivals = []
            for poly in spans:
                ts = []
                for k in range(len(poly)):
                    (s1, t1), (s2, t2) = poly[k], poly[(k + 1) % len(poly)]
                    if (s1 - s) * (s2 - s) <= 0 and s1 != s2:
                        ts.append(t1 + (t2 - t1) * (s - s1) / (s2 - s1))
                    elif s1 == s2 == s:
                        ts += [t1, t2]
                if ts:
                    ivals.append((max(min(ts), -half), min(max(ts), half)))
            if ivals:
                ivals.sort()
                free, cursor = 0.0, -half
                for a, b in ivals:
                    if b <= a:
                        continue
                    free = max(free, a - cursor)
                    cursor = max(cursor, b)
                free = max(free, half - cursor)
                if free < worst:
                    worst, at = free, s
            s += 0.5
        if worst < PASSABLE_M - 1e-6:
            out.add(site.id, 'R2', 'passable lane %.1f m at s=%.0f (needs %.1f m; archetype is not blocking)'
                    % (worst, at, PASSABLE_M))

    def r2_ops(self, site, parts, frame, polys, out):
        tangent = frame[0]
        half = ROAD_WIDTH_M / 2.0
        by_part = defaultdict(list)
        for o in site.objects:
            by_part[o.part].append(o)
        for pid, part in parts.items():
            op, objs = part.get('op'), by_part.get(pid, [])
            if op in ('in_lane', 'across_lane', 'shoulder', 'offroad', 'scatter') and not objs:
                continue
            side_sign = {'right': 1.0, 'left': -1.0}.get(part.get('side'))
            if op == 'in_lane':
                lane = {'right': half / 2.0, 'left': -half / 2.0}.get(part.get('lane'), 0.0)
                for o in objs:
                    t = self.st(site.origin, tangent, o.x, o.z)[1]
                    if abs(t - lane) > IN_LANE_TOL_M:
                        out.add(site.id, 'R2', '%s is %.1f m from the %s lane centre (max %.1f m)'
                                % (o.id, abs(t - lane), part.get('lane', 'centre'), IN_LANE_TOL_M))
            elif op == 'across_lane':
                covered = []
                for o in objs:
                    if polys[o.id] is None:
                        continue
                    ts = [self.st(site.origin, tangent, x, z)[1] for x, z in polys[o.id]]
                    covered.append((max(min(ts), -half), min(max(ts), half)))
                covered.sort()
                gaps, cursor = [], -half
                for a, b in covered:
                    if a > cursor:
                        gaps.append(a - cursor)
                    cursor = max(cursor, b)
                if cursor < half:
                    gaps.append(half - cursor)
                free = max(gaps, default=0.0)
                want = part.get('gap_m')
                if want is None and free > ROW_SPACING_TOL_M:
                    out.add(site.id, 'R2', 'part %s leaves a %.1f m gap but declares no gap_m' % (pid, free))
                elif want is not None and abs(free - float(want)) > ROW_SPACING_TOL_M + 0.5:
                    out.add(site.id, 'R2', 'part %s gap %.1f m, declared %.1f m' % (pid, free, float(want)))
                if want is not None and float(want) < PASSABLE_M and not site_blocking(self, site):
                    out.add(site.id, 'R2', 'part %s declares gap_m %.1f below %.1f m' % (pid, float(want),
                                                                                         PASSABLE_M))
            elif op in ('shoulder', 'offroad'):
                for o in objs:
                    if polys[o.id] is None:
                        continue
                    ts = [self.st(site.origin, tangent, x, z)[1] for x, z in polys[o.id]]
                    if side_sign is not None and min(t * side_sign for t in ts) < -0.01:
                        out.add(site.id, 'R2', '%s is not on the %s side' % (o.id, part.get('side')))
                        continue
                    near = min(abs(t) for t in ts)
                    if op == 'shoulder' and not SHOULDER_M[0] <= near - half <= SHOULDER_M[1]:
                        out.add(site.id, 'R2', '%s is %.1f m beyond the road edge (shoulder %.1f-%.1f m)'
                                % (o.id, near - half, *SHOULDER_M))
                    if op == 'offroad' and self.road_gap(polys[o.id]) < OFFROAD_OP_M:
                        out.add(site.id, 'R2', '%s is %.1f m from a centreline (offroad needs %.0f m)'
                                % (o.id, self.road_gap(polys[o.id]), OFFROAD_OP_M))
            elif op == 'scatter':
                for o in objs:
                    if abs(self.st(site.origin, tangent, o.x, o.z)[1]) < half:
                        out.add(site.id, 'R2', 'litter %s lies on the carriageway' % o.id)

    # ------------------------------------------------------------------------------------------ R3
    def r3(self, site, out):
        arch = self.archetype(site)
        if arch is None:
            return
        if site.legacy:
            self.r3_legacy(site, out)
            return
        parts = self.parts(arch)
        frame = self.road_frame(site)
        by_part = defaultdict(list)
        for o in site.objects:
            by_part[o.part].append(o)
        protected = site.extra.get('protected_bearing_deg')
        for o in site.objects:
            part = parts.get(o.part)
            if part is None:
                continue
            op, role = part.get('op'), self.inp.role(o.cls)
            faces = part.get('faces') or {'facing': 'of', 'ring': 'of'}.get(op)
            geo = self.inp.geo(o.cls)
            if role == 'tent' and faces is None:
                out.add(site.id, 'R3', 'tent %s declares no faces target (lane or fire)' % o.id)
            if faces is not None:
                target = self.target(site, o, part, faces, by_part)
                if isinstance(target, str):
                    out.add(site.id, 'R3', '%s: %s' % (o.id, target))
                elif geo is not None and not geo.symmetric:
                    if geo.front is None or geo.source == 'calibration_pending':
                        out.add(site.id, 'R3', '%s: class %s has no front_yaw_deg (calibration pending)'
                                % (o.id, o.cls))
                    else:
                        tol = TOL_ROW if op == 'row' else TOL_DEFENSIVE if role in DEFENSIVE_ROLES else TOL_SOCIAL
                        err = adiff(self.front(o), target)
                        if err > tol:
                            out.add(site.id, 'R3', '%s faces %.0f deg off its %s target (max %.0f)'
                                    % (o.id, err, faces, tol))
            if protected is not None and role in DEFENSIVE_ROLES and self.front(o) is not None:
                if adiff(self.front(o), protected) < 90.0:
                    out.add(site.id, 'R3', '%s faces the protected side' % o.id)
            self.r3_align(site, o, part, parts, by_part, frame, out)
        for pid, part in parts.items():
            self.r3_group(site, pid, part, by_part.get(pid, []), by_part, out)

    def target(self, site, obj, part, faces, by_part):
        """Target bearing or an error string."""
        if faces == 'forward':
            return site.forward % 360.0
        if faces == '-forward':
            return (site.forward + 180.0) % 360.0
        if faces == 'view':
            v = site.extra.get('view_yaw_deg')
            return float(v) % 360.0 if _num(v) else 'faces view but the site has no view_yaw_deg'
        ref = part.get('of') if faces in ('of', 'outward') else faces
        pool = by_part.get(ref) or []
        if not pool:
            return 'faces %r but no object of part %r exists' % (faces, ref)
        near = min(pool, key=lambda p: math.hypot(p.x - obj.x, p.z - obj.z))
        if near is obj:
            return 'faces itself'
        b = bearing(near.x - obj.x, near.z - obj.z)
        return (b + 180.0) % 360.0 if faces == 'outward' else b

    def r3_align(self, site, o, part, parts, by_part, frame, out):
        align = part.get('align')
        op = part.get('op')
        jitter = float(part.get('jitter_deg', 0.0))
        axis = self.long_axis(o)
        if op == 'across_lane':
            if frame is None:
                return
            if fold(axis, frame[0] + 90.0) > TOL_ROW + jitter:
                out.add(site.id, 'R3', '%s long axis %.0f deg off perpendicular to the road'
                        % (o.id, fold(axis, frame[0] + 90.0)))
        if align == 'road':
            hit = self.roads.nearest(o.x, o.z, 80.0) if self.roads is not None else None
            if hit is None:
                out.add(site.id, 'R3', '%s aligns to the road but no road within 80 m' % o.id)
            elif fold(axis, hit[2]) > TOL_ROW + jitter:
                out.add(site.id, 'R3', '%s long axis %.0f deg off the road tangent (max %.0f)'
                        % (o.id, fold(axis, hit[2]), TOL_ROW + jitter))
        elif align == 'anchor':
            anchors = [p for p in parts.values() if p.get('anchor')]
            pool = by_part.get(anchors[0]['id']) if anchors else None
            if pool and fold(axis, self.long_axis(pool[0])) > TOL_ROW + jitter:
                out.add(site.id, 'R3', '%s not aligned with the anchor' % o.id)
        elif align in ('fall_line', 'contour'):
            fl = site.extra.get('fall_line_deg')
            if not _num(fl):
                out.add(site.id, 'R3', '%s aligns to %s but the site has no fall_line_deg' % (o.id, align))
            else:
                want = fl if align == 'fall_line' else fl + 90.0
                if fold(axis, want) > TOL_ROW + jitter:
                    out.add(site.id, 'R3', '%s long axis %.0f deg off the %s' % (o.id, fold(axis, want), align))
        if op in ('beside', 'behind'):
            pool = by_part.get(part.get('of')) or []
            if not pool:
                out.add(site.id, 'R3', '%s is %s %r but that part has no object' % (o.id, op, part.get('of')))
            else:
                ref = min(pool, key=lambda p: math.hypot(p.x - o.x, p.z - o.z))
                fa, fb = self.front(o), self.front(ref)
                ya = fa if fa is not None and fb is not None else o.yaw
                yb = fb if fa is not None and fb is not None else ref.yaw
                if adiff(ya, yb) > TOL_INHERIT:
                    out.add(site.id, 'R3', '%s does not inherit the yaw of %s (%.0f deg off)'
                            % (o.id, ref.id, adiff(ya, yb)))

    def r3_group(self, site, pid, part, objs, by_part, out):
        op = part.get('op')
        if op == 'row' and len(objs) >= 2:
            yaws = [o.yaw for o in objs]
            if max(adiff(a, b) for a in yaws for b in yaws) > TOL_ROW:
                out.add(site.id, 'R3', 'row %s yaws differ by more than %.0f deg' % (pid, TOL_ROW))
            ordered = sorted(objs, key=lambda o: (o.x, o.z))
            if abs(ordered[-1].x - ordered[0].x) < abs(ordered[-1].z - ordered[0].z):
                ordered = sorted(objs, key=lambda o: (o.z, o.x))
            steps = [math.hypot(b.x - a.x, b.z - a.z) for a, b in zip(ordered, ordered[1:])]
            want = part.get('spacing_m')
            want = float(want) if want is not None else statistics.mean(steps)
            if any(abs(s - want) > ROW_SPACING_TOL_M for s in steps):
                out.add(site.id, 'R3', 'row %s spacing %s m, needs equal %.1f m +/- %.1f'
                        % (pid, '/'.join('%.1f' % s for s in steps), want, ROW_SPACING_TOL_M))
        if op == 'ring':
            pool = by_part.get(part.get('of')) or []
            r = part.get('r_m')
            if pool and r is not None:
                for o in objs:
                    d = min(math.hypot(o.x - p.x, o.z - p.z) for p in pool)
                    if abs(d - float(r)) > RING_RADIUS_TOL_M:
                        out.add(site.id, 'R3', '%s is %.1f m from %s, ring radius is %.1f m'
                                % (o.id, d, part.get('of'), float(r)))

    def r3_legacy(self, site, out):
        """Report-current: defences face outward, seats face a table or fire, tents face a fire."""
        fires = [o for o in site.objects if 'fireplace' in o.cls.lower()]
        tables = [o for o in site.objects if 'table' in o.cls.lower()]
        for o in site.objects:
            geo = self.inp.geo(o.cls)
            front = (o.yaw + (geo.front if geo and geo.front is not None else 0.0)) % 360.0
            name = o.cls.lower()
            if self.inp.role(o.cls) in DEFENSIVE_ROLES:
                outward = bearing(o.x - site.origin[0], o.z - site.origin[2])
                if adiff(front, outward) > TOL_DEFENSIVE:
                    out.add(site.id, 'R3', 'defensive %s faces %.0f deg off outward (max %.0f)'
                            % (o.id, adiff(front, outward), TOL_DEFENSIVE))
            elif 'chair' in name or 'bench' in name:
                pool = tables + fires
                if pool:
                    near = min(pool, key=lambda p: math.hypot(p.x - o.x, p.z - o.z))
                    err = adiff(front, bearing(near.x - o.x, near.z - o.z))
                    if err > TOL_SOCIAL:
                        out.add(site.id, 'R3', 'seat %s faces %.0f deg off its table/fire' % (o.id, err))
            elif self.inp.role(o.cls) == 'tent':
                if not fires:
                    out.add(site.id, 'R3', 'tent %s has no fire or declared lane to face' % o.id)
                    continue
                near = min(fires, key=lambda p: math.hypot(p.x - o.x, p.z - o.z))
                err = adiff(front, bearing(near.x - o.x, near.z - o.z))
                if err > TOL_SOCIAL:
                    out.add(site.id, 'R3', 'tent %s faces %.0f deg off the fire' % (o.id, err))

    # ------------------------------------------------------------------------------------------ R4
    def r4(self, site, out):
        arch = self.archetype(site)
        if arch is None:
            return
        parts = self.parts(arch)
        polys = {}
        for o in site.objects:
            polys[o.id] = self.poly(o)
            if polys[o.id] is None:
                out.add(site.id, 'R4', 'class %s has no measured geometry (class-geometry.json)' % o.cls)
        live = [o for o in site.objects if polys[o.id] is not None]
        for k, a in enumerate(live):
            for b in live[k + 1:]:
                pa, pb = parts.get(a.part) or {}, parts.get(b.part) or {}
                if pa.get('stack_on') == b.part or pb.get('stack_on') == a.part:
                    continue
                if (pa.get('op') == 'facing' and pa.get('of') == b.part) or \
                        (pb.get('op') == 'facing' and pb.get('of') == a.part):
                    continue
                need = APRON_M if self.inp.is_hard(a.cls) or self.inp.is_hard(b.cls) else 0.0
                gap = poly_gap(polys[a.id], polys[b.id])
                if gap < need - 1e-9 and (gap > 0 or need > 0):
                    out.add(site.id, 'R4', '%s and %s are %.2f m apart (need %.1f m)' % (a.id, b.id, gap, need))
        self.r4_stock(site, live, polys, out)
        self.r4_doors(site, live, polys, out)
        self.r4_fire(site, live, polys, out)
        self.r4_survey(site, live, out)
        self.r4_scatter(site, parts, out)

    def r4_stock(self, site, live, polys, out):
        if not live:
            return
        if self.inp.stock is None:
            out.add(site.id, 'R4', 'stock mapgrouppos missing; stock building clearance cannot be checked')
            return
        reach = max(math.hypot(o.x - site.origin[0], o.z - site.origin[2]) for o in live) + 60.0
        for row in self.inp.stock:
            if math.hypot(row[1] - site.origin[0], row[3] - site.origin[2]) > reach + 40.0:
                continue
            geo = self.inp.geometry.get(row[0]) if self.inp.geometry else None
            for o in live:
                need = STOCK_APRON_M if self.inp.is_hard(o.cls) else 0.0
                if geo is not None:
                    gap = poly_gap(polys[o.id], geo.corners(row[1], row[3], row[4]))
                    if gap < need or (gap == 0.0):
                        out.add(site.id, 'R4', '%s is %.1f m from stock %s (need %.0f m)' % (o.id, gap, row[0], need))
                else:
                    gap = poly_point_gap(polys[o.id], row[1], row[3])
                    if gap < STOCK_UNKNOWN_CLEAR_M and math.hypot(row[1] - o.x, row[3] - o.z) < \
                            STOCK_UNKNOWN_CLEAR_M + poly_radius(polys[o.id]) and \
                            self.inp.is_hard(o.cls) and row[0].startswith(('Land_', 'StaticObj_')):
                        out.add(site.id, 'R4', '%s is %.1f m from stock %s (unmeasured: needs %.0f m)'
                                % (o.id, gap, row[0], STOCK_UNKNOWN_CLEAR_M))

    def doors(self, o):
        geo = self.inp.geo(o.cls)
        if geo is None:
            return []
        points = geo.doors
        if points is None and self.inp.kind(o.cls) == 'container':
            half = (geo.sz if geo.sz >= geo.sx else geo.sx) / 2.0
            points = [[geo.cx, geo.cz + half + 0.0], [geo.cx, geo.cz - half]] if geo.sz >= geo.sx else \
                [[geo.cx + half, geo.cz], [geo.cx - half, geo.cz]]
        return [local_to_world(o.x, o.z, o.yaw, p[0], p[1]) for p in points or ()]

    def r4_doors(self, site, live, polys, out):
        for o in live:
            for dx, dz in self.doors(o):
                for other in live:
                    if other is o:
                        continue
                    gap = poly_point_gap(polys[other.id], dx, dz)
                    if gap < DOOR_APRON_M:  # the door sits on its own box edge: only OTHER objects count
                        out.add(site.id, 'R4', '%s blocks the door apron of %s (%.1f m, need %.0f m)'
                                % (other.id, o.id, gap, DOOR_APRON_M))

    def r4_fire(self, site, live, polys, out):
        fires = [o for o in live if 'fireplace' in o.cls.lower()]
        tents = [o for o in live if self.inp.role(o.cls) == 'tent' or self.inp.kind(o.cls) == 'tent']
        for f in fires:
            for t in tents:
                gap = poly_gap(polys[f.id], polys[t.id])
                if gap < FIRE_CANVAS_M:
                    out.add(site.id, 'R4', 'fire %s is %.1f m from canvas %s (need %.0f m)'
                            % (f.id, gap, t.id, FIRE_CANVAS_M))

    def r4_survey(self, site, live, out):
        if self.inp.survey is None:
            return
        for o in live:
            entry = self.inp.survey.pieces.get(o.id)
            if entry and entry.get('collides') and self.inp.is_hard(o.cls):
                out.add(site.id, 'R4', '%s: survey box collision (tree, wall, rock or fence)' % o.id)

    def r4_scatter(self, site, parts, out):
        by_part = defaultdict(list)
        for o in site.objects:
            by_part[o.part].append(o)
        for pid, part in parts.items():
            if part.get('op') != 'scatter':
                continue
            gap = float(part.get('min_gap_m', 0.0))
            objs = by_part.get(pid, [])
            for k, a in enumerate(objs):
                for b in objs[k + 1:]:
                    if math.hypot(a.x - b.x, a.z - b.z) < gap:
                        out.add(site.id, 'R4', 'litter %s and %s closer than %.1f m' % (a.id, b.id, gap))
            zone = (site.extra.get('zones') or {}).get(part.get('zone'))
            for a in objs:
                if part.get('zone') is None or not isinstance(zone, dict):
                    out.add(site.id, 'R4', 'litter %s has no declared zone' % a.id)
                elif math.hypot(a.x - zone['centre'][0], a.z - zone['centre'][1]) > zone['radius_m']:
                    out.add(site.id, 'R4', 'litter %s outside zone %s' % (a.id, part.get('zone')))

    # ------------------------------------------------------------------------------------------ R5
    def r5(self, site, out):
        arch = self.archetype(site)
        if arch is None:
            return
        survey = self.inp.survey
        loc_max = (arch.get('location') or {}).get('slope_pct_max')
        hard = [o for o in site.objects if self.inp.is_hard(o.cls)]
        if survey is None:
            if hard:
                out.add(site.id, 'R5', 'survey missing (config/sites/survey): ground contact cannot be checked')
            return
        for o in hard:
            e = survey.pieces.get(o.id)
            if not isinstance(e, dict):
                out.add(site.id, 'R5', '%s has no survey entry' % o.id)
                continue
            corners = e.get('corners_y')
            if not (isinstance(corners, list) and len(corners) == 4 and all(_num(v) for v in corners)):
                out.add(site.id, 'R5', '%s survey entry lacks four corner heights' % o.id)
                continue
            strict = self.inp.kind(o.cls) in STRICT_KINDS and self.inp.kind(o.cls) != 'wreck' \
                or self.inp.role(o.cls) in STRICT_ROLES
            limit = SPREAD_STRICT_M if strict else SPREAD_LOOSE_M
            spread = max(corners) - min(corners)
            if spread > limit + 1e-9:
                out.add(site.id, 'R5', '%s corner spread %.2f m above %.2f m' % (o.id, spread, limit))
            if e.get('water'):
                out.add(site.id, 'R5', '%s stands on water' % o.id)
            slope = e.get('slope_pct')
            cap = loc_max if _num(loc_max) else math.inf
            if strict and (self.inp.kind(o.cls) in ('tent', 'container') or self.inp.role(o.cls) in STRICT_ROLES):
                cap = min(cap, HARD_SLOPE_PCT)
            if _num(slope) and slope > cap:
                out.add(site.id, 'R5', '%s slope %.1f%% above %.1f%%' % (o.id, slope, cap))

    # ------------------------------------------------------------------------------------------ R7
    def r7(self, site, out):
        arch = self.archetype(site)
        if arch is None:
            return
        proto = [o for o in site.objects if o.loot == 'proto']
        if not PROTO_ROWS[0] <= len(proto) <= PROTO_ROWS[1]:
            out.add(site.id, 'R7', '%d proto loot rows, needs %d-%d' % (len(proto), *PROTO_ROWS))
        if site.legacy:
            return
        parts = self.parts(arch)
        allowed, forbidden = arch.get('allowed_roles'), arch.get('forbidden_roles') or []
        counts = defaultdict(int)
        for o in site.objects:
            part = parts.get(o.part)
            if part is None:
                out.add(site.id, 'R7', '%s names part %r which the archetype does not declare' % (o.id, o.part))
                continue
            counts[o.part] += 1
            classes = part.get('class')
            classes = [classes] if isinstance(classes, str) else classes or []
            if o.cls not in classes:
                out.add(site.id, 'R7', '%s class %s not allowed for part %s' % (o.id, o.cls, o.part))
            role = self.inp.role(o.cls)
            if (allowed is not None and role not in allowed) or role in forbidden:
                out.add(site.id, 'R7', '%s role %r not allowed for archetype %s' % (o.id, role, site.archetype))
            if o.loot == 'proto' and not (part.get('anchor') or self.inp.kind(o.cls) in ('container', 'tent')):
                out.add(site.id, 'R7', '%s carries loot but is neither anchor, container nor tent' % o.id)
            if o.loot == 'proto' and part.get('loot') != 'proto':
                out.add(site.id, 'R7', '%s carries loot the archetype does not declare for part %s' % (o.id, o.part))
            if part.get('op') == 'scatter' and self.inp.is_hard(o.cls):
                out.add(site.id, 'R7', '%s: scatter litter may never be a hard piece' % o.id)
        anchors = [p for p in parts.values() if p.get('anchor')]
        if len(anchors) != 1:
            out.add(site.id, 'R7', 'archetype declares %d anchor parts, needs exactly 1' % len(anchors))
        for pid, part in parts.items():
            want = part.get('count', 1)
            lo, hi = (want, want) if isinstance(want, int) else (want[0], want[1])
            if counts[pid] < lo and not part.get('optional'):
                out.add(site.id, 'R7', 'part %s has %d objects, needs %d' % (pid, counts[pid], lo))
            elif counts[pid] > hi:
                out.add(site.id, 'R7', 'part %s has %d objects, allows %d' % (pid, counts[pid], hi))
        self.r7_guards(site, parts, out)

    def r7_guards(self, site, parts, out):
        slots = defaultdict(list)
        for s in site.guard_slots:
            if not (isinstance(s, dict) and isinstance(s.get('pos'), list) and _num(s.get('facing_deg'))
                    and s.get('part')):
                out.add(site.id, 'R7', 'guard slot needs part, pos and facing_deg')
                continue
            slots[s['part']].append(s)
        for pid, part in parts.items():
            if not part.get('guard_post'):
                continue
            objs = [o for o in site.objects if o.part == pid]
            by_part = defaultdict(list)
            for o in site.objects:
                by_part[o.part].append(o)
            for o in objs:
                faces = part.get('faces') or 'forward'
                target = self.target(site, o, part, faces, by_part)
                geo = self.inp.geo(o.cls)
                front = self.front(o)
                near = [s for s in slots.get(pid, ()) if math.hypot(s['pos'][0] - o.x, s['pos'][2] - o.z) < 6.0]
                if not near:
                    out.add(site.id, 'R7', 'guard post %s has no guard slot' % o.id)
                    continue
                if isinstance(target, str) or geo is None or front is None:
                    continue
                s = min(near, key=lambda s: math.hypot(s['pos'][0] - o.x, s['pos'][2] - o.z))
                if adiff(s['facing_deg'], target) > TOL_DEFENSIVE:
                    out.add(site.id, 'R7', 'guard slot of %s faces %.0f deg off its target'
                            % (o.id, adiff(s['facing_deg'], target)))
                fx, fz = math.sin(math.radians(front)), math.cos(math.radians(front))
                aligned = adiff(front, o.yaw) < 45 or adiff(front, o.yaw + 180) < 45
                half = geo.sz / 2.0 if aligned else geo.sx / 2.0
                depth = (s['pos'][0] - o.x) * fx + (s['pos'][2] - o.z) * fz
                if not half - 2.5 <= depth <= half - 0.5:
                    out.add(site.id, 'R7', 'guard slot of %s sits %.1f m from the front face, needs 0.5-2.5 m '
                            'behind it' % (o.id, half - depth))

    # ------------------------------------------------------------------------------------------ R8
    def r8(self, site, out):
        if site.legacy:
            heading = site.extra.get('heading')
            if heading is not None and abs(heading / 15.0 - round(heading / 15.0)) < 1e-6:
                out.add(site.id, 'R8', 'heading %.0f is on the 15-degree first-fit sweep' % heading)
            return
        for o in site.objects:
            src = o.yaw_source
            if not isinstance(src, str) or not src:
                out.add(site.id, 'R8', '%s has no yaw_source' % o.id)
            elif src.startswith(BAD_YAW_SOURCES):
                out.add(site.id, 'R8', '%s yaw came from a %s' % (o.id, src))


def site_blocking(checker, site):
    arch = checker.archetype(site)
    return bool(arch and arch.get('blocking'))


def _r(v):
    return 'none' if v is None else '%.0f' % v


# ---- density, archetype files, run ----------------------------------------------------------------------------

def check_density(inputs, sites, out):
    live = [s for s in sites if s.id != '*']
    for k, a in enumerate(live):
        arch = inputs.archetypes.get(a.archetype) or {}
        density = arch.get('density') or {}
        for b in live[k + 1:]:
            d = math.hypot(a.origin[0] - b.origin[0], a.origin[2] - b.origin[2])
            need = SPACING_M
            reason = 'any'
            if a.archetype == b.archetype and a.archetype is not None:
                same = float(density.get('min_same_m', 0.0))
                if same > need:
                    need, reason = same, 'same'
            if d < need:
                for s, other in ((a, b), (b, a)):
                    out.add(s.id, 'R6', '%.0f m from %s (%s %s sites need %.0f m)' % (d, other.id, reason,
                                                                                    other.archetype, need))
    cells = defaultdict(list)
    for s in live:
        cells[(int(s.origin[0] // CELL_M), int(s.origin[2] // CELL_M))].append(s)
    for members in cells.values():
        if len(members) > 1:
            for s in members:
                out.add(s.id, 'R6', 'shares a 1 km cell with %s' % ', '.join(m.id for m in members if m is not s))
    per = defaultdict(list)
    for s in live:
        per[s.archetype].append(s)
    for name, members in per.items():
        cap = ((inputs.archetypes.get(name) or {}).get('density') or {}).get('max_per_map')
        if cap is not None and len(members) > cap:
            out.add('*', 'R6', '%d %s sites, archetype allows %d' % (len(members), name, cap))
    objects = sum(len(s.objects) for s in live)
    rows = sum(1 for s in live for o in s.objects if o.loot == 'proto')
    for label, value, cap in (('sites', len(live), MAX_SITES), ('objects', objects, MAX_OBJECTS),
                              ('CE rows', rows, MAX_ROWS)):
        if value > cap:
            out.add('*', 'R6', '%d %s exceed the cap of %d' % (value, label, cap))


def check_archetypes(inputs, out):
    classes = inputs.classes
    for ident, arch in sorted(inputs.archetypes.items()):
        label = 'archetype:' + ident
        if arch.get('kind') != 'hollow-country-site-archetype' or arch.get('id') != ident:
            out.add(label, 'R7', 'kind must be hollow-country-site-archetype and id must equal the file name')
        if not isinstance(arch.get('story'), str) or not arch['story'].strip():
            out.add(label, 'R7', 'missing story line')
        if not isinstance(arch.get('density'), dict):
            out.add(label, 'R7', 'missing density block')
        if (arch.get('frame') or {}).get('kind') not in FRAME_KINDS:
            out.add(label, 'R7', 'frame.kind must be one of %s' % '|'.join(FRAME_KINDS))
        seen = set()
        for p in arch.get('parts') or []:
            pid = p.get('id') if isinstance(p, dict) else None
            if not pid or pid in seen:
                out.add(label, 'R7', 'part id missing or duplicated: %r' % pid)
                continue
            seen.add(pid)
            if p.get('op') not in OPS:
                out.add(label, 'R7', 'part %s uses operator %r outside the closed set' % (pid, p.get('op')))
            cls = p.get('class')
            for name in ([cls] if isinstance(cls, str) else cls or []):
                if name not in classes:
                    out.add(label, 'R7', 'part %s class %s is not in classes.json' % (pid, name))


def run(inputs, sites, with_archetypes=True):
    out = Findings()
    if with_archetypes:
        check_archetypes(inputs, out)
    checker = Checker(inputs)
    if inputs.roads is None and sites:
        out.add('*', 'R0', 'road graph missing (mission/hollow-country/ai/road-graph.compact.json)')
    if inputs.geometry is None and not inputs.allow_reserve and sites:
        out.add('*', 'R0', 'class geometry missing (config/sites/class-geometry.json)')
    for site in sites:
        if site.id == '*':
            for e in site.errors:
                out.add('*', 'R0', e)
            continue
        for rule in (checker.r0, checker.r1, checker.r2, checker.r3, checker.r4, checker.r5, checker.r7, checker.r8):
            rule(site, out)
    check_density(inputs, sites, out)
    return out


def check_rebuild(inputs, root, out):
    """R8: the composer rebuilt from the same inputs must produce the committed bytes."""
    if not inputs.composed_files:
        return
    if inputs.rebuild is None:
        out.add('*', 'R8', 'tools.package.site_composer.rebuild_bytes is not available; determinism not shown')
        return
    try:
        built = inputs.rebuild(root)
    except Exception as exc:  # the hook is foreign code: any failure is a finding, never a crash
        out.add('*', 'R8', 'composer rebuild failed: %s' % type(exc).__name__)
        return
    for path in inputs.composed_files:
        rel = str(Path(path).relative_to(root)) if Path(path).is_absolute() else str(path)
        if rel not in built:
            out.add('*', 'R8', 'composer did not rebuild %s' % rel)
        elif Path(path).read_bytes() != built[rel]:
            out.add('*', 'R8', '%s differs from a fresh rebuild' % rel)


def load_composed_sites(inputs):
    sites = []
    for path in inputs.composed_files:
        sites += composed_sites(_json(path))
    return sites


def format_findings(out, detail=3):
    lines = []
    by_site = defaultdict(lambda: defaultdict(list))
    for site, rule, text in out.rows:
        by_site[site][rule].append(text)
    for site in sorted(by_site):
        for rule in RULES:
            items = by_site[site].get(rule)
            if not items:
                continue
            for text in items[:detail]:
                lines.append('FAIL %s %s %s' % (site, rule, text[:220]))
            if len(items) > detail:
                lines.append('FAIL %s %s (+%d more)' % (site, rule, len(items) - detail))
    return lines


def summary_line(out, sites, label):
    counts = defaultdict(int)
    failing = set()
    for site, rule, _text in out.rows:
        counts[rule] += 1
        failing.add(site)
    rules = ' '.join('%s=%d' % (r, counts[r]) for r in RULES if counts[r])
    real = [s for s in sites if s.id != '*']
    return 'site_rules: %s sites=%d failing=%d run_level=%d findings=%d %s' % (
        label, len(real), len(failing - {'*'}), counts_star(out), len(out.rows), rules)


def counts_star(out):
    return sum(1 for site, _r, _t in out.rows if site == '*')


def audit_parity(inputs, sites):
    """report-current only: the numbers of the design audit (1.3) recomputed, so a drift is visible."""
    roads = inputs.roads
    if roads is None:
        return []
    bound = [s for s in sites if s.legacy and s.kind == 'road']
    dists, near10, lane20, hard_on = [], 0, 0, 0
    for s in bound:
        hit = roads.nearest(s.origin[0], s.origin[2], 400.0)
        if hit is None:
            continue
        dists.append(hit[0])
        near10 += hit[0] <= 10.0
        lane20 += hit[0] <= 15.0 and fold(s.forward, hit[2]) <= 20.0
    for s in sites:
        if not s.legacy:
            continue
        for o in s.objects:
            hit = roads.nearest(o.x, o.z, 40.0)
            if hit and hit[0] < 4.0 and inputs.kind(o.cls) in HARD_KINDS:
                hard_on += 1
                break
    lines = ['audit-parity: road-bound sites=%d median_road_m=%s within_10m=%d lane_within_20deg=%d'
             % (len(bound), _r(statistics.median(dists)) if dists else 'none', near10, lane20),
             'audit-parity: sites_with_hard_piece_on_road=%d' % hard_on]
    return lines


def report_current(root, mission, detail, stream, summary_only=False):
    inputs = load_inputs(root, mission, composed=False, allow_reserve=True)
    sites = legacy_sites(root, inputs)
    out = run(inputs, sites, with_archetypes=False)
    notes = []
    if inputs.survey is None:
        notes.append('survey missing: R5 fails every site with a hard piece')
    if inputs.geometry is None:
        notes.append('class-geometry.json missing: geometry from footprint_reserve_m (front yaw 0)')
    if inputs.stock is None:
        notes.append('stock mission unavailable: stock building clearance not checked')
    for line in () if summary_only else format_findings(out, detail):
        print(line, file=stream)
    for line in audit_parity(inputs, sites):
        print(line, file=stream)
    for n in notes:
        print('note: ' + n, file=stream)
    print(summary_line(out, sites, 'report-current (never gates)'), file=stream)
    return 0


def gate(root, mission, detail, stream):
    inputs = load_inputs(root, mission)
    sites = load_composed_sites(inputs)
    out = run(inputs, sites)
    check_rebuild(inputs, root, out)
    profile = _json(Path(root) / 'config/map-overlays/profile.json')
    have = {_json(p).get('id') for p in inputs.composed_files}
    for layer_id in profile.get('enabled', []):
        if layer_id.startswith('composed-') and layer_id not in have:
            out.add('*', 'R0', 'profile enables layer %s but no such composed layer exists' % layer_id)
    for line in format_findings(out, detail):
        print(line, file=stream)
    label = 'composed_layers=%d archetypes=%d' % (len(inputs.composed_files), len(inputs.archetypes))
    print(summary_line(out, sites, label), file=stream)
    if not out.rows:
        print('site_rules: PASS ' + label + ' (offline geometry only; not DayZ behaviour)', file=stream)
    return 1 if out.rows else 0


def main(argv=None, stream=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--mission', type=Path, default=None, help='pristine mission dir with mapgrouppos.xml')
    parser.add_argument('--report-current', action='store_true', help="run over today's layers; never gates")
    parser.add_argument('--summary', action='store_true', help='report-current: print only the summary lines')
    parser.add_argument('--detail', type=int, default=3, help='findings printed per site and rule')
    args = parser.parse_args(argv)
    stream = stream or sys.stdout
    if args.report_current:
        return report_current(args.repo, args.mission, args.detail, stream, args.summary)
    return gate(args.repo, args.mission, args.detail, stream)


if __name__ == '__main__':
    raise SystemExit(main())
