"""Offline comparator contract tests. All fixtures are synthetic.

T007/AC-009 adversarial TDD record:
Red: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
     -p test_benchmark.py -k adversarial -v
Actual result before fixes: 4 tests, 11 failures; each invalid case returned
CLI exit 0 / PASS instead of exit 2 / INVALID (including threshold -0.0).
Green: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
       -p test_benchmark.py -v
Follow-up red: same command with -k json_numeric_underflow -v: 1 test,
1 failure; a bare negative JSON numeric token also returned exit 0 / PASS.
Actual final green result: 42 tests, OK.
"""
import csv
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/benchmark"
FIELDS = next(csv.reader((ROOT / "metrics/benchmark-template.csv").open()))


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=FIXTURES)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.baseline = self.directory / "baseline.csv"
        self.candidate = self.directory / "candidate.csv"
        for name in ("baseline", "candidate"):
            for suffix in (".csv", ".csv.manifest.json"):
                (self.directory / (name + suffix)).write_bytes((FIXTURES / (name + suffix)).read_bytes())

    def rows(self, path):
        with path.open(newline="") as stream:
            return list(csv.DictReader(stream))

    def write_rows(self, path, rows, fields=None):
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS if fields is None else fields)
            writer.writeheader()
            writer.writerows(rows)

    def change(self, field, value, path=None, index=None):
        path = path or self.candidate
        rows = self.rows(path)
        for position, row in enumerate(rows):
            if index is None or position == index:
                row[field] = value
        self.write_rows(path, rows)

    def manifest_path(self, path):
        return Path(str(path) + ".manifest.json")

    def change_context(self, field, value, path=None):
        path = self.manifest_path(path or self.candidate)
        data = json.loads(path.read_text())
        for context in data["runs"].values():
            context[field] = value
        path.write_text(json.dumps(data))

    def run_cli(self, *args, code=0):
        result = subprocess.run(
            [sys.executable, "-B", "-m", "tools.benchmark.compare", "--baseline", str(self.baseline),
             "--candidate", str(self.candidate), *map(str, args)], cwd=ROOT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), text=True, capture_output=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        try:
            return json.loads(result.stdout)
        except ValueError:
            self.fail("Expected JSON report: " + result.stdout + result.stderr)

    def assert_invalid(self, *args):
        report = self.run_cli(*args, code=2)
        self.assertEqual(report["status"], "INVALID")
        self.assertTrue(report["errors"])
        return report

    def test_module_importable(self):
        importlib.import_module("tools.benchmark.compare")

    def test_calibrated_verified_repeated_pairs_pass(self):
        report = self.run_cli("--max-regression-pct", "3")
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["pair_count"], 3)
        self.assertEqual(report["groups"][0]["repeat_count"], 3)
        self.assertIn("offline", report["scope"].lower())
        self.assertIn("DayZ", report["scope"])
        self.assertTrue(report["context_verified"])

    def test_no_threshold_is_incomplete(self):
        report = self.run_cli(code=2)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertTrue(any("threshold" in reason.lower() for reason in report["reasons"]))
        self.assertIsNone(report["max_regression_pct"])

    def test_missing_manifests_is_unverified_incomplete(self):
        self.manifest_path(self.baseline).unlink()
        self.manifest_path(self.candidate).unlink()
        report = self.run_cli("--max-regression-pct", "3", code=2)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertFalse(report["context_verified"])
        self.assertEqual(report["pair_count"], 3)
        self.assertTrue(any("manifest" in reason.lower() for reason in report["reasons"]))

    def test_one_missing_manifest_prevents_acceptance(self):
        self.manifest_path(self.candidate).unlink()
        report = self.run_cli("--max-regression-pct", "3", code=2)
        self.assertEqual(report["status"], "INCOMPLETE")

    def test_manifest_overrides(self):
        path = self.directory / "custom.json"
        self.manifest_path(self.candidate).rename(path)
        report = self.run_cli("--max-regression-pct", "3", "--candidate-manifest", path,
                              "--baseline-manifest", self.manifest_path(self.baseline))
        self.assertEqual(report["status"], "PASS")

    def test_missing_explicit_manifest_is_invalid(self):
        self.assert_invalid("--candidate-manifest", self.directory / "missing.json")

    def test_incomplete_manifest_prevents_acceptance(self):
        for field in ("hardware", "mission", "warmup_seconds", "sample_seconds"):
            with self.subTest(field=field):
                original = self.manifest_path(self.candidate).read_text()
                data = json.loads(original)
                del data["runs"]["candidate-1"][field]
                self.manifest_path(self.candidate).write_text(json.dumps(data))
                report = self.run_cli("--max-regression-pct", "3", code=2)
                self.assertEqual(report["status"], "INCOMPLETE")
                self.manifest_path(self.candidate).write_text(original)

    def test_manifest_context_mismatch_is_invalid(self):
        for field, value in (("hardware", "different"), ("mission", "different"),
                             ("warmup_seconds", 0), ("sample_seconds", 240)):
            with self.subTest(field=field):
                original = self.manifest_path(self.candidate).read_text()
                self.change_context(field, value)
                self.assert_invalid("--max-regression-pct", "3")
                self.manifest_path(self.candidate).write_text(original)

    def test_bad_manifest_is_invalid(self):
        for value in ("{", "[]", '{"runs": []}', '{"runs": {}}'):
            with self.subTest(value=value):
                self.manifest_path(self.candidate).write_text(value)
                self.assert_invalid()

    def test_invalid_context_values(self):
        for field, value in (("hardware", ""), ("mission", {}), ("warmup_seconds", -1),
                             ("warmup_seconds", True), ("warmup_seconds", "NaN"),
                             ("sample_seconds", 0)):
            with self.subTest(field=field, value=value):
                original = self.manifest_path(self.candidate).read_text()
                self.change_context(field, value)
                self.assert_invalid()
                self.manifest_path(self.candidate).write_text(original)

    def test_all_template_fields_required(self):
        rows = self.rows(self.candidate)
        for field in FIELDS:
            with self.subTest(field=field):
                reduced = [{key: value for key, value in row.items() if key != field} for row in rows]
                self.write_rows(self.candidate, reduced, [key for key in FIELDS if key != field])
                self.assert_invalid()
        self.write_rows(self.candidate, rows)

    def test_empty_identity_fields_rejected(self):
        for field in ("run_id", "game_build", "git_commit", "scenario", "seed"):
            with self.subTest(field=field):
                original = self.candidate.read_text()
                self.change(field, " ", index=0)
                self.assert_invalid()
                self.candidate.write_text(original)

    def test_numeric_values_finite_nonnegative(self):
        numeric = FIELDS[FIELDS.index("player_count"):FIELDS.index("notes")]
        for field in numeric:
            for value in ("", "NaN", "inf", "-inf", "-1", "bad"):
                with self.subTest(field=field, value=value):
                    original = self.candidate.read_text()
                    self.change(field, value, index=0)
                    self.assert_invalid()
                    self.candidate.write_text(original)

    def test_frame_and_fps_metrics_strictly_positive(self):
        for field in ("avg_server_fps", "p01_server_fps", "p95_server_frame_ms",
                      "p99_server_frame_ms", "client_avg_fps", "client_1pct_low_fps"):
            with self.subTest(field=field):
                original = self.candidate.read_text()
                self.change(field, "0", index=0)
                self.assert_invalid()
                self.candidate.write_text(original)

    def test_counts_integral_and_errors_zero(self):
        for field in ("player_count", "active_infected", "active_hordes", "active_interiors",
                      "active_objects", "errors"):
            with self.subTest(field=field):
                original = self.candidate.read_text()
                self.change(field, "0.5", index=0)
                self.assert_invalid()
                self.candidate.write_text(original)
        for path in (self.baseline, self.candidate):
            original = path.read_text()
            self.change("errors", "1", path=path)
            self.assert_invalid()
            path.write_text(original)

    def test_pairing_context_must_match(self):
        for field in ("scenario", "seed", "game_build", "player_count", "active_infected",
                      "active_hordes", "active_interiors", "active_objects"):
            with self.subTest(field=field):
                original = self.candidate.read_text()
                self.change(field, "999", index=0)
                self.assert_invalid("--max-regression-pct", "3")
                self.candidate.write_text(original)

    def test_git_commits_must_differ(self):
        self.change("git_commit", "synthetic-before")
        self.assert_invalid("--max-regression-pct", "3")

    def test_mixed_commits_rejected(self):
        self.change("git_commit", "third-commit", index=0)
        self.assert_invalid()

    def test_reordered_rows_pair_by_context(self):
        self.write_rows(self.candidate, list(reversed(self.rows(self.candidate))))
        report = self.run_cli("--max-regression-pct", "3")
        for pair in report["pairs"]:
            self.assertEqual(pair["baseline_run_id"].split("-")[-1],
                             pair["candidate_run_id"].split("-")[-1])

    def test_unmatched_runs_rejected(self):
        self.write_rows(self.candidate, self.rows(self.candidate)[:-1])
        self.assert_invalid()

    def test_duplicate_run_ids_rejected(self):
        self.change("run_id", "candidate-1")
        self.assert_invalid()

    def test_ambiguous_pairs_require_explicit_pair_id(self):
        self.change("seed", "101", path=self.baseline)
        self.change("seed", "101")
        self.assert_invalid()
        for path in (self.baseline, self.candidate):
            manifest_path = self.manifest_path(path)
            data = json.loads(manifest_path.read_text())
            for run_id, context in data["runs"].items():
                context["pair_id"] = run_id.split("-")[-1]
            manifest_path.write_text(json.dumps(data))
        report = self.run_cli("--max-regression-pct", "3")
        self.assertEqual(report["pair_count"], 3)

    def test_object_count_change_requires_switch_and_is_reported(self):
        self.change("active_objects", "120")
        self.assert_invalid("--max-regression-pct", "3")
        report = self.run_cli("--max-regression-pct", "3", "--allow-object-count-change")
        self.assertEqual(len(report["object_count_changes"]), 3)
        self.assertEqual(report["object_count_changes"][0]["baseline"], 100)
        self.assertEqual(report["object_count_changes"][0]["candidate"], 120)
        self.assertTrue(report["allow_object_count_change"])

    def test_single_pair_per_group_is_incomplete(self):
        for path in (self.baseline, self.candidate):
            self.write_rows(path, self.rows(path)[:1])
        report = self.run_cli("--max-regression-pct", "3", code=2)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertTrue(any("repeat" in reason.lower() for reason in report["reasons"]))

    def test_scenarios_are_aggregated_separately(self):
        for path in (self.baseline, self.candidate):
            self.change("scenario", "other-scenario", path=path, index=0)
        report = self.run_cli("--max-regression-pct", "3", code=2)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(sorted(group["repeat_count"] for group in report["groups"]), [1, 2])

    def test_aggregate_is_mean_paired_percent_not_ratio_of_means(self):
        for path, values in ((self.baseline, (10, 100, 10)), (self.candidate, (12, 100, 12))):
            rows = self.rows(path)
            for row, value in zip(rows, values):
                row["p95_server_frame_ms"] = str(value)
                row["p99_server_frame_ms"] = "150"  # Maintain valid ordered quantiles.
            self.write_rows(path, rows)
        report = self.run_cli("--max-regression-pct", "10", code=1)
        self.assertEqual(report["status"], "FAIL")
        metric = report["groups"][0]["metrics"]["p95_server_frame_ms"]
        self.assertAlmostEqual(metric["mean_paired_regression_pct"], 40 / 3)
        self.assertEqual(metric["paired_regression_pct"], [20, 0, 20])
        self.assertEqual(metric["min_paired_regression_pct"], 0)
        self.assertEqual(metric["max_paired_regression_pct"], 20)
        self.assertGreater(metric["stdev_paired_regression_pct"], 0)

    def test_all_three_metrics_gate_in_correct_direction(self):
        for field, value in (("p95_server_frame_ms", "22"), ("p99_server_frame_ms", "33"),
                             ("client_1pct_low_fps", "45")):
            with self.subTest(field=field):
                original = self.candidate.read_text()
                self.change(field, value)
                report = self.run_cli("--max-regression-pct", "5", code=1)
                self.assertEqual(report["status"], "FAIL")
                self.assertEqual(report["groups"][0]["metrics"][field]["status"], "FAIL")
                self.candidate.write_text(original)

    def test_improvements_and_exact_threshold_pass(self):
        self.change("p95_server_frame_ms", "19")
        self.change("p99_server_frame_ms", "31.5")
        self.change("client_1pct_low_fps", "55")
        report = self.run_cli("--max-regression-pct", "5")
        self.assertEqual(report["status"], "PASS")

    def test_missing_prerequisites_take_precedence_over_regression(self):
        self.change("p99_server_frame_ms", "60")
        self.manifest_path(self.candidate).unlink()
        report = self.run_cli("--max-regression-pct", "3", code=2)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["groups"][0]["metrics"]["p99_server_frame_ms"]["status"], "FAIL")

    def test_invalid_thresholds(self):
        for value in ("NaN", "inf", "-1", "abc"):
            with self.subTest(value=value):
                self.assert_invalid("--max-regression-pct", value)

    def test_empty_and_malformed_csv(self):
        original = self.candidate.read_text()
        for value in ("", ",".join(FIELDS) + "\n", original.replace("run_id,", "notes,", 1),
                      original + "too,few,columns\n", original.replace("synthetic-build", "a,b", 1)):
            with self.subTest(value=value[:50]):
                self.candidate.write_text(value)
                self.assert_invalid()
        self.candidate.write_text(original)

    def test_extreme_finite_values_do_not_emit_nonfinite_json(self):
        self.change("p95_server_frame_ms", "1e-300", path=self.baseline)
        self.change("p95_server_frame_ms", "1e300")
        for path in (self.baseline, self.candidate):
            self.change("p99_server_frame_ms", "1e300", path=path)
        self.assert_invalid("--max-regression-pct", "3")

    def test_large_values_have_safe_means(self):
        self.change("p95_server_frame_ms", "1e308", path=self.baseline)
        self.change("p95_server_frame_ms", "1e308")
        for path in (self.baseline, self.candidate):
            self.change("p99_server_frame_ms", "1e308", path=path)
        report = self.run_cli("--max-regression-pct", "3")
        self.assertEqual(report["groups"][0]["metrics"]["p95_server_frame_ms"]["baseline_mean"], 1e308)

    def test_output_file_matches_stdout(self):
        output = self.directory / "report.json"
        report = self.run_cli("--max-regression-pct", "3", "--output", output)
        self.assertEqual(json.loads(output.read_text()), report)

    def test_output_cannot_overwrite_evidence(self):
        for path in (self.baseline, self.candidate, self.manifest_path(self.candidate)):
            with self.subTest(path=path):
                original = path.read_bytes()
                self.assert_invalid("--output", path)
                self.assertEqual(path.read_bytes(), original)

    def test_adversarial_reversed_frame_quantiles_cannot_pass(self):
        # A purported p99 below p95 is impossible for one run's frame samples.
        for path in (self.baseline, self.candidate):
            with self.subTest(side=path.stem):
                original = path.read_text()
                self.change("p95_server_frame_ms", "31", path=path)
                self.change("p99_server_frame_ms", "30", path=path)
                report = self.assert_invalid("--max-regression-pct", "100")
                self.assertTrue(any("p95" in error and "p99" in error
                                    for error in report["errors"]))
                path.write_text(original)

    def test_adversarial_unchecked_manifest_context_cannot_pass(self):
        # Matching hardware/mission does not make different client settings comparable.
        originals = {path: self.manifest_path(path).read_text()
                     for path in (self.baseline, self.candidate)}
        for extra, baseline, candidate in (("client_settings", "ultra", "low"),
                                            ("weather", "storm", "clear"),
                                            ("sample_second", 120, 240)):
            with self.subTest(field=extra):
                for path, value in ((self.baseline, baseline), (self.candidate, candidate)):
                    self.manifest_path(path).write_text(originals[path])
                    self.change_context(extra, value, path=path)
                report = self.assert_invalid("--max-regression-pct", "3")
                self.assertTrue(any(extra in error for error in report["errors"]))
        for path, original in originals.items():
            self.manifest_path(path).write_text(original)

    def test_adversarial_negative_underflow_threshold_cannot_pass(self):
        for field, value in (("p95_server_frame_ms", "20"), ("p99_server_frame_ms", "30"),
                             ("client_1pct_low_fps", "50")):
            self.change(field, value)
        report = self.assert_invalid("--max-regression-pct=-1e-1000")
        self.assertTrue(any("max_regression_pct" in error for error in report["errors"]))

    def test_adversarial_negative_underflow_measurement_cannot_pass(self):
        for field in ("peak_ram_mb", "script_ms_per_frame", "allocations_per_min", "network_kbps"):
            with self.subTest(field=field):
                original = self.candidate.read_text()
                self.change(field, "-1e-1000")
                report = self.assert_invalid("--max-regression-pct", "3")
                self.assertTrue(any(field in error for error in report["errors"]))
                self.candidate.write_text(original)
        for path in (self.baseline, self.candidate):
            self.change_context("warmup_seconds", "-1e-1000", path=path)
        self.assert_invalid("--max-regression-pct", "3")

    def test_adversarial_json_numeric_underflow_cannot_pass(self):
        # Preserve the JSON numeric token; Python floats already lose its sign/value.
        for path in (self.baseline, self.candidate):
            manifest = self.manifest_path(path)
            data = json.loads(manifest.read_text())
            for context in data["runs"].values():
                context["warmup_seconds"] = "SYNTHETIC_NEGATIVE_UNDERFLOW"
            manifest.write_text(json.dumps(data).replace('"SYNTHETIC_NEGATIVE_UNDERFLOW"',
                                                        "-1e-1000"))
        report = self.assert_invalid("--max-regression-pct", "3")
        self.assertTrue(any("warmup_seconds" in error for error in report["errors"]))

    def test_missing_csv_is_invalid(self):
        self.candidate.unlink()
        self.assert_invalid()


if __name__ == "__main__":
    unittest.main()
