"""HC-17 synthetic authored-handler execution; never native DayZ evidence.

Uses the existing restricted group member port. Only declarations/helper binding
are adapted; native ACL, save, geometry and clocks are explicit fixtures.
Actual RED: focused command below failed "3 != 1" for wall/flag requirements;
then "False is not true : ShelterSite" exposed the native site subclass.
Special-building follow-up RED: "True is not false" on bunker admission.
Retained-row follow-up RED: "-1 not greater than or equal to 0" on cursor repair.
GREEN: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest
    test_hc_building_claim test_v2_camps -v (3 tests, OK).
Initial broader tier retirement was narrowed to leave legacy respawn isolated.
"""
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest
from tests.unit.test_group_server import EArray, execute_member, translated_rules
from tests.unit.test_horde_stimulus import compile_method

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / 'mods/HollowCountry/scripts/4_World/Camps/HCBuildingClaim.c'


def run(source, name, state, env, *args):
    source = re.sub(r'\bHCBuildingClaimRecord\b', 'HCGroupClaimRecord', source)
    source = source.replace('array<Man>', 'HCGroupObserverArray')
    source = re.sub(r'\bPlayerBase (?=\w+\s*=)', 'HCGroupPlayer ', source)
    source = re.sub(r'(?<![.\w])(HC(?:Ready|Commit|Fail|ClaimHealthy|ShouldExpire))\(', r'self.\1(', source)
    source = source.replace('bool self.', 'bool ').replace('void self.', 'void ')
    return execute_member(source, name, dict(env), state, *args)


class BuildingClaimBehavior(unittest.TestCase):
    def test_group_claim_lifecycle_quarantine_and_construction_specific_refusal(self):
        # Synthetic legacy visit classification must not require built walls/flags.
        tier = compile_method('../Camps/HCCampTiers.c', 'static int Evaluate(',
                              'hearth, shelter, storage, flag, food, kitchen, walls, lights, radio', {})
        self.assertEqual(3, tier(None, True, True, True, False, True, True, 0, 2, True),
                         'HC-17 removes wall/flag requirements from legacy camp visits')
        source = CLAIMS.read_text()
        # Authored service bridge consumes the live peer/current group, rather
        # than trusting a client group ID or a cached membership assertion.
        rules = translated_rules()
        group = rules['HCGroupRecord']()
        group.Id, group.OwnerId = 1, 'synthetic-owner'
        group.Members.extend(['synthetic-owner', 'synthetic-member'])
        groups = NS(m_Healthy=True, m_State=NS(Groups=EArray([group])))
        actor = NS(GetIdentity=lambda: NS(GetId=lambda: 'synthetic-member'))
        peer = NS(Id='synthetic-member', Player=actor)
        groups.Peer = lambda uid: peer
        groups.Live = lambda candidate: candidate is peer
        acl_env = {name: rules[name] for name in ('FindGroup', 'ById', 'Role')}
        acl = lambda name, *args: run(source, name, groups, acl_env, *args)
        groups.HCClaimHealthy = lambda: acl('HCClaimHealthy')
        self.assertEqual(1, acl('HCClaimActorGroup', actor, False))
        self.assertEqual(0, acl('HCClaimActorGroup', actor, True))
        group.Officers.append('synthetic-member')
        self.assertEqual(1, acl('HCClaimActorGroup', actor, True))
        group.Members.remove('synthetic-member')
        self.assertEqual(0, acl('HCClaimActorGroup', actor, False))
        self.assertEqual(1, acl('HCClaimGroupState', 1))
        groups.m_State.Groups.clear()
        self.assertEqual(0, acl('HCClaimGroupState', 1))
        groups.m_Healthy = False
        self.assertEqual(-1, acl('HCClaimGroupState', 1))
        # Native door boundary: only ordinary lockpick-compatible buildings.
        # Match HC-8's special-building refusal rather than promising a lock
        # or heavy-infected breach on bunker/code-lock infrastructure.
        class NativeText(str):
            def IndexOf(self, value): return self.find(value)
        special = [False]
        door = NS(IsPendingDeletion=lambda: False, GetType=lambda: NativeText('Land_SyntheticHouse'),
                  GetPosition=lambda: (100, 0, 200), GetDoorCount=lambda: 1,
                  GetDoorInfo=lambda index: object(), GetLockCompatibilityType=lambda index: 1)
        door_env = {'PositionValid': lambda position: True,
                    'Bunker': NS(Cast=lambda building: special[0]),
                    'ContainerLockedBase': NS(Cast=lambda building: False),
                    'EBuildingLockType': NS(LOCKPICK=0)}
        self.assertTrue(run(source, 'HCDoor', NS(), door_env, door, 0))
        self.assertFalse(run(source, 'HCDoor', NS(), door_env, door, -1))
        special[0] = True
        self.assertFalse(run(source, 'HCDoor', NS(), door_env, door, 0))
        special[0] = False
        door.GetDoorInfo = lambda index: None
        self.assertFalse(run(source, 'HCDoor', NS(), door_env, door, 0))
        clock = [1000]
        saves = []
        durable = [True]
        state = NS(m_Healthy=True, m_LastUtc=1000,
                   m_Config=NS(ExpiryDays=30), m_Save=NS(HCDirty=False),
                   m_Status=NS(HCPublish=lambda *args: None), m_Observers=EArray(),
                   m_Examining=None, m_Data=NS(Claims=EArray()))
        env = {'Print': lambda line: None,
               'HCSaveScheduler': NS(HCUnregister=lambda job: None),
               'HCAILimits': NS(Get=lambda: NS(MaxCamps=32)),
               'HCGroupClaimRecord': lambda: NS(GroupId=0, BuildingId='', Position=None,
                                                ClaimedUtc=0, LastVisitUtc=0)}
        invoke = lambda name, *args: run(source, name, state, env, *args)
        state.HCReady = lambda now: invoke('HCReady', now)
        state.HCFail = lambda: invoke('HCFail')
        # Save acknowledgement is the synthetic IO boundary; the authored
        # commit handler owns failure quarantine, rather than a Python policy.
        state.m_Owner = NS(Commit=lambda now: saves.append(now) or durable[0])
        state.HCCommit = lambda now: invoke('HCCommit', now)
        claim = lambda group=1, key='synthetic-world:house:100:0:200:0:0:0', manage=True, release=False: invoke(
            'HCApply', group, manage, key, (100, 0, 200), clock[0], release)
        self.assertFalse(claim(manage=False))
        self.assertTrue(claim())
        self.assertEqual(1, len(state.m_Data.Claims))
        self.assertFalse(claim(key='synthetic-world:other-house'))
        self.assertFalse(claim(group=2))
        self.assertFalse(claim(group=2, release=True))  # stale/member-left ACL
        self.assertFalse(claim(group=0, release=True))
        self.assertEqual(1, len(saves))
        # Unknown group service pauses, confirmed disband releases metadata only.
        row = state.m_Data.Claims[0]
        self.assertFalse(invoke('HCShouldExpire', row, 1000, -1))
        self.assertTrue(invoke('HCShouldExpire', row, 1000, 0))
        self.assertFalse(invoke('HCShouldExpire', row, 1000 + 30 * 86400 - 1, 1))
        self.assertTrue(invoke('HCShouldExpire', row, 1000 + 30 * 86400, 1))
        self.assertFalse(invoke('HCShouldExpire', row, 999, 1))
        self.assertTrue(claim(release=True))
        self.assertFalse(claim(release=True))
        self.assertTrue(claim(group=2))
        # Conflicting migrated metadata is quarantined, never first-wins.
        store = (ROOT / 'mods/HollowCountry/scripts/4_World/Camps/HCCampStore.c').read_text()
        data = NS(ClaimsVersion=1, Claims=state.m_Data.Claims)
        validate_env = {'HCAILimits': NS(Get=lambda: NS(MaxCamps=32)), 'PositionValid': lambda value: True}
        valid = lambda: run(store, 'HCClaimsValid', NS(), validate_env, data, clock[0])
        self.assertTrue(valid())
        data.Claims.append(NS(**vars(row)))
        self.assertFalse(valid())
        data.Claims.pop()
        duplicate_group = NS(**vars(state.m_Data.Claims[0]))
        duplicate_group.BuildingId = 'synthetic-world:different-house'
        data.Claims.append(duplicate_group)
        self.assertFalse(valid())
        data.Claims.pop()
        data.ClaimsVersion = 0
        self.assertFalse(valid())  # never infer a native building from a legacy fire
        data.ClaimsVersion = 1
        durable[0] = False
        self.assertFalse(claim(group=2, release=True))
        durable[0] = True
        self.assertFalse(claim())  # no retry/reset after uncertain save
        state.m_Healthy = True
        clock[0] = 999
        self.assertFalse(claim())
        self.assertFalse(state.m_Healthy)
        # A release between slices invalidates the retained row. Cursor repair
        # must precede the next native array access; expiry deletes metadata only.
        class SnapshotArray(EArray):
            def InsertAll(self, other): self.extend(other)
            def Find(self, item):
                return next((index for index, value in enumerate(self) if value is item), -1)
        stale, current = NS(**vars(row)), NS(**vars(row))
        step_now = [1000]
        step_saves = []
        step = NS(m_Healthy=True, m_LastUtc=1000, m_Elapsed=0, m_Cursor=0,
                  m_Examining=stale, m_Observers=SnapshotArray(), m_ObserverCursor=0,
                  m_VisitObservedUtc=0, m_Config=NS(ExpiryDays=30, VisitRadiusMeters=25),
                  m_Data=NS(Claims=SnapshotArray([current])), m_Save=NS(HCDirty=False),
                  m_Owner=NS(Commit=lambda now: step_saves.append(now) or True),
                  m_Work=NS(HCReset=lambda limit: None, HCContinue=lambda: True),
                  m_Units=NS(HCReset=lambda limit: None, HCCharge=lambda count: None, HCTake=lambda cost: True))
        step_env = {**env, 'Math': NS(Min=min), 'HCWorldClock': NS(UTC=lambda: step_now[0]),
                    'HCGroupService': NS(Get=lambda: NS(HCClaimHealthy=lambda: True,
                                                       HCClaimGroupState=lambda group: 1)),
                    'HCPerfPlayers': NS(HCGet=lambda: SnapshotArray())}
        step_call = lambda name, *args: run(source, name, step, step_env, *args)
        step.HCReady = lambda now: step_call('HCReady', now)
        step.HCCommit = lambda now: step_call('HCCommit', now)
        step.HCShouldExpire = lambda *args: step_call('HCShouldExpire', *args)
        step_call('HCStep', 5)
        self.assertGreaterEqual(step.m_Cursor, 0)
        step_call('HCStep', 5)
        self.assertEqual([current], step.m_Data.Claims)
        step_now[0] += 30 * 86400
        step_call('HCStep', 5)
        self.assertEqual([], step.m_Data.Claims)
        self.assertEqual([step_now[0]], step_saves)
        # Execute the construction filter with explicit native inheritance stubs.
        construction = (ROOT / 'mods/HollowCountry/scripts/4_World/Crafting/HCNoConstruction.c').read_text()
        for kind in ('Fence', 'Watchtower', 'TerritoryFlag', 'ShelterBase', 'ShelterSite',
                     'FenceKit', 'WatchtowerKit', 'TerritoryFlagKit', 'ShelterKit'):
            obj = NS(IsKindOf=lambda candidate, kind=kind: candidate == kind)
            self.assertTrue(run(construction, 'HCDeniedObject', NS(), {}, obj), kind)
        for kind in ('WoodenCrate', 'Barrel_ColorBase', 'SeaChest', 'MediumTent', 'GardenPlot', 'Lockpick'):
            obj = NS(IsKindOf=lambda candidate, kind=kind: candidate == kind)
            self.assertFalse(run(construction, 'HCDeniedObject', NS(), {}, obj), kind)
        for recipe in ('CraftFenceKit', 'CraftWatchtowerKit', 'CraftTerritoryFlagKit', 'CraftShelterKit'):
            self.assertTrue(run(construction, 'HCDeniedRecipe', NS(), {}, recipe))
        for recipe in ('CraftWoodenCrate', 'CraftFireplace', 'CraftTripWire'):
            self.assertFalse(run(construction, 'HCDeniedRecipe', NS(), {}, recipe))
        # Execute actual native commit guards: denied construction never reaches
        # the native transaction; container placement still delegates to it.
        native_calls = []
        guards = NS()
        guard_env = {'HCNoConstruction': guards,
                     'super': NS(OnFinishProgressServer=lambda data: native_calls.append(data))}
        guards.HCDeniedObject = lambda obj: run(construction, 'HCDeniedObject', NS(), {}, obj)
        guard_env['HCDeniedObject'] = guards.HCDeniedObject
        guards.HCDeniedTarget = lambda target: run(construction, 'HCDeniedTarget', NS(), guard_env, target)
        deploy = construction[construction.index('modded class ActionDeployObject'):].replace('action_data.m_MainItem', 'action_data.MainItem')
        for kind, expected in (('FenceKit', 0), ('ShelterKit', 0), ('WoodenCrate', 1), ('SeaChest', 2)):
            obj = NS(IsKindOf=lambda candidate, kind=kind: candidate == kind)
            run(deploy, 'OnFinishProgressServer', NS(), guard_env, NS(MainItem=obj))
            self.assertEqual(expected, len(native_calls))
        build = construction[construction.index('modded class ActionBuildPart'):].replace('action_data.m_Target', 'action_data.Target')
        site = NS(IsKindOf=lambda candidate: candidate == 'ShelterSite')
        run(build, 'OnFinishProgressServer', NS(), guard_env, NS(Target=NS(GetObject=lambda: site)))
        self.assertEqual(2, len(native_calls))


if __name__ == '__main__':
    unittest.main()
