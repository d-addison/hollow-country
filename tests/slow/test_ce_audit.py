"""T0 tests using invented CE names/positions, never engine acceptance tests."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/ce"
VALID = FIXTURES / "synthetic_valid"
CATALOG = FIXTURES / "synthetic_known_types.txt"


class CEAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic_run_")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.mission = self.workspace / "mission"
        shutil.copytree(VALID, self.mission)
        # Import in setUp so every test participates in the initial red run.
        self.module = importlib.import_module("tools.audit.ce_audit")

    def write(self, relative, text):
        path = self.mission / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def audit(self, **kwargs):
        return self.module.audit_mission(self.mission, **kwargs)

    def codes(self, report):
        return {item["code"] for item in report["diagnostics"]}

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "tools.audit.ce_audit", "--mission", str(self.mission), *map(str, args)],
            cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            text=True, capture_output=True, timeout=15,
        )

    def test_valid_raw_coverage_and_unplaced_groups(self):
        report = self.audit()
        self.assertTrue(report["valid"])
        self.assertEqual(report["types"]["unique_names"], 2)
        self.assertEqual(report["coverage"]["placement_count"], 3)
        self.assertEqual(report["coverage"]["raw_point_count"], 4)
        self.assertEqual(report["coverage"]["placed_raw_point_count"], 6)
        rows = {row["name"]: row for row in report["coverage"]["groups"]}
        self.assertEqual(rows["SyntheticHouse"]["placement_count"], 2)
        self.assertEqual(rows["SyntheticHouse"]["container_count"], 2)
        self.assertEqual(rows["SyntheticHouse"]["raw_point_count"], 3)
        self.assertEqual(rows["SyntheticUnplaced"]["placement_count"], 0)
        self.assertEqual(rows["SyntheticEmpty"]["raw_point_count"], 0)
        self.assertIsNone(report["coverage"]["engine_eligible_loot_points"])
        self.assertFalse(report["coverage"]["building_classes_verified"])
        self.assertIn("zero_raw_points", self.codes(report))
        self.assertIn("offline", " ".join(report["limitations"]).lower())

    def test_deterministic_json_and_relative_provenance(self):
        first, second = self.cli(), self.cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        report = json.loads(first.stdout)
        self.assertNotIn(str(self.workspace), first.stdout)
        self.assertNotIn(str(Path.home()), first.stdout)
        paths = {item["path"]: item for item in report["sources"]}
        self.assertEqual(paths["db/types.xml"]["sha256"], hashlib.sha256((self.mission / "db/types.xml").read_bytes()).hexdigest())
        self.assertTrue(all(not Path(path).is_absolute() for path in paths))
        self.assertEqual(report["schema_version"], 1)

    def test_provenance_changes_with_input_and_relocation_is_stable(self):
        first = self.audit()
        other = self.workspace / "relocated"
        shutil.copytree(self.mission, other)
        self.assertEqual(first, self.module.audit_mission(other))
        with (self.mission / "db/types.xml").open("a") as handle:
            handle.write("\n")
        self.assertNotEqual(first["sources"], self.audit()["sources"])

    def test_required_missing_inputs_are_each_explicit(self):
        for relative in ("db/types.xml", "mapgroupproto.xml", "mapgrouppos.xml"):
            with self.subTest(relative=relative):
                path = self.mission / relative
                original = path.read_bytes()
                path.unlink()
                report = self.audit()
                self.assertFalse(report["valid"])
                self.assertIn("missing_required_input", self.codes(report))
                self.assertTrue(any(relative in item["source"] for item in report["diagnostics"]))
                path.write_bytes(original)

    def test_nonexistent_mission_is_explicit_json_failure(self):
        self.mission = self.workspace / "absent"
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing_required_input", self.codes(json.loads(result.stdout)))
        self.assertNotIn("Traceback", result.stderr)

    def test_root_types_fallback_and_ambiguous_base_inputs(self):
        root_types = self.mission / "types.xml"
        shutil.move(self.mission / "db/types.xml", root_types)
        self.assertTrue(self.audit()["valid"])
        shutil.copyfile(root_types, self.mission / "db/types.xml")
        self.assertIn("ambiguous_types_input", self.codes(self.audit()))
        self.assertFalse(self.audit()["valid"])

    def test_malformed_xml_in_every_parsed_file(self):
        for relative in ("db/types.xml", "mapgroupproto.xml", "mapgrouppos.xml", "cfgeconomycore.xml"):
            with self.subTest(relative=relative):
                path = self.mission / relative
                original = path.read_bytes()
                path.write_text("<broken>")
                report = self.audit()
                self.assertFalse(report["valid"])
                self.assertIn("malformed_xml", self.codes(report))
                path.write_bytes(original)

    def test_wrong_roots_and_empty_names_rejected(self):
        for relative in ("db/types.xml", "mapgroupproto.xml", "mapgrouppos.xml", "cfgeconomycore.xml"):
            with self.subTest(relative=relative):
                path = self.mission / relative
                original = path.read_bytes()
                path.write_text("<wrong/>")
                self.assertIn("unexpected_root", self.codes(self.audit()))
                path.write_bytes(original)
        self.write("db/types.xml", '<types><type name=" "/></types>')
        self.assertIn("missing_name", self.codes(self.audit()))

    def test_duplicate_types_within_and_between_sources(self):
        self.write("db/types.xml", '<types><type name="X"/><type name="X"/></types>')
        self.assertIn("duplicate_type", self.codes(self.audit()))
        self.write("db/types.xml", '<types><type name="X"/></types>')
        self.write("mod/extra.xml", '<types><type name="X"/></types>')
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="extra.xml" type="types"/></ce></economycore>')
        report = self.audit()
        self.assertTrue(report["valid"], report["diagnostics"])
        self.assertNotIn("duplicate_type", self.codes(report))
        overrides = [row for row in report["diagnostics"] if row["code"] == "type_override"]
        self.assertEqual(len(overrides), 1)
        self.assertEqual(overrides[0]["severity"], "warning")
        self.assertEqual(report["types"]["entries"], 2)

    def test_duplicate_prototypes_are_not_silently_merged(self):
        self.write("mapgroupproto.xml", '<prototype><group name="X"/><group name="X"><container><point pos="0 0 0"/></container></group></prototype>')
        self.write("mapgrouppos.xml", '<map><group name="X" pos="0 0 0"/></map>')
        report = self.audit()
        self.assertFalse(report["valid"])
        self.assertIn("duplicate_group", self.codes(report))
        row = report["coverage"]["groups"][0]
        self.assertEqual(row["resolution"], "ambiguous")
        self.assertIsNone(row["placed_raw_point_count"])

    def test_negative_noninteger_and_nonfinite_type_counts(self):
        for field in ("nominal", "min", "lifetime", "restock", "cost"):
            for value in ("-1", "1.5", "nan", "inf", "oops", ""):
                with self.subTest(field=field, value=value):
                    self.write("db/types.xml", f'<types><type name="X"><{field}>{value}</{field}></type></types>')
                    report = self.audit()
                    self.assertFalse(report["valid"])
                    self.assertIn("invalid_count", self.codes(report))

    def test_min_nominal_relationship_and_repeated_fields(self):
        self.write("db/types.xml", '<types><type name="X"><nominal>1</nominal><min>2</min></type></types>')
        self.assertIn("min_exceeds_nominal", self.codes(self.audit()))
        self.write("db/types.xml", '<types><type name="X"><min>1</min><min>2</min></type></types>')
        self.assertIn("duplicate_field", self.codes(self.audit()))

    def test_quantity_sentinel_partial_entries_and_flags(self):
        self.assertTrue(self.audit()["valid"])
        self.write("db/types.xml", '<types><type name="X"><quantmin>-2</quantmin><flags count_in_map="2"/></type></types>')
        report = self.audit()
        self.assertIn("invalid_quantity", self.codes(report))
        self.assertIn("invalid_flag", self.codes(report))
        self.write("db/types.xml", '<types><type name="Partial"><nominal>0</nominal></type></types>')
        self.assertTrue(self.audit()["valid"])

    def test_group_container_and_default_count_validation(self):
        for xml in (
            '<group name="X" lootmax="-1"/>',
            '<group name="X"><container lootmax="1.5"/></group>',
            '<defaults><default name="group" lootmax="nan"/></defaults>',
        ):
            with self.subTest(xml=xml):
                self.write("mapgroupproto.xml", f'<prototype>{xml}</prototype>')
                self.assertIn("invalid_count", self.codes(self.audit()))

    def test_bad_coordinates_and_point_dimensions(self):
        for value in ("nan 0 0", "0 inf 0", "0 0 -inf", "0 1", "0 0 bad", "1e999 0 0"):
            for relative, xml in (
                ("mapgrouppos.xml", f'<map><group name="SyntheticHouse" pos="{value}"/></map>'),
                ("mapgroupproto.xml", f'<prototype><group name="SyntheticHouse"><container><point pos="{value}"/></container></group></prototype>'),
            ):
                with self.subTest(value=value, relative=relative):
                    original = (self.mission / relative).read_bytes()
                    self.write(relative, xml)
                    self.assertIn("invalid_coordinate", self.codes(self.audit()))
                    (self.mission / relative).write_bytes(original)
        self.write("mapgroupproto.xml", '<prototype><group name="X"><container><point pos="0 0 0" range="-1" height="nan"/></container></group></prototype>')
        self.assertIn("invalid_dimension", self.codes(self.audit()))

    def test_nonfinite_rotations_and_missing_positions(self):
        for attrs in ('pos="0 0 0" rpy="0 nan 0"', 'pos="0 0 0" a="inf"', ''):
            with self.subTest(attrs=attrs):
                self.write("mapgrouppos.xml", f'<map><group name="SyntheticHouse" {attrs}/></map>')
                self.assertIn("invalid_coordinate", self.codes(self.audit()))

    def test_missing_group_and_possible_alias_are_visible_unresolved(self):
        self.write("mapgrouppos.xml", '<map><group name="synthetichouse" pos="0 0 0"/><group name="MissingModel.p3d" pos="0 0 0"/></map>')
        report = self.audit()
        self.assertFalse(report["valid"])
        self.assertIn("possible_alias", self.codes(report))
        self.assertIn("missing_group", self.codes(report))
        rows = {row["name"]: row for row in report["coverage"]["groups"]}
        self.assertIsNone(rows["synthetichouse"]["raw_point_count"])
        self.assertEqual(rows["synthetichouse"]["alias_candidates"], ["SyntheticHouse"])
        self.assertFalse(report["coverage"]["building_classes_verified"])

    def test_explicit_alias_construct_is_visible_and_not_resolved(self):
        self.write("mapgroupproto.xml", '<prototype><group name="X"><alias name="Y"/></group></prototype>')
        self.assertIn("unresolved_alias", self.codes(self.audit()))

    def test_modular_types_are_declared_not_recursively_discovered(self):
        self.write("mod/types-extra.xml", '<types><type name="SyntheticModItem"/></types>')
        self.write("unregistered/types.xml", '<types><type name="Ignored"/></types>')
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="types-extra.xml" type="types"/></ce></economycore>')
        report = self.audit()
        self.assertTrue(report["valid"])
        self.assertEqual(report["types"]["unique_names"], 3)
        self.assertIn("mod/types-extra.xml", {source["path"] for source in report["sources"]})
        self.assertNotIn("unregistered/types.xml", {source["path"] for source in report["sources"]})

    def test_other_ce_file_kinds_are_listed_without_merging(self):
        self.write("mod/proto.xml", "<prototype/>")
        self.write("mod/events.xml", "<events/>")
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="proto.xml" type="mapgroupproto"/><file name="events.xml" type="events"/></ce></economycore>')
        report = self.audit()
        self.assertTrue(report["valid"])
        self.assertIn("unsupported_ce_file_type", self.codes(report))
        self.assertEqual(len(report["ce_declarations"]), 2)
        self.assertTrue(all(row["status"] == "not_audited" for row in report["ce_declarations"]))
        self.assertEqual(report["coverage"]["raw_point_count"], 4)

    def test_missing_declared_types_and_optional_core_visibility(self):
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="absent.xml" type="types"/></ce></economycore>')
        self.assertIn("missing_required_input", self.codes(self.audit()))
        (self.mission / "cfgeconomycore.xml").unlink()
        report = self.audit()
        self.assertTrue(report["valid"])
        self.assertIn("modular_types_not_checked", self.codes(report))

    def test_declaration_path_escape_and_symlinks_are_rejected(self):
        for folder, name in (("../outside", "types.xml"), ("/absolute", "types.xml"), ("C:\\secret", "types.xml"), ("mod", "../../escape.xml")):
            with self.subTest(folder=folder, name=name):
                self.write("cfgeconomycore.xml", f'<economycore><ce folder="{folder}"><file name="{name}" type="types"/></ce></economycore>')
                self.assertIn("unsafe_source_path", self.codes(self.audit()))
        outside = self.workspace / "outside.xml"
        outside.write_text('<types><type name="Secret"/></types>')
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="link.xml" type="types"/></ce></economycore>')
        (self.mission / "mod").mkdir(exist_ok=True)
        (self.mission / "mod/link.xml").symlink_to(outside)
        self.assertIn("unsafe_source_path", self.codes(self.audit()))

    def test_backslash_declaration_paths_and_repeated_source(self):
        self.write("mod/sub/extra.xml", '<types><type name="Mod"/></types>')
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod\\sub"><file name="extra.xml" type="types"/><file name="extra.xml" type="types"/></ce></economycore>')
        report = self.audit()
        self.assertIn("duplicate_source", self.codes(report))
        self.assertEqual(report["types"]["entries"], 3)

    def test_authoritative_catalog_is_optional_and_unknowns_fail(self):
        unchecked = self.audit()
        self.assertEqual(unchecked["types"]["catalog_status"], "not_supplied")
        self.assertTrue(self.audit(known_types=CATALOG)["valid"])
        catalog = self.workspace / "synthetic_partial_catalog.txt"
        catalog.write_text("SyntheticApple\n")
        report = self.audit(known_types=catalog)
        self.assertFalse(report["valid"])
        self.assertEqual(report["types"]["unknown_names"], ["SyntheticTool"])
        self.assertIn("unknown_type", self.codes(report))
        self.assertNotIn(str(self.workspace), json.dumps(report))
        self.assertTrue(any(source["role"] == "known_types" for source in report["sources"]))

    def test_missing_empty_and_invalid_catalog_fail(self):
        missing = self.workspace / "missing.txt"
        self.assertFalse(self.audit(known_types=missing)["valid"])
        catalog = self.workspace / "catalog.txt"
        for content in (b"", b"# comments only\n", b"\xff"):
            with self.subTest(content=content):
                catalog.write_bytes(content)
                self.assertIn("invalid_catalog", self.codes(self.audit(known_types=catalog)))

    def test_xml_catalog_support(self):
        catalog = self.workspace / "synthetic_catalog.xml"
        catalog.write_text('<types><type name="SyntheticApple"/><type name="SyntheticTool"/></types>')
        self.assertTrue(self.audit(known_types=catalog)["valid"])

    def test_bounded_bytes_files_nodes_and_depth(self):
        for constant, limit in (("MAX_FILE_BYTES", 16), ("MAX_TOTAL_BYTES", 32), ("MAX_SOURCE_FILES", 1), ("MAX_XML_NODES", 2), ("MAX_XML_DEPTH", 1)):
            with self.subTest(constant=constant), patch.object(self.module, constant, limit):
                report = self.audit()
                self.assertFalse(report["valid"])
                self.assertIn("resource_limit", self.codes(report))
                self.assertEqual(json.loads(json.dumps(report, allow_nan=False)), report)

    def test_dtd_and_entities_rejected_including_utf16(self):
        xml = '<!DOCTYPE types [<!ENTITY a "expanded">]><types><type name="&a;"/></types>'
        for encoding in ("utf-8", "utf-16"):
            with self.subTest(encoding=encoding):
                (self.mission / "db/types.xml").write_bytes(xml.encode(encoding))
                self.assertIn("unsafe_xml", self.codes(self.audit()))

    def test_output_file_matches_stdout_and_invalid_still_written(self):
        output = self.workspace / "audit.json"
        result = self.cli("--output", output, "--known-types", CATALOG)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(), result.stdout)
        self.write("db/types.xml", "<broken>")
        result = self.cli("--output", output)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(output.read_text()), json.loads(result.stdout))
        self.assertFalse(json.loads(result.stdout)["valid"])

    def test_output_cannot_overwrite_a_source_or_fail_with_traceback(self):
        source = self.mission / "db/types.xml"
        original = source.read_bytes()
        result = self.cli("--output", source)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(source.read_bytes(), original)
        self.assertIn("output_conflicts_with_source", self.codes(json.loads(result.stdout)))
        result = self.cli("--output", self.workspace / "missing/report.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("output_error", self.codes(json.loads(result.stdout)))
        self.assertNotIn(str(self.workspace), result.stdout + result.stderr)

    def test_missing_coverage_input_does_not_invent_zero_totals(self):
        (self.mission / "mapgroupproto.xml").unlink()
        report = self.audit()
        self.assertIsNone(report["coverage"]["raw_point_count"])
        self.assertIsNone(report["coverage"]["placed_raw_point_count"])
        self.assertEqual(report["coverage"]["placement_count"], 3)
        self.assertNotIn("missing_group", self.codes(report))
        self.assertTrue(all(row["resolution"] == "input_unavailable" for row in report["coverage"]["groups"]))

    def test_unresolved_placements_have_partial_subtotal_not_false_total(self):
        self.write("mapgrouppos.xml", '<map><group name="SyntheticHouse" pos="0 0 0"/><group name="Missing" pos="0 0 0"/></map>')
        report = self.audit()
        self.assertIsNone(report["coverage"]["placed_raw_point_count"])
        self.assertEqual(report["coverage"]["resolved_placed_raw_point_count"], 3)
        self.assertEqual(report["coverage"]["unresolved_placement_count"], 1)

    def test_declared_unparsed_files_are_protected_from_output(self):
        source = self.write("mod/events.xml", "<events/>")
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="events.xml" type="events"/></ce></economycore>')
        result = self.cli("--output", source)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(source.read_text(), "<events/>")
        self.assertIn("output_conflicts_with_source", self.codes(json.loads(result.stdout)))

    def test_missing_modular_source_is_not_reported_as_audited(self):
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="absent.xml" type="types"/></ce></economycore>')
        report = self.audit()
        self.assertEqual(report["ce_declarations"][0]["status"], "unavailable")

    def test_unresolvable_mission_path_is_json_failure(self):
        loop = self.workspace / "loop"
        loop.symlink_to(loop)
        self.mission = loop
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid_mission", self.codes(json.loads(result.stdout)))
        self.assertNotIn("Traceback", result.stderr)

    def one_prototype(self, body):
        self.write("mapgroupproto.xml", f"<prototype>{body}</prototype>")
        self.write("mapgrouppos.xml", '<map><group name="SyntheticHouse" pos="0 0 0"/></map>')

    def test_zero_nominal_positive_min_matches_shipped_data_shape(self):
        # Official DZ_130 AND installed mission contain 172 nominal=0/min=1
        # entries. This synthetic case tests that shape without importing data.
        self.write("db/types.xml", '<types><type name="SyntheticEventEntity"><nominal>0</nominal><min>1</min></type></types>')
        report = self.audit()
        self.assertTrue(report["valid"], report["diagnostics"])
        self.assertNotIn("min_exceeds_nominal", self.codes(report))

    def test_duplicate_within_override_file_still_fails(self):
        self.write("mod/extra.xml", '<types><type name="SyntheticApple"/><type name="SyntheticApple"/></types>')
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="extra.xml" type="types"/></ce></economycore>')
        report = self.audit()
        self.assertFalse(report["valid"])
        self.assertIn("duplicate_type", self.codes(report))
        self.assertIn("type_override", self.codes(report))

    def test_partial_cross_file_override_is_not_merged_or_rejected(self):
        self.write("mod/extra.xml", '<types><type name="SyntheticApple"><nominal>0</nominal></type></types>')
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="extra.xml" type="types"/></ce></economycore>')
        report = self.audit()
        self.assertTrue(report["valid"], report["diagnostics"])
        self.assertEqual(report["types"]["entries"], 3)
        self.assertEqual(report["types"]["unique_names"], 2)
        self.assertIn("type_override", self.codes(report))

    def test_official_dispatch_and_cluster_shape_with_synthetic_names(self):
        self.one_prototype('<defaults><default name="clusterMatrix" de="SyntheticTrajectory" width="12" height="12"/></defaults><group name="SyntheticHouse" lootmax="0"><container name="loot" lootmax="0"/><dispatch dechance="0.5"><proxy type="SyntheticTool" pos="1 2 3" rpy="90 0 -90" dechance="0"/></dispatch></group>')
        report = self.audit(known_types=CATALOG)
        self.assertTrue(report["valid"], report["diagnostics"])
        self.assertEqual(report["references"]["proxy_type_names"], ["SyntheticTool"])
        self.assertEqual(report["coverage"]["raw_point_count"], 0)
        self.assertIsNone(report["coverage"]["engine_eligible_loot_points"])

    def test_proxy_reference_checked_against_catalog_not_ce_inventory(self):
        self.one_prototype('<group name="SyntheticHouse"><dispatch><proxy type="SyntheticProxyOnly" pos="0 0 0"/></dispatch></group>')
        report = self.audit(known_types=CATALOG)
        self.assertFalse(report["valid"])
        self.assertIn("unknown_reference", self.codes(report))
        self.assertEqual(report["references"]["unknown_proxy_type_names"], ["SyntheticProxyOnly"])
        catalog = self.workspace / "catalog.txt"
        catalog.write_text(CATALOG.read_text() + "\nSyntheticProxyOnly\n")
        report = self.audit(known_types=catalog)
        self.assertTrue(report["valid"], report["diagnostics"])
        self.assertNotIn("SyntheticProxyOnly", report["types"]["names"])

    def test_proxy_reference_requires_nonempty_type(self):
        for attrs in ('', 'type=" "'):
            with self.subTest(attrs=attrs):
                self.one_prototype(f'<group name="SyntheticHouse"><dispatch><proxy {attrs} pos="0 0 0"/></dispatch></group>')
                report = self.audit()
                self.assertFalse(report["valid"])
                self.assertIn("missing_proxy_type", self.codes(report))

    def test_alias_attributes_and_elements_prevent_false_resolved_coverage(self):
        for body in ('<group name="SyntheticHouse" alias="SyntheticElsewhere"/>',
                     '<group name="SyntheticHouse"><alias name="SyntheticElsewhere"/></group>',
                     '<aliases><alias name="SyntheticElsewhere"/></aliases><group name="SyntheticHouse"/>'):
            with self.subTest(body=body):
                self.one_prototype(body)
                report = self.audit()
                self.assertFalse(report["valid"])
                self.assertIn("unresolved_alias", self.codes(report))
                self.assertIsNone(report["coverage"]["placed_raw_point_count"])
                row = next(row for row in report["coverage"]["groups"] if row["name"] == "SyntheticHouse")
                self.assertEqual(row["resolution"], "unresolved")
                self.assertIsNone(row["placed_raw_point_count"])

    def test_cluster_dimensions_finite_and_nonnegative(self):
        for field in ("width", "height"):
            for value in ("NaN", "inf", "-inf", "1e999", "-1", "oops"):
                with self.subTest(field=field, value=value):
                    self.one_prototype(f'<defaults><default name="clusterMatrix" {field}="{value}"/></defaults><group name="SyntheticHouse"/>')
                    report = self.audit()
                    self.assertFalse(report["valid"])
                    self.assertIn("invalid_dimension", self.codes(report))

    def test_dispatch_probability_finite_and_nonnegative(self):
        for tag in ("dispatch", "proxy"):
            for value in ("NaN", "inf", "-inf", "1e999", "-1", "oops"):
                with self.subTest(tag=tag, value=value):
                    content = f'<dispatch dechance="{value}"/>' if tag == "dispatch" else f'<dispatch><proxy type="SyntheticTool" pos="0 0 0" dechance="{value}"/></dispatch>'
                    self.one_prototype(f'<group name="SyntheticHouse">{content}</group>')
                    report = self.audit()
                    self.assertFalse(report["valid"])
                    self.assertIn("invalid_probability", self.codes(report))

    def test_point_flags_reject_noninteger_and_nonfinite(self):
        for value in ("NaN", "inf", "-1", "1.5"):
            with self.subTest(value=value):
                self.one_prototype(f'<group name="SyntheticHouse"><container><point pos="0 0 0" flags="{value}"/></container></group>')
                self.assertIn("invalid_count", self.codes(self.audit()))

    def test_numeric_core_defaults_reject_nonfinite_values(self):
        for value in ("NaN", "inf", "-inf", "1e999"):
            with self.subTest(value=value):
                self.write("cfgeconomycore.xml", f'<economycore><defaults><default name="dyn_radius" value="{value}"/></defaults></economycore>')
                report = self.audit()
                self.assertFalse(report["valid"])
                self.assertIn("invalid_number", self.codes(report))
        self.write("cfgeconomycore.xml", '<economycore><defaults><default name="dyn_radius" value="30"/><default name="log_ce_loop" value="false"/></defaults></economycore>')
        self.assertTrue(self.audit()["valid"])

    def test_missing_unparsed_declared_source_is_not_complete(self):
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="absent.xml" type="events"/></ce></economycore>')
        report = self.audit()
        self.assertFalse(report["valid"])
        self.assertFalse(report["inputs_complete"])
        self.assertIn("missing_required_input", self.codes(report))
        self.assertEqual(report["ce_declarations"][0]["status"], "unavailable")

    def test_unparsed_declarations_are_hashed_but_not_schema_validated(self):
        source = self.write("mod/events.xml", "not parsed as XML in this bounded audit")
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="events.xml" type="events"/></ce></economycore>')
        report = self.audit()
        self.assertTrue(report["valid"], report["diagnostics"])
        record = next(row for row in report["sources"] if row["path"] == "mod/events.xml")
        self.assertEqual(record["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(report["ce_declarations"][0]["status"], "not_audited")

    def test_unparsed_declaration_symlink_escape_is_invalid(self):
        outside = self.workspace / "outside.xml"
        outside.write_text("<events/>")
        self.write("mod/placeholder", "")
        (self.mission / "mod/events.xml").symlink_to(outside)
        self.write("cfgeconomycore.xml", '<economycore><ce folder="mod"><file name="events.xml" type="events"/></ce></economycore>')
        report = self.audit()
        self.assertFalse(report["valid"])
        self.assertIn("unsafe_source_path", self.codes(report))

    def test_catalog_may_reuse_already_audited_source(self):
        report = self.audit(known_types=self.mission / "db/types.xml")
        self.assertTrue(report["valid"], report["diagnostics"])
        self.assertEqual(report["types"]["catalog_status"], "supplied")
        self.assertNotIn("duplicate_source", self.codes(report))

    def test_bom_xml_catalog_detection_does_not_depend_on_suffix(self):
        catalog = self.workspace / "catalog.snapshot"
        xml = '<types><type name="SyntheticApple"/><type name="SyntheticTool"/></types>'
        for encoding in ("utf-8-sig", "utf-16", "utf-32"):
            with self.subTest(encoding=encoding):
                catalog.write_bytes(xml.encode(encoding))
                report = self.audit(known_types=catalog)
                self.assertTrue(report["valid"], report["diagnostics"])
                self.assertEqual(report["types"]["catalog_status"], "supplied")

    def test_catalog_control_characters_are_not_classnames(self):
        catalog = self.workspace / "catalog.txt"
        catalog.write_bytes(CATALOG.read_bytes() + b"\ninvalid\x00name\n")
        report = self.audit(known_types=catalog)
        self.assertFalse(report["valid"])
        self.assertIn("invalid_catalog", self.codes(report))

    def test_unresolvable_catalog_paths_are_json_failures(self):
        for relative in ("missing.txt", "loop.txt"):
            path = self.workspace / relative
            if relative == "loop.txt":
                path.symlink_to(path)
            report = self.audit(known_types=path)
            self.assertFalse(report["valid"])
            self.assertEqual(report["types"]["catalog_status"], "invalid")
            self.assertEqual(json.loads(json.dumps(report, allow_nan=False)), report)
        report = self.audit(known_types="\x00")
        self.assertFalse(report["valid"])
        self.assertIn("unreadable_input", self.codes(report))

    def test_cli_usage_and_no_bytecode(self):
        result = subprocess.run([sys.executable, "-m", "tools.audit.ce_audit"], cwd=ROOT,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--mission", result.stderr)
        self.assertFalse(list(self.mission.rglob("__pycache__")))


if __name__ == "__main__":
    unittest.main()
