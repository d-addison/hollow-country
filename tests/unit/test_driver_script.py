"""Step-file builder of the dev-only client driver; offline schema checks only."""
import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

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
        self.assertEqual(len(ds.resolve_waypoint("shelter:" + str(ident))), 2)

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
        walks = [step for step in script["steps"] if step["kind"] == "walk"]
        self.assertEqual(len(walks), 5)
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


if __name__ == "__main__":
    unittest.main()
