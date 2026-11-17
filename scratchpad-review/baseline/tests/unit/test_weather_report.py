"""Offline tests for the weather precedence report; every observation here is SYNTHETIC.

The report compares native observations to a cfgweather.xml's limits. These tests only prove the
comparison and its pending rules; they say nothing about what DayZ actually does.

Actual TDD 2026-11-17:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_weather_probe tests.unit.test_weather_report -v
RED: ImportError cannot import name 'weather_report' from 'tools.audit' (module missing).
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tests.unit import test_atmosphere as atmosphere_fixtures
from tools.audit import weather_report as report

ROOT = Path(__file__).resolve().parents[2]
PHENOMENA = ("overcast", "fog", "rain", "windMagnitude", "windDirection", "snowfall")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cfgweather(**limits):
    """Synthetic cfgweather.xml; limits maps phenomenon -> (min, max) overriding the fixture's limits."""
    root = ET.fromstring(atmosphere_fixtures.fixture())
    for name, (low, high) in limits.items():
        node = root.find(name + "/limits")
        node.set("min", str(low))
        node.set("max", str(high))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


STOCK = cfgweather()
# Distinct from the script's own picks (0.2-0.7 start overcast) on purpose.
DISTINCT = cfgweather(overcast=(0.8, 0.95))


def number(value, text=False):
    return str(value) if text else value


# Live limits the DISTINCT fixture's cfgweather.xml declares (see tests.unit.test_atmosphere.fixture).
LIVE_LIMITS = {"overcast": (0.8, 0.95), "fog": (0.0, 1.0), "rain": (0.0, 1.0), "windMagnitude": (0.0, 20.0),
               "windDirection": (-3.14, 3.14), "snowfall": (0.0, 0.0)}
LIVE_CHANGE_MAX = {"overcast": 1.0, "fog": 1.0, "rain": 1.0, "windMagnitude": 20.0, "windDirection": 3.14,
                   "snowfall": 0.0}


def phenomenon(name, actual, text=False, limits=None, **extra):
    low, high = limits or LIVE_LIMITS[name]
    row = {"actual": number(actual, text), "forecast": number(actual, text), "next_change": number(300, text),
           "limit_min": number(low, text), "limit_max": number(high, text),
           "change_min": number(0.0, text), "change_max": number(LIVE_CHANGE_MAX[name], text),
           "time_min": number(60.0, text), "time_max": number(900.0, text)}
    row.update(extra)
    return row


def header(planned=6, **extra):
    row = {"type": "header", "schema": 1, "kind": "weather-probe-observations", "world": "ChernarusPlus",
           "version": "1.30.164289", "planned_samples": planned, "interval_ms": 30000, "cap_ms": 300000}
    row.update(extra)
    return row


def sample(seq, actuals=None, mission_weather=False, frozen=False, text=False, limits=None):
    actuals = actuals or {}
    values = {"overcast": 0.9, "fog": 0.1, "rain": 0.0, "windMagnitude": 4.0, "windDirection": 0.5, "snowfall": 0.0}
    values.update(actuals)
    return {"type": "sample", "seq": seq, "game_ms": 30000 * seq, "weather_time": number(30 * seq, text),
            "mission_weather": mission_weather, "update_frozen": frozen, "year": 2026, "month": 11, "day": 17,
            "hour": 9, "minute": seq, "wind_speed": number(4, text), "wind_max_speed": number(20, text),
            "volfog_enabled": True, "volfog_distance_density": number(0.1, text),
            "volfog_height_density": number(0.2, text), "volfog_height_bias": number(50, text),
            "phenomena": {name: phenomenon(name, values[name], text, (limits or {}).get(name)) for name in PHENOMENA}}


def end(samples=6, status="complete"):
    return {"type": "end", "status": status, "samples": samples, "write_errors": 0, "end_ms": 200000}


def lines(rows):
    return "\n".join(row if isinstance(row, str) else json.dumps(row) for row in rows) + "\n"


def run(count=6, xml=DISTINCT, overrides=None, **kwargs):
    """Observations of `count` clean samples inside the DISTINCT candidate's overcast limits."""
    rows = [header(count)] + [sample(i, overrides) for i in range(count)] + [end(count)]
    return lines(rows)


class SingleRunTests(unittest.TestCase):
    def test_a_clean_run_inside_the_candidate_limits_is_within_candidate_for_every_phenomenon(self):
        result = report.evaluate(run(), DISTINCT)
        self.assertEqual("complete", result["status"])
        self.assertEqual([], result["issues"])
        self.assertEqual(6, result["samples"])
        for name in PHENOMENA:
            self.assertEqual("within_candidate", result["phenomena"][name]["status"], name)
        overcast = result["phenomena"]["overcast"]
        self.assertEqual({"min": 0.8, "max": 0.95}, overcast["candidate_limits"])
        self.assertEqual({"min": 0.9, "max": 0.9}, overcast["actual_range"])
        self.assertEqual("pending", result["runtime_acceptance"])
        self.assertFalse(result["feature_complete"])

    def test_actual_values_outside_the_candidate_limits_violate_only_that_phenomenon(self):
        rows = [header(6)] + [sample(i, {"overcast": 0.3 if i < 2 else 0.9}) for i in range(6)] + [end(6)]
        result = report.evaluate(lines(rows), DISTINCT)
        self.assertEqual("complete", result["status"])
        overcast = result["phenomena"]["overcast"]
        self.assertEqual("violates_candidate", overcast["status"])
        self.assertEqual(2, overcast["actual_violations"])
        self.assertEqual([0, 1], overcast["violating_samples"])
        for name in PHENOMENA[1:]:
            self.assertEqual("within_candidate", result["phenomena"][name]["status"], name)

    def test_the_boundary_tolerance_covers_float_text_but_not_real_excursions(self):
        for value, expected in ((0.8, "within_candidate"), (0.95, "within_candidate"), (0.9501, "within_candidate"),
                                (0.7995, "within_candidate"), (0.97, "violates_candidate"), (0.7, "violates_candidate")):
            rows = [header(6)] + [sample(i, {"overcast": value}) for i in range(6)] + [end(6)]
            with self.subTest(value=value):
                self.assertEqual(expected, report.evaluate(lines(rows), DISTINCT)["phenomena"]["overcast"]["status"])

    def test_the_forecast_is_reported_separately_and_never_decides_the_status(self):
        rows = [header(6)]
        for i in range(6):
            row = sample(i)
            row["phenomena"]["overcast"]["forecast"] = 0.3
            rows.append(row)
        rows.append(end(6))
        overcast = report.evaluate(lines(rows), DISTINCT)["phenomena"]["overcast"]
        self.assertEqual("within_candidate", overcast["status"])
        self.assertEqual(6, overcast["forecast_outside_limits"])
        self.assertEqual({"min": 0.3, "max": 0.3}, overcast["forecast_range"])

    def test_the_engines_live_limits_are_compared_to_the_candidates_limits(self):
        rows = [header(6)]
        for i in range(6):
            row = sample(i)
            if i >= 3:
                row["phenomena"]["overcast"]["limit_min"] = 0.0
                row["phenomena"]["overcast"]["limit_max"] = 1.0
            rows.append(row)
        rows.append(end(6))
        live = report.evaluate(lines(rows), DISTINCT)["phenomena"]["overcast"]["engine_limits"]
        self.assertEqual({"matching": 3, "total": 6}, live["limits"])
        self.assertEqual([[0.0, 1.0], [0.8, 0.95]], live["distinct_live_limits"])
        self.assertEqual({"matching": 6, "total": 6}, live["change_limits"])
        self.assertEqual({"matching": 6, "total": 6}, live["time_limits"])

    def test_a_phenomenon_with_too_few_valid_samples_is_insufficient(self):
        rows = [header(4)] + [sample(i) for i in range(4)] + [end(4)]
        result = report.evaluate(lines(rows), DISTINCT)
        self.assertEqual("complete", result["status"])
        for name in PHENOMENA:
            self.assertEqual("insufficient_samples", result["phenomena"][name]["status"])
        relaxed = report.evaluate(lines(rows), DISTINCT, min_samples=4)
        self.assertEqual("within_candidate", relaxed["phenomena"]["overcast"]["status"])

    def test_mission_weather_and_frozen_flags_are_reported_per_run(self):
        result = report.evaluate(run(), DISTINCT)
        self.assertEqual({"values": [False], "any_true": False, "all_true": False, "consistent": True},
                         result["mission_weather"])
        self.assertEqual({"values": [False], "any_true": False, "all_true": False, "consistent": True},
                         result["update_frozen"])
        rows = [header(6)] + [sample(i, mission_weather=True, frozen=(i == 2)) for i in range(6)] + [end(6)]
        result = report.evaluate(lines(rows), DISTINCT)
        self.assertEqual({"values": [True], "any_true": True, "all_true": True, "consistent": True},
                         result["mission_weather"])
        self.assertEqual({"values": [False, True], "any_true": True, "all_true": False, "consistent": False},
                         result["update_frozen"])

    def test_numbers_emitted_as_text_including_unusual_float_spellings_are_accepted(self):
        rows = [header(6)] + [sample(i, text=True) for i in range(6)] + [end(6)]
        self.assertEqual("complete", report.evaluate(lines(rows), DISTINCT)["status"])
        for spelling, value in ((".9", 0.9), ("0.9", 0.9), ("9e-1", 0.9), ("+0.9", 0.9), ("0.90000", 0.9)):
            rows = [header(6)]
            for i in range(6):
                row = sample(i, text=True)
                row["phenomena"]["overcast"]["actual"] = spelling
                rows.append(row)
            rows.append(end(6))
            with self.subTest(spelling=spelling):
                result = report.evaluate(lines(rows), DISTINCT)
                self.assertEqual("complete", result["status"])
                self.assertEqual({"min": value, "max": value}, result["phenomena"]["overcast"]["actual_range"])


class PendingTests(unittest.TestCase):
    def assert_pending(self, text, fragment, xml=DISTINCT, **kwargs):
        result = report.evaluate(text, xml, **kwargs)
        self.assertEqual("pending", result["status"], text[:200])
        self.assertTrue(any(fragment in issue for issue in result["issues"]), result["issues"])
        for name in PHENOMENA:
            self.assertEqual("insufficient_samples", result["phenomena"][name]["status"])
        return result

    def rows(self, count=6):
        return [header(count)] + [sample(i) for i in range(count)] + [end(count)]

    def test_a_missing_sample_is_pending(self):
        rows = self.rows()
        del rows[3]
        self.assert_pending(lines(rows), "missing")

    def test_a_duplicate_sample_is_pending(self):
        rows = self.rows()
        rows.insert(3, copy.deepcopy(rows[3]))
        self.assert_pending(lines(rows), "duplicate")

    def test_out_of_order_or_non_contiguous_sequence_numbers_are_pending(self):
        rows = self.rows()
        rows[2], rows[3] = rows[3], rows[2]
        self.assert_pending(lines(rows), "sequence")
        rows = self.rows()
        rows[3]["seq"] = 9
        self.assert_pending(lines(rows), "missing")

    def test_a_malformed_json_line_is_pending(self):
        rows = self.rows()
        rows[3] = '{"type": "sample", "seq": 2, '
        self.assert_pending(lines(rows), "malformed")

    def test_non_finite_numbers_are_pending(self):
        for bad in ("NaN", "nan", "-nan(ind)", "inf", "Infinity", "", "abc", "0.9x", None, True, [1]):
            rows = self.rows()
            rows[2]["phenomena"]["fog"]["actual"] = bad
            with self.subTest(bad=bad):
                self.assert_pending(lines(rows), "malformed")
        text = lines(self.rows()).replace('"seq": 1', '"seq": NaN', 1)
        self.assert_pending(text, "malformed")

    def test_a_missing_or_unknown_phenomenon_or_field_is_pending(self):
        rows = self.rows()
        del rows[2]["phenomena"]["snowfall"]
        self.assert_pending(lines(rows), "malformed")
        rows = self.rows()
        rows[2]["phenomena"]["sandstorm"] = phenomenon("fog", 0.1)
        self.assert_pending(lines(rows), "malformed")
        rows = self.rows()
        del rows[2]["phenomena"]["fog"]["next_change"]
        self.assert_pending(lines(rows), "malformed")
        rows = self.rows()
        del rows[2]["mission_weather"]
        self.assert_pending(lines(rows), "malformed")
        rows = self.rows()
        rows[2]["mission_weather"] = "false"
        self.assert_pending(lines(rows), "malformed")

    def test_a_run_without_a_complete_end_record_is_pending(self):
        rows = self.rows()[:-1]
        self.assert_pending(lines(rows), "end record")
        for status in ("partial", "failed"):
            rows = self.rows()
            rows[-1] = end(6, status)
            self.assert_pending(lines(rows), status)

    def test_write_errors_reported_by_the_probe_make_the_run_pending(self):
        rows = self.rows()
        rows[-1]["write_errors"] = 2
        self.assert_pending(lines(rows), "write errors")

    def test_the_end_record_and_header_must_agree_with_the_sample_count(self):
        rows = self.rows()
        rows[-1] = end(5)
        self.assert_pending(lines(rows), "end record")
        rows = self.rows()
        rows[0]["planned_samples"] = 9
        self.assert_pending(lines(rows), "planned")

    def test_structural_oddities_are_pending(self):
        rows = self.rows()
        self.assert_pending(lines(rows[1:]), "header")
        self.assert_pending(lines(rows + [sample(6)]), "after the end record")
        extra_header = self.rows()
        extra_header.insert(2, header(6))
        self.assert_pending(lines(extra_header), "header")
        wrong_kind = self.rows()
        wrong_kind[0]["kind"] = "taped-light-probe-observations"
        self.assert_pending(lines(wrong_kind), "kind")
        wrong_schema = self.rows()
        wrong_schema[0]["schema"] = 2
        self.assert_pending(lines(wrong_schema), "schema")
        self.assert_pending("", "empty")
        self.assert_pending("\n\n", "empty")
        unknown = self.rows()
        unknown.insert(2, {"type": "note"})
        self.assert_pending(lines(unknown), "unknown record")

    def test_blank_lines_inside_the_stream_are_malformed_not_ignored(self):
        rows = self.rows()
        text = lines(rows[:3]) + "\n" + lines(rows[3:])
        self.assert_pending(text, "blank")

    def test_oversized_input_is_refused(self):
        with self.assertRaises(ValueError):
            report.evaluate("x" * (report.MAX_OBSERVATION_BYTES + 1), DISTINCT)
        with self.assertRaises(ValueError):
            report.evaluate(run(), b"x" * (report.MAX_XML_BYTES + 1))

    def test_a_plan_that_disagrees_with_the_observations_or_cfgweather_is_pending(self):
        plan = {"kind": "weather-probe", "probe": {"samples": 6, "interval_s": 30, "observations_kind":
                                                    "weather-probe-observations",
                                                    "cfgweather": {"staged_sha256": sha(DISTINCT), "variant": "candidate"}}}
        ok = report.evaluate(run(), DISTINCT, plan=plan)
        self.assertEqual("complete", ok["status"])
        self.assertEqual("candidate", ok["cfgweather"]["variant"])
        bad = copy.deepcopy(plan)
        bad["probe"]["cfgweather"]["staged_sha256"] = sha(STOCK)
        self.assert_pending(run(), "cfgweather.xml", plan=bad)
        bad = copy.deepcopy(plan)
        bad["probe"]["samples"] = 7
        self.assert_pending(run(), "plan", plan=bad)
        bad = copy.deepcopy(plan)
        bad["kind"] = "ce-probe"
        self.assert_pending(run(), "plan", plan=bad)


class CfgweatherTests(unittest.TestCase):
    def test_limits_are_read_for_every_phenomenon_and_flags(self):
        parsed = report.parse_cfgweather(DISTINCT)
        self.assertEqual((0.8, 0.95), parsed["phenomena"]["overcast"]["limits"])
        self.assertEqual((-3.14, 3.14), parsed["phenomena"]["windDirection"]["limits"])
        self.assertEqual((0.0, 0.0), parsed["phenomena"]["snowfall"]["limits"])
        self.assertEqual((60.0, 900.0), parsed["phenomena"]["fog"]["time_limits"])
        self.assertEqual((False, False), (parsed["enable"], parsed["reset"]))
        self.assertEqual(sorted(PHENOMENA), sorted(parsed["phenomena"]))

    def test_malformed_hostile_or_incomplete_xml_is_refused(self):
        root = ET.fromstring(STOCK)
        root.remove(root.find("fog"))
        for bad in (b"", b"<weather", b"<other/>", ET.tostring(root),
                    b'<!DOCTYPE weather [<!ENTITY a "b">]>' + STOCK, STOCK.replace(b'max="1"', b'max="nan"', 1),
                    STOCK.replace(b'min="0"', b'min="1.5"', 1)):
            with self.subTest(bad=bad[:40]), self.assertRaises(ValueError):
                report.parse_cfgweather(bad)


class CompareTests(unittest.TestCase):
    def evaluate(self, xml, overcast):
        rows = [header(6)] + [sample(i, {"overcast": overcast}) for i in range(6)] + [end(6)]
        return report.evaluate(lines(rows), xml)

    def test_candidate_values_outside_the_stock_limits_and_inside_the_candidate_show_it_governs(self):
        stock = self.evaluate(STOCK, 0.3)
        candidate = self.evaluate(DISTINCT, 0.9)
        # Make the stock limits narrower than the candidate's observed values.
        narrow = report.evaluate(lines([header(6)] + [sample(i, {"overcast": 0.3}, limits={"overcast": (0.2, 0.6)})
                                                      for i in range(6)] + [end(6)]), cfgweather(overcast=(0.2, 0.6)))
        result = report.compare(narrow, candidate)
        self.assertEqual("candidate_governs", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("not_discriminating", result["phenomena"]["fog"]["evidence"])
        self.assertEqual("complete", result["status"])
        self.assertNotEqual("accepted", result["runtime_acceptance"])
        self.assertEqual("pending", result["runtime_acceptance"])
        self.assertEqual("candidate_governs", report.compare(stock, candidate)["phenomena"]["overcast"]["evidence"])

    def test_candidate_values_outside_the_candidate_limits_show_a_script_or_engine_override(self):
        stock = self.evaluate(STOCK, 0.3)
        candidate = self.evaluate(DISTINCT, 0.3)
        result = report.compare(stock, candidate)
        self.assertEqual("script_or_engine_overrides", result["phenomena"]["overcast"]["evidence"])

    def test_a_candidate_inside_the_stock_range_cannot_discriminate(self):
        stock = self.evaluate(STOCK, 0.9)
        candidate = self.evaluate(DISTINCT, 0.9)
        result = report.compare(stock, candidate)
        self.assertEqual("not_discriminating", result["phenomena"]["overcast"]["evidence"])

    def test_a_stock_run_that_only_partly_leaves_the_candidate_range_is_weak_evidence(self):
        rows = [header(6)] + [sample(i, {"overcast": 0.3 if i < 2 else 0.9}) for i in range(6)] + [end(6)]
        stock = report.evaluate(lines(rows), STOCK)
        result = report.compare(stock, self.evaluate(DISTINCT, 0.9))
        self.assertEqual("weakly_discriminating", result["phenomena"]["overcast"]["evidence"])

    def test_a_comparison_of_two_runs_with_the_same_cfgweather_is_pending(self):
        plan = {"kind": "weather-probe", "probe": {"samples": 6, "interval_s": 30,
                                                    "observations_kind": "weather-probe-observations",
                                                    "cfgweather": {"staged_sha256": sha(DISTINCT), "variant": "candidate"}}}
        one = report.evaluate(run(), DISTINCT, plan=plan)
        two = report.evaluate(run(), DISTINCT, plan=plan)
        result = report.compare(one, two)
        self.assertEqual("pending", result["status"])
        self.assertTrue(any("same cfgweather.xml" in issue for issue in result["issues"]))

    def test_a_pending_run_makes_the_comparison_pending(self):
        stock = self.evaluate(STOCK, 0.3)
        bad = report.evaluate("", DISTINCT)
        for pair in ((stock, bad), (bad, stock)):
            result = report.compare(*pair)
            self.assertEqual("pending", result["status"])
            self.assertEqual("pending", result["phenomena"]["overcast"]["evidence"])

    def test_the_mission_weather_flags_of_both_runs_are_carried_through(self):
        rows = [header(6)] + [sample(i, {"overcast": 0.9}, mission_weather=True) for i in range(6)] + [end(6)]
        candidate = report.evaluate(lines(rows), DISTINCT)
        result = report.compare(self.evaluate(STOCK, 0.3), candidate)
        self.assertEqual([False], result["mission_weather"]["stock"]["values"])
        self.assertEqual([True], result["mission_weather"]["candidate"]["values"])


class RuntimeAndCliTests(unittest.TestCase):
    def make_runtime(self, root, xml=DISTINCT, observations=None, sentinel="status=complete samples=6\n", variant="candidate"):
        mission = root / "mpmissions/dayzOffline.chernarusplus"
        mission.mkdir(parents=True)
        (mission / "cfgweather.xml").write_bytes(xml)
        plan = {"kind": "weather-probe", "probe": {"samples": 6, "interval_s": 30,
                                                    "observations_kind": "weather-probe-observations",
                                                    "cfgweather": {"staged_sha256": sha(xml), "variant": variant}}}
        (root / "weather-probe-plan.json").write_text(json.dumps(plan))
        directory = root / "profiles/HCWeatherProbe"
        directory.mkdir(parents=True)
        (directory / "observations.json").write_text(run() if observations is None else observations)
        if sentinel is not None:
            (directory / "complete.txt").write_text(sentinel)
        return root

    def test_a_staged_and_run_runtime_directory_is_read_through_its_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_runtime(Path(temp))
            result = report.load_run(root)
            self.assertEqual("complete", result["status"])
            self.assertEqual("candidate", result["cfgweather"]["variant"])

    def test_a_missing_sentinel_or_failed_sentinel_leaves_the_run_pending(self):
        for sentinel in (None, "status=partial samples=6\n", ""):
            with self.subTest(sentinel=sentinel), tempfile.TemporaryDirectory() as temp:
                result = report.load_run(self.make_runtime(Path(temp), sentinel=sentinel))
                self.assertEqual("pending", result["status"])
                self.assertTrue(any("sentinel" in issue for issue in result["issues"]))

    def test_symlinked_inputs_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_runtime(Path(temp) / "run")
            target = Path(temp) / "elsewhere.json"
            target.write_text(run())
            output = root / "profiles/HCWeatherProbe/observations.json"
            output.unlink()
            output.symlink_to(target)
            with self.assertRaises(ValueError):
                report.load_run(root)

    def test_the_cli_prints_json_and_uses_distinct_exit_codes(self):
        with tempfile.TemporaryDirectory() as temp:
            good = self.make_runtime(Path(temp) / "good")
            bad = self.make_runtime(Path(temp) / "bad", observations="")
            out = io.StringIO()
            with mock.patch("sys.stdout", out):
                self.assertEqual(0, report.main(["single", "--runtime", str(good)]))
            self.assertEqual("complete", json.loads(out.getvalue())["status"])
            out = io.StringIO()
            with mock.patch("sys.stdout", out):
                self.assertEqual(3, report.main(["single", "--runtime", str(bad)]))
            self.assertEqual("pending", json.loads(out.getvalue())["status"])
            out = io.StringIO()
            with mock.patch("sys.stdout", out), mock.patch("sys.stderr", io.StringIO()):
                self.assertEqual(2, report.main(["single", "--runtime", str(Path(temp) / "absent")]))
            stock = self.make_runtime(Path(temp) / "stock", xml=STOCK, observations=run(overrides={"overcast": 0.3}),
                                      variant="stock")
            out = io.StringIO()
            with mock.patch("sys.stdout", out):
                code = report.main(["compare", "--stock", str(stock), "--candidate", str(good)])
            self.assertEqual(0, code)
            self.assertEqual("complete", json.loads(out.getvalue())["status"])

    def test_the_report_never_runs_processes_or_touches_the_network(self):
        text = (ROOT / "tools/audit/weather_report.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess", "socket", "urllib", "os.system", "Popen"):
            self.assertNotIn(forbidden, text)


class HookContractTests(unittest.TestCase):
    """The keys the report requires must be keys the generated hook can emit."""

    def test_every_required_key_is_a_literal_in_the_generated_hook(self):
        from tools.setup import weather_probe as probe
        hook = probe.render_hook().decode("ascii")
        literals = set(re.findall(r'"(\w+)"', hook))
        required = (set(report.HEADER_KEYS) | set(report.SAMPLE_KEYS) | set(report.PHENOMENON_KEYS)
                    | set(report.END_KEYS) | set(PHENOMENA))
        self.assertEqual([], sorted(required - literals))
        self.assertEqual(report.OBSERVATIONS_KIND, probe.OBSERVATIONS_KIND)
        self.assertEqual(tuple(report.PHENOMENA), tuple(probe.PHENOMENA))

    def test_the_synthetic_fixture_uses_exactly_the_documented_sample_shape(self):
        row = sample(0)
        self.assertEqual(set(report.SAMPLE_KEYS) | {"type", "phenomena"}, set(row))
        self.assertEqual(set(report.PHENOMENON_KEYS), set(row["phenomena"]["fog"]))


if __name__ == "__main__":
    unittest.main()
