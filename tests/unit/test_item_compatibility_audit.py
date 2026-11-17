"""#52/#56 authored-policy execution and source contracts, not native acceptance.

Fixtures are synthetic. Native merged-config invocation belongs to the coordinator.
Only the new diagnostic source is read; no game files or exports are fixtures.

Actual TDD, 2026-11-16:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_item_compatibility_audit -v
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
Native-031 numeric type observation and completed root enumeration remain pending.
"""
import math
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

try:
    from .test_crafting_completion import body
except ImportError:
    from test_crafting_completion import body

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
        self.assertIn('roots.Insert("CfgWeapons")', scan)
        self.assertIn('roots.Insert("CfgVehicles")', scan)
        for api in ("ConfigGetChildrenCount", "ConfigGetChildName", "ConfigGetType"):
            self.assertIn(api, scan)
        for prohibited in ("displayName", "IsKindOf", "pilot", ".Contains("):
            self.assertNotIn(prohibited, scan)
        self.assertIn("MAX_VISITED_FACTOR", scan)
        self.assertIn("FitsRowBudget", scan)

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

    def test_no_automatic_hooks_assets_or_gameplay_mutations(self):
        code = re.sub(r"//[^\n]*", "", self.source)
        self.assertNotRegex(code, r"\bmodded\b|\boverride\b")
        for forbidden in ("OnInit", "OnStart", "CallLater", "CreateObject", "CreateInInventory",
                          "SetQuantity", "SetHealth", "ObjectDelete", "RPC", "GetPlayers"):
            self.assertNotIn(forbidden, code)
        self.assertEqual(code.count("OpenFile(destination, FileMode.WRITE)"), 1)
        self.assertIn("ActualWorld = actualWorld", code)
        self.assertIn("ActualBuild = actualBuild", code)


if __name__ == "__main__":
    unittest.main()
