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
                         samples=[] if client else [dict(mind=0, target=False, crawling=False,
                                                         left='100', right='100', alive=True,
                                                         position='6500 0 2500') for _ in range(2)],
                         doors=[dict(index=0, opened=False, locked=True)] if trial['kind'] == 'door_state' else [],
                         geometry=[] if client else [0, 0, 0, 0]))
    return dict(schema=1, kind=probe.OBSERVATIONS_KIND, hook_sha256=plan['probe']['hook_sha256'],
                status='complete', world='chernarusplus', version='1.30.164289',
                clients=0, spawned=sum(r['spawned'] for r in rows),
                deleted=sum(r['deleted'] for r in rows), trials=rows)


class HookTests(unittest.TestCase):
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
            with self.subTest(value=value), self.assertRaises(ValueError):
                probe.render_hook(trials=value)
        for duration in (0, 60001, True):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                probe.render_hook(per_trial_ms=duration)
        trials = probe.default_trials()
        trials[0]['structure'] = 'Bad"; Teleport()'
        with self.assertRaises(ValueError):
            probe.render_hook(trials=trials)
        trials = probe.default_trials()
        trials[0]['position'][0] = float('nan')
        with self.assertRaises(ValueError):
            probe.render_hook(trials=trials)


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

    def test_missing_real_registration_fails_loudly_before_staging(self):
        with mock.patch.dict(dm._PURPOSES), mock.patch.dict(rt.LAUNCHER_PROBES):
            dm._PURPOSES.pop(probe.PURPOSE, None)
            rt.LAUNCHER_PROBES.pop(probe.PURPOSE, None)
            with self.assertRaisesRegex(ValueError, 'registration'):
                probe.stage(self.source, self.dest, native_scripts=CACHE,
                            battleye_sha256=SYNTH_BE_SHA, _wsl_parent=self.root)
        self.assertFalse(self.dest.exists())

    def test_stage_is_fresh_pinned_no_clients_and_never_launches(self):
        with mock.patch('subprocess.Popen', side_effect=AssertionError('must stage only')):
            plan = self.stage()
        self.assertEqual(plan['status'], 'staged-only-not-launched')
        self.assertEqual(plan['acceptance'], 'PENDING')
        self.assertIn('maxPlayers = 0;', (self.dest / 'serverDZ.cfg').read_text())
        self.assertEqual((self.source / 'serverDZ.cfg').read_bytes(),
                         b'hostname = "SYNTHETIC";\nmaxPlayers = 6;\n')
        self.assertEqual(list((self.dest / 'profiles').iterdir()), [])
        hook = probe.render_hook()
        self.assertEqual(plan['probe']['hook_sha256'], hashlib.sha256(hook).hexdigest())
        self.assertEqual((self.dest / probe.HASH_RELATIVE).read_text(), rt.sha256(hook))
        for entry in plan['staged_files']:
            self.assertEqual(rt._hash_file(self.dest / entry['path'])[0], entry['sha256'])
        self.assertEqual(probe.validate_plan(plan), hook)
        with self.assertRaises(ValueError):
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
        mutations = [lambda r: r.update(hook_sha256='0' * 64),
                     lambda r: r['trials'][0].update(kind='wall_teleport'),
                     lambda r: r['trials'][-1].update(observed=True),
                     lambda r: r['trials'][-1].update(status='completed'),
                     lambda r: r['trials'][0].update(deleted=0),
                     lambda r: r.update(status='partial'),
                     lambda r: r.update(clients=1),
                     lambda r: r['trials'].pop(),
                     lambda r: r['trials'][0].update(elapsed_ms=60001),
                     lambda r: r['trials'][0]['samples'][0].update(left='NaN')]
        for mutate in mutations:
            receipt = copy.deepcopy(original)
            mutate(receipt)
            self.write_receipt(receipt)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
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
        with self.assertRaises(ValueError):
            probe.validate(self.dest)
        output.write_text('{"schema":1,"schema":1}')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            probe.validate(self.dest)

    def test_completed_records_require_kind_specific_evidence_and_pinned_build(self):
        plan = self.stage()
        original = synthetic_receipt(plan)
        mutations = [lambda r: r.update(world='enoch'),
                     lambda r: r.update(version='1.29.1'),
                     lambda r: r.update(clients=False),
                     lambda r: r['trials'][0].update(geometry=[]),
                     lambda r: r['trials'][0].update(elapsed_ms=1),
                     lambda r: r['trials'][2].update(doors=[]),
                     lambda r: r['trials'][-1].update(attack_observed=True)]
        for index, mutate in enumerate(mutations):
            receipt = copy.deepcopy(original)
            mutate(receipt)
            self.write_receipt(receipt)
            with self.subTest(index=index), self.assertRaises(ValueError):
                probe.validate(self.dest)

    def test_native_cache_required_and_config_duplicates_refused_before_writes(self):
        with self.assertRaises((ValueError, OSError)):
            probe.verify_native(self.root / 'missing-native')
        for config in (b'maxPlayers=6; maxPlayers=0;', b'// maxPlayers=0;\n',
                       b'maxPlayers=GetLimit();', b'maxPlayers="0";'):
            with self.subTest(config=config), self.assertRaises(ValueError):
                probe._no_clients_config(config)
        self.assertEqual(probe._no_clients_config(b'// maxPlayers=6;\nmaxPlayers=6;'),
                         b'// maxPlayers=6;\nmaxPlayers = 0;')

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
