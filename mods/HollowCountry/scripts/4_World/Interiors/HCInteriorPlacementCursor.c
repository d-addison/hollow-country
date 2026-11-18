// W5-PERF-1. <=1 slot per HCTick call (the module runs <=16 calls/4 ms per tick); cursor advances only after an attempted slot or
// deliberate refusal. Deferred rows retain catalog references (<=1500), never
// re-resolve/claim a completed house. No new inventory or persistence state.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380/389/407
// Count/Set/Insert; EnDebug.c:96 Print; EnConvert.c:30 int.ToString.
// Native placement/time calls are owned by HCInteriorTemplatePlacement and
// World/HCWorkBudget.c, with their installed signatures cited there.
class HCInteriorPlacementCursor
{
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
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;

    bool HCComplete() { return m_Complete; }

    void HCTick(HCInteriorsModule module, HCSettings settings, array<Object> placed)
    {
        if (m_Complete || !HCInteriorTemplates.Loaded()) { return; }
        m_Budget.HCReset(1);
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
            int beforeCount = placed.Count();
            if (!HCInteriorTemplatePlacement.HCPlaceRowSlice(module, m_Current, settings, placed, m_Slot, 1, m_Slot, m_HousePlaced))
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
        m_Slot = m_Slot + 1;
        if (m_Slot >= m_Current.Props.Count()) { m_Current = null; }
        m_Budget.HCDeferred("Interiors", rows.Count() - m_Next + m_DeferredRemaining);
    }
}
