"""Turn an interior-sampler census into a candidate tenement mapgroupproto treatment.

Input is the census written by tools/setup/interior_sampler.py after a native run. The census
is observation data: this tool aggregates it, measures how well it reproduces the STOCK points
of calibration buildings, and refuses to produce a treatment when that agreement is too low. It
proves nothing about DayZ spawning; a treatment is only a candidate that still needs normal
PBO/server testing. Output must be written outside the git checkout.

    python3 tools/audit/interior_points.py --census census.json --stock-proto stock/mapgroupproto.xml \
        --output /mnt/d/HollowCountryLocal/treatment/mapgroupproto.xml --report .../report.json \
        --min-calibration 0.6 [--reach-source strict|player]

Reach codes in a hit row: 1 reached, 0 not reached, 2 no navmesh near the floor, 3 unqualified (a
nontrivial snap or gap, a foreign obstruction below the required clearance, or a capped column),
-1 unknown. The hit row's code is the STRICT filter; a parallel ``player_codes`` array carries the
player-flag filter computed in the same run. ``--reach-source`` selects which one gates eligibility
(default strict; there is no silent switch and a census without player_codes is refused for player).
The report carries a per-class eligibility funnel, also when the run is refused, and a refusal
writes that report (never a treatment).

Round 5 (issue #11). hit[5] and ``player_codes`` are the run with every door AS FOUND; ``open_codes`` and
``open_player_codes`` are the parallel codes of the run with the unlocked doors OPENED, which is the run that
gates eligibility. A control only counts when it tested AND its ``entered`` stage (open run) entered the
building. The run is refused unless the open runs reached strictly more cells than the closed runs (otherwise
door semantics are unobserved) and unless the sampler recorded a native frame verdict: the stock
mapgroupproto frame is the sampler frame rotated +90 degrees (stock = (z, y, -x)). Calibration transforms
stock lootFloor points into the sampler frame and gates on lootFloor only (shelves and weapons are reported,
not gated); selected points are converted back to the stock frame before they are written.
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
HIT_CODES = (-1, 0, 1, 2, 3)
REACH_SOURCES = ("strict", "player")
REACH_BUCKETS = ("yes", "no", "nonav", "unqualified", "unknown")
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
FRAMES = ("as-is", "rot90")
FRAME_MIN_RECORDS = 4
FRAME_MIN_FRACTION = 0.8
FRAME_MIN_MARGIN = 0.25
MAX_FRAME_RECORDS = 4096
ENTERED_STATES = ("entered", "not-entered", "untested")


class CoverageError(ValueError):
    """Calibration agreement is too low, or there is no calibration data to measure it."""


def _number(value):
    """A finite JSON number. An integer too large for a float (OverflowError in isfinite) is not one."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _code(value):
    return _number(value) and value in HIT_CODES


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
                    or hit[3] < 0 or hit[5] not in HIT_CODES):
                raise ValueError(f"placement {index} has a malformed hit row")
        for key in ("player_codes", "open_codes", "open_player_codes"):
            codes = row.get(key)
            if codes is not None and (not isinstance(codes, list) or len(codes) != len(hits)
                                      or not all(_code(v) for v in codes)):
                raise ValueError(f"placement {index} {key} must parallel the hits with known codes")
        frame = row.get("frame")
        if frame is not None:
            if not isinstance(frame, list) or len(frame) > MAX_FRAME_RECORDS:
                raise ValueError(f"placement {index} frame must be a bounded list")
            for record in frame:
                if (not isinstance(record, list) or len(record) != 7 or not all(_number(v) for v in record)
                        or record[3] not in (0, 1) or record[5] not in (0, 1)):
                    raise ValueError(f"placement {index} has a malformed frame record")
        if row.get("found") is True and row.get("box_source") != "none":
            box = row.get("box_min")
            grid = row.get("grid")
            if not isinstance(box, list) or len(box) != 3 or not all(_number(v) for v in box):
                raise ValueError(f"placement {index} box_min must be three numbers")
            if not isinstance(grid, dict) or not _number(grid.get("step")) or grid["step"] <= 0:
                raise ValueError(f"placement {index} grid step must be a positive number")
    return document


def _check_frame(frame):
    if frame not in FRAMES:
        raise ValueError(f"frame must be one of {', '.join(FRAMES)}")


def stock_to_sampler(point, frame):
    """Stock mapgroupproto position -> sampler frame. The stock frame is the sampler frame rotated +90."""
    _check_frame(frame)
    x, y, z = point[0], point[1], point[2]
    if frame == "rot90":
        return (-z + 0.0, y + 0.0, x + 0.0)
    return (x + 0.0, y + 0.0, z + 0.0)


def sampler_to_stock(point, frame):
    """Exact inverse of stock_to_sampler."""
    _check_frame(frame)
    a, y, b = point[0], point[1], point[2]
    if frame == "rot90":
        return (b + 0.0, y + 0.0, -a + 0.0)
    return (a + 0.0, y + 0.0, b + 0.0)


def frame_verdict(census):
    """Native frame verdict from the sampler's vertical raycasts at stock lootFloor points.

    Per calibration class the fraction of stock points whose vertical ray hit the building as-is and under
    the rotate +90 transform decide the frame: one must reach FRAME_MIN_FRACTION and beat the other by
    FRAME_MIN_MARGIN (thresholds are provisional). Every calibration class must agree; anything else, or no
    record, gives verdict None. The verdict only says which transform matched a raycast, nothing about spawning.
    """
    classes, verdicts = {}, []
    for name in CALIBRATION_CLASSES:
        total = as_is = rotated = 0
        for row in census["placements"]:
            if row["class"] != name:
                continue
            for record in row.get("frame") or []:
                total += 1
                as_is += record[3] == 1
                rotated += record[5] == 1
        verdict = None
        if total >= FRAME_MIN_RECORDS:
            fa, fr = as_is / total, rotated / total
            if fr >= FRAME_MIN_FRACTION and fr - fa >= FRAME_MIN_MARGIN:
                verdict = "rot90"
            elif fa >= FRAME_MIN_FRACTION and fa - fr >= FRAME_MIN_MARGIN:
                verdict = "as-is"
        classes[name] = {"records": total, "as_is_hits": as_is, "rot90_hits": rotated, "verdict": verdict}
        verdicts.append(verdict)
    result = {"verdict": None, "classes": classes, "reason": "", "min_records": FRAME_MIN_RECORDS,
              "min_fraction": FRAME_MIN_FRACTION, "min_margin": FRAME_MIN_MARGIN}
    if all(v is not None for v in verdicts) and len(set(verdicts)) == 1:
        result["verdict"] = verdicts[0]
    elif any(c["records"] == 0 for c in classes.values()):
        result["reason"] = "no native frame verdict recorded: " + ", ".join(
            name for name, c in classes.items() if c["records"] == 0) + " carry no frame check records"
    elif len(set(v for v in verdicts if v is not None)) > 1:
        result["reason"] = "no native frame verdict: the calibration classes disagree"
    else:
        result["reason"] = "no native frame verdict: the raycasts do not separate the frames"
    return result


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


def _reach_block(row, reach_source):
    reach = row.get("reach") if isinstance(row.get("reach"), dict) else {}
    if reach_source == "player":
        reach = reach.get("player") if isinstance(reach.get("player"), dict) else {}
    return reach


def _control_state(row, reach_source):
    state = _reach_block(row, reach_source).get("state")
    return state if isinstance(state, str) else "absent"


def _entered(row, reach_source):
    """The control's entered stage per run: did the control path reach ~1 m inside a door."""
    block = row.get("entered") if isinstance(row.get("entered"), dict) else {}
    entered = block.get(reach_source)
    result = {}
    for run in ("closed", "open"):
        value = entered.get(run) if isinstance(entered, dict) else None
        result[run] = value if value in ENTERED_STATES else "absent"
    return result


def _gate_passed(row, reach_source):
    """Evidence needs the selected filter's control tested AND entered with the doors opened."""
    return _control_state(row, reach_source) == "tested" and _entered(row, reach_source)["open"] == "entered"


def _closed_codes(row, reach_source):
    """Codes of the run with the doors as found, or None when the census lacks them."""
    if reach_source == "strict":
        return [hit[5] for hit in row["hits"]]
    return row.get("player_codes")


def _row_codes(row, reach_source, name):
    """Codes of the run with the doors opened: the codes that gate eligibility. A row without them is unknown."""
    if reach_source == "strict":
        codes = row.get("open_codes")
        return codes if codes is not None else [-1] * len(row["hits"])
    codes = row.get("open_player_codes")
    if codes is None:
        if row["hits"]:
            raise ValueError(f"{name}: placement {row.get('i')} has no open_player_codes; the player reach source "
                             "needs a census from the round 5 sampler (never falls back to strict)")
        return []
    return codes


MAX_DOOR_PROBLEMS = 8
DOOR_COUNT_KEYS = ("count", "locked", "open_at_start", "opened", "observed_open", "restored")


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1_000_000


def _door_run_problem(record):
    """Why a placement's door run is not evidence that the doors opened and were put back; None when it is.

    The sampler opens only doors it found unlocked and actually closed, waits for the actual door phase, observes
    them open, runs the open pass, closes them and observes them closed. Anything short of that is not a
    door-semantics observation: a run that never opened a door, never saw one open, or left one open cannot be
    compared against the run with the doors as found.
    """
    if not isinstance(record, dict):
        return "door_run is missing"
    for key in DOOR_COUNT_KEYS:
        if key not in record:
            if key == "open_at_start":
                continue
            return f"door_run.{key} is missing"
        if not _count(record[key]):
            return f"door_run.{key} is not a non-negative integer"
    count, opened = record["count"], record["opened"]
    if record.get("state") != "done":
        return f"door_run.state is {record.get('state')!r}, not 'done'"
    if opened < 1:
        return "no door was opened by the run"
    if opened > count or record["locked"] > count or opened + record["locked"] > count:
        return "door_run counts are contradictory (opened plus locked exceed the door count)"
    if record["observed_open"] != opened:
        return f"{opened} door(s) opened but {record['observed_open']} observed open"
    if record["restored"] != opened:
        return f"{opened} door(s) opened but {record['restored']} restored"
    delay = record.get("delay_ticks")
    if delay is not None and not (_count(delay) and delay >= 1):
        return "door_run.delay_ticks is not a positive integer"
    doors = record.get("doors")
    if not isinstance(doors, list) or len(doors) != count:
        return "door_run.doors does not list every door"
    for door in doors:
        if not isinstance(door, list) or not 5 <= len(door) <= 6 or not all(_number(v) for v in door):
            return "door_run.doors has a malformed record"
    return None


def door_semantics(census, reach_source):
    """Do open doors reach strictly more cells than closed doors, over every usable row that passed its gate.

    The comparison only counts when every compared row's door run is valid evidence (see ``_door_run_problem``).
    """
    classes, closed_total, open_total, compared = {}, 0, 0, 0
    doors = {"count": 0, "locked": 0, "opened": 0, "observed_open": 0, "restored": 0, "rows": 0,
             "invalid_rows": 0, "problems": []}
    for name in TENEMENT_CLASSES + CALIBRATION_CLASSES:
        closed = opened = rows = 0
        for row in census["placements"]:
            if row["class"] != name or not _usable(row) or not _gate_passed(row, reach_source):
                continue
            open_codes = row.get("open_codes") if reach_source == "strict" else row.get("open_player_codes")
            closed_codes = _closed_codes(row, reach_source)
            if open_codes is None or closed_codes is None:
                continue
            rows += 1
            closed += sum(1 for code in closed_codes if code == 1)
            opened += sum(1 for code in open_codes if code == 1)
            record = row.get("door_run")
            problem = _door_run_problem(record)
            if problem is not None:
                doors["invalid_rows"] += 1
                if len(doors["problems"]) < MAX_DOOR_PROBLEMS:
                    doors["problems"].append({"class": name, "placement": row.get("i"), "problem": problem})
                continue
            doors["rows"] += 1
            for key in ("count", "locked", "opened", "observed_open", "restored"):
                doors[key] += record[key]
        classes[name] = {"rows_compared": rows, "closed_reached": closed, "open_reached": opened}
        closed_total += closed
        open_total += opened
        compared += rows
    return {"reach_source": reach_source, "rows_compared": compared, "closed_reached": closed_total,
            "open_reached": open_total,
            "observed": compared > 0 and open_total > closed_total and doors["invalid_rows"] == 0,
            "classes": classes, "doors": doors}


def class_candidates(census, name, band_tolerance=BAND_TOLERANCE, min_clearance=MIN_CLEARANCE,
                     reach_source="strict"):
    """Per-class floor-cell candidates, keyed per (grid cell, height band), aggregated over placements."""
    if reach_source not in REACH_SOURCES:
        raise ValueError(f"reach_source must be one of {', '.join(REACH_SOURCES)}")
    rows = [row for row in census["placements"] if row["class"] == name]
    usable = [row for row in rows if _usable(row)]
    states, entered_states = {}, {}
    for row in rows:
        state = _control_state(row, reach_source)
        states[state] = states.get(state, 0) + 1
        entered = _entered(row, reach_source)["open"]
        entered_states[entered] = entered_states.get(entered, 0) + 1
    result = {"candidates": [], "usable_placements": len(usable), "rows": len(rows), "reach_mode": "unknown",
              "off_grid_hits": 0, "step": 1.0, "reach_source": reach_source, "control_states": states,
              "entered_states": entered_states, "gated_rows": sum(1 for row in usable if _gate_passed(row, reach_source))}
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
        codes = _row_codes(row, reach_source, name)
        # An observation is only evidence when the SELECTED filter's control passed on this very row AND
        # entered the building with the doors opened. A failed, unavailable, missing or non-entering control
        # (or one where only the other filter passed) makes every hit of the row unknown; the row stays in
        # the usable denominator, so agreement is never inflated.
        control_passed = _gate_passed(row, reach_source)
        for (x, y, z, clearance, ny, _strict), code in zip(row["hits"], codes):
            ix, iz = round((x - bx) / row_step), round((z - bz) / row_step)
            if abs(x - (bx + ix * row_step)) > OFF_GRID_TOLERANCE or abs(z - (bz + iz * row_step)) > OFF_GRID_TOLERANCE:
                result["off_grid_hits"] += 1
                continue
            entries.append((ix, iz, y, clearance, ny, int(code) if control_passed else -1))
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
            if value[3] in (0, 1, 2, 3):
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
        unqualified = 0
        for value in values:
            if value[3] == 3:
                unqualified += 1
                continue
            counts[{1: "yes", 0: "no", 2: "nonav"}.get(value[3], "unknown")] += 1
        tested = counts["yes"] + counts["no"] + counts["nonav"] + unqualified
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
            "reachable": reachable, "reach": counts, "reach_unqualified": unqualified,
            "reach_agreement": counts["yes"] / len(usable),
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


def _cell_counts(cell):
    counts = dict(cell["reach"])
    counts["unqualified"] = cell.get("reach_unqualified", 0)
    return counts


def _verdict(cell):
    """The one reach bucket a cell lands in: yes, or the failure observed most often (ties: no, nonav,
    unqualified), or unknown when nothing was tested."""
    if cell["reachable"] is True:
        return "yes"
    counts = _cell_counts(cell)
    best, name = 0, "unknown"
    for key in ("no", "nonav", "unqualified"):
        if counts[key] > best:
            best, name = counts[key], key
    return name


def funnel(result, min_agreement):
    """Per-class eligibility funnel: how many cells survive each stage, in order, and why reach drops cells."""
    cells = result["candidates"]
    stages = {"candidates": len(cells)}
    alive = cells
    for key, test in (("clearance", lambda c: c["clearance_ok"]), ("height", lambda c: c["height_ok"]),
                      ("walkable", lambda c: c["walkable"])):
        alive = [c for c in alive if test(c)]
        stages[key] = len(alive)
    reach_cells = {key: 0 for key in REACH_BUCKETS}
    for cell in alive:
        reach_cells[_verdict(cell)] += 1
    reached = [c for c in alive if result["reach_mode"] == "known" and c["reachable"] is True]
    stages["reach"] = len(reached)
    stages["agreement"] = len([c for c in reached if c["agreement"] >= min_agreement - EPSILON
                               and c["reach_agreement"] >= min_agreement - EPSILON])
    stages["eligible"] = len(eligible(cells, result["reach_mode"], min_agreement))
    observations = {key: 0 for key in REACH_BUCKETS}
    for cell in cells:
        for key, value in _cell_counts(cell).items():
            observations[key] += value
    return {"status": "computed", "rows": result["rows"], "usable_placements": result["usable_placements"],
            "reach_source": result.get("reach_source", "strict"), "reach_mode": result["reach_mode"],
            "stages": stages, "reach_cells": reach_cells, "reach_observations": observations,
            "control_states": dict(result.get("control_states", {})),
            "entered_states": dict(result.get("entered_states", {}))}


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


def calibrate(candidates, stock, radius, min_agreement, frame=None, gate_container=FLOOR_CONTAINER):
    """How many stock points lie within ``radius`` of an eligible candidate, and which candidates stock uses.

    Stock points are moved into the sampler frame first (``frame`` is the native verdict; there is no default).
    Only ``gate_container`` (lootFloor) counts toward the totals and the gate: a floor sampler cannot cover
    shelf or weapon containers, so those are reported per container but not gated.
    """
    if frame is None:
        raise ValueError("calibration needs a native frame verdict")
    _check_frame(frame)
    pool = eligible(candidates["candidates"], candidates["reach_mode"], min_agreement)
    used = set()
    containers = {}
    total = xz_total = v3_total = 0
    for name in sorted(stock):
        gated = name == gate_container
        stats = {"points": 0, "xz_covered": 0, "v3_covered": 0, "gated": gated}
        for point in stock[name]:
            xz, v3, indices = _covering(pool, stock_to_sampler(point, frame), radius)
            stats["points"] += 1
            stats["xz_covered"] += xz
            stats["v3_covered"] += v3
            if gated:
                used.update(indices)
        containers[name] = stats
        if gated:
            total += stats["points"]
            xz_total += stats["xz_covered"]
            v3_total += stats["v3_covered"]
    return {"radius": radius, "frame": frame, "gate": gate_container, "points": total, "xz_covered": xz_total,
            "v3_covered": v3_total, "xz_coverage": xz_total / total if total else None,
            "v3_coverage": v3_total / total if total else None, "containers": containers,
            "candidates": len(pool), "candidates_used": len(used), "candidates_unused": len(pool) - len(used),
            "reach_mode": candidates["reach_mode"]}


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


def _stock_pos(point, frame):
    x, y, z = sampler_to_stock((point["x"], point["y"], point["z"]), frame)
    return "%.6f %.6f %.6f" % (x, y, z)


def _edit_group(block, points, loot_ratio=0.25, max_lootmax=12, frame="as-is"):
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
    lines = "".join('%s<point pos="%s" range="%s" height="%s" />%s'
                    % (indent, _stock_pos(p, frame), POINT_RANGE, POINT_HEIGHT, eol) for p in points)
    return (block[:container.start()] + _set_lootmax(container.group(0), lootmax) + block[container.end():line_start]
            + lines + block[line_start:])


def _check_points(points):
    if not isinstance(points, list) or len(points) > MAX_POINTS_PER_CLASS:
        raise ValueError(f"points must be a list of at most {MAX_POINTS_PER_CLASS}")
    for p in points:
        if not isinstance(p, dict) or not all(_number(p.get(k)) and abs(p[k]) < 1e5 for k in ("x", "y", "z")):
            raise ValueError("every point needs bounded finite x, y and z")


def write_treatment(stock_bytes, selections, loot_ratio=0.25, max_lootmax=12, frame="as-is"):
    """Return stock mapgroupproto bytes with points and lootmax added to the tenement groups only.

    ``selections`` are in the sampler frame; ``frame`` is the native verdict used to convert them back to the
    stock frame the file is written in.
    """
    _check_frame(frame)
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
        if (group.get("lootmax") != "0" or group.findall(".//point") or len(containers) != 1
                or any(c.get("lootmax") != "0" for c in group.findall("container"))):
            raise ValueError(f"stock group {name} is not an empty lootmax-0 shell with one {FLOOR_CONTAINER} container")
        start, end = _group_block(text, name)
        edits.append((start, end, name, points))
    for start, end, name, points in sorted(edits, reverse=True):
        text = text[:start] + _edit_group(text[start:end], points, loot_ratio=loot_ratio, max_lootmax=max_lootmax,
                                                  frame=frame) + text[end:]
    output = text.encode("utf-8")
    _verify(stock_bytes, output, before, {name: points for _s, _e, name, points in edits}, loot_ratio, max_lootmax,
            frame)
    return output


def _verify(stock, output, before, edited, loot_ratio, max_lootmax, frame="as-is"):
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
                expected = [_stock_pos(p, frame) for p in points]
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


def _refusal(error, kind, base):
    """Attach the refusal report (status, reason, funnel) to the exception; the CLI writes it."""
    report = dict(base)
    report["status"] = "refused"
    report["refusal"] = {"kind": kind, "message": str(error)}
    error.report = report
    return error


def build_treatment(census_bytes, stock_bytes, min_calibration, radius=CALIBRATION_RADIUS, max_per_storey=4,
                    max_total=48, spacing=2.0, loot_ratio=0.25, max_lootmax=12, min_agreement=0.75,
                    allow_empty_classes=False, reach_source="strict"):
    """Return (treatment bytes, report). Raise CoverageError when calibration is missing or too low.

    Every refusal carries ``error.report`` (status, reason, census/stock hashes, whatever was analysed); the
    CLI writes it. Nothing is ever written as a treatment on a refusal.
    """
    base = {
        "kind": "interior-points-report", "schema_version": 2,
        "note": "offline aggregation of a native census; candidate only, spawning is not accepted by this tool",
        "parameters": {"radius": radius, "max_per_storey": max_per_storey, "max_total": max_total,
                       "spacing": spacing, "loot_ratio": loot_ratio, "max_lootmax": max_lootmax,
                       "min_agreement": min_agreement, "min_clearance": MIN_CLEARANCE, "max_slope": MAX_SLOPE,
                       "band_tolerance": BAND_TOLERANCE, "height_spread_bound": HEIGHT_SPREAD_BOUND,
                       "reach_source": reach_source, "min_calibration": min_calibration},
        "funnel": {},
        "stock_mapgroupproto_sha256": hashlib.sha256(stock_bytes).hexdigest()
        if isinstance(stock_bytes, (bytes, bytearray)) else None,
        "census_sha256": hashlib.sha256(census_bytes).hexdigest()
        if isinstance(census_bytes, (bytes, bytearray)) else None,
    }
    try:
        return _build(census_bytes, stock_bytes, base, min_calibration, radius, max_per_storey, max_total, spacing,
                      loot_ratio, max_lootmax, min_agreement, allow_empty_classes, reach_source)
    except ValueError as error:
        if getattr(error, "report", None) is None:
            raise _refusal(error, "invalid-input", base)
        raise


def _build(census_bytes, stock_bytes, base, min_calibration, radius, max_per_storey, max_total, spacing,
           loot_ratio, max_lootmax, min_agreement, allow_empty_classes, reach_source):
    if reach_source not in REACH_SOURCES:
        raise ValueError(f"reach_source must be one of {', '.join(REACH_SOURCES)}")
    _bounded("min_calibration", min_calibration, 0.0, 1.0)
    _bounded("radius", radius, 0.05, 2.0)
    _bounded("max_per_storey", max_per_storey, 1, 32, integer=True)
    _bounded("max_total", max_total, 1, MAX_POINTS_PER_CLASS, integer=True)
    _bounded("spacing", spacing, 0.5, 20.0)
    _bounded("loot_ratio", loot_ratio, 0.01, 1.0)
    _bounded("max_lootmax", max_lootmax, 1, 64, integer=True)
    _bounded("min_agreement", min_agreement, 0.01, 1.0)
    try:
        census = parse_census(census_bytes)
    except ValueError as problem:
        raise _refusal(problem, "census-invalid", base)
    analysed, funnels, unavailable = {}, base["funnel"], []
    for name in TENEMENT_CLASSES + CALIBRATION_CLASSES:
        try:
            analysed[name] = class_candidates(census, name, reach_source=reach_source)
        except ValueError as problem:
            # The requested source cannot be computed from this census (a legacy census has no open codes).
            # Say so per class; never substitute the other source's codes.
            funnels[name] = {"status": "not-computable", "reach_source": reach_source, "refusal": str(problem)}
            unavailable.append(str(problem))
            continue
        funnels[name] = funnel(analysed[name], min_agreement)
    if unavailable:
        raise _refusal(ValueError("; ".join(unavailable)), "reach-source-unavailable", base)
    frame = frame_verdict(census)
    base["frame"] = frame
    if frame["verdict"] is None:
        raise _refusal(CoverageError(frame["reason"] + "; the builder refuses to guess the stock frame"),
                       "frame-verdict-missing", base)
    blind = [name for name in CALIBRATION_CLASSES if analysed[name]["usable_placements"] and not analysed[name]["gated_rows"]]
    if blind:
        raise _refusal(CoverageError("control did not enter the building (tested control with the doors opened "
                                     "and an entered stage are required) for " + ", ".join(blind)),
                       "control-not-entered", base)
    semantics = door_semantics(census, reach_source)
    base["door_semantics"] = semantics
    if not semantics["observed"]:
        message = ("door semantics unobserved: the run with the doors opened reached %d cells, the run with the "
                   "doors as found %d (rows compared %d); open must reach strictly more"
                   % (semantics["open_reached"], semantics["closed_reached"], semantics["rows_compared"]))
        if semantics["doors"]["invalid_rows"]:
            first = semantics["doors"]["problems"][0]
            message += ("; door-run evidence invalid in %d row(s) (a door run must open, observe open and restore "
                        "at least one door): %s %s: %s"
                        % (semantics["doors"]["invalid_rows"], first["class"], first["placement"], first["problem"]))
        raise _refusal(CoverageError(message), "door-semantics-unobserved", base)
    calibration, missing = {}, []
    for name in CALIBRATION_CLASSES:
        candidates = analysed[name]
        stock = parse_stock_points(stock_bytes, name)
        if not candidates["usable_placements"]:
            missing.append(f"{name} (no usable placement)")
        elif not stock.get(FLOOR_CONTAINER):
            missing.append(f"{name} (no stock {FLOOR_CONTAINER} points)")
        else:
            calibration[name] = calibrate(candidates, stock, radius, min_agreement, frame=frame["verdict"])
            calibration[name]["usable_placements"] = candidates["usable_placements"]
    if missing:
        base["calibration"] = {"passed": False, "missing": missing, "classes": calibration, "frame": frame}
        raise _refusal(CoverageError("calibration data missing for " + ", ".join(missing)
                                     + "; every calibration class is required"), "calibration-missing", base)
    coverage = min(entry["v3_coverage"] for entry in calibration.values())
    xz_coverage = min(entry["xz_coverage"] for entry in calibration.values())
    worst = min(calibration, key=lambda name: calibration[name]["v3_coverage"])
    passed = coverage >= min_calibration - EPSILON
    base["calibration"] = {"passed": passed, "min_coverage": coverage, "min_xz_coverage": xz_coverage,
                           "gate": "vertical (3D) coverage of %s points only" % FLOOR_CONTAINER,
                           "threshold": min_calibration, "frame": frame, "classes": calibration}
    if not passed:
        raise _refusal(CoverageError(f"calibration vertical (3D) coverage {coverage:.3f} ({worst}, radius {radius}, "
                                     f"xz-only {xz_coverage:.3f}, frame {frame['verdict']}) is below the threshold "
                                     f"{min_calibration:.3f}"), "calibration", base)
    selections, classes, empty = {}, {}, []
    for name in TENEMENT_CLASSES:
        candidates = analysed[name]
        chosen = select_points(candidates["candidates"], candidates["reach_mode"], min_agreement, max_per_storey,
                               max_total, spacing)
        for point in chosen:
            point["stock"] = [round(v, 6) for v in sampler_to_stock((point["x"], point["y"], point["z"]), frame["verdict"])]
        if not chosen:
            empty.append(f"{name}: no eligible candidates (usable placements {candidates['usable_placements']}, "
                         f"reachability {candidates['reach_mode']}, source {reach_source}; unknown reachability "
                         "never enters treatment)")
        selections[name] = chosen
        classes[name] = {
            "usable_placements": candidates["usable_placements"], "rows": candidates["rows"],
            "candidates": len(candidates["candidates"]),
            "eligible": len(eligible(candidates["candidates"], candidates["reach_mode"], min_agreement)),
            "reachability_mode": candidates["reach_mode"], "selected": len(chosen),
            "storeys": sorted({p["storey"] for p in chosen}), "off_grid_hits": candidates["off_grid_hits"],
            "points": chosen,
        }
    if empty and not allow_empty_classes:
        base["classes"] = classes
        raise _refusal(ValueError("; ".join(empty)), "no-eligible-candidates", base)
    treatment = write_treatment(stock_bytes, selections, loot_ratio=loot_ratio, max_lootmax=max_lootmax,
                                frame=frame["verdict"])
    report = dict(base)
    report["status"] = "ok"
    report["classes"] = classes
    report["treatment"] = {"sha256": hashlib.sha256(treatment).hexdigest(), "bytes": len(treatment),
                           "groups_changed": sorted(name for name, chosen in selections.items() if chosen),
                           "stock_frame": frame["verdict"]}
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


def _write_refusal(path, error):
    """Write the refusal report next to where the run report would go; never a treatment.

    A refusal that never got far enough to build a report (unreadable census, bad arguments) still writes a
    minimal one saying why.
    """
    if path is None:
        return
    report = getattr(error, "report", None)
    if report is None:
        report = {"kind": "interior-points-report", "schema_version": 2, "status": "refused",
                  "refusal": {"kind": "input-error", "message": str(error)}}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, default=str)
            stream.write("\n")
    except OSError as problem:
        print(f"interior_points: refusal report not written: {problem}", file=sys.stderr)
        return
    print(f"interior_points: refusal report {path}", file=sys.stderr)


class _UsageError(ValueError):
    """A command-line parse failure, kept so main can still write a refusal report."""


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SystemExit(2)


def _report_path_from(argv):
    """The safe --report path named on a command line that failed to parse, or None.

    Only the report option is read, with the same abbreviation rules; the path still has to pass the normal
    output-path checks (outside the checkout, no '..', not existing). Anything else yields no report.
    """
    lenient = _Parser(add_help=False)
    lenient.add_argument("--report")
    try:
        known, _rest = lenient.parse_known_args(argv)
        return _output_path(known.report) if known.report else None
    except (ValueError, OSError):
        return None


def main(argv=None):
    parser = _Parser(description=__doc__.splitlines()[0])
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
    parser.add_argument("--reach-source", choices=REACH_SOURCES, default="strict",
                        help="which navmesh filter's reach codes gate eligibility (default strict; never switched silently)")
    try:
        args = parser.parse_args(argv)
    except _UsageError as error:
        print(f"interior_points: {error}", file=sys.stderr)
        error.report = {"kind": "interior-points-report", "schema_version": 2, "status": "refused",
                        "refusal": {"kind": "invalid-input", "message": f"command line: {error}"}}
        _write_refusal(_report_path_from(sys.argv[1:] if argv is None else argv), error)
        return 1
    report_path = None
    try:
        report_path = _output_path(args.report)
        output = _output_path(args.output)
        if output == report_path:
            raise ValueError("output and report must differ")
        census = _read_bounded(args.census, MAX_CENSUS_BYTES)
        stock = _read_bounded(args.stock_proto, MAX_STOCK_BYTES)
        treatment, report = build_treatment(
            census, stock, args.min_calibration, radius=args.radius, max_per_storey=args.max_per_storey,
            max_total=args.max_total, spacing=args.spacing, loot_ratio=args.loot_ratio,
            max_lootmax=args.max_lootmax, min_agreement=args.min_agreement,
            allow_empty_classes=args.allow_empty_classes, reach_source=args.reach_source)
        for path in (output, report_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "xb") as stream:
            stream.write(treatment)
        with open(report_path, "x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except CoverageError as error:
        print(f"interior_points: calibration coverage refusal: {error}", file=sys.stderr)
        _write_refusal(report_path, error)
        return 2
    except (OSError, ValueError) as error:
        print(f"interior_points: {error}", file=sys.stderr)
        _write_refusal(report_path, error)
        return 1
    print(f"treatment {output} sha256={report['treatment']['sha256']} groups={','.join(report['treatment']['groups_changed'])}")
    print(f"calibration min xz coverage {report['calibration']['min_coverage']:.3f} "
          f"(threshold {args.min_calibration:.3f}); report {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
