"""v1 audit: search makes native AI noise (#15 #20); vision range from clothing,
darkness and lights (#20 #35 #56).

Offline tests execute authored Enforce policy text with explicit synthetic
inputs and inspect authored source shape. They prove neither compilation nor
any DayZ behavior: the noise config path, the AI vision multiplier semantics
and the factor constants are all unobserved at runtime. Both features stay
behind local-acceptance gates (vision) or documented acceptance steps (noise).

Engine citations (installed 1.30.164289 scripts):
  3_Game/Noise.c:7            NoiseSystem.AddNoisePos(EntityAI, vector, NoiseParams, float)
  3_Game/Noise.c:25           NoiseParams.LoadFromPath
  4_World/Classes/UserActionsComponent/Actions/Interact/ActionOpenDoors.c:78-90
                              vanilla OnEndServer noise pattern
  4_World/Static/MiscGameplayFunctions.c:1830  GenerateAINoiseAtPositionEx
  3_Game/Systems/AI/AITarget_callbacks.c:13   GetMaxVisionRangeModifier(EntityAI pApplicant)
  4_World/Entities/ManBase/PlayerBase/AITargetCallbacksPlayer.c:45-84
"""
import ast
import math
from pathlib import Path
import re
import unittest

try:
    from .test_fuel_transfer import Binary32, f32
    from .test_crafting_completion import body
except ImportError:
    from test_fuel_transfer import Binary32, f32
    from test_crafting_completion import body

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "mods/HollowCountry/scripts/4_World"
VISION = SCRIPTS / "Infected/HCInfectedVision.c"
NOISE = SCRIPTS / "Loot/HCSearchNoise.c"
ACTION = SCRIPTS / "Interiors/HCInteriorAction.c"
INF = float("inf")
NAN = float("nan")


def strip_comments(text):
    return re.sub(r"//[^\n]*", "", text)


def class_text(path, name):
    """Text of one top-level class (up to the next top-level class)."""
    source = path.read_text()
    match = re.search(r"^(?:modded )?class " + re.escape(name) + r"\b", source, re.M)
    if not match:
        raise AssertionError("missing authored class: " + name)
    rest = source[match.start():]
    tail = re.search(r"^(?:modded )?class ", rest[1:], re.M)
    return rest[: tail.start() + 1] if tail else rest


class Math:
    """Only the Enforce Math members the authored policy is allowed to call."""
    @staticmethod
    def Clamp(value, low, high):
        return min(max(value, low), high)


def authored_class(path, name):
    namespace = {"__builtins__": {}, "f32": f32, "Math": Math}
    text = strip_comments(class_text(path, name))
    signatures = re.findall(r"static (bool|float) (\w+)\(([^)]*)\)", text)
    if not signatures or len(signatures) != len(re.findall(r"\bstatic\b", text)):
        raise AssertionError("unsupported method declaration in " + name)
    for result_type, method, parameters in signatures:
        args = []
        for parameter in parameters.split(","):
            match = re.fullmatch(r"\s*float (\w+)\s*", parameter)
            if not match:
                raise AssertionError("unsupported parameter: " + parameter)
            args.append(match[1])
        method_body = body(str(path), method)
        method_body = strip_comments(method_body)
        if "{" in method_body or "}" in method_body:
            raise AssertionError("unsupported nested control flow")
        lines = ["def %s(%s):" % (method, ",".join(args))]
        lines += ["    %s = f32(%s)" % (arg, arg) for arg in args]
        for statement in method_body.split(";"):
            statement = statement.strip()
            if not statement:
                continue
            statement = re.sub(r"^float (\w+) =", r"\1 =", statement)
            statement = statement.replace("&&", " and ").replace("||", " or ")
            statement = re.sub(r"!(?!=)", "not ", statement)
            statement = re.sub(r"\btrue\b", "True", statement)
            statement = re.sub(r"\bfalse\b", "False", statement)
            statement = re.sub(
                r"^if \((.*)\)\s+(return .*|\w+ = .*)$",
                r"if \1: \2", statement, flags=re.S,
            )
            if not re.match(r"^(?:if |return |\w+ = )", statement):
                raise AssertionError("unsupported statement: " + statement)
            if result_type == "float":
                statement = re.sub(r"\breturn (.*)$", r"return f32(\1)", statement)
            lines.append("    " + statement.replace("\n", " "))
        tree = Binary32().visit(ast.parse("\n".join(lines)))
        exec(compile(ast.fix_missing_locations(tree), str(path), "exec"), namespace)
    return namespace


class VisionPolicyBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = authored_class(VISION, "HCInfectedVisionPolicy")

    def factor(self, coef=1.0, hour=12.0, lit=0.0):
        return self.policy["Factor"](coef, hour, lit)

    def test_given_neutral_clothing_daylight_no_light_then_exactly_native(self):
        self.assertEqual(1.0, self.factor())

    def test_given_any_inputs_then_factor_is_finite_and_clamped_to_0_6_1_3(self):
        coefs = (-5.0, 0.0, 0.1, 0.5, 0.6, 0.9, 1.0, 1.2, 1.3, 2.0, 1e30, INF, -INF, NAN)
        hours = [h / 2.0 for h in range(-2, 52)] + [INF, -INF, NAN]
        for coef in coefs:
            for hour in hours:
                for lit in (0.0, 1.0, 0.5, NAN, INF):
                    value = self.factor(coef, hour, lit)
                    self.assertTrue(math.isfinite(value), (coef, hour, lit))
                    self.assertGreaterEqual(value, 0.6 - 1e-6, (coef, hour, lit))
                    self.assertLessEqual(value, 1.3 + 1e-6, (coef, hour, lit))

    def test_given_invalid_or_uninitialised_inputs_then_neutral_not_a_penalty(self):
        self.assertEqual(1.0, self.policy["ClothingFactor"](0.0))
        self.assertEqual(1.0, self.policy["ClothingFactor"](-1.0))
        self.assertEqual(1.0, self.policy["ClothingFactor"](NAN))
        self.assertEqual(0.0, self.policy["Nightness"](NAN))
        self.assertEqual(0.0, self.policy["Nightness"](-1.0))
        self.assertEqual(0.0, self.policy["Nightness"](24.0))

    def test_given_camouflaging_clothing_then_shorter_range_floored_at_0_6(self):
        self.assertLess(self.factor(coef=0.8), self.factor(coef=1.0))
        self.assertEqual(f32(0.8), self.factor(coef=0.8))
        self.assertEqual(f32(0.6), self.factor(coef=0.2))

    def test_given_hour_then_nightness_ramps_at_dusk_and_dawn(self):
        n = self.policy["Nightness"]
        self.assertEqual(0.0, n(12.0))
        self.assertEqual(0.0, n(7.0))
        self.assertEqual(0.0, n(19.0))
        self.assertEqual(1.0, n(21.0))
        self.assertEqual(1.0, n(23.5))
        self.assertEqual(1.0, n(0.0))
        self.assertEqual(1.0, n(4.9))
        self.assertEqual(0.5, n(6.0))
        self.assertEqual(0.5, n(20.0))

    def test_given_darkness_then_unlit_player_is_seen_from_less_far(self):
        self.assertEqual(f32(0.75), self.factor(hour=2.0))
        self.assertLess(self.factor(hour=2.0), self.factor(hour=12.0))

    def test_given_lit_light_at_night_then_seen_from_further_than_unlit(self):
        unlit = self.factor(hour=2.0, lit=0.0)
        lit = self.factor(hour=2.0, lit=1.0)
        self.assertGreater(lit, unlit)
        self.assertAlmostEqual(1.125, lit, places=5)

    def test_given_lit_light_in_daylight_then_small_bounded_gain_only(self):
        self.assertAlmostEqual(1.1, self.factor(hour=12.0, lit=1.0), places=5)

    def test_given_best_case_for_detection_then_capped_at_1_3(self):
        self.assertEqual(f32(1.3), self.factor(coef=1.3, hour=2.0, lit=1.0))
        self.assertEqual(f32(1.3), self.factor(coef=1.3, hour=12.0, lit=1.0))


class VisionSourceShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = VISION.read_text()

    def test_closed_by_default_with_local_acceptance_marker_logged_experimental(self):
        qual = class_text(VISION, "HCInfectedVisionQualification")
        self.assertRegex(body(str(VISION), "Qualified"), r"return false;")
        self.assertIn('"$profile:HollowCountry/acceptance/infected_vision.enable"', qual)
        self.assertIn("FileExist(", qual)
        self.assertIn("EXPERIMENTAL", qual)
        self.assertIn("runtime acceptance PENDING", qual)
        admitted = body(str(VISION), "Admitted")
        self.assertIn("s_Checked", admitted)
        self.assertEqual(1, admitted.count("LocalAcceptanceOptIn()"))
        self.assertEqual(1, qual.count("FileExist("))

    def test_override_matches_engine_prototype_and_returns_native_when_not_admitted(self):
        self.assertIn("modded class AITargetCallbacksPlayer", self.source)
        self.assertIn("override float GetMaxVisionRangeModifier(EntityAI pApplicant)", self.source)
        method = strip_comments(body(str(VISION), "GetMaxVisionRangeModifier"))
        self.assertTrue(method.strip().startswith("float nativeRange = super.GetMaxVisionRangeModifier(pApplicant);"))
        admit = method.index("HCInfectedVisionQualification.Admitted()")
        self.assertLess(method.index("super.GetMaxVisionRangeModifier(pApplicant)"), admit)
        self.assertLess(admit, method.index("PlayerFactor("))
        refusal = method[admit:method.index("PlayerFactor(")]
        self.assertIn("return nativeRange;", refusal)
        self.assertIn("IsServer()", method)
        self.assertRegex(method, r"return nativeRange \* \w+;")

    def test_player_comes_from_own_constructor_capture_never_private_m_player(self):
        # AITargetCallbacksPlayer.c:5 declares m_Player private; a modded class
        # cannot read it, so the player is captured in a modded constructor.
        code = strip_comments(self.source)
        self.assertNotRegex(code, r"\bm_Player\b")
        modded = class_text(VISION, "AITargetCallbacksPlayer")
        self.assertIn("protected PlayerBase m_HCVisionPlayer;", modded)
        ctor = strip_comments(body(str(VISION), "AITargetCallbacksPlayer"))
        self.assertIn("m_HCVisionPlayer = pPlayer;", ctor)
        self.assertIn("void AITargetCallbacksPlayer(PlayerBase pPlayer)", modded)
        method = strip_comments(body(str(VISION), "GetMaxVisionRangeModifier"))
        self.assertIn("m_HCVisionPlayer", method)
        self.assertRegex(method, r"if \(!m_HCVisionPlayer\)\s+return nativeRange;")

    def test_hot_path_allocates_nothing_and_reads_only_target_local_state(self):
        for method in ("GetMaxVisionRangeModifier", "PlayerFactor", "LitItem", "HasLitLight"):
            text = strip_comments(body(str(VISION), method))
            self.assertNotIn("new ", text, method)
            self.assertNotIn("FileExist", text, method)
            self.assertNotIn("GetGame().GetPlayers", text, method)
            self.assertNotIn("GetObjectsAtPosition", text, method)
            self.assertNotIn("pApplicant.", text, method)
        factor = strip_comments(body(str(VISION), "PlayerFactor"))
        self.assertIn("player.GetVisibilityCoef()", factor)
        self.assertIn("GetGame().GetDayTime()", factor)

    def test_light_scan_is_bounded_and_uses_native_light_apis(self):
        lit = strip_comments(body(str(VISION), "HasLitLight"))
        self.assertIn("player.GetItemInHands()", lit)
        self.assertIn('FindAttachmentBySlotName("Headgear")', lit)
        self.assertIn("AttachmentCount()", lit)
        self.assertIn("GetAttachmentFromIndex(", lit)
        self.assertRegex(lit, r"count > 8")
        item = strip_comments(body(str(VISION), "LitItem"))
        self.assertIn("IsLightSource()", item)
        self.assertIn("IsIgnited()", item)

    def test_no_forbidden_enforce_shapes(self):
        for path in (VISION, NOISE):
            text = strip_comments(path.read_text())
            self.assertNotRegex(text, r"\?[^\n:]*:", path.name)  # no ternary
            for line in text.splitlines():
                self.assertFalse(line.lstrip().startswith(("||", "&&")), line)
                self.assertLessEqual(line.count("+"), 8, line)

    def test_no_personal_home_path_in_sources(self):
        for path in (VISION, NOISE, Path(__file__)):
            self.assertNotRegex(path.read_text(), r"/home/[a-z]")


class NoisePolicyBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = authored_class(NOISE, "HCSearchNoisePolicy")

    def test_given_commit_took_site_from_open_to_complete_then_one_emission(self):
        self.assertTrue(self.policy["ShouldEmit"](0, 2))

    def test_given_refusal_cancel_stopped_or_repeat_then_no_emission(self):
        # Phase meanings from HCInteriorModule.CommitSearch: 0 open, 1 reserved,
        # 2 complete, 3 stopped/unavailable. A commit that did not move 0 -> 2
        # (refused, failed, cancelled before commit, or already complete) is silent.
        for before, after in ((0, 0), (0, 1), (0, 3), (1, 2), (2, 2), (3, 3), (-1, 2), (0, -1), (2, 0)):
            self.assertFalse(self.policy["ShouldEmit"](before, after), (before, after))


class NoiseSourceShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = NOISE.read_text()
        cls.action = ACTION.read_text()

    def test_uses_native_noise_system_with_vanilla_config_path(self):
        text = strip_comments(self.source)
        self.assertIn('"CfgVehicles SurvivorBase NoiseActionDefault"', text)
        self.assertIn(".LoadFromPath(", text)
        self.assertIn("GetGame().GetNoiseSystem()", text)
        self.assertEqual(1, text.count(".AddNoisePos("))
        self.assertIn("player.GetPosition()", text)
        self.assertNotIn(".AddNoiseTarget(", text)
        self.assertNotIn(".AddNoise(", text)

    def test_emission_is_server_only_alive_actor_and_once_per_completion(self):
        emit = strip_comments(body(str(NOISE), "Emit"))
        self.assertIn("IsServer()", emit)
        self.assertIn("IsAlive()", emit)
        self.assertEqual(1, emit.count(".AddNoisePos("))
        self.assertNotRegex(emit, r"\b(for|while)\b")
        completed = strip_comments(body(str(NOISE), "OnCommitted"))
        self.assertIn("HCSearchNoisePolicy.ShouldEmit(", completed)
        self.assertLess(completed.index("ShouldEmit("), completed.index(".Emit("))
        self.assertEqual(1, completed.count(".Emit("))
        self.assertNotRegex(completed, r"\b(for|while)\b")

    def test_action_hook_is_server_completion_only_never_start_or_end(self):
        finish = strip_comments(body(str(ACTION), "OnFinishProgressServer"))
        self.assertIn("HCSearchNoise.PhaseOf(action_data)", finish)
        self.assertIn("HCSearchNoise.OnCommitted(action_data,", finish)
        self.assertLess(finish.index("CommitSearch("), finish.index("OnCommitted("))
        self.assertLess(finish.index("PhaseOf("), finish.index("CommitSearch("))
        for hook in ("OnStartServer", "OnEndServer", "ActionCondition", "ActionConditionContinue"):
            self.assertNotIn("HCSearchNoise", strip_comments(body(str(ACTION), hook)), hook)
        self.assertEqual(2, strip_comments(self.action).count("HCSearchNoise."))

    def test_crafting_salvage_files_are_untouched_by_noise_work(self):
        for path in (SCRIPTS / "Crafting").glob("*.c"):
            self.assertNotIn("HCSearchNoise", path.read_text(), path.name)


if __name__ == "__main__":
    unittest.main()
