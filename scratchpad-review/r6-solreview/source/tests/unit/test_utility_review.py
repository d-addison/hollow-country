"""Synthetic usefulness decisions, source hashes and graphs; no engine proof."""
import copy
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
        for bad, code in (({}, "source-files-manifest"), (dict(files, **{"Extra.c": b""}), "source-files-manifest"),
                    ({"Synthetic.c": files["Synthetic.c"] + b"\n"}, "source-bytes"), ({"Synthetic.c": "not bytes"}, "source-bytes")):
            with self.subTest(bad=list(bad)), self.assertRaisesRegex(ValueError, '^'+code+'$'):
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
        for changes, code in ((dict(inputs=[]), "proposal-arity"), (dict(rationale=""), "proposal-rationale"), (dict(id=True), "proposal-id"),
                        (dict(outputs=[dict(item="Missing", quantity=1)]), "proposal-class"),
                        (dict(outputs=[dict(item="CfgVehicles:Product", quantity=True)]), "proposal-quantity")):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, '^'+code+'$'):
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
        with patch.object(self.m, "MAX_OUTPUT_BYTES", 32), self.assertRaisesRegex(ValueError, "^output-bytes-budget$"):
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
        for chain, parent, code in ((["Child"], "Material", "config-ancestry-self"), (["Material", "material"], "Material", "config-ancestry-duplicates"),
                              (["Product"], "Material", "config-parent-ancestry"), ("Material", "Material", "config-ancestry")):
            rows = copy.deepcopy(self.rows)
            rows[3].update(ConfigAncestors=chain, ParentClass=parent)
            with self.subTest(chain=chain), self.assertRaisesRegex(ValueError, "^"+code+"$"):
                self.build(rows=rows)

    def test_proposals_cannot_target_ammo_config_definitions(self):
        rows = self.rows + [item("Projectile", root="CfgAmmo")]
        proposed = dict(id="Ammo", inputs=[dict(item="CfgVehicles:Product", quantity=1)],
                        outputs=[dict(item="CfgAmmo:Projectile", quantity=1)], rationale="SYNTHETIC")
        with self.assertRaisesRegex(ValueError, "^proposal-public-item-definition-required$"):
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


    def test_native_bool_literal_selector_writes_are_not_held(self):
        # Installed DeCraftGhillie*/DeCraftCourierBag write `m_ResultToInventory[1] = false;`
        # into an int[] selector (RecipeBase.c:59); the native compiler accepts it.
        family = self.build({"Synthetic.c": recipe(extra='m_ResultToInventory[0] = false;')})["recipe_families"][0]
        self.assertNotIn("invalid-recipe-parameter-value", family["holds"])
        self.assertTrue(family["source_template_supported"])
        family = self.build({"Synthetic.c": recipe(extra='m_ResultInheritsHealth[0] = true;')})["recipe_families"][0]
        self.assertNotIn("invalid-recipe-parameter-value", family["holds"])

    def test_native_zero_one_boolean_writes_retain_quantities_and_roles(self):
        data = recipe().replace(b'= true', b'= 1').replace(b'= false', b'= 0')
        family = self.build({"Synthetic.c": data})["recipe_families"][0]
        self.assertTrue(family["source_template_supported"])
        self.assertEqual({"kind": "literal", "value": 2}, family["outputs"][0]["quantity"])
        self.assertEqual({"0": "material", "1": "tool"}, family["ingredient_roles"])
        self.assertEqual(0, family["parameters"]["m_ResultSetFullQuantity"][0]["value"])


class WeightedCycleTests(unittest.TestCase):
    setUp = UtilityReviewTests.setUp
    build = UtilityReviewTests.build
    # Synthetic literal forward costs independently reproduce the inspected 1.30
    # bat/crate recipes. These are quantity proofs, not effective native yields.
    def proposal(self, identity, before, after, tool='Tool', wear=5):
        return dict(id=identity, inputs=[dict(item='CfgVehicles:'+n, quantity=1) for n in before],
                    outputs=[dict(item='CfgVehicles:'+n, quantity=q) for n,q in after],
                    tools=[dict(item='CfgVehicles:'+n, quantity=1, wear_hp=wear) for n in ([tool] if isinstance(tool,str) else tool)],
                    yield_policy='fixed-per-source', rationale='Explicit fixed recovery policy')

    def cohort(self):
        from tests.unit.test_crafting_families import FAMILIES
        from tests.unit.test_salvage_tools import tool_policy
        tools = tool_policy()
        proposals = [self.proposal(name, sources, outputs,
                     tool=[tools.ToolAt(seed, i) for i in range(tools.ToolCount(seed))], wear=wear)
                     for name, (sources, seed, outputs, wear, _, _) in FAMILIES.items()]
        bat = recipe('CraftBaseBallBatNailed','Nail','NailedBaseballBat',1,destroy=False).replace(
            b'm_IngredientAddQuantity[0] = 0',b'm_IngredientAddQuantity[0] = -12; m_MinQuantityIngredient[0] = 12').replace(
            b'InsertIngredient(1,"Tool")',b'InsertIngredient(1,"BaseballBat")').replace(
            b'm_IngredientDestroy[1] = false',b'm_IngredientDestroy[1] = true')
        crate = recipe('CraftWoodenCrate','WoodenPlank','WoodenCrate',1,destroy=False).replace(
            b'm_IngredientAddQuantity[0] = 0',b'm_IngredientAddQuantity[0] = -8; m_MinQuantityIngredient[0] = 8').replace(
            b'InsertIngredient(1,"Tool")',b'InsertIngredient(1,"Nail")').replace(
            b'm_IngredientAddQuantity[1] = 0',b'm_IngredientAddQuantity[1] = -16; m_MinQuantityIngredient[1] = 16')
        names = {'Tool','BaseballBat','Nail','WoodenPlank','WoodenCrate','NailedBaseballBat'}
        for p in proposals:
            names.update(x['item'].split(':')[1] for side in ('inputs','outputs','tools') for x in p[side])
        return proposals, {'Bat.c':bat,'Crate.c':crate}, [item(n) for n in sorted(names)]

    def test_all_six_exact_proposals_pass_quantity_gate(self):
        proposals, files, rows = self.cohort()
        result = self.build(files,rows,proposals=proposals)
        self.assertEqual({p['id']:p['cycle_status'] for p in result['proposals']}, {
            'HCRecoverLargeLeather':'acyclic-declared-graph',
            'HCRecoverMediumLeather':'acyclic-declared-graph',
            'HCRecoverBatWood':'acyclic-declared-graph',
            'HCRecoverNailedBat':'lossy-cycle-admissible',
            'HCRecoverBarbedBat':'acyclic-declared-graph',
            'HCRecoverRuinedCrate':'lossy-cycle-admissible'})
        self.assertTrue(all(p['quantity_gate_passed'] for p in result['proposals']))
        self.assertFalse(any(p['gameplay_acceptance'] for p in result['proposals']))

    def test_equal_or_growing_return_of_any_material_vetoes_entire_proposal(self):
        for identity, material, quantity in [('HCRecoverNailedBat','Nail',12),
                                              ('HCRecoverRuinedCrate','WoodenPlank',8),
                                              ('HCRecoverRuinedCrate','Nail',16),
                                              ('HCRecoverRuinedCrate','Nail',17)]:
            proposals, files, rows = self.cohort()
            for p in proposals:
                if p['id'] == identity:
                    for operand in p['outputs']:
                        if operand['item'] == 'CfgVehicles:'+material: operand['quantity']=quantity
            result = self.build(files,rows,proposals=proposals)
            verdict = next(p for p in result['proposals'] if p['id']==identity)
            self.assertEqual('cycle-veto',verdict['cycle_status'])
            self.assertFalse(verdict['quantity_gate_passed'])

    def test_custom_forward_mutation_and_missing_minimum_fail_closed(self):
        for mutate in (lambda raw:raw.replace(b'return true;',b'ingredients[0].AddQuantity(100); return true;'),
                       lambda raw:raw.replace(b'override bool CanDo',b'void Custom() {} override bool CanDo'),
                       lambda raw:raw.replace(b'm_MinQuantityIngredient[0] = 12',b'm_MinQuantityIngredient[0] = -1')):
            proposals,files,rows=self.cohort();files['Bat.c']=mutate(files['Bat.c'])
            result=self.build(files,rows,proposals=proposals)
            self.assertEqual('cycle-veto',next(p for p in result['proposals'] if p['id']=='HCRecoverNailedBat')['cycle_status'])

    def test_addresult_outside_init_is_not_a_declared_output(self):
        family=self.build({'Synthetic.c':recipe(custom='void Extra() { AddResult("Unresolved"); }')})['recipe_families'][0]
        self.assertEqual(1,len(family['outputs']))
        self.assertIn('custom-ingredient-or-result-semantics',family['holds'])

    def test_duplicate_and_contradictory_scope_evidence_is_rejected(self):
        rows=copy.deepcopy(self.rows);rows[0]['Fields'].append(field('SCOPE',scalar=0))
        with self.assertRaisesRegex(ValueError,'duplicate_field'): self.build(rows=rows)
        for key,value in [('ValueFloat',2.5),('ValueString','2'),('IntValues',[0])]:
            rows=copy.deepcopy(self.rows);rows[0]['Fields'][0][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'scope-contradiction'):
                self.build(rows=rows)

class NativeForwardCycleTests(unittest.TestCase):
    setUp = UtilityReviewTests.setUp
    build = UtilityReviewTests.build
    cohort = WeightedCycleTests.cohort
    proposal = WeightedCycleTests.proposal
    def test_forward_derived_quantities_and_optional_cache_use_config_object_units(self):
        import json
        from tests.unit.test_crafting_contract import FIXTURE
        from tests.unit.test_crafting_families_native import native_cache, native_fixture_sources
        records = [r for r in json.loads(FIXTURE.read_text())['derived_native_recipes']
                   if r['name'] in ('CraftBaseBallBatNailed','CraftWoodenCrate')]
        self.assertEqual(2,len(records))
        proposals, _, rows = self.cohort()
        for row_record in rows:
            if row_record['ItemClass'] in ('NailedBaseballBat','WoodenCrate'):
                row_record['Fields'] += [field('canBeSplit',scalar=0)]
        versions = [native_fixture_sources(records)]
        if native_cache().exists():
            files = {r['name']+'.c':(native_cache()/'4_World/Classes/Recipes/Recipes'/
                                    (r['name']+'.c')).read_bytes() for r in records}
            files['Registry.c'] = ('class Registry { void Register() { '+
                ' '.join('RegisterRecipe(new '+r['name']+');' for r in records)+' } }').encode()
            versions.append(files)
        for files in versions:
            with self.subTest(evidence='derived' if len(files)==2 else 'cache'):
                result = self.build(files,rows,proposals=proposals)
                self.assertTrue(all(p['quantity_gate_passed'] for p in result['proposals']),
                                [(p['id'],p['cycle_status']) for p in result['proposals']])
                # Remove config unit proof: a symbolic default must never silently be 1.
                unresolved = copy.deepcopy(rows)
                for row_record in unresolved: row_record['Fields']=row_record['Fields'][:1]
                result=self.build(files,unresolved,proposals=proposals)
                self.assertTrue(all(p['cycle_status']=='cycle-veto' for p in result['proposals']
                                   if p['id'] in ('HCRecoverNailedBat','HCRecoverRuinedCrate')))


class ReviewRoundTwoTests(unittest.TestCase):
    def test_gate_cohort_matches_authored_literals_and_family_expectations(self):
        from tests.unit.test_crafting_contract import CRAFTING, declarations
        from tests.unit.test_crafting_families import FAMILIES
        parsed = {p['class']: p for p in declarations((CRAFTING/'HCSalvageRecipe.c').read_text())}
        proposals, _, _ = WeightedCycleTests().cohort()
        self.assertEqual(set(FAMILIES), {p['id'] for p in proposals})
        for proposal in proposals:
            name = proposal['id']
            with self.subTest(family=name):
                self.assertIn(name, parsed)
                expected = FAMILIES[name]
                outputs = [(p['item'].split(':')[1], p['quantity']) for p in proposal['outputs']]
                self.assertEqual(expected[2], outputs)
                self.assertEqual(outputs, [(p['item'], p['quantity']) for p in parsed[name]['outputs']])
                self.assertEqual(expected[1], parsed[name]['tool'])
                self.assertEqual(expected[3], parsed[name]['wear'])

    def test_unknown_hc_salvage_and_drysack_edges_veto_feedback(self):
        worker = WeightedCycleTests(); worker.setUp()
        for before, after in [('CamoNet','Netting'), ('CableReel','MetalWire'),
                              ('DrysackBag_Green','WaterproofBag_Green'),
                              ('DrysackBag_Orange','Rope'), ('DrysackBag_Yellow','Rope')]:
            with self.subTest(edge=(before, after)):
                proposal = worker.proposal('Feedback', [after], [(before, 1)])
                result = worker.build({'NoRecipes.c':b'class NoRecipes {}'}, [item(before),item(after),item('Tool')], proposals=[proposal])
                self.assertEqual('cycle-veto', result['proposals'][0]['cycle_status'])
                self.assertTrue(any('split/stack' in line for line in result['limitations']))

    def test_unknown_native_split_stack_path_vetoes_lossy_feedback(self):
        worker = WeightedCycleTests(); worker.setUp()
        forward = recipe(quantity=1).replace(b'm_IngredientAddQuantity[0] = 0',
            b'm_IngredientAddQuantity[0] = -2; m_MinQuantityIngredient[0] = 2').replace(
            b'm_IngredientDestroy[0] = true', b'm_IngredientDestroy[0] = false')
        rows = [item('Material'),item('Product'),item('Tool')]
        rows[0]['Fields'].append(field('canBeSplit', scalar=1))
        proposal = worker.proposal('Feedback', ['Product'], [('Material',1)])
        result = worker.build({'Forward.c':forward}, rows, proposals=[proposal])
        self.assertEqual('cycle-veto', result['proposals'][0]['cycle_status'])


if __name__ == "__main__":
    unittest.main()
