"""One synthetic smoke of authored journal/cap policy; no DayZ runtime evidence."""
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.test_group_server import EArray, execute_member

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCPickers.c'


class HoldoutsSmoke(unittest.TestCase):
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
