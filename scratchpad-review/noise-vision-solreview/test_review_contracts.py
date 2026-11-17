"""Offline checks of authored adapters with explicit synthetic native fixtures.

The actual flat Enforce method bodies execute through the repository's existing
translator. No assertion establishes engine scheduling, AI response or rendering.
"""
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.unit.test_crafting_completion import execute_flat
from tests.unit.test_v1_native_noise_vision import VISION, NOISE, authored_class


class AdapterContracts(unittest.TestCase):
    def vision(self, server=True, admitted=True, player=True, game_present=True):
        calls = []
        applicant = object()
        target = object() if player else None

        def native(value):
            self.assertIs(applicant, value)
            calls.append("native")
            return 0.9

        def admission():
            calls.append("admission")
            return admitted

        def factor(value):
            self.assertIs(target, value)
            calls.append("factor")
            return 0.75

        game = NS(IsServer=lambda: server) if game_present else None
        method = execute_flat(str(VISION), "GetMaxVisionRangeModifier", "pApplicant", {
            "super": NS(GetMaxVisionRangeModifier=native), "GetGame": lambda: game,
            "HCInfectedVisionQualification": NS(Admitted=admission),
            "m_HCVisionPlayer": target, "HCInfectedVision": NS(PlayerFactor=factor)})
        return method(applicant), calls

    def test_client_keeps_exact_native_without_admission_or_factor(self):
        self.assertEqual((0.9, ["native"]), self.vision(server=False))

    def test_closed_server_gate_keeps_exact_native_without_factor(self):
        self.assertEqual((0.9, ["native", "admission"]), self.vision(admitted=False))

    def test_missing_game_or_player_keeps_exact_native(self):
        self.assertEqual((0.9, ["native"]), self.vision(game_present=False))
        self.assertEqual((0.9, ["native", "admission"]), self.vision(player=False))

    def test_admitted_server_multiplies_once_with_the_captured_target(self):
        value, calls = self.vision()
        self.assertAlmostEqual(0.675, value)
        self.assertEqual(["native", "admission", "factor"], calls)

    def emitter(self, server=True, alive=True, game_present=True, noise_present=True):
        calls = []
        player = NS(IsAlive=lambda: alive, GetPosition=lambda: "synthetic-player-position")

        class Params:
            def LoadFromPath(self, path):
                calls.append(("load", path))

        def add(source, pos, params):
            self.assertIs(player, source)
            self.assertEqual("synthetic-player-position", pos)
            self.assertIsInstance(params, Params)
            calls.append(("emit",))

        noise = NS(AddNoisePos=add) if noise_present else None
        game = NS(IsServer=lambda: server, GetNoiseSystem=lambda: noise) if game_present else None
        emit = execute_flat(str(NOISE), "Emit", "player", {
            # The existing translator appends () to `new Type` even when the
            # source already has (). Its translated NoiseParams()() needs a
            # factory returning the fixture type. This is a harness adaptation.
            "GetGame": lambda: game, "NoiseParams": lambda: Params,
            "NOISE_PATH": "CfgVehicles SurvivorBase NoiseActionDefault"})
        return emit, player, calls

    def test_noise_server_emits_once_using_config_and_actor_position(self):
        emit, player, calls = self.emitter()
        emit(player)
        self.assertEqual([("load", "CfgVehicles SurvivorBase NoiseActionDefault"), ("emit",)], calls)

    def test_noise_client_dead_null_and_missing_system_are_silent(self):
        for args in ({"server": False}, {"alive": False}, {"game_present": False}, {"noise_present": False}):
            emit, player, calls = self.emitter(**args)
            emit(player)
            self.assertEqual([], calls, args)
        emit, _, calls = self.emitter()
        emit(None)
        self.assertEqual([], calls)

    def test_phase_transition_is_once_and_refusal_failure_repeat_cancel_are_silent(self):
        policy = authored_class(NOISE, "HCSearchNoisePolicy")
        emitted = []
        phase_of = execute_flat(str(NOISE), "PhaseOf", "action_data", {
            "HCInteriorActionData": NS(Cast=lambda value: value)})
        completed = execute_flat(str(NOISE), "OnCommitted", "action_data,phaseBefore", {
            "HCSearchNoise": NS(PhaseOf=phase_of, Emit=lambda player: emitted.append(player)),
            "HCSearchNoisePolicy": NS(ShouldEmit=policy["ShouldEmit"])})
        target = object()
        action = NS(Site=NS(Phase=0), m_Player=target)
        # Explicit synthetic transitions; CommitSearch itself is inspected, not simulated as engine proof.
        for before, after in ((0, 0), (0, 1), (1, 1), (1, 2), (0, 3), (2, 2), (3, 3)):
            action.Site.Phase = after
            completed(action, before)
        self.assertEqual([], emitted)
        action.Site.Phase = 2
        completed(action, 0)
        completed(action, 2)
        self.assertEqual([target], emitted)
        action.Site = None
        completed(action, 0)
        completed(None, 0)
        self.assertEqual([target], emitted)

    def test_nonfinite_unset_and_extreme_inputs_are_bounded_before_native_product(self):
        policy = authored_class(VISION, "HCInfectedVisionPolicy")
        values = (float("nan"), float("inf"), -float("inf"), -1000001, -1, 0, 0.49,
                  0.5, 0.6, 1, 1.3, 2, 23.999, 24, 1000000, 1000001)
        for coef in values:
            for hour in values:
                for lit in values:
                    factor = policy["Factor"](coef, hour, lit)
                    self.assertTrue(0.6 - 1e-6 <= factor <= 1.3 + 1e-6, (coef, hour, lit))
                    # Native's finite speed/stance constants give .225 <= result <= 1.25.
                    self.assertGreaterEqual(0.225 * factor, 0.135 - 1e-6)
                    self.assertLessEqual(1.25 * factor, 1.625 + 1e-6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
