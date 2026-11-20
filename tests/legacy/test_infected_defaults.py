"""Synthetic execution of authored defaults/registration; not an Enforce compiler."""
import re
from types import SimpleNamespace as NS
import unittest
if __package__:
    from tests.legacy.test_infected_contract import SOURCE, policy_functions
    from tests.legacy.build_identity_support import translate as build_identity
else:
    from tests.legacy.test_infected_contract import SOURCE, policy_functions
    from build_identity_support import translate as build_identity


class Array(list):
    def __bool__(self): return True  # Allocated Enforce arrays are non-null.
    def Count(self): return len(self)
    def Insert(self, value): self.append(value)


def authored(filename, signature, context, **namespace):
    text = (SOURCE / filename).read_text()
    start = text.index("{", text.index(signature)) + 1
    end, depth = start, 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    body = re.sub(r"//[^\n]*", "", text[start:end-1])
    body = re.sub(r"if (\([^\n]+\))\s*([^{};\n]+;)", r"if \1 {\2}", body)
    body = re.sub(r"for \(int (\w+) = 0; \1 < ([^;]+); \1\+\+\)", r"for \1 in range(\2)", body)
    body = re.sub(r"foreach \(int (\w+) : (\w+)\)", r"for \1 in \2", body)
    lines, indent = ["def run(self):"], 1
    for token in re.split(r"([{};])", body):
        token = token.strip()
        if not token or token == ";": continue
        if token == "{": indent += 1; continue
        if token == "}": indent -= 1; continue
        token = re.sub(r"\b(?:bool|int|float|string|ZombieBase|HCInfectedModule|HCInfectedActor)\s+", "", token)
        token = re.sub(r"\bnew (\w+)\b", r"\1()", token)
        token = token.replace("&&", " and ").replace("||", " or ")
        token = re.sub(r"!(?!=)", "not ", token)
        for a, b in (("true", "True"), ("false", "False"), ("null", "None"), ("this", "self")):
            token = re.sub(r"\b"+a+r"\b", b, token)
        token = re.sub(r"\b(m_\w+)\b", r"self.\1", token)
        for name in ("FindActor", "CanRecycleActor", "ResetSweep", "IsAlive", "HCRegisterActive"):
            token = re.sub(r"(?<![.\w])"+name+r"\(", "self."+name+"(", token)
        token = re.sub(r"\b(self\.m_\w+)\+\+", r"\1 += 1", token)
        if token.startswith("if ("): token = "if " + token[4:-1] + ":"
        elif token.startswith("for "): token += ":"
        elif token == "else": token += ":"
        lines.append("    " * indent + token)
    # Existing scalar-default fixtures use already-normalized tuning.
    scope = dict(HCNormalizeTunables=lambda: None, **vars(context), **namespace)
    exec(compile("\n".join(lines), filename, "exec"), scope)
    return scope["run"](context)


PREFERENCES = ("EnableCEAdoption EnableContactGuard EnableNativePackRoutes EnableInvestigation "
    "EnableSupplementaryChains EnableMemberRecovery EnableVariantPolicies EnableHordeStimulusRoutes").split()


class InfectedDefaultsTests(unittest.TestCase):
    def test_native_build_accepts_only_the_two_qualified_aliases(self):
        for build in ("1.30.164289", "1.30.164289.70", "", "1.30.164289.71", "1.30.164289.70.extra", "1.30.164290", "1.31.164289"):
            with self.subTest(build=build):
                self.assertEqual(build in ("1.30.164289", "1.30.164289.70"),
                    authored("HCInfectedProfiles.c", "static bool NativeBuildSupported(", NS(), build=build,
                             HCBuildIdentity=build_identity()))
        self.assertIn("HCInfectedProfiles.NativeBuildSupported(runtimeBuild)",
            (SOURCE / "HCInfectedModule.c").read_text())

    def test_init_and_storage_hooks_share_the_registration_budget(self):
        native = (SOURCE / "HCInfectedNative.c").read_text()
        for signature in ("override void AfterStoreLoad()", "override void EOnInit(IEntity other, int extra)"):
            hook = native.split(signature, 1)[1].split("\n    }", 1)[0]
            self.assertIn("HCRegisterActive();", hook)
            self.assertNotIn(".Track(this)", hook)

    def test_voice_callbacks_share_the_once_per_round_registration_helper(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        voice = module.split("void NativeVoice(", 1)[1].split("protected void ResetSweep", 1)[0]
        self.assertIn("entity.HCRegisterActive();", voice)
        self.assertNotIn("Track(entity);", voice)

    def test_registration_budget_is_shared_and_reset_by_the_core_tick(self):
        context = self.registry(cap=2)
        first, second, third = [NS(IsAlive=lambda: True) for _ in range(3)]
        self.assertTrue(self.track(first, context))
        self.assertTrue(self.track(first, context))
        self.assertFalse(self.track(second, context))
        self.assertFalse(self.track(third, context))
        self.assertEqual(2, context.m_RegistrationAttempts)
        self.assertEqual(1, len(context.m_Actors))
        context.m_RegistrationAttempts = 0
        self.assertTrue(self.track(second, context))
        tick = (SOURCE / "HCInfectedModule.c").read_text().split("override void OnTick", 1)[1]
        self.assertLess(tick.index('Quarantine("registration round exhausted")'), tick.index("m_RegistrationRound++;"))
        self.assertLess(tick.index("m_RegistrationRound++;"), tick.index("m_RegistrationAttempts = 0;"))

    def test_command_hook_returns_each_parent_result_and_registers_once(self):
        for consumed in (False, True):
            calls = []
            context = NS(HCRegisterActive=lambda: calls.append("register"))
            parent = NS(ModCommandHandlerBefore=lambda *args: calls.append(args) or consumed)
            result = authored("HCInfectedNative.c", "override bool ModCommandHandlerBefore(", context,
                pDt=0.1, pCurrentCommandID=3, pCurrentCommandFinished=False, **{"super": parent})
            self.assertEqual(consumed, result)
            self.assertEqual([(0.1, 3, False), "register"], calls)

    def test_preferences_on_without_flipping_diagnostic_or_evidence_flags(self):
        state = (SOURCE / "HCInfectedState.c").read_text().split("class HCInfectedClue", 1)[0]
        for name in PREFERENCES:
            with self.subTest(name=name): self.assertIn("bool "+name+" = true;", state)
        self.assertIn("bool RunPolicySelfTests = false;", state)
        self.assertIn("bool EnableDiagnostic = false;", (SOURCE / "HCInfectedRooms.c").read_text())
        self.assertFalse(policy_functions()["CanMaterialize"]())
        self.assertFalse(policy_functions()["CanAbstract"]())

    def test_contact_preference_does_not_claim_qualified_wall_hit_filter(self):
        self.assertFalse(authored("HCInfectedProfiles.c", "static bool ContactGuardQualified()", NS()))
        module = (SOURCE / "HCInfectedModule.c").read_text()
        self.assertIn("HCInfectedProfiles.ContactGuardAdmitted()", module)
        self.assertIn("contact guard pending native wall-hit qualification", module)

    def valid_map(self, configured, enabled):
        return authored("HCInfectedProfiles.c", "static bool ValidateMap(", NS(),
            configured=configured, enabled=enabled, HCInfectedPolicy=NS(**policy_functions()))

    def config(self):
        text = (SOURCE / "HCInfectedState.c").read_text().split("bool IsValid()", 1)[0]
        values = {}
        for kind, name, value in re.findall(r"\b(bool|int) (\w+) = (\w+);", text):
            values[name] = value == "true" if kind == "bool" else int(value)
        return NS(**values, CivilianVariants=Array(), MilitaryVariants=Array())

    def valid_config(self, config):
        return authored("HCInfectedState.c", "bool IsValid()", config,
            HCInfectedProfiles=NS(ValidateMap=self.valid_map))

    def test_empty_enabled_variant_template_is_valid_but_unqualified(self):
        config = self.config(); config.EnableVariantPolicies = True
        self.assertTrue(self.valid_config(config))
        self.assertFalse(self.valid_map(config.CivilianVariants, True))
        infected = NS(HCIndividualStance=lambda: 0, IsZombieMilitary=lambda: False)
        self.assertEqual(-1, authored("HCInfectedProfiles.c", "static int ConfiguredVariant(", NS(),
            infected=infected, config=config, ValidateMap=self.valid_map))
        self.assertIn("variant preference enabled; explicit stance maps missing",
            (SOURCE / "HCInfectedModule.c").read_text())

    def test_maps_remain_explicit_bounded_and_validated_even_when_disabled(self):
        for enabled in (False, True):
            config = self.config(); config.EnableVariantPolicies = enabled
            config.CivilianVariants = Array([0, 1, 2, 5])
            config.MilitaryVariants = Array([0, 1, 2, 5])
            self.assertTrue(self.valid_config(config))
            for invalid in (None, Array([0]), Array([0, 1, -1, 5]), Array([0]*5)):
                config.CivilianVariants = invalid
                self.assertFalse(self.valid_config(config))

    def registration(self, context, current, server=True):
        return authored("HCInfectedNative.c", "void HCRegisterActive()", context,
            HCInfectedModule=NS(Instance=current), GetGame=lambda: NS(IsServer=lambda: server))

    def actor(self):
        return NS(m_HCRegistrationOwner=None, m_HCRegistered=False,
            m_HCRegistrationRound=-1, IsAlive=lambda: True)

    def test_prestartup_actor_retries_after_module_start(self):
        actor = self.actor(); calls = []
        self.registration(actor, None)
        module = NS(RegistrationRound=lambda: 0, Track=lambda entity: calls.append(entity) or True)
        self.registration(actor, module); self.registration(actor, module)
        self.assertEqual([actor], calls)

    def test_exhausted_registration_retries_only_after_new_core_round(self):
        actor = self.actor(); calls = []; epoch = [0]
        module = NS(RegistrationRound=lambda: epoch[0],
            Track=lambda entity: calls.append(entity) or len(calls) > 1)
        self.registration(actor, module); self.registration(actor, module)
        self.assertEqual(1, len(calls)); self.assertFalse(actor.m_HCRegistered)
        epoch[0] += 1
        self.registration(actor, module); self.registration(actor, module)
        self.assertEqual(2, len(calls)); self.assertTrue(actor.m_HCRegistered)

    def test_module_restart_invalidates_cached_success(self):
        actor = self.actor(); calls = []
        for name in ("old", "new"):
            module = NS(RegistrationRound=lambda: 0,
                Track=lambda entity, n=name: calls.append(n) or True)
            self.registration(actor, module)
        self.assertEqual(["old", "new"], calls)

    def test_dead_and_client_callbacks_do_not_register(self):
        actor = self.actor(); calls = []
        module = NS(RegistrationRound=lambda: 0, Track=lambda entity: calls.append(entity) or True)
        self.registration(actor, module, server=False)
        actor.IsAlive = lambda: False
        self.registration(actor, module)
        self.assertEqual([], calls)

    def test_native_command_hook_preserves_parent_result_once(self):
        native = (SOURCE / "HCInfectedNative.c").read_text()
        hook = native.split("override bool ModCommandHandlerBefore", 1)[1].split("override void AfterStoreLoad", 1)[0]
        self.assertEqual(1, hook.count("super.ModCommandHandlerBefore("))
        self.assertIn("HCRegisterActive();", hook)
        self.assertIn("return consumed;", hook)
        for forbidden in ("SetPosition(", "StartCommand_", "OverrideMovement", "GetTargetEntity("):
            self.assertNotIn(forbidden, hook)

    def track(self, entity, context):
        return authored("HCInfectedModule.c", "Track(ZombieBase entity)", context,
            entity=entity, GetGame=lambda: NS(IsServer=lambda: True), Math=NS(Min=min),
            HCInfectedActor=lambda: NS(SearchPack=None, GroupId=0, InitializeProfile=lambda config: None))

    def registry(self, cap=2):
        context = NS(m_Healthy=True, m_RegistrationAttempts=0, m_WorkCap=cap,
            m_Actors=Array(), m_Config=NS(MaxTracked=2), m_MemberCap=2)
        context.FindActor = lambda entity: next((a for a in context.m_Actors if a.InfectedEntity is entity), None)
        context.CanRecycleActor = lambda actor: actor.GroupId == 0
        context.ResetSweep = lambda: None
        return context

    def test_registration_budget_saturates_without_incrementing_at_int_max(self):
        context = self.registry(); entity = NS(IsAlive=lambda: True)
        context.m_RegistrationAttempts = 2147483647
        self.assertFalse(self.track(entity, context))
        self.assertEqual(2147483647, context.m_RegistrationAttempts)

    def test_tracking_returns_admission_never_duplicates_and_respects_capacity(self):
        context = self.registry(cap=8); first = NS(IsAlive=lambda: True)
        self.assertTrue(self.track(first, context)); self.assertTrue(self.track(first, context))
        self.assertEqual(1, len(context.m_Actors))
        self.assertTrue(self.track(NS(IsAlive=lambda: True), context))
        self.assertFalse(self.track(NS(IsAlive=lambda: True), context))
        self.assertEqual(2, len(context.m_Actors))

    def test_unresolved_member_tombstones_are_not_recycled(self):
        context = self.registry(cap=8)
        context.m_Actors = Array([NS(InfectedEntity=None, GroupId=1, SearchPack=None), NS(InfectedEntity=None, GroupId=1, SearchPack=None)])
        self.assertFalse(self.track(NS(IsAlive=lambda: True), context))
        self.assertEqual([1, 1], [a.GroupId for a in context.m_Actors])
        context.m_Actors[0].GroupId = 0
        self.assertTrue(self.track(NS(IsAlive=lambda: True), context))
        self.assertEqual(2, len(context.m_Actors))

    def test_core_round_startup_dependencies_and_parent_disable_are_explicit(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        self.assertIn("m_RegistrationRound >= 2000000000", module)
        self.assertIn("m_RegistrationRound++;", module)
        self.assertIn("enabled-preference template", module)
        self.assertIn("unsupported native source build:", module)
        self.assertIn("native pack routing prerequisites unavailable", module)
        self.assertIn("if (settings.EnableHordes && m_Admission.HordeStimulusRoutes && m_WorkCap < 24)", module)
        self.assertIn("m_Admission = HCInfectedAdmission.Evaluate(m_Config);", module)


    def test_policy_selftest_config_expectations_match_shipped_defaults(self):
        # HCInfectedSelfTests.Run() asserts default config values; if it pins the
        # pre-default (all disabled) state it returns false under DayZDiag.
        state = (SOURCE / "HCInfectedState.c").read_text()
        selftest = (SOURCE / "HCInfectedSelfTests.c").read_text()
        defaults = dict(re.findall(r"bool (Enable\w+|RunPolicySelfTests) = (true|false);", state[:state.index("}")]))
        asserted = re.findall(r"(!?)config\.(Enable\w+|RunPolicySelfTests)\b", selftest)
        self.assertTrue(asserted, "self-test must check the shipped config defaults")
        for negated, flag in asserted:
            self.assertIn(flag, defaults, flag)
            self.assertEqual(defaults[flag] == "true", negated == "", flag)
        self.assertEqual(set(defaults), {flag for _, flag in asserted})

    def test_policy_selftest_checks_default_requested_versus_closed_admission(self):
        selftest = (SOURCE / "HCInfectedSelfTests.c").read_text()
        # The closed-admission assertion resolves with every qualification false so a local-acceptance
        # profile marker cannot fail a DayZDiag self-test (Evaluate honours the markers).
        self.assertIn("HCInfectedAdmission.Resolve(config, false, false, false, false, false, false)", selftest)
        self.assertNotIn("HCInfectedAdmission.Evaluate(", selftest)
        for path in ("CEAdoption", "NativePackRoutes", "Investigation", "SupplementaryChains",
                     "MemberRecovery", "HordeStimulusRoutes"):
            self.assertIn("!admission." + path, selftest)
        self.assertIn("HCInfectedAdmission.Resolve(config, true, true, true, true, true, true)", selftest)
        self.assertIn("admission.Describe()", selftest)

    def test_preferences_stay_default_on_while_admission_is_closed(self):
        # Product decision: features default ON; capability admission is honest.
        state = (SOURCE / "HCInfectedState.c").read_text()
        for name in ("EnableCEAdoption", "EnableNativePackRoutes", "EnableInvestigation",
                     "EnableSupplementaryChains", "EnableMemberRecovery", "EnableHordeStimulusRoutes"):
            self.assertIn("bool " + name + " = true;", state)
        self.assertIn("runtime acceptance pending", (SOURCE / "HCInfectedModule.c").read_text())

if __name__ == "__main__": unittest.main()
