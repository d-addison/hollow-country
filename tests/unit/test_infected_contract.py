"""Execute scalar Enforce policy bodies on explicit synthetic fixtures.

The restricted translator tests shipped decisions, not a duplicate Python model.
It is deliberately not an Enforce compiler or evidence about native DayZ AI.
"""
import json
import math
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "mods/HollowCountry/scripts/4_World/Infected"
FIXTURE = ROOT / "tests/fixtures/runtime/infected-policy.json"


def policy_functions():
    source = (SOURCE / "HCInfectedPolicy.c").read_text()
    source = re.sub(r"//[^\n]*", "", source)
    namespace = {}
    pattern = r"static (?:bool|int|float) (\w+)\(([^)]*)\)\s*\{"
    for match in re.finditer(pattern, source):
        depth, end = 1, match.end()
        while depth:
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        body = source[match.end():end - 1]
        args = [arg.strip().split()[-1] for arg in match[2].split(",") if arg.strip()]
        lines = [f"def {match[1]}({', '.join(args)}):"]
        indent = 1
        # Only the intentionally scalar policy subset is supported. Unknown syntax
        # causes a SyntaxError instead of silently approximating engine semantics.
        for token in re.split(r"([{};])", body):
            token = token.strip()
            if not token or token == ";":
                continue
            if token == "{":
                indent += 1
                continue
            if token == "}":
                indent -= 1
                continue
            token = re.sub(r"\b(?:int|float|bool)\s+", "", token)
            token = token.replace("&&", " and ").replace("||", " or ")
            token = re.sub(r"!(?!=)", "not ", token)
            token = re.sub(r"\btrue\b", "True", token)
            token = re.sub(r"\bfalse\b", "False", token)
            if token.startswith("if ("):
                token = "if " + token[4:-1] + ":"
            elif token == "else":
                token += ":"
            lines.append("    " * indent + token)
        exec(compile("\n".join(lines), str(SOURCE / "HCInfectedPolicy.c"), "exec"), namespace)
    return namespace


class InfectedContractTests(unittest.TestCase):
    def test_low_budget_adoption_rotates_past_already_assigned_members(self):
        policy = policy_functions()
        cursor = 0
        visited = []
        for interval in range(2):
            batch = []
            for step in range(3):
                batch.append(cursor)
                cursor = policy["NextAdoptionCursor"](cursor, 6)
            visited.append(batch)
        self.assertEqual([[0, 1, 2], [3, 4, 5]], visited)
        module = (SOURCE / "HCInfectedModule.c").read_text()
        adoption = module.split("protected void TryAdopt", 1)[1].split("protected void TryInvestigate", 1)[0]
        self.assertIn("HCInfectedPolicy.NextAdoptionCursor", adoption)
        self.assertIn("m_Actors[m_AdoptionCursor]", adoption)

    def test_cohort_budget_requires_capacity_for_three_candidates(self):
        policy = policy_functions()
        for work in range(1, 10):
            self.assertEqual(work >= 9, policy["AdoptionWorkReady"](work))
        self.assertIn("HCInfectedPolicy.AdoptionWorkReady(m_WorkCap)", (SOURCE / "HCInfectedModule.c").read_text())

    def test_failed_release_retains_bounded_retry_ownership(self):
        navigation = (SOURCE / "HCInfectedNavigation.c").read_text()
        module = (SOURCE / "HCInfectedModule.c").read_text()
        self.assertIn("s_PendingRelease", navigation)
        self.assertIn("RetryPendingReleases", navigation)
        self.assertIn("HCNativeInfectedPack.RetryPendingReleases();", module)
        self.assertIn("s_PendingRelease.Insert(this)", navigation)
        self.assertIn("s_PendingRelease.RemoveItem(this)", navigation)

    def test_route_membership_and_persisted_active_marker_are_reconciled(self):
        navigation = (SOURCE / "HCInfectedNavigation.c").read_text()
        module = (SOURCE / "HCInfectedModule.c").read_text()
        tick = navigation.split("bool Tick(float now)", 1)[1].split("bool Release()", 1)[0]
        self.assertIn("currentAgent.GetGroup() == Group", tick)
        self.assertIn("HCInfectedPolicy.CountsOwnedMember", tick)
        self.assertIn("record.HasRoute = false", module)

    @classmethod
    def setUpClass(cls):
        cls.p = policy_functions()
        cls.fixture = json.loads(FIXTURE.read_text())

    def test_fixtures_explicitly_synthetic(self):
        self.assertEqual("synthetic-policy-only", self.fixture["evidence"])

    def test_observation_expires_and_never_accepts_future_or_unknown_provenance(self):
        p = self.p["AcceptClue"]
        self.assertTrue(p(100, 99, 110, 1, 1.0, 0))
        self.assertTrue(p(100, 99, 110, 2, 1.0, 0))
        for args in [(110, 99, 110, 1, 1., 0), (98, 99, 110, 1, 1., 0),
                     (100, 99, 110, 0, 1., 0), (100, 99, 200, 1, 1., 0),
                     (100, 99, 110, 1, 0., 0), (100, 99, 110, 1, 2., 0),
                     (100, 99, 110, 1, 1., 3), (100, 99, 110, 1, 1., -1),
                     (math.nan, 99, 110, 1, 1., 0)]:
            with self.subTest(args=args):
                self.assertFalse(p(*args))

    def test_chain_overload_dedupe_cooldown_ttl_hops_and_attenuation(self):
        p = self.p["AdmitVoice"]
        # now, nextAllowed, queue size/cap, per-tick work/cap, source alive,
        # native noise params, duplicate, hop, strength, expiry
        valid = [100, 99, 0, 16, 0, 8, True, True, False, 0, 1., 110]
        self.assertTrue(p(*valid))
        for index, value in [(1, 101), (2, 16), (4, 8), (6, False),
                             (7, False), (8, True), (9, 2), (9, -1),
                             (10, .1), (10, 2.), (11, 100), (11, 200)]:
            args = valid.copy()
            args[index] = value
            with self.subTest(index=index, value=value):
                self.assertFalse(p(*args))
        strength = 1.
        for _ in range(2):
            strength = self.p["Attenuate"](strength)
        self.assertLess(strength, .5)

    def test_population_reservation_counts_unresolved_and_never_refills_losses(self):
        p = self.p["CanReserve"]
        self.assertTrue(p(0, 2, 0, 24, 6))
        self.assertFalse(p(2, 2, 6, 24, 1))
        self.assertFalse(p(1, 2, 24, 24, 1))
        self.assertFalse(p(1, 2, 23, 24, 2))
        self.assertFalse(p(0, 2, 0, 24, -1))
        self.assertFalse(p(0, 2, 0, 24, 25))
        self.assertFalse(p(0, 3, 0, 24, 1))
        self.assertFalse(p(0, 2, 0, 25, 1))
        # Native CE accounting/identity/observer proofs are not exposed here:
        # no amount of spare capacity permits materialization or abstraction.
        self.assertFalse(self.p["CanMaterialize"]())
        self.assertFalse(self.p["CanAbstract"]())

    def test_horde_finite_lifecycle_and_escape_without_new_clues(self):
        state = 0
        for event in self.fixture["lifecycle"]:
            state = self.p["NextHordeState"](state, *event["inputs"])
            self.assertEqual(event["state"], state)
        self.assertEqual(5, state)
        self.assertEqual(5, self.p["NextHordeState"](5, 6, True, True, 0, 1))
        self.assertEqual(5, self.p["NextHordeState"](2, 0, True, True, 0, 1))
        self.assertEqual(5, self.p["NextHordeState"](3, 6, True, True, 0, 3600))

    def test_restart_does_not_rebind_or_replenish_unresolved_entities(self):
        for state in range(5):
            self.assertEqual(6, self.p["AfterRestart"](state))
        self.assertEqual(5, self.p["AfterRestart"](5))
        self.assertEqual(6, self.p["AfterRestart"](6))
        self.assertEqual(6, self.p["NextHordeState"](6, 6, True, True, 0, 1))
        self.assertEqual(5, self.p["NextHordeState"](6, 0, False, False, 100, 3600))

    def test_snapshot_rejects_corruption_world_mismatch_and_clock_rollback(self):
        p = self.p["ValidSnapshotHeader"]
        self.assertTrue(p(1, True, 1, 2, 12, 24, 100, 101))
        for args in [(2, True, 1, 2, 12, 24, 100, 101),
                     (1, False, 1, 2, 12, 24, 100, 101),
                     (1, True, 1, 3, 12, 24, 100, 101),
                     (1, True, 1, 2, 25, 24, 100, 101),
                     (1, True, 1, 2, 12, 24, 100, 99),
                     (1, True, 0, 2, 12, 24, 100, 101)]:
            self.assertFalse(p(*args))

    def test_snapshot_member_ledger_rejects_missing_fields_and_refill(self):
        p = self.p["ValidGroupRecord"]
        self.assertTrue(p(1, 0, 6, 4, 3, 100, 110, 120))
        for index, value in [(0, 2), (2, 7), (2, -1), (3, 7), (3, -1),
                             (4, -1), (4, 7), (5, 121), (6, 99), (6, 121)]:
            args = [1, 0, 6, 4, 3, 100, 110, 120]
            args[index] = value
            self.assertFalse(p(*args))
        p = self.p["ValidGenerationPair"]
        self.assertTrue(p(2, 1, 1, 1, 120, 110, 12, 6, 2, 1))
        for index, value in [(0, 3), (2, 2), (4, 100), (6, 5), (8, 0)]:
            args = [2, 1, 1, 1, 120, 110, 12, 6, 2, 1]
            args[index] = value
            self.assertFalse(p(*args))

    def test_profile_tradeoffs_preserve_native_variation_and_injuries(self):
        p = self.p["ProfileLifetime"]
        for stance in range(4):
            self.assertLess(p(True, False, stance), p(False, False, stance))
            self.assertLess(p(False, True, stance), p(True, False, stance))
            self.assertLessEqual(p(False, False, stance), 30)
        self.assertEqual(0, p(False, False, -1))
        self.assertEqual(0, p(False, False, 4))
        anchors = self.p["SearchAnchorBudget"]
        self.assertEqual(3, anchors(False, False))
        self.assertEqual(1, anchors(True, False))
        self.assertEqual(0, anchors(True, True))

    def test_persisted_membership_cannot_be_refilled_or_retired_group_reactivated(self):
        p = self.p["CanAdvanceRecord"]
        self.assertTrue(p(1, 1, 6, 6, 5, 4, 3, 4, 100, 100))
        self.assertFalse(p(1, 1, 6, 6, 4, 5, 3, 3, 100, 100))
        self.assertFalse(p(1, 1, 6, 5, 4, 4, 3, 3, 100, 100))
        self.assertFalse(p(1, 1, 6, 6, 4, 4, 5, 3, 100, 100))
        self.assertFalse(p(1, 1, 6, 6, 4, 4, 6, 3, 100, 100))
        self.assertFalse(p(1, 1, 6, 6, 4, 4, 3, 3, 100, 101))
        self.assertTrue(p(1, 1, 6, 6, 4, 4, 3, 6, 100, 100))

    def test_route_search_gives_up_on_native_combat_injury_expiry_or_stall(self):
        p = self.p["MayInvestigate"]
        self.assertTrue(p(True, True, False, False, False, 0, 2, 2))
        for index, value in [(0, False), (1, False), (2, True), (3, True),
                             (4, True), (5, 3), (6, 1)]:
            args = [True, True, False, False, False, 0, 2, 2]
            args[index] = value
            self.assertFalse(p(*args))
        p = self.p["RouteAlive"]
        self.assertTrue(p(10, 20, 1, True, False))
        self.assertFalse(p(20, 20, 1, True, False))
        self.assertFalse(p(10, 20, 16, True, False))
        self.assertFalse(p(10, 20, 1, False, False))
        self.assertFalse(p(10, 20, 1, True, True))

    def test_native_pack_route_uses_observed_surfaces_not_manual_steering(self):
        source = (SOURCE / "HCInfectedNavigation.c").read_text()
        for surface in ("SampleNavmeshPosition", "FindPath", "DZInfectedPackBeh",
                        "BehaviourGroupInfectedPack.Cast", "SetWaypoints(",
                        "RemoveAgent(", "AddAgent("):
            self.assertIn(surface, source)
        self.assertNotIn("OverrideHeading(", source)
        self.assertNotIn("SetKeepInIdle(", source)

    def test_visual_memory_requires_native_candidate_and_both_geometry_proofs(self):
        p = self.p["DirectlyObserved"]
        self.assertTrue(p(True, 100, .8, True, True))
        for args in [(False, 100, .8, True, True), (True, 401, .8, True, True),
                     (True, 100, .4, True, True), (True, 100, .8, False, True),
                     (True, 100, .8, True, False), (True, math.nan, .8, True, True)]:
            self.assertFalse(p(*args))

    def test_release_retry_budget_preserves_ownership_and_adoption_has_three_slots(self):
        p = self.p["MayRetryRelease"]
        self.assertTrue(p(0, 100, 100))
        self.assertFalse(p(1, 100, 105))
        self.assertTrue(p(2, 105, 105))
        self.assertFalse(p(3, 110, 105))
        p = self.p["AdoptionWorkReady"]
        self.assertFalse(p(8))
        self.assertTrue(p(9))
        self.assertTrue(p(32))
        p = self.p["CountsOwnedMember"]
        self.assertTrue(p(True, True, True))
        self.assertFalse(p(True, True, False))
        self.assertFalse(p(True, False, True))
        self.assertFalse(p(False, True, True))

    def test_native_attack_contact_gate_and_no_custom_damage(self):
        p = self.p["SuppressStrike"]
        self.assertTrue(p(True, True, False))
        self.assertFalse(p(True, True, True))
        self.assertFalse(p(False, True, False))
        source = (SOURCE / "HCInfectedNative.c").read_text()
        self.assertIn("CanAttackToPosition", source)
        self.assertIn("super.FightLogic", source)
        self.assertIn("super.ProcessSoundVoiceEvent", source)
        self.assertNotIn("CloseCombatDamage", source)

    def test_module_registration_authority_and_no_physics_or_audio_shortcuts(self):
        source = "\n".join(p.read_text() for p in SOURCE.glob("*.c"))
        self.assertIn("modded class HCModuleRegistry", source)
        self.assertIn("super.RegisterModules()", source)
        self.assertIn("settings.EnableInfected", source)
        self.assertIn("GetGame().IsServer()", source)
        for forbidden in ("SetPosition(", "CreateObject", "ObjectDelete(",
                          "OverrideMovementSpeed(", "OverrideHeading(",
                          "OverrideAlertLevel(", "AddNoise(",
                          "AddNoiseTarget(", "SetHealth(", "OpenDoor("):
            self.assertFalse(forbidden in source, forbidden)
        # The only native target lookup belongs to the bounded visual sensor.
        navigation = (SOURCE / "HCInfectedNavigation.c").read_text()
        self.assertEqual(1, source.count("GetTargetEntity("))
        self.assertIn("ObjIntersectView", navigation)
        self.assertIn("ObjIntersectFire", navigation)
        self.assertIn("vector.Dot", navigation)


if __name__ == "__main__":
    unittest.main()
