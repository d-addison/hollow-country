"""Authored route policies/scheduler on synthetic observations; no native AI claim."""
import math
import re
from types import SimpleNamespace
import unittest
if __package__:
    from .test_infected_contract import SOURCE, policy_functions
else:
    from test_infected_contract import SOURCE, policy_functions


class NativeArray(list):
    """Explicit synthetic Enforce array, including non-null empty arrays."""
    def __bool__(self): return True
    def Count(self): return len(self)
    def Insert(self, value): self.append(value)
    def Remove(self, index): self.pop(index)
    def RemoveItem(self, value):
        if value in self: self.remove(value)
    def Find(self, value): return self.index(value) if value in self else -1
    def Clear(self): self.clear()


def authored_navigation(signature, context, **namespace):
    """Execute a restricted translation of the shipped body, never native AI.

    Unsupported syntax raises, rather than selecting a handwritten policy model.
    Native collaborators and any vectors are supplied explicitly by each test.
    """
    source = (SOURCE / "HCInfectedNavigation.c").read_text()
    start = source.index("{", source.index(signature)) + 1
    depth, end = 1, start
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    body = re.sub(r"//[^\n]*", "", source[start:end-1])
    body = re.sub(r'Print\("[^"\n]*"\);', 'Print();', body)
    body = re.sub(r"if (\([^\n]+\))\s*([^{};\n]+;)", r"if \1 {\2}", body)
    body = re.sub(r"for \(int (\w+) = ([^;]+); \1 >= 0; \1--\)", r"for \1 in range(\2, -1, -1)", body)
    body = re.sub(r"(?:ref )?array<ref BehaviourGroupInfectedPackWaypointParams> ", "", body)
    body = body.replace("new array<ref BehaviourGroupInfectedPackWaypointParams>", "NativeArray()")
    body = body.replace("ref set<Object> ", "").replace("new set<Object>", "NativeArray()")
    body = re.sub(r"\bnew (\w+)\(", r"\1(", body)
    body = re.sub(r"\bnew (\w+)\b", r"\1()", body)
    body = re.sub(r"\bvector (\w+), (\w+);", r"\1 = None; \2 = None;", body)
    body = re.sub(r"\bint (\w+);", r"\1 = 0;", body)
    lines, indent = ["def run(self):"], 1
    for token in re.split(r"([{};])", body):
        token = token.strip()
        if not token or token == ";": continue
        if token == "{": indent += 1; continue
        if token == "}": indent -= 1; continue
        token = re.sub(r"\b(?:bool|int|float|vector|ZombieBase|AIWorld|AIGroup|AIAgent|BehaviourGroupInfectedPack|DayZInfectedInputController|EntityAI)\s+", "", token)
        token = re.sub(r"\b(m_\w+|Group|RouteResult)\b", r"self.\1", token)
        token = re.sub(r"(?<![.\w])GetAIWorld\(", "self.GetAIWorld(", token)
        token = re.sub(r"\b(self\.m_\w+)\+\+", r"\1 += 1", token)
        token = token.replace("&&", " and ").replace("||", " or ")
        token = re.sub(r"!(?!=)", "not ", token)
        for before, after in (("true", "True"), ("false", "False"), ("null", "None"), ("this", "self")):
            token = re.sub(r"\b"+before+r"\b", after, token)
        if token.startswith("if ("): token = "if " + token[4:-1] + ":"
        elif token.startswith("for "): token += ":"
        elif token == "else": token += ":"
        lines.append("    " * indent + token)
    scope = dict(NativeArray=NativeArray, Print=lambda: None,
                 HCInfectedPolicy=SimpleNamespace(**policy_functions()))
    scope.update(namespace)
    exec(compile("\n".join(lines), "authored-navigation:" + signature, "exec"), scope)
    return scope["run"](context)


def authored_scheduler():
    source = (SOURCE / "HCInfectedModule.c").read_text()
    signature = "protected void RetargetCohorts()"
    start = source.index("{", source.index(signature)) + 1
    depth, end = 1, start
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    body = re.sub(r"//[^\n]*", "", source[start:end-1])
    body = re.sub(r"for \(int (\w+) = 0; \1 < (\w+); \1\+\+\)", r"for \1 in range(\2)", body)
    body = re.sub(r"(\w+(?:\.\w+)*)\.Count\(\)", r"len(\1)", body)
    lines = ["def run():", "    global m_RetargetCursor, m_RoutesRemaining, m_Dirty"]
    indent = 1
    for token in re.split(r"([{};])", body):
        token = token.strip()
        if not token or token == ";": continue
        if token == "{": indent += 1; continue
        if token == "}": indent -= 1; continue
        token = re.sub(r"\b(?:int|bool|HCHordeRecord|HCHordeSweep|HCNativeInfectedPack)\s+", "", token)
        token = token.replace("HCInfectedPolicy.", "")
        token = token.replace("&&", " and ").replace("||", " or ")
        token = re.sub(r"!(?!=)", "not ", token)
        token = re.sub(r"\btrue\b", "True", token)
        token = re.sub(r"\bfalse\b", "False", token)
        token = token.replace("m_RoutesRemaining--", "m_RoutesRemaining -= 1")
        if token.startswith("if ("): token = "if " + token[4:-1] + ":"
        elif token.startswith("for "): token += ":"
        elif token == "else": token += ":"
        lines.append("    " * indent + token)
    namespace = policy_functions()
    exec(compile("\n".join(lines), "authored-RetargetCohorts", "exec"), namespace)
    return namespace


class InfectedRouteTests(unittest.TestCase):
    def test_route_journal_dirties_destination_and_plan_changes(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        snapshot = module.split("protected void SnapshotRoute", 1)[1].split("protected void RetargetCohorts", 1)[0]
        self.assertIn("record.RoutePlanned != pack.RoutePlanned", snapshot)
        self.assertIn("vector.DistanceSq(record.RouteEnd, pack.RouteEnd) > 0", snapshot)

    def test_route_requires_every_surviving_member_to_arrive(self):
        p = policy_functions()["RouteObservationResult"]
        self.assertEqual(1, p(10, 30, 1, 6, 5, False, False))
        self.assertEqual(2, p(10, 30, 1, 6, 6, False, False))
        self.assertEqual(6, p(10, 30, 1, 0, 0, False, False))
        self.assertEqual(6, p(10, 30, 1, 5, 5, True, False))
        self.assertEqual(5, p(10, 30, 1, 6, 6, False, True))
        self.assertEqual(4, p(30, 30, 1, 6, 6, False, False))
        self.assertEqual(3, p(10, 30, 15, 6, 0, False, False))
        self.assertEqual(6, p(math.nan, 30, 1, 6, 6, False, False))

    def test_progress_is_toward_waypoint_not_arbitrary_wandering(self):
        p = policy_functions()["RouteMadeProgress"]
        self.assertTrue(p(99, 100))
        self.assertFalse(p(101, 100))
        self.assertFalse(p(100, 100))
        self.assertFalse(p(99.9, 100))
        self.assertFalse(p(math.nan, 100))
        self.assertFalse(p(-1, 100))

    def test_route_metadata_does_not_confuse_intent_with_completion(self):
        p = policy_functions()["ValidRouteMetadata"]
        self.assertTrue(p(0, 0, 0, 0, False))
        self.assertTrue(p(1, 1, 1, 0, True))
        self.assertTrue(p(2, 2, 3, 3, False))
        self.assertTrue(p(1, 4, 1, 0, False))
        for args in ((0, 1, 0, 0, True), (1, 2, 3, 2, False),
                     (1, 1, 1, 1, True), (1, 2, 1, 1, True),
                     (1, 1, 4, 0, True), (3, 1, 1, 0, True)):
            self.assertFalse(p(*args), args)

    def test_no_fabricated_migration_and_observed_progress_is_persisted(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        navigation = (SOURCE / "HCInfectedNavigation.c").read_text()
        self.assertNotIn('anchor + "40 0 0"', module)
        self.assertIn("HCHordeStimulus.ChooseClue", module.split("protected void TryAdopt", 1)[1])
        self.assertIn("SnapshotRoute", module)
        self.assertIn("RouteCompleted", (SOURCE / "HCInfectedState.c").read_text())
        self.assertIn("RouteObservationResult", navigation)
        self.assertIn("RouteMadeProgress", navigation)
        self.assertIn("m_RoutePlan", navigation)
        self.assertIn("arrivedMembers", navigation)
        self.assertNotIn("vector.DistanceSq(leader.GetPosition(), m_LastPosition) >= 1", navigation)
        self.assertIn("ActivateWaypoint", navigation)

    def test_native_retarget_charges_attempts_including_geometry_failure_only(self):
        p = policy_functions()["RetargetSpent"]
        self.assertFalse(p(0))
        self.assertTrue(p(1))
        self.assertTrue(p(2))
        nav = (SOURCE / "HCInfectedNavigation.c").read_text()
        method = nav.split("int Retarget(", 1)[1].split("bool Tick(float now)", 1)[0]
        before_path, after_path = method.split("if (!Reachable(", 1)
        self.assertNotIn("return 1;", before_path)
        self.assertIn("return 1;", after_path)
        self.assertIn("return 2;", after_path)
        self.assertIn("m_RetargetAttempts++", before_path)

    def _schedule(self, geometry_fails=False):
        ns = authored_scheduler()
        policy = policy_functions()["RetargetAllowed"]
        calls, attempts = [0, 0], [0, 0]
        now = [12]
        class Pack:
            def __init__(self, idx):
                self.idx = idx; self.next = 20 if idx == 0 else 0
                self.last = 9 if idx == 0 else -1
                self.spent = 1 if idx == 0 else 0
            def Retarget(self, clue, instant):
                i = self.idx; calls[i] += 1
                if not policy(instant, self.next, clue.Observed, self.last, clue.Expires, self.spent, True, False):
                    return 0
                attempts[i] += 1; self.next = instant + 10
                self.last = clue.Observed; self.spent += 1
                return 1 if geometry_fails else 2
        clues = [SimpleNamespace(Observed=9, Expires=30), SimpleNamespace(Observed=11, Expires=20)]
        for clue in clues: clue.IsLive = lambda instant, c=clue: instant < c.Expires
        sweeps = [SimpleNamespace(Clue=True, Engaged=False, Stimulus=c) for c in clues]
        ns.update(m_Sweeps=sweeps, m_Packs=[Pack(0), Pack(1)], m_RetargetCursor=0,
                  m_Config=SimpleNamespace(EnableHordeStimulusRoutes=True),
                  m_State=SimpleNamespace(Groups=[SimpleNamespace(State=1), SimpleNamespace(State=1)]),
                  m_Dirty=False, SnapshotRoute=lambda record, pack: None)
        for instant in range(12,20):
            now[0] = instant; ns["m_Now"] = instant; ns["m_RoutesRemaining"] = 1
            ns["run"]()
            self.assertGreaterEqual(ns["m_RoutesRemaining"], 0)
        return calls, attempts, ns

    def test_given_consumed_first_cue_then_second_gets_path_attempt_before_expiry(self):
        calls, attempts, ns = self._schedule()
        self.assertGreater(calls[1], 0, calls)
        self.assertEqual([0,1], attempts)
        self.assertIn(ns["m_RetargetCursor"], (0,1))

    def test_failed_geometry_spends_shared_slot_and_is_not_retried_for_free(self):
        calls, attempts, ns = self._schedule(geometry_fails=True)
        self.assertEqual([0,1], attempts)
        self.assertGreater(calls[1], 0)


if __name__ == "__main__": unittest.main()
