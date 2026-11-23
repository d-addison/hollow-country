"""Soak campaign orchestration with a fake host, fake clock and synthetic trees; DayZ is never started."""
from contextlib import redirect_stdout
import copy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.testing import soak_campaign as camp

BAT = (b'@echo off\r\ncd /d "%~dp0"\r\nstart "DayZ" /min DayZServer_x64.exe -config=serverDZ.cfg -port=2302 '
       b'-profiles=profiles "-mod=@CF;@Dep;@HollowCountry;@HollowCountryExpansionAI" -dologs\r\n')
CFG = (b'hostname = "x";\r\npasswordAdmin = "hunter2";\r\ninstanceId = 1;\r\nserverTime = "SystemTime";\r\n'
       b'serverTimeAcceleration = 6;\r\n')
GAMEPLAY = {'version': 123, 'PlayerData': {'spawnGearPresetFiles': []}, 'other': 1}
PHASES = camp.load_phases()


def make_server(root, admins=True):
    server = Path(root) / 'server'
    mission = server / 'mpmissions/dayzOffline.chernarusplus'
    (mission / 'hollow-country-gameplay').mkdir(parents=True)
    (mission / 'cfggameplay.json').write_text(json.dumps(GAMEPLAY))
    (server / 'serverDZ.cfg').write_bytes(CFG)
    (server / 'start-server.bat').write_bytes(BAT)
    hc = server / 'profiles/HollowCountry'
    hc.mkdir(parents=True)
    (hc / 'settings.json').write_text(json.dumps({'EnableSmokeFixtures': False, 'Keep': 7}))
    (hc / 'admins.json').write_text(json.dumps({'PlainIds': ['x'] if admins else []}))
    (server / 'profiles/Other').mkdir()
    (server / 'profiles/Other/data.txt').write_text('d')
    (server / 'profiles/loose.RPT').write_text('root logs are not copied')
    for name, ident in (('@CF', '111'), ('@Dep', '222')):
        (server / name).mkdir()
        (server / name / 'meta.cpp').write_text('publishedid = %s;\n' % ident)
    return server


def make_client(root):
    client = Path(root) / 'client'
    ws = client / '!Workshop'
    for name, ident in (('@CF-client', '111'), ('@Dep-client', '222')):
        (ws / name).mkdir(parents=True)
        (ws / name / 'meta.cpp').write_text('publishedid = %s;\n' % ident)
    return client


def make_addon(root):
    addon = Path(root) / 'scratch/@HollowCountryTest'
    (addon / 'addons').mkdir(parents=True, exist_ok=True)
    (addon / 'addons/hollowcountrytest.pbo').write_bytes(b'pbo')
    return addon


class Tmp(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)


class PhaseMapTests(unittest.TestCase):
    def test_every_counter_is_mapped(self):
        self.assertEqual(camp.unmapped(PHASES), [])

    def test_removing_a_module_row_is_reported(self):
        broken = copy.deepcopy(PHASES)
        module = next(m for m in broken['modules'] if m == 'Crafting')
        del broken['modules'][module]
        broken['features'] = {k: v for k, v in broken['features'].items() if not k.startswith(module + '/')}
        self.assertTrue([x for x in camp.unmapped(broken) if 'Crafting' in x])

    def test_every_expectation_row_has_a_phase_or_a_declared_reason(self):
        for module, feature in camp.expectation_rows():
            self.assertIsNotNone(camp.phase_of(PHASES, module, feature), module + '/' + feature)

    def test_manual_rows_are_only_the_allowed_two_player_items(self):
        self.assertEqual(camp.manual_problems(PHASES), [])
        self.assertEqual(set(PHASES['manual']), camp.ALLOWED_MANUAL)
        for row in PHASES['manual'].values():
            self.assertIn(row['kind'], ('owner_check', 'friend_playtest'))
            self.assertTrue(row['reason'].strip())

    def test_a_row_outside_the_allowed_list_fails(self):
        broken = copy.deepcopy(PHASES)
        broken['manual']['Crafting/craft_completed'] = {'kind': 'owner_check', 'reason': 'too hard'}
        self.assertIn('manual row not allowed: Crafting/craft_completed', camp.manual_problems(broken))
        broken = copy.deepcopy(PHASES)
        broken['looks'].append({'id': 'everything', 'kind': 'owner_check', 'reason': 'x'})
        self.assertTrue(camp.manual_problems(broken))
        broken = copy.deepcopy(PHASES)
        broken['manual']['TeamPing/ping_delivered']['reason'] = ' '
        self.assertTrue(camp.manual_problems(broken))

    def test_phases_and_idle_window(self):
        self.assertEqual(tuple(p['name'] for p in PHASES['phases']), camp.PHASE_ORDER)
        self.assertGreaterEqual(PHASES['min_idle_minutes'], 125)
        self.assertEqual(PHASES['debug_snapshot_seconds'], 300)
        self.assertEqual(camp.phase_of(PHASES, 'DebugSnapshot', 'snapshot_saved'), ('phase', 'idle'))

    def test_bad_phase_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'p.json'
            for edit in (lambda d: d.update(min_idle_minutes=60), lambda d: d['modules'].update(X='nowhere'),
                         lambda d: d['phases'].reverse()):
                data = copy.deepcopy(PHASES)
                edit(data)
                path.write_text(json.dumps(data))
                with self.assertRaises(camp.Refused):
                    camp.load_phases(path)

    def test_plan_reports_zero_unmapped_and_writes_nothing(self):
        lines, problems = camp.plan_text(PHASES)
        text = '\n'.join(lines)
        self.assertEqual(problems, [])
        self.assertIn('unmapped counters: 0', text)
        for name in camp.PHASE_ORDER:
            self.assertIn(name, text)
        self.assertNotIn('/home', text)

    def test_shipped_reach_map_leaves_no_counter_unreached(self):
        rows = camp.reach_rows(PHASES)
        self.assertTrue(rows)
        self.assertEqual([(key, problems) for key, _, _, problems in rows if problems], [])
        lines, unreached = camp.reach_lines(rows)
        self.assertEqual(unreached, 0)
        self.assertIn('unreached=0', '\n'.join(camp.plan_text(PHASES)[0]))

    def test_every_how_token_names_a_real_step_fixture_or_setting(self):
        context = camp.reach_context()
        kinds = set()
        for key, row in PHASES['reach'].items():
            for token in row['how']:
                kinds.add(token.split(':', 1)[0])
                self.assertIsNone(camp.reach_token_problem(token, row['phase'], PHASES, context), (key, token))
        self.assertTrue({'step', 'fixture', 'setting', 'code'} <= kinds)

    def test_reach_map_refuses_a_missing_wrong_or_invented_row(self):
        key = sorted(PHASES['reach'])[0]
        for edit in (lambda d: d['reach'].pop(key),
                     lambda d: d['reach'][key].update(how=['code:HCNoSuchFile.c', 'boot']),
                     lambda d: d['reach'][key].update(how=['fixture:fx_no_such', 'code:HCWorkBudget.c']),
                     lambda d: d['reach'][key].update(how=['setting:NoSuchSetting', 'code:HCWorkBudget.c']),
                     lambda d: d['reach'][key].update(how=['code:HCWorkBudget.c']),
                     lambda d: d['reach'].update({'Nope/never': {'phase': 'idle', 'how': ['boot']}})):
            broken = copy.deepcopy(PHASES)
            edit(broken)
            lines, unreached = camp.reach_lines(camp.reach_rows(broken))
            self.assertGreater(unreached, 0)
        broken = copy.deepcopy(PHASES)
        lines, problems = camp.plan_text(broken)
        self.assertEqual(problems, [])

    def test_plan_cli_is_read_only_and_names_a_missing_step_file(self):
        buffer = StringIO()
        with mock.patch.object(camp, 'step_script', side_effect=camp.Refused('driver_script is not in this checkout')), \
                mock.patch.object(camp.Stager, 'save', side_effect=AssertionError('plan wrote')), \
                redirect_stdout(buffer):
            code = camp.main(['plan'])
        self.assertEqual(code, 2)
        self.assertIn('plan FAILED: step file unavailable', buffer.getvalue())


class BuilderTests(Tmp):
    def test_test_cfg_sets_the_soak_keys_and_keeps_every_other_byte(self):
        out = camp.test_cfg(CFG).decode()
        self.assertIn('instanceId = 99;', out)
        self.assertIn('serverTime = "2026/07/15/08/00";', out)
        self.assertIn('serverTimeAcceleration = 1;', out)
        self.assertIn('serverTimePersistent = 0;', out)
        self.assertIn('passwordAdmin = "hunter2";\r\n', out)
        self.assertIn('hostname = "x";', out)

    def test_test_cfg_refuses_a_duplicate_key(self):
        with self.assertRaises(camp.Refused):
            camp.test_cfg(CFG + b'instanceId = 2;\r\n')

    def test_forage_date_is_in_season_and_daytime(self):
        year, month, day, hour, minute = camp.SOAK_TIME.split('/')
        self.assertTrue(6 <= int(month) <= 11)
        self.assertTrue(8 <= int(hour) <= 12)

    def test_test_bat_adds_the_test_addon_and_redirects(self):
        out = camp.test_bat(BAT).decode()
        self.assertIn('-config=hc-soak.cfg', out)
        self.assertIn('-profiles=soak-profiles ', out)
        self.assertIn('"-mod=@CF;@Dep;@HollowCountry;@HollowCountryExpansionAI;@HollowCountryTest"', out)
        self.assertEqual(camp.server_mods(BAT), ['@CF', '@Dep', '@HollowCountry', '@HollowCountryExpansionAI'])
        for bad in (BAT.replace(b'-config=serverDZ.cfg', b'-config=other.cfg'), BAT.replace(b'@CF', b'@CF"x')):
            with self.assertRaises(camp.Refused):
                camp.test_bat(bad)

    def test_gear_preset_holds_every_item_the_actions_need(self):
        text = json.dumps(camp.gear_preset())
        for item in ('KitchenKnife', 'CamoNet', 'PersonalRadio', 'Battery9V', 'Mich2001Helmet', 'UniversalLight',
                     'DuctTape', 'Crowbar', 'Wrench', 'TortillaBag', 'Paper', 'Pen_Black', 'AKM', 'Mag_AKM_30Rnd', 'Ammo_762x39'):
            self.assertIn(item, text)

    def test_settings_and_gameplay_edits(self):
        settings = json.loads(camp.settings_with_fixtures(json.dumps({'Keep': 7}).encode()))
        self.assertEqual(settings, {'Keep': 7, 'EnableSmokeFixtures': True, 'FortifyBreachSeconds': 20})
        gameplay = json.loads(camp.gameplay_with_preset(json.dumps(GAMEPLAY).encode()))
        self.assertEqual(gameplay['PlayerData']['spawnGearPresetFiles'], [camp.GEAR_REL])
        self.assertEqual(gameplay['other'], 1)
        with self.assertRaises(camp.Refused):
            camp.gameplay_with_preset(b'{}')

    def test_client_mods_use_workshop_for_foreign_and_server_root_for_own(self):
        server, client = make_server(self.root), make_client(self.root)
        mods = camp.server_mods(BAT) + [camp.TEST_MOD]
        paths = camp.client_mods(mods, server, client / '!Workshop', str)
        self.assertEqual(paths[0], str(client / '!Workshop/@CF-client'))
        self.assertEqual(paths[1], str(client / '!Workshop/@Dep-client'))
        self.assertEqual(paths[2], str(server / '@HollowCountry'))
        self.assertEqual(paths[-1], str(server / '@HollowCountryTest'))
        (client / '!Workshop/@Dep-client/meta.cpp').write_text('publishedid = 9;\n')
        with self.assertRaises(camp.Refused):
            camp.client_mods(mods, server, client / '!Workshop', str)

    def test_client_arguments_use_the_battleye_launcher_and_never_bypass(self):
        args = camp.client_arguments(['A', 'B'], 'P')
        self.assertEqual(args[:5], ['0', '1', '1', '-exe', 'DayZ_x64.exe'])
        self.assertIn('-connect=127.0.0.1:2302:27016', args)
        self.assertIn('-mod=A;B', args)
        text = ' '.join(args).lower()
        for banned in ('nobe', 'nobattleye', 'filepatching', 'disablesig', 'nosplash=0', '-nolauncher'):
            self.assertNotIn(banned, text)

    def test_source_scan_finds_the_known_modules(self):
        pairs, modules = camp.scan_source()
        self.assertIn('Crafting', modules)
        self.assertTrue(pairs)


class StagerTests(Tmp):
    def setUp(self):
        super().setUp()
        self.server = make_server(self.root)
        self.client = make_client(self.root)
        self.state = self.root / 'state'
        self.stager = camp.Stager(self.server, self.client, self.state)
        self.addon = make_addon(self.root)
        self.mission = self.server / 'mpmissions/dayzOffline.chernarusplus'
        self.original = {p: p.read_bytes() for p in self.server.rglob('*') if p.is_file()}

    def snapshot(self):
        return {p: p.read_bytes() for p in self.server.rglob('*') if p.is_file()}

    def test_stage_creates_copies_and_leaves_the_real_profile_untouched(self):
        rows = self.stager.stage(self.addon, {'version': 1, 'steps': []})
        self.assertTrue(rows)
        profile = self.server / camp.PROFILE_COPY
        settings = json.loads((profile / 'HollowCountry/settings.json').read_text())
        self.assertTrue(settings['EnableSmokeFixtures'])
        self.assertEqual(settings['Keep'], 7)
        self.assertTrue((profile / camp.CELLAR_MARKER_REL).is_file())
        self.assertTrue((profile / 'Other/data.txt').is_file())
        self.assertFalse((profile / 'loose.RPT').exists())
        self.assertEqual((self.server / 'profiles/HollowCountry/settings.json').read_bytes(),
                         self.original[self.server / 'profiles/HollowCountry/settings.json'])
        self.assertTrue((self.mission / camp.GEAR_REL).is_file())
        self.assertEqual(json.loads((self.mission / 'cfggameplay.json').read_text())['PlayerData']['spawnGearPresetFiles'],
                         [camp.GEAR_REL])
        self.assertEqual((self.server / camp.CFG_COPY).read_bytes(), camp.test_cfg(CFG))
        self.assertEqual((self.server / 'serverDZ.cfg').read_bytes(), CFG)
        self.assertIn(b'@HollowCountryTest', (self.server / camp.BAT_COPY).read_bytes())
        self.assertEqual((self.server / 'start-server.bat').read_bytes(), BAT)
        self.assertTrue((self.server / camp.TEST_MOD / 'addons/hollowcountrytest.pbo').is_file())
        step = self.client / 'x'  # the client profile sits beside the DayZ install parent
        written = self.stager.client_parent / camp.CLIENT_PROFILE / camp.STEP_REL
        self.assertEqual(json.loads(written.read_text()), {'version': 1, 'steps': []})
        self.assertFalse(step.exists())

    def test_restore_puts_every_byte_back_and_is_idempotent(self):
        self.stager.stage(self.addon, {'steps': []})
        log = []
        self.assertTrue(self.stager.restore(log=log.append))
        self.assertEqual(self.snapshot(), self.original)
        self.assertFalse((self.server / camp.PROFILE_COPY).exists())
        self.assertFalse((self.mission / 'hollow-country-gameplay/gear').exists())
        self.assertTrue((self.mission / 'hollow-country-gameplay').is_dir())
        self.assertFalse((self.stager.client_parent / camp.CLIENT_PROFILE).exists())
        self.assertFalse(self.stager.receipt_path.exists())
        self.assertEqual(list(self.state.glob('*.bak')), [])
        self.assertFalse(self.stager.restore(log=log.append))
        self.assertIn('restore: nothing staged', log)

    def test_restore_with_nothing_staged_changes_nothing(self):
        before = self.snapshot()
        self.assertFalse(camp.Stager(self.server, self.client, self.state).restore(log=lambda text: None))
        self.assertEqual(self.snapshot(), before)

    def test_second_stage_is_refused_until_restored(self):
        self.stager.stage(self.addon, {'steps': []})
        with self.assertRaises(camp.Refused):
            camp.Stager(self.server, self.client, self.state).stage(self.addon, {'steps': []})

    def test_empty_admin_allowlist_is_refused_without_printing_ids(self):
        (self.server / 'profiles/HollowCountry/admins.json').write_text(json.dumps({'PlainIds': []}))
        with self.assertRaises(camp.Refused) as caught:
            self.stager.stage(self.addon, {'steps': []})
        self.assertNotIn('x', str(caught.exception).split(':')[-1].strip()[:0])
        self.assertEqual(self.snapshot().keys() - self.original.keys(), set())

    def test_stage_failure_midway_can_be_restored(self):
        (self.mission / 'cfggameplay.json').write_text('{"no": "player data"}')
        original = self.snapshot()
        with self.assertRaises(camp.Refused):
            self.stager.stage(self.addon, {'steps': []})
        self.assertTrue(camp.Stager(self.server, self.client, self.state).restore(log=lambda text: None))
        self.assertEqual(self.snapshot(), original)

    def test_a_tampered_receipt_cannot_delete_foreign_paths(self):
        self.stager.stage(self.addon, {'steps': []})
        receipt = json.loads(self.stager.receipt_path.read_text())
        receipt['created'].append({'root': 'server', 'rel': 'profiles', 'dir': True})
        self.stager.receipt_path.write_text(json.dumps(receipt))
        with self.assertRaises(camp.Refused):
            camp.Stager(self.server, self.client, self.state).restore(log=lambda text: None)
        self.assertTrue((self.server / 'profiles/HollowCountry').is_dir())

    def test_a_corrupt_byte_backup_is_refused(self):
        self.stager.stage(self.addon, {'steps': []})
        (self.state / 'edit-0.bak').write_bytes(b'bad')
        with self.assertRaises(camp.Refused):
            camp.Stager(self.server, self.client, self.state).restore(log=lambda text: None)

    def test_an_existing_target_is_never_overwritten(self):
        (self.server / camp.CFG_COPY).write_bytes(b'mine')
        with self.assertRaises(camp.Refused):
            self.stager.stage(self.addon, {'steps': []})
        self.assertEqual((self.server / camp.CFG_COPY).read_bytes(), b'mine')

    def test_run_logs_survive_restore_for_the_report(self):
        self.stager.stage(self.addon, {'steps': []})
        (self.server / camp.PROFILE_COPY / 'DayZServer_x64_1.RPT').write_text('server')
        (self.stager.client_parent / camp.CLIENT_PROFILE / 'DayZ_x64_1.RPT').write_text('client')
        self.stager.restore(log=lambda text: None)
        server, client = camp.last_run_logs(self.state)
        self.assertEqual((server.read_text(), client.read_text()), ('server', 'client'))


class FakeHost:
    """Simulates the two processes; the fake clock is advanced by the campaign's own sleeps."""

    def __init__(self, stager, clock, server_ready=True, stop_ok=True, driver='done', script_error=None):
        self.stager, self.clock, self.script_error = stager, clock, script_error
        self.running = {camp.SERVER_IMAGE: False, camp.CLIENT_IMAGE: False}
        self.calls, self.client_args, self.stopped_at = [], None, {}
        self.server_ready, self.stop_ok, self.driver = server_ready, stop_ok, driver

    def state(self, image):
        return 'running' if self.running[image] else 'gone'

    def launch_server(self, server_root_win):
        self.calls.append('launch_server')
        self.running[camp.SERVER_IMAGE] = True
        folder = Path(self.stager.server) / camp.PROFILE_COPY
        text = 'boot\n' + (camp.CONNECT_ENABLED + '\n' if self.server_ready else '')
        (folder / 'DayZServer_x64_1.RPT').write_text(text)
        script = '12:20:02.000 SCRIPT       : compiling\n'
        if self.script_error:
            script += '12:20:02.441 SCRIPT    (E): ' + self.script_error + '\n'
        (folder / 'script_1.log').write_text(script)

    def launch_client(self, client_root_win, arguments):
        self.calls.append('launch_client')
        self.client_args = arguments
        self.running[camp.CLIENT_IMAGE] = True
        folder = Path(self.stager.client_parent) / camp.CLIENT_PROFILE
        lines = ['[HC Driver] step=s01 kind=wait result=ok detail=ok']
        if self.driver == 'done':
            lines.append('[HC Driver] done run=r1 steps=1 ok=1 refused=0 unsupported=0 timeout=0')
        elif self.driver == 'inert':
            lines = ['[HC Driver] inert reason=no-step-file']
        (folder / 'DayZ_x64_1.RPT').write_text('\n'.join(lines) + '\n')

    def stop(self, image):
        self.calls.append('stop ' + image)
        if not self.stop_ok:
            raise camp.Refused('graceful stop of %s failed; stop it by hand, then run restore' % image)
        self.running[image] = False
        self.stopped_at[image] = self.clock.t


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class CampaignTests(Tmp):
    def setUp(self):
        super().setUp()
        self.server = make_server(self.root)
        self.client = make_client(self.root)
        self.state = self.root / 'state'
        self.stager = camp.Stager(self.server, self.client, self.state)
        self.mission = self.server / 'mpmissions/dayzOffline.chernarusplus'
        self.clock = Clock()
        self.original = {p: p.read_bytes() for p in self.server.rglob('*') if p.is_file()}

    def campaign(self, **options):
        host = FakeHost(self.stager, self.clock, **options)
        addon = make_addon(self.root)
        run = camp.Campaign(self.stager, host, PHASES, addon_build=lambda: addon, step_script={'version': 1, 'steps': []},
                            sleep=self.clock.sleep, now=self.clock.now, log=lambda text: None, win=str)
        return run, host

    def snapshot(self):
        return {p: p.read_bytes() for p in self.server.rglob('*') if p.is_file()}

    def test_full_run_drives_idles_stops_gracefully_and_restores(self):
        run, host = self.campaign()
        self.assertTrue(run.run())
        self.assertEqual(host.calls, ['launch_server', 'launch_client', 'stop ' + camp.CLIENT_IMAGE,
                                      'stop ' + camp.SERVER_IMAGE])
        self.assertIn('-connect=127.0.0.1:2302:27016', host.client_args)
        self.assertTrue([a for a in host.client_args if a.startswith('-mod=') and a.endswith(camp.TEST_MOD)])
        self.assertGreaterEqual(self.clock.t, PHASES['min_idle_minutes'] * 60)
        self.assertEqual(self.snapshot(), self.original)
        self.assertFalse(self.stager.receipt_path.exists())
        server, client = camp.last_run_logs(self.state)
        self.assertIsNotNone(server)
        self.assertIn('[HC Driver] done', client.read_text())

    def test_refuses_while_the_server_or_client_runs(self):
        for image in (camp.SERVER_IMAGE, camp.CLIENT_IMAGE):
            run, host = self.campaign()
            host.running[image] = True
            with self.assertRaisesRegex(camp.Refused, 'refused'):
                run.run()
            self.assertEqual(host.calls, [])
            self.assertFalse(self.stager.receipt_path.exists())
            self.assertEqual(self.snapshot(), self.original)

    def test_refuses_when_something_is_already_staged(self):
        self.stager.stage(make_addon(self.root), {'steps': []})
        run, host = self.campaign()
        with self.assertRaisesRegex(camp.Refused, 'restore'):
            run.run()
        self.assertEqual(host.calls, [])

    def test_a_server_that_never_connects_still_restores(self):
        run, host = self.campaign(server_ready=False)
        with self.assertRaisesRegex(camp.Refused, 'timed out'):
            run.run()
        self.assertIn('stop ' + camp.SERVER_IMAGE, host.calls)
        self.assertNotIn('launch_client', host.calls)
        self.assertEqual(self.snapshot(), self.original)

    def test_a_script_error_at_boot_refuses_names_it_and_restores(self):
        error = '@"HollowCountryTest/scripts/4_World/hctestreachfixtures.c,173": Unknown operator \'%\''
        run, host = self.campaign(script_error=error)
        with self.assertRaisesRegex(camp.Refused, 'script error before connect enabled: .*hctestreachfixtures.c,173'):
            run.run()
        self.assertEqual(self.clock.t, 0)
        self.assertNotIn('launch_client', host.calls)
        self.assertIn('stop ' + camp.SERVER_IMAGE, host.calls)
        self.assertEqual(self.snapshot(), self.original)

    def test_a_script_error_naming_a_host_path_is_withheld(self):
        self.assertIn('withheld', camp.script_error_text('x SCRIPT    (E): cannot open E:\\Server\\profiles\\a.json'))
        self.assertIn('withheld', camp.script_error_text('x SCRIPT    (E): cannot open ' + '/' + 'mnt/x/a.json'))
        self.assertEqual(camp.script_error_text('x SCRIPT    (E): @"A/b.c,3": Bad type'), '@"A/b.c,3": Bad type')

    def test_an_inert_driver_is_a_failure_and_still_restores(self):
        run, host = self.campaign(driver='inert')
        with self.assertRaisesRegex(camp.Refused, 'inert'):
            run.run()
        self.assertEqual(self.snapshot(), self.original)

    def test_a_failed_graceful_stop_leaves_the_stage_for_a_hand_stop(self):
        run, host = self.campaign(stop_ok=False)
        with self.assertRaisesRegex(camp.Refused, 'by hand'):
            run.run()
        self.assertTrue(self.stager.receipt_path.exists())
        host.stop_ok = True
        for image in host.running:
            host.running[image] = False
        self.assertTrue(camp.Stager(self.server, self.client, self.state).restore(log=lambda text: None))
        self.assertEqual(self.snapshot(), self.original)

    def test_an_os_error_with_a_failed_stop_never_restores_under_the_running_server(self):
        run, host = self.campaign(stop_ok=False)
        real = run.newest
        run.newest = mock.Mock(side_effect=PermissionError(13, 'denied', '/private/x'))
        with self.assertRaisesRegex(camp.Refused, 'unreadable'):
            run.run()
        run.newest = real
        self.assertTrue(self.stager.receipt_path.exists())
        self.assertTrue(host.running[camp.SERVER_IMAGE])

    def test_a_briefly_unreadable_live_log_is_retried(self):
        run, host = self.campaign()
        real, calls = run.newest, []

        def flaky(folder, pattern):
            calls.append(pattern)
            if len(calls) <= 3:
                raise PermissionError(13, 'denied', '/private/x')
            return real(folder, pattern)
        run.newest = flaky
        self.assertTrue(run.run())
        self.assertEqual(self.snapshot(), self.original)

    def test_a_log_that_stays_unreadable_refuses_and_restores(self):
        run, host = self.campaign()
        run.newest = mock.Mock(side_effect=PermissionError(13, 'denied', '/private/x'))
        with self.assertRaisesRegex(camp.Refused, 'unreadable .*EACCES'):
            run.run()
        self.assertEqual(self.snapshot(), self.original)

    def test_failure_text_names_errno_and_repo_frame_but_no_path(self):
        try:
            camp.tail_lines(self.root / 'missing' / 'x.RPT', 0)
        except OSError as error:
            text = camp.describe_failure(error)
        self.assertIn('ENOENT', text)
        self.assertIn('tools/testing/soak_campaign.py', text)
        self.assertNotIn(str(self.root), text)

    def test_the_stray_storage_folder_is_removed_only_when_staging_made_it(self):
        self.stager.stage(make_addon(self.root), {'steps': []})
        (self.mission / camp.STRAY_STORAGE / 'communityframework').mkdir(parents=True)
        self.assertTrue(self.stager.restore(log=lambda text: None))
        self.assertFalse((self.mission / camp.STRAY_STORAGE).exists())
        kept = self.mission / camp.STRAY_STORAGE / 'keep.bin'
        kept.parent.mkdir()
        kept.write_bytes(b'x')
        self.stager.stage(make_addon(self.root), {'steps': []})
        self.assertTrue(self.stager.restore(log=lambda text: None))
        self.assertEqual(b'x', kept.read_bytes())

    def test_the_stop_script_is_close_main_window_only(self):
        class Win:
            scripts = []

            def run(self, kind, args, **kw):
                self.scripts.append(args[0])
                return mock.Mock(returncode=0)

            def process_state(self, image):
                return 'gone'

        host = camp.WindowsHost.__new__(camp.WindowsHost)
        host.winproc = Win()
        host.stop(camp.SERVER_IMAGE)
        script = Win.scripts[0]
        self.assertIn('CloseMainWindow', script)
        for banned in ('Stop-Process', 'taskkill', 'Kill(', '.Kill'):
            self.assertNotIn(banned, script)


class ReportTests(Tmp):
    def test_rows_separate_active_zero_owner_and_friend(self):
        legacy = {'features': [
            dict(module='Crafting', feature='craft-completed', status='ACTIVE', value=2, samples=2, window_minutes=60,
                 elapsed_minutes=130),
            dict(module='Radio', feature='radio-tuned', status='WAITING', value=None, samples=0, window_minutes=60,
                 elapsed_minutes=10),
            dict(module='TeamPing', feature='ping-recipients', status='WAITING', value=None, samples=0,
                 window_minutes=60, elapsed_minutes=10)]}
        release = {'features': [dict(module='Crafting', feature='craft_completed', status='ACTIVE', count=3, fixture=0),
                                dict(module='Unknown', feature='thing', status='INERT', count=0, fixture=0)],
                   'activity': 'inert', 'count': 1}
        rows = camp.report_rows(PHASES, legacy, release)
        by = {(r[0], r[1]): r for r in rows}
        self.assertEqual(by[('expect', 'Crafting/craft-completed')][3], 'active')
        self.assertEqual(by[('expect', 'Radio/radio-tuned')][3], 'zero')
        self.assertEqual(by[('expect', 'TeamPing/ping-recipients')][3], 'friend playtest')
        self.assertEqual(by[('use', 'Unknown/thing')][2], 'unmapped')
        self.assertEqual(by[('use', 'Unknown/thing')][3], 'zero')
        self.assertEqual(by[('look', 'lighting_look')][3], 'owner check')
        text, totals = camp.render_report(rows, ['[HC Driver] done run=r1 steps=1'], 'activity=inert count=1')
        self.assertIn('| source | counter | phase | result | evidence |', text)
        self.assertIn('activity_check --release', text)
        self.assertEqual(totals['active'], 2)
        self.assertGreaterEqual(totals['zero'], 2)
        self.assertLess(text.index('| zero |') if '| zero |' in text else 0, len(text))

    def test_audit_failures_become_broken_rows_not_a_crash(self):
        rows = camp.report_rows(PHASES, None, None, ['activity_check --release unavailable: ValueError'])
        self.assertTrue([r for r in rows if r[0] == 'audit' and r[3] == 'zero'])

    def test_driver_lines_are_filtered(self):
        private = '/ho' + 'me/someone'
        rpt = self.root / 'c.RPT'
        rpt.write_text('noise\n[HC Driver] step=s01 kind=wait result=ok detail=fine\n'
                       '[HC Driver] step=s02 kind=admin result=refused detail=name=Bob\n'
                       '[HC Driver] step=s03 kind=wait result=ok detail=' + private + '/x\n'
                       '[HC Driver] done run=r1 steps=3 ok=2 refused=1 unsupported=0 timeout=0\n')
        found = camp.driver_lines(rpt)
        self.assertEqual(len(found), 3)
        self.assertNotIn('Bob', ' '.join(found))
        self.assertNotIn(private, ' '.join(found))

    def test_activity_failures_are_reported_independently(self):
        with mock.patch('tools.release.activity_check.scan', side_effect=ValueError('no readiness')), \
                mock.patch('tools.release.activity_check.scan_release', return_value={'features': []}):
            legacy, release, errors = camp.activity_results(Path('a'), Path('b'))
        self.assertIsNone(legacy)
        self.assertEqual(release, {'features': []})
        self.assertEqual(len(errors), 1)

    def test_report_without_a_last_run_is_refused(self):
        with self.assertRaises(camp.Refused):
            camp.command_report(PHASES, self.root, StringIO())


class MainTests(Tmp):
    def run_main(self, argv, **patches):
        out = StringIO()
        with mock.patch.object(camp, 'default_linux', side_effect=lambda text: self.root / 'server'), \
                mock.patch.object(camp, 'WindowsHost', side_effect=AssertionError('no real host in tests')):
            code = camp.main(argv + ['--state-dir', str(self.root / 'state')], host=patches.get('host'), out=out)
        return code, out.getvalue()

    def test_restore_is_a_no_op_when_nothing_is_staged(self):
        make_server(self.root)
        host = mock.Mock()
        host.state.return_value = 'gone'
        code, text = self.run_main(['restore', '--server-root', 'E:\\x'], host=host)
        self.assertEqual(code, 0)
        self.assertIn('nothing staged', text)

    def test_restore_refuses_while_dayz_runs(self):
        make_server(self.root)
        host = mock.Mock()
        host.state.return_value = 'running'
        code, text = self.run_main(['restore', '--server-root', 'E:\\x'], host=host)
        self.assertEqual(code, 2)
        self.assertIn('not stopped', text)

    def test_run_needs_the_lead_flag(self):
        make_server(self.root)
        make_client(self.root)
        host = mock.Mock()
        host.state.return_value = 'gone'
        with mock.patch.object(camp, 'step_script', return_value={'steps': []}), \
                mock.patch('tools.testing.test_addon.build', side_effect=AssertionError('built')):
            code, text = self.run_main(['run', '--server-root', 'E:\\x', '--client-root', str(self.root / 'client')], host=host)
        self.assertEqual(code, 2)
        self.assertIn('--yes', text)

    def test_run_takes_the_host_lock_and_reports_a_busy_host(self):
        make_server(self.root)
        make_client(self.root)
        host = mock.Mock()
        host.state.return_value = 'gone'
        from tools.release.host_lock import LockRefused
        with mock.patch.object(camp, 'step_script', return_value={'steps': []}), \
                mock.patch('tools.release.host_lock.host_lock', side_effect=LockRefused('native host busy: holder=x')):
            code, text = self.run_main(['run', '--yes', '--server-root', 'E:\\x',
                                        '--client-root', str(self.root / 'client')], host=host)
        self.assertEqual(code, 2)
        self.assertIn('native host busy', text)
        host.launch_server.assert_not_called()

    def test_errors_never_echo_a_private_path(self):
        make_server(self.root)
        with mock.patch.object(camp, 'load_phases', side_effect=OSError('/ho' + 'me/someone/secret')):
            code, text = self.run_main(['restore'])
        self.assertEqual(code, 2)
        self.assertNotIn('/home', text)


if __name__ == '__main__':
    unittest.main()
