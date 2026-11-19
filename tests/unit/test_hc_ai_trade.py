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
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as N
import json
import unittest

from tests.unit.test_hc_scavenge import bind
from tests.unit.test_map_layers import EStr

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
                     'interrupt', 'death', 'surrender', 'steal', 'lease', 'timeout', 'rollback_timeout'):
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


if __name__ == '__main__':
    unittest.main()
