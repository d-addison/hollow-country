"""Source-policy regressions only; no claim to emulate DayZ native execution."""
import json
import re
from functools import cmp_to_key
from pathlib import Path
import unittest

if __package__:
    from tests.legacy.test_infected_contract import SOURCE, policy_functions
else:
    from tests.legacy.test_infected_contract import SOURCE, policy_functions


class InfectedCompletionTests(unittest.TestCase):
    def test_native_centroid_uses_supported_vector_multiplication(self):
        weight = policy_functions()["CentroidWeight"]
        for count in (1, 2, 3, 6):
            self.assertAlmostEqual(1.0 / count, weight(count))
        for count in (-1, 0, 7):
            self.assertEqual(0, weight(count))
        module = (SOURCE / "HCInfectedModule.c").read_text()
        self.assertNotIn("sweep.Sum / living", module)
        self.assertIn("sweep.Sum * HCInfectedPolicy.CentroidWeight(living)", module)

    def test_native_formula_complexity_regression_has_small_boolean_expressions(self):
        for path in SOURCE.glob("*.c"):
            source = re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(), flags=re.S)
            for expression in re.split(r"[;{}]", source):
                with self.subTest(path=path.name, expression=expression.strip()[:80]):
                    self.assertLessEqual(expression.count("&&") + expression.count("||"), 6)

    def test_audited_native_type_names_do_not_collide_with_infected_declarations(self):
        # Actual intersection with 7,455 installed class/enum/typedef names found
        # HouseType, Building and Step after the previous World/Entity repairs.
        audited = {"World", "Entity", "HouseType", "Building", "Step"}
        for path in SOURCE.glob("*.c"):
            source = re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(), flags=re.S)
            for line in source.splitlines():
                match = re.match(r"^\s*(?:(?:protected|private|static|ref|autoptr|const|override)\s+)*(\w+(?:<[^;=()]+>)?)\s+(\w+)\b", line)
                if match and match[1] not in {"class", "enum", "return", "typedef"}:
                    self.assertNotIn(match[2], audited, f"{path.name}: {line.strip()}")

    def test_real_compiler_reserved_type_collisions_are_removed(self):
        for path in SOURCE.glob("*.c"):
            with self.subTest(path=path.name):
                self.assertIsNone(re.search(r"\b(?:string\s+World|ZombieBase\s+Entity|AIWorld\s+World)\b", path.read_text()))

    def test_real_compiler_keywords_and_accidental_api_rename_are_removed(self):
        for path in SOURCE.glob("*.c"):
            source = path.read_text()
            with self.subTest(path=path.name):
                self.assertNotIn("GetGetAIWorld", source)
                self.assertIsNone(re.search(r"\b(?:HCInfectedRoomSurvey\s+owned|vector\s+local)\b", source))
        self.assertIn("HCBuildIdentity.SameWorld(survey.WorldName, GetGame().GetWorldName())", (SOURCE / "HCInfectedRooms.c").read_text())
        self.assertIn("GetGame().GetWorldName()", (SOURCE / "HCInfectedModule.c").read_text())
    def test_given_native_voices_when_chain_progresses_then_limits_and_dedupe_hold(self):
        scenarios = json.loads((Path(__file__).parents[1] / "fixtures/runtime/infected-completion-scenarios.json").read_text())
        self.assertIn("synthetic-policy-only", scenarios["evidence"])
        policy = policy_functions()
        for case in scenarios["relay_checks"]:
            with self.subTest(given=case["given"]):
                self.assertEqual(case["then"], policy["MayRelay"](*case["when"]))
        seen = {"seed"}
        for case in scenarios["hearing_checks"]:
            accepted = policy["MayHearRelay"](
                case["now"], scenarios["root"]["expires"], 1, .5,
                case["distance_sq"], len(seen), scenarios["root"]["recipient_cap"],
                case["recipient"] in seen, True, case["geometry"], 0)
            self.assertEqual(case["then"], accepted, case)
            if accepted:
                seen.add(case["recipient"])
        self.assertEqual({"seed", "near", "second", "third"}, seen)

    def test_given_surveyed_rooms_when_ordered_then_ties_are_deterministic(self):
        scenarios = json.loads((Path(__file__).parents[1] / "fixtures/runtime/infected-completion-scenarios.json").read_text())
        prefer = policy_functions()["PreferRoom"]

        def compare(a, b):
            if a == b:
                return 0
            return -1 if prefer(a["clue_room"], b["clue_room"], a["distance_sq"],
                                b["distance_sq"], a["id"], b["id"]) else 1

        rooms = scenarios["rooms"]
        expected = scenarios["expected_room_order"]
        self.assertEqual(expected, [r["id"] for r in sorted(rooms, key=cmp_to_key(compare))])
        self.assertEqual(expected, [r["id"] for r in sorted(reversed(rooms), key=cmp_to_key(compare))])

    def test_chain_root_lifetime_hops_and_strength_are_inherited(self):
        p = policy_functions()["MayRelay"]
        self.assertTrue(p(12, 10, 25, 1, .5, True, True))
        for args in [(25, 10, 25, 1, .5, True, True),
                     (12, 10, 25, 2, .25, True, True),
                     (12, 13, 25, 0, 1., True, True),
                     (12, 10, 50, 0, 1., True, True),
                     (12, 10, 25, 1, .1, True, True),
                     (12, 10, 25, 1, .5, False, True),
                     (12, 10, 25, 1, .5, True, False)]:
            self.assertFalse(p(*args), args)

    def test_chain_recipients_are_bounded_deduped_occluded_and_rate_limited(self):
        p = policy_functions()["MayHearRelay"]
        valid = [12, 25, 1, .5, 25, 0, 12, False, True, True, 10]
        self.assertTrue(p(*valid))
        for index, value in [(0, 25), (2, 3), (3, .1), (4, 226),
                             (4, -1), (5, 12), (6, 13), (7, True),
                             (8, False), (9, False), (10, 13)]:
            args = valid.copy()
            args[index] = value
            self.assertFalse(p(*args), args)

    def test_root_dedupe_expires_without_extending_old_roots(self):
        p = policy_functions()["RootSlotReusable"]
        self.assertFalse(p(24, 25))
        self.assertTrue(p(25, 25))
        self.assertFalse(p(-1, 25))
        self.assertFalse(p(float("nan"), 25))

    def test_room_order_is_clue_first_then_distance_and_stable_id(self):
        p = policy_functions()["PreferRoom"]
        self.assertTrue(p(True, False, 20, 1, 9, 1))
        self.assertFalse(p(False, True, 1, 20, 1, 9))
        self.assertTrue(p(False, False, 4, 9, 7, 1))
        self.assertTrue(p(False, False, 4, 4, 1, 2))
        self.assertFalse(p(False, False, 4, 4, 2, 1))

    def test_room_admission_needs_measurement_and_bounded_catalog(self):
        p = policy_functions()["AdmitRoomCatalog"]
        self.assertTrue(p(True, True, 1, 6, 1, 4))
        for args in [(False, True, 1, 6, 1, 4), (True, False, 1, 6, 1, 4),
                     (True, True, 0, 6, 1, 4), (True, True, 1, 7, 1, 4),
                     (True, True, 1, 6, 4, 4)]:
            self.assertFalse(p(*args), args)

    def test_recovery_identity_never_uses_zero_or_partial_match(self):
        p = policy_functions()["ValidMemberIdentity"]
        self.assertFalse(p(0, 0, 0, 0, True))
        self.assertTrue(p(0, -1, 0, 0, True))
        self.assertFalse(p(1, 2, 3, 4, False))
        match = policy_functions()["MayRecoverMember"]
        valid = [True, True, True, True, False, False, 6, 100, 101, 0, 4]
        self.assertTrue(match(*valid))
        for index, value in [(0, False), (1, False), (2, False), (3, False),
                             (4, True), (5, True), (6, 5), (7, 102),
                             (8, 3700), (9, 4)]:
            args = valid.copy()
            args[index] = value
            self.assertFalse(match(*args), args)

    def test_recovered_cohort_requires_complete_count_and_preserves_escrow(self):
        p = policy_functions()["RecoveryComplete"]
        self.assertTrue(p(4, 4, 6, False))
        self.assertFalse(p(3, 4, 6, False))
        self.assertFalse(p(5, 4, 6, False))
        self.assertFalse(p(4, 4, 6, True))
        self.assertFalse(p(0, 0, 6, False))

    def test_audio_chain_native_emitter_and_root_provenance_wiring(self):
        source = (SOURCE / "HCAlertChain.c").read_text()
        module = (SOURCE / "HCInfectedModule.c").read_text()
        for surface in ("RootId", "RootObserved", "RootExpires", "Recipients",
                        "MayHearRelay", "ObjIntersectView", "ObjIntersectFire"):
            self.assertIn(surface, source)
        self.assertIn("m_AlertChain.NativeEmission", module)
        self.assertIn("m_AlertChain.ProcessPending", module)
        self.assertNotIn("OnSoundVoiceEvent(", source)
        self.assertNotIn("AddNoise(", source)

    def test_recovery_and_relay_wiring_sit_behind_admitted_capability_not_preference(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        tick = module.split("override void OnTick", 1)[1]
        self.assertLess(tick.index("m_Admission.MemberRecovery"), tick.index("HCHordeRecovery.Reconcile"))
        self.assertLess(tick.index("m_Admission.SupplementaryChains"), tick.index("m_AlertChain.ProcessPending"))
        voice = module.split("void NativeVoice(", 1)[1].split("protected void ResetSweep", 1)[0]
        self.assertLess(voice.index("m_Admission.SupplementaryChains"), voice.index("m_AlertChain.NativeEmission"))
        investigation = module.split("protected void TryInvestigate", 1)[1].split("protected void ReleasePacks", 1)[0]
        self.assertIn("HeardAdmitted() && actor.HeardExternally", investigation)
        self.assertIn("return m_Chains && m_Admission.SupplementaryChains;", module)
        self.assertIn("MayInvestigate(m_Admission.Investigation,", investigation)
        for name in ("EnableMemberRecovery", "EnableSupplementaryChains", "EnableInvestigation"):
            self.assertNotIn("m_Config." + name, module)

    def test_room_catalog_wired_before_native_membership_change(self):
        catalog = (SOURCE / "HCInfectedRooms.c").read_text()
        navigation = (SOURCE / "HCInfectedNavigation.c").read_text()
        self.assertIn("HCInfectedRoomCatalog", catalog)
        self.assertIn("WorldToModel", catalog)
        self.assertIn("PreferRoom", catalog)
        self.assertIn("HCInfectedRoomCatalog.BuildOrder", navigation)
        self.assertLess(navigation.index("HCInfectedRoomCatalog.BuildOrder"),
                        navigation.index("GetAIWorld().CreateGroup"))
        self.assertNotIn('end + "4 0 0"', navigation)

    def test_recovery_uses_load_hook_and_exact_ids_never_position_replacement(self):
        source = (SOURCE / "HCHordeRecovery.c").read_text()
        native = (SOURCE / "HCInfectedNative.c").read_text()
        self.assertIn("override void AfterStoreLoad()", native)
        self.assertIn("super.AfterStoreLoad()", native)
        self.assertIn("GetPersistentID", source)
        self.assertIn("MayRecoverMember", source)
        self.assertIn("MemberIds", (SOURCE / "HCInfectedState.c").read_text())
        self.assertIn("Conflicted", source)
        for forbidden in ("GetEntityByPersitentID", "CreateObject", "SetPosition("):
            self.assertNotIn(forbidden, source)

    def test_recovery_has_its_own_rotating_cursor_to_avoid_actor_sweep_starvation(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        self.assertIn("m_RecoveryCursor", module)
        self.assertIn("m_Actors[m_RecoveryCursor]", module)
        self.assertIn("NextAdoptionCursor(m_RecoveryCursor", module)

    def test_audible_investigation_uses_only_frozen_actual_voice_clue(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        investigation = module.split("protected void TryInvestigate", 1)[1].split("protected void ReleasePacks", 1)[0]
        self.assertIn("actor.Heard", investigation)
        self.assertIn("clue.Origin", investigation)
        self.assertIn("clue.Expires", investigation)
        self.assertNotIn("GetTargetEntity", investigation)

    def test_seed_cannot_investigate_its_own_voice_or_seed_from_calm_noise(self):
        chain = (SOURCE / "HCAlertChain.c").read_text()
        module = (SOURCE / "HCInfectedModule.c").read_text()
        self.assertIn("actor.HeardExternally = false", chain)
        self.assertIn("actor.HeardExternally = true", chain)
        self.assertIn("MINDSTATE_CALM", chain)
        investigation = module.split("protected void TryInvestigate", 1)[1].split("protected void ReleasePacks", 1)[0]
        self.assertIn("actor.HeardExternally", investigation)

    def test_short_voice_window_rotates_recipient_start_instead_of_starving_tail(self):
        chain = (SOURCE / "HCAlertChain.c").read_text()
        self.assertIn("m_RecipientCursor", chain)
        self.assertIn("StartCursor", chain)
        self.assertIn("emission.Scanned", chain)
        self.assertIn("NextAdoptionCursor(m_RecipientCursor", chain)


if __name__ == "__main__":
    unittest.main()
