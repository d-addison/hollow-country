"""Synthetic stock-shaped missions; offline staging safety, never engine proof."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.setup import diagnostic_mission as dm


STOCK = (b"// SYNTHETIC mission, not purchased game source\r\n"
         b"void main() {}\r\nclass CustomMission: MissionServer {}\r\n"
         b"Mission CreateCustomMission(string path)\r\n{\r\n"
         b"    return new CustomMission();\r\n}\r\n")


class DiagnosticMissionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "stock/dayzOffline.chernarusplus"
        self.source.mkdir(parents=True)
        (self.source / "init.c").write_bytes(STOCK)
        (self.source / "db").mkdir()
        (self.source / "db/types.xml").write_bytes(b"<types>synthetic</types>\r\n")
        self.dest = self.root / "experiment/mpmissions/dayzOffline.chernarusplus"

    def prepare(self):
        return dm.prepare_diagnostic_mission(self.source, self.dest)

    def test_item_audit_has_a_fixed_normal_server_hook_and_separate_provenance(self):
        result = dm.prepare_diagnostic_mission(self.source, self.dest, purpose='item-audit')
        copied = (self.dest / 'init.c').read_bytes()
        self.assertIn(b'HCItemCompatibilityAudit.Export(', copied)
        self.assertIn(b'GetVersion(version)', copied)
        self.assertIn(b'GetWorldName(world)', copied)
        self.assertNotIn(b'#ifdef DIAG_DEVELOPER', copied)
        self.assertNotIn(b'RunStorageProbe', copied)
        self.assertEqual(result['kind'], 'disposable-item-compatibility-audit')
        self.assertIsNone(result['storage_probe_epoch'])
        self.assertEqual(result['hook_sha256'], hashlib.sha256(dm.ITEM_AUDIT_HOOK).hexdigest())
        self.assertEqual(result['runtime_acceptance'], 'pending')

    def test_unknown_diagnostic_purpose_fails_before_any_output(self):
        with self.assertRaises(ValueError):
            dm.prepare_diagnostic_mission(self.source, self.dest, purpose='arbitrary-script')
        self.assertFalse(self.dest.exists())

    def test_copy_preserves_stock_and_records_exact_exception_and_hashes(self):
        before = {p.relative_to(self.source).as_posix(): p.read_bytes()
                  for p in self.source.rglob("*") if p.is_file()}
        result = self.prepare()
        self.assertEqual(result["mission_path"], str(self.dest))
        self.assertEqual(result["storage_probe_epoch"], 900001)
        self.assertEqual(result["runtime_acceptance"], "pending")
        self.assertEqual(result["source_root"], str(self.source))
        self.assertEqual(result["files"]["init.c"]["source_sha256"], hashlib.sha256(STOCK).hexdigest())
        for name, blob in before.items():
            self.assertEqual((self.source / name).read_bytes(), blob)
            entry = result["files"][name]
            self.assertEqual(entry["source_sha256"], hashlib.sha256(blob).hexdigest())
            copied = (self.dest / name).read_bytes()
            self.assertEqual(entry["staged_sha256"], hashlib.sha256(copied).hexdigest())
            if name != "init.c":
                self.assertEqual(copied, blob)
        expected = STOCK.replace(b"new CustomMission()", b"new HCDisposableDiagnosticMission()") + dm.DIAGNOSTIC_HOOK
        self.assertEqual((self.dest / "init.c").read_bytes(), expected)
        marker = json.loads((self.dest / dm.MARKER_NAME).read_text())
        self.assertEqual(marker, result)
        self.assertEqual(set(p.relative_to(self.dest).as_posix() for p in self.dest.rglob("*") if p.is_file()), {*before, dm.MARKER_NAME})

    def test_hook_preserves_super_chain_and_explicit_server_diag_once_guard(self):
        hook = dm.DIAGNOSTIC_HOOK.decode("ascii")
        self.assertIn("class HCDisposableDiagnosticMission : CustomMission", hook)
        self.assertIn("override void OnInit()", hook)
        self.assertLess(hook.index("super.OnInit();"), hook.index("HCInfectedSelfTests.Run()"))
        self.assertLess(hook.index("#ifdef DIAG_DEVELOPER"), hook.index("HCInteriorSelfTests.RunStorageProbe(900001)"))
        self.assertIn("GetGame().IsServer()", hook)
        self.assertIn("m_HCDiagnosticExecuted", hook)
        self.assertIn("[HC Diagnostic Mission] BEGIN", hook)
        self.assertIn("[HC Diagnostic Mission] PASS", hook)
        self.assertIn("[HC Diagnostic Mission] FAIL", hook)
        for forbidden in ("CreateObject", "CreateInInventory", "HCServer.Get", "EnableInfected", "CallLater"):
            self.assertNotIn(forbidden, hook)

    def test_existing_destination_and_dangling_link_are_never_overwritten(self):
        self.dest.mkdir(parents=True)
        sentinel = self.dest / "sentinel"
        sentinel.write_bytes(b"preserve")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(sentinel.read_bytes(), b"preserve")
        other = self.root / "dangling"
        other.symlink_to(self.root / "absent", target_is_directory=True)
        with self.assertRaises(ValueError):
            dm.prepare_diagnostic_mission(self.source, other)
        self.assertTrue(other.is_symlink())

    def test_source_entry_symlink_rejected_before_destination_created(self):
        (self.source / "alias.xml").symlink_to(self.source / "db/types.xml")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.dest.exists())

    def test_source_root_and_ancestor_symlinks_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.source.parent, target_is_directory=True)
        for source in (alias / self.source.name, self.source / "db/.."):
            with self.subTest(source=source), self.assertRaises(ValueError):
                dm.prepare_diagnostic_mission(source, self.dest)
        self.assertFalse(self.dest.exists())

    def test_destination_ancestor_symlink_rejected(self):
        actual = self.root / "actual"
        actual.mkdir()
        alias = self.root / "linked"
        alias.symlink_to(actual, target_is_directory=True)
        with self.assertRaises(ValueError):
            dm.prepare_diagnostic_mission(self.source, alias / "newmission")
        self.assertEqual(list(actual.iterdir()), [])

    def test_overlap_steam_and_checkout_paths_rejected(self):
        checkout = Path(dm.__file__).absolute().parents[2]
        paths = (self.source / "nested", self.source.parent,
                 self.root / "steamapps/common/experiment", checkout / "local-mission")
        for dest in paths:
            with self.subTest(dest=dest), self.assertRaises(ValueError):
                dm.prepare_diagnostic_mission(self.source, dest)
        steam = self.root / "steamapps/common/stock"
        steam.mkdir(parents=True)
        (steam / "init.c").write_bytes(STOCK)
        with self.assertRaises(ValueError):
            dm.prepare_diagnostic_mission(steam, self.dest)

    def test_missing_or_nonstock_factory_rejected_without_output(self):
        for blob in (b"", STOCK.replace(b"CustomMission: MissionServer", b"CustomMission: Unknown"),
                     STOCK.replace(b"return new CustomMission();", b"return null;"),
                     STOCK + b"\nMission CreateCustomMission(string path) { return new CustomMission(); }"):
            with self.subTest(blob=blob):
                (self.source / "init.c").write_bytes(blob)
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertFalse(self.dest.exists())

    def test_previously_instrumented_source_rejected(self):
        (self.source / dm.MARKER_NAME).write_text("{}")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.dest.exists())

    def test_entry_byte_depth_and_init_budgets_fail_before_copy(self):
        for constant, limit in (("MAX_ENTRIES", 2), ("MAX_FILE_BYTES", 16),
                                ("MAX_TOTAL_BYTES", len(STOCK)), ("MAX_INIT_BYTES", 16),
                                ("MAX_DEPTH", 0)):
            with self.subTest(constant=constant), patch.object(dm, constant, limit):
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertFalse(self.dest.exists())

    def test_special_file_rejected_without_reading(self):
        import os
        os.mkfifo(self.source / "named-pipe")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.dest.exists())

    def test_empty_directories_preserved(self):
        (self.source / "empty").mkdir()
        self.prepare()
        self.assertTrue((self.dest / "empty").is_dir())

    def test_copy_uses_exclusive_creation_and_preserves_partial_output_on_failure(self):
        native = Path.open
        def fail_open(path, mode="r", *args, **kwargs):
            if path == self.dest / "init.c" and "x" in mode:
                raise OSError("synthetic copy failure")
            return native(path, mode, *args, **kwargs)
        with patch.object(Path, "open", fail_open), self.assertRaises(OSError):
            self.prepare()
        self.assertTrue(self.dest.is_dir())
        self.assertFalse((self.dest / dm.MARKER_NAME).exists())
        with self.assertRaises(ValueError):
            self.prepare()
