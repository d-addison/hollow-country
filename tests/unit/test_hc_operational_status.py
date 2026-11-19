"""HC-1 synthetic lifecycle: execute authored status/lifecycle bodies via existing ports.

No Python gameplay model, real configuration IO, engine compile or runtime proof.
The lead supplies HCModule.HCGetOperationalStatus(): default null, owners return
cached reports only. Trace: HC-1 / RUNTIME_IMPLEMENTATION_CONTRACT lifecycle.

Actual TDD command (RED then GREEN):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_operational_status -v
RED: AssertionError: False is not true : disabled module has no cached off row;
     lifecycle request is not health (1 test, 1 failure).
GREEN: Ran 1 test; OK. Offline policy evidence only; runtime=PENDING.
"""
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest

from tests.unit import test_core_lifecycle as core
from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / 'mods/HollowCountry/scripts/3_Game/HCOperationalStatus.c'
ADMISSION = ROOT / 'mods/HollowCountry/scripts/4_World/Core/HCV2Admission.c'


def authored_status(logs):
    """Syntax/DTO/native-array ports only; all status decisions come from Enforce."""
    if not STATUS.exists():
        return None, None
    source = STATUS.read_text().replace('HCOperational', 'HCEventOperational')
    row_source, cache_source = source.split('class HCEventOperationalStatusCache', 1)
    env = dict(Print=logs.append, str=str, len=len)
    row_type = type('AuthoredStatus', (), {})
    cache_type = type('AuthoredCache', (), {})
    env.update(HCEventOperationalStatus=row_type, HCEventOperationalStatusCache=cache_type)
    for cls, text in ((row_type, row_source), (cache_type, cache_source)):
        names = re.findall(r'\b(?:void|bool|int|string) (HC\w+)\(', text)
        for name in names:
            setattr(cls, name, translate(text, name, env, cls.__name__, True))
    def make_row():
        row = row_type()
        row.m_Name = ''
        row.m_State = 'unknown'
        row.m_Reason = 'owner_state_unknown'
        row.m_Readiness = 'unknown'
        row.m_StartRequested = False
        return row
    env['HCEventOperationalStatus'] = make_row
    cache = cache_type()
    cache.m_Rows = core.NativeArray()
    return make_row, cache


class OperationalLifecycleTests(unittest.TestCase):
    def test_cached_lifecycle_distinguishes_off_refused_ready_and_unknown_without_io(self):
        logs, events, reads, report_reads = [], [], {}, {}
        make_row, cache = authored_status(logs)
        # Explicit synthetic module admission outcomes, not real DayZ providers.
        cases = [('off', False, 'off'), ('missing-provider', False, 'refused'),
                 ('start-refused', True, 'refused'), ('ready', True, 'ready'),
                 ('degraded', True, 'degraded'), ('legacy', True, None),
                 ('legacy-off', False, None)]
        modules, reports = [], {}
        for name, enabled, reported in cases:
            report = None
            if make_row and reported:
                report = make_row()
                report.HCPublish(reported, 'synthetic_' + reported)
                reports[name] = report
            def is_enabled(settings, name=name, enabled=enabled):
                reads[name] = reads.get(name, 0) + 1
                if reads[name] > 1:
                    raise AssertionError('second side-effecting IsEnabled/config IO: ' + name)
                return enabled
            def status(name=name, report=report, enabled=enabled):
                self.assertEqual(1, reads.get(name))
                if enabled:
                    self.assertIn('start:' + name, events)
                report_reads[name] = report_reads.get(name, 0) + 1
                return report
            modules.append(N(GetName=lambda name=name: name, IsEnabled=is_enabled,
                             HCGetOperationalStatus=status,
                             OnStart=lambda settings, name=name: events.append('start:' + name),
                             OnStop=lambda name=name: events.append('stop:' + name)))
        game = N(IsServer=lambda: True, GetTickTime=lambda: 12,
                 GetCallQueue=lambda category: N(Remove=lambda fn: None, CallLater=lambda *args: None))
        env = dict(GetGame=lambda: game, HCNativeSelfTests=N(Run=lambda: True),
                   HCSettings=N(LoadFromProfile=lambda: N(TickIntervalMs=1000, EnableInfected=True)),
                   HCModuleRegistry=lambda: N(RegisterModules=lambda: None, GetModules=lambda: modules),
                   # Synthetic passive ports; HC-47 integration has its own
                   # authored-gate tests, independent of HC-1 cached receipts.
                   HCInfectedVisionQualification=N(HCThreatReset=lambda enabled: None),
                   HCInfectedReachPolicy=N(HCThreatSummary=lambda requested: '[HC Plan] HC-47 synthetic'),
                   Print=logs.append, CALL_CATEGORY_SYSTEM=0)
        admission_source = ADMISSION.read_text().replace('HCOperational', 'HCEventOperational')
        admission = N(Summary=lambda settings: 'synthetic preferences')
        env['HCV2Admission'] = admission
        if cache:
            admission.OperationalSummary = translate(admission_source, 'OperationalSummary', env)
            admission.NonModuleSummary = translate(admission_source, 'NonModuleSummary', env)
        state = N(m_Started=False, m_Active=core.NativeArray(), m_Registry=None,
                  m_Settings=None, m_LastTick=0, m_Operational=cache, Tick=lambda: None,
                  m_Perf=N(Start=lambda seconds: None, Stop=lambda: None,
                           RegisterModule=lambda name: None))
        state.Stop = lambda: core.actual_method('Stop', env)(state)
        core.actual_method('Start', env)(state)
        self.assertTrue(any('module=off state=off' in line for line in logs),
                        'disabled module has no cached off row; lifecycle request is not health')
        for name, _, reported in cases:
            expected = reported or ('requested' if name == 'legacy' else 'off')
            line = next(line for line in logs if 'module=' + name + ' ' in line)
            self.assertIn('state=' + expected, line)
            self.assertIn('runtime=PENDING', line)
            if reported is None:
                self.assertIn('readiness=unknown', line)
        self.assertEqual({name: 1 for name, _, _ in cases}, reads)
        self.assertEqual(reads, report_reads)
        server_source = core.SOURCE.read_text()
        for method in ('HCOperationalCount', 'HCOperationalLine', 'HCOperationalSummary'):
            fn = translate(server_source, method, env, 'HCServer', True)
            setattr(state, method, lambda *args, fn=fn: fn(state, *args))
        summary = state.HCOperationalSummary()
        self.assertEqual(7, state.HCOperationalCount())
        self.assertIn('[HC Plan] HC-1 status rows=7 off=2 refused=2', summary)
        self.assertIn('ready=1 degraded=1 requested=1 unknown=2', summary)
        for _ in range(3):
            self.assertEqual(summary, state.HCOperationalSummary())
            self.assertIn('state=refused', state.HCOperationalLine(1))
        self.assertEqual({name: 1 for name, _, _ in cases}, reads)
        self.assertEqual(reads, report_reads)
        # Captured values do not change when an owner mutates its report later.
        reports['degraded'].HCPublish('ready', 'synthetic_later_change')
        self.assertIn('module=degraded state=degraded', cache.HCLine(4))
        self.assertIn('Fuel=unknown Stamina=unknown Weather=unknown', admission.NonModuleSummary())
        self.assertIn('MealBuffs=removal_requested', admission.NonModuleSummary())
        state.Stop()
        self.assertEqual(['stop:legacy', 'stop:degraded', 'stop:ready', 'stop:start-refused'],
                         [event for event in events if event.startswith('stop:')])
        self.assertIn('rows=7 off=7 refused=0 ready=0', cache.HCSummary())
        # A failed restart must discard prior observations before returning.
        env['HCNativeSelfTests'].Run = lambda: False
        core.actual_method('Start', env)(state)
        self.assertIn('rows=0', cache.HCSummary())
        # The status cache shares the registry's hard 64-row bound.
        for index in range(70):
            cache.HCCapture('synthetic-' + str(index), True, None)
        self.assertEqual(64, cache.HCCount())
        self.assertEqual('', cache.HCLine(-1))
        self.assertEqual('', cache.HCLine(64))


if __name__ == '__main__':
    unittest.main()


class OperationalStatusHook(unittest.TestCase):
    def test_base_module_declares_default_null_status_hook_used_by_server(self):
        root = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Core'
        module = (root / 'HCModule.c').read_text()
        base = module[module.index('class HCModule\n'):module.index('class HCModuleRegistry')]
        self.assertRegex(base, r'HCOperationalStatus\s+HCGetOperationalStatus\(\)\s*\{\s*return\s+null;\s*\}')
        self.assertIn('module.HCGetOperationalStatus()', (root / 'HCServer.c').read_text())


class StartLoopHasNoContinue(unittest.TestCase):
    """Boots 040 and 041 (native 1.30 server): with the status object passed
    straight from module.HCGetOperationalStatus() into HCCapture inside
    `foreach (... : m_Registry.GetModules())`, later iterations raised
    'NULL pointer to instance' on the foreach line and replayed one module, so
    later modules never started. Keep the array and status in named locals and
    avoid `continue` in the loop."""

    def test_server_start_module_loop_avoids_continue(self):
        server = (ROOT / 'mods/HollowCountry/scripts/4_World/Core/HCServer.c').read_text()
        start = server.index('void Start()')
        loop = server.index('foreach (HCModule module : modules)', start)
        body_start = server.index('{', loop)
        depth, i = 0, body_start
        while True:
            if server[i] == '{':
                depth += 1
            elif server[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = server[body_start:i]
        self.assertNotIn('continue', body)
        self.assertEqual(1, body.count('module.IsEnabled(m_Settings)'))
        self.assertEqual(1, body.count('m_Operational.HCCapture(module.GetName(), moduleEnabled, reported)'))
        self.assertIn('array<ref HCModule> modules = m_Registry.GetModules();', server[start:loop])


if __name__ == '__main__':
    unittest.main()
