"""Execute authored production admission on explicit SYNTHETIC engine boundaries.

Every coordinate/hash here is fabricated test input. Passing these tests never
establishes native JSON/config/house behavior, authentic evidence or qualification.
"""
import copy
import json
import math
import re
from pathlib import Path
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
    doc.Classes = Array([SimpleNamespace(BuildingClass="Synthetic_House_1", Disposition="covered"),
                         SimpleNamespace(BuildingClass="Synthetic_Shed_1", Disposition="unmeasured")])
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
                       house_classes=None, world_name="chernarusplus"):
    if document is None:
        document, houses = synthetic_production()
    ns, calls, _, _ = fixture(server=server, diagnostic=diagnostic)
    classes = ["Synthetic_House_1", "Synthetic_Shed_1"] if classes is None else classes
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
    game = SimpleNamespace(IsServer=lambda: server, GetWorldName=lambda: world_name,
        GetVersion=lambda output: setattr(output, "value", version), GetObjectsAtPosition3D=query,
        ConfigGetChildrenCount=lambda path: len(classes) if config_count is None else config_count,
        ConfigGetChildName=child,
        IsKindOf=lambda name, base: str(name) in (classes if house_classes is None else house_classes))
    ns.update(GetGame=lambda: game, FileExist=file_exists, OpenFile=open_file,
              ReadFile=read_file, CloseFile=lambda handle: calls["closed"].append(handle),
              FileMode=SimpleNamespace(READ=0), Print=calls["logs"].append,
              Loader=SimpleNamespace(LoadData=load), HCInfectedProductionRoomDocument=DTO,
              HCInfectedProductionRoomAnchor=Anchor, HCInfectedOwnedProductionRoomAnchor=Anchor, HCInfectedProductionRoomClass=SimpleNamespace,
              TStringArray=Array,
              HCInfectedRoomRecord=Record,
              s_ProductionBindings=Array(), s_ProductionClasses=Array(),
              s_ProductionAttempted=False, s_ProductionReason="rooms_not_loaded", s_ProductionContext="", s_JsonOffset=0,
              PRODUCTION_PATH="$profile:HollowCountry/Infected/production-rooms.json",
              MAX_PRODUCTION_BYTES=1048576, MAX_PRODUCTION_CLASSES=2048,
              MAX_CONFIG_CLASSES=32768, MAX_PRODUCTION_HOUSES=64,
              MAX_HOUSE_ANCHORS=16, MAX_TOTAL_ANCHORS=256,
              # Template binding state and constants (see the T4 section of the interiors contract).
              s_TemplateBindings=Array(), s_ConflictHouses=Array(), s_TemplateRefusals=Array(),
              s_BindRadius=30, s_BindQueryCap=2, s_BindQueries=0, s_BindStamp=0, s_ConflictsResolved=False,
              s_TemplateLogged=False, s_TemplateReason="rooms_templates_not_loaded",
              s_TemplateCovered=0, s_TemplateDenominator=0,
              DEFAULT_BIND_RADIUS=30, DEFAULT_BIND_QUERIES=2, MAX_TEMPLATE_CANDIDATES=1024,
              MAX_TEMPLATE_FOUND=16, MAX_TEMPLATE_LOG=64,
              TEMPLATE_EVIDENCE_KIND="native-room-survey-v1",
              TEMPLATE_READY="rooms_templates_provisional_path_audio_doors_pending",
              Math=SimpleNamespace(Min=min, AbsFloat=abs),
              HCInteriorTemplates=SimpleNamespace(Loaded=lambda: False),  # synthetic reader stub: no pack
              LogTemplateAdmission=lambda: None, BindTemplateHouses=lambda clue: None,
              ResolveLegacyConflicts=lambda: None)
    methods = {
        "ClearProduction": "", "ProductionReason": "", "ProductionServer": "",
        "ProductionCoverage": "covered=None, excluded=None",
        "ProductionToken": "value, limit", "ProductionHash": "value",
        "ProductionEvidence": "anchor", "ProductionDisposition": "value",
        "ProductionClassIndex": "document, className",
        "ValidateProductionCoverage": "document", "ValidateProductionHouse": "record",
        "ProductionBuildLabel": "value", "BindProduction": "document", "ProductionJsonChar": "content", "ProductionJsonCode": "content",
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
        self.assertEqual([("Synthetic_House_1", "covered"), ("Synthetic_Shed_1", "unmeasured")],
                         [(r.BuildingClass, r.Disposition) for r in ns["s_ProductionClasses"]])
        self.assertEqual((["Synthetic_House_1"], ["Synthetic_Shed_1=unmeasured"]), ns["ProductionCoverage"]())
        self.assertEqual(1, len(calls["logs"]))
        self.assertIn("room classes=2; instances=1", calls["logs"][0])
        self.assertEqual([], ns["s_Bindings"])
        self.assertEqual([], ns["BuildOrder"](houses[0].position, 2))  # old consumer stays DIAG only unless a template pack is loaded
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
        ns["EnsureProductionLoaded"]()
        self.assertEqual([], ns["BuildProductionOrder"](houses[0].position, 4))
        self.assertEqual([houses[0].position], ns["BuildProductionOrder"](houses[0].position, 2))
        houses[0].position = Vec((101, 10, 100))
        self.assertEqual([], ns["BuildProductionOrder"](houses[0].position, 2))

    def test_house_denominator_ignores_nonhouse_configs_and_reports_explicit_all_excluded(self):
        ns, _, _, _ = production_fixture(classes=["Synthetic_House_1", "UnrelatedItem", "Synthetic_Shed_1"],
                                         house_classes=["Synthetic_House_1", "Synthetic_Shed_1"])
        ns["EnsureProductionLoaded"]()
        self.assertEqual("rooms_admitted_measurements_path_audio_doors_pending", ns["ProductionReason"]())
        doc, houses = synthetic_production()
        doc.Buildings.Clear()
        doc.Classes[0].Disposition = "unmeasured"
        ns, _, _, _ = production_fixture(doc, houses)
        ns["EnsureProductionLoaded"]()
        covered, excluded = ns["ProductionCoverage"]()
        self.assertEqual([], covered)
        self.assertEqual(["Synthetic_House_1=unmeasured", "Synthetic_Shed_1=unmeasured"], excluded)
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
            self.assertEqual("rooms_limits" if count == 17 else "rooms_json", ns["ProductionReason"]())

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


    def assert_direct_refused(self, doc, houses, reason, **options):
        ns, calls, _, _ = production_fixture(doc, houses, **options)
        self.assertFalse(ns["BindProduction"](doc))
        self.assertEqual(reason, ns["ProductionReason"]())
        self.assertEqual([], ns["s_ProductionBindings"])
        self.assertEqual([], ns["s_ProductionClasses"])
        return ns, calls

    def test_json_preflight_guards_native_load_path(self):
        doc, houses = synthetic_production()
        valid = json.dumps(doc, default=encode)
        oversized, _ = synthetic_production(1, 17)
        cases = {
            "unknown": valid.replace('"Id": 1', '"Id": 1, "Unknown": 0'),
            "duplicate": valid.replace('"Id": 1', '"Id": 1, "Id": 1'),
            "17 anchors": json.dumps(oversized, default=encode),
            "A escape": valid.replace('native-boundary-001', r'native-boundary-001\u0041'),
        }
        for name, raw in cases.items():
            with self.subTest(name=name):
                json.loads(raw)  # Deliberately accepted by our native-parser stand-in.
                ns, calls, _, _ = production_fixture(doc, houses, raw=raw)
                ns["EnsureProductionLoaded"]()
                self.assertEqual(0, calls["parse"])
                self.assertEqual("rooms_json", ns["ProductionReason"]())
                self.assertEqual([], ns["s_ProductionBindings"])
                self.assertEqual([], ns["s_ProductionClasses"])

    def test_clear_resets_production_and_allows_one_new_read_and_log(self):
        ns, calls, _, houses = production_fixture()
        ns["EnsureProductionLoaded"]()
        self.assertEqual(1, len(ns["s_ProductionBindings"]))
        self.assertEqual(2, len(ns["s_ProductionClasses"]))
        ns["Clear"]()
        self.assertEqual([], ns["s_ProductionBindings"])
        self.assertEqual([], ns["s_ProductionClasses"])
        self.assertEqual("rooms_not_loaded", ns["ProductionReason"]())
        self.assertFalse(ns["s_ProductionAttempted"])
        self.assertEqual([], ns["BuildProductionOrder"](houses[0].position, 2))
        self.assertEqual(1, len(calls["reads"]))
        for _ in range(3): ns["EnsureProductionLoaded"]()
        self.assertEqual(2, len(calls["reads"]))
        self.assertEqual(2, len(calls["logs"]))
        self.assertEqual(1, len(ns["s_ProductionBindings"]))

    def assert_run_id_refused(self, value):
        doc, houses = synthetic_production()
        doc.Buildings[0].Anchors[0].SourceRunId = value
        self.assert_direct_refused(doc, houses, "rooms_evidence")

    def test_evidence_native_prefix_required(self):
        self.assert_run_id_refused("run-0001")

    def test_evidence_fixture_marker_refused(self):
        self.assert_run_id_refused("native-fixture-1")

    def test_evidence_selftest_marker_refused(self):
        self.assert_run_id_refused("native-selftest-1")

    def test_evidence_run_id_minimum_eight_characters(self):
        self.assert_run_id_refused("native-")
        doc, houses = synthetic_production()
        doc.Buildings[0].Anchors[0].SourceRunId = "native-1"
        ns, _, _, _ = production_fixture(doc, houses)
        self.assertTrue(ns["BindProduction"](doc))

    def test_owned_anchor_copies_all_evidence_fields(self):
        ns, _, doc, _ = production_fixture()
        self.assertTrue(ns["BindProduction"](doc))
        supplied = doc.Buildings[0].Anchors[0]
        owned = ns["s_ProductionBindings"][0].Survey.Anchors[0]
        self.assertIsNot(supplied, owned)
        for field in ("SourceRunId", "SourceSha256", "EvidenceKind"):
            expected = getattr(supplied, field)
            self.assertEqual(expected, getattr(owned, field, None), field)
            setattr(supplied, field, "changed")
            self.assertEqual(expected, getattr(owned, field), field)

    def test_document_and_runtime_on_same_unpinned_build_refused(self):
        doc, houses = synthetic_production()
        doc.Build = "1.31.1"
        self.assert_direct_refused(doc, houses, "rooms_build", version="1.31.1")

    def test_native_full_engine_build_admits_the_canonical_document(self):
        """Real engine GetVersion is 1.30.164289.70 (native census.json); the pinned document is 1.30.164289."""
        for version in ("1.30.164289.70", "1.30.164289"):
            with self.subTest(version=version):
                ns, calls, _, _ = production_fixture(version=version)
                ns["EnsureProductionLoaded"]()
                self.assertEqual("rooms_admitted_measurements_path_audio_doors_pending", ns["ProductionReason"]())
                self.assertEqual(1, len(ns["s_ProductionBindings"]))

    def test_other_engine_builds_still_refuse_even_with_a_matching_document(self):
        for version in ("1.30.164289.7x", "1.30.164289.700", "1.30.1642890", " 1.30.164289.70", "1.30.164289 ", ""):
            with self.subTest(version=version):
                doc, houses = synthetic_production()
                doc.Build = version
                self.assert_direct_refused(doc, houses, "rooms_build", version=version)
                doc, houses = synthetic_production()
                self.assert_direct_refused(doc, houses, "rooms_build", version=version)

    def test_world_name_compare_is_case_normalised(self):
        ns, _, _, _ = production_fixture(world_name="ChernarusPlus")
        ns["EnsureProductionLoaded"]()
        self.assertEqual("rooms_admitted_measurements_path_audio_doors_pending", ns["ProductionReason"]())
        doc, houses = synthetic_production()
        self.assert_direct_refused(doc, houses, "rooms_world", world_name="enoch")

    def test_257th_total_anchor_refused_directly(self):
        doc, houses = synthetic_production(17, 16)
        doc.Buildings[-1].Anchors = Array([doc.Buildings[-1].Anchors[0]])
        self.assertEqual(257, sum(len(row.Anchors) for row in doc.Buildings))
        self.assert_direct_refused(doc, houses, "rooms_limits")

    def test_65th_house_refused_directly(self):
        doc, houses = synthetic_production(65)
        self.assert_direct_refused(doc, houses, "rooms_limits")

    def test_17th_house_anchor_refused_directly(self):
        doc, houses = synthetic_production(1, 17)
        # All 17 points otherwise fit the declared house box.
        doc.Buildings[0].BoxMax = Vec((17, 16, 16))
        self.assert_direct_refused(doc, houses, "rooms_limits")

    def test_zero_anchor_house_refused_directly(self):
        doc, houses = synthetic_production(1, 0)
        self.assert_direct_refused(doc, houses, "rooms_limits")

    def test_house_box_below_minus_512_refused(self):
        doc, houses = synthetic_production()
        doc.Buildings[0].BoxMin = Vec((-513, -4, -16))
        self.assert_direct_refused(doc, houses, "rooms_geometry")

    def test_anchor_id_above_64_refused(self):
        doc, houses = synthetic_production()
        doc.Buildings[0].Anchors[0].Id = 65
        self.assert_direct_refused(doc, houses, "rooms_geometry")

    def test_duplicate_id_at_distinct_valid_positions_refused(self):
        doc, houses = synthetic_production(1, 2)
        doc.Buildings[0].Anchors[1].Id = 1
        self.assert_direct_refused(doc, houses, "rooms_geometry")

    def test_spacing_below_one_with_distinct_ids_refused(self):
        doc, houses = synthetic_production(1, 2)
        second = doc.Buildings[0].Anchors[1]
        second.LocalPosition = Vec((.5, 0, 0))
        second.LocalMin = Vec((.1, -1, -.4))
        second.LocalMax = Vec((.9, 1, .4))
        self.assert_direct_refused(doc, houses, "rooms_geometry")

    def test_local_position_below_room_min_refused(self):
        doc, houses = synthetic_production()
        doc.Buildings[0].Anchors[0].LocalPosition = Vec((-.5, 0, 0))
        self.assert_direct_refused(doc, houses, "rooms_geometry")

    def test_zero_volume_room_containing_point_refused(self):
        doc, houses = synthetic_production()
        anchor = doc.Buildings[0].Anchors[0]
        anchor.LocalMin = anchor.LocalMax = anchor.LocalPosition
        self.assert_direct_refused(doc, houses, "rooms_geometry")

    def test_nonhouse_padding_cannot_replace_missing_house_class(self):
        doc, houses = synthetic_production()
        doc.Classes[1].BuildingClass = "Unrelated_Item"
        self.assert_direct_refused(doc, houses, "rooms_coverage",
            classes=["Synthetic_House_1", "Synthetic_Shed_1", "Unrelated_Item"],
            house_classes=["Synthetic_House_1", "Synthetic_Shed_1"])

    def test_second_valid_bind_refused_and_publication_unchanged(self):
        ns, _, doc, _ = production_fixture()
        self.assertTrue(ns["BindProduction"](doc))
        bindings, classes = ns["s_ProductionBindings"], ns["s_ProductionClasses"]
        self.assertFalse(ns["BindProduction"](doc))
        self.assertIs(bindings, ns["s_ProductionBindings"])
        self.assertIs(classes, ns["s_ProductionClasses"])
        self.assertEqual("rooms_admitted_measurements_path_audio_doors_pending", ns["ProductionReason"]())

    def test_house_class_cap_reports_observed_counts_without_claiming_coverage(self):
        doc, houses = synthetic_production()
        classes = ["Synthetic_House_1", "Synthetic_Shed_1"]
        classes += ["Synthetic_House_" + str(i) for i in range(2, 2049)]
        ns, calls, _, _ = production_fixture(doc, houses, classes=classes + ["Unrelated_Item"],
                                           house_classes=classes)
        for _ in range(3): ns["EnsureProductionLoaded"]()
        self.assertEqual("rooms_house_class_cap", ns["ProductionReason"]())
        self.assertEqual([], ns["ProductionCoverage"]()[0])
        self.assertEqual([], ns["s_ProductionClasses"])
        self.assertEqual(len(classes) + 1, len(calls["config"]))
        self.assertEqual(1, len(calls["logs"]))
        self.assertIn("config children=2050; House classes=2049", calls["logs"][0])
        self.assertLess(len(calls["logs"][0]), 256)

    def test_2049th_declared_class_refused_directly_before_config_scan(self):
        doc, houses = synthetic_production()
        doc.Classes.extend(SimpleNamespace(BuildingClass="Synthetic_Excluded_" + str(i),
                                          Disposition="unmeasured") for i in range(2047))
        self.assertEqual(2049, len(doc.Classes))
        _, calls = self.assert_direct_refused(doc, houses, "rooms_limits")
        self.assertEqual([], calls["config"])

    def test_direct_json_preflight_rejects_1mib_plus_one_before_scanning(self):
        ns, _, doc, _ = production_fixture()
        valid = json.dumps(doc, default=encode)
        raw = valid + " " * (1048577 - len(valid))
        self.assertEqual(1048577, len(raw))
        self.assertFalse(ns["ValidProductionJson"](raw))
        self.assertEqual(0, ns["s_JsonOffset"])

    def test_json_fraction_requires_digits_before_native_parser(self):
        ns, calls, doc, houses = production_fixture()
        raw = json.dumps(doc, default=encode).replace('"LocalPosition": [0, 0, 0]',
                                                     '"LocalPosition": [0., 0, 0]')
        self.assertFalse(ns["ValidProductionJson"](raw))
        ns, calls, _, _ = production_fixture(doc, houses, raw=raw)
        ns["EnsureProductionLoaded"]()
        self.assertEqual(0, calls["parse"])
        self.assertEqual("rooms_json", ns["ProductionReason"]())

    def test_production_anchor_dto_is_flat_with_geometry_and_evidence(self):
        source = PATH.read_text()
        match = re.search(r'class HCInfectedProductionRoomAnchor\s*\{(.*?)\n\}', source, re.S)
        self.assertIsNotNone(match, "native JSON must not rely on inherited fields")
        for field, kind in (("Id", "int"), ("LocalPosition", "vector"), ("LocalMin", "vector"),
                            ("LocalMax", "vector"), ("SourceRunId", "string"),
                            ("SourceSha256", "string"), ("EvidenceKind", "string")):
            self.assertRegex(match[1], r'\b' + kind + ' ' + field + ';')
        self.assertIn("bool Contains(vector point)", match[1])

    def test_valid_production_order_never_loads_on_first_tick(self):
        ns, calls, _, houses = production_fixture()
        for _ in range(3):
            self.assertEqual([], ns["BuildProductionOrder"](houses[0].position, 2))
        for key in ("exists", "reads", "parse", "config", "queries", "logs"):
            self.assertFalse(calls[key], key)
        self.assertEqual("rooms_not_loaded", ns["ProductionReason"]())
        ns["EnsureProductionLoaded"]()
        self.assertEqual([houses[0].position], ns["BuildProductionOrder"](houses[0].position, 2))
        self.assertEqual(1, len(calls["reads"]))

    def test_build_refusal_logs_observed_build_bounded_and_printable(self):
        for version, label in (("1.31.1", "1.31.1"), ("x" * 100, "x" * 32),
                               ("1.31\n.1", "1.31?.1")):
            with self.subTest(version=version):
                ns, calls, _, _ = production_fixture(version=version)
                for _ in range(3): ns["EnsureProductionLoaded"]()
                self.assertEqual("rooms_build", ns["ProductionReason"]())
                self.assertEqual(1, len(calls["logs"]))
                self.assertIn("observed build=" + label + ";", calls["logs"][0])
                self.assertNotIn("\n", calls["logs"][0])
                self.assertLess(len(calls["logs"][0]), 256)

    def test_string_ascii_calls_use_a_named_local(self):
        self.assertNotRegex(PATH.read_text(), r'\.Get\([^\n;]*\)\.ToAscii\(')


# --- Class-level template anchors, bound lazily (interior templates contract, T4) -------------
# Everything below is SYNTHETIC: fabricated rooms, hashes and a test-only stand-in for the T3
# reader (HCInteriorTemplates). Passing proves bind/refusal control flow only, never DayZ
# behaviour. Nothing here is, or may become, a pack.
TEMPLATE_FIXTURE = {"Synthetic": True, "Reader": "test-only stub of HCInteriorTemplates"}
TEMPLATE_METHODS = {
    "ConfigureBinding": "radius, queriesPerTick", "BeginTick": "", "ResolveLegacyConflicts": "",
    "TemplateReason": "",
    "NoteTemplateRefusal": "reason, detail", "CountTemplateClasses": "", "LogTemplateAdmission": "",
    "TemplateAnchorTotal": "", "EvictTemplates": "incoming", "TemplateGeometry": "layout",
    "TemplateBinding": "house, layout", "FindTemplateBinding": "house", "LegacyClaims": "house",
    "DropLegacy": "house", "DropTemplate": "house", "ConflictKnown": "house", "MarkConflict": "house",
    "TemplateAmbiguous": "house, found", "AdmitTemplateHouse": "house, found",
    "BindTemplateHouses": "observedClue", "ClearProduction": "",
    "BuildProductionOrder": "observedClue, budget, points=None",
}


def synthetic_room(room_id, x, half=.8):
    return SimpleNamespace(Id=room_id, Label="room", Min=Array((x - half, -1, -half)),
                           Max=Array((x + half, 1, half)), Anchor=Array((x, 0, 0)), FloorY=-1, Cells=4)


def synthetic_template(kind="Synthetic_House_1", rooms=1, box=32):
    return SimpleNamespace(BuildingClass=kind, TemplateId=kind.lower() + "-v1",
        Box=SimpleNamespace(Min=Array((-box, -4, -box)), Max=Array((box, 16, box))),
        Evidence=Array([SimpleNamespace(Kind="native-room-survey-v1", RunId="c" * 32, Sha256="d" * 64)]),
        Rooms=Array(synthetic_room(index + 1, index * 2) for index in range(rooms)))


def spaced_houses(count, kind="Synthetic_House_1"):
    return [House(position=(100 + index * 100, 10, 100), kind=kind) for index in range(count)]


def template_fixture(houses, *, loaded=True, rows=None, templates=None, legacy_houses=None, **options):
    """Legacy file is empty unless legacy_houses names the instance the legacy file claims."""
    doc, claimed = synthetic_production()
    if legacy_houses is None:
        doc.Buildings = Array()
        doc.Classes[0].Disposition = "unmeasured"
    else:
        doc.Buildings[0].Position = legacy_houses[0].position
        doc.Buildings[0].Orientation = legacy_houses[0].orientation
    ns, calls, _, _ = production_fixture(doc, houses, **options)
    state = {"loaded": loaded, "tick": 1.0, "rows": {"Synthetic_House_1": "covered"} if rows is None else rows,
             "templates": {"Synthetic_House_1": synthetic_template()} if templates is None else templates}
    calls.update(row_calls=[], template_calls=[])
    def class_row(cls):
        calls["row_calls"].append(str(cls))
        status = state["rows"].get(str(cls))
        if status is None: return None
        return SimpleNamespace(BuildingClass=str(cls), Rooms=status, Furniture="covered", Search="covered")
    def template(cls):
        calls["template_calls"].append(str(cls))
        return state["templates"].get(str(cls))
    # Mirrors T3's real HCInteriorTemplates signatures (bld-T3 HCInteriorTemplates.c): points and boxes are
    # array<float>; VectorValid also requires Count() == 3 and a sane value, AsVector builds a vector.
    def vector_valid(value, limit):
        return value is not None and len(value) == 3 and all(math.isfinite(v) and abs(v) <= limit for v in value)
    def box_valid(minimum, maximum):
        return vector_valid(minimum, 512) and vector_valid(maximum, 512) and all(minimum[i] < maximum[i] for i in range(3))
    def inside(point, minimum, maximum):
        return all(minimum[i] <= point[i] <= maximum[i] for i in range(3))
    ns["HCInteriorTemplates"] = SimpleNamespace(Loaded=lambda: state["loaded"], ClassRow=class_row, Template=template,
        VectorValid=vector_valid, BoxValid=box_valid, Inside=inside, AsVector=lambda value: Vec((value[0], value[1], value[2])))
    # GetTickTime is an elapsed clock, not a tick identity: it changes on every call here.
    clock = {"now": 1.0}
    def jittering_clock():
        clock["now"] += .001
        return clock["now"]
    ns["GetGame"]().GetTickTime = jittering_clock
    for name, arguments in TEMPLATE_METHODS.items(): authored(name, arguments, ns, False)
    ns["state"] = state
    return ns, calls


def order(ns, house_or_point, budget=2, advance=True):
    point = house_or_point.position if isinstance(house_or_point, House) else house_or_point
    if advance: ns["BeginTick"]()  # the module tick starts a new budget window
    return ns["BuildProductionOrder"](point, budget)


class TemplateAnchorBindingTests(unittest.TestCase):
    def test_fixture_is_explicitly_synthetic_and_never_a_pack(self):
        self.assertTrue(TEMPLATE_FIXTURE["Synthetic"])
        self.assertNotIn('"Synthetic":', json.dumps(synthetic_template(), default=lambda o: o.__dict__))

    def test_clue_binds_a_covered_house_lazily_and_converts_anchors_with_model_to_world(self):
        houses = spaced_houses(1)
        ns, calls = template_fixture(houses)
        self.assertEqual([], ns["s_TemplateBindings"])
        self.assertEqual([], calls["queries"])  # nothing at start: binding waits for a clue
        self.assertEqual([houses[0].position], order(ns, houses[0]))
        self.assertEqual(1, len(ns["s_TemplateBindings"]))
        self.assertEqual([(houses[0].position, 30)], calls["queries"])
        anchor = ns["s_TemplateBindings"][0].Survey.Anchors[0]
        self.assertEqual(Vec((0, 0, 0)), anchor.LocalPosition)  # stored in the model frame
        self.assertEqual(("native-room-survey-v1", "c" * 32, "d" * 64),
                         (anchor.EvidenceKind, anchor.SourceRunId, anchor.SourceSha256))

    def test_two_rooms_order_the_clue_room_first_then_the_nearest(self):
        houses = spaced_houses(1)
        ns, _ = template_fixture(houses, templates={"Synthetic_House_1": synthetic_template(rooms=3)})
        clue = Vec((100, 10, 100))
        self.assertEqual([Vec((100, 10, 100)), Vec((102, 10, 100))], order(ns, clue, 2))

    def test_bind_radius_binds_at_29_m_and_not_at_31_m(self):
        houses = spaced_houses(1)
        for distance, bound in ((29, 1), (30, 1), (31, 0)):
            with self.subTest(distance=distance):
                ns, calls = template_fixture(houses)
                order(ns, Vec((100 + distance, 10, 100)))
                self.assertEqual(bound, len(ns["s_TemplateBindings"]))
                self.assertEqual([30], [radius for _, radius in calls["queries"]])

    def test_configured_radius_and_cap_obey_the_setting_bounds(self):
        houses = spaced_houses(1)
        ns, calls = template_fixture(houses)
        for radius, queries in ((4, 2), (61, 2), (30, 0), (30, 9)):
            self.assertFalse(ns["ConfigureBinding"](radius, queries), (radius, queries))
        self.assertTrue(ns["ConfigureBinding"](10, 1))
        order(ns, Vec((111, 10, 100)))
        self.assertEqual(0, len(ns["s_TemplateBindings"]))
        self.assertEqual([10], [radius for _, radius in calls["queries"]])
        order(ns, Vec((109, 10, 100)))
        self.assertEqual(1, len(ns["s_TemplateBindings"]))

    def test_per_tick_query_cap_defers_extra_binds_to_the_next_tick(self):
        houses = spaced_houses(3)
        ns, calls = template_fixture(houses)
        for house in houses: order(ns, house, advance=False)
        self.assertEqual(2, len(calls["queries"]))
        self.assertEqual(2, len(ns["s_TemplateBindings"]))
        order(ns, houses[2])  # the next tick resumes
        self.assertEqual(3, len(calls["queries"]))
        self.assertEqual(3, len(ns["s_TemplateBindings"]))
        order(ns, houses[0], advance=False)
        order(ns, houses[1], advance=False)
        order(ns, houses[2], advance=False)
        self.assertEqual(4, len(calls["queries"]))  # that tick had one query left, never more than 2 in total
        ns2, calls2 = template_fixture(houses)
        ns2["ConfigureBinding"](30, 1)
        for house in houses: order(ns2, house, advance=False)
        self.assertEqual(1, len(calls2["queries"]))

    def test_query_budget_follows_begin_tick_not_the_elapsed_clock(self):
        houses = spaced_houses(3)
        ns, calls = template_fixture(houses)  # GetTickTime differs on every call
        for house in houses: order(ns, house, advance=False)
        self.assertEqual(2, len(calls["queries"]))
        self.assertEqual(2, len(ns["s_TemplateBindings"]))
        ns["BeginTick"]()
        order(ns, houses[2], advance=False)
        self.assertEqual(3, len(calls["queries"]))
        self.assertNotIn("GetTickTime", re.sub(r"//[^\n]*", "", PATH.read_text().split("static bool ConfigureBinding(")[1].split("static void BuildOrder(")[0]))

    def test_cap_still_holds_when_begin_tick_is_never_called(self):
        houses = spaced_houses(4)
        ns, calls = template_fixture(houses)
        for house in houses: order(ns, house, advance=False)
        for house in houses: order(ns, house, advance=False)
        self.assertEqual(2, len(calls["queries"]))  # never reset: cached houses only afterwards
        self.assertEqual(2, len(ns["s_TemplateBindings"]))
        self.assertEqual([houses[0].position], order(ns, houses[0], advance=False))  # a cached house still orders

    def test_conflict_is_decided_before_the_query_quota(self):
        houses = spaced_houses(2)
        ns, calls = template_fixture(houses, legacy_houses=houses)
        ns["EnsureProductionLoaded"]()
        ns["ConfigureBinding"](30, 1)
        ns["BeginTick"]()
        self.assertEqual([houses[1].position], order(ns, houses[1], advance=False))  # uses the only query
        self.assertEqual([], order(ns, houses[0], advance=False))  # quota gone, yet no legacy anchors
        self.assertEqual("rooms_conflict", ns["TemplateReason"]())
        self.assertEqual(1, len([line for line in calls["logs"] if "rooms_conflict" in line]))
        self.assertEqual([], ns["s_ProductionBindings"])
        self.assertEqual([houses[1]], [b.HouseObject for b in ns["s_TemplateBindings"]])
        ns["BeginTick"]()
        self.assertEqual([], order(ns, houses[0], advance=False))  # still neither source next tick

    def test_conflict_evicts_a_template_cached_before_the_legacy_file_loaded(self):
        houses = spaced_houses(1)
        ns, calls = template_fixture(houses, legacy_houses=houses)
        self.assertEqual([houses[0].position], order(ns, houses[0], advance=False))  # cached pre-load
        self.assertEqual(1, len(ns["s_TemplateBindings"]))
        ns["EnsureProductionLoaded"]()
        ns["ConfigureBinding"](30, 1)
        ns["BeginTick"]()
        order(ns, Vec((900, 10, 900)), advance=False)  # an unrelated clue spends the quota
        self.assertEqual([], order(ns, houses[0], advance=False))
        self.assertEqual([], ns["s_TemplateBindings"])
        self.assertEqual(0, ns["TemplateAnchorTotal"]())
        self.assertEqual([], ns["s_ProductionBindings"])
        self.assertEqual("rooms_conflict", ns["TemplateReason"]())

    def test_ordering_skips_a_conflicted_house_even_if_a_binding_survives(self):
        houses = spaced_houses(1)
        ns, calls = template_fixture(houses)
        order(ns, houses[0], advance=False)
        ns["s_ConflictHouses"].append(houses[0])  # a belt-and-braces check on the merge itself
        self.assertEqual(1, len(ns["s_TemplateBindings"]))
        self.assertEqual([], order(ns, houses[0], advance=False))

    def test_template_dto_names_match_the_real_reader(self):
        reader = Path("/code/hc-worktrees/bld-T3/mods/HollowCountry/scripts/4_World/Interiors")
        if not reader.is_dir(): self.skipTest("T3 worktree is not present")
        text = (reader / "HCInteriorTemplatesData.c").read_text() + (reader / "HCInteriorTemplates.c").read_text()
        for name in ("static bool Loaded()", "static HCInteriorTemplateClassRow ClassRow(string cls)",
                     "static HCInteriorTemplate Template(string cls)", "static bool VectorValid(array<float> value, float limit)",
                     "static bool BoxValid(array<float> minimum, array<float> maximum)",
                     "static bool Inside(array<float> point, array<float> minimum, array<float> maximum)",
                     "static vector AsVector(array<float> value)", "ref array<float> Anchor", "ref array<float> Min",
                     "ref array<ref HCInteriorTemplateEvidence> Evidence", "string RunId;", "string Sha256;"):
            self.assertIn(name, text)

    def test_conflict_needs_no_query_at_all(self):
        houses = spaced_houses(1)
        ns, calls = template_fixture(houses, legacy_houses=houses)
        ns["EnsureProductionLoaded"]()
        queries = len(calls["queries"])
        ns["ConfigureBinding"](30, 1)
        ns["BeginTick"]()
        order(ns, Vec((900, 10, 900)), advance=False)  # an unrelated clue spends the quota
        self.assertEqual([], order(ns, houses[0], advance=False))
        self.assertEqual([], ns["s_ProductionBindings"])
        self.assertEqual("rooms_conflict", ns["TemplateReason"]())

    def test_lru_keeps_at_most_64_houses_and_releases_the_least_recently_used(self):
        houses = spaced_houses(65)
        ns, _ = template_fixture(houses)
        for house in houses[:64]: order(ns, house)
        self.assertEqual(64, len(ns["s_TemplateBindings"]))
        order(ns, houses[0])  # touch the oldest binding
        order(ns, houses[64])  # 65th house evicts the least recently used: house 1, not house 0
        bound = [binding.HouseObject for binding in ns["s_TemplateBindings"]]
        self.assertEqual(64, len(bound))
        self.assertIn(houses[0], bound)
        self.assertIn(houses[64], bound)
        self.assertNotIn(houses[1], bound)

    def test_anchor_cap_of_256_evicts_before_the_house_cap(self):
        houses = spaced_houses(17)
        ns, _ = template_fixture(houses, templates={"Synthetic_House_1": synthetic_template(rooms=16)})
        for house in houses[:16]: order(ns, house)
        total = lambda: sum(len(b.Survey.Anchors) for b in ns["s_TemplateBindings"])
        self.assertEqual((16, 256), (len(ns["s_TemplateBindings"]), total()))
        order(ns, houses[16])
        self.assertEqual((16, 256), (len(ns["s_TemplateBindings"]), total()))
        bound = [binding.HouseObject for binding in ns["s_TemplateBindings"]]
        self.assertNotIn(houses[0], bound)
        self.assertIn(houses[16], bound)

    def test_uncovered_or_unknown_classes_are_ignored(self):
        houses = spaced_houses(1)
        for rows in ({"Synthetic_House_1": "unmeasured"}, {"Synthetic_House_1": "not_enterable"}, {}):
            with self.subTest(rows=rows):
                ns, calls = template_fixture(houses, rows=rows)
                self.assertEqual([], order(ns, houses[0]))
                self.assertEqual([], ns["s_TemplateBindings"])
                self.assertEqual([], calls["template_calls"])
                self.assertEqual(["Synthetic_House_1"], calls["row_calls"][:1])

    def test_non_house_candidates_and_dense_results_are_bounded(self):
        houses = [object() for _ in range(1100)] + spaced_houses(1)
        ns, calls = template_fixture(houses)
        self.assertEqual([], order(ns, Vec((100, 10, 100))))
        self.assertEqual([], ns["s_TemplateBindings"])
        self.assertEqual("rooms_bind_dense", ns["TemplateReason"]())
        self.assertLessEqual(len(calls["row_calls"]), 1024)

    def test_legacy_claim_conflicts_refuse_the_house_for_both_sources(self):
        houses = spaced_houses(2)
        ns, calls = template_fixture(houses, legacy_houses=houses)
        ns["EnsureProductionLoaded"]()
        self.assertEqual(1, len(ns["s_ProductionBindings"]))  # the legacy file admitted house 0
        self.assertEqual([], order(ns, houses[0]))  # claimed by both: use neither
        self.assertEqual("rooms_conflict", ns["TemplateReason"]())
        self.assertEqual([], ns["s_TemplateBindings"])
        self.assertEqual([], ns["s_ProductionBindings"])
        for _ in range(3): order(ns, houses[0])
        self.assertEqual(1, len([line for line in calls["logs"] if "rooms_conflict" in line]))
        self.assertEqual([], ns["s_TemplateBindings"])
        self.assertEqual([houses[1].position], order(ns, houses[1]))  # an unclaimed house still binds

    def test_legacy_alone_keeps_working_when_the_pack_is_not_loaded(self):
        houses = spaced_houses(1)
        ns, calls = template_fixture(houses, loaded=False, legacy_houses=houses)
        self.assertEqual([], order(ns, houses[0]))  # not admitted yet: no first-tick load
        ns["EnsureProductionLoaded"]()
        queries = len(calls["queries"])
        self.assertEqual([houses[0].position], order(ns, houses[0]))
        self.assertEqual(queries, len(calls["queries"]))  # no template query, no template read
        self.assertEqual([], calls["row_calls"] + calls["template_calls"])
        self.assertEqual([], ns["s_TemplateBindings"])
        self.assertFalse([line for line in calls["logs"] if "templates" in line])

    def test_templates_without_the_legacy_file_work_and_legacy_still_orders_beside_them(self):
        houses = spaced_houses(2)
        ns, _ = template_fixture(houses, legacy_houses=houses[:1])
        ns["EnsureProductionLoaded"]()
        ns["state"]["rows"] = {"Synthetic_Shed_1": "covered"}  # legacy house is not a template class
        self.assertEqual([houses[0].position], order(ns, houses[0]))
        self.assertEqual([], ns["s_TemplateBindings"])
        self.assertEqual("rooms_admitted_measurements_path_audio_doors_pending", ns["ProductionReason"]())

    def test_house_pose_must_be_yaw_only_and_unambiguous(self):
        tilted = [House(position=(100, 10, 100), orientation=(30, 5, 0))]
        ns, _ = template_fixture(tilted)
        self.assertEqual([], order(ns, tilted[0]))
        self.assertEqual("tilted", ns["TemplateReason"]())
        self.assertEqual([], ns["s_TemplateBindings"])
        yawed = [House(position=(100, 10, 100), orientation=(30, 0, 0))]
        ns, _ = template_fixture(yawed)
        self.assertEqual([yawed[0].position], order(ns, yawed[0]))
        twins = [House(position=(100, 10, 100)), House(position=(100.5, 10, 100))]
        ns, _ = template_fixture(twins)
        self.assertEqual([], order(ns, twins[0]))
        self.assertEqual("rooms_template_ambiguous", ns["TemplateReason"]())
        self.assertEqual([], ns["s_TemplateBindings"])

    def test_malformed_templates_are_refused_without_a_binding(self):
        def mutate(change):
            layout = synthetic_template(rooms=2)
            change(layout)
            return {"Synthetic_House_1": layout}
        cases = {
            "rooms_template_geometry": (
                lambda t: setattr(t.Rooms[0], "Anchor", Array((5, 0, 0))),
                lambda t: setattr(t.Rooms[1], "Anchor", Array((0, 0, 0))),
                lambda t: setattr(t.Rooms[1], "Id", 1),
                lambda t: setattr(t.Rooms[0], "Max", Array((99, 1, .8))),
                lambda t: setattr(t.Box, "Max", Array((513, 16, 32))),
                lambda t: setattr(t.Rooms[0], "Anchor", Array((math.nan, 0, 0))),
                lambda t: setattr(t, "Rooms", Array()),
                lambda t: setattr(t, "BuildingClass", "Other_Class")),
            "rooms_template_evidence": (
                lambda t: setattr(t.Evidence[0], "Kind", "synthetic"),
                lambda t: setattr(t.Evidence[0], "RunId", ""),
                lambda t: setattr(t, "Evidence", Array())),
        }
        for reason, changes in cases.items():
            for change in changes:
                ns, _ = template_fixture(spaced_houses(1), templates=mutate(change))
                self.assertEqual([], order(ns, Vec((100, 10, 100))), reason)
                self.assertEqual(reason, ns["TemplateReason"]())
                self.assertEqual([], ns["s_TemplateBindings"])
        seventeen = {"Synthetic_House_1": synthetic_template(rooms=17, box=64)}
        ns, _ = template_fixture(spaced_houses(1), templates=seventeen)
        self.assertEqual([], order(ns, Vec((100, 10, 100))))
        self.assertEqual("rooms_template_geometry", ns["TemplateReason"]())
        ns, _ = template_fixture(spaced_houses(1), templates={})
        self.assertEqual([], order(ns, Vec((100, 10, 100))))
        self.assertEqual("rooms_template_missing", ns["TemplateReason"]())

    def test_refusals_are_logged_once_per_reason_and_class(self):
        houses = [House(orientation=(0, 5, 0))]
        ns, calls = template_fixture(houses)
        for _ in range(5): order(ns, houses[0])
        self.assertEqual(1, len([line for line in calls["logs"] if "tilted" in line]))

    def test_success_log_names_provisional_pending_state_and_class_counts_once(self):
        houses = spaced_houses(2)
        ns, calls = template_fixture(houses)
        for _ in range(3): order(ns, houses[0])
        logs = [line for line in calls["logs"] if "rooms_templates_provisional_path_audio_doors_pending" in line]
        self.assertEqual(1, len(logs))
        self.assertIn("classes=1/2", logs[0])
        order(ns, houses[1])
        self.assertEqual(1, len([line for line in calls["logs"] if "provisional" in line]))

    def test_late_load_and_clear_reset_template_state_and_settings(self):
        houses = spaced_houses(1)
        ns, calls = template_fixture(houses, loaded=False)
        self.assertEqual([], order(ns, houses[0]))
        self.assertEqual([], calls["queries"])
        ns["state"]["loaded"] = True  # the reader finished after the Infected module started
        self.assertEqual([houses[0].position], order(ns, houses[0]))
        ns["ConfigureBinding"](10, 1)
        ns["Clear"]()
        self.assertEqual([], ns["s_TemplateBindings"])
        self.assertEqual([], ns["s_ConflictHouses"])
        self.assertFalse(ns["s_TemplateLogged"])
        self.assertEqual((30, 2), (ns["s_BindRadius"], ns["s_BindQueryCap"]))

    def test_no_fabricated_offsets_spawns_or_blocked_doors_in_the_template_path(self):
        source = re.sub(r"//[^\n]*", "", PATH.read_text())
        start = source.index("static bool ConfigureBinding(")
        end = source.index("static void BuildOrder(")
        body = source[start:end]
        for forbidden in ("SetPosition(", "CreateObject", "SpawnEntity", "SetOrientation(", "Door", "GetPlayers("):
            self.assertNotIn(forbidden, body)
        self.assertEqual(1, body.count("GetObjectsAtPosition3D("))
        self.assertNotRegex(body, r"\?[^\n]*:")  # no ternary operator in Enforce script


if __name__ == "__main__": unittest.main()


class ProductionCatalogModuleWiringTests(unittest.TestCase):
    """Review P2-1: module start must load the catalog once, after validated config."""

    def test_module_start_loads_production_catalog_after_validated_limits(self):
        module = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts/4_World/Infected/HCInfectedModule.c"
        text = re.sub(r"//[^\n]*", "", module.read_text())
        start = text.index("override void OnStart(HCSettings settings)")
        body = text[start:text.index("HCInfectedAdmission.Evaluate(m_Config)", start)]
        self.assertEqual(1, text.count("HCInfectedRoomCatalog.EnsureProductionLoaded();"))
        self.assertIn("HCInfectedRoomCatalog.EnsureProductionLoaded();", body)
        self.assertLess(body.index('Quarantine("invalid limits")'),
                        body.index("HCInfectedRoomCatalog.EnsureProductionLoaded();"))


class TemplateBindingModuleWiringTests(unittest.TestCase):
    """The module configures template binding from settings and resets its query budget each tick."""

    def module_text(self):
        module = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts/4_World/Infected/HCInfectedModule.c"
        return re.sub(r"//[^\n]*", "", module.read_text())

    def test_start_configures_binding_before_loading_production_rooms(self):
        text = self.module_text()
        start = text.index("override void OnStart(HCSettings settings)")
        body = text[start:text.index("HCInfectedAdmission.Evaluate(m_Config)", start)]
        call = "HCInfectedRoomCatalog.ConfigureBinding(settings.InfectedBindRadius, settings.MaxBindQueriesPerTick);"
        self.assertEqual(1, text.count("HCInfectedRoomCatalog.ConfigureBinding("))
        self.assertIn(call, body)
        self.assertLess(body.index(call), body.index("HCInfectedRoomCatalog.EnsureProductionLoaded();"))

    def test_each_healthy_tick_begins_a_new_bind_budget(self):
        text = self.module_text()
        start = text.index("override void OnTick(float deltaTime)")
        body = text[start:text.index("m_RoutesRemaining = 1;", start)]
        self.assertEqual(1, text.count("HCInfectedRoomCatalog.BeginTick();"))
        self.assertIn("HCInfectedRoomCatalog.BeginTick();", body)
        self.assertLess(body.index("if (!m_Healthy"), body.index("HCInfectedRoomCatalog.BeginTick();"))
