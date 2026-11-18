"""HC Expansion AI self-defence and near-miss response (owner bug 2026-11-18).

Owner report: AI "didn't seem to mind being punched, shot, or killed". Cause
found in the sources: HCXFaction sets m_IsGuard (Expansion guards only fight when
a weapon is raised at them, eAIPlayerTargetInformation.c:163-170) and the HCX
stance override of CalculateThreat (HCXStance.c) zeroes or clamps the
threat that Expansion seeds on a hit (DayZPlayerImplement.c:514-516 ->
eAITargetInformation.c:388 AddFriendlyAI), so a hit player never became an enemy.

Executes the authored pure HCXDefencePolicy through the existing event translator
with explicit synthetic numbers, and checks the source wiring. Offline tests
prove only the authored decision rules and wiring; native hostility, noise and
bullet-impact behaviour remain runtime-pending (nothing observed in DayZ).

RED (first round): PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hcx_self_defence -v
     -> Ran 11 tests, FAILED (failures=11), "missing authored HCX self-defence policy".
RED (review round, P0/P1/P2 fixes): same command after adding the LOS-memory Active
     signature, rescue-hit excuse, ray end point, occlusion, downed-player,
     null-check, weak group key and stance-order tests
     -> Ran 16 tests, FAILED (failures=5, errors=4), then failures=5 on wiring only.
GREEN: same command -> Ran 16 tests OK (322 OK with the HCX/lint suites).
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
HCX = ROOT / "mods/HollowCountryExpansionAI/scripts/4_World"
POLICY = HCX / "HCXDefencePolicy.c"
DEFENCE = HCX / "HCXDefence.c"
STANCE = HCX / "HCXStance.c"


def policy():
    if not POLICY.exists():
        raise AssertionError("missing authored HCX self-defence policy " + str(POLICY.relative_to(ROOT)))
    text = POLICY.read_text()
    owner = SimpleNamespace()
    for name, value in re.findall(r"static const (?:int|float) (\w+) = ([-\d.]+);", text):
        setattr(owner, name, float(value) if "." in value else int(value))
    env = dict(HCXDefencePolicy=owner, len=len, str=str,
               Math=SimpleNamespace(AbsFloat=abs, Min=min, Max=max))
    for name in re.findall(r"\bstatic (?:bool|int|float) (\w+)\(", text):
        setattr(owner, name, translate(text, name, env, owner="HCXDefencePolicy"))
    return owner


def source(path):
    if not path.exists():
        raise AssertionError("missing authored HCX self-defence source " + str(path.relative_to(ROOT)))
    return path.read_text()


class SelfDefencePolicy(unittest.TestCase):
    def test_hostility_is_proportional_and_expires(self):
        p = policy()
        # A hit holds hostility for minutes, a kill a little longer, a near miss
        # only briefly: proportional, never permanent.
        self.assertGreater(p.HoldMs(p.KIND_KILL), p.HoldMs(p.KIND_HIT))
        self.assertGreater(p.HoldMs(p.KIND_HIT), p.HoldMs(p.KIND_MISS))
        self.assertLessEqual(p.HoldMs(p.KIND_KILL), 600000)
        self.assertGreaterEqual(p.HoldMs(p.KIND_HIT), 120000)
        self.assertEqual(0, p.HoldMs(0), "unknown kind never creates a grudge")
        until = 1000 + p.HoldMs(p.KIND_HIT)
        # Active(now, until, distanceToOrigin, losNow, lastLosMs, seededAtMs)
        self.assertTrue(p.Active(1000, until, 10.0, True, 0, 0), "live line of sight")
        self.assertFalse(p.Active(until, until, 10.0, True, 0, 0), "expired at the deadline")
        self.assertFalse(p.Active(until + 1, until, 10.0, True, 0, 0))
        self.assertFalse(p.Active(1000, 0, 10.0, True, 0, 0), "empty slot")
        self.assertFalse(p.Active(1000, until, 400.0, True, 0, 0), "group-mates far from the aggression stay out of it")
        # Never omniscient: m_SearchOnLOSLost is true after any native seed, so
        # it is not evidence of perception. Only live LOS, a recent LOS
        # timestamp, or the short native hit-direction window of the actor that
        # was itself seeded count.
        self.assertFalse(p.Active(60000, until, 10.0, False, 0, 0), "no perception at all")
        self.assertTrue(p.Active(60000, until, 10.0, False, 50000, 0), "LOS seen 10 s ago")
        self.assertFalse(p.Active(60000, until, 10.0, False, 40000, 0), "LOS memory is 15 s, not minutes")
        self.assertTrue(p.Active(60000, until, 10.0, False, 0, 50000), "hit direction: seeded 10 s ago")
        self.assertFalse(p.Active(60000, until, 10.0, False, 0, 30000), "seed window is 20 s")
        self.assertGreater(p.LOS_MEMORY_MS, 0)
        self.assertLessEqual(p.LOS_MEMORY_MS, 30000)
        self.assertLessEqual(p.SEED_WINDOW_MS, 30000)

    def test_rescue_hit_on_a_friendly_is_excused_once(self):
        p = policy()
        self.assertEqual(30000, p.HoldMs(p.KIND_RESCUE))
        # RescueHitExcused(friendly, infectedNear, lethal, nowMs, priorUntilMs)
        self.assertTrue(p.RescueHitExcused(True, 2, False, 5000, 0), "first stray round during a rescue")
        self.assertFalse(p.RescueHitExcused(True, 2, False, 6000, 5000 + p.HoldMs(p.KIND_RESCUE)), "a second hit within 30 s grudges")
        self.assertTrue(p.RescueHitExcused(True, 2, False, 40000, 5000 + p.HoldMs(p.KIND_RESCUE)), "excuse window ended")
        self.assertFalse(p.RescueHitExcused(True, 2, True, 5000, 0), "a kill always grudges")
        self.assertFalse(p.RescueHitExcused(True, 0, False, 5000, 0), "no infected near: a hit is aggression")
        self.assertFalse(p.RescueHitExcused(False, 3, False, 5000, 0), "only friendly or allied actors are excused")

    def test_threat_floor_only_with_an_active_grudge(self):
        p = policy()
        self.assertEqual(0.1, p.Threat(0.1, False), "no grudge keeps the stance result")
        self.assertGreaterEqual(p.Threat(0.1, True), 0.6, "a grudge lifts a watching actor to fight")
        self.assertEqual(0.9, p.Threat(0.9, True), "a stronger native threat is never lowered")

    def test_infected_near_the_shooter_or_actor_excuses_the_shot(self):
        p = policy()
        self.assertTrue(p.Excused(1, 0), "saving someone from an infected near the shooter")
        self.assertTrue(p.Excused(0, 2), "infected on the actor")
        self.assertFalse(p.Excused(0, 0))
        self.assertEqual(25.0, p.INFECTED_RADIUS)

    def test_near_miss_classification(self):
        p = policy()
        # (distance along the shot ray, perpendicular distance to the actor,
        # shooter-to-actor distance, loud weapon, end of the ray)
        end = p.PassEnd(-1.0)
        self.assertEqual(p.NEAR_PASS, p.Classify(30.0, 1.5, 30.0, True, end), "a bullet passing within 4 m")
        self.assertEqual(p.NEAR_PASS, p.Classify(30.0, 3.9, 30.0, False, end), "suppressed shots still pass close")
        self.assertEqual(p.NEAR_NONE, p.Classify(30.0, 6.0, 30.0, True, end), "wide of the actor")
        self.assertEqual(p.NEAR_NONE, p.Classify(-5.0, 1.0, 30.0, True, end), "behind the muzzle")
        self.assertEqual(p.NEAR_NONE, p.Classify(250.0, 1.0, 250.0, True, end), "far beyond hearing/line reach")
        self.assertEqual(p.NEAR_CLOSE, p.Classify(5.0, 20.0, 9.0, True, end), "a loud weapon fired close beside the actor")
        self.assertEqual(p.NEAR_NONE, p.Classify(5.0, 20.0, 9.0, False, end), "a quiet close shot elsewhere is not a threat")
        self.assertEqual(p.NEAR_NONE, p.Classify(5.0, 30.0, 40.0, True, end), "shot fired well away")

    def test_pass_by_stops_where_the_bullet_stops(self):
        p = policy()
        self.assertEqual(p.PASS_REACH, p.PassEnd(-1.0), "no hit: 200 m cap")
        self.assertEqual(p.PASS_REACH, p.PassEnd(900.0))
        self.assertEqual(52.0, p.PassEnd(50.0), "first hit plus about 2 m")
        end = p.PassEnd(50.0)
        self.assertEqual(p.NEAR_PASS, p.Classify(48.0, 2.0, 48.0, True, end), "in front of the wall")
        self.assertEqual(p.NEAR_NONE, p.Classify(120.0, 1.0, 120.0, True, end), "behind the wall the bullet hit")
        self.assertLessEqual(p.RAYCASTS_PER_SHOT, 4)

    def test_shot_evaluations_are_rate_and_window_capped(self):
        p = policy()
        self.assertTrue(p.ShotAllowed(1000, 900, 0, p.SHOT_WINDOW_CAP))
        self.assertFalse(p.ShotAllowed(1000, 1500, 0, p.SHOT_WINDOW_CAP), "per-player spacing")
        self.assertFalse(p.ShotAllowed(1000, 900, p.SHOT_WINDOW_CAP, p.SHOT_WINDOW_CAP), "per-window cap")
        self.assertLessEqual(p.GRUDGE_CAP, 64)
        self.assertGreaterEqual(p.GRUDGE_CAP, 8)

    def test_grudge_store_evicts_the_oldest_only_when_full(self):
        p = policy()
        self.assertEqual(-1, p.EvictIndex(3, p.GRUDGE_CAP))
        self.assertEqual(0, p.EvictIndex(p.GRUDGE_CAP, p.GRUDGE_CAP))


class SelfDefenceWiring(unittest.TestCase):
    def test_module_is_admitted_logged_bounded_and_registered(self):
        policy()
        text = source(DEFENCE)
        self.assertIn('HCV2Admission.Line("AISelfDefence"', text)
        self.assertIn("[HCX Defence]", text)
        self.assertIn("Register(new HCXDefenceModule", text)
        self.assertIn("HCWorkBudget", text, "bounded maintenance reuses the shared work budget")
        self.assertIn("EnableEncounters", text)
        for banned in ("SetPosition(", "SetOrigin(", "SetTransform(", "PostPhys_SetPosition"):
            self.assertNotIn(banned, text, "self-defence must never teleport actors")

    def test_native_hooks_are_overridden_not_replaced(self):
        policy()
        text = source(DEFENCE)
        for hook in ("override void EEHitBy(", "override void EEKilled(", "override void EEFired(",
                     "override void eAI_OnNoiseEvent("):
            self.assertIn(hook, text)
        self.assertEqual(text.count("super.EEHitBy("), 1)
        self.assertEqual(text.count("super.EEKilled("), 2, "eAIBase and ZombieBase chains")
        self.assertEqual(text.count("super.EEFired("), 1)
        # Targets are seeded through Expansion's own target objects, one actor at
        # a time and only where the actor already tracks or heard the aggressor.
        self.assertIn("GetTargetForAI(", text)
        self.assertIn("SetInitial(", text)
        self.assertIn("m_SearchOnLOSLost = true", text)
        self.assertIn("eAINoiseType.BULLETIMPACT", text)

    def test_every_expansion_hook_cites_the_installed_script(self):
        policy()
        text = source(DEFENCE)
        for cite in ("DayZPlayerImplement.c:472", "eAITargetInformation.c:388", "eAIGroup.c:708",
                     "eAIBase.c:4118", "eAIPlayerTargetInformation.c:", "eAINoiseSystem.c:"):
            self.assertIn(cite, text)

    def test_stance_override_consults_the_grudge_before_it_clears_threat(self):
        policy()
        stance = source(STANCE)
        grudge = stance.find("HCXDefence.Hostile(")
        zeroing = stance.find("state.m_ThreatLevel = 0;")
        capped = stance.find("m_HCWarnings.Count() >= 8")
        self.assertGreater(grudge, 0, "CalculateThreat never consults the self-defence grudge")
        self.assertLess(grudge, zeroing, "grudge must be read before unseen threat is cleared")
        self.assertLess(grudge, capped, "grudge must be read before the 8-warning early return")

    def test_hit_and_kill_only_count_real_player_attackers_and_exclude_infected_cases(self):
        policy()
        text = source(DEFENCE)
        self.assertIn("GetIdentity()", text, "only real players provoke a grudge")
        self.assertIn("InfectedNear(", text)
        self.assertIn("GetObjectsAtPosition3D", text)

    def test_p1_pass_by_ray_is_bounded_and_occluded(self):
        policy()
        text = source(DEFENCE)
        self.assertIn("RaycastRV(", text, "pass-by ray ends at the first server raycast hit")
        self.assertIn("ObjIntersectFire", text)
        self.assertIn("PassEnd(", text)
        self.assertIn("Blocked(", text, "a wall between the ray and the actor ends the near miss")

    def test_p1_rescue_hit_is_counted_and_logged(self):
        policy()
        text = source(DEFENCE)
        self.assertIn("RescueHitExcused(", text)
        self.assertIn("excused_rescue_hit", text)
        self.assertIn("KIND_RESCUE", text)

    def test_p2_downed_players_null_checks_and_weak_group_key(self):
        policy()
        text = source(DEFENCE)
        self.assertIn("IsUnconscious()", text[text.index("static bool Hostile("):text.index("static void OnHit(")],
                      "grudged AI must not keep attacking a downed player")
        self.assertIn("if (!info)", text, "GetTargetInformation() is null-checked before seeding")
        self.assertIn("grudge.Group == group", text, "a reused group ID must not inherit a grudge")
        self.assertIn("eAIGroup Group;", text)
        self.assertNotIn("state.m_SearchOnLOSLost", text, "m_SearchOnLOSLost is a seeded flag, not proof of perception")


if __name__ == "__main__":
    unittest.main()
