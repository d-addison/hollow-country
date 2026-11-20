"""Owner default-on preferences; synthetic ports, never DayZ acceptance.

Profile files are generated from Enforce defaults. Version 1 migrates once;
version 2 false is an operator opt-out, not a missing native verdict.
"""
from pathlib import Path
import unittest
from types import SimpleNamespace as NS

from tests.legacy.test_group_server import EArray, translated_rules
from tests.legacy.test_infected_lod_followups import lod_config
from tests.legacy.test_infected_lod import SERVICE

from tests.legacy.test_hc_status_review_round1 import bind

ROOT = Path(__file__).resolve().parents[2]


class DefaultsOn(unittest.TestCase):
    def test_missing_keys_restore_on_but_explicit_false_survives_native_zero_fill(self):
        from tests.legacy.json_loader_port import json_fields_port
        from tests.legacy.test_infected_w28 import MissingKeyDefaults
        from tests.legacy.test_event_runtime import translate
        restore_lod, logs = MissingKeyDefaults().restore()
        for content, expected in (("{}", True), ('{"EnableVirtualHerds":false}', False)):
            cfg, _ = lod_config()
            cfg.EnableVirtualHerds = False  # explicit synthetic native zero-fill
            restore_lod(cfg, content)
            self.assertEqual(expected, cfg.EnableVirtualHerds)
        text = (ROOT / 'mods/HollowCountry/scripts/3_Game/Groups/HCGroupData.c').read_text()
        text = text.replace('HCGroupSettings settings', 'HCEventHandle settings')
        text = text.replace('HCGroupSettings declared', 'HCEventHandle declared')
        env = dict(HCJsonFields=json_fields_port(), Print=logs.append,
                   HCGroupSettings=translated_rules()['HCGroupSettings'])
        restore_group = translate(text, 'HCRestoreMissingDefaults', env)
        for content, expected in (("{}", True), ('{"ShareDiscovery":false}', False)):
            cfg = env['HCGroupSettings']()
            cfg.ShareDiscovery = False
            restore_group(cfg, content)
            self.assertEqual(expected, cfg.ShareDiscovery)
        loader = (ROOT / 'mods/HollowCountry/scripts/4_World/Groups/HCGroupStore.c').read_text()
        self.assertIn('HCGroupSettingDefaults.HCRestoreMissingDefaults(settings, content)', loader)

    def test_virtual_herds_generated_default_is_on(self):
        cfg, _ = lod_config()
        self.assertTrue(cfg.EnableVirtualHerds, 'virtual herd preference must default on')

    def test_virtual_herd_opt_out_reaches_existing_admission(self):
        # Execute the authored startup with synthetic store/game/admission ports.
        # Even the false preference is logged, and never opens the herd journal.
        for enabled in (True, False):
            cfg, _ = lod_config()
            cfg.EnableVirtualHerds = enabled
            calls = []
            env = dict(GetGame=lambda: NS(IsServer=lambda: True, GetTickTime=lambda: 0),
                       HCInfectedLODConfig=NS(Load=lambda reason: cfg),
                       HCV2Gates=NS(Qualified=lambda gate: False),
                       HCV2Admission=NS(Admitted=lambda value: value,
                           Line=lambda feature, preference, gate, qualified: calls.append((feature, preference)),
                           OnOff=lambda value: 'on' if value else 'off'),
                       Print=lambda line: None, HCInfectedLOD=NS(HCSet=lambda config: None),
                       EArray=EArray, HCLODSightBudget=lambda: NS(),
                       HCInfectedLODExperiment=lambda: NS(HCArm=lambda: False),
                       HCInfectedLODModule=NS(), str=str)
            module = NS(m_Running=False, IsEnabled=lambda settings: True,
                        m_Config=None, m_Herds=False, HCLODResume=lambda: None)
            bind(module, SERVICE, 'HCInfectedLODModule', ['OnStart'], env)
            module.OnStart(NS(EnableDebugSnapshot=False))
            self.assertIn(('VirtualHerds', enabled), calls)
            self.assertTrue(module.m_Running)
            self.assertFalse(module.m_Herds, 'empty seeds never fabricate population')

    def test_group_sharing_generated_default_and_explicit_opt_out(self):
        env = translated_rules()
        cfg = env['HCGroupSettings']()
        self.assertTrue(cfg.ShareDiscovery, 'group discovery preference must default on')
        # KnownPlaces executes real authored rules, with explicit synthetic state.
        place = NS(Id='synthetic-visited')
        group = NS(Members=EArray(['alice', 'bob']))
        env['FindGroup'] = lambda state, uid: group if uid in group.Members else None
        state = NS(Explorers=EArray([NS(Id='alice', PlaceIds=EArray([place.Id]))]))
        catalog = NS(Places=EArray([place]))
        self.assertEqual([place], env['KnownPlaces'](state, cfg, 'bob', catalog))
        self.assertEqual([], env['KnownPlaces'](state, cfg, 'outsider', catalog))
        cfg.ShareDiscovery = False
        self.assertEqual([], env['KnownPlaces'](state, cfg, 'bob', catalog))
        self.assertEqual([place], env['KnownPlaces'](state, cfg, 'alice', catalog))


if __name__ == '__main__':
    unittest.main()
