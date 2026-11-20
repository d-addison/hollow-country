// HC sites on Expansion AI: patrols, scavenger parties and holdouts with a
// cache. Expansion's own eAIDynamicPatrol and sphere trigger do the spawning.
// LC-T402 transient admission / EXP-L1, EXP-P2 (unverified): installed native
// scripts-1.30.164289/3_Game/AI/AIWorld.c:65 SetFlags, :98 FindPath, :122
// SampleNavmeshPosition; 3_Game/Global/Game.c:1176 SurfaceY, :1535 GetTime,
// :945 GetPlayers; Global/DayZPhysics.c:199 RaycastRV; Entities/Object.c:287
// GetPosition; 1_Core/proto/EnScript.c:380 Count, :385 Clear, :407 Insert,
// :470 RemoveOrdered;
// W5 #125/#122: Object.c:517 IsAlive; Entities/Man.c:21 GetIdentity;
// 1_Core/proto/EnConvert.c:210 vector.DistanceSq, :115 float.ToString;
// 1_Core/proto/EnMath.c:413 Math.Round. Expansion eAIDynamicPatrol.c:13
// m_Config, :592-597 reads NumberOfAI/NumberOfAIMax on each native Spawn.
// New work: one cached player list/second, one O(players) identity count;
// constant scaling per spawn check. Existing cursor does 4 qualification
// items/tick plus configured bounded transients. Debug: <=66 states, <=64 member slots,
// <=2 qualified routes (<=128 points each), only when snapshot requested.
// EnConvert.c:3 bool.ToString, :30 int.ToString; EnDebug.c:96 Print;
// EnString.c:113 Substring, :199 Length; EnSystem.c:397 FileExist.
// Raid persistence: 3_Game/tools/JsonFileLoader.c:42 SaveFile, :69 LoadData;
// installed core_scripts.pbo/3_Game/DayZExpansion_Core/ExpansionStatic.c:1748
// GetTimestamp(bool useUTC). Raid times are UTC seconds in our own JSON only.
// Read-only installed Expansion
// ai_scripts.pbo: 4_World/DayZExpansion_AI/Classes/Patrols/eAIDynamicPatrol.c:
// 68 CreateEx, 427 WasGroupDestroyed, 673 SpawnAI_Deferred, 691-725 Despawn;
// eAIPatrol.c:96 Delete, :146 Stop; Classes/eAIGroup.c:1139 GetMember,
// :1185 Count (living members), :1194 DeceasedCount, :1220 ClearAI;
// 3_Game/DayZExpansion_AI/Factions/eAIFaction.c:129 Create. No provider copied.
// HC adds the budget, the 200 m and line-of-sight rules, a refusal to despawn
// in combat, finite fair actors, navmesh-qualified routes and journals.
// Nothing here moves an actor: Expansion places each one once when it spawns.
// Qualified endpoints already came from the navmesh. The provider's default
// GetWaypoints applies placement rays, which could move them onto another
// surface. Preserve exactly the qualified list, including snapped holdouts.
modded class HCXAIOwnedRow
{
    int ClearedAt = 0;
    bool PartialRaid = false;
}
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
class HCXAISitePatrol : eAIDynamicPatrol
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
    protected int m_HCNextBudgetLogMs;
    protected int m_HCNextSkipLogMs;
    // Interval of each per-site limiter: refusals and benign skips are limited separately (#194).
    static const int HC_SITE_LOG_INTERVAL_MS = 60000;

    // A benign re-entry (the spawner calls Spawn again while the group is live) is not a refusal:
    // its own line and limiter, so it can never use up the window of a real refusal line.
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
        if (nowMs < m_HCNextBudgetLogMs) { return; }
        m_HCNextBudgetLogMs = nowMs + HC_SITE_LOG_INTERVAL_MS;
        if (problem != "") { Print("[HC Expansion AI] site " + m_HCSiteId + " spawn refused: " + problem); }
        else { Print("[HC AI] site shared population reservation refused id=" + m_HCSiteId); }
    }

    override bool CanSpawn()
    {
        if (m_HCFinished) { return false; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return false; }
        string problem = director.HCPrepareRingSpawn(this);
        if (problem == "" && !super.CanSpawn()) { return false; }
        if (problem == "") { problem = director.SpawnProblemFor(this); }
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
        if (m_Group)
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
        // Transients reuse the already reserved durable materializer lease.
        string budgetId = "site:" + m_HCSiteId;
        if (m_HCTransient) { budgetId = m_HCSiteId.Substring(10, m_HCSiteId.Length() - 10); }
        if (!HCAIBudget.TryReserve(budgetId, m_HCGroupMax)) { this.HCRefuseBudget(); return; }
        m_HCPendingMembers = 0;
        super.Spawn();
        if (!m_Group) { if (!m_HCTransient) { HCAIBudget.Release(budgetId); } return; }
        m_HCPendingMembers = m_NumberOfAI - m_Group.Count();
        if (m_HCPendingMembers < 0) { m_HCPendingMembers = 0; }
        m_HCLive = true;
        director.Spawned(this);
    }
    // Expansion creates members 2..N one per frame at formation offsets. Check
    // the same point it is about to use, before the member exists; a refused
    // member ends the group at the members that already passed.
    override void SpawnAI_Deferred(int i)
    {
        m_HCPendingMembers = 0;
        if (m_HCFinished) { return; }
        if (m_HCTransient && m_Group && m_Group.Count() == 0)
        {
            this.HCRefuseBudget("transient group emptied before member spawn");
            return;
        }
        if (!m_Group || !m_Formation)
        {
            this.HCRefuseBudget("member spawn without a live group");
            return;
        }
        vector raw = m_Formation.ToWorld(m_Formation.GetPosition(i));
        vector placed = ExpansionAISpawnBase.GetPlacementPosition(raw, true);
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
            m_NumberOfAI = m_Group.Count();
            m_Group.SetWaypointBehaviour(m_WaypointBehaviour);
            Print("[HC Expansion AI] site " + m_HCSiteId + " member " + i.ToString() + " refused: " + problem + "; group stays at " + m_NumberOfAI.ToString());
            if (director) { director.SaveOwned(); }
            return;
        }
        m_HCPendingMembers = m_NumberOfAI - i - 1;
        if (m_HCPendingMembers < 0) { m_HCPendingMembers = 0; }
        super.SpawnAI_Deferred(i);
    }
    // Expansion Classes/eAIGroup.c:1041 RemoveDeceased(int), :1123 IsInCombat;
    // Classes/Patrols/eAIDynamicPatrol.c:29,46 public respawn clock fields.
    // RemoveDeceased only removes the record;
    // ClearAI at :1240 otherwise deletes bodies and their physical inventory.
    void HCPreserveBodies()
    {
        if (!m_Group) { return; }
        int bodyCount = m_Group.DeceasedCount();
        while (bodyCount > 0)
        {
            bodyCount--;
            m_Group.RemoveDeceased(bodyCount);
        }
    }
    override void Despawn(bool deferDespawnUntilLoosingAggro = false)
    {
        if (m_Group && m_Group.Count() > 0 && !HCXAISiteRules.DespawnAllowed(m_Group.IsInCombat(), m_Group.m_ForcePatrolDespawn)) { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        // Check every live member, not just the place/leader. Forced provider
        // retirement cannot make a transient disappear in front of an observer.
        if (m_HCTransient && m_Group)
        {
            if (!director) { return; }
            int memberIndex = 0;
            while (memberIndex < m_Group.Count())
            {
                DayZPlayerImplement retiringMember = m_Group.GetMember(memberIndex);
                if (retiringMember && (director.NearestPlayer(retiringMember.GetPosition()) < 200 || director.SeenByPlayer(retiringMember.GetPosition()))) { return; }
                memberIndex++;
            }
        }
        bool intact = false;
        if (m_Group) { intact = m_Group.Count() >= m_NumberOfAI && m_Group.DeceasedCount() == 0; }
        m_HCSurvivors = 0;
        if (m_Group) { m_HCSurvivors = m_Group.Count(); }
        bool wasLive = m_HCLive;
        // Only a group that lost members locks its site (RecordDeath already
        // recorded each kill); an intact group that only lost its audience may
        // return when a player comes back, so its gear is never duplicated.
        bool raided = wasLive && !intact;
        if (raided && director) { director.RecordCleared(this); }
        this.HCPreserveBodies();
        super.Despawn(false);
        m_HCPendingMembers = 0;
        m_HCLive = false;
        if (!m_HCTransient && !m_Group) { HCAIBudget.Release("site:" + m_HCSiteId); }
        // The persisted death epoch is the respawn clock; native audience
        // retirement must not add another full cooldown after it.
        if (intact || raided) { m_TimeSinceLastSpawn = m_RespawnTime; }
        if (wasLive && director) { director.Despawned(this, intact); }
    }
    override void OnUpdate()
    {
        if (m_HCFinished) { this.Stop(); return; }
        super.OnUpdate();
    }
    override void SetupAI(eAIBase ai)
    {
        super.SetupAI(ai);
        ai.eAI_SetUnlimitedReload(0);
        ai.eAI_SetLootingBehavior(0);
        ai.m_eAI_EnableFlankingOutsideCombat = false;
        ai.eAI_SetDamageMultiplier(1);
        ai.eAI_SetDamageReceivedMultiplier(1);
        ai.m_eAI_HeadshotResistance = 0;
        // Blocks Expansion's inventory-cloning recreate (no duplicate loot).
        ai.HCXAI_LeaseOwned = true;
        if (!ai.HCXAI_Fair() || ai.m_eAI_LootingBehavior != 0)
        {
            Print("[HC Expansion AI] site " + m_HCSiteId + " actor failed the fairness check; removed");
            ai.eAI_Despawn();
        }
    }
}
class HCXAISiteState : Managed
{
    ref HCXAISite Site;
    HCXAISitePatrol Patrol;
    ref array<vector> Points = new array<vector>();
    ref array<vector> Sampled = new array<vector>();
    ref array<vector> PatrolPoints = new array<vector>();
    string Key;
    bool Bound;
    bool Qualified;
    bool Failed;
    bool Cached;
    string Reason;
    int Leg;
    int ChainSteps;
    float ChainLength;
    vector ChainFrom;
    vector ClosestEnd;
    float ClosestGap;
    int PathCalls;
    int Continuations;
    // Tentative chain geometry is committed only after its target qualifies.
    ref array<vector> AttemptPoints = new array<vector>();
    int StartIndex;
    int Kept = 1;
    int Skipped;
    int Snapped;
    string SkippedPoints;
    bool Closed;
    bool OpenRoute;
    // chain-v4: one bounded retry of a refused outdoor route on outdoor-ground
    // samples (INSIDE excluded); Outdoor counts the points that found ground.
    bool OutdoorPass;
    int Outdoor;
    Object HouseObject;
    vector CacheWorld;
    vector CacheOrientation;
    bool Diagnosed;
    bool Transient;
    bool Completed;
    bool Materialized;
    int AdmittedAt;
    string ProposalId;
    string ProviderFaction;
    string LocalityId;
    int OpportunityAt;
}
// HC-18 verified intent/backup/copy/readback, same protocol as HCWorldStore.
// Native scripts-1.30.164289: JsonFileLoader.c:69,85; EnSystem.c:397,528,531.
// HCWorldStore.Read/Write supply bounded IO; no rename/fsync claim. Interrupted
// cursor intent is discarded on restart; primary then backup restore fairness. Routine observation checkpoints
// use the shared staged scheduler; selection intent is a synchronous barrier.
class HCXAILocalitySave : HCSaveJob
{
    static const string PATH = "$profile:HollowCountry/expansion-ai-locality-rotation.json";
    static const string INTENT = "$profile:HollowCountry/expansion-ai-locality-rotation.pending.json";
    static const string BACKUP = "$profile:HollowCountry/expansion-ai-locality-rotation.bak.json";
    ref HCXAILocalityRotation Data;
    bool Fault;
    protected int m_Stage;
    protected int m_Revision;
    protected int m_SnapshotRevision;
    protected string m_Text;

    override string HCName() { return "HC-18-localities"; }
    void HCChanged() { m_Revision++; HCDirty = true; }
    bool HCLoad(string world)
    {
        if (FileExist(INTENT))
        {
            Print("[HC Plan] HC-18 rotation interrupted cursor intent discarded; primary then backup runtime=PENDING");
            DeleteFile(INTENT);
        }
        if (this.HCRestore(PATH, world)) { return true; }
        if (this.HCRestore(BACKUP, world))
        {
            Print("[HC Plan] HC-18 rotation cursor recovered from backup runtime=PENDING");
            // Remove an invalid primary so the next checkpoint cannot back it
            // up over the valid recovery copy. This is cursor data only.
            if (FileExist(PATH)) { DeleteFile(PATH); }
            return true;
        }
        if (!FileExist(PATH) && !FileExist(BACKUP))
        {
            Data = new HCXAILocalityRotation();
            Data.WorldName = world;
            return true;
        }
        Fault = true;
        return false;
    }
    protected bool HCRestore(string path, string world)
    {
        if (!FileExist(path)) { return false; }
        string error;
        if (!JsonFileLoader<HCXAILocalityRotation>.LoadData(HCWorldStore.Read(path), Data, error) || !Data || Data.SchemaVersion != 1 || Data.WorldName != world || !Data.Rows || Data.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows() || Data.SelectionSerial < 0 || Data.NextId.Length() > 48) { return false; }
        map<string, bool> ids = new map<string, bool>();
        foreach (HCXAILocalityCoverage row : Data.Rows)
        {
            if (!row || !HCXAIRules.Token(row.LocalityId) || row.LocalityId.Length() > 48 || ids.Contains(row.LocalityId) || row.NextSite < 0 || row.LastSelected < 0 || row.LastSelected > Data.SelectionSerial || row.LastObserved < 0 || row.LastObserved > row.LastSelected || row.PendingSinceSerial < 0 || row.PendingSinceSerial > Data.SelectionSerial || row.RetryAt < 0 || row.Refusal.Length() > 192) { return false; }
            // Native zero-fill reads a missing Refusal as "": a pending row keeps its declared reason.
            if (row.Pending && row.Refusal == "") { row.Refusal = "route_not_reviewed"; }
            ids.Set(row.LocalityId, true);
        }
        return true;
    }
    override int HCStep()
    {
        if (Fault || !Data) { return HCSaveJob.STEP_FAILED; }
        string error;
        if (m_Stage == 0)
        {
            if (FileExist(INTENT) || !JsonFileLoader<HCXAILocalityRotation>.MakeData(Data, m_Text, error) || m_Text.Length() > HCWorldStore.MAX_BYTES) { Fault = true; return HCSaveJob.STEP_FAILED; }
            m_SnapshotRevision = m_Revision;
            MakeDirectory("$profile:HollowCountry");
            if (!HCWorldStore.Write(INTENT, m_Text)) { Fault = true; return HCSaveJob.STEP_FAILED; }
            m_Stage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (m_Stage == 1)
        {
            if (FileExist(PATH))
            {
                string prior = HCWorldStore.Read(PATH);
                if (prior == "" || !CopyFile(PATH, BACKUP) || HCWorldStore.Read(BACKUP) != prior) { Fault = true; return HCSaveJob.STEP_FAILED; }
            }
            m_Stage = 2;
            return HCSaveJob.STEP_MORE;
        }
        if (m_Stage == 2)
        {
            if (!CopyFile(INTENT, PATH) || HCWorldStore.Read(PATH) != m_Text) { Fault = true; return HCSaveJob.STEP_FAILED; }
            m_Stage = 3;
            return HCSaveJob.STEP_MORE;
        }
        if (!DeleteFile(INTENT) || FileExist(INTENT)) { Fault = true; return HCSaveJob.STEP_FAILED; }
        m_Stage = 0;
        m_Text = "";
        // An observed spawn during staging must not be lost by dirty clearing.
        if (m_SnapshotRevision != m_Revision) { return HCSaveJob.STEP_MORE; }
        return HCSaveJob.STEP_DONE;
    }
}
// Routes cache writes coalesce on the shared scheduler. The cache is disposable: a lost
// write only requalifies routes. Failure is ignored, as the direct write always was.
class HCXAIRouteSave : HCSaveJob
{
    HCXAISiteDirector Owner;
    override string HCName() { return "HCX-routes"; }
    override bool HCWrite()
    {
        if (Owner) { Owner.SaveRoutes(); }
        return true;
    }
}
class HCXAISiteDirector : Managed
{
    static const string POLICY = "$profile:HollowCountry/expansion-ai-sites.json";
    static const string ROUTES = "$profile:HollowCountry/expansion-ai-routes.json";
    static const string CACHES = "$profile:HollowCountry/expansion-ai-caches.json";
    static const string OWNED = "$profile:HollowCountry/expansion-ai-owned.json";
    static const string DIAGNOSTIC = "$profile:HollowCountry/acceptance/xai_diagnostic_spawn.enable";
    static const string OBSERVER = "native-eai";
    static const int WORK_PER_TICK = 4;
    protected static HCXAISiteDirector s_Active;

    protected ref HCXAISitePolicy m_Policy;
    protected ref HCXAIRouteCache m_Routes;
    protected ref HCXAICacheJournal m_Caches;
    protected ref HCXAIOwnership m_Owned;
    protected ref array<ref HCXAISiteState> m_States = new array<ref HCXAISiteState>();
    protected ref PGFilter m_Filter;
    // Sampling only: never passed to FindPath, never used for holdouts.
    protected ref PGFilter m_OutdoorFilter;
    protected string m_Build;
    protected string m_Phase = "wait";
    protected int m_Cursor;
    protected int m_CacheCursor;
    protected int m_RespawnCursor;
    protected int m_RingCandidates;
    // Ring search start angle; advanced past each rejected candidate so a
    // stationary observer does not get the same refused point forever.
    protected float m_RingDegrees;
    protected int m_Ticks;
    protected int m_LastActiveAI = -1;
    protected bool m_Diagnostic;
    protected bool m_RespawnOff; // ai-respawn.disable, probed once at Start (the marker contract is probe-once)
    protected ref HCXAIRouteSave m_RouteSave;
    protected bool m_WaitLogged;
    protected bool m_RadiusClampLogged;
    protected bool m_OwnedSaved = true;
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
    protected int m_LocalityNextAttemptAt;
    protected int m_LocalityNextPendingLogAt;
    protected bool m_LocalityRefused;
    protected string m_LocalityStatus = "off";
    protected string m_CoverageFault;
    protected int m_LocalitiesWithoutSites;
    protected ref HCOperationalStatus m_OperationalStatus = new HCOperationalStatus;

    // Cached owner state only: status reads never inspect players or patrols.
    HCOperationalStatus HCGetOperationalStatus()
    {
        if (m_Phase == "wait" || m_Phase == "bind" || m_Phase == "qualify" || m_Phase == "create")
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
    // Read by HCXAIEncounters only; encounters never add, remove or move states.
    array<ref HCXAISiteState> States() { return m_States; }
    // This process's ownership session (previous + 1), 0 before reconciliation.
    int OwnedSession()
    {
        if (!m_Owned) { return 0; }
        return m_Owned.Session;
    }

    // Read-only boot/status seam for the lead's adapter integration. Counts
    // describe catalog/candidate state, never observed coverage acceptance.
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
        string line = "[HC Plan] HC-18 localities=" + count.ToString() + " page=" + page.ToString() + " oldest_pending=" + oldest;
        return line + " cursor=" + next + " state=" + m_LocalityStatus + " runtime=PENDING";
    }
    protected bool HCStartLocalities()
    {
        if (!FileExist(LOCALITIES))
        {
            // Reuse the complete site policy as a bounded fallback queue. No
            // locality positions or routes are invented when the pack is absent.
            m_CoverageFault = "LOCALITY_CATALOG_MISSING_POLICY_QUEUE_RETAINED";
            Print("[HC Coverage] " + m_CoverageFault + " runtime=PENDING");
            m_Localities = new HCXAILocalityCatalog();
            m_Localities.WorldName = m_Policy.WorldName;
        }
        string error;
        if (FileExist(LOCALITIES))
        {
            string catalogText = HCWorldStore.Read(LOCALITIES);
            if (!JsonFileLoader<HCXAILocalityCatalog>.LoadData(catalogText, m_Localities, error) || !m_Localities) { m_LocalityStatus = "refused:catalog_unreadable"; return false; }
            if (!HCJsonFields.Has(catalogText, "Enabled")) { m_Localities.Enabled = true; }
        }
        // Empty fallback catalog is populated from actual authored site IDs.
        if (!FileExist(LOCALITIES) && !this.HCReconcileLocalitySites()) { return false; }
        string problem = HCXAISiteRules.HCLocalityProblem(m_Localities, m_Policy);
        if (problem != "") { m_LocalityStatus = "refused:" + problem; return false; }
        if (FileExist("$profile:HollowCountry/acceptance/locality-route-observer.disable")) { m_Localities.Enabled = false; }
        Print(HCV2Admission.Line("HC-18", m_Localities.Enabled, "locality-route-observer", false) + " runtime=PENDING");
        if (!HCV2Admission.Admitted(m_Localities.Enabled))
        {
            m_Localities = null;
            Print(this.HCLocalitySummary() + " refusal=operator_off legacy_sites_retained");
            return true;
        }
        if (!this.HCReconcileLocalitySites()) { m_LocalityStatus = "refused:catalog_drift_capacity"; return false; }
        if (m_LocalitiesWithoutSites > 0)
        {
            m_CoverageFault = "LOCALITY_AUTHORED_SITE_DATA_MISSING";
            Print("[HC Coverage] " + m_CoverageFault + " localities=" + m_LocalitiesWithoutSites.ToString() + " existing_routes_retained=1 runtime=PENDING");
        }
        m_LocalitySave = new HCXAILocalitySave();
        if (!m_LocalitySave.HCLoad(m_Localities.WorldName)) { m_LocalityStatus = "refused:rotation_quarantined"; return false; }
        foreach (HCXAILocality locality : m_Localities.Localities)
        {
            if (HCXAISiteRules.HCCoverage(m_LocalitySave.Data, locality.Id)) { continue; }
            if (m_LocalitySave.Data.Rows.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { m_LocalityStatus = "refused:coverage_history_full"; return false; }
            HCXAILocalityCoverage added = new HCXAILocalityCoverage();
            added.LocalityId = locality.Id;
            added.PendingSinceSerial = m_LocalitySave.Data.SelectionSerial;
            m_LocalitySave.Data.Rows.Insert(added);
        }
        if (m_LocalitySave.Data.NextId == "") { m_LocalitySave.Data.NextId = m_Localities.Localities[0].Id; }
        m_LocalitySave.HCChanged();
        if (!HCSaveScheduler.HCFlush(m_LocalitySave)) { m_LocalityStatus = "refused:rotation_save"; return false; }
        m_LocalityStatus = "pending_provider";
        Print(this.HCLocalitySummary());
        return true;
    }
    protected int HCLocalityPageCount()
    {
        int count = 0;
        foreach (HCXAISiteState state : m_States)
        {
            if (state.LocalityId != "") { count++; }
        }
        return count;
    }
    protected bool HCHasSite(string id)
    {
        foreach (HCXAISiteState state : m_States)
        {
            if (!state.Transient && state.Site.Id == id) { return true; }
        }
        return false;
    }
    // Keep valid operator additions in single-site localities. Catalog IDs
    // absent from the current operator policy are skipped once at startup.
    protected bool HCReconcileLocalitySites()
    {
        int unknown = 0;
        m_LocalitiesWithoutSites = 0;
        // One pass builds the policy id set; the 523-row catalog would otherwise
        // rescan all 528 sites for every catalog id in a single startup tick.
        map<string, bool> policyIds = new map<string, bool>();
        foreach (HCXAISite candidate : m_Policy.Sites) { policyIds.Set(candidate.Id, true); }
        foreach (HCXAILocality locality : m_Localities.Localities)
        {
            int siteIndex = locality.SiteIds.Count() - 1;
            while (siteIndex >= 0)
            {
                if (!policyIds.Contains(locality.SiteIds[siteIndex])) { locality.SiteIds.RemoveOrdered(siteIndex); unknown++; }
                siteIndex--;
            }
            if (locality.SiteIds.Count() == 0) { m_LocalitiesWithoutSites++; }
        }
        if (unknown > 0) { Print("[HC Plan] HC-18 catalog_unknown_site skipped=" + unknown.ToString() + " operator policy retained runtime=PENDING"); }
        int syntheticIndex = 0;
        map<string, bool> mappedIds = new map<string, bool>();
        // Locality ids are indexed once; each added locality joins the set, so a collision probe is O(1).
        map<string, bool> localityIds = new map<string, bool>();
        foreach (HCXAILocality mappedLocality : m_Localities.Localities)
        {
            localityIds.Set(mappedLocality.Id, true);
            foreach (string mappedId : mappedLocality.SiteIds) { mappedIds.Set(mappedId, true); }
        }
        foreach (HCXAISite site : m_Policy.Sites)
        {
            if (mappedIds.Contains(site.Id)) { continue; }
            if (m_Localities.Localities.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { return false; }
            string id = site.Id;
            bool collision = localityIds.Contains(id);
            while (collision)
            {
                id = "hc-unmapped-" + syntheticIndex.ToString();
                syntheticIndex++;
                collision = localityIds.Contains(id);
            }
            localityIds.Set(id, true);
            HCXAILocality added = new HCXAILocality();
            added.Id = id;
            added.Source = "operator site policy";
            added.SiteIds.Insert(site.Id);
            m_Localities.Localities.Insert(added);
        }
        return true;
    }
    protected void HCAddLegacySites()
    {
        foreach (HCXAISite site : m_Policy.Sites)
        {
            if (site.Checkpoint && !HCXAIQualification.EncountersEnabled()) { continue; }
            if (this.HCHasSite(site.Id)) { continue; }
            HCXAISiteState added = new HCXAISiteState();
            added.Site = site;
            m_States.Insert(added);
        }
    }
    protected void HCLocalityFault()
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
    // Attempts have a durable cursor. A full page retains its next candidate:
    // advancing while full can alias periodic expiry and starve an island.
    // Geometry/provider refusals advance, keeping their coverage pending.
    protected void HCTryLocality(int now)
    {
        if (this.HCLocalityPageCount() >= HCXAISiteRules.HCPageSize(m_Localities, HCAILimits.Get().MaxActiveSites)) { return; }
        if (!HCSaveScheduler.HCFlush(m_LocalitySave)) { this.HCLocalityFault(); return; }
        HCXAILocalityRotation rotation = m_LocalitySave.Data;
        if (rotation.SelectionSerial >= 2147483646) { this.HCLocalityFault(); return; }
        int index = HCXAISiteRules.HCNextLocality(m_Localities, rotation);
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
            int tries = 0;
            while (tries < locality.SiteIds.Count() && selected.Count() < slots)
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
        m_LocalitySave.HCChanged();
        if (!HCSaveScheduler.HCFlush(m_LocalitySave)) { this.HCLocalityFault(); return; }
        if (selected.Count() == 0)
        {
            // Missing authored rows were diagnosed once at boot, not per lap.
            if (locality.SiteIds.Count() == 0) { return; }
            if (row.LastSelected == rotation.SelectionSerial && now >= m_LocalityNextPendingLogAt)
            {
                m_LocalityNextPendingLogAt = now + 300;
                Print("[HC Plan] HC-18 state=pending locality=" + locality.Id + " reason=" + row.Refusal + " pending=1 runtime=PENDING");
            }
            return;
        }
        foreach (HCXAISite admitted : selected)
        {
            HCXAISiteState state = new HCXAISiteState();
            state.Site = admitted;
            state.LocalityId = locality.Id;
            state.OpportunityAt = now;
            m_States.Insert(state);
        }
    }
    protected void HCStepLocalities()
    {
        if (!m_Localities || !m_LocalitySave || m_LocalityRefused) { return; }
        if (m_LocalitySave.Fault) { this.HCLocalityFault(); return; }
        int now = ExpansionStatic.GetTimestamp(true);
        if (now < 1 || now > 2146878847) { this.HCLocalityFault(); return; }
        // HC_WORK_AI_SITES is the lead-owned shared consumer integration.
        // Reserve candidate work separately from maintenance. Otherwise four
        // armed controllers consume every local unit and prevent page growth.
        m_LocalityUnits.HCReset(HCXAISiteDirector.WORK_PER_TICK + HCXAISiteRules.HCAttemptsPerTick(m_Localities));
        m_LocalityWork.HCReset(HCXAISiteDirector.WORK_PER_TICK);
        int visited = 0;
        int count = m_States.Count();
        while (visited < count && visited < HCXAISiteDirector.WORK_PER_TICK && m_States.Count() > 0 && m_LocalityWork.HCContinue() && m_LocalityUnits.HCTake(1))
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_AI_SITES, 1)) { return; }
            if (m_LocalityCursor >= m_States.Count()) { m_LocalityCursor = 0; }
            HCXAISiteState state = m_States[m_LocalityCursor];
            visited++;
            if (state.LocalityId == "") { m_LocalityCursor++; continue; }
            // With enough slots, keep every legacy-eligible controller armed.
            // Expiry is solely for fairness among candidates beyond the cap.
            bool expired = m_Policy.Sites.Count() > HCXAISiteRules.HCPageSize(m_Localities, HCAILimits.Get().MaxActiveSites) && now >= state.OpportunityAt + HCXAISiteRules.HCOpportunitySeconds(m_Localities);
            bool live = state.Patrol && (state.Patrol.m_HCPendingMembers > 0 || (state.Patrol.m_Group && state.Patrol.m_Group.Count() > 0));
            if (state.Patrol && state.Patrol.m_Group && state.Patrol.m_Group.Count() > 0)
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
            // Never evict a live/deferred member, or a bound encounter. Natural
            // provider retirement remains observer/combat guarded. Empty patrol
            // controllers can be discarded; no actor is moved or spawned here.
            HCXAIEncounters encounters = HCXAIEncounters.Active();
            bool boundEncounter = encounters && encounters.SiteBound(state.Site.Id);
            if ((expired || state.Failed) && !live && !boundEncounter)
            {
                if (state.Patrol) { state.Patrol.m_HCFinished = true; state.Patrol.Stop(); state.Patrol.Delete(); }
                HCAIBudget.Release("site:" + state.Site.Id);
                m_States.RemoveOrdered(m_LocalityCursor);
                continue;
            }
            m_LocalityCursor++;
            if (state.Failed || state.Patrol) { continue; }
            bool createFailed = false;
            if (!state.Bound) { this.Bind(state); }
            else if (!state.Qualified)
            {
                int pathCallsBefore = state.PathCalls;
                this.QualifyStep(state);
                // [HC TickCost] window 12 of 096: the admitted row is 1 of a probe's 64 units.
                // Local units bound the slice; shared units debit the pool once, only for a real probe.
                if (state.PathCalls > pathCallsBefore)
                {
                    m_LocalityUnits.HCCharge(63);
                    HCServer.HCTickWork().HCCharge(63);
                }
                if (state.Failed || state.Qualified) { this.HCRoutesChanged(); }
            }
            else
            {
                this.Create(state);
                createFailed = !state.Patrol;
            }
            if (state.Failed || createFailed)
            {
                HCXAILocalityCoverage row = HCXAISiteRules.HCCoverage(m_LocalitySave.Data, state.LocalityId);
                row.Pending = true;
                row.Refusal = "route_geometry_or_provider_refused";
                row.RetryAt = now + HCXAISiteRules.HCRetrySeconds(m_Localities);
                m_LocalitySave.HCChanged();
                state.Failed = true;
                Print("[HC Plan] HC-18 state=refused locality=" + state.LocalityId + " reason=" + row.Refusal + " pending=1 runtime=PENDING");
            }
        }
        int attempts = 0;
        if (now < m_LocalityNextAttemptAt) { return; }
        while (attempts < HCXAISiteRules.HCAttemptsPerTick(m_Localities) && m_LocalityWork.HCContinue() && m_LocalityUnits.HCTake(1))
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_AI_SITES, 1)) { return; }
            this.HCTryLocality(now);
            attempts++;
            if (m_LocalityRefused) { return; }
        }
        if (attempts > 0) { m_LocalityNextAttemptAt = now + HCXAISiteRules.HCSelectionIntervalSeconds(m_Localities); }
    }

    // Includes full deferred-member reservations and not-yet-created transient
    // states. Authored and transient patrols consult the same ledger at spawn.
    string BudgetProblem(int actorCap, HCXAISitePatrol exceptPatrol)
    {
        int reservedSites = 0;
        int reservedActors = 0;
        foreach (HCXAISiteState reservation : m_States)
        {
            if (reservation.Completed) { continue; }
            if (exceptPatrol && reservation.Patrol == exceptPatrol) { continue; }
            // Empty native groups can outlive every member. Only an uncreated
            // transient, a living member or a queued deferred member owns a slot.
            if (!(reservation.Transient && !reservation.Materialized))
            {
                if (!reservation.Patrol || !reservation.Patrol.m_Group || (reservation.Patrol.m_Group.Count() == 0 && reservation.Patrol.m_HCPendingMembers <= 0))
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

    // true reserves a one-shot site; route/observer/create failures complete via
    // the bridge callback. It does not mean actors already exist or acceptance.
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
        eAIFaction faction = eAIFaction.Create(providerFaction);
        if (!faction || faction.IsInvincible() || faction.IsObserver() || faction.IsPassive() || faction.HasUnlimitedStamina() || faction.GetMeleeDamageMultiplier() != 1 || faction.GetMeleeYeetForce() != 0 || !FileExist(EXPANSION_LOADOUT_FOLDER + loadout + ".json")) { reason = "transient faction or loadout unavailable/unfair"; return false; }
        reason = this.MemberProblemFor(placePos);
        if (reason != "") { return false; }
        HCXAISite transientSite = new HCXAISite();
        transientSite.Id = "transient:" + proposalId;
        transientSite.Kind = "patrol";
        transientSite.Faction = providerFaction;
        transientSite.Loadout = loadout;
        transientSite.NumberOfAI = actorCap;
        transientSite.NumberOfAIMax = actorCap;
        // Small place-relative loop, never player-relative. All four endpoints
        // must go through Bind and the authored RouteMinimum/FindPath process.
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
        Print("[HC Expansion AI] materializer transient site=" + proposalId + " faction=" + factionId + " actors=" + actorCap.ToString());
        reason = "";
        return true;
    }

    // Configured bounded reserved states, one qualification step each/tick. An idle
    // trigger/blocked route gets five minutes, then traces; live groups retain
    // their reservation until death or the observed native despawn callback.
    protected void StepTransients()
    {
        int transientIndex = m_States.Count() - 1;
        while (transientIndex >= 0)
        {
            HCXAISiteState transientState = m_States[transientIndex];
            transientIndex--;
            if (!transientState.Transient) { continue; }
            if (transientState.Completed) { m_States.RemoveOrdered(transientIndex + 1); continue; }
            if (transientState.Materialized)
            {
                if (!transientState.Patrol) { this.FinishTransient(transientState, true, 0); continue; }
                if (!transientState.Patrol.m_Group)
                {
                    // Preserve provider load-balancing cleanup even when a
                    // native group was removed outside its normal callback.
                    transientState.Patrol.Despawn();
                    this.FinishTransient(transientState, true, 0);
                }
                else if (transientState.Patrol.m_Group.Count() == 0)
                {
                    // Balances the provider's active-patrol counter once;
                    // do not ClearAI here, so lootable corpses remain native.
                    transientState.Patrol.WasGroupDestroyed();
                    this.FinishTransient(transientState, true, 0);
                }
                continue;
            }
            int transientNow = GetGame().GetTime();
            if (transientNow < transientState.AdmittedAt || transientNow - transientState.AdmittedAt >= 300000)
            {
                transientState.Failed = true;
                transientState.Reason = "transient qualification/activation expired";
            }
            if (transientState.Failed) { this.FinishTransient(transientState, false, 0); continue; }
            if (!transientState.Bound) { this.Bind(transientState); continue; }
            if (!transientState.Qualified) { this.QualifyStep(transientState); continue; }
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
            state.Patrol.Stop();
            state.Patrol.Delete();
        }
        Print("[HC Expansion AI] materializer ended site=" + state.ProposalId + " materialized=" + materialized.ToString() + " survivors=" + survivors.ToString() + " reason=" + state.Reason);
        HCXMaterializerBridge.SiteEnded(state.ProposalId, materialized, survivors);
    }

    void Start()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        s_Active = this;
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
        // One provenance helper covers every expansion-ai profile copy sharing
        // the PBO-default path, before its existing owner reads/provisions it.
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
        // Startup step markers: log timestamps locate slow steps on large policies.
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
        Print("[HC Expansion AI] start step=policy_checked");
        if (!this.HCStartLocalities())
        {
            this.HCLocalityFault();
        }
        Print(HCV2Admission.Line("AIFreshRespawn", !m_RespawnOff, "EXP-P2", HCV2Gates.Qualified("EXP-P2")) + " runtime=PENDING");
        Print("[HC Expansion AI] fresh respawn policy full=" + m_Policy.AIRespawnSeconds.ToString() + "s member=" + m_Policy.MemberReplaceSeconds.ToString() + "s mode=fresh-group runtime=PENDING");
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
            if (stopping.Patrol) { stopping.Patrol.Stop(); }
        }
        if (m_LocalitySave)
        {
            if (!HCSaveScheduler.HCFlush(m_LocalitySave)) { this.HCLocalityFault(); }
            HCSaveScheduler.HCUnregister(m_LocalitySave);
        }
        if (m_RouteSave)
        {
            HCSaveScheduler.HCFlush(m_RouteSave);
            HCSaveScheduler.HCUnregister(m_RouteSave);
            m_RouteSave = null;
        }
        this.SaveOwned();
        m_Phase = "stopped";
        m_LocalityStatus = "off";
        if (m_Localities) { Print(this.HCLocalitySummary()); }
        if (s_Active == this) { s_Active = null; }
    }
    void Step()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        m_Ticks++;
        if (m_Phase == "wait") { this.StepWait(); return; }
        if (m_Phase == "bind") { this.StepBind(); return; }
        if (m_Phase == "qualify") { this.StepQualify(); return; }
        if (m_Phase == "create") { this.StepCreate(); return; }
        if (m_Phase == "run") { this.StepRun(); }
    }
    protected void StepWait()
    {
        bool aiLoaded = GetExpansionSettings() && GetExpansionSettings().GetAI() && GetExpansionSettings().GetAI().IsLoaded();
        bool patrolLoaded = false;
        if (aiLoaded && GetExpansionSettings().GetAIPatrol(false)) { patrolLoaded = GetExpansionSettings().GetAIPatrol(false).IsLoaded(); }
        if (!aiLoaded || !patrolLoaded) { return; }
        HCXAIDefaults.ProvisionLoadouts(m_Policy); // once: the wait phase ends below
        HCXAISiteAdmission admission = this.Observe();
        string problem = HCXAISiteRules.AdmissionProblem(m_Policy, admission);
        if (problem != "")
        {
            m_Phase = "refused";
            Print("[HC Expansion AI] sites admission refused: " + problem);
            if (m_Localities) { m_LocalityStatus = "refused:provider_admission"; Print(this.HCLocalitySummary()); }
            return;
        }
        m_Routes = HCXAISiteDirector.LoadRoutes();
        m_Caches = HCXAISiteDirector.LoadCaches();
        if (m_Routes && !m_RouteSave)
        {
            m_RouteSave = new HCXAIRouteSave();
            m_RouteSave.Owner = this;
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
        int include = PGPolyFlags.UNREACHABLE | PGPolyFlags.DISABLED | PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE | PGPolyFlags.LADDER;
        int exclude = PGPolyFlags.CRAWL | PGPolyFlags.CROUCH | PGPolyFlags.SWIM_SEA | PGPolyFlags.SWIM;
        if (eAIBase.AI_HANDLEVAULTING) { include = include | PGPolyFlags.SPECIAL; }
        else { exclude = exclude | PGPolyFlags.SPECIAL; }
        m_Filter.SetFlags(include, exclude, PGPolyFlags.NONE);
        // Native: 3_Game/AI/AIWorld.c:1-26 PGPolyFlags, :65 PGFilter.SetFlags. Walkable
        // outdoor polygons only, as HCEventPoliceNav samples police barrel ground.
        m_OutdoorFilter = new PGFilter();
        m_OutdoorFilter.SetFlags(PGPolyFlags.WALK, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.INSIDE | PGPolyFlags.DOOR | PGPolyFlags.LADDER | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        foreach (HCXAISite site : m_Policy.Sites)
        {
            if (m_Localities) { break; } // sparse pages enter through HCStepLocalities
            if (site.Checkpoint && !HCXAIQualification.EncountersEnabled()) { continue; }
            HCXAISiteState state = new HCXAISiteState();
            state.Site = site;
            m_States.Insert(state);
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
    // Every admission input is observed here from the engine, never read from a file.
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
        foreach (HCXAISite factionSite : m_Policy.Sites)
        {
            eAIFaction faction = eAIFaction.Create(HCXFactions.SiteFaction(factionSite));
            if (!faction || faction.IsInvincible() || faction.IsObserver() || faction.IsPassive() || faction.HasUnlimitedStamina() || faction.GetMeleeDamageMultiplier() != 1 || faction.GetMeleeYeetForce() != 0)
            {
                a.UnfairFaction = factionSite.Faction;
                break;
            }
        }
        // The reviewed catalog names a handful of loadouts across hundreds of sites: stat each name once.
        map<string, bool> loadoutChecked = new map<string, bool>();
        foreach (HCXAISite loadoutSite : m_Policy.Sites)
        {
            if (loadoutChecked.Contains(loadoutSite.Loadout)) { continue; }
            loadoutChecked.Set(loadoutSite.Loadout, true);
            if (!FileExist(EXPANSION_LOADOUT_FOLDER + loadoutSite.Loadout + ".json"))
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
    // Orphan cleanup: any actor in an "HC:" group at startup belongs to a
    // previous session (this director has created nothing yet) and is removed.
    protected bool Reconcile()
    {
        HCXAIOwnership previous = HCXAISiteDirector.LoadOwned();
        if (!previous) { return false; }
        array<eAIBase> all = new array<eAIBase>();
        all.Copy(eAIBase.eAI_GetAll());
        int removed = 0;
        foreach (eAIBase actor : all)
        {
            if (!actor) { continue; }
            eAIGroup group = actor.GetGroup();
            if (!group) { continue; }
            string groupName = group.GetName();
            HCTextWindow groupWindow = new HCTextWindow(groupName);
            if (groupWindow.Length() < 3 || groupWindow.Range(0, 3) != "HC:") { continue; }
            actor.eAI_Despawn();
            removed++;
        }
        int rows = previous.Rows.Count();
        Print("[HC Expansion AI] sites ownership: previous session " + previous.Session.ToString() + " listed " + rows.ToString() + " live sites; removed " + removed.ToString() + " orphan actors");
        m_Owned = previous;
        m_Owned.Session = previous.Session + 1;
        // Kills were recorded (and saved) as they happened, so ClearedAt already
        // locks raided sites across the restart; an intact live group is not
        // looted gear and is not locked out.
        return this.SaveOwned();
    }
    protected void StepBind()
    {
        int work = 0;
        while (work < HCXAISiteDirector.WORK_PER_TICK && m_Cursor < m_States.Count())
        {
            if (!m_States[m_Cursor].Bound && !m_States[m_Cursor].Failed) { this.Bind(m_States[m_Cursor]); }
            m_Cursor++;
            work++;
        }
        if (m_Cursor < m_States.Count()) { return; }
        int bound = 0;
        foreach (HCXAISiteState counted : m_States)
        {
            if (counted.Bound) { bound++; }
        }
        Print("[HC Expansion AI] sites bound: " + bound.ToString() + "/" + m_States.Count().ToString() + "; qualifying routes on the navmesh");
        m_Phase = "qualify";
        m_Cursor = 0;
    }
    protected void Bind(HCXAISiteState state)
    {
        HCXAISite site = state.Site;
        if (site.Kind != "holdout")
        {
            foreach (vector waypoint : site.Waypoints)
            {
                state.Points.Insert(Vector(waypoint[0], GetGame().SurfaceY(waypoint[0], waypoint[2]), waypoint[2]));
            }
        }
        else
        {
            array<Object> objects = new array<Object>();
            array<CargoBase> cargos = new array<CargoBase>();
            GetGame().GetObjectsAtPosition(site.HousePosition, 10, objects, cargos);
            float best = 11;
            foreach (Object candidate : objects)
            {
                if (!candidate || candidate.GetType() != site.HouseClass) { continue; }
                float gap = vector.Distance(candidate.GetPosition(), site.HousePosition);
                if (gap < best)
                {
                    best = gap;
                    state.HouseObject = candidate;
                }
            }
            if (!state.HouseObject)
            {
                state.Failed = true;
                state.Reason = "house " + site.HouseClass + " not found at its position";
                Print("[HC Expansion AI] site " + site.Id + " not bound: " + state.Reason);
                return;
            }
            foreach (vector inner : site.LocalPoints)
            {
                state.Points.Insert(state.HouseObject.ModelToWorld(inner));
            }
            state.CacheWorld = ExpansionAISpawnBase.GetPlacementPosition(state.HouseObject.ModelToWorld(site.CacheLocal));
            state.CacheOrientation = state.HouseObject.GetOrientation();
        }
        ExpansionSHA256.Update(HCXAISiteRules.RouteText(site, m_Build));
        state.Key = ExpansionSHA256.HexDigest();
        ExpansionSHA256.Reset();
        if (state.Transient) { state.Key = "transient:" + state.ProposalId; }
        state.Bound = true;
    }
    protected HCXAIRouteRow RouteRow(string key)
    {
        if (key.Length() >= 10 && key.Substring(0, 10) == "transient:") { return null; }
        foreach (HCXAIRouteRow row : m_Routes.Rows)
        {
            if (row.Key == key) { return row; }
        }
        return null;
    }
    protected void StepQualify()
    {
        int work = 0;
        while (work < HCXAISiteDirector.WORK_PER_TICK && m_Cursor < m_States.Count())
        {
            HCXAISiteState state = m_States[m_Cursor];
            if (!state.Bound || state.Failed || state.Qualified)
            {
                m_Cursor++;
                continue;
            }
            this.QualifyStep(state);
            work++;
        }
        if (m_Cursor < m_States.Count()) { return; }
        int qualified = 0;
        foreach (HCXAISiteState counted : m_States)
        {
            if (counted.Qualified) { qualified++; }
        }
        this.SaveRoutes();
        if (m_RouteSave) { m_RouteSave.HCDirty = false; }
        Print("[HC Expansion AI] sites routes qualified: " + qualified.ToString() + "/" + m_States.Count().ToString() + " (chain-v4; navmesh sample + bounded FindPath chains, one outdoor-ground retry; cache " + HCXAISiteDirector.ROUTES + " keyed by algorithm, route and build)");
        m_Phase = "create";
        m_Cursor = 0;
    }
    // One unit of work: sample the bounded authored points (first call), then
    // at most one FindPath. Outdoor partial paths resume from their actual end.
    protected void QualifyStep(HCXAISiteState state)
    {
        AIWorld world = GetGame().GetWorld().GetAIWorld();
        HCXAIRouteRow cached = this.RouteRow(state.Key);
        if (cached && !cached.Qualified)
        {
            state.Failed = true;
            state.Reason = "cached refusal: " + cached.Reason;
            Print("[HC Expansion AI] site " + state.Site.Id + " route refused (cached for this route and build): " + cached.Reason);
            return;
        }
        float radius = 12;
        if (state.Site.Kind == "holdout") { radius = 2; }
        if (state.Sampled.Count() == 0)
        {
            if (state.Points.Count() < 2 || state.Points.Count() > 8)
            {
                this.Refuse(state, "2..8 authored waypoints are required");
                return;
            }
            foreach (vector wanted : state.Points)
            {
                vector found = this.NavSample(wanted, radius, m_Filter);
                if (found == vector.Zero)
                {
                    this.Refuse(state, HCXAISiteRules.LegProblem(false, false, 0, 0, 0, 0));
                    return;
                }
                state.Sampled.Insert(found);
            }
            state.PatrolPoints.Insert(state.Sampled[0]);
            if (cached && HCXAISiteRules.ReuseQualifiedRoute(state.Site.Kind))
            {
                int cachedIndex = 1;
                while (cachedIndex < state.Sampled.Count())
                {
                    state.PatrolPoints.Insert(state.Sampled[cachedIndex]);
                    cachedIndex++;
                }
                state.Qualified = true;
                state.Cached = true;
            }
            return;
        }
        int authoredCount = state.Sampled.Count();
        if (authoredCount < 2 || authoredCount > 8)
        {
            this.Refuse(state, "2..8 authored waypoints are required");
            return;
        }
        int minimum = HCXAISiteRules.RouteMinimum(state.Site.Kind);
        bool closing = state.Leg >= authoredCount - 1;
        if (closing && state.Kept < minimum && authoredCount - state.StartIndex - 1 >= minimum)
        {
            // Too few later targets were reachable (an isolated first point, or
            // an isolated kept group). Drop the first point, retry all later
            // points, and keep the site's consumed-call budget.
            state.StartIndex++;
            state.Kept = 1;
            state.Leg = state.StartIndex;
            state.Skipped = state.StartIndex;
            state.Snapped = 0;
            state.SkippedPoints = "";
            int droppedIndex = 0;
            while (droppedIndex < state.StartIndex)
            {
                state.SkippedPoints = state.SkippedPoints + " " + droppedIndex.ToString() + HCXAISiteRules.PointText(state.Sampled[droppedIndex]);
                droppedIndex++;
            }
            state.PatrolPoints.Clear();
            state.PatrolPoints.Insert(state.Sampled[state.StartIndex]);
            state.AttemptPoints.Clear();
            state.ChainSteps = 0;
            return;
        }
        if (closing && state.Kept < minimum)
        {
            this.RefuseOrRetry(state, "route minimum: kept=" + state.Kept.ToString() + " required=" + minimum.ToString() + "; " + state.Reason);
            return;
        }
        if (closing && (state.Site.Behaviour != "LOOP" || state.Closed || state.OpenRoute))
        {
            state.Qualified = true;
            state.Reason = "";
            HCXAIRouteRow passed = new HCXAIRouteRow();
            passed.Key = state.Key;
            passed.SiteId = state.Site.Id;
            passed.Qualified = true;
            this.Remember(passed);
            int legs = state.Kept - 1;
            if (state.Closed) { legs++; }
            string sampling = "navmesh";
            if (state.OutdoorPass) { sampling = "outdoor"; }
            string qualifiedLine = "[HC Expansion AI] site " + state.Site.Id + " route qualified: chain-v4 legs=" + legs.ToString() + " FindPath=" + state.PathCalls.ToString() + " continuations=" + state.Continuations.ToString();
            qualifiedLine = qualifiedLine + " patrol waypoints=" + state.PatrolPoints.Count().ToString() + " skipped=" + state.Skipped.ToString() + " snapped=" + state.Snapped.ToString() + " behaviour=" + HCXAISiteRules.PatrolBehaviour(state.Site.Behaviour, state.OpenRoute);
            qualifiedLine = qualifiedLine + " sampling=" + sampling + " outdoor=" + state.Outdoor.ToString() + "/" + authoredCount.ToString() + " skipped-points=" + state.SkippedPoints;
            Print("" + qualifiedLine);
            return;
        }
        if (state.PathCalls >= 96)
        {
            this.Refuse(state, "route search budget");
            return;
        }
        vector legFrom = state.PatrolPoints[state.PatrolPoints.Count() - 1];
        vector legTo = state.Sampled[(state.Leg + 1) % authoredCount];
        if (closing) { legTo = state.PatrolPoints[0]; }
        if (state.ChainSteps == 0)
        {
            state.ChainFrom = legFrom;
            state.ChainLength = 0;
            state.ClosestEnd = legFrom;
            state.ClosestGap = vector.Distance(legFrom, legTo);
            state.AttemptPoints.Clear();
        }
        TVectorArray path = new TVectorArray();
        bool pathFound = world.FindPath(state.ChainFrom, legTo, m_Filter, path);
        state.PathCalls++;
        state.ChainSteps++;
        float length = 0;
        float endGap = 1000;
        int pathPoints = 0;
        if (pathFound) { pathPoints = path.Count(); }
        int index = 1;
        while (index < pathPoints)
        {
            length = length + vector.Distance(path[index - 1], path[index]);
            index++;
        }
        vector pathEnd = state.ChainFrom;
        float advance = 0;
        if (pathPoints > 0)
        {
            pathEnd = path[pathPoints - 1];
            endGap = vector.Distance(pathEnd, legTo);
            advance = vector.Distance(state.ChainFrom, pathEnd);
            if (state.ChainSteps == 1 || endGap < state.ClosestGap)
            {
                state.ClosestGap = endGap;
                state.ClosestEnd = pathEnd;
            }
        }
        state.ChainLength = state.ChainLength + length;
        string problem = HCXAISiteRules.ChainAction(state.Site.Kind, state.ChainSteps, pathPoints, endGap, advance, state.ChainLength, vector.Distance(legFrom, legTo));
        // A closing near miss keeps stepping toward the first point, as chain-v2
        // did, before falling back to native ONCE.
        if (closing && problem == "snap" && state.Site.Kind != "holdout" && advance >= 0.5 && state.ChainSteps < 16) { problem = "continue"; }
        if (problem == "continue")
        {
            state.AttemptPoints.Insert(pathEnd);
            state.ChainFrom = pathEnd;
            state.Continuations++;
            return;
        }
        // A closing snap would move the first point and invalidate its outgoing
        // qualified leg. Keep that first point and use native ONCE instead.
        if (closing && problem == "snap") { problem = "closing path ends short of the waypoint"; }
        if (problem != "" && problem != "snap")
        {
            state.Reason = "leg " + state.Leg.ToString() + ": " + problem + "; from=" + HCXAISiteRules.PointText(legFrom) + "; to=" + HCXAISiteRules.PointText(legTo);
            state.Reason = state.Reason + "; closest=" + HCXAISiteRules.PointText(state.ClosestEnd) + "; gap=" + state.ClosestGap.ToString() + "; steps=" + state.ChainSteps.ToString();
            state.AttemptPoints.Clear();
            state.ChainSteps = 0;
            if (closing)
            {
                state.OpenRoute = true;
                return;
            }
            int skippedIndex = state.Leg + 1;
            state.Skipped++;
            state.SkippedPoints = state.SkippedPoints + " " + skippedIndex.ToString() + HCXAISiteRules.PointText(state.Sampled[skippedIndex]);
            state.Leg++;
            // Refuse immediately when no remaining/restarted route can meet
            // the minimum; keep the final leg diagnostic for data correction.
            if (state.Leg >= authoredCount - 1 && state.Kept < minimum && authoredCount - state.StartIndex - 1 < minimum)
            {
                this.RefuseOrRetry(state, "route minimum: kept=" + state.Kept.ToString() + " required=" + minimum.ToString() + "; " + state.Reason);
            }
            return;
        }
        foreach (vector acceptedEnd : state.AttemptPoints)
        {
            state.PatrolPoints.Insert(acceptedEnd);
        }
        state.AttemptPoints.Clear();
        state.ChainSteps = 0;
        if (closing)
        {
            state.Closed = true;
            return;
        }
        // A snap keeps the end of the path that qualified it (endGap above).
        if (problem == "snap") { legTo = pathEnd; }
        vector lastKept = state.PatrolPoints[state.PatrolPoints.Count() - 1];
        if (!HCXAISiteRules.SnapKeeps(lastKept, legTo))
        {
            int mergedIndex = state.Leg + 1;
            state.Skipped++;
            state.SkippedPoints = state.SkippedPoints + " " + mergedIndex.ToString() + HCXAISiteRules.PointText(state.Sampled[mergedIndex]);
            state.Leg++;
            return;
        }
        if (problem == "snap") { state.Snapped++; }
        state.PatrolPoints.Insert(legTo);
        state.Kept++;
        state.Leg++;
    }
    // Native: 3_Game/AI/AIWorld.c:122 SampleNavmeshPosition (false leaves the
    // output untouched). vector.Zero means no sample, as in HCEventPoliceNav.
    protected vector NavSample(vector wanted, float radius, PGFilter filter)
    {
        AIWorld world = GetGame().GetWorld().GetAIWorld();
        if (!world) { return vector.Zero; }
        vector found = wanted;
        if (!world.SampleNavmeshPosition(wanted, radius, filter, found)) { return vector.Zero; }
        return found;
    }
    // Outdoor walkable ground near the terrain (Game.c:1176 SurfaceY); a sample
    // more than 2 m off the terrain is a roof, deck or ramp and is refused.
    protected vector GroundSample(vector probe, float radius)
    {
        vector found = this.NavSample(probe, radius, m_OutdoorFilter);
        if (found == vector.Zero) { return vector.Zero; }
        if (Math.AbsFloat(found[1] - GetGame().SurfaceY(found[0], found[2])) > 2) { return vector.Zero; }
        return found;
    }
    // At most five bounded samples: the terrain-projected authored point, then
    // four probes 12 m east, west, north and south; the horizontally nearest
    // ground wins. vector.Zero when no outdoor ground is found.
    protected vector OutdoorSample(vector wanted)
    {
        vector centre = this.GroundSample(wanted, 16);
        if (centre != vector.Zero) { return centre; }
        vector best = vector.Zero;
        float bestGap = 1000;
        int probe = 0;
        while (probe < 4)
        {
            float dx = 0;
            float dz = 0;
            if (probe == 0) { dx = 12; }
            if (probe == 1) { dx = -12; }
            if (probe == 2) { dz = 12; }
            if (probe == 3) { dz = -12; }
            float px = wanted[0] + dx;
            float pz = wanted[2] + dz;
            vector candidate = this.GroundSample(Vector(px, GetGame().SurfaceY(px, pz), pz), 8);
            if (candidate != vector.Zero)
            {
                float gap = vector.Distance(Vector(candidate[0], 0, candidate[2]), Vector(wanted[0], 0, wanted[2]));
                if (gap < bestGap)
                {
                    bestGap = gap;
                    best = candidate;
                }
            }
            probe++;
        }
        return best;
    }
    // A refused outdoor route gets one retry with outdoor-ground samples. The
    // first pass is unchanged, so routes that qualify keep their FindPath
    // sequence. PathCalls and Continuations stay cumulative: one 96-call budget.
    protected void RefuseOrRetry(HCXAISiteState state, string reason)
    {
        int count = state.Sampled.Count();
        if (state.Site.Kind == "holdout" || state.OutdoorPass || state.PathCalls >= 96 || count < HCXAISiteRules.RouteMinimum(state.Site.Kind) || state.Points.Count() != count)
        {
            this.Refuse(state, reason);
            return;
        }
        TVectorArray ground = new TVectorArray();
        int outdoor = 0;
        int index = 0;
        while (index < count)
        {
            vector found = this.OutdoorSample(state.Points[index]);
            if (found == vector.Zero) { ground.Insert(state.Sampled[index]); }
            else
            {
                ground.Insert(found);
                outdoor++;
            }
            index++;
        }
        state.OutdoorPass = true;
        state.Outdoor = outdoor;
        if (outdoor == 0)
        {
            this.Refuse(state, reason);
            return;
        }
        Print("[HC Expansion AI] site " + state.Site.Id + " route retry with outdoor ground samples (outdoor=" + outdoor.ToString() + "/" + count.ToString() + ") after: " + reason);
        state.Sampled.Clear();
        foreach (vector point : ground)
        {
            state.Sampled.Insert(point);
        }
        state.PatrolPoints.Clear();
        state.PatrolPoints.Insert(state.Sampled[0]);
        state.AttemptPoints.Clear();
        state.Leg = 0;
        state.StartIndex = 0;
        state.Kept = 1;
        state.Skipped = 0;
        state.Snapped = 0;
        state.SkippedPoints = "";
        state.ChainSteps = 0;
        state.Closed = false;
        state.OpenRoute = false;
        state.Reason = "";
    }
    protected void Refuse(HCXAISiteState state, string reason)
    {
        string text = reason;
        if (state.OutdoorPass) { text = "outdoor=" + state.Outdoor.ToString() + "/" + state.Sampled.Count().ToString() + "; " + reason; }
        state.Failed = true;
        state.Reason = text;
        HCXAIRouteRow failed = new HCXAIRouteRow();
        failed.Key = state.Key;
        failed.SiteId = state.Site.Id;
        failed.Qualified = false;
        failed.Reason = text;
        this.Remember(failed);
        Print("[HC Expansion AI] site " + state.Site.Id + " route refused: " + text);
    }
    protected void Remember(HCXAIRouteRow row)
    {
        // Transient route outcomes live only in their temporary state.
        if (row.SiteId.Length() >= 10 && row.SiteId.Substring(0, 10) == "transient:") { return; }
        int index = m_Routes.Rows.Count() - 1;
        while (index >= 0)
        {
            if (m_Routes.Rows[index].SiteId == row.SiteId) { m_Routes.Rows.Remove(index); }
            index--;
        }
        if (m_Routes.Rows.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { m_Routes.Rows.Remove(0); }
        m_Routes.Rows.Insert(row);
    }
    protected void StepCreate()
    {
        int work = 0;
        while (work < HCXAISiteDirector.WORK_PER_TICK && m_Cursor < m_States.Count())
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
    protected void Create(HCXAISiteState state)
    {
        HCXAISite site = state.Site;
        ExpansionAIDynamicSpawnBase config = new HCXAISiteSpawnConfig();
        config.Name = "HC:" + site.Id;
        string populationKind = site.Kind;
        if (site.Kind == "holdout") { populationKind = "occupation"; }
        if (site.Kind == "scavenger") { populationKind = "party"; }
        int population = HCAILimits.GroupSize(HCAILimits.Get().WorldSeed, site.Id, populationKind);
        if (state.Transient) { population = site.NumberOfAIMax; }
        site.NumberOfAI = population;
        site.NumberOfAIMax = population;
        config.NumberOfAI = population;
        config.NumberOfAIMax = population;
        config.Speed = site.Speed;
        config.UnderThreatSpeed = "SPRINT";
        config.Behaviour = HCXAISiteRules.PatrolBehaviour(site.Behaviour, state.OpenRoute);
        config.Faction = HCXFactions.SiteFaction(site);
        if (state.Transient) { config.Faction = state.ProviderFaction; }
        config.Loadout = site.Loadout;
        config.Persist = false;
        config.CanBeLooted = true;
        config.UnlimitedReload = 0;
        config.Chance = 1.0;
        config.CanBeTriggeredByAI = false;
        config.CanSpawnInContaminatedArea = false;
        config.MinDistRadius = HCPerceptionRing.HCSpawnMin();
        // Start with the event-binding radius (EncounterRadius), then apply
        // operator activation tuning. Perception and event bindings stay native.
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
        if (providerIssue == "") { providerIssue = HCXAIRules.PatrolProblem(config, state.PatrolPoints); }
        if (providerIssue != "")
        {
            Print("[HollowCountry] Living AI admission refused: " + site.Id + ": " + providerIssue);
            return;
        }
        HCXAISitePatrol patrol = eAIDynamicPatrolT<HCXAISitePatrol>.CreateEx(config, vector.Zero);
        if (!patrol)
        {
            Print("[HC Expansion AI] site " + site.Id + " native patrol setup refused");
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
    float HCActivationRadius(HCXAISite site, bool transient)
    {
        float radius = site.ActivationRadius;
        if (!transient) { radius = HCXAISiteRules.EncounterRadius(site.ActivationRadius); }
        float scale = m_Policy.ActivationRadiusScale;
        if (scale == 0) { scale = 1.0; }
        radius = radius * scale;
        // ExpansionAIPatrolBase.c:218-219; eAIDynamicPatrol.c:172-185
        // (installed read-only xref): native minimum/maximum trigger distances.
        // Scaled authored radius stays a lower bound, widened to SpawnMax.
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
        this.HCStepLocalities();
        if (m_Phase != "run") { return; }
        if (m_GroupScaling) { this.HCRefreshGroupFactor(); }
        if (!m_OwnedSaved && m_Ticks % 60 == 0) { this.SaveOwned(); }
        this.StepTransients();
        this.HCStepRespawns();
        this.StepCache();
        if (m_Diagnostic) { this.StepDiagnostic(); }
        if (m_Ticks % 60 != 0) { return; }
        int sites = 0;
        int actors = 0;
        foreach (HCXAISiteState counted : m_States)
        {
            if (!counted.Patrol || !counted.Patrol.m_Group) { continue; }
            sites++;
            actors = actors + counted.Patrol.m_Group.Count();
        }
        if (actors == m_LastActiveAI) { return; }
        m_LastActiveAI = actors;
        Print("[HC Expansion AI] sites active: " + sites.ToString() + " sites, " + actors.ToString() + " actors");
    }
    // Diagnostic only (marker off by default): the first created site of each
    // kind spawns once with no player so Wine runs can observe loadouts.
    protected void StepDiagnostic()
    {
        map<string, bool> done = new map<string, bool>();
        foreach (HCXAISiteState state : m_States)
        {
            if (state.Diagnosed) { done.Set(state.Site.Kind, true); }
        }
        foreach (HCXAISiteState candidate : m_States)
        {
            if (candidate.Transient || !candidate.Patrol || candidate.Diagnosed || done.Contains(candidate.Site.Kind)) { continue; }
            candidate.Diagnosed = true;
            Print("[HC Expansion AI] DIAGNOSTIC spawn of site " + candidate.Site.Id + " (" + candidate.Site.Kind + ")");
            candidate.Patrol.Spawn();
            return;
        }
    }
    // Select only an unmaterialized outdoor patrol anchor. HCFindLand is a
    // proposal; navmesh, route reachability and final sight veto still own it.
    // Native Game.c:1196 SurfaceIsSea, :1197 SurfaceIsPond; Object.c:287
    // GetPosition, :517 IsAlive; Man.c:21 GetIdentity; AIWorld.c:98 FindPath.
    // Expansion eAIDynamicPatrol.c:17 m_Position, :617 SpawnAI(m_Position).
    string HCPrepareRingSpawn(HCXAISitePatrol patrol)
    {
        if (!m_Policy || m_Phase != "run") { return "sites not running"; }
        if (patrol.m_Group || patrol.m_HCTransient || patrol.m_HCKind == "holdout") { return ""; }
        vector original = patrol.m_Position;
        float minimum = HCPerceptionRing.HCSpawnMin();
        if (this.NearestPlayer(original) >= minimum && !GetGame().SurfaceIsSea(original[0], original[2]) && !GetGame().SurfaceIsPond(original[0], original[2])) { return ""; }
        this.HCRefreshPlayers();
        array<vector> ringObservers = new array<vector>();
        array<Man> ringPlayers = m_Players;
        vector centre = vector.Zero;
        float nearestGap = -1;
        foreach (Man ringPlayer : ringPlayers)
        {
            if (!ringPlayer || !ringPlayer.GetIdentity() || !ringPlayer.IsAlive()) { continue; }
            vector observerPoint = ringPlayer.GetPosition();
            ringObservers.Insert(observerPoint);
            float observerGap = vector.Distance(observerPoint, original);
            if (nearestGap < 0 || observerGap < nearestGap) { centre = observerPoint; nearestGap = observerGap; }
        }
        if (ringObservers.Count() == 0) { return "spawn_ring_search_unavailable"; }
        if (!HCServer.HCTickWork().HCTake(m_RingCandidates)) { return "spawn_ring_work_pending"; }
        HCPerceptionRingPick pick = HCPerceptionRing.HCFindLand(centre, m_RingDegrees, ringObservers, m_RingCandidates);
        if (pick.Reason != "") { return pick.Reason; }
        HCServer.HCTickWork().HCCharge(1);
        string ringProblem = this.HCRingPickProblem(pick, centre, ringObservers, original);
        if (ringProblem != "")
        {
            // Step past the refused candidate (half a slot interleaves the next pass).
            m_RingDegrees = m_RingDegrees + 360.0 * (pick.Attempts + 0.5) / m_RingCandidates;
            while (m_RingDegrees >= 360.0) { m_RingDegrees = m_RingDegrees - 360.0; }
            return ringProblem;
        }
        patrol.m_Position = m_RingGround;
        return "";
    }

    protected vector m_RingGround;

    protected string HCRingPickProblem(HCPerceptionRingPick pick, vector centre, array<vector> ringObservers, vector original)
    {
        vector ground = this.GroundSample(pick.Position, HCPerceptionRing.HCGet().SpawnMarginMeters);
        if (ground == vector.Zero || !HCPerceptionRing.HCClearOfObservers(ground, ringObservers)) { return "spawn_ring_ground_unavailable"; }
        if (vector.Distance(ground, centre) > HCPerceptionRing.HCSpawnMax()) { return "spawn_ring_ground_outside_band"; }
        string routeProblem = this.HCRingRouteProblem(ground, original);
        if (routeProblem != "") { return routeProblem; }
        string observerProblem = this.MemberProblemFor(ground);
        if (observerProblem != "") { return observerProblem; }
        // No actor exists here. Provider owns the eventual fresh spawn.
        m_RingGround = ground;
        return "";
    }

    protected string HCRingRouteProblem(vector start, vector target)
    {
        AIWorld ringWorld = GetGame().GetWorld().GetAIWorld();
        if (!ringWorld) { return "spawn_ring_navmesh_unavailable"; }
        TVectorArray ringPath = new TVectorArray();
        HCServer.HCTickWork().HCCharge(1);
        if (!ringWorld.FindPath(start, target, m_Filter, ringPath) || ringPath.Count() < 2) { return "spawn_ring_route_unreachable"; }
        // Constant work after the single native query. A connector must reach
        // the exact already-qualified anchor; partial endpoints never authorize
        // a new spawn. Route qualification retains its separate detour checks.
        if (ringPath[ringPath.Count() - 1] != target) { return "spawn_ring_route_incomplete"; }
        return "";
    }
    string SpawnProblemFor(HCXAISitePatrol patrol)
    {
        if (!m_Policy || m_Phase != "run") { return "sites not running"; }
        if (patrol.m_HCFinished) { return "transient site completed"; }
        if (!m_OwnedSaved) { return "raid ownership save pending"; }
        foreach (HCXAISiteState raidState : m_States)
        {
            if (raidState.Patrol != patrol || raidState.Transient) { continue; }
            if (this.RaidLocked(raidState.Site, ExpansionStatic.GetTimestamp(true))) { return "raided site lockout"; }
            // Population is fixed from AILimits.WorldSeed + site ID at Create.
        }
        string providerIssue = HCXAIQualification.ProviderProblem();
        if (providerIssue != "") { return providerIssue; }
        string sharedBudget = this.BudgetProblem(patrol.m_HCGroupMax, patrol);
        if (sharedBudget != "") { return sharedBudget; }
        int activeSites = 0;
        int activeAI = 0;
        foreach (HCXAISiteState state : m_States)
        {
            if (state.Completed || !state.Patrol || state.Patrol == patrol || !state.Patrol.m_Group) { continue; }
            if (state.Patrol.m_Group.Count() == 0 && state.Patrol.m_HCPendingMembers <= 0) { continue; }
            activeSites++;
            activeAI = activeAI + state.Patrol.m_NumberOfAI;
        }
        if (activeSites >= HCAILimits.Get().MaxLiveGroups || activeAI + patrol.m_HCGroupMax > HCAILimits.Get().MaxLiveAI) { return "global AI budget reached"; }
        return HCXAISiteRules.SpawnProblem(m_Policy, activeAI, activeSites, patrol.m_HCGroupMax, this.NearestPlayer(patrol.m_Position), this.SeenByPlayer(patrol.m_Position));
    }
    string MemberProblemFor(vector pos)
    {
        if (!m_Policy || m_Phase != "run") { return "sites not running"; }
        string memberIssue = HCXAIQualification.ProviderProblem();
        if (memberIssue != "") { return memberIssue; }
        return HCXAISiteRules.MemberSpawnProblem(m_Policy, this.NearestPlayer(pos), this.SeenByPlayer(pos));
    }
    // Reuse the same population list for scaling, spawn safety and caches.
    // Provider callbacks may run between director ticks; refresh at most once
    // per second, including rollback. The intended server load is 3..6 players.
    protected void HCRefreshPlayers()
    {
        int now = GetGame().GetTime();
        if (m_PlayersAt >= 0 && now >= m_PlayersAt && now - m_PlayersAt < 1000) { return; }
        m_PlayersAt = now;
        m_Players.Copy(HCPerfPlayers.HCGet()); // native EnScript.c:499 array.Copy
        if (!m_GroupScaling) { return; }
        m_OnlinePlayers = 0;
        foreach (Man connected : m_Players)
        {
            // Connected dead/unconscious players still count; provider actors
            // have no identity and must never amplify their own group sizes.
            if (connected && connected.GetIdentity()) { m_OnlinePlayers++; }
        }
    }
    protected void HCRefreshGroupFactor()
    {
        if (!m_GroupScaling) { return; }
        this.HCRefreshPlayers();
        if (m_ScalePlayers == m_OnlinePlayers) { return; }
        m_ScalePlayers = m_OnlinePlayers;
        m_GroupFactor = HCXAISiteRules.HCGroupFactor(m_OnlinePlayers);
        Print("[HC Expansion AI] group scale players=" + m_OnlinePlayers.ToString() + " factor=" + m_GroupFactor.ToString());
    }
    float NearestPlayer(vector pos)
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
    // Native ray from each live player's eye to a standing chest height at pos.
    bool SeenByPlayer(vector pos)
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
    void Spawned(HCXAISitePatrol patrol)
    {
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
        this.SaveOwned();
    }
    void Despawned(HCXAISitePatrol patrol, bool intact)
    {
        foreach (HCXAISiteState endedState : m_States)
        {
            if (endedState.Transient && endedState.Patrol == patrol) { this.FinishTransient(endedState, true, patrol.m_HCSurvivors); }
        }
        Print("[HC Expansion AI] site " + patrol.m_HCSiteId + " despawned (intact=" + intact.ToString() + ")");
        this.SaveOwned();
    }
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
    protected void HCStepRespawns()
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
    // SpawnAI is private (eAIDynamicPatrol.c:376); deferred spawning at :681
    // uses the live formation, which cannot satisfy an independent spawn ring.
    // Retire an unseen depleted group, then use native fresh-group Spawn/loadout.
    // Work is bounded by the already reserved group size (AILimits ceiling).
    void HCRefreshDepleted(HCXAISitePatrol patrol)
    {
        if (!m_Policy || m_Phase != "run" || !m_OwnedSaved || patrol.m_HCTransient || !patrol.m_Group || patrol.m_HCPendingMembers > 0) { return; }
        if (m_RespawnOff) { return; }
        int surviving = patrol.m_Group.Count();
        // A wiped native group can retain its last combat flag: there is no
        // living actor whose combat needs protecting or can clear that flag.
        if (surviving >= patrol.m_NumberOfAI || (surviving > 0 && patrol.m_Group.IsInCombat())) { return; }
        HCXAIOwnedRow deathRow = this.OwnershipRow(patrol.m_HCSiteId);
        if (!deathRow || deathRow.ClearedAt <= 0) { return; }
        int now = ExpansionStatic.GetTimestamp(true);
        array<ref HCXAISiteState> freshStates = m_States;
        foreach (HCXAISiteState freshState : freshStates)
        {
            if (freshState.Patrol != patrol) { continue; }
            if (now < deathRow.ClearedAt || now - deathRow.ClearedAt < this.HCDeathDelay(freshState.Site, deathRow)) { return; }
            int liveIndex = 0;
            while (liveIndex < patrol.m_Group.Count())
            {
                DayZPlayerImplement liveMember = patrol.m_Group.GetMember(liveIndex);
                if (liveMember && this.MemberProblemFor(liveMember.GetPosition()) != "") { return; }
                liveIndex++;
            }
            patrol.Despawn();
            // The durable death epoch has already served the delay. Avoid a
            // second native timer after safe retirement. CanSpawn still checks
            // journal, budget, provider, ring and visibility on every attempt.
            if (!patrol.m_Group) { patrol.m_TimeSinceLastSpawn = patrol.m_RespawnTime; }
            return;
        }
    }
    bool RaidLocked(HCXAISite site, int now)
    {
        if (!m_Owned || now <= 0) { return true; }
        foreach (HCXAIOwnedRow raidRow : m_Owned.Rows)
        {
            if (raidRow.SiteId != site.Id || raidRow.ClearedAt == 0) { continue; }
            if (now < raidRow.ClearedAt) { return true; }
            if (m_RespawnOff) { return true; }
            return now - raidRow.ClearedAt < this.HCDeathDelay(site, raidRow);
        }
        return false;
    }
    protected HCXAIOwnedRow OwnershipRow(string siteId)
    {
        foreach (HCXAIOwnedRow candidateRow : m_Owned.Rows)
        {
            if (candidateRow.SiteId == siteId) { return candidateRow; }
        }
        if (m_Owned.Rows.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { return null; }
        HCXAIOwnedRow createdRow = new HCXAIOwnedRow();
        createdRow.SiteId = siteId;
        m_Owned.Rows.Insert(createdRow);
        return createdRow;
    }
    // Called before native death cleanup, while the killed actor still has its
    // group. Partial raids also lock out replacement bodies across a restart.
    void RecordDeath(eAIGroup killedGroup)
    {
        if (!killedGroup) { return; }
        foreach (HCXAISiteState killedState : m_States)
        {
            if (killedState.Transient || !killedState.Patrol) { continue; }
            if (killedState.Patrol.m_Group == killedGroup)
            {
                this.RecordCleared(killedState.Patrol, true);
                return;
            }
        }
    }
    void RecordCleared(HCXAISitePatrol patrol, bool death = false)
    {
        if (!m_Owned || patrol.m_HCTransient) { return; }
        HCXAIOwnedRow clearedRow = this.OwnershipRow(patrol.m_HCSiteId);
        if (!clearedRow) { m_OwnedSaved = false; return; }
        // Despawn must never restart the death timer. A new kill updates the
        // epoch; callback runs before native death cleanup (HCXStance).
        if (!death && clearedRow.ClearedAt > 0) { return; }
        clearedRow.ClearedAt = ExpansionStatic.GetTimestamp(true);
        clearedRow.PartialRaid = death && patrol.m_Group && patrol.m_Group.Count() > 1;
        this.SaveOwned();
        Print("[HC Expansion AI] site " + patrol.m_HCSiteId + " cleared-at=" + clearedRow.ClearedAt.ToString() + " saved=" + m_OwnedSaved.ToString());
    }
    // One holdout cache per tick: seed once per lifecycle, adopt after a crash,
    // mark looted when empty or gone, refill only after the cooldown.
    protected void StepCache()
    {
        int count = m_States.Count();
        int tries = 0;
        while (tries < count)
        {
            HCXAISiteState state = m_States[m_CacheCursor % count];
            m_CacheCursor++;
            tries++;
            if (state.Site.Kind != "holdout" || !state.Patrol || !state.HouseObject) { continue; }
            this.CacheStep(state);
            return;
        }
    }
    protected void CacheStep(HCXAISiteState state)
    {
        HCXAISite site = state.Site;
        EntityAI crate = this.FindCrate(state);
        int items = 0;
        if (crate && crate.GetInventory() && crate.GetInventory().GetCargo()) { items = crate.GetInventory().GetCargo().GetItemCount(); }
        bool playerNear = false;
        this.HCRefreshPlayers();
        foreach (Man player : m_Players)
        {
            if (!player || !player.GetIdentity()) { continue; }
            if (vector.DistanceSq(player.GetPosition(), state.CacheWorld) < m_Policy.CacheClearRadius * m_Policy.CacheClearRadius) { playerNear = true; break; }
        }
        HCXAICacheRow row = this.CacheRow(site.Id);
        int now = ExpansionStatic.GetTimestamp(true);
        bool present = false;
        if (crate) { present = true; }
        string action = HCXAISiteRules.CacheAction(row, present, items, now, playerNear);
        if (action == "seed" || action == "refill")
        {
            if (!m_OwnedSaved || this.RaidLocked(site, now)) { return; }
            // Migrate old four-hour cooldown rows as well as new policy files.
            if (row && row.LootedAt > 0 && now - row.LootedAt < 604800) { return; }
            this.SeedCache(state, row, now, crate);
            return;
        }
        if (action == "adopt")
        {
            row.State = "seeded";
            this.SaveCaches();
            Print("[HC Expansion AI] site " + site.Id + " cache adopted after an interrupted seed (no new items)");
            return;
        }
        if (action == "mark-looted")
        {
            row.State = "looted";
            row.LootedAt = now;
            int cacheCooldown = site.CacheCooldownSeconds;
            if (cacheCooldown < 604800) { cacheCooldown = 604800; }
            row.NextRefillAt = HCXAISiteRules.RefillAt(now, cacheCooldown);
            this.SaveCaches();
            Print("[HC Expansion AI] site " + site.Id + " cache looted or gone; refill not before " + row.NextRefillAt.ToString());
            return;
        }
        if (action == "refuse") { Print("[HC Expansion AI] site " + site.Id + " cache journal row in unknown state " + row.State); }
    }
    protected EntityAI FindCrate(HCXAISiteState state)
    {
        array<Object> objects = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition(state.CacheWorld, 1.5, objects, cargos);
        foreach (Object candidate : objects)
        {
            if (candidate && candidate.GetType() == state.Site.CacheClass) { return EntityAI.Cast(candidate); }
        }
        return null;
    }
    protected HCXAICacheRow CacheRow(string siteId)
    {
        foreach (HCXAICacheRow row : m_Caches.Rows)
        {
            if (row.SiteId == siteId) { return row; }
        }
        return null;
    }
    void SeedCache(HCXAISiteState state, HCXAICacheRow row, int now, EntityAI crate)
    {
        HCXAISite site = state.Site;
        if (!row)
        {
            if (m_Caches.Rows.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { return; }
            HCXAICacheRow newRow = new HCXAICacheRow();
            newRow.SiteId = site.Id;
            m_Caches.Rows.Insert(newRow);
            row = newRow;
        }
        row.ClassName = site.CacheClass;
        row.State = "seeding";
        row.Lifecycle = row.Lifecycle + 1;
        row.SeededAt = now;
        row.LootedAt = 0;
        row.NextRefillAt = 0;
        // Intent is durable before any item exists: a crash from here on can
        // only adopt or mark the cache looted, never seed it twice.
        if (!this.SaveCaches())
        {
            Print("[HC Expansion AI] site " + site.Id + " cache intent not saved; nothing created");
            return;
        }
        if (!crate)
        {
            crate = EntityAI.Cast(GetGame().CreateObjectEx(site.CacheClass, state.CacheWorld, ECE_SETUP | ECE_CREATEPHYSICS | ECE_KEEPHEIGHT | ECE_UPDATEPATHGRAPH | ECE_NOLIFETIME));
            if (crate) { crate.SetOrientation(state.CacheOrientation); }
        }
        if (!crate || !crate.GetInventory())
        {
            Print("[HC Expansion AI] site " + site.Id + " cache container could not be created; left as seeding");
            return;
        }
        int created = 0;
        foreach (HCXAISiteLoot loot : site.CacheLoot)
        {
            int made = 0;
            while (made < loot.Quantity)
            {
                EntityAI item = crate.GetInventory().CreateEntityInCargo(loot.ClassName);
                made++;
                if (!item) { continue; }
                created++;
                Magazine ammo = Magazine.Cast(item);
                if (ammo) { ammo.ServerSetAmmoCount(ammo.GetAmmoMax() / 2); }
            }
        }
        row.State = "seeded";
        this.SaveCaches();
        vector at = state.CacheWorld;
        Print("[HC Expansion AI] site " + site.Id + " cache " + site.CacheClass + " seeded lifecycle " + row.Lifecycle.ToString() + " with " + created.ToString() + " items at " + at.ToString());
    }
    bool SaveCaches()
    {
        if (!m_Caches || m_Caches.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return false; }
        string error;
        MakeDirectory("$profile:HollowCountry");
        return JsonFileLoader<HCXAICacheJournal>.SaveFile(HCXAISiteDirector.CACHES, m_Caches, error);
    }
    // Dirty mark only: the scheduler job (or the Stop flush) performs the write.
    void HCRoutesChanged()
    {
        if (m_RouteSave) { m_RouteSave.HCDirty = true; return; }
        this.SaveRoutes();
    }
    bool SaveRoutes()
    {
        if (!m_Routes || m_Routes.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return false; }
        string error;
        MakeDirectory("$profile:HollowCountry");
        return JsonFileLoader<HCXAIRouteCache>.SaveFile(HCXAISiteDirector.ROUTES, m_Routes, error);
    }
    bool SaveOwned()
    {
        if (!m_Owned) { return false; }
        foreach (HCXAIOwnedRow resetRow : m_Owned.Rows)
        {
            resetRow.Members = 0;
        }
        foreach (HCXAISiteState state : m_States)
        {
            if (state.Transient) { continue; }
            if (!state.Patrol || !state.Patrol.m_Group) { continue; }
            HCXAIOwnedRow ownedRow = this.OwnershipRow(state.Site.Id);
            if (!ownedRow) { m_OwnedSaved = false; return false; }
            ownedRow.Members = state.Patrol.m_Group.Count();
        }
        string error;
        MakeDirectory("$profile:HollowCountry");
        // Shared verified intent/backup/copy store: an interrupted promotion
        // quarantines the epoch rather than silently resetting a raid timer.
        m_OwnedSaved = HCV2ThreatStore<HCXAIOwnership>.Save(HCXAISiteDirector.OWNED, m_Owned, HCWorldStore.MAX_BYTES);
        if (!m_OwnedSaved) { Print("[HC Expansion AI] ownership save refused: " + error + "; new spawns and cache seeds held"); }
        return m_OwnedSaved;
    }
    static string ReadBounded(string path)
    {
        if (!FileExist(path)) { return ""; }
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return ""; }
        string data;
        int count = ReadFile(handle, data, 65537);
        CloseFile(handle);
        if (count < 1 || count > 65536) { return ""; }
        return data;
    }
    static HCXAISitePolicy LoadPolicy()
    {
        string data = HCWorldStore.Read(HCXAISiteDirector.POLICY);
        if (data == "") { return null; }
        string error;
        HCXAISitePolicy policy;
        if (!JsonFileLoader<HCXAISitePolicy>.LoadData(data, policy, error) || !policy) { return null; }
        // JsonFileLoader zero-fills absent scalars. Missing respawn policy
        // gets the short defaults; explicit zero intentionally inherits sites.
        if (!HCJsonFields.Has(data, "AIRespawnSeconds")) { policy.AIRespawnSeconds = 900; }
        if (!HCJsonFields.Has(data, "MemberReplaceSeconds")) { policy.MemberReplaceSeconds = 600; }
        // Legacy JSON fields are retained for old profiles, with one authority.
        policy.MaxActiveAI = HCAILimits.Get().MaxActiveAI;
        policy.MaxActiveSites = HCAILimits.Get().MaxActiveSites;
        return policy;
    }
    static HCXAIRouteCache LoadRoutes()
    {
        if (!FileExist(HCXAISiteDirector.ROUTES)) { return new HCXAIRouteCache(); }
        string data = HCWorldStore.Read(HCXAISiteDirector.ROUTES);
        if (data == "") { return null; }
        string error;
        HCXAIRouteCache routes;
        if (!JsonFileLoader<HCXAIRouteCache>.LoadData(data, routes, error) || !routes || routes.SchemaVersion != 1 || !routes.Rows || routes.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return null; }
        return routes;
    }
    static HCXAICacheJournal LoadCaches()
    {
        if (!FileExist(HCXAISiteDirector.CACHES)) { return new HCXAICacheJournal(); }
        string data = HCWorldStore.Read(HCXAISiteDirector.CACHES);
        if (data == "") { return null; }
        string error;
        HCXAICacheJournal caches;
        if (!JsonFileLoader<HCXAICacheJournal>.LoadData(data, caches, error) || !caches || caches.SchemaVersion != 1 || !caches.Rows || caches.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return null; }
        return caches;
    }
    static HCXAIOwnership LoadOwned()
    {
        if (!HCV2ThreatStore<HCXAIOwnership>.CanOpen(HCXAISiteDirector.OWNED)) { return null; }
        if (!FileExist(HCXAISiteDirector.OWNED)) { return new HCXAIOwnership(); }
        string data = HCWorldStore.Read(HCXAISiteDirector.OWNED);
        if (data == "") { return null; }
        string error;
        HCXAIOwnership journal;
        if (!JsonFileLoader<HCXAIOwnership>.LoadData(data, journal, error) || !journal || journal.SchemaVersion != 1 || !journal.Rows || journal.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return null; }
        foreach (HCXAIOwnedRow checkedRow : journal.Rows)
        {
            if (!checkedRow || checkedRow.ClearedAt < 0 || checkedRow.Members < 0) { return null; }
        }
        return journal;
    }
}
// LC-T410 / EXP-L1 fallback: one empty roadside table at each reviewed entry.
// Installed vanilla structures_military.pbo/config.bin CfgVehicles Land_Roadblock_Table;
// native scripts-1.30.164289/3_Game/Global/Game.c:703 CreateObjectEx, :945 GetPlayers,
// :923 GetObjectsAtPosition, :1176 SurfaceY; existing director NearestPlayer/SeenByPlayer supplies observer
// checks using 3_Game/Global/DayZPhysics.c:199 RaycastRV.
// Installed structures_military.pbo!config.bin CfgVehicles:
// Land_Roadblock_Table scope=1; Land_Roadblock_Table_DE inherits it, scope=2.
// Static config evidence only: factory/collision/path acceptance remains pending.
// Source review is a candidate placement; native path and client checks pending.
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
    // Start runs once per stance start, so every refusal logs once.
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
        // House includes walls and wrecks. Keep a conservative near-field veto
        // at 8 m rather than rejecting every roadside structure within 25 m.
        GetGame().GetObjectsAtPosition(at, 8, objects, cargos);
        if (objects.Count() > 128)
        {
            this.HCRetry(row, "nearby objects exceed cap=128 radius=8m");
            return;
        }
        foreach (Object candidate : objects)
        {
            // Adopt either generation before the House veto, regardless of
            // query order; never duplicate scenery on a restart.
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
        row.Table = GetGame().CreateObjectEx("Land_Roadblock_Table_DE", at, ECE_SETUP | ECE_KEEPHEIGHT | ECE_NOLIFETIME);
        if (!row.Table) { this.HCRetry(row, "native factory"); return; }
        row.Finished = true;
        Print("[HollowCountry] Checkpoints props present: " + row.Site.Id + "; empty roadside table remains if guards unavailable");
    }
}
