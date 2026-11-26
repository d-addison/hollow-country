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
        self.assertTrue(restart.verdict('Player connect enabled\n[HC Ready] module=World ready=true', xai=False)['clean'])
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
        line = 'spawn refused: raided site lockout'
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

    def test_stop_client_must_be_gone_before_server_request(self):
        host = Mock()
        host.state.return_value = 'running'
        stager = Mock(server=Path('/unused/server'), client_parent=Path('/unused'))
        campaign = restart.RestartCampaign(stager, host, [], Path('/unused/evidence'), Mock())
        with self.assertRaises(soak.Refused):
            campaign.stop()
        host.stop.assert_called_once_with(soak.CLIENT_IMAGE)

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
                host.clock.return_value = 0
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
                with patch.object(campaign, 'stage'), patch.object(campaign, 'watch', return_value=('', '')):
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

    def test_report_always_targeted_and_unrun_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            restart.write_report(Path(temp), [dict(kind='A', status='unrun')], 'failed')
            report = json.loads((Path(temp) / 'report.json').read_text())
            self.assertTrue(report['targeted'])
            self.assertEqual(report['cycles'][0]['status'], 'unrun')
            self.assertNotIn('release_class', report)


if __name__ == '__main__':
    unittest.main()
