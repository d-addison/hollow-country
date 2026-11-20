"""D4 source regressions on explicit synthetic config/actor/log fixtures.

These execute restricted translations of the shipped helpers, not DayZ AI.
"""
from types import SimpleNamespace as NS
import math
import unittest

if __package__:
    from tests.legacy.test_infected_contract import policy_functions
else:
    from tests.legacy.test_infected_contract import policy_functions


class Array(list):
    def __bool__(self):
        return True  # Allocated Enforce array remains non-null when empty.

    def Count(self):
        return len(self)


class InfectedVariantTests(unittest.TestCase):
    def test_w5_variety_caps_and_group_scaling_smoke(self):
        # Explicit synthetic scalar inputs; no engine/animation evidence.
        policy = policy_functions("Variety/HCInfectedVarietyPolicy.c", Math=NS(
            Min=min, Max=max, Floor=math.floor, Round=lambda v: math.floor(v + .5),
            Clamp=lambda v, lo, hi: max(lo, min(hi, v))))
        for players, scale, dormant, cohort in ((1, .6, 5, 3), (3, 1., 8, 4),
                                               (6, 1.3, 10, 5), (99, 1.3, 10, 5)):
            self.assertAlmostEqual(scale, policy['GroupScale'](players))
            self.assertEqual(dormant, policy['DormantLimit'](scale))
            self.assertEqual(cohort, policy['CohortLimit'](4, 6, scale))
        self.assertEqual(3, policy['CohortLimit'](3, 6, .6))  # v1 minimum stays three
        self.assertEqual(6, policy['CohortLimit'](6, 6, 1.3))
        self.assertEqual(2, policy['CohortLimit'](6, 2, 1.3))
        self.assertEqual(12, policy['DormantLimit'](100))
        for population in range(25):
            for nightness in (0., 1.):
                runners = policy['RunnerLimit'](population, nightness)
                self.assertLessEqual(runners, population * .15)
                if not nightness:
                    self.assertLessEqual(runners, population * .08)
        self.assertGreater(policy['DormantChance'](0., 0.), policy['DormantChance'](1., 1.))
        for role, expected in ((0, 1), (1, 2), (2, 3)):
            self.assertEqual(expected, policy['MovementLimit'](role, 3))
            self.assertEqual(0, policy['MovementLimit'](role, 0))
            self.assertEqual(.5, policy['MovementLimit'](role, .5))

    def setUp(self):
        self.logs = []
        self.policy = policy_functions()
        self.profiles = policy_functions("HCInfectedProfiles.c",
            HCInfectedPolicy=NS(**self.policy), Print=self.logs.append)

    def config(self, civilian, military=None, enabled=True):
        if military is None:
            military = civilian
        return NS(EnableVariantPolicies=enabled, CivilianVariants=Array(civilian),
                  MilitaryVariants=Array(military))

    def select(self, config, stance, military=False):
        infected = NS(HCIndividualStance=lambda: stance, IsZombieMilitary=lambda: military)
        return self.profiles["ConfiguredVariant"](infected, config)

    def test_stalker_and_heavy_maps_do_not_admit_unavailable_physical_variants(self):
        # Port of b04 audit D4 counterexample: valid input is not capability.
        self.assertFalse(self.profiles["ValidateMap"](Array([3, 4, 0, 1]), True),
            "Requested stalker/heavy map must not count as available without a capability disposition")

    def test_supported_only_map_selects_requested_attention_policy_without_warning(self):
        config = self.config([0, 1, 2, 5], [5, 2, 1, 0])
        for configured in (config.CivilianVariants, config.MilitaryVariants):
            self.assertTrue(self.profiles["ValidateMap"](configured, False))
            self.assertTrue(self.profiles["ValidateMap"](configured, True))
        for military, expected in ((False, [0, 1, 2, 5]), (True, [5, 2, 1, 0])):
            self.assertEqual(expected, [self.select(config, stance, military) for stance in range(4)])
        self.profiles["LogUnsupportedSubstitutions"](config)
        self.assertEqual([], self.logs)

    def test_mixed_map_preserves_input_and_reports_actual_ordinary_substitution(self):
        config = self.config([3, 4, 0, 1], [2, 3, 5, 4])
        self.assertTrue(self.profiles["ValidateMap"](config.CivilianVariants, False))
        requested = [self.select(config, stance) for stance in range(4)]
        self.assertEqual([3, 4, 0, 1], requested)
        self.assertEqual([0, 0, 0, 1], [self.policy["ResolveVariant"](choice) for choice in requested])
        self.profiles["LogUnsupportedSubstitutions"](config)
        self.assert_substitutions(stalker=2, heavy=2)
        self.assertEqual([3, 4, 0, 1], config.CivilianVariants)
        self.assertEqual([2, 3, 5, 4], config.MilitaryVariants)

    def test_all_unsupported_map_is_valid_input_without_admitting_either_capability(self):
        config = self.config([3, 3, 4, 4], [4, 3, 4, 3])
        for configured in (config.CivilianVariants, config.MilitaryVariants):
            self.assertTrue(self.profiles["ValidateMap"](configured, False))
            self.assertFalse(self.profiles["ValidateMap"](configured, True))
        for military in (False, True):
            for stance in range(4):
                requested = self.select(config, stance, military)
                self.assertIn(requested, (3, 4))
                self.assertEqual(0, self.policy["ResolveVariant"](requested))
        self.profiles["LogUnsupportedSubstitutions"](config)
        self.assert_substitutions(stalker=4, heavy=4)

    def assert_substitutions(self, stalker, heavy):
        self.assertEqual(2, len(self.logs))  # Once per kind, across both maps.
        for requested, name, reason, count in ((3, "careful_stalker", "stalker_physical_unqualified", stalker),
                (4, "forceful_heavy", "heavy_physical_unqualified", heavy)):
            matching = [line for line in self.logs if f"requested={requested} " in line]
            self.assertEqual(1, len(matching))
            for field in (f"name={name}", "disposition=unsupported_substituted_native",
                          f"reason={reason}", "resolved=0", "actual=ordinary_wanderer",
                          f"count={count}"):
                self.assertIn(field, matching[0])

    def test_one_unsupported_kind_is_logged_once_with_all_eight_slots_counted(self):
        for requested in (3, 4):
            self.logs.clear()
            config = self.config([requested] * 4)
            self.profiles["LogUnsupportedSubstitutions"](config)
            self.assertEqual(1, len(self.logs))
            self.assertIn(f"requested={requested} ", self.logs[0])
            self.assertIn("count=8", self.logs[0])

    def test_invalid_maps_fail_closed_without_scanning_or_changing_them(self):
        for invalid in (None, Array([3]), Array([3] * 5), Array([3, 4, -1, 0]),
                        Array([3, 4, 6, 0]), Array([3, 4, 100, 0])):
            with self.subTest(invalid=invalid):
                for enabled in (False, True):
                    self.assertFalse(self.profiles["ValidateMap"](invalid, enabled))
                for bad_military in (False, True):
                    config = self.config([3, 4, 0, 1])
                    if bad_military:
                        config.MilitaryVariants = invalid
                    else:
                        config.CivilianVariants = invalid
                    before = repr(config)
                    self.assertEqual(-1, self.select(config, 0))
                    self.assertEqual(-1, self.select(config, 0, True))
                    self.profiles["LogUnsupportedSubstitutions"](config)
                    self.assertEqual(before, repr(config))
                    self.assertEqual([], self.logs)

    def test_empty_map_keeps_native_fallback_even_when_other_map_is_populated(self):
        for civilian, military in (([], []), ([], [3, 4, 0, 1]), ([3, 4, 0, 1], [])):
            config = self.config(civilian, military)
            self.assertTrue(self.profiles["ValidateMap"](Array(), False))
            self.assertFalse(self.profiles["ValidateMap"](Array(), True))
            for category in (False, True):
                self.assertEqual(-1, self.select(config, 0, category))
            self.profiles["LogUnsupportedSubstitutions"](config)
            self.assertEqual([], self.logs)
            self.assertEqual(civilian, config.CivilianVariants)
            self.assertEqual(military, config.MilitaryVariants)

    def test_disabled_preference_and_bad_stance_never_select_or_log(self):
        config = self.config([3, 4, 0, 1], enabled=False)
        self.assertEqual(-1, self.select(config, 0))
        self.profiles["LogUnsupportedSubstitutions"](config)
        self.profiles["LogUnsupportedSubstitutions"](None)
        self.assertEqual([], self.logs)
        config.EnableVariantPolicies = True
        for stance in (-1, 4):
            self.assertEqual(-1, self.select(config, stance))

    def test_supported_descriptor_never_labels_a_substitution_as_stalker_or_heavy(self):
        for requested, proposed in ((3, "careful_stalker"), (4, "forceful_heavy")):
            self.assertEqual(proposed, self.profiles["RequestedDescriptorName"](requested))
            self.assertEqual("ordinary_wanderer", self.profiles["DescriptorName"](requested))
        self.assertEqual("injured_crawler", self.profiles["DescriptorName"](6))
        self.assertEqual("unavailable", self.profiles["DescriptorName"](-1))


if __name__ == "__main__":
    unittest.main()
