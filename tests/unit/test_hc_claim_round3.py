"""HC-17 round 3. Synthetic engine/IO fixtures; no native runtime evidence."""
import json
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import EArray, execute_member
from tests.unit.test_hc_building_claim import CLAIMS
from tests.unit.test_hc_claim_round2 import adapted, WORLD


class Snapshot(EArray):
    def InsertAll(self, values): self.extend(values)
    def Find(self, value):
        return next((i for i, row in enumerate(self) if row is value), -1)


class StepMap(dict):
    def Get(self, key): return self.get(key, 0)
    def Set(self, key, value): self[key] = value
    def Remove(self, key): self.pop(key, None)


def compiled_runner(source, state, env):
    # Syntax/native adapters only, identical to the earlier claim harness.
    source = re.sub(r'\bstring (HC(?:Apply|Request))\(', r'HCGroupMember \1(', source)
    source = re.sub(r'\bHCBuildingClaimRecord\b', 'HCGroupClaimRecord', source)
    source = source.replace('array<Man>', 'HCGroupObserverArray')
    source = re.sub(r'\bPlayerBase (?=\w+\s*=)', 'HCGroupPlayer ', source)
    source = re.sub(r'(?<![.\w])(HC(?:Ready|Commit|Fail|ShouldExpire|AccumulateAbsence))\(', r'self.\1(', source)
    source = re.sub(r'\b(bool|void) self\.', r'\1 ', source)
    cache = {}
    def invoke(name, *args):
        if name not in cache:
            scope = dict(env)
            result = execute_member(source, name, scope, state, *args)
            cache[name] = scope['member']
            return result
        return cache[name](state, *args)
    return invoke


def claim_fixture(row=None):
    source = CLAIMS.read_text()
    row = row or NS(GroupId=1, BuildingId='synthetic:house', Position=(0, 0, 0),
                    ClaimedUtc=1000, LastVisitUtc=1000, AbsentSeconds=0)
    clock, visiting, saves = [1000], [False], []
    actor = NS(GetPosition=lambda: (0, 0, 0))
    state = NS(m_Healthy=True, m_LastUtc=1000, m_Elapsed=0,
               m_OnlineSeconds=0, m_LastSteps=StepMap(), m_Cursor=0,
               m_Examining=None, m_Observers=Snapshot(), m_ObserverCursor=0,
               m_VisitObservedUtc=0, m_Config=NS(ExpiryDays=30, VisitRadiusMeters=25),
               m_Data=NS(Claims=Snapshot([row])), m_Save=NS(HCDirty=False),
               m_Owner=NS(Commit=lambda now: saves.append(row.AbsentSeconds) or True),
               m_Work=NS(HCReset=lambda cap: None, HCContinue=lambda: True),
               m_Units=NS(HCReset=lambda cap: None, HCCharge=lambda count: None, HCTake=lambda cost: True))
    env = dict(Math=NS(Min=min), HCWorldClock=NS(UTC=lambda: clock[0]),
               HCGroupService=NS(Get=lambda: NS(HCClaimHealthy=lambda: True,
                   HCClaimGroupState=lambda group: 1, HCClaimActorGroup=lambda player, manage: 1)),
               HCPerfPlayers=NS(HCGet=lambda: Snapshot([actor]) if visiting[0] else Snapshot()),
               PlayerBase=NS(Cast=lambda player: player), HCActor=lambda player: True,
               vector=NS(DistanceSq=lambda a, b: 0), Print=lambda line: None,
               HCAILimits=NS(Get=lambda: NS(MaxCamps=32)))
    invoke = compiled_runner(source, state, env)
    state.HCReady = lambda now: invoke('HCReady', now)
    state.HCCommit = lambda now: invoke('HCCommit', now)
    state.HCShouldExpire = lambda *args: invoke('HCShouldExpire', *args)
    state.HCAccumulateAbsence = lambda *args: invoke('HCAccumulateAbsence', *args)
    return state, row, clock, visiting, saves, invoke


class ClaimRound3Behavior(unittest.TestCase):
    def test_online_absence_survives_four_hour_restarts_for_31_days(self):
        state, row, clock, visiting, saves, invoke = claim_fixture()
        for tick in range(31 * 86400 // 5):
            if state.m_Data.Claims.Count() == 0: break
            if tick and tick % (4 * 3600 // 5) == 0:
                # Synthetic acknowledged checkpoint + process reload of DTO only.
                self.assertTrue(invoke('HCCheckpoint'))
                persisted = json.loads(json.dumps(vars(row)))
                state, row, new_clock, visiting, new_saves, invoke = claim_fixture(NS(**persisted))
                new_clock[0] = clock[0]
                state.m_LastUtc = new_clock[0]
                clock = new_clock
            clock[0] += 5
            invoke('HCStep', 5)
        self.assertEqual([], state.m_Data.Claims,
                         'claim must expire after 30 online days across four-hour restarts')
        self.assertEqual(30 * 86400, clock[0] - 1000)
        self.assertEqual(30 * 86400, row.AbsentSeconds)

    def test_visit_reset_downtime_hitch_legacy_and_bounds(self):
        state, row, clock, visiting, saves, invoke = claim_fixture()
        clock[0] += 5
        invoke('HCStep', 5)
        self.assertEqual(5, row.AbsentSeconds, 'online step must persist absence credit')
        self.assertTrue(state.m_Save.HCDirty)
        visiting[0] = True
        clock[0] += 5
        invoke('HCStep', 5)
        self.assertEqual(0, row.AbsentSeconds)
        # Equal UTC second still resets absence when a visit is observed.
        row.AbsentSeconds = 10
        invoke('HCStep', 5)
        self.assertEqual(0, row.AbsentSeconds)
        visiting[0] = False
        clock[0] += 40 * 86400
        state, row, new_clock, visiting, saves, invoke = claim_fixture(NS(**vars(row)))
        new_clock[0] = state.m_LastUtc = clock[0]
        new_clock[0] += 5
        invoke('HCStep', 5)
        self.assertEqual(5, row.AbsentSeconds, 'downtime is excluded on boot')
        self.assertEqual(1, state.m_Data.Claims.Count())
        new_clock[0] += 40 * 86400
        invoke('HCStep', 40 * 86400)
        self.assertLessEqual(row.AbsentSeconds, 10, 'a hitch/UTC jump earns at most a capped tick')
        # A stalled claim walk also caps credit independently of tick hitches.
        row.AbsentSeconds = 0
        state.m_OnlineSeconds += 40 * 86400
        new_clock[0] += 5
        invoke('HCStep', 5)
        self.assertEqual(10 * 32, row.AbsentSeconds)
        self.assertEqual(1, state.m_Data.Claims.Count())
        # Each row gets time since its own last turn, rather than just 5s per walk.
        multi, first, multi_clock, _, _, multi_invoke = claim_fixture()
        second = NS(**vars(first))
        second.GroupId, second.BuildingId = 2, 'synthetic:other-house'
        multi.m_Data.Claims.append(second)
        for _ in range(4):
            multi_clock[0] += 5
            multi_invoke('HCStep', 5)
        self.assertEqual((15, 20), (first.AbsentSeconds, second.AbsentSeconds))
        # Explicit synthetic JSON default adapter reads authored DTO int fields.
        store = (WORLD / 'Camps/HCCampStore.c').read_text()
        dto = store.split('class HCBuildingClaimRecord')[1].split('class HCCampData')[0]
        fields = re.findall(r'^\s*int (\w+);', dto, re.M)
        legacy = {key: 0 for key in fields}
        legacy.update(GroupId=1, ClaimedUtc=1000, LastVisitUtc=1000)
        self.assertEqual(0, legacy.get('AbsentSeconds'))
        loaded = NS(**legacy, BuildingId='synthetic:house', Position=(0, 0, 0))
        data = NS(ClaimsVersion=1, Claims=EArray([loaded]))
        validate = compiled_runner(store, NS(), dict(HCAILimits=NS(Get=lambda: NS(MaxCamps=32)), PositionValid=lambda pos: True))
        self.assertTrue(validate('HCClaimsValid', data, 1000, 30))
        for amount, expected in ((-1, False), (30 * 86400, True), (30 * 86400 + 1, False)):
            loaded.AbsentSeconds = amount
            self.assertEqual(expected, validate('HCClaimsValid', data, 1000, 30))

    def test_camp_fault_status_and_restart_clears_stale_claim_service(self):
        source = adapted((WORLD / 'Camps/HCCampModule.c').read_text())
        source = source.replace('m_Data.Camps.Count().ToString()', 'str(m_Data.Camps.Count())')
        status = NS(HCPublish=lambda value, reason: setattr(status, 'value', (value, reason)))
        events, stale = [], [True]
        state = NS(m_Running=False, m_AdmissionPrinted=True, m_Status=status, m_Players=EArray(),
                   Commit=lambda now: True,
                   s_Instance=None, IsEnabled=lambda settings: True)
        def stop():
            events.append('stop')
            stale[0] = False
        def start(*args):
            events.append('start')
            self.assertFalse(stale[0], 'stale claim singleton must be cleared before restart')
            return True
        env = dict(HCBuildingClaim=NS(HCGet=lambda: None, HCObservedStatus=lambda: 'claim-status', HCStop=stop, HCStart=start),
                   HCOperationalStatus=lambda: status, HCGroupMember=lambda: status,
                   GetGame=lambda: NS(IsServer=lambda: True), HCWorldClock=NS(UTC=lambda: 1000),
                   HCCampStore=NS(Load=lambda now: NS(Camps=EArray())),
                   HCV2Admission=NS(Line=lambda *args: ''), HCV2Gates=NS(Qualified=lambda gate: False), Print=lambda line: None)
        invoke = compiled_runner(source, state, env)
        state.Fail = lambda: invoke('Fail')
        invoke('HCCampModule')
        self.assertIs(status, invoke('HCGetOperationalStatus'))
        self.assertEqual(('off', 'camp_owner_not_running'), status.value)
        invoke('Fail')
        self.assertIs(status, invoke('HCGetOperationalStatus'), 'camp failure must override claim status')
        self.assertEqual(('refused', 'camp_clock_schema_or_persistence_fault'), status.value)
        invoke('OnStart', NS(EnableCamps=True, EnableGroups=True))
        self.assertEqual(['stop', 'start'], events)
        self.assertEqual('claim-status', invoke('HCGetOperationalStatus'))
        invoke('OnStop')
        self.assertIs(status, invoke('HCGetOperationalStatus'))
        self.assertEqual(('off', 'camp_owner_stopped'), status.value)

    def test_refusal_reason_reaches_server_player_message(self):
        state, row, clock, visiting, saves, invoke = claim_fixture()
        # The return value is the player-safe reason (empty means success).
        self.assertEqual('Building already claimed by another group.',
                         invoke('HCApply', 2, True, row.BuildingId, row.Position, 1000, False))
        self.assertEqual('Group access changed.',
                         invoke('HCApply', 0, True, row.BuildingId, row.Position, 1000, False))
        state.m_Owner.Commit = lambda now: False
        state.HCFail = lambda: setattr(state, 'm_Healthy', False)
        self.assertEqual('Claim persistence fault.',
                         invoke('HCApply', 1, True, row.BuildingId, row.Position, 1000, True))
        self.assertEqual('Claim service unavailable.',
                         invoke('HCApply', 1, True, 'other', row.Position, 1000, False))
        actions = adapted((WORLD / 'Actions/HCClaimBuildingActions.c').read_text()).replace('action_data.m_', 'action_data.')
        # Exercise the authored request too: stale preview permissions must not
        # hide live manager revalidation or service loss at completion.
        messages = []
        actor = NS(MessageStatus=messages.append, GetPosition=lambda: row.Position)
        building = NS(GetDoorIndex=lambda component: 0, GetPosition=lambda: row.Position,
                      GetDoorSoundPos=lambda door: row.Position)
        target = NS(GetParent=lambda: None, GetObject=lambda: building, GetComponentIndex=lambda: 0)
        live_group, healthy = [0], [True]
        request_env = dict(GetGame=lambda: NS(IsServer=lambda: True), HCActor=lambda player: True,
                           Building=NS(Cast=lambda obj: obj), HCDoor=lambda obj, door: True,
                           vector=NS(DistanceSq=lambda a, b: 0), HCIdentity=lambda obj: row.BuildingId,
                           HCWorldClock=NS(UTC=lambda: 1000),
                           HCGroupService=NS(Get=lambda: NS(HCClaimHealthy=lambda: healthy[0],
                               HCClaimActorGroup=lambda player, manage: live_group[0])),
                           HCApply=lambda *args: invoke('HCApply', *args))
        state.m_Healthy = True
        state.m_Config.ActionReachMeters = 2
        request = compiled_runner(adapted(CLAIMS.read_text()), state, request_env)
        self.assertEqual('Group access changed.', request('HCRequest', actor, target, False))
        healthy[0] = False
        self.assertEqual('Claim service unavailable.', request('HCRequest', actor, target, False))
        reason = ['Building already claimed by another group.']
        service = NS(HCRequest=lambda *args: reason[0])
        env = dict(HCBuildingClaim=NS(HCGet=lambda: service), Print=lambda line: None)
        action = NS(ActionCondition=lambda *args: False, HCReleaseRequest=lambda: False)
        send = compiled_runner(actions, action, env)
        for text in ('Building already claimed by another group.', 'Group access changed.',
                     'Claim persistence fault.', 'Claim service unavailable.', ''):
            reason[0] = text
            before = len(messages)
            send('OnFinishProgressServer', NS(Player=actor, Target=None, MainItem=None))
            self.assertEqual(before + bool(text), len(messages))
            if text: self.assertEqual(text, messages[-1])
        env['HCBuildingClaim'].HCGet = lambda: None
        send('OnFinishProgressServer', NS(Player=actor, Target=None, MainItem=None))
        self.assertEqual('Claim service unavailable.', messages[-1])

    def test_visit_default_is_native_literal_constant(self):
        # Native const initializers require a literal here; a division is rejected.
        source = CLAIMS.read_text()
        match = re.search(r'DEFAULT_VISIT_RADIUS_METERS = (\d+\.\d+);', source)
        self.assertIsNotNone(match, 'native visit-radius constant must be a float literal')
        self.assertEqual(25.0, float(match[1]))
