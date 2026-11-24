// HC site patrols: implementation behind the director's virtual seams.
class HCXAISiteSpawnConfig : ExpansionAIDynamicSpawnBase
{
    override TVectorArray GetWaypoints(vector position = vector.Zero, int beh = eAIWaypointBehavior.HALT)
    {
        TVectorArray qualified = new TVectorArray();
        foreach (vector waypoint : this.Waypoints)
        {
            qualified.Insert(waypoint);
        }
        return qualified;
    }
}
class HCXAISitePatrol : HCXExpansionPatrol
{
    string m_HCSiteId;
    string m_HCKind;
    int m_HCGroupMax;
    int m_HCAuthoredMin;
    int m_HCAuthoredMax;
    bool m_HCLive;
    bool m_HCTransient;
    bool m_HCFinished;
    int m_HCSurvivors;
    int m_HCPendingMembers;
    string m_HCRefusal;
    bool m_HCRingLogged;
    protected ref HCXAIGroupHold m_HCHold;
    int m_HCRingRetryMs;
    protected int m_HCNextBudgetLogMs;
    protected int m_HCNextSkipLogMs;
    static const int HC_SITE_LOG_INTERVAL_MS = 60000;
    // Weak patrol inventory also covers Delete's deferred provider teardown.
    protected static ref array<HCXAISitePatrol> s_HCLiveSlots = new array<HCXAISitePatrol>;
    protected bool m_HCDeathHeld;
    protected bool m_HCDeathResumePending;
    protected ref array<DayZPlayerImplement> m_HCDeathMembers = new array<DayZPlayerImplement>;
    protected int m_HCDeathKills;
    protected bool m_HCDeathOverflow;
    protected int m_HCDeathFrames;
    protected int m_HCDeathNextReportMs;
    protected int m_HCDeferredMember = -1;
    static const int HC_DEATH_HOLD_CAP_MS = 10000;
    void HCXAISitePatrol()
    {
        s_HCLiveSlots.Insert(this);
    }
    void ~HCXAISitePatrol()
    {
        this.HCDeathFrameStop();
        if (s_HCLiveSlots) { s_HCLiveSlots.RemoveItem(this); }
    }
    static bool HCNamesLiveSlot(eAIGroup group)
    {
        foreach (HCXAISitePatrol patrol : s_HCLiveSlots)
        {
            if (patrol && patrol.HCBridgeNamesGroup(group)) { return true; }
        }
        return false;
    }
    bool HCMatchesGroup(eAIGroup group)
    {
        return group && (this.HCBridgeNamesGroup(group) || HCXExpansionBridge.HCHoldSame(m_HCHold, group));
    }
    eAIGroup HCGroupIfSafe()
    {
        if (m_HCDeathHeld) { return null; }
        if (!m_HCHold || !this.HCBridgeOwnsHold(m_HCHold)) { return null; }
        return m_HCHold.HCResolveFresh();
    }
    bool HCDeathHeld() { return m_HCDeathHeld; }
    // No provider call or new strong reference through the raw slot on this path.
    void HCArmDeath(DayZPlayerImplement killed)
    {
        bool first = !m_HCDeathHeld;
        m_HCDeathHeld = true;
        m_HCDeathFrames = 0;
        m_HCDeathNextReportMs = GetGame().GetTime() + HC_DEATH_HOLD_CAP_MS;
        if (m_HCDeathKills < 2147483647) { m_HCDeathKills++; }
        if (!killed || m_HCDeathMembers.Count() >= 16) { m_HCDeathOverflow = true; }
        else { m_HCDeathMembers.Insert(killed); }
        // Re-arm even when the previous frame callback already removed itself.
        this.HCDeathFrameStop();
        GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(HCDeathFrame);
        if (first)
        {
            Print("[HCX SitePatrol] death_hold armed site=" + m_HCSiteId + " kills=" + m_HCDeathKills.ToString());
        }
        if (m_HCHold && m_HCHold.Deaths < 2147483647) { m_HCHold.Deaths++; }
        HCModuleReadiness.HCUse("SitePatrols", "death-hold-armed");
    }
    // Two SYSTEM invocations prove a frame boundary even if armed before this
    // frame's update queue. Native Game.c:1552, DayZGame.c:3027, tools.c:115.
    protected void HCDeathFrame(float timeslice)
    {
        if (m_HCDeathFrames < 2) { m_HCDeathFrames++; }
        if (m_HCDeathFrames >= 2) { this.HCDeathFrameStop(); }
    }
    protected void HCDeathFrameStop()
    {
        if (GetGame()) { GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCDeathFrame); }
    }
    protected void HCDeathHoldStep()
    {
        bool terminal = false;
        bool clean = false;
        if (m_HCDeathFrames >= 2 && !m_HCDeathOverflow && (!m_HCHold || this.HCBridgeOwnsHold(m_HCHold)))
        {
            clean = HCXExpansionBridge.HCHeldDeathClean(m_HCHold, m_HCDeathMembers, terminal);
        }
        if (terminal)
        {
            // Never resume a provider-unlisted or emptied group, even with pending spawns.
            this.HCEndPatrol();
            return;
        }
        if (clean && m_HCHold && this.HCBridgeOwnsHold(m_HCHold))
        {
            m_HCDeathHeld = false;
            m_HCDeathResumePending = true;
            m_HCDeathMembers.Clear();
            m_HCDeathKills = 0;
            HCModuleReadiness.HCUse("SitePatrols", "death-hold-released");
            return;
        }
        int nowMs = GetGame().GetTime();
        if (nowMs < m_HCDeathNextReportMs) { return; }
        m_HCDeathNextReportMs = nowMs + HC_DEATH_HOLD_CAP_MS;
        Print("[HCX SitePatrol] death_hold_deferred reason=DEATH_HOLD_STALE site=" + m_HCSiteId);
        HCModuleReadiness.HCUse("SitePatrols", "death-hold-deferred");
    }
    protected void HCLogSkipped(string why)
    {
        int nowMs = GetGame().GetTime();
        if (nowMs < m_HCNextSkipLogMs) { return; }
        m_HCNextSkipLogMs = nowMs + HC_SITE_LOG_INTERVAL_MS;
        Print("[HC Expansion AI] site " + m_HCSiteId + " spawn skipped: " + why);
    }
    protected void HCRefuseBudget(string problem = "")
    {
        int nowMs = GetGame().GetTime();
        HCXAISiteDirector refusedDirector = HCXAISiteDirector.Active();
        string countedProblem = problem;
        if (countedProblem == "") { countedProblem = "shared_population_reservation"; }
        if (refusedDirector) { refusedDirector.HCSpawnRefused(countedProblem); }
        if (nowMs < m_HCNextBudgetLogMs) { return; }
        m_HCNextBudgetLogMs = nowMs + HC_SITE_LOG_INTERVAL_MS;
        if (problem != "") { Print("[HC Expansion AI] site " + m_HCSiteId + " spawn refused: " + problem); }
        else { Print("[HC AI] site shared population reservation refused id=" + m_HCSiteId); }
    }
    override bool CanSpawn()
    {
        if (m_HCFinished || m_HCDeathHeld) { return false; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return false; }
        string problem = director.HCPrepareRingSpawn(this);
        if (problem == "" && !this.HCBridgeCanSpawn()) { problem = "provider_spawn_gate"; }
        if (problem == "") { problem = director.SpawnProblemFor(this); }
        director.HCSpawnRefused(problem);
        if (problem != m_HCRefusal)
        {
            m_HCRefusal = problem;
            if (problem != "" && problem != "sites not running") { Print("[HC Expansion AI] site " + m_HCSiteId + " spawn held: " + problem); }
        }
        return problem == "";
    }
    override void Spawn()
    {
        if (m_HCFinished) { return; }
        if (m_HCDeathHeld) { this.HCLogSkipped("DEATH_HOLD_ACTIVE"); return; }
        if (this.HCHasGroup())
        {
            this.HCLogSkipped("group already live");
            return;
        }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director)
        {
            this.HCRefuseBudget("sites not running");
            return;
        }
        string ringProblem = director.HCPrepareRingSpawn(this);
        if (ringProblem != "") { this.HCRefuseBudget(ringProblem); return; }
        string problem = director.SpawnProblemFor(this);
        if (problem != "")
        {
            this.HCRefuseBudget(problem);
            return;
        }
        string budgetId = "site:" + m_HCSiteId;
        if (m_HCTransient) { budgetId = m_HCSiteId.Substring(10, m_HCSiteId.Length() - 10); }
        if (!HCAIBudget.TryReserve(budgetId, m_HCGroupMax)) { this.HCRefuseBudget(); return; }
        m_HCPendingMembers = 0;
        this.HCBridgeSpawn();
        if (!this.HCHasGroup())
        {
            if (!m_HCTransient) { HCAIBudget.Release(budgetId); }
            this.HCRefuseBudget("provider_spawn_failed");
            return;
        }
        this.HCHoldMembers();
        m_HCPendingMembers = m_NumberOfAI - HCXExpansionBridge.HCHoldCount(m_HCHold);
        if (m_HCPendingMembers < 0) { m_HCPendingMembers = 0; }
        m_HCLive = true;
        director.Spawned(this);
    }
    override void SpawnAI_Deferred(int i)
    {
        if (m_HCFinished) { return; }
        if (m_HCDeathHeld) { m_HCDeferredMember = i; this.HCLogSkipped("DEATH_HOLD_ACTIVE"); return; }
        m_HCPendingMembers = 0;
        // An emptied group may already be out of the provider's group list (our hold keeps
        // the object alive); never add members to it.
        // The provider may call this inside Spawn, before Spawn followed the new group.
        this.HCHoldMembers();
        if (!HCXExpansionBridge.HCHoldAlive(m_HCHold) || !m_Formation)
        {
            this.HCRefuseBudget("member spawn without a live group");
            return;
        }
        if (HCXExpansionBridge.HCHoldCount(m_HCHold) == 0)
        {
            this.HCRefuseBudget("group emptied before member spawn");
            return;
        }
        vector raw = HCXExpansionBridge.HCFormationToWorld(m_Formation, HCXExpansionBridge.HCFormationGetPosition(m_Formation, i));
        vector placed = HCXExpansionBridge.HCPlacementPosition(raw, true);
        string problem = "sites not running";
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (director)
        {
            problem = director.MemberProblemFor(raw);
            if (problem == "") { problem = director.MemberProblemFor(placed); }
        }
        if (problem != "")
        {
            m_HCPendingMembers = 0;
            m_NumberOfAI = HCXExpansionBridge.HCHoldCount(m_HCHold);
            HCXExpansionBridge.HCHoldSetWaypointBehaviour(m_HCHold, m_WaypointBehaviour);
            Print("[HC Expansion AI] site " + m_HCSiteId + " member " + i.ToString() + " refused: " + problem + "; group stays at " + m_NumberOfAI.ToString());
            if (director) { director.HCQueueOwned(); }
            return;
        }
        m_HCPendingMembers = m_NumberOfAI - i - 1;
        if (m_HCPendingMembers < 0) { m_HCPendingMembers = 0; }
        this.HCBridgeSpawnAI_Deferred(i);
        // The provider joins the member to m_Group only after SetupAI returns.
        this.HCHoldMembers();
    }
    // #334: the patrol's group handle. Every reader outside this class goes through it and the
    // HCHold* bridge calls; a null, retired or dead handle is the "group gone" answer.
    HCXAIGroupHold HCGroupHold()
    {
        return m_HCHold;
    }
    // True while the provider's group slot is set, even if that group has died. Spawn and
    // site-recycle decisions use it (a dead slot must not respawn); a null compare, no dereference.
    bool HCHasGroup()
    {
        return this.HCBridgeHasGroupSlot();
    }
    // #334: keep the provider group alive while any member it spawned still exists.
    // The hold always follows the group slot; a hold on the live slot group is never retired here.
    protected void HCHoldGroup(eAIGroup group, DayZPlayerImplement member)
    {
        if (m_HCDeathHeld || !group) { return; }
        if (m_HCHold && !HCXExpansionBridge.HCHoldSame(m_HCHold, group))
        {
            if (this.HCBridgeOwnsHold(m_HCHold)) { return; }
            this.HCReleaseHold();
        }
        if (!m_HCHold) { m_HCHold = new HCXAIGroupHold(group); }
        m_HCHold.Track(member);
    }
    protected void HCHoldMembers()
    {
        if (m_HCDeathHeld) { return; }
        if (!this.HCHasGroup()) { return; }
        m_HCHold = this.HCBridgeFollowHold(m_HCHold);
    }
    void HCReleaseHold()
    {
        this.HCDeathFrameStop();
        if (m_HCDeathHeld) { HCModuleReadiness.HCUse("SitePatrols", "death-hold-released"); }
        m_HCDeathHeld = false;
        m_HCDeathResumePending = false;
        m_HCDeathMembers.Clear();
        m_HCDeathKills = 0;
        m_HCDeathOverflow = false;
        m_HCDeferredMember = -1;
        if (!m_HCHold) { return; }
        HCXAIGroupHolds.Retire(m_HCHold);
        m_HCHold = null;
    }
    void HCPreserveBodies()
    {
        HCXExpansionBridge.HCHoldRemoveDeceasedAll(m_HCHold);
    }
    override void Despawn(bool deferDespawnUntilLoosingAggro = false)
    {
        // Despawn persistence: Final reads resolve in any lifecycle state, so a stopping patrol
        // still reads its real group and never persists a defaulted "cleared" site.
        if (HCXExpansionBridge.HCHoldCountFinal(m_HCHold) > 0 && !HCXAISiteRules.DespawnAllowed(HCXExpansionBridge.HCHoldIsInCombatFinal(m_HCHold), HCXExpansionBridge.HCHoldForcePatrolDespawnFinal(m_HCHold))) { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (m_HCTransient && this.HCHasGroup())
        {
            if (!director) { return; }
            int memberIndex = 0;
            while (memberIndex < HCXExpansionBridge.HCHoldCount(m_HCHold))
            {
                DayZPlayerImplement retiringMember = HCXExpansionBridge.HCHoldGetMember(m_HCHold, memberIndex);
                if (retiringMember && (director.NearestPlayer(retiringMember.GetPosition()) < 200 || director.SeenByPlayer(retiringMember.GetPosition()))) { return; }
                memberIndex++;
            }
        }
        this.HCEndPatrol();
    }
    // Terminal teardown keeps persistence, bodies, provider despawn, then retirement.
    void HCEndPatrol()
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        bool intact = false;
        if (HCXExpansionBridge.HCHoldAliveFinal(m_HCHold)) { intact = HCXExpansionBridge.HCHoldCountFinal(m_HCHold) >= m_NumberOfAI && HCXExpansionBridge.HCHoldDeceasedCountFinal(m_HCHold) == 0; }
        m_HCSurvivors = HCXExpansionBridge.HCHoldCountFinal(m_HCHold);
        bool wasLive = m_HCLive;
        bool raided = wasLive && !intact;
        // A set provider slot with no hold means the real group was never read: do not persist
        // a "cleared" site from a defaulted count.
        bool holdLost = this.HCHasGroup() && !m_HCHold;
        if (raided && director && !holdLost) { director.RecordCleared(this); }
        this.HCPreserveBodies();
        this.HCBridgeDespawn(false);
        if (!this.HCHasGroup()) { this.HCReleaseHold(); }
        m_HCPendingMembers = 0;
        m_HCLive = false;
        if (!m_HCTransient && !this.HCHasGroup()) { HCAIBudget.Release("site:" + m_HCSiteId); }
        // No hold means the group was never read: not intact, not raided. Leave the respawn timer
        // alone and do not report the despawn as a raid outcome.
        if (holdLost)
        {
            if (wasLive) { Print("[HC Expansion AI] site " + m_HCSiteId + " despawn without a group hold; respawn timer and outcome left unchanged"); }
            return;
        }
        if (intact || raided) { m_TimeSinceLastSpawn = m_RespawnTime; }
        if (wasLive && director) { director.Despawned(this, intact); }
    }
    override void OnUpdate()
    {
        if (m_HCFinished || HCXExpansionBridge.HCSitePatrolBeingDestroyed(this)) { HCXExpansionBridge.HCSitePatrolStop(this); return; }
        if (m_HCDeathHeld) { this.HCDeathHoldStep(); return; }
        if (m_HCDeathResumePending)
        {
            // Cleanup and this timer tick can be separated by several seconds.
            if (!this.HCGroupIfSafe()) { this.HCEndPatrol(); return; }
            m_HCDeathResumePending = false;
        }
        if (m_HCDeferredMember >= 0)
        {
            // Revalidate without the positive listing cache before deferred resume.
            if (!this.HCGroupIfSafe()) { this.HCEndPatrol(); return; }
            int deferred = m_HCDeferredMember;
            m_HCDeferredMember = -1;
            HCXExpansionBridge.HCSitePatrolSpawnDeferred(this, deferred);
            return;
        }
        this.HCHoldMembers();
        this.HCBridgeOnUpdate();
    }
    override void SetupAI(eAIBase ai)
    {
        if (!this.HCBridgeSetupAI(ai)) { return; }
        // Deferred members still carry their temporary provider group here; hold m_Group instead.
        if (this.HCHasGroup())
        {
            this.HCHoldMembers();
            if (m_HCHold) { m_HCHold.Track(ai); }
        }
        else { this.HCHoldGroup(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(ai), ai); }
        HCXAffiliationCues.Actor(ai, m_Faction);
        HCXExpansionBridge.HCBaseSetUnlimitedReload(ai, 0);
        HCXExpansionBridge.HCBaseSetLootingBehavior(ai, 0);
        ai.m_eAI_EnableFlankingOutsideCombat = false;
        HCXExpansionBridge.HCBaseSetDamageMultiplier(ai, 1);
        HCXExpansionBridge.HCBaseSetDamageReceivedMultiplier(ai, 1);
        ai.m_eAI_HeadshotResistance = 0;
        ai.HCXAI_LeaseOwned = true;
        if (!ai.HCXAI_Fair() || ai.m_eAI_LootingBehavior != 0)
        {
            Print("[HC Expansion AI] site " + m_HCSiteId + " actor failed the fairness check; removed");
            HCXExpansionBridge.HCBaseDespawn(ai);
        }
        else
        {
            HCModuleReadiness.HCUse("optional-expansion-human-ai", "actor_spawned");
        }
    }
}
class HCXAISitePatrols : HCXAISiteSurvey
{
    // Create() refusal prints: once per site and reason (a changed reason prints again), at most
    // 64 lines per session, so a zone retried every minute never fills the log in a soak.
    protected ref map<string, string> m_HCCreateRefusalLogged = new map<string, string>;
    protected int m_HCCreateRefusalLogs;
    protected void HCCreateRefused(string siteId, string reason, string line)
    {
        string logged;
        if (m_HCCreateRefusalLogged.Find(siteId, logged) && logged == reason) { return; }
        if (m_HCCreateRefusalLogs >= 64) { return; }
        m_HCCreateRefusalLogged.Set(siteId, reason);
        m_HCCreateRefusalLogs++;
        Print("" + line);
    }
    override protected int HCLocalityPageCount()
    {
        int count = 0;
        foreach (HCXAISiteState state : m_States)
        {
            if (state.LocalityId != "") { count++; }
        }
        return count;
    }
    override protected bool HCHasSite(string id)
    {
        foreach (HCXAISiteState state : m_States)
        {
            if (!state.Transient && state.Site.Id == id) { return true; }
        }
        return false;
    }
    override protected void HCAddLegacySites()
    {
        foreach (HCXAISite site : m_Policy.Sites)
        {
            if (site.Checkpoint && !HCXAIQualification.EncountersEnabled()) { continue; }
            if (this.HCHasSite(site.Id)) { continue; }
            HCXAISiteState added = new HCXAISiteState();
            added.Site = site;
            m_States.Insert(added);
            m_AdmittedTotal++;
        }
    }
    override protected void HCLocalityFault()
    {
        if (m_LocalityRefused) { return; }
        m_LocalityRefused = true;
        if (m_LocalitySave) { HCSaveScheduler.HCUnregister(m_LocalitySave); }
        m_LocalitySave = null;
        m_Localities = null;
        m_LocalityStatus = "off:rotation_fault_legacy_sites_retained";
        m_CoverageFault = "LOCALITY_ROTATION_FAULT_LEGACY_SITES_RETAINED";
        foreach (HCXAISiteState retained : m_States) { retained.LocalityId = ""; }
        if (m_Phase == "run" || m_Phase == "bind" || m_Phase == "qualify" || m_Phase == "create")
        {
            this.HCAddLegacySites();
            m_Phase = "bind";
            m_Cursor = 0;
        }
        Print(this.HCLocalitySummary());
    }
    override protected void HCMakeNearbyRoom()
    {
        if (this.HCLocalityPageCount() < HCXAISiteRules.HCPageSize(m_Localities, HCAILimits.Get().MaxActiveSites)) { return; }
        int victim = -1;
        float farthest = 0;
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        for (int index = 0; index < m_States.Count() && index < 64; index++)
        {
            HCXAISiteState state = m_States[index];
            if (state.Transient || state.LocalityId == "" || this.HCWithinActivation(state.Site)) { continue; }
            if (state.Patrol && (state.Patrol.HCDeathHeld() || state.Patrol.m_HCPendingMembers > 0 || (HCXExpansionBridge.HCHoldCountFinal(state.Patrol.HCGroupHold()) > 0))) { continue; }
            if (encounters && encounters.SiteBound(state.Site.Id)) { continue; }
            float gap = this.HCPlayerGap(state.Site);
            if (gap <= farthest) { continue; }
            victim = index;
            farthest = gap;
        }
        if (victim < 0) { return; }
        HCXAISiteState retired = m_States[victim];
        this.HCRecordRouteState(retired);
        if (retired.Patrol) { retired.Patrol.m_HCFinished = true; HCXExpansionBridge.HCSitePatrolStop(retired.Patrol); HCXExpansionBridge.HCSitePatrolDelete(retired.Patrol); }
        retired.Patrol = null;
        HCAIBudget.Release("site:" + retired.Site.Id);
        m_States.RemoveOrdered(victim);
    }
    override protected void HCTryLocality(int now)
    {
        HCXAISite nearby;
        if (m_NearSite >= 0)
        {
            nearby = m_Policy.Sites[m_NearSite];
            int nearLocality = m_SiteLocalities.Get(nearby.Id);
            HCXAILocalityCoverage nearCoverage = m_CoverageRows.Get(m_Localities.Localities[nearLocality].Id);
            if (!nearCoverage || now < nearCoverage.RetryAt || this.HCHasSite(nearby.Id) || !this.HCWithinActivation(nearby)) { nearby = null; m_NearSite = -1; }
            else { this.HCMakeNearbyRoom(); }
        }
        if (this.HCLocalityPageCount() >= HCXAISiteRules.HCPageSize(m_Localities, HCAILimits.Get().MaxActiveSites)) { return; }
        if (m_LocalitySave.HCSelectionBlocked()) { return; }
        if (m_SelectionPending)
        {
            foreach (HCXAISite pendingSite : m_SelectionPending)
            {
                if (this.HCHasSite(pendingSite.Id)) { continue; }
                HCXAISiteState pendingState = this.HCSurveyState(pendingSite);
                if (pendingState.Failed) { continue; }
                if (!pendingState.Qualified && !this.HCWithinActivation(pendingSite)) { continue; }
                pendingState.LocalityId = m_SelectionLocality;
                pendingState.OpportunityAt = now;
                m_States.Insert(pendingState);
                m_AdmittedTotal++;
            }
            m_SelectionPending = null;
            return;
        }
        HCXAILocalityRotation rotation = m_LocalitySave.Data;
        if (rotation.SelectionSerial >= 2147483646) { this.HCLocalityFault(); return; }
        int index;
        if (nearby) { index = m_SiteLocalities.Get(nearby.Id); m_NearSite = -1; }
        else { index = HCXAISiteRules.HCNextLocality(m_Localities, rotation); }
        rotation.SelectionSerial++;
        HCXAILocality locality = m_Localities.Localities[index];
        HCXAILocalityCoverage row = HCXAISiteRules.HCCoverage(rotation, locality.Id);
        array<ref HCXAISite> selected = new array<ref HCXAISite>();
        int slots = HCXAISiteRules.HCPageSize(m_Localities, HCAILimits.Get().MaxActiveSites) - this.HCLocalityPageCount();
        if (now >= row.RetryAt)
        {
            row.LastSelected = rotation.SelectionSerial;
            if (!row.Pending) { row.PendingSinceSerial = rotation.SelectionSerial; }
            row.Pending = true;
            row.RetryAt = now + HCXAISiteRules.HCRetrySeconds(m_Localities);
            row.Refusal = "route_not_reviewed";
            if (locality.Island) { row.Refusal = "island_access_route_unreviewed"; }
            if (locality.SiteIds.Count() == 0) { row.Refusal = "authored_site_data_missing"; }
            if (nearby) { selected.Insert(nearby); }
            int tries = 0;
            while (!nearby && tries < locality.SiteIds.Count() && selected.Count() < slots)
            {
                int siteIndex = row.NextSite % locality.SiteIds.Count();
                string siteId = locality.SiteIds[siteIndex];
                row.NextSite = (siteIndex + 1) % locality.SiteIds.Count();
                tries++;
                if (this.HCHasSite(siteId)) { continue; }
                foreach (HCXAISite candidate : m_Policy.Sites)
                {
                    if (candidate.Id != siteId) { continue; }
                    if (candidate.Checkpoint && !HCXAIQualification.EncountersEnabled()) { row.Refusal = "checkpoint_gate_pending"; break; }
                    selected.Insert(candidate);
                    break;
                }
            }
            if (selected.Count() > 0) { row.Refusal = "route_provider_pending"; }
        }
        // This checkpoint is not an unchanged periodic rewrite: NextId and
        // SelectionSerial advanced, plus the selected row cursor/retry state.
        // Persist before geometry/admission to retain fair rotation on restart.
        m_LocalitySave.HCChanged();
        m_LocalitySave.HCUrgent = true;
        m_SelectionPending = selected;
        m_SelectionLocality = locality.Id;
        if (selected.Count() == 0)
        {
            if (locality.SiteIds.Count() == 0) { return; }
            if (row.LastSelected == rotation.SelectionSerial && now >= m_LocalityNextPendingLogAt)
            {
                m_LocalityNextPendingLogAt = now + 300;
                Print("[HC Plan] HC-18 state=pending locality=" + locality.Id + " reason=" + row.Refusal + " pending=1 runtime=PENDING");
            }
            return;
        }
    }
    override protected void HCStepLocalities()
    {
        if (!m_Localities || !m_LocalitySave || m_LocalityRefused) { return; }
        if (m_LocalitySave.Fault) { this.HCLocalityFault(); return; }
        int now = HCXExpansionBridge.HCGetTimestamp();
        if (now < 1 || now > 2146878847) { this.HCLocalityFault(); return; }
        if (!this.HCTakeSiteUnits(2)) { return; }
        m_LocalityUnits.HCReset(HCXAISiteDirector.WORK_PER_TICK + HCXAISiteRules.HCAttemptsPerTick(m_Localities));
        m_LocalityWork.HCReset(HCXAISiteDirector.WORK_PER_TICK, Math.Min(HCPerfConfig.HCGet().SliceMs, 2));
        this.HCScanNearby(now);
        if (m_LocalitySave.HCUrgent && m_LocalitySave.HCDirty && (!HCPerfConfig.HCGet().EnableSharedSaves || !HCSaveScheduler.HCRegistered(m_LocalitySave)))
        {
            if (m_LocalityWork.HCContinue() && this.HCTakeLocalityUnit())
            {
                HCSaveScheduler.HCPumpFallback(m_LocalitySave);
                if (m_LocalitySave.Fault) { this.HCLocalityFault(); return; }
            }
        }
        bool admissionTurn = m_LocalityAdmissionTurn;
        m_LocalityAdmissionTurn = !m_LocalityAdmissionTurn;
        if (!m_LocalitySave.HCSelectionBlocked() && (m_SelectionPending || (admissionTurn && (m_NearSite >= 0 || now >= m_LocalityNextAttemptAt))))
        {
            if (m_LocalityWork.HCContinue() && this.HCTakeLocalityUnit())
            {
                int selectionBegan = TickCount(0);
                this.HCTryLocality(now);
                this.HCSiteStageCost("locality_selection", selectionBegan);
                m_LocalityNextAttemptAt = now + HCXAISiteRules.HCSelectionIntervalSeconds(m_Localities);
            }
            if (m_LocalityRefused) { return; }
        }
        int refusedThisSlice = 0;
        int visited = 0;
        int count = m_States.Count();
        float nearestWork = 1000000000;
        for (int workIndex = 0; workIndex < count && workIndex < 64; workIndex++)
        {
            HCXAISiteState waiting = m_States[workIndex];
            if (waiting.LocalityId == "" || waiting.Failed || waiting.Patrol) { continue; }
            float workGap = this.HCPlayerGap(waiting.Site);
            float workRadius = this.HCActivationRadius(waiting.Site, false);
            if (workGap > workRadius * workRadius || workGap >= nearestWork) { continue; }
            nearestWork = workGap;
            m_LocalityCursor = workIndex;
        }
        while (visited < count && visited < HCXAISiteDirector.WORK_PER_TICK && m_States.Count() > 0 && m_LocalityWork.HCContinue() && this.HCTakeLocalityUnit())
        {
            if (m_LocalityCursor >= m_States.Count()) { m_LocalityCursor = 0; }
            HCXAISiteState state = m_States[m_LocalityCursor];
            visited++;
            if (state.LocalityId == "") { m_LocalityCursor++; continue; }
            this.HCRecordRouteState(state);
            bool expired = m_Policy.Sites.Count() > HCXAISiteRules.HCPageSize(m_Localities, HCAILimits.Get().MaxActiveSites) && now >= state.OpportunityAt + HCXAISiteRules.HCOpportunitySeconds(m_Localities);
            bool live = state.Patrol && (state.Patrol.HCDeathHeld() || state.Patrol.m_HCPendingMembers > 0 || (HCXExpansionBridge.HCHoldCountFinal(state.Patrol.HCGroupHold()) > 0));
            if (state.Patrol && !state.Patrol.HCDeathHeld() && HCXExpansionBridge.HCHoldCountFinal(state.Patrol.HCGroupHold()) > 0)
            {
                HCXAILocalityCoverage observed = HCXAISiteRules.HCCoverage(m_LocalitySave.Data, state.LocalityId);
                if (observed.Pending)
                {
                    observed.Pending = false;
                    observed.LastObserved = observed.LastSelected;
                    observed.Refusal = "";
                    m_LocalitySave.HCChanged();
                }
            }
            HCXAIEncounters encounters = HCXAIEncounters.Active();
            bool boundEncounter = encounters && encounters.SiteBound(state.Site.Id);
            if ((expired || state.Failed) && !live && !boundEncounter)
            {
                if (state.Patrol) { state.Patrol.m_HCFinished = true; HCXExpansionBridge.HCSitePatrolStop(state.Patrol); HCXExpansionBridge.HCSitePatrolDelete(state.Patrol); }
                state.Patrol = null;
                HCAIBudget.Release("site:" + state.Site.Id);
                m_States.RemoveOrdered(m_LocalityCursor);
                continue;
            }
            m_LocalityCursor++;
            if (state.Failed || state.Patrol) { continue; }
            bool createFailed = false;
            bool pathIssued = false;
            if (!state.Bound) { this.Bind(state); }
            else if (!state.Qualified)
            {
                int pathCallsBefore = state.PathCalls;
                int qualifyBegan = TickCount(0);
                this.QualifyStep(state);
                this.HCSiteStageCost("qualification", qualifyBegan);
                if (state.PathCalls > pathCallsBefore)
                {
                    pathIssued = true;
                    m_LocalityUnits.HCCharge(63);
                    HCServer.HCTickWork().HCCharge(63);
                }
            }
            else
            {
                this.Create(state);
                createFailed = !state.Patrol;
            }
            this.HCRecordRouteState(state);
            if (state.Failed || createFailed)
            {
                HCXAILocalityCoverage row = HCXAISiteRules.HCCoverage(m_LocalitySave.Data, state.LocalityId);
                row.Pending = true;
                row.Refusal = "route_geometry_or_provider_refused";
                row.RetryAt = now + HCXAISiteRules.HCRetrySeconds(m_Localities);
                m_LocalitySave.HCChanged();
                if (createFailed) { state.OpportunityAt = now - HCXAISiteRules.HCOpportunitySeconds(m_Localities); }
                this.HCRecordRouteState(state);
                refusedThisSlice++;
            }
            if (pathIssued) { break; }
        }
        if (refusedThisSlice > 0)
        {
            Print("[HC Plan] HC-18 state=refused count=" + refusedThisSlice.ToString() + " reason=route_geometry_or_provider_refused pending=1 runtime=PENDING");
        }
    }
    override string BudgetProblem(int actorCap, HCXAISitePatrol exceptPatrol)
    {
        int reservedSites = 0;
        int reservedActors = 0;
        foreach (HCXAISiteState reservation : m_States)
        {
            if (reservation.Completed) { continue; }
            if (exceptPatrol && reservation.Patrol == exceptPatrol) { continue; }
            if (!(reservation.Transient && !reservation.Materialized))
            {
                if (!reservation.Patrol || (!reservation.Patrol.HCDeathHeld() && (!HCXExpansionBridge.HCHoldAliveFinal(reservation.Patrol.HCGroupHold()) || (HCXExpansionBridge.HCHoldCountFinal(reservation.Patrol.HCGroupHold()) == 0 && reservation.Patrol.m_HCPendingMembers <= 0))))
                {
                    if (!reservation.Transient) { HCAIBudget.Release("site:" + reservation.Site.Id); }
                    continue;
                }
            }
            reservedSites++;
            reservedActors += reservation.Site.NumberOfAIMax;
        }
        if (reservedSites >= HCAILimits.Get().MaxLiveGroups || reservedActors + actorCap > HCAILimits.Get().MaxLiveAI) { return "global AI budget reached"; }
        if (reservedSites >= HCAILimits.Get().MaxActiveSites) { return "site budget reached"; }
        if (reservedActors + actorCap > HCAILimits.Get().MaxActiveAI) { return "AI budget reached"; }
        return "";
    }
    override protected void StepCreate()
    {
        if (!this.HCTakeSiteUnits(8)) { return; }
        HCWorkBudget slice = new HCWorkBudget;
        slice.HCReset(HCXAISiteDirector.WORK_PER_TICK, Math.Min(HCPerfConfig.HCGet().SliceMs, 2));
        int work = 0;
        while (work < HCXAISiteDirector.WORK_PER_TICK && m_Cursor < m_States.Count() && slice.HCContinue())
        {
            HCXAISiteState state = m_States[m_Cursor];
            m_Cursor++;
            if (!state.Qualified || state.Patrol) { continue; }
            this.Create(state);
            work++;
        }
        if (m_Cursor < m_States.Count()) { return; }
        int created = 0;
        string ids = "";
        foreach (HCXAISiteState counted : m_States)
        {
            if (!counted.Patrol) { continue; }
            created++;
            ids = ids + " " + counted.Site.Id;
        }
        Print("[HC Expansion AI] sites created: " + created.ToString() + " native dynamic patrols (activate when a player is inside ActivationRadius and every player is beyond MinPlayerDistance):" + ids);
        m_Phase = "run";
    }
    override protected void Create(HCXAISiteState state)
    {
        HCXAISite site = state.Site;
        ExpansionAIDynamicSpawnBase config = new HCXAISiteSpawnConfig();
        config.Name = "HC:" + site.Id;
        string populationKind = site.Kind;
        if (site.Kind == "holdout") { populationKind = "occupation"; }
        if (site.Kind == "scavenger") { populationKind = "party"; }
        int population = HCAILimits.GroupSize(HCAILimits.Get().WorldSeed, site.Id, populationKind);
        if (state.Transient) { population = site.NumberOfAIMax; }
        HCXZoneGuardsSite zoneSite = HCXZoneGuardsSite.Cast(site);
        if (zoneSite) { population = zoneSite.Members; }
        site.NumberOfAI = population;
        site.NumberOfAIMax = population;
        config.NumberOfAI = population;
        config.NumberOfAIMax = population;
        config.Speed = site.Speed;
        config.UnderThreatSpeed = "SPRINT";
        config.Behaviour = HCXAISiteRules.PatrolBehaviour(site.Behaviour, state.OpenRoute);
        config.Faction = HCXFactions.SiteFaction(site);
        if (state.Transient) { config.Faction = state.ProviderFaction; }
        if (zoneSite) { config.Faction = zoneSite.ProviderFaction; }
        config.Loadout = site.Loadout;
        config.Persist = false;
        config.CanBeLooted = true;
        config.UnlimitedReload = 0;
        config.Chance = 1.0;
        config.CanBeTriggeredByAI = false;
        config.CanSpawnInContaminatedArea = false;
        config.MinDistRadius = 0;
        config.MaxDistRadius = this.HCActivationRadius(site, state.Transient);
        config.DespawnRadius = config.MaxDistRadius + 100;
        config.DespawnTime = site.DespawnSeconds;
        config.RespawnTime = HCXAISiteDirector.HCRespawnDelay(site, m_Policy);
        if (state.Transient) { config.RespawnTime = -1; }
        config.MinSpreadRadius = 0;
        config.MaxSpreadRadius = 0;
        config.DamageMultiplier = 1;
        config.DamageReceivedMultiplier = 1;
        config.HeadshotResistance = 0;
        config.ShoryukenChance = 0;
        config.ShoryukenDamageMultiplier = 1;
        config.EnableFlankingOutsideCombat = 0;
        config.AccuracyMin = HCXAISiteRules.AccuracyMin(site.Kind);
        config.AccuracyMax = HCXAISiteRules.AccuracyMax(site.Kind);
        config.ThreatDistanceLimit = HCXAISiteRules.ThreatDistance(site.Kind);
        config.NoiseInvestigationDistanceLimit = HCXAISiteRules.NoiseDistance(site.Kind);
        config.MaxFlankingDistance = HCXAISiteRules.FlankDistance(site.Kind);
        config.LootingBehaviour = "NONE";
        config.UseRandomWaypointAsStartPoint = false;
        if (site.Kind == "holdout")
        {
            config.Formation = "File";
            config.FormationScale = 1.0;
        }
        config.Waypoints = new TVectorArray();
        foreach (vector point : state.PatrolPoints)
        {
            config.Waypoints.Insert(point);
        }
        string providerIssue = HCXAIQualification.ProviderProblem();
        if (providerIssue == "" && !HCXFactions.Registered(config.Faction)) { providerIssue = "unregistered faction '" + config.Faction + "'"; }
        if (providerIssue == "") { providerIssue = HCXAIRules.PatrolProblem(config, state.PatrolPoints); }
        if (providerIssue != "")
        {
            this.HCCreateRefused(site.Id, providerIssue, "[HollowCountry] Living AI admission refused: " + site.Id + ": " + providerIssue);
            return;
        }
        HCXAISitePatrol patrol = HCXExpansionBridge.HCCreatePatrol(config, vector.Zero);
        if (!patrol)
        {
            this.HCCreateRefused(site.Id, "native_patrol_setup", "[HC Expansion AI] site " + site.Id + " native patrol setup refused");
            return;
        }
        patrol.m_HCSiteId = site.Id;
        patrol.m_HCKind = site.Kind;
        patrol.m_HCGroupMax = site.NumberOfAIMax;
        patrol.m_HCAuthoredMin = site.NumberOfAI;
        patrol.m_HCAuthoredMax = site.NumberOfAIMax;
        patrol.m_HCTransient = state.Transient;
        state.Patrol = patrol;
        if (!state.Transient) { Print("[HC Expansion AI] site " + site.Id + " configured respawn=" + config.RespawnTime.ToString() + "s; raid timestamps persist in expansion-ai-owned.json"); }
    }
    override string SpawnProblemFor(HCXAISitePatrol patrol)
    {
        if (!m_Policy || m_Phase != "run") { return "sites not running"; }
        if (patrol.m_HCFinished) { return "transient site completed"; }
        if (!m_OwnedSaved) { return "raid ownership save pending"; }
        foreach (HCXAISiteState raidState : m_States)
        {
            if (raidState.Patrol != patrol || raidState.Transient) { continue; }
            if (this.RaidLocked(raidState.Site, HCXExpansionBridge.HCGetTimestamp())) { return "raided site lockout"; }
        }
        string providerIssue = HCXAIQualification.ProviderProblem();
        if (providerIssue != "") { return providerIssue; }
        string sharedBudget = this.BudgetProblem(patrol.m_HCGroupMax, patrol);
        if (sharedBudget != "") { return sharedBudget; }
        int activeSites = 0;
        int activeAI = 0;
        foreach (HCXAISiteState state : m_States)
        {
            if (state.Completed || !state.Patrol || state.Patrol == patrol || !HCXExpansionBridge.HCHoldAliveFinal(state.Patrol.HCGroupHold())) { continue; }
            if (!state.Patrol.HCDeathHeld() && HCXExpansionBridge.HCHoldCountFinal(state.Patrol.HCGroupHold()) == 0 && state.Patrol.m_HCPendingMembers <= 0) { continue; }
            activeSites++;
            activeAI = activeAI + state.Patrol.m_NumberOfAI;
        }
        if (activeSites >= HCAILimits.Get().MaxLiveGroups || activeAI + patrol.m_HCGroupMax > HCAILimits.Get().MaxLiveAI) { return "global AI budget reached"; }
        return HCXAISiteRules.SpawnProblem(m_Policy, activeAI, activeSites, patrol.m_HCGroupMax, this.NearestPlayer(patrol.m_Position), this.SeenByPlayer(patrol.m_Position));
    }
    override string MemberProblemFor(vector pos)
    {
        if (!m_Policy || m_Phase != "run") { return "sites not running"; }
        string memberIssue = HCXAIQualification.ProviderProblem();
        if (memberIssue != "") { return memberIssue; }
        return HCXAISiteRules.MemberSpawnProblem(m_Policy, this.NearestPlayer(pos), this.SeenByPlayer(pos));
    }
    override protected void HCRefreshPlayers()
    {
        int now = GetGame().GetTime();
        if (m_PlayersAt >= 0 && now >= m_PlayersAt && now - m_PlayersAt < 1000) { return; }
        m_PlayersAt = now;
        m_Players.Copy(HCPerfPlayers.HCGet()); // native EnScript.c:499 array.Copy
        if (!m_GroupScaling) { return; }
        m_OnlinePlayers = 0;
        foreach (Man connected : m_Players)
        {
            if (connected && connected.GetIdentity()) { m_OnlinePlayers++; }
        }
    }
    override protected void HCRefreshGroupFactor()
    {
        if (!m_GroupScaling) { return; }
        this.HCRefreshPlayers();
        if (m_ScalePlayers == m_OnlinePlayers) { return; }
        m_ScalePlayers = m_OnlinePlayers;
        m_GroupFactor = HCXAISiteRules.HCGroupFactor(m_OnlinePlayers);
        Print("[HC Expansion AI] group scale players=" + m_OnlinePlayers.ToString() + " factor=" + m_GroupFactor.ToString());
    }
    override float NearestPlayer(vector pos)
    {
        this.HCRefreshPlayers();
        float nearest = 100000;
        foreach (Man player : m_Players)
        {
            if (!player || !player.GetIdentity() || !player.IsAlive()) { continue; }
            float gap = vector.Distance(player.GetPosition(), pos);
            if (gap < nearest) { nearest = gap; }
        }
        return nearest;
    }
    override bool SeenByPlayer(vector pos)
    {
        this.HCRefreshPlayers();
        vector aim = pos + Vector(0, 1.2, 0);
        foreach (Man player : m_Players)
        {
            if (!player || !player.GetIdentity() || !player.IsAlive()) { continue; }
            if (vector.DistanceSq(player.GetPosition(), pos) > m_Policy.LineOfSightRange * m_Policy.LineOfSightRange) { continue; }
            vector eye = player.GetPosition() + Vector(0, 1.6, 0);
            vector contact;
            vector contactDir;
            int component;
            bool hit = DayZPhysics.RaycastRV(eye, aim, contact, contactDir, component, null, null, player);
            if (!hit || vector.Distance(contact, aim) < 1.0) { return true; }
        }
        return false;
    }
    override void Spawned(HCXAISitePatrol patrol)
    {
        m_SpawnedTotal++;
        if (!patrol.m_HCTransient)
        {
            HCXAIOwnedRow freshRow = this.OwnershipRow(patrol.m_HCSiteId);
            if (freshRow) { freshRow.ClearedAt = 0; freshRow.PartialRaid = false; }
        }
        foreach (HCXAISiteState spawnedState : m_States)
        {
            if (!spawnedState.Transient || spawnedState.Patrol != patrol || spawnedState.Materialized) { continue; }
            spawnedState.Materialized = true;
            HCXMaterializerBridge.SiteSpawned();
        }
        int spawnX = Math.Round(patrol.m_Position[0]);
        int spawnZ = Math.Round(patrol.m_Position[2]);
        Print("[HC Expansion AI] Spawning " + patrol.m_NumberOfAI.ToString() + " AI HC:" + patrol.m_HCSiteId + " at " + spawnX.ToString() + " " + spawnZ.ToString());
        this.HCQueueOwned();
    }
    override void Despawned(HCXAISitePatrol patrol, bool intact)
    {
        foreach (HCXAISiteState endedState : m_States)
        {
            if (endedState.Transient && endedState.Patrol == patrol) { this.FinishTransient(endedState, true, patrol.m_HCSurvivors); }
        }
        Print("[HC Expansion AI] site " + patrol.m_HCSiteId + " despawned (intact=" + intact.ToString() + ")");
        this.HCQueueOwned();
    }
    override protected void HCStepRespawns()
    {
        if (!m_Policy || m_States.Count() == 0 || m_RespawnOff) { return; }
        int checked = 0;
        while (checked < HCXAISiteDirector.WORK_PER_TICK && checked < m_States.Count())
        {
            if (m_RespawnCursor >= m_States.Count()) { m_RespawnCursor = 0; }
            HCXAISiteState respawnState = m_States[m_RespawnCursor];
            int cost = 1;
            if (respawnState.Patrol) { cost += respawnState.Patrol.m_HCGroupMax; }
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_AI_RESPAWN, cost)) { return; }
            m_RespawnCursor++;
            checked++;
            if (respawnState.Patrol) { this.HCRefreshDepleted(respawnState.Patrol); }
        }
    }
    override void HCRefreshDepleted(HCXAISitePatrol patrol)
    {
        if (patrol.HCDeathHeld()) { return; }
        if (!m_Policy || m_Phase != "run" || !m_OwnedSaved || patrol.m_HCTransient || !HCXExpansionBridge.HCHoldAlive(patrol.HCGroupHold()) || patrol.m_HCPendingMembers > 0) { return; }
        if (m_RespawnOff) { return; }
        int surviving = HCXExpansionBridge.HCHoldCount(patrol.HCGroupHold());
        if (surviving >= patrol.m_NumberOfAI || (surviving > 0 && HCXExpansionBridge.HCHoldIsInCombat(patrol.HCGroupHold()))) { return; }
        HCXAIOwnedRow deathRow = this.OwnershipRow(patrol.m_HCSiteId);
        if (!deathRow || deathRow.ClearedAt <= 0) { return; }
        int now = HCXExpansionBridge.HCGetTimestamp();
        if (now < 1) { return; }
        array<ref HCXAISiteState> freshStates = m_States;
        foreach (HCXAISiteState freshState : freshStates)
        {
            if (freshState.Patrol != patrol) { continue; }
            if (now < deathRow.ClearedAt || now - deathRow.ClearedAt < this.HCDeathDelay(freshState.Site, deathRow)) { return; }
            int liveIndex = 0;
            while (liveIndex < HCXExpansionBridge.HCHoldCount(patrol.HCGroupHold()))
            {
                DayZPlayerImplement liveMember = HCXExpansionBridge.HCHoldGetMember(patrol.HCGroupHold(), liveIndex);
                if (liveMember && this.MemberProblemFor(liveMember.GetPosition()) != "") { return; }
                liveIndex++;
            }
            HCXExpansionBridge.HCSitePatrolDespawn(patrol);
            if (!patrol.HCHasGroup()) { patrol.m_TimeSinceLastSpawn = patrol.m_RespawnTime; }
            return;
        }
    }
}
class HCXCheckpointProp
{
    ref HCXAISite Site;
    Object Table;
    int QuietSince = -1;
    int Attempts;
    int LastAttempt = -1;
    bool Finished;
}
class HCXCheckpointProps
{
    protected ref array<ref HCXCheckpointProp> m_Props = new array<ref HCXCheckpointProp>();
    protected int m_Cursor;
    protected ref HCPathgraphRefresh m_PathgraphPending;
    protected void HCStartRefused(string problem)
    {
        Print("[HollowCountry] Checkpoints props not placed: " + problem + "; runtime=PENDING");
    }
    void Start()
    {
        HCXAISitePolicy policy = HCXAISiteDirector.LoadPolicy();
        if (!policy) { this.HCStartRefused("policy unavailable"); return; }
        string policyProblem = HCXAISiteRules.PolicyProblem(policy);
        if (policyProblem != "") { this.HCStartRefused(policyProblem); return; }
        if (!GetGame() || !HCBuildIdentity.SameWorld(policy.WorldName, GetGame().GetWorldName())) { this.HCStartRefused("policy world differs from the running world"); return; }
        foreach (HCXAISite site : policy.Sites)
        {
            if (!site.Checkpoint) { continue; }
            if (m_Props.Count() >= 3) { this.HCStartRefused("checkpoint prop cap=3 reached at " + site.Id); return; }
            string siteProblem = HCXAIRules.CheckpointProblem(site);
            if (siteProblem != "") { this.HCStartRefused(site.Id + ": " + siteProblem); return; }
            HCXCheckpointProp row = new HCXCheckpointProp();
            row.Site = site;
            m_Props.Insert(row);
        }
    }
    protected void HCRetry(HCXCheckpointProp row, string reason)
    {
        row.QuietSince = -1;
        if (row.Attempts < 3) { return; }
        row.Finished = true;
        Print("[HollowCountry] Checkpoints prop refused: " + row.Site.Id + "; attempts=3; " + reason + "; runtime=PENDING");
    }
    void Step()
    {
        if (m_PathgraphPending)
        {
            // One post-snap region on the next props visit; never queue an
            // unbounded series of runtime marks or depend on the boot flush.
            m_PathgraphPending.Update();
            m_PathgraphPending = null;
            return;
        }
        if (!HCXAIQualification.EncountersEnabled() || m_Props.Count() == 0) { return; }
        HCXCheckpointProp row = m_Props[m_Cursor % m_Props.Count()];
        m_Cursor++;
        if (row.Finished) { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return; }
        vector wanted = row.Site.CheckpointProp;
        vector at = Vector(wanted[0], GetGame().SurfaceY(wanted[0], wanted[2]), wanted[2]);
        int nowMs = GetGame().GetTime();
        if (nowMs < 0 || director.NearestPlayer(at) < 200 || director.SeenByPlayer(at)) { row.QuietSince = -1; return; }
        if (row.LastAttempt >= 0)
        {
            if (nowMs < row.LastAttempt) { row.LastAttempt = nowMs; row.QuietSince = -1; return; }
            if (nowMs - row.LastAttempt < 600000) { return; }
        }
        if (row.QuietSince < 0 || nowMs < row.QuietSince) { row.QuietSince = nowMs; return; }
        if (nowMs - row.QuietSince < 5000) { return; }
        row.Attempts++;
        row.LastAttempt = nowMs;
        array<Object> objects = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition(at, 8, objects, cargos);
        if (objects.Count() > 128)
        {
            this.HCRetry(row, "nearby objects exceed cap=128 radius=8m");
            return;
        }
        foreach (Object candidate : objects)
        {
            if (!candidate) { continue; }
            if ((candidate.GetType() == "Land_Roadblock_Table_DE" || candidate.GetType() == "Land_Roadblock_Table") && vector.Distance(candidate.GetPosition(), at) < 2)
            {
                row.Table = candidate;
                row.Finished = true;
                return;
            }
        }
        foreach (Object nearbyHouse : objects)
        {
            if (nearbyHouse && House.Cast(nearbyHouse))
            {
                this.HCRetry(row, "House within 8m");
                return;
            }
        }
        row.Table = GetGame().CreateObjectEx("Land_Roadblock_Table_DE", at, ECE_SETUP | ECE_CREATEPHYSICS | ECE_KEEPHEIGHT | ECE_NOLIFETIME);
        if (!row.Table) { this.HCRetry(row, "native factory"); return; }
        HCGroundSnap.Snap(row.Table);
        m_PathgraphPending = new HCPathgraphRefresh();
        m_PathgraphPending.Include(row.Table);
        row.Finished = true;
        Print("[HollowCountry] Checkpoints props present: " + row.Site.Id + "; empty roadside table remains if guards unavailable");
    }
}
