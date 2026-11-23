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
        self.assertEqual(names, set(ds.ACTION_ARGS))

    def test_every_phase_builds_alone(self):
        for phase in ds.PHASES:
            script = ds.build_route([phase])
            ds.validate_script(script)
            self.assertTrue(script["steps"])

    def test_phase_order_follows_the_request(self):
        forward = ds.build_route(["join", "idle"])
        backward = ds.build_route(["idle", "join"])
        self.assertEqual(forward["steps"][0]["kind"], "wait")
        self.assertEqual(backward["steps"][-1]["kind"], "admin")

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

    def test_bad_waypoint_sources_refused(self):
        for source in ("site:no-such-site", "zone:no-such-zone", "shelter:no-such", "cell:1", "nocolon", 7):
            with self.assertRaises(ds.ScriptError):
                ds.resolve_waypoint(source)

    def test_default_route_walks_only_to_resolved_waypoints(self):
        script, notes = ds.build_plan(list(ds.PHASES))
        walks = [step for step in script["steps"] if step["kind"] == "walk"]
        self.assertEqual(len(walks), 3)
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


if __name__ == "__main__":
    unittest.main()
