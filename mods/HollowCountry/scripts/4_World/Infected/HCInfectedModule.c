class HCHordeSweep
{
    int Living;
    vector Sum;
    bool Clue;
    bool Engaged;

    void Clear()
    {
        Living = 0;
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
    protected bool m_Healthy;
    protected bool m_Hordes;
    protected bool m_Chains;
    protected bool m_Dirty;
    protected int m_WorkCap;
    protected int m_GroupCap;
    protected int m_MemberCap;
    protected int m_Cursor;
    protected int m_AdoptionCursor;
    protected int m_VoiceAttempts;
    protected int m_RegistrationAttempts;
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
            Quarantine("cannot create default-off config");
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
        return m_Healthy && m_Config.EnableContactGuard && GetGame().IsServer();
    }

    protected HCInfectedActor FindActor(ZombieBase entity)
    {
        foreach (HCInfectedActor actor : m_Actors)
        {
            if (actor.Entity == entity)
                return actor;
        }
        return null;
    }

    void Track(ZombieBase entity)
    {
        if (!m_Healthy || !GetGame().IsServer() || !entity || !entity.IsAlive())
            return;
        m_RegistrationAttempts++;
        if (m_RegistrationAttempts > m_WorkCap || FindActor(entity))
            return;
        int slot = -1;
        for (int i = 0; i < m_Actors.Count(); i++)
        {
            if (!m_Actors[i].Entity || !m_Actors[i].Entity.IsAlive())
            {
                slot = i;
                break;
            }
        }
        if (slot < 0 && m_Actors.Count() >= Math.Min(m_Config.MaxTracked, m_MemberCap))
            return;
        HCInfectedActor actor = new HCInfectedActor;
        actor.Entity = entity;
        actor.RefreshProfile();
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
        Track(entity);
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
        // super.ProcessSoundVoiceEvent already delivered the native hearing
        // signal. Never synthesize a second sound or assign remote recipients.
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
        if (!actor.Entity || !actor.Entity.IsAlive())
            return;
        actor.RefreshProfile();
        if (m_Config.EnableInvestigation && m_ObservationsRemaining > 0 && m_Now >= actor.NextVisualSample)
        {
            HCInfectedObservation.SampleVisual(actor, m_Now);
            actor.NextVisualSample = m_Now + Math.Max(2, m_Actors.Count());
            m_ObservationsRemaining--;
        }
        TryInvestigate(actor);
        if (!m_Hordes || actor.GroupId < 1 || actor.GroupId > m_Sweeps.Count())
            return;
        HCHordeRecord record = m_State.Groups[actor.GroupId - 1];
        if (record.State == 5 || record.State == 6)
            return;
        vector position = actor.Entity.GetPosition();
        if (!HCInfectedStore.ValidPosition(position))
            return;
        HCHordeSweep sweep = m_Sweeps[actor.GroupId - 1];
        sweep.Living++;
        sweep.Sum = sweep.Sum + position;
        if (actor.Clue && actor.Clue.IsLive(m_Now))
            sweep.Clue = true;
        int mind = actor.Entity.GetMindStateSynced();
        if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT)
            sweep.Engaged = true;
    }

    protected void FinishSweep(int nowUtc)
    {
        for (int i = 0; i < m_Sweeps.Count(); i++)
        {
            HCHordeRecord record = m_State.Groups[i];
            HCHordeSweep sweep = m_Sweeps[i];
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
                    vector centroid = sweep.Sum / living;
                    if (vector.DistanceSq(record.Anchor, centroid) > 25)
                    {
                        record.PreviousAnchor = record.Anchor;
                        record.Anchor = centroid;
                        m_Dirty = true;
                    }
                }
            }
        }
        ResetSweep();
    }

    protected void TryAdopt(int nowUtc)
    {
        if (!HCInfectedPolicy.AdoptionWorkReady(m_WorkCap)) return;
        if (!m_Hordes || !m_Config.EnableCEAdoption || m_State.Groups.Count() >= m_GroupCap)
            return;
        ref array<HCInfectedActor> candidates = new array<HCInfectedActor>;
        vector anchor;
        int scanCount = Math.Min(m_Actors.Count(), m_WorkCap - 6);
        for (int scanned = 0; scanned < scanCount; scanned++)
        {
            m_AdoptionCursor = m_AdoptionCursor % m_Actors.Count();
            HCInfectedActor actor = m_Actors[m_AdoptionCursor];
            m_AdoptionCursor = HCInfectedPolicy.NextAdoptionCursor(m_AdoptionCursor, m_Actors.Count());
            if (actor.EverAssigned || actor.SearchPack || !actor.Entity || !actor.Entity.IsAlive() || actor.Profile == "native_injured")
                continue;
            vector position = actor.Entity.GetPosition();
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
        HCNativeInfectedPack pack;
        if (m_Config.EnableNativePackRoutes)
        {
            pack = new HCNativeInfectedPack;
            vector destination = anchor + "40 0 0";
            destination[1] = GetGame().SurfaceY(destination[0], destination[2]);
            if (!pack.Start(candidates, destination, false, m_Now, m_Now + 3600))
                return;
        }
        HCHordeRecord record = new HCHordeRecord;
        record.State = 0;
        record.Id = m_State.Groups.Count() + 1;
        record.Reserved = requested;
        record.Living = requested;
        record.CreatedUtc = nowUtc;
        record.LastSignalUtc = nowUtc;
        record.Anchor = anchor;
        record.PreviousAnchor = anchor;
        if (pack)
        {
            record.HasRoute = true;
            record.RouteEnd = pack.RouteEnd;
        }
        m_State.Reserved += requested;
        m_State.Groups.Insert(record);
        m_Sweeps.Insert(new HCHordeSweep);
        m_Packs.Insert(pack);
        foreach (HCInfectedActor candidate : candidates)
        {
            candidate.GroupId = record.Id;
            candidate.EverAssigned = true;
        }
        ResetSweep();
        m_Dirty = true;
        // No entities are created, removed, moved or respawned by script.
        // Optional pack waypoints are followed by native AI/navigation only.
    }

    protected void TryInvestigate(HCInfectedActor actor)
    {
        bool visual = actor.Visual && actor.Visual.Provenance == 2 && actor.Visual.IsLive(m_Now);
        int mind = actor.Entity.GetMindStateSynced();
        bool engaged = mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT;
        bool grouped = actor.GroupId > 0 || actor.SearchPack != null;
        if (!HCInfectedPolicy.MayInvestigate(m_Config.EnableInvestigation, visual, engaged, actor.Profile == "native_injured", grouped, actor.SearchAttempts, m_Now, actor.NextSearch))
            return;
        if (m_RoutesRemaining < 1 || m_Investigators.Count() >= m_Config.MaxInvestigators)
            return;
        m_RoutesRemaining--;
        actor.SearchAttempts++;
        actor.NextSearch = m_Now + 10;
        ref array<HCInfectedActor> single = new array<HCInfectedActor>;
        single.Insert(actor);
        HCNativeInfectedPack pack = new HCNativeInfectedPack;
        // Frozen, directly observed clue only. Never a current hidden position.
        float expires = Math.Min(actor.Visual.Expires, m_Now + 15);
        if (pack.Start(single, actor.Visual.Origin, true, m_Now, expires))
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
                    m_Packs[p] = null;
                }
            }
            if (m_Packs[p])
            {
                if (!m_Packs[p].Tick(m_Now))
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
            int work = m_WorkCap - 2 - maintenance;
            int voices = Math.Min(m_Config.MaxVoicePerTick, work / 2);
            while (voices > 0 && m_Voices.Count() > 0)
            {
                HCInfectedVoice voice = m_Voices[0];
                m_Voices.Remove(0);
                HCInfectedActor actor = FindActor(voice.Emitter);
                if (actor && actor.Entity && actor.Entity.IsAlive() && voice.Clue.IsLive(m_Now))
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
