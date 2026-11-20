// #210 road branch: bounded road route for one convoy over the caravan's
// already-loaded installed road nodes (HCXAICaravanAdapter.c HCXAICaravanRoads).
// Read only: this planner keeps its own parent/frontier arrays and never
// writes HCXAICaravanRoadNode.Parent, never loads files and never opens roads.
// Native scripts-1.30.164289: 1_Core/proto/EnMath.c:305 Sqrt; EnScript.c:380/385/407
// array Count/Clear/Insert. Work is charged to HC_WORK_CONVOY_ROUTE, the consumer
// that owns the raid/column situation this route serves.
// Road geometry, drivability and arrival remain runtime=PENDING.
class HCXConvoyRoute
{
    ref array<int> mHCParent = new array<int>;
    ref array<int> mHCFrontier = new array<int>;
    ref array<vector> mHCPath = new array<vector>;
    string mHCPhase = "idle";
    string mHCReason;
    HCConvoyPolicy mHCPolicy;
    vector mHCFrom;
    vector mHCTo;
    float mHCStraight;
    float mHCStartGap;
    float mHCEndGap;
    float mHCLength;
    int mHCCount;
    int mHCScan;
    int mHCHead;
    int mHCStart = -1;
    int mHCEnd = -1;
    int mHCExpanded;

    static float HCFlatSq(vector a, vector b)
    {
        float dx = a[0] - b[0];
        float dz = a[2] - b[2];
        return dx * dx + dz * dz;
    }

    static float HCFlat(vector a, vector b)
    {
        return Math.Sqrt(HCFlatSq(a, b));
    }

    bool HCFail(string reason)
    {
        mHCPhase = "failed";
        mHCReason = reason;
        return false;
    }

    bool HCPlan(vector origin, vector destination, HCConvoyPolicy policy)
    {
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (!policy) { return HCFail("CONVOY_POLICY_INVALID"); }
        if (!roads) { return HCFail("CONVOY_ROAD_NETWORK_UNAVAILABLE"); }
        if (roads.Nodes.Count() < 2) { return HCFail("CONVOY_ROAD_NETWORK_UNAVAILABLE"); }
        mHCPolicy = policy;
        mHCFrom = origin;
        mHCTo = destination;
        mHCStraight = HCFlat(origin, destination);
        mHCCount = roads.Nodes.Count();
        mHCParent.Clear();
        mHCFrontier.Clear();
        mHCPath.Clear();
        mHCScan = 0;
        mHCHead = 0;
        mHCStart = -1;
        mHCEnd = -1;
        mHCExpanded = 0;
        mHCLength = 0;
        mHCStartGap = policy.MaxApproachMeters * policy.MaxApproachMeters;
        mHCEndGap = mHCStartGap;
        mHCReason = "";
        mHCPhase = "scan";
        return true;
    }

    // At most RoadNodesPerTick node steps per call, one shared work unit per
    // RoadNodesPerWorkUnit steps. A refused unit leaves the cursors untouched.
    void HCStep()
    {
        if (mHCPhase != "scan" && mHCPhase != "search" && mHCPhase != "build") { return; }
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (!roads) { HCFail("CONVOY_ROAD_NETWORK_CHANGED"); return; }
        if (roads.Nodes.Count() != mHCCount) { HCFail("CONVOY_ROAD_NETWORK_CHANGED"); return; }
        array<ref HCXAICaravanRoadNode> nodes = roads.Nodes;
        for (int unit = 0; unit < mHCPolicy.RoadNodesPerTick; unit++)
        {
            if (unit % mHCPolicy.RoadNodesPerWorkUnit == 0 && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_CONVOY_ROUTE, 1)) { return; }
            if (mHCPhase == "scan") { HCScan(nodes); }
            else if (mHCPhase == "search") { HCSearch(nodes); }
            else if (mHCPhase == "build") { HCBuild(nodes); }
            else { return; }
        }
    }

    void HCScan(array<ref HCXAICaravanRoadNode> nodes)
    {
        if (mHCScan < nodes.Count())
        {
            vector position = nodes[mHCScan].Position;
            mHCParent.Insert(-2);
            float fromGap = HCFlatSq(mHCFrom, position);
            float toGap = HCFlatSq(mHCTo, position);
            if (fromGap <= mHCStartGap) { mHCStart = mHCScan; mHCStartGap = fromGap; }
            if (toGap <= mHCEndGap) { mHCEnd = mHCScan; mHCEndGap = toGap; }
            mHCScan++;
            return;
        }
        if (mHCStart < 0 || mHCEnd < 0) { HCFail("CONVOY_ROAD_APPROACH_TOO_FAR"); return; }
        mHCParent.Set(mHCStart, -1);
        mHCFrontier.Insert(mHCStart);
        mHCPhase = "search";
    }

    // Breadth-first over links, pruned to an ellipse of DetourMeters around the
    // straight car-to-destination line; MaxPlanNodes caps expansions.
    void HCSearch(array<ref HCXAICaravanRoadNode> nodes)
    {
        if (mHCHead >= mHCFrontier.Count()) { HCFail("CONVOY_ROAD_DISCONNECTED"); return; }
        if (mHCExpanded >= mHCPolicy.MaxPlanNodes) { HCFail("CONVOY_ROAD_SEARCH_CAP"); return; }
        int current = mHCFrontier[mHCHead];
        mHCHead++;
        mHCExpanded++;
        if (current == mHCEnd)
        {
            mHCScan = current;
            mHCPhase = "build";
            return;
        }
        float limit = mHCStraight + 2 * mHCPolicy.DetourMeters;
        array<int> links = nodes[current].Links;
        foreach (int adjacent : links)
        {
            if (adjacent < 0 || adjacent >= mHCParent.Count()) { continue; }
            if (mHCParent[adjacent] != -2) { continue; }
            vector candidate = nodes[adjacent].Position;
            if (HCFlat(mHCFrom, candidate) + HCFlat(candidate, mHCTo) > limit) { continue; }
            mHCParent.Set(adjacent, current);
            mHCFrontier.Insert(adjacent);
        }
    }

    // Walks parents from the destination node back to the start node. Nodes
    // within DismountMeters of the destination are dropped so the crew stops
    // short and walks the last stretch; the start node is always kept.
    void HCBuild(array<ref HCXAICaravanRoadNode> nodes)
    {
        if (mHCScan < 0) { HCFinish(); return; }
        vector position = nodes[mHCScan].Position;
        int parent = mHCParent[mHCScan];
        mHCScan = parent;
        if (mHCPath.Count() == 0 && parent >= 0 && HCFlat(position, mHCTo) < mHCPolicy.DismountMeters) { return; }
        if (mHCPath.Count() >= mHCPolicy.MaxRouteNodes) { HCFail("CONVOY_ROUTE_NODE_CAP"); return; }
        if (mHCPath.Count() > 0) { mHCLength += HCFlat(mHCPath[mHCPath.Count() - 1], position); }
        mHCPath.Insert(position);
        if (mHCLength > mHCPolicy.MaxDriveMeters) { HCFail("CONVOY_ROUTE_LENGTH_CAP"); return; }
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
            high = high - 1;
        }
        if (mHCPath.Count() > 0) { mHCLength += HCFlat(mHCFrom, mHCPath[0]); }
        if (mHCPath.Count() < 1 || mHCLength < mHCPolicy.MinDriveMeters) { HCFail("CONVOY_ROUTE_TOO_SHORT"); return; }
        if (mHCLength > mHCPolicy.MaxDriveMeters) { HCFail("CONVOY_ROUTE_LENGTH_CAP"); return; }
        mHCPhase = "ready";
    }
}
