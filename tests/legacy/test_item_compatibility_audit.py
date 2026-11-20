"""#52/#56 authored-policy execution and source contracts, not native acceptance.

Fixtures are synthetic. Native merged-config invocation belongs to the coordinator.
Only the new diagnostic source is read; no game files or exports are fixtures.

Actual TDD, 2026-11-16:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_item_compatibility_audit -v
RED: 13 failures, "missing native merged-config acquisition seam", before source.
GREEN: 13 passed after implementation. The initial reused test translator also
misread equality as declaration assignment; this file's restricted expression
executor preserves equality. These results do not establish native compilation.

Actual native-030 regression, build 1.30.164289.70: compiled/initialized;
private JSON reported Partial=1, RowsWritten=0, VisitedChildren=2,
CfgWeapons AdvertisedChildren=216, StopReason=field_type:inventorySlot.
That JSON omitted class/type. Separately inspected staged dta/bin.pbo config.bin
SHA256 2bd35c18c2a3bbb284fb5faf308249b0a4836b99353f349811649f592ba66ef1:
CfgWeapons orders access then Weapon_Base, inventorySlot scalar string "".
Do not confuse the RAP scalar-string tag 0 with a runtime CT constant value.
Follow-up RED: three new variant/type regressions failed on missing authored
NativeReadMode/NativeTypeName. GREEN: all 16 focused tests passed after the fix.
Actual native-032 initialized and retained 945 rows before the 16 MiB conservative
bound: CfgWeapons 216/216 children, 215 rows; CfgVehicles 732/6790 children,
730 rows; stop CfgVehicles NBCPantsWhite. File 4,186,055 bytes; row bound 16,734,028.
Observed CT_INT=0, CT_FLOAT=1, CT_STRING=2, CT_ARRAY=3; Weapon_Base inventorySlot
was captured as scalar "" with CT_STRING=2 and explicit schema-kind uncertainty.

ExportAll TDD: same focused command, actual RED 8 new failures / 16 existing
passes before chunk implementation; GREEN all 24 passed. ExportAll itself has
not been compiled or invoked natively by this worker. No game data is a fixture.

Actual native-033 compiler RED: source line 810, Broken expression missing ;.
The local name reference is a native qualifier (1_Core/proto/proto.c).
Reserved-name regression above focused command: RED one failing assertion before
rename; GREEN all 24 passed after renaming the local to chunkReference.
Native-034 compilation and whole-root acquisition remain pending.

Subsequent coordinator-reported native-034: compile/init succeeded; 14 chunks,
7006 children / 7004 class rows in the original two roots, FullCoverage=0.
That run does not validate the expanded root list below.
Root-expansion TDD, same focused command: actual RED two failures (missing
BuildRoots/shared enumeration); GREEN 25 passed after implementation.
Native hierarchy inspected: Magazine.c Magazine : InventoryItemSuper,
AmmunitionPiles.c Ammunition_Base : Magazine_Base, and Game.c IsKindOf searches
CfgAmmo and CfgMagazines separately. The same staged base config.bin hash above
defines CfgMagazines (DefaultMagazine) and CfgAmmo (DefaultAmmo/BulletCore/
ShotgunCore); base definitions are not a merged runtime census.
Four-root compilation/acquisition and inventory eligibility remain pending.
"""
import math
from pathlib import Path
import re
import textwrap
from types import SimpleNamespace
import unittest

try:
    from tests.legacy.test_crafting_completion import body
except ImportError:
    from tests.legacy.test_crafting_completion import body

FILENAME = "HCItemCompatibilityAudit.c"
SOURCE = Path(__file__).resolve().parents[2] / (
    "mods/HollowCountry/scripts/4_World/Crafting/" + FILENAME)


def execute_policy(method, parameters, context):
    """Only flat if/return expressions; preserve equality, never rewrite it as assignment."""
    authored = re.sub(r"//[^\n]*", "", body(FILENAME, method))
    if "{" in authored or "}" in authored:
        raise AssertionError("unsupported policy control flow")
    lines = []
    for statement in authored.split(";"):
        statement = statement.strip()
        if not statement:
            continue
        if not re.match(r"^(?:return\b|if\s*\()", statement):
            raise AssertionError("unsupported policy statement: " + statement)
        statement = statement.replace("&&", " and ").replace("||", " or ")
        statement = re.sub(r"!(?!=)", "not ", statement)
        statement = re.sub(r"\btrue\b", "True", statement)
        statement = re.sub(r"\bfalse\b", "False", statement)
        statement = re.sub(r"^if \((.*)\)\s+(return\b.*)$", r"if \1: \2", statement, flags=re.S)
        lines.append("    " + " ".join(statement.split()))
    namespace = dict(context)
    program = "def actual(" + parameters + "):\n" + "\n".join(lines)
    exec(compile(program, "authored-item-audit:" + method, "exec"), namespace)
    return namespace["actual"]


class ItemCompatibilityAuditTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), "missing native merged-config acquisition seam")
        self.source = SOURCE.read_text()
        self.context = dict(re.findall(r"static const int (\w+) = (\d+);", self.source))
        self.context = {name: int(value) for name, value in self.context.items()}
        self.context["float"] = SimpleNamespace(MAX=3.4028234663852886e38)

    def policy(self, method, parameters):
        return execute_policy(method, parameters, self.context)

    def test_limits_reject_unbounded_or_unusable_requests(self):
        valid = self.policy("ValidLimits", "maxRows,maxBytes")
        self.assertTrue(valid(1, 65536))
        self.assertTrue(valid(65536, 33554432))
        for rows, size in ((0, 65536), (-1, 65536), (65537, 65536),
                           (1, 65535), (1, 33554433), (2147483647, 2147483647)):
            self.assertFalse(valid(rows, size), (rows, size))

    def test_filename_character_policy_rejects_paths_and_unicode(self):
        allowed = self.policy("AllowedRunIdCharacter", "code")
        for code in range(256):
            expected = chr(code) in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            self.assertEqual(allowed(code), expected, code)
        for code in (-1, 256, 0x202e, 0x10ffff):
            self.assertFalse(allowed(code))
        method = body(FILENAME, "SafeRunId")
        self.assertIn("AllowedRunIdCharacter", method)
        self.assertIn("MAX_RUN_ID", method)
        self.assertIn("runId.Length()", method)

    def test_byte_bound_is_conservative_and_overflow_safe(self):
        bound = self.policy("Utf8ByteBound", "units")
        self.assertEqual(bound(0), 0)
        self.assertEqual(bound(17), 68)
        self.assertEqual(bound(8388607), 33554428)
        for units in (-1, 8388608, 2147483647):
            self.assertEqual(bound(units), -1)

    def test_nonfinite_config_numbers_are_not_serialized(self):
        finite = self.policy("FiniteNumber", "value")
        for value in (-100., 0., 1., 1e30):
            self.assertTrue(finite(value))
        for value in (math.nan, math.inf, -math.inf, 1e39):
            self.assertFalse(finite(value))

    def test_row_admission_preserves_header_reserve_and_exact_bounds(self):
        fits = self.policy("FitsRowBudget", "rowCount,byteBound,rowByteBound,maxRows,maxBytes")
        self.assertTrue(fits(0, 0, 32768, 1, 65536))
        self.assertFalse(fits(1, 0, 100, 1, 65536))
        self.assertFalse(fits(0, 0, 32769, 1, 65536))
        self.assertTrue(fits(0, 100, 32668, 2, 65536))
        self.assertFalse(fits(0, 101, 32668, 2, 65536))
        self.assertFalse(fits(0, 0, 65537, 2, 33554432))
        for args in ((-1, 0, 1, 1, 65536), (0, -1, 1, 1, 65536),
                     (0, 0, -1, 1, 65536), (0, 2147483647, 1, 1, 65536)):
            self.assertFalse(fits(*args), args)

    def test_native_type_gate_preserves_zero_and_distinguishes_arrays(self):
        types = {"CT_INT": 1, "CT_FLOAT": 2, "CT_STRING": 3, "CT_ARRAY": 4, "CT_CLASS": 5}
        self.context.update(types)
        accepts = self.policy("TypeMatches", "configType,readAs")
        for name, value in types.items():
            self.assertEqual(accepts(value, "text"), name == "CT_STRING")
            self.assertEqual(accepts(value, "number"), name in ("CT_INT", "CT_FLOAT"))
            for mode in ("text_array", "int_array", "float_array"):
                self.assertEqual(accepts(value, mode), name == "CT_ARRAY")
        self.assertFalse(accepts(1, "invented"))

    def native_types(self):
        # Distinct synthetic codes deliberately differ from any assumed engine ABI.
        self.context.update({"CT_INT": 11, "CT_FLOAT": 23, "CT_STRING": 37,
                             "CT_ARRAY": 41, "CT_CLASS": 59, "CT_OTHER": 67})
        return self.context

    def test_native030_empty_scalar_inventory_slot_has_lossless_read_mode(self):
        self.native_types()
        mode = self.policy("NativeReadMode", "configType,expectedMode")
        # Synthetic reproduction of installed bin.pbo CfgWeapons Weapon_Base:
        # inventorySlot is scalar string "", not an array or an absent field.
        self.assertEqual(mode(self.context["CT_STRING"], "text_array"), "text")
        read = body(FILENAME, "ReadField")
        self.assertIn("field.ReadAs = NativeReadMode(fieldType, spec.ReadAs)", read)
        self.assertIn('if (field.ReadAs == "text")', read)
        self.assertNotIn('error = "field_type:"', read)
        self.assertNotIn("field.ValueText.Length() <", read)
        self.assertIn("field.ExpectedReadAs = spec.ReadAs", read)
        self.assertIn("field.ConfigTypeName = NativeTypeName(fieldType)", read)
        self.assertIn("field.ValueCaptured = true", read)

    def test_all_supported_native_kind_variants_preserve_actual_getter_selection(self):
        self.native_types()
        mode = self.policy("NativeReadMode", "configType,expectedMode")
        expected_modes = ("text", "number", "text_array", "int_array", "float_array")
        for expected in expected_modes:
            for native_name, selected in (("CT_STRING", "text"), ("CT_INT", "number"),
                                          ("CT_FLOAT", "number")):
                self.assertEqual(mode(self.context[native_name], expected), selected)
            selected = expected if expected.endswith("_array") else "text_array"
            self.assertEqual(mode(self.context["CT_ARRAY"], expected), selected)
            for native_name in ("CT_CLASS", "CT_OTHER"):
                self.assertEqual(mode(self.context[native_name], expected), "unresolved")

    def test_unreadable_kinds_remain_explicit_fields_without_aborting_roots(self):
        self.native_types()
        name = self.policy("NativeTypeName", "configType")
        for symbol in ("CT_INT", "CT_FLOAT", "CT_STRING", "CT_ARRAY", "CT_CLASS", "CT_OTHER"):
            self.assertEqual(name(self.context[symbol]), symbol)
        self.assertEqual(name(9876), "UNKNOWN_NATIVE_TYPE")
        read = body(FILENAME, "ReadField")
        for evidence in ("schema_kind_variant", "unsupported_native_kind", "array_element_kind_unverified",
                         "row.UnresolvedFields++", "row.KindVariantFields++"):
            self.assertIn(evidence, read)
        collect = body(FILENAME, "Collect")
        self.assertIn("header.UnresolvedFields += unresolvedFields", collect)
        self.assertIn("header.KindVariantFields += kindVariantFields", collect)
        self.assertIn('header.StopClassPath = root + " " + childName', collect)

    def test_complete_roots_are_scanned_without_label_or_pilot_filters(self):
        scan = body(FILENAME, "Collect")
        self.assertIn("BuildRoots(roots)", scan)
        for api in ("ConfigGetChildrenCount", "ConfigGetChildName", "ConfigGetType"):
            self.assertIn(api, scan)
        for prohibited in ("displayName", "IsKindOf", "pilot", ".Contains("):
            self.assertNotIn(prohibited, scan)
        self.assertIn("MAX_VISITED_FACTOR", scan)
        self.assertIn("FitsRowBudget", scan)

    def test_both_exports_share_all_four_roots_with_explicit_projectile_role(self):
        # Execute the authored fixed insertion method against a synthetic array.
        declared = body(FILENAME, "BuildRoots")
        self.assertRegex(declared, r'^(?:\s*roots\.Insert\("[A-Za-z]+"\);\s*)+$')
        class SyntheticRoots(list):
            Insert = list.append
        roots = SyntheticRoots()
        exec(compile(textwrap.dedent(declared).strip(), "authored-item-audit:BuildRoots", "exec"),
             {"__builtins__": {}, "roots": roots})
        self.assertEqual(roots, ["CfgWeapons", "CfgVehicles", "CfgMagazines", "CfgAmmo"])
        self.assertEqual(len(roots), len(set(roots)))
        for collector in ("Collect", "BuildIndexPlan"):
            method = body(FILENAME, collector)
            self.assertEqual(method.count("BuildRoots(roots)"), 1)
            self.assertNotIn("roots.Insert", method)
            self.assertIn("rootInfo.ConfigRole = RootRole(rootInfo.ConfigRoot)" if
                          collector == "BuildIndexPlan" else
                          "rootRecord.ConfigRole = RootRole(rootName)", method)
        header = body(FILENAME, "NewHeader")
        self.assertIn("BuildRoots(roots)", header)
        self.assertIn('header.EnumerationOrder = "native_child_index_" + string.Join("_then_", roots)', header)
        role = self.policy("RootRole", "root")
        self.assertEqual(role("CfgMagazines"), "magazine_and_ammunition_inventory_config")
        self.assertEqual(role("CfgAmmo"), "projectile_config_not_inventory_eligibility")
        self.assertEqual(role("CfgWeapons"), "weapon_config_not_inventory_eligibility")
        self.assertEqual(role("CfgVehicles"), "vehicle_and_equipment_config_not_inventory_eligibility")
        self.assertEqual(role("UnknownRoot"), "unresolved_root_role")
        # Explicit synthetic four-root denominator includes non-class children.
        fits = self.policy("AllChildrenFit", "already,additional")
        total = 0
        for count in (3, 5, 4, 2):
            self.assertTrue(fits(total, count))
            total += count
        self.assertTrue(self.policy("AllCountsComplete", "advertised,planned,covered,expectedRows,rows,nonclass")
                        (total, total, total, 10, 10, 4))
        self.assertFalse(fits(total, 16384))

    def test_ancestry_is_config_based_bounded_and_cycle_checked(self):
        ancestry = body(FILENAME, "ReadAncestry")
        for term in ("ConfigGetBaseName", "ConfigIsExisting", "MAX_ANCESTORS", ".Find("):
            self.assertIn(term, ancestry)
        self.assertIn('root + " " + currentClass', ancestry)
        self.assertNotIn("IsKindOf", ancestry)

    def test_missing_fields_omitted_and_present_types_drive_bounded_reads(self):
        read = body(FILENAME, "ReadField")
        self.assertLess(read.index("ConfigIsExisting"), read.index("ConfigGetType"))
        self.assertLess(read.index("TypeMatches"), read.index("ConfigGetTextRaw"))
        for api in ("ConfigGetInt", "ConfigGetFloat", "ConfigGetTextArrayRaw",
                    "ConfigGetIntArray", "ConfigGetFloatArray"):
            self.assertIn(api, read)
        for limit in ("MAX_ARRAY_VALUES", "MAX_VALUE_UNITS", "FiniteNumber"):
            self.assertIn(limit, read)

    def test_metadata_schema_covers_slots_energy_repair_liquid_and_cargo(self):
        schema = body(FILENAME, "BuildSchema")
        for name in ("scope", "model", "ClothingTypes male", "ClothingTypes female",
                     "inventorySlot", "attachments", "hasRailFunctionality",
                     "repairKitType", "repairableWithKits", "repairCosts",
                     "liquidContainerType", "varLiquidTypeInit", "varQuantityMax",
                     "Cargo itemsCargoSize", "itemSize", "EnergyManager energyUsagePerSecond",
                     "EnergyManager compatiblePlugTypes", "EnergyManager attachmentAction"):
            self.assertIn(name, schema)
        fields = re.findall(r'AddSpecs\(schema, "([^"]+)", "[^"]+"\)', schema)
        paths = [path for group in fields for path in group.split(",")]
        self.assertEqual(len(paths), len(set(paths)), "schema paths must be unique")
        self.assertLessEqual(len(paths), self.context["MAX_FIELDS"])
        self.assertGreater(len(paths), 40)

    def test_file_policy_is_profile_only_fresh_and_readback_verified(self):
        export = body(FILENAME, "Export")
        self.assertIn("profileOutsideGitConfirmed", export)
        self.assertIn("SafeRunId", export)
        self.assertIn('"$profile:HollowCountry/ItemCompatibilityAudit/"', export)
        self.assertGreaterEqual(export.count("FileExist(destination)"), 2)
        self.assertLess(export.index("FileExist(destination)"), export.index("Collect("))
        self.assertLess(export.rindex("FileExist(destination)"), export.index("OpenFile(destination, FileMode.WRITE)"))
        for term in ("FileMode.READ", "ReadFile", "maxBytes + 1", "readback != payload"):
            self.assertIn(term, export)
        self.assertNotIn("FileMode.APPEND", export)
        self.assertNotIn("DeleteFile", export)
        self.assertIn("s_ExportActive", export)

    def test_partial_export_never_becomes_full_coverage(self):
        self.assertIn("bool FullCoverage = false;", self.source)
        self.assertIn("bool Partial = false;", self.source)
        self.assertIn('"live_geometry"', self.source)
        self.assertIn('"model_proxies"', self.source)
        self.assertIn('"beam_alignment"', self.source)
        self.assertIn('"player_condition"', self.source)
        collect = body(FILENAME, "Collect")
        for reason in ("row_budget", "byte_budget", "visited_budget", "missing_root"):
            self.assertIn(reason, collect)
        self.assertIn("return !header.Partial", body(FILENAME, "Export"))

    def test_all_child_denominator_is_bounded_before_index_enumeration(self):
        fits = self.policy("AllChildrenFit", "already,additional")
        self.assertTrue(fits(0, 16384))
        self.assertTrue(fits(216, 6790))  # observed advertised children, not class count
        for args in ((0, -1), (-1, 1), (16384, 1), (1, 2147483647)):
            self.assertFalse(fits(*args), args)

    def test_chunk_limits_count_children_not_just_emitted_class_rows(self):
        fits = self.policy("ChunkFits", "coveredChildren,rowByteBound,candidateBound")
        self.assertTrue(fits(0, 0, 0))  # a non-class child still advances the cursor
        self.assertTrue(fits(511, 0, 100))
        self.assertFalse(fits(512, 0, 0))
        reserve = self.context["ALL_CHUNK_RESERVE"]
        maximum = self.context["ALL_CHUNK_BYTES"]
        self.assertTrue(fits(1, maximum - reserve - 100, 100))
        self.assertFalse(fits(1, maximum - reserve - 99, 100))
        self.assertFalse(fits(0, 0, 65537))
        self.assertFalse(fits(0, -1, 1))

    def test_aggregate_budget_reserves_final_manifest_and_caps_chunk_count(self):
        fits = self.policy("AllBytesFit", "chunkCount,committedBound,candidateBound")
        total = self.context["ALL_TOTAL_BYTES"]
        reserve = self.context["ALL_FINAL_RESERVE"]
        chunk = self.context["ALL_CHUNK_BYTES"]
        self.assertTrue(fits(63, total - reserve - chunk, chunk))
        self.assertFalse(fits(64, 0, 1))
        self.assertFalse(fits(0, total - reserve - chunk + 1, chunk))
        self.assertFalse(fits(0, 0, chunk + 1))
        self.assertFalse(fits(0, -1, 1))

    def test_chunk_windows_cannot_overlap_gap_skip_nonclass_or_exceed_plan(self):
        valid = self.policy("WindowFollows", "expectedStart,startIndex,nextIndex,planned,rows,nonclass")
        self.assertTrue(valid(0, 0, 4, 7, 3, 1))
        self.assertTrue(valid(4, 4, 7, 7, 2, 1))
        for args in ((4, 3, 7, 7, 3, 1), (4, 5, 7, 7, 2, 0),
                     (4, 4, 8, 7, 4, 0), (4, 4, 4, 7, 0, 0),
                     (0, 0, 4, 7, 3, 0), (0, 0, 513, 700, 513, 0)):
            self.assertFalse(valid(*args), args)

    def test_full_enumeration_requires_all_denominators_and_nonclass_accounting(self):
        complete = self.policy("AllCountsComplete", "advertised,planned,covered,expectedRows,rows,nonclass")
        self.assertTrue(complete(7, 7, 7, 5, 5, 2))
        for args in ((7, 6, 6, 5, 5, 1), (7, 7, 6, 5, 5, 1),
                     (7, 7, 7, 5, 4, 3), (7, 7, 7, 5, 5, 1),
                     (-1, 0, 0, 0, 0, 0)):
            self.assertFalse(complete(*args), args)

    def test_no_automatic_hooks_assets_or_gameplay_mutations(self):
        code = re.sub(r"//[^\n]*", "", self.source)
        self.assertNotRegex(code, r"\bmodded\b|\boverride\b")
        for forbidden in ("OnInit", "OnStart", "CallLater", "CreateObject", "CreateInInventory",
                          "SetQuantity", "SetHealth", "ObjectDelete", "RPC", "GetPlayers"):
            self.assertNotIn(forbidden, code)
        self.assertEqual(body(FILENAME, "Export").count("OpenFile(destination, FileMode.WRITE)"), 1)
        self.assertIn("ActualWorld = actualWorld", code)
        self.assertIn("ActualBuild = actualBuild", code)

    def test_all_index_is_acquired_once_with_duplicate_identity_check(self):
        index = body(FILENAME, "BuildIndexPlan")
        for term in ("ConfigGetChildrenCount", "ConfigGetChildName", "ConfigGetType",
                     "AllChildrenFit", "ALL_PLAN_BYTES", "duplicate_class_identity",
                     "manifest.IndexPlan.Insert", "ALL_MAX_CHILDREN"):
            self.assertIn(term, index)
        collect = body(FILENAME, "CollectAllChunks")
        self.assertNotIn("ConfigGetChildName", collect)
        self.assertNotIn("ConfigGetChildrenCount", collect)
        self.assertIn("manifest.IndexPlan[planIndex]", collect)
        self.assertEqual(collect.count("ReadRow("), 1)
        self.assertIn("candidateRow", collect)

    def test_chunk_commit_accounts_only_after_exact_readback_and_contiguous_cursor(self):
        commit = body(FILENAME, "CommitChunk")
        # Actual native-033 line 810: 'reference' is a native tool qualifier,
        # documented in installed 1_Core/proto/proto.c, not a legal local name.
        self.assertNotRegex(commit, r"\bHCItemCompatibilityChunkReference\s+reference\b",
                            "native-033 Broken expression at reserved reference declarator")
        self.assertIn("WindowFollows", commit)
        self.assertIn("AllBytesFit", commit)
        self.assertLess(commit.index("WriteFreshVerified"), commit.index("manifest.Chunks.Insert"))
        self.assertLess(commit.index("WriteFreshVerified"), commit.index("manifest.Header.VisitedChildren" , commit.index("WriteFreshVerified")))
        writer = body(FILENAME, "WriteFreshVerified")
        self.assertLess(writer.index("FileExist(destination)"), writer.index("FileMode.WRITE"))
        self.assertIn("readback != payload", writer)
        self.assertIn("maxBytes + 1", writer)
        self.assertNotIn("DeleteFile", writer)

    def test_export_all_is_fresh_only_manifest_last_and_explicitly_partial_on_failure(self):
        run = body(FILENAME, "ExportAll")
        self.assertIn("profileOutsideGitConfirmed", run)
        self.assertIn("SafeRunId", run)
        self.assertIn("FileExist(runDirectory)", run)
        self.assertIn("fresh_run_directory_exists", run)
        self.assertIn("s_ExportActive", run)
        self.assertLess(run.index("BuildIndexPlan"), run.index("CollectAllChunks"))
        self.assertLess(run.index("CollectAllChunks"), run.index("WriteFinalManifest"))
        final = body(FILENAME, "WriteFinalManifest")
        self.assertIn("manifest.Header.Partial", final)
        self.assertIn("ALL_MANIFEST_BYTES", final)
        self.assertIn("WriteFreshVerified", final)
        self.assertNotIn("resume", run.lower())
        self.assertNotIn("DeleteFile", self.source)
        self.assertNotIn("FileMode.APPEND", self.source)
        self.assertIn("external_SHA256_required", self.source)


if __name__ == "__main__":
    unittest.main()
