"""RED/GREEN contract tests for the pure whole-content review workbook."""
import copy
import importlib
import json
import unittest
from unittest.mock import patch


class ItemReviewTests(unittest.TestCase):
    def setUp(self):
        # Importing the contracted module was the initial RED for this slice.
        self.module = importlib.import_module("tools.audit.item_review")

    def row(self, name, root="CfgVehicles", *, parent=None, ancestors=None,
            fields=None, **extra):
        return {
            "ConfigRoot": root,
            "ItemClass": name,
            "ParentClass": parent,
            "ConfigAncestors": list(ancestors or []),
            "Fields": list(fields or []),
            **extra,
        }

    def field(self, path, value, type_name="CT_INT"):
        return {"ConfigPath": path, "ValueCaptured": 1, "ReadAs": "number",
                "ConfigTypeName": type_name,
                "ValueInt" if type_name == "CT_INT" else "ValueFloat": value}

    def recipe(self, name, *, status="registered", references=None,
               ancestry=None, resolved=True, unresolved=None):
        return {
            "class": name,
            "declaration_status": "declared",
            "source_status": status,
            "runtime_status": "unknown",
            "definitions": [{"source": "Synthetic.c", "line": 1,
                             "parent": "RecipeBase", "modded": False,
                             "conditions": []}],
            "ancestry": list(ancestry or [name, "RecipeBase"]),
            "recipe_ancestry_resolved": resolved,
            "registrations": [], "disabled_registrations": [],
            "unregistrations": [], "methods": [],
            "literal_references": list(references or []),
            "unresolved": list(unresolved or []), "semantics_resolved": False,
        }

    def reference(self, call, item, slot=None):
        return {"call": call, "slot": slot, "item": item,
                "source": "Synthetic.c", "line": 2,
                "method": "Init", "conditions": []}

    def census(self, recipes=None, registrations=None, valid=True):
        return {
            "schema_version": 1, "evidence_layer": "T0_source_only",
            "valid": valid, "inputs_complete": valid,
            "recipes": list(recipes or []),
            "registrations": list(registrations or []),
            "coverage": {"declared_recipe_classes": len(recipes or [])},
        }

    def review(self, rows, census=None, provenance=None):
        return self.module.build_review(rows, census or self.census(),
                                        provenance or {"source": "synthetic"})

    def by_name(self, report):
        return {row["name"]: row for row in report["classes"]}

    def test_green_full_denominators_retain_every_class_recipe_and_root_kind(self):
        rows = [
            self.row("InventoryThing", "CfgVehicles"),
            self.row("EquipmentThing", "CfgWeapons"),
            self.row("ProjectileThing", "CfgAmmo"),
            self.row("MagazineThing", "CfgMagazines"),
            self.row("OtherThing", "CfgNonItems"),
        ]
        recipes = [self.recipe("RecipeB"), self.recipe("RecipeA", status="unregistered")]
        report = self.review(rows, self.census(recipes))
        self.assertEqual(report["denominators"]["input_classes"], 5)
        self.assertEqual(report["denominators"]["output_classes"], 5)
        self.assertEqual(report["denominators"]["input_recipes"], 2)
        self.assertEqual(report["denominators"]["output_recipes"], 2)
        self.assertEqual({row["root_kind"] for row in report["classes"]},
                         {"vehicles", "weapons", "ammo", "magazines", "other"})
        self.assertEqual([row["class"] for row in report["recipes"]],
                         ["RecipeA", "RecipeB"])

    def test_duplicate_native_identity_is_rejected_not_silently_merged(self):
        rows = [self.row("Same"), self.row("same", root="cfgvehicles")]
        with self.assertRaisesRegex(ValueError, "duplicate_class_identity"):
            self.review(rows)

    def test_registered_disabled_and_unregistered_are_distinct_exact_counts(self):
        registrations = [
            {"class": "Active", "call": "RegisterRecipe", "source": "R.c",
             "line": 1, "disabled": False, "conditions": [], "unresolved": []},
            {"class": "Disabled", "call": "RegisterRecipe", "source": "R.c",
             "line": 2, "disabled": True, "conditions": [], "unresolved": []},
        ]
        recipes = [self.recipe("Active"), self.recipe("Disabled", status="disabled"),
                   self.recipe("Absent", status="unregistered")]
        report = self.review([], self.census(recipes, registrations))
        self.assertEqual(report["denominators"]["registration_records"], 2)
        self.assertEqual(report["denominators"]["active_registration_calls"], 1)
        self.assertEqual(report["denominators"]["comment_disabled_registration_calls"], 1)
        self.assertEqual(report["denominators"]["recipes_by_source_status"],
                         {"disabled": 1, "registered": 1, "unregistered": 1})

    def test_config_and_script_inheritance_are_separate_and_ambiguity_is_explicit(self):
        rows = [self.row("Base"),
                self.row("Child", parent="Missing", ancestors=["Child", "Base", "Base"])]
        recipe = self.recipe("ChildRecipe", ancestry=["ChildRecipe", "ScriptBase"],
                             resolved=False,
                             unresolved=[{"code": "unresolved_ancestry"}])
        report = self.review(rows, self.census([recipe]))
        child = self.by_name(report)["Child"]
        self.assertEqual(child["script_inheritance"], "UNKNOWN_NOT_DERIVED_FROM_CONFIG")
        self.assertEqual(child["review_status"], "review-unresolved")
        self.assertIn("unresolved_config_parent", child["config_inheritance_issues"])
        self.assertIn("duplicate_config_ancestor", child["config_inheritance_issues"])
        self.assertEqual(report["recipes"][0]["script_ancestry"],
                         ["ChildRecipe", "ScriptBase"])
        self.assertEqual(report["recipes"][0]["config_inheritance"],
                         "NOT_INFERRED_FROM_SCRIPT")

    def test_explicit_hidden_abstract_legacy_reasons_never_come_from_names(self):
        rows = [
            self.row("LooksAbstractButIsNot"),
            self.row("Hidden", fields=[self.field("scope", 0)]),
            self.row("Abstract", IsAbstract=True),
            self.row("Old", fields=[self.field("legacy", 1)]),
        ]
        classes = self.by_name(self.review(rows))
        self.assertEqual(classes["LooksAbstractButIsNot"]["review_status"], "retain")
        self.assertEqual(classes["Hidden"]["review_status"], "excluded-definition")
        self.assertEqual(classes["Abstract"]["review_status"], "excluded-definition")
        self.assertEqual(classes["Old"]["review_status"], "review-unresolved")
        self.assertEqual(classes["Old"]["review_reasons"],
                         ["explicit_legacy_definition"])

    def test_confirmed_missing_and_multi_root_references_are_preserved(self):
        rows = [self.row("Confirmed"), self.row("Twin", "CfgVehicles"),
                self.row("Twin", "CfgWeapons")]
        references = [self.reference("InsertIngredient", "Confirmed", 0),
                      self.reference("AddResult", "Missing"),
                      self.reference("AddResult", "Twin")]
        report = self.review(rows, self.census([self.recipe("Join", references=references)]))
        refs = report["recipes"][0]["references"]
        self.assertEqual([(row["item"], row["role"], row["resolution"],
                           row["candidate_count"]) for row in refs], [
            ("Confirmed", "ingredient", "confirmed", 1),
            ("Missing", "output", "unresolved", 0),
            ("Twin", "output", "ambiguous", 2),
        ])
        self.assertEqual(report["denominators"]["literal_references"], 3)
        self.assertEqual(report["denominators"]["confirmed_references"], 1)
        self.assertEqual(report["denominators"]["ambiguous_references"], 1)
        self.assertEqual(report["denominators"]["unresolved_references"], 1)

    def test_malformed_source_literal_is_preserved_without_repair_or_rejection(self):
        # Installed source census contains InsertIngredient(1,"Jambiya;") in
        # SplitLongWoodenStick.c:48. This test uses explicit synthetic evidence.
        refs = [self.reference("InsertIngredient", item, 1)
                for item in ("Jambiya;", "", "Jambiya")]
        report = self.review([self.row("Jambiya")],
                             self.census([self.recipe("SyntheticSplit", references=refs)]))
        observed = report["recipes"][0]["references"]
        self.assertEqual([(r["item"], r["resolution"], r["candidate_count"])
                          for r in observed], [("Jambiya;", "unresolved", 0),
                                              ("", "unresolved", 0),
                                              ("Jambiya", "confirmed", 1)])
        self.assertEqual(report["denominators"]["literal_references"], 3)
        self.assertEqual(report["denominators"]["unresolved_references"], 2)
        self.assertEqual(report["classes"][0]["link_counts"]["crafting_possible"], 1)
        bad = self.census([self.recipe("SyntheticBad", references=[
            self.reference("AddResult", 42)])])
        with self.assertRaisesRegex(ValueError, "invalid_item_reference"):
            self.review([], bad)

    def test_nonfinite_cyclic_and_oversize_inputs_fail_closed(self):
        cyclic = {}
        cyclic["again"] = cyclic
        bad_inputs = [
            ([self.row("Finite", fields=[{"ConfigPath": "x", "ValueCaptured": 1,
                                          "ReadAs": "number", "ConfigTypeName": "CT_FLOAT",
                                          "ValueFloat": float("nan")}])],
             self.census(), {}),
            ([], self.census(), cyclic),
        ]
        for rows, census, provenance in bad_inputs:
            with self.subTest(provenance=bool(provenance)):
                with self.assertRaises(ValueError):
                    self.module.build_review(rows, census, provenance)
        with patch.object(self.module, "MAX_ROWS", 1):
            with self.assertRaisesRegex(ValueError, "row_budget_or_shape"):
                self.review([self.row("One"), self.row("Two")])
        with patch.object(self.module, "MAX_INPUT_BYTES", 16):
            with self.assertRaisesRegex(ValueError, "input_byte_budget"):
                self.review([])

    def test_deterministic_order_provenance_copy_and_input_immutability(self):
        rows = [self.row("Zulu"), self.row("Alpha")]
        census = self.census([self.recipe("ZuluRecipe"), self.recipe("AlphaRecipe")])
        provenance = {"caller": {"label": "not-authenticated"}}
        original = copy.deepcopy((rows, census, provenance))
        first = self.module.build_review(rows, census, provenance)
        second = self.module.build_review(list(reversed(rows)),
                                          {**census, "recipes": list(reversed(census["recipes"]))},
                                          provenance)
        self.assertEqual(first, second)
        self.assertEqual((rows, census, provenance), original)
        provenance["caller"]["label"] = "changed"
        self.assertEqual(first["provenance"]["caller"]["label"], "not-authenticated")
        self.assertFalse(first["provenance_authenticated"])
        json.dumps(first, allow_nan=False)

    def test_link_cross_product_is_bounded_with_honest_partial_counts(self):
        rows = [self.row("Twin", root) for root in
                ("CfgVehicles", "CfgWeapons", "CfgAmmo")]
        references = [self.reference("AddResult", "Twin") for _ in range(3)]
        with patch.object(self.module, "MAX_LINKS", 4):
            report = self.review(rows, self.census([self.recipe("Many", references=references)]))
        self.assertEqual(report["link_enumeration"], {
            "possible": 9, "emitted": 4, "omitted": 5,
            "complete": False, "stop_reason": "link_budget",
        })
        self.assertEqual(sum(row["link_counts"]["crafting_possible"]
                             for row in report["classes"]), 9)
        self.assertEqual(sum(row["link_counts"]["crafting_emitted"]
                             for row in report["classes"]), 4)
        self.assertEqual(sum(ref["emitted_candidate_count"]
                             for ref in report["recipes"][0]["references"]), 4)
        self.assertEqual(len(report["classes"]), 3)

    def test_workbook_never_claims_feature_acceptance_or_name_based_craftability(self):
        report = self.review([self.row("ObviouslyCraftable", fields=[
            {"ConfigPath": "inventorySlot", "ValueCaptured": 1,
             "ReadAs": "text_array", "ConfigTypeName": "CT_ARRAY",
             "TextValues": ["Hands"]}])])
        self.assertFalse(report["full_coverage"])
        self.assertFalse(report["full_feature_pass"])
        self.assertEqual(report["feature_acceptance"], "NOT_EVALUATED")
        item = report["classes"][0]
        self.assertEqual(item["review_status"], "retain")
        self.assertNotIn("craftability", json.dumps(item).casefold())
        self.assertEqual(item["crafting_links"], [])

    def test_config_root_is_observation_not_inventory_eligibility(self):
        report = self.review([self.row("Land_SyntheticHouse", "cfgvehicles"),
                              self.row("SyntheticMagazine", "cfgmagazines")])
        classes = self.by_name(report)
        self.assertEqual(classes["Land_SyntheticHouse"]["root_kind"], "vehicles")
        self.assertEqual(classes["SyntheticMagazine"]["root_kind"], "magazines")
        for item in classes.values():
            self.assertEqual(item["inventory_eligibility"], "NOT_EVALUATED")

    def test_ambiguous_link_accounting_work_is_linear_before_emission_cap(self):
        # Count actual class-counter accesses, not elapsed wall time. Synthetic
        # namespaces intentionally maximize same-name ambiguity across roots.
        touches = [0]
        class CountingClass(dict):
            def __getitem__(self, key):
                if key == "link_counts":
                    touches[0] += 1
                return super().__getitem__(key)
        count, reference_count, cap = 96, 384, 3
        classes = [CountingClass(self.module._class_record(
            self.row("Shared", "SyntheticRoot" + str(index).zfill(3))))
            for index in range(count)]
        facts = [self.reference("AddResult", ("SHARED", "shared")[i % 2])
                 for i in range(reference_count)]
        facts.append(self.reference("AddResult", "Missing"))
        recipes = self.module._recipe_records(
            [self.recipe("Many", references=facts)], {"shared": classes}, True)
        with patch.object(self.module, "MAX_LINKS", cap):
            links, possible, _ = self.module._link_review(classes, recipes)
        work = touches[0]
        self.assertLessEqual(work, 2 * count + cap,
                             "candidate accounting visited the cross product")
        self.assertEqual(possible, count * reference_count)
        self.assertEqual(len(links), cap)
        self.assertTrue(all(item["link_counts"]["crafting_possible"] == reference_count
                            for item in classes))
        self.assertEqual([item["link_counts"]["crafting_emitted"] for item in classes],
                         [1] * cap + [0] * (count - cap))
        refs = recipes[0]["references"]
        self.assertEqual([ref["emitted_candidate_count"] for ref in refs],
                         [cap] + [0] * reference_count)
        self.assertEqual(refs[-1]["candidate_count"], 0)

    def test_config_edges_can_exhaust_budget_without_losing_possible_counts(self):
        rows = [self.row("Parent"), self.row("Shared", parent="Parent"),
                self.row("Shared", "CfgWeapons")]
        refs = [self.reference("AddResult", "Shared") for _ in range(3)]
        with patch.object(self.module, "MAX_LINKS", 1):
            report = self.review(rows, self.census([self.recipe("Many", references=refs)]))
        self.assertEqual(report["link_enumeration"], {
            "possible": 7, "emitted": 1, "omitted": 6,
            "complete": False, "stop_reason": "link_budget"})
        self.assertEqual(report["links"][0]["kind"], "config_inheritance")
        for item in report["classes"]:
            self.assertEqual(item["link_counts"]["crafting_emitted"], 0)
            self.assertEqual(item["link_counts"]["crafting_possible"],
                             3 if item["name"] == "Shared" else 0)
        self.assertTrue(all(ref["emitted_candidate_count"] == 0
                            for ref in report["recipes"][0]["references"]))


if __name__ == "__main__":
    unittest.main()
