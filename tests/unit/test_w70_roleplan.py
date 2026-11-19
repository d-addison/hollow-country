"""W70 #144/#146: synthetic behavioral ports execute authored role policy.
Spec: role/context selects existing providers; plan: bounded cursor and custody
checks; tasks: RED policy, source scheduler, focused checks. No DayZ evidence.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest
import json
import re
from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr
from tests.unit.json_loader_port import json_fields_port

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIRoleActivities.c'


class RolePlan(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text() if SOURCE.exists() else ''
        self.env = dict(EArray=EArray, str=str)
        self.policy = N()
        self.env['HCXAIRolePolicy'] = self.policy
        for name in ('HCMatch', 'HCDue', 'HCWeight', 'HCChoose', 'HCDerive', 'HCNight'):
            # Only syntax scaffolding: decisions are the authored Enforce body.
            text = self.source.replace('HCXAIRoleRule rule =', 'HCEventRule rule =')
            text = text.replace('HCXAIRoleActivity row =', 'HCEventActivity row =')
            setattr(self.policy, name, translate(text, name, self.env, 'HCXAIRolePolicy'))

    def rule(self, role, **kw):
        return N(Role=role, Faction=kw.get('Faction', ''), Kind=kw.get('Kind', ''),
                 Loadout=kw.get('Loadout', ''), Home=kw.get('Home', ''))

    def row(self, role, activity, **kw):
        defaults = dict(Role=role, Activity=activity, Weight=0, NeedWeight=0,
                        DangerWeight=0, InfectedWeight=0, NightWeight=0, SafeOnly=False)
        defaults.update(kw)
        return N(**defaults)

    def test_role_derivation_uses_ordered_config_and_all_identity_fields(self):
        rules = EArray([self.rule('mechanic', Loadout='repair'),
                        self.rule('guard', Home='camp:alpha', Kind='holdout'),
                        self.rule('scavenger', Faction='scavengers'), self.rule('patrol')])
        derive = self.policy.HCDerive
        self.assertEqual('mechanic', derive(rules, 'scavengers', 'holdout', 'repair', 'camp:alpha'))
        self.assertEqual('guard', derive(rules, 'locals', 'holdout', '', 'camp:alpha'))
        self.assertEqual('scavenger', derive(rules, 'scavengers', '', '', ''))
        self.assertEqual('patrol', derive(rules, 'unknown', '', '', ''))

    def test_weighted_choice_reacts_to_need_danger_infected_and_night(self):
        rows = EArray([self.row('scavenger', 'scavenge', NeedWeight=9, SafeOnly=True),
                       self.row('scavenger', 'hold', DangerWeight=7, InfectedWeight=8),
                       self.row('scavenger', 'patrol', NightWeight=5)])
        choose = self.policy.HCChoose
        self.assertEqual('scavenge', choose(rows, 'scavenger', True, False, False, False, 0))
        self.assertEqual('hold', choose(rows, 'scavenger', True, True, False, False, 0))
        self.assertEqual('hold', choose(rows, 'scavenger', True, False, True, False, 0))
        self.assertEqual('patrol', choose(rows, 'scavenger', False, False, False, True, 0))
        self.assertEqual('', choose(rows, 'guard', True, True, True, True, 0))
        weighted = EArray([self.row('guard', 'hold', Weight=2), self.row('guard', 'patrol', Weight=1)])
        self.assertEqual(['hold', 'hold', 'patrol'],
                         [choose(weighted, 'guard', False, False, False, False, x) for x in range(3)])

    def test_night_window_supports_midnight_and_daytime_windows(self):
        night = self.policy.HCNight
        self.assertTrue(night(23, 20, 6))
        self.assertTrue(night(5, 20, 6))
        self.assertFalse(night(12, 20, 6))
        self.assertTrue(night(12, 10, 15))
        self.assertFalse(night(18, 10, 15))
        self.assertFalse(night(12, 6, 6))

    def test_caps_cooldown_budget_and_operator_opt_out(self):
        due = self.policy.HCDue
        self.assertTrue(due(True, True, 20, 20, 0, 2))
        self.assertFalse(due(False, True, 20, 20, 0, 2))
        self.assertFalse(due(True, False, 20, 20, 0, 2))
        self.assertFalse(due(True, True, 19, 20, 0, 2))
        self.assertFalse(due(True, True, 20, 20, 2, 2))
        self.assertFalse(due(True, True, 20, 20, 0, 0))

    def test_table_images_do_not_allow_zero_filled_missing_row_keys(self):
        env = dict(HCJsonFields=json_fields_port(), str=str)
        text = re.sub(r"(\w+)\+\+", r"\1 += 1", self.source)
        text = re.sub(r"(\w+)--", r"\1 -= 1", text)
        extract = translate(text, 'HCArray', env)
        image = EStr(json.dumps(dict(Rules=[dict(Role='guard', Faction='', Kind='', Loadout='', Home='')],
                                    Activities=[dict(Role='guard', Activity='hold', Weight=1)])))
        rules = extract(image, 'Rules')
        activities = extract(image, 'Activities')
        self.assertEqual('guard', json.loads(rules)[0]['Role'])
        self.assertTrue(env['HCJsonFields'].Every(EStr(rules), 'Home', 2))
        self.assertFalse(env['HCJsonFields'].Every(EStr(activities), 'SafeOnly', 2))
        nested = EStr('{"Rules":[{"Role":"guard","nested":{"Home":"fake"}}]}')
        self.assertFalse(env['HCJsonFields'].Every(EStr(extract(nested, 'Rules')), 'Home', 2))
        escaped = EStr(json.dumps(dict(Rules=[dict(Role='quoted ] \" [', Home='camp')], Activities=[])))
        self.assertEqual('camp', json.loads(extract(escaped, 'Rules'))[0]['Home'])

    def test_hold_release_restores_only_owned_behaviour(self):
        text = self.source.replace('Held', 'm_Held').replace('Group.', 'm_Group.').replace('&& Group &&', '&& m_Group &&').replace('Previous', 'm_Previous')
        enum = N(HALT=0, LOOP=1)
        release = translate(text, 'HCRelease', dict(eAIWaypointBehavior=enum), member=True)
        calls = []
        group = N(GetWaypointBehaviour=lambda: enum.HALT, SetWaypointBehaviour=calls.append)
        lease = N(m_Held=True, m_Group=group, m_Previous=enum.LOOP)
        release(lease)
        self.assertEqual([enum.LOOP], calls)
        release(lease)
        self.assertEqual([enum.LOOP], calls)
        group.GetWaypointBehaviour = lambda: 5  # another provider changed it
        lease.m_Held = True
        release(lease)
        self.assertEqual([enum.LOOP], calls)

    def test_trade_offer_cannot_bypass_the_funded_producer_plan(self):
        calls = []
        producer = N(m_Planning=True, m_Travelling=False, m_Returning=False,
                     m_LeftLease='left', m_RightLease='right')
        def plan():
            calls.append('existing-plan')
            producer.m_Travelling = True
        producer.HCPlan = plan
        env = dict(s_Producer=producer)
        text = self.source.replace('HCXAITradeProducer producer =', 'HCEventProducer producer =')
        offer = translate(text, 'HCOffer', env, 'HCXAIRoleTradePort')
        self.assertEqual('TRADE_DIFFERENT_FUNDED_PAIR', offer('other', 'right'))
        self.assertEqual([], calls)
        self.assertEqual('', offer('left', 'right'))
        self.assertEqual(['existing-plan'], calls)
        self.assertEqual('TRADE_FUNDED_PLAN_ABSENT', offer('left', 'right'))
        self.assertEqual(['existing-plan'], calls)

    def test_tick_opt_out_and_budget_refusal_touch_no_group(self):
        text = re.sub(r"([\w.]+)\+\+", r"\1 += 1", self.source)
        text = re.sub(r"([\w.]+)--", r"\1 -= 1", text)
        # Only declaration syntax is adapted; the real tick body executes.
        text = re.sub(r'\b(?:HCXAISiteDirector|HCXAISiteState|eAIGroup|eAIBase|eAITarget|HCAIPartyIdentity|HCAICampRoutineView|HCHoldouts|HCPickers|HCScavengeTrip|HCAITrade|HCTradeState|eAIWaypointBehavior|HCXAIRoleLease|ZombieBase|HCWorldMaterializer|HCDebugProposalRow) (?=\w+)', 'HCEventPort ', text)
        visits = []
        states = EArray([N()])
        director = N(Phase=lambda: 'run', States=lambda: states)
        env = dict(HCXAISiteDirector=N(Active=lambda: visits.append('director') or director),
                   HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda *args: False)),
                   HCUnitBudget=N(HC_WORK_ROLES=13))
        tick = translate(text, 'OnTick', env, 'HCXAIRoleActivities', member=True)
        job = N(m_Running=False, m_Config=N(GroupsPerTick=1), m_Leases=EArray(),
                m_Cursor=0, m_Work=N(HCReset=lambda *args: None, HCContinue=lambda: True))
        tick(job, 1)
        self.assertEqual([], visits)
        job.m_Running = True
        tick(job, 1)
        self.assertEqual(['director'], visits)
        self.assertEqual(0, job.m_Cursor, 'a refused shared budget must retain the cursor')
        # An expired lease must release even after its site state is retired.
        releases = []
        job.m_LeaseCursor = 0
        job.m_Leases = EArray([N(Until=10, Group=None, HCProviderBusy=lambda: False,
                                HCRelease=lambda: releases.append('release'))])
        env['HCWorldClock'] = N(UTC=lambda: 100)
        env['HCServer'].HCTickWork = lambda: N(HCTakeFor=lambda *args: True)
        env['HCXAISiteDirector'].Active = lambda: None
        tick(job, 1)
        self.assertEqual(['release'], releases)
        self.assertEqual([], job.m_Leases)

    def _tick_text(self):
        text = re.sub(r"([\w.]+)\+\+", r"\1 += 1", self.source)
        text = re.sub(r"([\w.]+)--", r"\1 -= 1", text)
        # Dotted member chains (state.Patrol.m_Group) are renamed mm_* so the
        # translator's own-member rule (m_* -> self.m_*) leaves them alone.
        text = re.sub(r'(?<=\.)m_(\w+)', r'mm_\1', text)
        return re.sub(r'\b(?:HCXAISiteDirector|HCXAISiteState|eAIGroup|eAIBase|eAITarget|HCAIPartyIdentity|HCAICampRoutineView|HCHoldouts|HCPickers|HCScavengeTrip|HCAITrade|HCTradeState|eAIWaypointBehavior|HCXAIRoleLease|ZombieBase|HCWorldMaterializer|HCDebugProposalRow) (?=\w+)', 'HCEventPort ', text)

    def test_perceived_incident_preempts_a_new_role_pick(self):
        offers, due = [], []
        group = N(Count=lambda: 2, IsInCombat=lambda: False)
        state = N(Site=N(HousePosition=[1, 0, 1]), Qualified=True, Failed=False, Completed=False,
                  Patrol=N(mm_HCLive=True, mm_Group=group), PatrolPoints=EArray([[5, 0, 5]]),
                  ProposalId='p1', HCW70NextAt=0, HCW70DangerUntil=0)
        states = EArray([state])
        director = N(Phase=lambda: 'run', States=lambda: states)
        def offer(g, home):
            offers.append((g, home))
            return answer[0]
        answer = [True]
        self.policy.HCDue = lambda *args: due.append(args) or False
        env = dict(HCXAISiteDirector=N(Active=lambda: director),
                   HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda *args: True)),
                   HCUnitBudget=N(HC_WORK_ROLES=13), HCWorldClock=N(UTC=lambda: 100),
                   HCXAIRolePolicy=self.policy,
                   HCBaseRaid=N(HCOwns=lambda lease: False), HCPickers=N(Get=lambda: None),
                   HCAITrade=N(HCGet=lambda: None), HCXAIIncidentResponse=N(HCOffer=offer))
        tick = translate(self._tick_text(), 'OnTick', env, 'HCXAIRoleActivities', member=True)
        job = N(m_Running=True, m_Config=N(GroupsPerTick=1, MaxActive=4, DangerMemorySeconds=60),
                m_Leases=EArray(), m_Cursor=0, m_LeaseCursor=0,
                m_Work=N(HCReset=lambda *args: None, HCContinue=lambda: True))
        tick(job, 1)
        self.assertEqual([(group, [5, 0, 5])], offers, 'the incident offer sees the patrol home')
        self.assertEqual([], due, 'a group answering an incident gets no new role pick')
        self.assertEqual([], job.m_Leases)
        answer[0] = False
        tick(job, 1)
        self.assertEqual(2, len(offers))
        self.assertEqual(1, len(due), 'without an incident the normal role cadence runs')

    def test_repair_activity_reaches_the_landed_car_repair_owner(self):
        calls = []
        env = dict(HCXAICarRepair=N(HCOffer=lambda group, home: calls.append(home) or True))
        start = translate(self._tick_text(), 'HCStart', env, 'HCXAIRoleActivities', member=True)
        job = N(m_Config=N(EnableCarRepair=True))
        self.assertEqual('', start(job, None, N(), None, N(), 'repair', [3, 0, 3], 100))
        self.assertEqual([[3, 0, 3]], calls)
        job.m_Config.EnableCarRepair = False
        self.assertEqual('REPAIR_OPERATOR_OFF', start(job, None, N(), None, N(), 'repair', [3, 0, 3], 100))

    def test_existing_providers_and_admission_are_wired_without_new_movement(self):
        for token in ('director.HCParty(', 'HCFactionConflict.HCW70Offer(',
                      'producer.HCPlan(', 'HCBaseRaid.HCOwns(', 'HCXAICarRepair.HCOffer(group, home)',
                      'HCXAIIncidentResponse.HCOffer(group, incidentHome)', 'HCServer.HCTickWork().HCTakeFor(',
                      'HCPerfSlices', 'HCModuleReadiness.HCDerive(', 'HCV2Admission.Line(',
                      'role_activities.disable', 'HCJsonFields.Has('):
            self.assertIn(token, self.source)
        self.assertNotIn('#ifdef HCXAI_CAR_REPAIR', self.source, 'car repair landed in this addon; no dormant define')
        for token in ('SetPosition(', 'OverrideTargetPosition(', 'CreateObject(', 'GetObjectsAtPosition'):
            self.assertNotIn(token, self.source)


if __name__ == '__main__':
    unittest.main()
