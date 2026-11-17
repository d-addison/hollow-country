"""Synthetic usefulness decisions, source hashes and graphs; no engine proof."""
import copy
import hashlib
import importlib
import unittest
from unittest.mock import patch

from tools.audit import action_audit, crafting_audit
from tests.unit.test_item_utility import field, row


def recipe(name="Convert", source="Material", result="Product", quantity=2,
           destroy=True, extra="", custom=""):
    return ("""
class %s extends RecipeBase {
 override void Init() {
  m_Name = "SYNTHETIC";
  InsertIngredient(0,"%s"); InsertIngredient(1,"Tool");
  m_IngredientDestroy[0] = %s; m_IngredientAddQuantity[0] = 0;
  m_IngredientDestroy[1] = false; m_IngredientAddQuantity[1] = 0;
  m_IngredientAddHealth[1] = -2; m_IngredientSetHealth[1] = -1;
  AddResult("%s"); m_ResultSetFullQuantity[0] = false;
  m_ResultSetQuantity[0] = %s; m_ResultInheritsColor[0] = -1;
  %s
 }
 override bool CanDo(ItemBase ingredients[], PlayerBase player) { return true; }
 %s
};
class Registry { void Register() { RegisterRecipe(new %s); } }
""" % (name, source, str(destroy).lower(), result, quantity, extra, custom, name)).encode()


def inputs(files=None):
    files = {"Synthetic.c": recipe()} if files is None else files
    with patch.object(crafting_audit, "_sources", side_effect=lambda root: iter(sorted(files.items()))):
        craft = crafting_audit.audit_tree("synthetic")
        actions = action_audit.audit_tree("synthetic")
    return craft, actions, files


def item(name, parent="", ancestors=(), scope=2, root="CfgVehicles"):
    result = row(name, root, [field("scope", scalar=scope)])
    result.update(ParentClass=parent, ConfigAncestors=list(ancestors))
    return result


class UtilityReviewTests(unittest.TestCase):
    def setUp(self):
        self.m = importlib.import_module("tools.audit.utility_review")
        self.rows = [item("Material"), item("Tool"), item("Product"),
                     item("Child", "Material", ["Material"]), item("Unresolved"),
                     item("Definition", scope=0)]

    def build(self, files=None, rows=None, **kwargs):
        c, a, files = inputs(files)
        return self.m.build_review(self.rows if rows is None else rows, c, a,
                                   {"synthetic": True}, files, **kwargs)

    def test_every_class_gets_all_eight_dimensions_and_a_reasoned_decision(self):
        result = self.build()
        self.assertEqual(len(self.rows), len(result["classes"]))
        self.assertEqual(set(result["dimensions"]), {
            "native_use", "repair", "craft", "material", "tool",
            "candidate", "exclusion", "unresolved"})
        for record in result["classes"]:
            self.assertEqual(set(result["dimensions"]), set(record["dispositions"]))
            for decision in record["dispositions"].values():
                self.assertTrue(decision["reason"])
                self.assertIn(decision["status"], self.m.STATUSES)
        self.assertTrue(result["decision_enumeration_complete"])
        self.assertFalse(result["gameplay_acceptance"])
        self.assertFalse(result["runtime_qualified"])

    def test_source_quantities_wear_roles_and_inheritance_are_concrete_not_guessed(self):
        result = self.build()
        family = result["recipe_families"][0]
        self.assertEqual("Convert", family["id"])
        self.assertEqual(2, family["parameters"]["m_ResultSetQuantity"][0]["value"])
        self.assertEqual(-2, family["parameters"]["m_IngredientAddHealth"][0]["value"])
        self.assertEqual("material", family["ingredient_roles"]["0"])
        self.assertEqual("tool", family["ingredient_roles"]["1"])
        cohort = result["ingredient_cohorts"]["material"]
        self.assertEqual(["CfgVehicles:Child", "CfgVehicles:Material"], cohort["config_candidates"])
        child = next(c for c in result["classes"] if c["id"] == "CfgVehicles:Child")
        self.assertIn("material", child["dispositions"]["material"]["cohorts"])
        self.assertFalse(family["adds_new_recipe"])
        self.assertEqual("preserve-native", family["decision"])

    def test_custom_do_cannot_promote_init_to_effective_yield_or_tool(self):
        result = self.build({"Synthetic.c": recipe(custom=
            "override void Do(ItemBase ingredients[], PlayerBase player, array<ItemBase> results) {}")})
        family = result["recipe_families"][0]
        self.assertIn("custom-mutation-or-method", family["holds"])
        self.assertEqual("unknown", family["ingredient_roles"]["1"])
        self.assertFalse(family["source_template_supported"])

    def test_dynamic_color_default_quantities_and_duplicate_outputs_survive(self):
        result = self.build({"Synthetic.c": recipe(quantity=-1, extra=
            'm_ResultInheritsColor[0] = 0; AddResult("Product");')})
        family = result["recipe_families"][0]
        self.assertEqual(2, len(family["outputs"]))
        self.assertIn("dynamic-output-class", family["holds"])
        self.assertEqual("config-default", family["outputs"][0]["quantity"]["kind"])
        self.assertEqual("unknown", family["outputs"][1]["quantity"]["kind"])

    def test_disabled_and_unregistered_recipes_are_retained_not_enabled(self):
        data = recipe().replace(b"RegisterRecipe(new Convert);", b"// RegisterRecipe(new Convert);\n")
        disabled = self.build({"Synthetic.c": data})["recipe_families"][0]
        self.assertEqual("retain-disabled-definition", disabled["decision"])
        absent = self.build({"Synthetic.c": data.replace(b"// RegisterRecipe(new Convert);", b"")})
        self.assertEqual("retain-unregistered-definition", absent["recipe_families"][0]["decision"])

    def test_no_matching_recipe_is_unresolved_not_useless_and_base_is_not_spawned(self):
        result = self.build()
        records = {r["id"]: r for r in result["classes"]}
        unknown = records["CfgVehicles:Unresolved"]
        self.assertEqual("hold", unknown["dispositions"]["candidate"]["status"])
        self.assertEqual("unknown", unknown["dispositions"]["native_use"]["status"])
        base = records["CfgVehicles:Definition"]
        self.assertEqual("exclude", base["dispositions"]["exclusion"]["status"])
        self.assertIn("non-public-definition", base["dispositions"]["exclusion"]["reason"])

    def test_repair_candidates_are_preserved_without_element_typing_or_compatibility(self):
        self.rows[0]["Fields"] += [field("repairableWithKits", [7, 7]),
                                   field("repairCosts", [10, 11, 12])]
        self.rows[1]["Fields"] += [field("repairKitType", scalar=7)]
        result = self.build()
        target = next(r for r in result["classes"] if r["id"] == "CfgVehicles:Material")
        self.assertEqual("candidate", target["dispositions"]["repair"]["status"])
        self.assertEqual(2, len(target["repair"]["entries"]))
        self.assertEqual([12], target["repair"]["surplus_costs"])
        self.assertEqual("NOT_EVALUATED", target["repair"]["compatibility"])

    def test_equal_names_across_roots_stay_ambiguous_not_last_wins(self):
        self.rows.append(item("Material", root="CfgWeapons"))
        result = self.build()
        cohort = result["ingredient_cohorts"]["material"]
        self.assertEqual(3, len(cohort["config_candidates"]))
        self.assertEqual(2, len(cohort["exact_candidates"]))
        self.assertEqual("ambiguous", cohort["name_resolution"])

    def test_source_files_must_match_complete_manifest_exactly(self):
        c, a, files = inputs()
        for bad in ({}, dict(files, **{"Extra.c": b""}),
                    {"Synthetic.c": files["Synthetic.c"] + b"\n"}, {"Synthetic.c": "not bytes"}):
            with self.subTest(bad=list(bad)), self.assertRaises(ValueError):
                self.m.build_review(self.rows, c, a, {}, bad)

    def test_recipe_source_facts_must_match_pinned_bytes(self):
        c, a, files = inputs()
        c["recipes"][0]["literal_references"][0]["item"] = "Product"
        with self.assertRaisesRegex(ValueError, "recipe-source-facts"):
            self.m.build_review(self.rows, c, a, {}, files)

    def test_conditional_or_repeated_parameter_writes_are_explicit_holds(self):
        for extra in ("m_ResultSetQuantity[0] = 9;",
                      "if (true) { m_IngredientDestroy[1] = true; }",
                      "m_ResultSetQuantity[0] = SOME_CONSTANT;"):
            family = self.build({"Synthetic.c": recipe(extra=extra)})["recipe_families"][0]
            with self.subTest(extra=extra):
                self.assertFalse(family["source_template_supported"])
                self.assertTrue(family["holds"])

    def test_proposals_require_exact_refs_positive_quantities_and_explicit_rationale(self):
        proposed = dict(id="Recovery", inputs=[dict(item="CfgVehicles:Product", quantity=1)],
                        outputs=[dict(item="CfgVehicles:Unresolved", quantity=1)],
                        rationale="SYNTHETIC design proposal; not qualified")
        result = self.build(proposals=[proposed])
        self.assertEqual("acyclic-declared-graph", result["proposals"][0]["cycle_status"])
        self.assertFalse(result["proposals"][0]["implementation_approved"])
        for changes in (dict(inputs=[]), dict(rationale=""), dict(id=True),
                        dict(outputs=[dict(item="Missing", quantity=1)]),
                        dict(outputs=[dict(item="CfgVehicles:Product", quantity=True)])):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.build(proposals=[dict(proposed, **changes)])

    def test_native_and_proposed_reverse_cycles_veto_new_edges(self):
        reverse = dict(id="Reverse", inputs=[dict(item="CfgVehicles:Product", quantity=1)],
                       outputs=[dict(item="CfgVehicles:Material", quantity=1)],
                       rationale="SYNTHETIC reverse conversion")
        result = self.build(proposals=[reverse])
        self.assertEqual("cycle-veto", result["proposals"][0]["cycle_status"])
        self.assertFalse(result["proposals"][0]["implementation_approved"])
        self.assertEqual("preserve-native", result["recipe_families"][0]["decision"])

    def test_two_proposals_cannot_hide_a_joint_cycle_or_depend_on_order(self):
        def proposal(identity, before, after):
            return dict(id=identity, inputs=[dict(item=before, quantity=1)],
                        outputs=[dict(item=after, quantity=1)], rationale="SYNTHETIC")
        a = proposal("A", "CfgVehicles:Unresolved", "CfgVehicles:Tool")
        b = proposal("B", "CfgVehicles:Tool", "CfgVehicles:Unresolved")
        first = self.build(proposals=[a, b])
        second = self.build(proposals=[b, a])
        self.assertEqual(first["proposals"], second["proposals"])
        self.assertTrue(all(p["cycle_status"] == "cycle-veto" for p in first["proposals"]))

    def test_full_original_denominators_not_a_pilot_and_deterministic_immutable(self):
        c, a, files = inputs()
        rows = [item("Item" + str(i)) for i in range(7389)]
        before = copy.deepcopy([rows, c, a])
        first = self.m.build_review(rows, c, a, {"synthetic": True}, files)
        second = self.m.build_review(list(reversed(rows)), c, a, {"synthetic": True}, files)
        self.assertEqual(7389, first["denominators"]["classes"])
        self.assertEqual([r["id"] for r in first["classes"]], [r["id"] for r in second["classes"]])
        self.assertEqual(before, [rows, c, a])
        self.assertEqual(first["classes"], second["classes"])

    def test_output_budget_refuses_partial_success(self):
        with patch.object(self.m, "MAX_OUTPUT_BYTES", 32), self.assertRaises(ValueError):
            self.build()


    def test_missing_or_ambiguous_output_class_cannot_be_source_ready(self):
        for rows in ([r for r in self.rows if r["ItemClass"] != "Product"],
                     self.rows + [item("Product", root="CfgWeapons")]):
            family = self.build(rows=rows)["recipe_families"][0]
            self.assertFalse(family["source_template_supported"])
            self.assertIn("unresolved-or-ambiguous-output-class", family["holds"])

    def test_unknown_recipe_fields_and_out_of_range_indices_hold(self):
        for extra in ("m_UnsupportedNativeGuess[0] = 3;", "m_ResultSetHealth[10] = -1;"):
            family = self.build({"Synthetic.c": recipe(extra=extra)})["recipe_families"][0]
            with self.subTest(extra=extra):
                self.assertFalse(family["source_template_supported"])
                self.assertIn("unsupported-recipe-parameter", family["holds"])

    def test_conditional_registration_is_held_not_called_unregistered(self):
        data = recipe().replace(b"RegisterRecipe(new Convert);",
                                b"\n#ifdef SYNTHETIC\nRegisterRecipe(new Convert);\n#endif\n")
        family = self.build({"Synthetic.c": data})["recipe_families"][0]
        self.assertEqual("hold-conditional-or-unresolved-registration", family["decision"])
        self.assertIn("conditional-or-unresolved-registration", family["holds"])

    def test_contradictory_or_untyped_native_ancestry_is_rejected(self):
        for chain, parent in ((["Child"], "Material"), (["Material", "material"], "Material"),
                              (["Product"], "Material"), ("Material", "Material")):
            rows = copy.deepcopy(self.rows)
            rows[3].update(ConfigAncestors=chain, ParentClass=parent)
            with self.subTest(chain=chain), self.assertRaises(ValueError):
                self.build(rows=rows)

    def test_proposals_cannot_target_ammo_config_definitions(self):
        rows = self.rows + [item("Projectile", root="CfgAmmo")]
        proposed = dict(id="Ammo", inputs=[dict(item="CfgVehicles:Product", quantity=1)],
                        outputs=[dict(item="CfgAmmo:Projectile", quantity=1)], rationale="SYNTHETIC")
        with self.assertRaises(ValueError):
            self.build(rows=rows, proposals=[proposed])


    def test_dynamic_or_conditional_ingredient_calls_never_look_fully_supported(self):
        for old, new in (
            (b'InsertIngredient(0,"Material");', b'InsertIngredient(0,"Material" + suffix);'),
            (b'InsertIngredient(0,"Material");',
             b'\n#ifdef SYNTHETIC\nInsertIngredient(0,"Material");\n#endif\n')):
            family = self.build({"Synthetic.c": recipe().replace(old, new)})["recipe_families"][0]
            with self.subTest(new=new):
                self.assertFalse(family["source_template_supported"])
                self.assertTrue(family["holds"])

    def test_missing_trivial_cando_needs_an_explicit_inherited_semantics_hold(self):
        data = recipe().replace(
            b'override bool CanDo(ItemBase ingredients[], PlayerBase player) { return true; }', b'')
        family = self.build({"Synthetic.c": data})["recipe_families"][0]
        self.assertFalse(family["source_template_supported"])

    def test_native_ammo_result_is_not_an_inventory_output_template(self):
        rows = [r for r in self.rows if r["ItemClass"] != "Product"] + [item("Product", root="CfgAmmo")]
        family = self.build(rows=rows)["recipe_families"][0]
        self.assertFalse(family["source_template_supported"])


    def test_recipe_catalog_and_registration_must_match_all_source_bytes(self):
        for change in ("omit", "status", "ancestry"):
            c, a, files = inputs()
            if change == "omit":
                c["recipes"] = []
                c["coverage"]["declared_recipe_classes"] = 0
            elif change == "status":
                c["recipes"][0]["source_status"] = "disabled"
            else:
                c["recipes"][0]["ancestry"] = ["Convert", "Invented", "RecipeBase"]
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "recipe-source-facts"):
                self.m.build_review(self.rows, c, a, {}, files)

    def test_fractional_result_quantity_is_not_reported_as_effective_literal(self):
        family = self.build({"Synthetic.c": recipe(quantity=2.75)})["recipe_families"][0]
        self.assertFalse(family["source_template_supported"])
        self.assertIn("fractional-output-quantity", family["holds"])
        self.assertEqual("unknown", family["outputs"][0]["quantity"]["kind"])
        self.assertEqual(2.75, family["parameters"]["m_ResultSetQuantity"][0]["value"])

    def test_parameter_types_selectors_and_condition_ranges_are_held(self):
        for extra in ('m_ResultInheritsHealth[0] = 2;',
                      'm_ResultReplacesIngredient[0] = -2;',
                      'm_ResultToInventory[0] = 2;',
                      'm_MinQuantityIngredient[0] = 8; m_MaxQuantityIngredient[0] = 2;',
                      'm_MinDamageIngredient[0] = 4; m_MaxDamageIngredient[0] = 2;'):
            family = self.build({"Synthetic.c": recipe(extra=extra)})["recipe_families"][0]
            with self.subTest(extra=extra):
                self.assertFalse(family["source_template_supported"])
                self.assertIn("invalid-recipe-parameter-value", family["holds"])
        data = recipe().replace(b'm_IngredientDestroy[0] = true', b'm_IngredientDestroy[0] = "true"')
        family = self.build({"Synthetic.c": data})["recipe_families"][0]
        self.assertFalse(family["source_template_supported"])
        self.assertEqual("unknown", family["ingredient_roles"]["0"])

    def test_result_limit_and_assignments_without_result_are_held(self):
        for extra in ('AddResult("Product");' * 10, 'm_ResultSetHealth[1] = -1;'):
            family = self.build({"Synthetic.c": recipe(extra=extra)})["recipe_families"][0]
            with self.subTest(extra=extra):
                self.assertFalse(family["source_template_supported"])
                self.assertIn("result-slot-out-of-range", family["holds"])

    def test_retained_zero_wear_tool_cannot_create_false_material_cycle(self):
        data = recipe().replace(b'm_IngredientAddHealth[1] = -2', b'm_IngredientAddHealth[1] = 0')
        proposal = dict(id="ToolRecovery", inputs=[dict(item="CfgVehicles:Product", quantity=1)],
                        outputs=[dict(item="CfgVehicles:Tool", quantity=1)], rationale="SYNTHETIC")
        result = self.build({"Synthetic.c": data}, proposals=[proposal])
        self.assertEqual("tool", result["recipe_families"][0]["ingredient_roles"]["1"])
        self.assertEqual("acyclic-declared-graph", result["proposals"][0]["cycle_status"])

    def test_projectile_input_is_not_a_supported_inventory_template(self):
        rows = [r for r in self.rows if r["ItemClass"] != "Material"] + [item("Material", root="CfgAmmo")]
        family = self.build(rows=rows)["recipe_families"][0]
        self.assertFalse(family["source_template_supported"])
        self.assertIn("non-item-input-config-root", family["holds"])


    def test_native_zero_one_boolean_writes_retain_quantities_and_roles(self):
        data = recipe().replace(b'= true', b'= 1').replace(b'= false', b'= 0')
        family = self.build({"Synthetic.c": data})["recipe_families"][0]
        self.assertTrue(family["source_template_supported"])
        self.assertEqual({"kind": "literal", "value": 2}, family["outputs"][0]["quantity"])
        self.assertEqual({"0": "material", "1": "tool"}, family["ingredient_roles"])
        self.assertEqual(0, family["parameters"]["m_ResultSetFullQuantity"][0]["value"])


if __name__ == "__main__":
    unittest.main()
