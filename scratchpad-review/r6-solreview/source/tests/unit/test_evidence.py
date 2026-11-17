"""Synthetic T0 fixtures only: none of these files establish DayZ behavior."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="synthetic-evidence-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "evidence.json"
        self.artifacts = []
        for name in ("runs/baseline.log", "runs/candidate.log"):
            self.add_artifact(name, "SYNTHETIC TEST FIXTURE; NOT A DAYZ RUN\n")
        self.record = {
            "version": 1, "capability_id": "CAP-01", "status": "observed",
            "game_build": "synthetic-build-not-a-game", "test_ids": ["CE-002"],
            "artifacts": self.artifacts, "observation": "Synthetic observed result.",
            "observations": [{"test_id": "CE-002", "text": "Synthetic result only.",
                              "artifacts": ["runs/candidate.log"]}],
            "method": "Synthetic fixture: exercise the validator only.",
            "layer": "T2", "client_count": 1,
        }

    def add_artifact(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.artifacts[:] = [entry for entry in self.artifacts if entry["path"] != name]
        self.artifacts.append({"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    def accepted(self):
        record = copy.deepcopy(self.record)
        record["status"] = "accepted"
        record["layer"] = "T3"
        report = {
            "version": 1, "method": "Synthetic paired route, three trials per side.",
            "baseline": {"artifact": "runs/baseline.log", "sample_count": 3},
            "candidate": {"artifact": "runs/candidate.log", "sample_count": 3},
            "measurements": [{"metric": "server_frame_p95", "unit": "ms",
                              "baseline": 12.5, "candidate": 12.6}],
        }
        self.add_artifact("performance.json", json.dumps(report))
        record["artifacts"] = copy.deepcopy(self.artifacts)
        record["performance"] = {"report": "performance.json",
                                 "baseline": "runs/baseline.log",
                                 "candidate": "runs/candidate.log"}
        return record

    def validate(self, record=None):
        from tools.validate.evidence import validate
        self.path.write_text(json.dumps(self.record if record is None else record), encoding="utf-8")
        return validate(self.path)

    def assertInvalid(self, record=None, code=None, field=None):
        report = self.validate(record)
        self.assertFalse(report["valid"], report)
        self.assertTrue(report["errors"], report)
        matches = [e for e in report["errors"]
                   if (code is None or e["code"] == code) and (field is None or e["field"] == field)]
        self.assertTrue(matches, report)
        return report

    def test_observed_with_bound_run_evidence_is_structurally_valid(self):
        self.assertTrue(self.validate()["valid"])

    def test_documented_and_hypothesis_allow_pending_fields(self):
        for status in ("documented", "hypothesis"):
            with self.subTest(status=status):
                record = {"version": 1, "capability_id": "CAP-01", "status": status,
                          "game_build": None, "test_ids": [], "artifacts": [],
                          "observation": "", "layer": None, "client_count": None,
                          "pending_fields": ["game_build", "artifacts", "layer"]}
                self.assertTrue(self.validate(record)["valid"])

    def test_schema_rejects_bad_types_enums_unknown_keys_and_version(self):
        changes = [("version", True), ("version", 2), ("capability_id", "CAP-00"),
                   ("capability_id", "cap-01"), ("status", "prototype"),
                   ("layer", "T6"), ("client_count", True), ("client_count", -1),
                   ("test_ids", "CE-002"), ("requires_two_clients", 1),
                   ("unexpected", "value")]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                record = copy.deepcopy(self.record)
                record[key] = value
                self.assertInvalid(record)

    def test_required_identity_fields(self):
        for key in ("version", "capability_id", "status"):
            with self.subTest(key=key):
                record = copy.deepcopy(self.record)
                del record[key]
                self.assertInvalid(record, "required", key)

    def test_all_escalated_statuses_require_runtime_fields(self):
        for status in ("observed", "prototyped", "accepted"):
            for key in ("game_build", "artifacts", "test_ids", "observation",
                        "observations", "method", "layer", "client_count"):
                with self.subTest(status=status, key=key):
                    record = self.accepted() if status == "accepted" else copy.deepcopy(self.record)
                    record["status"] = status
                    record.pop(key)
                    self.assertInvalid(record, "required", key)

    def test_runtime_rejects_pending_and_placeholder_values(self):
        for field in ("game_build", "method", "observation"):
            for value in (None, "", "  ", "TBD", "pending", "unknown", "N/A"):
                with self.subTest(field=field, value=value):
                    record = copy.deepcopy(self.record)
                    record[field] = value
                    self.assertInvalid(record)
        self.record["pending_fields"] = ["game_build"]
        self.assertInvalid(code="pending_runtime", field="pending_fields")

    def test_offline_layers_and_zero_clients_never_escalate(self):
        for layer in ("T0", "T1"):
            self.record["layer"] = layer
            self.assertInvalid(code="runtime_layer", field="layer")
        self.record["layer"] = "T2"
        self.record["client_count"] = 0
        self.assertInvalid(code="runtime_clients", field="client_count")

    def test_exact_test_ids_not_substrings_or_missing_observations(self):
        for ids in (["CE-00"], ["CE-002", "CE-003"], ["CE-002", "CE-002"], ["nonsense"]):
            with self.subTest(ids=ids):
                self.record["test_ids"] = ids
                self.assertInvalid()

    def test_observations_require_one_exact_entry_per_test(self):
        for entries in ([], [self.record["observations"][0]] * 2,
                        [{"test_id": "CE-003", "text": "Synthetic", "artifacts": ["runs/candidate.log"]}]):
            with self.subTest(entries=entries):
                self.record["observations"] = entries
                self.assertInvalid()

    def test_observation_text_and_bound_artifacts_required(self):
        for field, value in (("text", "pending"), ("artifacts", []),
                             ("artifacts", ["unlisted.log"]), ("artifacts", "runs/candidate.log")):
            with self.subTest(field=field, value=value):
                self.record["observations"][0][field] = value
                self.assertInvalid()

    def test_hash_mismatch_missing_file_and_bad_hash_are_distinct(self):
        self.record["artifacts"][0]["sha256"] = "0" * 64
        self.assertInvalid(code="hash_mismatch", field="artifacts[0].sha256")
        self.record["artifacts"][0]["sha256"] = "not a hash"
        self.assertInvalid(code="schema", field="artifacts[0].sha256")
        self.record["artifacts"][0]["sha256"] = "0" * 64
        (self.root / "runs/baseline.log").unlink()
        self.assertInvalid(code="artifact_io", field="artifacts[0].path")

    def test_artifacts_cannot_escape_root_or_use_ambiguous_paths(self):
        for path in ("../outside.log", "/etc/passwd", "C:/Windows/test.log",
                     "runs/../../x", "runs\\candidate.log", "runs/./candidate.log",
                     "runs//candidate.log", "", ".", "runs/"):
            with self.subTest(path=path):
                self.record["artifacts"][0]["path"] = path
                self.assertInvalid(code="unsafe_path", field="artifacts[0].path")

    def test_symlinks_outside_root_rejected(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-outside-") as outside:
            target = Path(outside) / "outside.log"
            target.write_text("SYNTHETIC", encoding="utf-8")
            (self.root / "escape.log").symlink_to(target)
            self.record["artifacts"][0] = {
                "path": "escape.log", "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
            self.assertInvalid(code="unsafe_path", field="artifacts[0].path")

    def test_directories_and_empty_files_are_not_run_evidence(self):
        self.record["artifacts"][0]["path"] = "runs"
        self.assertInvalid(code="artifact_io")
        self.add_artifact("empty.log", "")
        self.record["artifacts"] = self.artifacts
        self.record["observations"][0]["artifacts"] = ["empty.log"]
        self.assertInvalid(code="empty_artifact")

    def test_duplicate_artifact_paths_rejected(self):
        self.record["artifacts"].append(copy.deepcopy(self.record["artifacts"][0]))
        self.assertInvalid(code="duplicate", field="artifacts[2].path")

    def test_sources_are_optional_but_must_be_http_urls(self):
        self.record["sources"] = ["https://community.bistudio.com/wiki/DayZ:Modding_Basics"]
        self.assertTrue(self.validate()["valid"])
        for sources in (["file:///etc/passwd"], ["https://"], "https://example.com", [12]):
            with self.subTest(sources=sources):
                self.record["sources"] = sources
                self.assertInvalid()

    def test_blocked_needs_reproducible_obstacle_and_real_artifacts(self):
        record = {"version": 1, "capability_id": "CAP-14", "status": "blocked",
                  "artifacts": copy.deepcopy(self.artifacts),
                  "obstacle": {"description": "Synthetic fixture reports a missing executable.",
                               "steps": ["Invoke the synthetic test command.", "Inspect its fixture log."]}}
        self.assertTrue(self.validate(record)["valid"])
        for obstacle in (None, "blocked", {}, {"description": "TBD", "steps": ["pending"]},
                         {"description": "Specific synthetic obstacle", "steps": []}):
            with self.subTest(obstacle=obstacle):
                record["obstacle"] = obstacle
                self.assertInvalid(record)
        record.pop("obstacle")
        record.pop("artifacts")
        self.assertInvalid(record, "required", "artifacts")

    def test_accepted_requires_structured_performance_comparison(self):
        record = self.accepted()
        self.assertTrue(self.validate(record)["valid"])
        record.pop("performance")
        self.assertInvalid(record, "required", "performance")
        record["performance"] = "Performance was good"
        self.assertInvalid(record, "schema", "performance")

    def test_two_clients_default_for_audio_and_replication(self):
        for capability in ("CAP-18", "CAP-21"):
            with self.subTest(capability=capability):
                record = self.accepted()
                record["capability_id"] = capability
                self.assertInvalid(record, "two_clients", "client_count")
                record["client_count"] = 2
                self.assertTrue(self.validate(record)["valid"])

    def test_explicit_two_client_requirement_cannot_disable_mandatory_gates(self):
        record = self.accepted()
        record["requires_two_clients"] = True
        self.assertInvalid(record, "two_clients", "client_count")
        record["capability_id"] = "CAP-18"
        record["requires_two_clients"] = False
        self.assertInvalid(record, "two_clients", "client_count")
        record["capability_id"] = "CAP-01"
        self.assertTrue(self.validate(record)["valid"])
        record["impacts"] = ["visibility"]
        self.assertInvalid(record, "two_clients", "client_count")
        for impact in ("network", "audio", "visibility"):
            record["impacts"] = [impact]
            record["client_count"] = 2
            self.assertTrue(self.validate(record)["valid"])

    def test_performance_references_must_be_bound_distinct_artifacts(self):
        for field, value in (("report", "unlisted.json"), ("baseline", "not-bound.log"),
                             ("candidate", "runs/baseline.log"), ("candidate", "performance.json")):
            with self.subTest(field=field, value=value):
                record = self.accepted()
                record["performance"][field] = value
                self.assertInvalid(record)

    def test_performance_report_requires_measurements_and_exact_refs(self):
        mutations = [lambda r: r.update(measurements=[]),
                     lambda r: r.update(baseline={"artifact": "wrong.log", "sample_count": 3}),
                     lambda r: r["candidate"].update(sample_count=0),
                     lambda r: r["baseline"].update(sample_count=True),
                     lambda r: r["measurements"][0].update(candidate="fast"),
                     lambda r: r["measurements"][0].update(baseline=True),
                     lambda r: r["measurements"][0].update(unit=""),
                     lambda r: r.update(method="pending"),
                     lambda r: r.update(version=2)]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                record = self.accepted()
                report = json.loads((self.root / "performance.json").read_text())
                mutation(report)
                self.replace_report(record, json.dumps(report))
                self.assertInvalid(record)

    def replace_report(self, record, content):
        path = self.root / "performance.json"
        path.write_text(content, encoding="utf-8")
        for artifact in record["artifacts"]:
            if artifact["path"] == "performance.json":
                artifact["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    def test_arbitrary_text_or_malformed_json_is_not_a_performance_report(self):
        for content in ("Performance passed.", "{}", "[]", '{"version": 1, "version": 1}',
                        '{"measurements": NaN}'):
            with self.subTest(content=content):
                record = self.accepted()
                self.replace_report(record, content)
                self.assertInvalid(record)

    def test_malformed_inputs_report_errors_without_traceback(self):
        from tools.validate.evidence import validate
        for raw in (b"{", b"[]", b"null", b"\xff", b'{"version":1,"version":1}',
                    b'{"version": NaN}'):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                report = validate(self.path)
                self.assertFalse(report["valid"])
                self.assertTrue(report["errors"])
        self.assertFalse(validate(self.root / "missing.json")["valid"])
        self.assertFalse(validate(self.root)["valid"])

    def test_nested_bad_types_never_crash(self):
        for field in ("artifacts", "observations", "test_ids", "sources", "impacts", "performance"):
            for value in ([None], [True], [[], {}], {"unexpected": []}):
                with self.subTest(field=field, value=value):
                    record = self.accepted()
                    record[field] = value
                    self.assertInvalid(record)

    def test_cli_report_contract_and_exit_codes(self):
        self.validate()
        result = self.cli(str(self.path))
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(set(report), {"report_version", "path", "capability_id", "status", "valid", "errors"})
        self.assertEqual(report["report_version"], 1)
        self.assertEqual(report["capability_id"], "CAP-01")
        self.assertEqual(report["status"], "observed")
        self.assertEqual(report["path"], str(self.path.resolve()))
        self.assertEqual(result.stderr, "")
        self.path.write_text("{}", encoding="utf-8")
        result = self.cli(str(self.path))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        errors = json.loads(result.stdout)["errors"]
        self.assertTrue(all(set(e) == {"code", "field", "message"} for e in errors))
        self.assertEqual(errors, json.loads(self.cli(str(self.path)).stdout)["errors"])
        self.assertEqual(self.cli().returncode, 2)

    def test_cli_paths_resolve_against_manifest_not_working_directory(self):
        self.validate()
        result = self.cli(str(self.path), cwd="/")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_adversarial_capability_defaults_cannot_be_self_exempted(self):
        for capability in ("CAP-18", "CAP-21"):
            with self.subTest(capability=capability):
                record = self.accepted()
                record.update(capability_id=capability, requires_two_clients=False, impacts=[])
                self.assertInvalid(record, "two_clients", "client_count")

    def test_adversarial_test_ids_enforce_multiplayer_without_impact_labels(self):
        for test_id in ("AUD-001", "NET-005", "INT-006", "INT-007", "CRF-004", "AI-012", "HOR-006"):
            with self.subTest(test_id=test_id):
                record = self.accepted()
                record.update(test_ids=[test_id], requires_two_clients=False)
                record["observations"][0]["test_id"] = test_id
                self.assertInvalid(record, "two_clients", "client_count")
                record["client_count"] = 2
                self.assertTrue(self.validate(record)["valid"])

    def test_adversarial_T4_layer_cannot_claim_one_client(self):
        for status in ("observed", "prototyped", "accepted"):
            with self.subTest(status=status):
                record = self.accepted()
                record.update(status=status, layer="T4", requires_two_clients=False)
                self.assertInvalid(record, "two_clients", "client_count")

    def test_adversarial_diagnostic_only_run_cannot_be_accepted(self):
        record = self.accepted()
        record["layer"] = "T2"
        self.assertInvalid(record, "runtime_layer", "layer")
        record["status"] = "prototyped"
        self.assertTrue(self.validate(record)["valid"])

    def test_adversarial_hardlinked_comparison_runs_are_one_file(self):
        record = self.accepted()
        candidate = self.root / "runs/candidate.log"
        candidate.unlink()
        candidate.hardlink_to(self.root / "runs/baseline.log")
        self.assertInvalid(record, "duplicate", "artifacts[1].path")

    def test_adversarial_performance_parse_uses_the_verified_bytes(self):
        from tools.validate import evidence
        record = self.accepted()
        report_path = self.root / "performance.json"
        good_report = report_path.read_bytes()
        self.replace_report(record, "{}")
        original_table = evidence._Validator.artifact_table

        def replace_after_verification(checker, value, required):
            original_table(checker, value, required)
            report_path.write_bytes(good_report)

        with patch.object(evidence._Validator, "artifact_table", replace_after_verification):
            # The manifest hashes {}, so a later passing JSON document must not
            # replace the bytes actually verified by artifact_table.
            self.assertInvalid(record, "required", "performance.report.version")

    def test_adversarial_symlink_swap_between_resolve_and_read(self):
        candidate = self.root / "runs/candidate.log"
        with tempfile.TemporaryDirectory(prefix="synthetic-outside-race-") as outside:
            target = Path(outside) / "private.log"
            target.write_text("SYNTHETIC OUTSIDE EVIDENCE ROOT")
            self.record["artifacts"][1]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            original_open = Path.open

            def swap_at_open(path, *args, **kwargs):
                if path == candidate and args and args[0] == "rb":
                    path.unlink()
                    path.symlink_to(target)
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", swap_at_open):
                # The prior implementation checked resolve(), then followed a
                # newly installed symlink while hashing outside-root bytes.
                self.assertInvalid()

    def test_adversarial_symlinked_parent_swap_cannot_escape(self):
        candidate = self.root / "runs/candidate.log"
        with tempfile.TemporaryDirectory(prefix="synthetic-parent-race-") as outside:
            target = Path(outside) / "candidate.log"
            target.write_text("SYNTHETIC OUTSIDE DIRECTORY")
            self.record["artifacts"][1]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            original_open = Path.open

            def swap_at_open(path, *args, **kwargs):
                if path == candidate and args and args[0] == "rb":
                    (self.root / "runs").rename(self.root / "held-runs")
                    (self.root / "runs").symlink_to(outside, target_is_directory=True)
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", swap_at_open):
                self.assertInvalid()

    @unittest.skipUnless(os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"), "POSIX anchored IO probe")
    def test_descriptor_open_rejects_last_component_swap(self):
        candidate = self.root / "runs/candidate.log"
        original_open = os.open
        injected = []
        with tempfile.TemporaryDirectory(prefix="synthetic-descriptor-race-") as outside:
            target = Path(outside) / "outside.log"
            target.write_text("SYNTHETIC OUTSIDE TARGET")
            self.record["artifacts"][1]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()

            def swap_at_open(path, flags, *args, **kwargs):
                if path == "candidate.log" and kwargs.get("dir_fd") is not None:
                    candidate.unlink()
                    candidate.symlink_to(target)
                    injected.append(True)
                return original_open(path, flags, *args, **kwargs)

            supported = os.supports_dir_fd | {swap_at_open}
            with patch.object(os, "open", swap_at_open), patch.object(os, "supports_dir_fd", supported):
                self.assertInvalid(code="unsafe_path", field="artifacts[1].path")
            self.assertTrue(injected, "Attack must run at the actual descriptor open.")

    @unittest.skipUnless(os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"), "POSIX anchored IO probe")
    def test_descriptor_open_keeps_checked_parent_when_name_is_swapped(self):
        original_open = os.open
        injected = []
        with tempfile.TemporaryDirectory(prefix="synthetic-directory-descriptor-race-") as outside:
            target = Path(outside) / "candidate.log"
            target.write_text("SYNTHETIC OUTSIDE DIRECTORY TARGET")
            self.record["artifacts"][1]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()

            def swap_at_open(path, flags, *args, **kwargs):
                if path == "candidate.log" and kwargs.get("dir_fd") is not None:
                    (self.root / "runs").rename(self.root / "held-runs")
                    (self.root / "runs").symlink_to(outside, target_is_directory=True)
                    injected.append(True)
                return original_open(path, flags, *args, **kwargs)

            supported = os.supports_dir_fd | {swap_at_open}
            with patch.object(os, "open", swap_at_open), patch.object(os, "supports_dir_fd", supported):
                # Reads remain tied to the original held directory, so the
                # outside target's digest must fail instead of being accepted.
                self.assertInvalid(code="hash_mismatch", field="artifacts[1].sha256")
            self.assertTrue(injected, "Attack must run after the parent descriptor is acquired.")

    def test_portable_fallback_accepts_regular_files_and_rejects_symlinks(self):
        with patch.object(os, "supports_dir_fd", set()):
            self.assertTrue(self.validate()["valid"])
            original = self.root / "runs/candidate.log"
            alias = self.root / "runs/alias.log"
            alias.symlink_to(original)
            self.record["artifacts"][1]["path"] = "runs/alias.log"
            self.record["observations"][0]["artifacts"] = ["runs/alias.log"]
            self.assertInvalid(code="unsafe_path", field="artifacts[1].path")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO probe")
    def test_adversarial_manifest_fifo_fails_without_blocking(self):
        fifo = self.root / "manifest.fifo"
        os.mkfifo(fifo)
        result = self.cli(str(fifo), timeout=1)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["errors"][0]["code"], "input_io")
        self.assertEqual(result.stderr, "")

    @staticmethod
    def cli(*args, cwd=None, timeout=10):
        repo = Path(__file__).resolve().parents[2]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(repo))
        return subprocess.run([sys.executable, "-m", "tools.validate.evidence", *args],
                              cwd=cwd or repo, env=env, text=True, capture_output=True, check=False, timeout=timeout)


if __name__ == "__main__":
    unittest.main()
