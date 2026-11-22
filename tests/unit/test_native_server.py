"""Normal-server adapter tests (AV-T007). Synthetic: no DayZ, Wine or real socket is involved.

The judge is exercised with evidence records built from the provider contract itself; the orchestrator is
exercised with a fake launcher and a fake /proc tree. A pass here is never DayZ evidence.
"""
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest import mock

from tests.unit.native_fakes import FakeHost, FakeProcess
from tools.testing import automation, drivers, native_common as common, native_server as server

PROVIDER = server.PROVIDERS["wine"]
PIN = hashlib.sha256(b"synthetic pbo").hexdigest()
OTHER = hashlib.sha256(b"another pbo").hexdigest()


def signature_report(pin=PIN, stem="SyntheticKey"):
    return {"status": "signed-development", "files": {
        "addons/" + server.PBO_NAME: pin,
        "addons/%s.%s.bisign" % (server.PBO_NAME, stem): OTHER,
        "keys/%s.bikey" % stem: OTHER}}


def good_evidence():
    return {
        "schema": 1, "provider": "wine", "client_count": 0, "synthetic": True,
        "pin": {"pbo_name": server.PBO_NAME, "pbo_sha256": PIN},
        "signature_report": signature_report(),
        "gate": {"returncode": 0, "pass_line": True, "fail_line": False, "pbo_sha256": PIN},
        "report": {"environment": PROVIDER.label, "client_count": 0, "pbo_sha256": PIN, "status": "timeout",
                   "engine_error_observed": False, "requested_gameplay_bind": "127.0.0.1:2402"},
        "logs": {"fresh_files": 2, "rejected": {}, "skipped": {}, "modules": list(server.REQUIRED_MODULES),
                 "script_errors": 0, "engine_errors": [], "dumps": 0},
        "sockets": {"sampled": 3, "claim": {"claimed": True, "reason": "owned_exact_bind",
                                            "ip": "127.0.0.1", "port": 2402}},
        "cleanup": {"observed": True, "survivors": [], "port_free": True},
        "guard": {"observed": True, "changed": []},
    }


def verdict_for(evidence):
    return server.judge(evidence)


class JudgeGreenTests(unittest.TestCase):
    def test_complete_evidence_passes_zero_client_only(self):
        verdict = verdict_for(good_evidence())
        self.assertEqual(verdict["outcome"], "PASS", verdict["failed"])
        self.assertEqual([item["name"] for item in verdict["checks"]], list(PROVIDER.required))
        self.assertEqual(verdict["claims"], list(PROVIDER.claims))
        self.assertEqual(verdict["client_count"], 0)
        self.assertEqual(verdict["acceptance"], "not_accepted")
        self.assertIn("signature_enforced_join", verdict["unobserved"])

    def test_every_required_check_is_load_bearing(self):
        # Removing the evidence behind any one required check must fail the verdict.
        removals = {"provider": ("report", {"environment": "other"}), "pbo_pin": ("pin", {}), "signature": ("signature_report", None),
                    "gate": ("gate", {}), "logs_fresh": ("logs", {}), "modules": ("logs", {"fresh_files": 1}),
                    "socket": ("sockets", {}), "cleanup": ("cleanup", {}), "guard": ("guard", {})}
        for check, (key, value) in removals.items():
            with self.subTest(check=check):
                evidence = good_evidence()
                evidence[key] = value
                verdict = verdict_for(evidence)
                self.assertEqual(verdict["outcome"], "FAIL")
                self.assertFalse(next(item for item in verdict["checks"] if item["name"] == check)["ok"])

    def test_unknown_provider_fails(self):
        self.assertEqual(verdict_for({"provider": "bogus"})["reason"], "provider_unknown")
        self.assertEqual(verdict_for("not a record")["outcome"], "FAIL")

    def test_malformed_check_input_fails_instead_of_raising(self):
        evidence = good_evidence()
        evidence["logs"] = ["not", "a", "dict"]
        self.assertEqual(verdict_for(evidence)["outcome"], "FAIL")


class JudgeRedTests(unittest.TestCase):
    def failing(self, mutate):
        evidence = good_evidence()
        mutate(evidence)
        verdict = verdict_for(evidence)
        self.assertEqual(verdict["outcome"], "FAIL")
        self.assertEqual(verdict["claims"], [])
        return verdict["failed"]

    def test_old_log_or_init_marker_does_not_pass(self):
        failed = self.failing(lambda e: e["logs"].update(rejected={"script_old.log": "stale_older_than_launch"}))
        self.assertIn("stale_or_unreadable_logs", failed)
        self.assertIn("no_fresh_log", self.failing(lambda e: e["logs"].update(fresh_files=0)))

    def test_mismatched_pbo_between_pin_gate_and_launch_fails(self):
        self.assertIn("pbo_pin_mismatch", self.failing(lambda e: e["report"].update(pbo_sha256=OTHER)))
        self.assertIn("pbo_pin_mismatch", self.failing(lambda e: e["gate"].update(pbo_sha256=OTHER)))
        self.assertIn("pbo_pin_missing", self.failing(lambda e: e["pin"].update(pbo_sha256="short")))

    def test_mismatched_signature_fails(self):
        self.assertIn("signature_pbo_mismatch",
                      self.failing(lambda e: e.update(signature_report=signature_report(pin=OTHER))))
        self.assertIn("signature_not_verified",
                      self.failing(lambda e: e["signature_report"].update(status="failed")))
        report = signature_report()
        report["files"]["keys/Other.biprivatekey"] = OTHER
        self.assertIn("signature_private_key_listed", self.failing(lambda e: e.update(signature_report=report)))
        report = signature_report()
        del report["files"]["keys/SyntheticKey.bikey"]
        self.assertIn("signature_file_mismatch", self.failing(lambda e: e.update(signature_report=report)))

    def test_a_signed_file_changed_after_signing_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            signed = Path(directory)
            (signed / "addons").mkdir()
            (signed / "keys").mkdir()
            blob = b"signed pbo"
            pin = hashlib.sha256(blob).hexdigest()
            names = {"addons/" + server.PBO_NAME: blob,
                     "addons/%s.K.bisign" % server.PBO_NAME: b"sig", "keys/K.bikey": b"key"}
            for name, data in names.items():
                (signed / name).write_bytes(data)
            report = {"status": "signed-development",
                      "files": {name: hashlib.sha256(data).hexdigest() for name, data in names.items()}}
            self.assertTrue(server.check_signature(report, server.PBO_NAME, pin, signed)[0])
            (signed / "addons" / server.PBO_NAME).write_bytes(b"swapped")
            ok, reason, _ = server.check_signature(report, server.PBO_NAME, pin, signed)
            self.assertFalse(ok)
            self.assertEqual(reason, "signature_files_changed")

    def test_wildcard_or_unbound_socket_claim_fails(self):
        wildcard = common.claim_socket([{"proto": "udp", "ip": "0.0.0.0", "port": 2402, "inode": 1, "owner": 7}],
                                       "127.0.0.1", 2402)
        failed = self.failing(lambda e: e["sockets"].update(claim=wildcard))
        self.assertIn("wildcard_not_a_claim", failed)
        self.assertIn("socket_not_observed", self.failing(lambda e: e["sockets"].update(sampled=0)))
        self.assertIn("not_bound", self.failing(
            lambda e: e["sockets"].update(claim=common.claim_socket([], "127.0.0.1", 2402))))

    def test_child_surviving_the_launcher_or_a_held_port_fails(self):
        self.assertIn("child_survived_launcher",
                      self.failing(lambda e: e["cleanup"].update(survivors=[{"pid": 5, "pgrp": 5}])))
        self.assertIn("port_not_released", self.failing(lambda e: e["cleanup"].update(port_free=False)))
        self.assertIn("cleanup_not_observed", self.failing(lambda e: e.update(cleanup={})))

    def test_modified_stock_or_server_files_fail(self):
        self.assertIn("stock_or_server_file_modified",
                      self.failing(lambda e: e["guard"].update(changed=["server_exe"])))
        self.assertIn("guard_not_observed", self.failing(lambda e: e.update(guard={})))

    def test_script_engine_and_gate_errors_are_never_a_pass(self):
        self.assertIn("script_errors", self.failing(lambda e: e["logs"].update(script_errors=1)))
        self.assertIn("engine_errors", self.failing(lambda e: e["logs"].update(engine_errors=["x"])))
        self.assertIn("engine_errors", self.failing(lambda e: e["logs"].update(dumps=1)))
        self.assertIn("compile_gate_failed", self.failing(lambda e: e["gate"].update(returncode=1)))
        self.assertIn("compile_gate_failed", self.failing(lambda e: e["report"].update(status="compiler-error")))
        self.assertIn("mission_not_loaded", self.failing(lambda e: e["logs"].update(modules=["World"])))

    def test_any_client_claim_is_refused(self):
        self.assertIn("client_claim_refused", self.failing(lambda e: e.update(client_count=1)))
        self.assertIn("client_claim_refused", self.failing(lambda e: e["report"].update(client_count=2)))
        self.assertIn("client_claim_refused", self.failing(lambda e: e.update(client_claims=["joined"])))

    def test_provider_label_must_match_the_contract(self):
        self.assertIn("provider_mismatch", self.failing(lambda e: e["report"].update(environment="native-windows-server")))


class WindowsProviderTests(unittest.TestCase):
    def evidence(self, **changes):
        record = server.windows_evidence({"pbo_name": server.PBO_NAME, "pbo_sha256": PIN}, PIN,
                                         "boot_verdict=connect_enabled\n", 0, 5_000, 1_000, [])
        record.update(changes)
        return record

    def test_attach_only_contract_passes_without_claiming_ownership(self):
        self.assertEqual(self.evidence()["environment"], server.PROVIDERS["windows"].label)
        verdict = server.judge(self.evidence())
        self.assertEqual(verdict["outcome"], "PASS", verdict["failed"])
        for gap in ("process_ownership", "socket_binding", "process_cleanup"):
            self.assertIn(gap, verdict["unobserved"])
        self.assertNotIn("loopback_socket", verdict["claims"])

    def test_windows_never_borrows_the_wine_label_and_stale_rpt_fails(self):
        self.assertIn("provider_mismatch", server.judge(self.evidence(environment=PROVIDER.label))["failed"])
        stale = server.windows_evidence({"pbo_name": server.PBO_NAME, "pbo_sha256": PIN}, PIN,
                                        "boot_verdict=connect_enabled\n", 0, 500, 1_000, [])
        self.assertIn("stale_or_unreadable_logs", server.judge(stale)["failed"])
        self.assertIn("boot_verdict_None", server.judge(server.windows_evidence(
            {"pbo_name": server.PBO_NAME, "pbo_sha256": PIN}, PIN, "no verdict here", 0, 5_000, 1_000, []))["failed"])


class LogCollectionTests(unittest.TestCase):
    def test_collect_logs_reads_only_fresh_logs_and_keeps_every_error(self):
        with tempfile.TemporaryDirectory() as directory:
            profiles = Path(directory) / "profiles"
            profiles.mkdir()
            old = profiles / "script_old.log"
            old.write_text("SCRIPT (E): stale failure\n")
            os.utime(old, ns=(1_000, 1_000))
            fresh = profiles / "script_new.log"
            fresh.write_text("Module: World; loaded 3 files\nModule: Mission; loaded 2 files\n"
                             "SCRIPT    (E): stock plugin failure\n")
            logs = server.collect_logs(directory, 2_000)
            self.assertEqual(logs["rejected"], {"script_old.log": "stale_older_than_launch"})
            self.assertEqual(logs["modules"], ["World", "Mission"])
            self.assertEqual(logs["script_errors"], 1)
            self.assertEqual(logs["fresh_files"], 1)

    def test_runtime_json_error_after_mission_is_counted_separately_not_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            profiles = Path(directory) / "profiles"
            profiles.mkdir()
            (profiles / "script_new.log").write_text(
                "Module: Mission; loaded 2 files\nSCRIPT (E): JSON ERROR missing data\n")
            logs = server.collect_logs(directory, 0)
            self.assertEqual(logs["runtime_json_errors"], 1)
            self.assertEqual(logs["script_errors"], 0)

    def test_engine_dump_files_are_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            profiles = Path(directory) / "profiles"
            profiles.mkdir()
            (profiles / "ErrorMessage_1.mdmp").write_bytes(b"d")
            self.assertEqual(server.collect_logs(directory, 0)["dumps"], 1)


class GateOutputTests(unittest.TestCase):
    def test_gate_output_is_parsed_from_its_own_lines_only(self):
        text = "noise\ncompile_gate: pbo_sha256=%s package_cache=hit\ncompile_gate: PASS status=timeout\n" % PIN
        parsed = server.parse_gate_output(text, 0)
        self.assertEqual((parsed["pbo_sha256"], parsed["pass_line"], parsed["fail_line"]), (PIN, True, False))
        spoof = server.parse_gate_output("see compile_gate: PASS status=x mid-line\n", 0)
        self.assertFalse(spoof["pass_line"])
        failed = server.parse_gate_output("compile_gate: FAIL status=compiler-error\n", 1)
        self.assertTrue(failed["fail_line"])


class OwnedRunTests(unittest.TestCase):
    """run_wine end to end against a fake launcher and a fake /proc tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.host = FakeHost(self.root / "host")
        self.server_root = self.root / "server"
        for name in ("DayZServer_x64.exe", "battleye/BEServer_x64.dll",
                     "mpmissions/dayzOffline.chernarusplus/init.c"):
            path = self.server_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("stock")
        self.prefix = self.root / "prefix"
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.calls = []
        self.blob = b"synthetic pbo"
        self.pin = hashlib.sha256(self.blob).hexdigest()

    def patches(self, *, gate_pass=True, survive=False, bind=("127.0.0.1", 2402), pin=None,
                script_text=None, tamper=False):
        from tools.release import compile_gate
        pin = pin or self.pin
        experiment = self.cache / "run-1"

        def on_start():
            self.host.process(4242, 1, 4242, sockets=(777,))
            self.host.bind(bind[0], bind[1], 777)
            profiles = experiment / "profiles"
            profiles.mkdir(parents=True)
            log = profiles / "script_1.log"
            log.write_text(script_text or "Module: World; loaded 3 files\nModule: Mission; loaded 2 files\n")
            later = time.time_ns() + 5_000_000_000   # a launch-relative write time, past coarse fs clocks
            os.utime(log, ns=(later, later))
            (experiment / "compiler-report.json").write_text(json.dumps({
                "environment": PROVIDER.label, "client_count": 0, "pbo_sha256": pin, "status": "timeout",
                "engine_error_observed": False, "requested_gameplay_bind": "127.0.0.1:2402"}))

        def on_exit():
            if tamper:
                (self.server_root / "DayZServer_x64.exe").write_text("modified")

        def popen(argv, cwd=None, stdout=None, stderr=None, start_new_session=None):
            self.calls.append(argv)
            line = "compile_gate: pbo_sha256=%s package_cache=miss\n" % pin
            line += "compile_gate: PASS status=timeout\n" if gate_pass else "compile_gate: FAIL status=x\n"
            stdout.write(line.encode())
            stdout.flush()
            return FakeProcess(self.host, 4242, polls=2, returncode=0 if gate_pass else 1, survive=survive,
                               on_start=on_start, on_exit=on_exit)

        def signer(source, output):
            names = {"addons/" + server.PBO_NAME: self.blob,
                     "addons/%s.K.bisign" % server.PBO_NAME: b"sig", "keys/K.bikey": b"key"}
            for name, data in names.items():
                common.write_owned(output, name, data)
            return {"status": "signed-development",
                    "files": {name: hashlib.sha256(data).hexdigest() for name, data in names.items()}}

        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.dict(os.environ, {}, clear=False))
        for name in ("CI", "GITHUB_ACTIONS"):
            os.environ.pop(name, None)
        stack.enter_context(mock.patch.object(compile_gate, "prerequisites",
                                              return_value=(self.server_root, self.prefix, None)))
        stack.enter_context(mock.patch.object(compile_gate, "require_client_idle"))
        stack.enter_context(mock.patch.object(server, "compute_pin", return_value=(
            {"pbo_name": server.PBO_NAME, "pbo_sha256": self.pin}, self.blob)))
        self.addCleanup(stack.close)
        return popen, signer

    def run_wine(self, popen, signer, **extra):
        return server.run_wine(self.root, self.root / "out", cache=self.cache, lock_path=self.root / "lock",
                               proc_root=self.host.proc, net_root=self.host.net, popen=popen, signer=signer,
                               sleep=lambda seconds: None, grace=0, seconds=30, **extra)

    def test_clean_run_passes_with_an_owned_exact_socket_and_full_cleanup(self):
        popen, signer = self.patches()
        verdict = self.run_wine(popen, signer)
        self.assertEqual(verdict["outcome"], "PASS", verdict.get("failed"))
        self.assertEqual(self.calls[0][1:4], ["-B", "-m", "tools.release.compile_gate"])
        self.assertTrue((self.root / "out" / "evidence.json").is_file())

    def test_launch_is_wrapped_never_reimplemented(self):
        popen, signer = self.patches()
        self.run_wine(popen, signer)
        self.assertEqual(len(self.calls), 1)
        self.assertIn("--server-root", self.calls[0])
        self.assertIn(str(self.server_root), self.calls[0])

    def test_child_surviving_the_launcher_fails(self):
        popen, signer = self.patches(survive=True)
        verdict = self.run_wine(popen, signer)
        self.assertEqual(verdict["outcome"], "FAIL")
        self.assertIn("child_survived_launcher", verdict["failed"])
        cleanup = next(item for item in verdict["checks"] if item["name"] == "cleanup")
        self.assertEqual(cleanup["reason"], "child_survived_launcher")

    def test_wildcard_socket_does_not_pass(self):
        popen, signer = self.patches(bind=("0.0.0.0", 2402))
        verdict = self.run_wine(popen, signer)
        self.assertEqual(verdict["outcome"], "FAIL")
        self.assertIn("wildcard_not_a_claim", verdict["failed"])

    def test_each_control_claim_override_produces_its_expected_rejection_on_a_healthy_run(self):
        overrides = {"wildcard_claim": {"ip": "0.0.0.0", "port": 2402}, "unbound_port": {"ip": "127.0.0.1", "port": 2499}}
        for name, claim in overrides.items():
            with self.subTest(control=name):
                self.calls.clear()
                popen, signer = self.patches()
                out = self.root / ("out-" + name)
                verdict = server.run_wine(self.root, out, cache=self.cache, lock_path=self.root / "lock",
                                          proc_root=self.host.proc, net_root=self.host.net, popen=popen,
                                          signer=signer, sleep=lambda seconds: None, grace=0, seconds=30,
                                          claim=claim)
                self.assertEqual(verdict["outcome"], "FAIL")
                self.assertIn(server.CONTROLS[name][0], verdict["failed"])
                shutil.rmtree(self.cache / "run-1")

    def test_a_modified_stock_server_file_fails(self):
        popen, signer = self.patches(tamper=True)
        verdict = self.run_wine(popen, signer)
        self.assertIn("stock_or_server_file_modified", verdict["failed"])

    def test_gate_report_for_a_different_pbo_fails(self):
        popen, signer = self.patches(pin=OTHER)
        self.assertIn("pbo_pin_mismatch", self.run_wine(popen, signer)["failed"])

    def test_failed_gate_and_script_error_do_not_pass(self):
        popen, signer = self.patches(gate_pass=False)
        self.assertIn("compile_gate_failed", self.run_wine(popen, signer)["failed"])

    def test_script_error_in_a_fresh_log_is_retained_and_fails(self):
        popen, signer = self.patches(script_text="Module: Mission; loaded 2 files\nSCRIPT (E): boom\n"
                                                 "Module: World; loaded 1 files\n")
        verdict = self.run_wine(popen, signer)
        self.assertIn("script_errors", verdict["failed"])

    def test_an_expected_pin_the_tree_does_not_produce_launches_nothing(self):
        popen, signer = self.patches()
        verdict = self.run_wine(popen, signer, expect_pin="0" * 64)
        self.assertEqual((verdict["outcome"], verdict["reason"]), ("FAIL", "pbo_pin_mismatch"))
        self.assertEqual(self.calls, [])

    def test_hosted_ci_and_a_reused_output_directory_are_refused_before_launch(self):
        popen, signer = self.patches()
        with mock.patch.dict(os.environ, {"CI": "true"}):
            with self.assertRaises(ValueError):
                self.run_wine(popen, signer)
        (self.root / "out").mkdir()
        with self.assertRaises(ValueError):
            self.run_wine(popen, signer)
        self.assertEqual(self.calls, [])

    def test_missing_prerequisites_block_rather_than_pass(self):
        from tools.release import compile_gate
        popen, signer = self.patches()
        with mock.patch.object(compile_gate, "prerequisites", return_value=(None, None, "isolated server root absent")):
            verdict = self.run_wine(popen, signer)
        self.assertEqual((verdict["outcome"], verdict["reason"]), ("BLOCKED", "prerequisite_absent"))
        self.assertEqual(self.calls, [])

    def test_native_work_runs_inside_the_shared_host_lock(self):
        from tools.release import host_lock as lock
        popen, signer = self.patches()
        events = []

        @contextlib.contextmanager
        def recorder(holder, path=None):
            events.append(("enter", holder))
            yield
            events.append(("exit", holder))

        with mock.patch.object(lock, "host_lock", recorder):
            self.run_wine(popen, signer)
        self.assertEqual(events, [("enter", server.HOLDER), ("exit", server.HOLDER)])
        self.assertRegex(server.HOLDER, r"[a-z_]{1,40}\Z")


class ControlTests(unittest.TestCase):
    def test_a_refused_lock_is_a_refusal_not_a_result(self):
        from tools.release.host_lock import LockRefused
        with mock.patch.object(server, "run_wine", side_effect=LockRefused("native host busy: holder=other")):
            with contextlib.redirect_stdout(__import__("io").StringIO()) as out:
                code = server.main(["run", "--tree", "."])
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", out.getvalue())

    def test_controls_pass_only_when_the_expected_rejection_is_observed(self):
        refusing = {"outcome": "FAIL", "reason": "pbo_pin_mismatch", "failed": ["pbo_pin_mismatch"]}
        with mock.patch.object(server, "run_wine", return_value=refusing) as launch:
            with contextlib.redirect_stdout(__import__("io").StringIO()) as out:
                code = server.main(["control", "wrong_pin", "--tree", "."])
        self.assertEqual(code, 0)
        self.assertIn("CONTROL PASS", out.getvalue())
        self.assertEqual(launch.call_args.kwargs["expect_pin"], "0" * 64)
        passing = {"outcome": "PASS", "reason": "all_required_checks_passed", "failed": []}
        with mock.patch.object(server, "run_wine", return_value=passing):
            with contextlib.redirect_stdout(__import__("io").StringIO()) as out:
                code = server.main(["control", "wildcard_claim", "--tree", "."])
        self.assertEqual(code, 1)
        self.assertIn("CONTROL FAIL", out.getvalue())

    def test_plan_lists_both_providers_and_never_launches(self):
        plan = server.plan_report()
        self.assertEqual(sorted(plan["providers"]), sorted(server.PROVIDERS))
        for provider in plan["providers"].values():
            self.assertIn("signature_enforced_join", provider["unobserved"])


class DriverRegistrationTests(unittest.TestCase):
    def test_registered_native_driver_and_judge_contract(self):
        driver = drivers.DRIVERS["native.server_adapter"]
        self.assertEqual(driver.kind, "native")
        self.assertEqual(driver.trust, "explicit")
        argv = driver.argv(Path("/repo"), {})
        self.assertIn("tools.testing.native_server", argv)
        self.assertIs(automation.drivers.DRIVERS["native.server_adapter"], driver)

    def test_lane_reports_the_adapter_not_missing_and_never_pass(self):
        capabilities = {need: "available" for item in drivers.DRIVERS.values() for need in item.needs}
        lane = automation.native_lane(capabilities, environ={})
        row = next(item for item in lane["drivers"] if item["id"] == "native.server_adapter")
        self.assertEqual(row["outcome"], "NOTRUN")
        blocked = automation.native_lane({}, environ={})
        row = next(item for item in blocked["drivers"] if item["id"] == "native.server_adapter")
        self.assertEqual(row["outcome"], "BLOCKED")
        for item in lane["drivers"]:
            self.assertNotEqual(item["outcome"], "PASS")

    def test_driver_judge_passes_only_a_terminal_zero_client_pass(self):
        passing = server.judge(good_evidence())
        text = "native_server: PASS\n" + json.dumps(passing)
        self.assertEqual(server.judge_output(0, text)[0], "PASS")
        self.assertEqual(server.judge_output(1, text)[0], "FAIL")
        failing = server.judge(dict(good_evidence(), guard={}))
        self.assertEqual(server.judge_output(1, json.dumps(failing))[0], "FAIL")
        self.assertEqual(server.judge_output(0, "native_server: PASS")[0], "FAIL")
        self.assertEqual(server.judge_output(1, "native_server: REFUSED busy")[0], "BLOCKED")
        spoof = dict(passing, client_count=1)
        self.assertEqual(server.judge_output(0, json.dumps(spoof))[0], "FAIL")
        blocked = {"outcome": "BLOCKED", "reason": "prerequisite_absent", "client_count": 0, "acceptance": "not_accepted"}
        self.assertEqual(server.judge_output(0, json.dumps(blocked))[0], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
