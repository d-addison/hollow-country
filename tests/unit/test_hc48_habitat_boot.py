"""HC-48 habitat boot line (#149) and HC-29 single refusal print (#192).

Wave 11 / w27-ecology. Synthetic ports only: this proves the authored source
reaches the habitat receipt through the existing Ecology module lifecycle and
that invalid settings print ONE HC-29 refusal. It never claims CE loaded the
habitat manifest or that any animal behaved (runtime=PENDING).

Actual RED (2026-11-19), command
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc48_habitat_boot
  FAILED (failures=4, errors=4), e.g.
  AssertionError: Lists differ: ['ready'] != []   (module never calls the receipt)
  AssertionError: 1 != 2 : [... HC-29 state=refused reason=invalid_settings ..., ... same line ...]
  TypeError: executed() takes 0 positional arguments but 1 was given (receipt takes no state)

GREEN (2026-11-19): same command -> Ran 20 tests ... OK; test_ecology_module, test_ecology_runtime,
test_ecology_native, test_script_syntax, test_enforce_locals, test_script_identifiers, test_hygiene OK;
python3 -B -m tools.validate.enforce_lint --no-native -> new=0 stale=0.
"""
import json
import re
import unittest
from types import SimpleNamespace

from tests.unit import test_ecology_module
from tests.unit.test_ecology_runtime import ROOT, environment, translated

NATIVE = ROOT / "4_World/Ecology/HCEcologyNative.c"
RUNTIME = ROOT / "4_World/Ecology/HCEcologyRuntime.c"
MANIFEST = ROOT.parents[2] / "mission/hollow-country/ecology/habitat-overrides.json"


class HabitatReceiptWiring(test_ecology_module.EcologyModuleBehavior):
    def setUp(self):
        super().setUp()
        self.receipts = []
        self.e["HCEcologyNative"] = SimpleNamespace(HCHabitatRefusals=lambda state: self.receipts.append(state))

    def test_started_module_prints_the_habitat_receipt_once(self):
        self.module.m_Settings = self.settings
        self.method("OnStart")(self.module, None)
        self.assertEqual(["ready"], self.receipts)

    def test_rejected_start_reports_refused(self):
        self.started = False
        self.module.m_Settings = self.settings
        self.method("OnStart")(self.module, None)
        self.assertEqual(["refused"], self.receipts)

    def test_operator_off_and_invalid_settings_report_off_and_refused(self):
        self.settings.Enabled = False
        self.method("IsEnabled")(self.module, None)
        self.settings = None
        self.method("IsEnabled")(self.module, None)
        self.assertEqual(["off", "refused"], self.receipts)

    def test_client_never_prints_a_receipt(self):
        self.game.IsServer = lambda: False
        self.method("IsEnabled")(self.module, None)
        self.assertEqual([], self.receipts)


class HabitatReceiptLine(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.manifest = json.loads(MANIFEST.read_text())
        self.e = environment()
        self.e["Print"] = self.logs.append
        text = NATIVE.read_text()
        self.state = SimpleNamespace(s_HabitatState="")
        self.source = text.replace("s_HabitatState", "hab.s_HabitatState")
        self.e["hab"] = self.state
        self.call = translated(self.source, "HCHabitatRefusals", self.e, "HCEcologyNative")

    def test_ready_line_carries_counts_dispositions_and_every_refusal_reason(self):
        self.call("ready")
        self.assertEqual(1, len(self.logs))
        line = self.logs[0]
        counts = self.manifest["Counts"]
        self.assertIn("[HC Plan] HC-48 species=%d habitats=%d target_pairs_supported=0 state=ready" % (
            counts["StockEventSpecies"], counts["BaselineEffectiveHabitatFiles"]), line)
        self.assertIn("authored_species=%d authored_habitats=%d admitted_overlay_species=0" % (
            counts["AuthoredSpecies"], counts["AuthoredHabitatFiles"]), line)
        self.assertIn("observed_reactions=unobserved", line)
        self.assertTrue(line.endswith("runtime=PENDING"))
        for refusal in self.manifest["Refusals"]:
            self.assertIn(refusal["Capability"] + ":" + refusal["Reason"], line)
        self.assertLess(len(line), 900)

    def test_off_and_refused_admit_nothing(self):
        for state in ("off", "refused"):
            self.logs.clear()
            self.state.s_HabitatState = ""
            self.call(state)
            self.assertIn("species=0 habitats=0 target_pairs_supported=0 state=" + state, self.logs[0])

    def test_same_state_prints_once_and_unknown_state_is_refused(self):
        self.call("ready")
        self.call("ready")
        self.assertEqual(1, len(self.logs))
        self.call("bogus")
        self.assertIn("state=refused", self.logs[-1])

    def test_disposition_counts_match_the_manifest(self):
        species = {}
        for row in self.manifest["Species"]:
            species[row["Disposition"]] = species.get(row["Disposition"], 0) + 1
        habitats = {}
        for row in self.manifest["Habitats"]:
            habitats[row["Disposition"]] = habitats.get(row["Disposition"], 0) + 1
        self.call("ready")
        line = self.logs[0]
        for name, count in species.items():
            self.assertIn(name + ":" + str(count), line)
        for name, count in habitats.items():
            self.assertIn(name + ":" + str(count), line)

    def test_manifest_stays_inert(self):
        counts = self.manifest["Counts"]
        self.assertEqual(0, counts["AdmittedOverlaySpecies"])
        self.assertEqual(0, counts["TargetPairsSupported"])
        self.assertFalse(self.manifest["ProductionEnabled"])
        self.assertFalse(self.manifest["Application"]["RuntimeLoader"])


class HC29InvalidSettingsPrintsOnce(unittest.TestCase):
    def test_invalid_settings_refusal_prints_once(self):
        logs = []
        e = environment()
        e["Print"] = logs.append
        e["HCEcologyNative"] = SimpleNamespace(Authority=lambda: True)
        e["GetGame"] = lambda: SimpleNamespace(GetWorldName=lambda: "synthetic-world", GetTime=lambda: 5000)
        settings = e["HCEcologyRuntimeSettings"]()
        settings.TickMs = 0  # SettingsValid rejects (see test_ecology_runtime bounds test)
        source = RUNTIME.read_text().replace('JsonFileLoader<HCEcologyRuntimeSettings>', 'HCEcologySettingsCodec')
        runtime = SimpleNamespace(m_StartupMaxTicks=0, m_StartRefusal="", m_Running=False, m_Session="",
                                  m_SaveMaxTicks=0, m_Settings=e["HCEcologyRuntimeSettings"](),
                                  Finish=lambda: None)
        runtime.Begin = lambda *args: translated(source, "Begin", e, "HCEcologyRuntime", True)(runtime, *args)
        e["HCEcologyRuntime"] = SimpleNamespace(Instance=lambda: runtime)
        start = translated(source, "Start", e, "HCEcologyRuntime")
        self.assertFalse(start(settings, "synthetic-world", "session-b"))
        refusals = [line for line in logs if "reason=invalid_settings" in line]
        self.assertEqual(1, len(refusals), logs)


if __name__ == "__main__":
    unittest.main()
