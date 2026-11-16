"""Create/update explicitly requested project tracking. Dry-run unless --apply.

Uses authenticated gh; never sends credentials or game files. Existing issue
states are preserved. Matching is by exact task prefix/milestone title, with
duplicates rejected. Generated index is written only after successful API calls.
"""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
FEATURE = "docs/specs/001-survival-overhaul"
REPO = "d-addison/hollow-country"
BASE = f"https://github.com/{REPO}"
PHASES = {
    "P0": "Foundation, official tooling and native baseline",
    "P1": "CE building coverage",
    "P2": "Persistent safe interiors",
    "P3": "Economy and authoritative search",
    "P4": "Crafting and salvage",
    "P5": "Native infected competence",
    "P6": "Investigation and variants",
    "P7": "Audible chains and persistent hordes",
    "P8": "Integration, performance and private handoff",
}


def api(path, method="GET", data=None):
    command = ["gh", "api", path, "--method", method]
    if data is not None:
        command += ["--input", "-"]
    result = subprocess.run(command, input=json.dumps(data) if data is not None else None,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def unique(items, key):
    result = {}
    for item in items:
        name = key(item)
        if name in result:
            raise ValueError(f"Duplicate tracking identity: {name}")
        result[name] = item
    return result


def body(node, dependencies, links):
    tid = node["id"]
    contract = node["contract"]
    acceptance = "\n".join(f"- [ ] {item}" for item in node["scope"]["acceptance_criteria"])
    files = contract["modifies"] + contract["creates"]
    paths = "\n".join(f"- `{p}`" for p in files)
    deps = ", ".join(links.get(i, i) for i in dependencies) or "None"
    return f"""Tracking task **{tid}** from the complete Hollow Country specification.

{node['scope']['objective']}

[Specification]({BASE}/blob/main/{FEATURE}/spec.md) · [Plan (section {tid})]({BASE}/blob/main/{FEATURE}/plan.md) · [Canonical graph]({BASE}/blob/main/{FEATURE}/task-graph.json) · [Traceability]({BASE}/blob/main/{FEATURE}/traceability.json)

Depends on: {deps}. Dependencies are evidence gates, not just issue status.

Acceptance:

{acceptance}

Writable deliverables (revise contract before changing scope):

{paths}

Behavior/evidence IDs: {', '.join(contract['traces'])}.

- [ ] Record failing behavioral test/scenario before implementation (TDD/SDD/BDD).
- [ ] Complete the smallest change and relevant regressions.
- [ ] Attach exact commands, build/commit and hashed evidence; describe limitations.
- [ ] Run native and two-client tests where required; compare calibrated performance.

Offline utilities never prove native gameplay. Complex features stay disabled
until accepted. This issue is a work item, not an implemented-feature claim.
Do not attach purchased assets, private keys, credentials or complete game dumps.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    graph = json.loads((ROOT / FEATURE / "task-graph.json").read_text())
    nodes = graph["nodes"]
    if not args.apply:
        print(json.dumps({"repository": REPO, "milestones": PHASES,
                          "issues": [{"id": n["id"], "title": n["title"]} for n in nodes]}, indent=2))
        return
    prefix = f"repos/{REPO}"
    repo = api(prefix)
    if not repo["private"]:
        raise ValueError("Expected the authorized private repository")
    milestones = unique(api(f"{prefix}/milestones?state=all&per_page=100"), lambda m: m["title"])
    numbers = {}
    for phase, title in PHASES.items():
        name = f"{phase}: {title}"
        data = {"title": name, "description": f"Hollow Country {phase} acceptance gate. See {BASE}/blob/main/{FEATURE}/plan.md. Complete native evidence before closing; no invented due date."}
        if name in milestones:
            milestone = milestones[name]
        else:
            milestone = api(f"{prefix}/milestones", "POST", data)
        numbers[phase] = milestone["number"]
    existing = api(f"{prefix}/issues?state=all&per_page=100")
    tasks = unique([i for i in existing if not i.get("pull_request") and
                    any(i["title"].startswith(n["id"] + ": ") for n in nodes)],
                   lambda i: i["title"].split(":", 1)[0])
    dependencies = {n["id"]: [] for n in nodes}
    for edge in graph["edges"]:
        dependencies[edge["to"]].append(edge["from"])
    for node in nodes:
        tid = node["id"]
        if tid not in tasks:
            tasks[tid] = api(f"{prefix}/issues", "POST", {
                "title": f"{tid}: {node['title']}",
                "body": body(node, dependencies[tid], {}),
                "milestone": numbers[node["title"].split(":", 1)[0]]})
    links = {tid: f"#{issue['number']}" for tid, issue in tasks.items()}
    for node in nodes:
        tid = node["id"]
        desired = body(node, dependencies[tid], links)
        if tasks[tid]["body"] != desired:
            api(f"{prefix}/issues/{tasks[tid]['number']}", "PATCH", {"body": desired})
    index = {"repository": REPO, "milestones": numbers,
             "tasks": {n["id"]: {"number": tasks[n["id"]]["number"],
                                  "url": tasks[n["id"]]["html_url"]} for n in nodes}}
    (ROOT / FEATURE / "github-tracking.json").write_text(json.dumps(index, indent=2) + "\n")
    rows = "\n".join(f"| [{n['id']}]({tasks[n['id']]['html_url']}) | {n['title']} |" for n in nodes)
    (ROOT / "docs/PROJECT_TRACKING.md").write_text(f"""# Project tracking

[All issues]({BASE}/issues) · [Milestones]({BASE}/milestones)

Every task in the full P0–P8 spec has an issue and a phase milestone. Read
[task status](specs/001-survival-overhaul/tasks.md) for the verified local state;
an open or closed issue alone cannot establish runtime acceptance.

| Issue | Scope |
|---|---|
{rows}

Canonical [spec](specs/001-survival-overhaul/spec.md),
[plan](specs/001-survival-overhaul/plan.md),
[graph](specs/001-survival-overhaul/task-graph.json) and
[traceability](specs/001-survival-overhaul/traceability.json) remain authoritative.
Update these together when requirements or dependencies change. New bugs and
scope changes use the repository issue templates and link requirement/test IDs.

`python3 -B tools/project/sync_github.py` previews the roadmap; `--apply` creates
missing tracking and refreshes generated task bodies. It preserves issue states
and milestone dates. Review generated body changes before applying to avoid
overwriting manually edited task descriptions. Use issue comments for execution
evidence and discussion; keep the generated description tied to the spec.
""")
    print(f"Tracking verified: {len(numbers)} milestones, {len(nodes)} task issues")


if __name__ == "__main__":
    main()
