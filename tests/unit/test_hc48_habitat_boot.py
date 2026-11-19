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

Wave 12 (#193, counts tallied from the manifest, not copied), actual RED 2026-11-19 (same command, against the
literal-count source): FAILED (failures=3), e.g. AssertionError: 'species=3 habitats=2 target_pairs_supported=0
state=ready' not found in '[HC Plan] HC-48 species=27 habitats=11 ...'; AssertionError: 1 != 0 (manifest never read).
GREEN: same command -> Ran 23 tests, OK.

GREEN (2026-11-19, wave 11): same command -> Ran 20 tests ... OK; test_ecology_module, test_ecology_runtime,
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


def _lowered(text):
    # Language lowering only: Enforce IndexOfFrom(start, sample) -> Python str.find(sample, start).
    return re.sub(r"(\w+)\.IndexOfFrom\((\w+), (\w+)\)", r"\1.find(\3, \2)", text)


class HabitatReceiptLine(unittest.TestCase):
    MANIFEST_BYTES = 32768

    def setUp(self):
        self.manifest_text = MANIFEST.read_text()
        self.manifest = json.loads(self.manifest_text)
        self.fresh(self.manifest_text)

    def fresh(self, text):
        """A new boot: empty static cache, the given manifest text behind the file port."""
        self.logs = []
        self.reads = []
        self.e = environment()
        self.e["Print"] = self.logs.append
        self.e["HCEcologyRuntimeIO"] = SimpleNamespace(
            Read=lambda path, limit: self.reads.append((path, limit)) or (text if len(text) <= limit else ""))
        self.state = SimpleNamespace(s_HabitatState="", s_HabitatLoaded=False, s_HabitatValid=False,
                                     s_HabitatSpeciesNative=0, s_HabitatSpeciesPending=0,
                                     s_HabitatSpeciesAddon=0, s_HabitatNative=0, s_HabitatLegacy=0)
        self.e["hab"] = self.state
        source = _lowered(NATIVE.read_text().replace("s_Habitat", "hab.s_Habitat"))
        native = SimpleNamespace()
        self.e["HCEcologyNative"] = native
        # Class constants the translated statics reference bare; read from the authored source.
        for name, value in re.findall(r'static const (?:string|int) (HC_HABITAT_\w+) = ("[^"]*"|\d+);', source):
            self.e[name] = json.loads(value)
        for name in ("HCHabitatCount", "HCHabitatLoad", "HCHabitatRefusals"):
            setattr(native, name, translated(source, name, self.e, "HCEcologyNative"))
        self.call = native.HCHabitatRefusals

    def rows(self, count, disposition):
        return ",".join('{"Disposition": "%s"}' % disposition for _ in range(count))

    def synthetic(self, species=(3, 2, 1), habitats=(2, 1), pairs=4, species_extra=""):
        """Explicit synthetic manifest: only the section keys and Disposition values the receipt reads."""
        names = ("retain_native", "pending_suitability", "selected_pending_addon_and_native")
        kinds = ("retain_native", "legacy_unreferenced_pending_survey")
        parts = [self.rows(n, d) for n, d in zip(species, names) if n] + ([species_extra] if species_extra else [])
        spec = ",".join(parts)
        hab = ",".join(self.rows(n, d) for n, d in zip(habitats, kinds) if n)
        return ('{"Version": 1, "Species": [%s], "Habitats": [%s], "TargetPairs": [%s], "Counts": {}}'
                % (spec, hab, self.rows(pairs, "retain_native")))

    def test_ready_line_carries_counts_dispositions_and_every_refusal_reason(self):
        self.call("ready")
        self.assertEqual(1, len(self.logs))
        line = self.logs[0]
        counts = self.manifest["Counts"]
        native_species = len([r for r in self.manifest["Species"] if r["Disposition"] == "retain_native"])
        native_habitats = len([r for r in self.manifest["Habitats"] if r["Disposition"] == "retain_native"])
        # Expected counts derive from the manifest rows, then cross-check its own Counts block.
        self.assertEqual((native_species, native_habitats), (counts["StockEventSpecies"], counts["BaselineEffectiveHabitatFiles"]))
        self.assertIn("[HC Plan] HC-48 species=%d habitats=%d target_pairs_supported=0 state=ready" % (
            native_species, native_habitats), line)
        self.assertIn("authored_species=%d authored_habitats=%d admitted_overlay_species=0" % (
            len(self.manifest["Species"]), len(self.manifest["Habitats"])), line)
        self.assertEqual((len(self.manifest["Species"]), len(self.manifest["Habitats"])),
                         (counts["AuthoredSpecies"], counts["AuthoredHabitatFiles"]))
        self.assertIn("observed_reactions=unobserved", line)
        self.assertTrue(line.endswith("runtime=PENDING"))
        for refusal in self.manifest["Refusals"]:
            self.assertIn(refusal["Capability"] + ":" + refusal["Reason"], line)
        self.assertLess(len(line), 900)

    def test_off_and_refused_admit_nothing(self):
        for state in ("off", "refused"):
            self.fresh(self.manifest_text)
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

    def test_counts_follow_the_loaded_manifest_not_copied_literals(self):
        self.fresh(self.synthetic())
        self.call("ready")
        line = self.logs[0]
        self.assertIn("species=3 habitats=2 target_pairs_supported=0 state=ready", line)
        self.assertIn("authored_species=6 authored_habitats=3 admitted_overlay_species=0", line)
        self.assertIn("species_dispositions=retain_native:3,pending_suitability:2,"
                      "selected_pending_addon_and_native:1 habitat_dispositions=retain_native:2,"
                      "legacy_unreferenced_pending_survey:1", line)
        self.assertNotIn("27", line, "the synthetic boot must not echo the shipped manifest counts")

    def test_manifest_is_read_once_per_boot_inside_its_declared_byte_bound(self):
        for state in ("ready", "off", "refused", "ready"):
            self.call(state)
        self.assertEqual(1, len(self.reads))
        path, limit = self.reads[0]
        self.assertEqual("$mission:hollow-country/ecology/habitat-overrides.json", path)
        self.assertEqual(self.manifest["ManifestMaxBytes"], limit)
        self.assertLessEqual(len(self.manifest_text.encode()), limit)

    def test_missing_or_inconsistent_manifest_refuses_instead_of_claiming_counts(self):
        broken = {
            "unreadable": "",
            "no sections": '{"Version": 1}',
            "sections out of order": '{"Habitats": [], "Species": [], "TargetPairs": []}',
            "unknown species disposition": self.synthetic(species_extra='{"Disposition": "mystery"}'),
            "empty habitats": self.synthetic(habitats=(0, 0)),
        }
        for name, text in broken.items():
            self.fresh(text)
            self.call("ready")
            self.assertEqual(1, len(self.logs), name)
            self.assertIn("species=0 habitats=0 target_pairs_supported=0 state=refused", self.logs[0], name)
            self.assertIn("authored_species=0 authored_habitats=0", self.logs[0], name)
            self.assertTrue(self.logs[0].endswith("runtime=PENDING"), name)

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
