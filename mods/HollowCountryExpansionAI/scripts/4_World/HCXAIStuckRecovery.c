// Own progress observer; dependency operations go through HCXExpansionBridge.
// Installed Workshop ai_scripts.pbo eAIGroup.c inspected: GetWaypoints,
// ClearWaypoints, AddWaypoint, SetWaypointBehaviour, IsInCombat exist.
// Rung 3 uses HC road planning, never a dependency path-reset API.
// Native 1.30.164289 Game.c GetTime, Object.c GetPosition, EnScript.c arrays.
// Journey FIFO ownership snapshot; the scheduler lives in HCXAICaravanAdapter.
class HCXJourneyReplanTurn
{
    ref HCXAISiteState State;
    ref HCXAIStuckRecovery Recovery;
    eAIGroup Group;
    vector Destination;
    int Started;
    bool Active;
}

class HCXAIStuckRecovery
{
    static const int HC_CHECKS = 3;
    static const int HC_ROUTE_CAP = 257;
    protected static string s_Module = "optional-expansion-human-ai";
    protected static int s_Routes;
    protected static int s_PopsMax;
    protected static int s_Reissue;
    protected static int s_Next;
    protected static int s_Replans;
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
    string Kind = "journey";
    ref HCXConvoyRoute Replan;
    bool Fixture;
    bool JourneyScheduled;
    bool AwaitingReplan;

    // Mark an existing observer only when its own next sample is due.
    // No sample, anchor, timestamp, ladder or route is changed here.
    static bool HCFixtureStuck(vector pos, bool apply, out string reason)
    {
        reason = "EnableSmokeFixtures-off";
        if (!HCAdminFixtures.HCEnabled()) { return false; }
        int now = GetGame().GetTime();
        HCXAIStuckRecovery chosen;
        float nearest = float.MAX;
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (director)
        {
            array<ref HCXAISiteState> states = director.States();
            HCWorkBudget work = new HCWorkBudget;
            work.HCReset(states.Count(), HCPerfConfig.HCGet().SliceMs);
            foreach (HCXAISiteState state : states)
            {
                if (!work.HCContinue()) { reason = "fixture-budget"; return false; }
                if (!state || !state.HCJourneyWalking || state.Completed || !state.Materialized || !state.Patrol || !state.Patrol.m_Group) { continue; }
                HCXAIStuckRecovery recovery = state.HCJourneyRecovery;
                if (!recovery || recovery.Fixture || recovery.GivenUp || !recovery.Anchored || recovery.Replan || recovery.AwaitingReplan || recovery.Route.Count() < 1 || now - recovery.CheckedAt < recovery.IntervalMs) { continue; }
                if (HCXExpansionBridge.HCGroupIsInCombat(state.Patrol.m_Group)) { continue; }
                DayZPlayerImplement leader = HCXExpansionBridge.HCGroupGetFormationLeader(state.Patrol.m_Group);
                if (!leader || !leader.IsAlive()) { continue; }
                float gap = vector.DistanceSq(pos, leader.GetPosition());
                if (gap < nearest) { nearest = gap; chosen = recovery; }
            }
        }
        HCXConvoyService service = HCXConvoyService.HCGet();
        if (service && service.mHCRun)
        {
            HCXConvoyRun run = service.mHCRun;
            HCXAIStuckRecovery convoy = run.mHCRecovery;
            if (run.mHCPhase == "drive" && run.mHCCar && convoy && !convoy.Fixture && !convoy.GivenUp && convoy.Anchored && !convoy.Replan && now - convoy.CheckedAt >= convoy.IntervalMs)
            {
                float carGap = vector.DistanceSq(pos, run.mHCCar.GetPosition());
                if (carGap < nearest) { chosen = convoy; }
            }
        }
        reason = "no-existing-due-motion-check";
        if (!chosen) { return false; }
        if (apply) { chosen.Fixture = true; }
        reason = "due-observer-marked-normal-motion-ladder";
        return true;
    }

    static void HCRegister(string module)
    {
        s_Module = module;
        HCModuleReadiness.HCRegisterUse(s_Module, "convoy_astar");
        HCModuleReadiness.HCRegisterUse(s_Module, "stuck_recovery");
    }
    static void HCRouteUsed()
    {
        s_Routes++;
        HCModuleReadiness.HCUse(s_Module, "convoy_astar");
    }
    static void HCObservePops(int pops) { if (pops > s_PopsMax) { s_PopsMax = pops; } }
    static string HCSummary()
    {
        string line = " routes=" + s_Routes.ToString();
        line += " astar_pops_max=" + s_PopsMax.ToString();
        line += " recoveries_step1=" + s_Reissue.ToString();
        line += " recoveries_step2=" + s_Next.ToString();
        line += " recoveries_step3=" + s_Replans.ToString() + " giveups=" + s_Giveups.ToString();
        return line;
    }
    static void HCSummarize(int now)
    {
        if (now < s_SummaryAt) { return; }
        s_SummaryAt = now + 300000;
        Print("" + "[HC Convoy] summary" + HCSummary() + " runtime=PENDING");
    }
    void HCStart(array<vector> route, int now, int routeCap)
    {
        Fixture = false;
        Route.Clear();
        Issued.Clear();
        Index = 0;
        LadderStep = 0;
        Checks = 0;
        CheckedAt = now;
        Anchored = false;
        GivenUp = false;
        Reason = "";
        Replan = null;
        AwaitingReplan = false;
        if (!route || route.Count() < 1 || route.Count() > Math.Min(HC_ROUTE_CAP, routeCap)) { HCGiveUp("STUCK_ROUTE_CAP"); return; }
        foreach (vector point : route) { Route.Insert(point); Issued.Insert(point); }
    }
    void HCGiveUp(string reason)
    {
        if (GivenUp) { return; }
        GivenUp = true;
        Reason = reason;
        s_Giveups++;
        string prefix = "[HC XAI] recovery=giveup party=" + Kind;
        if (Kind == "convoy") { prefix = "[HC Convoy] recovery=giveup"; }
        if (Fixture) { prefix += " fixture=1"; }
        Print(prefix + " reason=" + reason + HCSummary() + " runtime=PENDING");
        Fixture = false;
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
        if (LadderStep > 3) { HCGiveUp("STUCK_REPLAN_NO_PROGRESS"); return -1; }
        return LadderStep;
    }
    void HCRecovered(int step)
    {
        if (step == 1) { s_Reissue++; }
        else if (step == 2) { s_Next++; }
        else if (step == 3) { s_Replans++; }
        if (Fixture)
        {
            HCModuleReadiness.HCUseFixture(s_Module, "stuck_recovery");
            Print("[HC Convoy] recovery_step=" + step.ToString() + " fixture=1 runtime=PENDING");
        }
        else { HCModuleReadiness.HCUse(s_Module, "stuck_recovery"); }
        Fixture = false;
    }
    // At most sixteen forward candidates; never move the cursor backwards.
    static int HCForward(array<vector> path, int index, vector position)
    {
        int best = index;
        float gap = HCXConvoyRoute.HCFlatSq(position, path[index]);
        int end = Math.Min(path.Count(), index + 17);
        for (int scan = index + 1; scan < end; scan++)
        {
            float candidate = HCXConvoyRoute.HCFlatSq(position, path[scan]);
            if (candidate < gap) { gap = candidate; best = scan; }
        }
        return best;
    }
    bool HCBeginReplan(vector position, vector destination, HCConvoyPolicy policy, bool includeEnd = false)
    {
        Replan = new HCXConvoyRoute;
        if (!Replan.HCPlan(position, destination, policy, includeEnd))
        {
            HCGiveUp(Replan.mHCReason);
            return false;
        }
        // Use the bounded nearest-node scan, with an origin-specific refusal.
        Replan.mHCOriginFailure = "STUCK_OFFROAD";
        if (JourneyScheduled) { Replan.mHCTimeoutReason = "JOURNEY_REPLAN_TIMEOUT"; }
        return true;
    }
    int HCStepReplan()
    {
        Replan.HCStep();
        if (Replan.mHCPhase == "failed") { HCGiveUp(Replan.mHCReason); return -1; }
        if (Replan.mHCPhase == "ready") { return 1; }
        return 0;
    }
    // Route ownership is checked before any mutation. Combat suspends sampling.
    void HCCheck(eAIGroup group, vector position, int now, bool replanTick = false)
    {
        if (GivenUp || Route.Count() == 0 || !group) { return; }
        if (HCXExpansionBridge.HCGroupIsInCombat(group)) { Anchored = false; Checks = 0; return; }
        array<vector> live = HCXExpansionBridge.HCGroupGetWaypoints(group);
        if (!live || live.Count() != Issued.Count()) { HCGiveUp("STUCK_ROUTE_OWNER_CHANGED"); return; }
        for (int own = 0; own < live.Count(); own++)
        {
            if (HCXConvoyRoute.HCFlatSq(live[own], Issued[own]) >= 1) { HCGiveUp("STUCK_ROUTE_OWNER_CHANGED"); return; }
        }
        Index = HCForward(Route, Index, position);
        if (Index < Route.Count() - 1 && HCXConvoyRoute.HCFlat(position, Route[Index]) <= 8) { Index++; }
        if (Index == Route.Count() - 1 && HCXConvoyRoute.HCFlat(position, Route[Index]) <= EndMeters) { return; }
        int recovery;
        if (Replan || AwaitingReplan) { recovery = 3; }
        else { recovery = HCMotion(position, now); }
        if (recovery < 1) { return; }
        if (recovery == 2)
        {
            if (Index + 1 < Route.Count()) { Index++; }
            else { LadderStep = 3; recovery = 3; }
        }
        if (recovery == 3)
        {
            // Director visits request work; only the FIFO core tick may step it.
            if (JourneyScheduled && !replanTick) { AwaitingReplan = true; return; }
            if (!Replan)
            {
                HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
                if (!roads) { HCGiveUp("STUCK_REPLAN_ROADS_UNAVAILABLE"); return; }
                HCConvoyPolicy policy = roads.HCWalkingPolicy();
                if (!HCBeginReplan(position, Route[Route.Count() - 1], policy, true)) { return; }
            }
            int status = HCStepReplan();
            if (status != 1) { return; }
            vector destination = Route[Route.Count() - 1];
            Route.Clear();
            foreach (vector planned : Replan.mHCPath) { Route.Insert(planned); }
            Route.Insert(destination);
            Index = 0;
            Replan = null;
            AwaitingReplan = false;
            Reason = "";
            Anchor = position;
            CheckedAt = now;
            Checks = 0;
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
            mHCRecovery.Kind = "convoy";
            mHCRecovery.HCStart(mHCRoute.mHCPath, now, mHCPolicy.MaxRouteNodes + 1);
            mHCRecovery.IntervalMs = Math.Max(1, mHCPolicy.StallSeconds * 1000 / HCXAIStuckRecovery.HC_CHECKS);
            mHCRecovery.ProgressMeters = mHCPolicy.StallMeters;
            mHCRecovery.Anchor = mHCCar.GetPosition();
            mHCRecovery.Anchored = true;
        }
    }
    override void HCDrive(int now)
    {
        super.HCDrive(now);
        if (mHCPhase != "drive") { mHCRecovery.Fixture = false; return; }
        if (mHCRecovery.GivenUp) { HCStop(mHCRecovery.Reason, now); return; }
        vector position = mHCCar.GetPosition();
        int recovery;
        if (mHCRecovery.Replan) { recovery = 3; }
        else { recovery = mHCRecovery.HCMotion(position, now); }
        if (recovery < 0)
        {
            // No progress after rung 3 is a real stalled controller.
            HCStop("CONVOY_STALLED", now);
            return;
        }
        if (recovery == 1)
        {
            if (mHCIndex + 1 < mHCRoute.mHCPath.Count())
            {
                mHCIndex = HCXAIStuckRecovery.HCForward(mHCRoute.mHCPath, mHCIndex + 1, position);
                mHCRecovery.HCRecovered(1);
            }
            else { mHCRecovery.LadderStep = 3; recovery = 3; }
        }
        else if (recovery == 2)
        {
            if (mHCIndex + 1 < mHCRoute.mHCPath.Count()) { mHCIndex++; mHCRecovery.HCRecovered(2); }
            else { mHCRecovery.LadderStep = 3; recovery = 3; }
        }
        if (recovery == 3)
        {
            if (!mHCRecovery.Replan)
            {
                if (!mHCRecovery.HCBeginReplan(position, HCDestination(), mHCPolicy)) { HCStop(mHCRecovery.Reason, now); return; }
            }
            int status = mHCRecovery.HCStepReplan();
            if (status < 0) { HCStop(mHCRecovery.Reason, now); return; }
            if (status == 0) { return; }
            mHCRoute = mHCRecovery.Replan;
            mHCRecovery.Replan = null;
            mHCIndex = 0;
            mHCRecovery.Anchor = position;
            mHCRecovery.CheckedAt = now;
            mHCRecovery.Checks = 0;
            mHCRecovery.HCRecovered(3);
        }
    }

    override bool HCDriveStalled(float moved, int now)
    {
        // The finite observer ladder owns stalls, while HCDrive keeps all other checks.
        return false;
    }

    override void HCInput()
    {
        // Hold the real car while the replacement route is pending. The old
        // ready route stays intact until an entire new plan succeeds.
        if (mHCPhase == "drive" && mHCRecovery.Replan && HCHolding())
        {
            if (HCForeignDriver()) { HCYield(GetGame().GetTime()); return; }
            HCHoldBrake();
            return;
        }
        super.HCInput();
    }
}

modded class HCXAIAdapter
{
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (GetGame() && GetGame().IsServer() && HCXAIService.Adapter() == this) { HCXAIStuckRecovery.HCRegister(GetName()); }
        if (GetGame() && GetGame().IsServer() && HCXAIService.Adapter() == this) { HCXAIFixtureProvider.HCRegisterOnce(); }
    }
    override void OnTick(float deltaTime)
    {
        if (GetGame() && GetGame().IsServer() && HCXAIService.Adapter() == this) { HCXJourneyReplans.HCTick(); }
        super.OnTick(deltaTime);
        if (HCXAIService.Adapter() == this) { HCXAIStuckRecovery.HCSummarize(GetGame().GetTime()); }
    }
    override void OnStop()
    {
        if (HCXAIService.Adapter() == this) { HCXJourneyReplans.HCClear(); }
        super.OnStop();
    }
}

// Decode legacy aborted journals only. No active caravan caller drives this
// observer; do not retain a dead HCStep abort handler or claim Walker coverage.
modded class HCAICaravan
{
    override bool HCTerminal(string leg) { return leg == "aborted" || super.HCTerminal(leg); }

    override bool HCValidState(HCCaravanState row)
    {
        if (!row || row.Leg != "aborted") { return super.HCValidState(row); }
        if (row.Version != 1 || row.Refusal.Length() > 96 || !HCValidHistory(row)) { return false; }
        if (!HCValidTripId(row.Id, row.TripSequence) || !HCWorldLimits.Token(row.RouteId)) { return false; }
        if (!HCWorldLimits.Token(row.LeaseId) || !HCWorldLimits.Token(row.PartyId) || !HCWorldLimits.Token(row.CargoId)) { return false; }
        if (!HCWorldLimits.Token(row.ActorId) || !HCWorldLimits.Token(row.ItemId) || !HCWorldLimits.Token(row.ItemClass)) { return false; }
        if (row.Generation < 1 || !(row.Quantity >= 0) || !(row.Quantity <= float.MAX)) { return false; }
        return row.CargoReceipt == "retained" || row.CargoReceipt == "lost";
    }

}
