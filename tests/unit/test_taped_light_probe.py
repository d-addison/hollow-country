"""Offline stager/hook tests for the taped-light geometry probe; SYNTHETIC fixtures only.

Nothing here proves how DayZ spawns, attaches or presents anything. The generated Enforce
hook is only checked structurally and against compile-shape rules already observed natively
(see test_script_syntax/test_script_identifiers). Runtime acceptance stays PENDING until a
native run produces observations that tools/audit/taped_light_report.py can join.

Actual TDD 2026-11-17:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_probe -v
RED: ModuleNotFoundError for tools.setup.taped_light_probe (whole module missing).
"""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from tests.unit import test_script_identifiers as ident
from tests.unit import test_script_syntax as syn
from tools.audit import taped_light_report as report
from tools.setup import taped_light_probe as probe

ROOT = Path(__file__).resolve().parents[2]
PROBE_SOURCE = ROOT / "tools/setup/taped_light_probe.py"
STOCK_INIT = (b"// SYNTHETIC mission, not purchased game source\r\n"
              b"void main() {}\r\nclass CustomMission: MissionServer {}\r\n"
              b"Mission CreateCustomMission(string path)\r\n{\r\n"
              b"    return new CustomMission();\r\n}\r\n")
SYNTH_BE = b"SYNTHETIC-BATTLEYE"
SYNTH_BE_SHA = hashlib.sha256(SYNTH_BE).hexdigest()
EXE_SHA = "987fbc47bab1dab37f74d7f700aa2e5b6af936a7181a62f5ba9f0090aebba805"
WINDOWS_ROOT = r"D:\HollowCountryLocal\taped-light-test"
SLOTS = ["helmetFlashlight", "pistolFlashlight", "weaponFlashlight"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def host(name, group, root="CfgWeapons", slots=()):
    return {"id": root + ":" + name, "root": root, "name": name, "role": "gun_candidate", "group": group,
            "native_light_slots": list(slots), "scope": 2,
            "exclusion_reasons": ["scope_below_2"] if group == "excluded" else []}


def light(name, group, role, slots=()):
    return {"id": "CfgVehicles:" + name, "root": "CfgVehicles", "name": name, "group": group,
            "native_slots": list(slots), "probe_role": role, "exclusion_reasons": []}


def classification(hosts=None, lights=None):
    hosts = hosts if hosts is not None else [
        host("AK74", "slot_host", slots=["weaponFlashlight"]), host("Glock19", "slot_host", slots=["pistolFlashlight"]),
        host("PlainBag", "no_slot_host", "CfgVehicles"), host("PlainHat", "no_slot_host", "CfgVehicles"),
        host("RifleBase", "excluded")]
    lights = lights if lights is not None else [
        light("UniversalLight", "mount_light", "representative", ["helmetFlashlight", "weaponFlashlight"]),
        light("TLRLight", "mount_light", "representative", ["pistolFlashlight"]),
        light("Flashlight", "handheld_battery_light", "control"), light("Torch", "flame_or_chemical_light", "")]
    return {"schema_version": 1, "kind": "flashlight_host_light_classification", "native_light_slots": SLOTS,
            "probe_lights": sorted(l["name"] for l in lights if l["probe_role"]), "hosts": hosts, "lights": lights,
            "denominators": {}, "acceptance": "PENDING"}


def make_source_runtime(root):
    """Synthetic stand-in for the verified runtime's stock-backup and launch plan."""
    mission = root / "stock-backup/mpmissions/dayzOffline.chernarusplus"
    (mission / "db").mkdir(parents=True)
    files = {"init.c": STOCK_INIT, "db/types.xml": b"<types>synthetic</types>\n",
             "mapgroupproto.xml": b"<prototype/>\n"}
    plan_files = []
    for name, data in sorted(files.items()):
        (mission / name).write_bytes(data)
        plan_files.append({"path": name, "sha256": sha(data)})
    config = b'hostname = "SYNTHETIC";\r\n'
    (root / "serverDZ.cfg").write_bytes(config)
    (root / "battleye").mkdir()
    (root / "battleye/BEServer_x64.dll").write_bytes(SYNTH_BE)
    (root / "launch-plan.json").write_text(json.dumps(
        {"schema_version": 1, "status": "staged-only-not-launched", "config_sha256": sha(config),
         "mission_files": plan_files}))
    return root


class Workspace(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = make_source_runtime(self.root / "vanilla")
        self.dest = self.root / "taped-light-test"
        self.classification = classification()

    def kw(self, **extra):
        """Internal test-only parent mapping; the production CLI has no such switch."""
        base = {"battleye_sha256": SYNTH_BE_SHA, "_wsl_parent": self.root}
        base.update(extra)
        return base

    def stage(self, **extra):
        return probe.stage(self.source, self.dest, self.classification, **self.kw(**extra))


class TargetSelectionTests(unittest.TestCase):
    def test_only_live_slot_and_no_slot_hosts_are_probed_and_exclusions_are_counted(self):
        targets = probe.select_targets(classification())
        self.assertEqual(["AK74", "Glock19", "PlainBag", "PlainHat"], [h["class"] for h in targets["hosts"]])
        self.assertEqual(["slot_host", "slot_host", "no_slot_host", "no_slot_host"],
                         [h["group"] for h in targets["hosts"]])
        self.assertEqual(1, targets["excluded_not_probed"])
        self.assertEqual(["Flashlight", "TLRLight", "UniversalLight"], targets["lights"])
        self.assertEqual(SLOTS, targets["slots"])

    def test_selection_is_deterministic_for_shuffled_input(self):
        shuffled = classification()
        shuffled["hosts"].reverse()
        self.assertEqual(probe.select_targets(classification()), probe.select_targets(shuffled))

    def test_hard_class_cap_is_enforced_before_anything_else(self):
        many = [host("Gun%03d" % i, "no_slot_host") for i in range(probe.HARD_CAP)]
        self.assertEqual(probe.HARD_CAP, len(probe.select_targets(classification(many))["hosts"]))
        with self.assertRaises(ValueError):
            probe.select_targets(classification(many + [host("OneTooMany", "no_slot_host")]))
        self.assertLessEqual(probe.HARD_CAP, 600)

    def test_invalid_classifications_are_refused(self):
        cases = {"kind": dict(classification(), kind="other"),
                 "no hosts": classification([host("RifleBase", "excluded")]),
                 "no lights": classification(lights=[light("Torch", "flame_or_chemical_light", "")]),
                 "bad class": classification([host('Evil"Name', "no_slot_host")]),
                 "duplicate": classification([host("AK74", "slot_host"), host("ak74", "no_slot_host")]),
                 "bad group": classification([host("AK74", "mystery")]),
                 "too many lights": classification(lights=[light("Light%d" % i, "mount_light", "representative")
                                                           for i in range(probe.MAX_LIGHTS + 1)])}
        for label, document in cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                probe.select_targets(document)
        for bad in (None, [], "text"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                probe.select_targets(bad)


class HookRenderingTests(unittest.TestCase):
    def setUp(self):
        self.targets = probe.select_targets(classification())
        self.hook = probe.render_hook(self.targets).decode("ascii")

    def test_hook_is_ascii_with_every_class_light_and_slot_inlined_as_literal_data(self):
        self.assertTrue(probe.render_hook(self.targets).isascii())
        for name in ("AK74", "Glock19", "PlainBag", "PlainHat", "UniversalLight", "TLRLight", "Flashlight"):
            self.assertIn('"%s"' % name, self.hook)
        self.assertNotIn("RifleBase", self.hook)
        self.assertNotIn("Torch", self.hook)
        for slot in SLOTS:
            self.assertIn('"%s"' % slot, self.hook)

    def test_hook_runs_server_side_once_with_no_clients_or_player_apis(self):
        self.assertIn("GetGame().IsServer()", self.hook)
        self.assertIn("m_HCTLStarted", self.hook)
        for forbidden in ("GetPlayers", "CreatePlayer", "PlayerBase", "ScriptRPC", "RPC", "GetRPCManager", "SetPosition",
                          "TeleportPlayer", "GetHive", "SaveWorld", "CreateObject(", "OnClient", "RemoteObject"):
            self.assertNotIn(forbidden, self.hook, forbidden)

    def test_every_spawn_is_server_only_non_persistent_and_released_by_deletion(self):
        self.assertIn("ECE_NOPERSISTENCY_WORLD", self.hook)
        self.assertIn("ECE_NOLIFETIME", self.hook)
        self.assertIn("GetGame().CreateObjectEx(", self.hook)
        self.assertEqual(1, self.hook.count("GetGame().CreateObjectEx("))
        self.assertEqual(1, self.hook.count("GetGame().ObjectDelete("))
        self.assertIn("HCTLReleaseAll", self.hook)
        # Attachments created natively are tracked too, so deletion never depends on the parent.
        self.assertIn("CreateAttachmentEx(", self.hook)
        self.assertRegex(self.hook, r"m_HCTLLive\.Insert\(att")

    def test_hard_cap_per_class_timeout_and_watchdog_are_generated_constants(self):
        hook = probe.render_hook(self.targets, start_delay_s=25, per_class_ms=2500).decode()
        self.assertIn("m_HCTLPerClassMs = 2500", hook)
        self.assertIn("m_HCTLHardCap = %d" % probe.HARD_CAP, hook)
        self.assertIn("GetGame().GetTime() - beginMs > m_HCTLPerClassMs", hook)
        self.assertIn("HCTLWatchdog", hook)
        self.assertIn("CallLater(HCTLStep, 25000", hook)
        self.assertIn("m_HCTLClasses.Count() > m_HCTLHardCap", hook)
        watchdog = int(re.search(r"CallLater\(HCTLWatchdog, (\d+), false\)", hook).group(1))
        self.assertGreater(watchdog, 25000 + 4 * 2500)

    def test_output_is_one_bounded_json_then_sentinel_inside_the_probe_profile_directory_only(self):
        self.assertEqual(1, self.hook.count('"$profile:HCTapedLightProbe"'))
        self.assertEqual(2, self.hook.count("OpenFile("))
        self.assertEqual(2, self.hook.count("FileMode.WRITE"))
        self.assertIn("FileExist(outputPath)", self.hook)  # never overwrites earlier evidence
        self.assertLess(self.hook.index("observations.json"), self.hook.index("complete.txt"))
        self.assertNotRegex(self.hook, r"\$(?:mission|saves|storage|profile):(?!HCTapedLightProbe)")
        self.assertIn("residual", self.hook)
        self.assertIn("GetObjectsAtPosition3D", self.hook)

    def test_observation_surface_uses_only_the_listed_engine_apis(self):
        for api in ("InventorySlots.GetSlotIdFromString", "InventorySlots.GetSelectionForSlotId", "HasAttachmentSlot",
                    "HasSelection", "MemoryPointExists", "GetBoneIndex", "GetMemoryPointPos", "CanAddAttachment(",
                    "CanAddAttachmentEx(", "FindAttachment(", "GetSelectionList", "GetBoneObject", "GetLODByName(",
                    "GetSelections(", "GetVertexPosition(", "GetLODS(", "GetLODName(", "IndexOfFrom(",
                    "ConfigGetChildrenCount(", "ConfigGetChildName("):
            self.assertIn(api, self.hook)
        allowed = {"GetSlotIdFromString", "GetSelectionForSlotId", "GetSlotName", "HasAttachmentSlot", "HasSelection",
                   "MemoryPointExists", "GetBoneIndex", "GetMemoryPointPos", "CanAddAttachment", "CanAddAttachmentEx",
                   "CreateAttachmentEx", "FindAttachment", "GetSelectionList", "GetBoneObject", "GetSlotIdCount",
                   "GetSlotId", "GetInventory", "CreateObjectEx", "ObjectDelete", "GetObjectsAtPosition3D", "SurfaceY",
                   "GetCallQueue", "CallLater", "OpenFile", "FPrintln", "CloseFile", "MakeDirectory", "FileExist",
                   "IsSlotIdValid", "GetBoneNameForSlotId", "HasInventorySlot", "GetAttachmentSlotId",
                   "GetAttachmentSlotsCount", "IsServer", "GetTime", "GetWorldName", "GetVersion", "Cast", "Replace", "Substring", "Length",
                   "Insert", "Get", "Count", "Find", "Print", "Vector", "OnInit", "GetGame", "AsciiToString",
                   "GetType", "ToLower", "IndexOf", "Clear", "Remove", "ConfigIsExisting", "ConfigGetBool", "ToString", "LastIndexOf",
                   "ConfigGetText", "ConfigGetTextArray", "GetLODByName", "GetSelections", "GetName", "GetVertexCount",
                   "GetLODVertexIndex", "GetVertexPosition", "GetLODS", "GetLODName", "IndexOfFrom",
                   "ConfigGetChildrenCount", "ConfigGetChildName"}
        called = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", re.sub(r'"[^"]*"', '""', "\n".join(syn.strip_comments(self.hook)))))
        own = set(re.findall(r"\b(?:void|bool|int|float|string|vector|EntityAI|Object|array<[^>]+>)\s+(\w+)\s*\(", self.hook))
        keywords = {"if", "while", "for", "return", "override", "array", "super"}
        leftovers = {c for c in called if c not in allowed and c not in own and c not in keywords
                     and not c.startswith("HCTL")}
        self.assertEqual(set(), leftovers)

    def test_hook_size_is_bounded_at_the_hard_cap(self):
        many = {"hosts": [{"class": "Gun%03d" % i, "root": "CfgWeapons", "group": "no_slot_host", "index": i}
                          for i in range(probe.HARD_CAP)], "lights": ["UniversalLight"], "slots": SLOTS,
                "excluded_not_probed": 0}
        self.assertLess(len(probe.render_hook(many)), 128 * 1024)
        many["hosts"].append(dict(many["hosts"][0], index=probe.HARD_CAP))
        with self.assertRaises(ValueError):
            probe.render_hook(many)

    def test_invalid_targets_delays_and_positions_are_refused(self):
        bad = dict(self.targets, hosts=[dict(self.targets["hosts"][0], **{"class": 'AK"Evil'})])
        for kwargs, targets in (({}, bad), ({"start_delay_s": 1}, self.targets), ({"start_delay_s": 5000}, self.targets),
                                ({"per_class_ms": 10}, self.targets), ({"per_class_ms": 600000}, self.targets),
                                ({"position": (7680.0, float("nan"))}, self.targets),
                                ({"position": (-5.0, 100.0)}, self.targets),
                                ({}, dict(self.targets, hosts=[])), ({}, dict(self.targets, lights=[])),
                                ({}, dict(self.targets, lights=["A"] * (probe.MAX_LIGHTS + 1)))):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                probe.render_hook(targets, **kwargs)

    def test_generated_hook_passes_every_native_observed_compile_rule(self):
        self.assertEqual([], probe.lint_hook(self.hook))
        native = probe.native_type_names(syn.CACHE) if (syn.CACHE / "3_Game").is_dir() else frozenset()
        self.assertEqual([], probe.lint_hook(self.hook, native_types=native))

    def test_generated_hook_passes_the_existing_authored_source_checkers(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "init.c"
            path.write_text(self.hook, encoding="utf-8")
            saved, syn.ROOT = syn.ROOT, Path(temporary)
            try:
                self.assertEqual([], syn.leading_operator_lines([path]))
                if (syn.CACHE / "4_World").is_dir():
                    self.assertEqual([], syn.mismatched_overrides([path], syn.native_prototypes(syn.CACHE)))
            finally:
                syn.ROOT = saved
            exponent = re.compile(r"\b\d+(?:\.\d+)?[eE][+-]?\d+\b")
            for number, line in enumerate(syn.strip_comments(self.hook), 1):
                self.assertIsNone(exponent.search(re.sub(r'"[^"]*"', '""', line)), number)
            names = set(ident.PINNED_ENGINE_TYPES)
            if (ident.CACHE / "3_Game").is_dir():
                for layer in ident.native_types_by_layer(ident.CACHE).values():
                    names |= layer
            clashes = [(n, name) for n, name in ident.declarations(path) if name in names]
            self.assertEqual([], clashes)

    def test_hook_has_no_ternary_leading_operator_or_shared_scope_redeclaration(self):
        code = re.sub(r'"[^"]*"', '""', "\n".join(syn.strip_comments(self.hook)))
        self.assertNotIn("?", code)
        self.assertEqual([], [l for l in code.splitlines() if syn.LEADING_OPERATOR.match(l)])

    def test_every_class_observation_checks_the_timeout_and_still_releases_what_it_spawned(self):
        body = self.hook[self.hook.index("string HCTLObserveHost("):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("HCTLReleaseAll()", body)
        self.assertIn("timed_out", self.hook)
        self.assertGreaterEqual(self.hook.count("m_HCTLPerClassMs"), 3)


class LintDetectorTests(unittest.TestCase):
    def wrap(self, body, header="void F(int a)"):
        return "class HCSample : CustomMission\n{\n    %s\n    {\n%s\n    }\n}\n" % (header, body)

    def issues(self, body, **extra):
        return probe.lint_hook(self.wrap(body, **extra))

    def test_ternary_is_flagged_but_question_marks_in_strings_are_not(self):
        self.assertTrue(any("ternary" in i for i in self.issues("        int x = a ? 1 : 2;")))
        self.assertEqual([], self.issues('        Print("what?");'))

    def test_duplicate_locals_are_flagged_across_sibling_blocks_and_parameters(self):
        sibling = "        if (a) { int value = 1; }\n        if (!a) { int value = 2; }"
        self.assertTrue(any("duplicate local 'value'" in i for i in self.issues(sibling)))
        self.assertTrue(any("duplicate local 'a'" in i for i in self.issues("        int a = 1;")))

    def test_identifier_equal_to_an_engine_type_or_reserved_word_is_flagged(self):
        self.assertTrue(any("engine type name" in i for i in self.issues("        Object Object = null;")))
        found = probe.lint_hook(self.wrap("        int Weather = 1;"), native_types=frozenset({"Weather"}))
        self.assertTrue(any("'Weather'" in i for i in found))
        self.assertTrue(any("reserved" in i for i in self.issues("        vector local = a;")))

    def test_leading_logical_operators_and_exponent_literals_are_flagged(self):
        self.assertTrue(any("leading" in i for i in self.issues("        if (a\n            || a) { }")))
        self.assertTrue(any("leading" in i for i in self.issues("        if (a\n            && a) { }")))
        self.assertTrue(any("exponent" in i for i in self.issues("        float big = 3.4e38;")))
        self.assertEqual([], self.issues('        float big = FLT_MAX;\n        Print("1e5");'))

    def test_out_arguments_must_be_declared_before_the_call(self):
        bad = "        GetGame().GetObjectsAtPosition3D(a, 1.0, objects, cargos);"
        self.assertTrue(any("out argument 'objects'" in i for i in self.issues(bad)))
        selection = "        bool ok = InventorySlots.GetSelectionForSlotId(a, name);"
        self.assertTrue(any("out argument 'name'" in i for i in self.issues(selection)))
        names = "        host.GetSelectionList(names);"
        self.assertTrue(any("out argument 'names'" in i for i in self.issues(names)))
        good = ("        string name = \"\";\n        bool ok = InventorySlots.GetSelectionForSlotId(a, name);")
        self.assertEqual([], self.issues(good))

    def test_the_lod_selection_list_out_argument_must_be_declared_before_the_call(self):
        """Round 7: LOD.GetSelections (gameplay.c:216) fills its out array, so the lint holds it to the same rule."""
        bad = "        bool ok = lodItem.GetSelections(picked);"
        self.assertTrue(any("out argument 'picked'" in i for i in self.issues(bad)))
        late = "        bool ok = lodItem.GetSelections(picked);\n        array<Selection> picked = new array<Selection>;"
        self.assertTrue(any("out argument 'picked'" in i for i in self.issues(late)))
        good = "        array<Selection> picked = new array<Selection>;\n        bool ok = lodItem.GetSelections(picked);"
        self.assertEqual([], self.issues(good))

    def test_string_literal_containing_comment_markers_is_refused(self):
        self.assertTrue(any("comment marker" in i for i in self.issues('        Print("a//b");')))

    def test_override_parameter_names_must_match_the_engine_prototype(self):
        text = "class HCSample : CustomMission\n{\n    override void OnEvent(int renamed)\n    {\n    }\n}\n"
        found = probe.lint_hook(text, prototypes={"OnEvent": {("eventTypeId",)}})
        self.assertTrue(any("override OnEvent" in i for i in found))
        self.assertEqual([], probe.lint_hook(text, prototypes={"OnEvent": {("renamed",)}}))


class StagerTests(Workspace):
    def test_stage_creates_a_fresh_runtime_with_empty_storage_and_profiles(self):
        plan = self.stage()
        for name in ("storage", "profiles"):
            self.assertTrue((self.dest / name).is_dir())
            self.assertEqual([], list((self.dest / name).iterdir()))
        self.assertEqual(SYNTH_BE, (self.dest / "battleye/BEServer_x64.dll").read_bytes())
        self.assertEqual((self.source / "serverDZ.cfg").read_bytes(), (self.dest / "serverDZ.cfg").read_bytes())
        self.assertEqual(plan, json.loads((self.dest / "taped-light-probe-plan.json").read_text()))

    def test_plan_has_the_required_identity_paths_arguments_and_status(self):
        plan = self.stage()
        self.assertEqual("staged-only-not-launched", plan["status"])
        self.assertEqual("taped-light-probe", plan["kind"])
        self.assertEqual(r"D:\SteamLibrary\steamapps\common\DayZServer\DayZServer_x64.exe", plan["server_exe"])
        self.assertEqual(EXE_SHA, plan["server_exe_sha256"])
        self.assertEqual(WINDOWS_ROOT, plan["runtime_root"])
        self.assertEqual(WINDOWS_ROOT + r"\mpmissions\dayzOffline.chernarusplus", plan["mission"])
        self.assertEqual(2302, plan["port"])
        self.assertEqual("127.0.0.1:2302", plan["requested_bind"])
        self.assertEqual(["-ip=127.0.0.1", "-port=2302", f"-config={WINDOWS_ROOT}\\serverDZ.cfg",
                          f"-mission={plan['mission']}", f"-storage={plan['storage']}",
                          f"-profiles={plan['profiles']}", f"-BEpath={WINDOWS_ROOT}\\battleye",
                          "-doLogs", "-adminLog"], plan["arguments"])
        for argument in plan["arguments"]:
            self.assertNotRegex(argument, r"(?i)-mod=|-servermod=|-filepatching|-connect")
        self.assertEqual("server-only-no-clients", plan["probe"]["mode"])
        self.assertEqual(0, plan["probe"]["clients"])

    def test_plan_records_probe_limits_counts_and_output_locations(self):
        plan = self.stage(start_delay_s=25, per_class_ms=2000)
        probe_plan = plan["probe"]
        self.assertEqual(4, probe_plan["host_count"])
        self.assertEqual({"slot_host": 2, "no_slot_host": 2}, probe_plan["groups"])
        self.assertEqual(1, probe_plan["excluded_not_probed"])
        self.assertEqual(probe.HARD_CAP, probe_plan["hard_cap"])
        self.assertEqual(2000, probe_plan["per_class_ms"])
        self.assertEqual(25, probe_plan["start_delay_s"])
        self.assertEqual(["Flashlight", "TLRLight", "UniversalLight"], probe_plan["lights"])
        self.assertEqual("profiles/HCTapedLightProbe/observations.json", probe_plan["output_relative_path"])
        self.assertEqual("profiles/HCTapedLightProbe/complete.txt", probe_plan["sentinel_relative_path"])
        self.assertEqual(["AK74", "Glock19", "PlainBag", "PlainHat"], [t["class"] for t in plan["targets"]])
        self.assertGreaterEqual(probe_plan["wait_minutes"], 5)
        self.assertEqual("PENDING", plan["acceptance"])

    def test_every_staged_file_is_hashed_and_matches_disk(self):
        plan = self.stage()
        paths = {entry["path"] for entry in plan["staged_files"]}
        for expected in ("serverDZ.cfg", "battleye/BEServer_x64.dll", "mpmissions/dayzOffline.chernarusplus/init.c"):
            self.assertIn(expected, paths)
        on_disk = {p.relative_to(self.dest).as_posix() for p in self.dest.rglob("*")
                   if p.is_file() and p.name != "taped-light-probe-plan.json"}
        self.assertEqual(on_disk, paths)
        for entry in plan["staged_files"]:
            data = (self.dest / entry["path"]).read_bytes()
            self.assertEqual((sha(data), len(data)), (entry["sha256"], entry["bytes"]), entry["path"])

    def test_init_c_gets_the_hook_and_no_other_mission_file_changes(self):
        plan = self.stage()
        init = (self.dest / "mpmissions/dayzOffline.chernarusplus/init.c").read_bytes()
        self.assertIn(b"return new HCDisposableDiagnosticMission();", init)
        self.assertEqual(plan["probe"]["hook_sha256"], sha(init[init.index(b"\n\n// Hollow Country DISPOSABLE"):]))
        for name in ("db/types.xml", "mapgroupproto.xml"):
            self.assertEqual((self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus" / name).read_bytes(),
                             (self.dest / "mpmissions/dayzOffline.chernarusplus" / name).read_bytes())
        text = init.decode()
        self.assertEqual([], probe.lint_hook(text[text.index("// Hollow Country DISPOSABLE"):]))
        original = next(f for f in plan["mission_files"] if f["path"] == "init.c")
        self.assertEqual(sha(STOCK_INIT), original["source_sha256"])
        self.assertNotEqual(original["sha256"], original["source_sha256"])

    def test_already_instrumented_or_unexpected_init_c_is_refused(self):
        init = self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus/init.c"
        for payload in (STOCK_INIT + b"class HCDisposableDiagnosticMission {}\n", b"void main() {}\n"):
            init.write_bytes(payload)
            plan_path = self.source / "launch-plan.json"
            document = json.loads(plan_path.read_text())
            for entry in document["mission_files"]:
                if entry["path"] == "init.c":
                    entry["sha256"] = sha(payload)
            plan_path.write_text(json.dumps(document))
            with self.subTest(payload=payload[:20]), self.assertRaises(ValueError):
                self.stage()
            self.assertFalse(self.dest.exists())

    def test_class_cap_violation_is_refused_before_anything_is_created(self):
        self.classification = classification([host("Gun%03d" % i, "no_slot_host") for i in range(probe.HARD_CAP + 1)])
        with self.assertRaises(ValueError):
            self.stage()
        self.assertFalse(self.dest.exists())

    def test_tampered_stock_file_and_wrong_hashes_are_refused(self):
        mission = self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus"
        (mission / "db/types.xml").write_bytes(b"<types>tampered</types>\n")
        with self.assertRaises(ValueError):
            self.stage()
        (mission / "db/types.xml").write_bytes(b"<types>synthetic</types>\n")
        (self.source / "serverDZ.cfg").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.stage()
        (self.source / "serverDZ.cfg").write_bytes(b'hostname = "SYNTHETIC";\r\n')
        with self.assertRaises(ValueError):
            probe.stage(self.source, self.dest, self.classification, **self.kw(battleye_sha256="0" * 64))
        self.assertFalse(self.dest.exists())

    def test_existing_destination_is_never_overwritten_and_the_source_is_not_modified(self):
        before = {p.relative_to(self.source).as_posix(): sha(p.read_bytes()) for p in self.source.rglob("*") if p.is_file()}
        self.stage()
        marker = self.dest / "storage/keep.txt"
        marker.write_text("evidence")
        with self.assertRaises(ValueError):
            self.stage()
        self.assertEqual("evidence", marker.read_text())
        after = {p.relative_to(self.source).as_posix(): sha(p.read_bytes()) for p in self.source.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_destination_is_always_a_new_direct_child_of_the_probe_parent(self):
        with self.assertRaises(ValueError):
            probe.stage(self.source, self.source / "child", self.classification, **self.kw())
        with self.assertRaises(ValueError):
            probe.stage(self.source, ROOT / "taped-light-inside-checkout", self.classification, **self.kw())
        nested = self.root / "elsewhere"
        nested.mkdir()
        for bad in (nested / "taped-x", self.root / "a" / "b" / "taped-y", self.root / "taped z"):
            with self.subTest(bad=str(bad)), self.assertRaises(ValueError):
                probe.stage(self.source, bad, self.classification, **self.kw())
            self.assertFalse(bad.exists())
        for name in ("vanilla-p0-001", "VANILLA-P0-001"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                probe.stage(self.source, self.root / name, self.classification, **self.kw())
        with self.assertRaises(ValueError):  # production parent: a writable temp location is still refused
            probe.stage(self.source, self.dest, self.classification, battleye_sha256=SYNTH_BE_SHA)
        self.assertFalse(self.dest.exists())

    def test_windows_paths_derive_from_mnt_d_only(self):
        self.assertEqual(r"D:\HollowCountryLocal\taped-light-001",
                         probe.windows_runtime_root(Path("/mnt/d/HollowCountryLocal/taped-light-001")))
        for bad in ("/mnt/d/Other/x", "/tmp/x", "/mnt/d/HollowCountryLocal/vanilla-p0-001",
                    "/mnt/d/HollowCountryLocal/bad name", "/mnt/d/HollowCountryLocal/a/b"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                probe.windows_runtime_root(Path(bad))
        with self.assertRaises(TypeError):
            probe.stage(self.source, self.dest, self.classification, windows_runtime_root=WINDOWS_ROOT, **self.kw())

    def test_sensitive_source_files_are_refused_even_when_absent_from_the_manifest(self):
        mission = self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus"
        secret = b"SYNTHETIC-SECRET-MATERIAL"
        for relative in ("keys/server.biprivatekey", "profiles/state.json", "storage/data.bin", "notes.txt",
                         "credentials.json", "scripts/extra.c"):
            target = mission / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(secret)
            with self.subTest(relative=relative):
                with self.assertRaises(ValueError) as raised:
                    self.stage()
                self.assertNotIn(secret.decode(), str(raised.exception))
                self.assertFalse(self.dest.exists())
            target.unlink()
            if target.parent != mission and not any(target.parent.iterdir()):
                target.parent.rmdir()
        self.stage()

    def test_staged_tree_contains_only_allowlisted_content(self):
        plan = self.stage()
        allowed = re.compile(r"^(?:serverDZ\.cfg|battleye/BEServer_x64\.dll|taped-light-probe-plan\.json|"
                             r"mpmissions/dayzOffline\.chernarusplus/(?:\.hollow-country-diagnostic-mission\.json|"
                             r"(?:(?:db|env)/)?[A-Za-z0-9_.-]+\.(?:xml|json|map|c)))$")
        for path in (p.relative_to(self.dest).as_posix() for p in self.dest.rglob("*") if p.is_file()):
            self.assertRegex(path, allowed)
        self.assertEqual(sorted(e["path"] for e in plan["staged_files"]),
                         sorted(e["path"] for e in plan["staged_files"] if allowed.match(e["path"])))

    def test_staging_never_launches_anything_or_touches_the_network(self):
        with mock.patch("subprocess.Popen", side_effect=AssertionError("launch")), \
                mock.patch("socket.socket", side_effect=AssertionError("network")), \
                mock.patch("os.system", side_effect=AssertionError("launch")):
            self.stage()
        code = re.sub(r'""".*?"""', "", PROBE_SOURCE.read_text(encoding="utf-8"), flags=re.S)
        for forbidden in ("import subprocess", "Popen(", "os.system", "os.exec", "wine ", "powershell.exe", "socket"):
            self.assertNotIn(forbidden, code)

    def test_cli_stages_and_prints_the_plan_path_and_fails_on_reuse(self):
        document = self.root / "classification.json"
        document.write_text(json.dumps(self.classification))
        argv = ["--source-runtime", str(self.source), "--destination", str(self.dest),
                "--classification", str(document), "--battleye-sha256", SYNTH_BE_SHA, "--per-class-ms", "2000"]
        with mock.patch.object(probe, "WSL_PARENT", self.root), mock.patch("sys.stdout") as out:
            self.assertEqual(0, probe.main(argv))
        self.assertIn("taped-light-probe-plan.json", "".join(call.args[0] for call in out.write.call_args_list))
        self.assertEqual(2000, json.loads((self.dest / "taped-light-probe-plan.json").read_text())["probe"]["per_class_ms"])
        with mock.patch.object(probe, "WSL_PARENT", self.root), mock.patch("sys.stderr"):
            self.assertEqual(1, probe.main(argv))
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            probe.main(argv + ["--windows-runtime-root", WINDOWS_ROOT])


# ---------------------------------------------------------------------------
# Behavioral model of the GENERATED hook.
#
# SYNTHETIC engine: the mock below implements only the shape of the native calls the hook uses
# (create, attach, delete, census, clock, files). Its rules are explicit test assumptions and
# establish nothing about DayZ. What these tests prove is the generated hook's own logic: the
# order of its calls, what it counts and what it writes. The hook text is translated statement
# by statement to Python; a construct the translator does not model raises instead of passing.
# ---------------------------------------------------------------------------


class S(str):
    """Enforce-like string. The generated hook must convert numbers explicitly (x.ToString()): concatenating a
    raw bool, int or float is refused here, mirroring the stricter native compile rule the lint enforces."""

    def __add__(self, other):
        if not isinstance(other, str):
            raise TypeError("bare non-string concatenation operand: %r (use .ToString())" % (other,))
        return S(str(self) + other)

    def __radd__(self, other):
        if not isinstance(other, str):
            raise TypeError("bare non-string concatenation operand: %r (use .ToString())" % (other,))
        return S(other + str(self))

    def Length(self):
        return len(self)

    def Substring(self, start, length):
        return S(self[start:start + length])

    def Replace(self, sample, replacement):
        return S(str.replace(self, sample, replacement))

    def ToLower(self):
        return S(self.lower())

    def IndexOf(self, sample):
        return self.find(sample)

    def LastIndexOf(self, sample):
        return self.rfind(sample)

    def IndexOfFrom(self, start, sample):
        """EnString.c:271 proto native int IndexOfFrom(int start, string sample): first match at or after start, else -1."""
        return self.find(sample, start)


class EArray(list):
    def Count(self):
        return len(self)

    def Get(self, index):
        return self[index]

    def Insert(self, value):
        self.append(value)
        return len(self) - 1

    def Find(self, value):
        return self.index(value) if value in self else -1

    def Clear(self):
        del self[:]


_LITERAL = re.compile(r'"([^"]*)"')
_SIGNATURE = re.compile(r"^    (?:override\s+)?(?:void|bool|int|float|string|vector|Object|EntityAI|LOD)\s+(\w+)\(([^)]*)\)\s*$")
_FIELD = re.compile(r"^    protected (?:ref\s+)?[\w<>]+\s+(m_HCTL\w+)(?:\s*=\s*(.+))?;$")
_DECLARATION = re.compile(r"^(?:ref\s+)?(?!return\b)[A-Za-z_]\w*(?:<[^>]*>)?\s+(\w+)(?:\s*=\s*(.+))?$", re.S)
_OUT_ASSIGN = re.compile(r"^(?:\w+\s+)?(\w+)\s*=\s*([\w.]+\.(?:GetSelectionForSlotId|GetBoneNameForSlotId))\((.*),\s*(\w+)\)$")


def _code(text):
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"!(?!=)", " not ", text)
    for word, python in (("true", "True"), ("false", "False"), ("null", "None")):
        text = re.sub(r"\b%s\b" % word, python, text)
    text = re.sub(r"\bnew\s+(?:array<[^>]*>|TStringArray)", "EArray()", text)
    text = re.sub(r"\b(\w+)\.AsciiToString\(\)", r"S(chr(\1))", text)
    text = re.sub(r"((?<![\w.])\w+(?:\[\d+\])?(?:\(\))?(?:\.\w+\(\))*)\.ToString\(\)", r"NumberText(\1)", text)
    text = re.sub(r"\bsuper\.", "super().", text)
    return re.sub(r"(?<![\w.])((?:m_)?HCTL\w+)", r"self.\1", text)


def _expression(text):
    out, last = [], 0
    for match in _LITERAL.finditer(text):
        out.append(_code(text[last:match.start()]))
        # Enforce reads a three-number string literal as a vector.
        out.append("(0.0, 0.0, 0.0)" if match.group(1) == "0 0 0" else "S(%r)" % match.group(1))
        last = match.end()
    out.append(_code(text[last:]))
    return "".join(out).strip()


def _simple(statement):
    out = _OUT_ASSIGN.match(statement)
    if out:
        return "%s, %s = %s" % (out.group(1), out.group(4), _expression("%s(%s, %s)" % out.group(2, 3, 4)))
    version = re.match(r"^GetGame\(\)\.(GetWorldName|GetVersion)\((\w+)\)$", statement)
    if version:
        return "%s = GetGame().%s()" % (version.group(2), version.group(1))
    config_text = re.match(r"^GetGame\(\)\.ConfigGetText\((.+),\s*(\w+)\)$", statement)
    if config_text:                   # ConfigGetText(path, out string value): the out argument is assigned
        return "%s = GetGame().ConfigGetText(%s)" % (config_text.group(2), _expression(config_text.group(1)))
    child_name = re.match(r"^GetGame\(\)\.ConfigGetChildName\((.+),\s*(\w+)\)$", statement)
    if child_name:                    # ConfigGetChildName(path, index, out string name): the out argument is assigned
        return "%s = GetGame().ConfigGetChildName(%s)" % (child_name.group(2), _expression(child_name.group(1)))
    receiver = re.match(r"^(\w+)\.(?:ToLower|Replace)\(", statement)
    if receiver:                      # Enforce mutates the receiver; Python strings do not
        return "%s = %s" % (receiver.group(1), _expression(statement))
    if statement in ("break", "continue"):
        return statement
    if statement.startswith("return"):
        rest = statement[6:].strip()
        return "return " + _expression(rest) if rest else "return"
    declaration = _DECLARATION.match(statement)
    if declaration:
        return "%s = %s" % (declaration.group(1), _expression(declaration.group(2)) if declaration.group(2) else "None")
    return _expression(statement)


class _Reader:
    def __init__(self, text):
        self.text, self.at = text, 0

    def space(self):
        while self.text[self.at].isspace():
            self.at += 1

    def word(self):
        found = re.compile(r"[A-Za-z_]\w*").match(self.text, self.at)
        return found.group(0) if found else ""

    def balanced(self):
        depth, quoted, start = 0, False, self.at
        while True:
            char = self.text[self.at]
            self.at += 1
            if char == '"':
                quoted = not quoted
            elif not quoted and char == "(":
                depth += 1
            elif not quoted and char == ")":
                depth -= 1
                if depth == 0:
                    return self.text[start + 1:self.at - 1]

    def statement_text(self):
        quoted, start = False, self.at
        while quoted or self.text[self.at] != ";":
            if self.text[self.at] == '"':
                quoted = not quoted
            self.at += 1
        self.at += 1
        return self.text[start:self.at - 1].strip()


def _statement(reader):
    reader.space()
    if reader.text[reader.at] == "{":
        reader.at += 1
        lines = []
        while True:
            reader.space()
            if reader.text[reader.at] == "}":
                reader.at += 1
                return lines or ["pass"]
            lines += _statement(reader)
    word = reader.word()
    if word in ("if", "while") and reader.text[reader.at + len(word):].lstrip().startswith("("):
        reader.at += len(word)
        reader.space()
        condition = reader.balanced()
        lines = ["%s %s:" % (word, _expression(condition))] + ["    " + line for line in _statement(reader)]
        if word == "if":
            saved = reader.at
            reader.space()
            if reader.word() == "else":
                reader.at += 4
                lines += ["else:"] + ["    " + line for line in _statement(reader)]
            else:
                reader.at = saved
        return lines
    return [_simple(reader.statement_text())]


def enforce_to_python(text):
    """Translate the whole generated mission class to a Python class; refuse any shape it cannot model."""
    lines = re.sub(r"//[^\n]*", "", text).splitlines()    # lint refuses comment markers inside strings
    init, methods, index = [], [], 0
    while index < len(lines):
        field = _FIELD.match(lines[index])
        if field:
            init.append("        self.%s = %s" % (field.group(1), _expression(field.group(2)) if field.group(2) else "None"))
        signature = _SIGNATURE.match(lines[index])
        if signature and index + 1 < len(lines) and lines[index + 1] == "    {":
            end = index + 2
            while lines[end] != "    }":
                end += 1
            params = ["self"] + [p.split()[-1] for p in signature.group(2).split(",") if p.strip()]
            body = _statement(_Reader("{" + "\n".join(lines[index + 2:end]) + "}"))
            methods.append("    def %s(%s):\n%s" % (signature.group(1), ", ".join(params),
                                                    "\n".join("        " + line for line in body)))
            index = end
        index += 1
    return ("class HookModel(MissionBase):\n    def __init__(self):\n%s\n%s\n"
            % ("\n".join(init) or "        pass", "\n".join(methods)))


SLOT_IDS = {"weaponFlashlight": 101, "pistolFlashlight": 102, "helmetFlashlight": 103,
            "weaponHandguardAK": 201, "weaponHandguardM4": 202, "weaponHandguardMP5": 203}
SLOT_NAMES = {number: name for name, number in SLOT_IDS.items()}
HANDGUARD_SLOTS = ("weaponHandguardAK", "weaponHandguardM4", "weaponHandguardMP5")
SLOT_SELECTION = {"weaponFlashlight": "light_w", "pistolFlashlight": "light_p", "helmetFlashlight": "light_h",
                  "weaponHandguardAK": "hg_ak", "weaponHandguardM4": "hg_m4", "weaponHandguardMP5": "hg_mp5"}


def spec(slots=(), fits=(), selections=(), memory=(), rail=False, needs_rail=False, proxies=(), res=(),
         res_no_vertex=(), res_unlisted=False, view=None, lods=None, lods_unlisted=False):
    """``res`` is the selection names held by the resolution LOD "1.000" (the default LOD list); ``res_no_vertex`` names
    selections without a first vertex; ``res_unlisted`` makes LOD.GetSelections return false (with the names still in
    its out array, which the hook must ignore) on every LOD. ``view`` is the selection names of a LOD named "view" (None:
    no such LOD): a decoy, because the hook must never read it as evidence. ``lods`` is the LOD list Object.GetLODS
    reports, each item a name or a (name, selection names) pair (None: "1.000" holding ``res``, plus "view" when ``view``
    is given); ``lods_unlisted`` makes Object.GetLODS return false with junk in its out array."""
    return {"slots": tuple(slots), "fits": tuple(fits), "selections": tuple(selections), "memory": tuple(memory),
            "rail": rail, "needs_rail": needs_rail, "proxies": tuple(proxies), "res": tuple(res),
            "res_no_vertex": tuple(res_no_vertex), "res_unlisted": res_unlisted,
            "view": None if view is None else tuple(view), "lods": None if lods is None else tuple(lods),
            "lods_unlisted": lods_unlisted}


LIGHT_UNIVERSAL_PROXY = "proxy:/dz/weapons/attachments/light/weaponlight_universal.001"
LIGHT_TLR_PROXY = "proxy:/dz/weapons/attachments/light/weaponlight_tlr.001"
MUZZLE_PROXY = "proxy:/dz/weapons/proxies/muzzle_flash_rifle_m4.001"


def proxy_config():
    """Synthetic CfgNonAIVehicles entries shaped like the probe-003 observations: the config key is the class path,
    ``model`` keeps the engine's backslashes and a leading slash, ``inventorySlot`` is an array or a single text."""
    return {"CfgNonAIVehicles Proxyweaponlight_universal": {
                "model": "\\dz\\weapons\\attachments\\light\\weaponlight_universal.p3d", "inventorySlot": ["weaponFlashlight"]},
            "CfgNonAIVehicles Proxyweaponlight_tlr": {
                "model": "\\dz\\weapons\\attachments\\light\\weaponlight_tlr.p3d", "inventorySlot": "pistolFlashlight"}}


def catalogue():
    """Synthetic type table. needs_rail stands in for a refusal that depends on another attachment."""
    return {"AK74": spec(("weaponFlashlight", "weaponHandguardAK"), selections=("light_w", "hg_ak"), memory=("light_w",)),
            "Glock19": spec(("pistolFlashlight",), selections=("light_p",)),
            "PlainBag": spec(), "PlainHat": spec(),
            "UniversalLight": spec(fits=("helmetFlashlight", "weaponFlashlight"), needs_rail=True,
                                   memory=("beamStart", "beamEnd")),
            "TLRLight": spec(fits=("pistolFlashlight",)), "Flashlight": spec(),
            "AK_RailHndgrd": spec(fits=("weaponHandguardAK",), rail=True)}


class Entity:
    def __init__(self, world, type_name, entity_spec):
        self.world, self.type_name, self.spec = world, type_name, entity_spec
        self.alive, self.attached = True, {}
        self.inventory = Inventory(self)

    def __bool__(self):
        return self.alive          # the synthetic engine nulls a deleted reference

    def GetType(self):
        return S(self.type_name)

    def GetInventory(self):
        return self.inventory

    def HasSelection(self, name):
        return name in self.spec["selections"]

    def MemoryPointExists(self, name):
        return name in self.spec["memory"]

    def GetBoneIndex(self, name):
        return 3 if name in self.spec["selections"] else -1

    def GetBoneObject(self, index):
        return None

    def GetMemoryPointPos(self, name):
        return (0.0, 1.0, 2.0)

    def GetSelectionList(self, out):
        out.extend(S(name) for name in self.spec["selections"] + self.spec["proxies"])

    def lod_entries(self):
        """(name, selection names) of each LOD, in the order GetLODS lists them."""
        if self.spec["lods"] is not None:
            items = self.spec["lods"]
        else:
            items = (("1.000", self.spec["res"]),) + ((("view", self.spec["view"]),) if self.spec["view"] is not None else ())
        return [(item, ()) if isinstance(item, str) else (item[0], tuple(item[1])) for item in items]

    def GetLODS(self, out):
        """Object.c:98 proto native bool GetLODS(notnull out array<LOD> lods). A failed call returns false and may
        leave anything in the out array."""
        self.world.lods_calls += 1
        if self.spec["lods_unlisted"]:
            out.append(ModelLod(self, "9", ("junk",)))
            return False
        for name, names in self.lod_entries():
            out.append(ModelLod(self, name, names))
        return True

    def GetLODName(self, lod):
        """Object.c:101 proto native owned string GetLODName(LOD lod)."""
        return S(lod.name)

    def GetLODByName(self, name):
        """Object.c:106-122 (script): the first LOD whose lower-cased name equals the lower-cased argument, or null."""
        lods = EArray()
        self.GetLODS(lods)
        for lod in lods:
            if str(self.GetLODName(lod)).lower() == str(name).lower():
                return lod
        return None

    def ConfigIsExisting(self, key):
        return key == "hasRailFunctionality" and self.spec["rail"]

    def ConfigGetBool(self, key):
        return key == "hasRailFunctionality" and self.spec["rail"]


class ModelSelection:
    """gameplay.c:179 Selection: GetName, GetVertexCount, GetLODVertexIndex and the script GetVertexPosition(lod, index),
    which calls Error() (here: raises) when the LOD vertex index is -1, as the native class does."""

    def __init__(self, name, has_vertex):
        self.name, self.has_vertex = name, has_vertex

    def GetName(self):
        return S(self.name)

    def GetVertexCount(self):
        return 1 if self.has_vertex else 0

    def GetLODVertexIndex(self, index):
        return 0 if self.has_vertex and index == 0 else -1

    def GetVertexPosition(self, lod, index):
        lod_index = self.GetLODVertexIndex(index)
        if lod_index == -1:
            raise AssertionError("Error(Vertex doesn't exist)")
        return lod.GetVertexPosition(lod_index)


class ModelLod:
    """gameplay.c:203 LOD: GetSelectionCount, GetSelections(out array<Selection>) -> bool, GetVertexPosition(index). Every
    GetSelections call is logged by LOD name in world.selection_log. A failed call (spec res_unlisted) still fills the out
    array, as a native call that returned false might."""

    def __init__(self, entity, name, names):
        self.name, self.entity = name, entity
        self.selections = [ModelSelection(item, item not in entity.spec["res_no_vertex"]) for item in names]

    def GetSelectionCount(self):
        return len(self.selections)

    def GetSelections(self, out):
        self.entity.world.selection_log.append(self.name)
        out.extend(self.selections)
        return not self.entity.spec["res_unlisted"]

    def GetVertexPosition(self, index):
        return (0.5, 0.25, -1.5)


class LODNames:
    """The LOD class constants the hook reads (gameplay.c:207 NAME_VIEW)."""
    NAME_VIEW = S("view")


class Inventory:
    def __init__(self, entity):
        self.entity = entity

    def HasAttachmentSlot(self, slot_id):
        return SLOT_NAMES.get(slot_id) in self.entity.spec["slots"]

    def HasInventorySlot(self, slot_id):
        return SLOT_NAMES.get(slot_id) in self.entity.spec["fits"]

    def GetAttachmentSlotsCount(self):
        return len(self.entity.spec["slots"])

    def GetAttachmentSlotId(self, index):
        return SLOT_IDS[self.entity.spec["slots"][index]]

    def GetSlotIdCount(self):
        return len(self.entity.spec["fits"])

    def GetSlotId(self, index):
        return SLOT_IDS[self.entity.spec["fits"][index]]

    def CanAddAttachment(self, item):
        return any(self.CanAddAttachmentEx(item, SLOT_IDS[name]) for name in self.entity.spec["slots"])

    def CanAddAttachmentEx(self, item, slot_id):
        name, host = SLOT_NAMES.get(slot_id), self.entity
        if name not in host.spec["slots"] or name in host.attached or name not in item.spec["fits"]:
            return False
        if item.spec["needs_rail"]:
            owned = [slot for slot in host.spec["slots"] if slot in HANDGUARD_SLOTS]
            if owned and not any(slot in host.attached and host.attached[slot].spec["rail"] for slot in owned):
                return False
        return True

    def CreateAttachmentEx(self, type_name, slot_id):
        if not isinstance(type_name, str) or isinstance(slot_id, bool) or not isinstance(slot_id, int):
            raise TypeError("CreateAttachmentEx(string type, int slot): got %r, %r" % (type_name, slot_id))
        world = self.entity.world
        world.attach_calls.append((str(type_name), slot_id))
        if type_name not in world.catalogue:
            return None
        candidate = Entity(world, str(type_name), world.catalogue[type_name])
        if not self.CanAddAttachmentEx(candidate, slot_id):
            return None
        world.register(candidate)
        self.entity.attached[SLOT_NAMES[slot_id]] = candidate
        return candidate

    def FindAttachment(self, slot_id):
        return self.entity.attached.get(SLOT_NAMES.get(slot_id))


class Background:
    """A static world object the census can see (a tree, a wall)."""

    def __init__(self, type_name="Land_Synth_Tree"):
        self.type_name = type_name

    def __bool__(self):
        return True

    def GetType(self):
        return S(self.type_name)


class Queue:
    def __init__(self, world):
        self.world = world

    def CallLater(self, function, delay, repeat):
        self.world.queue.append((self.world.now + delay, len(self.world.queue), function))


class World:
    """Synthetic server: clock, object table, call queue, files. Deletion can be made to fail per type."""

    def __init__(self, types=None, background=0, stuck=(), spawn_ms=0, config=None):
        self.catalogue = types if types is not None else catalogue()
        self.config = proxy_config() if config is None else config
        self.entities, self.background = [], [Background() for _ in range(background)]
        self.stuck, self.spawn_ms, self.now = set(stuck), spawn_ms, 0
        self.queue, self.files, self.printed = [], {}, []
        self.attach_calls, self.delete_calls, self.create_calls = [], 0, []
        self.selection_log, self.lods_calls = [], 0

    def register(self, entity):
        self.entities.append(entity)
        self.now += self.spawn_ms

    def CreateObjectEx(self, type_name, position, flags):
        self.create_calls.append((str(type_name), flags))
        if type_name not in self.catalogue:
            return None
        entity = Entity(self, str(type_name), self.catalogue[type_name])
        self.register(entity)
        return entity

    def ObjectDelete(self, entity):
        self.delete_calls += 1
        if entity.type_name not in self.stuck:
            entity.alive = False

    def GetObjectsAtPosition3D(self, position, radius, objects, cargos):
        for candidate in self.background + [e for e in self.entities if e.alive]:
            objects.Insert(candidate)

    def _config_entry(self, path):
        """(class path, entry key) of a "<class path> <key>" config path, or the class path alone."""
        text = str(path)
        return (text, None) if text in self.config else tuple(text.rsplit(" ", 1))

    def ConfigIsExisting(self, path):
        return self._config_entry(path)[0] in self.config and (
            self._config_entry(path)[1] is None or self._config_entry(path)[1] in self.config[self._config_entry(path)[0]])

    def ConfigGetText(self, path):
        """The text value, or "" when the entry is absent or is an array (the native call returns false)."""
        entry, key = self._config_entry(path)
        value = self.config.get(entry, {}).get(key, "")
        return S(value) if isinstance(value, str) else S("")

    def _children(self, path):
        prefix = str(path) + " "
        return sorted(key[len(prefix):] for key in self.config if key.startswith(prefix) and " " not in key[len(prefix):])

    def ConfigGetChildrenCount(self, path):
        """Game.c:611 proto native int ConfigGetChildrenCount(string path)."""
        return len(self._children(path))

    def ConfigGetChildName(self, path, index):
        """Game.c:594 proto bool ConfigGetChildName(string path, int index, out string name); here the name."""
        return S(self._children(path)[index])

    def ConfigGetTextArray(self, path, out):
        entry, key = self._config_entry(path)
        value = self.config.get(entry, {}).get(key, [])
        out.extend(S(item) for item in (value if isinstance(value, list) else []))

    def GetTime(self):
        return self.now

    def IsServer(self):
        return True

    def SurfaceY(self, x, z):
        return 10.0

    def GetCallQueue(self, category):
        return Queue(self)

    def GetWorldName(self):
        return S("synthetic-world")

    def GetVersion(self):
        return S("synthetic-version")

    def live(self):
        return [e for e in self.entities if e.alive]


class MissionBase:
    def OnInit(self):
        pass


class _Slots:
    @staticmethod
    def GetSlotIdFromString(name):
        return SLOT_IDS.get(str(name), -1)

    @staticmethod
    def IsSlotIdValid(slot_id):
        return slot_id in SLOT_NAMES

    @staticmethod
    def GetSlotName(slot_id):
        return S(SLOT_NAMES.get(slot_id, ""))

    @staticmethod
    def GetSelectionForSlotId(slot_id, out):
        name = SLOT_NAMES.get(slot_id)
        return (True, S(SLOT_SELECTION[name])) if name else (False, S(""))

    @staticmethod
    def GetBoneNameForSlotId(slot_id, out):
        name = SLOT_NAMES.get(slot_id)
        return (True, S("bone_" + name)) if name else (False, S(""))


class _EntityAI:
    @staticmethod
    def Cast(value):
        return value if isinstance(value, Entity) else None


class _Handle:
    def __init__(self, path):
        self.path, self.lines = path, []


class _FileMode:
    WRITE = "write"


def number_text(value):
    """int/float .ToString() of the synthetic engine; a bool or non-number has none."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("ToString on a non-number: %r" % (value,))
    return S(str(value) if isinstance(value, int) else repr(value))


class _NoSelectionSlots(_Slots):
    """The probe-003 truth: InventorySlots.GetSelectionForSlotId returned false and "" for every slot natively."""

    @staticmethod
    def GetSelectionForSlotId(slot_id, out):
        return False, S("")


def build_model(hook_text, world, slots=_Slots):
    def open_file(path, mode):
        return _Handle(str(path))

    def close_file(handle):
        world.files[handle.path] = "\n".join(handle.lines) + "\n"

    namespace = {
        "NumberText": number_text, "S": S, "EArray": EArray, "MissionBase": MissionBase, "GetGame": lambda: world, "InventorySlots": slots,
        "EntityAI": _EntityAI, "LOD": LODNames, "Vector": lambda x, y, z: (x, y, z), "FileMode": _FileMode,
        "Print": lambda text: world.printed.append(str(text)), "FPrintln": lambda handle, text: handle.lines.append(str(text)),
        "OpenFile": open_file, "CloseFile": close_file,
        "FileExist": lambda path: str(path) in world.files or str(path).endswith("HCTapedLightProbe"),
        "MakeDirectory": lambda path: True,
        "ECE_IN_INVENTORY": 1, "ECE_NOPERSISTENCY_WORLD": 2, "ECE_NOLIFETIME": 4, "CALL_CATEGORY_SYSTEM": 0}
    source = enforce_to_python(hook_text)
    exec(compile(source, "<generated-hook>", "exec"), namespace)
    return namespace["HookModel"]()


def drain(world, limit=100000):
    """Run the call queue in due order on the synthetic clock."""
    for _ in range(limit):
        if not world.queue:
            return
        world.queue.sort(key=lambda item: item[:2])
        due, _order, function = world.queue.pop(0)
        world.now = max(world.now, due)
        function()
    raise AssertionError("call queue never drained")


OUTPUT_PATH = "$profile:HCTapedLightProbe/observations.json"


def run_hook(world, targets=None, slots=_Slots, **render):
    text = probe.render_hook(targets or probe.select_targets(classification()), **render).decode("ascii")
    model = build_model(text, world, slots)
    model.OnInit()
    drain(world)
    return model


def observations_of(world):
    return json.loads(world.files[OUTPUT_PATH])


def host_row(observations, name):
    return next(row for row in observations["hosts"] if row["class"] == name)


class HookBehaviorTests(unittest.TestCase):
    def test_the_hook_text_is_modelled_in_full_and_arms_itself(self):
        world = World()
        model = run_hook(world)
        self.assertTrue(any("ARMED" in line for line in world.printed))
        self.assertEqual("complete", model.m_HCTLStatus)
        self.assertIn(OUTPUT_PATH, world.files)

    def test_a_clean_run_deletes_every_object_it_spawned_and_reports_what_it_measured(self):
        world = World(background=5)
        model = run_hook(world)
        observations = observations_of(world)
        counters = observations["counters"]
        self.assertGreater(counters["spawned"], 10)
        self.assertEqual(counters["spawned"], counters["deleted"])
        self.assertEqual([], world.live())
        self.assertEqual(world.delete_calls, counters["deleted"])
        self.assertEqual(0, counters["live_after_release"])
        self.assertEqual(0, counters["residual_probe_types"])
        self.assertEqual((5, 5, False, True), (counters["census_total"], counters["census_scanned"],
                                               counters["census_truncated"], counters["census_complete"]))
        self.assertEqual(4, observations["observed"])
        self.assertEqual("complete", observations["status"])

    def test_every_spawn_is_non_persistent_and_native_attach_requests_type_then_slot(self):
        world = World()
        run_hook(world)
        self.assertTrue(world.create_calls)
        for _name, flags in world.create_calls:
            self.assertEqual(2 | 4, flags & (2 | 4))
        self.assertIn(("UniversalLight", SLOT_IDS["weaponFlashlight"]), world.attach_calls)
        self.assertIn(("TLRLight", SLOT_IDS["pistolFlashlight"]), world.attach_calls)
        for type_name, slot_id in world.attach_calls:
            self.assertIn(type_name, world.catalogue)
            self.assertIn(slot_id, SLOT_NAMES)

    def test_live_after_release_measures_objects_the_engine_did_not_delete(self):
        world = World(stuck=("PlainBag",))
        run_hook(world)
        counters = observations_of(world)["counters"]
        self.assertEqual(1, counters["live_after_release"])
        self.assertEqual(1, len(world.live()))

    def test_the_census_reports_leftovers_completeness_and_truncation(self):
        world = World(background=3)
        model = build_model(probe.render_hook(probe.select_targets(classification())).decode(), world)
        model.OnInit()
        world.queue.clear()
        for name in ("AK74", "UniversalLight", "PlainBag"):
            world.CreateObjectEx(S(name), None, 0)
        model.HCTLCensusResidual()
        self.assertEqual((3, 6, 6, False), (model.m_HCTLResidualProbe, model.m_HCTLCensusTotal,
                                            model.m_HCTLCensusScanned, model.m_HCTLCensusTruncated))
        self.assertEqual(3, model.m_HCTLResidualOther)
        crowded = World(background=probe.CENSUS_SCAN_LIMIT + 40)
        model = build_model(probe.render_hook(probe.select_targets(classification())).decode(), crowded)
        model.OnInit()
        model.HCTLCensusResidual()
        self.assertEqual(probe.CENSUS_SCAN_LIMIT, model.m_HCTLCensusScanned)
        self.assertEqual(probe.CENSUS_SCAN_LIMIT + 40, model.m_HCTLCensusTotal)
        self.assertTrue(model.m_HCTLCensusTruncated)

    def test_the_watchdog_ends_the_run_partial_releases_everything_and_queues_the_write(self):
        world = World()
        model = build_model(probe.render_hook(probe.select_targets(classification())).decode(), world)
        model.OnInit()
        world.queue.clear()
        model.HCTLSpawn(S("AK74"))
        model.HCTLSpawn(S("UniversalLight"))
        model.HCTLWatchdog()
        self.assertEqual("partial", model.m_HCTLStatus)
        self.assertTrue(model.m_HCTLDone)
        self.assertEqual([], world.live())
        self.assertEqual(2, model.m_HCTLDeleted)
        self.assertEqual(1, len(world.queue))
        drain(world)
        self.assertEqual("partial", observations_of(world)["status"])

    def test_a_slow_server_trips_the_watchdog_between_classes_and_the_probe_still_cleans_up(self):
        world = World(spawn_ms=15000)
        run_hook(world)
        observations = observations_of(world)
        self.assertEqual("partial", observations["status"])
        self.assertLess(observations["observed"], observations["classes"])
        self.assertEqual([], world.live())
        self.assertEqual(observations["counters"]["spawned"], observations["counters"]["deleted"])
        joined = report.build_report(classification(), observations)
        self.assertIn("probe_status_partial", joined["integrity"]["issues"])
        self.assertNotIn("qualified", {h["verdict"] for h in joined["hosts"]})

    def test_the_class_timeout_is_checked_after_every_observation_and_stops_the_class(self):
        world = World(spawn_ms=1500)
        run_hook(world, per_class_ms=2000)
        bag = host_row(observations_of(world), "PlainBag")
        self.assertTrue(bag["timed_out"])
        self.assertEqual(["Flashlight"], [light["light"] for light in bag["lights"]])

    def test_the_last_observation_overrunning_the_budget_still_marks_the_class_timed_out(self):
        world = World(spawn_ms=600)
        run_hook(world, per_class_ms=2000)
        bag = host_row(observations_of(world), "PlainBag")
        self.assertEqual(3, len(bag["lights"]))
        self.assertTrue(bag["timed_out"])

    def test_a_fast_class_is_not_marked_timed_out(self):
        world = World(spawn_ms=1)
        run_hook(world, per_class_ms=2000)
        self.assertEqual([False] * 4, [row["timed_out"] for row in observations_of(world)["hosts"]])

    def test_the_prerequisite_handguard_is_observed_on_a_fresh_host_and_cleaned_up(self):
        world = World()
        run_hook(world)
        observations = observations_of(world)
        ak74 = host_row(observations, "AK74")
        self.assertEqual({"weaponHandguardAK": (True, False, "")},
                         {p["slot"]: (p["host_has_slot"], p["rail_functional"], p["attached_type"])
                          for p in ak74["prereq"] if p["host_has_slot"]})
        self.assertEqual(sorted(slot for slot, _item in probe.PREREQUISITE_HANDGUARDS),
                         sorted(p["slot"] for p in ak74["prereq"]))
        variant = ak74["prereq_variant"]
        self.assertEqual((True, "weaponHandguardAK", "AK_RailHndgrd", True),
                         (variant["performed"], variant["slot"], variant["handguard"], variant["handguard_attached"]))
        self.assertEqual(["UniversalLight"], [light["light"] for light in variant["lights"]])
        weapon = next(s for s in variant["lights"][0]["per_slot"] if s["slot"] == "weaponFlashlight")
        plain = next(s for s in ak74["lights"] if s["light"] == "UniversalLight")
        refused = next(s for s in plain["per_slot"] if s["slot"] == "weaponFlashlight")
        self.assertEqual((False, True), (refused["can_add"], weapon["can_add"]))
        self.assertEqual({"performed": False}, host_row(observations, "Glock19")["prereq_variant"])
        self.assertEqual({"performed": False}, host_row(observations, "PlainBag")["prereq_variant"])
        self.assertEqual([], world.live())

    def test_the_variant_records_what_the_slot_actually_holds_not_the_requested_label(self):
        world = World()
        run_hook(world)
        variant = host_row(observations_of(world), "AK74")["prereq_variant"]
        self.assertEqual(("AK_RailHndgrd", True, True),
                         (variant["handguard_found_type"], variant["handguard_slot_occupied"],
                          variant["handguard_rail_functional"]))
        types = catalogue()
        types["AK_RailHndgrd"] = spec(fits=("weaponHandguardAK",), rail=False)
        world = World(types=types)
        run_hook(world)
        variant = host_row(observations_of(world), "AK74")["prereq_variant"]
        self.assertEqual((True, "AK_RailHndgrd", True, False),
                         (variant["handguard_attached"], variant["handguard_found_type"],
                          variant["handguard_slot_occupied"], variant["handguard_rail_functional"]))
        joined = report.build_report(classification(), observations_of(world))
        slot = next(h for h in joined["hosts"] if h["class"] == "AK74")["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual("pending", slot["verdict"])

    def test_a_variant_that_could_not_attach_records_an_empty_unoccupied_slot(self):
        types = catalogue()
        del types["AK_RailHndgrd"]
        world = World(types=types)
        run_hook(world)
        variant = host_row(observations_of(world), "AK74")["prereq_variant"]
        self.assertEqual((False, "", False, False),
                         (variant["handguard_attached"], variant["handguard_found_type"],
                          variant["handguard_slot_occupied"], variant["handguard_rail_functional"]))

    def test_the_synthetic_engine_refuses_bare_numbers_in_a_concatenation_so_the_hook_must_convert(self):
        for bare in (5, 1.5, True):
            with self.assertRaises(TypeError):
                S("a") + bare
            with self.assertRaises(TypeError):
                bare + S("a")
        self.assertEqual("n=5", S("n=") + number_text(5))
        self.assertEqual("r=1.5", S("r=") + number_text(1.5))

    def test_every_generated_row_statement_is_within_the_native_formula_bound_with_explicit_numbers(self):
        hook = probe.render_hook(probe.select_targets(classification())).decode()
        self.assertEqual([], probe.lint_hook(hook, explicit_numbers=True))
        self.assertLessEqual(probe.rt.max_statement_plus(hook), 8)
        self.assertLessEqual(probe.rt.MAX_STATEMENT_PLUS, 9)

    def test_the_split_row_builders_produce_the_same_observation_text_as_the_single_statement_generator(self):
        # sha256 of the observations.json text and of the printed lines, recorded from the generator that built each
        # row in one long statement (the form the native compiler refused), with the same synthetic engine rules.
        golden = {
            "default": (12184, "83dc8bf173bb699aacff98f457e80d6384337ef54862f356df97067c478474de",
                        "549837d7d62767e41db54b0693cbde69fff039ee2d7468bc751ccab83d7bb9c9", lambda: World()),
            "stuck_and_background": (12184, "63adba104be7bcd623ac429994165ad6d31895bad2c2782c4fc1aec691b2ac20",
                                     "95b2e08d2d3e4fb5969c67580597b4215082fa362cc52b0992c02b91bc30ccc7",
                                     lambda: World(stuck=("PlainBag",), background=3)),
            "class_timeout": (11124, "25b3f8b793c03418e174fa4e82761db7e30df125e179bea17ca14ac103ba5e35",
                              "6aa70f5238cc7483e6b7ae4b7ba6ce7ff312e2c6a666a5eeb714543e95d2f9fd",
                              lambda: World(spawn_ms=600)),
            "watchdog_partial": (3613, "520ef5127f687809ebce65faf6655648dfe86e06d211602693ecaa99dd441c0e",
                                 "5b28a8816f58c111cbf5892c5351008c8bc8f6cb56edbee86549df74019b77e2",
                                 lambda: World(spawn_ms=15000)),
        }
        # The variant later gained three read-back fields (handguard_found_type, handguard_slot_occupied,
        # handguard_rail_functional); everything else must still be byte-identical, so the fields are stripped here.
        # Fix round 3 added the per-host proxy facts (proxy_count, proxy_scan_complete, proxies); these hosts have no
        # proxies, so the empty facts are stripped as well. Fix round 4 added the per-host view-LOD facts, which these
        # hosts (no view LOD in the synthetic table) report as absent; fix round 5 added view_list_ok.
        # Fix round 6 added the header diagnostics line and the per-host LOD name facts (a resolution LOD only, no view LOD).
        # Round 7 replaced the view-LOD facts with the per-resolution-LOD scan: one numeric LOD "1.000" without selections.
        added = re.compile(r'"handguard_found_type":"[^"]*","handguard_slot_occupied":(?:true|false),'
                           r'"handguard_rail_functional":(?:true|false),'
                           r'|"proxy_count":0,"proxy_scan_complete":true,'
                           r'"res_enum_ok":true,"res_lod_count":1,"res_lods_scanned":1,"res_scan_complete":true,'
                           r'"res_lods":\[\{"name":"1\.000","list_ok":true,"selection_count":0,"scan_complete":true\}\],'
                           r'"lod_list_ok":true,"lod_count":1,"lod_names":\["1\.000"\],"lod_names_complete":true,'
                           r'"view_by_name":false,"proxies":\[\],'
                           r'|^"diagnostics":[^\n]*\n', re.M)
        for name, (size, output_sha, printed_sha, make) in golden.items():
            with self.subTest(scenario=name):
                world = make()
                run_hook(world)
                text = added.sub("", world.files[OUTPUT_PATH])
                self.assertEqual((size, output_sha), (len(text), hashlib.sha256(text.encode()).hexdigest()))
                self.assertEqual(printed_sha, hashlib.sha256("\n".join(world.printed).encode()).hexdigest())

    def test_a_host_that_already_holds_a_rail_handguard_needs_no_variant_and_a_plastic_one_does(self):
        types = catalogue()
        types["AK_PlasticHndgrd"] = spec(fits=("weaponHandguardAK",))
        world = World(types=types)
        model = build_model(probe.render_hook(probe.select_targets(classification())).decode(), world)
        model.OnInit()
        world.queue.clear()
        for handguard, expected_index, rail in (("AK_RailHndgrd", -1, True), ("AK_PlasticHndgrd", 0, False)):
            with self.subTest(handguard=handguard):
                gun = model.HCTLSpawn(S("AK74"))
                self.assertIsNotNone(gun.GetInventory().CreateAttachmentEx(S(handguard), SLOT_IDS["weaponHandguardAK"]))
                self.assertEqual(expected_index, model.HCTLFirstOpenPrereq(gun))
                prereq = json.loads("[" + model.HCTLHostPrereq(gun) + "]")
                owned = next(item for item in prereq if item["slot"] == "weaponHandguardAK")
                self.assertEqual((True, rail, handguard), (owned["host_has_slot"], owned["rail_functional"],
                                                           owned["attached_type"]))
        bare = model.HCTLSpawn(S("AK74"))
        self.assertEqual(0, model.HCTLFirstOpenPrereq(bare))
        self.assertEqual(-1, model.HCTLFirstOpenPrereq(model.HCTLSpawn(S("PlainBag"))))

    def test_the_generated_observations_join_into_a_report_without_integrity_issues(self):
        world = World(background=2)
        run_hook(world)
        joined = report.build_report(classification(), observations_of(world))
        self.assertEqual([], joined["integrity"]["issues"])
        verdicts = {h["class"]: h["verdict"] for h in joined["hosts"]}
        self.assertEqual({"AK74": "qualified", "Glock19": "qualified", "PlainBag": "geometry_missing",
                          "PlainHat": "geometry_missing", "RifleBase": "excluded"}, verdicts)
        ak74 = next(h for h in joined["hosts"] if h["class"] == "AK74")
        slot = ak74["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual("native_attach_with_rail_handguard_prerequisite", slot["reason"])
        self.assertTrue(slot["evidence"]["requires_prerequisite"])
        self.assertEqual("PENDING", joined["acceptance"])

    def test_a_stuck_object_and_a_truncated_census_stop_certification(self):
        for label, world in (("stuck", World(stuck=("PlainBag",))),
                             ("truncated", World(background=probe.CENSUS_SCAN_LIMIT + 5))):
            with self.subTest(label=label):
                run_hook(world)
                joined = report.build_report(classification(), observations_of(world))
                self.assertTrue(joined["integrity"]["issues"])
                self.assertNotIn("qualified", {h["verdict"] for h in joined["hosts"]})

    def test_the_watchdog_limit_is_documented_in_the_hook_and_the_module(self):
        hook = probe.render_hook(probe.select_targets(classification())).decode()
        self.assertIn("cannot interrupt a synchronous call", hook)
        self.assertIn("cannot interrupt a synchronous call", PROBE_SOURCE.read_text(encoding="utf-8"))


def proxy_types(old_evidence=False):
    """Probe-003 shaped hosts: the slot exists and the model carries proxies, but no slot selection, memory point or
    bone is reported (``old_evidence`` False). Duplicate selection names appear in the list, as in probe-003."""
    types = catalogue()
    keep = {"selections": ("light_w", "hg_ak"), "memory": ("light_w",)} if old_evidence else {}
    types["AK74"] = spec(("weaponFlashlight", "weaponHandguardAK"), proxies=(
        LIGHT_UNIVERSAL_PROXY, MUZZLE_PROXY, LIGHT_UNIVERSAL_PROXY), res=res_of(LIGHT_UNIVERSAL_PROXY, MUZZLE_PROXY),
        **keep)
    types["Glock19"] = spec(("pistolFlashlight",), proxies=(LIGHT_TLR_PROXY,), res=res_of(LIGHT_TLR_PROXY),
                            **({"selections": ("light_p",)} if old_evidence else {}))
    return types


def res_of(*proxies):
    """Resolution-LOD selection names as the engine would hold them (probe-005: backslashes only): the proxy selections,
    in the engine's backslash style and upper case (the hook normalises both), after unrelated selections."""
    return ("components", "zbytek") + tuple(name.replace("/", "\\").upper() for name in proxies)


class ProxyEvidenceHookTests(unittest.TestCase):
    """Fix round 3: the hook joins each proxy selection of the host model to its CfgNonAIVehicles entry."""

    def run_world(self, types=None, config=None, slots=_NoSelectionSlots):
        world = World(types=types or proxy_types(), config=config)
        run_hook(world, slots=slots)
        return world, observations_of(world)

    def test_each_host_lists_its_unique_proxies_with_their_config_join(self):
        _world, observations = self.run_world()
        row = host_row(observations, "AK74")
        self.assertEqual((2, True), (row["proxy_count"], row["proxy_scan_complete"]))
        self.assertEqual([LIGHT_UNIVERSAL_PROXY, MUZZLE_PROXY], [p["selection"] for p in row["proxies"]])
        light, muzzle = row["proxies"]
        self.assertEqual(("Proxyweaponlight_universal", True, "/dz/weapons/attachments/light/weaponlight_universal.p3d",
                          ["weaponFlashlight"]),
                         (light["cfg_class"], light["cfg_exists"], light["model"], light["inventory_slots"]))
        self.assertEqual(("Proxymuzzle_flash_rifle_m4", False, "", []),
                         (muzzle["cfg_class"], muzzle["cfg_exists"], muzzle["model"], muzzle["inventory_slots"]))

    def test_a_text_inventory_slot_is_read_when_the_array_is_empty(self):
        _world, observations = self.run_world()
        glock = host_row(observations, "Glock19")["proxies"][0]
        self.assertEqual((True, ["pistolFlashlight"]), (glock["cfg_exists"], glock["inventory_slots"]))

    def test_a_host_without_proxies_reports_none(self):
        _world, observations = self.run_world()
        row = host_row(observations, "PlainBag")
        self.assertEqual((0, True, []), (row["proxy_count"], row["proxy_scan_complete"], row["proxies"]))

    def test_unrelated_selections_are_not_proxies(self):
        types = proxy_types()
        types["PlainBag"] = spec(selections=("light_w", "xproxy:/a/b.001", "proxyfoo", "Proxy:/dz/x/y_z.003"))
        _world, observations = self.run_world(types)
        row = host_row(observations, "PlainBag")
        self.assertEqual(["Proxy:/dz/x/y_z.003"], [p["selection"] for p in row["proxies"]])
        self.assertEqual("Proxyy_z", row["proxies"][0]["cfg_class"])

    def test_the_listed_rows_and_the_scan_are_bounded(self):
        many = tuple("proxy:/dz/x/part%03d.001" % number for number in range(40))
        types = proxy_types()
        types["PlainBag"] = spec(proxies=many)
        types["PlainHat"] = spec(proxies=tuple("proxy:/dz/x/part%03d.001" % number for number in range(600)))
        _world, observations = self.run_world(types)
        bag, hat = host_row(observations, "PlainBag"), host_row(observations, "PlainHat")
        self.assertEqual((40, 24, True), (bag["proxy_count"], len(bag["proxies"]), bag["proxy_scan_complete"]))
        self.assertEqual((512, 24, False), (hat["proxy_count"], len(hat["proxies"]), hat["proxy_scan_complete"]))

    def test_the_hook_cites_the_native_api_locations_it_uses(self):
        hook = probe.render_hook(probe.select_targets(classification())).decode()
        for cite in ("Game.c:449", "Game.c:558", "Game.c:612", "constants.c:237", "SceneEditorMenu.c:1362",
                     "SceneEditorMenu.c:1385", "EntityAI.c:3996", "AttachmentsOutOfReach.c", "EnString.c:253",
                     "Object.c:98", "Object.c:106", "gameplay.c:179", "gameplay.c:184", "gameplay.c:185", "gameplay.c:186",
                     "gameplay.c:188", "gameplay.c:207", "gameplay.c:216", "gameplay.c:218", "EnScript.c:385"):
            with self.subTest(cite=cite):
                self.assertIn(cite, hook)

    def test_without_selection_evidence_the_proxy_join_qualifies_through_the_report(self):
        world, observations = self.run_world()
        self.assertTrue(all(not slot["selection_on_model"] and not slot["memory_point"] and slot["bone_index"] == -1
                            and slot["selection"] == "" for row in observations["hosts"] for slot in row["slots"]))
        joined = report.build_report(classification(), observations)
        self.assertEqual([], joined["integrity"]["issues"])
        by_name = {h["class"]: h for h in joined["hosts"]}
        self.assertEqual("qualified", by_name["AK74"]["verdict"])
        self.assertEqual("qualified", by_name["Glock19"]["verdict"])
        self.assertEqual("native_attach_with_resolution_lod_proxy_slot_and_rail_handguard_prerequisite",
                         by_name["AK74"]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]["reason"])
        self.assertEqual("native_attach_with_resolution_lod_proxy_slot",
                         by_name["Glock19"]["lights"]["TLRLight"]["slots"]["pistolFlashlight"]["reason"])
        self.assertEqual("PENDING", joined["acceptance"])
        self.assertEqual({axis: "pending" for axis in report.UNOBSERVED_AXES}, joined["unobserved_axes"])
        self.assertEqual([], world.live())

    def test_a_proxy_without_a_config_entry_is_never_inferred_from_its_name(self):
        _world, observations = self.run_world(config={})
        joined = report.build_report(classification(), observations)
        by_name = {h["class"]: h for h in joined["hosts"]}
        for name in ("AK74", "Glock19"):
            self.assertEqual("pending", by_name[name]["verdict"], name)
            self.assertIn("proxy_config_missing", by_name[name]["reasons"], name)
        self.assertEqual(0, joined["denominators"]["qualified"])

    def test_a_config_whose_slot_or_model_disagrees_does_not_qualify(self):
        wrong_slot = proxy_config()
        wrong_slot["CfgNonAIVehicles Proxyweaponlight_universal"]["inventorySlot"] = ["helmetFlashlight"]
        wrong_model = proxy_config()
        wrong_model["CfgNonAIVehicles Proxyweaponlight_universal"]["model"] = "\\dz\\weapons\\attachments\\light\\other.p3d"
        for label, config in (("wrong slot", wrong_slot), ("wrong model", wrong_model)):
            with self.subTest(label):
                _world, observations = self.run_world(config=config)
                joined = report.build_report(classification(), observations)
                ak = next(h for h in joined["hosts"] if h["class"] == "AK74")
                self.assertNotEqual("qualified", ak["verdict"])
                self.assertNotIn("native_attach_with_resolution_lod_proxy_slot_and_rail_handguard_prerequisite", ak["reasons"])

    def test_the_slot_selection_evidence_is_still_reported_unchanged(self):
        world, observations = self.run_world(proxy_types(old_evidence=True), slots=_Slots)
        slot = next(s for s in host_row(observations, "AK74")["slots"] if s["slot"] == "weaponFlashlight")
        self.assertEqual((True, True, "light_w"), (slot["selection_on_model"], slot["memory_point"], slot["selection"]))
        self.assertEqual([], world.live())


class RoundFourProxyHookTests(unittest.TestCase):
    """Fix round 4 (hc-taped-light-review-004): per-row slot bookkeeping, run through the synthetic engine and then
    through the report. The synthetic engine models the signatures cited in the hook; it establishes nothing about DayZ
    behaviour."""

    SLOT_CONFIG = "CfgNonAIVehicles Proxyweaponlight_universal"

    def run_world(self, types=None, config=None):
        world = World(types=types or proxy_types(), config=config)
        run_hook(world, slots=_NoSelectionSlots)
        return world, observations_of(world)

    def ak_slot(self, observations):
        joined = report.build_report(classification(), observations)
        ak = next(h for h in joined["hosts"] if h["class"] == "AK74")
        return ak["lights"]["UniversalLight"]["slots"]["weaponFlashlight"], joined

    def nine_slot_world(self, last="weaponFlashlight"):
        types = proxy_types()
        types["AK74"]["proxies"] = (LIGHT_UNIVERSAL_PROXY,)
        config = proxy_config()
        config[self.SLOT_CONFIG]["inventorySlot"] = ["unrelated%d" % number for number in range(8)] + [last]
        return types, config

    def test_a_slot_omitted_by_the_per_proxy_cap_stays_pending_end_to_end(self):
        types, config = self.nine_slot_world()
        _world, observations = self.run_world(types, config)
        row = host_row(observations, "AK74")["proxies"][0]
        self.assertEqual((8, 9, False), (len(row["inventory_slots"]), row["slot_count"], row["slot_scan_complete"]))
        slot, joined = self.ak_slot(observations)
        self.assertEqual(("pending", "proxy_slot_list_truncated"), (slot["verdict"], slot["reason"]))
        self.assertEqual("PENDING", joined["acceptance"])

    def test_a_complete_slot_list_reports_its_count_and_a_text_slot_counts_one(self):
        _world, observations = self.run_world()
        light = host_row(observations, "AK74")["proxies"][0]
        glock = host_row(observations, "Glock19")["proxies"][0]
        muzzle = host_row(observations, "AK74")["proxies"][1]
        self.assertEqual((1, True), (light["slot_count"], light["slot_scan_complete"]))
        self.assertEqual((1, True), (glock["slot_count"], glock["slot_scan_complete"]))
        self.assertEqual((0, True), (muzzle["slot_count"], muzzle["slot_scan_complete"]))

    def test_the_slot_list_is_exactly_the_eight_listed_when_the_config_holds_exactly_eight(self):
        types, config = self.nine_slot_world()
        config[self.SLOT_CONFIG]["inventorySlot"] = ["weaponFlashlight"] + ["unrelated%d" % number for number in range(7)]
        _world, observations = self.run_world(types, config)
        row = host_row(observations, "AK74")["proxies"][0]
        self.assertEqual((8, 8, True), (len(row["inventory_slots"]), row["slot_count"], row["slot_scan_complete"]))
        slot, _joined = self.ak_slot(observations)
        self.assertEqual("qualified", slot["verdict"])

    def test_a_slot_inside_the_cap_still_qualifies_when_more_slots_were_dropped(self):
        types, config = self.nine_slot_world()
        config[self.SLOT_CONFIG]["inventorySlot"] = ["weaponFlashlight"] + ["unrelated%d" % number for number in range(11)]
        _world, observations = self.run_world(types, config)
        slot, _joined = self.ak_slot(observations)
        self.assertEqual(("qualified", "native_attach_with_resolution_lod_proxy_slot_and_rail_handguard_prerequisite"),
                         (slot["verdict"], slot["reason"]))

    def test_the_proxy_match_is_the_whole_normalised_proxy_path_never_a_substring(self):
        """Review 005: AttachmentsOutOfReach.c matches by Contains(), which lets weaponlight_universal_extra stand in for
        weaponlight_universal. The hook accepts a resolution-LOD selection only when it is proxy:<path>.<digits> and its
        whole normalised path (lower case, forward slashes, no leading slash, no .p3d, prefix and instance suffix
        removed) equals the model path, exactly."""
        base = "/dz/weapons/attachments/light/weaponlight_universal"
        types = proxy_types()
        cases = {"longer model name": ("proxy:" + base + "_extra.001", False),
                 "version suffix": ("xx\\DZ\\Weapons\\Attachments\\Light\\WeaponLight_Universal_v2", False),
                 "longer directory": ("proxy:/xx" + base + ".001", False),
                 "generic named selection": ("label" + base, False),
                 "generic selection with an instance": ("label" + base + ".001", False),
                 "no instance suffix": ("proxy:" + base, False),
                 "non-numeric instance suffix": ("proxy:" + base + ".garbage", False),
                 "different directory": ("proxy:\\dz\\weapons\\attachments\\light2\\weaponlight_universal.001", False),
                 "only the basename": ("proxy:weaponlight_universal.001", False),
                 "backslashes and upper case": ("PROXY:\\DZ\\WEAPONS\\ATTACHMENTS\\LIGHT\\WEAPONLIGHT_UNIVERSAL.007", True),
                 "no leading slash": ("proxy:" + base[1:] + ".001", True),
                 "another instance number": ("proxy:" + base + ".12", True)}
        for label, (name, expected) in cases.items():
            with self.subTest(label):
                types["AK74"] = dict(types["AK74"], res=("components", name))
                _world, observations = self.run_world(types)
                entry = host_row(observations, "AK74")["proxies"][0]["res_lods"][0]
                self.assertEqual(expected, entry["selection"] != "", label)
                self.assertEqual(expected, self.ak_slot(observations)[0]["verdict"] == "qualified", label)

    def test_a_coincidental_name_listed_first_does_not_hide_the_genuine_selection_after_it(self):
        base = "/dz/weapons/attachments/light/weaponlight_universal"
        types = proxy_types()
        types["AK74"] = dict(types["AK74"], res=("components", "proxy:" + base + "_extra.001", "label" + base,
                                                 "proxy:" + base + ".003"))
        _world, observations = self.run_world(types)
        entry = host_row(observations, "AK74")["proxies"][0]["res_lods"][0]
        self.assertEqual("proxy:" + base + ".003", entry["selection"])
        self.assertEqual("qualified", self.ak_slot(observations)[0]["verdict"])

    def test_a_missing_config_model_never_matches_a_resolution_lod(self):
        config = proxy_config()
        config[self.SLOT_CONFIG]["model"] = ""
        _world, observations = self.run_world(config=config)
        light = host_row(observations, "AK74")["proxies"][0]
        self.assertEqual(("", "", False), (light["model"], light["res_lods"][0]["selection"], light["res_lods"][0]["vertex_ok"]))
        self.assertNotEqual("qualified", self.ak_slot(observations)[0]["verdict"])


class ResolutionLodHookTests(unittest.TestCase):
    """Round 7 (taped-light-probe-005): the dedicated server has no LOD named "view"; the names are resolution LODs ("0",
    "1", "1.000"), geometry, memory, landContact, geometryView, geometryFire and VIEW_PILOT. The hook therefore scans only
    the LODs whose WHOLE name is a non-negative number and reads their selections. The synthetic engine proves the hook's
    own logic and the join to the report; it establishes nothing about DayZ behaviour."""

    ALL_KINDS = ("geometry", "memory", "view", "VIEW_PILOT", "landContact", "geometryView", "geometryFire")

    def run_world(self, types=None, config=None):
        world = World(types=types or proxy_types(), config=config)
        run_hook(world, slots=_NoSelectionSlots)
        return world, observations_of(world)

    def ak_slot(self, observations):
        joined = report.build_report(classification(), observations)
        ak = next(h for h in joined["hosts"] if h["class"] == "AK74")
        return ak["lights"]["UniversalLight"]["slots"]["weaponFlashlight"], joined

    def ak_with(self, **changes):
        types = proxy_types()
        types["AK74"] = dict(types["AK74"], **changes)
        return self.run_world(types)

    def reason(self, observations):
        slot, _joined = self.ak_slot(observations)
        return slot["verdict"], slot["reason"]

    def test_each_host_reports_the_resolution_scan_and_each_proxy_row_its_per_lod_selection_and_first_vertex(self):
        _world, observations = self.run_world()
        ak = host_row(observations, "AK74")
        self.assertEqual((True, 1, 1, True), (ak["res_enum_ok"], ak["res_lod_count"], ak["res_lods_scanned"],
                                              ak["res_scan_complete"]))
        self.assertEqual([{"name": "1.000", "list_ok": True, "selection_count": 4, "scan_complete": True}], ak["res_lods"])
        light, muzzle = ak["proxies"]
        self.assertEqual([{"name": "1.000", "list_ok": True, "selection": LIGHT_UNIVERSAL_PROXY, "vertex_ok": True,
                           "vertex": ["0.5", "0.25", "-1.5"]}], light["res_lods"])
        self.assertEqual([{"name": "1.000", "list_ok": True, "selection": "", "vertex_ok": False, "vertex": []}],
                         muzzle["res_lods"])
        plain = host_row(observations, "PlainBag")
        self.assertEqual((True, 1, True, []), (plain["res_enum_ok"], plain["res_lod_count"], plain["res_scan_complete"],
                                               plain["proxies"]))
        self.assertEqual([{"name": "1.000", "list_ok": True, "selection_count": 0, "scan_complete": True}], plain["res_lods"])
        self.assertNotIn("view_lod", ak)
        self.assertNotIn("view_selection", light)

    def test_a_server_without_a_view_lod_qualifies_from_the_resolution_lod_with_the_evidence_reported(self):
        """The native shape of probe-005: no LOD named "view", the proxy selection in a numeric LOD."""
        _world, observations = self.run_world()
        slot, joined = self.ak_slot(observations)
        self.assertEqual(("qualified", "native_attach_with_resolution_lod_proxy_slot_and_rail_handguard_prerequisite"),
                         (slot["verdict"], slot["reason"]))
        self.assertEqual("resolution_lod_proxy_slot", slot["evidence"]["model_evidence"])
        self.assertEqual(("1.000", LIGHT_UNIVERSAL_PROXY, [0.5, 0.25, -1.5]),
                         (slot["evidence"]["resolution_lod"], slot["evidence"]["resolution_selection"],
                          slot["evidence"]["resolution_vertex"]))
        self.assertEqual("PENDING", joined["acceptance"])
        self.assertEqual([], joined["integrity"]["issues"])
        self.assertEqual({axis: "pending" for axis in report.UNOBSERVED_AXES}, joined["unobserved_axes"])

    def test_only_lods_with_a_whole_numeric_name_are_scanned_and_every_other_lod_is_never_asked_for_selections(self):
        proxy_names = res_of(LIGHT_UNIVERSAL_PROXY, MUZZLE_PROXY)
        lods = (("geometry", proxy_names), ("0", ()), ("memory", proxy_names), ("1", ()), ("view", proxy_names),
                ("VIEW_PILOT", proxy_names), ("1.000", proxy_names), ("landContact", proxy_names),
                ("geometryView", proxy_names), ("geometryFire", proxy_names))
        world, observations = self.ak_with(lods=lods)
        ak = host_row(observations, "AK74")
        self.assertEqual(["0", "1", "1.000"], [item["name"] for item in ak["res_lods"]])
        self.assertEqual((True, 3, 3, True), (ak["res_enum_ok"], ak["res_lod_count"], ak["res_lods_scanned"],
                                              ak["res_scan_complete"]))
        self.assertFalse({"geometry", "memory", "view", "VIEW_PILOT", "landContact", "geometryView", "geometryFire"}
                         & set(world.selection_log))
        self.assertEqual(1, world.selection_log.count("0"))
        self.assertEqual(1, world.selection_log.count("1"))
        light = ak["proxies"][0]
        self.assertEqual([("0", ""), ("1", ""), ("1.000", LIGHT_UNIVERSAL_PROXY)],
                         [(item["name"], item["selection"]) for item in light["res_lods"]])
        self.assertEqual(("qualified", "native_attach_with_resolution_lod_proxy_slot_and_rail_handguard_prerequisite"),
                         self.reason(observations))

    def test_a_proxy_that_only_a_non_numeric_lod_holds_is_never_evidence(self):
        names = res_of(LIGHT_UNIVERSAL_PROXY)
        for kind in self.ALL_KINDS:
            with self.subTest(kind):
                world, observations = self.ak_with(lods=(("1.000", ()), (kind, names)))
                self.assertEqual(("pending", "resolution_proxy_missing"), self.reason(observations))
                self.assertNotIn(kind, world.selection_log)
        _world, observations = self.ak_with(res=(), view=names)          # the old decoy: a LOD named "view"
        self.assertEqual(("pending", "resolution_proxy_missing"), self.reason(observations))
        self.assertTrue(host_row(observations, "AK74")["view_by_name"])

    def test_the_numeric_name_rule_accepts_digits_with_at_most_one_inner_dot_and_nothing_else(self):
        model = build_model(probe.render_hook(probe.select_targets(classification())).decode(), World())
        model.OnInit()
        for name in ("0", "1", "1.000", "10", "0.5", "01", "123456"):
            with self.subTest(accepted=name):
                self.assertTrue(model.HCTLIsNumericName(S(name)))
        for name in ("", "geometry", "memory", "view", "View", "VIEW_PILOT", "landContact", "geometryView", "geometryFire",
                     "-1", "+1", "1e3", "1.", ".5", ".", "1.0.0", "0x10", " 1", "1 ", "1_000", "res1", "1res", "1.000 "):
            with self.subTest(refused=name):
                self.assertFalse(model.HCTLIsNumericName(S(name)))

    def test_a_listed_lod_without_the_proxy_selection_is_pending_proxy_missing_and_no_numeric_lod_is_pending_absent(self):
        for label, changes, expected in (
                ("proxy not in the lod", dict(res=("components", "proxy:\\dz\\other\\thing.001")),
                 ("pending", "resolution_proxy_missing")),
                ("empty lod", dict(res=()), ("pending", "resolution_proxy_missing")),
                ("only non-numeric lods", dict(lods=(("geometry", res_of(LIGHT_UNIVERSAL_PROXY)), ("memory", ()))),
                 ("pending", "resolution_lod_absent")),
                ("no lods at all", dict(lods=()), ("pending", "resolution_lod_absent"))):
            with self.subTest(label):
                _world, observations = self.ak_with(**changes)
                self.assertEqual(expected, self.reason(observations), label)
                self.assertNotIn("qualified", {h["verdict"] for h in report.build_report(classification(), observations)["hosts"]
                                               if h["class"] == "AK74"})

    def test_a_selection_without_a_first_vertex_is_pending_vertex_missing(self):
        _world, observations = self.ak_with(res_no_vertex=res_of(LIGHT_UNIVERSAL_PROXY))
        entry = host_row(observations, "AK74")["proxies"][0]["res_lods"][0]
        self.assertEqual((LIGHT_UNIVERSAL_PROXY, False, []), (entry["selection"], entry["vertex_ok"], entry["vertex"]))
        self.assertEqual(("pending", "resolution_vertex_missing"), self.reason(observations))

    def test_any_one_numeric_lod_holding_the_proxy_is_enough_and_a_repeated_name_is_scanned_each_time(self):
        names = res_of(LIGHT_UNIVERSAL_PROXY)
        for label, lods in (("second lod", (("0", ()), ("1", names))), ("first lod", (("0", names), ("1", ()))),
                            ("repeated name", (("1", ()), ("1", names))),
                            ("repeated name, first holds it", (("1", names), ("1", ())))):
            with self.subTest(label):
                world, observations = self.ak_with(lods=lods)
                ak = host_row(observations, "AK74")
                self.assertEqual([name for name, _ in lods], [item["name"] for item in ak["res_lods"]])
                self.assertEqual(2, len(ak["proxies"][0]["res_lods"]))
                self.assertEqual("qualified", self.reason(observations)[0], label)
        world, _observations = self.ak_with(lods=(("1", ()), ("1", names)))
        self.assertEqual(2, world.selection_log.count("1"))

    def test_the_scan_of_each_lod_runs_once_per_host_and_never_once_per_proxy_row(self):
        world, observations = self.ak_with(lods=(("0", res_of(LIGHT_UNIVERSAL_PROXY, MUZZLE_PROXY)), ("1", ())))
        self.assertEqual(2, len(host_row(observations, "AK74")["proxies"]))
        self.assertEqual(1, world.selection_log.count("0"))
        self.assertEqual(1, world.selection_log.count("1"))

    def test_the_lod_scan_is_bounded_at_sixteen_lods_and_a_cut_scan_without_the_selection_is_pending_truncated(self):
        names = res_of(LIGHT_UNIVERSAL_PROXY)
        many = tuple((str(number), ()) for number in range(20))
        world, observations = self.ak_with(lods=many)
        ak = host_row(observations, "AK74")
        self.assertEqual((True, 20, 16, False), (ak["res_enum_ok"], ak["res_lod_count"], ak["res_lods_scanned"],
                                                 ak["res_scan_complete"]))
        self.assertEqual(16, len(ak["res_lods"]))
        self.assertFalse({str(number) for number in range(16, 20)} & set(world.selection_log))
        self.assertEqual(("pending", "resolution_evidence_truncated"), self.reason(observations))
        late = many[:17] + (("17", names),) + many[18:]
        _world, observations = self.ak_with(lods=late)
        self.assertEqual(("pending", "resolution_evidence_truncated"), self.reason(observations))
        early = (("3", names),) + many[:3] + many[4:]
        _world, observations = self.ak_with(lods=early)
        self.assertEqual("qualified", self.reason(observations)[0])     # a complete LOD that holds it is enough

    def test_the_selection_scan_is_bounded_at_512_and_says_when_it_was_cut(self):
        filler = tuple("filler%03d" % number for number in range(600))
        _world, observations = self.ak_with(res=filler + res_of(LIGHT_UNIVERSAL_PROXY))
        ak = host_row(observations, "AK74")
        self.assertEqual([{"name": "1.000", "list_ok": True, "selection_count": 603, "scan_complete": False}], ak["res_lods"])
        self.assertFalse(ak["res_scan_complete"])
        self.assertEqual("", ak["proxies"][0]["res_lods"][0]["selection"])
        self.assertEqual(("pending", "resolution_evidence_truncated"), self.reason(observations))
        _world, observations = self.ak_with(res=res_of(LIGHT_UNIVERSAL_PROXY) + filler)
        self.assertEqual(LIGHT_UNIVERSAL_PROXY, host_row(observations, "AK74")["proxies"][0]["res_lods"][0]["selection"])
        self.assertEqual(("pending", "resolution_evidence_truncated"), self.reason(observations))   # found, but the LOD was cut
        _world, observations = self.ak_with(res=tuple("filler%03d" % number for number in range(512)) + res_of(LIGHT_UNIVERSAL_PROXY)[2:])
        ak = host_row(observations, "AK74")
        self.assertEqual((513, False), (ak["res_lods"][0]["selection_count"], ak["res_lods"][0]["scan_complete"]))
        _world, observations = self.ak_with(res=tuple("filler%03d" % number for number in range(511)) + (res_of(LIGHT_UNIVERSAL_PROXY)[2],))
        ak = host_row(observations, "AK74")
        self.assertEqual((512, True), (ak["res_lods"][0]["selection_count"], ak["res_lods"][0]["scan_complete"]))
        self.assertEqual("qualified", self.reason(observations)[0])

    def test_a_failed_lod_list_is_unknown_and_its_out_array_is_ignored(self):
        world, observations = self.ak_with(lods_unlisted=True)
        ak = host_row(observations, "AK74")
        self.assertEqual((False, 0, 0, False, []), (ak["res_enum_ok"], ak["res_lod_count"], ak["res_lods_scanned"],
                                                    ak["res_scan_complete"], ak["res_lods"]))
        self.assertEqual((False, 0, []), (ak["lod_list_ok"], ak["lod_count"], ak["lod_names"]))
        self.assertNotIn("9", world.selection_log)      # the junk LOD left in the out array was never read
        self.assertEqual([], ak["proxies"][0]["res_lods"])
        self.assertEqual(("pending", "resolution_enumeration_failed"), self.reason(observations))

    def test_more_than_128_lods_are_not_scanned_and_are_reported_as_not_listed(self):
        names = res_of(LIGHT_UNIVERSAL_PROXY)
        world, observations = self.ak_with(lods=tuple((str(number), names) for number in range(129)))
        ak = host_row(observations, "AK74")
        self.assertEqual((False, 0, 0, False), (ak["res_enum_ok"], ak["res_lod_count"], ak["res_lods_scanned"],
                                                ak["res_scan_complete"]))
        self.assertEqual((False, 0), (ak["lod_list_ok"], ak["lod_count"]))
        self.assertNotIn("5", world.selection_log)
        self.assertEqual(("pending", "resolution_enumeration_failed"), self.reason(observations))
        _world, observations = self.ak_with(lods=tuple((str(number), names) for number in range(128)))
        self.assertEqual((True, 128, 16), (host_row(observations, "AK74")["res_enum_ok"],
                                           host_row(observations, "AK74")["res_lod_count"],
                                           host_row(observations, "AK74")["res_lods_scanned"]))

    def test_a_failed_selection_list_is_reported_unknown_and_its_out_array_is_ignored(self):
        """LOD.GetSelections (gameplay.c:216) returns bool and says nothing about its out array on failure. The synthetic
        engine leaves the matching selections in the out array of a failed call, as a native failure might."""
        _world, observations = self.ak_with(res_unlisted=True)
        ak = host_row(observations, "AK74")
        self.assertEqual([{"name": "1.000", "list_ok": False, "selection_count": 0, "scan_complete": False}], ak["res_lods"])
        self.assertEqual((True, 1, 1, False), (ak["res_enum_ok"], ak["res_lod_count"], ak["res_lods_scanned"],
                                               ak["res_scan_complete"]))
        self.assertEqual([{"name": "1.000", "list_ok": False, "selection": "", "vertex_ok": False, "vertex": []}],
                         ak["proxies"][0]["res_lods"])
        self.assertEqual(("pending", "resolution_enumeration_failed"), self.reason(observations))

    def test_one_failed_lod_list_keeps_a_match_in_another_complete_lod_valid_but_a_miss_is_unknown(self):
        names = res_of(LIGHT_UNIVERSAL_PROXY)
        original = ModelLod.GetSelections

        def fail_first(lod, out):
            result = original(lod, out)
            return result and lod.name != "0"
        with mock.patch.object(ModelLod, "GetSelections", fail_first):
            world = World(types=dict(proxy_types(), AK74=dict(proxy_types()["AK74"], lods=(("0", names), ("1", names)))))
            run_hook(world, slots=_NoSelectionSlots)
            self.assertEqual("qualified", self.reason(observations_of(world))[0])
            world = World(types=dict(proxy_types(), AK74=dict(proxy_types()["AK74"], lods=(("0", names), ("1", ())))))
            run_hook(world, slots=_NoSelectionSlots)
            self.assertEqual(("pending", "resolution_enumeration_failed"), self.reason(observations_of(world)))

    def test_the_selection_out_array_is_cleared_before_every_call_and_again_after_a_failure(self):
        """array.Clear is EnScript.c:385 (class array<Class T>, proto native void Clear())."""
        hook = probe.render_hook(probe.select_targets(classification())).decode()
        self.assertEqual(1, hook.count(".GetSelections("))
        call = hook.index(".GetSelections(")
        self.assertIn("lodSelections.Clear();", hook[:call])
        self.assertRegex(hook[call:], r"(?s)\A[^;]*;\s*listedFlag = 1;\s*if \(selectionsListed == false\)\s*\{\s*"
                                      r"listedFlag = 0;\s*lodSelections\.Clear\(\);")
        self.assertIn("EnScript.c:385", hook)

    def test_the_resolution_facts_are_emitted_for_every_host_and_stay_within_the_json_contract(self):
        _world, observations = self.run_world()
        for row in observations["hosts"]:
            if row.get("spawned"):
                self.assertEqual(bool, type(row["res_enum_ok"]), row["class"])
                self.assertEqual(int, type(row["res_lod_count"]), row["class"])
                self.assertEqual(int, type(row["res_lods_scanned"]), row["class"])
                self.assertEqual(bool, type(row["res_scan_complete"]), row["class"])
                for entry in row["res_lods"]:
                    self.assertEqual((str, bool, int, bool), tuple(type(entry[key]) for key in
                                                                  ("name", "list_ok", "selection_count", "scan_complete")))
                for item in row["proxies"]:
                    for entry in item["res_lods"]:
                        self.assertTrue(all(isinstance(number, str) for number in entry["vertex"]))

    def test_the_old_view_facts_are_gone_and_every_consumed_resolution_key_is_emitted_by_the_hook(self):
        hook = probe.render_hook(probe.select_targets(classification())).decode()
        for key in ("view_lod", "view_selection_count", "view_scan_complete", "view_list_ok", "view_selection",
                    "view_vertex_ok", "view_vertex"):
            self.assertNotIn('HCTLKey("%s")' % key, hook, key)
        for key in ("res_enum_ok", "res_lod_count", "res_lods_scanned", "res_scan_complete", "res_lods", "name", "list_ok",
                    "selection_count", "scan_complete", "selection", "vertex_ok", "vertex", "view_by_name"):
            self.assertIn('HCTLKey("%s")' % key, hook, key)
            self.assertIn(key, report.CONSUMED_KEYS, key)

    def test_the_new_natives_are_cited_and_a_view_lod_is_not_a_gate_any_more(self):
        hook = probe.render_hook(probe.select_targets(classification())).decode()
        for cite in ("Object.c:98", "Object.c:101", "gameplay.c:203", "gameplay.c:216", "gameplay.c:179", "gameplay.c:184",
                     "gameplay.c:185", "gameplay.c:186", "gameplay.c:188", "EnString.c:240", "EnString.c:271",
                     "EnScript.c:380", "EnScript.c:385", "EnScript.c:394", "EnScript.c:399", "EnScript.c:407"):
            with self.subTest(cite=cite):
                self.assertIn(cite, hook)
        self.assertNotIn("HCTLViewLod", hook)
        self.assertNotIn("HCTLViewRow", hook)


SELF_TEST_SAMPLE = "proxy:/dz/a/b.001"


class RoundSixNativeEvidenceTests(unittest.TestCase):
    """Fix round 6 (taped-light-probe-004): cfg_class kept the whole path ("Proxy/dz/weapons/.../weaponlight_universal"),
    which a working LastIndexOf("/") could not have produced from forward slashes. Round 7 (probe-005) measured IndexOf,
    LastIndexOf and IndexOfFrom as correct and the raw selection names as backslash-only. The synthetic engine here
    proves only the hook's own logic: the hook must not depend on LastIndexOf, must emit what it tried and what the
    engine answered, and must report the native LOD names."""

    def run_world(self, types=None, config=None):
        world = World(types=types or proxy_types(), config=config)
        run_hook(world, slots=_NoSelectionSlots)
        return world, observations_of(world)

    def backslash_types(self):
        types = proxy_types()
        types["AK74"] = dict(types["AK74"], proxies=tuple(name.replace("/", "\\") for name in types["AK74"]["proxies"]))
        return types

    def test_the_header_carries_the_string_self_test_with_every_result_as_the_engine_gave_it(self):
        _world, observations = self.run_world()
        test = observations["diagnostics"]["string_self_test"]
        self.assertEqual(SELF_TEST_SAMPLE, test["sample"])
        self.assertEqual({"first_slash": 6, "last_slash": 11, "first_dot": 13, "last_dot": 13, "from_slash_7": 9,
                          "from_slash_10": 11, "from_slash_12": -1, "from_dot_0": 13, "loop_last_slash": 11,
                          "loop_last_dot": 13, "bs_length": 17, "bs_first": 6, "bs_last": 11, "bs_loop_last": 11,
                          "bs_count": 3, "slash_code_length": 1}, {k: v for k, v in test.items() if k != "sample"})

    def test_the_self_test_reports_a_native_last_index_of_that_disagrees_instead_of_hiding_it(self):
        with mock.patch.object(S, "LastIndexOf", lambda self, sample: -1):
            _world, observations = self.run_world()
        test = observations["diagnostics"]["string_self_test"]
        self.assertEqual((-1, -1, -1), (test["last_slash"], test["last_dot"], test["bs_last"]))
        self.assertEqual((11, 13, 11, 6), (test["loop_last_slash"], test["loop_last_dot"], test["bs_loop_last"],
                                           test["first_slash"]))

    def test_the_base_name_is_derived_without_last_index_of_for_slash_and_backslash_names(self):
        for label, types in (("forward slashes", proxy_types()), ("raw backslashes", self.backslash_types())):
            with self.subTest(label), mock.patch.object(S, "LastIndexOf", lambda self, sample: -1):
                _world, observations = self.run_world(types)
                light, muzzle = host_row(observations, "AK74")["proxies"]
                self.assertEqual(("Proxyweaponlight_universal", True, "/dz/weapons/attachments/light/weaponlight_universal.p3d"),
                                 (light["cfg_class"], light["cfg_exists"], light["model"]), label)
                self.assertEqual(("Proxymuzzle_flash_rifle_m4", False), (muzzle["cfg_class"], muzzle["cfg_exists"]), label)
                self.assertEqual("proxy:/dz/weapons/attachments/light/weaponlight_universal.001", light["selection"], label)
                joined = report.build_report(classification(), observations)
                ak = next(h for h in joined["hosts"] if h["class"] == "AK74")
                slot = ak["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
                self.assertEqual("qualified", slot["verdict"], label)

    def test_each_proxy_row_counts_the_raw_separators_so_a_backslash_name_is_measured_not_guessed(self):
        _world, observations = self.run_world(self.backslash_types())
        light = host_row(observations, "AK74")["proxies"][0]
        self.assertEqual((0, 5), (light["sep_slash"], light["sep_backslash"]))
        _world, observations = self.run_world()
        light = host_row(observations, "AK74")["proxies"][0]
        self.assertEqual((5, 0), (light["sep_slash"], light["sep_backslash"]))
        types = proxy_types()
        types["PlainBag"] = spec(proxies=("proxy:dz\\mixed/part.002",))
        _world, observations = self.run_world(types)
        self.assertEqual((1, 1), tuple(host_row(observations, "PlainBag")["proxies"][0][k] for k in ("sep_slash", "sep_backslash")))

    def test_each_proxy_row_lists_the_config_names_it_tried_with_the_engine_answer_for_each(self):
        _world, observations = self.run_world()
        light, muzzle = host_row(observations, "AK74")["proxies"]
        self.assertEqual((["Proxyweaponlight_universal", "weaponlight_universal"], [True, False]),
                         (light["cfg_tried"], light["cfg_tried_exists"]))
        self.assertEqual((["Proxymuzzle_flash_rifle_m4", "muzzle_flash_rifle_m4"], [False, False]),
                         (muzzle["cfg_tried"], muzzle["cfg_tried_exists"]))
        self.assertEqual((light["cfg_class"], light["cfg_exists"]), (light["cfg_tried"][0], light["cfg_tried_exists"][0]))

    def test_a_bare_basename_config_hit_is_only_a_diagnostic_and_never_the_join(self):
        config = {"CfgNonAIVehicles weaponlight_universal": {
            "model": "\\dz\\weapons\\attachments\\light\\weaponlight_universal.p3d", "inventorySlot": ["weaponFlashlight"]}}
        _world, observations = self.run_world(config=config)
        light = host_row(observations, "AK74")["proxies"][0]
        self.assertEqual(([False, True], False, "", []), (light["cfg_tried_exists"], light["cfg_exists"], light["model"],
                                                         light["inventory_slots"]))
        joined = report.build_report(classification(), observations)
        ak = next(h for h in joined["hosts"] if h["class"] == "AK74")
        self.assertNotEqual("qualified", ak["verdict"])

    def test_each_host_reports_its_lod_names_bounded_with_the_count_and_the_view_by_name_cross_check(self):
        types = proxy_types()
        types["AK74"] = dict(types["AK74"], lods=("1.000", "2.000", "Geometry", "VIEW"))
        types["Glock19"] = dict(types["Glock19"], lods=("1.000", "memory", "geometry"))
        _world, observations = self.run_world(types)
        ak, glock = host_row(observations, "AK74"), host_row(observations, "Glock19")
        self.assertEqual((True, 4, True, ["1.000", "2.000", "Geometry", "VIEW"], True),
                         (ak["lod_list_ok"], ak["lod_count"], ak["lod_names_complete"], ak["lod_names"], ak["view_by_name"]))
        self.assertEqual((True, 3, True, ["1.000", "memory", "geometry"], False),
                         (glock["lod_list_ok"], glock["lod_count"], glock["lod_names_complete"], glock["lod_names"],
                          glock["view_by_name"]))
        self.assertEqual(["1.000", "2.000"], [item["name"] for item in ak["res_lods"]])

    def test_the_lod_name_list_is_capped_at_eight_names_and_a_late_view_lod_is_still_found_by_name(self):
        names = tuple("res%02d" % number for number in range(10)) + ("view",)
        types = proxy_types()
        types["AK74"] = dict(types["AK74"], lods=names)
        _world, observations = self.run_world(types)
        ak = host_row(observations, "AK74")
        self.assertEqual((11, 8, False, True), (ak["lod_count"], len(ak["lod_names"]), ak["lod_names_complete"], ak["view_by_name"]))
        self.assertEqual(list(names[:8]), ak["lod_names"])
        many = tuple("res%03d" % number for number in range(100))
        types["AK74"] = dict(types["AK74"], lods=many)
        _world, observations = self.run_world(types)
        ak = host_row(observations, "AK74")
        self.assertEqual((100, 8, False, False), (ak["lod_count"], len(ak["lod_names"]), ak["lod_names_complete"], ak["view_by_name"]))

    def test_a_failed_lod_list_is_unknown_in_the_lod_facts_and_the_report_says_enumeration_failed(self):
        types = proxy_types()
        types["AK74"] = dict(types["AK74"], lods_unlisted=True)
        _world, observations = self.run_world(types)
        ak = host_row(observations, "AK74")
        self.assertEqual((False, 0, True, [], False), (ak["lod_list_ok"], ak["lod_count"], ak["lod_names_complete"],
                                                       ak["lod_names"], ak["view_by_name"]))
        joined = report.build_report(classification(), observations)
        slot = next(h for h in joined["hosts"] if h["class"] == "AK74")["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("pending", "resolution_enumeration_failed"), (slot["verdict"], slot["reason"]))

    def test_a_server_without_a_numeric_lod_is_pending_resolution_lod_absent_never_qualified(self):
        types = proxy_types()
        types["AK74"] = dict(types["AK74"], lods=("geometry", "memory", "view"))
        _world, observations = self.run_world(types)
        joined = report.build_report(classification(), observations)
        ak = next(h for h in joined["hosts"] if h["class"] == "AK74")
        slot = ak["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("pending", "resolution_lod_absent"), (slot["verdict"], slot["reason"]))
        self.assertEqual(["geometry", "memory", "view"], ak["diagnostics"]["lod"]["names"])
        self.assertEqual((True, 0, True), (ak["diagnostics"]["resolution"]["enum_ok"], ak["diagnostics"]["resolution"]["count"],
                                           ak["diagnostics"]["resolution"]["complete"]))
        self.assertNotIn("qualified", {h["verdict"] for h in joined["hosts"] if h["class"] == "AK74"})

    def test_the_header_scans_the_config_class_names_once_and_reports_the_weaponlight_ones_with_their_models(self):
        _world, observations = self.run_world()
        scan = observations["diagnostics"]["cfg_nonai_scan"]
        self.assertEqual((2, 2, True, 2), (scan["child_count"], scan["scanned"], scan["complete"], scan["proxy_named"]))
        self.assertEqual([{"name": "Proxyweaponlight_tlr", "model": "/dz/weapons/attachments/light/weaponlight_tlr.p3d"},
                          {"name": "Proxyweaponlight_universal",
                           "model": "/dz/weapons/attachments/light/weaponlight_universal.p3d"}],
                         scan["weaponlight_children"])       # the synthetic engine lists children sorted

    def test_the_config_class_scan_is_bounded_and_says_when_it_was_cut(self):
        config = {"CfgNonAIVehicles ProxyWeaponLight_Universal%02d" % number: {"model": "\\dz\\x%d.p3d" % number}
                  for number in range(12)}
        config.update({"CfgNonAIVehicles Filler%04d" % number: {} for number in range(4100)})
        _world, observations = self.run_world(config=config)
        scan = observations["diagnostics"]["cfg_nonai_scan"]
        self.assertEqual((4112, 4096, False), (scan["child_count"], scan["scanned"], scan["complete"]))
        self.assertLessEqual(len(scan["weaponlight_children"]), 8)

    def test_the_proxy_and_resolution_scans_never_call_last_index_of_and_the_new_natives_are_cited(self):
        hook = probe.render_hook(probe.select_targets(classification())).decode()
        for function in ("HCTLProxyBase", "HCTLViewPath", "HCTLProxyRow", "HCTLProxyFacts", "HCTLResolutionScan",
                         "HCTLResRow", "HCTLResFacts", "HCTLIsNumericName"):
            start = re.search(r"\n    \w+ %s\(" % function, hook).start()
            body = hook[start:hook.index("\n    }\n", start)]
            self.assertNotIn("LastIndexOf(", re.sub(r"//[^\n]*", "", body), function)
        for cite in ("EnString.c:240", "EnString.c:253", "EnString.c:271", "Object.c:101", "Game.c:594", "Game.c:611",
                     "constants.c:237"):
            with self.subTest(cite=cite):
                self.assertIn(cite, hook)

    def test_the_hook_keeps_every_native_compile_rule_and_its_size_bound(self):
        hook = probe.render_hook(probe.select_targets(classification())).decode()
        self.assertEqual([], probe.lint_hook(hook, explicit_numbers=True))
        self.assertLessEqual(probe.rt.max_statement_plus(hook), 8)
        self.assertLess(len(hook.encode("ascii")), 256 * 1024)


if __name__ == "__main__":
    unittest.main()
