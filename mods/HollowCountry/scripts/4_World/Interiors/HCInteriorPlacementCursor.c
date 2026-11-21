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
    protected bool m_Resolved;
    protected ref HCWorkBudget m_Budget = new HCPerfSlices("Interiors");

    // One deadline/count for the outer furnishing loop, never one per slot.
    void HCBeginTick() { m_Budget.HCReset(HCPerfConfig.HCGet().InteriorStepsPerTick, Math.Min(HCPerfConfig.HCGet().SliceMs, 2)); }

    bool HCComplete() { return m_Complete; }
    int HCLastCost() { return m_LastCost; }
    bool HCYield() { return m_Yield; }

    void HCTick(HCInteriorsModule module, HCSettings settings, array<Object> placed)
    {
        int visitStart = TickCount(0);
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
            m_Resolved = false;
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
            m_Resolved = false;
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
            if (!m_Resolve)
            {
                m_Resolve = new HCInteriorResolveCursor;
                // Separate row/cursor preparation from native query cost.
                // Build 131's CementWorks query-labelled 33 ms item had only
                // 0.5 ms inside HCStep: its remaining cost was not a query.
                HCInteriorTemplatePlacement.HCRecordResolve(m_Current, 0, "prepare", TickCount(visitStart));
                m_Yield = true;
                return;
            }
            if (!m_Resolved)
            {
                m_Resolved = m_Resolve.HCStep(m_Current);
                // A completed candidate loop gets no prop inspection/creation
                // in the same grant. The resolved house and slot stay pinned.
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
        m_Resolved = false;
        m_Slot = m_Slot + 1;
        if (m_Slot >= m_Current.Props.Count()) { m_Current = null; }
        m_Budget.HCDeferred("Interiors", rows.Count() - m_Next + m_DeferredRemaining);
    }
}

// One resolve chunk per admitted HCWorkBudget visit. Measured-heavy cache misses cover the
// original 0.75 m circle with four overlapping 0.531 m circles, one per tick.
// Each circle covers a quadrant's 0.75 x 0.75 m bounding square (half diagonal
// sqrt(2)*0.375). Merge drops overlap and origins outside the original circle;
// exact 3D/class/ambiguity/tilt checks below still decide placement. Native
// Game.c:923 documents circle enumeration; origin membership/binding equivalence
// and the <=16 ms tick target require a native run, especially cold models.
// Query merging and filtering visit <=8 candidates per tick. No house is
// claimed and no cache snapshot is published until all query work completes.
class HCInteriorResolveCursor
{
    static const int CANDIDATES_PER_STEP = 8;
    protected ref HCInteriorResolveEntry m_Entry;
    protected int m_Next;
    protected int m_QueryTile;
    protected int m_QueryNext;
    protected bool m_QueryMerging;
    protected bool m_QueryComplete;
    protected ref array<Object> m_QueryObjects = new array<Object>;
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
            if (m_Entry) { m_QueryComplete = true; }
            else
            {
                if (!HCQuerySliced(row.BuildingClass))
                {
                    m_Entry = HCInteriorTemplatePlacement.HCResolveObjects(position);
                    m_QueryComplete = true;
                    HCInteriorTemplatePlacement.HCRecordResolve(row, m_Entry.QuerySize, "query", TickCount(mark));
                    return false;
                }
                m_Entry = new HCInteriorResolveEntry;
                m_Entry.Position = position;
            }
        }
        if (!m_QueryComplete)
        {
            string phase = "query" + m_QueryTile.ToString();
            if (m_QueryMerging) { phase = "merge"; }
            HCQueryStep(position);
            int querySize = m_Entry.QuerySize;
            if (phase != "merge") { querySize = m_QueryObjects.Count(); }
            HCInteriorTemplatePlacement.HCRecordResolve(row, querySize, phase, TickCount(mark));
            return false;
        }
        bool done = HCFilter(position, row.BuildingClass);
        HCInteriorTemplatePlacement.HCRecordResolve(row, m_Entry.QuerySize, "filter", TickCount(mark));
        return done;
    }

    // Build 131's five heaviest query-labelled classes. Avoid multiplying
    // startup latency for the remaining catalog's already-cheap queries.
    protected bool HCQuerySliced(string buildingClass)
    {
        // One comparison per statement: a continued "||" line fails to compile.
        if (buildingClass == "Land_CementWorks_ExpeditionA") { return true; }
        if (buildingClass == "Land_Tenement_Small") { return true; }
        if (buildingClass == "Land_Mil_Barracks3") { return true; }
        if (buildingClass == "Land_Mil_Barracks4") { return true; }
        return buildingClass == "Land_House_2B01";
    }

    protected void HCQueryStep(vector position)
    {
        if (!m_QueryMerging)
        {
            int column = m_QueryTile % 2;
            int line = m_QueryTile / 2;
            vector centre = position + Vector(column * 0.75 - 0.375, 0, line * 0.75 - 0.375);
            // Native scripts-1.30.164289: 3_Game/Global/Game.c:923.
            // Never enumerate proxy cargo. Rounded outward to cover seams.
            GetGame().GetObjectsAtPosition(centre, 0.531, m_QueryObjects, null);
            m_QueryNext = 0;
            m_QueryMerging = true;
            return;
        }
        int stop = Math.Min(m_QueryNext + CANDIDATES_PER_STEP, m_QueryObjects.Count());
        while (m_QueryNext < stop)
        {
            Object candidate = m_QueryObjects[m_QueryNext];
            m_QueryNext = m_QueryNext + 1;
            if (!candidate) { continue; }
            vector origin = candidate.GetPosition();
            float dx = origin[0] - position[0];
            float dz = origin[2] - position[2];
            // Each origin belongs to exactly one quadrant, including seams.
            // That quadrant's query circle covers its entire bounding square.
            // This removes overlapping results without a nested object scan.
            int ownerTile = 0;
            if (dx >= 0) { ownerTile = 1; }
            if (dz >= 0) { ownerTile = ownerTile + 2; }
            // Retain nonmatching classes for the existing 256-object refusal.
            if (ownerTile != m_QueryTile || dx * dx + dz * dz > 0.5625) { continue; }
            m_Entry.QuerySize = m_Entry.QuerySize + 1;
            if (m_Entry.QuerySize > 256)
            {
                m_Entry.Objects.Clear();
                HCQueryFinish();
                return;
            }
            m_Entry.Objects.Insert(candidate);
        }
        if (m_QueryNext < m_QueryObjects.Count()) { return; }
        m_QueryObjects.Clear();
        m_QueryMerging = false;
        m_QueryTile = m_QueryTile + 1;
        if (m_QueryTile == 4) { HCQueryFinish(); }
    }

    protected void HCQueryFinish()
    {
        m_QueryObjects.Clear();
        m_QueryComplete = true;
        HCInteriorTemplatePlacement.HCStoreResolveObjects(m_Entry);
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
