// Shared state: SiteBase -> SiteStorage -> SiteSurvey -> SitePatrols -> SiteDirector.
// Base virtual seams preserve picker/caravan/routes modded dispatch regardless of file order.
// Native scripts-1.30.164289: AIWorld PGFilter/FindPath, Game GetTime/GetPlayers/SurfaceY,
// Object GetPosition/IsAlive, DayZPhysics RaycastRV.
modded class HCXAIOwnedRow
{
    int ClearedAt = 0;
    bool PartialRaid = false;
}
class HCXAISiteState : Managed
{
    ref HCXAISite Site;
    HCXAISitePatrol Patrol;
    ref HCReleaseRadius ReleaseRadius;
    ref array<vector> Points = new array<vector>();
    ref array<vector> Sampled = new array<vector>();
    ref array<vector> PatrolPoints = new array<vector>();
    string Key;
    bool Bound;
    ref HCGapcodeRouteHashState HCBindHash;
    string HCBindText;
    int HCBindCursor;
    bool Qualified;
    bool Failed;
    bool Cached;
    bool HCRouteCacheChecked;
    ref HCXAIRouteRow HCCachedRoute;
    int HCCacheCursor;
    string Reason;
    int Leg;
    int ChainSteps;
    float ChainLength;
    vector ChainFrom;
    vector ClosestEnd;
    float ClosestGap;
    int PathCalls;
    int Continuations;
    ref TVectorArray HCPath = new TVectorArray();
    bool HCPathReady;
    int HCPathCursor;
    float HCPathLength;
    ref array<vector> AttemptPoints = new array<vector>();
    int StartIndex;
    int Kept = 1;
    int Skipped;
    int Snapped;
    string SkippedPoints;
    bool Closed;
    bool OpenRoute;
    int HCOutdoorProbe;
    vector HCOutdoorBest;
    float HCOutdoorBestGap = 1000;
    int Outdoor;
    int IndoorFallback;
    int HCAiWorldWaits;
    Object HouseObject;
    vector CacheWorld;
    vector CacheOrientation;
    bool Diagnosed;
    bool Transient;
    bool Completed;
    bool Materialized;
    int AdmittedAt;
    int HCQualificationProgressAt;
    string ProposalId;
    string ProviderFaction;
    string LocalityId;
    int OpportunityAt;
}
class HCXAISiteBase : Managed
{
    protected string m_SpawnLogLine;
    protected float m_SpawnLogAt;
    protected string m_SitesLogLine;
    protected float m_SitesLogAt;
    protected int m_ReleaseRadiusCursor;
    static const string POLICY = "$profile:HollowCountry/expansion-ai-sites.json";
    static const string ROUTES = "$profile:HollowCountry/expansion-ai-routes.json";
    static const string CACHES = "$profile:HollowCountry/expansion-ai-caches.json";
    static const string OWNED = "$profile:HollowCountry/expansion-ai-owned.json";
    static const string DIAGNOSTIC = "$profile:HollowCountry/acceptance/xai_diagnostic_spawn.enable";
    static const string OBSERVER = "native-eai";
    static const int WORK_PER_TICK = 1;
    // Chain-version upgrade (stale "algorithm" rows, e.g. chain-v6 to chain-v7): at most this many rows are
    // discarded and requalified per boot. The rest keep their stored row and are replaced on later boots, so the
    // upgrade boot neither spikes the AI_SITES tick cost nor holds the route owner late. Sites with a player
    // inside their activation radius are exempt, so nobody meets an empty route they are standing next to.
    static const int HC_UPGRADE_REQUAL_PER_BOOT = 16;
    protected static HCXAISiteDirector s_Active;
    protected ref HCXAISitePolicy m_Policy;
    protected ref HCXAIRouteCache m_Routes;
    protected ref HCXAICacheJournal m_Caches;
    protected ref HCXAIOwnership m_Owned;
    protected ref HCXAIOwnership m_BootOwned;
    protected ref array<ref HCXAISiteState> m_States = new array<ref HCXAISiteState>();
    protected ref PGFilter m_Filter;
    protected ref PGFilter m_OutdoorFilter;
    protected string m_Build;
    protected string m_RouteValidity;
    protected string m_RouteLegacyTerm;
    protected int m_LegacyAccepted;
    protected int m_LegacyRefusedRequal;
    protected int m_AiWorldPostponed;
    protected ref map<string, bool> m_CacheReasons = new map<string, bool>();
    protected int m_CacheSampleTick = -1;
    protected int m_CacheSamples;
    protected int m_CacheHits;
    protected int m_Requalified;
    protected int m_UpgradeRequal;
    protected ref map<string, bool> m_UpgradeDeferred = new map<string, bool>();
    protected int m_CacheDiscarded;
    protected int m_CacheRetained;
    protected bool m_CacheReviewTurn;
    protected int m_CacheReviewCursor;
    protected ref array<string> m_CacheReviewIds = new array<string>();
    protected ref map<string, bool> m_CachePending = new map<string, bool>();
    protected ref map<string, ref HCXAISite> m_CachePolicy = new map<string, ref HCXAISite>();
    protected ref map<string, ref HCXAISiteState> m_CacheStates = new map<string, ref HCXAISiteState>();
    protected bool m_RoutesWarm;
    protected string m_Phase = "wait";
    protected int m_Cursor;
    protected int m_CacheCursor;
    protected int m_RespawnCursor;
    protected int m_RingCandidates;
    protected float m_RingDegrees;
    protected int m_Ticks;
    protected int m_RunStage;
    protected int m_TransientCursor;
    protected bool m_LocalityAdmissionTurn = true;
    protected int m_RingNextProbeMs;
    protected int m_AdmittedTotal;
    protected int m_SpawnedTotal;
    protected int m_RelocatedTotal;
    protected ref map<string, int> m_SpawnRefusals = new map<string, int>();
    protected ref map<string, int> m_SiteStagePeaks = new map<string, int>();
    void HCSpawnRefused(string reason)
    {
        if (reason == "") { return; }
        if (!m_SpawnRefusals.Contains(reason) && m_SpawnRefusals.Count() >= 23) { reason = "other"; }
        int count;
        m_SpawnRefusals.Find(reason, count);
        if (count < 2147483647) { m_SpawnRefusals.Set(reason, count + 1); }
    }
    protected void HCSiteStageCost(string stage, int began)
    {
        int elapsed = TickCount(began);
        int peak;
        if (m_SiteStagePeaks.Find(stage, peak) && elapsed <= peak) { return; }
        m_SiteStagePeaks.Set(stage, elapsed);
        if (elapsed >= 40000) { Print("[HC Expansion AI] site_stage=" + stage + " ticks_max=" + elapsed.ToString() + " runtime=PENDING"); }
    }
    protected bool m_Diagnostic;
    protected bool m_RespawnOff; // ai-respawn.disable, probed once at Start (the marker contract is probe-once)
    protected ref HCXAIRouteSave m_RouteSave;
    protected ref HCXAICacheSave m_CacheSave;
    protected ref HCXAIOwnedSave m_OwnedSave;
    protected ref map<string, HCXAIRouteRow> m_RouteRows = new map<string, HCXAIRouteRow>();
    protected ref map<string, int> m_RouteIndices = new map<string, int>();
    protected ref map<string, HCXAIOwnedRow> m_OwnedRows = new map<string, HCXAIOwnedRow>();
    protected ref map<string, HCXAICacheRow> m_CacheRows = new map<string, HCXAICacheRow>();
    protected bool m_LegacyRoutesDirty;
    protected bool m_WaitLogged;
    protected bool m_RadiusClampLogged;
    protected bool m_OwnedSaved = true;
    protected bool m_OwnershipClockFault;
    protected bool m_GroupScaling;
    protected float m_GroupFactor = 1.0;
    protected int m_OnlinePlayers;
    protected int m_ScalePlayers = -1;
    protected int m_PlayersAt = -1;
    protected ref array<Man> m_Players = new array<Man>();
    protected ref HCXAIPatrolDebug m_Debug;
    static const string LOCALITIES = "$profile:HollowCountry/expansion-ai-localities.json";
    protected ref HCXAILocalityCatalog m_Localities;
    protected ref HCXAILocalitySave m_LocalitySave;
    protected ref HCUnitBudget m_LocalityUnits = new HCUnitBudget();
    protected ref HCWorkBudget m_LocalityWork = new HCWorkBudget();
    protected int m_LocalityCursor;
    static const int HC_PROXIMITY_ROWS = 16;
    protected ref map<string, int> m_SiteLocalities = new map<string, int>();
    protected ref map<string, HCXAILocalityCoverage> m_CoverageRows = new map<string, HCXAILocalityCoverage>();
    protected ref map<string, bool> m_PolicySiteIds = new map<string, bool>();
    protected ref map<string, int> m_RouteResults = new map<string, int>();
    protected ref map<string, ref HCXAISiteState> m_Survey = new map<string, ref HCXAISiteState>();
    protected ref HCWorkBudget m_SurveyWork = new HCWorkBudget();
    protected int m_SurveyCursor;
    protected int m_SurveyStartedMs = -1;
    protected bool m_SurveyTurn;
    protected bool m_SurveyBackgroundLogged;
    protected int m_LastSummaryMs;
    protected int m_LastSummaryQualified;
    protected ref array<ref HCXAISite> m_SelectionPending;
    protected string m_SelectionLocality;
    protected int m_QualifiedCount;
    protected int m_RefusedCount;
    protected int m_ProximityCursor;
    protected int m_NearSite = -1;
    protected int m_ScanNearSite = -1;
    protected float m_ScanNearGap = 1000000000;
    protected int m_NextSummaryMs;
    protected int m_LocalityNextAttemptAt;
    protected int m_LocalityNextPendingLogAt;
    protected bool m_LocalityRefused;
    protected string m_LocalityStatus = "off";
    protected string m_CoverageFault;
    protected int m_LocalitiesWithoutSites;
    protected ref HCOperationalStatus m_OperationalStatus = new HCOperationalStatus;
    HCOperationalStatus HCGetOperationalStatus()
    {
        if (m_Phase == "wait" && HCXExpansionBridge.HCBridgeUp())
        {
            // Admitted and stepping every tick. The wait is for Expansion's own settings and the HC
            // faction (HCXExpansionBridge.HCMissingCondition, logged once): every provider call refuses
            // with a counted NOT_READY reason meanwhile and StepWait retries each tick, so the owner
            // reports ready now instead of holding AIRoles and the adapter late (R4, soak 175: 47.6 s).
            m_OperationalStatus.HCPublish("ready", "sites_wait_provider_gated");
        }
        else if (m_Phase == "wait" || m_Phase == "bind" || m_Phase == "qualify" || m_Phase == "create")
        {
            m_OperationalStatus.HCPublish("requested", "sites_" + m_Phase);
        }
        else if (m_Phase == "refused" || m_Phase == "off")
        {
            m_OperationalStatus.HCPublish("refused", "sites_policy_or_provider_unavailable");
        }
        else
        {
            HCModuleReadiness.HCDerive(m_OperationalStatus, m_Phase == "run", "", m_CoverageFault, "site_owner_running_routes_qualify_incrementally");
        }
        return m_OperationalStatus;
    }
    static HCXAISiteDirector Active() { return s_Active; }
    string Phase() { return m_Phase; }
    array<ref HCXAISiteState> States() { return m_States; }
    int OwnedSession()
    {
        if (!m_Owned) { return 0; }
        return m_Owned.Session;
    }
    string HCLocalitySummary()
    {
        int count = 0;
        int page = 0;
        string oldest = "";
        if (m_Localities) { count = m_Localities.Localities.Count(); }
        if (m_LocalitySave && m_LocalitySave.Data) { oldest = HCXAISiteRules.HCOldestPending(m_LocalitySave.Data); }
        foreach (HCXAISiteState state : m_States)
        {
            if (state.LocalityId != "") { page++; }
        }
        string next = "";
        if (m_LocalitySave && m_LocalitySave.Data) { next = m_LocalitySave.Data.NextId; }
        if (m_Phase == "run" && m_Localities) { m_LocalityStatus = this.HCGetOperationalStatus().HCState(); }
        string line = "[HC Plan] HC-18 localities=" + count.ToString() + " page=" + page.ToString() + " oldest_pending=" + oldest;
        return line + " cursor=" + next + " state=" + m_LocalityStatus + " runtime=PENDING";
    }
    protected bool HCStartLocalities() { return false; }
    protected int HCLocalityPageCount() { return 0; }
    protected bool HCHasSite(string id) { return false; }
    protected bool HCReconcileLocalitySites() { return false; }
    protected void HCAddLegacySites() {  }
    protected void HCLocalityFault() {  }
    protected vector HCSiteAnchor(HCXAISite site) { return vector.Zero; }
    protected float HCPlayerGap(HCXAISite site) { return 0; }
    protected bool HCWithinActivation(HCXAISite site) { return false; }
    protected void HCScanNearby(int now) {  }
    protected bool HCSurveyReady() { return true; }
    protected HCXAISiteState HCSurveyState(HCXAISite site) { return null; }
    protected HCXAISiteState HCNearbySurveyState() { return null; }
    protected void HCStepSurvey() {  }
    protected void HCRecordRouteState(HCXAISiteState state) {  }
    protected void HCMakeNearbyRoom() {  }
    protected void HCTryLocality(int now) {  }
    protected void HCStepLocalities() {  }
    string BudgetProblem(int actorCap, HCXAISitePatrol exceptPatrol) { return ""; }
    bool AdmitTransient(string proposalId, string factionId, vector placePos, int actorCap, out string reason)
    {
        if (m_Phase != "run" || !m_Policy || !HCXAIQualification.EncountersEnabled()) { reason = "sites not running"; return false; }
        reason = "transient actor cap outside group safety ceiling";
        if (actorCap < 1 || actorCap > HCAILimits.SIZE_CEILING) { Print("[HC AI] transient refused group safety ceiling"); return false; }
        reason = this.BudgetProblem(actorCap, null);
        if (reason != "") { return false; }
        reason = HCXAIQualification.ProviderProblem();
        if (reason != "") { return false; }
        if (!HCXAIRules.Token(proposalId) || proposalId.Length() > 96 || !HCXAIRules.PositionValid(placePos, 16000) || placePos[0] < 1 || placePos[2] < 1 || placePos[0] > 15950 || placePos[2] > 15950) { reason = "invalid transient id or place anchor"; return false; }
        foreach (HCXAISiteState existing : m_States)
        {
            if (existing.ProposalId == proposalId) { reason = "duplicate transient proposal"; return false; }
        }
        string providerFaction = "";
        string loadout = "HollowCountry_Holdout";
        if (factionId == "locals") { providerFaction = "HCLocals"; }
        if (factionId == "volunteers") { providerFaction = "HCVolunteers"; loadout = "HollowCountry_Patrol"; }
        if (factionId == "scavengers") { providerFaction = "HCScavengers"; loadout = "HollowCountry_Scavenger"; }
        if (factionId == "raiders") { providerFaction = "HCRaiders"; loadout = "HollowCountry_Patrol"; }
        if (factionId == "travellers") { providerFaction = "HCTravellers"; }
        if (providerFaction == "") { reason = "unknown transient faction"; return false; }
        eAIFaction faction = HCXExpansionBridge.HCFactionCreate(providerFaction);
        if (!faction || HCXExpansionBridge.HCFactionIsInvincible(faction) || HCXExpansionBridge.HCFactionIsObserver(faction) || HCXExpansionBridge.HCFactionIsPassive(faction) || HCXExpansionBridge.HCFactionHasUnlimitedStamina(faction) || HCXExpansionBridge.HCFactionGetMeleeDamageMultiplier(faction) != 1 || HCXExpansionBridge.HCFactionGetMeleeYeetForce(faction) != 0 || !HCXAIDefaults.HCLoadoutPresent(loadout)) { reason = "transient faction or loadout unavailable/unfair"; return false; }
        reason = this.MemberProblemFor(placePos);
        if (reason != "") { return false; }
        HCXAISite transientSite = new HCXAISite();
        transientSite.Id = "transient:" + proposalId;
        transientSite.Kind = "patrol";
        transientSite.Faction = providerFaction;
        transientSite.Loadout = loadout;
        transientSite.NumberOfAI = actorCap;
        transientSite.NumberOfAIMax = actorCap;
        transientSite.Waypoints.Insert(placePos);
        transientSite.Waypoints.Insert(placePos + Vector(30, 0, 0));
        transientSite.Waypoints.Insert(placePos + Vector(30, 0, 30));
        transientSite.Waypoints.Insert(placePos + Vector(0, 0, 30));
        HCXAISiteState admitted = new HCXAISiteState();
        admitted.Site = transientSite;
        admitted.Transient = true;
        admitted.ProposalId = proposalId;
        admitted.ProviderFaction = providerFaction;
        admitted.AdmittedAt = GetGame().GetTime();
        m_States.Insert(admitted);
        m_AdmittedTotal++;
        Print("[HC Expansion AI] materializer transient site=" + proposalId + " faction=" + factionId + " actors=" + actorCap.ToString());
        reason = "";
        return true;
    }
    protected void StepTransients()
    {
        if (!this.HCTakeSiteUnits(64)) { return; }
        int inspected = 0;
        int transientWork = 0;
        while (inspected < m_States.Count() && transientWork < 1)
        {
            if (m_TransientCursor >= m_States.Count()) { m_TransientCursor = 0; }
            int transientIndex = m_TransientCursor;
            HCXAISiteState transientState = m_States[transientIndex];
            m_TransientCursor++;
            inspected++;
            if (!transientState.Transient) { continue; }
            transientWork++;
            if (transientState.Completed) { m_States.RemoveOrdered(transientIndex); m_TransientCursor = transientIndex; continue; }
            if (transientState.Materialized)
            {
                if (!transientState.Patrol) { this.FinishTransient(transientState, true, 0); continue; }
                // Provider slot empty: despawn. Slot set and the (ungated Final) count zero: the
                // party was destroyed. A not-READY bridge never turns a live party into a despawn.
                if (!transientState.Patrol.HCHasGroup())
                {
                    HCXExpansionBridge.HCSitePatrolDespawn(transientState.Patrol);
                    this.FinishTransient(transientState, true, 0);
                }
                else if (!transientState.Patrol.HCDeathHeld() && HCXExpansionBridge.HCHoldCountFinal(transientState.Patrol.HCGroupHold()) == 0)
                {
                    HCXExpansionBridge.HCSitePatrolWasGroupDestroyed(transientState.Patrol);
                    this.FinishTransient(transientState, true, 0);
                }
                continue;
            }
            int transientNow = GetGame().GetTime();
            int progressAt = Math.Max(transientState.AdmittedAt, transientState.HCQualificationProgressAt);
            if (transientNow < progressAt || transientNow - progressAt >= 300000)
            {
                transientState.Failed = true;
                transientState.Reason = "transient qualification/activation expired";
            }
            if (transientState.Failed) { this.FinishTransient(transientState, false, 0); continue; }
            if (!transientState.Bound) { this.Bind(transientState); transientState.HCQualificationProgressAt = transientNow; continue; }
            if (!transientState.Qualified) { this.QualifyStep(transientState); transientState.HCQualificationProgressAt = transientNow; continue; }
            if (!transientState.Patrol)
            {
                this.Create(transientState);
                if (!transientState.Patrol) { this.FinishTransient(transientState, false, 0); }
            }
        }
    }
    protected void FinishTransient(HCXAISiteState state, bool materialized, int survivors)
    {
        if (state.Completed) { return; }
        state.Completed = true;
        if (state.Patrol)
        {
            state.Patrol.m_HCFinished = true;
            state.Patrol.m_HCLive = false;
            HCXExpansionBridge.HCSitePatrolStop(state.Patrol);
            HCXExpansionBridge.HCSitePatrolDelete(state.Patrol);
        }
        Print("[HC Expansion AI] materializer ended site=" + state.ProposalId + " materialized=" + materialized.ToString() + " survivors=" + survivors.ToString() + " reason=" + state.Reason);
        HCXMaterializerBridge.SiteEnded(state.ProposalId, materialized, survivors);
    }
    void Start()
    {
        m_SitesLogLine = "";
        m_SitesLogAt = 0;
        m_SpawnLogLine = "";
        m_SpawnLogAt = 0;
        if (!GetGame() || !GetGame().IsServer()) { return; }
        m_SurveyStartedMs = GetGame().GetTime();
        s_Active = HCXAISiteDirector.Cast(this);
        HCXAIStore.HCPrimeJournal();
        HCSettings preferences = HCServer.Get().GetSettings();
        m_GroupScaling = preferences && preferences.EnableGroupScaling;
        m_RingCandidates = HCOperatorSettingsRegistry.HCDefault("MaxTickWorkItems");
        if (preferences) { m_RingCandidates = preferences.MaxTickWorkItems; }
        if (preferences && preferences.EnableDebugSnapshot)
        {
            m_Debug = new HCXAIPatrolDebug();
            HCDebugSnapshot.HCRegister(m_Debug);
            Print("[HC Expansion AI] patrol debug contributor registered");
        }
        m_Build = HCXAIStore.NativeBuild();
        m_Diagnostic = FileExist(HCXAISiteDirector.DIAGNOSTIC);
        m_RespawnOff = FileExist("$profile:HollowCountry/acceptance/ai-respawn.disable");
        string shippedSites = HCXAIDefaults.Shipped() + HCXAIDefaults.SitesFile();
        string missionSites = "$mission:hollow-country/ai/sites.json";
        if (FileExist(missionSites)) { shippedSites = missionSites; }
        HCXAIRespawnDefaults.HCEnsure(HCXAIDefaults.SitesFile(), shippedSites);
        string shippedLocalities = HCXAIDefaults.Shipped() + "expansion-ai-localities.json";
        string missionLocalities = "$mission:hollow-country/ai/localities.json";
        if (FileExist(missionLocalities)) { shippedLocalities = missionLocalities; }
        HCXAIRespawnDefaults.HCEnsure("expansion-ai-localities.json", shippedLocalities, true);
        HCXAIRespawnDefaults.HCEnsure("expansion-ai-formations.json", HCXAIDefaults.Shipped() + "expansion-ai-formations.json");
        HCXAIRespawnDefaults.HCEnsure("expansion-ai-tactics.json", HCXAIDefaults.Shipped() + "expansion-ai-tactics.json");
        Print("[HC Expansion AI] start step=defaults_checked");
        m_Policy = HCXAISiteDirector.LoadPolicy();
        if (!m_Policy)
        {
            m_Phase = "off";
            Print("[HC Expansion AI] sites off: no readable policy at " + HCXAISiteDirector.POLICY);
            Print(this.HCLocalitySummary() + " refusal=site_policy_unreadable");
            return;
        }
        Print("[HC Expansion AI] start step=policy_loaded");
        string problem = HCXAISiteRules.PolicyProblem(m_Policy);
        if (problem != "")
        {
            m_Phase = "off";
            Print("[HC Expansion AI] sites off: policy refused: " + problem);
            Print(this.HCLocalitySummary() + " refusal=site_policy_invalid");
            return;
        }
        foreach (HCXAISite reviewedSite : m_Policy.Sites)
        {
            string checkpointIssue = HCXAIRules.CheckpointProblem(reviewedSite);
            if (checkpointIssue != "")
            {
                m_Phase = "off";
                Print("[HollowCountry] Checkpoints refused: " + reviewedSite.Id + ": " + checkpointIssue);
                return;
            }
        }
        m_Routes = HCXAISiteDirector.LoadRoutes();
        if (m_Routes)
        {
            foreach (HCXAISite bootSite : m_Policy.Sites) { m_CachePolicy.Set(bootSite.Id, bootSite); }
            foreach (HCXAIRouteRow bootRoute : m_Routes.Rows)
            {
                if (!m_CachePolicy.Contains(bootRoute.SiteId)) { m_CacheRetained++; continue; }
                if (m_CachePending.Contains(bootRoute.SiteId)) { continue; }
                m_CachePending.Set(bootRoute.SiteId, true);
                m_CacheReviewIds.Insert(bootRoute.SiteId);
            }
            this.HCDiscardLegacyRoutes();
            this.HCRoutesWarm();
            this.HCIndexRoutes();
        }
        m_Caches = HCXAISiteDirector.LoadCaches();
        m_BootOwned = HCXAISiteDirector.LoadOwned();
        if (m_Caches)
        {
            foreach (HCXAICacheRow bootCache : m_Caches.Rows)
            {
                if (!m_CacheRows.Contains(bootCache.SiteId)) { m_CacheRows.Set(bootCache.SiteId, bootCache); }
            }
            m_CacheSave = new HCXAICacheSave();
            m_CacheSave.Owner = HCXAISiteDirector.Cast(this);
            HCSaveScheduler.HCRegister(m_CacheSave);
        }
        Print("[HC Expansion AI] start step=policy_checked");
        if (!this.HCStartLocalities())
        {
            this.HCLocalityFault();
        }
        Print(HCV2Admission.Line("AIFreshRespawn", !m_RespawnOff, "EXP-P2", HCV2Gates.Qualified("EXP-P2")) + " runtime=PENDING");
        Print("[HC Expansion AI] fresh respawn policy full=" + m_Policy.AIRespawnSeconds.ToString() + "s member=" + m_Policy.MemberReplaceSeconds.ToString() + "s mode=fresh-group runtime=PENDING");
        foreach (HCXAISite policySite : m_Policy.Sites) { m_PolicySiteIds.Set(policySite.Id, true); }
        int count = m_Policy.Sites.Count();
        Print("[HC Expansion AI] sites policy accepted: " + count.ToString() + " sites; waiting for Expansion AI settings");
        if (m_Policy.RaidCooldownFloorSeconds > 0) { Print("[HC Expansion AI] raid cooldown floor " + m_Policy.RaidCooldownFloorSeconds.ToString() + "s (operator)"); }
        bool shippedPolicy = HCXAIDefaults.MatchesShipped();
        int shippedCount = count;
        if (!shippedPolicy) { shippedCount = HCXAIDefaults.ShippedSiteCount(); }
        string drift = HCXAIDefaults.PolicyDrift(shippedPolicy, count, shippedCount);
        if (drift != "") { Print("" + drift); }
        if (m_Diagnostic) { Print("[HC Expansion AI] DIAGNOSTIC marker present: one site of each kind spawns once with no player (Wine observation only)"); }
    }
    void Stop()
    {
        if (m_Debug)
        {
            HCDebugSnapshot.HCUnregister(m_Debug);
            m_Debug = null;
            Print("[HC Expansion AI] patrol debug contributor unregistered");
        }
        foreach (HCXAISiteState stopping : m_States)
        {
            if (stopping.LocalityId != "" && stopping.Patrol) { stopping.Patrol.m_HCFinished = true; }
            if (stopping.Patrol) { HCXExpansionBridge.HCSitePatrolStop(stopping.Patrol); }
        }
        if (m_LocalitySave)
        {
            if (!HCSaveScheduler.HCFlush(m_LocalitySave)) { this.HCLocalityFault(); }
            HCSaveScheduler.HCUnregister(m_LocalitySave);
        }
        if (m_RouteSave)
        {
            m_RouteSave.HCShutdown = true;
            HCSaveScheduler.HCFlush(m_RouteSave);
            HCSaveScheduler.HCUnregister(m_RouteSave);
            m_RouteSave = null;
        }
        this.SaveOwned();
        if (m_OwnedSave) { HCSaveScheduler.HCUnregister(m_OwnedSave); m_OwnedSave = null; }
        if (m_CacheSave)
        {
            HCSaveScheduler.HCFlush(m_CacheSave);
            HCSaveScheduler.HCUnregister(m_CacheSave);
            m_CacheSave = null;
        }
        HCXAIDefaults.HCStopLoadouts();
        m_Phase = "stopped";
        m_LocalityStatus = "off";
        if (m_Localities) { Print(this.HCLocalitySummary()); }
        if (s_Active == this) { s_Active = null; }
    }
    // Capacity/disabled fallback keeps routine debounce and advances one stage.
    // Urgency is temporary here; routine mutations never bypass coalescing.
    protected void HCPumpSiteSave(HCSaveJob job)
    {
        if (!job || !job.HCDirty || job.HCFaulted) { return; }
        if (HCPerfConfig.HCGet().EnableSharedSaves && HCSaveScheduler.HCRegistered(job)) { return; }
        float now = GetGame().GetTickTime();
        if (!job.HCInFlight && (now < job.HCDue || (job.HCHasCommitted && now < job.HCLastCommitSeconds + job.HCInterval()))) { return; }
        job.HCUrgent = true;
        HCSaveScheduler.HCPumpFallback(job);
        job.HCUrgent = false;
    }
    protected bool HCTakeSiteUnits(int units) { return HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_AI_SITES, units); }
    // The global slot paid entry; this local hard cap must progress independently.
    protected bool HCTakeLocalityUnit() { return m_LocalityUnits.HCTakeFor(HCUnitBudget.HC_WORK_AI_SITES, 1); }
    void Step()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        m_Ticks++;
        if (!m_OwnedSaved && m_Ticks % 60 == 0) { this.HCQueueOwned(); }
        this.HCPumpSiteSave(m_CacheSave);
        this.HCPumpSiteSave(m_OwnedSave);
        this.HCPumpSiteSave(m_RouteSave);
        // Selection checkpoints retain their urgent, budgeted locality pump.
        // Routine observations/refusals must also progress without another selection.
        if (m_LocalitySave && !m_LocalitySave.HCUrgent) { this.HCPumpSiteSave(m_LocalitySave); }
        if (m_Phase == "wait") { this.StepWait(); return; }
        if (m_Phase == "bind") { this.StepBind(); return; }
        if (m_Phase == "qualify") { this.StepQualify(); return; }
        if (m_Phase == "create") { this.StepCreate(); return; }
        if (m_Phase == "run")
        {
            m_SurveyTurn = !m_SurveyTurn;
            if (m_SurveyTurn) { m_CacheReviewTurn = !m_CacheReviewTurn; }
            if (!m_RoutesWarm && m_SurveyTurn && m_CacheReviewTurn && (!m_Localities || this.HCSurveyReady()))
            {
                this.HCReviewCachedRoute();
                return;
            }
            if (m_Localities && m_SurveyTurn && m_SurveyCursor < m_Policy.Sites.Count())
            {
                this.HCStepSurvey();
                return;
            }
            int runBegan = TickCount(0);
            this.StepRun();
            if (TickCount(runBegan) < 120000) { this.HCSampleReleaseRadius(); }
        }
    }
    protected void HCRoutesWarm() {  }
    protected void HCCacheVerdict(string siteId, bool reused) {  }
    protected void HCCacheDiscard(HCXAIRouteRow row, string reason, string field = "") {  }
    protected void HCDiscardLegacyRoutes() {  }
    protected void HCReviewCachedRoute() {  }
    protected bool HCUpgradeRequalAllowed(HCXAISite site, string field) { return true; }
    protected void StepWait()
    {
        ExpansionAISettings aiSettings = HCXExpansionBridge.HCSettings();
        bool aiLoaded = aiSettings != null;
        bool patrolLoaded = false;
        if (aiLoaded) { patrolLoaded = HCXExpansionBridge.HCPatrolSettings() != null; }
        if (!aiLoaded || !patrolLoaded) { return; }
        HCXAIDefaults.ProvisionLoadouts(m_Policy);
        if (!HCXAIDefaults.HCLoadoutsReady()) { return; }
        HCXAISiteAdmission admission = this.Observe();
        string problem = HCXAISiteRules.AdmissionProblem(m_Policy, admission);
        if (problem != "")
        {
            m_Phase = "refused";
            Print("[HC Expansion AI] sites admission refused: " + problem);
            if (m_Localities) { m_LocalityStatus = "refused:provider_admission"; Print(this.HCLocalitySummary()); }
            return;
        }
        if (m_Routes && !m_RouteSave)
        {
            m_RouteSave = new HCXAIRouteSave();
            m_RouteSave.Owner = HCXAISiteDirector.Cast(this);
            if (m_LegacyRoutesDirty) { this.SaveRoutes(); m_LegacyRoutesDirty = false; }
            HCSaveScheduler.HCRegister(m_RouteSave);
        }
        if (!m_Routes || !m_Caches)
        {
            m_Phase = "refused";
            Print("[HC Expansion AI] sites admission refused: route or cache journal unreadable or over budget");
            if (m_Localities) { m_LocalityStatus = "refused:site_journal"; Print(this.HCLocalitySummary()); }
            return;
        }
        m_Filter = new PGFilter();
        // Qualify on the navmesh the patrols walk: Expansion's patrol filter includes UNREACHABLE and
        // DISABLED polygons, so excluding them here refused routes the AI can walk (#355, road patrols
        // "leg 0: path chain stalled"). The outdoor-retry filter below still excludes both.
        int legacyBits = PGPolyFlags.UNREACHABLE | PGPolyFlags.DISABLED;
        int include = legacyBits | PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE | PGPolyFlags.LADDER;
        int exclude = PGPolyFlags.CRAWL | PGPolyFlags.CROUCH | PGPolyFlags.SWIM_SEA | PGPolyFlags.SWIM;
        if (aiSettings.Vaulting) { include = include | PGPolyFlags.SPECIAL; }
        else { exclude = exclude | PGPolyFlags.SPECIAL; }
        m_Filter.SetFlags(include, exclude, PGPolyFlags.NONE);
        m_OutdoorFilter = new PGFilter();
        int outdoorExclude = PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.INSIDE | PGPolyFlags.DOOR | PGPolyFlags.LADDER | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH;
        m_OutdoorFilter.SetFlags(PGPolyFlags.WALK, outdoorExclude, PGPolyFlags.NONE);
        string navContent = HCXAISiteRules.HCNavContent();
        m_RouteValidity = HCXAISiteRules.HCRouteValidity(m_Build, GetGame().GetWorldName(), m_Policy.MaxLegLength, include, exclude, PGPolyFlags.WALK, outdoorExclude, navContent);
        // Pre-#355 primary filter term (UNREACHABLE|DISABLED excluded), derived from the live flags: a
        // route that qualified on that smaller navmesh stays valid on this one, so the cache keeps it.
        int legacyInclude = include - legacyBits;
        int legacyExclude = exclude | legacyBits;
        m_RouteLegacyTerm = legacyInclude.ToString() + ":" + legacyExclude.ToString() + ":0";
        if (m_RouteValidity == "")
        {
            string validityReason = "validity_scalars";
            if (!HCXAISiteRules.HCManifestValid(navContent)) { validityReason = "validity_manifest"; }
            Print("[HC Expansion AI] route cache reuse disabled reason=" + validityReason);
        }
        foreach (HCXAISite site : m_Policy.Sites)
        {
            if (m_Localities) { break; } // sparse pages enter through HCStepLocalities
            if (site.Checkpoint && !HCXAIQualification.EncountersEnabled()) { continue; }
            HCXAISiteState state = new HCXAISiteState();
            state.Site = site;
            m_States.Insert(state);
            m_AdmittedTotal++;
        }
        Print("[HC Expansion AI] sites admitted: build=" + admission.BuildVersion + " world=" + admission.WorldName + " addons=present expansion_ai_settings=loaded globals=fair factions=fair loadouts=present observer=" + admission.ObserverPolicy + " pve_patrols=true ownership=reconciled; binding sites");
        if (m_Localities)
        {
            HCSaveScheduler.HCRegister(m_LocalitySave);
            m_Phase = "run";
            m_LocalityStatus = this.HCGetOperationalStatus().HCState();
            Print(this.HCLocalitySummary());
            return;
        }
        m_Phase = "bind";
        m_Cursor = 0;
    }
    protected bool HCFactionFair(string factionName, map<string, bool> factionChecked)
    {
        if (factionName == "" || factionChecked.Contains(factionName)) { return true; }
        factionChecked.Set(factionName, true);
        if (!HCXExpansionBridge.HCFactionGetType(factionName)) { return false; }
        eAIFaction faction = HCXExpansionBridge.HCFactionCreate(factionName);
        if (!faction || HCXExpansionBridge.HCFactionIsInvincible(faction) || HCXExpansionBridge.HCFactionIsObserver(faction) || HCXExpansionBridge.HCFactionIsPassive(faction) || HCXExpansionBridge.HCFactionHasUnlimitedStamina(faction)) { return false; }
        return HCXExpansionBridge.HCFactionGetMeleeDamageMultiplier(faction) == 1 && HCXExpansionBridge.HCFactionGetMeleeYeetForce(faction) == 0;
    }
    protected HCXAISiteAdmission Observe()
    {
        HCXAISiteAdmission a = new HCXAISiteAdmission();
        a.BuildVersion = m_Build;
        string world = GetGame().GetWorldName();
        world.ToLower();
        a.WorldName = world;
        array<string> addons = {"HollowCountryExpansionAI", "DayZExpansion_AI_Scripts", "DayZExpansion_Core_Scripts", "DayZExpansion_AI_Animations", "JM_CF_Scripts"};
        foreach (string addon : addons)
        {
            if (!GetGame().ConfigIsExisting("CfgPatches " + addon)) { a.MissingAddons = a.MissingAddons + addon + " "; }
        }
        a.SettingsLoaded = true;
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (adapter) { a.Globals = adapter.GlobalsProblem(); }
        else { a.Globals = "adapter not bound"; }
        if (a.Globals == "") { a.Globals = HCXAIQualification.ProviderProblem(); }
        map<string, bool> factionChecked = new map<string, bool>();
        foreach (HCXAISite factionSite : m_Policy.Sites)
        {
            if (!this.HCFactionFair(factionSite.Faction, factionChecked)) { a.UnfairFaction = factionSite.Faction; break; }
            string armedFaction = HCXFactions.EncounterFaction(factionSite);
            if (!this.HCFactionFair(armedFaction, factionChecked)) { a.UnfairFaction = armedFaction; break; }
        }
        map<string, bool> loadoutChecked = new map<string, bool>();
        foreach (HCXAISite loadoutSite : m_Policy.Sites)
        {
            if (loadoutChecked.Contains(loadoutSite.Loadout)) { continue; }
            loadoutChecked.Set(loadoutSite.Loadout, true);
            if (!HCXAIDefaults.HCLoadoutPresent(loadoutSite.Loadout))
            {
                a.MissingLoadout = loadoutSite.Loadout;
                break;
            }
        }
        a.ObserverPolicy = HCXAISiteDirector.OBSERVER;
        a.Marker = HCXAIQualification.Admitted() || HCXAIQualification.EncountersEnabled();
        a.OwnershipReconciled = this.Reconcile();
        return a;
    }
    protected bool Reconcile()
    {
        HCXAIOwnership previous = m_BootOwned;
        if (!previous) { return false; }
        array<eAIBase> all = new array<eAIBase>();
        array<eAIBase> observedActors = HCXExpansionBridge.HCBaseGetAll();
        all.Copy(observedActors);
        int removed = 0;
        foreach (eAIBase actor : all)
        {
            if (!actor) { continue; }
            eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor);
            if (!group) { continue; }
            string groupName = HCXExpansionBridge.HCGroupGetName(group);
            HCTextWindow groupWindow = new HCTextWindow(groupName);
            if (groupWindow.Length() < 3 || groupWindow.Range(0, 3) != "HC:") { continue; }
            HCXExpansionBridge.HCBaseDespawn(actor);
            removed++;
        }
        int rows = previous.Rows.Count();
        Print("[HC Expansion AI] sites ownership: previous session " + previous.Session.ToString() + " listed " + rows.ToString() + " live sites; removed " + removed.ToString() + " orphan actors");
        m_Owned = previous;
        m_OwnedRows.Clear();
        foreach (HCXAIOwnedRow bootRow : m_Owned.Rows)
        {
            if (!m_OwnedRows.Contains(bootRow.SiteId)) { m_OwnedRows.Set(bootRow.SiteId, bootRow); }
        }
        if (!m_OwnedSave)
        {
            m_OwnedSave = new HCXAIOwnedSave();
            m_OwnedSave.Owner = HCXAISiteDirector.Cast(this);
            HCSaveScheduler.HCRegister(m_OwnedSave);
        }
        m_Owned.Session = previous.Session + 1;
        return this.SaveOwned();
    }
    protected void StepBind() {  }
    protected void Bind(HCXAISiteState state) {  }
    protected HCXAIRouteRow RouteRow(string siteId) { return null; }
    protected void StepQualify() {  }
    protected void QualifyStep(HCXAISiteState state, bool cacheOnly = false) {  }
    protected void HCFinishPath(HCXAISiteState state) {  }
    protected vector NavSample(vector wanted, float radius, PGFilter filter) { return vector.Zero; }
    protected vector GroundSample(vector probe, float radius) { return vector.Zero; }
    protected void HCOutdoorStep(HCXAISiteState state) {  }
    protected void Refuse(HCXAISiteState state, string reason) {  }
    protected void HCReusedRoute(HCXAISiteState state) {  }
    protected void Remember(HCXAIRouteRow row) {  }
    protected void StepCreate() {  }
    protected void Create(HCXAISiteState state) {  }
    float HCActivationRadius(HCXAISite site, bool transient)
    {
        float radius = site.ActivationRadius;
        if (!transient) { radius = HCXAISiteRules.EncounterRadius(site.ActivationRadius); }
        float scale = m_Policy.ActivationRadiusScale;
        if (scale == 0) { scale = 1.0; }
        radius = radius * scale;
        float clamped = HCPerceptionRing.HCClampActivation(radius);
        if (clamped != radius && !m_RadiusClampLogged)
        {
            m_RadiusClampLogged = true;
            Print("[HC Expansion AI] activation radius clamped " + radius.ToString() + "m to " + clamped.ToString() + "m; perception ring runtime=PENDING");
        }
        return clamped;
    }
    protected void StepRun()
    {
        HCXAIGroupHolds.PruneStep();
        int stage = 0;
        if (m_RunStage % 2 == 1) { stage = 1 + m_RunStage / 2; }
        m_RunStage = (m_RunStage + 1) % 8;
        int stageBegan = TickCount(0);
        if (stage == 0) { this.HCStepLocalities(); this.HCSiteStageCost("localities", stageBegan); return; }
        if (stage == 1) { this.StepTransients(); this.HCSiteStageCost("transients", stageBegan); return; }
        if (stage == 2) { this.HCStepRespawns(); this.HCSiteStageCost("respawns", stageBegan); return; }
        if (stage == 3) { this.StepCache(); this.HCSiteStageCost("cache", stageBegan); return; }
        if (m_GroupScaling) { this.HCRefreshGroupFactor(); }
        if (m_Diagnostic) { this.StepDiagnostic(); }
        int nowMs = GetGame().GetTime();
        if (nowMs < m_NextSummaryMs) { return; }
        m_NextSummaryMs = nowMs + 300000;
        int sites = 0;
        int actors = 0;
        foreach (HCXAISiteState counted : m_States)
        {
            this.HCRecordRouteState(counted);
            if (!counted.Patrol || counted.Patrol.HCDeathHeld() || HCXExpansionBridge.HCHoldCount(counted.Patrol.HCGroupHold()) == 0) { continue; }
            sites++;
            actors = actors + HCXExpansionBridge.HCHoldCount(counted.Patrol.HCGroupHold());
        }
        int pending = m_Policy.Sites.Count() - m_QualifiedCount - m_RefusedCount;
        string summary = "[HC Expansion AI] sites summary: qualified=" + m_QualifiedCount.ToString() + " refused=" + m_RefusedCount.ToString() + " pending=" + pending.ToString();
        string spawnStatusLine = "[HC Expansion AI] spawn summary admitted=" + m_AdmittedTotal.ToString() + " spawned=" + m_SpawnedTotal.ToString() + " relocated=" + m_RelocatedTotal.ToString() + " runtime=PENDING";
        float spawnStatusLineNow = GetGame().GetTickTime();
        if (spawnStatusLine != m_SpawnLogLine || spawnStatusLineNow < m_SpawnLogAt || spawnStatusLineNow - m_SpawnLogAt >= 1800)
        {
            Print("" + spawnStatusLine);
            m_SpawnLogLine = spawnStatusLine;
            m_SpawnLogAt = spawnStatusLineNow;
        }
        string refusals = "[HC Expansion AI] spawn refusals";
        for (int refusalIndex = 0; refusalIndex < m_SpawnRefusals.Count(); refusalIndex++)
        {
            int refusedCount = m_SpawnRefusals.GetElement(refusalIndex);
            refusals += " " + m_SpawnRefusals.GetKey(refusalIndex) + "=" + refusedCount.ToString();
        }
        Print(refusals + " runtime=PENDING");
        m_AdmittedTotal = 0;
        m_SpawnedTotal = 0;
        m_RelocatedTotal = 0;
        m_SpawnRefusals.Clear();
        float qualifiedRate = 0;
        if (m_LastSummaryMs > 0 && nowMs > m_LastSummaryMs)
        {
            qualifiedRate = (m_QualifiedCount - m_LastSummaryQualified) * 1000.0 / (nowMs - m_LastSummaryMs);
        }
        m_LastSummaryMs = nowMs;
        m_LastSummaryQualified = m_QualifiedCount;
        summary += " qualified_per_s=" + qualifiedRate.ToString() + " survey_cursor=" + m_SurveyCursor.ToString();
        string sitesStatusLine = summary + " active_sites=" + sites.ToString() + " actors=" + actors.ToString() + " controllers=" + m_States.Count().ToString() + " runtime=PENDING";
        float sitesStatusLineNow = GetGame().GetTickTime();
        if (sitesStatusLine != m_SitesLogLine || sitesStatusLineNow < m_SitesLogAt || sitesStatusLineNow - m_SitesLogAt >= 1800)
        {
            Print("" + sitesStatusLine);
            m_SitesLogLine = sitesStatusLine;
            m_SitesLogAt = sitesStatusLineNow;
        }
    }

    protected void HCSampleReleaseRadius()
    {
        if (m_States.Count() == 0 || !this.HCTakeSiteUnits(1)) { return; }
        if (m_ReleaseRadiusCursor >= m_States.Count()) { m_ReleaseRadiusCursor = 0; }
        HCXAISiteState state = m_States[m_ReleaseRadiusCursor];
        m_ReleaseRadiusCursor++;
        if (!state.Qualified || state.Failed || !state.Patrol || state.Transient)
        {
            state.ReleaseRadius = null;
            return;
        }
        if (!state.ReleaseRadius) { state.ReleaseRadius = new HCReleaseRadius; }
        vector centre = this.HCSiteAnchor(state.Site);
        float radius = this.HCActivationRadius(state.Site, false);
        state.ReleaseRadius.HCSample(centre, radius, HCReleaseRadiusWire.AI_SITE);
    }
    protected void StepDiagnostic()
    {
        map<string, bool> done = new map<string, bool>();
        foreach (HCXAISiteState state : m_States)
        {
            if (state.Diagnosed) { done.Set(state.Site.Kind, true); }
        }
        HCXAISiteState selected;
        foreach (HCXAISiteState candidate : m_States)
        {
            if (candidate.Transient || !candidate.Patrol || candidate.Diagnosed || done.Contains(candidate.Site.Kind)) { continue; }
            selected = candidate;
            break;
        }
        if (!selected) { return; }
        selected.Diagnosed = true;
        Print("[HC Expansion AI] DIAGNOSTIC spawn of site " + selected.Site.Id + " (" + selected.Site.Kind + ")");
        HCXExpansionBridge.HCSitePatrolSpawn(selected.Patrol);
    }
    string HCPrepareRingSpawn(HCXAISitePatrol patrol) { return ""; }
    protected vector m_RingGround;
    protected string HCRingPickProblem(HCPerceptionRingPick pick, vector centre, array<vector> ringObservers, vector original) { return ""; }
    protected string HCRingRouteProblem(vector start, vector target) { return ""; }
    string SpawnProblemFor(HCXAISitePatrol patrol) { return ""; }
    string MemberProblemFor(vector pos) { return ""; }
    protected void HCRefreshPlayers() {  }
    protected void HCRefreshGroupFactor() {  }
    float NearestPlayer(vector pos) { return 0; }
    bool SeenByPlayer(vector pos) { return false; }
    void Spawned(HCXAISitePatrol patrol) {  }
    void Despawned(HCXAISitePatrol patrol, bool intact) {  }
    static int RaidCooldown(HCXAISite site, int operatorFloor = 0)
    {
        int minimum = site.RespawnSeconds;
        if (operatorFloor > minimum) { minimum = operatorFloor; }
        return minimum;
    }
    static int HCRespawnDelay(HCXAISite site, HCXAISitePolicy policy)
    {
        int seconds = policy.AIRespawnSeconds;
        if (seconds == 0) { seconds = site.RespawnSeconds; }
        if (site.Kind == "patrol" && policy.PatrolRespawnSeconds > 0) { seconds = policy.PatrolRespawnSeconds; }
        if (site.Kind == "holdout" && policy.HoldoutRespawnSeconds > 0) { seconds = policy.HoldoutRespawnSeconds; }
        bool military = site.Id.Length() >= 4 && site.Id.Substring(0, 4) == "mil-";
        if (military && policy.MilitaryRespawnSeconds > 0) { seconds = policy.MilitaryRespawnSeconds; }
        if (policy.RaidCooldownFloorSeconds > seconds) { seconds = policy.RaidCooldownFloorSeconds; }
        return seconds;
    }
    int HCDeathDelay(HCXAISite site, HCXAIOwnedRow row)
    {
        if (row.PartialRaid && m_Policy.MemberReplaceSeconds > 0) { return m_Policy.MemberReplaceSeconds; }
        return HCXAISiteDirector.HCRespawnDelay(site, m_Policy);
    }
    protected void HCStepRespawns() {  }
    void HCRefreshDepleted(HCXAISitePatrol patrol) {  }
    bool RaidLocked(HCXAISite site, int now) { return false; }
    protected HCXAIOwnedRow OwnershipRow(string siteId) { return null; }
    void HCArmDeath(eAIGroup killedGroup, DayZPlayerImplement killed)
    {
        if (!killedGroup) { return; }
        foreach (HCXAISiteState state : m_States)
        {
            if (!state.Patrol || !state.Patrol.HCMatchesGroup(killedGroup)) { continue; }
            state.Patrol.HCArmDeath(killed);
            return;
        }
    }
    void RecordDeath(eAIGroup killedGroup) {  }
    void RecordCleared(HCXAISitePatrol patrol, bool death = false) {  }
    protected void StepCache() {  }
    protected void CacheStep(HCXAISiteState state) {  }
    protected EntityAI FindCrate(HCXAISiteState state) { return null; }
    protected HCXAICacheRow CacheRow(string siteId) { return null; }
    void SeedCache(HCXAISiteState state, HCXAICacheRow row, int now, EntityAI crate) {  }
    bool SaveCaches() { return false; }
    bool SaveRoutes() { return false; }
    bool HCTakeRouteCacheUnit() { return false; }
    int HCRouteRowCount() { return 0; }
    HCXAIRouteRow HCRouteRowAt(int index) { return null; }
    bool HCRoutesText(HCXAIRouteCache snapshot, out string text) { return false; }
    protected void HCIndexRoutes() {  }
    protected void HCRemoveRoute(HCXAIRouteRow row) {  }
    void HCQueueCaches() {  }
    void HCQueueOwned() {  }
    protected bool HCUpdateMembers() { return false; }
    bool HCCachesText(out string text) { return false; }
    HCXAIOwnership HCOwnershipData() { return null; }
    void HCOwnershipSaved(bool saved) {  }
    bool SaveOwned() { return false; }
    static string ReadBounded(string path) { return HCXAISiteStore.ReadBounded(path); }
    static HCXAISitePolicy LoadPolicy() { return HCXAISiteStore.LoadPolicy(); }
    static string HCWholeCacheText(string path) { return HCXAISiteStore.HCWholeCacheText(path); }
    static void HCRoutesRefused(string reason) { HCXAISiteStore.HCRoutesRefused(reason); }
    static void HCCachesRefused(string reason) { HCXAISiteStore.HCCachesRefused(reason); }
    static bool HCPreserveRoute(string path, out string preserved) { return HCXAISiteStore.HCPreserveRoute(path, preserved); }
    static HCXAIRouteCache LoadRoutes() { return HCXAISiteStore.LoadRoutes(); }
    static HCXAICacheJournal LoadCaches() { return HCXAISiteStore.LoadCaches(); }
    static HCXAIOwnership LoadOwned() { return HCXAISiteStore.LoadOwned(); }
}
// External picker/caravan/routes mods extend only this final facade.
class HCXAISiteDirector : HCXAISitePatrols {}
