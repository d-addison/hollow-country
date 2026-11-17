"""Review-only mutations: redirect existing tests to independent scratch sources."""
from pathlib import Path
import hashlib
import io
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.unit import test_fuel_siphon_production as production
from tests.unit import test_fuel_transfer as transfer

OUT = Path(__file__).resolve().parent
ACTION = production.ACTION
POLICY = transfer.SOURCE
original = {"action": ACTION.read_text(), "policy": POLICY.read_text()}
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ACTION, POLICY)}

# id, target, exact replacement, explanation; each mutant starts from originals.
MUTANTS = [
    ("M01", "action", "if (!GetGame().IsServer())\n        {", "if (GetGame().IsServer())\n        {", "Invert mutation authority guard"),
    ("M02", "action", "Liquid.FillContainer(vessel, LIQUID_GASOLINE, creditMl);", "Liquid.FillContainer(vessel, LIQUID_GASOLINE, creditMl * 2);", "Double vessel credit"),
    ("M03", "action", "car.Leak(CarFluid.FUEL, stepMl * 0.001);", "car.Leak(CarFluid.FUEL, stepMl);", "Debit milliliters as liters"),
    ("M04", "action", "float creditMl = HCFuelTransferPolicy.SiphonCreditMl(stepMl, beforeLiters, afterLiters);", "float creditMl = HCFuelTransferPolicy.SiphonCreditMl(stepMl, beforeLiters, beforeLiters - stepMl * 0.001);", "Replace readback with fabricated after value"),
    ("M05", "action", "CalcAndSetQuantity(action_data);\n        return UA_CANCEL;", "if (false)\n            CalcAndSetQuantity(action_data);\n        return UA_CANCEL;", "Make Cancel flush unreachable"),
    ("M06", "action", "return settings && settings.EnableCrafting;", "return settings || settings.EnableCrafting;", "Ignore disabled crafting when settings exist"),
    ("M07", "action", "if (vector.DistanceSq(car.GetRefillPointPosWS(), player.GetPosition()) >= reach * reach)", "if (vector.DistanceSq(car.GetRefillPointPosWS(), player.GetPosition()) < reach * reach)", "Invert distance eligibility"),
    ("M08", "action", "if (!car || car.IsDamageDestroyed() || car.EngineIsOn() || car.IsMoving())", "if (!car || (false && car.IsDamageDestroyed()) || car.EngineIsOn() || car.IsMoving())", "Allow destroyed car"),
    ("M09", "action", "m_PendingMl = 0;\n        float remainingMl", "m_PendingMl = requestMl;\n        float remainingMl", "Replay pending transfer on next flush"),
    ("M10", "action", "m_MovedMl += creditMl;", "m_MovedMl += 0;", "Never advance server progress"),
    ("M11", "action", "if (selections.Get(i) == car.GetActionCompNameFuel())", "if (selections.Get(i) != car.GetActionCompNameFuel())", "Accept wrong car selection"),
    ("M12", "action", "AddAction(HCActionSiphonFuelFromCar);", "AddAction(ActionFillFuel);", "Remove held-item siphon registration"),
    ("M13", "policy", "float availableMl = fuelLiters * 1000.0;", "float availableMl = fuelLiters * 100.0;", "Session liters conversion off by ten"),
    ("M14", "policy", "if (stepMl > pendingMl)\n            stepMl = pendingMl;", "if (false)\n            stepMl = pendingMl;", "Remove pending cap"),
    ("M15", "policy", "if (stepMl > remainingMl)\n            stepMl = remainingMl;", "if (false)\n            stepMl = remainingMl;", "Remove remaining cap"),
    ("M16", "policy", "if (removedMl > stepMl)\n            return stepMl;", "if (false)\n            return stepMl;", "Remove credit step cap"),
    ("M17", "policy", "!FiniteNonNegative(vesselMl) || !FiniteNonNegative(vesselMaxMl)", "!FiniteNonNegative(vesselMl)", "Remove session maximum finite check (last occurrence only)"),
    ("M18", "policy", "if (!FiniteNonNegative(pendingMl) || !FiniteNonNegative(remainingMl))", "if (!FiniteNonNegative(pendingMl))", "Remove remaining finite check"),
    ("M19", "policy", "if (!FiniteNonNegative(stepMl) || !FiniteNonNegative(fuelBeforeLiters) || !FiniteNonNegative(fuelAfterLiters))", "if (!FiniteNonNegative(stepMl) || !FiniteNonNegative(fuelBeforeLiters))", "Remove after-fuel finite check"),
    ("M20", "policy", "if (!FiniteNonNegative(availableMl))\n            return 0;", "if (false)\n            return 0;", "Remove session conversion overflow check (last occurrence only)"),
]

results = []
for ident, target, old, new, description in MUTANTS:
    case = OUT / "mutants" / ident
    case.mkdir(parents=True, exist_ok=True)
    sources = original.copy()
    assert old in sources[target], ident
    if ident in ("M17", "M20"):
        before, sep, after = sources[target].rpartition(old)
        sources[target] = before + new + after
    else:
        assert sources[target].count(old) == 1, ident
        sources[target] = sources[target].replace(old, new)
    action_path, policy_path = case / "HCFuelSiphon.c", case / "HCFuelTransferPolicy.c"
    action_path.write_text(sources["action"])
    policy_path.write_text(sources["policy"])
    production.ACTION = action_path
    transfer.SOURCE = policy_path
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (production, transfer))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (case / "test-output.txt").write_text(stream.getvalue())
    failed = [test.id() for test, _ in result.failures + result.errors]
    record = dict(id=ident, target=target, description=description,
                  status="SURVIVED" if result.wasSuccessful() else "KILLED",
                  tests=result.testsRun, failed=failed)
    results.append(record)
    print(ident, record["status"], description, "; ".join(failed))

assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
(OUT / "mutations.json").write_text(json.dumps(dict(source_sha256=hashes, results=results), indent=2) + "\n")
print("Source SHA-256 unchanged; total", len(results), "killed", sum(r["status"] == "KILLED" for r in results))
