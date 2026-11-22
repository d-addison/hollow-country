// Shared deterministic per-tick work budget (issue #138). Cost is counted in caller-defined work
// units, never in clock time: HCWorkBudget's 4 ms guard compares GetTickTime() deltas, and the
// measured spikes (Interiors, Ecology) were bursts of whole slices that the clock guard let through,
// so a count-weighted budget is what bounds one HC tick.
// No engine calls: pure integer arithmetic, so it is cheap, allocation free after construction and
// can be modelled offline with explicit synthetic costs (tests/unit/test_hc_unit_budget.py).
// Contract:
//   HCReset(limit)  starts one tick with `limit` units.
//   HCTake(cost)    true when the item fits in the remaining units. The FIRST item of a tick is
//                   always admitted, even when its cost exceeds the limit, so an item heavier than
//                   the whole budget still makes progress (one item per tick) and can never starve.
//   Callers keep their cursor/stage BEFORE yielding and resume at the item whose HCTake failed.
// Typical units: 1 per cheap array row, 8 per object creation, 64 per native path probe.
//
// Shared core-tick budget (wave 13, issue #138): HCServer owns ONE instance, reset to
// MaxTickWorkItems at the top of every core tick and exposed through HCServer.HCTickWork().
// Item loops of several modules take one unit per item with HCTakeFor(consumer, cost):
//   - a consumer whose requests fit in the remaining units is admitted as usual;
//   - NO STARVATION RULE: a consumer's FIRST request in a tick that the exhausted pool refuses is
//     still admitted once (a forced item, counted in HCStarved), so every consumer advances at least
//     one item per tick whatever the earlier modules spent. Its later requests in that tick are
//     refused normally. Total work per tick is therefore at most
//     limit + (HC_WORK_CONSUMERS - 1) cost-1 units, never more (the very first item of a tick is the budget's
//     own first-item admission, so at most the other consumers can be forced).
//   Callers keep their cursor and resume at the item whose request was refused.
// Outside a core tick HCServer.HCTickWork() returns its idle budget (reset to HC_WORK_UNBOUNDED), which
// never refuses. This class stays allocation free: the one idle instance is owned by HCServer.
// The per-window figures (shared_used_max, shared_starved) are rolled by HCEndTick and printed once per
// perf window by HCWindowReport; there is no per-tick print.
class HCUnitBudget
{
    // Consumer ids for HCTakeFor. Fixed storage supports 64 independent consumers.
    // Native fixed arrays: scripts-1.30.164289/3_Game/CfgBunkerBroadcastJsonData.c:56.
    static const int HC_WORK_INFECTED = 0;
    static const int HC_WORK_INTERIORS = 1;
    static const int HC_WORK_SEARCH_BIND = 2;
    static const int HC_WORK_SEARCH_MAINT = 3;
    static const int HC_WORK_SEARCH_REFRESH = 4;
    // Wave 14 (#195): the detached-slot loop of HCSearchHouses.RecycleSpentBindings has its own id, so a
    // spent pool still forces one unit for it after the active-slot loop took the MAINT one.
    static const int HC_WORK_SEARCH_DETACHED = 5;
    static const int HC_WORK_LOD_CLASSIFY = 6;
    static const int HC_WORK_LOD_HERD = 7;
    // Wave 17: player-base stash scan (#151) and faction conflict outcomes (#146).
    static const int HC_WORK_BASES = 8;
    static const int HC_WORK_CONFLICT = 9;
    // AI-to-AI caravan pairing and cargo scans (#145).
    static const int HC_WORK_TRADE = 10;
    // Leased AI situations and physical event spoils (#147).
    static const int HC_WORK_SITUATIONS = 11;
    static const int HC_WORK_BASE_RAID = 12;
    // Role activity scheduling and its lease maintenance (#144 #146).
    static const int HC_WORK_ROLES = 13;
    // Context formation styling of HC site patrol groups.
    static const int HC_WORK_FORMATION = 14;
    // AI car finding and repair jobs.
    static const int HC_WORK_CARFIX = 15;
    // Hearth fire bookkeeping behind house smoke (lit fireplaces with provenance).
    static const int HC_WORK_HEARTH = 16;
    // World incident registry sweep (gas zones, heli crashes, scenes, raids, gunfire, hordes).
    static const int HC_WORK_INCIDENTS = 17;
    // Expansion AI responses to perceived world incidents.
    static const int HC_WORK_INCIDENT_RESPONSE = 18;
    static const int HC_WORK_AI_RESPAWN = 19;
    static const int HC_WORK_SEARCH_COMPACT = 20;
    static const int HC_WORK_SHELTER = 21;
    // HC-18 AI site director locality paging.
    static const int HC_WORK_AI_SITES = 22;
    // HC-42 story index line batches. Own slot: Events takes SITUATIONS first on
    // every tick, so a shared slot left the index refused for the whole boot (095).
    static const int HC_WORK_STORY_INDEX = 23;
    // HC-18 regional road route source check and resolve. Own slot: it steps after the
    // site director in the same Step, which took AI_SITES first every tick (096).
    static const int HC_WORK_AI_ROUTES = 24;
    static const int HC_WORK_POLICE_BIND = 25;
    // Road graph load and caravan path search. Own slot: AITrade takes TRADE first on
    // starved ticks, so the 38820-node graph got at most 8 nodes per tick (099).
    static const int HC_WORK_ROADS = 26;
    // #264/#265 perf batches: own slots for consumers that shared one before.
    static const int HC_WORK_INFECTED_VARIETY = 27;
    static const int HC_WORK_INFECTED_VARIETY_ROUTES = 28;
    static const int HC_WORK_SITUATION_RUNTIME = 29;
    static const int HC_WORK_SITUATION_SMOKE = 30;
    static const int HC_WORK_ADMIN_VISITOR = 31;
    static const int HC_WORK_TACTICS_SCAN = 32;
    static const int HC_WORK_AI_TRADE_PRODUCER = 33;
    static const int HC_WORK_CONVOY_ROUTE = 34;
    static const int HC_WORK_CONVOY_RUN = 35;
    static const int HC_WORK_SEARCH_COVERAGE = 36;
    static const int HC_WORK_SEARCH_RETIREMENT = 37;
    static const int HC_WORK_WILDLIFE = 38;
    // Zone state/service must advance even when earlier modules exhaust the pool.
    static const int HC_WORK_ZONE_GUARDS = 39;
    // P1.2 qualified-route cache validity/sampling. Own slot: it shares HCXAISiteDirector with the
    // AI_SITES pager and must not starve the gapcode route catalog on AI_ROUTES.
    static const int HC_WORK_AI_ROUTE_CACHE = 40;
    static const int HC_WORK_ADMIN_TELEPORT = 41;
    // Wave D (HC-P010): one owned slot per real consumer that used to take the shared pool raw.
    static const int HC_WORK_ADMIN_WORLD = 42;
    static const int HC_WORK_SIGNS_OF_LIFE = 43;
    static const int HC_WORK_ECOLOGY_TOWN = 44;
    static const int HC_WORK_ECOLOGY_ANIMAL = 45;
    static const int HC_WORK_ECOLOGY_PATH = 46;
    static const int HC_WORK_ECOLOGY_MIGRATION = 47;
    static const int HC_WORK_FORAGE = 48;
    static const int HC_WORK_HORDE_REINFORCE = 49;
    static const int HC_WORK_PICKERS = 50;
    static const int HC_WORK_PICK_CARRY = 51;
    static const int HC_WORK_PICK_HOUSES = 52;
    static const int HC_WORK_MISSION_BEACON = 53;
    static const int HC_WORK_NAV_INF = 54;
    static const int HC_WORK_NAV_XAI = 55;
    static const int HC_WORK_CONSUMERS = 56;
    // Sentinel limit of HCServer's idle budget (no core tick running): far above any real per-tick count and
    // far below int overflow of m_Used + units.
    static const int HC_WORK_UNBOUNDED = 1000000000;

    // Authoring table: add a slot here and its Performance.TickWeight row in
    // shared_settings.json. Labels and weights are consumed without DTO fields.
    protected static ref array<string> s_ConsumerNames;
    protected static ref array<int> s_DefaultWeights;

    static void HCRegisterConsumer(int slot, string name, int defaultWeight)
    {
        s_ConsumerNames.Set(slot, name);
        s_DefaultWeights.Set(slot, defaultWeight);
    }

    static void HCInitConsumers()
    {
        if (s_ConsumerNames) { return; }
        s_ConsumerNames = new array<string>;
        s_DefaultWeights = new array<int>;
        s_ConsumerNames.Resize(HC_WORK_CONSUMERS);
        s_DefaultWeights.Resize(HC_WORK_CONSUMERS);
        HCRegisterConsumer(HC_WORK_INFECTED, "INFECTED", 1);
        HCRegisterConsumer(HC_WORK_INTERIORS, "INTERIORS", 1);
        HCRegisterConsumer(HC_WORK_SEARCH_BIND, "SEARCH_BIND", 1);
        HCRegisterConsumer(HC_WORK_SEARCH_MAINT, "SEARCH_MAINT", 1);
        HCRegisterConsumer(HC_WORK_SEARCH_REFRESH, "SEARCH_REFRESH", 1);
        HCRegisterConsumer(HC_WORK_SEARCH_DETACHED, "SEARCH_DETACHED", 1);
        HCRegisterConsumer(HC_WORK_LOD_CLASSIFY, "LOD_CLASSIFY", 1);
        HCRegisterConsumer(HC_WORK_LOD_HERD, "LOD_HERD", 1);
        HCRegisterConsumer(HC_WORK_BASES, "BASES", 1);
        HCRegisterConsumer(HC_WORK_CONFLICT, "CONFLICT", 1);
        HCRegisterConsumer(HC_WORK_TRADE, "TRADE", 1);
        HCRegisterConsumer(HC_WORK_SITUATIONS, "SITUATIONS", 1);
        HCRegisterConsumer(HC_WORK_BASE_RAID, "BASE_RAID", 1);
        HCRegisterConsumer(HC_WORK_ROLES, "ROLES", 1);
        HCRegisterConsumer(HC_WORK_FORMATION, "FORMATION", 1);
        HCRegisterConsumer(HC_WORK_CARFIX, "CARFIX", 1);
        HCRegisterConsumer(HC_WORK_HEARTH, "HEARTH", 1);
        HCRegisterConsumer(HC_WORK_INCIDENTS, "INCIDENTS", 1);
        HCRegisterConsumer(HC_WORK_INCIDENT_RESPONSE, "INCIDENT_RESPONSE", 1);
        HCRegisterConsumer(HC_WORK_AI_RESPAWN, "AI_RESPAWN", 1);
        HCRegisterConsumer(HC_WORK_SEARCH_COMPACT, "SEARCH_COMPACT", 1);
        HCRegisterConsumer(HC_WORK_SHELTER, "SHELTER", 1);
        HCRegisterConsumer(HC_WORK_AI_SITES, "AI_SITES", 1);
        HCRegisterConsumer(HC_WORK_STORY_INDEX, "STORY_INDEX", 1);
        HCRegisterConsumer(HC_WORK_AI_ROUTES, "AI_ROUTES", 1);
        HCRegisterConsumer(HC_WORK_POLICE_BIND, "POLICE_BIND", 1);
        HCRegisterConsumer(HC_WORK_ROADS, "ROADS", 1);
        HCRegisterConsumer(HC_WORK_INFECTED_VARIETY, "INFECTED_VARIETY", 1);
        HCRegisterConsumer(HC_WORK_INFECTED_VARIETY_ROUTES, "INFECTED_VARIETY_ROUTES", 1);
        HCRegisterConsumer(HC_WORK_SITUATION_RUNTIME, "SITUATION_RUNTIME", 1);
        HCRegisterConsumer(HC_WORK_SITUATION_SMOKE, "SITUATION_SMOKE", 1);
        HCRegisterConsumer(HC_WORK_ADMIN_VISITOR, "ADMIN_VISITOR", 1);
        HCRegisterConsumer(HC_WORK_TACTICS_SCAN, "TACTICS_SCAN", 1);
        HCRegisterConsumer(HC_WORK_AI_TRADE_PRODUCER, "AI_TRADE_PRODUCER", 1);
        HCRegisterConsumer(HC_WORK_CONVOY_ROUTE, "CONVOY_ROUTE", 1);
        HCRegisterConsumer(HC_WORK_CONVOY_RUN, "CONVOY_RUN", 1);
        HCRegisterConsumer(HC_WORK_SEARCH_COVERAGE, "SEARCH_COVERAGE", 1);
        HCRegisterConsumer(HC_WORK_SEARCH_RETIREMENT, "SEARCH_RETIREMENT", 1);
        HCRegisterConsumer(HC_WORK_WILDLIFE, "WILDLIFE", 1);
        HCRegisterConsumer(HC_WORK_ZONE_GUARDS, "ZONE_GUARDS", 1);
        HCRegisterConsumer(HC_WORK_AI_ROUTE_CACHE, "AI_ROUTE_CACHE", 1);
        HCRegisterConsumer(HC_WORK_ADMIN_TELEPORT, "ADMIN_TELEPORT", 1);
        HCRegisterConsumer(HC_WORK_ADMIN_WORLD, "ADMIN_WORLD", 1);
        HCRegisterConsumer(HC_WORK_SIGNS_OF_LIFE, "SIGNS_OF_LIFE", 1);
        HCRegisterConsumer(HC_WORK_ECOLOGY_TOWN, "ECOLOGY_TOWN", 1);
        HCRegisterConsumer(HC_WORK_ECOLOGY_ANIMAL, "ECOLOGY_ANIMAL", 1);
        HCRegisterConsumer(HC_WORK_ECOLOGY_PATH, "ECOLOGY_PATH", 1);
        HCRegisterConsumer(HC_WORK_ECOLOGY_MIGRATION, "ECOLOGY_MIGRATION", 1);
        HCRegisterConsumer(HC_WORK_FORAGE, "FORAGE", 1);
        HCRegisterConsumer(HC_WORK_HORDE_REINFORCE, "HORDE_REINFORCE", 1);
        HCRegisterConsumer(HC_WORK_PICKERS, "PICKERS", 1);
        HCRegisterConsumer(HC_WORK_PICK_CARRY, "PICK_CARRY", 1);
        HCRegisterConsumer(HC_WORK_PICK_HOUSES, "PICK_HOUSES", 1);
        HCRegisterConsumer(HC_WORK_MISSION_BEACON, "MISSION_BEACON", 1);
        HCRegisterConsumer(HC_WORK_NAV_INF, "NAV_INF", 1);
        HCRegisterConsumer(HC_WORK_NAV_XAI, "NAV_XAI", 1);
    }

    static string HCConsumerName(int slot)
    {
        HCInitConsumers();
        return s_ConsumerNames.Get(slot);
    }

    static int HCConsumerWeight(int slot)
    {
        HCInitConsumers();
        return HCPerfConfig.HCGet().HCWeight(s_ConsumerNames.Get(slot), s_DefaultWeights.Get(slot));
    }

    protected ref HCUnitProfile m_Profile;
    void HCSetProfile(HCUnitProfile profile) { m_Profile = profile; }
    void HCCloseSpan() { if (m_Profile) { m_Profile.HCCloseSpan(); } }

    protected int m_Limit;
    protected int m_Used;
    protected int m_Items;
    // Shared-budget bookkeeping, allocated with the owner, never on a tick.
    protected bool m_Served[64];
    protected int m_Starved;
    // Perf-window figures, rolled once per tick by HCEndTick.
    protected int m_WindowUsedMax;
    protected int m_WindowStarved;
    protected int m_WindowTicks;
    protected int m_WindowIndex;
    protected float m_WindowElapsed;

    void HCReset(int limit)
    {
        HCCloseSpan();
        m_Limit = limit;
        if (m_Limit < 1) { m_Limit = 1; }
        m_Used = 0;
        m_Items = 0;
        for (int slot = 0; slot < HC_WORK_CONSUMERS; slot++) { m_Served[slot] = false; }
        m_Starved = 0;
    }

    bool HCTake(int cost)
    {
        HCCloseSpan();
        return HCTryTake(cost);
    }

    protected bool HCTryTake(int cost)
    {
        int units = cost;
        if (units < 1) { units = 1; }
        if (m_Items > 0 && m_Used + units > m_Limit) { return false; }
        m_Used = m_Used + units;
        m_Items = m_Items + 1;
        return true;
    }

    // Shared-budget request: HCTake, plus ONE forced item per consumer per tick when the pool is
    // exhausted (see the header). A forced item is charged, so HCUsed may exceed the limit by the
    // forced units. Invalid ids clamp to the first/last registered consumer.
    bool HCTakeFor(int consumer, int cost)
    {
        int slot = consumer;
        if (slot < 0) { slot = 0; }
        if (slot >= HC_WORK_CONSUMERS) { slot = HC_WORK_CONSUMERS - 1; }
        HCCloseSpan();
        int units = cost;
        if (units < 1) { units = 1; }
        if (m_Profile) { units = m_Profile.HCWeightedUnits(slot, units); }
        if (HCTryTake(units))
        {
            m_Served[slot] = true;
            if (m_Profile) { m_Profile.HCItem(slot, units, false); }
            return true;
        }
        if (m_Served[slot])
        {
            if (m_Profile) { m_Profile.HCRefused(slot); }
            return false;
        }
        m_Served[slot] = true;
        m_Starved = m_Starved + 1;
        m_Used = m_Used + units;
        m_Items = m_Items + 1;
        if (m_Profile) { m_Profile.HCItem(slot, units, true); }
        return true;
    }

    // Charge work that already happened (an item whose cost was only known afterwards).
    void HCCharge(int cost)
    {
        if (cost > 0)
        {
            m_Used = m_Used + cost;
            if (m_Profile) { m_Profile.HCCharge(cost); }
        }
    }

    // Issue #138 round 2: charge an item by the larger of its declared units and its MEASURED cost.
    // The caller measures (raw EnSystem.c:106 TickCount units) and passes ticksPerUnit; this class
    // still reads no clock. `taken` is what HCTake already charged for the item. A non-positive
    // measurement or divisor charges only the declared units (never a refund).
    void HCChargeMeasured(int declared, int measuredTicks, int ticksPerUnit, int taken)
    {
        int units = declared;
        if (ticksPerUnit > 0 && measuredTicks > 0)
        {
            int measured = measuredTicks / ticksPerUnit;
            if (measured > units) { units = measured; }
        }
        HCCharge(units - taken);
    }

    bool HCExhausted() { return m_Items > 0 && m_Used >= m_Limit; }
    int HCUsed() { return m_Used; }
    int HCLimit() { return m_Limit; }
    int HCItems() { return m_Items; }
    int HCStarved() { return m_Starved; }

    // End of one core tick: fold this tick into the perf window. True when the window is full
    // (the caller prints HCWindowReport once). windowSeconds matches HCPerfSampler's window.
    bool HCEndTick(float elapsed, int windowSeconds)
    {
        if (m_Used > m_WindowUsedMax) { m_WindowUsedMax = m_Used; }
        m_WindowStarved = m_WindowStarved + m_Starved;
        m_WindowTicks = m_WindowTicks + 1;
        if (elapsed > 0) { m_WindowElapsed = m_WindowElapsed + elapsed; }
        return m_WindowElapsed >= windowSeconds;
    }

    // Fields appended to a perf line: shared_used_max = most units one tick used in the window,
    // shared_starved = consumer ticks whose first request found the pool exhausted (served only by
    // the forced item).
    string HCWindowFields()
    {
        return " shared_used_max=" + m_WindowUsedMax.ToString() + " shared_starved=" + m_WindowStarved.ToString();
    }

    // The once-per-window line; rolls and clears the window. Log text only, runtime stays PENDING.
    string HCWindowReport()
    {
        m_WindowIndex = m_WindowIndex + 1;
        string report = "[HC TickWork] window=" + m_WindowIndex.ToString() + " ticks=" + m_WindowTicks.ToString();
        report = report + " limit=" + m_Limit.ToString() + HCWindowFields() + "; runtime=PENDING";
        HCWindowReset();
        return report;
    }

    void HCWindowReset()
    {
        m_WindowUsedMax = 0;
        m_WindowStarved = 0;
        m_WindowTicks = 0;
        m_WindowElapsed = 0;
    }
}

// Reuse the same validated counter conversion as every HCWorkBudget slice.
class HCStartupFrameBudget : HCWorkBudget
{
    float HCRemainingMs()
    {
        if (m_SliceTicksPerMs <= 0) { return 0; }
        return Math.Max(0, m_Deadline * 1000 - TickCount(m_SliceStart) / m_SliceTicksPerMs);
    }
    float HCMilliseconds(int ticks)
    {
        if (m_SliceTicksPerMs <= 0 || ticks < 0) { return 0; }
        return ticks / m_SliceTicksPerMs;
    }
}
