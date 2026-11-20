"""Synthetic C11/IC-07 scenarios execute the authored Enforce policy/state bodies.

This restricted translator is not an Enforce compiler, observer provider, Python
policy mirror, or runtime evidence. Unsupported syntax fails loudly.
"""
import math
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "mods/HollowCountry/scripts/4_World/Infected/HCObserverTransitionGate.c"


def block(text, start):
    depth, end = 1, start
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end - 1]


def expression(text):
    text = text.replace("HCObserverTransitionGate.", "")
    text = re.sub(r"\bnew (HC\w+)\(\)", r"\1()", text)
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"!(?!=)", "not ", text)
    for old, new in (("true", "True"), ("false", "False"), ("null", "None")):
        text = re.sub(r"\b" + old + r"\b", new, text)
    return text


def tokens(body):
    chunk, depth = "", 0
    for char in body:
        if char == "(": depth += 1
        if char == ")": depth -= 1
        if char in "{};" and depth == 0:
            if chunk.strip(): yield chunk.strip()
            chunk = ""
            if char != ";": yield char
        else:
            chunk += char
    if chunk.strip(): raise AssertionError("unterminated source statement")


def authored_contract():
    """Translate DTO initializers and scalar/array control flow, never decisions."""
    if not SOURCE.exists():
        raise AssertionError("C11 observer transition contract has not been authored")
    source = re.sub(r"//[^\n]*", "", SOURCE.read_text())
    namespace = {}
    for match in re.finditer(r"class (HC\w+)\s*\{", source):
        if match[1] == "HCObserverTransitionGate": continue
        fields = {}
        for field in block(source, match.end()).split(";"):
            if not field.strip(): continue
            declaration = re.fullmatch(r"\s*(?:ref )?(bool|int|float|HC\w+|array<ref HC\w+>)\s+(\w+)(?:\s*=\s*(.*))?\s*", field)
            if not declaration: raise AssertionError("unsupported DTO declaration: " + field)
            initial = {"bool": False, "int": 0, "float": 0.0}.get(declaration[1])
            if declaration[3] is not None:
                initial = eval(expression(declaration[3]), {"__builtins__": {}})
            fields[declaration[2]] = initial
        namespace[match[1]] = lambda defaults=fields: SimpleNamespace(**defaults)
    for match in re.finditer(r"static (?:bool|int|float) (\w+)\(([^)]*)\)\s*\{", source):
        args = [arg.strip().split()[-1] for arg in match[2].split(",") if arg.strip()]
        lines, indent = [f"def {match[1]}({', '.join(args)}):"], 1
        for token in tokens(block(source, match.end())):
            if token == "{": indent += 1; continue
            if token == "}": indent -= 1; continue
            loop = re.fullmatch(r"for \(int (\w+) = (.*); \1 < (.*); \1\+\+\)", token, re.S)
            if loop:
                token = f"for {loop[1]} in range({expression(loop[2])}, {expression(loop[3])}):"
            elif token.startswith("if (") and token.endswith(")"):
                token = "if " + expression(token[4:-1]) + ":"
            elif token == "else": token = "else:"
            else:
                if re.search(r"\b(?:for|while|foreach|switch|try|catch)\b", token):
                    raise AssertionError("unsupported source control flow: " + token)
                token = re.sub(r"^(?:bool|int|float|HC\w+)\s+(\w+) =", r"\1 =", token)
                token = expression(token)
            lines.append("    " * indent + token)
        exec(compile("\n".join(lines), str(SOURCE) + ":" + match[1], "exec"), namespace)
    return SimpleNamespace(**namespace)


class Samples(list):
    def Count(self): return len(self)


class ObserverTransitionTests(unittest.TestCase):
    def setUp(self):
        self.g = authored_contract()
        self.state = self.g.HCObserverTransitionState()
        self.policy = self.g.HCObserverTransitionPolicy()
        # EXPLICIT SYNTHETIC units/bounds; none are production recommendations.
        for key, value in dict(ProvisionalDiagnostic=True, Revision=1,
                               TimeBound=10000., DistanceBound=1000., DurationBound=100.,
                               NearDistance=10., FarDistance=20., SnapshotTTL=2.,
                               VisibilityGrace=5., ProximityGrace=5., QuietPeriod=3.,
                               TransitionCooldown=7., MaxObservers=4, MaxSamples=4).items():
            setattr(self.policy, key, value)
        self.assertTrue(self.g.Configure(self.state, self.policy))

    def sample(self, observer_id=1, at=100., **changes):
        sample = self.g.HCObserverTransitionSample()
        for key, value in dict(ObserverId=observer_id, ObservedAt=at,
                               CoverageKnown=True, SpectatorKnown=True, IsSpectator=False,
                               OpticsKnown=True, UsingOptics=False, VisibilityKnown=True,
                               Visible=False, RecentVisibilityKnown=True, LastVisibleAt=-1.,
                               NativeCombatKnown=True, InNativeCombat=False,
                               ProximityKnown=True, Distance=30., RecentProximityKnown=True,
                               LastNearAt=-1.).items(): setattr(sample, key, value)
        for key, value in changes.items(): setattr(sample, key, value)
        return sample

    def snapshot(self, at=100., samples=None, **changes):
        snapshot = self.g.HCObserverTransitionInput()
        if samples is None: samples = [self.sample(at=at), self.sample(2, at)]
        for key, value in dict(CapturedAt=at, RosterRevision=1, CoverageKnown=True,
                               SpectatorCoverageKnown=True, OpticsCoverageKnown=True,
                               ExpectedObservers=len(samples), Observers=Samples(samples),
                               NativeCombatKnown=True, InNativeCombat=False,
                               MembershipKnown=True, MembershipResolved=True,
                               CEAuthorityKnown=True, CEAuthority=True,
                               DurableIntentKnown=True, DurableIntent=True,
                               PopulationBudgetKnown=True, PopulationWithinBudget=True,
                               TransitionHistoryKnown=True, LastTransitionAt=-1.).items():
            setattr(snapshot, key, value)
        for key, value in changes.items(): setattr(snapshot, key, value)
        return snapshot

    def evaluate(self, at=100., **changes):
        return self.g.Evaluate(self.state, self.snapshot(at=at, **changes), at)

    def warm(self, start=100, **changes):
        results = [self.evaluate(float(at), **changes) for at in range(start, start + 4)]
        self.assertEqual([2, 2, 2, 3], results)

    def test_given_two_fresh_observers_when_continuously_clear_then_diagnostic_only(self):
        self.warm()
        self.assertFalse(self.g.CanTransition())
        self.assertFalse(self.g.ProviderCapabilityResolved())

    def test_default_inputs_and_policy_are_unknown_and_rejected(self):
        self.assertEqual(0, self.g.Evaluate(self.state, self.g.HCObserverTransitionInput(), 100.))
        self.assertFalse(self.g.Configure(self.state, self.g.HCObserverTransitionPolicy()))
        self.assertEqual(0, self.evaluate())
        self.assertFalse(self.g.Configure(None, self.policy))
        self.assertEqual(0, self.g.Evaluate(None, self.snapshot(), 100.))
        self.assertFalse(self.g.CanTransition())

    def test_policy_bounds_status_order_and_work_caps_are_required(self):
        invalid = dict(ProvisionalDiagnostic=False, Revision=0, TimeBound=0.,
                       DistanceBound=0., DurationBound=0., NearDistance=20.,
                       FarDistance=1001., SnapshotTTL=0., VisibilityGrace=101.,
                       ProximityGrace=0., QuietPeriod=0., TransitionCooldown=0.,
                       MaxObservers=33, MaxSamples=33)
        for key, value in invalid.items():
            with self.subTest(key=key):
                original = getattr(self.policy, key)
                setattr(self.policy, key, value)
                self.assertFalse(self.g.Configure(self.state, self.policy))
                setattr(self.policy, key, original)
        for key in ("TimeBound", "DistanceBound", "DurationBound", "NearDistance", "FarDistance",
                    "SnapshotTTL", "VisibilityGrace", "ProximityGrace", "QuietPeriod", "TransitionCooldown"):
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(key=key, value=value):
                    original = getattr(self.policy, key)
                    setattr(self.policy, key, value)
                    self.assertFalse(self.g.Configure(self.state, self.policy))
                    setattr(self.policy, key, original)
        self.policy.MaxSamples = 3
        self.assertFalse(self.g.Configure(self.state, self.policy))
        self.policy.MaxSamples = 4
        self.policy.DurationBound = 10001.
        self.assertFalse(self.g.Configure(self.state, self.policy))

    def test_caller_mutation_does_not_reconfigure_cached_policy(self):
        self.policy.QuietPeriod = .1
        self.assertEqual(2, self.evaluate())
        self.assertEqual(2, self.evaluate(101.))
        self.assertTrue(self.g.Configure(self.state, self.policy))
        self.assertEqual(2, self.evaluate(102.))
        self.assertEqual(3, self.evaluate(103.))

    def test_global_coverage_and_population_prerequisites_each_fail_closed(self):
        for key in ("CoverageKnown", "SpectatorCoverageKnown", "OpticsCoverageKnown",
                    "NativeCombatKnown", "MembershipKnown", "MembershipResolved",
                    "CEAuthorityKnown", "CEAuthority", "DurableIntentKnown", "DurableIntent",
                    "PopulationBudgetKnown", "PopulationWithinBudget", "TransitionHistoryKnown"):
            with self.subTest(key=key):
                self.assertEqual(0, self.evaluate(**{key: False}))
                self.assertEqual(-1., self.state.ClearSince)

    def test_each_observer_unknown_channel_vetoes_including_second_observer(self):
        for key in ("CoverageKnown", "SpectatorKnown", "OpticsKnown", "VisibilityKnown",
                    "RecentVisibilityKnown", "NativeCombatKnown", "ProximityKnown", "RecentProximityKnown"):
            with self.subTest(key=key):
                self.assertEqual(0, self.evaluate(samples=[self.sample(), self.sample(2, **{key: False})]))
                self.assertEqual(-1., self.state.ClearSince)

    def test_visible_spectator_optics_combat_and_proximity_veto(self):
        for key, value in (("Visible", True), ("IsSpectator", True), ("UsingOptics", True),
                           ("InNativeCombat", True), ("Distance", 10.), ("LastVisibleAt", 99.),
                           ("LastNearAt", 99.)):
            with self.subTest(key=key):
                self.state = self.g.HCObserverTransitionState()
                self.assertTrue(self.g.Configure(self.state, self.policy))
                self.assertEqual(1, self.evaluate(samples=[self.sample(), self.sample(2, **{key: value})]))
        self.state = self.g.HCObserverTransitionState()
        self.assertTrue(self.g.Configure(self.state, self.policy))
        self.assertEqual(1, self.evaluate(InNativeCombat=True))

    def test_missing_duplicate_excess_observers_are_rejected_before_scan(self):
        for changes in (dict(Observers=None), dict(samples=[] , ExpectedObservers=1),
                        dict(ExpectedObservers=3), dict(ExpectedObservers=-1),
                        dict(samples=[self.sample(), self.sample()]),
                        dict(samples=[self.sample(0)]), dict(samples=[None]),
                        dict(samples=[self.sample(i) for i in range(1, 6)])):
            with self.subTest(changes=changes): self.assertEqual(0, self.evaluate(**changes))
        class NeverScan:
            def Count(self): return 1000000
            def __getitem__(self, index): raise AssertionError("overflow must reject before scan")
        self.assertEqual(0, self.evaluate(Observers=NeverScan(), ExpectedObservers=1000000))
        self.assertEqual(0, self.evaluate(Observers=NeverScan(), ExpectedObservers=2))

    def test_zero_observers_needs_explicit_complete_camera_coverage(self):
        self.warm(samples=[])
        self.assertEqual(0, self.evaluate(104., samples=[], SpectatorCoverageKnown=False))
        self.assertFalse(self.g.CanTransition())

    def test_nonfinite_future_stale_and_out_of_bounds_sample_values_reject(self):
        for key in ("ObservedAt", "Distance", "LastVisibleAt", "LastNearAt"):
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(key=key, value=value):
                    self.assertEqual(0, self.evaluate(samples=[self.sample(**{key: value})]))
        for key, value in (("ObservedAt", 101.), ("ObservedAt", 98.), ("ObservedAt", -1.),
                           ("Distance", -1.), ("Distance", 1001.), ("LastVisibleAt", 101.),
                           ("LastNearAt", 101.), ("LastVisibleAt", -2.), ("LastNearAt", -2.)):
            with self.subTest(key=key, value=value):
                self.assertEqual(0, self.evaluate(samples=[self.sample(**{key: value})]))

    def test_now_and_snapshot_history_validation_is_fail_closed(self):
        for now in (math.nan, math.inf, -math.inf, -1., 10001.):
            self.assertEqual(0, self.g.Evaluate(self.state, self.snapshot(), now))
        for key, value in (("CapturedAt", math.nan), ("CapturedAt", math.inf),
                           ("CapturedAt", 101.), ("CapturedAt", 98.), ("RosterRevision", 0),
                           ("LastTransitionAt", math.nan), ("LastTransitionAt", math.inf),
                           ("LastTransitionAt", 101.), ("LastTransitionAt", -2.)):
            with self.subTest(key=key, value=value): self.assertEqual(0, self.evaluate(**{key: value}))
        self.assertEqual(0, self.g.Evaluate(self.state, None, 100.))

    def test_grace_boundaries_and_transition_cooldown_reset_quiet_period(self):
        self.assertEqual(1, self.evaluate(LastTransitionAt=94., samples=[self.sample()]))
        self.assertEqual(2, self.evaluate(101., LastTransitionAt=94., samples=[
            self.sample(at=101., LastVisibleAt=96., LastNearAt=96.)]))
        self.assertEqual(2, self.evaluate(102., LastTransitionAt=94., samples=[self.sample(at=102.)]))
        self.assertEqual(0, self.evaluate(103., LastTransitionAt=93.))
        self.assertEqual(-1., self.state.ClearSince)
        self.assertEqual(0, self.evaluate(104., LastTransitionAt=-1.))

    def test_far_entry_near_exit_hysteresis_does_not_flap_in_middle_band(self):
        self.assertEqual(2, self.evaluate(samples=[self.sample(Distance=15.)]))
        self.assertEqual(-1., self.state.ClearSince)
        self.assertEqual(2, self.evaluate(101., samples=[self.sample(at=101., Distance=21.)]))
        for at in (102., 103.):
            self.assertEqual(2, self.evaluate(at, samples=[self.sample(at=at, Distance=15.)]))
        self.assertEqual(3, self.evaluate(104., samples=[self.sample(at=104., Distance=15.)]))
        self.assertEqual(1, self.evaluate(105., samples=[self.sample(at=105., Distance=10.)]))
        self.assertEqual(1, self.evaluate(106., samples=[self.sample(at=106., Distance=20.)]))
        self.assertEqual(2, self.evaluate(110., samples=[self.sample(at=110., Distance=20.)]))
        self.assertEqual(-1., self.state.ClearSince)
        self.assertEqual(2, self.evaluate(111., samples=[self.sample(at=111., Distance=21.)]))

    def test_veto_then_clear_requires_a_whole_new_quiet_window(self):
        self.warm()
        self.assertEqual(1, self.evaluate(104., samples=[self.sample(at=104.), self.sample(2, at=104., Visible=True)]))
        self.assertEqual(1, self.evaluate(108.))
        self.warm(start=109)

    def test_rollback_retains_high_water_and_cannot_reuse_quiet_evidence(self):
        self.warm()
        self.assertEqual(0, self.evaluate(102.))
        self.assertEqual(103., self.state.HighWater)
        self.assertEqual(0, self.evaluate(102.5))
        self.assertEqual(2, self.evaluate(104.))
        self.assertTrue(self.g.Configure(self.state, self.policy))
        self.assertEqual(0, self.evaluate(100.))

    def test_repeated_snapshots_or_repeated_observer_readings_cannot_age_into_ready(self):
        self.assertEqual(2, self.evaluate())
        self.assertEqual(0, self.g.Evaluate(self.state, self.snapshot(), 101.))
        self.assertEqual(0, self.evaluate(101., samples=[self.sample(at=100.)]))
        self.assertEqual(-1., self.state.ClearSince)
        self.assertEqual(2, self.evaluate(102.))

    def test_observer_timestamp_cannot_be_newer_than_snapshot(self):
        self.assertEqual(0, self.g.Evaluate(self.state, self.snapshot(99., samples=[self.sample(at=100.)]), 100.))

    def test_gap_or_roster_change_requires_new_window_and_roster_rollback_rejects(self):
        self.assertEqual(2, self.evaluate())
        self.assertEqual(2, self.evaluate(102.))  # TTL-sized gap resets continuity.
        self.assertEqual(2, self.evaluate(103., RosterRevision=2))
        self.assertEqual(103., self.state.ClearSince)
        self.assertEqual(0, self.evaluate(104., RosterRevision=1))
        self.assertEqual(0, self.evaluate(105., RosterRevision=2, samples=[]))
        self.assertEqual(2, self.evaluate(106., RosterRevision=3, samples=[]))

    def test_invalid_state_never_inherits_a_ready_window(self):
        for field in ("HighWater", "ClearSince", "LastSnapshotAt", "LastTransitionAt", "LastVisibilityAt", "LastProximityAt"):
            for value in (math.nan, math.inf, -math.inf, -2., 10001.):
                with self.subTest(field=field, value=value):
                    self.state = self.g.HCObserverTransitionState()
                    self.assertTrue(self.g.Configure(self.state, self.policy))
                    setattr(self.state, field, value)
                    self.assertEqual(0, self.evaluate())
        self.state = self.g.HCObserverTransitionState()
        self.assertTrue(self.g.Configure(self.state, self.policy))
        self.state.ClearSince = 101.
        self.assertEqual(0, self.evaluate())

    def test_visibility_and_proximity_history_cannot_be_erased_by_next_snapshot(self):
        for changes in ({"Visible": True}, {"Distance": 10.},
                        {"LastVisibleAt": 100.}, {"LastNearAt": 100.}):
            with self.subTest(changes=changes):
                self.state = self.g.HCObserverTransitionState()
                self.assertTrue(self.g.Configure(self.state, self.policy))
                self.assertEqual(1, self.evaluate(samples=[self.sample(), self.sample(2, **changes)]))
                self.assertEqual(1, self.evaluate(101.))
                for at in (102., 103., 104.): self.assertEqual(1, self.evaluate(at))
                self.warm(start=105)

    def test_exact_structural_cap_is_bounded_and_duplicate_last_observer_rejects(self):
        self.policy.MaxObservers = 32
        self.policy.MaxSamples = 32
        self.assertTrue(self.g.Configure(self.state, self.policy))
        results = []
        for at in range(100, 104):
            results.append(self.evaluate(float(at), samples=[self.sample(i, float(at)) for i in range(1, 33)]))
        self.assertEqual([2, 2, 2, 3], results)
        readings = [self.sample(i, 104.) for i in range(1, 33)]
        readings[-1].ObserverId = 1
        self.assertEqual(0, self.evaluate(104., samples=readings))
        self.assertEqual(-1., self.state.ClearSince)

    def test_unknown_input_after_ready_resets_continuity_and_recovery_rewarms(self):
        self.warm()
        self.assertEqual(0, self.evaluate(104., OpticsCoverageKnown=False))
        self.assertEqual(-1., self.state.ClearSince)
        self.warm(start=105)
        self.assertFalse(self.g.CanTransition())

    def test_existing_runtime_capabilities_remain_disabled(self):
        source = (SOURCE.parent / "HCInfectedPolicy.c").read_text()
        for name in ("CanAbstract", "CanMaterialize"):
            self.assertRegex(source, r"static bool " + name + r"\(\)\s*\{\s*return false;\s*\}")
        self.assertFalse(self.g.CanTransition())


if __name__ == "__main__": unittest.main()
