"""#160 final burn (w28-s160): the last HC-S001 and HC-S005 baseline entries.

Authored C bodies run through the repo's syntax adapters; engine, store and
module ports are explicit synthetic stand-ins. Offline tests never establish
DayZ behaviour; every runtime claim stays pending a native boot.

RED (2026-11-19, base ead3f87):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_s160_final_burn -v
GREEN: same command after the edits, see the commit message.
"""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.json_loader_port import decode_json, json_fields_port
from tests.unit import test_interior_catalog as measured_fixtures
from tests.unit.test_enforce_lint import G, W, run, where
from tests.unit.test_hc_burn_infected import brace_ifs
from tests.unit.test_hc_scavenge import bind
from tests.unit.test_map_layers import EStr
from tests.unit.test_interior_measured_catalog import fixture as measured_fixture
from tools.validate import enforce_json
from tools.validate import enforce_lint as lint
from tools.validate import enforce_source as es

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts'
XAI = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAISites.c'


def read(relative):
    return (SCRIPTS / relative).read_text()


def execute_present():
    """Authored HCSearchRetirementStore.HCFieldsPresent over the authored HCJsonFields."""
    from tests.unit.test_event_runtime import translate
    return translate(read('4_World/Loot/HCSearchRefresh.c'), 'HCFieldsPresent', {'HCJsonFields': json_fields_port()})


def adapt(source):
    """Syntax only: drop comments and brace single-statement ifs for the adapter."""
    return brace_ifs(re.sub(r'(?m)(?<=\s)//[^\n]*|^//[^\n]*', '', source))


class FinishedGuardLint(unittest.TestCase):
    """Teach HC-S001 only the exact already-printed/already-finished re-entry guard."""
    TEXT = ('class HCStartup : HCModule\n{\n    bool m_Printed;\n    bool m_HCFinished;\n    bool m_Busy;\n'
            '    override void OnStart(HCSettings settings)\n    {\n        GUARD\n        m_Printed = true;\n    }\n}\n')

    def flagged(self, guard):
        return where(run({W + 'Survival/HCStartup.c': self.TEXT.replace('GUARD', guard)}, 'HC-S001'))

    def test_a_bare_already_printed_or_finished_member_is_an_idempotent_reentry(self):
        self.assertEqual([], self.flagged('if (m_Printed) { return; }'))
        self.assertEqual([], self.flagged('if (m_HCFinished) { return; }'))

    def test_the_inverse_and_other_busy_flags_are_still_silent_refusals(self):
        self.assertEqual([('HCStartup.c', 8, 'HCStartup.OnStart')], self.flagged('if (!m_Printed) { return; }'))
        self.assertEqual([('HCStartup.c', 8, 'HCStartup.OnStart')], self.flagged('if (m_Busy) { return; }'))
        self.assertEqual([('HCStartup.c', 8, 'HCStartup.OnStart')],
                         self.flagged('if (m_Printed && Other()) { return; }'))

    def test_the_shape_never_exempts_a_bool_gate(self):
        text = ('class HCGate\n{\n    bool m_Printed;\n    bool Admit(PlayerBase player)\n    {\n'
                '        if (m_Printed) return false;\n        return true;\n    }\n}\n')
        self.assertEqual([('HCGate.c', 6, 'HCGate.Admit')], where(run({W + 'Survival/HCGate.c': text}, 'HC-S002')))


class ModuleReasons(unittest.TestCase):
    def test_infected_memory_reentry_names_a_reason_once_per_start(self):
        logs = []
        source = read('4_World/Infected/HCInfectedMemory.c').split('class HCInfectedMemoryModule', 1)[1]
        source = 'class HCInfectedMemoryModule' + source
        created = []
        memory = lambda: created.append(1) or N(Start=lambda: None)
        env = dict(Print=logs.append, GetGame=lambda: N(IsServer=lambda: True),
                   HCV2Admission=N(Line=lambda *a: 'admission'), HCV2Gates=N(Qualified=lambda g: False),
                   HCInfectedMemory=memory)
        module = N(m_Memory=None, IsEnabled=lambda settings: True)
        bind(adapt(source), 'HCInfectedMemoryModule', module, ('OnStart',), env)
        module.OnStart(N())
        module.m_Memory = N()
        module.OnStart(N())
        self.assertEqual(['admission', '[HC InfectedMemory] start ignored: already_started'], logs)
        self.assertEqual(1, len(created))
        logs.clear()
        module.m_Memory = None
        module.IsEnabled = lambda settings: False
        module.OnStart(N())
        self.assertEqual([], logs, 'a disabled module is the operator choice, reported by HCServer')

    def test_atmosphere_start_names_a_reason_when_its_qualification_does_not_admit(self):
        logs = []
        source = read('4_World/Weather/HCAtmosphereLifecycle.c')
        source = source.split('string atmosphereWorld;', 1)[0] + '}\n}\n'
        source = source.replace('super.Start();', '')
        env = dict(Print=logs.append, HCAtmosphereQualification=N(Enabled=lambda: False))
        server = N()
        bind(adapt(source), 'HCServer', server, ('Start',), env)
        server.Start()
        self.assertEqual(['[HollowCountry][Atmosphere] not started: qualification gates not admitted '
                          '(see the Atmosphere reason line above when a gate refused); vanilla weather retained'], logs)

    def test_a_missing_optional_legacy_interiors_pilot_file_says_so(self):
        logs = []
        source = read('4_World/Interiors/HCInteriorModule.c')
        start = source.index('override void OnStart(HCSettings settings)')
        text = 'class X\n{\n    ' + source[start:source.index('if (!HCInteriorJson<HCInteriorConfig>.Load', start)]
        text = re.sub(r'#ifdef.*?#endif', '', text, flags=re.S) + '}\n}\n'
        text = text.replace('override void OnStart', 'void OnStart')
        env = dict(Print=logs.append, GetGame=lambda: N(IsServer=lambda: True), FileExist=lambda path: False,
                   s_Instance=None, IsEnabled=lambda settings: True)
        module = N(IsEnabled=lambda settings: True)
        bind(adapt(text), 'X', module, ('OnStart',), env)
        module.OnStart(N())
        self.assertEqual(['[HC Interiors] legacy pilot off: interiors.json absent (optional); '
                          'no pilot search or placement'], logs)


class SiteReentryReasons(unittest.TestCase):
    def setUp(self):
        from tests.unit.test_expansion_ai_adapter import A, Authored
        self.logs, self.now = [], [1000]
        env = dict(A=A, len=len, str=str, Print=self.logs.append,
                   GetGame=lambda: N(GetTime=lambda: self.now[0]),
                   HCXAISiteDirector=N(Active=lambda: None))
        source = XAI.read_text()
        source = source.replace('m_HCSiteId.Substring(10, m_HCSiteId.Length() - 10)', 'synthetic_suffix(m_HCSiteId)')
        source = source.replace('super.Spawn();', 'synthetic_spawn(this);')
        source = source.replace('super.SpawnAI_Deferred(i);', 'synthetic_super(i);')
        # Named const the sources read bare (lowered from the authored declaration).
        for name, value in re.findall(r'static const int (HC_\w+) = (\d+);', source):
            env[name] = int(value)
        self.authored = Authored(source, env)

    def patrol(self, **fields):
        owner = N(m_Group=None, m_Formation=None, m_HCFinished=False, m_HCTransient=False,
                  m_HCSiteId='synthetic-site', m_HCNextBudgetLogMs=0, m_HCNextSkipLogMs=0, m_HCPendingMembers=0)
        owner.__dict__.update(fields)
        owner.HCRefuseBudget = lambda *a: self.authored.call('HCRefuseBudget', owner, *a)
        owner.HCLogSkipped = lambda *a: self.authored.call('HCLogSkipped', owner, *a)
        return owner

    def test_spawn_with_a_live_group_is_a_skip_line_with_its_own_limiter_and_a_finished_site_stays_quiet(self):
        patrol = self.patrol(m_Group=N(Count=lambda: 2))
        for _ in range(20):
            self.authored.call('Spawn', patrol)
        self.assertEqual(['[HC Expansion AI] site synthetic-site spawn skipped: group already live'], self.logs)
        self.logs.clear()
        done = self.patrol(m_HCFinished=True)
        self.authored.call('Spawn', done)
        self.assertEqual([], self.logs)

    def test_a_benign_reentry_never_masks_a_real_refusal(self):
        # #194: the re-entry used the shared 60 s refusal limiter, so a real refusal inside that
        # window was swallowed. The two lines are limited separately, in either order.
        patrol = self.patrol(m_Group=N(Count=lambda: 2))
        self.authored.call('Spawn', patrol)
        patrol.m_Group = None
        self.now[0] += 1000
        self.authored.call('Spawn', patrol)
        self.assertEqual(['[HC Expansion AI] site synthetic-site spawn skipped: group already live',
                          '[HC Expansion AI] site synthetic-site spawn refused: sites not running'], self.logs)
        again = self.patrol()
        self.logs.clear()
        self.authored.call('Spawn', again)
        again.m_Group = N(Count=lambda: 2)
        self.now[0] += 1000
        self.authored.call('Spawn', again)
        self.assertEqual(['[HC Expansion AI] site synthetic-site spawn refused: sites not running',
                          '[HC Expansion AI] site synthetic-site spawn skipped: group already live'], self.logs)
        self.now[0] += 100000
        again.m_Group = None
        self.authored.call('Spawn', again)
        self.assertEqual(3, len(self.logs), 'each limiter still reopens after its own interval')
        self.assertFalse([line for line in self.logs if 'group already spawned' in line])

    def test_deferred_member_of_an_emptied_transient_group_names_a_bounded_reason(self):
        patrol = self.patrol(m_HCTransient=True, m_Group=N(Count=lambda: 0), m_Formation=N())
        for index in range(1, 6):
            self.authored.call('SpawnAI_Deferred', patrol, index)
        self.assertEqual(['[HC Expansion AI] site synthetic-site spawn refused: '
                          'transient group emptied before member spawn'], self.logs)
        self.assertEqual(0, patrol.m_HCPendingMembers)
        self.logs.clear()
        done = self.patrol(m_HCFinished=True, m_Group=N(Count=lambda: 0))
        self.authored.call('SpawnAI_Deferred', done, 1)
        self.assertEqual([], self.logs)


class MeasuredPropIndex(unittest.TestCase):
    PATH = '$profile:HollowCountry/measured-interiors/measured-record.json'

    def boot(self, drop_index):
        e, raw, calls, house, objects, candidate, profile = measured_fixture()
        logs = []
        e['Print'] = logs.append
        e['HCJsonFields'] = json_fields_port()
        if drop_index:
            record = json.loads(raw[self.PATH])
            for layout in record['Layouts']:
                del layout['Survey']['Props'][0]['Index']
            edited = measured_fixtures.encode(record).decode()
            profile['ExpectedRecordText'] = edited
            raw[self.PATH] = edited
            raw['$profile:HollowCountry/interiors-measured-profile.json'] = json.dumps(profile)
        e['MeasuredEnsureLoaded']()
        return e, calls, logs

    def test_a_missing_index_zero_fills_and_would_alias_the_first_prop(self):
        prop = decode_json('{"Room":"kitchen","Observation":"a"}', 'HCInteriorMeasuredCatalogMeasuredProp')
        self.assertEqual(0, prop.Index, 'synthetic native zero-fill, not the -1 initializer')

    def test_a_record_with_a_prop_missing_index_is_refused_with_a_named_reason(self):
        e, calls, logs = self.boot(True)
        self.assertIsNone(e['s_Binding'])
        self.assertEqual(1, calls['parse'], 'only the profile may reach LoadData')
        self.assertEqual(['[HC Interiors] measured record refused: measured_prop_index_missing; '
                          'native acceptance pending'], logs)

    def test_a_complete_record_still_binds_and_reports_no_refusal(self):
        e, calls, logs = self.boot(False)
        self.assertIsNotNone(e['s_Binding'])
        self.assertFalse([line for line in logs if 'refused' in line])

    def test_the_presence_guard_names_the_prop_depth_and_selector(self):
        present = json_fields_port()
        prop = '{"Index":%d,"Room":"r","Bounds":{"Min":[0],"Max":[1]},"Observation":"o"}'
        keepout = '{"Id":"k","Kind":"door","Bounds":{"Min":[0],"Max":[1]}}'
        good = '{"Layouts":[{"Survey":{"Props":[' + prop % 0 + ',' + prop % 1 + '],"Keepouts":[' + keepout + ']}}]}'
        self.assertTrue(present.Every(good, 'Index', 6, 'Room'))
        bad = good.replace('"Index":1,', '')
        self.assertFalse(present.Every(bad, 'Index', 6, 'Room'))


class LegacyDtoPresenceGuards(unittest.TestCase):
    """The two former LEGACY_BASELINE S005 entries now read raw-key presence."""

    def test_group_request_send_refuses_a_payload_without_color(self):
        logs = []
        source = (SCRIPTS / '5_Mission/Groups/HCGroupClient.c').read_text()
        source = source.replace('JsonFileLoader<HCGroupRequest>.MakeData(request, m_PendingPayload, error)',
                                'synthetic_make(request)')
        source = source.replace('JsonFileLoader<HCGroupRequest>.LoadData(m_PendingPayload, m_Pending, error)',
                                'synthetic_load()')
        target = N(m_View=N(Enabled=True), m_Pending=None, m_Session='s', m_RequestId=0, m_Revision=0,
                   m_PendingPayload='', m_MutationGeneration=0, m_Retries=0, m_Notice='', Transmit=lambda r: None)
        payload = ['{"Version":3,"RequestId":1,"Color":-1}']

        def make(request):
            target.m_PendingPayload = EStr(payload[0])
            return True

        def load():
            target.m_Pending = N(RequestId=1)
            return True

        env = dict(Print=logs.append, HCJsonFields=json_fields_port(), synthetic_make=make, synthetic_load=load,
                   HCGroupRules=N(TextValid=lambda *a: True), HCGroupProtocol=N(VERSION=3), Transmit=lambda r: None)
        start = source.index('    bool Send(HCGroupRequest request)')
        fields = ''.join('    int %s;\n' % name for name in (
            'm_View', 'm_Pending', 'm_Session', 'm_RequestId', 'm_Revision', 'm_PendingPayload',
            'm_MutationGeneration', 'm_Retries', 'm_Notice', 'm_LastSend'))
        text = 'class X\n{\n' + fields + source[start:source.index('    void ReceiveReply', start)] + '}\n'
        bind(adapt(text), 'X', target, ('Send',), env)
        request = N(Op=1, Name='', Note='', TargetId='', Version=0, Session='', RequestId=0, ExpectedRevision=0)
        payload[0] = '{"Version":3,"RequestId":1,"Op":1}'
        self.assertFalse(target.Send(request))
        self.assertIsNone(target.m_Pending)
        self.assertEqual('', target.m_PendingPayload)
        self.assertEqual(['[HC Groups] request not sent: Color missing from the serialized payload; runtime=PENDING'], logs)
        payload[0] = '{"Version":3,"RequestId":1,"Op":1,"Color":-1}'
        self.assertTrue(target.Send(request))
        self.assertIsNotNone(target.m_Pending)

    def retired_store(self, raw, recent_count=0, recent=()):
        logs = []
        source = read('4_World/Loot/HCSearchRefresh.c').split('class HCSearchRetirementStore', 1)[1]
        source = 'class HCSearchRetirementStore' + source.split('    bool Contains(string supplyId)', 1)[0] + '}\n'
        for call, port in (('HCV2ThreatStore<HCSearchRetirementState>.CanOpen(m_Path)', 'synthetic_can()'),
                           ('HCV2ThreatStore<HCSearchRetirementState>.Load(m_Path, MAX_BYTES, m_Data)', 'synthetic_load()'),
                           ('HCV2ThreatStore<HCSearchRetirementState>.Save(m_Path, m_Data, MAX_BYTES)', 'synthetic_save()'),
                           ('HCGroupIO.Read(m_Path, MAX_BYTES, image)', 'synthetic_read()')):
            source = source.replace(call, port)
        source = source.replace('m_RecentIds.', 'synthetic_ids.')

        class Arr(list):
            def Count(self): return len(self)
            def __bool__(self): return True

        state = N(Version=1, RecentCount=recent_count, Recent=Arr(recent), Archive=Arr([0] * 2048))
        store = N(m_Path='', m_Root='', m_Data=None, m_EvictionLogged=False)

        def load():
            store.m_Data = state
            return True

        present = execute_present()
        env = dict(Print=logs.append, FileExist=lambda path: True, synthetic_ids=N(Contains=lambda k: False, Set=lambda k, v: None), synthetic_can=lambda: True,
                   synthetic_load=load, synthetic_read=lambda: True, synthetic_save=lambda: True,
                   MAX_BYTES=524288, HCSearchRetirementPolicy=N(MAX_RECENT=2048, BUCKETS=2048),
                   HCFieldsPresent=lambda text: present(raw),
                   HCSearchRules=N(TextValid=lambda *a: True))
        bind(adapt(source), 'HCSearchRetirementStore', store, ('Open',), env)
        return store, logs

    def test_retired_json_without_recent_count_is_refused_with_a_reason(self):
        store, logs = self.retired_store('{"Version":1,"Recent":[],"Archive":[0]}')
        data = decode_json('{"Version":1,"Recent":[],"Archive":[0]}', 'HCSearchRetirementState')
        self.assertEqual(0, data.RecentCount, 'synthetic native zero-fill, not the -1 sentinel')
        self.assertFalse(store.Open('root'))
        self.assertEqual(['[HC Search] retired.json refused: RecentCount missing or unreadable; '
                          'no replay barrier is rewound'], logs)

    def test_retired_json_with_recent_count_opens(self):
        store, logs = self.retired_store('{"Version":1,"RecentCount":0,"Recent":[],"Archive":[0]}')
        self.assertTrue(store.Open('root'))
        self.assertEqual([], logs)


class LintRetirement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.findings = lint.lint(es.mod_sources(ROOT))

    def test_no_hc_s001_or_hc_s005_finding_remains(self):
        self.assertEqual([], [(f.rule, f.symbol) for f in self.findings if f.rule in ('HC-S001', 'HC-S005')])

    def test_the_legacy_s005_exceptions_are_gone(self):
        self.assertEqual([], enforce_json.LEGACY_BASELINE)


if __name__ == '__main__':
    unittest.main()
