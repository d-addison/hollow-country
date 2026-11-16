"""Rebuild authored planning artifacts, never runtime acceptance or task status."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/specs/001-survival-overhaul"
# id, phase, title, dependencies, criterion, paths, tests, concrete done condition
TASKS = [
 ("T001", "P0", "Private source, confirmed decisions and lossless traceability", [], "AC-001", ["docs/specs/001-survival-overhaul/spec.md", "docs/specs/001-survival-overhaul/traceability.json"], ["NET-008"], "All confirmed requirements and catalog tests mapped; private repository verified; no assets/secrets committed"),
 ("T002", "P0", "Inventory local official binaries, host and sources", ["T001"], "AC-002", ["research/P0-build-inventory.md"], ["CE-001"], "Exact client/server/Tools versions and paths, actual OS/hardware, source pins; missing installs explicit"),
 ("T003", "P0", "Install official Tools and Server; vanilla local join", ["T002"], "AC-002", ["research/P0-server-launch.md"], ["NET-004", "NET-005"], "Vanilla Chernarus local join, respawn, inventory, reconnect and persistence restart observed with logs"),
 ("T004", "P0", "Diagnostic hello-world, official package and signature smoke test", ["T003"], "AC-002", ["research/P0-first-mod.md", "mods/HollowCountry/scripts/4_World/Core/HCNativeSelfTests.c", "tools/package/Invoke-NativeSmoke.ps1"], ["NET-006", "NET-008"], "Inspect current scripts, verify diagnostic hook then signed PBO in normal client/server, record hashes; no unproven API"),
 ("T005", "P0", "Native baseline fixtures and 3–6-player budget calibration", ["T003"], "AC-009", ["research/P0-baseline.md", "metrics/baseline.csv"], ["CE-001", "AI-001", "AUD-001"], "Verified building fixtures, controlled repeated warm/cold runs, host contention, proposed p95/p99/client budgets approved"),
 ("T006", "P0", "TDD native CE offline audit and modular input validation", ["T001"], "AC-003", ["tools/audit/ce_audit.py", "tests/unit/test_ce_audit.py"], ["CE-001", "CE-011"], "Recorded red/green; malformed/duplicate/nonfinite/negative inputs rejected; raw point/placement counts and hashes; no engine eligibility claim"),
 ("T007", "P0", "TDD repeated paired benchmark comparator", ["T001"], "AC-009", ["tools/benchmark/compare.py", "tests/unit/test_benchmark.py"], ["HOR-008"], "Recorded red/green; incompatible evidence rejected; p95/p99 and client lows checked; missing calibrated thresholds/manifests INCOMPLETE"),
 ("T008", "P0", "TDD evidence promotion validator", ["T001"], "AC-010", ["tools/validate/evidence.py", "tests/unit/test_evidence.py"], ["NET-006"], "Recorded red/green; runtime promotions require build/method/artifact hashes, two-client and performance evidence; missing/tampered files fail"),
 ("T009", "P0", "Spec/task integrity, executable offline BDD and static CI", ["T006", "T007", "T008"], "AC-012", ["tools/validate/project.py", "tests/unit/test_project_contract.py", "tests/features/offline.feature", ".github/workflows/static.yml"], ["NET-008"], "Unmapped IDs/cycles fail, all behavior bindings execute; Banso spec/plan/task/BDD checks run; inexpensive static CI excludes game builds"),
 ("T010", "P1", "Audit actual CE snapshot and identify apartment/barracks", ["T004", "T005", "T006"], "AC-004", ["research/experiments/EXP-CE-coverage.md", "metrics/building_coverage.csv"], ["CE-001", "CE-003", "CE-004", "CE-012"], "Pinned local source hashes, exact classes/positions and eligible point evidence; zero raw points not mistaken for verified no-loot"),
 ("T011", "P1", "Minimal supported CE coverage fix and controlled comparison", ["T010"], "AC-004", ["mission/hollow-country/README.md", "research/experiments/EXP-CE-override.md"], ["CE-002", "CE-003", "CE-004", "CE-011"], "Observed correct override/point update mechanism, valid placements and zero CE errors; backup/rollback and matched benchmark"),
 ("T012", "P3", "Contextual economy routes and conservative budgets", ["T011"], "AC-004", ["research/experiments/EXP-loot-balance.md", "metrics/loot_routes.csv"], ["CE-005", "CE-006", "CE-007", "CE-008", "CE-009", "CE-012"], "Essentials have two credible routes; soft high-tier exceptions, diversity and world counts measured; tune rates only after baseline"),
 ("T013", "P2", "Native object and furniture targeting feasibility", ["T004", "T005"], "AC-005", ["research/experiments/EXP-interior-feasibility.md"], ["INT-004", "INT-005", "INT-008", "INT-010", "INT-011"], "One verified house, safe asset catalog, target/proxy feasibility and 0/5/10/20 prop sweep; no blocked doors/nav regression"),
 ("T014", "P2", "Stable building identity and three persistent layouts", ["T013"], "AC-005", ["mods/HollowCountry/scripts/4_World/Interiors/README.md", "research/experiments/EXP-layout-persistence.md"], ["INT-001", "INT-002", "INT-004", "INT-005", "INT-006", "INT-009", "INT-010", "INT-011"], "Three layouts/two histories for tested class, deterministic instance IDs with collision handling; restart/migration idempotence and two-client sync"),
 ("T015", "P3", "Server search allocation and crash-safe depletion", ["T012", "T014", "T008"], "AC-005", ["mods/HollowCountry/scripts/4_World/Interiors/SEARCH.md", "research/experiments/EXP-search-transaction.md"], ["INT-003", "INT-006", "INT-007", "INT-008", "CE-009", "CE-010", "NET-001", "NET-002", "NET-003", "NET-005", "NET-007"], "Server range/LOS/item whitelist, quota and depletion journal; two-client same-site retry/crash/full inventory no duplication; no drawer refill"),
 ("T016", "P4", "Vanilla recipe audit and three salvage pilot definitions", ["T004"], "AC-006", ["research/experiments/EXP-salvage-feasibility.md"], ["CRF-001", "CRF-006", "CRF-007"], "Avoid duplicate vanilla recipes; three useful permitted pilots including camo-net feasibility; typed material and wear ledger, no positive resource cycles"),
 ("T017", "P4", "Native authoritative salvage implementation", ["T016", "T008"], "AC-006", ["mods/HollowCountry/scripts/4_World/Crafting/README.md", "research/experiments/EXP-salvage-transaction.md"], ["CRF-001", "CRF-002", "CRF-003", "CRF-004", "CRF-005", "CRF-006", "CRF-007", "NET-001", "NET-002", "NET-003", "NET-007"], "Inspect native transaction semantics before atomicity design; cancellation/death/disconnect/tool wear/full inventory and two-client races all observed"),
 ("T018", "P5", "Risk-first native AI doorway/LOS/door/audio/injury experiments", ["T004", "T005"], "AC-007", ["research/experiments/EXP-AI-native.md"], ["AI-001", "AI-003", "AI-008", "AI-010", "AI-011", "AUD-001", "AUD-002", "AUD-003", "AUD-007"], "Timebox 100 doorway trials where practical, two-client audio surfaces, current hooks/hitpoints; document inherited bugs, no speculative fix"),
 ("T019", "P5", "Smallest proven competence and injury corrections", ["T018"], "AC-007", ["mods/HollowCountry/scripts/4_World/Infected/COMPETENCE.md", "research/experiments/EXP-AI-competence.md"], ["AI-001", "AI-002", "AI-003", "AI-008", "AI-010", "AI-011", "AI-012", "AUD-005", "AUD-006"], "Evidence-backed hooks, actual contacts and lock policy; bounded fallback; never teleport or bypass collisions; native control unregressed"),
 ("T020", "P6", "Observed-memory investigation and two variant trade-offs", ["T019"], "AC-007", ["mods/HollowCountry/scripts/4_World/Infected/INVESTIGATION.md", "research/experiments/EXP-AI-search.md"], ["AI-004", "AI-005", "AI-006", "AI-007", "AI-009", "AI-012", "AUD-001", "AUD-002", "AUD-003", "AUD-004", "AUD-006"], "Last observed clues expire; reachable room anchors and bounded retries; player can escape; slower stalker remains audible to two clients"),
 ("T021", "P7", "Native-first local audible chains with bounded propagation", ["T018", "T020"], "AC-008", ["mods/HollowCountry/scripts/4_World/Infected/ALERTS.md", "research/experiments/EXP-alert-chain.md"], ["HOR-001", "HOR-002", "HOR-003", "HOR-008", "HOR-011"], "Native hearing first; real audible provenance, spatial nearby query, TTL/hops/attenuation/dedupe/cooldown/rate/queue caps; no hidden coordinates"),
 ("T022", "P7", "Persistent horde accounting and safe activation", ["T020", "T021"], "AC-008", ["mods/HollowCountry/scripts/4_World/Infected/HORDES.md", "research/experiments/EXP-horde-lifecycle.md"], ["HOR-004", "HOR-005", "HOR-006", "HOR-007", "HOR-008", "HOR-009", "HOR-010", "HOR-011"], "Finite shared CE budget, persistent identity/epoch/member reconciliation, reachable routes, two-observer safe activation and hysteresis, no duplicate or visible spawning"),
 ("T023", "P8", "Combined modules, authority, migration and adversarial regression", ["T015", "T017", "T022"], "AC-011", ["research/experiments/EXP-integration.md"], ["NET-001", "NET-002", "NET-003", "NET-004", "NET-005", "NET-006", "NET-007", "NET-008"], "Individual and combined flags, malformed RPC, late join/crash/restart, corruption/migration/backup and throttling tests; all original test catalog covered"),
 ("T024", "P8", "Paired performance, endurance and destination capacity", ["T023", "T007"], "AC-009", ["research/experiments/EXP-performance.md", "metrics/candidate.csv"], ["HOR-008", "HOR-011"], "Repeat controlled runs at 3–6-player intended load; p95/p99/client lows/memory/net/write slopes pass calibrated budgets; record host contention and friend hardware recheck"),
 ("T025", "P8", "Signed private handoff, install, clean rollback and legal inventory", ["T023", "T024"], "AC-011", ["docs/TRANSFER_AND_ROLLBACK.md", "research/experiments/EXP-transfer.md"], ["NET-005", "NET-006", "NET-008"], "Pinned package hashes/signatures, no assets or secrets; friend OS/build verified, save backup, install/join/restart and rollback exercised; no public release"),
]


def main():
    nodes, edges = [], []
    # Documentation stays outside the strict authored-addon package allowlist.
    scope_aliases = {
        "mods/HollowCountry/scripts/4_World/Interiors/README.md": "research/experiments/EXP-interiors-implementation.md",
        "mods/HollowCountry/scripts/4_World/Interiors/SEARCH.md": "research/experiments/EXP-interiors-implementation.md",
        "mods/HollowCountry/scripts/4_World/Crafting/README.md": "research/experiments/EXP-crafting-implementation.md",
        "mods/HollowCountry/scripts/4_World/Infected/COMPETENCE.md": "research/experiments/EXP-infected-implementation.md",
        "mods/HollowCountry/scripts/4_World/Infected/INVESTIGATION.md": "research/experiments/EXP-infected-implementation.md",
        "mods/HollowCountry/scripts/4_World/Infected/ALERTS.md": "research/experiments/EXP-infected-implementation.md",
        "mods/HollowCountry/scripts/4_World/Infected/HORDES.md": "research/experiments/EXP-infected-implementation.md",
    }
    implementation_paths = {
        "T004": ["mods/HollowCountry/config.cpp", "mods/HollowCountry/scripts/3_Game/HCSettings.c", "mods/HollowCountry/scripts/4_World/Core/HCServer.c", "mods/HollowCountry/scripts/5_Mission/HCMissionServer.c"],
        "T009": ["tools/validate/runtime.py", "tests/unit/test_runtime_settings.py", "config/hollow-country-settings.json"],
        "T011": ["tools/package/economy.py", "tests/unit/test_economy_contract.py", "mission/hollow-country/cfgeconomycore.append.xml"],
        "T012": ["mission/hollow-country/ce/types.xml", "mission/hollow-country/economy-profiles/contextual-pilot.json"],
        "T014": ["mods/HollowCountry/scripts/4_World/Interiors/HCInteriorCatalog.c", "mods/HollowCountry/scripts/4_World/Interiors/HCInteriorModule.c"],
        "T015": ["mods/HollowCountry/scripts/4_World/Interiors/HCInteriorAction.c", "mods/HollowCountry/scripts/4_World/Interiors/HCInteriorStore.c"],
        "T017": ["mods/HollowCountry/scripts/4_World/Crafting/HCSalvageRecipe.c", "mods/HollowCountry/scripts/4_World/Crafting/HCRecipeRegistration.c", "mods/HollowCountry/scripts/4_World/Crafting/HCCraftingModule.c"],
        "T019": ["mods/HollowCountry/scripts/4_World/Infected/HCInfectedNative.c"],
        "T020": ["mods/HollowCountry/scripts/4_World/Infected/HCInfectedPolicy.c", "mods/HollowCountry/scripts/4_World/Infected/HCInfectedNavigation.c"],
        "T021": ["mods/HollowCountry/scripts/4_World/Infected/HCInfectedModule.c"],
        "T022": ["mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c"],
        "T023": ["docs/MODULE_STATUS.md", "docs/RUNTIME_IMPLEMENTATION_CONTRACT.md"],
        "T025": ["tools/package/pbo.py", "tools/package/sign.py", "tools/package/Build-Sign-Verify.ps1", "tests/unit/test_package.py", "mission/hollow-country/INSTALL_AND_ROLLBACK.md"],
    }
    for tid, phase, title, deps, ac, paths, tests, done in TASKS:
        paths = paths + implementation_paths.get(tid, [])
        paths = [scope_aliases.get(path, path) for path in paths]
        if tid == "T020":
            done += "; reject blanket health/damage inflation, sample variable densities below cap, verify recognizable variant appearance and location tendencies against native controls"
        nodes.append({"id": tid, "title": f"{phase}: {title}", "kind": "task", "dispatch": "agent",
                      "lineage": {"origin_task_id": tid, "depth": 0, "created_by": "author", "generation": 0},
                      "scope": {"objective": title, "context": f"Read spec.md, handoff and {phase} gate; TDD/SDD/BDD required. Do not implement against unobserved engine APIs.", "acceptance_criteria": [f"{ac}: {done}"]},
                      "contract": {"reads": ["docs/SPECIFICATION.md", "docs/TESTING_PERFORMANCE.md"],
                                   "modifies": [p for p in paths if (ROOT / p).is_file()],
                                   "creates": [p for p in paths if not (ROOT / p).is_file()], "traces": [ac] + tests,
                                   "verify_commands": ["PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v", "PYTHONDONTWRITEBYTECODE=1 python3 -m tools.validate.project"]},
                      "must_not": ["Claim offline checks prove DayZ behavior", "Bundle proprietary game assets or secrets", "Enable production features without prerequisite runtime evidence"],
                      "tags": [f"#phase:{phase}", "#method:tdd", "#method:sdd", "#method:bdd"]})
        edges.extend({"from": dep, "to": tid, "kind": "depends_on"} for dep in deps)
    graph = {"schema_kind": "banso.task_graph", "schema_version": "3.0.0", "feature": "001-survival-overhaul",
             "description": "Complete P0–P8 roadmap; not a blanket live dispatch authorization. Runtime leaves wait for evidence gates.", "nodes": nodes, "edges": edges}
    (DEST / "task-graph.json").write_text(json.dumps(graph, indent=2) + "\n")
    handoff = (ROOT / "docs/SPECIFICATION.md").read_text()
    reqs = sorted(set(re.findall(r"^\| ([A-Z]+-\d{2}) \|", handoff, re.M)))
    catalog = sorted(set(re.findall(r"^\| ([A-Z]+-\d{3}) \|", (ROOT / "docs/TESTING_PERFORMANCE.md").read_text(), re.M)))
    groups = {"GOV": (["T001", "T024", "T025"], "AC-011", ["NET-008"]),
              "DEV": (["T002", "T003", "T004", "T023"], "AC-002", [t for t in catalog if t.startswith("NET-")]),
              "LOOT": (["T010", "T011", "T012", "T015"], "AC-004", [t for t in catalog if t.startswith("CE-")]),
              "INT": (["T013", "T014", "T015"], "AC-005", [t for t in catalog if t.startswith("INT-")]),
              "CRFT": (["T016", "T017"], "AC-006", [t for t in catalog if t.startswith("CRF-")]),
              "AI": (["T018", "T019", "T020", "T021", "T022"], "AC-007", [t for t in catalog if t.startswith(("AI-", "HOR-"))]),
              "PHY": (["T013", "T018", "T019", "T020", "T022", "T023"], "AC-007", ["INT-004", "AI-010", "AI-011", "HOR-006"]),
              "AUD": (["T018", "T019", "T020", "T021"], "AC-007", [t for t in catalog if t.startswith("AUD-")])}
    rows = []
    for req in reqs:
        taskids, ac, tests = groups[req.split("-")[0]]
        if req == "AI-02":
            taskids, ac, tests = ["T021", "T022"], "AC-008", [t for t in catalog if t.startswith("HOR-")]
        rows.append({"id": req, "tasks": taskids, "criterion": ac, "tests": tests, "layer": "T4"})
    authored = {
        "FR-001": ("T001", "AC-001"), "FR-002": ("T004", "AC-002"),
        "FR-003": ("T006", "AC-003"), "FR-004": ("T011", "AC-004"),
        "FR-005": ("T014", "AC-005"), "FR-006": ("T015", "AC-005"),
        "FR-007": ("T017", "AC-006"), "FR-008": ("T019", "AC-007"),
        "FR-009": ("T022", "AC-008"), "FR-010": ("T024", "AC-009"),
        "FR-011": ("T008", "AC-010"), "FR-012": ("T025", "AC-011"),
        "FR-013": ("T020", "AC-007"),
        "NFR-001": ("T009", "AC-012"), "NFR-002": ("T023", "AC-011"),
        "NFR-003": ("T024", "AC-009"), "NFR-004": ("T023", "AC-011"),
        "NFR-005": ("T025", "AC-011"), "NFR-006": ("T008", "AC-010"),
    }
    by_id = {t[0]: t for t in TASKS}
    for rid, (tid, ac) in authored.items():
        rows.append({"id": rid, "tasks": [tid], "criterion": ac,
                     "tests": by_id[tid][6], "layer": "T4"})
    trace = {"schema_version": 1, "source": "docs/SPECIFICATION.md section 0.1",
             "requirements": rows, "test_catalog": catalog,
             "note": "Runtime obligations retained even where preparatory offline tests pass. GOV/DEV also require real deployment checks."}
    (DEST / "traceability.json").write_text(json.dumps(trace, indent=2) + "\n")
    plan = """---
status: draft
owner: d-addison
updated: 2026-11-16
---
# Plan: Hollow Country

## Architecture

Native CE owns ordinary world loot and population first. Interiors own stable
building/layout/site identities and request bounded allocations from Loot.
Crafting extends native actions and server inventory transactions. Infected adds
only proven decisions; native physics/navigation/animation/audio remain authority.
One addon at mods/HollowCountry owns shared settings, bounded module lifecycle,
and server mission hooks; see docs/RUNTIME_IMPLEMENTATION_CONTRACT.md. Offline Python audit/benchmark/evidence tools have no
runtime gameplay role. See the full handoff for data models and invariants.

## Data and transaction design gates

WorldIdentity = map/build/schema/reset epoch. BuildingInstance = class + verified
quantized transform + collision discriminator; layout ID never depends on pointer
or iteration order. Site = instance/site/schema + durable depletion + allocation
ledger. Craft = validated native inventory transaction. Stimulus = audible origin,
time, category, provenance, TTL/hop budget. Memory contains observed clues only.
Horde = ID/epoch/count/anchor/route/materialized members with global occupancy.
Exact native classes, save and RPC signatures wait for installed-script spikes.
Crash journal and inventory atomicity are unproven until actual failure injection;
disable search/crafting if safe recovery cannot be established.

## Parallel work and gates

Immediate independent leaves: T006 CE audit, T007 benchmark comparator, T008
evidence validator, plus read-only platform/source research while T001 planning
is authored. Their write sets are disjoint. T009 integrates them. P1 economy and
P5 native AI research overlap after P0 runtime proof; interiors and recipe research
can also proceed independently after P0. User authorized source/package authoring before client join. Installed-script API
inspection and offline regressions permit that work; predecessor runtime evidence
remains mandatory for acceptance and production enablement.
The graph is a complete roadmap, not a claim every leaf is executable today.

## Implementation Tasks

"""
    for tid, phase, title, deps, ac, paths, tests, done in TASKS:
        paths = paths + implementation_paths.get(tid, [])
        paths = [scope_aliases.get(path, path) for path in paths]
        if tid == "T020":
            done += "; reject blanket health/damage inflation, sample variable densities below cap, verify recognizable variant appearance and location tendencies against native controls"
        plan += f"### {tid}: {phase} — {title}\n\n- Depends: {', '.join(deps) or 'none'}.\n- Scope: {', '.join(paths)}.\n- Acceptance: {ac}; {done}.\n- Behavior tests: {', '.join(tests)}.\n- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.\n\n"
    plan += """## Risks and rollback

| Risk | Response |
|---|---|
| Missing Tools/server or Windows interop unavailable | Continue independent offline work; report exact failure; no runtime success claim |
| Native nav/audio/targeting not exposed | Timebox experiment; reproducible obstacle + ADR; no physics cheats |
| Search/crafting partial commits | Crash and two-client tests; block release until recovery is proven |
| Furnishing or hordes exceed budget | Reduce counts/detail; keep collision/audio fairness; disable feature |
| Live save schema change | Back up, migrate on copy, test restore; no silent wipe |
| Unknown friend's host | Portable manifest/runbook now, destination test later |

Gate exit requires requirement coverage, executed tests, pinned artifacts and
matched baseline/candidate data. Missing runtime prerequisites leave dependent
tasks pending. Final alpha is not accepted until P8 and destination smoke test.
"""
    (DEST / "plan.md").write_text(plan)
    print(f"Authored {len(nodes)} tasks, {len(edges)} dependencies, {len(reqs)} requirements, {len(catalog)} original tests")


if __name__ == "__main__":
    main()
