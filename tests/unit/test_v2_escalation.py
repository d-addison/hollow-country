"""Small authored-policy smoke checks with synthetic days/heat, never DayZ evidence."""
import math
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_horde_stimulus import compile_method
from tests.unit.test_alert_chain import Array, actor, chain

WORLD = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts/4_World"


class V2EscalationSmoke(unittest.TestCase):
    def test_escalation_curves_are_monotone_capped_inputs_only(self):
        scope = {"Math": NS(Clamp=lambda v, lo, hi: max(lo, min(hi, v)))}
        curve = compile_method("../World/HCEscalationClock.c", "static float Curve(",
                               "day, week, fortnight, cap", scope)
        scope["HCEscalationClock"] = NS(Curve=lambda *a: curve(None, *a))
        pressure = compile_method("../World/HCEscalationClock.c", "static float PressureAtDay(",
                                  "axis, day", scope)
        for axis in ("infected", "raiders", "scarcity"):
            values = [pressure(None, axis, day) for day in range(-1, 100)]
            self.assertEqual(sorted(values), values)
            self.assertTrue(all(0 <= value <= 1 for value in values))
            self.assertEqual(0, values[0])
            self.assertEqual(1, values[-1])
        self.assertEqual(0, pressure(None, "unknown", 99))
        source = (WORLD / "World/HCEscalationClock.c").read_text()
        self.assertNotRegex(source, r"\b(?:CreateObject|SetNominal|SetEconomy|GetCEApi)\s*\(")
        self.assertIn('HCV2Admission.Line("Escalation", true, "none", true)', source)

    def test_memory_fades_in_three_days_and_scales_existing_cohort_within_caps(self):
        scope = {"Math": NS(Clamp=lambda v, lo, hi: max(lo, min(hi, v)),
                            Min=min, Max=max, Round=lambda v: math.floor(v + .5))}
        decay = compile_method("HCInfectedMemory.c", "static float Decayed(",
                               "heat, elapsed", scope)
        size = compile_method("HCInfectedMemory.c", "static int CohortSizeAtHeat(",
                              "heat, available", scope)
        response = compile_method("HCInfectedMemory.c", "static int ResponseLimitAtHeat(", "heat", scope)
        values = [decay(None, 1., elapsed) for elapsed in (0, 60, 86400, 172800, 259200, 345600)]
        self.assertEqual(sorted(values, reverse=True), values)
        self.assertAlmostEqual(2 / 3, values[2])
        self.assertEqual([0, 0], values[-2:])
        self.assertEqual(0, decay(None, 0, 0))
        self.assertEqual(3, size(None, 0, 6))
        self.assertEqual(6, size(None, 1, 6))
        self.assertEqual(4, size(None, 1, 4))
        self.assertTrue(all(3 <= size(None, heat / 10, 6) <= 6 for heat in range(11)))
        self.assertEqual([6, 12], [response(None, heat) for heat in (0, 1)])
        module = (WORLD / "Infected/HCInfectedModule.c").read_text()
        self.assertIn("HCInfectedMemory.CohortSize(anchor, requested)", module)
        self.assertIn("Math.Min(settings.MaxActiveHordes, 2)", module)
        self.assertIn("Math.Min(settings.MaxActiveHordeMembers, 24)", module)
        memory = (WORLD / "Infected/HCInfectedMemory.c").read_text()
        self.assertIn("override void EEFired(int muzzleType, int mode, string ammoType)", memory)
        self.assertIn("override protected void OnExplode()", memory)
        self.assertIn("super.ProcessPending(actors, now, 1)", memory)
        for heat, clear, expected in ((0, True, 6), (1, True, 12), (1, False, 1)):
            context, emitter = chain(geometry=clear), actor()
            actors = Array([emitter] + [actor((3, 0, 0)) for _ in range(13)])
            context.NativeEmission(emitter, 17, 100, 16, len(actors))
            root = context.m_Roots[0]
            wrapped = compile_method("HCInfectedMemory.c", "override int ProcessPending(",
                "actors, now, work", {"GetGame": lambda: NS(IsServer=lambda: True),
                "HCInfectedMemory": NS(Active=lambda: True, ResponseLimit=lambda pos: response(None, heat)),
                "super": NS(ProcessPending=context.ProcessPending)}, ("Expire",))
            self.assertLessEqual(wrapped(context, actors, 100, 32), 32)
            self.assertEqual(expected, root.Recipients.Count())


if __name__ == "__main__":
    unittest.main()
