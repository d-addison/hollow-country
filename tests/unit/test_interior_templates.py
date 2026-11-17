"""Offline interior template builder; SYNTHETIC fixtures only.

The census rows and stock XML below are hand-built. They check the schema, the caps, the frame
conversion and the refusal rules of tools/package/interior_templates.py. They never show how a real
building is laid out, where the engine places a prop, or what spawns; runtime acceptance stays pending.
"""
import contextlib
import copy
import io
import json
import math
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from tools.audit import interior_points as pts
from tools.package import interior_templates as tpl

ROOT = Path(__file__).resolve().parents[2]
RUN = "a" * 32
HOUSE = "Land_Test_House"
CALIBRATION = ("Land_HouseBlock_2F1", "Land_Mil_Barracks2")
XS = [x + 0.5 for x in range(-4, 4)]
ZS = [z + 0.5 for z in range(-3, 3)]


def grid(xs, zs, y=0.0, clearance=2.8, reach=1):
    return [[x, y, z, clearance, 1.0, reach] for x in xs for z in zs]


def door_run(positions):
    count = len(positions)
    return {"count": count, "locked": 0, "open_at_start": 0, "ajar_at_start": 0, "moving_at_start": 0,
            "opened": count, "opened_doors": list(range(count)), "observed_open": count, "restored": count,
            "delay_ticks": 5, "open_settle_ticks": 0, "close_settle_ticks": 0, "settle_limit": 30,
            "state": "done", "doors": [[x, y, z, 0, 0, 0] for x, y, z in positions]}


def frame_records(frame="rot90", count=8):
    as_is, rotated = {"as-is": (1, 0), "rot90": (0, 1), "none": (0, 0)}[frame]
    return [[float(i), 0.0, float(-i), as_is, 0.0, rotated, 0.0] for i in range(count)]


def placement(cls, hits, index=0, doors=((4.0, 1.0, 0.0),), state="tested", entered="entered", found=True,
              box_min=(-4.0, -1.0, -3.0), frame=None, box_max=None):
    closed = [list(h[:5]) + [0 if h[5] == 1 else h[5]] for h in hits]
    row = {"i": index, "class": cls, "found": found, "box_source": "clipping" if found else "none",
           "box_min": list(box_min), "box_max": list(box_max) if box_max is not None else [box_min[0] + 8, 5.0, box_min[2] + 6],
           "grid": {"step": 1.0, "rows": 6, "cols": 8},
           "reach": {"state": state, "doors": [], "entrances": []},
           "entered": {"strict": {"closed": "not-entered", "open": entered},
                       "player": {"closed": "not-entered", "open": entered}},
           "hits": closed, "open_codes": [h[5] for h in hits], "door_run": door_run(list(doors)),
           "stats": {"ray_capped": False, "output_capped": False}}
    if frame:
        row["frame"] = frame_records(frame)
    return row


def calibration_rows(frame="rot90"):
    return [placement(name, [], index=100 + i, frame=frame) for i, name in enumerate(CALIBRATION)]


def house_rows(cls=HOUSE, **kwargs):
    kwargs.setdefault("doors", ((4.0, 1.0, 0.0),))
    return [placement(cls, grid(XS, ZS), index=i, **kwargs) for i in range(2)]


def census(rows, classes, run_id=RUN, complete=True):
    return {"Synthetic": True, "schema": 1, "kind": "interior-sampler-census", "door_phase_contract": 2,
            "native_run_id": run_id, "world": "synthetic", "version": "0", "house_classes": list(classes),
            "placements": rows, "summary": {"targets": len(rows), "found": len(rows), "complete": complete}}


def encode(document):
    return json.dumps(document).encode()


def point(pos, rng="0.4", height="1.0"):
    return '<point pos="%s" range="%s" height="%s" />' % (pos, rng, height)


def container(name, points, categories=("tools",), tags=()):
    body = "".join('<category name="%s" />' % c for c in categories) + "".join('<tag name="%s" />' % t for t in tags)
    return '<container name="%s" lootmax="2">%s%s</container>' % (name, body, "".join(points))


def group(name, containers, usages=("Town",)):
    return '<group name="%s" lootmax="3">%s%s</group>' % (
        name, "".join('<usage name="%s" />' % u for u in usages), "".join(containers))


def proto_xml(groups):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!-- Synthetic fixture -->\n<prototype>'
            + "".join(groups) + "</prototype>").encode()


def pos_xml(entries):
    rows = "".join('<group name="%s" pos="%s" rpy="0 0 0" a="%s" />' % entry for entry in entries)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!-- Synthetic fixture -->\n<map>' + rows + "</map>").encode()


# Stock points are in the stock frame: for rot90, sampler = (-z, y, x).
HOUSE_GROUP = group(HOUSE, [
    container("lootFloor", [point("2.0 0.0 3.0"), point("-1.0 0.0 -1.0")], ("tools", "clothes"), ("floor",)),
    container("lootshelves", [point("1.0 1.0 3.0", "0.1", "0.25"), point("1.2 1.0 3.0", "0.1", "0.25")],
              ("books",), ("shelves",))])
OTHER_GROUP = group("Land_Other_Farm", [container("loot", [point("0 0 0")])], ("Farm",))
PROTO = proto_xml([HOUSE_GROUP, OTHER_GROUP])
POS = pos_xml([(HOUSE, "1598.030273 304.510010 8970.620117", "15.04"),
               (HOUSE, "2000.5 310.25 9000.75", "-120.5"),
               (HOUSE, "3000.0 100.0 4000.0", "90.0"),
               ("Land_Other_Farm", "10 20 30", "5")])
CLASSES = (HOUSE,) + CALIBRATION
TYPES = (b'<types><type name="Hammer"><nominal>5</nominal><category name="tools"/></type>'
         b'<type name="Book"><nominal>5</nominal><category name="books"/></type></types>')


def standard(classes=CLASSES, rows=None, proto=PROTO, pos=POS, **kwargs):
    rows = house_rows() + calibration_rows() if rows is None else rows
    kwargs.setdefault("types_bytes", TYPES)
    return tpl.build([encode(census(rows, classes))], proto, pos, **kwargs)


def load(result, name):
    return json.loads(result.files[name])


def class_rows(result):
    rows = []
    for name in sorted(n for n in result.files if n.startswith("classes-")):
        rows.extend(load(result, name)["Rows"])
    return {row["BuildingClass"]: row for row in rows}


def furnish_rows(result):
    rows = []
    for name in sorted(n for n in result.files if n.startswith("furnish-")):
        rows.extend(load(result, name)["Rows"])
    return rows


def template(result, cls=HOUSE):
    for name in sorted(n for n in result.files if n.startswith("t-")):
        data = load(result, name)
        if data["BuildingClass"] == cls:
            return data
    return None


def inside(outer, inner, eps=1e-9):
    return all(outer["Min"][i] - eps <= inner["Min"][i] and inner["Max"][i] <= outer["Max"][i] + eps for i in range(3))


def overlap(a, b, margin=0.0, axes=(0, 1, 2)):
    return all(a["Min"][i] - margin < b["Max"][i] and b["Min"][i] < a["Max"][i] + margin for i in axes)


class FrameAndShapeTests(unittest.TestCase):
    def setUp(self):
        self.result = standard()
        self.template = template(self.result)

    def test_bounds_include_keepouts_and_sites_but_never_exceed_census_model(self):
        pr = proto_xml([group(HOUSE, [container("lootFloor", [
            point("2 4.5 3"), point("0 0 -20")])])])
        built = standard(proto=pr)
        t = template(built)
        model = {"Min": [-4, -1, -3], "Max": [4, 5, 3]}
        self.assertTrue(inside(model, t["Box"]))
        self.assertEqual(t["Box"]["Max"][1], 5)
        self.assertTrue(all(inside(t["Box"], k) for k in t["KeepOuts"]))
        self.assertEqual([s["Center"] for s in t["SearchSites"]], [[-3, 4.5, 2]])
        self.assertEqual(built.summary["keepouts_dropped_outside_model"], 1)
        self.assertEqual(built.summary["sites_dropped_outside_model"], 1)
        self.assertEqual(built.summary["search_points_dropped"], 1)

    def test_symmetric_calibrator_is_ignored_and_decisive_classes_are_recorded(self):
        rows = house_rows() + calibration_rows()
        rows[-2]["frame"] = [[float(i), 0, 0, 1, 0, 1, 0] for i in range(8)]
        built = standard(rows=rows)
        verdict = built.manifest["FrameVerdict"]
        self.assertEqual(verdict["deciding_classes"], [CALIBRATION[1]])
        self.assertEqual(verdict["ignored_classes"], [CALIBRATION[0]])
        self.assertEqual(verdict["verdict"], "rot90")

    def test_contradictory_or_only_symmetric_calibrators_refuse(self):
        for mode in ("contradiction", "symmetric"):
            rows = house_rows() + calibration_rows()
            if mode == "contradiction":
                rows[-2]["frame"] = frame_records("as-is")
            else:
                for row in rows[-2:]:
                    row["frame"] = [[float(i), 0, 0, 1, 0, 1, 0] for i in range(8)]
            with self.subTest(mode=mode), self.assertRaises(tpl.TemplateError):
                standard(rows=rows)

    def test_generated_props_do_not_touch_keepout_faces(self):
        from tools.package import interiors_profile as ip
        pr = proto_xml([group(HOUSE, [container("lootFloor", [point("-2.65 0 3", "0.05", "1")])])])
        t = template(standard(proto=pr))
        for prop in t["PropSlots"]:
            for keep in t["KeepOuts"]:
                self.assertFalse(ip._template_intersects(prop["Bounds"], keep,
                                 0.6 if keep["Kind"] == "door" else 0), (prop, keep))

    def test_the_house_class_gets_a_template_that_matches_the_contract_schema(self):
        t = self.template
        self.assertEqual(list(t), ["SchemaVersion", "BuildingClass", "TemplateId", "Box", "Evidence", "Rooms",
                                   "KeepOuts", "PropSlots", "SearchSites"])
        self.assertEqual(t["SchemaVersion"], 2)
        self.assertEqual(t["TemplateId"], "land_test_house-v1")
        self.assertEqual(t["Evidence"], [{"Kind": "native-room-survey-v1", "RunId": RUN,
                                          "Sha256": tpl.sha256(encode(census(house_rows() + calibration_rows(), CLASSES)))}])
        self.assertEqual(sorted(t["Box"]), ["Max", "Min"])
        for room in t["Rooms"]:
            self.assertEqual(list(room), ["Id", "Label", "Min", "Max", "Anchor", "FloorY", "Cells"])
            self.assertEqual(room["Label"], "room")
            self.assertTrue(inside(t["Box"], room))
            self.assertTrue(all(room["Min"][i] <= room["Anchor"][i] <= room["Max"][i] for i in range(3)))
            self.assertTrue(all(abs(v) <= 512 for v in room["Min"] + room["Max"]))
        self.assertEqual([r["Id"] for r in t["Rooms"]], list(range(1, len(t["Rooms"]) + 1)))

    def test_the_room_is_the_door_trimmed_cell_cluster_with_the_doors_keep_out(self):
        t = self.template
        self.assertEqual(len(t["Rooms"]), 1)
        # 8 x 6 cells minus the four cells whose centres lie inside the grown door box (x 2.8..5.2, z -1.2..1.2).
        door_cells = [c for c in ((3.5, -0.5), (3.5, 0.5))]
        self.assertEqual(t["Rooms"][0]["Cells"], 48 - len(door_cells))
        doors = [k for k in t["KeepOuts"] if k["Kind"] == "door"]
        self.assertEqual(len(doors), 1)
        self.assertEqual(doors[0]["Min"][0], 2.8)
        self.assertEqual(doors[0]["Min"][2], -1.2)
        self.assertEqual(doors[0]["Max"][2], 1.2)
        self.assertLessEqual(doors[0]["Max"][0], t["Box"]["Max"][0])

    def test_a_door_in_a_thin_building_splits_it_into_two_rooms(self):
        rows = [placement(HOUSE, grid([x + 0.5 for x in range(-4, 4)], [-0.5, 0.5]), index=i,
                          doors=((0.0, 1.0, 0.0),)) for i in range(2)]
        result = standard(rows=rows + calibration_rows())
        rooms = template(result)["Rooms"]
        self.assertEqual([r["Cells"] for r in rooms], [6, 6])
        self.assertLess(rooms[0]["Max"][0], rooms[1]["Min"][0] + 1.5)

    def test_stock_points_are_converted_with_the_native_frame_verdict(self):
        t = self.template
        self.assertEqual(pts.frame_verdict(census(house_rows() + calibration_rows(), CLASSES))["verdict"], "rot90")
        points = [k for k in t["KeepOuts"] if k["Kind"] == "ce-point"]
        self.assertEqual(len(points), 4)
        expected = pts.stock_to_sampler((2.0, 0.0, 3.0), "rot90")
        self.assertEqual(expected, (-3.0, 0.0, 2.0))
        self.assertIn({"Kind": "ce-point", "Min": [-3.4, 0.0, 1.6], "Max": [-2.6, 1.0, 2.4]},
                      [{k: v for k, v in p.items() if k != "Index"} for p in points])
        floor = [s for s in t["SearchSites"] if s["Source"] == "lootFloor"]
        self.assertEqual(sorted(s["Center"] for s in floor), [[-3.0, 0.0, 2.0], [1.0, 0.0, -1.0]])

    def test_the_as_is_verdict_is_refused_by_the_runtime_pack_builder(self):
        rows = house_rows() + calibration_rows("as-is")
        with self.assertRaisesRegex(tpl.TemplateError, "rot90"):
            standard(rows=rows)

    def test_search_sites_follow_the_contract(self):
        sites = self.template["SearchSites"]
        self.assertEqual([s["Id"] for s in sites], [1, 2, 3])
        shelves = sites[0]
        self.assertEqual((shelves["Source"], shelves["Points"]), ("lootshelves", [0, 1]))
        self.assertEqual(shelves["Center"], [-3.0, 1.0, 1.1])
        self.assertEqual(shelves["Radius"], 0.25)
        self.assertTrue(all(re.fullmatch(r"g-\d{4}", g) for s in sites for g in s["Groups"]))
        self.assertTrue(all(1 <= len(s["Groups"]) <= 8 and s["Room"] == 1 for s in sites))
        self.assertEqual(sites[1]["Groups"] != sites[0]["Groups"], True)

    def test_every_stock_point_lies_inside_its_site_sphere(self):
        for site in self.template["SearchSites"]:
            self.assertGreaterEqual(site["Radius"], 0.25)
            self.assertLessEqual(site["Radius"], 8.0)

    def test_a_ramp_beside_the_room_becomes_a_stair_keep_out(self):
        flat = grid([x + 0.5 for x in range(-2, 2)], [x + 0.5 for x in range(-2, 2)])
        ramp = [[2.5, 0.5, 0.5, 2.8, 1.0, 1], [3.5, 1.0, 0.5, 2.8, 1.0, 1], [4.5, 1.5, 0.5, 2.8, 1.0, 1]]
        rows = [placement(HOUSE, flat + ramp, index=i, doors=((-2.0, 1.0, 0.0),), box_min=(-2.0, -1.0, -2.0))
                for i in range(2)]
        t = template(standard(rows=rows + calibration_rows()))
        stairs = [k for k in t["KeepOuts"] if k["Kind"] == "stair"]
        self.assertEqual(len(stairs), 1)
        self.assertLessEqual(stairs[0]["Min"][0], 2.0)
        self.assertGreaterEqual(stairs[0]["Max"][0], 5.0)
        self.assertEqual([k["Index"] for k in t["KeepOuts"] if k["Kind"] == "stair"], [0])

    def test_prop_slots_use_catalog_types_and_stay_clear_of_doors_and_keep_outs(self):
        t = self.template
        self.assertGreaterEqual(len(t["PropSlots"]), 1)
        self.assertLessEqual(len(t["PropSlots"]), 5)
        rooms = {r["Id"]: r for r in t["Rooms"]}
        for slot in t["PropSlots"]:
            self.assertEqual(list(slot), ["Id", "Room", "Type", "Position", "Orientation", "Bounds", "History"])
            self.assertIn(slot["Type"], tpl.PROP_TYPES)
            self.assertTrue(set(slot["History"]) <= {"family", "ransacked"} and slot["History"])
            self.assertTrue(inside(rooms[slot["Room"]], slot["Bounds"]))
            for keep in t["KeepOuts"]:
                if keep["Kind"] == "door":
                    self.assertFalse(overlap(slot["Bounds"], keep, 0.6, (0, 2)), "door floor margin below 0.6 m")
                else:
                    self.assertFalse(overlap(slot["Bounds"], keep), keep["Kind"])
            self.assertEqual(slot["Orientation"][1:], [0, 0])
        for first in t["PropSlots"]:
            for second in t["PropSlots"]:
                if first["Id"] < second["Id"]:
                    self.assertFalse(overlap(first["Bounds"], second["Bounds"]))

    def test_prop_types_come_from_the_reviewed_catalog(self):
        from tools.package import interior_catalog
        pilot_types = {t for layout in interior_catalog.PILOT for t in layout[2:]}
        self.assertEqual(set(tpl.PROP_TYPES), pilot_types)
        for name, spec in tpl.PROP_TYPES.items():
            self.assertTrue(set(spec["History"]) <= {"family", "ransacked"})


class ClassRowTests(unittest.TestCase):
    def test_rows_equal_every_house_class_each_once_with_a_disposition_or_reason(self):
        result = standard()
        rows = class_rows(result)
        self.assertEqual(sorted(rows), sorted(CLASSES))
        reasons = set(tpl.REASONS)
        for row in rows.values():
            self.assertEqual(list(row), ["BuildingClass", "Rooms", "Furniture", "Search"])
            for field in ("Rooms", "Furniture", "Search"):
                self.assertTrue(row[field] == "covered" or row[field] in reasons, row)
        self.assertEqual((rows[HOUSE]["Rooms"], rows[HOUSE]["Furniture"], rows[HOUSE]["Search"]),
                         ("covered", "covered", "covered"))
        names = [n for n in result.files if n.startswith("t-")]
        self.assertEqual(len(names), 1)

    def test_every_other_reason_is_reported_per_class(self):
        names = {"unmeasured": "Land_A_Unmeasured", "path": "Land_B_Path", "door": "Land_C_Door",
                 "blocked": "Land_D_Blocked", "low": "Land_E_Low", "nopos": "Land_F_NoPos",
                 "nopoints": "Land_G_NoPoints", "tight": "Land_H_Tight", "capped": "Land_I_Capped"}
        rows = house_rows() + calibration_rows()
        rows += house_rows(names["path"], state="control-failed")
        door_bad = house_rows(names["door"])
        for row in door_bad:
            row["door_run"]["opened"] = 0
        rows += door_bad
        rows += [placement(names["blocked"], grid(XS, ZS, reach=0), index=i) for i in range(2)]
        rows += [placement(names["low"], grid(XS, ZS, clearance=1.0), index=i) for i in range(2)]
        rows += house_rows(names["nopos"]) + house_rows(names["nopoints"])
        rows += house_rows(names["tight"])
        capped = house_rows(names["capped"])
        for row in capped:
            row["stats"]["ray_capped"] = True
        rows += capped
        floor = lambda: container("lootFloor", [point("2.0 0.0 3.0")])
        huge = container("lootFloor", [point("0.0 0.0 0.0", "6.0", "4.0")])
        groups = [HOUSE_GROUP]
        for key in ("unmeasured", "path", "door", "blocked", "low", "nopos", "capped"):
            groups.append(group(names[key], [floor()]))
        groups.append(group(names["tight"], [huge]))
        groups.append(group(names["nopoints"], []))
        proto = proto_xml(groups)
        pos = pos_xml([(HOUSE, "1.0 2.0 3.0", "0"), (names["tight"], "100 0 0", "0"),
                       (names["nopoints"], "200 0 0", "0")])
        classes = list(CLASSES) + list(names.values())
        result = tpl.build([encode(census(rows, classes))], proto, pos, types_bytes=TYPES)
        table = class_rows(result)
        self.assertEqual(sorted(table), sorted(classes))
        self.assertEqual(table[names["unmeasured"]]["Rooms"], "unmeasured")
        self.assertEqual(table[names["path"]]["Rooms"], "path_pending")
        self.assertEqual(table[names["door"]]["Rooms"], "door_pending")
        self.assertEqual(table[names["blocked"]]["Rooms"], "not_enterable")
        self.assertEqual(table[names["low"]]["Rooms"], "unsupported_geometry")
        self.assertEqual(table[names["capped"]]["Rooms"], "unsupported_geometry")
        self.assertEqual(table[names["nopos"]]["Rooms"], "covered")
        self.assertEqual(table[names["nopos"]]["Furniture"], "not_in_mapgrouppos")
        self.assertEqual(table[names["nopoints"]]["Rooms"], "covered")
        self.assertEqual(table[names["nopoints"]]["Search"], "no_ce_points")
        self.assertEqual(table[names["tight"]]["Rooms"], "covered")
        self.assertEqual(table[names["tight"]]["Furniture"], "clearance_failed")
        self.assertEqual(table[names["tight"]]["Search"], "covered")
        for key in ("unmeasured", "low", "capped"):
            row = table[names[key]]
            self.assertEqual(row["Furniture"], row["Rooms"])
            self.assertEqual(row["Search"], row["Rooms"])
        # Measured classes whose rooms lack path/door proof are searched at their vanilla CE points only:
        # a search-only template with no rooms, keep-outs or prop slots, never furniture or infected rooms.
        for key in ("path", "door", "blocked"):
            row = table[names[key]]
            self.assertEqual(row["Furniture"], row["Rooms"])
            self.assertEqual(row["Search"], "covered")
            t = template(result, names[key])
            self.assertEqual((t["Rooms"], t["KeepOuts"], t["PropSlots"]), ([], [], []))
            self.assertTrue(t["SearchSites"])
            self.assertTrue(all(site["Room"] == 0 for site in t["SearchSites"]))
            self.assertTrue(all(inside(t["Box"], {"Min": s["Center"], "Max": s["Center"]}) for s in t["SearchSites"]))
            self.assertTrue(inside({"Min": [-4, -1, -3], "Max": [4, 5, 3]}, t["Box"]))
        self.assertEqual(result.summary["search_only_templates"], 3)
        self.assertFalse(any(r["BuildingClass"] in {names[k] for k in ("path", "door", "blocked")}
                             for r in furnish_rows(result)))
        covered = {n for n, r in table.items() if "covered" in (r["Rooms"], r["Furniture"], r["Search"])}
        self.assertEqual(covered, {HOUSE, names["nopos"], names["nopoints"], names["tight"],
                                   names["path"], names["door"], names["blocked"]})
        built = sorted(load(result, n)["BuildingClass"] for n in result.files if n.startswith("t-"))
        self.assertEqual(built, sorted(covered))

    def test_a_census_without_a_native_frame_verdict_refuses_the_build(self):
        rows = house_rows() + calibration_rows("none")
        with self.assertRaisesRegex(tpl.TemplateError, "rot90"):
            standard(rows=rows)

    def test_a_class_with_stock_points_but_no_template_is_counted_as_search_only_possible(self):
        result = standard(classes=CLASSES + ("Land_Other_Farm",))
        self.assertEqual(class_rows(result)["Land_Other_Farm"]["Rooms"], "unmeasured")
        self.assertEqual(result.summary["search_only_possible"], 1)

    def test_the_template_file_cap_marks_the_rest_over_budget(self):
        names = ["Land_Many_%03d" % i for i in range(4)]
        rows = calibration_rows()
        for name in names:
            rows += house_rows(name)
        pos = pos_xml([(n, "%d 0 0" % (i * 50), "0") for i, n in enumerate(names)] + [(names[3], "999 0 0", "0")])
        proto = proto_xml([group(n, [container("lootFloor", [point("2.0 0.0 3.0")])]) for n in names])
        with mock.patch.object(tpl, "MAX_TEMPLATES", 2):
            result = tpl.build([encode(census(rows, list(CALIBRATION) + names))], proto, pos)
        table = class_rows(result)
        over = [n for n in names if table[n]["Rooms"] == "over_budget"]
        self.assertEqual(len(over), 2)
        self.assertEqual(len([n for n in result.files if n.startswith("t-")]), 2)
        for name in over:
            self.assertEqual((table[name]["Furniture"], table[name]["Search"]), ("over_budget",) * 2)
        # Instance count wins the slots: the class with two instances stays covered.
        self.assertEqual(table[names[3]]["Rooms"], "covered")
        self.assertEqual(tpl.MAX_TEMPLATES, 512)

    def test_the_index_byte_budget_marks_the_rest_over_budget(self):
        # index.json is one pack file under the 32767-byte cap, so its TemplateFiles entries are budgeted.
        names = ["Land_Many_%03d" % i for i in range(4)]
        rows = calibration_rows()
        for name in names:
            rows += house_rows(name)
        pos = pos_xml([(n, "%d 0 0" % (i * 50), "0") for i, n in enumerate(names)] + [(names[3], "999 0 0", "0")])
        proto = proto_xml([group(n, [container("lootFloor", [point("2.0 0.0 3.0")])]) for n in names])
        entry = len('{"File":"t-0000.json","BuildingClass":"Land_Many_000","Sha256":"%s"},' % ("0" * 64))
        with mock.patch.object(tpl, "_index_template_budget", lambda sources: 2 * entry + entry // 2):
            result = tpl.build([encode(census(rows, list(CALIBRATION) + names))], proto, pos)
        table = class_rows(result)
        over = [n for n in names if table[n]["Rooms"] == "over_budget"]
        self.assertEqual(len(over), 2)
        self.assertEqual(len([n for n in result.files if n.startswith("t-")]), 2)
        self.assertEqual(table[names[3]]["Rooms"], "covered")

    def test_a_full_template_budget_fits_the_largest_possible_index(self):
        # Every other list at its contract maximum (16 class, 16 furnish, 64 group chunks), every source
        # pin present and eight census runs: the templates that fit the budget still fit one index file.
        from tools.package import interiors_profile as ip
        sources = {"census-run-%d" % i: "a" * 64 for i in range(8)}
        budget = tpl._index_template_budget(sources)
        name = "Land_" + "X" * 40
        cost = len('{"File":"t-0000.json","BuildingClass":"%s","Sha256":"%s"},' % (name, "0" * 64))
        pins = dict(sources, **{key: "b" * 64 for key in ip.TEMPLATE_SOURCES})
        index = {"SchemaVersion": 2, "Kind": "hc-interior-templates", "WorldName": ip.WORLD, "Build": ip.BUILD,
                 "PackId": "c" * 32, "SourcePin": "d" * 64, "Frame": "rot90", "Provisional": True,
                 "Sources": dict(sorted(pins.items())),
                 "ClassFiles": [{"File": "classes-%03d.json" % i, "Sha256": "e" * 64} for i in range(16)],
                 "TemplateFiles": [{"File": "t-%04d.json" % i, "Sha256": "f" * 64, "BuildingClass": name}
                                   for i in range(budget // cost)],
                 "FurnishFiles": [{"File": "furnish-%03d.json" % i, "Sha256": "e" * 64} for i in range(16)],
                 "GroupFiles": [{"File": "search-groups-%03d.json" % i, "Sha256": "e" * 64} for i in range(64)]}
        self.assertLessEqual(len(ip._compact(index)), tpl.FILE_CAP)
        self.assertGreater(budget // cost, 100)

    def test_furnish_budget_exhaustion_marks_a_class_over_budget(self):
        result = standard(max_furnished=0)
        self.assertEqual(class_rows(result)[HOUSE]["Furniture"], "over_budget")
        self.assertEqual(furnish_rows(result), [])
        self.assertEqual(class_rows(result)[HOUSE]["Rooms"], "covered")


class FurnishTests(unittest.TestCase):
    def test_rows_copy_mapgrouppos_and_only_use_template_slots(self):
        result = standard()
        rows = furnish_rows(result)
        t = template(result)
        slots = {s["Id"]: s for s in t["PropSlots"]}
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["Slot"] for r in rows], [0, 1, 2])
        copied = {(r["Position"][0], r["Position"][1], r["Position"][2], r["Yaw"]) for r in rows}
        self.assertEqual(copied, {(1598.030273, 304.51001, 8970.620117, 15.04), (2000.5, 310.25, 9000.75, -120.5),
                                  (3000.0, 100.0, 4000.0, 90.0)})
        for row in rows:
            self.assertEqual(list(row), ["Slot", "BuildingClass", "Position", "Yaw", "Props", "History"])
            self.assertEqual(row["BuildingClass"], HOUSE)
            self.assertIn(row["History"], ("family", "ransacked"))
            self.assertTrue(row["Props"] and len(row["Props"]) <= 5)
            for prop in row["Props"]:
                self.assertIn(row["History"], slots[prop]["History"])
        self.assertEqual(result.summary["furnish_props"], sum(len(r["Props"]) for r in rows))

    def test_classes_without_a_clearance_passing_template_get_no_rows(self):
        proto = proto_xml([group(HOUSE, [container("lootFloor", [point("0 0 0", "9.0", "4.0")])])])
        result = standard(proto=proto)
        self.assertEqual(class_rows(result)[HOUSE]["Furniture"], "clearance_failed")
        self.assertEqual(furnish_rows(result), [])
        self.assertEqual(len(template(result)["PropSlots"]), 0)

    def test_two_instances_closer_than_the_resolver_radius_are_not_furnished(self):
        pos = pos_xml([(HOUSE, "100 5 100", "0"), (HOUSE, "100.5 5 100", "0"), (HOUSE, "300 5 300", "0")])
        rows = furnish_rows(standard(pos=pos))
        self.assertEqual([r["Position"] for r in rows], [[300.0, 5.0, 300.0]])

    def test_the_total_is_capped_and_towns_come_first(self):
        farm = "Land_Farm_House"
        rows = house_rows() + house_rows(farm) + calibration_rows()
        proto = proto_xml([HOUSE_GROUP, group(farm, [container("lootFloor", [point("2.0 0.0 3.0")])], ("Farm",))])
        entries = [(HOUSE, "%d 0 0" % (i * 10), "0") for i in range(20)] + [(farm, "%d 0 500" % (i * 10), "0")
                                                                          for i in range(20)]
        result = tpl.build([encode(census(rows, [HOUSE, farm] + list(CALIBRATION)))], proto, pos_xml(entries),
                           max_furnished=9)
        out = furnish_rows(result)
        self.assertLessEqual(sum(len(r["Props"]) for r in out), 9)
        self.assertTrue(out)
        self.assertEqual({r["BuildingClass"] for r in out}, {HOUSE})
        self.assertEqual(class_rows(result)[farm]["Furniture"], "over_budget")

    def test_the_fifteen_hundred_prop_cap_is_never_exceeded(self):
        entries = [(HOUSE, "%d 0 %d" % (i % 40 * 10, i // 40 * 10), "0") for i in range(900)]
        result = standard(pos=pos_xml(entries))
        rows = furnish_rows(result)
        self.assertLessEqual(sum(len(r["Props"]) for r in rows), 1500)
        self.assertGreater(sum(len(r["Props"]) for r in rows), 1400)
        self.assertEqual(len({r["Slot"] for r in rows}), len(rows))
        self.assertEqual(len({tuple(r["Position"]) for r in rows}), len(rows))
        for name in result.files:
            if name.startswith("furnish-"):
                self.assertLessEqual(len(load(result, name)["Rows"]), 128)
        with self.assertRaises(tpl.TemplateError):
            standard(max_furnished=1501)

    def test_a_changed_pack_reselects_but_the_same_pack_never_does(self):
        entries = [(HOUSE, "%d 0 %d" % (i % 40 * 10, i // 40 * 10), "0") for i in range(600)]
        first = standard(pos=pos_xml(entries), max_furnished=300)
        again = standard(pos=pos_xml(entries), max_furnished=300)
        changed = standard(pos=pos_xml(entries) + b"<!-- changed pack -->", max_furnished=300)
        self.assertEqual(furnish_rows(first), furnish_rows(again))
        self.assertNotEqual(first.manifest["PackId"], changed.manifest["PackId"])
        self.assertNotEqual([r["Position"] for r in furnish_rows(first)],
                            [r["Position"] for r in furnish_rows(changed)])


class CapTests(unittest.TestCase):
    def test_empty_furnishing_has_no_chunk(self):
        result = standard(max_furnished=0)
        self.assertFalse([n for n in result.files if n.startswith("furnish-")])

    def test_sites_use_only_emitted_group_ids_after_empty_and_over_budget_keys(self):
        from tools.package import search_context as sc
        pr = proto_xml([group(HOUSE, [
            container("loot", [point("0 0 0")], ()),
            container("loot", [point("0 0 0")], ("absent",)),
            container("loot", [point("0 0 0")], ("bulk",)),
            container("lootFactory", [point("0 0 0")]),
            container("lootFloor", [point("0 0 0")]),
            container("lootshelves", [point("1 1 1")], ("books",))])])
        ty = TYPES.replace(b'</types>', b''.join(
            ('<type name="Bulk%d"><nominal>1</nominal><category name="bulk"/></type>' % i).encode()
            for i in range(1025)) + b'</types>')
        result = standard(proto=pr, types_bytes=ty)
        chunks, _ = sc.build_search_groups(pr, ty)
        groups = {g["Id"]: g for c in chunks for g in json.loads(c)["Groups"]}
        sites = template(result)["SearchSites"]
        self.assertEqual({s["Source"] for s in sites}, {"lootFloor", "lootshelves"})
        for site in sites:
            for gid in site["Groups"]:
                self.assertIn(gid, groups)
                self.assertEqual(groups[gid]["Container"], site["Source"])

    def test_without_types_no_unverified_search_groups_are_referenced(self):
        self.assertEqual(template(standard(types_bytes=None))["SearchSites"], [])

    def test_rooms_are_capped_at_sixteen_and_anchors_stay_apart(self):
        cells = []
        for island in range(20):
            base = island * 4.0
            cells += grid([base + 0.5, base + 1.5], [0.5, 1.5])
        rows = [placement(HOUSE, cells, index=i, doors=((-9.0, 1.0, 9.0),), box_min=(0.0, -1.0, 0.0), box_max=(80, 5, 3))
                for i in range(2)] + calibration_rows()
        t = template(standard(rows=rows))
        self.assertEqual(len(t["Rooms"]), 16)
        anchors = [r["Anchor"] for r in t["Rooms"]]
        for i, first in enumerate(anchors):
            for second in anchors[i + 1:]:
                self.assertGreaterEqual(math.dist(first, second), 1.0)

    def test_keep_outs_are_capped_at_thirty_two_and_merging_only_enlarges_them(self):
        doors = [(-3.5 + 0.2 * i, 1.0, 2.9) for i in range(40)]
        points = [point("%d.0 0.0 %d.0" % (i % 6 - 3, i // 6 - 2), "0.3", "1.0") for i in range(30)]
        proto = proto_xml([group(HOUSE, [container("lootFloor", points)])])
        rows = [placement(HOUSE, grid(XS, ZS), index=i, doors=doors) for i in range(2)] + calibration_rows()
        t = template(standard(rows=rows, proto=proto))
        self.assertLessEqual(len(t["KeepOuts"]), 32)
        door_boxes = [k for k in t["KeepOuts"] if k["Kind"] == "door"]
        self.assertTrue(door_boxes)
        for dx, dy, dz in doors:
            if t["Box"]["Min"][0] <= dx <= t["Box"]["Max"][0] and t["Box"]["Min"][2] <= dz <= t["Box"]["Max"][2]:
                self.assertTrue(any(k["Min"][0] <= dx <= k["Max"][0] and k["Min"][2] <= dz <= k["Max"][2]
                                    for k in door_boxes), (dx, dz))
        for kind in ("door", "stair", "ce-point"):
            self.assertEqual([k["Index"] for k in t["KeepOuts"] if k["Kind"] == kind],
                             list(range(len([k for k in t["KeepOuts"] if k["Kind"] == kind]))))

    def test_prop_slots_are_capped_at_five(self):
        big = [placement(HOUSE, grid([x + 0.5 for x in range(-10, 10)], [z + 0.5 for z in range(-10, 10)]),
                         index=i, doors=((10.0, 1.0, 0.0),), box_min=(-10.0, -1.0, -10.0), box_max=(10, 5, 10)) for i in range(2)]
        self.assertEqual(len(template(standard(rows=big + calibration_rows()))["PropSlots"]), 5)

    def test_search_sites_are_capped_at_twenty_four_and_spheres_hold_their_points(self):
        stock = [(x * 20 - 100, z * 20 - 100) for x in range(10) for z in range(10)]
        points = [point("%d 0.5 %d" % (sz, -sx), "0.4", "1.0") for sx, sz in stock]
        proto = proto_xml([group(HOUSE, [container("lootFloor", points)])])
        rows = house_rows(box_min=(-110, -1, -110), box_max=(110, 5, 110)) + calibration_rows()
        result = standard(proto=proto, rows=rows)
        sites = template(result)["SearchSites"]
        self.assertEqual(len(sites), 24)
        for site in sites:
            self.assertTrue(0.25 <= site["Radius"] <= 8.0)
            for index in site["Points"]:
                sx, sz = stock[index]
                converted = pts.stock_to_sampler((sz, 0.5, -sx), "rot90")
                self.assertLessEqual(math.dist(converted, site["Center"]) + 0.4, site["Radius"] + 1e-9)
        self.assertEqual(result.summary["search_points_dropped"], 76)

    def test_close_points_merge_and_the_sphere_radius_never_exceeds_eight_metres(self):
        points = [point("%.1f 0.5 0.0" % (i * 1.5), "0.4", "1.0") for i in range(14)]
        proto = proto_xml([group(HOUSE, [container("lootFloor", points)])])
        rows = house_rows(box_min=(-4, -1, -3), box_max=(4, 5, 25)) + calibration_rows()
        sites = template(standard(proto=proto, rows=rows))["SearchSites"]
        self.assertLess(len(sites), 14)
        self.assertTrue(all(s["Radius"] <= 8.0 for s in sites))
        self.assertEqual(sorted(i for s in sites for i in s["Points"]), list(range(14)))

    def test_class_and_template_files_respect_the_size_and_chunk_limits(self):
        names = ["Land_Bulk_%04d" % i for i in range(400)] + [HOUSE]
        result = tpl.build([encode(census(house_rows() + calibration_rows(), list(CALIBRATION) + names))],
                           PROTO, POS)
        chunks = sorted(n for n in result.files if n.startswith("classes-"))
        self.assertEqual(chunks, ["classes-%03d.json" % i for i in range(len(chunks))])
        self.assertEqual(len(chunks), 3)
        rows = []
        for name in chunks:
            data = load(result, name)
            self.assertEqual(data["SchemaVersion"], 2)
            self.assertLessEqual(len(data["Rows"]), 160)
            rows += [r["BuildingClass"] for r in data["Rows"]]
        self.assertEqual(rows, sorted(set(CALIBRATION) | set(names)))
        for name, data in result.files.items():
            self.assertLessEqual(len(data), 32767, name)
            data.decode("ascii")

    def test_more_than_two_thousand_classes_are_refused(self):
        names = ["Land_X_%04d" % i for i in range(2049)]
        with self.assertRaises(tpl.TemplateError):
            tpl.build([encode(census([], names))], PROTO, POS)


class DeterminismTests(unittest.TestCase):
    def test_two_builds_are_byte_identical_and_provisional(self):
        first, second = standard(), standard()
        self.assertEqual(first.files, second.files)
        self.assertEqual(first.manifest, second.manifest)
        manifest = first.manifest
        self.assertEqual(manifest["SchemaVersion"], 2)
        self.assertTrue(manifest["Provisional"])
        self.assertRegex(manifest["PackId"], r"^[0-9a-f]{32}$")
        self.assertEqual(manifest["Frame"], "rot90")
        for key in ("mapgroupproto", "mapgrouppos", "generator", "census-" + RUN):
            self.assertRegex(manifest["Sources"][key], r"^[0-9a-f]{64}$")
        listed = {entry["File"]: entry["Sha256"] for entry in manifest["Files"]}
        self.assertEqual(sorted(listed), sorted(first.files))
        for name, data in first.files.items():
            self.assertEqual(listed[name], tpl.sha256(data))

    def test_a_changed_source_is_a_new_pack(self):
        base = standard().manifest["PackId"]
        self.assertNotEqual(base, standard(pos=POS + b"<!-- more -->").manifest["PackId"])
        self.assertNotEqual(base, standard(proto=PROTO + b" ").manifest["PackId"])

    def test_the_order_of_census_rows_and_class_lists_does_not_change_the_output(self):
        rows = list(reversed(house_rows() + calibration_rows()))
        a = standard()
        b = standard(classes=tuple(reversed(CLASSES)), rows=rows)
        self.assertEqual(a.files.keys(), b.files.keys())
        self.assertEqual(class_rows(a), class_rows(b))
        self.assertEqual(furnish_rows(a), furnish_rows(b))

    def test_json_is_compact_ascii_with_stable_key_order(self):
        text = standard().files["classes-000.json"].decode("ascii")
        self.assertTrue(text.startswith('{"SchemaVersion":2,"Chunk":0,"Rows":['))
        self.assertTrue(text.endswith("\n"))


class RefusalTests(unittest.TestCase):
    def refuse(self, document=None, proto=PROTO, pos=POS, raw=None, **kwargs):
        data = raw if raw is not None else encode(document)
        with self.assertRaises(tpl.TemplateError):
            tpl.build([data], proto, pos, **kwargs)

    def good(self):
        return census(house_rows() + calibration_rows(), CLASSES)

    def test_census_problems_are_refused(self):
        for key in ("native_run_id", "house_classes"):
            document = self.good()
            del document[key]
            self.refuse(document)
        for bad in ("A" * 32, "a" * 31, 7):
            document = self.good()
            document["native_run_id"] = bad
            self.refuse(document)
        for bad in ([], "x", [7], [HOUSE, HOUSE], ["Land_é"], ["Land X"], ["a" * 129], [""]):
            document = self.good()
            document["house_classes"] = bad
            self.refuse(document)
        document = self.good()
        document["summary"]["complete"] = False
        self.refuse(document)
        document = self.good()
        document["door_phase_contract"] = 1
        self.refuse(document)
        self.refuse(raw=b"not json")
        self.refuse(raw=b"")
        with self.assertRaises(tpl.TemplateError):
            tpl.build([], PROTO, POS)

    def test_a_placement_class_outside_the_house_list_is_refused(self):
        document = self.good()
        document["house_classes"] = list(CALIBRATION)
        self.refuse(document)

    def test_object_house_class_rows_are_accepted(self):
        document = self.good()
        document["house_classes"] = [{"class": name, "scope": 2} for name in CLASSES]
        result = tpl.build([encode(document)], PROTO, POS)
        self.assertEqual(sorted(class_rows(result)), sorted(CLASSES))

    def test_two_censuses_with_one_run_id_are_refused(self):
        data = encode(self.good())
        with self.assertRaises(tpl.TemplateError):
            tpl.build([data, data], PROTO, POS)

    def test_two_censuses_are_merged_and_each_template_names_its_own_run(self):
        other = "b" * 32
        first = census(house_rows() + calibration_rows(), CLASSES)
        second = census(house_rows("Land_Second_House"), CLASSES + ("Land_Second_House",), run_id=other)
        first["house_classes"] = list(CLASSES) + ["Land_Second_House"]
        proto = proto_xml([HOUSE_GROUP, group("Land_Second_House", [container("lootFloor", [point("2.0 0.0 3.0")])])])
        result = tpl.build([encode(first), encode(second)], proto, POS)
        self.assertEqual(template(result, "Land_Second_House")["Evidence"][0]["RunId"], other)
        self.assertEqual(template(result)["Evidence"][0]["RunId"], RUN)
        self.assertIn("census-" + other, result.manifest["Sources"])

    def test_stock_xml_problems_are_refused(self):
        self.refuse(self.good(), proto=b'<!DOCTYPE x><prototype/>')
        self.refuse(self.good(), proto=b"<prototype>")
        self.refuse(self.good(), proto=proto_xml([HOUSE_GROUP, HOUSE_GROUP]))
        self.refuse(self.good(), proto=proto_xml([group(HOUSE, [container("lootFloor", ['<point pos="1 2" range="1" height="1"/>'])])]))
        self.refuse(self.good(), proto=proto_xml([group(HOUSE, [container("lootFloor", ['<point pos="nan 0 0" range="1" height="1"/>'])])]))
        self.refuse(self.good(), pos=b'<!ENTITY x "y"><map/>')
        self.refuse(self.good(), pos=pos_xml([(HOUSE, "1 2", "0")]))
        self.refuse(self.good(), pos=pos_xml([(HOUSE, "1 2 3", "x")]))
        self.refuse(self.good(), pos=b'<map><group name="Land_Test_House" pos="1 2 3" /></map>')

    def test_bad_parameters_are_refused(self):
        for kwargs in ({"min_agreement": 0}, {"min_agreement": 1.5}, {"max_furnished": -1},
                       {"max_furnished": 1501}, {"reach_source": "other"}):
            self.refuse(self.good(), **kwargs)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hc-synthetic-templates-")
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        (self.dir / "census.json").write_bytes(encode(census(house_rows() + calibration_rows(), CLASSES)))
        (self.dir / "mapgroupproto.xml").write_bytes(PROTO)
        (self.dir / "mapgrouppos.xml").write_bytes(POS)
        (self.dir / "types.xml").write_bytes(TYPES)

    def run_cli(self, out, *extra):
        argv = ["build", "--census", str(self.dir / "census.json"), "--proto", str(self.dir / "mapgroupproto.xml"),
                "--pos", str(self.dir / "mapgrouppos.xml"), "--types", str(self.dir / "types.xml"),
                "--out", str(out)] + list(extra)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = tpl.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_build_writes_the_pack_and_prints_the_coverage_summary(self):
        out = self.dir / "out"
        code, text, _err = self.run_cli(out)
        self.assertEqual(code, 0)
        names = sorted(p.name for p in out.iterdir())
        self.assertEqual(names, ["build-manifest.json", "classes-000.json", "furnish-000.json", "t-0000.json"])
        self.assertIn("classes=3", text)
        self.assertIn("rooms covered=1", text)
        self.assertIn("path_pending=2", text)
        self.assertIn("furnish rows=3", text)
        self.assertIn("frame=rot90", text)
        expected = standard()
        for name, data in expected.files.items():
            self.assertEqual((out / name).read_bytes(), data)

    def test_a_non_empty_output_directory_is_refused_and_left_untouched(self):
        out = self.dir / "out"
        out.mkdir()
        (out / "keep.txt").write_text("x")
        code, _text, err = self.run_cli(out)
        self.assertNotEqual(code, 0)
        self.assertIn("not empty", err)
        self.assertEqual([p.name for p in out.iterdir()], ["keep.txt"])

    def test_an_empty_existing_directory_is_accepted(self):
        out = self.dir / "empty"
        out.mkdir()
        self.assertEqual(self.run_cli(out)[0], 0)

    def test_output_inside_the_checkout_or_over_a_file_is_refused(self):
        inside_repo = ROOT / "hc-synthetic-template-output-must-not-exist"
        code, _text, err = self.run_cli(inside_repo)
        self.assertNotEqual(code, 0)
        self.assertFalse(inside_repo.exists())
        target = self.dir / "file"
        target.write_text("x")
        self.assertNotEqual(self.run_cli(target)[0], 0)

    def test_a_refused_build_writes_nothing(self):
        (self.dir / "mapgrouppos.xml").write_bytes(b"<map>")
        out = self.dir / "out"
        code, _text, err = self.run_cli(out)
        self.assertNotEqual(code, 0)
        self.assertFalse(out.exists())

    def test_a_missing_input_is_a_refusal_not_a_traceback(self):
        out = self.dir / "out"
        (self.dir / "census.json").unlink()
        code, _text, err = self.run_cli(out)
        self.assertNotEqual(code, 0)
        self.assertFalse(out.exists())

    def test_parameters_reach_the_build(self):
        code, text, _err = self.run_cli(self.dir / "out", "--max-furnished", "0")
        self.assertEqual(code, 0)
        self.assertIn("furnish rows=0", text)


if __name__ == "__main__":
    unittest.main()


class CensusAdapterTests(unittest.TestCase):
    """Synthetic T1-shaped placement config; no runtime observations."""

    def native(self, name=HOUSE, run=RUN):
        row = placement(name, grid(XS, ZS))
        row['house'] = {'model': 'synthetic_model', 'door_count': 1,
                        'doors': [[4.0, 1.0, 0.0]], 'door_selections': [['door1', 4.0, 1.0, 0.0]],
                        'selection_total': 1}
        doc = census([row], [], run_id=run)
        del doc['house_classes']
        return doc

    def test_real_t1_shape_uses_canonical_house_rows(self):
        loaded = tpl.load_census(encode(self.native()))
        self.assertEqual(loaded['classes'], [HOUSE])
        self.assertEqual(loaded['houses'][0]['model'], 'synthetic_model')

    def test_t1_validation_and_model_frame_bound_are_enforced(self):
        for change in (lambda r: r['house'].update(door_count=2),
                       lambda r: r.update(box_max=[513, 5, 3]),
                       lambda r: r['house'].update(doors=[[0, 0, -513]]),
                       lambda r: r['house'].update(door_selections=[['door1', 0, 513, 0]]),
                       lambda r: r.update(hits=[[513, 0, 0, 2, 1, 1]])):
            doc = self.native()
            change(doc['placements'][0])
            with self.subTest(change=change), self.assertRaises(ValueError):
                tpl.load_census(encode(doc))

    def test_missing_house_is_not_a_synthetic_fallback(self):
        doc = self.native()
        del doc['placements'][0]['house']
        with self.assertRaises(ValueError):
            tpl.load_census(encode(doc))

    def test_conflicting_class_values_are_refused_within_one_run(self):
        doc = self.native()
        other = copy.deepcopy(doc['placements'][0])
        other['house']['model'] = 'conflicting_model'
        doc['placements'].append(other)
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            tpl.load_census(encode(doc))

    def test_collection_merges_batches_against_full_stock_denominator(self):
        first = self.native()
        second = self.native('Land_Second_House', 'b' * 32)
        proto = proto_xml([HOUSE_GROUP, group('Land_Second_House', []), group('Land_Unmeasured', [])])
        docs, names = tpl.load_censuses([encode(first), encode(second)], proto)
        self.assertEqual(names, sorted([HOUSE, 'Land_Second_House', 'Land_Unmeasured']))
        self.assertEqual(len(docs), 2)
        empty, same_names = tpl.load_censuses([], proto)
        self.assertEqual(empty, [])
        self.assertEqual(names, same_names)

    def test_collection_refuses_conflicting_class_values_across_runs(self):
        first = self.native()
        second = self.native(run='b' * 32)
        second['placements'][0]['box_max'][1] += 1
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            tpl.load_censuses([encode(first), encode(second)], PROTO)

    def test_missing_door_phase_evidence_keeps_valid_config_for_pending_measurement(self):
        for absent in (None, []):
            doc = self.native()
            doc['placements'][0]['door_run'] = absent
            loaded = tpl.load_census(encode(doc))
            self.assertEqual(loaded['classes'], [HOUSE])
