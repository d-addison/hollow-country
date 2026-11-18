"""Infected death selection (#32): policy truth table and production source contracts.

Offline only. The policy translation proves the authored decision table; it does
NOT prove that DayZ calls the override, that IMPULSE looks different from
DEFAULT, that the corpse replicates, or anything about collision, loot or
cleanup. Those need the paired DayZDiag controls and a local-server run.
"""
import itertools
import math
import os
from pathlib import Path
import re
import types
import unittest

try:
    from .test_infected_contract import policy_functions
except ImportError:
    from test_infected_contract import policy_functions

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "mods/HollowCountry/scripts/4_World/Infected"
POLICY = SOURCE / "HCInfectedDeathPolicy.c"
DEATH = SOURCE / "HCInfectedDeath.c"
NATIVE = Path(os.environ.get(
    "HC_NATIVE_SCRIPTS",
    Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"))

DEFAULT, IMPULSE, BACKSTAB, NECKSTAB = 0, 1, 2, 3


def code(path):
    return re.sub(r"//[^\n]*", "", path.read_text())


def policy():
    anims = types.SimpleNamespace(ANIM_DEATH_DEFAULT=DEFAULT, ANIM_DEATH_IMPULSE=IMPULSE,
                                  ANIM_DEATH_BACKSTAB=BACKSTAB, ANIM_DEATH_NECKSTAB=NECKSTAB)
    return policy_functions("HCInfectedDeathPolicy.c", Math=types.SimpleNamespace(AbsFloat=abs),
                            DayZInfectedDeathAnims=anims)


class SelectionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.select = policy()["SelectDeathType"]

    def pick(self, native=DEFAULT, finisher=False, hit_anim=0, heavy=True, zone="Torso", direction=0.0):
        return self.select(native, finisher, hit_anim, heavy, zone, direction)

    def test_heavy_frontal_torso_or_head_kill_upgrades_default_to_impulse(self):
        for zone in ("Torso", "Head"):
            self.assertEqual(IMPULSE, self.pick(zone=zone), zone)

    def test_heavy_by_ammo_hit_animation_or_by_override_both_count(self):
        self.assertEqual(IMPULSE, self.pick(hit_anim=1, heavy=False))
        self.assertEqual(IMPULSE, self.pick(hit_anim=0, heavy=True))

    def test_light_hits_stay_on_the_vanilla_default(self):
        self.assertEqual(DEFAULT, self.pick(hit_anim=0, heavy=False))
        self.assertEqual(DEFAULT, self.pick(hit_anim=-1, heavy=False))

    def test_rear_and_side_kills_stay_on_the_vanilla_default(self):
        for direction in (61.0, 90.0, 120.0, 180.0, -61.0, -90.0, -180.0):
            self.assertEqual(DEFAULT, self.pick(direction=direction), direction)

    def test_frontal_cone_boundary_is_inclusive_sixty_degrees(self):
        for direction in (0.0, 59.9, 60.0, -59.9, -60.0):
            self.assertEqual(IMPULSE, self.pick(direction=direction), direction)
        self.assertEqual(DEFAULT, self.pick(direction=60.01))
        self.assertEqual(DEFAULT, self.pick(direction=-60.01))

    def test_nonfinite_direction_is_refused_to_vanilla(self):
        self.assertEqual(DEFAULT, self.pick(direction=math.nan))

    def test_leg_zones_keep_the_vanilla_fold(self):
        for zone in ("LeftLeg", "RightLeg"):
            self.assertEqual(DEFAULT, self.pick(zone=zone), zone)

    def test_other_zones_and_empty_zone_stay_default(self):
        for zone in ("", "Neck", "LeftArm", "RightArm", "Brain", "Global", "torso"):
            self.assertEqual(DEFAULT, self.pick(zone=zone), zone)

    def test_finishers_and_nondefault_native_types_are_never_rewritten(self):
        for native in (DEFAULT, IMPULSE, BACKSTAB, NECKSTAB):
            self.assertEqual(native, self.pick(native=native, finisher=True), native)
        for native in (IMPULSE, BACKSTAB, NECKSTAB):
            self.assertEqual(native, self.pick(native=native), native)

    def test_exhaustive_sweep_only_ever_upgrades_default_to_impulse(self):
        zones = ("Torso", "Head", "LeftLeg", "RightLeg", "Neck", "")
        directions = (-180.0, -61.0, -60.0, 0.0, 60.0, 61.0, 180.0, math.nan)
        for native, finisher, hit, heavy, zone, direction in itertools.product(
                (DEFAULT, IMPULSE, BACKSTAB, NECKSTAB), (False, True), (-1, 0, 1),
                (False, True), zones, directions):
            out = self.select(native, finisher, hit, heavy, zone, direction)
            if out != native:
                self.assertEqual((DEFAULT, IMPULSE), (native, out))
                self.assertFalse(finisher)


class ProductionSourceContractTests(unittest.TestCase):
    def setUp(self):
        self.text = code(DEATH)
        self.policy = code(POLICY)

    def test_admission_is_open_by_default_with_probe_once_disable_opt_out(self):
        self.assertRegex(self.text, r"class HCInfectedDeathQualification")
        self.assertRegex(self.text, r"static bool Qualified\(\)\s*\{\s*return false;\s*\}")
        self.assertIn('!FileExist("$profile:HollowCountry/acceptance/infected_deaths.disable")', self.text)
        self.assertNotIn("infected_deaths.enable", self.text)
        self.assertRegex(self.text, r"if \(!s_Checked\)")
        self.assertRegex(self.text, r"s_Checked = true;")
        self.assertIn("EXPERIMENTAL", self.text)
        self.assertIn("runtime acceptance PENDING", self.text)
        self.assertEqual(1, self.text.count("FileExist("))

    def test_only_the_supported_death_evaluation_hook_is_overridden(self):
        self.assertRegex(self.text, r"modded class ZombieBase")
        self.assertIn("override bool EvaluateDeathAnimationEx(EntityAI pSource, ZombieHitData data, "
                      "out int pAnimType, out float pAnimHitDir)", self.text)
        self.assertEqual(1, len(re.findall(r"\boverride\b", self.text)))
        self.assertRegex(self.text, r"bool result = super\.EvaluateDeathAnimationEx\(pSource, data, pAnimType, pAnimHitDir\);")

    def test_server_admission_and_null_guards_precede_any_rewrite(self):
        body = self.text[self.text.index("EvaluateDeathAnimationEx"):]
        guard = body.index("IsServer()")
        self.assertLess(body.index("super.EvaluateDeathAnimationEx"), guard)
        self.assertLess(guard, body.index("Admitted()"))
        self.assertLess(body.index("Admitted()"), body.index("pAnimType ="))
        self.assertIn("!data", body)

    def test_selection_reads_native_inputs_and_leaves_direction_to_vanilla(self):
        self.assertIn('ConfigGetInt("cfgAmmo " + data.m_AmmoType + " hitAnimation")', self.text)
        self.assertIn("m_HeavyHitOverride", self.text)
        self.assertIn("IsBeingBackstabbed()", self.text)
        self.assertIn("data.m_DamageZone", self.text)
        self.assertIn("HCInfectedDeathPolicy.SelectDeathType(", self.text)
        self.assertNotRegex(self.text, r"pAnimHitDir\s*=[^=]")

    def test_no_velocity_teleport_physics_health_or_deletion_calls(self):
        for token in ("dBodyApply", "dBodySet", "SetPosition", "SetOrigin", "SetDirection", "StartCommand_Death",
                      "PhysicsSet", "SetHealth", "ObjectDelete", "SetAnimationInstance", "CreateObject",
                      "SetVelocity", "SetPosition", "CallLater", "ScriptRPC", "SendEntityKilled"):
            self.assertNotIn(token, self.text, token)
            self.assertNotIn(token, self.policy, token)

    def test_no_loops_timers_or_client_owned_state(self):
        for text in (self.text, self.policy):
            self.assertNotRegex(text, r"\b(for|while|foreach)\b")
            self.assertNotIn("GetCallQueue", text)
            self.assertNotRegex(text, r"\bm_Hc\w*Dirty\b|RegisterNetSyncVariable")

    def test_decision_log_is_bounded_and_uses_explicit_to_string(self):
        self.assertRegex(self.text, r"s_Logged\s*<\s*16")
        self.assertRegex(self.text, r"s_Logged\+\+;")
        statements = re.findall(r'Print\(((?:"[^"]*"|[^";])*)\);', self.text)
        self.assertGreaterEqual(len(statements), 3)
        for statement in statements:
            self.assertLessEqual(statement.count("+"), 8)
            for piece in (part.strip() for part in statement.split("+")):
                self.assertTrue(piece.startswith('"') or piece in ("ammo", "zone", "line")
                                or piece.endswith(".ToString()"), piece)
        for statement in re.findall(r"string line = ([^;]*);|line = ([^;]*);", self.text):
            for piece in (part.strip() for part in "".join(statement).split("+")):
                self.assertTrue(piece.startswith('"') or piece in ("ammo", "zone", "line")
                                or piece.endswith(".ToString()"), piece)
            self.assertLessEqual("".join(statement).count("+"), 8)

    def test_policy_is_pure_static_scalar_helpers(self):
        self.assertRegex(self.policy, r"class HCInfectedDeathPolicy")
        self.assertRegex(self.policy, r"static int SelectDeathType\(int nativeType, bool finisher, "
                                      r"int ammoHitAnimation, bool heavyOverride, string zone, float hitDirection\)")
        for token in ("GetGame", "g_Game", "EntityAI", "ZombieBase", "FileExist"):
            self.assertNotIn(token, self.policy, token)

    @unittest.skipUnless(NATIVE.is_dir(), "installed native script cache not available")
    def test_every_native_api_used_exists_in_the_inspected_cache(self):
        zombie = (NATIVE / "4_World/Entities/Creatures/Infected/ZombieBase.c").read_text()
        infected = (NATIVE / "3_Game/Entities/DayZInfected.c").read_text()
        self.assertIn("bool EvaluateDeathAnimationEx(EntityAI pSource, ZombieHitData data, "
                      "out int pAnimType, out float pAnimHitDir)", zombie)
        self.assertIn("EvaluateDeathAnimationEx(source, data, m_DeathType, m_DamageHitDirection);", zombie)
        self.assertIn("override bool IsBeingBackstabbed()", zombie)
        self.assertIn("string m_DamageZone;", zombie)
        self.assertIn("string m_AmmoType;", zombie)
        self.assertRegex(infected, r"bool\s+m_HeavyHitOverride;")
        for member in ("ANIM_DEATH_DEFAULT = 0", "ANIM_DEATH_IMPULSE = 1"):
            self.assertIn(member, infected)
        self.assertIn('"cfgAmmo " + pAmmoType + " hitAnimation"', zombie)


class AuditDocumentTests(unittest.TestCase):
    DOC = ROOT / "docs/INFECTED_DEATHS.md"

    def test_audit_exists_cites_cache_lines_and_states_unsupported_and_pending(self):
        text = self.DOC.read_text()
        for required in ("EvaluateDeathAnimationEx", "ZombieBase.c:", "DayZInfected.c:",
                         "PhysicsSetRagdoll", "unsupported", "ECE_INITAI", "run 065",
                         "run 047", "run 043", "run 062", "run 064",
                         "PENDING", "infected_deaths.disable", "on by default"):
            self.assertIn(required, text, required)
        self.assertNotIn(str(Path.home()), text)

    def test_audit_does_not_claim_acceptance_or_proven_ragdoll(self):
        text = self.DOC.read_text()
        self.assertNotRegex(text, r"(?i)ragdoll (is|was) (observed|accepted|proven)")
        self.assertNotRegex(text, r"(?i)acceptance:\s*(pass|accepted|complete)")


if __name__ == "__main__":
    unittest.main()
