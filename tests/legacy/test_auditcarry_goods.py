"""Pick-carry spec/plan/tasks: durable receipts -> physical carry -> observed-home unload.

Synthetic authored-handler execution only; native acceptance remains PENDING.
Plan: retain bounded persistent ids before search commit; journal each unload intent;
reuse HCScavengeInventory.HCMove without replacing the primary trip item; never replay.
Tasks covered: cap, ownership, arrival, full crate, death/abort, write failure, restart.
"""
from copy import deepcopy
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_auditpick_harness import WORLD
from tests.legacy.test_group_server import EArray
from tests.legacy.test_hc_scavenge import bind
from tests.legacy.test_map_layers import EStr

CARRY = WORLD / 'auditpick_Carry.c'


class CarryBehavior(unittest.TestCase):
    def rig(self):
        self.assertTrue(CARRY.exists(), 'house goods have no durable carry/deposit handler')
        source = CARRY.read_text().replace('ref array<', 'ref Array<')
        actor, home = N(pid='actor'), N(pid='home')
        stock = N(pid='goods', parent=actor)
        stock.GetHierarchyRootPlayer = lambda: stock.parent
        state = N(Phase=EStr('leaving'), HouseGoods=EArray(), ActorId=EStr('actor'))
        saves, moves, logs = [], [], []
        port = N(Actor=actor, Home=home, Source=N(), Item=N(pid='primary'),
                 Survey=N(RunMaxCarriedHouseGoods=2), Defaults=N(), live=True, current=True,
                 at_home=False, full=False, result=2)
        port.HCLive = lambda: port.live
        port.HCPartyCurrent = lambda row: port.current
        port.HCAtHome = lambda: port.at_home
        trip = N(m_State=state, m_Ready=True, m_Busy=False, fail=False)
        def checkpoint():
            if trip.fail:
                trip.m_Ready = False
                state.Phase = EStr('quarantined')
                return False
            saves.append(deepcopy(state))
            return True
        trip.HCCheckpoint = checkpoint
        def transfer():
            proxy = N()
            def move(returning, row):
                self.assertTrue(trip.m_Busy)
                self.assertEqual('depositing', saves[-1].HouseGoods[0].Phase)
                moves.append(proxy.Item.pid)
                if port.full: return 4
                stock.parent = home
                return port.result
            proxy.HCMove = move
            return proxy
        service = N(Handles=EArray())
        env = dict(HCPickCarryReceipt=lambda: N(ItemId=EStr(''), Phase=EStr('')),
                   HCSearchSupplyRegistry=N(PersistentId=lambda item: item.pid if item else ''),
                   ItemBase=N(Cast=lambda item: item), HCPickCarryInventory=transfer,
                   HCPickRunner=N(HOLD=EStr("HOLD")), Print=logs.append, HCServer=N(HCTickWork=lambda: N(HCTake=lambda n: True)))
        bind(source, 'HCPickCarry', service, ('HCPrepare', 'HCResult', 'HCUnload', 'HCClear'), env)
        return N(service=service, stock=stock, port=port, state=state, trip=trip,
                 saves=saves, moves=moves, logs=logs, actor=actor, home=home)

    def prepare(self, f):
        self.assertTrue(f.service.HCPrepare(f.port, f.trip, f.stock, f.state))
        self.assertEqual('claim', f.saves[-1].HouseGoods[0].Phase)
        return f.service.HCResult(f.port, f.trip, True, f.state)

    def test_carries_same_item_until_observed_home_then_deposits_once(self):
        f = self.rig()
        self.assertTrue(self.prepare(f))
        f.state.Phase = EStr('returning')
        self.assertEqual('', f.service.HCUnload(f.port, f.trip, f.state))
        self.assertIs(f.actor, f.stock.parent)
        self.assertEqual([], f.moves)
        f.port.at_home = True
        self.assertEqual('HOLD', f.service.HCUnload(f.port, f.trip, f.state))
        self.assertIs(f.home, f.stock.parent)
        self.assertEqual('deposited', f.saves[-1].HouseGoods[0].Phase)
        self.assertEqual('', f.service.HCUnload(f.port, f.trip, f.state))
        self.assertEqual(['goods'], f.moves)
        self.assertEqual('primary', f.port.Item.pid)

    def test_full_crate_leaves_goods_on_actor_and_logs_once(self):
        f = self.rig(); self.prepare(f)
        f.port.at_home, f.port.full = True, True
        f.state.Phase = EStr('returning')
        f.service.HCUnload(f.port, f.trip, f.state)
        f.service.HCUnload(f.port, f.trip, f.state)
        self.assertIs(f.actor, f.stock.parent)
        self.assertEqual('retained', f.state.HouseGoods[0].Phase)
        self.assertEqual(1, len(f.logs))
        self.assertIn('runtime=PENDING', f.logs[0])

    def test_missing_stolen_dead_aborted_and_restart_never_move_or_refund(self):
        for reason in ('stolen', 'dead', 'lost', 'quarantined', 'restart'):
            with self.subTest(reason=reason):
                f = self.rig(); self.prepare(f)
                f.state.Phase = EStr('returning'); f.port.at_home = True
                if reason == 'stolen': f.stock.parent = N(pid='player')
                if reason == 'dead': f.port.live = False
                if reason in ('lost', 'quarantined'): f.state.Phase = EStr(reason)
                if reason == 'restart':
                    f.service.HCClear()
                    f.state.Phase = EStr('quarantined')
                f.service.HCUnload(f.port, f.trip, f.state)
                self.assertEqual([], f.moves)
                self.assertIsNot(f.home, f.stock.parent)

    def test_authored_restore_quarantines_receipts_without_rebinding_or_replay(self):
        for phase in ('leaving', 'acquiring', 'returning', 'depositing', 'returned'):
            with self.subTest(phase=phase):
                f = self.rig(); self.prepare(f)
                f.state.Phase = EStr(phase)
                f.state.CargoOwner = EStr('actor')
                f.state.Refusal = EStr('')
                f.service.HCClear()
                bind((WORLD / 'HCPickers.c').read_text(), 'HCScavengeTrip', f.trip,
                     ('HCRestore',), {})
                f.trip.HCRestore()
                self.assertEqual('quarantined', f.state.Phase)
                self.assertEqual('PAIRED_NATIVE_RESTORE_UNPROVEN', f.state.Refusal)
                self.assertEqual('goods', f.state.HouseGoods[0].ItemId)
                f.port.at_home = True
                self.assertEqual('', f.service.HCUnload(f.port, f.trip, f.state))
                self.assertIs(f.actor, f.stock.parent)
                self.assertEqual([], f.moves)

    def test_cap_duplicate_missing_id_failed_commit_and_write_failure(self):
        f = self.rig(); self.prepare(f)
        self.assertFalse(f.service.HCPrepare(f.port, f.trip, f.stock, f.state))
        f.stock.pid = ''
        self.assertFalse(f.service.HCPrepare(f.port, f.trip, f.stock, f.state))
        f.stock.pid = 'second'
        self.assertTrue(f.service.HCPrepare(f.port, f.trip, f.stock, f.state))
        self.assertTrue(f.service.HCResult(f.port, f.trip, False, f.state))
        f.stock.pid = 'third'
        self.assertFalse(f.service.HCPrepare(f.port, f.trip, f.stock, f.state))
        f = self.rig(); f.trip.fail = True
        self.assertFalse(f.service.HCPrepare(f.port, f.trip, f.stock, f.state))
        self.assertEqual([], f.moves)
        f = self.rig(); self.prepare(f)
        f.state.Phase = EStr('returning'); f.port.at_home = True; f.trip.fail = True
        f.service.HCUnload(f.port, f.trip, f.state)
        self.assertEqual([], f.moves)

    def test_ambiguous_move_is_not_replayed(self):
        f = self.rig(); self.prepare(f)
        f.state.Phase = EStr('returning'); f.port.at_home = True; f.port.result = 3
        self.assertEqual('RUN_ABORT_HOUSE_CUSTODY_UNCERTAIN', f.service.HCUnload(f.port, f.trip, f.state))
        self.assertEqual('uncertain', f.state.HouseGoods[0].Phase)
        f.service.HCUnload(f.port, f.trip, f.state)
        self.assertEqual(['goods'], f.moves)


class NativeCarryBehavior(unittest.TestCase):
    """Execute the existing native HCMove through the authored carry proxy, with
    explicit synthetic InventoryLocation and engine ports. No DayZ evidence."""

    rig = CarryBehavior.rig
    prepare = CarryBehavior.prepare

    def native(self, f, preflight=None, during_move=None):
        source = (WORLD / 'HCPickers.c').read_text()
        f.stock.GetHierarchyParent = lambda: f.stock.parent
        f.stock.GetType = lambda: 'SyntheticHouseGoods'
        f.stock.GetQuantity = lambda: 1
        f.stock.IsRuined = lambda: False
        f.stock.IsTakeable = lambda: True
        class Location:
            def __init__(self): self.parent = None
            def GetParent(self): return self.parent
            def CompareLocationOnly(self, other): return self.parent is other.parent
        def current(loc): loc.parent = f.stock.parent; return True
        f.stock.GetInventory = lambda: N(GetCurrentInventoryLocation=current)
        def find(goods, flags, loc):
            loc.parent = f.home
            if preflight: preflight()
            return not f.port.full
        def move(mode, before, target):
            f.moves.append(f.stock.pid)
            if during_move: during_move()
            f.stock.parent = target.parent
            return True
        f.home.GetInventory = lambda: N(FindFreeLocationFor=find, TakeToDst=move)
        f.port.Source.pid = 'source'
        f.port.guard = True
        f.port.HCAccessible = lambda cache: True
        def factory():
            proxy = N(HCLive=lambda: f.port.live)
            env = dict(HCSearchSupplyRegistry=N(PersistentId=lambda entity: entity.pid if entity else ''),
                       InventoryLocation=Location, FindInventoryLocationType=N(CARGO=1),
                       InventoryMode=N(SERVER=1), HCCampTheft=N(HCGuard=lambda port, row: port.guard))
            bind(source, 'HCScavengeInventory', proxy, ('HCOwner', 'HCMove'), env)
            bind(CARRY.read_text(), 'HCPickCarryInventory', proxy,
                 ('HCPartyCurrent', 'HCAtHome', 'HCAccessible'), env)
            return proxy
        f.service.HCUnload.__func__.__globals__['HCPickCarryInventory'] = factory

    def test_native_custody_moves_the_house_item_without_replacing_primary(self):
        f = self.rig(); self.prepare(f); self.native(f)
        f.state.Phase = EStr('returning'); f.port.at_home = True
        self.assertEqual('HOLD', f.service.HCUnload(f.port, f.trip, f.state))
        self.assertIs(f.home, f.stock.parent)
        self.assertEqual('primary', f.port.Item.pid)
        self.assertEqual(['goods'], f.moves)

    def test_preflight_rechecks_visibility_lease_and_ownership(self):
        for change in ('observer', 'lease', 'owner'):
            with self.subTest(change=change):
                f = self.rig(); self.prepare(f)
                def interrupt():
                    if change == 'observer': f.port.guard = False
                    if change == 'lease': f.port.current = False
                    if change == 'owner': f.stock.parent = N(pid='player')
                self.native(f, preflight=interrupt)
                f.state.Phase = EStr('returning'); f.port.at_home = True
                f.service.HCUnload(f.port, f.trip, f.state)
                self.assertEqual([], f.moves)
                self.assertEqual('retained', f.state.HouseGoods[0].Phase)

    def test_cancel_in_native_callback_retains_terminal_evidence(self):
        f = self.rig(); self.prepare(f)
        def cancel():
            f.state.Phase = EStr('quarantined')
            f.trip.HCCheckpoint()
        self.native(f, during_move=cancel)
        f.state.Phase = EStr('returning'); f.port.at_home = True
        self.assertEqual('RUN_ABORT_HOUSE_INTERRUPTED', f.service.HCUnload(f.port, f.trip, f.state))
        self.assertEqual('quarantined', f.saves[-1].Phase)
        self.assertEqual('depositing', f.saves[-1].HouseGoods[0].Phase)
        f.service.HCUnload(f.port, f.trip, f.state)
        self.assertEqual(['goods'], f.moves)


class SearchCarryIntegration(unittest.TestCase):
    def test_search_saves_receipt_before_native_commit_and_records_real_custody(self):
        from tests.legacy.test_auditpick_runs import Rig
        for failed_barrier in (False, True):
            with self.subTest(failed_barrier=failed_barrier):
                f = CarryBehavior().rig()
                rig = Rig(sites=[('house', (10.0, 0.0, 0.0))])
                rig.row.Phase = EStr('leaving')
                rig.row.HouseGoods = EArray()
                f.trip.m_State = rig.row
                f.trip.HCCheckpoint = lambda: not failed_barrier
                rig.port.Actor = f.actor
                f.actor.GetPosition = lambda: rig.port.pos
                rig.port.HCCarryPrepare = lambda goods, row: f.service.HCPrepare(rig.port, f.trip, goods, row)
                rig.port.HCCarryResult = lambda committed, row: f.service.HCResult(rig.port, f.trip, committed, row)
                f.stock.GetType = lambda: EStr('SyntheticHouseGoods')
                f.stock.parent = N(pid='house')
                rig.houses.HCItem = lambda token: f.stock
                commits = []
                def commit(token):
                    self.assertEqual('claim', rig.row.HouseGoods[0].Phase)
                    commits.append(f.stock)
                    f.stock.parent = f.actor
                    return True
                rig.houses.HCCommit = commit
                rig.tick(); rig.port.pos = (10.0, 0.0, 0.0); rig.tick(1)
                rig.tick(rig.survey.RunHouseSearchSeconds)
                self.assertEqual([] if failed_barrier else [f.stock], commits)
                self.assertIsNone(rig.runner.HouseToken)
                if not failed_barrier:
                    self.assertEqual('goods', rig.row.HouseGoods[0].ItemId)
                    self.assertEqual('held', rig.row.HouseGoods[0].Phase)

    def test_carry_cap_is_required_and_validated_in_the_shipped_survey(self):
        from tests.legacy import test_auditpick_harness as h
        self.assertEqual(3, h.shipped_survey().RunMaxCarriedHouseGoods)
        for cap in (0, -1, 17):
            self.assertEqual('PICKER_SURVEY_RUN_CARRY',
                             h.policy().RunRefusal(h.shipped_survey(RunMaxCarriedHouseGoods=cap)))
        source = (WORLD / 'HCPickers.c').read_text()
        self.assertIn('HCJsonFields.Has(text, "RunMaxCarriedHouseGoods")', source)
