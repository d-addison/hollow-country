"""Offline stager/hook tests for the native weather precedence probe; SYNTHETIC fixtures only.

Nothing here proves how DayZ weather behaves. The generated Enforce hook is only checked
structurally and against compile-shape rules already observed natively. Runtime acceptance
stays PENDING until a native run produces observations that tools/audit/weather_report.py
can read.

Actual TDD 2026-11-17:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_weather_probe tests.legacy.test_weather_report -v
RED: ImportError cannot import name 'weather_probe' from 'tools.setup' and 'weather_report' from 'tools.audit'.
"""
import ast
import copy
import hashlib
import heapq
import inspect
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tests.legacy import test_atmosphere as atmosphere_fixtures
from tools.package import atmosphere
from tools.setup import diagnostic_mission as dm
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
# The rows the coordinator adds to the shared modules at integration; this module must not register them.
PURPOSE_ROW = {"weather-probe": ("disposable-weather-probe", None,
                                 ["server mode", "fresh storage and profiles", "no clients",
                                  "inspect observation completeness separately from startup"])}


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
        for registry, row in ((rt.LAUNCHER_PROBES, LAUNCHER_ROW), (dm._PURPOSES, PURPOSE_ROW)):
            patcher = mock.patch.dict(registry, row)
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


# --- a tiny Enforce-subset interpreter: runs the generated hook against a SYNTHETIC engine --------
# It translates the hook's line-oriented Enforce into Python and drives it with fake adapters. It
# proves the hook's control flow (guards, ordering, timing) only. It says nothing about how DayZ
# behaves: every engine value below is invented and distinct per getter so swapped getters show up.

_DECLARATION = re.compile(r"^(?:int|string|bool|float|FileHandle|Weather) (\w+)(?: = (.*))?$")
_OUT_CALL = re.compile(r"^(.*)\.(GetWorldName|GetVersion|GetDate|GetLimits|GetForecastChangeLimits|"
                       r"GetForecastTimeLimits)\((.*)\)$")
_VALUE_METHODS = {"ToString": "_tostring", "AsciiToString": "_ascii", "Length": "_length",
                  "Substring": "_substring", "IndexOf": "_indexof"}
_STRING_LITERAL = re.compile(r'("[^"]*")')


def _outside_strings(text, function):
    return "".join(part if index % 2 else function(part) for index, part in enumerate(_STRING_LITERAL.split(text)))


def _fix_expression(text):
    def fix(part):
        part = part.replace("&&", " and ").replace("||", " or ")
        part = re.sub(r"!(?!=)", "not ", part)
        part = re.sub(r"\btrue\b", "True", part)
        part = re.sub(r"\bfalse\b", "False", part)
        part = re.sub(r"(?<![\w.])(m_HCWP\w+|HCWP\w+)", r"self.\1", part)
        return part
    return _outside_strings(text, fix)


def transpile(source):
    """Python source for the hook's one class; only the Enforce forms the generated hook uses."""
    fields, body = [], []
    for raw in source.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("//") or stripped in ("{", "}"):
            continue
        pad = " " * (len(raw) - len(raw.lstrip()))
        if raw.startswith("class "):
            body.append("class HCMission(CustomMission):")
            continue
        field = re.match(r"^\s+protected \w+ (m_\w+) = (.+);$", raw)
        if field:
            fields.append(_fix_expression("        " + field.group(1) + " = " + field.group(2)))
            continue
        method = re.match(r"^\s+(?:override )?(?:void|string|bool|float|int) (\w+)\((.*)\)$", raw)
        if method:
            arguments = [re.sub(r"^\w+\s+", "", part.strip()) for part in method.group(2).split(",") if part.strip()]
            body.append(f"{pad}def {method.group(1)}({', '.join(['self'] + arguments)}):")
            continue
        text = stripped[:-1] if stripped.endswith(";") else stripped
        condition = re.match(r"^if \((.*)\)$", text)
        declaration = _DECLARATION.match(text)
        out_call = _OUT_CALL.match(text) if " = " not in text else None
        replace = re.match(r"^(\w+)\.Replace\((.*)\)$", text)
        if condition:
            line = "if " + condition.group(1) + ":"
        elif declaration:
            line = declaration.group(1) + " = " + (declaration.group(2) if declaration.group(2) is not None else '""')
        elif out_call:
            targets = [part.strip() for part in out_call.group(3).split(",")]
            line = ", ".join(targets) + " = " + out_call.group(1) + "." + out_call.group(2) + "()"
        elif replace:
            line = f"{replace.group(1)} = {replace.group(1)}.replace({replace.group(2)})"
        elif text == "return":
            line = "return"
        elif text == "super.OnInit()":
            line = "super().OnInit()"
        else:
            line = text
        body.append(pad + _fix_expression(line))
    init = ["    def __init__(self):"] + (fields or ["        pass"])
    return "\n".join([body[0]] + init + body[1:]) + "\n"


class _ValueCalls(ast.NodeTransformer):
    def visit_Call(self, node):
        self.generic_visit(node)
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr in _VALUE_METHODS:
            return ast.Call(func=ast.Name(id=_VALUE_METHODS[function.attr], ctx=ast.Load()),
                            args=[function.value] + node.args, keywords=[])
        return node


def _format_float(value):
    return format(value, ".6g")


class FakeWeatherPhenomenon:
    def __init__(self, index):
        self.values = {"actual": 0.31 + index / 100, "forecast": 0.62 + index / 100, "next_change": 700 + index,
                       "limits": (0.11 + index / 100, 0.91 + index / 100),
                       "change": (0.02 + index / 100, 0.72 + index / 100),
                       "time": (61 + index, 901 + index)}

    def GetActual(self):
        return self.values["actual"]

    def GetForecast(self):
        return self.values["forecast"]

    def GetNextChange(self):
        return self.values["next_change"]

    def GetLimits(self):
        return self.values["limits"]

    def GetForecastChangeLimits(self):
        return self.values["change"]

    def GetForecastTimeLimits(self):
        return self.values["time"]


OBSERVATIONS_PATH = "$profile:HCWeatherProbe/observations.json"
SENTINEL_PATH = "$profile:HCWeatherProbe/complete.txt"


class FakeEngine:
    """A synthetic engine: virtual clock, call queue, in-memory profile files and fake weather."""

    def __init__(self, hook, files=None, now_ms=100000, server=True):
        self.now, self.files, self.directories = now_ms, dict(files or {}), set()
        self.queue, self.counter, self.server = [], 0, server
        self.prints, self.delays, self.observations_at_sentinel_open = [], [], None
        self.handles, self.next_handle = {}, 1
        self.weather_offset = 4321.5
        self.phenomena = [FakeWeatherPhenomenon(index) for index in range(6)]
        namespace = self.namespace()
        tree = _ValueCalls().visit(ast.parse(transpile(hook.decode("ascii"))))
        exec(compile(ast.fix_missing_locations(tree), "<hook>", "exec"), namespace)
        self.mission = namespace["HCMission"]()

    def namespace(self):
        engine = self

        class CustomMission:
            def OnInit(self):
                pass

        class Weather:
            def GetTime(_self):
                # Elapsed weather seconds; deliberately not derived from the millisecond game clock alone.
                return engine.weather_offset + engine.now / 1000.0

            def GetMissionWeather(_self):
                return True

            def GetWeatherUpdateFrozen(_self):
                return False

            def GetWindSpeed(_self):
                return 3.5

            def GetWindMaximumSpeed(_self):
                return 21.5

            def IsDynVolFogEnabled(_self):
                return True

            def GetDynVolFogDistanceDensity(_self):
                return 0.125

            def GetDynVolFogHeightDensity(_self):
                return 0.25

            def GetDynVolFogHeightBias(_self):
                return 42.5

        for index, name in enumerate(("Overcast", "Fog", "Rain", "WindMagnitude", "WindDirection", "Snowfall")):
            setattr(Weather, "Get" + name, (lambda position: lambda _self: engine.phenomena[position])(index))

        class World:
            def GetDate(_self):
                return 2026, 11, 17, 9, 30

        class Queue:
            def CallLater(_self, function, delay, repeat):
                assert repeat is False
                engine.counter += 1
                engine.delays.append((function.__name__, delay))
                heapq.heappush(engine.queue, (engine.now + delay, engine.counter, function))

        class Game:
            def IsServer(_self):
                return engine.server

            def GetTime(_self):
                return engine.now

            def GetWeather(_self):
                return Weather()

            def GetWorld(_self):
                return World()

            def GetWorldName(_self):
                return "ChernarusPlus"

            def GetVersion(_self):
                return "1.30.164289"

            def GetCallQueue(_self, _category):
                return Queue()

        class FileMode:
            WRITE, APPEND = "write", "append"

        def open_file(path, mode):
            if mode == "write":
                if path == SENTINEL_PATH:
                    engine.observations_at_sentinel_open = engine.files.get(OBSERVATIONS_PATH)
                engine.files[path] = ""
            else:
                engine.files.setdefault(path, "")
            handle, engine.next_handle = engine.next_handle, engine.next_handle + 1
            engine.handles[handle] = path
            return handle

        def make_directory(path):
            engine.directories.add(path)
            return True

        def fprintln(handle, line):
            engine.files[engine.handles[handle]] += line + "\n"

        return {
            "CustomMission": CustomMission, "GetGame": lambda: Game(), "CALL_CATEGORY_SYSTEM": 0,
            "FileMode": FileMode, "OpenFile": open_file, "CloseFile": lambda handle: None, "FPrintln": fprintln,
            "FileExist": lambda path: path in engine.files or path in engine.directories,
            "MakeDirectory": make_directory, "Print": engine.prints.append,
            "_tostring": lambda value: str(value) if isinstance(value, int) else _format_float(value),
            "_ascii": chr, "_length": len, "_substring": lambda text, start, length: text[start:start + length],
            "_indexof": lambda text, needle: text.find(needle),
        }

    def start(self):
        self.mission.OnInit()
        return self

    def run_until(self, until_ms):
        while self.queue and self.queue[0][0] <= until_ms:
            due, _order, function = heapq.heappop(self.queue)
            self.now = max(self.now, due)
            function()
        self.now = max(self.now, until_ms)

    def stall(self, milliseconds):
        self.now += milliseconds

    def drop(self, name):
        self.queue = [entry for entry in self.queue if entry[2].__name__ != name]
        heapq.heapify(self.queue)

    def rows(self):
        return [json.loads(line) for line in self.files.get(OBSERVATIONS_PATH, "").splitlines()]

    @property
    def sentinel(self):
        return self.files.get(SENTINEL_PATH)


class HookBehaviourTests(unittest.TestCase):
    """The generated hook run against the synthetic engine above (control flow only)."""

    START_S, INTERVAL_S, SAMPLES = 5, 5, 6

    def engine(self, **extra):
        hook = probe.render_hook(self.START_S, self.INTERVAL_S, self.SAMPLES)
        return FakeEngine(hook, **extra).start()

    def full_run(self):
        engine = self.engine()
        engine.run_until(engine.now + 600000)
        return engine

    def test_a_clean_run_writes_header_ordered_samples_a_complete_end_record_then_the_sentinel(self):
        engine = self.full_run()
        rows = engine.rows()
        self.assertEqual(["header"] + ["sample"] * 6 + ["end"], [row["type"] for row in rows])
        self.assertEqual("weather-probe-observations", rows[0]["kind"])
        self.assertEqual((6, 5000), (rows[0]["planned_samples"], rows[0]["interval_ms"]))
        self.assertEqual(list(range(6)), [row["seq"] for row in rows[1:7]])
        self.assertEqual({"type": "end", "status": "complete", "samples": 6, "write_errors": 0},
                         {k: rows[-1][k] for k in ("type", "status", "samples", "write_errors")})
        self.assertEqual("status=complete samples=6 write_errors=0\n", engine.sentinel)

    def test_samples_are_spaced_by_exactly_the_configured_interval(self):
        engine = self.full_run()
        times = [row["game_ms"] for row in engine.rows()[1:7]]
        self.assertEqual([self.INTERVAL_S * 1000] * 5, [b - a for a, b in zip(times, times[1:])])
        self.assertEqual(5, sum(1 for name, delay in engine.delays if name == "HCWPStep" and delay == 5000))

    def test_every_sampled_value_comes_from_its_own_native_getter(self):
        engine = self.full_run()
        sample = engine.rows()[1]
        fake = {name: engine.phenomena[index] for index, name in enumerate(probe.PHENOMENA)}
        for name, source in fake.items():
            row = sample["phenomena"][name]
            values = source.values
            expected = {"actual": values["actual"], "forecast": values["forecast"], "next_change": values["next_change"],
                        "limit_min": values["limits"][0], "limit_max": values["limits"][1],
                        "change_min": values["change"][0], "change_max": values["change"][1],
                        "time_min": values["time"][0], "time_max": values["time"][1]}
            self.assertEqual({key: _format_float(value) for key, value in expected.items()}, row, name)
        self.assertEqual("3.5", sample["wind_speed"])
        self.assertEqual("21.5", sample["wind_max_speed"])
        self.assertEqual((True, False), (sample["mission_weather"], sample["update_frozen"]))
        self.assertEqual((2026, 11, 17, 9, 30), tuple(sample[k] for k in ("year", "month", "day", "hour", "minute")))

    def test_weather_time_is_the_weather_clock_in_seconds_not_the_millisecond_game_clock(self):
        engine = self.full_run()
        for row in engine.rows()[1:7]:
            self.assertEqual(_format_float(engine.weather_offset + row["game_ms"] / 1000.0), row["weather_time"])
            self.assertNotEqual(str(row["game_ms"]), row["weather_time"])
        first, second = engine.rows()[1:3]
        self.assertEqual(5.0, float(second["weather_time"]) - float(first["weather_time"]))

    def test_the_hook_output_round_trips_through_the_report(self):
        from tools.audit import weather_report
        engine = self.full_run()
        text = engine.files[OBSERVATIONS_PATH]
        result = weather_report.evaluate(text, STOCK_XML, sentinel=engine.sentinel)
        self.assertEqual([], result["issues"])
        self.assertEqual("complete", result["status"])
        self.assertEqual(6, result["samples"])

    def test_the_sentinel_is_written_only_after_the_end_record_is_in_the_observations(self):
        engine = self.full_run()
        before = engine.observations_at_sentinel_open
        self.assertIsNotNone(before)
        self.assertEqual("end", json.loads(before.splitlines()[-1])["type"])

    def test_existing_probe_output_is_never_overwritten_and_nothing_is_scheduled(self):
        for existing in ({OBSERVATIONS_PATH: "earlier run\n"}, {SENTINEL_PATH: "earlier sentinel\n"},
                         {OBSERVATIONS_PATH: "earlier run\n", SENTINEL_PATH: "earlier sentinel\n"}):
            with self.subTest(existing=sorted(existing)):
                engine = self.engine(files=existing)
                engine.run_until(engine.now + 600000)
                self.assertEqual(existing, engine.files)
                self.assertTrue(any("not overwriting" in line for line in engine.prints), engine.prints)
                self.assertFalse([name for name, _delay in engine.delays if name == "HCWPStep"])

    def test_a_stalled_clock_past_the_duration_cap_ends_the_run_partial_instead_of_sampling_on(self):
        engine = self.engine()
        cap = probe.cap_ms(self.INTERVAL_S, self.SAMPLES)
        engine.run_until(engine.now + 5000 + 12000)  # begin plus a few samples
        taken = len(engine.rows()) - 1
        self.assertTrue(1 <= taken < self.SAMPLES)
        engine.stall(cap + 1000)  # still before the watchdog, which fires 60 s after the cap
        engine.run_until(engine.now + 1000)
        rows = engine.rows()
        self.assertEqual("end", rows[-1]["type"])
        self.assertEqual(("partial", taken), (rows[-1]["status"], rows[-1]["samples"]))
        self.assertEqual("status=partial samples=%d write_errors=0\n" % taken, engine.sentinel)
        self.assertEqual(taken, len([row for row in rows if row["type"] == "sample"]))

    def test_the_watchdog_finishes_a_run_whose_sampling_chain_stopped(self):
        engine = self.engine()
        engine.run_until(engine.now + 5000 + 7000)
        taken = len(engine.rows()) - 1
        self.assertTrue(1 <= taken < self.SAMPLES)
        engine.drop("HCWPStep")  # the chain dies without finishing
        engine.run_until(engine.now + 600000)
        rows = engine.rows()
        self.assertEqual(("end", "partial", taken), (rows[-1]["type"], rows[-1]["status"], rows[-1]["samples"]))
        self.assertEqual("status=partial samples=%d write_errors=0\n" % taken, engine.sentinel)

    def test_the_watchdog_does_not_touch_a_run_that_already_finished(self):
        engine = self.full_run()
        before = dict(engine.files)
        engine.run_until(engine.now + 600000)
        self.assertEqual(before, engine.files)

    def test_a_watchdog_before_the_file_opened_leaves_no_output(self):
        engine = self.engine(files={})
        engine.drop("HCWPBegin")
        engine.run_until(engine.now + 600000)
        self.assertEqual({}, engine.files)
        self.assertTrue(any("watchdog fired before" in line for line in engine.prints))

    def test_only_a_server_runs_the_sampler(self):
        engine = FakeEngine(probe.render_hook(5, 5, 6), server=False).start()
        self.assertEqual([], engine.queue)
        self.assertEqual({}, engine.files)


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
        plan = self.stage(candidate=candidate)
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

    def tamper(self, candidate, mutate):
        """Change the candidate's cfgweather.xml and recompute every hash so metadata still agrees."""
        path = candidate / "cfgweather.xml"
        tree = ET.fromstring(path.read_bytes())
        mutate(tree)
        data = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
        path.write_bytes(data)
        report_path = candidate / "atmosphere-report.json"
        report = json.loads(report_path.read_text())
        report["candidate_sha256"] = sha(data)
        report_path.write_bytes(atmosphere.encode(report))
        manifest_path = candidate / "atmosphere-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["cfgweather.xml"] = sha(data)
        manifest["files"]["atmosphere-report.json"] = sha(report_path.read_bytes())
        manifest_path.write_bytes(atmosphere.encode(manifest))

    def test_an_unreported_candidate_change_is_refused_even_when_the_metadata_hashes_were_recomputed(self):
        candidate = write_candidate(self.root / "candidate")
        self.tamper(candidate, lambda tree: tree.find("fog/limits").set("max", "0.5"))
        # Precondition: without the stock the tampered candidate is internally consistent.
        atmosphere.validate_candidate(candidate)
        with self.assertRaisesRegex(ValueError, "reconstruction"):
            self.stage(candidate=candidate)
        self.assertFalse(self.dest.exists())

    def test_a_candidate_replaced_between_admission_and_reconstruction_is_refused(self):
        first = write_candidate(self.root / "first")
        second = write_candidate(self.root / "second", overrides={"fog": {"limits": {"min": 0.3, "max": 0.5},
                                                                          "current": {"actual": 0.4}}})
        self.assertNotEqual((first / "cfgweather.xml").read_bytes(), (second / "cfgweather.xml").read_bytes())
        real = probe.load_candidate

        def swapping(candidate):
            loaded = real(candidate)  # admitted: the first candidate's bytes and digest
            for name in ("cfgweather.xml", "atmosphere-report.json", "atmosphere-manifest.json"):
                (Path(candidate) / name).write_bytes((second / name).read_bytes())
            return loaded
        atmosphere.validate_candidate(second, source=self.root / "vanilla" / "stock-backup" / MISSION / "cfgweather.xml")
        with mock.patch.object(probe, "load_candidate", swapping):
            with self.assertRaisesRegex(ValueError, "changed during reconstruction"):
                self.stage(candidate=first)
        self.assertFalse(self.dest.exists())

    def test_reconstruction_refuses_bytes_that_differ_from_the_admitted_digest(self):
        candidate = write_candidate(self.root / "candidate")
        probe.reconstruct_candidate(candidate, STOCK_XML, sha((candidate / "cfgweather.xml").read_bytes()))
        with self.assertRaisesRegex(ValueError, "changed during reconstruction"):
            probe.reconstruct_candidate(candidate, STOCK_XML, "0" * 64)

    def test_the_reconstruction_source_is_the_held_stock_not_a_caller_supplied_file(self):
        seen = []
        real = atmosphere.validate_candidate

        def spy(candidate, source=None):
            seen.append(None if source is None else Path(source).read_bytes())
            return real(candidate, source=source)
        with mock.patch.object(atmosphere, "validate_candidate", spy):
            plan = self.stage(candidate=write_candidate(self.root / "candidate"))
        self.assertEqual(STOCK_XML, seen[-1])
        self.assertIs(True, plan["probe"]["cfgweather"]["candidate"]["source_verified"])
        self.assertNotIn("candidate_source", inspect.signature(probe.stage).parameters)

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

    def test_a_missing_purpose_row_is_refused_and_the_shared_registry_is_never_mutated(self):
        dm._PURPOSES.pop(probe.PURPOSE)
        before = dict(dm._PURPOSES)
        with self.assertRaisesRegex(ValueError, "_PURPOSES"):
            self.stage()
        self.assertEqual(before, dm._PURPOSES)
        self.assertNotIn(probe.PURPOSE, dm._PURPOSES)
        self.assertFalse(self.dest.exists())

    def test_a_conflicting_purpose_row_cannot_substitute_another_hook_or_metadata(self):
        for wrong in (dm._PURPOSES["selftests"], ("disposable-something-else", None, ["wrong prerequisites"]),
                      ("disposable-weather-probe", None, ["wrong prerequisites"])):
            dm._PURPOSES[probe.PURPOSE] = wrong
            with self.subTest(wrong=wrong[0]), self.assertRaisesRegex(ValueError, "_PURPOSES"):
                self.stage()
            self.assertEqual(wrong, dm._PURPOSES[probe.PURPOSE])
            self.assertFalse(self.dest.exists())

    def test_the_module_no_longer_carries_a_setdefault_registry_fallback(self):
        self.assertFalse(hasattr(probe, "_ensure_purpose"))
        self.assertNotIn("setdefault", PROBE_SOURCE.read_text(encoding="utf-8"))

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
