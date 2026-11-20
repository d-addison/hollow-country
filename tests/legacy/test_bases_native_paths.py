"""#151 authored behavior with explicit synthetic native/IO fixtures; no DayZ proof."""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from tests.legacy.test_hc_building_claim import run
from tests.legacy.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World'


class BasesNativePaths(unittest.TestCase):
    def test_pitched_world_tent_is_storage_but_packed_or_carried_is_not(self):
        source = (WORLD / 'Camps/HCCampScan.c').read_text().replace('TentBase storageTent', 'HCGroupTent storageTent')
        tent = NS(IsKindOf=lambda kind: kind == 'TentBase', GetState=lambda: 1,
                  GetHierarchyParent=lambda: None)
        env = dict(TentBase=NS(Cast=lambda item: item if item is tent else None, PITCHED=1))
        self.assertTrue(run(source, 'StorageItem', NS(), env, tent), 'pitched tent must count as storage')
        tent.GetState = lambda: 0
        self.assertFalse(run(source, 'StorageItem', NS(), env, tent))
        tent.GetState = lambda: 1
        tent.GetHierarchyParent = lambda: object()
        self.assertFalse(run(source, 'StorageItem', NS(), env, tent))
        for kind in ('WoodenCrate', 'SeaChest', 'Barrel_ColorBase'):
            item = NS(IsKindOf=lambda candidate: candidate == kind, GetHierarchyParent=lambda: None)
            self.assertTrue(run(source, 'StorageItem', NS(), env, item), kind)

    def test_claimed_building_lock_requires_live_group_but_unclaimed_keeps_vanilla(self):
        source = (WORLD / 'Camps/HCBuildingClaim.c').read_text().replace('array<ref HCBuildingClaimRecord>', 'HCGroupClaimArray')
        self.assertIn('bool HCCanLock(', source)
        # Execute the actual narrow authorization policy; geometry/native actions tested separately.
        claims = EArray([NS(GroupId=7, BuildingId='synthetic:house')])
        state = NS(m_Healthy=True, m_Data=NS(Claims=claims))
        for group, key, expected in ((7, 'synthetic:house', True), (8, 'synthetic:house', False),
                                     (0, 'synthetic:house', False), (0, 'synthetic:other', True)):
            self.assertEqual(expected, run(source, 'HCCanLock', state, {}, group, key))
        state.m_Healthy = False
        self.assertFalse(run(source, 'HCCanLock', state, {}, 7, 'synthetic:house'))

    def test_native_lock_completion_revalidates_and_retains_native_tool_damage(self):
        source = (WORLD / 'Camps/HCBuildingClaim.c').read_text()
        part = source.split('modded class ActionLockDoors\n')[-1]
        self.assertIn('modded class ActionLockDoors\n', source)
        calls = []
        allowed = [False]
        env = dict(HCBuildingClaim=NS(HCLockAllowed=lambda player, target: allowed[0]),
                   super=NS(ActionCondition=lambda *args: True,
                            OnFinishProgressServer=lambda data: calls.append(data)))
        state = NS(ActionCondition=lambda *args: allowed[0])
        data = NS(Player=NS(MessageStatus=lambda message: None), Target='synthetic-door', MainItem='synthetic-lockpick')
        part = part.replace('action_data.m_', 'action_data.').replace('if (!ActionCondition(', 'if (!self.ActionCondition(')
        self.assertFalse(run(part, 'ActionCondition', state, env, data.Player, data.Target, data.MainItem))
        run(part, 'OnFinishProgressServer', state, env, data)
        self.assertEqual([], calls)
        allowed[0] = True
        self.assertTrue(run(part, 'ActionCondition', state, env, data.Player, data.Target, data.MainItem))
        run(part, 'OnFinishProgressServer', state, env, data)
        self.assertEqual([data], calls)
        self.assertNotIn('modded class ActionUnlockDoors', source, 'raiding keeps native unlock behavior')

    def test_live_lock_bridge_keeps_client_preview_and_operator_opt_out_native(self):
        source = (WORLD / 'Camps/HCBuildingClaim.c').read_text()
        source = source.replace('Building lockBuilding', 'HCGroupBuilding lockBuilding')
        source = source.replace('HCGroupService lockGroups', 'HCGroupGroups lockGroups')
        source = source.replace('s_Instance.m_', 's_Instance.')
        service = NS(Healthy=True, OperatorDisabled=False,
                     HCCanLock=lambda group, key: group == 7)
        server, live_group = [True], [7]
        groups = NS(HCClaimHealthy=lambda: True, HCClaimActorGroup=lambda player, manager: live_group[0])
        building = NS(GetDoorIndex=lambda component: 0)
        target = NS(GetObject=lambda: building, GetComponentIndex=lambda: 0)
        env = dict(s_Instance=service, GetGame=lambda: NS(IsServer=lambda: server[0]),
                   HCActor=lambda actor: True, Building=NS(Cast=lambda value: value),
                   HCDoor=lambda obj, door: True, HCGroupService=NS(Get=lambda: groups),
                   HCIdentity=lambda obj: 'synthetic:house')
        invoke = lambda: run(source, 'HCLockAllowed', NS(), env, object(), target)
        self.assertTrue(invoke())
        live_group[0] = 8
        self.assertFalse(invoke(), 'membership is resolved at server completion')
        service.OperatorDisabled = True
        self.assertTrue(invoke())
        service.OperatorDisabled = False
        service.Healthy = False
        self.assertFalse(invoke())
        server[0] = False
        self.assertTrue(invoke(), 'client preview does not own the ACL')

    def test_probe_admission_is_default_on_and_opt_out_is_read_once(self):
        source = (WORLD / 'Camps/HCCampProbes.c').read_text()
        for name in ('s_AdmissionPrinted', 's_Enabled', 's_Refusal'):
            source = source.replace(name, 'self.' + name)
        for disabled in (False, True):
            reads, logs = [], []
            state = NS(s_AdmissionPrinted=False, s_Enabled=False, s_Refusal='')
            env = dict(FileExist=lambda path: reads.append(path) or disabled,
                       Print=logs.append, HCV2Admission=NS(Line=lambda *args: str(args)))
            self.assertEqual(not disabled, run(source, 'HCEnabled', state, env))
            self.assertEqual(not disabled, run(source, 'HCEnabled', state, env))
            self.assertEqual(['$profile:HollowCountry/acceptance/camp_probes.disable'], reads)
            self.assertEqual(1, len(logs))
            run(source, 'HCRefuse', state, env, 'PROBE_PLAYER_BASE_DISPATCH_UNAVAILABLE')
            run(source, 'HCRefuse', state, env, 'PROBE_PLAYER_BASE_DISPATCH_UNAVAILABLE')
            self.assertEqual(2, len(logs), 'same reason logs once')

    def test_missing_probe_dispatch_does_not_spend_durable_cooldown(self):
        source = (WORLD / 'Camps/HCCampProbes.c').read_text().replace('camp.Tier.ToString()', 'str(camp.Tier)')
        saves, logs = [], []
        module = NS(Commit=lambda now: saves.append(now) or True)
        camp = NS(ProbePhase=0, ProbeUntil=0, Tier=3, LastProbe=0, Id='synthetic-camp')
        env = dict(Eligible=lambda *args: True, HCEscalationClock=NS(Day=lambda: 14),
                   Print=logs.append, FileExist=lambda path: False, HCEnabled=lambda: True,
                   HCRefuse=lambda reason: logs.append(reason + ' runtime=PENDING'))
        # Execute the new real dispatch bridge with an explicit unbound provider.
        bridge = (WORLD / 'Camps/HCBaseRaid.c').read_text().replace('HCBaseRaidPort port', 'HCGroupPort port')
        bridge_env = dict(HCBaseRaid=NS(HCEnabled=lambda: True, HCGet=lambda: None,
                          HCRefuse=lambda reason: logs.append(reason + ' runtime=PENDING')))
        env['HCBaseRaid'] = NS(HCWarn=lambda *args: run(bridge, 'HCWarn', NS(), bridge_env, *args))
        scan = NS(Hidden=lambda burning: False)
        run(source, 'Step', NS(), env, module, camp, scan, False, 2000000)
        self.assertEqual(0, camp.LastProbe, 'unavailable dispatch must not spend cooldown')
        self.assertEqual([], saves)
        self.assertTrue(any('PROBE_' in line and 'runtime=PENDING' in line for line in logs))

    def test_storage_only_stash_is_tier_one_without_construction_or_a_hearth(self):
        from tests.legacy.test_horde_stimulus import compile_method
        tier = compile_method('../Camps/HCCampTiers.c', 'static int Evaluate(',
                              'hearth, shelter, storage, flag, food, kitchen, walls, lights, radio', {})
        self.assertEqual(1, tier(None, False, False, True, False, False, False, 0, 0, False))
        self.assertEqual(0, tier(None, False, True, False, False, False, False, 0, 0, False))

    def test_container_discovery_uses_native_identity_and_acknowledged_camp_store(self):
        path = WORLD / 'Camps/HCBasesContainers.c'
        self.assertTrue(path.exists(), 'container discovery owner is missing')
        source = path.read_text()
        # Authored registration against an explicit synthetic world candidate.
        source = source.replace('ItemBase stash', 'HCGroupItem stash')
        source = source.replace('HCCampRecord', 'HCGroupCampRecord').replace('array<ref HCGroupCampRecord>', 'HCGroupCampArray')
        source = source.replace('campGroup.ToString()', 'str(campGroup)')
        source = source.replace('m_HCBasesContainers', 'self.m_HCBasesContainers')
        rows, saves = EArray(), []
        item = NS(IsPendingDeletion=lambda: False, IsRuined=lambda: False,
                  GetPosition=lambda: (100, 0, 200), GetType=lambda: 'WoodenCrate')
        actor = NS(GetPosition=lambda: (100, 0, 200))
        state = NS(m_Data=NS(Camps=rows), GroupId=lambda player: '7',
                   Commit=lambda now: saves.append(now) or True)
        env = dict(HCCampScan=NS(StorageItem=lambda candidate: candidate is item, RefOf=lambda candidate: '1:2:3:4'),
                   HCPerfPlayers=NS(HCGet=lambda: EArray([actor])),
                   HCWorldMaterializer=NS(MAX_PLAYERS=32),
                   HCBuildingClaim=NS(HCActor=lambda player: True), PlayerBase=NS(Cast=lambda value: value),
                   HCBuildingClaimConfig=NS(DEFAULT_ACTION_REACH_METERS=2), UAMaxDistances=NS(DEFAULT=2),
                   HCAILimits=NS(Get=lambda: NS(MaxCamps=32)), vector=NS(DistanceSq=lambda a, b: 0),
                   HCGroupCampRecord=lambda: NS(), Print=lambda line: None)
        # Calls to owner methods are a language binding adaptation only.
        source = source.replace('GroupId(stashPlayer)', 'self.GroupId(stashPlayer)')
        source = source.replace('if (!Commit(now))', 'if (!self.Commit(now))')
        run(source, 'HCBasesCandidate', state, env, item, 1000)
        self.assertEqual(1, len(rows))
        self.assertEqual(('7', '1:2:3:4', 1000), (rows[0].GroupId, rows[0].FireRef, rows[0].LastLit))
        self.assertEqual([1000], saves)
        run(source, 'HCBasesCandidate', state, env, item, 1005)
        self.assertEqual(1, len(rows), 'same native container must not duplicate a camp')
        self.assertEqual(1005, rows[0].LastLit)

    def test_container_tick_uses_its_shared_consumer_to_avoid_starvation(self):
        source = (WORLD / 'Camps/HCBasesContainers.c').read_text()
        source = source.replace('ItemBase nextStash', 'HCGroupItem nextStash')
        source = source.replace('HCBasesCandidate(nextStash, m_LastUtc)', 'self.HCBasesCandidate(nextStash, m_LastUtc)')
        charged, dispatched = [], []
        state = NS(m_Running=True, m_HCBasesEnabled=True, m_HCBasesCursor=0,
                   m_Data=NS(Camps=EArray()), m_LastUtc=1000,
                   HCBasesCandidate=lambda item, now: dispatched.append((item, now)))
        # Explicit synthetic constants follow the integrated shared core:
        # HCUnitBudget.HC_WORK_BASES=8, HC_WORK_CONSUMERS=20.
        budget = NS(HCTake=lambda cost: False,
                    HCTakeFor=lambda consumer, cost: charged.append((consumer, cost)) or True)
        env = dict(super=NS(OnTick=lambda delta: None), HCServer=NS(HCTickWork=lambda: budget),
                   HCUnitBudget=NS(HC_WORK_BASES=8, HC_WORK_CONSUMERS=20),
                   HCWorldMaterializer=NS(MAX_PLAYERS=32),
                   HCBasesContainers=NS(HCCount=lambda: 1, HCAt=lambda index: 'synthetic-stash'))
        run(source, 'OnTick', state, env, 1)
        self.assertEqual([('synthetic-stash', 1000)], dispatched, 'container must progress after other consumers exhaust the tick')
        self.assertEqual([(8, 32)], charged)
        state.m_HCBasesEnabled = False
        run(source, 'OnTick', state, env, 1)
        self.assertEqual(1, len(dispatched), 'operator off is a cheap no-op')

    def test_barrels_and_chests_classify_native_storage_without_invented_lock_slots(self):
        source = (WORLD / 'World/HCLockTable.c').read_text()
        for kind in ('TentBase', 'WoodenCrate', 'SeaChest', 'Barrel_ColorBase'):
            item = NS(IsKindOf=lambda candidate: kind == candidate, GetType=lambda: kind)
            self.assertTrue(run(source, 'StorageType', NS(), {}, item), kind)


if __name__ == '__main__':
    unittest.main()
