// P2.1 infected navigation scheduler and the two PGFilter profiles (WD-2A-1).
// Installed scripts-1.30.164289: 3_Game/AI/AIWorld.c:59 PGFilter, :65 SetFlags, :67 SetCost,
// :28 PGAreaType (WATER, DOOR_CLOSED, FENCE_WALL), :98 FindPath; 3_Game/Global/Game.c GetTickTime.
//
// At most ONE FindPath per server tick is granted to deferrable callers (route extension, retarget,
// stuck re-path). GetTickTime is constant within one tick (#278), so it is the tick id. Callers that
// cannot be refused without retiring a pack or another module's job (Start, variety and migration
// segments) stay mandatory: they are charged to HC_WORK_NAV_INF and counted as nav_forced, never
// hidden. Route/flow cache hits cost no token.
class HCNavScheduler
{
    protected static float s_Tick = -1;
    protected static int s_Used;
    protected static int s_Granted;
    protected static int s_Deferred;
    protected static int s_Forced;

    protected static void HCRoll()
    {
        float now = GetGame().GetTickTime();
        if (now != s_Tick)
        {
            s_Tick = now;
            s_Used = 0;
        }
    }

    // Peek only: true while this tick's FindPath token is unspent.
    static bool HCAvailable()
    {
        if (!GetGame()) { return true; }
        HCRoll();
        return s_Used < 1;
    }

    // Deferrable FindPath: false means "try again on a later tick", nothing was spent.
    static bool HCTake()
    {
        if (!GetGame()) { return true; }
        HCRoll();
        if (s_Used >= 1 || !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_NAV_INF, 4))
        {
            s_Deferred++;
            HCModuleReadiness.HCUse("Infected", "nav_deferred");
            return false;
        }
        s_Used++;
        s_Granted++;
        HCModuleReadiness.HCUse("Infected", "nav_find_path");
        return true;
    }

    // Mandatory FindPath: always runs, always counted. A second one in the same tick is "forced".
    static void HCTakeMandatory()
    {
        if (!GetGame()) { return; }
        HCRoll();
        HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_NAV_INF, 4);
        if (s_Used >= 1)
        {
            s_Forced++;
            HCModuleReadiness.HCUse("Infected", "nav_forced");
        }
        s_Used++;
        s_Granted++;
        HCModuleReadiness.HCUse("Infected", "nav_find_path");
    }

    static string HCStats()
    {
        string line = "granted=" + s_Granted.ToString() + " deferred=" + s_Deferred.ToString() + " forced=" + s_Forced.ToString();
        return line;
    }

    static void HCStatsReset()
    {
        s_Tick = -1;
        s_Used = 0;
        s_Granted = 0;
        s_Deferred = 0;
        s_Forced = 0;
    }
}

// INF_OUTDOOR / INF_INTERIOR. SetFlags runs for both, always (HC-E033: an empty filter matches no
// polygon). Closed doors are cheap on purpose: a pack walks up to a door and the door queue opens
// it, instead of routing hundreds of metres around.
class HCNavFilters
{
    static const int PROFILE_OUTDOOR = 0;
    static const int PROFILE_INTERIOR = 1;

    protected static ref PGFilter s_Outdoor;
    protected static ref PGFilter s_Interior;

    protected static void HCBuild()
    {
        if (s_Outdoor && s_Interior) { return; }
        s_Outdoor = new PGFilter;
        // Native fence vaults and climbs are allowed outdoors (the vanilla locomotion already drives them).
        s_Outdoor.SetFlags(PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE | PGPolyFlags.JUMP | PGPolyFlags.CLIMB, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        s_Outdoor.SetCost(PGAreaType.DOOR_CLOSED, 12);
        s_Outdoor.SetCost(PGAreaType.FENCE_WALL, 4);
        s_Outdoor.SetCost(PGAreaType.WATER, 20);
        s_Interior = new PGFilter;
        s_Interior.SetFlags(PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        s_Interior.SetCost(PGAreaType.DOOR_CLOSED, 6);
    }

    static PGFilter HCFor(int profile)
    {
        HCBuild();
        if (profile == PROFILE_INTERIOR) { return s_Interior; }
        return s_Outdoor;
    }
}

// Shared summary line, printed on change only. The [HC Use] lines stay the authoritative counters;
// this one adds the cache and scheduler totals the lead reads next to the infected R2 tick cost.
modded class HCModuleReadiness
{
    protected static string s_HCNavSummaryLast;

    override static void HCSummary()
    {
        super.HCSummary();
        string line = "[HC Nav] scheduler " + HCNavScheduler.HCStats() + " " + HCNavRouteCache.HCStats() + " " + HCHordeFlowCache.HCStats();
        if (line == s_HCNavSummaryLast) { return; }
        s_HCNavSummaryLast = line;
        Print("" + line);
    }
}
