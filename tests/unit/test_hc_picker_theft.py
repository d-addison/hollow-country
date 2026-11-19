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


    def test_expansion_hook_keeps_native_identity_failure_and_checks_camp_guard(self):
        from tests.unit.test_debug_map_layers import compile_authored
        from tests.unit.test_admin_test_kit import base_scope
        from tests.unit.test_hc_picker_walk import WALK
        native_valid, safe, calls = [False], [True], []
        port, row = N(), N()
        def guard(port, row): calls.append(row); return safe[0]
        run = compile_authored(WALK, 'HCXAIPickerWalk', 'HCPartyCurrent',
            base_scope(this=port, **{'super': N(HCPartyCurrent=lambda row: native_valid[0])},
                       HCCampTheft=N(HCGuard=guard)), modded=False)
        self.assertFalse(run(port,row))
        self.assertEqual([], calls)
        native_valid[0] = True
        self.assertTrue(run(port,row))
        safe[0] = False
        self.assertFalse(run(port,row))
        self.assertEqual([row,row], calls)


if __name__ == '__main__': unittest.main()
