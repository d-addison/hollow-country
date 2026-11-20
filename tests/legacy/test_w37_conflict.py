"""#146/#198 spec-plan-task: bounded ledger conflict; synthetic ports, not DayZ.
Plan: authored hostility -> shared holdings -> offscreen transfer or live offer;
pressure reads the existing infected owner; observed outcomes use the ledger/save owner.
Actual RED: python3 -B -m unittest tests.legacy.test_w37_conflict -v
AssertionError: Missing authored class: HCConflictPolicy (FAILED, failures=2).
GREEN: python3 -B -m unittest tests.legacy.test_w37_conflict -v (8 tests, OK).
The focused reader + shared-brief suite ran 78 tests, OK; runtime=PENDING.

Round 2 spec/plan/tasks (#146/#198, inputs/task.md + inputs/round2.md):
- Rotate one journal retry per tick; block pending sites, continue unrelated sites.
- Capture group deceased-count baselines on bind; require this encounter's evidence.
- Register conflict debug contributor through the snapshot owner's lifecycle.
RED: python3 -B -m unittest tests.legacy.test_w37_conflict -v
Actual: ('faction_clash', 'synthetic-b', 1) not found in [] :
        a player parked at A must not stall outcomes at B
Actual: True is not false : a pre-existing casualty cannot finish this encounter
Actual: 1 != 0 (missing conflict debug registration).
GREEN command/result retained in .banso-writer/commit-message and round2 report.
Fixtures execute authored handlers against explicit synthetic ports, never DayZ.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest
import re
from tests.legacy.test_map_layers import translate
from tests.legacy.test_group_server import EArray
from tests.legacy.test_event_runtime import translate as execute
from tests.legacy.test_hc_module_readiness_wave16 import FakeStatus, derive

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
        from tests.legacy.test_hc_faction_outcomes import syntax
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
                   HCUnitBudget=N(HC_WORK_CONFLICT=9),
                   HCWorldMaterializer=N(HCDebugGet=lambda: None),
                   HCFactionConflict=N(Cell=lambda p:'0:0', HCReserveDataOutcome=lambda *a:True,
                                       HCTerritoryPending=lambda place:False),
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

    def test_pending_site_receipt_rotates_without_stalling_other_sites(self):
        # Explicit synthetic battlefield A, distant B, player parked at A.
        from tests.legacy.test_hc_faction_outcomes import syntax
        owner,cfg,a,b,players,calls,lines,clock,env = self.fixture()
        site_a = owner.m_Data.Places[0]
        site_b = N(Id='synthetic-b', Position=[5010,0,10], Name='Synthetic B')
        owner.m_Data.Places.Insert(site_b)
        owner.m_Data.Place = lambda key: site_a if key == site_a.Id else site_b
        env['HCFactionConflict'].Cell = lambda pos: '0:0' if pos[0] < 1000 else '5:0'
        a.Territory.Insert('5:0')
        b.Territory.Insert('5:0')
        receipt = N(PlaceId=site_a.Id, LeftFaction='locals', RightFaction='raiders',
                    State='LEFT_REMAINS', TerritoryEpoch=90, TerritoryApplied=False, LeftSurvivors=1)
        history = N(PlaceId='synthetic-history', TerritoryEpoch=0,
                    TerritoryApplied=False, LeftSurvivors=-1)
        source = syntax((WORLD/'HCFactionConflict.c').read_text()).replace('protected ', '')
        source = re.sub(r'array<[^;=]+> (?=\w+ =)', 'HCArray ', source)
        replay_env = dict(HCWorldModule=N(Get=lambda:owner), HCWorldClock=env['HCWorldClock'])
        translate(source, 'HCFactionConflict', replay_env, only=('HCServiceWorld','HCTerritoryPending'))
        saves, retries, offers = [], [], []
        observed = owner.HCConflictObserved
        owner.HCConflictObserved = lambda row,config: retries.append(row.PlaceId) or observed(row,config)
        module = N(m_ConflictConfig=cfg, m_Outcomes=N(Rows=EArray([receipt,history])),
                   m_OutcomeCursor=0, m_Current=None, s_CombatPort=N(
                       HCOffer=lambda *args:offers.append(args), HCActiveAt=lambda key:False),
                   HCDecline=lines.append, HCSave=lambda:saves.append(True) or True)
        replay_env['s_Instance'] = module
        replay_env['s_CombatPort'] = module.s_CombatPort
        env['HCFactionConflict'].HCTerritoryPending = replay_env['HCTerritoryPending']
        players.Insert(N(GetIdentity=lambda:True, GetPosition=lambda:site_a.Position))
        service = lambda: replay_env['HCServiceWorld'](module)
        for _ in range(6):
            service()
            clock[0] += 1
        self.assertIn(('faction_clash',site_b.Id,1), calls,
                      'a player parked at A must not stall outcomes at B')
        self.assertFalse(receipt.TerritoryApplied)
        self.assertIn('0:0', b.Territory)
        self.assertEqual([], offers, 'pending A must not offer a new fight')
        self.assertEqual([site_a.Id]*3, retries, 'one receipt per tick, rotating over history')
        players.Clear()
        for _ in range(4):
            service()
            clock[0] += 1
        self.assertTrue(receipt.TerritoryApplied, 'A retries after the player leaves')
        self.assertNotIn('0:0', b.Territory)
        self.assertEqual([True], saves)
        self.assertEqual(1, sum(kind == 'locals_pushed_raiders' and site == site_a.Id
                                for kind,site,_ in calls), 'receipt publication stays idempotent')

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
        from tests.legacy.test_hc_faction_outcomes import syntax
        source=(ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXFactionCombatAdapter.c').read_text()
        env={}
        translate(syntax(source).replace('protected ','').replace('override ','').replace('eAIGroup group', 'HCGroup group').replace('ref array<eAIGroup> m_Groups', 'HCArray m_Groups').replace('ref array<int> m_InitialDeceased', 'HCArray m_InitialDeceased'),'HCXFactionCombatAdapter',env,only=('HCDisengaged',))
        combat=[False]
        deaths=[0]
        group=N(IsInCombat=lambda:combat[0],DeceasedCount=lambda:deaths[0])
        owner=N(m_Groups=EArray([group]),m_InitialDeceased=EArray([0]),m_SeenCombat=False)
        finish=lambda:env['HCDisengaged'](owner,'synthetic:encounter')
        self.assertFalse(finish())
        combat[0]=True
        self.assertFalse(finish())
        combat[0]=False
        self.assertTrue(finish())
        owner.m_SeenCombat=False
        deaths[0]=1
        self.assertTrue(finish(),'a recorded real death also establishes a fight')

    def test_preexisting_casualty_is_not_current_encounter_combat(self):
        from tests.legacy.test_hc_faction_outcomes import syntax
        source=(ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXFactionCombatAdapter.c').read_text()
        source=syntax(source).replace('protected ','').replace('override ','')
        source=source.replace('eAIGroup group', 'HCGroup group').replace('eAIBase body', 'HCBody body')
        source=re.sub(r'array<[^;=]+> (?=\w+)', 'HCArray ', source)
        env=dict(eAIBase=N(Cast=lambda actor:actor),
                 HCWorldMaterializer=N(HCIdentity=lambda lease:True),
                 HCAIPartyIdentity=N(HCValid=lambda identity:True),
                 HCXFactions=N(Id=lambda faction:faction,HCWorldId=lambda faction:faction),
                 HCXFactionCombatAdapter=N(MAX_RECORDED_GROUPS=2))
        translate(source,'HCXFactionCombatAdapter',env,only=('HCSurveyed','HCOwns','HCDisengaged'))
        deaths, combat = [2], [False]
        group=N(IsInCombat=lambda:combat[0],DeceasedCount=lambda:deaths[0],GetFaction=lambda:'locals')
        actor=N(IsAlive=lambda:True,GetIdentity=lambda:None,GetGroup=lambda:group)
        owner=N(m_Groups=EArray(),m_InitialDeceased=EArray([99]),m_SeenCombat=True,
                HCSurveyState=lambda *args:True, HCLeaseAtPlace=lambda *args:True,
                HCLeaseState=lambda lease:N(Patrol=N(m_Group=group)))
        self.assertTrue(env['HCSurveyed'](owner,'synthetic-a','survey'))
        self.assertTrue(env['HCOwns'](owner,'lease','locals',actor,'synthetic-a','survey'))
        finish=lambda:env['HCDisengaged'](owner,'synthetic:encounter')
        self.assertFalse(finish(), 'a pre-existing casualty cannot finish this encounter')
        self.assertEqual([2],owner.m_InitialDeceased,'bind captures cumulative deaths once')
        deaths[0]=3
        self.assertTrue(env['HCOwns'](owner,'lease','locals',actor,'synthetic-a','survey'))
        self.assertTrue(finish(), 'a new death since binding establishes this fight')
        env['HCSurveyed'](owner,'synthetic-a','survey')
        env['HCOwns'](owner,'lease','locals',actor,'synthetic-a','survey')
        self.assertFalse(finish(), 'the next encounter must capture a fresh baseline')
        combat[0]=True
        self.assertFalse(finish())
        combat[0]=False
        self.assertTrue(finish(), 'observed combat can establish a fight without deaths')


class W37DebugRegistration(unittest.TestCase):
    def test_snapshot_module_registers_conflict_contributor(self):
        source=(ROOT/'mods/HollowCountry/scripts/4_World/Debug/HCDebugSnapshotModule.c').read_text()
        self.assertEqual(1,source.count('HCConflictDebugContributor conflicts = new HCConflictDebugContributor;'))
        self.assertEqual(1,source.count('HCKeep(conflicts);'))

    def test_conflict_contributor_follows_snapshot_module_lifecycle(self):
        # Synthetic registration ports; execute the authored startup/stop bodies.
        class SyntheticWorldName(str):
            def ToLower(self): pass
        source=(ROOT/'mods/HollowCountry/scripts/4_World/Debug/HCDebugSnapshotModule.c').read_text()
        source=source.replace('protected ','').replace('override ','')
        source=source.replace('HCV2ThreatStore<HCDebugDocument>', 'HCStore')
        source=source.replace('new array<ref HCDebugContributor>', 'new HCArray')
        source=source.replace('ref array<ref HCDebugContributor>', 'HCArray')
        source=source.replace('new HCDebugLeadsContributor(players)', 'HCMakeLeads(players)')
        registered, removed = [], []
        env=dict(HCArray=EArray, PATH='synthetic:snapshot',
                 HCDebugSnapshot=N(HCRegister=registered.append,HCUnregister=removed.append),
                 HCStore=N(CanOpen=lambda path:True),FileExist=lambda path:True,
                 GetGame=lambda:N(IsServer=lambda:True,GetWorldName=lambda:SyntheticWorldName('chernarusplus')),
                 HCV2Admission=N(Line=lambda *args:'synthetic admission'),Print=lambda line:None,
                 HCMakeLeads=lambda players:N(kind='HCDebugLeadsContributor'))
        for name in re.findall(r'new (HCDebug\w+Contributor|HCConflictDebugContributor)',source):
            env[name]=lambda name=name:N(kind=name)
        translate(source,'HCDebugSnapshotModule',env,only=('OnStart','HCKeep','OnStop'))
        owner=N(m_Running=False,m_AdmissionPrinted=False,m_Builtins=None,m_Save=None,
                IsEnabled=lambda settings:settings.EnableDebugSnapshot,
                HCRefuse=lambda:self.fail('synthetic prerequisites are present'))
        owner.HCKeep=lambda row:env['HCKeep'](owner,row)
        env['OnStart'](owner,N(EnableDebugSnapshot=False))
        self.assertEqual([],registered)
        env['OnStart'](owner,N(EnableDebugSnapshot=True))
        self.assertEqual(1,sum(row.kind == 'HCConflictDebugContributor' for row in registered))
        self.assertEqual(13,len(registered))
        env['OnStart'](owner,N(EnableDebugSnapshot=True))
        self.assertEqual(13,len(registered),'repeated startup must not duplicate registrations')
        env['OnStop'](owner)
        self.assertEqual(registered,removed,'stop unregisters the owned conflict contributor too')
        self.assertIsNone(owner.m_Builtins)

if __name__ == '__main__': unittest.main()
