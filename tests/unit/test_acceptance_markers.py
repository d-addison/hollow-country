"""Offline tests for the local-acceptance marker inventory and its checklist document.

Every fixture below is SYNTHETIC: tiny Enforce-like sources written to a temporary tree. These tests
prove the static scan, the dry-run/apply planner and the traceability of the real source's markers to
docs/LOCAL_ACCEPTANCE_V1.md. They prove nothing about DayZ behavior or any feature's acceptance.

Actual TDD 2026-11-17:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_acceptance_markers -v
RED: ImportError cannot import name 'acceptance_markers' from 'tools.audit' (module missing).
GREEN: Ran 37 tests, OK (after docs/LOCAL_ACCEPTANCE_V1.md was written).

Checklist refresh 2026-11-17 (landed work moved out of "Features pending landing"):
RED: Ran 42 tests, FAILED (failures=5): pending rows still listed landed work, "(worker branch)" labels
     remained, log literals missing from mods/ source, Session flow and Workshop notes absent.
GREEN: Ran 42 tests, OK (after docs/LOCAL_ACCEPTANCE_V1.md was rewritten).
"""
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import re
import tempfile
import unittest

from tools.audit import acceptance_markers as markers

ROOT = Path(__file__).resolve().parents[2]
CHECKLIST = ROOT / "docs/LOCAL_ACCEPTANCE_V1.md"
NAME = "$profile:HollowCountry/acceptance/"

FUEL = """// #53 production fuel siphon fixture.
// Marker named in a comment must not count: $profile:HollowCountry/acceptance/commented_out.enable
class FixtureFuelQualification
{
    static bool Qualified()
    {
        return false;
    }

    static bool LocalAcceptanceOptIn()
    {
        return FileExist("$profile:HollowCountry/acceptance/fuel_siphon.enable");
    }
}
"""

INFECTED = """class FixtureInfectedQualification
{
    // Evidence required: synthetic.
    static bool AlphaQualified()
    {
        return false;
    }

    static bool BetaQualified()
    {
        return true;
    }

    static bool GammaQualified()
    {
        return Compute();
    }
}
"""

OPTIN = """class FixtureWeather
{
    /* block comment: $profile:HollowCountry/acceptance/block_commented.enable */
    static bool WeatherOptIn()
    {
        return Probe();
    }

    static bool DynamicProbe(string name)
    {
        return FileExist("$profile:HollowCountry/acceptance/" + name + ".enable");
    }
}
"""


def write(root, relative, text):
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def fixture_tree(root):
    write(root, "mods/Fake/scripts/4_World/Actions/FakeFuelSiphon.c", FUEL)
    write(root, "mods/Fake/scripts/4_World/Infected/FakeState.c", INFECTED)
    write(root, "mods/Fake/scripts/4_World/Weather/FakeWeather.c", OPTIN)
    # Outside any scripts directory, wrong extension and a decoy: all must be ignored.
    write(root, "mods/Fake/config.cpp", 'x = "$profile:HollowCountry/acceptance/config_only.enable";')
    write(root, "mods/Fake/scripts/4_World/Notes.txt", 'static bool NotCodeQualified() { return false; }')
    write(root, "tools/decoy/scripts/Decoy.c", 'FileExist("$profile:HollowCountry/acceptance/decoy.enable");')


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        fixture_tree(self.tmp.name)
        self.result = markers.scan_tree(Path(self.tmp.name))
        self.by_marker = {}
        for record in self.result["markers"]:
            self.by_marker.setdefault(record["marker"], []).append(record)

    def test_profile_marker_has_location_class_and_tags(self):
        record = self.by_marker[NAME + "fuel_siphon.enable"][0]
        self.assertEqual("profile_marker", record["kind"])
        self.assertEqual("fuel_siphon", record["name"])
        self.assertEqual("mods/Fake/scripts/4_World/Actions/FakeFuelSiphon.c", record["file"])
        self.assertEqual(12, record["line"])
        self.assertEqual("mods/Fake/scripts/4_World/Actions/FakeFuelSiphon.c:12", record["location"])
        self.assertEqual("FixtureFuelQualification", record["class"])
        self.assertEqual("LocalAcceptanceOptIn", record["method"])
        self.assertEqual("fuel_siphon", record["feature"])
        self.assertEqual(["#53"], record["issues"])
        self.assertEqual("comment", record["issue_source"])

    def test_comments_do_not_count(self):
        self.assertNotIn(NAME + "commented_out.enable", self.by_marker)
        self.assertNotIn(NAME + "block_commented.enable", self.by_marker)

    def test_only_script_c_files_under_mods_are_scanned(self):
        self.assertEqual(3, self.result["scanned_files"])
        self.assertNotIn(NAME + "config_only.enable", self.by_marker)
        self.assertNotIn(NAME + "decoy.enable", self.by_marker)
        self.assertNotIn("FixtureNotes.NotCodeQualified", self.by_marker)

    def test_qualified_gates_report_class_and_state(self):
        alpha = self.by_marker["FixtureInfectedQualification.AlphaQualified"][0]
        self.assertEqual("source_qualification", alpha["kind"])
        self.assertEqual("FixtureInfectedQualification", alpha["class"])
        self.assertEqual("closed", alpha["state"])
        self.assertEqual("infected", alpha["feature"])
        self.assertEqual("open", self.by_marker["FixtureInfectedQualification.BetaQualified"][0]["state"])
        self.assertEqual("computed", self.by_marker["FixtureInfectedQualification.GammaQualified"][0]["state"])
        self.assertEqual(4, alpha["line"])

    def test_plain_qualified_gate_is_listed_beside_the_opt_in_marker(self):
        gate = self.by_marker["FixtureFuelQualification.Qualified"][0]
        self.assertEqual("closed", gate["state"])
        self.assertEqual(["#53"], gate["issues"])

    def test_opt_in_probe_without_a_literal_marker_is_an_opt_in_gate(self):
        gate = self.by_marker["FixtureWeather.WeatherOptIn"][0]
        self.assertEqual("opt_in_gate", gate["kind"])
        self.assertEqual("computed", gate["state"])

    def test_opt_in_probe_that_holds_a_marker_is_not_duplicated(self):
        self.assertNotIn("FixtureFuelQualification.LocalAcceptanceOptIn", self.by_marker)

    def test_accepted_gates_are_source_qualifications(self):
        write(self.tmp.name, "mods/Other/scripts/4_World/Interiors/FakeRules.c",
              "class FakeRules\n{\n    static bool PlacementAccepted()\n    {\n        return false;\n    }\n}\n")
        gate = [r for r in markers.scan_tree(Path(self.tmp.name))["markers"]
                if r["marker"] == "FakeRules.PlacementAccepted"][0]
        self.assertEqual(("source_qualification", "closed", "interiors"), (gate["kind"], gate["state"], gate["feature"]))

    def test_dynamic_marker_is_reported_but_not_creatable(self):
        dynamic = [r for r in self.result["markers"] if r["kind"] == "dynamic_profile_marker"]
        self.assertEqual(1, len(dynamic))
        self.assertEqual("FixtureWeather", dynamic[0]["class"])
        self.assertEqual("DynamicProbe", dynamic[0]["method"])
        self.assertIsNone(dynamic[0]["name"])
        self.assertNotIn(dynamic[0]["marker"], markers.creatable_names(self.result))

    def test_creatable_names_are_the_sorted_unique_profile_markers(self):
        self.assertEqual(["fuel_siphon"], markers.creatable_names(self.result))

    def test_records_are_sorted_and_scan_is_deterministic(self):
        keys = [(r["file"], r["line"], r["marker"]) for r in self.result["markers"]]
        self.assertEqual(sorted(keys), keys)
        self.assertEqual(self.result, markers.scan_tree(Path(self.tmp.name)))

    def test_untagged_marker_has_null_tags_not_guesses(self):
        write(self.tmp.name, "mods/Other/scripts/4_World/Misc/Plain.c",
              'class Plain { static bool Check() { return FileExist("$profile:HollowCountry/acceptance/mystery.enable"); } }\n')
        record = [r for r in markers.scan_tree(Path(self.tmp.name))["markers"] if r["name"] == "mystery"][0]
        self.assertEqual("mystery", record["feature"])
        self.assertEqual([], record["issues"])
        self.assertIsNone(record["issue_source"])

    def test_disable_markers_are_opt_outs_and_never_creatable(self):
        write(self.tmp.name, "mods/Other/scripts/4_World/Misc/Gate.c",
              'class Gate { static bool On() { return !FileExist("$profile:HollowCountry/acceptance/gate_feature.disable"); } }\n')
        result = markers.scan_tree(Path(self.tmp.name))
        record = [r for r in result["markers"] if r["name"] == "gate_feature"][0]
        self.assertEqual(("profile_marker", "disable", NAME + "gate_feature.disable"),
                         (record["kind"], record["polarity"], record["marker"]))
        self.assertEqual("enable", self.by_marker[NAME + "fuel_siphon.enable"][0]["polarity"])
        self.assertEqual(["gate_feature"], markers.opt_out_names(result))
        self.assertEqual(["fuel_siphon"], markers.creatable_names(result))

    def test_malformed_marker_names_are_not_creatable(self):
        write(self.tmp.name, "mods/Other/scripts/4_World/Misc/Bad.c",
              'class Bad { static bool Check() { return FileExist("$profile:HollowCountry/acceptance/../escape.enable"); } }\n')
        result = markers.scan_tree(Path(self.tmp.name))
        self.assertNotIn("..", "".join(markers.creatable_names(result)))
        self.assertNotIn("escape", markers.creatable_names(result))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        fixture_tree(self.repo)
        (self.repo / ".git").mkdir()
        self.profile = Path(self.tmp.name) / "profile"
        self.profile.mkdir()
        self.result = markers.scan_tree(self.repo)

    def plan(self, **kwargs):
        return markers.plan_profile(self.result, self.profile, self.repo, **kwargs)

    def test_plan_lists_files_without_creating_anything(self):
        plan = self.plan()
        self.assertEqual([str(self.profile.resolve() / "HollowCountry/acceptance/fuel_siphon.enable")],
                         [item["path"] for item in plan["files"]])
        self.assertEqual("create", plan["files"][0]["action"])
        self.assertEqual([], list(self.profile.iterdir()))

    def test_apply_creates_only_empty_marker_files(self):
        plan = self.plan()
        markers.apply_plan(plan)
        created = self.profile / "HollowCountry/acceptance/fuel_siphon.enable"
        self.assertTrue(created.is_file())
        self.assertEqual(0, created.stat().st_size)
        self.assertEqual([created], [p for p in (self.profile / "HollowCountry").rglob("*") if p.is_file()])

    def test_apply_never_overwrites_an_existing_marker(self):
        existing = self.profile / "HollowCountry/acceptance/fuel_siphon.enable"
        existing.parent.mkdir(parents=True)
        existing.write_text("operator content")
        plan = self.plan()
        self.assertEqual("exists", plan["files"][0]["action"])
        markers.apply_plan(plan)
        self.assertEqual("operator content", existing.read_text())

    def test_destination_inside_the_repo_is_refused(self):
        inside = self.repo / "mods"
        with self.assertRaises(markers.RefusedDestination):
            markers.plan_profile(self.result, inside, self.repo)
        with self.assertRaises(markers.RefusedDestination):
            markers.plan_profile(self.result, self.repo, self.repo)

    def test_destination_under_any_git_checkout_is_refused(self):
        other = Path(self.tmp.name) / "elsewhere"
        (other / ".git").mkdir(parents=True)
        (other / "profile").mkdir()
        with self.assertRaises(markers.RefusedDestination):
            markers.plan_profile(self.result, other / "profile", self.repo)

    def test_symlink_into_the_repo_is_refused(self):
        link = Path(self.tmp.name) / "link"
        link.symlink_to(self.repo / "mods")
        with self.assertRaises(markers.RefusedDestination):
            markers.plan_profile(self.result, link, self.repo)

    def test_missing_or_file_destination_is_refused(self):
        with self.assertRaises(markers.RefusedDestination):
            markers.plan_profile(self.result, Path(self.tmp.name) / "nope", self.repo)
        target = Path(self.tmp.name) / "file"
        target.write_text("x")
        with self.assertRaises(markers.RefusedDestination):
            markers.plan_profile(self.result, target, self.repo)

    def test_a_disable_marker_is_never_planned_or_written(self):
        write(self.repo, "mods/Other/scripts/4_World/Misc/Gate.c",
              'class Gate { static bool On() { return !FileExist("$profile:HollowCountry/acceptance/gate_feature.disable"); } }\n')
        result = markers.scan_tree(self.repo)
        plan = markers.plan_profile(result, self.profile, self.repo)
        self.assertEqual(["fuel_siphon"], [item["name"] for item in plan["files"]])
        with self.assertRaises(markers.RefusedDestination):
            markers.plan_profile(result, self.profile, self.repo, only=["gate_feature"])
        markers.apply_plan(plan)
        self.assertEqual([], [p for p in (self.profile / "HollowCountry").rglob("*.disable")])

    def test_present_opt_outs_reports_disable_files_and_unknown_ones(self):
        write(self.repo, "mods/Other/scripts/4_World/Misc/Gate.c",
              'class Gate { static bool On() { return !FileExist("$profile:HollowCountry/acceptance/gate_feature.disable"); } }\n')
        result = markers.scan_tree(self.repo)
        base = self.profile / "HollowCountry/acceptance"
        self.assertEqual([], markers.present_opt_outs(result, self.profile)["opt_outs"])
        write(base, "gate_feature.disable", "")
        write(base, "stale_name.disable", "")
        write(base, "fuel_siphon.enable", "")  # an opt-in file is not an opt-out
        report = markers.present_opt_outs(result, self.profile)
        self.assertEqual(["gate_feature"], report["opt_outs"])
        self.assertEqual(["stale_name"], report["unrecognised"])
        self.assertEqual({"fuel_siphon.enable", "gate_feature.disable", "stale_name.disable"},
                         {p.name for p in base.iterdir()}, "the report must write nothing")

    def test_only_filter_selects_and_rejects_unknown_names(self):
        self.assertEqual(["fuel_siphon"], [i["name"] for i in self.plan(only=["fuel_siphon"])["files"]])
        with self.assertRaises(markers.RefusedDestination):
            self.plan(only=["not_a_marker"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        fixture_tree(self.repo)
        (self.repo / ".git").mkdir()
        self.profile = Path(self.tmp.name) / "profile"
        self.profile.mkdir()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = markers.main(["--root", str(self.repo), *args])
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def test_default_output_is_json_with_relative_paths_only(self):
        code, out, _ = self.run_cli()
        self.assertEqual(0, code)
        data = json.loads(out)
        self.assertEqual(1, data["schema"])
        self.assertNotIn(str(self.repo), out)
        self.assertTrue(all(not r["file"].startswith("/") for r in data["markers"]))

    def test_dry_run_prints_files_and_creates_nothing(self):
        code, out, _ = self.run_cli("--write-profile-plan", str(self.profile))
        self.assertEqual(0, code)
        plan = json.loads(out)
        self.assertFalse(plan["applied"])
        self.assertEqual(1, len(plan["files"]))
        self.assertEqual([], list(self.profile.iterdir()))

    def test_apply_creates_the_files(self):
        code, out, _ = self.run_cli("--write-profile-plan", str(self.profile), "--apply")
        self.assertEqual(0, code)
        self.assertTrue(json.loads(out)["applied"])
        self.assertTrue((self.profile / "HollowCountry/acceptance/fuel_siphon.enable").is_file())

    def test_opt_outs_flag_lists_present_disable_markers_read_only(self):
        write(self.repo, "mods/Other/scripts/4_World/Misc/Gate.c",
              'class Gate { static bool On() { return !FileExist("$profile:HollowCountry/acceptance/gate_feature.disable"); } }\n')
        write(self.profile / "HollowCountry/acceptance", "gate_feature.disable", "")
        code, out, _ = self.run_cli("--opt-outs", str(self.profile))
        self.assertEqual(0, code)
        self.assertEqual(["gate_feature"], json.loads(out)["opt_outs"])
        code, _, err = self.run_cli("--opt-outs", str(self.profile), "--apply")
        self.assertEqual(2, code)

    def test_apply_without_a_destination_is_a_usage_error(self):
        code, _, err = self.run_cli("--apply")
        self.assertEqual(2, code)
        self.assertIn("--write-profile-plan", err)

    def test_repo_destination_is_refused_in_dry_run_and_apply(self):
        for extra in ([], ["--apply"]):
            code, out, err = self.run_cli("--write-profile-plan", str(self.repo / "mods"), *extra)
            self.assertEqual(2, code)
            self.assertEqual("", out)
            self.assertIn("refused", err)
        self.assertFalse((self.repo / "mods" / "HollowCountry").exists())


class ChecklistTraceabilityTests(unittest.TestCase):
    """Keeps every marker in the current source traceable to the owner's checklist."""

    @classmethod
    def setUpClass(cls):
        cls.result = markers.scan_tree(ROOT)
        cls.text = CHECKLIST.read_text(encoding="utf-8") if CHECKLIST.is_file() else ""

    OPT_OUTS = ("ai_trade_emote_ack", "atmosphere", "ecology_migration", "events", "events_sites", "fuel_siphon", "infected_ce_adoption",
                "infected_contact_guard", "infected_deaths", "infected_horde_routes", "infected_investigation",
                "infected_member_recovery", "infected_pack_routes", "infected_supplementary_chains",
                "infected_vision", "interior_placement", "interior_search", "pve_patrols", "taped_helmet", "taped_light")

    def test_the_real_source_has_the_known_fuel_opt_out(self):
        self.assertIn("fuel_siphon", markers.opt_out_names(self.result))

    def test_the_eighteen_features_are_opt_out_and_only_the_diagnostic_is_opt_in(self):
        self.assertEqual(sorted(self.OPT_OUTS), markers.opt_out_names(self.result))
        # Opt-ins: the Expansion AI diagnostic and the #135 infected LOD experiment 1.
        self.assertEqual(["infected_lod_experiment", "xai_diagnostic_spawn"], markers.creatable_names(self.result))

    def test_every_marker_in_current_source_is_in_the_checklist(self):
        self.assertTrue(self.text, "docs/LOCAL_ACCEPTANCE_V1.md is missing")
        missing = sorted({r["marker"] for r in self.result["markers"] if r["marker"] not in self.text})
        self.assertEqual([], missing, "add these markers to docs/LOCAL_ACCEPTANCE_V1.md")

    def test_every_marker_record_names_its_class_and_location(self):
        for record in self.result["markers"]:
            self.assertTrue(record["class"], record)
            self.assertGreater(record["line"], 0, record)
            self.assertFalse(record["file"].startswith("/"), record)

    def test_no_dynamic_marker_hides_a_name_from_the_checklist(self):
        self.assertEqual([], [r for r in self.result["markers"] if r["kind"] == "dynamic_profile_marker"])


class ChecklistShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CHECKLIST.read_text(encoding="utf-8") if CHECKLIST.is_file() else ""

    def test_document_exists_with_required_sections(self):
        self.assertTrue(self.text, "docs/LOCAL_ACCEPTANCE_V1.md is missing")
        for heading in ("## Setup", "## Per-feature checklist", "## Features pending landing",
                        "## Deferred two-client items", "## Performance"):
            self.assertIn(heading, self.text)

    def test_feature_table_has_the_required_columns(self):
        header = ("| Issue | Feature | Marker | Player steps (one client) | Expected observation "
                  "| RPT line to grep | Pass | Fail | Notes |")
        self.assertIn(header, self.text)

    def test_every_table_row_has_the_same_column_count(self):
        # Feature and pending rows start with an issue number or a dash; both tables share the header.
        feature_rows = [l for l in self.text.splitlines() if re.match(r"\| (#\d+|—|#\?)", l)]
        self.assertTrue(feature_rows)
        self.assertEqual({10}, {l.count("|") for l in feature_rows})

    PENDING_FEATURES = ("Interiors measured layouts and rooms", "Taped light other hosts")

    def section(self, name):
        return self.text.split(name, 1)[-1].split("\n## ", 1)[0]

    def feature_rows(self, name):
        return [l for l in self.section(name).splitlines() if re.match(r"\| (#\d+|\u2014|#\?)", l)]

    def test_pending_landing_rows_cover_only_unlanded_work(self):
        section = self.section("## Features pending landing")
        rows = self.feature_rows("## Features pending landing")
        for feature in self.PENDING_FEATURES:
            self.assertIn(feature, section)
        # Every pending row is genuinely unlanded; the count tracks the list above exactly.
        self.assertEqual(len(self.PENDING_FEATURES), len(rows))
        self.assertEqual(len(self.PENDING_FEATURES), section.count("pending landing:"))
        # Work that is on main moved to the per-feature table; none of it may stay pending.
        for landed in ("Weather", "Groups r2", "Crafting r2", "Deaths", "Noise/vision", "Batch A pathgraph",
                       "Batch B cfggameplay", "Build-identity fix", "Events (", "Firearms (",
                       "CE tenement coverage points", "Launcher follow-up", "Rostered optics",
                       "Deferred datamined variants"):
            self.assertNotIn(landed, section)

    def test_no_row_still_carries_a_worker_branch_label(self):
        labelled = [l[:60] for l in self.text.splitlines() if "(worker branch)" in l]
        self.assertEqual([], labelled)

    def test_pending_issue_numbers_are_not_labelled_as_worker_branch_work(self):
        pending = {n for row in self.feature_rows("## Features pending landing")
                   for n in re.findall(r"#(\d+)", row.split("|")[1])}
        branch_rows = [l for l in self.text.splitlines() if "(worker branch)" in l]
        landed_labels = {n for row in branch_rows for n in re.findall(r"#(\d+)", row.split("|")[1])}
        self.assertEqual(set(), pending & landed_labels)

    def test_every_per_feature_and_pending_row_has_ten_pipes_and_nine_cells(self):
        for name in ("## Per-feature checklist", "## Features pending landing"):
            lines = [l for l in self.section(name).splitlines()
                     if l.startswith("|") and not l.startswith("| Issue") and not l.startswith("| :---")]
            self.assertTrue(lines, name)
            for line in lines:
                self.assertRegex(line, r"^\| (#\d+( #\d+)*|\u2014) \|", line[:80])
                self.assertEqual(10, line.count("|"), line[:80])
                cells = [c.strip() for c in line.split("|")[1:-1]]
                self.assertEqual(9, len(cells), line[:80])
                self.assertEqual(["[ ]", "[ ]"], cells[6:8], "checkboxes must stay unchecked: " + line[:80])
                self.assertTrue(all(cells[:6]), "empty cell: " + line[:80])

    def test_quoted_log_literals_exist_in_the_mod_source(self):
        # Every complete backticked log literal in the "RPT line to grep" column must be a substring of a
        # Print in mods/. Literals with placeholders (<..>, ...) or prose are skipped.
        source = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                           for p in sorted((ROOT / "mods").rglob("*.c")))
        checked = 0
        missing = []
        for name in ("## Per-feature checklist", "## Features pending landing"):
            for row in self.feature_rows(name):
                for literal in re.findall(r"`([^`]+)`", row.split("|")[6]):
                    if "<" in literal or "..." in literal or literal.startswith("$"):
                        continue
                    checked += 1
                    if literal not in source:
                        missing.append(literal)
        self.assertGreater(checked, 40)
        self.assertEqual([], sorted(set(missing)))

    def test_session_flow_and_workshop_prerequisites_are_documented(self):
        for needle in ("### Session flow", "tools/setup/local_test_session.py", " plan ", " apply ", " rollback ",
                       "--snafu", "--tactical-flava", "--install-key", "--markers", "--interiors", "--ce-coverage",
                       "--expansion-ai", "all-local",
                       "2291785308", "2792982069", "2646817942", "Dabs Framework", "Expansion-Animations",
                       "CC BY-NC-ND"):
            self.assertIn(needle, self.text)
        mods_text = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                              for base in ("mods", "mission", "config") if (ROOT / base).is_dir()
                              for p in (ROOT / base).rglob("*") if p.is_file() and p.stat().st_size < 4000000)
        for forbidden in ("2291785308", "2792982069", "2646817942"):
            self.assertNotIn(forbidden, mods_text)

    def test_readme_v1_items_are_each_covered(self):
        lowered = self.text.lower()
        for needle in ("stamina", "weight", "group", "icon", "map", "event", "interior", "search", "ce coverage",
                       "crafting", "salvage", "fuel siphon", "taped light", "door", "line of sight", "audio",
                       "injury", "investigation", "alert chain", "horde", "death", "ecology", "weather",
                       "firearm", "snafu", "temperature", "spawn kit", "weapon obstruction", "wet weight",
                       "hit indicator", "leg crawler"):
            self.assertIn(needle, lowered)

    def test_referenced_repo_tools_exist(self):
        paths = set(re.findall(r"`((?:tools|mission|config|mods)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`", self.text))
        self.assertTrue(paths)
        self.assertEqual([], sorted(p for p in paths if not (ROOT / p).exists()))

    def test_document_prints_no_personal_home_path(self):
        self.assertIsNone(re.search(r"(?i)(?:/home/|/Users/|[A-Za-z]:[\\/]+Users[\\/])[A-Za-z0-9._-]+", self.text))


if __name__ == "__main__":
    unittest.main()
