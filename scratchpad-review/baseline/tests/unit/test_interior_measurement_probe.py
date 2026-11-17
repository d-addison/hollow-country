"""Synthetic stock, declarations and receipts; no DayZ or geometric fit proof."""
import copy
import hashlib
import importlib
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

STOCK = b"""void main() {
    Hive ce = CreateHive();
    if (ce) ce.InitOffline();
    int preserved = 7;
}
class CustomMission: MissionServer { void Preserved() {} }
Mission CreateCustomMission(string path) { return new CustomMission(); }
"""
POSITIONS = b'<map><group name="Land_House_1W01" pos="100 10 200" rpy="0 0 90" a="0"/></map>'
PROTOTYPES = b'''<prototype><group name="Land_House_1W01"><usage name="Village"/>
<container name="shelves"><category name="food"/><tag name="shelves"/>
<point pos="1 0 2" range="0.2" height="0.5" flags="0"/>
</container></group></prototype>'''


def sha(value):
    return hashlib.sha256(value).hexdigest()


def request():
    return dict(schema=1, world_name="chernarusplus", engine_version="1.30.164289.70",
        stock_sha256={"init.c": sha(STOCK), "mapgrouppos.xml": sha(POSITIONS),
                      "mapgroupproto.xml": sha(PROTOTYPES)},
        areas=[dict(id="area-a", reviewed=True, center=[100, 10, 200], radius=5,
            expected=[dict(id="house-a", stock_row=0,
                building_class="Land_House_1W01", orientation=[90, 0, 0])])])


def receipt(probe, files):
    manifest = json.loads(files[probe.MARKER])
    refs = json.loads(files[probe.REFERENCE])["houses"]
    def sample(index, point):
        return dict(id=index, world_position=[100 + point[0], 10 + point[1], 200 + point[2]],
                    local_return=list(point), error_squared=0)
    areas = []
    for index, area in enumerate(manifest["request"]["areas"]):
        houses = []
        for ref in (r for r in refs if r["area_id"] == area["id"]):
            houses.append(dict(id=ref["id"], status="measured", matches=1,
                building_class=ref["building_class"], position=ref["position"],
                orientation=ref["orientation"], model_name="synthetic_house",
                collision_success=1, collision_min=[-5, -3, -5], collision_max=[5, 3, 5],
                clipping_min=[-5, -3, -5], clipping_max=[5, 3, 5], clipping_radius=8,
                transforms=[sample(i, p) for i, p in enumerate(probe.PROBES)],
                ce_points=[sample(i, p["local_position"]) for i, p in enumerate(ref["ce_points"])]))
        areas.append(dict(id=area["id"], query_object_count=len(houses),
            house_count=len(houses), overflow=0, frame_ordinal=index+1, houses=houses))
    return dict(schema=1, kind=probe.KIND, run_id=manifest["run_id"],
        world_name="chernarusplus", engine_version="1.30.164289.70",
        request_sha256=manifest["request_sha256"], reference_sha256=sha(files[probe.REFERENCE]),
        stock_init_sha256=manifest["request"]["stock_sha256"]["init.c"],
        stock_positions_sha256=manifest["request"]["stock_sha256"]["mapgrouppos.xml"],
        stock_prototypes_sha256=manifest["request"]["stock_sha256"]["mapgroupproto.xml"],
        ce_point_provenance="stock-xml-reference-only", bbox_basis="unqualified-native-return",
        missing_survey_data=list(probe.MISSING), server_context=1,
        complete=1, failed=0, reason="", phase="complete", callbacks_detached=1,
        entities_created=0, gameplay_acceptance=0, survey_complete=0,
        engine_eligibility_verified=0, frame_entries=len(areas)+1,
        frame_exits=len(areas)+1, queue_entries=len(areas), queue_exits=len(areas),
        elapsed_seconds=1, areas=areas)


class InteriorMeasurementProbeTests(unittest.TestCase):
    def setUp(self):
        self.p = importlib.import_module("tools.setup.interior_measurement_probe")

    def generate(self, req=None, positions=POSITIONS, prototypes=PROTOTYPES):
        interfaces = {name: "\n".join(tokens).encode()
                      for name, tokens in self.p.INTERFACES.items()}
        return self.p.generate_probe(STOCK, positions, prototypes,
            request() if req is None else req, interfaces, run_id="a"*32)

    def validate(self, row=None, files=None, **kwargs):
        files = self.generate() if files is None else files
        return self.p.validate_receipt(json.dumps(receipt(self.p, files) if row is None else row).encode(),
            files, **dict(dict(outer_timed_out=False, outer_elapsed_seconds=80), **kwargs))

    def test_generator_is_fixed_ce_disabled_and_schedules_real_callbacks(self):
        files = self.generate()
        self.assertEqual({"init.c", self.p.MARKER, self.p.REFERENCE}, set(files))
        text = files["init.c"].decode()
        self.assertIn("Hive ce = CreateHive();", text)
        self.assertNotIn("ce.InitOffline();", text)
        self.assertIn("int preserved = 7;", text)
        self.assertIn("CallLater(Tick, 100, true)", text)
        self.assertIn("Insert(Frame)", text)
        self.assertIn("Remove(Tick)", text)
        self.assertIn("Remove(Frame)", text)
        for forbidden in ("GetCEApi(", "CreateObjectEx(", "CreatePlayer(", "ObjectDelete(", "SetPosition(", "OpenDoor("):
            self.assertNotIn(forbidden, text)
        manifest = json.loads(files[self.p.MARKER])
        self.assertEqual(request()["stock_sha256"], manifest["request"]["stock_sha256"])
        self.assertFalse(manifest["gameplay_acceptance"])

    def test_success_only_admits_measurement_acquisition(self):
        result = self.validate()
        self.assertEqual("measurement-acquisition-complete", result["status"])
        self.assertFalse(result["gameplay_acceptance"])
        self.assertFalse(result["survey_complete"])
        self.assertEqual(1, result["house_count"])
        self.assertEqual(1, result["ce_reference_point_count"])

    def test_stock_prototype_defaults_are_pinned_without_becoming_eligibility(self):
        defaults = b'<defaults><default name="group" lootmax="6"/><default name="clusterMatrix" de="TrajectoryApple" width="12" height="12"/></defaults>'
        prototypes = PROTOTYPES.replace(b'<prototype>', b'<prototype>'+defaults)
        req = request()
        req['stock_sha256']['mapgroupproto.xml'] = sha(prototypes)
        files = self.generate(req, prototypes=prototypes)
        result = self.validate(files=files)
        self.assertEqual(1, result['ce_reference_point_count'])
        self.assertFalse(result['engine_eligibility_verified'])
        self.assertEqual(sha(prototypes), result['receipt']['stock_prototypes_sha256'])

    def test_duplicate_unknown_or_unbounded_defaults_fail_before_emission(self):
        cases = (b'<defaults/><defaults/>', b'<unknown/>',
                 b'<defaults><default><nested/></default></defaults>',
                 b'<defaults>'+b'<default name="group"/>'*65+b'</defaults>')
        for value in cases:
            with self.subTest(value=value[:80]), self.assertRaises(ValueError):
                prototypes = PROTOTYPES.replace(b'<prototype>', b'<prototype>'+value)
                req = request()
                req['stock_sha256']['mapgroupproto.xml'] = sha(prototypes)
                self.generate(req, prototypes=prototypes)

    def test_timeout_and_budget_never_admit_even_a_complete_receipt(self):
        for kwargs in (dict(outer_timed_out=True), dict(outer_timed_out=None),
                       dict(outer_elapsed_seconds=181), dict(outer_elapsed_seconds=float("nan"))):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.validate(**kwargs)

    def test_request_requires_exact_pins_explicit_review_and_bounded_areas(self):
        variants = []
        for key, value in (("world_name", "enoch"), ("engine_version", "1.30.164289.700"),
                           ("areas", []), ("schema", True)):
            value_request = request(); value_request[key] = value; variants.append(value_request)
        value_request = request(); value_request["stock_sha256"]["mapgrouppos.xml"] = "0"*64; variants.append(value_request)
        value_request = request(); value_request["areas"][0]["reviewed"] = False; variants.append(value_request)
        value_request = request(); value_request["areas"][0]["radius"] = 25.01; variants.append(value_request)
        value_request = request(); value_request["areas"] *= 5; variants.append(value_request)
        value_request = request(); value_request["areas"][0]["expected"] *= 17; variants.append(value_request)
        value_request = request(); value_request["areas"][0]["center"] = [999, 10, 200]; variants.append(value_request)
        value_request = request(); value_request["areas"][0]["unexpected"] = 1; variants.append(value_request)
        for value_request in variants:
            with self.subTest(request=value_request), self.assertRaises(ValueError):
                self.generate(value_request)

    def test_stock_row_identity_class_and_orientation_are_not_guessed(self):
        for key, value in (("stock_row", 1), ("stock_row", True),
                           ("building_class", "Land_Other"),
                           ("orientation", [90, float("nan"), 0])):
            req = request(); req["areas"][0]["expected"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.generate(req)
        refs = json.loads(self.generate()[self.p.REFERENCE])
        self.assertEqual([100, 10, 200], refs["houses"][0]["position"])
        self.assertEqual([90, 0, 0], refs["houses"][0]["orientation"])

    def test_installed_interface_mismatch_and_non_stock_mission_rejected(self):
        with self.assertRaises(ValueError):
            self.p.generate_probe(STOCK, POSITIONS, PROTOTYPES, request(), {}, run_id="a"*32)
        changed = STOCK.replace(b"ce.InitOffline();", b"ce.InitOffline(); ce.InitOffline();")
        req = request(); req["stock_sha256"]["init.c"] = sha(changed)
        interfaces = {n: "\n".join(v).encode() for n, v in self.p.INTERFACES.items()}
        with self.assertRaises(ValueError):
            self.p.generate_probe(changed, POSITIONS, PROTOTYPES, req, interfaces, run_id="a"*32)

    def test_xml_declarations_and_point_budget_fail_before_emission(self):
        for blob in (b'<!DOCTYPE map [<!ENTITY x "x">]><map/>',
                     '<map/>'.encode("utf-16")):
            req = request(); req["stock_sha256"]["mapgrouppos.xml"] = sha(blob)
            with self.assertRaises(ValueError):
                self.generate(req, positions=blob)
        points = b"".join(f'<point pos="{i} 0 0"/>'.encode() for i in range(129))
        proto = b'<prototype><group name="Land_House_1W01"><container name="x">' + points + b'</container></group></prototype>'
        req = request(); req["stock_sha256"]["mapgroupproto.xml"] = sha(proto)
        with self.assertRaises(ValueError):
            self.generate(req, prototypes=proto)

    def test_nonce_provenance_and_scope_flags_are_strict(self):
        files = self.generate(); original = receipt(self.p, files)
        for key, value in (("run_id", "b"*32), ("engine_version", "1.30.164289.700"),
            ("stock_positions_sha256", "0"*64), ("ce_point_provenance", "engine-eligible"),
            ("bbox_basis", "room-clearance"), ("gameplay_acceptance", 1),
            ("survey_complete", 1), ("engine_eligibility_verified", 1), ("complete", 1.0),
            ("entities_created", True), ("reason", "failed"), ("phase", "query")):
            row = copy.deepcopy(original); row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(row, files)
        row = copy.deepcopy(original); row["missing_survey_data"].pop()
        with self.assertRaises(ValueError): self.validate(row, files)

    def test_every_requested_area_house_and_reference_point_is_required_once(self):
        files = self.generate()
        for target in ("areas", "houses", "ce_points", "transforms"):
            row = receipt(self.p, files)
            value = row["areas"]
            if target != "areas": value = value[0]["houses"]
            if target in ("ce_points", "transforms"): value = value[0][target]
            value.pop()
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.validate(row, files)
        row = receipt(self.p, files); row["areas"][0]["houses"] *= 2
        with self.assertRaises(ValueError): self.validate(row, files)

    def test_overflow_ambiguity_pose_failure_and_bad_native_geometry_rejected(self):
        files = self.generate()
        for change in ("overflow", "matches", "position", "orientation", "collision",
                       "inverted", "radius", "nonfinite", "roundtrip"):
            row = receipt(self.p, files); area = row["areas"][0]; house = area["houses"][0]
            if change == "overflow": area["query_object_count"] = 257
            if change == "matches": house["matches"] = 2
            if change == "position": house["position"][0] += .11
            if change == "orientation": house["orientation"][0] += .11
            if change == "collision": house["collision_success"] = 0
            if change == "inverted": house["collision_min"][0] = 9
            if change == "radius": house["clipping_radius"] = -1
            if change == "nonfinite": house["clipping_max"][1] = float("inf")
            if change == "roundtrip": house["transforms"][0]["local_return"][0] = .01
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(row, files)

    def test_callback_denominators_and_cleanup_are_observations_not_defaults(self):
        files = self.generate()
        for key, value in (("queue_entries", 0), ("frame_entries", 0),
                           ("queue_exits", 0), ("callbacks_detached", 0)):
            row = receipt(self.p, files); row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(row, files)
        row = receipt(self.p, files); row["areas"][0]["frame_ordinal"] = 0
        with self.assertRaises(ValueError): self.validate(row, files)

    def test_receipt_and_bundle_bytes_are_bounded_and_hash_bound(self):
        files = self.generate()
        with self.assertRaises(ValueError):
            self.p.validate_receipt(b"x"*(self.p.MAX_RECEIPT_BYTES+1), files,
                outer_timed_out=False, outer_elapsed_seconds=80)
        changed = dict(files); changed["init.c"] += b" "
        with self.assertRaises(ValueError): self.validate(files=changed)
        changed = dict(files); changed[self.p.REFERENCE] += b" "
        with self.assertRaises(ValueError): self.validate(files=changed)
        with self.assertRaises(ValueError):
            self.p.validate_receipt(b'{"schema":1,"schema":1}', files,
                outer_timed_out=False, outer_elapsed_seconds=80)


    def test_bundle_metadata_cannot_weaken_request_or_reference_denominators(self):
        files = self.generate()
        for case in ("schema", "areas", "reference-schema", "reference-id",
                     "point-number", "interfaces", "watchdog", "nonce"):
            changed = dict(files)
            marker = json.loads(changed[self.p.MARKER])
            refs = json.loads(changed[self.p.REFERENCE])
            if case == "schema": marker["schema"] = True
            if case == "areas": marker["request"]["areas"][0]["reviewed"] = False
            if case == "reference-schema": refs["schema"] = True
            if case == "reference-id": refs["houses"][0]["id"] = "different-house"
            if case == "point-number": refs["houses"][0]["ce_points"][0]["point_index"] = True
            if case == "interfaces": marker["interfaces"] = {}
            if case == "watchdog": marker["native_watchdog_seconds"] = 3600
            if case == "nonce": marker["run_id"] = "not-a-run-id"
            changed[self.p.REFERENCE] = self.p._encode(refs)
            marker["reference_sha256"] = sha(changed[self.p.REFERENCE])
            marker["request_sha256"] = sha(self.p._encode(marker["request"]))
            changed[self.p.MARKER] = self.p._encode(marker)
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.validate(receipt(self.p, changed), changed)

    def test_minimal_main_and_braced_hive_pair_keep_main_balanced(self):
        interfaces = {n: "\n".join(v).encode() for n, v in self.p.INTERFACES.items()}
        for pair in (b"if (ce) ce.InitOffline();", b"if (ce) { ce.InitOffline(); }"):
            stock = STOCK.replace(b"if (ce) ce.InitOffline();\n    int preserved = 7;", pair)
            req = request(); req["stock_sha256"]["init.c"] = sha(stock)
            emitted = self.p.generate_probe(stock, POSITIONS, PROTOTYPES,
                req, interfaces, run_id="a"*32)["init.c"].decode()
            self.assertEqual(emitted.count("{"), emitted.count("}"))
            self.assertIn("HCIMeasure.Begin();", emitted)


    def test_maximum_reviewed_inputs_generate_without_unmeasured_admission(self):
        positions = []
        req = request(); req["areas"] = []
        for a in range(4):
            expected = []
            for h in range(4):
                index = a*4+h
                positions.append(f'<group name="Land_House_1W01" pos="{100+a*100+h} 10 200"/>')
                expected.append(dict(id=f"house-{index}", stock_row=index,
                    building_class="Land_House_1W01", orientation=[90,0,0]))
            req["areas"].append(dict(id=f"area-{a}", reviewed=True,
                center=[100+a*100,10,200], radius=25, expected=expected))
        blob = ("<map>"+"".join(positions)+"</map>").encode()
        req["stock_sha256"]["mapgrouppos.xml"] = sha(blob)
        files = self.generate(req, positions=blob)
        row = receipt(self.p, files)
        result = self.validate(row, files)
        self.assertEqual((4,16,16),(result["area_count"], result["house_count"],
                                   result["ce_reference_point_count"]))
        row["areas"][1]["frame_ordinal"] = row["areas"][0]["frame_ordinal"]
        with self.assertRaises(ValueError): self.validate(row, files)

    def test_callback_body_persists_partial_before_native_query_and_checks_after(self):
        text = self.generate()["init.c"].decode()
        tick = text[text.index("static void Tick()"):text.index("static void Interrupt()")]
        self.assertLess(tick.index("Save();"), tick.index("Acquire(area, result);"))
        self.assertLess(tick.index("Acquire(area, result);"), tick.index("if (!Check()) return;", tick.index("Acquire(area, result);")))
        self.assertIn("Count(Frame) == 0", text)
        self.assertNotRegex(text, r"@[A-Z]+@")
        self.assertIn('if (objects.Count() > 256)', text)
        self.assertIn('if (row.matches != 1)', text)

    def test_cli_rejects_unexpected_or_link_nodes_before_reading_receipt(self):
        for bad in ("unexpected", "link"):
            entries = [SimpleNamespace(name=name, is_file=lambda **kw: True)
                       for name in ("init.c", self.p.MARKER, self.p.REFERENCE)]
            if bad == "unexpected":
                entries.append(SimpleNamespace(name="extra", is_file=lambda **kw: True))
            else:
                entries[0].is_file = lambda **kw: False
            manager = MagicMock()
            manager.__enter__.return_value = iter(entries)
            with patch.object(self.p, "_safe", side_effect=Path), \
                 patch.object(self.p.os, "scandir", return_value=manager), \
                 patch.object(self.p, "_read") as read, redirect_stderr(StringIO()):
                with self.subTest(bad=bad), self.assertRaises(SystemExit) as raised:
                    self.p.main(["validate","--bundle-dir","/synthetic/bundle",
                        "--receipt","/synthetic/profile/receipt.json",
                        "--outer-outcome","completed","--outer-elapsed-seconds","80"])
                self.assertEqual(1, raised.exception.code)
                read.assert_not_called()

    def test_cli_only_reads_exact_bounded_bundle_and_receipt(self):
        files = self.generate()
        row = json.dumps(receipt(self.p, files)).encode()
        entries = [SimpleNamespace(name=name, is_file=lambda **kw: True)
                   for name in files]
        manager = MagicMock(); manager.__enter__.return_value = iter(entries)
        limits = []
        def read(path, limit):
            limits.append(limit)
            return row if path.name == "receipt.json" else files[path.name]
        output = StringIO()
        with patch.object(self.p, "_safe", side_effect=Path), \
             patch.object(self.p.os, "scandir", return_value=manager), \
             patch.object(self.p, "_read", side_effect=read), redirect_stdout(output):
            self.p.main(["validate","--bundle-dir","/synthetic/bundle",
                "--receipt","/synthetic/profile/receipt.json",
                "--outer-outcome","completed","--outer-elapsed-seconds","80"])
        self.assertEqual([128*1024, self.p.MAX_MANIFEST_BYTES,
                          self.p.MAX_REFERENCE_BYTES, self.p.MAX_RECEIPT_BYTES], limits)
        self.assertFalse(json.loads(output.getvalue())["gameplay_acceptance"])


if __name__ == "__main__":
    unittest.main()
