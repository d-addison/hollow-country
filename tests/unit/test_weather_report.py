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
import subprocess
import sys
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
    row = {"type": "sample", "seq": seq, "game_ms": 30000 * seq, "weather_time": number(30 * seq, text),
            "mission_weather": mission_weather, "update_frozen": frozen, "year": 2026, "month": 11, "day": 17,
            "hour": 9, "minute": seq, "wind_speed": number(4, text), "wind_max_speed": number(20, text),
            "volfog_enabled": True, "volfog_distance_density": number(0.1, text),
            "volfog_height_density": number(0.2, text), "volfog_height_bias": number(50, text),
            "phenomena": {name: phenomenon(name, values[name], text, (limits or {}).get(name)) for name in PHENOMENA}}
    # Synthetic progression: a forecast boundary every 100 s and a forecast that moves after the first one.
    for name, entry in row["phenomena"].items():
        entry["next_change"] = number(100 * (30 * seq // 100 + 1), text)
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
    def test_candidate_values_outside_the_stock_limits_and_inside_the_candidate_show_observed_limit_compliance(self):
        stock = evaluated(STOCK, "stock", 0.3)
        candidate = evaluated(DISTINCT, "candidate", 0.9)
        narrow = evaluated(NARROW, "stock", 0.3, stock=NARROW, limits={"overcast": (0.2, 0.6)})
        narrow_candidate = evaluated(DISTINCT, "candidate", 0.9, stock=NARROW)
        result = report.compare(narrow, narrow_candidate)
        self.assertEqual("observed_limit_compliance", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("not_treated", result["phenomena"]["fog"]["evidence"])
        self.assertEqual(["overcast"], result["treated"])
        self.assertEqual("complete", result["status"], result["issues"])
        self.assertEqual("pending", result["runtime_acceptance"])
        self.assertFalse(result["feature_complete"])
        plain = report.compare(stock, candidate)
        self.assertEqual("observed_limit_compliance", plain["phenomena"]["overcast"]["evidence"])
        self.assertNotIn("candidate_governs", json.dumps(plain))
        self.assertTrue(any("not proof" in note for note in plain["notes"]), plain["notes"])

    def test_candidate_values_outside_the_candidate_limits_show_limits_exceeded_in_the_candidate_run(self):
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", 0.3))
        self.assertEqual("candidate_limits_exceeded", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("complete", result["status"], result["issues"])

    def test_a_candidate_inside_the_stock_range_cannot_discriminate(self):
        result = report.compare(evaluated(STOCK, "stock", 0.9), evaluated(DISTINCT, "candidate", 0.9))
        self.assertEqual("not_discriminating", result["phenomena"]["overcast"]["evidence"])

    def test_a_stock_run_that_only_partly_leaves_the_candidate_range_is_weak_evidence(self):
        def partly(rows):
            for i, row in enumerate(rows[1:7]):
                row["phenomena"]["overcast"]["actual"] = 0.3 if i < 2 else 0.9
        result = report.compare(evaluated(STOCK, "stock", mutate=partly), evaluated(DISTINCT, "candidate", 0.9))
        self.assertEqual("weakly_discriminating", result["phenomena"]["overcast"]["evidence"])

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
                row["phenomena"]["fog"]["next_change"] = 1000
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(both, "candidate", mutate=stuck))
        self.assertEqual(["overcast", "fog"], result["treated"])
        self.assertEqual("pending", result["phenomena"]["fog"]["evidence"])
        self.assertEqual("observed_limit_compliance", result["phenomena"]["overcast"]["evidence"])
        self.assertEqual("pending", result["status"])
        self.assertTrue(any("fog" in issue for issue in result["issues"]), result["issues"])


class ProgressionTests(unittest.TestCase):
    """Compliance with the candidate's limits only counts when something was observed changing."""

    def compare(self, stock_overcast=0.3, candidate_overcast=0.9, stock_mutate=None, candidate_mutate=None, xml=DISTINCT):
        stock = evaluated(STOCK, "stock", stock_overcast, mutate=stock_mutate)
        candidate = evaluated(xml, "candidate", candidate_overcast, mutate=candidate_mutate)
        return report.compare(stock, candidate)

    def assert_not_established(self, result):
        self.assertNotEqual("observed_limit_compliance", result["phenomena"]["overcast"]["evidence"])
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
                entry.update(limit_min=0.0, limit_max=1.0, forecast=0.3, next_change=1000)
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
                row["phenomena"]["overcast"].update(actual=0.86 + i * 0.01, limit_min=0.0, limit_max=1.0, forecast=0.3)
        candidate = evaluated(DISTINCT, "candidate", 0.9, mutate=conflicting)
        result = report.compare(evaluated(STOCK, "stock", 0.3), candidate)
        entry = self.overcast(result)
        self.assertEqual("limits_not_observed_applied", entry["evidence"])
        self.assertIs(True, entry["values_in_range"])
        self.assertFalse(entry["live_readback"]["limits"]["candidate_live_matches_candidate_xml"])
        self.assertEqual(6, entry["candidate_forecast_outside_limits"])
        self.assertEqual("complete", result["status"], result["issues"])

    def test_a_stock_run_that_reads_the_same_live_limits_gives_no_differential(self):
        def same_as_candidate(rows):
            for row in rows[1:-1]:
                row["phenomena"]["overcast"].update(limit_min=0.8, limit_max=0.95)
        result = report.compare(evaluated(STOCK, "stock", 0.3, mutate=same_as_candidate), evaluated(DISTINCT, "candidate"))
        readback = self.overcast(result)["live_readback"]["limits"]
        self.assertEqual("limits_not_observed_applied", self.overcast(result)["evidence"])
        self.assertTrue(readback["candidate_live_matches_candidate_xml"])
        self.assertFalse(readback["stock_live_differs_from_candidate_xml"])

    def test_the_differential_makes_the_positive_label_and_reports_the_live_readings(self):
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(DISTINCT, "candidate", 0.9))
        entry = self.overcast(result)
        self.assertEqual("observed_limit_compliance", entry["evidence"])
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
        self.assertEqual("limits_not_observed_applied", ignored["phenomena"]["fog"]["evidence"])
        shown = report.compare(evaluated(STOCK, "stock"), evaluated(xml, "candidate"))
        self.assertTrue(shown["phenomena"]["fog"]["live_readback"]["time_limits"]["candidate_live_matches_candidate_xml"])
        self.assertNotEqual("limits_not_observed_applied", shown["phenomena"]["fog"]["evidence"])

    def test_a_comparison_whose_candidate_changes_no_limits_has_nothing_to_compare(self):
        result = report.compare(evaluated(STOCK, "stock", 0.3), evaluated(cfgweather(enable="1"), "candidate", 0.3))
        self.assertEqual("pending", result["status"])
        self.assertEqual([], result["treated"])
        self.assertTrue(any("no treatment" in issue for issue in result["issues"]), result["issues"])
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
        self.assertEqual("observed_limit_compliance", result["phenomena"]["overcast"]["evidence"])

    def test_slow_fog_and_wind_direction_schedules_do_not_block_an_overcast_result_in_a_24_minute_run(self):
        # Invented deadlines reflecting visible native durations; not recorded native observations.
        def run(xml, variant, overcast):
            rows = [header(289, interval_ms=5000, cap_ms=1475000)]
            for i in range(289):
                row = sample(i, {"overcast": overcast})
                row["game_ms"] = 30000 + 5000 * i
                row["weather_time"] = 30 + 5 * i
                for entry in row["phenomena"].values():
                    entry["next_change"] = 100 * ((30 + 5 * i) // 100 + 1)
                    entry["forecast"] = entry["actual"] if i < 14 else entry["actual"] + 0.01
                row["phenomena"]["fog"]["next_change"] = 1805
                row["phenomena"]["windDirection"]["next_change"] = 2205
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


class DeadlineProgressionTests(unittest.TestCase):
    """Passing a deadline shows nothing unless the controller then rescheduled or chose a new forecast."""

    def test_interpolation_toward_an_unchanged_forecast_with_an_unchanged_deadline_is_not_a_cycle(self):
        def interpolate(rows):
            for i, row in enumerate(rows[1:-1]):
                row["phenomena"]["overcast"].update(actual=0.81 + i * 0.01, forecast=0.9, next_change=100)
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
            "no deadline reached": ([(0, 100, .5), (30, 100, .5), (60, 100, .5)], (False, False)),
            "crossed, nothing recomputed": ([(0, 100, .5), (60, 100, .5), (120, 100, .5), (150, 100, .5)], (True, False)),
            "crossed, new deadline": ([(0, 100, .5), (60, 100, .5), (120, 200, .5)], (True, True)),
            "crossed, deadline appears one sample later": ([(0, 100, .5), (120, 100, .5), (150, 260, .5)], (True, True)),
            "crossed, new forecast": ([(0, 100, .5), (60, 100, .5), (120, 100, .6)], (True, True)),
            "crossed, forecast changes one sample later": ([(0, 100, .5), (120, 100, .5), (150, 100, .6)], (True, True)),
            "deadline reset to an expired value": ([(0, 100, .5), (120, 100, .5), (150, 90, .5)], (True, False)),
            "forecast moved before the deadline only": ([(0, 100, .5), (60, 100, .6), (120, 100, .6), (150, 100, .6)],
                                                        (True, False)),
            "zero deadlines never count": ([(t, 0, 0.5) for t in spread], (False, False)),
            "zero deadlines with a changing forecast": ([(t, 0, 0.5 + t / 1000) for t in spread], (False, False)),
            "negative deadlines": ([(t, -5, 0.5 + t / 1000) for t in spread], (False, False)),
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
