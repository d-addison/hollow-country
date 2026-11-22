"""Portable planning plus a bounded runner. No gameplay acceptance is ever inferred.

plan() executes nothing. run_automation() runs only drivers resolved from the trusted
registry (tools/testing/drivers.py), records PASS/FAIL/BLOCKED/NOTRUN for every catalog
row and writes evidence-v1 records. An offline PASS supports a row, it never accepts an
original test, and the evidence label is never "multiplayer".

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
import shutil
import signal
import stat
import subprocess
import sys
import time

from tools.testing import artifacts, discovery, drivers
from tools.validate import evidence

MAX_INPUT_BYTES = 1_048_576
MAX_TESTS = 1024
ORIGINAL_IDS = frozenset(
    f"{prefix}-{number:03}"
    for prefix, count in (
        ("AI", 12), ("AUD", 7), ("CE", 12), ("CRF", 7),
        ("HOR", 11), ("INT", 11), ("NET", 8))
    for number in range(1, count + 1)
)
ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = {
    "unittest": "Offline unit tests; run through tools.testing.drivers",
    "bdd": "Offline behavior bindings; run through tools.testing.drivers",
    "runtime": "Offline configuration checks; run through tools.testing.drivers",
    "hygiene": "Offline repository checks; run through tools.testing.drivers",
}
# Owner decision 2026-11-22: two licensed clients, audio judgement and load qualification
# are deferred. They stay traceable here as NOTRUN and are never claimed.
DEFERRED_REASON = "deferred_owner_2026-11-22"
DEFERRED_DRIVER = "deferred.task"
DEFERRED_TASKS = {
    "AV-T017": "Distinct two-client barriers, observation and races",
    "AV-T018": "Owned network delay/retry/adversarial request adapter",
    "AV-T019": "Calibrated real-client audio capture/review seam",
    "AV-T022": "Independent co-op-6 and public-90 workload qualification",
}
# Evidence-v1 needs a CAP-NN id; CAP-99 is reserved for framework records, never a product capability.
FRAMEWORK_CAPABILITY = "CAP-99"
MAX_LOG_BYTES = 8 * 1024 * 1024
MANIFEST_FIELDS = {"schema_version", "run_id", "catalog", "selected", "tasks"}
TASK_FIELDS = {"id", "driver", "covers", "inputs"}
ENV_PASSTHROUGH = ("PATH", "HOME", "LANG", "LC_ALL", "DISPLAY", "WAYLAND_DISPLAY",
                   "XDG_RUNTIME_DIR", "HC_SERVER_ROOT", "HC_WINE_PREFIX", "WINEPREFIX")
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
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ['run']:
        return run_main(arguments[1:])
    if arguments[:1] == ['coverage']:
        return coverage_main(arguments[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path, help='Portable test catalog JSON')
    parser.add_argument('--capability', action='append', default=[], metavar='NAME=STATUS',
                        help='Explicit available, blocked or unknown capability; repeat as needed')
    parser.add_argument('--select', action='append', metavar='TEST_ID',
                        help='Plan only these IDs; repeat as needed')
    args = parser.parse_args(arguments)
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


def _load_json_file(path):
    """Bounded regular-file JSON read with duplicate-key and constant rejection."""
    try:
        path = Path(path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT_BYTES:
            raise ValueError("Expected bounded regular JSON file")
        return json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant)
    except (OSError, UnicodeError) as error:
        raise ValueError("Cannot read JSON file") from error


def _manifest_catalog(manifest):
    """Validate the manifest header and return its repository-relative catalog path."""
    _encoded(manifest)
    if type(manifest) is not dict or not set(manifest) <= MANIFEST_FIELDS or \
            not {"schema_version", "run_id", "tasks"} <= set(manifest):
        raise ValueError("Manifest fields do not match schema")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("Unsupported manifest schema_version")
    _name(manifest["run_id"], "run_id")
    catalog = manifest.get("catalog", "tests/catalog.json")
    if (not isinstance(catalog, str) or not catalog or Path(catalog).is_absolute()
            or ".." in Path(catalog).parts):
        raise ValueError("catalog: expected a repository-relative path")
    return catalog


def _manifest_tasks(manifest, registry, root, identifiers):
    """Resolve every task to a trusted driver and a built argv before anything launches."""
    tasks = manifest["tasks"]
    if type(tasks) is not list or len(tasks) > 256:
        raise ValueError("tasks: expected bounded list")
    seen, plans = set(), []
    for task in tasks:
        if type(task) is not dict or not {"id", "driver"} <= set(task) or not set(task) <= TASK_FIELDS:
            raise ValueError("Task fields do not match schema")
        _name(task["id"], "task id")
        if task["id"] in seen or task["id"] in DEFERRED_TASKS:
            raise ValueError("Duplicate or reserved task id")
        seen.add(task["id"])
        driver = drivers.get(registry, task["driver"])
        covers = task.get("covers", [])
        _strings(covers, "covers", names=True, limit=MAX_TESTS)
        if not set(covers) <= identifiers:
            raise ValueError("covers contains unknown test IDs")
        inputs = task.get("inputs", {})
        if type(inputs) is not dict or not set(inputs) <= set(driver.inputs):
            raise ValueError("inputs: unsupported input for driver")
        plans.append((task["id"], driver, list(covers), driver.argv(root, inputs)))
    return plans


def _fresh_output(output_dir):
    out = Path(output_dir)
    if out.is_symlink() or (out.exists() and (not out.is_dir() or any(out.iterdir()))):
        raise ValueError("output_dir must be a new or empty directory")
    (out / "work").mkdir(parents=True)  # live driver output; only sealed store snapshots are evidence
    return out


def _environment():
    env = {key: os.environ[key] for key in ENV_PASSTHROUGH if key in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _launch(argv, cwd, timeout, log_path):
    """Run argv without a shell in its own session; bound time and output; reap the group."""
    status = "ok"
    code = None
    with open(log_path, "wb") as log:
        try:
            process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, env=_environment(),
                                       start_new_session=True)
        except OSError:
            return None, "launch_error"
        deadline = time.monotonic() + timeout
        while True:
            code = process.poll()
            if code is not None:
                break
            if time.monotonic() > deadline:
                status = "timeout"
            elif log_path.stat().st_size > MAX_LOG_BYTES:
                status = "output_limit"
            else:
                time.sleep(0.05)
                continue
            break
        try:  # the driver's whole process group is owned by this runner
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        if code is None:
            code = process.wait()
    return code, status


def _record(attempt, task_id, outcome, reason, method, steps):
    """Snapshot the log and write one evidence-v1 record into the attempt. Only an offline PASS is documented."""
    log = attempt.artifacts[0]
    base = {"version": 1, "capability_id": FRAMEWORK_CAPABILITY,
            "artifacts": [{"path": log["path"].rsplit("/", 1)[1], "sha256": log["sha256"]}],
            "method": method}
    if outcome == "PASS":
        base.update(status="documented",
                    observation=f"{task_id} {outcome} reason={reason}; supports, never accepts, a test")
    else:
        base.update(status="blocked", obstacle={
            "description": f"{task_id} {outcome} reason={reason}", "steps": steps})
    relative = attempt.add("record.json", json.dumps(base, indent=2, sort_keys=True) + "\n", "evidence_record")
    result = evidence.validate(str(attempt.path("record.json")))
    errors = [error["code"] + ":" + error["field"] for error in result["errors"]]
    return {"path": "evidence/" + relative, "valid": result["valid"], "errors": errors}


def _run_task(out, store, root, task_id, driver, argv, trusted, capabilities):
    log_path = out / "work" / (artifacts.task_slug(task_id) + ".log")
    outcome = reason = None
    if driver.kind == "native" and driver.id not in trusted:
        outcome, reason = "NOTRUN", "untrusted_native"
    else:
        missing = sorted(need for need in driver.needs if capabilities.get(need) != "available")
        if missing:
            outcome, reason = "BLOCKED", "missing_capability:" + ",".join(missing)
        elif driver.memory and not shutil.which("agent-run"):
            outcome, reason = "BLOCKED", "agent_run_missing"
    if outcome is not None:
        text = f"{task_id}: not launched; {outcome} reason={reason}\n"
        output = ""
    else:
        launch = ["agent-run", "--memory", driver.memory, "--", *argv] if driver.memory else argv
        code, status = _launch(launch, root, driver.timeout, log_path)
        raw = log_path.read_bytes().decode("utf-8", errors="replace") if log_path.exists() else ""
        # The footer keeps a silent child's artifact nonempty and records how it ended.
        text = (raw + f"\n[runner] driver={driver.id} exit={code} status={status}\n")
        output = discovery.redact(raw)
        if status != "ok":
            outcome, reason = "FAIL", status
        else:
            outcome, reason = driver.judge(code, output)
    actor, presented = artifacts.producer_for(driver)
    attempt = store.begin(task_id, driver.id, actor=actor, presented_as=presented, client_count=0,
                          pin=artifacts.method_pin(driver))
    # Raw native (zero-client) output is its own role; it never backs a runtime claim.
    log_role = "driver_log" if driver.kind == "offline" else "zero_client_report"
    attempt.add("driver.log", text, log_role)
    steps = ["Read the redacted raw output in the artifact", "Resolve the reason, then rerun in a new output directory"]
    method = f"{driver.id} layer={driver.layer} clients=0 (never multiplayer)"
    result = _record(attempt, task_id, outcome, reason, method, steps)
    if not result["valid"]:
        outcome, reason = "FAIL", "evidence_invalid:" + ",".join(result["errors"])
    attempt.finish(outcome, reason)
    return {"task": task_id, "driver": driver.id, "layer": driver.layer, "outcome": outcome,
            "reason": reason, "evidence": result}


def _row_outcomes(base, capabilities, selection, task_results, covers):
    """Per-row outcome. Original IDs can be supported by a PASS but never promoted by one."""
    deferred = set(discovery.DEFERRED_CAPABILITIES)
    results = {task["task"]: task["outcome"] for task in task_results}
    rows = []
    for row in base["tests"]:
        supporting = sorted(t for t, ids in covers.items() if row["id"] in ids and results.get(t) == "PASS")
        blocked_by = sorted(set(row["requires"]) & deferred)
        if row["id"] not in selection:
            outcome, reason = "NOTRUN", "not_selected"
        elif blocked_by:
            outcome, reason = "NOTRUN", DEFERRED_REASON
        elif row["id"] in ORIGINAL_IDS:
            outcome, reason = "BLOCKED", "original_gameplay_requires_native_execution"
        elif row["missing_capabilities"]:
            outcome, reason = "BLOCKED", "missing_capability:" + ",".join(row["missing_capabilities"])
        elif row["unsupported_modes"]:
            outcome, reason = "BLOCKED", "no_adapter_for_modes:" + ",".join(row["unsupported_modes"])
        else:
            mine = [results[t] for t, ids in covers.items() if row["id"] in ids]
            if "FAIL" in mine:
                outcome, reason = "FAIL", "covering_task_failed"
            elif mine and all(value == "PASS" for value in mine):
                outcome, reason = "PASS", "covering_tasks_passed"
            elif "BLOCKED" in mine:
                outcome, reason = "BLOCKED", "covering_task_blocked"
            else:
                outcome, reason = "NOTRUN", "no_driver_run" if not mine else "covering_task_not_run"
        rows.append({"id": row["id"], "origin": row["origin"], "outcome": outcome, "reason": reason,
                     "supporting_tasks": supporting, "deferred_capabilities": blocked_by})
    return rows


def run_automation(manifest, output_dir, *, trusted_drivers=(), capabilities=None,
                   registry=None, repo_root=None):
    """Run the manifest's drivers and report every catalog row. Native drivers need trust."""
    root = Path(repo_root) if repo_root is not None else ROOT
    registry = drivers.DRIVERS if registry is None else registry
    if isinstance(trusted_drivers, str) or not all(isinstance(item, str) for item in trusted_drivers):
        raise ValueError("trusted_drivers: expected driver IDs")
    trusted = set(trusted_drivers)
    for identifier in trusted:
        drivers.get(registry, identifier)
    catalog = load_catalog(root / _manifest_catalog(manifest))
    identifiers = {row["id"] for row in catalog["tests"]}
    planned = _manifest_tasks(manifest, registry, root, identifiers)
    if capabilities is None:
        capabilities = discovery.planner_capabilities(discovery.inventory(root))
    selected = manifest.get("selected")
    base = plan(catalog, capabilities=capabilities, selected=selected)  # validates both inputs
    selection = identifiers if selected is None else set(selected)
    out = _fresh_output(output_dir)
    store = artifacts.ArtifactStore(out / "evidence", manifest["run_id"])
    pins = artifacts.pins_for(registry, {DEFERRED_DRIVER: artifacts.text_pin(DEFERRED_DRIVER + DEFERRED_REASON)})

    task_results, covers = [], {}
    for task_id, driver, covered, argv in planned:
        covers[task_id] = set(covered)
        task_results.append(_run_task(out, store, root, task_id, driver, argv, trusted, capabilities))
    for task_id, title in DEFERRED_TASKS.items():
        attempt = store.begin(task_id, DEFERRED_DRIVER, actor="offline", presented_as="offline_framework",
                              client_count=0, pin=pins[DEFERRED_DRIVER])
        attempt.add("driver.log", f"{task_id} {title}: NOTRUN {DEFERRED_REASON}\n", "driver_log")
        result = _record(attempt, task_id, "NOTRUN", DEFERRED_REASON,
                         "deferred task layer=none clients=0 (never multiplayer)",
                         ["Wait for the owner to lift the 2026-11-22 deferral", "Build the adapter and qualify it natively"])
        attempt.finish("NOTRUN", DEFERRED_REASON)
        task_results.append({"task": task_id, "driver": None, "layer": "none", "title": title,
                             "outcome": "NOTRUN", "reason": DEFERRED_REASON, "evidence": result})

    # Completeness: the sealed store must validate strictly and hold every task, or the run is incomplete.
    sealed = store.validate(pins, expected_tasks=[result["task"] for result in task_results])
    stored = {"manifest": "evidence/" + evidence.STORE_MANIFEST, "sha256": store.manifest_sha256(),
              "valid": sealed["valid"], "errors": [e["code"] + ":" + e["field"] for e in sealed["errors"]]}

    rows = _row_outcomes(base, capabilities, selection, task_results, covers)
    original = {row["id"]: row for row in rows if row["id"] in ORIGINAL_IDS}
    for missing in sorted(ORIGINAL_IDS - set(original)):
        original[missing] = {"id": missing, "origin": "original", "outcome": "BLOCKED",
                             "reason": "missing_from_catalog", "supporting_tasks": [],
                             "deferred_capabilities": []}
    counts = {name: 0 for name in drivers.OUTCOMES}
    for row in list(original.values()) + [r for r in rows if r["id"] not in ORIGINAL_IDS]:
        counts[row["outcome"]] += 1
    task_counts = {name: sum(1 for t in task_results if t["outcome"] == name) for name in drivers.OUTCOMES}
    order = ("FAIL", "BLOCKED", "NOTRUN") if stored["valid"] else ("FAIL", "INCOMPLETE")
    # No valid manifest: the run is incomplete (below FAIL, above everything else), never passed.
    overall = next((name for name in order if name == "INCOMPLETE" or counts[name] or task_counts[name]), "PASS")
    report = {
        "report_version": 1, "mode": "execution", "acceptance": "not_evaluated",
        "evidence_label": "offline-framework", "clients": 0, "run_id": manifest["run_id"],
        "catalog_id": base["catalog_id"], "catalog_sha256": base["catalog_sha256"],
        "capabilities": dict(sorted(capabilities.items())),
        "trusted_drivers": sorted(trusted),
        "complete": stored["valid"], "store": stored,
        "tasks": task_results, "task_counts": task_counts,
        "counts": counts,
        "coverage": {"original": {"expected": len(ORIGINAL_IDS), "listed": len(original),
                                  "rows": [original[key] for key in sorted(original)]}},
        "tests": rows, "status": overall,
    }
    report["coverage_report"] = _write_coverage(out, store, catalog, manifest, covers, capabilities, selected, pins)
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _write_coverage(out, store, catalog, manifest, covers, capabilities, selected, pins, reviews=None):
    """Post-run hook (AV-T027): coverage.json and coverage.md next to the sealed store, never in the repo."""
    from tools.testing import coverage
    built = coverage.build_report(
        catalog, store.root, run_id=manifest["run_id"], covers=covers, capabilities=capabilities,
        selected=selected, pins=pins, manifest_sha256=store.manifest_sha256(), reviews=reviews,
        expected_tasks=[entry["task"] for entry in store.entries])
    try:
        written = coverage.write_outputs(out, built)
    except ValueError as error:
        return {"written": False, "reason": discovery.redact(error)}
    return dict(written, written=True, status=built["status"], complete=built["complete"])


def coverage_main(arguments):
    """Rebuild the coverage report of a finished run from its sealed store and the run manifest."""
    from tools.testing import coverage
    parser = argparse.ArgumentParser(prog="automation coverage",
                                     description="Coverage, human-review and blocker report for a sealed run")
    parser.add_argument("run_dir", type=Path, help="the run's output directory (holds evidence/)")
    parser.add_argument("manifest", type=Path, help="the manifest the run used (names the covering tasks)")
    parser.add_argument("--reviews", type=Path, help="JSON object id -> {decision, reviewer, artifact:{path, sha256}}")
    parser.add_argument("--out", type=Path, help="directory for coverage.json and coverage.md (default: the run dir)")
    args = parser.parse_args(arguments)
    try:
        manifest = _load_json_file(args.manifest)
        catalog = load_catalog(ROOT / _manifest_catalog(manifest))
        covers = coverage.covers_from_manifest(manifest, {row["id"] for row in catalog["tests"]})
        previous = _load_json_file(args.run_dir / "report.json") if (args.run_dir / "report.json").exists() else {}
        capabilities = previous.get("capabilities", {}) if isinstance(previous, dict) else {}
        reviews = _load_json_file(args.reviews) if args.reviews else None
        store_manifest = coverage._load_store(args.run_dir / "evidence")
        if store_manifest is None or store_manifest.get("run_id") != manifest["run_id"]:
            raise ValueError("manifest run_id does not match the sealed store")
        built = coverage.build_report(
            catalog, args.run_dir / "evidence", run_id=manifest["run_id"], covers=covers,
            capabilities=capabilities, selected=manifest.get("selected"),
            pins=coverage.pins_for_run(drivers.DRIVERS), reviews=reviews)
        written = coverage.write_outputs(args.out or args.run_dir, built)
    except ValueError as error:
        parser.error(discovery.redact(error))
    print(json.dumps(dict(written, status=built["status"], complete=built["complete"], counts=built["counts"]),
                     sort_keys=True))
    return 1 if built["status"] in ("FAIL", "INCOMPLETE") else 0


def run_main(arguments):
    parser = argparse.ArgumentParser(prog="automation run", description="Run a manifest through the trusted registry")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output_dir", type=Path, help="new or empty directory")
    parser.add_argument("--trust", action="append", default=[], metavar="DRIVER_ID",
                        help="allow a native driver; repeat as needed")
    parser.add_argument("--machine", action="store_true", help="include file-presence machine discovery")
    args = parser.parse_args(arguments)
    try:
        machine = discovery.discover_machine() if args.machine else None
        capabilities = discovery.planner_capabilities(discovery.inventory(ROOT, machine))
        report = run_automation(_load_json_file(args.manifest), args.output_dir,
                                trusted_drivers=args.trust, capabilities=capabilities)
    except ValueError as error:
        parser.error(discovery.redact(error))
    print(json.dumps({key: report[key] for key in ("run_id", "status", "complete", "counts", "task_counts")}, sort_keys=True))
    return 1 if report["status"] in ("FAIL", "INCOMPLETE") else 0


if __name__ == '__main__':
    raise SystemExit(main())
