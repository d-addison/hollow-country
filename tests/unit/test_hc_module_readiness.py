"""Wave 7 #157/#175: synthetic lifecycle ports and pure source lint only.

These execute authored control flow; no native compile or DayZ readiness proof.
"""
from types import SimpleNamespace as N
import unittest

from tests.unit import test_core_lifecycle as core

class ModuleReadiness(unittest.TestCase):
    def test_each_registered_module_has_one_conservative_readiness_line(self):
        logs, events, reads = [], [], {}
        cases = [('Disabled', False, None), ('Skipped', True, ('refused', 'provider_missing')),
                 ('Ready', True, ('ready', 'owner_started')), ('Legacy', True, None),
                 ('Conflict', False, ('ready', 'owner_started')),
                 ('Degraded', True, ('degraded', 'partial_admission'))]
        modules = []
        for name, enabled, status in cases:
            def admitted(settings, name=name, enabled=enabled):
                reads[name] = reads.get(name, 0) + 1
                return enabled
            report = None if status is None else N(HCState=lambda status=status: status[0],
                                                   HCReason=lambda status=status: status[1])
            modules.append(N(GetName=lambda name=name: name, IsEnabled=admitted,
                             HCGetOperationalStatus=lambda report=report: report,
                             OnStart=lambda settings, name=name: events.append(name),
                             OnStop=lambda: None))
        state, _ = core.fixture(modules=modules, ports={'Print': logs.append})
        state.Start()
        lines = [line for line in logs if any(line.startswith('[HC ' + name + ']')
                                              for name, _, _ in cases)]
        self.assertEqual(len(cases), len(lines), 'disabled and skipped modules need readiness lines')
        self.assertEqual(['[HC Disabled] off reason=module_not_enabled',
                          '[HC Skipped] off reason=provider_missing', '[HC Ready] ready',
                          '[HC Legacy] started reason=owner_state_unreported',
                          '[HC Conflict] off reason=owner_report_conflicts_with_no_start',
                          '[HC Degraded] degraded reason=partial_admission'], lines)
        self.assertEqual({name: 1 for name, _, _ in cases}, reads)
        self.assertEqual(['Skipped', 'Ready', 'Legacy', 'Degraded'], events)
        state.Start()  # idempotent start must not print another set
        self.assertEqual(lines, [line for line in logs if line in lines])


class ReadinessLint(unittest.TestCase):
    def test_registered_modules_need_names_and_engine_types_cannot_name_variables(self):
        from tools.validate import enforce_rules_readiness as rules
        # Explicit synthetic split registration, inheritance and modded-link fixtures.
        files = {'Core/HCModule.c': '''class HCModule { string GetName() { return "unnamed"; } }
            class HCModuleRegistry { void RegisterModules() {
              Register(new Good); Register(new Missing()); Register(new Inherited);
              Register(new Linked); Register(new IndirectMissing); } }''',
                 'Modules.c': '''class Good : HCModule { override string GetName() { return "ok"; } }
                     class Missing : HCModule {} class Inherited : Good {}
                     class Linked : HCModule {} modded class Linked { string GetName() { return "ok"; } }
                     class IndirectMissing : Missing {} class Unregistered : HCModule {}'''}
        findings = rules.module_readiness(files)
        self.assertEqual([('HC-S006', 'Missing'), ('HC-S006', 'IndirectMissing')],
                         [(row.rule, row.symbol) for row in findings])
        for name in rules.ENGINE_TYPE_NAMES:
            with self.subTest(name=name):
                text = ('class Synthetic { ref array<ref Object> ' + name + '; '
                        'void Run() { int ' + name + ' = 0; } }')
                rows = rules.engine_type_names(text, 'synthetic.c')
                self.assertEqual(2, len(rows))
                self.assertTrue(all(row.rule == 'HC-E009' for row in rows))
        text = '''class Safe { ref array<Object> actors;
            void Run(Object actor) { string note = "int Queue;";
              // int Param;
              Object.Cast(actor); int LocalityQueue = 0;
              int first, Queue; foreach (Object Object : actors) {}
              int scalar = Call(1, 2), Param = 0; }
            Object Object() { return null; } }'''
        self.assertEqual(['Queue', 'Object', 'Param'], [row.symbol.rsplit('.', 1)[-1]
                         for row in rules.engine_type_names(text)])
        # Both adapters are independently wireable into the shared lint dispatcher.
        from tools.validate.enforce_lint import lint_texts
        rows = lint_texts(files, rules=(rules.rule_module_names, rules.rule_engine_type_names))
        self.assertEqual({'Missing', 'IndirectMissing'}, {row.symbol for row in rows})
