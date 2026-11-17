"""Actual temporary-directory transactions; all archive inputs are synthetic."""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools.package import deploy, pbo


class Interrupted(BaseException):
    """Simulate process death without automatic exception rollback."""


class DeploymentBehavior(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.dest = self.root / 'private-runtime'
        self.dest.mkdir()
        self.profiles = self.dest / 'profiles/HollowCountry/state.bin'
        self.profiles.parent.mkdir(parents=True)
        self.profiles.write_bytes(b'SYNTHETIC-SAVE\x00\xff')
        (self.dest / 'other-mod.txt').write_bytes(b'unrelated')
        self.one, self.two = self.package('one'), self.package('two')

    def package(self, version):
        addon, mission = self.root / ('addon-' + version), self.root / ('mission-' + version)
        addon.mkdir()
        mission.mkdir()
        (addon / 'config.cpp').write_text('class Synthetic_' + version + ' {};\n')
        (addon / 'mod.cpp').write_text('name="Synthetic-' + version + '";\n')
        layouts = addon / 'gui/layouts'
        layouts.mkdir(parents=True)
        (layouts / 'hc_synthetic.layout').write_text('FrameWidgetClass Synthetic { size 1 1 }\n')
        (mission / 'README.md').write_text('Synthetic original fixture ' + version)
        archive = self.root / (version + '.zip')
        archive.write_bytes(pbo.handoff(addon, mission))
        return archive

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob('*') if p.is_file()}

    def installed(self):
        return self.snapshot(self.dest / deploy.ACTIVE)

    def install(self, package=None, **kwargs):
        return deploy.install(package or self.one, self.dest, server_stopped=True, **kwargs)

    def crash(self, event):
        def checkpoint(actual):
            if actual == event:
                raise Interrupted(actual)
        return checkpoint

    def assert_profiles(self):
        self.assertEqual(self.profiles.read_bytes(), b'SYNTHETIC-SAVE\x00\xff')
        self.assertEqual((self.dest / 'other-mod.txt').read_bytes(), b'unrelated')

    def test_plan_read_only_and_install_verified_roundtrip(self):
        before = self.snapshot(self.dest)
        self.assertEqual(deploy.plan(self.one, self.dest)['operation'], 'install')
        self.assertFalse((self.dest / deploy.CONTROL).exists())
        self.assertEqual(before, self.snapshot(self.dest))
        result = self.install()
        self.assertEqual(result['status'], 'committed')
        self.assertEqual(result['runtime_acceptance'], 'pending')
        with zipfile.ZipFile(self.one) as archive:
            self.assertEqual(self.installed(), {n: archive.read(n) for n in archive.namelist()})
        self.assert_profiles()

    def test_source_export_without_agent_metadata_is_not_a_runtime_destination(self):
        source = self.root / 'synthetic-source-export'
        module = source / 'tools/package/deploy.py'
        module.parent.mkdir(parents=True)
        module.write_text('# synthetic exported helper')
        marker = source / 'mods/HollowCountry/config.cpp'
        marker.parent.mkdir(parents=True)
        marker.write_text('// synthetic authored addon')
        with patch.object(deploy, '__file__', str(module)):
            for target in (source, module.parent, self.root):
                with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'source/root'):
                    deploy._root(target)

    def test_native_short_name_parent_allows_exact_install_and_rollback(self):
        # Hosted Windows uses RUNNER~1 in TEMP. Host paths are not PBO members.
        short = self.root / 'RUNNER~1'
        short.mkdir()
        archive = short / 'package.zip'
        archive.write_bytes(self.one.read_bytes())
        destination = short / 'runtime'
        destination.mkdir()
        result = deploy.install(archive, destination, server_stopped=True)
        self.assertEqual(result['status'], 'committed')
        restored = deploy.rollback(destination, result['transaction'], server_stopped=True)
        self.assertEqual(restored['status'], 'committed')
        self.assertFalse((destination / deploy.ACTIVE).exists())
        with self.assertRaises(ValueError):
            pbo.safe_name('RUNNER~1')  # Archive allowlist is unchanged.

    def test_upgrade_migration_exact_backup_and_targeted_rollback_idempotence(self):
        first = self.install()
        original = self.installed()
        second = self.install(self.two, operation='migrate')
        self.assertNotEqual(original, self.installed())
        backup = self.dest / deploy.CONTROL / 'transactions' / second['transaction'] / 'before'
        self.assertEqual(self.snapshot(backup), original)
        result = deploy.rollback(self.dest, second['transaction'], server_stopped=True)
        self.assertEqual(result['status'], 'committed')
        self.assertEqual(original, self.installed())
        before = self.snapshot(self.dest / deploy.CONTROL)
        again = deploy.rollback(self.dest, second['transaction'], server_stopped=True)
        self.assertTrue(again['idempotent'])
        self.assertEqual(before, self.snapshot(self.dest / deploy.CONTROL))
        deploy.rollback(self.dest, first['transaction'], server_stopped=True)
        self.assertFalse((self.dest / deploy.ACTIVE).exists())
        self.assert_profiles()

    def test_repeated_install_noop(self):
        first = self.install()
        before = self.snapshot(self.dest / deploy.CONTROL)
        again = self.install()
        self.assertTrue(again['idempotent'])
        self.assertEqual(first['transaction'], again['transaction'])
        self.assertEqual(before, self.snapshot(self.dest / deploy.CONTROL))

    def test_operation_and_stopped_server_preconditions(self):
        with self.assertRaises(ValueError):
            deploy.install(self.one, self.dest)
        with self.assertRaises(ValueError):
            self.install(self.two, operation='upgrade')
        first = self.install()
        with self.assertRaises(ValueError):
            self.install(self.two)
        with self.assertRaises(ValueError):
            deploy.rollback(self.dest, first['transaction'])
        with self.assertRaises(ValueError):
            deploy.recover(self.dest)

    def test_tampered_archive_refused_before_writes(self):
        out = io.BytesIO()
        with zipfile.ZipFile(self.one) as src, zipfile.ZipFile(out, 'w') as dst:
            for name in src.namelist():
                dst.writestr(name, b'tampered' if name.endswith('.pbo') else src.read(name))
        self.one.write_bytes(out.getvalue())
        before = self.snapshot(self.dest)
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(before, self.snapshot(self.dest))

    def rewrite(self, change):
        with zipfile.ZipFile(self.one) as src:
            data = {n: src.read(n) for n in src.namelist()}
        manifest = json.loads(data['manifest.json'])
        change(data, manifest)
        data['manifest.json'] = pbo.json_bytes(manifest)
        with zipfile.ZipFile(self.one, 'w') as dst:
            for name, contents in data.items():
                dst.writestr(name, contents)

    def test_private_distribution_and_no_bundled_keys_or_assets(self):
        self.rewrite(lambda data, manifest: manifest.update(distribution='public'))
        with self.assertRaises(ValueError):
            self.install()
        self.one = self.package('safe')
        def add_key(data, manifest):
            contents = {'config.cpp': b'class Synthetic {};', 'secret.biprivatekey': b'NOT-A-KEY'}
            value = pbo.pack(contents)
            name = '@HollowCountry/addons/hollowcountry.pbo'
            data[name] = value
            manifest['files'][name] = {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
            manifest['sources'] = {n: hashlib.sha256(v).hexdigest() for n, v in contents.items()}
        self.rewrite(add_key)
        with self.assertRaises(ValueError):
            self.install()
        self.assertFalse((self.dest / deploy.CONTROL).exists())

    def test_steam_checkout_symlink_hardlink_reparse_path_guards(self):
        steam = self.root / 'sTeAmApPs/common/private'
        steam.mkdir(parents=True)
        source = self.root / 'checkout'
        source.mkdir()
        (source / '.git').mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(self.dest, target_is_directory=True)
        linked = self.root / 'linked.zip'
        os.link(self.one, linked)
        for archive, destination in [(self.one, steam), (self.one, source),
                                     (self.one, alias), (linked, self.dest)]:
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                deploy.plan(archive, destination)
        fake = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_nlink=1,
                               st_file_attributes=0x400)
        with self.assertRaises(ValueError):
            deploy._check_stat(fake, directory=True)

    def test_unowned_tree_metadata_and_case_alias_refused(self):
        for name in [deploy.ACTIVE, deploy.CONTROL, deploy.ACTIVE.lower()]:
            path = self.dest / name
            path.mkdir()
            try:
                with self.assertRaises(ValueError):
                    self.install()
            finally:
                path.rmdir()
        self.assert_profiles()

    def test_active_edits_extra_files_and_directories_refuse_all_mutations(self):
        first = self.install()
        active = self.dest / deploy.ACTIVE
        config = active / '@HollowCountry/mod.cpp'
        saved = config.read_bytes()
        for mutation in ['edit', 'extra-file', 'extra-directory']:
            path = active / ('modification.txt' if mutation == 'extra-file' else 'intruder')
            if mutation == 'edit':
                config.write_bytes(b'changed')
            elif mutation == 'extra-file':
                path.write_bytes(b'unrelated')
            else:
                path.mkdir()
            before = self.snapshot(self.dest)
            calls = [lambda: self.install(self.two, operation='upgrade'),
                     lambda: deploy.rollback(self.dest, first['transaction'], server_stopped=True)]
            for call in calls:
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    call()
                self.assertEqual(before, self.snapshot(self.dest))
            if mutation == 'edit':
                config.write_bytes(saved)
            elif path.is_file():
                path.unlink()
            else:
                path.rmdir()

    def test_backup_tampering_refuses_rollback(self):
        self.install()
        second = self.install(self.two, operation='upgrade')
        backup = self.dest / deploy.CONTROL / 'transactions' / second['transaction'] / 'before'
        (backup / '@HollowCountry/mod.cpp').write_bytes(b'drift')
        before = self.snapshot(self.dest)
        with self.assertRaises(ValueError):
            deploy.rollback(self.dest, second['transaction'], server_stopped=True)
        self.assertEqual(before, self.snapshot(self.dest))

    def test_abort_every_precommit_checkpoint(self):
        for event in ['journaled', 'stage-file', 'staged', 'backed-up', 'activated']:
            with self.subTest(event=event):
                dest = self.root / ('abort-' + event)
                dest.mkdir()
                deploy.install(self.one, dest, server_stopped=True)
                original = self.snapshot(dest / deploy.ACTIVE)
                with self.assertRaises(Interrupted):
                    deploy.install(self.two, dest, operation='upgrade', server_stopped=True,
                                   checkpoint=self.crash(event))
                with self.assertRaises(ValueError):
                    deploy.install(self.two, dest, operation='upgrade', server_stopped=True)
                result = deploy.recover(dest, action='abort', server_stopped=True)
                self.assertEqual(result['status'], 'aborted')
                self.assertEqual(original, self.snapshot(dest / deploy.ACTIVE))
                self.assertTrue(deploy.recover(dest, action='abort', server_stopped=True)['idempotent'])

    def test_resume_complete_stage_and_committed_transactions_cannot_be_aborted(self):
        for event in ['staged', 'backed-up', 'activated', 'committed', 'recorded']:
            with self.subTest(event=event):
                dest = self.root / ('resume-' + event)
                dest.mkdir()
                deploy.install(self.one, dest, server_stopped=True)
                with self.assertRaises(Interrupted):
                    deploy.install(self.two, dest, operation='upgrade', server_stopped=True,
                                   checkpoint=self.crash(event))
                result = deploy.recover(dest, action='abort' if event in {'committed', 'recorded'}
                                        else 'resume', server_stopped=True)
                self.assertEqual(result['status'], 'committed')
                with zipfile.ZipFile(self.two) as archive:
                    self.assertEqual(self.snapshot(dest / deploy.ACTIVE),
                                     {n: archive.read(n) for n in archive.namelist()})

    def test_partial_stage_resume_refused_abort_works(self):
        self.install()
        original = self.installed()
        with self.assertRaises(Interrupted):
            self.install(self.two, operation='upgrade', checkpoint=self.crash('stage-file'))
        with self.assertRaises(ValueError):
            deploy.recover(self.dest, action='resume', server_stopped=True)
        deploy.recover(self.dest, action='abort', server_stopped=True)
        self.assertEqual(original, self.installed())

    def test_recovery_drift_and_journal_traversal_refused(self):
        self.install()
        with self.assertRaises(Interrupted):
            self.install(self.two, operation='upgrade', checkpoint=self.crash('activated'))
        victim = self.dest / deploy.ACTIVE / '@HollowCountry/mod.cpp'
        original = victim.read_bytes()
        victim.write_bytes(b'drift after interruption')
        with self.assertRaises(ValueError):
            deploy.recover(self.dest, action='abort', server_stopped=True)
        victim.write_bytes(original)
        journal = self.dest / deploy.CONTROL / 'pending.json'
        data = json.loads(journal.read_text())
        data['transaction'] = '../../profiles'
        journal.write_bytes(pbo.json_bytes(data))
        with self.assertRaises(ValueError):
            deploy.recover(self.dest, action='abort', server_stopped=True)
        self.assert_profiles()

    def test_initial_install_and_rollback_interruptions(self):
        with self.assertRaises(Interrupted):
            self.install(checkpoint=self.crash('activated'))
        deploy.recover(self.dest, action='abort', server_stopped=True)
        self.assertFalse((self.dest / deploy.ACTIVE).exists())
        first = self.install()
        with self.assertRaises(Interrupted):
            deploy.rollback(self.dest, first['transaction'], server_stopped=True,
                            checkpoint=self.crash('activated'))
        deploy.recover(self.dest, action='abort', server_stopped=True)
        self.assertTrue(self.installed())
        deploy.rollback(self.dest, first['transaction'], server_stopped=True)
        self.assertFalse((self.dest / deploy.ACTIVE).exists())

    def test_stale_transaction_and_corrupt_state_refused(self):
        first = self.install()
        self.install(self.two, operation='upgrade')
        for target in [first['transaction'], '../profiles']:
            with self.assertRaises(ValueError):
                deploy.rollback(self.dest, target, server_stopped=True)
        state = self.dest / deploy.CONTROL / 'state.json'
        state.write_text('{broken')
        with self.assertRaises(ValueError):
            deploy.plan(self.two, self.dest)
        self.assert_profiles()

    def test_lock_refuses_second_process_without_breaking_owner(self):
        self.install()
        with deploy._locked(self.dest / deploy.CONTROL):
            result = subprocess.run([sys.executable, '-m', 'tools.package.deploy', 'upgrade',
                                     '--zip', str(self.two), '--destination', str(self.dest),
                                     '--server-stopped'], capture_output=True, text=True,
                                    env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('locked', result.stderr.lower())

    def test_standalone_cli_readonly_json_plan(self):
        result = subprocess.run([sys.executable, 'tools/package/deploy.py', 'plan',
                                 '--zip', str(self.one), '--destination', str(self.dest)],
                                capture_output=True, text=True,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['operation'], 'install')
        self.assertFalse((self.dest / deploy.CONTROL).exists())

    def test_archived_journal_checksum_drift_refused_before_rollback(self):
        self.install()
        second = self.install(self.two, operation='upgrade')
        journal = self.dest / deploy.CONTROL / 'transactions' / second['transaction'] / 'journal.json'
        value = json.loads(journal.read_text())
        # Still a structurally legal upgrade, but no longer the committed journal.
        value['operation'] = 'migrate'
        journal.write_bytes(pbo.json_bytes(value))
        before = self.snapshot(self.dest)
        with self.assertRaises(ValueError):
            deploy.rollback(self.dest, second['transaction'], server_stopped=True)
        self.assertEqual(before, self.snapshot(self.dest))

    def test_recovery_receipt_drift_refused_before_directory_changes(self):
        self.install()
        with self.assertRaises(Interrupted):
            self.install(self.two, operation='upgrade', checkpoint=self.crash('activated'))
        control = self.dest / deploy.CONTROL
        intent = json.loads((control / 'pending.json').read_text())
        receipt = control / 'transactions' / intent['transaction'] / 'result.json'
        receipt.write_text('{"status":"fabricated"}')
        before = self.snapshot(self.dest)
        with self.assertRaises(ValueError):
            deploy.recover(self.dest, action='abort', server_stopped=True)
        self.assertEqual(before, self.snapshot(self.dest))

    def test_abort_recovery_itself_can_crash_and_resume_idempotently(self):
        for event in ['abort-deactivated', 'abort-restored', 'abort-recorded']:
            with self.subTest(event=event):
                dest = self.root / event
                dest.mkdir()
                deploy.install(self.one, dest, server_stopped=True)
                original = self.snapshot(dest / deploy.ACTIVE)
                with self.assertRaises(Interrupted):
                    deploy.install(self.two, dest, operation='upgrade', server_stopped=True,
                                   checkpoint=self.crash('activated'))
                with self.assertRaises(Interrupted):
                    deploy.recover(dest, action='abort', server_stopped=True,
                                   checkpoint=self.crash(event))
                # A persisted abort decision wins over a changed retry argument.
                result = deploy.recover(dest, action='resume', server_stopped=True)
                self.assertEqual(result['status'], 'aborted')
                self.assertEqual(original, self.snapshot(dest / deploy.ACTIVE))

    def test_partial_atomic_journal_and_unpublished_stage_file_preserved(self):
        self.install()
        original = self.installed()
        control = self.dest / deploy.CONTROL
        temporary = control / '.pending.json.next'
        temporary.write_bytes(b'{partial journal')
        with self.assertRaises(ValueError):
            self.install(self.two, operation='upgrade')
        deploy.recover(self.dest, action='abort', server_stopped=True)
        self.assertIn(b'{partial journal', self.snapshot(control / 'quarantine').values())
        original_new = deploy._new
        def interrupted_write(path, data):
            if Path(path).name == 'work.tmp':
                original_new(path, data[:3])
                raise OSError('SYNTHETIC injected storage failure')
            return original_new(path, data)
        with patch.object(deploy, '_new', side_effect=interrupted_write), self.assertRaises(OSError):
            self.install(self.two, operation='upgrade')
        result = deploy.recover(self.dest, action='abort', server_stopped=True)
        work = control / 'transactions' / result['transaction'] / 'work.tmp'
        self.assertEqual(work.stat().st_size, 3)
        self.assertEqual(original, self.installed())

    def test_committed_metadata_and_owned_payload_links_are_refused(self):
        self.install()
        active = self.dest / deploy.ACTIVE / '@HollowCountry/mod.cpp'
        data = active.read_bytes()
        active.unlink()
        active.symlink_to(self.profiles)
        with self.assertRaises(ValueError):
            self.install(self.two, operation='upgrade')
        active.unlink()
        active.write_bytes(data)
        os.link(active, self.root / 'outside-link')
        with self.assertRaises(ValueError):
            self.install(self.two, operation='upgrade')
        self.assert_profiles()

    def test_custom_steam_library_and_windows_unsafe_destination_names_refused(self):
        library = self.root / 'Games'
        (library / 'steamapps').mkdir(parents=True)
        destination = library / 'private'
        destination.mkdir()
        with self.assertRaises(ValueError):
            deploy.plan(self.one, destination)
        # Never ask Windows to create a reserved device, ADS or trailing-dot
        # alias. Exercise the lexical guard before any filesystem mutation.
        for name in ['CON', 'runtime:stream', 'trailing.']:
            destination = self.root / name
            with self.subTest(path=destination), self.assertRaises(ValueError):
                deploy._safe(destination, missing=True)
        self.assert_profiles()

    def test_real_process_exit_releases_lock_and_recovery_restores_commit_boundary(self):
        script = (
            'import os,sys; from pathlib import Path; from tools.package import deploy; '
            'deploy.install(Path(sys.argv[1]),Path(sys.argv[2]),operation="upgrade",'
            'server_stopped=True,checkpoint=lambda event: '
            'os._exit(91) if event==sys.argv[3] else None)'
        )
        for event in ['stage-file', 'backed-up', 'activated', 'committed']:
            with self.subTest(event=event):
                dest = self.root / ('process-' + event)
                dest.mkdir()
                deploy.install(self.one, dest, server_stopped=True)
                original = self.snapshot(dest / deploy.ACTIVE)
                result = subprocess.run([sys.executable, '-c', script, str(self.two), str(dest), event],
                                        capture_output=True, text=True,
                                        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
                self.assertEqual(result.returncode, 91, result.stderr)
                recovered = deploy.recover(dest, action='abort', server_stopped=True)
                self.assertEqual(recovered['status'], 'committed' if event == 'committed' else 'aborted')
                if event != 'committed':
                    self.assertEqual(original, self.snapshot(dest / deploy.ACTIVE))

    def test_duplicate_manifest_keys_and_nonregular_zip_members_refused(self):
        with zipfile.ZipFile(self.one) as source:
            files = {n: source.read(n) for n in source.namelist()}
        for problem in ['duplicate', 'special']:
            with zipfile.ZipFile(self.one, 'w') as target:
                for name, value in files.items():
                    info = zipfile.ZipInfo(name)
                    if problem == 'special' and name.endswith('README.md'):
                        info.create_system = 3
                        info.external_attr = (stat.S_IFIFO | 0o600) << 16
                    if problem == 'duplicate' and name == 'manifest.json':
                        value = b'{"schema":1,' + value[1:]
                    target.writestr(info, value)
            before = self.snapshot(self.dest)
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.install()
            self.assertEqual(before, self.snapshot(self.dest))

    def test_compressed_oversize_manifest_refused_without_opening_any_member(self):
        """CR-01: rejection must precede decompression, not just JSON parsing."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', b' ' * (8 * 1024 * 1024))
        blob = buffer.getvalue()
        self.assertLess(len(blob), 16 * 1024)
        opened = []
        original_open = zipfile.ZipFile.open
        def observe(source, name, *args, **kwargs):
            opened.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
            return original_open(source, name, *args, **kwargs)
        before = self.snapshot(self.dest)
        with patch.object(deploy, '_read', return_value=blob), \
                patch.object(zipfile.ZipFile, 'open', observe), \
                patch.object(pbo, 'verify_handoff') as verifier:
            with self.assertRaises(ValueError):
                deploy.plan(self.one, self.dest)
            verifier.assert_not_called()
        self.assertEqual(opened, [], 'oversized manifest was decompressed before rejection')
        self.assertEqual(before, self.snapshot(self.dest))

    def test_zip_entry_count_and_aggregate_budget_checked_before_member_reads(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', b'{"files":{}}')
            archive.writestr('mission/hollow-country/README.md', b'x' * 40)
            archive.writestr('@HollowCountry/mod.cpp', b'y' * 40)
        # Explicitly reduced synthetic budgets avoid allocating a large payload.
        for setting, budget in [('MAX_ENTRIES', 2), ('MAX_BYTES', 64)]:
            with self.subTest(budget=setting), patch.object(pbo, setting, budget), \
                    patch.object(deploy, '_read', return_value=buffer.getvalue()), \
                    patch.object(zipfile.ZipFile, 'open', autospec=True) as opened:
                # An attempted member read returns a mock rather than real data;
                # the test must catch it even if eventual validation also fails.
                with self.assertRaises((ValueError, TypeError)):
                    deploy.plan(self.one, self.dest)
                opened.assert_not_called()

    def test_every_member_has_bounded_stream_read_before_existing_verifier(self):
        original_open, original_read = zipfile.ZipFile.open, zipfile.ZipExtFile.read
        original_verifier = pbo.verify_handoff
        with zipfile.ZipFile(self.one) as archive:
            expected = set(archive.namelist())
        opened, requests = set(), []
        phase = {'preflight': True}
        def observe_open(source, name, *args, **kwargs):
            if phase['preflight']:
                opened.add(name.filename if isinstance(name, zipfile.ZipInfo) else name)
            return original_open(source, name, *args, **kwargs)
        def bounded_read(stream, size=-1):
            if phase['preflight']:
                requests.append(size)
                self.assertGreater(size, 0, 'unbounded pre-verifier member read')
                self.assertLessEqual(size, 64 * 1024, 'oversize pre-verifier read chunk')
            return original_read(stream, size)
        def verify_after_preflight(blob):
            self.assertEqual(opened, expected, 'verifier ran before every member was bounded')
            phase['preflight'] = False
            return original_verifier(blob)
        with patch.object(zipfile.ZipFile, 'open', observe_open), \
                patch.object(zipfile.ZipExtFile, 'read', bounded_read), \
                patch.object(pbo, 'verify_handoff', side_effect=verify_after_preflight) as verifier:
            deploy.plan(self.one, self.dest)
            verifier.assert_called_once()
        self.assertTrue(requests)
        self.assertFalse((self.dest / deploy.CONTROL).exists())

    def test_compression_without_bounded_native_decompression_refused_before_open(self):
        # ZipExtFile uses a capped zlib decompress for DEFLATED. Its BZIP2/LZMA
        # branches can inflate a whole compressed input chunk before read(n)
        # truncates the result, so these formats are outside our contract.
        original_open = zipfile.ZipFile.open
        for method in [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA]:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', compression=method) as archive:
                archive.writestr('manifest.json', b'{"files":{}}')
            opened = []
            def observe(source, name, *args, **kwargs):
                opened.append(name)
                return original_open(source, name, *args, **kwargs)
            with self.subTest(compression=method), \
                    patch.object(deploy, '_read', return_value=buffer.getvalue()), \
                    patch.object(zipfile.ZipFile, 'open', observe):
                with self.assertRaises(ValueError):
                    deploy.plan(self.one, self.dest)
                self.assertEqual(opened, [], 'unsupported decompressor ran before rejection')

    def test_metadata_validation_does_not_read_the_windows_locked_byte(self):
        self.install()
        control = self.dest / deploy.CONTROL
        original_read = deploy._read
        def locked_byte_read(path, *args, **kwargs):
            if Path(path) == control / 'lock':
                raise PermissionError('SYNTHETIC Windows byte-range lock denies reading this byte')
            return original_read(path, *args, **kwargs)
        with deploy._locked(control), patch.object(deploy, '_read', side_effect=locked_byte_read):
            state = deploy._metadata(control)
        self.assertIsNotNone(state['active'])

    def test_executable_deployment_bdd_scenarios(self):
        """Execute every Given/When/Then line; an unknown step is a test failure."""
        feature = Path('tests/fixtures/deploy/deployment.feature').read_text()
        scenarios = []
        for raw in feature.splitlines():
            line = raw.strip()
            if not line or line.startswith(('#', 'Feature:')):
                continue
            if line.startswith('Scenario:'):
                scenarios.append((line, []))
            else:
                self.assertTrue(scenarios, 'step without scenario')
                scenarios[-1][1].append(line)
        self.assertEqual(len(scenarios), 4)
        for index, (name, steps) in enumerate(scenarios):
            with self.subTest(scenario=name):
                destination = self.root / ('bdd-' + str(index))
                destination.mkdir()
                save = destination / 'profiles/synthetic-save.bin'
                save.parent.mkdir()
                save.write_bytes(b'SYNTHETIC opaque runtime save')
                state = {}
                def install_one():
                    state['first'] = deploy.install(self.one, destination, server_stopped=True)
                    state['original'] = self.snapshot(destination / deploy.ACTIVE)
                def upgrade():
                    state['second'] = deploy.install(self.two, destination, operation='upgrade', server_stopped=True)
                def crash(event):
                    with self.assertRaises(Interrupted):
                        deploy.install(self.two, destination, operation='upgrade', server_stopped=True,
                                       checkpoint=self.crash(event))
                def abort():
                    deploy.recover(destination, action='abort', server_stopped=True)
                def rollback_twice():
                    deploy.rollback(destination, state['second']['transaction'], server_stopped=True)
                    result = deploy.rollback(destination, state['second']['transaction'], server_stopped=True)
                    self.assertTrue(result['idempotent'])
                def original():
                    self.assertEqual(self.snapshot(destination / deploy.ACTIVE), state['original'])
                def upgraded():
                    with zipfile.ZipFile(self.two) as archive:
                        self.assertEqual(self.snapshot(destination / deploy.ACTIVE),
                                         {n: archive.read(n) for n in archive.namelist()})
                def profiles():
                    self.assertEqual(save.read_bytes(), b'SYNTHETIC opaque runtime save')
                bindings = {
                    'Given an owned synthetic first installation': install_one,
                    'When the verified second package is upgraded': upgrade,
                    'When the upgrade stops after activation': lambda: crash('activated'),
                    'When the upgrade stops after state commit': lambda: crash('committed'),
                    'And recovery explicitly requests abort': abort,
                    'And its transaction is rolled back twice': rollback_twice,
                    'Then the original package bytes are active': original,
                    'Then the second package bytes are active': upgraded,
                    'And external runtime profile bytes are unchanged': profiles,
                }
                for step in steps:
                    self.assertIn(step, bindings, 'unbound deployment scenario step')
                    bindings[step]()


if __name__ == '__main__':
    unittest.main()
