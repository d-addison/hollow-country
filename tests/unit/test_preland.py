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

from tools.validate import mission_sources, preland, wiring_audit as wiring


MESH_PASS = 'world_mesh_audit: pass checked=5 findings=0 skipped=0'


def key(module, arguments=()):
    """Check name for a call: the mission_sources modes are the hc_events/ce_slot_pressure gates."""
    if module.endswith('mission_sources'):
        return {'--events': 'hc_events', '--ce-slots': 'ce_slot_pressure'}.get(
            next((a for a in arguments if a in ('--events', '--ce-slots')), ''), 'mission_sources')
    return module.rsplit('.', 1)[1]


class PrelandTests(unittest.TestCase):
    def invoke(self, args=(), codes=None, missing=(), outputs=None, assets=(('synthetic-asset',),),
               mission=True, mesh_gap=''):
        calls = []
        outputs = {'world_mesh_audit': MESH_PASS, **(outputs or {})}
        def run(module, arguments):
            calls.append((module, arguments))
            return preland.CheckResult((codes or {}).get(key(module, arguments), 0),
                                       outputs.get(key(module, arguments), ''))
        args = list(args) + (['--ce-mission', 'synthetic-mission'] if mission else [])
        with patch.object(preland.importlib.util, 'find_spec', side_effect=lambda m: None if m.rsplit('.', 1)[1] in missing else object()), patch.object(preland, 'run_check', side_effect=run), patch.object(preland, 'asset_lint_runs', return_value=[list(a) for a in assets] if not isinstance(assets, str) else assets), patch.object(preland, 'world_mesh_gap', return_value=mesh_gap), patch.dict(os.environ, {'HC_CE_MISSION': ''}), contextlib.redirect_stdout(io.StringIO()) as out:
            code = preland.main(args)
        return code, calls, out.getvalue()

    def test_order_native_argument_and_optional_workbench(self):
        code, calls, _ = self.invoke(['--wb'])
        self.assertEqual(0, code)
        self.assertEqual([*preland.CHECKS, 'wb_compile'], [key(m, a) for m, a in calls])
        self.assertEqual(['--native-scripts', str(preland.NATIVE)], calls[0][1])
        self.assertIn(('tools.package.regenerate_all', ['--check']), calls)
        self.assertIn(('tools.package.generated_digests', ['--check']), calls)

    def test_digest_failures_fail_even_with_zero_exit(self):
        self.assertEqual(1, self.invoke(missing={'generated_digests'})[0])
        self.assertEqual(1, self.invoke(codes={'generated_digests': 1})[0])
        for args in ([], ['--profile', 'ci']):
            with self.subTest(args=args):
                code, _, output = self.invoke(args, outputs={
                    'generated_digests': 'FAIL firearms committed input/source/output digest differs'})
                self.assertEqual(1, code)
                self.assertIn('generated_digests | FAIL', output)

    def test_ci_digest_skips_require_exact_installed_input_notices(self):
        notice = 'SKIP inventory_sizes inventory provider Addons unavailable'
        self.assertEqual(0, self.invoke(['--profile', 'ci'],
                                       outputs={'generated_digests': notice})[0])
        self.assertEqual(1, self.invoke(['--profile', 'ci', '--strict'],
                                       outputs={'generated_digests': notice})[0])
        for detail in ('receipt pending', 'receipt missing', 'changed inputs',
                       'inventory provider Addons unavailable unexpected'):
            with self.subTest(detail=detail):
                self.assertEqual(1, self.invoke(['--profile', 'ci'], outputs={
                    'generated_digests': 'SKIP inventory_sizes ' + detail})[0])

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
        by_name = {key(m, a): a for m, a in calls}
        self.assertEqual([], by_name['enforce_perf'], 'perf ratchet needs a full-project run')
        self.assertEqual(paths, by_name['cfgconvert_check'])
        self.assertEqual([], by_name['layout_lint'])
        self.assertEqual(['--check'], by_name['regenerate_all'])
        self.assertEqual(['--check'], by_name['generated_digests'])
        with patch.object(preland, 'changed_files', return_value=[]):
            _, calls, _ = self.invoke(['--changed', 'HEAD'])
        self.assertIn('tools.validate.enforce_perf', [m for m, _ in calls])
        self.assertIn(('tools.package.regenerate_all', ['--check']), calls)
        self.assertIn(('tools.package.generated_digests', ['--check']), calls)

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
        by_name = {key(m, a): a for m, a in calls}
        self.assertEqual(set(preland.CHECKS) - set(preland.CI_ONLY_EXCLUDED), set(by_name))
        self.assertEqual(['--no-native'], by_name['enforce_lint'])
        self.assertEqual(['--no-texture-index'], by_name['layout_lint'])
        self.assertEqual(['--offline'], by_name['wiring_audit'])
        for name in ('regenerate_all', 'generated_digests'):
            for flag in ('--addons', '--workshop', '--source', '--image-to-paa'):
                self.assertIn(flag, by_name[name])
            tool = Path(by_name[name][by_name[name].index('--image-to-paa') + 1])
            addons = Path(by_name[name][by_name[name].index('--addons') + 1])
            self.assertEqual(addons.parent, tool.parent)
            self.assertFalse(tool.exists(), 'CI must not discover an installed Windows converter')
            self.assertEqual('--check', by_name[name][0])
        for name, reason in preland.CI_EXCLUSIONS.items():
            self.assertIn(name + ': ' + reason, output)

    def test_ci_accepts_counted_external_class_exclusion_only(self):
        notice = ('EXCLUDED external_classes: '
                  + preland.CI_EXCLUSIONS['wiring_audit.external_classes'] + '; count=3')
        self.assertEqual([], preland.incomplete_lines('wiring_audit', notice, ci=True))
        # Coverage notes still fail strict installed checks.
        coverage = 'NOTE External class-index roots missing: CfgVehicles'
        self.assertTrue(preland.incomplete_lines('wiring_audit', coverage, ci=False))
        self.assertEqual([], preland.incomplete_lines('wiring_audit', notice + '\n' + coverage, ci=True))
        self.assertEqual(0, self.invoke(['--profile', 'ci'], outputs={'wiring_audit': notice})[0])

    def test_strict_rejects_optional_missing_and_skip_exit(self):
        for name in ('layout_lint', 'wb_compile'):
            with self.subTest(name=name):
                self.assertEqual(1, self.invoke(['--strict', '--wb'], missing={name})[0])
        for name in preland.CHECKS:
            with self.subTest(name=name):
                self.assertEqual(1, self.invoke(['--strict'], codes={name: preland.SKIPPED})[0])
        _, calls, _ = self.invoke(['--strict'])
        self.assertIn(('tools.package.regenerate_all', ['--check', '--require-installed']), calls)
        self.assertIn(('tools.package.generated_digests', ['--check', '--require-installed']), calls)

    def test_strict_rejects_zero_exit_coverage_gaps_without_changing_default(self):
        cases = {
            'regenerate_all': 'SKIP inventory_sizes required addons directory unavailable',
            'generated_digests': ('SKIP loot_point_preserve stock mission mapgrouppos.xml unavailable\n'
                                  'SKIP snafu_optional weapon pack verification report unavailable\n'
                                  'SKIP tactical_flava_optional weapon pack verification report unavailable\n'
                                  'SKIP new_buildings stock mission mapgrouppos.xml unavailable'),
            'layout_lint': 'layout_lint: NOTICE installed texture index unavailable; skipping unresolved vanilla file checks (build)',
            'enforce_lint': 'enforce_lint: pass findings=0 native=no',
            'wiring_audit': 'NOTE External class-index roots missing: CfgVehicles',
            'settings_consistency': 'missing input: registry',
        }
        for name, output in cases.items():
            with self.subTest(name=name):
                code, _, text = self.invoke(outputs={name: output})
                self.assertEqual(preland.SKIPPED, code)
                self.assertIn('status=needs-host-check', text)
                self.assertIn('tools.release.test_queue submit --commit', text)
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

    def test_ci_current_regeneration_skips_require_exact_installed_inputs(self):
        notices = [
            'SKIP loot_point_preserve existing validation passed; byte regeneration: stock mission mapgrouppos.xml unavailable',
            'SKIP gui_icons existing validation passed; byte regeneration: ImageToPAA converter unavailable',
            'SKIP gui_icons existing validation passed; byte regeneration: ImageToPAA Windows interop unavailable',
            'SKIP anims_config required addons directory unavailable',
            'SKIP economy required source directory unavailable',
            'SKIP ai_patrols required source directory unavailable',
        ]
        for notice in notices:
            with self.subTest(notice=notice):
                lines = [notice]
                output = '\n'.join([*lines,
                    f'regenerate_all: pass checked=0 failed=0 skipped={len(lines)}'])
                self.assertEqual(0, self.invoke(['--profile', 'ci'],
                    outputs={'regenerate_all': output})[0])
                self.assertEqual(1, self.invoke(['--profile', 'ci', '--strict'],
                    outputs={'regenerate_all': output})[0])
                code, _, text = self.invoke(outputs={'regenerate_all': output})
                self.assertEqual(preland.SKIPPED, code)
                self.assertIn('status=needs-host-check', text)
                for invalid in (notice + ' unexpected',
                                notice.replace('SKIP ', 'SKIP unknown_', 1)):
                    self.assertEqual(1, self.invoke(['--profile', 'ci'],
                        outputs={'regenerate_all': invalid})[0])
        for notice in (
            'SKIP gui_icons existing validation passed; byte regeneration: receipt unavailable',
            'SKIP loot_point_preserve existing validation passed; byte regeneration: geometry Addons (installed vanilla *.pbo) unavailable',
        ):
            with self.subTest(notice=notice):
                self.assertEqual(1, self.invoke(['--profile', 'ci'],
                    outputs={'regenerate_all': notice})[0])

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

    def test_ci_layout_defers_only_vanilla_dayz_gui_symbolic_members(self):
        skipped = preland.layout_lint.SKIPPED
        vanilla = ('SKIPPED mods/HollowCountry/gui/layouts/x.layout:24: imageset symbolic reference '
                   'needs native review: set:dayz_gui image:circle\n'
                   'layout_lint: SKIP explicit offline run')
        self.assertEqual(0, self.invoke(['--profile', 'ci'], codes={'layout_lint': skipped},
                                        outputs={'layout_lint': vanilla})[0])
        self.assertEqual(1, self.invoke(['--profile', 'ci', '--strict'], codes={'layout_lint': skipped},
                                        outputs={'layout_lint': vanilla})[0])
        for other in ('set:hc_owned image:circle', 'set:dayz_gui image:a b'):
            owned = vanilla.replace('set:dayz_gui image:circle', other)
            self.assertEqual(1, self.invoke(['--profile', 'ci'], codes={'layout_lint': skipped},
                                            outputs={'layout_lint': owned})[0], other)

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

    def test_wave_c_gates_run_with_their_declared_commands(self):
        _, calls, output = self.invoke()
        by_name = {key(m, a): (m, a) for m, a in calls}
        self.assertEqual(['--summary'], by_name['hygiene'][1])
        self.assertEqual(['--events'], by_name['hc_events'][1])
        self.assertEqual(['--ce-slots', str(Path('synthetic-mission'))], by_name['ce_slot_pressure'][1])
        self.assertEqual('tools.audit.world_mesh_audit', by_name['world_mesh_audit'][0])
        self.assertEqual('--report', by_name['world_mesh_audit'][1][0])
        self.assertEqual(['synthetic-asset'], by_name['asset_lint'][1])
        for name in ('hygiene', 'hc_events', 'ce_slot_pressure', 'world_mesh_audit', 'asset_lint'):
            self.assertIn(name + ' | pass', output)

    def test_ce_slot_pressure_skips_without_a_staged_mission(self):
        code, calls, output = self.invoke(mission=False)
        self.assertEqual(preland.SKIPPED, code)
        self.assertIn('ce_slot_pressure | skipped: staged CE mission not provided', output)
        self.assertNotIn('ce_slot_pressure', [key(m, a) for m, a in calls])
        code, _, output = self.invoke(['--strict'], mission=False)
        self.assertEqual(1, code)
        self.assertIn('ce_slot_pressure | FAIL (skipped: ', output)
        self.assertEqual(1, self.invoke(codes={'ce_slot_pressure': 1})[0])

    def test_world_mesh_audit_skips_cleanly_and_fails_on_findings(self):
        code, calls, output = self.invoke(mesh_gap='installed vanilla Addons unavailable')
        self.assertEqual(preland.SKIPPED, code)
        self.assertIn('world_mesh_audit | skipped: installed vanilla Addons unavailable', output)
        self.assertNotIn('world_mesh_audit', [key(m, a) for m, a in calls])
        self.assertEqual(1, self.invoke(['--strict'], mesh_gap='installed vanilla Addons unavailable')[0])
        partial = 'SKIP INSTALLED_ADDONS_UNAVAILABLE\nworld_mesh_audit: pass checked=0 findings=0 skipped=1'
        code, _, output = self.invoke(outputs={'world_mesh_audit': partial})
        self.assertEqual(preland.SKIPPED, code)
        self.assertIn('skipped: INSTALLED_ADDONS_UNAVAILABLE', output)
        self.assertEqual(1, self.invoke(['--strict'], outputs={'world_mesh_audit': partial})[0])
        self.assertEqual(0, self.invoke(['--strict'])[0])
        failing = 'world_mesh_audit: fail checked=3 findings=2 skipped=0'
        self.assertEqual(1, self.invoke(codes={'world_mesh_audit': 1}, outputs={'world_mesh_audit': failing})[0])
        self.assertEqual(1, self.invoke(outputs={'world_mesh_audit': ''})[0], 'a missing summary is not a pass')

    def test_ci_excludes_staged_and_installed_gates_but_keeps_offline_ones(self):
        code, calls, output = self.invoke(['--profile', 'ci'], mission=False, mesh_gap='unavailable')
        self.assertEqual(0, code)
        names = [key(m, a) for m, a in calls]
        for name in ('hygiene', 'hc_events', 'asset_lint'):
            self.assertIn(name, names)
        for name in ('ce_slot_pressure', 'world_mesh_audit'):
            self.assertNotIn(name, names)
            self.assertIn(name + ' | excluded: ' + preland.CI_EXCLUSIONS[name], output)

    def test_asset_lint_without_built_assets_is_not_applicable_and_refusals_fail(self):
        code, calls, output = self.invoke(assets=())
        self.assertEqual(0, code)
        self.assertIn('asset_lint | no applicable inputs', output)
        self.assertNotIn('asset_lint', [key(m, a) for m, a in calls])
        code, _, output = self.invoke(assets='asset x.p3d lacks its sidecar')
        self.assertEqual(1, code)
        self.assertIn('asset_lint | FAIL (asset x.p3d lacks its sidecar)', output)
        self.assertEqual(1, self.invoke(codes={'asset_lint': 1})[0])

    def test_asset_lint_runs_pair_each_built_asset_with_its_sidecars(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / 'config.cpp'
            self.assertEqual([], preland.asset_lint_runs(root / 'none', config))
            config.write_text('class CfgPatches {};')
            (root / 'a.p3d').write_bytes(b'')
            (root / 'b.ir.json').write_text('{}')
            self.assertIsInstance(preland.asset_lint_runs(root, config), str)
            for stem in ('a', 'b'):
                (root / (stem + '.model.cfg')).write_text('')
                (root / (stem + '.sources.json')).write_text('[]')
            runs = preland.asset_lint_runs(root, config)
            self.assertEqual([str(root / 'a.p3d'), str(root / 'b.ir.json')], [r[0] for r in runs])
            for run in runs:
                self.assertEqual({'--model-cfg', '--config', '--sources'}, {a for a in run if a.startswith('--')})
            config.unlink()
            self.assertIsInstance(preland.asset_lint_runs(root, config), str)


class MissionInvariantTests(unittest.TestCase):
    def run_cli(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = mission_sources.main(list(argv))
        return code, out.getvalue()

    def test_committed_event_anchors_hold_the_measured_y_invariant(self):
        code, output = self.run_cli('--events')
        self.assertEqual(0, code, output)
        self.assertIn('mission_sources: events PASS', output)

    def test_event_invariant_failure_is_reported_without_a_traceback(self):
        with patch('tools.package.hc_events.validate', side_effect=ValueError('missing or invalid anchor y: E:site001')):
            code, output = self.run_cli('--events')
        self.assertEqual(1, code)
        self.assertIn('events FAIL missing or invalid anchor y', output)

    def test_ce_slots_requires_inputs_and_gates_on_the_weapon_reservation(self):
        from tools.package import ce_slot_pressure

        def report(mission, military, limit):
            return {'status': 'fail' if military else 'pass', 'demand': 10, 'required_with_headroom': 13,
                    'headroom_deficit': 3, 'placeable_upper_bound': 9, 'deficit': 1}
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(2, self.run_cli('--ce-slots', raw)[0])
            for name in ce_slot_pressure.INPUTS:
                (Path(raw) / name).write_text('')
            with patch.object(ce_slot_pressure, 'feasibility', side_effect=report):
                code, output = self.run_cli('--ce-slots', raw)
            self.assertEqual(1, code)
            self.assertIn('FAIL military-weapons', output)
            self.assertIn('info all-categories', output)
            passing = lambda mission, military, limit: dict(report(mission, military, limit), status='pass')
            with patch.object(ce_slot_pressure, 'feasibility', side_effect=passing):
                self.assertEqual(0, self.run_cli('--ce-slots', raw)[0])
            with patch.object(ce_slot_pressure, 'feasibility', side_effect=ValueError('unreadable')):
                self.assertEqual(2, self.run_cli('--ce-slots', raw)[0])

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
