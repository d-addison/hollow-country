"""Baseline ratcheting tests; synthetic audit results establish no engine behavior."""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validate import wiring_audit as wiring


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        (self.root / 'config/wiring-audit.json').write_text(json.dumps({'schema': 1, 'baseline': 'baseline.json'}))
        self.path = self.root / 'baseline.json'
        self.live = {'id': 'W004', 'subject': 'Local', 'file': 'mods/Local.c', 'line': 1, 'why': 'local class'}
        self.kept = dict(self.live, reason='reviewed fixture')
        self.stale = dict(self.kept, subject='Removed')
        self.baseline = {'schema': 1, 'note': 'retain metadata', 'findings': [self.kept, self.stale]}
        self.path.write_text(json.dumps(self.baseline))

    def run_cli(self, *args, findings=None, missing_roots=()):
        output = io.StringIO()
        def run(audit):
            audit.missing_class_roots = set(missing_roots)
            return copy.deepcopy([self.live] if findings is None else findings)
        with patch.object(wiring, 'ROOT', self.root), patch.object(wiring.Audit, 'run', run), redirect_stdout(output):
            result = wiring.main(['--json', *args])
        return result, json.loads(output.getvalue())

    def test_report_and_strict_do_not_mutate_baseline(self):
        before = self.path.read_bytes()
        result, report = self.run_cli()
        self.assertEqual(result, 0)
        self.assertEqual(report['stale_baseline'], [self.stale])
        self.assertEqual(report['stale_baseline_entries'], len(report['stale_baseline']))
        self.assertEqual(self.run_cli('--strict-baseline')[0], 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_ratchet_only_removes_stale_and_preserves_new_failure(self):
        new = dict(self.live, subject='New')
        result, report = self.run_cli('--ratchet', '--strict-baseline', findings=[self.live, new])
        self.assertEqual(result, 1)
        expected = dict(self.baseline, findings=[self.kept])
        self.assertEqual(json.loads(self.path.read_text()), expected)
        self.assertEqual(report['stale_baseline'], [])
        self.assertEqual([f['subject'] for f in report['findings'] if f['new']], [new['subject']])
        before = self.path.read_bytes()
        self.assertEqual(self.run_cli('--ratchet', '--strict-baseline')[0], 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_legacy_prune_alias_and_empty_live_set(self):
        self.assertEqual(self.run_cli('--update-baseline', '--strict-baseline', findings=[])[0], 0)
        self.assertEqual(json.loads(self.path.read_text())['findings'], [])

    def test_external_exclusions_are_not_new_or_baselined(self):
        finding = dict(self.live, id='W007', subject='External', excluded='external_classes')
        before = self.path.read_bytes()
        result, report = self.run_cli('--offline', findings=[finding], missing_roots={'CfgVehicles'})
        self.assertEqual(0, result)
        reported, = report['findings']
        self.assertFalse(reported['new'])
        self.assertNotIn('reason', reported)
        self.assertEqual(before, self.path.read_bytes())

    def test_ratchet_refuses_incomplete_caches_without_writing_baseline(self):
        before = self.path.read_bytes()
        for flags in (('--ratchet',), ('--offline', '--ratchet'), ('--update-baseline',)):
            with self.subTest(flags=flags):
                result, report = self.run_cli(*flags, missing_roots={'CfgVehicles'})
                self.assertEqual(2, result)
                self.assertIn('cannot ratchet', report['error'])
                self.assertEqual(before, self.path.read_bytes())


class ExternalClassTests(unittest.TestCase):
    def test_missing_object_caches_defer_only_external_dependent_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'manifest.json').write_text('{"mods": []}')
            (root / 'config.cpp').write_text("""
                class CfgVehicles {
                    class ExternalParent;
                    class LocalBase: ExternalParent {};
                    class LocalChild: LocalBase {scope=2;};
                    class EngineBase: ExternalParent {};
                    class UnwiredPublic: ExternalParent {scope=2;};
                    class Parentless {};
                };
            """)
            (root / 'script.c').write_text('class LocalScript {}; void Spawn() {CreateObject("ExternalObject");}')
            (root / 'types.xml').write_text('<types><type name="ExternalObject"><nominal>1</nominal></type></types>')
            cache = root / 'classes.json'
            rules = copy.deepcopy(wiring.DEFAULTS)
            rules.update(bundle_profile_catalogue=False, workshop_manifest='manifest.json',
                         ce_type_patterns=['types.xml'],
                         class_sources=[{'path': 'classes.json', 'format': 'json'}])
            rules['roots'] = {'scripts': ['script.c'], 'configs': ['config.cpp'],
                              'data': ['types.xml'], 'tools': [], 'audit_data': []}
            def run():
                audit = wiring.Audit(rules, offline=True)
                with ExitStack() as stack:
                    stack.enter_context(patch.object(wiring, 'ROOT', root))
                    stack.enter_context(patch.object(audit, 'spawn_routes', return_value=(set(), set())))
                    for method in ('zeroed_check', 'bundle_check', 'data_check', 'settings_check',
                                   'module_check', 'rpc_check'):
                        stack.enter_context(patch.object(audit, method))
                    findings = audit.run()
                return audit, {(f['id'], f['subject']): f for f in findings}
            absent, findings = run()
            deferred = {key for key, finding in findings.items()
                        if finding.get('excluded') == 'external_classes'}
            self.assertEqual({('W001', 'LocalBase'), ('W001', 'EngineBase'), ('W007', 'ExternalObject'),
                              ('W008', 'ExternalObject')}, deferred)
            self.assertNotIn('excluded', findings['W001', 'UnwiredPublic'])
            self.assertNotIn('excluded', findings['W001', 'Parentless'])
            self.assertIn(f'count={len(deferred)}', absent.exclusions['external_classes'])
            # An indexed object root restores real missing-class findings even
            # when the independent ammo root has no cache (the local census).
            cache.write_text(json.dumps({name: ({'externalparent': {'scope': 0},
                                                 'enginechild': {'parent': 'enginebase', 'scope': 2}}
                                                if name == 'CfgVehicles' else {})
                                         for name in rules['config_roots'] if name != 'CfgAmmo'}))
            present, findings = run()
            self.assertNotIn(('W001', 'LocalBase'), findings)
            self.assertNotIn(('W001', 'EngineBase'), findings)
            self.assertNotIn('external_classes', present.exclusions)
            for key in (('W007', 'ExternalObject'), ('W008', 'ExternalObject'),
                        ('W001', 'UnwiredPublic')):
                self.assertNotIn('excluded', findings[key])


if __name__ == '__main__':
    unittest.main()
