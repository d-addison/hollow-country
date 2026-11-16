"""Synthetic feature inputs exercise admission without running the bound suites."""
import io
import unittest
from unittest.mock import patch

from tools.validate import bdd


def synthetic_feature(names=None):
    names = list(bdd.BINDINGS) if names is None else names
    lines = ["@offline @synthetic", "Feature: Synthetic bound acceptance",
             "  Synthetic tooling checks only."]
    for name in names:
        lines += [f"  Scenario: {name}"]
        lines += ["    " + step for step in bdd.BINDINGS[name][0]]
    return "\n".join(lines) + "\n"


class BDDBindingsTests(unittest.TestCase):
    def admit(self, text):
        with patch.object(bdd.sys, "argv", ["bdd", "synthetic.feature"]), \
             patch.object(bdd.Path, "read_text", return_value=text), \
             patch.object(bdd.unittest.TestLoader, "discover") as discover, \
             patch.object(bdd.unittest, "TextTestRunner") as runner, \
             patch("sys.stdout", new_callable=io.StringIO), \
             patch("sys.stderr", new_callable=io.StringIO) as stderr:
            discover.return_value = unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])
            runner.return_value.run.return_value.wasSuccessful.return_value = True
            code = bdd.main()
            return code, discover.call_count, runner.call_count, stderr.getvalue()

    def test_steps_are_parsed_in_order(self):
        original = "Scenario: example\n Given input\n When action\n Then outcome\n"
        self.assertEqual([("example", ("Given input", "When action", "Then outcome"))],
                         bdd.parse_scenarios(original))

    def test_empty_or_incomplete_scenario_fails(self):
        for text in ("Feature: empty", "Scenario: missing\n Given input\n Then outcome"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                bdd.parse_scenarios(text)

    def test_complete_required_scenario_set_executes_all_bindings(self):
        code, calls, runners, _ = self.admit(synthetic_feature())
        self.assertEqual((0, len(bdd.BINDINGS), 1), (code, calls, runners))

    def test_removing_any_required_scenario_fails_before_execution(self):
        for omitted in bdd.BINDINGS:
            with self.subTest(omitted=omitted):
                text = synthetic_feature([n for n in bdd.BINDINGS if n != omitted])
                code, calls, runners, error = self.admit(text)
                self.assertEqual((1, 0, 0), (code, calls, runners))
                self.assertIn(omitted, error)

    def test_changed_step_and_unbound_scenario_fail_before_execution(self):
        original = synthetic_feature()
        for text in (original.replace("Given synthetic mission XML", "Given real mission XML"),
                     original + "Scenario: Unbound\n Given input\n When action\n Then outcome\n"):
            with self.subTest(text=text):
                self.assertEqual((1, 0, 0), self.admit(text)[:3])

    def test_unsupported_assertions_and_structures_fail_before_execution(self):
        original = synthetic_feature()
        additions = ("But duplicate allocations never occur", "* no duplicates",
                     '"""', "| expected | actual |", "Examples:",
                     "Scenario Outline: Missing acceptance", "Rule: Unsafe omission",
                     "Background:", "This assertion must not disappear")
        for addition in additions:
            with self.subTest(addition=addition):
                self.assertEqual((1, 0, 0), self.admit(original + addition + "\n")[:3])

    def test_background_and_steps_before_first_scenario_are_rejected(self):
        original = synthetic_feature()
        for preamble in ("Background:\n Given authorization\n", "Given authorization\n"):
            with self.subTest(preamble=preamble):
                text = original.replace("  Scenario:", preamble + "  Scenario:", 1)
                self.assertEqual((1, 0, 0), self.admit(text)[:3])

    def test_comments_tags_and_feature_description_are_allowed(self):
        text = synthetic_feature().replace("  Scenario:", "  # acceptance\n  @AC-001\n  Scenario:")
        self.assertEqual(0, self.admit(text)[0])

    def test_duplicate_scenario_is_rejected(self):
        text = synthetic_feature() + synthetic_feature([next(iter(bdd.BINDINGS))])
        self.assertEqual((1, 0, 0), self.admit(text)[:3])


if __name__ == "__main__":
    unittest.main()
