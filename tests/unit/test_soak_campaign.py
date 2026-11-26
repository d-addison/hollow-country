"""Soak campaign orchestration with a fake host, fake clock and synthetic trees; DayZ is never started."""
import base64
from contextlib import nullcontext, redirect_stdout
import copy
from io import StringIO
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from tools.release.host_lock import LockRefused
from tools.setup.winproc import InteropError
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
        broken['manual']['Cellars/visual_applied'] = {'kind': 'owner_check', 'reason': 'walk into a cellar'}
        self.assertIn('manual row not allowed: Cellars/visual_applied', camp.manual_problems(broken))

    def test_phases_and_idle_window(self):
        self.assertEqual(tuple(p['name'] for p in PHASES['phases']), camp.PHASE_ORDER)
        self.assertGreaterEqual(PHASES['min_idle_minutes'], 125)
        self.assertEqual(PHASES['debug_snapshot_seconds'], 300)
        self.assertEqual(camp.phase_of(PHASES, 'DebugSnapshot', 'snapshot_saved'), ('phase', 'idle'))

    def test_campaign_index_preserves_phase_boundaries_after_shared_approaches(self):
        script, index = camp._campaign_driver_plan(camp.PHASE_ORDER)
        by_id = {step['id']: step for step in script['steps']}
        for phase in ('combat', 'loot', 'vehicle', 'survive'):
            ids = index[phase][phase]
            self.assertEqual(len(ids), 1)
            self.assertEqual(by_id[ids[0]]['kind'], phase)
        self.assertIn('admin:fx_site_patrol_kill', index['walk_ai'])
        self.assertEqual(set(index['walk_town']),
                         {'walk:site:scav-chernogorsk', 'route:site:scav-chernogorsk', 'stand', 'search_site',
                          'climb', 'cellar', 'combat', 'admin:fx_shoot_held', 'fixture:fx_shoot_held'})
        indexed = {step_id for tokens in index.values() for ids in tokens.values() for step_id in ids}
        self.assertEqual(indexed, set(by_id))
        self.assertEqual(len(by_id), len(script['steps']))

    def test_diagnostic_classifications_and_nav_members_match_the_code(self):
        for key in ('AIRoles/routes_pending', 'CellarSampler/class_measured', 'InfectedReach/backoff_started'):
            self.assertEqual(PHASES['reach'][key]['class'], 'diagnostic')
            self.assertTrue(PHASES['reach'][key]['note'])
        expectations = json.loads(camp.EXPECTATIONS.read_text())['features']
        by_key = {r['module'] + '/' + camp.norm(r['feature']): r for r in expectations}
        for key in ('AIRoles/routes_pending', 'CellarSampler/class_measured', 'InfectedReach/backoff_started'):
            self.assertEqual(by_key[key]['scope'], 'diagnostic')
        for key, member in (('HordeMigration/nav_route_advance', 'HordeMigration/route_advanced'),
                            ('InfectedDoors/nav_door_action', 'InfectedDoors/door_action'),
                            ('InfectedReach/nav_vault_started', 'InfectedReach/vault_started'),
                            ('optional-expansion-human-ai/nav_stuck_recovery',
                             'optional-expansion-human-ai/stuck_recovery')):
            self.assertEqual(PHASES['reach'][key]['how'], PHASES['reach'][member]['how'])
            self.assertNotIn('module=Nav', by_key[key]['signal']['regex'])
        tokens = {token for r in PHASES['reach'].values() if r.get('status') == 'pending-driver'
                  for token in r['how']}
        self.assertTrue({'fixture:' + name for name in ('fx_shoot_held', 'fx_door_press', 'fx_hearth',
                        'fx_die', 'fx_car_zeds', 'fx_incident', 'fx_tactic', 'fx_trade', 'fx_convoy_stuck')} <= tokens)
        self.assertTrue({'step:' + name for name in ('search_site', 'take_lead', 'raise', 'hold_ring', 'respawn')}
                        <= tokens)

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
        self.assertEqual(problems, ["unreached counters: 3"])
        self.assertIn('unmapped counters: 0', text)
        for name in camp.PHASE_ORDER:
            self.assertIn(name, text)
        self.assertNotIn('/home', text)

    def test_shipped_reach_map_only_has_declared_pending_driver_gaps(self):
        rows = camp.reach_rows(PHASES)
        self.assertTrue(rows)
        for key, _, _, problems in rows:
            if problems:
                self.assertEqual(PHASES['reach'][key]['status'], 'pending-driver')
                self.assertTrue(all(p.startswith('pending-driver:') for p in problems))
        lines, unreached = camp.reach_lines(rows)
        self.assertEqual(unreached, 3)
        # The lead maps counters after native proof. Do not credit the final phase to fixtures.
        self.assertEqual({key for key, _, _, problems in rows if problems},
                         {"BodyStories/body_observed", "BodyStories/death_checked",
                          "CampRespawn/respawn_reserved"})

    def test_every_how_token_names_a_real_step_fixture_or_setting(self):
        context = camp.reach_context()
        kinds = set()
        for key, row in PHASES['reach'].items():
            for token in row['how']:
                kinds.add(token.split(':', 1)[0])
                problem = camp.reach_token_problem(token, row['phase'], PHASES, context)
                if problem:
                    self.assertEqual(row.get('status'), 'pending-driver', (key, token))
                else:
                    self.assertIsNone(problem)
        self.assertTrue({'step', 'fixture', 'setting', 'code'} <= kinds)

    def test_reach_map_refuses_a_missing_wrong_or_invented_row(self):
        key = sorted(PHASES['reach'])[0]
        baseline = {key: problems for key, _, _, problems in camp.reach_rows(PHASES) if problems}
        for edit in (lambda d: d['reach'].pop(key),
                     lambda d: d['reach'][key].update(how=['code:HCNoSuchFile.c', 'boot']),
                     lambda d: d['reach'][key].update(how=['fixture:fx_no_such', 'code:HCWorkBudget.c']),
                     lambda d: d['reach'][key].update(how=['setting:NoSuchSetting', 'code:HCWorkBudget.c']),
                     lambda d: d['reach'][key].update(how=['code:HCWorkBudget.c']),
                     lambda d: d['reach'].update({'Nope/never': {'phase': 'idle', 'how': ['boot']}})):
            broken = copy.deepcopy(PHASES)
            edit(broken)
            rows = camp.reach_rows(broken)
            self.assertNotEqual({key: problems for key, _, _, problems in rows if problems}, baseline)
            lines, unreached = camp.reach_lines(rows)
            self.assertGreater(unreached, 0)
        broken = copy.deepcopy(PHASES)
        lines, problems = camp.plan_text(broken)
        self.assertTrue(all(p.startswith('unreached counters:') for p in problems))

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
        self.assertIn('serverTime = "2026/09/15/17/50";', out)
        self.assertIn('serverTimeAcceleration = 1;', out)
        self.assertIn('serverTimePersistent = 0;', out)
        self.assertIn('passwordAdmin = "hunter2";\r\n', out)
        self.assertIn('hostname = "x";', out)

    def test_test_cfg_refuses_a_duplicate_key(self):
        with self.assertRaises(camp.Refused):
            camp.test_cfg(CFG + b'instanceId = 2;\r\n')

    def test_soak_date_covers_forage_season_and_the_dusk_windows(self):
        year, month, day, hour, minute = camp.SOAK_TIME.split('/')
        self.assertTrue(9 <= int(month) <= 11)  # flora 6-11 and mushrooms 9-11
        start = int(hour) + int(minute) / 60.0
        self.assertTrue(17 <= start < 18)  # camp visitors 17-21, water 17-20, SignsOfLife from 18

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
                     'DuctTape', 'Crowbar', 'Wrench', 'TortillaBag', 'Paper', 'Pen_Black', 'AKM', 'Mag_AKM_30Rnd', 'Ammo_762x39', 'ChernarusMap', 'BakedBeansCan_Opened', 'WaterBottle'):
            self.assertIn(item, text)

    def test_settings_and_gameplay_edits(self):
        settings = json.loads(camp.settings_with_fixtures(json.dumps({'Keep': 7}).encode()))
        self.assertEqual(settings, {'Keep': 7, 'EnableSmokeFixtures': True, 'FortifyBreachSeconds': 20})
        gameplay = json.loads(camp.gameplay_with_preset(json.dumps(GAMEPLAY).encode()))
        self.assertEqual(gameplay['PlayerData']['spawnGearPresetFiles'], [camp.GEAR_REL])
        self.assertEqual(gameplay['other'], 1)
        self.assertFalse(gameplay['UIData']['use3DMap'])
        self.assertTrue(gameplay['MapData']['ignoreMapOwnership'])
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


class DependencyParityTests(Tmp):
    def setUp(self):
        super().setUp()
        self.server = make_server(self.root)
        self.client = make_client(self.root)
        self.mods = camp.server_mods(BAT) + [camp.TEST_MOD]
        self.paths = camp.client_mods(self.mods, self.server, self.client / '!Workshop', Path)
        self.left = self.server / '@CF/addons/Example.pbo'
        self.right = self.paths[0] / 'addons/example.PBO'
        for path in (self.left, self.right):
            path.parent.mkdir(parents=True)
            path.write_bytes(b'matching')

    def rows(self):
        return camp.dependency_parity(self.mods, self.server, self.paths)

    def test_match_is_case_insensitive_and_logs_folder_count(self):
        self.assertEqual(self.rows(), [('@CF', 0), ('@Dep', 0)])
        lines = []
        camp.require_dependency_parity(self.mods, self.server, self.paths, lines.append)
        self.assertEqual(lines, ['dependency parity: 2 folders ok'])

    def test_differing_bytes_of_same_size_refuse(self):
        self.right.write_bytes(b'different'[:8])
        self.assertEqual(self.rows()[0], ('@CF', 1))
        with self.assertRaisesRegex(camp.Refused, r'dependency mismatch: @CF \(1 pbo differ; players get kick 146; '
                                   r'rerun friend_install --apply\)'):
            camp.require_dependency_parity(self.mods, self.server, self.paths)

    def test_size_difference_and_multiple_missing_pbos_are_counted(self):
        self.right.write_bytes(b'short')
        (self.left.parent / 'server_only.pbo').write_bytes(b'one')
        (self.right.parent / 'client_only.pbo').write_bytes(b'two')
        self.assertEqual(self.rows()[0], ('@CF', 3))

    def test_own_folder_is_compared_if_client_uses_a_separate_copy(self):
        own = self.server / '@HollowCountry'
        own.mkdir()
        (own / 'own.pbo').write_bytes(b'own')
        other = self.root / 'other-own'
        other.mkdir()
        self.assertEqual(camp.dependency_parity(['@HollowCountry'], self.server, [other]),
                         [('@HollowCountry', 1)])

    def test_missing_pbo_on_either_side(self):
        for path in (self.left, self.right):
            content = path.read_bytes()
            path.unlink()
            self.assertEqual(self.rows()[0], ('@CF', 1))
            path.write_bytes(content)

    def test_only_pbos_in_shared_folders_are_read_and_own_same_files_are_excluded(self):
        (self.paths[0] / 'ignored.txt').write_bytes(b'other')
        extra = self.client / '!Workshop/@NotLoaded'
        extra.mkdir()
        (extra / 'other.pbo').write_bytes(b'unrelated')
        for mod in camp.OWN_MODS:
            folder = self.server / mod
            folder.mkdir(exist_ok=True)
            (folder / 'own.pbo').write_bytes(b'own')
        with mock.patch.object(Path, 'open', autospec=True, side_effect=Path.open) as opened:
            self.assertEqual(self.rows(), [('@CF', 0), ('@Dep', 0)])
        self.assertEqual({call.args[0] for call in opened.call_args_list}, {self.left, self.right})


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
        self.assertTrue((profile / camp.SPAWN_MARKER_REL).is_file())
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

    def test_profile_skip_is_copy_only_and_fresh_state_is_opt_in(self):
        hc = self.server / 'profiles/HollowCountry'
        files = ['admin-tour.json', 'scene-chains.json', 'scene-chains.json.tmp', 'scene-chains.json.bak',
                 'Infected/hordes-a.json', 'Infected/hordes-a.json.tmp', 'Infected/hordes-a.json.bak',
                 'Infected/hordes-b.json', 'Infected/hordes-b.json.tmp', 'Infected/hordes-b.json.bak',
                 'Events/state/intent-1.json', 'Events/state/image-1.json', 'Events/state/commit-1.json',
                 'Events/rewards/1-boot.txt', 'world.json', 'world.json.tmp', 'world.json.bak',
                 'ai-custody.json', 'recovery-hc.json', 'w38-situations.json', 'Groups/state/state_1.json']
        for rel in files:
            path = hc / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'preserve')
        source = {p: p.read_bytes() for p in hc.rglob('*') if p.is_file()}
        for fresh in (False, True):
            with self.subTest(fresh=fresh):
                logs = []
                self.stager.stage(self.addon, {'steps': []}, fresh_world_state=fresh, log=logs.append)
                self.assertIn('staged: skipped admin-tour.json', logs)
                for rel in files:
                    should_skip = (rel == 'admin-tour.json' or fresh and (
                        rel.startswith('Events/state/') or ('HollowCountry/' + rel).lower() in camp.FRESH_WORLD_SKIP))
                    self.assertEqual((self.server / camp.PROFILE_COPY / 'HollowCountry' / rel).exists(),
                                     not should_skip, rel)
                self.assertEqual({p: p.read_bytes() for p in source}, source)
                self.stager.restore(log=lambda line: None)
                staged = json.loads((self.state / 'last-run/staging.json').read_text())
                self.assertEqual(staged['fresh_world_state'], fresh)
                self.assertEqual({p: p.read_bytes() for p in source}, source)

    def test_copied_settings_symlink_cannot_modify_the_source(self):
        settings = self.server / 'profiles/HollowCountry/settings.json'
        target = self.root / 'source-settings.json'
        original = settings.read_bytes()
        target.write_bytes(original)
        settings.unlink()
        settings.symlink_to(target)
        self.stager.stage(self.addon, {'steps': []}, log=lambda line: None)
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse((self.server / camp.PROFILE_COPY / 'HollowCountry/settings.json').is_symlink())

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

    def __init__(self, stager, clock, server_ready=True, stop_ok=True, driver='done', script_error=None,
                 late=0, unknown_reads=0, server_crash=False, join=True, kick=None):
        self.stager, self.clock, self.script_error = stager, clock, script_error
        # late: client polls that read gone after launch (the BattlEye launcher has not started it yet);
        # unknown_reads: client polls that read unknown (lost interop replies) once the client has read running.
        self.late, self.unknown_reads, self.seen_running = late, unknown_reads, False
        self.running = dict.fromkeys(camp.PROCESS_IMAGES, False)
        self.calls, self.client_args, self.stopped_at = [], None, {}
        self.server_ready, self.stop_ok, self.driver = server_ready, stop_ok, driver
        # server_crash: the server dies (engine crash log written) once the client is up and driving.
        self.server_crash = server_crash
        self.join, self.kick = join, kick

    def state(self, image):
        if image == camp.CLIENT_IMAGE and self.running[image]:
            if self.late:
                self.late -= 1
                return 'gone'
            if self.unknown_reads and self.seen_running:
                self.unknown_reads -= 1
                return 'unknown'
            self.seen_running = True
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
        if self.join:
            lines.append('[HC Driver] connect session start')
        server_rpt = Path(self.stager.server) / camp.PROFILE_COPY / 'DayZServer_x64_1.RPT'
        with server_rpt.open('a') as stream:
            if self.join:
                stream.write('Server: SetClientState dpid=7 id=0 name=Survivor MISSION RECEIVED -> GAME LOADED\n')
            if self.kick:
                stream.write(self.kick + '\n')
        (folder / 'DayZ_x64_1.RPT').write_text('\n'.join(lines) + '\n')
        if self.server_crash:
            self.running[camp.SERVER_IMAGE] = False
            (Path(self.stager.server) / camp.PROFILE_COPY / 'crash_1.log').write_text(
                'Program: ' + 'C:' + '\\Us' + 'ers\\someone\\DayZServer_x64.exe\nFunction: \'ProcessGun\'\nStack trace:\n'
                'HollowCountry/scripts/4_World/loot/hcgunpile.c:177 Function ProcessGun\n'
                'scripts/3_Game/dayzgame.c:3026 Function OnUpdate\n')

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

    def campaign(self, selection=None, **options):
        host = FakeHost(self.stager, self.clock, **options)
        addon = make_addon(self.root)
        run = camp.Campaign(self.stager, host, PHASES, addon_build=lambda: addon, step_script={'version': 1, 'steps': []},
                            sleep=self.clock.sleep, now=self.clock.now, log=lambda text: None, win=str,
                            selection=selection)
        return run, host

    def snapshot(self):
        return {p: p.read_bytes() for p in self.server.rglob('*') if p.is_file()}

    def test_client_script_compile_failure_refuses_during_join_and_restores(self):
        run, host = self.campaign(join=False)
        launch = host.launch_client

        def broken_client(root, arguments):
            launch(root, arguments)
            profile = self.stager.client_parent / camp.CLIENT_PROFILE
            (profile / 'script_1.log').write_text("Multiple declaration of function 'Connect'\n")

        host.launch_client = broken_client
        with self.assertRaisesRegex(camp.Refused, 'client compile check failed: compile_errors'):
            run.run()
        self.assertFalse(host.running[camp.CLIENT_IMAGE])
        self.assertFalse(host.running[camp.SERVER_IMAGE])
        self.assertEqual(self.snapshot(), self.original)

    def test_full_run_drives_idles_stops_gracefully_and_restores(self):
        run, host = self.campaign()
        self.assertTrue(run.run())
        self.assertEqual(host.calls, ['launch_server', 'launch_client', 'stop ' + camp.CLIENT_IMAGE,
                                      'stop ' + camp.SERVER_IMAGE])
        self.assertIn('-connect=127.0.0.1:2302:27016', host.client_args)
        self.assertTrue([a for a in host.client_args if a.startswith('-mod=') and a.endswith(camp.TEST_MOD)])
        self.assertEqual(self.clock.t, camp.DRIVER_GRACE_SECONDS)
        self.assertEqual(self.snapshot(), self.original)
        self.assertFalse(self.stager.receipt_path.exists())
        server, client = camp.last_run_logs(self.state)
        self.assertIsNotNone(server)
        self.assertIn('[HC Driver] done', client.read_text())

    def test_explicit_minimum_survives_early_driver_completion(self):
        run, host = self.campaign()
        run.min_duration_seconds = 30 * 60
        self.assertTrue(run.run())
        self.assertEqual(host.stopped_at[camp.CLIENT_IMAGE], 30 * 60)

    def test_final_receipt_for_another_run_cannot_shorten_this_run(self):
        run, host = self.campaign()
        run.step_script['run_id'] = 'expected'
        self.assertTrue(run.run())
        self.assertGreaterEqual(self.clock.t, PHASES['min_idle_minutes'] * 60)

    def test_completion_arriving_after_driver_budget_gets_the_grace(self):
        run, host = self.campaign(driver='running')
        sleep = run.sleep
        completed_at = None

        def append_done(seconds):
            nonlocal completed_at
            sleep(seconds)
            # Initial driver budget for all phases is longer than 300 minutes.
            if completed_at is None and self.clock.t >= 360 * 60:
                rpt = self.stager.client_parent / camp.CLIENT_PROFILE / 'DayZ_x64_1.RPT'
                with rpt.open('a') as stream:
                    stream.write('[HC Driver] done run=r1 steps=1 ok=1 refused=0 unsupported=0 timeout=0\n')
                completed_at = self.clock.t

        run.sleep = append_done
        self.assertTrue(run.run())
        self.assertIsNotNone(completed_at)
        self.assertEqual(host.stopped_at[camp.CLIENT_IMAGE], completed_at + camp.DRIVER_GRACE_SECONDS)

    def test_a_targeted_run_idles_short_and_marks_the_last_run(self):
        selection = camp.select_targets(PHASES, only_phases=['actions'], index={})
        run, host = self.campaign(selection)
        self.assertTrue(run.run())
        self.assertLess(self.clock.t, PHASES['min_idle_minutes'] * 60)
        self.assertEqual(self.clock.t, camp.DRIVER_GRACE_SECONDS)
        marker = self.state / 'last-run' / camp.SELECTION_FILE
        self.assertEqual(json.loads(marker.read_text())['phases'], ['join', 'actions', 'idle'])
        self.assertEqual(self.snapshot(), self.original)
        run, host = self.campaign()
        self.assertTrue(run.run())
        self.assertFalse(marker.exists())

    def test_a_server_crash_while_driving_ends_the_run_at_once_and_restores(self):
        run, host = self.campaign(driver='running', server_crash=True)
        with self.assertRaisesRegex(camp.Refused, 'DayZServer_x64.exe crashed while waiting for the driver to finish: '
                                    'HollowCountry/scripts/4_World/loot/hcgunpile.c:177 Function ProcessGun') as caught:
            run.run()
        self.assertNotIn('someone', str(caught.exception))
        self.assertLess(self.clock.t, 5 * 60)
        self.assertEqual(self.snapshot(), self.original)
        self.assertTrue((self.state / 'last-run/server/crash_1.log').exists())

    def test_a_lost_close_reply_is_reconciled_after_the_client_exits(self):
        run, host = self.campaign()
        request_close, process_state = host.stop, host.state
        readings = iter(['running', 'unknown', 'gone'])

        def stop(image):
            request_close(image)
            if image == camp.CLIENT_IMAGE:
                raise InteropError('lost reply')

        def state(image):
            if image == camp.CLIENT_IMAGE and image in host.stopped_at:
                return next(readings)
            return process_state(image)

        host.stop, host.state = stop, state
        log = []
        run.log = log.append
        self.assertTrue(run.run())
        self.assertEqual(host.calls.count('stop ' + camp.CLIENT_IMAGE), 1)
        self.assertEqual(host.calls.count('stop ' + camp.SERVER_IMAGE), 1)
        self.assertTrue(any('Independently confirmed gone' in line for line in log))
        self.assertEqual(self.snapshot(), self.original)
        self.assertFalse(self.stager.receipt_path.exists())

    def test_unknown_exit_state_leaves_the_stage_and_still_stops_the_server(self):
        run, host = self.campaign()
        request_close, process_state = host.stop, host.state

        def stop(image):
            request_close(image)
            if image == camp.CLIENT_IMAGE:
                raise InteropError('lost reply')

        def state(image):
            if image == camp.CLIENT_IMAGE and image in host.stopped_at:
                raise InteropError('lost query reply')
            return process_state(image)

        host.stop, host.state = stop, state
        with self.assertRaisesRegex(camp.Refused, r'DayZ_x64.exe state=unknown.*run restore'):
            run.run()
        self.assertEqual(host.calls.count('stop ' + camp.CLIENT_IMAGE), 1)
        self.assertIn('stop ' + camp.SERVER_IMAGE, host.calls)
        self.assertFalse(host.running[camp.SERVER_IMAGE])
        self.assertTrue(self.stager.receipt_path.exists())
        self.assertNotEqual(self.snapshot(), self.original)

    def test_a_refused_close_still_fails_the_run_after_a_safe_restore(self):
        run, host = self.campaign()
        request_close = host.stop

        def stop(image):
            request_close(image)
            if image == camp.CLIENT_IMAGE:
                raise camp.Refused('graceful close request failed')

        host.stop = stop
        with self.assertRaisesRegex(camp.Refused, 'graceful close request failed'):
            run.run()
        self.assertEqual(self.snapshot(), self.original)
        self.assertFalse(self.stager.receipt_path.exists())

    def test_server_crash_remains_the_failure_after_a_lost_client_close_reply(self):
        run, host = self.campaign(driver='running', server_crash=True)
        request_close = host.stop

        def stop(image):
            request_close(image)
            if image == camp.CLIENT_IMAGE:
                raise InteropError('lost reply')

        host.stop = stop
        with self.assertRaisesRegex(camp.Refused, 'DayZServer_x64.exe crashed .*hcgunpile.c:177 Function ProcessGun'):
            run.run()
        self.assertIn('stop ' + camp.SERVER_IMAGE, host.calls)
        self.assertEqual(self.snapshot(), self.original)
        self.assertTrue((self.state / 'last-run/server/crash_1.log').exists())

    def test_a_running_launcher_leaves_the_stage_after_both_game_processes_stop(self):
        run, host = self.campaign()
        launch = host.launch_client

        def launch_client(root, arguments):
            launch(root, arguments)
            host.running[camp.LAUNCHER_IMAGE] = True

        host.launch_client = launch_client
        with self.assertRaisesRegex(camp.Refused, r'DayZ_BE.exe state=running.*run restore'):
            run.run()
        self.assertTrue(self.stager.receipt_path.exists())
        self.assertFalse(host.running[camp.CLIENT_IMAGE])
        self.assertFalse(host.running[camp.SERVER_IMAGE])

    def test_crash_summary_without_a_script_frame(self):
        folder = self.root / 'logs'
        folder.mkdir()
        self.assertIsNone(camp.crash_summary(folder))
        (folder / 'crash_1.log').write_text('Program: x\nReason: Access violation\n')
        self.assertEqual(camp.crash_summary(folder), 'native crash without a script frame')

    def test_a_client_the_launcher_starts_late_is_waited_for(self):
        run, host = self.campaign(late=3)
        self.assertTrue(run.run())
        self.assertEqual(0, host.late)
        self.assertEqual(self.snapshot(), self.original)

    def test_a_client_that_never_appears_refuses_and_restores(self):
        run, host = self.campaign(late=10 ** 6)
        with self.assertRaisesRegex(camp.Refused, 'did not start within'):
            run.run()
        self.assertEqual(self.snapshot(), self.original)

    def test_a_few_unknown_process_reads_do_not_end_the_run(self):
        run, host = self.campaign(unknown_reads=camp.UNREADABLE_POLLS - 1)
        self.assertTrue(run.run())

    def test_unknown_process_reads_that_repeat_refuse(self):
        run, host = self.campaign(unknown_reads=camp.UNREADABLE_POLLS)
        run.min_duration_seconds = 30 * 60
        with self.assertRaisesRegex(camp.Refused, 'process state unknown'):
            run.run()
        self.assertEqual(self.snapshot(), self.original)

    def test_refuses_while_the_server_or_client_runs(self):
        for image in camp.PROCESS_IMAGES:
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

    def test_join_deadline_requires_evidence_from_both_peers(self):
        for missing in ('client', 'server', 'both'):
            with self.subTest(missing=missing):
                run, host = self.campaign(join=False)
                launch = host.launch_client

                def launch_without_evidence(*args):
                    launch(*args)
                    if missing == 'server':
                        path = self.stager.client_parent / camp.CLIENT_PROFILE / 'DayZ_x64_1.RPT'
                        with path.open('a') as stream:
                            stream.write('[HC Driver] connect session start\n')
                    if missing == 'client':
                        path = self.server / camp.PROFILE_COPY / 'DayZServer_x64_1.RPT'
                        with path.open('a') as stream:
                            stream.write('Server: SetClientState dpid=7 id=0 name=Survivor MISSION RECEIVED -> GAME LOADED\n')

                host.launch_client = launch_without_evidence
                started = self.clock.t
                with self.assertRaisesRegex(camp.Refused, 'client never joined:'):
                    run.run()
                self.assertEqual(self.clock.t - started, camp.CLIENT_JOIN_SECONDS)
                self.assertEqual(self.snapshot(), self.original)
                self.assertFalse(any(host.running.values()))

    def test_kick_refuses_immediately_and_removes_identity(self):
        identity = '12345678901234567'
        line = 'Player "Synthetic Player" (id=' + identity + ') kicked from server: 146 (' + (
            'Client has a more recent version. (DayZ-Expansion-Vehicles id=' + identity + '))')
        run, host = self.campaign(join=False, kick=line)
        with self.assertRaises(camp.Refused) as caught:
            run.run()
        refusal = str(caught.exception)
        self.assertIn('client never joined: kicked 146 (Client has a more recent version.', refusal)
        self.assertIn('DayZ-Expansion-Vehicles', refusal)
        self.assertNotIn(identity, refusal)
        self.assertNotIn('Synthetic Player', refusal)
        self.assertEqual(self.clock.t, 0)
        self.assertEqual(self.snapshot(), self.original)
        self.assertFalse(any(host.running.values()))

    def test_kick_reason_redacts_identity_fields_and_quoted_names(self):
        line = ('Player "Synthetic Player" kicked from server: 99 '
                '(Rejected "Synthetic Player" guid=synthetic_base64_identity=)')
        self.assertEqual(camp.kick_refusal(line),
                         'client never joined: kicked 99 (Rejected [redacted] [id removed])')
        self.assertIsNone(camp.kick_refusal('unrelated server line'))

    def test_dependency_mismatch_refuses_before_build_or_launch_and_restores(self):
        (self.server / '@CF/addons').mkdir()
        (self.server / '@CF/addons/test.pbo').write_bytes(b'server')
        original = self.snapshot()
        run, host = self.campaign()
        run.addon_build = mock.Mock(side_effect=AssertionError('must not build'))
        with mock.patch.object(self.stager, 'restore', wraps=self.stager.restore) as restore:
            with self.assertRaisesRegex(camp.Refused, 'dependency mismatch: @CF'):
                run.run()
            restore.assert_called_once()
        self.assertEqual(host.calls, [])
        self.assertEqual(self.snapshot(), original)
        self.assertFalse(self.stager.receipt_path.exists())

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

        host = camp.WindowsHost.__new__(camp.WindowsHost)
        host.winproc = Win()
        host.stop(camp.SERVER_IMAGE)
        wrapped = Win.scripts[0]
        self.assertNotIn('"', wrapped)  # nothing for the Windows command line to re-quote
        script = base64.b64decode(re.search(r"FromBase64String\('([^']+)'", wrapped)[1]).decode('utf-16-le')
        self.assertIn('CloseMainWindow', script)
        # The compile error box gets Ignore (5) only; Abort (3) would end the process abruptly.
        self.assertIn('"Compile error"', script)
        self.assertIn('(IntPtr)5', script)
        self.assertNotIn('(IntPtr)3', script)
        for banned in ('Stop-Process', 'taskkill', 'Kill(', '.Kill'):
            self.assertNotIn(banned, script)


    def launch_host(self, replies, states):
        """replies: per run() call, 'lost' or a returncode; states: per state() poll, cycled from the last."""
        from tools.setup import winproc

        class Win:
            InteropError = winproc.InteropError
            scripts = []

            def run(self, kind, args, **kw):
                self.scripts.append(args[0])
                reply = replies.pop(0)
                if reply == 'lost':
                    raise winproc.InteropError('lost')
                return mock.Mock(returncode=reply, stdout='HC launch acknowledged\n')

            def process_state(self, image):
                return states.pop(0) if len(states) > 1 else states[0]

        host = camp.WindowsHost.__new__(camp.WindowsHost)
        host.winproc = Win()
        now = [0.0]
        host.clock = lambda: now[0]
        host.sleep = lambda seconds: now.__setitem__(0, now[0] + seconds)
        return host

    def test_a_lost_launch_reply_retries_only_after_the_client_reads_gone(self):
        host = self.launch_host(['lost', 0], ['gone'])
        host.launch_client('G:\\DayZ', ['0', '-mod=G:\\a b;G:\\c'])
        self.assertEqual(2, len(host.winproc.scripts))
        self.assertNotIn('"', host.winproc.scripts[0])

    def test_a_lost_launch_reply_with_the_client_running_does_not_launch_twice(self):
        host = self.launch_host(['lost', 0], ['gone', 'running'])
        host.launch_client('G:\\DayZ', ['0'])
        self.assertEqual(1, len(host.winproc.scripts))

    def test_an_unknown_process_state_after_a_lost_reply_refuses(self):
        host = self.launch_host(['lost', 0], ['unknown'])
        with self.assertRaisesRegex(camp.Refused, 'cannot tell whether the client started'):
            host.launch_client('G:\\DayZ', ['0'])
        self.assertEqual(1, len(host.winproc.scripts))

    def test_every_reply_lost_and_nothing_running_refuses(self):
        host = self.launch_host(['lost'] * camp.LAUNCH_ATTEMPTS, ['gone'])
        with self.assertRaisesRegex(camp.Refused, 'server start failed'):
            host.launch_server('E:\\srv')
        self.assertEqual(camp.LAUNCH_ATTEMPTS, len(host.winproc.scripts))

    def test_a_failed_launch_refuses_without_retry(self):
        host = self.launch_host([1, 0], ['gone'])
        with self.assertRaisesRegex(camp.Refused, 'client start failed'):
            host.launch_client('G:\\DayZ', ['0'])
        self.assertEqual(1, len(host.winproc.scripts))


def synthetic_phases(reach):
    phases = copy.deepcopy(PHASES)
    phases['reach'] = reach
    return phases


class SelectionTests(unittest.TestCase):
    INDEX = {'walk_town': {'walk:site:town': ['s1']}, 'fixtures': {'fixture:fx_a': ['s2']}}
    REACH = {
        'Radio/delivered': {'phase': 'actions', 'how': ['step:walk:site:town', 'code:HCRadio.c']},
        'Cellars/sampled': {'phase': 'idle', 'how': ['timer:60m', 'code:HCCellarSampler.c']},
        'Fix/started': {'phase': 'fixtures', 'how': ['fixture:fx_a', 'code:HCFix.c']},
    }
    FOLDERS = {'HCRadio.c': {'HollowCountry/Radio'}, 'HCCellarSampler.c': {'HollowCountry/Cellars'}}

    def select(self, **options):
        options.setdefault('index', self.INDEX)
        options.setdefault('folders', self.FOLDERS)
        return camp.select_targets(synthetic_phases(self.REACH), **options)

    def test_no_option_is_the_full_campaign(self):
        self.assertIsNone(self.select())

    def test_a_changed_file_brings_its_phase_and_the_earlier_phase_of_its_step(self):
        got = self.select(changed=['mods/HollowCountry/scripts/4_World/Radio/HCRadio.c', 'docs/x.md'])
        self.assertEqual(got['phases'], ['join', 'walk_town', 'actions', 'idle'])
        self.assertEqual(got['counters'], ['Radio/delivered'])
        self.assertEqual(got['idle_minutes'], camp.TARGETED_IDLE_MINUTES)
        self.assertEqual(got['sources'], ['mods/HollowCountry/scripts/4_World/Radio/HCRadio.c'])

    def test_a_timer_lengthens_the_idle(self):
        got = self.select(changed=['mods/HollowCountry/scripts/4_World/Cellars/HCCellarSampler.c'])
        self.assertEqual(got['idle_minutes'], 60)
        self.assertEqual(got['phases'], ['join', 'idle'])

    def test_an_unnamed_file_falls_back_to_its_feature_folder_in_any_layer(self):
        got = self.select(changed=['mods/HollowCountry/scripts/3_Game/Radio/HCRadioSettings.c'])
        self.assertEqual(got['counters'], ['Radio/delivered'])
        self.assertEqual(got['unmapped_sources'], [])

    def test_a_flat_layer_file_is_listed_and_refused_alone(self):
        flat = 'mods/HollowCountry/scripts/3_Game/HCSettings.c'
        with self.assertRaisesRegex(camp.Refused, 'HCSettings.c'):
            self.select(changed=[flat])
        got = self.select(changed=[flat, 'mods/X/scripts/4_World/HCFix.c'])
        self.assertEqual(got['unmapped_sources'], [flat])
        self.assertEqual(got['phases'], ['join', 'fixtures', 'idle'])
        got = self.select(changed=[flat], only_phases=['scene'])
        self.assertEqual(got['phases'], ['join', 'scene', 'idle'])

    def test_test_addon_changes_select_nothing_alone(self):
        harness = 'mods/HollowCountryTest/scripts/5_Mission/HCClientDriver.c'
        with self.assertRaisesRegex(camp.Refused, 'HCClientDriver.c'):
            self.select(changed=[harness])
        self.assertEqual(self.select(changed=[harness], modules=['Fix'])['harness_sources'], [harness])

    def test_unknown_module_or_phase_is_refused(self):
        with self.assertRaisesRegex(camp.Refused, 'module Nope'):
            self.select(modules=['Nope'])
        with self.assertRaisesRegex(camp.Refused, 'unknown phase'):
            self.select(only_phases=['nope'])

    def test_judged_needs_a_driven_phase_and_a_timer_inside_the_run(self):
        phases = synthetic_phases(self.REACH)
        got = self.select(modules=['Radio'])
        self.assertTrue(camp.judged(got, phases, 'Radio/delivered', 'actions'))
        self.assertFalse(camp.judged(got, phases, 'Fix/started', 'fixtures'))
        self.assertFalse(camp.judged(got, phases, 'Cellars/sampled', 'idle'))
        self.assertTrue(camp.judged(None, phases, 'Fix/started', 'fixtures'))

    def test_the_real_reach_map_selects_a_module(self):
        got = camp.select_targets(PHASES, modules=['Radio'])
        self.assertIn('join', got['phases'])
        self.assertTrue(all(key.startswith('Radio/') for key in got['counters']))


class ReportTests(Tmp):
    def test_a_targeted_report_marks_undriven_counters_not_run(self):
        phases = synthetic_phases(SelectionTests.REACH)
        selection = camp.select_targets(phases, modules=['Radio'], index=SelectionTests.INDEX)
        release = {'features': [dict(module='Radio', feature='delivered', status='INERT', count=0, fixture=0),
                                dict(module='Fix', feature='started', status='INERT', count=0, fixture=0),
                                dict(module='Cellars', feature='sampled', status='ACTIVE', count=1, fixture=0)],
                   'activity': 'inert', 'count': 1}
        phases['features'].update({'Radio/delivered': 'actions', 'Fix/started': 'fixtures', 'Cellars/sampled': 'idle'})
        rows = camp.report_rows(phases, None, release, (), selection)
        by = {r[1]: r[3] for r in rows if r[0] == 'use'}
        self.assertEqual(by, {'Radio/delivered': 'zero', 'Fix/started': 'not run', 'Cellars/sampled': 'active'})
        text, totals = camp.render_report(rows, [], None, selection)
        self.assertIn('Targeted run: not release evidence', text)
        self.assertEqual(totals['not run'], 1)

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
        self.assertEqual(by[('expect', 'TeamPing/ping-recipients')][3], 'zero')
        self.assertEqual(by[('expect', 'TeamPing/ping-recipients')][2], 'group')
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

    def test_tour_armed_or_any_stop_is_a_failed_soak_report(self):
        server, client = self.root / 's.RPT', self.root / 'c.RPT'
        client.write_text('')
        for line in ('[HC Tour] state=armed delay=60 dwell=90',
                     '[HC Tour] stop=1 result=ok', '[HC Tour] stop=0 result=refused'):
            server.write_text(line + '\n')
            with mock.patch.object(camp, 'activity_results', return_value=(None, None, [])), \
                    mock.patch('tools.release.client_compile_check.scan', return_value={'passed': True}), \
                    mock.patch('tools.release.client_compile_check.verdict_line', return_value='ok'):
                report, totals = camp.build_report(PHASES, server, client)
            self.assertEqual(totals['zero'], 1)
            self.assertIn('admin_tour_detected', report)
            self.assertIn('no-teleport rule violated', report)
        server.write_text('[HC Tour] state=off\n')
        self.assertIsNone(camp.admin_tour_failure(server))

    def test_tour_failure_makes_report_command_nonzero(self):
        server = self.root / 'last-run/server/s.RPT'
        client = self.root / 'last-run/client/c.RPT'
        server.parent.mkdir(parents=True)
        client.parent.mkdir(parents=True)
        server.write_text('[HC Tour] stop=1 result=ok\n')
        client.write_text('')
        with mock.patch.object(camp, 'activity_results', return_value=(None, None, [])), \
                mock.patch('tools.release.client_compile_check.scan', return_value={'passed': True}), \
                mock.patch('tools.release.client_compile_check.verdict_line', return_value='ok'):
            self.assertEqual(camp.command_report(PHASES, self.root, StringIO()), 8)
        self.assertIn('admin_tour_detected', (self.root / 'last-run/report.md').read_text())

    def test_diagnostic_zero_is_visible_and_not_broken(self):
        release = {'features': [dict(module='AIRoles', feature='routes_pending', status='INERT', count=0)]}
        rows = camp.report_rows(PHASES, None, release)
        row = next(r for r in rows if r[1] == 'AIRoles/routes_pending')
        self.assertEqual(row[3], 'not run')
        self.assertIn('diagnostic (zero allowed)', row[4])

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
                mock.patch.object(camp, 'WindowsHost', side_effect=AssertionError('no real host in tests')), \
                mock.patch('tools.release.host_lock.host_lock', patches.get('lock', lambda holder: nullcontext())):
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
        host.state.side_effect = lambda image: 'running' if image == camp.CLIENT_IMAGE else 'gone'
        code, text = self.run_main(['restore', '--server-root', 'E:\\x'], host=host)
        self.assertEqual(code, 2)
        self.assertIn('not stopped', text)

    def test_restore_requires_the_launcher_to_be_confirmed_gone(self):
        server = make_server(self.root)
        client = make_client(self.root)
        stager = camp.Stager(server, client, self.root / 'state', win=str)
        stager.stage(make_addon(self.root), {'steps': []})
        for state in ('running', 'unknown'):
            with self.subTest(state=state):
                host = mock.Mock()
                host.state.side_effect = lambda image: state if image == camp.LAUNCHER_IMAGE else 'gone'
                code, text = self.run_main(['restore'], host=host)
                self.assertEqual(code, 2)
                self.assertIn('DayZ_BE.exe is not stopped (state=' + state + ')', text)
                self.assertTrue(stager.receipt_path.exists())

    def test_restore_takes_the_host_lock_before_querying_processes(self):
        make_server(self.root)
        host = mock.Mock()
        lock = mock.Mock(side_effect=LockRefused('native host busy: holder=x'))
        code, text = self.run_main(['restore'], host=host, lock=lock)
        self.assertEqual(code, 2)
        self.assertIn('native host busy', text)
        lock.assert_called_once_with('soak_campaign')
        host.state.assert_not_called()

    def test_stage_requires_the_game_processes_to_be_stopped_before_building(self):
        make_server(self.root)
        client = make_client(self.root)
        host = mock.Mock()
        host.state.side_effect = lambda image: 'running' if image == camp.SERVER_IMAGE else 'gone'
        with mock.patch.object(camp, 'step_script', return_value={'steps': []}), \
                mock.patch('tools.testing.test_addon.build', side_effect=AssertionError('built')):
            code, text = self.run_main(['stage', '--client-root', str(client)], host=host)
        self.assertEqual(code, 2)
        self.assertIn('stage refused: DayZServer_x64.exe is not stopped (state=running)', text)
        self.assertFalse((self.root / 'state' / 'receipt.json').exists())

    def test_run_reports_before_releasing_the_host_lock(self):
        make_server(self.root)
        client = make_client(self.root)
        events = mock.Mock()
        lease = mock.MagicMock()
        events.attach_mock(lease, 'lease')
        events.run.return_value = True
        events.report.return_value = 8
        with mock.patch.object(camp, 'step_script', return_value={'steps': []}), \
                mock.patch.object(camp.Campaign, 'run', events.run), \
                mock.patch.object(camp, 'command_report', events.report):
            code, _ = self.run_main(['run', '--yes', '--client-root', str(client)], host=mock.Mock(),
                                    lock=lambda holder: lease)
        self.assertEqual(code, 8)
        self.assertEqual(events.mock_calls, [mock.call.lease.__enter__(), mock.call.run(),
                                            mock.call.report(PHASES, self.root / 'state', mock.ANY),
                                            mock.call.lease.__exit__(None, None, None)])

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
        lock = mock.Mock(side_effect=LockRefused('native host busy: holder=x'))
        with mock.patch.object(camp, 'step_script', return_value={'steps': []}):
            code, text = self.run_main(['run', '--yes', '--server-root', 'E:\\x',
                                        '--client-root', str(self.root / 'client')], host=host, lock=lock)
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


class AIClearEvidenceTests(unittest.TestCase):
    def test_plan_indexes_both_modes_and_reserves_one_respawn(self):
        script, index = camp._campaign_driver_plan(camp.PHASE_ORDER)
        by_id = {s['id']: s for s in script['steps']}
        ids = index['ai_clear']['fixture:fx_site_clear']
        self.assertEqual([by_id[key]['value'] for key in ids], ['0', '1'])
        self.assertEqual(sum(s['kind'] == 'respawn' for s in script['steps']), 1)
        self.assertEqual(camp.PHASE_ORDER[-2:], ('ai_clear', 'idle'))
        self.assertEqual(next(p['minutes'] for p in PHASES['phases'] if p['name'] == 'ai_clear'), 15)

    def test_evidence_preserves_terminal_duplicates_and_missing_despawns(self):
        lines = [
            '[HCX SitePatrol] death_hold armed site=zg-vmc kills=1',
            '[HC Test] fx_site_clear site=zg-vmc kind=zone mode=attributed kill=1 members_left=1 held_ms=0',
            '[HCX SitePatrol] death_hold_deferred reason=DEATH_HOLD_STALE site=zg-vmc',
            '[HC Expansion AI] site zg-vmc cleared-at=123 saved=true',
            '[HC ZoneGuards] zone=vmc from=held to=abandoned',
            '[HC Expansion AI] site zg-vmc despawned (intact=false)',
            '[HC Expansion AI] site zg-vmc despawned (intact=false)',
            '[HC Test] fx_site_clear site=zg-vmc mode=attributed result=terminal kills=2 elapsed_s=12 last=patrol-not-live',
            '[HC Test] fx_site_clear site=police-chernogorsk kind=site mode=health kill=1 members_left=0 held_ms=0',
            '[HC Test] fx_site_clear site=police-chernogorsk mode=health result=timeout kills=1 elapsed_s=180 last=death-held',
            '[HC Expansion AI] site unrelated despawned (intact=false)',
            'unrelated private log',
        ]
        with tempfile.TemporaryDirectory() as folder:
            rpt = Path(folder) / 'server.RPT'
            rpt.write_text('\n'.join(lines))
            evidence, counts = camp.ai_clear_evidence(rpt)
            self.assertEqual(evidence, lines[:-2])
            self.assertEqual(counts, {'police-chernogorsk': 0, 'zg-vmc': 2})
            report = '\n'.join(camp.ai_clear_report_lines(rpt))
            self.assertIn('| zg-vmc | 2 | FAIL |', report)
            self.assertIn('| police-chernogorsk | 0 | FAIL |', report)
            self.assertIn('Infected counters excluded', report)
            rpt.write_text('\n'.join(lines[:6] + lines[7:8]))
            self.assertIn('| zg-vmc | 1 | PASS |', '\n'.join(camp.ai_clear_report_lines(rpt)))

    def test_mode_receipts_are_observations_not_credited_deltas(self):
        with tempfile.TemporaryDirectory() as folder:
            rpt = Path(folder) / 'server.RPT'
            rpt.write_text('\n'.join([
                '[HC Use] module=SitePatrols feature=death-hold-armed count=8',
                '[HC Test] fx_site_clear site=zg-vmc mode=attributed start=1 reason=live-patrol-selected',
                '[HC Use] module=SitePatrols feature=death-hold-armed count=9',
                '[HC Use] module=AISelfDefence feature=hit_reaction count=1',
                '[HC Test] fx_site_clear site=police-chernogorsk mode=health start=1 reason=live-patrol-selected',
                '[HC Use] module=SitePatrols feature=death-hold-armed count=15',
                '[HC Use] module=InfectedVariety feature=actor_woken count=4',
            ]))
            observed = camp.ai_clear_mode_counters(rpt)
            self.assertEqual([row[:3] for row in observed], [
                ('attributed', 'SitePatrols/death-hold-armed', 9),
                ('attributed', 'AISelfDefence/hit_reaction', 1),
                ('health', 'SitePatrols/death-hold-armed', 15)])
            report = '\n'.join(camp.ai_clear_report_lines(rpt))
            self.assertIn('cumulative, not attributable deltas', report)
            self.assertIn('Excluded observed infected counters: InfectedVariety/actor_woken.', report)
