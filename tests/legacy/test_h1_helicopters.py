"""H1 helicopters: pending Workshop dependency plus the provider-optional HC policy.

Synthetic fixtures only. The authored Enforce bodies run through the admin test
kit's statement-level adapter with explicit fake collaborators; nothing here
establishes DayZ, Expansion or Workshop behaviour (runtime acceptance pending).
"""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace as NS

from tests.legacy.test_admin_test_kit import Cell, base_scope, compile_authored, strip_comments
from tests.legacy.test_group_server import EArray
from tools.setup import workshop_sync as ws

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tools/setup/workshop_mods.json"
POLICY = ROOT / "mods/HollowCountry/scripts/4_World/Vehicles/HCHeliPolicy.c"
VEHICLES_ID = "2291785437"
LICENSED_ID = "2116157322"


class S(str):
    """Synthetic Enforce string: only the Length() the bodies call."""
    def Length(self):
        return len(self)


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class ActiveDependency(unittest.TestCase):
    # Owner subscribed 2026-11-19; the pair is now an active client dependency.
    def test_helicopter_provider_is_active(self):
        data = manifest()
        self.assertFalse(data.get("pending_mods"))
        active = {m["id"]: m for m in data["mods"]}
        for mod_id in (VEHICLES_ID, LICENSED_ID):
            self.assertIn(mod_id, active)
            self.assertEqual(("client", "pve_patrols", False), (active[mod_id]["side"], active[mod_id]["group"], active[mod_id]["publish"]))

    def test_active_entries_load_between_core_and_ai(self):
        loaded = ws.load_manifest(MANIFEST)
        order = [m["folder"] for m in loaded["mods"]]
        core, ai = order.index("@Expansion-Core"), order.index("@Expansion-AI")
        self.assertLess(core, order.index("@Expansion-Licensed"))
        self.assertLess(order.index("@Expansion-Licensed"), order.index("@Expansion-Vehicles"))
        self.assertLess(order.index("@Expansion-Vehicles"), ai)
        self.assertFalse([f for f in order if f.startswith("@Expansion") and "Animations" in f], "Expansion-Animations is not allowed")


class ConfigValidity(unittest.TestCase):
    FIELDS = ("Version", "ProviderPatch", "VehicleClasses", "MaxTracked", "WorldCap", "MaxTypeCache", "SpawnFuelMaxFraction")

    def config(self, **change):
        values = dict(Version=1, ProviderPatch=S("DayZExpansion_Vehicles_Scripts"),
                      VehicleClasses=EArray([S("Expansion_Helicopter")]), MaxTracked=16,
                      WorldCap=4, MaxTypeCache=128, SpawnFuelMaxFraction=0.1)
        values.update(change)
        registry = NS(HCFind=lambda key: False, HCValid=lambda key, value: True)
        fn = compile_authored(POLICY, "HCHeliPolicyConfig", "HCValid", base_scope(HCOperatorSettingsRegistry=registry),
                              modded=False, fields=self.FIELDS)
        return fn(NS(**values))

    def test_defaults_are_valid(self):
        self.assertTrue(self.config())

    def test_out_of_range_values_are_refused(self):
        nan = float("nan")
        for change in (dict(Version=2), dict(MaxTracked=0), dict(MaxTracked=65), dict(WorldCap=-1),
                       dict(WorldCap=17), dict(MaxTypeCache=0), dict(SpawnFuelMaxFraction=0.36),
                       dict(SpawnFuelMaxFraction=-0.01), dict(SpawnFuelMaxFraction=nan),
                       dict(ProviderPatch=S("")), dict(VehicleClasses=EArray([])),
                       dict(VehicleClasses=EArray([S("")])), dict(VehicleClasses=None)):
            with self.subTest(change=change):
                self.assertFalse(self.config(**change))

    def test_registry_rows_apply_once_mirrored(self):
        seen = []
        registry = NS(HCFind=lambda key: True, HCValid=lambda key, value: seen.append(key) or key != "Helicopters.WorldCap")
        fn = compile_authored(POLICY, "HCHeliPolicyConfig", "HCValid", base_scope(HCOperatorSettingsRegistry=registry),
                              modded=False, fields=self.FIELDS)
        self.assertFalse(fn(NS(Version=1, ProviderPatch=S("P"), VehicleClasses=EArray([S("C")]), MaxTracked=16,
                               WorldCap=4, MaxTypeCache=128, SpawnFuelMaxFraction=0.1)))
        self.assertIn("Helicopters.WorldCap", seen)


class PolicyDecisions(unittest.TestCase):
    def fn(self, name):
        return compile_authored(POLICY, "HCHeliPolicy", name, base_scope(), modded=False)

    def test_vehicle_class_match_is_exact(self):
        match = self.fn("HCClassMatch")
        classes = EArray(["Expansion_Helicopter"])
        self.assertTrue(match(None, classes, "Expansion_Helicopter"))
        self.assertFalse(match(None, classes, "Expansion_Car"))
        self.assertFalse(match(None, classes, ""))
        self.assertFalse(match(None, None, "Expansion_Helicopter"))

    def test_spawn_fuel_is_capped_to_the_policy_fraction(self):
        excess = self.fn("HCExcessFuel")
        self.assertAlmostEqual(25.0, excess(None, 100.0, 0.35, 0.1))
        self.assertEqual(0, excess(None, 100.0, 0.05, 0.1))
        self.assertEqual(0, excess(None, 0.0, 0.5, 0.1))

    def test_tracking_is_bounded_and_idempotent(self):
        admit = self.fn("HCAdmit")
        tracked = EArray([])
        a, b, c = object(), object(), object()
        self.assertEqual(0, admit(None, tracked, a, 2))
        self.assertEqual(1, admit(None, tracked, a, 2))
        self.assertEqual(0, admit(None, tracked, b, 2))
        self.assertEqual(2, admit(None, tracked, c, 2))
        self.assertEqual([a, b], list(tracked))
        self.assertEqual(3, admit(None, tracked, None, 2))

    def test_status_is_derived_never_fixed(self):
        derive = self.fn("HCDerive")
        cases = [
            ((False, True, True, True, 0, 4, 0), "off", "helicopters_not_started"),
            ((True, False, True, True, 0, 4, 0), "off", "operator_disabled"),
            ((True, True, False, True, 0, 4, 0), "refused", "HELI_CONFIG_INVALID"),
            ((True, True, True, False, 0, 4, 0), "off", "HELI_PROVIDER_NOT_LOADED"),
            ((True, True, True, True, 3, 4, 1), "degraded", "HELI_TRACK_CAP"),
            ((True, True, True, True, 5, 4, 0), "degraded", "HELI_OVER_WORLD_CAP"),
            ((True, True, True, True, 4, 4, 0), "ready", "provider_loaded_policy_active_runtime_pending"),
        ]
        for args, state, reason in cases:
            with self.subTest(args=args):
                cell = Cell()
                self.assertEqual(state, derive(None, *args, cell))
                self.assertEqual(reason, cell.value)


class SyntheticCar:
    """Explicit fake tank and provider classification, with identity semantics."""
    def __init__(self, helicopter=True):
        self.this = self
        self.helicopter = helicopter
        self.fraction = 0.35
        self.m_HCHeliOverflow = False
        self.leaks = []

    def GetType(self):
        return "heli" if self.helicopter else "car"

    def GetFluidCapacity(self, fluid):
        return 100.0

    def GetFluidFraction(self, fluid):
        return self.fraction

    def Leak(self, fluid, litres):
        self.leaks.append(litres)
        self.fraction -= litres / 100.0


class EventLifecycle(unittest.TestCase):
    def setUp(self):
        # Admission/config are explicit synthetic preconditions; no disk or engine.
        self.publications, self.owner_events = [], []
        owner = NS(HCObserve=lambda *args: self.owner_events.append("observe"),
                   HCStop=lambda *args: self.owner_events.append("stop"))
        self.policy = NS(s_Admission=True, s_Active=True, s_Enabled=True,
                         s_Provider=True, s_Overflow=0, s_Shaped=0, s_Refusal="", s_Line="",
                         s_Config=NS(MaxTracked=1, WorldCap=1, SpawnFuelMaxFraction=0.1),
                         s_Tracked=EArray([]), s_Owner=owner,
                         s_Status=NS(HCPublish=lambda state, reason: self.publications.append(state)))
        fields = tuple(self.policy.__dict__)
        methods = ("HCEnabled", "HCTrack", "HCUntrack", "HCSpawnFuel", "HCAdmit",
                   "HCExcessFuel", "HCPublishStatus", "HCGetOperationalStatus", "HCStart", "HCStop")
        derive = compile_authored(POLICY, "HCHeliPolicy", "HCDerive", base_scope(), modded=False)
        # This fake bridges the native out-string argument; status decisions still
        # execute the authored HCDerive. Reason values have separate direct tests.
        self.policy.HCDerive = lambda *args: derive(None, *args[:-1], Cell())
        self.policy.HCIsHelicopter = lambda name: name == "heli"
        self.policy.HCRefuse = lambda reason: None
        scope = base_scope(GetGame=lambda: NS(GetTickTime=lambda: 1.0),
                           CarFluid=NS(FUEL=0), Print=lambda line: None,
                           HCOperationalContributors=NS(HCRegisterOwner=lambda name: owner))
        for name in methods:
            fn = compile_authored(POLICY, "HCHeliPolicy", name, scope,
                                  members=methods + ("HCDerive", "HCIsHelicopter", "HCRefuse"),
                                  fields=fields, modded=False)
            setattr(self.policy, name, MethodType(fn, self.policy))
        # Execute the actual authored hooks, with explicit no-op vanilla super.
        hooks = NS(EEInit=lambda: None, EEOnCECreate=lambda: None, EEDelete=lambda parent: None)
        self.hooks = {name: compile_authored(POLICY, "CarScript", name,
                      base_scope(HCHeliPolicy=self.policy, super=hooks), fields=("this",))
                      for name in ("EEInit", "EEOnCECreate", "EEDelete")}

    def test_overflow_init_ce_delete_caps_fuel_and_recovers(self):
        a, b = SyntheticCar(), SyntheticCar()
        self.hooks["EEInit"](a)
        self.hooks["EEInit"](b)
        self.hooks["EEOnCECreate"](b)
        self.assertAlmostEqual(0.1, b.fraction)
        self.assertEqual(1, self.policy.s_Overflow)
        self.hooks["EEInit"](b)
        self.hooks["EEOnCECreate"](b)
        self.assertEqual(1, self.policy.s_Overflow)
        self.assertEqual(1, len(b.leaks))
        self.hooks["EEDelete"](b, None)
        self.assertEqual(0, self.policy.s_Overflow)
        self.assertEqual("ready", self.publications[-1])
        self.hooks["EEDelete"](b, None)
        self.assertEqual(0, self.policy.s_Overflow)

    def test_capacity_return_recovers_and_callback_promotes_survivor(self):
        a, b = SyntheticCar(), SyntheticCar()
        self.hooks["EEInit"](a)
        self.hooks["EEInit"](b)
        self.assertEqual("degraded", self.publications[-1])
        self.hooks["EEDelete"](a, None)
        self.assertEqual("ready", self.publications[-1])
        self.hooks["EEInit"](b)
        self.assertEqual([b], list(self.policy.s_Tracked))
        self.assertEqual(0, self.policy.s_Overflow)
        self.hooks["EEDelete"](b, None)
        self.assertEqual([], list(self.policy.s_Tracked))

    def test_non_helicopter_fuel_is_untouched(self):
        car = SyntheticCar(helicopter=False)
        self.hooks["EEInit"](car)
        self.hooks["EEOnCECreate"](car)
        self.assertEqual([], car.leaks)
        self.assertEqual([], list(self.policy.s_Tracked))
        self.hooks["EEDelete"](car, None)
        self.assertEqual([], self.publications)

    def test_stop_callbacks_getter_and_restart(self):
        self.policy.HCStart()
        self.assertEqual("ready", self.publications[-1])
        self.policy.HCStop()
        self.assertEqual("off", self.publications[-1])
        self.assertEqual("stop", self.owner_events[-1])
        car = SyntheticCar()
        self.hooks["EEInit"](car)
        self.hooks["EEOnCECreate"](car)
        self.policy.HCGetOperationalStatus()
        self.assertEqual("off", self.publications[-1])
        self.assertFalse(self.policy.HCEnabled())
        self.assertEqual([], car.leaks)
        self.assertEqual([], list(self.policy.s_Tracked))
        self.policy.HCStart()
        self.assertTrue(self.policy.HCEnabled())
        self.hooks["EEInit"](car)
        self.hooks["EEOnCECreate"](car)
        self.assertAlmostEqual(0.1, car.fraction)
        self.assertEqual("ready", self.publications[-1])


class SourceContract(unittest.TestCase):
    def setUp(self):
        self.text = POLICY.read_text(encoding="utf-8")
        self.code = re.sub(r'"(?:\\.|[^"\\])*"', '""', strip_comments(self.text))

    def test_no_provider_symbol_so_base_mod_loads_without_it(self):
        self.assertNotRegex(self.code, r"\bExpansion\w*")
        self.assertNotRegex(self.code, r"#ifdef")

    def test_admission_opt_out_and_pending_wording(self):
        self.assertIn('HCV2Admission.Line("Helicopters"', self.text)
        self.assertIn('"$profile:HollowCountry/acceptance/helicopters.disable"', self.text)
        self.assertIn("overflight=pending_flight_api runtime=PENDING", self.text)
        self.assertIn('HCEncounterStore<HCHeliPolicyConfig>("helicopters")', self.text)
        self.assertNotIn('HCPublish("ready"', self.text)
        self.assertIn('HCOperationalContributors.HCRegisterOwner("Helicopters")', self.text)

    def test_vehicle_hooks_chain_super_first(self):
        self.assertRegex(self.code, r"override void EEInit\(\)\s*\{\s*super\.EEInit\(\);\s*HCHeliPolicy\.HCTrack\(this\);")
        self.assertRegex(self.code, r"override void EEOnCECreate\(\)\s*\{\s*super\.EEOnCECreate\(\);\s*HCHeliPolicy\.HCSpawnFuel\(this\);")
        self.assertRegex(self.code, r"override void EEDelete\(EntityAI parent\)\s*\{\s*HCHeliPolicy\.HCUntrack\(this\);\s*super\.EEDelete\(parent\);")

    def test_no_banned_text(self):
        lowered = self.text.lower()
        for banned in ("snafu", "tactical" + "flava", "2646817942", "2291785308", "2792982069", VEHICLES_ID, LICENSED_ID):
            self.assertNotIn(banned, lowered)


if __name__ == "__main__":
    unittest.main()
