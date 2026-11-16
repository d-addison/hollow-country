"""Validate lossless handoff traceability and the authored task dependency graph."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path("docs/specs/001-survival-overhaul")


def _text_list(value, *, empty=False):
    return (isinstance(value, list) and (empty or bool(value))
            and all(isinstance(x, str) and x.strip() for x in value))


def _plan_dependencies(plan):
    """Read the explicit dependency declarations in authored task sections."""
    dependencies, errors, current = {}, [], None
    for raw in plan.splitlines():
        line = raw.strip()
        heading = re.fullmatch(r"### (T\d{3,}):.*", line)
        if heading:
            current = heading[1]
            if current in dependencies:
                errors.append(f"duplicate plan task {current}")
            dependencies[current] = None
        elif line.startswith("#"):
            current = None
        elif line.startswith("- Depends:"):
            if current is None:
                errors.append("plan dependency outside task section")
                continue
            if dependencies[current] is not None:
                errors.append(f"{current}: duplicate plan dependency declaration")
            value = line.removeprefix("- Depends:").strip().removesuffix(".")
            if value == "none":
                dependencies[current] = set()
            elif re.fullmatch(r"T\d{3,}(?:,\s*T\d{3,})*", value):
                dependencies[current] = set(re.findall(r"T\d{3,}", value))
            else:
                errors.append(f"{current}: invalid plan dependency declaration")
    for task, deps in dependencies.items():
        if deps is None:
            errors.append(f"{task}: missing plan dependency declaration")
    return dependencies, errors


def validate_contract(graph, trace, requirements, catalog, criteria, plan=None):
    errors = []
    ids = [node["id"] for node in graph["nodes"]]
    if not ids:
        errors.append("empty task graph")
    errors.extend(f"duplicate task {i}" for i, n in Counter(ids).items() if n > 1)
    nodes = set(ids)
    task_traces = {}
    for node in graph["nodes"]:
        label = node["id"]
        scope = node.get("scope") or {}
        contract = node.get("contract") or {}
        for key in ("objective", "context"):
            if not isinstance(scope.get(key), str) or not scope[key].strip():
                errors.append(f"{label}: missing scope {key}")
        acceptance = scope.get("acceptance_criteria")
        if not _text_list(acceptance):
            errors.append(f"{label}: missing acceptance criteria")
            acceptance = []
        for key in ("reads", "traces", "verify_commands"):
            if not _text_list(contract.get(key)):
                errors.append(f"{label}: missing contract {key}")
        for key in ("modifies", "creates"):
            if not _text_list(contract.get(key), empty=True):
                errors.append(f"{label}: invalid contract {key}")
        if not contract.get("modifies") and not contract.get("creates"):
            errors.append(f"{label}: missing write scope")
        if not _text_list(node.get("must_not")):
            errors.append(f"{label}: missing guardrails")
        links = set(contract["traces"]) if _text_list(contract.get("traces")) else set()
        task_traces[label] = links
        errors.extend(f"{label}: unknown task trace {i}"
                      for i in sorted(links - (requirements | catalog | criteria)))
        for item in acceptance:
            acs = set(re.findall(r"AC-\d{3}", item))
            if not acs or acs - criteria or acs - links:
                errors.append(f"{label}: acceptance criterion missing, unknown or untraced")

    entries = trace["requirements"]
    mapped = [row["id"] for row in entries]
    errors.extend(f"duplicate requirement {i}" for i, n in Counter(mapped).items() if n > 1)
    errors.extend(f"unmapped requirement {i}" for i in sorted(requirements - set(mapped)))
    errors.extend(f"unknown requirement {i}" for i in sorted(set(mapped) - requirements))
    tests = set(trace["test_catalog"])
    errors.extend(f"missing test {i}" for i in sorted(catalog - tests))
    errors.extend(f"unknown test {i}" for i in sorted(tests - catalog))
    linked_tests = set()
    for row in entries:
        label = row["id"]
        tasks = row.get("tasks")
        if not _text_list(tasks) or set(tasks) - nodes:
            errors.append(f"{label}: unknown or missing task")
        criterion = row.get("criterion")
        if criterion not in criteria:
            errors.append(f"{label}: unknown criterion")
        row_tests = row.get("tests")
        if not _text_list(row_tests) or set(row_tests) - catalog:
            errors.append(f"{label}: unknown or missing test link")
        else:
            linked_tests.update(row_tests)
        owned = set()
        if _text_list(tasks):
            for task in tasks:
                owned.update(task_traces.get(task, set()))
        for link in ([criterion] if criterion in criteria else []) + (row_tests if _text_list(row_tests) else []):
            if link not in owned:
                errors.append(f"{label}: mapped tasks do not trace {link}")
        # Authored FR/NFRs include offline tooling. This is layer declaration
        # validation only; a conservative T4 label never asserts runtime success.
        layers = {"T0", "T1", "T2", "T3", "T4", "T5"}
        if not re.fullmatch(r"(?:FR|NFR)-\d{3}", label):
            layers -= {"T0", "T1"}
        if row.get("layer") not in layers:
            errors.append(f"{label}: product runtime requirement needs valid runtime evidence layer")
    owned_tests = set().union(*task_traces.values()) if task_traces else set()
    errors.extend(f"orphan test {i}: no requirement link" for i in sorted(catalog - linked_tests))
    errors.extend(f"orphan test {i}: no task owner" for i in sorted(catalog - owned_tests))

    adjacency = {i: [] for i in nodes}
    incoming = {i: set() for i in nodes}
    kinds = {"depends_on", "verify_after", "parent_child", "dataflow", "write_conflict", "rename"}
    for edge in graph.get("edges", []):
        if edge.get("kind") not in kinds:
            errors.append(f"unknown dependency kind {edge.get('kind')}")
        if edge["from"] not in nodes or edge["to"] not in nodes:
            errors.append("unknown dependency endpoint")
        elif edge.get("kind") in {"depends_on", "verify_after"}:
            adjacency[edge["from"]].append(edge["to"])
            if edge["kind"] == "depends_on":
                incoming[edge["to"]].add(edge["from"])
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            errors.append(f"dependency cycle at {node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for target in adjacency[node]:
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(nodes):
        visit(node)
    if plan is None:
        errors.append("missing plan dependency contract")
    else:
        dependencies, plan_errors = _plan_dependencies(plan)
        errors.extend(plan_errors)
        errors.extend(f"missing plan task {i}" for i in sorted(nodes - dependencies.keys()))
        errors.extend(f"unknown plan task {i}" for i in sorted(dependencies.keys() - nodes))
        for task in sorted(nodes & dependencies.keys()):
            if dependencies[task] != incoming[task]:
                errors.append(f"{task}: plan dependency mismatch: plan={sorted(dependencies[task] or [])}, graph={sorted(incoming[task])}")
    return sorted(set(errors))


def check_project(root=ROOT):
    handoff = (root / "docs/SPECIFICATION.md").read_text()
    tests = (root / "docs/TESTING_PERFORMANCE.md").read_text()
    spec = (root / SPEC / "spec.md").read_text()
    requirements = set(re.findall(r"^\| ([A-Z]+-\d{2}) \|", handoff, re.M))
    catalog = set(re.findall(r"^\| ([A-Z]+-\d{3}) \|", tests, re.M))
    requirements.update(re.findall(r"^\s*- ((?:FR|NFR)-\d{3}):", spec, re.M))
    criteria = set(re.findall(r"^\s*- (?:\[[ xX]\] )?(AC-\d{3}):", spec, re.M))
    plan = (root / SPEC / "plan.md").read_text()
    graph = json.loads((root / SPEC / "task-graph.json").read_text())
    trace = json.loads((root / SPEC / "traceability.json").read_text())
    errors = validate_contract(graph, trace, requirements, catalog, criteria, plan)
    return {"status": "fail" if errors else "pass", "requirements": len(requirements),
            "tests": len(catalog), "tasks": len(graph["nodes"]), "errors": errors,
            "scope": "planning integrity only; no DayZ runtime acceptance"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        report = check_project(args.root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {"status": "fail", "errors": [str(exc)]}
    print(json.dumps(report, indent=2))
    return int(report["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
