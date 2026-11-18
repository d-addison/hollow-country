"""One offline smoke: authored cap refusal and corrupt-load control flow.

JSON/files/DTO construction are explicit synthetic native ports. This is neither
an Enforce compile nor evidence of DayZ persistence or simulation behaviour.

2026-11-17 RED, before implementation: AssertionError: False is not true :
missing world implementation HCWorldData.c
GREEN: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v2_world -v
Ran 1 test; OK.
"""
import json
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'mods/HollowCountry/scripts/3_Game/World/HCWorldData.c'
STORE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCWorldStore.c'


class WorldSmoke(unittest.TestCase):
    def test_perf_budget_yields_without_consuming_the_next_cursor_item(self):
        # Explicit synthetic monotonic seconds; executes the authored guard.
        # Native timing, serialization cost and DayZ scheduling remain unproved.
        path = STORE.parent / 'HCWorkBudget.c'
        self.assertTrue(path.is_file(), 'W5-PERF shared HCWorkBudget missing')
        env = {}
        guard = translate(path.read_text(), 'HCMayContinue', env, 'HCWorkBudget', member=True)
        budget = N(m_Deadline=0.004, m_Limit=2, m_Used=0)
        cursor = 7
        for now in (0.0, 0.003, 0.0035, 0.005):
            if guard(budget, now):
                cursor += 1
        self.assertEqual(9, cursor)
        self.assertEqual(2, budget.m_Used)
        budget.m_Used = 0
        self.assertFalse(guard(budget, 0.004))
        self.assertEqual(0, budget.m_Used)
        self.assertFalse(guard(budget, float('nan')))

    def test_cap_refusal_and_corrupt_load_preserve_backup_and_start_fresh(self):
        self.assertTrue(DATA.is_file(), 'missing world implementation HCWorldData.c')
        logs = []
        env = dict(Print=logs.append, str=str, len=len)
        env['HCWorldLimits'] = N()
        admit = translate(DATA.read_text(), 'Admit', env, 'HCWorldLimits')
        self.assertTrue(admit(23, 24, 'Holdouts'))
        self.assertFalse(admit(24, 24, 'Holdouts'))
        self.assertFalse(admit(25, 24, 'Holdouts'))
        self.assertIn('[HollowCountry] V2 world insert refused collection=Holdouts cap=24', logs)

        with TemporaryDirectory(prefix='hc-synthetic-world-') as tmp:
            image = Path(tmp) / 'world.json'
            backup = Path(tmp) / 'world.json.bak'
            image.write_text('{synthetic corrupt JSON')
            backup.write_text('{"synthetic":"preserve me"}')
            store = N(m_Path=str(image), m_Temp=str(image) + '.tmp',
                      m_Backup=str(backup), m_Data=None, m_KeepBackup=False,
                      m_Fresh=False, Prepare=lambda: True)

            def read_current():
                # Native JSON decoder port; the authored Load chooses recovery.
                try:
                    json.loads(image.read_text())
                except json.JSONDecodeError:
                    return False
                raise AssertionError('fixture must remain corrupt')

            store.ReadCurrent = read_current
            env.update(FileExist=lambda p: Path(p).exists(),
                       HCWorldClock=N(UTC=lambda: 123456),
                       HCWorldData=N(Fresh=lambda now: N(Meta=N(Epoch=now), Facts=[])))
            env.update(Read=lambda p: Path(p).read_text(),
                       CopyFile=lambda a, b: bool(shutil.copyfile(a, b)),
                       DeleteFile=lambda p: os.remove(p) is None)
            preserve = translate(STORE.read_text(), 'Preserve', env, 'HCWorldStore', member=True)
            store.Read = env['Read']
            store.Preserve = lambda f: preserve(store, f)
            loaded = translate(STORE.read_text(), 'Load', env, 'HCWorldStore', member=True)
            self.assertTrue(loaded(store))
            self.assertTrue(store.m_KeepBackup)
            self.assertTrue(store.m_Fresh)
            self.assertEqual(123456, store.m_Data.Meta.Epoch)
            self.assertEqual([], store.m_Data.Facts)
            self.assertEqual('{"synthetic":"preserve me"}', backup.read_text())
            self.assertEqual('{synthetic corrupt JSON', Path(str(image) + '.rejected').read_text())
            self.assertIn('[HollowCountry] V2 world load rejected; fresh world; rejected image kept as world.json.rejected, backup preserved', logs)


if __name__ == '__main__':
    unittest.main()
