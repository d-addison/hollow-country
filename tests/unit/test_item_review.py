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
            self.row("OtherThing", "CfgNonItems"),
        ]
        recipes = [self.recipe("RecipeB"), self.recipe("RecipeA", status="unregistered")]
        report = self.review(rows, self.census(recipes))
        self.assertEqual(report["denominators"]["input_classes"], 4)
        self.assertEqual(report["denominators"]["output_classes"], 4)
        self.assertEqual(report["denominators"]["input_recipes"], 2)
        self.assertEqual(report["denominators"]["output_recipes"], 2)
        self.assertEqual({row["root_kind"] for row in report["classes"]},
                         {"inventory", "equipment", "projectile", "other"})
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


if __name__ == "__main__":
    unittest.main()
