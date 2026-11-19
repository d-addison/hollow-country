"""s2-tactics: dynamic AI tactics (smoke cover, infected lure) for the HCX addon.

Executes the authored pure HCXAITacticsPolicy through the existing event
translator with explicit synthetic numbers, pins the shipped config defaults
against the in-code validated ranges, and checks the source wiring. Offline
tests prove only the authored decision rules and wiring; throw force units, the
native noise reaction of infected, smoke activation and group behaviour are
runtime-pending (nothing observed in DayZ).

RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_s2_tactics -v
GREEN: same command.
"""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
MARKER = "$profile:HollowCountry/acceptance/ai_tactics.disable"
LOADOUT_CHANCE = {"Raider": 0.25, "Patrol": 0.25, "Holdout": 0.15}
ADDON = ROOT / "mods/HollowCountryExpansionAI"
WORLD = ADDON / "scripts/4_World"
TACTICS = WORLD / "HCXAITactics.c"
THROWABLES = WORLD / "HCXAIThrowables.c"
DEFAULTS = ADDON / "data/defaults/expansion-ai-tactics.json"
FORBIDDEN = ("snafu", "tactical" + "flava", "2646817942", "2291785308", "2792982069")


def read(path):
    if not path.exists():
        raise AssertionError("missing authored s2-tactics source " + str(path.relative_to(ROOT)))
    return path.read_text()


def policy():
    text = read(TACTICS)
    owner = SimpleNamespace()
    for name, value in re.findall(r"static const (?:int|float) (\w+) = ([-\d.]+);", text):
        setattr(owner, name, float(value) if "." in value else int(value))
    env = dict(HCXAITacticsPolicy=owner, len=len, str=str,
               Math=SimpleNamespace(AbsFloat=abs, Min=min, Max=max))
    block = text[text.index("class HCXAITacticsPolicy"):]
    block = block[:block.index("\nclass ")] if "\nclass " in block else block
    for name in re.findall(r"\bstatic (?:bool|int|float|string) (\w+)\(", block):
        setattr(owner, name, translate(block, name, env, owner="HCXAITacticsPolicy"))
    return owner


def normalise_lines():
    text = read(TACTICS)
    found = {}
    for field, kind, default, lo, hi in re.findall(
            r"(\w+) = HCXAITacticsPolicy\.Clamp(Int|Float)\(\1, ([-\d.]+), ([-\d.]+), ([-\d.]+)\);", text):
        found[field] = (float(default), float(lo), float(hi), kind)
    return found


class SmokeDecision(unittest.TestCase):
    def test_trigger_is_fire_or_downed_mate_and_never_unperceived(self):
        p = policy()
        # SmokeDecision(fireEvents, eventsRequired, downedMate, perceived, distance, minM, maxM)
        self.assertEqual("fire", p.SmokeDecision(2, 2, False, True, 40.0, 15.0, 120.0))
        self.assertEqual("downed", p.SmokeDecision(0, 2, True, True, 40.0, 15.0, 120.0))
        self.assertEqual("fire", p.SmokeDecision(3, 2, True, True, 40.0, 15.0, 120.0), "fire outranks downed")
        self.assertEqual("no_trigger", p.SmokeDecision(1, 2, False, True, 40.0, 15.0, 120.0))
        self.assertEqual("no_trigger", p.SmokeDecision(0, 2, False, True, 40.0, 15.0, 120.0))

    def test_no_omniscience_needs_a_perceived_threat_in_range(self):
        p = policy()
        self.assertEqual("no_perceived_threat", p.SmokeDecision(5, 2, True, False, 40.0, 15.0, 120.0))
        self.assertEqual("threat_too_close", p.SmokeDecision(2, 2, False, True, 5.0, 15.0, 120.0))
        self.assertEqual("threat_too_far", p.SmokeDecision(2, 2, False, True, 400.0, 15.0, 120.0))
        self.assertEqual("fire", p.SmokeDecision(2, 2, False, True, 15.0, 15.0, 120.0), "bounds inclusive")
        self.assertEqual("fire", p.SmokeDecision(2, 2, False, True, 120.0, 15.0, 120.0))
        nan = float("nan")
        self.assertNotEqual("fire", p.SmokeDecision(2, 2, False, True, nan, 15.0, 120.0), "NaN distance is refused")

    def test_cover_lands_between_group_and_threat_not_on_it(self):
        p = policy()
        # ThrowMeters(distance, throwMeters, fractionPct): never past the configured
        # fraction of the way to the threat, never farther than the throw reach.
        self.assertAlmostEqual(12.0, p.ThrowMeters(100.0, 12.0, 40))
        self.assertAlmostEqual(8.0, p.ThrowMeters(20.0, 12.0, 40))
        self.assertLess(p.ThrowMeters(20.0, 12.0, 40), 20.0)
        self.assertLessEqual(p.ThrowMeters(1000.0, 12.0, 90), 12.0)

    def test_force_scales_with_reach_inside_the_configured_band(self):
        p = policy()
        # ThrowForce(meters, maxMeters, forceMin, forceMax)
        self.assertAlmostEqual(20.0, p.ThrowForce(0.0, 12.0, 20.0, 60.0))
        self.assertAlmostEqual(60.0, p.ThrowForce(12.0, 12.0, 20.0, 60.0))
        self.assertAlmostEqual(60.0, p.ThrowForce(30.0, 12.0, 20.0, 60.0), "never above the band")
        self.assertAlmostEqual(40.0, p.ThrowForce(6.0, 12.0, 20.0, 60.0))
        self.assertAlmostEqual(60.0, p.ThrowForce(5.0, 0.0, 20.0, 60.0), "degenerate reach uses the cap")


class LureDecision(unittest.TestCase):
    def test_lure_needs_perceived_infected_pressure_and_no_human_threat(self):
        p = policy()
        # LureDecision(infected, minInfected, nearest, minM, maxM, humanThreat)
        self.assertEqual("", p.LureDecision(4, 3, 30.0, 12.0, 60.0, False))
        self.assertEqual("no_infected", p.LureDecision(2, 3, 30.0, 12.0, 60.0, False))
        self.assertEqual("no_infected", p.LureDecision(0, 3, 30.0, 12.0, 60.0, False))
        self.assertEqual("too_close", p.LureDecision(4, 3, 5.0, 12.0, 60.0, False), "already on us: smoke or fight, not a lure")
        self.assertEqual("too_far", p.LureDecision(4, 3, 150.0, 12.0, 60.0, False))
        self.assertEqual("human_threat", p.LureDecision(4, 3, 30.0, 12.0, 60.0, True), "noise would also bring the humans")
        self.assertEqual("", p.LureDecision(3, 3, 12.0, 12.0, 60.0, False), "bounds inclusive")

    def test_only_listed_empty_noisy_items_are_thrown(self):
        p = policy()
        types = "|SardinesCan|WaterBottle|"
        # NoisyItemOk(types, type, hasQuantity, quantity, allowFull)
        self.assertTrue(p.NoisyItemOk(types, "SardinesCan", True, 0.0, False), "empty listed can")
        self.assertTrue(p.NoisyItemOk(types, "WaterBottle", False, 0.0, False), "no quantity at all counts as empty")
        self.assertFalse(p.NoisyItemOk(types, "SardinesCan", True, 120.0, False), "full food is not thrown by default")
        self.assertTrue(p.NoisyItemOk(types, "SardinesCan", True, 120.0, True), "operator may allow full")
        self.assertFalse(p.NoisyItemOk(types, "Pot", True, 0.0, True), "unlisted type")
        self.assertFalse(p.NoisyItemOk(types, "Sardines", True, 0.0, True), "whole-token match only")
        self.assertFalse(p.NoisyItemOk(types, "", True, 0.0, True))

    def test_flare_lure_is_a_named_refusal_not_a_guess(self):
        text = read(TACTICS)
        self.assertIn("flare_lure_unverified", text)
        self.assertNotRegex(text, r"CompEM\(\)\.SwitchOn")


class SmokeItem(unittest.TestCase):
    def test_contaminated_smoke_is_never_used(self):
        p = policy()
        # The contaminated M18 variant spawns a ContaminatedArea_Dynamic when it stops (SmokeGrenadeBase.c).
        self.assertFalse(p.SmokeTypeOk("M18SmokeGrenade_Red_Contaminated", "Contaminated"))
        self.assertTrue(p.SmokeTypeOk("M18SmokeGrenade_White", "Contaminated"))
        self.assertTrue(p.SmokeTypeOk("RDG2SmokeGrenade_Black", "Contaminated"))
        self.assertTrue(p.SmokeTypeOk("M18SmokeGrenade_Red_Contaminated", ""), "an empty exclusion means none")

    def test_activation_consumes_the_real_item_and_gives_up_cleanly(self):
        p = policy()
        # ActivateStep(held, pinned, tries, maxTries, ageMs, maxAgeMs)
        self.assertEqual("wait", p.ActivateStep(True, True, 0, 4, 500, 10000), "still in the thrower's inventory")
        self.assertEqual("give_up", p.ActivateStep(True, True, 0, 4, 10001, 10000), "never left the inventory")
        self.assertEqual("activate", p.ActivateStep(False, True, 0, 4, 900, 10000), "landed, still pinned")
        self.assertEqual("activate", p.ActivateStep(False, True, 3, 4, 900, 10000))
        self.assertEqual("give_up", p.ActivateStep(False, True, 4, 4, 900, 10000), "bounded retries")
        self.assertEqual("done", p.ActivateStep(False, False, 1, 4, 900, 10000), "pin already pulled")
        self.assertEqual("done", p.ActivateStep(True, False, 0, 4, 100, 10000))


class GateAndConfig(unittest.TestCase):
    def test_cooldown_and_group_cap(self):
        p = policy()
        # Gate(nowMs, lastMs, cooldownMs, uses, cap)
        self.assertEqual("", p.Gate(100000, 0, 90000, 0, 3), "never used")
        self.assertEqual("cooldown", p.Gate(100000, 50000, 90000, 1, 3))
        self.assertEqual("", p.Gate(150000, 50000, 90000, 1, 3), "cooldown elapsed")
        self.assertEqual("group_cap", p.Gate(900000, 50000, 90000, 3, 3))
        self.assertEqual("", p.Gate(900000, 50000, 90000, 2, 3))
        self.assertTrue(p.WindowExpired(700000, 100000, 600000))
        self.assertFalse(p.WindowExpired(699999, 100000, 600000))
        self.assertTrue(p.TrackedFull(32, 32))
        self.assertFalse(p.TrackedFull(31, 32))

    def test_recent_fire_window(self):
        p = policy()
        self.assertTrue(p.Recent(10000, 5000, 8000))
        self.assertFalse(p.Recent(20000, 5000, 8000))
        self.assertFalse(p.Recent(10000, 0, 8000), "no stamp")
        self.assertFalse(p.Recent(4000, 5000, 8000), "stamp from the future is ignored")

    def test_clamps_replace_zero_filled_and_out_of_range_values(self):
        p = policy()
        self.assertEqual(90, p.ClampInt(0, 90, 10, 3600), "JsonFileLoader zero-fill falls back to the default")
        self.assertEqual(90, p.ClampInt(5, 90, 10, 3600))
        self.assertEqual(90, p.ClampInt(99999, 90, 10, 3600))
        self.assertEqual(300, p.ClampInt(300, 90, 10, 3600))
        self.assertAlmostEqual(6.0, p.ClampFloat(0.0, 6.0, 1.0, 30.0))
        self.assertAlmostEqual(6.0, p.ClampFloat(float("nan"), 6.0, 1.0, 30.0))
        self.assertAlmostEqual(9.5, p.ClampFloat(9.5, 6.0, 1.0, 30.0))

    def test_on_by_default_with_three_opt_outs(self):
        p = policy()
        # Allowed(globalDisabled, featureDisabled)
        self.assertTrue(p.Allowed(False, False), "zero-filled config means on")
        self.assertFalse(p.Allowed(True, False))
        self.assertFalse(p.Allowed(False, True))
        data = json.loads(read(DEFAULTS))
        for flag in ("Disabled", "SmokeDisabled", "LureDisabled"):
            self.assertIs(False, data[flag], flag + " ships off so the feature ships on")

    def test_shipped_defaults_match_the_validated_ranges(self):
        data = json.loads(read(DEFAULTS))
        lines = normalise_lines()
        self.assertGreaterEqual(len(lines), 20, "every numeric tunable is range validated")
        for field, (default, lo, hi, kind) in lines.items():
            self.assertIn(field, data, field + " missing from the shipped JSON")
            self.assertEqual(default, float(data[field]), field + " default drifted from Normalise")
            self.assertTrue(lo <= default <= hi, field + " default outside its own range")
        numeric = {k for k, v in data.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and k != "SchemaVersion"}
        self.assertEqual(set(), numeric - set(lines), "numeric field without validation")
        self.assertEqual(1, data["SchemaVersion"])
        self.assertIn("Contaminated", data["SmokeExclude"])
        self.assertNotIn("flare", data["LureTypes"].lower())

    def test_every_dto_field_is_in_the_shipped_json(self):
        text = read(TACTICS)
        dto = text[text.index("class HCXAITacticsConfig"):]
        dto = dto[:dto.index("\n}")]
        fields = set(re.findall(r"^\s*(?:int|float|bool|string) (\w+)(?:\s*=[^;]+)?;", dto, re.M))
        self.assertEqual(fields, set(json.loads(read(DEFAULTS))))


class Wiring(unittest.TestCase):
    def setUp(self):
        self.tactics = read(TACTICS)
        self.throw = read(THROWABLES)
        self.both = self.tactics + self.throw
        self.code = re.sub(r"//[^\n]*", "", self.both)

    def test_no_spawned_items_and_no_unusable_server_throw(self):
        for needle in ("CreateObject", "CreateInInventory", "CreateInHands", "SpawnEntity", "CreateObjectEx"):
            self.assertNotIn(needle, self.code, needle + " would duplicate loot; the item must be a real carried one")
        self.assertNotIn(".ThrowEntity(", self.code, "HumanInventory.ThrowEntity returns false on a multiplayer server")
        self.assertIn("MiscGameplayFunctions.ThrowEntityFromInventory", self.throw)
        self.assertIn("ServerDropEntity", self.throw, "named drop fallback")
        self.assertIn("HCSituationSignals.HCSmoke", self.throw, "reuse the existing guarded unpin")
        self.assertIn("SmokeGrenadeBase.Cast", self.throw)

    def test_noise_goes_through_the_native_noise_system(self):
        self.assertRegex(self.throw, r"GetNoiseSystem\(\)")
        self.assertRegex(self.throw, r"AddNoisePos\(")
        self.assertRegex(self.throw, r"LoadFromPath\(")
        self.assertNotRegex(self.code, r"AddNoiseTarget", "a timed target is a longer lived alert than one can landing")

    def test_perception_only_and_native_budgets(self):
        self.assertNotRegex(self.code, r"GetPlayers\(|GetGame\(\)\.GetWorld\(\)\.GetPlayerList|CastTo\(\s*\w+\s*,\s*GetGame\(\)\.GetPlayer")
        self.assertIn("GetTargets()", self.tactics)
        self.assertIn("m_LOS", self.tactics)
        self.assertRegex(self.both, r"HCServer\.HCTickWork\(\)\.HCTakeFor\(HCUnitBudget\.HC_WORK_SITUATIONS")
        self.assertIn("HCWorkBudget", self.tactics)
        self.assertIn("HCXStance.Owns", self.tactics, "only HC owned AI act")
        self.assertRegex(self.tactics, r"HCReset\(")

    def test_module_admission_readiness_and_optout(self):
        self.assertRegex(self.tactics, r"class HCXAITacticsModule : HCModule")
        self.assertRegex(self.tactics, r"modded class HCModuleRegistry")
        self.assertRegex(self.tactics, r"HCXAITacticsModule \w+ = new HCXAITacticsModule\(\);\s*Register\(\w+\);")
        self.assertIn("HCModuleReadiness.HCDerive", self.tactics)
        self.assertIn("HCV2Admission.Line(", self.tactics)
        self.assertIn("runtime=PENDING", self.tactics)
        self.assertIn("Disabled in expansion-ai-tactics.json", self.tactics)
        self.assertIn(MARKER, self.tactics, "acceptance marker opt-out in addition to the JSON fields")
        self.assertRegex(self.tactics, r'FileExist\("\$profile:HollowCountry/acceptance/ai_tactics\.disable"\)')
        self.assertIn("HCProfileDefaults.Ensure", self.tactics)
        self.assertIn("JsonFileLoader<HCXAITacticsConfig>.LoadData", self.tactics)
        self.assertRegex(self.tactics, r"ready.*|HCDerive")
        self.assertEqual(1, len(re.findall(r"HCV2Admission\.Line\(", self.tactics)), "one admission line")

    def test_hooks_live_in_this_scope_not_in_read_only_defence_files(self):
        self.assertRegex(self.tactics, r"modded class eAIBase")
        self.assertRegex(self.tactics, r"override void EEHitBy\(")
        self.assertRegex(self.tactics, r"override void eAI_OnNoiseEvent\(")
        self.assertIn("Weapon_Base.Cast(source)", self.tactics, "only a weapon hit is effective fire")
        self.assertIn("BULLETIMPACT", self.tactics)

    def test_named_refusals_logged_once(self):
        for reason in ("no_smoke_stock", "no_noisy_item", "throw_refused", "flare_lure_unverified", "capability_unverified"):
            self.assertIn(reason, self.both)
        self.assertRegex(self.tactics, r"HCRefuse\(")

    def test_citations_and_status_markers(self):
        self.assertRegex(self.throw, r"MiscGameplayFunctions\.c:1305")
        self.assertRegex(self.throw, r"HumanInventory\.c:164")
        self.assertRegex(self.throw, r"(?i)unverified")
        self.assertRegex(self.throw, r"(?i)verified")

    def test_forbidden_strings_absent(self):
        for path in (TACTICS, THROWABLES, DEFAULTS):
            lowered = read(path).lower()
            for needle in FORBIDDEN:
                self.assertNotIn(needle.lower(), lowered, path.name)


class Lifecycle(unittest.TestCase):
    """Synthetic item lifecycle driven through the authored decision rules."""

    def test_failed_throw_drops_at_the_feet_and_fails_closed_without_the_drop(self):
        p = policy()
        # ThrowOutcome(refusal, dropped): the engine throw returns void, so only the preconditions refuse.
        self.assertEqual("thrown", p.ThrowOutcome("", False))
        self.assertEqual("dropped", p.ThrowOutcome("throw_refused", True), "named fallback: ServerDropEntity")
        self.assertEqual("failed", p.ThrowOutcome("throw_refused", False), "nothing left the inventory: no pending, no use counted")

    def test_inventory_transfer_activation_and_pending_removal(self):
        p = policy()
        item = {"held": True, "pinned": True, "tries": 0, "age": 0}
        seen = []
        for _ in range(12):
            step = p.ActivateStep(item["held"], item["pinned"], item["tries"], 4, item["age"], 10000)
            action = p.PendingAction(False, True, step, True)
            seen.append(action)
            if action == "activate_smoke":
                item["tries"] += 1
                item["pinned"] = False
            if action.startswith("remove"):
                break
            if len(seen) == 2:
                item["held"] = False  # the native throw moved it out of the thrower's inventory
            item["age"] += 1000
        self.assertEqual(["keep", "keep", "activate_smoke", "remove_activated"], seen)
        self.assertEqual(1, item["tries"], "pin pulled once, never re-activated")

    def test_item_that_never_leaves_the_inventory_is_lost_and_named_not_retried(self):
        p = policy()
        step = p.ActivateStep(True, True, 0, 4, 10001, 10000)
        self.assertEqual("remove_lost", p.PendingAction(False, True, step, False))
        self.assertEqual("remove_lost", p.PendingAction(False, False, step, False))

    def test_activation_gives_up_after_bounded_tries(self):
        p = policy()
        step = p.ActivateStep(False, True, 4, 4, 900, 10000)
        self.assertEqual("remove_lost", p.PendingAction(False, True, step, True))

    def test_vanished_item_is_removed_and_only_a_smoke_counts_lost(self):
        p = policy()
        self.assertEqual("remove_lost", p.PendingAction(True, True, "wait", False))
        self.assertEqual("remove", p.PendingAction(True, False, "wait", False))

    def test_lure_makes_one_noise_only_after_the_landing_delay(self):
        p = policy()
        self.assertEqual("keep", p.PendingAction(False, False, "activate", False), "still in flight")
        self.assertEqual("noise_remove", p.PendingAction(False, False, "activate", True))
        self.assertEqual("remove", p.PendingAction(False, False, "done", True))

    def test_smoke_already_active_is_removed_as_activated(self):
        p = policy()
        self.assertEqual("remove_activated", p.PendingAction(False, True, "done", True))
        self.assertEqual("keep", p.PendingAction(False, True, "wait", False))


class PerActorBackoff(unittest.TestCase):
    def test_one_member_without_stock_does_not_block_a_mate_who_carries_smoke(self):
        p = policy()
        until = {}
        # Member A scans empty at t=1000 and backs off for the cooldown; member B has no backoff.
        until["A"] = p.BackoffUntil(1000, 90000)
        self.assertEqual(91000, until["A"])
        self.assertTrue(p.BackedOff(2000, until["A"]))
        self.assertFalse(p.BackedOff(2000, until.get("B", 0)), "the mate is still evaluated")
        self.assertFalse(p.BackedOff(91000, until["A"]), "backoff expires on its own")
        self.assertFalse(p.BackedOff(2000, 0), "no entry means no backoff")

    def test_ledger_is_keyed_by_actor_not_group(self):
        text = read(TACTICS)
        code = re.sub(r"//[^\n]*", "", text)
        self.assertNotIn("StockUntil", code, "the per-group backoff is gone")
        self.assertRegex(code, r"class HCXTacticsBackoff\s*\{[^}]*eAIBase Actor;[^}]*int SmokeUntil;[^}]*int LureUntil;")
        self.assertRegex(code, r"static const int BACKOFF_MAX = \d+;")
        self.assertRegex(code, r"HCXAITactics\.Backoff\(actor\)")
        self.assertRegex(code, r"BackedOff\(nowMs, \w+\.SmokeUntil\)")
        self.assertRegex(code, r"BackoffUntil\(nowMs, s_Config\.SmokeCooldownSec \* 1000\)")


class Loadouts(unittest.TestCase):
    PATHS = (ROOT / "mission/hollow-country/ai/loadouts", ADDON / "data/defaults/loadouts")

    def smoke_entries(self, path):
        data = json.loads(path.read_text())
        return [row for row in data["InventoryCargo"] if row["ClassName"] == "M18SmokeGrenade_White"]

    def test_raider_patrol_holdout_carry_a_real_smoke_at_a_low_chance(self):
        for role, chance in LOADOUT_CHANCE.items():
            for folder in self.PATHS:
                path = folder / ("HollowCountry_" + role + ".json")
                rows = self.smoke_entries(path)
                self.assertEqual(1, len(rows), role + " in " + folder.parent.name)
                self.assertAlmostEqual(chance, rows[0]["Chance"], msg=role)
                self.assertEqual([], rows[0]["InventoryCargo"])

    def test_shipped_and_mission_copies_stay_byte_identical(self):
        for role in LOADOUT_CHANCE:
            name = "HollowCountry_" + role + ".json"
            self.assertEqual((self.PATHS[0] / name).read_bytes(), (self.PATHS[1] / name).read_bytes(), name)

    def test_loadout_smoke_class_is_not_the_contaminated_variant(self):
        self.assertNotIn("Contaminated", "M18SmokeGrenade_White")


class OperatorSurfaces(unittest.TestCase):
    def test_marker_is_listed_in_the_acceptance_docs_and_marker_test(self):
        docs = (ROOT / "docs/LOCAL_ACCEPTANCE_V1.md").read_text()
        self.assertIn(MARKER, docs)
        self.assertIn('"ai_tactics"', (ROOT / "tests/unit/test_acceptance_markers.py").read_text())

    def test_friend_bundle_ships_the_tactics_config_and_knows_its_source(self):
        from tools.setup import friend_bundle as fb
        self.assertTrue(fb._profile_allowed("HollowCountry/expansion-ai-tactics.json"))
        self.assertIn("mods/HollowCountryExpansionAI/data/defaults/expansion-ai-tactics.json",
                      fb.PROFILE_SOURCES["HollowCountry/expansion-ai-tactics.json"])
        self.assertTrue((ROOT / fb.PROFILE_SOURCES["HollowCountry/expansion-ai-tactics.json"][0]).is_file())


class CompileLimits(unittest.TestCase):
    """Native Enforce limits: at most 9 '+' per statement, no inline allocation passed as an argument."""

    def statements(self, path):
        for number, line in enumerate(read(path).splitlines(), 1):
            if line.strip().startswith("//"):
                continue
            bare = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
            bare = re.sub(r"\+\+", "", bare)
            yield number, bare.count("+")

    def test_no_statement_exceeds_nine_plus_operators(self):
        for path in (TACTICS, THROWABLES):
            for number, count in self.statements(path):
                self.assertLessEqual(count, 9, path.name + ":" + str(number) + " has " + str(count) + " '+'")

    def test_no_inline_new_as_an_argument(self):
        code = re.sub(r"//[^\n]*", "", read(TACTICS) + read(THROWABLES))
        self.assertNotRegex(code, r"[(,]\s*new\s+\w+", "allocate a local first; native rejects it for non-out params")
        self.assertNotRegex(code, r"Register\(new")


if __name__ == "__main__":
    unittest.main()
