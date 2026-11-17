"""Deliberately failing review regressions. Synthetic binary32, no native evidence."""
from pathlib import Path
from fractions import Fraction
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.unit.test_fuel_transfer import authored_policy, f32


class ReviewConservationTests(unittest.TestCase):
    def test_credit_does_not_round_above_observed_loss(self):
        before, after = f32(0.7), f32(0.0)
        credit = authored_policy()["SiphonCreditMl"](700.0, before, after)
        exact_loss = (Fraction(before) - Fraction(after)) * 1000
        print("credit=", credit, "exact observed loss ml=", float(exact_loss))
        self.assertLessEqual(Fraction(credit), exact_loss)

    def test_destination_gain_does_not_round_above_credit(self):
        before, after = f32(10.0), f32(9.75)
        vessel_before = f32(1024.0 - 2**-14)
        policy = authored_policy()
        step = policy["SiphonStepMl"](before, vessel_before, 20000.0, 250.0, 5000.0)
        credit = policy["SiphonCreditMl"](step, before, after)
        # Native Liquid.FillContainer -> ItemBase.AddQuantity ->
        # SetQuantity(GetQuantity() + value); this explicitly models only that sum.
        vessel_after = f32(vessel_before + credit)
        gain = Fraction(vessel_after) - Fraction(vessel_before)
        exact_loss = (Fraction(before) - Fraction(after)) * 1000
        print("vessel before=", vessel_before, "after=", vessel_after,
              "gain ml=", float(gain), "tank loss ml=", float(exact_loss))
        self.assertLessEqual(gain, exact_loss)


if __name__ == "__main__":
    unittest.main(verbosity=2)
