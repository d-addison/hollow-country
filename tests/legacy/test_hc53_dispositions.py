"""Offline authored-data checks only; no synthetic or native DayZ observations."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tools/audit/data/hc53"
MISSION = ROOT / "mission/hollow-country/interiors"


class HC53DispositionsTests(unittest.TestCase):
    def test_dispositions_stay_out_of_runtime_pack_and_remain_pending(self):
        # These are the files present before HC-53, not a new runtime allowlist.
        self.assertEqual(
            {p.relative_to(MISSION).as_posix() for p in MISSION.rglob("*") if p.is_file()},
            {"pack.json", "pack-profile.json", "interiors.json", "evidence/house-candidates.json"},
            "HC-53 audit/source files must not be under mission interiors",
        )
        documents = {name: json.loads((DATA / name).read_text(encoding="utf-8"))
                     for name in ("coverage.json", "manifest.json", "priority-buildings.json")}
        coverage = documents["coverage.json"]
        counts = coverage["counts"]
        placed, unplaced = coverage["placed"], coverage["unplaced"]
        self.assertEqual((counts["placed_classes"], counts["stock_instances"], counts["unplaced167"]),
                         (269, 11679, 167))
        self.assertEqual(len(placed), counts["placed_classes"])
        self.assertEqual(sum(row["stock_instances"] for row in placed), counts["stock_instances"])
        self.assertEqual(len(unplaced), counts["unplaced167"])
        self.assertTrue(all(row["stock_instances"] == 0 for row in unplaced))
        self.assertEqual(len(placed) + len(unplaced), counts["prototypes"])
        classes = [row["building_class"] for row in placed + unplaced]
        self.assertEqual(len(set(classes)), counts["prototypes"])
        for family in coverage["families"]:
            rows = [row for row in placed if row["family"] == family["id"]]
            self.assertEqual(len(rows), family["placed_classes"])
            self.assertEqual(sum(row["stock_instances"] for row in rows), family["stock_instances"])
            self.assertEqual(sum(family["regions"].values()), family["stock_instances"])
        self.assertEqual(sum(f["placed_classes"] for f in coverage["families"]), len(placed))
        for name, document in documents.items():
            self.assertEqual(document["runtime_acceptance"], "pending", name)
            self.check_pending_and_no_coordinate_pairs(document, name)
        self.assertIs(documents["manifest.json"]["production_enabled"], False)
        for name, digest in documents["manifest.json"]["documents"].items():
            self.assertEqual(hashlib.sha256((DATA / name).read_bytes()).hexdigest(), digest, name)

    def check_pending_and_no_coordinate_pairs(self, value, path):
        if isinstance(value, dict):
            numeric_keys = {key.lower() for key, item in value.items() if type(item) in (int, float)}
            for axes in ({"x", "y"}, {"x", "z"}, {"y", "z"}, {"lat", "lon"}, {"latitude", "longitude"}):
                self.assertFalse(axes <= numeric_keys, path)
            for key, item in value.items():
                if key in ("runtime_acceptance", "native_acceptance", "qualification"):
                    self.assertEqual(item, "pending", path + "/" + key)
                if key in ("admitted", "observed"):
                    self.assertEqual(item, 0, path + "/" + key)
                self.check_pending_and_no_coordinate_pairs(item, path + "/" + key)
        elif isinstance(value, list):
            # Preserve existing 3D poses; prop IDs and API line numbers are metadata.
            if path.rsplit("/", 1)[-1] not in ("props", "lines"):
                self.assertFalse(len(value) == 2 and all(type(v) in (int, float) for v in value), path)
            for index, item in enumerate(value):
                self.check_pending_and_no_coordinate_pairs(item, path + "/" + str(index))


if __name__ == "__main__":
    unittest.main()
