"""Drift check for the autonomous validation data (spec 002 AV-T001). Named apart from the local-only, gitignored automation_spec module.

Validates the checked-in catalog, capability inventory and runtime feature against the
framework contract: exact original ID set, capability names and statuses, runtime scenario
bindings and tags. The graph check (AV-T029) also requires the catalogue rows, the feature-file
tags, the BDD bindings and the driver registry to agree: an unknown or missing ID, a driver
needing an unlisted capability or a binding naming an unknown task is an error. The 001-only
validators (tools.validate.bdd) never claim this graph; they print "002 graph not checked" and
point here. Bindings whose bound unit-test file is gone are listed under "unexecutable_bindings"
(information, not an error: the offline BDD lane cannot run them). When the local-only spec
documents exist they are cross-checked too
(original IDs in plan.md, runtime scenario names, acyclic task graph, deferred tasks); when
absent that part is reported as skipped and never blocks. Reads files only.

CLI: python3 -B -m tools.validate.automation_drift   (prints one JSON report, exit 0 if valid)
"""
import argparse
import json
from pathlib import Path
import re
import sys

from tools.testing import automation, discovery, drivers
from tools.validate import bdd

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = "docs/specs/002-autonomous-validation"
TASK_HEADING = re.compile(r"^### (AV-T\d{3}):", re.M)
ID_TAG = re.compile(r"@([A-Z]+-\d{3})\Z")
TASK_ID = re.compile(r"AV-T\d{3}\Z")
GRAPH = "002"
# Tags that are not catalogue IDs: acceptance-criterion, issue and phase references and the
# feature-level markers of the two feature files.
REFERENCE_TAG = re.compile(r"@(?:AC-\d{3}|ISSUE-\d+|phase\d+)\Z")
MARKER_TAGS = frozenset(bdd.RUNTIME_FEATURE_TAGS) | {"@offline", "@synthetic"}
BINDING_TIERS = ("unit", "slow", "legacy")


def _graph(tasks_text):
    """AV task -> dependencies, from the '- [ ] ... depends: ...' line of each task."""
    sections = re.split(r"^### ", tasks_text, flags=re.M)[1:]
    graph = {}
    for section in sections:
        name = section[:7]
        match = re.search(r"depends:\s*([^.]*)\.", " ".join(section.split()))
        graph[name] = sorted(set(re.findall(r"AV-T\d{3}", match.group(1)))) if match else []
    return graph


def _cycle(graph):
    state = {}

    def visit(node):
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        if any(visit(dep) for dep in graph.get(node, ()) if dep in graph):
            return True
        state[node] = 2
        return False

    return any(visit(node) for node in graph)


def _catalogue_errors(catalog, rows):
    """Cross-references inside the catalogue itself: every named ID must be a row."""
    errors = []
    for key, row in sorted(rows.items()):
        for other in row["related_ids"]:
            if other not in rows:
                errors.append(f"catalog row {key}: related ID {other} is not a catalog row")
    coverage = catalog["coverage"] if isinstance(catalog["coverage"], dict) else {}
    for key in coverage.get("row_sources", {}):
        if key not in rows:
            errors.append(f"coverage.row_sources names unknown row {key}")
    declared = {source.get("id") for source in catalog["sources"] if isinstance(source, dict)}
    for key, entries in coverage.get("row_sources", {}).items():
        for entry in entries:
            if entry.get("source") not in declared:
                errors.append(f"coverage.row_sources {key}: source {entry.get('source')} is not declared")
    for parent, parts in coverage.get("split_criteria", {}).items():
        for part in parts:
            if part not in rows:
                errors.append(f"coverage.split_criteria {parent}: {part} is not a catalog row")
    for issue, entry in coverage.get("extensions", {}).get("issues", {}).items():
        for key in entry.get("test_ids", []):
            if key not in rows:
                errors.append(f"coverage.extensions issue {issue}: {key} is not a catalog row")
    return errors


def _tag_errors(label, tags, rows):
    errors = []
    for tag in tags:
        if tag in MARKER_TAGS or REFERENCE_TAG.fullmatch(tag):
            continue
        match = ID_TAG.fullmatch(tag)
        if not match:
            errors.append(f"{label}: tag {tag} is neither a marker, a reference nor a catalog ID")
        elif match.group(1) not in rows:
            errors.append(f"{label}: tag {tag} is not a catalog ID")
    return errors


def _feature_errors(root, rows):
    """Offline feature tags, scenarios and steps against the bindings; runtime tags against rows."""
    errors = []
    try:
        text = (root / "tests/features/offline.feature").read_text(encoding="utf-8")
        scenarios = bdd.parse_scenarios(text)
        feature_tags, tags = bdd.parse_feature_tags(text)
    except (OSError, ValueError) as error:
        return [f"offline.feature: {error}"]
    errors += _tag_errors("offline.feature", feature_tags, rows)
    names = [name for name, _ in scenarios]
    for name, steps in scenarios:
        if name not in bdd.BINDINGS:
            errors.append(f"offline.feature scenario has no binding: {name}")
        elif steps != bdd.BINDINGS[name][0]:
            errors.append(f"offline.feature scenario steps differ from its binding: {name}")
        errors += _tag_errors("offline.feature", tags.get(name, ()), rows)
    for name in sorted(set(bdd.BINDINGS) - set(names)):
        errors.append(f"binding has no offline.feature scenario: {name}")
    return errors


def unexecutable_bindings(root):
    """Bound scenarios whose unit-test file exists in no tier; the offline BDD lane cannot run them."""
    root = Path(root)
    return sorted(name for name, (_, pattern) in bdd.BINDINGS.items()
                  if not any(next((root / "tests" / tier).glob(pattern), None) for tier in BINDING_TIERS))


def _binding_errors(rows):
    errors = []
    for name, (tags, steps, tasks) in bdd.RUNTIME_BINDINGS.items():
        errors += _tag_errors(f"runtime binding {name}", tags, rows)
        for task in tasks:
            if not TASK_ID.fullmatch(task):
                errors.append(f"runtime binding {name}: {task} is not a task ID")
    for name, (steps, pattern) in bdd.BINDINGS.items():
        if not steps or not pattern.startswith("test_") or not pattern.endswith(".py"):
            errors.append(f"binding {name}: malformed steps or test file pattern")
    return errors


def _driver_errors(root, capabilities, registry):
    """Registry entries against capability names, trust classes and the deferred-task constants."""
    errors = []
    for key, driver in sorted(registry.items()):
        if driver.id != key or not re.fullmatch(r"(?:offline|native)\.[a-z_]+", key):
            errors.append(f"driver {key}: ID does not match its registry key or the offline./native. form")
        if driver.kind not in ("offline", "native") or not key.startswith(driver.kind + "."):
            errors.append(f"driver {key}: kind does not match its ID")
        for need in driver.needs:
            if need not in capabilities:
                errors.append(f"driver {key}: needs capability {need} that no catalog row lists")
        if not driver.timeout > 0:
            errors.append(f"driver {key}: timeout must be positive")
        try:
            argv = driver.argv(root, {})
        except ValueError:
            if not driver.inputs:
                errors.append(f"driver {key}: argv failed without declared inputs")
            continue
        module = argv[argv.index("-m") + 1] if "-m" in argv else ""
        if not module or not (root / (module.replace(".", "/") + ".py")).is_file():
            errors.append(f"driver {key}: module {module or '?'} is not in the repository")
    if automation.DEFERRED_DRIVER in registry:
        errors.append("deferred.task must stay out of the registry; deferred tasks are never runnable")
    for task in automation.DEFERRED_TASKS:
        if not TASK_ID.fullmatch(task):
            errors.append(f"deferred task {task} is not a task ID")
    return errors


def validate(root=ROOT, registry=None):
    root = Path(root)
    registry = drivers.DRIVERS if registry is None else registry
    errors, skipped = [], []

    def fail(message):
        errors.append(message)

    try:
        catalog = automation.load_catalog(root / "tests/catalog.json")
    except ValueError as error:
        return {"report_version": 1, "graph": GRAPH, "valid": False, "errors": [f"catalog: {error}"],
                "skipped": [], "unexecutable_bindings": []}
    rows = {row["id"]: row for row in catalog["tests"]}
    originals = {key for key, row in rows.items() if row["origin"] == "original"}
    if originals != set(automation.ORIGINAL_IDS):
        fail("catalog original IDs differ from the original ID set: " +
             ", ".join(sorted(originals ^ set(automation.ORIGINAL_IDS))))
    declared = catalog["coverage"].get("original", {}) if isinstance(catalog["coverage"], dict) else {}
    if sorted(declared.get("ids", [])) != sorted(automation.ORIGINAL_IDS) or \
            declared.get("expected_count") != len(automation.ORIGINAL_IDS):
        fail("coverage.original does not list every original ID")

    try:
        document = json.loads((root / "tests/capabilities.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        document = None
        fail("tests/capabilities.json unreadable")
    if document is not None:
        required = {name for row in rows.values() for name in row["requires"]}
        capabilities = document.get("capabilities", {})
        observations = document.get("observations", {})
        if document.get("catalog_id") != catalog["catalog_id"]:
            fail("capabilities catalog_id differs from the catalog")
        if set(capabilities) != required:
            fail("capabilities names differ from catalog requirements: " +
                 ", ".join(sorted(set(capabilities) ^ required)))
        if set(observations) != set(capabilities):
            fail("observations and capabilities name different sets")
        for name, status in capabilities.items():
            fact = observations.get(name, {})
            if fact.get("status") not in discovery.STATUSES or not fact.get("evidence"):
                fail(f"capability {name}: observation needs a status and evidence")
            elif discovery.PLANNER_STATUS[fact["status"]] != status:
                fail(f"capability {name}: planner status does not match its observation")
            if name in discovery.DEFERRED_CAPABILITIES and status != "unknown":
                fail(f"capability {name}: deferred capability must stay unknown")
        if document.get("context", {}).get("machine_discovery_performed") is not False:
            fail("checked-in capabilities must be repository-only")

    errors.extend(_catalogue_errors(catalog, rows))
    errors.extend(_binding_errors(rows))
    errors.extend(_feature_errors(root, rows))
    capability_names = {name for row in rows.values() for name in row["requires"]}
    errors.extend(_driver_errors(root, capability_names, registry))

    try:
        report = bdd.runtime_report((root / "tests/features/runtime.feature").read_text())
    except (ValueError, OSError) as error:
        report = None
        fail(f"runtime.feature: {error}")
    if report is not None:
        for scenario in report["scenarios"]:
            for tag in scenario["tags"]:
                match = ID_TAG.fullmatch(tag)
                if match and not match.group(1).startswith("AC-") and match.group(1) not in rows:
                    fail(f"runtime.feature tag {tag} is not a catalog ID")

    spec = root / SPEC_DIR
    if not (spec / "plan.md").is_file() or not (spec / "tasks.md").is_file():
        skipped.append("spec documents absent (local-only); document cross-checks not run")
    else:
        plan_text = (spec / "plan.md").read_text(encoding="utf-8")
        tasks_text = (spec / "tasks.md").read_text(encoding="utf-8")
        mapped = set(re.findall(r"^\| ([A-Z]+-\d{3}) \|", plan_text, re.M))
        if mapped != set(automation.ORIGINAL_IDS):
            fail("plan.md original-ID map differs from the original ID set")
        section = plan_text.split("## Existing runtime BDD", 1)[-1].split("\n## ", 1)[0]
        names = re.findall(r"^\| ([^|]+?) \| AV-T", section, re.M)
        if names != list(bdd.RUNTIME_BINDINGS):
            fail("plan.md runtime scenario names differ from the runtime bindings")
        headings = TASK_HEADING.findall(tasks_text)
        graph = _graph(tasks_text)
        if len(headings) != len(set(headings)) or set(headings) != set(graph):
            fail("tasks.md task headings are duplicated or unparsed")
        if any(dep not in graph for deps in graph.values() for dep in deps):
            fail("tasks.md references an unknown dependency")
        if _cycle(graph):
            fail("tasks.md dependency graph has a cycle")
        for task in automation.DEFERRED_TASKS:
            if task not in graph:
                fail(f"deferred task {task} missing from tasks.md")
        for scenario in (report or {}).get("scenarios", []):
            for task in scenario["tasks"]:
                if task not in graph:
                    fail(f"runtime scenario task {task} missing from tasks.md")
    return {"report_version": 1, "graph": GRAPH, "valid": not errors, "errors": errors, "skipped": skipped,
            "unexecutable_bindings": unexecutable_bindings(root)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    report = validate(args.root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
