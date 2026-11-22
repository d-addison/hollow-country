"""Operator settings admission (tools.validate.runtime) against the shipped file and registry.

Offline: validates authored data only; it never establishes DayZ behaviour. Expectations derive
from the registry-backed rule tables the validator itself exposes.
"""
import copy
import json
import unittest

from tools.validate import runtime
from tools.validate import settings_consistency

SHIPPED = runtime.ROOT / "config/hollow-country-settings.json"
DEPENDENCIES = (("EnableSearch", "EnableInteriors"), ("EnableHordes", "EnableInfected"),
                ("EnableAlertChains", "EnableInfected"))


class RuntimeSettingsTests(unittest.TestCase):
    def setUp(self):
        self.shipped = json.loads(SHIPPED.read_text())

    def test_shipped_settings_and_registry_mirror_are_admitted(self):
        self.assertEqual([], runtime.validate_settings(self.shipped))
        self.assertEqual([], settings_consistency.check_consistency())

    def test_shipped_feature_flags_follow_the_registry_defaults(self):
        for key in sorted(runtime.FLAGS | (runtime.V2_FLAGS & self.shipped.keys())):
            with self.subTest(key=key):
                self.assertIs(runtime.RULES[key]["default"], self.shipped[key])
        for key in sorted(runtime.FLAGS):
            with self.subTest(core=key):
                self.assertIs(True, self.shipped[key])

    def test_explicit_disable_of_any_flag_is_preserved_and_admitted(self):
        for key in sorted(runtime.FLAGS):
            value = copy.deepcopy(self.shipped)
            value[key] = False
            with self.subTest(key=key):
                self.assertEqual([], [e for e in runtime.validate_settings(value) if "requires" not in e])
                self.assertIs(False, value[key])

    def test_child_features_require_their_enabled_parent(self):
        for child, parent in DEPENDENCIES:
            value = copy.deepcopy(self.shipped)
            value[parent] = False
            value[child] = True
            with self.subTest(child=child):
                self.assertIn(f"{child} requires {parent}", runtime.validate_settings(value))

    def test_malformed_flags_fail_admission(self):
        for key in sorted(runtime.FLAGS):
            for bad in (1, 0, "true", None, [True]):
                value = copy.deepcopy(self.shipped)
                value[key] = bad
                with self.subTest(key=key, bad=bad):
                    self.assertIn(f"{key} must be boolean", runtime.validate_settings(value))

    def test_limits_outside_the_registry_range_fail_admission(self):
        for key, (low, high) in runtime.LIMITS.items():
            for bad in (low - 1, high + 1, True, "1", None):
                value = copy.deepcopy(self.shipped)
                value[key] = bad
                with self.subTest(key=key, bad=bad):
                    self.assertIn(f"{key} must be an integer within {low}..{high}",
                                  runtime.validate_settings(value))

    def test_limits_at_the_registry_bounds_are_admitted(self):
        for key, (low, high) in runtime.LIMITS.items():
            for edge in (low, high):
                value = copy.deepcopy(self.shipped)
                value[key] = edge
                with self.subTest(key=key, edge=edge):
                    self.assertEqual([], runtime.validate_settings(value))

    def test_missing_unknown_schema_and_non_object_fail_admission(self):
        self.assertEqual(["Settings must be a JSON object"], runtime.validate_settings([]))
        value = copy.deepcopy(self.shipped)
        del value["TickIntervalMs"]
        value["NotASetting"] = True
        value["SchemaVersion"] = self.shipped["SchemaVersion"] + 1
        errors = runtime.validate_settings(value)
        for expected in ("Missing field TickIntervalMs", "Unknown field NotASetting", "Unsupported SchemaVersion"):
            self.assertIn(expected, errors)

    def test_ai_limits_reject_unknown_keys_and_inverted_ranges(self):
        value = copy.deepcopy(self.shipped)
        value["AILimits"] = {"NotALimit": 1, "PartyMin": 3, "PartyMax": 2}
        errors = runtime.validate_settings(value)
        self.assertIn("Unknown field AILimits.NotALimit", errors)
        self.assertIn("AILimits.PartyMin must not exceed PartyMax", errors)


if __name__ == "__main__":
    unittest.main()
