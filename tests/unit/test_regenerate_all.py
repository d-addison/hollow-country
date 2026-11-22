"""Read-only aggregate orchestration, inventory coverage and privacy contracts."""
import ast
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.package import regenerate_all as regen
from tools.release.ship_inputs import ADDONS


class RegenerateAllTests(unittest.TestCase):
    def invoke(self, args=(), **patches):
        with contextlib.ExitStack() as stack:
            for name, value in patches.items():
                stack.enter_context(patch.object(regen, name, **value))
            output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            code = regen.main(list(args))
        return code, output.getvalue()

    def test_every_argparse_check_module_is_accounted_for(self):
        expected = set()
        for path in (regen.ROOT / 'tools/package').rglob('*.py'):
            tree = ast.parse(path.read_text())
            for call in ast.walk(tree):
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                    continue
                strings = {arg.value for arg in call.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
                flag = call.func.attr == 'add_argument' and '--check' in strings
                subcommand = call.func.attr == 'add_parser' and 'check' in strings
                choices = any(k.arg == 'choices' and any(isinstance(n, ast.Constant) and n.value == 'check'
                              for n in ast.walk(k.value)) for k in call.keywords)
                if flag or subcommand or (call.func.attr == 'add_argument' and choices):
                    expected.add('.'.join(path.relative_to(regen.ROOT / 'tools/package').with_suffix('').parts))
        names = [g.name for g in regen.GENERATORS]
        excluded = regen.EXCLUDED_CHECK_MODULES
        self.assertEqual(len(names), len(set(names)))
        self.assertFalse(set(names) & excluded.keys())
        self.assertTrue(all(reason.strip() for reason in excluded.values()))
        packaged = [g for g in regen.GENERATORS if g.package == 'tools.package']
        self.assertEqual(expected, {g.name for g in packaged if g.arguments} | excluded.keys())
        from tools.package.generated_digests import contracts
        self.assertEqual({g.name for g in regen.GENERATORS if g.digest}, {c.name for c in contracts()})
        self.assertEqual(set(names) - {c.name for c in contracts()}, {g.name for g in regen.GENERATORS if not g.digest})
        for generator in regen.GENERATORS:
            if not generator.digest:
                self.assertTrue((regen.ROOT / (generator.package.replace('.', '/') + '/' + generator.name + '.py')).is_file())

    def test_default_checks_run_every_generator_and_continue_after_failure(self):
        calls = []
        def check(generator, values, timeout):
            calls.append((generator.name, values, timeout))
            return ('FAIL', 'stale input') if generator.name == 'military_loot' else ('PASS', 'current')
        code, output = self.invoke(check_generator={'side_effect': check})
        self.assertEqual(1, code)
        self.assertEqual([g.name for g in regen.GENERATORS], [c[0] for c in calls])
        self.assertEqual(ADDONS, calls[0][1]['addons'])
        self.assertIn(f'checked={len(calls)} failed=1 skipped=0', output)
        self.assertEqual(len(calls) + 1, len(output.splitlines()))

    def test_skip_never_counts_as_checked_and_strict_mode_fails(self):
        skipped = {'return_value': ('SKIP', 'installed input unavailable')}
        for args, expected in (([], 0), (['--require-installed'], 1)):
            code, output = self.invoke(args, check_generator=skipped)
            self.assertEqual(expected, code)
            self.assertIn(f'checked=0 failed=0 skipped={len(regen.GENERATORS)}', output)
            self.assertNotIn('PASS ', output)

    def test_missing_installed_input_skips_without_launching(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(regen.subprocess, 'run') as run:
            values = {'addons': Path(temp) / 'absent'}
            generator = next(g for g in regen.GENERATORS if g.name == 'inventory_sizes')
            self.assertEqual('SKIP', regen.check_generator(generator, values, 2)[0])
            run.assert_not_called()
        generator = next(g for g in regen.GENERATORS if g.name == 'snafu_optional')
        self.assertIn('snafu report', regen.missing_inputs(generator, {'source': regen.ROOT, 'snafu_report': None}))

    def test_child_commands_use_real_check_clis_and_bounded_subprocesses(self):
        with tempfile.TemporaryDirectory() as temp:
            values = dict(addons=Path(temp), workshop=Path(temp), source=Path(temp),
                          snafu_report=Path(temp) / 'snafu.json', tactical_flava_report=Path(temp) / 'tf.json')
            def run(command, **kwargs):
                self.assertEqual(7, kwargs['timeout'])
                self.assertEqual(regen.ROOT, kwargs['cwd'])
                self.assertTrue(kwargs['capture_output'])
                if command[:2] == ['git', 'show']:
                    return subprocess.CompletedProcess(command, 0, '{}', '')
                self.assertIn('-B', command)
                self.assertNotIn('--write', command)
                if 'tools.package.loot_point_preserve' in command:
                    for flag in ('--prior', '--candidate'):
                        self.assertEqual('{}', Path(command[command.index(flag) + 1]).read_text())
                    self.assertEqual(regen.LOOT_OUTPUT, command[-1])
                self.assertTrue('--check' in command or 'check' in command or '--compare' in command)
                return subprocess.CompletedProcess(command, 0, 'ok', '')
            with patch.object(regen, 'missing_inputs', return_value=None), patch.object(regen.subprocess, 'run', side_effect=run) as child:
                for generator in regen.GENERATORS:
                    self.assertEqual('PASS', regen.check_generator(generator, values, 7)[0])
            expected = sum(bool(g.arguments) + bool(g.digest) for g in regen.GENERATORS) + len(regen.LOOT_REVISIONS)
            self.assertEqual(expected, child.call_count)

    def test_failed_history_is_failure_not_skip(self):
        generator = next(g for g in regen.GENERATORS if g.name == 'loot_point_preserve')
        result = subprocess.CompletedProcess([], 128, '', 'revision unavailable')
        with patch.object(regen.subprocess, 'run', return_value=result):
            status, reason = regen.check_generator(generator, {}, 2)
        self.assertEqual('FAIL', status)
        self.assertIn('historical prior input unavailable', reason)

    def test_failure_output_is_private_and_one_line(self):
        generator = regen.GENERATORS[0]
        sensitive = '/home/' + 'private-person/file'
        result = subprocess.CompletedProcess([], 1, 'stale generated artifact\n',
                                             sensitive + '\n' + 'Steam ID: ' + '7' * 17)
        with patch.object(regen.subprocess, 'run', return_value=result):
            status, reason = regen.check_generator(generator, {}, 2)
        self.assertEqual('FAIL', status)
        self.assertNotIn(sensitive, reason)
        self.assertNotIn('7' * 17, reason)
        self.assertNotIn('\n', reason)
        self.assertNotIn('private-person', regen.diagnostic(subprocess.CompletedProcess([], 1, '', sensitive)))

    def test_timeout_and_launch_errors_fail_without_exposing_exception(self):
        for error in (subprocess.TimeoutExpired('private command', 1), OSError('unavailable')):
            code, output = self.invoke(check_generator={'side_effect': error})
            self.assertEqual(1, code)
            self.assertIn(f'failed={len(regen.GENERATORS)} skipped=0', output)
            self.assertNotIn('private command', output)

    def test_write_is_not_supported(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            regen.main(['--write'])
        self.assertEqual(2, raised.exception.code)


if __name__ == '__main__':
    unittest.main()
