"""#58 / #196 wave 15: one receipt row per approved cross-slot weapon pair; runtime=PENDING.

The approved cross-slot pairs are TLRLight on the 22 rail rifles and UniversalLight
on the 7 pistols. Their stable ids are DERIVED from the compiled
HCTapedLightCatalog rows by the authored HCTapedLightCatalog.CrossPairIds (no second
hand-kept weapon list); lights/pair-receipts.json is the operator's record sheet and
this test is the single check that the sheet and the derivation agree. Every row
ships Checked=false: nothing is admitted and Qualified() stays false. Fixtures are
SYNTHETIC: the file read, JSON codec, native slot arrays and HCJsonFields scan are
explicit fakes from test_hc_taped_pack_loader; DayZ behaviour is not established.
"""
import json
from pathlib import Path
import re
import unittest

from tests.legacy.test_hc_taped_pack_loader import CATALOG, MANIFEST, PACKS, WEARABLE, build, light_catalogue, start
from tests.legacy.test_hc_taped_pack_receipts import boot_line, receipt, receipts, synthetic_catalogue_admits

ROOT = Path(__file__).resolve().parents[2]
RECEIPTS = ROOT / "mission/hollow-country/lights/pair-receipts.json"
PACK_IDS = ["tortilla_universal_mount", "tortilla_universal_cross"]
# Independent expectation, stated once from the owner-approved scope in
# docs/OUTSTANDING.md section 4 (not derived from the code under test).
RIFLES, PISTOLS = 22, 7


def derived_ids():
    return list(light_catalogue().CrossPairIds())


class CrossPairIdDerivationTests(unittest.TestCase):
    def test_catalogue_derives_one_cross_pair_per_approved_weapon(self):
        catalogue = light_catalogue()
        ids = derived_ids()
        self.assertEqual(RIFLES + PISTOLS, len(ids))
        self.assertEqual(len(ids), len(set(ids)), "pair ids must be unique")
        rifles = [row for row in catalogue.rows
                  if row.LightClass == "UniversalLight" and row.SlotName == "weaponFlashlight"]
        pistols = [row for row in catalogue.rows
                   if row.LightClass == "TLRLight" and row.SlotName == "pistolFlashlight"]
        self.assertEqual(RIFLES, len(rifles))
        self.assertEqual(PISTOLS, len(pistols))
        for row in rifles:
            self.assertIn("cross_" + row.HostClass + "_TLRLight", ids)
        for row in pistols:
            self.assertIn("cross_" + row.HostClass + "_UniversalLight", ids)

    def test_ids_are_stable_exact_and_never_collide_with_pack_pairs_or_native_pairs(self):
        ids = derived_ids()
        for pair in ids:
            self.assertRegex(pair, r"^cross_[A-Za-z0-9_]+_(?:TLRLight|UniversalLight)$")
        for pack in PACK_IDS:
            self.assertNotIn(pack, ids)
        self.assertEqual("cross_AK101_TLRLight", ids[0])
        self.assertIn("cross_Glock19_Tan_UniversalLight", ids)

    def test_rows_without_an_approved_cross_light_derive_nothing(self):
        catalogue = light_catalogue()
        row = type("Row", (), {"HostClass": "R12", "LightClass": "UniversalLight",
                               "SlotName": "someOtherSlot"})()
        self.assertEqual("", catalogue.CrossPairId(row))
        self.assertEqual("", catalogue.CrossLightClass(row))
        self.assertEqual("", catalogue.CrossPairId(None))
        self.assertNotIn("R12", " ".join(derived_ids()))

    def test_pack_catalogue_lists_pack_pairs_first_then_the_derived_weapon_pairs(self):
        gate = build(MANIFEST.read_text())
        catalog = gate.env["HCTapedPackCatalog"]
        self.assertEqual(PACK_IDS + derived_ids(), list(catalog.ReceiptPairIds()))
        self.assertEqual(PACK_IDS, list(catalog.PairIds()), "boot-line order of pack pairs is unchanged")
        self.assertFalse(catalog.KnownPair("cross_AK101_TLRLight"), "weapon pairs are not pack pairs")


class ShippedReceiptSheetTests(unittest.TestCase):
    def test_sheet_lists_every_catalogue_pair_exactly_once_all_unchecked(self):
        data = json.loads(RECEIPTS.read_text())
        listed = [row["PairId"] for row in data["Receipts"]]
        self.assertEqual(PACK_IDS + derived_ids(), listed)
        self.assertEqual(2 + RIFLES + PISTOLS, len(listed))
        for row in data["Receipts"]:
            self.assertIs(False, row["Checked"], row["PairId"])
            self.assertEqual("", row["CheckDate"], row["PairId"])
            self.assertNotEqual("", row["Note"], row["PairId"])
        self.assertEqual("PENDING", data["RuntimeAcceptance"])

    def test_sheet_stays_well_under_the_manifest_receipt_read_limit(self):
        limit = json.loads(MANIFEST.read_text())["SettingsContract"]["MaxReceiptBytes"]
        size = len(RECEIPTS.read_bytes())
        self.assertLess(size * 4, limit * 3, "receipt sheet %d bytes vs limit %d" % (size, limit))

    def test_shipped_sheet_loads_clean_with_zero_checked_and_nothing_disabled(self):
        gate = build(MANIFEST.read_text(), receipts=RECEIPTS.read_text())
        _, published = start(gate, setting=True)
        line = boot_line(gate)
        for field in ("receipts_checked=0", "pack_checked=0", "weapon_checked=0", "setting=on",
                      "receipts=ok", "receipt_pairs=%d" % (2 + RIFLES + PISTOLS),
                      "runtime=PENDING"):
            self.assertIn(field, line)
        self.assertIn(("degraded", "pack_native_slot_unavailable"), published)
        self.assertEqual(0, gate.VerifiedCount())
        self.assertEqual([], list(gate.mHCChecked))
        for row in json.loads(RECEIPTS.read_text())["Receipts"]:
            self.assertIs(False, row["Disabled"], row["PairId"])

    def test_setting_off_keeps_the_file_unread_and_the_count_visible(self):
        gate = build(MANIFEST.read_text(), receipts=RECEIPTS.read_text())
        gate.ReadReceipts = lambda: self.fail("receipts read while the setting is off")
        start(gate, setting=False)
        line = boot_line(gate)
        for field in ("receipt_pairs=%d" % (2 + RIFLES + PISTOLS), "setting=off", "admitted=0"):
            self.assertIn(field, line)


class WeaponPairReceiptTests(unittest.TestCase):
    def apply(self, text, setting=True):
        gate = build(MANIFEST.read_text(), receipts=text)
        gate.ApplyManifest(MANIFEST.read_text())
        gate.mHCSettingOn = setting
        return gate, gate.ApplyReceipts(text)

    def test_a_checked_weapon_receipt_is_recorded_for_that_pair_only(self):
        ids = derived_ids()
        gate, reason = self.apply(receipts(receipt(ids[0]), receipt(ids[1], checked=False)))
        self.assertEqual("", reason)
        self.assertEqual([ids[0]], list(gate.mHCChecked))
        self.assertTrue(gate.ReceiptChecked(ids[0]))
        self.assertFalse(gate.ReceiptChecked(ids[1]))

    def test_a_checked_weapon_receipt_is_only_a_record_and_admits_no_pack_pair(self):
        ids = derived_ids()
        gate = build(MANIFEST.read_text(), receipts=receipts(receipt(ids[0]), receipt(ids[-1])))
        synthetic_catalogue_admits(gate, tuple(PACK_IDS) + tuple(ids))
        _, published = start(gate, setting=True)
        line = boot_line(gate)
        for field in ("receipts_checked=2", "weapon_checked=2", "pack_checked=0", "receipts=ok"):
            self.assertIn(field, line)
        self.assertEqual(2, gate.AdmittedCount())
        self.assertEqual(0, gate.VerifiedCount())
        for pair in ids:
            self.assertFalse(gate.PairQualified(pair), pair)
        self.assertFalse(any(state == "degraded" for state, _ in published), published)

    def test_a_pair_that_is_not_in_the_catalogue_is_refused_with_a_named_reason(self):
        ids = derived_ids()
        for stranger in ("cross_R12_TLRLight",             # R12 stays PENDING, not catalogued
                         "cross_AK101_UniversalLight",     # native pair, not a cross-slot pair
                         "cross_Glock19_TLRLight",         # native pair, not a cross-slot pair
                         "cross_ak101_TLRLight",           # ids are exact, case matters
                         "cross_AK101_TLRLight ",          # no whitespace tolerance
                         "tlr_rifle_cross"):
            gate, reason = self.apply(receipts(receipt(ids[0]), receipt(stranger)))
            self.assertEqual("receipt_unknown_pair", reason, stranger)
            self.assertEqual([], list(gate.mHCChecked), stranger)

    def test_duplicate_weapon_receipt_refuses_the_whole_file(self):
        ids = derived_ids()
        gate, reason = self.apply(receipts(receipt(ids[2]), receipt(ids[2], checked=False)))
        self.assertEqual("receipt_duplicate_pair", reason)
        self.assertEqual([], list(gate.mHCChecked))

    def test_checked_weapon_row_needs_a_real_date_and_note(self):
        ids = derived_ids()
        for row in (receipt(ids[3], date=""), receipt(ids[3], note=""),
                    receipt(ids[3], date="2026-02-31")):
            gate, reason = self.apply(receipts(row))
            self.assertEqual("receipt_check_incomplete", reason, row)
            self.assertEqual([], list(gate.mHCChecked))


class SourceContractTests(unittest.TestCase):
    def test_pair_ids_are_derived_in_code_not_listed_twice(self):
        catalogue = CATALOG.read_text()
        self.assertIn("static TStringArray CrossPairIds()", catalogue)
        self.assertEqual(29, len(re.findall(r'"cross_[A-Z0-9]', catalogue)))
        self.assertEqual(0, len(re.findall(r'"cross_[A-Z0-9]', WEARABLE.read_text())))
        self.assertEqual(0, len(re.findall(r'"cross_[A-Z0-9]', PACKS.read_text())))

    def test_verdict_gate_stays_closed_and_the_setting_defaults_on(self):
        wearable = WEARABLE.read_text()
        match = re.search(r"class HCTapedPackCatalog\b.*?static bool Qualified\(string pairId\)\s*\{(.*?)\}",
                          wearable, re.S)
        self.assertIsNotNone(match)
        self.assertIn("return false;", match[1])
        native = (ROOT / "mods/HollowCountry/scripts/3_Game/HCSettings.c").read_text()
        self.assertIn("bool EnableTapedPackMounts = true;", native)
        self.assertEqual(["tortilla_universal_cross"], json.loads(MANIFEST.read_text())["SettingsContract"]["DefaultPermittedPairIds"])
        self.assertIs(False, json.loads(MANIFEST.read_text())["Qualified"])


if __name__ == "__main__":
    unittest.main()
