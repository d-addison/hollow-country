"""Authored loader control flow with synthetic native boundaries, not fit proof."""
import copy
import inspect
import json
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest
from tests.unit.build_identity_support import translate as build_identity
from tests.unit.test_group_server import EArray, body, translated_rules
from tests.unit import test_interior_catalog as measured_fixtures
from tools.package import interior_catalog as export


ROOT = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts"
DATA = ROOT / "3_Game/Interiors/HCInteriorMeasuredCatalogData.c"
SOURCE = ROOT / "4_World/Interiors/HCInteriorMeasuredCatalog.c"


class EMap(dict):
    def Count(self): return len(self)
    def Get(self, key): return self.get(key, "")
    def __missing__(self, key): return ""
    def __bool__(self): return True


class SyntheticHouse:
    def __init__(self, position, orientation):
        self.position, self.orientation = list(position), list(orientation)
        self.kind = "Land_House_1W01"
    def GetPosition(self): return self.position
    def GetOrientation(self): return self.orientation
    def GetType(self): return self.kind
    @staticmethod
    def Cast(value): return value if isinstance(value, SyntheticHouse) else None


def statements(source):
    """Split syntax delimiters while preserving complete string literals."""
    result, start = [], 0
    for match in re.finditer(r'"(?:\\.|[^"\\])*"|[{};]', source):
        if match[0].startswith('"'):
            continue
        result.extend((source[start:match.start()], match[0]))
        start = match.end()
    result.append(source[start:])
    return result


def authored():
    """Execute authored methods; adapt language/native boundaries, not policy.

    String literals are protected during syntax conversion so JSON boolean
    tokens and schema names are not rewritten as Python keywords.
    """
    data, source = DATA.read_text(), SOURCE.read_text()
    env = {"EArray": EArray, "EMap": EMap, "len": len, "ord": ord}
    for match in re.finditer(r"class (\w+)\s*\{", data):
        fields = body(data, match.end())
        defaults = [
            m.groups() for m in re.finditer(
                r"^\s*(?:ref )?([\w<>, ]+?) (\w+)(?:\s*=\s*([^;]+))?;",
                fields, re.M)]

        def make(defaults=defaults):
            value = NS()
            for typ, name, initial in defaults:
                if "array<" in typ:
                    result = EArray()
                elif "map<" in typ:
                    result = EMap()
                elif initial is not None:
                    result = json.loads(initial)
                else:
                    result = {"string": "", "int": 0, "float": 0.,
                              "bool": False}.get(typ)
                setattr(value, name, result)
            return value
        env[match[1]] = make
    source = re.sub(r"//[^\n]*", "", source)
    methods = re.finditer(r"static ([\w<>]+) (\w+)\(([^)]*)\)\s*\{", source)
    for match in methods:
        name = match[2]
        if name in {"MeasuredRead", "MeasuredEngineBuild"}:
            continue  # Explicit native boundaries replaced by fixture().
        args = [arg.strip().split()[-1] for arg in re.sub(r"<[^>]*>", "", match[3]).split(",")
                if arg.strip()]
        lines = [f"def {name}({', '.join(args)}):",
                 "    global s_Attempted, s_Requested, s_Binding, s_WorldKey"]
        indent = 1
        for token in statements(body(source, match.end())):
            token = token.strip()
            if not token or token == ";":
                continue
            if token == "{":
                indent += 1
                continue
            if token == "}":
                indent -= 1
                continue
            literals = []

            def protect(m):
                literals.append(m[0])
                return f"__STRING_{len(literals)-1}__"

            token = re.sub(r'"(?:\\.|[^"\\])*"', protect, token)
            token = re.sub(r"JsonFileLoader<(\w+)>\.LoadData\(",
                           r'NativeLoad("\1", ', token)
            token = re.sub(r"new array<[^;]+>\(\)", "EArray()", token)
            token = re.sub(r"new (HCInteriorMeasuredCatalog\w+)(?:\(\))?",
                           r"\1()", token)
            token = token.replace("new HCInteriorLayout", "HCInteriorLayout()")
            token = token.replace("new HCInteriorProp(", "HCInteriorProp(")
            token = re.sub(
                r"\b(?:int|float|bool|string|vector|HCInteriorMeasuredCatalog\w+|HCInteriorLayout|HCInteriorProp|House|Object)\s+(?=\w+\s*=)",
                "", token)
            token = re.sub(r"array<[\w ]+>\s+(?=\w+\s*=)", "", token)
            bare = re.fullmatch(r"(int|float|bool|string|vector) (\w+)", token)
            if bare:
                token = bare[2] + " = " + {
                    "int": "0", "float": "0.", "bool": "False",
                    "string": "''", "vector": "[0., 0., 0.]"}[bare[1]]
            token = re.sub(r"([\w.]+)\.Get\(([^)]+)\)", r"\1[\2]", token)
            token = re.sub(r"(\w+)\.ToAscii\(\)", r"ord(\1)", token)
            token = re.sub(
                r"([\w.]+)\.Substring\(([^,]+), ([^)]+)\)",
                r"\1[\2:(\2)+min((\3), 8191)]", token)  # engine cap, observed diag-json-1
            split = re.fullmatch(r"(\w+)\.Split\(([^,]+), (\w+)\)", token)
            if split:
                token = split[3] + ".extend(part for part in " + split[1] + ".split(" + split[2] + ") if part)"
            lower = re.fullmatch(r"(\w+)\.ToLower\(\)", token)
            if lower:
                token = lower[1] + " = " + lower[1] + ".lower()"
            token = re.sub(r"([\w.]+)\.Length\(\)", r"len(\1)", token)
            token = re.sub(r"([\w.]+)\.Trim\(\)", r"\1.strip()", token)
            token = token.replace("&&", " and ").replace("||", " or ")
            token = re.sub(r"!(?!=)", "not ", token)
            for old, new in (("true", "True"), ("false", "False"), ("null", "None")):
                token = re.sub(r"\b" + old + r"\b", new, token)
            if token.startswith(("if (", "while (")):
                prefix, condition = token.split(" (", 1)
                token = prefix + " " + condition[:-1] + ":"
            elif token.startswith("foreach ("):
                loop = re.fullmatch(r"foreach \(\w+ (\w+) : (.+)\)", token)
                if not loop:
                    raise AssertionError("unsupported authored loop: " + token)
                token = f"for {loop[1]} in {loop[2]}:"
            elif token == "else":
                token += ":"
            for index, literal in enumerate(literals):
                token = token.replace(f"__STRING_{index}__", literal)
            lines.append("    " * indent + token)
        exec(compile("\n".join(lines), str(SOURCE) + ":" + name, "exec"), env)
    return env


def dto(value, key=""):
    if isinstance(value, list):
        return EArray(dto(item) for item in value)
    if isinstance(value, dict):
        if key in {"SourceSha256", "source_sha256", "AssetPboSha256", "candidate_sha256"}:
            return EMap(value)
        result = NS(**{name: dto(child, name) for name, child in value.items()})
        if {"Id", "History", "Props"} <= value.keys() and "Survey" not in value:
            result.Survey = None
        return result
    return value


def fixture(enabled=True, trusted=True):
    e = authored()
    record, sources, artifacts = measured_fixtures.fixture()
    # Explicit synthetic geometry asserts these flags solely to test rejection
    # and control flow. It never becomes an authentic survey or native evidence.
    record["Synthetic"] = False
    files, report = export.prepare(measured_fixtures.encode(record), sources, artifacts)
    profile = dict(
        SchemaVersion=1, EnableTrustedExperiment=enabled,
        TrustedExternalValidation=trusted, WorldName="chernarusplus",
        Build="1.30.164289", TrustedAddonSha256="a" * 64,
        TrustedValidatorSha256="b" * 64, SourceSha256=record["SourceSha256"],
        ExpectedRecordText=files["measured-record.json"].decode(),
        ExpectedCandidateText=files["interior-layouts.candidate.json"].decode(),
        ExpectedPolicyText=files["context-policy.candidate.json"].decode(),
        ExpectedReportText=files["interior-report.json"].decode())
    base = "$profile:HollowCountry/measured-interiors/"
    profile_path = "$profile:HollowCountry/interiors-measured-profile.json"
    raw = {base + name: data.decode() for name, data in files.items()}
    raw[profile_path] = json.dumps(profile)
    calls = {"reads": [], "queries": 0, "parse": 0}
    house = SyntheticHouse(record["Context"]["BuildingPosition"],
                           record["Context"]["BuildingOrientation"])
    objects = [house]

    def read(path, limit):
        calls["reads"].append(path)
        content = raw.get(path, "")
        return content if 0 < len(content.encode()) <= limit else ""

    def load(type_name, content, target, error):
        calls["parse"] += 1
        try:
            value = dto(json.loads(content))
        except (ValueError, TypeError):
            return False
        from tests.unit.json_loader_port import zero_scalars
        target.__dict__.update(vars(zero_scalars(target)))
        target.__dict__.update(value.__dict__)
        return True

    def query(position, radius, found, cargos):
        calls["queries"] += 1
        found.extend(objects)

    game = NS(IsServer=lambda: True, GetWorldName=lambda: "chernarusplus",
              GetObjectsAtPosition3D=query)
    e.update(HCBuildIdentity=build_identity(), EMap=EMap, ord=ord, Vector=lambda x, y, z: [x, y, z],
             vector=NS(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))),
             House=SyntheticHouse, GetGame=lambda: game, NativeLoad=load,
             FileExist=lambda path: path in raw,
             PROFILE_PATH=profile_path, DATA_ROOT=base,
             s_Attempted=False, s_Requested=False, s_Binding=None, s_WorldKey=-1,
             HCInteriorMeasuredCatalogBinding=NS,
             HCInteriorLayout=lambda: NS(Id="", History="", Props=EArray()),
             HCInteriorProp=lambda typ, pos, ori, search, point:
                 NS(Type=typ, Position=list(pos), Orientation=list(ori),
                    Searchable=search, SearchPoint=list(point)),
             Print=lambda message: None)
    e["MeasuredRead"] = read  # Explicit bounded native file-I/O boundary.
    e["MeasuredEngineBuild"] = lambda: "1.30.164289"
    candidate = NS(Type=record["BuildingType"], Position=list(house.position),
                   Orientation=list(house.orientation))
    return e, raw, calls, house, objects, candidate, profile


class InteriorMeasuredCatalogTests(unittest.TestCase):
    def test_native_key_remap_preserves_trusted_embedded_json(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        self.assertEqual(profile, json.loads(
            e["MeasuredNativeText"](json.dumps(profile), "profile")))
        record = json.loads(profile["ExpectedRecordText"])
        record["Context"]["Operator"] = "BuildingType Selection World world"
        record["Policy"]["Rules"][0]["Rationale"] = (
            'Keep values {"BuildingType":"Selection","World":"world"} unchanged.')
        expected = copy.deepcopy(record)
        expected["BuildingClass"] = expected.pop("BuildingType")
        expected["Context"]["WorldName"] = expected["Context"].pop("World")
        for rule in expected["Policy"]["Rules"]:
            rule["SelectionMode"] = rule.pop("Selection")
        self.assertEqual(expected, json.loads(
            e["MeasuredNativeText"](json.dumps(record), "record")))
        self.assertEqual("", e["MeasuredNativeText"]('{"Unknown":1}', "record"))

    def test_record_longer_than_one_native_substring_survives_the_key_remap(self):
        # Enforce Substring returns at most 8191 characters; the remap must copy in pieces.
        e, raw, calls, house, objects, candidate, profile = fixture()
        record = json.loads(profile["ExpectedRecordText"])
        record["Policy"]["Rules"][0]["Rationale"] = "x" * 20000
        text = e["MeasuredNativeText"](json.dumps(record), "record")
        self.assertEqual(20000, len(json.loads(text)["Policy"]["Rules"][0]["Rationale"]))

    def test_only_pinned_base_and_observed_full_version_are_admitted(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        e["MeasuredEngineBuild"] = lambda: "1.30.164289.70"
        e["MeasuredEnsureLoaded"]()
        self.assertIsNotNone(e["s_Binding"])
        self.assertIsNotNone(e["MeasuredSelect"](0, candidate))
        for version in ("1.30.1642890.70", "1.30.164289.700",
                        "1.30.164289.71", "1.30.164289.070",
                        "1.30.164289.70.1", " 1.30.164289.70",
                        "1.30.164289.70x"):
            self.assertFalse(e["MeasuredBuildMatches"](version, "1.30.164289"))
        self.assertFalse(e["MeasuredBuildMatches"]("1.30.164289.70", "1.30.16428"))

    def test_pinned_and_actual_use_the_one_shared_build_matcher(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        for actual in ("1.30.164289", "1.30.164289.70"):
            for pinned in ("1.30.164289", "1.30.164289.70"):
                self.assertTrue(e["MeasuredBuildMatches"](actual, pinned), (actual, pinned))
        for bad in ("", "1.30.164289.7x", "1.30.1642890", "1.30.164289 "):
            self.assertFalse(e["MeasuredBuildMatches"](bad, "1.30.164289"), bad)
            self.assertFalse(e["MeasuredBuildMatches"]("1.30.164289.70", bad), bad)

    def test_trusted_profile_build_text_is_admitted_through_the_shared_matcher(self):
        path = "$profile:HollowCountry/interiors-measured-profile.json"
        for stamped, expected in (("1.30.164289.70", True), ("1.30.164289", True),
                                  ("1.30.164289.7x", False), ("1.30.1642890", False)):
            e, raw, calls, house, objects, candidate, profile = fixture()
            e["MeasuredEngineBuild"] = lambda: "1.30.164289.70"
            raw[path] = json.dumps(dict(profile, Build=stamped))
            e["MeasuredEnsureLoaded"]()
            self.assertEqual(expected, e["s_Binding"] is not None, stamped)

    def test_empty_path_components_are_rejected_before_native_split(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        for value in ("/diag/native.log", "diag/native.log/",
                      "diag//native.log", "diag/../native.log", "diag/CON.txt"):
            self.assertFalse(e["MeasuredPortablePath"](value), value)
        self.assertTrue(e["MeasuredPortablePath"]("diag/native.log"))

    def test_schema_guard_rejects_nested_unknown_duplicate_types_and_excess(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        original = json.loads(profile["ExpectedRecordText"])
        self.assertTrue(e["MeasuredStrict"](json.dumps(original), "record"))
        variants = []
        value = copy.deepcopy(original)
        value["SchemaVersion"] = 4294967297
        variants.append(json.dumps(value))
        value = copy.deepcopy(original)
        value["Layouts"][0]["Survey"]["Keepouts"][0]["Unknown"] = 1
        variants.append(json.dumps(value))
        value = copy.deepcopy(original)
        value["Policy"]["Limits"]["Slots"] = True
        variants.append(json.dumps(value))
        value = copy.deepcopy(original)
        value["Policy"]["Limits"]["Slots"] = 1.5
        variants.append(json.dumps(value))
        value = copy.deepcopy(original)
        value["Context"]["BuildingPosition"] = [0] * 33
        variants.append(json.dumps(value))
        variants.append(profile["ExpectedRecordText"].replace(
            '"SchemaVersion": 1', '"SchemaVersion": 1, "SchemaVersion": 1', 1))
        variants.append(json.dumps(original) + "{}")
        for content in variants:
            with self.subTest(content=content[:80]):
                self.assertFalse(e["MeasuredStrict"](content, "record"))

    def test_survey_geometry_and_policy_validate_authored_denominators(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        e["MeasuredEnsureLoaded"]()
        self.assertIsNotNone(e["s_Binding"])
        record = e["s_Binding"].Record
        self.assertTrue(e["MeasuredRecord"](record))
        changed = copy.deepcopy(record)
        changed.Layouts[0].Survey.Props[0].Bounds.Min[0] = 9
        self.assertFalse(e["MeasuredRecord"](changed))
        changed = copy.deepcopy(record)
        changed.Layouts[0].Survey.Keepouts[0].Kind = "stairs"
        self.assertFalse(e["MeasuredRecord"](changed))
        changed = copy.deepcopy(record)
        changed.Layouts[0].Survey.Props[0].Observation = "missing.log"
        self.assertFalse(e["MeasuredRecord"](changed))
        changed = copy.deepcopy(record)
        changed.Policy.Rules[0].ItemGroups.append("unknown-group")
        self.assertFalse(e["MeasuredRecord"](changed))
        changed = copy.deepcopy(record)
        changed.Policy.Rules[1].LayoutId = changed.Policy.Rules[0].LayoutId
        self.assertFalse(e["MeasuredRecord"](changed))
        changed = copy.deepcopy(record)
        changed.Synthetic = True
        self.assertFalse(e["MeasuredRecord"](changed))

    def test_wrong_build_world_pose_and_later_ambiguity_refuse_selection(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        e["MeasuredEngineBuild"] = lambda: "1.30.other"
        e["MeasuredEnsureLoaded"]()
        self.assertIsNone(e["s_Binding"])
        self.assertEqual(0, calls["queries"])
        e, raw, calls, house, objects, candidate, profile = fixture()
        e["MeasuredEnsureLoaded"]()
        candidate.Position[0] += .01
        self.assertIsNone(e["MeasuredSelect"](0, candidate))
        candidate.Position[0] = house.position[0]
        objects.append(SyntheticHouse(house.position, house.orientation))
        self.assertIsNone(e["MeasuredSelect"](0, candidate))
        self.assertEqual("", e["MeasuredDigest"](candidate))

    def test_report_and_candidate_contradictions_are_not_acceptance(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        e["MeasuredEnsureLoaded"]()
        record = e["s_Binding"].Record
        exported = dto(json.loads(e["MeasuredNativeText"](
            profile["ExpectedCandidateText"], "candidate")))
        report_value = json.loads(e["MeasuredNativeText"](
            profile["ExpectedReportText"], "report"))
        report = dto(report_value)
        self.assertTrue(e["MeasuredCandidate"](record, exported))
        self.assertTrue(e["MeasuredReport"](record, exported, report))
        exported.Layouts[0].Props[0].Position[0] += .1
        self.assertFalse(e["MeasuredCandidate"](record, exported))
        exported = dto(json.loads(e["MeasuredNativeText"](
            profile["ExpectedCandidateText"], "candidate")))
        report.production_accepted = True
        self.assertFalse(e["MeasuredReport"](record, exported, report))
        report.production_accepted = False
        report.pending.pop()
        self.assertFalse(e["MeasuredReport"](record, exported, report))

    def test_default_off_and_untrusted_profiles_never_publish(self):
        for enabled, trusted in ((False, True), (True, False)):
            with self.subTest(enabled=enabled, trusted=trusted):
                e, raw, calls, house, objects, candidate, profile = fixture(enabled, trusted)
                e["MeasuredEnsureLoaded"]()
                self.assertIsNone(e["s_Binding"])
                self.assertIsNone(e["MeasuredSelect"](0, candidate))
                self.assertEqual(0, calls["queries"])

    def test_valid_synthetic_assertions_load_once_and_return_defensive_layouts(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        e["MeasuredEnsureLoaded"]()
        self.assertIsNotNone(e["s_Binding"])
        first = e["MeasuredSelect"](0, candidate)
        self.assertEqual("family-pantry-v1", first.Id)
        self.assertEqual([1.25, .5, 1.25], first.Props[0].Position)
        first.Props[0].Position[0] = 999
        first.Props.clear()
        self.assertEqual(2, len(e["MeasuredSelect"](0, candidate).Props))
        reads = list(calls["reads"])
        e["MeasuredEnsureLoaded"]()
        self.assertEqual(reads, calls["reads"])
        self.assertEqual(64, len(e["MeasuredDigest"](candidate)))

    def test_any_changed_import_bytes_refuse_publication(self):
        for name in ("measured-record.json", "interior-layouts.candidate.json",
                     "context-policy.candidate.json", "interior-report.json"):
            with self.subTest(name=name):
                e, raw, calls, house, objects, candidate, profile = fixture()
                path = "$profile:HollowCountry/measured-interiors/" + name
                raw[path] += " "
                e["MeasuredEnsureLoaded"]()
                self.assertIsNone(e["s_Binding"])
                self.assertIsNone(e["MeasuredSelect"](0, candidate))

    def test_live_house_must_be_unique_and_remain_at_the_exact_bound_pose(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        objects.append(SyntheticHouse(house.position, house.orientation))
        e["MeasuredEnsureLoaded"]()
        self.assertIsNone(e["s_Binding"])
        e, raw, calls, house, objects, candidate, profile = fixture()
        e["MeasuredEnsureLoaded"]()
        house.position[0] += .5
        self.assertIsNone(e["MeasuredSelect"](0, candidate))
        self.assertEqual("", e["MeasuredDigest"](candidate))

    def test_rejected_attempt_is_not_retried_until_explicit_clear(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        path = "$profile:HollowCountry/interiors-measured-profile.json"
        original = raw[path]
        raw[path] = '{"SchemaVersion":2}'
        e["MeasuredEnsureLoaded"]()
        reads = list(calls["reads"])
        raw[path] = original
        e["MeasuredEnsureLoaded"]()
        self.assertEqual(reads, calls["reads"])
        self.assertIsNone(e["s_Binding"])
        e["MeasuredClear"]()
        e["MeasuredEnsureLoaded"]()
        self.assertIsNotNone(e["s_Binding"])

    def test_unknown_duplicate_and_missing_profile_fields_are_rejected(self):
        for content in ('{"SchemaVersion":1,"SchemaVersion":1}',
                        '{"SchemaVersion":1}', '{"Unknown":1}'):
            e, raw, calls, house, objects, candidate, profile = fixture()
            raw["$profile:HollowCountry/interiors-measured-profile.json"] = content
            e["MeasuredEnsureLoaded"]()
            self.assertIsNone(e["s_Binding"])
            self.assertEqual(0, calls["parse"])
            self.assertTrue(e["MeasuredRequested"]())

    def test_policy_caps_and_item_groups_filter_existing_finite_allocation(self):
        e, raw, calls, house, objects, candidate, profile = fixture()
        e["MeasuredEnsureLoaded"]()
        self.assertEqual(1, e["MeasuredAllocation"](0, candidate, 1, 0, 0))
        self.assertEqual(2, e["MeasuredAllocation"](0, candidate, 2, 0, 0))
        self.assertEqual(0, e["MeasuredAllocation"](0, candidate, 1, 4, 0))
        self.assertEqual(0, e["MeasuredAllocation"](0, candidate, 2, 0, 2))
        self.assertEqual(0, e["MeasuredAllocation"](3, candidate, 1, 0, 0))

    def test_acceptance_gates_remain_false_and_module_uses_bound_selection(self):
        rules = (ROOT / "4_World/Interiors/HCInteriorRules.c").read_text()
        for name in ("PlacementAccepted", "SearchAccepted"):
            match = re.search(r"static bool " + name + r"\(\)\s*\{", rules)
            self.assertEqual("return false;", body(rules, match.end()).strip())
        module = (ROOT / "4_World/Interiors/HCInteriorModule.c").read_text()
        self.assertGreaterEqual(module.count("HCInteriorCatalog.GetFor("), 2)
        self.assertIn("MeasuredRecordSha256", module)
