"""Synthetic planning fixtures; these checks cannot establish DayZ behavior."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.validate.project import check_project


class ProjectContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path("/synthetic-hollow-country-project")
        self.graph = {"nodes": [], "edges": [
            {"from": "T001", "to": "T002", "kind": "depends_on"}]}
        for task in ("T001", "T002"):
            self.graph["nodes"].append({
                "id": task,
                "scope": {"objective": "Synthetic task", "context": "Synthetic input",
                          "acceptance_criteria": ["AC-004: Synthetic acceptance"]},
                "contract": {"reads": ["fixtures/input.json"], "modifies": [],
                             "creates": [f"fixtures/{task}.json"],
                             "traces": ["AC-004", "CE-001"],
                             "verify_commands": ["python3 -m synthetic_check"]},
                "must_not": ["Claim synthetic checks prove native behavior"],
            })
        self.trace = {"requirements": [
            {"id": key, "tasks": ["T002"], "tests": ["CE-001"],
             "criterion": "AC-004", "layer": "T4"}
            for key in ("LOOT-01",)],
            "test_catalog": ["CE-001"]}
        self.spec = "- [ ] AC-004: Synthetic acceptance.\n"
        self.plan = ("### T001: Synthetic root\n- Depends: none.\n"
                     "### T002: Synthetic dependent\n- Depends: T001.\n")
        self.catalog = "| CE-001 | Synthetic test | Synthetic outcome |\n"

    def check(self):
        files = {
            "docs/SPECIFICATION.md": "| LOOT-01 | Synthetic product requirement |\n",
            "docs/TESTING_PERFORMANCE.md": self.catalog,
            "docs/specs/001-survival-overhaul/spec.md": self.spec,
            "docs/specs/001-survival-overhaul/plan.md": self.plan,
            "docs/specs/001-survival-overhaul/task-graph.json": json.dumps(self.graph),
            "docs/specs/001-survival-overhaul/traceability.json": json.dumps(self.trace),
        }
        def read_text(path, *args, **kwargs):
            return files[str(path.relative_to(self.root))]
        with patch.object(Path, "read_text", autospec=True, side_effect=read_text):
            return check_project(self.root)["errors"]

    def test_complete_contract_is_admitted(self):
        self.assertEqual([], self.check())

    def test_dropped_requirement_is_rejected(self):
        self.trace["requirements"] = []
        self.assertTrue(any("LOOT-01" in x for x in self.check()))

    def test_dropped_test_is_rejected(self):
        self.trace["test_catalog"] = []
        self.assertTrue(any("CE-001" in x for x in self.check()))

    def test_unknown_task_or_criterion_is_rejected(self):
        original = copy.deepcopy(self.trace)
        for key in ("tasks", "criterion"):
            with self.subTest(key=key):
                self.trace = copy.deepcopy(original)
                self.trace["requirements"][0][key] = ["T999"] if key == "tasks" else "AC-999"
                self.assertTrue(self.check())

    def test_dependency_cycle_is_rejected(self):
        self.graph["edges"].append({"from": "T002", "to": "T001", "kind": "depends_on"})
        self.assertTrue(any("cycle" in x for x in self.check()))

    def test_unknown_dependency_is_rejected(self):
        self.graph["edges"][0]["from"] = "T999"
        self.assertTrue(self.check())

    def test_duplicate_requirement_and_task_are_rejected(self):
        self.trace["requirements"].append(copy.deepcopy(self.trace["requirements"][0]))
        self.graph["nodes"].append(copy.deepcopy(self.graph["nodes"][0]))
        self.assertGreaterEqual(len(self.check()), 2)

    def test_runtime_claim_cannot_be_mapped_only_to_offline_layer(self):
        self.trace["requirements"][0]["layer"] = "T0"
        self.assertTrue(any("runtime" in x for x in self.check()))

    def test_unknown_test_or_omitted_test_link_is_rejected(self):
        for tests in (["CE-999"], []):
            with self.subTest(tests=tests):
                self.trace["requirements"][0]["tests"] = tests
                self.assertTrue(self.check())

    def add_authored_requirements(self):
        for key in ("FR-001", "NFR-001"):
            self.spec += f"- {key}: Synthetic authored requirement.\n"
            row = copy.deepcopy(self.trace["requirements"][0])
            row["id"] = key
            self.trace["requirements"].append(row)

    def test_authored_requirements_accept_conservative_runtime_layer(self):
        self.add_authored_requirements()
        self.assertEqual([], self.check())

    def test_current_functional_and_quality_requirements_cannot_be_dropped(self):
        self.add_authored_requirements()
        original = copy.deepcopy(self.trace)
        for key in ("FR-001", "NFR-001"):
            with self.subTest(requirement=key):
                self.trace = copy.deepcopy(original)
                self.trace["requirements"] = [r for r in self.trace["requirements"] if r["id"] != key]
                self.assertIn(f"unmapped requirement {key}", self.check())

    def test_offline_authored_requirement_can_use_offline_layer(self):
        self.add_authored_requirements()
        for row in self.trace["requirements"][1:]:
            row["layer"] = "T0"
        self.assertEqual([], self.check())

    def test_catalog_test_needs_a_requirement_link(self):
        self.catalog += "| CE-002 | Synthetic orphan | No requirement |\n"
        self.trace["test_catalog"].append("CE-002")
        self.graph["nodes"][0]["contract"]["traces"].append("CE-002")
        self.assertIn("orphan test CE-002: no requirement link", self.check())

    def test_catalog_test_needs_a_task_owner(self):
        for node in self.graph["nodes"]:
            node["contract"]["traces"].remove("CE-001")
        self.assertIn("orphan test CE-001: no task owner", self.check())

    def test_requirement_links_must_be_owned_by_its_mapped_tasks(self):
        self.catalog += "| CE-002 | Synthetic other test | Outcome |\n"
        self.trace["test_catalog"].append("CE-002")
        self.graph["nodes"][0]["contract"]["traces"].append("CE-002")
        self.trace["requirements"][0]["tests"].append("CE-002")
        self.assertIn("LOOT-01: mapped tasks do not trace CE-002", self.check())

    def test_stripped_and_empty_task_graphs_are_rejected(self):
        for nodes in ([{"id": "T001"}, {"id": "T002"}], []):
            with self.subTest(nodes=nodes):
                self.graph["nodes"] = nodes
                self.graph["edges"] = []
                self.assertTrue(self.check())

    def test_task_scope_and_contract_fields_cannot_be_empty(self):
        original = copy.deepcopy(self.graph)
        fields = [("scope", "objective"), ("scope", "context"),
                  ("scope", "acceptance_criteria"), ("contract", "reads"),
                  ("contract", "traces"), ("contract", "verify_commands")]
        for section, key in fields:
            for value in (None, "", [], [" "]):
                with self.subTest(section=section, key=key, value=value):
                    self.graph = copy.deepcopy(original)
                    self.graph["nodes"][0][section][key] = value
                    self.assertTrue(self.check())

    def test_write_scope_and_guardrails_cannot_be_stripped(self):
        self.graph["nodes"][0]["contract"]["creates"] = []
        self.graph["nodes"][0]["must_not"] = []
        self.assertTrue(self.check())

    def test_unknown_task_trace_is_rejected(self):
        self.graph["nodes"][0]["contract"]["traces"].append("CE-999")
        self.assertTrue(any("CE-999" in e for e in self.check()))

    def test_deleted_or_reversed_dependencies_disagree_with_plan(self):
        for edges in ([], [{"from": "T002", "to": "T001", "kind": "depends_on"}]):
            with self.subTest(edges=edges):
                self.graph["edges"] = edges
                self.assertTrue(any("plan dependency mismatch" in e for e in self.check()))

    def test_verify_after_does_not_replace_required_dependency(self):
        self.graph["edges"][0]["kind"] = "verify_after"
        self.assertTrue(any("plan dependency mismatch" in e for e in self.check()))

    def test_unknown_dependency_kind_is_rejected(self):
        self.graph["edges"][0]["kind"] = "depend_on"
        self.assertTrue(any("unknown dependency kind" in e for e in self.check()))

    def test_missing_or_duplicate_plan_dependency_declaration_is_rejected(self):
        original = self.plan
        for plan in (original.replace("- Depends: T001.\n", ""),
                     original + "- Depends: T001.\n"):
            with self.subTest(plan=plan):
                self.plan = plan
                self.assertTrue(self.check())

    def test_plan_task_set_and_dependency_targets_must_match_graph(self):
        original = self.plan
        for plan in ("", original.split("### T002:")[0],
                     original + "### T003: Extra\n- Depends: none.\n",
                     original.replace("Depends: T001.", "Depends: T999.")):
            with self.subTest(plan=plan):
                self.plan = plan
                self.assertTrue(self.check())


if __name__ == "__main__":
    unittest.main()
