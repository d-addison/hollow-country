"""HC-35/#145 spec -> plan -> task: one funded, reciprocal same-item barter.

Explicit synthetic inventory/provider/store ports execute authored Enforce
handlers through the existing restricted translator; never DayZ evidence.
Provider rendezvous/emote acknowledgement and paired Hive restore are pending.

2026-11-18 actual RED (before source existed):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_ai_trade -v
AssertionError: False is not true : HC-35 second-party failure has no conserved-cargo rollback barrier
FAILED (failures=1). Native preflight extension also failed with 4 != 2 for an
invalidated intent; HCMoveAllowed now checks the durable phase before mutation.
GREEN: same focused command, Ran 1 test, OK. Synthetic evidence only.

HC-36 extends this same feature check (no second test):
2026-11-18 actual RED with the same command before caravan source existed:
AssertionError: False is not true : HC-36 has no durable outbound/return corridor or loss barrier
FAILED (failures=1).
Turnaround/flee extension RED: 'fleeing_return_pending' != 'fleeing_returning'.
HC-10 route provenance extension RED: HCBegin('lease') -> False (route:party).
GREEN: same focused command, Ran 1 test, OK; synthetic ports only, never DayZ.

Wave 6 wiring/review regression, actual RED 2026-11-18 (same focused command):
Ran 1 test; FAILED (failures=5): addon lifecycle and cached status missing;
HCQuarantine and failed HCCheckpoint both yielded 'lost' != 'unknown';
False is not true : terminal + cooldown must admit remaining stock.
Stock-ceiling extension RED: 1 != 2 : observed depletion must lower the durable stock ceiling.
Loss/quantity uncertainty extension RED: ('quarantined', 'lost') != ('quarantined', 'unknown').
GREEN: same command, Ran 1 test, OK. Extends this one behavioral test with
synthetic lifecycle/status/store/native-handle ports, never DayZ evidence.

"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as N
import json
import re
import unittest

from tests.unit.test_hc_scavenge import bind
from tests.unit.test_map_layers import EStr
from tests.unit.test_group_server import EArray, body

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCAITrade.c'
ADAPTER = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAITradeAdapter.c'


class TradeBehavior(unittest.TestCase):
    def test_second_party_failure_restores_committed_cargo_without_replay(self):
        self.assertTrue(SOURCE.exists(),
                        'HC-35 second-party failure has no conserved-cargo rollback barrier')
        source = SOURCE.read_text()
        self.assertIn('$mission:hollow-country/ai/trade-recipes.json', source)
        content = json.loads((ROOT / 'mission/hollow-country/ai/trade-recipes.json').read_text())
        recipe = N(**content)
        bind(source, 'HCTradeRecipe', recipe, ('HCValid',),
             dict(HCScavengeDefaults=lambda: N(TransferRangeMeters=2.5)))
        self.assertTrue(recipe.HCValid())
        recipe.TransferRangeMeters = 1000
        self.assertFalse(recipe.HCValid(), 'network bubble is not a transfer range')
        names = ('HCValidState', 'HCActive', 'HCCheckpoint', 'HCBegin', 'HCStep', 'HCMoveStep',
                 'HCQuarantine', 'HCAbort', 'HCRestore', 'HCComplete', 'HCClose', 'HCLog')

        def fixture(second=2, rollback=2, fail_write=0, interrupt=False, ready=True):
            # Exactly two pre-existing items; moves only change their owners.
            state = N(Version=1, Id='', Phase='idle', Transfer='none', Refusal='',
                      LeftLease='', RightLease='', LeftParty='', RightParty='',
                      LeftCargo='', RightCargo='', LeftGeneration=0, RightGeneration=0,
                      LeftActor='', RightActor='', LeftItem='', RightItem='',
                      LeftQuantity=2, RightQuantity=1, StartedAt=0, EndsAt=0)
            physical, moves, saved, logs = ['left', 'right'], [], [], []
            live, at, gesture, current, clock, writes = [True], [False], [False], [True], [100], [0]
            left = N(HCPartyId=lambda: 'left-party', HCCargoId=lambda: 'left-cargo', HCGeneration=lambda: 1)
            right = N(HCPartyId=lambda: 'right-party', HCCargoId=lambda: 'right-cargo', HCGeneration=lambda: 2)

            def save(row):
                writes[0] += 1
                if writes[0] == fail_write: return False
                saved.append(deepcopy(row))
                return True

            def move(step, row):
                moves.append(step)
                self.assertEqual('intent_' + step, saved[-1].Phase)
                # Restricted native port refuses before mutation when either
                # item was stolen. The native handler is exercised below too.
                expected = ['left', 'right'] if step == 'left' else ['right', 'right']
                if physical != expected: return 4
                result = 2
                if step == 'right': result = second
                if step == 'rollback': result = rollback
                if result != 4:  # Ambiguous native result MAY already have moved.
                    if step == 'left': physical[0] = 'right'
                    if step == 'right': physical[1] = 'left'
                    if step == 'rollback': physical[0] = 'left'
                if interrupt: trade.HCAbort(EStr('INTERRUPTED_INSIDE_NATIVE'))
                return result

            io = N(HCReady=lambda: ready, HCRefusal=lambda: 'SYNTHETIC_PROVIDER_REFUSED',
                   HCBind=lambda row: True, HCBeginWalk=lambda row: True,
                   HCCurrent=lambda row: current[0], HCLive=lambda: live[0],
                   HCAtMeeting=lambda: at[0], HCObservedGestures=lambda row: gesture[0],
                   HCOwners=lambda row, exchanged: physical == (['right', 'left'] if exchanged else ['left', 'right']),
                   HCMove=move, HCClear=lambda: None,
                   HCItemId=lambda left_side: 'left-item' if left_side else 'right-item',
                   HCActorId=lambda left_side: 'left' if left_side else 'right')
            trade = N(m_State=state, m_Store=N(Save=save), m_IO=io,
                      m_Ready=True, m_Enabled=True, m_Busy=False, m_Reports=0,
                      m_Recipe=N(RecipeId='bandage-for-drink', TimeoutSeconds=120),
                      m_Status=N(HCPublish=lambda *args: None))
            env = dict(Print=logs.append, str=str, float=N(MAX=3.402823466e38),
                       HCWorldLimits=N(Token=lambda value: 0 < len(value) <= 96),
                       HCAIPartyIdentity=N(HCValid=lambda i: i in (left, right)),
                       HCWorldMaterializer=N(HCIdentity=lambda lease: {'left-lease': left, 'right-lease': right}.get(lease)))
            bind(source, 'HCTradeTransaction', trade, names, env)
            return N(trade=trade, state=state, physical=physical, moves=moves,
                     saved=saved, logs=logs, live=live, at=at, gesture=gesture,
                     current=current, clock=clock)

        def start(f):
            return f.trade.HCBegin('left-lease', 'right-lease', 100)

        def rendezvous(f):
            f.at[0] = True
            f.gesture[0] = True

        # Required RED scenario: first item committed, second definitively
        # refused before native mutation. Refund is the SAME native item.
        f = fixture(second=4)
        self.assertTrue(start(f))
        f.trade.HCStep(101)
        self.assertEqual([], f.moves, 'no remote trade')
        f.at[0] = True
        f.trade.HCStep(102)
        self.assertEqual([], f.moves, 'request is not observed gesture completion')
        rendezvous(f)
        f.trade.HCStep(103)
        self.assertEqual(['right', 'right'], f.physical)
        f.trade.HCStep(104)
        self.assertEqual('rollback_pending', f.state.Phase)
        f.trade.HCStep(105)
        self.assertEqual(('rolled_back', ['left', 'right']), (f.state.Phase, f.physical))
        self.assertEqual(['left', 'right', 'rollback'], f.moves)
        self.assertFalse(f.trade.HCComplete())
        self.assertFalse(start(f))
        for now in range(106, 110): f.trade.HCStep(now)
        self.assertEqual(3, len(f.moves))

        # Happy path keeps both original item identities; no stock grant port.
        ok = fixture()
        self.assertTrue(start(ok))
        rendezvous(ok)
        ok.trade.HCStep(101)
        ok.trade.HCStep(102)
        self.assertTrue(ok.trade.HCComplete())
        self.assertEqual(['right', 'left'], ok.physical)
        self.assertEqual(('complete', 'reciprocal_confirmed'), (ok.state.Phase, ok.state.Transfer))
        ok.physical[0] = 'player'
        self.assertFalse(ok.trade.HCComplete(), 'receipt cannot hide subsequent theft')

        # Unknown native state, failed rollback, journal failure and callbacks
        # never authorize a second refund, mint, debit or replay.
        for mode in ('ambiguous', 'rollback_failed', 'save_before', 'save_after',
                     'interrupt', 'death', 'surrender', 'steal', 'lease', 'timeout'):
            with self.subTest(mode=mode):
                f = fixture(second=3 if mode == 'ambiguous' else 4,
                            rollback=4 if mode == 'rollback_failed' else 2,
                            fail_write={'save_before': 2, 'save_after': 3}.get(mode, 0),
                            interrupt=mode == 'interrupt')
                self.assertTrue(start(f))
                rendezvous(f)
                if mode == 'timeout':
                    f.trade.HCStep(220)
                    self.assertEqual([], f.moves)
                    self.assertEqual('cancelled', f.state.Phase)
                else:
                    f.trade.HCStep(101)
                    if mode in ('death', 'surrender'): f.live[0] = False
                    if mode == 'steal': f.physical[0] = 'player'
                    if mode == 'lease': f.current[0] = False
                    f.trade.HCStep(102)
                    f.trade.HCStep(220 if mode == 'rollback_timeout' else 103)
                self.assertFalse(f.trade.HCComplete())
                self.assertIn(f.state.Phase, ('quarantined', 'cancelled'))
                count = len(f.moves)
                f.trade.HCStep(221)
                self.assertEqual(count, len(f.moves))
                self.assertFalse(start(f))

        # Review P2 (lead): a timeout after the left item moved still returns that
        # same item (right refused before mutation), whether the timeout lands in
        # right_pending or rollback_pending. RED before: quarantined, left item kept.
        for mode in ('right_timeout', 'rollback_timeout'):
            with self.subTest(mode=mode):
                f = fixture(second=4)
                self.assertTrue(start(f))
                rendezvous(f)
                f.trade.HCStep(101)
                self.assertEqual('right_pending', f.state.Phase)
                if mode == 'rollback_timeout':
                    f.trade.HCStep(102)
                    self.assertEqual('rollback_pending', f.state.Phase)
                f.trade.HCStep(220)
                self.assertEqual(('rolled_back', ['left', 'right']), (f.state.Phase, f.physical))
                self.assertNotIn('right', f.moves[1:] if mode == 'right_timeout' else [])
                count = len(f.moves)
                f.trade.HCStep(221)
                self.assertEqual(count, len(f.moves))
                self.assertFalse(f.trade.HCComplete())

        # Restart at every saved exchange boundary must quarantine without
        # rebind, native replay or compensation. Terminal receipts stay final.
        crashed = fixture(second=4)
        start(crashed)
        rendezvous(crashed)
        for now in (101, 102, 103): crashed.trade.HCStep(now)
        for image in crashed.saved:
            f = fixture()
            f.trade.m_State = deepcopy(image)
            f.trade.HCRestore()
            f.trade.HCStep(101)
            self.assertEqual([], f.moves)
            expected = 'rolled_back' if image.Phase == 'rolled_back' else 'quarantined'
            self.assertEqual(expected, f.trade.m_State.Phase)
            self.assertFalse(start(f))

        stopped = fixture()
        start(stopped)
        rendezvous(stopped)
        stopped.trade.HCStep(101)
        stopped.trade.HCClose()
        stopped.trade.HCClose()
        stopped.trade.HCStep(102)
        self.assertEqual(['left'], stopped.moves)
        self.assertEqual('quarantined', stopped.state.Phase)
        off = fixture()
        off.trade.m_Enabled = False
        self.assertFalse(start(off))
        off.trade.HCStep(100)
        self.assertEqual([], off.saved)
        refused = fixture(ready=False)
        self.assertFalse(start(refused))
        self.assertEqual([], refused.moves)
        self.assertTrue(any('trade=none' in line and 'count=0' in line for line in refused.logs))
        binding_stop = fixture()
        binding_stop.trade.m_IO.HCBind = lambda row: setattr(binding_stop.trade, 'm_Enabled', False) or True
        self.assertFalse(start(binding_stop))
        self.assertEqual([], binding_stop.saved, 'stop during binding must not issue a walk intent')
        self.assertTrue(ok.trade.HCValidState(ok.state))
        for field, invalid in (('Phase', 'forged'), ('Transfer', 'none'), ('EndsAt', 0),
                               ('LeftItem', ''), ('RightCargo', 'left-cargo'), ('LeftQuantity', float('nan'))):
            row = deepcopy(ok.state)
            setattr(row, field, invalid)
            self.assertFalse(ok.trade.HCValidState(row), field)
        self.assertTrue(any('HC-35 trade=' in line and 'transfer=' in line and
                            'runtime=PENDING' in line for line in ok.logs))

        # Shipping provider refuses capabilities that cannot be inspected here.
        adapter = N()
        bind(ADAPTER.read_text(), 'HCXAITradeAdapter', adapter,
             ('HCReady', 'HCRefusal', 'HCBeginWalk', 'HCObservedGestures', 'HCBind'), {})
        self.assertFalse(adapter.HCReady())
        self.assertFalse(adapter.HCBind(N()))
        self.assertFalse(adapter.HCBeginWalk(N()))
        self.assertFalse(adapter.HCObservedGestures(N()))
        self.assertEqual('TRADE_RENDEZVOUS_EMOTE_ACK_UNVERIFIED', adapter.HCRefusal())

        # Actual authored N2 handler against explicit synthetic native handles.
        # These ports only expose location/capacity/mutation, never trade policy.
        class Location:
            def __init__(self): self.parent = None
            def GetParent(self): return self.parent
            def CompareLocationOnly(self, other): return self.parent is other.parent

        capacity, locked, remote, surrendered, player, live = [True], [False], [False], [False], [False], [True]
        callback, result, native_moves = [lambda: None], [True], []
        left_actor, right_actor = N(pid='left'), N(pid='right')
        parents, quantities = [left_actor, right_actor], [2, 1]
        left_item, right_item = N(pid='left-item'), N(pid='right-item')
        for actor in (left_actor, right_actor):
            actor.GetIdentity = lambda: object() if player[0] else None
            actor.IsAlive = lambda: live[0]
            actor.IsUnconscious = lambda: False
            actor.IsSurrendered = lambda: surrendered[0]
            actor.GetPosition = lambda: (0, 0, 0)
        right_actor.GetPosition = lambda: (100, 0, 0) if remote[0] else (0, 0, 0)

        def inventory(actor):
            def find(stock, flags, loc):
                loc.parent = actor
                callback[0]()
                return capacity[0]
            def move(mode, before, target):
                native_moves.append((before.parent.pid, target.parent.pid))
                index = 1 if io.RightItem is stock_in_move[0] else 0
                parents[index] = target.parent
                return result[0]
            return N(FindFreeLocationFor=find, TakeToDst=move,
                     IsInventoryLocked=lambda: locked[0])

        stock_in_move = [left_item]
        for actor in (left_actor, right_actor):
            actor.GetInventory = lambda actor=actor: inventory(actor)
        for index, item in enumerate((left_item, right_item)):
            item.GetHierarchyRootPlayer = lambda index=index: parents[index]
            item.GetQuantity = lambda index=index: quantities[index]
            item.GetType = lambda index=index: ('BandageDressing', 'SodaCan_Kvass')[index]
            item.IsRuined = lambda: False
            item.IsTakeable = lambda: True
            def current(loc, index=index): loc.parent = parents[index]; return True
            item.GetInventory = lambda current=current: N(GetCurrentInventoryLocation=current)
        native_left = N(HCPartyId=lambda: 'left-party', HCCargoId=lambda: 'left-cargo', HCGeneration=lambda: 1)
        native_right = N(HCPartyId=lambda: 'right-party', HCCargoId=lambda: 'right-cargo', HCGeneration=lambda: 2)
        row = N(Phase='intent_left', LeftLease='left-lease', RightLease='right-lease',
                LeftParty='left-party', RightParty='right-party', LeftCargo='left-cargo', RightCargo='right-cargo',
                LeftGeneration=1, RightGeneration=2)
        io = N(LeftActor=left_actor, RightActor=right_actor, LeftItem=left_item, RightItem=right_item,
               Recipe=N(HCValid=lambda: True, TransferRangeMeters=2.5,
                        LeftClass='BandageDressing', RightClass='SodaCan_Kvass'))
        native_env = dict(GetGame=lambda: N(IsServer=lambda: True),
            HCSearchSupplyRegistry=N(PersistentId=lambda entity: entity.pid),
            HCWorldMaterializer=N(HCIdentity=lambda lease: {'left-lease': native_left, 'right-lease': native_right}.get(lease)),
            HCAIPartyIdentity=N(HCValid=lambda identity: identity in (native_left, native_right)),
            InventoryLocation=Location, FindInventoryLocationType=N(CARGO=1), InventoryMode=N(SERVER=1),
            vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))))
        bind(source, 'HCTradeInventory', io,
             ('HCActorId', 'HCItemId', 'HCLive', 'HCAtMeeting', 'HCCurrent',
              'HCOwners', 'HCInventoryBound', 'HCMoveAllowed', 'HCMove'), native_env)
        self.assertTrue(io.HCInventoryBound(row))
        for mode in ('full', 'locked', 'remote', 'surrender', 'player', 'dead', 'identity', 'quantity', 'phase', 'stolen'):
            with self.subTest(native_refusal=mode):
                capacity[0], locked[0], remote[0] = mode != 'full', mode == 'locked', mode == 'remote'
                surrendered[0], player[0], live[0] = mode == 'surrender', mode == 'player', mode != 'dead'
                row.LeftItem = 'wrong-item' if mode == 'identity' else 'left-item'
                quantities[0] = 3 if mode == 'quantity' else 2
                row.Phase = 'quarantined' if mode == 'phase' else 'intent_left'
                parents[0] = None if mode == 'stolen' else left_actor
                self.assertEqual(4, io.HCMove('left', row))
                self.assertEqual([], native_moves)
        capacity[0], locked[0], remote[0], surrendered[0], player[0], live[0] = True, False, False, False, False, True
        parents[0], row.Phase = left_actor, 'intent_left'
        # Callback during FindFreeLocationFor invalidates the persisted intent.
        callback[0] = lambda: setattr(row, 'Phase', 'quarantined')
        self.assertEqual(4, io.HCMove('left', row))
        self.assertEqual([], native_moves)
        callback[0] = lambda: None
        row.Phase = 'intent_left'
        self.assertEqual(2, io.HCMove('left', row))
        self.assertIs(right_actor, parents[0])
        stock_in_move[0], row.Phase, capacity[0] = right_item, 'intent_right', False
        self.assertEqual(4, io.HCMove('right', row))
        self.assertIs(right_actor, parents[1])
        stock_in_move[0], row.Phase, capacity[0] = left_item, 'intent_rollback', True
        self.assertEqual(2, io.HCMove('rollback', row))
        self.assertEqual([left_actor, right_actor], parents)
        # A false return after native mutation is uncertain, never a safe refusal.
        result[0], row.Phase = False, 'intent_left'
        self.assertEqual(3, io.HCMove('left', row))
        self.assertIs(right_actor, parents[0])

        # HC-36 extends this ONE trade feature check. Explicit synthetic walking,
        # custody and durable-store ports execute the authored corridor handler.
        caravan_path = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCAICaravan.c'
        self.assertTrue(caravan_path.exists(),
                        'HC-36 has no durable outbound/return corridor or loss barrier')
        caravan_source = caravan_path.read_text()
        # Wave 6 source contracts: the optional addon owns this adjunct even
        # when its retired lease profile is absent. No native runtime claim.
        owner_source = (ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIAdapter.c').read_text()
        def lifecycle(name):
            match = re.search(r'override void ' + name + r'\([^)]*\)\s*\{', owner_source)
            return body(owner_source, match.end())
        startup, tick, stop = map(lifecycle, ('OnStart', 'OnTick', 'OnStop'))
        with self.subTest(wave6='addon_lifecycle'):
            self.assertIn('protected ref HCAICaravan m_Caravan;', owner_source)
            self.assertIn('HCXAICaravanAdapter caravanPort = new HCXAICaravanAdapter();', startup)
            self.assertLess(startup.index('HCXAIService.Bind'), startup.index('m_Caravan.Open(settings, caravanPort)'))
            self.assertLess(startup.index('m_Caravan.Open(settings, caravanPort)'), startup.index('startup rejected'))
            self.assertLess(tick.index('m_Caravan.Step()'), tick.index('if (!m_Profile)'))
            self.assertIn('m_Caravan.HCClose()', stop)
            self.assertLess(stop.index('m_Caravan.HCClose()'), stop.index('m_Caravan = null'))
        with self.subTest(wave6='cached_status'):
            operational = (ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXOperationalAdapters.c').read_text()
            self.assertIn('m_Caravan.HCGetOperationalStatus()', operational)
            self.assertIn('HCObserve(', operational)
            self.assertEqual(1, operational.count('[HC Plan] HC-36'))
        # Execute the addon lifecycle with synthetic sibling owners. This uses
        # the existing syntax adapter, independently of the older addon fixture.
        for service_bound in (True, False):
            calls, logs, captured = [], [], []
            cached = N(HCState=lambda: 'refused', HCReason=lambda: 'CARAVAN_CORRIDOR_UNSURVEYED')
            caravan_port = N()
            adjunct = N(Open=lambda settings, port: calls.append(('open', port)),
                        Step=lambda: calls.append(('step',)),
                        HCClose=lambda: calls.append(('close',)),
                        HCGetOperationalStatus=lambda: cached, m_Ready=False, m_IO=None,
                        m_ProviderRefusal='CARAVAN_PROVIDER_CALLBACKS_UNVERIFIED',
                        HCActive=lambda: self.fail('refused status should not inspect active state'))
            ports = []
            owner = N(m_Profile=None, m_Leases=EArray(), m_Caravan=None,
                      m_CaravanOperationalOwner=None, m_ReadinessLogged=True,
                      LogAddonChecks=lambda: None, LogReadiness=lambda trigger: None,
                      HasReservations=lambda: False)
            scope = dict(Print=logs.append, GetGame=lambda: N(IsServer=lambda: True, GetTickTime=lambda: 100),
                         HCXAIQualification=N(SetEncountersEnabled=lambda enabled: None),
                         HCXAIService=N(Bind=lambda module: service_bound, Adapter=lambda: owner),
                         # Synthetic situation/raid ports; only bind order is recorded here.
                         HCSituationActors=N(HCBind=lambda port: ports.append(('situation', port)),
                                             HCBindRaid=lambda port: ports.append(('raid', port)),
                                             HCBindTransit=lambda port: ports.append(('transit', port))),
                         HCCampRaidActors=N(HCBind=lambda port: ports.append(('camp-raid', port))),
                         HCXAISituationAdapter=lambda: 'situation-port', HCXAIRaidAdapter=lambda: 'raid-port',
                         HCXAITransitAdapter=lambda: 'transit-port',
                         HCXAISiteDirector=lambda: N(Start=lambda: None, Step=lambda: None, Stop=lambda: None),
                         HCXAIEncounters=lambda: N(Open=lambda: None, Step=lambda: None, Close=lambda: None),
                         HCXAICampRoutine=lambda: N(Open=lambda settings: None, Step=lambda: None, Close=lambda: None),
                         HCXAICaravanAdapter=lambda: caravan_port, HCAICaravan=lambda: adjunct,
                         HCOperationalContributors=N(HCRegisterOwner=lambda name: N(
                             HCObserve=lambda requested, status, now: captured.append((requested, status)))))
            lifecycle_source = owner_source.replace('this', 'self').replace('array<ref HCXAILease>', 'EArray')
            bind(lifecycle_source, 'HCXAIAdapter', owner,
                 ('OnStart', 'OnTick', 'OnStop'), scope)
            # Own namespace: the shared translator keys string literals by index.
            bind(lifecycle_source, 'HCXAIAdapter', owner, ('HCDropCaravanHandles',), dict(scope))
            # Syntax-only field inheritance expansion for the modded link.
            status_source = operational.replace('    protected ref HCOperationalOwner',
                '    ref HCAICaravan m_Caravan;\n    bool m_CaravanRequested;\n    protected ref HCOperationalOwner', 1)
            bind(status_source, 'HCXAIAdapter', owner, ('HCPublishCaravanStatus',), scope)
            owner.OnStart(N(EnableEncounters=True))
            self.assertEqual([('open', caravan_port)], calls)
            self.assertIs(cached, captured[-1][1], 'publish exactly the cached caravan status')
            owner.OnTick(1)
            self.assertEqual(('step',), calls[-1], 'retired profile cannot skip caravan Step')
            owner.OnStop()
            self.assertEqual(('close',), calls[-1])
            self.assertIsNone(owner.m_Caravan)
            self.assertFalse(captured[-1][0], 'stopped contributor must retain an inactive receipt')
            plan_lines = [line for line in logs if '[HC Plan] HC-36' in line]
            self.assertEqual(1, len(plan_lines))
            self.assertIn('state=refused reason=CARAVAN_CORRIDOR_UNSURVEYED', plan_lines[0])
            self.assertIn('count=0 count_cap=1 runtime=PENDING', plan_lines[0])
            self.assertIn('provider_refused=CARAVAN_PROVIDER_CALLBACKS_UNVERIFIED', plan_lines[0])
        corridor = N(**json.loads((ROOT / 'mission/hollow-country/ai/caravans.json').read_text(),
                                 object_hook=lambda fields: {k: EStr(v) if isinstance(v, str) else v
                                                            for k, v in fields.items()}))
        bind(caravan_source, 'HCCaravanCorridor', corridor, ('HCValid', 'HCAdmissionRefusal'),
             dict(HCScavengeDefaults=lambda: N(TransferRangeMeters=2.5),
                  HCWorldLimits=N(Token=lambda value: bool(value) and len(value) <= 96)))
        self.assertTrue(corridor.HCValid())
        self.assertEqual('CARAVAN_CORRIDOR_UNSURVEYED', corridor.HCAdmissionRefusal())
        corridor.Version = 0
        self.assertFalse(corridor.HCValid(), 'missing JSON version must refuse')
        corridor.Version, corridor.ArrivalRangeMeters = 1, 1000
        self.assertFalse(corridor.HCValid(), 'network bubble is not camp arrival')

        caravan_names = ('HCTerminal', 'HCValidTripId', 'HCValidHistory', 'Step', 'HCValidState', 'HCActive', 'HCCheckpoint', 'HCQuarantine',
                         'HCBegin', 'HCRequestWalk', 'HCStep', 'HCRestore',
                         'HCConfirmedReturn', 'HCClose', 'HCLog')
        class CaravanFixture(N):
            @property
            def row(self): return self.trip.m_State

        def caravan_row():
            return N(Version=1, Id='', Leg='idle', CargoReceipt='none', Refusal=EStr(''),
                    LeaseId='', PartyId='', CargoId='', RouteId='', Generation=0,
                    ActorId='', ItemId='', ItemClass='', Quantity=0,
                    TripSequence=0, History=EArray())

        def caravan_fixture(fail_write=0, ready=True, interrupt=False):
            row = caravan_row()
            place, cargo, alive, current, fleeing = ['home'], ['retained'], [True], [True], [False]
            clock, stock = [100], [2]
            walks, saved, logs, writes = [], [], [], [0]
            def save_caravan(image):
                writes[0] += 1
                if writes[0] == fail_write: return False
                saved.append(deepcopy(image))
                return True
            def walk_caravan(image, returning):
                self.assertEqual('returning' if returning else 'outbound', saved[-1].Leg)
                walks.append(returning)
                if interrupt: trip.HCClose()
                return True
            def bind_caravan(image):
                image.ActorId, image.ItemId = 'carrier', 'finite-item'
                image.ItemClass, image.Quantity = 'BandageDressing', stock[0]
                return True
            port = N(HCReady=lambda: ready, HCRefusal=lambda: 'SYNTHETIC_ROUTE_REFUSED',
                     HCBindCaravan=bind_caravan, HCCurrentCaravan=lambda image: current[0],
                     HCCargoReceipt=lambda image: cargo[0], HCRemainingQuantity=lambda image: stock[0],
                     HCLive=lambda: alive[0],
                     HCAtCamp=lambda image, returning: place[0] == ('home' if returning else 'away'),
                     HCFleeObserved=lambda image: fleeing[0], HCWalkCaravan=walk_caravan,
                     HCClear=lambda: None)
            identity = N(HCPartyId=lambda: 'party', HCCargoId=lambda: 'cargo',
                         HCGeneration=lambda: 1, HCRouteId=lambda: 'route:party')
            status, budget_calls, clears = ['refused', 'synthetic_pending'], [], []
            port.HCClear = lambda: clears.append('clear')
            trip = N(m_State=row, m_IO=port, m_Store=N(Save=save_caravan),
                     m_Units=N(HCReset=lambda cap: budget_calls.append(cap), HCTake=lambda count: True),
                     m_Work=N(HCReset=lambda cap: budget_calls.append(cap), HCContinue=lambda: True),
                     m_ProviderRefusal='SYNTHETIC_PROVIDER_REFUSED',
                     m_TerminalAt=-1, m_Enabled=True, m_Ready=True, m_Busy=False, m_Reports=0,
                     m_Corridor=N(CorridorId=EStr('hc36-first-corridor'), HCAdmissionRefusal=lambda: '',
                                  CooldownSeconds=900, MaxTripHistory=16),
                     m_Status=N(HCPublish=lambda state, reason: status.__setitem__(slice(None), [state, reason]),
                                HCState=lambda: status[0], HCReason=lambda: status[1]))
            bind(caravan_source, 'HCAICaravan', trip, caravan_names,
                 dict(Print=logs.append, str=str, float=N(MAX=3.402823466e38),
                      GetGame=lambda: N(GetTickTime=lambda: clock[0]),
                      HCCaravanState=caravan_row, HCCaravanReceipt=N,
                      HCWorldLimits=N(Token=lambda value: bool(value) and len(value) <= 96),
                      HCAIPartyIdentity=N(HCValid=lambda value: value is identity),
                      HCWorldMaterializer=N(HCIdentity=lambda lease: identity if lease == 'lease' else None)))
            return CaravanFixture(trip=trip, place=place, cargo=cargo, alive=alive,
                     current=current, fleeing=fleeing, walks=walks, saved=saved, logs=logs,
                     clock=clock, stock=stock, budget_calls=budget_calls, clears=clears)

        c = caravan_fixture()
        self.assertTrue(c.trip.HCBegin('lease'))
        self.assertEqual([False], c.walks)
        c.trip.HCStep()
        self.assertEqual('outbound', c.row.Leg, 'elapsed time does not prove arrival')
        c.fleeing[0] = True
        c.trip.HCStep()
        self.assertEqual('fleeing_outbound', c.row.Leg)
        c.cargo[0] = 'lost'
        c.trip.HCStep()
        self.assertEqual(('fleeing_outbound', 'lost'), (c.row.Leg, c.row.CargoReceipt))
        c.fleeing[0], c.place[0] = False, 'away'
        c.trip.HCStep()
        self.assertEqual('return_pending', c.row.Leg)
        self.assertEqual([False], c.walks, 'arrival cannot cause instantaneous return')
        c.trip.HCStep()
        self.assertEqual([False, True], c.walks)
        c.place[0], c.cargo[0] = 'home', 'retained'
        c.trip.HCStep()
        self.assertEqual(('returned', 'lost'), (c.row.Leg, c.row.CargoReceipt))
        self.assertTrue(c.trip.HCConfirmedReturn(), 'party may return without stolen cargo')
        self.assertFalse(c.trip.HCBegin('lease'), 'return never resets finite stock')
        for snapshot in c.saved:
            reboot = caravan_fixture()
            reboot.trip.m_State = deepcopy(snapshot)
            reboot.trip.HCRestore()
            reboot.trip.HCStep()
            self.assertEqual([], reboot.walks, 'restart never replays travel or cargo')
            self.assertIn(reboot.trip.m_State.Leg, ('quarantined', 'returned'))
            self.assertFalse(reboot.trip.HCBegin('lease'))

        paused_return = caravan_fixture()
        self.assertTrue(paused_return.trip.HCBegin('lease'))
        paused_return.place[0] = 'away'
        paused_return.trip.HCStep()
        paused_return.fleeing[0] = True
        paused_return.trip.HCStep()
        self.assertEqual('fleeing_return_pending', paused_return.row.Leg)
        self.assertEqual([False], paused_return.walks)
        paused_return.fleeing[0] = False
        paused_return.trip.HCStep()
        self.assertEqual([False, True], paused_return.walks,
                         'flee at turnaround must retain the unissued return request')

        happy = caravan_fixture()
        self.assertTrue(happy.trip.HCBegin('lease'))
        happy.place[0] = 'away'
        happy.trip.HCStep()
        happy.trip.HCStep()
        happy.fleeing[0] = True
        happy.trip.HCStep()
        self.assertEqual('fleeing_returning', happy.row.Leg)
        happy.fleeing[0], happy.place[0] = False, 'home'
        happy.trip.HCStep()
        self.assertTrue(happy.trip.HCConfirmedReturn())
        self.assertEqual(('retained', 2, 'finite-item'),
                         (happy.row.CargoReceipt, happy.row.Quantity, happy.row.ItemId))
        self.assertTrue(happy.trip.HCValidState(happy.row))
        with self.subTest(wave6='observed_stock_floor'):
            drained = caravan_fixture()
            self.assertTrue(drained.trip.HCBegin('lease'))
            drained.cargo[0], drained.stock[0] = 'lost', 1
            drained.trip.HCStep()
            self.assertEqual(1, drained.row.Quantity, 'observed depletion must lower the durable stock ceiling')
            self.assertEqual(1, drained.saved[-1].Quantity)
            drained.stock[0] = 0.5
            drained.trip.HCStep()
            self.assertEqual(0.5, drained.saved[-1].Quantity, 'subsequent depletion must also checkpoint')
            drained.cargo[0], drained.place[0] = 'retained', 'away'
            drained.trip.HCStep()
            drained.trip.HCStep()
            drained.place[0] = 'home'
            drained.trip.HCStep()
            drained.clock[0] += 900
            drained.stock[0] = 2
            self.assertFalse(drained.trip.HCBegin('lease'), 'same item cannot regain observed spent stock')
            drained.stock[0] = 0.5
            self.assertTrue(drained.trip.HCBegin('lease'))
            self.assertEqual(('lost', 0.5), (drained.row.History[0].CargoReceipt, drained.row.Quantity))
        with self.subTest(wave6='lost_then_quantity_uncertain'):
            uncertain = caravan_fixture()
            self.assertTrue(uncertain.trip.HCBegin('lease'))
            uncertain.cargo[0], uncertain.stock[0] = 'lost', -1
            uncertain.trip.HCStep()
            self.assertEqual(('quarantined', 'lost'), (uncertain.row.Leg, uncertain.row.CargoReceipt))
        with self.subTest(wave6='lost_quarantine'):
            lost = caravan_fixture()
            self.assertTrue(lost.trip.HCBegin('lease'))
            lost.row.CargoReceipt = 'lost'
            lost.trip.HCQuarantine(EStr('SYNTHETIC_UNCERTAINTY'))
            self.assertEqual('lost', lost.row.CargoReceipt)
            self.assertTrue(lost.trip.HCValidState(lost.row))
        with self.subTest(wave6='lost_failed_checkpoint'):
            lost = caravan_fixture(fail_write=2)
            self.assertTrue(lost.trip.HCBegin('lease'))
            lost.row.CargoReceipt = 'lost'
            self.assertFalse(lost.trip.HCCheckpoint())
            self.assertEqual('lost', lost.row.CargoReceipt)
            self.assertTrue(lost.trip.HCValidState(lost.row))
        with self.subTest(wave6='second_trip'):
            repeat = caravan_fixture()
            self.assertTrue(repeat.trip.HCBegin('lease'))
            first_id = repeat.row.Id
            repeat.clock[0] += 1000
            self.assertFalse(repeat.trip.HCBegin('lease'), 'cooldown alone cannot end an active trip')
            repeat.place[0] = 'away'
            repeat.trip.HCStep()
            repeat.trip.HCStep()
            repeat.place[0] = 'home'
            repeat.trip.HCStep()
            self.assertFalse(repeat.trip.HCBegin('lease'), 'terminal state alone cannot skip cooldown')
            repeat.clock[0] += 899
            self.assertFalse(repeat.trip.HCBegin('lease'), 'cooldown boundary is inclusive only at expiry')
            repeat.clock[0] += 1
            repeat.stock[0] = 1
            self.assertTrue(repeat.trip.HCBegin('lease'), 'terminal + cooldown must admit remaining stock')
            self.assertNotEqual(first_id, repeat.trip.m_State.Id)
            self.assertEqual(('finite-item', 1), (repeat.trip.m_State.ItemId, repeat.trip.m_State.Quantity))
            self.assertEqual([first_id], [receipt.Id for receipt in repeat.row.History])
            self.assertEqual(1, repeat.saved[-1].Quantity)
            # Repeated new trips retain one finite item. No second cargo source.
            repeat.trip.m_Corridor.MaxTripHistory = 2
            def finish_repeat():
                repeat.place[0] = 'away'
                repeat.trip.HCStep()
                repeat.trip.HCStep()
                repeat.place[0] = 'home'
                repeat.trip.HCStep()
                repeat.clock[0] += 900
            finish_repeat()
            second_id = repeat.row.Id
            before = deepcopy(repeat.row)
            repeat.stock[0] = 2
            self.assertFalse(repeat.trip.HCBegin('lease'), 'same item may never refill remaining stock')
            self.assertEqual(before, repeat.row, 'refused admission cannot erase the terminal receipt')
            repeat.stock[0] = 1
            original_bind = repeat.trip.m_IO.HCBindCaravan
            def replacement(image):
                original_bind(image)
                image.ItemId = 'replacement-item'
                return True
            repeat.trip.m_IO.HCBindCaravan = replacement
            self.assertFalse(repeat.trip.HCBegin('lease'), 'replacement stock is not remaining stock')
            repeat.trip.m_IO.HCBindCaravan = original_bind
            self.assertTrue(repeat.trip.HCBegin('lease'))
            self.assertEqual(3, repeat.row.TripSequence)
            self.assertEqual([second_id], [receipt.Id for receipt in repeat.row.History],
                             'only the oldest terminal receipt is evicted')
            self.assertEqual((3, [second_id]), (repeat.saved[-1].TripSequence,
                             [receipt.Id for receipt in repeat.saved[-1].History]))
            invalid_history = deepcopy(repeat.row)
            invalid_history.History[0].Leg = 'outbound'
            self.assertFalse(repeat.trip.HCValidState(invalid_history))
            live_id, stored = repeat.row.Id, len(repeat.saved)
            repeat.clock[0] += 9000
            self.assertFalse(repeat.trip.HCBegin('lease'), 'active rows are never evictable')
            self.assertEqual((live_id, stored), (repeat.row.Id, len(repeat.saved)))
            finish_repeat()
            repeat.trip.HCRestore()
            self.assertFalse(repeat.trip.HCBegin('lease'), 'restart waits a fresh conservative cooldown')
            repeat.clock[0] += 900
            self.assertTrue(repeat.trip.HCBegin('lease'))
            self.assertEqual(4, repeat.row.TripSequence, 'eviction/restart never reuses an identity')
        with self.subTest(wave8='fresh_idle_stock_ceiling'):
            idle = caravan_fixture()
            self.assertTrue(idle.trip.HCBegin('lease'))
            idle.place[0] = 'away'
            idle.trip.HCStep()
            idle.trip.HCStep()
            idle.place[0] = 'home'
            idle.trip.HCStep()
            idle.clock[0] += 900
            # Explicit synthetic stale binding: admission still reports the old
            # quantity while the existing remaining-stock port observes depletion.
            stale_bind = idle.trip.m_IO.HCBindCaravan
            idle.trip.m_IO.HCRemainingQuantity = lambda image: 0.5
            self.assertFalse(idle.trip.HCBegin('lease'), 'fresh remaining stock must reject a stale bind ceiling')
            self.assertEqual(0.5, idle.saved[-1].Quantity)
            idle.trip.m_IO.HCRemainingQuantity = lambda image: 2
            self.assertFalse(idle.trip.HCBegin('lease'), 'idle refill must not restore an observed ceiling')
            idle.stock[0] = 0.5
            idle.trip.m_IO.HCRemainingQuantity = lambda image: 0.5
            idle.trip.m_IO.HCBindCaravan = stale_bind
            self.assertTrue(idle.trip.HCBegin('lease'))
            self.assertEqual(('lost', 0.5), (idle.row.History[-1].CargoReceipt, idle.row.Quantity))
        with self.subTest(wave8='trim_loaded_terminal_history'):
            loaded = caravan_fixture()
            self.assertTrue(loaded.trip.HCBegin('lease'))
            loaded.row.TripSequence = 5
            loaded.row.Id = 'hc36-first-corridor:trip:5'
            loaded.row.Leg = 'returned'
            loaded.row.History = EArray(N(Id='hc36-first-corridor:trip:' + str(seq),
                TripSequence=seq, Leg='returned', CargoReceipt='retained',
                ItemId='finite-item', Quantity=2) for seq in range(1, 5))
            loaded.trip.m_Corridor.MaxTripHistory = 2
            self.assertTrue(loaded.trip.HCValidState(loaded.row), 'lower operator cap must not invalidate terminal history')
            # Execute the authored load preparation handler, also called by Open.
            bind(caravan_source, 'HCAICaravan', loaded.trip, ('HCTrimHistory',), {})
            self.assertTrue(loaded.trip.HCTrimHistory())
            self.assertEqual([4], [r.TripSequence for r in loaded.row.History])
            self.assertEqual([4], [r.TripSequence for r in loaded.saved[-1].History])
            loaded.row.History[0].Leg = 'outbound'
            before = deepcopy(loaded.row)
            self.assertFalse(loaded.trip.HCTrimHistory(), 'nonterminal history must never be trimmed')
            self.assertEqual(before, loaded.row)
            loaded.row.History[0].Leg = 'returned'
            loaded.trip.m_Corridor.MaxTripHistory = 1
            loaded.trip.m_Store.Save = lambda image: False
            self.assertFalse(loaded.trip.HCTrimHistory(), 'trim readback failure must refuse load')
            self.assertIn('HCTrimHistory()', body(caravan_source, re.search(r'void Open\([^)]*\)\s*\{', caravan_source).end()))
        with self.subTest(wave8='failed_bind_clears_handles'):
            failed = caravan_fixture()
            failed.trip.m_IO.HCBindCaravan = lambda image: False
            self.assertFalse(failed.trip.HCBegin('lease'))
            self.assertEqual(['clear'], failed.clears, 'failed bind must clear provider handles')
            self.assertEqual([], failed.saved)
        legacy = caravan_fixture()
        self.assertTrue(legacy.trip.HCBegin('lease'))
        legacy.row.Id, legacy.row.TripSequence, legacy.row.History = 'hc36-first-corridor', 0, None
        legacy.row.Leg = 'returned'
        legacy.trip.HCRestore()
        self.assertTrue(legacy.trip.HCValidState(legacy.row), 'legacy missing sequence/history remain valid')
        legacy.clock[0] += 900
        self.assertTrue(legacy.trip.HCBegin('lease'))
        self.assertEqual('hc36-first-corridor:trip:1', legacy.row.Id)
        self.assertEqual(['hc36-first-corridor'], [receipt.Id for receipt in legacy.row.History])
        legacy.trip.HCQuarantine(EStr('SYNTHETIC_LOSS_UNCERTAINTY'))
        legacy.clock[0] += 9000
        self.assertFalse(legacy.trip.HCBegin('lease'), 'uncertainty cannot become reusable terminal stock')
        # Known loss stays in history even when remaining stock is observed.
        c.clock[0] += 900
        c.stock[0] = 1
        self.assertTrue(c.trip.HCBegin('lease'))
        self.assertEqual('lost', c.row.History[0].CargoReceipt)
        # Missing v1 JSON fields are native zero, not declared initializers.
        corridor.Version, corridor.ArrivalRangeMeters = 1, 2.5
        corridor.CooldownSeconds, corridor.MaxTripHistory = 0, 0
        self.assertTrue(corridor.HCValid())
        self.assertEqual((900, 16), (corridor.CooldownSeconds, corridor.MaxTripHistory))
        for field, bad in (('CooldownSeconds', -1), ('CooldownSeconds', 604801),
                           ('MaxTripHistory', -1), ('MaxTripHistory', 65)):
            old = getattr(corridor, field)
            setattr(corridor, field, bad)
            self.assertFalse(corridor.HCValid())
            setattr(corridor, field, old)
        for inactive in ('off', 'refused'):
            f = caravan_fixture(ready=False)
            f.trip.m_Enabled = inactive != 'off'
            f.trip.Step()
            self.assertEqual(([], []), (f.budget_calls, f.saved), 'no hidden off/refused work')
            f.trip.HCClose()
            self.assertEqual(['clear'], f.clears)
            self.assertIsNone(f.trip.m_IO)
        for field, bad in (('Version', 0), ('Leg', 'forged'), ('CargoReceipt', 'minted'),
                           ('ItemId', ''), ('RouteId', ''), ('Generation', 0), ('Quantity', float('nan'))):
            invalid = deepcopy(happy.row)
            setattr(invalid, field, bad)
            self.assertFalse(happy.trip.HCValidState(invalid), field)
        for mode in ('dead', 'lease', 'unknown', 'save', 'stop', 'off', 'refused', 'callback'):
            f = caravan_fixture(fail_write=2 if mode == 'save' else 0,
                                ready=mode != 'refused', interrupt=mode == 'callback')
            if mode == 'off': f.trip.m_Enabled = False
            began = f.trip.HCBegin('lease')
            if mode in ('off', 'refused'):
                self.assertFalse(began)
                self.assertEqual([], f.saved)
            else:
                if mode == 'dead': f.alive[0] = False
                if mode == 'lease': f.current[0] = False
                if mode == 'unknown': f.cargo[0] = 'unknown'
                if mode == 'stop': f.trip.HCClose()
                f.place[0] = 'away'
                f.trip.HCStep()
                self.assertIn(f.row.Leg, ('lost', 'quarantined'))
            prior = len(f.walks)
            f.trip.HCStep()
            self.assertEqual(prior, len(f.walks))
        self.assertTrue(any('HC-36 caravan=' in line and 'cargo=lost' in line and
                            'runtime=PENDING' in line for line in c.logs))
        # Reuse HC-35's authored persistent-ID readers, with explicit native
        # stand-ins. No item creation/move/counting policy exists in this fixture.
        carrier_alive, unconscious = [True], [False]
        stock_owner, stock_quantity, stock_id = ['carrier'], [2], ['finite-item']
        carrier = N(pid='carrier', GetIdentity=lambda: None,
                    IsAlive=lambda: carrier_alive[0], IsUnconscious=lambda: unconscious[0])
        stock = N(pid='finite-item', GetType=lambda: 'BandageDressing',
                  GetHierarchyRootPlayer=lambda: carrier if stock_owner[0] == 'carrier' else None,
                  GetQuantity=lambda: stock_quantity[0], IsRuined=lambda: False)
        native_identity = N(HCPartyId=lambda: 'party', HCCargoId=lambda: 'cargo',
                            HCGeneration=lambda: 1, HCRouteId=lambda: 'route:party')
        native_caravan = N(LeftActor=carrier, LeftItem=stock)
        native_row = N(LeaseId='lease', PartyId='party', CargoId='cargo',
                       Generation=1, Id='hc36-first-corridor', RouteId='route:party')
        native_caravan_env = dict(GetGame=lambda: N(IsServer=lambda: True),
            HCSearchSupplyRegistry=N(PersistentId=lambda entity: stock_id[0] if entity is stock else entity.pid),
            HCWorldMaterializer=N(HCIdentity=lambda lease: native_identity if lease == 'lease' else None),
            HCAIPartyIdentity=N(HCValid=lambda value: value is native_identity),
            HCWorldLimits=N(Token=lambda value: bool(value) and len(value) <= 96))
        bind(source, 'HCTradeInventory', native_caravan, ('HCActorId', 'HCItemId'), native_caravan_env)
        # Syntax-only inheritance expansion: the restricted translator has no
        # class hierarchy; native Enforce inherits these HC-35 members/methods.
        inherited_source = caravan_source.replace('    ref HCCaravanCorridor Corridor;',
            '    PlayerBase LeftActor;\n    ItemBase LeftItem;\n    ref HCCaravanCorridor Corridor;')
        inherited_source = inherited_source.replace('HCActorId(true)', 'self.HCActorId(true)')
        inherited_source = inherited_source.replace('HCItemId(true)', 'self.HCItemId(true)')
        bind(inherited_source, 'HCCaravanInventory', native_caravan,
             ('HCLive', 'HCCurrentCaravan', 'HCCargoReceipt', 'HCRemainingQuantity', 'HCInventoryBoundCaravan'), native_caravan_env)
        self.assertTrue(native_caravan.HCInventoryBoundCaravan(native_row))
        self.assertTrue(native_caravan.HCCurrentCaravan(native_row))
        self.assertEqual('retained', native_caravan.HCCargoReceipt(native_row))
        stock_owner[0] = 'player'
        self.assertEqual('lost', native_caravan.HCCargoReceipt(native_row))
        self.assertEqual(0, native_caravan.HCRemainingQuantity(native_row))
        stock_owner[0], stock_quantity[0] = 'carrier', 1
        self.assertEqual('lost', native_caravan.HCCargoReceipt(native_row))
        self.assertEqual(1, native_caravan.HCRemainingQuantity(native_row))
        stock_quantity[0] = 3
        self.assertEqual('unknown', native_caravan.HCCargoReceipt(native_row))
        self.assertEqual(-1, native_caravan.HCRemainingQuantity(native_row))
        stock_quantity[0], stock_id[0] = 2, 'replacement-item'
        self.assertEqual('unknown', native_caravan.HCCargoReceipt(native_row))
        native_row.Generation = 2
        self.assertFalse(native_caravan.HCCurrentCaravan(native_row))
        unconscious[0] = True
        self.assertFalse(native_caravan.HCLive())
        carrier_alive[0], unconscious[0] = False, False
        self.assertFalse(native_caravan.HCLive())

        shipped = N(LeftActor=carrier, RightActor=None, LeftItem=stock, RightItem=None)
        bind(source, 'HCTradeInventory', shipped, ('HCClear',), {})
        addon = (ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAICaravanAdapter.c').read_text()
        addon = addon.replace('HCClear()', 'self.HCClear()')  # syntax-only inherited method binding
        bind(addon, 'HCXAICaravanAdapter', shipped,
             ('HCReady', 'HCRefusal', 'HCBindCaravan', 'HCWalkCaravan', 'HCAtCamp', 'HCFleeObserved'), {})
        self.assertFalse(shipped.HCReady())
        self.assertFalse(shipped.HCBindCaravan(N()))
        self.assertEqual((None, None), (shipped.LeftActor, shipped.LeftItem),
                         'refused provider bind must discard stale native handles')
        self.assertFalse(shipped.HCWalkCaravan(N(), False))
        self.assertFalse(shipped.HCAtCamp(N(), True))
        self.assertFalse(shipped.HCFleeObserved(N()))
        self.assertEqual('CARAVAN_PROVIDER_CALLBACKS_UNVERIFIED', shipped.HCRefusal())


if __name__ == '__main__':
    unittest.main()
