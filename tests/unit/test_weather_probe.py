"""Offline stager/hook tests for the native weather precedence probe; SYNTHETIC fixtures only.

Nothing here proves how DayZ weather behaves. The generated Enforce hook is only checked
structurally and against compile-shape rules already observed natively. Runtime acceptance
stays PENDING until a native run produces observations that tools/audit/weather_report.py
can read.

Actual TDD 2026-11-17:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_weather_probe tests.unit.test_weather_report -v
RED: ImportError cannot import name 'weather_probe' from 'tools.setup' and 'weather_report' from 'tools.audit'.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from tests.unit import test_atmosphere as atmosphere_fixtures
from tools.package import atmosphere
from tools.setup import probe_runtime as rt
from tools.setup import weather_probe as probe

ROOT = Path(__file__).resolve().parents[2]
PROBE_SOURCE = ROOT / "tools/setup/weather_probe.py"
CACHE = Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"
STOCK_INIT = (b"// SYNTHETIC mission, not purchased game source\r\n"
              b"void main() {}\r\nclass CustomMission: MissionServer {}\r\n"
              b"Mission CreateCustomMission(string path)\r\n{\r\n"
              b"    return new CustomMission();\r\n}\r\n")
SYNTH_BE = b"SYNTHETIC-BATTLEYE"
SYNTH_BE_SHA = hashlib.sha256(SYNTH_BE).hexdigest()
WINDOWS_ROOT = r"D:\HollowCountryLocal\weather-test"
MISSION = "mpmissions/dayzOffline.chernarusplus"
STOCK_XML = atmosphere_fixtures.fixture()
LAUNCHER_ROW = {"weather-probe": ("weather-probe-plan.json", "HCWeatherProbe", "observations.json")}


def sha(data):
    return hashlib.sha256(data).hexdigest()


# --- compile-shape checks that the parallel probe_runtime lint is meant to enforce ---------------

_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')


def code_of(text):
    """Text with comments dropped and string literal contents blanked."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(_STRING.sub('""', line).split("//")[0] for line in text.splitlines())


def statements(text):
    """(first_line, statement) pairs, split on ; { }; a statement may span lines."""
    result, current, first, line = [], [], None, 1
    for char in code_of(text):
        if char == "\n":
            line += 1
        if char in ";{}":
            body = "".join(current).strip()
            if body:
                result.append((first, body))
            current, first = [], None
            continue
        if first is None and not char.isspace():
            first = line
        current.append(char)
    return result


def plus_counts(text):
    """Binary '+' count per statement and per physical line (strings blanked)."""
    per_statement = [(first, body.count("+")) for first, body in statements(text)]
    per_line = [(number, line.count("+")) for number, line in enumerate(code_of(text).splitlines(), 1)]
    return per_statement, per_line


def top_level_operands(expression):
    operands, depth, current = [], 0, []
    for char in expression:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == "+" and depth == 0:
            operands.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    operands.append("".join(current).strip())
    return operands


def concatenation_problems(text):
    """Operands of a string concatenation that are not provably string typed."""
    code = code_of(text)
    string_names = set(re.findall(r"\bstring\s+(\w+)", code))
    string_functions = set(re.findall(r"^[ \t]{4}string\s+(\w+)\s*\(", code, re.M))
    problems = []
    for first, body in statements(text):
        body = re.sub(r"^(?:if|while|else if)\s*\(", "(", body)
        if "+" not in body or '""' not in body:
            continue
        right = body.split("=", 1)[1] if re.match(r"^[\w\[\]\. ]+=[^=]", body) else body
        right = re.sub(r"^return\s+", "", right.strip())
        for operand in top_level_operands(right):
            if (operand == '""' or operand.endswith(".ToString()") or operand.endswith(".AsciiToString()")
                    or operand in string_names or re.match(r"^(\w+)\(", operand) and re.match(r"^(\w+)", operand).group(1) in string_functions):
                continue
            problems.append(f"line {first}: operand '{operand}' is not provably a string (use .ToString())")
    return problems


def write_source_runtime(root):
    mission = root / "stock-backup" / MISSION
    (mission / "db").mkdir(parents=True)
    files = {"init.c": STOCK_INIT, "db/types.xml": b"<types>synthetic</types>\n", "cfgweather.xml": STOCK_XML}
    plan_files = []
    for name, data in sorted(files.items()):
        (mission / name).write_bytes(data)
        plan_files.append({"path": name, "sha256": sha(data)})
    config = b'hostname = "SYNTHETIC";\r\n'
    (root / "serverDZ.cfg").write_bytes(config)
    (root / "battleye").mkdir()
    (root / "battleye/BEServer_x64.dll").write_bytes(SYNTH_BE)
    (root / "launch-plan.json").write_text(json.dumps(
        {"schema_version": 1, "status": "staged-only-not-launched", "config_sha256": sha(config),
         "mission_files": plan_files}))
    return root


def write_candidate(directory, overrides=None, **profile_changes):
    """A validated atmosphere candidate generated from the synthetic stock cfgweather.xml."""
    source = directory.parent / "stock-source.xml"
    if not source.exists():
        source.write_bytes(STOCK_XML)
    profile = dict(schema=1, name="distinctive", world="chernarusplus", build="1.30.164289",
                   source_sha256=sha(STOCK_XML), enable=True, reset=False,
                   overrides=overrides if overrides is not None else
                   {"overcast": {"limits": {"min": 0.8, "max": 0.95}, "current": {"actual": 0.85}}})
    profile.update(profile_changes)
    atmosphere.write_candidate(directory, atmosphere.generate(source, profile))
    return directory


class Workspace(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = write_source_runtime(self.root / "vanilla")
        self.dest = self.root / "weather-test"
        patcher = mock.patch.dict(rt.LAUNCHER_PROBES, LAUNCHER_ROW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def stage(self, **extra):
        base = {"battleye_sha256": SYNTH_BE_SHA, "_wsl_parent": self.root}
        base.update(extra)
        return probe.stage(self.source, self.dest, **base)


class HookRenderingTests(unittest.TestCase):
    def setUp(self):
        self.hook = probe.render_hook().decode("ascii")

    def test_hook_is_ascii_server_only_and_runs_once(self):
        self.assertTrue(probe.render_hook().isascii())
        self.assertIn("GetGame().IsServer()", self.hook)
        self.assertIn("m_HCWPStarted", self.hook)
        self.assertTrue(self.hook.lstrip().startswith("// Hollow Country DISPOSABLE"))
        for forbidden in ("GetPlayers", "PlayerBase", "ScriptRPC", "GetRPCManager", "TeleportPlayer", "GetHive",
                          "CreateObject", "ObjectDelete", "SaveWorld", "SetPosition", "OnClient"):
            self.assertNotIn(forbidden, self.hook, forbidden)

    def test_the_hook_reads_weather_and_never_writes_it(self):
        setters = re.findall(r"\.(Set\w*|MissionWeather|SuppressLightningSimulation)\s*\(", self.hook)
        self.assertEqual([], setters)
        self.assertNotRegex(self.hook, r"(?<![A-Za-z])Set[A-Z]\w*\(")
        # The only Set-like spelling allowed is the sampler's own SetStep helper name: none exists.
        self.assertNotIn("SetStorm", self.hook)

    def test_every_requested_observation_is_called_exactly_through_the_cited_getters(self):
        for api in ("GetGame().GetWeather()", "GetMissionWeather()", "GetWeatherUpdateFrozen()", ".GetActual()",
                    ".GetForecast()", ".GetNextChange()", ".GetLimits(", ".GetForecastChangeLimits(",
                    ".GetForecastTimeLimits(", ".GetWindSpeed()", ".GetWindMaximumSpeed()", ".IsDynVolFogEnabled()",
                    ".GetDynVolFogDistanceDensity()", ".GetDynVolFogHeightDensity()", ".GetDynVolFogHeightBias()",
                    ".GetTime()", "GetGame().GetTime()", "GetGame().GetWorld().GetDate(", ".GetOvercast()", ".GetFog()",
                    ".GetRain()", ".GetSnowfall()", ".GetWindMagnitude()", ".GetWindDirection()"):
            self.assertIn(api, self.hook, api)
        for name in probe.PHENOMENA:
            self.assertIn('"%s"' % name, self.hook)

    def test_sampling_is_bounded_by_inlined_sample_count_duration_cap_and_watchdog(self):
        hook = probe.render_hook(start_delay_s=40, interval_s=15, samples=12).decode("ascii")
        self.assertIn("m_HCWPMaxSamples = 12;", hook)
        self.assertIn("m_HCWPIntervalMs = 15000;", hook)
        self.assertIn("m_HCWPCapMs = %d;" % probe.cap_ms(15, 12), hook)
        self.assertIn("CallLater(HCWPBegin, 40000, false)", hook)
        self.assertIn("CallLater(HCWPWatchdog, %d, false)" % probe.watchdog_ms(40, 15, 12), hook)
        self.assertIn("m_HCWPSamples >= m_HCWPMaxSamples", hook)
        self.assertIn("m_HCWPSamples = m_HCWPSamples + 1;", hook)
        self.assertEqual(1, hook.count("CALL_CATEGORY_SYSTEM).CallLater(HCWPStep"))
        self.assertEqual([], re.findall(r"CallLater\([^;]*,\s*true\)", hook))  # no repeating timers
        self.assertGreater(probe.watchdog_ms(40, 15, 12), 40000 + 11 * 15000)

    def test_output_is_json_lines_in_the_probe_profile_directory_then_a_sentinel_written_last(self):
        self.assertIn('"$profile:HCWeatherProbe/observations.json"', self.hook)
        self.assertIn('"$profile:HCWeatherProbe/complete.txt"', self.hook)
        self.assertEqual(2, self.hook.count("FileMode.WRITE"))  # header and sentinel only
        self.assertIn("FileMode.APPEND", self.hook)
        self.assertEqual(2, len(re.findall(r"\$profile:", self.hook)))
        self.assertLess(self.hook.index("HCWPAppend(HCWPEndLine"), self.hook.index("m_HCWPSentinel, FileMode.WRITE"))
        self.assertIn("earlier probe output exists; not overwriting", self.hook)
        for key in ('"header"', '"sample"', '"end"'):
            self.assertIn(key, self.hook)

    def test_numbers_are_emitted_as_json_strings_so_unobserved_float_formatting_cannot_break_json(self):
        self.assertIn("string HCWPFloat(", self.hook)
        self.assertRegex(self.hook, r"HCWPQuoted\(value\.ToString\(\)\)")

    def test_invalid_parameters_are_refused(self):
        for kwargs in ({"start_delay_s": 4}, {"start_delay_s": 601}, {"interval_s": 4}, {"interval_s": 601},
                       {"samples": 5}, {"samples": probe.MAX_SAMPLES + 1}, {"samples": True}, {"interval_s": 1.5},
                       {"interval_s": 600, "samples": 720}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                probe.render_hook(**kwargs)

    def test_generated_hook_passes_the_shared_native_compile_rule_lint(self):
        self.assertEqual([], rt.lint_hook(self.hook))
        native = rt.native_type_names(CACHE) if (CACHE / "3_Game").is_dir() else frozenset()
        self.assertEqual([], rt.lint_hook(self.hook, native_types=native))

    def test_no_identifier_equals_an_engine_type_name_even_without_the_cache(self):
        for match in rt._DECLARATION.finditer(code_of(self.hook)):
            self.assertNotIn(match.group(2), rt.ENGINE_TYPE_NAMES)

    def test_every_statement_has_at_most_eight_binary_plus_operators(self):
        per_statement, per_line = plus_counts(self.hook)
        self.assertLessEqual(max(count for _n, count in per_statement), probe.MAX_PLUS_PER_STATEMENT)
        self.assertLessEqual(max(count for _n, count in per_line), probe.MAX_PLUS_PER_STATEMENT)
        self.assertEqual(8, probe.MAX_PLUS_PER_STATEMENT)
        self.assertNotIn("++", code_of(self.hook))
        self.assertNotIn("+=", code_of(self.hook))
        self.assertEqual([], probe.statement_problems(self.hook))

    def test_every_number_in_a_string_concatenation_goes_through_explicit_to_string(self):
        self.assertEqual([], concatenation_problems(self.hook))
        self.assertEqual([], probe.statement_problems(self.hook))

    def test_the_concatenation_checks_flag_the_real_failures(self):
        nine = 'void F()\n{\n    string s = "a" + b + "c" + d + "e" + f + "g" + h + "i" + j;\n}\n'
        self.assertTrue(probe.statement_problems(nine))
        self.assertTrue(any("'+'" in p or "operators" in p for p in probe.statement_problems(nine)))
        eight = 'void F()\n{\n    string s = "a" + b + "c" + d + "e" + f + "g" + h + "i";\n}\n'
        self.assertFalse([p for p in probe.statement_problems(eight) if "operators" in p])
        implicit = 'void F()\n{\n    int count = 3;\n    string s = "n=" + count;\n}\n'
        self.assertTrue(concatenation_problems(implicit))
        self.assertTrue(probe.statement_problems(implicit))
        explicit = 'void F()\n{\n    int count = 3;\n    string s = "n=" + count.ToString();\n}\n'
        self.assertEqual([], concatenation_problems(explicit))
        self.assertEqual([], probe.statement_problems(explicit))
        multi_line = 'void F()\n{\n    string s = "a" + b + "c" + d\n        + "e" + f + "g" + h + "i" + j;\n}\n'
        self.assertTrue([p for p in probe.statement_problems(multi_line) if "operators" in p])
        numeric_only = 'void F()\n{\n    int total = 1 + 2 + 3;\n}\n'
        self.assertEqual([], probe.statement_problems(numeric_only))

    def test_no_ternary_leading_operator_exponent_literal_or_shared_scope_redeclaration(self):
        code = code_of(self.hook)
        self.assertNotIn("?", code)
        self.assertEqual([], [l for l in code.splitlines() if re.match(r"^\s*(\|\||&&)", l)])
        self.assertIsNone(re.search(r"\b\d+(?:\.\d+)?[eE][+-]?\d+\b", code))
        self.assertEqual([], [i for i in rt.lint_hook(self.hook) if "duplicate local" in i])

    def test_out_parameters_are_declared_before_the_call(self):
        for call in ("GetLimits(", "GetForecastChangeLimits(", "GetForecastTimeLimits(", "GetDate(", "GetWorldName(",
                     "GetVersion("):
            index = self.hook.index(call)
            before = self.hook[:index]
            arguments = self.hook[index + len(call):self.hook.index(")", index)]
            for name in [a.strip() for a in arguments.split(",")]:
                self.assertRegex(before, r"(?:float|int|string)\s+%s\s*=?" % re.escape(name), call + " " + name)


class NativeCitationTests(unittest.TestCase):
    """Every API cited in the module docstring is looked up at its file:line in the native script cache."""

    def citations(self):
        text = probe.__doc__
        return re.findall(r"^\s+(\S+?)\s+->\s+(\S+?):(\d+)", text, re.M)

    def test_the_docstring_cites_every_native_api_the_hook_calls(self):
        cited = {api for api, _file, _line in self.citations()}
        for api in ("GetWeather", "GetMissionWeather", "GetWeatherUpdateFrozen", "GetActual", "GetForecast",
                    "GetNextChange", "GetLimits", "GetForecastChangeLimits", "GetForecastTimeLimits", "GetWindSpeed",
                    "GetWindMaximumSpeed", "IsDynVolFogEnabled", "GetDynVolFogDistanceDensity",
                    "GetDynVolFogHeightDensity", "GetDynVolFogHeightBias", "Weather.GetTime", "CGame.GetTime", "GetDate",
                    "GetOvercast", "GetFog", "GetRain", "GetSnowfall", "GetWindMagnitude", "GetWindDirection",
                    "CallLater", "OpenFile", "FPrintln", "MakeDirectory", "FileExist", "GetWorldName", "GetVersion",
                    "float.ToString", "int.ToString", "int.AsciiToString", "IsServer"):
            self.assertIn(api, cited, api)

    def test_each_citation_resolves_in_the_installed_native_script_cache(self):
        if not (CACHE / "3_Game").is_dir():
            self.skipTest("native script cache not extracted")
        for api, name, line in self.citations():
            lines = (CACHE / name).read_text(encoding="utf-8", errors="replace").splitlines()
            leaf = api.split(".")[-1]
            self.assertIn(leaf, lines[int(line) - 1], f"{api} not at {name}:{line}")


class StagerTests(Workspace):
    def test_stock_run_stages_the_untouched_stock_cfgweather_and_records_its_hash(self):
        plan = self.stage()
        staged = (self.dest / MISSION / "cfgweather.xml").read_bytes()
        self.assertEqual(STOCK_XML, staged)
        self.assertEqual("weather-probe", plan["kind"])
        self.assertEqual("stock", plan["probe"]["cfgweather"]["variant"])
        self.assertEqual(sha(STOCK_XML), plan["probe"]["cfgweather"]["staged_sha256"])
        self.assertEqual(sha(STOCK_XML), plan["probe"]["cfgweather"]["stock_sha256"])
        self.assertIsNone(plan["probe"]["cfgweather"]["candidate"])
        origin = {f["path"]: f["origin"] for f in plan["mission_files"]}
        self.assertEqual("stock-copy", origin["cfgweather.xml"])
        self.assertEqual("instrumented", origin["init.c"])

    def test_candidate_run_replaces_only_cfgweather_with_the_validated_candidate_bytes(self):
        candidate = write_candidate(self.root / "candidate")
        plan = self.stage(candidate=candidate, candidate_source=self.root / "stock-source.xml")
        staged = (self.dest / MISSION / "cfgweather.xml").read_bytes()
        self.assertEqual((candidate / "cfgweather.xml").read_bytes(), staged)
        self.assertNotEqual(STOCK_XML, staged)
        info = plan["probe"]["cfgweather"]
        self.assertEqual("candidate", info["variant"])
        self.assertEqual(sha(staged), info["staged_sha256"])
        self.assertEqual(sha(STOCK_XML), info["stock_sha256"])
        self.assertEqual({"name": "distinctive", "source_verified": True, "enable": True, "reset": False},
                         {k: info["candidate"][k] for k in ("name", "source_verified", "enable", "reset")})
        self.assertEqual(sha(staged), info["candidate"]["sha256"])
        self.assertGreater(info["candidate"]["changes"], 0)
        origin = {f["path"]: f["origin"] for f in plan["mission_files"]}
        self.assertEqual("treatment-replacement", origin["cfgweather.xml"])
        for name in ("db/types.xml",):
            self.assertEqual((self.source / "stock-backup" / MISSION / name).read_bytes(),
                             (self.dest / MISSION / name).read_bytes())

    def test_unvalidated_or_tampered_candidates_are_refused_before_anything_is_created(self):
        candidate = write_candidate(self.root / "candidate")
        xml = candidate / "cfgweather.xml"
        xml.write_bytes(xml.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            self.stage(candidate=candidate)
        self.assertFalse(self.dest.exists())
        partial = self.root / "partial"
        partial.mkdir()
        (partial / "cfgweather.xml").write_bytes(STOCK_XML)
        for bad in (partial, self.root / "missing", self.source / "launch-plan.json"):
            with self.subTest(bad=bad), self.assertRaises((ValueError, OSError)):
                self.stage(candidate=bad)
        self.assertFalse(self.dest.exists())

    def test_a_candidate_generated_from_a_different_source_or_world_is_refused(self):
        other = STOCK_XML.replace(b'actual="0"', b'actual="0.0"', 1)
        self.assertNotEqual(other, STOCK_XML)
        source = self.root / "other-source.xml"
        source.write_bytes(other)
        profile = dict(schema=1, name="other", world="chernarusplus", build="1.30.164289", source_sha256=sha(other),
                       enable=True, reset=False, overrides={"fog": {"limits": {"max": 0.5}}})
        atmosphere.write_candidate(self.root / "foreign", atmosphere.generate(source, profile))
        with self.assertRaisesRegex(ValueError, "stock cfgweather"):
            self.stage(candidate=self.root / "foreign")
        sakhal = write_candidate(self.root / "sakhal", world="sakhal")
        with self.assertRaisesRegex(ValueError, "chernarusplus"):
            self.stage(candidate=sakhal)
        self.assertFalse(self.dest.exists())

    def test_candidate_reconstruction_against_a_wrong_pinned_source_is_refused(self):
        candidate = write_candidate(self.root / "candidate")
        wrong = self.root / "wrong.xml"
        wrong.write_bytes(STOCK_XML + b"<!-- x -->")
        with self.assertRaises(ValueError):
            self.stage(candidate=candidate, candidate_source=wrong)
        self.assertFalse(self.dest.exists())

    def test_without_a_pinned_source_the_candidate_is_integrity_checked_but_not_source_verified(self):
        plan = self.stage(candidate=write_candidate(self.root / "candidate"))
        self.assertFalse(plan["probe"]["cfgweather"]["candidate"]["source_verified"])

    def test_the_stock_mission_must_contain_cfgweather_xml(self):
        mission = self.source / "stock-backup" / MISSION
        (mission / "cfgweather.xml").unlink()
        plan_path = self.source / "launch-plan.json"
        data = json.loads(plan_path.read_text())
        data["mission_files"] = [f for f in data["mission_files"] if f["path"] != "cfgweather.xml"]
        plan_path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "cfgweather.xml"):
            self.stage()
        self.assertFalse(self.dest.exists())

    def test_plan_is_accepted_by_the_launcher_checks_and_records_probe_limits_and_outputs(self):
        plan = self.stage(start_delay_s=40, interval_s=20, samples=30)
        self.assertEqual("staged-only-not-launched", plan["status"])
        self.assertEqual(WINDOWS_ROOT, plan["runtime_root"])
        plan_path = self.dest / "weather-probe-plan.json"
        self.assertEqual(plan, json.loads(plan_path.read_text()))
        # launcher_problems inventories every file, and the plan file is by design not in staged_files.
        held = self.root / "held-plan.json"
        plan_path.rename(held)
        try:
            self.assertEqual([], rt.launcher_problems(plan, self.dest, "weather-probe-plan.json"))
        finally:
            held.rename(plan_path)
        info = plan["probe"]
        self.assertEqual(("server-only-no-clients", 0), (info["mode"], info["clients"]))
        self.assertEqual((40, 20, 30), (info["start_delay_s"], info["interval_s"], info["samples"]))
        self.assertEqual(probe.cap_ms(20, 30), info["cap_ms"])
        self.assertEqual(probe.watchdog_ms(40, 20, 30), info["watchdog_ms"])
        self.assertEqual("profiles/HCWeatherProbe/observations.json", info["output_relative_path"])
        self.assertEqual("profiles/HCWeatherProbe/complete.txt", info["sentinel_relative_path"])
        self.assertEqual("weather-probe-observations", info["observations_kind"])
        self.assertEqual("PENDING", plan["acceptance"])
        self.assertGreaterEqual(info["wait_minutes"], probe.worst_case_minutes(40, 20, 30))
        self.assertTrue(5 <= info["wait_minutes"] <= 120)
        for argument in plan["arguments"]:
            self.assertNotRegex(argument, r"(?i)-mod=|-servermod=|-filepatching|-connect")

    def test_init_c_gets_the_generated_hook_and_its_hash_is_recorded(self):
        plan = self.stage()
        init = (self.dest / MISSION / "init.c").read_bytes()
        self.assertIn(b"return new HCDisposableDiagnosticMission();", init)
        hook = probe.render_hook()
        self.assertEqual(plan["probe"]["hook_sha256"], sha(hook))
        self.assertEqual(plan["probe"]["hook_bytes"], len(hook))
        self.assertEqual(plan["probe"]["hook_sha256"], sha(init[init.index(b"\n\n// Hollow Country DISPOSABLE"):]))

    def test_the_stage_is_deterministic_for_both_runs_hook_bytes(self):
        first = self.stage()
        self.dest = self.root / "weather-test2"
        second = self.stage()
        self.assertEqual(first["probe"]["hook_sha256"], second["probe"]["hook_sha256"])

    def test_wait_minutes_must_cover_the_worst_case_and_the_launcher_limit(self):
        for wait in (5, probe.worst_case_minutes(30, 30, 60) - 1, 121):
            with self.subTest(wait=wait), self.assertRaises(ValueError):
                self.stage(wait_minutes=wait)
            self.assertFalse(self.dest.exists())

    def test_a_run_too_long_for_the_launcher_wait_limit_is_refused(self):
        with self.assertRaises(ValueError):
            self.stage(interval_s=300, samples=probe.MAX_SAMPLES)
        self.assertFalse(self.dest.exists())

    def test_a_missing_launcher_row_is_refused_before_anything_is_created(self):
        with mock.patch.dict(rt.LAUNCHER_PROBES, clear=False):
            rt.LAUNCHER_PROBES.pop("weather-probe")
            with self.assertRaisesRegex(ValueError, "LAUNCHER_PROBES"):
                self.stage()
        self.assertFalse(self.dest.exists())

    def test_existing_destination_and_the_verified_runtime_name_are_never_reused(self):
        self.dest.mkdir()
        with self.assertRaises(ValueError):
            self.stage()
        with self.assertRaises(ValueError):
            probe.stage(self.source, self.root / "vanilla-p0-001", battleye_sha256=SYNTH_BE_SHA, _wsl_parent=self.root)

    def test_the_stager_builds_on_probe_runtime_instead_of_duplicating_its_staging_code(self):
        text = PROBE_SOURCE.read_text(encoding="utf-8")
        for duplicated in ("def verify_source", "def build_runtime", "def lint_hook", "def _hash_file", "def write_plan",
                           "def windows_runtime_root", "def server_arguments", "NAME_RULE =", "SERVER_EXE ="):
            self.assertNotIn(duplicated, text)
        for used in ("rt.begin(", "rt.build_runtime(", "rt.plan_header(", "rt.plan_runtime_fields(", "rt.write_plan(",
                     "rt.lint_hook("):
            self.assertIn(used, text)

    def test_staging_never_launches_anything_or_touches_the_network(self):
        text = PROBE_SOURCE.read_text(encoding="utf-8")
        for forbidden in ("subprocess", "socket", "urllib", "os.system", "Popen", "powershell", "wine"):
            self.assertNotIn(forbidden, text)

    def test_cli_stages_and_reports_the_hook_hash_and_fails_on_reuse(self):
        stdout = mock.MagicMock()
        with mock.patch.object(probe, "WSL_PARENT", self.root), \
                mock.patch.object(rt, "WSL_PARENT", self.root), \
                mock.patch.object(probe, "BATTLEYE_SHA256", SYNTH_BE_SHA), \
                mock.patch("builtins.print", stdout):
            code = probe.main(["--destination", str(self.dest), "--source-runtime", str(self.source),
                               "--native-scripts", str(self.root / "no-cache")])
            self.assertEqual(0, code)
            self.assertTrue((self.dest / "weather-probe-plan.json").is_file())
            self.assertIn("hook_sha256=", " ".join(str(c) for c in stdout.call_args_list))
            self.assertEqual(1, probe.main(["--destination", str(self.dest), "--source-runtime", str(self.source)]))


if __name__ == "__main__":
    unittest.main()
