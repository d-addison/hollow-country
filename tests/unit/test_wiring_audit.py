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

    def run_cli(self, *args, findings=None, missing_roots=(), definitions=None, indexed=None):
        output = io.StringIO()
        def run(audit):
            audit.missing_class_roots = set(missing_roots)
            audit.definitions = definitions or {}
            audit.indexed = indexed or {}
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

    def test_ratchet_prunes_independent_entries_with_missing_roots(self):
        for roots in ({'CfgAmmo'}, {'CfgVehicles'}, set(wiring.DEFAULTS['config_roots'])):
            with self.subTest(roots=roots):
                self.path.write_text(json.dumps(self.baseline))
                result, report = self.run_cli('--ratchet', missing_roots=roots)
                self.assertEqual(result, 0)
                self.assertEqual(json.loads(self.path.read_text())['findings'], [self.kept])
                self.assertEqual(report['missing_class_roots'], sorted(roots))
                self.assertEqual(report['baseline_kept_missing_roots'], 0)

    def test_ratchet_retains_missing_root_dependent_entries(self):
        dependent = [dict(self.stale, id=check) for check in ('W001', 'W001b', 'W007', 'W008')]
        self.baseline['findings'] += dependent
        self.path.write_text(json.dumps(self.baseline))
        result, report = self.run_cli('--ratchet', '--strict-baseline', missing_roots={'CfgVehicles'})
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(self.path.read_text())['findings'], [self.kept, *dependent])
        self.assertEqual(report['baseline_kept_missing_roots'], len(dependent))
        self.assertEqual(report['stale_baseline'], dependent)

    def test_missing_ammo_keeps_unknown_config_provenance_but_prunes_object_findings(self):
        dependent = dict(self.stale, id='W001')
        object_entries = [dict(self.stale, id=check) for check in ('W007', 'W008')]
        self.baseline['findings'] += [dependent, *object_entries]
        self.path.write_text(json.dumps(self.baseline))
        result, report = self.run_cli('--ratchet', missing_roots={'CfgAmmo'})
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(self.path.read_text())['findings'], [self.kept, dependent])
        self.assertEqual(report['baseline_kept_missing_roots'], 1)

    def test_ratchet_uses_config_root_provenance(self):
        entries = [dict(self.stale, id=check) for check in ('W001', 'W001b')]
        self.baseline['findings'] += entries
        for root in ('CfgVehicles', 'CfgAmmo'):
            with self.subTest(root=root):
                self.path.write_text(json.dumps(self.baseline))
                _, report = self.run_cli('--ratchet', missing_roots={'CfgAmmo'},
                                         definitions={self.stale['subject'].lower(): {'root': root}},
                                         indexed={root: {self.stale['subject'].lower(): {}}})
                expected = entries if root == 'CfgAmmo' else []
                self.assertEqual(json.loads(self.path.read_text())['findings'], [self.kept, *expected])
                self.assertEqual(report['baseline_kept_missing_roots'], len(expected))


class DeadClassTests(unittest.TestCase):
    """W004 reachability: derived from script, config and tool sources; no engine behaviour is implied."""

    def audit(self, scripts, config='', tool=''):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, text in scripts.items():
            (root / name).write_text(text)
        (root / 'config.cpp').write_text(config)
        (root / 'tool.py').write_text(tool)
        rules = copy.deepcopy(wiring.DEFAULTS)
        rules['roots'] = {'scripts': list(scripts), 'configs': ['config.cpp'], 'data': [],
                          'tools': ['tool.py'], 'audit_data': []}
        audit = wiring.Audit(rules, offline=True)
        with patch.object(wiring, 'ROOT', root):
            parsed = {p: wiring.mask(audit.read(p)) for p in audit.paths(scripts)}
            script_classes = [(p, c) for p, t in parsed.items() for c in wiring.classes(t)]
            audit.dead_class_check(parsed, script_classes)
        return {f['subject'] for f in audit.findings if f['id'] == 'W004'}

    def test_unreferenced_class_is_flagged(self):
        self.assertEqual({'Dead'}, self.audit({'a.c': 'class Dead { void Run() {} }'}))

    def test_comment_and_own_body_do_not_reference(self):
        text = '// Dead\nclass Dead { static Dead Make() { return new Dead(); } }'
        self.assertEqual({'Dead'}, self.audit({'a.c': text}))

    def test_file_local_helper_used_by_live_code_is_live(self):
        text = 'class Helper {}\nmodded class MissionServer { void OnInit() { new Helper(); } }'
        self.assertEqual(set(), self.audit({'a.c': text}))

    def test_helper_used_only_by_dead_class_is_dead_chain(self):
        text = 'class Helper {}\nclass Dead { void Run() { new Helper(); } }'
        self.assertEqual({'Helper', 'Dead'}, self.audit({'a.c': text}))

    def test_cross_file_reference_from_live_code_is_live(self):
        scripts = {'a.c': 'class Used {}', 'b.c': 'void Boot() { Used u; }'}
        self.assertEqual(set(), self.audit(scripts))

    def test_config_named_and_exact_literal_classes_are_live(self):
        scripts = {'a.c': 'class Configured {}\nclass Looked {}\nclass Other {}',
                   'b.c': 'void Boot() { GetGame().CreateObject("Looked", vector.Zero); }'}
        self.assertEqual({'Other'}, self.audit(scripts, config='class CfgMods { class X { dependencies[] = {"Configured"}; }; };'))

    def test_substring_literal_does_not_reference(self):
        scripts = {'a.c': 'class Looked {}', 'b.c': 'void Boot() { Print("Looked at it"); }'}
        self.assertEqual({'Looked'}, self.audit(scripts))

    def test_tool_embedded_call_or_new_is_an_entry_point(self):
        scripts = {'a.c': 'class Hook { static void Run() {} }\nclass Maker {}\nclass Dead {}'}
        tool = '"""Dead.Run() in a docstring"""\nHOOK = "void Init() { Hook.Run(); Maker m = new Maker(); }"\n'
        self.assertEqual({'Dead'}, self.audit(scripts, tool=tool))


class FieldRouteTests(unittest.TestCase):
    """A string-array field default reaches the creation call that consumes it, across methods."""

    def routes(self, source):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'a.c').write_text(source)
        rules = copy.deepcopy(wiring.DEFAULTS)
        rules['roots'] = {'scripts': ['a.c'], 'configs': [], 'data': [], 'tools': [], 'audit_data': []}
        audit = wiring.Audit(rules, offline=True)
        with patch.object(wiring, 'ROOT', root), patch.object(audit, 'safe', side_effect=Path):
            scripts = {p: wiring.mask(audit.read(p)) for p in audit.paths(['a.c'])}
            script_classes = [(p, c) for p, t in scripts.items() for c in wiring.classes(t)]
            with patch('tools.package.map_overlay.load_source'), \
                    patch('tools.package.map_overlay.enabled_layers', return_value=[]):
                return audit.spawn_routes({}, scripts, script_classes)[0]

    CONFIG = 'class Cfg { ref array<string> Herbs = {"Cannabis", "Nettle"}; }\n'

    def test_field_array_read_through_pending_field_is_a_route(self):
        source = self.CONFIG + """class Spawner {
            protected string m_Pending;
            string Pick(int slot) { return Cfg.Get().Herbs[0]; }
            void Plan() { string type = Pick(0); m_Pending = type; }
            void Create() { string type = m_Pending; GetGame().CreateObjectEx(type, vector.Zero, 0); }
        }"""
        self.assertIn('cannabis', self.routes(source))

    def test_field_assigned_but_never_created_is_not_a_route(self):
        source = self.CONFIG + """class Spawner {
            protected string m_Pending;
            string Pick(int slot) { return Cfg.Get().Herbs[0]; }
            void Plan() { string type = Pick(0); m_Pending = type; }
            void Create() { Print(m_Pending); }
        }"""
        self.assertNotIn('cannabis', self.routes(source))


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
