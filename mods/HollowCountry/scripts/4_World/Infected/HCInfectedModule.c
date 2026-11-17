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
    protected ref HCInfectedSnapshot m_State;
    protected ref array<ref HCInfectedActor> m_Actors = new array<ref HCInfectedActor>;
    protected ref array<ref HCInfectedVoice> m_Voices = new array<ref HCInfectedVoice>;
    protected ref array<ref HCHordeSweep> m_Sweeps = new array<ref HCHordeSweep>;
    protected ref array<ref HCNativeInfectedPack> m_Packs = new array<ref HCNativeInfectedPack>;
    protected ref array<ref HCInfectedActor> m_Investigators = new array<ref HCInfectedActor>;
    protected ref HCAlertChain m_AlertChain = new HCAlertChain;
    protected bool m_Healthy;
    protected bool m_Hordes;
    protected bool m_Chains;
    protected bool m_Dirty;
    protected int m_WorkCap;
    protected int m_GroupCap;
    protected int m_MemberCap;
    protected int m_Cursor;
    protected int m_AdoptionCursor;
    protected int m_RecoveryCursor;
    protected int m_RetargetCursor;
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
        m_WorkCap = Math.Min(settings.MaxTickWorkItems, 32);
        if ((settings.EnableHordes || m_Config.EnableNativePackRoutes || m_Config.EnableInvestigation) && m_WorkCap < 8)
        {
            Quarantine("hordes/routing require at least eight bounded work items");
            return;
        }
        if (settings.EnableHordes && m_Config.EnableCEAdoption && !HCInfectedPolicy.AdoptionWorkReady(m_WorkCap))
        {
            Quarantine("cohort adoption requires work budget at least 9");
            return;
        }
        if (settings.EnableHordes && m_Config.EnableHordeStimulusRoutes && m_WorkCap < 24)
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
        if (m_Config.EnableNativePackRoutes || m_Config.EnableInvestigation)
        {
            bool packReady = GetGame().GetWorld() && GetGame().GetWorld().GetAIWorld();
            packReady = packReady && GetGame().ConfigIsExisting("GroupBehaviourTemplates DZInfectedPackBeh");
            if (!packReady)
            {
                Quarantine("native pack routing prerequisites unavailable");
                return;
            }
        }
        bool variantMaps = HCInfectedProfiles.ValidateMap(m_Config.CivilianVariants, true);
        variantMaps = variantMaps && HCInfectedProfiles.ValidateMap(m_Config.MilitaryVariants, true);
        if (m_Config.EnableVariantPolicies && !variantMaps)
        {
            Print("[HC Infected] variant preference enabled; explicit stance maps missing; native profiles retained");
        }
        if (m_Config.EnableContactGuard && !HCInfectedProfiles.ContactGuardQualified())
            Print("[HC Infected] contact guard pending native wall-hit qualification; native combat retained");
        Print("[HC Infected] enabled-preference template defaults; existing explicit disables preserved");
        m_GroupCap = Math.Min(settings.MaxActiveHordes, 2);
        m_MemberCap = Math.Min(settings.MaxActiveHordeMembers, 24);
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
            if (!HCInfectedStore.Load(m_State, GetGame().GetWorldName(), m_MemberCap, m_GroupCap, m_LastUtc))
            {
                Quarantine("state/schema/build/world/clock mismatch; no fallback or reset");
                return;
            }
            foreach (HCHordeRecord group : m_State.Groups)
            {
                m_Sweeps.Insert(new HCHordeSweep);
                m_Packs.Insert(null);
            }
            m_Dirty = true;
        }
        m_Healthy = true;
        Instance = this;
        m_NextSave = m_Config.SaveIntervalSeconds;
        m_NextAdopt = m_Config.SaveIntervalSeconds;
#ifdef DIAG_DEVELOPER
        if (m_Config.RunPolicySelfTests && !HCInfectedSelfTests.Run())
            Quarantine("scalar policy selftest failed");
#endif
        Print("[HC Infected] source installed; optional native pack routing; no materialization; runtime acceptance pending");
    }

    protected void Quarantine(string reason)
    {
        m_Healthy = false;
        if (Instance == this)
            Instance = null;
        ReleasePacks();
        Print("[HC Infected] disabled: " + reason);
    }

    bool ContactGuardEnabled()
    {
        return m_Healthy && m_Config.EnableContactGuard && HCInfectedProfiles.ContactGuardQualified() && GetGame().IsServer();
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
        int slot = -1;
        for (int i = 0; i < m_Actors.Count(); i++)
        {
            if (CanRecycleActor(m_Actors[i]) && (!m_Actors[i].InfectedEntity || !m_Actors[i].InfectedEntity.IsAlive()))
            {
                slot = i;
                break;
            }
        }
        if (slot < 0 && m_Actors.Count() >= Math.Min(m_Config.MaxTracked, m_MemberCap))
            return false;
        HCInfectedActor actor = new HCInfectedActor;
        actor.InfectedEntity = entity;
        actor.InitializeProfile(m_Config);
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
        if (m_Config.EnableSupplementaryChains)
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
            if (m_Config.EnableInvestigation && m_ObservationsRemaining > 0 && m_Now >= actor.NextVisualSample)
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
        bool hearing = m_Chains && m_Config.EnableSupplementaryChains;
        HCInfectedClue sensed = HCHordeStimulus.ChooseClue(actor, m_Now, hearing);
        if (HCHordeStimulus.PreferClue(sensed, sweep.Stimulus, m_Now))
            sweep.Stimulus = sensed;
        int mind = actor.InfectedEntity.GetMindStateSynced();
        if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT)
            sweep.Engaged = true;
    }

    protected void FinishSweep(int nowUtc)
    {
        for (int i = 0; i < m_Sweeps.Count(); i++)
        {
            HCHordeRecord record = m_State.Groups[i];
            HCHordeSweep sweep = m_Sweeps[i];
            if (record.State == 5)
                continue;
            if (record.State != 5 && record.State != 6)
            {
                if (!HCInfectedPolicy.CompleteMembership(record.Reserved, sweep.Living, sweep.ConfirmedDead, sweep.Accounted, sweep.Ambiguous))
                {
                    record.State = 6;
                    record.RecoveryConflicted = true;
                    record.HasRoute = false;
                    if (m_Packs[i])
                    {
                        m_Packs[i].Release();
                        SnapshotRoute(record, m_Packs[i]);
                        m_Packs[i] = null;
                    }
                    m_Dirty = true;
                    Print("[HC Infected] ambiguous membership; reservation retained for horde " + record.Id);
                }
            }
            sweep.Clue = sweep.Stimulus && sweep.Stimulus.IsLive(m_Now);
            int living = sweep.Living;
            if (record.State == 6)
                living = record.Living; // Unresolved is not evidence of death.
            if (sweep.Engaged || sweep.Clue)
                record.LastSignalUtc = nowUtc;
            int next = HCInfectedPolicy.NextHordeState(record.State, living, sweep.Clue, sweep.Engaged, nowUtc - record.LastSignalUtc, nowUtc - record.CreatedUtc);
            if (next != record.State)
            {
                Print("[HC Infected] horde " + record.Id + " state " + record.State + " -> " + next);
                record.State = next;
                m_Dirty = true;
            }
            if (record.State == 5 && m_Packs[i])
            {
                m_Packs[i].Release();
                SnapshotRoute(record, m_Packs[i]);
                m_Packs[i] = null;
                record.HasRoute = false;
                m_Dirty = true;
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
            if (!sweep.Clue || !sweep.Stimulus.IsLive(m_Now))
            {
                continue;
            }
            int result = pack.Retarget(sweep.Stimulus, m_Now);
            // 0=pre-path rejection; 1=path attempted/failed; 2=accepted.
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

    protected bool SaveAdoptionBoundary(string boundary)
    {
        // Close/readback is the inspected native guarantee available here.
        // It is not an fsync or atomic native CE/group transaction.
        if (!HCInfectedStore.Save(m_State, m_MemberCap, m_GroupCap))
        {
            Quarantine("adoption " + boundary + " write/readback failed; preserving spent intent");
            return false;
        }
        m_Dirty = false;
        m_NextSave = m_Now + m_Config.SaveIntervalSeconds;
        return true;
    }

    protected void TryAdopt(int nowUtc)
    {
        if (!HCInfectedPolicy.AdoptionWorkReady(m_WorkCap)) return;
        if (!m_Hordes || !m_Config.EnableCEAdoption || m_State.Groups.Count() >= m_GroupCap)
            return;
        foreach (HCHordeRecord pending : m_State.Groups)
        {
            // Restored members must never be adopted as a fresh population while
            // a prior reservation is unresolved. Retirement never refunds it.
            if (pending.State == 6)
                return;
        }
        ref array<HCInfectedActor> candidates = new array<HCInfectedActor>;
        vector anchor;
        int scanCount = Math.Min(m_Actors.Count(), m_WorkCap - 6);
        for (int scanned = 0; scanned < scanCount; scanned++)
        {
            m_AdoptionCursor = m_AdoptionCursor % m_Actors.Count();
            HCInfectedActor actor = m_Actors[m_AdoptionCursor];
            m_AdoptionCursor = HCInfectedPolicy.NextAdoptionCursor(m_AdoptionCursor, m_Actors.Count());
            if (actor.EverAssigned || actor.SearchPack || !actor.InfectedEntity || !actor.InfectedEntity.IsAlive() || actor.Profile == "native_injured")
                continue;
            int mind = actor.InfectedEntity.GetMindStateSynced();
            if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT)
                continue;
            vector position = actor.InfectedEntity.GetPosition();
            if (!HCInfectedStore.ValidPosition(position))
                continue;
            if (candidates.Count() == 0)
                anchor = position;
            if (vector.DistanceSq(position, anchor) <= 1600)
                candidates.Insert(actor);
            if (candidates.Count() == 6)
                break;
        }
        int requested = candidates.Count();
        if (requested < 3 || !HCInfectedPolicy.CanReserve(m_State.Groups.Count(), m_GroupCap, m_State.Reserved, m_MemberCap, requested))
            return;
        HCInfectedClue adoptionClue;
        foreach (HCInfectedActor observer : candidates)
        {
            HCInfectedClue observedClue = HCHordeStimulus.ChooseClue(observer, m_Now, m_Chains && m_Config.EnableSupplementaryChains);
            if (HCHordeStimulus.PreferClue(observedClue, adoptionClue, m_Now))
                adoptionClue = observedClue;
        }
        // No invented migration destination: without a genuine cue, leave the
        // existing CE population in its native group and try a later interval.
        if (m_Config.EnableNativePackRoutes && !adoptionClue)
            return;
        HCHordeRecord record = new HCHordeRecord;
        HCHordeRecovery.Capture(candidates, record);
        if (record.RecoveryConflicted)
            return;
        // PREPARE: the reservation is durable before any native membership
        // transfer. A restart never replays this incomplete intent.
        record.State = 6;
        record.AdoptionStage = 1;
        record.Id = m_State.Groups.Count() + 1;
        record.Reserved = requested;
        record.Living = requested;
        record.CreatedUtc = nowUtc;
        record.LastSignalUtc = nowUtc;
        record.Anchor = anchor;
        record.PreviousAnchor = anchor;
        m_State.Reserved += requested;
        m_State.Groups.Insert(record);
        m_Sweeps.Insert(new HCHordeSweep);
        m_Packs.Insert(null);
        m_Dirty = true;
        if (!SaveAdoptionBoundary("prepare"))
            return;
        foreach (HCInfectedActor candidate : candidates)
        {
            candidate.GroupId = record.Id;
            candidate.EverAssigned = true;
        }
        ResetSweep();
        HCNativeInfectedPack pack;
        bool attempted = m_Config.EnableNativePackRoutes;
        bool succeeded = false;
        bool releasing = false;
        if (attempted)
        {
            pack = new HCNativeInfectedPack;
            m_Packs[record.Id - 1] = pack;
            float routeNow = HCInfectedClock.UtcSeconds() - m_StartedUtc;
            if (adoptionClue.IsLive(routeNow))
                succeeded = pack.Start(candidates, adoptionClue.Origin, false, routeNow, adoptionClue.Expires);
            releasing = pack.IsReleasing();
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
            record.HasRoute = false;
        }
        m_Dirty = true;
        if (!SaveAdoptionBoundary("outcome"))
            return;
        if (record.AdoptionStage != 2)
            Quarantine("adoption transfer failed or ambiguous; durable reservation retained");
        // Native entities are never spawned, deleted or moved by script.
    }

    protected void TryInvestigate(HCInfectedActor actor)
    {
        HCInfectedClue clue;
        if (actor.Visual && actor.Visual.Provenance == 2 && actor.Visual.IsLive(m_Now))
            clue = actor.Visual;
        if (m_Chains && m_Config.EnableSupplementaryChains && actor.HeardExternally && actor.Heard)
        {
            if (actor.Heard.Provenance == 1 && actor.Heard.IsLive(m_Now))
            {
                if (!clue || actor.Heard.Observed > clue.Observed)
                    clue = actor.Heard;
            }
        }
        bool observedClue = clue != null;
        int mind = actor.InfectedEntity.GetMindStateSynced();
        bool engaged = mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT;
        bool grouped = actor.GroupId > 0 || actor.SearchPack != null;
        if (!HCInfectedPolicy.MayInvestigate(m_Config.EnableInvestigation, observedClue, engaged, actor.Profile == "native_injured", grouped, actor.SearchAttempts, m_Now, actor.NextSearch))
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
            actor.SearchPack = pack;
            m_Investigators.Insert(actor);
        }
    }

    protected void ReleasePacks()
    {
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
        if (m_State)
        {
            foreach (HCHordeRecord record : m_State.Groups)
            {
                if (record.HasRoute)
                {
                    record.HasRoute = false;
                    record.RouteResult = 5;
                    m_Dirty = true;
                }
            }
        }
    }

    override void OnTick(float deltaTime)
    {
        HCNativeInfectedPack.RetryPendingReleases();
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
        m_VoiceAttempts = 0;
        m_RegistrationAttempts = 0;
        m_ObservationsRemaining = 1;
        m_RoutesRemaining = 1;
        int maintenance = m_Investigators.Count();
        for (int p = 0; p < m_Packs.Count(); p++)
        {
            maintenance++;
            // Absolute lifetime cannot depend on finishing an actor sweep:
            // continuous CE registration can reset a partial aggregate.
            HCHordeRecord record = m_State.Groups[p];
            if (record.State != 5 && nowUtc - record.CreatedUtc >= 3600)
            {
                record.State = 5;
                m_Dirty = true;
                if (m_Packs[p])
                {
                    m_Packs[p].Release();
                    SnapshotRoute(record, m_Packs[p]);
                    m_Packs[p] = null;
                }
            }
            if (m_Packs[p])
            {
                bool routeAlive = m_Packs[p].Tick(m_Now);
                SnapshotRoute(record, m_Packs[p]);
                if (!routeAlive)
                    m_Packs[p] = null;
            }
            if (record.HasRoute && (!m_Packs[p] || m_Packs[p].IsReleasing()))
            {
                record.HasRoute = false;
                m_Dirty = true;
            }
        }
        // Search expiry is checked every core tick, independent of the actor
        // sampling cursor, with at most two native packs to inspect.
        for (int s = m_Investigators.Count() - 1; s >= 0; s--)
        {
            HCInfectedActor investigator = m_Investigators[s];
            if (!investigator.SearchPack || !investigator.SearchPack.Tick(m_Now))
            {
                investigator.SearchPack = null;
                m_Investigators.Remove(s);
            }
        }
        if (m_Hordes && m_Now >= m_NextAdopt)
        {
            // Adoption gets its own bounded tick rather than doubling scan work.
            TryAdopt(nowUtc);
            m_NextAdopt = m_Now + m_Config.SaveIntervalSeconds;
        }
        else
        {
            // At most two cohort eligibility scans (six members each), plus
            // one charged bounded path. Rejections cannot starve another pack.
            int retargetReserve = 0;
            if (m_Hordes && m_Config.EnableHordeStimulusRoutes)
                retargetReserve = 16;
            int work = m_WorkCap - 2 - maintenance - retargetReserve;
            if (m_Hordes && m_Config.EnableMemberRecovery && m_Actors.Count() > 0 && work > 1)
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
            if (m_Chains && m_Config.EnableSupplementaryChains && work > 2)
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
                m_Voices.Remove(0);
                HCInfectedActor actor = FindActor(voice.Emitter);
                if (actor && actor.InfectedEntity && actor.InfectedEntity.IsAlive() && voice.Clue.IsLive(m_Now))
                    actor.Clue = voice.Clue;
                voices--;
                work--;
            }
            while (work > 0 && m_Cursor < m_Actors.Count())
            {
                SampleActor(m_Actors[m_Cursor]);
                m_Cursor++;
                work--;
            }
            if (m_Cursor >= m_Actors.Count())
                FinishSweep(nowUtc);
        }
        if (m_Hordes && m_Dirty && m_Now >= m_NextSave)
        {
            if (!HCInfectedStore.Save(m_State, m_MemberCap, m_GroupCap))
            {
                Quarantine("snapshot write/readback failed; preserving state");
                return;
            }
            m_Dirty = false;
            m_NextSave = m_Now + m_Config.SaveIntervalSeconds;
        }
    }

    override void OnStop()
    {
        ReleasePacks();
        if (m_Healthy && m_Hordes && m_Dirty && GetGame().IsServer())
        {
            if (!HCInfectedStore.Save(m_State, m_MemberCap, m_GroupCap))
                Quarantine("shutdown snapshot failed");
        }
        if (Instance == this)
            Instance = null;
        m_Healthy = false;
        m_Voices.Clear();
        m_Actors.Clear();
        m_Sweeps.Clear();
        m_Packs.Clear();
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
