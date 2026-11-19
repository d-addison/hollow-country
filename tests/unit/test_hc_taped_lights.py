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

HC-23 spec -> plan -> task, 2026-11-18: first exact native helmet pair and
compatibility queue, bounded startup/off receipt, HC-7 qualification seam.
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_taped_lights -v
RED: AssertionError: True is not false : unsupported helmet mount accepted
from a self-declared row. Ran 6 tests; FAILED (failures=1).
GREEN: Ran 6 tests; OK. Native compile/boot/PBO/two-client acceptance PENDING.
Required specification files are absent from this worker snapshot; the supplied
HC-23 task/brief and runtime contract are the scoped design inputs.

HC-52 spec -> plan -> task, 2026-11-18: exact pack/cross-slot identity and
server preference guards before HC-7 custody; no supported backpack proxy or
transform is fabricated. Authored candidate/evidence queue: backpack-mounts.json.
RED command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_taped_lights.TapedLightConservationTests.test_pack_pairs_refuse_before_custody_without_native_qualification -v
Actual RED: Ran 1 test; FAILED (failures=1).
AssertionError: 3 != 0 : unenabled cross-slot pair attached
GREEN command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_taped_lights -v
GREEN: Ran 7 tests; OK. Native compile/boot/PBO/two-client acceptance PENDING.
The supplied HC-52 task/brief and runtime contract are the scoped design inputs;
the two required specification files remain absent. No distance added.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit import test_taped_light_service as policy
from tests.unit.test_group_server import EArray, body
from tests.unit.test_group_ui import ui_member
from tests.unit.test_taped_light_v1 import NATIVE, CATALOG, native_member

ROOT = Path(__file__).resolve().parents[2]
WEARABLE = ROOT / "mods/HollowCountry/scripts/3_Game/Survival/HCTapedWearableCatalog.c"
HELMETS = ROOT / "mods/HollowCountry/scripts/4_World/Survival/HCTapedHelmetMounts.c"
MANIFEST = ROOT / "mission/hollow-country/lights/helmet-mounts.json"
PACKS = ROOT / "mods/HollowCountry/scripts/4_World/Survival/HCTapedPackMounts.c"
PACK_MANIFEST = ROOT / "mission/hollow-country/lights/backpack-mounts.json"
MOUNT_DEFAULTS = ROOT / "config/hollow-country-light-mounts.json"


def helmet_member(path, cls, method, state, env, *args):
    """Existing restricted executor; only receiver/type syntax is adapted."""
    text = path.read_text()
    match = re.search(r'class ' + cls + r'\b[^\{]*\{', text)
    source = body(text, match.end())
    source = re.sub(r'\b(?:HCTapedLightHostRow|TStringArray)\s+(?=\w+\s*[=;])',
                    'HCGroupNative ', source)
    source = source.replace('new TStringArray', 'NewSlots()')
    source = re.sub(r'\b(?:HCTapedLightBinding|HCOperationalStatus) '
                    r'(?=(?:Resolve|HCGetOperationalStatus)\()', 'int ', source)
    source = re.sub(r'(\w+)\.ToString\(\)', r'str(\1)', source)
    return ui_member(source, method, state, dict(env), *args)


class TapedLightConservationTests(unittest.TestCase):
    setUp = policy.TapedLightTests.setUp
    run_op = policy.TapedLightTests.run_op

    def test_pack_pairs_refuse_before_custody_without_native_qualification(self):
        # Explicit SYNTHETIC binding/port: a forged qualification must not
        # turn a cross-slot request into a tape debit or inventory move.
        original = copy.deepcopy(self.port.sample)
        self.port.binding.CrossSlot = True
        self.port.binding.PairId = ""
        self.assertEqual(self.code.BLOCKED, self.run_op(),
                         "unenabled cross-slot pair attached")
        self.assertEqual([], self.port.moves)
        self.assertEqual([], self.port.consumptions)
        self.assertEqual([], self.port.writes)
        self.assertEqual(vars(original), vars(self.port.sample))

        catalog = NS()
        for method in ("KnownPair", "Matches", "Qualified", "SlotName", "Refusal"):
            setattr(catalog, method, lambda *args, method=method: helmet_member(
                WEARABLE, "HCTapedPackCatalog", method, catalog, {}, *args))
        gate = NS(mHCCrossSlot=False, mHCPermitted=EArray(), mHCConfigured=False)
        server = True
        slots = {"CfgVehicles TortillaBag attachments": EArray([
                    "Chemlight", "WalkieTalkie", "Backpack_1", "NBCBag"]),
                 "CfgVehicles UniversalLight inventorySlot": EArray([
                    "weaponFlashlight", "helmetFlashlight"])}
        probes = []
        def config(path, out):
            probes.append(path)
            out.extend(slots[path])
        env = dict(GetGame=lambda: NS(IsServer=lambda: server, ConfigGetTextArray=config),
                   HCBuildIdentity=NS(Matches=lambda build: True, SeenBuild=lambda: "synthetic"),
                   HCTapedPackCatalog=catalog, NewSlots=EArray,
                   HCV2Admission=NS(OnOff=lambda value: "on" if value else "off",
                                     Line=lambda *args: "synthetic admission"))
        for method in ("Configure", "Reset", "CrossSlotEnabled", "NativeSlotAvailable",
                       "PairRefusal", "BindingAllowed"):
            setattr(gate, method, lambda *args, method=method: helmet_member(
                PACKS, "HCTapedPackMounts", method, gate, env, *args))
        self.e["HCTapedPackMounts"] = gate
        manifest = json.loads(PACK_MANIFEST.read_text())
        defaults = json.loads(MOUNT_DEFAULTS.read_text())
        self.assertFalse(defaults["crossSlotLights"])
        self.assertEqual([], defaults["permittedPairIds"])
        self.assertTrue(gate.Configure(NS(crossSlotLights=False, permittedPairIds=EArray())))
        self.assertEqual("cross_slot_disabled", gate.PairRefusal("tortilla_universal_cross"))
        self.assertEqual("pack_native_slot_unavailable", gate.PairRefusal("tortilla_universal_mount"))
        self.assertEqual("unsupported_pack_pair", gate.PairRefusal("unknown"))
        self.assertTrue(gate.Configure(NS(crossSlotLights=True, permittedPairIds=EArray())))
        self.assertEqual("cross_slot_pair_not_permitted", gate.PairRefusal("tortilla_universal_cross"))
        pairs = manifest["AuthoredPairs"] + manifest["CrossSlotPairs"]
        for pair in pairs:
            self.assertTrue(catalog.Matches(pair["PairId"], pair["HostClass"],
                                           pair["LightClass"], pair["SlotName"], pair["CrossSlot"]))
            self.assertFalse(catalog.Qualified(pair["PairId"]))
            self.assertIsNone(pair["LocalPosition"])
            self.assertIsNone(pair["LocalOrientation"])
            for field, value in (("HostClass", "TortillaBag_Winter"),
                                 ("LightClass", "Flashlight"),
                                 ("SlotName", "Back"),
                                 ("PairId", "unknown"),
                                 ("CrossSlot", not pair["CrossSlot"])):
                forged = dict(pair)
                forged[field] = value
                self.assertFalse(catalog.Matches(forged["PairId"], forged["HostClass"],
                                                forged["LightClass"], forged["SlotName"],
                                                forged["CrossSlot"]))
            for enabled in (False, True):
                settings = NS(crossSlotLights=enabled, permittedPairIds=EArray([pair["PairId"]]))
                self.assertTrue(gate.Configure(settings))
                binding = self.port.binding
                for field in ("PairId", "HostClass", "LightClass", "SlotName", "CrossSlot"):
                    setattr(binding, field, pair[field])
                self.assertEqual(self.code.BLOCKED, self.run_op())
                self.assertFalse(gate.BindingAllowed(binding))
                copied = self.e["CopyBinding"](binding)
                self.assertTrue(self.e["SameBinding"](copied, binding))
                copied.CrossSlot = not binding.CrossSlot
                self.assertFalse(self.e["SameBinding"](copied, binding))
                copied = self.e["CopyBinding"](binding)
                copied.PairId = "other-pair"
                self.assertFalse(self.e["SameBinding"](copied, binding))
                self.assertEqual([], self.port.moves)
                self.assertEqual([], self.port.consumptions)
                self.assertEqual([], self.port.writes)
                self.assertEqual(vars(original), vars(self.port.sample))
        # A permissive live config or operator file is never geometry evidence.
        slots["CfgVehicles TortillaBag attachments"].append("helmetFlashlight")
        self.assertTrue(gate.NativeSlotAvailable("tortilla_universal_mount"))
        self.assertFalse(catalog.Qualified("tortilla_universal_mount"))
        self.assertEqual("pack_mount_geometry_pending", gate.PairRefusal("tortilla_universal_mount"))
        self.assertEqual("pack_native_slot_unavailable", gate.PairRefusal("tortilla_universal_cross"))
        # Explicit SYNTHETIC future qualification isolates preference/identity
        # checks, then executes the same HC-7 transaction and conservation code.
        # The shipped catalogue's Qualified method above remains hard false.
        catalog.Qualified = lambda pair_id: True
        slots["CfgVehicles UniversalLight inventorySlot"].append("Chemlight")
        for enabled, ids in ((False, ["tortilla_universal_cross"]), (True, [])):
            self.assertTrue(gate.Configure(NS(crossSlotLights=enabled, permittedPairIds=EArray(ids))))
            self.assertFalse(gate.BindingAllowed(self.port.binding))
        permitted = EArray(["tortilla_universal_cross"])
        self.assertTrue(gate.Configure(NS(crossSlotLights=True, permittedPairIds=permitted)))
        permitted.clear()
        self.assertTrue(gate.BindingAllowed(self.port.binding), "settings ID list was not copied")
        before = copy.deepcopy(self.port.sample)
        self.assertEqual(self.code.OK, self.run_op())
        self.assertTrue(self.e["Preserved"](before, self.port.sample))
        self.assertEqual([1], self.port.consumptions)
        self.assertEqual([True], self.port.moves)
        self.assertEqual(self.code.OK, self.run_op("pack-remove", False))
        self.assertTrue(self.e["Preserved"](before, self.port.sample))
        self.assertEqual([1], self.port.consumptions)
        self.assertEqual([True, False], self.port.moves)
        self.assertTrue(self.e["StateValid"](self.state))
        catalog.Qualified = lambda pair_id: helmet_member(
            WEARABLE, "HCTapedPackCatalog", "Qualified", catalog, {}, pair_id)
        for settings in (None, NS(crossSlotLights=True, permittedPairIds=None),
                         NS(crossSlotLights=True, permittedPairIds=EArray(["unknown"])),
                         NS(crossSlotLights=True, permittedPairIds=EArray([
                             "tortilla_universal_cross", "tortilla_universal_cross"])),
                         NS(crossSlotLights=True, permittedPairIds=EArray(["unknown"] * 3))):
            self.assertFalse(gate.Configure(settings))
            self.assertFalse(gate.CrossSlotEnabled())
            self.assertEqual([], gate.mHCPermitted)
        self.assertTrue(self.e["StateValid"](self.state),
                        "disabled preference invalidated historical custody")
        server = False
        probes.clear()
        self.assertFalse(gate.Configure(NS(**defaults)))
        self.assertFalse(gate.BindingAllowed(self.port.binding))
        self.assertFalse(gate.NativeSlotAvailable("tortilla_universal_mount"))
        self.assertEqual([], probes)
        server = True
        # Startup/off receipt is bounded and idempotent; status is cached, and
        # stop closes preferences without an inventory, scheduler or light port.
        logs = []
        status = NS(HCPublish=lambda *args: logs.append(args), HCStop=lambda: logs.append("stop"))
        module = NS(mHCStarted=False, mHCStatus=status, PairRefusal=gate.PairRefusal,
                    CrossSlotEnabled=gate.CrossSlotEnabled, Reset=gate.Reset,
                    mHCPermitted=gate.mHCPermitted)
        env["Print"] = logs.append
        self.assertIs(status, helmet_member(PACKS, "HCTapedPackMounts", "HCGetOperationalStatus", module, env))
        for _ in range(2):
            helmet_member(PACKS, "HCTapedPackMounts", "OnStart", module, env, NS())
        plan = [line for line in logs if isinstance(line, str) and "HC-52 pack_pairs=" in line]
        self.assertEqual(1, len(plan))
        for field in ("pack_pairs=1", "cross_slot=off", "qualified=0", "state=off",
                      "authored=1 admitted=0 observed=0", "runtime=PENDING"):
            self.assertIn(field, plan[0])
        pair_lines = [line for line in logs if isinstance(line, str) and "HC-52 pair=" in line]
        self.assertEqual(2, len(pair_lines))
        self.assertIn(("off", "pack_mount_geometry_pending"), logs)
        self.assertTrue(gate.Configure(NS(crossSlotLights=True, permittedPairIds=EArray([
            "tortilla_universal_cross"]))))
        helmet_member(PACKS, "HCTapedPackMounts", "OnStop", module, env)
        self.assertFalse(gate.CrossSlotEnabled())
        self.assertFalse(module.mHCStarted)
        self.assertEqual([], gate.mHCPermitted)
        self.assertIn("stop", logs)
        self.assertEqual("PENDING", manifest["RuntimeAcceptance"])
        self.assertEqual([], manifest["DistancesAdded"])
        self.assertFalse(manifest["Qualified"])

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
    def test_helmet_manifest_refuses_unsupported_pairs_and_unqualified_binding(self):
        # HC-23 spec/plan/task: exactly one native pair, no proxy authoring;
        # queue other helmets, preserve HC-7 ownership, keep runtime=PENDING.
        # Synthetic rows/entities/config outputs. The baseline uses HC-7's
        # generic identity predicate until the helmet allowlist exists: an
        # operator-authored unsupported row must not become its own evidence.
        def matches(row, host, light, slot):
            if not WEARABLE.exists():
                from tests.unit.test_taped_light_v1 import member
                return member(CATALOG, "HCTapedLightCatalog", "Matches", NS(),
                              {}, row, host, light, slot)
            state = NS()
            state.Supported = lambda candidate: helmet_member(
                WEARABLE, "HCTapedWearableCatalog", "Supported", state, {}, candidate)
            return helmet_member(WEARABLE, "HCTapedWearableCatalog", "Matches",
                                 state, {}, row, host, light, slot)

        unsupported = NS(HostClass="ConstructionHelmet_Orange", LightClass="UniversalLight",
                         SlotName="helmetFlashlight", PrerequisiteSlot="", PrerequisiteClass="")
        self.assertFalse(matches(unsupported, unsupported.HostClass,
                                 unsupported.LightClass, unsupported.SlotName),
                         "unsupported helmet mount accepted from a self-declared row")
        manifest = json.loads(MANIFEST.read_text())
        rows = EArray(NS(**row) for row in manifest["NativePairs"])
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(("Mich2001Helmet", "UniversalLight", "helmetFlashlight"),
                         (row.HostClass, row.LightClass, row.SlotName))
        self.assertTrue(matches(row, row.HostClass, row.LightClass, row.SlotName))
        for host, light, slot in (("mich2001helmet", row.LightClass, row.SlotName),
                                  ("Mich2001Helmet_Black", row.LightClass, row.SlotName),
                                  (row.HostClass, "Flashlight", row.SlotName),
                                  (row.HostClass, "TLRLight", row.SlotName),
                                  (row.HostClass, row.LightClass, "weaponFlashlight")):
            with self.subTest(host=host, light=light, slot=slot):
                self.assertFalse(matches(row, host, light, slot))
                forged = NS(HostClass=host, LightClass=light, SlotName=slot,
                            PrerequisiteSlot="", PrerequisiteClass="")
                self.assertFalse(matches(forged, host, light, slot))
        state = NS(Supported=lambda candidate: matches(
            candidate, candidate.HostClass, candidate.LightClass, candidate.SlotName))
        for candidates, expected in ((rows, True), (None, False), (EArray(), False),
                                      (EArray([unsupported]), False),
                                      (EArray([row, row]), False),
                                      (EArray([row, unsupported]), False)):
            self.assertEqual(expected, helmet_member(
                WEARABLE, "HCTapedWearableCatalog", "ManifestAllowed", state, {}, candidates))
        self.assertIn(hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), WEARABLE.read_text())
        compiled = re.findall(r'HCTapedLightCatalog.Add\(rows, "([^"]+)", "([^"]+)", "([^"]+)", "([^"]*)", "([^"]*)"\)', WEARABLE.read_text())
        self.assertEqual([tuple(vars(row).values()) for row in rows], compiled)
        queued = re.findall(r'rows.Insert\("([^"]+)"\)', WEARABLE.read_text())
        self.assertEqual([row["HostClass"] for row in manifest["CompatibilityQueue"]], queued)
        self.assertEqual("PENDING", manifest["RuntimeAcceptance"])
        self.assertFalse(manifest["Qualified"])
        self.assertEqual(3, len(manifest["CompatibilityQueue"]))
        for candidate in manifest["CompatibilityQueue"]:
            self.assertEqual("PENDING", candidate["RuntimeAcceptance"])
            self.assertFalse(matches(unsupported, candidate["HostClass"], "UniversalLight", "helmetFlashlight"))

        # A marker/HC-7 opt-in cannot qualify helmets. No inventory/light port
        # is supplied: any mutation attempted by this off path fails the test.
        self.assertFalse(helmet_member(WEARABLE, "HCTapedWearableCatalog", "Qualified", NS(), {}))
        self.assertFalse(helmet_member(HELMETS, "HCTapedHelmetQualification", "Ready", NS(),
                                      {"HCTapedWearableCatalog": NS(Qualified=lambda: False)}))
        for host in (None, NS(), unsupported):
            self.assertIsNone(helmet_member(HELMETS, "HCTapedHelmetQualification", "Resolve",
                                           NS(), {}, host, NS()))
        for host, expected in ((row.HostClass, "helmet_mount_two_client_pending"),
                               (unsupported.HostClass, "unsupported_helmet_pair")):
            self.assertEqual(expected, helmet_member(
                WEARABLE, "HCTapedWearableCatalog", "Refusal", NS(), {}, host, "UniversalLight", "helmetFlashlight"))

        # Explicit synthetic config API; absence on either end, foreign build
        # or a client must refuse without inferring a mount from inheritance.
        slots = {"CfgVehicles Mich2001Helmet attachments": EArray(["helmetFlashlight"]),
                 "CfgVehicles UniversalLight inventorySlot": EArray(["helmetFlashlight"])}
        probes = []
        def config(path, out):
            probes.append(path)
            out.extend(slots[path])
        server, build_ok = True, True
        native_env = dict(GetGame=lambda: NS(IsServer=lambda: server, ConfigGetTextArray=config),
                          HCBuildIdentity=NS(Matches=lambda build: build_ok,
                                             SeenBuild=lambda: "synthetic-build"), NewSlots=EArray)
        available = lambda: helmet_member(HELMETS, "HCTapedHelmetMounts", "NativeSlotAvailable", NS(), native_env)
        self.assertTrue(available())
        for path in slots:
            saved = slots[path]
            slots[path] = EArray()
            self.assertFalse(available())
            slots[path] = saved
        probes.clear()
        server = False
        self.assertFalse(available())
        server, build_ok = True, False
        self.assertFalse(available())
        self.assertEqual([], probes)
        logs, status = [], NS(HCPublish=lambda *args: logs.append(args), HCStop=lambda: logs.append("stop"))
        module = NS(mHCStarted=False, mHCStatus=status)
        self.assertIs(status, helmet_member(HELMETS, "HCTapedHelmetMounts", "HCGetOperationalStatus", module, {}))
        env = dict(Print=logs.append, HCV2Admission=NS(Line=lambda *args: "synthetic admission"),
                   HCTapedWearableCatalog=NS(Rows=lambda: rows,
                                            CompatibilityQueue=lambda: EArray(queued)))
        module.NativeSlotAvailable = lambda: True
        for _ in range(2):
            helmet_member(HELMETS, "HCTapedHelmetMounts", "OnStart", module, env, NS())
        plan = [line for line in logs if isinstance(line, str) and line.startswith("[HC Plan] HC-23 ")]
        self.assertEqual(1, len(plan))
        for field in ("helmet_mounts=1", "qualified=0", "unsupported=3", "state=off",
                      "reason=helmet_mount_two_client_pending", "runtime=PENDING"):
            self.assertIn(field, plan[0])
        helmet_member(HELMETS, "HCTapedHelmetMounts", "OnStop", module, env)
        self.assertFalse(module.mHCStarted)
        self.assertIn("stop", logs)
        module.NativeSlotAvailable = lambda: False
        helmet_member(HELMETS, "HCTapedHelmetMounts", "OnStart", module, env, NS())
        self.assertIn(("off", "helmet_native_slot_unavailable"), logs)

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
