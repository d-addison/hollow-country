"""Execute the explicitly bound offline Gherkin subset; runtime protocols stay manual.

Bindings execute the corresponding behavioral test suites, including failure cases.
Every scenario name AND ordered step text must match; new/changed steps fail closed.
This intentionally supports Scenario/Given/When/Then/And, no general Gherkin engine.
Use `banso bdd validate` for full syntax validation separately.
"""
import argparse
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
BINDINGS = {
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
        ("Given authored settings with default-off features and bounded work limits",
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
    "Reject dropped requirements and cyclic tasks": (
        ("Given authored requirement mappings and task dependencies",
         "When the project contract behavior tests execute",
         "Then unmapped obligations and dependency cycles fail admission"), "test_project_contract.py"),
}


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
    args = parser.parse_args()
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
            tests = unittest.TestLoader().discover(str(ROOT / "tests/unit"), pattern=BINDINGS[name][1])
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
