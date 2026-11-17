"""Offline interior point aggregation and treatment writer; SYNTHETIC fixtures only.

The census rows below are hand-built geometry, not DayZ observations. They check the
arithmetic and refusal rules of the aggregation; they never show where a real building
has floors, whether the engine raycast agrees with stock points, or what spawns.
"""
import json
import math
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tools.audit import interior_points as pts

BOX_MIN = (-5.0, -1.0, -4.0)
XS0 = [-4.5, -3.5, -2.5, -1.5, -0.5]
ZS = [-3.5, -2.5, -1.5, -0.5]
XS1 = [-4.5, -3.5, -2.5]


def cells(y, xs, zs, clearance=2.8, reach=-1, ny=1.0):
    return [[x, y, z, clearance, ny, reach] for x in xs for z in zs]


def storey_hits(reach=-1):
    return cells(0.0, XS0, ZS, reach=reach) + cells(3.0, XS1, ZS, reach=reach)


def placement(name, hits, index=0, role="tenement", found=True, box_source="clipping", reach_state="unavailable",
              ray_capped=False, output_capped=False):
    return {"i": index, "class": name, "role": role, "found": found, "box_source": box_source,
            "box_min": list(BOX_MIN), "box_max": [7.0, 9.0, 3.0],
            "grid": {"step": 1.0, "rows": 12, "cols": 7}, "reach": {"state": reach_state, "doors": [], "entrances": []},
            "hits": hits, "stats": {"ray_capped": ray_capped, "output_capped": output_capped}}


def census(rows, complete=True):
    return {"schema": 1, "kind": "interior-sampler-census", "world": "synthetic", "version": "0",
            "placements": rows, "summary": {"targets": len(rows), "found": len(rows), "complete": complete}}


def encode(document):
    return json.dumps(document).encode()


def four_placements(name, role="tenement", hits=None, **kwargs):
    return [placement(name, hits if hits is not None else storey_hits(), index=i, role=role, **kwargs) for i in range(4)]


STOCK = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<lootmax>
\t<group name="Land_HouseBlock_2F1" lootmax="6">
\t\t<usage name="Town" />
\t\t<container name="lootFloor" lootmax="4">
\t\t\t<category name="tools" />
\t\t\t<tag name="floor" />
\t\t\t<point pos="-4.4 0.0 -3.4" range="0.4" height="1.0" />
\t\t\t<point pos="-3.0 0.0 -2.0" range="0.4" height="1.0" />
\t\t\t<point pos="-1.0 0.0 -2.0" range="0.4" height="1.0" />
\t\t\t<point pos="-4.5 0.0 3.5" range="0.4" height="1.0" />
\t\t</container>
\t\t<container name="lootshelves" lootmax="2">
\t\t\t<category name="books" />
\t\t\t<tag name="shelves" />
\t\t\t<point pos="-4.5 1.0 -3.5" range="0.1" height="0.25" />
\t\t\t<point pos="-4.5 3.4 -3.5" range="0.1" height="0.25" />
\t\t\t<point pos="-2.5 5.9 -2.5" range="0.1" height="0.25" />
\t\t</container>
\t</group>
\t<group name="Land_Tenement_Small" lootmax="0">
\t\t<usage name="Town" />
\t\t<container name="lootFloor" lootmax="0">
\t\t\t<category name="tools" />
\t\t\t<category name="clothes" />
\t\t\t<tag name="floor" />
\t\t</container>
\t\t<container name="lootshelves" lootmax="0">
\t\t\t<category name="books" />
\t\t\t<tag name="shelves" />
\t\t</container>
\t\t<container name="lootweapons" lootmax="0">
\t\t\t<category name="weapons" />
\t\t</container>
\t</group>
\t<group name="Land_Tenement_Big" lootmax="0">
\t\t<usage name="Town" />
\t\t<container name="lootFloor" lootmax="0">
\t\t\t<category name="tools" />
\t\t\t<tag name="floor" />
\t\t</container>
\t\t<container name="lootshelves" lootmax="0">
\t\t\t<category name="books" />
\t\t\t<tag name="shelves" />
\t\t</container>
\t</group>
\t<group name="Land_Other" lootmax="3">
\t\t<container name="lootFloor" lootmax="3">
\t\t\t<category name="tools" />
\t\t\t<point pos="1 2 3" range="1" height="2" />
\t\t</container>
\t</group>
</lootmax>
"""


def full_census(extra_rows=()):
    rows = (four_placements("Land_Tenement_Small") + four_placements("Land_Tenement_Big", hits=cells(0.0, XS0, ZS))
            + four_placements("Land_HouseBlock_2F1", role="calibration") + list(extra_rows))
    return census(rows)


def candidates_of(rows, name="Land_Tenement_Small", **kwargs):
    return pts.class_candidates(pts.parse_census(encode(census(rows))), name, **kwargs)


def keyed(candidates):
    return {(round(c["x"], 2), round(c["z"], 2), c["storey"]): c for c in candidates}


class CensusParsingTests(unittest.TestCase):
    def test_valid_census_round_trips_and_defaults_are_documented_numbers(self):
        parsed = pts.parse_census(encode(full_census()))
        self.assertEqual(12, len(parsed["placements"]))
        self.assertEqual(1.9, pts.MIN_CLEARANCE)
        self.assertEqual(0.5, pts.CALIBRATION_RADIUS)

    def test_refusals(self):
        good = full_census()
        broken = []
        for mutate in (lambda d: d.update(kind="ce-probe-census"), lambda d: d.update(schema=2),
                       lambda d: d["summary"].update(complete=False), lambda d: d.pop("placements"),
                       lambda d: d["placements"][0]["hits"].append([1, 2, 3]),
                       lambda d: d["placements"][0]["hits"].append([1, 2, 3, 4, 5, 9]),
                       lambda d: d["placements"][0]["hits"].append([1, 2, 3, 4, 5, "x"]),
                       lambda d: d["placements"][0]["hits"].append([1, 2, 3, -1, 5, 0]),
                       lambda d: d["placements"][0].pop("hits"),
                       lambda d: d["placements"].extend(d["placements"] * 30)):
            document = json.loads(json.dumps(good))
            mutate(document)
            broken.append(document)
        for document in broken:
            with self.subTest(document=str(document)[:60]), self.assertRaises(ValueError):
                pts.parse_census(encode(document))
        for data in (b"not json", b"[]", b"", encode(good) + b" " * (pts.MAX_CENSUS_BYTES + 1)):
            with self.subTest(data=data[:12]), self.assertRaises(ValueError):
                pts.parse_census(data)
        with self.assertRaises(ValueError):
            pts.parse_census(b'{"kind": "interior-sampler-census", "schema": 1, "summary": {"complete": true}, '
                             b'"placements": [{"class": "A", "hits": [[NaN, 0, 0, 2, 1, 0]]}]}')


class CandidateTests(unittest.TestCase):
    def test_storeys_are_clustered_from_y_and_numbered_from_the_lowest(self):
        got = pts.class_candidates(pts.parse_census(encode(full_census())), "Land_Tenement_Small")
        self.assertEqual(32, len(got["candidates"]))
        self.assertEqual({0, 1}, {c["storey"] for c in got["candidates"]})
        self.assertEqual({0.0}, {c["y"] for c in got["candidates"] if c["storey"] == 0})
        self.assertEqual({3.0}, {c["y"] for c in got["candidates"] if c["storey"] == 1})
        self.assertEqual(20, sum(1 for c in got["candidates"] if c["storey"] == 0))

    def test_storey_noise_within_the_gap_stays_one_storey_and_a_larger_gap_splits(self):
        wobble = cells(0.0, XS0, [-3.5]) + cells(0.2, XS0, [-2.5]) + cells(0.4, XS0, [-1.5])
        got = candidates_of(four_placements("Land_Tenement_Small", hits=wobble))["candidates"]
        self.assertEqual({0}, {c["storey"] for c in got})
        split = cells(0.0, XS0, [-3.5]) + cells(0.9, XS0, [-3.5 + 1.0])
        got = candidates_of(four_placements("Land_Tenement_Small", hits=split), storey_gap=0.75)["candidates"]
        self.assertEqual({0, 1}, {c["storey"] for c in got})

    def test_clearance_flag_uses_the_minimum_over_placements_and_the_documented_threshold(self):
        low, high = cells(0.0, XS0, [-3.5], clearance=1.89), cells(0.0, XS0, [-2.5], clearance=1.9)
        rows = four_placements("Land_Tenement_Small", hits=low + high)
        got = keyed(candidates_of(rows)["candidates"])
        self.assertFalse(got[(-4.5, -3.5, 0)]["clearance_ok"])
        self.assertTrue(got[(-4.5, -2.5, 0)]["clearance_ok"])
        mixed = [placement("Land_Tenement_Small", cells(0.0, XS0, [-3.5], clearance=2.5 if i else 1.5), index=i)
                 for i in range(4)]
        cell = keyed(candidates_of(mixed)["candidates"])[(-4.5, -3.5, 0)]
        self.assertFalse(cell["clearance_ok"])
        self.assertEqual(1.5, cell["clearance"])

    def test_a_slab_underside_in_the_same_cell_does_not_replace_the_floor_above_it(self):
        hits = [[-4.5, 0.0, -3.5, 2.6, 1.0, -1], [-4.5, 2.6, -3.5, 0.4, -1.0, -1], [-4.5, 3.0, -3.5, 3.0, 1.0, -1]]
        got = keyed(candidates_of(four_placements("Land_Tenement_Small", hits=hits))["candidates"])
        self.assertEqual({(-4.5, -3.5, 0), (-4.5, -3.5, 1)}, set(got))
        self.assertTrue(got[(-4.5, -3.5, 1)]["clearance_ok"])
        self.assertEqual(3.0, got[(-4.5, -3.5, 1)]["y"])

    def test_slope_comes_from_neighbour_heights_and_isolated_cells_are_not_walkable(self):
        gentle = [[x, 0.3 * k, -3.5, 2.8, 1.0, -1] for k, x in enumerate(XS0)]
        steep = [[x, 0.8 * k, -1.5, 2.8, 1.0, -1] for k, x in enumerate(XS0)]
        alone = [[4.5, 0.0, 2.5, 2.8, 1.0, -1]]
        got = keyed(candidates_of(four_placements("Land_Tenement_Small", hits=gentle + steep + alone))["candidates"])
        self.assertTrue(all(got[(x, -3.5, 0)]["walkable"] for x in XS0))
        self.assertFalse(any(c["walkable"] for key, c in got.items() if key[1] == -1.5))
        self.assertFalse(got[(4.5, 2.5, 0)]["walkable"])

    def test_the_raw_engine_normal_is_carried_but_not_used_for_walkability(self):
        flat = cells(0.0, XS0, [-3.5], ny=0.12)
        got = candidates_of(four_placements("Land_Tenement_Small", hits=flat))["candidates"]
        self.assertTrue(all(c["walkable"] for c in got))
        self.assertEqual({0.12}, {c["ny_abs"] for c in got})

    def test_agreement_counts_only_usable_placements_and_is_per_cell_and_storey(self):
        rows = four_placements("Land_Tenement_Small")
        rows[3]["hits"] = [h for h in rows[3]["hits"] if h[0] != -4.5]
        rows.append(placement("Land_Tenement_Small", [], index=4, found=False))
        rows.append(placement("Land_Tenement_Small", storey_hits(), index=5, ray_capped=True))
        rows.append(placement("Land_Tenement_Small", storey_hits(), index=6, output_capped=True))
        rows.append(placement("Land_Tenement_Small", storey_hits(), index=7, box_source="none"))
        got = candidates_of(rows)
        self.assertEqual(4, got["usable_placements"])
        self.assertEqual(8, got["rows"])
        by = keyed(got["candidates"])
        self.assertEqual(0.75, by[(-4.5, -3.5, 0)]["agreement"])
        self.assertEqual(3, by[(-4.5, -3.5, 0)]["placements"])
        self.assertEqual(1.0, by[(-2.5, -2.5, 1)]["agreement"])

    def test_classes_without_a_usable_placement_have_no_candidates(self):
        got = candidates_of([placement("Land_Tenement_Small", [], found=False)])
        self.assertEqual(0, got["usable_placements"])
        self.assertEqual([], got["candidates"])
        self.assertEqual([], candidates_of(four_placements("Land_Tenement_Small"), name="Land_Absent")["candidates"])

    def test_reachability_is_unknown_without_any_tested_code_and_not_a_filter(self):
        got = candidates_of(four_placements("Land_Tenement_Small"))
        self.assertEqual("unknown", got["reach_mode"])
        self.assertTrue(all(c["reachable"] is None for c in got["candidates"]))
        self.assertEqual(32, len(pts.eligible(got["candidates"], got["reach_mode"], min_agreement=1.0)))

    def test_reachability_known_keeps_only_cells_reached_by_a_majority_of_tested_placements(self):
        def rows_with(codes):
            return [placement("Land_Tenement_Small", [[-4.5, 0.0, -3.5, 2.8, 1.0, codes[i]], [-3.5, 0.0, -3.5, 2.8, 1.0, 1],
                                                       [-2.5, 0.0, -3.5, 2.8, 1.0, -1], [-1.5, 0.0, -3.5, 2.8, 1.0, 2]],
                              index=i, reach_state="tested") for i in range(4)]
        got = candidates_of(rows_with([1, 1, 0, -1]))
        self.assertEqual("known", got["reach_mode"])
        by = keyed(got["candidates"])
        self.assertIs(True, by[(-4.5, -3.5, 0)]["reachable"])
        self.assertEqual({"yes": 2, "no": 1, "nonav": 0, "unknown": 1}, by[(-4.5, -3.5, 0)]["reach"])
        self.assertIs(True, by[(-3.5, -3.5, 0)]["reachable"])
        self.assertIs(False, by[(-2.5, -3.5, 0)]["reachable"])         # never tested
        self.assertIs(False, by[(-1.5, -3.5, 0)]["reachable"])         # no navmesh under the point
        tied = keyed(candidates_of(rows_with([1, 1, 0, 0]))["candidates"])
        self.assertIs(False, tied[(-4.5, -3.5, 0)]["reachable"])
        eligible = pts.eligible(got["candidates"], "known", min_agreement=0.75)
        self.assertEqual({(-4.5, -3.5), (-3.5, -3.5)}, {(round(c["x"], 2), round(c["z"], 2)) for c in eligible})

    def test_eligibility_requires_clearance_walkability_and_agreement(self):
        rows = four_placements("Land_Tenement_Small", hits=cells(0.0, XS0, ZS))
        rows[0]["hits"] = [h for h in rows[0]["hits"] if h[0] != -0.5]
        rows[1]["hits"] = [h for h in rows[1]["hits"] if h[0] != -0.5]
        got = candidates_of(rows)
        self.assertEqual(20, len(pts.eligible(got["candidates"], got["reach_mode"], min_agreement=0.5)))
        self.assertEqual(16, len(pts.eligible(got["candidates"], got["reach_mode"], min_agreement=0.75)))


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.candidates = pts.class_candidates(pts.parse_census(encode(full_census())), "Land_HouseBlock_2F1")
        self.stock = pts.parse_stock_points(STOCK, "Land_HouseBlock_2F1")

    def calibrate(self, radius):
        return pts.calibrate(self.candidates, self.stock, radius=radius, min_agreement=0.75)

    def test_stock_points_are_parsed_per_container(self):
        self.assertEqual({"lootFloor": 4, "lootshelves": 3}, {k: len(v) for k, v in self.stock.items()})
        self.assertEqual((-4.4, 0.0, -3.4), tuple(self.stock["lootFloor"][0][:3]))

    def test_coverage_at_half_a_metre_counts_xz_and_vertical_separately_with_exact_expected_numbers(self):
        result = self.calibrate(0.5)
        self.assertEqual(7, result["points"])
        self.assertEqual(4, result["xz_covered"])
        self.assertEqual(3, result["v3_covered"])
        self.assertAlmostEqual(4 / 7, result["xz_coverage"])
        self.assertAlmostEqual(3 / 7, result["v3_coverage"])
        self.assertEqual({"points": 4, "xz_covered": 1, "v3_covered": 1}, {k: result["containers"]["lootFloor"][k] for k in ("points", "xz_covered", "v3_covered")})
        self.assertEqual({"points": 3, "xz_covered": 3, "v3_covered": 2}, {k: result["containers"]["lootshelves"][k] for k in ("points", "xz_covered", "v3_covered")})
        self.assertEqual(32, result["candidates"])
        self.assertEqual(2, result["candidates_used"])
        self.assertEqual(30, result["candidates_unused"])

    def test_coverage_at_three_quarters_of_a_metre_reaches_the_grid_diagonal(self):
        result = self.calibrate(0.75)
        self.assertEqual(6, result["xz_covered"])
        self.assertEqual(10, result["candidates_used"])
        self.assertEqual(22, result["candidates_unused"])

    def test_the_radius_boundary_is_inclusive_and_just_outside_is_not_covered(self):
        stock = pts.parse_stock_points(
            b'<lootmax><group name="G"><container name="c"><point pos="0.0 0.0 -2.5" range="1" height="1" />'
            b'<point pos="0.01 0.0 -2.5" range="1" height="1" /></container></group></lootmax>', "G")
        result = pts.calibrate(self.candidates, stock, radius=0.5, min_agreement=0.75)
        self.assertEqual(1, result["xz_covered"])

    def test_vertical_band_runs_from_half_a_metre_below_the_floor_to_the_clearance(self):
        def covered(y):
            stock = pts.parse_stock_points(
                ('<lootmax><group name="G"><container name="c"><point pos="-4.5 %s -3.5" range="1" height="1" />'
                 '</container></group></lootmax>' % y).encode(), "G")
            return pts.calibrate(self.candidates, stock, radius=0.5, min_agreement=0.75)["v3_covered"]
        self.assertEqual(1, covered(-0.5))
        self.assertEqual(0, covered(-0.51))
        self.assertEqual(1, covered(2.8))
        self.assertEqual(1, covered(3.0))           # inside the upper storey's band
        self.assertEqual(0, covered(5.81))

    def test_ineligible_candidates_do_not_count_as_coverage(self):
        low = four_placements("Land_HouseBlock_2F1", role="calibration", hits=cells(0.0, XS0, ZS, clearance=1.5))
        candidates = pts.class_candidates(pts.parse_census(encode(census(low))), "Land_HouseBlock_2F1")
        result = pts.calibrate(candidates, self.stock, radius=0.5, min_agreement=0.75)
        self.assertEqual(0, result["xz_covered"])
        self.assertEqual(0, result["candidates"])

    def test_unreachable_cells_stop_counting_once_reachability_is_known(self):
        hits = [[x, 0.0, z, 2.8, 1.0, 1 if x < -2.0 else 0] for x in XS0 for z in ZS]
        rows = four_placements("Land_HouseBlock_2F1", role="calibration", hits=hits, reach_state="tested")
        candidates = pts.class_candidates(pts.parse_census(encode(census(rows))), "Land_HouseBlock_2F1")
        result = pts.calibrate(candidates, self.stock, radius=0.75, min_agreement=0.75)
        self.assertEqual("known", result["reach_mode"])
        self.assertEqual(12, result["candidates"])
        self.assertEqual(7, result["points"])
        self.assertEqual(5, result["xz_covered"])      # the (-1.0, -2.0) stock point has only unreachable cells nearby

    def test_empty_stock_points_report_zero_points_without_dividing_by_zero(self):
        result = pts.calibrate(self.candidates, {}, radius=0.5, min_agreement=0.75)
        self.assertEqual(0, result["points"])
        self.assertIsNone(result["xz_coverage"])


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.got = pts.class_candidates(pts.parse_census(encode(full_census())), "Land_Tenement_Small")

    def select(self, **kwargs):
        options = {"min_agreement": 0.75, "max_per_storey": 4, "max_total": 48, "spacing": 2.0}
        options.update(kwargs)
        return pts.select_points(self.got["candidates"], self.got["reach_mode"], **options)

    def test_farthest_point_order_is_deterministic_and_matches_the_hand_derived_picks(self):
        chosen = self.select()
        storey0 = [(p["x"], p["z"]) for p in chosen if p["storey"] == 0]
        self.assertEqual([(-4.5, -3.5), (-0.5, -0.5), (-4.5, -0.5), (-1.5, -3.5)], sorted(storey0, key=lambda c: chosen_order(chosen, c)))
        self.assertEqual(4, len(storey0))

    def test_result_is_bounded_spaced_sorted_and_independent_of_input_order(self):
        base = self.select()
        shuffled = list(reversed(self.got["candidates"]))
        again = pts.select_points(shuffled, self.got["reach_mode"], min_agreement=0.75, max_per_storey=4, max_total=48, spacing=2.0)
        self.assertEqual(base, again)
        self.assertLessEqual(len(base), 8)
        for storey in (0, 1):
            group = [p for p in base if p["storey"] == storey]
            self.assertLessEqual(len(group), 4)
            for i, a in enumerate(group):
                for b in group[i + 1:]:
                    self.assertGreaterEqual(math.hypot(a["x"] - b["x"], a["z"] - b["z"]), 2.0)
        self.assertEqual(sorted(base, key=lambda p: (p["storey"], p["x"], p["z"])), base)

    def test_total_cap_spacing_floor_and_empty_inputs(self):
        self.assertEqual(3, len(self.select(max_total=3)))
        self.assertEqual(8, len(self.select(max_per_storey=4, spacing=0.5)))
        wide = self.select(spacing=4.9, max_per_storey=12)
        self.assertEqual(2, len([p for p in wide if p["storey"] == 0]))
        self.assertEqual([], pts.select_points([], "unknown", min_agreement=0.75, max_per_storey=4, max_total=48, spacing=2.0))
        self.assertEqual([], self.select(max_total=0))

    def test_only_eligible_candidates_are_ever_selected(self):
        rows = four_placements("Land_Tenement_Small", hits=cells(0.0, XS0, ZS[:2], clearance=1.0) + cells(0.0, XS0, ZS[2:]))
        got = pts.class_candidates(pts.parse_census(encode(census(rows))), "Land_Tenement_Small")
        chosen = pts.select_points(got["candidates"], got["reach_mode"], min_agreement=0.75, max_per_storey=12, max_total=48, spacing=0.5)
        self.assertTrue(chosen)
        self.assertTrue(all(p["z"] in (-1.5, -0.5) for p in chosen))

    def test_selected_points_report_floor_height_clearance_and_provenance(self):
        point = self.select()[0]
        for key in ("x", "y", "z", "storey", "clearance", "agreement", "reachable"):
            self.assertIn(key, point)


def chosen_order(chosen, cell):
    for index, point in enumerate(chosen):
        if (point["x"], point["z"]) == cell and point["storey"] == 0:
            return point["pick"]
    raise AssertionError(cell)


def treated_groups(data):
    root = ET.fromstring(data)
    return {g.get("name"): g for g in root.iter("group")}


def strip_groups(text, names):
    for name in names:
        text = re.sub(r'[ \t]*<group name="%s"[^>]*>.*?</group>\r?\n?' % name, "", text, flags=re.S)
    return text


class TreatmentWriterTests(unittest.TestCase):
    def setUp(self):
        got = pts.class_candidates(pts.parse_census(encode(full_census())), "Land_Tenement_Small")
        self.small = pts.select_points(got["candidates"], got["reach_mode"], min_agreement=0.75, max_per_storey=4,
                                       max_total=48, spacing=2.0)
        self.big = self.small[:3]

    def write(self, **kwargs):
        return pts.write_treatment(STOCK, {"Land_Tenement_Small": self.small, "Land_Tenement_Big": self.big}, **kwargs)

    def test_only_the_two_tenement_groups_change_and_the_rest_is_byte_identical(self):
        treated = self.write().decode()
        names = ("Land_Tenement_Small", "Land_Tenement_Big")
        self.assertEqual(strip_groups(STOCK.decode(), names), strip_groups(treated, names))
        self.assertNotEqual(STOCK.decode(), treated)

    def test_categories_tags_usage_and_container_names_are_unchanged(self):
        before, after = treated_groups(STOCK), treated_groups(self.write())
        for name in ("Land_Tenement_Small", "Land_Tenement_Big"):
            def skeleton(group):
                return [(c.tag, c.attrib.get("name"))
                        for container in group.iter() for c in ([container] if container.tag != "point" and container.tag != "group" else [])
                        if c.tag in ("usage", "container", "category", "tag")]
            self.assertEqual(skeleton(before[name]), skeleton(after[name]))

    def test_points_land_only_in_the_floor_container_with_exact_format_and_lootmax(self):
        after = treated_groups(self.write(loot_ratio=0.25, max_lootmax=12))
        small = after["Land_Tenement_Small"]
        floor = [c for c in small.findall("container") if c.get("name") == "lootFloor"][0]
        written = floor.findall("point")
        self.assertEqual(len(self.small), len(written))
        self.assertEqual(2, int(floor.get("lootmax")))           # ceil(8 * 0.25)
        self.assertEqual("2", small.get("lootmax"))
        for other in small.findall("container"):
            if other.get("name") != "lootFloor":
                self.assertEqual([], other.findall("point"))
                self.assertEqual("0", other.get("lootmax"))
        first = written[0]
        self.assertEqual(("%.6f %.6f %.6f" % (self.small[0]["x"], self.small[0]["y"], self.small[0]["z"])), first.get("pos"))
        self.assertEqual("0.400000", first.get("range"))
        self.assertEqual("1.000000", first.get("height"))
        big = [c for c in after["Land_Tenement_Big"].findall("container") if c.get("name") == "lootFloor"][0]
        self.assertEqual(3, len(big.findall("point")))
        self.assertEqual("1", big.get("lootmax"))                # ceil(3 * 0.25)

    def test_lootmax_is_capped_and_never_zero_for_a_class_with_points(self):
        capped = treated_groups(self.write(loot_ratio=1.0, max_lootmax=5))["Land_Tenement_Small"]
        self.assertEqual("5", capped.get("lootmax"))
        tiny = pts.write_treatment(STOCK, {"Land_Tenement_Small": self.small[:1], "Land_Tenement_Big": []})
        self.assertEqual("1", treated_groups(tiny)["Land_Tenement_Small"].get("lootmax"))

    def test_a_class_without_points_keeps_its_stock_text(self):
        data = pts.write_treatment(STOCK, {"Land_Tenement_Small": self.small, "Land_Tenement_Big": []}).decode()
        self.assertEqual(strip_groups(STOCK.decode(), ("Land_Tenement_Small",)), strip_groups(data, ("Land_Tenement_Small",)))

    def test_inserted_points_share_the_indentation_of_the_container_children(self):
        text = self.write().decode()
        floor_block = text[text.index('<group name="Land_Tenement_Small"'):]
        tag = re.search(r'^(\s*)<tag name="floor" />', floor_block, re.M).group(1)
        point = re.search(r'^(\s*)<point ', floor_block, re.M).group(1)
        self.assertEqual(tag, point)

    def test_crlf_stock_text_stays_crlf(self):
        data = pts.write_treatment(STOCK.replace(b"\n", b"\r\n"), {"Land_Tenement_Small": self.small, "Land_Tenement_Big": []})
        self.assertNotRegex(data.decode(), r"(?<!\r)\n")

    def test_unsafe_stock_shapes_are_refused(self):
        selections = {"Land_Tenement_Small": self.small, "Land_Tenement_Big": []}
        with_points = STOCK.replace(b'<tag name="floor" />\n\t\t</container>\n\t\t<container name="lootshelves" lootmax="0">\n\t\t\t<category name="books" />\n\t\t\t<tag name="shelves" />\n\t\t</container>\n\t\t<container name="lootweapons"',
                                    b'<tag name="floor" />\n\t\t\t<point pos="1 2 3" range="1" height="1" />\n\t\t</container>\n\t\t<container name="lootshelves" lootmax="0">\n\t\t\t<category name="books" />\n\t\t\t<tag name="shelves" />\n\t\t</container>\n\t\t<container name="lootweapons"', 1)
        self.assertNotEqual(STOCK, with_points)
        nonzero = STOCK.replace(b'<group name="Land_Tenement_Small" lootmax="0">', b'<group name="Land_Tenement_Small" lootmax="7">')
        duplicated = STOCK + b'<group name="Land_Tenement_Small" lootmax="0"></group>\n'
        missing = STOCK.replace(b"Land_Tenement_Small", b"Land_Tenement_Tiny")
        nofloor = STOCK.replace(b'name="lootFloor" lootmax="0"', b'name="lootNothing" lootmax="0"', 1)
        for data in (with_points, nonzero, duplicated, missing, nofloor, b"<lootmax><group"):
            with self.subTest(data=data[-40:]), self.assertRaises(ValueError):
                pts.write_treatment(data, selections)
        with self.assertRaises(ValueError):
            pts.write_treatment(STOCK, {"Land_Other": self.small})

    def test_write_treatment_verifies_its_own_output(self):
        with mock.patch.object(pts, "_edit_group", lambda block, points, **kw: block + "<!-- stray -->\n"):
            with self.assertRaises(ValueError):
                self.write()


class BuildTreatmentTests(unittest.TestCase):
    def build(self, document=None, **kwargs):
        options = {"min_calibration": 0.4}
        options.update(kwargs)
        return pts.build_treatment(encode(document or full_census()), STOCK, **options)

    def test_build_reports_calibration_selection_and_hashes(self):
        data, report = self.build()
        self.assertEqual("interior-points-report", report["kind"])
        self.assertTrue(report["calibration"]["passed"])
        self.assertAlmostEqual(4 / 7, report["calibration"]["classes"]["Land_HouseBlock_2F1"]["xz_coverage"])
        self.assertAlmostEqual(4 / 7, report["calibration"]["min_coverage"])
        self.assertEqual(0.4, report["calibration"]["threshold"])
        self.assertEqual({"Land_Tenement_Small", "Land_Tenement_Big"}, set(report["classes"]))
        self.assertEqual(8, report["classes"]["Land_Tenement_Small"]["selected"])
        self.assertEqual(4, report["classes"]["Land_Tenement_Big"]["selected"])
        self.assertEqual(hash_of(data), report["treatment"]["sha256"])
        self.assertEqual(hash_of(STOCK), report["stock_mapgroupproto_sha256"])
        self.assertEqual(["Land_Tenement_Big", "Land_Tenement_Small"], sorted(report["treatment"]["groups_changed"]))
        self.assertIn("reachability_mode", report["classes"]["Land_Tenement_Small"])
        self.assertEqual("unknown", report["classes"]["Land_Tenement_Small"]["reachability_mode"])
        self.assertEqual(report, json.loads(json.dumps(report)))

    def test_coverage_below_the_threshold_is_refused_with_the_numbers(self):
        with self.assertRaises(pts.CoverageError) as caught:
            self.build(min_calibration=0.6)
        self.assertIn("0.571", str(caught.exception))
        _data, report = self.build(min_calibration=0.6, radius=0.75)
        self.assertGreaterEqual(report["calibration"]["min_coverage"], 6 / 7 - 1e-9)

    def test_missing_calibration_data_is_refused_not_assumed(self):
        document = census(four_placements("Land_Tenement_Small") + four_placements("Land_Tenement_Big"))
        with self.assertRaises(pts.CoverageError):
            self.build(document)
        document = census(four_placements("Land_Tenement_Small") + four_placements("Land_Tenement_Big")
                          + four_placements("Land_HouseBlock_2F1", role="calibration", hits=[]))
        with self.assertRaises(pts.CoverageError):
            self.build(document)

    def test_classes_without_eligible_candidates_are_refused(self):
        document = census(four_placements("Land_Tenement_Small", hits=[]) + four_placements("Land_Tenement_Big")
                          + four_placements("Land_HouseBlock_2F1", role="calibration"))
        with self.assertRaises(ValueError):
            self.build(document)
        data, report = self.build(document, allow_empty_classes=True)
        self.assertEqual(0, report["classes"]["Land_Tenement_Small"]["selected"])

    def test_bad_arguments_are_refused(self):
        for kwargs in ({"min_calibration": -0.1}, {"min_calibration": 1.1}, {"radius": 0.0}, {"radius": 3.0},
                       {"max_per_storey": 0}, {"max_per_storey": 100}, {"max_total": 500}, {"spacing": 0.1},
                       {"loot_ratio": 0.0}, {"max_lootmax": 0}, {"min_agreement": 0.0}, {"min_agreement": 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.build(**kwargs)

    def test_two_runs_are_byte_identical(self):
        self.assertEqual(self.build()[0], self.build()[0])


def hash_of(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


class CliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.census = self.root / "census.json"
        self.stock = self.root / "mapgroupproto.xml"
        self.census.write_bytes(encode(full_census()))
        self.stock.write_bytes(STOCK)
        self.out = self.root / "out" / "mapgroupproto.xml"
        self.report = self.root / "out" / "report.json"

    def argv(self, *extra):
        return ["--census", str(self.census), "--stock-proto", str(self.stock), "--output", str(self.out),
                "--report", str(self.report), *extra]

    def test_cli_writes_treatment_and_report_outside_git_and_refuses_overwrite(self):
        with mock.patch("sys.stdout") as out:
            self.assertEqual(0, pts.main(self.argv("--min-calibration", "0.4")))
        self.assertIn("treatment", "".join(call.args[0] for call in out.write.call_args_list))
        self.assertEqual(set(treated_groups(STOCK)), set(treated_groups(self.out.read_bytes())))
        self.assertEqual("interior-points-report", json.loads(self.report.read_text())["kind"])
        with mock.patch("sys.stderr") as err:
            self.assertEqual(1, pts.main(self.argv("--min-calibration", "0.4")))
        self.assertIn("interior_points:", "".join(call.args[0] for call in err.write.call_args_list))

    def test_cli_refuses_low_coverage_without_writing_anything(self):
        with mock.patch("sys.stderr") as err:
            self.assertEqual(2, pts.main(self.argv("--min-calibration", "0.9")))
        self.assertIn("coverage", "".join(call.args[0] for call in err.write.call_args_list).lower())
        self.assertFalse(self.out.exists())
        self.assertFalse(self.report.exists())

    def test_cli_refuses_outputs_inside_the_source_checkout_or_with_traversal(self):
        inside = Path(pts.__file__).resolve().parents[2] / "treatment-must-not-exist.xml"
        for bad in (inside, self.root / ".." / "x.xml"):
            argv = ["--census", str(self.census), "--stock-proto", str(self.stock), "--output", str(bad),
                    "--report", str(self.report)]
            with self.subTest(bad=str(bad)), mock.patch("sys.stderr"):
                self.assertEqual(1, pts.main(argv))
        self.assertFalse(inside.exists())

    def test_cli_reports_unreadable_input_without_a_traceback(self):
        argv = self.argv()
        argv[1] = str(self.root / "missing.json")
        with mock.patch("sys.stderr") as err:
            self.assertEqual(1, pts.main(argv))
        self.assertIn("interior_points:", "".join(call.args[0] for call in err.write.call_args_list))


if __name__ == "__main__":
    unittest.main()
