"""Core lifecycle wiring for the bounded ecology observation service (#34).

Synthetic ports only: this proves the authored module calls the reviewed
Start/Tick/Stop seam and releases the pre-start cohort when it will not run.
It does not establish native registration, pathing or persistence behavior.
"""
import re
import unittest
from types import SimpleNamespace
from tests.unit.test_ecology_runtime import ROOT, environment, translated

SOURCE = ROOT / "4_World/Ecology/HCEcologyRuntimeModule.c"
# The shared syntax-only translator recognises local declarations only for the
# HCEvent* spelling. Rename the TYPE token of every `HCOperational* name =`
# declaration; call sites such as HCOperationalContributors.X() stay authored.
_LOCAL_OPERATIONAL_TYPE = re.compile(r"\bHCOperational(\w+)(\s+\w+\s*=)")


def translator_spelling(text):
    adapted, count = _LOCAL_OPERATIONAL_TYPE.subn(r"HCEventOperational\1\2", text)
    if count < 1:
        raise AssertionError("fixture found no HCOperational* local declaration to spell for the translator")
    return adapted


class EcologyModuleBehavior(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.e = environment()
        self.e["HCEcologyDisposition"] = SimpleNamespace(Report=lambda: None)
        # Synthetic HC-48 boot receipt port (#149); tests/unit/test_hc48_habitat_boot.py asserts the calls.
        self.e["HCEcologyNative"] = SimpleNamespace(HCHabitatRefusals=lambda state: None)
        self.settings = self.e["HCEcologyRuntimeSettings"]()
        self.game = SimpleNamespace(IsServer=lambda: True, GetWorldName=lambda: "chernarusplus", GetTime=lambda: 4321)
        self.e["GetGame"] = lambda: self.game
        self.e["HCEcologyRuntimeIO"] = SimpleNamespace(Settings=lambda: self.settings)
        self.started = True
        self.e["HCEcologyRuntime"] = SimpleNamespace(
            CloseCollection=lambda: self.calls.append("close"),
            Start=lambda s, w, session: self.calls.append(("start", s, w, session)) or self.started,
            Tick=lambda now: self.calls.append(("tick", now)),
            Stop=lambda: self.calls.append("stop"))
        self.migration_calls = []
        self.e['HCEcologyMigration'] = SimpleNamespace(
            Start=lambda world: self.migration_calls.append(('start', world)),
            Stop=lambda: self.migration_calls.append('stop'))
        self.wildlife_calls = []  # Synthetic HC-15 observation collaborator.
        self.e['HCWildlifeObservation'] = SimpleNamespace(
            HCStart=lambda enabled: self.wildlife_calls.append(('start', enabled)),
            HCTick=lambda now: self.wildlife_calls.append(('tick', now)),
            HCStop=lambda: self.wildlife_calls.append('stop'))
        # Synthetic HC-49 carcass-scene collaborator; the static accessor is a namespace for the translator.
        self.e['hc49_static'] = SimpleNamespace(instance=None)
        status = SimpleNamespace(HCPublish=lambda *args: None)
        wildlife_status = SimpleNamespace(HCPublish=lambda *args: None)
        self.e['HCWildlifeScenes'] = lambda: SimpleNamespace(
            HCOpen=lambda enabled: None, HCStatus=lambda: wildlife_status, HCActive=lambda: False,
            HCStep=lambda *args: None, HCClose=lambda: None)
        self.e['HCGroupClock'] = SimpleNamespace(Utc=lambda: 1577836900)
        # Explicit synthetic HC-25 registration port. The wildlife behavioral
        # test executes real HC-25 capture; this legacy fixture has no registry.
        self.e['HCOperationalContributors'] = SimpleNamespace(HCRegisterOwner=lambda name: None)
        self.source = translator_spelling(SOURCE.read_text()).replace('s_Instance', 'hc49_static.instance')
        self.module = SimpleNamespace(m_Settings=None, m_Started=False, Session=lambda: "s20261117-010203-77",
                                      m_WildlifeScenes=None, m_Status=status, m_WildlifeStatus=wildlife_status)
        self.module.HCObserveWildlife = lambda requested: self.method('HCObserveWildlife')(self.module, requested)

    def method(self, name):
        return translated(self.source, name, self.e, "HCEcologyRuntimeModule", True)

    def test_enabled_settings_admit_the_module_without_closing_collection(self):
        self.assertTrue(self.method("IsEnabled")(self.module, None))
        self.assertIs(self.settings, self.module.m_Settings)
        self.assertEqual([], self.calls)

    def test_disabled_or_unreadable_settings_release_the_prestart_cohort(self):
        self.settings.Enabled = False
        self.assertFalse(self.method("IsEnabled")(self.module, None))
        self.settings = None
        self.assertFalse(self.method("IsEnabled")(self.module, None))
        self.assertEqual(["close", "close"], self.calls)

    def test_translator_spelling_changes_only_local_type_tokens(self):
        self.assertIn("HCEventOperationalOwner wildlifeOwner =", self.source)
        self.assertIn("HCOperationalContributors.HCRegisterOwner(", self.source)
        self.assertEqual("x = HCOperationalContributors.A();",
                         translator_spelling("HCOperationalOwner o = 1;\nx = HCOperationalContributors.A();").split("\n")[1])
        with self.assertRaises(AssertionError):
            translator_spelling("no declaration here")

    def test_client_never_admits(self):
        self.game.IsServer = lambda: False
        self.assertFalse(self.method("IsEnabled")(self.module, None))

    def test_start_passes_loaded_settings_world_and_fresh_session(self):
        self.module.m_Settings = self.settings
        self.method("OnStart")(self.module, None)
        self.assertEqual([("start", self.settings, "chernarusplus", "s20261117-010203-77")], self.calls)
        self.assertTrue(self.module.m_Started)

    def test_migration_uses_existing_module_lifecycle_after_observation_admission(self):
        self.module.m_Settings = self.settings
        self.method("OnStart")(self.module, None)
        self.assertEqual([('start', 'chernarusplus')], self.migration_calls)
        self.method("OnStop")(self.module)
        self.assertEqual([('start', 'chernarusplus'), 'stop'], self.migration_calls)

    def test_failed_observation_start_never_opens_migration_state(self):
        self.started = False
        self.method("OnStart")(self.module, None)
        self.assertEqual([], self.migration_calls)

    def test_rejected_start_closes_collection(self):
        self.started = False
        self.module.m_Settings = self.settings
        self.method("OnStart")(self.module, None)
        self.assertEqual("close", self.calls[-1])
        self.assertFalse(self.module.m_Started)

    def test_tick_uses_engine_milliseconds_and_stop_stops(self):
        self.method("OnTick")(self.module, 1.0)
        self.method("OnStop")(self.module)
        self.assertEqual([("tick", 4321), "stop"], self.calls)
        self.assertFalse(self.module.m_Started)

    def test_session_token_is_valid_and_registered_through_the_core_registry(self):
        token = re.search(r'string SessionToken\([^)]*\)\s*\{([\s\S]*?)\n\s*\}', self.source)
        self.assertIsNotNone(token)
        self.assertIn("GetYearMonthDayUTC(", self.source)
        self.assertIn("GetHourMinuteSecondUTC(", self.source)
        self.assertIn("Math.RandomIntInclusive(", self.source)
        registry = re.search(r"modded class HCModuleRegistry\s*\{([\s\S]*?)\n\}", self.source)
        self.assertIsNotNone(registry)
        self.assertIn("super.RegisterModules();", registry[1])
        self.assertIn("Register(new HCEcologyRuntimeModule", registry[1])


if __name__ == "__main__":
    unittest.main()
