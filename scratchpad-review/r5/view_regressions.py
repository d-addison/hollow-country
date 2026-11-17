"""Independent expected-red checks; all engine inputs are explicit synthetic fixtures.

No native runtime behaviour is inferred from these Python models. Source imports
come from the reviewed checkout, independent of the mutated scratch snapshots.
"""
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from tests.unit import test_taped_light_probe as pf, test_taped_light_report as f
from tools.audit import taped_light_report as report


def slot_of(observations):
    result = report.build_report(pf.classification(), observations)
    host = next(h for h in result["hosts"] if h["class"] == "AK74")
    return host["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]


def report_rows(items):
    row = f.row("AK74", "slot_host", f.gun_slots(weapon_model=False), f.good_gun_lights(), proxies=items)
    result = report.build_report(f.classification([f.host("AK74", "slot_host")]), f.observations([row]))
    return result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]


class ViewRegressions(unittest.TestCase):
    def test_another_proxy_model_in_view_lod_cannot_establish_membership(self):
        types = pf.proxy_types()
        types["AK74"]["view"] = (
            "components", "proxy:/dz/weapons/attachments/light/weaponlight_universal_extra.001")
        world = pf.World(types=types)
        pf.run_hook(world, slots=pf._NoSelectionSlots)
        obs = pf.observations_of(world)
        item = pf.host_row(obs, "AK74")["proxies"][0]
        slot = slot_of(obs)
        print("COINCIDENTAL_MODEL", json.dumps({"view": item["view_selection"],
              "slot": slot["verdict"], "reason": slot["reason"], "live": len(world.live())}), flush=True)
        self.assertEqual("pending", slot["verdict"])

    def test_a_generic_named_selection_cannot_establish_proxy_membership(self):
        item = f.proxy(view_selection="label/dz/weapons/attachments/light/weaponlight_universal")
        slot = report_rows([item])
        print("GENERIC_SELECTION", json.dumps({"slot": slot["verdict"], "reason": slot["reason"]}), flush=True)
        self.assertEqual("pending", slot["verdict"])

    def test_one_model_cannot_have_two_different_results_of_the_same_view_scan(self):
        cases = {
            "missing selection": dict(f.proxy(number="002"), view_selection="", view_vertex_ok=False, view_vertex=[]),
            "different vertex": f.proxy(number="002", vertex=("10", "20", "30")),
            "different selection": f.proxy(number="002", view_selection="proxy:" + f.LIGHT_PROXY_PATH + ".002"),
        }
        for name, second in cases.items():
            with self.subTest(case=name):
                slot = report_rows([f.proxy(number="001"), second])
                print("CONTRADICTORY_VIEW", json.dumps({"case": name, "slot": slot["verdict"],
                      "reason": slot["reason"]}), flush=True)
                self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]))

    def test_a_failed_view_enumeration_must_not_supply_a_qualified_match(self):
        # The native bool signature does not promise its out array is empty on failure.
        # Explicitly model a failed call that leaves data in its out argument.
        original = pf.ViewLod.GetSelections
        def failed(lod, out):
            original(lod, out)
            return False
        world = pf.World(types=pf.proxy_types())
        with mock.patch.object(pf.ViewLod, "GetSelections", failed):
            pf.run_hook(world, slots=pf._NoSelectionSlots)
        obs = pf.observations_of(world)
        host = pf.host_row(obs, "AK74")
        slot = slot_of(obs)
        print("FAILED_VIEW_ENUMERATION", json.dumps({"view_scan_complete": host["view_scan_complete"],
              "slot": slot["verdict"], "reason": slot["reason"], "live": len(world.live())}), flush=True)
        self.assertEqual("pending", slot["verdict"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
