"""#135 infected LOD service, virtual herds, tiered posed budget and native experiments.

Executes the authored pure HCLODPolicy (4_World/Core/HCLODPolicy.c) and the
variety posed-budget helpers through the existing restricted translators with
explicit synthetic numbers, and checks the source wiring (admission gate W7-135,
start/stats lines, spawn path, fold guards, store caps, experiment marker).
Offline tests prove only the authored decision rules and wiring. Native
materialization, sight, keep-in-idle, DisableSimulation and network range
behaviour remain runtime-pending: nothing here was observed in DayZ.

RED:   PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_lod -v
       -> Ran 16 tests FAILED (failures=14, errors=2): AssertionError: missing
          authored #135 source .../4_World/Core/HCLODPolicy.c; KeyError: 'DormantLimitAt'
GREEN: same command -> Ran 16 tests OK
"""
from tests.unit.test_c1_infectedcfg import tuning_fixture
import math
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.unit.test_event_runtime import translate
from tests.unit.test_infected_contract import policy_functions

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "mods/HollowCountry/scripts/4_World"
POLICY = SCRIPTS / "Core/HCLODPolicy.c"
LOD_DIR = SCRIPTS / "Infected/LOD"
SERVICE = LOD_DIR / "HCInfectedLOD.c"
STORE = LOD_DIR / "HCInfectedLODStore.c"
EXPERIMENT = LOD_DIR / "HCInfectedLODExperiment.c"
VARIETY = SCRIPTS / "Infected/Variety/HCInfectedVarietyModule.c"
STATE = SCRIPTS / "Infected/HCInfectedState.c"
CHECKLIST = ROOT / "docs/LOCAL_ACCEPTANCE_V1.md"
MARKER = "$profile:HollowCountry/acceptance/infected_lod_experiment.enable"


def strip(text):
    return re.sub(r"//[^\n]*", "", text)


def source(path):
    if not path.exists():
        raise AssertionError("missing authored #135 source " + str(path.relative_to(ROOT)))
    return path.read_text()


def policy():
    text = source(POLICY)
    owner = SimpleNamespace()
    for name, value in re.findall(r"static const (?:int|float) (\w+) = ([-\d.]+);", text):
        setattr(owner, name, float(value) if "." in value else int(value))
    env = dict(HCInfectedTuning=tuning_fixture(), HCLODPolicy=owner, len=len, str=str,
               Math=SimpleNamespace(AbsFloat=abs, Min=min, Max=max, Sqrt=math.sqrt))
    for name in re.findall(r"\bstatic (?:bool|int|float) (\w+)\(", text):
        setattr(owner, name, translate(text, name, env, owner="HCLODPolicy"))
    return owner


def variety():
    return policy_functions("Variety/HCInfectedVarietyPolicy.c", Math=SimpleNamespace(
        Min=min, Max=max, Floor=math.floor, Round=lambda v: math.floor(v + .5),
        Clamp=lambda v, lo, hi: max(lo, min(hi, v))),
        HCPostureAdmission=SimpleNamespace(HCCanEnter=translate(
            source(VARIETY.with_name("HCPostureAdmission.c")), "HCCanEnter", {})))


class LODTiers(unittest.TestCase):
    def test_three_tiers_by_nearest_player_distance(self):
        p = policy()
        self.assertEqual(p.TIER_FULL, p.Tier(10.0, 150.0, 450.0))
        self.assertEqual(p.TIER_FULL, p.Tier(150.0, 150.0, 450.0), "boundary stays full AI")
        self.assertEqual(p.TIER_IDLE, p.Tier(151.0, 150.0, 450.0))
        self.assertEqual(p.TIER_IDLE, p.Tier(450.0, 150.0, 450.0))
        self.assertEqual(p.TIER_VIRTUAL, p.Tier(451.0, 150.0, 450.0))
        # Unknown distance (no valid snapshot) never degrades an infected.
        self.assertEqual(p.TIER_FULL, p.Tier(-1.0, 150.0, 450.0))
        self.assertEqual({0, 1, 2}, {p.TIER_VIRTUAL, p.TIER_IDLE, p.TIER_FULL})

    def test_safely_far_is_conservative_about_sample_age_and_speed(self):
        p = policy()
        self.assertTrue(p.SafelyFar(200.0, 0.0, 6.0))
        self.assertFalse(p.SafelyFar(6.0, 0.0, 6.0), "the exact radius is not far")
        self.assertFalse(p.SafelyFar(10.0, 0.0, 12.0))
        # Observers can close the gap at vehicle speed between samples.
        self.assertFalse(p.SafelyFar(100.0, 2.0, 6.0))
        self.assertTrue(p.SafelyFar(200.0, 2.0, 6.0))
        self.assertFalse(p.SafelyFar(5000.0, tuning_fixture().Get().LevelOfDetail.SampleAge + 0.5, 6.0), "stale samples never skip work")
        self.assertFalse(p.SafelyFar(-1.0, 0.0, 6.0), "unknown distance never skips work")
        self.assertFalse(p.SafelyFar(200.0, -1.0, 6.0), "clock went backwards")
        self.assertGreaterEqual(tuning_fixture().Get().LevelOfDetail.ObserverSpeed, 40.0)


class VirtualHerds(unittest.TestCase):
    def test_members_are_wanted_only_near_players_and_within_caps(self):
        p = policy()
        # DesiredMembers(alive, nearest, materializeRange, perHerd)
        self.assertEqual(0, p.DesiredMembers(20, 400.0, 350.0, 6), "no player near the herd")
        self.assertEqual(0, p.DesiredMembers(20, -1.0, 350.0, 6), "unknown snapshot")
        self.assertEqual(6, p.DesiredMembers(20, 300.0, 350.0, 6))
        self.assertEqual(2, p.DesiredMembers(2, 300.0, 350.0, 6), "never more bodies than living head count")
        self.assertEqual(0, p.DesiredMembers(0, 300.0, 350.0, 6))
        # MayMaterialize(desired, leasedHerd, leasedTotal, maxTotal, tracked, trackedCap)
        self.assertTrue(p.MayMaterialize(6, 2, 4, 12, 10, 24))
        self.assertFalse(p.MayMaterialize(6, 6, 6, 12, 10, 24), "herd already has its nearest members")
        self.assertFalse(p.MayMaterialize(6, 2, 12, 12, 10, 24), "global lease cap")
        self.assertFalse(p.MayMaterialize(6, 2, 4, 12, 24, 24), "tracked slot cap")

    def test_spawn_point_must_be_out_of_every_players_sight(self):
        p = policy()
        # SpawnHidden(nearest, minSpawn, observersInRange, occluded, maxObservers)
        self.assertTrue(p.SpawnHidden(130.0, 120.0, 2, 2, 8))
        self.assertFalse(p.SpawnHidden(120.0, 120.0, 0, 0, 8), "minimum distance boundary refuses")
        self.assertFalse(p.SpawnHidden(119.0, 120.0, 0, 0, 8))
        self.assertFalse(p.SpawnHidden(130.0, 120.0, 2, 1, 8), "one player with line of sight refuses")
        self.assertFalse(p.SpawnHidden(130.0, 120.0, 9, 9, 8), "too many observers to prove, refuse")
        self.assertFalse(p.SpawnHidden(-1.0, 120.0, 0, 0, 8), "unknown snapshot refuses")

    def test_fold_never_removes_a_seen_fighting_alerted_or_claimed_body(self):
        p = policy()
        # FoldDecision(alive, calm, sinceHit, claimed, nearest, foldRange, observers, occluded, maxObservers)
        self.assertEqual(p.FOLD_NOW, p.FoldDecision(True, True, -1.0, False, 600.0, 450.0, 0, 0, 8))
        self.assertEqual(p.FOLD_NOW, p.FoldDecision(True, True, 500.0, False, 600.0, 450.0, 1, 1, 8))
        self.assertEqual(p.FOLD_DEAD, p.FoldDecision(False, True, -1.0, False, 600.0, 450.0, 0, 0, 8))
        self.assertEqual(p.FOLD_RELEASE, p.FoldDecision(True, True, -1.0, True, 600.0, 450.0, 0, 0, 8),
                         "a horde-claimed body leaves the herd instead of folding")
        self.assertEqual(p.FOLD_KEEP, p.FoldDecision(True, False, -1.0, False, 600.0, 450.0, 0, 0, 8), "alerted or chasing")
        self.assertEqual(p.FOLD_KEEP, p.FoldDecision(True, True, 30.0, False, 600.0, 450.0, 0, 0, 8), "recently hit")
        self.assertEqual(p.FOLD_KEEP, p.FoldDecision(True, True, -1.0, False, 450.0, 450.0, 0, 0, 8), "fold range boundary")
        self.assertEqual(p.FOLD_KEEP, p.FoldDecision(True, True, -1.0, False, 600.0, 450.0, 2, 1, 8), "a player can see it")
        self.assertEqual(p.FOLD_KEEP, p.FoldDecision(True, True, -1.0, False, 600.0, 450.0, 9, 9, 8))
        self.assertEqual(p.FOLD_KEEP, p.FoldDecision(True, True, -1.0, False, -1.0, 450.0, 0, 0, 8))
        self.assertGreaterEqual(tuning_fixture().Get().LevelOfDetail.HitQuiet, 60.0)

    def test_regrow_is_slow_and_only_while_fully_virtual(self):
        p = policy()
        # MayRegrow(alive, headCount, leased, elapsed, regrowSeconds)
        self.assertTrue(p.MayRegrow(3, 10, 0, 1800.0, 1800.0))
        self.assertFalse(p.MayRegrow(3, 10, 0, 1799.0, 1800.0))
        self.assertFalse(p.MayRegrow(3, 10, 1, 5000.0, 1800.0), "never while members are in the world")
        self.assertFalse(p.MayRegrow(10, 10, 0, 5000.0, 1800.0), "never above the seeded head count")
        self.assertFalse(p.MayRegrow(3, 10, 0, 5000.0, 0.0), "zero disables regrow")

    def test_config_and_store_caps(self):
        p = policy()
        # ValidRanges(full, idle, minSpawn, materialize, fold, visibility)
        self.assertTrue(p.ValidRanges(150.0, 450.0, 120.0, 350.0, 450.0, 1000.0))
        self.assertFalse(p.ValidRanges(450.0, 150.0, 120.0, 350.0, 450.0, 1000.0))
        self.assertFalse(p.ValidRanges(150.0, 450.0, 350.0, 350.0, 450.0, 1000.0), "materialize beyond min spawn")
        self.assertFalse(p.ValidRanges(150.0, 450.0, 120.0, 450.0, 450.0, 1000.0), "fold hysteresis")
        self.assertFalse(p.ValidRanges(150.0, 450.0, 20.0, 350.0, 450.0, 1000.0), "minimum spawn distance floor")
        self.assertFalse(p.ValidRanges(150.0, 450.0, 120.0, 350.0, 1200.0, 1000.0), "fold inside visibility checks")
        # ValidCaps(classify, maxMaterialized, perHerd, posed, posedFull, posedIdle, herds)
        self.assertTrue(p.ValidCaps(8, 12, 6, 12, 12, 12, 0))
        self.assertFalse(p.ValidCaps(0, 12, 6, 12, 12, 12, 0))
        self.assertFalse(p.ValidCaps(8, 25, 6, 12, 12, 12, 0), "leases never exceed the 24 tracked slots")
        self.assertFalse(p.ValidCaps(8, 12, 6, 12, 12, 12, p.MAX_HERDS + 1))
        self.assertFalse(p.ValidCaps(8, 12, 6, 25, 12, 12, 0))
        # ValidHerd(x, z, radius, headCount, alive)
        self.assertTrue(p.ValidHerd(7000.0, 8000.0, 60.0, 20, 20))
        self.assertFalse(p.ValidHerd(-1.0, 8000.0, 60.0, 20, 20))
        self.assertFalse(p.ValidHerd(7000.0, 16000.0, 60.0, 20, 20))
        self.assertFalse(p.ValidHerd(7000.0, 8000.0, 5.0, 20, 20))
        self.assertFalse(p.ValidHerd(7000.0, 8000.0, 60.0, p.MAX_HEAD + 1, 1))
        self.assertFalse(p.ValidHerd(7000.0, 8000.0, 60.0, 20, 21))
        self.assertFalse(p.ValidHerd(7000.0, 8000.0, 60.0, 20, -1))
        self.assertLessEqual(p.MAX_HERDS, 16)
        self.assertLessEqual(p.MAX_HEAD, 64)


class PosedBudget(unittest.TestCase):
    def test_tiered_budget_at_twelve_is_the_shipped_behaviour(self):
        v = variety()
        for scale in (0.6, 0.8, 1.0, 1.1, 1.2, 1.3, 100.0):
            self.assertEqual(v["DormantLimit"](scale), v["DormantLimitAt"](scale, 12), scale)
        self.assertEqual(5, v["DormantLimitAt"](0.6, 12))
        self.assertEqual(10, v["DormantLimitAt"](1.3, 12))
        self.assertEqual(4, v["DormantLimitAt"](1.0, 6), "lower budget scales the cap down")
        self.assertEqual(6, v["DormantLimitAt"](100.0, 6))
        self.assertEqual(0, v["DormantLimitAt"](1.0, 0))

    def test_per_tier_posed_room(self):
        v = variety()
        # PosedRoom(nearPlayers, fullPosed, idlePosed, fullBudget, idleBudget)
        self.assertTrue(v["PosedRoom"](True, 3, 9, 4, 0))
        self.assertFalse(v["PosedRoom"](True, 4, 0, 4, 12))
        self.assertTrue(v["PosedRoom"](False, 4, 0, 4, 12))
        self.assertFalse(v["PosedRoom"](False, 0, 2, 12, 2))


class Wiring(unittest.TestCase):
    def test_save_job_names_itself_for_the_save_peak_line(self):
        text = strip(source(STORE))
        self.assertIn('override string HCName() { return "InfectedLOD"; }', text)

    def test_admission_and_start_line(self):
        text = strip(source(SERVICE))
        self.assertIn('HCV2Admission.Line("InfectedLOD"', text)
        self.assertIn('HCV2Admission.Line("VirtualHerds"', text)
        self.assertGreaterEqual(text.count('"W7-135"'), 2)
        self.assertIn('HCV2Gates.Qualified("W7-135")', text)
        self.assertIn('"[HC InfectedLOD] started', text)
        self.assertIn("runtime=PENDING", text)
        self.assertIn('"[HC InfectedLOD] stats', text)
        for field in ("full=", "idle=", "virtual=", "materialized_per_min=", "folded_per_min=", "refused_sight="):
            self.assertIn(field, text)
        self.assertIn("modded class HCModuleRegistry", text)
        self.assertIn("Register(new HCInfectedLODModule)", text)
        self.assertIn("HCDebugSnapshot.HCRegister(", text)
        self.assertIn("HCDebugSnapshot.HCUnregister(", text)
        self.assertIn("HCPerfPlayers.HCGet()", text)

    def test_ship_defaults(self):
        text = strip(source(STORE))
        self.assertRegex(text, r"bool EnableLOD = true;")
        self.assertRegex(text, r"bool EnableVirtualHerds = true;", "owner default-on; verdict remains unverified")
        self.assertRegex(text, r"int PosedBudget = 12;")
        self.assertRegex(text, r"int PosedFullBudget = 12;")
        self.assertRegex(text, r"int PosedIdleBudget = 12;")
        self.assertIn("HCV2ThreatStore<HCInfectedLODState>", text)
        self.assertIn("HCSaveJob", text)
        self.assertIn("HCLODPolicy.ValidHerd(", text)
        self.assertIn("HCLODPolicy.MAX_HERDS", text)

    def test_materialize_uses_the_admin_sitter_spawn_path_out_of_sight(self):
        text = strip(source(SERVICE))
        self.assertIn("GetGame().CreateObjectEx(", text)
        self.assertIn("ECE_INITAI | ECE_PLACE_ON_SURFACE", text)
        self.assertIn("HCAdminPlacement.HCClear(", text)
        self.assertIn("HCObserverTransitionGate.CanTransition(", text)
        self.assertIn("HCLODPolicy.SpawnHidden(", text)
        self.assertIn("!FindActor(infected) && !Track(infected)", text)
        self.assertIn("DayZPhysics.RaycastRV(", text)

    def test_fold_deletes_only_leased_calm_unseen_bodies(self):
        text = strip(source(SERVICE))
        self.assertIn("HCLODPolicy.FoldDecision(", text)
        self.assertIn("GetMindStateSynced()", text)
        self.assertIn("MINDSTATE_CALM", text)
        # ObjectDelete only on our own leases: refused-track cleanup and fold.
        self.assertLessEqual(text.count("ObjectDelete("), 3)
        fold = text.split("protected void HCLODFoldStep", 1)
        self.assertEqual(2, len(fold), "fold step missing")
        self.assertIn("HCLODPolicy.FOLD_NOW", fold[1].split("\n    }\n", 1)[0])

    def test_variety_reuses_the_lod_service(self):
        text = strip(source(VARIETY))
        self.assertIn("HCInfectedVarietyPolicy.DormantLimitAt(", text)
        self.assertIn("HCInfectedVarietyPolicy.PosedRoom(", text)
        self.assertIn("HCLODPolicy.SafelyFar(", text)
        self.assertIn("HCInfectedLOD.PosedBudget()", text)
        state = strip(source(STATE))
        for field in ("int LODTier", "float LODDistance", "float LODAt"):
            self.assertIn(field, state)

    def test_experiment_is_off_by_default_behind_a_marker_and_restores(self):
        text = strip(source(EXPERIMENT))
        self.assertIn('FileExist("' + MARKER + '")', text)
        self.assertIn("SetKeepInIdle(true)", text)
        self.assertIn("SetKeepInIdle(false)", text)
        self.assertIn("DisableSimulation(true)", text)
        self.assertIn("DisableSimulation(false)", text)
        self.assertIn('"[HC InfectedLOD] experiment', text)
        self.assertIn("result", text)
        self.assertIn(MARKER, CHECKLIST.read_text(encoding="utf-8"))

    def test_network_range_procedure_is_documented_without_changing_defaults(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        perf = text.split("## Performance", 1)[-1]
        self.assertIn("networkRangeFar", perf)
        self.assertIn("#135", perf)
        # A procedure only: no tool writes the serverDZ.cfg network range keys.
        for tool in sorted((ROOT / "tools/setup").glob("*.py")):
            self.assertNotIn("networkRange", tool.read_text(errors="ignore"), tool)


if __name__ == "__main__":
    unittest.main()
