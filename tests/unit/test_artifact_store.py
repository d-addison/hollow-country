"""Artifact store and strict evidence bridge tests (spec 002 AV-T006).

All inputs are synthetic T0 data; they never establish DayZ behaviour. Expectations derive from
the store constants, the evidence validator codes and the driver registry.
"""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

from tools.testing import artifacts, automation, discovery, drivers
from tools.validate import evidence

ROOT = Path(__file__).resolve().parents[2]
SECRET = "hunter2-synthetic-value"
PEM_BODY = "QUJDREVGR0hJSktMTU5PUA"
PEM = "-----" + "BEGIN " + "RSA PRIVATE KEY" + "-----\n" + PEM_BODY + "\n-----" + "END " + "RSA PRIVATE KEY" + "-----\n"
DRIVER = drivers.Driver("t.offline", "offline", "synthetic", (), lambda root, inputs: ["x"], drivers.judge_exit)
PINS = artifacts.pins_for({DRIVER.id: DRIVER})


def codes(report):
    return {error["code"] for error in report["errors"]}


def record_json(log, *, status="documented", clients=None, text="synthetic observation", extra=None):
    data = {"version": 1, "capability_id": automation.FRAMEWORK_CAPABILITY, "status": status,
            "method": "synthetic method", "observation": text,
            "artifacts": [{"path": log["path"].rsplit("/", 1)[1], "sha256": log["sha256"]}]}
    if status == "documented":
        pass
    else:
        data.update(game_build="synthetic-build", layer="T3", client_count=clients, test_ids=["CE-001"],
                    observations=[{"test_id": "CE-001", "text": text,
                                   "artifacts": [log["path"].rsplit("/", 1)[1]]}])
    data.update(extra or {})
    return json.dumps(data, sort_keys=True) + "\n"


class StoreCase(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.dir = Path(scratch.name)
        self.store = artifacts.ArtifactStore(self.dir / "evidence", "synthetic")

    def attempt(self, task="t1", *, outcome="PASS", role="driver_log", actor="offline",
                presented="offline_framework", clients=0, status="documented", record_clients=None,
                text="synthetic observation", log=b"synthetic output\n", record_roles=None, finish=True):
        item = self.store.begin(task, DRIVER.id, actor=actor, presented_as=presented,
                                client_count=clients, pin=PINS[DRIVER.id])
        item.add("driver.log", log, role)
        item.add("record.json", record_json(item.artifacts[0], status=status, clients=record_clients, text=text),
                 "evidence_record")
        if finish:
            item.finish(outcome, "synthetic")
        return item

    def real_client_attempt(self, **kwargs):
        item = self.store.begin("rc", DRIVER.id, actor="real_client", presented_as="real_client",
                                client_count=kwargs.pop("clients", 1), pin=PINS[DRIVER.id])
        item.add("client.log", b"synthetic client output\n", "runtime_client_log")
        log = item.artifacts[0]
        item.add("record.json", record_json(log, status="observed", clients=kwargs.pop("record_clients", 1), **kwargs),
                 "evidence_record")
        item.finish("PASS", "synthetic")
        return item

    def check(self, **kwargs):
        return self.store.validate(PINS, **kwargs)

    def file(self, entry_path):
        return self.store.root / entry_path


class SnapshotTests(StoreCase):
    def test_clean_store_validates_and_snapshots_are_immutable_role_hash_pairs(self):
        item = self.attempt()
        report = self.check(expected_tasks=["t1"])
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["valid"])
        manifest = json.loads((self.store.root / evidence.STORE_MANIFEST).read_text())
        entry = manifest["attempts"][0]
        self.assertEqual((entry["driver"], entry["method_pin"]), (DRIVER.id, PINS[DRIVER.id]))
        for stored in entry["artifacts"]:
            self.assertIn(stored["role"], evidence.STORE_ROLES)
            self.assertEqual(len(stored["sha256"]), 64)
            self.assertFalse(self.file(stored["path"]).stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            with self.assertRaises(FileExistsError):
                os.open(self.file(stored["path"]), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        self.assertEqual(manifest["acceptance"], "not_evaluated")
        self.assertNotIn("multiplayer", manifest["evidence_label"])
        self.assertEqual(item.number, 1)

    def test_root_must_be_fresh_and_the_manifest_is_written_atomically(self):
        with self.assertRaises(ValueError):
            artifacts.ArtifactStore(self.store.root, "again")
        link = self.dir / "link"
        link.symlink_to(self.dir)
        with self.assertRaises(ValueError):
            artifacts.ArtifactStore(link, "linked")
        self.attempt()
        before = (self.store.root / evidence.STORE_MANIFEST).read_bytes()
        with mock.patch.object(artifacts.os, "replace", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                self.store.flush()
        self.assertEqual((self.store.root / evidence.STORE_MANIFEST).read_bytes(), before)
        self.store.flush()
        self.assertFalse((self.store.root / (evidence.STORE_MANIFEST + ".tmp")).exists())

    def test_an_empty_artifact_cannot_be_snapshotted_and_a_name_cannot_be_reused(self):
        item = self.store.begin("t1", DRIVER.id, actor="offline", presented_as="offline_framework",
                                client_count=0, pin=PINS[DRIVER.id])
        with self.assertRaises(ValueError):
            item.add("empty.log", b"", "driver_log")
        item.add("a.log", b"x", "driver_log")
        with self.assertRaises(ValueError):
            item.add("a.log", b"y", "driver_log")
        with self.assertRaises(ValueError):
            item.add("b.log", b"y", "no_such_role")


class RedTests(StoreCase):
    def entry_path(self, name, index=0):
        manifest = json.loads((self.store.root / evidence.STORE_MANIFEST).read_text())
        return next(item["path"] for item in manifest["attempts"][index]["artifacts"] if item["path"].endswith(name))

    def test_missing_tampered_and_emptied_artifacts_fail(self):
        self.attempt()
        log = self.file(self.entry_path("driver.log"))
        log.chmod(0o644)
        log.write_bytes(b"tampered")
        self.assertIn("hash_mismatch", codes(self.check()))
        log.write_bytes(b"")
        self.assertIn("empty_artifact", codes(self.check()))
        log.unlink()
        self.assertIn("artifact_missing", codes(self.check()))

    def test_unlisted_and_symlinked_files_fail(self):
        self.attempt()
        (self.store.root / "attempts/extra.log").write_bytes(b"x")
        self.assertIn("unlisted_artifact", codes(self.check()))
        (self.store.root / "attempts/link").symlink_to(self.dir)
        self.assertIn("unsafe_path", codes(self.check()))

    def test_same_bytes_under_two_roles_or_a_hard_link_are_aliases(self):
        item = self.store.begin("t1", DRIVER.id, actor="offline", presented_as="offline_framework",
                                client_count=0, pin=PINS[DRIVER.id])
        item.add("one.log", b"same bytes\n", "driver_log")
        item.add("two.log", b"same bytes\n", "server_log")
        item.add("record.json", record_json(item.artifacts[0]), "evidence_record")
        item.finish("PASS", "synthetic")
        self.assertIn("aliased_artifact", codes(self.check()))

        other = artifacts.ArtifactStore(self.dir / "second", "synthetic")
        item = other.begin("t1", DRIVER.id, actor="offline", presented_as="offline_framework",
                           client_count=0, pin=PINS[DRIVER.id])
        item.add("one.log", b"first\n", "driver_log")
        item.add("two.log", b"first\n", "driver_log")
        item.add("record.json", record_json(item.artifacts[0]), "evidence_record")
        item.finish("PASS", "synthetic")
        self.assertNotIn("aliased_artifact", codes(other.validate(PINS)))
        two = other.root / item.dir / "two.log"
        two.unlink()
        os.link(other.root / item.dir / "one.log", two)
        self.assertIn("aliased_artifact", codes(other.validate(PINS)))

    def test_stale_or_unknown_method_pin_fails(self):
        self.attempt()
        self.assertIn("stale_pin", codes(self.store.validate({DRIVER.id: "0" * 64})))
        self.assertIn("unknown_producer", codes(self.store.validate({})))
        changed = drivers.Driver(DRIVER.id, "offline", "synthetic", (), lambda root, inputs: ["y"], drivers.judge_hygiene)
        self.assertNotEqual(artifacts.method_pin(changed), PINS[DRIVER.id])
        self.assertIn("stale_pin", codes(self.store.validate(artifacts.pins_for({DRIVER.id: changed}))))

    def test_a_retry_gets_a_new_attempt_directory_and_an_overwritten_failure_fails(self):
        first = self.attempt(outcome="FAIL")
        before = self.file(first.dir + "/driver.log").read_bytes()
        second = self.attempt(outcome="PASS")
        self.assertNotEqual(first.dir, second.dir)
        self.assertEqual((first.number, second.number), (1, 2))
        self.assertEqual(self.file(first.dir + "/driver.log").read_bytes(), before)
        self.assertEqual(self.check(expected_tasks=["t1"])["errors"], [])
        # Replacing the failed attempt with a clean one, then re-sealing the manifest, breaks the chain.
        manifest_path = self.store.root / evidence.STORE_MANIFEST
        manifest = json.loads(manifest_path.read_text())
        dropped = manifest["attempts"].pop(0)
        manifest_path.write_text(json.dumps(manifest))
        self.assertIn("retry_overwritten", codes(self.store.validate(PINS)))
        for stored in dropped["artifacts"]:
            self.assertTrue(self.file(stored["path"]).exists())
        self.assertIn("unlisted_artifact", codes(self.store.validate(PINS)))

    def test_attempt_entries_cannot_be_edited_after_the_fact(self):
        self.attempt(outcome="FAIL")
        manifest_path = self.store.root / evidence.STORE_MANIFEST
        manifest = json.loads(manifest_path.read_text())
        manifest["attempts"][0]["outcome"] = "PASS"
        manifest_path.write_text(json.dumps(manifest))
        self.assertIn("store_manifest", codes(self.store.validate(PINS)))
        self.assertIn("hash_mismatch", codes(evidence.validate_store(self.store.root, pins=PINS, manifest_sha256="0" * 64)))
        self.assertIn("hash_mismatch", codes(self.store.validate(PINS)))  # the store remembers what it sealed

    def test_missing_expected_task_and_an_open_attempt_fail(self):
        self.attempt()
        self.assertIn("task_missing", codes(self.check(expected_tasks=["t1", "never-ran"])))
        self.attempt("t2", finish=False)
        self.assertIn("unlisted_artifact", codes(self.check()))


class ActorTests(StoreCase):
    def test_bot_diagnostic_or_zero_client_actor_cannot_be_presented_as_a_real_client(self):
        for actor in ("bot", "diagnostic", "server", "offline"):
            with self.subTest(actor=actor):
                other = artifacts.ArtifactStore(self.dir / ("s-" + actor), "synthetic")
                item = other.begin("rc", DRIVER.id, actor=actor, presented_as="real_client",
                                   client_count=1, pin=PINS[DRIVER.id])
                item.add("client.log", b"synthetic\n", "runtime_client_log")
                item.add("record.json", record_json(item.artifacts[0], status="observed", clients=1), "evidence_record")
                item.finish("PASS", "synthetic")
                report = other.validate(PINS)
                self.assertIn("actor_mismatch", codes(report))
                self.assertFalse(report["valid"])

    def test_zero_client_native_run_can_never_become_runtime_or_accepted_evidence(self):
        for status, expected in (("observed", "actor_mismatch"), ("accepted", "zero_client_accepted")):
            with self.subTest(status=status):
                other = artifacts.ArtifactStore(self.dir / ("z-" + status), "synthetic")
                item = other.begin("n1", DRIVER.id, actor="server", presented_as="zero_client_native",
                                   client_count=0, pin=PINS[DRIVER.id])
                item.add("driver.log", b"synthetic native output\n", "zero_client_report")
                item.add("record.json", record_json(item.artifacts[0], status=status, clients=1), "evidence_record")
                item.finish("PASS", "synthetic")
                self.assertIn(expected, codes(other.validate(PINS)))

    def test_a_real_client_runtime_record_is_valid_and_raw_zero_client_reports_stay_separate(self):
        self.real_client_attempt()
        self.assertEqual(self.check()["errors"], [])
        other = artifacts.ArtifactStore(self.dir / "mixed", "synthetic")
        item = other.begin("rc", DRIVER.id, actor="real_client", presented_as="real_client",
                           client_count=1, pin=PINS[DRIVER.id])
        item.add("client.log", b"synthetic client\n", "runtime_client_log")
        item.add("raw.log", b"synthetic raw zero-client report\n", "zero_client_report")
        record = json.loads(record_json(item.artifacts[0], status="observed", clients=1))
        record["artifacts"].append({"path": "raw.log", "sha256": item.artifacts[1]["sha256"]})
        record["observations"][0]["artifacts"].append("raw.log")
        item.add("record.json", json.dumps(record), "evidence_record")
        item.finish("PASS", "synthetic")
        self.assertIn("raw_zero_client_in_runtime", codes(other.validate(PINS)))

    def test_only_a_real_client_attempt_may_hold_runtime_client_logs(self):
        self.attempt(role="runtime_client_log")
        self.assertIn("actor_mismatch", codes(self.check()))

    def test_a_record_cannot_claim_more_clients_than_the_attempt_observed(self):
        self.real_client_attempt(record_clients=2)
        self.assertIn("two_clients", codes(self.check()))

    def test_autotest_evidence_never_claims_multiplayer(self):
        self.attempt(text="synthetic multiplayer result")
        self.assertIn("multiplayer_claim", codes(self.check()))
        other = artifacts.ArtifactStore(self.dir / "negated", "synthetic")
        item = other.begin("t1", DRIVER.id, actor="offline", presented_as="offline_framework",
                           client_count=0, pin=PINS[DRIVER.id])
        item.add("driver.log", b"x\n", "driver_log")
        item.add("record.json", record_json(item.artifacts[0], text="supports a test (never multiplayer)"), "evidence_record")
        item.finish("PASS", "synthetic")
        self.assertEqual(other.validate(PINS)["errors"], [])


class CredentialTests(StoreCase):
    def test_text_artifacts_are_redacted_and_the_material_is_never_stored_or_printed(self):
        text = f"start\npassword={SECRET}\n{PEM}token: {SECRET}\nkey at /x/server.biprivatekey\nend\n"
        item = self.attempt(log=text.encode())
        stored = item.artifacts[0]
        data = self.file(stored["path"]).read_text()
        for material in (SECRET, PEM_BODY, "server.biprivatekey"):
            self.assertNotIn(material, data)
        self.assertEqual(stored["redactions"], ["biprivatekey", "password", "private_key"])
        self.assertIn("start", data)
        self.assertEqual(self.check()["errors"], [])
        self.assertNotIn(SECRET, (self.store.root / evidence.STORE_MANIFEST).read_text())

    def test_binary_or_key_file_artifacts_are_refused_without_echoing_them(self):
        item = self.store.begin("t1", DRIVER.id, actor="offline", presented_as="offline_framework",
                                client_count=0, pin=PINS[DRIVER.id])
        with self.assertRaises(artifacts.CredentialRefused) as caught:
            item.add("blob.bin", b"\xff\xfe" + PEM.encode(), "driver_log")
        self.assertNotIn(PEM_BODY, str(caught.exception))
        self.assertIn("private_key", str(caught.exception))
        with self.assertRaises(ValueError):
            item.add("server.biprivatekey", b"x", "driver_log")
        self.assertEqual(item.artifacts, [])

    def test_credential_material_smuggled_into_a_stored_file_is_reported_without_printing_it(self):
        self.attempt()
        manifest = json.loads((self.store.root / evidence.STORE_MANIFEST).read_text())
        log = self.file(manifest["attempts"][0]["artifacts"][0]["path"])
        log.chmod(0o644)
        log.write_text(f"password={SECRET}\n")
        report = self.check()
        self.assertIn("credential_material", codes(report))
        self.assertNotIn(SECRET, json.dumps(report))


class BridgeTests(StoreCase):
    def test_validate_contract_is_preserved_and_strict_adds_rules_without_changing_the_shape(self):
        item = self.attempt()
        record = self.file(item.dir + "/record.json")
        plain = evidence.validate(record)
        strict = evidence.validate_strict(record, store_root=self.store.root, pins=PINS,
                                          expected_tasks=["t1"])
        self.assertEqual(set(plain), set(strict))
        self.assertEqual((plain["valid"], strict["valid"]), (True, True))
        for error in strict["errors"]:
            self.assertEqual(set(error), {"code", "field", "message"})
        stale = evidence.validate_strict(record, store_root=self.store.root, pins={DRIVER.id: "0" * 64})
        self.assertFalse(stale["valid"])
        self.assertTrue(evidence.validate(record)["valid"])  # the original contract is untouched

    def test_strict_rejects_a_record_outside_the_manifest_and_a_missing_manifest(self):
        self.attempt()
        stray = self.dir / "stray.json"
        stray.write_text(record_json({"path": "attempts/x/y.log", "sha256": "0" * 64}))
        self.assertIn("store_manifest", codes(evidence.validate_strict(stray, store_root=self.store.root, pins=PINS)))
        (self.store.root / evidence.STORE_MANIFEST).unlink()
        self.assertIn("store_manifest", codes(self.store.validate(PINS)))


class RunnerWiringTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.dir = Path(scratch.name)
        self.registry = {d.id: d for d in (
            drivers.Driver("t.pass", "offline", "synthetic", (), lambda root, inputs: [sys.executable, "-c", "print('ok')"],
                           drivers.judge_exit, timeout=30),
            drivers.Driver("t.native", "native", "synthetic", (), lambda root, inputs: [sys.executable, "-c", "print('n')"],
                           drivers.judge_exit, timeout=30),
        )}
        self.capabilities = {name: "available" for name in discovery.capability_names(ROOT)}

    def run_it(self, name="out", **kwargs):
        manifest = {"schema_version": 1, "run_id": "synthetic",
                    "tasks": [{"id": "p", "driver": "t.pass"}, {"id": "n", "driver": "t.native"}]}
        return automation.run_automation(manifest, self.dir / name, registry=self.registry,
                                         capabilities=self.capabilities, trusted_drivers=["t.native"], **kwargs)

    def test_a_run_with_a_valid_manifest_is_complete_and_every_record_passes_strict_validation(self):
        report = self.run_it()
        out = self.dir / "out"
        self.assertTrue(report["complete"])
        self.assertTrue(report["store"]["valid"], report["store"])
        self.assertNotEqual(report["status"], "INCOMPLETE")
        pins = artifacts.pins_for(self.registry)
        pins[automation.DEFERRED_DRIVER] = artifacts.text_pin(automation.DEFERRED_DRIVER + automation.DEFERRED_REASON)
        manifest = json.loads((out / "evidence" / evidence.STORE_MANIFEST).read_text())
        self.assertEqual({a["task"] for a in manifest["attempts"]}, {"p", "n", *automation.DEFERRED_TASKS})
        for task in report["tasks"]:
            strict = evidence.validate_strict(out / task["evidence"]["path"], store_root=out / "evidence",
                                              pins=pins, manifest_sha256=report["store"]["sha256"])
            self.assertTrue(strict["valid"], strict["errors"])
        roles = {a["task"]: {item["role"] for item in a["artifacts"]} for a in manifest["attempts"]}
        self.assertIn("zero_client_report", roles["n"])
        self.assertNotIn("zero_client_report", roles["p"])
        for entry in manifest["attempts"]:
            self.assertEqual((entry["client_count"], entry["presented_as"] == "real_client"), (0, False))

    def test_a_run_without_a_valid_manifest_is_incomplete_not_passed(self):
        bad = {"report_version": 1, "path": "x", "capability_id": None, "status": None, "valid": False,
               "errors": [{"code": "store_manifest", "field": "$", "message": "synthetic"}]}
        with mock.patch.object(automation.evidence, "validate_store", return_value=bad):
            report = self.run_it("bad")
        self.assertFalse(report["complete"])
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["store"]["errors"], ["store_manifest:$"])

    def test_the_runner_never_labels_evidence_as_real_client_or_multiplayer(self):
        report = self.run_it()
        manifest = json.loads((self.dir / "out/evidence" / evidence.STORE_MANIFEST).read_text())
        self.assertEqual(report["evidence_label"], manifest["evidence_label"])
        self.assertNotIn("real_client", {entry["actor"] for entry in manifest["attempts"]})
        for entry in manifest["attempts"]:
            self.assertIn((entry["actor"], entry["presented_as"]),
                          {("offline", "offline_framework"), ("server", "zero_client_native"),
                           ("diagnostic", "zero_client_native")})


if __name__ == "__main__":
    unittest.main()
