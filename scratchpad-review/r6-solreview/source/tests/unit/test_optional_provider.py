"""Synthetic declarations only: no provider installation or native acceptance."""
import copy
import importlib
import json
import unittest

PIN = "d84d3c73694969eba2f969e9178a1914e2f1b31d"
NATIVE = "09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a"
GRAPH = {
    "DayZExpansion_AI_Scripts": ["DZ_Characters", "DayZExpansion_Core_Scripts"],
    "DayZExpansion_AI_Animations": ["DZ_Anims_Anm_Player", "DZ_Anims_Cfg", "DZ_Characters"],
    "DayZExpansion_Sounds_AI": ["DZ_Sounds_Effects"],
    "DayZExpansion_Core_Scripts": ["DayZExpansion_ModStorage_Scripts", "DF_Scripts"],
    "DayZExpansion_ModStorage_Scripts": ["JM_CF_Scripts"],
    "JM_CF_Scripts": ["DZ_Data"], "DF_Scripts": ["DZ_Scripts", "DF_GUI"],
    "DF_GUI": [], "DZ_Data": [], "DZ_Scripts": [], "DZ_Characters": [],
    "DZ_Anims_Anm_Player": [], "DZ_Anims_Cfg": [], "DZ_Sounds_Effects": [],
}
PACKAGES = [
    ("2792982069", PIN, ["DayZExpansion_AI_Scripts", "DayZExpansion_AI_Animations",
                         "DayZExpansion_Sounds_AI"]),
    ("2291785308", PIN, ["DayZExpansion_Core_Scripts", "DayZExpansion_ModStorage_Scripts"]),
    ("1559212036", "0763e7e7548c9a0bed6626afff835de80693ebf3", ["JM_CF_Scripts"]),
    ("2545327648", "245190266b4e72bb0519fbfdd68bbed71c1edc1f", ["DF_Scripts", "DF_GUI"]),
]


def fixture():
    # Repeated hex characters are explicit synthetic hashes, never observed files.
    items = [dict(workshop_id=wid, source_commit=commit, inventory_sha256="a"*64,
                  addons=[dict(name=n, pbo_sha256="b"*64, signature_sha256="c"*64)
                          for n in names]) for wid, commit, names in PACKAGES]
    return dict(
        schema_version=1, provider="expansion-ai", experimental_opt_in=True,
        source=dict(repository="salutesh/DayZ-Expansion-Scripts", commit=PIN,
                    version="1.9.84", snapshot_sha256="d"*64),
        build=dict(version="1.30.164289", scripts_sha256=NATIVE, executable_sha256="e"*64),
        world=dict(name="chernarusplus", definition_sha256="f"*64, session="synthetic-session"),
        artifacts=dict(status="pinned", items=items),
        addons=[dict(name=n, requires=deps[:]) for n, deps in GRAPH.items()],
        policy=dict(
            provisional_diagnostic_bounds=True, allow_builtin_stuck_recovery=False,
            limits=dict(max_actors=4, max_groups=2, max_items=16, max_tick_work=4,
                        observer_max_age_ms=1000, hysteresis_ms=2000, proximity_bound_m=500),
            effective_state_sha256="1"*64, global_reload_mask=0, global_reload_all=False,
            global_flanking_outside_combat=False,
            actors=[dict(id="actor-1", group_id="group-1", inventory_items=4, reload_mask=0, flanking_outside_combat=False,
                         invincible=False, damage_multiplier=1, damage_received_multiplier=1,
                         headshot_resistance=0, ammunition_units=30, loadout_sha256="2"*64)]),
        retirements=[dict(
            receipt_id="receipt-1", actor_id="actor-1", session="synthetic-session",
            world_sha256="f"*64, source_commit=PIN, artifact_sha256="b"*64,
            build_sha256="e"*64, native_scripts_sha256=NATIVE, effective_state_sha256="1"*64,
            observed_ms=10000, now_ms=10500, clear_since_ms=8000,
            coverage_known=True, spectators_known=True, optics_known=True,
            visibility_current=False, visibility_recent=False,
            native_combat_known=True, in_native_combat=False, proximity_known=True,
            near_observer=False, proximity_bound_m=500, deleted_observed=True)])


class OptionalProviderTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("tools.package.optional_provider")
        self.data = fixture()

    def evaluate(self):
        return self.mod.evaluate(self.data)

    def reason(self, code):
        result = self.evaluate()
        self.assertIn(code, result["reasons"])
        self.assertNotEqual("candidate", result["status"])
        return result

    def test_explicit_recovery_exception_is_declaration_candidate_only(self):
        self.data["policy"]["allow_builtin_stuck_recovery"] = True
        result = self.evaluate()
        self.assertTrue(result["schema_valid"])
        self.assertEqual("candidate", result["status"])
        self.assertEqual([], result["reasons"])
        self.assertTrue(result["recovery_relocation_allowed"])
        self.assertEqual("reviewed-human-ai-built-in-stuck-recovery-only",
                         result["recovery_relocation_scope"])
        self.assertEqual(PIN, result["recovery_relocation_source_pin"])
        self.assertTrue(result["diagnostic_only"])
        for field in ("runtime_qualified", "production_enabled", "artifact_bytes_verified"):
            self.assertFalse(result[field])

    def test_recovery_false_and_main_opt_in_are_separate_gates(self):
        result = self.reason("source-teleport-unsupported")
        self.assertFalse(result["recovery_relocation_allowed"])
        self.data["policy"]["allow_builtin_stuck_recovery"] = True
        self.data["experimental_opt_in"] = False
        result = self.reason("experimental-opt-in-disabled")
        self.assertEqual("blocked", result["status"])
        self.assertEqual(["experimental-opt-in-disabled"], result["reasons"])

    def test_recovery_exception_cannot_override_unreviewed_source(self):
        for field, value in (("commit", "0"*40), ("repository", "other/repository"),
                             ("version", "1.9.85")):
            self.data = fixture()
            self.data["policy"]["allow_builtin_stuck_recovery"] = True
            self.data["source"][field] = value
            with self.subTest(field=field):
                result = self.reason("source-unreviewed")
                self.assertFalse(result["recovery_relocation_allowed"])
                self.assertFalse(result["runtime_qualified"])

    def test_recovery_flag_is_required_exact_boolean_and_rejects_unknown_flags(self):
        for value in (0, 1, None, "true", [], {}):
            self.data = fixture()
            self.data["policy"]["allow_builtin_stuck_recovery"] = value
            with self.subTest(value=value):
                result = self.evaluate()
                self.assertEqual("rejected", result["status"])
                self.assertFalse(result["recovery_relocation_allowed"])
        self.data = fixture()
        del self.data["policy"]["allow_builtin_stuck_recovery"]
        self.assertEqual("rejected", self.evaluate()["status"])
        self.data = fixture()
        self.data["policy"]["allow_builtin_teleport"] = True
        self.assertEqual("rejected", self.evaluate()["status"])

    def test_recovery_exception_removes_only_relocation_veto(self):
        changes = [
            lambda d: d["policy"].update(global_reload_all=True),
            lambda d: d["policy"].update(global_flanking_outside_combat=True),
            lambda d: d["policy"].update(effective_state_sha256=None),
            lambda d: d["policy"]["actors"][0].update(invincible=True),
            lambda d: d["policy"]["actors"][0].update(reload_mask=1),
            lambda d: d["policy"]["actors"][0].update(damage_received_multiplier=0),
            lambda d: d["artifacts"]["items"].pop(),
            lambda d: d["addons"].pop(),
            lambda d: d["build"].update(scripts_sha256="0"*64),
            lambda d: d["world"].update(name="othermap"),
            lambda d: d["retirements"][0].update(visibility_current=True),
            lambda d: d["retirements"][0].update(optics_known=None),
            lambda d: d["retirements"][0].update(now_ms=12000),
            lambda d: d["retirements"][0].update(clear_since_ms=9000),
            lambda d: d["retirements"][0].update(session="other"),
            lambda d: d["policy"]["limits"].update(max_items=1),
        ]
        for mutate in changes:
            self.data = fixture()
            mutate(self.data)
            conservative = self.evaluate()
            self.assertIn("source-teleport-unsupported", conservative["reasons"])
            self.data["policy"]["allow_builtin_stuck_recovery"] = True
            with self.subTest(mutate=mutate):
                result = self.evaluate()
                self.assertEqual(set(conservative["reasons"]) - {"source-teleport-unsupported"},
                                 set(result["reasons"]))
                self.assertEqual("blocked", result["status"])
                for field in ("runtime_qualified", "production_enabled", "artifact_bytes_verified"):
                    self.assertFalse(result[field])

    def test_recovery_exception_cannot_change_provider_scope(self):
        self.data["policy"]["allow_builtin_stuck_recovery"] = True
        self.data["provider"] = "infected"
        result = self.evaluate()
        self.assertEqual("rejected", result["status"])
        self.assertFalse(result["recovery_relocation_allowed"])

    def test_current_source_has_irreducible_teleport_blocker(self):
        result = self.reason("source-teleport-unsupported")
        self.assertTrue(result["schema_valid"])
        self.assertEqual("blocked", result["status"])
        self.assertTrue(result["diagnostic_only"])
        self.assertFalse(result["runtime_qualified"])
        self.assertFalse(result["production_enabled"])
        self.assertFalse(result["artifact_bytes_verified"])
        self.assertEqual(["receipt-1"], result["declared_clear_retirements"])

    def test_opt_in_cannot_promote_source_and_supported_bool_is_rejected(self):
        for flag in (False, True):
            self.data["experimental_opt_in"] = flag
            self.reason("source-teleport-unsupported")
        self.data["supported"] = True
        self.assertEqual("rejected", self.evaluate()["status"])

    def test_unknown_artifacts_never_follow_from_source_pin(self):
        self.data["artifacts"] = dict(status="unknown", items=[])
        result = self.reason("artifact-pins-missing")
        self.assertEqual("unknown", result["artifact_pin_status"])
        self.assertEqual([], result["declared_clear_retirements"])

    def test_source_identity_and_snapshot_hash_are_distinct(self):
        self.data["source"]["commit"] = "0"*40
        self.reason("source-unreviewed")
        self.data = fixture()
        self.data["source"]["snapshot_sha256"] = PIN
        self.assertEqual("rejected", self.evaluate()["status"])

    def test_artifact_source_mapping_is_not_just_matching_version(self):
        self.data["artifacts"]["items"][0]["source_commit"] = "0"*40
        self.reason("artifact-source-pin-mismatch")
        self.data = fixture()
        self.data["artifacts"]["items"][1]["inventory_sha256"] = "not-a-hash"
        self.assertEqual("rejected", self.evaluate()["status"])

    def test_missing_package_and_addon_are_explicit(self):
        self.data["artifacts"]["items"].pop()
        self.reason("artifact-package-closure")
        self.data = fixture()
        self.data["artifacts"]["items"][0]["addons"].pop()
        self.reason("artifact-addon-closure")

    def test_dependency_cycle_is_rejected_before_exact_graph_comparison(self):
        next(row for row in self.data["addons"] if row["name"] == "DZ_Data")["requires"] = ["JM_CF_Scripts"]
        self.assertEqual("rejected", self.reason("dependency-cycle")["status"])

    def test_missing_dependency_and_wrong_edge_are_distinct(self):
        self.data["addons"] = [r for r in self.data["addons"] if r["name"] != "DF_GUI"]
        self.reason("dependency-missing")
        self.data = fixture()
        next(r for r in self.data["addons"] if r["name"] == "DF_Scripts")["requires"] = ["DZ_Scripts"]
        self.reason("dependency-pin-mismatch")

    def test_duplicate_graph_packages_and_actor_ids_are_rejected(self):
        for key in ("graph", "package", "actor", "receipt"):
            self.data = fixture()
            target = {"graph": self.data["addons"], "package": self.data["artifacts"]["items"],
                      "actor": self.data["policy"]["actors"], "receipt": self.data["retirements"]}[key]
            target.append(copy.deepcopy(target[0]))
            with self.subTest(key=key):
                self.assertEqual("rejected", self.evaluate()["status"])

    def test_global_reload_overrides_actor_zero(self):
        for name, value in (("global_reload_mask", 1), ("global_reload_all", True)):
            self.data = fixture()
            self.data["policy"][name] = value
            self.reason("unlimited-ammunition")
        self.data["policy"]["actors"][0]["reload_mask"] = 1
        self.reason("unlimited-ammunition")

    def test_unknown_effective_state_is_not_false(self):
        for field in ("global_reload_mask", "global_reload_all", "global_flanking_outside_combat"):
            self.data = fixture()
            self.data["policy"][field] = None
            self.reason("effective-state-unknown")
        self.data = fixture()
        self.data["policy"]["effective_state_sha256"] = None
        self.reason("effective-state-unknown")

    def test_actor_fairness_and_finite_inventory_are_checked(self):
        changes = [
            ("reload_mask", 1, "unlimited-ammunition"),
            ("flanking_outside_combat", True, "outside-combat-flanking"),
            ("invincible", True, "actor-damage-policy"),
            ("damage_multiplier", 2, "actor-damage-policy"),
            ("damage_received_multiplier", 0, "actor-damage-policy"),
            ("headshot_resistance", 1, "actor-damage-policy"),
        ]
        for field, value, code in changes:
            self.data = fixture()
            self.data["policy"]["actors"][0][field] = value
            with self.subTest(field=field):
                self.reason(code)
        self.data = fixture()
        self.data["policy"]["actors"][0]["ammunition_units"] = -1
        self.assertEqual("rejected", self.evaluate()["status"])

    def test_build_world_and_native_source_binding(self):
        for section, field, value, reason in (
            ("build", "version", "1.29.1", "build-unreviewed"),
            ("build", "scripts_sha256", "0"*64, "native-scripts-pin-mismatch"),
            ("world", "name", "othermap", "world-unreviewed")):
            self.data = fixture()
            self.data[section][field] = value
            with self.subTest(field=field):
                self.reason(reason)

    def test_retirement_receipt_identity_binding(self):
        for field, value in (("session", "other"), ("actor_id", "other"),
                             ("world_sha256", "0"*64), ("source_commit", "0"*40),
                             ("artifact_sha256", "0"*64)):
            self.data = fixture()
            self.data["retirements"][0][field] = value
            with self.subTest(field=field):
                result = self.reason("retirement-binding-mismatch")
                self.assertEqual([], result["declared_clear_retirements"])

    def test_unknown_visible_combat_proximity_inputs_fail_closed(self):
        fields = ("coverage_known", "spectators_known", "optics_known",
                  "visibility_current", "visibility_recent", "native_combat_known",
                  "in_native_combat", "proximity_known", "near_observer")
        for field in fields:
            self.data = fixture()
            self.data["retirements"][0][field] = None
            with self.subTest(field=field):
                self.reason("observer-inputs-unknown")
        for field in ("visibility_current", "visibility_recent", "in_native_combat", "near_observer"):
            self.data = fixture()
            self.data["retirements"][0][field] = True
            self.reason("observer-retirement-veto")

    def test_stale_rollback_hysteresis_and_wrong_bound_fail_closed(self):
        for values, reason in (
            (dict(now_ms=12000), "observer-stale"),
            (dict(now_ms=9000), "observer-clock-order"),
            (dict(clear_since_ms=10001), "observer-clock-order"),
            (dict(clear_since_ms=9000), "observer-hysteresis"),
            (dict(proximity_bound_m=499), "observer-bound-mismatch"),
            (dict(deleted_observed=False), "retirement-deletion-unconfirmed")):
            self.data = fixture()
            self.data["retirements"][0].update(values)
            with self.subTest(reason=reason):
                result = self.reason(reason)
                self.assertEqual([], result["declared_clear_retirements"])

    def test_strict_types_unknown_fields_and_numeric_bounds(self):
        mutations = [
            lambda d: d.update(schema_version=True),
            lambda d: d.update(experimental_opt_in=1),
            lambda d: d["policy"]["limits"].update(max_actors=True),
            lambda d: d["policy"]["limits"].update(max_tick_work=33),
            lambda d: d["policy"]["limits"].update(hysteresis_ms=0),
            lambda d: d["policy"]["actors"][0].update(invincible=0),
            lambda d: d["policy"]["actors"][0].update(damage_multiplier=float("nan")),
            lambda d: d["retirements"][0].update(now_ms=True),
            lambda d: d["source"].update(local_path="/synthetic/private"),
        ]
        for mutate in mutations:
            self.data = fixture()
            mutate(self.data)
            with self.subTest(mutate=mutate):
                self.assertEqual("rejected", self.evaluate()["status"])

    def test_counts_depth_cycles_and_strings_are_bounded(self):
        for value in ("x"*257, [None]*65):
            self.data = fixture()
            self.data["unknown"] = value
            self.assertEqual("rejected", self.evaluate()["status"])
        deep = {}
        cursor = deep
        for _ in range(12):
            cursor["next"] = {}
            cursor = cursor["next"]
        self.data["unknown"] = deep
        self.assertEqual("rejected", self.evaluate()["status"])
        self.data = fixture()
        self.data["cycle"] = self.data
        self.assertEqual("rejected", self.evaluate()["status"])
        self.data = fixture()
        self.data["policy"]["actors"] = [dict(self.data["policy"]["actors"][0], id="a"+str(i)) for i in range(5)]
        self.reason("actor-budget-exceeded")

    def test_json_duplicate_keys_nan_utf8_and_byte_limits(self):
        for payload in (b'{"schema_version":1,"schema_version":1}', b'{"x":NaN}',
                        b"\xff", b" " * 65537, b'{"x":123456789012345678901}'):
            with self.subTest(payload=payload[:40]), self.assertRaises(ValueError):
                self.mod.decode_manifest(payload)

    def test_json_roundtrip_and_report_are_detached_without_private_values(self):
        decoded = self.mod.decode_manifest(json.dumps(self.data).encode())
        self.assertEqual(self.data, decoded)
        result = self.mod.evaluate(decoded)
        decoded["source"]["commit"] = "0"*40
        self.assertIn("source-teleport-unsupported", result["reasons"])
        self.assertEqual(result, json.loads(json.dumps(result, allow_nan=False)))
        self.assertNotIn("synthetic-session", json.dumps(result))

    def test_group_item_and_actor_resource_budgets(self):
        for field, value, code in (
            ("max_groups", 1, "group-budget-exceeded"),
            ("max_items", 1, "item-budget-exceeded")):
            self.data = fixture()
            if field == "max_groups":
                self.data["policy"]["actors"].append(dict(
                    self.data["policy"]["actors"][0], id="actor-2", group_id="group-2"))
            self.data["policy"]["limits"][field] = value
            self.reason(code)

    def test_absent_actor_snapshot_fails_closed(self):
        self.data["policy"]["actors"] = []
        self.reason("actor-state-missing")

    def test_receipts_bind_build_and_effective_state_snapshot(self):
        for field in ("build_sha256", "native_scripts_sha256", "effective_state_sha256"):
            self.data = fixture()
            self.data["retirements"][0][field] = "0"*64
            with self.subTest(field=field):
                result = self.reason("retirement-binding-mismatch")
                self.assertEqual([], result["declared_clear_retirements"])

    def test_receipt_batch_respects_explicit_work_budget(self):
        self.data["policy"]["limits"]["max_tick_work"] = 1
        self.data["policy"]["actors"].append(dict(
            self.data["policy"]["actors"][0], id="actor-2"))
        self.data["retirements"].append(dict(
            self.data["retirements"][0], receipt_id="receipt-2", actor_id="actor-2"))
        result = self.reason("retirement-work-budget-exceeded")
        self.assertEqual([], result["declared_clear_retirements"])

    def test_missing_observer_fields_and_false_known_flags(self):
        del self.data["retirements"][0]["optics_known"]
        self.assertEqual("rejected", self.evaluate()["status"])
        for field in ("coverage_known", "spectators_known", "optics_known",
                      "native_combat_known", "proximity_known"):
            self.data = fixture()
            self.data["retirements"][0][field] = False
            self.reason("observer-inputs-unknown")


if __name__ == "__main__":
    unittest.main()
