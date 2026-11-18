"""Synthetic authored-policy smokes; no DayZ runtime evidence.

Fix-round RED: missing day-0 holdout transition (HCAdvanceOccupancy absent).
GREEN: test_day_zero_occupancy_and_post_raid_world_upsert ... ok.
The added smoke executes occupancy, Raid, PublishState and UpsertHoldout with
explicit synthetic clock/cache/validation/transport collaborators.
"""
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.test_group_server import EArray, execute_member

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCPickers.c'


class HoldoutsSmoke(unittest.TestCase):
    def publisher_fixture(self):
        """Explicit synthetic clock, arrays, DTOs and map; execute authored policy."""
        from tests.unit.test_map_layers import translate
        class Rows(EArray):
            def Set(self, index, value): self[index] = value
        class Reports(dict):
            def Get(self, key): return self.get(key, '')
            def Set(self, key, value): self[key] = value
        clock, logs, lights = [1000000], [], []
        row = N(Ledger=N(Id='synthetic-house', PlaceId='synthetic-place',
                        FactionId='locals', HouseClass='Land_House_1W01',
                        HousePos=[100, 0, 200], CacheRef='', Occupants=1,
                        State='OCCUPIED', Since=clock[0], ReoccupyAfter=0,
                        Routine='SHELTER'), Cache=N(EntityRef='synthetic-cache'),
                Published=False)
        data = N(Holdouts=Rows(), Facts=Rows(), Meta=N(Epoch=1),
                 HoldoutValid=lambda value: value.Occupants <= 3,
                 Place=lambda value: N(Id='synthetic-place')
                 if value in ('synthetic-place', 'Synthetic Place') else None)
        data.InsertHoldout = lambda value: len(data.Holdouts) < 24 and data.Holdouts.Insert(value) is None
        data.AppendFact = lambda value: data.Facts.Insert(value) is None
        world = N(m_Running=True, m_Data=data, m_Dirty=False, m_HoldoutRefusal='')
        env = dict(HCWorldHoldout=N, HCWorldFact=N,
                   HCWorldLimits=N(OCCUPIED=6, HOLDOUTS=24, FACT_LIFETIME=604800,
                                   Token=lambda value: bool(value)),
                   HCWorldClock=N(UTC=lambda: clock[0]), Print=logs.append,
                   HCWorldModule=N(Get=lambda: world if world.m_Running else None))
        world_env = dict(env)
        translate((SOURCE.parent / 'HCWorldModule.c').read_text(), 'HCWorldModule',
                  world_env, only=('UpsertHoldout', 'HoldoutRefusal', 'AddFact', 'AddHoldoutFact'))
        for name in ('UpsertHoldout', 'HoldoutRefusal', 'AddFact', 'AddHoldoutFact'):
            if name in world_env:
                setattr(world, name, lambda *a, name=name: world_env[name](world, *a))
        module = N(m_Dirty=False, m_PublishRefusals=Reports(),
                   HCSyncLights=lambda: lights.append('snapshot'))
        # Existing adapter does not discover native lowercase map<T, U> fields.
        env['m_PublishRefusals'] = module.m_PublishRefusals
        translate((SOURCE.parent / 'HCHoldouts.c').read_text(), 'HCHoldouts', env,
                  only=('PublishState',))
        module.PublishState = lambda value: env['PublishState'](module, value)
        return module, row, world, clock, logs, lights

    def test_publish_refusal_does_not_dirty_store_and_logs_only_reason_changes(self):
        module, row, world, clock, logs, lights = self.publisher_fixture()
        for holdout_id in ('synthetic-house', 'synthetic-other-house'):
            row.Ledger.Id = holdout_id
            row.Ledger.Occupants = 4  # Explicit invalid row; world refuses it.
            for _ in range(3):
                module.PublishState(row)
                self.assertFalse(module.m_Dirty, 'refused publish must not rewrite holdouts.json')
                self.assertFalse(row.Published)
            refusals = [line for line in logs if 'publish refused id=' + holdout_id + ' ' in line]
            self.assertEqual(1, len(refusals))
            self.assertIn('reason=invalid holdout', refusals[0])
        row.Ledger.Occupants = 1
        world.m_Data.Holdouts.extend(N(Id='synthetic-occupied-' + str(i), Occupants=1)
                                    for i in range(6))
        for _ in range(3):
            module.PublishState(row)
        self.assertFalse(module.m_Dirty)
        self.assertEqual(1, sum('reason=occupied cap' in line for line in logs))
        self.assertEqual([], lights)
        world.m_Data.Holdouts.clear()
        world.m_Data.Holdouts.extend(N(Id='synthetic-dormant-' + str(i), Occupants=0)
                                    for i in range(24))
        for _ in range(3):
            module.PublishState(row)
        self.assertFalse(module.m_Dirty)
        self.assertEqual(24, len(world.m_Data.Holdouts))
        self.assertEqual(1, sum('reason=catalog cap' in line for line in logs))
        world.m_Data.Holdouts.clear()
        module.PublishState(row)
        self.assertTrue(row.Published)
        self.assertTrue(module.m_Dirty)
        module.m_Dirty = False
        module.PublishState(row)
        self.assertFalse(module.m_Dirty, 'already-published row has no persistence change')

    def test_restart_republish_preserves_fact_expiry_and_repairs_original_time(self):
        for state, severity in (('RAIDED', 2), ('ABANDONED', 1)):
            with self.subTest(state=state):
                module, row, world, clock, logs, lights = self.publisher_fixture()
                row.Ledger.State, row.Ledger.Occupants = state, 0
                row.Ledger.PlaceId = 'Synthetic Place'  # Existing name-or-ID contract.
                module.PublishState(row)
                self.assertEqual(1, len(world.m_Data.Facts))
                fact = world.m_Data.Facts[0]
                self.assertEqual('synthetic-place', fact.PlaceId)
                self.assertEqual((state, severity, clock[0], clock[0] + 604800),
                                 (fact.Kind, fact.Severity, fact.At, fact.Expires))
                for elapsed in (60, 3600, 604800, 700000):
                    clock[0] = row.Ledger.Since + elapsed
                    row.Published = False  # OnStart deliberately forces re-publication.
                    world.m_Dirty = False
                    module.PublishState(row)
                    self.assertEqual([fact], world.m_Data.Facts, 'restart must not append a fact')
                    self.assertEqual(row.Ledger.Since + 604800, fact.Expires)
                world.m_Data.Facts.clear()
                row.Published = False
                module.PublishState(row)
                self.assertEqual([], world.m_Data.Facts, 'expired transition must stay expired')
                clock[0] = row.Ledger.Since + 120
                module.PublishState(row)  # Missing world write after a crash: repair it.
                self.assertEqual(1, len(world.m_Data.Facts))
                self.assertEqual((row.Ledger.Since, row.Ledger.Since + 604800),
                                 (world.m_Data.Facts[0].At, world.m_Data.Facts[0].Expires))
                # Legacy facts used publication time; retain their existing expiry too.
                world.m_Data.Facts[0].At += 30
                world.m_Data.Facts[0].Expires += 30
                row.Published = False
                clock[0] += 60
                module.PublishState(row)
                self.assertEqual(1, len(world.m_Data.Facts))
                self.assertEqual(row.Ledger.Since + 604830, world.m_Data.Facts[0].Expires)
                # An actual later transition still adds a new fact.
                row.Ledger.Since = clock[0]
                module.PublishState(row)
                self.assertEqual(2, len(world.m_Data.Facts))

    def test_day_zero_occupancy_and_post_raid_world_upsert(self):
        # Explicit synthetic cache, clock, validation and transport ports.
        # Authored transitions and upsert execute; this is no engine evidence.
        from tests.unit.test_map_layers import translate
        world_source = (SOURCE.parent / 'HCWorldModule.c').read_text()
        holdouts_source = (SOURCE.parent / 'HCHoldouts.c').read_text()
        clock = [1000000]
        row = N(Ledger=N(Id='synthetic-house', PlaceId='synthetic-place',
                        FactionId='locals', HouseClass='Land_House_1W01',
                        HousePos=[100, 0, 200], CacheRef='', Occupants=0,
                        State='DORMANT', Since=clock[0], ReoccupyAfter=0,
                        Routine=''), Cache=N(EntityRef='synthetic-cache', Phase=2),
                Published=False, Contents=EArray())
        class Rows(EArray):
            def Set(self, index, value): self[index] = value
        ledger = N(Holdouts=Rows(), HoldoutValid=lambda value: value.Occupants <= 3,
                   OccupiedCount=lambda: sum(r.Occupants > 0 for r in ledger.Holdouts))
        ledger.InsertHoldout = lambda value: ledger.Holdouts.Insert(value) is None
        world = N(m_Running=True, m_Data=ledger, m_Dirty=False, AddHoldoutFact=lambda *a: True)
        env = dict(HCWorldHoldout=N, HCWorldLimits=N(OCCUPIED=6, HOLDOUTS=24),
                   HCWorldModule=N(Get=lambda: world),
                   HCEscalationClock=N(Day=lambda: 0),
                   HCWorldClock=N(UTC=lambda: clock[0]), Print=lambda text: None)
        transition_env = dict(env)
        translate(holdouts_source, 'HCHoldouts', transition_env, only=('HCAdvanceOccupancy',))
        self.assertIn('HCAdvanceOccupancy', transition_env, 'missing day-0 holdout transition')
        upsert_env = dict(env)
        translate(world_source, 'HCWorldModule', upsert_env, only=('UpsertHoldout',))
        world.UpsertHoldout = lambda value: upsert_env['UpsertHoldout'](world, value)
        translate(holdouts_source, 'HCHoldouts', env, only=('PublishState',))
        module = N(m_State=N(Rows=Rows([row])), m_Dirty=False,
                   m_PublishRefusals=N(Set=lambda *a: None),
                   Occupied=lambda: row.Ledger.Occupants > 0,
                   SiteAvailable=lambda value: True, Cache=lambda index: object(),
                   HCSyncLights=lambda: None, SaveChanged=lambda: True)
        env['m_PublishRefusals'] = module.m_PublishRefusals
        module.PublishState = lambda value: env['PublishState'](module, value)
        self.assertEqual(0, env['HCEscalationClock'].Day())
        self.assertTrue(transition_env['HCAdvanceOccupancy'](module, 0, clock[0]))
        module.PublishState(row)
        self.assertEqual(('OCCUPIED', 1),
                         (ledger.Holdouts[0].State, ledger.Holdouts[0].Occupants))
        raid_env = dict(env)
        translate(holdouts_source, 'HCHoldouts', raid_env, only=('Raid',))
        raid_env['Raid'](module, 0)
        self.assertEqual(('RAIDED', 0),
                         (ledger.Holdouts[0].State, ledger.Holdouts[0].Occupants))
        self.assertFalse(transition_env['HCAdvanceOccupancy'](module, 0, clock[0] + 604799))
        self.assertTrue(transition_env['HCAdvanceOccupancy'](module, 0, clock[0] + 604800))
        module.PublishState(row)
        self.assertEqual(1, len(ledger.Holdouts))
        self.assertEqual(('OCCUPIED', 1),
                         (ledger.Holdouts[0].State, ledger.Holdouts[0].Occupants))
        self.assertIsNot(row.Ledger, ledger.Holdouts[0])

    def test_zero_move_charge_locked_crate_and_player_deposit(self):
        # Explicit synthetic inventory/config adapters; never engine evidence.
        source = SOURCE.read_text()
        for phase in (0, 3, 4):
            self.assertEqual(2, execute_member(source, 'ChargeAfterVisit', {}, N(), 2, phase))
        self.assertEqual(3, execute_member(source, 'ChargeAfterVisit', {}, N(), 2, 2))
        theft = (SOURCE.parent.parent / 'Camps/HCCampTheft.c').read_text()
        # Native string-array declaration uses the existing DTO/array scaffolding.
        theft = theft.replace('TStringArray slots =', 'HCGroupArray slots =')
        attachments = [0]
        slots = EArray()
        game = N(ConfigIsExisting=lambda path: True, ConfigGetType=lambda path: 3,
                 ConfigGetTextArray=lambda path, output: output.extend(slots))
        inventory = N(AttachmentCount=lambda: attachments[0])
        crate = N(GetType=lambda: 'WoodenCrate', GetInventory=lambda: inventory)
        env = {'GetGame': lambda: game, 'TStringArray': EArray, 'CT_ARRAY': 3}
        self.assertTrue(execute_member(theft, 'Unlocked', env.copy(), N(), crate))
        attachments[0] = 1  # Unknown/lock attachment always refuses.
        self.assertFalse(execute_member(theft, 'Unlocked', env.copy(), N(), crate))
        attachments[0] = 0
        slots.Insert('CombinationLock')  # Modified config cannot be classified.
        self.assertFalse(execute_member(theft, 'Unlocked', env.copy(), N(), crate))
        drops = (SOURCE.parent / 'HCDeadDrops.c').read_text()
        recorded = EArray(['synthetic-house-item'])
        self.assertTrue(execute_member(drops, 'MayWithdraw', {}, N(), recorded, 'synthetic-house-item'))
        self.assertFalse(execute_member(drops, 'MayWithdraw', {}, N(), recorded, 'synthetic-player-item'))

    def test_picker_moves_only_through_journal_and_six_daily_attempts(self):
        self.assertTrue(SOURCE.is_file(), 'missing authored picker journal implementation')
        source = SOURCE.read_text()
        events = []
        phases = []
        fail = [None]
        row = N(Phase=0)
        def set_phase(index, phase):
            phases.append(phase)
            row.Phase = phase
        journal = N(Healthy=lambda: True, Row=lambda index: row,
                    SetPhase=set_phase,
                    Write=lambda index, kind, actor, phase:
                        events.append(kind) is None and kind != fail[0])
        registry = N(Transfer=lambda *args: events.append('native_move') or 2)
        receiver = N(m_Journal=journal, m_Registry=registry)
        for failure, expected in ((None, 2), ('claim', 3), ('attempt', 3), ('result', 3)):
            events.clear()
            phases.clear()
            fail[0] = failure
            row.Phase = 0
            phase = execute_member(source, 'CommitMove', {}, receiver, N(), N(), 'synthetic-picker', 0)
            self.assertEqual(expected, phase)
            self.assertEqual(1, phases[0])
            self.assertEqual(expected, phases[-1])
            if failure in ('claim', 'attempt'):
                self.assertNotIn('native_move', events)
            else:
                self.assertEqual(['claim', 'attempt', 'native_move', 'result'], events)
            before = list(events)
            self.assertEqual(expected, execute_member(source, 'CommitMove', {}, receiver, N(), N(), 'synthetic-picker', 0))
            self.assertEqual(before, events)
        for used in range(8):
            allowed = execute_member(source, 'MayVisit', {}, N(), used, 12, 12, False)
            self.assertEqual(used < 6, allowed)
        self.assertFalse(execute_member(source, 'MayVisit', {}, N(), 0, 12, 12, True))
        self.assertFalse(execute_member(source, 'MayVisit', {}, N(), 0, 13, 12, False))
        for forbidden in ('CreateObject', 'CreateInInventory', 'CreateEntityInCargo'):
            self.assertNotIn(forbidden, source)
