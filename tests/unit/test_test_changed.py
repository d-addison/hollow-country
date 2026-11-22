"""Changed-file unit-test selection runs only mapped modules and never widens to the full suite."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validate import preland, test_changed as selector

FILES = {
    'tools/pkg/a.py': '',
    'tools/pkg/b.py': 'from tools.pkg import a\n',
    'tools/pkg/c.py': 'from . import b\n',
    'tools/pkg/lazy.py': 'def go():\n    import tools.pkg.a as alias\n',
    'tools/pkg/lonely.py': 'x = 1\n',
    'tools/setup/runtime.py': '',
    'tools/setup/script_user.py': 'import runtime\n',
    'tests/unit/test_a.py': '',
    'tests/unit/test_b.py': 'from tools.pkg import b\n',
    'tests/unit/test_c.py': 'from tools.pkg.c import thing\n',
    'tests/unit/test_script.py': 'from tools.setup import script_user\n',
    'tests/unit/helper.py': '',
    'tests/unit/test_uses_helper.py': 'from tests.unit import helper\n',
    'tests/test_top.py': 'import tools.pkg.lazy\n',
    'tests/slow/test_slow.py': 'import tools.pkg.a\n',
}


class Selection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative, text in FILES.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def pick(self, *changed, **kwargs):
        return selector.select(changed, self.root, **kwargs)

    def test_direct_convention_and_transitive_importers(self):
        self.assertEqual((['tests.unit.test_a'], [], []), self.pick('tools/pkg/a.py', depth=1))
        # a <- b, lazy (an `import ... as alias` inside a function counts); tests import those at depth 2
        modules, notes, unmapped = self.pick('tools/pkg/a.py')
        self.assertEqual(['tests.test_top', 'tests.unit.test_a', 'tests.unit.test_b'], modules)
        self.assertEqual(([], []), (notes, unmapped))
        # c imports b with a relative import, so test_c needs depth 3
        self.assertIn('tests.unit.test_c', self.pick('tools/pkg/a.py', depth=3)[0])
        self.assertNotIn('tests.unit.test_script', self.pick('tools/pkg/a.py', depth=3)[0])

    def test_slow_suite_is_never_selected(self):
        modules, _, _ = self.pick('tools/pkg/a.py', depth=3)
        self.assertNotIn('tests.slow.test_slow', modules)

    def test_changed_test_and_helper_modules(self):
        self.assertEqual((['tests.unit.test_a'], [], []), self.pick('tests/unit/test_a.py'))
        self.assertEqual((['tests.unit.test_uses_helper'], [], []), self.pick('tests/unit/helper.py'))

    def test_script_style_bare_import_resolves_beside_the_importer(self):
        modules, _, _ = self.pick('tools/setup/runtime.py')
        self.assertEqual(['tests.unit.test_script'], modules)

    def test_unmapped_deleted_and_non_python_files(self):
        modules, _, unmapped = self.pick('tools/pkg/lonely.py', 'docs/x.md', 'tools/pkg/gone.py')
        self.assertEqual(([], ['tools/pkg/lonely.py']), (modules, unmapped))

    def test_cap_drops_transitive_levels_but_refuses_a_wide_direct_level(self):
        modules, notes, _ = self.pick('tools/pkg/a.py', depth=3, max_modules=2)
        self.assertEqual(['tests.unit.test_a'], modules)
        self.assertTrue(any(n.startswith('depth-2 importers dropped') for n in notes))
        modules, notes, _ = self.pick('tests/unit/test_a.py', 'tests/unit/test_b.py', max_modules=1)
        self.assertTrue(notes[0].startswith('direct level selects'))

    def test_real_repository_maps_this_tool_and_stays_unittest_only(self):
        modules, _, unmapped = selector.select(['tools/validate/source_cache.py'])
        self.assertIn('tests.unit.test_source_cache', modules)
        self.assertEqual([], unmapped)
        self.assertTrue(all(m.startswith('tests.') and '.slow.' not in m for m in modules))


class Command(unittest.TestCase):
    def main(self, argv, run_code=0):
        out = io.StringIO()
        with patch.object(selector, 'run', return_value=run_code) as run, contextlib.redirect_stdout(out):
            code = selector.main(argv)
        return code, run, out.getvalue()

    def test_files_run_only_mapped_modules_through_unittest(self):
        code, run, output = self.main(['--files', 'tools/validate/source_cache.py', '--depth', '1'], 3)
        self.assertEqual(3, code)
        modules = run.call_args[0][0]
        self.assertIn('tests.unit.test_source_cache', modules)
        run.assert_called_once()
        with patch.object(selector.subprocess, 'run') as sub:
            selector.run(['tests.unit.test_a'], timeout=5)
        self.assertEqual(['-B', '-m', 'unittest', 'tests.unit.test_a'], sub.call_args[0][0][1:])

    def test_nothing_mapped_runs_nothing(self):
        code, run, output = self.main(['--files', 'docs/x.md'])
        self.assertEqual(0, code)
        run.assert_not_called()
        self.assertIn('no unit tests map', output)

    def test_list_does_not_run(self):
        code, run, output = self.main(['--files', 'tools/validate/test_changed.py', '--list'])
        self.assertEqual(0, code)
        run.assert_not_called()
        self.assertIn('tests.unit.test_test_changed', output)

    def test_over_cap_direct_level_is_refused(self):
        code, run, output = self.main(['--files', 'tools/validate/enforce_source.py', '--max-modules', '1'])
        self.assertEqual(2, code)
        run.assert_not_called()
        self.assertIn('refusing to widen', output)


class PrelandHook(unittest.TestCase):
    def test_only_python_changes_run_the_mapped_tests(self):
        with patch.object(preland, 'run_check') as run:
            self.assertEqual(('unit_tests_changed', 'no applicable changes', False),
                             preland.changed_unit_tests(['mods/x.c', 'docs/a.md']))
            run.assert_not_called()
            run.return_value = preland.CheckResult(0, '')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(('unit_tests_changed', 'pass', False),
                                 preland.changed_unit_tests(['mods/x.c', 'tools/a.py']))
            run.assert_called_once_with('tools.validate.test_changed', ['--files', 'tools/a.py'])
            run.return_value = preland.CheckResult(1, '')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(('unit_tests_changed', 'FAIL (1)', True), preland.changed_unit_tests(['tools/a.py']))
            run.side_effect = OSError()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(('unit_tests_changed', 'FAIL (launch/timeout)', True),
                                 preland.changed_unit_tests(['tools/a.py']))

    def test_changed_run_reports_the_row_and_full_runs_do_not(self):
        def run(args, paths):
            with patch.object(preland.importlib.util, 'find_spec', return_value=object()), \
                    patch.object(preland, 'run_check', return_value=preland.CheckResult(0, 'world_mesh_audit: pass checked=5 findings=0 skipped=0')), \
                    patch.object(preland, 'asset_lint_runs', return_value=[]), \
                    patch.object(preland, 'changed_files', return_value=paths), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                preland.main(args)
            return out.getvalue()
        self.assertIn('unit_tests_changed | pass | changed files', run(['--changed', 'HEAD'], ['tools/a.py']))
        self.assertIn('unit_tests_changed | no applicable changes', run(['--changed', 'HEAD'], ['docs/a.md']))
        self.assertNotIn('unit_tests_changed', run([], []))

    def test_checks_get_the_shared_source_cache_directory(self):
        with patch.object(preland.subprocess, 'run') as sub, patch.dict(preland.os.environ, {}, clear=False):
            preland.os.environ.pop('HC_SOURCE_CACHE_DIR', None)
            sub.return_value = preland.subprocess.CompletedProcess([], 0, '', '')
            preland.run_check('tools.example', [])
            self.assertEqual(str(preland.SOURCE_CACHE_DIR), sub.call_args.kwargs['env']['HC_SOURCE_CACHE_DIR'])
            self.assertEqual('build', preland.SOURCE_CACHE_DIR.parent.name)


if __name__ == '__main__':
    unittest.main()
