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
class HCUnitBudget
{
    protected int m_Limit;
    protected int m_Used;
    protected int m_Items;

    void HCReset(int limit)
    {
        m_Limit = limit;
        if (m_Limit < 1) { m_Limit = 1; }
        m_Used = 0;
        m_Items = 0;
    }

    bool HCTake(int cost)
    {
        int units = cost;
        if (units < 1) { units = 1; }
        if (m_Items > 0 && m_Used + units > m_Limit) { return false; }
        m_Used = m_Used + units;
        m_Items = m_Items + 1;
        return true;
    }

    // Charge work that already happened (an item whose cost was only known afterwards).
    void HCCharge(int cost)
    {
        if (cost > 0) { m_Used = m_Used + cost; }
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
}
