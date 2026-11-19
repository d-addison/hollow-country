"""#58 wave 16: taped light mounts are on by default; receipts are a verdict log; runtime=PENDING.

Owner decision 2026-11-19: "enable all features by default". EnableTapedPackMounts
is true everywhere. A pair is admitted unless its receipt row opts it out with
Disabled=true; Checked/CheckDate/Note stay the operator's record of a client
check. Admission is "admitted unverified" (the HCV2Admission pattern): no native
or two-client verdict is claimed. An unknown pair id or a malformed receipt file
still refuses the whole file and the module reports degraded with the reason.
Weapon cross-slot pairs (29 cross_<Host>_<Light> ids) get their own admission
path through the same receipt gate plus an honest native slot check.

Fixtures are SYNTHETIC: the file read, JSON codec, native slot arrays, HCJsonFields
scan and the file-exists probe are explicit fakes. Offline tests never establish
DayZ behaviour; nothing here was observed in DayZ.
"""
import json
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_hc_taped_lights import helmet_member
from tests.unit.test_hc_taped_pack_loader import MANIFEST, PACKS, build, light_catalogue, start
from tests.unit.test_hc_taped_pack_receipts import boot_line, receipt, receipts
from tests.unit.test_taped_light_v1 import NATIVE, member as native_member
from tools.validate import settings_consistency

ROOT = Path(__file__).resolve().parents[2]
RECEIPTS = ROOT / "mission/hollow-country/lights/pair-receipts.json"
HELMETS = ROOT / "mods/HollowCountry/scripts/4_World/Survival/HCTapedHelmetMounts.c"
SETTING = "EnableTapedPackMounts"
MOUNT = "tortilla_universal_mount"
CROSS = "tortilla_universal_cross"
RIFLE_PAIR = "cross_AKM_TLRLight"
PISTOL_PAIR = "cross_Glock19_UniversalLight"
WEAPON_PAIRS = 29

VANILLA = {"CfgVehicles TortillaBag attachments": ["Chemlight", "WalkieTalkie", "Backpack_1", "NBCBag"],
           "CfgVehicles UniversalLight inventorySlot": ["weaponFlashlight", "helmetFlashlight"],
           "CfgVehicles TLRLight inventorySlot": ["pistolFlashlight"]}
# SYNTHETIC: authored slot overrides, also checked against config.cpp by the
# slot-table tests. Not an observation of the running DayZ engine.
PATCHED = {"CfgVehicles TortillaBag attachments": ["Chemlight", "WalkieTalkie", "Backpack_1", "NBCBag", "helmetFlashlight"],
           "CfgVehicles UniversalLight inventorySlot": ["weaponFlashlight", "helmetFlashlight",
                                                        "pistolFlashlight", "Chemlight"],
           "CfgVehicles TLRLight inventorySlot": ["pistolFlashlight", "weaponFlashlight"]}


def native_slots(gate, table):
    """SYNTHETIC native config: weapons carry both light slots, lights per table."""
    def config(path, out):
        if path.startswith("CfgWeapons ") and path.endswith(" attachments"):
            out.extend(["weaponFlashlight", "pistolFlashlight"])
        else:
            out.extend(table.get(path, []))
    gate.env["GetGame"] = lambda: NS(IsServer=lambda: True, ConfigGetTextArray=config)


def with_row(pair, **extra):
    row = receipt(pair, checked=False, date="", note="client check pending")
    row.update(extra)
    return row


def lines(gate, prefix):
    return [x for x in gate.logs if isinstance(x, str) and x.startswith(prefix)]


def booted(rows=None, table=PATCHED, setting=True):
    text = RECEIPTS.read_text() if rows is None else json.dumps({"SchemaVersion": 1, "Receipts": rows})
    gate = build(MANIFEST.read_text(), receipts=text)
    native_slots(gate, table)
    _, published = start(gate, setting=setting)
    return gate, published


class DefaultOnTests(unittest.TestCase):
    def test_setting_defaults_to_true_in_code_registry_and_both_shipped_files(self):
        self.assertEqual([], settings_consistency.check_consistency())
        for rel in ("config/hollow-country-settings.json",
                    "mission/hollow-country/operator/settings.json"):
            self.assertIs(True, json.loads((ROOT / rel).read_text())[SETTING], rel)
        row = {r["key"]: r for r in settings_consistency.load_registry()}[SETTING]
        self.assertEqual(("bool", True), (row["type"], row["default"]))
        native = (ROOT / "mods/HollowCountry/scripts/3_Game/HCSettings.c").read_text()
        self.assertIn("bool EnableTapedPackMounts = true;", native)
        self.assertIn('HCAdd("EnableTapedPackMounts", "bool", 1, 0, 1, "HCSettings");', native)
        # A missing JSON key falls back to the code default, which is now true.
        self.assertIn("if (!HCJsonFields.Has(content, \"EnableTapedPackMounts\")) "
                      "{ settings.EnableTapedPackMounts = defaults.EnableTapedPackMounts; }", native)


class ReceiptVerdictLogTests(unittest.TestCase):
    def apply(self, text):
        gate = build(MANIFEST.read_text(), receipts=text)
        gate.ApplyManifest(MANIFEST.read_text())
        gate.mHCSettingOn = True
        return gate, gate.ApplyReceipts(text)

    def test_shipped_receipt_sheet_loads_clean_with_nothing_disabled(self):
        gate, reason = self.apply(RECEIPTS.read_text())
        self.assertEqual("", reason)
        self.assertEqual([], gate.mHCChecked)
        self.assertEqual([], gate.mHCDisabled)

    def test_shipped_sheet_documents_the_new_rule(self):
        data = json.loads(RECEIPTS.read_text())
        authority = data["Authority"]
        for needle in ("on by default", "Disabled", "admitted unverified", "runtime=PENDING"):
            self.assertIn(needle, authority)
        self.assertNotIn("can only qualify", authority)
        for row in data["Receipts"]:
            self.assertIs(False, row["Disabled"], row["PairId"])
            self.assertIs(False, row["Checked"], row["PairId"])

    def test_disabled_true_opts_the_pair_out_and_absent_means_admitted(self):
        rows = [with_row(MOUNT, Disabled=True), with_row(CROSS), with_row(RIFLE_PAIR, Disabled=False)]
        gate, reason = self.apply(json.dumps({"SchemaVersion": 1, "Receipts": rows}))
        self.assertEqual("", reason)
        self.assertEqual([MOUNT], gate.mHCDisabled)
        self.assertTrue(gate.ReceiptDisabled(MOUNT))
        self.assertFalse(gate.ReceiptDisabled(CROSS))

    def test_unicode_escaped_receipt_keys_are_refused_with_a_named_reason(self):
        for key in (r"Disab\u006ced", r"\u0044isabled", r"Check\u0065d"):
            for value in ("null", '"yes"', "1", "true"):
                text = receipts(with_row(MOUNT, Disabled=False))
                original = "Checked" if key.startswith("Check") else "Disabled"
                text = text.replace('"' + original + '": false', '"' + key + '": ' + value)
                gate, reason = self.apply(text)
                self.assertEqual("receipt_key_unicode_escape", reason, (key, value))
                self.assertEqual([], gate.mHCDisabled)
                self.assertEqual([], gate.mHCChecked)

    def test_unicode_escapes_in_note_values_are_allowed(self):
        text = receipts(with_row(MOUNT, Note="client café"))
        self.assertIn(r"\u00e9", text)
        self.assertEqual("", self.apply(text)[1])

    def test_disabled_must_be_a_json_bool_or_the_file_is_refused(self):
        for bad in ('"yes"', "1", "null", "0"):
            text = receipts(with_row(MOUNT)).replace(
                '"Note": "client check pending"', '"Note": "client check pending", "Disabled": ' + bad)
            gate, reason = self.apply(text)
            self.assertEqual("receipt_disabled_type", reason, bad)
            self.assertEqual([], gate.mHCDisabled)

    def test_unknown_pair_and_malformed_file_still_refuse_everything(self):
        for text, expected in ((receipts(with_row("cross_Nope_TLRLight")), "receipt_unknown_pair"),
                               (receipts(with_row(MOUNT), with_row(MOUNT)), "receipt_duplicate_pair"),
                               ("", "receipts_unreadable")):
            gate, reason = self.apply(text)
            self.assertEqual(expected, reason)
            self.assertEqual([], gate.mHCChecked)
            self.assertEqual([], gate.mHCDisabled)

    def test_a_refused_file_degrades_the_module_and_admits_nothing(self):
        gate, published = booted(rows=[with_row("cross_Nope_TLRLight")])
        self.assertIn(("degraded", "receipt_unknown_pair"), published)
        self.assertEqual(0, gate.AdmittedCount())
        self.assertEqual("receipt_unknown_pair", gate.PairAdmission(MOUNT))
        self.assertEqual("receipt_unknown_pair", gate.PairAdmission(RIFLE_PAIR))
        self.assertFalse(gate.WeaponPairAdmitted(RIFLE_PAIR))


class PackAdmissionTests(unittest.TestCase):
    def test_a_pack_pair_is_admitted_unverified_with_no_checked_receipt(self):
        gate, published = booted()
        self.assertEqual("", gate.PairAdmission(MOUNT))
        self.assertTrue(gate.PairQualified(MOUNT))
        self.assertIn(("ready", "admitted_unverified"), published)
        self.assertEqual(0, gate.VerifiedCount())

    def test_shipped_defaults_admit_the_pack_cross_pair_when_slots_exist(self):
        gate, _ = booted()
        self.assertEqual("", gate.PairAdmission(CROSS))
        self.assertTrue(gate.CrossSlotEnabled())
        self.assertEqual(2, gate.AdmittedCount())
        data = (ROOT / "mods/HollowCountry/scripts/3_Game/Survival/HCTapedLightData.c").read_text()
        self.assertIn("bool DefaultCrossSlotLights = true;", data)

    def test_receipt_disabled_opts_one_pack_pair_out(self):
        gate, _ = booted(rows=[with_row(MOUNT, Disabled=True)])
        self.assertEqual("receipt_disabled", gate.PairAdmission(MOUNT))
        self.assertFalse(gate.PairQualified(MOUNT))

    def test_a_missing_pack_native_slot_is_one_named_refusal_not_a_degraded_module(self):
        gate, published = booted(table=VANILLA)
        self.assertEqual("pack_native_slot_unavailable", gate.PairAdmission(MOUNT))
        self.assertEqual(1, len(lines(gate, "[HC TapedPackMounts] pack_pairs_refused")))
        self.assertIn("reason=pack_native_slot_unavailable", lines(gate, "[HC TapedPackMounts] pack_pairs_refused")[0])
        self.assertTrue(any(state == "ready" for state, _ in published))

    def test_setting_off_is_the_named_operator_opt_out(self):
        gate, published = booted(setting=False)
        self.assertIn(("off", "setting_off"), published)
        self.assertEqual("setting_off", gate.PairAdmission(MOUNT))
        self.assertEqual("setting_off", gate.PairAdmission(RIFLE_PAIR))
        self.assertEqual(0, len(gate.mHCWeaponAdmitted))


class WeaponAdmissionTests(unittest.TestCase):
    def test_every_weapon_pair_is_admitted_unverified_with_native_slots(self):
        gate, published = booted()
        self.assertEqual(WEAPON_PAIRS, len(gate.mHCWeaponAdmitted))
        self.assertTrue(gate.WeaponPairAdmitted(RIFLE_PAIR))
        self.assertTrue(gate.WeaponPairAdmitted(PISTOL_PAIR))
        self.assertEqual("", gate.PairAdmission(RIFLE_PAIR))
        self.assertFalse(gate.WeaponPairAdmitted("cross_Nope_TLRLight"))
        self.assertIn(("ready", "admitted_unverified"), published)

    def test_boot_reports_pack_and_weapon_checked_counts_separately(self):
        rows = [with_row(MOUNT, Checked=True, CheckDate="2026-11-19", Note="one client"),
                with_row(RIFLE_PAIR, Checked=True, CheckDate="2026-11-19", Note="one client"),
                with_row(PISTOL_PAIR, Checked=True, CheckDate="2026-11-19", Note="one client")]
        gate, _ = booted(rows=rows)
        line = boot_line(gate)
        for field in ("receipts_checked=3", "pack_checked=1", "weapon_checked=2",
                      "pack_admitted=2", "weapon_admitted=29", "admitted=31",
                      "setting=on", "reason=admitted_unverified", "runtime=PENDING"):
            self.assertIn(field, line)

    def test_one_summary_line_counts_admitted_unverified_pairs_not_one_line_per_pair(self):
        gate, _ = booted(rows=[with_row(PISTOL_PAIR, Disabled=True)])
        summary = lines(gate, "[HC TapedPackMounts] admission result=admitted unverified")
        self.assertEqual(1, len(summary))
        for field in ("pairs=31", "unchecked=31", "checked=0", "disabled=1", "runtime=PENDING"):
            self.assertIn(field, summary[0])
        weapon_ids = [pair for pair in gate.mHCWeaponAdmitted] + [PISTOL_PAIR]
        self.assertEqual([], [x for x in gate.logs if isinstance(x, str) and any(pair in x for pair in weapon_ids)])
        self.assertEqual(WEAPON_PAIRS - 1, len(gate.mHCWeaponAdmitted))
        self.assertEqual("receipt_disabled", gate.PairAdmission(PISTOL_PAIR))

    def test_summary_checked_and_unchecked_use_only_the_covered_cohort(self):
        rows = [with_row(MOUNT, Checked=True, CheckDate="2026-11-19", Note="synthetic"),
                with_row(RIFLE_PAIR, Checked=True, CheckDate="2026-11-19", Note="synthetic")]
        gate, _ = booted(rows=rows, table=VANILLA)
        summary = lines(gate, "[HC TapedPackMounts] admission result=")[0]
        for field in ("pairs=0", "unchecked=0", "checked=0"):
            self.assertIn(field, summary)
        # Checked receipts remain reported independently of admission.
        self.assertIn("receipts_checked=2", boot_line(gate))

    def test_checked_disabled_pairs_are_covered_but_never_admitted(self):
        gate, _ = booted(rows=[with_row(MOUNT, Disabled=True, Checked=True,
                                      CheckDate="2026-11-19", Note="synthetic")])
        self.assertEqual(1, gate.AdmittedCount())
        summary = lines(gate, "[HC TapedPackMounts] admission result=")[0]
        for field in ("pairs=31", "unchecked=30", "checked=1", "disabled=1"):
            self.assertIn(field, summary)

    def test_missing_weapon_light_slot_is_one_named_line_and_the_module_stays_ready(self):
        gate, published = booted(table=VANILLA)
        self.assertEqual(0, len(gate.mHCWeaponAdmitted))
        refused = lines(gate, "[HC TapedPackMounts] weapon_pairs_refused")
        self.assertEqual(1, len(refused))
        for field in ("count=29", "reason=weapon_light_slot_unavailable", "runtime=PENDING"):
            self.assertIn(field, refused[0])
        self.assertEqual("weapon_light_slot_unavailable", gate.PairAdmission(RIFLE_PAIR))
        self.assertTrue(any(state == "ready" for state, _ in published))
        self.assertFalse(any(state == "degraded" for state, _ in published))

    def test_a_weapon_binding_is_allowed_only_for_an_admitted_exact_pair(self):
        gate, _ = booted(rows=[with_row(PISTOL_PAIR, Disabled=True)])
        binding = NS(HostConfigRoot="CfgWeapons", PairId=RIFLE_PAIR, HostClass="AKM",
                     LightClass="TLRLight", SlotName="weaponFlashlight", CrossSlot=True)
        self.assertTrue(gate.BindingAllowed(binding))
        for field, value in (("HostClass", "M4A1"), ("LightClass", "UniversalLight"),
                             ("SlotName", "pistolFlashlight"), ("PairId", PISTOL_PAIR),
                             ("CrossSlot", False), ("PairId", "")):
            forged = NS(**vars(binding))
            setattr(forged, field, value)
            self.assertFalse(gate.BindingAllowed(forged), field)
        pistol = NS(HostConfigRoot="CfgWeapons", PairId=PISTOL_PAIR, HostClass="Glock19",
                    LightClass="UniversalLight", SlotName="pistolFlashlight", CrossSlot=True)
        self.assertFalse(gate.BindingAllowed(pistol))

    def test_stop_forgets_the_admitted_weapon_pairs(self):
        source = PACKS.read_text()
        self.assertIn("mHCWeaponAdmitted.Clear();", source)


class CatalogueCrossRowTests(unittest.TestCase):
    def test_cross_rows_are_derived_from_the_catalogue_with_the_pair_id(self):
        catalogue = light_catalogue()
        row = catalogue.CrossRow(RIFLE_PAIR)
        self.assertEqual(("AKM", "TLRLight", "weaponFlashlight", "weaponHandguardAK", "AK_RailHndgrd", RIFLE_PAIR),
                         (row.HostClass, row.LightClass, row.SlotName, row.PrerequisiteSlot,
                          row.PrerequisiteClass, row.PairId))
        row = catalogue.CrossRow(PISTOL_PAIR)
        self.assertEqual(("Glock19", "UniversalLight", "pistolFlashlight", PISTOL_PAIR),
                         (row.HostClass, row.LightClass, row.SlotName, row.PairId))
        self.assertIsNone(catalogue.CrossRow("cross_Nope_TLRLight"))
        self.assertIsNone(catalogue.CrossRow(""))

    def test_cross_row_match_is_exact_host_and_cross_light_only(self):
        catalogue = light_catalogue()
        self.assertEqual(RIFLE_PAIR, catalogue.CrossRowMatch("AKM", "TLRLight").PairId)
        self.assertEqual(PISTOL_PAIR, catalogue.CrossRowMatch("Glock19", "UniversalLight").PairId)
        for host, light in (("AKM", "UniversalLight"), ("Glock19", "TLRLight"), ("akm", "TLRLight"),
                            ("Mosin9130", "TLRLight")):
            self.assertIsNone(catalogue.CrossRowMatch(host, light), (host, light))


class NativeAttachSiteTests(unittest.TestCase):
    """HCTapedLightV1Qualification.Row/Resolve use the admitted weapon pair, nothing else."""

    def fixture(self, admitted, server=True, disabled=()):
        catalogue = light_catalogue()
        gate = NS(WeaponPairAdmitted=lambda pair: server and pair in admitted,
                  ReceiptDisabled=lambda pair: pair in disabled)
        state = NS()
        env = {"GetGame": lambda: NS(IsServer=lambda: server), "HCTapedLightCatalog": NS(
                   Rows=catalogue.Rows, Matches=lambda *a: native_member(
                       ROOT / "mods/HollowCountry/scripts/3_Game/Survival/HCTapedLightCatalog.c",
                       "HCTapedLightCatalog", "Matches", NS(), {}, *a),
                   CrossRowMatch=catalogue.CrossRowMatch),
               "HCTapedPackMounts": gate}
        return state, env

    def row(self, admitted, host, light, server=True, disabled=()):
        state, env = self.fixture(admitted, server, disabled)
        source = NATIVE.read_text()
        match = re.search(r"class HCTapedLightV1Qualification\b[^\{]*\{", source)
        self.assertIn("static HCTapedLightHostRow CrossRow(", source[match.end():])
        from tests.unit.test_group_server import body
        text = re.sub(r"\bHCTapedLightHostRow (?=(?:Row|CrossRow)\()", "int ", body(source, match.end()))
        text = re.sub(r"\b(?:HCTapedLightHostRow|ref array<ref HCTapedLightHostRow>) (?=\w+ = )", "HCGroupNative ", text)
        text = text.replace("ref array<ref HCTapedLightHostRow>", "HCGroupNative")
        from tests.unit.test_group_ui import ui_member
        state.CrossRow = lambda h, l: ui_member(text, "CrossRow", state, dict(env), h, l)
        host_item = NS(GetType=lambda: host)
        light_item = NS(GetType=lambda: light)
        return ui_member(text, "Row", state, dict(env), host_item, light_item)

    def test_an_admitted_cross_pair_resolves_a_row_for_the_exact_host_and_light(self):
        row = self.row({RIFLE_PAIR}, "AKM", "TLRLight")
        self.assertEqual((RIFLE_PAIR, "TLRLight", "weaponFlashlight"),
                         (row.PairId, row.LightClass, row.SlotName))

    def test_an_unadmitted_cross_pair_resolves_nothing(self):
        self.assertIsNone(self.row(set(), "AKM", "TLRLight"))
        self.assertIsNone(self.row({PISTOL_PAIR}, "AKM", "TLRLight"))

    def test_client_mount_and_remove_previews_show_an_unadmitted_cross_pair(self):
        from tests.unit.test_client_frame_costs import runtime_member
        from tests.unit.test_taped_light_v1 import native_member as selection
        row = lambda h, l: self.row(set(), h.GetType(), l.GetType(), server=False)
        light = NS(GetType=lambda: "TLRLight", IsDamageDestroyed=lambda: False,
                   GetCompEM=lambda: NS(IsSwitchedOn=lambda: False))
        host = NS(GetType=lambda: "AKM")
        actor = NS()
        light.GetHierarchyRootPlayer = lambda: actor
        light.GetInventory = lambda: NS(GetCurrentInventoryLocation=lambda loc: True)
        actor.GetInventory = lambda: NS(EnumerateInventory=lambda mode, out: out.append(light) or True,
                                       FindFreeLocationFor=lambda *args: True)
        class Location:
            def GetType(self): return 3
        env = dict(NewItems=EArray, ItemBase=NS(Cast=lambda x: x), HCGroupLocation=Location,
                   InventoryTraversalType=NS(PREORDER=1), InventoryLocationType=NS(CARGO=3),
                   FindInventoryLocationType=NS(CARGO=3),
                   HCTapedLightV1Qualification=NS(Row=row, CrossRow=lambda h, l: self.row(set(), h, l, server=False)),
                   HCTapedLightCatalog=NS(Rows=light_catalogue().Rows, Matches=lambda *args: False),
                   GetGame=lambda: NS(IsServer=lambda: False, GetTime=lambda: 1000))
        for mounting in (True, False):
            host.FindAttachmentBySlotName = lambda slot: None if mounting else light
            state = NS(Held=lambda *a: True, KnownHost=lambda h: True, Tape=lambda a: NS(),
                       mHCHintHost=None, mHCHintTime=0, mHCHintMount=False, mHCHintRemove=False)
            state.LooseLight = lambda a, h: selection("HCTapedLightRuntime", "LooseLight", state, env, a, h)
            state.MountedLight = lambda h: runtime_member("HCTapedLightRuntime", "MountedLight", state, env, h)
            state.Preview = lambda a, h, m: runtime_member("HCTapedLightRuntime", "Preview", state, env, a, h, m)
            env.update(MountedLight=state.MountedLight, LooseLight=state.LooseLight,
                       Tape=state.Tape, Preview=state.Preview)
            self.assertTrue(runtime_member("HCTapedLightRuntime", "PreviewHint", state, env, actor, host, mounting), mounting)

    def test_server_resolve_refuses_unadmitted_and_slot_missing_cross_pairs(self):
        from tests.unit.test_client_frame_costs import class_body
        from tests.unit.test_group_ui import ui_member
        text = class_body(NATIVE.read_text(), "HCTapedLightV1Qualification")
        text = text.replace("HCTapedLightBinding Resolve(", "int Resolve(")
        text = text.replace("ref HCTapedLightJournal buildReader = new HCTapedLightJournal;",
                            "HCGroupNative buildReader = NewJournal();")
        text = re.sub(r"TStringArray (\w+) = new TStringArray;", r"HCGroupNative \1 = NewSlots();", text)
        text = re.sub(r"\b(?:HCTapedLightHostRow|HCTapedLightBinding|EntityAI) (?=\w+ = )", "HCGroupNative ", text)
        host, light = NS(GetType=lambda: "AKM"), NS(GetType=lambda: "TLRLight")
        probes = []
        env = dict(NewJournal=lambda: NS(Build=lambda: "synthetic"), NewSlots=EArray,
                   HCBuildIdentity=NS(Matches=lambda b: True),
                   GetGame=lambda: NS(IsServer=lambda: True,
                                      ConfigGetTextArray=lambda p, out: probes.append(p)))
        for admitted in (set(), {RIFLE_PAIR}):
            env["Row"] = lambda h, l: self.row(admitted, h.GetType(), l.GetType())
            self.assertIsNone(ui_member(text, "Resolve", NS(Ready=lambda: True), env.copy(), host, light))
            self.assertEqual(2 if admitted else 0, len(probes))

    def test_client_known_disabled_cross_pair_is_hidden(self):
        self.assertIsNone(self.row(set(), "AKM", "TLRLight", server=False, disabled={RIFLE_PAIR}))

    def test_the_native_cohort_still_resolves_without_any_admission(self):
        row = self.row(set(), "AKM", "UniversalLight")
        self.assertEqual(("", "UniversalLight"), (row.PairId, row.LightClass))


class HelmetAndTapedLightStatusTests(unittest.TestCase):
    def run_helmet(self, disabled=False, native=True):
        probes, logs, published = [], [], []
        module = NS(mHCStarted=False,
                    mHCStatus=NS(HCPublish=lambda *a: published.append(a), HCStop=lambda: published.append("stop")))
        module.NativeSlotAvailable = lambda: native
        admitted = []
        env = dict(GetGame=lambda: NS(IsServer=lambda: True),
                   FileExist=lambda path: probes.append(path) or disabled,
                   Print=logs.append,
                   HCTapedWearableCatalog=NS(Rows=lambda: EArray(["row"]),
                                             CompatibilityQueue=lambda: EArray(["a", "b", "c"]),
                                             Qualified=lambda: False,
                                             HCSetAdmitted=admitted.append),
                   HCV2Admission=NS(Line=lambda *a: "admission " + repr(a[1:])))
        helmet_member(HELMETS, "HCTapedHelmetMounts", "OnStart", module, env, NS())
        return published, logs, probes, admitted

    def test_helmet_mounts_are_admitted_unverified_by_default(self):
        published, logs, probes, admitted = self.run_helmet()
        self.assertEqual([("ready", "admitted_unverified")], published)
        self.assertEqual([True], admitted)
        self.assertEqual(["$profile:HollowCountry/acceptance/taped_helmet.disable"], probes)
        self.assertFalse(any("helmet_mount_two_client_pending" in str(x) and "state=off" in str(x) for x in logs))
        self.assertEqual(1, len([x for x in logs if "helmet_action_pending" in str(x)]))

    def test_helmet_opt_out_file_is_a_named_off_reason(self):
        published, logs, probes, admitted = self.run_helmet(disabled=True)
        self.assertEqual([("off", "operator_disable_file")], published)
        self.assertEqual([False], admitted)

    def test_helmet_native_slot_loss_is_degraded_not_ready(self):
        published, _, _, admitted = self.run_helmet(native=False)
        self.assertEqual([("degraded", "helmet_native_slot_unavailable")], published)
        self.assertEqual([False], admitted)

    def test_helmet_qualification_ready_follows_the_catalogue_admission_only(self):
        source = HELMETS.read_text()
        self.assertIn("return HCTapedWearableCatalog.Admitted();", source)
        self.assertIn("return null;", source[source.index("class HCTapedHelmetQualification"):])

    def run_taped_light(self, disabled=False):
        published, logs = [], []
        module = NS(m_Printed=False,
                    m_Status=NS(HCPublish=lambda *a: published.append(a), HCStop=lambda: published.append("stop")))
        env = dict(HCTapedLightAdmission=NS(Admitted=lambda: not disabled, Qualified=lambda: False),
                   HCTapedLightCatalog=NS(Rows=lambda: EArray(["a"] * 29)),
                   HCV2Admission=NS(Line=lambda *a: "admission", OnOff=lambda v: "on" if v else "off"),
                   Print=logs.append)
        source = NATIVE.read_text()
        match = re.search(r"class HCTapedLightStartup\b[^\{]*\{", source)
        from tests.unit.test_group_server import body
        from tests.unit.test_group_ui import ui_member
        text = body(source, match.end()).replace("m_Printed", "mHCPrinted").replace("m_Status", "mHCStatus")
        text = re.sub(r"(\w+)\.ToString\(\)", r"str(\1)", text)
        module.mHCPrinted, module.mHCStatus = module.m_Printed, module.m_Status
        ui_member(text, "OnStart", module, dict(env), NS())
        return published, logs

    def test_taped_light_publishes_an_honest_ready_from_its_admission(self):
        published, logs = self.run_taped_light()
        self.assertEqual([("ready", "admitted_unverified")], published)
        published, logs = self.run_taped_light(disabled=True)
        self.assertEqual([("off", "operator_disable_file")], published)

    def test_taped_light_exposes_its_status_through_the_operational_hook(self):
        source = NATIVE.read_text()
        section = source[source.index("class HCTapedLightStartup"):source.index("modded class HCModuleRegistry")]
        self.assertIn("override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }", section)
        self.assertIn("m_Status.HCStop();", section)


if __name__ == "__main__":
    unittest.main()
