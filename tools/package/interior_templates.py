"""Offline builder for the class-level interior template pack (docs/INTERIOR_TEMPLATES_CONTRACT.md, T2).

    python3 tools/package/interior_templates.py build --census census.json [--census more.json] \
        --proto mapgroupproto.xml --pos mapgrouppos.xml [--types types.xml] --out <empty dir outside the checkout>

Inputs are the native interior sampler census (one or more runs; each carries ``native_run_id`` and
``house_classes``, the House denominator) plus the stock ``mapgroupproto.xml`` and ``mapgrouppos.xml``,
which are passed as paths and never committed. Output is ``classes-NNN.json`` (one row per House
class), ``t-NNNN.json`` (one template per covered class, model frame), ``furnish-NNN.json`` (instances,
at most 1,500 props) and ``build-manifest.json`` (pins for the assembler; the game never reads it).
Search sites require ``types.xml`` so their group IDs bind only to emitted search groups.

Everything is provisional room evidence: the census is sampled geometry, the prop boxes are
reviewed native log boxes when available, otherwise conservative guesses; the stock frame comes from the sampler's native verdict. Nothing here shows
how DayZ places, renders or spawns anything; runtime acceptance stays pending.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

try:
    from tools.audit import interior_points as pts
    from tools.package import interior_catalog
    from tools.package.search_context import CONTAINERS, group_ids
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.audit import interior_points as pts
    from tools.package import interior_catalog
    from tools.package.search_context import CONTAINERS, group_ids

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 2
EVIDENCE_KIND = "native-room-survey-v1"
MANIFEST_NAME = "build-manifest.json"
FILE_CAP = 32767
MAX_CLASSES = 2048
MAX_TEMPLATES = 512
CLASS_ROWS, CLASS_CHUNKS = 160, 16
FURNISH_ROWS, FURNISH_CHUNKS = 128, 16
MAX_FURNISHED = 1500
MAX_ROOMS, MAX_KEEPOUTS, MAX_SLOTS, MAX_SITES = 16, 32, 5, 24
SITE_RADIUS_MIN, SITE_RADIUS_MAX = 0.25, 8.0
SITE_RADIUS_STEPS = (2.0, 3.0, 4.0, 6.0, 8.0)
SOURCES = CONTAINERS
MODEL_LIMIT = 512.0
MIN_ROOM_CELLS = 4
ANCHOR_SPACING = 1.0
DOOR_SWING = 1.2
DOOR_FLOOR_MARGIN = 0.6
STAIR_MIN_RISE, STAIR_MAX_RISE = 0.35, 1.0
INSTANCE_RADIUS = 0.75
SLOT_GAP = 0.3
WALL_INSET = 0.05
TOWN_USAGES = ("Town", "Village")
MAX_POS_ROWS = 200000
DEFAULT_MIN_AGREEMENT = 0.6
EPS = 1e-6
FIELDS = ("Rooms", "Furniture", "Search")
REASONS = ("unmeasured", "not_enterable", "path_pending", "door_pending", "unsupported_geometry",
           "frame_unverified", "clearance_failed", "no_ce_points", "not_in_mapgrouppos", "over_budget")
RUN_ID = re.compile(r"[0-9a-f]{32}")
CLASS_NAME = re.compile(r"[A-Za-z0-9_]{1,128}")
HISTORIES = ("family", "ransacked", "abandoned")
BOXES_PATH = Path(__file__).with_name("interior_prop_boxes.json")
BOX_LOG_LIMIT = 64 * 1024 * 1024
BOX_MARKER = "[HC Interiors] prop box "
BOX_LINE = re.compile(r"type=([A-Za-z0-9_]+) min=<([^<>]+)> max=<([^<>]+)>\s*\"?\s*$")
# The schema-1 pilot stays frozen. Class templates use the separately reviewed catalog.
_SIZES = {name: spec["Size"] for name, spec in interior_catalog.PROPS.items()}
PROP_ORDER = tuple(_SIZES)
PROP_TYPES = {name: {"History": list(spec["History"]), "Size": spec["Size"],
                     "BoxSource": "conservative guess (NOT measured)"}
              for name, spec in interior_catalog.PROPS.items()}
# (wall direction x, z, yaw that faces away from that wall); yaw 0 faces +z, which is unobserved natively.
WALLS = ((0, -1, 0), (0, 1, 180), (-1, 0, 90), (1, 0, 270))


class TemplateError(ValueError):
    """The inputs or parameters cannot produce a template pack."""


class Build:
    def __init__(self, files, summary, manifest):
        self.files, self.summary, self.manifest = files, summary, manifest


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def generator_sha256(boxes_bytes=None):
    """Pin all generator inputs without adding unrecognised runtime Source keys."""
    if boxes_bytes is None:
        boxes_bytes = _read(BOXES_PATH, FILE_CAP)
    return sha256(_dump({"interior_templates.py": sha256(Path(__file__).read_bytes()),
                         "interior_catalog.py": sha256(Path(interior_catalog.__file__).read_bytes()),
                         "interior_prop_boxes.json": sha256(boxes_bytes)}))


def load_boxes(raw):
    """Small reviewed native-box database; no synthetic measurements ship by default."""
    try:
        if not isinstance(raw, bytes) or not 0 < len(raw) <= FILE_CAP:
            raise TemplateError("prop boxes exceed file cap or are empty")
        data = json.loads(raw.decode("ascii"), object_pairs_hook=interior_catalog.json_pairs,
                          parse_constant=interior_catalog.reject_constant)
        interior_catalog.fields(data, "SchemaVersion Build Props")
        if type(data["SchemaVersion"]) is not int or data["SchemaVersion"] != 1 or data["Build"] != interior_catalog.BUILD:
            raise TemplateError("unsupported prop box schema/build")
        if not isinstance(data["Props"], dict) or not set(data["Props"]) <= set(PROP_TYPES):
            raise TemplateError("unknown prop box class")
        for entry in data["Props"].values():
            interior_catalog.fields(entry, "Min Max Width Depth Height SourceLogSha256")
            low, high = interior_catalog.box({k: entry[k] for k in ("Min", "Max")})
            sizes = [high[i] - low[i] for i in (0, 2, 1)]
            for key, size in zip(("Width", "Depth", "Height"), sizes):
                value = interior_catalog.number(entry[key], .001, 20)
                if not math.isclose(value, size, abs_tol=1e-8):
                    raise TemplateError("prop dimensions differ from native bounds")
            if not isinstance(entry["SourceLogSha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["SourceLogSha256"]):
                raise TemplateError("invalid source log sha256")
        return data
    except (ValueError, UnicodeError, TypeError, KeyError, RecursionError) as error:
        raise TemplateError("invalid prop boxes: " + str(error)) from error


def ingest_boxes(log_bytes, previous=None):
    """Merge only explicit native box diagnostics; refuse malformed/conflicting rows."""
    if not isinstance(log_bytes, bytes) or len(log_bytes) > BOX_LOG_LIMIT:
        raise TemplateError("prop box log outside byte limit")
    data = load_boxes(previous) if previous is not None else {"SchemaVersion": 1, "Build": interior_catalog.BUILD, "Props": {}}
    measured = {}
    for line in log_bytes.decode("utf-8", errors="replace").splitlines():
        if BOX_MARKER not in line:
            continue
        match = BOX_LINE.fullmatch(line.split(BOX_MARKER, 1)[1])
        if not match or match[1] not in PROP_TYPES:
            raise TemplateError("malformed or unknown native prop box line")
        try:
            low, high = list(_triple(match[2])), list(_triple(match[3]))
        except ValueError as error:
            raise TemplateError("invalid native prop box vector") from error
        entry = {"Min": low, "Max": high, "Width": high[0] - low[0], "Depth": high[2] - low[2],
                 "Height": high[1] - low[1], "SourceLogSha256": sha256(log_bytes)}
        if match[1] in measured and measured[match[1]] != entry:
            raise TemplateError("conflicting native boxes for " + match[1])
        measured[match[1]] = entry
    if not measured:
        raise TemplateError("no native prop box lines found")
    for name, entry in measured.items():
        reviewed = data["Props"].get(name)
        if reviewed is None:
            data["Props"][name] = entry
        elif (reviewed["Min"], reviewed["Max"]) != (entry["Min"], entry["Max"]):
            # A reviewed measurement changes only by editing the reviewed file.
            raise TemplateError("native box for " + name + " differs from the reviewed measurement")
    return load_boxes(_dump(data))


def prop_specs(boxes_bytes):
    measured = load_boxes(boxes_bytes)["Props"]
    specs = {name: dict(spec) for name, spec in PROP_TYPES.items()}
    for name, entry in measured.items():
        # Retain origin offsets. Include the origin for reader admission, and grow 1 cm
        # for log/JSON rounding. Native dimensions alone cannot safely centre a model.
        low = [min(0, v) - .01 for v in entry["Min"]]
        high = [max(0, v) + .01 for v in entry["Max"]]
        specs[name].update(Size=tuple(high[i] - low[i] for i in (0, 2, 1)),
                           NativeMin=low, NativeMax=high, BoxSource="measured")
    return specs


def _dump(document):
    return (json.dumps(document, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def _r(value):
    return round(float(value), 3) + 0.0


def _vec(values):
    return [_r(v) for v in values]


# ----------------------------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------------------------

def _class_name(value):
    return isinstance(value, str) and CLASS_NAME.fullmatch(value) is not None


def _house_signature(row):
    return {key: value for key, value in row.items() if key != "native_run_id"}


def _check_house_conflicts(rows, seen):
    for row in rows:
        name = row["class"]
        value = _house_signature(row)
        if name in seen and seen[name] != value:
            raise TemplateError("conflicting House config values for " + name)
        seen[name] = value


def load_census(data):
    """Validate real T1 placement House objects; legacy fixtures remain explicitly synthetic."""
    from tools.setup.interior_sampler import house_rows

    document = pts.parse_census(data)
    run = document.get("native_run_id")
    if not isinstance(run, str) or not RUN_ID.fullmatch(run):
        raise TemplateError("census native_run_id must be 32 lowercase hex characters")
    synthetic = document.get("Synthetic") is True and "house_classes" in document
    houses = [] if synthetic else house_rows(document)
    _check_house_conflicts(houses, {})
    for row in houses:
        vectors = [row["box_min"], row["box_max"]]
        vectors += [d["position"] for d in row["doors"] + row["door_selections"]]
        if (not _within_model(vectors)
                or any(a >= b for a, b in zip(row["box_min"], row["box_max"]))):
            raise TemplateError("House model-frame box/doors outside ±512 m or inverted")
    for row in document["placements"]:
        if row.get("found") is True:
            vectors = [row[k] for k in ("box_min", "box_max") if k in row]
            vectors += [hit[:3] for hit in row["hits"]]
            door_run = row.get("door_run")
            if isinstance(door_run, dict):
                vectors += [door[:3] for door in door_run.get("doors", [])]
            if not _within_model(vectors):
                raise TemplateError("census model-frame coordinates outside ±512 m")
    listed = document["house_classes"] if synthetic else sorted({row["class"] for row in houses})
    if not isinstance(listed, list) or (synthetic and not listed):
        raise TemplateError("census house_classes must be a non-empty list (synthetic fixture only)")
    names = []
    for item in listed:
        name = item.get("class") if isinstance(item, dict) else item
        if not _class_name(name):
            raise TemplateError("house class names must be ASCII identifiers of at most 128 characters")
        names.append(name)
    if len(set(names)) != len(names):
        raise TemplateError("house_classes lists a class twice")
    if synthetic and {row["class"] for row in document["placements"]} - set(names):
        raise TemplateError("census placements name classes outside house_classes")
    canonical = dict(document, house_classes=sorted(names),
                     placements=sorted(json.dumps(row, sort_keys=True) for row in document["placements"]))
    return {"doc": document, "run": run, "classes": names, "houses": houses, "sha": sha256(data),
            "canon": sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("ascii"))}


def load_censuses(censuses, proto):
    """Batch adapter: canonical House configs must agree; stock remains the audit denominator."""
    docs = sorted((load_census(data) for data in censuses), key=lambda d: d["run"])
    if len({d["run"] for d in docs}) != len(docs):
        raise TemplateError("two censuses share one native_run_id")
    seen = {}
    for document in docs:
        _check_house_conflicts(document["houses"], seen)
    names = sorted(parse_proto(proto))
    if not 1 <= len(names) <= MAX_CLASSES or not all(_class_name(n) for n in names):
        raise TemplateError("stock House denominator outside supported bounds")
    return docs, names


def _number(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("non-finite number")
    return value


def _triple(text):
    parts = text.split()
    if len(parts) != 3:
        raise ValueError("expected three numbers")
    return tuple(_number(p) for p in parts)


def parse_proto(xml):
    """{class: {usages, containers: [{name, categories, tags, points: [(x, y, z, range, height)]}]}}."""
    root = pts._parse_xml(xml)
    groups = {}
    for node in root.iter("group"):
        name = node.get("name")
        if not name:
            raise TemplateError("proto group without a name")
        if name in groups:
            raise TemplateError("proto lists group %s twice" % name)
        containers = []
        for child in node.findall("container"):
            points = []
            for item in child.findall("point"):
                try:
                    x, y, z = _triple(item.get("pos", ""))
                    rng, height = _number(item.get("range", "0")), _number(item.get("height", "0"))
                except ValueError as error:
                    raise TemplateError("unreadable point in %s/%s" % (name, child.get("name"))) from error
                if rng < 0 or height < 0:
                    raise TemplateError("negative point range or height in %s" % name)
                points.append((x, y, z, rng, height))
            containers.append({"name": child.get("name", ""),
                               "categories": sorted({c.get("name", "") for c in child.findall("category")}),
                               "tags": sorted({t.get("name", "") for t in child.findall("tag")}),
                               "points": points})
        groups[name] = {"usages": sorted({u.get("name", "") for u in node.findall("usage")}),
                        "containers": containers}
    return groups


def parse_pos(xml):
    """[(class, (x, y, z), yaw)] in document order."""
    root = pts._parse_xml(xml)
    rows = []
    for node in root.iter("group"):
        try:
            position, yaw = _triple(node.get("pos", "")), _number(node.get("a", ""))
        except ValueError as error:
            raise TemplateError("unreadable mapgrouppos row for %s" % node.get("name")) from error
        if not node.get("name"):
            raise TemplateError("mapgrouppos group without a name")
        rows.append((node.get("name"), tuple(round(v, 6) + 0.0 for v in position), round(yaw, 6) + 0.0))
        if len(rows) > MAX_POS_ROWS:
            raise TemplateError("mapgrouppos has too many rows")
    return rows


# ----------------------------------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------------------------------

def _box(low, high):
    return {"Min": _vec(low), "Max": _vec(high)}


def _overlap(a, b, margin=0.0, axes=(0, 1, 2)):
    return all(a["Min"][i] - margin < b["Max"][i] and b["Min"][i] < a["Max"][i] + margin for i in axes)


def _union(boxes):
    return _box([min(b["Min"][i] for b in boxes) for i in range(3)], [max(b["Max"][i] for b in boxes) for i in range(3)])


def _within_model(vectors):
    return all(abs(v) <= MODEL_LIMIT for vec in vectors for v in vec)


def _components(keys, neighbours):
    seen, result = set(), []
    for start in sorted(keys):
        if start in seen:
            continue
        seen.add(start)
        order, queue = [], [start]
        while queue:
            current = queue.pop()
            order.append(current)
            for other in neighbours(current):
                if other in keys and other not in seen:
                    seen.add(other)
                    queue.append(other)
        result.append(sorted(order))
    return result


# ----------------------------------------------------------------------------------------------
# Rooms, keep-outs and prop slots
# ----------------------------------------------------------------------------------------------

def _measure(docs, name, frame, reach_source, min_agreement):
    """(reason, None) or (None, measurement) for one class."""
    best = None
    for item in docs:
        rows = [row for row in item["doc"]["placements"] if row["class"] == name]
        if rows:
            usable = sum(1 for row in rows if pts._usable(row))
            if best is None or usable > best[0]:
                best = (usable, item, rows)
    if best is None:
        return "unmeasured", None
    _usable, item, rows = best
    usable_rows = [row for row in rows if pts._usable(row)]
    if not usable_rows:
        return ("unsupported_geometry" if any(row.get("found") is True for row in rows) else "unmeasured"), None
    if frame is None:
        return "frame_unverified", None
    gated = [row for row in usable_rows if pts._gate_passed(row, reach_source)]
    if not gated:
        return "path_pending", None
    valid = [row for row in gated if pts._door_run_problem(row.get("door_run")) is None]
    if not valid:
        return "door_pending", None
    try:
        result = pts.class_candidates(item["doc"], name, reach_source=reach_source)
    except ValueError:
        return "path_pending", None
    if result["reach_mode"] != "known":
        return "path_pending", None
    chosen = pts.eligible(result["candidates"], result["reach_mode"], min_agreement)
    if not chosen:
        if any(c["reachable"] is True for c in result["candidates"]):
            return "unsupported_geometry", None
        return "not_enterable", None
    doors = {}
    for row in valid:
        for door in row["door_run"]["doors"]:
            doors.setdefault(tuple(round(v * 4) for v in door[:3]), tuple(door[:3]))
    return None, {"run": item, "result": result, "cells": chosen, "doors": [doors[k] for k in sorted(doors)],
                   # Inward millimetre rounding keeps emitted bounds inside every observed model box.
                   "model": {"Min": [math.ceil(max(r["box_min"][i] for r in valid) * 1000) / 1000 for i in range(3)],
                             "Max": [math.floor(min(r["box_max"][i] for r in valid) * 1000) / 1000 for i in range(3)]}}


def _lattice(candidates, step):
    x0 = min(c["x"] for c in candidates)
    z0 = min(c["z"] for c in candidates)
    return x0, z0


def _door_covers(door, cell):
    return (abs(cell["x"] - door[0]) <= DOOR_SWING + EPS and abs(cell["z"] - door[2]) <= DOOR_SWING + EPS
            and door[1] - 2.0 <= cell["y"] <= door[1] + 0.3)


def _build_rooms(measurement):
    result, step = measurement["result"], measurement["result"]["step"]
    x0, z0 = _lattice(result["candidates"], step)

    def key(cell):
        return (round((cell["x"] - x0) / step), round((cell["z"] - z0) / step), cell["storey"])

    free = {}
    for cell in measurement["cells"]:
        if not any(_door_covers(door, cell) for door in measurement["doors"]):
            free[key(cell)] = cell
    groups = _components(free, lambda k: ((k[0] + 1, k[1], k[2]), (k[0] - 1, k[1], k[2]),
                                          (k[0], k[1] + 1, k[2]), (k[0], k[1] - 1, k[2])))
    rooms = []
    for members in groups:
        if len(members) < MIN_ROOM_CELLS:
            continue
        cells = [free[k] for k in members]
        mean_x = sum(c["x"] for c in cells) / len(cells)
        mean_z = sum(c["z"] for c in cells) / len(cells)
        anchor = min(zip(members, cells), key=lambda pair: ((pair[1]["x"] - mean_x) ** 2
                                                           + (pair[1]["z"] - mean_z) ** 2, pair[0]))[1]
        floors = sorted(c["y"] for c in cells)
        low = (min(c["x"] for c in cells) - step / 2, min(floors) - 0.05, min(c["z"] for c in cells) - step / 2)
        high = (max(c["x"] for c in cells) + step / 2, max(c["y"] + c["clearance"] for c in cells),
                max(c["z"] for c in cells) + step / 2)
        rooms.append({"members": members, "cells": dict(zip(members, cells)), "box": _box(low, high),
                      "anchor": _vec((anchor["x"], anchor["y"] + 0.05, anchor["z"])),
                      "floor": _r(floors[len(floors) // 2]), "count": len(cells)})
    rooms.sort(key=lambda r: (-r["count"], r["members"][0]))
    kept = []
    for room in rooms:
        if len(kept) == MAX_ROOMS:
            break
        if all(math.dist(room["anchor"], other["anchor"]) >= ANCHOR_SPACING for other in kept):
            kept.append(room)
    for index, room in enumerate(kept, 1):
        room["id"] = index
    return kept, (x0, z0), step


def _stair_boxes(measurement, step):
    cells = [c for c in measurement["result"]["candidates"] if c["clearance_ok"]]
    if not cells:
        return []
    x0, z0 = _lattice(cells, step)
    columns = {}
    for index, cell in enumerate(cells):
        columns.setdefault((round((cell["x"] - x0) / step), round((cell["z"] - z0) / step)), []).append(index)
    links = {}
    for (ix, iz), members in columns.items():
        for other in ((ix + 1, iz), (ix, iz + 1)):
            for first in members:
                for second in columns.get(other, ()):
                    rise = abs(cells[first]["y"] - cells[second]["y"]) / step
                    if STAIR_MIN_RISE < rise <= STAIR_MAX_RISE:
                        links.setdefault(first, set()).add(second)
                        links.setdefault(second, set()).add(first)
    boxes = []
    for members in _components(set(links), lambda k: links[k]):
        picked = [cells[i] for i in members]
        boxes.append(_box((min(c["x"] for c in picked) - step / 2, min(c["y"] for c in picked) - 0.05,
                           min(c["z"] for c in picked) - step / 2),
                          (max(c["x"] for c in picked) + step / 2, max(c["y"] + c["clearance"] for c in picked),
                           max(c["z"] for c in picked) + step / 2)))
    return boxes


def _gap(a, b):
    return math.sqrt(sum(max(a["Min"][i] - b["Max"][i], b["Min"][i] - a["Max"][i], 0.0) ** 2 for i in range(3)))


def _merge_keepouts(boxes):
    """Merge the closest same-kind pairs (bounding boxes only grow) until at most MAX_KEEPOUTS remain."""
    boxes = [dict(b) for b in boxes]
    while len(boxes) > MAX_KEEPOUTS:
        counts = {}
        for box in boxes:
            counts[box["Kind"]] = counts.get(box["Kind"], 0) + 1
        kind = max(sorted(counts), key=lambda k: counts[k])
        indices = [i for i, b in enumerate(boxes) if b["Kind"] == kind]
        best = None
        for a in range(len(indices)):
            for b in range(a + 1, len(indices)):
                score = (_gap(boxes[indices[a]], boxes[indices[b]]), indices[a], indices[b])
                if best is None or score < best:
                    best = score
        _gap_value, first, second = best
        merged = _union([boxes[first], boxes[second]])
        merged["Kind"] = kind
        boxes[first] = merged
        del boxes[second]
    return boxes


def _clip(box, model):
    low = [max(box["Min"][i], model["Min"][i]) for i in range(3)]
    high = [min(box["Max"][i], model["Max"][i]) for i in range(3)]
    return _box(low, high) if all(low[i] < high[i] for i in range(3)) else None


def _keepouts(measurement, rooms, step, model, stock_points, frame):
    boxes = [{"Kind": "door", **_box([v - DOOR_SWING for v in door],
                                     [v + DOOR_SWING for v in door])} for door in measurement["doors"]]
    boxes += [{"Kind": "stair", **b} for b in _stair_boxes(measurement, step)]
    for x, y, z, rng, height in stock_points:
        sx, sy, sz = pts.stock_to_sampler((x, y, z), frame)
        rng, height = max(rng, 0.05), max(height, 0.05)
        boxes.append({"Kind": "ce-point", **_box((sx - rng, sy, sz - rng),
                                                  (sx + rng, sy + height, sz + rng))})
    clipped, dropped = [], 0
    for box in boxes:
        bounded = _clip(box, model)
        if bounded is None:
            dropped += 1
        else:
            clipped.append({"Kind": box["Kind"], **bounded})
    merged = _merge_keepouts(clipped)
    order = {"door": 0, "stair": 1, "ce-point": 2}
    merged.sort(key=lambda b: (order[b["Kind"]], b["Min"], b["Max"]))
    counters, rows = {}, []
    for item in merged:
        index = counters.get(item["Kind"], 0)
        counters[item["Kind"]] = index + 1
        rows.append({"Kind": item["Kind"], "Index": index, "Min": item["Min"], "Max": item["Max"]})
    return rows, dropped


def _connected(members, removed, neighbours):
    rest = set(members) - removed
    return bool(rest) and len(_components(rest, neighbours)) == 1


def _place(kind, room, lattice, step, keepouts, taken, specs=None):
    spec = (PROP_TYPES if specs is None else specs)[kind]
    width, depth, height = spec["Size"]
    x0, z0 = lattice
    members = set(room["members"])

    def near(k):
        return ((k[0] + 1, k[1], k[2]), (k[0] - 1, k[1], k[2]), (k[0], k[1] + 1, k[2]), (k[0], k[1] - 1, k[2]))

    for member in room["members"]:
        cell = room["cells"][member]
        for dx, dz, yaw in WALLS:
            if (member[0] + dx, member[1] + dz, member[2]) in members:
                continue
            inset = step / 2 - depth / 2 - WALL_INSET
            cx, cz = cell["x"] + dx * inset, cell["z"] + dz * inset
            fx, fz = (depth, width) if dx else (width, depth)
            bounds = _box((cx - fx / 2, cell["y"], cz - fz / 2), (cx + fx / 2, cell["y"] + height, cz + fz / 2))
            lo_x = math.floor((bounds["Min"][0] - x0) / step + 0.5 + EPS)
            hi_x = math.ceil((bounds["Max"][0] - x0) / step - 0.5 - EPS)
            lo_z = math.floor((bounds["Min"][2] - z0) / step + 0.5 + EPS)
            hi_z = math.ceil((bounds["Max"][2] - z0) / step - 0.5 - EPS)
            footprint = {(i, j, member[2]) for i in range(lo_x, hi_x + 1) for j in range(lo_z, hi_z + 1)}
            if not footprint <= members:
                continue
            if any(abs(room["cells"][k]["y"] - cell["y"]) > 0.1 or room["cells"][k]["clearance"] < height + 0.05
                   for k in footprint):
                continue
            if not _inside(room["box"], bounds):
                continue
            blocked = False
            for keep in keepouts:
                if keep["Kind"] == "door":
                    blocked = blocked or _overlap(bounds, keep, DOOR_FLOOR_MARGIN + EPS, (0, 2))
                else:
                    # The reader rejects touching faces as well as positive-volume intersections.
                    blocked = blocked or all(bounds["Max"][i] >= keep["Min"][i]
                                              and bounds["Min"][i] <= keep["Max"][i] for i in range(3))
            if blocked or any(_overlap(bounds, other["Bounds"], SLOT_GAP) for other in taken["slots"]):
                continue
            removed = taken["cells"].get(room["id"], set()) | footprint
            if not _connected(members, removed, near):
                continue
            taken["cells"][room["id"]] = removed
            origin = [cx, cell["y"], cz]
            if "NativeMin" in spec:
                low, high = spec["NativeMin"], spec["NativeMax"]
                center = [(low[i] + high[i]) / 2 for i in range(3)]
                ox, oz = {0: (center[0], center[2]), 90: (center[2], -center[0]),
                          180: (-center[0], -center[2]), 270: (-center[2], center[0])}[yaw]
                origin = [cx - ox, cell["y"] - low[1], cz - oz]
            return {"Room": room["id"], "Type": kind, "Position": _vec(origin),
                    "Orientation": [yaw, 0, 0], "Bounds": bounds, "History": list(spec["History"])}
    return None


def _point_inside(box, point):
    return all(box["Min"][i] <= point[i] <= box["Max"][i] for i in range(3))


def _inside(outer, inner):
    return all(outer["Min"][i] <= inner["Min"][i] and inner["Max"][i] <= outer["Max"][i] for i in range(3))


def _slots(rooms, lattice, step, keepouts, name="", specs=None):
    taken = {"slots": [], "cells": {}}
    # Class identity varies the catalog order; reserve a chance for each history
    # before filling spare slots. All candidate boxes still share the same keepouts.
    order = sorted(PROP_ORDER, key=lambda kind: sha256((name + "|" + kind).encode("ascii")))
    selected = []
    for history in HISTORIES:
        preferred = [k for k in order if history in PROP_TYPES[k]["History"]]
        if history == "abandoned":
            preferred.sort(key=lambda k: interior_catalog.PROPS[k]["Role"] not in ("rubbish", "clutter"))
        selected.append(preferred)
    selected.extend([[k] for k in order])
    for index, choices in enumerate(selected):
        if len(taken["slots"]) == MAX_SLOTS:
            break
        for kind in choices:
            if any(s["Type"] == kind for s in taken["slots"]):
                continue
            for offset in range(len(rooms)):
                room = rooms[(index + offset) % len(rooms)]
                slot = _place(kind, room, lattice, step, keepouts, taken, specs)
                if slot is not None:
                    taken["slots"].append({"Id": len(taken["slots"]) + 1, **slot})
                    break
            if slot is not None:
                break
    return [{key: slot[key] for key in ("Id", "Room", "Type", "Position", "Orientation", "Bounds", "History")}
            for slot in taken["slots"]]


# ----------------------------------------------------------------------------------------------
# Search sites
# ----------------------------------------------------------------------------------------------

def _sphere(members):
    center = [sum(m[1][i] for m in members) / len(members) for i in range(3)]
    reach = max(math.dist(center, m[1]) + m[2] for m in members)
    return center, max(SITE_RADIUS_MIN, math.ceil((reach + 0.001) * 1000) / 1000)


def _cluster(members, limit):
    clusters = [[m] for m in members]
    while True:
        spheres = [_sphere(c) for c in clusters]
        best = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                distance = math.dist(spheres[i][0], spheres[j][0])
                if distance > 2 * limit or (best is not None and distance >= best[0]):
                    continue
                if _sphere(clusters[i] + clusters[j])[1] <= limit:
                    best = (distance, i, j)
        if best is None:
            return clusters
        _d, i, j = best
        clusters[i] = clusters[i] + clusters[j]
        del clusters[j]


def _sites(group, ids, frame, rooms, model):
    """(sites, supported point count, dropped point count)."""
    by_source = {name: [] for name in SOURCES}
    for item in group["containers"]:
        if item["name"] not in by_source:
            continue
        gid = ids.get((tuple(group["usages"]), item["name"], tuple(item["categories"]), tuple(item["tags"])))
        for x, y, z, rng, _height in item["points"]:
            members = by_source[item["name"]]
            if gid is None or rng > SITE_RADIUS_MAX:
                members.append(None)
                continue
            members.append((len(members), pts.stock_to_sampler((x, y, z), frame), rng, gid))
    supported = sum(len(v) for v in by_source.values())
    points = {name: [m for m in members if m is not None] for name, members in by_source.items()}
    found = []
    for limit in SITE_RADIUS_STEPS:
        found = []
        for order, name in enumerate(SOURCES):
            for members in _cluster(points[name], limit):
                found.append((order, name, sorted(members, key=lambda m: m[0])))
        if len(found) <= MAX_SITES:
            break
    bounded = [f for f in found if _point_inside(model, _vec(_sphere(f[2])[0]))]
    outside = len(found) - len(bounded)
    found = bounded
    found.sort(key=lambda f: (-len(f[2]), f[0], f[2][0][0]))
    found = sorted(found[:MAX_SITES], key=lambda f: (f[0], f[2][0][0]))
    sites = []
    for order, name, members in found:
        center, radius = _sphere(members)
        center = _vec(center)
        sites.append({"Id": len(sites) + 1, "Room": _nearest_room(rooms, center) if rooms else 0, "Center": center,
                      "Radius": radius, "Source": name, "Points": [m[0] for m in members],
                      "Groups": sorted({m[3] for m in members})})
    return sites, supported, supported - sum(len(s["Points"]) for s in sites), outside


def _nearest_room(rooms, point):
    def distance(room):
        box = room["box"]
        return math.sqrt(sum(max(box["Min"][i] - point[i], point[i] - box["Max"][i], 0.0) ** 2 for i in range(3)))
    return min(rooms, key=lambda r: (distance(r), r["id"]))["id"]


# ----------------------------------------------------------------------------------------------
# Template, furnish and chunk assembly
# ----------------------------------------------------------------------------------------------

def _template(name, measurement, group, ids, frame, specs=None):
    rooms, lattice, step = _build_rooms(measurement)
    if not rooms:
        return "unsupported_geometry", None
    model = measurement["model"]
    bounded = []
    for room in rooms:
        clipped = _clip(room["box"], model)
        if clipped and _point_inside(clipped, room["anchor"]) and clipped["Min"][1] <= room["floor"] <= clipped["Max"][1]:
            room["box"] = clipped
            room["id"] = len(bounded) + 1
            bounded.append(room)
    rooms = bounded
    if not rooms:
        return "unsupported_geometry", None
    stock = [p for item in (group["containers"] if group else []) for p in item["points"]]
    keepouts, keeps_dropped = _keepouts(measurement, rooms, step, model, stock, frame)
    slots = _slots(rooms, lattice, step, keepouts, name, specs)
    sites, supported, dropped, sites_dropped = ([], 0, 0, 0)
    if group:
        sites, supported, dropped, sites_dropped = _sites(group, ids, frame, rooms, model)
    # Box is an admission envelope only; runtime search spheres/room anchors remain authoritative.
    box = _union([r["box"] for r in rooms] + keepouts +
                 [{"Min": s["Center"], "Max": s["Center"]} for s in sites])
    evidence = [{"Kind": EVIDENCE_KIND, "RunId": measurement["run"]["run"], "Sha256": measurement["run"]["sha"]}]
    document = {"SchemaVersion": SCHEMA_VERSION, "BuildingClass": name, "TemplateId": name.lower() + "-v1",
                "Box": box, "Evidence": evidence,
                "Rooms": [{"Id": r["id"], "Label": "room", "Min": r["box"]["Min"], "Max": r["box"]["Max"],
                           "Anchor": r["anchor"], "FloorY": r["floor"], "Cells": r["count"]} for r in rooms],
                "KeepOuts": keepouts, "PropSlots": slots, "SearchSites": sites}
    if len(_dump(document)) > FILE_CAP:
        raise TemplateError("template for %s exceeds %d bytes" % (name, FILE_CAP))
    return None, {"document": document, "supported": supported, "dropped": dropped,
                  "keepouts_dropped_outside_model": keeps_dropped, "sites_dropped_outside_model": sites_dropped}


# Rooms not yet proven by path/door evidence; the house geometry itself was measured.
SEARCH_ONLY_REASONS = ("path_pending", "door_pending", "not_enterable")


def _model_box(docs, name):
    """(run item, model bounds) from the census rows with usable geometry, or (None, None)."""
    best = None
    for item in docs:
        usable = [row for row in item["doc"]["placements"] if row["class"] == name and pts._usable(row)]
        if usable and (best is None or len(usable) > len(best[1])):
            best = (item, usable)
    if best is None:
        return None, None
    item, rows = best
    return item, {"Min": [math.ceil(max(r["box_min"][i] for r in rows) * 1000) / 1000 for i in range(3)],
                  "Max": [math.floor(min(r["box_max"][i] for r in rows) * 1000) / 1000 for i in range(3)]}


def _search_template(name, docs, group, ids, frame):
    """A search-only template: sites at the class's vanilla CE container points, no rooms, keep-outs or props."""
    item, model = _model_box(docs, name)
    if item is None or not group or any(model["Min"][i] >= model["Max"][i] for i in range(3)):
        return None
    sites, supported, dropped, sites_dropped = _sites(group, ids, frame, [], model)
    if not sites:
        return None
    # Admission envelope: the site spheres, clipped to the census model box (which holds every centre).
    box = _clip(_union([{"Min": [c - s["Radius"] for c in s["Center"]], "Max": [c + s["Radius"] for c in s["Center"]]}
                        for s in sites]), model)
    if not box:
        return None
    document = {"SchemaVersion": SCHEMA_VERSION, "BuildingClass": name, "TemplateId": name.lower() + "-search-v1",
                "Box": box, "Evidence": [{"Kind": EVIDENCE_KIND, "RunId": item["run"], "Sha256": item["sha"]}],
                "Rooms": [], "KeepOuts": [], "PropSlots": [], "SearchSites": sites}
    if len(_dump(document)) > FILE_CAP:
        raise TemplateError("template for %s exceeds %d bytes" % (name, FILE_CAP))
    return {"document": document, "supported": supported, "dropped": dropped, "search_only": True,
            "keepouts_dropped_outside_model": 0, "sites_dropped_outside_model": sites_dropped}


def _instances(rows):
    """Per class, the mapgrouppos instances that resolve to exactly one live object."""
    by_class = {}
    for name, position, yaw in rows:
        by_class.setdefault(name, []).append((position, yaw))
    result = {}
    for name, items in by_class.items():
        result[name] = [item for item in items
                        if sum(1 for other in items if math.dist(item[0], other[0]) <= INSTANCE_RADIUS) == 1]
    return result


def _furnish(templates, instances, proto, pack_id, limit):
    candidates = []
    for name, entry in templates.items():
        slots = entry["document"]["PropSlots"]
        if not slots:
            continue
        histories = [h for h in HISTORIES if any(h in s["History"] for s in slots)]
        town = 0 if set(proto.get(name, {"usages": []})["usages"]) & set(TOWN_USAGES) else 1
        for position, yaw in instances.get(name, ()):
            digest = sha256(("%s|%s|%r|%r" % (pack_id, name, position, yaw)).encode("ascii"))
            history = histories[int(digest[:8], 16) % len(histories)]
            props = [s["Id"] for s in slots if history in s["History"]][:MAX_SLOTS]
            if history == "abandoned":
                # Sparse storage/rubbish first; do not fill abandoned rooms to the cap.
                by_id = {s["Id"]: s for s in slots}
                props.sort(key=lambda pid: interior_catalog.PROPS[by_id[pid]["Type"]]["Role"] not in ("clutter", "rubbish"))
                props = props[:2]
            candidates.append(((town, digest), {"BuildingClass": name, "Position": list(position), "Yaw": yaw,
                                                "Props": props, "History": history}))
    candidates.sort(key=lambda pair: pair[0])
    rows, total = [], 0
    for _key, row in candidates:
        if total + len(row["Props"]) > limit:
            continue
        rows.append({"Slot": len(rows), **row})
        total += len(row["Props"])
        if total == limit:
            break
    return rows, total


def _chunks(prefix, rows, per_chunk, max_chunks, label):
    chunks, current = [], []
    for row in rows:
        trial = current + [row]
        too_big = len(_dump({"SchemaVersion": SCHEMA_VERSION, "Chunk": len(chunks), "Rows": trial})) > FILE_CAP
        if current and (len(trial) > per_chunk or too_big):
            chunks.append(current)
            current = [row]
        else:
            current = trial
    if current:
        chunks.append(current)
    if len(chunks) > max_chunks:
        raise TemplateError("%s need %d chunks; the limit is %d" % (label, len(chunks), max_chunks))
    return {"%s-%03d.json" % (prefix, i): _dump({"SchemaVersion": SCHEMA_VERSION, "Chunk": i, "Rows": rows_})
            for i, rows_ in enumerate(chunks)}


def _count(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def build(censuses, proto, pos, reach_source="strict", min_agreement=DEFAULT_MIN_AGREEMENT,
          max_furnished=MAX_FURNISHED, types_bytes=None, boxes_bytes=None):
    """Template pack files (name -> bytes), a summary and the manifest. Raises TemplateError on any refusal."""
    try:
        return _build(censuses, proto, pos, reach_source, min_agreement, max_furnished, types_bytes, boxes_bytes)
    except TemplateError:
        raise
    except ValueError as error:
        raise TemplateError(str(error)) from error


def _build(censuses, proto_bytes, pos_bytes, reach_source, min_agreement, max_furnished, types_bytes, boxes_bytes):
    if boxes_bytes is None:
        boxes_bytes = _read(BOXES_PATH, FILE_CAP)
    specs = prop_specs(boxes_bytes)
    if reach_source not in pts.REACH_SOURCES:
        raise TemplateError("reach_source must be one of " + ", ".join(pts.REACH_SOURCES))
    if (not isinstance(min_agreement, (int, float)) or isinstance(min_agreement, bool)
            or not 0 < min_agreement <= 1):
        raise TemplateError("min_agreement must be in (0, 1]")
    if not isinstance(max_furnished, int) or isinstance(max_furnished, bool) or not 0 <= max_furnished <= MAX_FURNISHED:
        raise TemplateError("max_furnished must be an integer in 0..%d" % MAX_FURNISHED)
    if not censuses:
        raise TemplateError("at least one census is required")
    docs = sorted((load_census(data) for data in censuses), key=lambda d: d["run"])
    if len({d["run"] for d in docs}) != len(docs):
        raise TemplateError("two censuses share one native_run_id")
    names = sorted({name for d in docs for name in d["classes"]})
    if len(names) > MAX_CLASSES:
        raise TemplateError("%d House classes exceed the limit of %d" % (len(names), MAX_CLASSES))
    proto, rows = parse_proto(proto_bytes), parse_pos(pos_bytes)
    ids = group_ids(proto_bytes, types_bytes)
    merged = {"placements": [row for d in docs for row in d["doc"]["placements"]]}
    frame_evidence = pts.frame_verdict(merged)
    deciding = {name: row["verdict"] for name, row in frame_evidence["classes"].items()
                if row["verdict"] is not None}
    verdicts = set(deciding.values())
    frame = next(iter(verdicts)) if len(verdicts) == 1 else None
    frame_evidence.update(verdict=frame, deciding_classes=sorted(deciding),
                          ignored_classes=sorted(set(frame_evidence["classes"]) - set(deciding)),
                          reason=("" if frame else "contradictory or no discriminating calibration classes"))
    if frame != "rot90":
        raise TemplateError("runtime templates require census frame rot90; got %r" % frame)
    instances = _instances(rows)
    generator = generator_sha256(boxes_bytes)
    sources = {"mapgroupproto": sha256(proto_bytes), "mapgrouppos": sha256(pos_bytes), "generator": generator}
    if types_bytes is not None:
        from tools.package import search_context
        sources.update({"types": sha256(types_bytes), "search-generator": search_context.generator_sha256()})
    for d in docs:
        sources["census-" + d["run"]] = d["sha"]
    parameters = {"reach_source": reach_source, "min_agreement": min_agreement, "max_furnished": max_furnished}
    pinned = dict(sources, **{"census-" + d["run"]: d["canon"] for d in docs})
    pack_id = sha256(_dump({"Sources": pinned, "Parameters": parameters}))[:32]

    reasons, templates, search_only = {}, {}, 0
    for name in names:
        reason, measurement = _measure(docs, name, frame, reach_source, min_agreement)
        group = proto.get(name)
        points = [c for c in (group["containers"] if group else []) if c["name"] in SOURCES and c["points"]]
        if reason is None:
            reason, built = _template(name, measurement, group, ids, frame, specs)
            if reason is None:
                templates[name] = built
        if reason in SEARCH_ONLY_REASONS and points:
            built = _search_template(name, docs, group, ids, frame)
            if built is not None:
                templates[name] = built
                reasons[name] = reason
                continue
        if reason is not None:
            reasons[name] = reason
            if frame is not None and points:
                search_only += 1
    # Paging bounds each metadata file; only the template count limits admission.
    ranked = sorted(templates, key=lambda n: (bool(templates[n].get("search_only")),
                                              -len(instances.get(n, ())), n))
    kept = 0
    for name in ranked:
        if kept >= MAX_TEMPLATES:
            break
        kept += 1
    over = set(ranked[kept:])
    for name in over:
        del templates[name]
        reasons[name] = "over_budget"

    furnish, total = _furnish(templates, instances, proto, pack_id, max_furnished)
    furnished = {row["BuildingClass"] for row in furnish}
    table = []
    for name in names:
        if name in templates:
            entry = templates[name]["document"]
            if not entry["PropSlots"]:
                furniture = "clearance_failed"
            elif not instances.get(name):
                furniture = "not_in_mapgrouppos"
            elif name not in furnished:
                furniture = "over_budget"
            else:
                furniture = "covered"
            search = ("covered" if entry["SearchSites"] else
                      "over_budget" if templates[name]["supported"] else "no_ce_points")
            if templates[name].get("search_only"):
                table.append({"BuildingClass": name, "Rooms": reasons[name], "Furniture": reasons[name],
                              "Search": search})
                continue
            table.append({"BuildingClass": name, "Rooms": "covered", "Furniture": furniture, "Search": search})
        else:
            reason = reasons[name]
            group = proto.get(name)
            has_points = any(c["name"] in SOURCES and c["points"] for c in (group["containers"] if group else []))
            if reason == "over_budget" or name in over:
                search = "over_budget"
            else:
                search = reason if has_points else "no_ce_points"
            table.append({"BuildingClass": name, "Rooms": reason, "Furniture": reason, "Search": search})

    files = _chunks("classes", table, CLASS_ROWS, CLASS_CHUNKS, "class rows")
    for index, name in enumerate(sorted(templates)):
        files["t-%04d.json" % index] = _dump(templates[name]["document"])
    files.update(_chunks("furnish", furnish, FURNISH_ROWS, FURNISH_CHUNKS, "furnish rows"))
    excluded = [{"BuildingClass": n, "Reason": "not_observed_as_house"} for n in sorted(set(proto) - set(names))]
    used_types = sorted({s["Type"] for t in templates.values() for s in t["document"]["PropSlots"]})
    summary = {"prop_boxes": {n: specs[n]["BoxSource"] for n in used_types},
               "histories": _count(r["History"] for r in furnish),
               "excluded_proto_classes": excluded,
               "keepouts_dropped_outside_model": sum(t["keepouts_dropped_outside_model"] for t in templates.values()),
               "sites_dropped_outside_model": sum(t["sites_dropped_outside_model"] for t in templates.values()),
               "classes": len(names), "templates": len(templates), "frame": frame,
               "furnish_rows": len(furnish), "furnish_props": total, "search_only_possible": search_only,
               "search_only_templates": sum(1 for t in templates.values() if t.get("search_only")),
               "search_points_dropped": sum(t["dropped"] for t in templates.values()),
               "unsupported_containers_dropped": sum(c["name"] not in SOURCES
                    for g in proto.values() for c in g["containers"]),
               "chunks": {"classes": len([n for n in files if n.startswith("classes-")]),
                          "furnish": len([n for n in files if n.startswith("furnish-")])}}
    for field in FIELDS:
        values = [row[field] for row in table]
        summary[field.lower()] = {"covered": values.count("covered"),
                                  "excluded": _count([v for v in values if v != "covered"])}
    manifest = {"SchemaVersion": SCHEMA_VERSION, "Kind": "hc-interior-templates-build", "PackId": pack_id,
                "Frame": frame, "FrameVerdict": frame_evidence, "ExcludedProtoClasses": excluded,
                "Provisional": True, "Sources": dict(sorted(sources.items())),
                "Parameters": parameters,
                "Files": [{"File": n, "Sha256": sha256(files[n]), "Bytes": len(files[n])} for n in sorted(files)]}
    return Build(files, summary, manifest)


def summary_lines(summary, pack_id):
    lines = ["interior templates: classes=%d templates=%d frame=%s pack=%s"
             % (summary["classes"], summary["templates"], summary["frame"], pack_id)]
    for field in FIELDS:
        entry = summary[field.lower()]
        excluded = " ".join("%s=%d" % (k, entry["excluded"][k]) for k in sorted(entry["excluded"])) or "none"
        lines.append("%s covered=%d excluded: %s" % (field.lower(), entry["covered"], excluded))
    lines.append("furnish rows=%d props=%d chunks=%d" % (summary["furnish_rows"], summary["furnish_props"],
                                                        summary["chunks"]["furnish"]))
    lines.append("search_only_possible=%d search_points_dropped=%d"
                 % (summary["search_only_possible"], summary["search_points_dropped"]))
    lines.append("excluded_proto_classes=%d keepouts_dropped_outside_model=%d sites_dropped_outside_model=%d"
                 % (len(summary.get("excluded_proto_classes", [])), summary.get("keepouts_dropped_outside_model", 0),
                    summary.get("sites_dropped_outside_model", 0)))
    for row in summary.get("excluded_proto_classes", []):
        lines.append("excluded proto %s: %s" % (row["BuildingClass"], row["Reason"]))
    lines.append("unsupported_containers_dropped=%d" % summary["unsupported_containers_dropped"])
    for name, source in summary.get("prop_boxes", {}).items():
        lines.append("prop box %s: %s" % (name, source))
    lines.append("histories: " + " ".join("%s=%d" % (h, summary.get("histories", {}).get(h, 0)) for h in HISTORIES))
    return lines


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------

def _read(path, limit):
    try:
        with open(path, "rb") as handle:
            data = handle.read(limit + 1)
    except OSError as error:
        raise TemplateError("cannot read %s: %s" % (path, error.strerror)) from error
    if len(data) > limit:
        raise TemplateError("%s is larger than %d bytes" % (path, limit))
    return data


def _output_dir(value):
    path = Path(value).absolute()
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise TemplateError("the output directory must be outside the git checkout")
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise TemplateError("the output directory %s is not empty" % path)
    return path


def _write(path, build_):
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise TemplateError("the output directory %s is not empty" % path)
    files = dict(build_.files)
    files[MANIFEST_NAME] = _dump(build_.manifest)
    for name in sorted(files):
        with open(path / name, "xb") as handle:
            handle.write(files[name])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="interior_templates", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="build classes-*, t-* and furnish-* into an empty directory")
    build_parser.add_argument("--census", action="append", required=True, help="sampler census (repeat per run)")
    build_parser.add_argument("--proto", required=True, help="stock mapgroupproto.xml")
    build_parser.add_argument("--pos", required=True, help="stock mapgrouppos.xml")
    build_parser.add_argument("--types", help="stock types.xml; required to emit search sites")
    build_parser.add_argument("--out", required=True, help="empty (or new) output directory outside the checkout")
    build_parser.add_argument("--reach-source", choices=pts.REACH_SOURCES, default="strict")
    build_parser.add_argument("--min-agreement", type=float, default=DEFAULT_MIN_AGREEMENT)
    build_parser.add_argument("--max-furnished", type=int, default=MAX_FURNISHED)
    ingest_parser = commands.add_parser("ingest-boxes", help="merge native box logs into the reviewed box database; review diff before building")
    ingest_parser.add_argument("--log", required=True, help="script log containing native prop box diagnostics")
    ingest_parser.add_argument("--out", type=Path, default=BOXES_PATH, help="reviewed box database (default: tools/package/interior_prop_boxes.json)")
    args = parser.parse_args(argv)
    try:
        if args.command == "ingest-boxes":
            destination = interior_catalog.checked_path(args.out)
            previous = _read(destination, FILE_CAP) if destination.exists() else None
            measured = ingest_boxes(_read(args.log, BOX_LOG_LIMIT), previous)
            raw = (json.dumps(measured, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("ascii")
            load_boxes(raw)  # Check the human-readable representation against FILE_CAP too.
            # All input validation precedes the atomic replacement.
            import tempfile
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(raw)
                os.chmod(temporary, 0o644)  # NamedTemporaryFile is 0600; the database is tracked.
                os.replace(temporary, destination)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
            print("prop boxes=%d; review native log measurements before rebuilding; acceptance pending" % len(measured["Props"]))
            return 0
        out = _output_dir(args.out)
        censuses = [_read(path, pts.MAX_CENSUS_BYTES) for path in args.census]
        result = build(censuses, _read(args.proto, pts.MAX_STOCK_BYTES), _read(args.pos, pts.MAX_STOCK_BYTES),
                       reach_source=args.reach_source, min_agreement=args.min_agreement,
                       max_furnished=args.max_furnished,
                       types_bytes=_read(args.types, pts.MAX_STOCK_BYTES) if args.types else None)
        _write(out, result)
    except (TemplateError, OSError, ValueError) as error:
        print("refused: %s" % error, file=sys.stderr)
        return 2
    for line in summary_lines(result.summary, result.manifest["PackId"]):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
