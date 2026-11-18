"""HC-7 / #58: synthetic custody/intent/removal conservation; runtime=PENDING.

Spec: acknowledge completed keys without fresh tape; new mounts spend once;
full cargo refuses removal; failed reservation acquisition releases only our
leases. Plan: extend the existing journal/native port, keep all 29 exact rows
and R12 pending. Task: source policy + bounded admission diagnostic, then native
DayZDiag/PBO and two-client acceptance by the lead. These fixtures execute the
authored handlers through existing restricted adapters, never a gameplay model.

Actual TDD receipt, 2026-11-18:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_taped_lights -v
RED: Ran 5 tests; FAILED (failures=6): AssertionError: 0 != 2 (spent-roll
replay); partial custody leaked (host/tape/battery); 1 != 0 (missing plan line).
GREEN: Ran 5 tests; OK. Native compilation/presentation remain unobserved.
"""
import copy
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit import test_taped_light_service as policy
from tests.unit.test_group_server import EArray, body
from tests.unit.test_group_ui import ui_member
from tests.unit.test_taped_light_v1 import NATIVE, CATALOG, native_member


class TapedLightConservationTests(unittest.TestCase):
    setUp = policy.TapedLightTests.setUp
    run_op = policy.TapedLightTests.run_op

    def test_spent_last_tape_replay_acknowledges_without_a_new_debit_or_move(self):
        self.port.sample.TapeQuantity = 1
        self.assertEqual(self.code.OK, self.run_op())
        receipt = copy.deepcopy(self.port.writes)
        self.assertEqual(0, self.port.sample.TapeQuantity)
        for missing_roll in (False, True):
            with self.subTest(missing_roll=missing_roll):
                if missing_roll:
                    self.port.sample.TapeId = ""
                    self.port.sample.TapeHealth = 0
                self.assertEqual(self.code.OK, self.run_op())
                self.assertEqual(receipt, self.port.writes)
        self.assertEqual([1], self.port.consumptions)
        self.assertEqual([True], self.port.moves)
        self.assertEqual(self.code.CONFLICT, self.run_op("mount-1", False))
        self.assertEqual(self.code.OK, self.run_op("remove-1", False))
        self.assertEqual(self.code.DENIED, self.run_op("new-mount"))
        self.port.sample.TapeId = "fresh-roll"
        self.port.sample.TapeHealth = .6
        self.port.sample.TapeQuantity = 1
        self.assertEqual(self.code.OK, self.run_op("new-mount"))
        self.assertEqual([1, 1], self.port.consumptions)
        self.assertEqual([True, False, True], self.port.moves)

    def test_full_cargo_refuses_before_intent_then_returns_same_light_and_battery(self):
        self.port.binding.ReturnToCargo = True
        original = copy.deepcopy(self.port.sample)
        self.assertEqual(self.code.OK, self.run_op())
        receipt = copy.deepcopy(self.port.writes)
        # Explicit synthetic capacity port; no ground/hands fallback.
        self.port.CanTransfer = lambda binding, mounting: False
        self.assertEqual(self.code.BLOCKED, self.run_op("remove", False))
        self.assertEqual(receipt, self.port.writes)
        self.assertEqual([True], self.port.moves)
        self.assertFalse(self.state.Quarantined)
        self.port.CanTransfer = lambda binding, mounting: True
        transfer = self.port.Transfer

        def to_cargo(binding, mounting):
            moved = transfer(binding, mounting)
            if not mounting:
                self.port.sample.Place = 0
            return moved

        self.port.Transfer = to_cargo
        self.assertEqual(self.code.OK, self.run_op("remove", False))
        self.assertEqual(0, self.port.sample.Place)
        self.assertTrue(self.e["Preserved"](original, self.port.sample))
        self.assertEqual([1], self.port.consumptions)
        self.assertEqual([True, False], self.port.moves)

    def test_spent_tape_intent_fault_never_refunds_or_replays_on_reopen(self):
        self.port.sample.TapeQuantity = 1
        self.port.fail_phase = self.phase.TAPE_SPENT
        self.assertEqual(self.code.QUARANTINED, self.run_op())
        self.assertEqual(0, self.port.sample.TapeQuantity)
        self.assertEqual([], self.port.moves)
        self.assertEqual(self.code.QUARANTINED, self.run_op("retry"))
        recovered = self.e["HCTapedLightState"]()
        self.port.Load = lambda state: state.Records.extend(
            copy.deepcopy(self.state.Records)) or True
        self.assertEqual(self.code.QUARANTINED,
                         self.e["Open"](recovered, self.port))
        self.assertEqual([1], self.port.consumptions)


class TapedLightNativeCustodyTests(unittest.TestCase):
    def test_failed_acquisition_releases_partial_owned_reservations(self):
        # Explicit synthetic native reservation API. A failed host/tape/battery
        # reservation does not grant us a lease for that item.
        for refused in ("host", "tape", "battery"):
            with self.subTest(refused=refused):
                actor = NS()
                light, host, tape, battery = [NS(name=name) for name in
                                               ("light", "host", "tape", "battery")]
                for item in (light, host, tape):
                    item.GetHierarchyRootPlayer = lambda: actor
                actor.GetItemInHands = lambda: host
                light.FindAttachmentBySlotName = lambda slot: battery
                active, cleared = [], []

                def reserve(item, destination, timeout):
                    if item.name == refused:
                        return False
                    active.append(item)
                    return True

                def release(item, destination):
                    cleared.append(item.name)
                    active.remove(item)
                    return True

                env = dict(
                    GetGame=lambda: NS(IsServer=lambda: True),
                    HCGroupLocation=lambda: NS(SetAttachment=lambda *args: None),
                    InventorySlots=NS(GetSlotIdFromString=lambda slot: 17),
                    GameInventory=NS(
                        HasInventoryReservation=lambda item, dst: item in active,
                        AddInventoryReservation=reserve,
                        ClearInventoryReservation=release,
                        c_InventoryReservationTimeoutMS=5000))
                state = NS(mHCReserved=EArray(), mHCDestination=None,
                           mHCLight=None, Ready=lambda: True,
                           mHCBinding=NS(SlotName="weaponFlashlight",
                                         BatterySlotName="BatteryD"))
                for method in ("Reserve", "Release"):
                    setattr(state, method, lambda *args, method=method:
                            native_member("HCTapedLightV1Custody", method,
                                          state, env, *args))
                self.assertFalse(native_member("HCTapedLightV1Custody", "Acquire",
                                               state, env, actor, host,
                                               light, tape, True))
                self.assertEqual([], active, "partial custody leaked")
                self.assertEqual([], state.mHCReserved)
                self.assertNotIn(refused, cleared)

    def test_start_reports_all_pairs_and_r12_pending_even_when_off(self):
        text = NATIVE.read_text()
        match = re.search(r'class HCTapedLightStartup\b[^\{]*\{', text)
        source = body(text, match.end())
        source = re.sub(r'(\w+)\.ToString\(\)', r'str(\1)', source)
        rows = re.findall(r'Add\(rows, "([^"]+)"', CATALOG.read_text())
        for admitted in (False, True):
            logs = []
            env = dict(Print=logs.append,
                       HCTapedLightAdmission=NS(Admitted=lambda: admitted,
                                               Qualified=lambda: False),
                       HCTapedLightCatalog=NS(Rows=lambda: EArray(rows)),
                       HCV2Admission=NS(Line=lambda *args: "synthetic admission",
                                        OnOff=lambda value: "on" if value else "off"))
            state = NS(m_Printed=False)
            ui_member(source, "OnStart", state, env, NS())
            ui_member(source, "OnStart", state, env, NS())
            plan = [line for line in logs if line.startswith("[HC Plan] HC-7 ")]
            self.assertEqual(1, len(plan), logs)
            for field in ("weapon_pairs=29", "client_accepted=0", "runtime=PENDING",
                          "r12=pending_proxy_client", "state=" + ("on" if admitted else "off")):
                self.assertIn(field, plan[0])
            self.assertNotIn("R12", rows)


if __name__ == "__main__":
    unittest.main()
