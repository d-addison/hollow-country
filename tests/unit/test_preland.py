"""Orchestration tests fake every gate and never launch DayZ."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.validate import preland, wiring_audit as wiring


class PrelandTests(unittest.TestCase):
    def invoke(self, args=(), codes=None, missing=(), outputs=None):
        calls = []
        def run(module, arguments):
            calls.append((module, arguments))
            return preland.CheckResult((codes or {}).get(module.rsplit('.', 1)[1], 0),
                                       (outputs or {}).get(module.rsplit('.', 1)[1], ''))
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

    def test_ci_runs_full_offline_subset_and_declares_exclusions(self):
        code, calls, output = self.invoke(['--profile', 'ci'])
        self.assertEqual(0, code)
        by_name = {m.rsplit('.', 1)[1]: a for m, a in calls}
        self.assertEqual(set(preland.CHECKS) - {'cfgconvert_check'}, set(by_name))
        self.assertEqual(['--no-native'], by_name['enforce_lint'])
        self.assertEqual(['--no-texture-index'], by_name['layout_lint'])
        self.assertEqual(['--offline'], by_name['wiring_audit'])
        for flag in ('--addons', '--workshop', '--source'):
            self.assertIn(flag, by_name['regenerate_all'])
        for name, reason in preland.CI_EXCLUSIONS.items():
            self.assertIn(name + ': ' + reason, output)

    def test_strict_rejects_optional_missing_and_skip_exit(self):
        for name in ('layout_lint', 'wb_compile'):
            with self.subTest(name=name):
                self.assertEqual(1, self.invoke(['--strict', '--wb'], missing={name})[0])
        for name in preland.CHECKS:
            with self.subTest(name=name):
                self.assertEqual(1, self.invoke(['--strict'], codes={name: preland.SKIPPED})[0])
        _, calls, _ = self.invoke(['--strict'])
        self.assertIn(('tools.package.regenerate_all', ['--check', '--require-installed']), calls)

    def test_strict_rejects_zero_exit_coverage_gaps_without_changing_default(self):
        cases = {
            'regenerate_all': 'SKIP inventory_sizes required addons directory unavailable',
            'layout_lint': 'layout_lint: NOTICE installed texture index unavailable; skipping unresolved vanilla file checks (build)',
            'enforce_lint': 'enforce_lint: pass findings=0 native=no',
            'wiring_audit': 'NOTE External class-index roots missing: CfgVehicles',
            'settings_consistency': 'missing input: registry',
        }
        for name, output in cases.items():
            with self.subTest(name=name):
                self.assertEqual(0, self.invoke(outputs={name: output})[0])
                self.assertEqual(1, self.invoke(['--strict'], outputs={name: output})[0])

    def test_ci_allows_only_named_installed_coverage_notices(self):
        outputs = {
            'enforce_lint': 'enforce_lint: pass findings=0 native=no',
            'layout_lint': 'layout_lint: NOTICE installed texture index unavailable; skipping unresolved vanilla file checks (build)',
            'regenerate_all': ('SKIP inventory_sizes required addons directory unavailable\n'
                               'SKIP firearms required source directory unavailable\n'
                               'regenerate_all: pass checked=2 failed=0 skipped=2'),
            'wiring_audit': 'NOTE Optional class source unavailable: cache.json',
        }
        self.assertEqual(0, self.invoke(['--profile', 'ci'], outputs=outputs)[0])
        self.assertEqual(1, self.invoke(['--profile', 'ci', '--strict'], outputs=outputs)[0])
        for name, output in (('regenerate_all', 'SKIP gui_icons missing input'),
                             ('regenerate_all', 'regenerate_all: pass checked=1 failed=0 skipped=1'),
                             ('regenerate_all', 'SKIP firearms missing input: unexpected report'),
                             ('layout_lint', 'SKIP layout parser unavailable'),
                             ('enforce_perf', 'not available'),
                             ('settings_consistency', 'skipped'),
                             ('wiring_audit', 'missing input: registry')):
            with self.subTest(name=name, output=output):
                self.assertEqual(1, self.invoke(['--profile', 'ci'], outputs={name: output})[0])
        self.assertEqual(1, self.invoke(['--profile', 'ci'], missing={'layout_lint'})[0])
        self.assertEqual(1, self.invoke(['--profile', 'ci'], codes={'regenerate_all': preland.SKIPPED})[0])

    def test_ci_accepts_only_declared_stock_exclusions(self):
        notices = '\n'.join(f'EXCLUDED {name}: {reason}'
                            for name, reason in wiring.OFFLINE_EXCLUSIONS.items())
        self.assertEqual(0, self.invoke(['--profile', 'ci'], outputs={'wiring_audit': notices})[0])
        self.assertEqual(1, self.invoke(['--profile', 'ci', '--strict'],
                                       outputs={'wiring_audit': notices})[0])
        self.assertEqual(1, self.invoke(['--profile', 'ci'], outputs={
            'wiring_audit': 'EXCLUDED repository_checks: skipped'})[0])

    def test_ci_handles_r7_explicit_offline_layout_without_accepting_unknown_skips(self):
        baseline = json.loads(preland.layout_lint.BASELINE.read_text())
        output = '\n'.join('SKIPPED ' + row['reference'] for row in baseline['skipped'])
        output += '\nlayout_lint: SKIP explicit offline run'
        code, _, report = self.invoke(['--profile', 'ci'],
            codes={'layout_lint': preland.layout_lint.SKIPPED}, outputs={'layout_lint': output})
        self.assertEqual(0, code)
        self.assertIn('textures/native review excluded', report)
        self.assertEqual(1, self.invoke(['--profile', 'ci', '--strict'],
            codes={'layout_lint': preland.layout_lint.SKIPPED}, outputs={'layout_lint': output})[0])
        self.assertEqual(1, self.invoke(['--profile', 'ci'],
            codes={'layout_lint': preland.layout_lint.SKIPPED},
            outputs={'layout_lint': output + '\nSKIPPED mods/Synthetic.layout:1: unknown'})[0])
        self.assertEqual(1, self.invoke(['--profile', 'ci'],
            codes={'layout_lint': preland.layout_lint.SKIPPED})[0])

    def test_offline_wiring_keeps_repository_zeroed_rows_and_avoids_stock_reads(self):
        from tools.package import firearms
        audit = wiring.Audit(wiring.DEFAULTS, offline=True)
        owned = wiring.ROOT / 'mission/hollow-country/ce/types.xml'
        roster = wiring.ROOT / 'tools/package/firearms_roster.json'
        reasons = wiring.ROOT / wiring.DEFAULTS['zeroed_items']
        documents = {owned: '<types><type name="Synthetic"><nominal>0</nominal><min>0</min></type></types>',
                     roster: '{}', reasons: '{}'}
        def read(path):
            path = Path(path)
            if path.name.endswith('_allowlist.json'):
                return '{"entries": []}'
            return documents[path]  # Any stock read fails, even on an installed host.
        with patch.object(audit, 'read', side_effect=read), \
             patch.object(audit, 'paths', return_value=[owned]), \
             patch.object(firearms, 'selected_roster', return_value={'entries': []}):
            audit.zeroed_check(set())
        self.assertTrue(any(f['id'] == 'W009' and f['subject'] == 'Synthetic'
                            for f in audit.findings))
        self.assertEqual(set(wiring.OFFLINE_EXCLUSIONS), set(audit.exclusions))

    def test_offline_spawn_routes_ignore_installed_events_and_keep_repository_routes(self):
        from tools.package import infected_variety, map_overlay
        audit = wiring.Audit(wiring.DEFAULTS, offline=True)
        authored = wiring.ROOT / 'mission/synthetic-types.xml'
        policy = {'production_enabled': True,
                  'substitutions': [{'to': 'SyntheticStockDestination'}]}
        def read(path):
            self.assertEqual(infected_variety.POLICY, path)
            return json.dumps(policy)
        with patch.object(audit, 'read', side_effect=read), \
             patch.object(audit, 'safe', side_effect=AssertionError('stock path accessed')), \
             patch.object(audit, 'paths', return_value=[]), \
             patch.object(map_overlay, 'load_source', return_value={}), \
             patch.object(map_overlay, 'enabled_layers', return_value=[]):
            routes, admin = audit.spawn_routes({authored: (
                '<types><type name="SyntheticOwned"><nominal>1</nominal></type></types>')}, {}, [])
        self.assertEqual({'syntheticowned'}, routes)
        self.assertEqual(set(), admin)
        self.assertEqual({row['to'].lower() for row in policy['substitutions']},
                         audit.stock_route_candidates)

    def test_offline_wiring_retains_baseline_ratchet_and_strictness(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config').mkdir()
            (root / 'config/wiring-audit.json').write_text(json.dumps({'baseline': 'baseline.json'}))
            baseline = root / 'baseline.json'
            entry = {'id': 'W004', 'subject': 'Removed', 'file': 'mods/Synthetic.c',
                     'reason': 'synthetic reviewed finding'}
            baseline.write_text(json.dumps({'schema': 1, 'findings': [entry]}))
            before = baseline.read_bytes()
            with patch.object(wiring, 'ROOT', root), \
                 patch.object(wiring.Audit, 'run', return_value=[]), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(1, wiring.main(['--offline', '--json', '--strict-baseline']))
                self.assertEqual(before, baseline.read_bytes())
                report = json.loads(output.getvalue())
                self.assertEqual(wiring.OFFLINE_EXCLUSIONS, report['exclusions'])
                output.seek(0)
                output.truncate()
                self.assertEqual(0, wiring.main(['--offline', '--ratchet', '--strict-baseline']))
            self.assertEqual([], json.loads(baseline.read_text())['findings'])

    def test_offline_stock_route_candidates_are_deferred_while_other_routes_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config').mkdir()
            (root / 'config/wiring-audit.json').write_text('{}')
            def audit_run(audit):
                audit.stock_route_candidates = {'syntheticstock'}
                return [{'id': 'W001', 'subject': name, 'file': 'mods/Synthetic.c',
                         'line': 1, 'why': 'unresolved route'}
                        for name in ('SyntheticStock', 'SyntheticUnwired')]
            with patch.object(wiring, 'ROOT', root), \
                 patch.object(wiring.Audit, 'run', audit_run), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(1, wiring.main(['--offline', '--json']))
            findings = {f['subject']: f for f in json.loads(output.getvalue())['findings']}
            self.assertEqual('W001.stock_routes', findings['SyntheticStock']['excluded'])
            self.assertFalse(findings['SyntheticStock']['new'])
            self.assertNotIn('reason', findings['SyntheticStock'])
            self.assertTrue(findings['SyntheticUnwired']['new'])
            self.assertNotIn('excluded', findings['SyntheticUnwired'])

    def test_strict_allows_zero_skipped_summary(self):
        self.assertEqual(0, self.invoke(['--strict'], outputs={
            'regenerate_all': 'regenerate_all: pass checked=9 failed=0 skipped=0'})[0])

    def test_run_check_captures_raw_status_but_filters_published_output(self):
        import subprocess
        result = subprocess.CompletedProcess([], 0, 'SKIP generator missing input\n', 'unavailable\n')
        with patch.object(preland.subprocess, 'run', return_value=result), contextlib.redirect_stdout(io.StringIO()):
            checked = preland.run_check('tools.example', [])
        self.assertEqual(0, checked.code)
        self.assertIn('SKIP generator', checked.output)
        self.assertIn('unavailable', checked.output)

    def test_launch_exception_is_failure_and_remaining_checks_run(self):
        with patch.object(preland.importlib.util, 'find_spec', return_value=object()), patch.object(preland, 'run_check', side_effect=OSError()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, preland.main([]))


class HookTests(unittest.TestCase):
    """Exercise hooks using a Git shim; never mutate repository metadata."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.hooks = self.root / 'custom-hooks'
        git = self.bin / 'git'
        git.write_text('#!/bin/sh\ncase "$*" in\n'
                       '"rev-parse --show-toplevel") echo "$HOOK_TEST_ROOT" ;;\n'
                       '"rev-parse --git-path hooks") echo custom-hooks ;;\n'
                       '*) exit 2 ;;\nesac\n')
        git.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                    'HOOK_TEST_ROOT': str(self.root)}

    def install(self, *args):
        return subprocess.run(['sh', str(preland.ROOT / 'tools/hooks/install.sh'), *args],
                              env=self.env, cwd=self.root, capture_output=True, text=True, timeout=10)

    def test_installer_preserves_existing_and_dangling_hooks_until_replace(self):
        self.hooks.mkdir()
        hook = self.hooks / 'pre-push'
        hook.write_text('operator hook')
        self.assertNotEqual(0, self.install().returncode)
        self.assertEqual('operator hook', hook.read_text())
        hook.unlink()
        hook.symlink_to(self.root / 'absent')
        self.assertNotEqual(0, self.install().returncode)
        self.assertEqual(0, self.install('--replace').returncode)
        self.assertEqual(self.root / 'tools/hooks/pre-push', hook.resolve())
        self.assertEqual(0, self.install().returncode)

    def test_installer_links_hook_and_refuses_directory_or_unknown_args(self):
        self.assertEqual(0, self.install().returncode)
        hook = self.hooks / 'pre-push'
        self.assertTrue(hook.is_symlink())
        hook.unlink()
        hook.mkdir()
        self.assertNotEqual(0, self.install('--replace').returncode)
        self.assertTrue(hook.is_dir())
        self.assertNotEqual(0, self.install('--unknown').returncode)
        self.assertNotEqual(0, self.install('--replace', 'extra').returncode)

    def test_hook_runs_ci_from_repo_root_and_propagates_failure(self):
        python = self.bin / 'python3'
        python.write_text('#!/bin/sh\npwd > "$HOOK_TEST_ROOT/invocation"\n'
                          'printf "%s\\n" "$@" >> "$HOOK_TEST_ROOT/invocation"\nexit 7\n')
        python.chmod(0o755)
        result = subprocess.run(['sh', str(preland.ROOT / 'tools/hooks/pre-push')],
                                cwd=self.bin, env=self.env, capture_output=True, timeout=10)
        self.assertEqual(7, result.returncode)
        self.assertEqual([str(self.root), '-B', '-m', 'tools.validate.preland', '--profile', 'ci'],
                         (self.root / 'invocation').read_text().splitlines())


if __name__ == '__main__':
    unittest.main()
