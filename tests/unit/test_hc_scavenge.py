"""HC-34/#144: one item, one custody chain; synthetic ports, never DayZ evidence.

Spec -> plan -> task: HC-34 consumes HC-10/16/18. Leave a funded home,
acquire accessible existing stock, return that identical item, or retain loss.
Provider source/survey admission and paired Hive/journal restore stay pending.
One behavioral test executes authored handlers with explicit stdlib fixtures.
RED: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_scavenge -v
2026-11-18: FAILED (failures=1), "HC-34 interrupted transfer has no single-custody trip barrier".
GREEN: same command, Ran 1 test, OK. No native/provider qualification claimed.
"""
from copy import deepcopy
from pathlib import Path
from types import MethodType, SimpleNamespace as N
import re
import unittest

from tests.unit.test_group_server import EArray, execute_member
from tests.unit.test_map_layers import translate

ROOT = Path(__file__).resolve().parents[2]
PICKERS = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCPickers.c'
ADAPTER = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIScavengeAdapter.c'


def bind(source, owner, target, names, env):
    source = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', source)
    source = re.sub(r'\b(?:protected|override)\s+', '', source)
    translate(source, owner, env, only=names)
    for name in names:
        if name not in env:
            raise AssertionError('missing authored handler ' + owner + '.' + name)
        setattr(target, name, MethodType(env[name], target))


class ScavengeBehavior(unittest.TestCase):
    def test_single_custody_interruption_return_loss_and_restart(self):
        source = PICKERS.read_text()
        self.assertTrue('class HCScavengeTrip' in source,
                      'HC-34 interrupted transfer has no single-custody trip barrier')
        names = ('HCCheckpoint', 'HCLeave', 'HCStep', 'HCLose', 'HCRestore', 'HCConfirmedReturn')

        def fixture(fail_write=0, ambiguous=False, full=False, cancel_during_move=False):
            # A synthetic source/drop, actor and home share ONE physical item.
            state = N(Version=1, Phase='idle', PartyId='', CargoId='', Generation=0,
                      LeaseId='', SourceId='', ActorId='', HomeId='', ItemId='',
                      CargoOwner='', Refusal='')
            physical, saved, moves, walks, writes = ['source'], [], [], [], [0]
            locations, alive, route = ['home'], [True], [True]
            identity = N(HCPartyId=lambda: 'party', HCCargoId=lambda: 'cargo',
                         HCGeneration=lambda: 1, HCRouteId=lambda: 'route:synthetic')
            def save(row):
                writes[0] += 1
                if writes[0] == fail_write: return False
                saved.append(deepcopy(row))
                return True
            def move(returning, row):
                moves.append(returning)
                self.assertEqual('unknown', saved[-1].CargoOwner)
                if cancel_during_move: trip.HCLose('CANCELLED_INSIDE_NATIVE')
                if full: return 4
                physical[0] = 'home' if returning else 'actor'
                return 3 if ambiguous else 2
            io = N(HCRouteReady=lambda i, lease: route[0],
                   HCLive=lambda: alive[0], HCOwner=lambda: physical[0],
                   HCAtSource=lambda: locations[0] == 'source',
                   HCAtHome=lambda: locations[0] == 'home', HCMove=move,
                   HCWalk=lambda returning: walks.append(returning) is None,
                   HCPartyCurrent=lambda row: True)
            trip = N(m_State=state, m_Store=N(Save=save), m_IO=io,
                     m_Ready=True, m_Busy=False, HCLog=lambda: None)
            bind(source, 'HCScavengeTrip', trip, names,
                 dict(str=str, HCAIPartyIdentity=N(HCValid=lambda i: i is identity)))
            return N(trip=trip, state=state, physical=physical, saved=saved,
                     moves=moves, walks=walks, locations=locations, alive=alive,
                     route=route, identity=identity)

        def leave(f):
            return f.trip.HCLeave(f.identity, 'lease', 'source', 'actor', 'home', 'item')

        # Re-entrant/native interruption cannot credit a source and a home.
        f = fixture(ambiguous=True)
        self.assertTrue(leave(f))
        self.assertEqual(('leaving', 'source'), (f.state.Phase, f.state.CargoOwner))
        f.locations[0] = 'source'
        f.trip.HCStep()
        self.assertEqual(('quarantined', 'unknown'), (f.state.Phase, f.state.CargoOwner))
        self.assertEqual('actor', f.physical[0])
        self.assertFalse(f.trip.HCConfirmedReturn())
        f.trip.HCStep()
        self.assertEqual([False], f.moves)
        self.assertEqual('acquiring', f.saved[1].Phase, 'durable intent precedes native move')
        self.assertEqual('unknown', f.saved[1].CargoOwner)
        f.trip.HCRestore()
        self.assertFalse(leave(f), 'restart never replenishes or replays a trip')

        f = fixture(cancel_during_move=True)
        self.assertTrue(leave(f))
        f.locations[0] = 'source'
        f.trip.HCStep()
        self.assertEqual(('quarantined', 'unknown'), (f.state.Phase, f.state.CargoOwner))
        self.assertFalse(f.trip.HCConfirmedReturn())
        f.locations[0] = 'home'
        f.trip.HCStep()
        self.assertEqual([False], f.moves)

        # Same identity arrives at home exactly once; no abstract camp credit.
        f = fixture()
        self.assertTrue(leave(f))
        self.assertFalse(leave(f))
        f.trip.HCStep()  # Not at source: no remote acquisition.
        self.assertEqual([], f.moves)
        f.locations[0] = 'source'
        f.trip.HCStep()
        self.assertEqual(('returning', 'actor', 'actor'),
                         (f.state.Phase, f.state.CargoOwner, f.physical[0]))
        self.assertFalse(f.trip.HCConfirmedReturn())
        f.locations[0] = 'home'
        f.trip.HCStep()
        self.assertTrue(f.trip.HCConfirmedReturn())
        for _ in range(3): f.trip.HCStep()
        self.assertEqual([False, True], f.moves)
        self.assertEqual(('returned', 'home', 'home', 'item'),
                         (f.state.Phase, f.state.CargoOwner, f.physical[0], f.state.ItemId))
        f.physical[0] = 'player'  # Players can steal a completed delivery.
        self.assertFalse(f.trip.HCConfirmedReturn())

        for interruption in ('steal', 'drop', 'kill', 'cancel', 'restart', 'full', 'locked', 'write'):
            with self.subTest(interruption=interruption):
                f = fixture(fail_write=2 if interruption == 'write' else 0,
                            full=interruption == 'full')
                if interruption == 'locked':
                    f.route[0] = False
                    self.assertFalse(leave(f))
                    self.assertEqual([], f.moves)
                    continue
                self.assertTrue(leave(f))
                f.locations[0] = 'source'
                f.trip.HCStep()
                if interruption in ('steal', 'drop'): f.physical[0] = interruption
                if interruption == 'kill': f.alive[0] = False
                if interruption == 'cancel': f.trip.HCLose('CANCELLED')
                if interruption == 'restart':
                    # Explicit synthetic restart from the last verified journal.
                    f.trip.m_State = deepcopy(f.saved[-1])
                    f.trip.HCRestore()
                f.locations[0] = 'home'
                f.trip.HCStep()
                self.assertFalse(f.trip.HCConfirmedReturn())
                self.assertLessEqual(len(f.moves), 1)
                self.assertFalse(leave(f))

        # Run the authored native-inventory handler against explicit synthetic
        # InventoryLocation and native inventory ports (no policy reimplementation).
        parent, actor_pos, blocked, capacity, native_moves = [None], [(0, 0, 0)], [False], [True], []
        class Location:
            def __init__(self): self.parent = None
            def GetParent(self): return self.parent
            def CompareLocationOnly(self, other): return self.parent is other.parent
        actor, source_cache, home = N(pid='actor'), N(pid='source'), N(pid='home')
        parent[0] = source_cache
        item = N(pid='item', GetHierarchyParent=lambda: parent[0],
                 GetHierarchyRootPlayer=lambda: actor if parent[0] is actor else None,
                 IsRuined=lambda: False, IsTakeable=lambda: True,
                 GetType=lambda: 'SyntheticStock', GetQuantity=lambda: 1)
        def current(loc): loc.parent = parent[0]; return True
        item.GetInventory = lambda: N(GetCurrentInventoryLocation=current)
        def inventory(entity):
            def find(stock, flags, loc): loc.parent = entity; return capacity[0]
            def move(mode, before, target):
                native_moves.append((before.parent.pid, target.parent.pid))
                parent[0] = target.parent
                return True
            return N(FindFreeLocationFor=find, TakeToDst=move,
                     IsInventoryLocked=lambda: blocked[0])
        for entity in (actor, source_cache, home):
            entity.GetInventory = lambda entity=entity: inventory(entity)
            entity.GetPosition = lambda: (0, 0, 0)
            entity.GetHierarchyParent = lambda: None
            entity.GetHierarchyRootPlayer = lambda: None
            entity.IsRuined = lambda: False
        actor.GetPosition = lambda: actor_pos[0]
        actor.GetIdentity = lambda: None
        actor.IsAlive = lambda: True
        actor.IsUnconscious = lambda: False
        native_identity = N(HCPartyId=lambda: 'party', HCCargoId=lambda: 'cargo', HCGeneration=lambda: 1, HCRouteId=lambda: 'route:synthetic')
        io = N(Actor=actor, Source=source_cache, Home=home, Item=item, LeaseId='lease', Survey=None,
               Defaults=N(TransferRangeMeters=2.5))
        native_env = dict(GetGame=lambda: N(IsServer=lambda: True), ItemBase=N(Cast=lambda item: item),
            HCSearchSupplyRegistry=N(PersistentId=lambda entity: entity.pid),
            HCWorldMaterializer=N(HCIdentity=lambda lease: native_identity),
            HCAIPartyIdentity=N(HCValid=lambda identity: identity is native_identity),
            HCCampTheft=N(Unlocked=lambda crate: True), HCLockTable=N(CampUnlocked=lambda crate: True),
            InventoryLocation=Location, FindInventoryLocationType=N(CARGO=1), InventoryMode=N(SERVER=1),
            vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))))
        bind(source, 'HCScavengeInventory', io,
             ('HCPartyCurrent', 'HCLive', 'HCOwner', 'HCAtSource', 'HCAtHome',
              'HCAccessible', 'HCMatches', 'HCMove', 'HCRouteReady', 'HCWalk'), native_env)
        row = N(PartyId='party', CargoId='cargo', Generation=1, LeaseId='lease',
                SourceId='source', HomeId='home', ActorId='actor', ItemId='item')
        self.assertFalse(io.HCRouteReady(native_identity, 'lease'))
        self.assertFalse(io.HCWalk(False))
        for mode in ('locked', 'full', 'remote', 'identity'):
            blocked[0] = mode == 'locked'
            capacity[0] = mode != 'full'
            actor_pos[0] = (100, 0, 0) if mode == 'remote' else (0, 0, 0)
            row.ItemId = 'different' if mode == 'identity' else 'item'
            self.assertEqual(4, io.HCMove(False, row))
            self.assertIs(source_cache, parent[0])
        blocked[0], capacity[0], actor_pos[0], row.ItemId = False, True, (0, 0, 0), 'item'
        self.assertEqual([], native_moves)
        self.assertEqual(2, io.HCMove(False, row))
        self.assertIs(actor, parent[0])
        self.assertEqual(2, io.HCMove(True, row))
        self.assertIs(home, parent[0])
        self.assertEqual([('source', 'actor'), ('actor', 'home')], native_moves)
        # Every legacy remote entry point now refuses even valid-looking handles.
        self.assertEqual(4, execute_member(source, 'TakeOne', {}, N(), source_cache, home, 'party', EArray()))
        self.assertEqual(4, execute_member(source, 'V2Visit', {}, N(), source_cache, home, 'party', 0))
        # Review P2: holdout upkeep must not spend finite StockAttempts or save for a refused hop.
        self.assertFalse(execute_member(source, 'V2VisitAvailable', {}, N()))
        holdouts = (ROOT / 'mods/HollowCountry/scripts/4_World/World/HCHoldouts.c').read_text()
        gate = holdouts.index('houses.V2VisitAvailable()')
        self.assertLess(gate, holdouts.index('row.StockAttempts++;'))

        # Adapter waits once for an idle owner, then binds the real walk port.
        # Synthetic lifecycle fixture: no DayZ/Expansion evidence.
        adapter = ADAPTER.read_text()
        worker = N(m_Enabled=False, m_Reported=False, m_Bound=False, m_Port=None)
        env = dict(Print=lambda s: None,
                   HCXAIPickerWalk=lambda: N(HCFinishWalk=lambda: None),
                   HCPickers=N(Get=lambda: None),
                   HCServer=N(HCTickWork=lambda: N(HCTake=lambda cost: True)))
        bind(adapter, 'HCXAIScavengeAdapter', worker, ('Open', 'Step', 'Close'), env)
        worker.Open(N(EnableEncounters=False))
        worker.Step()
        self.assertFalse(worker.m_Enabled)
        worker.Open(N(EnableEncounters=True))
        worker.Step()
        self.assertTrue(worker.m_Reported)
        worker.Close()
        self.assertFalse(worker.m_Enabled)
        for forbidden in ('SetPosition(', 'CreateObject', 'CreateInInventory', 'OverrideTargetPosition('):
            self.assertNotIn(forbidden, adapter)


if __name__ == '__main__': unittest.main()
