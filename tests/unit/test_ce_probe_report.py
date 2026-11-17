"""Offline CE probe report; SYNTHETIC fixtures only, never DayZ behavior.

The report must never claim more than the evidence: zero raw points and an
empty census are recorded as observations, not as verified absence of loot.
"""
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.audit import ce_probe_report as report

STOCK_PROTO = b"""<?xml version="1.0" encoding="UTF-8"?>
<lootmax>
  <group name="SynthApartment" lootmax="0">
    <usage name="Town" />
    <container name="lootFloor" lootmax="0"><category name="tools" /></container>
    <container name="lootshelves" lootmax="0"><category name="books" /></container>
  </group>
  <group name="SynthBarracks" lootmax="10">
    <container name="lootFloor" lootmax="8">
      <point pos="1 2 3" range="1" height="2" />
      <point pos="4 5 6" range="1" height="2" />
    </container>
    <container name="lootweapons" lootmax="2"><point pos="7 8 9" range="1" height="2" /></container>
  </group>
  <group name="SynthHouse" lootmax="6">
    <container name="lootFloor" lootmax="6"><point pos="0 0 0" range="1" height="2" /></container>
  </group>
</lootmax>
"""
EXPORT_PROTO = b"""<lootmax>
  <group name="SynthApartment" lootmax="0">
    <container name="lootFloor" lootmax="0" />
  </group>
  <group name="SynthBarracks" lootmax="10">
    <container name="lootFloor" lootmax="8"><point pos="1 2 3" range="1" height="2" /></container>
  </group>
</lootmax>
"""


def row(klass, index, found=True, box="clipping", items=0, types=(), truncated=False, role="target"):
    return {"i": index, "class": klass, "role": role, "found": found, "type": klass if found else "",
            "distance": 0.1, "box_source": box if found else "none", "sphere_loose": items,
            "box_loose": items if found else 0, "truncated": truncated, "types": list(types)}


def census(rows):
    return {"schema": 1, "kind": "ce-probe-census", "world": "chernarusplus",
            "version": "SYNTHETIC", "placements": rows}


def by_class(result):
    return {entry["class"]: entry for entry in result["classes"]}


class ProtoParsingTests(unittest.TestCase):
    def test_groups_report_containers_points_and_lootmax(self):
        groups = report.parse_proto(STOCK_PROTO)
        self.assertEqual({"containers": 2, "points": 0, "lootmax": 0, "duplicates": 0}, groups["SynthApartment"])
        self.assertEqual({"containers": 2, "points": 3, "lootmax": 10, "duplicates": 0}, groups["SynthBarracks"])

    def test_entity_declarations_are_refused(self):
        evil = b'<!DOCTYPE x [<!ENTITY a "b">]><lootmax><group name="G" lootmax="1" /></lootmax>'
        with self.assertRaises(ValueError):
            report.parse_proto(evil)

    def test_duplicate_group_names_are_counted_not_merged(self):
        xml = b'<lootmax><group name="G" lootmax="1" /><group name="G" lootmax="9" /></lootmax>'
        self.assertEqual(1, report.parse_proto(xml)["G"]["duplicates"])
        self.assertEqual(1, report.parse_proto(xml)["G"]["lootmax"])


class StatusNeverOverclaimsTests(unittest.TestCase):
    def build(self, rows, export=None):
        return report.build_report(STOCK_PROTO, export, census(rows))

    def test_zero_raw_points_and_empty_census_is_not_verified_no_loot(self):
        result = by_class(self.build([row("SynthApartment", n) for n in range(4)]))["SynthApartment"]
        self.assertEqual(0, result["stock_points"])
        self.assertEqual("zero-raw-points-census-empty", result["status"])
        self.assertEqual(1.0, result["zero_item_fraction"])
        for forbidden in ("verified", "no-loot", "confirmed", "accepted"):
            self.assertNotIn(forbidden, result["status"])
        self.assertTrue(any("not evidence" in note for note in result["notes"]))

    def test_zero_raw_points_with_items_observed_is_flagged_as_unexpected(self):
        rows = [row("SynthApartment", 0, items=3, types=["Apple", "Rag"]), row("SynthApartment", 1)]
        result = by_class(self.build(rows))["SynthApartment"]
        self.assertEqual("zero-raw-points-items-observed", result["status"])
        self.assertEqual(1.5, result["item_count_mean"])
        self.assertEqual(0.5, result["zero_item_fraction"])
        self.assertEqual(2, result["distinct_item_types"])

    def test_points_present_and_items_observed(self):
        rows = [row("SynthBarracks", 0, items=4, types=["A", "B"]), row("SynthBarracks", 1, items=2, types=["B", "C"])]
        result = by_class(self.build(rows))["SynthBarracks"]
        self.assertEqual("points-present-items-observed", result["status"])
        self.assertEqual((2, 3, 10), (result["stock_containers"], result["stock_points"], result["stock_lootmax"]))
        self.assertEqual(3.0, result["item_count_mean"])
        self.assertEqual(0.0, result["zero_item_fraction"])
        self.assertEqual(3, result["distinct_item_types"])
        self.assertEqual((2, 2), (result["placements_sampled"], result["placements_found"]))

    def test_points_present_but_empty_census_is_not_proof_of_nonspawning(self):
        result = by_class(self.build([row("SynthBarracks", 0)]))["SynthBarracks"]
        self.assertEqual("points-present-census-empty", result["status"])
        self.assertNotIn("no-loot", result["status"])

    def test_class_not_found_in_world_is_not_a_coverage_statement(self):
        result = by_class(self.build([row("SynthHouse", 0, found=False), row("SynthHouse", 1, found=False)]))["SynthHouse"]
        self.assertEqual("not-found-in-census", result["status"])
        self.assertEqual((2, 0), (result["placements_sampled"], result["placements_found"]))
        self.assertIsNone(result["item_count_mean"])
        self.assertIsNone(result["zero_item_fraction"])

    def test_unusable_or_truncated_boxes_are_excluded_from_statistics(self):
        rows = [row("SynthHouse", 0, box="none", items=0), row("SynthHouse", 1, items=5, truncated=True)]
        result = by_class(self.build(rows))["SynthHouse"]
        self.assertEqual("census-box-unusable", result["status"])
        self.assertEqual(2, result["placements_found"])
        self.assertEqual(2, result["placements_unreliable"])
        self.assertIsNone(result["item_count_mean"])

    def test_class_missing_from_stock_proto_is_reported_as_such(self):
        result = by_class(self.build([row("SynthUnknown", 0, items=1)]))["SynthUnknown"]
        self.assertEqual("stock-group-missing", result["status"])
        self.assertIsNone(result["stock_points"])

    def test_exported_points_are_reported_beside_stock_and_differences_are_noted(self):
        result = by_class(self.build([row("SynthBarracks", 0, items=1)], export=EXPORT_PROTO))["SynthBarracks"]
        self.assertEqual((1, 1), (result["export_containers"], result["export_points"]))
        self.assertTrue(any("export differs" in note for note in result["notes"]))
        absent = by_class(self.build([row("SynthBarracks", 0, items=1)]))["SynthBarracks"]
        self.assertIsNone(absent["export_points"])

    def test_zero_points_in_stock_and_export_is_still_only_an_observation(self):
        result = by_class(self.build([row("SynthApartment", 0)], export=EXPORT_PROTO))["SynthApartment"]
        self.assertEqual(0, result["export_points"])
        self.assertEqual("zero-raw-points-census-empty", result["status"])

    def test_report_states_its_evidence_limits(self):
        result = self.build([row("SynthBarracks", 0, items=1)])
        self.assertIn("single census", " ".join(result["evidence_limits"]))
        self.assertEqual("observation-only-not-accepted", result["acceptance"])

    def test_malformed_census_is_rejected(self):
        with self.assertRaises(ValueError):
            report.build_report(STOCK_PROTO, None, {"placements": [{"class": "X"}]})
        with self.assertRaises(ValueError):
            report.build_report(STOCK_PROTO, None, {"placements": "no"})


class CsvTests(unittest.TestCase):
    def test_header_is_the_proposed_stable_building_coverage_header(self):
        self.assertEqual(
            ["building_class", "role", "stock_points", "stock_containers", "stock_lootmax",
             "export_points", "export_containers", "placements_sampled", "placements_found",
             "placements_unreliable", "item_count_mean", "zero_item_fraction",
             "distinct_item_types", "status", "evidence"],
            report.CSV_HEADER)

    def test_rows_round_trip_and_blank_means_unknown(self):
        result = report.build_report(STOCK_PROTO, None, census(
            [row("SynthBarracks", 0, items=2, types=["A"]), row("SynthHouse", 1, found=False)]))
        parsed = list(csv.DictReader(io.StringIO(report.csv_text(result))))
        self.assertEqual(["SynthBarracks", "SynthHouse"], sorted(r["building_class"] for r in parsed))
        house = next(r for r in parsed if r["building_class"] == "SynthHouse")
        self.assertEqual("", house["item_count_mean"])
        self.assertEqual("", house["export_points"])
        self.assertEqual("not-found-in-census", house["status"])


class CliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "stock.xml").write_bytes(STOCK_PROTO)
        (self.root / "census.json").write_text(json.dumps(census([row("SynthBarracks", 0, items=1)])))

    def args(self, *extra):
        return ["--stock-proto", str(self.root / "stock.xml"), "--census", str(self.root / "census.json"),
                "--out-json", str(self.root / "report.json"), "--out-csv", str(self.root / "report.csv"), *extra]

    def test_cli_writes_json_and_csv_with_input_hashes_and_never_overwrites(self):
        self.assertEqual(0, report.main(self.args()))
        data = json.loads((self.root / "report.json").read_text())
        self.assertEqual(64, len(data["inputs"]["stock_proto_sha256"]))
        self.assertEqual(64, len(data["inputs"]["census_sha256"]))
        self.assertIsNone(data["inputs"]["export_proto_sha256"])
        self.assertTrue((self.root / "report.csv").read_text().startswith("building_class,"))
        self.assertEqual(1, report.main(self.args()))

    def test_cli_refuses_to_write_into_the_repository_metrics_directory(self):
        metrics = Path(report.__file__).resolve().parents[2] / "metrics"
        argv = self.args()
        argv[argv.index("--out-csv") + 1] = str(metrics / "building_coverage.csv")
        self.assertEqual(1, report.main(argv))
        self.assertFalse((metrics / "building_coverage.csv").exists())

    def test_cli_reports_bad_input_with_exit_one(self):
        (self.root / "census.json").write_text("{not json")
        self.assertEqual(1, report.main(self.args()))


if __name__ == "__main__":
    unittest.main()
