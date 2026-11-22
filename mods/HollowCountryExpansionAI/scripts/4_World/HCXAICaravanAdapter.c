// #145 original integration; no Expansion source/data copied or repackaged.
// Installed Expansion xref (read only):
// ai/4_World/DayZExpansion_AI/Classes/eAIGroup.c:213 AddWaypoint, :241
// ClearWaypoints, :251 SetWaypointBehaviour, :1123 IsInCombat, :1139
// GetMember, :1185 Count; Entities/DayZPlayerImplement.c:234 GetGroup.
// Roads/eAIRoadNetwork.c:678-730 and eAIRoadNode.c:281-319 document the
// installed version-4 road-file format. Its FindPath at :805 is a NO-OP and
// ExpansionWorld.c:30 does not initialise the network. We therefore read the
// provider's installed data incrementally; never call that stub or redistribute
// the data. Own BFS retains cursors, caps degrees/nodes/path and charges work.
// Native scripts-1.30.164289: EnSystem.c:417/443/501 OpenFile/CloseFile/FGets;
// EnString.c:199/20/59 Length/ToInt/ToVector; Global/Game.c:1120 IsServer;
// Object.c:287 GetPosition; EnConvert.c:210/196 DistanceSq/Distance; EnScript.c:380/407
// arrays Count/Insert. Inherited item/actor calls are cited by HCTradeInventory.
// Timing API inspected in scripts-1.30.164289: EnSystem.c:106 TickCount;
// 3_Game/Global/Game.c:914 GetTickTime, :1535 GetTime.
// All walking/geometry/arrival/loot/replication acceptance remains runtime=PENDING.
class HCXRoadVisit
{
    int Parent = -1;
    float Cost;
    float Score;
    int Heap = -1;
    bool Closed;
}

// One candidate per step; only the nine cells around the query are visited.
class HCXRoadNearest
{
    vector Position;
    float Gap;
    int Best = -1;
    int Cell;
    int Offset;

    void HCStart(vector position, float radius)
    {
        Position = position;
        Gap = radius * radius;
        Best = -1;
        Cell = 0;
        Offset = 0;
    }

    bool HCStep(HCXAICaravanRoads roads)
    {
        if (Cell >= 9) { return true; }
        int x = Math.Floor(Position[0] / HCXAICaravanRoads.HC_CELL_METERS);
        int z = Math.Floor(Position[2] / HCXAICaravanRoads.HC_CELL_METERS);
        int dx = Cell % 3 - 1;
        int dz = Cell / 3 - 1;
        array<int> bucket = roads.Grid.Get(roads.HCGridKey(x + dx, z + dz));
        if (!bucket || Offset >= bucket.Count()) { Cell++; Offset = 0; return false; }
        int node = bucket[Offset];
        Offset++;
        float gap = HCXConvoyRoute.HCFlatSq(Position, roads.Nodes[node].Position);
        if (gap <= Gap) { Gap = gap; Best = node; }
        return false;
    }
}

class HCXAICaravanRoadNode
{
    vector Position;
    ref array<int> Links = new array<int>;
    // Native EnScript.c:902/917 map Set/Contains; built once with Links.
    ref map<int, bool> LinkIds = new map<int, bool>;
}
class HCXAICaravanRoads : HCStartupOwner
{
    protected static ref HCXAICaravanRoads s_Instance;
    ref HCCaravanCorridor Config;
    ref array<ref HCXAICaravanRoadNode> Nodes = new array<ref HCXAICaravanRoadNode>;
    static const float HC_CELL_METERS = 250;
    ref map<int, ref array<int>> Grid = new map<int, ref array<int>>;
    ref HCXConvoyRoute Planner = new HCXConvoyRoute;
    ref array<vector> Path = new array<vector>;
    string Phase = "cold";
    string Reason;
    FileHandle m_File;
    // FileHandle is typedef int[]: it compares with 0 but cannot be assigned 0.
    bool m_FileOpen;
    int m_Count;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    // Loading retains one line cursor and yields through the shared deadline.
    protected ref HCXAICaravanRoadNode m_LoadNode;
    protected int m_LoadField;
    protected int m_LoadDegree;
    protected int m_LoadEdge;
    protected int m_LoadTick = -1;
    protected int m_LoadSlices;
    protected int m_LoadTicks;
    protected int m_LoadMaxTicks;
    protected float m_LoadStarted;
    float m_Length;
    vector From;
    vector To;

    static HCXAICaravanRoads HCGet() { return s_Instance; }
    static void HCOpen(HCCaravanCorridor config)
    {
        if (s_Instance || !config) { return; }
        s_Instance = new HCXAICaravanRoads;
        s_Instance.Config = config;
        s_Instance.HCLoad();
    }
    static void HCClose()
    {
        if (s_Instance) { s_Instance.HCStopLoading(); }
        if (s_Instance && s_Instance.m_FileOpen) { CloseFile(s_Instance.m_File); s_Instance.m_FileOpen = false; }
        s_Instance = null;
    }
    string HCLine()
    {
        string line;
        if (!m_FileOpen || FGets(m_File, line) <= 0 || line.Length() > 96)
        {
            HCRefuse("CARAVAN_ROAD_DATA_TRUNCATED");
            return "";
        }
        return line;
    }
    // Native Game.c:1552 / DayZGame.c:3027: SYSTEM update invokes timeslice
    // every server frame, independently of the one-second core module cadence.
    override bool HCNeedsWork() { return Phase == "loading"; }
    override void HCSlice() { this.HCLoadFrame(0); }
    void HCLoadFrame(float timeslice)
    {
        if (Phase == "loading") { HCStep(true); }
    }
    void HCStopLoading()
    {
        HCStartupPump.HCFinish(this);
    }
    void HCRefuse(string reason)
    {
        HCStopLoading();
        m_LoadNode = null;
        Phase = "failed";
        if (m_FileOpen) { CloseFile(m_File); m_FileOpen = false; }
        if (Reason == reason) { return; }
        Reason = reason;
        Print("[HC Caravan] roads=unavailable reason=" + reason + " runtime=PENDING");
    }
    void HCLoad()
    {
        m_File = OpenFile(Config.RoadDataPath, FileMode.READ);
        if (m_File == 0) { HCRefuse("CARAVAN_INSTALLED_ROAD_DATA_MISSING"); return; }
        m_FileOpen = true;
        string version = HCLine();
        string width = HCLine();
        string height = HCLine();
        string count = HCLine();
        m_Count = count.ToInt();
        if (Phase == "failed") { return; }
        if (version.ToInt() != 4 || width.ToInt() != Config.RoadMapWidth || height.ToInt() != Config.RoadMapHeight || m_Count < 1 || m_Count > Config.MaxRoadNodes)
        {
            HCRefuse("CARAVAN_ROAD_DATA_HEADER_INVALID"); return;
        }
        m_LoadStarted = GetGame().GetTickTime();
        Phase = "loading";
        HCStartupPump.HCRegister(this, "road_graph");
    }
    void HCLoadNode()
    {
        // One file line per unit, including each edge. A high-degree node can
        // no longer consume an entire slice without a shared deadline check.
        string value = HCLine();
        if (Phase == "failed") { return; }
        if (m_LoadField == 0)
        {
            if (value.ToInt() != Nodes.Count()) { HCRefuse("CARAVAN_ROAD_NODE_INVALID"); return; }
            m_LoadNode = new HCXAICaravanRoadNode;
        }
        else if (m_LoadField == 1)
        {
            m_LoadNode.Position = value.ToVector();
            if (!HCWorldLimits.Position(m_LoadNode.Position)) { HCRefuse("CARAVAN_ROAD_POSITION_INVALID"); return; }
        }
        // Field 2 is the provider's flags, as before.
        else if (m_LoadField == 3)
        {
            m_LoadDegree = value.ToInt();
            m_LoadEdge = 0;
            if (m_LoadDegree < 0 || m_LoadDegree > Config.MaxRoadDegree) { HCRefuse("CARAVAN_ROAD_NODE_INVALID"); return; }
        }
        else if (m_LoadField == 4)
        {
            int target = value.ToInt();
            if (target < 0 || target >= m_Count) { HCRefuse("CARAVAN_ROAD_LINK_INVALID"); return; }
            m_LoadNode.Links.Insert(target);
            m_LoadNode.LinkIds.Set(target, true);
            m_LoadEdge++;
        }
        if (m_LoadField < 4) { m_LoadField++; }
        if (m_LoadField == 4 && m_LoadEdge == m_LoadDegree)
        {
            // Built once inside the existing per-line loading budget.
            int x = Math.Floor(m_LoadNode.Position[0] / HC_CELL_METERS);
            int z = Math.Floor(m_LoadNode.Position[2] / HC_CELL_METERS);
            int key = HCGridKey(x, z);
            array<int> bucket = Grid.Get(key);
            if (!bucket)
            {
                bucket = new array<int>;
                Grid.Set(key, bucket);
            }
            bucket.Insert(Nodes.Count());
            Nodes.Insert(m_LoadNode);
            m_LoadNode = null;
            m_LoadField = 0;
            if (Nodes.Count() == m_Count)
            {
                CloseFile(m_File); m_FileOpen = false;
                HCStopLoading();
                Phase = "idle";
            }
        }
    }
    // World limits keep cell coordinates below 1,024; offset covers edge queries.
    int HCGridKey(int x, int z) { return (x + 1) * 1024 + z + 1; }

    HCConvoyPolicy HCWalkingPolicy()
    {
        HCConvoyPolicy policy = new HCConvoyPolicy;
        policy.RoadNodesPerTick = Config.RoadWorkPerTick;
        policy.RoadNodesPerWorkUnit = Config.RoadNodesPerWorkUnit;
        policy.MaxPlanNodes = Config.MaxRoadNodes;
        policy.MaxApproachMeters = Config.MaxApproachMeters;
        policy.MaxRouteNodes = Config.MaxRouteNodes;
        policy.MaxDriveMeters = Config.MaxJourneyMeters;
        policy.MinDriveMeters = 0;
        policy.DismountMeters = 0;
        policy.DetourMeters = Config.MaxJourneyMeters;
        return policy;
    }

    bool HCPlan(vector origin, vector destination)
    {
        if (Phase == "cold" || Phase == "loading" || Phase == "failed") { return false; }
        From = origin;
        To = destination;
        Path.Clear();
        Reason = "";
        HCConvoyPolicy policy = HCWalkingPolicy();
        if (!Planner.HCPlan(origin, destination, policy, true)) { Reason = Planner.mHCReason; return false; }
        Phase = "planning";
        return true;
    }
    void HCStep(bool loadFrame = false)
    {
        if (Phase == "idle" || Phase == "ready" || Phase == "failed") { return; }
        if (Phase == "planning")
        {
            Planner.HCStep();
            if (Planner.mHCPhase == "failed") { Phase = "idle"; Reason = Planner.mHCReason; }
            else if (Planner.mHCPhase == "ready")
            {
                // Caravan contract retains destination -> source order.
                for (int index = Planner.mHCPath.Count() - 1; index >= 0; index--) { Path.Insert(Planner.mHCPath[index]); }
                m_Length = Planner.mHCLength;
                if (m_Length > Config.MaxJourneyMeters) { Path.Clear(); Phase = "idle"; Reason = "CARAVAN_ROUTE_LENGTH_CAP"; }
                else { Phase = "ready"; }
            }
            return;
        }
        if (Phase == "loading" && !loadFrame && !Finished) { return; }
        if (Phase == "loading" && !loadFrame)
        {
            if (m_LoadTick == GetGame().GetTime()) { return; }
            m_LoadTick = GetGame().GetTime();
        }
        // One ROADS admission per visit; frame loading uses the shared idle
        // admission outside core ticks. HCWorkBudget bounds elapsed work. Taking TRADE per 8 nodes after AITrade held the graph at 8 nodes per tick (099).
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_ROADS, 1)) { return; }
        bool loading = Phase == "loading";
        int limit = Config.RoadWorkPerTick;
        if (loading)
        {
            // Shared frame pump during catch-up; one normal tick visit after
            // its deadline/opt-out. Keep the same line/unit ceiling.
            limit = Math.Min(limit * 64, 32768);
        }
        int began = TickCount(0);
        // Reserve headroom below the 8 ms target; native calls are cooperative.
        if (loading) { m_Work.HCReset(limit, HCStartupPump.HCSliceMs(Math.Min(HCPerfConfig.HCGet().SliceMs, 4))); }
        else { m_Work.HCReset(limit); }
        int unit = 0;
        for (unit = 0; unit < limit; unit++)
        {
            if (!m_Work.HCContinue()) { break; }
            if (Phase == "loading") { HCLoadNode(); }
            else { break; }
        }
        if (loading)
        {
            int ticks = TickCount(began);
            m_LoadSlices++;
            m_LoadTicks += ticks;
            if (ticks > m_LoadMaxTicks) { m_LoadMaxTicks = ticks; }
            if (Phase == "idle")
            {
                float elapsed = GetGame().GetTickTime() - m_LoadStarted;
                string line = "[HC Caravan] roads=loaded source=installed_expansion nodes=" + Nodes.Count().ToString();
                line += " slices=" + m_LoadSlices.ToString() + " elapsed_s=" + elapsed.ToString();
                line += " ticks_sum=" + m_LoadTicks.ToString() + " ticks_max=" + m_LoadMaxTicks.ToString();
                Print(line + " route_acceptance=unverified runtime=PENDING");
            }
        }
    }
}

class HCXAICaravanAdapter : HCCaravanInventory
{
    eAIGroup m_Group;
    vector m_From;
    vector m_To;
    string m_Lease;
    ref array<vector> m_Original = new array<vector>;
    int m_Behaviour;
    eAIGroup m_PartnerGroup;
    ref array<vector> m_PartnerOriginal = new array<vector>;
    int m_PartnerBehaviour;
    ref HCXAITradeAdapter m_StockReader;
    ref HCXAIStuckRecovery m_Recovery = new HCXAIStuckRecovery;

    override bool HCReady()
    {
        if (!GetGame() || !GetGame().IsServer() || !HCXAIQualification.EncountersEnabled()) { return false; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        return director && director.Phase() == "run" && roads && roads.Phase != "failed" && roads.Phase != "loading";
    }
    override string HCOperationalFault()
    {
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (roads && roads.Phase == "failed") { return roads.Reason; }
        if (m_Recovery.GivenUp) { return m_Recovery.Reason; }
        return "";
    }
    override string HCRefusal() { return "CARAVAN_WAITING_FUNDED_ROAD_PAIR"; }

    // Same qualified existing group; never CreateGroup/CreateObject/teleport.
    bool HCPrepare(string lease, PlayerBase carrier, vector destination)
    {
        eAIBase actor = eAIBase.Cast(carrier);
        if (!HCReady() || !actor || !HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor) || HCXExpansionBridge.HCBaseGetIdentity(actor)) { return false; }
        m_Recovery = new HCXAIStuckRecovery;
        m_Group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor); m_Lease = lease;
        LeftActor = actor;
        m_From = HCXExpansionBridge.HCBaseGetPosition(actor); m_To = destination;
        m_Original.Clear();
        array<vector> original = HCXExpansionBridge.HCGroupGetWaypoints(m_Group);
        if (original.Count() > Corridor.MaxRouteNodes) { return false; }
        foreach (vector point : original) { m_Original.Insert(point); }
        m_Behaviour = HCXExpansionBridge.HCGroupGetWaypointBehaviour(m_Group);
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        return roads.HCPlan(m_From, m_To);
    }
    bool HCHoldPartner(PlayerBase partner)
    {
        eAIBase actor = eAIBase.Cast(partner);
        if (!actor || !HCXExpansionBridge.HCBaseIsAlive(actor) || !HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor) || HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor) == m_Group || HCXExpansionBridge.HCGroupIsInCombat(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor))) { return false; }
        eAIGroup partnerGroup = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor);
        array<vector> waypoints = HCXExpansionBridge.HCGroupGetWaypoints(partnerGroup);
        if (waypoints.Count() > Corridor.MaxRouteNodes) { return false; }
        m_PartnerGroup = partnerGroup;
        m_PartnerOriginal.Clear();
        foreach (vector waypoint : waypoints) { m_PartnerOriginal.Insert(waypoint); }
        m_PartnerBehaviour = HCXExpansionBridge.HCGroupGetWaypointBehaviour(m_PartnerGroup);
        m_To = HCXExpansionBridge.HCBaseGetPosition(actor);
        HCXExpansionBridge.HCGroupClearWaypoints(m_PartnerGroup);
        HCXExpansionBridge.HCGroupSetWaypointBehaviour(m_PartnerGroup, eAIWaypointBehavior.HALT);
        HCXExpansionBridge.HCGroupAddWaypoint(m_PartnerGroup, m_To);
        return true;
    }
    void HCReleasePartner()
    {
        if (!m_PartnerGroup || HCXExpansionBridge.HCGroupIsInCombat(m_PartnerGroup)) { return; }
        HCXExpansionBridge.HCGroupClearWaypoints(m_PartnerGroup);
        HCXExpansionBridge.HCGroupSetWaypointBehaviour(m_PartnerGroup, m_PartnerBehaviour);
        array<vector> waypoints = m_PartnerOriginal;
        foreach (vector waypoint : waypoints) { HCXExpansionBridge.HCGroupAddWaypoint(m_PartnerGroup, waypoint); }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (director) { director.HCResetPartyJourney(m_PartnerGroup); }
        m_PartnerGroup = null;
    }

    // eAIGroup.c:222 GetWaypoints, :304 GetWaypointBehaviour. Restore the
    // existing owner's route only after real home arrival, never force position.
    bool HCRestoreRoute()
    {
        HCReleasePartner();
        if (!m_Group) { return true; }
        if (HCXExpansionBridge.HCGroupIsInCombat(m_Group)) { return false; }
        HCXExpansionBridge.HCGroupClearWaypoints(m_Group);
        HCXExpansionBridge.HCGroupSetWaypointBehaviour(m_Group, m_Behaviour);
        array<vector> original = m_Original;
        foreach (vector point : original) { HCXExpansionBridge.HCGroupAddWaypoint(m_Group, point); }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (director) { director.HCResetPartyJourney(m_Group); }
        return true;
    }
    bool HCRequest(bool returning)
    {
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (!HCReady() || !m_Group || HCXExpansionBridge.HCGroupIsInCombat(m_Group) || !roads || roads.Phase != "ready") { return false; }
        // Path is destination -> source. Installed Expansion
        // eAIState_TraversingWaypoints treats HALT as final at the CURRENT
        // waypoint, so multi-point paths use ONCE, which advances to the last
        // waypoint and stops there. No combat/speed override or forced recovery.
        HCXExpansionBridge.HCGroupClearWaypoints(m_Group);
        HCXExpansionBridge.HCGroupSetWaypointBehaviour(m_Group, eAIWaypointBehavior.ONCE);
        if (returning)
        {
            for (int back = 0; back < roads.Path.Count(); back++) { HCXExpansionBridge.HCGroupAddWaypoint(m_Group, roads.Path[back]); }
            HCXExpansionBridge.HCGroupAddWaypoint(m_Group, m_From);
        }
        else
        {
            for (int forward = 0; forward < roads.Path.Count(); forward++) { HCXExpansionBridge.HCGroupAddWaypoint(m_Group, roads.Path[roads.Path.Count() - 1 - forward]); }
            HCXExpansionBridge.HCGroupAddWaypoint(m_Group, m_To);
        }
        // Legacy in-progress journals may still request a route. Recovery stays
        // dormant until a caller owns its give-up/abort lifecycle; arrival polling
        // alone cannot complete that lifecycle after an observer gives up.
        return true;
    }
    override bool HCBindCaravan(HCCaravanState row)
    {
        HCClear();
        if (!row || !Corridor || row.LeaseId != m_Lease || !m_Group || !HCReady()) { return false; }
        if (!m_StockReader) { m_StockReader = new HCXAITradeAdapter; }
        HCTradeRecipe stockRecipe = new HCTradeRecipe;
        m_StockReader.Recipe = stockRecipe;
        ItemBase stock;
        eAIBase holder = m_StockReader.HCHolder(row.LeaseId, stockRecipe.LeftClass, stock);
        if (!holder || !stock) { return false; }
        LeftActor = holder; LeftItem = stock;
        return HCInventoryBoundCaravan(row);
    }
    override bool HCWalkCaravan(HCCaravanState row, bool returning)
    {
        return row && HCCurrentCaravan(row) && HCRequest(returning);
    }
    override bool HCAtCamp(HCCaravanState row, bool returning)
    {
        if (!row || !LeftActor || !Corridor || !HCCurrentCaravan(row)) { return false; }
        vector destination = m_To;
        if (returning) { destination = m_From; }
        bool arrived = vector.DistanceSq(LeftActor.GetPosition(), destination) <= Corridor.ArrivalRangeMeters * Corridor.ArrivalRangeMeters;
        // Trade Walker arrival polling does not call this port (deferred).
        if (!arrived) { m_Recovery.HCCheck(m_Group, LeftActor.GetPosition(), GetGame().GetTime()); }
        return arrived;
    }
    override bool HCFleeObserved(HCCaravanState row) { return m_Group && HCXExpansionBridge.HCGroupIsInCombat(m_Group); }
}

// #256: one current physical party per director visit, one bounded native
// path query. The existing provider retains spawn, caps and despawn ownership.
modded class HCXAISiteState
{
    ref HCXAIStuckRecovery HCJourneyRecovery;
    bool HCJourneyWalking;
    vector HCJourneyEnd;
    float HCJourneyRetry;
    float HCJourneyStarted;
    int HCJourneyRecoveryChecks;
    int HCJourneyRetryVisits;
    ref TVectorArray HCJourneyPath = new TVectorArray;
    vector HCJourneySampled;
    vector HCJourneySampleTarget;
    int HCJourneyPathStage;
    int HCJourneyPathFailures;

    // Failures wait at least 15/30 seconds AND skip one/two eligible visits.
    // Visit backoff still matters when the director rotation exceeds that time.
    void HCFailJourneyLeg()
    {
        HCJourneyPathStage = 0;
        HCJourneyPath.Clear();
        HCJourneyPathFailures = Math.Min(HCJourneyPathFailures + 1, 2);
        HCJourneyRetry = GetGame().GetTickTime() + 15 * HCJourneyPathFailures;
        HCJourneyRetryVisits = HCJourneyPathFailures;
    }

    void HCResetJourney()
    {
        HCStopJourney();
        HCJourneyPath.Clear();
        HCJourneyPathStage = 0;
        HCJourneyPathFailures = 0;
    }

    // Stop motion observation; callers invalidating geometry use HCResetJourney.
    void HCStopJourney()
    {
        HCXJourneyReplans.HCRelease(this);
        HCJourneyWalking = false;
        HCJourneyRecovery = null;
        HCJourneyStarted = 0;
        HCJourneyRecoveryChecks = 0;
        HCJourneyRetry = 0;
        HCJourneyRetryVisits = 0;
    }
}

// One server-wide FIFO. No planner exists while waiting; only the head gets
// one HCCheck/HCStep per core tick. Array work is bounded independently of N.
class HCXJourneyReplans
{
    static const int HC_QUEUE_CAP = 64;
    protected static ref array<ref HCXJourneyReplanTurn> s_Queue = new array<ref HCXJourneyReplanTurn>;
    protected static int s_Frame = -1;

    static void HCRelease(HCXAISiteState state)
    {
        for (int index = s_Queue.Count() - 1; index >= 0; index--)
        {
            if (s_Queue[index].State == state)
            {
                HCClearFixture(s_Queue[index]);
                s_Queue.RemoveOrdered(index);
            }
        }
    }
    // The turn owns its recovery observer, including the per-request fixture mark.
    static void HCClearFixture(HCXJourneyReplanTurn turn)
    {
        turn.Recovery.Fixture = false;
    }
    static void HCClear()
    {
        foreach (HCXJourneyReplanTurn turn : s_Queue) { HCClearFixture(turn); }
        s_Queue.Clear();
        s_Frame = -1;
    }

    static void HCQueue(HCXAISiteState state, eAIGroup group, vector destination)
    {
        foreach (HCXJourneyReplanTurn existing : s_Queue)
        {
            if (existing.State == state) { return; }
        }
        if (s_Queue.Count() >= HC_QUEUE_CAP) { state.HCJourneyRecovery.HCGiveUp("JOURNEY_REPLAN_QUEUE_CAP"); return; }
        HCXJourneyReplanTurn turn = new HCXJourneyReplanTurn;
        turn.State = state;
        turn.Recovery = state.HCJourneyRecovery;
        turn.Group = group;
        turn.Destination = destination;
        turn.Recovery.Reason = "JOURNEY_REPLAN_QUEUED";
        s_Queue.Insert(turn);
        string line = "[HC XAI] recovery=waiting party=journey reason=JOURNEY_REPLAN_QUEUED";
        if (turn.Recovery.Fixture) { line += " fixture=1"; }
        Print(line + " runtime=PENDING");
    }

    static void HCTick()
    {
        int now = GetGame().GetTime();
        if (s_Frame == now) { return; }
        s_Frame = now;
        if (s_Queue.Count() == 0) { return; }
        HCXJourneyReplanTurn turn = s_Queue[0];
        if (!turn.Active) { turn.Active = true; turn.Started = now; }
        // Even perpetual admission refusal cannot retain the active slot.
        if (now < turn.Started || now - turn.Started >= HCXConvoyRoute.HC_PLAN_TIMEOUT_MS)
        {
            turn.Recovery.HCGiveUp("JOURNEY_REPLAN_TIMEOUT");
            turn.State.HCResetJourney();
            return;
        }
        // Separate observation admission leaves HC_WORK_CONVOY_ROUTE for the
        // planner's existing per-work-unit HCTakeFor and HCWorkBudget deadline.
        if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_CARAVAN, HCUnitBudget.HC_WORK_ROADS, 2)) { return; }
        HCXAISiteState state = turn.State;
        if (!state.Transient || !state.Materialized || state.Completed || !state.Patrol || state.Patrol.m_Group != turn.Group || state.HCJourneyRecovery != turn.Recovery || !state.HCJourneyWalking || turn.Recovery.GivenUp)
        {
            state.HCResetJourney();
            return;
        }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
        HCWorldModule world = HCWorldModule.Get();
        vector destination;
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (!identity || !world || !world.HCJourneyTarget(identity.HCPartyId(), destination) || destination != turn.Destination || HCW38SituationRuntime.HCUsed(state.ProposalId) || HCAITrade.HCJourneyBusy(state.ProposalId) || (adapter && adapter.HCJourneyBusy(state.ProposalId)))
        {
            state.HCResetJourney();
            return;
        }
        DayZPlayerImplement leader = HCXExpansionBridge.HCGroupGetFormationLeader(turn.Group);
        if (!turn.Group || HCXExpansionBridge.HCGroupCount(turn.Group) < 1 || state.Patrol.m_HCPendingMembers > 0 || !leader || !leader.IsAlive() || HCXExpansionBridge.HCGroupIsInCombat(turn.Group))
        {
            state.HCResetJourney();
            return;
        }
        vector position = leader.GetPosition();
        if (vector.DistanceSq(position, state.HCJourneyEnd) <= 64) { state.HCResetJourney(); return; }
        turn.Recovery.HCCheck(turn.Group, position, now, true);
        if (turn.Recovery.GivenUp) { state.HCResetJourney(); return; }
        if (turn.Recovery.Replan) { turn.Recovery.Replan.mHCStarted = turn.Started; }
        if (!turn.Recovery.AwaitingReplan) { HCRelease(state); }
    }
}

modded class HCXAISiteDirector
{
    protected int m_HCJourneyCursor;

    void HCResetPartyJourney(eAIGroup party)
    {
        foreach (HCXAISiteState released : m_States)
        {
            if (released && released.Patrol && released.Patrol.m_Group == party) { released.HCResetJourney(); }
        }
    }

    // Despawned and the last-member-death path both finish here. Release
    // before the provider deletes the patrol or removes the director state.
    override protected void FinishTransient(HCXAISiteState state, bool materialized, int survivors)
    {
        state.HCResetJourney();
        super.FinishTransient(state, materialized, survivors);
    }

    override void Spawned(HCXAISitePatrol patrol)
    {
        foreach (HCXAISiteState fresh : m_States)
        {
            if (fresh && fresh.Patrol == patrol) { fresh.HCResetJourney(); }
        }
        super.Spawned(patrol);
    }

    // The caller admits the complete visit before observation or native work.
    // Sampling yields; FindPath uses the current leader position and shares its
    // visit with bounded validation and issue. Never cache an origin across visits.
    bool HCJourneyLeg(HCXAISiteState state, vector position, vector wanted, vector destination)
    {
        if (state.HCJourneyPathStage != 0 && state.HCJourneySampleTarget != destination)
        {
            state.HCJourneyPathStage = 0;
            state.HCJourneyPath.Clear();
        }
        if (state.HCJourneyPathStage == 0)
        {
            state.HCJourneySampleTarget = destination;
            state.HCJourneySampled = this.NavSample(wanted, 12, m_Filter);
            if (state.HCJourneySampled == vector.Zero) { state.HCFailJourneyLeg(); return false; }
            state.HCJourneyPathStage = 1;
            return false;
        }
        AIWorld navigation = GetGame().GetWorld().GetAIWorld();
        TVectorArray path = state.HCJourneyPath;
        path.Clear();
        if (!navigation || !navigation.FindPath(position, state.HCJourneySampled, m_Filter, path))
        {
            state.HCFailJourneyLeg();
            return false;
        }
        bool valid = path.Count() >= 2 && path.Count() <= 32;
        if (valid) { valid = HCXConvoyRoute.HCFlatSq(path[0], position) <= 64 && vector.DistanceSq(path[path.Count() - 1], state.HCJourneySampled) <= 4; }
        float length = 0;
        if (valid)
        {
            for (int index = 1; index < path.Count(); index++) { length += vector.Distance(path[index - 1], path[index]); }
        }
        if (valid && length <= 240) { state.HCJourneyPathStage = 0; state.HCJourneyPathFailures = 0; return true; }
        state.HCFailJourneyLeg();
        return false;
    }

    override protected void StepTransients()
    {
        super.StepTransients();
        if (m_States.Count() == 0) { return; }
        m_HCJourneyCursor = m_HCJourneyCursor % m_States.Count();
        HCXAISiteState state = m_States[m_HCJourneyCursor];
        m_HCJourneyCursor++;
        if (!state) { return; }
        if (!state.Transient || !state.Materialized || state.Completed || !state.Patrol || !state.Patrol.m_Group) { state.HCResetJourney(); return; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
        HCWorldModule world = HCWorldModule.Get();
        vector destination;
        if (!identity || !world || !world.HCJourneyTarget(identity.HCPartyId(), destination)) { state.HCResetJourney(); return; }
        eAIGroup party = state.Patrol.m_Group;
        if (HCXExpansionBridge.HCGroupCount(party) < 1 || state.Patrol.m_HCPendingMembers > 0) { state.HCResetJourney(); return; }
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (HCW38SituationRuntime.HCUsed(state.ProposalId) || HCAITrade.HCJourneyBusy(state.ProposalId)) { state.HCResetJourney(); return; }
        if (adapter && adapter.HCJourneyBusy(state.ProposalId)) { state.HCResetJourney(); return; }
        DayZPlayerImplement leader = HCXExpansionBridge.HCGroupGetFormationLeader(party);
        if (!leader || !leader.IsAlive()) { state.HCResetJourney(); return; }
        vector position = leader.GetPosition();
        float now = GetGame().GetTickTime();
        bool combat = HCXExpansionBridge.HCGroupIsInCombat(party);
        bool recoveryVisit = state.HCJourneyWalking && vector.DistanceSq(position, state.HCJourneyEnd) > 64;
        int cost = 1;
        if (!combat)
        {
            if (recoveryVisit) { cost = 2; }
            else if (state.HCJourneyRetryVisits == 0 && now >= state.HCJourneyRetry && vector.DistanceSq(position, destination) > 64) { cost = 65; }
        }
        // Exactly one take, first for this consumer: the bounded first-item
        // overshoot admits even native work under MaxTickWorkItems=32.
        if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_CARAVAN, HCUnitBudget.HC_WORK_ROADS, cost)) { return; }
        world.HCJourneyObserved(identity.HCPartyId(), position);
        if (combat) { state.HCResetJourney(); return; }
        // Installed eAIDynamicPatrol.c:760-765 measures despawn distance
        // from the formation leader, so visible travelling parties stay live.
        if (recoveryVisit)
        {
            if (state.HCJourneyRecovery)
            {
                state.HCJourneyRecovery.HCCheck(party, position, GetGame().GetTime());
                if (state.HCJourneyRecovery.AwaitingReplan) { HCXJourneyReplans.HCQueue(state, party, destination); }
                state.HCJourneyRecoveryChecks = Math.Min(state.HCJourneyRecoveryChecks + 1, 24);
            }
            bool gaveUp = state.HCJourneyRecovery && state.HCJourneyRecovery.GivenUp;
            bool refresh = state.HCJourneyRecoveryChecks >= 4 && now - state.HCJourneyStarted >= 90;
            // Preserve the ladder window after an issued rung, but only up to
            // 24 checks. Pending samples/replans cannot defeat that hard cap.
            bool ladderWindow = state.HCJourneyRecovery && state.HCJourneyRecovery.LadderStep > 0 && state.HCJourneyRecoveryChecks < 24;
            if (state.HCJourneyRecovery && (state.HCJourneyRecovery.Checks > 0 || state.HCJourneyRecovery.Replan || state.HCJourneyRecovery.AwaitingReplan || ladderWindow)) { refresh = false; }
            if (state.HCJourneyRecoveryChecks >= 24) { refresh = true; }
            if (!gaveUp && !refresh) { return; }
            // Give-up and timed refresh both discard possibly failed geometry.
            state.HCResetJourney();
            // This visit admitted recovery only; native planning gets its own visit.
            return;
        }
        if (state.HCJourneyRetryVisits > 0) { state.HCJourneyRetryVisits--; return; }
        if (now < state.HCJourneyRetry || cost != 65) { return; }
        state.HCJourneyRetry = now + 1;
        HCXJourneyReplans.HCRelease(state);
        state.HCJourneyWalking = false;
        state.HCJourneyRecovery = null;
        if (!world.HCJourneyTarget(identity.HCPartyId(), destination)) { return; }
        vector direction = destination - position;
        direction[1] = 0;
        float distance = direction.Length();
        if (distance <= 8) { return; }
        direction.Normalize();
        vector wanted = position + direction * Math.Min(100, distance);
        wanted[1] = GetGame().SurfaceY(wanted[0], wanted[2]);
        if (!HCJourneyLeg(state, position, wanted, destination)) { return; }
        TVectorArray path = state.HCJourneyPath;
        HCXExpansionBridge.HCGroupClearWaypoints(party);
        // ONCE walks the whole navmesh path; HALT would stop at path[0].
        HCXExpansionBridge.HCGroupSetWaypointBehaviour(party, eAIWaypointBehavior.ONCE);
        foreach (vector point : path) { HCXExpansionBridge.HCGroupAddWaypoint(party, point); }
        state.HCJourneyRecovery = new HCXAIStuckRecovery;
        state.HCJourneyRecovery.Kind = "journey";
        state.HCJourneyRecovery.JourneyScheduled = true;
        state.HCJourneyRecovery.HCStart(path, GetGame().GetTime(), 32);
        state.HCJourneyRecoveryChecks = 0;
        state.HCJourneyEnd = state.HCJourneySampled;
        state.HCJourneyWalking = true;
        state.HCJourneyStarted = now;
        HCReached.Mark("caravan.physical_leg");
    }
}

// HCX loads after the base materializer has added MaterializerRow.
modded class HCWorldModule
{
    override HCWorldProposal MaterializerRow(int rowIndex)
    {
        HCWorldProposal proposal = super.MaterializerRow(rowIndex);
        int index = rowIndex - HCAILimits.Get().MaxHoldouts;
        if (!proposal || index < 0 || index >= m_Data.Parties.Count()) { return proposal; }
        HCWorldParty party = m_Data.Parties[index];
        HCWorldPlace next = m_Data.Place(party.Route[(party.Edge + 1) % party.Route.Count()]);
        if (!next) { return null; }
        proposal.Position = proposal.Position + (next.Position - proposal.Position) * party.Progress;
        vector current = proposal.Position;
        current[1] = GetGame().SurfaceY(current[0], current[2]);
        proposal.Position = current;
        return proposal;
    }

}

// Higher-priority finite cargo trips retain their existing waypoint ownership.
modded class HCAITrade
{
    static bool HCJourneyBusy(string lease)
    {
        HCXAITradeAdapter port = HCXAITradeAdapter.Cast(s_Provider);
        if (!port || !port.Producer) { return false; }
        return port.Producer.m_LeftLease == lease || port.Producer.m_RightLease == lease;
    }
}

modded class HCXAIAdapter
{
    bool HCJourneyBusy(string lease)
    {
        return m_Caravan && m_Caravan.HCActive() && m_Caravan.m_State.LeaseId == lease;
    }
}
