// Core owns the sole registry insertion; this module owns server RPC lifetime.
// Transport calls Runtime().Join/Leave with the actual sender PlayerBase.
class HCEventModule : HCModule
{
    protected static HCEventModule s_Instance;
    // HCServer drops stopped modules from its active list. Keep at most one
    // unresolved owner alive across registry replacement; never replace its AI.
    protected static ref HCEventModule s_CleanupOwner;
    protected ref HCEventSettings m_Config;
    protected ref HCEventRuntime m_Runtime;
    protected ref HCEventNativeObserver m_NativeObserver;
    protected float m_RosterElapsed = 0;
    protected int m_RosterCursor = 0;
    protected ref HCEventRPC m_EventRPC;
    protected bool m_Stopping = false;
    protected bool m_Quarantined = false;
    protected int m_CleanupAttempts = 0;
    protected int m_QuarantineTicks = 0;
    protected float m_StartedAt;
    protected string m_Session;
    protected ref array<string> m_AnnouncedMissions;
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
        return m_Config && m_Config.Enabled;
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
    override void OnStart(HCSettings settings)
    {
        // Repeated starts must revoke the old callback/session before replacing
        // its runtime, even when the new configuration no longer admits Events.
        OnStop();
        if (s_CleanupOwner && s_CleanupOwner != this)
        {
            s_CleanupOwner.OnStop();
        }
        if (s_CleanupOwner)
        {
            Print("[HC Events] startup blocked: prior runtime cleanup remains unconfirmed");
            return;
        }
        if (!m_Config || !m_Config.Enabled || !GetGame() || !GetGame().IsServer())
        {
            return;
        }
        if (!HCEventQualification.Admitted()) { return; }
        m_RosterCursor = 0;
        m_RosterElapsed = 0;
        m_AnnouncedMissions = new array<string>();
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
            Print("[HC Events] inactive: context/configuration/journal admission failed");
            OnStop();
            return;
        }
        // Runtime canonicalizes the nonce with its persisted session generation.
        m_Session = context.Session;
        BindReviewedTargets(observer, m_Config);
        bool aiReady = AIReady(context);
        int admitted = 0;
        foreach (HCEventSite site : m_Config.Sites)
        {
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
                    int result = m_Runtime.Announce(mission, context);
                    if (result == HCEventCode.OK)
                    {
                        RememberAnnounced(mission.Id);
                        admitted = admitted + 1;
                    }
                    else
                    {
                        Print("[HC Events] roster mission not admitted; code " + result.ToString());
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
            Print("[HC Events] opt-in transport unavailable; stopping runtime");
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
    void RefreshRoster(HCEventContext context)
    {
        if (!m_Runtime || !m_NativeObserver || m_Config.Sites.Count() == 0) { return; }
        // One site's one family per five seconds; late CE population can admit
        // missions without restart. Current-session terminal missions never repeat.
        int siteIndex = Math.Floor(m_RosterCursor / 7);
        int family = (m_RosterCursor % 7) + 1;
        m_RosterCursor = (m_RosterCursor + 1) % (m_Config.Sites.Count() * 7);
        HCEventSite site = m_Config.Sites[siteIndex];
        if (!site || !m_AnnouncedMissions) { return; }
        string siteWorld = site.WorldName;
        siteWorld.ToLower();
        if (siteWorld != context.WorldName) { return; }
        array<ref HCEventMission> roster = HCEventRoster.Build(site, AIReady(context));
        foreach (HCEventMission mission : roster)
        {
            // HasMission cannot see pruned records, so this session list is the
            // authority that a terminal mission never announces again.
            if (mission.Family == family && m_AnnouncedMissions.Find(mission.Id) < 0 && !m_Runtime.HasMission(mission.Id))
            {
                HCEventWorldBinding.Bind(m_NativeObserver, mission);
                if (m_Runtime.Announce(mission, context) == HCEventCode.OK)
                {
                    // Remembered once, so this line appears once per mission id.
                    if (RememberAnnounced(mission.Id))
                    {
                        Print("[HC Events] mission admitted later; " + mission.Id);
                    }
                }
            }
        }
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
        if (m_AnnouncedMissions && m_AnnouncedMissions.Count() < 64 && m_AnnouncedMissions.Find(missionId) < 0)
        {
            m_AnnouncedMissions.Insert(missionId);
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
