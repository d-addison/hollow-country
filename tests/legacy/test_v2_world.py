"""One offline smoke: authored cap refusal and corrupt-load control flow.

JSON/files/DTO construction are explicit synthetic native ports. This is neither
an Enforce compile nor evidence of DayZ persistence or simulation behaviour.

2026-11-17 RED, before implementation: AssertionError: False is not true :
missing world implementation HCWorldData.c
GREEN: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_v2_world -v
Ran 1 test; OK.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_event_runtime import translate

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

    def test_w6_append_villages_and_reach_bounded_herb_yield(self):
        from tests.legacy.test_map_layers import translate as authored
        from tests.legacy.test_group_server import EArray
        # Explicit synthetic pre-W6 save: stable identity/order and sentinel
        # positions; JSON validation/native vector conversion are not exercised.
        ids = ('chernogorsk', 'elektrozavodsk', 'berezino', 'svetloyarsk',
               'novodmitrovsk', 'severograd', 'novaya-petrovka', 'vybor',
               'nw-airfield', 'stary-sobor', 'novy-sobor', 'gorka',
               'zelenogorsk', 'pavlovo', 'balota', 'green-mountain',
               'devils-castle', 'tisy', 'komarovo', 'mogilevka',
               'nadezhdino', 'pogorevka', 'polana', 'kamenka', 'staroye')
        prefix = [N(Id=name, Name=name, Position=[i, 0, i])
                  for i, name in enumerate(ids)]
        data = N(Meta=N(SchemaVersion=1), Places=EArray(prefix))
        data.Place = lambda key: next((p for p in data.Places if p.Id == key), None)
        data.InsertPlace = lambda place: data.Places.Insert(place)
        env = dict(HCWorldPlace=N, HCWorldLimits=N(SCHEMA=1))
        authored(DATA.read_text(), 'HCWorldData', env, only=('Town', 'ExtendPlaces'))
        env['HCWorldData'] = N(Valid=lambda value: True,
                              ExtendPlaces=env['ExtendPlaces'])
        authored(STORE.read_text(), 'HCWorldStore', env, only=('Migrate',))
        with self.subTest(part='append-only migration'):
            self.assertTrue(env['Migrate'](data))
            self.assertEqual(30, len(data.Places), 'five villages must append to the existing 25')
            self.assertEqual(prefix, data.Places[:25])
            self.assertEqual([(name, pos) for name, pos in (
                ('bor', '3316.406 0 4070.966'), ('dolina', '11285.17 0 6633.58'),
                ('sosnovka', '2556 0 6307'), ('grishino', '5980 0 10257'),
                ('kabanino', '5300.71 0 8645.9'))],
                [(p.Id, p.Position) for p in data.Places[25:]])
            self.assertTrue(env['Migrate'](data))
            self.assertEqual(30, len(data.Places), 'repeat load must not duplicate villages')
        with self.subTest(part='seasonal herb yield'):
            forage = ROOT / 'mods/HollowCountry/scripts/4_World/Forage/HCForage.c'
            roll = [0]
            from tests.legacy.test_c3_survivalcfg import config_ports
            seasonal = translate(forage.read_text(), 'HCSeasonalType',
                                 dict(config_ports(), Math=N(RandomInt=lambda low, high: roll[0])), member=True)
            for month in range(1, 13):
                yields = []
                for slot in range(3):
                    for roll[0] in range(10):
                        yields.append(seasonal(N(), month, slot))
                expected = 1 if 6 <= month <= 11 else 0
                self.assertEqual(expected, yields.count('Cannabis'))
            import xml.etree.ElementTree as ET
            herb = ET.parse(ROOT / 'mission/hollow-country/ce/types.xml').find("type[@name='Cannabis']")
            self.assertIsNotNone(herb, 'scripted herb needs a packaged CE persistence row')
            self.assertEqual(('0', '0'), (herb.findtext('nominal'), herb.findtext('min')))

    def test_cap_refusal_and_corrupt_load_preserves_files_and_quarantines(self):
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
            refused = []
            env['HCPersistenceDisposition'] = N(HCAdmitStore=lambda name: True,
                HCQuarantine=lambda name, reason: refused.append((name, reason)) or False)
            loaded = translate(STORE.read_text().replace('HCWorldData ', 'HCEventWorldData '), 'Load', env, 'HCWorldStore', member=True)
            self.assertFalse(loaded(store))
            self.assertTrue(store.m_Fault)
            self.assertFalse(store.m_Fresh)
            self.assertIsNone(store.m_Data)
            self.assertEqual('{"synthetic":"preserve me"}', backup.read_text())
            self.assertEqual('{synthetic corrupt JSON', image.read_text())
            self.assertFalse(Path(str(image) + '.rejected').exists())
            self.assertEqual([('world', 'world_parse_or_schema_failure')], refused)



if __name__ == '__main__':
    unittest.main()
