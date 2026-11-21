// #230: fixed consumer observer for the shared core budget only. Native TickCount:
// scripts-1.30.164289/1_Core/proto/EnSystem.c:106; same raw ticks as [HC Save].
// Task measurement convention: 100 ns/tick; preserve raw units for calibration.
// Spans end at the next budget request/refusal or module return. Setup before the
// first grant is excluded; trailing module work is included. Nested grants end
// the outer span (no stack). These are attribution estimates, never runtime proof.
// Floats hold window totals to avoid signed-int overflow; maxima remain raw int.
class HCUnitCost
{
    string Name;
    int Weight = 1;
    float Granted;
    float Used;
    float Starved;
    float Refused;
    float Ticks;
    int MaxTicks;
    void HCReset()
    {
        Granted = 0;
        Used = 0;
        Starved = 0;
        Refused = 0;
        Ticks = 0;
        MaxTicks = 0;
    }
}

class HCUnitProfile
{
    protected ref array<ref HCUnitCost> m_Costs = new array<ref HCUnitCost>;
    protected int m_OpenSlot = -1;
    protected int m_Start;

    void HCUnitProfile()
    {
        HCPerfConfig config = HCPerfConfig.HCGet();
        HCRegister("INFECTED", config.TickWeight_INFECTED);
        HCRegister("INTERIORS", config.TickWeight_INTERIORS);
        HCRegister("SEARCH_BIND", config.TickWeight_SEARCH_BIND);
        HCRegister("SEARCH_MAINT", config.TickWeight_SEARCH_MAINT);
        HCRegister("SEARCH_REFRESH", config.TickWeight_SEARCH_REFRESH);
        HCRegister("SEARCH_DETACHED", config.TickWeight_SEARCH_DETACHED);
        HCRegister("LOD_CLASSIFY", config.TickWeight_LOD_CLASSIFY);
        HCRegister("LOD_HERD", config.TickWeight_LOD_HERD);
        HCRegister("BASES", config.TickWeight_BASES);
        HCRegister("CONFLICT", config.TickWeight_CONFLICT);
        HCRegister("TRADE", config.TickWeight_TRADE);
        HCRegister("SITUATIONS", config.TickWeight_SITUATIONS);
        HCRegister("BASE_RAID", config.TickWeight_BASE_RAID);
        HCRegister("ROLES", config.TickWeight_ROLES);
        HCRegister("FORMATION", config.TickWeight_FORMATION);
        HCRegister("CARFIX", config.TickWeight_CARFIX);
        HCRegister("HEARTH", config.TickWeight_HEARTH);
        HCRegister("INCIDENTS", config.TickWeight_INCIDENTS);
        HCRegister("INCIDENT_RESPONSE", config.TickWeight_INCIDENT_RESPONSE);
        HCRegister("AI_RESPAWN", config.TickWeight_AI_RESPAWN);
        HCRegister("SEARCH_COMPACT", config.TickWeight_SEARCH_COMPACT);
        HCRegister("SHELTER", config.TickWeight_SHELTER);
        HCRegister("AI_SITES", config.TickWeight_AI_SITES);
        HCRegister("STORY_INDEX", config.TickWeight_STORY_INDEX);
        HCRegister("AI_ROUTES", config.TickWeight_AI_ROUTES);
        HCRegister("POLICE_BIND", config.TickWeight_POLICE_BIND);
        HCRegister("ROADS", config.TickWeight_ROADS);
        HCRegister("INFECTED_VARIETY", config.TickWeight_INFECTED_VARIETY);
        HCRegister("INFECTED_VARIETY_ROUTES", config.TickWeight_INFECTED_VARIETY_ROUTES);
        HCRegister("SITUATION_RUNTIME", config.TickWeight_SITUATION_RUNTIME);
        HCRegister("SITUATION_SMOKE", config.TickWeight_SITUATION_SMOKE);
        HCRegister("ADMIN_VISITOR", config.TickWeight_ADMIN_VISITOR);
        HCRegister("TACTICS_SCAN", config.TickWeight_TACTICS_SCAN);
        HCRegister("AI_TRADE_PRODUCER", config.TickWeight_AI_TRADE_PRODUCER);
        HCRegister("CONVOY_ROUTE", config.TickWeight_CONVOY_ROUTE);
        HCRegister("CONVOY_RUN", config.TickWeight_CONVOY_RUN);
        HCRegister("SEARCH_COVERAGE", config.TickWeight_SEARCH_COVERAGE);
        HCRegister("SEARCH_RETIREMENT", config.TickWeight_SEARCH_RETIREMENT);
        HCRegister("WILDLIFE", config.TickWeight_WILDLIFE);
        HCRegister("ZONE_GUARDS", config.TickWeight_ZONE_GUARDS);
        HCRegister("AI_ROUTE_CACHE", config.TickWeight_AI_ROUTE_CACHE);
    }

    protected void HCRegister(string label, int weight)
    {
        HCUnitCost entry = new HCUnitCost;
        entry.Name = label;
        entry.Weight = weight;
        m_Costs.Insert(entry);
    }

    int HCWeightedUnits(int slot, int units)
    {
        // Saturate before multiplication; malformed large callers cannot wrap.
        int weight = m_Costs.Get(slot).Weight;
        if (units > HCUnitBudget.HC_WORK_UNBOUNDED / weight) { return HCUnitBudget.HC_WORK_UNBOUNDED; }
        return units * weight;
    }

    void HCCloseSpan()
    {
        if (m_OpenSlot < 0) { return; }
        int ticks = TickCount(m_Start);
        HCUnitCost entry = m_Costs.Get(m_OpenSlot);
        if (ticks > 0)
        {
            entry.Ticks = entry.Ticks + ticks;
            if (ticks > entry.MaxTicks) { entry.MaxTicks = ticks; }
        }
        m_OpenSlot = -1;
    }

    void HCItem(int slot, int units, bool forced)
    {
        HCUnitCost entry = m_Costs.Get(slot);
        // A grant is consumed on admission; Used additionally includes explicit post-hoc charges.
        entry.Granted = entry.Granted + units;
        entry.Used = entry.Used + units;
        if (forced) { entry.Starved = entry.Starved + 1; }
        m_OpenSlot = slot;
        m_Start = TickCount(0);
    }

    void HCRefused(int slot)
    {
        HCUnitCost entry = m_Costs.Get(slot);
        entry.Refused = entry.Refused + 1;
    }

    void HCCharge(int units)
    {
        if (m_OpenSlot < 0) { return; }
        HCUnitCost entry = m_Costs.Get(m_OpenSlot);
        entry.Used = entry.Used + units;
    }

    void HCReset()
    {
        m_OpenSlot = -1;
        foreach (HCUnitCost entry : m_Costs) { entry.HCReset(); }
    }

    // Hard cap: HC_WORK_CONSUMERS compact lines/window, only ids with admitted work. No hot-path strings.
    void HCPrintWindow(int windowIndex)
    {
        HCCloseSpan();
        foreach (HCUnitCost entry : m_Costs)
        {
            if (entry.Granted <= 0) { continue; }
            float perUnit = entry.Ticks / entry.Used;
            string line = "[HC TickCost] window=" + windowIndex.ToString() + " consumer=" + entry.Name;
            line = line + " weight=" + entry.Weight.ToString() + " granted=" + entry.Granted.ToString() + " used=" + entry.Used.ToString();
            line = line + " starved=" + entry.Starved.ToString() + " refused=" + entry.Refused.ToString();
            line = line + " ticks_sum=" + entry.Ticks.ToString() + " ticks_max=" + entry.MaxTicks.ToString();
            line = line + " per_unit_ticks=" + perUnit.ToString() + " runtime=PENDING";
            Print("" + line);
        }
        HCReset();
    }
}
