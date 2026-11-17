"""Synthetic config rows only; matrix execution is not DayZ acceptance.

Actual TDD 2026-11-16:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_flashlight_matrix -v
RED: 15 missing-module errors before implementation; GREEN: 15 tests passed.
Follow-up actual RED: two failures for case-insensitive root selection and
inconsistent native field type supplying slot hints; GREEN: all 19 passed.

Separate read-only Python shape exercise on private native-035 rows processed
7389 classes, 584 possible hosts and 82 possible lights, with all 47888 candidate
pairs emitted. This did not run DayZ or validate the upstream manifest and is
not a fixture or a full-feature pass. All gameplay compatibility remains unknown.
"""
import copy
import importlib
import json
import unittest
from unittest.mock import patch


def field(path, values, mode="text_array", reasons=None):
    result = {"ConfigPath": path, "ReadAs": mode, "ExpectedReadAs": mode,
              "ConfigTypeName": "CT_ARRAY", "Status": "captured_unresolved",
              "ValueCaptured": 1, "UnresolvedReasons":
              ["array_element_kind_unverified"] if reasons is None else reasons}
    result["TextValues" if mode == "text_array" else "ValueInt"] = values
    if mode == "number":
        result.update(ConfigTypeName="CT_INT", Status="captured")
    return result


def row(name, root="CfgVehicles", ancestors=(), fields=()):
    return {"ConfigRoot": root, "ItemClass": name, "ParentClass": "",
            "ConfigAncestors": list(ancestors), "Fields": list(fields)}


class FlashlightMatrixTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("tools.audit.flashlight_matrix")
        self.provenance = {"ActualBuild": "synthetic-build", "manifest_sha256": "a" * 64}
        self.rows = [row("GunA", "CfgWeapons", fields=[field("attachments", ["Rail"])]),
                     row("GunB", "CfgWeapons", fields=[field("scope", 0, "number", [])]),
                     row("SurveyBag", ancestors=["Clothing"], fields=[field("inventorySlot", ["Back"])]),
                     row("SurveyHat", ancestors=["Clothing"], fields=[field("inventorySlot", ["Headgear"])]),
                     row("Flashlight", fields=[field("inventorySlot", ["Rail"])]),
                     row("Generator", fields=[field("EnergyManager plugType", 1, "number", [])]),
                     row("Unmapped"), row("Cartridge", "CfgMagazines"), row("Bullet", "CfgAmmo")]

    def build(self, rows=None):
        return self.mod.build_matrix(self.rows if rows is None else rows, self.provenance)

    def test_complete_class_denominator_and_all_candidate_pairs(self):
        result = self.build()
        self.assertEqual(len(result["classes"]), 9)
        self.assertEqual(result["denominators"]["input_classes"], 9)
        self.assertEqual(result["denominators"]["candidate_hosts"], 4)
        self.assertEqual(result["denominators"]["candidate_lights"], 2)
        self.assertEqual(result["denominators"]["possible_pairs"], 8)
        self.assertEqual(len(result["pairs"]), 8)
        self.assertTrue(result["pair_enumeration_complete"])
        self.assertFalse(result["full_coverage"])
        self.assertFalse(result["full_feature_pass"])

    def test_overlap_is_observed_not_native_eligibility(self):
        pair = next(p for p in self.build()["pairs"] if p["host"] == "CfgWeapons:GunA"
                    and p["light"] == "CfgVehicles:Flashlight")
        self.assertEqual(pair["observed_slot_overlap"], ["Rail"])
        self.assertEqual(pair["slot_evidence"], "UNVERIFIED")
        for key in ("native_eligibility", "improvised_eligibility", "geometry", "proxies",
                    "beam", "power", "switch", "held_worn_stored", "replication"):
            self.assertEqual(pair[key], "UNKNOWN")

    def test_no_overlap_never_becomes_incompatibility(self):
        pair = next(p for p in self.build()["pairs"] if p["host"] == "CfgWeapons:GunB")
        self.assertEqual(pair["observed_slot_overlap"], [])
        self.assertEqual(pair["native_eligibility"], "UNKNOWN")

    def test_ambiguous_and_outside_root_classes_are_retained(self):
        classes = {c["id"]: c for c in self.build()["classes"]}
        self.assertEqual(classes["CfgVehicles:Unmapped"]["status"], "UNRESOLVED")
        for identity in ("CfgAmmo:Bullet", "CfgMagazines:Cartridge"):
            self.assertEqual(classes[identity]["status"], "AUDIT_SCOPE_EXCLUDED")
            self.assertTrue(classes[identity]["reasons"])
        self.assertEqual(classes["CfgWeapons:GunB"]["scope"], 0)
        self.assertIn("gun_candidate", classes["CfgWeapons:GunB"]["roles"])

    def test_names_never_classify_unknown_equipment(self):
        data = self.build([row("SuperFlashlightHelmetBackpack")])
        self.assertEqual(data["denominators"]["candidate_hosts"], 0)
        self.assertEqual(data["denominators"]["candidate_lights"], 0)
        self.assertEqual(data["classes"][0]["status"], "UNRESOLVED")

    def test_script_and_config_ancestry_remain_distinct(self):
        data = self.build([row("NovelLamp", ancestors=["Flashlight"]),
                           row("NovelClothing", ancestors=["Clothing"])])
        lamp, clothing = {c["name"]: c for c in data["classes"]}.values()
        self.assertTrue(all(c["script_ancestry"] == "UNKNOWN" for c in (lamp, clothing)))
        self.assertEqual(data["denominators"]["candidate_lights"], 1)
        self.assertEqual(data["denominators"]["candidate_hosts"], 1)

    def test_powered_devices_are_only_possible_lights(self):
        generator = next(c for c in self.build()["classes"] if c["name"] == "Generator")
        self.assertEqual(generator["status"], "CANDIDATE_UNKNOWN")
        self.assertIn("energy_metadata_does_not_prove_light", generator["reasons"])

    def test_malformed_field_is_retained_without_using_tokens(self):
        rows = [row("Mystery", ancestors=["Clothing"],
                    fields=[field("inventorySlot", ["Back", 42])])]
        result = self.build(rows)
        cls = result["classes"][0]
        self.assertEqual(cls["inventory_slot_tokens"], [])
        self.assertIn("ambiguous_equipment_candidate", cls["roles"])
        self.assertIn("unusable_inventorySlot", cls["reasons"])
        self.assertEqual(cls["metadata"][0]["TextValues"], ["Back", 42])

    def test_uncaptured_or_inconsistent_native_type_never_supplies_slot_hints(self):
        for overrides in ({"ValueCaptured": 0}, {"ValueCaptured": "1"},
                          {"ConfigTypeName": "CT_CLASS"}):
            slot = field("inventorySlot", ["Back"])
            slot.update(overrides)
            result = self.build([row("NoAssumptions", ancestors=["Clothing"], fields=[slot])])
            cls = result["classes"][0]
            self.assertEqual(cls["inventory_slot_tokens"], [], overrides)
            self.assertNotIn("backpack_candidate", cls["roles"])

    def test_same_classname_in_distinct_config_roots_is_not_deduplicated(self):
        result = self.build([row("Twin", "CfgWeapons"), row("Twin", "CfgAmmo")])
        self.assertEqual(result["denominators"]["input_classes"], 2)
        self.assertEqual(len({c["id"] for c in result["classes"]}), 2)

    def test_case_insensitive_root_and_field_names_preserve_candidates(self):
        slot = field("INVENTORYSLOT", ["Back"])
        result = self.build([row("BackItem", root="cfgvehicles", fields=[slot]),
                             row("Gun", root="cfgweapons")])
        self.assertEqual(result["denominators"]["candidate_hosts"], 2)

    def test_nested_and_array_budgets_reject_unsafe_inputs(self):
        cyclic = {}; cyclic["self"] = cyclic
        with self.assertRaises(ValueError):
            self.mod.build_matrix([], cyclic)
        with self.assertRaises(ValueError):
            self.build([row("TooMany", fields=[field("inventorySlot", ["Back"] * 129)])])
        with patch.object(self.mod, "MAX_JSON_NODES", 2), self.assertRaises(ValueError):
            self.build()

    def test_input_order_does_not_change_matrix_or_digest(self):
        expected = self.build()
        reordered = copy.deepcopy(self.rows[::-1])
        for item in reordered:
            item["Fields"].reverse()
        self.assertEqual(self.build(reordered), expected)
        json.dumps(expected, allow_nan=False)

    def test_pure_inputs_and_outputs_do_not_share_mutable_data(self):
        before = copy.deepcopy((self.rows, self.provenance))
        result = self.build()
        self.assertEqual((self.rows, self.provenance), before)
        result["provenance"]["ActualBuild"] = "changed"
        result["classes"][0]["metadata"].append({})
        self.assertEqual((self.rows, self.provenance), before)

    def test_pair_budget_keeps_every_class_and_exact_missing_denominator(self):
        with patch.object(self.mod, "MAX_PAIRS", 3):
            result = self.build()
        self.assertEqual(len(result["classes"]), 9)
        self.assertEqual(len(result["pairs"]), 3)
        self.assertEqual(result["denominators"]["omitted_pairs"], 5)
        self.assertFalse(result["pair_enumeration_complete"])
        self.assertEqual(result["stop_reason"], "pair_budget")

    def test_large_nonpilot_family_has_complete_cross_product(self):
        rows = [row("G" + str(n), "CfgWeapons") for n in range(12)]
        rows += [row("L" + str(n), ancestors=["Flashlight"]) for n in range(9)]
        self.assertEqual(len(self.build(rows)["pairs"]), 108)

    def test_required_hand_removal_and_fresh_tape_are_requirements_not_passes(self):
        rules = self.build()["required_behavior"]
        self.assertFalse(rules["removal_tool_required"])
        self.assertTrue(rules["tape_consumed"])
        self.assertFalse(rules["tape_refunded"])
        self.assertTrue(rules["fresh_tape_each_remount"])
        self.assertEqual(rules["acceptance"], "PENDING")

    def test_rejects_duplicates_invalid_shapes_and_nonfinite_values(self):
        for rows in ([row("X"), row("x")], [row("X", fields=[field("a", []), field("A", [])])],
                     [{}], [row("X", fields=[field("scope", float("nan"), "number")])]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.build(rows)
        with self.assertRaises(ValueError):
            self.build(iter(self.rows))
        with self.assertRaises(ValueError):
            self.mod.build_matrix(self.rows, [])

    def test_resource_caps_fail_closed(self):
        for constant, bound in (("MAX_ROWS", 2), ("MAX_INPUT_BYTES", 30),
                                ("MAX_OUTPUT_BYTES", 30), ("MAX_FIELDS", 0)):
            with self.subTest(constant=constant), patch.object(self.mod, constant, bound):
                with self.assertRaises(ValueError):
                    self.build()
