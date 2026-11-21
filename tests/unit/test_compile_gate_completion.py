"""Offline gate decisions using observed log syntax; never launch Wine or DayZ."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.release import compile_gate


class CompileCompletionTests(unittest.TestCase):
    # Retain only the relevant prefixes from cached run-1795243948522642708,
    # script_2026-11-21_01-52-29.log:73,76 (also present in its RPT).
    WORLD = '01:53:27.143 SCRIPT       : Module: World; loaded 3913x files;'
    MISSION = '01:55:04.706  SCRIPT       : Module: Mission; loaded 680x files;'

    def gate(self, script, status='timeout', seconds=None, rpt='', dump=False):
        with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
            root = Path(temp)
            output = io.StringIO()
            stack.enter_context(contextlib.redirect_stdout(output))
            stack.enter_context(patch.object(compile_gate, 'prerequisites',
                                             return_value=(root, root, None)))
            stack.enter_context(patch.object(compile_gate, 'source_tree',
                                             return_value=contextlib.nullcontext(root)))
            stack.enter_context(patch.object(compile_gate, 'ship_config'))
            stack.enter_context(patch.object(compile_gate, 'compatibility_inputs',
                                             return_value=contextlib.nullcontext({})))
            stack.enter_context(patch.object(compile_gate.pbo, 'collect_addon', return_value={}))
            stack.enter_context(patch.object(compile_gate.pbo, 'pack', return_value=b'fixture'))
            stack.enter_context(patch.object(compile_gate, 'stage_release_pbos', return_value={}))

            def run(server, package, experiment, prefix, **kwargs):
                profiles = experiment / 'profiles'
                profiles.mkdir(parents=True)
                (profiles / 'script_fixture.log').write_text(script)
                (profiles / 'server.RPT').write_text(rpt)
                if dump:
                    (profiles / 'ErrorMessage_fixture.mdmp').write_bytes(b'engine error')
                return {'status': status}

            probe = stack.enter_context(patch.object(compile_gate.probe, 'run', side_effect=run))
            argv = ['compile_gate', '--cache', str(root / 'cache')]
            if seconds is not None:
                argv += ['--seconds', str(seconds)]
            stack.enter_context(patch('sys.argv', argv))
            result = compile_gate.main()
            return result, output.getvalue(), probe.call_args.kwargs['seconds']

    def test_default_budget_requires_mission_on_timeout(self):
        result, output, seconds = self.gate(self.WORLD)
        self.assertEqual(seconds, 900)
        self.assertEqual(result, 1)
        self.assertIn('Mission load not observed', output)
        self.assertIn('FAIL status=timeout', output)

    def test_observed_mission_load_completes_compilation(self):
        result, output, seconds = self.gate(self.WORLD + '\n' + self.MISSION, seconds=300)
        self.assertEqual(seconds, 300)
        self.assertEqual(result, 0)
        self.assertIn('modules_loaded=World,Mission', output)
        self.assertIn('runtime acceptance pending', output)

    def test_rpt_mission_marker_alone_cannot_establish_script_load(self):
        result, _, _ = self.gate(self.WORLD, rpt=self.MISSION)
        self.assertEqual(result, 1)

    def test_initialized_status_does_not_replace_mission_marker(self):
        result, _, _ = self.gate(self.WORLD, status='initialized')
        self.assertEqual(result, 1)

    def test_errors_and_bad_status_still_refuse_after_mission(self):
        script = self.WORLD + '\n' + self.MISSION
        for kwargs in (
                {'rpt': "Can't compile Mission script module!"},
                {'rpt': 'SCRIPT (E): type error'},
                {'dump': True},
                {'status': 'engine-crash'},
                {'status': 'exited-before-initialization'}):
            with self.subTest(kwargs=kwargs):
                result, _, _ = self.gate(script, **kwargs)
                self.assertEqual(result, 1)

    def test_json_runtime_exception_still_requires_mission(self):
        error = '\nSCRIPT (E): JSON ERROR missing gate mission data'
        for mission, expected in (('', 1), ('\n' + self.MISSION, 0)):
            with self.subTest(mission=bool(mission)):
                result, _, _ = self.gate(self.WORLD + mission + error, status='compiler-error')
                self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
