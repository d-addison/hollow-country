"""Diagnostic probe adapter tests (AV-T008). Synthetic: no DayZDiag, Wine or hook is ever started.

Subcase names, settings cases and hook markers derive from the source tree and the probe tool; the
orchestrator runs against a fake launcher and a fake /proc tree. A pass here is never DayZ evidence.
"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests.unit.native_fakes import FakeHost, FakeProcess
from tools.setup import diagnostic_mission
from tools.testing import automation, drivers, native_probe as probe, native_server as server

ROOT = Path(__file__).resolve().parents[2]
SUBCASES = probe.discover_subcases(ROOT)
NEGATIVES = probe.settings_cases(ROOT)
MARKERS = probe.hook_markers()


def marker_text(names, passed=True, detail="ok"):
    return "".join("[HC SelfTest] name=%s pass=%s detail=%s\n" % (name, str(passed).lower(), detail)
                   for name in names)


def selftest_evidence(names=None):
    names = list(names if names is not None else SUBCASES)
    return {
        "schema": 1, "probe": "core-selftests", "requested": names, "synthetic": True,
        "subcases": {name: {"markers": [[True, "ok"]]} for name in names},
        "executable_kind": "diagnostic-server", "client_count": 0,
        "logs": {"fresh_files": 1, "rejected": {}, "skipped": {}, "modules": ["World", "Mission"],
                 "script_errors": 0, "script_error_lines": [], "engine_errors": [], "dumps": 0},
        "normal_artifact": {"sha256": "0" * 64, "hook_bytes": [], "markers_checked": len(MARKERS)},
        "cleanup": {"observed": True, "survivors": []},
        "guard": {"observed": True, "changed": []},
    }


def negative_evidence():
    return {
        "schema": 1, "probe": "settings-negatives", "requested": list(NEGATIVES), "synthetic": True,
        "subcases": {name: {"status": "settings-rejected", "settings_original_preserved": True}
                     for name in NEGATIVES},
        "executable_kind": "dedicated-server", "client_count": 0,
        "logs": {"fresh_files": 3, "rejected": {}, "skipped": {}, "modules": [], "script_errors": 0,
                 "script_error_lines": [], "engine_errors": [], "dumps": 0},
        "normal_artifact": {"sha256": "0" * 64, "hook_bytes": [], "markers_checked": len(MARKERS)},
        "cleanup": {"observed": True, "survivors": []},
        "guard": {"observed": True, "changed": []},
    }


class HCMissionStagingTests(unittest.TestCase):
    def test_shared_target_refused_before_writes_and_disposable_bytes_pinned(self):
        from tools.setup import wine_compile_probe as wine
        # safe() excludes source checkouts, so fake only location policy for this
        # private scratch fixture; keep the explicit destination guard real.
        scratch = ROOT / '.banso'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp, \
                mock.patch.object(wine, 'safe', side_effect=lambda p: Path(p).absolute()):
            root = Path(temp)
            server_root = root / 'server'
            shared = server_root / 'mpmissions/dayzOffline.chernarusplus'
            shared.mkdir(parents=True)
            (shared / 'init.c').write_bytes(b'original init')
            before = wine.snapshot_mission(shared)
            experiment = root / 'experiment'
            experiment.mkdir()
            files = {'one.json': b'{"raw":true}\n', 'nested/two.xml': b'<raw/>'}
            with self.assertRaisesRegex(ValueError, 'hc_mission_shared_target'):
                wine.stage_hc_mission(shared, experiment, server_root, files)
            self.assertEqual(before, wine.snapshot_mission(shared))
            mission = experiment / 'mod-stack.chernarusplus'
            import shutil
            shutil.copytree(shared, mission)
            wine.stage_hc_mission(mission, experiment, server_root, files)
            for name, data in files.items():
                self.assertEqual((mission / 'hollow-country' / name).read_bytes(), data)
            self.assertEqual((mission / 'init.c').read_bytes(), b'original init')
            receipt = wine.hc_mission_receipt(files)
            self.assertEqual(receipt, wine.hc_mission_receipt(dict(reversed(list(files.items())))))
            self.assertEqual(receipt['hc_mission_files'], 2)
            self.assertEqual(receipt['hc_mission_bytes'], sum(map(len, files.values())))
            expected = wine.snapshot_mission(mission)
            wine.verify_final_inputs(mission, expected, [])
            (mission / 'hollow-country/one.json').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'complete staged mission inventory drift'):
                wine.verify_final_inputs(mission, expected, [])
            self.assertEqual(before, wine.snapshot_mission(shared))


    def test_combined_entry_and_byte_budgets_refuse_before_hc_writes(self):
        from tools.setup import wine_compile_probe as wine
        scratch = ROOT / '.banso'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp, \
                mock.patch.object(wine, 'safe', side_effect=lambda p: Path(p).absolute()):
            root = Path(temp)
            experiment = root / 'experiment'
            mission = experiment / 'mod-stack.chernarusplus'
            mission.mkdir(parents=True)
            (mission / 'init.c').write_bytes(b'init')
            # Staging uses the HC-extended budget; zero the HC caps so the stock cap
            # alone is the limit and the refusal still lands before any write.
            for budget, cap, message in [('MAX_ENTRIES', 2, 'mission entry budget exceeded'),
                                          ('MAX_TOTAL_BYTES', 5, 'mission byte budget exceeded')]:
                with mock.patch.object(wine.staging, budget, cap), \
                        mock.patch.object(wine, 'HC_MISSION_MAX_ENTRIES', 0), \
                        mock.patch.object(wine, 'HC_MISSION_MAX_BYTES', 0):
                    with self.assertRaisesRegex(ValueError, message):
                        wine.stage_hc_mission(mission, experiment, root / 'server', {'a.json': b'{}'})
                self.assertFalse((mission / 'hollow-country').exists())



class DiscoveryTests(unittest.TestCase):
    def test_subcases_are_discovered_from_source_and_each_is_printed_there(self):
        self.assertTrue(SUBCASES)
        text = "\n".join(path.read_text(errors="replace")
                         for path in (ROOT / probe.SCRIPT_ROOT).rglob("*.c") if "SelfTest" in path.read_text(errors="replace"))
        for name in SUBCASES:
            self.assertIn('"%s"' % name if ("Receipt(\"%s\"" % name) in text else "name=%s pass=" % name, text)

    def test_settings_cases_are_the_options_the_probe_tool_accepts(self):
        helped = subprocess.run([sys.executable, "-B", "-m", "tools.setup.wine_compile_probe", "--help"],
                                cwd=ROOT, capture_output=True, text=True, timeout=60).stdout
        self.assertTrue(NEGATIVES)
        for name in NEGATIVES:
            self.assertIn(name, helped)

    def test_hook_markers_come_from_the_real_hook_bytes(self):
        self.assertTrue(MARKERS)
        hooks = b"".join(getattr(diagnostic_mission, name) for name in dir(diagnostic_mission)
                         if name.endswith("_HOOK") and isinstance(getattr(diagnostic_mission, name), bytes))
        for marker in MARKERS:
            self.assertIn(marker.encode(), hooks)

    def test_unknown_probe_is_refused(self):
        with self.assertRaises(ValueError):
            probe.subcases_for("nope", ROOT)

    def test_discovery_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / probe.SCRIPT_ROOT
            base.mkdir(parents=True)
            with mock.patch.object(probe, "MAX_SOURCE_FILES", 2):
                for index in range(3):
                    (base / ("f%d.c" % index)).write_text("// SelfTest\n")
                with self.assertRaises(ValueError):
                    probe.discover_subcases(directory)


class MarkerParsingTests(unittest.TestCase):
    def test_exact_markers_parse_with_values(self):
        found = probe.parse_markers({"a.log": marker_text(["x_one"], True, "observed=1") +
                                              marker_text(["x_two"], False, "bad")})
        self.assertEqual(found["x_one"], [[True, "observed=1"]])
        self.assertEqual(found["x_two"], [[False, "bad"]])

    def test_lookalike_lines_do_not_parse(self):
        self.assertEqual(probe.parse_markers({"a.log": "[HC SelfTest] name=x pass=maybe detail=\n"
                                                      "HC SelfTest name=x pass=true detail=\n"}), {})

    def test_marker_count_is_bounded(self):
        with mock.patch.object(probe, "MAX_MARKERS", 2):
            with self.assertRaises(ValueError):
                probe.parse_markers({"a.log": marker_text(["a", "b", "c"])})


class JudgeGreenTests(unittest.TestCase):
    def test_every_requested_subcase_with_clean_logs_passes_as_diagnostic_native(self):
        verdict = probe.judge(selftest_evidence())
        self.assertEqual(verdict["outcome"], "PASS", verdict["problems"])
        self.assertEqual(sorted(verdict["subcases"]), SUBCASES)
        self.assertEqual(verdict["layer"], "diagnostic-native")
        self.assertEqual(verdict["acceptance"], "not_accepted")
        self.assertIn("diag_executable_not_normal_server", verdict["differences"])

    def test_negative_inputs_pass_only_on_rejection_and_preservation(self):
        verdict = probe.judge(negative_evidence())
        self.assertEqual(verdict["outcome"], "PASS", verdict["problems"])
        self.assertEqual(sorted(verdict["subcases"]), sorted(NEGATIVES))


class JudgeRedTests(unittest.TestCase):
    def failing(self, evidence):
        verdict = probe.judge(evidence)
        self.assertEqual(verdict["outcome"], "FAIL")
        return verdict

    def test_module_loaded_but_requested_subcase_never_ran_is_rejected(self):
        evidence = selftest_evidence()
        missing = SUBCASES[0]
        evidence["subcases"].pop(missing)
        verdict = self.failing(evidence)
        self.assertEqual(verdict["subcases"][missing], {"outcome": "MISSING", "reason": "subcase_never_ran"})
        self.assertEqual(verdict["reason"], "subcase_never_ran")

    def test_a_requested_name_the_source_never_prints_is_rejected(self):
        evidence = selftest_evidence(SUBCASES + [probe.NEVER_PRINTED])
        evidence["subcases"].pop(probe.NEVER_PRINTED)
        self.assertEqual(self.failing(evidence)["subcases"][probe.NEVER_PRINTED]["reason"], "subcase_never_ran")

    def test_a_failed_serializer_marker_is_a_failure_with_the_rest_still_listed(self):
        evidence = selftest_evidence()
        failed = SUBCASES[-1]
        evidence["subcases"][failed] = {"markers": [[False, "deserialize_failed"]]}
        verdict = self.failing(evidence)
        self.assertEqual(verdict["subcases"][failed]["reason"], "subcase_failed")
        others = [name for name in SUBCASES if name != failed]
        self.assertTrue(all(verdict["subcases"][name]["outcome"] == "PASS" for name in others))

    def test_conflicting_markers_for_one_subcase_are_not_a_pass(self):
        evidence = selftest_evidence()
        evidence["subcases"][SUBCASES[0]] = {"markers": [[True, "a"], [False, "b"]]}
        self.assertEqual(self.failing(evidence)["subcases"][SUBCASES[0]]["reason"], "subcase_conflicting")

    def test_stock_plugin_script_error_beside_passing_markers_is_never_a_clean_pass(self):
        evidence = selftest_evidence()
        evidence["logs"].update(script_errors=2, script_error_lines=["SCRIPT (E): stock plugin"])
        verdict = self.failing(evidence)
        self.assertIn("script_errors", verdict["problems"])
        self.assertEqual(verdict["errors"]["script"], 2)
        self.assertEqual(verdict["errors"]["script_lines"], ["SCRIPT (E): stock plugin"])

    def test_engine_errors_and_dumps_stay_visible(self):
        evidence = selftest_evidence()
        evidence["logs"].update(engine_errors=["Cannot compile"], dumps=1)
        verdict = self.failing(evidence)
        self.assertIn("engine_errors", verdict["problems"])
        self.assertEqual(verdict["errors"]["engine"], ["Cannot compile"])

    def test_an_unrequested_failing_selftest_is_reported(self):
        evidence = selftest_evidence(SUBCASES[:1])
        evidence["subcases"]["unasked_check"] = {"markers": [[False, "boom"]]}
        verdict = self.failing(evidence)
        self.assertEqual(verdict["unrequested_failures"], ["unasked_check"])

    def test_stale_logs_and_no_mission_and_wrong_executable_fail(self):
        evidence = selftest_evidence()
        evidence["logs"].update(rejected={"script_old.log": "stale_older_than_launch"})
        self.assertIn("stale_or_unreadable_logs", self.failing(evidence)["problems"])
        evidence = selftest_evidence()
        evidence["logs"]["modules"] = ["World"]
        self.assertIn("mission_not_loaded", self.failing(evidence)["problems"])
        evidence = selftest_evidence()
        evidence["executable_kind"] = "dedicated-server"
        self.assertIn("wrong_executable_kind", self.failing(evidence)["problems"])

    def test_test_hook_bytes_in_the_normal_artifact_fail(self):
        evidence = selftest_evidence()
        evidence["normal_artifact"]["hook_bytes"] = [MARKERS[0]]
        self.assertIn("test_hook_in_normal_artifact", self.failing(evidence)["problems"])
        evidence["normal_artifact"].pop("hook_bytes")
        self.assertIn("artifact_not_checked", self.failing(evidence)["problems"])

    def test_hook_bytes_are_found_in_a_blob_that_carries_them_and_absent_otherwise(self):
        self.assertEqual(probe.hook_bytes_in(b"nothing here", MARKERS), [])
        self.assertEqual(probe.hook_bytes_in(b"class " + MARKERS[0].encode() + b" : X", MARKERS), [MARKERS[0]])

    def test_clients_survivors_and_modified_files_fail(self):
        for key, value, problem in (("client_count", 1, "client_claim_refused"),
                                    ("cleanup", {"observed": True, "survivors": [{"pid": 3}]}, "child_survived_launcher"),
                                    ("guard", {"observed": True, "changed": ["server_exe"]},
                                     "stock_or_server_file_modified")):
            with self.subTest(problem=problem):
                evidence = selftest_evidence()
                evidence[key] = value
                self.assertIn(problem, self.failing(evidence)["problems"])

    def test_empty_or_invalid_request_and_unknown_probe_fail(self):
        evidence = selftest_evidence()
        evidence["requested"] = []
        self.assertIn("requested_subcases_invalid", self.failing(evidence)["problems"])
        self.assertEqual(probe.judge({"probe": "nope"})["reason"], "probe_unknown")


class NegativeInputTests(unittest.TestCase):
    def mutate(self, name, **fields):
        evidence = negative_evidence()
        evidence["subcases"][name] = fields
        return probe.judge(evidence)

    def test_negative_input_that_was_accepted_or_not_preserved_fails(self):
        name = NEGATIVES[0]
        self.assertEqual(self.mutate(name, status="initialized", settings_original_preserved=True)
                         ["subcases"][name]["reason"], "negative_input_not_rejected")
        self.assertEqual(self.mutate(name, status="settings-rejected", settings_original_preserved=False)
                         ["subcases"][name]["reason"], "original_not_preserved")
        self.assertEqual(self.mutate(name, status="settings-rejected", settings_original_preserved=None)
                         ["subcases"][name]["reason"], "original_not_preserved")

    def test_a_negative_case_that_never_ran_is_missing(self):
        verdict = self.mutate(NEGATIVES[0])
        self.assertEqual(verdict["subcases"][NEGATIVES[0]]["outcome"], "MISSING")

    def test_rejection_does_not_hide_errors_from_the_logs(self):
        evidence = negative_evidence()
        evidence["logs"].update(script_errors=1, script_error_lines=["SCRIPT (E): after rejection"])
        verdict = probe.judge(evidence)
        self.assertEqual(verdict["outcome"], "FAIL")
        self.assertEqual(verdict["errors"]["script"], 1)
        self.assertEqual(verdict["subcases"][NEGATIVES[0]]["outcome"], "PASS")


class OwnedProbeRunTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.host = FakeHost(self.root / "host")
        self.server_root = self.root / "server"
        for name in ("DayZServer_x64.exe", "DayZDiag_x64.exe", "battleye/BEServer_x64.dll",
                     "mpmissions/dayzOffline.chernarusplus/init.c"):
            path = self.server_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("stock")
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.calls = []
        self.blob = b"normal artifact without hook bytes"

    def start(self, *, texts=None, status="initialized", preserved=True, survive=False, tamper=False,
              kind="diagnostic-server", blob=None):
        from tools.release import compile_gate
        blob = blob or self.blob
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for name in ("CI", "GITHUB_ACTIONS"):
            os.environ.pop(name, None)
        stack.enter_context(mock.patch.object(compile_gate, "prerequisites",
                                              return_value=(self.server_root, self.root / "prefix", None)))
        stack.enter_context(mock.patch.object(compile_gate, "require_client_idle"))
        stack.enter_context(mock.patch.object(server, "compute_pin", return_value=(
            {"pbo_name": server.PBO_NAME, "pbo_sha256": hashlib.sha256(blob).hexdigest()}, blob)))

        def popen(argv, cwd=None, stdout=None, stderr=None, start_new_session=None):
            self.calls.append(argv)
            experiment = Path(argv[argv.index("--experiment") + 1])
            profiles = experiment / "profiles"
            profiles.mkdir(parents=True)
            body = "Module: World; loaded 3 files\nModule: Mission; loaded 2 files\n" + (texts or "")
            log = profiles / "script_1.log"
            log.write_text(body)
            later = time.time_ns() + 5_000_000_000
            os.utime(log, ns=(later, later))
            (experiment / "compiler-report.json").write_text(json.dumps({
                "executable_kind": kind, "status": status, "settings_original_preserved": preserved}))
            self.host.process(4300, 1, 4300)

            def on_exit():
                if tamper:
                    (self.server_root / "DayZDiag_x64.exe").write_text("modified")
            return FakeProcess(self.host, 4300, polls=1, survive=survive, on_exit=on_exit)
        return popen

    def run_probe(self, popen, name="core-selftests", **extra):
        return probe.run_probe(ROOT, self.root / ("out-" + name), name, cache=self.cache,
                               lock_path=self.root / "lock", proc_root=self.host.proc, net_root=self.host.net,
                               popen=popen, sleep=lambda seconds: None, grace=0, seconds=30, **extra)

    def test_all_markers_printed_passes_and_uses_the_diagnostic_flags(self):
        popen = self.start(texts=marker_text(SUBCASES))
        verdict = self.run_probe(popen, subcases=SUBCASES)
        self.assertEqual(verdict["outcome"], "PASS", verdict.get("problems"))
        self.assertEqual(len(self.calls), 1)
        self.assertIn("--diagnostic", self.calls[0])
        self.assertIn("--diagnostic-selftests", self.calls[0])
        self.assertIn("tools.setup.wine_compile_probe", self.calls[0])

    def test_module_loaded_but_one_requested_subcase_never_printed_is_rejected(self):
        popen = self.start(texts=marker_text(SUBCASES[1:]))
        verdict = self.run_probe(popen, subcases=SUBCASES)
        self.assertEqual(verdict["outcome"], "FAIL")
        self.assertEqual(verdict["subcases"][SUBCASES[0]]["reason"], "subcase_never_ran")

    def test_failed_serializer_marker_and_stock_script_error_are_not_a_clean_pass(self):
        popen = self.start(texts=marker_text(SUBCASES[:-1]) + marker_text(SUBCASES[-1:], passed=False, detail="x")
                           + "SCRIPT (E): stock plugin\n")
        verdict = self.run_probe(popen, subcases=SUBCASES)
        self.assertEqual(verdict["outcome"], "FAIL")
        self.assertIn("subcase_failed", verdict["problems"])
        self.assertIn("script_errors", verdict["problems"])

    def test_the_control_name_is_rejected_beside_real_subcases(self):
        popen = self.start(texts=marker_text(SUBCASES))
        verdict = self.run_probe(popen, subcases=SUBCASES, extra=[probe.NEVER_PRINTED])
        self.assertEqual(verdict["subcases"][probe.NEVER_PRINTED]["reason"], "subcase_never_ran")

    def test_hook_bytes_in_the_normal_artifact_fail_the_run(self):
        popen = self.start(texts=marker_text(SUBCASES), blob=b"class " + MARKERS[0].encode() + b" : CustomMission")
        self.assertIn("test_hook_in_normal_artifact", self.run_probe(popen, subcases=SUBCASES)["problems"])

    def test_surviving_child_and_modified_stock_file_fail(self):
        verdict = self.run_probe(self.start(texts=marker_text(SUBCASES), survive=True), subcases=SUBCASES)
        self.assertIn("child_survived_launcher", verdict["problems"])

    def test_modified_stock_executable_during_the_boot_fails(self):
        popen = self.start(texts=marker_text(SUBCASES), tamper=True)
        self.assertIn("stock_or_server_file_modified", self.run_probe(popen, subcases=SUBCASES)["problems"])

    def test_each_settings_negative_is_its_own_boot_with_its_own_assertion(self):
        popen = self.start(status="settings-rejected", kind="dedicated-server")
        verdict = self.run_probe(popen, "settings-negatives")
        self.assertEqual(verdict["outcome"], "PASS", verdict.get("problems"))
        self.assertEqual(len(self.calls), len(NEGATIVES))
        self.assertEqual(sorted(argv[argv.index("--settings-case") + 1] for argv in self.calls), sorted(NEGATIVES))

    def test_an_accepted_negative_input_fails(self):
        popen = self.start(status="initialized", kind="dedicated-server")
        verdict = self.run_probe(popen, "settings-negatives")
        self.assertEqual(verdict["outcome"], "FAIL")
        self.assertIn("negative_input_not_rejected", verdict["problems"])

    def test_a_missing_diag_executable_blocks_instead_of_running(self):
        (self.server_root / "DayZDiag_x64.exe").unlink()
        verdict = self.run_probe(self.start(texts=marker_text(SUBCASES)), subcases=SUBCASES)
        self.assertEqual((verdict["outcome"], verdict["reason"]), ("BLOCKED", "executable_absent"))
        self.assertEqual(self.calls, [])

    def test_hosted_ci_and_bad_requests_are_refused_before_launch(self):
        popen = self.start()
        with mock.patch.dict(os.environ, {"CI": "true"}):
            with self.assertRaises(ValueError):
                self.run_probe(popen)
        with self.assertRaises(ValueError):
            self.run_probe(popen, subcases=["Bad Name"])
        with self.assertRaises(ValueError):
            probe.run_probe(ROOT, self.root / "x", "nope")
        self.assertEqual(self.calls, [])

    def test_the_probe_takes_the_shared_host_lock(self):
        from tools.release import host_lock as lock
        events = []

        @contextlib.contextmanager
        def recorder(holder, path=None):
            events.append(holder)
            yield

        popen = self.start(texts=marker_text(SUBCASES))
        with mock.patch.object(lock, "host_lock", recorder):
            self.run_probe(popen, subcases=SUBCASES)
        self.assertEqual(events, [probe.HOLDER])
        self.assertRegex(probe.HOLDER, r"[a-z_]{1,40}\Z")


class CommandLineAndDriverTests(unittest.TestCase):
    def test_a_refused_lock_is_a_refusal(self):
        from tools.release.host_lock import LockRefused
        with mock.patch.object(probe, "run_probe", side_effect=LockRefused("native host busy: holder=x")):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(probe.main(["run", "--probe", "core-selftests", "--tree", "."]), 1)
        self.assertIn("REFUSED", out.getvalue())

    def test_control_passes_only_when_the_never_printed_subcase_is_rejected(self):
        rejected = {"outcome": "FAIL", "subcases": {probe.NEVER_PRINTED: {"reason": "subcase_never_ran"}}}
        with mock.patch.object(probe, "run_probe", return_value=rejected) as launch:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(probe.main(["control", "missing_subcase", "--tree", "."]), 0)
        self.assertEqual(launch.call_args.kwargs["extra"], [probe.NEVER_PRINTED])
        self.assertIn("CONTROL PASS", out.getvalue())
        passing = {"outcome": "PASS", "subcases": {}}
        with mock.patch.object(probe, "run_probe", return_value=passing):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(probe.main(["control", "missing_subcase", "--tree", "."]), 1)
        self.assertIn("CONTROL FAIL", out.getvalue())

    def test_plan_lists_probes_from_source_and_launches_nothing(self):
        plan = probe.plan_report(ROOT)
        self.assertEqual(plan["probes"]["core-selftests"]["subcases"], SUBCASES)
        self.assertEqual(plan["probes"]["settings-negatives"]["subcases"], NEGATIVES)

    def test_registered_drivers_are_native_explicit_and_name_their_capability(self):
        for driver_id, need in (("native.probe_adapter", "dayzdiag"), ("native.probe_settings", "normal_server")):
            driver = drivers.DRIVERS[driver_id]
            self.assertEqual((driver.kind, driver.trust, driver.needs), ("native", "explicit", (need,)))
            self.assertIn("tools.testing.native_probe", driver.argv(ROOT, {}))
        capabilities = {need: "available" for item in drivers.DRIVERS.values() for need in item.needs}
        lane = automation.native_lane(capabilities, environ={})
        row = next(item for item in lane["drivers"] if item["id"] == "native.probe_adapter")
        self.assertEqual(row["outcome"], "NOTRUN")

    def test_driver_judge_passes_only_a_terminal_zero_client_pass(self):
        passing = probe.judge(selftest_evidence())
        self.assertEqual(probe.judge_output(0, "x\n" + json.dumps(passing))[0], "PASS")
        self.assertEqual(probe.judge_output(1, json.dumps(passing))[0], "FAIL")
        failing = selftest_evidence()
        failing["subcases"].pop(SUBCASES[0])
        self.assertEqual(probe.judge_output(1, json.dumps(probe.judge(failing)))[0], "FAIL")
        self.assertEqual(probe.judge_output(0, "native_probe: PASS")[0], "FAIL")
        self.assertEqual(probe.judge_output(1, "native_probe: REFUSED busy")[0], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
