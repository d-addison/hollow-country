"""WP3 offline contracts. All runtime/receipt fixtures here are SYNTHETIC.

Registration patches model coordinator integration, not installed registration.
Unpatched staging must refuse missing registrations before writing anything.
These tests never launch DayZ or establish native competence.
"""
import copy
import contextlib
import hashlib
import io
import json
import math
import re
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.unit.test_taped_light_probe import make_source_runtime, SYNTH_BE_SHA
from tools.setup import diagnostic_mission as dm
from tools.setup import probe_runtime as rt
from tools.setup import infected_competence_probe as probe

CACHE = Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')


def synthetic_receipt(plan):
    rows = []
    for trial in plan['trials']:
        client = trial['support_state'] == 'client_required'
        rows.append(dict(id=trial['id'], kind=trial['kind'], support_state=trial['support_state'],
                         status='client_required' if client else 'completed', observed=not client,
                         reason=trial['reason'] if client else 'sampled', spawned=0 if client else 1,
                         deleted=0 if client else 1, elapsed_ms=0 if client else 5000,
                         anchor_authored_y='' if client else str(trial['structure_position'][1]),
                         anchor_surface_y='' if client else '20',
                         spawn_authored_y='' if client else str(trial['position'][1]),
                         spawn_surface_y='' if client else '21',
                         samples=[] if client else [dict(mind=0, target=False, crawling=False,
                                                         left='100', right='100', alive=True,
                                                         position='6500 0 2500') for _ in range(2)],
                         doors=[dict(index=0, opened=False, locked=True)] if trial['kind'] == 'door_state' else [],
                         geometry=[] if client else [0, 0, 0, 0]))
        if trial['kind'] in ('limb_damage', 'crawl_health_only'):
            rows[-1]['samples'][1]['left'] = '0'
    return dict(schema=1, kind=probe.OBSERVATIONS_KIND, hook_sha256=plan['probe']['hook_sha256'],
                status='complete', world='chernarusplus', version='1.30.164289',
                clients=0, spawned=sum(r['spawned'] for r in rows),
                deleted=sum(r['deleted'] for r in rows), trials=rows)


class HookTests(unittest.TestCase):
    def test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded(self):
        hook = probe.render_hook().decode('ascii')
        step = hook.split('    void HCICStep()')[1].split('    void HCICObserve()')[0]
        for variable in ('anchor', 'spawnPoint'):
            call = f'{variable}[1] = GetGame().SurfaceY({variable}[0], {variable}[2]);'
            self.assertIn(call, step)
            self.assertLess(step.index(call), step.index('Building structure ='))
        self.assertIn(('3_Game/Global/Game.c', 1176, 'SurfaceY'), probe.NATIVE)
        for field in ('anchor_authored_y', 'anchor_surface_y', 'spawn_authored_y', 'spawn_surface_y'):
            self.assertIn(f'm_Trial.{field} =', step)
        self.assertIn('GetObjectsAtPosition3D(anchor, 5.0,', hook)

    def test_f7_client_elapsed_is_explicitly_zero(self):
        hook = probe.render_hook().decode('ascii')
        method = hook.split('    void HCICNext()')[1].split('    void HCICWatchdog()')[0]
        self.assertRegex(method, r'if \(m_Trial.support_state == "client_required"\)\s+m_Trial.elapsed_ms = 0;\s+else\s+m_Trial.elapsed_ms = GetGame\(\).GetTime\(\) - m_TrialBegin;')

    def test_server_trials_and_explicit_client_exclusions(self):
        trials = probe.default_trials()
        self.assertEqual(len(trials), 9)
        self.assertEqual(sum(t['support_state'] == 'client_required' for t in trials), 3)
        self.assertTrue(all(t['reason'] for t in trials))
        hook = probe.render_hook().decode('ascii')
        for api in ('GetMindState()', 'GetTargetEntity()', 'IsDoorOpen(', 'IsDoorLocked(',
                    'RaycastRV(', 'DecreaseHealth(', 'IsCrawling()', 'ObjectDelete('):
            self.assertIn(api, hook)
        for forbidden in ('SetPosition(', 'OpenDoor(', 'CloseDoor(', 'LockDoor(', 'AddNoise(',
                          'OverrideMovementSpeed(', 'StartCommand_Crawl(', 'ProcessDirectDamage('):
            self.assertNotIn(forbidden, hook)
        self.assertIn('m_Owned', hook)
        self.assertIn('HCICCleanup();', hook)
        self.assertIn('override void OnMissionFinish()', hook)
        self.assertIn('GetPlayerIndentities', hook)
        self.assertIn('HCInfectedCompetence/complete.txt', hook)

    def test_compile_shape_against_real_cache(self):
        self.assertTrue(CACHE.is_dir(), 'pinned native cache required, never silently skip lint')
        hook = probe.render_hook().decode('ascii')
        self.assertEqual(rt.lint_hook(hook, native_types=rt.native_type_names(CACHE),
                                      explicit_numbers=True), [])
        self.assertLessEqual(rt.max_statement_plus(hook), 8)
        evidence = probe.verify_native(CACHE)
        self.assertTrue(evidence)
        self.assertTrue(all(row['line'] > 0 for row in evidence))

    def test_bounds_and_injection_rejected(self):
        for value in ([], probe.default_trials() * 101, True):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'trials must contain'):
                probe.render_hook(trials=value)
        for duration in (0, 60001, True):
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, 'per trial ms'):
                probe.render_hook(per_trial_ms=duration)
        trials = probe.default_trials()
        trials[0]['structure'] = 'Bad"; Teleport()'
        with self.assertRaisesRegex(ValueError, 'plain identifiers'):
            probe.render_hook(trials=trials)
        trials = probe.default_trials()
        trials[0]['position'][0] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite numeric position'):
            probe.render_hook(trials=trials)

    def test_check_trials_each_guard_and_plus_budget(self):
        cases = [('kind', 'unknown', 'unknown trial kind'),
                 ('support_state', 'client_required', 'support state mismatch'),
                 ('reason', 'invented', 'canonical support reason'),
                 ('fixture_status', 'accepted', 'fixture status'),
                 ('position', [6550, 0, 2500], 'within 20m'),
                 ('position', [-1, 0, 2500], 'outside Chernarus'),
                 ('position', [16000, 0, 2500], 'outside Chernarus'),
                 ('structure_position', [6500, 2001, 2500], 'outside Chernarus'),
                 ('position', [6500, -101, 2500], 'outside Chernarus'),
                 ('position', [6500, 0], 'three-coordinate'),
                 ('position', [True, 0, 2500], 'finite numeric'),
                 ('position', [math.inf, 0, 2500], 'finite numeric')]
        for field, value, message in cases:
            trials = probe.default_trials()
            trials[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, message):
                probe.check_trials(trials)
        trials = probe.default_trials()
        trials[1]['id'] = trials[0]['id']
        with self.assertRaisesRegex(ValueError, 'duplicate trial id'):
            probe.check_trials(trials)
        trials = [dict(probe.default_trials()[0], id=f't{i:03}') for i in range(101)]
        with self.assertRaisesRegex(ValueError, 'trials must contain 1..100'):
            probe.check_trials(trials)
        with mock.patch.object(rt, 'max_statement_plus', return_value=9):
            with self.assertRaisesRegex(ValueError, 'eight binary plus'):
                probe.render_hook()

    def test_hook_cleanup_ownership_guards_and_bounds_structure(self):
        hook = probe.render_hook().decode('ascii')

        def body(name):
            start = re.search(r'\b' + name + r'\([^)]*\)\s*\{', hook).end()
            depth = 1
            for index in range(start, len(hook)):
                depth += (hook[index] == '{') - (hook[index] == '}')
                if depth == 0:
                    return hook[start:index]
            self.fail('unterminated method ' + name)

        for name in ('HCICNext', 'HCICFinish', 'OnMissionFinish'):
            self.assertIn('HCICCleanup();', body(name), name)
        cleanup = body('HCICCleanup')
        for statement in ('if (m_Owned)', 'GetGame().ObjectDelete(m_Owned);',
                          'm_Receipt.deleted = m_Receipt.deleted + 1;',
                          'm_Trial.deleted = m_Trial.deleted + 1;', 'm_Owned = null;', 'm_Actor = null;'):
            self.assertIn(statement, cleanup)
        self.assertLess(cleanup.index('ObjectDelete'), cleanup.index('m_Owned = null;'))
        no_clients = body('HCICNoClients')
        self.assertRegex(no_clients, r'if \(identities.Count\(\) != 0\)\s*\{\s*m_Receipt.clients = identities.Count\(\);\s*HCICFinish\("partial"\);\s*return false;')
        for name in ('HCICStep', 'HCICObserve'):
            self.assertRegex(body(name), r'if \(!HCICNoClients\(\)\)\s*return;')
        step = body('HCICStep')
        self.assertRegex(step, r'if \(GetGame\(\).GetTime\(\) - m_Begin > 84900\)\s*\{\s*HCICFinish\("partial"\);\s*return;')
        client_branch = re.search(r'if \(m_Trial.support_state == "client_required"\)\s*\{([^}]+)\}', step)
        self.assertIsNotNone(client_branch)
        self.assertIn('m_Trial.status = "client_required";', client_branch[1])
        self.assertRegex(client_branch[1], r'HCICNext\(\);\s*return;')
        self.assertNotIn('CreateObjectEx', client_branch[1])
        self.assertLess(step.index(client_branch[0]), step.index('CreateObjectEx'))
        self.assertEqual(hook.count('CreateObjectEx('), 1)
        self.assertIn('m_Owned = GetGame().CreateObjectEx("ZmbF_JournalistNormal_Blue", spawnPoint, ECE_PLACE_ON_SURFACE|ECE_INITAI);', step)
        self.assertRegex(step, r'if \(m_Owned\)\s*\{\s*m_Trial.spawned = 1;\s*m_Receipt.spawned = m_Receipt.spawned \+ 1;')
        self.assertIn('ZombieBase.Cast(m_Owned)', step)
        self.assertIn('doorIndex < doorCount && doorIndex < 16', step)
        self.assertIn('if (doorCount < 1 || doorCount > 16)', step)
        self.assertIn('if (legHealth <= 0 || legHealth > 10000)', step)
        self.assertIn('rayIndex < 4', body('HCICGeometry'))
        structure = body('HCICStructure')
        self.assertRegex(structure, r'if \(nearby.Count\(\) > 128 \|\| proxyCargos.Count\(\) > 128\)\s*return null;')
        self.assertIn('scanIndex < nearby.Count() && scanIndex < 128', structure)
        self.assertRegex(structure, r'if \(matches != 1\)\s*return null;')
        self.assertIn('CallLater(HCICWatchdog, 124900, false);', body('OnInit'))
        self.assertRegex(body('HCICWatchdog'), r'if \(m_Ready && !m_Done\)\s*HCICFinish\("partial"\);\s*m_Done = true;')
        finish = body('HCICFinish')
        self.assertRegex(finish, r'if \(outputData.Length\(\) > 262144\)\s*return;')
        self.assertIn('FPrintln(sentinelFile, "status=" + outcome);', finish)
        self.assertLess(finish.index('CloseFile(outputFile)'), finish.index('FPrintln(sentinelFile'))


class StagingAndReceiptTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = make_source_runtime(self.root / 'vanilla')
        config = b'hostname = "SYNTHETIC";\nmaxPlayers = 6;\n'
        (self.source / 'serverDZ.cfg').write_bytes(config)
        source_plan = json.loads((self.source / 'launch-plan.json').read_text())
        source_plan['config_sha256'] = rt.sha256(config)
        (self.source / 'launch-plan.json').write_text(json.dumps(source_plan))
        self.dest = self.root / 'infected-test'

    def stage(self):
        # Explicit integration stand-ins; never mutate shared production files.
        with mock.patch.dict(dm._PURPOSES, {probe.PURPOSE: probe.PURPOSE_ROW}), \
                mock.patch.dict(rt.LAUNCHER_PROBES, {probe.PURPOSE: probe.LAUNCHER_ROW}):
            return probe.stage(self.source, self.dest, native_scripts=CACHE,
                               battleye_sha256=SYNTH_BE_SHA, _wsl_parent=self.root)

    def write_receipt(self, receipt):
        directory = self.dest / 'profiles/HCInfectedCompetence'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'observations.json').write_text(json.dumps(receipt))
        (directory / 'complete.txt').write_text('status=complete\n')

    def test_survey_read_only_even_placements_yaw_provenance_and_stage(self):
        # Tiny invented mapgrouppos, never copied from game files. Angles are rpy degrees.
        xml = b'<map>' + b''.join(
            f'<group name="Land_Synthetic" pos="{100 + i * 10} 17 200" rpy="0 0 90"/>'.encode()
            for i in range(6)) + b'<group name="Land_Other" pos="500 12 500" rpy="0 0 0"/></map>'
        stock = self.root / 'synthetic-mapgrouppos.xml'
        stock.write_bytes(xml)
        output_path = self.root / 'trials.json'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path),
                                         '--classes', 'Land_Synthetic', '--per-class', '2']), 0)
        document = json.loads(output_path.read_text())
        self.assertEqual(stock.read_bytes(), xml)
        self.assertEqual(document['survey']['stock_sha256'], hashlib.sha256(xml).hexdigest())
        parameters = document['survey']['selection']
        self.assertEqual(parameters['classes'], ['Land_Synthetic'])
        self.assertEqual(parameters['per_class'], 2)
        self.assertEqual(parameters['spawn_offset_m'], 3.0)
        self.assertEqual(parameters['yaw_component'], 'rpy[2] degrees')
        trials = document['trials']
        self.assertEqual(len(trials), 18)
        self.assertEqual({t['structure_position'][0] for t in trials}, {110, 140})
        for trial in trials:
            self.assertEqual(trial['fixture_status'], 'stock-derived')
            self.assertEqual(trial['structure_position'][1], 17)
            self.assertAlmostEqual(trial['position'][0], trial['structure_position'][0] + 3)
            self.assertAlmostEqual(trial['position'][2], 200)
        with mock.patch.object(probe, 'stage', return_value={'probe': {'hook_sha256': 'test'}}) as staging, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(probe.main(['stage', '--destination', str(self.dest), '--trials-json', str(output_path)]), 0)
            self.assertEqual(staging.call_args.kwargs['trials'], document)
        self.assertNotIn('omitted', error.getvalue())
        plan = probe.stage(self.source, self.dest, trials=document, native_scripts=CACHE,
                           battleye_sha256=SYNTH_BE_SHA, _wsl_parent=self.root)
        self.assertEqual(plan['fixture_survey'], document['survey'])
        self.write_receipt(synthetic_receipt(plan))
        self.assertEqual(probe.validate(self.dest)['fixture_status_counts'], {'stock-derived': 18})
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path)]), 1)
        self.assertEqual(stock.read_bytes(), xml)

    def test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output(self):
        stock = self.root / 'synthetic-mapgrouppos.xml'
        output_path = self.root / 'trials.json'
        cases = [
            (b'<!DOCTYPE map><map/>', [], 'DOCTYPE'),
            (b'<map/>', [], 'no selected placements'),
            (b'<map><group name="Land_Synthetic" pos="100 0 200" rpy="0 NaN 0"/></map>', [], 'finite rpy'),
            (b'<map><group name="Land_Synthetic" pos="100 0 200"/></map>', [], 'rpy'),
            (b'<map><group name="Land_Synthetic" pos="100 0 200" rpy="0 0 0"/></map>', ['--classes', 'Land_Missing'], 'missing selected classes'),
            (b'<map><group name="Land_Synthetic" pos="100 0 200" rpy="0 0 0"/></map>', ['--per-class', '0'], 'per class'),
            (b'<map><group name="Land_Synthetic" pos="100 0 200" rpy="0 0 0"/></map>', ['--spawn-offset-m', 'nan'], 'spawn offset'),
            (b'<map>' + b''.join(f'<group name="Land_Synthetic" pos="{100+i} 0 200" rpy="0 0 0"/>'.encode() for i in range(12)) + b'</map>', ['--per-class', '12'], '1..100'),
        ]
        for xml, arguments, message in cases:
            stock.write_bytes(xml)
            with self.subTest(message=message), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path)] + arguments), 1)
                self.assertIn(message, error.getvalue())
                self.assertFalse(output_path.exists())
            self.assertEqual(stock.read_bytes(), xml)

    def test_missing_real_registration_fails_loudly_before_staging(self):
        with mock.patch.dict(dm._PURPOSES), mock.patch.dict(rt.LAUNCHER_PROBES):
            dm._PURPOSES.pop(probe.PURPOSE, None)
            rt.LAUNCHER_PROBES.pop(probe.PURPOSE, None)
            with self.assertRaisesRegex(ValueError, 'registration'):
                probe.stage(self.source, self.dest, native_scripts=CACHE,
                            battleye_sha256=SYNTH_BE_SHA, _wsl_parent=self.root)
        self.assertFalse(self.dest.exists())

    def test_stage_refuses_native_drift_and_lint_before_destination(self):
        for function, kwargs, message in (
                ('verify_native', {'side_effect': ValueError('native API evidence missing/drift: SYNTHETIC')}, 'native API evidence missing/drift'),
                ('lint_hook', {'return_value': ['SYNTHETIC compile refusal']}, 'generated hook violates native compile rules')):
            owner = probe if function == 'verify_native' else rt
            with self.subTest(function=function), mock.patch.object(owner, function, **kwargs) as guard:
                with self.assertRaisesRegex(ValueError, message):
                    self.stage()
                guard.assert_called_once()
                self.assertFalse(self.dest.exists())

    def test_stage_entity_and_wait_bounds_follow_explicit_trials(self):
        trials = [dict(probe.default_trials()[0], id=f't{i:03}') for i in range(100)]
        plan = probe.stage(self.source, self.dest, trials=trials, per_trial_ms=60000,
                           native_scripts=CACHE, battleye_sha256=SYNTH_BE_SHA, _wsl_parent=self.root)
        self.assertEqual(plan['probe']['max_spawned_entities'], 100)
        self.assertEqual(plan['probe']['wait_minutes'], 106)
        self.assertEqual(plan['probe']['max_live_entities'], 1)
        self.assertEqual(plan['probe']['max_output_bytes'], 262144)
        # The default plan computes six minutes, below the mutated 50-minute floor (S13).
        self.dest = self.root / 'short-probe'
        plan = self.stage()
        self.assertEqual(plan['probe']['max_spawned_entities'], 6)
        self.assertEqual(plan['probe']['wait_minutes'], 6)

    def test_staged_config_and_each_init_binding_guard(self):
        plan = self.stage()
        self.write_receipt(synthetic_receipt(plan))
        config = self.dest / 'serverDZ.cfg'
        original = config.read_bytes()
        config.write_bytes(original + b'// SYNTHETIC drift\n')
        with self.assertRaisesRegex(ValueError, 'staged config mismatch'):
            probe.validate(self.dest)
        config.write_bytes(original)
        initial = self.dest / 'mpmissions' / rt.MISSION_NAME / 'init.c'
        original_init = initial.read_bytes()
        initial.write_bytes(b'// SYNTHETIC prefix\n' + original_init)
        with self.assertRaisesRegex(ValueError, 'staged hook init hash mismatch'):
            probe.validate(self.dest)
        initial.write_bytes(original_init + b'// SYNTHETIC suffix\n')
        pinned = next(row for row in plan['staged_files'] if row['path'].endswith('/init.c'))
        pinned['sha256'] = rt.sha256(initial.read_bytes())
        (self.dest / probe.PLAN_NAME).write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, 'staged hook-sha mismatch'):
            probe.validate(self.dest)

    def test_stage_is_fresh_pinned_no_clients_and_never_launches(self):
        with mock.patch('subprocess.Popen', side_effect=AssertionError('must stage only')):
            plan = self.stage()
        self.assertEqual(plan['status'], 'staged-only-not-launched')
        self.assertEqual(plan['acceptance'], 'PENDING')
        self.assertEqual((self.dest / 'serverDZ.cfg').read_bytes(),
                         (self.source / 'serverDZ.cfg').read_bytes())
        self.assertEqual((self.source / 'serverDZ.cfg').read_bytes(),
                         b'hostname = "SYNTHETIC";\nmaxPlayers = 6;\n')
        self.assertEqual(list((self.dest / 'profiles').iterdir()), [])
        hook = probe.render_hook()
        self.assertEqual(plan['probe']['hook_sha256'], hashlib.sha256(hook).hexdigest())
        self.assertEqual((self.dest / probe.HASH_RELATIVE).read_text(), rt.sha256(hook))
        for entry in plan['staged_files']:
            self.assertEqual(rt._hash_file(self.dest / entry['path'])[0], entry['sha256'])
        self.assertEqual(probe.validate_plan(plan), hook)
        with self.assertRaisesRegex(ValueError, 'destination must be fresh'):
            self.stage()

    def test_receipt_denominator_and_inconclusive_are_honest(self):
        plan = self.stage()
        receipt = synthetic_receipt(plan)
        receipt['trials'][0].update(status='inconclusive', reason='structure_missing', observed=False,
                                    spawned=0, deleted=0, samples=[])
        receipt['spawned'] -= 1
        receipt['deleted'] -= 1
        self.write_receipt(receipt)
        result = probe.validate(self.dest)
        self.assertEqual(result['denominator'], dict(attempted=6, completed=5, inconclusive=1,
                                                     client_required=3))
        self.assertEqual(result['runtime_acceptance'], 'PENDING')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(probe.main(['report', str(self.dest)]), 0)
        self.assertEqual(json.loads(output.getvalue())['denominator'], result['denominator'])

    def test_refuse_incomplete_and_bad_sentinel(self):
        plan = self.stage()
        receipt = synthetic_receipt(plan)
        self.write_receipt(receipt)
        sentinel = self.dest / probe.SENTINEL_RELATIVE
        sentinel.unlink()
        with self.assertRaises((OSError, ValueError)):
            probe.validate(self.dest)
        sentinel.write_text('status=partial\n')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            probe.validate(self.dest)

    def test_refuse_hash_unknown_kind_client_observations_and_cleanup_lies(self):
        plan = self.stage()
        original = synthetic_receipt(plan)
        mutations = [
            ('hash', lambda r: r.update(hook_sha256='0' * 64), 'receipt hook-sha mismatch'),
            ('unknown kind', lambda r: r['trials'][0].update(kind='wall_teleport'), 'unknown trial kind'),
            ('identity', lambda r: r['trials'][0].update(id='different'), 'identity/support mismatch'),
            ('client observed', lambda r: r['trials'][-1].update(observed=True), 'client_required trial cannot be observed'),
            ('client status', lambda r: r['trials'][-1].update(status='completed'), 'client_required trial cannot be observed'),
            ('row cleanup', lambda r: r['trials'][0].update(deleted=0), 'incomplete cleanup'),
            ('totals', lambda r: r.update(deleted=r['deleted'] - 1), 'run cleanup totals mismatch'),
            ('partial', lambda r: r.update(status='partial'), 'incomplete or client-contaminated'),
            ('clients', lambda r: r.update(clients=1), 'incomplete or client-contaminated'),
            ('denominator', lambda r: r['trials'].pop(), 'incomplete trial denominator'),
            ('elapsed', lambda r: r['trials'][0].update(elapsed_ms=60001), 'trial elapsed'),
            ('nonfinite', lambda r: r['trials'][0]['samples'][0].update(left='NaN'), 'nonfinite sample'),
            ('limb range', lambda r: r['trials'][0]['samples'][0].update(left='10001'), 'invalid limb sample'),
            ('observed iff completed', lambda r: r['trials'][0].update(observed=False), 'invalid trial outcome'),
            ('completed spawn', lambda r: r['trials'][0].update(spawned=0, deleted=0), 'completed trial needs'),
            ('completed samples', lambda r: r['trials'][0].update(samples=[]), 'completed trial needs'),
            ('door outside', lambda r: r['trials'][0].update(doors=[dict(index=0, opened=False, locked=False)]), 'outside door-state'),
            ('target', lambda r: r['trials'][0]['samples'][0].update(target=True), 'no-target control contaminated'),
            ('dead', lambda r: r['trials'][0]['samples'][0].update(alive=False), 'no-target control contaminated'),
            ('sample bound', lambda r: r['trials'][0]['samples'].append(copy.deepcopy(r['trials'][0]['samples'][0])), 'bounded sample/door/geometry arrays'),
            ('door bound', lambda r: r['trials'][2].update(doors=[dict(index=i, opened=False, locked=False) for i in range(17)]), 'bounded sample/door/geometry arrays'),
            ('ray bound', lambda r: r['trials'][0]['geometry'].append(0), 'bounded sample/door/geometry arrays'),
            ('reason length', lambda r: r['trials'][0].update(reason='x' * 257), 'bounded outcome reason'),
            ('reason empty', lambda r: r['trials'][0].update(reason=''), 'bounded outcome reason'),
            ('door index', lambda r: r['trials'][2]['doors'][0].update(index=1), 'invalid door observation'),
        ]
        for label, mutate, message in mutations:
            receipt = copy.deepcopy(original)
            mutate(receipt)
            self.write_receipt(receipt)
            with self.subTest(mutation=label), self.assertRaisesRegex(ValueError, message):
                probe.validate(self.dest)

    def test_client_required_each_field_refused_independently(self):
        plan = self.stage()
        original = synthetic_receipt(plan)
        server_sample = original['trials'][0]['samples'][0]
        fields = dict(observed=True, status='completed', spawned=1, samples=[server_sample],
                      doors=[dict(index=0, opened=False, locked=True)], geometry=[0], elapsed_ms=1,
                      reason='unsupported reason', anchor_authored_y='0', anchor_surface_y='1',
                      spawn_authored_y='0', spawn_surface_y='1')
        for field, value in fields.items():
            receipt = copy.deepcopy(original)
            row = receipt['trials'][-1]
            row[field] = value
            if field == 'spawned':
                row['deleted'] = 1
                receipt['spawned'] += 1
                receipt['deleted'] += 1
            message = ('client-required reason mismatch' if field == 'reason' else
                       'client_required trial cannot contain terrain' if field.endswith('_y') else
                       'client_required trial cannot be observed')
            self.write_receipt(receipt)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                probe.validate(self.dest)

    def test_plan_and_staged_hook_tamper_refused(self):
        plan = self.stage()
        self.write_receipt(synthetic_receipt(plan))
        path = self.dest / probe.PLAN_NAME
        plan['probe']['hook_sha256'] = '0' * 64
        path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, 'hook'):
            probe.validate(self.dest)

    def test_output_budget_and_duplicate_keys_refused(self):
        plan = self.stage()
        self.write_receipt(synthetic_receipt(plan))
        output = self.dest / probe.OUTPUT_RELATIVE
        output.write_bytes(b' ' * (probe.MAX_OUTPUT_BYTES + 1))
        with self.assertRaisesRegex(ValueError, 'byte limit|budget'):
            probe.validate(self.dest)
        output.write_text('{"schema":1,"schema":1}')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            probe.validate(self.dest)

    def test_completed_records_require_kind_specific_evidence_and_pinned_build(self):
        plan = self.stage()
        original = synthetic_receipt(plan)
        mutations = [(lambda r: r.update(world='enoch'), 'pinned Chernarus/build'),
                     (lambda r: r.update(version='1.29.1'), 'pinned Chernarus/build'),
                     (lambda r: r.update(clients=False), 'incomplete or client-contaminated'),
                     (lambda r: r['trials'][0].update(geometry=[]), 'completed trial needs'),
                     (lambda r: r['trials'][0].update(elapsed_ms=1), 'completed trial needs'),
                     (lambda r: r['trials'][2].update(doors=[]), 'completed door trial needs'),
                     (lambda r: r['trials'][-1].update(attack_observed=True), 'trial record fields')]
        for index, (mutate, message) in enumerate(mutations):
            receipt = copy.deepcopy(original)
            mutate(receipt)
            self.write_receipt(receipt)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, message):
                probe.validate(self.dest)

    def test_native_cache_required_and_config_duplicates_refused_before_writes(self):
        with self.assertRaises((ValueError, OSError)):
            probe.verify_native(self.root / 'missing-native')

    def test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound(self):
        plan = self.stage()
        receipt = synthetic_receipt(plan)
        cap = len(plan['trials']) * (plan['probe']['per_trial_ms'] + 1100) + 30000
        row = receipt['trials'][0]
        row.update(status='inconclusive', observed=False, reason='trial_time_budget', elapsed_ms=6070)
        self.write_receipt(receipt)
        self.assertEqual(probe.validate(self.dest)['denominator']['inconclusive'], 1)
        row['elapsed_ms'] = cap
        self.write_receipt(receipt)
        probe.validate(self.dest)
        row['elapsed_ms'] = cap + 1
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ValueError, 'trial elapsed'):
            probe.validate(self.dest)
        row.update(status='completed', observed=True, elapsed_ms=6001)
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ValueError, 'trial elapsed'):
            probe.validate(self.dest)

    def test_f1_authored_height_roundtrip_and_invalid_height_receipts(self):
        plan = self.stage()
        original = synthetic_receipt(plan)
        original['trials'][0]['anchor_authored_y'] = '0.000004'
        self.write_receipt(original)
        probe.validate(self.dest)  # Enforce floats/ToString need a small numeric tolerance.
        for field, value, message in (('anchor_authored_y', '0.1', 'authored terrain height mismatch'),
                                      ('spawn_authored_y', '0.1', 'authored terrain height mismatch'),
                                      ('anchor_surface_y', 'NaN', 'nonfinite sample'),
                                      ('spawn_surface_y', 'NaN', 'nonfinite sample')):
            receipt = copy.deepcopy(original)
            receipt['trials'][0][field] = value
            self.write_receipt(receipt)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                probe.validate(self.dest)

    def test_f3_health_only_labels_drop_and_shared_coverage(self):
        self.assertNotIn('crawl_transition', probe.KINDS)
        self.assertIn('hit-path not exercised', probe.KINDS['crawl_health_only'][1])
        plan = self.stage()
        original = synthetic_receipt(plan)
        self.write_receipt(original)
        result = probe.validate(self.dest)
        self.assertEqual(result['completed_observation_paths'],
                         ['spawn_state_geometry_door_reads', 'leg_health_only'])
        self.assertTrue(any('distinct coverage' in text for text in result['limitations']))
        for kind in ('limb_damage', 'crawl_health_only'):
            for after in ('100', '101'):
                receipt = copy.deepcopy(original)
                row = next(r for r in receipt['trials'] if r['kind'] == kind)
                row['samples'][1]['left'] = after
                self.write_receipt(receipt)
                with self.subTest(kind=kind, after=after), self.assertRaisesRegex(ValueError, 'left-leg health must fall'):
                    probe.validate(self.dest)

    def test_f5_fixture_status_printed_and_default_stage_warning(self):
        plan = self.stage()
        self.write_receipt(synthetic_receipt(plan))
        for command in ('validate', 'report'):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(probe.main([command, str(self.dest)]), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result['fixture_status_counts'], {'unqualified-candidate': 9})
            self.assertTrue(any('not the #18 building/angle denominator' in text for text in result['limitations']))
        with mock.patch.object(probe, 'stage', return_value=plan), contextlib.redirect_stderr(io.StringIO()) as error, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main(['stage', '--destination', str(self.dest)]), 0)
        self.assertIn('--trials-json omitted', error.getvalue())

    def test_f8_exact_nested_and_document_fields(self):
        plan = self.stage()
        original = synthetic_receipt(plan)
        for location, message in (('document', 'document fields'), ('sample', 'sample fields'), ('door', 'door observation')):
            for remove in (False, True):
                receipt = copy.deepcopy(original)
                target = {'document': receipt, 'sample': receipt['trials'][0]['samples'][0],
                          'door': receipt['trials'][2]['doors'][0]}[location]
                if remove:
                    del target[{'document': 'deleted', 'sample': 'right', 'door': 'locked'}[location]]
                else:
                    target['attack_observed'] = True
                self.write_receipt(receipt)
                with self.subTest(location=location, remove=remove), self.assertRaisesRegex(ValueError, message):
                    probe.validate(self.dest)

    def test_sidecar_and_hook_bytes_tamper_refused(self):
        plan = self.stage()
        self.write_receipt(synthetic_receipt(plan))
        sidecar = self.dest / probe.HASH_RELATIVE
        sidecar.write_text('0' * 64)
        with self.assertRaisesRegex(ValueError, 'hook'):
            probe.validate(self.dest)
        sidecar.write_text(plan['probe']['hook_sha256'])
        initial = self.dest / 'mpmissions' / rt.MISSION_NAME / 'init.c'
        initial.write_bytes(initial.read_bytes() + b'// tampered')
        with self.assertRaisesRegex(ValueError, 'hook'):
            probe.validate(self.dest)


if __name__ == '__main__':
    unittest.main()
