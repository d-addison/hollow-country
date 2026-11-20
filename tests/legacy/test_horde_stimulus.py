"""Execute authored stimulus decisions on explicit synthetic clues, never DayZ AI.

The deliberately small translator rejects unsupported syntax. Native observations,
lighting, hearing, compilation and client presentation are outside these tests.
"""
import re
from types import SimpleNamespace as NS
import unittest

if __package__:
    from tests.legacy.test_infected_contract import SOURCE, policy_functions
else:
    from tests.legacy.test_infected_contract import SOURCE, policy_functions


def method_body(filename, signature):
    source = (SOURCE / filename).read_text()
    if signature not in source:
        raise AssertionError(f"Missing authored contract: {filename}: {signature}")
    start = source.index("{", source.index(signature)) + 1
    end, depth = start, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return re.sub(r"//[^\n]*", "", source[start:end - 1])


def compile_method(filename, signature, parameters, scope, member_calls=()):
    """Translate actual authored bodies; explicit stubs provide native collaborators.

    out reason uses a mutable cell only in this harness. No fallback Python policy.
    """
    body = method_body(filename, signature)
    body = re.sub(r"if (\([^\n]+\))\s*([^{};\n]+;)", r"if \1 {\2}", body)
    body = re.sub(r"for \(int (\w+) = ([^;]+); \1 >= 0; \1--\)",
                  r"for \1 in range(\2, -1, -1)", body)
    body = re.sub(r"foreach \(HCAlertRoot (\w+) : ([^)]+)\)", r"for \1 in \2", body)
    lines, indent = [f"def run(self, {parameters}):"], 1
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
        uninitialized = re.fullmatch(r"(?:int|float|bool|HCInfectedClue|HCAlertRoot)\s+\w+", token)
        token = re.sub(r"\b(?:int|float|bool|HCInfectedClue|HCAlertRoot|HCAlertEmission|HCInfectedActor)\s+", "", token)
        token = re.sub(r"\bnew (\w+)\b", r"\1()", token)
        token = re.sub(r"\b(m_\w+)\b", r"self.\1", token)
        for name in member_calls:
            token = re.sub(r"(?<![.\w])" + name + r"\(", "self." + name + "(", token)
        token = token.replace("&&", " and ").replace("||", " or ")
        token = re.sub(r"!(?!=)", "not ", token)
        for old, new in (("true", "True"), ("false", "False"), ("null", "None")):
            token = re.sub(r"\b" + old + r"\b", new, token)
        if "reason" in parameters.split(", "):
            token = re.sub(r"\breason\b(?!\.)", "reason.value", token)
        elif token == "reason":
            token = "reason = NS(value=0)"
        after = None
        if token.endswith("++"):
            token = token[:-2]
            if " = " in token:
                after = token.split(" = ", 1)[1] + " += 1"
            else:
                token += " += 1"
        if uninitialized and re.fullmatch(r"\w+", token):
            token += " = None"  # uninitialized Enforce reference local
        if token.startswith("if ("):
            token = "if " + token[4:-1] + ":"
        elif token.startswith("while ("):
            token = "while " + token[7:-1] + ":"
        elif token.startswith("for ") or token == "else":
            token += ":"
        lines.append("    " * indent + token)
        if after:
            lines.append("    " * indent + after)
    exec(compile("\n".join(lines), f"{filename}: {signature} [synthetic]", "exec"), scope)
    return scope["run"]


class SyntheticClue:
    def __init__(self, provenance=1, observed=99, expires=110, strength=1, hops=0):
        self.Origin = (3, 4, 5)
        self.Provenance, self.Observed, self.Expires = provenance, observed, expires
        self.Strength, self.Hops, self.EventId = strength, hops, 17

    def IsLive(self, now):
        return policy_functions()["AcceptClue"](
            now, self.Observed, self.Expires, self.Provenance, self.Strength, self.Hops)


def stimulus_api():
    scope = dict(NS=NS, HCInfectedClue=SyntheticClue, HCInfectedPolicy=NS(**policy_functions()))
    text = (SOURCE / "HCHordeStimulus.c").read_text()
    # Enums are declarations, never an alternate implementation of decisions.
    # Enforce requires Enum.MEMBER (native compile 078), so each enum is a namespace.
    for enum, body in re.findall(r"\benum\s+(\w+)\s*\{([^}]*)\}", text):
        scope[enum] = NS(**{name: int(value) for name, value in re.findall(r"\b(\w+)\s*=\s*(\d+)", body)})
    api = NS()
    scope["HCHordeStimulus"] = api
    for name, parameters in (
        ("Category", "candidate, now"),
        ("PreferClue", "candidate, previousClue, now"),
        ("SelectClue", "visual, heard, admitExternalHeard, now, reason"),
        ("FreezeClue", "candidate"),
        ("ChooseClue", "actor, now, hearing"),
    ):
        function = compile_method("HCHordeStimulus.c", name + "(", parameters, scope)
        setattr(api, name, lambda *args, f=function: f(None, *args))
        scope[name] = getattr(api, name)
    return api


class HordeStimulusTests(unittest.TestCase):
    def select(self, visual, heard, admitted=True, now=100):
        reason = NS(value=-1)
        chosen = stimulus_api().SelectClue(visual, heard, admitted, now, reason)
        return chosen, reason.value

    def test_live_observed_visual_beats_newer_sound_and_reports_reason(self):
        visual, heard = SyntheticClue(2, 95), SyntheticClue(1, 99)
        chosen, reason = self.select(visual, heard)
        self.assertIs(visual, chosen)
        self.assertEqual(1, reason)

    def test_sound_beats_expired_visual_or_unknown_retained_memory(self):
        heard = SyntheticClue()
        for memory in (SyntheticClue(2, 80, 100), SyntheticClue(0), SyntheticClue(7)):
            with self.subTest(memory=vars(memory)):
                self.assertEqual((heard, 2), self.select(memory, heard))

    def test_stale_but_live_visual_beats_a_fresher_sound_by_deliberate_precedence(self):
        # "Live" means inside its TTL. The oldest still-live visual clue wins over
        # the newest sound; recency only orders clues of the same category.
        # Two-client perception acceptance of this precedence is pending.
        visual = SyntheticClue(2, observed=71, expires=100.5)
        heard = SyntheticClue(1, observed=99.9, expires=129.5)
        self.assertEqual((visual, 1), self.select(visual, heard))
        actor = NS(Visual=visual, Heard=heard, HeardExternally=True)
        frozen = stimulus_api().ChooseClue(actor, 100, True)
        self.assertEqual(vars(visual), vars(frozen))
        # One tick later the same visual is memory and the sound is selected.
        self.assertEqual((heard, 2), self.select(visual, heard, now=100.5))
        text = (SOURCE / "HCHordeStimulus.c").read_text()
        header = text.split("enum HCStimulusCategory", 1)[0]
        for phrase in ("stale-but-live", "two-client", "pending"):
            self.assertIn(phrase, header)

    def test_freeze_preserves_hops_including_the_two_hop_boundary(self):
        api = stimulus_api()
        for hops in (0, 1, 2):
            with self.subTest(hops=hops):
                original = SyntheticClue(1, hops=hops)
                frozen = api.FreezeClue(original)
                self.assertIsNot(original, frozen)
                self.assertEqual(hops, frozen.Hops)
                self.assertEqual(vars(original), vars(frozen))
        original = SyntheticClue(1, hops=2)
        frozen = api.FreezeClue(original)
        original.Hops = 0
        self.assertEqual(2, frozen.Hops)

    def test_memory_is_explicit_but_never_promoted_to_observation(self):
        api = stimulus_api()
        self.assertEqual(0, api.Category(None, 100))
        for memory in (SyntheticClue(2, 80, 100), SyntheticClue(0)):
            self.assertEqual(1, api.Category(memory, 100))
            self.assertEqual((None, 3), self.select(memory, None))
        self.assertEqual(2, api.Category(SyntheticClue(1), 100))
        self.assertEqual(3, api.Category(SyntheticClue(2), 100))
        self.assertEqual((None, 0), self.select(None, None))

    def test_expired_future_invalid_strength_and_hops_are_never_chosen(self):
        for bad in (SyntheticClue(2, 80, 100), SyntheticClue(1, 80, 100),
                    SyntheticClue(2, 101), SyntheticClue(1, 99, 140),
                    SyntheticClue(2, strength=0), SyntheticClue(1, hops=3)):
            with self.subTest(clue=vars(bad)):
                self.assertIsNone(self.select(bad, bad)[0])
        self.assertIsNone(self.select(SyntheticClue(2), SyntheticClue(), now=float("nan"))[0])

    def test_nonadmitted_heard_input_is_ignored_including_self_voice(self):
        self.assertEqual((None, 0), self.select(None, SyntheticClue(), False))
        visual = SyntheticClue(2)
        self.assertEqual((visual, 1), self.select(visual, SyntheticClue(), False))
        api = stimulus_api()
        actor = NS(Visual=None, Heard=SyntheticClue(), HeardExternally=False)
        self.assertIsNone(api.ChooseClue(actor, 100, True))

    def test_source_slots_do_not_upgrade_wrong_provenance(self):
        self.assertIsNone(self.select(SyntheticClue(1), SyntheticClue(2))[0])

    def test_individual_helper_and_cohort_wrapper_agree_for_same_inputs(self):
        api = stimulus_api()
        clues = (None, SyntheticClue(2, 95), SyntheticClue(1), SyntheticClue(0), SyntheticClue(2, 80, 100))
        for visual in clues:
            for heard in clues:
                for hearing in (False, True):
                    for external in (False, True):
                        actor = NS(Visual=visual, Heard=heard, HeardExternally=external)
                        reason = NS(value=-1)
                        chosen = api.SelectClue(visual, heard, hearing and external, 100, reason)
                        frozen = api.ChooseClue(actor, 100, hearing)
                        with self.subTest(visual=visual, heard=heard, hearing=hearing, external=external):
                            if chosen is None:
                                self.assertIsNone(frozen)
                            else:
                                self.assertIsNot(chosen, frozen)
                                self.assertEqual(vars(chosen), vars(frozen))

    def test_cohort_comparison_uses_category_then_recency_then_strength(self):
        prefer = stimulus_api().PreferClue
        self.assertTrue(prefer(SyntheticClue(2, 95), SyntheticClue(1, 99), 100))
        self.assertFalse(prefer(SyntheticClue(1, 99), SyntheticClue(2, 95), 100))
        self.assertTrue(prefer(SyntheticClue(1, 99), SyntheticClue(0), 100))
        self.assertFalse(prefer(SyntheticClue(0), SyntheticClue(1), 100))
        self.assertFalse(prefer(SyntheticClue(2, 80, 100), None, 100))
        self.assertTrue(prefer(SyntheticClue(1, 99, strength=.5), SyntheticClue(1, 98), 100))
        self.assertTrue(prefer(SyntheticClue(1, strength=1), SyntheticClue(1, strength=.5), 100))
        self.assertFalse(prefer(SyntheticClue(1), SyntheticClue(1), 100))

    def test_frozen_selection_never_refreshes_original_or_copy(self):
        actor = NS(Visual=SyntheticClue(2), Heard=None, HeardExternally=False)
        before = vars(actor.Visual).copy()
        frozen = stimulus_api().ChooseClue(actor, 100, True)
        self.assertEqual(before, vars(actor.Visual))
        self.assertEqual(before, vars(frozen))
        actor.Visual.Origin = (999, 999, 999)
        self.assertEqual(before["Origin"], frozen.Origin)


if __name__ == "__main__":
    unittest.main()
