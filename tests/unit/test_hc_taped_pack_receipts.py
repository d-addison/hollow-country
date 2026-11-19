"""#58 / HC-52 wave 13: operator setting + per-pair client-check receipt; runtime=PENDING.

A pack pair qualifies only when ALL hold: the operator setting
EnableTapedPackMounts is on, that pair has a checked receipt in the
mission-authored lights/pair-receipts.json, and the catalogue gate admits it.
The catalogue gate (HCTapedPackCatalog.Qualified) stays false in shipped code,
so the shipped result is admitted=0. Fixtures are SYNTHETIC: the file read, the
JSON codec, the native slot arrays and the catalogue verdict used to exercise the
"catalogue admits" branch are explicit fakes; DayZ behaviour is not established.
"""
import json
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_hc_taped_pack_loader import MANIFEST, PACKS, build, member, start
from tools.validate import settings_consistency

ROOT = Path(__file__).resolve().parents[2]
RECEIPTS = ROOT / "mission/hollow-country/lights/pair-receipts.json"
RECEIPT_PATH = "$mission:hollow-country/lights/pair-receipts.json"
SETTING = "EnableTapedPackMounts"
MOUNT = "tortilla_universal_mount"
CROSS = "tortilla_universal_cross"


def receipt(pair, checked=True, date="2026-11-19", note="two-client check"):
    return {"PairId": pair, "Checked": checked, "CheckDate": date, "Note": note}


def receipts(*rows):
    return json.dumps({"SchemaVersion": 1, "Receipts": list(rows)})


def synthetic_catalogue_admits(gate, pairs):
    """Explicit SYNTHETIC verdict: the catalogue gate admits these pairs and the
    native slot arrays list the slot. Real shipped code admits nothing."""
    gate.env["HCTapedPackCatalog"].Qualified = lambda pair: pair in pairs
    slots = {"CfgVehicles TortillaBag attachments": ["helmetFlashlight", "Chemlight"],
             "CfgVehicles UniversalLight inventorySlot": ["helmetFlashlight", "Chemlight"]}
    gate.env["GetGame"] = lambda: type("G", (), {
        "IsServer": staticmethod(lambda: True),
        "ConfigGetTextArray": staticmethod(lambda path, out: out.extend(slots[path]))})()


def boot_line(gate):
    lines = [x for x in gate.logs if isinstance(x, str) and x.startswith("[HC TapedPackMounts]")]
    assert len(lines) == 1, lines
    return lines[0]


def manifest_with(cross=False, permitted=()):
    data = json.loads(MANIFEST.read_text())
    data["SettingsContract"]["DefaultCrossSlotLights"] = cross
    data["SettingsContract"]["DefaultPermittedPairIds"] = list(permitted)
    return json.dumps(data)


class ShippedFilesTests(unittest.TestCase):
    def test_setting_is_registered_and_shipped_off_in_every_settings_file(self):
        self.assertEqual([], settings_consistency.check_consistency())
        for rel in ("config/hollow-country-settings.json",
                    "mission/hollow-country/operator/settings.json"):
            self.assertIs(False, json.loads((ROOT / rel).read_text())[SETTING], rel)
        registry = {row["key"]: row for row in settings_consistency.load_registry()}
        self.assertEqual(("bool", False, "HCSettings"),
                         (registry[SETTING]["type"], registry[SETTING]["default"],
                          registry[SETTING]["owner"]))
        native = (ROOT / "mods/HollowCountry/scripts/3_Game/HCSettings.c").read_text()
        self.assertIn("bool EnableTapedPackMounts = false;", native)
        self.assertIn('HCJsonFields.Has(content, "EnableTapedPackMounts")', native)

    def test_shipped_receipts_list_only_known_pairs_all_unchecked(self):
        data = json.loads(RECEIPTS.read_text())
        self.assertEqual(1, data["SchemaVersion"])
        known = build(MANIFEST.read_text()).env["HCTapedPackCatalog"].ReceiptPairIds()
        for row in data["Receipts"]:
            self.assertIn(row["PairId"], known)
            self.assertIs(False, row["Checked"])
        self.assertIn("runtime", RECEIPTS.read_text().lower())

    def test_manifest_names_the_receipt_read_limit_as_a_config_field(self):
        contract = json.loads(MANIFEST.read_text())["SettingsContract"]
        self.assertGreater(contract["MaxReceiptBytes"], 0)

    def test_manifest_names_the_receipt_read_ceiling_as_a_config_field(self):
        contract = json.loads(MANIFEST.read_text())["SettingsContract"]
        self.assertGreater(contract["MaxReceiptBytesCeiling"], 0)
        self.assertLessEqual(contract["MaxReceiptBytes"], contract["MaxReceiptBytesCeiling"])
        self.assertLessEqual(contract["MaxReceiptBytesCeiling"], 1048576)

    def test_source_reads_mission_receipts_never_profile(self):
        source = PACKS.read_text()
        self.assertIn(RECEIPT_PATH, source)
        self.assertNotIn("$profile:", source)
        self.assertIn("HCJsonFields.Every", source)


class AdmissionTests(unittest.TestCase):
    def shipped(self, receipt_text, setting):
        gate = build(MANIFEST.read_text(), receipts=receipt_text)
        start(gate, setting=setting)
        return gate

    def test_shipped_files_admit_nothing_with_the_setting_off(self):
        gate = self.shipped(RECEIPTS.read_text(), False)
        line = boot_line(gate)
        for field in ("pairs=2", "receipts_checked=0", "admitted=0", "setting=off",
                      "reason=setting_off"):
            self.assertIn(field, line)
        self.assertEqual(0, gate.AdmittedCount())
        self.assertFalse(gate.PairQualified(MOUNT))

    def test_setting_off_admits_nothing_even_with_a_checked_receipt_and_open_catalogue(self):
        gate = build(MANIFEST.read_text(), receipts=receipts(receipt(MOUNT)))
        synthetic_catalogue_admits(gate, (MOUNT, CROSS))
        start(gate, setting=False)
        self.assertIn("admitted=0", boot_line(gate))
        self.assertIn("setting=off", boot_line(gate))
        self.assertIn("receipts_checked=0", boot_line(gate))
        self.assertFalse(gate.PairQualified(MOUNT))

    def test_setting_on_without_a_checked_receipt_admits_nothing_with_a_reason(self):
        for text in (RECEIPTS.read_text(), receipts(), receipts(receipt(MOUNT, checked=False))):
            gate = build(MANIFEST.read_text(), receipts=text)
            synthetic_catalogue_admits(gate, (MOUNT, CROSS))
            _, published = start(gate, setting=True)
            line = boot_line(gate)
            for field in ("receipts_checked=0", "admitted=0", "setting=on",
                          "reason=client_check_pending"):
                self.assertIn(field, line)
            self.assertIn(("refused", "client_check_pending"), published)
            self.assertEqual("client_check_pending", gate.PairAdmission(MOUNT))

    def test_checked_receipt_for_one_pair_qualifies_exactly_that_pair(self):
        gate = build(manifest_with(cross=True, permitted=(CROSS,)),
                     receipts=receipts(receipt(MOUNT), receipt(CROSS, checked=False)))
        synthetic_catalogue_admits(gate, (MOUNT, CROSS))
        _, published = start(gate, setting=True)
        line = boot_line(gate)
        for field in ("pairs=2", "receipts_checked=1", "admitted=1", "setting=on",
                      "reason=pairs_client_checked"):
            self.assertIn(field, line)
        self.assertIn(("ready", "pairs_client_checked"), published)
        self.assertTrue(gate.PairQualified(MOUNT))
        self.assertFalse(gate.PairQualified(CROSS))
        self.assertEqual("client_check_pending", gate.PairAdmission(CROSS))

    def test_cross_pair_needs_cross_slot_and_permission_as_well_as_its_receipt(self):
        for manifest, reason in ((manifest_with(), "cross_slot_disabled"),
                                 (manifest_with(cross=True), "cross_slot_pair_not_permitted")):
            gate = build(manifest, receipts=receipts(receipt(CROSS)))
            synthetic_catalogue_admits(gate, (MOUNT, CROSS))
            start(gate, setting=True)
            self.assertEqual(reason, gate.PairAdmission(CROSS))
            self.assertIn("admitted=0", boot_line(gate))
        gate = build(manifest_with(cross=True, permitted=(CROSS,)),
                     receipts=receipts(receipt(CROSS)))
        synthetic_catalogue_admits(gate, (MOUNT, CROSS))
        start(gate, setting=True)
        self.assertTrue(gate.PairQualified(CROSS))
        self.assertFalse(gate.PairQualified(MOUNT))

    def test_shipped_catalogue_gate_keeps_a_checked_receipt_at_admitted_zero(self):
        gate = build(MANIFEST.read_text(), receipts=receipts(receipt(MOUNT)))
        start(gate, setting=True)
        line = boot_line(gate)
        for field in ("receipts_checked=1", "admitted=0", "setting=on",
                      "reason=pack_mount_geometry_pending"):
            self.assertIn(field, line)
        self.assertFalse(gate.PairQualified(MOUNT))

    def test_binding_is_allowed_only_for_a_qualified_pair(self):
        from types import SimpleNamespace as NS
        binding = NS(HostConfigRoot="CfgVehicles", PairId=MOUNT, HostClass="TortillaBag",
                     LightClass="UniversalLight", SlotName="helmetFlashlight", CrossSlot=False)
        gate = build(MANIFEST.read_text(), receipts=receipts(receipt(MOUNT)))
        synthetic_catalogue_admits(gate, (MOUNT,))
        start(gate, setting=True)
        self.assertTrue(gate.BindingAllowed(binding))
        gate.mHCSettingOn = False
        self.assertFalse(gate.BindingAllowed(binding))
        gate.mHCSettingOn = True
        gate.mHCChecked.clear()
        self.assertFalse(gate.BindingAllowed(binding))


class ReceiptLimitCeilingTests(unittest.TestCase):
    def manifest(self, **fields):
        data = json.loads(MANIFEST.read_text())
        data["SettingsContract"].update(fields)
        return json.dumps(data)

    def test_limit_above_the_named_ceiling_refuses_and_stays_unconfigured(self):
        ceiling = json.loads(MANIFEST.read_text())["SettingsContract"]["MaxReceiptBytesCeiling"]
        for limit in (ceiling + 1, 1048576, 2000000000):
            text = self.manifest(MaxReceiptBytes=limit)
            gate = build(text)
            self.assertEqual("mount_manifest_receipt_limit", gate.ApplyManifest(text), limit)
            self.assertFalse(gate.mHCConfigured)
            self.assertEqual(0, gate.mHCReceiptMaxBytes)

    def test_limit_at_the_ceiling_is_accepted(self):
        ceiling = json.loads(MANIFEST.read_text())["SettingsContract"]["MaxReceiptBytesCeiling"]
        text = self.manifest(MaxReceiptBytes=ceiling)
        gate = build(text)
        self.assertEqual("", gate.ApplyManifest(text))
        self.assertEqual(ceiling, gate.mHCReceiptMaxBytes)

    def test_missing_or_non_positive_ceiling_refuses(self):
        data = json.loads(MANIFEST.read_text())
        del data["SettingsContract"]["MaxReceiptBytesCeiling"]
        text = json.dumps(data)
        gate = build(text)
        self.assertEqual("mount_manifest_fields_missing", gate.ApplyManifest(text))
        self.assertFalse(gate.mHCConfigured)
        for ceiling in (0, -5):
            text = self.manifest(MaxReceiptBytesCeiling=ceiling)
            gate = build(text)
            self.assertEqual("mount_manifest_receipt_limit", gate.ApplyManifest(text), ceiling)
            self.assertFalse(gate.mHCConfigured)

    def test_boot_line_degrades_with_the_limit_reason(self):
        text = self.manifest(MaxReceiptBytes=1048576)
        gate = build(text, receipts=receipts(receipt(MOUNT)))
        _, published = start(gate, setting=True)
        self.assertIn(("degraded", "mount_manifest_receipt_limit"), published)
        self.assertFalse(gate.mHCConfigured)
        self.assertIn("admitted=0", boot_line(gate))


class ReceiptValidationTests(unittest.TestCase):
    def apply(self, text, setting=True):
        gate = build(MANIFEST.read_text(), receipts=text)
        gate.ApplyManifest(MANIFEST.read_text())
        gate.mHCSettingOn = setting
        return gate, gate.ApplyReceipts(text)

    def test_valid_receipts_record_only_checked_pairs(self):
        gate, reason = self.apply(receipts(receipt(MOUNT), receipt(CROSS, checked=False)))
        self.assertEqual("", reason)
        self.assertEqual([MOUNT], gate.mHCChecked)
        self.assertTrue(gate.ReceiptChecked(MOUNT))
        self.assertFalse(gate.ReceiptChecked(CROSS))

    def test_unknown_pair_id_refuses_and_grants_nothing(self):
        gate, reason = self.apply(receipts(receipt(MOUNT), receipt("tlr_rifle_cross")))
        self.assertEqual("receipt_unknown_pair", reason)
        self.assertEqual([], gate.mHCChecked)

    def test_missing_key_refuses_for_every_field_and_grants_nothing(self):
        for key in ("PairId", "Checked", "CheckDate", "Note"):
            row = receipt(MOUNT)
            del row[key]
            gate, reason = self.apply(receipts(row))
            self.assertEqual("receipts_fields_missing", reason, key)
            self.assertEqual([], gate.mHCChecked, key)
        data = {"SchemaVersion": 1}
        gate, reason = self.apply(json.dumps(data))
        self.assertEqual("receipts_fields_missing", reason)
        data = {"Receipts": []}
        gate, reason = self.apply(json.dumps(data))
        self.assertEqual("receipts_fields_missing", reason)

    def test_other_refusals_grant_nothing(self):
        cases = (("", "receipts_unreadable"),
                 (json.dumps({"SchemaVersion": 2, "Receipts": []}), "receipts_schema"),
                 (receipts(receipt(MOUNT), receipt(MOUNT)), "receipt_duplicate_pair"),
                 (receipts(receipt(MOUNT, date="")), "receipt_check_incomplete"),
                 (receipts(receipt(MOUNT, note="")), "receipt_check_incomplete"))
        for text, reason in cases:
            gate, got = self.apply(text)
            self.assertEqual(reason, got, text)
            self.assertEqual([], gate.mHCChecked, text)

    def test_wrongly_typed_checked_refuses_with_a_named_reason_and_grants_nothing(self):
        for bad in ("true", "false", 1, 0, None, "yes"):
            for rows in ((receipt(MOUNT, checked=bad),),
                         (receipt(MOUNT), receipt(CROSS, checked=bad))):
                gate, reason = self.apply(receipts(*rows))
                self.assertEqual("receipt_checked_type", reason, (bad, rows))
                self.assertEqual([], gate.mHCChecked, (bad, rows))

    def test_wrongly_typed_checked_degrades_the_boot_line_with_the_reason(self):
        gate = build(MANIFEST.read_text(), receipts=receipts(receipt(MOUNT, checked="true")))
        synthetic_catalogue_admits(gate, (MOUNT, CROSS))
        _, published = start(gate, setting=True)
        line = boot_line(gate)
        for field in ("receipts_checked=0", "admitted=0", "reason=receipt_checked_type"):
            self.assertIn(field, line)
        self.assertIn(("refused", "receipt_checked_type"), published)

    def test_note_text_quoting_the_checked_key_is_not_a_typed_field(self):
        note = 'the "Checked": 1 wording is only prose'
        text = receipts(receipt(MOUNT, note=note))
        self.assertIn('\\"Checked\\": 1', text)
        gate, reason = self.apply(text)
        self.assertEqual("", reason)
        self.assertEqual([MOUNT], gate.mHCChecked)

    def test_a_string_value_spelled_checked_is_not_a_key(self):
        for note in ("Checked", "Checked: true", "Checked:"):
            gate, reason = self.apply(receipts(receipt(MOUNT, note=note)))
            self.assertEqual("", reason, note)
            self.assertEqual([MOUNT], gate.mHCChecked, note)

    def test_checked_key_whitespace_variants_are_typed_by_the_literal(self):
        for gap in ("", " ", "\t", "\n", "\r\n  "):
            for literal, accepted in (("true", True), ("false", True), ("1", False), ('"true"', False)):
                text = ('{"SchemaVersion": 1, "Receipts": [{"PairId": "%s", "Checked"%s:%s%s, '
                        '"CheckDate": "2026-11-19", "Note": "n"}]}') % (MOUNT, gap, gap, literal)
                gate, reason = self.apply(text)
                if accepted:
                    self.assertEqual("", reason, (gap, literal))
                else:
                    self.assertEqual("receipt_checked_type", reason, (gap, literal))
                    self.assertEqual([], gate.mHCChecked, (gap, literal))

    def test_check_date_must_be_an_iso_date(self):
        for date in ("2026-13-01", "2026-00-10", "2026-11-32", "2026-11-00", "2026-11-40",
                     "20261119", "2026/11/19", "2026-1-19", "2026-11-1", "today",
                     "2026-11-1x", "2026-11-19 ", "2026-11-19T00", "26-11-19", " 026-11-19"):
            for checked in (True, False):
                gate, reason = self.apply(receipts(receipt(MOUNT, checked=checked, date=date)))
                self.assertEqual("receipt_check_incomplete", reason, (date, checked))
                self.assertEqual([], gate.mHCChecked, date)
        for date in ("2026-11-19", "2026-01-31", "2026-12-01", "2027-02-09", "2026-10-30"):
            gate, reason = self.apply(receipts(receipt(MOUNT, date=date)))
            self.assertEqual("", reason, date)
            self.assertEqual([MOUNT], gate.mHCChecked, date)

    def test_unchecked_receipt_may_leave_the_date_empty_but_checked_may_not(self):
        gate, reason = self.apply(receipts(receipt(MOUNT, checked=False, date="")))
        self.assertEqual("", reason)
        gate, reason = self.apply(receipts(receipt(MOUNT, checked=True, date="")))
        self.assertEqual("receipt_check_incomplete", reason)

    def test_oversize_receipt_file_is_refused_by_the_read_limit_with_a_named_reason(self):
        limit = json.loads(MANIFEST.read_text())["SettingsContract"]["MaxReceiptBytes"]
        padded = receipts(receipt(MOUNT, note="x" * (limit + 1)))
        self.assertGreater(len(padded), limit)
        asked = []

        def bounded_read(path, bound, out):
            asked.append((path, bound))
            return len(padded) <= bound  # SYNTHETIC stand-in for HCGroupIO.HCReadRaw
        gate = build(MANIFEST.read_text(), receipts=padded)
        gate.env["HCGroupIO"] = NS(Read=bounded_read)
        gate.ReadReceipts = lambda: member(PACKS, "HCTapedPackMounts", "ReadReceipts",
                                           gate, gate.env)
        synthetic_catalogue_admits(gate, (MOUNT, CROSS))
        _, published = start(gate, setting=True)
        self.assertEqual([(RECEIPT_PATH, limit)], asked)
        line = boot_line(gate)
        for field in ("receipts_checked=0", "admitted=0", "reason=receipts_unreadable",
                      "receipts=receipts_unreadable"):
            self.assertIn(field, line)
        self.assertIn(("refused", "receipts_unreadable"), published)
        self.assertEqual([], gate.mHCChecked)

    def test_unconfigured_manifest_never_reads_receipts(self):
        gate = build("", receipts=receipts(receipt(MOUNT)))
        gate.mHCSettingOn = True
        self.assertEqual("pack_mounts_unconfigured", gate.LoadReceipts())
        self.assertEqual([], gate.mHCChecked)

    def test_setting_off_skips_the_receipt_read(self):
        gate = build(MANIFEST.read_text(), receipts=receipts(receipt(MOUNT)))
        gate.ApplyManifest(MANIFEST.read_text())
        gate.ReadReceipts = lambda: self.fail("receipts read while the setting is off")
        gate.mHCSettingOn = False
        self.assertEqual("", gate.LoadReceipts())
        self.assertEqual([], gate.mHCChecked)

    def test_invalid_receipts_degrade_the_boot_line_with_the_reason(self):
        gate = build(MANIFEST.read_text(), receipts=receipts(receipt("nope")))
        _, published = start(gate, setting=True)
        line = boot_line(gate)
        for field in ("receipts_checked=0", "admitted=0", "reason=receipt_unknown_pair"):
            self.assertIn(field, line)
        self.assertIn(("refused", "receipt_unknown_pair"), published)

    def test_stop_clears_the_receipts_and_setting(self):
        gate = build(MANIFEST.read_text(), receipts=receipts(receipt(MOUNT)))
        start(gate, setting=True)
        self.assertEqual([MOUNT], gate.mHCChecked)
        gate.Reset()
        self.assertEqual([], gate.mHCChecked)
        self.assertFalse(gate.mHCSettingOn)

class CheckDateCalendarTests(unittest.TestCase):
    """P3 (#196): the check date must be a real Gregorian calendar day."""

    def valid(self, date):
        return build(MANIFEST.read_text()).ValidCheckDate(date)

    def test_impossible_calendar_days_are_refused(self):
        for date in ("2026-02-29", "2026-02-31", "2026-04-31", "2026-06-31", "2026-09-31",
                     "2026-11-31", "2100-02-29", "1900-02-29", "2026-02-30", "2026-13-01",
                     "2026-00-10", "2026-01-00", "2026-01-32", "2026-1-011", "20261119xx"):
            self.assertFalse(self.valid(date), date)

    def test_real_calendar_days_are_accepted(self):
        for date in ("2028-02-29", "2000-02-29", "2026-12-31", "2026-02-28", "2026-04-30",
                     "2026-01-31", "2026-11-19", "2400-02-29"):
            self.assertTrue(self.valid(date), date)


if __name__ == "__main__":
    unittest.main()
