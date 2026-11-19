"""HC-16 / #143 synthetic authored-policy execution, never DayZ evidence.

Given finite founding reserves and one home, growth must pay exactly once;
raids retain a seven-day barrier across a synthetic restart. Native inventory,
provider movement/emotes, two-client presentation and persistence remain pending.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import translate

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/World'


def authored_camp_api():
    """Shared explicit synthetic DTO/stdlib port for holdout fixture updates."""
    source = (WORLD / 'HCAICampLifecycle.c').read_text()
    cfg = N(**{k: int(v) for k, v in re.findall(r'^    int (\w+) = (\d+);',
                source.split('class HCAICampLife')[0], re.M)})
    api = N()
    env = dict(HCAICampLifecycle=api, HCAILimits=N(SIZE_CEILING=12))
    translate(source, 'HCAICampLifecycle', env)
    for name, value in tuple(env.items()):
        if callable(value): setattr(api, name, value)
    return cfg, api


class AICampBehavior(unittest.TestCase):
    def test_finite_growth_single_home_raid_restart_and_observed_death(self):
        path = WORLD / 'HCAICampLifecycle.c'
        self.assertTrue(path.exists(), 'HC-16 missing resource-funded camp lifecycle')
        cfg, api = authored_camp_api()
        def camp(home):
            return N(Home=home, Party='', Allocated=False, Population=0, Supply=0,
                     Level=-1, LastStage=0, LastUpkeep=0, ReoccupyAfter=0)
        pool = N(Stock=cfg.FoundingStock, Population=cfg.FoundingPopulation)
        a, b = camp('synthetic-house'), camp('synthetic-house')
        rows = EArray([a, b])
        empty = N(Stock=0, Population=0)
        self.assertFalse(api.HCFound(a, empty, rows, 'holdout:synthetic-house', 3, 100, cfg))
        self.assertEqual((0, 0, -1), (a.Population, a.Supply, a.Level))
        self.assertTrue(api.HCFound(a, pool, rows, 'holdout:synthetic-house', 3, 100, cfg))
        remaining = (pool.Stock, pool.Population)
        self.assertFalse(api.HCFound(a, pool, rows, 'holdout:synthetic-house', 3, 100, cfg))
        self.assertFalse(api.HCFound(b, pool, rows, 'another-party', 3, 100, cfg))
        self.assertEqual(remaining, (pool.Stock, pool.Population))
        self.assertEqual((cfg.FoundingStock-cfg.CampAllocation, cfg.FoundingPopulation-3), remaining)
        for level in range(4):
            self.assertTrue(api.HCGrow(a, 100 + level*cfg.GrowthSeconds, cfg))
            self.assertEqual(level, a.Level)
        self.assertEqual(cfg.CampAllocation - sum(api.HCCost(i, cfg) for i in range(4)), a.Supply)
        self.assertFalse(api.HCGrow(a, 100+4*cfg.GrowthSeconds, cfg))
        self.assertEqual(remaining, (pool.Stock, pool.Population))
        api.HCRaid(a, 50000, cfg)
        restored, restored_pool = deepcopy(a), deepcopy(pool)  # Explicit synthetic DTO restart.
        self.assertFalse(api.HCGrow(restored, 50000+604799, cfg))
        self.assertTrue(api.HCGrow(restored, 50000+604800, cfg))
        self.assertEqual(remaining, (restored_pool.Stock, restored_pool.Population))
        self.assertEqual(3, restored.Population, 'a theft/raid does not invent deaths')
        self.assertTrue(api.HCDeath(restored))
        self.assertEqual(2, restored.Population)
        restored.Supply = 0
        self.assertFalse(api.HCGrow(restored, 50000+604800+cfg.GrowthSeconds, cfg))
        self.assertTrue(api.HCUpkeep(restored, restored.LastUpkeep+cfg.UpkeepSeconds, cfg))
        self.assertEqual(-1, restored.Level)
        self.assertTrue(api.HCDeath(restored))
        self.assertTrue(api.HCDeath(restored))
        self.assertFalse(api.HCDeath(restored))
        self.assertFalse(api.HCFound(restored, restored_pool, EArray([restored]),
                                     restored.Party, 3, 900000, cfg))
        # Integration: execute the actual funded transition through a synthetic
        # verified-write port. A failed durable barrier closes the feature.
        holdouts = (WORLD/'HCHoldouts.c').read_text()
        row = N(Camp=camp('synthetic-other'), Ledger=N(Id='synthetic-other', HousePos=(1,0,1),
                State='DORMANT', Occupants=0, Routine='', Since=100, ReoccupyAfter=0),
                Published=True)
        state = N(Resources=N(Stock=cfg.FoundingStock, Population=cfg.FoundingPopulation),
                  CampPolicy=cfg, Rows=EArray([row]))
        from tests.unit.ai_limits_fixture import install
        integration = dict(HCAICampLifecycle=api, Print=lambda s: None,
                           HCAICampLife=N, HCAICampPolicy=N)
        install(integration)
        # The shared translator provides language scaffolding only.
        holdouts = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', holdouts)
        holdouts = holdouts.replace('array<ref HCAICampLife> homes', 'HCAICampHomeArray homes')
        integration['str'] = str
        translate(holdouts, 'HCHoldouts', integration,
                  only=('HCStepCamp', 'HCCampHomes'))
        writes = []
        module = N(m_State=state, m_Dirty=False, m_Ready=True,
                   SiteAvailable=lambda r: True, Cache=lambda i: object(),
                   Occupied=lambda: 0, Count=lambda: len(state.Rows), SaveChanged=lambda: writes.append(deepcopy(state)) or True,
                   HCLogCamp=lambda *a: None)
        module.HCCampHomes = lambda: integration['HCCampHomes'](module)
        self.assertTrue(integration['HCStepCamp'](module, 0, 100))
        self.assertEqual(1, len(writes))
        self.assertEqual('OCCUPIED', row.Ledger.State)
        self.assertEqual(0, row.Camp.Level)
        # Explicit high-stage fixture: alert expiry must work even when no
        # further growth or daily upkeep is due.
        row.Camp.Level = 3
        row.Ledger.State = 'ALERT'
        self.assertFalse(integration['HCStepCamp'](module, 0, 160))
        self.assertEqual('ALERT', row.Ledger.State)
        self.assertTrue(integration['HCStepCamp'](module, 0, 100+cfg.GrowthSeconds))
        self.assertEqual('OCCUPIED', row.Ledger.State)
        row.Camp.Level = 0
        module.SaveChanged = lambda: False
        self.assertFalse(integration['HCStepCamp'](module, 0, 100+cfg.GrowthSeconds))
        self.assertFalse(module.m_Ready)
        # No timed text simulation is permitted to kill or create neighbours.
        for filename in ('HCCampVisitors.c', 'HCCampProbes.c'):
            text = (WORLD.parent/'Camps'/filename).read_text()
            self.assertNotIn('module.Tell(', text)
            self.assertNotIn('LoseNeighbours(', text)
            self.assertNotIn('camp.Neighbours =', text)
        routine = ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXAICampRoutine.c'
        self.assertIn('HCWorldMaterializer.HCIdentity', routine.read_text())
        self.assertNotIn('CreateObject', routine.read_text())

        # One actor request per dispatch on an already qualified synthetic route;
        # providers record requests only, never claim that an engine action ran.
        from tests.unit.test_map_layers import EStr
        from tests.unit.test_group_server import execute_member
        requests, identities, refusals = [], [], []
        clock, position, combat = [100], [(0, 0, 0)], [False]
        identity = N(HCCampId=lambda: EStr('camp:synthetic-house'))
        actors = EArray(N(IsAlive=lambda: True, GetIdentity=lambda: None,
                         GetPosition=lambda: position[0],
                         GetEmoteManager=lambda: N(IsEmotePlaying=lambda: False,
                                                   CanPlayEmote=lambda i: True),
                         Expansion_SetEmote=lambda *a: requests.append(('rest', a)),
                         OverrideTargetPosition=lambda *a: requests.append(('walk', a)))
                        for _ in range(3))
        group = N(Count=lambda: 3, GetMember=lambda i: actors[i], IsInCombat=lambda: combat[0])
        site = N(Transient=True, Completed=False, Qualified=True,
                 Patrol=N(m_Group=group), ProposalId='synthetic-lease',
                 PatrolPoints=EArray([(0, 0, 0)]), HCCampMemberCursor=0,
                 HCCampRoleEpoch=0, HCCampNextRoleAt=0)
        view = N(Home=N(State='OCCUPIED', Id='synthetic-house', HousePos=(0, 0, 0)),
                 Level=3, Supply=9, Population=3)
        homes = N(HCRoutineView=lambda i: view, HCRoutinePolicy=lambda: cfg,
                  HCOwnsOccupant=lambda *a: True, BindOccupant=lambda *a: True)
        director = N(Phase=lambda: 'run', States=lambda: EArray([site]))
        routine_env = dict(GetGame=lambda: N(IsServer=lambda: True),
            HCXAISiteDirector=N(Active=lambda: director), HCHoldouts=N(Get=lambda: homes),
            HCPerfPlayers=N(HCGet=lambda: EArray([object()])),
            HCWorldMaterializer=N(HCIdentity=lambda lease: identities.append(lease) or identity),
            HCWorldClock=N(UTC=lambda: clock[0]), eAIBase=N(Cast=lambda a: a),
            EmoteConstants=N(ID_EMOTE_SITA=123),  # Explicitly synthetic enum value.
            vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x,y in zip(a,b))),
            HCRefuse=lambda state, reason: refusals.append(reason), Print=lambda s: None, str=str)
        routine_source = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', routine.read_text())
        routine_source = routine_source.replace('array<ref HCXAISiteState> states', 'HCXAICampStates states')
        routine_source = routine_source.replace('array<Man> players', 'HCPlayers players')
        routine_source = routine_source.replace('eAIGroup group', 'HCGroup group').replace('eAIBase actor', 'HCActor actor')
        translate(routine_source, 'HCXAICampRoutine', routine_env, only=('Step', 'Close'))
        worker = N(m_Enabled=False, m_Closed=False, m_Cursor=0,
                   m_Units=N(HCReset=lambda n: None, HCTake=lambda n: True),
                   m_Work=N(HCReset=lambda n: None, HCContinue=lambda: True))
        step = lambda: routine_env['Step'](worker)
        step()
        self.assertEqual([], identities)
        worker.m_Enabled = True
        for expected in range(1, 4):
            step()
            self.assertEqual(expected, len(requests))
        self.assertEqual(['walk', 'rest', 'walk'], [r[0] for r in requests])
        step()  # Role cooldown: no new request.
        self.assertEqual(3, len(requests))
        combat[0] = True
        step()
        self.assertEqual(3, len(requests))
        combat[0] = False
        position[0] = (cfg.RoutineRangeMeters+1, 0, 0)
        step()
        self.assertEqual('HOUSE_ROUTE_CONNECTION_UNPROVEN', refusals[-1])
        self.assertEqual(3, len(requests))
        routine_env['Close'](worker)
        count = len(identities)
        step()
        self.assertEqual(count, len(identities), 'off means no identity scan')
        observed = []
        callback_env = dict(HCXAICampRoutine=N(HCObserveKilled=observed.append),
                            super=N(EEKilled=lambda killer: None))
        killed = N(m_HCCampDeathSent=False)
        for _ in range(2):
            execute_member(routine.read_text().replace('this', 'self'), 'EEKilled', callback_env.copy(), killed, None)
        self.assertEqual([killed], observed, 'a real callback is debited once')


if __name__ == '__main__': unittest.main()
