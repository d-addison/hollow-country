"""Synthetic authored-policy fixtures; not VM, network or persistence proof."""
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

from tests.unit.test_group_server import body, execute_member, translated_rules

SOURCE = Path(__file__).resolve().parents[2] / (
    'mods/HollowCountry/scripts/4_World/Groups/HCGroupNativeChecks.c')
METHODS = ('Require Request ApplyCase Exercise BeginCases MarkerCases FinishCases '
           'Error Completion').split()


class GroupNativeChecksTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'missing opt-in synthetic group runner')
        self.source = re.sub(r'//[^\n]*', '', SOURCE.read_text())
        self.env = translated_rules()
        self.logs, self.calls, self.instances = [], [], []
        self.env['MAX_STEPS'] = int(re.search(
            r'MAX_STEPS = (\d+)', self.source)[1])
        self.env['str'] = str
        self.env['Print'] = self.logs.append
        self.env['serialize'] = lambda value: (
            True, json.dumps(value, default=vars, sort_keys=True), '')
        actual = self.env['Apply']

        def observed(*args):
            result = actual(*args)
            self.calls.append((args[2].Op, result))
            return result

        self.env['Apply'] = observed
        self.env['HCGroupNativeChecks'] = self.fixture

    def invoke(self, fixture, name, *args):
        match = re.search(
            r'\b(?:bool|int|string|HCGroupRequest) ' + name +
            r'\(([^)]*)\)\s*\{', self.source)
        self.assertIsNotNone(match, name)
        authored = body(self.source, match.end())
        for method in METHODS:
            authored = re.sub(r'(?<![\w.])' + method + r'\(',
                              'self.' + method + '(', authored)
        authored = authored.replace('m_Steps.ToString()', 'str(m_Steps)')
        if name == 'Run':
            # Adapt only the language's out parameter, preserving every guard.
            authored = re.sub(r'return (true|false);',
                              r'return \1, error;', authored)
        method = 'bool ' + name + '(' + match[1] + ') {' + authored + '}'
        return execute_member(method, name, self.env, fixture, *args)

    def fixture(self):
        # Explicit synthetic language scaffolding, matching field initializers.
        fixture = SimpleNamespace(
            m_State=self.env['HCGroupState'](),
            m_Config=self.env['HCGroupSettings'](),
            m_Steps=0, m_Now=1000, m_Error='')
        for name in METHODS:
            setattr(fixture, name, lambda *a, n=name: self.invoke(fixture, n, *a))
        self.instances.append(fixture)
        return fixture

    def run_fixture(self):
        return self.invoke(SimpleNamespace(), 'Run', 'previous error')

    def test_success_executes_all_thirteen_ops_before_completion(self):
        self.assertEqual((True, ''), self.run_fixture())
        self.assertEqual(set(range(1, 14)),
                         {op for op, result in self.calls if result == 0})
        self.assertGreater(len(self.calls), 12)
        self.assertLessEqual(len(self.calls), 64)
        self.assertEqual(self.instances[0].m_Steps, len(self.calls))
        self.assertEqual(len(self.logs), 1)
        self.assertIn('COMPLETE synthetic-policy-fixtures', self.logs[0])
        self.assertIn('wire=3 durable=1', self.logs[0])
        self.assertEqual([], self.instances[0].m_State.Groups)


    def test_rejected_mutation_cannot_print_completion(self):
        actual = self.env['Apply']

        def corrupt_rejection(*args):
            result = actual(*args)
            if result != 0:
                args[0].NextId += 1
            return result

        self.env['Apply'] = corrupt_rejection
        passed, error = self.run_fixture()
        self.assertFalse(passed)
        self.assertIn('rejected_state_changed', error)
        self.assertEqual([], self.logs)

    def test_unexpected_result_cannot_print_completion(self):
        self.env['Apply'] = lambda *args: self.env['HCGroupCode'].DENIED
        passed, error = self.run_fixture()
        self.assertFalse(passed)
        self.assertIn('create', error)
        self.assertEqual([], self.logs)

    def test_step_budget_rejects_before_apply(self):
        fixture = self.fixture()
        fixture.m_Steps = 64
        request = self.env['HCGroupRequest']()
        self.assertFalse(fixture.ApplyCase(request, 'fixture_alice', 0, 'overflow'))
        self.assertIn('step_budget', fixture.m_Error)
        self.assertEqual([], self.calls)

    def test_wire_version_pin_cannot_silently_drift(self):
        self.env['HCGroupProtocol'].VERSION = 1
        passed, error = self.run_fixture()
        self.assertFalse(passed)
        self.assertIn('wire_version', error)
        self.assertEqual([], self.calls)
        self.assertEqual([], self.logs)

    def test_opt_in_and_side_effect_contract(self):
        self.assertRegex(self.source, r'static bool Run\(out string error\)')
        self.assertEqual(64, self.env['MAX_STEPS'])
        self.assertEqual(1, len(re.findall(r'\bPrint\(', self.source)))
        self.assertNotRegex(self.source, r'\b(?:modded|override)\b')
        self.assertNotRegex(
            self.source,
            r'GetGame\(|g_Game|PlayerIdentity|ScriptRPC|OpenFile|'
            r'CreateObject|CallLater|HCGroupStore')

    def test_fixture_calls_do_not_bind_native_step_attribute_constructor(self):
        # Native 2_GameLib/tests/TestingFramework.c declares Step(EStage).
        self.assertNotRegex(self.source, r'\bStep\(')


if __name__ == '__main__':
    unittest.main()
