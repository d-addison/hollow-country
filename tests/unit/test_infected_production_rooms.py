"""Execute authored production admission on explicit SYNTHETIC engine boundaries.

Every coordinate/hash here is fabricated test input. Passing these tests never
establishes native JSON/config/house behavior, authentic evidence or qualification.
"""
import copy
import json
import math
from types import SimpleNamespace
import unittest

if __package__:
    from .test_room_catalog_completion import Array, Vec, Text, House, Survey, Anchor, Record, PATH, authored, fixture
else:
    from test_room_catalog_completion import Array, Vec, Text, House, Survey, Anchor, Record, PATH, authored, fixture


class DTO(SimpleNamespace):
    def __init__(self):
        super().__init__(SchemaVersion=0, Build="", WorldName="", Classes=Array(), Buildings=Array())


def synthetic_production(count=1, anchors=1):
    """Pretends to be measured for boundary tests ONLY; never write a profile."""
    doc = DTO()
    doc.SchemaVersion, doc.Build, doc.WorldName = 1, "1.30.164289", "chernarusplus"
    doc.Classes = Array([SimpleNamespace(BuildingClass="SyntheticHouse", Disposition="covered"),
                         SimpleNamespace(BuildingClass="SyntheticShed", Disposition="unmeasured")])
    houses = []
    for index in range(count):
        house = House(position=(100 + index * 100, 10, 100))
        houses.append(house)
        points = Array()
        for slot in range(anchors):
            points.append(SimpleNamespace(Id=slot + 1, LocalPosition=Vec((slot, 0, 0)),
                LocalMin=Vec((slot - .4, -1, -.4)), LocalMax=Vec((slot + .4, 1, .4)),
                SourceRunId="native-boundary-001", SourceSha256="a" * 64,
                EvidenceKind="native-room-survey-v1"))
        doc.Buildings.append(SimpleNamespace(BuildingClass=house.kind,
            Position=house.position, Orientation=house.orientation,
            BoxMin=Vec((-16, -4, -16)), BoxMax=Vec((16, 16, 16)), Anchors=points))
    return doc, houses


def encode(value): return value.__dict__


def production_fixture(document=None, houses=None, *, server=True, diagnostic=False,
                       exists=True, read_ok=True, parse_ok=True, raw=None,
                       classes=None, version="1.30.164289", config_count=None, read_result=None,
                       house_classes=None):
    if document is None:
        document, houses = synthetic_production()
    ns, calls, _, _ = fixture(server=server, diagnostic=diagnostic)
    classes = ["SyntheticHouse", "SyntheticShed"] if classes is None else classes
    raw = json.dumps(document, default=encode) if raw is None else raw
    calls.update(exists=[], logs=[], config=[], io=[], closed=[])
    def file_exists(path):
        calls["exists"].append(path)
        return exists
    def open_file(path, mode):
        calls["reads"].append(path)
        return 1 if read_ok else 0
    def read_file(handle, content, limit):
        calls["io"].append(limit)
        content.value = raw[:limit]
        return len(content.value) if read_result is None else read_result
    def load(content, result, error):
        calls["parse"] += 1
        if not parse_ok: return False
        try: json.loads(str(content))
        except ValueError: return False
        result.__dict__.update(copy.deepcopy(document.__dict__))
        return True
    def query(position, radius, found, cargos):
        calls["queries"].append((position, radius))
        found.extend(houses or [])
    def child(path, index, output):
        calls["config"].append(index)
        if index >= len(classes): return False
        output.value = classes[index]
        return True
    game = SimpleNamespace(IsServer=lambda: server, GetWorldName=lambda: "chernarusplus",
        GetVersion=lambda output: setattr(output, "value", version), GetObjectsAtPosition3D=query,
        ConfigGetChildrenCount=lambda path: len(classes) if config_count is None else config_count,
        ConfigGetChildName=child,
        IsKindOf=lambda name, base: str(name) in (classes if house_classes is None else house_classes))
    ns.update(GetGame=lambda: game, FileExist=file_exists, OpenFile=open_file,
              ReadFile=read_file, CloseFile=lambda handle: calls["closed"].append(handle),
              FileMode=SimpleNamespace(READ=0), Print=calls["logs"].append,
              Loader=SimpleNamespace(LoadData=load), HCInfectedProductionRoomDocument=DTO,
              HCInfectedProductionRoomAnchor=Anchor, HCInfectedProductionRoomClass=SimpleNamespace,
              TStringArray=Array,
              HCInfectedRoomRecord=Record,
              s_ProductionBindings=Array(), s_ProductionClasses=Array(),
              s_ProductionAttempted=False, s_ProductionReason="rooms_not_loaded", s_JsonOffset=0,
              PRODUCTION_PATH="$profile:HollowCountry/Infected/production-rooms.json",
              MAX_PRODUCTION_BYTES=1048576, MAX_PRODUCTION_CLASSES=2048,
              MAX_CONFIG_CLASSES=32768, MAX_PRODUCTION_HOUSES=64,
              MAX_HOUSE_ANCHORS=16, MAX_TOTAL_ANCHORS=256)
    methods = {
        "ClearProduction": "", "ProductionReason": "", "ProductionServer": "",
        "ProductionCoverage": "covered=None, excluded=None",
        "ProductionToken": "value, limit", "ProductionHash": "value",
        "ProductionEvidence": "anchor", "ProductionDisposition": "value",
        "ProductionClassIndex": "document, className",
        "ValidateProductionCoverage": "document", "ValidateProductionHouse": "record",
        "BindProduction": "document", "ProductionJsonChar": "content", "ProductionJsonCode": "content",
        "ProductionJsonSkip": "content",
        "ProductionJsonText": "content", "ProductionJsonNumber": "content, integerOnly",
        "ProductionKeyBit": "kind, key", "ProductionRequiredKeys": "kind",
        "ProductionJsonValue": "content, kind, key", "ProductionJsonArray": "content, kind",
        "ProductionJsonObject": "content, kind", "ValidProductionJson": "content",
        "EnsureProductionLoaded": "", "BuildProductionOrder": "observedClue, budget, points=None",
        "OrderBindings": "observedClue, budget, bindings, points=None",
    }
    for name, arguments in methods.items(): authored(name, arguments, ns, diagnostic)
    return ns, calls, document, houses


class InfectedProductionRoomTests(unittest.TestCase):
    def test_normal_server_admits_data_once_and_reports_all_classes_without_routing(self):
        ns, calls, doc, houses = production_fixture()
        for _ in range(3): ns["EnsureProductionLoaded"]()
        self.assertEqual([ns["PRODUCTION_PATH"]], calls["reads"])
        self.assertEqual([1048577], calls["io"])
        self.assertEqual([1], calls["closed"])
        self.assertEqual(1, len(ns["s_ProductionBindings"]))
        self.assertEqual("rooms_admitted_measurements_path_audio_doors_pending", ns["ProductionReason"]())
        self.assertEqual([("SyntheticHouse", "covered"), ("SyntheticShed", "unmeasured")],
                         [(r.BuildingClass, r.Disposition) for r in ns["s_ProductionClasses"]])
        self.assertEqual((["SyntheticHouse"], ["SyntheticShed=unmeasured"]), ns["ProductionCoverage"]())
        self.assertEqual(1, len(calls["logs"]))
        self.assertIn("room classes=2; instances=1", calls["logs"][0])
        self.assertEqual([], ns["s_Bindings"])
        self.assertEqual([], ns["BuildOrder"](houses[0].position, 2))  # old consumer stays DIAG only
        self.assertEqual([houses[0].position], ns["BuildProductionOrder"](houses[0].position, 2))
        # Only data ordering is available; there is no route or qualification API here.
        source = PATH.read_text()
        for forbidden in ("EnableInvestigation =", "EnableNativePackRoutes =", ".SetWaypoints(", ".CreateGroup("):
            self.assertNotIn(forbidden, source)

    def test_client_has_no_profile_config_or_object_access(self):
        ns, calls, doc, houses = production_fixture(server=False)
        self.assertFalse(ns["BindProduction"](doc))
        ns["EnsureProductionLoaded"]()
        self.assertEqual([], ns["BuildProductionOrder"](houses[0].position, 1))
        for name in ("exists", "reads", "queries", "config", "logs"): self.assertEqual([], calls[name])

    def test_invalid_order_requests_do_not_load_and_moved_houses_are_not_used(self):
        ns, calls, doc, houses = production_fixture()
        for point, budget in ((houses[0].position, 0), (houses[0].position, 4),
                              (Vec((math.nan, 0, 0)), 2)):
            self.assertEqual([], ns["BuildProductionOrder"](point, budget))
        self.assertEqual([], calls["reads"])
        self.assertEqual([houses[0].position], ns["BuildProductionOrder"](houses[0].position, 2))
        houses[0].position = Vec((101, 10, 100))
        self.assertEqual([], ns["BuildProductionOrder"](houses[0].position, 2))

    def test_house_denominator_ignores_nonhouse_configs_and_reports_explicit_all_excluded(self):
        ns, _, _, _ = production_fixture(classes=["SyntheticHouse", "UnrelatedItem", "SyntheticShed"],
                                         house_classes=["SyntheticHouse", "SyntheticShed"])
        ns["EnsureProductionLoaded"]()
        self.assertEqual("rooms_admitted_measurements_path_audio_doors_pending", ns["ProductionReason"]())
        doc, houses = synthetic_production()
        doc.Buildings.Clear()
        doc.Classes[0].Disposition = "unmeasured"
        ns, _, _, _ = production_fixture(doc, houses)
        ns["EnsureProductionLoaded"]()
        covered, excluded = ns["ProductionCoverage"]()
        self.assertEqual([], covered)
        self.assertEqual(["SyntheticHouse=unmeasured", "SyntheticShed=unmeasured"], excluded)
        excluded.Clear()
        self.assertEqual(2, len(ns["ProductionCoverage"]()[1]))

    def test_total_anchor_boundary_is_admitted_as_data(self):
        doc, houses = synthetic_production(16, 16)
        ns, _, _, _ = production_fixture(doc, houses)
        self.assertTrue(ns["BindProduction"](doc))
        self.assertEqual(256, sum(len(b.Survey.Anchors) for b in ns["s_ProductionBindings"]))

    def test_native_read_failure_or_inconsistent_byte_count_does_not_parse(self):
        for read_result in (-1, 1):
            ns, calls, _, _ = production_fixture(read_result=read_result)
            ns["EnsureProductionLoaded"]()
            self.assertEqual("rooms_read", ns["ProductionReason"]())
            self.assertEqual(0, calls["parse"])
            self.assertEqual([1], calls["closed"])

    def test_header_wrong_runtime_build_and_wrong_world_are_specific(self):
        for field, value, reason in (("SchemaVersion", 2, "rooms_schema"),
                                    ("Build", "other", "rooms_build"),
                                    ("WorldName", "other", "rooms_world")):
            doc, houses = synthetic_production()
            setattr(doc, field, value)
            ns, calls, _, _ = production_fixture(doc, houses)
            ns["EnsureProductionLoaded"]()
            self.assertEqual(reason, ns["ProductionReason"]())
            self.assertEqual([], calls["queries"])
        ns, calls, _, _ = production_fixture(version="1.31.1")
        ns["EnsureProductionLoaded"]()
        self.assertEqual("rooms_build", ns["ProductionReason"]())

    def test_denominator_missing_unknown_duplicate_and_unknown_exclusion_fail_closed(self):
        mutations = [lambda d: d.Classes.pop(),
            lambda d: d.Classes.append(SimpleNamespace(BuildingClass="Unknown", Disposition="unmeasured")),
            lambda d: d.Classes.append(copy.deepcopy(d.Classes[0])),
            lambda d: setattr(d.Classes[1], "Disposition", "trust-me"),
            lambda d: setattr(d.Classes[0], "Disposition", "unmeasured"),
            lambda d: setattr(d.Classes[1], "Disposition", "covered")]
        for mutate in mutations:
            doc, houses = synthetic_production()
            mutate(doc)
            ns, calls, _, _ = production_fixture(doc, houses)
            ns["EnsureProductionLoaded"]()
            self.assertEqual("rooms_coverage", ns["ProductionReason"]())
            self.assertEqual([], ns["s_ProductionBindings"])
            self.assertEqual([], ns["s_ProductionClasses"])
        ns, calls, _, _ = production_fixture(config_count=32769)
        ns["EnsureProductionLoaded"]()
        self.assertEqual("rooms_denominator_cap", ns["ProductionReason"]())
        self.assertEqual([], calls["config"])

    def test_per_house_total_and_instance_caps(self):
        for count, anchors in ((1, 17), (17, 16), (65, 1)):
            doc, houses = synthetic_production(count, anchors)
            ns, calls, _, _ = production_fixture(doc, houses)
            ns["EnsureProductionLoaded"]()
            self.assertEqual([], ns["s_ProductionBindings"])
            self.assertEqual("rooms_limits", ns["ProductionReason"]())

    def test_anchor_evidence_is_required_bounded_and_never_synthetic(self):
        for field, value in (("SourceRunId", ""), ("SourceRunId", "native-synthetic-001"),
                             ("SourceRunId", "native-" + "a" * 100),
                             ("SourceSha256", ""), ("SourceSha256", "x" * 64),
                             ("SourceSha256", "0" * 64), ("SourceSha256", "a" * 65),
                             ("EvidenceKind", "synthetic")):
            doc, houses = synthetic_production()
            setattr(doc.Buildings[0].Anchors[0], field, value)
            ns, _, _, _ = production_fixture(doc, houses)
            ns["EnsureProductionLoaded"]()
            self.assertEqual("rooms_evidence", ns["ProductionReason"](), (field, value))
            self.assertEqual([], ns["s_ProductionBindings"])

    def test_measured_box_room_bounds_pose_nonfinite_and_duplicates(self):
        for mutate in (
            lambda r: setattr(r, "BoxMin", Vec((math.nan, -4, -16))),
            lambda r: setattr(r, "BoxMax", Vec((513, 16, 16))),
            lambda r: setattr(r, "BoxMax", r.BoxMin),
            lambda r: setattr(r.Anchors[0], "LocalPosition", Vec((17, 0, 0))),
            lambda r: setattr(r.Anchors[0], "LocalPosition", Vec((math.nan, 0, 0))),
            lambda r: setattr(r.Anchors[0], "LocalMin", Vec((-17, -1, -.4))),
            lambda r: setattr(r.Anchors[0], "LocalMax", Vec((math.inf, 1, .4))),
            lambda r: setattr(r.Anchors[0], "Id", 0),
            lambda r: r.Anchors.append(copy.deepcopy(r.Anchors[0])),
        ):
            doc, houses = synthetic_production()
            mutate(doc.Buildings[0])
            ns, _, _, _ = production_fixture(doc, houses)
            # Direct DTO admission isolates semantic validation from JSON nonfinite rejection.
            self.assertFalse(ns["BindProduction"](doc))
            self.assertEqual("rooms_geometry", ns["ProductionReason"]())
            self.assertEqual([], ns["s_ProductionBindings"])
        for field, value in (("Position", Vec((101, 10, 100))),
                             ("Orientation", Vec((361, 0, 0)))):
            doc, houses = synthetic_production()
            setattr(doc.Buildings[0], field, value)
            ns, _, _, _ = production_fixture(doc, houses)
            self.assertFalse(ns["BindProduction"](doc))
            self.assertEqual("rooms_binding", ns["ProductionReason"]())

    def test_atomic_publish_ambiguous_house_and_owned_copy(self):
        doc, houses = synthetic_production(2)
        doc.Buildings[1].Anchors[0].SourceRunId = ""
        ns, _, _, _ = production_fixture(doc, houses)
        self.assertFalse(ns["BindProduction"](doc))
        self.assertEqual([], ns["s_ProductionBindings"])
        doc, houses = synthetic_production()
        ns, _, _, _ = production_fixture(doc, houses + [House()])
        self.assertFalse(ns["BindProduction"](doc))
        ns, _, _, _ = production_fixture(doc, houses)
        self.assertTrue(ns["BindProduction"](doc))
        doc.Buildings[0].Anchors[0].LocalPosition = Vec((99, 0, 0))
        doc.Classes[0].Disposition = "unmeasured"
        self.assertEqual(Vec((0, 0, 0)), ns["s_ProductionBindings"][0].Survey.Anchors[0].LocalPosition)
        self.assertEqual("covered", ns["s_ProductionClasses"][0].Disposition)
        self.assertFalse(ns["BindProduction"](doc))
        self.assertEqual(1, len(ns["s_ProductionBindings"]))

    def test_io_json_refusals_are_logged_once_until_clear(self):
        for options, reason in (({"exists": False}, "rooms_missing"),
                                ({"read_ok": False}, "rooms_read"),
                                ({"parse_ok": False}, "rooms_json"),
                                ({"raw": " " * 1048577}, "rooms_size"),
                                ({"raw": ""}, "rooms_size"), ({"raw": "{"}, "rooms_json")):
            ns, calls, _, _ = production_fixture(**options)
            for _ in range(3): ns["EnsureProductionLoaded"]()
            self.assertEqual(reason, ns["ProductionReason"]())
            self.assertEqual(1, len(calls["logs"]))
            self.assertLessEqual(len(calls["reads"]), 1)
            self.assertEqual([], ns["s_ProductionBindings"])
            ns["ClearProduction"]()
            ns["EnsureProductionLoaded"]()
            self.assertEqual(2, len(calls["logs"]))

    def test_strict_production_json_rejects_unknown_duplicate_missing_types_shapes_and_escapes(self):
        ns, _, doc, _ = production_fixture()
        valid = json.dumps(doc, default=encode)
        self.assertTrue(ns["ValidProductionJson"](valid))
        invalid = [valid.replace('"SchemaVersion": 1', '"SchemaVersion": 1, "SchemaVersion": 1'),
            valid.replace('"SchemaVersion": 1', '"SchemaVersion": "1"'),
            valid.replace('"SchemaVersion": 1', '"SchemaVersion": true'),
            valid.replace('"Build":', '"Bui\\u006cd":', 1),
            valid.replace('"Id": 1', '"Id": 1, "Unknown": 0'),
            valid.replace('"Id": 1', '"Id": 1, "Id": 1'),
            valid.replace('"Id": 1, ', ''),
            valid.replace('"Id": 1', '"Id": 1.0'),
            valid.replace('"LocalPosition": [0, 0, 0]', '"LocalPosition": [0, 0]'),
            valid.replace('"LocalPosition": [0, 0, 0]', '"LocalPosition": [0, 0, 0, 0]'),
            valid.replace('"LocalPosition": [0, 0, 0]', '"LocalPosition": "0 0 0"'),
            valid.replace('"LocalPosition": [0, 0, 0]', '"LocalPosition": [NaN, 0, 0]'),
            valid.replace('"Classes": [', '"Classes": [null,'),
            valid.replace('"Classes": [', '"Classes": [['),
            valid.replace('"Classes": [', '"Classes": {'),
            valid.replace('"Buildings": [', '"Buildings": [true,'),
            valid.replace('"Build": "1.30.164289"', '"Build": null'),
            valid.replace('"Id": 1', '"Id": 01'), valid[:-1] + ',}',
            valid + valid, '{}', '[]']
        for raw in invalid:
            with self.subTest(raw=raw[:120]): self.assertFalse(ns["ValidProductionJson"](raw))

    def test_truncated_json_never_reads_beyond_string_and_integer_overflow_is_not_coerced(self):
        ns, _, doc, _ = production_fixture()
        valid = json.dumps(doc, default=encode)
        for end in range(len(valid)):
            self.assertFalse(ns["ValidProductionJson"](valid[:end]), end)
        for key in ("Id", "SchemaVersion"):
            self.assertFalse(ns["ValidProductionJson"](valid.replace('"' + key + '": 1',
                                                                    '"' + key + '": 4294967297')))
        self.assertTrue(ns["ValidProductionJson"](valid.replace('"LocalPosition": [0, 0, 0]',
                                                               '"LocalPosition": [-0.0, 0e0, 0.0E+0]')))


if __name__ == "__main__": unittest.main()
