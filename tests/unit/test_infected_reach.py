"""#137 infected anti-cheese reach smoke.

Executes the authored pure Reach policy through the existing event translator
with explicit synthetic numbers. It proves only the authored decision rules:
offline tests never establish DayZ behavior (native attack animation, vault
landing, vehicle damage and controller heading remain runtime-pending).

RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_reach -v
     -> FAILED (failures=5), each: AssertionError: missing authored #137 reach
        policy mods/HollowCountry/scripts/4_World/Infected/Reach/HCInfectedReachPolicy.c
GREEN: same command.
"""
from tests.unit.test_c1_infectedcfg import tuning_fixture
import math
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
REACH = ROOT / "mods/HollowCountry/scripts/4_World/Infected/Reach"
POLICY = REACH / "HCInfectedReachPolicy.c"


def policy():
    if not POLICY.exists():
        raise AssertionError("missing authored #137 reach policy " + str(POLICY.relative_to(ROOT)))
    text = POLICY.read_text()
    owner = SimpleNamespace()
    for name, value in re.findall(r'static const (?:bool|string) (\w+) = ("[^"]*"|true|false);', text):
        setattr(owner, name, value == 'true' if value in ('true', 'false') else value[1:-1])
    env = dict(HCInfectedTuning=tuning_fixture(), HCInfectedReachPolicy=owner, len=len, str=str,
               Math=SimpleNamespace(AbsFloat=abs, Min=min, Max=max))
    for name in re.findall(r"\bstatic (?:bool|int|float) (\w+)\(", text):
        setattr(owner, name, translate(text, name, env, owner="HCInfectedReachPolicy"))
    return owner


class InfectedReachSmoke(unittest.TestCase):
    def test_elevated_strike_needs_band_reach_line_and_vanilla_failure(self):
        p = policy()
        # Player on a ~1.5 m car roof, 1.2 m horizontal: vanilla's 3D distance
        # (~1.9 m) exceeds the 1.7 m up attack; horizontal reach admits it.
        self.assertTrue(p.MayStrike(1.5, 1.2, 1.7, True, True, True, False))
        self.assertFalse(p.MayStrike(1.5, 1.2, 1.7, False, True, True, False), "blocked line hits through walls")
        self.assertFalse(p.MayStrike(1.5, 1.2, 1.7, True, False, True, False), "stale line verdict")
        self.assertFalse(p.MayStrike(1.5, 1.2, 1.7, True, True, False, False), "cooldown ignored")
        self.assertFalse(p.MayStrike(1.5, 1.2, 1.7, True, True, True, True), "vanilla attack keeps precedence")
        self.assertFalse(p.MayStrike(0.5, 1.2, 1.7, True, True, True, False), "flat ground is vanilla's job")
        self.assertFalse(p.MayStrike(2.6, 0.4, 1.7, True, True, True, False), "a roof above 2.3 m stays out of reach")
        self.assertFalse(p.MayStrike(1.5, 1.8, 1.7, True, True, True, False), "horizontal reach exceeded")
        # The first ray contact must be the target or the surface just under it.
        self.assertTrue(p.LineClear(False, False, 0.0, 2.0))
        self.assertTrue(p.LineClear(True, True, 0.6, 2.0))
        self.assertTrue(p.LineClear(True, False, 1.85, 2.0))
        self.assertFalse(p.LineClear(True, False, 0.6, 2.0), "wall between infected and shin")

    def test_vault_band_and_experiment_retires_without_landings(self):
        p = policy()
        self.assertEqual([p.VaultType(h) for h in (0.5, 1.0, 1.4, 1.9, 2.2)], [-1, 1, 2, 3, -1])
        self.assertTrue(p.MayVault(1.4, 1.2, 10.0, True, 20.0, 15.0, 0, False))
        self.assertFalse(p.MayVault(1.4, 1.2, 40.0, True, 20.0, 15.0, 0, False), "not facing the platform")
        self.assertFalse(p.MayVault(1.4, 1.2, 10.0, False, 20.0, 15.0, 0, False), "no platform ahead")
        self.assertFalse(p.MayVault(1.4, 1.2, 10.0, True, 10.0, 15.0, 0, False), "per-infected retry spacing")
        self.assertFalse(p.MayVault(1.4, 1.2, 10.0, True, 20.0, 15.0, 4, False), "concurrent vault cap")
        self.assertFalse(p.MayVault(1.4, 1.2, 10.0, True, 20.0, 15.0, 0, True), "experiment retired")
        self.assertTrue(p.VaultLanded(10.0, 10.7))
        self.assertFalse(p.VaultLanded(10.0, 10.2))
        self.assertTrue(p.VaultRetired(6, 0))
        self.assertFalse(p.VaultRetired(6, 1))
        self.assertFalse(p.VaultRetired(5, 0))

    def test_unreachable_backoff_cycles_and_releases(self):
        p = policy()
        self.assertFalse(p.Unreachable(1.5, 1.0, True, 5.0, 8.0), "needs six seconds without a reach hit")
        self.assertFalse(p.Unreachable(1.5, 1.0, False, 9.0, 9.0), "a reachable target is not waited out")
        self.assertTrue(p.Unreachable(1.5, 1.0, True, 6.0, 6.0))
        self.assertFalse(p.Unreachable(1.5, 7.0, True, 9.0, 9.0), "only near targets")
        NONE, RETREAT, CIRCLE, WAIT = 0, 1, 2, 3
        self.assertEqual(p.NextPhase(RETREAT, 1.0, 1.5), RETREAT)
        self.assertEqual(p.NextPhase(RETREAT, 1.0, 3.1), CIRCLE)
        self.assertEqual(p.NextPhase(RETREAT, 3.1, 1.5), CIRCLE, "retreat is time-bounded")
        self.assertEqual(p.NextPhase(CIRCLE, 2.1, 3.0), WAIT)
        self.assertEqual(p.NextPhase(WAIT, 3.1, 3.0), NONE)
        self.assertEqual(p.NextPhase(CIRCLE, 1.0, 4.5), WAIT, "never drifts past 4 m")
        self.assertEqual(p.PhaseSpeed(RETREAT), 1)
        self.assertEqual(p.PhaseSpeed(WAIT), 0)
        self.assertAlmostEqual(p.PhaseYaw(RETREAT, 10.0, 1), -170.0)
        self.assertAlmostEqual(p.PhaseYaw(CIRCLE, 170.0, 1), -100.0)
        self.assertAlmostEqual(p.PhaseYaw(WAIT, 10.0, -1), 10.0)

    def test_batter_only_occupied_or_unreachable_topped_vehicle(self):
        p = policy()
        self.assertTrue(p.MayBatter(True, False, False, 1.2, 5.0, 4.0))
        self.assertTrue(p.MayBatter(False, True, False, 1.2, 5.0, 4.0))
        self.assertFalse(p.MayBatter(False, True, True, 1.2, 5.0, 4.0), "reachable legs come first")
        self.assertFalse(p.MayBatter(False, False, False, 1.2, 5.0, 4.0), "empty vehicles are not battered")
        self.assertFalse(p.MayBatter(True, False, False, 2.2, 5.0, 4.0), "not adjacent")
        self.assertFalse(p.MayBatter(True, False, False, 1.2, 3.0, 4.0), "per-vehicle hit spacing")
        self.assertTrue(p.Keep(True, True, True, 3.0, 5.0, 9.0))
        self.assertFalse(p.Keep(True, True, False, 3.0, 5.0, 9.0), "alerted is not chase/fight")
        self.assertFalse(p.Keep(True, True, True, 9.0, 5.0, 9.0), "disengaged past 8 m")
        self.assertFalse(p.Keep(True, False, True, 3.0, 5.0, 9.0), "target changed")
        self.assertFalse(p.Keep(True, True, True, 3.0, 10.0, 9.0), "expired")

    def test_reach_sources_self_register_without_position_writes(self):
        policy()
        text = "\n".join(p.read_text() for p in sorted(REACH.glob("*.c")))
        self.assertIn("Register(new HCInfectedReachModule)", text)
        self.assertIn('HCV2Admission.Line("InfectedReach"', text)
        self.assertIn("settings.EnableInfected", text)
        for banned in ("SetPosition(", "SetOrigin(", "SetTransform(", "PostPhys_SetPosition", "AddNoise"):
            self.assertNotIn(banned, text, "Reach must not move infected or invent noise")


if __name__ == "__main__":
    unittest.main()
