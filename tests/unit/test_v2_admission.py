"""V2 admission line and preferences summary (LC-T003, V2 core issue).

Every V2 module logs one admission line naming its preference, its Gate
experiment and whether the experiment register qualifies it. Owner decision
2026-11-17: V2 features are on by default, so a missing verdict is logged as
unverified rather than blocking. At Start the core prints the eight V2
preferences. These are authored Enforce bodies run by the restricted
translators; nothing here establishes DayZ behaviour.

TDD record (2026-11-17): RED before HCV2Admission.c existed:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v2_admission
failed with AssertionError: missing V2 admission source HCV2Admission.c.
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit import test_core_lifecycle as core
from tests.unit.test_event_runtime import translate
from tools.validate.runtime import V2_FLAGS as RUNTIME_FLAGS

# EnableTapedPackMounts is a default-off gate switch (#58), not a V2 preference.
V2_FLAGS = {flag for flag in RUNTIME_FLAGS if flag != 'EnableTapedPackMounts'}

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Core/HCV2Admission.c'
SETTINGS = ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c'


def admission():
    if not SOURCE.is_file():
        raise AssertionError('missing V2 admission source HCV2Admission.c')
    text = SOURCE.read_text()
    env = {'str': str, 'len': len}
    owner = N()
    env['HCV2Admission'] = owner
    for name in ('OnOff', 'Admitted', 'Line', 'Summary'):
        setattr(owner, name, translate(text, name, env, 'HCV2Admission'))
    return owner


def settings(**overrides):
    values = {flag: True for flag in V2_FLAGS}
    values.update(overrides)
    return N(**values)


class AdmissionLineTests(unittest.TestCase):
    def setUp(self):
        self.a = admission()

    def test_a_qualified_preferred_feature_is_admitted(self):
        self.assertEqual(
            '[HollowCountry] V2 admission feature=Grade preference=on gate=EXP-A1 qualified=1 result=admitted',
            self.a.Line('Grade', True, 'EXP-A1', True))

    def test_an_unqualified_gate_admits_on_by_default_and_logs_it_unverified(self):
        # Owner decision 2026-11-17: V2 features are on by default.
        self.assertEqual(
            '[HollowCountry] V2 admission feature=Camps preference=on gate=EXP-S2 qualified=0 '
            'result=admitted unverified: EXP-S2 has no recorded native verdict',
            self.a.Line('Camps', True, 'EXP-S2', False))

    def test_the_operator_preference_wins_over_any_verdict(self):
        for qualified in (True, False):
            with self.subTest(qualified=qualified):
                line = self.a.Line('Travel', False, 'EXP-T1', qualified)
                self.assertTrue(line.endswith('result=off: operator preference'), line)
                self.assertIn('preference=off', line)
                self.assertIn('qualified=' + ('1' if qualified else '0'), line)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.a = admission()

    def test_the_summary_lists_every_v2_preference_from_the_settings_class(self):
        declared = re.findall(r'bool (Enable\w+) = true;', SETTINGS.read_text())
        self.assertEqual(set(V2_FLAGS), set(declared) & set(V2_FLAGS))
        line = self.a.Summary(settings(EnableCamps=False))
        for flag in V2_FLAGS:
            name = flag[len('Enable'):]
            with self.subTest(flag=flag):
                self.assertIn(name + '=' + ('off' if flag == 'EnableCamps' else 'on'), line)
        self.assertTrue(line.startswith('[HollowCountry] V2 preferences '), line)
        self.assertTrue(line.endswith('V2 features on by default, gate verdicts logged per module; runtime acceptance pending'), line)

    def test_missing_settings_report_unavailable_without_claiming_preferences(self):
        line = self.a.Summary(None)
        self.assertIn('unavailable', line)
        self.assertNotIn('=on', line)


class StartPrintTests(unittest.TestCase):
    def test_start_prints_the_v2_summary_before_the_initialized_line(self):
        logs = []
        queue = N(Remove=lambda fn: None, CallLater=lambda *args: None)
        game = N(IsServer=lambda: True, GetTickTime=lambda: 12, GetCallQueue=lambda category: queue)
        loaded = settings(EnableWorld=False)
        loaded.TickIntervalMs = 1000
        loaded.EnableInfected = False
        registry = N(RegisterModules=lambda: None, GetModules=lambda: [])
        context = {'GetGame': lambda: game, 'HCNativeSelfTests': N(Run=lambda: True),
                   'HCSettings': N(LoadFromProfile=lambda: loaded), 'HCModuleRegistry': lambda: registry,
                   'Print': logs.append, 'CALL_CATEGORY_SYSTEM': 0, 'TickCount': lambda prior: 0,
                   'HCV2Admission': admission(),
                   'HCOperationalContributors': N(HCReset=lambda: None, HCRegisterOwner=lambda name: None,
                                                  HCReport=lambda: None),
                   'HCInfectedVisionQualification': N(HCThreatReset=lambda enabled: None),
                   'HCInfectedReachPolicy': N(HCThreatSummary=lambda requested: '[HC Plan] HC-47 synthetic')}
        # HC-1: Start also prints the cached module status receipts.
        context['HCV2Admission'].OperationalSummary = lambda cache: '[HC Plan] HC-1 status rows=0'
        context['HCV2Admission'].NonModuleSummary = lambda: '[HC Plan] HC-1 non-module'
        state = N(m_Started=False, m_Active=core.NativeArray(), m_Settings=None, m_Registry=None,
                  m_Operational=N(HCReset=lambda: None, HCStopAll=lambda: None,
                                  HCCapture=lambda name, requested, reported: None),
                  m_LastTick=0, Tick=lambda: None, Stop=lambda: None,
                  m_Perf=N(Start=lambda seconds: None, RegisterModule=lambda name: None))
        core.actual_method('Start', context)(state)
        summary = [i for i, l in enumerate(logs) if l.startswith('[HollowCountry] V2 preferences ')]
        ready = [i for i, l in enumerate(logs) if 'Server initialized' in l]
        self.assertEqual(1, len(summary), logs)
        self.assertEqual(1, len(ready), logs)
        self.assertLess(summary[0], ready[0])
        self.assertIn('World=off', logs[summary[0]])


class GateMirrorTests(unittest.TestCase):
    def test_compiled_gates_mirror_the_register_qualifying_verdicts(self):
        from tools.validate import experiments as ex
        text = (ROOT / 'mods/HollowCountry/scripts/4_World/Core/HCV2Gates.c').read_text()
        compiled = set(re.search(r'QUALIFIED = "([^"]*)";', text)[1].split())
        data = ex.load(ex.REGISTER)
        self.assertEqual({i for i in ex.IDS if ex.qualified(data, i)}, compiled)


if __name__ == '__main__':
    unittest.main()
