"""Production fuel siphon (#53): authored policy execution and source contracts.

Offline only: this proves neither Enforce compilation nor native car/container
behavior. Native acceptance is a local-server run with a real client.
"""
from pathlib import Path
import math
import re
import unittest

try:
    from .test_fuel_transfer import authored_policy
except ImportError:
    from test_fuel_transfer import authored_policy

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

    def test_credit_is_what_the_tank_actually_lost_capped_by_the_step(self):
        credit = self.p["SiphonCreditMl"]
        self.assertEqual(250, credit(250.0, 10.0, 9.75))
        self.assertAlmostEqual(100, credit(250.0, 0.1, 0.0), places=3)
        self.assertEqual(250, credit(250.0, 10.0, 9.0))   # extra leak never credited
        for args in ((250.0, 10.0, 10.0), (250.0, 10.0, 11.0), (0.0, 10.0, 9.0),
                     (250.0, math.nan, 9.0)):
            self.assertEqual(0, credit(*args), args)


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

    def test_server_gate_follows_the_crafting_preference(self):
        gate = method(self.text, "ServerEnabled")
        self.assertIn("HCServer.Get()", gate)
        self.assertIn("IsStarted()", gate)
        self.assertIn("EnableCrafting", gate)
        cond = method(self.text, "ActionCondition")
        self.assertIn("IsServer()", cond)
        self.assertIn("ServerEnabled()", cond)
        self.assertIn("ServerEnabled()", method(self.text, "ActionConditionContinue"))

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
        order = [calc.index(n) for n in ("Liquid.CanFillContainer", ".Leak(CarFluid.FUEL",
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
