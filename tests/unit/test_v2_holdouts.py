"""One synthetic smoke of authored journal/cap policy; no DayZ runtime evidence."""
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.test_group_server import execute_member

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCPickers.c'


class HoldoutsSmoke(unittest.TestCase):
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
