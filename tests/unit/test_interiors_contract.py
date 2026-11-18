"""Synthetic algorithm execution and source contracts; never DayZ runtime proof."""
import itertools
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace
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
    declaration = re.search(r"^\s*(?:(?:static|override|protected)\s+)*\w+(?:<[^>\n]+>)?\s+" + re.escape(name) + r"\([^;\n]*\)\s*\{", text, re.M)
    if not declaration:
        raise AssertionError("missing method declaration: " + name)
    start = declaration.end() - 1
    depth = 1
    end = start + 1
    while depth:
        if text[end] == "{": depth += 1
        if text[end] == "}": depth -= 1
        end += 1
    return text[start + 1:end - 1]


def authored_pool():
    """Restricted execution of the authored collection methods, with synthetic DTOs.

    This is not an Enforce compiler: only the pool's if/foreach/assignment subset
    is admitted, with explicit Python lists instead of engine collections.
    """
    class SyntheticArray(list):
        def Clear(self): self.clear()
        def Insert(self, value): self.append(value)
        def Count(self): return len(self)

    pool = SimpleNamespace()
    namespace = {
        "m_Entries": SyntheticArray(), "m_Opened": False, "HCInteriorRules": SimpleNamespace(
            ReconcilePhase=lambda *args: authored("ReconcilePhase", *args),
            PoolWithinBounds=lambda *args: authored("PoolWithinBounds", *args)),
        "HCInteriorCatalog": SimpleNamespace(ItemAllowed=lambda item: item in ("", "Rag", "Battery9V")),
        "HCInteriorAllocation": lambda: SimpleNamespace(SlotId=0, SiteId="", Item="", Phase=0),
        "HCInteriorSupplyCount": lambda: SimpleNamespace(Allocated=0, Available=0, Reserved=0, Spent=0, Quarantined=0),
    }
    signatures = {"Open": "manifest", "FindSlot": "slot", "Matches": "site", "Reserved": "site",
                  "TryReserve": "site", "Reconcile": "site,phase", "Count": "item"}
    for name, params in signatures.items():
        body = re.sub(r"//[^\n]*", "", method_body("HCInteriorSearchPool.c", name))
        statements = re.split(r"([{};])", body)
        indent = 1
        lines = []
        for part in statements:
            part = part.strip()
            if not part or part == ";": continue
            if part == "{": indent += 1; continue
            if part == "}": indent -= 1; continue
            part = part.replace("&&", " and ").replace("||", " or ")
            part = re.sub(r"!(?!=)", "not ", part)
            for native, python in [("null", "None"), ("true", "True"), ("false", "False")]:
                part = re.sub(r"\b" + native + r"\b", python, part)
            part = re.sub(r"\bnew (HCInteriorAllocation|HCInteriorSupplyCount)\b", r"\1()", part)
            part = re.sub(r"\b\w+ (\w+) =", r"\1 =", part)
            part = re.sub(r"^(?:int|bool) (\w+)$", r"\1 = 0", part)
            part = re.sub(r"([\w.]+)\+\+", r"\1 += 1", part)
            part = re.sub(r"([\w.]+)\.Count\(\)", r"len(\1)", part)
            part = re.sub(r"([\w.]+)\.Length\(\)", r"len(\1)", part)
            part = re.sub(r"^foreach \(\w+ (\w+) : (.*)\)$", r"for \1 in \2:", part)
            part = re.sub(r"^if \((.*)\)\s+(.*)$", r"if \1: \2", part, flags=re.S)
            lines.append("    " * indent + part.replace("\n", " "))
        code = "def " + name + "(" + params + "):\n    global m_Opened\n" + "\n".join(lines)
        exec(compile(code, "authored-enforce-pool:" + name, "exec"), namespace)
        setattr(pool, name, namespace[name])
    return pool


class InteriorsContractTests(unittest.TestCase):
    def test_native_owned_keyword_is_never_an_interior_variable_or_parameter(self):
        for path in SRC.glob("*.c"):
            code = re.sub(r"//[^\n]*", "", path.read_text())
            self.assertNotRegex(code, r"\b(?:int|Object)\s+owned\b", path.name)

    def test_native_compiler_reported_type_names_are_not_interior_identifiers(self):
        # Native names protected by this regression; raw compiler logs stay local.
        reserved = {"World", "Slot"}
        for path in SRC.glob("*.c"):
            declarations = re.findall(r"^\s*(?:(?:protected|static|const|ref)\s+)*\w+(?:<[^;\n]+>)?\s+(\w+)\s*(?:[;=]|\()", path.read_text(), re.M)
            self.assertFalse(reserved.intersection(declarations), path.name)

    def test_completion_interrupted_allocation_cannot_be_resumed_by_resetting_site_phase(self):
        pool = authored_pool()
        manifest = SimpleNamespace(SchemaVersion=1, Assignments=[SimpleNamespace(SlotId=0, InstanceId="SYNTHETIC_A", Item="Rag")])
        self.assertTrue(pool.Open(manifest))
        site = SimpleNamespace(SlotId=0, Id="SYNTHETIC_A_storage_v1", Item="Rag", Phase=0)
        self.assertTrue(pool.TryReserve(site))
        site.Phase = 1
        self.assertTrue(pool.Reserved(site))
        self.assertEqual(pool.Reconcile(site, 3), 3)
        site.Phase = 1  # stale action data must not revive an interrupted grant
        self.assertFalse(pool.Reserved(site))
        self.assertIn("m_Pool.Reserved(site)", method_body("HCInteriorStore.c", "BeginGrant"))
        self.assertIn("m_Pool.Reserved(site)", method_body("HCInteriorStore.c", "Finish"))

    def test_completion_journal_omitted_version_is_not_accepted_from_dto_defaults(self):
        source = (SRC / "HCInteriorSearchPool.c").read_text().split("class HCInteriorJournalIdentity", 1)[1].split("}", 1)[0]
        defaults = {}
        for field in ("SchemaVersion", "SourceSchema"):
            match = re.search(r"int " + field + r"(?: = (\d+))?;", source)
            self.assertIsNotNone(match)
            defaults[field] = int(match[1] or 0)
        self.assertFalse(authored("JournalVersionAccepted", defaults["SchemaVersion"], defaults["SourceSchema"]))
        for schema, origin in itertools.product(range(4), repeat=2):
            self.assertEqual(authored("JournalVersionAccepted", schema, origin), (schema, origin) == (2, 1))

    def test_completion_actual_pool_cannot_reopen_to_refund_spent_units(self):
        manifest = SimpleNamespace(SchemaVersion=1, Assignments=[SimpleNamespace(SlotId=0, InstanceId="SYNTHETIC_A", Item="Rag")])
        pool = authored_pool()
        self.assertTrue(pool.Open(manifest))
        site = SimpleNamespace(SlotId=0, Id="SYNTHETIC_A_storage_v1", Item="Rag", Phase=0)
        self.assertTrue(pool.TryReserve(site))
        self.assertEqual(pool.Reconcile(site, 2), 2)
        self.assertFalse(pool.Open(manifest))
        self.assertFalse(pool.TryReserve(site))

    def test_completion_actual_pool_two_consumers_cannot_share_one_unit(self):
        pool = authored_pool()
        manifest = SimpleNamespace(SchemaVersion=1, Assignments=[SimpleNamespace(SlotId=0, InstanceId="SYNTHETIC_A", Item="Rag")])
        self.assertTrue(pool.Open(manifest))
        a = SimpleNamespace(SlotId=0, Id="SYNTHETIC_A_storage_v1", Item="Rag", Phase=0)
        b = SimpleNamespace(**vars(a))
        self.assertTrue(pool.TryReserve(a))
        self.assertFalse(pool.TryReserve(b))
        self.assertEqual(pool.Reconcile(a, 2), 2)
        self.assertFalse(pool.TryReserve(b))
        count = pool.Count("Rag")
        self.assertEqual((count.Allocated, count.Available, count.Reserved, count.Spent, count.Quarantined), (1, 0, 0, 1, 0))

    def test_completion_actual_pool_restart_reconciles_missing_building_escrow(self):
        manifest = SimpleNamespace(SchemaVersion=1, Assignments=[SimpleNamespace(SlotId=i, InstanceId="SYNTHETIC_" + str(i), Item="Rag") for i in range(4)])
        pool = authored_pool()
        self.assertTrue(pool.Open(manifest))
        for slot, phase in enumerate([2, 3, 3, 0]):
            site = SimpleNamespace(SlotId=slot, Id="SYNTHETIC_" + str(slot) + "_storage_v1", Item="Rag", Phase=0)
            self.assertEqual(pool.Reconcile(site, phase), phase)
        count = pool.Count("Rag")
        self.assertEqual((count.Allocated, count.Available, count.Spent, count.Quarantined), (4, 1, 1, 2))
        held = SimpleNamespace(SlotId=1, Id="SYNTHETIC_1_storage_v1", Item="Rag", Phase=0)
        self.assertFalse(pool.TryReserve(held))
        self.assertEqual(pool.Reconcile(held, 0), 3)

    def test_completion_actual_pool_rejects_overquota_and_aliased_owners(self):
        for count in (0, 5, 13):
            manifest = SimpleNamespace(SchemaVersion=1, Assignments=[SimpleNamespace(SlotId=i, InstanceId="SYNTHETIC_" + str(i), Item="Rag") for i in range(count)])
            self.assertFalse(authored_pool().Open(manifest))
        for assignments in (
            [SimpleNamespace(SlotId=0, InstanceId="A", Item="Rag"), SimpleNamespace(SlotId=0, InstanceId="B", Item="Rag")],
            [SimpleNamespace(SlotId=0, InstanceId="A", Item="Rag"), SimpleNamespace(SlotId=1, InstanceId="A", Item="Rag")],
            [SimpleNamespace(SlotId=0, InstanceId="A", Item="M4A1")],
        ):
            self.assertFalse(authored_pool().Open(SimpleNamespace(SchemaVersion=1, Assignments=assignments)))

    def test_completion_recovery_crash_cuts_never_replay_a_grant(self):
        cases = json.loads((FIX.parent / "interiors-completion-synthetic.json").read_text())
        for case in cases["journal"]:
            with self.subTest(case=case["given"]):
                self.assertEqual(authored("RecoverJournal", *case["flags"]), case["then_phase"])

    def test_completion_pool_conserves_units_across_retirement_and_restart(self):
        # Synthetic owner phases; policy itself is executed from authored Enforce.
        for before, recovered in itertools.product(range(4), repeat=2):
            after = authored("ReconcilePhase", before, recovered)
            if before != 0:
                self.assertNotEqual(after, 0)
            if before == recovered:
                self.assertEqual(after, before)
        for count in range(-1, 15):
            self.assertEqual(authored("PoolWithinBounds", count, 4, 2), 1 <= count <= 12)
        self.assertFalse(authored("PoolWithinBounds", 12, 5, 2))
        self.assertFalse(authored("PoolWithinBounds", 12, 4, 3))
        self.assertFalse(authored("PoolWithinBounds", 12, -1, 0))

    def test_completion_version_migration_is_explicit_forward_only(self):
        self.assertTrue(authored("MigrationAllowed", 1, 2, True, True))
        for source, target, approval, exact in itertools.product(range(4), range(4), [False, True], [False, True]):
            if (source, target, approval, exact) != (1, 2, True, True):
                self.assertFalse(authored("MigrationAllowed", source, target, approval, exact))

    def test_completion_recovery_rejects_every_inconsistent_journal(self):
        for flags in itertools.product([False, True], repeat=6):
            claim, valid_claim, attempt, valid_attempt, result, valid_result = flags
            phase = authored("RecoverJournal", *flags, 2, 2)
            if not claim and (attempt or result):
                self.assertEqual(phase, 3)
            if claim and not valid_claim:
                self.assertEqual(phase, 3)
            if claim and not result:
                self.assertEqual(phase, 3)
            if phase == 0:
                self.assertFalse(claim or attempt or result)

    def test_completion_orphan_recovery_does_not_adopt_foreign_props(self):
        self.assertEqual(authored("OrphanDecision", True, 0, 0, True), 0)
        self.assertEqual(authored("OrphanDecision", True, 1, 1, True), 1)
        for bounded, matches, owners, exact in itertools.product([False, True], range(4), range(4), [False, True]):
            decision = authored("OrphanDecision", bounded, matches, owners, exact)
            if decision == 1:
                self.assertEqual((bounded, matches, owners, exact), (True, 1, 1, True))
            if not bounded or matches > 1:
                self.assertEqual(decision, 3)

    def test_completion_shared_pool_reconciles_every_slot_before_search(self):
        opened = method_body("HCInteriorStore.c", "Open")
        self.assertIn("OpenJournal", opened)
        self.assertIn("ReconcileAll", opened)
        body = method_body("HCInteriorStore.c", "ReconcileAll")
        self.assertIn("slot < 12", body)
        self.assertIn("orphan journal", body)
        reserve = method_body("HCInteriorStore.c", "Reserve")
        self.assertIn("m_Pool.TryReserve", reserve)
        self.assertIn("ResultPath", reserve)
        self.assertIn("AttemptPath", reserve)

    def test_completion_routes_inventory_only_through_the_economy(self):
        body = method_body("HCInteriorModule.c", "CommitSearch")
        self.assertEqual(body.count("m_Economy.Grant("), 1)
        self.assertNotIn("CreateInInventory", body)
        self.assertNotIn("m_Store.BeginGrant", body)
        self.assertNotIn("m_Store.Finish", body)
        self.assertIn("GetPersistentID", (SRC / "HCInteriorStore.c").read_text())

    def test_completion_migration_preserves_legacy_paths_and_bindings(self):
        body = method_body("HCInteriorStore.c", "OpenJournal")
        self.assertIn("MigrationAllowed", body)
        self.assertIn("MigrateLegacyJournal", body)
        self.assertIn("journal-v2.json", body)
        self.assertIn("WriteNew", body)
        source = (SRC / "HCInteriorStore.c").read_text()
        self.assertNotIn("DeleteFile", source)
        self.assertNotIn("CopyFile", source)
        self.assertIn("result.PlayerId == claim.PlayerId", source)

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
        self.assertLess(body.index("site.Phase = 1"), body.index("m_Economy.Grant("))
        self.assertIn("site.Phase = 3", body)
        self.assertEqual(body.count("m_Economy.Grant("), 1)
        self.assertNotIn("CreateInInventory", body)
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

    def test_refused_or_completed_search_has_honest_native_feedback(self):
        body = method_body("HCInteriorModule.c", "CommitSearch")
        self.assertIn('ActionRefusalMessage(data, HCRefusal.SUPPLY, "Search unavailable: supply, inventory or service changed.")', body)
        self.assertIn('MessageStatus("Search complete.")', body)
        self.assertIn('ActionRefusalMessage(data, HCRefusal.STORAGE, "Search stopped; this storage is unavailable.")', body)

    def test_legacy_allocation_is_bounded_and_new_layouts_allocate_no_items(self):
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
        self.assertNotIn("HCInteriorRules.Allocation", body)
        self.assertNotIn("assignment.Item =", body)

    def test_identity_and_candidate_collisions_do_not_depend_on_object_order(self):
        source = (SRC / "HCInteriorCatalog.c").read_text()
        self.assertIn('Type + "_" + HCInteriorRules.TransformKey(Position, Orientation)', source)
        self.assertIn('SlotId.ToString()', source)
        config = method_body("HCInteriorModule.c", "ValidateConfig")
        self.assertIn("previous.Key() == candidate.Key()", config)
        self.assertIn("previous.SlotId == candidate.SlotId", config)
        resolved = method_body("HCInteriorModule.c", "ResolveBuilding")
        self.assertIn("if (found) return null", resolved)
        self.assertIn("objects.Count() > 256", resolved)

    def test_server_measures_duration_and_rechecks_empty_hands(self):
        body = method_body("HCInteriorModule.c", "ValidateTarget")
        self.assertIn("GetEntityInHands()", body)
        commit = method_body("HCInteriorModule.c", "CommitSearch")
        self.assertIn("GetTickTime() - site.StartedAt < 5.5", commit)
        begin = method_body("HCInteriorModule.c", "BeginSearch")
        self.assertIn("site.StartedAt = GetGame().GetTickTime()", begin)

    def test_both_independent_acceptance_gates_report_operator_reasons(self):
        start = method_body("HCInteriorModule.c", "OnStart")
        self.assertIn("collision/nav/replication proof", start)
        self.assertIn("durable commit/CE/two-client proof", start)


class FixupPlacementTests(unittest.TestCase):
    """T014/INT-005: execute placement batches with explicit SYNTHETIC players."""

    def placement(self, count=12):
        from tests.unit import test_search_economy_houses as houses
        source = (SRC / 'HCInteriorTemplatePlacement.c').read_text()
        # ClippingInfo's fixed-size output array is an unused native boundary here.
        match = re.search(r'    static void LogPropBox\([^)]*\)\s*\{', source)
        end = houses.match_brace(source, match.end() - 1)
        source = source[:match.start()] + source[end + 1:]
        source = source.replace('int firstRow = 0', 'int firstRow')
        class NativeArray(houses.EArray):
            def Remove(self, index):
                # Installed EnScript.c:463 swaps in the last element.
                self[index] = self[-1]
                self.pop()
        rows = NativeArray(SimpleNamespace(Position=[100. * i, 0., 0.],
                            Props=houses.EArray([1])) for i in range(count))
        players, placed, logs = houses.EArray(), [], []
        env = dict(EArray=NativeArray, HMap=houses.HMap, tostr=str,
                   GetGame=lambda: SimpleNamespace(GetPlayers=lambda out: out.extend(players)),
                   HCInteriorTemplates=SimpleNamespace(Loaded=lambda: True,
                       FurnishRows=lambda: rows, AsVector=lambda v: v),
                   HCInteriorRules=SimpleNamespace(PlacementAdmitted=lambda: True),
                   Math=SimpleNamespace(Min=min), Print=logs.append,
                   vector=SimpleNamespace(DistanceSq=lambda a,b: sum((x-y)**2 for x,y in zip(a,b))))
        for code in houses.Translator(source).classes():
            exec(code, env)
        api = env['HCInteriorTemplatePlacement']
        module = SimpleNamespace(PlaceCandidate=lambda row, settings: placed.append(row))
        def batch(first):
            api.Place(module, SimpleNamespace(), houses.EArray(), first)
        return api, rows, players, placed, logs, batch

    def test_player_within_thirty_metres_defers_only_that_row_until_clear(self):
        api, rows, players, placed, logs, batch = self.placement()
        # Includes a null handle and a second player: every player must be checked.
        players.extend([None, SimpleNamespace(GetPosition=lambda: [900., 0., 0.]),
                        SimpleNamespace(GetPosition=lambda: [30., 0., 0.])])
        batch(0)
        self.assertNotIn(rows[0], placed)
        self.assertNotIn(rows[9], placed)
        self.assertEqual(8, len(placed))
        batch(10)
        self.assertEqual(10, len(placed))
        self.assertFalse(api.s_Started)
        batch(12)
        self.assertEqual(10, len(placed))
        players.clear()
        batch(12)
        self.assertEqual(12, len(placed))
        self.assertTrue(all(placed.count(row) == 1 for row in rows))
        self.assertTrue(api.s_Started)
        self.assertEqual(1, sum('templates placement placed=' in line for line in logs))
        batch(12)
        self.assertEqual(12, len(placed))
        api.ResetPlacement()
        self.assertFalse(api.s_Started)
        self.assertEqual(0, api.s_Deferred.Count())

    def test_deferred_retries_keep_ten_row_budget_and_reach_all_rows(self):
        api, rows, players, placed, logs, batch = self.placement(25)
        players.extend(SimpleNamespace(GetPosition=lambda row=row: row.Position) for row in rows)
        for first in (0, 10, 20):
            batch(first)
        self.assertEqual([], placed)
        # A blocked first retry batch must not starve the other deferred rows.
        players[:] = players[:10]
        for _ in range(3):
            before = len(placed)
            batch(25)
            self.assertLessEqual(len(placed) - before, 10)
        self.assertEqual(15, len(placed))
        players.clear()
        batch(25)
        self.assertEqual(25, len(placed))
        self.assertTrue(api.s_Started)

    def test_player_outside_thirty_metres_does_not_defer(self):
        api, rows, players, placed, logs, batch = self.placement(1)
        players.append(SimpleNamespace(GetPosition=lambda: [30.001, 0., 0.]))
        batch(0)
        self.assertEqual([rows[0]], placed)
        self.assertTrue(api.s_Started)
