"""Production fuel siphon (#53): authored policy execution and source contracts.

Offline only: this proves neither Enforce compilation nor native car/container
behavior. Native acceptance is a local-server run with a real client.
"""
from pathlib import Path
import math
import re
import unittest

from fractions import Fraction
import random

try:
    from tests.legacy.test_fuel_transfer import authored_policy, f32
except ImportError:
    from tests.legacy.test_fuel_transfer import authored_policy, f32

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "mods/HollowCountry/scripts/4_World/Actions/HCFuelSiphon.c"
DIAGNOSTIC = ROOT / "mods/HollowCountry/scripts/4_World/Actions/HCActionSiphonFuel.c"


def code(path):
    return re.sub(r"//[^\n]*", "", path.read_text())


def method(text, name):
    start = re.search(r"\b" + name + r"\s*\([^)]*\)\s*\{", text)
    if not start:
        raise AssertionError("missing method " + name)
    depth, index = 0, start.end() - 1
    for index in range(start.end() - 1, len(text)):
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth == 0:
            break
    return text[start.end():index]


class SiphonPolicyTests(unittest.TestCase):
    def setUp(self):
        self.p = authored_policy()

    def test_session_is_bounded_by_real_tank_fuel_and_vessel_space(self):
        session = self.p["SiphonSessionMl"]
        self.assertEqual(5000, session(5.0, 0.0, 20000.0))      # tank limits
        self.assertEqual(3000, session(50.0, 2000.0, 5000.0))   # space limits
        for args in ((0.0, 0.0, 5000.0), (5.0, 5000.0, 5000.0), (5.0, 6000.0, 5000.0),
                     (-1.0, 0.0, 5000.0), (math.inf, 0.0, 5000.0), (math.nan, 0.0, 5000.0)):
            self.assertEqual(0, session(*args), args)

    def test_step_never_exceeds_tank_space_or_remaining_session(self):
        step = self.p["SiphonStepMl"]
        self.assertEqual(250, step(10.0, 0.0, 5000.0, 250.0, 5000.0))
        self.assertEqual(100, step(0.1, 0.0, 5000.0, 250.0, 5000.0))
        self.assertEqual(40, step(10.0, 4960.0, 5000.0, 250.0, 5000.0))
        self.assertEqual(30, step(10.0, 0.0, 5000.0, 250.0, 30.0))
        for args in ((0.0, 0.0, 5000.0, 250.0, 5000.0), (10.0, 0.0, 5000.0, 0.0, 5000.0),
                     (10.0, 0.0, 5000.0, 250.0, 0.0), (10.0, 0.0, 5000.0, math.nan, 5000.0)):
            self.assertEqual(0, step(*args), args)

    def test_credit_is_below_what_the_tank_actually_lost_capped_by_the_step(self):
        credit = self.p["SiphonCreditMl"]
        self.assertEqual(249, credit(250.0, 10.0, 9.75, 0.0, 20000.0))   # 1 ml spill per step
        self.assertAlmostEqual(99, credit(250.0, 0.1, 0.0, 0.0, 20000.0), places=3)
        self.assertEqual(249, credit(250.0, 10.0, 9.0, 0.0, 20000.0))    # extra leak never credited
        self.assertEqual(40, credit(250.0, 10.0, 9.75, 19960.0, 20000.0))  # native clamp is a loss
        for args in ((250.0, 10.0, 10.0, 0.0, 20000.0), (250.0, 10.0, 11.0, 0.0, 20000.0),
                     (0.0, 10.0, 9.0, 0.0, 20000.0), (250.0, math.nan, 9.0, 0.0, 20000.0),
                     (250.0, 10.0, 9.9995, 0.0, 20000.0),              # under one ml lost
                     (250.0, 10.0, 9.75, 20000.0, 20000.0),            # full vessel
                     (250.0, 5000.0, 4999.75, 0.0, 20000.0),           # tank outside bound
                     (250.0, 10.0, 9.75, 0.0, 2.0e7),                  # vessel outside bound
                     (math.inf, 10.0, 9.75, 0.0, 20000.0)):
            self.assertEqual(0, credit(*args), args)

    def test_review_counterexamples_never_credit_more_than_the_exact_loss(self):
        credit = self.p["SiphonCreditMl"]
        c1 = credit(700.0, f32(0.7), 0.0, 0.0, 20000.0)
        self.assertLess(Fraction(c1), (Fraction(f32(0.7)) - 0) * 1000)
        vessel = 1023.9999389648438
        c2 = credit(250.0, 10.0, 9.75, vessel, 20000.0)
        self.assertLess(Fraction(f32(vessel + c2)) - Fraction(vessel), Fraction(250))

    def test_binary32_grid_destination_gain_stays_below_exact_tank_loss(self):
        credit, receipt = self.p["SiphonCreditMl"], self.p["SiphonReceiptOk"]
        rng = random.Random(53)
        for _ in range(4000):
            before = f32(rng.uniform(0.001, 4096.0))
            after = f32(max(0.0, before - rng.uniform(0.0, 0.6)))
            step = f32(rng.choice((rng.uniform(0.0, 600.0), 250.0, 1.0, 1.5)))
            vessel = f32(rng.uniform(0.0, 20000.0))
            vmax = f32(rng.choice((20000.0, 5000.0, 1000.0, vessel + rng.uniform(0.0, 3.0))))
            c = credit(step, before, after, vessel, vmax)
            exact_loss = (Fraction(before) - Fraction(after)) * 1000
            self.assertGreaterEqual(c, 0)
            if c:
                gained_after = min(f32(vessel + c), vmax)  # SetQuantity clamps to max
                gain = Fraction(gained_after) - Fraction(vessel)
                self.assertLess(gain, exact_loss, (step, before, after, vessel, vmax))
                self.assertLessEqual(c, step)
                self.assertTrue(receipt(c, vessel, gained_after))

    def test_receipt_refuses_a_destination_gain_above_the_credit_or_none(self):
        receipt = self.p["SiphonReceiptOk"]
        self.assertTrue(receipt(249.0, 1000.0, 1249.0))
        self.assertTrue(receipt(249.0, 1000.0, 1100.0))   # clamp/partial is a loss, not a gain
        for args in ((249.0, 1000.0, 1000.0), (249.0, 1000.0, 999.0), (249.0, 1000.0, 1249.6),
                     (0.0, 1000.0, 1001.0), (249.0, math.nan, 1249.0), (249.0, 1000.0, math.inf)):
            self.assertFalse(receipt(*args), args)


class SiphonActionContractTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ACTION.is_file(), "missing production siphon action")
        self.text = code(ACTION)

    def test_action_is_registered_on_held_liquid_containers_like_native_refuel(self):
        # Native ActionFillFuel is registered in Bottle_Base.SetActions (item action map).
        self.assertRegex(self.text, r"class HCActionSiphonFuelFromCar extends ActionContinuousBase")
        self.assertRegex(self.text, r"modded class ActionConstructor[\s\S]*actions\.Insert\(HCActionSiphonFuelFromCar\)")
        self.assertRegex(self.text, r"modded class Bottle_Base[\s\S]*super\.SetActions\(\);[\s\S]*AddAction\(HCActionSiphonFuelFromCar\)")
        self.assertNotIn("modded class PlayerBase", self.text)
        self.assertNotIn("HCActionSiphonFuel)", self.text)
        self.assertNotIn("HCActionSiphonFuel,", self.text)
        self.assertNotRegex(code(DIAGNOSTIC), r"actions\.Insert|AddAction\(")

    def test_server_gate_is_crafting_lifecycle_and_fuel_admission_open_unless_disabled(self):
        gate = method(self.text, "ServerEnabled")
        self.assertIn("IsServer()", gate)
        self.assertIn("HCCraftingGate.CanPreviewOrCraft()", gate)
        self.assertIn("HCFuelSiphonQualification.Admitted()", gate)
        qualified = method(self.text, "Qualified")
        self.assertRegex(qualified, r"^\s*return false;\s*$")
        admitted = method(self.text, "Admitted")
        self.assertIn("Qualified()", admitted)
        self.assertIn("LocalAcceptanceOptIn()", admitted)
        self.assertIn('!FileExist("$profile:HollowCountry/acceptance/fuel_siphon.disable")', self.text)
        self.assertNotIn("fuel_siphon.enable", self.text)
        self.assertIn("EXPERIMENTAL", admitted)
        self.assertIn("s_Checked", admitted)          # one file probe per server process
        cond = method(self.text, "ActionCondition")
        self.assertIn("IsServer()", cond)
        self.assertIn("ServerEnabled()", cond)
        self.assertIn("ActionCondition(action_data.m_Player, action_data.m_Target, action_data.m_MainItem)",
                      method(self.text, "ActionConditionContinue"))

    def test_every_server_debit_including_cancel_revalidates_gate_and_eligibility(self):
        calc = method(self.text, "CalcAndSetQuantity")
        server = calc[calc.index("IsServer()"):]
        check = server.index("HCFuelSiphon.ServerEnabled()")
        allowed = server.index("HCFuelSiphon.Allowed(action_data.m_Player, action_data.m_Target, vessel)")
        leak = server.index(".Leak(CarFluid.FUEL")
        self.assertLess(check, leak)
        self.assertLess(allowed, leak)
        self.assertLess(calc.index("m_PendingMl = 0;"), calc.index("IsServer()"))  # repeat Cancel is a no-op
        self.assertIn("GetItemInHands() != item", method(self.text, "Allowed"))

    def test_destination_readback_is_checked_after_fill(self):
        calc = method(self.text, "CalcAndSetQuantity")
        fill = calc.index("Liquid.FillContainer")
        self.assertLess(fill, calc.index("SiphonReceiptOk"))
        self.assertIn("SiphonCreditMl(stepMl, beforeLiters, afterLiters, vesselBeforeMl, vessel.GetQuantityMax())", calc)

    def test_eligibility_mirrors_native_refuel_in_reverse(self):
        allowed = method(self.text, "Allowed")
        for needle in ("CarScript.Cast", "IsDamageDestroyed()", "EngineIsOn()", "IsInVehicle()",
                       "GetFluidFraction(CarFluid.FUEL)", "IsLiquidContainer()",
                       "Liquid.CanFillContainer(item, LIQUID_GASOLINE)", "LIQUID_GASOLINE",
                       "GetActionCompNameFuel()", "GetRefillPointPosWS()", "GetActionDistanceFuel()",
                       "GetQuantityMax()"):
            self.assertIn(needle, allowed, needle)

    def test_transfer_checks_destination_before_debit_and_credits_readback(self):
        calc = method(self.text, "CalcAndSetQuantity")
        self.assertIn("IsServer()", calc)
        order = [calc.index(n) for n in ("HCFuelSiphon.Allowed(", ".Leak(CarFluid.FUEL",
                                         "SiphonCreditMl", "Liquid.FillContainer")]
        self.assertEqual(order, sorted(order))
        self.assertIn("SiphonStepMl", calc)
        self.assertNotRegex(self.text, r"\.Fill\(|FillScript\(|LeakAll\(|CreateInInventory|SpawnEntity")

    def test_session_and_interruption_follow_native_component(self):
        setup = method(self.text, "Setup")
        self.assertIn("SiphonSessionMl", setup)
        self.assertIn("GetLiquidThroughputCoef()", setup)
        self.assertIn("UAQuantityConsumed.FUEL", self.text)
        self.assertIn("CalcAndSetQuantity(action_data)", method(self.text, "Cancel"))
        self.assertRegex(self.text, r"class CAContinuousHCSiphonFuel extends CAContinuousBase")


if __name__ == "__main__":
    unittest.main()
