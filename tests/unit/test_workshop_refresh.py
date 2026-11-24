"""Receipt-owned dependency refreshes: synthetic bytes only; never starts Steam or DayZ."""
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools.setup import friend_install as fi
from tools.setup import workshop_sync as ws


def put(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


class RefreshTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / 'server'
        self.root.mkdir()
        self.content = self.base / 'steamapps/workshop/content/221100'
        self.item = dict(folder='@CF', id='1559212036', name='synthetic')
        self.source = self.content / self.item['id']
        for rel, data in [('addons/a.pbo', b'old pbo'), ('addons/a.pbo.key.bisign', b'old sig'),
                          ('keys/key.bikey', b'old key'), ('meta.cpp', 'timestamp = 10;')]:
            put(self.source, rel, data)
        targets, _, _ = ws.plan_install([self.item], [self.content], self.root)
        rows = {}
        for rel, (item, digest, src) in targets.items():
            put(self.root, rel, src.read_bytes())
            rows[rel] = dict(path=rel, sha256=digest, size=src.stat().st_size, item=item['id'])
        self.receipt = ws.receipt_data(rows, {'@CF', '@CF/addons', '@CF/keys', 'keys'})
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, self.receipt)
        args = fi.build_parser().parse_args(['--bundle', str(self.base / 'bundle'), '--assume-stopped'])
        self.ctx = fi.Ctx(args, io.StringIO(), None)
        self.ctx.server = self.root
        self.ctx.receipt = {'schema': 1, 'files': {}, 'overlay': None}

    def plan(self, **kwargs):
        return ws.plan_refresh(self.item, [self.content], self.root, self.load(), **kwargs)

    def load(self):
        return ws.load_receipt(self.root, {'@CF', '@Other'})

    def update(self):
        put(self.source, 'addons/a.pbo', b'new pbo')
        put(self.source, 'meta.cpp', 'timestamp = 20;')

    def apply(self, plan=None, repair=False):
        return ws.apply_refresh(self.root, self.load(), [plan or self.plan()],
                                lambda rel, digest: fi.record_written(self.ctx, rel, digest), repair)

    def test_stale_update_and_second_apply_noop(self):
        self.update()
        p = self.plan()
        self.assertEqual(p['state'], 'stale')
        with mock.patch.object(ws, 'write_json_atomic', wraps=ws.write_json_atomic) as write:
            self.apply(p)
            self.assertEqual(sum(call.args[0] == self.root / ws.RECEIPT_NAME for call in write.call_args_list), 1)
        self.assertEqual((self.root / '@CF/addons/a.pbo').read_bytes(), b'new pbo')
        self.assertEqual(self.plan()['state'], 'current')
        self.assertFalse(self.apply())

    def test_current_noop(self):
        self.assertEqual(self.plan()['state'], 'current')
        self.assertFalse(self.apply())
        self.assertIsNone(self.ctx.journal)

    def test_edited_blocks_and_repair_backs_up(self):
        self.update()
        put(self.root, '@CF/addons/a.pbo', b'owner edit')
        self.assertEqual(self.plan()['state'], 'edited')
        with self.assertRaisesRegex(ws.SyncError, '--repair'):
            self.apply()
        self.assertIsNone(self.ctx.journal)
        self.apply(repair=True)
        self.assertEqual((self.ctx.backup_root / '@CF/addons/a.pbo').read_bytes(), b'owner edit')

    def test_unrecorded_blocks_even_yes(self):
        self.update()
        receipt = self.load()
        receipt['files'] = [e for e in receipt['files'] if e['path'] != '@CF/addons/a.pbo']
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, receipt)
        self.assertEqual(self.plan()['state'], 'unrecorded')
        with self.assertRaises(ws.SyncError):
            self.apply()
        self.assertIsNone(self.ctx.journal)

    def test_equal_unrecorded_is_adopted(self):
        receipt = self.load()
        receipt['files'] = [e for e in receipt['files'] if e['path'] != '@CF/addons/a.pbo']
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, receipt)
        self.assertEqual(self.plan()['state'], 'current')
        self.apply()
        self.assertTrue(any(e['path'] == '@CF/addons/a.pbo' for e in self.load()['files']))
        self.assertFalse(any(e['path'] == '@CF/addons/a.pbo' for e in self.ctx.journal['entries']))

    def test_new_and_removed_files(self):
        (self.source / 'addons/a.pbo.key.bisign').unlink()
        put(self.source, 'addons/new.bisign', b'new sig')
        self.apply()
        self.assertFalse((self.root / '@CF/addons/a.pbo.key.bisign').exists())
        self.assertEqual((self.root / '@CF/addons/new.bisign').read_bytes(), b'new sig')
        self.assertFalse(any(e['path'].endswith('a.pbo.key.bisign') for e in self.load()['files']))

    def test_case_only_rename_removals_before_writes(self):
        (self.source / 'addons/a.pbo').rename(self.source / 'addons/A.pbo')
        self.apply()
        self.assertFalse((self.root / '@CF/addons/a.pbo').exists())
        self.assertTrue((self.root / '@CF/addons/A.pbo').is_file())
        self.assertEqual(self.plan()['state'], 'current')

    def test_case_only_rename_rollback(self):
        (self.source / 'addons/a.pbo').rename(self.source / 'addons/A.pbo')
        self.apply()
        fi.rollback_run(self.ctx, self.ctx.backup_root, self.ctx.journal)
        self.assertTrue((self.root / '@CF/addons/a.pbo').is_file())
        self.assertFalse((self.root / '@CF/addons/A.pbo').exists())

    def test_shared_root_key_rotation_keeps_old_provider_key(self):
        put(self.root, '@Other/keys/key.bikey', b'old key')
        (self.source / 'keys/key.bikey').unlink()
        put(self.source, 'keys/new.bikey', b'new key')
        self.apply()
        self.assertEqual((self.root / 'keys/key.bikey').read_bytes(), b'old key')
        self.assertEqual((self.root / 'keys/new.bikey').read_bytes(), b'new key')
        self.assertNotIn('keys/key.bikey', {e['path'] for e in self.load()['files']})

    def test_root_key_not_owned_blocks_whole_item_even_repair(self):
        receipt = self.load()
        receipt['files'] = [e for e in receipt['files'] if e['path'] != 'keys/key.bikey']
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, receipt)
        self.update()
        put(self.source, 'keys/key.bikey', b'new key')
        with self.assertRaisesRegex(ws.SyncError, 'unowned root key'):
            self.apply(repair=True)
        self.assertIsNone(self.ctx.journal)
        self.assertEqual((self.root / '@CF/addons/a.pbo').read_bytes(), b'old pbo')

    def test_downgrade_refused(self):
        put(self.source, 'meta.cpp', 'timestamp = 9;')
        self.assertEqual(self.plan()['state'], 'downgrade')
        with self.assertRaises(ws.SyncError):
            self.apply(repair=True)

    def test_newest_source_chosen_not_first(self):
        other = self.base / 'other'
        shutil.copytree(self.source, other / self.item['id'])
        put(other / self.item['id'], 'meta.cpp', 'timestamp = 30;')
        state, path, detail = ws.find_item(self.item['id'], [self.content, other])
        self.assertEqual(state, 'present')
        self.assertEqual(path, other / self.item['id'])
        self.assertIn('sources disagree', detail)

    def test_mid_download_skips(self):
        (self.content.parent.parent / 'downloads/221100' / self.item['id']).mkdir(parents=True)
        self.assertEqual(self.plan()['state'], 'content-updating')
        self.assertIsNone(self.ctx.journal)

    def test_missing_content_keeps_existing(self):
        shutil.rmtree(self.source)
        self.assertEqual(self.plan()['state'], 'content-missing')
        self.assertIsNone(self.ctx.journal)

    def test_source_changed_mid_copy_rolls_back(self):
        self.update()
        original = ws.copy_atomic

        def changed(source, target, expected=None):
            if expected is not None:
                source.write_bytes(b'changed mid-copy')
            return original(source, target, expected)

        with mock.patch.object(ws, 'copy_atomic', side_effect=changed):
            with self.assertRaisesRegex(ws.SyncError, 'source changed'):
                self.apply()
        fi.rollback_run(self.ctx, self.ctx.backup_root, self.ctx.journal)
        self.assertEqual((self.root / '@CF/addons/a.pbo').read_bytes(), b'old pbo')
        self.assertEqual(self.load(), self.receipt)

    def test_interrupted_apply_pending_runs_and_recover(self):
        self.update()
        original = ws.copy_atomic

        def exit_after_copy(source, target, expected=None):
            original(source, target, expected)
            if expected is not None:
                raise SystemExit(99)

        with mock.patch.object(ws, 'copy_atomic', side_effect=exit_after_copy):
            with self.assertRaises(SystemExit):
                self.apply()
        runs = fi.pending_runs(self.ctx)
        self.assertEqual(len(runs), 1)
        fi.recover_runs(self.ctx, runs, False)
        self.assertEqual((self.root / '@CF/addons/a.pbo').read_bytes(), b'old pbo')
        self.assertEqual(self.load(), self.receipt)

    def test_enospc_preflight_writes_nothing(self):
        self.update()
        with mock.patch.object(ws.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(1, 1, 0)):
            with self.assertRaisesRegex(ws.SyncError, 'free space'):
                self.apply()
        self.assertIsNone(self.ctx.journal)

    def test_enospc_mid_write_rolls_back(self):
        self.update()
        original = ws.copy_atomic
        writes = []

        def no_space(source, target, expected=None):
            if expected is not None:
                writes.append(target)
                if len(writes) == 2:
                    raise OSError(28, 'No space left on device')
            return original(source, target, expected)

        with mock.patch.object(ws, 'copy_atomic', side_effect=no_space):
            with self.assertRaises(OSError):
                self.apply()
        fi.rollback_run(self.ctx, self.ctx.backup_root, self.ctx.journal)
        self.assertEqual((self.root / '@CF/addons/a.pbo').read_bytes(), b'old pbo')
        self.assertEqual(self.load(), self.receipt)

    def test_rollback_restores_receipt_bytes_and_next_apply_updates(self):
        self.update()
        before = (self.root / ws.RECEIPT_NAME).read_bytes()
        self.apply()
        fi.rollback_run(self.ctx, self.ctx.backup_root, self.ctx.journal)
        self.assertEqual((self.root / '@CF/addons/a.pbo').read_bytes(), b'old pbo')
        self.assertEqual((self.root / ws.RECEIPT_NAME).read_bytes(), before)
        self.assertEqual(self.plan()['state'], 'stale')
        self.ctx.journal = None
        self.apply()
        self.assertEqual(self.plan()['state'], 'current')

    def test_extra_kept_plain_apply_and_backed_up_only_repair(self):
        put(self.root, '@CF/addons/extra.pbo', b'owner extra')
        self.update()
        self.assertIn('@CF/addons/extra.pbo', self.plan()['extras'])
        self.apply()
        self.assertTrue((self.root / '@CF/addons/extra.pbo').exists())
        self.ctx.journal = None
        self.apply(repair=True)
        self.assertFalse((self.root / '@CF/addons/extra.pbo').exists())
        self.assertEqual((self.ctx.backup_root / '@CF/addons/extra.pbo').read_bytes(), b'owner extra')

    def test_unowned_folder_refresh_refused(self):
        with self.assertRaisesRegex(ws.SyncError, 'unowned'):
            ws.plan_refresh(self.item, [self.content], self.root, None)

    def test_repair_rows_use_workshop_step(self):
        self.assertEqual(fi.repair_step(dict(kind='edited', path='@CF/addons/a.pbo', step='workshop')), 'workshop')

    def installer_context(self):
        self.ctx.manifest = {'files': [], 'mission': 'dayzOffline.synthetic'}
        self.ctx.skip = set(fi.SKIPPABLE) - {'workshop'}
        self.ctx.args.workshop_content = [str(self.content)]
        self.ctx.args.yes = True
        self.item = next(i for i in ws.load_manifest()['mods'] if i['folder'] == '@CF')
        put(self.ctx.bundle, 'start-server.bat', 'DayZServer_x64.exe "-mod=@CF"')
        put(self.root, 'mission-sentinel', b'mission bytes unchanged')
        manifest = {'mods': [self.item], 'retired': []}
        patch = mock.patch.object(ws, 'load_manifest', return_value=manifest)
        patch.start()
        self.addCleanup(patch.stop)
        process = mock.patch.object(ws.subprocess, 'run', side_effect=AssertionError('process started'))
        process.start()
        self.addCleanup(process.stop)

    def test_installer_step3_plan_apply_and_second_run(self):
        self.installer_context()
        self.update()
        a = fi.analyze(self.ctx)
        status, lines, action = fi.plan_workshop(self.ctx, a)
        self.assertEqual(status, 'planned')
        self.assertIn('update @CF from', '\n'.join(lines))
        self.assertIn('2 file(s) to write', '\n'.join(lines))
        action()
        self.assertIn('updated @CF from', self.ctx.out.getvalue())
        self.assertIn('2 file(s) written', self.ctx.out.getvalue())
        self.assertEqual(fi.plan_workshop(self.ctx, fi.analyze(self.ctx))[0], 'already-done')
        self.assertEqual((self.root / 'mission-sentinel').read_bytes(), b'mission bytes unchanged')

    def test_installer_plain_apply_rejects_edits_before_journal(self):
        self.installer_context()
        self.update()
        put(self.root, '@CF/addons/a.pbo', b'owner edit')
        a = fi.analyze(self.ctx)
        self.assertEqual(fi.plan_workshop(self.ctx, a)[0], 'planned')
        self.assertIn('repairable', '\n'.join(fi.plan_workshop(self.ctx, a)[1]))
        self.assertIn('Workshop source', a.repairs[0]['detail'])
        self.assertEqual(fi.repair_step(a.repairs[0]), 'workshop')
        with self.assertRaises(fi.Refused):
            fi.pre_apply(self.ctx, a)
        self.assertIsNone(self.ctx.journal)
        self.ctx.args.repair = True
        fi.plan_workshop(self.ctx, fi.analyze(self.ctx))[2]()
        self.assertEqual(self.plan()['state'], 'current')

    def test_check_dependency_versions_fail_and_warn_read_only(self):
        self.installer_context()
        self.ctx.args.check = True
        self.update()
        put(self.root, '@CF/addons/extra.pbo', b'extra')
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        fi.run_check(self.ctx)
        output = self.ctx.out.getvalue()
        self.assertIn('FAIL  dependency_versions  @CF: stale; --apply', output)
        self.assertIn('WARN  dependency_versions  @CF/addons/extra.pbo: untracked extra', output)
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertIsNone(self.ctx.journal)

    def test_unowned_stale_folder_check_warn_and_never_changes(self):
        self.installer_context()
        (self.root / ws.RECEIPT_NAME).unlink()
        self.update()
        a = fi.analyze(self.ctx)
        self.assertFalse(a.dependencies)
        self.assertFalse(a.pending)
        self.assertIn('non-owned dependency differs from Workshop; update by hand', '\n'.join(a.dependency_warnings))
        self.assertEqual(fi.plan_workshop(self.ctx, a)[0], 'already-done')
        self.assertIsNone(self.ctx.journal)

    def test_steamcmd_only_warns_until_explicit_update(self):
        self.installer_context()
        executable = put(self.base, 'steamcmd.sh', '# synthetic executable, never run')
        self.ctx.args.steamcmd = str(executable)
        a = fi.analyze(self.ctx)
        self.assertIn('steamcmd copies are only refreshed with --update-workshop', '\n'.join(a.dependency_warnings))
        self.ctx.workshop_updated = True
        self.assertNotIn('steamcmd copies are only refreshed', '\n'.join(fi.analyze(self.ctx).dependency_warnings))

    def test_update_workshop_fetches_only_owned_before_analysis(self):
        self.installer_context()
        self.ctx.args.update_workshop = True
        self.ctx.args.steam_user = self.ctx.steam_user = 'synthetic-user'
        self.ctx.args.steamcmd = str(put(self.base, 'steamcmd.sh', '# never run'))
        calls = []

        def fetch(ctx, request):
            calls.append([i['folder'] for i in request.fetch])
            self.update()

        planners = {name: (lambda ctx, a: ('already-done', [], None)) for name in fi.STEPS}
        planners['workshop'] = fi.plan_workshop
        with mock.patch.object(fi, 'do_fetch', side_effect=fetch), mock.patch.dict(fi.PLANNERS, planners):
            fi.run_steps(self.ctx, True)
        self.assertEqual(calls, [['@CF']])
        self.assertEqual((self.root / '@CF/addons/a.pbo').read_bytes(), b'new pbo')
        self.assertEqual(self.plan()['state'], 'current')

    def test_check_and_dry_run_never_fetch_with_update_option(self):
        self.installer_context()
        self.ctx.args.update_workshop = True
        planners = {name: (lambda ctx, a: ('already-done', [], None)) for name in fi.STEPS}
        planners['workshop'] = fi.plan_workshop
        with mock.patch.object(fi, 'do_fetch', side_effect=AssertionError('fetch called')), mock.patch.dict(fi.PLANNERS, planners):
            fi.run_steps(self.ctx, False)
            self.ctx.args.check = True
            fi.run_check(self.ctx)
        self.assertIsNone(self.ctx.journal)

    def test_shared_same_name_different_key_blocks_rotation(self):
        self.update()
        put(self.source, 'keys/key.bikey', b'new key')
        put(self.root, '@Other/keys/key.bikey', b'old key')
        with self.assertRaisesRegex(ws.SyncError, 'conflicts with active provider'):
            self.apply()
        self.assertIsNone(self.ctx.journal)

    def test_two_owned_items_rotate_shared_key_together(self):
        other = dict(self.item, folder='@Other', id='1559212037')
        shutil.copytree(self.source, self.content / other['id'])
        shutil.copytree(self.root / '@CF', self.root / '@Other')
        receipt = self.load()
        receipt['files'] += [dict(e, path=e['path'].replace('@CF/', '@Other/'), item=other['id'])
                             for e in list(receipt['files']) if e['path'].startswith('@CF/')]
        receipt['dirs'] += ['@Other', '@Other/addons', '@Other/keys']
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, receipt)
        for source in (self.source, self.content / other['id']):
            put(source, 'keys/key.bikey', b'new key')
            put(source, 'addons/a.pbo.key.bisign', b'new sig')
        plans = [ws.plan_refresh(i, [self.content], self.root, receipt) for i in (self.item, other)]
        ws.apply_refresh(self.root, receipt, plans, lambda rel, digest: fi.record_written(self.ctx, rel, digest))
        self.assertEqual((self.root / 'keys/key.bikey').read_bytes(), b'new key')
        self.assertEqual(len([e for e in self.load()['files'] if e['path'] == 'keys/key.bikey']), 1)
        next_plans = [ws.plan_refresh(i, [self.content], self.root, self.load()) for i in (self.item, other)]
        self.assertTrue(all(not p['receipt_changed'] for p in next_plans))
        self.assertFalse(ws.apply_refresh(self.root, self.load(), next_plans,
                         lambda rel, digest: fi.record_written(self.ctx, rel, digest)))

    def test_equal_timestamp_sources_with_different_bytes_warn(self):
        other = self.base / 'other'
        shutil.copytree(self.source, other / self.item['id'])
        put(other / self.item['id'], 'addons/a.pbo', b'other bytes')
        self.assertIn('sources disagree', ws.find_item(self.item['id'], [self.content, other])[2])

    def test_bundle_shared_key_stays_on_server(self):
        bundle_keys = self.base / 'bundle-keys'
        put(bundle_keys, 'key.bikey', b'old key')
        (self.source / 'keys/key.bikey').unlink()
        put(self.source, 'keys/new.bikey', b'new key')
        p = self.plan(extra_key_dirs=[bundle_keys])
        self.apply(p)
        self.assertTrue((self.root / 'keys/key.bikey').is_file())
        self.assertNotIn('keys/key.bikey', {e['path'] for e in self.load()['files']})

    def test_missing_owned_folder_without_content_queues_fetch_and_missing_check(self):
        self.installer_context()
        shutil.rmtree(self.root / '@CF')
        shutil.rmtree(self.source)
        a = fi.analyze(self.ctx)
        self.assertEqual(a.fetch, [self.item])
        self.assertEqual([t['item'] for t in a.pending], [self.item])
        self.assertNotIn('existing server copy kept', '\n'.join(a.dependency_warnings))
        a.fetch = []
        with self.assertRaisesRegex(fi.Refused, 'not downloaded'):
            fi.pre_apply(self.ctx, a)

    def test_missing_owned_folder_restored_when_source_available(self):
        self.installer_context()
        shutil.rmtree(self.root / '@CF')
        a = fi.analyze(self.ctx)
        self.assertEqual([t['item'] for t in a.pending], [self.item])
        self.assertFalse(a.fetch)
        self.update()
        fi.plan_workshop(self.ctx, fi.analyze(self.ctx))[2]()
        self.assertEqual((self.root / '@CF/addons/a.pbo').read_bytes(), b'new pbo')
        self.assertEqual(self.plan()['state'], 'current')

    def test_missing_owned_fetch_installs_newest_available_copy(self):
        self.installer_context()
        shutil.rmtree(self.root / '@CF')
        shutil.rmtree(self.source)
        a = fi.analyze(self.ctx)
        with mock.patch.object(fi, 'do_fetch', side_effect=lambda ctx, request: self.update_source()):
            fi.plan_workshop(self.ctx, a)[2]()
        self.assertEqual((self.root / '@CF/addons/a.pbo').read_bytes(), b'new pbo')

    def update_source(self):
        for rel, data in [('addons/a.pbo', b'new pbo'), ('addons/a.pbo.key.bisign', b'new sig'),
                          ('keys/key.bikey', b'old key'), ('meta.cpp', 'timestamp = 30;')]:
            put(self.source, rel, data)

    def test_nonowned_comparison_errors_warn_read_only(self):
        self.installer_context()
        (self.root / ws.RECEIPT_NAME).unlink()
        for error in (ws.SyncError('synthetic symlink'), OSError('unreadable meta')):
            with self.subTest(error=error), mock.patch.object(ws, 'find_item', side_effect=error):
                a = fi.analyze(self.ctx)
                self.assertIn('@CF: not compared (%s)' % error, a.dependency_warnings)
                self.assertEqual(fi.plan_workshop(self.ctx, a)[0], 'already-done')
                self.ctx.args.check = True
                self.ctx.out = io.StringIO()
                fi.run_check(self.ctx)
                self.assertNotIn('FAIL  dependency_versions', self.ctx.out.getvalue())
                self.assertIn('WARN  dependency_versions  @CF: not compared', self.ctx.out.getvalue())
                self.assertIsNone(self.ctx.journal)

    def test_nonowned_bad_source_and_server_symlink_warn(self):
        self.installer_context()
        (self.root / ws.RECEIPT_NAME).unlink()
        bad = put(self.source, 'addons/no.txt', b'unsupported')
        a = fi.analyze(self.ctx)
        self.assertIn('not compared', '\n'.join(a.dependency_warnings))
        bad.unlink()
        (self.root / '@CF/addons/link.pbo').symlink_to(self.source / 'addons/a.pbo')
        self.assertIn('not compared', '\n'.join(fi.analyze(self.ctx).dependency_warnings))

    def test_owned_content_error_blocks_only_that_folder(self):
        self.installer_context()
        put(self.source, 'addons/no.txt', b'unsupported')
        a = fi.analyze(self.ctx)
        self.assertEqual(a.dependencies[0]['state'], 'blocked')
        self.assertIn('@CF: blocked (', '\n'.join(fi.plan_workshop(self.ctx, a)[1]))
        fi.pre_apply(self.ctx, a)
        self.ctx.args.check = True
        fi.run_check(self.ctx)
        self.assertIn('FAIL  dependency_versions  @CF: blocked', self.ctx.out.getvalue())
        self.assertIsNone(self.ctx.journal)

    def test_owned_error_and_downgrade_allow_other_item_update(self):
        self.installer_context()
        other = dict(self.item, folder='@Other', id='1559212037')
        shutil.copytree(self.source, self.content / other['id'])
        shutil.copytree(self.root / '@CF', self.root / '@Other')
        receipt = self.load()
        receipt['files'] += [dict(e, path=e['path'].replace('@CF/', '@Other/'), item=other['id'])
                             for e in list(receipt['files']) if e['path'].startswith('@CF/')]
        receipt['dirs'] += ['@Other', '@Other/addons', '@Other/keys']
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, receipt)
        ws.load_manifest.return_value['mods'].append(other)
        put(self.content / other['id'], 'addons/a.pbo', b'other updated')
        put(self.content / other['id'], 'meta.cpp', 'timestamp = 20;')
        for bad in ('downgrade', 'blocked'):
            updated_bytes = ('updated with ' + bad).encode()
            put(self.content / other['id'], 'addons/a.pbo', updated_bytes)
            put(self.source, 'meta.cpp', 'timestamp = 9;')
            if bad == 'blocked':
                put(self.source, 'meta.cpp', 'timestamp = 10;')
                put(self.source, 'addons/no.txt', b'unsupported')
            a = fi.analyze(self.ctx)
            self.assertEqual(a.dependencies[0]['state'], bad)
            fi.pre_apply(self.ctx, a)
            action = fi.plan_workshop(self.ctx, a)[2]
            if action:
                action()
            self.assertEqual((self.root / '@Other/addons/a.pbo').read_bytes(), updated_bytes)
            self.assertEqual((self.root / '@CF/addons/a.pbo').read_bytes(), b'old pbo')
            if bad == 'downgrade':
                self.ctx.args.check = True
                self.ctx.out = io.StringIO()
                fi.run_check(self.ctx)
                self.assertNotIn('FAIL  dependency_versions', self.ctx.out.getvalue())
                self.assertIn('WARN  dependency_versions  @CF: downgrade skipped', self.ctx.out.getvalue())
                self.assertIn('--update-workshop', self.ctx.out.getvalue())

    def test_download_marker_skips_only_its_source(self):
        other = self.base / 'other/content/221100'
        shutil.copytree(self.source, other / self.item['id'])
        marker = self.content.parent.parent / 'downloads/221100' / self.item['id']
        marker.mkdir(parents=True)
        state, source, detail = ws.find_item(self.item['id'], [self.content, other])
        self.assertEqual(state, 'present')
        self.assertEqual(source, other / self.item['id'])
        self.assertIn(str(marker), detail)

    def test_first_install_download_marker_refuses_with_path(self):
        self.installer_context()
        shutil.rmtree(self.root / '@CF')
        marker = self.content.parent.parent / 'downloads/221100' / self.item['id']
        marker.mkdir(parents=True)
        a = fi.analyze(self.ctx)
        self.assertTrue(a.pending)
        self.assertFalse(a.fetch)
        self.assertIn(str(marker), '\n'.join(fi.plan_workshop(self.ctx, a)[1]))
        with self.assertRaisesRegex(fi.Refused, 'Steam is still downloading 1559212036') as error:
            fi.pre_apply(self.ctx, a)
        self.assertIn(str(marker), str(error.exception))
        self.assertIsNone(self.ctx.journal)

    def test_unrecorded_repair_listing_and_backup(self):
        self.installer_context()
        receipt = self.load()
        receipt['files'] = [e for e in receipt['files'] if e['path'] != '@CF/addons/a.pbo']
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, receipt)
        put(self.root, '@CF/addons/a.pbo', b'owner unrecorded')
        self.ctx.args.repair = True
        a = fi.analyze(self.ctx)
        self.assertIn('not installed by us; replaced with the Workshop copy, old file backed up', a.repairs[0]['detail'])
        fi.plan_workshop(self.ctx, a)[2]()
        self.assertEqual((self.ctx.backup_root / '@CF/addons/a.pbo').read_bytes(), b'owner unrecorded')

    def test_existing_keys_directory_not_added_to_receipt(self):
        receipt = self.load()
        receipt['dirs'].remove('keys')
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, receipt)
        (self.root / 'keys').rename(self.root / 'Keys')
        self.update()
        put(self.source, 'keys/key.bikey', b'new key')
        self.apply()
        self.assertNotIn('keys', {d.casefold() for d in self.load()['dirs']})

    def test_new_directory_recorded_case_insensitively(self):
        shutil.rmtree(self.root / '@CF/keys')
        receipt = self.load()
        receipt['dirs'].remove('@CF/keys')
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, receipt)
        self.apply()
        self.assertIn('@CF/keys', self.load()['dirs'])
        receipt = self.load()
        receipt['dirs'] = [d.upper() for d in receipt['dirs']]
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, receipt)
        self.assertIsNotNone(self.load())

    def test_nonowned_incomplete_and_updating_warnings_are_accurate(self):
        self.installer_context()
        (self.root / ws.RECEIPT_NAME).unlink()
        for state in ('incomplete', 'content-updating'):
            with mock.patch.object(ws, 'find_item', return_value=(state, self.source, 'source unavailable')):
                warnings = '\n'.join(fi.analyze(self.ctx).dependency_warnings)
                self.assertIn(state, warnings)
                self.assertNotIn('differs from Workshop', warnings)

    def test_dry_run_preserves_interactive_edited_repair_offer(self):
        self.installer_context()
        put(self.root, '@CF/addons/a.pbo', b'owner edit')
        planners = {name: (lambda ctx, a: ('already-done', [], None)) for name in fi.STEPS}
        planners['workshop'] = fi.plan_workshop
        with mock.patch.dict(fi.PLANNERS, planners):
            self.assertFalse(fi.run_steps(self.ctx, False))
        self.assertTrue(any(row['kind'] == 'edited' for row in self.ctx.repair_blocked))
        self.assertIsNone(self.ctx.journal)

    def test_owned_top_level_nonallowlisted_file_blocks(self):
        self.installer_context()
        put(self.source, 'no.exe', b'unsupported')
        self.assertEqual(fi.analyze(self.ctx).dependencies[0]['state'], 'blocked')

    def test_repaired_receipt_persisted_when_refresh_replan_is_noop(self):
        self.installer_context()
        orphan = put(self.root, 'keys/orphan.bikey', b'orphan')
        put(self.root, '@Other/keys/orphan.bikey', b'orphan')
        receipt = self.load()
        receipt['files'].append(dict(path='keys/orphan.bikey', item=self.item['id'],
                                     sha256=ws.sha256_of(orphan), size=orphan.stat().st_size))
        ws.write_json_atomic(self.root / ws.RECEIPT_NAME, receipt)
        self.update()
        a = fi.analyze(self.ctx)
        self.assertTrue(a.receipt_repaired)
        # Steam's content returns to the installed bytes after the initial analysis.
        put(self.source, 'addons/a.pbo', b'old pbo')
        put(self.source, 'meta.cpp', 'timestamp = 10;')
        fi.plan_workshop(self.ctx, a)[2]()
        self.assertFalse(fi.analyze(self.ctx).receipt_repaired)
        self.assertNotIn('keys/orphan.bikey', {e['path'] for e in self.load()['files']})
        self.assertTrue(orphan.exists())
        self.assertTrue(any(e['path'] == ws.RECEIPT_NAME for e in self.ctx.journal['entries']))

    def test_current_check_pass_row(self):
        self.installer_context()
        self.ctx.args.check = True
        fi.run_check(self.ctx)
        self.assertIn('PASS  dependency_versions', self.ctx.out.getvalue())

    def test_uppercase_server_addons_directory_kept_consistent(self):
        (self.root / '@CF/addons').rename(self.root / '@CF/Addons')
        self.update()
        self.apply()
        self.assertFalse((self.root / '@CF/addons').exists())
        self.assertTrue((self.root / '@CF/Addons/a.pbo').exists())
        self.assertEqual(self.plan()['state'], 'current')

    def test_casefold_folder_key_and_root_key_rows_validate(self):
        (self.root / '@CF/keys').rename(self.root / '@CF/Keys')
        (self.root / 'keys').rename(self.root / 'Keys')
        self.update()
        put(self.source, 'keys/key.bikey', b'new key')
        self.apply()
        self.assertEqual((self.root / 'Keys/key.bikey').read_bytes(), b'new key')
        self.assertEqual(self.plan()['state'], 'current')
        self.assertIn('Keys/key.bikey', {e['path'] for e in self.load()['files']})
        self.assertFalse(self.plan()['receipt_changed'])

    def test_removed_owner_edited_file_blocks_without_repair(self):
        (self.source / 'addons/a.pbo.key.bisign').unlink()
        put(self.root, '@CF/addons/a.pbo.key.bisign', b'owner edit')
        self.assertEqual(self.plan()['state'], 'edited')
        with self.assertRaises(ws.SyncError):
            self.apply()
        self.assertIsNone(self.ctx.journal)

    def test_owner_edit_after_plan_never_overwritten_even_repair(self):
        self.update()
        p = self.plan()
        put(self.root, '@CF/addons/a.pbo', b'edit after plan')
        with self.assertRaisesRegex(ws.SyncError, 'changed after planning'):
            self.apply(p, repair=True)
        self.assertIsNone(self.ctx.journal)

    def test_absent_root_key_installed_with_folder_update(self):
        (self.root / 'keys/key.bikey').unlink()
        self.apply()
        self.assertEqual((self.root / 'keys/key.bikey').read_bytes(), b'old key')
        self.assertEqual(self.plan()['state'], 'current')

    def test_unknown_source_timestamp_cannot_downgrade_known_server(self):
        put(self.source, 'meta.cpp', 'publishedid = 1559212036;')
        self.assertEqual(self.plan()['state'], 'downgrade')

    def test_bundle_same_name_key_conflict_blocks_before_writes(self):
        self.update()
        bundle_keys = self.base / 'bundle-keys'
        put(bundle_keys, 'key.bikey', b'old key')
        put(self.source, 'keys/key.bikey', b'new key')
        with self.assertRaisesRegex(ws.SyncError, 'conflicts with active provider'):
            self.apply(self.plan(extra_key_dirs=[bundle_keys]))
        self.assertIsNone(self.ctx.journal)

    def test_edited_wrong_size_is_classified_without_hashing_server_pbo(self):
        self.update()
        target = put(self.root, '@CF/addons/a.pbo', b'owner edit with a different size')
        original = ws.sha256_of

        def hashed(path):
            self.assertNotEqual(path, target, 'size already rules out both Workshop and receipt equality')
            return original(path)

        with mock.patch.object(ws, 'sha256_of', side_effect=hashed):
            self.assertEqual(self.plan()['state'], 'edited')

    def test_size_difference_skips_workshop_equality_hash(self):
        self.update()
        put(self.source, 'addons/a.pbo', b'a larger source pbo')
        p = self.plan()
        self.assertEqual(p['state'], 'stale')
        # matches_file itself must reject a different size without reading the file.
        with mock.patch.object(ws, 'sha256_of', side_effect=AssertionError('unnecessary hash')):
            self.assertFalse(ws.matches_file(self.root / '@CF/addons/a.pbo', 'unused', 999))


if __name__ == '__main__':
    unittest.main()
