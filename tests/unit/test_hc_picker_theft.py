"""#201 spec/plan/task: opportunistic camp pickup into the existing custody trip.
Explicit synthetic ports execute authored code; no DayZ behaviour is established.
"""
from copy import deepcopy
from types import SimpleNamespace as N
import unittest
from tests.unit.test_hc_pickers_survey import method


class CampCustody(unittest.TestCase):
    def fixture(self, phase='leaving', allowed=True, near=True, saved=True):
        receipts, steps, commits = [], [], []
        crate, home, stock = N(pid='camp-crate'), N(pid='home'), N(pid='same-item')
        io = N(Source=N(pid='survey-source'), Home=home, Item=N(pid='survey-item'),
               Actor=N(pid='actor'), HCTheftCamp=None, HCTheftOwner=None,
               HCLive=lambda: True, HCPartyCurrent=lambda row: True,
               HCTheftNear=lambda crate: near, HCTheftFirstItem=lambda source: stock)
        row = N(Phase=phase, HCTheftDay=0, HCTheftAttempts=0, SourceId='survey-source',
                ItemId='survey-item', CargoOwner='survey-source')
        def checkpoint(): receipts.append(deepcopy(row)); return saved
        trip = N(m_Ready=True, m_Busy=False, m_State=row, m_IO=io,
                 HCCheckpoint=checkpoint, HCStep=lambda: steps.append(io.Item))
        camp = N(LastTheft=0)
        owner = N(Commit=lambda now: commits.append(now) is None)
        run = method('HCScavengeTrip', 'HCTheftPickup', members=('HCCheckpoint', 'HCStep'),
                     HCSearchSupplyRegistry=N(PersistentId=lambda entity: entity.pid),
                     HCCampTheft=N(HCAllowed=lambda *args: allowed, SafeItem=lambda item: True))
        return N(run=run, trip=trip, io=io, row=row, crate=crate, stock=stock,
                 camp=camp, owner=owner, receipts=receipts, steps=steps, commits=commits)

    def call(self, f, now=86400):
        return f.run(f.trip, f.owner, f.camp, f.crate, now, 1)

    def test_bounded_cargo_scan_skips_unsafe_items_without_synthesising_stock(self):
        gun, food = N(pid='gun', safe=False), N(pid='food', safe=True)
        for item in (gun, food): item.IsTakeable = lambda: True
        cargo = N(GetItemCount=lambda: 2, GetItem=lambda index: (gun,food)[index])
        crate = N(GetInventory=lambda: N(GetCargo=lambda: cargo))
        port = N(Survey=N(MaxCargoScan=2))
        run = method('HCScavengeInventory', 'HCTheftFirstItem', fields=('Survey',),
                     HCCampTheft=N(SafeItem=lambda item: item.safe),
                     ItemBase=N(Cast=lambda item:item),
                     HCSearchSupplyRegistry=N(PersistentId=lambda item:item.pid))
        self.assertIs(food, run(port,crate))
        port.Survey.MaxCargoScan = 1
        self.assertIsNone(run(port,crate))

    def test_same_item_source_is_checkpointed_before_existing_trip_steps(self):
        f = self.fixture()
        self.assertEqual('', self.call(f))
        self.assertIs(f.stock, f.io.Item)
        self.assertIs(f.crate, f.io.Source)
        self.assertEqual(['same-item'], [item.pid for item in f.steps])
        self.assertEqual(('camp-crate', 'same-item', 1, 1),
                         (f.receipts[0].SourceId, f.receipts[0].ItemId,
                          f.receipts[0].HCTheftDay, f.receipts[0].HCTheftAttempts))
        self.assertEqual([86400], f.commits)
        self.assertEqual(86400, f.camp.LastTheft)
        self.assertNotEqual('', self.call(f), 'no second pickup while carrying')

    def test_remote_busy_attended_and_uncertain_barriers_never_move(self):
        for kwargs in ({'phase':'returning'}, {'near':False}, {'allowed':False}, {'saved':False}):
            with self.subTest(kwargs=kwargs):
                f = self.fixture(**kwargs)
                self.assertNotEqual('', self.call(f))
                self.assertEqual([], f.steps)

    def test_daily_attempt_budget_survives_new_trip_and_clock_rollback(self):
        f = self.fixture()
        f.row.HCTheftDay, f.row.HCTheftAttempts = 1, 1
        self.assertEqual('THEFT_DAILY_CAP', self.call(f))
        self.assertEqual('THEFT_CLOCK_ROLLBACK', self.call(f, 1))
        self.assertEqual([], f.commits)
        self.assertEqual('', self.call(f, 172800))

    def test_theft_runs_existing_intents_and_quarantines_ambiguous_restart(self):
        from tests.unit.test_hc_scavenge import bind, PICKERS
        for outcome in ('return', 'ambiguous', 'kill', 'restart', 'cancel'):
            with self.subTest(outcome=outcome):
                f = self.fixture()
                f.row.ActorId, f.row.HomeId, f.row.Refusal = 'actor', 'home', ''
                parent, at_home, alive, moves = ['camp-crate'], [False], [True], []
                f.io.HCOwner = lambda: parent[0]
                f.io.HCAtSource = lambda: True
                f.io.HCAtHome = lambda: at_home[0]
                f.io.HCLive = lambda: alive[0]
                f.io.HCWalk = lambda returning: True
                def move(returning, row):
                    # Executed authored acquiring/depositing intent was durable
                    # before this explicit fake native inventory callback.
                    self.assertEqual('unknown', f.receipts[-1].CargoOwner)
                    self.assertEqual('depositing' if returning else 'acquiring', f.receipts[-1].Phase)
                    moves.append((f.io.Item, returning))
                    parent[0] = 'home' if returning else 'actor'
                    if outcome == 'cancel': f.trip.HCLose('CANCELLED_INSIDE_NATIVE')
                    return 3 if outcome == 'ambiguous' else 2
                f.io.HCMove = move
                bind(PICKERS.read_text(), 'HCScavengeTrip', f.trip,
                     ('HCStep', 'HCLose', 'HCRestore', 'HCConfirmedReturn'), {})
                self.assertEqual('', self.call(f))
                self.assertIs(f.stock, moves[0][0])
                if outcome == 'kill': alive[0] = False
                if outcome == 'restart':
                    f.trip.m_State = deepcopy(f.receipts[-1])
                    f.trip.HCRestore()
                at_home[0] = True
                f.trip.HCStep()
                f.trip.HCStep()
                if outcome == 'return':
                    self.assertEqual('home', parent[0])
                    self.assertEqual(2, len(moves))
                    self.assertIs(moves[0][0], moves[1][0])
                    self.assertTrue(f.trip.HCConfirmedReturn())
                else:
                    self.assertEqual('actor', parent[0], 'physical item remains on carrier/body')
                    self.assertEqual(1, len(moves))
                    self.assertIn(f.trip.m_State.Phase, ('lost', 'quarantined'))
                    self.assertFalse(f.trip.HCConfirmedReturn())


class CampVetoes(unittest.TestCase):
    def test_live_group_attendance_observer_veto_and_roster_cap(self):
        from tests.unit.test_debug_map_layers import compile_authored
        from tests.unit.test_admin_test_kit import base_scope
        from tests.unit.test_group_server import EArray
        from tests.unit.test_hc_pickers_survey import ROOT
        people, clear = [], [True]
        owner = N(GroupId=lambda player: player.group)
        game = N(IsServer=lambda: True, GetPlayers=lambda target: target.extend(people))
        camp, crate = N(GroupId='owners', Position=(0,0,0)), N(GetPosition=lambda: (0,0,0))
        config = N(AttendanceRangeMeters=500, ObserverRangeMeters=500, MaxAttendancePlayers=32)
        target = N(s_Config=config, HCEnabled=lambda: True)
        run = compile_authored(ROOT / 'mods/HollowCountry/scripts/4_World/Camps/HCCampTheft.c',
            'HCCampTheft', 'HCAllowed', base_scope(array=EArray, GetGame=lambda: game,
                HCCampModule=N(Get=lambda: owner), PlayerBase=N(Cast=lambda player: player),
                vector=N(DistanceSq=lambda a,b: sum((x-y)**2 for x,y in zip(a,b))),
                HCObserverTransitionGate=N(CanTransition=lambda *args: clear[0])),
            members=('HCEnabled',), fields=('s_Config',), modded=False)
        self.assertTrue(run(target, owner, camp, crate))
        person = N(group='owners', IsAlive=lambda: True, GetIdentity=lambda: 'human',
                   GetPosition=lambda: (500,0,0))
        people.append(person)
        self.assertFalse(run(target, owner, camp, crate), 'attendance includes exact range boundary')
        person.group = 'other'
        self.assertTrue(run(target, owner, camp, crate))
        clear[0] = False
        self.assertFalse(run(target, owner, camp, crate), 'all-player veto includes nonowners')
        clear[0] = True
        people[:] = [person] * 33
        self.assertFalse(run(target, owner, camp, crate), 'oversized roster is never partially trusted')

    def test_custody_hook_checks_pickup_and_home_and_preserves_regular_pickers(self):
        from tests.unit.test_debug_map_layers import compile_authored
        from tests.unit.test_admin_test_kit import base_scope
        from tests.unit.test_hc_pickers_survey import ROOT
        enabled, attended, home_clear, seen = [True], [False], [True], []
        target = N(s_Config=N(ObserverRangeMeters=500), HCEnabled=lambda: enabled[0],
                   HCAllowed=lambda *args: not attended[0])
        port = N(HCTheftCamp=N(), HCTheftOwner=N(), Source=N(), Home=N(GetPosition=lambda: 'home'))
        def observer(at, radius): seen.append((at, radius)); return home_clear[0]
        run = compile_authored(ROOT / 'mods/HollowCountry/scripts/4_World/Camps/HCCampTheft.c',
            'HCCampTheft', 'HCGuard', base_scope(ItemBase=N(Cast=lambda value:value),
                HCObserverTransitionGate=N(CanTransition=observer)),
            members=('HCEnabled','HCAllowed'), fields=('s_Config',), modded=False)
        for phase in ('leaving', 'acquiring'):
            row = N(Phase=phase)
            self.assertTrue(run(target,port,row))
            attended[0] = True
            self.assertFalse(run(target,port,row))
            attended[0] = False
        for phase in ('returning','depositing'):
            row = N(Phase=phase)
            self.assertTrue(run(target,port,row))
            home_clear[0] = False
            self.assertFalse(run(target,port,row))
            home_clear[0] = True
        self.assertEqual([('home',500)] * 4, seen)
        enabled[0] = False
        self.assertFalse(run(target,port,N(Phase='acquiring')))
        port.HCTheftCamp = None
        self.assertTrue(run(target,port,N(Phase='acquiring')), 'ordinary picker custody is unchanged')


    def test_transfer_guard_refuses_without_native_move(self):
        from tests.unit.test_debug_map_layers import compile_authored
        from tests.unit.test_admin_test_kit import base_scope
        from tests.unit.test_hc_picker_walk import WALK
        safe, calls = [False], []
        port, row = N(m_TransferState=None), N(Phase='depositing')
        run = compile_authored(WALK, 'HCXAIPickerWalk', 'HCMove',
            base_scope(this=port, **{'super': N(HCMove=lambda *args: calls.append(args) or 2)},
                       HCCampTheft=N(HCGuard=lambda *args: safe[0])), modded=False)
        self.assertEqual(4, run(port, True, row))
        self.assertEqual([], calls)
        safe[0] = True
        self.assertEqual(2, run(port, True, row))
        self.assertEqual([(True, row)], calls)

    def test_accessibility_rechecks_observation_after_inventory_callbacks(self):
        from tests.unit.test_debug_map_layers import compile_authored
        from tests.unit.test_admin_test_kit import base_scope
        from tests.unit.test_hc_picker_walk import WALK
        clear, calls = [True], []
        row = N(Phase='depositing')
        port = N(m_TransferState=row)
        run = compile_authored(WALK, 'HCXAIPickerWalk', 'HCAccessible',
            base_scope(this=port, HCCampTheft=N(HCGuard=lambda *args: clear[0]),
                       **{'super': N(HCAccessible=lambda cache: calls.append(cache) is None)}),
            modded=False)
        self.assertTrue(run(port, 'home'))
        clear[0] = False  # Synthetic observer arriving inside inventory preflight.
        self.assertFalse(run(port, 'home'))
        self.assertEqual(['home'], calls)
        port.m_TransferState = None
        self.assertTrue(run(port, 'ordinary-cache'))



class ReturnObservation(unittest.TestCase):
    """#208 spec/plan/task: separate identity, defer home transfer, bound wait.

    Explicit synthetic time, positions, observation and native inventory callback;
    execute the authored trip and walk port, never claim engine evidence.
    """
    def fixture(self):
        from tests.unit.test_hc_scavenge import bind, PICKERS
        from tests.unit.test_hc_picker_walk import WALK
        from tests.unit.test_debug_map_layers import compile_authored
        from tests.unit.test_admin_test_kit import base_scope
        clock, clear, at_home, valid = [1000], [True], [False], [True]
        parent, moves, receipts = ['actor'], [], []
        row = N(Phase='returning', ActorId='actor', HomeId='home', SourceId='camp',
                CargoOwner='actor', Refusal='')
        port = N(m_DepositWaitUntil=0, m_TransferState=None, Defaults=N(PartyCooldownSeconds=30),
                 HCPartyCurrent=lambda row: valid[0], HCLive=lambda: True,
                 HCOwner=lambda: parent[0], HCAtSource=lambda: False)
        trip = N(m_State=row, m_IO=port, m_Ready=True, m_Busy=False,
                 HCCheckpoint=lambda: receipts.append(deepcopy(row)) is None)
        bind(PICKERS.read_text(), 'HCScavengeTrip', trip, ('HCStep','HCLose'), {})
        def move(returning, state):
            self.assertEqual('depositing', receipts[-1].Phase)
            self.assertEqual('unknown', receipts[-1].CargoOwner)
            moves.append(returning)
            parent[0] = 'home'
            return 2
        scope = base_scope(this=port, HCScavengeState=lambda: N(Phase=""), HCCampTheft=N(HCGuard=lambda *args: clear[0]),
                           ExpansionStatic=N(GetTimestamp=lambda utc: clock[0]),
                           **{'super': N(HCAtHome=lambda: at_home[0], HCMove=move)})
        port.HCAtHome = lambda: at_home[0]
        port.HCMove = move
        for name in ('HCAtHome', 'HCMove'):
            if 'override ' + ('bool ' if name == 'HCAtHome' else 'int ') + name not in WALK.read_text():
                continue
            fn = compile_authored(WALK, 'HCXAIPickerWalk', name, scope,
                                  fields=('Defaults',), modded=False)
            setattr(port, name, lambda *args, fn=fn: fn(port, *args))
        # Preserve the original bug in the fixture until its override is removed.
        if 'override bool HCPartyCurrent' in WALK.read_text():
            fn = compile_authored(WALK, 'HCXAIPickerWalk', 'HCPartyCurrent',
                base_scope(this=port, HCCampTheft=N(HCGuard=lambda *args: clear[0]),
                           **{'super': N(HCPartyCurrent=lambda row: valid[0])}), modded=False)
            port.HCPartyCurrent = lambda row: fn(port, row)
        return N(trip=trip, row=row, port=port, clock=clock, clear=clear,
                 at_home=at_home, valid=valid, parent=parent, moves=moves, receipts=receipts)

    def test_observer_arrives_during_return_leg_trip_keeps_custody(self):
        f = self.fixture()
        f.clear[0] = False
        f.trip.HCStep()
        self.assertEqual('returning', f.row.Phase)
        self.assertEqual('actor', f.parent[0])
        self.assertEqual([], f.moves)
        self.assertEqual(0, f.port.m_DepositWaitUntil, 'wait starts only at home')
        f.at_home[0] = True
        f.trip.HCStep()
        self.assertEqual('returning', f.row.Phase)
        self.assertEqual(1030, f.port.m_DepositWaitUntil)
        self.assertEqual([], f.receipts, 'no uncertain intent while waiting')

    def test_deposit_completes_once_after_observer_leaves(self):
        f = self.fixture()
        f.at_home[0], f.clear[0] = True, False
        f.trip.HCStep()
        self.assertEqual('returning', f.row.Phase)
        f.clock[0], f.clear[0] = 1029, True
        f.trip.HCStep()
        f.trip.HCStep()
        self.assertEqual(('returned', 'home', 'home'),
                         (f.row.Phase, f.row.CargoOwner, f.parent[0]))
        self.assertEqual([True], f.moves)

    def test_persistent_observer_expires_through_normal_refusal(self):
        f = self.fixture()
        f.at_home[0], f.clear[0] = True, False
        f.trip.HCStep()
        for now in (1001, 1029):
            f.clock[0] = now
            f.trip.HCStep()
            self.assertEqual('returning', f.row.Phase)
        f.clock[0] = 1030
        f.trip.HCStep()
        self.assertEqual(('lost', 'NATIVE_TRANSFER_REFUSED', 'actor'),
                         (f.row.Phase, f.row.Refusal, f.row.CargoOwner))
        self.assertEqual('actor', f.parent[0])
        self.assertEqual([], f.moves)

    def test_real_identity_loss_still_ends_trip_while_observed(self):
        f = self.fixture()
        f.valid[0], f.clear[0] = False, False
        f.trip.HCStep()
        self.assertEqual(('lost', 'PARTY_LEASE_LOST'), (f.row.Phase, f.row.Refusal))
        self.assertEqual([], f.moves)


if __name__ == '__main__': unittest.main()
