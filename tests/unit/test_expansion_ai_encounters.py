"""AI_ENCOUNTER on HC site patrols: authored HCXAIEncounters bodies, synthetic director state.

Every director state, patrol group, player and journal here is an explicit synthetic fixture.
Nothing establishes DayZ behaviour: binding, kill attribution through the native group and
event completion stay pending a local server run with a client.
"""
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_expansion_ai_adapter import A, Authored, declarations
from tests.unit.test_expansion_ai_sites import api, dto

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'
AI = ROOT / 'mission/hollow-country/ai'
# Base HCEventSites.ChernarusPlus (read-only input): the two AI-capable police anchors.
COASTAL = (3569.727783, 13.310547, 2431.353027)
INLAND = (3421.308105, 199.738251, 13019.891602)


class FakeJournal:
    def __init__(self):
        self.calls = []
        self.ok = True

    def PrepareBegin(self, *a):
        self.calls.append(('prepare',) + a)
        return self.ok

    def Begin(self, *a):
        self.calls.append(('begin',) + a)
        return self.ok

    def End(self, *a):
        self.calls.append(('end',) + a)
        return self.ok


class EncounterTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.phase = 'run'
        self.owned_session = 7
        self.world = 'ChernarusPlus'
        self.journal = FakeJournal()
        self.opened = []
        self.states = A()
        self.env = dict(A=A, Print=self.logs.append)
        declarations(self.env)
        self.env['vector'] = N(Distance=lambda a, b: math.dist(a, b), Zero=(0., 0., 0.))
        self.env['Math'] = N(AbsFloat=abs)
        self.env['HCXAIRules'] = api((SCRIPTS / 'HCXAIRules.c').read_text(), self.env)
        self.env['HCXAISiteRules'] = api((SCRIPTS / 'HCXAISiteRules.c').read_text(), self.env)
        self.director = N(Phase=lambda: self.phase, OwnedSession=lambda: self.owned_session,
                          States=lambda: self.states)
        self.env['HCXAISiteDirector'] = N(Active=lambda: self.director)
        self.env['HCXAIJournal'] = N(Open=self.open_journal)
        self.env['ExpansionStatic'] = N(GetTimestamp=lambda utc=False: 1763400000 if utc else -1)
        self.env['HCBuildIdentity'] = N(SameWorld=lambda a, b: a != '' and a.lower() == b.lower())
        self.env['GetGame'] = lambda: N(IsServer=lambda: True, GetWorldName=lambda: self.world)
        self.env['HCEventObjectiveEvidence'] = lambda: N(Observed=False, Lease='', Session='',
                                                         ParticipantId='', Sequence=0, Token='')
        self.env['HCXAIEncounters'] = N(MAX_OPEN=8, MAX_KILLS=16)
        self.source = (SCRIPTS / 'HCXAIEncounters.c').read_text()
        self.code = Authored(self.source, self.env)
        self.svc = N(m_Journal=None, m_Bindings=A(), m_Token='', m_State='waiting for sites',
                     m_Armed=False, m_Settled=False)
        for name in re.findall(r'\n    (?:protected |static |override )*[\w<>]+ (\w+)\([^)]*\)\s*\{', self.source):
            setattr(self.svc, name, lambda *a, n=name: self.code.call(n, self.svc, *a))

    def open_journal(self, token, limit, reconciled=False):
        self.opened.append((token, limit, reconciled))
        return self.journal

    def state(self, site_id, points, radius=650., qualified=True, patrol=True):
        group = N(name='HC:' + site_id)
        return N(Site=N(Id=site_id, ActivationRadius=radius), Qualified=qualified,
                 PatrolPoints=A(points), Patrol=N(m_Group=group) if patrol else None)

    def player(self, pid='p1', alive=True):
        return N(IsAlive=lambda: alive, GetIdentity=lambda: N(GetId=lambda: pid))

    def armed(self):
        self.svc.Step()
        self.assertTrue(self.svc.Armed())

    def test_arms_once_with_a_per_process_token_after_sites_run(self):
        self.phase = 'qualify'
        self.svc.Step()
        self.assertFalse(self.svc.Armed())
        self.assertFalse(self.svc.Settled())
        self.assertEqual([], self.opened)
        self.phase = 'run'
        self.svc.Step(); self.svc.Step()
        self.assertTrue(self.svc.Armed())
        self.assertEqual([('xai-7-1763400000', 64, True)], self.opened)
        self.assertEqual('xai-7-1763400000', self.svc.m_Token)
        armed = [l for l in self.logs if 'encounters armed' in l]
        self.assertEqual(1, len(armed), self.logs)
        self.assertIn('session=xai-7-1763400000', armed[0])
        self.assertIn('no actors are spawned', armed[0])

    def test_sites_off_refused_or_unreconciled_never_arm(self):
        for phase, session in (('off', 7), ('refused', 7), ('stopped', 7), ('run', 0)):
            self.setUp()
            self.phase, self.owned_session = phase, session
            self.svc.Step(); self.svc.Step()
            self.assertFalse(self.svc.Armed(), phase)
            self.assertTrue(self.svc.Settled(), phase)
            self.assertFalse(self.svc.Ready('chernarusplus'))
            self.assertEqual(1, len([l for l in self.logs if 'encounters not armed' in l]), self.logs)

    def test_journal_refusal_leaves_encounters_unready(self):
        self.journal = None
        self.svc.Step()
        self.assertFalse(self.svc.Armed())
        self.assertTrue(self.svc.Settled())
        self.assertIn('journal', self.svc.State())

    def test_ready_needs_the_world_and_a_qualified_owned_patrol(self):
        self.armed()
        self.assertFalse(self.svc.Ready('chernarusplus'))
        self.states.Insert(self.state('police-x', [(0., 0., 0.)], patrol=False))
        self.states.Insert(self.state('police-y', [(0., 0., 0.)], qualified=False))
        self.assertFalse(self.svc.Ready('chernarusplus'))
        self.states.Insert(self.state('police-z', [(0., 0., 0.)]))
        self.assertTrue(self.svc.Ready('chernarusplus'))
        self.assertFalse(self.svc.Ready('enoch'))
        self.assertFalse(self.svc.Ready(''))
        self.phase = 'stopped'
        self.assertFalse(self.svc.Ready('chernarusplus'))

    def test_start_binds_the_nearest_eligible_patrol_and_journals_the_intent(self):
        self.armed()
        anchor = (1000., 0., 1000.)
        self.states.Insert(self.state('near-unqualified', [(1010., 0., 1000.)], qualified=False))
        self.states.Insert(self.state('far', [(1600., 0., 1000.)]))
        self.states.Insert(self.state('near', [(5000., 0., 5000.), (1300., 0., 1000.)]))
        self.assertTrue(self.svc.StartEncounter('ev:1', 'ev', 'coastal-police-source-5', anchor, 2))
        binding = self.svc.FindEncounter('ev:1')
        self.assertEqual(('near', 'ev', 'coastal-police-source-5'), (binding.SiteId, binding.Session, binding.MissionId))
        self.assertEqual([('prepare', 'ev:1', 'ev', 'coastal-police-source-5'),
                          ('begin', 'ev:1', 'ev', 'coastal-police-source-5')], self.journal.calls)
        bound = [l for l in self.logs if 'encounter bound' in l]
        self.assertEqual(1, len(bound), self.logs)
        for part in ('lease=ev:1', 'mission=coastal-police-source-5', 'site=near', 'gap=300'):
            self.assertIn(part, bound[0])
        # Idempotent for the same identity; a different identity or reuse is refused.
        self.assertTrue(self.svc.StartEncounter('ev:1', 'ev', 'coastal-police-source-5', anchor, 2))
        self.assertFalse(self.svc.StartEncounter('ev:1', 'other', 'coastal-police-source-5', anchor, 2))
        self.assertEqual(1, len([c for c in self.journal.calls if c[0] == 'begin']))
        # One open encounter per site: the next anchor takes the next eligible patrol.
        self.assertTrue(self.svc.StartEncounter('ev:2', 'ev', 'inland-police-source-5', anchor, 2))
        self.assertEqual('far', self.svc.FindEncounter('ev:2').SiteId)
        self.assertFalse(self.svc.StartEncounter('ev:3', 'ev', 'third-5', anchor, 2))

    def test_start_refuses_bad_input_unarmed_state_and_journal_refusal(self):
        self.states.Insert(self.state('near', [(0., 0., 0.)]))
        self.assertFalse(self.svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 2))  # not armed
        self.armed()
        self.assertFalse(self.svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 0))
        self.assertFalse(self.svc.StartEncounter('', 'ev', 'm-5', (0., 0., 0.), 2))
        self.journal.ok = False
        self.assertFalse(self.svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 2))
        self.assertIsNone(self.svc.FindEncounter('ev:1'))
        self.assertTrue(any('encounter refused' in l and 'journal' in l for l in self.logs), self.logs)

    def test_open_encounters_are_bounded(self):
        self.armed()
        for index in range(10):
            self.states.Insert(self.state('s' + str(index), [(float(index), 0., 0.)]))
        results = [self.svc.StartEncounter('ev:' + str(i), 'ev', 'm' + str(i) + '-5', (0., 0., 0.), 2)
                   for i in range(10)]
        self.assertEqual([True] * 8 + [False] * 2, results)
        self.assertFalse(self.svc.Ready('chernarusplus'))
        self.assertTrue(self.svc.StopEncounter('ev:0'))
        self.assertTrue(self.svc.Ready('chernarusplus'))

    def test_shipped_routes_bind_each_police_anchor_to_its_village_patrol(self):
        # CONTENT on shipped sites.json authored waypoints (not qualified navmesh
        # points). The first encounter work found no route within reach of either
        # police event site (nearest scav-chernogorsk and mil-tisy); the village
        # patrols police-komarovo and police-novaya-petrovka now close that gap.
        # The native "site <id> route qualified" line remains the evidence.
        sites = dto(self.env, 'HCXAISitePolicy', json.loads((AI / 'sites.json').read_text())).Sites
        for site in sites:
            if len(site.Waypoints) > 0:
                self.states.Insert(N(Site=site, Qualified=True, PatrolPoints=A(site.Waypoints),
                                     Patrol=N(m_Group=N())))
        self.armed()
        self.assertTrue(self.svc.Ready('chernarusplus'))
        self.assertTrue(self.svc.StartEncounter('ev:1', 'ev', 'coastal-police-source-5', COASTAL, 2))
        self.assertTrue(self.svc.StartEncounter('ev:2', 'ev', 'inland-police-source-5', INLAND, 2))
        bound = [l for l in self.logs if 'encounter bound' in l]
        self.assertEqual(2, len(bound), self.logs)
        self.assertIn('site=police-komarovo', bound[0])
        self.assertIn('site=police-novaya-petrovka', bound[1])
        self.assertEqual([], [l for l in self.logs if 'encounter refused' in l])

    def test_a_kill_by_the_participant_on_the_bound_patrol_completes_once(self):
        self.armed()
        bound = self.state('near', [(0., 0., 0.)])
        other = self.state('other', [(5000., 0., 0.)])
        self.states.Insert(bound); self.states.Insert(other)
        self.svc.RecordKill(bound.Patrol.m_Group, 'p1')  # before any binding: not counted
        self.assertTrue(self.svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 2))
        self.assertIsNone(self.svc.ObserveEncounter('ev:1', self.player('p1')))
        self.svc.RecordKill(other.Patrol.m_Group, 'p1')
        self.svc.RecordKill(None, 'p1')
        self.svc.RecordKill(bound.Patrol.m_Group, '')
        self.assertIsNone(self.svc.ObserveEncounter('ev:1', self.player('p1')))
        self.svc.RecordKill(bound.Patrol.m_Group, 'p1')
        self.assertTrue(any('encounter kill observed' in l and 'lease=ev:1' in l for l in self.logs), self.logs)
        self.assertIsNone(self.svc.ObserveEncounter('ev:1', self.player('p2')))
        self.assertIsNone(self.svc.ObserveEncounter('ev:1', self.player('p1', alive=False)))
        self.assertIsNone(self.svc.ObserveEncounter('ev:1', None))
        self.assertIsNone(self.svc.ObserveEncounter('ev:2', self.player('p1')))
        evidence = self.svc.ObserveEncounter('ev:1', self.player('p1'))
        self.assertEqual((True, 'ev:1', 'ev', 'p1', 1, 'ev:1:kill:0'),
                         (evidence.Observed, evidence.Lease, evidence.Session, evidence.ParticipantId,
                          evidence.Sequence, evidence.Token))
        # The receipt stays with the first observed participant.
        self.svc.RecordKill(bound.Patrol.m_Group, 'p2')
        self.assertIsNone(self.svc.ObserveEncounter('ev:1', self.player('p2')))
        again = self.svc.ObserveEncounter('ev:1', self.player('p1'))
        self.assertEqual(('ev:1:kill:0', 1), (again.Token, again.Sequence))

    def test_kills_per_encounter_are_bounded(self):
        self.armed()
        bound = self.state('near', [(0., 0., 0.)])
        self.states.Insert(bound)
        self.assertTrue(self.svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 2))
        for _ in range(20):
            self.svc.RecordKill(bound.Patrol.m_Group, 'p1')
        self.assertEqual(16, self.svc.FindEncounter('ev:1').Kills.Count())

    def test_stop_releases_and_ends_the_journal_row_prunable_and_gone_retries(self):
        self.armed()
        bound = self.state('near', [(0., 0., 0.)])
        self.states.Insert(bound)
        self.assertFalse(self.svc.StopEncounter('unknown'))
        self.assertTrue(self.svc.GoneEncounter('unknown'))  # nothing was ever owned
        self.assertTrue(self.svc.StartEncounter('ev:1', 'ev', 'm-5', (0., 0., 0.), 2))
        self.svc.RecordKill(bound.Patrol.m_Group, 'p1')
        self.journal.ok = False
        self.assertTrue(self.svc.StopEncounter('ev:1'))
        self.assertIsNone(self.svc.ObserveEncounter('ev:1', self.player('p1')))
        self.assertFalse(self.svc.GoneEncounter('ev:1'))
        self.journal.ok = True
        self.assertTrue(self.svc.GoneEncounter('ev:1'))
        self.assertTrue(self.svc.GoneEncounter('ev:1'))
        self.assertIn(('end', 'ev:1', True), self.journal.calls)
        # A released encounter frees its site for a later mission.
        self.assertTrue(self.svc.StartEncounter('ev:2', 'ev', 'm2-5', (0., 0., 0.), 2))
        self.assertEqual('near', self.svc.FindEncounter('ev:2').SiteId)


class EncounterSourceTests(unittest.TestCase):
    def code(self, text):
        text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
        return re.sub(r'//[^\n]*', '', text)

    def setUp(self):
        self.adapter = self.code((SCRIPTS / 'HCXAIAdapter.c').read_text())

    def body(self, start):
        from tests.unit.test_expansion_ai_adapter import block
        found = re.search(re.escape(start) + r'[^{]*\{', self.adapter)
        self.assertIsNotNone(found, start)
        return block(self.adapter, found.end())

    def test_provider_delegates_to_encounters_not_the_retired_lease_spawner(self):
        provider = self.body('class HCExpansionAIEventProvider extends HCEventAIProvider')
        for call in ('StartEncounter(', 'ObserveEncounter(', 'StopEncounter(', 'GoneEncounter(', '.Ready(world)'):
            self.assertIn(call, provider)
        self.assertEqual(5, provider.count('HCXAIEncounters.Active()'))
        for retired in ('StartLease', 'ObserveLease', 'StopLease', 'HCXAIService.Adapter()'):
            self.assertNotIn(retired, provider)

    def test_start_arms_encounters_without_the_receipt_profile_or_local_hooks(self):
        start = self.body('override void OnStart(HCSettings settings)')
        for retired in ('InstallLocalHooks', 'HCXAIStore.Load()', 'this.Install('):
            self.assertNotIn(retired, start)
        self.assertIn('new HCXAIEncounters()', start)
        tick = self.body('override void OnTick(float deltaTime)')
        self.assertIn('m_Encounters.Step()', tick)
        stop = self.body('override void OnStop()')
        self.assertIn('m_Encounters.Close()', stop)

    def test_kills_reach_encounters_through_the_native_group_during_eekilled(self):
        killed = self.body('override void EEKilled(Object killer)')
        self.assertLess(killed.index('super.EEKilled(killer)'), killed.index('RecordKill(this.GetGroup()'))
