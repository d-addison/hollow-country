"""Bounded observation helpers for the native adapters. Synthetic: they never observe DayZ.

Expectations derive from the helpers' own constants and from tree layouts the tests build.
"""
import os
from pathlib import Path
import tempfile
import unittest

from tests.unit.native_fakes import FakeHost
from tools.testing import native_common as common


class TempCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)


class LogFreshnessTests(TempCase):
    def write(self, name, text, mtime_ns=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if mtime_ns is not None:
            os.utime(path, ns=(mtime_ns, mtime_ns))
        return path

    def test_log_older_than_launch_is_rejected_by_name(self):
        self.write("script_old.log", "Module: Mission; loaded 1 files\n", mtime_ns=1_000)
        files, skipped = common.read_logs(self.root)
        texts, rejected = common.fresh_logs(files, {}, 2_000)
        self.assertEqual(texts, {})
        self.assertEqual(rejected, {"script_old.log": "stale_older_than_launch"})
        self.assertEqual(skipped, {})

    def test_only_bytes_after_the_baseline_count_and_a_rewrite_is_rejected(self):
        self.write("a.log", "old line\n", mtime_ns=1_000)
        baseline = common.logs_baseline(common.read_logs(self.root)[0])
        self.write("a.log", "old line\nnew line\n", mtime_ns=5_000)
        texts, rejected = common.fresh_logs(common.read_logs(self.root)[0], baseline, 2_000)
        self.assertEqual(texts, {"a.log": "new line\n"})
        self.assertEqual(rejected, {})
        self.write("a.log", "other\n", mtime_ns=6_000)
        texts, rejected = common.fresh_logs(common.read_logs(self.root)[0], baseline, 2_000)
        self.assertEqual(texts, {})
        self.assertEqual(rejected, {"a.log": "rewritten_since_baseline"})

    def test_non_log_files_are_ignored_and_oversized_logs_are_skipped_by_name(self):
        self.write("note.txt", "x")
        big = self.root / "big.log"
        with open(big, "wb") as stream:
            stream.truncate(common.MAX_LOG_FILE + 1)
        files, skipped = common.read_logs(self.root)
        self.assertEqual(files, {})
        self.assertIn("big.log", skipped)


class ProcessOwnershipTests(TempCase):
    def setUp(self):
        super().setUp()
        self.host = FakeHost(self.root)

    def test_descendants_follow_parent_links_not_names(self):
        self.host.process(10, 1, 10)
        self.host.process(11, 10, 10)
        self.host.process(12, 11, 12)
        self.host.process(99, 1, 99)
        table = common.scan(self.host.proc)
        self.assertEqual(sorted(common.descendants(table, 10)), [10, 11, 12])

    def test_a_reparented_group_member_stays_owned_through_the_group(self):
        self.host.process(10, 1, 10)
        self.host.process(11, 10, 11)
        ledger = common.Ledger(own_group=1)
        ledger.update(common.scan(self.host.proc), 10)
        self.host.kill(10)
        self.host.process(11, 1, 11)          # reparented to init after the launcher died
        survivors = ledger.survivors(common.scan(self.host.proc))
        self.assertEqual([item["pid"] for item in survivors], [11])

    def test_a_reused_pid_with_new_start_ticks_is_not_a_survivor(self):
        self.host.process(10, 1, 10, start=100)
        ledger = common.Ledger(own_group=1)
        ledger.update(common.scan(self.host.proc), 10)
        self.host.process(10, 1, 77, start=999)
        self.assertEqual(ledger.survivors(common.scan(self.host.proc)), [])

    def test_a_zombie_is_not_a_survivor(self):
        self.host.process(10, 1, 10)
        ledger = common.Ledger(own_group=1)
        ledger.update(common.scan(self.host.proc), 10)
        self.host.process(10, 1, 10, state="Z")
        self.assertEqual(ledger.survivors(common.scan(self.host.proc)), [])


class SocketClaimTests(TempCase):
    def setUp(self):
        super().setUp()
        self.host = FakeHost(self.root)
        self.host.process(10, 1, 10, sockets=(501,))

    def rows(self):
        return common.observe_sockets(self.host.proc, self.host.net, [10])

    def test_exact_loopback_bind_owned_by_the_child_is_a_claim(self):
        self.host.bind("127.0.0.1", 2402, 501)
        claim = common.claim_socket(self.rows(), "127.0.0.1", 2402)
        self.assertTrue(claim["claimed"])
        self.assertEqual(claim["reason"], "owned_exact_bind")

    def test_a_wildcard_bind_never_satisfies_a_loopback_claim(self):
        self.host.bind("0.0.0.0", 2402, 501)
        claim = common.claim_socket(self.rows(), "127.0.0.1", 2402)
        self.assertFalse(claim["claimed"])
        self.assertEqual(claim["reason"], "wildcard_not_a_claim")
        self.assertEqual(common.wildcard_owned(self.rows()), [("udp", 2402)])

    def test_claiming_the_wildcard_itself_is_refused(self):
        self.host.bind("0.0.0.0", 2402, 501)
        self.assertFalse(common.claim_socket(self.rows(), "0.0.0.0", 2402)["claimed"])

    def test_an_exact_bind_held_by_another_process_is_not_ours(self):
        self.host.bind("127.0.0.1", 2402, 999)
        claim = common.claim_socket(self.rows(), "127.0.0.1", 2402)
        self.assertEqual(claim["reason"], "port_held_by_other_process")

    def test_an_unbound_port_is_not_bound_and_a_free_port_is_free(self):
        self.assertEqual(common.claim_socket(self.rows(), "127.0.0.1", 2402)["reason"], "not_bound")
        self.assertTrue(common.port_free(self.rows(), "127.0.0.1", 2402))
        self.host.bind("0.0.0.0", 2402, 999)
        self.assertFalse(common.port_free(self.rows(), "127.0.0.1", 2402))


class ConfinementAndGuardTests(TempCase):
    def test_writes_stay_inside_staging_and_never_overwrite(self):
        staging = self.root / "stage"
        common.write_owned(staging, "a/b.bin", b"x")
        with self.assertRaises(FileExistsError):
            common.write_owned(staging, "a/b.bin", b"y")
        with self.assertRaises(ValueError):
            common.write_owned(staging, "../escape.bin", b"x")
        self.assertFalse((self.root / "escape.bin").exists())

    def test_a_symlink_component_is_refused(self):
        staging = self.root / "stage"
        staging.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        os.symlink(outside, staging / "link")
        with self.assertRaises(ValueError):
            common.write_owned(staging, "link/file.bin", b"x")
        self.assertEqual(list(outside.iterdir()), [])

    def test_guard_detects_a_content_change_an_added_file_and_a_removal(self):
        exe = self.root / "server.exe"
        exe.write_bytes(b"one")
        directory = self.root / "mission"
        directory.mkdir()
        (directory / "init.c").write_text("a")
        before = common.snapshot_guard({"exe": exe}, {"mission": directory})
        self.assertEqual(common.diff_guard(before, common.snapshot_guard({"exe": exe}, {"mission": directory})), [])
        exe.write_bytes(b"two")
        (directory / "extra.c").write_text("b")
        (directory / "init.c").unlink()
        changed = common.diff_guard(before, common.snapshot_guard({"exe": exe}, {"mission": directory}))
        self.assertEqual(changed, ["exe", "mission/extra.c", "mission/init.c"])

    def test_guard_refuses_a_directory_beyond_its_entry_bound(self):
        directory = self.root / "many"
        directory.mkdir()
        for index in range(common.MAX_GUARD_ENTRIES + 1):
            (directory / ("f%d" % index)).write_text("")
        with self.assertRaises(ValueError):
            common.snapshot_guard({}, {"many": directory})


if __name__ == "__main__":
    unittest.main()
