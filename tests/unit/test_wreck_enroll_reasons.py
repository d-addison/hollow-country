"""#193 crafting P3s: HCWreckSalvage.CanStart names every refusal, and an enroll failure
separates "table full" from "journal save failed".

Synthetic ports only (translated authored source); never DayZ behaviour. Runtime
acceptance stays pending.

RED (2026-11-19): PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_wreck_enroll_reasons -v
FAILED (failures=2): AssertionError: 'session_changed' != '' ; AssertionError: 'wreck_table_full' != 'storage_unavailable'
GREEN: same command, Ran 4 tests, OK.
"""
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_refusal_report import MethodsTranslator
from tests.unit.test_search_economy_houses import HMap, find_out
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Vehicles/HCWreckSalvage.c'
REASONS = dict(BUSY='busy', SERVICE='service', SALVAGE='salvage_unavailable', CAPACITY='capacity',
               SESSION='session_changed', STORAGE='storage_unavailable', NOTHING='nothing')


class Rows(EArray):
    def Insert(self, item):
        self.append(item)
        return len(self) - 1


class EnrollReasons(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.save_ok = True
        source = SOURCE.read_text().replace('.IndexOf(', '.find(')
        source = re.sub(r'(?<![\w.])Save\(\)', 'self.Save()', source)
        source = re.sub(r'(?<![\w.])Enroll\(', 'self.Enroll(', source)
        source = source.replace('int self.Enroll(', 'int Enroll(')
        game = N(IsServer=lambda: True, GetTime=lambda: 1000)
        policy = N(Reviewed=lambda kind: True, PositionValid=lambda pos: True,
                   Key=lambda kind, pos: kind + str(pos), Budget=lambda key: 2,
                   Allowed=lambda *args: True)
        self.env = dict(Print=self.logs.append, GetGame=lambda: game, find_out=find_out,
                        HCRefusal=N(**REASONS), HCWreckSalvage=policy,
                        HCWreckSalvageRow=lambda: N(), HMap=HMap, EArray=Rows, HCModule=object,
                        tostr=str, SyntheticArray=Rows,
                        HCUnitBudget=lambda: N(), HCWorkBudget=lambda: N(),
                        HCOperationalStatus=lambda: N(HCPublish=lambda *a: None))
        from tests.unit.test_c3_survivalcfg import config_ports
        self.env.update(config_ports())  # Explicit synthetic default profile.
        for code in MethodsTranslator(source, 'HCWreckSalvageModule',
                                      ('Enroll', 'CanStart', 'HCRefuseStart', 'HCRefuseBegin',
                                       'StartRefusal', 'HCEnrollReason')).classes():
            exec(code, self.env)
        module = self.env['HCWreckSalvageModule']()
        module.m_Active = True
        module.m_Busy = False
        module.m_HCStartRefusal = ''
        module.m_HCBeginRefusal = ''
        module.m_HCEnrollRefusal = ''
        module.m_Index = HMap()
        module.m_State = N(Rows=Rows())
        module.Save = lambda: self.save_ok
        self.module = module
        self.player = N(GetIdentity=lambda: object())
        self.target = N(GetObject=lambda: N(GetType=lambda: 'Wreck', GetPosition=lambda: [1, 0, 2]))

    def start(self):
        return self.module.CanStart(self.player, self.target, object())

    def test_missing_player_names_the_session_reason_and_logs_once(self):
        self.assertFalse(self.module.CanStart(None, self.target, object()))
        self.assertEqual('session_changed', self.module.StartRefusal())
        self.assertEqual(1, len([l for l in self.logs if 'reason=session_changed' in l]), self.logs)

    def test_full_table_and_failed_save_are_two_named_reasons(self):
        self.env['HCWreckSalvageModule'].MAX_WRECKS = 0
        self.assertFalse(self.start())
        self.assertEqual('wreck_table_full', self.module.StartRefusal())
        self.assertEqual(0, len(self.module.m_State.Rows), 'a full table adds no row')
        self.env['HCWreckSalvageModule'].MAX_WRECKS = 4096
        self.save_ok = False
        self.assertFalse(self.start())
        self.assertEqual('wreck_journal_save_failed', self.module.StartRefusal())
        self.assertEqual(1, len([l for l in self.logs if 'reason=wreck_table_full' in l]), self.logs)
        self.assertEqual(1, len([l for l in self.logs if 'reason=wreck_journal_save_failed' in l]), self.logs)

    def test_a_good_enroll_clears_the_enroll_cause(self):
        self.save_ok = False
        self.assertFalse(self.start())
        self.save_ok = True
        self.module.m_State.Rows.clear()
        self.assertTrue(self.start())
        self.assertEqual('', self.module.StartRefusal())
        self.assertEqual('', self.module.m_HCEnrollRefusal)

    def test_other_enroll_failures_keep_the_broad_storage_reason(self):
        self.module.Enroll = lambda wreck: -1
        self.assertFalse(self.start())
        self.assertEqual('storage_unavailable', self.module.StartRefusal())


if __name__ == '__main__':
    unittest.main()
