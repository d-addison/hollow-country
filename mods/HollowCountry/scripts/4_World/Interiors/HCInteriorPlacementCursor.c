// W5-PERF-1. <=1 slot per HCTick call (the module runs HCTick calls until its shared HCUnitBudget
// is spent, issue #138: HCLastCost() reports SLOT_UNITS after a creation attempt, else CHEAP_UNITS); cursor advances only after an attempted slot or
// deliberate refusal. Deferred rows retain catalog references (<=1500), never
// re-resolve/claim a completed house. No new inventory or persistence state.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380/389/407
// Count/Set/Insert; EnDebug.c:96 Print; EnConvert.c:30 int.ToString.
// Native placement/time calls are owned by HCInteriorTemplatePlacement and
// World/HCWorkBudget.c, with their installed signatures cited there.
class HCInteriorPlacementCursor
{
    // Work units charged to the module's HCUnitBudget per HCTick call (issue #138). A slot that
    // reaches the creation path (Resolve + spawn + collision checks) is the measured burst source.
    static const int CHEAP_UNITS = 1;
    static const int SLOT_UNITS = 8;
    protected int m_LastCost = 1;
    protected bool m_Yield;
    protected int m_Next;
    protected int m_Slot;
    protected int m_HousePlaced;
    protected int m_DeferredNext;
    protected int m_DeferredSlot;
    protected int m_DeferredRemaining;
    protected bool m_FromDeferred;
    protected ref array<ref HCInteriorFurnishRow> m_Deferred = new array<ref HCInteriorFurnishRow>;
    protected HCInteriorFurnishRow m_Current;
    protected bool m_Complete;
    protected ref HCInteriorResolveCursor m_Resolve;
    protected ref HCWorkBudget m_Budget = new HCPerfSlices("Interiors");

    // One deadline/count for the outer furnishing loop, never one per slot.
    void HCBeginTick() { m_Budget.HCReset(HCPerfConfig.HCGet().InteriorStepsPerTick); }

    bool HCComplete() { return m_Complete; }
    int HCLastCost() { return m_LastCost; }
    bool HCYield() { return m_Yield; }

    void HCTick(HCInteriorsModule module, HCSettings settings, array<Object> placed)
    {
        m_LastCost = CHEAP_UNITS;
        m_Yield = false;
        if (m_Complete || !HCInteriorTemplates.Loaded()) { return; }
        if (!m_Budget.HCContinue()) { m_Budget.HCDeferred("Interiors", 1); return; }
        array<ref HCInteriorFurnishRow> rows = HCInteriorTemplates.FurnishRows();
        if (!m_Current)
        {
            if (m_Next < rows.Count())
            {
                m_FromDeferred = false;
                m_Current = rows[m_Next];
                m_Next = m_Next + 1;
            }
            else
            {
                if (m_DeferredRemaining > 0)
                {
                    if (m_DeferredNext >= m_Deferred.Count()) { m_DeferredNext = 0; }
                    m_DeferredSlot = m_DeferredNext;
                    m_DeferredNext = m_DeferredNext + 1;
                    m_Current = m_Deferred[m_DeferredSlot];
                    m_FromDeferred = true;
                    // Tombstones avoid ordered-array shifts and swap/remove
                    // starvation when several occupied rows keep deferring.
                    if (!m_Current) { return; }
                }
            }
            m_Resolve = null;
            m_Slot = 0;
            m_HousePlaced = 0;
        }
        if (!m_Current)
        {
            m_Complete = true;
            Print("[HC Interiors] templates placement complete props=" + placed.Count().ToString() + "; native acceptance pending");
            return;
        }
        // Recheck proximity on EVERY continuation; a joining player must never
        // see a subsequent furnishing appear in the same house.
        if (HCInteriorTemplatePlacement.PlayersNearRow(m_Current, HCPerfPlayers.HCGet()))
        {
            // A player can hold a partially filtered row for many ticks.
            // Restart live candidate checks after that hold; keep the same
            // cached native snapshot, as before the staged resolver.
            m_Resolve = null;
            if (m_Slot == 0)
            {
                if (!m_FromDeferred)
                {
                    m_Deferred.Insert(m_Current);
                    m_DeferredRemaining = m_DeferredRemaining + 1;
                }
                m_Current = null;
            }
            m_Budget.HCDeferred("Interiors", rows.Count() - m_Next + m_DeferredRemaining + 1);
            return;
        }
        if (m_FromDeferred)
        {
            m_Deferred.Set(m_DeferredSlot, null);
            m_DeferredRemaining = m_DeferredRemaining - 1;
            m_FromDeferred = false;
        }
        if (HCInteriorRules.PlacementAdmitted())
        {
            m_LastCost = SLOT_UNITS;
            // The outer shared HCWorkBudget admits ONE resolve chunk; keep
            // the candidate index across uninterrupted module ticks.
            if (!m_Resolve) { m_Resolve = new HCInteriorResolveCursor; }
            if (!m_Resolve.HCStep(m_Current))
            {
                m_Yield = true;
                return;
            }
            int beforeCount = placed.Count();
            if (!HCInteriorTemplatePlacement.HCPlaceRowSlice(module, m_Current, settings, placed, m_Slot, 1, m_Slot, m_HousePlaced, m_Resolve))
            {
                m_Current = null;
                return;
            }
            m_HousePlaced = m_HousePlaced + placed.Count() - beforeCount;
        }
        else
        {
            HCInteriorTemplatePlacement.CountRefusal("acceptance_pending", m_Current.Props.Count());
            m_Current = null;
            return;
        }
        m_Resolve = null;
        m_Slot = m_Slot + 1;
        if (m_Slot >= m_Current.Props.Count()) { m_Current = null; }
        m_Budget.HCDeferred("Interiors", rows.Count() - m_Next + m_DeferredRemaining);
    }
}

// One resolve chunk per admitted HCWorkBudget visit. A cache miss runs only
// the object query and always yields; cache hits avoid that extra tick. The
// original <=256-object snapshot is filtered in <=8-candidate chunks instead
// of an indivisible foreach. No house is claimed until resolution completes.
class HCInteriorResolveCursor
{
    static const int CANDIDATES_PER_STEP = 8;
    protected ref HCInteriorResolveEntry m_Entry;
    protected int m_Next;
    protected Object m_Found;
    protected string m_Reason = "unresolved";
    protected bool m_Complete;

    Object HCHouse() { return m_Found; }
    string HCReason() { return m_Reason; }
    int HCQuerySize() { return m_Entry.QuerySize; }

    bool HCStep(HCInteriorFurnishRow row)
    {
        if (m_Complete) { return true; }
        int mark = TickCount(0);
        vector position = HCInteriorTemplates.AsVector(row.Position);
        if (!m_Entry)
        {
            m_Entry = HCInteriorTemplatePlacement.HCFindResolveObjects(position);
            if (!m_Entry)
            {
                m_Entry = HCInteriorTemplatePlacement.HCResolveObjects(position);
                HCInteriorTemplatePlacement.HCRecordResolve(row, m_Entry.QuerySize, "query", TickCount(mark));
                return false;
            }
        }
        bool done = HCFilter(position, row.BuildingClass);
        HCInteriorTemplatePlacement.HCRecordResolve(row, m_Entry.QuerySize, "filter", TickCount(mark));
        return done;
    }

    protected bool HCFilter(vector position, string buildingClass)
    {
        if (m_Entry.QuerySize > 256)
        {
            m_Reason = "query_cap";
            m_Complete = true;
            return true;
        }
        int stop = Math.Min(m_Next + CANDIDATES_PER_STEP, m_Entry.Objects.Count());
        while (m_Next < stop)
        {
            Object candidate = m_Entry.Objects[m_Next];
            m_Next = m_Next + 1;
            if (!candidate || candidate.GetType() != buildingClass || vector.DistanceSq(position, candidate.GetPosition()) > 0.5625) { continue; }
            if (m_Found)
            {
                m_Found = null;
                m_Reason = "ambiguous";
                m_Complete = true;
                return true;
            }
            m_Found = candidate;
        }
        if (m_Next < m_Entry.Objects.Count()) { return false; }
        m_Complete = true;
        if (!m_Found) { return true; }
        vector orientation = m_Found.GetOrientation();
        if (!HCInteriorRules.SaneVector(orientation, 360) || !HCInteriorRules.TiltAcceptable(orientation, HCInteriorRules.MAX_HOUSE_TILT_DEGREES))
        {
            m_Found = null;
            m_Reason = "tilted";
            return true;
        }
        m_Reason = "";
        return true;
    }
}
