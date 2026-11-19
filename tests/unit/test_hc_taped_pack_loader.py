"""#58 / HC-52: backpack light-mount manifest loader wiring; runtime=PENDING.

Spec: the mission manifest lights/backpack-mounts.json is the only settings
source (cross-slot lights default on); the module loads it once at start behind
HCJsonFields presence guards, calls Configure(), and publishes a readiness line.
Qualified() stays false; admission is unverified and still needs native slots. Fixtures are SYNTHETIC: the JSON
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
CATALOG = ROOT / "mods/HollowCountry/scripts/3_Game/Survival/HCTapedLightCatalog.c"
MANIFEST = ROOT / "mission/hollow-country/lights/backpack-mounts.json"
PATH = "$mission:hollow-country/lights/backpack-mounts.json"


def member(path, cls, method, state, env, *args):
    text = path.read_text()
    match = re.search(r'class ' + cls + r'\b[^\{]*\{', text)
    source = body(text, match.end())
    source = re.sub(r'\b(?:TStringArray|HCTapedPackManifest|HCTapedPackSettingsContract|'
                    r'HCTapedLightMountSettings|HCTapedPairReceipts|HCTapedPairReceipt|HCTapedReceiptRows|HCTapedReceiptRow|'
                    r'array<ref HCTapedPairReceipt>|array<ref HCTapedReceiptRow>|array<ref HCTapedLightHostRow>|HCTapedLightHostRow)\s+(?=\w+\s*[=;])', 'HCGroupNative ', source)
    source = source.replace('new TStringArray', 'NewSlots()')
    source = re.sub(r'(\w+)\.ToString\(\)', r'str(\1)', source)
    # Native string members on Python str: Get/Substring/IndexOf/IndexOfFrom.
    source = re.sub(r'(\w+)\.Get\(([^()]+)\)', r'\1[\2]', source)
    source = re.sub(r'(\w+)\.Substring\((\w+), (\d+)\)', r'\1[\2:\2 + \3]', source)
    source = re.sub(r'(\w+)\.IndexOfFrom\((\w+), (\w+)\)', r'\1.find(\3, \2)', source)
    source = re.sub(r'(\w+)\.IndexOf\((\w+)\)', r'\1.find(\2)', source)
    source = re.sub(r'\bTStringArray (?=(?:PairIds|ReceiptPairIds|CrossPairIds)\()', 'int ', source)
    source = re.sub(r'\b(?:HCTapedPackManifest|HCTapedPairReceipts|HCTapedReceiptRows|HCOperationalStatus) (?=(?:ParseManifest|ParseReceipts|ParseOptOuts|HCGetOperationalStatus)\()',
                    'int ', source)
    source = re.sub(r'\bHCTapedLightHostRow (?=(?:CrossRow|CrossRowFor|CrossRowMatch)\()', 'int ', source)
    return ui_member(source, method, state, dict(env), *args)


def scan(text, key, depth):
    """Synthetic stand-in for HCJsonFields.Check: key present at the object depth."""
    data = json.loads(text)
    if depth == 1:
        return key in data
    return any(isinstance(v, dict) and key in v for v in data.values())


def scan_every(text, key, depth):
    """Synthetic stand-in for HCJsonFields.Every at depth 3: every row object in
    every top-level array carries the key (an empty array passes)."""
    assert depth == 3
    data = json.loads(text)
    rows = [row for v in data.values() if isinstance(v, list) for row in v if isinstance(row, dict)]
    return all(key in row for row in rows)


def light_catalogue():
    """Executes the authored HCTapedLightCatalog cross-pair derivation over the
    compiled Add(rows, ...) data. The row list is parsed from the source text; the
    derivation rule itself is the authored code, not a copy."""
    rows = EArray(NS(HostClass=a, LightClass=b, SlotName=c, PrerequisiteSlot=d, PrerequisiteClass=e, PairId="")
                  for a, b, c, d, e in re.findall(
                      r'Add\(rows, "([^"]+)", "([^"]+)", "([^"]+)", "([^"]*)", "([^"]*)"\)',
                      CATALOG.read_text()))
    catalogue = NS(Rows=lambda: rows, rows=rows)
    env = {"NewSlots": EArray, "Rows": catalogue.Rows,
           "HCTapedLightHostRow": lambda: NS(HostClass="", LightClass="", SlotName="",
                                             PrerequisiteSlot="", PrerequisiteClass="", PairId="")}
    for name in ("CrossLightClass", "CrossPairId", "CrossPairIds", "CrossRowFor", "CrossRow", "CrossRowMatch"):
        setattr(catalogue, name, lambda *a, name=name: member(
            CATALOG, "HCTapedLightCatalog", name, catalogue, env, *a))
    return catalogue


def build(text, build_ok=True, files=None, receipts=""):
    """Executes the authored PackMounts handlers against explicit fakes."""
    catalog = NS()
    lights = light_catalogue()
    for name in ("KnownPair", "Matches", "Qualified", "SlotName", "Refusal", "PairIds", "ReceiptPairIds"):
        setattr(catalog, name, lambda *a, name=name: member(
            WEARABLE, "HCTapedPackCatalog", name, catalog,
            {"NewSlots": EArray, "HCTapedLightCatalog": lights}, *a))
    probes = []
    gate = NS(mHCCrossSlot=False, mHCPermitted=EArray(), mHCConfigured=False, probes=probes,
              mHCSettingOn=False, mHCChecked=EArray(), mHCReceiptMaxBytes=0,
              mHCStarted=False, mHCDisabled=EArray(), mHCReceiptReason="",
              mHCWeaponAdmitted=EArray(), mHCWeaponFirstRefusal="", mHCWeaponRefused=0)
    logs = []
    manifest_text = {"value": text}
    receipt_text = {"value": receipts}
    env = dict(
        GetGame=lambda: NS(IsServer=lambda: True,
                           ConfigGetTextArray=lambda p, out: out.extend([])),
        HCBuildIdentity=NS(Matches=lambda b: build_ok, SeenBuild=lambda: "synthetic"),
        HCTapedPackCatalog=catalog, HCTapedLightCatalog=lights, NewSlots=EArray,
        HCJsonFields=NS(Has=lambda t, k: scan(t, k, 1),
                        Every=scan_every,
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
             "BindingAllowed", "ApplyManifest", "LoadSettings", "ReadManifest", "ParseManifest",
             "ApplyReceipts", "ReceiptCheckedTyped", "ReceiptBoolTyped", "ValidCheckDate", "DateNumber", "LoadReceipts", "ReadReceipts", "ParseReceipts", "ParseOptOuts", "ReceiptChecked",
             "ReceiptDisabled", "PairAdmission", "PairQualified", "AdmittedCount", "VerifiedCount", "FirstAdmissionReason", "OnStart",
             "WeaponPairAdmission", "WeaponNativeSlotAvailable", "WeaponPairAdmitted", "WeaponBindingAllowed", "HCRefreshWeaponAdmission",
             "ReceiptPackChecked", "ReceiptWeaponChecked", "PackRefusedCount",
             "ReceiptKeysUnescaped", "ReceiptCoveredChecked")
    for name in names:
        setattr(gate, name, lambda *a, name=name: member(PACKS, "HCTapedPackMounts", name, gate, env, *a))
    gate.ReadManifest = lambda: manifest_text["value"]
    gate.ParseManifest = parse
    gate.ReadReceipts = lambda: receipt_text["value"]
    gate.ParseReceipts = parse
    def parse_opt_outs(t):
        # SYNTHETIC codec: an absent optional bool loads as false, like the native default.
        data = parse(t)
        for row in data.Receipts:
            if not hasattr(row, "Disabled"):
                row.Disabled = False
        return data
    gate.ParseOptOuts = parse_opt_outs
    gate.receipt_text = receipt_text
    gate.manifest_text = manifest_text
    gate.logs = logs
    gate.env = env
    return gate


def start(gate, setting=False):
    """Runs the authored OnStart on the gate itself so all mHC state is shared."""
    published = []
    gate.mHCStatus = NS(HCPublish=lambda *a: published.append(a),
                        HCStop=lambda: published.append("stop"))
    gate.mHCStarted = False
    member(PACKS, "HCTapedPackMounts", "OnStart", gate, gate.env,
           NS(EnableTapedPackMounts=setting))
    return gate, published


class TapedPackLoaderTests(unittest.TestCase):
    def real(self):
        return MANIFEST.read_text()

    def test_manifest_defaults_exist_at_the_depths_the_guards_read(self):
        data = json.loads(self.real())
        contract = data["SettingsContract"]
        self.assertIs(True, contract["DefaultCrossSlotLights"])
        self.assertEqual(["tortilla_universal_cross"], contract["DefaultPermittedPairIds"])
        self.assertEqual(2, contract["MaxPermittedPairIds"])
        self.assertIs(False, data["Qualified"])

    def test_manifest_text_names_itself_the_runtime_input_without_pending_integration_claims(self):
        text = self.real()
        contract = json.loads(text)["SettingsContract"]
        self.assertNotIn("lead-owned integration pending", text)
        self.assertNotIn("DefaultsFile", text)
        self.assertIn("HCTapedPackMounts.ReadManifest/ApplyManifest", contract["RuntimeInput"])
        self.assertIn("EnableTapedPackMounts", contract["RuntimeInput"])
        self.assertIn("Qualified() stays false", contract["RuntimeInput"])
        self.assertIn("offline mirror", contract["OfflineMirror"])
        self.assertIn("config/hollow-country-light-mounts.json", contract["OfflineMirror"])

    def test_real_manifest_configures_enabled_defaults_without_any_attach(self):
        gate = build(self.real())
        self.assertEqual("", gate.ApplyManifest(self.real()))
        self.assertTrue(gate.mHCConfigured)
        self.assertTrue(gate.CrossSlotEnabled())
        self.assertEqual(["tortilla_universal_cross"], gate.mHCPermitted)

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
        self.assertIn(("off", "setting_off"), published)
        plan = [x for x in gate.logs if isinstance(x, str) and "HC-52 pack_pairs=" in x]
        self.assertEqual(1, len(plan))
        for field in ("config=loaded", "cross_slot=on", "qualified=0", "state=off",
                      "reason=setting_off", "admitted=0", "runtime=PENDING"):
            self.assertIn(field, plan[0])

    def test_enabled_cross_slot_needs_its_native_slot_then_is_admitted_unverified(self):
        data = json.loads(self.real())
        data["SettingsContract"]["DefaultCrossSlotLights"] = True
        data["SettingsContract"]["DefaultPermittedPairIds"] = ["tortilla_universal_cross"]
        gate = build(json.dumps(data), receipts=(ROOT / "mission/hollow-country/lights/pair-receipts.json").read_text())
        module, published = start(gate, setting=True)
        self.assertTrue(gate.CrossSlotEnabled())
        # Wave 16: the synthetic config has no native slot arrays, so the pair is a
        # named refusal and the module stays ready (loaded, nothing degraded).
        self.assertIn(("ready", "pack_native_slot_unavailable"), published)
        binding = NS(HostConfigRoot="CfgVehicles", PairId="tortilla_universal_cross",
                     HostClass="TortillaBag", LightClass="UniversalLight",
                     SlotName="Chemlight", CrossSlot=True)
        self.assertFalse(gate.BindingAllowed(binding))
        plan = [x for x in gate.logs if isinstance(x, str) and "HC-52 pack_pairs=" in x][0]
        self.assertIn("state=ready", plan)
        self.assertIn("permitted=1", plan)
        # SYNTHETIC native slot arrays: now cross is admitted unverified, nothing more.
        slots = {"CfgVehicles TortillaBag attachments": ["Chemlight", "helmetFlashlight"],
                 "CfgVehicles UniversalLight inventorySlot": ["Chemlight", "helmetFlashlight"]}
        gate.env["GetGame"] = lambda: NS(IsServer=lambda: True,
                                         ConfigGetTextArray=lambda p, out: out.extend(slots.get(p, [])))
        module, published = start(gate, setting=True)
        self.assertIn(("ready", "admitted_unverified"), published)
        self.assertTrue(gate.BindingAllowed(binding))
        self.assertEqual(0, gate.VerifiedCount())

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
