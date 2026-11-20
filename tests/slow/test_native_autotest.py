"""Synthetic adapter tests; engine results require the actual DayZ diagnostic."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.testing import native_autotest as native


class NativeAutotestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hc-synthetic-autotest-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mission = self.root / "stock"
        self.mission.mkdir()
        self.init = (b"// Synthetic stock-shaped fixture, not purchased game data.\n"
                     b"class CustomMission : MissionServer {}\n"
                     b"Mission CreateCustomMission(string path) { return new CustomMission(); }\n")
        (self.mission / "init.c").write_bytes(self.init)
        (self.mission / "synthetic.dat").write_bytes(b"SYNTHETIC-MISSION-DATA")
        self.scripts = self.root / "installed-synthetic"
        # Explicit declaration-only fixtures exercise source contract admission,
        # never native API availability or an actual game install.
        for relative in dict(native.INTERFACES, **native.DIRECT_INTERFACES):
            patterns = native.INTERFACES.get(relative, ()) + native.DIRECT_INTERFACES.get(relative, ())
            path = self.scripts / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(patterns), encoding="utf-8")
        self.destination = self.root / "fresh"

    def prepare(self, **kwargs):
        return native.prepare_autotest(self.mission, self.destination, self.scripts,
                                       x=6500, z=6500, **kwargs)

    def xml(self, content=None):
        path = self.root / "synthetic-result.xml"
        if content is None:
            content = (f'<testsuites><testsuite name="{native.SUITE}">'
                       + "".join(f'<testcase name="{name}"/>' for name in native.CASES)
                       + '</testsuite></testsuites>')
        path.write_text(content, encoding="utf-8")
        return path

    def test_prepares_real_native_suite_and_runner_not_just_config(self):
        report = self.prepare()
        self.assertEqual({"TestSuites": [native.SUITE]}, json.loads(
            (self.destination / "hc-autotest.json").read_text()))
        text = (self.destination / "init.c").read_text()
        for fragment in ("class HCNativeAutotestSuite : TestSuite", "[Test(",
                         "[Step(EStage.Main)]", "AutotestRunner.Start()",
                         "AutotestRunner.Update(0.1)", "GetNTests()",
                         "GetResult()", "Failure()", "RequestExit(",
                         "OverrideMovementSpeed", "OverrideMovementAngle",
                         "HumanInputControllerOverrideType.DISABLED", "ObjectDelete"):
            self.assertIn(fragment, text)
        self.assertNotIn("SelectPlayer(", text)
        self.assertNotIn("SetPosition(", text)
        self.assertEqual(0, report["real_clients"])
        self.assertEqual("pending", report["runtime_acceptance"])
        self.assertEqual(self.init, (self.mission / "init.c").read_bytes())
        self.assertEqual(b"SYNTHETIC-MISSION-DATA", (self.destination / "synthetic.dat").read_bytes())
        self.assertTrue((self.destination / native.MARKER).exists())

    def test_native_harness_starts_synchronously_and_uses_system_queue(self):
        self.prepare()
        text = (self.destination / "init.c").read_text()
        self.assertIn("CallLater(HCAutotestTick, 100, true)", text)
        self.assertIn("GetCallQueue(CALL_CATEGORY_SYSTEM)", text)
        self.assertIn("m_HCRunning = true;\n        HCAutotestTick();", text)
        self.assertIn("Remove(HCAutotestTick)", text)
        self.assertNotIn("override void OnUpdate", text)

    def test_registration_diagnostics_log_actual_count_and_names_before_guard(self):
        self.prepare()
        text = (self.destination / "init.c").read_text()
        count = text.index('Print("[HC Native Autotest] registration suites=" + count)')
        name = text.index('" name=" + suite.GetName()')
        guard = text.index('if (suite.GetName() == "HCNativeAutotestSuite")')
        self.assertLess(count, name)
        self.assertLess(name, guard)
        self.assertIn('" cases=" + suite.GetNTests()', text[count:guard])

    def test_exact_nonempty_suite_cases_required_in_xml(self):
        self.prepare()
        report = native.verify_result(self.xml(), self.destination)
        self.assertTrue(report["valid"], report)
        self.assertEqual(2, report["cases"])
        self.assertFalse(report["multiplayer_acceptance"])
        self.assertEqual(64, len(report["xml_sha256"]))

    def test_direct_actor_is_explicit_and_independent_of_native_registration(self):
        report = self.prepare(mode="direct-actor")
        text = (self.destination / "init.c").read_text()
        self.assertEqual("native-diagnostic-direct-actor", report["kind"])
        self.assertEqual([], report["cases"])
        for fragment in ("CreatePlayer(null", 'CreateInHands("Rag")',
                         "GetHierarchyRootPlayer()", "OverrideMovementSpeed",
                         "HCActorTick();", "CallLater(HCActorTick, 100, true)",
                         "Remove(HCActorTick)", "ObjectDelete", "cleanup_confirmed",
                         "JsonFileLoader<HCNativeActorReceipt>.SaveFile",
                         "[HC Native Actor] PASS", "[HC Native Actor] FAIL"):
            self.assertIn(fragment, text)
        for forbidden in ("TestHarness", "TestBase", "SetResult(", "AutotestRunner",
                          "[Test(", "SetPosition(", "SelectPlayer("):
            self.assertNotIn(forbidden, text)
        self.assertFalse(native.verify_result(self.xml(), self.destination)["valid"])

    def test_unknown_mode_refuses_before_any_output(self):
        with self.assertRaises(ValueError):
            self.prepare(mode="automatic")
        self.assertFalse(self.destination.exists())

    def test_direct_mode_checks_serializer_and_refuses_stale_receipt_before_copy(self):
        serializer = self.scripts / "3_Game/tools/JsonFileLoader.c"
        original = serializer.read_bytes()
        serializer.unlink()
        with self.assertRaises(ValueError):
            self.prepare(mode="direct-actor")
        self.assertFalse(self.destination.exists())
        serializer.write_bytes(original)
        (self.mission / "hc-native-actor-result.json").write_text("{}")
        with self.assertRaises(ValueError):
            self.prepare(mode="direct-actor")
        self.assertFalse(self.destination.exists())

    def test_direct_runner_observes_outer_system_frames_and_uses_engine_start_clock(self):
        self.prepare(mode="direct-actor")
        text = (self.destination / "init.c").read_text()
        for fragment in ("GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(HCActorFrame)",
                         "GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCActorFrame)",
                         "void HCActorFrame(float timeslice)", "GetTickTime()",
                         "[HC Native Actor] frame=", "mission_ms=", "dt=", "idle=",
                         "GetHive()", "IsIdleMode()", "heartbeat_count < 20"):
            self.assertIn(fragment, text)
        tick = text[text.index("void HCActorTick()") :]
        self.assertIn("GetTickTime() * 1000", tick)
        self.assertNotIn("int now = GetGame().GetTime()", tick)
        self.assertIn("m_Receipt.elapsed_ms = elapsed", tick)

    def test_direct_receipt_rejects_wrong_mode_malformed_and_unbounded_inputs(self):
        self.prepare()
        path = self.root / "synthetic-direct-receipt.json"
        for content in (b"{}", b"null", b"[]", b'{"schema":1,"schema":1}', b"x" * 16385):
            path.write_bytes(content)
            self.assertFalse(native.verify_direct_result(path, self.destination)["valid"])
        # A direct marker is needed to exercise parsing after bundle admission.
        marker = self.destination / native.MARKER
        data = json.loads(marker.read_text())
        data.update(kind="native-diagnostic-direct-actor", mode="direct-actor")
        marker.write_text(json.dumps(data))
        for content in (b"{}", b"null", b"[]", b'{"schema":1,"schema":1}', b"x" * 16385):
            path.write_bytes(content)
            self.assertFalse(native.verify_direct_result(path, self.destination)["valid"])

    def test_direct_receipt_requires_every_assertion_and_observed_bounded_motion(self):
        self.prepare(mode="direct-actor")
        receipt = {"schema": 1, "kind": "native-diagnostic-direct-actor",
                   "real_clients": 0, "planar_m": 2.0, "vertical_m": 0.1,
                   "elapsed_ms": 3000, "reason": ""}
        flags = ("passed", "server_context", "no_clients", "actor_spawned",
                 "inventory_owned", "controller_requested", "movement_passed",
                 "cleanup_requested", "cleanup_confirmed")
        receipt.update(dict.fromkeys(flags, True))
        path = self.root / "synthetic-direct-receipt.json"
        path.write_text(json.dumps(receipt))
        result = native.verify_direct_result(path, self.destination)
        self.assertTrue(result["valid"], result)
        self.assertFalse(result["testharness_acceptance"])
        variants = [dict(receipt, **{flag: False}) for flag in flags]
        variants.extend([dict(receipt, planar_m=value) for value in (0, 21, float("nan"), True)])
        variants.extend([dict(receipt, elapsed_ms=1), dict(receipt, vertical_m=3),
                         dict(receipt, real_clients=1), dict(receipt, passed=1), [], None])
        for i, variant in enumerate(variants):
            with self.subTest(variant=i):
                path.write_text(json.dumps(variant))
                self.assertFalse(native.verify_direct_result(path, self.destination)["valid"])
        path.write_text(json.dumps(receipt))
        (self.destination / "init.c").write_text("// synthetic drift")
        self.assertFalse(native.verify_direct_result(path, self.destination)["valid"])

    def test_missing_empty_duplicate_wrong_failed_skipped_or_error_case_refused(self):
        self.prepare()
        cases = "".join(f'<testcase name="{n}"/>' for n in native.CASES)
        variants = ["", '<testsuite name="HCNativeAutotestSuite"/>',
                    f'<testsuite name="Other">{cases}</testsuite>',
                    f'<testsuite name="{native.SUITE}">{cases}{cases}</testsuite>']
        for tag in ("failure", "error", "skipped"):
            variants.append(f'<testsuite name="{native.SUITE}"><testcase name="{native.CASES[0]}">'
                            f'<{tag}/></testcase><testcase name="{native.CASES[1]}"/></testsuite>')
        for content in variants:
            with self.subTest(index=variants.index(content)):
                self.assertFalse(native.verify_result(self.xml(content), self.destination)["valid"])

    def test_dtd_and_oversized_xml_refused_before_parse(self):
        self.prepare()
        self.assertFalse(native.verify_result(self.xml('<!DOCTYPE x><x/>'), self.destination)["valid"])
        with mock.patch.object(native, "MAX_XML_BYTES", 12):
            self.assertFalse(native.verify_result(self.xml(), self.destination)["valid"])

    def test_utf16_dtd_cannot_bypass_declaration_refusal(self):
        self.prepare()
        content = self.xml().read_text()
        path = self.root / "utf16.xml"
        path.write_bytes(('<!DOCTYPE testsuites [<!ENTITY ignored "synthetic">]>' + content).encode("utf-16"))
        self.assertFalse(native.verify_result(path, self.destination)["valid"])

    def test_native_summary_failure_and_unrun_status_cannot_claim_success(self):
        self.prepare()
        content = self.xml().read_text()
        variants = [content.replace("<testsuites>", '<testsuites failures="1">'),
                    content.replace("<testsuites>", '<testsuites errors="1">'),
                    content.replace('<testcase name=', '<testcase status="notrun" name=', 1)]
        for content in variants:
            with self.subTest(index=variants.index(content)):
                self.assertFalse(native.verify_result(self.xml(content), self.destination)["valid"])

    def test_failed_copy_preserves_partial_output_without_completion_marker(self):
        original_open = Path.open

        def fail_copy(path, *args, **kwargs):
            if path == self.destination / "synthetic.dat" and args == ("xb",):
                raise OSError("synthetic write fault")
            return original_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", fail_copy):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertTrue(self.destination.exists())
        self.assertFalse((self.destination / native.MARKER).exists())
        with self.assertRaises(ValueError):
            self.prepare()

    def test_changed_generated_init_or_config_invalidates_result(self):
        self.prepare()
        (self.destination / "init.c").write_text("// changed", encoding="utf-8")
        self.assertFalse(native.verify_result(self.xml(), self.destination)["valid"])

    def test_malformed_marker_containers_and_duplicate_keys_refuse_without_exception(self):
        self.prepare()
        marker = self.destination / native.MARKER
        original = json.loads(marker.read_text())
        variants = ["[]", "null", "true", '"synthetic"']
        for generated in (None, [], "synthetic", 12, {"init.c": None}):
            variants.append(json.dumps(dict(original, generated=generated)))
        variants.append(marker.read_text().replace('"schema": 1', '"schema": 1, "schema": 1'))
        for content in variants:
            with self.subTest(index=variants.index(content)):
                marker.write_text(content, encoding="utf-8")
                result = native.verify_result(self.xml(), self.destination)
                self.assertFalse(result["valid"])
                self.assertTrue(result["errors"])

    def test_missing_interface_refuses_before_output(self):
        (self.scripts / "2_GameLib/tests/TestingFramework.c").unlink()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.destination.exists())

    def test_empty_framework_contract_is_not_native_evidence(self):
        (self.scripts / "2_GameLib/tests/TestingFramework.c").write_text("// absent", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.destination.exists())

    def test_coordinates_duration_and_watchdog_are_bounded(self):
        for value in (float("nan"), float("inf"), -1, 20000, True):
            with self.subTest(x=value):
                with self.assertRaises(ValueError):
                    native.prepare_autotest(self.mission, self.destination, self.scripts, x=value, z=6500)
                self.assertFalse(self.destination.exists())
        for duration in (0, 31, True, 1.5):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    self.prepare(duration=duration)

    def test_existing_source_and_destination_never_overwritten(self):
        self.prepare()
        before = (self.destination / "init.c").read_bytes()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(before, (self.destination / "init.c").read_bytes())

    def test_unsupported_factory_shape_or_instrumented_mission_refused(self):
        for content in (b"class CustomMission: MissionServer {}", self.init + b"// HCNativeAutotest"):
            (self.mission / "init.c").write_bytes(content)
            with self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse(self.destination.exists())

    def test_symlink_sources_and_destinations_refused(self):
        try:
            (self.mission / "link.txt").symlink_to(self.mission / "init.c")
        except (OSError, NotImplementedError):
            self.skipTest("host cannot create links")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.destination.exists())

    def test_native_file_preflight_size_bound(self):
        with mock.patch.object(native, "MAX_INTERFACE_BYTES", 4):
            with self.assertRaises(ValueError):
                self.prepare()
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
