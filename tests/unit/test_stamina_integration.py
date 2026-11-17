"""Synthetic execution of authored hooks; no native/network acceptance."""
import math
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest
try:
    from .test_crafting_completion import body, execute_flat
    from .test_stamina_policy import policy_functions
except ImportError:
    from test_crafting_completion import body, execute_flat
    from test_stamina_policy import policy_functions

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "mods/HollowCountry/scripts/4_World/Survival/HCStaminaIntegration.c"
SETTINGS = ROOT / "mods/HollowCountry/scripts/3_Game/Survival/HCStaminaSettings.c"

def hook(name, params, gate):
    lines, indent = [f"def actual(self,{params}):"], 1
    for token in re.split(r"([{};])", re.sub(r"//[^\n]*", "", body(str(HOOK), name))):
        token = token.strip()
        if not token or token == ";": continue
        if token == "{": indent += 1; continue
        if token == "}": indent -= 1; continue
        token = re.sub(r"\b(?:bool|float)\s+", "", token)
        token = re.sub(r"\b(?:m_\w+|s_Settings)\b", lambda m: "self." + m[0], token)
        token = token.replace("new HCStaminaSettings", "HCStaminaSettings()")
        token = token.replace("super.", "self.native.")
        token = token.replace("HCStaminaIntegration.", "gate.")
        token = token.replace("HCStaminaPolicy.", "policy.")
        token = token.replace("CfgGameplayHandler.", "cfg.")
        token = token.replace("&&", " and ").replace("||", " or ")
        token = re.sub(r"!(?!=)", "not ", token)
        token = re.sub(r"\btrue\b", "True", token)
        token = re.sub(r"\bfalse\b", "False", token)
        if token.startswith("if ("): token = "if " + token[4:-1] + ":"
        elif token == "else": token += ":"
        lines.append("    " * indent + token)
    ns = dict(gate=gate, policy=NS(**policy_functions()), Math=NS(Max=max),
              HCStaminaSettings=lambda: NS(Enabled=False, ContinuousExertionScale=1., RecoveryScale=1.),
              DayZPlayerInstanceType=NS(INSTANCETYPE_CLIENT=1),
              cfg=NS(GetStaminaMax=lambda: 200., GetStaminaMinCap=lambda: 5.,
                     GetStaminaWeightLimitThreshold=lambda: 6000.,
                     GetStaminaKgToStaminaPercentPenalty=lambda: 1.75))
    exec(compile("\n".join(lines), str(HOOK), "exec"), ns)
    return ns["actual"]

class StaminaIntegrationTests(unittest.TestCase):
    def run_step(self, enabled=True, dt=.5, authority=True, instance=0, **changes):
        gate = NS(Enabled=lambda: enabled, ExertionScale=lambda: .5,
                  RecoveryScale=lambda: .5)
        h = NS(m_Player=NS(GetInstanceType=lambda: instance), m_Stamina=100.,
               m_StaminaCap=200., m_StaminaDelta=-4., m_StaminaDepletion=25.,
               m_StaminaDepletionMultiplier=2., m_StaminaRecoveryMultiplier=2.,
               m_IsInCooldown=False)
        h.__dict__.update(changes)
        calls = []
        h.native = NS(ProcessStaminaChanges=lambda *args: calls.append(
            (h.m_Stamina, h.m_StaminaDelta, h.m_StaminaDepletion, args)))
        hook("ProcessStaminaChanges", "deltaT,isServerOrSingleplayer", gate)(h, dt, authority)
        return h, calls

    def test_replacement_spends_native_event_and_continuous_cost_once(self):
        h, calls = self.run_step()
        self.assertEqual([(100., -2., 25., (.5, True))], calls)
        self.assertEqual((-4., 25.), (h.m_StaminaDelta, h.m_StaminaDepletion))

    def test_disabled_long_frame_and_remote_use_native_inputs(self):
        for kwargs in (dict(enabled=False), dict(dt=1.1), dict(authority=False),
                       dict(dt=math.nan), dict(m_StaminaDepletion=math.nan),
                       dict(m_StaminaDepletionMultiplier=math.inf)):
            h, calls = self.run_step(**kwargs)
            self.assertEqual(100., calls[0][0])
            self.assertEqual(-4., calls[0][1])
            if not math.isnan(h.m_StaminaDepletion):
                self.assertEqual(h.m_StaminaDepletion, calls[0][2])
            self.assertEqual(1, len(calls))

    def test_prediction_uses_same_proposal_but_no_server_authority(self):
        h, calls = self.run_step(authority=False, instance=1)
        self.assertEqual([(100., -2., 25., (.5, False))], calls)

    def test_native_cooldown_event_and_zero_recovery_factor_are_preserved(self):
        for changes, rate in ((dict(), 2.5),
                              (dict(m_IsInCooldown=True, m_StaminaDelta=0.), 0.),
                              (dict(m_StaminaDepletion=10.), 2.5),
                              (dict(m_StaminaRecoveryMultiplier=0.), 2.5)):
            inputs = dict(m_Stamina=50., m_StaminaDelta=5., m_StaminaDepletion=0.)
            inputs.update(changes)
            h, calls = self.run_step(**inputs)
            self.assertEqual([(50., rate, inputs["m_StaminaDepletion"],
                               (.5, True))], calls)
            self.assertEqual(changes.get("m_IsInCooldown", False), h.m_IsInCooldown)
            self.assertEqual(changes.get("m_StaminaRecoveryMultiplier", 2.),
                             h.m_StaminaRecoveryMultiplier)

    def test_capacity_uses_native_configuration_and_cached_weight(self):
        calls = []
        h = NS(m_PlayerLoad=7000., m_StaminaCap=100.,
               native=NS(RecalculateStaminaCap=lambda: calls.append(True)))
        fn = hook("RecalculateStaminaCap", "", NS(Enabled=lambda: True))
        fn(h)
        self.assertEqual((198.25, 198.25), (h.m_StaminaCap, h.m_StaminaCapSynced))
        h.m_PlayerLoad = math.nan
        fn(h)
        self.assertEqual([True], calls)

    def test_installer_snapshots_once_and_rejects_invalid_configuration(self):
        runtime = NS(s_Settings=None)
        install = hook("InstallTrusted", "settings", None)
        self.assertFalse(install(runtime, None))
        config = NS(Enabled=True, ContinuousExertionScale=2., RecoveryScale=1.,
                    Validate=lambda: False)
        self.assertFalse(install(runtime, config))
        config.Validate = lambda: True
        self.assertTrue(install(runtime, config))
        config.ContinuousExertionScale = 4.
        self.assertEqual(2., runtime.s_Settings.ContinuousExertionScale)
        self.assertFalse(install(runtime, config))

    def test_settings_default_off_and_reject_invalid_scales(self):
        self.assertIn("bool Enabled = false;", SETTINGS.read_text())
        for scale in (0., 5.01, math.nan, math.inf, -math.inf):
            fields = dict(SchemaVersion=1, ContinuousExertionScale=scale, RecoveryScale=1.)
            self.assertFalse(execute_flat(str(SETTINGS), "Validate", "", fields)())
        for version in (0, 2):
            self.assertFalse(execute_flat(str(SETTINGS), "Validate", "", dict(
                SchemaVersion=version, ContinuousExertionScale=1., RecoveryScale=1.))())
        self.assertTrue(execute_flat(str(SETTINGS), "Validate", "", dict(
            SchemaVersion=1, ContinuousExertionScale=1., RecoveryScale=1.))())


    def test_recovery_and_event_reach_native_step_together(self):
        h, calls = self.run_step(m_Stamina=98., m_StaminaCap=100.,
                                 m_StaminaDelta=8., m_StaminaDepletion=10.)
        self.assertEqual([(98., 4., 10., (.5, True))], calls)

    def test_event_subtraction_precedes_capacity_clamp(self):
        h, calls = self.run_step(m_Stamina=100.005, m_StaminaCap=100.,
                                 m_StaminaDelta=0., m_StaminaDepletion=10.)
        self.assertEqual([(100.005, 0., 10., (.5, True))], calls)

    def test_positive_recovery_retains_native_cap_snap(self):
        h, calls = self.run_step(m_Stamina=99.995, m_StaminaCap=100.,
                                 m_StaminaDelta=.001, m_StaminaDepletion=0.)
        self.assertEqual([(99.995, .0005, 0., (.5, True))], calls)

if __name__ == "__main__":
    unittest.main()
