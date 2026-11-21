"""Orchestration tests fake every gate and never launch DayZ."""
import contextlib
import io
import unittest
from unittest.mock import patch

from tools.validate import preland


class PrelandTests(unittest.TestCase):
    def invoke(self, args=(), codes=None, missing=()):
        calls = []
        def run(module, arguments):
            calls.append((module, arguments))
            return (codes or {}).get(module.rsplit('.', 1)[1], 0)
        with patch.object(preland.importlib.util, 'find_spec', side_effect=lambda m: None if m.rsplit('.', 1)[1] in missing else object()), patch.object(preland, 'run_check', side_effect=run), contextlib.redirect_stdout(io.StringIO()) as out:
            code = preland.main(list(args))
        return code, calls, out.getvalue()

    def test_order_native_argument_and_optional_workbench(self):
        code, calls, _ = self.invoke(['--wb'])
        self.assertEqual(0, code)
        self.assertEqual([*preland.CHECKS, 'wb_compile'], [m.rsplit('.', 1)[1] for m, _ in calls])
        self.assertEqual(['--native-scripts', str(preland.NATIVE)], calls[0][1])
        self.assertIn(('tools.package.regenerate_all', ['--check']), calls)

    def test_regeneration_is_required_and_propagates_failure(self):
        self.assertEqual(1, self.invoke(missing={'regenerate_all'})[0])
        code, calls, _ = self.invoke(codes={'regenerate_all': 1})
        self.assertEqual(1, code)
        self.assertIn(('tools.package.regenerate_all', ['--check']), calls)

    def test_failures_do_not_short_circuit_and_skips_are_incomplete(self):
        code, calls, output = self.invoke(codes={'enforce_lint': 1, 'cfgconvert_check': 3})
        self.assertEqual(1, code)
        self.assertEqual(len(preland.CHECKS), len(calls))
        self.assertIn('Check | Result | Scope', output)
        code, _, output = self.invoke(codes={'cfgconvert_check': preland.SKIPPED})
        self.assertEqual(preland.SKIPPED, code)
        self.assertIn('INCOMPLETE', output)

    def test_missing_optional_vs_required(self):
        self.assertEqual(preland.SKIPPED, self.invoke(['--wb'], missing={'layout_lint', 'wb_compile'})[0])
        self.assertEqual(1, self.invoke(missing={'enforce_lint'})[0])

    def test_changed_scope_keeps_perf_on_the_full_tree(self):
        authored = next((preland.ROOT / 'mods/HollowCountry/scripts').rglob('*.c'))
        paths = [authored.relative_to(preland.ROOT).as_posix(), 'mods/Test/include.hpp', 'docs/note.md']
        with patch.object(preland, 'changed_files', return_value=paths):
            code, calls, output = self.invoke(['--changed', 'HEAD'])
        self.assertEqual(0, code)
        by_name = {m.rsplit('.', 1)[1]: a for m, a in calls}
        self.assertEqual([], by_name['enforce_perf'], 'perf ratchet needs a full-project run')
        self.assertEqual(paths, by_name['cfgconvert_check'])
        self.assertEqual([], by_name['layout_lint'])
        self.assertEqual(['--check'], by_name['regenerate_all'])
        with patch.object(preland, 'changed_files', return_value=[]):
            _, calls, _ = self.invoke(['--changed', 'HEAD'])
        self.assertIn('tools.validate.enforce_perf', [m for m, _ in calls])
        self.assertIn(('tools.package.regenerate_all', ['--check']), calls)

    def test_changed_query_keeps_deleted_includes_without_git_mutation(self):
        import subprocess
        replies = [subprocess.CompletedProcess([], 0, b'mods/Test/gone.hpp\0'),
                   subprocess.CompletedProcess([], 0, b'tools/new.py\0')]
        with patch.object(preland.subprocess, 'run', side_effect=replies) as run:
            paths = preland.changed_files('HEAD')
        self.assertIn('mods/Test/gone.hpp', paths)
        self.assertEqual(['git', 'diff', '--name-only', '-z', 'HEAD', '--'], run.call_args_list[0].args[0])
        self.assertEqual(['git', 'ls-files', '--others', '--exclude-standard', '-z'], run.call_args_list[1].args[0])

    def test_launch_exception_is_failure_and_remaining_checks_run(self):
        with patch.object(preland.importlib.util, 'find_spec', return_value=object()), patch.object(preland, 'run_check', side_effect=OSError()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, preland.main([]))


if __name__ == '__main__':
    unittest.main()
