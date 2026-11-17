"""Offline tests for the shared probe runtime helpers; SYNTHETIC fixtures, never DayZ behavior.

Covers the hardening shared by the CE probe and the taped-light probe stagers: Windows name
aliases, exact-inventory copy integrity, symlinked inputs, and static compatibility of a staged
runtime with tools/setup/Start-CEProbeServer.ps1 (PowerShell is never parsed or run here).

Actual TDD 2026-11-17 (fix round for issue 56):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_probe_runtime -v
RED: ImportError, cannot import name 'probe_runtime' from 'tools.setup' (unknown location).
"""
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from tests.unit import test_ce_probe as cet
from tests.unit import test_taped_light_probe as tlt
from tools.setup import ce_probe as ce
from tools.setup import diagnostic_mission as dm
from tools.setup import probe_runtime as rt
from tools.setup import taped_light_probe as taped

ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "tools/setup"
SCRIPT = (SETUP / "Start-CEProbeServer.ps1").read_text()

BAD_NAMES = ("vanilla-p0-001.", "vanilla-p0-001 ", "Vanilla-P0-001", "VANILLA-P0-001.", "CON", "con", "nul.txt",
             "NUL", "aux.", "PRN", "COM1", "com9.log", "LPT1", "lpt9.tar.gz", "name.", "name ", ".hidden", "-lead",
             "a b", "x" * 65, "bad:stream", "a..b.", "ce-probe-001 ")
GOOD_NAMES = ("ce-probe-001", "taped-light-probe-002", "COM10", "console", "com0", "lpt", "a", "x" * 64, "a.b-c_d")


class WindowsAliasTests(unittest.TestCase):
    parent = Path("/mnt/d/HollowCountryLocal")

    def test_aliases_of_the_verified_runtime_and_reserved_devices_are_refused_by_every_entry_point(self):
        for name in BAD_NAMES:
            for label, function in (("rt", rt.windows_runtime_root), ("ce", ce.windows_runtime_root),
                                    ("taped", taped.windows_runtime_root)):
                with self.subTest(name=name, entry=label), self.assertRaises(ValueError):
                    function(self.parent / name, self.parent)

    def test_plain_names_still_map_to_one_windows_child(self):
        for name in GOOD_NAMES:
            with self.subTest(name=name):
                self.assertEqual("D:\\HollowCountryLocal\\" + name, rt.windows_runtime_root(self.parent / name, self.parent))

    def test_the_protected_name_is_compared_after_windows_normalization(self):
        self.assertEqual("vanilla-p0-001", rt.windows_normalized_name("Vanilla-P0-001. . "))
        self.assertEqual("nul", rt.windows_normalized_name("NUL."))

    def test_launcher_name_rule_mirrors_the_python_rule(self):
        self.assertRegex(SCRIPT, r"\$name -notmatch '\^\[A-Za-z0-9\]\(\?:\[A-Za-z0-9\._-\]\{0,62\}\[A-Za-z0-9_-\]\)\?\$'")
        self.assertRegex(SCRIPT, r"\(CON\|PRN\|AUX\|NUL\|COM\[1-9\]\|LPT\[1-9\]\)")
        self.assertIn("vanilla-p0-001", SCRIPT)
        self.assertEqual(rt.NAME_RULE.pattern, r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9_-])?$")


class SharedSurfaceTests(unittest.TestCase):
    def test_both_stagers_use_the_one_shared_implementation(self):
        for name in ("SERVER_EXE", "SERVER_INSTALL", "SERVER_EXE_SHA256", "BATTLEYE_SHA256", "WINDOWS_PARENT",
                     "VERIFIED_RUNTIME_NAME", "MISSION_NAME", "PORT", "NAME_RULE", "IDENT_RULE", "SENSITIVE_PART",
                     "ALLOWED_MISSION_DIRS", "ALLOWED_MISSION_FILE", "PLAN_PIN_DELTAS", "MAX_PLAN_BYTES",
                     "lint_hook", "native_type_names", "sha256", "_clean", "_split_arguments", "_parameter_names",
                     "_function_bodies", "_read_bounded", "_hash_file", "_safe_plan_path", "_check_mission_entry",
                     "_new_file"):
            for module in (ce, taped):
                with self.subTest(name=name, module=module.__name__):
                    self.assertIs(getattr(rt, name.lstrip("_") if False else name), getattr(module, name))

    def test_server_arguments_are_exactly_the_launcher_list(self):
        root = r"D:\HollowCountryLocal\x-001"
        self.assertEqual(
            ["-ip=127.0.0.1", "-port=2302", f"-config={root}\\serverDZ.cfg",
             f"-mission={root}\\mpmissions\\dayzOffline.chernarusplus", f"-storage={root}\\storage",
             f"-profiles={root}\\profiles", f"-BEpath={root}\\battleye", "-doLogs", "-adminLog"],
            rt.server_arguments(root))

    def test_shared_module_never_launches_or_networks(self):
        text = re.sub(r'""".*?"""', "", (SETUP / "probe_runtime.py").read_text(), flags=re.S)
        text = "\n".join(re.sub(r"#.*", "", line) for line in text.splitlines())
        for forbidden in ("import subprocess", "Popen(", "os.system", "os.exec", "wine ", "powershell", "socket"):
            self.assertNotIn(forbidden, text)


def launcher_expected_arguments(root):
    """Parse the argument list the launcher will accept straight from its text."""
    block = re.search(r"\$expectedArguments = @\((.*?)\)\n", SCRIPT, re.S).group(1)
    tokens = re.findall(r"\"([^\"]+)\"|'([^']+)'", block)
    mission = root + "\\mpmissions\\dayzOffline.chernarusplus"
    return [(a or b).replace("$root", root).replace("$mission", mission) for a, b in tokens]


class LauncherCompatibilityTests(unittest.TestCase):
    """Emulate the launcher's checks on a staged taped-light runtime, from the PS1 text."""

    def stage_taped(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        source = tlt.make_source_runtime(root / "vanilla")
        dest = root / "taped-light-test"
        plan = taped.stage(source, dest, tlt.classification(), battleye_sha256=tlt.SYNTH_BE_SHA, _wsl_parent=root)
        return dest, plan

    def test_plan_arguments_equal_the_launcher_list_parsed_from_the_script(self):
        dest, plan = self.stage_taped()
        self.assertEqual(launcher_expected_arguments(plan["runtime_root"]), plan["arguments"])
        self.assertIn("-BEpath=" + plan["runtime_root"] + "\\battleye", plan["arguments"])
        self.assertEqual(["-doLogs", "-adminLog"], plan["arguments"][-2:])

    def test_launcher_fixed_table_matches_the_taped_light_plan_and_probe_paths(self):
        dest, plan = self.stage_taped()
        self.assertRegex(SCRIPT, r"'taped-light-probe'\s*=\s*@\{\s*Plan = '%s'; Directory = '%s'; Output = 'observations.json'"
                         % (re.escape(taped.PLAN_NAME), taped.PROBE_DIRECTORY))
        self.assertTrue((dest / taped.PLAN_NAME).is_file())
        self.assertEqual("taped-light-probe", plan["kind"])
        self.assertEqual("profiles/%s/observations.json" % taped.PROBE_DIRECTORY, plan["probe"]["output_relative_path"])
        self.assertEqual("profiles/%s/complete.txt" % taped.PROBE_DIRECTORY, plan["probe"]["sentinel_relative_path"])

    def test_every_launcher_precondition_holds_for_the_staged_runtime(self):
        dest, plan = self.stage_taped()
        root = plan["runtime_root"]
        mission = root + "\\mpmissions\\dayzOffline.chernarusplus"
        self.assertEqual("staged-only-not-launched", plan["status"])
        self.assertEqual((root, rt.SERVER_EXE, rt.SERVER_INSTALL, mission, 2302, rt.SERVER_EXE_SHA256),
                         (plan["runtime_root"], plan["server_exe"], plan["working_directory"], plan["mission"],
                          plan["port"], plan["server_exe_sha256"]))
        self.assertTrue(5 <= plan["probe"]["wait_minutes"] <= 120)
        staged = {entry["path"] for entry in plan["staged_files"]}
        on_disk = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
        self.assertEqual(on_disk, staged | {taped.PLAN_NAME})
        for entry in plan["staged_files"]:
            self.assertRegex(entry["path"], r"^[A-Za-z0-9_./-]+$")
            self.assertEqual(entry["sha256"], rt._hash_file(dest / entry["path"])[0])
        self.assertEqual([], list((dest / "storage").iterdir()))
        self.assertEqual([], list((dest / "profiles").iterdir()))
        self.assertFalse(any(p.is_symlink() for p in dest.rglob("*")))
        self.assertRegex(plan["runtime_root"], r"^D:\\HollowCountryLocal\\[^\\]+$")

    def test_launcher_wait_bounds_are_enforced_by_the_stager(self):
        self.assertIn("ValidateRange(0, 120)", SCRIPT)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        source = tlt.make_source_runtime(root / "vanilla")
        for minutes in (4, 121):
            with self.subTest(minutes=minutes), self.assertRaises(ValueError):
                taped.stage(source, root / f"taped-{minutes}", tlt.classification(), wait_minutes=minutes,
                            battleye_sha256=tlt.SYNTH_BE_SHA, _wsl_parent=root)
        many = tlt.classification([tlt.host("Gun%03d" % i, "no_slot_host") for i in range(600)])
        with self.assertRaises(ValueError):  # worst-case runtime would exceed the launcher's 120 minute ceiling
            taped.stage(source, root / "taped-long", many, per_class_ms=30000, battleye_sha256=tlt.SYNTH_BE_SHA,
                        _wsl_parent=root)
        self.assertFalse((root / "taped-long").exists())


def make_ce(root):
    source = cet.make_source_runtime(root / "vanilla")
    return source, root / "ce-probe-test", lambda s, d: ce.stage(s, d, battleye_sha256=cet.SYNTH_BE_SHA, _wsl_parent=root)


def make_taped(root):
    source = tlt.make_source_runtime(root / "vanilla")
    return source, root / "taped-light-test", lambda s, d: taped.stage(
        s, d, tlt.classification(), battleye_sha256=tlt.SYNTH_BE_SHA, _wsl_parent=root)


KINDS = (("ce", make_ce), ("taped", make_taped))
MISSION = "stock-backup/mpmissions/dayzOffline.chernarusplus"


class IntegrityCase(unittest.TestCase):
    def workspace(self, factory):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        source, dest, stage = factory(root)
        return root, source, dest, stage

    def assert_refused_and_clean(self, dest, stage, source, forbidden=()):
        with self.assertRaises(ValueError):
            stage(source, dest)
        for name in forbidden:
            self.assertEqual([], list(dest.rglob(name)) if dest.exists() else [], name)

    def mutate_after_verification(self, mutate):
        original = rt.verify_source

        def verified(*args, **kwargs):
            result = original(*args, **kwargs)
            mutate()
            return result
        return mock.patch.object(rt, "verify_source", side_effect=verified)


class CopyIntegrityTests(IntegrityCase):
    def test_a_file_added_to_the_mission_after_verification_is_refused_and_never_copied(self):
        for label, factory in KINDS:
            for added in ("credentials.json", "extra.xml", "db/notes.xml"):
                with self.subTest(kind=label, added=added):
                    root, source, dest, stage = self.workspace(factory)
                    mission = source / MISSION
                    with self.mutate_after_verification(lambda: (mission / added).write_bytes(b"{}\n")):
                        self.assert_refused_and_clean(dest, stage, source, forbidden=("credentials*", "extra.xml", "notes.xml"))

    def test_a_mission_file_changed_after_verification_is_refused(self):
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                target = source / MISSION / "db/types.xml"
                with self.mutate_after_verification(lambda: target.write_bytes(b"<types>swapped</types>\n")):
                    self.assert_refused_and_clean(dest, stage, source)

    def test_config_or_battleye_changed_after_verification_is_refused(self):
        for label, factory in KINDS:
            for relative in ("serverDZ.cfg", "battleye/BEServer_x64.dll"):
                with self.subTest(kind=label, changed=relative):
                    root, source, dest, stage = self.workspace(factory)
                    target = source / relative
                    with self.mutate_after_verification(lambda: target.write_bytes(b"changed after verification\n")):
                        self.assert_refused_and_clean(dest, stage, source)
                    self.assertNotIn(b"changed after verification", (dest / relative).read_bytes() if (dest / relative).exists() else b"")

    def test_symlinked_inputs_are_refused_before_anything_is_created(self):
        for label, factory in KINDS:
            for relative in ("serverDZ.cfg", "battleye/BEServer_x64.dll", "launch-plan.json", MISSION + "/db/types.xml",
                             MISSION + "/db", MISSION + "/init.c", "stock-backup", "battleye"):
                with self.subTest(kind=label, link=relative):
                    root, source, dest, stage = self.workspace(factory)
                    path = source / relative
                    moved = root / ("moved-" + relative.replace("/", "-"))
                    path.rename(moved)
                    os.symlink(moved, path)
                    self.assert_refused_and_clean(dest, stage, source)
                    self.assertFalse(dest.exists())

    def test_written_bytes_are_verified_against_the_admitted_hash(self):
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                real = rt._new_file

                def corrupt(path, data):
                    real(path, data + b"x")
                with mock.patch.object(rt, "new_file", side_effect=corrupt), mock.patch.object(rt, "_new_file", side_effect=corrupt):
                    self.assert_refused_and_clean(dest, stage, source)

    def test_mission_copy_rereads_the_destination_and_refuses_a_mismatch(self):
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                with mock.patch.object(dm, "_reread_digest", return_value="0" * 64):
                    self.assert_refused_and_clean(dest, stage, source)

    def test_an_unexpected_staged_file_is_refused(self):
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                real = rt.new_file

                def stray(path, data):
                    real(path, data)
                    if Path(path).name == "serverDZ.cfg":
                        (Path(path).parent / "stray.txt").write_bytes(b"x")
                with mock.patch.object(rt, "new_file", side_effect=stray):
                    self.assert_refused_and_clean(dest, stage, source)

    def test_sensitive_entries_are_refused_even_when_the_launch_plan_lists_them(self):
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                (source / MISSION / "credentials.json").write_bytes(b"{}\n")
                plan_path = source / "launch-plan.json"
                plan = json.loads(plan_path.read_text())
                plan["mission_files"].append({"path": "credentials.json", "sha256": rt.sha256(b"{}\n")})
                plan_path.write_text(json.dumps(plan))
                self.assert_refused_and_clean(dest, stage, source)
                self.assertFalse(dest.exists())

    def test_clean_staging_still_succeeds_for_both_stagers(self):
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                plan = stage(source, dest)
                self.assertEqual("staged-only-not-launched", plan["status"])
                self.assertEqual(plan["arguments"], rt.server_arguments(plan["runtime_root"]))


class DiagnosticMissionAdmissionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "mission"
        (self.source / "db").mkdir(parents=True)
        (self.source / "init.c").write_bytes(tlt.STOCK_INIT)
        (self.source / "db/types.xml").write_bytes(b"<types/>\n")
        self.admitted = {"files": {"init.c": (rt.sha256(tlt.STOCK_INIT), len(tlt.STOCK_INIT)),
                                   "db/types.xml": (rt.sha256(b"<types/>\n"), 9)}, "directories": ["db"]}

    def prepare(self, name, **extra):
        return dm.prepare_diagnostic_mission(self.source, self.root / name, purpose="taped-light-probe",
                                             hook=b"\n\n// hook\nclass HCDisposableDiagnosticMission : CustomMission {}\n",
                                             **extra)

    def test_exact_admitted_inventory_copies(self):
        result = self.prepare("ok", admitted=self.admitted, entry_check=rt._check_mission_entry)
        self.assertIn("init.c", result["files"])

    def test_inventory_drift_hash_drift_and_rejected_entries_are_refused(self):
        (self.source / "extra.xml").write_bytes(b"<x/>\n")
        with self.assertRaises(ValueError):
            self.prepare("extra", admitted=self.admitted)
        (self.source / "extra.xml").unlink()
        bad = dict(self.admitted, files=dict(self.admitted["files"], **{"db/types.xml": ("0" * 64, 9)}))
        with self.assertRaises(ValueError):
            self.prepare("hash", admitted=bad)
        (self.source / "secrets.json").write_bytes(b"{}\n")
        with self.assertRaises(ValueError):
            self.prepare("entry", entry_check=rt._check_mission_entry)
        self.assertFalse((self.root / "entry/secrets.json").exists())

    def test_existing_purposes_keep_working_without_admission(self):
        (self.source / "secrets.json").unlink() if (self.source / "secrets.json").exists() else None
        result = dm.prepare_diagnostic_mission(self.source, self.root / "legacy")
        self.assertEqual("disposable-diagnostic-selftests", result["kind"])


if __name__ == "__main__":
    unittest.main()
