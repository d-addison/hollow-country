"""Synthetic config rows only; matrix execution is not DayZ acceptance.

Actual TDD 2026-11-16:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_flashlight_matrix -v
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


def text_field(path, value):
    return {"ConfigPath": path, "ReadAs": "text", "ExpectedReadAs": "text", "ConfigTypeName": "CT_STRING",
            "Status": "captured", "ValueCaptured": 1, "UnresolvedReasons": [], "ValueText": value}


def equipment(name, root="CfgVehicles", ancestors=(), slots=None, attachments=None, scope=2,
              model="\\dz\\gear\\sample.p3d", extra=()):
    fields = [text_field("model", model)]
    if scope is not None:
        fields.append(field("scope", scope, "number", []))
    if slots is not None:
        fields.append(field("inventorySlot", list(slots)))
    if attachments is not None:
        fields.append(field("attachments", list(attachments)))
    return row(name, root, ancestors, fields + list(extra))


ENERGY = field("EnergyManager plugType", 1, "number", [])


class HostLightClassificationTests(unittest.TestCase):
    """Synthetic classification of hosts (slot / no slot / excluded) and lights.

    Class and slot names mirror the private native-035 capture shape; the fixtures are
    invented. Classification is config evidence only: no geometry or attach verdict.
    """

    def setUp(self):
        self.mod = importlib.import_module("tools.audit.flashlight_matrix")
        self.rows = [
            equipment("SlotRifle", "CfgWeapons", attachments=["Rail", "weaponFlashlight"]),
            equipment("SlotPistol", "CfgWeapons", attachments=["pistolFlashlight"]),
            equipment("SlotHelmet", ancestors=["Clothing"], slots=["Headgear"], attachments=["helmetFlashlight"]),
            equipment("PlainRifle", "CfgWeapons", attachments=["Rail"]),
            equipment("PlainBag", ancestors=["Clothing"], slots=["Back"]),
            equipment("PlainHat", ancestors=["Clothing"], slots=["Headgear"]),
            equipment("RifleBase", "CfgWeapons", attachments=["weaponFlashlight"], scope=0),
            equipment("HatBase", ancestors=["Clothing"], slots=["Headgear"], scope=2),
            equipment("NoModelBag", ancestors=["Clothing"], slots=["Back"], model=""),
            equipment("Hat_Ruined", ancestors=["Clothing"], slots=["Headgear"]),
            equipment("AKM_TESTBED", "CfgWeapons", attachments=["weaponFlashlight"]),
            equipment("HiddenHat", ancestors=["Clothing"], slots=["Headgear"], scope=1),
            equipment("UnreadableScope", "CfgWeapons", attachments=["Rail"], scope=None),
            equipment("Clothing", ancestors=[], slots=None),
            equipment("FakeRadio", ancestors=[], slots=["Back"], extra=[ENERGY]),
            equipment("UniversalLight", attachments=["BatteryD"], slots=["helmetFlashlight", "weaponFlashlight"], extra=[ENERGY]),
            equipment("TLRLight", attachments=["BatteryD"], slots=["pistolFlashlight"], extra=[ENERGY]),
            equipment("Flashlight", attachments=["BatteryD"], slots=[], extra=[ENERGY]),
            equipment("Raycaster", ancestors=["Flashlight"], attachments=["BatteryD"], slots=[], extra=[ENERGY]),
            equipment("Headtorch_Black", ancestors=["Headtorch_ColorBase"], attachments=["BatteryD"], slots=["Eyewear"], extra=[ENERGY]),
            equipment("Headtorch_ColorBase", attachments=["BatteryD"], slots=["Eyewear"], scope=0, extra=[ENERGY]),
            equipment("Torch", attachments=["Rags"], slots=["Melee"], extra=[ENERGY]),
            equipment("Chemlight_Blue", ancestors=["Chemlight_ColorBase"], slots=["Chemlight"],
                      extra=[field("EnergyManager convertEnergyToQuantity", 1, "number", [])]),
            equipment("PortableGasLamp", attachments=["GasCanister"], slots=[], extra=[ENERGY]),
            equipment("Generator", extra=[ENERGY]),
            equipment("Bullet", "CfgAmmo"),
        ]
        self.matrix = self.mod.build_matrix(self.rows, {"ActualBuild": "synthetic"})
        self.result = self.mod.classify_matrix(self.matrix)
        self.hosts = {h["name"]: h for h in self.result["hosts"]}
        self.lights = {l["name"]: l for l in self.result["lights"]}

    def test_native_light_slot_names_are_the_observed_config_slots(self):
        self.assertEqual(["helmetFlashlight", "pistolFlashlight", "weaponFlashlight"],
                         self.result["native_light_slots"])

    def test_hosts_with_a_native_light_slot_report_which_slots(self):
        self.assertEqual("slot_host", self.hosts["SlotRifle"]["group"])
        self.assertEqual(["weaponFlashlight"], self.hosts["SlotRifle"]["native_light_slots"])
        self.assertEqual(["pistolFlashlight"], self.hosts["SlotPistol"]["native_light_slots"])
        self.assertEqual("slot_host", self.hosts["SlotHelmet"]["group"])
        self.assertEqual(["helmetFlashlight"], self.hosts["SlotHelmet"]["native_light_slots"])
        self.assertEqual([], self.hosts["SlotRifle"]["exclusion_reasons"])

    def test_live_hosts_without_a_slot_are_a_distinct_group_not_excluded(self):
        for name in ("PlainRifle", "PlainBag", "PlainHat"):
            self.assertEqual("no_slot_host", self.hosts[name]["group"], name)
            self.assertEqual([], self.hosts[name]["native_light_slots"])
            self.assertEqual([], self.hosts[name]["exclusion_reasons"])
        self.assertEqual("backpack_candidate", self.hosts["PlainBag"]["role"])
        self.assertEqual("headgear_candidate", self.hosts["PlainHat"]["role"])
        self.assertEqual("gun_candidate", self.hosts["PlainRifle"]["role"])

    def test_excluded_hosts_keep_every_applicable_reason_even_when_they_carry_a_slot(self):
        expected = {"RifleBase": {"scope_below_2", "base_class_name"}, "HatBase": {"base_class_name"},
                    "NoModelBag": {"model_empty"}, "Hat_Ruined": {"ruined_variant"},
                    "AKM_TESTBED": {"test_variant"}, "HiddenHat": {"scope_below_2"},
                    "UnreadableScope": {"scope_unreadable"}, "Clothing": {"no_host_category"},
                    "FakeRadio": {"energy_device_not_a_host"}}
        for name, reasons in expected.items():
            with self.subTest(name=name):
                self.assertEqual("excluded", self.hosts[name]["group"])
                self.assertTrue(reasons <= set(self.hosts[name]["exclusion_reasons"]),
                                (reasons, self.hosts[name]["exclusion_reasons"]))
        self.assertEqual(["weaponFlashlight"], self.hosts["RifleBase"]["native_light_slots"])

    def test_every_candidate_host_is_in_exactly_one_group_with_exact_denominators(self):
        counts = self.result["denominators"]
        self.assertEqual(self.matrix["denominators"]["candidate_hosts"], counts["hosts"])
        self.assertEqual(counts["hosts"], counts["slot_host"] + counts["no_slot_host"] + counts["excluded"])
        self.assertEqual(3, counts["slot_host"])
        self.assertEqual(3, counts["no_slot_host"])
        self.assertEqual(counts["excluded"], sum(1 for h in self.result["hosts"] if h["group"] == "excluded"))
        self.assertEqual(counts["hosts"], len(self.result["hosts"]))
        self.assertEqual(2, counts["exclusion_reasons"]["base_class_name"])
        for host in self.result["hosts"]:
            self.assertEqual(host["group"] == "excluded", bool(host["exclusion_reasons"]), host["name"])

    def test_lights_are_grouped_by_native_slot_and_energy_model(self):
        self.assertEqual("mount_light", self.lights["UniversalLight"]["group"])
        self.assertEqual(["helmetFlashlight", "weaponFlashlight"], self.lights["UniversalLight"]["native_slots"])
        self.assertEqual("battery_slot", self.lights["UniversalLight"]["energy_model"])
        self.assertEqual("mount_light", self.lights["TLRLight"]["group"])
        self.assertEqual(["pistolFlashlight"], self.lights["TLRLight"]["native_slots"])
        self.assertEqual("handheld_battery_light", self.lights["Flashlight"]["group"])
        self.assertEqual([], self.lights["Flashlight"]["native_slots"])
        self.assertEqual("worn_light", self.lights["Headtorch_Black"]["group"])
        self.assertEqual("flame_or_chemical_light", self.lights["Torch"]["group"])
        self.assertEqual("rags_fuel", self.lights["Torch"]["energy_model"])
        self.assertEqual("flame_or_chemical_light", self.lights["Chemlight_Blue"]["group"])
        self.assertEqual("consumed_charge", self.lights["Chemlight_Blue"]["energy_model"])
        self.assertEqual("fuel_canister", self.lights["PortableGasLamp"]["energy_model"])
        self.assertEqual("energy_device_not_light", self.lights["Generator"]["group"])

    def test_excluded_lights_state_why(self):
        self.assertEqual("excluded", self.lights["Headtorch_ColorBase"]["group"])
        self.assertIn("scope_below_2", self.lights["Headtorch_ColorBase"]["exclusion_reasons"])
        self.assertIn("base_class_name", self.lights["Headtorch_ColorBase"]["exclusion_reasons"])
        self.assertEqual("excluded", self.lights["Raycaster"]["group"])
        self.assertIn("raycaster_tool_not_a_light", self.lights["Raycaster"]["exclusion_reasons"])
        counts = self.result["denominators"]
        self.assertEqual(self.matrix["denominators"]["candidate_lights"], counts["lights"])
        self.assertEqual(counts["lights"], sum(counts["light_groups"].values()))

    def test_probe_lights_are_the_mount_lights_plus_one_handheld_control_and_never_a_fire_light(self):
        self.assertEqual(["Flashlight", "TLRLight", "UniversalLight"], sorted(self.result["probe_lights"]))
        self.assertEqual("control", self.lights["Flashlight"]["probe_role"])
        self.assertEqual("representative", self.lights["UniversalLight"]["probe_role"])
        self.assertEqual("", self.lights["Torch"]["probe_role"])

    def test_classification_is_deterministic_and_does_not_mutate_the_matrix(self):
        import copy
        before = copy.deepcopy(self.matrix)
        again = self.mod.classify_matrix(self.matrix)
        self.assertEqual(before, self.matrix)
        self.assertEqual(self.result, again)
        self.assertEqual("flashlight_host_light_classification", self.result["kind"])
        self.assertEqual(self.matrix["source_rows_sha256"], self.result["source_rows_sha256"])
        self.assertEqual("PENDING", self.result["acceptance"])

    def test_classification_refuses_a_non_matrix_input(self):
        for bad in (None, {}, {"kind": "other"}, []):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.mod.classify_matrix(bad)


class ClassificationCliTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("tools.audit.flashlight_matrix")
        import tempfile
        from pathlib import Path
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.rows = self.dir / "rows.json"
        self.rows.write_text(json.dumps([equipment("PlainBag", ancestors=["Clothing"], slots=["Back"]),
                                         equipment("Flashlight", attachments=["BatteryD"], slots=[], extra=[ENERGY])]))

    def test_classify_cli_writes_a_new_file_and_never_overwrites(self):
        out = self.dir / "classification.json"
        self.assertEqual(0, self.mod.main(["classify", "--rows", str(self.rows), "--out", str(out)]))
        document = json.loads(out.read_text())
        self.assertEqual(1, document["denominators"]["no_slot_host"])
        self.assertEqual(1, document["denominators"]["lights"])
        self.assertEqual(1, self.mod.main(["classify", "--rows", str(self.rows), "--out", str(out)]))

    def test_classify_cli_refuses_output_inside_the_source_checkout(self):
        from pathlib import Path
        inside = Path(self.mod.__file__).resolve().parents[2] / "classification-must-not-exist.json"
        self.assertEqual(1, self.mod.main(["classify", "--rows", str(self.rows), "--out", str(inside)]))
        self.assertFalse(inside.exists())

    def test_manifest_loading_is_delegated_to_the_pinned_native_loader(self):
        out = self.dir / "from-manifest.json"
        with patch.object(self.mod, "load_manifest_rows", return_value=json.loads(self.rows.read_text())) as loader:
            self.assertEqual(0, self.mod.main(["classify", "--manifest", "m.json", "--manifest-sha256", "a" * 64,
                                               "--out", str(out)]))
        loader.assert_called_once_with("m.json", "a" * 64)
        self.assertTrue(out.is_file())

    def test_rows_and_manifest_are_mutually_exclusive_and_one_is_required(self):
        out = str(self.dir / "x.json")
        with self.assertRaises(SystemExit):
            self.mod.main(["classify", "--out", out])
        with self.assertRaises(SystemExit):
            self.mod.main(["classify", "--rows", str(self.rows), "--manifest", "m", "--manifest-sha256", "a" * 64,
                           "--out", out])
