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
class HCXAICaravanRoadNode
{
    vector Position;
    ref array<int> Links = new array<int>;
    // Native EnScript.c:902/917 map Set/Contains; built once with Links.
    ref map<int, bool> LinkIds = new map<int, bool>;
    int Parent = -2;
}
class HCXAICaravanRoads
{
    protected static ref HCXAICaravanRoads s_Instance;
    ref HCCaravanCorridor Config;
    ref array<ref HCXAICaravanRoadNode> Nodes = new array<ref HCXAICaravanRoadNode>;
    ref array<int> Frontier = new array<int>;
    ref array<vector> Path = new array<vector>;
    string Phase = "cold";
    string Reason;
    FileHandle m_File;
    // FileHandle is typedef int[]: it compares with 0 but cannot be assigned 0.
    bool m_FileOpen;
    int m_Count;
    int m_Scan;
    int m_Head;
    int m_Start = -1;
    int m_End = -1;
    float m_StartGap;
    float m_EndGap;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    // Loading retains one line cursor and yields through the shared deadline.
    protected ref HCXAICaravanRoadNode m_LoadNode;
    protected int m_LoadField;
    protected int m_LoadDegree;
    protected int m_LoadEdge;
    protected int m_LoadFrame = -1;
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
    void HCLoadFrame(float timeslice)
    {
        if (Phase == "loading") { HCStep(true); }
    }
    void HCStopLoading()
    {
        if (GetGame()) { GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCLoadFrame); }
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
        GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(HCLoadFrame);
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
    bool HCPlan(vector origin, vector destination)
    {
        if (Phase == "cold" || Phase == "loading" || Phase == "failed") { return false; }
        From = origin; To = destination;
        m_Scan = 0; m_Head = 0; m_Start = -1; m_End = -1;
        m_StartGap = Config.MaxApproachMeters * Config.MaxApproachMeters;
        m_EndGap = m_StartGap;
        Frontier.Clear(); Path.Clear(); m_Length = 0;
        Phase = "nearest";
        return true;
    }
    void HCNearest()
    {
        if (m_Scan < Nodes.Count())
        {
            HCXAICaravanRoadNode node = Nodes[m_Scan];
            node.Parent = -2;
            float fromGap = vector.DistanceSq(From, node.Position);
            float toGap = vector.DistanceSq(To, node.Position);
            if (fromGap <= m_StartGap) { m_Start = m_Scan; m_StartGap = fromGap; }
            if (toGap <= m_EndGap) { m_End = m_Scan; m_EndGap = toGap; }
            m_Scan++;
            return;
        }
        if (m_Start < 0 || m_End < 0) { Phase = "idle"; Reason = "CARAVAN_CAMP_ROAD_APPROACH_TOO_FAR"; return; }
        Nodes[m_Start].Parent = -1;
        Frontier.Insert(m_Start);
        Phase = "search";
    }
    void HCSearch()
    {
        if (m_Head >= Frontier.Count()) { Phase = "idle"; Reason = "CARAVAN_ROAD_DISCONNECTED"; return; }
        int current = Frontier[m_Head];
        m_Head++;
        if (current == m_End) { m_Scan = current; Phase = "reconstruct"; return; }
        array<int> links = Nodes[current].Links;
        foreach (int adjacent : links)
        {
            HCXAICaravanRoadNode nextNode = Nodes[adjacent];
            if (nextNode.Parent != -2) { continue; }
            nextNode.Parent = current;
            Frontier.Insert(adjacent);
        }
    }
    void HCStep(bool loadFrame = false)
    {
        if (Phase == "idle" || Phase == "ready" || Phase == "failed") { return; }
        if (Phase == "loading" && !loadFrame) { return; }
        if (Phase == "loading" && m_LoadFrame == GetGame().GetTime()) { return; }
        // One ROADS admission per visit; frame loading uses the shared idle
        // admission outside core ticks. HCWorkBudget bounds elapsed work. Taking TRADE per 8 nodes after AITrade held the graph at 8 nodes per tick (099).
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_ROADS, 1)) { return; }
        bool loading = Phase == "loading";
        int limit = Config.RoadWorkPerTick;
        if (loading)
        {
            // Only the native frame callback pumps loading. Catalog/caravan
            // visits cannot add a second slice or impose their slow cadence.
            m_LoadFrame = GetGame().GetTime();
            limit = Math.Min(limit * 64, 32768);
        }
        int began = TickCount(0);
        // Reserve headroom below the 8 ms target; native calls are cooperative.
        if (loading) { m_Work.HCReset(limit, Math.Min(HCPerfConfig.HCGet().SliceMs, 4)); }
        else { m_Work.HCReset(limit); }
        int unit = 0;
        for (unit = 0; unit < limit; unit++)
        {
            if (!m_Work.HCContinue()) { break; }
            if (Phase == "loading") { HCLoadNode(); }
            else if (Phase == "nearest") { HCNearest(); }
            else if (Phase == "search") { HCSearch(); }
            else if (Phase == "reconstruct")
            {
                if (m_Scan < 0) { Phase = "ready"; return; }
                if (Path.Count() >= Config.MaxRouteNodes) { Phase = "idle"; Reason = "CARAVAN_ROUTE_NODE_CAP"; return; }
                vector routePoint = Nodes[m_Scan].Position;
                if (Path.Count() == 0) { m_Length = vector.Distance(To, routePoint); }
                else { m_Length += vector.Distance(Path[Path.Count() - 1], routePoint); }
                if (Nodes[m_Scan].Parent < 0) { m_Length += vector.Distance(From, routePoint); }
                if (m_Length > Config.MaxJourneyMeters) { Phase = "idle"; Reason = "CARAVAN_ROUTE_LENGTH_CAP"; return; }
                Path.Insert(routePoint);
                m_Scan = Nodes[m_Scan].Parent;
            }
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
        return "";
    }
    override string HCRefusal() { return "CARAVAN_WAITING_FUNDED_ROAD_PAIR"; }

    // Same qualified existing group; never CreateGroup/CreateObject/teleport.
    bool HCPrepare(string lease, PlayerBase carrier, vector destination)
    {
        eAIBase actor = eAIBase.Cast(carrier);
        if (!HCReady() || !actor || !HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor) || HCXExpansionBridge.HCBaseGetIdentity(actor)) { return false; }
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
        return vector.DistanceSq(LeftActor.GetPosition(), destination) <= Corridor.ArrivalRangeMeters * Corridor.ArrivalRangeMeters;
    }
    override bool HCFleeObserved(HCCaravanState row) { return m_Group && HCXExpansionBridge.HCGroupIsInCombat(m_Group); }
}

// #256: one current physical party per director visit, one bounded native
// path query. The existing provider retains spawn, caps and despawn ownership.
modded class HCXAISiteState
{
    bool HCJourneyWalking;
    vector HCJourneyEnd;
    float HCJourneyRetry;
    float HCJourneyStarted;
}

modded class HCXAISiteDirector
{
    protected int m_HCJourneyCursor;

    override protected void StepTransients()
    {
        super.StepTransients();
        if (m_States.Count() == 0 || !HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_CARAVAN, HCUnitBudget.HC_WORK_ROADS, 1)) { return; }
        m_HCJourneyCursor = m_HCJourneyCursor % m_States.Count();
        HCXAISiteState state = m_States[m_HCJourneyCursor];
        m_HCJourneyCursor++;
        if (!state || !state.Transient || !state.Materialized || state.Completed || !state.Patrol || !state.Patrol.m_Group) { return; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
        HCWorldModule world = HCWorldModule.Get();
        vector destination;
        if (!identity || !world || !world.HCJourneyTarget(identity.HCPartyId(), destination)) { return; }
        eAIGroup party = state.Patrol.m_Group;
        if (HCXExpansionBridge.HCGroupCount(party) < 1 || state.Patrol.m_HCPendingMembers > 0) { return; }
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (HCW38SituationRuntime.HCUsed(state.ProposalId) || HCAITrade.HCJourneyBusy(state.ProposalId)) { return; }
        if (adapter && adapter.HCJourneyBusy(state.ProposalId)) { return; }
        DayZPlayerImplement leader = HCXExpansionBridge.HCGroupGetFormationLeader(party);
        if (!leader || !leader.IsAlive()) { return; }
        vector position = leader.GetPosition();
        world.HCJourneyObserved(identity.HCPartyId(), position);
        if (HCXExpansionBridge.HCGroupIsInCombat(party)) { state.HCJourneyWalking = false; return; }
        // Installed eAIDynamicPatrol.c:760-765 measures despawn distance
        // from the formation leader, so visible travelling parties stay live.
        float now = GetGame().GetTickTime();
        if (state.HCJourneyWalking && vector.DistanceSq(position, state.HCJourneyEnd) > 64 && now - state.HCJourneyStarted < 90) { return; }
        if (now < state.HCJourneyRetry) { return; }
        state.HCJourneyRetry = now + 15;
        state.HCJourneyWalking = false;
        if (!world.HCJourneyTarget(identity.HCPartyId(), destination)) { return; }
        vector direction = destination - position;
        direction[1] = 0;
        float distance = direction.Length();
        if (distance <= 8) { return; }
        direction.Normalize();
        vector wanted = position + direction * Math.Min(100, distance);
        wanted[1] = GetGame().SurfaceY(wanted[0], wanted[2]);
        vector sampled = this.NavSample(wanted, 12, m_Filter);
        if (sampled == vector.Zero) { return; }
        TVectorArray path = new TVectorArray;
        AIWorld navigation = GetGame().GetWorld().GetAIWorld();
        if (!navigation || !navigation.FindPath(position, sampled, m_Filter, path)) { return; }
        if (path.Count() < 2 || path.Count() > 32 || vector.DistanceSq(path[path.Count() - 1], sampled) > 4) { return; }
        float length = 0;
        for (int index = 1; index < path.Count(); index++) { length += vector.Distance(path[index - 1], path[index]); }
        if (length > 240) { return; }
        HCXExpansionBridge.HCGroupClearWaypoints(party);
        // ONCE walks the whole navmesh path; HALT would stop at path[0].
        HCXExpansionBridge.HCGroupSetWaypointBehaviour(party, eAIWaypointBehavior.ONCE);
        foreach (vector point : path) { HCXExpansionBridge.HCGroupAddWaypoint(party, point); }
        state.HCJourneyEnd = sampled;
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
