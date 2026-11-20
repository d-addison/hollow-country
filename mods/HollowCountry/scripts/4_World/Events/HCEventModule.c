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
    // One bounded slot per configured site/family, reset on module start.
    // Six fast post-readiness attempts, then indefinitely spaced slow retries.
    // One roster slot per five seconds. With one
    // site the same family is visited every 35 seconds (up to 8 sites: 280 s).
    protected ref array<int> m_PoliceRetryAttempts;
    protected ref array<float> m_PoliceRetryAfter;
    protected bool m_PoliceRetryReady;
    protected ref HCEventRPC m_EventRPC;
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

    void HCStepSituations()
    {
        if (!m_SituationEnabled || !m_Situations) { return; }
        if (m_Incidents) { m_Incidents.HCStep(); }
        HCSceneChainState source = HCSituationSource.HCState();
        HCSceneChainStore store = HCSituationSource.HCStore();
        // The first server tick follows all module starts. Resolve once, so
        // registry order cannot hide a scene binding and missing input never
        // creates a retry scan or another persistence owner.
        if (!m_SourceAttempted)
        {
            m_SourceAttempted = true;
            // A missing source on the first tick is named once (refused, no retry scan).
            if (!source || !store) { m_Situations.HCOpen(null, null, true); }
            if (source && store && m_Situations.HCOpen(source, store, true))
            {
                // One startup reconciliation over HC-19's validated <=4 rows.
                // Future arrivals are pushed by the existing durable owner;
                // there is no recurring chain scan or offer/save loop here.
                foreach (HCSceneChain retained : source.Chains) { m_Situations.HCOffer(retained); }
            }
        }
        if (!source || !store) { HCPublishSituations(); return; }
        int utc = HCGroupClock.Utc();
        if (utc < 1577836801) { return; }
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
        if (!m_Runtime.Start(m_Config, context, journal, observer, ai))
        {
            Print("[HC Events] inactive: context/configuration/journal admission failed reason=" + m_Runtime.Refusal());
            OnStop();
            return;
        }
        // Runtime canonicalizes the nonce with its persisted session generation.
        m_Session = context.Session;
        BindReviewedTargets(observer, m_Config);
        bool aiReady = AIReady(context);
        int admitted = 0;
        // SettingsValid admits at most eight sites; make that startup bound explicit.
        for (int startupSite = 0; startupSite < 8 && startupSite < m_Config.Sites.Count(); startupSite++)
        {
            HCEventSite site = m_Config.Sites[startupSite];
            string siteWorld;
            if (site)
            {
                siteWorld = site.WorldName;
                siteWorld.ToLower();
            }
            if (!site || siteWorld != context.WorldName)
            {
                Print("[HC Events] blocked site: missing or different world identity");
            }
            else
            {
                array<ref HCEventMission> roster = HCEventRoster.Build(site, aiReady);
                foreach (HCEventMission mission : roster)
                {
                    HCEventCacheSpawner.PoliceObjectiveClass(mission);
                    int result = HCAnnouncePaced(mission, context);
                    if (result == HCEventCode.OK)
                    {
                        RememberAnnounced(mission.Id);
                        admitted = admitted + 1;
                    }
                    else
                    {
                        Print("[HC Events] roster mission not admitted; " + mission.Id + "; code " + result.ToString());
                    }
                }
            }
        }
        if (m_Stopping)
        {
            if (!m_Quarantined)
            {
                OnStop();
            }
            return;
        }
        // Admit opt-in requests only after runtime and current-world roster.
        m_EventRPC = new HCEventRPC;
        if (!m_EventRPC.Start(this))
        {
            Print("[HC Events] opt-in transport unavailable; stopping runtime reason=" + m_EventRPC.Refusal());
            OnStop();
            return;
        }
        s_Instance = this;
        if (admitted == 0)
        {
            Print("[HC Events] enabled preference, no active missions: review sites/target bindings/provider capabilities");
        }
        else
        {
            if (HCEventSitesGate.Admitted())
            {
                Print("[HC Events] admitted missions " + admitted.ToString() + "; participation is optional; reward caches from finite journaled pool");
            }
            else
            {
                Print("[HC Events] admitted missions " + admitted.ToString() + "; participation is optional; reward caches unavailable");
            }
        }
    }
    override void OnTick(float deltaTime)
    {
        HCStepSituations();
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
            // Revoke disconnected peers before any objective observations.
            if (m_EventRPC)
            {
                m_EventRPC.Tick();
            }
            m_Runtime.Tick(context);
            m_RosterElapsed = m_RosterElapsed + deltaTime;
            if (m_RosterElapsed >= 5)
            {
                m_RosterElapsed = 0;
                RefreshRoster(context);
            }
        }
    }
    // Only HC-owned AI starts consume the situation budget. Native CE events,
    // existing infected objectives and passive recovery/delivery offers keep
    // their own owners and are never disabled by this pacing gate.
    int HCAnnouncePaced(HCEventMission mission, HCEventContext context)
    {
        if (mission && mission.Family == HCEventFamily.AI_ENCOUNTER)
        {
            if (!HCPaceSituation("event:" + mission.Id, mission.Source, mission.LifetimeSeconds)) { return HCEventCode.BLOCKED; }
        }
        int result = m_Runtime.Announce(mission, context);
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

    void RefreshRoster(HCEventContext context)
    {
        if (!m_Runtime || !m_NativeObserver || m_Config.Sites.Count() == 0) { return; }
        // One site's one family per five seconds; late CE population can admit
        // missions without restart. Runtime owns terminal cleanup and the two-hour
        // cooldown; remembering an admission only suppresses early retry work/logs.
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
                if (policeRetry && !remembered)
                {
                    // Cached module readiness, no speculative loading API. Do not
                    // spend the finite allowance during startup/provider refusal.
                    if (m_SituationStatus.HCState() != "ready" || !m_PoliceRetryAttempts) { return; }
                    if (context.Now < m_PoliceRetryAfter[retrySlot]) { return; }
                    policePolicy = HCW38SituationPolicy.HCGet();
                    if (!policePolicy) { return; }
                    // Physical stock charges its own scan; infected lookup is
                    // charged here. A budget yield never consumes an attempt.
                    if (mission.Family == HCEventFamily.INFECTED_CLEAR && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_POLICE_BIND, 8)) { return; }
                    if (!m_PoliceRetryReady)
                    {
                        m_PoliceRetryReady = true;
                        Print("[HC Events] police binding retries ready; attempts_per_mission=6; slot_interval_s=5; slow_interval_s=" + policePolicy.PoliceSlowRetrySeconds.ToString() + " runtime=PENDING");
                    }
                }
                bool bound = HCEventWorldBinding.Bind(m_NativeObserver, mission);
                if (policeRetry && !remembered)
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
                        Print("[HC Events] police binding slow retry; " + mission.Id + "; attempts=6; retryable=1 runtime=PENDING");
                        return;
                    }
                    return;
                }
                HCEventCacheSpawner.PoliceObjectiveClass(mission);
                int admission = HCAnnouncePaced(mission, context);
                if (admission == HCEventCode.OK)
                {
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
        m_Runtime.ItemDelivered(item, previousCarrier, destination, Context());
    }
    void InfectedKilled(ZombieBase infected, PlayerBase participant)
    {
        if (!m_Runtime || !m_NativeObserver || m_Stopping) { return; }
        m_Runtime.InfectedKilled(infected, participant, Context());
    }
    void PlayerDisconnected(PlayerBase player)
    {
        if (m_Runtime)
        {
            m_Runtime.Disconnect(player, Context());
        }
    }
    override void OnStop()
    {
        HCCloseSituations();
        if (m_EventRPC)
        {
            m_EventRPC.Stop();
            m_EventRPC = null;
        }
        if (s_Instance == this)
        {
            s_Instance = null;
        }
        if (m_Runtime)
        {
            m_Stopping = true;
            s_CleanupOwner = this;
            m_CleanupAttempts = m_CleanupAttempts + 1;
            if (!m_Runtime.Stop(Context()))
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
