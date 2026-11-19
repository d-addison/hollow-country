"""#146/#198 spec-plan-task: bounded ledger conflict; synthetic ports, not DayZ.
Plan: authored hostility -> shared holdings -> offscreen transfer or live offer;
pressure reads the existing infected owner; observed outcomes use the ledger/save owner.
Actual RED: python3 -B -m unittest tests.unit.test_w37_conflict -v
AssertionError: Missing authored class: HCConflictPolicy (FAILED, failures=2).
GREEN: python3 -B -m unittest tests.unit.test_w37_conflict -v (8 tests, OK).
The focused reader + shared-brief suite ran 78 tests, OK; runtime=PENDING.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest
import re
from tests.unit.test_map_layers import translate
from tests.unit.test_group_server import EArray
from tests.unit.test_event_runtime import translate as execute
from tests.unit.test_hc_module_readiness_wave16 import FakeStatus, derive

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/World'

class W37Conflict(unittest.TestCase):
    def policy(self):
        env = {'HCWorldLimits': N(TERRITORY=64)}
        translate((WORLD/'HCTerritoryOutcomes.c').read_text(), 'HCConflictPolicy', env)
        return N(**env)

    def test_hostility_holdings_and_finite_transfer(self):
        p = self.policy()
        left = N(Id='locals', Strength=4, Hostile=EArray(['raiders']), Territory=EArray(['1:1']))
        right = N(Id='raiders', Strength=2, Hostile=EArray(['locals']), Territory=EArray(['1:1']))
        self.assertTrue(p.HCOpposed(left, right, '1:1'))
        self.assertFalse(p.HCOpposed(left, right, '2:2'))
        right.Hostile.Clear()
        self.assertFalse(p.HCOpposed(left, right, '1:1'))
        right.Hostile.Insert('locals')
        self.assertEqual('locals', p.HCWinner(left, right))
        right.Strength = 4
        self.assertEqual('', p.HCWinner(left, right), 'ties do not invent victory')
        self.assertTrue(p.HCTransfer(left, right, '1:1'))
        self.assertEqual([], right.Territory)
        self.assertEqual(['1:1'], left.Territory)
        self.assertFalse(p.HCTransfer(left, right, '1:1'), 'retry cannot duplicate a holding')
        self.assertEqual((4, 4), (left.Strength, right.Strength), 'no fictional body deaths')

    def test_behavioral_readiness_sequence(self):
        source = (WORLD/'HCFactionConflict.c').read_text()
        fn = execute(source.replace('HCOperationalStatus', 'HCEventOperationalStatus'), 'HCGetOperationalStatus', {}, None, True)
        status = FakeStatus()
        owner = N(m_Operational=status, m_Healthy=False, m_Refusal='', m_StatusReason='starting')
        fn.__globals__.update(HCModuleReadiness=N(HCDerive=derive()), HCWorldModule=N(Get=lambda:True), s_Active=False)
        fn(owner)
        self.assertEqual('off', status.state)
        owner.m_Healthy = True
        fn.__globals__['s_Active'] = True
        owner.m_StatusReason = 'ledger_loaded_provider_absent'
        fn(owner)
        self.assertEqual(('ready', 'ledger_loaded_provider_absent'), (status.state, status.reason))
        owner.m_Healthy = False
        owner.m_Refusal = 'OUTCOME_STORE_UNCERTAIN'
        fn(owner)
        self.assertEqual(('refused', 'OUTCOME_STORE_UNCERTAIN'), (status.state, status.reason))
        owner.m_Refusal = ''
        fn.__globals__['s_Active'] = False
        fn(owner)
        self.assertEqual('off', status.state)


class W37WorldBehavior(unittest.TestCase):
    def fixture(self):
        from tests.unit.test_hc_faction_outcomes import syntax
        policy = W37Conflict().policy()
        source = (WORLD/'HCFactionConflict.c').read_text().replace('protected ', '')
        source = re.sub(r"array<[^;=]+> (?=\w+ =)", "HCArray ", syntax(source))
        source = source.replace('modded class HCWorldModule\n{', 'modded class HCWorldModule\n{\n    bool m_Running;\n    HCWorldData m_Data;\n    HCStore m_Store;\n    bool m_Dirty;\n    bool AddFact(string kind, string place, int severity) { return false; }\n    bool HCFlushRoutine() { return false; }')
        calls, lines, players, clock = [], [], EArray(), [100]
        a = N(Id='locals', Strength=4, Hostile=EArray(['raiders']), Territory=EArray(['0:0']))
        b = N(Id='raiders', Strength=2, Hostile=EArray(['locals']), Territory=EArray(['0:0']))
        place = N(Id='synthetic-place', Position=[10,0,10], Name='Synthetic')
        data = N(Meta=N(Epoch=1), Places=EArray([place]), Factions=EArray([a,b]),
                 Facts=EArray(), Holdouts=EArray())
        data.Place = lambda key: place
        data.Faction = lambda key: a if key == a.Id else b
        cfg = N(Enabled=True, FarMeters=1500, MaxPlayers=64, CooldownSeconds=86400,
                MaxDailyOutcomes=2, ResolveEqualStrength=True, PressureMeters=120)
        env = dict(HCWorldLimits=N(TERRITORY=64, Position=lambda p: all(v >= 0 for v in p)),
                   HCConflictPolicy=policy, HCPerfPlayers=N(HCGet=lambda: players),
                   vector=N(DistanceSq=lambda a,b: sum((x-y)**2 for x,y in zip(a,b))),
                   HCWorldClock=N(UTC=lambda: clock[0], Day=lambda d,t: t//86400),
                   HCRecoveryGate=N(HCReady=lambda store: True),
                   HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda consumer,n: True)),
                   HCConflictConfig=N(WORK_CONSUMER=6),
                   HCWorldMaterializer=N(HCDebugGet=lambda: None),
                   HCFactionConflict=N(Cell=lambda p:'0:0', HCReserveDataOutcome=lambda *a:True),
                   HCInfectedModule=N(Instance=None),
                   GetGame=lambda: N(GetTime=lambda: clock[0]), Print=lines.append, str=str)
        translate(source, 'HCWorldModule', env, only=('HCConflictStep','HCConflictFar',
                  'HCConflictBudget','HCConflictLeased','HCConflictPublish',
                  'HCConflictPressure','HCConflictObserved'))
        owner = N(m_Running=True, m_Data=data, m_Dirty=False, m_ConflictPlace=0,
                  m_ConflictLeft=0, m_ConflictRight=1, m_ConflictFrame=-1, m_Store=N(SaveInFlight=lambda:False))
        for name in ('HCConflictStep','HCConflictFar','HCConflictBudget','HCConflictLeased',
                     'HCConflictPublish','HCConflictPressure','HCConflictObserved'):
            setattr(owner, name, lambda *args,n=name: env[n](owner,*args))
        def fact(kind, place, severity):
            calls.append((kind,place,severity))
            data.Facts.Insert(N(Kind=kind,PlaceId=place,At=clock[0],Expires=clock[0]+604800))
            return True
        owner.AddFact = fact
        owner.HCFlushRoutine = lambda: True
        return owner,cfg,a,b,players,calls,lines,clock,env

    def test_far_outcome_is_capped_and_replay_is_quiet(self):
        owner,cfg,a,b,players,calls,lines,clock,env = self.fixture()
        owner.HCConflictStep(cfg,None)
        self.assertEqual([], b.Territory)
        self.assertEqual((4,2),(a.Strength,b.Strength))
        self.assertEqual(['faction_clash','locals_pushed_raiders'],[c[0] for c in calls])
        self.assertTrue(owner.m_Dirty)
        self.assertIn('bodies=0 loot=0 runtime=PENDING',lines[-1])
        b.Territory.Insert('0:0')
        clock[0] += 10
        owner.HCConflictStep(cfg,None)
        self.assertEqual(2,len(calls),'persisted fact prevents another outcome during cooldown')
        cfg.Enabled=False
        clock[0] += 86400
        owner.HCConflictStep(cfg,None)
        self.assertEqual(2,len(calls))

    def test_near_player_gets_real_provider_offer_without_ledger_roll(self):
        owner,cfg,a,b,players,calls,lines,clock,env = self.fixture()
        offers=[]
        port=N(HCOffer=lambda *a: offers.append(a), HCActiveAt=lambda place:False)
        players.Insert(N(GetIdentity=lambda: True, GetPosition=lambda:[10,0,10]))
        owner.HCConflictStep(cfg,port)
        self.assertEqual([('synthetic-place','locals','raiders')],offers)
        self.assertEqual([],calls)
        self.assertEqual(['0:0'],b.Territory)
        players.Clear()
        players.extend([N() for _ in range(65)])
        clock[0] += 1
        owner.HCConflictStep(cfg,None)
        self.assertEqual([],calls,'over-cap viewers never become an offscreen verdict')

    def test_claimed_lease_prevents_far_roll_and_observed_result_waits_for_all_viewers(self):
        owner,cfg,a,b,players,calls,lines,clock,env = self.fixture()
        owner.HCConflictLeased=lambda place:True
        owner.HCConflictStep(cfg,None)
        self.assertEqual([],calls)
        row=N(PlaceId='synthetic-place',LeftFaction='locals',RightFaction='raiders',State='LEFT_REMAINS')
        players.Insert(N(GetIdentity=lambda:True,GetPosition=lambda:[10,0,10]))
        self.assertFalse(owner.HCConflictObserved(row,cfg))
        self.assertEqual(['0:0'],b.Territory)
        players.Clear()
        self.assertTrue(owner.HCConflictObserved(row,cfg))
        self.assertTrue(owner.HCConflictObserved(row,cfg))
        self.assertEqual([],b.Territory)
        self.assertEqual(1,len(calls),'idempotent transfer does not repeat chatter')

    def test_pressure_uses_real_infected_owner_without_simulated_casualties(self):
        owner,cfg,a,b,players,calls,lines,clock,env = self.fixture()
        camp=N(PlaceId='synthetic-place',FactionId='locals',Occupants=2)
        owner.m_Data.Holdouts.Insert(camp)
        env['HCInfectedModule'].Instance=N(HCConflictPressureAt=lambda *a:3)
        owner.HCConflictPressure(owner.m_Data.Places[0],'0:0',clock[0],cfg)
        self.assertEqual(2,camp.Occupants)
        self.assertIn('outcome=camp_holds',lines[-1])
        camp.Occupants=0
        owner.HCConflictPressure(owner.m_Data.Places[0],'0:0',clock[0],cfg)
        self.assertEqual([],a.Territory)
        self.assertIn('empty_camp_claim_falls',lines[-1])

class W37DurableQuota(unittest.TestCase):
    def test_restart_clock_rollback_daily_cap_and_cooldown(self):
        from copy import deepcopy
        import math
        source=(WORLD/'HCTerritoryOutcomes.c').read_text()
        source=re.sub(r'array<[^;=]+> (?=\w+ =)', 'HCArray ', source)
        env=dict(HCWorldLimits=N(DAY=86400,PLACES=64,Token=lambda key:bool(key)),
                 HCConflictPlaceStamp=N,Math=N(Floor=math.floor))
        translate(source,'HCConflictQuota',env,only=('HCReserve',))
        reserve=env['HCReserve']
        cfg=N(Enabled=True,MaxDailyOutcomes=2,CooldownSeconds=86400)
        data=N(Day=-1,Count=0,Rows=EArray())
        self.assertTrue(reserve(data,cfg,'synthetic:a',100))
        self.assertFalse(reserve(data,cfg,'synthetic:a',101))
        self.assertTrue(reserve(data,cfg,'synthetic:b',102))
        restored=deepcopy(data)  # Explicit synthetic persisted quota, no world fact dependency.
        self.assertFalse(reserve(restored,cfg,'synthetic:c',103))
        self.assertFalse(reserve(restored,cfg,'synthetic:c',99))
        self.assertTrue(reserve(restored,cfg,'synthetic:a',86501))
        self.assertEqual(1,restored.Count)
        self.assertFalse(reserve(restored,cfg,'synthetic:c',100))

class W37CombatCompletion(unittest.TestCase):
    def test_unengaged_groups_cannot_finish_before_fighting(self):
        from tests.unit.test_hc_faction_outcomes import syntax
        source=(ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXFactionCombatAdapter.c').read_text()
        env={}
        translate(syntax(source).replace('protected ','').replace('override ','').replace('eAIGroup group', 'HCGroup group').replace('ref array<eAIGroup> m_Groups', 'HCArray m_Groups'),'HCXFactionCombatAdapter',env,only=('HCDisengaged',))
        combat=[False]
        deaths=[0]
        group=N(IsInCombat=lambda:combat[0],DeceasedCount=lambda:deaths[0])
        owner=N(m_Groups=EArray([group]),m_SeenCombat=False)
        finish=lambda:env['HCDisengaged'](owner,'synthetic:encounter')
        self.assertFalse(finish())
        combat[0]=True
        self.assertFalse(finish())
        combat[0]=False
        self.assertTrue(finish())
        owner.m_SeenCombat=False
        deaths[0]=1
        self.assertTrue(finish(),'a recorded real death also establishes a fight')

if __name__ == '__main__': unittest.main()
