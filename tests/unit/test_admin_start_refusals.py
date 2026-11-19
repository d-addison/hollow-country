"""#160 burn-down: HCAdminModule.OnStart refusals carry a stable reason.

Explicit synthetic ports only (store, file, game); the authored OnStart runs through the
restricted statement adapter. Offline tests never establish DayZ behaviour.

RED: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_admin_start_refusals -v
AssertionError: Lists differ: [('refused', 'admin_allowlist_store_recovery_required')] != [] (and 3 sibling failures=4)
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

from tests.unit.test_admin_test_kit import compile_authored, base_scope
from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c'


class Arr(EArray):
    def Clear(self): self.clear()


class OnStartRefusals(unittest.TestCase):
    def build(self, can_open=True, exists=True, load=True, save=True, admins=(EStr('a1'),), loaded_null=False):
        self.status, self.printed = [], []
        allowlist = N(PlainIds=Arr(list(admins)))
        self.allowlist = allowlist

        def load_into(path, limit, target):
            return load

        store = N(CanOpen=lambda path: can_open, Load=load_into, Save=lambda path, data, limit: save)
        game = N(IsServer=lambda: True)
        env = base_scope(GetGame=lambda: game, HCV2ThreatStore=store, FileExist=lambda path: exists,
                         HCAdminAllowlist=lambda: allowlist, HCV2Admission=N(Line=lambda *args: 'admission'),
                         Print=lambda line: self.printed.append(line),
                         DayZGame=N(Event_OnRPC=N(Insert=lambda fn: None)), HCReceive=lambda *args: None)
        source = (MODULE.read_text().replace('HCV2ThreatStore<HCAdminAllowlist>', 'HCV2ThreatStore')
                  .replace('array<string> seen = new array<string>;', 'seen = Arr();')
                  .replace('new array<ref HCAdminDeniedPeer>', 'Arr()')
                  .replace('new array<float>', 'Arr()').replace('new array<int>', 'Arr()')
                  .replace('new array<PlayerIdentity>', 'Arr()').replace('new array<Man>', 'Arr()'))
        env['Arr'] = Arr
        env['PATH'] = 'synthetic:admins.json'
        with patch.object(Path, 'read_text', return_value=source):
            start = compile_authored(MODULE, 'HCAdminModule', 'OnStart', env, ('HCStartRefused', 'IsEnabled'),
                                     modded=False, native_strings=EStr)
        owner = N(m_Running=False, m_Printed=False, m_Admins=None if loaded_null else allowlist,
                  m_Status=N(HCPublish=lambda state, reason: self.status.append((state, reason))),
                  IsEnabled=lambda settings: True, m_DebugEnabled=False,
                  m_Denied=None, m_CommandAt=None, m_SnapshotAt=None, m_Tickets=None,
                  m_Identities=None, m_Players=None)
        owner.HCStartRefused = lambda reason: (self.status.append(('refused', reason)),
                                               self.printed.append('[HC Admin] allowlist refused: reason=' + reason))
        self.owner = owner
        settings = N(EnableAdminMap=True, EnableDebugSnapshot=False)
        start(owner, settings)

    def assertRefused(self, reason):
        self.assertEqual([('refused', reason)], self.status)
        self.assertFalse(self.owner.m_Running)
        self.assertTrue(any('reason=' + reason in line for line in self.printed))

    def test_store_recovery_refusal_names_its_reason(self):
        self.build(can_open=False)
        self.assertRefused('admin_allowlist_store_recovery_required')

    def test_unreadable_allowlist_names_its_reason(self):
        self.build(load=False)
        self.assertRefused('admin_allowlist_load_failed')

    def test_first_run_template_save_failure_names_its_reason(self):
        self.build(exists=False, save=False)
        self.assertRefused('admin_allowlist_save_failed')

    def test_empty_loaded_list_names_its_reason(self):
        self.build(loaded_null=True, exists=True, load=True)
        self.assertRefused('admin_allowlist_missing_after_load')

    def test_valid_allowlist_publishes_ready_and_runs(self):
        self.build()
        self.assertEqual([('ready', 'allowlist_loaded_native_acceptance_pending')], self.status)
        self.assertTrue(self.owner.m_Running)
        self.assertFalse(any('refused' in line for line in self.printed))


if __name__ == '__main__':
    unittest.main()
