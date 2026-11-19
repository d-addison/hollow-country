"""#58 item 1: every config slot extension must be backed by an existing model light proxy.

The fixture tests/fixtures/runtime/light-proxy-slot-table.json is a small table DERIVED from the
read-only probe-006 native observation (server-side proxy scan of every installed firearm model),
not a vanilla dump. Offline tests never establish DayZ behaviour; client alignment stays PENDING.
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
TABLE = json.loads((ROOT / 'tests/fixtures/runtime/light-proxy-slot-table.json').read_text())
CATALOG = (ROOT / 'mods/HollowCountry/scripts/3_Game/Survival/HCTapedLightCatalog.c').read_text()
CONFIG = (ROOT / 'mods/HollowCountry/config.cpp').read_text()
LIGHT_SLOTS = ('weaponFlashlight', 'pistolFlashlight')


class LightProxySlotTableTests(unittest.TestCase):
    def test_table_is_derived_and_marked_pending(self):
        self.assertEqual('PENDING', TABLE['acceptance'])
        self.assertIn('probe-006', TABLE['provenance']['source'])
        self.assertEqual(135, TABLE['provenance']['weapon_hosts_scanned'])
        self.assertEqual(135, len(TABLE['light_rows']) + len(TABLE['no_light_proxy_no_light_slot']))

    def test_only_scout_family_has_a_proxy_without_a_slot(self):
        gap = sorted(r['class'] for r in TABLE['light_rows'] if r['proxy'] and not r['slots'])
        self.assertEqual(['Scout', 'Scout_Chernarus', 'Scout_Livonia'], gap)

    def test_catalog_extension_rows_are_exactly_the_proxy_backed_slotless_hosts(self):
        rows = re.findall(r'Add\(rows, "([^"]+)", "([^"]+)", "([^"]+)", "([^"]*)", "([^"]*)"\);', CATALOG)
        by_class = {r['class']: r for r in TABLE['light_rows']}
        for host, light, slot, _, _ in rows:
            row = by_class[host]
            self.assertTrue(row['proxy'], host)
            self.assertEqual({'UniversalLight': 'weaponlight_universal.001',
                              'TLRLight': 'weaponlight_tlr.001'}[light], row['proxy'], host)
            self.assertTrue(slot in row['slots'] or not row['slots'], host)
        extension = sorted(h for h, _, _, _, _ in rows if not by_class[h]['slots'])
        self.assertEqual(['Scout', 'Scout_Chernarus', 'Scout_Livonia'], extension)

    def test_slot_without_proxy_is_never_a_catalog_host(self):
        no_proxy = [r['class'] for r in TABLE['light_rows'] if r['slots'] and not r['proxy']]
        self.assertEqual(['R12'], no_proxy)
        hosts = set(re.findall(r'Add\(rows, "([^"]+)"', CATALOG))
        self.assertFalse(hosts & set(no_proxy))

    def test_config_adds_light_slot_only_where_a_proxy_exists(self):
        added = re.findall(r'class (\w+): \w+\s*\{[^{}]*attachments\[\] = \{([^}]*)\}', CONFIG)
        by_class = {r['class']: r for r in TABLE['light_rows']}
        self.assertEqual(['Scout'], [c for c, a in added if any(s in a for s in LIGHT_SLOTS)])
        for cls, _ in added:
            if cls in by_class:
                self.assertTrue(by_class[cls]['proxy'], cls)

    def test_cross_slot_config_preserves_vanilla_arrays_and_inheritance(self):
        from tools.audit.pbo_config import parse_text_config
        classes = parse_text_config(CONFIG, ("CfgVehicles",))["CfgVehicles"]
        expected = {
            "TortillaBag": ("Clothing", "attachments", ["Chemlight", "WalkieTalkie", "Backpack_1", "NBCBag", "helmetFlashlight"]),
            "UniversalLight": ("Switchable_Base", "inventorySlot", ["weaponFlashlight", "helmetFlashlight", "pistolFlashlight", "Chemlight"]),
            "TLRLight": ("Switchable_Base", "inventorySlot", ["pistolFlashlight", "weaponFlashlight"]),
        }
        for name, (parent, field, slots) in expected.items():
            self.assertEqual(parent, classes[name]["parent"], name)
            self.assertEqual(slots, classes[name][field], name)
        self.assertIn('"DZ_Weapons_Lights"', CONFIG)
        self.assertIn("~/", CONFIG)

    def test_all_authored_pairs_have_slots_in_the_patched_static_table(self):
        from tools.audit.pbo_config import parse_text_config
        from tests.unit.test_hc_taped_pack_loader import light_catalogue
        classes = parse_text_config(CONFIG, ("CfgVehicles", "CfgWeapons"))
        lights = classes["CfgVehicles"]
        hosts = {r["class"]: r["slots"] for r in TABLE["light_rows"]}
        hosts["Scout"] = classes["CfgWeapons"]["Scout"]["attachments"]
        hosts["Scout_Chernarus"] = hosts["Scout"]
        hosts["Scout_Livonia"] = hosts["Scout"]
        catalogue = light_catalogue()
        refused = []
        for pair in catalogue.CrossPairIds():
            row = catalogue.CrossRow(pair)
            if row.SlotName not in hosts[row.HostClass] or row.SlotName not in lights[row.LightClass]["inventorySlot"]:
                refused.append(pair)
        manifest = json.loads((ROOT / "mission/hollow-country/lights/backpack-mounts.json").read_text())
        for row in manifest["AuthoredPairs"] + manifest["CrossSlotPairs"]:
            if (row["SlotName"] not in lights[row["HostClass"]]["attachments"] or
                    row["SlotName"] not in lights[row["LightClass"]]["inventorySlot"]):
                refused.append(row["PairId"])
        self.assertEqual([], refused)  # Static slots only; geometry/client acceptance PENDING.


if __name__ == '__main__':
    unittest.main()
