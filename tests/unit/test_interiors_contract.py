"""Synthetic algorithm execution and source contracts; never DayZ runtime proof."""
import itertools
import json
import math
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "mods/HollowCountry/scripts/4_World/Interiors"
FIX = ROOT / "tests/fixtures/runtime/interiors-synthetic.json"


def authored(name, *args):
    """Execute the restricted scalar Enforce algorithm, not a Python reimplementation.

    Only scalar expressions, if/return, and local assignments are supported.
    Fails on unsupported syntax. Engine calls, objects and persistence are excluded.
    """
    source = (SRC / "HCInteriorRules.c").read_text()
    match = re.search(r"static (?:int|bool|float) " + name + r"\(([^)]*)\)\s*\{([^{}]*)\}", source)
    if not match:
        raise AssertionError("missing executable scalar algorithm: " + name)
    params = [p.strip().split()[-1] for p in match[1].split(",") if p.strip()]
    lines = []
    for statement in match[2].split(";"):
        statement = re.sub(r"//[^\n]*", "", statement).strip()
        if not statement:
            continue
        statement = re.sub(r"\b(int|float|bool) (\w+) =", r"\2 =", statement)
        statement = statement.replace("Math.Floor", "math.floor").replace("Math.AbsInt", "abs")
        statement = statement.replace("&&", " and ").replace("||", " or ")
        statement = re.sub(r"!(?!=)", "not ", statement)
        statement = re.sub(r"\btrue\b", "True", statement)
        statement = re.sub(r"\bfalse\b", "False", statement)
        statement = re.sub(r"if \((.*)\)\s*return (.*)", r"if \1: return \2", statement, flags=re.S)
        lines.append("    " + statement.replace("\n", " "))
    code = "def algorithm(" + ",".join(params) + "):\n" + "\n".join(lines)
    namespace = {"math": math, "abs": abs, "Quantize": lambda value: authored("Quantize", value)}
    exec(compile(code, "authored-enforce:" + name, "exec"), namespace)
    return namespace["algorithm"](*args)


def method_body(filename, name):
    text = (SRC / filename).read_text()
    start = text.index(name + "(")
    start = text.index("{", start)
    depth = 1
    end = start + 1
    while depth:
        if text[end] == "{": depth += 1
        if text[end] == "}": depth -= 1
        end += 1
    return text[start + 1:end - 1]


class InteriorsContractTests(unittest.TestCase):
    def test_authored_quantization_signed_and_boundary(self):
        for value, expected in json.loads(FIX.read_text())["quantize"]:
            self.assertEqual(authored("Quantize", value), expected)

    def test_authored_yaw_identity_normalizes_full_turns(self):
        for value in [-720, -360, 0, 360, 720]:
            self.assertEqual(authored("Yaw", value), 0)
        self.assertEqual(authored("Yaw", -90), 27000)

    def test_authored_assignment_is_bounded_and_spans_all_layouts(self):
        picks = {authored("Layout", x, 120, 800, 0, 17) for x in range(300)}
        self.assertEqual(picks, {0, 1, 2})
        for x in [-1536000, 0, 1536000]:
            self.assertIn(authored("Layout", x, -200, x, 35999, 17), range(3))

    def test_authored_claim_has_no_refill_or_rollback_transition(self):
        for before, after, expected in json.loads(FIX.read_text())["transitions"]:
            self.assertEqual(authored("Transition", before, after), expected)
        for before, after in itertools.product(range(-1, 5), repeat=2):
            if before in (2, 3):
                self.assertFalse(authored("Transition", before, after))

    def test_authored_recovery_never_reissues_ambiguous_claim(self):
        for exists, parses, schema, phase in itertools.product([False, True], [False, True], [0, 1, 2], range(4)):
            result = authored("Recover", exists, parses, schema, phase)
            if exists:
                self.assertIn(result, (2, 3))
            else:
                self.assertEqual(result, 0)
        self.assertEqual(authored("Recover", True, True, 1, 2), 2)
        self.assertEqual(authored("Recover", True, False, 1, 2), 3)

    def test_authored_authority_requires_every_gate(self):
        self.assertTrue(authored("MaySearch", *([True] * 7)))
        for i in range(7):
            flags = [True] * 7
            flags[i] = False
            self.assertFalse(authored("MaySearch", *flags))

    def test_catalog_has_three_native_layouts_two_histories(self):
        source = (SRC / "HCInteriorCatalog.c").read_text()
        self.assertEqual(len(re.findall(r'layout.Id = "', source)), 3)
        self.assertIn('"family"', source)
        self.assertIn('"ransacked"', source)
        self.assertIn('Land_House_1W01', source)
        self.assertNotIn('.p3d', source)

    def test_client_hooks_preview_without_settings_or_profile_io(self):
        source = (SRC / "HCInteriorAction.c").read_text()
        self.assertIn("modded class ActionConstructor", source)
        self.assertIn("actions.Insert(HCActionSearchInterior)", source)
        self.assertIn("override void SetActions(out TInputActionMap InputActionMap)", source)
        preview = method_body("HCInteriorAction.c", "Preview")
        for forbidden in ["HCServer", "JsonFileLoader", "$profile", "HCSettings"]:
            self.assertNotIn(forbidden, preview)
        self.assertIn("GetComponentIndex", preview)
        self.assertIn("CCTCursor", source)

    def test_server_uses_authored_anchor_not_client_cursor_for_commit(self):
        body = method_body("HCInteriorModule.c", "ValidateTarget")
        self.assertIn("GetComponentIndex", body)
        self.assertIn("DayZPhysics.RaycastRV", body)
        self.assertIn("vector.DistanceSq", body)
        self.assertNotIn("GetCursorHitPos", body)
        self.assertIn("hits[0] != site.Target", body)
        self.assertIn("HCServer.Get().GetSettings()", (SRC / "HCInteriorModule.c").read_text())

    def test_claim_marker_precedes_inventory_and_never_retries_output(self):
        body = method_body("HCInteriorModule.c", "CommitSearch")
        self.assertLess(body.index("FindFirstFreeLocationForNewEntity"), body.index("m_Store.Reserve"))
        self.assertLess(body.index("m_Store.Reserve"), body.index("CreateInInventory"))
        self.assertIn("site.Phase = 3", body)
        self.assertEqual(body.count("CreateInInventory"), 1)
        self.assertNotIn("CreateObject", body)
        store = (SRC / "HCInteriorStore.c").read_text()
        self.assertNotIn("DeleteFile", store)
        self.assertNotIn("CopyFile", store)
        self.assertIn("FileExist(path)", store)

    def test_bounded_manifest_registration_and_default_off_acceptance(self):
        source = (SRC / "HCInteriorModule.c").read_text()
        self.assertIn("super.RegisterModules()", source)
        self.assertIn("Register(new HCInteriorsModule)", source)
        self.assertIn("MaxActiveInteriors", source)
        self.assertIn("MaxPropsPerInterior", source)
        self.assertIn("GetObjectsAtPosition3D", source)
        self.assertNotIn("GetPlayers(", source)
        self.assertIn("m_NextCandidate++", source)
        rules = (SRC / "HCInteriorRules.c").read_text()
        self.assertFalse(authored("PlacementAccepted"))
        self.assertFalse(authored("SearchAccepted"))
        self.assertIn("DIAG_DEVELOPER", source)

    def test_native_self_tests_call_real_algorithm_without_spawn(self):
        source = (SRC / "HCInteriorSelfTests.c").read_text()
        for call in ["HCInteriorRules.Quantize", "HCInteriorRules.Recover", "HCInteriorRules.Transition", "HCInteriorRules.Layout"]:
            self.assertIn(call, source)
        self.assertNotIn("CreateObject", source)
        self.assertNotIn("CreateInInventory", source)

    def test_server_condition_never_uses_cursor_preview(self):
        body = method_body("HCInteriorAction.c", "ActionCondition")
        self.assertIn("if (!GetGame().IsServer()) return Preview", body)
        self.assertNotIn("!Preview", body)

    def test_persistence_write_and_read_are_bounded_and_no_stale_restore(self):
        source = (SRC / "HCInteriorStore.c").read_text()
        self.assertIn("ReadFile(handle, text, 32769)", source)
        self.assertIn("text.Length() >= 32768", source)
        self.assertIn("manifest.backup.json", source)
        opened = method_body("HCInteriorStore.c", "Open")
        self.assertIn("return left == right", opened)
        self.assertNotIn("DeleteFile", opened)
        reserve = method_body("HCInteriorStore.c", "Reserve")
        self.assertLess(reserve.index("site.Phase = 1"), reserve.index("WriteNew"))
        self.assertIn('return Fail("reservation write/readback failed', reserve)
        self.assertIn("m_Fault = true", method_body("HCInteriorStore.c", "Fail"))

    def test_no_inventory_mutation_until_duration_and_exact_lock_owner(self):
        source = (SRC / "HCInteriorAction.c").read_text()
        self.assertIn("CAContinuousTime(6.0)", source)
        for hook in ["OnStartServer", "OnEndServer"]:
            self.assertNotIn("CommitSearch", method_body("HCInteriorAction.c", hook))
        body = method_body("HCInteriorModule.c", "CanContinue")
        self.assertIn("action.Site.Owner == data", body)
        self.assertIn("action.Site.Deadline", body)
        begin = method_body("HCInteriorModule.c", "BeginSearch")
        self.assertIn("site.Owner = data", begin)
        commit = method_body("HCInteriorModule.c", "CommitSearch")
        self.assertIn("!CanContinue(data)", commit)

    def test_furnishings_are_created_during_startup_not_live_ticks(self):
        self.assertNotIn("PlaceCandidate(", method_body("HCInteriorModule.c", "OnTick"))
        self.assertIn("PlaceCandidate(", method_body("HCInteriorModule.c", "OnStart"))

    def test_full_inventory_and_empty_results_have_native_feedback(self):
        body = method_body("HCInteriorModule.c", "CommitSearch")
        self.assertIn('MessageStatus("Not enough inventory space.")', body)
        self.assertIn('MessageStatus("The storage is empty.")', body)

    def test_authored_allocation_never_exceeds_finite_supplementary_quotas(self):
        for layout in range(-1, 5):
            for rags in range(7):
                for batteries in range(5):
                    allocation = authored("Allocation", layout, rags, batteries)
                    self.assertIn(allocation, (0, 1, 2))
                    if rags >= 4: self.assertNotEqual(allocation, 1)
                    if batteries >= 2: self.assertNotEqual(allocation, 2)
                    if layout not in (0, 1): self.assertEqual(allocation, 0)
        rags = batteries = 0
        for layout in [0, 1, 2] * 30:
            allocation = authored("Allocation", layout, rags, batteries)
            rags += allocation == 1
            batteries += allocation == 2
        self.assertEqual((rags, batteries), (4, 2))
        body = method_body("HCInteriorModule.c", "AllocateManifest")
        self.assertIn("HCInteriorRules.Allocation", body)

    def test_identity_and_candidate_collisions_do_not_depend_on_object_order(self):
        source = (SRC / "HCInteriorCatalog.c").read_text()
        self.assertIn('Type + "_" + HCInteriorRules.TransformKey(Position, Orientation)', source)
        self.assertIn('Slot.ToString()', source)
        config = method_body("HCInteriorModule.c", "ValidateConfig")
        self.assertIn("previous.Key() == candidate.Key()", config)
        self.assertIn("previous.Slot == candidate.Slot", config)
        resolved = method_body("HCInteriorModule.c", "ResolveBuilding")
        self.assertIn("if (found) return null", resolved)
        self.assertIn("objects.Count() > 256", resolved)

    def test_server_measures_duration_and_rechecks_empty_hands(self):
        body = method_body("HCInteriorModule.c", "ValidateTarget")
        self.assertIn("GetEntityInHands()", body)
        commit = method_body("HCInteriorModule.c", "CommitSearch")
        self.assertIn("GetTickTime() - site.StartedAt < 6.0", commit)
        begin = method_body("HCInteriorModule.c", "BeginSearch")
        self.assertIn("site.StartedAt = GetGame().GetTickTime()", begin)

    def test_both_independent_acceptance_gates_report_operator_reasons(self):
        start = method_body("HCInteriorModule.c", "OnStart")
        self.assertIn("collision/nav/replication proof", start)
        self.assertIn("durable commit/CE/two-client proof", start)
