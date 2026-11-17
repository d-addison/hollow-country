"""Review-only synthetic counterexamples. Expected failures expose acceptance gaps."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent / "baseline"
sys.path.insert(0, str(BASE))
from tests.unit import test_weather_report as f
from tests.unit import test_weather_probe as p
from tools.audit import weather_report as r
from tools.setup import weather_probe as w, diagnostic_mission as dm, probe_runtime as rt
from tools.package import atmosphere


def stream(actual, *, frozen=False, ticking=True, live=(0, 1), forecast=None):
    rows = [f.header(6)]
    for i in range(6):
        row = f.sample(i, {"overcast": actual}, frozen=frozen, limits={"overcast": live})
        row["weather_time"] = i * 30 if ticking else 10
        row["phenomena"]["overcast"]["next_change"] = 1000
        if forecast is not None:
            row["phenomena"]["overcast"]["forecast"] = forecast
        rows.append(row)
    return f.lines(rows + [f.end(6)])


class ReviewCases(unittest.TestCase):
    def test_frozen_non_ticking_runs_do_not_establish_precedence(self):
        stock = r.evaluate(stream(.3, frozen=True, ticking=False), f.STOCK)
        cand = r.evaluate(stream(.65, frozen=True, ticking=False), f.cfgweather(overcast=(.6, .7)))
        result = r.compare(stock, cand)
        actual = result["phenomena"]["overcast"]["evidence"]
        print("frozen/no tick:", json.dumps({"evidence": actual, "clock_advanced": cand["weather_time_advanced"],
              "frozen": cand["update_frozen"], "enable": cand["cfgweather"]["enable"]}))
        self.assertNotEqual("candidate_governs", actual)

    def test_no_forecast_boundary_and_conflicting_limits_do_not_establish_precedence(self):
        stock = r.evaluate(stream(.3), f.STOCK)
        cand = r.evaluate(stream(.9, forecast=.3), f.DISTINCT)
        result = r.compare(stock, cand)
        actual = result["phenomena"]["overcast"]["evidence"]
        print("no forecast boundary:", json.dumps({"evidence": actual, "overcast": cand["phenomena"]["overcast"]}))
        self.assertNotEqual("candidate_governs", actual)

    def test_incompatible_plan_sources_and_builds_make_comparison_pending(self):
        def plan(xml, variant, pin):
            return {"kind": "weather-probe", "source": {"launch_plan_sha256": pin},
                    "probe": {"samples": 6, "interval_s": 30, "observations_kind": r.OBSERVATIONS_KIND,
                              "hook_sha256": pin, "cfgweather": {"variant": variant,
                              "staged_sha256": f.sha(xml), "stock_sha256": pin}}}
        stock_text = stream(.3).replace('1.30.164289', '1.29.000000')
        stock = r.evaluate(stock_text, f.STOCK, plan=plan(f.STOCK, "stock", "a" * 64))
        cand = r.evaluate(stream(.9), f.DISTINCT, plan=plan(f.DISTINCT, "candidate", "b" * 64))
        result = r.compare(stock, cand)
        print("incompatible runs:", result["status"], result["phenomena"]["overcast"]["evidence"], result["issues"])
        self.assertEqual("pending", result["status"])

    def test_duplicate_json_keys_make_run_pending(self):
        text = f.run().replace('"actual": 0.9', '"actual": 0.1, "actual": 0.9', 1)
        result = r.evaluate(text, f.DISTINCT)
        print("duplicate actual key:", result["status"], result["issues"])
        self.assertEqual("pending", result["status"])

    def test_overflowed_numeric_value_is_pending_instead_of_crashing(self):
        rows = [f.header(6)] + [f.sample(i) for i in range(6)] + [f.end(6)]
        rows[1]["phenomena"]["overcast"]["actual"] = 10 ** 400
        self.assertEqual("pending", r.evaluate(f.lines(rows), f.DISTINCT)["status"])

    def test_overflow_cli_does_not_escape_with_a_traceback(self):
        rows = [f.header(6)] + [f.sample(i) for i in range(6)] + [f.end(6)]
        rows[1]["phenomena"]["overcast"]["actual"] = 10 ** 400
        with tempfile.TemporaryDirectory() as tmp:
            root = f.RuntimeAndCliTests().make_runtime(Path(tmp), observations=f.lines(rows))
            result = subprocess.run([sys.executable, "-B", str(BASE / "tools/audit/weather_report.py"),
                                     "single", "--runtime", str(root)], capture_output=True, text=True)
            print("overflow CLI:", result.returncode, result.stderr.splitlines()[-1])
            self.assertEqual(3, result.returncode)

    def test_repeated_timestamps_are_not_a_valid_ordered_sampling_run(self):
        rows = [f.header(6)] + [f.sample(i) for i in range(6)] + [f.end(6)]
        for row in rows[1:-1]:
            row["game_ms"] = 1
        result = r.evaluate(f.lines(rows), f.DISTINCT)
        print("repeated game_ms:", result["status"], result["issues"])
        self.assertEqual("pending", result["status"])

    def test_comparison_below_min_samples_is_pending(self):
        stock = r.evaluate(f.run(4, overrides={"overcast": .3}), f.STOCK)
        cand = r.evaluate(f.run(4), f.DISTINCT)
        result = r.compare(stock, cand)
        print("four-sample comparison:", result["status"], result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("pending", result["status"])

    def test_null_phenomena_is_pending_without_none_iteration_crash(self):
        rows = [f.header(6)] + [f.sample(i) for i in range(6)] + [f.end(6)]
        rows[1]["phenomena"] = None
        self.assertEqual("pending", r.evaluate(f.lines(rows), f.DISTINCT)["status"])

    def test_unreported_candidate_drift_is_refused_against_available_stock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = p.write_source_runtime(root / "source")
            candidate = p.write_candidate(root / "candidate")
            path = candidate / "cfgweather.xml"
            tree = ET.fromstring(path.read_bytes())
            tree.find("fog/limits").set("max", "0.5")  # absent from profile overrides and changes
            data = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
            path.write_bytes(data)
            report_path = candidate / "atmosphere-report.json"
            report = json.loads(report_path.read_text())
            report["candidate_sha256"] = f.sha(data)
            report_path.write_bytes(atmosphere.encode(report))
            manifest_path = candidate / "atmosphere-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"]["cfgweather.xml"] = f.sha(data)
            manifest["files"]["atmosphere-report.json"] = f.sha(report_path.read_bytes())
            manifest_path.write_bytes(atmosphere.encode(manifest))
            with mock.patch.dict(rt.LAUNCHER_PROBES, p.LAUNCHER_ROW), mock.patch.dict(dm._PURPOSES):
                with self.assertRaises(ValueError):
                    plan = w.stage(source, root / "weather-cand", candidate=candidate,
                                   battleye_sha256=p.SYNTH_BE_SHA, _wsl_parent=root)
                    print("unreported fog drift: staged; source_verified=", plan["probe"]["cfgweather"]["candidate"]["source_verified"])

    def test_conflicting_purpose_row_cannot_substitute_fixed_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = p.write_source_runtime(root / "source")
            with mock.patch.dict(rt.LAUNCHER_PROBES, p.LAUNCHER_ROW), mock.patch.dict(dm._PURPOSES, {w.PURPOSE: dm._PURPOSES["selftests"]}):
                with self.assertRaises(ValueError):
                    plan = w.stage(source, root / "weather-test", battleye_sha256=p.SYNTH_BE_SHA, _wsl_parent=root)
                    init = (root / "weather-test" / p.MISSION / "init.c").read_bytes()
                    print("conflicting purpose: staged; weather sampler present=", b"HCWPSampleLine" in init,
                          "weather hook hash advertised=", plan["probe"]["hook_sha256"] == f.sha(w.render_hook()))

    def test_missing_purpose_should_be_refused_without_mutating_shared_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = p.write_source_runtime(root / "source")
            with mock.patch.dict(rt.LAUNCHER_PROBES, p.LAUNCHER_ROW), mock.patch.dict(dm._PURPOSES):
                dm._PURPOSES.pop(w.PURPOSE, None)
                with self.assertRaises(ValueError):
                    w.stage(source, root / "weather-test", battleye_sha256=p.SYNTH_BE_SHA, _wsl_parent=root)
                    print("missing purpose: staged; shared registry mutated=", w.PURPOSE in dm._PURPOSES)

    def test_conflicting_generated_purpose_metadata_should_be_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = p.write_source_runtime(root / "source")
            wrong = ("disposable-something-else", None, ["wrong prerequisites"])
            with mock.patch.dict(rt.LAUNCHER_PROBES, p.LAUNCHER_ROW), mock.patch.dict(dm._PURPOSES, {w.PURPOSE: wrong}):
                with self.assertRaises(ValueError):
                    w.stage(source, root / "weather-test", battleye_sha256=p.SYNTH_BE_SHA, _wsl_parent=root)
                    marker = root / "weather-test" / p.MISSION / dm.MARKER_NAME
                    print("wrong generated purpose: staged; manifest kind=", json.loads(marker.read_text())["kind"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
