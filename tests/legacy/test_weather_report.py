"""Offline tests for the weather precedence report; every observation here is SYNTHETIC.

The report compares native observations to a cfgweather.xml's limits. These tests only prove the
comparison and its pending rules; they say nothing about what DayZ actually does.

Actual TDD 2026-11-17:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_weather_probe tests.legacy.test_weather_report -v
RED: ImportError cannot import name 'weather_report' from 'tools.audit' (module missing).
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tests.legacy import test_atmosphere as atmosphere_fixtures
from tools.audit import weather_report as report

ROOT = Path(__file__).resolve().parents[2]
PHENOMENA = ("overcast", "fog", "rain", "windMagnitude", "windDirection", "snowfall")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cfgweather(enable=None, times=None, **limits):
    """Synthetic cfgweather.xml; limits maps phenomenon -> (min, max) overriding the fixture's limits and
    times maps phenomenon -> (min, max) overriding its timelimits."""
    root = ET.fromstring(atmosphere_fixtures.fixture())
    if enable is not None:
        root.set("enable", enable)
    for name, (low, high) in (times or {}).items():
        node = root.find(name + "/timelimits")
        node.set("min", str(low))
        node.set("max", str(high))
    for name, (low, high) in limits.items():
        node = root.find(name + "/limits")
        node.set("min", str(low))
        node.set("max", str(high))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


STOCK = cfgweather(enable="0")
# Distinct from the script's own picks (0.2-0.7 start overcast) on purpose.
DISTINCT = cfgweather(enable="1", overcast=(0.8, 0.95))
DISABLED = cfgweather(enable="0", overcast=(0.8, 0.95))
NARROW = cfgweather(enable="0", overcast=(0.2, 0.6))


def number(value, text=False):
    return str(value) if text else value


# Live limits the DISTINCT fixture's cfgweather.xml declares (see tests.legacy.test_atmosphere.fixture).
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
    row = {"type": "sample", "seq": seq, "game_ms": 30000 * seq, "weather_time": number(30 * seq, text),
            "mission_weather": mission_weather, "update_frozen": frozen, "year": 2026, "month": 11, "day": 17,
            "hour": 9, "minute": seq, "wind_speed": number(4, text), "wind_max_speed": number(20, text),
            "volfog_enabled": True, "volfog_distance_density": number(0.1, text),
            "volfog_height_density": number(0.2, text), "volfog_height_bias": number(50, text),
            "phenomena": {name: phenomenon(name, values[name], text, (limits or {}).get(name)) for name in PHENOMENA}}
    # Synthetic progression: next_change is the REMAINING seconds (a countdown, as natively observed); a forecast
    # boundary falls every 100 s of weather time and the forecast moves after the first one.
    for name, entry in row["phenomena"].items():
        entry["next_change"] = number(100 * (30 * seq // 100 + 1) - 30 * seq, text)
        if seq >= 4:
            entry["forecast"] = number(round(values[name] + 0.01, 6), text)
    return row


def end(samples=6, status="complete"):
    return {"type": "end", "status": status, "samples": samples, "write_errors": 0, "end_ms": 200000}


def lines(rows):
    return "\n".join(row if isinstance(row, str) else json.dumps(row) for row in rows) + "\n"


SOURCE = {"launch_plan_sha256": "1" * 64, "config_sha256": "2" * 64, "battleye_sha256": "3" * 64}


def plan_for(xml, variant, stock=STOCK, source=None, **probe_changes):
    """A full-provenance synthetic plan; probe_changes override the probe section's keys."""
    plan = {"kind": "weather-probe", "source": dict(SOURCE, **(source or {})),
            "probe": {"samples": 6, "interval_s": 30, "start_delay_s": 30, "observations_kind": "weather-probe-observations",
                      "hook_sha256": "4" * 64,
                      "cfgweather": {"variant": variant, "staged_sha256": sha(xml), "stock_sha256": sha(stock)}}}
    plan["probe"].update(probe_changes)
    return plan


def apply_live(rows, xml):
    """Make every sample's live limit readings equal to what `xml` declares (as an enabled engine would report)."""
    for name, values in report.parse_cfgweather(xml)["phenomena"].items():
        for row in rows[1:-1]:
            entry = row["phenomena"][name]
            entry.update(limit_min=values["limits"][0], limit_max=values["limits"][1],
                         change_min=values["change_limits"][0], change_max=values["change_limits"][1],
                         time_min=values["time_limits"][0], time_max=values["time_limits"][1])


def evaluated(xml, variant, overcast=0.9, stock=STOCK, count=6, limits=None, mutate=None, header_changes=None,
              source=None, plan=True, **probe_changes):
    """report.evaluate of a synthetic run; mutate(rows) may alter the rows before they are serialised."""
    rows = [header(count, **(header_changes or {}))] + [sample(i, {"overcast": overcast}, limits=limits)
                                                         for i in range(count)] + [end(count)]
    if limits is None:
        apply_live(rows, xml)
    if mutate:
        mutate(rows)
    probe_changes.setdefault("samples", count)
    chosen = plan_for(xml, variant, stock, source, **probe_changes) if plan else None
    return report.evaluate(lines(rows), xml, plan=chosen)


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
        self.assertEqual((True, False), (parsed["enable"], parsed["reset"]))
        self.assertEqual(sorted(PHENOMENA), sorted(parsed["phenomena"]))

    def test_malformed_hostile_or_incomplete_xml_is_refused(self):
        root = ET.fromstring(STOCK)
        root.remove(root.find("fog"))
        for bad in (b"", b"<weather", b"<other/>", ET.tostring(root),
                    b'<!DOCTYPE weather [<!ENTITY a "b">]>' + STOCK, STOCK.replace(b'max="1"', b'max="nan"', 1),
                    STOCK.replace(b'min="0"', b'min="1.5"', 1)):
            with self.subTest(bad=bad[:40]), self.assertRaises(ValueError):
                report.parse_cfgweather(bad)


XML_TREATING_OVERCAST_AND_FOG = cfgweather(enable="1", overcast=(0.8, 0.95), fog=(0.7, 0.8))


class CompareTests(unittest.TestCase):
    def test_candidate_values_outside_the_stock_limits_and_inside_the_candidate_show_candidate_live_limits_read_back(self):
        stock = evaluated(STOCK, "stock", 0.3)
        candidate = evaluated(DISTINCT, "candidate", 0.9)
        narrow = evaluated(NARROW, "stock", 0.3, stock=NARROW, limits={"overcast": (0.2, 0.6)})
        narrow_candidate = evaluated(DISTINCT, "candidate", 0.9, stock=NARROW)
        result = report.compare(narrow, narrow_candidate)
        self.assertEqual("candidate_live_limits_read_back", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("not_treated", result["phenomena"]["fog"]["evidence"])
        self.assertEqual(["overcast"], result["treated"])
        self.assertEqual("complete", result["status"], result["issues"])
        self.assertEqual("pending", result["runtime_acceptance"])
        self.assertFalse(result["feature_complete"])
        plain = report.compare(stock, candidate)
        self.assertEqual("candidate_live_limits_read_back", plain["phenomena"]["overcast"]["evidence"])
        self.assertNotIn("candidate_governs", json.dumps(plain))
        self.assertEqual("entirely_outside", plain["phenomena"]["overcast"]["stock_values_vs_candidate_limits"])
        self.assertEqual(list(report.NON_CLAIMS), plain["non_claims"])

    def test_candidate_values_outside_the_candidate_limits_show_limits_exceeded_in_the_candidate_run(self):
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", 0.3))
        self.assertEqual("candidate_values_outside_limits", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("complete", result["status"], result["issues"])

    def test_a_candidate_inside_the_stock_range_cannot_discriminate(self):
        result = report.compare(evaluated(STOCK, "stock", 0.9), evaluated(DISTINCT, "candidate", 0.9))
        self.assertEqual("candidate_live_limits_read_back", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("inside", result["phenomena"]["overcast"]["stock_values_vs_candidate_limits"])

    def test_a_stock_run_that_only_partly_leaves_the_candidate_range_is_weak_evidence(self):
        def partly(rows):
            for i, row in enumerate(rows[1:7]):
                row["phenomena"]["overcast"]["actual"] = 0.3 if i < 2 else 0.9
        result = report.compare(evaluated(STOCK, "stock", mutate=partly), evaluated(DISTINCT, "candidate", 0.9))
        self.assertEqual("candidate_live_limits_read_back", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("partly_outside", result["phenomena"]["overcast"]["stock_values_vs_candidate_limits"])

    def test_a_comparison_of_two_runs_with_the_same_cfgweather_is_pending(self):
        result = report.compare(evaluated(DISTINCT, "candidate"), evaluated(DISTINCT, "candidate"))
        self.assertEqual("pending", result["status"])
        self.assertTrue(any("same cfgweather.xml" in issue for issue in result["issues"]))

    def test_a_pending_run_makes_the_comparison_pending(self):
        stock = evaluated(STOCK, "stock", 0.3)
        bad = report.evaluate("", DISTINCT)
        for pair in ((stock, bad), (bad, stock)):
            result = report.compare(*pair)
            self.assertEqual("pending", result["status"])
            self.assertEqual("pending", result["phenomena"]["overcast"]["evidence"])

    def test_the_mission_weather_flags_of_both_runs_are_carried_through(self):
        def flag(rows):
            for row in rows[1:7]:
                row["mission_weather"] = True
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", mutate=flag))
        self.assertEqual([False], result["mission_weather"]["stock"]["values"])
        self.assertEqual([True], result["mission_weather"]["candidate"]["values"])

    def test_a_comparison_below_the_minimum_sample_count_is_pending(self):
        result = report.compare(evaluated(STOCK, "stock", 0.3, count=4), evaluated(DISTINCT, "candidate", count=4))
        self.assertEqual("pending", result["status"])
        self.assertEqual("pending", result["phenomena"]["overcast"]["evidence"])
        self.assertTrue(result["issues"])

    def test_one_pending_treated_phenomenon_makes_the_whole_comparison_pending(self):
        both = XML_TREATING_OVERCAST_AND_FOG
        def stuck(rows):
            for row in rows[1:7]:
                row["phenomena"]["fog"].update(actual=0.75, forecast=0.75, next_change=1000)
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(both, "candidate", mutate=stuck))
        self.assertEqual(["overcast", "fog"], result["treated"])
        self.assertEqual("pending", result["phenomena"]["fog"]["evidence"])
        self.assertEqual("candidate_live_limits_read_back", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("pending", result["status"])
        self.assertTrue(any("fog" in issue for issue in result["issues"]), result["issues"])


class ProgressionTests(unittest.TestCase):
    """Compliance with the candidate's limits only counts when something was observed changing."""

    def compare(self, stock_overcast=0.3, candidate_overcast=0.9, stock_mutate=None, candidate_mutate=None, xml=DISTINCT):
        stock = evaluated(STOCK, "stock", stock_overcast, mutate=stock_mutate)
        candidate = evaluated(xml, "candidate", candidate_overcast, mutate=candidate_mutate)
        return report.compare(stock, candidate)

    def assert_not_established(self, result):
        self.assertNotEqual("candidate_live_limits_read_back", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("pending", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("pending", result["status"])

    def test_frozen_runs_do_not_establish_anything(self):
        def freeze(rows):
            for row in rows[1:7]:
                row["update_frozen"] = True
        self.assert_not_established(self.compare(stock_mutate=freeze, candidate_mutate=freeze))
        self.assert_not_established(self.compare(candidate_mutate=freeze))
        self.assert_not_established(self.compare(stock_mutate=freeze))

    def test_runs_whose_weather_clock_did_not_advance_do_not_establish_anything(self):
        def stopped(rows):
            for row in rows[1:7]:
                row["weather_time"] = 10
        self.assert_not_established(self.compare(candidate_mutate=stopped))
        self.assert_not_established(self.compare(stock_mutate=stopped))

    def test_a_candidate_with_the_xml_disabled_does_not_establish_anything(self):
        self.assert_not_established(self.compare(xml=DISABLED))

    def test_no_forecast_boundary_in_the_candidate_run_means_nothing_is_established(self):
        def no_boundary(rows):
            for row in rows[1:7]:
                for entry in row["phenomena"].values():
                    entry["next_change"] = 1000
        self.assert_not_established(self.compare(candidate_mutate=no_boundary))

    def test_a_stock_run_without_a_cycle_is_reported_but_does_not_block_the_treated_candidate_result(self):
        def no_boundary(rows):
            for row in rows[1:7]:
                for entry in row["phenomena"].values():
                    entry["next_change"] = 1000
        result = self.compare(stock_mutate=no_boundary)
        self.assertEqual("complete", result["status"], result["issues"])
        self.assertEqual({"stock": False, "candidate": True}, result["phenomena"]["overcast"]["cycle_observed"])

    def test_conflicting_live_limits_without_a_forecast_boundary_do_not_establish_anything(self):
        def conflicting(rows):
            for row in rows[1:7]:
                entry = row["phenomena"]["overcast"]
                entry.update(limit_min=0.0, limit_max=1.0, forecast=0.9, next_change=1000)
        result = self.compare(candidate_overcast=0.9, candidate_mutate=conflicting)
        self.assert_not_established(result)

    def test_a_candidate_that_never_changed_anything_does_not_establish_compliance(self):
        def static(rows):
            for row in rows[1:7]:
                for entry in row["phenomena"].values():
                    entry["forecast"] = entry["actual"]
        result = self.compare(candidate_mutate=static)
        self.assert_not_established(result)
        self.assertTrue(any("overcast" in issue for issue in result["issues"]), result["issues"])

    def test_per_run_progression_is_reported(self):
        single = evaluated(DISTINCT, "candidate")
        self.assertEqual({"time_advanced": True, "unfrozen": True, "xml_enabled": True},
                         {k: single["progression"][k] for k in ("time_advanced", "unfrozen", "xml_enabled")})
        self.assertEqual({"boundary_crossed": True, "cycle_observed": True, "change_observed": True},
                         {k: single["phenomena"]["overcast"][k]
                          for k in ("boundary_crossed", "cycle_observed", "change_observed")})

    def test_the_evidence_vocabulary_never_claims_precedence(self):
        result = self.compare()
        self.assertNotIn("governs", json.dumps(result))
        self.assertNotIn("candidate_governs", report.__doc__)


class LimitReadbackTests(unittest.TestCase):
    """Values that merely fall inside the candidate's limits do not show that the engine applied them."""

    def overcast(self, result):
        return result["phenomena"]["overcast"]

    def test_values_in_range_with_unchanged_live_limits_do_not_show_the_limits_applied(self):
        def conflicting(rows):
            for i, row in enumerate(rows[1:-1]):
                row["phenomena"]["overcast"].update(actual=0.86 + i * 0.01, limit_min=0.0, limit_max=1.0, forecast=0.9)
        candidate = evaluated(DISTINCT, "candidate", 0.9, mutate=conflicting)
        result = report.compare(evaluated(STOCK, "stock", 0.3), candidate)
        entry = self.overcast(result)
        self.assertEqual("inconclusive_readback", entry["evidence"])
        self.assertIs(True, entry["values_in_range"])
        self.assertFalse(entry["live_readback"]["limits"]["candidate_live_matches_candidate_xml"])
        self.assertEqual(0, entry["candidate_forecast_outside_limits"])
        self.assertEqual("complete", result["status"], result["issues"])

    def test_a_forecast_outside_the_candidates_limits_counts_with_values_in_range_and_stale_limits(self):
        def conflicting(rows):
            for i, row in enumerate(rows[1:-1]):
                row["phenomena"]["overcast"].update(actual=0.86 + i * 0.01, limit_min=0.0, limit_max=1.0, forecast=0.3)
        candidate = evaluated(DISTINCT, "candidate", 0.9, mutate=conflicting)
        result = report.compare(evaluated(STOCK, "stock", 0.3), candidate)
        entry = self.overcast(result)
        self.assertEqual("candidate_values_outside_limits", entry["evidence"])
        self.assertIs(True, entry["values_in_range"])
        self.assertEqual(6, entry["candidate_forecast_outside_limits"])
        self.assertEqual("complete", result["status"], result["issues"])

    def test_a_stock_run_that_reads_the_same_live_limits_gives_no_differential(self):
        def same_as_candidate(rows):
            for row in rows[1:-1]:
                row["phenomena"]["overcast"].update(limit_min=0.8, limit_max=0.95)
        result = report.compare(evaluated(STOCK, "stock", 0.3, mutate=same_as_candidate), evaluated(DISTINCT, "candidate"))
        readback = self.overcast(result)["live_readback"]["limits"]
        self.assertEqual("inconclusive_readback", self.overcast(result)["evidence"])
        self.assertTrue(readback["candidate_live_matches_candidate_xml"])
        self.assertFalse(readback["stock_live_differs_from_candidate_xml"])

    def test_the_differential_makes_the_positive_label_and_reports_the_live_readings(self):
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", 0.9))
        entry = self.overcast(result)
        self.assertEqual("candidate_live_limits_read_back", entry["evidence"])
        self.assertEqual(["limits"], entry["treated_attributes"])
        self.assertEqual([[0.8, 0.95]], entry["live_readback"]["limits"]["candidate_live"])
        self.assertEqual([[0.0, 1.0]], entry["live_readback"]["limits"]["stock_live"])

    def test_a_treated_time_limit_must_also_show_in_the_live_readings(self):
        xml = cfgweather(enable="1", times={"fog": (30, 60)})

        def stale(rows):
            for row in rows[1:-1]:
                row["phenomena"]["fog"].update(time_min=61, time_max=901)
        ignored = report.compare(evaluated(STOCK, "stock"), evaluated(xml, "candidate", mutate=stale))
        self.assertEqual(["time_limits"], ignored["phenomena"]["fog"]["treated_attributes"])
        self.assertEqual("inconclusive_readback", ignored["phenomena"]["fog"]["evidence"])
        shown = report.compare(evaluated(STOCK, "stock"), evaluated(xml, "candidate"))
        self.assertTrue(shown["phenomena"]["fog"]["live_readback"]["time_limits"]["candidate_live_matches_candidate_xml"])
        self.assertNotEqual("inconclusive_readback", shown["phenomena"]["fog"]["evidence"])

    def test_a_comparison_whose_candidate_changes_no_limits_has_nothing_to_compare(self):
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(cfgweather(enable="1"), "candidate", 0.3))
        self.assertEqual("pending", result["status"])
        self.assertEqual([], result["treated"])
        self.assertTrue(any("no supported treatment" in issue for issue in result["issues"]), result["issues"])
        self.assertEqual({"not_treated"}, {entry["evidence"] for entry in result["phenomena"].values()})


class TreatedGateTests(unittest.TestCase):
    """Only the phenomena the candidate changes are gated; the others are informational."""

    def test_an_unchanged_zero_snowfall_does_not_block_a_targeted_overcast_result(self):
        def inert(rows):
            for row in rows[1:-1]:
                row["phenomena"]["snowfall"].update(actual=0, forecast=0, next_change=0)
        result = report.compare(evaluated(STOCK, "stock", 0.3, mutate=inert), evaluated(DISTINCT, "candidate", mutate=inert))
        self.assertEqual("complete", result["status"], result["issues"])
        self.assertEqual("not_treated", result["phenomena"]["snowfall"]["evidence"])
        self.assertEqual("candidate_live_limits_read_back", result["phenomena"]["overcast"]["evidence"])

    def test_slow_fog_and_wind_direction_schedules_do_not_block_an_overcast_result_in_a_24_minute_run(self):
        # Invented deadlines reflecting visible native durations; not recorded native observations.
        def run(xml, variant, overcast):
            rows = [header(289, interval_ms=5000, cap_ms=1475000)]
            for i in range(289):
                row = sample(i, {"overcast": overcast})
                row["game_ms"] = 30000 + 5000 * i
                row["weather_time"] = 30 + 5 * i
                for entry in row["phenomena"].values():
                    entry["next_change"] = 100 * ((30 + 5 * i) // 100 + 1) - (30 + 5 * i)
                    entry["forecast"] = entry["actual"] if i < 14 else entry["actual"] + 0.01
                row["phenomena"]["fog"]["next_change"] = 1805 - (30 + 5 * i)
                row["phenomena"]["windDirection"]["next_change"] = 2205 - (30 + 5 * i)
                rows.append(row)
            rows.append(end(289))
            apply_live(rows, xml)
            plan = plan_for(xml, variant, samples=289, interval_s=5, start_delay_s=30)
            return report.evaluate(lines(rows), xml, plan=plan)
        result = report.compare(run(STOCK, "stock", 0.3), run(DISTINCT, "candidate", 0.9))
        self.assertEqual("complete", result["status"], result["issues"])
        self.assertEqual("not_treated", result["phenomena"]["fog"]["evidence"])
        self.assertEqual("not_treated", result["phenomena"]["windDirection"]["evidence"])

    def test_a_treated_phenomenon_still_needs_its_own_candidate_cycle(self):
        def stuck(rows):
            for row in rows[1:-1]:
                row["phenomena"]["overcast"]["next_change"] = 5000
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", mutate=stuck))
        self.assertEqual("pending", result["status"])
        self.assertEqual("pending", result["phenomena"]["overcast"]["evidence"])
        self.assertTrue(any(issue.startswith("overcast:") for issue in result["issues"]), result["issues"])

    def test_a_blocked_comparison_keeps_untreated_phenomena_informational(self):
        result = report.compare(evaluated(STOCK, "stock", 0.3), report.evaluate("", DISTINCT))
        self.assertEqual("pending", result["status"])
        self.assertEqual("pending", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("not_treated", result["phenomena"]["rain"]["evidence"])


class NativeShapedTests(unittest.TestCase):
    """Synthetic observations SHAPED like the first native stock run (weather-probe-001-stock); not that data."""

    COUNT = 241

    def shaped(self, xml, variant, overcast_actual=None):
        rows = [header(self.COUNT, interval_ms=5000, cap_ms=1235000)]
        for i in range(self.COUNT):
            row = sample(i, {"overcast": overcast_actual if overcast_actual is not None else 0.2217}, text=True)
            row["game_ms"] = 80529 + 5000 * i
            row["weather_time"] = "%.6g" % (5.30287 + 5.0 * i)
            entries = row["phenomena"]
            # fog: a countdown of remaining seconds, run out at sample 58, a fresh countdown and forecast at 59
            fog = 294.987 - 5.03 * i if i < 59 else 898.934 - 5.03 * (i - 59)
            entries["fog"].update(next_change="%.6g" % fog, forecast="0" if i < 59 else "0.0081521",
                                  actual="0" if i < 59 else "5.51835e-05")
            # overcast: a remainder of about zero at the first sample, then a fresh countdown and a new forecast
            overcast = 0.000964308 if i == 0 else 1582.11 - 4.89 * (i - 1)
            entries["overcast"].update(next_change="%.6g" % overcast)
            if i >= 1:
                entries["overcast"]["forecast"] = "%.6g" % (overcast_actual - 0.01 if overcast_actual else 0.0753319)
            # windMagnitude: a first jump up from a large countdown (a reschedule, not a crossing)
            entries["windMagnitude"].update(next_change="294.987" if i == 0 else "%.6g" % (3000 - 4.89 * (i - 1)))
            # rain: script managed, 30 then 60 and constant
            entries["rain"].update(next_change="30" if i == 0 else "60")
            rows.append(row)
        rows.append(end(self.COUNT))
        apply_live(rows, xml)
        for row in rows[1:-1]:
            for entry in row["phenomena"].values():
                for key in ("limit_min", "limit_max", "change_min", "change_max", "time_min", "time_max"):
                    entry[key] = str(entry[key])
        plan = plan_for(xml, variant, samples=self.COUNT, interval_s=5, start_delay_s=5)
        return report.evaluate(lines(rows), xml, plan=plan)

    def test_a_countdown_run_with_exponent_lexemes_is_read_and_its_crossings_are_found(self):
        single = self.shaped(STOCK, "stock")
        self.assertEqual("complete", single["status"], single["issues"])
        for name, crossed in (("fog", True), ("overcast", True), ("windMagnitude", False), ("rain", False)):
            with self.subTest(name):
                self.assertEqual(crossed, single["phenomena"][name]["boundary_crossed"])
                self.assertEqual(crossed, single["phenomena"][name]["cycle_observed"])
        self.assertAlmostEqual(0.0, single["phenomena"]["fog"]["actual_range"]["min"])
        self.assertAlmostEqual(5.51835e-05, single["phenomena"]["fog"]["actual_range"]["max"])

    def test_a_pair_of_native_shaped_runs_with_a_countdown_gives_a_descriptive_result(self):
        result = report.compare(self.shaped(STOCK, "stock", 0.3), self.shaped(DISTINCT, "candidate", 0.9))
        self.assertEqual("complete", result["status"], result["issues"])
        entry = result["phenomena"]["overcast"]
        self.assertEqual("candidate_live_limits_read_back", entry["evidence"])
        self.assertEqual({"stock": True, "candidate": True}, entry["cycle_observed"])

    def test_a_native_shaped_run_whose_countdown_never_ends_is_pending_for_the_treated_phenomenon(self):
        # a candidate whose overcast countdown starts large and only counts down over the 20 minutes
        rows = [header(self.COUNT, interval_ms=5000, cap_ms=1235000)]
        for i in range(self.COUNT):
            row = sample(i, {"overcast": 0.9}, text=True)
            row["game_ms"] = 80529 + 5000 * i
            row["weather_time"] = "%.6g" % (5.30287 + 5.0 * i)
            for entry in row["phenomena"].values():
                entry["next_change"] = "%.6g" % (2000 - 4.89 * i)
            rows.append(row)
        rows.append(end(self.COUNT))
        apply_live(rows, DISTINCT)
        plan = plan_for(DISTINCT, "candidate", samples=self.COUNT, interval_s=5, start_delay_s=5)
        stuck = report.evaluate(lines(rows), DISTINCT, plan=plan)
        self.assertFalse(stuck["phenomena"]["overcast"]["boundary_crossed"])
        result = report.compare(self.shaped(STOCK, "stock", 0.3), stuck)
        self.assertEqual("pending", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("pending", result["status"])


class DeadlineProgressionTests(unittest.TestCase):
    """Passing a deadline shows nothing unless the controller then rescheduled or chose a new forecast."""

    def test_interpolation_toward_an_unchanged_forecast_with_an_unchanged_deadline_is_not_a_cycle(self):
        def interpolate(rows):
            for i, row in enumerate(rows[1:-1]):
                row["phenomena"]["overcast"].update(actual=0.81 + i * 0.01, forecast=0.9,
                                                    next_change=max(100 - 30 * i, 0))
        single = evaluated(DISTINCT, "candidate", mutate=interpolate)
        entry = single["phenomena"]["overcast"]
        self.assertTrue(entry["boundary_crossed"])
        self.assertFalse(entry["cycle_observed"])
        result = report.compare(evaluated(STOCK, "stock", 0.3), single)
        self.assertEqual("pending", result["status"])
        self.assertEqual("pending", result["phenomena"]["overcast"]["evidence"])
        self.assertTrue(any("interpolation" in issue for issue in result["issues"]), result["issues"])

    def test_the_decision_table(self):
        spread = (0, 30, 60, 90, 120, 150)
        cases = {
            "countdown not yet at its end": ([(0, 100, .5), (30, 70, .5), (60, 40, .5)], (False, False)),
            "countdown steady and never reaching the end": ([(0, 100, .5), (30, 70, .5), (60, 40, .5), (90, 10, .5)],
                                                            (False, False)),
            "crossed, nothing recomputed": ([(0, 100, .5), (60, 40, .5), (120, 0, .5), (150, 0, .5)], (True, False)),
            "crossed, exactly at a sample": ([(0, 60, .5), (30, 30, .5), (60, 0, .5)], (True, False)),
            "crossed, a fresh countdown": ([(0, 100, .5), (60, 40, .5), (120, 80, .5)], (True, True)),
            "crossed, the fresh countdown appears one sample later": ([(0, 100, .5), (120, 0, .5), (150, 110, .5)],
                                                                      (True, True)),
            "crossed, new forecast": ([(0, 100, .5), (60, 40, .5), (120, 0, .6)], (True, True)),
            "crossed, forecast changes one sample later": ([(0, 100, .5), (120, 0, .5), (150, 0, .6)], (True, True)),
            "crossed, countdown stays at zero": ([(0, 100, .5), (120, 0, .5), (150, 0, .5)], (True, False)),
            "forecast moved before the end only": ([(0, 100, .5), (60, 40, .6), (120, 0, .6), (150, 0, .6)],
                                                   (True, False)),
            "zero countdowns never count": ([(t, 0, 0.5) for t in spread], (False, False)),
            "zero countdowns with a changing forecast": ([(t, 0, 0.5 + t / 1000) for t in spread], (False, False)),
            "negative countdowns": ([(t, -5, 0.5 + t / 1000) for t in spread], (False, False)),
            "a constant countdown (script managed) is never crossed": ([(5 * i, 30, .5) for i in range(8)],
                                                                      (False, False)),
            # the near-the-end window is one sample interval plus 10 percent and 0.05 s (interval 5 s here)
            "a remainder just inside the slack still crosses": ([(0, 5.4, .5), (5, 600, .5)], (True, True)),
            "a remainder just outside the slack is a reschedule": ([(0, 5.7, .5), (5, 600, .5)], (False, False)),
            # the rise tolerance is 0.05 s: reading noise is not a jump up
            "a rise inside the tolerance is no crossing": ([(0, 4.0, .5), (5, 4.03, .5), (10, 4.0, .5)],
                                                          (False, False)),
            "a rise inside the tolerance after a crossing is no cycle": ([(0, 4.0, .5), (5, 0, .5), (10, 0.03, .5)],
                                                                         (True, False)),
        }
        for label, (points, expected) in cases.items():
            with self.subTest(label):
                self.assertEqual(expected, report._deadline_progress(points))

    def test_a_native_shaped_countdown_with_a_slightly_slow_rate_is_not_a_false_cycle(self):
        # The native countdown drifted 0.97-1.03 of the weather clock (observation: weather-probe-001-stock).
        cases = {
            "slow countdown leaves a small positive rest": ([(0, 9.8, .5), (5, 4.95, .5), (10, 0.06, .5), (15, 0, .5)],
                                                            (True, False)),
            "the rest is followed by a jump up": ([(0, 9.8, .5), (5, 4.95, .5), (10, 0.06, .5), (15, 898.9, .5)],
                                                  (True, True)),
            "a jump up straight from a small remainder": ([(0, 10.0, .5), (5, 3.907, .5), (10, 898.934, .6)],
                                                          (True, True)),
            "overcast style: a tiny remainder at the first sample": ([(5.3, 0.000964, .22), (10.3, 1582.11, .075)],
                                                                     (True, True)),
            "windMagnitude style: a first jump up from a large countdown is no crossing": (
                [(5.3, 294.987, 10.0), (10.3, 876.111, 7.277), (15.3, 871.2, 7.277), (20.3, 866.3, 7.277)],
                (False, False)),
            "rain style: 30 then 60, never counting down": ([(5.3, 30, .0), (10.3, 60, .0), (15.3, 60, .0)],
                                                           (False, False)),
        }
        for label, (points, expected) in cases.items():
            with self.subTest(label):
                self.assertEqual(expected, report._deadline_progress(points))

    def test_a_forecast_change_without_any_future_deadline_is_not_a_cycle(self):
        def expired(rows):
            for i, row in enumerate(rows[1:-1]):
                row["phenomena"]["overcast"].update(next_change=0, forecast=0.5 + i * 0.01)
        entry = evaluated(DISTINCT, "candidate", mutate=expired)["phenomena"]["overcast"]
        self.assertEqual((False, False), (entry["boundary_crossed"], entry["cycle_observed"]))


def with_current(xml, name, actual="0.75"):
    """The same cfgweather.xml with one phenomenon's <current actual=...> changed (limits untouched)."""
    root = ET.fromstring(xml)
    root.find(name + "/current").set("actual", actual)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


class MixedReadbackTests(unittest.TestCase):
    """The readback needs EVERY candidate reading to match and NO stock reading to; partial matches are inconclusive."""

    def overcast(self, stock, candidate):
        return report.compare(stock, candidate)["phenomena"]["overcast"]

    def test_one_stale_candidate_reading_among_matching_ones_is_inconclusive(self):
        def one_stale(rows):
            rows[1]["phenomena"]["overcast"].update(limit_min=0.0, limit_max=1.0)
        candidate = evaluated(DISTINCT, "candidate", mutate=one_stale)
        entry = self.overcast(evaluated(STOCK, "stock", 0.3), candidate)
        self.assertEqual("inconclusive_readback", entry["evidence"])
        detail = entry["live_readback"]["limits"]
        self.assertFalse(detail["candidate_live_matches_candidate_xml"])
        self.assertEqual({"matching": 5, "total": 6}, detail["candidate_readings_matching_candidate_xml"])

    def test_one_stock_reading_that_already_equals_the_candidate_is_inconclusive(self):
        def one_match(rows):
            rows[1]["phenomena"]["overcast"].update(limit_min=0.8, limit_max=0.95)
        entry = self.overcast(evaluated(STOCK, "stock", 0.3, mutate=one_match), evaluated(DISTINCT, "candidate"))
        self.assertEqual("inconclusive_readback", entry["evidence"])
        self.assertFalse(entry["live_readback"]["limits"]["stock_live_differs_from_candidate_xml"])

    def test_a_mixed_time_limit_readback_is_inconclusive_as_well(self):
        xml = cfgweather(enable="1", times={"fog": (30, 60)})

        def one_stale(rows):
            rows[3]["phenomena"]["fog"].update(time_min=60, time_max=900)
        entry = report.compare(evaluated(STOCK, "stock"), evaluated(xml, "candidate", mutate=one_stale))["phenomena"]["fog"]
        self.assertEqual("inconclusive_readback", entry["evidence"])

    def test_a_readback_that_is_inconclusive_claims_nothing_about_the_native_engine(self):
        def stale(rows):
            for row in rows[1:-1]:
                row["phenomena"]["overcast"].update(limit_min=0.0, limit_max=1.0)
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", mutate=stale))
        entry = result["phenomena"]["overcast"]
        self.assertEqual("complete", result["status"], result["issues"])
        self.assertIn("no native conclusion", entry["reason"])
        self.assertIn("delayed", entry["reason"])
        self.assertEqual("pending", result["runtime_acceptance"])


class CanceledDeadlineTests(unittest.TestCase):
    """A deadline that was replaced before it was reached is not crossed; only the active deadline counts."""

    def test_a_countdown_replaced_by_a_larger_one_before_it_ended_does_not_establish_a_cycle(self):
        def canceled(rows):
            for i, row in enumerate(rows[1:-1]):
                row["phenomena"]["overcast"].update(actual=0.81 + 0.01 * i, forecast=0.9,
                                                    next_change=100 if i == 0 else 1000 - 30 * (i - 1))
        candidate = evaluated(DISTINCT, "candidate", mutate=canceled)
        entry = candidate["phenomena"]["overcast"]
        self.assertEqual((False, False), (entry["boundary_crossed"], entry["cycle_observed"]))
        result = report.compare(evaluated(STOCK, "stock", 0.3), candidate)
        self.assertEqual("pending", result["status"])
        self.assertEqual("pending", result["phenomena"]["overcast"]["evidence"])
        self.assertFalse(result["phenomena"]["overcast"]["cycle_observed"]["candidate"])

    def test_the_decision_table_with_canceled_and_replaced_countdowns(self):
        cases = {
            "a jump up from a countdown that was not near its end is a reschedule, not a crossing": (
                [(0, 100, .5), (30, 1000, .5), (60, 970, .5), (120, 910, .5)], (False, False)),
            "the same jump with a forecast change is still no crossing": (
                [(0, 100, .5), (30, 1000, .6), (60, 970, .6)], (False, False)),
            "a replaced countdown that later runs out without a cycle": (
                [(0, 100, .5), (30, 200, .5), (150, 80, .5), (180, 50, .5), (210, 20, .5), (240, 0, .5), (270, 0, .5)],
                (True, False)),
            "a replaced countdown that later runs out and is rescheduled": (
                [(0, 100, .5), (30, 200, .5), (210, 20, .5), (240, 300, .5)], (True, True)),
            "a countdown moved earlier then run out without a cycle": (
                [(0, 500, .5), (30, 60, .5), (60, 30, .5), (90, 0, .5), (120, 0, .5)], (True, False)),
            "a canceled countdown would have ended, the forecast changes much later": (
                [(0, 100, .5), (30, 1000, .5), (150, 880, .6)], (False, False)),
        }
        for label, (points, expected) in cases.items():
            with self.subTest(label):
                self.assertEqual(expected, report._deadline_progress(points))


def series(name, points):
    """mutate(rows): set (actual, forecast, next_change) for one phenomenon from `points`, one tuple per sample."""
    def mutate(rows):
        for row, (actual, forecast, left) in zip(rows[1:-1], points):
            row["phenomena"][name].update(actual=actual, forecast=forecast, next_change=left)
    return mutate


def combine(*mutations):
    def mutate(rows):
        for one in mutations:
            one(rows)
    return mutate


class InitialTransitionTests(unittest.TestCase):
    """Samples before the first scheduled change (or before the actual reaches the first forecast) form a window."""

    # overcast, DISTINCT limits .8..95, 30 s samples; the countdown runs 100,70,40,10 then a fresh one
    COUNTDOWN = [100, 70, 40, 10] * 3

    def overcast(self, actual, forecast, countdown=None):
        points = list(zip(actual, forecast, countdown or self.COUNTDOWN))
        return evaluated(DISTINCT, "candidate", count=len(points), mutate=series("overcast", points))["phenomena"]["overcast"]

    def test_out_of_limit_actuals_before_the_actual_reaches_the_first_forecast_are_reported_not_violations(self):
        entry = self.overcast([.3, .45, .6, .75] + [.9] * 8, [.9] * 8 + [.85] * 4)
        self.assertEqual("within_candidate", entry["status"])
        self.assertEqual(0, entry["actual_violations"])
        self.assertEqual([], entry["violating_samples"])
        window = entry["initial_transition"]
        self.assertEqual(4, window["samples"])
        self.assertEqual("actual_reached_initial_forecast", window["ended_by"])
        self.assertEqual(4, window["actual_outside_limits"])
        self.assertEqual([0, 1, 2, 3], window["outside_samples"])

    def test_an_out_of_limit_actual_after_the_transition_still_violates(self):
        entry = self.overcast([.3, .45, .6, .75] + [.9] * 5 + [.5] + [.9] * 2, [.9] * 12)
        self.assertEqual("violates_candidate", entry["status"])
        self.assertEqual([9], entry["violating_samples"])
        self.assertEqual(4, entry["initial_transition"]["samples"])

    def test_the_window_also_ends_at_the_first_scheduled_change(self):
        entry = self.overcast([.3, .35, .4, .45, .5, .55] + [.9] * 6, [.9] * 4 + [.85] * 8)
        window = entry["initial_transition"]
        self.assertEqual((4, "first_scheduled_change"), (window["samples"], window["ended_by"]))
        self.assertEqual("violates_candidate", entry["status"])
        self.assertEqual([4, 5], entry["violating_samples"])

    def test_each_kind_of_scheduled_change_ends_the_window_on_its_own(self):
        never_reaching = [.3, .35, .4, .45, .5, .55, .6, .6]
        cases = {
            "a forecast change": ([.9] * 4 + [.85] * 4, [900 - 30 * i for i in range(8)]),
            "a countdown that ran out": ([.9] * 8, [100, 70, 40, 10, 0, 0, 0, 0]),
            "a countdown that jumped up": ([.9] * 8, [100, 70, 40, 10, 100, 70, 40, 10]),
        }
        for label, (forecast, countdown) in cases.items():
            with self.subTest(label):
                window = self.overcast(never_reaching, forecast, countdown)["initial_transition"]
                self.assertEqual((4, "first_scheduled_change"), (window["samples"], window["ended_by"]))

    def test_a_first_sample_that_already_holds_the_forecast_has_no_window(self):
        entry = self.overcast([.9] * 12, [.9] * 12)
        self.assertEqual(0, entry["initial_transition"]["samples"])
        self.assertEqual("actual_reached_initial_forecast", entry["initial_transition"]["ended_by"])

    def test_a_transition_that_never_ends_is_not_excused(self):
        points = [(.3, .9, 900 - 30 * i) for i in range(12)]
        entry = evaluated(DISTINCT, "candidate", count=12, mutate=series("overcast", points))["phenomena"]["overcast"]
        self.assertIsNone(entry["initial_transition"]["ended_by"])
        self.assertEqual(0, entry["initial_transition"]["samples"])
        self.assertEqual("violates_candidate", entry["status"])
        self.assertEqual(12, entry["actual_violations"])

    def test_a_forecast_outside_the_limits_counts_even_inside_the_window(self):
        points = [(a, .99, left) for a, left in zip([.3, .45, .6, .75] + [.99] * 8, self.COUNTDOWN)]
        candidate = evaluated(DISTINCT, "candidate", count=12, mutate=series("overcast", points))
        self.assertEqual(12, candidate["phenomena"]["overcast"]["forecast_outside_limits"])
        result = report.compare(evaluated(STOCK, "stock", 0.3, count=12), candidate)
        self.assertEqual("candidate_values_outside_limits", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual(12, result["phenomena"]["overcast"]["candidate_forecast_outside_limits"])

    def test_the_pair_reports_the_window_for_the_candidate(self):
        points = list(zip([.3, .45, .6, .75] + [.9] * 8, [.9] * 8 + [.85] * 4, self.COUNTDOWN))
        candidate = evaluated(DISTINCT, "candidate", count=12, mutate=series("overcast", points))
        entry = report.compare(evaluated(STOCK, "stock", 0.3, count=12), candidate)["phenomena"]["overcast"]
        self.assertEqual(4, entry["initial_transition"]["samples"])
        self.assertEqual("within_candidate", entry["candidate_status"])
        self.assertEqual("candidate_live_limits_read_back", entry["evidence"])


def fog_current_run(xml, variant, fog_series=None, count=14):
    """A 14 sample, 30 s run whose fog is the XML's <current actual=.75 time=120 duration=240>: forecast .75 from the
    first sample, a countdown of 360 - weather_time, the actual reaching .75 at 120 s; the countdown then runs out
    and a fresh one follows."""
    countdown = [360 - 30 * i for i in range(12)] + [0, 40]
    actual = [.3, .4, .55, .7] + [.75] * 10
    points = fog_series or list(zip(actual, [.75] * count, countdown))
    return evaluated(xml, variant, count=count, mutate=series("fog", points))


FOG_CURRENT = with_current(cfgweather(enable="1"), "fog")
FOG_CURRENT_LIMITS = with_current(cfgweather(enable="1", fog=(0.7, 0.8), times={"fog": (30, 60)}), "fog")


class PostEntryExcursionTests(unittest.TestCase):
    """The initial transition excuses only the run from the reset value up to the first actual inside the limits; an
    excursion after that first entry is a violation, whatever else was read back. Synthetic traces, not DayZ output."""

    POSITIVE = ("candidate_live_limits_read_back", "candidate_current_read_back")

    def overcast_pair(self, actual):
        points = list(zip(actual, [.9] * 8, [100, 70, 40, 10, 100, 70, 40, 10]))
        candidate = evaluated(DISTINCT, "candidate", count=8, mutate=series("overcast", points))
        return candidate, report.compare(evaluated(STOCK, "stock", 0.3, count=8), candidate)

    def fog_pair(self, actual):
        countdown = [360 - 30 * i for i in range(12)] + [0, 40]
        points = list(zip(actual, [.75] * 14, countdown))
        candidate = fog_current_run(FOG_CURRENT_LIMITS, "candidate", fog_series=points)
        return candidate, report.compare(evaluated(STOCK, "stock", count=14), candidate)

    def assert_no_positive_labels(self, entry):
        self.assertNotIn(entry["evidence"], self.POSITIVE)
        self.assertEqual("candidate_values_outside_limits", entry["evidence"])
        for label in (entry["attribute_evidence"] or {}).values():
            self.assertNotIn(label, self.POSITIVE)

    def test_an_actual_that_starts_inside_the_limits_and_leaves_them_violates(self):
        candidate, result = self.overcast_pair([.81, .4, .6, .75, .9, .9, .9, .9])
        entry = candidate["phenomena"]["overcast"]
        self.assertEqual("violates_candidate", entry["status"])
        self.assertEqual([1, 2, 3], entry["violating_samples"])
        self.assertEqual(0, entry["initial_transition"]["samples"])
        self.assertEqual(0, entry["initial_transition"]["actual_outside_limits"])
        pair = result["phenomena"]["overcast"]
        self.assert_no_positive_labels(pair)
        self.assertEqual("violates_candidate", pair["candidate_status"])
        self.assertIs(False, pair["values_in_range"])

    def test_an_excursion_after_the_first_entry_violates_even_with_the_current_read_back(self):
        candidate, result = self.fog_pair([.3, .4, .72, .1, .75] + [.75] * 9)
        entry = candidate["phenomena"]["fog"]
        self.assertEqual("violates_candidate", entry["status"])
        self.assertEqual([3], entry["violating_samples"])
        self.assertEqual((2, "actual_entered_limits"),
                         (entry["initial_transition"]["samples"], entry["initial_transition"]["ended_by"]))
        self.assertEqual([0, 1], entry["initial_transition"]["outside_samples"])
        pair = result["phenomena"]["fog"]
        self.assert_no_positive_labels(pair)
        self.assertEqual("complete", result["status"], result["issues"])

    def test_the_convergence_from_the_reset_value_is_excused_only_before_the_first_entry(self):
        candidate, result = self.fog_pair([.3, .4, .55, .7] + [.75] * 10)
        entry = candidate["phenomena"]["fog"]
        self.assertEqual("within_candidate", entry["status"])
        self.assertEqual((3, "actual_entered_limits"),
                         (entry["initial_transition"]["samples"], entry["initial_transition"]["ended_by"]))
        self.assertEqual("candidate_live_limits_read_back", result["phenomena"]["fog"]["evidence"])

    def test_the_decision_table_of_the_window_end(self):
        limits = (.8, .95)
        cases = {
            "the first actual is inside the limits": (
                [(0, .81, .9, 100), (30, .4, .9, 70), (60, .9, .9, 40)], (0, "actual_entered_limits")),
            "the entry comes before the forecast is reached": (
                [(0, .3, .9, 100), (30, .85, .9, 70), (60, .5, .9, 40), (90, .9, .9, 10)], (1, "actual_entered_limits")),
            "the forecast is reached while the limits are not the target": (
                [(0, .3, .5, 100), (30, .4, .5, 70), (60, .5, .5, 40)], (2, "actual_reached_initial_forecast")),
            "a forecast change comes before any entry": (
                [(0, .3, .9, 100), (30, .35, .9, 70), (60, .4, .85, 40), (90, .85, .85, 10)], (2, "first_scheduled_change")),
            "no entry, no forecast and no scheduled change is no transition": (
                [(0, .3, .9, 100), (30, .35, .9, 70), (60, .4, .9, 40)], (0, None)),
        }
        for label, (points, expected) in cases.items():
            with self.subTest(label):
                self.assertEqual(expected, report._initial_transition(points, limits))


class VerdictBeforeGateTests(unittest.TestCase):
    """Known violations are reported once there are enough usable samples, whatever the countdown did."""

    COUNTDOWN = [900 - 30 * i for i in range(6)]

    def pair(self, actual, forecast):
        points = list(zip(actual, forecast, self.COUNTDOWN))
        candidate = evaluated(DISTINCT, "candidate", mutate=series("overcast", points))
        return report.compare(evaluated(STOCK, "stock", 0.3), candidate)

    def test_forecast_outside_is_reported_even_without_a_cycle(self):
        result = self.pair([.9] * 6, [.99] * 6)
        entry = result["phenomena"]["overcast"]
        self.assertEqual((False, False), (entry["boundary_crossed"]["candidate"], entry["cycle_observed"]["candidate"]))
        self.assertEqual(6, entry["candidate_forecast_outside_limits"])
        self.assertEqual("candidate_values_outside_limits", entry["evidence"])
        self.assertEqual("complete", result["status"], result["issues"])

    def test_an_observed_actual_violation_is_reported_even_without_a_cycle(self):
        result = self.pair([.9, .9, .9, .5, .9, .9], [.9] * 6)
        entry = result["phenomena"]["overcast"]
        self.assertFalse(entry["cycle_observed"]["candidate"])
        self.assertEqual("violates_candidate", entry["candidate_status"])
        self.assertEqual("candidate_values_outside_limits", entry["evidence"])
        self.assertEqual("complete", result["status"], result["issues"])

    def test_too_few_samples_stay_pending_whatever_they_show(self):
        candidate = evaluated(DISTINCT, "candidate", count=3,
                              mutate=series("overcast", [(.9, .99, 900), (.9, .99, 870), (.9, .99, 840)]))
        result = report.compare(evaluated(STOCK, "stock", 0.3, count=3), candidate)
        self.assertEqual("pending", result["phenomena"]["overcast"]["evidence"])


class RawValuesInRangeTests(unittest.TestCase):
    """values_in_range describes every raw actual; the excused status is reported under its own scoped field."""

    def test_values_in_range_describes_the_raw_samples(self):
        candidate = fog_current_run(FOG_CURRENT_LIMITS, "candidate")
        result = report.compare(evaluated(STOCK, "stock", count=14), candidate)
        entry = result["phenomena"]["fog"]
        self.assertEqual("within_candidate", entry["candidate_status"])
        self.assertIs(False, entry["values_in_range"])
        self.assertIs(True, entry["values_in_range_after_initial_transition"])
        self.assertEqual(.3, entry["candidate_actual_range"]["min"])
        self.assertEqual(3, entry["raw_actual_outside_limits"])

    def test_values_in_range_after_the_transition_is_false_for_a_later_violation(self):
        countdown = [360 - 30 * i for i in range(12)] + [0, 40]
        points = list(zip([.3, .4, .72, .1, .75] + [.75] * 9, [.75] * 14, countdown))
        entry = report.compare(evaluated(STOCK, "stock", count=14),
                               fog_current_run(FOG_CURRENT_LIMITS, "candidate", fog_series=points))["phenomena"]["fog"]
        self.assertEqual((False, False), (entry["values_in_range"], entry["values_in_range_after_initial_transition"]))

    def test_values_in_range_is_true_only_when_no_raw_actual_is_outside(self):
        candidate = evaluated(DISTINCT, "candidate", 0.9)
        entry = report.compare(evaluated(STOCK, "stock", 0.3), candidate)["phenomena"]["overcast"]
        self.assertEqual((True, True), (entry["values_in_range"], entry["values_in_range_after_initial_transition"]))

    def short_entry(self, actual):
        points = list(zip(actual, [.9] * 3, [900, 870, 840]))
        candidate = evaluated(DISTINCT, "candidate", count=3, mutate=series("overcast", points))
        result = report.compare(evaluated(STOCK, "stock", 0.3, count=3), candidate)
        self.assertEqual("insufficient_samples", candidate["phenomena"]["overcast"]["status"])
        return result["phenomena"]["overcast"]

    def test_short_clean_run_does_not_claim_post_transition_actuals_outside(self):
        entry = self.short_entry([.9, .9, .9])
        self.assertEqual("pending", entry["evidence"])
        self.assertEqual("insufficient_samples", entry["candidate_status"])
        self.assertIs(True, entry["values_in_range_after_initial_transition"])
        self.assertIs(True, entry["values_in_range"])

    def test_short_violating_run_reports_the_violation_and_stays_pending(self):
        entry = self.short_entry([.9, .5, .9])
        self.assertEqual("pending", entry["evidence"])
        self.assertEqual("insufficient_samples", entry["candidate_status"])
        self.assertIs(False, entry["values_in_range_after_initial_transition"])
        self.assertIs(False, entry["values_in_range"])

    def test_a_run_without_samples_has_no_range_booleans(self):
        entry = report.compare(evaluated(STOCK, "stock", 0.3, count=0), evaluated(DISTINCT, "candidate", count=0)
                               )["phenomena"]["overcast"]
        self.assertIsNone(entry["values_in_range"])
        self.assertIsNone(entry["values_in_range_after_initial_transition"])

    def test_emitted_transition_prose_matches_first_entry_rule(self):
        notes = [note for note in report.NON_CLAIMS if "initial transition" in note]
        self.assertEqual(1, len(notes), notes)
        note = notes[0]
        for text in ("earliest", "forecast", "enters", "limits", "scheduled change", "is assessed", "never ends",
                     "not excused"):
            self.assertIn(text, note)
        for result in (evaluated(DISTINCT, "candidate"), report.compare(evaluated(STOCK, "stock", 0.3),
                                                                        evaluated(DISTINCT, "candidate", 0.9))):
            self.assertIn(note, result["non_claims"])

    def test_the_notes_scope_a_clean_status_to_after_the_initial_transition(self):
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", 0.9))
        self.assertTrue(any("after the initial transition" in note and "not whole-run compliance" in note
                            for note in result["notes"]), result["notes"])
        self.assertIn("after the initial transition", report.__doc__.split("within_candidate", 1)[1][:200])


class CurrentReadbackTests(unittest.TestCase):
    """The candidate's <current> is read back when the first forecast, the first countdown and the actual match it."""

    def fog(self, candidate, stock=None, count=14):
        stock = stock or evaluated(STOCK, "stock", count=count)
        return report.compare(stock, candidate)["phenomena"]["fog"]

    def test_a_matching_current_is_read_back_and_coverage_is_complete(self):
        result = report.compare(evaluated(STOCK, "stock", count=14), fog_current_run(FOG_CURRENT, "candidate"))
        entry = result["phenomena"]["fog"]
        self.assertEqual("candidate_current_read_back", entry["evidence"])
        self.assertEqual({"current": "candidate_current_read_back"}, entry["attribute_evidence"])
        self.assertEqual(["current"], entry["treated_attributes"])
        self.assertEqual([], entry["unsupported_treatments"])
        self.assertEqual("complete", result["coverage"])
        self.assertEqual("complete", result["status"], result["issues"])
        self.assertEqual({}, result["unsupported_treatments"])
        detail = entry["current_readback"]["candidate"]
        self.assertTrue(detail["matches"])
        self.assertEqual({"actual": 0.75, "time": 120.0, "duration": 240.0}, detail["expected"])
        self.assertEqual(0.0, detail["observed"]["first_weather_time"])
        self.assertEqual(120.0, detail["observed"]["actual_reached_weather_time"])
        self.assertEqual(360.0, detail["observed"]["expected_first_countdown"])

    def test_a_current_target_alone_does_not_need_a_forecast_cycle(self):
        points = [(.3, .75, 360), (.4, .75, 330), (.55, .75, 300), (.7, .75, 270), (.75, .75, 240), (.75, .75, 210)]
        entry = self.fog(evaluated(FOG_CURRENT, "candidate", count=6, mutate=series("fog", points)), count=6)
        self.assertEqual("candidate_current_read_back", entry["evidence"])
        self.assertFalse(entry["boundary_crossed"]["candidate"])

    def test_a_current_whose_first_countdown_is_far_off_is_inconclusive_even_without_a_cycle(self):
        points = [(.3, .75, 900 - 30 * i) for i in range(4)] + [(.75, .75, 780), (.75, .75, 750)]
        entry = self.fog(evaluated(FOG_CURRENT, "candidate", count=6, mutate=series("fog", points)), count=6)
        self.assertEqual("current_inconclusive", entry["evidence"])

    def test_a_first_forecast_that_is_not_the_current_target_is_inconclusive(self):
        points = list(zip([.3, .4, .55, .7] + [.75] * 10, [.6] * 14, [360 - 30 * i for i in range(12)] + [0, 40]))
        entry = self.fog(fog_current_run(FOG_CURRENT, "candidate", points))
        self.assertEqual("current_inconclusive", entry["evidence"])
        self.assertFalse(entry["current_readback"]["candidate"]["checks"]["first_forecast_equals_current_actual"])
        self.assertIn("first forecast", entry["reason"])

    def test_a_first_countdown_that_is_not_time_plus_duration_minus_weather_time_is_inconclusive(self):
        for first in (200, 700, 358.5, 361.5):
            countdown = [first - 30 * i for i in range(12)] + [0, 40]
            points = list(zip([.3, .4, .55, .7] + [.75] * 10, [.75] * 14, countdown))
            with self.subTest(first=first):
                entry = self.fog(fog_current_run(FOG_CURRENT, "candidate", points))
                self.assertEqual("current_inconclusive", entry["evidence"])
                self.assertFalse(entry["current_readback"]["candidate"]["checks"][
                    "first_countdown_is_time_plus_duration_minus_weather_time"])

    def test_a_first_countdown_within_the_provisional_tolerance_is_read_back(self):
        for first in (359.2, 360.9):
            countdown = [first - 30 * i for i in range(12)] + [0, 40]
            points = list(zip([.3, .4, .55, .7] + [.75] * 10, [.75] * 14, countdown))
            with self.subTest(first=first):
                self.assertEqual("candidate_current_read_back",
                                 self.fog(fog_current_run(FOG_CURRENT, "candidate", points))["evidence"])

    def test_an_actual_that_never_reaches_the_current_target_is_inconclusive(self):
        points = list(zip([.3] * 14, [.75] * 14, [360 - 30 * i for i in range(12)] + [0, 40]))
        entry = self.fog(fog_current_run(FOG_CURRENT, "candidate", points))
        self.assertEqual("current_inconclusive", entry["evidence"])
        self.assertIsNone(entry["current_readback"]["candidate"]["observed"]["actual_reached_weather_time"])

    def test_an_actual_that_reaches_the_target_only_after_time_plus_slack_is_inconclusive(self):
        for reach, expected in ((4, "candidate_current_read_back"), (5, "current_inconclusive")):
            actual = [.3, .4, .5, .6, .7][:reach] + [.75] * (14 - reach)
            points = list(zip(actual, [.75] * 14, [360 - 30 * i for i in range(12)] + [0, 40]))
            with self.subTest(reach_sample=reach, weather_time=30 * reach):
                self.assertEqual(expected, self.fog(fog_current_run(FOG_CURRENT, "candidate", points))["evidence"])

    def test_a_stock_run_that_already_started_at_the_candidates_target_gives_no_differential(self):
        stock = evaluated(STOCK, "stock", count=14, mutate=series("fog", [(.75, .75, 360 - 30 * i) for i in range(14)]))
        entry = self.fog(fog_current_run(FOG_CURRENT, "candidate"), stock=stock)
        self.assertEqual("current_inconclusive", entry["evidence"])
        self.assertIn("stock", entry["reason"])

    def test_an_inconclusive_current_claims_nothing_and_leaves_the_comparison_complete(self):
        points = list(zip([.3] * 14, [.6] * 14, [100] * 14))
        result = report.compare(evaluated(STOCK, "stock", count=14),
                                fog_current_run(FOG_CURRENT, "candidate", points))
        entry = result["phenomena"]["fog"]
        self.assertEqual("current_inconclusive", entry["evidence"])
        self.assertEqual("complete", result["status"], result["issues"])
        self.assertIn("no native conclusion", entry["reason"])
        self.assertEqual("pending", result["runtime_acceptance"])

    def test_a_current_that_does_not_differ_from_the_stock_is_not_a_treatment(self):
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", 0.9))
        self.assertEqual({}, result["unsupported_treatments"])
        self.assertEqual("complete", result["coverage"])
        self.assertNotIn("current", result["phenomena"]["overcast"]["treated_attributes"])
        self.assertEqual("not_treated", result["phenomena"]["fog"]["evidence"])
        self.assertIsNone(result["phenomena"]["fog"]["attribute_evidence"])

    def test_limits_time_limits_and_current_each_get_their_own_label(self):
        result = report.compare(evaluated(STOCK, "stock", count=14), fog_current_run(FOG_CURRENT_LIMITS, "candidate"))
        entry = result["phenomena"]["fog"]
        self.assertEqual(["limits", "time_limits", "current"], entry["treated_attributes"])
        self.assertEqual({"limits": "candidate_live_limits_read_back", "time_limits": "candidate_live_limits_read_back",
                          "current": "candidate_current_read_back"}, entry["attribute_evidence"])
        self.assertEqual("candidate_live_limits_read_back", entry["evidence"])
        self.assertEqual("complete", result["status"], result["issues"])
        self.assertEqual("complete", result["coverage"])
        self.assertEqual((3, "actual_entered_limits"),
                         (entry["initial_transition"]["samples"], entry["initial_transition"]["ended_by"]))
        self.assertEqual("within_candidate", entry["candidate_status"])

    def test_a_positive_limits_label_never_hides_an_inconclusive_current(self):
        stock = evaluated(STOCK, "stock", count=14, mutate=series("fog", [(.75, .75, 360 - 30 * i) for i in range(14)]))
        result = report.compare(stock, fog_current_run(FOG_CURRENT_LIMITS, "candidate"))
        entry = result["phenomena"]["fog"]
        self.assertEqual("current_inconclusive", entry["evidence"])
        self.assertEqual("candidate_live_limits_read_back", entry["attribute_evidence"]["limits"])
        self.assertEqual("current_inconclusive", entry["attribute_evidence"]["current"])

    def test_a_positive_current_never_hides_an_inconclusive_limit_readback(self):
        def stale(rows):
            for row in rows[1:-1]:
                row["phenomena"]["fog"].update(limit_min=0.0, limit_max=1.0)
        rows_mutation = combine(series("fog", list(zip([.3, .4, .55, .7] + [.75] * 10, [.75] * 14,
                                                       [360 - 30 * i for i in range(12)] + [0, 40]))), stale)
        candidate = evaluated(FOG_CURRENT_LIMITS, "candidate", count=14, mutate=rows_mutation)
        entry = self.fog(candidate)
        self.assertEqual("inconclusive_readback", entry["evidence"])
        self.assertEqual("inconclusive_readback", entry["attribute_evidence"]["limits"])
        self.assertEqual("candidate_current_read_back", entry["attribute_evidence"]["current"])

    def test_an_unsupported_current_never_lets_a_supported_limits_label_stand_for_the_phenomenon(self):
        root = ET.fromstring(FOG_CURRENT_LIMITS)
        del root.find("fog/current").attrib["duration"]
        xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        result = report.compare(evaluated(STOCK, "stock", count=14), fog_current_run(xml, "candidate"))
        entry = result["phenomena"]["fog"]
        self.assertEqual("treated_unsupported", entry["evidence"])
        self.assertEqual("candidate_live_limits_read_back", entry["supported_attribute_evidence"])
        self.assertEqual(["limits", "time_limits"], entry["treated_attributes"])
        self.assertEqual("pending", result["status"])

    def test_a_current_with_missing_keys_stays_unsupported_with_coverage_pending(self):
        root = ET.fromstring(FOG_CURRENT)
        del root.find("fog/current").attrib["duration"]
        xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        result = report.compare(evaluated(STOCK, "stock", count=14), fog_current_run(xml, "candidate"))
        entry = result["phenomena"]["fog"]
        self.assertEqual("treated_unsupported", entry["evidence"])
        self.assertEqual(["current"], entry["unsupported_treatments"])
        self.assertEqual("pending", result["coverage"])
        self.assertEqual("pending", result["status"])
        self.assertTrue(any("fog" in issue and "current" in issue for issue in result["issues"]), result["issues"])

    def test_the_provisional_tolerances_are_explicit_constants(self):
        self.assertEqual(1.0, report.CURRENT_COUNTDOWN_TOLERANCE_S)
        self.assertEqual(10.0, report.CURRENT_CONVERGENCE_SLACK_S)


class CandidateShapedFixtureTests(unittest.TestCase):
    """Synthetic observations SHAPED like the native candidate run (weather-probe-001-candidate); not that data:
    a pre-existing actual, the forecast equal to <current> at the first sample, the actual reaching it at 120 s, the
    first change at 360 s, later countdowns within the 30..60 s time limits."""

    COUNT = 241
    FIRST, STEP = 5.30287, 5.0
    WINDOW = {"overcast": (23, "actual_reached_initial_forecast"), "fog": (22, "actual_entered_limits")}

    def rows(self, xml, variant, shapes):
        rows = [header(self.COUNT, interval_ms=5000, cap_ms=1235000)]
        for i in range(self.COUNT):
            row = sample(i, text=True)
            row["game_ms"] = 220480 + 5000 * i
            row["weather_time"] = "%.6g" % (self.FIRST + self.STEP * i)
            rows.append(row)
        rows.append(end(self.COUNT))
        apply_live(rows, xml)
        for i, row in enumerate(rows[1:-1]):
            weather_time = self.FIRST + self.STEP * i
            for name, shape in shapes.items():
                actual, forecast, left = shape(weather_time)
                row["phenomena"][name].update(actual="%.6g" % actual, forecast="%.6g" % forecast,
                                              next_change="%.6g" % left)
            for entry in row["phenomena"].values():
                for key in ("limit_min", "limit_max", "change_min", "change_max", "time_min", "time_max"):
                    entry[key] = str(entry[key])
        return rows, plan_for(xml, variant, samples=self.COUNT, interval_s=5, start_delay_s=5)

    @staticmethod
    def candidate_shape(start, target, low, high):
        """Converges to `target` by 120 s; countdown 360.29 - t until 360 s; then 40 s segments alternating the
        forecast between `high` and `low`, the actual moving to each new forecast within 30 s."""
        slope = (target - start) / (120.0 - 5.30287)

        def shape(t):
            if t < 360.0:
                return min(target, start + slope * (t - 5.30287)), target, 360.29 - t
            index = int((t - 360.0) // 40)
            begin = 360.0 + 40 * index
            forecasts = [target] + [high if k % 2 == 0 else low for k in range(index + 1)]
            actual = forecasts[-2] + (forecasts[-1] - forecasts[-2]) * min(1.0, (t - begin) / 30.0)
            return actual, forecasts[-1], begin + 40 - t
        return shape

    @staticmethod
    def flat_shape(value, first_left):
        return lambda t: (value, value, first_left - t)

    def pair(self, candidate_xml):
        stock_rows, stock_plan = self.rows(STOCK, "stock", {"overcast": self.flat_shape(.2217, 900),
                                                            "fog": self.flat_shape(0.0, 900)})
        shapes = {"overcast": self.candidate_shape(.2877, .98, .97, .99), "fog": self.candidate_shape(.0312421, .75, .7, .8)}
        candidate_rows, candidate_plan = self.rows(candidate_xml, "candidate", shapes)
        return (report.evaluate(lines(stock_rows), STOCK, plan=stock_plan),
                report.evaluate(lines(candidate_rows), candidate_xml, plan=candidate_plan))

    def candidate_xml(self):
        xml = cfgweather(enable="1", overcast=(0.97, 0.99), fog=(0.7, 0.8),
                         times={"overcast": (30, 60), "fog": (30, 60)})
        return with_current(with_current(xml, "overcast", "0.98"), "fog", "0.75")

    def test_the_first_samples_are_a_transition_toward_the_current_target(self):
        stock, candidate = self.pair(self.candidate_xml())
        self.assertEqual("complete", candidate["status"], candidate["issues"])
        for name in ("overcast", "fog"):
            with self.subTest(name):
                entry = candidate["phenomena"][name]
                # the fog actual enters .7..8 one sample before it reaches .75; the overcast actual reaches .98 first
                self.assertEqual(self.WINDOW[name], (entry["initial_transition"]["samples"],
                                                     entry["initial_transition"]["ended_by"]))
                self.assertGreater(entry["initial_transition"]["actual_outside_limits"], 20)
                self.assertEqual("within_candidate", entry["status"])
                self.assertEqual(0, entry["actual_violations"])
                self.assertEqual(0, entry["forecast_outside_limits"])
                self.assertTrue(entry["current_readback"]["matches"], entry["current_readback"])

    def test_the_pair_reads_back_limits_time_limits_and_current_with_coverage_complete(self):
        stock, candidate = self.pair(self.candidate_xml())
        result = report.compare(stock, candidate)
        self.assertEqual("complete", result["status"], result["issues"])
        self.assertEqual("complete", result["coverage"])
        for name in ("overcast", "fog"):
            with self.subTest(name):
                entry = result["phenomena"][name]
                self.assertEqual("candidate_live_limits_read_back", entry["evidence"])
                self.assertEqual({"limits": "candidate_live_limits_read_back",
                                  "time_limits": "candidate_live_limits_read_back",
                                  "current": "candidate_current_read_back"}, entry["attribute_evidence"])
                self.assertEqual("within_candidate", entry["candidate_status"])
                self.assertEqual(self.WINDOW[name][0], entry["initial_transition"]["samples"])
                self.assertIs(False, entry["values_in_range"])
                self.assertIs(True, entry["values_in_range_after_initial_transition"])
        self.assertEqual("pending", result["runtime_acceptance"])

    def test_the_pre_existing_actual_is_kept_in_the_reported_range(self):
        stock, candidate = self.pair(self.candidate_xml())
        entry = candidate["phenomena"]["overcast"]
        self.assertGreater(entry["initial_transition"]["actual_outside_limits"], 0)
        self.assertEqual({"min": 0.2877, "max": 0.99}, {key: round(value, 4) for key, value in entry["actual_range"].items()})


class NonClaimTests(unittest.TestCase):
    """No output label states precedence or native non-application; a fixed non-claims list travels with it."""

    LABELS = {"pending", "not_treated", "treated_unsupported", "candidate_values_outside_limits",
              "inconclusive_readback", "candidate_live_limits_read_back", "current_inconclusive",
              "candidate_current_read_back"}

    def test_the_label_set_is_exactly_the_descriptive_one(self):
        self.assertEqual(self.LABELS, set(report.EVIDENCE_LABELS))
        for label in report.EVIDENCE_LABELS:
            for word in ("precedence", "governs", "applied", "ignored", "compliance", "proof"):
                self.assertNotIn(word, label)

    def test_every_pair_result_carries_the_fixed_non_claims_and_only_known_labels(self):
        def stale(rows):
            for row in rows[1:-1]:
                row["phenomena"]["overcast"].update(limit_min=0.0, limit_max=1.0)
        pairs = [report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", 0.9)),
                 report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", mutate=stale)),
                 report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", 0.3)),
                 report.compare(evaluated(STOCK, "stock", 0.3), report.evaluate("", DISTINCT))]
        for result in pairs:
            self.assertEqual(list(report.NON_CLAIMS), result["non_claims"])
            self.assertLessEqual({entry["evidence"] for entry in result["phenomena"].values()}, self.LABELS)
        self.assertEqual(list(report.NON_CLAIMS), evaluated(DISTINCT, "candidate")["non_claims"])

    def test_the_non_claims_name_precedence_non_application_the_stock_cycle_and_acceptance(self):
        text = " ".join(report.NON_CLAIMS).lower()
        for needle in ("precedence", "ignored", "delayed loading", "measurement defect", "stock run",
                       "runtime acceptance", "current"):
            self.assertIn(needle, text)


class ProvenanceTests(unittest.TestCase):
    """Runs may be compared only when they were built from the same engine, source, hook and sampling."""

    def pair(self, **candidate_args):
        return report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", **candidate_args))

    def assert_refused(self, result, fragment):
        self.assertEqual("pending", result["status"])
        self.assertTrue(any(fragment in issue for issue in result["issues"]), result["issues"])
        for name in PHENOMENA:
            self.assertEqual("pending" if name == "overcast" else "not_treated", result["phenomena"][name]["evidence"], name)

    def test_matching_provenance_compares(self):
        self.assertEqual("complete", self.pair()["status"])

    def test_different_engine_versions_are_refused(self):
        self.assert_refused(self.pair(header_changes={"version": "1.29.000000"}), "version")

    def test_a_differently_spelled_world_is_refused(self):
        self.assert_refused(self.pair(header_changes={"world": "chernarusplus"}), "world")

    def test_different_sampling_parameters_are_refused(self):
        def slower(rows):
            rows[0]["interval_ms"] = 60000
        self.assert_refused(self.pair(mutate=slower, interval_s=60), "interval")
        self.assert_refused(self.pair(count=8), "samples")
        self.assert_refused(self.pair(start_delay_s=60), "start_delay_s")

    def test_different_hooks_and_source_plans_are_refused(self):
        self.assert_refused(self.pair(hook_sha256="9" * 64), "hook")
        for key in SOURCE:
            with self.subTest(key=key):
                self.assert_refused(self.pair(source={key: "8" * 64}), key)

    def test_a_candidate_built_from_another_stock_cfgweather_is_refused(self):
        stock = evaluated(STOCK, "stock", 0.3)
        candidate = evaluated(DISTINCT, "candidate", stock=NARROW)
        self.assert_refused(report.compare(stock, candidate), "stock cfgweather")

    def test_runs_without_a_plan_or_with_swapped_variants_are_refused(self):
        stock = evaluated(STOCK, "stock", 0.3)
        self.assert_refused(report.compare(stock, evaluated(DISTINCT, "candidate", plan=False)), "plan")
        self.assert_refused(report.compare(evaluated(DISTINCT, "candidate"), stock), "variant")

    def test_a_different_observations_kind_is_refused(self):
        self.assert_refused(self.pair(observations_kind="taped-light-probe-observations"), "observations_kind")


class RobustnessTests(unittest.TestCase):
    def rows(self):
        return [header(6)] + [sample(i) for i in range(6)] + [end(6)]

    def assert_pending(self, rows_or_text, fragment=None, xml=DISTINCT):
        text = rows_or_text if isinstance(rows_or_text, str) else lines(rows_or_text)
        result = report.evaluate(text, xml)
        self.assertEqual("pending", result["status"])
        if fragment:
            self.assertTrue(any(fragment in issue for issue in result["issues"]), result["issues"])
        return result

    def test_duplicate_json_object_keys_are_malformed(self):
        text = run().replace('"actual": 0.9', '"actual": 0.1, "actual": 0.9', 1)
        self.assertNotEqual(run(), text)
        self.assert_pending(text, "malformed")
        top = run().replace('"type": "end"', '"type": "end", "type": "end"', 1)
        self.assert_pending(top, "malformed")

    def test_a_duplicate_key_in_the_plan_file_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = RuntimeAndCliTests().make_runtime(Path(temp))
            path = root / "weather-probe-plan.json"
            path.write_text(path.read_text().replace('"kind"', '"kind": "ce-probe", "kind"', 1))
            with self.assertRaises(ValueError):
                report.load_run(root)

    def test_numeric_overflow_is_malformed_not_a_crash(self):
        for huge in (10 ** 400, 1e999, "1" + "0" * 400):
            rows = self.rows()
            rows[1]["phenomena"]["overcast"]["actual"] = huge
            with self.subTest(huge=str(huge)[:12]):
                self.assert_pending(lines(rows) if not isinstance(huge, float) else
                                    lines(rows).replace("Infinity", "1e999"), "malformed")

    def test_the_cli_never_prints_a_traceback_for_overflow_and_keeps_its_exit_codes(self):
        rows = self.rows()
        rows[1]["phenomena"]["overcast"]["actual"] = 10 ** 400
        with tempfile.TemporaryDirectory() as temp:
            root = RuntimeAndCliTests().make_runtime(Path(temp), observations=lines(rows))
            done = subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit/weather_report.py"), "single",
                                   "--runtime", str(root)], capture_output=True, text=True)
            self.assertEqual(3, done.returncode, done.stderr[-300:])
            self.assertNotIn("Traceback", done.stderr)
            self.assertEqual("pending", json.loads(done.stdout)["status"])

    def test_an_unexpected_failure_becomes_exit_code_two_without_a_traceback(self):
        for error in (OverflowError("x"), RecursionError("y"), ZeroDivisionError("z")):
            err = io.StringIO()
            with self.subTest(error=type(error).__name__), mock.patch.object(report, "load_run", side_effect=error), \
                    mock.patch("sys.stderr", err), mock.patch("sys.stdout", io.StringIO()):
                self.assertEqual(2, report.main(["single", "--runtime", "anywhere"]))
            self.assertIn("weather_report:", err.getvalue())

    def test_deeply_nested_json_is_malformed_not_a_recursion_crash(self):
        self.assert_pending("[" * 100000 + "\n", "malformed")
        rows = self.rows()
        text = lines(rows[:2]) + "{\"type\": \"sample\", \"x\": " + "[" * 100000 + "\n" + lines(rows[3:])
        self.assert_pending(text, "malformed")

    def test_repeated_or_reversed_timestamps_are_not_an_ordered_sampling_run(self):
        rows = self.rows()
        for row in rows[1:7]:
            row["game_ms"] = 1
        self.assert_pending(rows, "game_ms")
        rows = self.rows()
        rows[4]["game_ms"] = rows[3]["game_ms"]
        self.assert_pending(rows, "game_ms")
        rows = self.rows()
        rows[3]["weather_time"], rows[4]["weather_time"] = rows[4]["weather_time"], rows[3]["weather_time"]
        self.assert_pending(rows, "weather_time")

    def test_samples_far_closer_than_the_interval_are_refused(self):
        rows = self.rows()
        for i, row in enumerate(rows[1:7]):
            row["game_ms"] = 1000 * i
        self.assert_pending(rows, "interval")

    def test_a_null_or_non_object_phenomena_value_is_pending(self):
        for bad in (None, [], "x", 3):
            rows = self.rows()
            rows[1]["phenomena"] = bad
            with self.subTest(bad=bad):
                self.assert_pending(rows, "malformed")


class RuntimeAndCliTests(unittest.TestCase):
    def make_runtime(self, root, xml=DISTINCT, observations=None, sentinel="status=complete samples=6\n", variant="candidate",
                     stock=STOCK):
        mission = root / "mpmissions/dayzOffline.chernarusplus"
        mission.mkdir(parents=True)
        (mission / "cfgweather.xml").write_bytes(xml)
        (root / "weather-probe-plan.json").write_text(json.dumps(plan_for(xml, variant, stock)))
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
