// Own progress observer; dependency operations go through HCXExpansionBridge.
// Installed Workshop ai_scripts.pbo eAIGroup.c inspected: GetWaypoints,
// ClearWaypoints, AddWaypoint, SetWaypointBehaviour, IsInCombat exist.
// R5 bridge has no path-reset entry point: ladder deliberately stops at step 2.
// Native 1.30.164289 Game.c GetTime, Object.c GetPosition, EnScript.c arrays.
class HCXAIStuckRecovery
{
    static const int HC_CHECKS = 3;
    static const int HC_ROUTE_CAP = 256;
    protected static int s_Routes;
    protected static int s_PopsMax;
    protected static int s_Reissue;
    protected static int s_Next;
    protected static int s_Giveups;
    protected static int s_SummaryAt;
    ref array<vector> Route = new array<vector>;
    ref array<vector> Issued = new array<vector>;
    int Index;
    int LadderStep;
    int Checks;
    int CheckedAt;
    int IntervalMs = 5000;
    float ProgressMeters = 3;
    float EndMeters = 8;
    vector Anchor;
    bool Anchored;
    bool GivenUp;
    string Reason;

    static void HCRegister()
    {
        HCModuleReadiness.HCRegisterUse("ExpansionAI", "convoy_astar");
        HCModuleReadiness.HCRegisterUse("ExpansionAI", "stuck_recovery");
    }
    static void HCRouteUsed()
    {
        s_Routes++;
        HCModuleReadiness.HCUse("ExpansionAI", "convoy_astar");
    }
    static void HCObservePops(int pops) { if (pops > s_PopsMax) { s_PopsMax = pops; } }
    static string HCSummary()
    {
        string line = " routes=" + s_Routes.ToString();
        line += " astar_pops_max=" + s_PopsMax.ToString();
        line += " recoveries_step1=" + s_Reissue.ToString();
        line += " recoveries_step2=" + s_Next.ToString();
        line += " recoveries_step3=0 giveups=" + s_Giveups.ToString();
        return line;
    }
    static void HCSummarize(int now)
    {
        if (now < s_SummaryAt) { return; }
        s_SummaryAt = now + 300000;
        Print("" + "[HC Convoy] summary" + HCSummary() + " runtime=PENDING");
    }
    void HCStart(array<vector> route, int now)
    {
        Route.Clear();
        Issued.Clear();
        Index = 0;
        LadderStep = 0;
        Checks = 0;
        CheckedAt = now;
        Anchored = false;
        GivenUp = false;
        Reason = "";
        if (!route || route.Count() < 1 || route.Count() > HC_ROUTE_CAP) { HCGiveUp("STUCK_ROUTE_CAP"); return; }
        foreach (vector point : route) { Route.Insert(point); Issued.Insert(point); }
    }
    void HCGiveUp(string reason)
    {
        if (GivenUp) { return; }
        GivenUp = true;
        Reason = reason;
        s_Giveups++;
        Print("" + "[HC Convoy] recovery=giveup reason=" + reason + HCSummary() + " runtime=PENDING");
    }
    // Meaningful movement resets the sample window, but never the ladder.
    // A slow loop therefore cannot retry indefinitely.
    int HCMotion(vector position, int now)
    {
        if (GivenUp) { return 0; }
        if (!Anchored) { Anchor = position; Anchored = true; CheckedAt = now; return 0; }
        if (now - CheckedAt < IntervalMs) { return 0; }
        CheckedAt = now;
        if (HCXConvoyRoute.HCFlat(position, Anchor) >= ProgressMeters)
        {
            Anchor = position;
            Checks = 0;
            return 0;
        }
        Checks++;
        if (Checks < HC_CHECKS) { return 0; }
        Checks = 0;
        LadderStep++;
        if (LadderStep > 2) { HCGiveUp("STUCK_PATH_RESET_BRIDGE_UNAVAILABLE"); return -1; }
        return LadderStep;
    }
    void HCRecovered(int step)
    {
        if (step == 1) { s_Reissue++; }
        else if (step == 2) { s_Next++; }
        HCModuleReadiness.HCUse("ExpansionAI", "stuck_recovery");
    }
    // Route ownership is checked before any mutation. Combat suspends sampling.
    void HCCheck(eAIGroup group, vector position, int now)
    {
        if (GivenUp || Route.Count() == 0 || !group) { return; }
        if (HCXExpansionBridge.HCGroupIsInCombat(group)) { Anchored = false; Checks = 0; return; }
        array<vector> live = HCXExpansionBridge.HCGroupGetWaypoints(group);
        if (!live || live.Count() != Issued.Count()) { HCGiveUp("STUCK_ROUTE_OWNER_CHANGED"); return; }
        for (int own = 0; own < live.Count(); own++)
        {
            if (live[own] != Issued[own]) { HCGiveUp("STUCK_ROUTE_OWNER_CHANGED"); return; }
        }
        // Follow observed arrivals, never infer an unobserved provider index.
        while (Index < Route.Count() - 1 && HCXConvoyRoute.HCFlat(position, Route[Index]) <= 8) { Index++; }
        if (Index == Route.Count() - 1 && HCXConvoyRoute.HCFlat(position, Route[Index]) <= EndMeters) { return; }
        int recovery = HCMotion(position, now);
        if (recovery < 1) { return; }
        if (recovery == 2)
        {
            if (Index + 1 >= Route.Count()) { HCGiveUp("STUCK_NO_NEXT_WAYPOINT"); return; }
            Index++;
        }
        HCXExpansionBridge.HCGroupClearWaypoints(group);
        HCXExpansionBridge.HCGroupSetWaypointBehaviour(group, eAIWaypointBehavior.ONCE);
        Issued.Clear();
        for (int index = Index; index < Route.Count(); index++)
        {
            vector point = Route[index];
            HCXExpansionBridge.HCGroupAddWaypoint(group, point);
            Issued.Insert(point);
        }
        HCRecovered(recovery);
    }
}

// Extend in the scoped recovery file; HCXConvoyRuntime.c remains lead-owned.
modded class HCXConvoyRun
{
    ref HCXAIStuckRecovery mHCRecovery = new HCXAIStuckRecovery;

    override void HCBoard(int now)
    {
        string prior = mHCPhase;
        super.HCBoard(now);
        if (prior != "drive" && mHCPhase == "drive")
        {
            mHCRecovery.HCStart(mHCRoute.mHCPath, now);
            mHCRecovery.IntervalMs = Math.Max(1, mHCPolicy.StallSeconds * 1000 / HCXAIStuckRecovery.HC_CHECKS);
            mHCRecovery.ProgressMeters = mHCPolicy.StallMeters;
            mHCRecovery.Anchor = mHCCar.GetPosition();
            mHCRecovery.Anchored = true;
        }
    }
    override void HCDrive(int now)
    {
        string problem = HCDriveProblem();
        if (problem != "") { HCStop(problem, now); return; }
        if (mHCRecovery.GivenUp) { HCStop(mHCRecovery.Reason, now); return; }
        int recovery = mHCRecovery.HCMotion(mHCCar.GetPosition(), now);
        if (recovery < 0) { HCStop(mHCRecovery.Reason, now); return; }
        if (recovery > 0)
        {
            if (recovery == 2)
            {
                if (mHCIndex + 1 >= mHCRoute.mHCPath.Count()) { mHCRecovery.HCGiveUp("STUCK_NO_NEXT_WAYPOINT"); HCStop(mHCRecovery.Reason, now); return; }
                mHCIndex++;
            }
            // HC's car controller reads this same current road waypoint.
            // Reissue through the bridge too; no position or speed correction.
            HCXExpansionBridge.HCGroupClearWaypoints(mHCGroup);
            HCXExpansionBridge.HCGroupAddWaypoint(mHCGroup, mHCRoute.mHCPath[mHCIndex]);
            HCXExpansionBridge.HCGroupSetWaypointBehaviour(mHCGroup, eAIWaypointBehavior.HALT);
            mHCRecovery.HCRecovered(recovery);
        }
        // The bounded ladder supersedes the old immediate stall abort. Other
        // drive safety checks, total timeout and arrival still run in super.
        mHCProgressAt = now;
        super.HCDrive(now);
    }
}

modded class HCXAIAdapter
{
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (GetGame() && GetGame().IsServer() && HCXAIService.Adapter() == this) { HCXAIStuckRecovery.HCRegister(); }
    }
    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (HCXAIService.Adapter() == this) { HCXAIStuckRecovery.HCSummarize(GetGame().GetTime()); }
    }
}

// The existing journal quarantine is the finite-trip failure path. Do not
// misreport a stalled carrier as dead or fabricate arrival/inventory receipts.
modded class HCAICaravan
{
    override void HCStep()
    {
        HCXAICaravanAdapter port = HCXAICaravanAdapter.Cast(m_IO);
        if (!m_Enabled || !m_Ready || m_Busy || !HCActive()) { super.HCStep(); return; }
        if (port && port.m_Recovery.GivenUp)
        {
            HCQuarantine(port.m_Recovery.Reason);
            return;
        }
        super.HCStep();
    }
}
