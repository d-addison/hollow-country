// LC-T309/310, #93/#94/#120. EnableEncounters admits source by preference;
// EXP-S3 is logged, never asserted accepted. No core registration edit required.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:932 GetWorldName, :914
// GetTickTime, :1550 GetCallQueue; 3_Game/DayZGame.c:1233 queue implementation;
// 2_GameLib/tools.c:61 CallLater, :65 Remove.
// HCGroupClock (UTC), HCGroupIO and the v1 director are reused, not reimplemented.
// Common natives: 3_Game/Global/Game.c:1120 IsServer; 1_Core/proto/EnDebug.c:96 Print;
// EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove; EnConvert.c:30 int.ToString;
// EnString.c:171 ToLower, :199 Length (1_Core/proto).

class HCScenesModule : HCModule
{
    protected static ref HCScenesModule s_CleanupOwner;
    protected ref HCSceneChainStore m_Store;
    protected ref HCSceneChainState m_State;
    protected ref array<ref HCSceneLease> m_Leases = new array<ref HCSceneLease>();
    protected int m_Cursor;
    protected int m_Placed;
    protected int m_Refused;
    // Last preflight refusal reason printed per chain id; bounded by the 4 reviewed chains.
    protected ref map<string, string> m_PreflightReasons = new map<string, string>();
    protected int m_LastNow;
    protected float m_WorkElapsed;
    protected float m_LogElapsed;
    protected bool m_Running;
    protected bool m_AdmissionPrinted;
    protected bool m_SummaryPrinted;

    override string GetName() { return "Scenes"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer() || !IsEnabled(settings) || m_Running) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Scenes", true, "EXP-S3", HCV2Gates.Qualified("EXP-S3")));
            m_AdmissionPrinted = true;
        }
        if (s_CleanupOwner || m_Leases.Count() > 0)
        {
            Print("[HollowCountry] V2 scenes startup refused; prior observer-gated cleanup pending");
            return;
        }
        string world;
        GetGame().GetWorldName(world);
        world.ToLower();
        if (world != "chernarusplus")
        {
            Print("[HollowCountry] V2 scenes refused; no reviewed sites for this world");
            return;
        }
        int now = Now();
        if (now < 1) { return; }
        m_Store = new HCSceneChainStore;
        m_State = m_Store.Open(now);
        if (!m_State) { return; }
        m_LastNow = now;
        m_Running = true;
        if (!m_SummaryPrinted) { Summary(); }
    }

    int Now()
    {
        int utc = HCGroupClock.Utc();
        // Director bounds its clock to 1e9 seconds. Fixed UTC 2020 origin keeps
        // genuine wall-clock hours/days and includes server downtime.
        if (utc < 1577836801) { return -1; }
        return utc - 1577836800;
    }

    bool Commit(int now)
    {
        m_State.LastNow = now;
        if (m_Store.Save(m_State)) { return true; }
        m_Running = false;
        OnStop();
        return false;
    }

    HCSceneLease Lease(string chainId)
    {
        foreach (HCSceneLease ownedLease : m_Leases)
        {
            if (ownedLease.ChainId == chainId) { return ownedLease; }
        }
        return null;
    }

    bool SiteAvailable(vector anchor)
    {
        foreach (HCSceneLease siteLease : m_Leases)
        {
            if (siteLease.Anchor == anchor) { return false; }
        }
        return true;
    }

    // Offer the already-placed scene through the existing optional v1 UI when
    // that module is admitted. V2 scenery itself does not require v1 markers.
    void Advertise(HCSceneLease lease, HCSceneStageDefinition stage, HCEventSite site, int seconds)
    {
        HCEventModule events = HCEventModule.Get();
        if (!events || !events.Runtime() || seconds < stage.Objective.DwellSeconds) { return; }
        HCEventMission mission = HCEventReviewedSites.SceneMission(site, stage.Objective.Id, seconds);
        HCEventRuntime runtime = events.Runtime();
        if (runtime.HasMission(mission.Id)) { return; }
        HCEventContext context = events.Context();
        if (runtime.Announce(mission, context) != HCEventCode.OK) { return; }
        HCEventRuntimeState snapshot = runtime.Snapshot();
        foreach (HCEventRun run : snapshot.Runs)
        {
            if (run.Objective.Id == mission.Id)
            {
                lease.ViewEventId = run.EventId;
                lease.ViewSession = context.Session;
            }
        }
    }

    void RetireView(HCSceneLease lease)
    {
        if (!lease || lease.ViewEventId == 0) { return; }
        HCEventModule events = HCEventModule.Get();
        if (!events || !events.Runtime()) { return; }
        HCEventContext context = events.Context();
        if (context.Session != lease.ViewSession) { return; }
        HCEventRuntimeState snapshot = events.Runtime().Snapshot();
        HCEventRecord record = HCEventDirector.FindRecord(snapshot.Director, lease.ViewEventId);
        if (record && !HCEventDirector.Terminal(record.Status)) { events.Runtime().Cancel(record.Id, context); }
        lease.ViewEventId = 0;
    }

    bool Cleanup(HCSceneLease lease)
    {
        if (!lease) { return true; }
        lease.Closing = true;
        RetireView(lease);
        if (!HCSceneKits.Remove(lease)) { return false; }
        int index = m_Leases.Find(lease);
        if (index >= 0) { m_Leases.Remove(index); }
        return true;
    }

    // One line whenever a chain's refusal reason changes, never once per retry.
    void PreflightRefused(string chainId, string reason)
    {
        string previous;
        if (m_PreflightReasons.Find(chainId, previous) && previous == reason) { return; }
        if (m_PreflightReasons.Count() >= 16 && !m_PreflightReasons.Contains(chainId)) { return; }
        m_PreflightReasons.Set(chainId, reason);
        Print("[HollowCountry] V2 scene preflight refused id=" + chainId + " reason=" + reason);
    }

    void Fail(HCSceneChain chain, int now, string reason)
    {
        HCSceneChains.Cancel(chain, now);
        m_Refused = m_Refused + 1;
        if (!Commit(now)) { return; }
        Print("[HollowCountry] V2 scene chain cancelled id=" + chain.Id + " stage=" + chain.Stage.ToString() + " reason=" + reason);
    }

    void Work(int now)
    {
        if (m_Cursor >= m_State.Chains.Count()) { m_Cursor = 0; }
        int selected = m_Cursor;
        m_Cursor = m_Cursor + 1;
        HCSceneChain chain = m_State.Chains[selected];
        HCSceneChainDefinition plan = m_State.Catalog.Chains[selected];
        HCSceneStageDefinition stage = plan.Stages[chain.Stage];
        HCSceneLease lease = Lease(chain.Id);
        if (chain.Cancelled || chain.Complete)
        {
            Cleanup(lease);
            return;
        }
        int status = HCEventStatus.ANNOUNCED;
        HCEventRecord record;
        if (chain.EventId > 0)
        {
            record = HCEventDirector.FindRecord(chain.Director, chain.EventId);
            if (!record) { Fail(chain, now, "missing-director-record"); return; }
            status = record.Status;
        }
        if (HCSceneChains.CancelExpired(chain, now, status))
        {
            Fail(chain, now, "stage-expired-or-failed");
            return;
        }
        if (status == HCEventStatus.COMPLETED)
        {
            if (!Cleanup(lease)) { return; }
            if (chain.Stage + 1 >= plan.Stages.Count())
            {
                chain.Complete = true;
            }
            else
            {
                chain.Stage = chain.Stage + 1;
                HCSceneChains.Schedule(chain, plan.Stages[chain.Stage], now);
            }
            Commit(now);
            return;
        }
        if (now < chain.DueAt) { return; }
        if (!lease)
        {
            if (m_Leases.Count() >= 2) { m_Refused = m_Refused + 1; return; }
            HCEventSite site = HCSceneChains.Site(plan.SiteId);
            if (!site) { Fail(chain, now, "missing-reviewed-site"); return; }
            // A later chain may reuse this reviewed anchor, but never while an
            // earlier lease (even a closing/partially removed one) still owns it.
            if (!SiteAvailable(site.Position)) { m_Refused = m_Refused + 1; return; }
            HCSceneKit kit = HCSceneKits.Find(stage.Kit);
            array<vector> positions;
            int variant;
            if (!HCSceneKits.Preflight(kit, site, positions, variant))
            {
                m_Refused = m_Refused + 1;
                PreflightRefused(chain.Id, HCSceneKits.Refusal());
                return;
            }
            if (chain.EventId == 0)
            {
                if (!HCSceneChains.Begin(chain, stage, now)) { Fail(chain, now, "director-refused"); return; }
                if (!Commit(now)) { return; }
            }
            // Record owned handles before the first native create. Partial kits
            // are cancelled and retained for observer-gated cleanup, never replaced.
            lease = new HCSceneLease;
            lease.ChainId = chain.Id;
            lease.Stage = chain.Stage;
            lease.Anchor = site.Position;
            m_Leases.Insert(lease);
            bool placed = HCSceneKits.Place(lease, kit, positions, variant);
            m_Placed = m_Placed + lease.Objects.Count();
            if (!placed) { Fail(chain, now, "placement-failed"); return; }
            int remaining = stage.HoldSeconds - (now - chain.BeganAt);
            Advertise(lease, stage, site, remaining);
            Print("[HollowCountry] V2 scene placed id=" + chain.Id + " stage=" + chain.Stage.ToString() + " kit=" + stage.Kit + " layout=" + variant.ToString());
            m_PreflightReasons.Remove(chain.Id);
        }
        if (!HCSceneKits.Healthy(lease)) { Fail(chain, now, "partial-or-missing-lease"); return; }
        if (now - chain.BeganAt >= stage.HoldSeconds)
        {
            int result = HCEventDirector.SceneElapsed(chain.Director, HCSceneChains.Context(chain, now), chain.EventId, chain.BeganAt, stage.HoldSeconds);
            if (result != HCEventCode.OK) { Fail(chain, now, "director-stage-failed"); return; }
            if (!Commit(now)) { return; }
            Print("[HollowCountry] V2 scene stage complete id=" + chain.Id + " stage=" + chain.Stage.ToString());
        }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !GetGame() || !GetGame().IsServer()) { return; }
        m_WorkElapsed = m_WorkElapsed + deltaTime;
        m_LogElapsed = m_LogElapsed + deltaTime;
        if (m_WorkElapsed >= 10)
        {
            m_WorkElapsed = 0;
            int now = Now();
            if (now < m_LastNow || now < m_State.LastNow || now > 999000000)
            {
                Print("[HollowCountry] V2 scenes stopped; invalid or rewound UTC clock");
                OnStop();
                return;
            }
            m_LastNow = now;
            // One chain per ten seconds; at most two live kits of <=8 props.
            Work(now);
        }
        if (m_LogElapsed >= 600)
        {
            m_LogElapsed = 0;
            Summary();
        }
    }

    void Summary()
    {
        int active = 0;
        int chains = 0;
        foreach (HCSceneLease lease : m_Leases)
        {
            if (!lease.Closing) { active = active + 1; }
        }
        if (m_State)
        {
            foreach (HCSceneChain chain : m_State.Chains)
            {
                if (!chain.Cancelled && !chain.Complete) { chains = chains + 1; }
            }
        }
        Print("[HollowCountry] V2 scenes active=" + active.ToString() + " chains=" + chains.ToString() + " placed=" + m_Placed.ToString() + " refused=" + m_Refused.ToString());
        m_SummaryPrinted = true;
    }

    // HCServer may drop stopped modules; keep ownership and a bounded queue
    // retry until all native references disappear. Never delete in front of players.
    void CleanupStopped()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (m_Leases.Count() > 0) { Cleanup(m_Leases[0]); }
        if (m_Leases.Count() == 0)
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(CleanupStopped);
            if (s_CleanupOwner == this) { s_CleanupOwner = null; }
        }
    }

    override void OnStop()
    {
        m_Running = false;
        if (!GetGame() || !GetGame().IsServer() || m_Leases.Count() == 0) { return; }
        s_CleanupOwner = this;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(CleanupStopped);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(CleanupStopped, 10000, true);
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCScenesModule);
    }
}
