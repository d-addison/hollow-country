"""Portable planning only. No subprocesses or gameplay acceptance.

Capabilities are explicit name -> available|blocked|unknown declarations.
Related IDs are traceability references, not execution dependencies.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

MAX_INPUT_BYTES = 1_048_576
MAX_TESTS = 1024
ORIGINAL_IDS = frozenset(
    f"{prefix}-{number:03}"
    for prefix, count in (
        ("AI", 12), ("AUD", 7), ("CE", 12), ("CRF", 7),
        ("HOR", 11), ("INT", 11), ("NET", 8))
    for number in range(1, count + 1)
)
ADAPTERS = {
    "unittest": "Offline unit tests; execution pending",
    "bdd": "Offline behavior bindings; execution pending",
    "runtime": "Offline configuration checks; execution pending",
    "hygiene": "Offline repository checks; execution pending",
}
ROOT_FIELDS = {"schema_version", "catalog_id", "sources", "tests", "coverage"}
ROW_FIELDS = {
    "id", "origin", "scenario", "criterion", "modes", "requires",
    "assertions", "evidence_requirements", "related_ids",
}
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}\Z")


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{label}: expected nonempty bounded text")


def _name(value, label):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError(f"{label}: invalid identifier")


def _strings(value, label, names=False, required=False, limit=128):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"{label}: expected bounded list")
    if required and not value:
        raise ValueError(f"{label}: empty list")
    for item in value:
        (_name if names else _text)(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f"{label}: duplicate values")


def _encoded(value):
    """Bound direct JSON inputs, including nesting and aggregate item count."""
    budget = [0, 0]

    def visit(node, depth):
        budget[0] += 1
        budget[1] += len(node) if type(node) is str else 4
        if budget[1] > MAX_INPUT_BYTES:
            raise ValueError('Aggregate input budget exceeded')
        if depth > 16 or budget[0] > 100_000:
            raise ValueError("JSON nesting/item budget exceeded")
        if type(node) is dict:
            for key, item in node.items():
                if not isinstance(key, str):
                    raise ValueError("Non-string JSON key")
                visit(key, depth + 1)
                visit(item, depth + 1)
        elif type(node) is list:
            for item in node:
                visit(item, depth + 1)
        elif type(node) not in (str, int, float, bool, type(None)):
            raise ValueError("Non-JSON value")
        elif isinstance(node, str) and len(node) > MAX_INPUT_BYTES:
            raise ValueError("Oversized string")

    visit(value, 0)
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          allow_nan=False, ensure_ascii=True).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("Invalid JSON input") from error
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("Input exceeds byte budget")
    return data


def validate_catalog(catalog):
    encoded = _encoded(catalog)
    if type(catalog) is not dict or set(catalog) != ROOT_FIELDS:
        raise ValueError("Catalog fields do not match schema")
    version = catalog["schema_version"]
    if type(version) is not int or version != 1:
        raise ValueError("Unsupported schema_version")
    _name(catalog["catalog_id"], "catalog_id")
    for field in ("sources", "coverage"):
        if type(catalog[field]) not in (dict, list):
            raise ValueError(f"{field}: expected object or list")
    rows = catalog["tests"]
    if type(rows) is not list or not 1 <= len(rows) <= MAX_TESTS:
        raise ValueError("Expected 1..1024 test rows")
    seen = set()
    for row in rows:
        if type(row) is not dict or set(row) != ROW_FIELDS:
            raise ValueError("Test fields do not match schema")
        _name(row["id"], "id")
        if row["id"] in seen:
            raise ValueError("Duplicate test ID")
        seen.add(row["id"])
        for field in ("origin", "scenario", "criterion"):
            _text(row[field], field)
        _strings(row["modes"], "modes", names=True, required=True, limit=16)
        _strings(row["requires"], "requires", names=True)
        _strings(row["assertions"], "assertions", required=True)
        _strings(row["evidence_requirements"], "evidence_requirements",
                 required=True)
        _strings(row["related_ids"], "related_ids", names=True)
    return encoded


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"Invalid JSON number: {value}")


def load_catalog(path):
    """Read only the explicit catalog; never consult local specs."""
    try:
        path = Path(path)
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_INPUT_BYTES:
            raise ValueError('Expected bounded regular catalog')
        flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            opened = os.fstat(stream.fileno())
            identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            if not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened):
                raise ValueError('Catalog changed before read')
            data = stream.read(MAX_INPUT_BYTES + 1)
            if identity(opened) != identity(os.fstat(stream.fileno())) or len(data) != opened.st_size:
                raise ValueError('Catalog changed during read')
        if len(data) > MAX_INPUT_BYTES:
            raise ValueError("Input exceeds byte budget")
        catalog = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                             parse_constant=_constant)
        validate_catalog(catalog)
        return catalog
    except (OSError, UnicodeError, RecursionError) as error:
        raise ValueError("Cannot read catalog") from error


def plan(catalog, *, capabilities=None, selected=None):
    """Preserve supplied criteria without executing or passing tests."""
    encoded = validate_catalog(catalog)
    capabilities = {} if capabilities is None else capabilities
    if type(capabilities) is not dict or len(capabilities) > 512:
        raise ValueError("Expected bounded capability mapping")
    for name, status in capabilities.items():
        _name(name, "capability")
        if type(status) is not str or status not in {
                "available", "blocked", "unknown"}:
            raise ValueError("Invalid capability status")

    identifiers = {row["id"] for row in catalog["tests"]}
    if selected is None:
        selection = identifiers
    else:
        _strings(selected, "selected", names=True, limit=MAX_TESTS)
        selection = set(selected)
        if not selection <= identifiers:
            raise ValueError("Selection contains unknown test IDs")

    rows = []
    counts = {"PASS": 0, "FAIL": 0, "BLOCKED": 0, "NOTRUN": 0}
    for source in catalog["tests"]:
        row = copy.deepcopy(source)
        missing = sorted(
            name for name in row["requires"]
            if capabilities.get(name) != "available"
        )
        unsupported = sorted(set(row["modes"]) - set(ADAPTERS))
        if row["id"] not in selection:
            status, reason = "NOTRUN", "Not selected"
        elif row["id"] in ORIGINAL_IDS:
            status, reason = (
                "BLOCKED", "Original gameplay requires actual execution"
            )
        elif missing:
            status, reason = (
                "BLOCKED", "Capabilities unavailable or unknown"
            )
        elif unsupported:
            status, reason = (
                "BLOCKED", "No allowed adapter for requested modes"
            )
        else:
            status, reason = (
                "NOTRUN", "Eligible offline modes; planner executes nothing"
            )
        row.update(
            status=status,
            reason=reason,
            missing_capabilities=missing,
            unsupported_modes=unsupported,
        )
        rows.append(row)
        counts[status] += 1

    return {
        "report_version": 1,
        "mode": "planning-only",
        "acceptance": "not_evaluated",
        "catalog_id": catalog["catalog_id"],
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "sources": copy.deepcopy(catalog["sources"]),
        "coverage": copy.deepcopy(catalog["coverage"]),
        "missing_original_ids": sorted(ORIGINAL_IDS - identifiers),
        "capabilities": dict(sorted(capabilities.items())),
        "adapters": dict(ADAPTERS),
        "counts": counts,
        "tests": rows,
        "status": "BLOCKED" if counts["BLOCKED"] else "NOTRUN",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path, help='Portable test catalog JSON')
    parser.add_argument('--capability', action='append', default=[], metavar='NAME=STATUS',
                        help='Explicit available, blocked or unknown capability; repeat as needed')
    parser.add_argument('--select', action='append', metavar='TEST_ID',
                        help='Plan only these IDs; repeat as needed')
    args = parser.parse_args(argv)
    capabilities = {}
    try:
        for assignment in args.capability:
            name, separator, status = assignment.partition('=')
            if not separator or name in capabilities:
                raise ValueError('Capability assignments must be unique NAME=STATUS pairs')
            capabilities[name] = status
        report = plan(load_catalog(args.catalog), capabilities=capabilities,
                      selected=args.select)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
    # Success means a plan was generated, never that gameplay passed.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
