"""Step-file builder of the dev-only client driver; offline schema checks only."""
import copy
import io
import json
import math
import re
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.testing import driver_script as ds


def _action_script(name, args=None):
    step = {"id": "s01", "kind": "action", "name": name, "args": args or {}, "timeout_s": 60}
    return {"version": 1, "run_id": "t1", "steps": [step]}


class DriverScriptTests(unittest.TestCase):
    def test_default_route_validates_and_covers_the_contract(self):
        script = ds.build_route(list(ds.PHASES))
        ds.validate_script(script)
        kinds = {step["kind"] for step in script["steps"]}
        self.assertEqual(kinds, set(ds.KINDS))
        commands = {step["cmd"] for step in script["steps"] if step["kind"] == "admin"}
        for fixture in ds.FIXTURES:
            self.assertIn(fixture, commands)
        names = {step["name"] for step in script["steps"] if step["kind"] == "action"}
        self.assertEqual(names, set(ds.ACTION_ARGS) - set(ds.UNSUPPORTED_ACTIONS))

    def test_initial_spawn_route_uses_nearest_legs_and_measured_lengths(self):
        script, notes = ds.build_plan(list(ds.PHASES))
        walks = [step for step in script["steps"] if step["kind"] == "walk"
                 and not notes[step["id"]].startswith("ai_clear:")]
        self.assertEqual([notes[s["id"]] for s in walks],
                         [ds.AI_SITE, ds.TOWN, ds.AI_SITE, ds.ZONE, ds.SCENE, ds.FOREST])
        first = walks[0]
        self.assertLess(math.dist(ds.SPAWN_XZ, first["to"]), 100)
        distance = max(math.dist(origin, first["to"])
                       for origin in (*ds.INITIAL_SPAWN_CANDIDATES_XZ, ds.SPAWN_XZ))
        self.assertEqual(first["timeout_s"], ds._timeout_for(distance + 150, first["gait"]))

    def test_initial_spawn_candidates_match_server_source(self):
        source = (ds.ROOT / "mods/HollowCountryTest/scripts/5_Mission/HCDriverInitialSpawn.c").read_text(
            encoding="utf-8")
        block = re.search(r"ref array<vector> candidates = \{(.*?)\};", source, re.S)
        self.assertIsNotNone(block)
        points = [tuple(map(float, point.split())) for point in re.findall(r'"([^"\n]+)"', block[1])]
        self.assertEqual(ds.INITIAL_SPAWN_CANDIDATES_XZ, tuple((x, z) for x, _, z in points))
        fallback = re.search(r"return Vector\((\d+), GetGame\(\).SurfaceY\(\d+, \d+\), (\d+)\);", source)
        self.assertIsNotNone(fallback)
        self.assertEqual(ds.SPAWN_XZ, tuple(map(float, fallback.groups())))

    def test_first_walk_budgets_all_spawn_points_and_keeps_uncertainty_margin(self):
        for phases, margin in ((["walk_ai"], 0), (["join", "walk_ai"], 150),
                               (["walk_town"], 0), (["ai_clear"], 0)):
            with self.subTest(phases=phases):
                first = next(s for s in ds.build_route(phases)["steps"] if s["kind"] == "walk")
                distance = max(math.dist(origin, first["to"])
                               for origin in (*ds.INITIAL_SPAWN_CANDIDATES_XZ, ds.SPAWN_XZ))
                self.assertEqual(first["timeout_s"], ds._timeout_for(distance + margin, "jog"))

    def test_initial_route_budgets_approach_and_route_legs(self):
        points = ds.resolve_route(ds.TOWN)
        distance = max(math.dist(origin, points[0])
                       for origin in (*ds.INITIAL_SPAWN_CANDIDATES_XZ, ds.SPAWN_XZ))
        distance += sum(math.dist(a, b) for a, b in zip(points, points[1:]))
        for uncertain in (False, True):
            b = ds._Builder()
            if uncertain:
                b.add("menu", name="map", seconds=4)
            b.route(ds.TOWN)
            self.assertEqual(b.steps[-1]["timeout_s"], min(
                3600, ds._timeout_for(distance + (150 if uncertain else 0), "jog") + 30 * len(points)))
            b.walk(ds.ZONE)
            self.assertEqual(b.steps[-1]["timeout_s"], ds._timeout_for(
                math.dist(points[-1], ds.resolve_waypoint(ds.ZONE)), "jog"))

    def test_initial_budget_includes_fallback_and_retains_timeout_cap(self):
        # The fallback is farthest for this target; the shortlist alone underbudgets it.
        with patch.object(ds, "resolve_waypoint", return_value=(4000.0, 2500.0)):
            b = ds._Builder()
            b.walk(ds.AI_SITE)
            self.assertEqual(b.steps[-1]["timeout_s"], ds._timeout_for(2500, "jog"))
        with patch.object(ds, "resolve_waypoint", return_value=(15000.0, 15000.0)), \
                patch.object(ds, "resolve_route", return_value=[(15000.0, 15000.0), (15010.0, 15010.0)]):
            for kind in ("walk", "route"):
                b = ds._Builder()
                getattr(b, kind)(ds.AI_SITE)
                self.assertEqual(b.steps[-1]["timeout_s"], 3600)

    def test_returning_to_fallback_does_not_restart_initial_budget(self):
        b = ds._Builder()
        b.walk(ds.AI_SITE)
        with patch.object(ds, "resolve_waypoint", return_value=ds.SPAWN_XZ):
            b.walk(ds.AI_SITE)
        b.walk(ds.TOWN)
        self.assertEqual(b.steps[-1]["timeout_s"], ds._timeout_for(
            math.dist(ds.SPAWN_XZ, ds.resolve_waypoint(ds.TOWN)), "jog"))

    def test_ai_clear_plan_uses_existing_steps_both_modes_and_one_respawn(self):
        script, notes = ds.build_plan(["fixtures", "ai_clear"])
        steps = script["steps"]
        clear = [s for s in steps if s.get("cmd") == "fx_site_clear"]
        self.assertEqual([s["value"] for s in clear], ["0", "1"])
        self.assertEqual(sum(s["kind"] == "respawn" for s in steps), 1)
        self.assertEqual(sum(s.get("cmd") == "fx_die" for s in steps), 1)
        self.assertEqual(ds.PHASES[-2:], ("ai_clear", "idle"))
        self.assertEqual(len(ds.phase_index()["ai_clear"]["fixture:fx_site_clear"]), 2)
        self.assertTrue(any("reach=bounded-foot" in note for note in notes.values()))
        for clear_step in clear:
            following = steps[steps.index(clear_step) + 1]
            self.assertEqual((following["kind"], following["seconds"]), ("stand", 200))
        self.assertTrue(any(s["kind"] == "stand" and s["seconds"] == 120 for s in steps))

    def test_ai_clear_prefers_authored_held_guard_and_short_second_site(self):
        targets = ds.ai_clear_targets(ds.SPAWN_XZ)
        self.assertEqual([row[2] for row in targets], ["zone:balota", ds.AI_SITE])
        self.assertEqual(targets[0][3], (6652.3, 2907.0))
        self.assertEqual(ds.ai_clear_targets((15000, 1000)), [])
        script, notes = ds.build_plan(["ai_clear"])
        self.assertEqual([s["to"] for s in script["steps"] if s["kind"] == "walk"],
                         [list(row[3]) for row in targets])
        self.assertTrue(all(s["arrive_m"] <= 150 for s in script["steps"] if s["kind"] == "walk"))

    def test_phase_ranges_describe_combined_route_not_standalone_lengths(self):
        ranges = {}
        script, _ = ds.build_plan(list(ds.PHASES), phase_ranges=ranges)
        self.assertEqual(ranges["join"][0], 0)
        self.assertEqual(ranges["idle"][1], len(script["steps"]))
        for previous, following in zip(ds.PHASES, ds.PHASES[1:]):
            self.assertEqual(ranges[previous][1], ranges[following][0])
        start, end = ranges["combat"]
        self.assertEqual([s["kind"] for s in script["steps"][start:end]], ["combat"])
        alone = ds.build_route(["combat"])
        self.assertEqual([s["kind"] for s in alone["steps"]], ["walk", "combat"])

    def test_every_phase_builds_alone(self):
        for phase in ds.PHASES:
            script = ds.build_route([phase])
            ds.validate_script(script)
            self.assertTrue(script["steps"])

    def test_phase_order_follows_the_request(self):
        forward = ds.build_route(["join", "idle"])
        backward = ds.build_route(["idle", "join"])
        self.assertEqual(forward["steps"][0]["kind"], "wait")
        self.assertEqual(backward["steps"][-1]["kind"], "action")
        self.assertEqual(backward["steps"][-1]["name"], "earplugs")

    def test_unknown_phase_and_empty_request_refused(self):
        with self.assertRaises(ds.ScriptError):
            ds.build_route(["join", "teleport"])
        with self.assertRaises(ds.ScriptError):
            ds.build_route([])

    def test_unknown_kind_refused(self):
        script = ds.build_route(["join"])
        script["steps"][0]["kind"] = "teleport"
        with self.assertRaises(ds.ScriptError):
            ds.validate_script(script)

    def test_unknown_field_refused(self):
        for mutate in (
            lambda s: s["steps"][0].update(extra=1),
            lambda s: s.update(extra=1),
        ):
            script = ds.build_route(["join"])
            mutate(script)
            with self.assertRaises(ds.ScriptError):
                ds.validate_script(script)

    def test_unknown_action_name_and_args_refused(self):
        with self.assertRaises(ds.ScriptError):
            ds.validate_script(_action_script("explode"))
        with self.assertRaises(ds.ScriptError):
            ds.validate_script(_action_script("craft", {"item1": "CamoNet", "item2": "KitchenKnife", "x": "y"}))
        with self.assertRaises(ds.ScriptError):
            ds.validate_script(_action_script("craft", {"item1": "CamoNet"}))

    def test_every_contract_action_kind_is_buildable(self):
        for name in ("craft", "search", "take", "mount", "close_door", "salvage", "melee", "fire",
                     "flip", "radio", "pickup_forage"):
            self.assertIn(name, ds.ACTION_ARGS)
            args = dict(ds.DEFAULT_ACTION_ARGS.get(name, {}))
            ds.validate_script(_action_script(name, args))
        self.assertEqual(set(ds.UNSUPPORTED_ACTIONS), {"melee", "fire"})

    def test_teleport_admin_commands_refused(self):
        for command in ("tp", "tpto", "teleport", "goto", "tphere"):
            script = {"version": 1, "run_id": "t1", "steps": [
                {"id": "s01", "kind": "admin", "cmd": command, "value": ""}]}
            with self.assertRaises(ds.ScriptError):
                ds.validate_script(script)

    def test_admin_value_must_be_empty_or_digits(self):
        good = {"version": 1, "run_id": "t1", "steps": [
            {"id": "s01", "kind": "admin", "cmd": "status", "value": "12"}]}
        ds.validate_script(good)
        bad = copy.deepcopy(good)
        bad["steps"][0]["value"] = "twelve"
        with self.assertRaises(ds.ScriptError):
            ds.validate_script(bad)

    def test_walk_targets_and_gait_checked(self):
        step = {"id": "s01", "kind": "walk", "to": [3900.0, 2330.0], "gait": "jog",
                "arrive_m": 5, "timeout_s": 600}
        script = {"version": 1, "run_id": "t1", "steps": [step]}
        ds.validate_script(script)
        for key, value in (("gait", "fly"), ("to", [1.0]), ("to", [-5.0, 10.0]), ("arrive_m", 0)):
            broken = copy.deepcopy(script)
            broken["steps"][0][key] = value
            with self.assertRaises(ds.ScriptError):
                ds.validate_script(broken)

    def test_waypoint_sources_resolve_to_repo_data(self):
        site = ds.resolve_waypoint(ds.AI_SITE)
        zone = ds.resolve_waypoint(ds.ZONE)
        town = ds.resolve_waypoint(ds.TOWN)
        self.assertEqual(zone, ds.ZONE_CENTER)
        for x, z in (site, zone, town):
            self.assertTrue(0 < x < ds.WORLD_SIZE and 0 < z < ds.WORLD_SIZE)
        surveys = json.loads((ds.MISSION / "travel" / "route-surveys.json").read_text(encoding="utf-8"))
        shelter = surveys["existing_shelters"][0]
        ident = shelter.get("id") or shelter.get("name")
        with self.assertRaises(ds.ScriptError):
            ds.resolve_waypoint("shelter:" + str(ident))
        with tempfile.TemporaryDirectory() as directory:
            rpt = Path(directory) / "server.RPT"
            rpt.write_text("[HollowCountry] V2 shelter placed name=Drozhino Hay Refuge alternate=0 pick=1 point=100 20 300\n")
            self.assertEqual(ds.resolve_waypoint("shelter:" + str(ident), rpt), (100.0, 300.0))

    def test_scene_waypoint_resolves_to_scene_chain_data(self):
        x, z = ds.resolve_waypoint(ds.SCENE)
        self.assertTrue(0 < x < ds.WORLD_SIZE and 0 < z < ds.WORLD_SIZE)
        with self.assertRaises(ds.ScriptError):
            ds.resolve_waypoint("scene:no-such-chain")

    def test_phase_index_names_the_steps_that_reach_each_counter(self):
        index = ds.phase_index()
        self.assertEqual(tuple(index), ds.PHASES)
        script = ds.build_route(list(ds.PHASES))
        ids = {step["id"] for step in script["steps"]}
        for tokens in index.values():
            for found in tokens.values():
                self.assertTrue(set(found) <= ids)
        for fixture in ds.FIXTURES:
            self.assertTrue(any("fixture:" + fixture in tokens for tokens in index.values()), fixture)
        for token in ("menu:admin", "action:craft", "action:mount", "action:salvage", "action:flip", "action:write",
                      "admin:forage", "admin:snapshot"):
            self.assertTrue(any(token in tokens for tokens in index.values()), token)

    def test_bad_waypoint_sources_refused(self):
        for source in ("site:no-such-site", "zone:no-such-zone", "shelter:no-such", "cell:1", "nocolon", 7):
            with self.assertRaises(ds.ScriptError):
                ds.resolve_waypoint(source)

    def test_default_route_walks_only_to_resolved_waypoints(self):
        script, notes = ds.build_plan(list(ds.PHASES))
        walks = [step for step in script["steps"] if step["kind"] == "walk"
                 and not notes[step["id"]].startswith("ai_clear:")]
        self.assertEqual(len(walks), 6)
        self.assertTrue(any(notes[step["id"]].startswith("scene:") for step in walks))
        for step in walks:
            self.assertIn(step["id"], notes)
            self.assertEqual(tuple(step["to"]), ds.resolve_waypoint(notes[step["id"]]))

    def test_build_is_deterministic(self):
        self.assertEqual(ds.build_route(list(ds.PHASES)), ds.build_route(list(ds.PHASES)))

    def test_write_and_validate_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "acceptance" / "client_driver.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ds.main(["write", str(path), "--route", "default"]), 0)
                self.assertEqual(ds.main(["validate", str(path)]), 0)
            ds.validate_script(json.loads(path.read_text(encoding="utf-8")))
            path.write_text(json.dumps({"version": 1, "run_id": "t1", "steps": [
                {"id": "s01", "kind": "nope"}]}), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ds.main(["validate", str(path)]), 1)


    def test_r3_route_covers_the_six_smoke_categories_on_foot(self):
        script, _ = ds.build_r3()
        ds.validate_script(script)
        menus = [step["name"] for step in script["steps"] if step["kind"] == "menu"]
        zones = [step["zone"] for step in script["steps"] if step["kind"] == "enter"]
        self.assertEqual(menus, ["map", "inventory", "admin"])  # the M map also opens the group controls
        self.assertEqual(zones, ["site", "mission"])
        self.assertFalse({"admin", "action", "walk"} & {step["kind"] for step in script["steps"]})
        self.assertEqual(ds.build_r3(), ds.build_r3())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "client_driver.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ds.main(["write", str(path), "--route", "r3"]), 0)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), script)

    def test_site_candidates_are_patrol_anchors_at_the_default_radius(self):
        sites = ds.site_candidates()
        self.assertEqual(len(sites) % 3, 0)
        self.assertLessEqual(len(sites) // 3, ds.MAX_SITE_CANDIDATES)
        anchors = {ds.resolve_waypoint("site:" + row["Id"]) for row in ds._load("ai/sites.json")["Sites"]
                   if row.get("Kind") == "patrol" and row.get("Waypoints")}
        for index in range(0, len(sites), 3):
            self.assertIn((sites[index], sites[index + 1]), anchors)
            self.assertGreaterEqual(sites[index + 2], ds.SITE_RADIUS_FLOOR)

    def test_enter_steps_checked(self):
        good = {"id": "s01", "kind": "enter", "zone": "site", "sites": [6564.47, 2551.96, 1500.0],
                "gait": "jog", "hold_s": 60, "timeout_s": 600}
        ds.validate_step(good)
        bad = [dict(good, zone="town"), dict(good, sites=[1.0, 2.0]), dict(good, sites=[]),
               dict(good, sites=[1.0, 2.0, 10.0]), dict(good, sites=[99999.0, 2.0, 1500.0]),
               dict(good, hold_s=5), dict(good, hold_s=600), dict(good, timeout_s=10), dict(good, gait="crawl"),
               dict(good, zone="mission"), dict(good, to=[1, 2])]
        for step in bad:
            with self.assertRaises(ds.ScriptError):
                ds.validate_step(step)
        mission = {key: value for key, value in good.items() if key != "sites"}
        ds.validate_step(dict(mission, zone="mission"))
        with self.assertRaises(ds.ScriptError):
            ds.validate_step(mission)  # a site step needs its candidates
        self.assertEqual(ds.step_token(dict(mission, zone="mission"), {}), "enter:mission")

    def test_route_steps_follow_site_waypoints_and_are_checked(self):
        script, notes = ds.build_plan(["walk_town"])
        routes = [step for step in script["steps"] if step["kind"] == "route"]
        self.assertEqual(len(routes), 1)
        source = notes[routes[0]["id"]]
        self.assertEqual(ds.step_token(routes[0], notes), "route:" + source)
        points = ds.resolve_route(source)
        self.assertEqual(routes[0]["points"], [value for point in points for value in point])
        good = {"id": "s01", "kind": "route", "points": [6790.0, 2580.0, 6659.0, 2575.0], "gait": "jog",
                "arrive_m": 5, "timeout_s": 300}
        ds.validate_step(good)
        bad = [dict(good, points=[6790.0, 2580.0]), dict(good, points=[6790.0, 2580.0, 1.0]),
               dict(good, points=[99999.0, 2580.0, 6659.0, 2575.0]), dict(good, points=[1.0] * 130),
               dict(good, arrive_m=1), dict(good, timeout_s=5), dict(good, gait="crawl"), dict(good, to=[1, 2])]
        for step in bad:
            with self.assertRaises(ds.ScriptError):
                ds.validate_step(step)
        for source in ("zone:balota-cf3bbed7", "site:no-such-site"):
            with self.assertRaises(ds.ScriptError):
                ds.resolve_route(source)

    def test_combat_steps_are_bounded_and_never_fire(self):
        script, notes = ds.build_plan(list(ds.PHASES))
        combats = [step for step in script["steps"] if step["kind"] == "combat"]
        self.assertTrue(combats)
        self.assertEqual(ds.step_token(combats[0], notes), "combat")
        self.assertIn("fire=unsupported", ds.describe(combats[0], notes))
        good = {"id": "s01", "kind": "combat", "range_m": 60, "timeout_s": 180}
        ds.validate_step(good)
        bad = [dict(good, range_m=5), dict(good, range_m=500), dict(good, timeout_s=5),
               dict(good, timeout_s=7200), dict(good, fire=True), dict(good, range_m="60")]
        for step in bad:
            with self.assertRaises(ds.ScriptError):
                ds.validate_step(step)

    def test_climb_schema_and_bounds(self):
        good = {"id": "s01", "kind": "climb", "range_m": 100, "hold_s": 90, "timeout_s": 360}
        ds.validate_step(good)
        for key in ("range_m", "hold_s", "timeout_s"):
            missing = dict(good)
            del missing[key]
            with self.subTest(missing=key), self.assertRaises(ds.ScriptError):
                ds.validate_step(missing)
            for value in (True, "90", None, float("nan"), float("inf"), 0):
                with self.subTest(key=key, value=value), self.assertRaises(ds.ScriptError):
                    ds.validate_step(dict(good, **{key: value}))
        for fields in ({"range_m": 151}, {"hold_s": 601}, {"timeout_s": 1801},
                       {"timeout_s": 90}, {"timeout_s": 89}, {"position": [1, 2]}):
            with self.subTest(fields=fields), self.assertRaises(ds.ScriptError):
                ds.validate_step(dict(good, **fields))
        self.assertEqual(ds.step_token(good, {}), "climb")
        self.assertIn("hold_s=90", ds.describe(good, {}))

    def test_town_climb_follows_combat_and_noise(self):
        for phases in (["walk_town"], list(ds.PHASES)):
            steps = ds.build_route(phases)["steps"]
            indices = [i for i, step in enumerate(steps) if step["kind"] == "climb"]
            self.assertEqual(len(indices), 1)
            i = indices[0]
            self.assertEqual(steps[i - 2]["kind"], "combat")
            self.assertEqual(steps[i - 1]["kind"], "admin")
            self.assertEqual(steps[i - 1]["cmd"], "fx_shoot_held")
            self.assertEqual(steps[i]["hold_s"], 90)
            self.assertEqual(steps[i]["range_m"], 100)
            ds.validate_script({"version": 1, "run_id": "t1", "steps": steps})
        b = ds._Builder()
        b.add("climb", range_m=100, hold_s=90, timeout_s=360)
        self.assertTrue(b.uncertain)

    def test_cellar_schema_and_bounds(self):
        good = {"id": "s01", "kind": "cellar", "classes_from": ["Land_House_1W01"],
                "range_m": 100, "hold_s": 20, "timeout_s": 240}
        ds.validate_step(good)
        for key in ("classes_from", "range_m", "hold_s", "timeout_s"):
            missing = dict(good)
            del missing[key]
            with self.subTest(missing=key), self.assertRaises(ds.ScriptError):
                ds.validate_step(missing)
        for classes in (None, "cellars/classes.json", [], [True], ["bad class"], [""],
                        ["A" * 65], ["House", "House"], ["House%d" % i for i in range(65)]):
            with self.subTest(classes=classes), self.assertRaises(ds.ScriptError):
                ds.validate_step(dict(good, classes_from=classes))
        for key, low, high in (("range_m", 5, 150), ("hold_s", 1, 600), ("timeout_s", 10, 1800)):
            for value in (True, None, "20", float("nan"), float("inf"), low - 1, high + 1):
                with self.subTest(key=key, value=value), self.assertRaises(ds.ScriptError):
                    ds.validate_step(dict(good, **{key: value}))
        for fields in ({"timeout_s": 20}, {"timeout_s": 19}, {"position": [1, 2]}, {"classes": []}):
            with self.subTest(fields=fields), self.assertRaises(ds.ScriptError):
                ds.validate_step(dict(good, **fields))
        for value in (5, 150):
            ds.validate_step(dict(good, range_m=value))
        ds.validate_step(dict(good, hold_s=1, timeout_s=10))
        ds.validate_step(dict(good, hold_s=600, timeout_s=1800,
                              classes_from=["House%d" % i for i in range(64)]))
        self.assertEqual(ds.step_token(good, {}), "cellar")
        self.assertIn("classes=1", ds.describe(good, {}))

    def test_cellar_classes_are_embedded_from_mission_data(self):
        from unittest.mock import patch
        expected = [row["BuildingClass"] for row in json.loads(
            (ds.MISSION / "cellars" / "classes.json").read_text())["Classes"]]
        self.assertEqual(ds.cellar_classes(), expected)
        self.assertEqual(len(expected), 28)
        # A different source changes the step: no class names are baked into the builder.
        with tempfile.TemporaryDirectory() as directory:
            mission = Path(directory)
            (mission / "cellars").mkdir()
            source = mission / "cellars" / "classes.json"
            source.write_text(json.dumps({"Classes": [{"BuildingClass": "Land_TestHouse"}]}))
            with patch.object(ds, "MISSION", mission):
                self.assertEqual(ds.cellar_classes(), ["Land_TestHouse"])
            source.write_text(json.dumps({"Classes": [{"BuildingClass": "bad class"}]}))
            with patch.object(ds, "MISSION", mission), self.assertRaises(ds.ScriptError):
                ds.cellar_classes()
        for phases in (["walk_town"], list(ds.PHASES)):
            steps = ds.build_route(phases)["steps"]
            indices = [i for i, step in enumerate(steps) if step["kind"] == "cellar"]
            self.assertEqual(len(indices), 1)
            i = indices[0]
            self.assertEqual(steps[i - 1]["kind"], "climb")
            self.assertTrue(any(step["kind"] == "search_site" for step in steps[:i]))
            self.assertEqual(steps[i]["classes_from"], expected)
            self.assertEqual((steps[i]["hold_s"], steps[i]["timeout_s"]), (20, 240))
        builder = ds._Builder()
        builder.add("cellar", classes_from=expected, range_m=100, hold_s=20, timeout_s=240)
        self.assertTrue(builder.uncertain)

    def test_loot_steps_are_bounded(self):
        script, notes = ds.build_plan(list(ds.PHASES))
        loots = [step for step in script["steps"] if step["kind"] == "loot"]
        self.assertTrue(loots)
        self.assertEqual(ds.step_token(loots[0], notes), "loot")
        good = {"id": "s01", "kind": "loot", "range_m": 40, "max_items": 4, "timeout_s": 300}
        ds.validate_step(good)
        bad = [dict(good, range_m=2), dict(good, range_m=200), dict(good, max_items=0),
               dict(good, max_items=11), dict(good, max_items=2.5), dict(good, max_items=True),
               dict(good, timeout_s=5), dict(good, spawn="Apple")]
        for step in bad:
            with self.assertRaises(ds.ScriptError):
                ds.validate_step(step)

    def test_survive_steps_have_a_known_mode(self):
        script, notes = ds.build_plan(list(ds.PHASES))
        survives = [step for step in script["steps"] if step["kind"] == "survive"]
        self.assertTrue(survives)
        self.assertEqual(ds.step_token(survives[0], notes), "survive")
        good = {"id": "s01", "kind": "survive", "mode": "need", "timeout_s": 120}
        ds.validate_step(good)
        ds.validate_step(dict(good, mode="always"))
        bad = [dict(good, mode="heal"), dict(good, mode=None), dict(good, timeout_s=5),
               dict(good, timeout_s=900), dict(good, health=100)]
        for step in bad:
            with self.assertRaises(ds.ScriptError):
                ds.validate_step(step)

    def test_vehicle_steps_are_bounded(self):
        script, notes = ds.build_plan(list(ds.PHASES))
        vehicles = [step for step in script["steps"] if step["kind"] == "vehicle"]
        self.assertTrue(vehicles)
        self.assertEqual(ds.step_token(vehicles[0], notes), "vehicle")
        good = {"id": "s01", "kind": "vehicle", "range_m": 40, "seconds": 8, "throttle": 0.5, "timeout_s": 180}
        ds.validate_step(good)
        bad = [dict(good, range_m=200), dict(good, seconds=0), dict(good, seconds=120),
               dict(good, throttle=0), dict(good, throttle=1.5), dict(good, throttle=True),
               dict(good, timeout_s=10), dict(good, fuel=1.0)]
        for step in bad:
            with self.assertRaises(ds.ScriptError):
                ds.validate_step(step)


    def test_playing_phases_run_alone_and_in_the_default_route(self):
        def tokens_of(phases):
            script, notes = ds.build_plan(phases)
            return [ds.step_token(step, notes) for step in script["steps"]]
        tokens, index = tokens_of(list(ds.PHASES)), ds.phase_index()
        # The default route plays each kind once, in its own phase, without extra walks or fixtures.
        self.assertEqual(sorted(index["combat"]), ["combat"])
        self.assertEqual(sorted(index["loot"]), ["loot"])
        self.assertEqual(sorted(index["vehicle"]), ["vehicle"])
        self.assertEqual(sorted(index["survive"]), ["survive"])
        self.assertLess(tokens.index("action:flip"), tokens.index("vehicle"))
        self.assertLess(tokens.index("loot"), tokens.index("survive"))
        alone = tokens_of(["join", "combat", "idle"])
        self.assertIn("walk:" + ds.TOWN, alone)
        alone = tokens_of(["join", "vehicle", "idle"])
        self.assertLess(alone.index("admin:fx_car_side"), alone.index("action:flip"))
        self.assertLess(alone.index("action:flip"), alone.index("vehicle"))


    def test_extra_step_schemas_and_bounds(self):
        steps = [
            {"kind": "search_site", "site": "police-chernogorsk", "timeout_s": 240},
            {"kind": "take_lead", "timeout_s": 180},
            {"kind": "raise", "range_min_m": 45, "range_max_m": 75, "seconds": 3, "timeout_s": 180},
            {"kind": "hold_ring", "to": [5264.47, 2551.96], "hold_s": 120, "timeout_s": 900},
            {"kind": "respawn", "timeout_s": 180},
        ]
        for step in steps:
            step["id"] = "s01"
            ds.validate_step(step)
            for invalid in (dict(step, timeout_s=True), dict(step, timeout_s=0),
                            dict(step, timeout_s=float("nan")), dict(step, position=[1, 2])):
                with self.subTest(invalid=invalid), self.assertRaises(ds.ScriptError):
                    ds.validate_step(invalid)
            missing = dict(step)
            del missing["timeout_s"]
            with self.assertRaises(ds.ScriptError):
                ds.validate_step(missing)
        invalid_steps = [dict(steps[0], site="missing"), dict(steps[0], site=True),
                         dict(steps[2], range_min_m=40), dict(steps[2], range_max_m=81),
                         dict(steps[2], range_min_m=75), dict(steps[2], seconds=0),
                         dict(steps[2], seconds=30, timeout_s=20),
                         dict(steps[3], to=[1]), dict(steps[3], to=[True, 1]),
                         dict(steps[3], hold_s=0), dict(steps[3], timeout_s=120)]
        for invalid in invalid_steps:
            with self.subTest(invalid=invalid), self.assertRaises(ds.ScriptError):
                ds.validate_step(invalid)

    def test_fixtures_group_retry_death_and_car_order(self):
        for phases in (["fixtures"], list(ds.PHASES)):
            steps = ds.build_route(phases)["steps"]
            commands = [(i, step["cmd"]) for i, step in enumerate(steps) if step["kind"] == "admin"]
            index = {cmd: i for i, cmd in commands}
            group = next(i for i, step in enumerate(steps) if step["kind"] == "group")
            ping = next(i for i, step in enumerate(steps) if step["kind"] == "ping")
            self.assertLess(group, ping)
            self.assertLess(ping, index["fx_camp_setup"])
            self.assertLess(index["fx_car_side"], index["fx_car_zeds"])
            self.assertEqual(steps[index["fx_die"] + 1]["kind"], "respawn")
            attempts = [i for i, cmd in commands if cmd == "fx_site_patrol_kill"]
            self.assertEqual(len(attempts), 2)
            self.assertTrue(any(step["kind"] == "walk" and step["to"] == list(ds.resolve_waypoint(ds.AI_SITE))
                                for step in steps[attempts[0] + 1:attempts[1]]))

    def test_uncertain_end_timeout_uses_last_walk_target_plus_margin(self):
        for kind, fields in (("admin", {"cmd": "fx_food", "value": ""}),
                             ("combat", {}), ("menu", {}), ("enter", {})):
            b = ds._Builder()
            b.walk(ds.AI_SITE)
            origin = b.position
            b.route(ds.TOWN)
            b.add(kind, **fields)
            b.add("stand", seconds=3)  # Waiting does not restore certainty.
            b.walk(ds.ZONE)
            distance = __import__("math").dist(origin, ds.resolve_waypoint(ds.ZONE)) + 150
            self.assertEqual(b.steps[-1]["timeout_s"], ds._timeout_for(distance, "jog"))
        b = ds._Builder()
        b.walk(ds.AI_SITE)
        origin = b.position
        b.walk(ds.ZONE)
        self.assertEqual(b.steps[-1]["timeout_s"], ds._timeout_for(
            __import__("math").dist(origin, ds.resolve_waypoint(ds.ZONE)), "jog"))


if __name__ == "__main__":
    unittest.main()
