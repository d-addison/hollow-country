"""#53 synthetic tests execute authored Enforce; no native/atomicity evidence.

Installed 1_Core/proto/EnConvert.c:112 declares float.MAX = FLT_MAX.
That source declaration is verified; runtime behavior remains untested.
"""
import ast
import itertools
import math
from pathlib import Path
import re
import struct
import unittest

try:
    from tests.legacy.test_crafting_completion import body
except ImportError:
    from tests.legacy.test_crafting_completion import body

SOURCE = Path(__file__).resolve().parents[2] / (
    "mods/HollowCountry/scripts/4_World/Crafting/HCFuelTransferPolicy.c"
)
FLOAT_MAX = struct.unpack("!f", bytes.fromhex("7f7fffff"))[0]


def f32(value):
    try:
        return struct.unpack("!f", struct.pack("!f", value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


class Binary32(ast.NodeTransformer):
    """Mechanical scalar rounding, never a second fuel-policy implementation."""
    def visit_BinOp(self, node):
        self.generic_visit(node)
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            raise AssertionError("unsupported arithmetic")
        return ast.copy_location(
            ast.Call(ast.Name("f32", ast.Load()), [node], []), node
        )

    def visit_Constant(self, node):
        if type(node.value) is float:
            return ast.copy_location(ast.Constant(f32(node.value)), node)
        return node


def authored_policy():
    namespace = {"__builtins__": {}, "f32": f32, "FLOAT_MAX": FLOAT_MAX}
    source = re.sub(r"//[^\n]*", "", SOURCE.read_text())
    signatures = re.findall(r"static (bool|float) (\w+)\(([^)]*)\)", source)
    if not signatures or len(signatures) != len(re.findall(r"\bstatic\b", source)):
        raise AssertionError("unsupported method declaration")
    for result_type, name, parameters in signatures:
        args = []
        for parameter in parameters.split(","):
            match = re.fullmatch(r"\s*float (\w+)\s*", parameter)
            if not match:
                raise AssertionError("unsupported parameter: " + parameter)
            args.append(match[1])
        text = re.sub(r"//[^\n]*", "", body(str(SOURCE), name))
        if "{" in text or "}" in text:
            raise AssertionError("unsupported nested control flow")
        lines = [f"def {name}({','.join(args)}):"]
        lines += [f"    {arg} = f32({arg})" for arg in args]
        for statement in text.split(";"):
            statement = statement.strip()
            if not statement:
                continue
            statement = statement.replace("float.MAX", "FLOAT_MAX")
            statement = re.sub(r"^float (\w+) =", r"\1 =", statement)
            statement = statement.replace("&&", " and ").replace("||", " or ")
            statement = re.sub(r"!(?!=)", "not ", statement)
            statement = re.sub(r"\btrue\b", "True", statement)
            statement = re.sub(r"\bfalse\b", "False", statement)
            statement = re.sub(
                r"^if \((.*)\)\s+(return .*|\w+ = .*)$",
                r"if \1: \2", statement, flags=re.S,
            )
            if not re.match(r"^(?:if |return |\w+ = )", statement):
                raise AssertionError("unsupported statement: " + statement)
            if result_type == "float":
                statement = re.sub(r"\breturn (.*)$", r"return f32(\1)", statement)
            lines.append("    " + statement.replace("\n", " "))
        tree = Binary32().visit(ast.parse("\n".join(lines)))
        exec(compile(ast.fix_missing_locations(tree), str(SOURCE), "exec"), namespace)
    return namespace


class FuelTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = authored_policy()

    def plan(self, **changes):
        # Explicit synthetic inputs; no production balance or eligibility implied.
        args = dict(capacityLiters=60., fuelFraction=.5, vesselMl=1000.,
                    vesselMaxMl=20000., rateMlPerSecond=500., elapsedSeconds=.5,
                    maxStepSeconds=1., remainingMl=2000., quantumCapMl=1000.)
        args.update(changes)
        return self.policy["PlanQuantum"](**args)

    def test_given_half_second_then_one_bounded_quantum(self):
        self.assertEqual(250., self.plan())
        cases = (
            ({"capacityLiters": .125, "fuelFraction": 1.}, 125.),
            ({"vesselMl": 19975.}, 25.), ({"remainingMl": 17.}, 17.),
            ({"quantumCapMl": 11.}, 11.), ({"vesselMl": 0.}, 250.),
            ({"elapsedSeconds": 3600.}, 500.),
            ({"elapsedSeconds": 3600., "maxStepSeconds": .25}, 125.),
        )
        for changes, expected in cases:
            self.assertEqual(expected, self.plan(**changes), changes)

    def test_invalid_plan_inputs_fail_closed(self):
        names = ("capacityLiters", "fuelFraction", "vesselMl", "vesselMaxMl",
                 "rateMlPerSecond", "elapsedSeconds", "maxStepSeconds",
                 "remainingMl", "quantumCapMl")
        for name, value in itertools.product(names, (math.nan, math.inf, -math.inf, -1.)):
            with self.subTest(name=name, value=value):
                self.assertEqual(0., self.plan(**{name: value}))
        for name in names:
            if name != "vesselMl":
                self.assertEqual(0., self.plan(**{name: 0.}), name)
        for changes in ({"fuelFraction": 1.01}, {"vesselMl": 20000.},
                        {"vesselMl": 20001.}):
            self.assertEqual(0., self.plan(**changes))

    def test_binary32_overflow_underflow_and_invisible_changes(self):
        for changes in (
            {"capacityLiters": FLOAT_MAX, "fuelFraction": 1.},
            {"rateMlPerSecond": FLOAT_MAX, "maxStepSeconds": 2., "elapsedSeconds": 2.},
            {"rateMlPerSecond": 1e-40, "elapsedSeconds": 1e-20},
            {"capacityLiters": 1e20, "fuelFraction": 1.},
            {"vesselMl": 1e20, "vesselMaxMl": 2e20},
            {"quantumCapMl": 1e-44},
        ):
            self.assertEqual(0., self.plan(**changes), changes)

    def test_synthetic_grid_respects_all_caps(self):
        for capacity, fraction, filled, elapsed, remaining, cap in itertools.product(
                (.125, 60.), (0., .5, 1.), (0., 19975., 20000.),
                (.25, 4.), (0., 17., 2000.), (11., 1000.)):
            amount = self.plan(capacityLiters=capacity, fuelFraction=fraction,
                               vesselMl=filled, elapsedSeconds=elapsed,
                               remainingMl=remaining, quantumCapMl=cap)
            self.assertTrue(math.isfinite(amount))
            self.assertGreaterEqual(amount, 0.)
            for bound in (capacity * fraction * 1000., 20000. - filled,
                          500. * min(elapsed, 1.), remaining, cap):
                self.assertLessEqual(amount, bound)

    def test_credit_requires_measured_debit_and_fresh_space(self):
        credit = self.policy["CreditQuantum"]
        self.assertEqual(500., credit(500., 30., 29.5, 1000., 20000.))
        self.assertEqual(250., credit(500., 30., 29.75, 1000., 20000.))
        self.assertEqual(25., credit(500., 30., 29.5, 19975., 20000.))
        for after in (30., 31., 29.):
            self.assertEqual(0., credit(500., 30., after, 1000., 20000.))
        for quantity, maximum in ((20000., 20000.), (1e20, 2e20)):
            self.assertEqual(0., credit(500., 30., 29.5, quantity, maximum))
        self.assertEqual(0., credit(0., 30., 29.5, 1000., 20000.))

    def test_receipt_conservation_is_not_success_or_atomicity(self):
        receipt = self.policy["ReceiptConserves"]
        self.assertTrue(receipt(30., 29.5, 1000., 1500., 500.))
        self.assertTrue(receipt(30., 29.5, 1000., 1250., 500.))  # permits loss
        for args in ((30., 29.5, 1000., 1501., 501.),
                     (30., 29.5, 1000., 1500., 499.),
                     (30., 30., 1000., 1500., 500.),
                     (30., 29.5, 1000., 1000., 500.),
                     (30., 29.5, 1000., 999., 500.),
                     (30., 31., 1000., 1250., 500.)):
            self.assertFalse(receipt(*args), args)

    def test_readback_checks_reject_invalid_scalars_at_each_position(self):
        for name, baseline in (
            ("CreditQuantum", [500., 30., 29.5, 1000., 20000.]),
            ("ReceiptConserves", [30., 29.5, 1000., 1500., 500.]),
        ):
            for index, value in itertools.product(
                    range(5), (math.nan, math.inf, -math.inf, -1.)):
                args = baseline.copy()
                args[index] = value
                self.assertFalse(self.policy[name](*args), (name, args))

    def test_rounding_cannot_hide_created_fuel(self):
        receipt = self.policy["ReceiptConserves"]
        self.assertFalse(receipt(1., .5, 2**-16, 500. + 2**-15, 500.))
        self.assertFalse(receipt(1., 2**-25, 0., 1000., 1000.))
        self.assertFalse(receipt(.7, 0., 0., 700., 700.))

    def test_credit_and_plan_reject_rounded_up_vessel_gain(self):
        credit = self.policy["CreditQuantum"]
        self.assertEqual(0., credit(500., 1., .5, 3 * 2**-16, 20000.))
        self.assertEqual(0., credit(1000., 1., 2**-25, 0., 20000.))
        self.assertEqual(0., credit(700., .7, 0., 0., 20000.))
        self.assertEqual(0., self.plan(vesselMl=3 * 2**-17))

    def test_finite_predicate_uses_binary32_range(self):
        predicate = self.policy["FiniteNonNegative"]
        for value in (0., -0., 1., FLOAT_MAX):
            self.assertTrue(predicate(value), value)
        for value in (-1., math.nan, math.inf, -math.inf, 1e39):
            self.assertFalse(predicate(value), value)


if __name__ == "__main__":
    unittest.main()
