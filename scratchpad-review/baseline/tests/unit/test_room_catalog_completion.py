"""Execute authored room catalog methods with synthetic engine/JSON boundaries.

These tests establish source control flow, not native serialization, lookup,
survey measurements, collision, navigation or client acceptance.
"""
import copy
import json
import math
import re
from types import SimpleNamespace
import unittest

from test_core_lifecycle import NativeArray, tokens
from test_infected_contract import SOURCE, policy_functions


PATH = SOURCE / "HCInfectedRooms.c"


class Text:
    def __init__(self, value=""): self.value = value
    def __str__(self): return self.value
    def __len__(self): return len(self.value)


class Vec(tuple):
    @staticmethod
    def DistanceSq(a, b): return sum((x - y) ** 2 for x, y in zip(a, b))


class Array(NativeArray):
    def Find(self, item): return self.index(item) if item in self else -1
    def __bool__(self): return True  # native array references remain nonnull when empty


class Anchor:
    def __init__(self):
        self.Id = 0
        self.LocalPosition = Vec((0, 0, 0))
        self.LocalMin = Vec((0, 0, 0))
        self.LocalMax = Vec((0, 0, 0))

    def Contains(self, point):
        return all(lo <= x <= hi for lo, x, hi in zip(self.LocalMin, point, self.LocalMax))


class Survey:
    def __init__(self):
        self.Build = self.WorldName = self.BuildingClass = self.EvidenceId = ""
        self.Revision = 0
        self.Measured = False
        self.Anchors = Array()


class Document:
    def __init__(self):
        self.SchemaVersion = 0
        self.EnableDiagnostic = False
        self.Build = self.WorldName = ""
        self.Buildings = Array()


class Record:
    def __init__(self):
        self.Position = Vec((200001, 200001, 200001))
        self.Orientation = Vec((1000, 1000, 1000))
        self.Survey = None


class House:
    def __init__(self, position=(100, 10, 100), orientation=(0, 0, 0), kind="SyntheticHouse"):
        self.position, self.orientation, self.kind = Vec(position), Vec(orientation), kind
    def GetPosition(self): return self.position
    def GetOrientation(self): return self.orientation
    def GetType(self): return self.kind
    def WorldToModel(self, point): return Vec(a - b for a, b in zip(point, self.position))
    def ModelToWorld(self, point): return Vec(a + b for a, b in zip(point, self.position))
    @staticmethod
    def Cast(candidate): return candidate if isinstance(candidate, House) else None


def source_method(name, diagnostic):
    source = PATH.read_text()
    source = re.sub(r"#ifdef DIAG_DEVELOPER\n(.*?)#endif", lambda m: m[1] if diagnostic else "", source, flags=re.S)
    match = re.search(r"static (?:bool|void|int|HCInfectedRoomBinding|House|HCInfectedRoomDocument) " + name + r"\([^\n]*\)\s*\{", source)
    if not match: raise AssertionError("missing actual room catalog method: " + name)
    start = end = match.end()
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return re.sub(r"//[^\n]*", "", source[start:end-1])


def expression(text):
    text = re.sub(r"new array<[^;]+?>", "Array()", text)
    text = re.sub(r"new (\w+)(?![\w(])", r"\1()", text)
    text = text.replace("JsonFileLoader<HCInfectedRoomDocument>", "Loader")
    text = re.sub(r"\b(?:ref )?(?:array<[^;]+?>|int|float|bool|string|vector|House|Object|HCInfectedRoom\w+) (\w+) =", r"\1 =", text)
    empty = re.fullmatch(r"(int|float|bool|string|vector|House|HCInfectedRoom\w+) (\w+)", text)
    if empty:
        default = {"int": "0", "float": "0", "bool": "False", "string": "Text()", "vector": "Vec((0, 0, 0))"}.get(empty[1], "None")
        return empty[2] + " = " + default
    text = re.sub(r"(\w+(?:\.\w+)*(?:\[[^]]+\])?)\.Length\(\)", r"len(\1)", text)
    text = re.sub(r"(\w+)\.Get\(([^)]+)\)", r"str(\1)[\2]", text)
    text = re.sub(r"(\w+)\.ToAscii\(\)", r"ord(\1)", text)
    text = re.sub(r"(\w+)\.Substring\(([^,]+), ([^)]+)\)", r"str(\1)[\2:(\2) + (\3)]", text)
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"!(?!=)", "not ", text)
    text = re.sub(r"\b(true|false|null)\b", lambda m: {"true": "True", "false": "False", "null": "None"}[m[1]], text)
    text = re.sub(r"(\w+)\+\+", r"\1 += 1", text)
    text = re.sub(r"(\w+)--", r"\1 -= 1", text)
    return text


def authored(name, arguments, ns, diagnostic=True):
    lines, indent = ["def " + name + "(" + arguments + "):"], 1
    lines.append("    global s_Bindings, s_DiagnosticAttempted")
    for token in tokens(source_method(name, diagnostic)):
        if token == "{": indent += 1; continue
        if token == "}": indent -= 1; continue
        each = re.fullmatch(r"foreach \(\w+ (\w+) : (.*)\)", token, re.S)
        loop = re.fullmatch(r"for \(int (\w+) = 0; \1 < (.*); \1\+\+\)", token, re.S)
        conditional = re.match(r"^(if|while) \(", token)
        if each: line = "for " + each[1] + " in " + expression(each[2]) + ":"
        elif loop: line = "for " + loop[1] + " in range(" + expression(loop[2]) + "):"
        elif conditional:
            begin = token.index("(")
            level = 0
            for index in range(begin, len(token)):
                level += (token[index] == "(") - (token[index] == ")")
                if level == 0: break
            line = conditional[1] + " " + expression(token[begin+1:index]) + ": " + expression(token[index+1:].strip())
        elif token == "else": line = "else:"
        else:
            if re.search(r"\b(?:for|foreach|while|try|catch|switch)\b", token):
                raise AssertionError("unsupported syntax: " + token)
            line = expression(token)
        if name == "BuildOrder": line = re.sub(r"\breturn$", "return points", line)
        lines.append("    " * indent + line.replace("\n", " "))
    if name == "BuildOrder": lines.append("    return points")
    exec(compile("\n".join(lines), "authored-rooms:" + name, "exec"), ns)


def synthetic_document(count=1):
    """Explicit test coordinates: never a measured or production fixture."""
    doc = Document()
    doc.SchemaVersion, doc.EnableDiagnostic = 1, True
    doc.Build, doc.WorldName = "1.30.164289", "chernarusplus"
    houses = []
    for index in range(count):
        house = House(position=(100 + index * 100, 10, 100))
        houses.append(house)
        record, survey, anchor = Record(), Survey(), Anchor()
        record.Position, record.Orientation = house.position, house.orientation
        survey.Build, survey.WorldName = doc.Build, doc.WorldName
        survey.BuildingClass, survey.EvidenceId = house.kind, "SYNTHETIC-NOT-MEASURED"
        survey.Revision, survey.Measured = 1, True  # assertion under test, no actual survey
        anchor.Id = 1
        anchor.LocalMin, anchor.LocalMax = Vec((-2, -2, -2)), Vec((2, 2, 2))
        survey.Anchors.Insert(anchor)
        record.Survey = survey
        doc.Buildings.Insert(record)
    return doc, houses


def encode(value):
    if isinstance(value, (Document, Record, Survey, Anchor)): return value.__dict__
    raise TypeError(type(value))


def fixture(diagnostic=True, server=True, document=None, objects=None, raw=None, read_ok=True, parse_ok=True):
    doc, houses = synthetic_document() if document is None else (document, objects or [])
    calls = {"reads": [], "queries": [], "parse": 0}
    raw = json.dumps(doc, default=encode) if raw is None else raw
    def read(path, content):
        calls["reads"].append(path)
        content.value = raw
        return read_ok and 0 < len(raw) <= 65536
    def load(content, result, error):
        calls["parse"] += 1
        if not parse_ok: return False
        try: json.loads(str(content))
        except ValueError: return False
        result.__dict__.update(copy.deepcopy(doc.__dict__))
        return True
    def query(position, radius, found, cargos):
        calls["queries"].append((position, radius))
        found.extend(houses if objects is None else objects)
    game = SimpleNamespace(IsServer=lambda: server, GetWorldName=lambda: "chernarusplus", GetObjectsAtPosition3D=query)
    ns = dict(GetGame=lambda: game, s_Bindings=Array(), s_DiagnosticAttempted=False,
              DIAGNOSTIC_PATH="$profile:HollowCountry/Infected/measured-rooms.json",
              Array=Array, Text=Text, Vec=Vec, vector=Vec, House=House,
              HCInfectedRoomDocument=Document, HCInfectedRoomSurvey=Survey, HCInfectedRoomAnchor=Anchor,
              HCInfectedRoomBinding=SimpleNamespace, TVectorArray=Array,
              HCInfectedPolicy=SimpleNamespace(**policy_functions()),
              HCInfectedStore=SimpleNamespace(ReadBounded=read, ValidPosition=lambda v: all(-200000 <= x <= 200000 for x in v)),
              Loader=SimpleNamespace(LoadData=load), Print=lambda message: None)
    methods = [("DiagnosticServer", ""), ("KeyBit", "depth, key"), ("RequiredKeys", "depth"),
               ("JsonSpace", "ch"), ("ValidJsonKeys", "content"), ("CreateBinding", "building, survey, existing"),
               ("ResolveBuilding", "record"), ("BindDiagnostic", "document"), ("ReadDiagnostic", ""),
               ("EnsureDiagnosticLoaded", ""), ("Register", "building, survey"), ("Clear", ""),
               ("BuildOrder", "observedClue, budget, points=None")]
    for name, args in methods: authored(name, args, ns, diagnostic)
    return ns, calls, doc, houses


class RoomCatalogCompletionTests(unittest.TestCase):
    def test_given_valid_synthetic_catalog_when_build_order_then_load_once_and_bind(self):
        ns, calls, doc, houses = fixture()
        self.assertEqual([houses[0].position], ns["BuildOrder"](houses[0].position, 2))
        ns["BuildOrder"](houses[0].position, 2)
        self.assertEqual(calls["reads"], [ns["DIAGNOSTIC_PATH"]])
        self.assertEqual(len(calls["queries"]), 1)
        self.assertEqual(len(ns["s_Bindings"]), 1)

    def test_normal_pbo_and_client_never_read_or_bind(self):
        for options in ({"diagnostic": False}, {"server": False}):
            with self.subTest(options=options):
                ns, calls, doc, houses = fixture(**options)
                self.assertFalse(ns["BindDiagnostic"](doc))
                self.assertFalse(ns["Register"](houses[0], doc.Buildings[0].Survey))
                self.assertEqual(ns["BuildOrder"](houses[0].position, 2), [])
                self.assertEqual(calls["reads"], [])
                self.assertEqual(calls["queries"], [])

    def test_disabled_bad_version_identity_and_missing_records_fail_before_queries(self):
        mutations = [("EnableDiagnostic", False), ("SchemaVersion", 0), ("SchemaVersion", 2),
                     ("Build", "other"), ("WorldName", "other"), ("Buildings", None), ("Buildings", Array())]
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                doc, houses = synthetic_document()
                setattr(doc, field, value)
                ns, calls, _, _ = fixture(document=doc, objects=houses)
                self.assertFalse(ns["BindDiagnostic"](doc))
                self.assertEqual(calls["queries"], [])
                self.assertEqual(ns["s_Bindings"], [])
        doc, houses = synthetic_document(5)
        ns, calls, _, _ = fixture(document=doc, objects=houses)
        self.assertFalse(ns["BindDiagnostic"](doc))
        self.assertEqual(calls["queries"], [])

    def test_staging_rejects_later_bad_record_without_partial_publication(self):
        doc, houses = synthetic_document(2)
        doc.Buildings[1].Survey.EvidenceId = ""
        ns, _, _, _ = fixture(document=doc, objects=houses)
        self.assertFalse(ns["BindDiagnostic"](doc))
        self.assertEqual(ns["s_Bindings"], [])
        doc.Buildings[1].Survey.EvidenceId = "SYNTHETIC"
        self.assertTrue(ns["BindDiagnostic"](doc))
        published = list(ns["s_Bindings"])
        self.assertFalse(ns["BindDiagnostic"](doc))
        self.assertEqual(ns["s_Bindings"], published)

    def test_duplicate_house_and_ambiguous_native_candidates_reject(self):
        doc, houses = synthetic_document()
        doc.Buildings.Insert(copy.deepcopy(doc.Buildings[0]))
        ns, _, _, _ = fixture(document=doc, objects=houses)
        self.assertFalse(ns["BindDiagnostic"](doc))
        self.assertEqual(ns["s_Bindings"], [])
        doc.Buildings.pop()
        ns, _, _, _ = fixture(document=doc, objects=houses + [House()])
        self.assertFalse(ns["BindDiagnostic"](doc))

    def test_house_class_pose_and_finite_coordinates_are_required(self):
        for field, value in [("Position", Vec((math.nan, 0, 0))), ("Position", Vec((200001, 0, 0))),
                             ("Orientation", Vec((math.inf, 0, 0))), ("Orientation", Vec((361, 0, 0))),
                             ("Position", Vec((101, 10, 100))), ("Orientation", Vec((1, 0, 0)))]:
            with self.subTest(field=field, value=value):
                ns, _, doc, _ = fixture()
                setattr(doc.Buildings[0], field, value)
                self.assertFalse(ns["BindDiagnostic"](doc))
        ns, _, doc, _ = fixture(objects=[House(kind="OtherClass")])
        self.assertFalse(ns["BindDiagnostic"](doc))
        ns, _, doc, _ = fixture(objects=[object()] * 65)
        self.assertFalse(ns["BindDiagnostic"](doc))

    def test_existing_survey_checks_and_deep_copy_survive_loader(self):
        for field, value in [("Measured", False), ("Revision", 0), ("Build", "other"),
                             ("WorldName", "other"), ("BuildingClass", "OtherClass"),
                             ("EvidenceId", ""), ("EvidenceId", "x" * 129), ("Anchors", None), ("Anchors", Array())]:
            with self.subTest(field=field):
                ns, _, doc, _ = fixture()
                setattr(doc.Buildings[0].Survey, field, value)
                self.assertFalse(ns["BindDiagnostic"](doc))
                self.assertEqual(ns["s_Bindings"], [])
        ns, _, doc, _ = fixture()
        self.assertTrue(ns["BindDiagnostic"](doc))
        doc.Buildings[0].Survey.Anchors[0].LocalPosition = Vec((99, 99, 99))
        self.assertEqual(ns["s_Bindings"][0].Survey.Anchors[0].LocalPosition, (0, 0, 0))

    def test_anchor_bounds_duplicates_nonfinite_and_capacity_reject(self):
        for change in (lambda a: setattr(a, "Id", 0), lambda a: setattr(a, "LocalPosition", Vec((math.nan, 0, 0))),
                       lambda a: setattr(a, "LocalMin", Vec((-33, -2, -2))),
                       lambda a: setattr(a, "LocalMax", Vec((math.nan, 2, 2))),
                       lambda a: setattr(a, "LocalPosition", Vec((3, 0, 0)))):
            ns, _, doc, _ = fixture()
            change(doc.Buildings[0].Survey.Anchors[0])
            self.assertFalse(ns["BindDiagnostic"](doc))
        for count in (2, 7):
            ns, _, doc, _ = fixture()
            anchor = doc.Buildings[0].Survey.Anchors[0]
            doc.Buildings[0].Survey.Anchors = Array(copy.deepcopy(anchor) for _ in range(count))
            self.assertFalse(ns["BindDiagnostic"](doc))

    def test_manual_binding_is_preserved_and_moved_house_yields_no_points(self):
        ns, calls, doc, houses = fixture()
        self.assertTrue(ns["Register"](houses[0], doc.Buildings[0].Survey))
        ns["BuildOrder"](houses[0].position, 2)
        self.assertEqual(calls["reads"], [])
        houses[0].position = Vec((100.1, 10, 100))
        self.assertEqual(ns["BuildOrder"](houses[0].position, 2), [])

    def test_failed_reads_malformed_and_oversize_loads_are_once_until_clear(self):
        for options in ({"read_ok": False}, {"parse_ok": False}, {"raw": "{"},
                        {"raw": " " * 65537}, {"raw": ""}):
            with self.subTest(options={key: (len(value) if key == "raw" else value) for key, value in options.items()}):
                ns, calls, _, houses = fixture(**options)
                for _ in range(3): self.assertEqual(ns["BuildOrder"](houses[0].position, 2), [])
                self.assertEqual(len(calls["reads"]), 1)
                self.assertEqual(ns["s_Bindings"], [])
                ns["Clear"]()
                ns["BuildOrder"](houses[0].position, 2)
                self.assertEqual(len(calls["reads"]), 2)

    def test_strict_keys_reject_duplicates_unknown_missing_and_escaped_names(self):
        ns, _, doc, _ = fixture()
        valid = json.dumps(doc, default=encode)
        self.assertTrue(ns["ValidJsonKeys"](valid))
        invalid = [valid.replace('"SchemaVersion": 1', '"SchemaVersion": 1, "SchemaVersion": 1'),
                   valid.replace('"SchemaVersion": 1', '"Unexpected": 1'),
                   valid.replace('"SchemaVersion": 1, ', ''),
                   valid.replace('"Revision": 1', '"Revision": 1, "Revision": 1'),
                   valid.replace('"Id": 1', '"Id": 1, "Id": 1'),
                   valid.replace('"Survey":', '"Unknown":'),
                   valid.replace('"Build":', '"Bui\\u006cd":', 1),
                   valid + valid, "{}", "[]"]
        for raw in invalid:
            with self.subTest(raw=raw[:100]): self.assertFalse(ns["ValidJsonKeys"](raw))
        ns, calls, _, houses = fixture(raw=invalid[0])
        self.assertEqual(ns["BuildOrder"](houses[0].position, 2), [])
        self.assertEqual(calls["parse"], 0)

    def test_four_buildings_are_bounded_and_invalid_requests_do_not_load(self):
        doc, houses = synthetic_document(4)
        ns, calls, _, _ = fixture(document=doc, objects=houses)
        for point, budget in ((houses[0].position, 0), (houses[0].position, 4), (Vec((math.nan, 0, 0)), 2)):
            self.assertEqual(ns["BuildOrder"](point, budget), [])
        self.assertEqual(calls["reads"], [])
        self.assertTrue(ns["BindDiagnostic"](doc))
        self.assertEqual(len(ns["s_Bindings"]), 4)
        self.assertEqual(len(calls["queries"]), 4)
        self.assertTrue(all(0 < radius <= .5 for _, radius in calls["queries"]))

    def test_null_building_record_fails_closed_without_dereference(self):
        doc, houses = synthetic_document()
        doc.Buildings.Insert(None)
        ns, _, _, _ = fixture(document=doc, objects=houses)
        self.assertFalse(ns["BindDiagnostic"](doc))
        self.assertEqual(ns["s_Bindings"], [])


if __name__ == "__main__": unittest.main()
