"""Execute the explicitly bound offline Gherkin subset; runtime protocols stay manual.

Bindings execute the corresponding behavioral test suites, including failure cases.
Every scenario name AND ordered step text must match; new/changed steps fail closed.
This intentionally supports Scenario/Given/When/Then/And, no general Gherkin engine.
Use `banso bdd validate` for full syntax validation separately.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
BINDINGS = {
    "Retain every stock placement through reviewed measurement batches": (
        ("Given synthetic complete stock inventories reviewed poses and native acquisition receipts",
         "When bounded survey planning and receipt merging preserve each placement denominator",
         "Then unmeasured ambiguous replayed or failed batches cannot become fitted or eligible interiors"), "test_interior_survey.py"),
    "Default feature preferences on while preserving explicit disables": (
        ("Given the shipped operator settings and authored native defaults",
         "When feature preferences and dependency constraints are validated",
         "Then enabled defaults preserve explicit disables and do not grant native qualification"), "test_runtime_settings.py"),
    "Admit death selections only from bounded real callback observations": (
        ("Given synthetic pinned stock missions native declarations and death selection receipts",
         "When the fixed CE disabled bundle and bounded receipt checks execute",
         "Then missing callbacks changed damage inputs or unconfirmed cleanup cannot establish rendered physics"), "test_death_selection_probe.py"),
    "Preserve group state and clock watermark across bounded journal recovery": (
        ("Given synthetic native storage with current legacy and torn group journals",
         "When authored group store and startup methods recover state",
         "Then corrupt images clock rollback and unsafe migrations cannot replace committed membership"), "test_group_persistence.py"),
    "Keep group RPC changes authenticated ordered and durably committed": (
        ("Given synthetic authenticated peers sessions clocks and native group storage",
         "When authored RPC and commit methods receive retries changed payloads and failures",
         "Then replay stale sessions and failed commits cannot create an unauthorized group mutation"), "test_group_rpc.py"),
    "Respect human AI recovery policy without declaring runtime qualification": (
        ("Given synthetic provider source artifact dependency and human AI recovery declarations",
         "When the bounded optional provider audit checks closure fairness and retirement receipts",
         "Then reviewed recovery exceptions cannot bypass source pins fairness or runtime qualification"), "test_optional_provider.py"),
    "Retain complete utility cohorts without inferring repair compatibility": (
        ("Given synthetic complete item recipe and action evidence with repeated source identities",
         "When bounded utility indexing retains every admitted class reference and candidate cohort",
         "Then ambiguity unknown typing and work limits remain explicit without gameplay approval"), "test_item_utility.py"),
    "Prepare house measurements without inferring room fit or loot eligibility": (
        ("Given synthetic pinned stock maps native interfaces and real-house acquisition receipts",
         "When the fixed measurement bundle and bounded receipt validator execute",
         "Then unmatched houses incomplete callbacks and changed evidence cannot establish a qualified interior"), "test_interior_measurement_probe.py"),
    "Observe bounded owned-process counters without inferring engine liveness": (
        ("Given synthetic procfs identities counters log metadata and monotonic clocks",
         "When the bounded process observer samples explicit owned process and log inputs",
         "Then reuse missing data rollback and work limits remain explicit without readiness or deadlock claims"), "test_process_observation.py"),
    "Admit actor-free startup controls only from unchanged bounded evidence": (
        ("Given synthetic isolated native processes and nonce-bound startup receipts",
         "When the fixed startup runner checks staging publication deadlines and cleanup",
         "Then changed evidence uncertain reports and incomplete callbacks cannot pass admission"), "test_native_startup_runner.py"),
    "Bind measured interior records without inventing layout qualification": (
        ("Given synthetic measured records pinned source documents and live house collaborators",
         "When the bounded interior import and contextual binding methods execute",
         "Then ambiguous houses invalid transforms and mismatched provenance cannot enable placement"), "test_interior_measured_catalog.py"),
    "Preserve audited cutting tools through salvage registration and completion": (
        ("Given the complete audited cutting class set and synthetic native recipe collaborators",
         "When salvage registration eligibility and completion guards execute",
         "Then every supported tool retains its identity wear and material checks without native transaction claims"), "test_salvage_tools.py"),
    "Preserve taped-light identity while consuming tape on each mount": (
        ("Given synthetic qualified bindings inventory custody snapshots and journal receipts",
         "When the authored taped-light mount and hand-removal policies execute",
         "Then replay failed writes and changed identities cannot retry a move or refund consumed tape"), "test_taped_light_service.py"),
    "Retain whole-source action and item-use evidence without evaluating dispatch": (
        ("Given synthetic complete source trees with action registration calls and item callbacks",
         "When the bounded action census retains declarations controls and unresolved ancestry",
         "Then no omitted input ambiguous receiver or disabled reference becomes effective gameplay approval"), "test_action_audit.py"),
    "Activate stamina only from an opted-in trusted session configuration": (
        ("Given synthetic native configuration receipts server profiles and session callbacks",
         "When the authored stamina configuration loader and activation gates execute",
         "Then missing opt-in invalid profiles unauthenticated receipts and session resets cannot retain custom stamina"), "test_stamina_configuration.py"),
    "Schedule resource attraction only from bounded fresh native observations": (
        ("Given synthetic resource zones actor observations and explicit navigation capabilities",
         "When the authored ecology scheduling and receipt commit policies execute",
         "Then stale null oversized overflowing or replayed proposals cannot mutate assignments"), "test_ecology_rules.py"),
    "Admit fuel receipts only inside an owned bounded native run": (
        ("Given synthetic process clocks isolated missions and fuel observation receipts",
         "When the fixed fuel runner enforces launch staging deadline and cleanup ownership",
         "Then startup late receipts foreign directories and surviving processes cannot pass"), "test_fuel_probe_runner.py"),
    "Require all death cases before the native probe deadline": (
        ("Given synthetic server logs process lifetimes and five-case death receipts",
         "When the receipt-aware native compiler harness evaluates the fixed death purpose",
         "Then initialization stale nonces late completion and missing cleanup cannot qualify the run"), "test_wine_compile_probe.py"),
    "Retain whole-content item and recipe evidence within bounded review work": (
        ("Given synthetic native rows and a complete source recipe census",
         "When the bounded whole-content review joins class and recipe evidence",
         "Then every input remains counted and truncated links never become gameplay approval"), "test_item_review.py"),
    "Authorize a single diagnostic fuel transfer without replay": (
        ("Given synthetic native vehicle vessel actor and action collaborators",
         "When the authored diagnostic fuel action guards and transfer methods execute",
         "Then unauthorized cancelled or replayed attempts cannot credit fuel"), "test_siphon_fuel_action.py"),
    "Prepare fuel observations without accepting an unobserved transfer": (
        ("Given synthetic installed interfaces fresh missions and correlated fuel receipts",
         "When the fixed fuel probe preparation and result validator execute",
         "Then missing conservation callbacks cleanup or timely completion reject the observation"), "test_fuel_siphon_probe.py"),
    "Compare native stamina transport with bounded numeric tolerance": (
        ("Given synthetic native contexts and the observed finite quantization sample",
         "When the stamina transport control generator and numeric comparisons execute",
         "Then harmless rounding is accepted while mismatches and nonfinite fields fail"), "test_stamina_transport_probe.py"),
    "Display bounded native stamina and carried-weight samples": (
        ("Given synthetic cached native load and stamina samples with widget collaborators",
         "When the authored stamina HUD sampling and display methods execute",
         "Then weight and stamina remain separate and hidden or invalid samples cannot display stale data"), "test_stamina_hud.py"),
    "Track optional event progress only from admitted observations": (
        ("Given synthetic event definitions opted participants and ordered server observations",
         "When the authored bounded event director policies execute",
         "Then invalid transitions and replay cannot complete objectives or grant unimplemented rewards"), "test_event_director.py"),
    "Admit complete item export manifests without upgrading metadata to compatibility": (
        ("Given synthetic pinned item manifests and contiguous bounded configuration chunks",
         "When the strict item export consumer executes",
         "Then broken coverage and unsafe inputs fail while eligibility remains unqualified"), "test_item_compatibility_manifest.py"),
    "Prepare bounded infected death observations without claiming rendered physics": (
        ("Given synthetic native interfaces stock missions and correlated result receipts",
         "When the infected death diagnostic preparation and result checks execute",
         "Then missing cleanup incomplete cases and outer timeouts cannot qualify the observation"), "test_infected_death_probe.py"),
    "Build weather candidates without silently changing native defaults": (
        # test_atmosphere.load_tests also executes #35 v1 authored weather and
        # admission policies. Existing operator-profile step contract is retained.
        ("Given synthetic native weather XML and explicit pinned operator profiles",
         "When the bounded atmosphere candidate generator and validator execute",
         "Then unspecified native settings remain unchanged and no runtime acceptance is inferred"), "test_atmosphere.py"),
    "Retain every audited class in the flashlight candidate denominator": (
        ("Given synthetic item metadata with unresolved category and attachment hints",
         "When the bounded flashlight candidate matrix executes",
         "Then every class remains counted and geometry power and eligibility remain unqualified"), "test_flashlight_matrix.py"),
    "Read consistent bounded UTC snapshots for group expiry": (
        ("Given synthetic native date and time reads across midnight and clock rollback",
         "When the authored group UTC sampling methods execute",
         "Then invalid or inconsistent samples fail within the fixed retry bound"), "test_group_clock.py"),
    "Exercise opt-in group policy fixtures without world side effects": (
        ("Given synthetic group DTO fixtures and a fixed step budget",
         "When the authored opt-in group check runner executes through offline adapters",
         "Then every operation and rejection must pass before a completion marker is emitted"), "test_group_native_checks.py"),
    "Recover group command ordering without replaying uncertain mutations": (
        ("Given synthetic sessions delayed snapshots and caller-owned requests",
         "When the authored group client recovery and retry methods execute",
         "Then request floors cannot rewind and uncertain payloads cannot change or replay across sessions"), "test_group_client.py"),
    "Preserve group map edits and native menu dispatch": (
        ("Given synthetic map widgets group snapshots and native menu collaborators",
         "When the authored map editing and menu dispatch methods execute",
         "Then edits retain server constraints and unrelated native menus remain available"), "test_group_ui.py"),
    "Scale continuous stamina changes through the native handler": (
        ("Given synthetic native handler state and trusted bounded stamina settings",
         "When the authored stamina integration methods execute",
         "Then native event subtraction capacity clamps and permission handling remain authoritative"), "test_stamina_integration.py"),
    "Bound effective item metadata acquisition without claiming compatibility": (
        ("Given synthetic configuration types and explicit export budgets",
         "When the authored acquisition policies and fixed mission hook checks execute",
         "Then variants and partial scans remain explicit without geometry or gameplay claims"), "test_item_compatibility_audit.py"),
    "Authorize group changes and bound durable server state": (
        ("Given synthetic authenticated peers group state and store failures",
         "When the authored group rules and server orchestration execute",
         "Then unauthorized changes unsafe persistence and outsider position disclosure fail"), "test_group_server.py"),
    "Retain ambiguous recipes in a whole-source census": (
        ("Given synthetic source trees with conditional recipes and unregistered descendants",
         "When the bounded crafting census executes",
         "Then ambiguous candidates remain unresolved rather than disappearing from coverage"), "test_crafting_audit.py"),
    "Reject fuel credits that can create quantity through rounding": (
        ("Given synthetic binary32 vehicle and vessel measurements",
         "When the authored fuel quantum and receipt policies execute",
         "Then unrepresentable gains fail without claiming a native fluid transaction"), "test_fuel_transfer.py"),
    "Calculate bounded stamina and carried-load changes": (
        ("Given synthetic load exertion recovery and cooldown inputs",
         "When the authored stamina policy executes",
         "Then invalid inputs fail and native permission vetoes remain authoritative"), "test_stamina_policy.py"),
    "Plan portable criteria without manufacturing acceptance": (
        ("Given a bounded acceptance catalog and explicit capability declarations",
         "When the planning-only adapter executes",
         "Then criteria stay intact and no execution or PASS is claimed"), "test_automation.py"),
    "Preserve the original and extended ledger without local specs": (
        ("Given the portable catalog and unknown capability inventory",
         "When only those two files are exported for planning",
         "Then original criteria and fuel and flashlight constraints survive without source documents"), "test_portable_catalog.py"),
    "Admit measured room catalogs without enabling production search": (
        ("Given synthetic measured room documents and native house collaborators",
         "When bounded diagnostic catalog admission and binding execute",
         "Then invalid or ambiguous catalogs publish nothing and production search stays gated"), "test_room_catalog_completion.py"),
    "Veto observer transitions until complete trustworthy evidence exists": (
        ("Given synthetic observer samples explicit limits and retained visibility history",
         "When the authored observer veto and hysteresis policies execute",
         "Then missing stale visible or unresolved inputs cannot authorize transitions"), "test_observer_transition.py"),
    "Reject unsafe private repository content without echoing secrets": (
        ("Given synthetic Git trees private source notices and unsafe content variants",
         "When bounded repository hygiene admission executes",
         "Then restricted material and broken links fail without secret excerpts or publication rights"), "test_hygiene.py"),
    "Prepare interior candidates only from explicit measured evidence": (
        ("Given synthetic measured layouts contextual policies and source evidence pins",
         "When interior candidate preparation and validation execute",
         "Then unsafe or unproven candidates fail without runtime installation or eligibility claims"), "test_interior_catalog.py"),
    "Persist cohort intent before native ownership transfer": (
        ("Given synthetic cohort reservations journal generations and crash boundaries",
         "When the authored durable adoption policies and orchestration execute",
         "Then uncommitted or ambiguous transfers retain reservations and cannot replay"), "test_infected_persistence.py"),
    "Observe route progress and fairly schedule cohort clues": (
        ("Given synthetic observed members waypoints and competing cohort clues",
         "When the authored route progress and retarget scheduler execute",
         "Then completion requires observed arrival and stale cohorts cannot starve valid clues"), "test_infected_routes.py"),
    "Keep infected profiles and pack retargets bound to observed evidence": (
        ("Given synthetic profile assignments member observations and frozen stimuli",
         "When the authored infected profile and pack routing policies execute",
         "Then unsupported capabilities stale clues and ambiguous membership remain blocked"), "test_infected_wave.py"),
    "Unwind interrupted module lifecycle without repeating callbacks": (
        ("Given synthetic module callbacks with interrupted startup and shutdown",
         "When the authored core lifecycle methods execute",
         "Then cleanup retries preserve reverse order and do not repeat removed callbacks"), "test_core_lifecycle.py"),
    "Reject salvage admission after failed core startup": (
        ("Given synthetic core state and registered native recipe objects",
         "When the authored crafting admission and registry audits execute",
         "Then stopped cores and mismatched recipes cannot authorize salvage"), "test_crafting_completion.py"),
    "Prepare pinned CE geometry candidates without inventing eligibility": (
        ("Given synthetic stock geometry diagnostic exports and hashed observations",
         "When the coverage candidate preparation tests execute",
         "Then drift invalid points and unrelated edits fail without native eligibility claims"), "test_coverage_patch.py"),
    "Recover private installation transactions without overwriting drift": (
        ("Given verified synthetic packages and isolated installation directories",
         "When install upgrade interrupted recovery and rollback tests execute",
         "Then unrelated files and drift are preserved without live deployment claims"), "test_deploy.py"),
    "Bound supplementary infected propagation and restart recovery": (
        ("Given finite synthetic audible chain and persistent membership states",
         "When the infected completion policy and wiring tests execute",
         "Then propagation and recovery stay bounded without claiming native hearing or spawning"), "test_infected_completion.py"),
    "Preserve finite interior allocations and depleted search sites": (
        ("Given synthetic building identities allocation quotas and reservation states",
         "When the authored interior policy and source contract tests execute",
         "Then ambiguous claims cannot refill and server search admission retains every authority gate"), "test_interiors_contract.py"),
    "Conserve salvage materials through native recipe definitions": (
        ("Given three authored salvage definitions and synthetic material ledgers",
         "When the crafting policy and native source contract tests execute",
         "Then invalid ingredients and resource gain cycles fail without claiming native transactions"), "test_crafting_contract.py"),
    "Bound infected memory alerts and persistent population accounting": (
        ("Given synthetic observed clues finite horde reservations and restart states",
         "When the authored infected scalar policy tests execute",
         "Then expired clues overload and unsafe replenishment are rejected without AI claims"), "test_infected_contract.py"),
    "Preserve stock economy budgets and exact rollback": (
        ("Given synthetic stock mission files and conservative economy profiles",
         "When the economy generation install and rollback tests execute",
         "Then drift and unsupported edits are rejected without claiming effective engine merges"), "test_economy_contract.py"),
    "Package only authored content with explicit unsigned status": (
        ("Given synthetic addon sources and private handoff inputs",
         "When the deterministic package and signing command tests execute",
         "Then unsafe paths tampering and unsupported release promotion fail admission"), "test_package.py"),
    "Admit bounded operator settings before native execution": (
        ("Given authored settings with enabled feature preferences and bounded work limits",
         "When the runtime settings admission tests execute",
         "Then malformed flags limits and feature dependencies fail admission without engine claims"), "test_runtime_settings.py"),
    "Reject invalid CE data and report raw coverage": (
        ("Given synthetic mission XML with known raw points and invalid variants",
         "When the CE audit behavior tests execute",
         "Then invalid data is rejected and coverage remains an offline structural claim"), "test_ce_audit.py"),
    "Reject incomplete or incomparable benchmark evidence": (
        ("Given synthetic repeated baseline and candidate CSV measurements",
         "When the benchmark behavior tests execute",
         "Then comparison requires matching context and an explicit calibrated budget"), "test_benchmark.py"),
    "Reject unsupported capability promotions": (
        ("Given synthetic capability manifests and hashed artifact files",
         "When the evidence behavior tests execute",
         "Then missing runtime proof and tampered artifacts prevent promotion"), "test_evidence.py"),
}


# Runtime protocols (spec 002 plan.md, "Existing runtime BDD"): name -> (tags, steps, tasks).
# Names and steps stay exactly as authored; changing one fails closed. Nothing here executes
# DayZ: every scenario reports BLOCKED until its driver tasks are qualified, and the last
# scenario's task list includes tasks the owner deferred on 2026-11-22.
RUNTIME_FEATURE_TAGS = ("@manual", "@runtime", "@pending")
RUNTIME_BINDINGS = {
    "Local official server loads the signed smoke mod": (
        ("@AC-002",),
        ("Given matching installed DayZ client and dedicated server builds",
         "And a diagnostic hello-world and officially built signed PBO",
         "When a normal client joins and reconnects after server restart",
         "Then the smoke event and persistence checks have captured logs and hashes"),
        ("AV-T007", "AV-T008", "AV-T009", "AV-T015")),
    "Apartment and barracks have real eligible opportunities": (
        ("@AC-004", "@CE-003", "@CE-004"),
        ("Given verified building classnames and vanilla CE control fixtures",
         "When the minimal native economy change runs in the same controlled mission",
         "Then valid accessible placements are observed without CE errors or inflation"),
        ("AV-T012", "AV-T013")),
    "Two clients race to claim a persistent search site": (
        ("@AC-005", "@INT-007", "@NET-002"),
        ("Given a server allocated site and two eligible clients",
         "When both search concurrently and retry across a server restart",
         "Then exactly one allocation commits and the site stays depleted"),
        ("AV-T009", "AV-T010", "AV-T014", "AV-T017", "AV-T018")),
    "Interrupted salvage does not create free materials": (
        ("@AC-006", "@CRF-004", "@CRF-005"),
        ("Given a verified native recipe and server owned inputs",
         "When clients race or disconnect and the inventory is full",
         "Then outputs and consumed inputs recover as a single valid transaction"),
        ("AV-T010", "AV-T014", "AV-T015", "AV-T017")),
    "A player can escape an audible searcher": (
        ("@AC-007", "@AI-004", "@AI-006", "@AUD-004"),
        ("Given two observing clients and a native navigation and audio control",
         "When the player breaks sight quietly and changes location",
         "Then the searcher follows observed clues and expires its memory",
         "And locomotion stays physically audible without hidden live tracking"),
        ("AV-T016", "AV-T017", "AV-T019", "AV-T020")),
    "Hordes and local chains coexist without visible materialization": (
        ("@AC-008", "@HOR-002", "@HOR-006", "@HOR-009", "@HOR-010"),
        ("Given a persistent horde and finite shared infected and alert budgets",
         "When a real audible chain attracts the group across two observers and restart",
         "Then population and identity reconcile without doubling or visible pop-in"),
        ("AV-T009", "AV-T010", "AV-T011", "AV-T013", "AV-T016", "AV-T017", "AV-T018",
         "AV-T019", "AV-T020")),
    "The private transfer is reversible at the intended co-op load": (
        ("@AC-009", "@AC-011"),
        ("Given calibrated repeated representative benchmarks and a signed package",
         "When an operator installs on a matching server and restores a save backup",
         "Then module combinations and rollback preserve state within approved budgets"),
        ("AV-T021", "AV-T022", "AV-T024", "AV-T025", "AV-T026")),
}


def parse_feature_tags(text):
    """Return (feature_tags, {scenario name: tags}) from the supported subset."""
    feature_tags, pending, result, seen_feature = (), [], {}, False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("@"):
            pending.extend(line.split())
        elif line.startswith("Feature:"):
            feature_tags, pending, seen_feature = tuple(pending), [], True
        elif line.startswith("Scenario:"):
            result[line.removeprefix("Scenario:").strip()] = tuple(pending)
            pending = []
        elif line and not line.startswith("#") and seen_feature:
            pending = []
    return feature_tags, result


def runtime_report(text):
    """Check the runtime feature against RUNTIME_BINDINGS; every scenario stays BLOCKED.

    Raises ValueError on any drift in names, order, steps or tags so a changed protocol can
    never be silently treated as bound. A pending/manual scenario is never PASS.
    """
    scenarios = parse_scenarios(text)
    feature_tags, tags = parse_feature_tags(text)
    if feature_tags != RUNTIME_FEATURE_TAGS:
        raise ValueError("Runtime feature tags changed")
    names = [name for name, _ in scenarios]
    if names != list(RUNTIME_BINDINGS):
        raise ValueError("Runtime scenario names or order changed: " + "; ".join(
            sorted(set(names) ^ set(RUNTIME_BINDINGS))))
    rows = []
    for name, steps in scenarios:
        expected_tags, expected_steps, tasks = RUNTIME_BINDINGS[name]
        if steps != expected_steps:
            raise ValueError(f"Runtime scenario steps changed: {name}")
        if tags.get(name) != expected_tags:
            raise ValueError(f"Runtime scenario tags changed: {name}")
        rows.append({"scenario": name, "tags": list(expected_tags), "tasks": list(tasks),
                     "outcome": "BLOCKED", "reason": "manual_runtime_protocol_pending"})
    return {"feature_tags": list(feature_tags), "scenarios": rows}


def parse_scenarios(text):
    """Parse only the supported subset, rejecting anything that could hide steps."""
    scenarios, name, steps, feature = [], None, [], False
    unsupported = re.compile(r"^(?:Background\s*:|Rule\s*:|Scenario (?:Outline|Template)\s*:|Examples\s*:|But\b|\*|\||\"\"\"|'\x27\x27)")
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if unsupported.match(line):
            raise ValueError(f"Unsupported BDD syntax at line {number}: {line}")
        if line.startswith("@"):
            if not re.fullmatch(r"@[\w.:-]+(?:\s+@[\w.:-]+)*", line):
                raise ValueError(f"Invalid tags at line {number}")
        elif line.startswith("Feature:"):
            if feature or name is not None or not line.removeprefix("Feature:").strip():
                raise ValueError(f"Invalid feature at line {number}")
            feature = True
        elif line.startswith("Scenario:"):
            if name is not None:
                scenarios.append((name, tuple(steps)))
            name, steps = line.removeprefix("Scenario:").strip(), []
        elif line.startswith(("Given ", "When ", "Then ", "And ")):
            if name is None:
                raise ValueError(f"Step outside scenario at line {number}")
            steps.append(line)
        elif feature and name is None:
            # Feature descriptions are prose. Structural keywords and steps
            # were checked above, so prerequisites cannot disappear here.
            continue
        else:
            raise ValueError(f"Unsupported BDD syntax at line {number}: {line}")
    if name is not None:
        scenarios.append((name, tuple(steps)))
    if not scenarios:
        raise ValueError("No executable scenarios")
    if len({name for name, _ in scenarios}) != len(scenarios):
        raise ValueError("Duplicate scenario name")
    for name, steps in scenarios:
        if not name or not all(any(s.startswith(k + " ") for s in steps)
                               for k in ("Given", "When", "Then")):
            raise ValueError(f"Incomplete scenario: {name}")
    return scenarios


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature", type=Path, nargs="?", default=ROOT / "tests/features/offline.feature")
    parser.add_argument("--runtime", action="store_true",
                        help="check the runtime protocol bindings and print JSON; scenarios stay BLOCKED")
    args = parser.parse_args()
    if args.runtime:
        path = ROOT / "tests/features/runtime.feature" if args.feature.name == "offline.feature" else args.feature
        try:
            report = runtime_report(path.read_text())
        except (ValueError, OSError) as exc:
            print(json.dumps({"intact": False, "error": str(exc)}, sort_keys=True))
            return 1
        print(json.dumps(dict(report, intact=True), sort_keys=True))
        return 0
    try:
        scenarios = parse_scenarios(args.feature.read_text())
        for name, steps in scenarios:
            if name not in BINDINGS or steps != BINDINGS[name][0]:
                raise ValueError(f"Unbound scenario or changed step: {name}")
        missing = set(BINDINGS) - {name for name, _ in scenarios}
        if missing:
            raise ValueError("Missing required scenarios: " + "; ".join(sorted(missing)))
        suite = unittest.TestSuite()
        for name, _ in scenarios:
            # Bindings live in whichever test tier (fast, slow, legacy) now holds them.
            tests = unittest.TestSuite()
            for tier in ("unit", "slow", "legacy"):
                found = unittest.TestLoader().discover(str(ROOT / "tests" / tier), pattern=BINDINGS[name][1])
                if found.countTestCases():
                    tests = found
                    break
            if tests.countTestCases() == 0:
                raise ValueError(f"No behavior tests for {name}")
            suite.addTests(tests)
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        print(f"Bound offline scenarios: {len(scenarios)}; runtime acceptance: NOT EXECUTED")
        return 0 if result.wasSuccessful() else 1
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
