"""Execute authored scalar policies; wiring checks are not engine acceptance."""
import math
import re
import unittest

if __package__:
    from .test_infected_contract import SOURCE, policy_functions
else:
    from test_infected_contract import SOURCE, policy_functions


class InfectedWaveTests(unittest.TestCase):
    def test_no_known_enforce_keywords_as_new_parameters_or_locals(self):
        for path in SOURCE.glob("*.c"):
            self.assertIsNone(re.search(r"\b(?:bool|float|int|vector|string)\s+(?:owned|local)\b", path.read_text()), path.name)

    def test_terminal_cohort_retains_last_observed_population_count(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        finish = module.split("protected void FinishSweep", 1)[1].split("protected void TryAdopt", 1)[0]
        self.assertRegex(finish, r"if \(record.State == 5\)\s*\{\s*RefundRetired\(record, nowUtc\);\s*continue;\s*\}")

    def test_all_seven_descriptors_and_explicit_unsupported_fallback(self):
        p = policy_functions()["ResolveVariant"]
        self.assertEqual([0, 1, 2, 0, 0, 5], [p(i) for i in range(6)])
        disposition = policy_functions()["VariantDisposition"]
        self.assertEqual(["supported", "supported", "supported",
                          "unsupported_substituted_native", "unsupported_substituted_native",
                          "supported"], [disposition(i) for i in range(6)])
        for invalid in (-1, 6, 7, 100):
            self.assertEqual(-1, p(invalid))
        profiles = (SOURCE / "HCInfectedProfiles.c").read_text()
        for label in ("ordinary_wanderer", "reactive_infected", "persistent_searcher",
                      "careful_stalker", "forceful_heavy", "group_responder", "injured_crawler"):
            self.assertIn(label, profiles)
        self.assertIn("HCInfectedPolicy.ResolveVariant", profiles)

    def test_variant_attention_and_search_are_bounded_and_injury_is_overlay(self):
        p = policy_functions()
        lifetime = p["VariantLifetime"]
        anchors = p["VariantAnchorBudget"]
        self.assertLess(lifetime(0, 0, False), lifetime(2, 0, False))
        self.assertLess(lifetime(1, 0, False), lifetime(2, 0, False))
        for variant in range(6):
            for stance in range(4):
                self.assertTrue(0 < lifetime(variant, stance, False) <= 30)
                self.assertEqual(6 + stance, lifetime(variant, stance, True))
            self.assertEqual(0, anchors(variant, True))
        self.assertEqual([1, 1, 3, 1, 1, 2], [anchors(v, False) for v in range(6)])
        self.assertEqual(0, lifetime(-1, 0, False))
        self.assertEqual(0, lifetime(0, 4, False))

    def test_profiles_use_explicit_maps_and_keep_base_stable_across_injury(self):
        state = (SOURCE / "HCInfectedState.c").read_text()
        profiles = (SOURCE / "HCInfectedProfiles.c").read_text()
        self.assertIn("bool EnableVariantPolicies = true", state)
        self.assertIn("CivilianVariants = new array<int>", state)
        self.assertIn("MilitaryVariants = new array<int>", state)
        self.assertIn("count != 4", profiles)
        self.assertIn("config.CivilianVariants", profiles)
        self.assertIn("config.MilitaryVariants", profiles)
        self.assertIn("InitializeProfile(m_Config)", (SOURCE / "HCInfectedModule.c").read_text())
        refresh = state.split("void RefreshProfile()", 1)[1].split("class HCInfectedVoice", 1)[0]
        self.assertIn("VariantLifetime(BaseVariant", refresh)
        self.assertIn("VariantAnchorBudget(BaseVariant", refresh)
        self.assertNotIn("BaseVariant =", refresh)
        self.assertIn("actors[0].SearchAnchorLimit", (SOURCE / "HCInfectedNavigation.c").read_text())

    def test_visible_evidence_has_priority_then_newer_then_stronger(self):
        p = policy_functions()["PreferStimulus"]
        self.assertTrue(p(5, 2, 1., 9, 1, 1.))
        self.assertFalse(p(9, 1, 1., 5, 2, 1.))
        self.assertTrue(p(9, 1, .5, 8, 1, 1.))
        self.assertFalse(p(8, 1, 1., 9, 1, .5))
        self.assertTrue(p(9, 1, 1., 9, 1, .5))
        self.assertFalse(p(9, 1, .5, 9, 1, .5))

    def test_retarget_requires_live_fresh_owned_evidence_and_budget(self):
        p = policy_functions()["RetargetAllowed"]
        valid = [10, 10, 9, -1, 20, 0, True, False]
        self.assertTrue(p(*valid))
        for index, value in ((0, 20), (0, math.nan), (1, 11), (2, 11),
                             (2, -1), (3, 9), (4, 50), (5, 2), (5, -1),
                             (6, False), (7, True)):
            args = valid.copy()
            args[index] = value
            self.assertFalse(p(*args), args)
        # A cue may be accepted just before expiry, never at expiry.
        self.assertTrue(p(19.9, 10, 9, -1, 20, 1, True, False))
        self.assertFalse(p(20, 10, 9, -1, 20, 1, True, False))

    def test_frozen_clue_excludes_self_voice_and_does_not_refresh_expiry(self):
        source = (SOURCE / "HCHordeStimulus.c").read_text()
        self.assertIn("actor.HeardExternally", source)
        self.assertIn("actor.Visual", source)
        self.assertIn("IsLive(now)", source)
        self.assertIn("frozenClue.Origin = candidate.Origin", source)
        self.assertIn("frozenClue.Expires = candidate.Expires", source)
        self.assertNotIn("candidate.Expires =", source)
        self.assertNotIn("GetTargetEntity", source)
        self.assertNotIn("actor.Clue", source)

    def test_retarget_updates_only_existing_pack_without_membership_transfer(self):
        source = (SOURCE / "HCInfectedNavigation.c").read_text()
        method = source.split("int Retarget(", 1)[1].split("bool Tick(float now)", 1)[0]
        for required in ("RetargetAllowed", "Reachable(", "currentAgent.GetGroup() != Group",
                         "MINDSTATE_CHASE", "MINDSTATE_FIGHT", "SetWaypoints API",
                         "clue.Expires", "m_NextRetarget", "m_RetargetAttempts"):
            self.assertIn(required, method)
        for forbidden in ("AddAgent(", "RemoveAgent(", "CreateGroup(", "CreateObject", "GetTargetEntity"):
            self.assertNotIn(forbidden, method)

    def test_cohort_route_clue_is_wired_and_work_reserved(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        self.assertIn("HCHordeStimulus.ChooseClue", module)
        self.assertIn("sweep.Stimulus", module)
        self.assertIn(".Retarget(sweep.Stimulus, m_Now)", module)
        self.assertIn("m_RoutesRemaining--", module)
        self.assertIn("retargetReserve", module)
        self.assertIn("bool EnableHordeStimulusRoutes = true", (SOURCE / "HCInfectedState.c").read_text())

    def test_missing_member_never_counts_as_confirmed_death(self):
        p = policy_functions()["CompleteMembership"]
        self.assertTrue(p(6, 6, 0, 6, False))
        self.assertTrue(p(6, 4, 2, 6, False))
        for args in ((6, 4, 0, 4, False), (6, 4, 2, 6, True),
                     (6, 5, 2, 6, False), (6, 6, 0, 5, False),
                     (7, 7, 0, 7, False), (6, -1, 7, 6, False)):
            self.assertFalse(p(*args), args)

    def test_group_ambiguity_latches_without_reservation_refund(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        finish = module.split("protected void FinishSweep", 1)[1].split("protected void TryAdopt", 1)[0]
        self.assertIn("CompleteMembership", finish)
        self.assertIn("record.RecoveryConflicted = true", finish)
        self.assertIn("record.State = 6", finish)
        self.assertNotIn("record.Reserved =", finish)
        refund = module.split("protected void RefundRetired", 1)[1].split("protected void TryAdopt", 1)[0]
        self.assertIn("record.State != 5 || record.BudgetReleased", refund)
        self.assertEqual(1, module.count("m_State.Reserved -= record.Reserved;"))
        self.assertIn("m_State.Reserved -= record.Reserved;", refund)
        self.assertIn("ConfirmedDead", module)
        tracking = module.split("bool Track(", 1)[1].split("void NativeVoice", 1)[0]
        self.assertIn("CanRecycleActor", tracking)

    def test_ambiguous_membership_cannot_expire_or_refund_even_with_recovery_admitted(self):
        from tests.unit.test_infected_admission import StartedModule, hypothetical, prepared_record
        for living in (0, 3):
            record = prepared_record(1, created=10000)
            record.Living = living
            started = StartedModule(journal=(record,), flags=hypothetical("MemberRecovery")).start()
            for age in (3599, 3600, 20000):
                started.tick(10000 + age)
                retained = started.ctx.m_State.Groups[0]
                self.assertEqual(6, retained.State)
                self.assertFalse(retained.BudgetReleased)
                self.assertEqual(3, started.ctx.m_State.Reserved)

    def test_v2_drift_never_reaches_ecology_v1_submission(self):
        from tests.unit.test_infected_admission import Array, admission, module_call, requested_config
        from types import SimpleNamespace as NS
        for drift, complete, expected in ((True, True, []), (True, False, []),
                                          (False, True, ["ecology", "retarget"]), (False, False, [])):
            with self.subTest(drift=drift, complete=complete):
                calls = []
                pack = NS(IsV2Drifting=lambda: drift, Retarget=lambda *a: calls.append("retarget") or 2)
                ctx = NS(m_Sweeps=Array([NS(Engaged=False, Clue=True, Stimulus=NS(IsLive=lambda now: True),
                            Living=3, ConfirmedDead=0, Accounted=3 if complete else 2, Ambiguous=False)]),
                    m_State=NS(Groups=Array([NS(Id=1, State=1, Reserved=3)])), m_Packs=Array([pack]),
                    m_Config=requested_config(), m_RoutesRemaining=1, m_RetargetCursor=0, m_Now=100,
                    m_Actors=Array(), SnapshotRoute=lambda *a: None,
                    m_Admission=admission(Investigation=True, SupplementaryChains=True))
                module_call("protected void RetargetCohorts(", ctx,
                    HCInfectedPolicy=NS(**policy_functions()),
                    HCEcologyMigrationQualification=NS(Admitted=lambda: True),
                    HCEcologyMigration=NS(SubmitCohort=lambda *a: calls.append("ecology") or 0))
                self.assertEqual(expected, calls)
                self.assertEqual(0 if expected else 1, ctx.m_RoutesRemaining)
        migration = (SOURCE / "HCHordeMigration.c").read_text()
        self.assertRegex(migration, r"override bool IsV2Drifting\(\)\s*\{\s*return m_V2Drift;\s*\}")

    def test_confirmed_retirement_waits_for_release_then_refunds_only_once(self):
        from tests.unit.test_infected_admission import StartedModule, hypothetical, committed_record
        from types import SimpleNamespace as NS
        record = committed_record()
        record.State = 5
        started = StartedModule(journal=(record,), flags=hypothetical("MemberRecovery")).start()
        released = [False]
        started.ctx.m_Packs[0] = NS(Release=lambda: released[0], RoutePlanned=0)
        for ready in (False, True, True):
            released[0] = ready
            started.ctx.FinishSweep(20000)
            retained = started.ctx.m_State.Groups[0]
            self.assertEqual(3, retained.Living)
            self.assertEqual(ready, retained.BudgetReleased)
            self.assertEqual(0 if ready else 3, started.ctx.m_State.Reserved)
        self.assertEqual(1, sum("infected horde budget used=" in e for e in started.events if isinstance(e, str)))

    def test_releasing_an_ambiguous_pack_does_not_resolve_its_membership(self):
        from tests.unit.test_infected_admission import StartedModule, hypothetical, prepared_record
        from types import SimpleNamespace as NS
        started = StartedModule(journal=(prepared_record(1),), flags=hypothetical("MemberRecovery")).start()
        started.ctx.m_Packs[0] = NS(Tick=lambda now: False, RoutePlanned=0)
        started.tick(20000)
        retained = started.ctx.m_State.Groups[0]
        self.assertIsNone(started.ctx.m_Packs[0])
        self.assertEqual(6, retained.State)
        self.assertFalse(retained.BudgetReleased)
        self.assertEqual(3, started.ctx.m_State.Reserved)


if __name__ == "__main__":
    unittest.main()
