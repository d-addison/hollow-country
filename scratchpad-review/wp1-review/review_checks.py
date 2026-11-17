"""Reviewer counterexamples. Explicit synthetic collaborators; no engine proof.

Uses the writer's translator on real bodies. For OnStart, adapts only native
out-argument/preprocessor/implicit-this syntax, never admission predicates.
"""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import re
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.unit import test_infected_admission as a

class Array(a.Array):
    def Clear(self): self.clear()

class ReviewChecks(unittest.TestCase):
    def startup(self, work=32, **overrides):
        events = []
        Admission, _ = a.admission_functions()
        config = a.requested_config(SchemaVersion=1, MaxTracked=24, MaxVoiceQueue=16,
            MaxVoicePerTick=8, VoiceCooldownSeconds=10, SaveIntervalSeconds=60, MaxInvestigators=2,
            CivilianVariants=Array(), MilitaryVariants=Array(), **overrides)
        profiles = NS(ValidateMap=lambda *x: True, NativeBuildSupported=lambda x: x == '1.30.164289',
                      ContactGuardQualified=lambda: False)
        is_valid = a.translate('HCInfectedState.c', 'bool IsValid(', (),
            fields=tuple(vars(config)), HCInfectedProfiles=profiles)
        config.IsValid = lambda: is_valid(config)
        ctx = NS(Instance=None, m_State=None, m_Healthy=False, m_Dirty=False,
                 m_Admission=a.admission(), m_Sweeps=Array(), m_Packs=Array())
        ctx.Quarantine = lambda reason: events.append(('quarantine', reason))
        ctx.IsEnabled = lambda settings: settings.EnableInfected
        def load(*args):
            ctx.m_State = NS(Groups=Array(), Reserved=0)
            return True
        # The test fixture contains no preexisting operator file, so loader branch
        # is not taken. Native version out-string is modeled as a returned string.
        original_read = Path.read_text
        def read(path, *args, **kwargs):
            source = original_read(path, *args, **kwargs)
            if path.name == 'HCInfectedModule.c':
                source = re.sub(r'#ifdef DIAG_DEVELOPER.*?#endif', '', source, flags=re.S)
                source = source.replace('string content, error;', 'string content = ""; string error = "";')
                source = source.replace('GetGame().GetVersion(runtimeBuild);', 'runtimeBuild = GetGame().GetVersion();')
                source = re.sub(r'(?<![.\w])Instance\b', 'self.Instance', source)
                source = source.replace('Instance = this;', 'Instance = self;')
            return source
        game = NS(IsServer=lambda: True, GetVersion=lambda: '1.30.164289', GetWorldName=lambda: 'chernarusplus',
                  GetWorld=lambda: NS(GetAIWorld=lambda: object()), ConfigIsExisting=lambda x: True)
        with patch.object(Path, 'read_text', read):
            fn = a.translate('HCInfectedModule.c', 'override void OnStart(',
                a.MODULE_METHODS + ('IsEnabled',), GetGame=lambda: game,
                HCInfectedConfig=lambda: config,
                HCInfectedStore=NS(ROOT='synthetic', DIRECTORY='synthetic/infected', Load=load),
                MakeDirectory=lambda *args: None, FileExist=lambda *args: False,
                JsonFileLoader=NS(SaveFile=lambda *args: True), HCInfectedAdmission=Admission,
                HCInfectedProfiles=profiles, HCInfectedPolicy=NS(**a.policy_functions()),
                HCInfectedClock=NS(UtcSeconds=lambda: 10000), HCHordeSweep=lambda: NS(), Print=events.append)
            fn(ctx, NS(EnableInfected=True, EnableHordes=True, EnableAlertChains=True,
                       MaxTickWorkItems=work, MaxActiveHordes=2, MaxActiveHordeMembers=24))
        return ctx, events

    def test_closed_capabilities_do_not_quarantine_native_only_startup_at_valid_core_budget(self):
        ctx, events = self.startup(work=4)
        print('STARTUP budget=4 all qualifications=false:', events)
        self.assertTrue(ctx.m_Healthy, 'An unadmitted horde preference must not quarantine native-only startup')

    def test_explicit_pack_disable_does_not_quarantine_unqualified_stimulus_preference(self):
        ctx, events = self.startup(EnableNativePackRoutes=False)
        print('STARTUP routes preference=false stimulus preference=true all qualifications=false:', events)
        self.assertTrue(ctx.m_Healthy, 'Dependency belongs in capability admission, not whole-module invalid config')

    def test_unadmitted_recovery_does_not_retire_and_save_a_previously_pending_journal(self):
        probe = a.UnqualifiedPathsPerformNoMutation()
        rec = a.Recorder()
        ctx = probe.tick_context(rec)
        # State 6 is exactly the state Load produces for a nonterminal old journal.
        # No actor is associated with it because MemberRecovery is unadmitted.
        record = NS(Id=1, State=6, CreatedUtc=1, LastSignalUtc=90, Living=3, Reserved=3,
            AdoptionStage=2, HasRoute=False, RecoveryConflicted=False, Anchor=(1, 0, 1),
            PreviousAnchor=(1, 0, 1), RoutePurpose=0, RouteResult=0, RoutePlanned=0,
            RouteCompleted=0, MemberIds=Array())
        ctx.m_State = NS(SchemaVersion=2, Build='1.30.164289', WorldName='chernarusplus',
            Epoch=1, Generation=7, SavedUtc=100, Reserved=3, Groups=Array())
        policies = NS(**a.policy_functions())
        position = a.translate('HCInfectedState.c', 'static bool ValidPosition(', ())
        roster = a.translate('HCHordeRecovery.c', 'static bool ValidateRoster(', ())
        validate = a.translate('HCInfectedState.c', 'static bool Validate(', (),
            HCInfectedPolicy=policies, ValidPosition=lambda p: position(None, p),
            HCHordeRecovery=NS(ValidateRoster=lambda r: roster(None, r)))
        def save(snapshot, member_cap, group_cap):
            # Execute the real DTO validator before allowing the synthetic write.
            self.assertTrue(validate(None, snapshot, 'chernarusplus', member_cap, group_cap, 4000))
            rec.events.append('save')
            return True
        ctx.m_State.Groups = Array([record]); ctx.m_Packs = Array([None])
        ctx.m_NextSave = 0; ctx.m_MemberCap = 24; ctx.m_GroupCap = 2
        a.module_call('override void OnTick(', ctx, 1.0,
            GetGame=lambda: NS(IsServer=lambda: True),
            HCInfectedClock=NS(UtcSeconds=lambda: 4000),
            HCNativeInfectedPack=NS(RetryPendingReleases=lambda: None),
            HCInfectedStore=NS(Save=save))
        print('PENDING JOURNAL all qualifications=false:', dict(State=record.State, Living=record.Living,
              Reserved=record.Reserved, events=rec.events))
        self.assertEqual(6, record.State, 'Dormant unqualified recovery intent must not be made permanently terminal')
        self.assertEqual([], rec.events)

    def test_startup_positive_control_default_budget_reaches_healthy(self):
        ctx, events = self.startup()
        self.assertTrue(ctx.m_Healthy, events)
        self.assertEqual(1, sum(isinstance(e, str) and 'capability admission (' in e for e in events))
        self.assertTrue(all(not getattr(ctx.m_Admission, p) for p in a.PATHS))

if __name__ == '__main__': unittest.main(verbosity=2)
