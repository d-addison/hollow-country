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
        self.assertIn(b'HCItemCompatibilityAudit.ExportAll(', copied)
        self.assertIn(b'GetVersion(version)', copied)
        self.assertIn(b'GetWorldName(world)', copied)
        self.assertNotIn(b'#ifdef DIAG_DEVELOPER', copied)
        self.assertNotIn(b'RunStorageProbe', copied)
        self.assertEqual(result['kind'], 'disposable-item-compatibility-audit')
        self.assertIsNone(result['storage_probe_epoch'])
        self.assertEqual(result['hook_sha256'], hashlib.sha256(dm.ITEM_AUDIT_HOOK).hexdigest())
        self.assertEqual(result['runtime_acceptance'], 'pending')

    def test_group_checks_hook_is_fixed_and_has_no_gameplay_side_effects(self):
        result = dm.prepare_diagnostic_mission(self.source, self.dest, purpose='group-checks')
        copied = (self.dest / 'init.c').read_bytes()
        self.assertIn(b'HCGroupNativeChecks.Run(error)', copied)
        self.assertIn(b'[HC Group Checks] BEGIN; synthetic policy fixtures only', copied)
        self.assertIn(b'[HC Group Checks] result=', copied)
        for forbidden in (b'CreateObject', b'RunStorageProbe', b'EnableGroups',
                          b'HCItemCompatibilityAudit', b'#ifdef DIAG_DEVELOPER'):
            self.assertNotIn(forbidden, copied)
        self.assertEqual(result['kind'], 'disposable-group-policy-checks')
        self.assertIsNone(result['storage_probe_epoch'])
        self.assertEqual(result['hook_sha256'], hashlib.sha256(dm.GROUP_CHECKS_HOOK).hexdigest())
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

    def test_anchored_primitives_never_follow_a_link_at_the_leaf_or_in_any_directory(self):
        import os
        import stat
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "target.xml").write_bytes(b"<types>synthetic</types>\r\n")
        leaf = self.source / "db/leaf-link.xml"
        leaf.symlink_to(outside / "target.xml")
        linked_dir = self.source / "dir-link"
        linked_dir.symlink_to(outside, target_is_directory=True)
        for label, call in (
                ("leaf open", lambda: dm.open_file_at(leaf, os.O_RDONLY)),
                ("leaf re-read", lambda: dm._reread_digest(leaf)),
                ("directory open", lambda: dm.open_dir_at(linked_dir)),
                ("file below a linked directory", lambda: dm.open_file_at(linked_dir / "target.xml", os.O_RDONLY)),
                ("exclusive create below a linked directory", lambda: dm.create_exclusive(linked_dir / "new.xml", b"x")),
                ("mkdir below a linked directory", lambda: dm.mkdir_at(linked_dir / "sub"))):
            with self.subTest(label), self.assertRaises(ValueError):
                call()
        self.assertEqual({"target.xml"}, {p.name for p in outside.iterdir()})
        self.assertTrue(stat.S_ISLNK(dm.lstat_at(leaf).st_mode))      # lstat describes the link, never its target

    def test_walk_plain_lists_regular_files_and_refuses_links_and_special_files(self):
        import os
        listed = dm.walk_plain(self.source)
        self.assertEqual({"init.c": len(STOCK), "db/types.xml": 26}, listed)
        link = self.source / "db/alias.xml"
        link.symlink_to(self.source / "db/types.xml")
        with self.assertRaises(ValueError):
            dm.walk_plain(self.source)
        link.unlink()
        os.mkfifo(self.source / "pipe")
        with self.assertRaises(ValueError):
            dm.walk_plain(self.source)

    def test_walk_plain_refuses_a_directory_that_stopped_occupying_its_name_after_it_was_opened(self):
        """Sol review 003 P2: a retained descriptor of a moved directory must not certify the tree."""
        import os
        real_child = dm._open_child_dir
        cases = {
            "a symlink under the old name": lambda path, moved: os.symlink(moved, path, target_is_directory=True),
            "another directory under the old name": lambda path, moved: path.mkdir(),
            "nothing under the old name": lambda path, moved: None,
        }
        for label, replace in cases.items():
            with self.subTest(label):
                moved = self.root / ("moved-" + label.split()[0] + "-" + str(len(label)))
                fired = []

                def child(descriptor, name):
                    opened = real_child(descriptor, name)
                    if name == "db" and not fired:
                        fired.append(name)
                        (self.source / "db").rename(moved)
                        replace(self.source / "db", moved)
                    return opened
                try:
                    with patch.object(dm, "_open_child_dir", child), self.assertRaises(ValueError):
                        dm.walk_plain(self.source)
                    self.assertEqual(["db"], fired)
                finally:
                    link = self.source / "db"
                    if link.is_symlink():
                        link.unlink()
                    elif link.is_dir():
                        link.rmdir()
                    moved.rename(link)
        self.assertEqual({"init.c": len(STOCK), "db/types.xml": 26}, dm.walk_plain(self.source))      # untouched tree

    def test_walk_plain_checks_the_root_identity_even_when_the_tree_has_no_subdirectory(self):
        flat = self.root / "flat"
        flat.mkdir()
        (flat / "only.xml").write_bytes(b"<a/>")
        real_child, moved, fired = dm._open_child_dir, self.root / "flat-moved", []

        def child(descriptor, name):
            opened = real_child(descriptor, name)
            if name == "flat" and not fired:
                fired.append(name)
                flat.rename(moved)
                flat.mkdir()                              # a different directory now occupies the name
                (flat / "only.xml").write_bytes(b"<a/>")      # with the same listing
            return opened
        with patch.object(dm, "_open_child_dir", child), self.assertRaises(ValueError):
            dm.walk_plain(flat)
        self.assertEqual(["flat"], fired)

    def test_walk_plain_accepts_an_undisturbed_nested_tree(self):
        (self.source / "db/deeper").mkdir()
        (self.source / "db/deeper/a.xml").write_bytes(b"<a/>")
        self.assertEqual({"init.c": len(STOCK), "db/types.xml": 26, "db/deeper/a.xml": 4}, dm.walk_plain(self.source))

    def test_copy_uses_exclusive_creation_and_preserves_partial_output_on_failure(self):
        native = dm._create_staged     # creation is anchored on directory descriptors (O_EXCL), not Path.open
        def fail_create(path, data):
            if path == self.dest / "init.c":
                raise OSError("synthetic copy failure")
            return native(path, data)
        with patch.object(dm, "_create_staged", fail_create), self.assertRaises(OSError):
            self.prepare()
        self.assertTrue(self.dest.is_dir())
        self.assertFalse((self.dest / dm.MARKER_NAME).exists())
        with self.assertRaises(ValueError):
            self.prepare()
