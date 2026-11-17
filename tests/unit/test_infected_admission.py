"""Fail-closed per-path capability admission for infected (audit D1, #19/#44).

Operator preferences stay default-on; a complex path mutates native state only
when preference AND an explicit server-only qualification are both true. The
translator executes authored Enforce bodies on explicit synthetic fixtures. It
is not an Enforce compiler and never establishes DayZ runtime behavior.
"""
import re
from types import SimpleNamespace as NS
import unittest
if __package__:
    from .test_infected_contract import SOURCE, policy_functions
    from .test_horde_stimulus import stimulus_api
else:
    from test_infected_contract import SOURCE, policy_functions
    from test_horde_stimulus import stimulus_api

PATHS = ("CEAdoption", "NativePackRoutes", "Investigation",
         "SupplementaryChains", "MemberRecovery", "HordeStimulusRoutes")
REASONS = {
    "CEAdoption": "ce_adoption_unqualified",
    "NativePackRoutes": "native_pack_routes_unqualified",
    "Investigation": "investigation_unqualified",
    "SupplementaryChains": "supplementary_chains_unqualified",
    "MemberRecovery": "member_recovery_unqualified",
    "HordeStimulusRoutes": "horde_stimulus_routes_unqualified",
}


class Array(list):
    def __bool__(self): return True
    def Count(self): return len(self)
    def Insert(self, value): self.append(value)
    def Remove(self, index): del self[index]
    def Clear(self): self.clear()
    def Find(self, value): return self.index(value) if value in self else -1


def _mask(text):
    strings = []
    def keep(match):
        strings.append(match.group(0))
        return "__S%d__" % (len(strings) - 1)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', keep, text)
    return re.sub(r"//[^\n]*", "", text), strings


def _body(text, signature):
    at = text.index(signature)
    open_paren = text.index("(", at)
    depth, i = 1, open_paren + 1
    while depth:
        depth += (text[i] == "(") - (text[i] == ")")
        i += 1
    params = [p.strip().split()[-1] for p in text[open_paren + 1:i - 1].split(",") if p.strip()]
    start = text.index("{", i) + 1
    end, depth = start, 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return params, text[start:end - 1]


DECL = re.compile(r"^(?:bool|int|float|string|vector|array|[A-Z]\w*)\s+(\w+)\s*(=[^=].*)?$", re.S)


def translate(filename, signature, bound, fields=(), statics=(), **namespace):
    """Return a Python callable for the authored body. `bound` lists instance
    methods of the same class that must resolve through `self`."""
    raw = (SOURCE / filename).read_text()
    text, strings = _mask(raw)
    params, body = _body(text, signature)
    body = re.sub(r"\bref\s+", "", body)
    body = re.sub(r"if (\([^\n]+\))\s*([^{};\n]+;)", r"if \1 {\2}", body)
    body = re.sub(r"\belse\s+(?!if\b)([^{};\s][^{};\n]*;)", r"else {\1}", body)
    body = re.sub(r"((?:foreach|for) \([^\n{]+\))[ \t]*\n\s*([^{};\s][^{};\n]*;)", r"\1 {\2}", body)
    body = re.sub(r"for \(int (\w+) = (.+?); \1 >= 0; \1--\)", r"for \1 in range(\2, -1, -1)", body)
    body = re.sub(r"for \(int (\w+) = 0; \1 < ([^;]+); \1\+\+\)", r"for \1 in range(\2)", body)
    body = re.sub(r"foreach \((?:\w+(?:<[^>]*>)?) (\w+) : ([^)]+)\)", r"for \1 in \2", body)
    body = re.sub(r"\bwhile \(([^\n]+)\)\s*\{", r"while \1 {", body)
    lines, indent = ["def run(%s):" % ", ".join(["self"] + params)], 1
    for token in re.split(r"([{};])", body):
        token = token.strip()
        if not token or token == ";": continue
        if token == "{": indent += 1; lines.append("    " * indent + "pass"); continue
        if token == "}": indent -= 1; continue
        token = re.sub(r"\bnew (\w+)(?:<[^>]*>)?", lambda m: ("Array" if m[1] == "array" else m[1]) + "()", token)
        token = re.sub(r"<[A-Za-z_][\w, <>]*>", "", token)
        decl = DECL.match(token)
        if decl and not token.startswith(("return", "else", "if", "for", "while")):
            token = decl[1] + (decl[2] or " = None")
        token = re.sub(r"([\w.]+(?:\(\))?)\.ToString\(\)", r"str(\1)", token)
        token = token.replace("&&", " and ").replace("||", " or ").replace(" / ", " // ")
        token = re.sub(r"!(?!=)", "not ", token)
        for a, b in (("true", "True"), ("false", "False"), ("null", "None")):
            token = re.sub(r"\b" + a + r"\b", b, token)
        token = re.sub(r"(?<![.\w])(m_\w+)\b", r"self.\1", token)
        for name in fields:
            token = re.sub(r"(?<![.\w])" + name + r"\b", "self." + name, token)
        for name in statics:
            token = re.sub(r"(?<![.\w])" + name + r"\b", "STATICS." + name, token)
        for name in bound:
            token = re.sub(r"(?<![.\w])" + name + r"\(", "self." + name + "(", token)
        token = re.sub(r"\b(self\.m_\w+|\w+)\+\+", r"\1 += 1", token)
        token = re.sub(r"\b(self\.m_\w+|\w+)--", r"\1 -= 1", token)
        if token.startswith("else if ("): token = "elif " + token[9:-1] + ":"
        elif token.startswith("if ("): token = "if " + token[4:-1] + ":"
        elif token.startswith("while "): token += ":"
        elif token.startswith("for "): token += ":"
        elif token == "else": token += ":"
        lines.append("    " * indent + token)
    code = "\n".join(lines)
    code = re.sub(r"__S(\d+)__", lambda m: repr(strings[int(m[1])][1:-1]), code)
    scope = dict(namespace, Array=Array, Math=NS(Min=min, Max=max))
    scope.setdefault("STATICS", NS())
    exec(compile(code, filename + ":" + signature, "exec"), scope)
    return scope["run"]


MODULE_METHODS = ("FindActor", "CanRecycleActor", "ResetSweep", "SampleActor", "SampleMembership",
    "FinishSweep", "SnapshotRoute", "RetargetCohorts", "SaveAdoptionBoundary", "TryAdopt",
    "TryInvestigate", "ReleasePacks", "Quarantine", "HeardAdmitted")


def bind_heard_admitted(context):
    """Bind the real authored HeardAdmitted body; never a test-side re-implementation."""
    translated = translate("HCInfectedModule.c", "protected bool HeardAdmitted(", MODULE_METHODS)
    context.HeardAdmitted = lambda: translated(context)


def module_call(signature, context, *args, **namespace):
    if not hasattr(context, "HeardAdmitted"):
        bind_heard_admitted(context)
    fn = translate("HCInfectedModule.c", signature, MODULE_METHODS, **namespace)
    return fn(context, *args)


# ---- explicit synthetic admission fixtures ---------------------------------

def admission(**admitted):
    return NS(**{path: bool(admitted.get(path, False)) for path in PATHS})


def requested_config(**overrides):
    state = (SOURCE / "HCInfectedState.c").read_text().split("bool IsValid()", 1)[0]
    values = {n: v == "true" for n, v in re.findall(r"\bbool (\w+) = (\w+);", state)}
    values.update(overrides)
    return NS(**values)


def admission_functions():
    """Real authored HCInfectedAdmission statics; qualification statics too."""
    source = (SOURCE / "HCInfectedState.c").read_text()
    cls = {}

    class Admission:
        pass

    qualification = NS()
    for path in PATHS:
        fn = translate("HCInfectedState.c", "static bool %sQualified(" % path, ())
        setattr(qualification, path + "Qualified", lambda fn=fn: fn(None))
        # Admitted() = Qualified OR a local-acceptance marker; with no marker it is the closed gate
        # (marker behavior is executed in test_acceptance_optins.py).
        setattr(qualification, path + "Admitted", lambda fn=fn: fn(None))
    namespace = dict(HCInfectedAdmission=Admission, HCInfectedQualification=qualification)
    for name in ("DisabledReason", "Admitted", "Reason", "Flag", "Segment"):
        if ("static " in source) and re.search(r"static \w+ %s\(" % name, source):
            sig = re.search(r"static \w+ %s\(" % name, source)[0]
            fn = translate("HCInfectedState.c", sig, (), **namespace)
            setattr(Admission, name, staticmethod(lambda *a, fn=fn: fn(None, *a)))
            namespace[name] = getattr(Admission, name)
    for name in ("Resolve", "Evaluate"):
        sig = re.search(r"static HCInfectedAdmission %s\(" % name, source)[0]
        fn = translate("HCInfectedState.c", sig, (), **namespace)
        setattr(Admission, name, staticmethod(lambda *a, fn=fn: fn(None, *a)))
        namespace[name] = getattr(Admission, name)
    sig = re.search(r"string Describe\(", source)[0]
    fn = translate("HCInfectedState.c", sig, (), fields=tuple(PATHS) + tuple(p + "Reason" for p in PATHS), **namespace)
    Admission.Describe = lambda self, fn=fn: fn(self)
    return Admission, qualification


class QualificationSourceTests(unittest.TestCase):
    def test_every_complex_path_has_a_server_only_static_qualification_returning_false(self):
        state = (SOURCE / "HCInfectedState.c").read_text()
        for path in PATHS:
            with self.subTest(path=path):
                match = re.search(r"static bool %sQualified\(\)\s*\{\s*return false;\s*\}" % path, state)
                self.assertTrue(match, "%sQualified must be a literal false until accepted native evidence" % path)
                preceding = state[:match.start()].splitlines()[-4:]
                self.assertTrue(any("evidence" in line.lower() for line in preceding),
                                "document the accepted-evidence prerequisite")
        self.assertNotIn("Qualified", (SOURCE / "HCInfectedProfiles.c").read_text().replace("ContactGuardQualified", ""))
        self.assertNotIn("Qualified", (SOURCE / "HCInfectedPolicy.c").read_text())

    def test_qualification_is_not_operator_configurable_or_persisted(self):
        state = (SOURCE / "HCInfectedState.c").read_text()
        config = state.split("class HCInfectedConfig", 1)[1].split("// Server-only static qualification", 1)[0]
        self.assertNotIn("Qualified", config)
        self.assertNotIn("Admitted", config)
        # Preferences stay default-on and the operator config is never rewritten.
        for path in PATHS:
            self.assertIn("bool Enable%s = true;" % path, config)
        module = (SOURCE / "HCInfectedModule.c").read_text()
        self.assertEqual(1, module.count("SaveFile(path, m_Config, error)"))
        self.assertNotRegex(module, r"m_Config\.Enable\w+\s*=[^=]")


class AdmissionResolutionTests(unittest.TestCase):
    def test_default_preferences_are_requested_but_not_admitted_with_specific_reasons(self):
        Admission, _ = admission_functions()
        result = Admission.Evaluate(requested_config())
        for path in PATHS:
            with self.subTest(path=path):
                self.assertIs(False, getattr(result, path))
                self.assertEqual(REASONS[path], getattr(result, path + "Reason"))

    def test_explicit_false_is_a_hard_disable_even_if_qualified(self):
        Admission, _ = admission_functions()
        off = {"Enable" + path: False for path in PATHS}
        result = Admission.Resolve(requested_config(**off), True, True, True, True, True, True)
        for path in PATHS:
            with self.subTest(path=path):
                self.assertIs(False, getattr(result, path))
                self.assertEqual("disabled_by_preference", getattr(result, path + "Reason"))

    def test_hypothetical_qualified_path_is_admitted_alone(self):
        Admission, _ = admission_functions()
        for index, path in enumerate(PATHS):
            with self.subTest(path=path):
                flags = [i == index for i in range(len(PATHS))]
                # Stimulus routes cannot be admitted without admitted pack routes.
                if path == "HordeStimulusRoutes":
                    flags[1] = True
                result = Admission.Resolve(requested_config(), *flags)
                self.assertIs(True, getattr(result, path))
                self.assertEqual("admitted", getattr(result, path + "Reason"))
                others = [p for p in PATHS if p != path and not (path == "HordeStimulusRoutes" and p == "NativePackRoutes")]
                for other in others:
                    self.assertIs(False, getattr(result, other), other)

    def test_stimulus_routes_require_admitted_pack_routes(self):
        Admission, _ = admission_functions()
        result = Admission.Resolve(requested_config(), False, False, False, False, False, True)
        self.assertIs(False, result.HordeStimulusRoutes)
        self.assertEqual("horde_stimulus_routes_requires_pack_routes", result.HordeStimulusRoutesReason)
        result = Admission.Resolve(requested_config(EnableNativePackRoutes=False), False, True, False, False, False, True)
        self.assertIs(False, result.HordeStimulusRoutes)

    def test_shipped_qualification_is_all_false(self):
        _, qualification = admission_functions()
        for path in PATHS:
            self.assertIs(False, getattr(qualification, path + "Qualified")())

    def test_default_object_is_closed_before_evaluation(self):
        state = (SOURCE / "HCInfectedState.c").read_text()
        cls = state.split("class HCInfectedAdmission", 1)[1].split("\nclass ", 1)[0]
        for path in PATHS:
            self.assertNotRegex(cls, r"bool %s\s*=\s*true" % path)
            self.assertRegex(cls, r"bool %s( = false)?;" % path)

    def test_status_reports_requested_admitted_and_reason_for_every_path(self):
        Admission, _ = admission_functions()
        text = Admission.Evaluate(requested_config()).Describe()
        for path, reason in REASONS.items():
            self.assertIn("reason=" + reason, text)
        self.assertEqual(6, text.count("requested=1"))
        self.assertEqual(6, text.count("admitted=0"))
        off = Admission.Evaluate(requested_config(EnableInvestigation=False)).Describe()
        self.assertIn("requested=0 admitted=0 reason=disabled_by_preference", off)

    def test_reason_codes_are_bounded_lowercase_tokens(self):
        state = (SOURCE / "HCInfectedState.c").read_text()
        cls = state.split("class HCInfectedAdmission", 1)[1]
        codes = set(re.findall(r'"([a-z_]+_(?:unqualified|requires_pack_routes)|disabled_by_preference|admitted)"', cls))
        self.assertTrue(set(REASONS.values()) <= codes)
        for code in codes:
            self.assertLessEqual(len(code), 48)


class StartupWiringTests(unittest.TestCase):
    def setUp(self):
        self.module = (SOURCE / "HCInfectedModule.c").read_text()
        self.start = self.module.split("override void OnStart", 1)[1].split("protected void Quarantine", 1)[0]

    def test_start_derives_and_logs_admission_once_after_config_validation(self):
        self.assertIn("m_Admission = HCInfectedAdmission.Evaluate(m_Config);", self.start)
        self.assertEqual(1, self.start.count("m_Admission.Describe()"))
        self.assertLess(self.start.index("m_Config.IsValid()"), self.start.index("HCInfectedAdmission.Evaluate"))
        self.assertLess(self.start.index("HCInfectedAdmission.Evaluate"), self.start.index("m_WorkCap = "))
        self.assertIn("runtime acceptance pending", self.start)
        self.assertIn("string AdmissionStatus()", self.module)

    def test_runtime_never_reads_the_six_preferences_except_behind_an_admitted_caller(self):
        reads = [line.strip() for line in self.module.splitlines()
                 if re.search(r"m_Config\.Enable(%s)\b" % "|".join(PATHS), line)]
        # RetargetCohorts keeps its pre-existing requested-preference guard; its only
        # caller (FinishSweep) is gated on the admitted capability.
        self.assertEqual(["if (!m_Config.EnableHordeStimulusRoutes || count < 1 || m_RoutesRemaining < 1)"], reads)
        finish = self.module.split("protected void FinishSweep", 1)[1].split("protected void SnapshotRoute", 1)[0]
        self.assertIn("if (m_Admission.HordeStimulusRoutes)", finish)
        self.assertEqual(1, self.module.count("RetargetCohorts();"))

    def test_startup_budget_checks_use_admitted_capabilities_not_preferences(self):
        # The extra eight-item prerequisite follows admitted work, never the raw
        # EnableHordes preference or a dormant journal.
        self.assertIn("bool admittedHordeWork = settings.EnableHordes && (m_Admission.CEAdoption || m_Admission.MemberRecovery || m_Admission.HordeStimulusRoutes);", self.start)
        self.assertIn("if ((admittedHordeWork || m_Admission.NativePackRoutes || m_Admission.Investigation) && m_WorkCap < 8)", self.start)
        self.assertIn("if (settings.EnableHordes && m_Admission.CEAdoption && !HCInfectedPolicy.AdoptionWorkReady(m_WorkCap))", self.start)
        self.assertIn("if (settings.EnableHordes && m_Admission.HordeStimulusRoutes && m_WorkCap < 24)", self.start)
        self.assertIn("if (m_Admission.NativePackRoutes || m_Admission.Investigation)", self.start)

    def test_variant_map_diagnostic_matches_selection_and_logs_substitutions_once(self):
        # D4 integration: a populated mixed map (e.g. [0,3,1,2]) still applies its
        # supported slots, so it must not be reported as missing; unsupported
        # stalker/heavy slots are logged once at startup by the WP4 helper.
        lines = self.start.splitlines()
        at = next(i for i, line in enumerate(lines) if "variant preference enabled" in line)
        self.assertIn("if (m_Config.EnableVariantPolicies && !variantMaps)", lines[at - 2])
        self.assertIn("missing or invalid; native profiles retained", lines[at])
        self.assertIn("ValidateMap(m_Config.CivilianVariants, false)", self.start)
        self.assertIn("ValidateMap(m_Config.MilitaryVariants, false)", self.start)
        self.assertNotIn("ValidateMap(m_Config.CivilianVariants, true)", self.start)
        self.assertIn("m_Config.CivilianVariants.Count() == 4 && m_Config.MilitaryVariants.Count() == 4", self.start)
        self.assertEqual(1, self.module.count("HCInfectedProfiles.LogUnsupportedSubstitutions(m_Config);"))
        self.assertEqual("        HCInfectedProfiles.LogUnsupportedSubstitutions(m_Config);", lines[at + 2])


# ---- behavioural: requested=true + unknown qualification performs NO mutation --

class Recorder:
    def __init__(self):
        self.events = []
    def __call__(self, name, result=None):
        def record(*args, **kwargs):
            self.events.append(name)
            return result
        return record


def pack_factory(recorder):
    class Pack:
        def __init__(self):
            recorder.events.append("pack_created")
        def Start(self, *a): recorder.events.append("pack_start"); return True
        def IsReleasing(self): return False
        def Release(self): recorder.events.append("pack_release")
        def Retarget(self, *a): recorder.events.append("retarget"); return 2
    return Pack


class UnqualifiedPathsPerformNoMutation(unittest.TestCase):
    policy = None

    @classmethod
    def setUpClass(cls):
        cls.policy = NS(**policy_functions())

    def clue(self, provenance=1):
        return NS(Origin=(1, 0, 1), Observed=1, Expires=60, Provenance=provenance, IsLive=lambda now: True)

    def candidate(self, i):
        return NS(EverAssigned=False, SearchPack=None, InfectedEntity=NS(IsAlive=lambda: True,
            GetMindStateSynced=lambda: 0, GetPosition=lambda: (float(i), 0.0, 0.0)), Profile="native",
            GroupId=0, Visual=None, Heard=None, HeardExternally=False, SearchAttempts=0, NextSearch=0)

    # -- CE adoption + native pack routes (TryAdopt) --
    def adopt_context(self, rec, admitted, requested=True):
        state = NS(Groups=Array(), Reserved=0)
        ctx = NS(m_Hordes=True, m_WorkCap=24, m_GroupCap=2, m_MemberCap=24, m_Now=10, m_Chains=True,
            m_Config=requested_config(EnableCEAdoption=requested, EnableNativePackRoutes=requested),
            m_Admission=admission(**admitted), m_State=state, m_Actors=Array([self.candidate(i) for i in range(3)]),
            m_AdoptionCursor=0, m_Sweeps=Array(), m_Packs=Array(), m_Dirty=False, m_StartedUtc=0)
        ctx.SaveAdoptionBoundary = lambda boundary: rec.events.append("save_" + boundary) or True
        ctx.ResetSweep = lambda: None
        ctx.SnapshotRoute = lambda record, pack: None
        ctx.Quarantine = lambda reason: rec.events.append("quarantine")
        return ctx

    def run_adopt(self, ctx, rec):
        policy = dict(policy_functions())
        namespace = dict(
            HCInfectedPolicy=NS(**policy),
            HCInfectedStore=NS(ValidPosition=lambda v: True),
            HCInfectedClock=NS(UtcSeconds=lambda: 10),
            HCHordeStimulus=NS(ChooseClue=lambda actor, now, hearing: self.clue(), PreferClue=lambda a, b, now: a is not None and b is None),
            HCHordeRecovery=NS(Capture=lambda candidates, record: rec.events.append("capture")),
            HCHordeRecord=lambda: NS(RecoveryConflicted=False),
            HCNativeInfectedPack=pack_factory(rec), HCHordeSweep=lambda: NS(),
            DayZInfectedConstants=NS(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4),
            vector=NS(DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))))
        return module_call("protected void TryAdopt(", ctx, 100, **namespace)

    def test_ce_adoption_requested_but_unadmitted_does_not_reserve_save_capture_or_transfer(self):
        rec = Recorder(); ctx = self.adopt_context(rec, {})
        self.run_adopt(ctx, rec)
        self.assertEqual([], rec.events)
        self.assertEqual(0, len(ctx.m_State.Groups))
        self.assertEqual(0, ctx.m_State.Reserved)
        self.assertEqual(0, len(ctx.m_Sweeps))
        self.assertFalse(ctx.m_Dirty)
        self.assertTrue(all(not a.EverAssigned and a.GroupId == 0 for a in ctx.m_Actors))

    def test_ce_adoption_positive_control_reserves_and_saves_when_admitted(self):
        rec = Recorder(); ctx = self.adopt_context(rec, {"CEAdoption": True})
        self.run_adopt(ctx, rec)
        self.assertIn("save_prepare", rec.events)
        self.assertEqual(1, len(ctx.m_State.Groups))
        self.assertTrue(all(a.EverAssigned for a in ctx.m_Actors))

    def test_native_pack_routes_unadmitted_never_start_a_pack_even_with_ce_adoption_admitted(self):
        rec = Recorder(); ctx = self.adopt_context(rec, {"CEAdoption": True})
        self.run_adopt(ctx, rec)
        self.assertNotIn("pack_created", rec.events)
        self.assertNotIn("pack_start", rec.events)

    def test_native_pack_routes_positive_control_starts_a_pack_when_admitted(self):
        rec = Recorder(); ctx = self.adopt_context(rec, {"CEAdoption": True, "NativePackRoutes": True})
        self.run_adopt(ctx, rec)
        self.assertIn("pack_start", rec.events)

    # -- investigation --
    def investigate_context(self, rec, admitted):
        actor = self.candidate(0)
        actor.Visual = self.clue(provenance=2)
        ctx = NS(m_Chains=True, m_Config=requested_config(MaxInvestigators=2), m_Admission=admission(**admitted),
            m_Now=10, m_RoutesRemaining=1, m_Investigators=Array())
        return ctx, actor

    def run_investigate(self, ctx, actor, rec):
        return module_call("protected void TryInvestigate(", ctx, actor,
            HCInfectedPolicy=NS(**policy_functions()), HCNativeInfectedPack=pack_factory(rec),
            DayZInfectedConstants=NS(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4), Math=NS(Min=min),
            **self.stimulus_namespace())

    def test_investigation_requested_but_unadmitted_routes_nothing(self):
        rec = Recorder(); ctx, actor = self.investigate_context(rec, {"NativePackRoutes": True})
        self.run_investigate(ctx, actor, rec)
        self.assertEqual([], rec.events)
        self.assertEqual(1, ctx.m_RoutesRemaining)
        self.assertEqual(0, actor.SearchAttempts)
        self.assertIsNone(actor.SearchPack)
        self.assertEqual(0, len(ctx.m_Investigators))

    def test_investigation_positive_control_starts_one_bounded_search(self):
        rec = Recorder(); ctx, actor = self.investigate_context(rec, {"Investigation": True})
        self.run_investigate(ctx, actor, rec)
        self.assertIn("pack_start", rec.events)
        self.assertEqual(1, actor.SearchAttempts)

    def stimulus_namespace(self):
        real = stimulus_api()
        return dict(HCHordeStimulus=NS(SelectClue=lambda v, h, admit, now, reason:
            real.SelectClue(v, h, admit, now, NS(value=0))))

    def heard_investigation(self, rec, chains=True, supplementary=True, external=True):
        ctx, actor = self.investigate_context(rec, {"Investigation": True, "SupplementaryChains": supplementary})
        ctx.m_Chains = chains
        actor.Visual = None
        actor.Heard = self.clue(provenance=1)
        actor.HeardExternally = external
        return ctx, actor

    def test_investigation_uses_the_shared_selector_with_the_single_heard_gate(self):
        text = (SOURCE / "HCInfectedModule.c").read_text()
        _, body = _body(_mask(text)[0], "protected void TryInvestigate(")
        self.assertIn("HCHordeStimulus.SelectClue(actor.Visual, actor.Heard, admitHeard, m_Now, stimulusReason)", text)
        self.assertIn("bool admitHeard = HeardAdmitted() && actor.HeardExternally;", text)
        self.assertNotIn("actor.Heard.Observed", body)
        self.assertNotIn("Provenance ==", body)
        self.assertIn("return m_Chains && m_Admission.SupplementaryChains;", text)
        # The pair is spelled once in the helper; the only other uses are the
        # NativeVoice emission gate, the relay-work gate and the admitted
        # ecology migration submit (which passes the flag through), not heard-clue sites.
        self.assertEqual(4, text.count("m_Admission.SupplementaryChains"))
        self.assertEqual(1, text.count("m_Admission.Investigation, m_Admission.SupplementaryChains)"))
        for signature in ("protected void SampleMembership(", "protected void TryAdopt("):
            _, site = _body(_mask(text)[0], signature)
            self.assertIn("HeardAdmitted()", site)
            self.assertNotIn("SupplementaryChains", site)

    def test_investigation_refuses_heard_clues_unless_chains_are_admitted_and_external(self):
        for label, kwargs in (("unadmitted", dict(supplementary=False)), ("chains_off", dict(chains=False)),
                              ("self_voice", dict(external=False))):
            with self.subTest(label):
                rec = Recorder(); ctx, actor = self.heard_investigation(rec, **kwargs)
                self.run_investigate(ctx, actor, rec)
                self.assertEqual([], rec.events)
                self.assertEqual(1, ctx.m_RoutesRemaining)
                self.assertEqual(0, actor.SearchAttempts)

    def test_investigation_accepts_heard_clue_when_hypothetically_qualified(self):
        rec = Recorder(); ctx, actor = self.heard_investigation(rec)
        self.run_investigate(ctx, actor, rec)
        self.assertIn("pack_start", rec.events)
        self.assertEqual(1, actor.SearchAttempts)
        self.assertEqual(0, ctx.m_RoutesRemaining)

    def test_investigation_live_visual_still_investigates_without_chains(self):
        rec = Recorder(); ctx, actor = self.investigate_context(rec, {"Investigation": True})
        ctx.m_Chains = False
        self.run_investigate(ctx, actor, rec)
        self.assertIn("pack_start", rec.events)

    def test_investigation_visual_is_unchanged_when_heard_is_refused(self):
        rec = Recorder(); ctx, actor = self.heard_investigation(rec, supplementary=False)
        actor.Visual = self.clue(provenance=2)
        self.run_investigate(ctx, actor, rec)
        self.assertIn("pack_start", rec.events)

    def test_investigation_visual_sampling_is_gated_by_admission(self):
        for admitted, expected in ((False, []), (True, ["sample"])):
            with self.subTest(admitted=admitted):
                rec = Recorder()
                actor = self.candidate(0)
                actor.NextVisualSample = 0
                actor.Clue = None; actor.Visual = None
                actor.RefreshProfile = lambda: None
                ctx = NS(m_Now=10, m_Actors=Array([actor]), m_ObservationsRemaining=1,
                    m_Config=requested_config(), m_Admission=admission(Investigation=admitted))
                ctx.TryInvestigate = lambda a: None
                ctx.SampleMembership = lambda a: None
                module_call("protected void SampleActor(", ctx, actor,
                    HCInfectedObservation=NS(VisualSamplingAvailable=lambda: True,
                        SampleVisual=lambda a, now: rec.events.append("sample")), Math=NS(Max=max))
                self.assertEqual(expected, rec.events)

    # -- supplementary chains --
    def test_supplementary_chains_requested_but_unadmitted_emit_no_relay(self):
        for admitted, expected in ((False, []), (True, ["emit"])):
            with self.subTest(admitted=admitted):
                rec = Recorder()
                actor = NS(LastEventId=-1, LastEventAt=-1, NextVoice=0, ClueLifetime=30)
                entity = NS(IsAlive=lambda: True, HCRegisterActive=lambda: None, GetPosition=lambda: (1.0, 0.0, 1.0))
                sound = NS(m_iID=7, m_NoiseParams=object())
                ctx = NS(m_Healthy=True, m_Chains=True, m_VoiceAttempts=0, m_WorkCap=8, m_LastUtc=0,
                    m_StartedUtc=0, m_Now=0, m_Voices=Array(), m_Actors=Array([actor]),
                    m_Config=requested_config(MaxVoicePerTick=8, MaxVoiceQueue=16, VoiceCooldownSeconds=10),
                    m_Admission=admission(SupplementaryChains=admitted),
                    m_AlertChain=NS(NativeEmission=lambda *a: rec.events.append("emit")))
                ctx.FindActor = lambda e: actor
                ctx.Quarantine = lambda reason: rec.events.append("quarantine")
                actor.InfectedEntity = entity
                module_call("void NativeVoice(", ctx, entity, sound,
                    GetGame=lambda: NS(IsServer=lambda: True),
                    HCInfectedClock=NS(UtcSeconds=lambda: 5),
                    HCInfectedPolicy=NS(AdmitVoice=lambda *a: True, Attenuate=lambda s: s),
                    HCInfectedStore=NS(ValidPosition=lambda v: True),
                    HCInfectedClue=lambda: NS(Strength=1), HCInfectedVoice=lambda: NS())
                self.assertEqual(expected, rec.events)

    def test_hearing_clues_ignored_by_membership_sampling_unless_chains_admitted(self):
        for admitted in (False, True):
            with self.subTest(admitted=admitted):
                seen = []
                entity = NS(IsAlive=lambda: True, GetPosition=lambda: (1.0, 0.0, 1.0), GetMindStateSynced=lambda: 0)
                actor = NS(GroupId=1, InfectedEntity=entity, ConfirmedDead=False)
                record = NS(State=0, HasRoute=False)
                sweep = NS(Accounted=0, Living=0, Sum=(0.0, 0.0, 0.0), Stimulus=None, Engaged=False, Ambiguous=False, ConfirmedDead=0)
                ctx = NS(m_Hordes=True, m_Sweeps=Array([sweep]), m_State=NS(Groups=Array([record])), m_Packs=Array([None]),
                    m_Chains=True, m_Config=requested_config(), m_Admission=admission(SupplementaryChains=admitted), m_Now=1)
                module_call("protected void SampleMembership(", ctx, actor,
                    HCInfectedStore=NS(ValidPosition=lambda v: True),
                    HCHordeStimulus=NS(ChooseClue=lambda a, now, hearing: seen.append(hearing), PreferClue=lambda a, b, now: False),
                    DayZInfectedConstants=NS(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4),
                    vector=NS(Zero=(0.0, 0.0, 0.0)))
                self.assertEqual([admitted], seen)

    # -- tick-level gates: recovery, chains relay, stimulus reserve --
    def tick_context(self, rec, **admitted):
        actor = self.candidate(0)
        actor.Clue = None; actor.Visual = None
        ctx = NS(m_Healthy=True, m_Hordes=True, m_Chains=True, m_RegistrationRound=0, m_LastUtc=0, m_StartedUtc=0,
            m_Now=0, m_VoiceAttempts=0, m_RegistrationAttempts=0, m_ObservationsRemaining=0, m_RoutesRemaining=0,
            m_Investigators=Array(), m_Packs=Array(), m_Voices=Array(), m_Actors=Array([actor]), m_Cursor=0,
            m_NextAdopt=10 ** 6, m_NextSave=10 ** 6, m_Dirty=False, m_WorkCap=32, m_RecoveryCursor=0,
            m_State=NS(Groups=Array()), m_Admission=admission(**admitted),
            m_Config=requested_config(SaveIntervalSeconds=60, MaxVoicePerTick=8))
        ctx.m_AlertChain = NS(ProcessPending=lambda actors, now, work: rec.events.append("relay") or 0)
        ctx.FinishSweep = lambda nowUtc: None
        ctx.SampleActor = lambda a: None
        ctx.Quarantine = lambda reason: rec.events.append("quarantine")
        ctx.TryAdopt = lambda nowUtc: rec.events.append("adopt")
        ctx.FindActor = lambda e: None
        return ctx

    def run_tick(self, ctx, rec):
        return module_call("override void OnTick(", ctx, 1.0,
            GetGame=lambda: NS(IsServer=lambda: True), HCInfectedClock=NS(UtcSeconds=lambda: 100),
            HCNativeInfectedPack=NS(RetryPendingReleases=lambda: None), HCInfectedRoomCatalog=NS(BeginTick=lambda: None),
            HCHordeRecovery=NS(Reconcile=lambda actor, state, actors, flag, now: rec.events.append("recover") or False),
            HCInfectedPolicy=NS(NextAdoptionCursor=lambda i, n: (i + 1) % n),
            HCInfectedStore=NS(Save=lambda *a: True))

    def test_member_recovery_requested_but_unadmitted_performs_no_reconciliation(self):
        for admitted, expected in ((False, 0), (True, 1)):
            with self.subTest(admitted=admitted):
                rec = Recorder(); ctx = self.tick_context(rec, MemberRecovery=admitted)
                self.run_tick(ctx, rec)
                self.assertEqual(expected, rec.events.count("recover"), rec.events)

    def test_chain_relay_processing_requested_but_unadmitted_performs_no_relay(self):
        for admitted, expected in ((False, 0), (True, 1)):
            with self.subTest(admitted=admitted):
                rec = Recorder(); ctx = self.tick_context(rec, SupplementaryChains=admitted)
                self.run_tick(ctx, rec)
                self.assertEqual(expected, rec.events.count("relay"), rec.events)

    def test_adoption_tick_still_defers_to_admission_inside_try_adopt(self):
        rec = Recorder(); ctx = self.tick_context(rec)
        ctx.m_NextAdopt = 0
        self.run_tick(ctx, rec)
        self.assertEqual(["adopt"], [e for e in rec.events if e == "adopt"])

    def test_stimulus_routes_requested_but_unadmitted_never_reach_retarget(self):
        for admitted, expected in ((False, 0), (True, 1)):
            with self.subTest(admitted=admitted):
                rec = Recorder()
                ctx = NS(m_Sweeps=Array(), m_State=NS(Groups=Array()), m_Packs=Array(), m_Admission=admission(HordeStimulusRoutes=admitted),
                    m_Config=requested_config(), m_Dirty=False, m_Now=1, m_Cursor=0)
                ctx.RetargetCohorts = lambda: rec.events.append("retarget_cohorts")
                ctx.ResetSweep = lambda: None
                module_call("protected void FinishSweep(", ctx, 100)
                self.assertEqual(expected, rec.events.count("retarget_cohorts"), rec.events)

    def test_retarget_reserve_is_only_claimed_for_admitted_stimulus_routes(self):
        tick = (SOURCE / "HCInfectedModule.c").read_text().split("override void OnTick", 1)[1]
        self.assertIn("if (m_Hordes && m_Admission.HordeStimulusRoutes)", tick)
        self.assertIn("m_Hordes && m_Admission.MemberRecovery", tick)
        self.assertIn("m_Chains && m_Admission.SupplementaryChains && work > 2", tick)


# ---- round 2: startup budget, dependency and dormant-journal fail-closed ----
import copy
from pathlib import Path
from unittest.mock import patch

NO_ADMISSION = (False,) * len(PATHS)


def hypothetical(*paths):
    """Explicit synthetic qualification flags in PATHS order."""
    return tuple(path in paths for path in PATHS)


def committed_record(record_id=1, created=1):
    return NS(Id=record_id, State=0, CreatedUtc=created, LastSignalUtc=90, Living=3, Reserved=3,
        AdoptionStage=2, HasRoute=True, RecoveryConflicted=False, Anchor=(1.0, 0.0, 1.0),
        PreviousAnchor=(1.0, 0.0, 1.0), RoutePurpose=1, RouteResult=1, RoutePlanned=2,
        RouteCompleted=1, RouteEnd=(2.0, 0.0, 2.0), MemberIds=Array())


def prepared_record(record_id=2, created=1):
    return NS(Id=record_id, State=6, CreatedUtc=created, LastSignalUtc=90, Living=3, Reserved=3,
        AdoptionStage=1, HasRoute=False, RecoveryConflicted=False, Anchor=(5.0, 0.0, 5.0),
        PreviousAnchor=(5.0, 0.0, 5.0), RoutePurpose=0, RouteResult=0, RoutePlanned=0,
        RouteCompleted=0, RouteEnd=(0.0, 0.0, 0.0), MemberIds=Array())


class SweepFixture:
    def __init__(self):
        self.Living = 0; self.ConfirmedDead = 0; self.Accounted = 0; self.Ambiguous = False
        self.Stimulus = None; self.Sum = (0.0, 0.0, 0.0); self.Clue = False; self.Engaged = False
    def Clear(self):
        self.__init__()


def authored_load_wrapper(slot_loader, policies):
    """Authored Load body (translated) composed of the given explicit slot-loader double
    and the actual translated ApplyRestart body; nothing of the restart is re-implemented here."""
    restart = translate("HCInfectedState.c", "static void ApplyRestart(", (), HCInfectedPolicy=policies)
    return translate("HCInfectedState.c", "static bool Load(", (), LoadVerbatim=slot_loader,
        ApplyRestart=lambda snapshot: restart(None, snapshot))


class StartedModule:
    """Executes the authored OnStart/OnTick/OnStop on explicit synthetic collaborators."""

    def __init__(self, work=32, flags=None, hordes=True, journal=(), **overrides):
        self.events = []
        self.saves = []
        self.store_calls = []
        self.released = []
        self.clock = [10000]
        self.journal = Array(journal)
        self.work = work
        self.hordes = hordes
        self.policies = NS(**policy_functions())
        Admission, _ = admission_functions()
        if flags is not None:
            Admission.Evaluate = staticmethod(lambda config, flags=flags: Admission.Resolve(config, *flags))
        self.config = requested_config(SchemaVersion=1, MaxTracked=24, MaxVoiceQueue=16,
            MaxVoicePerTick=8, VoiceCooldownSeconds=10, SaveIntervalSeconds=60, MaxInvestigators=2,
            CivilianVariants=Array(), MilitaryVariants=Array(), **overrides)
        self.profiles = NS(ValidateMap=lambda *x: True, NativeBuildSupported=lambda x: x == "1.30.164289",
            ContactGuardQualified=lambda: False, ContactGuardAdmitted=lambda: False, LogUnsupportedSubstitutions=lambda config: None)
        is_valid = translate("HCInfectedState.c", "bool IsValid(", (), fields=tuple(vars(self.config)),
            HCInfectedProfiles=self.profiles)
        self.config.IsValid = lambda: is_valid(self.config)
        self.ctx = NS(Instance=None, m_State=None, m_Healthy=False, m_Dirty=False, m_Admission=admission(),
            m_Sweeps=Array(), m_Packs=Array(), m_Actors=Array(), m_Voices=Array(), m_Investigators=Array(),
            m_RegistrationRound=0, m_Cursor=0, m_RecoveryCursor=0, m_AdoptionCursor=0, m_RetargetCursor=0,
            m_Now=0, m_AlertChain=NS(ProcessPending=lambda *a: 0))
        self.ctx.Quarantine = lambda reason: self.events.append(("quarantine", reason))
        self.ctx.IsEnabled = lambda settings: settings.EnableInfected
        self.Admission = Admission
        self.settings = NS(EnableInfected=True, EnableHordes=hordes, EnableAlertChains=True,
            MaxTickWorkItems=work, MaxActiveHordes=2, MaxActiveHordeMembers=24,
            InfectedBindRadius=30, MaxBindQueriesPerTick=2)
        def fresh():
            return NS(Groups=Array(), Reserved=0)

        def slot_loader(snapshot, *args):
            # Explicit slot-loader double: committed bytes as validated records, no restart applied.
            self.slot_loads.append("slot")
            snapshot.Groups.Clear()
            snapshot.Groups.extend(copy.deepcopy(list(self.journal)))
            snapshot.Reserved = sum(g.Reserved for g in self.journal)
            return True
        self.slot_loads = []
        authored_load = authored_load_wrapper(slot_loader, self.policies)

        def verbatim(*args):
            self.store_calls.append("verbatim")
            self.ctx.m_State = fresh()
            return slot_loader(self.ctx.m_State)

        def load(*args):
            self.store_calls.append("load")
            self.ctx.m_State = fresh()
            return authored_load(None, self.ctx.m_State, *args[1:])

        def save(snapshot_value, member_cap, group_cap):
            self.saves.append(copy.deepcopy(vars(snapshot_value)))
            return True
        self.store = NS(ROOT="synthetic", DIRECTORY="synthetic/infected", Load=load, LoadVerbatim=verbatim,
            Save=save)

    def namespace(self, **extra):
        game = NS(IsServer=lambda: True, GetVersion=lambda: "1.30.164289", GetWorldName=lambda: "chernarusplus",
            GetWorld=lambda: NS(GetAIWorld=lambda: object()), ConfigIsExisting=lambda x: True)
        namespace = dict(GetGame=lambda: game, HCInfectedConfig=lambda: self.config, HCInfectedStore=self.store,
            MakeDirectory=lambda *args: None, FileExist=lambda *args: False,
            JsonFileLoader=NS(SaveFile=lambda *args: True), HCInfectedAdmission=self.Admission,
            HCInfectedProfiles=self.profiles, HCInfectedPolicy=self.policies,
            HCInfectedClock=NS(UtcSeconds=lambda: self.clock[0]), HCHordeSweep=SweepFixture,
            HCHordeRecovery=NS(Reconcile=lambda *a: False), HCNativeInfectedPack=NS(RetryPendingReleases=lambda: None),
            HCInfectedRoomCatalog=NS(Clear=lambda: None, EnsureProductionLoaded=lambda: False, ConfigureBinding=lambda radius, queries: True, BeginTick=lambda: None), HCAlertChain=lambda: NS(ProcessPending=lambda *a: 0),
            DayZInfectedConstants=NS(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4),
            vector=NS(Zero=(0.0, 0.0, 0.0), DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))),
            Print=self.events.append)
        namespace.update(extra)
        return namespace

    def module_function(self, signature):
        original = Path.read_text

        def read(path, *args, **kwargs):
            source = original(path, *args, **kwargs)
            if path.name == "HCInfectedModule.c":
                source = re.sub(r"#ifdef DIAG_DEVELOPER.*?#endif", "", source, flags=re.S)
                source = source.replace("string content, error;", 'string content = ""; string error = "";')
                source = source.replace("GetGame().GetVersion(runtimeBuild);", "runtimeBuild = GetGame().GetVersion();")
                source = re.sub(r"(?<![.\w])Instance\b", "self.Instance", source)
                source = source.replace("Instance = this;", "Instance = self;").replace("== this", "== self")
            return source
        with patch.object(Path, "read_text", read):
            return translate("HCInfectedModule.c", signature, MODULE_METHODS + ("IsEnabled",), **self.namespace())

    def bind_real_methods(self):
        for signature in ("protected void FinishSweep(", "protected void ReleasePacks(", "protected void ResetSweep(",
                          "protected void TryAdopt(", "protected void SnapshotRoute(", "protected void SampleMembership(",
                          "protected bool HeardAdmitted("):
            name = signature.split()[-1].rstrip("(")
            function = self.module_function(signature)
            setattr(self.ctx, name, lambda *args, function=function: function(self.ctx, *args))
        self.ctx.SampleActor = lambda actor: None
        self.ctx.FindActor = lambda entity: None

    def start(self):
        self.module_function("override void OnStart(")(self.ctx, self.settings)
        self.bind_real_methods()
        return self

    def tick(self, utc):
        self.clock[0] = utc
        self.module_function("override void OnTick(")(self.ctx, 1.0)

    def stop(self):
        self.module_function("override void OnStop(")(self.ctx)

    @property
    def quarantines(self):
        return [e for e in self.events if isinstance(e, tuple)]

    @property
    def admission_logs(self):
        return [e for e in self.events if isinstance(e, str) and "capability admission (" in e]


class StartupBudgetAndDependencyTests(unittest.TestCase):
    def test_closed_capabilities_do_not_quarantine_native_only_startup_at_valid_core_budget(self):
        for work in (4, 5, 6, 7):
            with self.subTest(work=work):
                started = StartedModule(work=work).start()
                self.assertTrue(started.ctx.m_Healthy, started.events)
                self.assertEqual([], started.quarantines)
                self.assertEqual(1, len(started.admission_logs))
                self.assertTrue(all(not getattr(started.ctx.m_Admission, path) for path in PATHS))

    def test_generic_core_minimum_of_four_is_kept(self):
        started = StartedModule(work=3).start()
        self.assertFalse(started.ctx.m_Healthy)
        self.assertEqual("invalid limits", started.quarantines[0][1])

    def test_startup_positive_control_default_budget_reaches_healthy(self):
        started = StartedModule().start()
        self.assertTrue(started.ctx.m_Healthy, started.events)
        self.assertEqual(1, len(started.admission_logs))
        self.assertTrue(all(not getattr(started.ctx.m_Admission, path) for path in PATHS))

    def test_each_admitted_horde_lifecycle_keeps_the_eight_item_prerequisite(self):
        cases = (hypothetical("CEAdoption"), hypothetical("MemberRecovery"),
                 hypothetical("NativePackRoutes", "HordeStimulusRoutes"))
        for flags in cases:
            for work in (4, 7):
                with self.subTest(flags=flags, work=work):
                    started = StartedModule(work=work, flags=flags).start()
                    self.assertFalse(started.ctx.m_Healthy)
                    self.assertIn("at least eight", started.quarantines[0][1])

    def test_admitted_native_routes_and_investigation_keep_the_eight_item_prerequisite(self):
        for flags in (hypothetical("NativePackRoutes"), hypothetical("Investigation")):
            with self.subTest(flags=flags):
                started = StartedModule(work=7, flags=flags, hordes=False).start()
                self.assertFalse(started.ctx.m_Healthy)
                self.assertIn("at least eight", started.quarantines[0][1])

    def test_admitted_horde_work_without_the_hordes_setting_needs_no_extra_budget(self):
        started = StartedModule(work=4, flags=hypothetical("MemberRecovery"), hordes=False).start()
        self.assertTrue(started.ctx.m_Healthy, started.events)

    def test_existing_adoption_and_stimulus_budgets_still_apply_at_eight(self):
        started = StartedModule(work=8, flags=hypothetical("CEAdoption")).start()
        self.assertIn("at least 9", started.quarantines[0][1])
        started = StartedModule(work=8, flags=hypothetical("NativePackRoutes", "HordeStimulusRoutes")).start()
        self.assertIn("at least 24", started.quarantines[0][1])

    def test_explicit_pack_disable_does_not_quarantine_unqualified_stimulus_preference(self):
        started = StartedModule(EnableNativePackRoutes=False).start()
        self.assertTrue(started.ctx.m_Healthy, started.events)
        self.assertEqual([], started.quarantines)
        self.assertIs(False, started.ctx.m_Admission.NativePackRoutes)
        self.assertIs(False, started.ctx.m_Admission.HordeStimulusRoutes)
        self.assertEqual("disabled_by_preference", started.ctx.m_Admission.NativePackRoutesReason)
        self.assertEqual("horde_stimulus_routes_unqualified", started.ctx.m_Admission.HordeStimulusRoutesReason)

    def test_explicit_pack_disable_with_hypothetical_stimulus_qualification_is_admission_not_invalid_config(self):
        started = StartedModule(EnableNativePackRoutes=False,
            flags=hypothetical("NativePackRoutes", "HordeStimulusRoutes")).start()
        self.assertTrue(started.ctx.m_Healthy, started.events)
        self.assertEqual([], started.quarantines)
        self.assertIs(False, started.ctx.m_Admission.HordeStimulusRoutes)
        self.assertEqual("horde_stimulus_routes_requires_pack_routes",
                         started.ctx.m_Admission.HordeStimulusRoutesReason)
        # Explicit false stays a hard disable and is never rewritten.
        self.assertIs(False, started.config.EnableNativePackRoutes)
        self.assertIs(True, started.config.EnableHordeStimulusRoutes)

    def test_config_validity_no_longer_encodes_a_capability_dependency(self):
        text = (SOURCE / "HCInfectedState.c").read_text()
        valid = text.split("bool IsValid()", 1)[1].split("\n    }", 1)[0]
        self.assertNotIn("EnableHordeStimulusRoutes", valid)
        self.assertNotIn("EnableNativePackRoutes", valid)
        started = StartedModule(EnableNativePackRoutes=False)
        self.assertTrue(started.config.IsValid())


class DormantJournalTests(unittest.TestCase):
    """A journal with no admitted lifecycle is evidence to keep, not state to advance."""

    VARIANTS = (("requested_unqualified", {}), ("recovery_explicitly_disabled", {"EnableMemberRecovery": False}))

    def journal(self):
        return (committed_record(1), prepared_record(2))

    def test_startup_tick_and_shutdown_leave_dormant_journals_byte_for_byte_unchanged(self):
        for name, overrides in self.VARIANTS:
            with self.subTest(variant=name):
                journal = self.journal()
                before = copy.deepcopy([vars(record) for record in journal])
                started = StartedModule(journal=journal, **overrides).start()
                self.assertTrue(started.ctx.m_Healthy, started.events)
                self.assertEqual(["verbatim"], started.store_calls)
                self.assertEqual(before, [vars(record) for record in started.ctx.m_State.Groups])
                self.assertIs(False, started.ctx.m_Dirty)
                for utc in (20000, 20001, 20002, 20003):
                    started.tick(utc)
                self.assertTrue(started.ctx.m_Healthy, started.events)
                self.assertEqual(before, [vars(record) for record in started.ctx.m_State.Groups])
                self.assertIs(False, started.ctx.m_Dirty)
                self.assertEqual([], started.saves)
                started.stop()
                self.assertEqual(before, [vars(record) for record in started.ctx.m_State.Groups])
                self.assertEqual([], started.saves)

    def test_unadmitted_recovery_does_not_retire_and_save_a_previously_pending_journal(self):
        probe = UnqualifiedPathsPerformNoMutation()
        rec = Recorder()
        ctx = probe.tick_context(rec)
        record = prepared_record(1)
        record.AdoptionStage = 2
        ctx.m_State = NS(SchemaVersion=2, Build="1.30.164289", WorldName="chernarusplus",
            Epoch=1, Generation=7, SavedUtc=100, Reserved=3, Groups=Array([record]))
        ctx.m_Packs = Array([None]); ctx.m_NextSave = 0; ctx.m_MemberCap = 24; ctx.m_GroupCap = 2
        module_call("override void OnTick(", ctx, 1.0, GetGame=lambda: NS(IsServer=lambda: True),
            HCInfectedClock=NS(UtcSeconds=lambda: 4000), HCNativeInfectedPack=NS(RetryPendingReleases=lambda: None),
            HCInfectedRoomCatalog=NS(BeginTick=lambda: None),
            HCInfectedStore=NS(Save=lambda *a: rec.events.append("save") or True))
        self.assertEqual(6, record.State)
        self.assertEqual([], rec.events)
        self.assertIs(False, ctx.m_Dirty)

    def test_finish_sweep_does_not_advance_a_dormant_journal(self):
        for admitted in ({}, {"HordeStimulusRoutes": True}):
            with self.subTest(admitted=admitted):
                record = prepared_record(1)
                before = copy.deepcopy(vars(record))
                ctx = NS(m_Sweeps=Array([SweepFixture()]), m_State=NS(Groups=Array([record])), m_Packs=Array([None]),
                    m_Admission=admission(**admitted), m_Config=requested_config(), m_Dirty=False, m_Now=1, m_Cursor=0)
                ctx.RetargetCohorts = lambda: None
                ctx.ResetSweep = lambda: None
                ctx.SnapshotRoute = lambda *a: None
                module_call("protected void FinishSweep(", ctx, 20000, HCInfectedPolicy=NS(**policy_functions()),
                    Print=lambda *a: None, vector=NS(DistanceSq=lambda a, b: 0))
                self.assertEqual(before, vars(record))
                self.assertIs(False, ctx.m_Dirty)

    def test_shutdown_still_releases_owned_packs_without_touching_dormant_routes(self):
        started = StartedModule(journal=self.journal()).start()
        before = copy.deepcopy([vars(record) for record in started.ctx.m_State.Groups])
        pack = NS(Release=lambda: started.released.append("pack"))
        actor = NS(SearchPack=pack)
        started.ctx.m_Investigators = Array([actor]); started.ctx.m_Actors = Array([actor])
        started.stop()
        self.assertEqual(["pack"], started.released)
        self.assertIsNone(actor.SearchPack)
        self.assertEqual(before, [vars(record) for record in started.ctx.m_State.Groups])
        self.assertEqual([], started.saves)

    def test_admitted_recovery_keeps_the_existing_restart_retire_and_save_lifecycle(self):
        journal = (prepared_record(1),)
        started = StartedModule(journal=journal, flags=hypothetical("MemberRecovery")).start()
        self.assertEqual(["load"], started.store_calls)
        self.assertIs(True, started.ctx.m_Dirty)
        for utc in (20000, 20001, 20002):
            started.tick(utc)
        self.assertEqual(5, started.ctx.m_State.Groups[0].State)
        self.assertGreaterEqual(len(started.saves), 1)

    def test_admitted_adoption_alone_never_retires_a_state_six_journal(self):
        journal = (prepared_record(1),)
        started = StartedModule(journal=journal, flags=hypothetical("CEAdoption")).start()
        self.assertEqual(["load"], started.store_calls)
        for utc in (20000, 20001, 20002):
            started.tick(utc)
        self.assertEqual(6, started.ctx.m_State.Groups[0].State)

    def test_restart_semantics_are_a_separate_authored_step_from_verbatim_loading(self):
        state = (SOURCE / "HCInfectedState.c").read_text()
        self.assertIn("static bool LoadVerbatim(", state)
        self.assertIn("static void ApplyRestart(", state)
        load = state.split("static bool Load(", 1)[1].split("static bool Save(", 1)[0]
        self.assertIn("LoadVerbatim(", load)
        self.assertIn("ApplyRestart(", load)
        verbatim = state.split("static bool LoadVerbatim(", 1)[1].split("static void ApplyRestart(", 1)[0]
        self.assertNotIn("AfterRestart", verbatim)


class CommittedRecordRestartThroughAuthoredLoadTests(unittest.TestCase):
    """A previously committed active record must become unresolved by the real Load wrapper
    before any admitted consumer sees it (#19 #44). Slot loading is an explicit synthetic double;
    restart interpretation is the authored ApplyRestart body, not a fixture re-implementation."""

    def route_record(self, state, stage=2, created=9000):
        record = committed_record(1, created)
        record.State = state
        record.AdoptionStage = stage
        record.MemberIds = Array(["a", "b", "c"])
        return record

    def load(self, journal):
        loaded = []
        def slot_loader(snapshot, *args):
            loaded.append(args)
            snapshot.Groups.Clear()
            snapshot.Groups.extend(copy.deepcopy(list(journal)))
            snapshot.Reserved = sum(g.Reserved for g in journal)
            return True
        load = authored_load_wrapper(slot_loader, NS(**policy_functions()))
        snapshot = NS(Groups=Array(), Reserved=0)
        self.assertTrue(load(None, snapshot, "chernarusplus", 24, 2, 10000))
        self.assertEqual(1, len(loaded))
        return snapshot

    def test_committed_active_states_load_as_unresolved_with_interrupted_route_and_kept_reservation(self):
        for state in (0, 2, 3):
            with self.subTest(state=state):
                committed = self.route_record(state)
                self.assertTrue(committed.HasRoute)
                self.assertEqual(3, committed.Reserved)
                snapshot = self.load((committed,))
                record = snapshot.Groups[0]
                self.assertEqual(6, record.State)
                self.assertIs(False, record.HasRoute)
                self.assertEqual(5, record.RouteResult)
                self.assertEqual(2, record.AdoptionStage)
                self.assertEqual(["a", "b", "c"], list(record.MemberIds))
                self.assertEqual((3, 3), (record.Living, record.Reserved))
                self.assertEqual(3, snapshot.Reserved)
                self.assertEqual((2.0, 0.0, 2.0), record.RouteEnd)

    def test_retired_state_is_kept_and_stage_one_becomes_conflicted_by_the_same_wrapper(self):
        retired = self.route_record(5)
        pending = self.route_record(0, stage=1)
        snapshot = self.load((retired, pending))
        self.assertEqual(5, snapshot.Groups[0].State)
        self.assertEqual(6, snapshot.Groups[1].State)
        self.assertEqual(3, snapshot.Groups[1].AdoptionStage)
        self.assertIs(True, snapshot.Groups[1].RecoveryConflicted)

    def test_started_admitted_lifecycle_sees_unresolved_state_and_does_not_replay_before_expiry(self):
        for name, flags, expiry in (("adoption", hypothetical("CEAdoption"), None),
                                    ("recovery", hypothetical("MemberRecovery"), 12600)):
            for state in (0, 2, 3):
                with self.subTest(path=name, state=state):
                    journal = (self.route_record(state),)
                    started = StartedModule(journal=journal, flags=flags).start()
                    self.assertTrue(started.ctx.m_Healthy, started.events)
                    self.assertEqual(["load"], started.store_calls)
                    self.assertEqual(["slot"], started.slot_loads)
                    self.assertIs(True, started.ctx.m_Dirty)
                    record = started.ctx.m_State.Groups[0]
                    self.assertEqual((6, False, 5, 3), (record.State, record.HasRoute, record.RouteResult, record.Reserved))
                    self.assertEqual(3, started.ctx.m_State.Reserved)
                    for utc in (10001, 10060, 11000, 12599):
                        started.tick(utc)
                        record = started.ctx.m_State.Groups[0]
                        self.assertEqual((6, False, 5, 3, 3), (record.State, record.HasRoute, record.RouteResult,
                            record.Reserved, record.Living), (name, state, utc))
                        self.assertEqual(["a", "b", "c"], list(record.MemberIds))
                    self.assertEqual(3, started.ctx.m_State.Reserved)
                    for snapshot in started.saves:
                        self.assertTrue(all(g.State == 6 and not g.HasRoute for g in snapshot["Groups"]))
                    if expiry:
                        started.tick(expiry)
                        started.tick(expiry + 1)
                        self.assertEqual(5, started.ctx.m_State.Groups[0].State)
                        self.assertEqual(3, started.ctx.m_State.Groups[0].Reserved)
                    else:
                        started.tick(20000)
                        self.assertEqual(6, started.ctx.m_State.Groups[0].State)

    def test_admission_selects_verbatim_loading_when_neither_journal_lifecycle_is_admitted(self):
        for name, flags in (("none", hypothetical()),
                            ("pack_routes_only", hypothetical("NativePackRoutes")),
                            ("investigation_chains_stimulus", hypothetical("Investigation", "SupplementaryChains",
                                "HordeStimulusRoutes"))):
            with self.subTest(admitted=name):
                journal = (self.route_record(0), self.route_record(2))
                journal[1].Id = 2
                before = copy.deepcopy([vars(r) for r in journal])
                started = StartedModule(journal=journal, flags=flags).start()
                self.assertTrue(started.ctx.m_Healthy, started.events)
                self.assertEqual(["verbatim"], started.store_calls)
                self.assertEqual(["slot"], started.slot_loads)
                self.assertEqual(before, [vars(r) for r in started.ctx.m_State.Groups])
                self.assertIs(False, started.ctx.m_Dirty)
                self.assertEqual([], started.saves)

    def test_admission_selects_the_restart_wrapper_when_either_journal_lifecycle_is_admitted(self):
        for admitted in ("CEAdoption", "MemberRecovery"):
            with self.subTest(admitted=admitted):
                started = StartedModule(journal=(self.route_record(0),), flags=hypothetical(admitted)).start()
                self.assertEqual(["load"], started.store_calls)
                self.assertEqual(6, started.ctx.m_State.Groups[0].State)
                self.assertIs(True, started.ctx.m_Dirty)


class NativeIntegrationInterfaceTests(unittest.TestCase):
    def navigation(self):
        return (SOURCE / "HCInfectedNavigation.c").read_text()

    def test_release_attempt_limit_has_one_policy_source(self):
        policy = policy_functions()
        self.assertEqual(3, policy["MaxReleaseAttempts"]())
        limit = policy["MaxReleaseAttempts"]()
        for attempts in range(0, limit + 3):
            self.assertEqual(attempts < limit, policy["MayRetryRelease"](attempts, 100, 0), attempts)
        navigation = self.navigation()
        self.assertIn("m_ReleaseAttempts >= HCInfectedPolicy.MaxReleaseAttempts()", navigation)
        self.assertNotIn("m_ReleaseAttempts >= 3", navigation)

    def test_visual_sampling_availability_is_false_until_observed_evidence_exists(self):
        available = translate("HCInfectedNavigation.c", "static bool VisualSamplingAvailable(", ())
        self.assertIs(False, available(None))

    def test_visual_sampling_skips_call_and_observation_budget_while_unavailable(self):
        for available, expected, budget, next_sample in ((False, [], 1, 0), (True, ["sample"], 0, 12)):
            with self.subTest(available=available):
                rec = Recorder()
                actor = UnqualifiedPathsPerformNoMutation().candidate(0)
                actor.NextVisualSample = 0
                actor.Clue = None; actor.Visual = None
                actor.RefreshProfile = lambda: None
                ctx = NS(m_Now=10, m_Actors=Array([actor]), m_ObservationsRemaining=1,
                    m_Config=requested_config(), m_Admission=admission(Investigation=True))
                ctx.TryInvestigate = lambda a: None
                ctx.SampleMembership = lambda a: None
                module_call("protected void SampleActor(", ctx, actor,
                    HCInfectedObservation=NS(VisualSamplingAvailable=lambda available=available: available,
                        SampleVisual=lambda a, now: rec.events.append("sample")), Math=NS(Max=max))
                self.assertEqual(expected, rec.events)
                self.assertEqual(budget, ctx.m_ObservationsRemaining)
                self.assertEqual(next_sample, actor.NextVisualSample)

    def release_functions(self, pending, printed):
        fns = NS()
        statics = NS(s_ReportedPending=0, s_ReportedQuarantined=0)
        bound = ("QuarantinedReleaseCount", "ReleaseStatus")
        for signature, name in (("static int QuarantinedReleaseCount(", "QuarantinedReleaseCount"),
                                ("static string ReleaseStatus(", "ReleaseStatus"),
                                ("static void RetryPendingReleases(", "RetryPendingReleases")):
            function = translate("HCInfectedNavigation.c", signature, bound,
                statics=("s_ReportedPending", "s_ReportedQuarantined"), s_PendingRelease=pending,
                STATICS=statics, Print=printed.append)
            setattr(fns, name, lambda function=function: function(fns))
        return fns

    def test_release_quarantine_and_pending_count_are_logged_once_per_transition(self):
        packs = Array()
        printed = []
        fns = self.release_functions(packs, printed)
        for _ in range(3):
            fns.RetryPendingReleases()
        self.assertEqual([], printed, "nothing pending, nothing to report")
        stuck = NS(quarantined=False)
        stuck.Release = lambda: False
        stuck.IsReleaseQuarantined = lambda: stuck.quarantined
        packs.Insert(stuck)
        for _ in range(5):
            fns.RetryPendingReleases()
        self.assertEqual(1, len(printed), printed)
        self.assertIn("pending=1 quarantined=0 new_routes_blocked=yes", printed[0])
        stuck.quarantined = True
        for _ in range(5):
            fns.RetryPendingReleases()
        self.assertEqual(2, len(printed), printed)
        self.assertIn("pending=1 quarantined=1 new_routes_blocked=yes", printed[1])
        packs.Clear()
        for _ in range(5):
            fns.RetryPendingReleases()
        self.assertEqual(3, len(printed), printed)
        self.assertIn("pending=0 quarantined=0 new_routes_blocked=no", printed[2])
        self.assertEqual("pending=0 quarantined=0 new_routes_blocked=no", fns.ReleaseStatus())


if __name__ == "__main__":
    unittest.main()
