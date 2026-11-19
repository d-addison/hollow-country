"""#58 / HC-52: backpack light-mount manifest loader wiring; runtime=PENDING.

Spec: the mission manifest lights/backpack-mounts.json is the only settings
source (it holds the closed defaults); the module loads it once at start behind
HCJsonFields presence guards, calls Configure(), and publishes a readiness line.
Qualified() stays false, so no pair attaches. Fixtures are SYNTHETIC: the JSON
codec, file read and HCJsonFields scan are explicit fakes; native behaviour is
not established here.
"""
import json
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import EArray, body
from tests.unit.test_group_ui import ui_member

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "mods/HollowCountry/scripts/4_World/Survival/HCTapedPackMounts.c"
WEARABLE = ROOT / "mods/HollowCountry/scripts/3_Game/Survival/HCTapedWearableCatalog.c"
MANIFEST = ROOT / "mission/hollow-country/lights/backpack-mounts.json"
PATH = "$mission:hollow-country/lights/backpack-mounts.json"


def member(path, cls, method, state, env, *args):
    text = path.read_text()
    match = re.search(r'class ' + cls + r'\b[^\{]*\{', text)
    source = body(text, match.end())
    source = re.sub(r'\b(?:TStringArray|HCTapedPackManifest|HCTapedPackSettingsContract|'
                    r'HCTapedLightMountSettings)\s+(?=\w+\s*[=;])', 'HCGroupNative ', source)
    source = source.replace('new TStringArray', 'NewSlots()')
    source = re.sub(r'(\w+)\.ToString\(\)', r'str(\1)', source)
    source = re.sub(r'\b(?:HCTapedPackManifest|HCOperationalStatus) (?=(?:ParseManifest|HCGetOperationalStatus)\()',
                    'int ', source)
    return ui_member(source, method, state, dict(env), *args)


def scan(text, key, depth):
    """Synthetic stand-in for HCJsonFields.Check: key present at the object depth."""
    data = json.loads(text)
    if depth == 1:
        return key in data
    return any(isinstance(v, dict) and key in v for v in data.values())


def build(text, build_ok=True, files=None):
    """Executes the authored PackMounts handlers against explicit fakes."""
    catalog = NS()
    for name in ("KnownPair", "Matches", "Qualified", "SlotName", "Refusal"):
        setattr(catalog, name, lambda *a, name=name: member(
            WEARABLE, "HCTapedPackCatalog", name, catalog, {}, *a))
    probes = []
    gate = NS(mHCCrossSlot=False, mHCPermitted=EArray(), mHCConfigured=False, probes=probes)
    logs = []
    manifest_text = {"value": text}
    env = dict(
        GetGame=lambda: NS(IsServer=lambda: True,
                           ConfigGetTextArray=lambda p, out: out.extend([])),
        HCBuildIdentity=NS(Matches=lambda b: build_ok, SeenBuild=lambda: "synthetic"),
        HCTapedPackCatalog=catalog, NewSlots=EArray,
        HCJsonFields=NS(Has=lambda t, k: scan(t, k, 1),
                        Check=lambda t, k, d, every: scan(t, k, d)),
        HCGroupIO=NS(), Print=logs.append,
        HCTapedLightMountSettings=lambda: NS(crossSlotLights=False, permittedPairIds=EArray()),
        HCV2Admission=NS(OnOff=lambda v: "on" if v else "off",
                         Line=lambda *a: "synthetic admission"))
    def parse(t):
        def hook(d):
            return NS(**{k: EArray(v) if isinstance(v, list) else v for k, v in d.items()})
        return json.loads(t, object_hook=hook)
    names = ("Configure", "Reset", "CrossSlotEnabled", "NativeSlotAvailable", "PairRefusal",
             "BindingAllowed", "ApplyManifest", "LoadSettings", "ReadManifest", "ParseManifest")
    for name in names:
        setattr(gate, name, lambda *a, name=name: member(PACKS, "HCTapedPackMounts", name, gate, env, *a))
    gate.ReadManifest = lambda: manifest_text["value"]
    gate.ParseManifest = parse
    gate.logs = logs
    gate.env = env
    return gate


def start(gate):
    published = []
    status = NS(HCPublish=lambda *a: published.append(a), HCStop=lambda: published.append("stop"))
    module = NS(mHCStarted=False, mHCStatus=status, mHCPermitted=gate.mHCPermitted)
    for name in ("PairRefusal", "CrossSlotEnabled", "Reset", "LoadSettings"):
        setattr(module, name, getattr(gate, name))
    module.mHCPermitted = gate.mHCPermitted
    member(PACKS, "HCTapedPackMounts", "OnStart", module, gate.env, NS())
    return module, published


class TapedPackLoaderTests(unittest.TestCase):
    def real(self):
        return MANIFEST.read_text()

    def test_manifest_defaults_exist_at_the_depths_the_guards_read(self):
        data = json.loads(self.real())
        contract = data["SettingsContract"]
        self.assertIs(False, contract["DefaultCrossSlotLights"])
        self.assertEqual([], contract["DefaultPermittedPairIds"])
        self.assertEqual(2, contract["MaxPermittedPairIds"])
        self.assertIs(False, data["Qualified"])

    def test_real_manifest_configures_closed_defaults_without_any_attach(self):
        gate = build(self.real())
        self.assertEqual("", gate.ApplyManifest(self.real()))
        self.assertTrue(gate.mHCConfigured)
        self.assertFalse(gate.CrossSlotEnabled())
        self.assertEqual([], gate.mHCPermitted)

    def test_missing_nested_field_refuses_and_stays_unconfigured(self):
        data = json.loads(self.real())
        del data["SettingsContract"]["MaxPermittedPairIds"]
        text = json.dumps(data)
        gate = build(text)
        self.assertEqual("mount_manifest_fields_missing", gate.ApplyManifest(text))
        self.assertFalse(gate.mHCConfigured)

    def test_manifest_cannot_claim_qualification_or_bad_schema(self):
        for field, value, reason in (("Qualified", True, "mount_manifest_qualified_claim"),
                                     ("SchemaVersion", 2, "mount_manifest_schema")):
            data = json.loads(self.real())
            data[field] = value
            text = json.dumps(data)
            gate = build(text)
            self.assertEqual(reason, gate.ApplyManifest(text))
            self.assertFalse(gate.mHCConfigured)

    def test_unknown_or_oversize_pair_list_refuses_closed(self):
        for ids in (["nope"], ["tortilla_universal_cross", "tortilla_universal_cross"],
                    ["tortilla_universal_cross", "tortilla_universal_mount", "x"]):
            data = json.loads(self.real())
            data["SettingsContract"]["DefaultCrossSlotLights"] = True
            data["SettingsContract"]["DefaultPermittedPairIds"] = ids
            text = json.dumps(data)
            gate = build(text)
            self.assertEqual("pack_mount_settings_refused", gate.ApplyManifest(text), ids)
            self.assertFalse(gate.mHCConfigured)
            self.assertFalse(gate.CrossSlotEnabled())

    def test_start_loads_once_and_publishes_off_while_setting_off(self):
        gate = build(self.real())
        module, published = start(gate)
        self.assertTrue(gate.mHCConfigured)
        self.assertIn(("off", "cross_slot_disabled"), published)
        plan = [x for x in gate.logs if isinstance(x, str) and "HC-52 pack_pairs=" in x]
        self.assertEqual(1, len(plan))
        for field in ("config=loaded", "cross_slot=off", "qualified=0", "state=off",
                      "reason=cross_slot_disabled", "runtime=PENDING"):
            self.assertIn(field, plan[0])

    def test_enabled_cross_slot_is_refused_client_check_pending_and_never_attaches(self):
        data = json.loads(self.real())
        data["SettingsContract"]["DefaultCrossSlotLights"] = True
        data["SettingsContract"]["DefaultPermittedPairIds"] = ["tortilla_universal_cross"]
        gate = build(json.dumps(data))
        module, published = start(gate)
        self.assertTrue(gate.CrossSlotEnabled())
        self.assertIn(("refused", "client_check_pending"), published)
        binding = NS(HostConfigRoot="CfgVehicles", PairId="tortilla_universal_cross",
                     HostClass="TortillaBag", LightClass="UniversalLight",
                     SlotName="Chemlight", CrossSlot=True)
        self.assertFalse(gate.BindingAllowed(binding))
        plan = [x for x in gate.logs if isinstance(x, str) and "HC-52 pack_pairs=" in x][0]
        self.assertIn("state=refused", plan)
        self.assertIn("permitted=1", plan)

    def test_unreadable_or_invalid_manifest_degrades_with_reason(self):
        for text, reason in (("", "mount_manifest_unreadable"),
                             ("{\"SchemaVersion\": 1}", "mount_manifest_fields_missing")):
            gate = build(text)
            module, published = start(gate)
            self.assertFalse(gate.mHCConfigured)
            self.assertIn(("degraded", reason), published)
            self.assertFalse(gate.CrossSlotEnabled())

    def test_source_loads_the_mission_path_and_registers_the_module(self):
        source = PACKS.read_text()
        self.assertIn(PATH, source)
        self.assertEqual(1, len(re.findall(r'Register\(new HCTapedPackMounts', source)))
        self.assertIn("HCJsonFields.Has", source)
        self.assertNotIn("config/hollow-country-light-mounts.json", source)


if __name__ == "__main__":
    unittest.main()
