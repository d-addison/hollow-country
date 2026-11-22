"""Drift check for the autonomous validation data (spec 002 AV-T001). Named apart from the local-only, gitignored automation_spec module.

Validates the checked-in catalog, capability inventory and runtime feature against the
framework contract: exact original ID set, capability names and statuses, runtime scenario
bindings and tags. When the local-only spec documents exist they are cross-checked too
(original IDs in plan.md, runtime scenario names, acyclic task graph, deferred tasks); when
absent that part is reported as skipped and never blocks. Reads files only.

CLI: python3 -B -m tools.validate.automation_drift   (prints one JSON report, exit 0 if valid)
"""
import argparse
import json
from pathlib import Path
import re
import sys

from tools.testing import automation, discovery
from tools.validate import bdd

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = "docs/specs/002-autonomous-validation"
TASK_HEADING = re.compile(r"^### (AV-T\d{3}):", re.M)
ID_TAG = re.compile(r"@([A-Z]+-\d{3})\Z")


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


def validate(root=ROOT):
    root = Path(root)
    errors, skipped = [], []

    def fail(message):
        errors.append(message)

    try:
        catalog = automation.load_catalog(root / "tests/catalog.json")
    except ValueError as error:
        return {"report_version": 1, "valid": False, "errors": [f"catalog: {error}"], "skipped": []}
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
    return {"report_version": 1, "valid": not errors, "errors": errors, "skipped": skipped}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    report = validate(args.root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
