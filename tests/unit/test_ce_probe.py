"""Offline CE probe stager/hook tests; SYNTHETIC fixtures, never DayZ behavior.

Nothing here proves how the engine, the Central Economy or the retail server
behave. The generated Enforce hook is only checked against compile-shape rules
already observed natively (see test_script_syntax/test_script_identifiers).
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
from tools.setup import ce_probe as probe
from tools.setup import diagnostic_mission as dm

ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "tools/setup"

STOCK_INIT = (b"// SYNTHETIC mission, not purchased game source\r\n"
              b"void main() {}\r\nclass CustomMission: MissionServer {}\r\n"
              b"Mission CreateCustomMission(string path)\r\n{\r\n"
              b"    return new CustomMission();\r\n}\r\n")
SYNTH_BE = b"SYNTHETIC-BATTLEYE"
SYNTH_BE_SHA = hashlib.sha256(SYNTH_BE).hexdigest()
SYNTH_PROTO = b'<prototype><group name="Land_Tenement_Small" lootmax="0" /></prototype>\n'
TREATMENT_PROTO = (b'<prototype><group name="Land_Tenement_Small" lootmax="12">'
                   b'<container name="c" lootmax="12"><point pos="1 2 3" range="1" height="2" /></container>'
                   b'</group></prototype>\n')
EXE_SHA = "987fbc47bab1dab37f74d7f700aa2e5b6af936a7181a62f5ba9f0090aebba805"
WINDOWS_ROOT = r"D:\HollowCountryLocal\ce-probe-test"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pos_xml(counts):
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', "<map>"]
    for name, count in counts.items():
        for i in range(count):
            # Deliberately unsorted so the selection must sort deterministically.
            x = 1000.0 + ((i * 37) % 101) * 10.5
            z = 2000.0 + ((i * 53) % 97) * 7.25
            lines.append(f'    <group name="{name}" pos="{x:.6f} {100 + i}.500000 {z:.6f}" '
                         f'rpy="0.000000 0.000000 0.000000" a="0.000000" />')
    lines.append("</map>")
    return ("\n".join(lines) + "\n").encode()


def default_counts(extra=40):
    counts = {name: extra for name, _role in probe.PROBE_CLASSES}
    counts["Land_Mil_Barracks6"] = 1
    counts["Land_Tisy_Barracks"] = 2
    counts["Land_Unrelated_Shed"] = 30
    return counts


def make_source_runtime(root, counts=None, messages_pinned_differs=True):
    """Synthetic stand-in for the verified runtime's stock-backup and launch plan."""
    mission = root / "stock-backup/mpmissions/dayzOffline.chernarusplus"
    (mission / "db").mkdir(parents=True)
    files = {"init.c": STOCK_INIT, "db/types.xml": b"<types>synthetic</types>\n",
             "db/messages.xml": b"<messages>stock</messages>\n",
             "mapgroupproto.xml": SYNTH_PROTO, "mapgrouppos.xml": pos_xml(counts or default_counts())}
    plan_files = []
    for name, data in sorted(files.items()):
        (mission / name).write_bytes(data)
        pinned = data
        if name == "db/messages.xml" and messages_pinned_differs:
            pinned = b"<messages>runtime shutdown delta</messages>\n"
        plan_files.append({"path": name, "sha256": sha(pinned)})
    config = b'hostname = "SYNTHETIC";\r\n'
    (root / "serverDZ.cfg").write_bytes(config)
    (root / "battleye").mkdir()
    (root / "battleye/BEServer_x64.dll").write_bytes(SYNTH_BE)
    (root / "launch-plan.json").write_text(json.dumps(
        {"schema_version": 1, "status": "staged-only-not-launched", "config_sha256": sha(config),
         "mission_files": plan_files}))
    return root


def kwargs(**extra):
    base = {"battleye_sha256": SYNTH_BE_SHA, "windows_runtime_root": WINDOWS_ROOT}
    base.update(extra)
    return base


def targets_for(counts=None, per_class=24):
    placements = probe.parse_placements(pos_xml(counts or default_counts()))
    return probe.build_targets(placements, per_class=per_class)


class Workspace(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = make_source_runtime(self.root / "vanilla")
        self.dest = self.root / "ce-probe-test"


class PlacementSelectionTests(unittest.TestCase):
    def test_parse_reads_only_wanted_groups_and_rejects_exponent_or_nonfinite_positions(self):
        xml = pos_xml({"A": 2, "B": 1})
        self.assertEqual({"A": 2}, {k: len(v) for k, v in probe.parse_placements(xml, wanted={"A"}).items()})
        for bad in ("1e5 2 3", "nan 2 3", "1 2", "inf 0 0"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                probe.parse_placements(f'<map><group name="A" pos="{bad}" /></map>'.encode())

    def test_selection_is_deterministic_sorted_and_evenly_spaced(self):
        positions = [(float(x), 0.0, float(100 - x)) for x in range(100)]
        first = probe.select_placements(positions, 24)
        self.assertEqual(24, len(first))
        self.assertEqual(first, probe.select_placements(list(reversed(positions)), 24))
        xs = [p[0] for p in first]
        self.assertEqual(sorted(xs), xs)
        gaps = {round(b - a) for a, b in zip(xs, xs[1:])}
        self.assertLessEqual(max(gaps) - min(gaps), 1)
        self.assertLess(xs[0], 5)
        self.assertGreater(xs[-1], 94)

    def test_selection_keeps_all_when_fewer_than_the_limit_and_never_duplicates(self):
        positions = [(1.0, 0.0, 1.0), (2.0, 0.0, 2.0), (3.0, 0.0, 3.0)]
        self.assertEqual(positions, probe.select_placements(positions, 24))
        self.assertEqual(24, len(set(probe.select_placements([(float(i), 0.0, 0.0) for i in range(25)], 24))))

    def test_targets_cover_the_required_classes_roles_and_caps(self):
        names = [n for n, _ in probe.PROBE_CLASSES]
        for required in ("Land_Tenement_Small", "Land_Tenement_Big", "Land_Mil_Barracks1", "Land_Mil_Barracks2",
                         "Land_Mil_Barracks3", "Land_Mil_Barracks4", "Land_Mil_Barracks5",
                         "Land_Mil_Barracks_Round", "Land_Mil_Barracks6", "Land_Tisy_Barracks",
                         "Land_House_1W01", "Land_House_2W01", "Land_HouseBlock_2F1"):
            self.assertIn(required, names)
        roles = dict(probe.PROBE_CLASSES)
        self.assertEqual("control", roles["Land_House_1W01"])
        self.assertEqual("apartment", roles["Land_Tenement_Big"])
        self.assertEqual("barracks", roles["Land_Mil_Barracks1"])
        targets = targets_for()
        per = {}
        for t in targets:
            per[t["class"]] = per.get(t["class"], 0) + 1
        self.assertEqual(24, per["Land_Tenement_Small"])
        self.assertEqual(1, per["Land_Mil_Barracks6"])
        self.assertEqual(2, per["Land_Tisy_Barracks"])
        self.assertNotIn("Land_Unrelated_Shed", per)
        self.assertEqual(list(range(len(targets))), [t["index"] for t in targets])
        self.assertLessEqual(len(targets), 400)

    def test_hard_cap_is_enforced_and_missing_class_is_recorded_not_invented(self):
        placements = probe.parse_placements(pos_xml(default_counts(60)))
        with self.assertRaises(ValueError):
            probe.build_targets(placements, per_class=24, hard_cap=50)
        sparse = probe.parse_placements(pos_xml({"Land_Tenement_Small": 3}))
        targets = probe.build_targets(sparse, per_class=24)
        self.assertEqual(3, len(targets))


class HookRenderingTests(unittest.TestCase):
    def setUp(self):
        self.targets = targets_for()
        self.hook = probe.render_hook(self.targets, export_delay_s=30, census_delay_s=240).decode()

    def test_exports_are_ordered_bracketed_by_prints_and_scheduled_after_init(self):
        order = [self.hook.index(f"GetCEApi().{name}(") for name in
                 ("ExportProxyProto", "ExportProxyData", "ExportClusterData")]
        self.assertEqual(sorted(order), order)
        self.assertIn("GetCEApi().ExportProxyData(Vector(7680, 0, 7680), 11000);", self.hook)
        for name in ("ExportProxyProto", "ExportProxyData", "ExportClusterData"):
            call = self.hook.index(f"GetCEApi().{name}(")
            self.assertIn(f"[HC CE Probe] {name} BEGIN", self.hook[:call][-200:])
            self.assertIn(f"[HC CE Probe] {name} END", self.hook[call:call + 200])
        self.assertIn("CallLater(HCProbeRunExports, 30000, false)", self.hook)
        self.assertIn("CallLater(HCProbeCensusStep, 240000, false)", self.hook)
        self.assertIn("GetGame().IsServer()", self.hook)
        self.assertNotIn("#ifdef", self.hook)

    def test_targets_are_inlined_as_literal_data_without_exponents(self):
        adds = re.findall(r'HCProbeAdd\("([A-Za-z0-9_]+)", "(\w+)", (-?\d+\.\d{6}), (-?\d+\.\d{6}), (-?\d+\.\d{6})\);', self.hook)
        self.assertEqual(len(self.targets), len(adds))
        first = self.targets[0]
        self.assertEqual(first["class"], adds[0][0])
        self.assertEqual(first["role"], adds[0][1])
        self.assertAlmostEqual(first["pos"][0], float(adds[0][2]), places=5)

    def test_census_output_is_bounded_json_then_sentinel_then_complete_marker(self):
        self.assertIn('"$profile:HCCEProbe"', self.hook)
        self.assertIn("census.json", self.hook)
        self.assertIn("complete.txt", self.hook)
        self.assertLess(self.hook.index("census.json"), self.hook.index("complete.txt"))
        self.assertIn('Print("[HC CE Probe] COMPLETE")', self.hook)
        self.assertLess(self.hook.index("CloseFile(handle)"), self.hook.index("[HC CE Probe] COMPLETE"))
        for name in ("GetObjectsAtPosition3D", "ItemBase.Cast", "GetHierarchyParent()", "CoordToLocal",
                     "ClippingInfo", "GetCollisionBox", "GetType()", "FPrintln", "OpenFile", "MakeDirectory"):
            self.assertIn(name, self.hook)
        self.assertIn("FileExist(censusPath)", self.hook)  # never overwrites earlier evidence

    def test_hook_size_is_bounded_at_the_hard_cap(self):
        many = [{"class": "Land_House_1W01", "role": "control", "index": i, "pos": [1.0, 2.0, 3.0]} for i in range(400)]
        self.assertLess(len(probe.render_hook(many)), 96 * 1024)
        with self.assertRaises(ValueError):
            probe.render_hook(many + [many[0]])

    def test_invalid_targets_and_delays_are_refused(self):
        bad = dict(self.targets[0], **{"class": 'Land_"Evil'})
        with self.assertRaises(ValueError):
            probe.render_hook([bad])
        with self.assertRaises(ValueError):
            probe.render_hook(self.targets, census_delay_s=5)
        with self.assertRaises(ValueError):
            probe.render_hook(self.targets, export_delay_s=0)
        with self.assertRaises(ValueError):
            probe.render_hook([])

    def test_generated_hook_passes_every_native_observed_compile_rule(self):
        self.assertEqual([], probe.lint_hook(self.hook))

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
            exponent = re.compile(r'\b\d+(?:\.\d+)?[eE][+-]?\d+\b')
            for number, line in enumerate(syn.strip_comments(self.hook), 1):
                self.assertIsNone(exponent.search(re.sub(r'"[^"]*"', '""', line)), number)
            names = set(ident.PINNED_ENGINE_TYPES)
            if (ident.CACHE / "3_Game").is_dir():
                for layer in ident.native_types_by_layer(ident.CACHE).values():
                    names |= layer
            clashes = [(n, name) for n, name in ident.declarations(path) if name in names]
            self.assertEqual([], clashes)

    def test_hook_declares_out_arrays_and_uses_no_unlisted_engine_api(self):
        allowed = {"GetCEApi", "ExportProxyProto", "ExportProxyData", "ExportClusterData", "GetObjectsAtPosition3D",
                   "GetCallQueue", "CallLater", "GetHierarchyParent", "CoordToLocal", "ClippingInfo",
                   "GetCollisionBox", "GetType", "GetPosition", "OpenFile", "FPrintln", "CloseFile", "MakeDirectory",
                   "FileExist", "IsServer", "GetTime", "GetWorldName", "GetVersion", "Cast", "Distance", "Replace",
                   "Substring", "Length", "Insert", "Get", "Count", "Find", "Print", "Vector", "Max", "Min",
                   "AbsFloat", "Sqrt", "OnInit", "ToString", "GetGame", "AsciiToString"}
        called = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", re.sub(r'"[^"]*"', '""', "\n".join(syn.strip_comments(self.hook)))))
        own = set(re.findall(r"\b(?:void|bool|int|float|string|Object|array<[^>]+>)\s+(\w+)\s*\(", self.hook))
        keywords = {"if", "while", "for", "return", "override", "array", "super"}
        leftovers = {c for c in called if c not in allowed and c not in own and c not in keywords
                     and not c.startswith("HCProbe")}
        self.assertEqual(set(), leftovers)


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
        param = "        int a = 1;"
        self.assertTrue(any("duplicate local 'a'" in i for i in self.issues(param)))
        two_functions = ("class HCSample : CustomMission\n{\n    void F()\n    {\n        int value = 1;\n    }\n"
                         "    void G()\n    {\n        int value = 2;\n    }\n}\n")
        self.assertEqual([], probe.lint_hook(two_functions))

    def test_identifier_equal_to_an_engine_type_is_flagged(self):
        self.assertTrue(any("engine type name" in i for i in self.issues("        Object Object = null;")))
        found = probe.lint_hook(self.wrap("        int Weather = 1;"), native_types=frozenset({"Weather"}))
        self.assertTrue(any("'Weather'" in i for i in found))

    def test_reserved_words_are_not_usable_as_identifiers(self):
        self.assertTrue(any("reserved" in i for i in self.issues("        vector local = a;")))

    def test_leading_logical_operators_and_exponent_literals_are_flagged(self):
        self.assertTrue(any("leading" in i for i in self.issues("        if (a\n            || a) { }")))
        self.assertTrue(any("leading" in i for i in self.issues("        if (a\n            && a) { }")))
        self.assertTrue(any("exponent" in i for i in self.issues("        float big = 3.4e38;")))
        self.assertEqual([], self.issues('        float big = FLT_MAX;\n        Print("1e5");'))

    def test_out_arguments_must_be_declared_before_the_call(self):
        bad = "        GetGame().GetObjectsAtPosition3D(a, 1.0, objects, cargos);"
        self.assertTrue(any("out argument 'objects'" in i for i in self.issues(bad)))
        good = ("        array<Object> objects = new array<Object>;\n        array<CargoBase> cargos = new array<CargoBase>;\n"
                "        GetGame().GetObjectsAtPosition3D(a, 1.0, objects, cargos);")
        self.assertEqual([], self.issues(good))
        box = "        float r = obj.ClippingInfo(box);"
        self.assertTrue(any("out argument 'box'" in i for i in self.issues(box)))

    def test_string_literal_containing_comment_markers_is_refused(self):
        self.assertTrue(any("comment marker" in i for i in self.issues('        Print("a//b");')))

    def test_override_parameter_names_must_match_the_engine_prototype(self):
        text = "class HCSample : CustomMission\n{\n    override void OnEvent(int renamed)\n    {\n    }\n}\n"
        found = probe.lint_hook(text, prototypes={"OnEvent": {("eventTypeId",)}})
        self.assertTrue(any("override OnEvent" in i for i in found))
        self.assertEqual([], probe.lint_hook(text, prototypes={"OnEvent": {("renamed",)}}))


class DiagnosticMissionHookParameterTests(Workspace):
    def test_ce_probe_purpose_requires_an_explicit_hook_and_others_forbid_one(self):
        with self.assertRaises(ValueError):
            dm._instrument(STOCK_INIT, purpose="ce-probe")
        with self.assertRaises(ValueError):
            dm._instrument(STOCK_INIT, purpose="item-audit", hook=b"// x\n")
        with self.assertRaises(ValueError):
            dm._instrument(STOCK_INIT, purpose="ce-probe", hook=b"x" * (256 * 1024 + 1))
        result = dm._instrument(STOCK_INIT, purpose="ce-probe", hook=b"\n// HOOK\n")
        self.assertTrue(result.endswith(b"\n// HOOK\n"))
        self.assertIn(b"return new HCDisposableDiagnosticMission();", result)

    def test_existing_purposes_are_unchanged(self):
        before = dm._instrument(STOCK_INIT, purpose="item-audit")
        self.assertIn(b"HCItemCompatibilityAudit.ExportAll(", before)

    def test_prepare_records_the_supplied_hook_hash_under_its_own_kind(self):
        stock = self.root / "stock"
        (stock).mkdir()
        (stock / "init.c").write_bytes(STOCK_INIT)
        hook = b"\n// HOOK\n"
        manifest = dm.prepare_diagnostic_mission(stock, self.root / "out/m", purpose="ce-probe", hook=hook)
        self.assertEqual("disposable-ce-probe", manifest["kind"])
        self.assertEqual(sha(hook), manifest["hook_sha256"])
        self.assertEqual("pending", manifest["runtime_acceptance"])


class StagerTests(Workspace):
    def stage(self, **extra):
        return probe.stage(self.source, self.dest, **kwargs(**extra))

    def test_stage_creates_a_fresh_runtime_with_empty_storage_and_profiles(self):
        plan = self.stage()
        for name in ("storage", "profiles"):
            self.assertTrue((self.dest / name).is_dir())
            self.assertEqual([], list((self.dest / name).iterdir()))
        self.assertEqual(SYNTH_BE, (self.dest / "battleye/BEServer_x64.dll").read_bytes())
        self.assertEqual((self.source / "serverDZ.cfg").read_bytes(), (self.dest / "serverDZ.cfg").read_bytes())
        self.assertEqual(plan, json.loads((self.dest / "ce-probe-plan.json").read_text()))

    def test_plan_has_the_required_identity_paths_arguments_and_status(self):
        plan = self.stage()
        self.assertEqual("staged-only-not-launched", plan["status"])
        self.assertEqual("ce-probe", plan["kind"])
        self.assertEqual(r"D:\SteamLibrary\steamapps\common\DayZServer\DayZServer_x64.exe", plan["server_exe"])
        self.assertEqual(EXE_SHA, plan["server_exe_sha256"])
        self.assertEqual(r"D:\SteamLibrary\steamapps\common\DayZServer", plan["working_directory"])
        self.assertEqual(WINDOWS_ROOT, plan["runtime_root"])
        self.assertEqual(WINDOWS_ROOT + r"\mpmissions\dayzOffline.chernarusplus", plan["mission"])
        self.assertEqual(WINDOWS_ROOT + r"\storage", plan["storage"])
        self.assertEqual(WINDOWS_ROOT + r"\profiles", plan["profiles"])
        self.assertEqual(2302, plan["port"])
        self.assertEqual("127.0.0.1:2302", plan["requested_bind"])
        self.assertEqual(["-ip=127.0.0.1", "-port=2302", f"-config={WINDOWS_ROOT}\\serverDZ.cfg",
                          f"-mission={plan['mission']}", f"-storage={plan['storage']}",
                          f"-profiles={plan['profiles']}", f"-BEpath={WINDOWS_ROOT}\\battleye",
                          "-doLogs", "-adminLog"], plan["arguments"])
        for argument in plan["arguments"]:
            self.assertNotRegex(argument, r"(?i)-mod=|-servermod=|-filepatching|-connect")
        self.assertEqual("control", plan["variant"])
        self.assertIsNone(plan["treatment"])

    def test_every_staged_file_is_hashed_and_matches_disk(self):
        plan = self.stage()
        paths = {entry["path"] for entry in plan["staged_files"]}
        for expected in ("serverDZ.cfg", "battleye/BEServer_x64.dll", "mpmissions/dayzOffline.chernarusplus/init.c",
                         "mpmissions/dayzOffline.chernarusplus/mapgroupproto.xml",
                         "mpmissions/dayzOffline.chernarusplus/.hollow-country-diagnostic-mission.json"):
            self.assertIn(expected, paths)
        on_disk = {p.relative_to(self.dest).as_posix() for p in self.dest.rglob("*")
                   if p.is_file() and p.name != "ce-probe-plan.json"}
        self.assertEqual(on_disk, paths)
        for entry in plan["staged_files"]:
            data = (self.dest / entry["path"]).read_bytes()
            self.assertEqual((sha(data), len(data)), (entry["sha256"], entry["bytes"]), entry["path"])

    def test_control_leaves_stock_mapgroupproto_and_treatment_replaces_only_that_file(self):
        control = self.stage()
        mission = "mpmissions/dayzOffline.chernarusplus/"
        control_hashes = {e["path"]: e["sha256"] for e in control["staged_files"]}
        self.assertEqual(sha(SYNTH_PROTO), control_hashes[mission + "mapgroupproto.xml"])
        treatment_file = self.root / "treatment.xml"
        treatment_file.write_bytes(TREATMENT_PROTO)
        self.dest = self.root / "ce-probe-treated"
        treated = probe.stage(self.source, self.dest, treatment_mapgroupproto=treatment_file,
                              **kwargs(windows_runtime_root=WINDOWS_ROOT + "T"))
        treated_hashes = {e["path"]: e["sha256"] for e in treated["staged_files"]}
        self.assertEqual("treatment", treated["variant"])
        self.assertEqual(sha(TREATMENT_PROTO), treated_hashes[mission + "mapgroupproto.xml"])
        self.assertEqual({"mapgroupproto_sha256": sha(TREATMENT_PROTO), "stock_mapgroupproto_sha256": sha(SYNTH_PROTO)},
                         {k: treated["treatment"][k] for k in ("mapgroupproto_sha256", "stock_mapgroupproto_sha256")})
        changed = {p for p in treated_hashes if treated_hashes[p] != control_hashes.get(p)
                   and not p.endswith(".hollow-country-diagnostic-mission.json")}
        self.assertEqual({mission + "mapgroupproto.xml"}, changed)

    def test_bad_treatment_is_refused_before_anything_is_created(self):
        for payload in (b"<notxml", b'<!DOCTYPE x [<!ENTITY a "b">]><prototype/>', b"<other/>"):
            bad = self.root / "bad.xml"
            bad.write_bytes(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.stage(**{"treatment_mapgroupproto": bad})
            self.assertFalse(self.dest.exists())

    def test_init_c_is_instrumented_with_the_inlined_probe_and_no_other_mission_file_changes(self):
        plan = self.stage()
        init = (self.dest / "mpmissions/dayzOffline.chernarusplus/init.c").read_bytes()
        self.assertIn(b"return new HCDisposableDiagnosticMission();", init)
        self.assertEqual(plan["probe"]["hook_sha256"], sha(init[init.index(b"\n\n// Hollow Country DISPOSABLE"):]))
        self.assertEqual((self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus/db/types.xml").read_bytes(),
                         (self.dest / "mpmissions/dayzOffline.chernarusplus/db/types.xml").read_bytes())
        self.assertEqual(len(plan["targets"]), plan["probe"]["target_count"])
        self.assertLessEqual(plan["probe"]["target_count"], 400)
        self.assertEqual(24, plan["probe"]["per_class_limit"])
        self.assertEqual(30, plan["probe"]["export_delay_s"])
        self.assertEqual(240, plan["probe"]["census_delay_s"])
        self.assertEqual("profiles/HCCEProbe/census.json", plan["probe"]["census_relative_path"])
        self.assertEqual("profiles/HCCEProbe/complete.txt", plan["probe"]["sentinel_relative_path"])
        self.assertEqual([], probe.lint_hook(init.decode()[init.decode().index("// Hollow Country DISPOSABLE"):]))

    def test_plan_records_sampled_targets_and_availability_per_class(self):
        plan = self.stage()
        by_class = {c["class"]: c for c in plan["target_classes"]}
        self.assertEqual({"available": 40, "sampled": 24}, {k: by_class["Land_Tenement_Small"][k] for k in ("available", "sampled")})
        self.assertEqual(1, by_class["Land_Mil_Barracks6"]["sampled"])
        first = plan["targets"][0]
        self.assertEqual({"class", "role", "index", "pos"}, set(first))

    def test_launch_plan_hash_mismatch_is_refused_except_the_documented_runtime_delta(self):
        plan = self.stage()  # messages.xml differs from the plan pin: recorded, not hidden
        record = next(f for f in plan["mission_files"] if f["path"] == "db/messages.xml")
        self.assertEqual("differs-from-launch-plan-recorded", record["plan_hash_status"])
        self.assertEqual(sha(b"<messages>stock</messages>\n"), record["sha256"])
        match = next(f for f in plan["mission_files"] if f["path"] == "init.c")
        self.assertEqual("match", match["plan_hash_status"])
        self.assertEqual(sha(STOCK_INIT), match["source_sha256"])
        self.assertNotEqual(match["sha256"], match["source_sha256"])  # instrumented

    def test_tampered_stock_file_and_unplanned_files_are_handled_explicitly(self):
        mission = self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus"
        (mission / "db/types.xml").write_bytes(b"<types>tampered</types>\n")
        with self.assertRaises(ValueError):
            self.stage()
        self.assertFalse(self.dest.exists())
        (mission / "db/types.xml").write_bytes(b"<types>synthetic</types>\n")
        (mission / "extra.xml").write_bytes(b"<x/>\n")
        plan = self.stage()
        extra = next(f for f in plan["mission_files"] if f["path"] == "extra.xml")
        self.assertEqual("absent-from-launch-plan-recorded", extra["plan_hash_status"])

    def test_wrong_config_or_battleye_hash_is_refused(self):
        (self.source / "serverDZ.cfg").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.stage()
        self.assertFalse(self.dest.exists())
        (self.source / "serverDZ.cfg").write_bytes(b'hostname = "SYNTHETIC";\r\n')
        with self.assertRaises(ValueError):
            probe.stage(self.source, self.dest, **kwargs(battleye_sha256="0" * 64))
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
        self.assertEqual(1, len(list((self.root).glob("ce-probe-*"))))

    def test_destination_must_be_outside_the_source_runtime_and_checkout(self):
        with self.assertRaises(ValueError):
            probe.stage(self.source, self.source / "child", **kwargs())
        with self.assertRaises(ValueError):
            probe.stage(self.source, ROOT / "ce-probe-inside-checkout", **kwargs())

    def test_windows_paths_derive_from_mnt_d_and_unknown_locations_need_an_override(self):
        self.assertEqual(r"D:\HollowCountryLocal\ce-probe-001",
                         probe.windows_runtime_root(Path("/mnt/d/HollowCountryLocal/ce-probe-001")))
        for bad in ("/mnt/d/Other/ce-probe-001", "/tmp/ce-probe-001", "/mnt/d/HollowCountryLocal/vanilla-p0-001",
                    "/mnt/d/HollowCountryLocal/bad name"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                probe.windows_runtime_root(Path(bad))
        with self.assertRaises(ValueError):
            probe.stage(self.source, self.dest, battleye_sha256=SYNTH_BE_SHA)

    def test_staging_never_launches_anything_or_touches_the_network(self):
        with mock.patch("subprocess.Popen", side_effect=AssertionError("launch")), \
                mock.patch("socket.socket", side_effect=AssertionError("network")):
            self.stage()

    def test_cli_stages_and_prints_the_plan_path_and_fails_on_reuse(self):
        argv = ["--source-runtime", str(self.source), "--destination", str(self.dest),
                "--battleye-sha256", SYNTH_BE_SHA, "--windows-runtime-root", WINDOWS_ROOT,
                "--census-delay-s", "300", "--per-class", "5"]
        with mock.patch("sys.stdout") as out:
            self.assertEqual(0, probe.main(argv))
        self.assertIn("ce-probe-plan.json", "".join(call.args[0] for call in out.write.call_args_list))
        plan = json.loads((self.dest / "ce-probe-plan.json").read_text())
        self.assertEqual(300, plan["probe"]["census_delay_s"])
        self.assertEqual(5, plan["probe"]["per_class_limit"])
        self.assertEqual(1, probe.main(argv))


class WindowsLaunchScriptStaticTests(unittest.TestCase):
    """Static text checks only; PowerShell is never parsed or executed here."""

    def setUp(self):
        self.script = (SETUP / "Start-CEProbeServer.ps1").read_text()
        self.code = "\n".join(line for line in self.script.splitlines() if not line.lstrip().startswith("#"))

    def test_script_cannot_start_clients_services_tasks_remoting_or_other_processes(self):
        for forbidden in (r"(?i)\bInvoke-Expression\b", r"(?i)\bEnable-PSRemoting\b", r"(?i)\bInvoke-Command\b",
                          r"(?i)\bEnter-PSSession\b", r"(?i)\bSet-ExecutionPolicy\b", r"(?i)\bNew-NetFirewallRule\b",
                          r"(?i)\bnetsh\b", r"(?i)\bRegister-ScheduledTask\b", r"(?i)\bschtasks\b",
                          r"(?i)\bNew-Service\b", r"(?i)\bsc\.exe\b", r"(?i)\btaskkill\b", r"(?i)\bRemove-Item\b",
                          r"(?i)-(?:Force|Recurse)\b", r"(?i)DayZ_x64|DayZLauncher|Start-LocalClient|-connect=",
                          r"(?i)-filePatching\b|-serverMod=|-mod=", r"(?i)\bupnp\s*=", r"(?i)Stop-Process\s+-Name",
                          r"(?i)\|\s*Stop-Process", r"(?i)\bGet-FileHash\b", r"(?i)\bInvoke-WebRequest\b|\bInvoke-RestMethod\b"):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(self.code, forbidden)

    def test_requires_ps51_and_a_mandatory_runtime_parameter_with_whatif_support(self):
        self.assertTrue(self.script.startswith("#requires -Version 5.1"))
        self.assertIn("SupportsShouldProcess = $true", self.script)
        self.assertRegex(self.script, r"\[Parameter\(Mandatory = \$true\)\]\s*\[string\]\$Runtime")
        self.assertIn("$TimeoutMinutes", self.script)

    def test_validates_runtime_location_plan_exe_and_every_staged_hash(self):
        for required in (r"D:\HollowCountryLocal", "ce-probe-plan.json", "staged-only-not-launched",
                         EXE_SHA, r"D:\SteamLibrary\steamapps\common\DayZServer\DayZServer_x64.exe",
                         "-port=2302", "-ip=127.0.0.1", "staged_files", "Read-Sha256",
                         "[System.Security.Cryptography.SHA256]::Create()", "vanilla-p0-001",
                         "Unexpected CE probe plan", "storage and profiles must be empty"):
            with self.subTest(required=required):
                self.assertIn(required, self.script)

    def test_refuses_a_running_server_before_the_shouldprocess_gate_and_launch(self):
        running = self.script.index("Get-Process -Name DayZServer_x64")
        gate = self.script.index("$PSCmdlet.ShouldProcess(")
        launch = self.script.index("Start-Process")
        stop = self.script.index("Stop-Process")
        self.assertLess(running, gate)
        self.assertLess(gate, launch)
        self.assertLess(launch, stop)
        self.assertIn("-PassThru", self.script)
        self.assertIn("already running", self.script)

    def test_only_the_started_pid_is_ever_stopped_and_only_after_the_wait(self):
        stops = re.findall(r"Stop-Process[^\r\n]*", self.code)
        self.assertTrue(stops)
        for stop in stops:
            self.assertRegex(stop, r"^Stop-Process -Id \$server\.Id\b")
        self.assertNotRegex(self.code, r"(?i)Get-Process[^\r\n]*\|")
        self.assertIn("complete.txt", self.script)
        self.assertIn("HCCEProbe", self.script)
        self.assertIn("HasExited", self.script)
        self.assertIn("$TimeoutMinutes", self.script)

    def test_observation_json_names_the_logs_and_never_claims_acceptance(self):
        for required in ("ce-probe-observation-", "observed-not-accepted", "*.RPT", "script_*.log", "error_*.log",
                         "*.ADM", "census.json", "complete.txt", "[System.IO.FileMode]::CreateNew",
                         "outcome", "server_pid"):
            with self.subTest(required=required):
                self.assertIn(required, self.script)
        for claim in ("'accepted'", "'verified'", "'passed'"):
            self.assertNotIn(claim, self.script)


if __name__ == "__main__":
    unittest.main()
