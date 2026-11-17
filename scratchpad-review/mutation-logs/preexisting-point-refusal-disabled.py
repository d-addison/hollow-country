"""Turn an interior-sampler census into a candidate tenement mapgroupproto treatment.

Input is the census written by tools/setup/interior_sampler.py after a native run. The census
is observation data: this tool aggregates it, measures how well it reproduces the STOCK points
of calibration buildings, and refuses to produce a treatment when that agreement is too low. It
proves nothing about DayZ spawning; a treatment is only a candidate that still needs normal
PBO/server testing. Output must be written outside the git checkout.

    python3 tools/audit/interior_points.py --census census.json --stock-proto stock/mapgroupproto.xml \
        --output /mnt/d/HollowCountryLocal/treatment/mapgroupproto.xml --report .../report.json \
        --min-calibration 0.6
"""
import argparse
from bisect import bisect_left, bisect_right
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

CENSUS_KIND = "interior-sampler-census"
TENEMENT_CLASSES = ("Land_Tenement_Small", "Land_Tenement_Big")
CALIBRATION_CLASSES = ("Land_HouseBlock_2F1", "Land_Mil_Barracks2")
MIN_CLEARANCE = 1.9
CALIBRATION_RADIUS = 0.5
MAX_SLOPE = 0.6
BAND_TOLERANCE = 0.25
HEIGHT_SPREAD_BOUND = 0.1
MAX_CENSUS_BYTES = 64 * 1024 * 1024
MAX_STOCK_BYTES = 16 * 1024 * 1024
MAX_PLACEMENTS = 64
MAX_HITS_PER_PLACEMENT = 2000000
MAX_POINTS_PER_CLASS = 256
VERTICAL_BELOW = 0.5
POINT_RANGE = "0.400000"
POINT_HEIGHT = "1.000000"
DEFAULT_MIN_CALIBRATION = 0.6
OFF_GRID_TOLERANCE = 0.1
EPSILON = 1e-9
FLOOR_CONTAINER = "lootFloor"


class CoverageError(ValueError):
    """Calibration agreement is too low, or there is no calibration data to measure it."""


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _reject_constant(name):
    raise ValueError(f"non-finite JSON constant {name}")


def parse_census(data):
    """Validate and return the census document; raise ValueError on anything unexpected."""
    if not isinstance(data, (bytes, bytearray)) or not data or len(data) > MAX_CENSUS_BYTES:
        raise ValueError("census must be non-empty bytes within the size bound")
    try:
        document = json.loads(bytes(data).decode("utf-8"), parse_constant=_reject_constant)
    except RecursionError as error:
        raise ValueError("census nesting too deep") from error
    if not isinstance(document, dict):
        raise ValueError("census must be a JSON object")
    if document.get("kind") != CENSUS_KIND or document.get("schema") != 1 or isinstance(document.get("schema"), bool):
        raise ValueError(f"census kind/schema must be {CENSUS_KIND}/1")
    summary = document.get("summary")
    if not isinstance(summary, dict) or summary.get("complete") is not True:
        raise ValueError("census summary missing or incomplete; the sampler did not finish")
    placements = document.get("placements")
    if not isinstance(placements, list) or len(placements) > MAX_PLACEMENTS:
        raise ValueError(f"census placements must be a list of at most {MAX_PLACEMENTS}")
    for index, row in enumerate(placements):
        if not isinstance(row, dict) or not isinstance(row.get("class"), str):
            raise ValueError(f"placement {index} must be an object with a class")
        hits = row.get("hits")
        if not isinstance(hits, list) or len(hits) > MAX_HITS_PER_PLACEMENT:
            raise ValueError(f"placement {index} hits must be a bounded list")
        for hit in hits:
            if (not isinstance(hit, list) or len(hit) != 6 or not all(_number(v) for v in hit)
                    or hit[3] < 0 or hit[5] not in (-1, 0, 1, 2)):
                raise ValueError(f"placement {index} has a malformed hit row")
        if row.get("found") is True and row.get("box_source") != "none":
            box = row.get("box_min")
            grid = row.get("grid")
            if not isinstance(box, list) or len(box) != 3 or not all(_number(v) for v in box):
                raise ValueError(f"placement {index} box_min must be three numbers")
            if not isinstance(grid, dict) or not _number(grid.get("step")) or grid["step"] <= 0:
                raise ValueError(f"placement {index} grid step must be a positive number")
    return document


def _usable(row):
    stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}
    return (row.get("found") is True and row.get("box_source") != "none" and not stats.get("ray_capped")
            and not stats.get("output_capped"))


def _bands(support, tolerance):
    """Map each height to a storey index by physical height band, never by chaining.

    A band is centred on the best supported height (most hits, lowest first on a tie) and claims every
    unclaimed height within ``tolerance`` of that centre only. Heights are therefore never linked through
    intermediate steps, so a staircase between two floors becomes unsupported bands of its own instead of
    merging the floors. Bands are numbered from the lowest centre.
    """
    heights = sorted(support)
    claimed, centres = {}, {}
    for centre in sorted(heights, key=lambda h: (-support[h], h)):
        if centre in claimed:
            continue
        low = bisect_left(heights, centre - tolerance - EPSILON)
        high = bisect_right(heights, centre + tolerance + EPSILON)
        for height in heights[low:high]:
            if height not in claimed:
                claimed[height] = centre
        centres[centre] = None
    for rank, centre in enumerate(sorted(centres)):
        centres[centre] = rank
    return {height: centres[centre] for height, centre in claimed.items()}


def class_candidates(census, name, band_tolerance=BAND_TOLERANCE, min_clearance=MIN_CLEARANCE):
    """Per-class floor-cell candidates, keyed per (grid cell, height band), aggregated over placements."""
    rows = [row for row in census["placements"] if row["class"] == name]
    usable = [row for row in rows if _usable(row)]
    result = {"candidates": [], "usable_placements": len(usable), "rows": len(rows), "reach_mode": "unknown",
              "off_grid_hits": 0, "step": 1.0}
    if not usable:
        return result
    step = float(usable[0]["grid"]["step"])
    origin_x = float(usable[0]["box_min"][0]) + step / 2.0
    origin_z = float(usable[0]["box_min"][2]) + step / 2.0
    result["step"] = step
    per_placement = []
    support = {}
    for row in usable:
        row_step = float(row["grid"]["step"])
        bx, bz = float(row["box_min"][0]) + row_step / 2.0, float(row["box_min"][2]) + row_step / 2.0
        entries = []
        for x, y, z, clearance, ny, code in row["hits"]:
            ix, iz = round((x - bx) / row_step), round((z - bz) / row_step)
            if abs(x - (bx + ix * row_step)) > OFF_GRID_TOLERANCE or abs(z - (bz + iz * row_step)) > OFF_GRID_TOLERANCE:
                result["off_grid_hits"] += 1
                continue
            entries.append((ix, iz, y, clearance, ny, int(code)))
            support[round(y, 3)] = support.get(round(y, 3), 0) + 1
        per_placement.append(entries)
    storeys = _bands(support, band_tolerance)
    cells = {}
    raw_heights = {}
    tested_any = False
    for entries in per_placement:
        best = {}
        for ix, iz, y, clearance, ny, code in entries:
            key = (ix, iz, storeys[round(y, 3)])
            raw_heights.setdefault(key, []).append(y)
            if key not in best or (clearance, y) > (best[key][1], best[key][0]):
                best[key] = (y, clearance, ny, code)
        for key, value in best.items():
            cells.setdefault(key, []).append(value)
            if value[3] in (0, 1, 2):
                tested_any = True
    heights = {key: sum(v[0] for v in values) / len(values) for key, values in cells.items()}
    candidates = []
    for key in sorted(cells):
        ix, iz, storey = key
        values = cells[key]
        neighbours = [heights[n] for n in ((ix - 1, iz, storey), (ix + 1, iz, storey), (ix, iz - 1, storey),
                                           (ix, iz + 1, storey)) if n in heights]
        walkable = bool(neighbours) and all(abs(heights[key] - h) / step <= MAX_SLOPE + EPSILON for h in neighbours)
        counts = {"yes": 0, "no": 0, "nonav": 0, "unknown": 0}
        for value in values:
            counts[{1: "yes", 0: "no", 2: "nonav"}.get(value[3], "unknown")] += 1
        tested = counts["yes"] + counts["no"] + counts["nonav"]
        reachable = None
        if tested_any:
            reachable = tested > 0 and counts["yes"] * 2 > tested
        clearance = min(v[1] for v in values)
        spread = max(raw_heights[key]) - min(raw_heights[key])
        candidates.append({
            "x": round(origin_x + ix * step, 6), "y": round(heights[key], 6), "z": round(origin_z + iz * step, 6),
            "storey": storey, "clearance": round(clearance, 6), "clearance_ok": clearance >= min_clearance - EPSILON,
            "height_spread": round(spread, 6), "height_ok": spread <= HEIGHT_SPREAD_BOUND + EPSILON,
            "walkable": walkable, "ny_abs": round(sum(abs(v[2]) for v in values) / len(values), 6),
            "agreement": len(values) / len(usable), "placements": len(values),
            "reachable": reachable, "reach": counts, "reach_agreement": counts["yes"] / len(usable),
        })
    result["candidates"] = candidates
    result["reach_mode"] = "known" if tested_any else "unknown"
    return result


def eligible(candidates, reach_mode, min_agreement):
    """Candidates that are roofed with clearance, walkable, one measured height and agreed by placements.

    Reachability must be known and agreed: successful reach observations across the whole usable placement
    cohort must reach ``min_agreement``, so unknown or failed tests never authorize a point.
    """
    if reach_mode != "known":
        return []
    return [c for c in candidates
            if c["clearance_ok"] and c["height_ok"] and c["walkable"] and c["agreement"] >= min_agreement - EPSILON
            and c["reachable"] is True and c["reach_agreement"] >= min_agreement - EPSILON]


def _parse_xml(data):
    if len(data) > MAX_STOCK_BYTES or b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise ValueError("proto XML too large or declares a DTD")
    try:
        return ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError(f"malformed proto XML: {error}") from error


def parse_stock_points(xml, group):
    """{container: [(x, y, z, range, height), ...]} for one group of a mapgroupproto."""
    root = _parse_xml(xml)
    groups = [g for g in root.iter("group") if g.get("name") == group]
    if len(groups) > 1:
        raise ValueError(f"duplicate group {group}")
    result = {}
    for container in (groups[0].findall("container") if groups else []):
        points = []
        for point in container.findall("point"):
            try:
                x, y, z = (float(v) for v in point.get("pos", "").split())
                points.append((x, y, z, float(point.get("range", "0")), float(point.get("height", "0"))))
            except ValueError as error:
                raise ValueError(f"unreadable point in {group}/{container.get('name')}") from error
            if not all(math.isfinite(v) for v in points[-1]):
                raise ValueError("non-finite stock point")
        result[container.get("name", "")] = points
    return result


def _covering(candidate_list, point, radius):
    """(xz_covered, v3_covered, indices of candidates that cover the point in 3D)."""
    xz, used = False, []
    for index, c in enumerate(candidate_list):
        if math.hypot(c["x"] - point[0], c["z"] - point[2]) > radius + EPSILON:
            continue
        xz = True
        if c["y"] - VERTICAL_BELOW - EPSILON <= point[1] <= c["y"] + c["clearance"] + EPSILON:
            used.append(index)
    return xz, bool(used), used


def calibrate(candidates, stock, radius, min_agreement):
    """How many stock points lie within ``radius`` of an eligible candidate, and which candidates stock uses."""
    pool = eligible(candidates["candidates"], candidates["reach_mode"], min_agreement)
    used = set()
    containers = {}
    total = xz_total = v3_total = 0
    for name in sorted(stock):
        stats = {"points": 0, "xz_covered": 0, "v3_covered": 0}
        for point in stock[name]:
            xz, v3, indices = _covering(pool, point, radius)
            stats["points"] += 1
            stats["xz_covered"] += xz
            stats["v3_covered"] += v3
            used.update(indices)
        containers[name] = stats
        total += stats["points"]
        xz_total += stats["xz_covered"]
        v3_total += stats["v3_covered"]
    return {"radius": radius, "points": total, "xz_covered": xz_total, "v3_covered": v3_total,
            "xz_coverage": xz_total / total if total else None, "v3_coverage": v3_total / total if total else None,
            "containers": containers, "candidates": len(pool), "candidates_used": len(used),
            "candidates_unused": len(pool) - len(used), "reach_mode": candidates["reach_mode"]}


def select_points(candidates, reach_mode, min_agreement, max_per_storey, max_total, spacing):
    """Deterministic farthest-point choice per storey; independent of input order, sorted by (storey, x, z)."""
    pool = sorted(eligible(candidates, reach_mode, min_agreement), key=lambda c: (c["storey"], c["x"], c["z"]))
    by_storey = {}
    for c in pool:
        by_storey.setdefault(c["storey"], []).append(c)
    picks = {}
    for storey, cells in by_storey.items():
        cx = sum(c["x"] for c in cells) / len(cells)
        cz = sum(c["z"] for c in cells) / len(cells)
        chosen = [max(cells, key=lambda c: (round(math.hypot(c["x"] - cx, c["z"] - cz), 9), -c["x"], -c["z"]))]
        while len(chosen) < max_per_storey:
            best, best_distance = None, -1.0
            for c in cells:
                distance = min(math.hypot(c["x"] - p["x"], c["z"] - p["z"]) for p in chosen)
                if round(distance, 9) > round(best_distance, 9):
                    best, best_distance = c, distance
            if best is None or best_distance < spacing - EPSILON:
                break
            chosen.append(best)
        picks[storey] = chosen
    selected, rank = [], 0
    while len(selected) < max_total and any(rank < len(chosen) for chosen in picks.values()):
        for storey in sorted(picks):
            if rank < len(picks[storey]) and len(selected) < max_total:
                point = picks[storey][rank]
                selected.append({"x": point["x"], "y": point["y"], "z": point["z"], "storey": storey,
                                 "clearance": point["clearance"], "agreement": point["agreement"],
                                 "reachable": point["reachable"], "pick": rank})
        rank += 1
    return sorted(selected, key=lambda p: (p["storey"], p["x"], p["z"]))


# ---------------------------------------------------------------------------
# Treatment writer: edits only the two tenement group blocks, as text
# ---------------------------------------------------------------------------


def _skeleton(group):
    return [(element.tag, element.get("name")) for element in group.iter() if element.tag in ("usage", "container", "category", "tag")]


def _group_block(text, name):
    matches = list(re.finditer(r'<group\b[^>]*\bname="%s"[^>]*>' % re.escape(name), text))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one group {name}, found {len(matches)}")
    opening = matches[0]
    if opening.group(0).endswith("/>"):
        raise ValueError(f"group {name} is self-closing")
    end = text.find("</group>", opening.end())
    if end < 0:
        raise ValueError(f"group {name} is not closed")
    return opening.start(), end + len("</group>")


def _set_lootmax(tag, value):
    updated, count = re.subn(r'\blootmax="0"', 'lootmax="%d"' % value, tag, count=1)
    if count != 1:
        raise ValueError("stock lootmax is not 0; refusing to overwrite authored data")
    return updated


def _lootmax_for(count, loot_ratio, max_lootmax):
    return max(1, min(max_lootmax, math.ceil(count * loot_ratio - EPSILON)))


def _edit_group(block, points, loot_ratio=0.25, max_lootmax=12):
    eol = "\r\n" if "\r\n" in block else "\n"
    lootmax = _lootmax_for(len(points), loot_ratio, max_lootmax)
    opening = re.match(r"<group\b[^>]*>", block)
    block = _set_lootmax(opening.group(0), lootmax) + block[opening.end():]
    containers = [m for m in re.finditer(r'<container\b[^>]*\bname="%s"[^>]*>' % FLOOR_CONTAINER, block)]
    if len(containers) != 1 or containers[0].group(0).endswith("/>"):
        raise ValueError(f"expected exactly one open {FLOOR_CONTAINER} container")
    container = containers[0]
    close = block.find("</container>", container.end())
    if close < 0:
        raise ValueError("container is not closed")
    line_start = block.rfind("\n", 0, close) + 1
    if block[line_start:close].strip():
        raise ValueError("container end tag is not on its own line")
    body = block[container.end():line_start]
    children = [line for line in body.splitlines() if line.strip()]
    if children:
        indent = re.match(r"[ \t]*", children[-1]).group(0)
    else:
        indent = block[line_start:close] + "\t"
    lines = "".join('%s<point pos="%.6f %.6f %.6f" range="%s" height="%s" />%s'
                    % (indent, p["x"], p["y"], p["z"], POINT_RANGE, POINT_HEIGHT, eol) for p in points)
    return (block[:container.start()] + _set_lootmax(container.group(0), lootmax) + block[container.end():line_start]
            + lines + block[line_start:])


def _check_points(points):
    if not isinstance(points, list) or len(points) > MAX_POINTS_PER_CLASS:
        raise ValueError(f"points must be a list of at most {MAX_POINTS_PER_CLASS}")
    for p in points:
        if not isinstance(p, dict) or not all(_number(p.get(k)) and abs(p[k]) < 1e5 for k in ("x", "y", "z")):
            raise ValueError("every point needs bounded finite x, y and z")


def write_treatment(stock_bytes, selections, loot_ratio=0.25, max_lootmax=12):
    """Return stock mapgroupproto bytes with points and lootmax added to the tenement groups only."""
    unknown = sorted(set(selections) - set(TENEMENT_CLASSES))
    if unknown:
        raise ValueError("only the tenement groups may be treated, not: " + ", ".join(unknown))
    text = stock_bytes.decode("utf-8")
    before = {g.get("name"): g for g in _parse_xml(stock_bytes).iter("group")}
    edits = []
    for name in TENEMENT_CLASSES:
        points = selections.get(name) or []
        _check_points(points)
        if not points:
            continue
        group = before.get(name)
        if group is None:
            raise ValueError(f"stock has no group {name}")
        containers = [c for c in group.findall("container") if c.get("name") == FLOOR_CONTAINER]
        if (group.get("lootmax") != "0" or False or len(containers) != 1
                or any(c.get("lootmax") != "0" for c in group.findall("container"))):
            raise ValueError(f"stock group {name} is not an empty lootmax-0 shell with one {FLOOR_CONTAINER} container")
        start, end = _group_block(text, name)
        edits.append((start, end, name, points))
    for start, end, name, points in sorted(edits, reverse=True):
        text = text[:start] + _edit_group(text[start:end], points, loot_ratio=loot_ratio, max_lootmax=max_lootmax) + text[end:]
    output = text.encode("utf-8")
    _verify(stock_bytes, output, before, {name: points for _s, _e, name, points in edits}, loot_ratio, max_lootmax)
    return output


def _verify(stock, output, before, edited, loot_ratio, max_lootmax):
    after = {g.get("name"): g for g in _parse_xml(output).iter("group")}
    if set(after) != set(before):
        raise ValueError("treatment changed the set of groups")
    for name, group in after.items():
        if name not in edited:
            if ET.tostring(group) != ET.tostring(before[name]):
                raise ValueError(f"treatment changed group {name}")
            continue
        points = edited[name]
        lootmax = str(_lootmax_for(len(points), loot_ratio, max_lootmax))
        if _skeleton(group) != _skeleton(before[name]) or group.get("lootmax") != lootmax:
            raise ValueError(f"treatment altered the structure of {name}")
        for container in group.findall("container"):
            written = container.findall("point")
            if container.get("name") == FLOOR_CONTAINER:
                expected = ["%.6f %.6f %.6f" % (p["x"], p["y"], p["z"]) for p in points]
                if [w.get("pos") for w in written] != expected or container.get("lootmax") != lootmax:
                    raise ValueError(f"treatment points of {name} do not match the selection")
            elif written or container.get("lootmax") != "0":
                raise ValueError(f"treatment touched container {container.get('name')} of {name}")
    if _outside_groups(stock, edited) != _outside_groups(output, edited):
        raise ValueError("treatment changed bytes outside the tenement groups")


def _outside_groups(data, names):
    text = data.decode("utf-8")
    for name in sorted(names):
        start, end = _group_block(text, name)
        text = text[:start] + text[end:]
    return text


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _bounded(name, value, low, high, integer=False):
    ok = _number(value) and low <= value <= high and (not integer or isinstance(value, int))
    if not ok:
        raise ValueError(f"{name} must be {'an integer' if integer else 'a number'} in {low}..{high}")
    return value


def build_treatment(census_bytes, stock_bytes, min_calibration, radius=CALIBRATION_RADIUS, max_per_storey=4,
                    max_total=48, spacing=2.0, loot_ratio=0.25, max_lootmax=12, min_agreement=0.75,
                    allow_empty_classes=False):
    """Return (treatment bytes, report). Raise CoverageError when calibration is missing or too low."""
    _bounded("min_calibration", min_calibration, 0.0, 1.0)
    _bounded("radius", radius, 0.05, 2.0)
    _bounded("max_per_storey", max_per_storey, 1, 32, integer=True)
    _bounded("max_total", max_total, 1, MAX_POINTS_PER_CLASS, integer=True)
    _bounded("spacing", spacing, 0.5, 20.0)
    _bounded("loot_ratio", loot_ratio, 0.01, 1.0)
    _bounded("max_lootmax", max_lootmax, 1, 64, integer=True)
    _bounded("min_agreement", min_agreement, 0.01, 1.0)
    census = parse_census(census_bytes)
    calibration, missing = {}, []
    for name in CALIBRATION_CLASSES:
        candidates = class_candidates(census, name)
        stock = parse_stock_points(stock_bytes, name)
        if not candidates["usable_placements"]:
            missing.append(f"{name} (no usable placement)")
        elif not any(stock.values()):
            missing.append(f"{name} (no stock points)")
        else:
            calibration[name] = calibrate(candidates, stock, radius, min_agreement)
            calibration[name]["usable_placements"] = candidates["usable_placements"]
    if missing:
        raise CoverageError("calibration data missing for " + ", ".join(missing)
                            + "; every calibration class is required")
    coverage = min(entry["v3_coverage"] for entry in calibration.values())
    xz_coverage = min(entry["xz_coverage"] for entry in calibration.values())
    worst = min(calibration, key=lambda name: calibration[name]["v3_coverage"])
    if coverage < min_calibration - EPSILON:
        raise CoverageError(f"calibration vertical (3D) coverage {coverage:.3f} ({worst}, radius {radius}, "
                            f"xz-only {xz_coverage:.3f}) is below the threshold {min_calibration:.3f}")
    selections, classes = {}, {}
    for name in TENEMENT_CLASSES:
        candidates = class_candidates(census, name)
        chosen = select_points(candidates["candidates"], candidates["reach_mode"], min_agreement, max_per_storey,
                               max_total, spacing)
        if not chosen and not allow_empty_classes:
            raise ValueError(f"{name}: no eligible candidates (usable placements {candidates['usable_placements']}, "
                             f"reachability {candidates['reach_mode']}; unknown reachability never enters treatment)")
        selections[name] = chosen
        classes[name] = {
            "usable_placements": candidates["usable_placements"], "rows": candidates["rows"],
            "candidates": len(candidates["candidates"]),
            "eligible": len(eligible(candidates["candidates"], candidates["reach_mode"], min_agreement)),
            "reachability_mode": candidates["reach_mode"], "selected": len(chosen),
            "storeys": sorted({p["storey"] for p in chosen}), "off_grid_hits": candidates["off_grid_hits"],
            "points": chosen,
        }
    treatment = write_treatment(stock_bytes, selections, loot_ratio=loot_ratio, max_lootmax=max_lootmax)
    report = {
        "kind": "interior-points-report", "schema_version": 1,
        "note": "offline aggregation of a native census; candidate only, spawning is not accepted by this tool",
        "parameters": {"radius": radius, "max_per_storey": max_per_storey, "max_total": max_total,
                       "spacing": spacing, "loot_ratio": loot_ratio, "max_lootmax": max_lootmax,
                       "min_agreement": min_agreement, "min_clearance": MIN_CLEARANCE, "max_slope": MAX_SLOPE,
                       "band_tolerance": BAND_TOLERANCE, "height_spread_bound": HEIGHT_SPREAD_BOUND},
        "calibration": {"passed": True, "min_coverage": coverage, "min_xz_coverage": xz_coverage,
                        "gate": "vertical (3D) coverage", "threshold": min_calibration,
                        "classes": calibration},
        "classes": classes,
        "treatment": {"sha256": hashlib.sha256(treatment).hexdigest(), "bytes": len(treatment),
                      "groups_changed": sorted(name for name, chosen in selections.items() if chosen)},
        "stock_mapgroupproto_sha256": hashlib.sha256(stock_bytes).hexdigest(),
        "census_sha256": hashlib.sha256(census_bytes).hexdigest(),
    }
    return treatment, report


def _read_bounded(path, limit):
    with open(path, "rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{path} exceeds {limit} bytes")
    return data


def _output_path(value):
    raw = Path(value)
    if ".." in raw.parts:
        raise ValueError(f"{value}: '..' is not allowed in output paths")
    path = raw.resolve()
    checkout = Path(__file__).resolve().parents[2]
    if path == checkout or checkout in path.parents:
        raise ValueError(f"{value}: output must be outside the source checkout")
    if path.exists() or path.is_symlink():
        raise ValueError(f"{value}: refusing to overwrite")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--census", required=True)
    parser.add_argument("--stock-proto", required=True, help="stock mapgroupproto.xml")
    parser.add_argument("--output", required=True, help="treatment mapgroupproto.xml (outside the checkout)")
    parser.add_argument("--report", required=True, help="JSON report (outside the checkout)")
    parser.add_argument("--min-calibration", type=float, default=DEFAULT_MIN_CALIBRATION)
    parser.add_argument("--radius", type=float, default=CALIBRATION_RADIUS)
    parser.add_argument("--max-per-storey", type=int, default=4)
    parser.add_argument("--max-total", type=int, default=48)
    parser.add_argument("--spacing", type=float, default=2.0)
    parser.add_argument("--loot-ratio", type=float, default=0.25)
    parser.add_argument("--max-lootmax", type=int, default=12)
    parser.add_argument("--min-agreement", type=float, default=0.75)
    parser.add_argument("--allow-empty-classes", action="store_true")
    args = parser.parse_args(argv)
    try:
        output, report_path = _output_path(args.output), _output_path(args.report)
        if output == report_path:
            raise ValueError("output and report must differ")
        census = _read_bounded(args.census, MAX_CENSUS_BYTES)
        stock = _read_bounded(args.stock_proto, MAX_STOCK_BYTES)
        treatment, report = build_treatment(
            census, stock, args.min_calibration, radius=args.radius, max_per_storey=args.max_per_storey,
            max_total=args.max_total, spacing=args.spacing, loot_ratio=args.loot_ratio,
            max_lootmax=args.max_lootmax, min_agreement=args.min_agreement,
            allow_empty_classes=args.allow_empty_classes)
        for path in (output, report_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "xb") as stream:
            stream.write(treatment)
        with open(report_path, "x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except CoverageError as error:
        print(f"interior_points: calibration coverage refusal: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(f"interior_points: {error}", file=sys.stderr)
        return 1
    print(f"treatment {output} sha256={report['treatment']['sha256']} groups={','.join(report['treatment']['groups_changed'])}")
    print(f"calibration min xz coverage {report['calibration']['min_coverage']:.3f} "
          f"(threshold {args.min_calibration:.3f}); report {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
