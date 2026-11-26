// Native evidence, installed scripts-1.30.164289: 1_Core/proto/EnScript.c:380
// Count, :394 Find, :407 Insert; EnDebug.c:96 Print; EnConvert.c:30 int.ToString.
// Native membership release uses HCInfectedNavigation.c's inspected AI APIs;
// refund requires its verified Release() result, never an assumed deletion.
class HCHordeSweep
{
    int Living;
    int ConfirmedDead;
    int Accounted;
    bool Ambiguous;
    ref HCInfectedClue Stimulus;
    vector Sum;
    bool Clue;
    bool Engaged;

    void Clear()
    {
        Living = 0;
        ConfirmedDead = 0;
        Accounted = 0;
        Ambiguous = false;
        Stimulus = null;
        Sum = vector.Zero;
        Clue = false;
        Engaged = false;
    }
}

class HCInfectedModule : HCModule
{
    static HCInfectedModule Instance;
    protected ref HCInfectedConfig m_Config;
    protected ref HCOperationalStatus m_HCOwnerStatus = new HCOperationalStatus;
    protected ref HCNativeVariantAdmission m_NativeVariants;
    // Closed until OnStart derives requested-AND-qualified capabilities.
    protected ref HCInfectedAdmission m_Admission = new HCInfectedAdmission;
    protected ref HCInfectedSnapshot m_State;
    protected ref array<ref HCInfectedActor> m_Actors = new array<ref HCInfectedActor>;
    protected ref array<ref HCInfectedVoice> m_Voices = new array<ref HCInfectedVoice>;
    protected ref array<ref HCHordeSweep> m_Sweeps = new array<ref HCHordeSweep>;
    protected ref array<ref HCNativeInfectedPack> m_Packs = new array<ref HCNativeInfectedPack>;
    protected ref array<ref HCInfectedActor> m_Investigators = new array<ref HCInfectedActor>;
    // Runtime-only: a restarted aborted intent is still unknown membership.
    // Only a failed transfer seen by this process may leave other slots open.
    // Native scripts-1.30.164289: EnScript.c:917/:926 map Contains/Insert.
    protected ref map<int, bool> m_FailedCohorts = new map<int, bool>;
    protected ref HCAlertChain m_AlertChain = new HCAlertChain;
    // Last pack route refusal this module logged (site:reason); "" after a success.
    protected string m_LastRouteRefusal;
    protected bool m_Healthy;
    protected bool m_Hordes;
    protected string m_PacingHordeId;
    protected int m_PacingHordeAttempts;
    // Runtime-only offer: retry the same CE roster and fixed reservation anchor.
    // Strong refs: the offer retries across ticks for up to 600 s while Track
    // can recycle a dead candidate's slot (or LOD archive it to the tombstone
    // FIFO), freeing it; a raw
    // HCInfectedActor (not Managed) would dangle. Eligibility re-checks the body.
    protected ref array<ref HCInfectedActor> m_PacingHordeCandidates = new array<ref HCInfectedActor>;
    protected vector m_PacingHordeAnchor;
    protected int m_PacingHordeTarget;
    protected float m_PacingHordeDeadline;
    protected ref HCHordeRouteSurvey m_PacingHordePatrol;
    protected ref HCActivityCounters m_HCHordeActivity = new HCActivityCounters("offers retries budget_deferred offers_closed no_seed no_route paced_wait started failed reinforcement_retired refused work_cap adoption_disabled checkpoint_failed state_blocked cap_full slots_full retire_checkpoint reuse_wait cohort_ineligible cohort_position cohort_range cohort_changed defaults_missing capacity_changed reserve_full recovery_conflict prepare_checkpoint offer_expired", "[HC Hordes]");
    protected bool m_PacingHordeWaiting;
    protected bool m_Chains;
    protected bool m_Dirty;
    protected ref HCInfectedSaveJob m_SaveJob;
    protected int m_WorkCap;
    protected int m_GroupCap;
    protected int m_MemberCap;
    protected int m_Cursor;
    protected int m_AdoptionCursor;
    protected int m_RecoveryCursor;
    protected int m_RetargetCursor;
    protected int m_HCPackTickCursor;
    protected ref HCWorkBudget m_HCAdoptWork = new HCWorkBudget;
    protected int m_VoiceAttempts;
    protected int m_RegistrationAttempts;
    protected int m_RegistrationRound;
    protected int m_LastUtc;
    protected int m_StartedUtc;
    protected int m_ObservationsRemaining;
    protected int m_RoutesRemaining;
    protected float m_Now;
    protected float m_NextSave;
    protected float m_NextAdopt;

    override string GetName()
    {
        return "Infected";
    }

    // Passive cached owner reports only. The variety getter performs no IO,
    // capability experiment or activation; degraded admission remains visible
    // to HC-1 while the primary owner is healthy.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        if (m_Healthy)
        {
            HCOperationalStatus variety = HCInfectedVarietyModule.HCObservedStatus();
            if (variety && variety.HCState() == "degraded") { return variety; }
        }
        return m_HCOwnerStatus;
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableInfected;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || Instance)
            return;
        m_Config = new HCInfectedConfig;
        MakeDirectory(HCInfectedStore.ROOT);
        MakeDirectory(HCInfectedStore.DIRECTORY);
        string path = HCInfectedStore.DIRECTORY + "/config.json";
        string content, error;
        if (FileExist(path))
        {
            if (!HCInfectedStore.ReadBounded(path, content) || !JsonFileLoader<HCInfectedConfig>.LoadData(content, m_Config, error))
            {
                Quarantine("invalid config; preserving files");
                return;
            }
            // Templates written before 89e6fe61 pinned the old default 24, which
            // keeps hordes, LOD and fresh variety at their headroom floor. Raise
            // that exact legacy value in memory only; the operator file is kept
            // and any other explicit value is honoured.
            if (m_Config && m_Config.MaxTracked == 24)
            {
                m_Config.MaxTracked = 256;
                Print("[HC Infected] config_migration MaxTracked legacy=24 now=256 file=preserved runtime=PENDING");
            }
        }
        else if (!JsonFileLoader<HCInfectedConfig>.SaveFile(path, m_Config, error))
        {
            Quarantine("cannot create enabled-preference template");
            return;
        }
        if (!m_Config || !m_Config.IsValid() || settings.MaxTickWorkItems < 4 || settings.MaxActiveHordes < 1 || settings.MaxActiveHordeMembers < 1)
        {
            Quarantine("invalid limits");
            return;
        }
        // Settings already validated the ranges; out-of-range values keep the catalog defaults.
        HCInfectedRoomCatalog.ConfigureBinding(settings.InfectedBindRadius, settings.MaxBindQueriesPerTick);
        // One bounded attempt per Clear(); a refusal is latched and logged once.
        HCInfectedRoomCatalog.EnsureProductionLoaded();
        // Preferences stay as the operator wrote them; native-affecting paths use
        // only the admitted capability (preference AND qualification).
        m_Admission = HCInfectedAdmission.Evaluate(m_Config);
        m_WorkCap = Math.Min(settings.MaxTickWorkItems, 32);
        // The eight-item floor follows work that can actually run. An unadmitted
        // horde preference or a dormant journal never raises the prerequisite.
        bool admittedHordeWork = settings.EnableHordes && (m_Admission.CEAdoption || m_Admission.MemberRecovery || m_Admission.HordeStimulusRoutes);
        if ((admittedHordeWork || m_Admission.NativePackRoutes || m_Admission.Investigation) && m_WorkCap < 8)
        {
            Quarantine("hordes/routing require at least eight bounded work items");
            return;
        }
        if (settings.EnableHordes && m_Admission.CEAdoption && !HCInfectedPolicy.AdoptionWorkReady(m_WorkCap))
        {
            Quarantine("cohort adoption requires work budget at least 9");
            return;
        }
        if (settings.EnableHordes && m_Admission.HordeStimulusRoutes && m_WorkCap < 24)
        {
            Quarantine("stimulus routes require hordes and at least 24 bounded work items");
            return;
        }
        string runtimeBuild;
        GetGame().GetVersion(runtimeBuild);
        if (!HCInfectedProfiles.NativeBuildSupported(runtimeBuild))
        {
            Quarantine("unsupported native source build: " + runtimeBuild);
            return;
        }
        if (m_Admission.NativePackRoutes || m_Admission.Investigation)
        {
            bool packReady = GetGame().GetWorld() && GetGame().GetWorld().GetAIWorld();
            packReady = packReady && GetGame().ConfigIsExisting("GroupBehaviourTemplates DZInfectedPackBeh");
            if (!packReady)
            {
                Quarantine("native pack routing prerequisites unavailable");
                return;
            }
        }
        // Syntax validation plus populated maps mirrors ConfiguredVariant selection;
        // unsupported stalker/heavy slots are reported, never admitted.
        bool variantMaps = HCInfectedProfiles.ValidateMap(m_Config.CivilianVariants, false);
        variantMaps = variantMaps && HCInfectedProfiles.ValidateMap(m_Config.MilitaryVariants, false);
        if (variantMaps)
        {
            variantMaps = m_Config.CivilianVariants.Count() == 4 && m_Config.MilitaryVariants.Count() == 4;
        }
        bool emptyMaps = m_Config.CivilianVariants && m_Config.MilitaryVariants && m_Config.CivilianVariants.Count() == 0 && m_Config.MilitaryVariants.Count() == 0;
        if (m_Config.EnableVariantPolicies && emptyMaps)
        {
            Print("[HC Infected] variant preference enabled; no stance maps configured (default); native profiles used");
        }
        else if (m_Config.EnableVariantPolicies && !variantMaps)
        {
            Print("[HC Infected] variant preference enabled; explicit stance maps invalid (need 4 supported entries each); native profiles retained");
        }
        HCInfectedProfiles.LogUnsupportedSubstitutions(m_Config);
        if (m_Config.EnableContactGuard && !HCInfectedProfiles.ContactGuardAdmitted())
            Print("[HC Infected] contact guard pending native wall-hit qualification; native combat retained");
        Print("[HC Infected] enabled-preference template defaults; existing explicit disables preserved");
        Print("[HC Infected] capability admission (requested vs admitted; unqualified paths fail closed, native behavior retained): " + m_Admission.Describe());
        m_GroupCap = settings.MaxActiveHordes;
        m_MemberCap = settings.MaxActiveHordeMembers;
        int trackedCap = m_Config.MaxTracked;
        Print("[HC Infected] limits groups=" + m_GroupCap.ToString() + " members=" + m_MemberCap.ToString() + " tracked=" + trackedCap.ToString() + " per_pack=" + HCHordeLimits.MAX_PACK.ToString() + " runtime=PENDING");
        m_Hordes = settings.EnableHordes;
        m_Chains = settings.EnableAlertChains;
        m_LastUtc = HCInfectedClock.UtcSeconds();
        if (m_LastUtc <= 0)
        {
            Quarantine("unsupported UTC clock");
            return;
        }
        m_StartedUtc = m_LastUtc;
        if (m_Hordes)
        {
            // Restart interpretation, retirement and persistence belong to an
            // admitted journal lifecycle (adoption or member recovery). Without
            // one the stored journal is validated and kept verbatim.
            bool journalLifecycle = m_Admission.CEAdoption || m_Admission.MemberRecovery;
            bool journalLoaded;
            if (journalLifecycle)
                journalLoaded = HCInfectedStore.Load(m_State, GetGame().GetWorldName(), m_MemberCap, m_GroupCap, m_LastUtc);
            else
                journalLoaded = HCInfectedStore.LoadVerbatim(m_State, GetGame().GetWorldName(), m_MemberCap, m_GroupCap, m_LastUtc);
            if (!journalLoaded)
            {
                Quarantine("state/schema/build/world/clock mismatch; no fallback or reset");
                return;
            }
            foreach (HCHordeRecord group : m_State.Groups)
            {
                m_Sweeps.Insert(new HCHordeSweep);
                m_Packs.Insert(null);
            }
            m_Dirty = journalLifecycle;
        }
        // Content admission is config-only. The separate variety module owns
        // behavior/scaling; neither path mutates CE or the shared preference.
        m_NativeVariants = HCNativeVariantAdmission.Check(settings.EnableInfectedVariety);
        Print(m_NativeVariants.HCAdmissionLine());
        m_Healthy = true;
        if (m_Hordes)
        {
            m_SaveJob = new HCInfectedSaveJob;
            m_SaveJob.HCBind(this);
            HCSaveScheduler.HCRegister(m_SaveJob);
        }
        // The posture owner (InfectedVariety) is a separate module registered after this one, so
        // it cannot have started when HC-1 captures this row. It prints its own readiness line;
        // this owner reports only its own started state and still surfaces a later degraded
        // posture row through HCGetOperationalStatus.
        m_HCOwnerStatus.HCPublish("ready", "infected_owner_running_runtime_pending");
        Instance = this;
        // Periodic saves run half an interval after adoption so the two
        // persistence-heavy steps never share a server tick.
        m_NextSave = m_Config.SaveIntervalSeconds + m_Config.SaveIntervalSeconds / 2;
        m_NextAdopt = m_Config.SaveIntervalSeconds;
#ifdef DIAG_DEVELOPER
        if (m_Config.RunPolicySelfTests && !HCInfectedSelfTests.Run())
            Quarantine("scalar policy selftest failed");
#endif
        if (m_Healthy)
        {
            HCInfectedVisionQualification.HCThreatReset(true);
            HCInfectedVisionQualification.Admitted();
        }
        Print("[HC Infected] source installed; optional native pack routing; no materialization; runtime acceptance pending");
    }

    protected void Quarantine(string reason)
    {
        m_Healthy = false;
        m_HCOwnerStatus.HCPublish("refused", reason);
        HCInfectedVisionQualification.HCThreatReset(false);
        if (m_SaveJob)
        {
            HCSaveScheduler.HCUnregister(m_SaveJob);
            m_SaveJob.HCDetach();
            m_SaveJob = null;
        }
        if (Instance == this)
            Instance = null;
        ReleasePacks();
        Print("[HC Infected] disabled: " + reason);
    }

    // Per-path requested vs admitted vs reason; bounded diagnostic for logs/self-tests.
    string AdmissionStatus()
    {
        return m_Admission.Describe();
    }

    // Fixed content-status owner can read this without repeating config work.
    HCNativeVariantAdmission NativeVariants()
    {
        return m_NativeVariants;
    }

    bool ContactGuardEnabled()
    {
        return m_Healthy && m_Config.EnableContactGuard && HCInfectedProfiles.ContactGuardAdmitted() && GetGame().IsServer();
    }

    protected HCInfectedActor FindActor(ZombieBase entity)
    {
        foreach (HCInfectedActor actor : m_Actors)
        {
            if (actor.InfectedEntity == entity)
                return actor;
        }
        return null;
    }

    protected bool CanRecycleActor(HCInfectedActor actor)
    {
        // Keep assigned tombstones until terminal retirement; otherwise a new
        // CE registration can erase the only confirmed death/missing evidence.
        if (actor.GroupId == 0) return true;
        if (!m_State || actor.GroupId < 1 || actor.GroupId > m_State.Groups.Count())
            return false;
        return m_State.Groups[actor.GroupId - 1].State == 5;
    }

    bool Track(ZombieBase entity)
    {
        if (!m_Healthy || !GetGame().IsServer() || !entity || !entity.IsAlive())
        {
            return false;
        }
        if (!entity.HCLODTrackingDue()) { return false; }
        // Check before increment: rejected callbacks cannot wrap a native int.
        if (m_RegistrationAttempts >= m_WorkCap)
        {
            return false;
        }
        m_RegistrationAttempts++;
        if (FindActor(entity))
        {
            return true;
        }
        // Do not let distant calm CE callbacks refill released slots. Unknown
        // observer distance is admitted; native AI keeps running either way.
        float nearest = HCInfectedLOD.NearestDistance(HCPerfPlayers.HCGet(), entity.GetPosition());
        if (nearest > HCInfectedLOD.TrackingRange() && entity.GetMindStateSynced() == DayZInfectedConstants.MINDSTATE_CALM)
        {
            entity.HCLODDeferTracking();
            return false;
        }
        int slot = -1;
        for (int i = 0; i < m_Actors.Count(); i++)
        {
            if (CanRecycleActor(m_Actors[i]) && (!m_Actors[i].InfectedEntity || !m_Actors[i].InfectedEntity.IsAlive()))
            {
                slot = i;
                break;
            }
        }
        if (slot < 0 && m_Actors.Count() >= m_Config.MaxTracked)
            return false;
        HCInfectedActor actor = new HCInfectedActor;
        actor.InfectedEntity = entity;
        actor.InitializeProfile(m_Config);
        HCModuleReadiness.HCUseGuarded("Infected", "actor_bound", entity);
        if (slot < 0)
            m_Actors.Insert(actor);
        else
        {
            if (m_Actors[slot].SearchPack)
            {
                m_Actors[slot].SearchPack.Release();
                m_Actors[slot].SearchPack = null;
            }
            m_Actors[slot] = actor;
        }
        // A changed registry invalidates an unfinished aggregate.
        ResetSweep();
        return true;
    }

    // Called only after a native join receipt, with capacity reserved before creation.
    bool HCReinforceTrack(ZombieBase body, int groupId)
    {
        if (!FindActor(body) && !Track(body)) { return false; }
        HCInfectedActor actor = FindActor(body);
        if (!actor || groupId < 1 || groupId > m_State.Groups.Count()) { return false; }
        actor.GroupId = groupId;
        actor.EverAssigned = true;
        ResetSweep();
        return true;
    }

    bool HCReinforceRoom()
    {
        return m_Healthy && m_Actors.Count() < m_Config.MaxTracked && m_RegistrationAttempts < m_WorkCap;
    }

    // Only the live pack that owns the reserved continuation can retire its
    // unfilled offer. The journal requires immutable per-record reservations;
    // partial refunds would fail restart validation. Use its terminal lifecycle
    // instead, retaining the full charge until native Release completes.
    bool HCReinforceRetire(HCNativeInfectedPack pack, int groupId, int admitted, int target)
    {
        if (!m_Healthy || !m_State || groupId < 1 || groupId > m_State.Groups.Count()) { return false; }
        if (!pack || m_Packs[groupId - 1] != pack) { return false; }
        HCHordeRecord record = m_State.Groups[groupId - 1];
        if (record.AdoptionStage != 2 || record.State == 6 || record.BudgetReleased) { return false; }
        if (record.Reserved != target || admitted < 3 || admitted >= target) { return false; }
        record.State = 5;
        record.HCStopRoute();
        m_Dirty = true;
        if (!SaveAdoptionBoundary("reinforcement_retire")) { return false; }
        m_HCHordeActivity.Add("reinforcement_retired");
        Print("[HC Hordes] reinforcement_retired cohort=" + groupId.ToString() + " admitted=" + admitted.ToString() + " reserved=" + target.ToString() + " refund=awaiting_native_release runtime=PENDING");
        // FinishSweep's RefundRetired retries release and refunds exactly once.
        return true;
    }

    int RegistrationRound()
    {
        return m_RegistrationRound;
    }

    void NativeVoice(ZombieBase entity, AnimSoundVoiceEvent soundEvent)
    {
        if (!m_Healthy || !m_Chains || !GetGame().IsServer())
            return;
        m_VoiceAttempts++;
        if (m_VoiceAttempts > Math.Min(m_Config.MaxVoicePerTick, m_WorkCap) || !entity || !soundEvent || !soundEvent.m_NoiseParams)
            return;
        int nowUtc = HCInfectedClock.UtcSeconds();
        if (nowUtc < m_LastUtc)
        {
            Quarantine("voice callback clock rollback");
            return;
        }
        m_Now = nowUtc - m_StartedUtc;
        entity.HCRegisterActive();
        HCInfectedActor actor = FindActor(entity);
        if (!actor)
            return;
        bool duplicate = actor.LastEventId == soundEvent.m_iID && actor.LastEventAt == m_Now;
        if (!HCInfectedPolicy.AdmitVoice(m_Now, actor.NextVoice, m_Voices.Count(), m_Config.MaxVoiceQueue, m_VoiceAttempts - 1, m_Config.MaxVoicePerTick, entity.IsAlive(), true, duplicate, 0, 1, m_Now + actor.ClueLifetime))
            return;
        HCInfectedVoice voice = new HCInfectedVoice;
        voice.Emitter = entity;
        voice.Clue = new HCInfectedClue;
        voice.Clue.Origin = entity.GetPosition();
        if (!HCInfectedStore.ValidPosition(voice.Clue.Origin))
            return;
        voice.Clue.Observed = m_Now;
        voice.Clue.Expires = m_Now + actor.ClueLifetime;
        // Decay logical attention; native hearing strength is never modified.
        voice.Clue.Strength = HCInfectedPolicy.Attenuate(voice.Clue.Strength);
        voice.Clue.EventId = soundEvent.m_iID;
        m_Voices.Insert(voice);
        actor.LastEventId = soundEvent.m_iID;
        actor.LastEventAt = m_Now;
        actor.NextVoice = m_Now + m_Config.VoiceCooldownSeconds;
        if (m_Admission.SupplementaryChains)
            m_AlertChain.NativeEmission(actor, soundEvent.m_iID, m_Now, m_Config.MaxVoiceQueue, m_Actors.Count());
        // super.ProcessSoundVoiceEvent already delivered the native hearing
        // signal. Supplementary local attention can only use that real origin;
        // it never synthesizes another sound, targets or client RPC.
    }

    protected void ResetSweep()
    {
        m_Cursor = 0;
        foreach (HCHordeSweep sweep : m_Sweeps)
            sweep.Clear();
    }

    protected void SampleActor(HCInfectedActor actor)
    {
        if (actor.Clue && !actor.Clue.IsLive(m_Now))
            actor.Clue = null;
        if (actor.Visual && !actor.Visual.IsLive(m_Now))
            actor.Visual = null;
        if (actor.InfectedEntity && actor.InfectedEntity.IsAlive())
        {
            actor.RefreshProfile();
            if (m_Admission.Investigation && HCInfectedObservation.VisualSamplingAvailable() && m_ObservationsRemaining > 0 && m_Now >= actor.NextVisualSample)
            {
                HCInfectedObservation.SampleVisual(actor, m_Now);
                actor.NextVisualSample = m_Now + Math.Max(2, m_Actors.Count());
                m_ObservationsRemaining--;
            }
            TryInvestigate(actor);
        }
        SampleMembership(actor);
    }

    protected void SampleMembership(HCInfectedActor actor)
    {
        if (!m_Hordes || actor.GroupId < 1 || actor.GroupId > m_Sweeps.Count())
            return;
        HCHordeRecord record = m_State.Groups[actor.GroupId - 1];
        if (record.State == 5 || record.State == 6)
            return;
        HCHordeSweep sweep = m_Sweeps[actor.GroupId - 1];
        sweep.Accounted++;
        if (!actor.InfectedEntity)
        {
            if (actor.ConfirmedDead)
                sweep.ConfirmedDead++;
            else
                sweep.Ambiguous = true;
            return;
        }
        if (!actor.InfectedEntity.IsAlive())
        {
            actor.ConfirmedDead = true;
            sweep.ConfirmedDead++;
            return;
        }
        if (actor.ConfirmedDead)
        {
            sweep.Ambiguous = true;
            return;
        }
        if (record.HasRoute)
        {
            HCNativeInfectedPack pack = m_Packs[actor.GroupId - 1];
            if (!pack || !pack.OwnsMember(actor.InfectedEntity))
            {
                sweep.Ambiguous = true;
                return;
            }
        }
        vector position = actor.InfectedEntity.GetPosition();
        if (!HCInfectedStore.ValidPosition(position))
        {
            sweep.Ambiguous = true;
            return;
        }
        sweep.Living++;
        sweep.Sum = sweep.Sum + position;
        HCInfectedClue sensed = HCHordeStimulus.ChooseClue(actor, m_Now, HeardAdmitted());
        if (HCHordeStimulus.PreferHotClue(sensed, sweep.Stimulus, m_Now))
        {
            sweep.Stimulus = sensed;
        }
        int mind = actor.InfectedEntity.GetMindStateSynced();
        if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT)
            sweep.Engaged = true;
    }

    protected void FinishSweep(int nowUtc)
    {
        // Journal records advance only under an admitted lifecycle; an unresolved
        // record is never retired by anything but admitted member recovery.
        string sweepReport = "";
        int sweepCount = 0;
        if (m_Admission.CEAdoption || m_Admission.MemberRecovery)
            sweepCount = m_Sweeps.Count();
        for (int i = 0; i < sweepCount; i++)
        {
            HCHordeRecord record = m_State.Groups[i];
            HCHordeSweep sweep = m_Sweeps[i];
            // Reserved shortfall is not ambiguous membership while its live
            // staging pack owns the bounded reinforcement continuation.
            if (m_Packs[i] && m_Packs[i].HCReinforcePending()) { continue; }
            if (record.State == 5)
            {
                RefundRetired(record, nowUtc);
                continue;
            }
            if (record.State == 6 && !m_Admission.MemberRecovery && !m_Packs[i])
                continue;
            if (record.State != 5 && record.State != 6)
            {
                if (!HCInfectedPolicy.CompleteMembership(record.Reserved, sweep.Living, sweep.ConfirmedDead, sweep.Accounted, sweep.Ambiguous))
                {
                    record.State = 6;
                    record.RecoveryConflicted = true;
                    record.HCStopRoute();
                    if (m_Packs[i])
                    {
                        bool releaseCompleted = m_Packs[i].Release();
                        SnapshotRoute(record, m_Packs[i]);
                        if (releaseCompleted)
                        {
                            m_Packs[i] = null;
                        }
                    }
                    m_Dirty = true;
                    sweepReport += " ambiguous_membership_reservation_retained=" + record.Id.ToString();
                }
            }
            sweep.Clue = sweep.Stimulus && sweep.Stimulus.IsLive(m_Now);
            int living = sweep.Living;
            if (record.State == 6)
            {
                // Age, an empty partial sweep, and native pack release cannot
                // resolve journal membership. Only recovery may leave state 6.
                continue;
            }
            if (sweep.Engaged || sweep.Clue)
                record.LastSignalUtc = nowUtc;
            int next = HCInfectedPolicy.NextHordeState(record.State, living, sweep.Clue, sweep.Engaged, nowUtc - record.LastSignalUtc, nowUtc - record.CreatedUtc);
            if (next != record.State)
            {
                sweepReport += " horde=" + record.Id.ToString() + " state=" + record.State.ToString() + "->" + next.ToString();
                record.State = next;
                m_Dirty = true;
            }
            if (record.State == 5)
            {
                RefundRetired(record, nowUtc);
            }
            if (record.State != 6)
            {
                if (record.Living != living)
                    m_Dirty = true;
                record.Living = living;
                if (living > 0 && record.State != 5)
                {
                    vector centroid = sweep.Sum * HCInfectedPolicy.CentroidWeight(living);
                    if (vector.DistanceSq(record.Anchor, centroid) > 25)
                    {
                        record.PreviousAnchor = record.Anchor;
                        record.Anchor = centroid;
                        m_Dirty = true;
                    }
                }
            }
        }
        if (sweepReport != "") { Print("[HC Infected] sweep" + sweepReport); }
        // Cohort retargets steer native packs; never reached without admission.
        if (m_Admission.HordeStimulusRoutes)
            RetargetCohorts();
        ResetSweep();
    }

    protected void SnapshotRoute(HCHordeRecord record, HCNativeInfectedPack pack)
    {
        if (!pack || pack.RoutePlanned == 0) return;
        if (record.RoutePurpose != pack.RoutePurpose || record.RouteResult != pack.RouteResult)
            m_Dirty = true;
        if (record.RouteCompleted != pack.RouteCompleted || record.HasRoute == pack.IsReleasing())
            m_Dirty = true;
        if (record.RoutePlanned != pack.RoutePlanned || vector.DistanceSq(record.RouteEnd, pack.RouteEnd) > 0)
            m_Dirty = true;
        record.RoutePurpose = pack.RoutePurpose;
        record.RouteResult = pack.RouteResult;
        record.RoutePlanned = pack.RoutePlanned;
        record.RouteCompleted = pack.RouteCompleted;
        record.RouteEnd = pack.RouteEnd;
        record.HasRoute = pack.RouteResult == 1 && !pack.IsReleasing();
    }

    protected void RetargetCohorts()
    {
        int count = m_Sweeps.Count();
        if (!m_Config.EnableHordeStimulusRoutes || count < 1 || m_RoutesRemaining < 1)
        {
            return;
        }
        int startIndex = m_RetargetCursor % count;
        m_RetargetCursor = HCInfectedPolicy.NextAdoptionCursor(startIndex, count);
        for (int offset = 0; offset < count; offset++)
        {
            int index = (startIndex + offset) % count;
            HCHordeRecord record = m_State.Groups[index];
            HCHordeSweep sweep = m_Sweeps[index];
            HCNativeInfectedPack pack = m_Packs[index];
            if (record.State == 5 || record.State == 6 || sweep.Engaged || !pack)
            {
                continue;
            }
            if (pack.IsV2Drifting())
            {
                // V2 owns this pack, including ecology's alternate entry path.
                continue;
            }
            if (!sweep.Clue || !sweep.Stimulus.IsLive(m_Now))
            {
                continue;
            }
            // A migration that actually spends a path owns this attempt. A
            // pre-path refusal leaves the ordinary noise retarget available.
            int result = 0;
            bool fallbackReady = true;
            if (HCEcologyMigrationQualification.Admitted())
            {
                fallbackReady = HCInfectedPolicy.CompleteMembership(record.Reserved, sweep.Living, sweep.ConfirmedDead, sweep.Accounted, sweep.Ambiguous);
                if (fallbackReady)
                {
                    result = HCEcologyMigration.SubmitCohort(record.Id, pack, m_Actors, sweep.Living, m_Now, m_Admission.Investigation, m_Admission.SupplementaryChains);
                }
            }
            if (result == 0 && fallbackReady)
            {
                result = pack.Retarget(sweep.Stimulus, m_Now);
            }
            // 0=pre-path rejection; 1=path attempted/failed; 2=accepted;
            // 3=durable migration continuation pending (no ordinary fallback).
            // Failed geometry remains charged, cooldown/attempts remain spent.
            if (HCInfectedPolicy.RetargetSpent(result))
            {
                m_RoutesRemaining--;
                m_RetargetCursor = HCInfectedPolicy.NextAdoptionCursor(index, count);
                SnapshotRoute(record, pack);
            }
            if (m_RoutesRemaining < 1)
            {
                return;
            }
        }
    }

    // Called only by this owner's save job. Encoding freezes the image; later
    // actor/route updates keep m_Dirty for the next generation, never alter it.
    bool HCBeginCheckpoint(HCStagedSaveImage image)
    {
        if (!m_Healthy || !m_State) { return false; }
        if (!HCInfectedStore.HCBeginImage(image, m_State, m_MemberCap, m_GroupCap)) { return false; }
        m_Dirty = false;
        return true;
    }

    void HCCheckpointFailed()
    {
        Quarantine("snapshot write/readback failed; preserving spent intent");
    }

    protected bool SaveAdoptionBoundary(string boundary)
    {
        // Durability barrier: finish any older image, then persist current intent
        // BEFORE native membership transfer/refund reuse. Routine ticks only queue.
        // Close/readback is not fsync or an atomic native CE/group transaction.
        if (!m_SaveJob || !HCSaveScheduler.HCFlush(m_SaveJob))
        {
            Quarantine("adoption " + boundary + " pending write/readback failed; preserving spent intent");
            return false;
        }
        m_SaveJob.HCDirty = true;
        if (!HCSaveScheduler.HCFlush(m_SaveJob))
        {
            Quarantine("adoption " + boundary + " write/readback failed; preserving spent intent");
            return false;
        }
        m_NextSave = m_Now + m_Config.SaveIntervalSeconds + m_Config.SaveIntervalSeconds / 2;
        return true;
    }

    protected void RefundRetired(HCHordeRecord record, int nowUtc)
    {
        if (record.State != 5 || record.BudgetReleased)
        {
            return;
        }
        int index = record.Id - 1;
        HCNativeInfectedPack retiringPack = m_Packs[index];
        if (retiringPack)
        {
            bool released = retiringPack.Release();
            SnapshotRoute(record, retiringPack);
            if (!released)
            {
                return;
            }
            m_Packs[index] = null;
        }
        record.HCStopRoute();
        record.BudgetReleased = true;
        record.RetiredUtc = nowUtc;
        m_State.Reserved -= record.Reserved;
        m_Dirty = true;
        int used = 0;
        foreach (HCHordeRecord budgetRecord : m_State.Groups)
        {
            if (!budgetRecord.BudgetReleased)
            {
                used++;
            }
        }
        Print("[HollowCountry] infected horde budget used=" + used.ToString() + "/" + m_GroupCap.ToString());
    }

    protected void TryAdopt(int nowUtc)
    {
        m_PacingHordeWaiting = false;
        m_HCHordeActivity.Add("offers");
        if (m_PacingHordeId == "" || m_Now < m_PacingHordeDeadline) { HCTryAdoptPaced(nowUtc); }
        else { m_HCHordeActivity.HCRefuse("offer_expired"); }
        if (!m_PacingHordeWaiting && m_PacingHordeId != "")
        {
            // Includes early eligibility/prepare failures; no native start is
            // replayed. A confirmed start is immune to this cancellation.
            HCEventModule.HCCancelSituation(m_PacingHordeId);
            m_PacingHordeId = "";
            m_PacingHordeAttempts = 0;
            m_PacingHordeCandidates.Clear();
            m_PacingHordeAnchor = vector.Zero;
            m_PacingHordeTarget = 0;
            m_PacingHordePatrol = null;
            m_PacingHordeDeadline = 0;
            m_HCHordeActivity.Add("offers_closed");
        }
    }

    protected void HCTryAdoptPaced(int nowUtc)
    {
        if (!HCInfectedPolicy.AdoptionWorkReady(m_WorkCap)) { m_HCHordeActivity.HCRefuse("work_cap"); return; }
        if (!m_Hordes || !m_Admission.CEAdoption)
        {
            m_HCHordeActivity.HCRefuse("adoption_disabled");
            return;
        }
        if (m_SaveJob && (m_SaveJob.HCDirty || m_SaveJob.HCInFlight))
        {
            if (!HCSaveScheduler.HCFlush(m_SaveJob)) { m_HCHordeActivity.HCRefuse("checkpoint_failed"); HCCheckpointFailed(); return; }
        }
        int activeGroups = 0;
        int reusableSlot = -1;
        for (int slot = 0; slot < m_State.Groups.Count(); slot++)
        {
            HCHordeRecord pending = m_State.Groups[slot];
            if (!pending.BudgetReleased)
            {
                activeGroups++;
                // A persisted stage-3 abort may also be a crashed PREPARE.
                // Never infer safe membership from that journal value alone.
                if (pending.State == 6)
                {
                    if (!m_FailedCohorts.Contains(pending.Id))
                    {
                        m_HCHordeActivity.HCRefuse("state_blocked");
                        return;
                    }
                }
            }
            if (HCInfectedPolicy.MayReuseHorde(pending.State, pending.BudgetReleased, pending.RetiredUtc, nowUtc))
            {
                if (!m_Packs[slot] && reusableSlot < 0)
                {
                    reusableSlot = slot;
                }
            }
        }
        if (activeGroups >= m_GroupCap)
        {
            m_HCHordeActivity.HCRefuse("cap_full");
            return;
        }
        if (reusableSlot < 0 && m_State.Groups.Count() >= m_GroupCap)
        {
            m_HCHordeActivity.HCRefuse("slots_full");
            return;
        }
        if (reusableSlot >= 0 && m_State.Groups[reusableSlot].RetiredUtc > m_State.SavedUtc)
        {
            // Land terminal refund in the preceding generation before reuse.
            if (!SaveAdoptionBoundary("retire"))
            {
                m_HCHordeActivity.HCRefuse("retire_checkpoint");
                return;
            }
        }
        if (reusableSlot >= 0 && nowUtc <= m_State.SavedUtc)
        {
            m_HCHordeActivity.HCRefuse("reuse_wait");
            return;
        }
        bool retryOffer = m_PacingHordeId != "";
        ref array<HCInfectedActor> candidates = new array<HCInfectedActor>;
        vector anchor = m_PacingHordeAnchor;
        int scanCount = Math.Min(m_Actors.Count(), m_WorkCap - 6);
        if (retryOffer) { scanCount = m_PacingHordeCandidates.Count(); }
        m_HCAdoptWork.HCReset(scanCount);
        HCUnitBudget adoptionWork = HCServer.HCTickWork();
        if (!adoptionWork.HCTakeFor(HCUnitBudget.HC_WORK_INFECTED, scanCount))
        {
            // A shared tick-budget deferral is not a changed/refused offer.
            if (retryOffer)
            {
                m_PacingHordeWaiting = true;
            }
            m_HCHordeActivity.HCRefuse("budget_deferred");
            return;
        }
        for (int scanned = 0; scanned < scanCount; scanned++)
        {
            if (!m_HCAdoptWork.HCContinue())
            {
                if (retryOffer)
                {
                    m_PacingHordeWaiting = true;
                    m_HCHordeActivity.HCRefuse("budget_deferred");
                    return;
                }
                break;
            }
            HCInfectedActor actor;
            if (retryOffer)
            {
                actor = m_PacingHordeCandidates[scanned];
            }
            else
            {
                m_AdoptionCursor = m_AdoptionCursor % m_Actors.Count();
                actor = m_Actors[m_AdoptionCursor];
                m_AdoptionCursor = HCInfectedPolicy.NextAdoptionCursor(m_AdoptionCursor, m_Actors.Count());
            }
            bool eligible = actor && !actor.EverAssigned && !actor.SearchPack && actor.InfectedEntity && actor.InfectedEntity.IsAlive() && actor.Profile != "native_injured";
            if (eligible)
            {
                int mind = actor.InfectedEntity.GetMindStateSynced();
                eligible = mind != DayZInfectedConstants.MINDSTATE_CHASE && mind != DayZInfectedConstants.MINDSTATE_FIGHT;
            }
            if (!eligible)
            {
                if (retryOffer) { m_HCHordeActivity.HCRefuse("cohort_ineligible"); return; }
                continue;
            }
            vector position = actor.InfectedEntity.GetPosition();
            if (!HCInfectedStore.ValidPosition(position))
            {
                if (retryOffer) { m_HCHordeActivity.HCRefuse("cohort_position"); return; }
                continue;
            }
            if (!retryOffer && candidates.Count() == 0)
            {
                // CE activates local population; routes never use a player fix.
                anchor = position;
            }
            if (vector.DistanceSq(position, anchor) <= 10000)
                candidates.Insert(actor);
            else if (retryOffer) { m_HCHordeActivity.HCRefuse("cohort_range"); return; }
            if (candidates.Count() >= Math.Min(HCHordeLimits.MAX_PACK, m_MemberCap - m_State.Reserved))
                break;
        }
        // A retained cohort is all-or-nothing; never replace members or move its
        // anchor while waiting for the director's durable reservation barrier.
        if (retryOffer && candidates.Count() != m_PacingHordeCandidates.Count()) { m_HCHordeActivity.HCRefuse("cohort_changed"); return; }
        int requested = candidates.Count();
        HCHordeRouteDefaults limits = HCHordeRoutes.Defaults();
        if (!limits) { m_HCHordeActivity.HCRefuse("defaults_missing"); return; }
        int capacity = Math.Min(HCHordeLimits.MAX_PACK, Math.Min(limits.MaxMembers, m_MemberCap - m_State.Reserved));
        if (capacity < HCHordeLimits.MIN_PATROL || requested < 3) { m_HCHordeActivity.Add("no_seed"); return; }
        int target = m_PacingHordeTarget;
        if (!retryOffer) { target = Math.Clamp(HCInfectedMemory.CohortSize(anchor, capacity), HCHordeLimits.MIN_PATROL, capacity); }
        if (target > capacity) { m_HCHordeActivity.HCRefuse("capacity_changed"); return; }
        while (candidates.Count() > target) { candidates.Remove(candidates.Count() - 1); }
        requested = candidates.Count();
        if (requested < 1 || !HCInfectedPolicy.CanReserve(activeGroups, m_GroupCap, m_State.Reserved, m_MemberCap, target))
        {
            m_HCHordeActivity.HCRefuse("reserve_full");
            return;
        }
        HCInfectedClue adoptionClue;
        foreach (HCInfectedActor observer : candidates)
        {
            HCInfectedClue observedClue = HCHordeStimulus.ChooseClue(observer, m_Now, HeardAdmitted());
            if (HCHordeStimulus.PreferHotClue(observedClue, adoptionClue, m_Now))
            {
                adoptionClue = observedClue;
            }
        }
        // Patrols use authored corridors or CE-observed local destinations;
        // neither is a hearing receipt. Keep the chosen route across retries.
        HCHordeRouteSurvey patrol = m_PacingHordePatrol;
        if (!retryOffer && HCHordeMigration.Active() && m_Admission.HordeStimulusRoutes)
        {
            patrol = HCHordeRoutes.Select(anchor, null);
            // Outside authored corridors, use a real CE member's observed
            // position. Start must still sample and FindPath before transfer.
            if (!patrol) { patrol = HCHordeRoutes.HCLocalOffer(anchor, candidates); }
        }
        if (!m_Admission.NativePackRoutes || !patrol)
        {
            m_HCHordeActivity.Add("no_route");
            return;
        }
        HCHordeRecord record = new HCHordeRecord;
        HCHordeRecovery.Capture(candidates, record);
        if (record.RecoveryConflicted)
        {
            m_HCHordeActivity.HCRefuse("recovery_conflict");
            return;
        }
        if (!retryOffer)
        {
            m_PacingHordeId = "horde:" + nowUtc.ToString();
            m_PacingHordeCandidates.Clear();
            foreach (HCInfectedActor retained : candidates) { m_PacingHordeCandidates.Insert(retained); }
            m_PacingHordeAnchor = anchor;
            m_PacingHordeTarget = target;
            m_PacingHordePatrol = patrol;
            m_PacingHordeDeadline = m_Now + 600;
        }
        else { m_HCHordeActivity.Add("retries"); }
        m_PacingHordeAttempts++;
        // At most six passes for this fixed offer. Only after it terminates may
        // the next admission resume selection at the already advanced cursor.
        if (!HCEventModule.HCPaceSituation(m_PacingHordeId, anchor, 600))
        {
            m_PacingHordeWaiting = m_PacingHordeAttempts < 6;
            m_HCHordeActivity.Add("paced_wait");
            return;
        }
        // Never persist a partial roster or identities of supplemental bodies.
        if (requested < target) { record.MemberIds.Clear(); }
        // PREPARE: the reservation is durable before any native membership
        // transfer. A restart never replays this incomplete intent.
        record.State = 6;
        record.AdoptionStage = 1;
        record.Id = m_State.Groups.Count() + 1;
        if (reusableSlot >= 0)
        {
            record.Id = reusableSlot + 1;
        }
        record.Reserved = target;
        record.Living = requested;
        record.CreatedUtc = nowUtc;
        record.LastSignalUtc = nowUtc;
        record.Anchor = anchor;
        record.PreviousAnchor = anchor;
        m_State.Reserved += target;
        if (reusableSlot < 0)
        {
            m_State.Groups.Insert(record);
            m_Sweeps.Insert(new HCHordeSweep);
            m_Packs.Insert(null);
        }
        else
        {
            // Old living members remain native and permanently ineligible for
            // fresh adoption. Clear slot identity before assigning the new roster.
            foreach (HCInfectedActor retiredActor : m_Actors)
            {
                if (retiredActor.GroupId == record.Id)
                {
                    retiredActor.GroupId = 0;
                }
            }
            m_State.Groups[reusableSlot] = record;
            m_Sweeps[reusableSlot] = new HCHordeSweep;
            m_Packs[reusableSlot] = null;
        }
        m_Dirty = true;
        if (!SaveAdoptionBoundary("prepare"))
        {
            m_HCHordeActivity.HCRefuse("prepare_checkpoint");
            return;
        }
        int used = activeGroups + 1;
        Print("[HollowCountry] infected horde budget used=" + used.ToString() + "/" + m_GroupCap.ToString());
        foreach (HCInfectedActor candidate : candidates)
        {
            candidate.GroupId = record.Id;
            candidate.EverAssigned = true;
        }
        ResetSweep();
        HCNativeInfectedPack pack;
        bool attempted = m_Admission.NativePackRoutes;
        bool succeeded = false;
        bool releasing = false;
        if (attempted)
        {
            pack = new HCNativeInfectedPack;
            m_Packs[record.Id - 1] = pack;
            float routeNow = HCInfectedClock.UtcSeconds() - m_StartedUtc;
            if (patrol)
            {
                // Native-checked CE seed; the reserved shortfall is staged at entry.
                vector entry = patrol.Nodes[0];
                vector last = patrol.Nodes[patrol.Nodes.Count() - 1];
                if (vector.DistanceSq(anchor, last) < vector.DistanceSq(anchor, entry)) { entry = last; }
                succeeded = pack.Start(candidates, entry, false, routeNow, routeNow + 600);
                if (succeeded && !pack.IsReleasing()) { succeeded = pack.HCAdmitPatrol(patrol, record.Id, routeNow, target); }
                if (!succeeded) { pack.Release(); }
            }
            else if (adoptionClue && adoptionClue.IsLive(routeNow))
                succeeded = pack.Start(candidates, adoptionClue.Origin, false, routeNow, adoptionClue.Expires);
            succeeded = succeeded && !pack.IsReleasing();
            releasing = pack.IsReleasing();
        }
        if (succeeded) { HCHordeRoutes.HCActivity().Add("native_admitted"); }
        else { HCHordeRoutes.HCActivity().Add("native_refused"); }
        if (succeeded)
        {
            HCEventModule.HCStartedSituation(m_PacingHordeId);
            m_HCHordeActivity.Add("started");
        }
        else
        {
            HCEventModule.HCCancelSituation(m_PacingHordeId);
            m_HCHordeActivity.Add("failed");
        }
        record.AdoptionStage = HCInfectedPolicy.AdoptionOutcome(true, attempted, succeeded, releasing);
        if (record.AdoptionStage == 2)
        {
            record.State = 0;
            if (pack)
            {
                SnapshotRoute(record, pack);
            }
        }
        else
        {
            record.State = 6;
            record.RecoveryConflicted = true;
            record.HCStopRoute();
            if (!m_FailedCohorts.Contains(record.Id))
            {
                m_FailedCohorts.Insert(record.Id, true);
            }
        }
        m_Dirty = true;
        if (!SaveAdoptionBoundary("outcome"))
            return;
        if (record.AdoptionStage != 2)
        {
            // not_started: Start was never called (routes off, clue no longer live);
            // none: Start ran and left an empty reason.
            string packReason = "not_started";
            if (pack && pack.HCStartRan())
            {
                packReason = "none";
                if (pack.HCRefusalReason() != "")
                    packReason = pack.HCRefusalReason();
            }
            Print("[HollowCountry] infected cohort quarantined id=" + record.Id.ToString() + " reason=adoption_transfer_failed_or_ambiguous pack_reason=" + packReason + " reservation=retained");
        }
        // CE members are never deleted or moved by script. Reinforcement owns only its creations.
    }

    // The single heard-clue gate: chains must be requested AND qualified.
    protected bool HeardAdmitted()
    {
        return m_Chains && m_Admission.SupplementaryChains;
    }

    // Pack-route refusal reason from HCNativeInfectedPack.HCRefusalReason(): logged
    // once per change (site + reason); an empty reason (a success) re-arms the log.
    protected void HCNoteRouteRefusal(string site, string reason)
    {
        if (reason == "")
        {
            m_LastRouteRefusal = "";
            return;
        }
        string key = site + ":" + reason;
        if (m_LastRouteRefusal == key)
            return;
        m_LastRouteRefusal = key;
        Print("[HC Infected] " + site + " pack route refused reason=" + reason + " runtime=PENDING");
    }

    protected void TryInvestigate(HCInfectedActor actor)
    {
        // One selector for every consumer: a qualified live visual clue wins, an
        // admitted external heard cue is next, retained memory never routes.
        int stimulusReason;
        bool admitHeard = HeardAdmitted() && actor.HeardExternally;
        HCInfectedClue clue = HCHordeStimulus.SelectClue(actor.Visual, actor.Heard, admitHeard, m_Now, stimulusReason);
        if (!clue)
            return;
        bool observedClue = clue != null;
        int mind = actor.InfectedEntity.GetMindStateSynced();
        bool engaged = mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT;
        bool grouped = actor.GroupId > 0 || actor.SearchPack != null;
        if (!HCInfectedPolicy.MayInvestigate(m_Admission.Investigation, observedClue, engaged, actor.Profile == "native_injured", grouped, actor.SearchAttempts, m_Now, actor.NextSearch))
            return;
        if (m_RoutesRemaining < 1 || m_Investigators.Count() >= m_Config.MaxInvestigators)
            return;
        m_RoutesRemaining--;
        actor.SearchAttempts++;
        actor.NextSearch = m_Now + 10;
        ref array<HCInfectedActor> single = new array<HCInfectedActor>;
        single.Insert(actor);
        HCNativeInfectedPack pack = new HCNativeInfectedPack;
        // Frozen direct observation or actual emitted local voice, never a
        // current hidden target. Investigation cannot extend root lifetime.
        float expires = Math.Min(clue.Expires, m_Now + 15);
        if (pack.Start(single, clue.Origin, true, m_Now, expires))
        {
            HCNoteRouteRefusal("investigate", "");
            actor.SearchPack = pack;
            m_Investigators.Insert(actor);
        }
        else
        {
            HCNoteRouteRefusal("investigate", pack.HCRefusalReason());
        }
    }

    protected void ReleasePacks()
    {
        // Finish: Release() (HCInfectedNavigation.c) skips native work itself; the route
        // records below still clear so the shutdown save runs (Opus review, #375).
        foreach (HCNativeInfectedPack pack : m_Packs)
        {
            if (pack)
                pack.Release();
        }
        foreach (HCInfectedActor actor : m_Actors)
        {
            if (actor.SearchPack)
            {
                actor.SearchPack.Release();
                actor.SearchPack = null;
            }
        }
        m_Investigators.Clear();
        // Only an admitted lifecycle owns route intent; a dormant journal keeps
        // its stored route fields untouched.
        int routeRecords = 0;
        if (m_State && (m_Admission.CEAdoption || m_Admission.MemberRecovery))
            routeRecords = Math.Min(m_State.Groups.Count(), m_Packs.Count());
        for (int r = 0; r < routeRecords; r++)
        {
            HCHordeRecord routeRecord = m_State.Groups[r];
            if (routeRecord.State == 6 && !m_Admission.MemberRecovery && !m_Packs[r])
                continue;
            if (routeRecord.HasRoute)
            {
                routeRecord.HasRoute = false;
                routeRecord.RouteResult = 5;
                m_Dirty = true;
            }
        }
    }

    override void OnTick(float deltaTime)
    {
        HCNativeInfectedPack.RetryPendingReleases();
        HCEcologyMigration.Tick();
        if (!m_Healthy || !GetGame().IsServer())
            return;
        int nowUtc = HCInfectedClock.UtcSeconds();
        if (nowUtc <= 0 || nowUtc < m_LastUtc || !(deltaTime > 0 && deltaTime <= 300))
        {
            Quarantine("clock rollback or invalid tick");
            return;
        }
        if (m_RegistrationRound >= 2000000000)
        {
            Quarantine("registration round exhausted");
            return;
        }
        m_RegistrationRound++;
        m_LastUtc = nowUtc;
        m_Now = nowUtc - m_StartedUtc;
        HCHordeReinforce.HCBeginTick();
        m_HCHordeActivity.Report("tracked=" + m_Actors.Count().ToString() + " reserved=" + m_State.Reserved.ToString());
        m_VoiceAttempts = 0;
        m_RegistrationAttempts = 0;
        HCInfectedRoomCatalog.BeginTick();
        m_ObservationsRemaining = 1;
        m_RoutesRemaining = 1;
        bool adoptionDue = m_Hordes && m_Now >= m_NextAdopt;
        int maintenance = m_Investigators.Count();
        int packSlots = 0;
        if (m_Admission.CEAdoption || m_Admission.MemberRecovery)
            packSlots = m_Packs.Count();
        // One physical pack per non-adoption tick, round-robin. Charge its complete <=MAX_PACK
        // member sweep before starting; the native call is not preemptible.
        int packTick = -1;
        if (packSlots > 0)
        {
            packTick = m_HCPackTickCursor % packSlots;
            m_HCPackTickCursor = (packTick + 1) % packSlots;
        }
        HCUnitBudget packWork = HCServer.HCTickWork();
        for (int p = 0; p < packSlots; p++)
        {
            HCHordeRecord record = m_State.Groups[p];
            // A pending (state 6) journal with no runtime pack is evidence for
            // member recovery. Without that path admitted it is neither retired,
            // marked dirty nor saved.
            if (record.State == 6 && !m_Admission.MemberRecovery && !m_Packs[p])
                continue;
            maintenance++;
            // Absolute lifetime cannot depend on finishing an actor sweep:
            // continuous CE registration can reset a partial aggregate.
            if (record.State != 5 && record.State != 6 && nowUtc - record.CreatedUtc >= 3600)
            {
                record.State = 5;
                m_Dirty = true;
            }
            if (record.State == 5)
            {
                RefundRetired(record, nowUtc);
                continue;
            }
            if (!adoptionDue && m_Packs[p] && p == packTick && packWork.HCTakeFor(HCUnitBudget.HC_WORK_INFECTED, record.Reserved))
            {
                maintenance += record.Reserved;
                bool routeAlive = m_Packs[p].Tick(m_Now);
                SnapshotRoute(record, m_Packs[p]);
                if (!routeAlive)
                {
                    m_Packs[p] = null;
                    // A released/despawned/wiped cohort no longer owns a
                    // runtime route. Retire and refund rather than leak escrow.
                    if (record.State != 6)
                    {
                        record.State = 5;
                        RefundRetired(record, nowUtc);
                    }
                }
            }
            if (record.HasRoute && (!m_Packs[p] || m_Packs[p].IsReleasing()))
            {
                record.HCStopRoute();
                m_Dirty = true;
            }
        }
        // Search expiry is checked every core tick, independent of the actor
        // sampling cursor, with at most two native packs to inspect. A queued
        // room segment shares the tick's single route token (one FindPath per
        // tick) and waits while adoption, which may start a route, is due.
        for (int s = m_Investigators.Count() - 1; s >= 0; s--)
        {
            HCInfectedActor investigator = m_Investigators[s];
            if (!investigator.SearchPack || !investigator.SearchPack.Tick(m_Now))
            {
                investigator.SearchPack = null;
                m_Investigators.Remove(s);
            }
            else if (!adoptionDue && m_RoutesRemaining > 0 && investigator.SearchPack.ExtendRoute())
            {
                m_RoutesRemaining--;
            }
        }
        bool adopted = false;
        if (adoptionDue)
        {
            // Adoption gets its own bounded tick rather than doubling scan work.
            adopted = true;
            TryAdopt(nowUtc);
            m_NextAdopt = m_Now + m_Config.SaveIntervalSeconds;
        }
        else
        {
            // Actor sampling resumes its cursor after the charged member sweep.
            // At most one native path token is shared by all route consumers.
            int retargetReserve = 0;
            if (m_Hordes && m_Admission.HordeStimulusRoutes)
                retargetReserve = 2;
            int work = m_WorkCap - 2 - maintenance - retargetReserve;
            if (m_Hordes && m_Admission.MemberRecovery && m_Actors.Count() > 0 && work > 1)
            {
                // Dedicated cursor: the first actor in a completed sweep must
                // not monopolize the one-per-tick reconciliation allowance.
                m_RecoveryCursor = m_RecoveryCursor % m_Actors.Count();
                HCInfectedActor recovering = m_Actors[m_RecoveryCursor];
                m_RecoveryCursor = HCInfectedPolicy.NextAdoptionCursor(m_RecoveryCursor, m_Actors.Count());
                if (HCHordeRecovery.Reconcile(recovering, m_State, m_Actors, true, nowUtc))
                    m_Dirty = true;
                work--;
            }
            if (m_Chains && m_Admission.SupplementaryChains && work > 2)
            {
                // Leave an actor slot so a sustained voice stream cannot starve
                // observations/recovery/expiry. One recipient costs <=2 rays.
                int alertWork = Math.Min(2, (work - 1) / 3);
                work -= m_AlertChain.ProcessPending(m_Actors, m_Now, alertWork) * 3;
            }
            int voices = Math.Min(m_Config.MaxVoicePerTick, work / 2);
            while (voices > 0 && m_Voices.Count() > 0)
            {
                HCInfectedVoice voice = m_Voices[0];
                m_Voices.RemoveOrdered(0);
                HCInfectedActor actor = FindActor(voice.Emitter);
                if (actor && actor.InfectedEntity && actor.InfectedEntity.IsAlive() && voice.Clue.IsLive(m_Now))
                    actor.Clue = voice.Clue;
                voices--;
                work--;
            }
            // Wave 13 (#138): each sampled actor also takes one unit from the shared core-tick
            // budget (own cap above stays). A refused request leaves m_Cursor on that actor; the
            // sweep resumes there next tick (HCUnitBudget forces one item per consumer per tick).
            HCUnitBudget sharedWork = HCServer.HCTickWork();
            while (work > 0 && m_Cursor < m_Actors.Count() && sharedWork.HCTakeFor(HCUnitBudget.HC_WORK_INFECTED, 1))
            {
                SampleActor(m_Actors[m_Cursor]);
                HCReached.Mark("infected.actor_sample");
                m_Cursor++;
                work--;
            }
            if (m_Cursor >= m_Actors.Count())
                FinishSweep(nowUtc);
        }
        // A save due on an adoption tick waits one tick (state stays dirty).
        if (m_Hordes && m_Dirty && !adopted && m_Now >= m_NextSave)
        {
            m_SaveJob.HCDirty = true;
            // A refused registration still advances at most one staged operation.
            m_NextSave = m_Now + m_Config.SaveIntervalSeconds;
        }
        if (m_SaveJob && !HCSaveScheduler.HCRegistered(m_SaveJob) && (m_SaveJob.HCDirty || m_SaveJob.HCInFlight))
        {
            m_SaveJob.HCStep();
        }
    }

    override void OnStop()
    {
        if (m_PacingHordeId != "") { HCEventModule.HCCancelSituation(m_PacingHordeId); }
        m_PacingHordeId = "";
        m_PacingHordeAttempts = 0;
        m_PacingHordeWaiting = false;
        m_PacingHordeCandidates.Clear();
        m_PacingHordeAnchor = vector.Zero;
        m_PacingHordeTarget = 0;
        m_PacingHordePatrol = null;
        m_PacingHordeDeadline = 0;
        m_HCHordeActivity.Report("stopped", true);
        HCInfectedVisionQualification.HCThreatReset(false);
        ReleasePacks();
        if (m_Healthy && m_Hordes && m_Dirty && GetGame().IsServer())
        {
            SaveAdoptionBoundary("shutdown");
        }
        if (m_SaveJob)
        {
            if (m_Healthy && (m_SaveJob.HCDirty || m_SaveJob.HCInFlight)) { HCSaveScheduler.HCFlush(m_SaveJob); }
            HCSaveScheduler.HCUnregister(m_SaveJob);
            m_SaveJob.HCDetach();
            m_SaveJob = null;
        }
        if (Instance == this)
            Instance = null;
        m_Healthy = false;
        m_HCOwnerStatus.HCPublish("off", "infected_owner_stopped");
        m_NativeVariants = null;
        m_Voices.Clear();
        m_Actors.Clear();
        m_Sweeps.Clear();
        m_Packs.Clear();
        m_FailedCohorts.Clear();
        HCInfectedRoomCatalog.Clear();
        m_AlertChain = new HCAlertChain;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCInfectedModule);
    }
}

// Shared scheduler owns routine writes; HCFlush is reserved for the explicit
// adoption/shutdown durability barriers above. The image text is immutable.
class HCInfectedSaveJob : HCSaveJob
{
    protected HCInfectedModule m_Owner;
    protected ref HCStagedSaveImage m_Image;
    protected bool m_Failed;

    override string HCName() { return "Infected"; }
    void HCBind(HCInfectedModule owner) { m_Owner = owner; }
    void HCDetach() { m_Owner = null; }

    override int HCStep()
    {
        if (m_Failed || !m_Owner) { return STEP_FAILED; }
        int result = STEP_MORE;
        if (!m_Image)
        {
            m_Image = new HCStagedSaveImage;
            if (!m_Owner.HCBeginCheckpoint(m_Image)) { result = STEP_FAILED; }
            this.HCInFlight = true;
        }
        else
        {
            result = m_Image.HCStepImage();
        }
        if (result == STEP_DONE)
        {
            m_Image = null;
            this.HCDirty = false;
            this.HCInFlight = false;
        }
        if (result == STEP_FAILED)
        {
            m_Failed = true;
            this.HCDirty = false;
            this.HCInFlight = false;
            m_Owner.HCCheckpointFailed();
        }
        return result;
    }
}
