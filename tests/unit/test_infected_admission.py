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
else:
    from test_infected_contract import SOURCE, policy_functions

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


def translate(filename, signature, bound, fields=(), **namespace):
    """Return a Python callable for the authored body. `bound` lists instance
    methods of the same class that must resolve through `self`."""
    raw = (SOURCE / filename).read_text()
    text, strings = _mask(raw)
    params, body = _body(text, signature)
    body = re.sub(r"\bref\s+", "", body)
    body = re.sub(r"if (\([^\n]+\))\s*([^{};\n]+;)", r"if \1 {\2}", body)
    body = re.sub(r"\belse\s+(?!if\b)([^{};\s][^{};\n]*;)", r"else {\1}", body)
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
        token = token.replace("&&", " and ").replace("||", " or ").replace(" / ", " // ")
        token = re.sub(r"!(?!=)", "not ", token)
        for a, b in (("true", "True"), ("false", "False"), ("null", "None")):
            token = re.sub(r"\b" + a + r"\b", b, token)
        token = re.sub(r"(?<![.\w])(m_\w+)\b", r"self.\1", token)
        for name in fields:
            token = re.sub(r"(?<![.\w])" + name + r"\b", "self." + name, token)
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
    exec(compile(code, filename + ":" + signature, "exec"), scope)
    return scope["run"]


MODULE_METHODS = ("FindActor", "CanRecycleActor", "ResetSweep", "SampleActor", "SampleMembership",
    "FinishSweep", "SnapshotRoute", "RetargetCohorts", "SaveAdoptionBoundary", "TryAdopt",
    "TryInvestigate", "ReleasePacks", "Quarantine")


def module_call(signature, context, *args, **namespace):
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
        self.assertIn("if ((settings.EnableHordes || m_Admission.NativePackRoutes || m_Admission.Investigation) && m_WorkCap < 8)", self.start)
        self.assertIn("if (settings.EnableHordes && m_Admission.CEAdoption && !HCInfectedPolicy.AdoptionWorkReady(m_WorkCap))", self.start)
        self.assertIn("if (settings.EnableHordes && m_Admission.HordeStimulusRoutes && m_WorkCap < 24)", self.start)
        self.assertIn("if (m_Admission.NativePackRoutes || m_Admission.Investigation)", self.start)

    def test_variant_map_call_site_stays_simple_for_integration(self):
        lines = self.start.splitlines()
        at = next(i for i, line in enumerate(lines) if "variant preference enabled" in line)
        self.assertIn("if (m_Config.EnableVariantPolicies && !variantMaps)", lines[at - 2])
        self.assertEqual("        {", lines[at - 1])
        self.assertEqual("        }", lines[at + 1])


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
            DayZInfectedConstants=NS(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4), Math=NS(Min=min))

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
                    HCInfectedObservation=NS(SampleVisual=lambda a, now: rec.events.append("sample")),
                    Math=NS(Max=max))
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
            HCNativeInfectedPack=NS(RetryPendingReleases=lambda: None),
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


if __name__ == "__main__":
    unittest.main()
