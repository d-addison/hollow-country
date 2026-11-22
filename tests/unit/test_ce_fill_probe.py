"""Synthetic tooling checks only; no DayZ behaviour is established here."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.setup import ce_fill_probe as probe, probe_runtime as rt


def mods():
    return {'-mod': [dict(path='E:\\HollowCountryLocal\\friend-local-1\\@Example',
                         pbos=[dict(path='addons/example.pbo', sha256='a'*64)])]}


class FillProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = dict(kind='ce-fill-probe', status='staged-only-not-launched', variant='t0',
                         layers=list(probe.TREATMENTS['t0']), mods=mods(), mod_source={'authority': 'synthetic'},
                         stock_mission_sha256='b'*64, run_id='synthetic', hold_seconds=240,
                         server_exe_sha256=rt.SERVER_EXE_SHA256, staged_utc='2026-11-21T00:00:00Z',
                         runtime_root=rt.WINDOWS_PARENT+'\\synthetic-fill',
                         authored_inputs_sha256='c'*64, tool_sha256={'synthetic.py': 'd'*64})
        self.plan['arguments'] = rt.server_arguments(self.plan['runtime_root'], self.plan['mods'])
        self.plan['binding'] = probe.binding(self.plan)
        self.plan_path = self.root/probe.PLAN_NAME

    def lines(self, types=('Example', 'Example', 'Other')):
        token = self.plan['binding']
        return ['23:58:00.000 [CE][LootRespawner] :: Initially (re)spawned:1, Nominal:10, Total in Map: 10',
                *[f'23:58:01.000 [CE][LootRespawner] (PRIDummy) :: Item [{i}] is hard to place, performance drops: "{name}"'
                  for i, name in enumerate(types)],
                f'23:58:02.000 [HC FillProbe] begin binding={token}',
                f' 0:02:02.000 [HC FillProbe] done binding={token}']

    def ingest(self, lines):
        self.plan_path.write_text(json.dumps(self.plan))
        rpt = self.root/'sample.RPT'
        rpt.write_text('\n'.join(lines))
        return probe.ingest(rpt, self.root/'result.json', self.plan_path)

    def test_counts_pre_oninit_fill_and_midnight_hold_and_provenance(self):
        types = ('Example', 'Other', 'Example')
        result = self.ingest(self.lines(types))
        self.assertEqual(result['total'], len(types))
        self.assertEqual(result['types']['Example']['count'], types.count('Example'))
        self.assertEqual(result['mission_hold_seconds'], self.plan['hold_seconds'])
        self.assertEqual(result['provenance']['plan_sha256'], rt.sha256(self.plan_path.read_bytes()))
        self.assertEqual(result['provenance']['mods'], self.plan['mods'])

    def test_zero_warning_control_is_complete(self):
        self.assertEqual(self.ingest(self.lines(()))['types'], {})

    def test_incomplete_short_wrong_binding_and_late_warning_refused(self):
        lines = self.lines()
        cases = [lines[:-1], lines + [lines[1]],
                 lines[:-1] + [lines[-1].replace('0:02:02', '0:01:02')],
                 lines[:-1] + [lines[-1].replace(self.plan['binding'], 'f'*64)],
                 lines + [lines[-1]], lines[1:]]
        for case in cases:
            with self.subTest(case=cases.index(case)), self.assertRaises(ValueError):
                self.ingest(case)

    def test_binding_covers_treatment_mod_hashes_source_and_hold(self):
        for key in ('mods', 'hold_seconds', 'mod_source', 'layers', 'run_id', 'authored_inputs_sha256', 'tool_sha256'):
            changed = copy.deepcopy(self.plan)
            if key == 'mods':
                changed[key]['-mod'][0]['pbos'][0]['sha256'] = 'f'*64
            elif key == 'tool_sha256':
                changed[key]['synthetic.py'] = 'f'*64
            elif key == 'hold_seconds':
                changed[key] += 1
            elif key == 'layers':
                changed[key] = ['base']
            else:
                changed[key] = {'changed': True} if key == 'mod_source' else 'other'
            self.assertNotEqual(probe.binding(changed), self.plan['binding'])

    def test_mod_schema_refuses_arbitrary_paths_switches_and_duplicates(self):
        variants = [dict(mods(), **{'-config': []}),
                    {'-mod': [dict(path='C:\\arbitrary', pbos=mods()['-mod'][0]['pbos'])]},
                    {'-mod': mods()['-mod'] * 2}]
        for value in variants:
            with self.assertRaises(ValueError):
                rt.validate_mods(value)
        changed = mods()
        changed['-mod'][0]['pbos'][0]['path'] = '../example.pbo'
        with self.assertRaises(ValueError):
            rt.validate_mods(changed)

    def test_mod_verification_refuses_inventory_and_hash_drift(self):
        with patch.object(rt.dm, 'walk_plain', return_value={'addons/example.pbo': 1}), \
             patch.object(rt, '_hash_file', return_value=('f'*64, 1)):
            with self.assertRaisesRegex(ValueError, 'hash drift'):
                rt.validate_mods(mods(), verify=True)
        with patch.object(rt.dm, 'walk_plain', return_value={'addons/unlisted.pbo': 1}):
            with self.assertRaisesRegex(ValueError, 'inventory drift'):
                rt.validate_mods(mods(), verify=True)

    def test_receipted_launcher_is_authority_and_pbos_are_pinned(self):
        folder = self.root/'@Example'/'addons'
        folder.mkdir(parents=True)
        data = b'synthetic PBO bytes'
        (folder/'example.pbo').write_bytes(data)
        launcher = b'"-mod=@Example"'
        (self.root/'start-server.bat').write_bytes(launcher)
        receipt = {'files': {'start-server.bat': rt.sha256(launcher)}}
        path = self.root/probe.friend_install.RECEIPT
        path.write_text(json.dumps(receipt))
        actual, authority = probe.installed_mods(self.root)
        self.assertEqual(actual['-mod'][0]['pbos'][0]['sha256'], rt.sha256(data))
        self.assertEqual(authority['launcher_sha256'], rt.sha256(launcher))
        (self.root/'start-server.bat').write_bytes(launcher+b' drift')
        with self.assertRaisesRegex(ValueError, 'receipt'):
            probe.installed_mods(self.root)

    def test_optional_mods_leave_legacy_arguments_and_plan_bytes_identical(self):
        root = rt.WINDOWS_PARENT+'\\legacy-probe'
        expected_arguments = ['-ip=127.0.0.1', '-port='+str(rt.PORT), '-config='+root+'\\serverDZ.cfg',
            '-mission='+root+'\\mpmissions\\'+rt.MISSION_NAME, '-storage='+root+'\\storage',
            '-profiles='+root+'\\profiles', '-BEpath='+root+'\\battleye', '-doLogs', '-adminLog']
        context = dict(windows_root=root, source_runtime=self.root,
                       source={'launch_plan_sha256':'b'*64}, battleye_sha256='c'*64)
        built = {'staged_hash': {'serverDZ.cfg': 'd'*64}}
        expected = dict(server_exe=rt.SERVER_EXE, server_exe_sha256=rt.SERVER_EXE_SHA256,
            working_directory=rt.SERVER_INSTALL, port=rt.PORT, requested_bind='127.0.0.1:'+str(rt.PORT),
            runtime_root=root, mission=root+'\\mpmissions\\'+rt.MISSION_NAME,
            storage=root+'\\storage', profiles=root+'\\profiles', battleye=root+'\\battleye',
            arguments=expected_arguments, source=dict(runtime_wsl_path=str(self.root), launch_plan_sha256='b'*64,
            config_sha256='d'*64, battleye_sha256='c'*64))
        encode = lambda value: json.dumps(value, indent=2).encode()
        for empty in (None, {}):
            self.assertEqual(encode(rt.server_arguments(root, empty)), encode(expected_arguments))
            self.assertEqual(encode(rt.plan_runtime_fields(context, built, empty)), encode(expected))
        self.assertEqual(encode(rt.plan_runtime_fields(context, built)), encode(expected))
        self.assertEqual(rt.server_arguments(root, mods())[:-1], expected_arguments)
        self.assertEqual(rt.server_arguments(root, mods())[-1], '-mod='+mods()['-mod'][0]['path'])

    def test_hook_lint_and_treatment_cap(self):
        self.assertLessEqual(len(probe.TREATMENTS), probe.HARD_CAP)
        self.assertFalse(rt.lint_hook(probe.render_hook(self.plan['binding'], self.plan['hold_seconds']).decode()))
        for treatment in probe.TREATMENTS:
            with self.subTest(treatment=treatment):
                with self.assertRaises(ValueError):
                    probe.stage('unused', self.root/'unused', treatment=treatment, hold_seconds=239, dry_run=True)
