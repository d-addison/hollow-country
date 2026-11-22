// Own road planner; no Expansion implementation or geometry redistributed.
// Native 1.30.164289: EnScript.c array/map Get/Set/Insert/Remove/Contains;
// EnMath.c Floor/Sqrt; Game.c GetTime. Road drivability remains unverified.
class HCXConvoyRoute
{
    // Fixed safety ceilings; policy work/node limits may lower them.
    static const int HC_POP_CEILING = 128;
    static const int HC_OPEN_CAP = 1024;
    static const int HC_PLAN_TIMEOUT_MS = 120000;
    protected static int s_PopFrame = -1;
    protected static int s_Pops;
    ref map<int, ref HCXRoadVisit> mHCVisits = new map<int, ref HCXRoadVisit>;
    ref array<int> mHCFrontier = new array<int>;
    ref array<vector> mHCPath = new array<vector>;
    ref HCXRoadNearest mHCNearestFrom = new HCXRoadNearest;
    ref HCXRoadNearest mHCNearestTo = new HCXRoadNearest;
    ref HCWorkBudget mHCWork = new HCWorkBudget;
    string mHCPhase = "idle";
    string mHCReason;
    string mHCTimeoutReason = "CONVOY_ROAD_BUDGET_TIMEOUT";
    string mHCOriginFailure = "CONVOY_ROAD_APPROACH_TOO_FAR";
    ref HCConvoyPolicy mHCPolicy;
    HCXAICaravanRoads mHCRoads;
    vector mHCFrom;
    vector mHCTo;
    float mHCStraight;
    float mHCLength;
    int mHCCount;
    int mHCScan;
    int mHCEnd = -1;
    int mHCExpanded;
    int mHCStarted;
    int mHCFrame = -1;
    int mHCCurrent = -1;
    int mHCEdge;
    bool mHCIncludeEnd;
    // Weak request owner: cancellation clears its mark without retaining recovery.
    HCXAIStuckRecovery mHCFixtureRecovery;

    static float HCFlatSq(vector a, vector b)
    {
        float dx = a[0] - b[0];
        float dz = a[2] - b[2];
        return dx * dx + dz * dz;
    }
    static float HCFlat(vector a, vector b) { return Math.Sqrt(HCFlatSq(a, b)); }

    bool HCFail(string reason)
    {
        mHCFixtureRecovery = null;
        mHCPhase = "failed";
        mHCReason = reason;
        return false;
    }

    bool HCPlan(vector origin, vector destination, HCConvoyPolicy policy, bool includeEnd = false, HCXAIStuckRecovery fixtureRecovery = null)
    {
        mHCFixtureRecovery = fixtureRecovery;
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (!policy) { return HCFail("CONVOY_POLICY_INVALID"); }
        if (!roads) { return HCFail("CONVOY_ROAD_NETWORK_UNAVAILABLE"); }
        if (roads.Phase == "loading" || roads.Phase == "failed" || roads.Nodes.Count() < 2) { return HCFail("CONVOY_ROAD_NETWORK_UNAVAILABLE"); }
        mHCPolicy = policy;
        mHCIncludeEnd = includeEnd;
        mHCRoads = roads;
        mHCFrom = origin;
        mHCTo = destination;
        mHCStraight = HCFlat(origin, destination);
        mHCCount = roads.Nodes.Count();
        mHCVisits.Clear();
        mHCFrontier.Clear();
        mHCPath.Clear();
        mHCExpanded = 0;
        mHCLength = 0;
        mHCCurrent = -1;
        mHCNearestFrom.HCStart(origin, policy.MaxApproachMeters);
        mHCNearestTo.HCStart(destination, policy.MaxApproachMeters);
        mHCStarted = GetGame().GetTime();
        mHCReason = "";
        mHCPhase = "scan";
        return true;
    }

    void HCSwap(int a, int b)
    {
        int held = mHCFrontier[a];
        mHCFrontier.Set(a, mHCFrontier[b]);
        mHCFrontier.Set(b, held);
        mHCVisits.Get(mHCFrontier[a]).Heap = a;
        mHCVisits.Get(mHCFrontier[b]).Heap = b;
    }
    void HCRaise(int index)
    {
        while (index > 0)
        {
            int parent = (index - 1) / 2;
            if (mHCVisits.Get(mHCFrontier[parent]).Score <= mHCVisits.Get(mHCFrontier[index]).Score) { return; }
            HCSwap(parent, index);
            index = parent;
        }
    }
    int HCPop()
    {
        int result = mHCFrontier[0];
        int last = mHCFrontier.Count() - 1;
        HCSwap(0, last);
        mHCFrontier.Remove(last);
        mHCVisits.Get(result).Heap = -1;
        int index = 0;
        while (index * 2 + 1 < mHCFrontier.Count())
        {
            int child = index * 2 + 1;
            int right = child + 1;
            if (right < mHCFrontier.Count())
            {
                if (mHCVisits.Get(mHCFrontier[right]).Score < mHCVisits.Get(mHCFrontier[child]).Score) { child = right; }
            }
            if (mHCVisits.Get(mHCFrontier[index]).Score <= mHCVisits.Get(mHCFrontier[child]).Score) { break; }
            HCSwap(index, child);
            index = child;
        }
        return result;
    }

    void HCStep()
    {
        if (mHCPhase != "scan" && mHCPhase != "search" && mHCPhase != "build") { return; }
        int now = GetGame().GetTime();
        if (now - mHCStarted > HC_PLAN_TIMEOUT_MS) { HCFail(mHCTimeoutReason); return; }
        if (mHCFrame == now) { return; }
        mHCFrame = now;
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (!roads || roads != mHCRoads) { HCFail("CONVOY_ROAD_NETWORK_CHANGED"); return; }
        if (roads.Nodes.Count() != mHCCount) { HCFail("CONVOY_ROAD_NETWORK_CHANGED"); return; }
        if (s_PopFrame != now) { s_PopFrame = now; s_Pops = 0; }
        int popLimit = Math.Min(HC_POP_CEILING, mHCPolicy.RoadNodesPerTick);
        mHCWork.HCReset(mHCPolicy.RoadNodesPerTick, HCPerfConfig.HCGet().SliceMs);
        for (int unit = 0; unit < mHCPolicy.RoadNodesPerTick; unit++)
        {
            if (!mHCWork.HCContinue()) { break; }
            if (unit % mHCPolicy.RoadNodesPerWorkUnit == 0)
            {
                if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_CONVOY_ROUTE, 1)) { break; }
            }
            if (mHCPhase == "scan") { HCScan(roads); }
            else if (mHCPhase == "search")
            {
                if (mHCCurrent < 0)
                {
                    if (s_Pops >= popLimit) { break; }
                }
                int expanded = mHCExpanded;
                HCSearch(roads.Nodes);
                if (mHCExpanded > expanded) { s_Pops++; }
            }
            else if (mHCPhase == "build") { HCBuild(roads.Nodes); }
            else { break; }
        }
        HCXAIStuckRecovery.HCObservePops(s_Pops);
    }

    void HCScan(HCXAICaravanRoads roads)
    {
        if (!mHCNearestFrom.HCStep(roads)) { return; }
        // Reject an off-road recovery before scanning the destination or starting A*.
        if (mHCNearestFrom.Best < 0) { HCFail(mHCOriginFailure); return; }
        if (!mHCNearestTo.HCStep(roads)) { return; }
        int start = mHCNearestFrom.Best;
        mHCEnd = mHCNearestTo.Best;
        if (start < 0 || mHCEnd < 0) { HCFail("CONVOY_ROAD_APPROACH_TOO_FAR"); return; }
        HCXRoadVisit visit = new HCXRoadVisit;
        visit.Score = HCFlat(roads.Nodes[start].Position, roads.Nodes[mHCEnd].Position);
        visit.Heap = 0;
        mHCVisits.Set(start, visit);
        mHCFrontier.Insert(start);
        mHCPhase = "search";
    }

    // A* with Euclidean edge cost and consistent Euclidean heuristic.
    // One edge per work step; indexed heap has no duplicate entries.
    void HCSearch(array<ref HCXAICaravanRoadNode> nodes)
    {
        if (mHCCurrent < 0)
        {
            if (mHCFrontier.Count() == 0) { HCFail("CONVOY_ROAD_DISCONNECTED"); return; }
            if (mHCExpanded >= mHCPolicy.MaxPlanNodes) { HCFail("CONVOY_ROAD_SEARCH_CAP"); return; }
            mHCCurrent = HCPop();
            mHCVisits.Get(mHCCurrent).Closed = true;
            mHCExpanded++;
            mHCEdge = 0;
            if (mHCCurrent == mHCEnd) { mHCScan = mHCCurrent; mHCPhase = "build"; return; }
        }
        array<int> links = nodes[mHCCurrent].Links;
        if (mHCEdge >= links.Count()) { mHCCurrent = -1; return; }
        int adjacent = links[mHCEdge];
        mHCEdge++;
        if (adjacent < 0 || adjacent >= nodes.Count()) { return; }
        vector candidate = nodes[adjacent].Position;
        if (HCFlat(mHCFrom, candidate) + HCFlat(candidate, mHCTo) > mHCStraight + 2 * mHCPolicy.DetourMeters) { return; }
        HCXRoadVisit next = mHCVisits.Get(adjacent);
        if (next && next.Closed) { return; }
        float cost = mHCVisits.Get(mHCCurrent).Cost + HCFlat(nodes[mHCCurrent].Position, candidate);
        if (next && cost >= next.Cost) { return; }
        if (!next)
        {
            if (mHCFrontier.Count() >= HC_OPEN_CAP) { HCFail("CONVOY_ROAD_OPEN_CAP"); return; }
            next = new HCXRoadVisit;
            next.Heap = mHCFrontier.Count();
            mHCVisits.Set(adjacent, next);
            mHCFrontier.Insert(adjacent);
        }
        next.Parent = mHCCurrent;
        next.Cost = cost;
        next.Score = cost + HCFlat(candidate, nodes[mHCEnd].Position);
        HCRaise(next.Heap);
    }

    void HCBuild(array<ref HCXAICaravanRoadNode> nodes)
    {
        if (mHCScan < 0) { HCFinish(); return; }
        vector position = nodes[mHCScan].Position;
        int parent = mHCVisits.Get(mHCScan).Parent;
        mHCScan = parent;
        if (mHCPath.Count() == 0 && parent >= 0 && HCFlat(position, mHCTo) < mHCPolicy.DismountMeters) { return; }
        if (mHCPath.Count() >= mHCPolicy.MaxRouteNodes) { HCFail("CONVOY_ROUTE_NODE_CAP"); return; }
        if (mHCPath.Count() > 0) { mHCLength += HCFlat(mHCPath[mHCPath.Count() - 1], position); }
        mHCPath.Insert(position);
        if (mHCLength > mHCPolicy.MaxDriveMeters) { HCFail("CONVOY_ROUTE_LENGTH_CAP"); }
    }
    void HCFinish()
    {
        int low = 0;
        int high = mHCPath.Count() - 1;
        while (low < high)
        {
            vector held = mHCPath[low];
            mHCPath.Set(low, mHCPath[high]);
            mHCPath.Set(high, held);
            low++;
            high--;
        }
        if (mHCPath.Count() > 0) { mHCLength += HCFlat(mHCFrom, mHCPath[0]); }
        if (mHCIncludeEnd && mHCPath.Count() > 0) { mHCLength += HCFlat(mHCPath[mHCPath.Count() - 1], mHCTo); }
        if (mHCPath.Count() < 1 || mHCLength < mHCPolicy.MinDriveMeters) { HCFail("CONVOY_ROUTE_TOO_SHORT"); return; }
        if (mHCLength > mHCPolicy.MaxDriveMeters) { HCFail("CONVOY_ROUTE_LENGTH_CAP"); return; }
        mHCPhase = "ready";
        bool fixture = mHCFixtureRecovery && mHCFixtureRecovery.Fixture;
        HCXAIStuckRecovery.HCRouteUsed(fixture);
        string line = "[HC Convoy] astar expanded=" + mHCExpanded.ToString();
        line += " nodes=" + mHCPath.Count().ToString() + " length_m=" + mHCLength.ToString();
        if (fixture) { line += " fixture=1"; }
        Print(line + HCXAIStuckRecovery.HCSummary() + " runtime=PENDING");
        mHCFixtureRecovery = null;
    }
}
