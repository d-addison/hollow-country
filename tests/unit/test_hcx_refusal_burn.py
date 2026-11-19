"""#160 HC-S001/S002 burn-down for the Expansion AI addon: refusals carry a stable reason.

Authored C bodies run through the repo's syntax adapter (Authored); the engine, director,
journal store and Expansion ports are explicit synthetic fixtures. Nothing here observes
DayZ: the reasons are read by logs and accessors only until a native boot reads them.
"""
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

# Module imports (not class imports) keep the neighbours' TestCases out of this module.
from tests.unit import test_expansion_ai_adapter as adapter_suite
from tests.unit import test_expansion_ai_encounters as encounter_suite
from tests.unit.test_expansion_ai_adapter import A, Authored, declarations
from tests.unit.test_expansion_ai_sites import api

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'
HCREFUSAL = N(BUSY='busy', SERVICE='service', CAPACITY='capacity', NO_SITE='no_site')


def lines(logs, needle):
    return [text for text in logs if needle in text]


class AdapterLeaseRefusals(unittest.TestCase):
    def setUp(self):
        self.t = adapter_suite.ExpansionAdapterTests()
        self.t.setUp()

    def diagnostics(self):
        return [c[1] for c in self.t.calls if c[0] == 'diagnostic']

    def test_start_before_install_reports_adapter_not_ready_once(self):
        self.assertFalse(self.t.start())
        self.assertEqual('adapter_not_ready', self.t.mod.LeaseRefusal())
        self.assertFalse(self.t.start(lease='second'))
        refused = lines(self.diagnostics(), 'lease start refused')
        self.assertEqual(['[HC Expansion AI] lease start refused reason=adapter_not_ready'], refused)

    def test_bad_tokens_and_unqualified_route_and_unfair_faction_have_distinct_reasons(self):
        self.assertTrue(self.t.install())
        self.assertFalse(self.t.start(lease=''))
        self.assertEqual('bad_lease_token', self.t.mod.LeaseRefusal())
        self.t.hooks.RouteQualified = lambda *a: False
        self.assertFalse(self.t.start(lease='unqualified'))
        self.assertEqual('route_unqualified', self.t.mod.LeaseRefusal())
        self.t.hooks.RouteQualified = lambda *a: True
        self.t.faction.IsInvincible = lambda: True
        self.assertFalse(self.t.start(lease='unfair'))
        self.assertEqual('faction_unfair', self.t.mod.LeaseRefusal())
        self.t.faction.IsInvincible = lambda: False
        self.t.faction.GetMeleeYeetForce = lambda: 5.
        self.assertFalse(self.t.start(lease='yeet'))
        self.assertEqual('faction_melee_unfair', self.t.mod.LeaseRefusal())
        self.assertEqual(4, len(lines(self.diagnostics(), 'lease start refused')))
        self.assertEqual([], self.t.mod.m_Leases)

    def test_reentrant_start_reports_busy_and_an_accepted_start_clears_the_reason(self):
        self.assertTrue(self.t.install())
        self.t.mod.m_Starting = True
        self.assertFalse(self.t.start(lease='nested'))
        self.assertEqual('busy', self.t.mod.LeaseRefusal())
        self.t.mod.m_Starting = False
        self.assertTrue(self.t.start(lease='fine'))
        self.assertEqual('', self.t.mod.LeaseRefusal())

    def test_unconfirmed_journal_intent_and_group_failure_keep_their_state_and_reason(self):
        self.assertTrue(self.t.install())
        self.t.journal_ok = False
        self.assertFalse(self.t.start(lease='uncertain'))
        self.assertEqual('journal_intent_unconfirmed', self.t.mod.LeaseRefusal())
        self.assertTrue(self.t.mod.m_Leases[0].Failed)
        self.assertTrue(self.t.mod.m_Leases[0].Retiring)

    def test_idempotent_restart_mismatch_names_a_reason_and_a_match_clears_it(self):
        self.assertTrue(self.t.install())
        self.assertTrue(self.t.start(lease='again'))
        self.t.mod.m_LeaseRefusal = 'stale_reason'
        self.assertTrue(self.t.start(lease='again'))
        self.assertEqual('', self.t.mod.LeaseRefusal())
        self.assertFalse(self.t.start(lease='again', cap=3))
        self.assertEqual('lease_params_mismatch', self.t.mod.LeaseRefusal())
        self.assertFalse(self.t.start(lease='again', session='other-session'))
        self.assertEqual('lease_params_mismatch', self.t.mod.LeaseRefusal())
        self.assertEqual(1, len(lines(self.diagnostics(), 'reason=lease_params_mismatch')))
        self.t.mod.m_Leases[0].Retiring = True
        self.assertFalse(self.t.start(lease='again'))
        self.assertEqual('lease_not_active', self.t.mod.LeaseRefusal())
        self.assertEqual(1, len(self.t.mod.m_Leases))

    def test_cap_anchor_group_and_capacity_refusals_log_once_per_reason_change(self):
        self.assertTrue(self.t.install())
        self.assertFalse(self.t.start(lease='big', cap=5))
        self.assertEqual('actor_cap_limit', self.t.mod.LeaseRefusal())
        self.assertFalse(self.t.start(lease='big2', cap=5))
        self.assertFalse(self.t.mod.StartLease('far', 'event-session', 'mission-site-5', (1., 0., 1.), 4))
        self.assertEqual('mission_or_anchor', self.t.mod.LeaseRefusal())
        self.assertFalse(self.t.start(lease='small', cap=1))
        self.assertEqual('group_size', self.t.mod.LeaseRefusal())
        self.t.ai_limits.MaxLiveGroups = 1
        self.assertTrue(self.t.start(lease='first'))
        self.assertFalse(self.t.start(lease='second'))
        self.assertEqual('capacity', self.t.mod.LeaseRefusal())
        self.assertFalse(self.t.start(lease='third'))
        reasons = [re.search(r'reason=(\w+)', l)[1] for l in lines(self.diagnostics(), 'lease start refused')]
        self.assertEqual(['actor_cap_limit', 'mission_or_anchor', 'group_size', 'capacity'], reasons)
        self.assertEqual([], lines(self.diagnostics(), '[HC AI] adapter'))


class JournalBeginRefusals(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.ok = True
        self.env = dict(A=A, Print=self.logs.append, HCRefusal=HCREFUSAL, GetGame=lambda: N(IsServer=lambda: True))
        declarations(self.env)
        self.env['HCXAIStore'] = N(SaveJournal=lambda data: self.ok)
        self.env['HCXAIRules'] = N(Token=lambda s: isinstance(s, str) and 0 < len(s) <= 128)
        self.code = Authored((SCRIPTS / 'HCXAIJournal.c').read_text(), self.env)
        self.owner = N(m_Data=self.env['HCXAIJournalData'](), m_Session='new-process', m_Limit=2, m_Refusal='')
        self.owner.m_Data.Rows = A()
        self.owner.m_Data.SchemaVersion = 1
        for name in ('Valid', 'Begin', 'RefuseBegin', 'Refusal', 'PrepareBegin', 'Prune'):
            setattr(self.owner, name, lambda *a, n=name: self.code.call(n, self.owner, *a))

    def test_each_begin_refusal_has_a_reason_and_logs_once_per_change(self):
        self.assertFalse(self.owner.Begin('', 'event', 'site'))
        self.assertEqual('bad_token', self.owner.Refusal())
        self.assertFalse(self.owner.Begin('', 'event', 'site'))
        self.assertEqual(1, len(lines(self.logs, 'reason=bad_token')))
        self.assertTrue(self.owner.Begin('one', 'event', 'site'))
        self.assertEqual('', self.owner.Refusal())
        self.assertFalse(self.owner.Begin('one', 'event', 'site'))
        self.assertEqual('duplicate_id', self.owner.Refusal())
        self.assertTrue(self.owner.Begin('two', 'event', 'site'))
        self.assertFalse(self.owner.Begin('three', 'event', 'site'))
        self.assertEqual('capacity', self.owner.Refusal())
        self.owner.m_Data.SchemaVersion = 9
        self.assertFalse(self.owner.Begin('four', 'event', 'site'))
        self.assertEqual('journal_invalid', self.owner.Refusal())
        self.assertEqual(['bad_token', 'duplicate_id', 'capacity', 'journal_invalid'],
                         [re.search(r'reason=(\w+)', l)[1] for l in lines(self.logs, 'intent refused')])

    def test_failed_begin_save_names_a_reason_and_a_good_save_clears_it(self):
        self.ok = False
        self.assertFalse(self.owner.Begin('one', 'event', 'site'))
        self.assertEqual('journal_save_failed', self.owner.Refusal())
        self.assertEqual(1, len(self.owner.m_Data.Rows))
        self.ok = True
        self.assertTrue(self.owner.Begin('two', 'event', 'site'))
        self.assertEqual('', self.owner.Refusal())
        self.assertEqual(1, len(lines(self.logs, 'reason=journal_save_failed')))

    def test_prepare_begin_refusals_each_have_a_reason_and_log_once(self):
        self.owner.m_Data.SchemaVersion = 9
        self.assertFalse(self.owner.PrepareBegin('one', 'event', 'site'))
        self.assertEqual('journal_invalid', self.owner.Refusal())
        self.owner.m_Data.SchemaVersion = 1
        self.assertFalse(self.owner.PrepareBegin('', 'event', 'site'))
        self.assertEqual('bad_token', self.owner.Refusal())
        self.assertFalse(self.owner.PrepareBegin('', 'event', 'site'))
        self.assertTrue(self.owner.Begin('one', 'event', 'site'))
        self.assertFalse(self.owner.PrepareBegin('one', 'event', 'site'))
        self.assertEqual('duplicate_id', self.owner.Refusal())
        self.assertTrue(self.owner.Begin('two', 'event', 'site'))
        self.assertFalse(self.owner.PrepareBegin('three', 'event', 'site'))
        self.assertEqual('capacity', self.owner.Refusal())
        self.assertEqual(['journal_invalid', 'bad_token', 'duplicate_id', 'capacity'],
                         [re.search(r'reason=(\w+)', l)[1] for l in lines(self.logs, 'intent refused')])
        self.owner.m_Data.Rows[0].Closed = True
        self.owner.m_Data.Rows[0].Prunable = True
        self.ok = False
        self.assertFalse(self.owner.PrepareBegin('three', 'event', 'site'))
        self.assertEqual('prune_failed', self.owner.Refusal())
        self.assertEqual(2, len(self.owner.m_Data.Rows))

    def test_a_successful_prepare_begin_clears_the_standing_refusal_and_logs_once(self):
        self.owner.m_Data.SchemaVersion = 9
        self.assertFalse(self.owner.PrepareBegin('one', 'event', 'site'))
        self.assertEqual('journal_invalid', self.owner.Refusal())
        self.owner.m_Data.SchemaVersion = 1
        self.assertTrue(self.owner.PrepareBegin('one', 'event', 'site'))
        self.assertEqual('', self.owner.Refusal())
        # The same reason after recovery is a change again and logs again.
        self.owner.m_Data.SchemaVersion = 9
        self.assertFalse(self.owner.PrepareBegin('one', 'event', 'site'))
        self.assertEqual(2, len(lines(self.logs, 'reason=journal_invalid')))


class EncounterStartRefusals(unittest.TestCase):
    def setUp(self):
        self.t = encounter_suite.EncounterTests()
        self.t.setUp()

    def test_unarmed_cap_ids_and_director_refusals_report_a_reason_once(self):
        svc, logs = self.t.svc, self.t.logs
        self.assertFalse(svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 2))
        self.assertEqual('encounters_not_armed', svc.LastRefusal())
        self.assertFalse(svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 2))
        self.assertEqual(1, len(lines(logs, 'reason=encounters_not_armed')))
        self.t.armed()
        self.assertFalse(svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 0))
        self.assertEqual('actor_cap', svc.LastRefusal())
        self.assertFalse(svc.StartEncounter('', 'ev', 'm-5', (0., 0., 0.), 2))
        self.assertEqual('lease_ids_missing', svc.LastRefusal())
        self.t.phase = 'stopped'
        self.assertFalse(svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 2))
        self.assertEqual('director_not_running', svc.LastRefusal())
        self.t.phase = 'run'
        self.assertFalse(svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 2))
        self.assertEqual('no_site', svc.LastRefusal())  # no eligible patrol state
        self.t.states.Insert(self.t.state('near', [(0., 0., 0.)]))
        self.assertTrue(svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 2))
        self.assertEqual('', svc.LastRefusal())


class SiteDirectorAndPatrolRefusals(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.now = [1000]
        self.env = dict(A=A, len=len, str=str, Print=self.logs.append,
                        GetGame=lambda: N(GetTime=lambda: self.now[0]),
                        HCRefusal=HCREFUSAL, vector=N(Distance=math.dist),
                        Vector=lambda *a: a, HCXAISiteDirector=N(Active=lambda: None))
        self.source = (SCRIPTS / 'HCXAISites.c').read_text()
        # Native Substring port: the syntax adapter cannot parse the nested Length().
        self.source = self.source.replace('m_HCSiteId.Substring(10, m_HCSiteId.Length() - 10)',
                                          'synthetic_suffix(m_HCSiteId)')

    def patrol(self, authored, **fields):
        owner = N(m_Group=None, m_Formation=None, m_HCFinished=False, m_HCTransient=False,
                  m_HCSiteId='synthetic-site', m_HCNextBudgetLogMs=0, m_HCPendingMembers=0, **fields)
        owner.HCRefuseBudget = lambda *a: authored.call('HCRefuseBudget', owner, *a)
        return owner

    def test_spawn_without_a_director_logs_why_through_the_site_limiter(self):
        authored = Authored(self.source.replace('super.Spawn();', 'synthetic_spawn(this);'), self.env)
        patrol = self.patrol(authored)
        for _ in range(20):
            authored.call('Spawn', patrol)
        self.assertEqual(['[HC Expansion AI] site synthetic-site spawn refused: sites not running'], self.logs)
        self.now[0] = 61000
        authored.call('Spawn', patrol)
        self.assertEqual(2, len(self.logs))
        self.assertIsNone(patrol.m_Group)

    def test_deferred_member_without_a_group_logs_why_and_creates_nothing(self):
        authored = Authored(self.source.replace('super.SpawnAI_Deferred(i);', 'synthetic_super(i);'), self.env)
        patrol = self.patrol(authored)
        for index in range(1, 4):
            authored.call('SpawnAI_Deferred', patrol, index)
        self.assertEqual(['[HC Expansion AI] site synthetic-site spawn refused: member spawn without a live group'],
                         self.logs)
        self.assertEqual(0, patrol.m_HCPendingMembers)

    def test_admit_transient_reports_each_gate_through_the_out_reason(self):
        # The syntax adapter has no out parameters: the reason is read from a synthetic member.
        source = self.source.replace(', out string reason)', ')')
        source = re.sub(r'\breason\b', 'm_Reason', source)
        env = dict(self.env, HCXAIQualification=N(EncountersEnabled=lambda: True, ProviderProblem=lambda: ''),
                   FileExist=lambda path: True, EXPANSION_LOADOUT_FOLDER='synthetic/',
                   HCXAISite=lambda: N(Waypoints=A()), HCXAISiteState=lambda: N(), eAIFaction=N(Create=lambda n: self.faction))
        env['HCXAIRules'] = api((SCRIPTS / 'HCXAIRules.c').read_text(), env)
        from tests.unit.ai_limits_fixture import install
        install(env, MaxLiveGroups=2, MaxLiveAI=8)
        authored = Authored(source, env)
        self.faction = N(IsInvincible=lambda: False, IsObserver=lambda: False, IsPassive=lambda: False,
                         HasUnlimitedStamina=lambda: False, GetMeleeDamageMultiplier=lambda: 1.,
                         GetMeleeYeetForce=lambda: 0.)
        director = N(m_Phase='run', m_Policy=N(MaxActiveAI=24, MaxActiveSites=8), m_States=A(), m_Reason='untouched')
        director.BudgetProblem = lambda cap, exclude: ''
        director.MemberProblemFor = lambda position: ''
        admit = lambda pid, faction, pos, cap: authored.call('AdmitTransient', director, pid, faction, pos, cap)
        good = (500., 0., 500.)
        director.m_Phase = 'stopped'
        self.assertFalse(admit('p1', 'locals', good, 2))
        self.assertEqual('sites not running', director.m_Reason)
        director.m_Phase = 'run'
        self.assertFalse(admit('', 'locals', good, 2))
        self.assertEqual('invalid transient id or place anchor', director.m_Reason)
        self.assertFalse(admit('p1', 'nobody', good, 2))
        self.assertEqual('unknown transient faction', director.m_Reason)
        self.faction.IsPassive = lambda: True
        self.assertFalse(admit('p1', 'locals', good, 2))
        self.assertEqual('transient faction or loadout unavailable/unfair', director.m_Reason)


class CheckpointPropStartRefusals(unittest.TestCase):
    def setUp(self):
        self.logs = []
        source = (SCRIPTS / 'HCXAISites.c').read_text().split('class HCXCheckpointProps\n', 1)[1]
        source = source.replace('HCXCheckpointProp row', 'HCXAICheckpointProp row')
        self.policy = N(WorldName='chernarusplus', Sites=A())
        self.policy_problem = ''
        self.site_problem = ''
        self.world = 'chernarusplus'
        env = dict(A=A, Print=self.logs.append,
                   GetGame=lambda: N(GetWorldName=lambda: self.world),
                   HCXAISiteDirector=N(LoadPolicy=lambda: self.policy),
                   HCXAISiteRules=N(PolicyProblem=lambda policy: self.policy_problem),
                   HCXAIRules=N(CheckpointProblem=lambda site: self.site_problem),
                   HCBuildIdentity=N(SameWorld=lambda a, b: a.lower() == b.lower()),
                   HCXCheckpointProp=lambda: N())
        self.authored = Authored(source, env)
        self.owner = N(m_Props=A(), m_Cursor=0)
        self.owner.HCStartRefused = lambda *a: self.authored.call('HCStartRefused', self.owner, *a)

    def start(self):
        self.authored.call('Start', self.owner)

    def site(self, name):
        return N(Id=name, Checkpoint=True)

    def test_missing_invalid_or_foreign_policy_logs_why_and_places_nothing(self):
        self.policy.Sites = A([self.site('cp-1')])
        self.policy_problem = 'synthetic policy problem'
        self.start()
        self.assertEqual(['[HollowCountry] Checkpoints props not placed: synthetic policy problem; runtime=PENDING'],
                         self.logs)
        self.policy_problem = ''
        self.world = 'enoch'
        self.start()
        self.assertIn('policy world differs from the running world', self.logs[-1])
        self.assertEqual(0, len(self.owner.m_Props))

    def test_site_problem_and_prop_cap_log_and_keep_the_loaded_rows(self):
        self.policy.Sites = A([self.site('cp-1'), self.site('cp-2')])
        self.site_problem = 'synthetic site problem'
        self.start()
        self.assertEqual(0, len(self.owner.m_Props))
        self.assertIn('cp-1: synthetic site problem', self.logs[-1])
        self.site_problem = ''
        self.owner.m_Props = A([N(), N(), N()])
        self.start()
        self.assertEqual(3, len(self.owner.m_Props))
        self.assertIn('checkpoint prop cap=3 reached at cp-1', self.logs[-1])
        self.assertEqual(2, len(self.logs))


class DefenceStartRefusal(unittest.TestCase):
    def test_second_start_logs_that_it_was_ignored_and_does_not_restart(self):
        logs, started = [], []
        running = [False]
        defence = N(Running=lambda: running[0], Start=lambda: (started.append(1), running.__setitem__(0, True)))
        env = dict(Print=logs.append, GetGame=lambda: N(IsServer=lambda: True),
                   HCXDefence=defence, IsEnabled=lambda settings: True,
                   HCV2Admission=N(Line=lambda *a: 'admission line'))
        source = (SCRIPTS / 'HCXDefence.c').read_text().split('class HCXDefenceModule', 1)[1]
        authored = Authored(source, env)
        authored.call('OnStart', N(), N())
        authored.call('OnStart', N(), N())
        self.assertEqual([1], started)
        self.assertEqual(1, len(lines(logs, 'start ignored: already running')))
        self.assertEqual(1, len(lines(logs, 'admission line')))


if __name__ == '__main__':
    unittest.main()
