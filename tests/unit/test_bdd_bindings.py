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
    def test_completion_scenarios_cannot_be_omitted(self):
        expected = {
            'Observe bounded owned-process counters without inferring engine liveness': 'test_process_observation.py',
            'Admit actor-free startup controls only from unchanged bounded evidence': 'test_native_startup_runner.py',
            'Bind measured interior records without inventing layout qualification': 'test_interior_measured_catalog.py',
            'Preserve audited cutting tools through salvage registration and completion': 'test_salvage_tools.py',
            'Preserve taped-light identity while consuming tape on each mount': 'test_taped_light_service.py',
            'Retain whole-source action and item-use evidence without evaluating dispatch': 'test_action_audit.py',
            'Activate stamina only from an opted-in trusted session configuration': 'test_stamina_configuration.py',
            'Schedule resource attraction only from bounded fresh native observations': 'test_ecology_rules.py',
            'Admit fuel receipts only inside an owned bounded native run': 'test_fuel_probe_runner.py',
            'Require all death cases before the native probe deadline': 'test_wine_compile_probe.py',
            'Retain whole-content item and recipe evidence within bounded review work': 'test_item_review.py',
            'Authorize a single diagnostic fuel transfer without replay': 'test_siphon_fuel_action.py',
            'Prepare fuel observations without accepting an unobserved transfer': 'test_fuel_siphon_probe.py',
            'Compare native stamina transport with bounded numeric tolerance': 'test_stamina_transport_probe.py',
            'Display bounded native stamina and carried-weight samples': 'test_stamina_hud.py',
            'Track optional event progress only from admitted observations': 'test_event_director.py',
            'Admit complete item export manifests without upgrading metadata to compatibility': 'test_item_compatibility_manifest.py',
            'Prepare bounded infected death observations without claiming rendered physics': 'test_infected_death_probe.py',
            'Build weather candidates without silently changing native defaults': 'test_atmosphere.py',
            'Retain every audited class in the flashlight candidate denominator': 'test_flashlight_matrix.py',
            'Read consistent bounded UTC snapshots for group expiry': 'test_group_clock.py',
            'Exercise opt-in group policy fixtures without world side effects': 'test_group_native_checks.py',
            'Recover group command ordering without replaying uncertain mutations': 'test_group_client.py',
            'Preserve group map edits and native menu dispatch': 'test_group_ui.py',
            'Scale continuous stamina changes through the native handler': 'test_stamina_integration.py',
            'Bound effective item metadata acquisition without claiming compatibility': 'test_item_compatibility_audit.py',
            'Authorize group changes and bound durable server state': 'test_group_server.py',
            'Retain ambiguous recipes in a whole-source census': 'test_crafting_audit.py',
            'Reject fuel credits that can create quantity through rounding': 'test_fuel_transfer.py',
            'Calculate bounded stamina and carried-load changes': 'test_stamina_policy.py',
            'Plan portable criteria without manufacturing acceptance': 'test_automation.py',
            'Preserve the original and extended ledger without local specs': 'test_portable_catalog.py',
            'Admit measured room catalogs without enabling production search': 'test_room_catalog_completion.py',
            'Veto observer transitions until complete trustworthy evidence exists': 'test_observer_transition.py',
            'Reject unsafe private repository content without echoing secrets': 'test_hygiene.py',
            'Prepare interior candidates only from explicit measured evidence': 'test_interior_catalog.py',
            'Persist cohort intent before native ownership transfer': 'test_infected_persistence.py',
            'Observe route progress and fairly schedule cohort clues': 'test_infected_routes.py',
            'Keep infected profiles and pack retargets bound to observed evidence': 'test_infected_wave.py',
            'Unwind interrupted module lifecycle without repeating callbacks': 'test_core_lifecycle.py',
            'Reject salvage admission after failed core startup': 'test_crafting_completion.py',
            'Prepare pinned CE geometry candidates without inventing eligibility': 'test_coverage_patch.py',
            'Recover private installation transactions without overwriting drift': 'test_deploy.py',
            'Bound supplementary infected propagation and restart recovery': 'test_infected_completion.py',
        }
        for name, pattern in expected.items():
            with self.subTest(name=name):
                self.assertTrue(name in bdd.BINDINGS, name)
                self.assertEqual(pattern, bdd.BINDINGS[name][1])

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
