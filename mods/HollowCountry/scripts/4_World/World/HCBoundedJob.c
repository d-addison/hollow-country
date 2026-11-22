// Reusable bounded job: one walk over N items, resumed across ticks within a shared HCWorkBudget.
//
// A module that must scan a collection that can grow with the world (nearest house, nearest
// site, bounds of a placed scene) derives a job, answers HCItemCount() and HCStepItem(index),
// and calls HCRun(budget) once per tick. The cursor lives in the job; the budget is the
// caller's HCWorkBudget (HCReset before HCRun), so the walk stops at the unit cap or the
// deadline and carries on at the same cursor on the next call.
//
// Contract
//   - HCBegin(owner) arms the job and rewinds the cursor. A job is reusable: HCBegin again
//     after DONE, CANCELLED or FAILED. Begin does no per-item work. The owner must derive from
//     Managed (only Managed objects null their weak references when freed); a plain class
//     owner, or a static module, passes null and the owner's own ref field then bounds the job.
//   - HCRun(budget) returns true while the job still has items (call it again next tick) and
//     false once it reached a terminal state: DONE, CANCELLED or FAILED. It is a no-op on a
//     job that is not RUNNING. The first unit of a freshly reset budget is always granted
//     (HCWorkBudget.HCContinue), so a job cannot starve under a tight deadline.
//   - HCStepItem(index) does the work for one item and answers ITEM_ADVANCE (next item),
//     ITEM_STAY (retry this item on the next call; the run yields, e.g. a precondition is
//     not met yet), ITEM_DONE (the answer is complete, stop early) or ITEM_FAIL.
//   - HCItemCount() is read on every step, so a collection that shrinks or grows while the job
//     runs is safe: the cursor is clamped to the live count and the job finishes when it
//     passes the end.
//   - HCCancel() stops the job without a result. The owner is held by a weak reference (a
//     non-ref Managed member), so a Managed owner that is freed between ticks cancels the job
//     on its next HCRun and the job never touches a freed owner. A job begun with a null
//     owner is never cancelled by owner loss. Collections the job walks are held the same
//     way, as weak pointers that the derived job null-checks in HCItemCount().
//   - HCProgress* reports the cursor, the item count and a percentage for logs and status.
//   - No allocation per item: HCStepItem works on fields of the derived job.
//
// Not for work that needs a result in the same call. A caller that must answer synchronously
// (a gate that returns bool) keeps its own bound and capped collection instead.
class HCBoundedJob : Managed
{
    static const int STATE_IDLE = 0;
    static const int STATE_RUNNING = 1;
    static const int STATE_DONE = 2;
    static const int STATE_CANCELLED = 3;
    static const int STATE_FAILED = 4;

    static const int ITEM_ADVANCE = 0;
    static const int ITEM_STAY = 1;
    static const int ITEM_DONE = 2;
    static const int ITEM_FAIL = 3;

    protected int m_State;
    protected int m_Cursor;
    protected int m_Processed;
    protected int m_Slices;
    // Weak: the job never keeps its owner alive and sees null once the owner is freed.
    protected Managed m_Owner;
    protected bool m_OwnerBound;

    // Items in the collection right now. Read on every step.
    int HCItemCount() { return 0; }

    // Work for one item. Return one of the ITEM_ constants.
    int HCStepItem(int index) { return ITEM_ADVANCE; }

    // Module name for the shared "perf budget ... deferred" line; "" keeps the job silent.
    string HCJobModule() { return ""; }

    // Called once when the job reaches DONE, CANCELLED or FAILED.
    void HCOnFinish(int state) { }

    // Called by HCClear: a derived job drops its pointers to the collections it walked.
    void HCOnClear() { }

    void HCBegin(Managed owner)
    {
        m_Owner = owner;
        m_OwnerBound = owner != null;
        m_Cursor = 0;
        m_Processed = 0;
        m_Slices = 0;
        m_State = STATE_RUNNING;
    }

    // Back to IDLE with no result and no callback (owner cleanup, module stop).
    void HCClear()
    {
        m_State = STATE_IDLE;
        m_Cursor = 0;
        m_Processed = 0;
        m_Slices = 0;
        m_Owner = null;
        m_OwnerBound = false;
        HCOnClear();
    }

    void HCCancel()
    {
        if (m_State != STATE_RUNNING) { return; }
        HCFinish(STATE_CANCELLED);
    }

    protected void HCFinish(int state)
    {
        m_State = state;
        HCOnFinish(state);
    }

    // True while more ticks are needed.
    bool HCRun(HCWorkBudget budget)
    {
        if (m_State != STATE_RUNNING) { return false; }
        if (m_OwnerBound && !m_Owner)
        {
            HCFinish(STATE_CANCELLED);
            return false;
        }
        if (!budget)
        {
            HCFinish(STATE_FAILED);
            return false;
        }
        m_Slices++;
        while (true)
        {
            if (m_Cursor >= HCItemCount())
            {
                HCFinish(STATE_DONE);
                return false;
            }
            if (!budget.HCContinue())
            {
                string module = HCJobModule();
                if (module != "") { budget.HCDeferred(module, HCItemCount() - m_Cursor); }
                return true;
            }
            int verdict = HCStepItem(m_Cursor);
            if (verdict == ITEM_STAY) { return true; }
            m_Processed++;
            if (verdict == ITEM_FAIL)
            {
                HCFinish(STATE_FAILED);
                return false;
            }
            if (verdict == ITEM_DONE)
            {
                HCFinish(STATE_DONE);
                return false;
            }
            m_Cursor++;
        }
        return true;
    }

    int HCState() { return m_State; }
    bool HCRunning() { return m_State == STATE_RUNNING; }
    bool HCDone() { return m_State == STATE_DONE; }
    bool HCCancelled() { return m_State == STATE_CANCELLED; }
    bool HCFailed() { return m_State == STATE_FAILED; }
    int HCCursor() { return m_Cursor; }
    int HCProcessed() { return m_Processed; }
    int HCSlices() { return m_Slices; }

    // 0..100 of the items currently counted; 100 once DONE.
    int HCProgressPercent()
    {
        if (m_State == STATE_DONE) { return 100; }
        int total = HCItemCount();
        if (total < 1) { return 0; }
        return Math.Clamp(m_Cursor * 100 / total, 0, 100);
    }
}
