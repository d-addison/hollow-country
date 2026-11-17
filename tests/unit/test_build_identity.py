"""One shared engine-build matcher (#29 phase 1).

Native evidence: GetGame().GetVersion(out string) returns "1.30.164289.70" on
the real engine (interior-sampler-001 census.json "version"); Hollow Country
pins the canonical "1.30.164289". The authored HCBuildIdentity.c statics are
executed through build_identity_support.translate, never re-implemented here.
Site behaviour lives next to each module's own tests; this file owns the
matcher table, the module gates that have no other harness, and the source
scan that keeps the literal inside HCBuildIdentity.c. Offline tests never
establish DayZ behavior.
"""
import re
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace as NS

from tests.unit.build_identity_support import translate as build_identity
from tests.unit import test_infected_admission as admission
from tests.unit import test_search_economy_integration as integration

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "mods/HollowCountry/scripts"
IDENTITY = SCRIPTS / "3_Game/HCBuildIdentity.c"
CANONICAL = "1.30.164289"
NATIVE = "1.30.164289.70"
REFUSED = ("", " ", " 1.30.164289", "1.30.164289 ", " 1.30.164289.70", "1.30.164289.70 ",
           "1.30.164289.70\n", "\t1.30.164289", "1.30.164289.7x", "1.30.164289.7", "1.30.164289.71",
           "1.30.164289.700", "1.30.164289.070", "1.30.164289.70.1", "1.30.164289.", "1.30.1642890",
           "1.30.16428", "1.30.164290", "1.31.164289", "21.30.164289", "v1.30.164289", "1.30.164289.70x",
           "synthetic_build", "1.30.164289\x00", "1.30.164289.70\x00")

# runtime script path (relative to mods/HollowCountry/scripts) -> one-line reason the dotted build
# literal may stay outside HCBuildIdentity.c. Comment-only mentions are exempt (comments cannot
# compare or stamp a build). Every key must still contain the literal in code (checked below).
ALLOWLIST = {}
LITERAL = re.compile(r"1\.30\.164289")


class Snippet:
    """A Path stand-in whose text is an excerpt of an authored file, so the translators run only
    the authored statements under test (the harness cannot translate whole bodies)."""

    def __init__(self, text):
        self.text = text

    def __truediv__(self, name):
        return self

    def read_text(self, *args, **kwargs):
        return self.text


def excerpt(path, start, stop, after=""):
    """Authored text from the first `start` marker (after the `after` marker) up to (excluding) `stop`."""
    text = path.read_text()
    begin = text.index(start, text.index(after) if after else 0)
    return text[begin:text.index(stop, begin)]


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return "\n".join(line.split("//")[0] for line in text.splitlines())


class MatcherTests(unittest.TestCase):
    def setUp(self):
        self.identity = build_identity()

    def test_canonical_is_the_pinned_script_snapshot_build(self):
        self.assertEqual(CANONICAL, self.identity.Canonical())

    def test_matches_exactly_the_pin_and_the_observed_native_full_version(self):
        self.assertTrue(self.identity.Matches(CANONICAL))
        self.assertTrue(self.identity.Matches(NATIVE))

    def test_every_other_text_is_refused(self):
        for text in REFUSED:
            with self.subTest(text=text):
                self.assertFalse(self.identity.Matches(text))

    def test_normalize_collapses_only_admitted_builds(self):
        self.assertEqual(CANONICAL, self.identity.Normalize(NATIVE))
        self.assertEqual(CANONICAL, self.identity.Normalize(CANONICAL))
        for text in REFUSED:
            self.assertEqual(text, self.identity.Normalize(text))

    def test_same_build_is_equality_after_normalising_and_never_for_empty(self):
        self.assertTrue(self.identity.SameBuild(NATIVE, CANONICAL))
        self.assertTrue(self.identity.SameBuild(CANONICAL, NATIVE))
        self.assertTrue(self.identity.SameBuild("synthetic", "synthetic"))
        self.assertFalse(self.identity.SameBuild("", ""))
        self.assertFalse(self.identity.SameBuild(NATIVE, "1.30.164289.7x"))
        self.assertFalse(self.identity.SameBuild("1.30.164289.7x", NATIVE))

    def test_world_name_is_lowercased_and_case_insensitive(self):
        self.assertEqual("chernarusplus", self.identity.CanonicalWorld("ChernarusPlus"))
        self.assertEqual("enoch", self.identity.CanonicalWorld("ENOCH"))
        self.assertTrue(self.identity.SameWorld("ChernarusPlus", "chernarusplus"))
        self.assertFalse(self.identity.SameWorld("enoch", "chernarusplus"))
        self.assertFalse(self.identity.SameWorld("", ""))

    def test_authored_class_stays_inside_the_executable_subset(self):
        # build_identity_support asserts on any statement it cannot execute faithfully.
        text = strip_comments(IDENTITY.read_text())
        self.assertNotRegex(text, r"\?[^;]*:")  # no ternary in Enforce
        self.assertEqual(1, text.count("class HCBuildIdentity"))
        self.assertEqual({CANONICAL, NATIVE}, set(re.findall(r'"(1\.30\.164289[^"]*)"', text)))


class ProfilesDelegationTests(unittest.TestCase):
    def test_infected_native_build_gate_uses_the_shared_matcher(self):
        from tests.unit.test_infected_defaults import authored
        for build in (CANONICAL, NATIVE) + REFUSED:
            with self.subTest(build=build):
                result = authored("HCInfectedProfiles.c", "static bool NativeBuildSupported(", NS(),
                                  build=build, HCBuildIdentity=build_identity())
                self.assertEqual(build in (CANONICAL, NATIVE), result)


class InfectedSnapshotTests(unittest.TestCase):
    """A snapshot stamped by this code must reload under the real '.70' engine string."""

    def setUp(self):
        self.identity = build_identity()
        self.policies = NS(**admission.policy_functions())
        self.validate = admission.translate(
            "HCInfectedState.c", "static bool Validate(", (), HCBuildIdentity=self.identity,
            HCInfectedPolicy=self.policies, ValidPosition=lambda value: True,
            HCHordeRecovery=NS(ValidateRoster=lambda group: True))

    def snapshot(self, build, **fields):
        values = dict(Build=build, SchemaVersion=2, WorldName="chernarusplus", Epoch=1, Reserved=0,
                      Groups=admission.Array(), Generation=1, SavedUtc=50)
        values.update(fields)
        return NS(**values)

    def test_fresh_journal_is_stamped_canonical_and_reloads_under_the_native_engine_string(self):
        created = []

        def factory():
            created.append(NS())
            return created[-1]

        state = SCRIPTS / "4_World/Infected/HCInfectedState.c"
        block = excerpt(state, "snapshot = new HCInfectedSnapshot;", "        HCInfectedSnapshot a, b;",
                         after="if (!existsA && !existsB)")
        source = ("static bool Fresh(out HCInfectedSnapshot snapshot, string world, int now) {\n"
                  + block.rstrip() + "\n    }\n}")
        with mock.patch.object(admission, "SOURCE", Snippet(source)):
            fresh = admission.translate("HCInfectedState.c", "static bool Fresh(", (), HCBuildIdentity=self.identity,
                                        HCInfectedSnapshot=factory)
        self.assertTrue(fresh(None, None, "chernarusplus", 100))
        snapshot = created[0]
        self.assertEqual(CANONICAL, snapshot.Build)
        snapshot.Generation, snapshot.SavedUtc = 1, 50  # what the first Save stamps
        self.assertTrue(self.validate(None, snapshot, "chernarusplus", 24, 16, 100))
        # Module start admits the live engine string through the same matcher the stamp came from.
        self.assertTrue(self.identity.Matches(NATIVE))

    def test_legacy_native_stamp_still_loads_and_foreign_stamps_quarantine(self):
        for build, expected in ((CANONICAL, True), (NATIVE, True), ("1.30.164289.7x", False), ("", False),
                                (" 1.30.164289", False), ("1.30.1642890", False)):
            with self.subTest(build=build):
                self.assertEqual(expected, self.validate(None, self.snapshot(build), "chernarusplus", 24, 16, 100))


class InteriorConfigTests(unittest.TestCase):
    """HCInteriorModule.ValidateConfig: same matcher as the measured catalog."""

    def gate(self, build):
        reasons = []
        module = SCRIPTS / "4_World/Interiors/HCInteriorModule.c"
        # Only the schema/map/build and epoch/seed guards: the rest of the body is outside the harness.
        source = ("bool ValidateConfig(HCSettings settings) {\n"
                  + excerpt(module, "if (!m_Config || m_Config.SchemaVersion", "        string world = GetGame()")
                  + "return true;\n}")
        t = NS(m_Config=NS(SchemaVersion=1, MapName="chernarusplus", Build=build, Epoch=0, Seed=1))
        t.Reject = lambda reason: reasons.append(reason) or False
        env = {"HCBuildIdentity": build_identity()}
        with mock.patch.object(integration, "SOURCE", Snippet(source)):
            integration.invoke("ValidateConfig", env, t, NS())
        return reasons

    def test_config_build_gate_admits_canonical_and_native_and_refuses_the_rest(self):
        for build in (CANONICAL, NATIVE):
            with self.subTest(build=build):
                self.assertEqual(["epoch or seed outside supported bounds"], self.gate(build))
        for build in REFUSED:
            with self.subTest(build=build):
                self.assertEqual(["config schema/map/build mismatch; migration is manual"], self.gate(build))


class SourceScanTests(unittest.TestCase):
    """The literal is a build string; only HCBuildIdentity.c may carry it as code."""

    def runtime_files(self):
        return sorted(p for p in SCRIPTS.rglob("*.c") if p != IDENTITY)

    def test_no_runtime_script_compares_or_stamps_the_build_literal(self):
        offenders = []
        for path in self.runtime_files():
            relative = str(path.relative_to(SCRIPTS))
            code = strip_comments(path.read_text())
            if relative in ALLOWLIST:
                continue
            for number, line in enumerate(code.splitlines(), 1):
                if LITERAL.search(line):
                    offenders.append("%s:%d: %s" % (relative, number, line.strip()[:100]))
        self.assertEqual([], offenders)

    def test_allowlist_is_minimal_every_entry_carries_a_reason_and_still_needs_it(self):
        for relative, reason in ALLOWLIST.items():
            with self.subTest(relative=relative):
                self.assertTrue(reason.strip() and "\n" not in reason)
                code = strip_comments((SCRIPTS / relative).read_text())
                self.assertRegex(code, LITERAL, "stale allowlist entry: remove " + relative)


class GetVersionSiteTests(unittest.TestCase):
    """Every HollowCountry GetVersion consumer routes through HCBuildIdentity (no bare compares)."""

    def test_every_get_version_site_feeds_the_shared_matcher(self):
        users = {}
        for path in SCRIPTS.rglob("*.c"):
            code = strip_comments(path.read_text())
            if "GetVersion(" in code:
                users[str(path.relative_to(SCRIPTS))] = code
        self.assertEqual({
            "4_World/Loot/HCSearchNativeSupply.c", "4_World/Loot/HCSearchSupplyProvider.c",
            "4_World/Infected/HCInfectedRooms.c", "4_World/Infected/HCInfectedModule.c",
            "4_World/Interiors/HCInteriorMeasuredCatalog.c", "4_World/Survival/HCTapedLightService.c",
            "4_World/Weather/HCAtmosphereQualification.c",
            "4_World/Ecology/HCEcologyMigrationNative.c"},
            set(users))
        for relative, code in users.items():
            with self.subTest(relative=relative):
                # Module start delegates to HCInfectedProfiles.NativeBuildSupported, which uses the matcher.
                self.assertTrue("HCBuildIdentity." in code or "NativeBuildSupported(" in code)


if __name__ == "__main__":
    unittest.main()
