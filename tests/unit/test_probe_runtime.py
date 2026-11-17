"""Offline tests for the shared probe runtime helpers; SYNTHETIC fixtures, never DayZ behavior.

Covers the hardening shared by the CE probe and the taped-light probe stagers: Windows name
aliases, exact-inventory copy integrity, symlinked inputs, and static compatibility of a staged
runtime with tools/setup/Start-CEProbeServer.ps1 (PowerShell is never parsed or run here).

Actual TDD 2026-11-17 (fix round for issue 56):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_probe_runtime -v
RED: ImportError, cannot import name 'probe_runtime' from 'tools.setup' (unknown location).

Actual TDD 2026-11-17 (launcher kinds for issues 11/35, compile-refusal early exit):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_probe_runtime.LauncherKindTableTests \
    tests.unit.test_probe_runtime.LauncherCompileFailureTests
RED: Ran 10 tests, FAILED (failures=5, errors=2).
GREEN: test_probe_runtime + test_ce_probe + test_taped_light_probe, Ran 172 tests, OK. The PS1 parses
with no errors under Windows PowerShell 5.1, and the extracted Test-CompileRefused gave
taped-light-probe-002 True, taped-light-probe-003 False and ce-probe-001 False on the real profiles.
"""
import json
import os
from pathlib import Path
import re
import shutil
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


def powershell_accepts(name):
    """Static emulation of the launcher's name conditions (Start-CEProbeServer.ps1), read from its text.

    PowerShell is never run: the four literals are extracted from the script and evaluated with Python's re,
    case-insensitive as -match is. This is an offline mirror check, not proof of PowerShell's behavior.
    """
    def literal(pattern):
        found = re.search(pattern, SCRIPT)
        assert found, f"launcher condition not found: {pattern}"
        return found.group(1)
    consecutive = literal(r"\$root -match '([^']+)'")
    plain = literal(r"\$name -notmatch '([^']+)'")
    device = literal(r"\$name -match '(\^\(\?i:[^']+)'")
    verified = literal(r"ToLowerInvariant\(\) -eq '([^']+)'")
    root = "D:\\HollowCountryLocal\\" + name
    if re.search(consecutive, root, re.I) or not re.search(plain, name, re.I) or re.search(device, name):
        return False
    return name.rstrip(". ").lower() != verified


# One executable table shared by the Python rule and the launcher mirror: (name, accepted by both).
NAME_CASES = (
    ("ce-probe-001", True), ("taped-light-probe-002", True), ("a", True), ("x" * 64, True), ("a.b-c_d", True),
    ("COM10", True), ("console", True), ("com0", True), ("lpt", True), ("a_.b", True),
    ("a..b", False), ("a...b", False), ("a..", False), ("..", False), ("a.", False), ("a ", False), (".a", False),
    ("-a", False), ("a b", False), ("x" * 65, False), ("a:b", False), ("a*b", False),
    ("vanilla-p0-001", False), ("vanilla-p0-001.", False), ("Vanilla-P0-001", False), ("VANILLA-P0-001. ", False),
    ("CON", False), ("con", False), ("nul.txt", False), ("NUL.", False), ("aux.log", False), ("PRN", False),
    ("COM1", False), ("com9.log", False), ("LPT1", False), ("lpt9.tar.gz", False),
)


class NameRuleAlignmentTests(unittest.TestCase):
    parent = Path("/mnt/d/HollowCountryLocal")

    def test_python_and_launcher_accept_exactly_the_same_names(self):
        for name, expected in NAME_CASES:
            with self.subTest(name=name):
                try:
                    rt.windows_runtime_root(self.parent / name, self.parent)
                    python_accepts = True
                except ValueError:
                    python_accepts = False
                self.assertEqual(expected, python_accepts, "python rule")
                self.assertEqual(expected, powershell_accepts(name), "launcher text rule")

    def test_the_staged_plan_check_applies_the_same_rule(self):
        for name, expected in NAME_CASES:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                plan = {"kind": "ce-probe", "runtime_root": "D:\\HollowCountryLocal\\" + name}
                problems = rt.launcher_problems(plan, temp, "ce-probe-plan.json")
                self.assertEqual(not expected, "runtime root is not an allowed launcher name" in problems)

    def test_the_launcher_mirror_extractor_reads_the_real_script(self):
        self.assertTrue(powershell_accepts("ce-probe-001"))
        self.assertFalse(powershell_accepts("a..b"))      # the launcher's own substring rule


class CompatibilitySurfaceTests(unittest.TestCase):
    def test_ce_probe_keeps_the_module_attributes_it_exported_before_the_shared_runtime(self):
        import datetime
        import hashlib
        from pathlib import PureWindowsPath
        self.assertIs(ce.datetime, datetime)
        self.assertIs(ce.hashlib, hashlib)
        self.assertIs(ce.PureWindowsPath, PureWindowsPath)


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


class HookExpressionLintTests(unittest.TestCase):
    """The native compiler refused a 27-term concatenation ("Formula too complex") and a bare int in a
    string concatenation; the shared lint must refuse both shapes before staging."""

    def wrap(self, body, header="void F(int count, float ratio, string name)", extra=""):
        return ("class HCSample : CustomMission\n{\n    protected int m_Total;\n%s"
                "    %s\n    {\n        string row = \"\";\n%s\n    }\n}\n") % (extra, header, body)

    def issues(self, body, explicit_numbers=True, **kw):
        return rt.lint_hook(self.wrap(body, **kw), explicit_numbers=explicit_numbers)

    def chain(self, plus_count):
        return '        row = ' + " + ".join(['"x"'] * (plus_count + 1)) + ";"

    def test_a_ref_or_autoptr_returning_method_is_linted_like_any_other(self):
        """Review 006: ``ref array<string> HCReview()`` was not recognised as a method header, so duplicate locals, an
        over-long statement or a late out argument inside it were never seen."""
        for modifier in ("ref ", "autoptr ", "protected ref ", "static ref "):
            with self.subTest(modifier):
                header = modifier + "array<string> HCReview()"
                duplicate = "        int sample = 0;\n        int sample = 1;\n        return null;"
                self.assertTrue(any("sample" in item for item in self.issues(duplicate, header=header)),
                                self.issues(duplicate, header=header))
                self.assertTrue(any("binary '+'" in item for item in self.issues(self.chain(rt.MAX_STATEMENT_PLUS + 1) +
                                                                                 "\n        return null;", header=header)))
        clean = "        int sample = 0;\n        return null;"
        self.assertEqual([], self.issues(clean, header="ref array<string> HCReview()"))

    def test_the_bound_is_the_observed_native_maximum_and_cites_its_evidence(self):
        self.assertEqual(9, rt.MAX_STATEMENT_PLUS)
        for phrase in ("Formula too complex", "164289", "ce-probe-001"):
            self.assertIn(phrase, rt.lint_hook.__doc__ + (rt.__doc__ or "") + rt.HOOK_EXPRESSION_EVIDENCE)

    def test_a_statement_over_the_bound_is_flagged_and_one_at_the_bound_is_not(self):
        self.assertEqual([], self.issues(self.chain(rt.MAX_STATEMENT_PLUS)))
        found = self.issues(self.chain(rt.MAX_STATEMENT_PLUS + 1))
        self.assertTrue(any("binary '+' operators" in i and "Formula too complex" in i for i in found), found)

    def test_the_count_is_per_statement_across_lines_and_ignores_strings_and_compound_operators(self):
        spread = "        row = row + \"a\"\n            + \"b\" + \"c\" + \"d\" + \"e\" + \"f\"\n            + \"g\" + \"h\" + \"i\" + \"j\";"
        self.assertTrue(any("binary '+'" in i for i in self.issues(spread)), spread)
        in_strings = '        row = "+++++++++++++ + + + + + + + + + + + +";'
        self.assertEqual([], self.issues(in_strings))
        compound = "        int n = 0;\n        n++;\n        n += 1;\n        n++; n++; n++; n++; n++; n++; n++; n++; n++; n++; n++;"
        self.assertEqual([], self.issues(compound, header="void F()"))
        self.assertTrue(any("binary '+'" in i for i in self.issues(
            "        row = row" + " + \"a\"" * 10 + ";")))

    def test_statements_are_counted_separately(self):
        two = self.chain(rt.MAX_STATEMENT_PLUS) + "\n" + self.chain(rt.MAX_STATEMENT_PLUS)
        self.assertEqual([], self.issues(two))

    def test_a_bare_int_float_or_bool_local_in_a_string_concatenation_is_flagged(self):
        for body, name in (('        row = row + "n=" + count;', "count"),
                           ('        row = "r=" + ratio + ",";', "ratio"),
                           ('        row = count + "n";', "count"),
                           ('        row = "t" + m_Total;', "m_Total"),
                           ('        bool ready = true;\n        row = "b" + ready;', "ready"),
                           ('        row = Foo("k") + count;', "count")):
            with self.subTest(body=body):
                found = self.issues(body, extra="    string Foo(string key)\n    {\n        return key;\n    }\n")
                self.assertTrue(any("bare numeric" in i and name in i for i in found), found)

    def test_a_bare_numeric_literal_or_numeric_returning_call_in_a_concatenation_is_flagged(self):
        self.assertTrue(any("bare numeric" in i for i in self.issues('        row = "n" + 5;')))
        self.assertTrue(any("bare numeric" in i for i in self.issues('        row = "n" + 1.5;')))
        helper = "    int Total()\n    {\n        return 1;\n    }\n"
        self.assertTrue(any("bare numeric" in i for i in self.issues('        row = "n" + Total();', extra=helper)))
        self.assertTrue(any("bare numeric" in i for i in self.issues('        row = "n" + Count_(count);',
                                                                     extra=helper.replace("Total", "Count_"))))
        self.assertTrue(any("bare numeric" in i for i in self.issues('        TStringArray items = new TStringArray;\n        row = "n" + items.Count();')))

    def test_a_vector_component_in_a_string_concatenation_is_a_bare_float(self):
        found = self.issues('        row = "[" + where[0] + "]";', header="void F(vector where)")
        self.assertTrue(any("bare numeric" in i and "where[0]" in i for i in found), found)
        self.assertEqual([], self.issues('        row = "[" + where[0].ToString() + "]";', header="void F(vector where)"))

    def test_the_numeric_rule_is_opt_in_because_the_ce_hook_compiled_natively_without_it(self):
        self.assertEqual([], self.issues('        row = "n=" + count;', explicit_numbers=False))
        self.assertEqual([], rt.lint_hook(self.wrap('        row = "n=" + count;')))
        self.assertTrue(self.issues('        row = "n=" + count;'))

    def test_explicit_to_string_and_plain_arithmetic_are_accepted(self):
        for body in ('        row = row + "n=" + count.ToString();',
                     '        row = "r=" + ratio.ToString() + ",";',
                     '        row = name + "=" + name;',
                     '        int next = count + 1;\n        float scaled = ratio + 0.5 + next;',
                     '        if (count + 1 > 2)\n            row = "x";',
                     '        row = Foo("a", count + 1);',
                     '        row = "n" + Foo2(count + 1);'):
            with self.subTest(body=body):
                found = self.issues(body, extra="    string Foo(string key, int v)\n    {\n        return key;\n    }\n"
                                                "    string Foo2(int v)\n    {\n        return \"\";\n    }\n")
                self.assertEqual([], found)

    def test_nested_call_arguments_are_checked_too(self):
        found = self.issues('        Print("n" + count);')
        self.assertTrue(any("bare numeric" in i for i in found), found)

    LONG = " + ".join(['"x"'] * 28)  # 27 binary '+', the shape the native compiler refused

    def layouts(self):
        """The same over-bound statement in method layouts the old four-space regex did not recognise."""
        row = "string row = %s;" % self.LONG
        return {
            "brace on the declaration line": "class HC : CustomMission\n{\n    void F() {\n        %s\n    }\n}\n" % row,
            "eight space indent": "class HC : CustomMission\n{\n        void F()\n        {\n            %s\n        }\n}\n" % row,
            "tab indent": "class HC : CustomMission\n{\n\tvoid F()\n\t{\n\t\t%s\n\t}\n}\n" % row,
            "unindented": "class HC : CustomMission\n{\nvoid F()\n{\n%s\n}\n}\n" % row,
            "one line": "class HC : CustomMission\n{\n    void F() { %s }\n}\n" % row,
            "braces in a block": "class HC : CustomMission\n{\n    void F()\n    {\n        if (true) { %s }\n    }\n}\n" % row,
            "modifier on an inline method": "class HC : CustomMission\n{\n    override void F(int a) {\n        %s\n    }\n}\n" % row,
        }

    def test_the_complexity_bound_holds_for_every_method_layout_not_just_the_generated_one(self):
        for label, hook in self.layouts().items():
            with self.subTest(layout=label):
                self.assertEqual(27, rt.max_statement_plus(hook))
                for explicit in (False, True):
                    found = rt.lint_hook(hook, explicit_numbers=explicit)
                    self.assertTrue(any("Formula too complex" in i and "27 binary '+'" in i for i in found), found)

    def test_the_complexity_bound_reports_the_line_of_a_statement_outside_any_method(self):
        found = rt.lint_hook("class HC : CustomMission\n{\n    string m_Row = %s;\n}\n" % self.LONG)
        self.assertTrue(any(i.startswith("line 3:") and "Formula too complex" in i for i in found), found)

    def test_a_statement_at_the_bound_is_accepted_in_every_layout(self):
        at_bound = " + ".join(['"x"'] * (rt.MAX_STATEMENT_PLUS + 1))
        for label, hook in self.layouts().items():
            with self.subTest(layout=label):
                self.assertEqual([], rt.lint_hook(hook.replace(self.LONG, at_bound), explicit_numbers=True))

    def test_the_numeric_rule_follows_the_same_method_layouts(self):
        for header in ("void F(int count) {", "        void F(int count)\n        {", "\tvoid F(int count)\n\t{"):
            hook = "class HC : CustomMission\n{\n%s\n        string row = \"\";\n        row = \"n=\" + count;\n    }\n}\n" % header
            with self.subTest(header=header):
                found = rt.lint_hook(hook, explicit_numbers=True)
                self.assertTrue(any("bare numeric" in i and "count" in i for i in found), found)
                self.assertEqual([], rt.lint_hook(hook.replace("+ count", "+ count.ToString()"), explicit_numbers=True))

    def test_control_flow_headers_are_not_mistaken_for_methods(self):
        hook = self.wrap('        if (count > 0) { row = "a"; }\n        else if (count < 0) { row = "b"; }\n'
                         '        while (count > 0) { count = count - 1; }\n        for (int i = 0; i < 3; i++) { row = "c"; }')
        self.assertEqual([], rt.lint_hook(hook, explicit_numbers=True))

    def test_compound_assignment_into_a_string_is_a_concatenation(self):
        for body, term in (('        row += count;', "count"),
                           ('        row += "n=" + count;', "count"),
                           ('        row += ratio;', "ratio"),
                           ('        row += 5;', "5"),
                           ('        row += Total();', "Total()"),
                           ('        name += count;', "count")):
            with self.subTest(body=body):
                found = self.issues(body, extra="    int Total()\n    {\n        return 1;\n    }\n")
                self.assertTrue(any("bare numeric" in i and term in i for i in found), found)

    def test_parenthesised_numeric_terms_are_normalised_before_the_check(self):
        for body in ('        row = "n=" + (count);', '        row = "n=" + ((count));', '        row = (count) + "n=";',
                     '        row += (count);', '        row = "n=" + (count + 1);', '        row += "n=" + (ratio * 2);'):
            with self.subTest(body=body):
                found = self.issues(body)
                self.assertTrue(any("bare numeric" in i for i in found), found)

    def test_explicit_strings_and_numeric_destinations_stay_accepted_with_compound_and_parentheses(self):
        for body in ('        row += count.ToString();',
                     '        row += "n=" + count.ToString();',
                     '        row += (count + 1).ToString();',
                     '        row = "n=" + (count.ToString());',
                     '        row += name;',
                     '        row += "a" + (name);',
                     '        count += 1;',
                     '        count += count + 1;',
                     '        ratio += (ratio + 0.5);',
                     '        row = (name);'):
            with self.subTest(body=body):
                self.assertEqual([], self.issues(body))


class GeneratedHookExpressionTests(unittest.TestCase):
    def test_the_ce_probe_hook_passes_the_expression_lint_unchanged(self):
        hook = ce.render_hook(cet.targets_for(), export_delay_s=30, census_delay_s=240).decode()
        self.assertEqual([], rt.lint_hook(hook))
        self.assertLessEqual(rt.max_statement_plus(hook), rt.MAX_STATEMENT_PLUS)
        self.assertEqual(9, rt.max_statement_plus(hook))

    def test_the_taped_light_hook_passes_with_headroom_below_the_native_maximum(self):
        hook = taped.render_hook(taped.select_targets(tlt.classification())).decode()
        self.assertEqual([], rt.lint_hook(hook, explicit_numbers=True))
        self.assertLessEqual(rt.max_statement_plus(hook), 8)

    def test_both_stagers_run_the_expression_lint_before_writing(self):
        text = Path(taped.__file__).read_text() + Path(ce.__file__).read_text()
        self.assertEqual(2, text.count("lint_hook(hook.decode"))
        self.assertIn("explicit_numbers=True", Path(taped.__file__).read_text())
        self.assertNotIn("explicit_numbers", Path(ce.__file__).read_text())


class StagedHookComplexityTests(unittest.TestCase):
    """A hook the stager renders is linted as text: formatting of an extra method must not bypass the bound."""

    def stage_with_extra_method(self, method):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        source = tlt.make_source_runtime(root / "vanilla")
        dest = root / "taped-light-test"
        real = taped.render_hook

        def render(*args, **kwargs):
            text = real(*args, **kwargs).decode()
            index = text.rfind("}")
            return (text[:index] + method + text[index:]).encode()
        with mock.patch.object(taped, "render_hook", side_effect=render):
            with self.assertRaises(ValueError) as caught:
                taped.stage(source, dest, tlt.classification(), battleye_sha256=tlt.SYNTH_BE_SHA, _wsl_parent=root)
        self.assertFalse((dest / taped.PLAN_NAME).exists())
        return str(caught.exception)

    def test_the_real_stager_refuses_an_over_bound_statement_in_any_method_layout(self):
        row = 'string row = %s;' % " + ".join(['"x"'] * 28)
        for label, method in (("inline brace", "    void HCReviewComplexity() {\n        %s\n    }\n" % row),
                              ("eight spaces", "        void HCReviewComplexity()\n        {\n            %s\n        }\n" % row)):
            with self.subTest(layout=label):
                self.assertIn("Formula too complex", self.stage_with_extra_method(method))


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


def swap_for_link(path, target):
    """Replace the directory or file at ``path`` by a symlink to ``target`` (a link-swap race)."""
    path = Path(path)
    if path.is_dir() and not path.is_symlink():
        for child in sorted(path.rglob("*"), reverse=True):
            child.rmdir() if child.is_dir() else child.unlink()
        path.rmdir()
    else:
        path.unlink()
    os.symlink(target, path)


class LinkRaceTests(IntegrityCase):
    """A path component swapped for a symlink between a check and its use must be refused by the very call
    that would have followed it. Sol P2: the earlier lstat checks left a gap before each open/write."""

    def test_a_source_battleye_directory_swapped_for_a_symlink_right_before_the_dll_read_is_refused(self):
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                real_read = rt.read_identified

                def swapping(path, limit):
                    if Path(path).name == "BEServer_x64.dll":
                        copy = root / "elsewhere-battleye"
                        (copy).mkdir()
                        (copy / "BEServer_x64.dll").write_bytes((Path(path)).read_bytes())    # same bytes: a follow would pass
                        swap_for_link(Path(path).parent, copy)
                    return real_read(path, limit)
                with mock.patch.object(rt, "read_identified", side_effect=swapping):
                    self.assert_refused_and_clean(dest, stage, source)
                self.assertFalse(dest.exists())

    def test_a_destination_battleye_directory_swapped_before_the_dll_write_writes_nothing_outside(self):
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                outside = root / "outside"
                outside.mkdir()
                real_new = rt.new_file

                def swapping(path, data):
                    if Path(path).name == "BEServer_x64.dll":
                        swap_for_link(Path(path).parent, outside)
                    real_new(path, data)
                with mock.patch.object(rt, "new_file", side_effect=swapping):
                    self.assert_refused_and_clean(dest, stage, source)
                self.assertEqual([], list(outside.iterdir()))

    def test_a_staged_mission_file_swapped_for_a_symlink_before_the_final_tree_check_is_refused(self):
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                outside = root / "outside-types.xml"
                real_create = dm.create_exclusive

                def swapping(path, data):
                    real_create(path, data)
                    if Path(path).name == dm.MARKER_NAME:       # last write of the mission copy
                        outside.write_bytes((Path(path).parent / "db/types.xml").read_bytes())
                        swap_for_link(Path(path).parent / "db/types.xml", outside)
                with mock.patch.object(dm, "create_exclusive", side_effect=swapping):
                    self.assert_refused_and_clean(dest, stage, source)

    def displace_during_final_scan(self, factory, component, replace):
        """Stage while ``component`` is renamed away right after the final scan opened it (retained descriptor
        keeps pointing at the moved inode), then put ``replace(path, moved)`` under the old name."""
        root, source, dest, stage = self.workspace(factory)
        state = {"launch": False, "walk": 0, "done": False}
        real_launch, real_walk, real_child = rt.launcher_problems, dm.walk_plain, dm._open_child_dir
        moved = root / "moved-away"

        def launch(*args, **kwargs):
            state["launch"] = True
            try:
                return real_launch(*args, **kwargs)
            finally:
                state["launch"] = False

        def walk(*args, **kwargs):
            state["walk"] += 1
            try:
                return real_walk(*args, **kwargs)
            finally:
                state["walk"] -= 1

        def child(descriptor, name):
            opened = real_child(descriptor, name)
            if state["launch"] and state["walk"] and name == component and not state["done"]:
                state["done"] = True
                target = next(dest.rglob(component))
                target.rename(moved)
                replace(target, moved)
            return opened
        with mock.patch.object(rt, "launcher_problems", side_effect=launch), \
                mock.patch.object(dm, "walk_plain", side_effect=walk), \
                mock.patch.object(dm, "_open_child_dir", side_effect=child):
            with self.assertRaises(ValueError):
                stage(source, dest)
        self.assertTrue(state["done"], "the displacement hook never ran")
        plans = [p for p in root.rglob("*-probe-plan.json")]
        self.assertEqual([], plans)

    def test_a_directory_displaced_after_the_final_scan_opened_it_never_yields_a_plan(self):
        """Sol review 003 P2: the final scan certified a retained descriptor of a directory that no longer
        occupied its name (a symlink there). Every opened directory is rechecked against its name."""
        replacements = {
            "symlink to the moved tree": lambda path, moved: os.symlink(moved, path, target_is_directory=True),
            "an empty real directory": lambda path, moved: path.mkdir(),
            "nothing at all": lambda path, moved: None,
        }
        for label, factory in KINDS:
            for component in ("db", "mpmissions", "battleye"):
                for how, replace in replacements.items():
                    with self.subTest(kind=label, component=component, replacement=how):
                        self.displace_during_final_scan(factory, component, replace)

    def test_the_staged_root_replaced_after_the_final_scan_opened_it_never_yields_a_plan(self):
        for label, factory in KINDS:
            for how in ("symlink", "empty"):
                with self.subTest(kind=label, replacement=how):
                    root, source, dest, stage = self.workspace(factory)
                    state = {"launch": False, "walk": 0, "done": False}
                    real_launch, real_walk, real_child = rt.launcher_problems, dm.walk_plain, dm._open_child_dir
                    moved = root / "moved-root"

                    def launch(*args, **kwargs):
                        state["launch"] = True
                        return real_launch(*args, **kwargs)

                    def walk(*args, **kwargs):
                        state["walk"] += 1
                        try:
                            return real_walk(*args, **kwargs)
                        finally:
                            state["walk"] -= 1

                    def child(descriptor, name):
                        opened = real_child(descriptor, name)
                        if state["launch"] and state["walk"] and name == dest.name and not state["done"]:
                            state["done"] = True
                            dest.rename(moved)
                            os.symlink(moved, dest, target_is_directory=True) if how == "symlink" else dest.mkdir()
                        return opened
                    with mock.patch.object(rt, "launcher_problems", side_effect=launch), \
                            mock.patch.object(dm, "walk_plain", side_effect=walk), \
                            mock.patch.object(dm, "_open_child_dir", side_effect=child):
                        with self.assertRaises(ValueError):
                            stage(source, dest)
                    self.assertTrue(state["done"])
                    self.assertEqual([], list(root.rglob("*-probe-plan.json")))

    def test_a_directory_moved_after_it_was_opened_but_before_the_leaf_write_is_still_refused(self):
        """Narrowed contract (documented in diagnostic_mission.py): a descriptor-anchored write cannot stop the
        one leaf that lands in a directory renamed after it was opened. Staging must still end refused, with no
        plan; where those bytes went is the residual that only a protected ancestor namespace removes."""
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                real_child, moved = dm._open_child_dir, root / "moved-battleye"
                state = {"writing": False, "done": False}
                real_new = rt.new_file

                def writing(path, data):
                    state["writing"] = Path(path).name == "BEServer_x64.dll"
                    try:
                        real_new(path, data)
                    finally:
                        state["writing"] = False

                def child(descriptor, name):
                    opened = real_child(descriptor, name)
                    if state["writing"] and name == "battleye" and not state["done"]:
                        state["done"] = True
                        (dest / "battleye").rename(moved)
                    return opened
                with mock.patch.object(rt, "new_file", side_effect=writing), \
                        mock.patch.object(dm, "_open_child_dir", side_effect=child):
                    with self.assertRaises((ValueError, OSError)):    # a refusal, never a published plan
                        stage(source, dest)
                self.assertTrue(state["done"])
                self.assertEqual([], list(root.rglob("*-probe-plan.json")))

    def test_staging_is_refused_where_directory_descriptor_operations_are_unavailable(self):
        for label, factory in KINDS:
            with self.subTest(kind=label):
                root, source, dest, stage = self.workspace(factory)
                with mock.patch("sys.platform", "win32"):
                    self.assert_refused_and_clean(dest, stage, source)
                self.assertFalse(dest.exists())
        with mock.patch.object(dm.os, "supports_dir_fd", frozenset()), self.assertRaises(ValueError):
            dm.require_fd_anchoring()

    def test_the_concurrency_contract_names_what_is_guaranteed_and_the_matching_replacement_residual(self):
        """Sol review 004: the comment must not say a displaced destination always ends refused. It states the
        trusted-namespace assumption, the refusals that remain detectable and the undetectable matching replacement."""
        text = " ".join(line.lstrip("# ").strip() for line in Path(dm.__file__).read_text().splitlines()
                        if line.startswith("#"))
        for needle in ("stable, trusted destination namespace", "still detectable", "NOT detected",
                       "same names and bytes", "outside the requested destination", "Only a protected"):
            self.assertIn(needle, text)
        self.assertNotIn("ends refused with no plan", text)
        self.assertNotIn("always refused", text)

    def test_a_moved_directory_replaced_by_a_writer_with_the_same_bytes_is_a_known_undetected_residual(self):
        """PINNED RESIDUAL (Sol review 004, synthetic): a concurrent writer moves the opened battleye directory away
        and later supplies the same file bytes at the requested path. The stager cannot tell, so staging succeeds
        although one leaf was written outside the destination. If this ever starts being refused, update the
        concurrency comment in diagnostic_mission.py together with this test."""
        root, source, dest, stage = self.workspace(make_taped)
        real_child, real_new, moved = dm._open_child_dir, rt.new_file, root / "moved-battleye"
        state = {"writing": False, "done": False}

        def writing(path, data):
            state["writing"] = Path(path).name == "BEServer_x64.dll"
            try:
                real_new(path, data)
            finally:
                state["writing"] = False
            if Path(path).name == "BEServer_x64.dll" and state["done"]:
                shutil.copyfile(moved / "BEServer_x64.dll", path)       # the concurrent writer's matching bytes

        def child(descriptor, name):
            opened = real_child(descriptor, name)
            if state["writing"] and name == "battleye" and not state["done"]:
                state["done"] = True
                (dest / "battleye").rename(moved)
                (dest / "battleye").mkdir()
            return opened
        with mock.patch.object(rt, "new_file", side_effect=writing), mock.patch.object(dm, "_open_child_dir", side_effect=child):
            stage(source, dest)
        self.assertTrue(state["done"])
        self.assertTrue((moved / "BEServer_x64.dll").exists())          # the leaf that was written outside
        self.assertEqual(1, len(list(root.rglob("*-probe-plan.json"))))

    def test_the_drvfs_junction_residual_is_documented_and_left_to_the_launcher_reverification(self):
        """PINNED RESIDUAL, not a behavior test: O_NOFOLLOW and *at() calls cannot see an NTFS junction or
        reparse point that a Windows process swaps in on /mnt/d. The launcher must keep re-verifying."""
        text = Path(dm.__file__).read_text()
        for needle in ("DrvFs", "junction", "reparse", "Windows launcher re-verifies"):
            self.assertIn(needle, text)
        self.assertGreaterEqual(SCRIPT.count("Assert-NoReparsePoints -Path $root"), 2)
        self.assertIn("Reparse point refused", SCRIPT)


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

    def test_a_staged_symlink_with_the_same_bytes_never_passes_admitted_preparation(self):
        """The re-read must not follow a link: a same-byte symlink at the staged name would pass a following read."""
        outside = self.root / "outside-types.xml"
        real = dm._reread_digest

        def swapping(path):
            if Path(path).name == "types.xml":
                outside.write_bytes(b"<types/>\n")
                swap_for_link(path, outside)
            return real(path)
        with mock.patch.object(dm, "_reread_digest", swapping), self.assertRaises(ValueError):
            self.prepare("linked", admitted=self.admitted, entry_check=rt._check_mission_entry)
        self.assertEqual(b"<types/>\n", outside.read_bytes())

    def test_a_staged_symlink_is_refused_even_without_admission(self):
        outside = self.root / "outside-types.xml"
        real = dm.create_exclusive

        def swapping(path, data):
            real(path, data)
            if Path(path).name == dm.MARKER_NAME:
                outside.write_bytes(b"<types/>\n")
                swap_for_link(Path(path).parent / "db/types.xml", outside)
        with mock.patch.object(dm, "create_exclusive", swapping), self.assertRaises(ValueError):
            self.prepare("linked-final")

    def test_existing_purposes_keep_working_without_admission(self):
        (self.source / "secrets.json").unlink() if (self.source / "secrets.json").exists() else None
        result = dm.prepare_diagnostic_mission(self.source, self.root / "legacy")
        self.assertEqual("disposable-diagnostic-selftests", result["kind"])


def launcher_kind_table(script):
    """The launcher's fixed per-kind table, parsed from its text: kind -> (plan, directory, output)."""
    block = re.search(r"\$probes = @\{(.*?)\n\}", script, re.S)
    assert block, "launcher probe table not found"
    rows = re.findall(r"'([a-z-]+)' = @\{ Plan = '([^']+)'; Directory = '([^']+)'; Output = '([^']+)' \}", block.group(1))
    return {kind: (plan, directory, output) for kind, plan, directory, output in rows}


def launcher_validate_set(script):
    found = re.search(r"\[ValidateSet\(([^)]*)\)\]\s*\[string\]\$Kind", script)
    assert found, "launcher -Kind ValidateSet not found"
    return set(re.findall(r"'([^']+)'", found.group(1)))


def launcher_wait_loop(script):
    found = re.search(r"while \(\[DateTime\]::UtcNow -lt \$deadline\) \{(.*?)\n    \}", script, re.S)
    assert found, "launcher wait loop not found"
    return found.group(1)


class LauncherKindTableTests(unittest.TestCase):
    """The PS1 kind table, its ValidateSet and probe_runtime.LAUNCHER_PROBES are one table (issues 11, 35, 56)."""

    def test_launcher_table_equals_the_python_table(self):
        self.assertEqual(rt.LAUNCHER_PROBES, launcher_kind_table(SCRIPT))

    def test_validate_set_admits_exactly_the_table_kinds(self):
        self.assertEqual(set(rt.LAUNCHER_PROBES), launcher_validate_set(SCRIPT))

    def test_weather_and_interior_kinds_have_fixed_paths(self):
        self.assertEqual(("weather-probe-plan.json", "HCWeatherProbe", "observations.json"),
                         rt.LAUNCHER_PROBES["weather-probe"])
        self.assertEqual(("interior-sampler-plan.json", "HCInteriorSampler", "census.json"),
                         rt.LAUNCHER_PROBES["interior-sampler"])

    def test_every_kind_has_distinct_plan_and_profile_directory(self):
        plans = [row[0] for row in rt.LAUNCHER_PROBES.values()]
        directories = [row[1].lower() for row in rt.LAUNCHER_PROBES.values()]
        self.assertEqual(len(plans), len(set(plans)))
        self.assertEqual(len(directories), len(set(directories)))
        for kind, (plan, directory, output) in rt.LAUNCHER_PROBES.items():
            self.assertEqual(kind + "-plan.json", plan)
            self.assertRegex(directory, r"^HC[A-Za-z]+$")
            self.assertRegex(output, r"^[a-z]+\.json$")


class LauncherCompileFailureTests(unittest.TestCase):
    """A server that refuses the mission script stays alive on its error dialog (taped-light-probe-002).

    The launcher must notice the compile failure inside the wait loop, end the wait early with a
    distinct outcome, still stop only its own server in `finally`, and record the crash logs.
    """

    def setUp(self):
        self.loop = launcher_wait_loop(SCRIPT)

    def test_a_crash_log_alone_does_not_end_the_wait(self):
        """Native evidence: completed run taped-light-probe-003 wrote crash_2026-11-17_04-53-03.log for
        non-fatal VM exceptions (Weapon.SaveCurrentFSMState on DartGun); only the compile refusal ends early."""
        self.assertNotIn("crash_", self.loop)
        self.assertEqual(1, self.loop.count("'compile-failed'"))

    def test_wait_loop_reads_the_script_log_for_the_native_compile_refusal(self):
        self.assertIn("Test-CompileRefused", self.loop)
        reader = re.search(r"function Test-CompileRefused \{(.*?)\n\}", SCRIPT, re.S)
        self.assertIn("Can't compile", reader.group(1))
        self.assertIn("'script_*.log'", reader.group(1))

    def test_script_log_reader_shares_the_file_and_reads_a_bounded_tail(self):
        reader = re.search(r"function Test-CompileRefused \{(.*?)\n\}", SCRIPT, re.S)
        self.assertIsNotNone(reader)
        body = reader.group(1)
        self.assertIn("[System.IO.FileShare]::ReadWrite", body)
        self.assertRegex(body, r"\$tail = \d+")
        self.assertIn("Seek", body)

    def test_compile_failure_breaks_the_loop_and_still_stops_the_server(self):
        self.assertRegex(self.loop, r"\$outcome = 'compile-failed'; break")
        self.assertRegex(SCRIPT, r"(?s)\} finally \{.*Stop-Process -Id \$server\.Id")

    def test_sentinel_takes_precedence_over_a_later_crash_check(self):
        sentinel = self.loop.index("'sentinel-seen'")
        crash = self.loop.index("'compile-failed'")
        self.assertLess(sentinel, crash)

    def test_report_records_crash_logs(self):
        self.assertRegex(SCRIPT, r"crash_logs = @\(Get-FileRecords \$profiles 'crash_\*\.log'")


if __name__ == "__main__":
    unittest.main()
