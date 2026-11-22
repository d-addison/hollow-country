// Core owns the sole registry insertion; this module owns server RPC lifetime.
// Transport calls Runtime().Join/Leave with the actual sender PlayerBase.
// Native 1.30.164289: 3_Game/Global/Game.c:914/932/1120 clock/world/server;
// 1_Core/proto/EnScript.c:380/394/407 array Count/Find/Insert.
// 3_Game/gameplay.c:636 GetGame; 1_Core/proto/EnMath.c:54/427 random/floor;
// 1_Core/proto/EnString.c:171 ToLower; EnConvert.c:30 int.ToString.
// Native logging: 1_Core/proto/EnDebug.c:96 Print.
class HCEventModule : HCModule
{
    protected static HCEventModule s_Instance;
    protected static HCEventModule s_SituationOwner;
    // HCServer drops stopped modules from its active list. Keep at most one
    // unresolved owner alive across registry replacement; never replace its AI.
    protected static ref HCEventModule s_CleanupOwner;
    protected ref HCEventSettings m_Config;
    protected ref HCStepTimer m_TickSteps;
    protected int m_SituationStep;
    protected int m_RuntimeStep;
    protected int m_RosterStep;

    protected void HCMeasureStep(int step, string stage, int started)
    {
        int ticks = TickCount(started);
        m_TickSteps.HCAdd(step, ticks);
        m_TickSteps.HCItem(stage, ticks);
    }
    protected ref HCSituationDirector m_Situations;
    protected ref HCCampRaidSituation m_Raids;
    protected ref HCTransitSituation m_Transit;
    protected ref HCOperationalStatus m_SituationStatus = new HCOperationalStatus;
    protected ref HCOperationalOwner m_SurvivorOwner;
    protected ref HCOperationalOwner m_RaidOwner;
    protected ref HCOperationalOwner m_TransitOwner;
    // HC-41 native crash observation lease (owned here; one open per start).
    protected ref HCNativeIncidentLease m_Incidents;
    protected ref HCOperationalOwner m_IncidentOwner;
    protected bool m_SituationEnabled;
    protected bool m_SourceAttempted;
    // Last provider refusal already named in the log (one line per change).
    protected string m_ProviderNoted;
    protected ref HCEventRuntime m_Runtime;
    protected ref HCEventNativeObserver m_NativeObserver;
    protected float m_RosterElapsed = 0;
    protected int m_RosterCursor = 0;
    protected bool m_BindContinuing;
    protected bool m_StartupSweep;
    // Issue #333: one bounded roster summary per 60 s window (counters, no allocation per tick).
    protected float m_RosterWindow;
    protected int m_RosterBlockedPublish;
    protected int m_RosterBlockedAnnounce;
    protected int m_RosterRefreshes;
    protected int m_RosterAdmitted;
    protected int m_RosterSummarySeq;
    protected ref HCEventMission m_Announcing;
    protected int m_AnnouncingSlot;
    protected bool m_AnnouncingPolice;
    // One bounded slot per configured site/family, reset on module start.
    // Six fast post-readiness attempts, then indefinitely spaced slow retries.
    // One roster slot per five seconds. With one
    // site the same family is visited every 35 seconds (up to 8 sites: 280 s).
    protected ref array<int> m_PoliceRetryAttempts;
    protected ref array<float> m_PoliceRetryAfter;
    protected bool m_PoliceRetryReady;
    protected bool m_Stopping = false;
    protected bool m_Quarantined = false;
    protected int m_CleanupAttempts = 0;
    protected int m_QuarantineTicks = 0;
    protected float m_StartedAt;
    protected string m_Session;
    protected string m_StartRefusal;
    protected ref map<string, bool> m_AnnouncedMissions;
    // Same provider the runtime owns; read-only here so the roster offers the
    // AI encounter family only while that provider reports ready.
    protected ref HCEventAIProvider m_AIProvider;

    static HCEventModule Get()
    {
        return s_Instance;
    }
    override string GetName()
    {
        return "Events";
    }
    override int StartupPhase() { return HC_PHASE_FEATURE; }
    override void RegisterUses() { HCModuleReadiness.HCRegisterUse("Events", "police_supply_bound"); }
    override bool IsEnabled(HCSettings settings)
    {
        HCEventConfiguration loader = new HCEventConfiguration;
        m_Config = loader.Load();
        // Lifecycle stays registered so even shipping/off profiles get exactly
        // one boot receipt. Preference-off ticks are a cheap no-op, with no IO.
        return true;
    }
    override HCOperationalStatus HCGetOperationalStatus() { return m_SituationStatus; }

    void HCStartSituations(HCSettings settings)
    {
        s_SituationOwner = this;
        m_SituationEnabled = HCV2Admission.Admitted(settings && settings.EnableEncounters);
        m_SourceAttempted = false;
        m_Situations = new HCSituationDirector;
        m_Raids = new HCCampRaidSituation;
        m_Transit = new HCTransitSituation;
        HCCampRaidConfig raids;
        if (m_SituationEnabled) { raids = HCCampRaidSituation.HCLoad(); }
        m_Raids.HCOpen(raids, m_SituationEnabled);
        m_Transit.HCOpen(m_SituationEnabled);
        m_Incidents = new HCNativeIncidentLease;
        HCNativeIncidentSource incidentSource = new HCNativeIncidentSource;
        m_Incidents.HCOpen(incidentSource, m_SituationEnabled);
        m_ProviderNoted = "";
        m_Situations.HCDeferSource(m_SituationEnabled);
        m_Situations.HCEnableProfile("raid", m_Raids.HCProfilesEnabled(), 0);
        m_Situations.HCEnableProfile("column", m_Raids.HCProfilesEnabled(), 0);
        HCTransitProfile roadside = m_Transit.HCFind("hc40-roadside-position");
        HCTransitProfile exodus = m_Transit.HCFind("hc40-threatened-exodus");
        // Configuration enables profiles; HCOffer checks EVERY live actor port
        // after addon starts, before consuming the profile's one durable row.
        // Raid/column also require HCProfilesEnabled() above.
        if (roadside) { m_Situations.HCEnableProfile("roadside-position", m_SituationEnabled, roadside.LifetimeSeconds); }
        if (exodus) { m_Situations.HCEnableProfile("threatened-exodus", m_SituationEnabled, exodus.LifetimeSeconds); }
        m_SurvivorOwner = HCOperationalContributors.HCRegisterOwner("HC-38 survivor");
        m_RaidOwner = HCOperationalContributors.HCRegisterOwner("HC-39 raid,column");
        m_TransitOwner = HCOperationalContributors.HCRegisterOwner("HC-40 roadside,exodus");
        m_IncidentOwner = HCOperationalContributors.HCRegisterOwner("HC-41 native incidents");
        HCPublishSituations();
    }

    void HCPublishSituations()
    {
        if (!m_Situations || !m_Raids || !m_Transit) { return; }
        // Cached HC-1/25 path only: no new status, concatenation, config read or
        // provider readiness query. Owners retain separate off/refused receipts.
        HCOperationalStatus survivorStatus = m_Situations.HCStatus();
        HCOperationalStatus raidStatus = m_Raids.HCStatus();
        HCOperationalStatus transitStatus = m_Transit.HCStatus();
        // Events stays started for the independent director. Its module receipt
        // still reports legacy Events off when disabled; HC-38 retains its own
        // contributor receipt. With legacy Events enabled, use director state.
        if (!m_Config || !m_Config.Enabled) { m_SituationStatus.HCPublish("off", "operator_off"); }
        else if (m_Runtime && !m_Runtime.HCOperational()) { m_SituationStatus.HCPublish("degraded", "event_runtime_journal_unavailable"); }
        else if (m_Situations.HCProviderPending())
        {
            // Director and scene source run; only the actor provider is missing, so the
            // module is ready and the missing part is named once (never off/degraded).
            m_SituationStatus.HCPublish("ready", "situation_director_running_actor_provider_pending");
            string providerReason = survivorStatus.HCReason();
            if (m_ProviderNoted != providerReason)
            {
                m_ProviderNoted = providerReason;
                Print("[HC Events] situation actor provider pending reason=" + providerReason + " offers_wait=1 runtime=PENDING");
            }
        }
        else { m_SituationStatus.HCPublish(survivorStatus.HCState(), survivorStatus.HCReason()); }
        float observedAt = -1;
        if (GetGame()) { observedAt = GetGame().GetTickTime(); }
        if (m_SurvivorOwner) { m_SurvivorOwner.HCObserve(m_SituationEnabled, survivorStatus, observedAt); }
        if (m_RaidOwner) { m_RaidOwner.HCObserve(m_SituationEnabled, raidStatus, observedAt); }
        if (m_TransitOwner) { m_TransitOwner.HCObserve(m_SituationEnabled, transitStatus, observedAt); }
        if (m_IncidentOwner && m_Incidents) { m_IncidentOwner.HCObserve(m_SituationEnabled, m_Incidents.HCStatus(), observedAt); }
    }

    override void OnAllModulesStarted()
    {
        if (!m_Situations || !m_SituationEnabled) { HCPublishSituations(); return; }
        HCSceneChainState source = HCSituationSource.HCState();
        HCSceneChainStore store = HCSituationSource.HCStore();
        // Resolve only after Scenes and the optional actor ports have started.
        // The validated source has at most four retained chains.
        if (!m_SourceAttempted)
        {
            m_SourceAttempted = true;
            // Missing input is refused once; no retry scan or second store owner.
            if (!source || !store) { m_Situations.HCOpen(null, null, true); }
            if (source && store && m_Situations.HCOpen(source, store, true))
            {
                // One startup reconciliation over HC-19's validated <=4 rows.
                // Future arrivals are pushed by the existing durable owner;
                // there is no recurring chain scan or offer/save loop here.
                foreach (HCSceneChain retained : source.Chains) { m_Situations.HCOffer(retained); }
            }
        }
        HCPublishSituations();
    }

    void HCStepSituations()
    {
        if (!m_SituationEnabled || !m_Situations) { return; }
        if (m_Incidents) { m_Incidents.HCStep(); }
        HCSceneChainState source = HCSituationSource.HCState();
        HCSceneChainStore store = HCSituationSource.HCStore();
        if (!source || !store)
        {
            string prerequisite = "source";
            if (source && !store) { prerequisite = "store"; }
            m_Situations.HCActivityStep(-1, prerequisite);
            HCPublishSituations();
            return;
        }
        int utc = HCGroupClock.Utc();
        if (utc < 1577836801) { m_Situations.HCActivityStep(-1, "clock"); return; }
        int now = utc - 1577836800;
        m_Situations.HCStep(now);
        HCPublishSituations();
    }

    // Called only after HC-19 durably issued a fresh chain. No client/RPC
    // surface; offers still validate membership, sequence and retained history.
    static void HCStoryArrived(HCSceneChain chain)
    {
        if (s_SituationOwner) { s_SituationOwner.HCOfferSituation(chain); }
    }

    // Trusted server-owner seam for other HC situations (e.g. horde owner).
    // Retry a stable, namespaced identity until true, then start once and
    // confirm success. CE spawning and native aggro must never call this gate.
    static bool HCPaceSituation(string identity, vector anchor, int lifetimeSeconds)
    {
        // Optional owner/source off or unavailable: original owners keep their
        // own safety, capacity, finite stock and expiry rules.
        if (!s_SituationOwner || !s_SituationOwner.m_SituationEnabled || !s_SituationOwner.m_Config || !s_SituationOwner.m_Config.Enabled) { return true; }
        if (!s_SituationOwner.m_Situations || !s_SituationOwner.m_Situations.HCExternalAvailable()) { return true; }
        return s_SituationOwner.m_Situations.HCReserveExternal(identity, anchor, lifetimeSeconds);
    }

    static void HCCancelSituation(string identity)
    {
        if (s_SituationOwner && s_SituationOwner.m_Situations) { s_SituationOwner.m_Situations.HCCancelExternal(identity); }
    }

    static void HCEndedSituation(string identity)
    {
        if (s_SituationOwner && s_SituationOwner.m_Situations) { s_SituationOwner.m_Situations.HCEndExternal(identity); }
    }

    static void HCStartedSituation(string identity)
    {
        if (s_SituationOwner && s_SituationOwner.m_Situations) { s_SituationOwner.m_Situations.HCConfirmExternal(identity); }
    }

    void HCOfferSituation(HCSceneChain chain)
    {
        if (!m_SituationEnabled || !m_Situations) { return; }
        m_Situations.HCOffer(chain);
    }

    static void HCSourceClosing()
    {
        if (s_SituationOwner) { s_SituationOwner.HCCloseSituations(); }
    }

    void HCCloseSituations()
    {
        if (s_SituationOwner == this) { s_SituationOwner = null; }
        if (m_Situations) { m_Situations.HCClose(); }
        if (m_Raids) { m_Raids.HCClose(); }
        if (m_Transit) { m_Transit.HCClose(); }
        if (m_Incidents) { m_Incidents.HCClose(); }
        m_SituationEnabled = false;
        HCPublishSituations();
        m_ProviderNoted = "";
        m_Situations = null;
        m_Raids = null;
        m_Transit = null;
        m_SurvivorOwner = null;
        m_RaidOwner = null;
        m_TransitOwner = null;
        m_Incidents = null;
        m_IncidentOwner = null;
    }

    HCEventAIProvider CreateAIProvider()
    {
        return HCEventAISelection.Create();
    }
    HCEventNativeObserver CreateObserver()
    {
        return new HCEventNativeObserver;
    }
    void BindReviewedTargets(HCEventNativeObserver observer, HCEventSettings settings)
    {
        HCEventWorldBinding.BindSites(observer, settings, Context().WorldName);
    }

    HCEventContext Context()
    {
        HCEventContext context = new HCEventContext;
        if (!GetGame() || !GetGame().IsServer())
        {
            return context;
        }
        float elapsed = GetGame().GetTickTime() - m_StartedAt;
        if (elapsed != elapsed || elapsed < 0 || elapsed > 1000000000)
        {
            return context;
        }
        context.Server = true;
        // Vanilla lowercases the engine world name (missionBase.c); ToLower mutates in place.
        string world;
        GetGame().GetWorldName(world);
        world.ToLower();
        context.WorldName = world;
        context.Session = m_Session;
        context.Now = Math.Floor(elapsed);
        return context;
    }
    HCEventRuntime Runtime()
    {
        return m_Runtime;
    }
    // OnStart runs once per module start, so each reason is one boot line.
    // The independent HC-38 situation director keeps its own status receipts.
    string HCStartRefusal() { return m_StartRefusal; }
    void HCStartRefused(string reason)
    {
        m_StartRefusal = reason;
        Print("[HC Events] legacy events not started reason=" + reason);
    }
    override void OnStart(HCSettings settings)
    {
        // Repeated starts must revoke the old callback/session before replacing
        // its runtime, even when the new configuration no longer admits Events.
        OnStop();
        m_StartRefusal = "";
        m_TickSteps = new HCStepTimer("Events");
        m_SituationStep = m_TickSteps.HCDefine("situations");
        m_RuntimeStep = m_TickSteps.HCDefine("maintenance");
        m_RosterStep = m_TickSteps.HCDefine("roster");
        if (s_CleanupOwner && s_CleanupOwner != this)
        {
            s_CleanupOwner.OnStop();
        }
        if (s_CleanupOwner)
        {
            Print("[HC Events] startup blocked: prior runtime cleanup remains unconfirmed");
            return;
        }
        if (!GetGame() || !GetGame().IsServer()) { return; }
        HCStartSituations(settings);
        if (!m_Config || !m_Config.Enabled)
        {
            HCStartRefused("operator_off");
            return;
        }
        if (!HCEventQualification.Admitted())
        {
            HCStartRefused("local_acceptance_opt_out");
            return;
        }
        m_RosterCursor = 0;
        m_RosterElapsed = 0;
        m_RosterWindow = 0;
        m_RosterBlockedPublish = 0;
        m_RosterBlockedAnnounce = 0;
        m_RosterRefreshes = 0;
        m_RosterAdmitted = 0;
        m_RosterSummarySeq = 0;
        m_BindContinuing = false;
        m_StartupSweep = true;
        m_PoliceRetryReady = false;
        m_PoliceRetryAttempts = new array<int>;
        m_PoliceRetryAfter = new array<float>;
        int retrySlots = m_Config.Sites.Count() * 7;
        while (m_PoliceRetryAttempts.Count() < retrySlots) { m_PoliceRetryAttempts.Insert(0); m_PoliceRetryAfter.Insert(0); }
        m_AnnouncedMissions = new map<string, bool>;
        m_StartedAt = GetGame().GetTickTime();
        m_Session = "events-" + Math.RandomIntInclusive(1, 1000000000).ToString() + "-" + Math.RandomIntInclusive(1, 1000000000).ToString();
        HCEventContext context = Context();
        HCEventJournal journal = new HCEventJournal(m_Config);
        HCEventNativeObserver observer = CreateObserver();
        m_NativeObserver = observer;
        HCEventAIProvider ai = CreateAIProvider();
        m_AIProvider = ai;
        m_Runtime = new HCEventRuntime;
        m_Runtime.HCSetStepTimer(m_TickSteps);
        if (!m_Runtime.Start(m_Config, context, journal, observer, ai))
        {
            Print("[HC Events] inactive: context/configuration/journal admission failed reason=" + m_Runtime.Refusal());
            OnStop();
            return;
        }
        // Runtime canonicalizes the nonce with its persisted session generation.
        m_Session = context.Session;
        BindReviewedTargets(observer, m_Config);
        // Admit through the same bounded roster continuation after startup.
        // A startup loop must not bind other missions while one save owns the journal.
        m_BindContinuing = true;
        if (m_Stopping)
        {
            if (!m_Quarantined)
            {
                OnStop();
            }
            return;
        }
        s_Instance = this;
        Print("[HC Events] roster admission queued; participation is optional");
    }
    override void OnTick(float deltaTime)
    {
        if (!m_TickSteps) { return; }
        int started = TickCount(0);
        HCMeasuredTick(deltaTime);
        m_TickSteps.HCEndTick(TickCount(started));
    }

    protected void HCMeasuredTick(float deltaTime)
    {
        int situationStarted = TickCount(0);
        HCStepSituations();
        HCMeasureStep(m_SituationStep, "situations", situationStarted);
        if (m_Stopping)
        {
            if (!m_Quarantined)
            {
                OnStop();
                return;
            }
            // Slow provider confirmations still complete; retries stay rate-bounded.
            m_QuarantineTicks = m_QuarantineTicks + 1;
            if (m_QuarantineTicks >= 60)
            {
                m_QuarantineTicks = 0;
                OnStop();
            }
            return;
        }
        if (m_Runtime)
        {
            HCEventContext context = Context();
            if (!context.Server)
            {
                Print("[HC Events] invalid native session clock; stopping module, cleanup confirmation remains required");
                OnStop();
                return;
            }
            bool journalTick = m_Runtime.HCPublishPending();
            bool journalAtStart = m_Runtime.HCJournalPending();
            int runtimeStarted = TickCount(0);
            m_Runtime.Tick(context);
            // Runtime names individual expiry/cleanup/journal chunks. Keep its
            // aggregate out of HCItem so it cannot hide a measured chunk name.
            m_TickSteps.HCAdd(m_RuntimeStep, TickCount(runtimeStarted));
            m_RosterElapsed = m_RosterElapsed + deltaTime;
            HCRosterSummaryTick(deltaTime);
            if (m_Announcing && !m_Runtime.HCAnnouncePending())
            {
                HCCompleteAnnouncement(context);
                return;
            }
            if (journalTick || m_Runtime.HCJournalPending())
            {
                // blocked_publish_pending counts only ticks with an unpublished journal image; a
                // retained announce stage without one is blocked_announce.
                if (journalAtStart || m_Runtime.HCJournalPending()) { m_RosterBlockedPublish = m_RosterBlockedPublish + 1; }
                else { m_RosterBlockedAnnounce = m_RosterBlockedAnnounce + 1; }
                return;
            }
            if (m_Runtime.HCPublishPending() || m_Runtime.HCAnnounceOwned())
            {
                m_RosterBlockedAnnounce = m_RosterBlockedAnnounce + 1;
                return;
            }
            if (m_StartupSweep || m_BindContinuing || m_RosterElapsed >= 5)
            {
                m_RosterElapsed = 0;
                m_RosterRefreshes = m_RosterRefreshes + 1;
                int rosterStarted = TickCount(0);
                RefreshRoster(context);
                HCMeasureStep(m_RosterStep, "roster", rosterStarted);
                HCFinishStartupSweep();
            }
        }
    }
    // One line per 60 s window while the runtime is up: ticks the roster could not run
    // behind an unpublished journal image / an owned announcement, refreshes run, missions admitted.
    protected void HCRosterSummaryTick(float deltaTime)
    {
        m_RosterWindow = m_RosterWindow + deltaTime;
        if (m_RosterWindow < 60) { return; }
        m_RosterWindow = 0;
        m_RosterSummarySeq = m_RosterSummarySeq + 1;
        Print("[HC Events] roster summary window=" + m_RosterSummarySeq.ToString() + " window_s=60 blocked_publish_pending=" + m_RosterBlockedPublish.ToString() + " blocked_announce=" + m_RosterBlockedAnnounce.ToString() + " refreshes=" + m_RosterRefreshes.ToString() + " admitted=" + m_RosterAdmitted.ToString() + " runtime=PENDING");
        m_RosterBlockedPublish = 0;
        m_RosterBlockedAnnounce = 0;
        m_RosterRefreshes = 0;
        m_RosterAdmitted = 0;
    }

    // Only HC-owned AI starts consume the situation budget. Native CE events,
    // existing infected objectives and passive recovery/delivery offers keep
    // their own owners and are never disabled by this pacing gate.
    protected string m_AnnounceRefusal;

    int HCAnnouncePaced(HCEventMission mission, HCEventContext context)
    {
        m_AnnounceRefusal = "";
        if (m_Announcing || m_Runtime.HCPublishPending() || m_Runtime.HCAnnounceOwned()) { m_AnnounceRefusal = "event-slot-busy; retry"; return HCEventCode.BLOCKED; }
        if (mission && mission.Family == HCEventFamily.AI_ENCOUNTER)
        {
            if (!HCPaceSituation("event:" + mission.Id, mission.Source, mission.LifetimeSeconds)) { m_AnnounceRefusal = "situation-pacing-refused; retry"; return HCEventCode.BLOCKED; }
        }
        int result = m_Runtime.HCAnnounceStaged(mission, context);
        if (m_Runtime.HCAnnouncePending())
        {
            m_Announcing = mission;
            return result;
        }
        if (result == HCEventCode.OK && mission.Family == HCEventFamily.AI_ENCOUNTER)
        {
            HCStartedSituation("event:" + mission.Id);
        }
        else if (mission && mission.Family == HCEventFamily.AI_ENCOUNTER)
        {
            HCCancelSituation("event:" + mission.Id);
        }
        return result;
    }

    // Caller-side receipt notification; the module alone consumes the result.
    protected void HCAnnouncementCompleted(HCEventMission mission, int result) {}

    protected void HCCompleteAnnouncement(HCEventContext context)
    {
        int result = m_Runtime.HCTakeAnnounceResult(m_Announcing, context);
        if (m_Announcing.Family == HCEventFamily.AI_ENCOUNTER)
        {
            if (result == HCEventCode.OK) { HCStartedSituation("event:" + m_Announcing.Id); }
            else { HCCancelSituation("event:" + m_Announcing.Id); }
        }
        if (result == HCEventCode.OK)
        {
            m_RosterAdmitted = m_RosterAdmitted + 1;
            if (RememberAnnounced(m_Announcing.Id))
            {
                Print("[HC Events] mission admitted later; " + m_Announcing.Id + " runtime=PENDING");
            }
        }
        else if (m_AnnouncingPolice)
        {
            if (m_PoliceRetryAttempts[m_AnnouncingSlot] < 7) { m_PoliceRetryAttempts[m_AnnouncingSlot] = m_PoliceRetryAttempts[m_AnnouncingSlot] + 1; }
            HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
            if (policy && m_PoliceRetryAttempts[m_AnnouncingSlot] >= 6) { m_PoliceRetryAfter[m_AnnouncingSlot] = context.Now + policy.PoliceSlowRetrySeconds; }
            if (m_PoliceRetryAttempts[m_AnnouncingSlot] == 6)
            {
                Print("[HC Events] police binding retries exhausted; " + m_Announcing.Id + "; attempts=6; code=" + result.ToString() + " runtime=PENDING");
            }
        }
        m_RosterCursor = (m_AnnouncingSlot + 1) % (m_Config.Sites.Count() * 7);
        HCAnnouncementCompleted(m_Announcing, result);
        m_Announcing = null;
        m_AnnouncingPolice = false;
        m_BindContinuing = false;
        HCFinishStartupSweep();
    }

    protected void HCFinishStartupSweep()
    {
        if (!m_StartupSweep || m_Announcing || m_BindContinuing || m_RosterCursor != 0) { return; }
        m_StartupSweep = false;
        int admitted = m_AnnouncedMissions.Count();
        if (admitted > 0) { Print("[HC Events] admitted missions " + admitted.ToString()); }
        else { Print("[HC Events] enabled preference, no active missions"); }
    }

    void RefreshRoster(HCEventContext context)
    {
        if (m_Config.Sites.Count() == 0)
        {
            m_BindContinuing = false;
            HCFinishStartupSweep();
            return;
        }
        if (!m_Runtime || !m_NativeObserver || m_Announcing || m_Runtime.HCPublishPending() || m_Runtime.HCAnnounceOwned()) { return; }
        // One slot per tick during startup, then per five seconds; late CE population can admit
        // missions without restart. Runtime owns terminal cleanup and the two-hour
        // cooldown; remembering an admission only suppresses early retry work/logs.
        m_BindContinuing = false;
        int retrySlot = m_RosterCursor;
        int siteIndex = Math.Floor(m_RosterCursor / 7);
        int family = (m_RosterCursor % 7) + 1;
        m_RosterCursor = (m_RosterCursor + 1) % (m_Config.Sites.Count() * 7);
        HCEventSite site = m_Config.Sites[siteIndex];
        if (!site || !m_AnnouncedMissions) { return; }
        string siteWorld = site.WorldName;
        siteWorld.ToLower();
        if (siteWorld != context.WorldName) { return; }
        array<ref HCEventMission> roster = HCEventRoster.Build(site, AIReady(context));
        string rosterReceipt;
        foreach (HCEventMission mission : roster)
        {
            bool remembered = m_AnnouncedMissions.Contains(mission.Id);
            bool offerDue = !remembered || context.Now >= 7200;
            bool matchingFamily = mission.Family == family && offerDue;
            if (matchingFamily && !m_Runtime.HasMission(mission.Id))
            {
                bool policeRetry = HCEventSites.PoliceSupplies(mission);
                if (mission.Family == HCEventFamily.INFECTED_CLEAR && mission.AnchorClass == "Land_Village_PoliceStation") { policeRetry = true; }
                HCW38SituationPolicy policePolicy;
                if (policeRetry && !m_PoliceRetryAfter) { return; }
                if (policeRetry && context.Now < m_PoliceRetryAfter[retrySlot]) { return; }
                if (policeRetry && !remembered)
                {
                    // Cached module readiness, no speculative loading API. Do not
                    // spend the finite allowance during startup/provider refusal.
                    if (m_SituationStatus.HCState() != "ready" || !m_PoliceRetryAttempts) { return; }
                    policePolicy = HCW38SituationPolicy.HCGet();
                    if (!policePolicy) { return; }
                    // Each retained stock/infected stage takes its own grant.
                    // A budget yield never consumes a finite retry attempt.
                    if (!m_PoliceRetryReady)
                    {
                        m_PoliceRetryReady = true;
                        Print("[HC Events] police binding retries ready; attempts_per_mission=6; slot_interval_s=5; slow_interval_s=" + policePolicy.PoliceSlowRetrySeconds.ToString() + " runtime=PENDING");
                    }
                }
                bool bound = HCEventWorldBinding.Bind(m_NativeObserver, mission);
                // Keep the exact roster slot through a yield, including a
                // refused grant. Neither a continuation nor starvation spends
                // a finite retry or changes mission order.
                if (!bound && HCEventWorldBinding.BindReason() == "police_work_budget")
                {
                    m_BindContinuing = true;
                    m_RosterCursor = retrySlot;
                    return;
                }
                if (!bound && HCEventSites.PoliceSupplies(mission) && HCEventWorldBinding.PoliceStockWaiting())
                {
                    // A spent finite fallback is steady state. Continue bounded
                    // physical-stock probes without treating it as six failures.
                    HCW38SituationPolicy stockPolicy = HCW38SituationPolicy.HCGet();
                    if (!stockPolicy) { return; }
                    m_PoliceRetryAfter[retrySlot] = context.Now + stockPolicy.PoliceSlowRetrySeconds;
                    HCEventWorldBinding.PoliceStockDeferred(mission, m_PoliceRetryAfter[retrySlot]);
                    return;
                }
                if (policeRetry && !remembered && !bound)
                {
                    if (!bound && HCEventWorldBinding.PoliceWaitingForPlayers()) { return; }
                    if (!bound && HCEventSites.PoliceSupplies(mission) && HCEventCacheSpawner.PoliceReason() == "police_work_budget") { return; }
                    // Saturate at seven so the exhaustion receipt is emitted once.
                    if (m_PoliceRetryAttempts[retrySlot] < 7) { m_PoliceRetryAttempts[retrySlot] = m_PoliceRetryAttempts[retrySlot] + 1; }
                    if (m_PoliceRetryAttempts[retrySlot] >= 6) { m_PoliceRetryAfter[retrySlot] = context.Now + policePolicy.PoliceSlowRetrySeconds; }
                }
                if (policeRetry && !bound)
                {
                    // Binding logs state changes. Do not repeatedly Announce a known
                    // unavailable target; after six failures keep the slow timer alive.
                    if (!remembered && m_PoliceRetryAttempts[retrySlot] == 6)
                    {
                        Print("[HC Events] police binding slow retry; " + mission.Id + "; attempts=6; reason=" + HCEventWorldBinding.BindReason() + "; retryable=1 runtime=PENDING");
                        return;
                    }
                    return;
                }
                HCEventCacheSpawner.PoliceObjectiveClass(mission);
                int admission = HCAnnouncePaced(mission, context);
                if (m_Announcing)
                {
                    m_AnnouncingSlot = retrySlot;
                    m_AnnouncingPolice = policeRetry && !remembered;
                    m_BindContinuing = true;
                    m_RosterCursor = retrySlot;
                    return;
                }
                if (policeRetry && !remembered && bound)
                {
                    if (m_PoliceRetryAttempts[retrySlot] < 7) { m_PoliceRetryAttempts[retrySlot] = m_PoliceRetryAttempts[retrySlot] + 1; }
                    if (m_PoliceRetryAttempts[retrySlot] >= 6) { m_PoliceRetryAfter[retrySlot] = context.Now + policePolicy.PoliceSlowRetrySeconds; }
                }
                if (admission == HCEventCode.OK)
                {
                    m_RosterAdmitted = m_RosterAdmitted + 1;
                    // Remembered once, so this line appears once per mission id.
                    if (RememberAnnounced(mission.Id))
                    {
                        rosterReceipt = "[HC Events] mission admitted later; " + mission.Id + " runtime=PENDING";
                    }
                }
                else if (policeRetry && !remembered && m_PoliceRetryAttempts[retrySlot] == 6)
                {
                    rosterReceipt = "[HC Events] police binding retries exhausted; " + mission.Id + "; attempts=6; code=" + admission.ToString() + " runtime=PENDING";
                }
            }
        }
        if (rosterReceipt != "") { Print("" + rosterReceipt); }
    }
    // No provider, or a provider that is not ready, means no AI mission is offered.
    bool AIReady(HCEventContext context)
    {
        if (!m_AIProvider) { return false; }
        return m_AIProvider.Ready(context.WorldName);
    }
    // Bounded: at most 8 sites x 7 families; a full list refuses to remember.
    // True only when the id was newly remembered.
    bool RememberAnnounced(string missionId)
    {
        if (m_AnnouncedMissions && m_AnnouncedMissions.Count() < 64 && !m_AnnouncedMissions.Contains(missionId))
        {
            m_AnnouncedMissions.Insert(missionId, true);
            return true;
        }
        return false;
    }
    void ItemLocationChanged(ItemBase item, PlayerBase previousCarrier, EntityAI destination)
    {
        if (!m_Runtime || !m_NativeObserver || m_Stopping) { return; }
        // Every transition revokes an older receipt, even when this actor is
        // not enrolled. A direct native move from an enrolled actor may renew it.
        m_NativeObserver.RevokeDelivery(item);
        // No previous carrier means no actor can be attributed; skip Context().
        if (!previousCarrier) { return; }
        HCEventContext context = Context();
        m_Runtime.ItemDelivered(item, previousCarrier, destination, context);
    }
    void InfectedKilled(ZombieBase infected, PlayerBase participant)
    {
        if (!m_Runtime || !m_NativeObserver || m_Stopping) { return; }
        HCEventContext context = Context();
        m_Runtime.InfectedKilled(infected, participant, context);
    }
    void PlayerDisconnected(PlayerBase player)
    {
        if (m_Runtime)
        {
            HCEventContext context = Context();
            m_Runtime.Disconnect(player, context);
        }
    }
    override void OnStop()
    {
        if (m_Announcing)
        {
            if (m_Announcing.Family == HCEventFamily.AI_ENCOUNTER) { HCCancelSituation("event:" + m_Announcing.Id); }
            m_Announcing = null;
        }
        HCCloseSituations();
        if (s_Instance == this)
        {
            s_Instance = null;
        }
        if (m_Runtime)
        {
            m_Stopping = true;
            s_CleanupOwner = this;
            m_CleanupAttempts = m_CleanupAttempts + 1;
            HCEventContext context = Context();
            if (!m_Runtime.Stop(context))
            {
                if (m_CleanupAttempts == 1)
                {
                    Print("[HC Events] shutdown pending: runtime/provider/journal ownership retained");
                }
                if (m_CleanupAttempts >= 8 && !m_Quarantined)
                {
                    m_Quarantined = true;
                    Print("[HC Events] cleanup quarantined: owner/entities retained; retrying every 60 module ticks; fresh start rechecks closure, journal faults require explicit recovery");
                }
                return;
            }
            m_Runtime = null;
            m_NativeObserver = null;
            m_AIProvider = null;
        }
        m_Stopping = false;
        m_Quarantined = false;
        m_CleanupAttempts = 0;
        m_QuarantineTicks = 0;
        if (s_CleanupOwner == this)
        {
            s_CleanupOwner = null;
        }
        m_Session = "";
        m_StartedAt = 0;
    }
}
