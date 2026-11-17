"""Join stock/exported mapgroupproto data with one native CE probe census.

Observation only. A census counts loose items in one building sample at one moment;
it cannot show that a building can never hold loot. Zero raw points and an empty
census therefore never become a "no loot" verdict here, and every class status is a
neutral description of what was seen, not an acceptance.

Proposed metrics/building_coverage.csv header (this tool never writes into metrics/):
see CSV_HEADER.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

MAX_XML_BYTES = 32 * 1024 * 1024
MAX_CENSUS_BYTES = 8 * 1024 * 1024
MAX_ROWS = 4096
METRICS = Path(__file__).resolve().parents[2] / "metrics"
EVIDENCE = "single-census-observation-only"
EVIDENCE_LIMITS = (
    "single census at one moment after server start; not repeated",
    "item counts depend on the observed building bounding box, whose semantics are unobserved",
    "type lists are bounded per placement and lower-bound the distinct type count",
    "mapgroupproto points describe candidate spawn points, not proof that items spawn",
    "an empty census is not evidence that a building can never hold loot",
)
CSV_HEADER = [
    "building_class", "role", "stock_points", "stock_containers", "stock_lootmax",
    "export_points", "export_containers", "placements_sampled", "placements_found",
    "placements_unreliable", "item_count_mean", "zero_item_fraction",
    "distinct_item_types", "status", "evidence",
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_proto(data, wanted=None):
    """Return {group: {containers, points, lootmax, duplicates}}; never merges duplicates."""
    if len(data) > MAX_XML_BYTES:
        raise ValueError("proto XML exceeds byte budget")
    lowered = data[:4096].lower()
    if b"<!doctype" in lowered or b"<!entity" in data.lower():
        raise ValueError("DOCTYPE/ENTITY declarations are refused")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError(f"proto XML is not well-formed: {error}") from error
    groups = {}
    for group in root.iter("group"):
        name = group.get("name")
        if not name or (wanted is not None and name not in wanted):
            continue
        if name in groups:
            groups[name]["duplicates"] += 1
            continue
        try:
            lootmax = int(group.get("lootmax")) if group.get("lootmax") is not None else None
        except ValueError:
            lootmax = None
        groups[name] = {"containers": sum(1 for _ in group.iter("container")),
                        "points": sum(1 for _ in group.iter("point")),
                        "lootmax": lootmax, "duplicates": 0}
    return groups


def _validated_rows(census):
    rows = census.get("placements") if isinstance(census, dict) else None
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("census placements must be a bounded list")
    clean = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("class"), str) or not isinstance(row.get("found"), bool):
            raise ValueError("census row needs a string 'class' and boolean 'found'")
        if row["found"]:
            if not isinstance(row.get("box_loose"), int) or row["box_loose"] < 0:
                raise ValueError("found census row needs a non-negative integer 'box_loose'")
            if not isinstance(row.get("box_source"), str) or not isinstance(row.get("truncated"), bool):
                raise ValueError("found census row needs 'box_source' and 'truncated'")
            if not isinstance(row.get("types"), list) or not all(isinstance(t, str) for t in row["types"]):
                raise ValueError("found census row needs a 'types' list of strings")
        clean.append(row)
    return clean


def _status(stock, rows_found, usable, items):
    if stock is None:
        return "stock-group-missing"
    if rows_found == 0:
        return "not-found-in-census"
    if usable == 0:
        return "census-box-unusable"
    observed = any(count > 0 for count in items)
    if stock["points"] == 0:
        return "zero-raw-points-items-observed" if observed else "zero-raw-points-census-empty"
    return "points-present-items-observed" if observed else "points-present-census-empty"


def _class_entry(name, rows, stock, export):
    found = [r for r in rows if r["found"]]
    usable = [r for r in found if r["box_source"] != "none" and not r["truncated"]]
    items = [r["box_loose"] for r in usable]
    types = {t for r in usable for t in r["types"]}
    status = _status(stock, len(found), len(usable), items)
    notes = []
    if stock is not None and stock["points"] == 0:
        notes.append("stock proto has zero raw points: an empty census is not evidence of no loot, "
                     "and zero points is not evidence of coverage either")
    if stock is not None and stock["duplicates"]:
        notes.append(f"stock proto lists {stock['duplicates'] + 1} groups with this name; first used")
    if stock is not None and export is not None and (
            (stock["points"], stock["containers"]) != (export["points"], export["containers"])):
        notes.append("export differs from stock (points/containers); engine export is an observation, not an override")
    if len(found) != len(usable):
        notes.append("some found placements had an unusable box or truncated scan and are excluded from statistics")
    roles = sorted({r.get("role") for r in rows if isinstance(r.get("role"), str)})
    return {
        "class": name, "role": roles[0] if len(roles) == 1 else (None if not roles else "mixed"),
        "stock_points": None if stock is None else stock["points"],
        "stock_containers": None if stock is None else stock["containers"],
        "stock_lootmax": None if stock is None else stock["lootmax"],
        "export_points": None if export is None else export["points"],
        "export_containers": None if export is None else export["containers"],
        "export_lootmax": None if export is None else export["lootmax"],
        "placements_sampled": len(rows), "placements_found": len(found),
        "placements_unreliable": len(found) - len(usable),
        "item_count_mean": round(sum(items) / len(items), 4) if items else None,
        "zero_item_fraction": round(sum(1 for c in items if c == 0) / len(items), 4) if items else None,
        "distinct_item_types": len(types) if items else None,
        "status": status, "notes": notes, "evidence": EVIDENCE,
    }


def build_report(stock_proto, export_proto, census, census_sha256=None):
    rows = _validated_rows(census)
    names = sorted({r["class"] for r in rows})
    stock = parse_proto(stock_proto, wanted=set(names))
    export = parse_proto(export_proto, wanted=set(names)) if export_proto is not None else {}
    classes = [_class_entry(n, [r for r in rows if r["class"] == n], stock.get(n), export.get(n)) for n in names]
    return {
        "schema": 1, "kind": "ce-probe-report", "acceptance": "observation-only-not-accepted",
        "inputs": {"stock_proto_sha256": sha256(stock_proto),
                   "export_proto_sha256": None if export_proto is None else sha256(export_proto),
                   "census_sha256": census_sha256,
                   "census_world": census.get("world"), "census_version": census.get("version")},
        "evidence_limits": list(EVIDENCE_LIMITS), "classes": classes,
    }


def csv_text(report):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for entry in sorted(report["classes"], key=lambda e: e["class"]):
        writer.writerow(["" if entry.get(key if key != "building_class" else "class") is None else
                         entry.get(key if key != "building_class" else "class") for key in CSV_HEADER])
    return buffer.getvalue()


def _guard_output(path):
    resolved = Path(path).resolve()
    if resolved == METRICS or METRICS in resolved.parents:
        raise ValueError("refusing to write into the repository metrics/ directory")
    if resolved.exists() or resolved.is_symlink():
        raise ValueError(f"refusing to overwrite {path}")


def _read(path, limit):
    data = Path(path).read_bytes()
    if len(data) > limit:
        raise ValueError(f"{path} exceeds its byte budget")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock-proto", required=True)
    parser.add_argument("--export-proto")
    parser.add_argument("--census", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-csv", required=True)
    args = parser.parse_args(argv)
    try:
        _guard_output(args.out_json)
        _guard_output(args.out_csv)
        census_bytes = _read(args.census, MAX_CENSUS_BYTES)
        try:
            census = json.loads(census_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"census is not valid JSON: {error}") from error
        export = _read(args.export_proto, MAX_XML_BYTES) if args.export_proto else None
        report = build_report(_read(args.stock_proto, MAX_XML_BYTES), export, census, sha256(census_bytes))
        with open(args.out_json, "x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        with open(args.out_csv, "x", encoding="utf-8", newline="") as stream:
            stream.write(csv_text(report))
    except (OSError, ValueError) as error:
        print(f"ce_probe_report: {error}", file=sys.stderr)
        return 1
    print(f"wrote {args.out_json} and {args.out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
