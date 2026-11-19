"""HC-3: authored handlers over explicit SYNTHETIC inventory/tank ports.

Offline results are control-flow evidence only; runtime acceptance pending.

TDD receipt on the #154 base:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_fuel_conservation -v
RED: (16.0, 0.0, 1, 0, 0) != (15.75, 249.0, 1, 1, 1): closed vessel debited donor.
The shared harness supplies synthetic native GetType for #154 refusal reporting.

Round 2 review, actual RED (before source changes):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_fuel_conservation.RoundTwoTests -v
Ran 8 tests; FAILED (failures=37). Per finding:
- Both endings: [] != ['Siphoning stopped; the fuel, container or service changed.']
  (with continuation: [] != ['Cannot siphon fuel now; check the car, container and server availability.']).
- Causes: ['Open the fuel container first.'] != [generic refusal]; the RED
  receipt includes closed/full/liquid/range/LOS/moving/restrained/service-off.
- Cheap checks: [] != [0, 1] (both synthetic raycasts ran for an empty tank).
- Start: [True] != [] / [False] != []; stop: True is not false (lease held).
ProductionStop itself already cleared leases; its direct regression passes.
Follow-up sub-spill final-tank RED: Ran 1 test; FAILED (failures=1),
[] != ['Cannot siphon fuel now; check the car, container and server availability.'].
Raw RED and final GREEN commands/results: .banso-writer/hc3-round2-report.md.
"""
from types import SimpleNamespace as NS
from unittest.mock import patch
import unittest

from tests.unit import test_fuel_siphon_behavior as behavior
from tests.unit import test_siphon_fuel_action as diagnostic
from tests.unit.test_fuel_siphon_behavior import (
    World, LeaseData, native_actor, ItemBase, PlayerBase, authored,
)


class FuelConservationTests(unittest.TestCase):
    def test_closed_vessel_cannot_debit_real_tank(self):
        world = World()
        world.vessel.IsOpen = lambda: False
        before = world.snapshot()
        world.component().Execute(world.data)
        self.assertEqual(before, world.snapshot(), "closed vessel debited donor")

    def test_competing_users_have_one_donor_lease(self):
        world = World()
        first = world.component()
        other = world.competitor()
        second = world.component(setup=False)
        second.Setup(other)
        first.Execute(world.data)
        second.Execute(other)
        self.assertEqual(1, len(world.car.leaks), "competing action debited leased donor")

    def test_slowly_moving_car_is_not_a_stationary_donor(self):
        world = World()
        # Native CarScript.IsMoving returns false up to 3.5 km/h.
        world.car.GetSpeedometerAbsolute = lambda: 0.1
        before = world.snapshot()
        world.component().Execute(world.data)
        self.assertEqual(before, world.snapshot(), "slowly moving donor debited")

    def test_recipient_and_los_failures_never_debit(self):
        for fault in ("mixed", "full", "ruined", "no_quantity", "occluded", "empty", "deleted", "boat", "oversized_vessel"):
            with self.subTest(fault=fault):
                world = World()
                if fault == "mixed": world.vessel.quantity, world.vessel.liquid = 10, 2
                if fault == "full": world.vessel.quantity = world.vessel.maximum
                if fault == "ruined": world.vessel.destroyed = True
                if fault == "no_quantity": world.vessel.HasQuantity = lambda: False
                if fault == "occluded": world.visible = False
                if fault == "empty": world.car.liters = 0
                if fault == "deleted": world.target.obj = None
                if fault == "boat": world.target.obj = NS(GetType=lambda: "SyntheticBoat")
                if fault == "oversized_vessel": world.vessel.maximum = 1048577
                before = world.snapshot()
                world.component().Execute(world.data)
                self.assertEqual(before, world.snapshot())

    def test_cancel_flushes_only_owned_partial_step_and_restart_is_fresh(self):
        world = World(delta=0.25)
        comp = world.component()
        comp.Execute(world.data)
        self.assertEqual([], world.car.leaks)
        comp.Cancel(world.data)
        self.assertEqual(1, len(world.car.leaks))
        after = world.snapshot()
        comp.Cancel(world.data)
        comp.Execute(world.data)
        self.assertEqual(after, world.snapshot())
        self.assertFalse(world.data.LockHeld)
        world.data = LeaseData(world.player, world.target, world.vessel)
        next_comp = world.component()
        next_comp.Execute(world.data)
        next_comp.Cancel(world.data)
        self.assertEqual(2, len(world.car.leaks))

    def test_revalidation_on_cancel_discards_invalid_pending_credit(self):
        world = World(delta=0.25)
        comp = world.component()
        comp.Execute(world.data)
        world.vessel.open = False
        comp.Cancel(world.data)
        self.assertEqual([], world.car.leaks)
        self.assertFalse(world.data.LockHeld)

    def test_expired_or_stopped_session_cannot_reacquire_from_late_callback(self):
        for fault in ("expire", "stop", "retarget", "actor"):
            with self.subTest(fault=fault):
                world = World()
                comp = world.component()
                if fault == "expire": world.now += 10001
                if fault == "stop": world.ns["HCActionSiphonFuel"].ProductionStop()
                if fault == "retarget": world.target.obj = None
                if fault == "actor": world.data.m_Player = native_actor(PlayerBase(world.vessel))
                comp.Execute(world.data)
                self.assertEqual([], world.car.leaks)
                comp.Setup(world.data)
                comp.Execute(world.data)
                self.assertEqual([], world.car.leaks)

    def test_partial_debit_credit_is_readback_bounded_and_noop_never_credits(self):
        for mode in ("normal", "half", "noop"):
            with self.subTest(mode=mode):
                world = World()
                world.car.leak_mode = mode
                before = world.car.liters
                world.component().Execute(world.data)
                removed = (before - world.car.liters) * 1000
                self.assertLessEqual(world.vessel.quantity, removed)
                self.assertEqual(bool(removed), bool(world.fills))

    def test_post_debit_changes_or_abort_never_credit_or_replay(self):
        for fault in ("deleted", "recipient", "cancel", "abort"):
            with self.subTest(fault=fault):
                world = World()
                comp = world.component()
                native_leak = world.car.Leak
                def leak(fluid, amount):
                    native_leak(fluid, amount)
                    if fault == "deleted": world.target.obj = None
                    if fault == "recipient": world.vessel.quantity = 1
                    if fault == "cancel": comp.Cancel(world.data)
                    if fault == "abort": raise RuntimeError("SYNTHETIC native abort after debit")
                world.car.Leak = leak
                if fault == "abort":
                    with self.assertRaisesRegex(RuntimeError, "SYNTHETIC"):
                        comp.Execute(world.data)
                else:
                    comp.Execute(world.data)
                comp.Cancel(world.data)
                comp.Execute(world.data)
                self.assertEqual(1, len(world.car.leaks))
                self.assertEqual([], world.fills)

    def test_off_and_client_paths_have_no_inventory_writes_or_leases(self):
        for changes in ({"gate": False}, {"on": False}, {"server": False}):
            with self.subTest(changes=changes):
                world = World(**changes)
                if world.server:
                    self.assertFalse(world.action().ActionCondition(world.player, world.target, world.vessel))
                    self.assertEqual([], world.rays, "off action performed physics work")
                comp = world.component()
                comp.Execute(world.data)
                comp.Cancel(world.data)
                self.assertEqual([], world.car.leaks)
                self.assertEqual([], world.fills)
                self.assertEqual([], world.locks.m_Sessions)

    def test_geometry_guard_uses_both_native_channels_and_native_reach(self):
        world = World()
        self.assertTrue(world.Siphon.Allowed(world.player, world.target, world.vessel))
        self.assertEqual([0, 1], world.rays)
        world.car.reach = 0.5
        self.assertFalse(world.Siphon.Allowed(world.player, world.target, world.vessel))

    def test_all_production_refusal_phases_keep_shared_reason_reports(self):
        # Native writes, identities, clocks and physics are SYNTHETIC ports.
        # The authored component and the actual #154 helper execute in this harness.
        for fault in ("closed_gate", "lease", "cancel_recipient", "noop_debit",
                      "post_debit_gate", "post_debit_recipient", "post_credit_lease", "receipt"):
            with self.subTest(fault=fault):
                world = World(gate=fault != "closed_gate",
                              delta=0.25 if fault == "cancel_recipient" else 0.5)
                comp = world.component()
                if fault == "lease": world.now += 10001
                if fault == "noop_debit": world.car.leak_mode = "noop"
                if fault == "receipt": world.fill_mode = "none"
                if fault.startswith("post_debit"):
                    native_leak = world.car.Leak
                    def leak(fluid, amount):
                        native_leak(fluid, amount)
                        if fault == "post_debit_gate": world.gate = False
                        else: world.vessel.open = False
                    world.car.Leak = leak
                if fault == "post_credit_lease":
                    liquid = world.ns["Liquid"]
                    native_fill = liquid.FillContainer
                    def fill(vessel, kind, amount):
                        native_fill(vessel, kind, amount)
                        world.ns["HCActionSiphonFuel"].ProductionStop()
                    liquid.FillContainer = fill
                comp.Execute(world.data)
                if fault == "cancel_recipient": world.vessel.open = False
                comp.Cancel(world.data)
                after = world.snapshot()
                for _ in range(3):
                    comp.Execute(world.data)
                    comp.Cancel(world.data)
                reason = {"receipt": "siphon_receipt_mismatch",
                          "closed_gate": "siphon_service_off", "post_debit_gate": "siphon_service_off",
                          "cancel_recipient": "siphon_closed", "post_debit_recipient": "siphon_closed"}.get(
                              fault, "siphon_unavailable")
                self.assertEqual(["[HC Refusal] refused reason=" + reason + " class=SyntheticCar"],
                                 [line for line in world.prints if line.startswith("[HC Refusal]")])
                self.assertEqual(1, len(world.player.messages))
                self.assertFalse(world.data.LockHeld)
                self.assertEqual(after, world.snapshot(), "refused step replayed")

    def test_native_end_hook_releases_and_slow_ticks_renew_only_live_lease(self):
        world = World()
        comp = world.component()
        for _ in range(3):
            world.now += 5000
            comp.Execute(world.data)
            self.assertTrue(world.data.LockHeld)
        context = {"HCActionSiphonFuel": world.ns["HCActionSiphonFuel"],
                   "super": NS(OnEndServer=lambda data: None)}
        with patch.object(diagnostic, "SOURCE", behavior.ACTION):
            end = authored("OnEndServer", "action_data", context)
        end(None, world.data)
        after = world.snapshot()
        comp.Execute(world.data)
        self.assertEqual(after, world.snapshot())
        self.assertFalse(world.data.LockHeld)


class RoundTwoTests(unittest.TestCase):
    """Review regressions: authored source, explicitly SYNTHETIC native ports."""

    def assert_quiet_completion(self, **kwargs):
        for continuation in (False, True):
            with self.subTest(continuation=continuation, **kwargs):
                world = World(**kwargs)
                before_liters, before_ml = world.car.liters, world.vessel.quantity
                free = world.vessel.maximum - before_ml
                comp, action = world.component(), world.action()
                for _ in range(100):
                    if continuation and not action.ActionConditionContinue(world.data):
                        break
                    if comp.Execute(world.data) == 4:
                        break
                else:
                    self.fail("session did not complete")
                self.assertEqual([], world.player.messages, "normal completion sent a refusal")
                self.assertFalse(any("[HC Refusal]" in line for line in world.prints))
                self.assertEqual(1, sum("Fuel siphon completed" in line for line in world.prints))
                self.assertGreater(world.vessel.quantity, before_ml)
                self.assertGreaterEqual((before_liters - world.car.liters) * 1000,
                                        world.vessel.quantity - before_ml)
                self.assertLessEqual(world.vessel.quantity - before_ml, free)
                self.assertFalse(world.data.LockHeld)
                after = world.snapshot()
                for _ in range(3):
                    comp.Execute(world.data)
                    comp.Cancel(world.data)
                    action.ActionConditionContinue(world.data)
                self.assertEqual(after, world.snapshot())
                self.assertEqual([], world.player.messages)
                self.assertEqual(1, sum("Fuel siphon completed" in line for line in world.prints))

    def test_tank_limited_session_completes_without_refusal_and_conserves(self):
        self.assert_quiet_completion(liters=0.5)

    def test_vessel_limited_session_completes_without_refusal_and_conserves(self):
        self.assert_quiet_completion(quantity=4700, maximum=5000)

    def test_sub_spill_final_tank_readback_is_a_quiet_completion(self):
        world = World(liters=1.0)
        comp = world.component()
        # Synthetic external drain leaves less than a spill in an active tank.
        world.car.liters = behavior.f32(0.0005)
        comp.Execute(world.data)
        self.assertEqual(0, world.car.liters)
        self.assertEqual([], world.fills)
        self.assertEqual([], world.player.messages)
        self.assertEqual(1, sum("Fuel siphon completed" in line for line in world.prints))
        self.assertFalse(world.data.LockHeld)

    def test_live_empty_tank_or_full_vessel_finishes_quietly(self):
        for exhausted in ("tank", "vessel"):
            for continuation in (False, True):
                with self.subTest(exhausted=exhausted, continuation=continuation):
                    world = World()
                    comp = world.component()
                    comp.Execute(world.data)
                    if exhausted == "tank": world.car.liters = 0
                    else: world.vessel.quantity = world.vessel.maximum
                    before = world.snapshot()
                    if continuation:
                        self.assertFalse(world.action().ActionConditionContinue(world.data))
                    else:
                        self.assertEqual(4, comp.Execute(world.data))
                    comp.Cancel(world.data)
                    self.assertEqual(before, world.snapshot())
                    self.assertEqual([], world.player.messages)
                    self.assertEqual(1, sum("Fuel siphon completed" in line for line in world.prints))
                    self.assertFalse(world.data.LockHeld)

    def test_refusal_causes_have_distinct_messages_and_log_reasons(self):
        cases = (
            ("closed", lambda w: setattr(w.vessel, "open", False), "Open the fuel container first."),
            ("full", lambda w: setattr(w.vessel, "quantity", w.vessel.maximum), "The fuel container is full."),
            ("liquid", lambda w: (setattr(w.vessel, "quantity", 1), setattr(w.vessel, "liquid", 2)),
             "Use a container that accepts gasoline."),
            ("range", lambda w: setattr(w.player, "pos", (9., 0., 0.)), "Move closer to the fuel tank."),
            ("los", lambda w: setattr(w, "visible", False), "The fuel tank is obstructed."),
            ("moving", lambda w: setattr(w.car, "GetSpeedometerAbsolute", lambda: 0.1), "Stop the vehicle first."),
            ("restrained", lambda w: setattr(w.player, "IsRestrained", lambda: True), "Free your hands before siphoning."),
            ("service_off", lambda w: setattr(w, "gate", False), "Fuel siphoning is unavailable on this server."),
        )
        for cause, invalidate, message in cases:
            # Both check APIs report their actual cause through a caller-owned DTO.
            for check in ("Allowed", "ProductionRecipientReady"):
                with self.subTest(cause=cause, check=check):
                    world = World()
                    invalidate(world)
                    refusal = world.ns["HCRefusalResult"]()
                    owner = world.Siphon if check == "Allowed" else world.ns["HCActionSiphonFuel"]
                    self.assertFalse(getattr(owner, check)(world.player, world.target, world.vessel, refusal))
                    self.assertEqual("siphon_" + cause, refusal.Reason)
            for phase in (("prediction", "start") if cause == "full" else ("prediction", "start", "step", "cancel")):
                with self.subTest(cause=cause, phase=phase):
                    world = World(delta=0.25 if phase == "cancel" else 0.5)
                    comp = world.component() if phase in ("step", "cancel") else None
                    if phase == "cancel": comp.Execute(world.data)
                    invalidate(world)
                    before = world.snapshot()
                    if phase == "prediction":
                        self.assertFalse(world.action().ActionCondition(world.player, world.target, world.vessel))
                    elif phase == "start":
                        context = dict(world.ns, super=NS(OnStartServer=lambda data: None))
                        with patch.object(diagnostic, "SOURCE", behavior.ACTION):
                            start = authored("OnStartServer", "action_data", context)
                        start(None, world.data)
                    elif phase == "cancel": comp.Cancel(world.data)
                    else: comp.Execute(world.data)
                    self.assertEqual([message], world.player.messages)
                    self.assertEqual(["[HC Refusal] refused reason=siphon_" + cause + " class=SyntheticCar"],
                                     [line for line in world.prints if "[HC Refusal]" in line])
                    self.assertEqual(before, world.snapshot())

    def test_allowed_rejects_cheap_failures_before_any_raycast(self):
        for fault in ("empty", "invalid_tank", "wrong_selection", "oversized_selection", "hands"):
            with self.subTest(fault=fault):
                world = World()
                if fault == "empty": world.car.liters = 0
                if fault == "invalid_tank": world.car.capacity = 4097
                if fault == "wrong_selection": world.car.selections = ["wheel"]
                if fault == "oversized_selection": world.car.selections = ["refill"] * 33
                if fault == "hands": world.player.hands = None
                self.assertFalse(world.Siphon.Allowed(world.player, world.target, world.vessel))
                self.assertEqual([], world.rays, "cheap refusal performed raycasts")

    def test_invalid_target_is_rejected_before_native_selection_lookup(self):
        for fault in ("negative_component", "parented"):
            with self.subTest(fault=fault):
                world = World()
                if fault == "negative_component": world.target.index = -1
                else: world.target.GetParent = lambda: object()
                lookups = []
                world.car.GetActionComponentNameList = lambda index, names: lookups.append(index)
                self.assertFalse(world.Siphon.Allowed(world.player, world.target, world.vessel))
                self.assertEqual([], lookups)
                self.assertEqual([], world.rays)

    def crafting_hook(self, world, method, valid=True, enabled=True):
        source = behavior.ROOT / "mods/HollowCountry/scripts/4_World/Crafting/HCCraftingModule.c"
        gate = NS(m_Started=False, m_Validated=False, m_Crafted=NS(ToString=lambda: "0"))
        calls = []
        service = world.ns["HCActionSiphonFuel"]
        context = dict(GetGame=lambda: world.game, HCCraftingGate=gate,
                       HCCraftingNativeChecks=NS(Run=lambda: valid),
                       # SYNTHETIC HC-30 collaborator; its real validation/report has focused coverage.
                       HCCommonRecoveryPolicy=NS(HCValidateRegistered=lambda: True,
                                                 HCReport=lambda enabled, admitted: None),
                       HCActionSiphonFuel=NS(ProductionStart=lambda preference: calls.append(preference),
                                            ProductionStop=service.ProductionStop), Print=world.prints.append)
        context.update(HCModule=object, tostr=lambda value: value.ToString())
        from tests.unit.test_refusal_report import MethodsTranslator
        for code in MethodsTranslator(source.read_text(), "HCCraftingModule",
                                      ("IsEnabled", "OnStart", "OnStop")).classes():
            exec(code, context)
        module = context["HCCraftingModule"]()
        if method == "OnStart": module.OnStart(NS(EnableCrafting=enabled))
        else: module.OnStop()
        return gate, calls

    def test_crafting_start_calls_production_start_after_validation(self):
        for valid in (False, True):
            with self.subTest(valid=valid):
                gate, calls = self.crafting_hook(World(), "OnStart", valid=valid)
                self.assertEqual([valid], calls)
                self.assertEqual(valid, gate.m_Started)
        self.assertEqual([], self.crafting_hook(World(server=False), "OnStart")[1])
        self.assertEqual([], self.crafting_hook(World(), "OnStart", enabled=False)[1])

    def test_crafting_stop_clears_live_siphon_leases(self):
        world = World()
        comp = world.component()
        self.assertTrue(world.data.LockHeld)
        self.crafting_hook(world, "OnStop")
        self.assertFalse(world.data.LockHeld)
        self.assertEqual([], world.locks.m_Sessions)
        before = world.snapshot()
        comp.Execute(world.data)
        self.assertEqual(before, world.snapshot())

    def test_production_stop_clears_every_lease(self):
        world = World()
        world.component()
        world.ns["HCActionSiphonFuel"].ProductionStop()
        self.assertFalse(world.data.LockHeld)
        self.assertEqual([], world.locks.m_Sessions)


if __name__ == "__main__":
    unittest.main()
