"""Interior measured-pack coverage report (audit #199 / #197); SYNTHETIC fixtures only.

The report states how much of the stock House denominator a qualifying native census covers, why a census
was rejected, and how many native sampler runs are still needed. It reads stock XML and census bytes and
writes nothing. It never shows how DayZ lays out, renders or spawns an interior; runtime acceptance of
every interior stays pending.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tests.slow import test_interior_templates as fixture
from tools.package import auditinterior_coverage as cov
from tools.package import interiors_profile as ip

ROOT = Path(__file__).resolve().parents[2]


def stock(count):
    """A synthetic stock with ``count`` placed House-like classes (each with one loot container point)."""
    names = ["Land_Synth_%03d" % i for i in range(count)]
    proto = fixture.proto_xml([fixture.group(n, [fixture.container("lootFloor", [fixture.point("1 0 1")])])
                               for n in names])
    pos = fixture.pos_xml([(n, "%d.0 10.0 %d.0" % (100 + i, 200 + i), "0.0") for i, n in enumerate(names)])
    return names, proto, pos


def legacy_census():
    """Shape of the three census files already on disk: no run id, no door phase contract."""
    document = fixture.census(fixture.house_rows(), fixture.CLASSES)
    for key in ("Synthetic", "door_phase_contract", "native_run_id", "house_classes"):
        del document[key]
    return fixture.encode(document)


class CensusClassificationTests(unittest.TestCase):
    def test_a_requested_phase_census_is_rejected_with_the_door_phase_reason(self):
        verdict = cov.classify_census("old/census.json", legacy_census())
        self.assertFalse(verdict["accepted"])
        self.assertEqual(verdict["reason"], "door_phase_contract")

    def test_a_census_without_a_native_run_id_is_rejected_by_name(self):
        document = fixture.census(fixture.house_rows(), fixture.CLASSES)
        del document["native_run_id"]
        verdict = cov.classify_census("x.json", fixture.encode(document))
        self.assertEqual((verdict["accepted"], verdict["reason"]), (False, "native_run_id"))

    def test_an_unfinished_census_is_rejected_as_incomplete(self):
        document = fixture.census(fixture.house_rows(), fixture.CLASSES, complete=False)
        verdict = cov.classify_census("x.json", fixture.encode(document))
        self.assertEqual((verdict["accepted"], verdict["reason"]), (False, "incomplete"))

    def test_garbage_bytes_are_rejected_as_unreadable_not_raised(self):
        verdict = cov.classify_census("x.json", b"{not json")
        self.assertEqual((verdict["accepted"], verdict["reason"]), (False, "unreadable"))

    def test_a_qualifying_census_names_its_run_and_measured_classes(self):
        rows = fixture.house_rows() + fixture.calibration_rows()
        verdict = cov.classify_census("good.json", fixture.encode(fixture.census(rows, fixture.CLASSES)))
        self.assertTrue(verdict["accepted"])
        self.assertEqual(verdict["run"], fixture.RUN)
        self.assertEqual(verdict["measured"], sorted(fixture.CLASSES))

    def test_the_label_never_carries_a_directory(self):
        verdict = cov.classify_census("/home/someone/secret/census.json", legacy_census())
        self.assertEqual(verdict["label"], "census.json")


class CoverageReportTests(unittest.TestCase):
    def test_no_qualifying_census_leaves_every_stock_class_unmeasured_and_sizes_the_survey(self):
        names, proto, pos = stock(130)
        report = cov.coverage(proto, pos, [("a.json", legacy_census())])
        self.assertEqual(report["stock_classes"], 130)
        self.assertEqual(report["placed_classes"], 130)
        self.assertEqual(report["measured_classes"], 0)
        self.assertEqual(report["unmeasured_classes"], 130)
        self.assertEqual(report["survey_runs_needed"], 3)  # 130 classes at one target each, 64 per run
        self.assertEqual(report["census_rejected"], 1)
        self.assertEqual(report["census_accepted"], 0)
        self.assertEqual(report["rejected"][0]["reason"], "door_phase_contract")
        self.assertEqual(report["state"], "pending-measurement")

    def test_measured_classes_leave_the_survey_queue(self):
        names, proto, pos = stock(70)
        measured = names[-6:]  # the whole second chunk, so its run is omitted
        rows = []
        for index, name in enumerate(measured):
            rows.extend(fixture.house_rows(cls=name))
        rows += fixture.calibration_rows()
        data = fixture.encode(fixture.census(rows, measured + list(fixture.CALIBRATION)))
        report = cov.coverage(proto, pos, [("good.json", data)])
        self.assertEqual(report["census_accepted"], 1)
        self.assertEqual(report["measured_classes"], 6)
        self.assertEqual(report["unmeasured_classes"], 64)
        self.assertEqual(report["survey_runs_needed"], 1)
        self.assertEqual(report["state"], "partial-pending-acceptance")

    def test_a_fully_measured_stock_needs_no_more_runs(self):
        names, proto, pos = stock(3)
        rows = []
        for name in names:
            rows.extend(fixture.house_rows(cls=name))
        rows += fixture.calibration_rows()
        data = fixture.encode(fixture.census(rows, names + list(fixture.CALIBRATION)))
        report = cov.coverage(proto, pos, [("good.json", data)])
        self.assertEqual(report["unmeasured_classes"], 0)
        self.assertEqual(report["survey_runs_needed"], 0)
        self.assertEqual(report["state"], "measured-pending-acceptance")

    def test_classes_without_a_stock_placement_are_counted_but_not_queued(self):
        proto = fixture.proto_xml([fixture.group("Land_Placed", [fixture.container("lootFloor", [fixture.point("1 0 1")])]),
                                   fixture.group("Land_Unplaced", [fixture.container("lootFloor", [fixture.point("1 0 1")])])])
        pos = fixture.pos_xml([("Land_Placed", "10 10 10", "0")])
        report = cov.coverage(proto, pos, [])
        self.assertEqual((report["stock_classes"], report["placed_classes"]), (2, 1))
        self.assertEqual(report["unplaced"], ["Land_Unplaced"])
        self.assertEqual(report["survey_runs_needed"], 1)

    def test_duplicate_run_ids_are_a_rejection_not_a_crash(self):
        names, proto, pos = stock(4)
        rows = fixture.house_rows(cls=names[0]) + fixture.calibration_rows()
        data = fixture.encode(fixture.census(rows, [names[0]] + list(fixture.CALIBRATION)))
        report = cov.coverage(proto, pos, [("one.json", data), ("two.json", data)])
        self.assertEqual((report["census_accepted"], report["census_rejected"]), (1, 1))
        self.assertEqual(report["rejected"][0]["reason"], "duplicate_run")

    def test_report_is_deterministic_and_json_serialisable(self):
        names, proto, pos = stock(5)
        first = cov.coverage(proto, pos, [("a.json", legacy_census())])
        second = cov.coverage(proto, pos, [("a.json", legacy_census())])
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_lines_carry_pending_wording_and_no_acceptance_claim(self):
        names, proto, pos = stock(5)
        text = "\n".join(cov.lines(cov.coverage(proto, pos, [])))
        self.assertIn("runtime=PENDING", text)
        self.assertIn("unmeasured=5", text)
        self.assertNotIn("accepted by DayZ", text)


class CommandTests(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ip.main(list(argv))
        return code, out.getvalue()

    def test_coverage_command_reads_files_prints_the_report_and_writes_nothing(self):
        names, proto, pos = stock(70)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "proto.xml").write_bytes(proto)
            (base / "pos.xml").write_bytes(pos)
            (base / "old.json").write_bytes(legacy_census())
            before = sorted(p.name for p in base.iterdir())
            code, text = self.run_cli("coverage", "--proto", str(base / "proto.xml"), "--pos", str(base / "pos.xml"),
                                      "--census", str(base / "old.json"))
            after = sorted(p.name for p in base.iterdir())
        self.assertIn(code, (0, None))
        self.assertEqual(before, after)
        self.assertIn("measured=0", text)
        self.assertIn("survey_runs=2", text)
        self.assertIn("door_phase_contract", text)
        self.assertIn("_old.json", text)
        self.assertNotIn(tmp, text)

    def test_coverage_json_flag_prints_one_object(self):
        names, proto, pos = stock(2)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "proto.xml").write_bytes(proto)
            (base / "pos.xml").write_bytes(pos)
            code, text = self.run_cli("coverage", "--proto", str(base / "proto.xml"), "--pos", str(base / "pos.xml"),
                                      "--json")
        self.assertEqual(json.loads(text)["stock_classes"], 2)

    def test_shipped_pack_is_untouched_by_the_report(self):
        pack = ROOT / "mission/hollow-country/interiors/pack.json"
        before = pack.read_bytes()
        names, proto, pos = stock(2)
        cov.coverage(proto, pos, [])
        self.assertEqual(pack.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
