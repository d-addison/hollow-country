// #230: fixed consumer observer for the shared core budget only. Native TickCount:
// scripts-1.30.164289/1_Core/proto/EnSystem.c:106; same raw ticks as [HC Save].
// Counter units are undocumented; preserve raw units and use the shared calibration.
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
    bool SlowSpan;
    void HCReset()
    {
        Granted = 0;
        Used = 0;
        Starved = 0;
        Refused = 0;
        Ticks = 0;
        MaxTicks = 0;
        SlowSpan = false;
    }
}

class HCUnitProfile
{
    protected ref array<ref HCUnitCost> m_Costs = new array<ref HCUnitCost>;
    protected ref HCUnitCost m_Total = new HCUnitCost;
    protected int m_OpenSlot = -1;
    protected int m_Start;

    void HCUnitProfile()
    {
        for (int slot = 0; slot < HCUnitBudget.HC_WORK_CONSUMERS; slot++)
        {
            HCUnitCost entry = new HCUnitCost;
            entry.Name = HCUnitBudget.HCConsumerName(slot);
            entry.Weight = HCUnitBudget.HCConsumerWeight(slot);
            m_Costs.Insert(entry);
        }
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
        float rate = HCWorkBudget.HCTicksPerMs();
        if (rate <= 0 || ticks < 0 || ticks > rate * 5) { entry.SlowSpan = true; }
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

    // Summary each minute, routine top three every third window. Always emit
    // every >5 ms span; when calibration is invalid preserve all raw evidence.
    // Consumer rows retain the parser contract. A separate TickCostTotal tag
    // avoids inventing a consumer in the R1 starvation/weight report.
    void HCPrintWindow(int windowIndex)
    {
        HCCloseSpan();
        HCUnitCost total = m_Total;
        total.HCReset();
        total.Name = "ALL";
        int top[3];
        top[0] = -1;
        top[1] = -1;
        top[2] = -1;
        for (int slot = 0; slot < m_Costs.Count(); slot++)
        {
            HCUnitCost entry = m_Costs.Get(slot);
            total.Granted += entry.Granted;
            total.Used += entry.Used;
            total.Starved += entry.Starved;
            total.Refused += entry.Refused;
            total.Ticks += entry.Ticks;
            total.MaxTicks = Math.Max(total.MaxTicks, entry.MaxTicks);
            if (entry.Granted <= 0) { continue; }
            for (int rank = 0; rank < 3; rank++)
            {
                if (top[rank] >= 0 && entry.MaxTicks <= m_Costs.Get(top[rank]).MaxTicks) { continue; }
                for (int shift = 2; shift > rank; shift--) { top[shift] = top[shift - 1]; }
                top[rank] = slot;
                break;
            }
        }
        HCPrintCost(windowIndex, total, "[HC TickCostTotal]");
        float ticksPerMs = HCWorkBudget.HCTicksPerMs();
        for (int emit = 0; emit < m_Costs.Count(); emit++)
        {
            HCUnitCost candidate = m_Costs.Get(emit);
            if (candidate.Granted <= 0) { continue; }
            bool routine = windowIndex % 3 == 0 && (emit == top[0] || emit == top[1] || emit == top[2]);
            if (routine || candidate.SlowSpan || ticksPerMs <= 0 || candidate.MaxTicks > ticksPerMs * 5) { HCPrintCost(windowIndex, candidate); }
        }
        HCReset();
    }

    protected void HCPrintCost(int windowIndex, HCUnitCost entry, string tag = "[HC TickCost]")
    {
        float perUnit = 0;
        if (entry.Used > 0) { perUnit = entry.Ticks / entry.Used; }
        string line = tag + " window=" + windowIndex.ToString() + " consumer=" + entry.Name;
        line = line + " weight=" + entry.Weight.ToString() + " granted=" + entry.Granted.ToString() + " used=" + entry.Used.ToString();
        line = line + " starved=" + entry.Starved.ToString() + " refused=" + entry.Refused.ToString();
        line = line + " ticks_sum=" + entry.Ticks.ToString() + " ticks_max=" + entry.MaxTicks.ToString();
        line = line + " per_unit_ticks=" + perUnit.ToString() + " runtime=PENDING";
        Print("" + line);
    }
}
