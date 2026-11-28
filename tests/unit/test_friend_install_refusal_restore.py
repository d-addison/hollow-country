"""Refusal/recovery restores synthetic missions; no server or network calls."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.package import hc_events as hc
from tools.setup import friend_install as fi


class RefusalRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.server = Path(self.temp.name)
        self.mission = self.server / 'mpmissions/test'
        self.mission.mkdir(parents=True)
        for name in hc.PATCHED:
            (self.mission / name).write_bytes(b'original ' + name.encode())
        (self.mission / 'empty').mkdir()
        self.output = io.StringIO()
        self.ctx = fi.Ctx(fi.build_parser().parse_args(['--apply', '--assume-stopped']), self.output, None)
        self.ctx.server = self.server
        fi.track_target(self.ctx, 'mpmissions/test', tree=True)
        self.before = fi.tree_inventory(self.mission)

    def install_events(self):
        # Exercise the real receipt/atomic writer with a small prevalidated candidate.
        before = {name: (self.mission / name).read_bytes() for name in hc.PATCHED}
        before[hc.GENERATED] = None
        files = {name: b'events ' + name.encode() for name in hc.TARGETS}
        with mock.patch.object(hc, 'validate', return_value=({}, None, None, {})), \
                mock.patch.object(hc, '_digest', return_value='a' * 64), \
                mock.patch.object(hc, 'plan', return_value=dict(before=before, files=files, source='a' * 64, report={})):
            hc.install(Path('unused'), self.mission)

    def test_unfingerprinted_events_then_refusal_restores_exactly(self):
        # Model a helper escaping the writer fingerprint after the mission backup.
        self.install_events()
        with self.assertRaises(fi.Refused):
            raise fi.Refused('overlay', 'later step refused')
        fi.rollback_run(self.ctx, self.ctx.backup_root, self.ctx.journal)
        self.assertEqual(fi.tree_inventory(self.mission), self.before)
        self.assertFalse((self.mission / hc.MANAGED).exists())

    def test_fingerprinted_events_then_refusal_restores_exactly(self):
        with self.assertRaises(fi.Refused):
            with fi.tree_writer(self.ctx, self.mission):
                self.install_events()
                raise fi.Refused('overlay', 'later step refused')
        fi.rollback_run(self.ctx, self.ctx.backup_root, self.ctx.journal)
        self.assertEqual(fi.tree_inventory(self.mission), self.before)

    def test_refused_upgrade_restores_existing_encounter_receipt_and_bytes(self):
        self.install_events()
        self.ctx = fi.Ctx(self.ctx.args, self.output, None)
        self.ctx.server = self.server
        fi.track_target(self.ctx, 'mpmissions/test', tree=True)
        before = fi.tree_inventory(self.mission)
        with self.assertRaises(fi.Refused):
            with fi.tree_writer(self.ctx, self.mission):
                hc.rollback(self.mission)
                with fi.tree_writer(self.ctx, self.mission):
                    (self.mission / 'new/nested').mkdir(parents=True)
                raise fi.Refused('overlay', 'stock drift')
        fi.rollback_run(self.ctx, self.ctx.backup_root, self.ctx.journal)
        self.assertEqual(fi.tree_inventory(self.mission), before)

    def test_recovery_restores_unfingerprinted_events(self):
        self.install_events()
        data = fi.read_journal(self.ctx, fi.journal_path(self.ctx.backup_root))
        fi.recover_runs(self.ctx, [(self.ctx.backup_root, data)])
        self.assertEqual(fi.tree_inventory(self.mission), self.before)
        self.assertIn('Recovered interrupted install; ' + fi.ROLLBACK_OK, self.output.getvalue())

    def test_restore_mismatch_lists_relative_paths_and_keeps_backup(self):
        with fi.tree_writer(self.ctx, self.mission):
            self.install_events()
        with mock.patch.object(fi, 'restore_change'):
            with self.assertRaises(fi.Refused) as caught:
                fi.recover_runs(self.ctx, [(self.ctx.backup_root, self.ctx.journal)])
        self.assertEqual(caught.exception.code, 'restore_mismatch')
        self.assertIn('mpmissions/test/cfgeconomycore.xml', str(caught.exception))
        self.assertIn('mpmissions/test/hollow-country-events', str(caught.exception))
        self.assertNotIn(str(self.server), str(caught.exception))
        self.assertNotIn(fi.ROLLBACK_OK, self.output.getvalue())
        self.assertTrue(self.ctx.backup_root.exists())
        self.assertEqual(self.ctx.journal['state'], 'rollback_pending')

    def test_main_never_claims_success_when_restore_leaves_differences(self):
        def refuse(ctx, apply):
            self.ctx = ctx
            with fi.tree_writer(ctx, self.mission):
                self.install_events()
                raise fi.Refused('overlay', 'later step refused')
        errors = io.StringIO()
        with mock.patch.object(fi, 'load_bundle', return_value={}), \
                mock.patch.object(fi, 'resolve_server', return_value=self.server), \
                mock.patch.object(fi, 'pending_runs', return_value=[]), \
                mock.patch.object(fi, 'load_run_receipt'), \
                mock.patch.object(fi, 'run_steps', side_effect=refuse), \
                mock.patch.object(fi, 'restore_change'), \
                contextlib.redirect_stderr(errors):
            result = fi.main(['--apply', '--assume-stopped'], out=self.output)
        self.assertEqual(result, 2)
        self.assertIn('restore_mismatch', errors.getvalue())
        self.assertNotIn(fi.ROLLBACK_OK, errors.getvalue())

    def test_hard_exit_recovery_stashes_and_restores_with_repair(self):
        row = self.ctx.journal['entries'][-1]
        row['writing'] = 1
        self.install_events()
        fi.recover_runs(self.ctx, [(self.ctx.backup_root, self.ctx.journal)], force=True)
        self.assertEqual(fi.tree_inventory(self.mission), self.before)
        stashes = list(self.ctx.backup_root.glob(fi.STASH_PREFIX + '*'))
        self.assertEqual(len(stashes), 1)
        self.assertTrue((stashes[0] / 'mpmissions/test' / hc.GENERATED).is_file())

    def test_completed_run_preview_retains_drift_checks(self):
        self.install_events()
        self.ctx.journal['state'] = 'complete'
        current = fi.tree_inventory(self.mission)
        with self.assertRaisesRegex(ValueError, 'changed after interrupted install'):
            fi.rollback_changes(self.ctx, self.ctx.backup_root, self.ctx.journal)
        self.assertEqual(fi.tree_inventory(self.mission), current)

    def test_missing_backup_refuses_before_mutating(self):
        self.install_events()
        (self.ctx.backup_root / 'mpmissions/test/cfgeconomycore.xml').unlink()
        current = fi.tree_inventory(self.mission)
        with self.assertRaisesRegex(ValueError, 'backup missing or changed'):
            fi.rollback_run(self.ctx, self.ctx.backup_root, self.ctx.journal)
        self.assertEqual(fi.tree_inventory(self.mission), current)

    def test_persistence_is_untouched(self):
        for folder in ('storage_1', 'profiles', 'saves'):
            path = self.mission / folder / 'state'
            path.parent.mkdir()
            path.write_bytes(b'keep')
        self.install_events()
        fi.rollback_run(self.ctx, self.ctx.backup_root, self.ctx.journal)
        for folder in ('storage_1', 'profiles', 'saves'):
            self.assertEqual((self.mission / folder / 'state').read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
