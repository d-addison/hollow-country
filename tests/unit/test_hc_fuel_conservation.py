"""HC-3: authored handlers over explicit SYNTHETIC inventory/tank ports.

Offline results are control-flow evidence only; runtime acceptance pending.

TDD receipt on the #154 base:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_fuel_conservation -v
RED: (16.0, 0.0, 1, 0, 0) != (15.75, 249.0, 1, 1, 1): closed vessel debited donor.
The shared harness supplies synthetic native GetType for #154 refusal reporting.
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
                reason = "siphon_receipt_mismatch" if fault == "receipt" else "siphon_unavailable"
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


if __name__ == "__main__":
    unittest.main()
