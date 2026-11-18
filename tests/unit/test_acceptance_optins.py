"""Local-acceptance marker opt-outs for the remaining source gates.

Gates covered (each Qualified()/Accepted() stays a literal `return false;`; a server-only,
probe-once, cached marker gate is OR'd in through a new Admitted() method, the shape of
HCFuelSiphonQualification, HCInfectedDeathQualification and HCInfectedVisionQualification).
Owner decision 2026-11-17: every feature is ON by default and `<name>.disable` in the server profile turns
exactly that gate off, so the OptIn() probe is `!FileExist(<name>.disable)`:

  HCInfectedProfiles.ContactGuardQualified       infected_contact_guard.disable
  HCInfectedQualification.CEAdoptionQualified    infected_ce_adoption.disable
  HCInfectedQualification.NativePackRoutesQualified     infected_pack_routes.disable
  HCInfectedQualification.InvestigationQualified        infected_investigation.disable
  HCInfectedQualification.SupplementaryChainsQualified  infected_supplementary_chains.disable
  HCInfectedQualification.MemberRecoveryQualified       infected_member_recovery.disable
  HCInfectedQualification.HordeStimulusRoutesQualified  infected_horde_routes.disable
  HCInteriorRules.PlacementAccepted              interior_placement.disable
  HCInteriorRules.SearchAccepted                 interior_search.disable

HCStaminaConfiguration.Qualified is deliberately NOT given a marker: nothing reads it (the
stamina module is already enabled by the stamina.json profile), so a marker could open nothing.

The authored Enforce methods are cut out of the real sources, translated token by token by the
Enforce-subset translator of test_v1_native_noise_vision.py and EXECUTED against explicit
SYNTHETIC natives (GetGame, FileExist, Print). The extraction only slices authored text; it never
reimplements a method. These tests prove authored control flow only: not Enforce compilation, not
DayZ behavior, not runtime acceptance of any gated feature.
"""
import re
from pathlib import Path
import unittest

try:
    from .test_v1_native_noise_vision import Translator, f32, Unsupported
except ImportError:
    from test_v1_native_noise_vision import Translator, f32, Unsupported

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "mods/HollowCountry/scripts/4_World"
PREFIX = "$profile:HollowCountry/acceptance/"
INFECTED_STATE = SCRIPTS / "Infected/HCInfectedState.c"
INFECTED_PROFILES = SCRIPTS / "Infected/HCInfectedProfiles.c"
INFECTED_MODULE = SCRIPTS / "Infected/HCInfectedModule.c"
INFECTED_SELFTESTS = SCRIPTS / "Infected/HCInfectedSelfTests.c"
ECOLOGY = SCRIPTS / "Ecology/HCEcologyMigrationNative.c"
INTERIOR_RULES = SCRIPTS / "Interiors/HCInteriorRules.c"
INTERIOR_MODULE = SCRIPTS / "Interiors/HCInteriorModule.c"

# class, file, Qualified/Accepted method, Admitted method, marker name
GATES = (
    ("HCInfectedProfiles", INFECTED_PROFILES, "ContactGuardQualified", "ContactGuardAdmitted", "infected_contact_guard"),
    ("HCInfectedQualification", INFECTED_STATE, "CEAdoptionQualified", "CEAdoptionAdmitted", "infected_ce_adoption"),
    ("HCInfectedQualification", INFECTED_STATE, "NativePackRoutesQualified", "NativePackRoutesAdmitted", "infected_pack_routes"),
    ("HCInfectedQualification", INFECTED_STATE, "InvestigationQualified", "InvestigationAdmitted", "infected_investigation"),
    ("HCInfectedQualification", INFECTED_STATE, "SupplementaryChainsQualified", "SupplementaryChainsAdmitted", "infected_supplementary_chains"),
    ("HCInfectedQualification", INFECTED_STATE, "MemberRecoveryQualified", "MemberRecoveryAdmitted", "infected_member_recovery"),
    ("HCInfectedQualification", INFECTED_STATE, "HordeStimulusRoutesQualified", "HordeStimulusRoutesAdmitted", "infected_horde_routes"),
    ("HCInteriorRules", INTERIOR_RULES, "PlacementAccepted", "PlacementAdmitted", "interior_placement"),
    ("HCInteriorRules", INTERIOR_RULES, "SearchAccepted", "SearchAdmitted", "interior_search"),
)


def strip_comments(text):
    return re.sub(r"//[^\n]*", "", text)


def class_source(path, name):
    source = path.read_text()
    match = re.search(r"^(?:modded )?class " + re.escape(name) + r"\b", source, re.M)
    if not match:
        raise AssertionError("missing authored class: " + name)
    open_brace = source.index("{", match.end())
    depth, pos = 0, open_brace
    while True:
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace + 1:pos]
        pos += 1


def method_source(body, name):
    match = re.search(r"\bstatic [A-Za-z]+ " + re.escape(name) + r"\s*\([^)]*\)\s*\{", body)
    if not match:
        raise AssertionError("missing authored method: " + name)
    depth, pos = 1, match.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(body[pos], 0)
        pos += 1
    return body[match.start():pos]


def fragment(path, cls, methods):
    """Authored statics and the named authored methods of one class, as a one-class source."""
    body = class_source(path, cls)
    fields = re.findall(r"^[ \t]*protected static (?:bool|int) \w+(?: = \w+)?;[ \t]*$", body, re.M)
    return "class %s\n{\n%s\n%s\n}\n" % (cls, "\n".join(fields), "\n".join(method_source(body, m) for m in methods))


class World:
    """Authored gate methods over synthetic natives; `present` is the set of `.disable` marker files that exist."""

    def __init__(self, cls, path, methods, present=(), server=True, game=True):
        self.log = []
        self.present = set(present)
        log, present_files = self.log, self.present

        class Game:
            def IsServer(self):
                log.append(("IsServer",))
                return server

        self.game = Game() if game else None
        natives = {
            "GetGame": lambda: self.game,
            "FileExist": lambda name: log.append(("FileExist", name)) or name in present_files,
            "Print": lambda text: log.append(("Print", text)),
        }
        code = Translator(fragment(path, cls, methods), natives).emit({cls: None})
        namespace = dict(natives)
        namespace["f32"] = f32
        exec(compile(code, "authored-enforce:" + cls, "exec"), namespace)
        self.cls = namespace[cls]

    def prints(self):
        return [entry[1] for entry in self.log if entry[0] == "Print"]

    def probes(self):
        return [entry[1] for entry in self.log if entry[0] == "FileExist"]


def world(gate, **kwargs):
    cls, path, closed, admitted, marker = gate
    return World(cls, path, (closed, admitted, marker_method(cls, admitted)), **kwargs)


def marker_method(cls, admitted):
    return admitted.replace("Admitted", "OptIn")


class OptInExecutionTests(unittest.TestCase):
    def each(self):
        for gate in GATES:
            yield gate, "%s.%s" % (gate[0], gate[3])

    def test_without_the_marker_the_gate_is_open_probes_once_and_logs_one_line(self):
        for gate, label in self.each():
            with self.subTest(gate=label):
                w = world(gate)
                admitted = getattr(w.cls, gate[3])
                self.assertIs(False, getattr(w.cls, gate[2])(), "the source gate itself stays closed")
                for _ in range(4):
                    self.assertIs(True, admitted(), "the default with no marker is open")
                self.assertEqual([PREFIX + gate[4] + ".disable"], w.probes())
                lines = w.prints()
                self.assertEqual(1, len(lines))
                self.assertIn("EXPERIMENTAL", lines[0])
                self.assertIn("runtime acceptance PENDING", lines[0])

    def test_disable_marker_closes_the_gate_probes_once_and_logs_nothing(self):
        for gate, label in self.each():
            with self.subTest(gate=label):
                name = PREFIX + gate[4] + ".disable"
                w = world(gate, present=[name])
                admitted = getattr(w.cls, gate[3])
                for _ in range(4):
                    self.assertIs(False, admitted())
                self.assertIs(False, getattr(w.cls, gate[2])())
                self.assertEqual([name], w.probes())
                self.assertEqual([], w.prints(), "an opted-out gate logs nothing")

    def test_each_disable_marker_closes_only_its_own_gate(self):
        for gate, label in self.each():
            with self.subTest(gate=label):
                for other in GATES:
                    if other[:2] != gate[:2] or other is gate:
                        continue
                    w = world(gate, present=[PREFIX + other[4] + ".disable"])
                    self.assertIs(True, getattr(w.cls, gate[3])())
                w = world(gate, present=[PREFIX + gate[4] + ".enable"])
                self.assertIs(True, getattr(w.cls, gate[3])(), "a stray .enable file closes nothing")

    def test_server_only_and_a_non_server_probe_does_not_poison_the_cache(self):
        for gate, label in self.each():
            with self.subTest(gate=label):
                name = PREFIX + gate[4] + ".disable"
                for kwargs in ({"server": False}, {"game": False}):
                    w = world(gate, **kwargs)
                    admitted = getattr(w.cls, gate[3])
                    self.assertIs(False, admitted())
                    self.assertEqual([], w.probes())
                    self.assertEqual([], w.prints())
                w = world(gate, server=False)
                admitted = getattr(w.cls, gate[3])
                self.assertIs(False, admitted())
                w.game.IsServer = lambda: True
                self.assertIs(True, admitted())
                self.assertEqual([name], w.probes())

    def test_source_qualification_short_circuits_without_probing(self):
        for gate, label in self.each():
            with self.subTest(gate=label):
                w = world(gate)
                setattr(w.cls, gate[2], staticmethod(lambda: True))
                self.assertIs(True, getattr(w.cls, gate[3])())
                self.assertEqual([], w.probes())
                self.assertEqual([], w.prints())

    def test_marker_names_are_distinct_and_each_gate_probes_a_literal_disable_marker(self):
        names = [gate[4] for gate in GATES]
        self.assertEqual(len(names), len(set(names)))
        for cls, path, closed, admitted, marker in GATES:
            body = class_source(path, cls)
            literal = '!FileExist("%s%s.disable")' % (PREFIX, marker)
            self.assertEqual(1, body.count(literal), literal)
            self.assertEqual("return false;", re.sub(r"\s+", " ", re.search(
                r"static bool " + closed + r"\(\)\s*\{(.*?)\}", body, re.S).group(1)).strip())


# SYNTHETIC stand-in for HCInfectedAdmission.Resolve: returns the six qualification flags it was given.
SYNTHETIC_RESOLVE = """static string Resolve(HCInfectedConfig config, bool a, bool b, bool c, bool d, bool e, bool f)
    {
        return Flags(a, b, c, d, e, f);
    }
    """


class AdmissionEvaluateTests(unittest.TestCase):
    """HCInfectedAdmission.Evaluate hands each marker to the right Resolve argument."""

    def evaluate(self, present):
        log, files = [], set(present)
        natives = {
            "GetGame": lambda: type("G", (), {"IsServer": staticmethod(lambda: True)})(),
            "FileExist": lambda name: name in files,
            "Print": lambda text: log.append(text),
            "Flags": lambda *flags: flags,
        }
        paths = ("CEAdoption", "NativePackRoutes", "Investigation",
                 "SupplementaryChains", "MemberRecovery", "HordeStimulusRoutes")
        qual = []
        for path in paths:
            qual += [path + "Qualified", path + "Admitted", path + "OptIn"]
        text = fragment(INFECTED_STATE, "HCInfectedQualification", qual)
        text += fragment(INFECTED_STATE, "HCInfectedAdmission", ["Evaluate"]).replace(
            "static HCInfectedAdmission Evaluate", SYNTHETIC_RESOLVE + "static HCInfectedAdmission Evaluate", 1)
        code = Translator(text, natives).emit({"HCInfectedQualification": None, "HCInfectedAdmission": None})
        namespace = dict(natives)
        namespace["f32"] = f32
        exec(compile(code, "authored-enforce:admission", "exec"), namespace)
        return namespace["HCInfectedAdmission"].Evaluate("config"), log

    def test_default_all_open_and_one_log_line_per_path(self):
        flags, log = self.evaluate(())
        self.assertEqual((True,) * 6, flags)
        self.assertEqual(6, len(log))

    def test_each_disable_marker_flips_exactly_its_resolve_argument(self):
        order = ("infected_ce_adoption", "infected_pack_routes", "infected_investigation",
                 "infected_supplementary_chains", "infected_member_recovery", "infected_horde_routes")
        for index, marker in enumerate(order):
            with self.subTest(marker=marker):
                flags, log = self.evaluate([PREFIX + marker + ".disable"])
                expected = tuple(i != index for i in range(6))
                self.assertEqual(expected, flags)
                self.assertEqual(5, len(log), "the opted-out path logs nothing")


class CallSiteContractTests(unittest.TestCase):
    """Every consumer asks the Admitted() form; nothing else probes or opens a gate."""

    def code(self, path):
        return strip_comments(path.read_text())

    def test_admission_evaluate_uses_only_the_admitted_forms(self):
        body = method_source(class_source(INFECTED_STATE, "HCInfectedAdmission"), "Evaluate")
        for path in ("CEAdoption", "NativePackRoutes", "Investigation", "SupplementaryChains",
                     "MemberRecovery", "HordeStimulusRoutes"):
            self.assertIn("HCInfectedQualification.%sAdmitted()" % path, body)
            self.assertNotIn(path + "Qualified()", body)

    def test_contact_guard_consumers_use_the_admitted_form(self):
        module = self.code(INFECTED_MODULE)
        self.assertEqual(2, module.count("HCInfectedProfiles.ContactGuardAdmitted()"))
        self.assertNotIn("ContactGuardQualified", module)

    def test_ecology_consumers_use_the_admitted_forms(self):
        text = self.code(ECOLOGY)
        for path in ("Investigation", "SupplementaryChains", "NativePackRoutes", "HordeStimulusRoutes"):
            self.assertIn("HCInfectedQualification.%sAdmitted()" % path, text)
            self.assertNotIn("HCInfectedQualification.%sQualified()" % path, text)

    def test_interior_module_asks_the_admitted_forms(self):
        text = self.code(INTERIOR_MODULE)
        self.assertIn("m_PlacementProof = HCInteriorRules.PlacementAdmitted();", text)
        self.assertIn("m_SearchProof = HCInteriorRules.SearchAdmitted();", text)
        self.assertNotIn("PlacementAccepted()", text)
        self.assertNotIn("SearchAccepted()", text)

    def test_diag_selftest_closed_assertion_no_longer_depends_on_a_profile_marker(self):
        text = self.code(INFECTED_SELFTESTS)
        self.assertNotIn("HCInfectedAdmission.Evaluate(", text)
        self.assertIn("HCInfectedAdmission admission = HCInfectedAdmission.Resolve(config, false, false, false, false, false, false);", text)

    def test_only_the_nine_new_probes_were_added(self):
        counts = {
            INFECTED_PROFILES: 1, INFECTED_STATE: 8, INTERIOR_RULES: 2,
        }
        for path, expected in counts.items():
            self.assertEqual(expected, self.code(path).count("FileExist("), path.name)
        # HCInfectedState.c already held two unrelated probes before this change (6 + 2); the
        # ecology file keeps its single pre-existing ecology_migration probe.
        self.assertNotIn("acceptance/", self.code(INFECTED_MODULE))
        self.assertEqual(1, self.code(ECOLOGY).count("FileExist("))

    def test_every_new_opt_in_is_server_gated_inside_the_admitted_method(self):
        for cls, path, closed, admitted, marker in GATES:
            body = method_source(class_source(path, cls), admitted)
            self.assertIn("GetGame()", body)
            self.assertIn("IsServer()", body)
            self.assertLess(body.index("IsServer()"), body.index(marker_method(cls, admitted) + "()"))


if __name__ == "__main__":
    unittest.main()
