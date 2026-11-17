"""Synthetic metadata/source cohorts: no engine or crafting qualification."""
import copy
import hashlib
import importlib
import json
import unittest
from unittest.mock import patch


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def field(name, values=None, scalar=None):
    if scalar is not None:
        return dict(ConfigPath=name, ReadAs="number", ConfigTypeName="CT_INT",
                    ConfigType=0, ValueCaptured=True, Status="captured", ValueInt=scalar)
    integers = name == "repairableWithKits"
    return dict(ConfigPath=name, ReadAs="int_array" if integers else "float_array",
                ConfigTypeName="CT_ARRAY", ConfigType=3, ValueCaptured=True,
                Status="captured_unresolved", UnresolvedReasons=["array_element_kind_unverified"],
                **{"IntValues" if integers else "FloatValues": list(values or [])})


def row(name, root="CfgVehicles", fields=()):
    return dict(ConfigRoot=root, ItemClass=name, ParentClass="", ConfigAncestors=[],
                Fields=list(fields))


def censuses():
    sources = [dict(path="Synthetic.c", bytes=12, sha256="a" * 64, encoding="utf-8-sig")]
    common = dict(schema_version=1, evidence_layer="T0_source_only", valid=True,
                  inputs_complete=True, sources=sources, fallback_encoding=None,
                  manifest_sha256=digest(dict(schema_version=1, suffix=".c (case-insensitive)",
                                            fallback_encoding=None, sources=sources)))
    coverage = dict(source_census_complete=True, source_files=1, source_bytes=12)
    craft = dict(common, recipes=[], registrations=[], coverage=dict(coverage, declared_recipe_classes=0))
    actions = dict(common, classes=[], actions=[], methods=[], callbacks=[], bindings=[],
                   aliases=[], directives=[], diagnostics=[], coverage=dict(coverage, classes=0,
                   action_candidates=0, method_declarations=0, callbacks=0, emitted_bindings=0, aliases=0))
    return copy.deepcopy(craft), copy.deepcopy(actions)


def add_recipe(craft, name="Recipe", references=()):
    craft["recipes"].append(dict(
        **{"class": name}, source_status="registered", definitions=[dict(source="Synthetic.c", line=1)],
        literal_references=[dict(item=n, call="InsertIngredient", slot=0,
                                 source="Synthetic.c", line=2, conditions=["SYNTHETIC"])
                            for n in references], unresolved=[dict(code="custom_method_semantics")]))
    craft["coverage"]["declared_recipe_classes"] += 1


def add_action(actions, name="ActionSynthetic", candidate=True):
    actions["classes"].append(dict(
        **{"class": name}, definitions=[dict(source="Synthetic.c", line=1)],
        action_candidate=candidate,
        action_candidate_status="declared-path" if candidate else "UNKNOWN-unresolved-ancestry",
        ancestry=dict(observed_classes=[name], unresolved=[] if candidate else ["missing_parent"]),
        declared_method_ids=[], direct_binding_ids=[], inherited_registration_sources=[]))
    actions["coverage"]["classes"] += 1
    if candidate:
        actions["actions"].append(dict(**{"class": name}, item_binding_ids=[],
                                       constructor_binding_ids=[], runtime_status="UNKNOWN"))
        actions["coverage"]["action_candidates"] += 1


class ItemUtilityTests(unittest.TestCase):
    def setUp(self):
        self.m = importlib.import_module("tools.audit.item_utility")

    def build(self, rows=(), craft=None, actions=None):
        c, a = censuses()
        return self.m.build_audit(list(rows), craft if craft is not None else c,
                                  actions if actions is not None else a, {"fixture": "synthetic"})

    def test_decision_table_is_lossless_and_never_grants_gameplay(self):
        c, a = censuses()
        for name, status in [('RepairElectric', 'registered'), ('Legacy', 'disabled'),
                             ('Orphan', 'unregistered'), ('Conditional', 'UNKNOWN')]:
            add_recipe(c, name)
            c['recipes'][-1]['source_status'] = status
        for name in ('ActionRepairTent', 'ActionRepairWithToolFromHands', 'ActionOther'):
            add_action(a, name)
        add_action(a, 'Unresolved', False)
        add_action(a, 'OrdinaryItem', False)
        a['classes'][-1]['action_candidate_status'] = 'no-source-path'
        rows = [row('Positive', fields=[field('repairableWithKits', [7]),
                                       field('repairCosts', [25, 99])]),
                row('Empty', fields=[field('repairableWithKits')]), row('Absent')]
        result = self.build(rows, c, a)
        table = result['decision_table']
        self.assertEqual(['Unresolved'], table['unresolved_script_classes'])
        self.assertEqual({r['id'] for r in result['classes']},
                         {r['id'] for r in table['config_classes']})
        self.assertEqual(['qualify-native-maintenance', 'hold-disabled',
                          'hold-unregistered', 'UNKNOWN'],
                         [r['decision'] for r in table['recipes']])
        self.assertEqual(['qualify-native-maintenance', 'hold-test-only', 'preserve-native'],
                         [r['decision'] for r in table['actions']])
        self.assertEqual(['Unresolved'], table['unresolved_script_classes'])
        target = next(r for r in table['config_classes'] if r['id'].endswith(':Positive'))
        self.assertEqual('qualify-native-maintenance', target['repair'])
        self.assertEqual('UNKNOWN', target['material_conversion'])
        self.assertFalse(table['runtime_qualified'])
        self.assertFalse(table['production_enablement'])
        self.assertEqual([99], result['classes'][2]['repair']['surplus_costs'])

    def test_complete_cohorts_include_unresolved_and_every_root(self):
        c, a = censuses()
        for i in range(234):
            add_recipe(c, "Recipe" + str(i))
        for i in range(460):
            add_action(a, "Action" + str(i))
        add_action(a, "UnknownCandidate", False)
        rows = [row("Item" + str(i), r) for i, r in enumerate(
            ("CfgVehicles", "CfgWeapons", "CfgMagazines", "CfgAmmo", "OtherRoot"))]
        r = self.build(rows, c, a)
        self.assertEqual(r["denominators"]["classes"], 5)
        self.assertEqual(r["denominators"]["recipes"], 234)
        self.assertEqual(r["denominators"]["actions"], 460)
        self.assertEqual(r["denominators"]["script_classes"], 461)
        self.assertEqual(r["source_censuses"]["actions"], a)
        self.assertEqual(r["source_censuses"]["crafting"], c)
        self.assertFalse(r["runtime_qualified"])
        self.assertFalse(r["provenance_authenticated"])
        self.assertTrue(r["cohort_enumeration_complete"])

    def test_duplicate_kit_candidates_and_all_target_entries_are_retained(self):
        rows = [row("Kit", fields=[field("repairKitType", scalar=2)]),
                row("OtherKit", "CfgWeapons", [field("repairKitType", scalar=2)]),
                row("Target", fields=[field("repairableWithKits", [2, 2, 9, 0, -1]),
                                       field("repairCosts", [25, 30])])]
        r = self.build(rows)
        target = next(x for x in r["classes"] if x["name"] == "Target")["repair"]
        self.assertEqual(len(target["entries"]), 5)
        self.assertEqual(target["entries"][0]["kit_cohort"], "2")
        self.assertEqual(target["entries"][0]["resolution"], "ambiguous_metadata_candidates")
        self.assertEqual(target["entries"][2]["resolution"], "no_metadata_candidate")
        self.assertEqual(target["entries"][3]["resolution"], "nonpositive_observation")
        self.assertEqual(target["entries"][2]["cost_status"], "missing")
        self.assertEqual(r["kit_cohorts"]["2"], ["CfgVehicles:Kit", "CfgWeapons:OtherKit"])
        self.assertEqual(r["denominators"]["kit_target_possible_links"], 4)

    def test_unverified_array_typing_never_becomes_compatibility(self):
        r = self.build([row("Target", fields=[field("repairableWithKits", [1]),
                                               field("repairCosts", [25, 30])])])
        repair = r["classes"][0]["repair"]
        self.assertEqual(repair["array_element_typing"], "UNKNOWN")
        self.assertEqual(repair["compatibility"], "NOT_EVALUATED")
        self.assertEqual(repair["surplus_costs"], [30])
        self.assertEqual(repair["cost_alignment"], "surplus_costs")

    def test_missing_empty_nonpositive_and_unreadable_arrays_distinct(self):
        bad = field("repairableWithKits", [1]); bad["ValueCaptured"] = False
        r = self.build([row("Absent"), row("Empty", fields=[field("repairableWithKits")]),
                        row("Zero", fields=[field("repairableWithKits", [0])]),
                        row("Unknown", fields=[bad])])
        self.assertEqual({x["name"]: x["repair"]["cohort"] for x in r["classes"]},
                         dict(Absent="field_absent", Empty="empty_observation",
                              Zero="nonpositive_only", Unknown="unknown_metadata"))
        self.assertEqual(next(x for x in r["classes"] if x["name"] == "Unknown")["evidence"]["Fields"], [bad])

    def test_wrong_scalar_types_and_bool_array_entries_not_coerced(self):
        bad = field("repairKitType", scalar=True)
        wrong = field("repairKitType", scalar=2); wrong["ConfigType"] = 2
        r = self.build([row("Bad", fields=[bad]), row("Wrong", fields=[wrong]),
                        row("Target", fields=[field("repairableWithKits", [True, "2", 2.0])])])
        self.assertEqual(r["kit_cohorts"], {})
        entries = next(x for x in r["classes"] if x["name"] == "Target")["repair"]["entries"]
        self.assertEqual([x["resolution"] for x in entries], ["unknown_observation"] * 3)

    def test_every_literal_reference_and_cross_root_ambiguity_retained(self):
        c, a = censuses(); add_recipe(c, references=["Target", "Missing", "Target", "not a class"])
        r = self.build([row("Target"), row("target", "CfgAmmo")], c, a)
        refs = r["recipe_references"]
        self.assertEqual(len(refs), 4)
        self.assertEqual([x["resolution"] for x in refs], ["ambiguous_name", "unresolved_name", "ambiguous_name", "invalid_identifier"])
        self.assertEqual(r["denominators"]["recipe_config_possible_links"], 4)
        self.assertEqual(c["recipes"][0]["literal_references"][0], refs[0]["evidence"])

    def test_source_name_correspondence_does_not_establish_script_identity(self):
        c, a = censuses(); add_action(a, "Target", False)
        r = self.build([row("Target")], c, a)
        cohort = r["name_cohorts"]["target"]
        self.assertEqual(cohort["script_classes"], ["Target"])
        self.assertEqual(cohort["identity"], "UNKNOWN_CONFIG_SCRIPT_RELATIONSHIP")
        self.assertEqual(r["classes"][0]["inventory_eligibility"], "NOT_EVALUATED")

    def test_global_methods_callbacks_bindings_and_conditions_unchanged(self):
        c, a = censuses(); add_action(a)
        method = dict(id="global:1", owner_class=None, name="SetupSpawnedItem", source="Synthetic.c", line=3)
        a["methods"] = [method]; a["coverage"]["method_declarations"] = 1
        a["callbacks"] = [dict(method, category="repair")]; a["coverage"]["callbacks"] = 1
        a["bindings"] = [dict(id="binding:0", source="Synthetic.c", line=4,
                              candidate=None, action_class=None, unresolved=["dynamic_expression"],
                              conditions=["SYNTHETIC"], disabled=True)]
        a["coverage"]["emitted_bindings"] = 1
        r = self.build([], c, a)
        self.assertEqual(r["source_censuses"]["actions"], a)
        self.assertEqual(r["denominators"]["global_functions"], 1)

    def test_deterministic_fresh_payload_preserves_input(self):
        rows = [row("Z"), row("A")]; c, a = censuses()
        original = copy.deepcopy((rows, c, a))
        r = self.build(rows, c, a); again = self.build(rows, c, a)
        self.assertEqual(r, again)
        self.assertEqual((rows, c, a), original)
        r["classes"][0]["evidence"]["Fields"].append({"changed": True})
        self.assertEqual((rows, c, a), original)

    def test_duplicate_class_or_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate_class"):
            self.build([row("A"), row("a", "cfgvehicles")])
        with self.assertRaisesRegex(ValueError, "duplicate_field"):
            self.build([row("A", fields=[field("repairCosts"), field("REPAIRCOSTS")])])

    def test_partial_or_inconsistent_census_rejected(self):
        for change, code in ((lambda c: c.update(valid=False), "incomplete_source_census"), (lambda c: c.update(inputs_complete=False), "incomplete_source_census"),
                       (lambda c: c["coverage"].update(declared_recipe_classes=1), "coverage_mismatch:declared_recipe_classes")):
            with self.subTest(change=change):
                c, a = censuses(); change(c)
                with self.assertRaisesRegex(ValueError, "^"+code+"$"): self.build([], c, a)

    def test_manifest_digest_and_cross_census_sources_verified(self):
        c, a = censuses(); a["manifest_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "manifest"):
            self.build([], c, a)
        c, a = censuses(); a["sources"][0]["sha256"] = "b" * 64
        a["manifest_sha256"] = digest(dict(schema_version=1, suffix=".c (case-insensitive)",
                                          fallback_encoding=None, sources=a["sources"]))
        with self.assertRaisesRegex(ValueError, "source_manifest_mismatch"):
            self.build([], c, a)

    def test_unmanifested_reference_and_dangling_binding_rejected(self):
        c, a = censuses(); add_recipe(c, references=["A"])
        c["recipes"][0]["literal_references"][0]["source"] = "Missing.c"
        with self.assertRaisesRegex(ValueError, "unmanifested_source"):
            self.build([], c, a)
        c, a = censuses(); add_action(a); a["actions"][0]["item_binding_ids"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "dangling_binding"):
            self.build([], c, a)

    def test_invalid_json_nonfinite_cycle_and_oversized_scalar_rejected(self):
        for value, code in ((float("nan"), "nonfinite_number"), (float("inf"), "nonfinite_number"), (1 << 80, "integer_limit"), (object(), "json_value_type")):
            with self.subTest(value=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "^"+code+"$"): self.build([dict(row("A"), invalid=value)])
        cycle = []; cycle.append(cycle)
        with self.assertRaisesRegex(ValueError, "depth"):
            self.build([dict(row("A"), invalid=cycle)])

    def test_byte_node_work_output_and_count_budgets_fail_closed(self):
        for limit, value, message in (("MAX_INPUT_BYTES", 32, "input_bytes"),
                                      ("MAX_NODES", 4, "nodes"),
                                      ("MAX_WORK", 4, "work"),
                                      ("MAX_OUTPUT_BYTES", 32, "output_bytes"),
                                      ("MAX_CLASSES", 0, "class_count")):
            with self.subTest(limit=limit), patch.object(self.m, limit, value):
                with self.assertRaisesRegex(ValueError, message): self.build([row("A")])

    def test_reference_budget_counts_every_literal_not_just_resolved(self):
        c, a = censuses(); add_recipe(c, references=["Missing", "Missing"])
        with patch.object(self.m, "MAX_REFERENCES", 1):
            with self.assertRaisesRegex(ValueError, "reference_count"):
                self.build([], c, a)

    def test_candidate_links_are_factorized_with_exact_product_count(self):
        rows = [row("Kit" + str(i), fields=[field("repairKitType", scalar=1)]) for i in range(100)]
        rows += [row("Target" + str(i), fields=[field("repairableWithKits", [1] * 100)]) for i in range(50)]
        r = self.build(rows)
        self.assertEqual(r["denominators"]["kit_target_possible_links"], 500000)
        self.assertEqual(r["denominators"]["target_entries"], 5000)
        self.assertLess(r["analysis_work"], 250000)
        self.assertEqual(r["link_representation"], "complete_factorized_cohorts")

    def test_repeated_method_ids_retain_all_occurrences_and_ambiguous_links(self):
        c, a = censuses(); add_action(a)
        method = dict(id="same:method:1", owner_class="ActionSynthetic", name="Check",
                      source="Synthetic.c", line=2)
        a["methods"] = [method, copy.deepcopy(method), dict(method, line=3)]
        a["coverage"]["method_declarations"] = 3
        a["classes"][0]["declared_method_ids"] = [method["id"]]
        a["callbacks"] = [dict(method, category="repair")]; a["coverage"]["callbacks"] = 1
        r = self.build([], c, a)
        self.assertEqual(r["source_method_id_cohorts"], {method["id"]: [0, 1, 2]})
        self.assertEqual(r["denominators"]["methods"], 3)
        self.assertEqual(r["denominators"]["repeated_method_id_records"], 2)
        self.assertEqual(r["source_censuses"]["actions"]["methods"], a["methods"])

    def test_unhashable_source_anchor_fails_with_valueerror(self):
        c, a = censuses(); add_recipe(c, references=["A"])
        c["recipes"][0]["literal_references"][0]["source"] = []
        with self.assertRaisesRegex(ValueError, "unmanifested_source"):
            self.build([], c, a)

    def test_source_paths_and_supplied_count_bounds_fail_closed(self):
        for path in ("../Synthetic.c", "/Synthetic.c", "a\\Synthetic.c", "C:Synthetic.c", "a/./Synthetic.c"):
            c, a = censuses(); c["sources"][0]["path"] = path
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "source_path"):
                self.build([], c, a)
        for limit, value, code in (("MAX_SOURCES", 0, "source_count"), ("MAX_ACTIONS", 0, "actions_count"), ("MAX_METHODS", 0, "methods_count")):
            c, a = censuses(); add_action(a)
            a["methods"] = [dict(id="m", owner_class=None, source="Synthetic.c", line=1)]
            a["coverage"]["method_declarations"] = 1
            with self.subTest(limit=limit), patch.object(self.m, limit, value):
                with self.assertRaisesRegex(ValueError, "^"+code+"$"): self.build([], c, a)

    def test_scalar_field_evidence_remains_separate_from_unknown_kit_id(self):
        bad = field("repairKitType", scalar=2); bad["Status"] = "unresolved"
        r = self.build([row("Kit", fields=[bad])])
        self.assertEqual(r["kit_cohorts"], {})
        self.assertEqual(r["classes"][0]["evidence"]["Fields"], [bad])

    def test_cost_nan_rejected_and_negative_observation_never_approved(self):
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            self.build([row("A", fields=[field("repairCosts", [float("nan")])])])
        r = self.build([row("A", fields=[field("repairableWithKits", [1]), field("repairCosts", [-1])])])
        self.assertEqual(r["classes"][0]["repair"]["entries"][0]["cost_status"], "invalid_observation")

    def test_target_reference_budget_counts_all_entries_before_completion(self):
        with patch.object(self.m, "MAX_REFERENCES", 1):
            with self.assertRaisesRegex(ValueError, "target_reference_count"):
                self.build([row("A", fields=[field("repairableWithKits", [0, 0])])])

    def test_type_codes_require_actual_integer_evidence_not_bool_or_float(self):
        for code in (False, 0.0, None):
            bad = field("repairKitType", scalar=2)
            if code is None:
                del bad["ConfigType"]
            else:
                bad["ConfigType"] = code
            with self.subTest(code=code):
                self.assertEqual(self.build([row("Kit", fields=[bad])])["kit_cohorts"], {})
        bad = field("repairableWithKits", [2]); bad["ConfigType"] = 3.0
        r = self.build([row("Target", fields=[bad])])
        self.assertEqual(r["classes"][0]["repair"]["cohort"], "unknown_metadata")


    def test_repeated_callback_ids_from_complete_source_census_are_retained(self):
        from tools.audit import action_audit, crafting_audit
        content = b'class Wrapper<class T> { void OnConsume() {} };'
        with patch.object(crafting_audit, "_sources", side_effect=lambda root:
                          iter([("Synthetic.c", content)])):
            craft = crafting_audit.audit_tree("synthetic-no-filesystem")
            actions = action_audit.audit_tree("synthetic-no-filesystem")
        self.assertTrue(craft["valid"])
        self.assertTrue(actions["valid"])
        self.assertEqual(2, len(actions["callbacks"]))
        identity = actions["callbacks"][0]["id"]
        self.assertEqual(identity, actions["callbacks"][1]["id"])
        report = self.build([], craft, actions)
        self.assertEqual(actions["callbacks"], report["source_censuses"]["actions"]["callbacks"])
        self.assertEqual(2, report["denominators"]["callbacks"])
        self.assertEqual([0, 1], report["source_method_id_cohorts"][identity])

    def test_source_schema_version_requires_an_actual_integer(self):
        for side in (0, 1):
            for invalid in (True, 1.0):
                craft, actions = censuses()
                (craft, actions)[side]["schema_version"] = invalid
                with self.subTest(side=side, invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "incomplete_source_census"):
                        self.build([], craft, actions)


if __name__ == "__main__":
    unittest.main()
