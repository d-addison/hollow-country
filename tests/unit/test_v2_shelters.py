"""One source/lifecycle smoke check; synthetic placement is not DayZ evidence.

RED before implementation, command (also GREEN afterward):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v2_shelters -v
AssertionError: False is not true : missing shelter implementation
GREEN: Ran 1 test in 0.004s / OK.
"""
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_core_lifecycle import NativeArray
from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
TRAVEL = ROOT / 'mods/HollowCountry/scripts/4_World/Travel'


class ShelterSmoke(unittest.TestCase):
    def test_catalog_and_repeated_start_stop(self):
        catalog = TRAVEL / 'HCShelterCatalog.c'
        module = TRAVEL / 'HCShelterModule.c'
        self.assertTrue(catalog.is_file() and module.is_file(), 'missing shelter implementation')
        entries = re.findall(r'Add\("([^"]+)", "([\d. ]+)", "([^"]+)"\);', catalog.read_text())
        self.assertTrue(5 <= len(entries) <= 10, entries)
        self.assertEqual(len(entries), len({row[0] for row in entries}))
        self.assertEqual(len(entries), len({tuple(map(float, row[1].split())) for row in entries}))
        self.assertTrue(all(len(row[2]) > 30 for row in entries))
        logs, deleted = [], []
        game = N(IsServer=lambda: True, GetWorldName=lambda: 'chernarusplus')
        env = dict(GetGame=lambda: game, Print=logs.append, str=str,
                   HCShelterCatalog=N(Count=lambda: len(entries)),
                   HCV2Gates=N(Qualified=lambda gate: False),
                   HCV2Admission=N(Line=lambda *args: 'synthetic admission ' + args[2]))
        source = module.read_text()
        owner = type('SyntheticShelterModule', (), {})
        for method in ('IsEnabled', 'OnStart', 'OnStop'):
            setattr(owner, method, translate(source, method, env, 'HCShelterModule', True))
        state = owner()
        state.m_Started = False
        state.m_Objects = NativeArray()
        state.m_Placed = state.m_Refused = 0

        def synthetic_place(index):
            # Explicit engine seam: three synthetic static handles per shelter.
            for slot in range(3):
                state.m_Objects.Insert((index, slot))
            state.m_Placed += 1

        state.PlaceShelter = synthetic_place
        state.DeleteProp = deleted.append
        off, on = N(EnableTravel=False), N(EnableTravel=True)
        state.OnStart(off)
        self.assertEqual(0, len(logs))
        state.OnStart(on)
        state.OnStart(on)
        self.assertEqual(len(entries) * 3, state.m_Objects.Count())
        self.assertEqual(1, sum('EXP-T5' in line for line in logs))
        self.assertIn(f'[HollowCountry] V2 shelters placed={len(entries)} props={len(entries) * 3} refused=0', logs)
        state.OnStop()
        state.OnStop()
        self.assertEqual(len(entries) * 3, len(deleted))
        self.assertEqual(0, state.m_Objects.Count())
        state.OnStart(on)
        self.assertEqual(len(entries) * 3, state.m_Objects.Count())
        self.assertEqual(0, state.m_Refused)


if __name__ == '__main__':
    unittest.main()
