"""Synthetic scalar contracts executed from the shipped Enforce method bodies.

Uses the existing infected-policy translator convention, not a Python stamina
model. This is not an Enforce compiler, native hook, HUD or network acceptance.
All numbers below are explicit synthetic fixtures, not measured tuning.
"""
import math
from pathlib import Path
import re
import unittest


SOURCE = (Path(__file__).resolve().parents[2] /
          "mods/HollowCountry/scripts/4_World/Survival/HCStaminaPolicy.c")


def policy_functions():
    source = re.sub(r"//[^\n]*", "", SOURCE.read_text(encoding="utf-8"))
    namespace = {"__builtins__": {}}
    pattern = r"static (?:bool|int|float) (\w+)\(([^)]*)\)\s*\{"
    for match in re.finditer(pattern, source):
        depth, end = 1, match.end()
        while depth:
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        body = source[match.end():end - 1]
        args = [arg.strip().split()[-1] for arg in match[2].split(",") if arg.strip()]
        lines = [f"def {match[1]}({', '.join(args)}):"]
        indent = 1
        for token in re.split(r"([{};])", body):
            token = token.strip()
            if not token or token == ";":
                continue
            if token == "{":
                indent += 1
                continue
            if token == "}":
                indent -= 1
                continue
            token = re.sub(r"\b(?:int|float|bool)\s+", "", token)
            token = token.replace("HCStaminaPolicy.", "")
            token = token.replace("&&", " and ").replace("||", " or ")
            token = re.sub(r"!(?!=)", "not ", token)
            token = re.sub(r"\btrue\b", "True", token)
            token = re.sub(r"\bfalse\b", "False", token)
            if token.startswith("if ("):
                token = "if " + token[4:-1] + ":"
            elif token == "else":
                token += ":"
            lines.append("    " * indent + token)
        exec(compile("\n".join(lines), str(SOURCE), "exec"), namespace)
    if "StepUnits" not in namespace:
        raise AssertionError("No authored stamina step was translated")
    return namespace


class StaminaPolicyTests(unittest.TestCase):
    def setUp(self):
        self.p = policy_functions()
        # authority, enabled, current/cap units, elapsed seconds, signed native
        # rate units/s, event units, native drain/recovery factors, policy factors,
        # remaining cooldown seconds. Native condition factors are applied once.
        self.step = [True, True, 100., 200., 1., -4., 0., 1., 1., 1., 1., 0.]

    def test_capacity_is_extended_and_penalty_is_units_per_kg_above_free_grams(self):
        capacity = self.p["CapacityUnits"]
        self.assertEqual(200., capacity(6000., 200., 5., 6000., 1.75))
        self.assertEqual(198.25, capacity(7000., 200., 5., 6000., 1.75))
        self.assertEqual(5., capacity(1_000_000., 200., 5., 6000., 1.75))
        self.assertEqual(200., capacity(1_000_000., 200., 5., 6000., 0.))
        self.assertEqual(100., capacity(0., 100., 100., 0., 20.))

    def test_capacity_settings_reject_every_nonfinite_and_out_of_range_field(self):
        valid = [200., 5., 6000., 1.75]
        self.assertTrue(self.p["ValidCapacitySettings"](*valid))
        for index in range(4):
            for value in (math.nan, math.inf, -math.inf):
                args = valid.copy()
                args[index] = value
                with self.subTest(index=index, value=value):
                    self.assertFalse(self.p["ValidCapacitySettings"](*args))
                    self.assertEqual(-1., self.p["CapacityUnits"](6000., *args))
        for index, value in [(0, 99.9), (0, 500.1), (1, 0.), (1, 201.),
                             (2, -1.), (2, 100001.), (3, -.1), (3, 20.1)]:
            args = valid.copy()
            args[index] = value
            self.assertFalse(self.p["ValidCapacitySettings"](*args))
        for value in (math.nan, math.inf, -math.inf, -1., 1000001.):
            self.assertEqual(-1., self.p["CapacityUnits"](value, *valid))

    def test_dynamics_settings_have_finite_explicit_bounds(self):
        valid = [1., 1., .45, .5, .2]
        p = self.p["ValidDynamicsSettings"]
        self.assertTrue(p(*valid))
        self.assertTrue(p(.05, 5., 0., 30., 1.))
        for index in range(5):
            for value in (math.nan, math.inf, -math.inf):
                args = valid.copy()
                args[index] = value
                self.assertFalse(p(*args))
        for index, value in [(0, 0.), (0, 5.01), (1, 0.), (1, 5.01),
                             (2, -.1), (2, 10.01), (3, -.1), (3, 30.01),
                             (4, 0.), (4, 1.01)]:
            args = valid.copy()
            args[index] = value
            self.assertFalse(p(*args))

    def test_only_enabled_server_policy_may_propose_a_step(self):
        for authority, enabled in [(False, True), (True, False), (False, False)]:
            self.step[:2] = authority, enabled
            self.assertEqual(-1., self.p["StepUnits"](*self.step))
        self.step[:2] = True, True
        self.assertEqual(96., self.p["StepUnits"](*self.step))

    def test_every_step_scalar_rejects_nonfinite_and_out_of_contract_inputs(self):
        for index in range(2, len(self.step)):
            for value in (math.nan, math.inf, -math.inf):
                args = self.step.copy()
                args[index] = value
                with self.subTest(index=index, value=value):
                    self.assertEqual(-1., self.p["StepUnits"](*args))
        for index, value in [(2, -1.), (2, 501.), (3, 0.), (3, 501.),
                             (4, -.1), (4, 1.01), (5, -100.1), (5, 100.1),
                             (6, -1.), (6, 501.), (7, -.1), (7, 16.1),
                             (8, -.1), (8, 16.1), (9, 0.), (9, 5.01),
                             (10, 0.), (10, 5.01), (11, -.1), (11, 30.1)]:
            args = self.step.copy()
            args[index] = value
            with self.subTest(index=index, value=value):
                self.assertEqual(-1., self.p["StepUnits"](*args))

    def test_weight_gain_clips_current_and_weight_loss_never_refills_it(self):
        small = self.p["CapacityUnits"](100000., 200., 5., 6000., 1.75)
        self.step[3:7] = small, 0., 0., 0.
        clipped = self.p["StepUnits"](*self.step)
        self.assertEqual(small, clipped)
        self.step[2:4] = clipped, 200.
        self.assertEqual(clipped, self.p["StepUnits"](*self.step))

    def test_recovery_waits_only_the_remaining_cooldown_portion_of_frame(self):
        self.step[5] = 5.
        self.step[11] = .75
        self.assertEqual(101.25, self.p["StepUnits"](*self.step))
        self.step[11] = 1.
        self.assertEqual(100., self.p["StepUnits"](*self.step))
        self.step[11] = 30.
        self.assertEqual(100., self.p["StepUnits"](*self.step))

    def test_recovery_at_cooldown_boundary_is_independent_of_frame_split(self):
        self.step[5], self.step[11] = 5., .75
        whole = self.p["StepUnits"](*self.step)
        self.step[4] = .5
        first = self.p["StepUnits"](*self.step)
        self.step[2] = first
        self.step[11] = self.p["NextCooldownSeconds"](.75, .5, 0., False, .45, .5)
        self.assertAlmostEqual(whole, self.p["StepUnits"](*self.step))

    def test_native_condition_multipliers_and_policy_scales_apply_exactly_once(self):
        self.step[7], self.step[9] = 1.25 * 1.33, .5
        self.assertAlmostEqual(100 - 4 * 1.25 * 1.33 * .5,
                               self.p["StepUnits"](*self.step))
        self.step[5], self.step[8], self.step[10] = 5., .5 * .33, 2.
        self.assertAlmostEqual(100 + 5 * .5 * .33 * 2.,
                               self.p["StepUnits"](*self.step))

    def test_epinephrine_zero_drain_and_drowning_zero_recovery_are_preserved(self):
        self.step[6], self.step[7] = 25., 0.
        self.assertEqual(100., self.p["StepUnits"](*self.step))
        self.step[5:9] = 5., 0., 1., 0.
        self.assertEqual(100., self.p["StepUnits"](*self.step))

    def test_discrete_event_cost_is_not_multiplied_by_frame_time_or_recovered_back(self):
        self.step[4:8] = 0., 5., 25., 1.25
        self.step[9] = .5
        self.assertEqual(84.375, self.p["StepUnits"](*self.step))
        self.step[4] = 1.
        self.assertEqual(84.375, self.p["StepUnits"](*self.step))

    def test_sustained_drain_and_event_cost_both_obey_zero_and_cap(self):
        self.step[2], self.step[6], self.step[11] = 2., 25., 30.
        self.assertEqual(0., self.p["StepUnits"](*self.step))
        self.step[2:7] = 199., 200., 1., 100., 0.
        self.step[11] = 0.
        self.assertEqual(200., self.p["StepUnits"](*self.step))

    def test_cooldown_rearms_for_real_spend_and_does_not_shorten_longer_native_delay(self):
        p = self.p["NextCooldownSeconds"]
        self.assertEqual(.45, p(0., .1, 4., False, .45, .5))
        self.assertEqual(.5, p(0., .1, 4., True, .45, .5))
        self.assertEqual(4.9, p(5., .1, 4., True, .45, .5))
        self.assertEqual(0., p(.45, 1., 0., False, .45, .5))

    def test_exhaustion_transition_does_not_rearm_forever_at_zero(self):
        next_units = 0.
        cooldown = self.p["NextCooldownSeconds"](0., 0., 1., True, .45, .5)
        # Transition flag is positive -> zero only; resting at zero is not a new
        # transition. An authored integration must persist this state atomically.
        for _ in range(10):
            self.step[2:7] = next_units, 200., .1, 5., 0.
            self.step[11] = cooldown
            next_units = self.p["StepUnits"](*self.step)
            cooldown = self.p["NextCooldownSeconds"](cooldown, .1, 0., False, .45, .5)
        self.assertGreater(next_units, 2.)
        self.assertEqual(0., cooldown)

    def test_cooldown_rejects_every_nonfinite_or_out_of_range_input(self):
        valid = [0., .1, 1., False, .45, .5]
        for index in (0, 1, 2, 4, 5):
            for value in (math.nan, math.inf, -math.inf):
                args = valid.copy()
                args[index] = value
                self.assertEqual(-1., self.p["NextCooldownSeconds"](*args))
        for index, value in [(0, -.1), (0, 30.1), (1, -.1), (1, 1.01),
                             (2, -.1), (2, 50001.), (4, -.1), (4, 10.1),
                             (5, -.1), (5, 30.1)]:
            args = valid.copy()
            args[index] = value
            self.assertEqual(-1., self.p["NextCooldownSeconds"](*args))

    def test_exhaustion_latches_until_configured_fraction_of_current_capacity(self):
        p = self.p["IsExhausted"]
        self.assertTrue(p(False, 0., 200., .2))
        self.assertTrue(p(True, 39., 200., .2))
        self.assertFalse(p(True, 40., 200., .2))
        self.assertFalse(p(False, 1., 200., .2))
        self.assertFalse(p(True, 1., 5., .2))
        for args in [(False, math.nan, 200., .2), (False, 1., math.inf, .2),
                     (False, 1., 200., math.nan), (False, -1., 200., .2),
                     (False, 1., 0., .2), (False, 1., 200., 0.)]:
            self.assertTrue(p(*args))

    def test_policy_exertion_never_bypasses_native_permission_or_owns_client_state(self):
        p = self.p["MayExert"]
        valid = [True, True, True, False, 50., 25.]
        self.assertTrue(p(*valid))
        for index, value in [(0, False), (1, False), (2, False), (3, True),
                             (4, 0.), (4, math.nan), (4, math.inf),
                             (5, 51.), (5, -1.), (5, math.nan), (5, math.inf)]:
            args = valid.copy()
            args[index] = value
            self.assertFalse(p(*args))

    def test_exhaustion_fraction_uses_current_capacity_and_remains_normalized(self):
        p = self.p["ExhaustionFraction"]
        self.assertEqual(1., p(0., 200.))
        self.assertEqual(.75, p(50., 200.))
        self.assertEqual(0., p(500., 200.))
        for args in [(math.nan, 200.), (1., math.inf), (-1., 200.), (1., 0.)]:
            self.assertEqual(-1., p(*args))

    def test_repeated_synthetic_exertion_and_recovery_never_escape_capacity(self):
        units = 200.
        for i in range(2000):
            capacity = self.p["CapacityUnits"]((i % 100) * 1000., 200., 5., 6000., 1.75)
            self.step[2:7] = units, capacity, .25, (-4. if i % 2 else 5.), 0.
            units = self.p["StepUnits"](*self.step)
            self.assertTrue(math.isfinite(units))
            self.assertGreaterEqual(units, 0.)
            self.assertLessEqual(units, capacity)


if __name__ == "__main__":
    unittest.main()
