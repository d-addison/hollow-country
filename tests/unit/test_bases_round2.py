"""Round-two bases regressions; native world/identity/budget ports are synthetic.

Execute authored registration, hearth binding, tier and respawn gates. These
fixtures cannot establish DayZ inventory, geometry or replication behaviour.
"""
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_hc_building_claim import run
from tests.unit.test_horde_stimulus import compile_method

WORLD = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World'
BASES = WORLD / 'Camps/HCBasesContainers.c'
CAMPS = WORLD / 'Camps/HCCampModule.c'


def authored(source):
    """Language bindings only; all decisions remain in authored method bodies."""
    source = re.sub(r'array<(?:ref )?\w+>', 'HCGroupArray', source)
    source = source.replace('HCCampRecord', 'HCGroupCampRecord')
    source = source.replace('FireplaceBase', 'HCGroupMember').replace('ItemBase', 'HCGroupItem')
    source = source.replace('PlayerBase player', 'HCGroupPlayer player')
    source = source.replace('HCCampScan scan', 'HCGroupScan scan')
    source = source.replace('this', 'self')
    source = re.sub(r'(previous|camp.Tier)\.ToString\(\)', r'str(\1)', source)
    source = source.replace('GroupId(', 'self.GroupId(')
    source = source.replace('Commit(now)', 'self.Commit(now)').replace('Tell(', 'self.Tell(')
    return source


class BasesRoundTwo(unittest.TestCase):
    def test_container_then_hearth_matches_hearth_only_binding_tier_and_respawn(self):
        native = authored(CAMPS.read_text())
        extension = authored(BASES.read_text())
        tier = compile_method('../Camps/HCCampTiers.c', 'static int Evaluate(',
                              'hearth, shelter, storage, flag, food, kitchen, walls, lights, radio', {})
        eligible = compile_method('../Camps/HCCampTiers.c', 'static bool HCRespawnEligible(',
                                  'tier, threat, now, last', {})
        outcomes = []
        for container_first in (False, True):
            rows, saves = EArray(), []
            actor = NS(GetPosition=lambda: (100, 0, 200), IsAlive=lambda: True,
                       GetIdentity=lambda: 'synthetic-account')
            stash = NS(IsPendingDeletion=lambda: False, IsRuined=lambda: False,
                       GetPosition=lambda: (100, 0, 200), GetType=lambda: 'WoodenCrate')
            fire = NS(IsPendingDeletion=lambda: False, GetHierarchyParent=lambda: None,
                      IsBurning=lambda: True, GetPosition=lambda: (101, 0, 200),
                      GetType=lambda: 'Fireplace')
            state = NS(m_Data=NS(Camps=rows), m_Players=EArray([actor]),
                       m_HCBasesEnabled=True, m_Running=True, GroupId=lambda player: '7',
                       Commit=lambda now: saves.append(now) or True, Tell=lambda *args: None)
            env = dict(HCGroupArray=EArray,
                       HCGroupCampRecord=lambda: NS(FireClass='', FireRef='', LastScan=0, Tier=0,
                                                    ProbePhase=0, Members=EArray()),
                       HCCampScan=NS(StorageItem=lambda item: item is stash,
                                     RefOf=lambda item: 'synthetic-stash' if item is stash else 'synthetic-fire',
                                     Read=lambda *args: NS(Shelter=True, Storage=True, RaisedFlag=False,
                                                           Garden=True, Traps=0, Kitchen=True, Walls=0,
                                                           Lights=2, HasRadio=True, Flag='', Items=EArray())),
                       HCPerfPlayers=NS(HCGet=lambda: EArray([actor])), HCWorldMaterializer=NS(MAX_PLAYERS=32),
                       HCBuildingClaim=NS(HCActor=lambda player: True), PlayerBase=NS(Cast=lambda value: value),
                       HCBuildingClaimConfig=NS(DEFAULT_ACTION_REACH_METERS=2), UAMaxDistances=NS(DEFAULT=2),
                       HCAILimits=NS(Get=lambda: NS(MaxCamps=1)),
                       vector=NS(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))),
                       GetGame=lambda: NS(IsKindOf=lambda kind, parent: kind == 'WoodenCrate' and parent == kind),
                       Print=lambda message: None, s_Fires=EArray([fire]),
                       HCCampTiers=NS(Evaluate=lambda *args: tier(None, *args),
                                      Decayed=lambda value, now, last: value),
                       HCCampVisitors=NS(Step=lambda *args: None),
                       HCCampMailbox=NS(Step=lambda *args: None),
                       # Explicit synthetic visitor refusal; tier/respawn policy remains authored.
                       HCCampProbes=NS(Step=lambda *args: None,
                                      HCRequestVisitorParty=lambda *args: False),
                       HCCampTheft=NS(Step=lambda *args: None),
                       Fact=lambda *args: None)
            env['super'] = NS(Candidate=lambda hearth, now: run(native, 'Candidate', state, env, hearth, now))
            if container_first:
                run(extension, 'HCBasesCandidate', state, env, stash, 1000)
                self.assertEqual(1, len(rows))
                old_row = rows[0]
                old_row.Members.Insert('synthetic-existing-member')
            candidate_source = extension if re.search(r'override (?:protected )?void Candidate\(', extension) else native
            run(candidate_source, 'Candidate', state, env, fire, 1005)
            self.assertEqual(1, len(rows), 'promote the existing row even at MaxCamps')
            row = rows[0]
            self.assertEqual('Fireplace', row.FireClass, 'storage row must accept the later hearth')
            self.assertIs(fire, run(native, 'FireFor', state, env, row))
            if container_first:
                self.assertIs(old_row, row)
                self.assertEqual(['synthetic-existing-member'], row.Members)
                # A later storage retry must never refresh the hearth's LastLit.
                run(extension, 'HCBasesCandidate', state, env, stash, 1010)
                self.assertEqual(1005, row.LastLit)
            env['FireFor'] = lambda camp: run(native, 'FireFor', state, env, camp)
            run(native, 'StepCamp', state, env, row, 1015)
            self.assertEqual(3, row.Tier)
            self.assertEqual(1015, row.LastScan)
            outcomes.append((row.Position, row.FireClass, row.FireRef, row.LastLit, row.Tier,
                             [eligible(None, row.Tier, threat, now, last)
                              for threat, now, last in ((False, 4000, 0), (True, 4000, 0),
                                                        (False, 4000, 2500), (False, 4300, 2500))]))
            self.assertEqual([True, False, False, True], outcomes[-1][-1])
            self.assertEqual([1000, 1005, 1015] if container_first else [1005, 1015], saves)
        self.assertEqual(outcomes[0], outcomes[1])

    def test_overflow_candidates_are_retained_and_retried_one_per_budgeted_tick(self):
        source = authored(BASES.read_text())
        source = source.replace('s_Items', 'self.s_Items')
        source = source.replace('HCBasesCandidate(nextStash, m_LastUtc)', 'self.HCBasesCandidate(nextStash, m_LastUtc)')
        registry = NS(s_Items=EArray())
        items = [NS(IsKindOf=lambda kind: kind == 'WoodenCrate') for _ in range(5)]
        env = dict(GetGame=lambda: NS(IsServer=lambda: True),
                   HCAILimits=NS(Get=lambda: NS(MaxCampItems=2)), HCRefuse=lambda reason: None)
        for item in items:
            run(source, 'HCRemember', registry, env, item)
        visited, charged = [], []
        permitted = [False]
        budget = NS(HCTakeFor=lambda consumer, cost: charged.append((consumer, cost)) or permitted[0])
        state = NS(m_Running=True, m_HCBasesEnabled=True, m_HCBasesCursor=0,
                   m_Data=NS(Camps=EArray()), m_LastUtc=1000,
                   HCBasesCandidate=lambda item, now: visited.append(item))
        # Synthetic budget port uses the current production consumer id.
        env.update(super=NS(OnTick=lambda delta: None), HCServer=NS(HCTickWork=lambda: budget),
                   HCUnitBudget=NS(HC_WORK_BASES=8), HCWorldMaterializer=NS(MAX_PLAYERS=32),
                   HCBasesContainers=NS(HCCount=lambda: len(registry.s_Items),
                                        HCAt=lambda index: registry.s_Items[index]))
        run(source, 'OnTick', state, env, 1)
        self.assertEqual([], visited, 'budget refusal retains the cursor and candidates')
        permitted[0] = True
        for _ in range(len(items)):
            before = len(visited)
            run(source, 'OnTick', state, env, 1)
            self.assertEqual(before + 1, len(visited), 'bounded dispatch, even after overflow')
        self.assertEqual([id(item) for item in items], [id(item) for item in visited],
                         'overflow candidates must be visited on later ticks')
        run(source, 'HCForget', registry, env, items[-1])
        run(source, 'OnTick', state, env, 1)
        self.assertNotIn(id(items[-1]), [id(item) for item in registry.s_Items])
        self.assertTrue(all(cost == (8, 32) for cost in charged))


if __name__ == '__main__':
    unittest.main()
