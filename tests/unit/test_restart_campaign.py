"""Offline contracts only: no Windows process, DayZ or native helper is launched."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools.testing import restart_campaign as restart
from tools.testing import soak_campaign as soak


CLEAN = '''Player connect enabled
[HC Ready] module=World enabled=true ready=true
[HC Use] module=World feature=world_read_ok count=1
[HC Use] module=Materializer feature=custody_read_ok count=1
[HC Use] module=LootRefresh feature=intent_read_ok count=1
[HollowCountry] V2 world loaded day=2 places=10 facts=3 factions=2
[HC Materializer] custody_load file=ai-custody.json relocation_depth=0 loaded=true
[HC XAI Bridge] teardown retired_released=3 retained=0
[HC Teardown] shelters_skipped=1 pathgraph_skipped=2 callbacks_removed=3 packs_released=4 rpc_skipped=5
'''


class RestartTests(unittest.TestCase):
    def test_plan_defaults_and_optional_order(self):
        cycles = restart.cycle_plan()
        self.assertEqual([c.kind for c in cycles], ['A', 'A', 'A', 'B', 'B'])
        self.assertEqual(sum(c.minutes for c in cycles), 25)
        cycles = restart.cycle_plan(['world', 'custody'], ['intent'], True)
        self.assertEqual([c.kind for c in cycles[5:]], ['C', 'C', 'D', 'D-readback', 'E'])
        self.assertEqual([c.store for c in cycles[5:8]], ['world', 'custody', 'intent'])
        self.assertGreaterEqual(cycles[7].minutes, 40)
        self.assertFalse(cycles[-1].join)
        self.assertFalse(cycles[-1].xai)
        output = io.StringIO()
        with patch.object(restart, 'WindowsHost', create=True, side_effect=AssertionError):
            self.assertEqual(restart.main(['plan', '--fault-recover', '--no-xai'], out=output), 0)
        self.assertIn('Total planned minutes: 31', output.getvalue())

    def test_driver_uses_existing_steps_and_same_places(self):
        first, later = restart.driver_script(True), restart.driver_script(False, 2)
        self.assertEqual([s['to'] for s in first['steps'] if s['kind'] == 'walk'],
                         [s['to'] for s in later['steps'] if s['kind'] == 'walk'])
        for kind in ('group', 'ping', 'search_site', 'vehicle'):
            self.assertTrue(any(s['kind'] == kind for s in first['steps']))
        self.assertTrue(any(s.get('cmd') == 'fx_site_patrol_kill' for s in first['steps']))
        self.assertFalse(any(s.get('cmd') == 'fx_site_patrol_kill' for s in later['steps']))
        self.assertNotEqual(first['run_id'], later['run_id'])

    def inventories(self):
        return {'@HollowCountry': {'hc': {'dz_scripts'}},
                '@HollowCountryExpansionAI': {'hcx': {'hc', 'dayzexpansion_ai_scripts'}},
                '@HollowCountryTest': {'hctest': {'hcx'}},
                '@ExpansionAI': {'dayzexpansion_ai_scripts': set()},
                '@Other': {'other': {'hc'}}}

    def test_no_xai_mods_and_required_addons_refusal(self):
        inventory = self.inventories()
        self.assertEqual(restart.no_xai_mods(list(inventory), inventory), ['@HollowCountry', '@Other'])
        inventory['@Other']['other'].add('dayzexpansion_ai_scripts')
        with self.assertRaisesRegex(soak.Refused, 'requiredAddons'):
            restart.no_xai_mods(list(inventory), inventory)
        inventory = self.inventories()
        inventory['@Other']['other'].add('hctest')
        with self.assertRaises(soak.Refused):
            restart.no_xai_mods(list(inventory), inventory)
        del inventory['@ExpansionAI']
        with self.assertRaisesRegex(soak.Refused, 'identify'):
            restart.no_xai_mods(list(inventory), inventory)

    def test_installed_pbo_text_config_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            pbo = Path(temp) / 'addon.pbo'
            pbo.touch()
            data = b'class CfgPatches { class One { requiredAddons[]={"Removed"}; }; };'
            with patch('tools.audit.pbo_config.read_pbo_index', return_value={'entries': [{'name': 'config.cpp'}]}), \
                 patch('tools.audit.pbo_config.read_member', return_value=data):
                self.assertEqual(restart.patch_inventory(temp), {'one': {'removed'}})
            pbo.with_suffix('.ebo').touch()
            with self.assertRaises(soak.Refused):
                restart.patch_inventory(temp)

    def test_lock_path_refuses_live_profile_and_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = root / 'soak-profiles'
            (staged / 'HollowCountry').mkdir(parents=True)
            file = staged / 'HollowCountry/world.json'
            file.write_bytes(b'original')
            self.assertEqual(restart.lock_path(staged, 'world'), file.resolve())
            with self.assertRaises(soak.Refused):
                restart.lock_path(root / 'profiles', 'world')
            file.unlink()
            outside = root / 'outside.json'
            outside.write_bytes(b'untouched')
            file.symlink_to(outside)
            with self.assertRaises(soak.Refused):
                restart.lock_path(staged, 'world')
            with self.assertRaises(soak.Refused):
                restart.lock_path(staged, '../world')

    def test_files_use_directory_snapshot_not_mtime(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            old = folder / 'old.rpt'
            old.write_text('old')
            before = restart.snapshot(folder)
            new = folder / 'new.rpt'
            new.write_text('new\n')
            old.write_text('touched after launch\n')
            crash = folder / 'crash_1.log'
            crash.touch()
            dump = folder / 'engine.mdmp'
            dump.touch()
            self.assertEqual(set(restart.launch_files(folder, before)), {new, crash, dump})
            self.assertNotIn('touched', restart.log_text(restart.launch_files(folder, before)))

    def test_verdict_crash_script_vme_teardown_and_counters(self):
        result = restart.verdict(CLEAN)
        self.assertTrue(result['clean'])
        self.assertTrue(all(result['store_reads'].values()))
        self.assertEqual(len(result['store_restores']['custody']), 1)
        for marker in ('0xc0000374', 'Unhandled exception', 'Access violation', 'Exception code: 1'):
            self.assertTrue(restart.verdict(CLEAN + marker)['crash'])
        self.assertTrue(restart.verdict(CLEAN, crash_files=True)['crash'])
        result = restart.verdict(CLEAN, 'SCRIPT (E) failure\nVirtual Machine Exception\n')
        self.assertFalse(result['clean'])
        self.assertEqual((result['script_e'], result['vme']), (1, 1))
        self.assertFalse(restart.verdict(CLEAN + CLEAN)['clean'])
        self.assertFalse(restart.verdict(CLEAN.replace('ready=true', 'ready=false'))['clean'])
        self.assertTrue(restart.verdict(CLEAN.replace('[HC XAI Bridge] teardown retired_released=3 retained=0\n', ''), xai=False)['clean'])
        self.assertFalse(restart.verdict('Player connect enabled\n[HC Ready] module=World enabled=true ready=true', xai=False)['clean'])
        self.assertFalse(restart.verdict('Player connect enabled', xai=False)['clean'])
        result = restart.verdict(CLEAN + '[HC Use] module=World feature=world_read_recovered count=1\n'
                                 '[HC Use] module=World feature=world_save_read_pending count=2\n')
        self.assertEqual(result['counters_woken']['World/world_save_read_pending'], 2)
        self.assertNotIn('World/world_read_retrying', result['counters_woken'])

    def test_fault_quarantine_or_fresh_wins_and_hashes_cover_all_images(self):
        for store, name in restart.STORES.items():
            pending = '[HC Persistence] store=%s read_unavailable\n' % store
            self.assertEqual(restart.fault_observation(pending, store), 'read_unavailable')
            self.assertEqual(restart.fault_observation(
                '[HC Use] module=World feature=%s_read_ok count=1' % store, store), 'FileExist under share-none')
            for suffix in ('action=fresh', 'reason=%s_interrupted_pair' % store, 'action=quarantine'):
                self.assertEqual(restart.fault_observation(pending + '[HC Store] path=' + name + ' ' + suffix, store),
                                 'FileExist under share-none')
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'HollowCountry'
            folder.mkdir()
            (folder / 'world.json.bak').write_bytes(b'backup')
            hashes = restart.store_hashes(temp)
            self.assertEqual(len(hashes), 9)
            self.assertIsNotNone(hashes['world.bak'])
            self.assertIsNone(hashes['world.tmp'])

    def test_lockout_real_utc_boundary(self):
        line = '[HC Expansion AI] site police-chernogorsk spawn refused: raided site lockout'
        self.assertEqual(restart.lockout(1000, 1599, line), 'passed')
        self.assertEqual(restart.lockout(1000, 1600, line), 'not_applicable(elapsed=600)')
        self.assertTrue(restart.lockout(1000, 1100, '').startswith('failed'))
        self.assertIn('unobservable', restart.lockout(None, 1100, line))

    def test_round_trip_is_not_claimed_without_save_evidence(self):
        rows = restart.round_trip({}, restart.verdict(CLEAN))
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(r['status'] == 'unobservable' and r['proposed_line'] for r in rows))
        self.assertIn('places=10', rows[0]['restore'])
        self.assertIsNone(rows[2]['restore'])

    def test_restore_only_when_all_images_and_helper_gone(self):
        stager, host, lock = Mock(state=Path('/nonexistent-restart-test-state')), Mock(), Mock()
        host.state.return_value = 'running'
        with self.assertRaises(soak.Refused):
            restart.restore_when_gone(stager, host, [lock])
        stager.restore.assert_not_called()
        host.state.return_value = 'unknown'
        with self.assertRaises(soak.Refused):
            restart.restore_when_gone(stager, host, [lock])
        host.state.return_value = 'gone'
        lock.gone.return_value = False
        with self.assertRaises(soak.Refused):
            restart.restore_when_gone(stager, host, [lock])
        stager.restore.assert_not_called()
        lock.gone.return_value = True
        restart.restore_when_gone(stager, host, [lock])
        lock.clean_markers.assert_called_once()
        stager.restore.assert_called_once()

    def test_stop_requests_both_games_and_tolerates_lost_reply(self):
        for error in (OSError('lost reply'), restart.InteropError('lost reply'), soak.Refused('refused')):
            host = Mock()
            host.state.return_value = 'gone'
            host.clock.return_value = 0
            host.stop.side_effect = [error, None]
            stager = Mock(server=Path('/unused/server'), client_parent=Path('/unused'))
            campaign = restart.RestartCampaign(stager, host, [], Path('/unused/evidence'), Mock())
            if isinstance(error, soak.Refused):
                with self.assertRaises(soak.Refused):
                    campaign.stop()
            else:
                campaign.stop()
            self.assertEqual([call.args[0] for call in host.stop.call_args_list],
                             [soak.CLIENT_IMAGE, soak.SERVER_IMAGE])
            self.assertEqual([call.args[0] for call in host.state.call_args_list], list(soak.PROCESS_IMAGES))

    def test_lock_helper_has_read_only_share_none_and_finally(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp) / 'soak-profiles'
            (profile / 'HollowCountry').mkdir(parents=True)
            (profile / 'HollowCountry/world.json').touch()
            host = Mock()
            host.clock.return_value = 0
            lock = restart.ReadLock(profile, 'world', host, str)
            process = Mock()
            process.poll.return_value = 0
            captured = []
            def popen(args, **kwargs):
                self.assertTrue(kwargs['start_new_session'])
                captured.extend(args)
                lock.ready.touch()
                lock.closed.touch()
                return process
            with patch.object(restart.subprocess, 'Popen', side_effect=popen):
                lock.start()
            import base64
            encoded = captured[-1].split("FromBase64String('")[1].split("')")[0]
            script = base64.b64decode(encoded).decode('utf-16-le')
            for token in ('FileAccess]::Read', 'FileShare]::None', 'finally', '.Dispose()', 'AddMinutes(75)'):
                self.assertIn(token, script)
            for token in ('Stop-Process', 'taskkill', '.Kill('):
                self.assertNotIn(token, script)
            lock.release()
            lock.clean_markers()
            self.assertTrue(lock.gone())

    def test_campaign_stops_after_crash_or_stop_failure_and_marks_unrun(self):
        for stop_fails in (False, True):
            with self.subTest(stop_fails=stop_fails), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                server = root / 'server'
                profile = server / soak.PROFILE_COPY
                client = root / soak.CLIENT_PROFILE
                (profile / 'HollowCountry').mkdir(parents=True)
                (client / soak.STEP_REL).parent.mkdir(parents=True)
                stager = Mock(server=server, client_parent=root, state=root / 'state', win=str)
                stager.load.return_value = None
                states = dict.fromkeys(soak.PROCESS_IMAGES, 'gone')
                host = Mock()
                host.state.side_effect = lambda image: states[image]
                clock = [0]
                host.clock.side_effect = lambda: clock[0]
                host.sleep.side_effect = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
                def launch(_):
                    states[soak.SERVER_IMAGE] = 'running'
                    text = CLEAN if stop_fails else CLEAN + 'Access violation\n'
                    (profile / 'boot.RPT').write_text(text)
                def stop(image):
                    if stop_fails:
                        raise soak.Refused('graceful close failed')
                    states[image] = 'gone'
                host.launch_server.side_effect = launch
                host.stop.side_effect = stop
                campaign = restart.RestartCampaign(stager, host, [restart.Cycle('B', 5), restart.Cycle('B', 5)],
                                                    root / 'evidence', Mock(), log=Mock())
                with patch.object(campaign, 'stage'), patch.object(campaign, 'validate_launch'), patch.object(campaign, 'watch', return_value=('', '')):
                    self.assertFalse(campaign.run())
                self.assertEqual([r['status'] for r in campaign.rows], ['failed', 'unrun'])
                self.assertEqual(campaign.rows[0]['kind'], 'B')
                self.assertEqual(campaign.rows[0]['crash'], not stop_fails)
                self.assertEqual(campaign.rows[0]['stop'], not stop_fails)
                if stop_fails:
                    stager.restore.assert_not_called()
                    campaign.log.assert_any_call('stop DayZ by hand, then run restore')
                else:
                    stager.restore.assert_called_once()
                self.assertTrue((root / 'evidence/report.json').is_file())

    def test_readiness_last_enabled_module_verdict(self):
        lines = ('[HC Ready] module=AIRoles enabled=true ready=false reason=catalog_loading\n'
                 '[HC Ready] module=Sites enabled=false ready=false\n')
        self.assertFalse(restart.verdict(CLEAN + lines)['ready'])
        lines += '[HC Ready] module=AIRoles enabled=true ready=true\n'
        self.assertTrue(restart.verdict(CLEAN + lines)['clean'])
        self.assertFalse(restart.verdict(CLEAN + lines +
                         '[HC Ready] module=AIRoles enabled=true ready=false')['ready'])

    def test_crash_labels_and_exceptions_in_verdict_and_watch(self):
        for line in ('[HC Tour] label="Incident crash"', '[HC Tour] label="Access violation"',
                     '12:00:00 SCRIPT       : [HC Tour] label="Unhandled exception"'):
            self.assertFalse(restart.verdict(CLEAN + line)['crash'])
        for line in ('0xc0000005', '0xc0000374', 'Unhandled exception', 'Access violation'):
            self.assertTrue(restart.verdict(CLEAN + line)['crash'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stager = Mock(server=root, client_parent=root)
            host = Mock()
            host.clock.return_value = 0
            host.state.return_value = 'running'
            campaign = restart.RestartCampaign(stager, host, [], root / 'evidence', Mock())
            for source in campaign.sources:
                source.mkdir()
            snapshots = [restart.snapshot(p) for p in campaign.sources]
            rpt = campaign.profile / 'boot.rpt'
            rpt.write_text(CLEAN + '[HC Tour] label="Incident crash"\n')
            campaign.rows = [dict(join=False)]
            campaign.watch_paths, campaign.watch_text, campaign.offsets = [[], []], [[], []], {}
            campaign.watch(snapshots, 1, lambda s, c: soak.CONNECT_ENABLED in s)
            with rpt.open('a') as stream:
                stream.write('Unhandled exception 0xc0000005\n')
            with self.assertRaisesRegex(soak.Refused, 'crash'):
                campaign.watch(snapshots, 1)

    def test_fault_hash_boundary_and_recovered_saves(self):
        for kind, probe, changed, should_pass in (
                ('C', False, False, True), ('C', False, True, True),
                ('D', False, True, False), ('probe-lock', True, True, False)):
            with self.subTest(kind=kind, changed=changed), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                stager = Mock(server=root / 'server', client_parent=root, state=root / 'state', win=str)
                host = Mock()
                host.state.return_value = 'gone'
                host.clock.return_value = 0
                campaign = restart.RestartCampaign(stager, host, [], root / 'evidence', Mock(), probe=probe)
                (campaign.profile / 'HollowCountry').mkdir(parents=True)
                (campaign.client / soak.STEP_REL).parent.mkdir(parents=True)
                target = campaign.profile / 'HollowCountry/world.json'
                target.write_bytes(b'original')
                pending = ('[HC Persistence] store=world read_unavailable\n'
                           '[HC Persistence] store=world reason=world_read_retrying attempt=1 action=retry_in_session\n'
                           '[HC Use] module=World feature=world_read_recovered count=1\n'
                           '[HC Use] module=World feature=world_save_read_pending count=1\n')
                lock = Mock(closed_ack=False)
                held = [False]
                def start():
                    held[0] = True
                def release():
                    held[0] = False
                    lock.closed_ack = True
                lock.start.side_effect = start
                lock.release.side_effect = release
                def launch(_):
                    (campaign.profile / 'boot.rpt').write_text(CLEAN + pending)
                host.launch_server.side_effect = launch
                real_hashes = restart.store_hashes
                calls = []
                def hashes(profile):
                    # Windows share-none would raise here if the helper still owned the file.
                    self.assertFalse(held[0])
                    calls.append('hash')
                    return real_hashes(profile)
                def stop():
                    if changed:
                        target.write_bytes(b'legitimate recovered save' if kind == 'C' else b'bad change')
                campaign.stop = stop
                with patch.object(restart, 'ReadLock', return_value=lock), \
                     patch.object(restart, 'store_hashes', side_effect=hashes), \
                     patch.object(campaign, 'validate_launch'), patch.object(campaign, 'watch'), \
                     patch.object(soak.Campaign, 'appear'):
                    if should_pass:
                        campaign.run_cycle(1, restart.Cycle(kind, 5, store='world', fault=True))
                    else:
                        with self.assertRaisesRegex(soak.Refused, 'locked store changed'):
                            campaign.run_cycle(1, restart.Cycle(kind, 40, store='world', fault=True))
                self.assertGreaterEqual(len(calls), 2)
                if kind == 'C':
                    self.assertEqual(campaign.rows[0]['hashes_before'], campaign.rows[0]['hashes_at_unlock'])
                    self.assertEqual(campaign.rows[0]['status'], 'passed')

    def test_helper_pid_query_and_timestamped_lockout(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / 'started'
            marker.write_text('1234')
            with patch.object(restart.winproc, 'run', return_value=Mock(returncode=0, stdout='INFO: No tasks are running')) as query:
                self.assertEqual(restart.helper_state(marker), 'gone')
                self.assertIn('PID eq 1234', query.call_args.args[1])
        from datetime import datetime
        boot = datetime(2026, 11, 26, 12, 0, 0).timestamp()
        death = restart.event_time('12:01:00 [HC Test] fx_site_patrol_kill patrol=police-chernogorsk result=ok', restart.KILL, boot)
        spawn = restart.event_time('12:10:59 [HC Expansion AI] site police-chernogorsk spawn refused: raided site lockout', restart.SPAWN, boot + 300)
        self.assertEqual(spawn - death, 599)
        self.assertEqual(restart.lockout(death, spawn, '[HC Expansion AI] site police-chernogorsk spawn refused: raided site lockout'), 'passed')
        self.assertIn('unobservable', restart.lockout(death, None, ''))
        self.assertTrue(restart.lockout(death, spawn,
            '[HC Expansion AI] DIAGNOSTIC spawn of site police-chernogorsk (police)\n'
            '[HC Expansion AI] site police-chernogorsk spawn refused: raided site lockout').startswith('failed'))

    def test_watch_offsets_transient_errors_and_load_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stager = Mock(server=root, client_parent=root)
            host = Mock()
            clock = [0]
            host.clock.side_effect = lambda: clock[0]
            host.sleep.side_effect = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
            host.state.side_effect = ['unknown', 'running'] + ['running'] * 100
            campaign = restart.RestartCampaign(stager, host, [], root / 'evidence', Mock())
            for folder in campaign.sources:
                folder.mkdir()
            snapshots = [restart.snapshot(p) for p in campaign.sources]
            rpt = campaign.profile / 'boot.rpt'
            rpt.write_text('engine startup\n')
            campaign.rows = [dict(join=False)]
            campaign.watch_paths, campaign.watch_text, campaign.offsets = [[], []], [[], []], {}
            real_tail = soak.tail_lines
            offsets = []
            def tail(path, offset):
                offsets.append(offset)
                if len(offsets) == 1:
                    raise OSError('briefly locked')
                if clock[0] == 6:
                    with rpt.open('a') as stream:
                        stream.write('[HC Ready] module=World enabled=true ready=false\n')
                return real_tail(path, offset)
            with patch.object(soak, 'tail_lines', side_effect=tail), \
                 patch.object(restart, 'launch_files', wraps=restart.launch_files) as discover:
                with self.assertRaisesRegex(soak.Refused, 'deadline'):
                    # Before the first load marker at t=6, this must not expire at t=4.
                    campaign.watch(snapshots, 4, lambda s, c: False, start_on_load=True)
                self.assertEqual(clock[0], 10)
                self.assertEqual(discover.call_count, 1)
            self.assertEqual(offsets[:2], [0, 0])
            self.assertGreater(offsets[-1], 0)

    def test_launch_replacements_must_match(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stager = Mock(server=root, client_parent=root, mission=Path('dayzOffline.chernarusplus'))
            campaign = restart.RestartCampaign(stager, Mock(), [], root / 'evidence', Mock())
            bat = root / soak.BAT_COPY
            config = root / soak.CFG_COPY
            good = '-config=%s -profiles=%s "-mod=@HollowCountry;%s"' % (soak.CFG_COPY, soak.PROFILE_COPY, soak.TEST_MOD)
            bat.write_text(good)
            config.write_text('template="dayzOffline.chernarusplus";')
            campaign.validate_launch(restart.Cycle('A', 5))
            bat.write_text(good.replace(soak.CFG_COPY, 'serverDZ.cfg'))
            with self.assertRaisesRegex(soak.Refused, 'start-bat'):
                campaign.validate_launch(restart.Cycle('A', 5))
            bat.write_text(good)
            config.write_text('template="wrong.chernarusplus";')
            with self.assertRaisesRegex(soak.Refused, 'template'):
                campaign.validate_launch(restart.Cycle('A', 5))

    def test_restore_without_closed_marker_checks_windows_pid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            hc = root / soak.PROFILE_COPY / 'HollowCountry'
            hc.mkdir(parents=True)
            (hc / 'restart-lock.started').write_text('1234')
            host = Mock()
            host.state.return_value = 'gone'
            stager = Mock(state=root / 'state')
            with patch.object(restart, 'host_lock'), patch.object(soak, 'local_roots', return_value=(root, root)), \
                 patch.object(soak, 'Stager', return_value=stager), \
                 patch.object(restart, 'helper_state', return_value='gone') as state:
                self.assertEqual(restart.main(['restore'], host=host, out=io.StringIO()), 0)
                state.assert_called_once_with(hc / 'restart-lock.started')
                stager.restore.assert_called_once()

    def test_run_preserves_probe_evidence_and_receipts_include_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_dir = root / 'state'
            probe = state_dir / 'probes' / 'world'
            probe.mkdir(parents=True)
            (probe / 'report.json').write_text('native proof')
            host = Mock()
            host.state.return_value = 'gone'
            stager = Mock()
            campaign = Mock()
            campaign.run.return_value = True
            sha = 'a' * 40
            with patch.object(restart, 'STATE', state_dir), patch.object(restart, 'host_lock'), \
                 patch.object(soak, 'local_roots', return_value=(root, root)), \
                 patch.object(soak, 'Stager', return_value=stager), \
                 patch.object(restart, 'commit_sha', return_value=sha), \
                 patch.object(restart, 'RestartCampaign', return_value=campaign) as factory:
                self.assertEqual(restart.main(['probe-lock', '--yes'], host=host, out=io.StringIO()), 0)
                receipt = state_dir / 'probes/probe-world.json'
                self.assertEqual(json.loads(receipt.read_text()), dict(passed=True, commit_sha=sha))
                self.assertEqual(factory.call_args.args[3], probe)
                self.assertEqual(restart.main(['run', '--yes'], host=host, out=io.StringIO()), 0)
                self.assertEqual(factory.call_args.args[3], state_dir / 'last-run')
                self.assertEqual((probe / 'report.json').read_text(), 'native proof')
                self.assertTrue(receipt.is_file())

    def test_report_always_targeted_and_unrun_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            restart.write_report(Path(temp), [dict(kind='A', status='unrun')], 'failed')
            report = json.loads((Path(temp) / 'report.json').read_text())
            self.assertTrue(report['targeted'])
            self.assertEqual(report['cycles'][0]['status'], 'unrun')
            self.assertNotIn('release_class', report)


if __name__ == '__main__':
    unittest.main()
