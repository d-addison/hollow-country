// HC-29 routine diagnostic checkpoint, scheduled by the existing HCSaveScheduler.
// Registration/unregistration belongs to HCEcologyRuntimeModule integration.
// N1: 1_Core/proto/EnSystem.c:106 TickCount; EnDebug.c:96 Print.
// Each store stage uses the existing verified
// intent/overwrite/readback/delete protocol. No asynchronous IO/rename/fsync API.
// A six-scalar snapshot (<=2048 encoded bytes) never contains entity handles.
class HCEcologySaveJob : HCSaveJob
{
    protected HCEcologyRuntime m_Owner;
    protected HCEcologyRuntimeStore m_Store;
    protected ref HCEcologyCheckpoint m_Snapshot;
    protected bool m_Failed;

    override string HCName() { return "Ecology"; }
    bool HCFailed() { return m_Failed; }

    void HCBind(HCEcologyRuntime owner, HCEcologyRuntimeStore store)
    {
        m_Owner = owner;
        m_Store = store;
    }

    void HCDetach()
    {
        m_Owner = null;
        m_Store = null;
        m_Snapshot = null;
        this.HCDirty = false;
        this.HCInFlight = false;
    }

    override int HCStep()
    {
        if (m_Failed || !m_Owner || !m_Store) { return STEP_FAILED; }
        int started = TickCount(0);
        int result = HCAdvance();
        m_Owner.HCRecordSaveTicks(TickCount(started));
        if (result == STEP_FAILED)
        {
            m_Failed = true;
            this.HCDirty = false;
            this.HCInFlight = false;
            Print("[HC Plan] HC-29 state=refused reason=save_continuation visited=0 deferred=0 save_phase=-1 elapsed_us=-1; runtime=PENDING");
        }
        return result;
    }

    int HCAdvance()
    {
        if (!m_Snapshot)
        {
            m_Snapshot = m_Owner.HCSnapshot();
            if (!m_Snapshot) { return STEP_DONE; }
            if (!m_Store.HCBeginSave(m_Snapshot)) { return STEP_FAILED; }
            this.HCInFlight = true;
            return STEP_MORE;
        }
        int result = m_Store.HCStepSave();
        if (result == STEP_DONE)
        {
            m_Owner.HCSaved(m_Snapshot);
            m_Snapshot = null;
            this.HCInFlight = false;
        }
        return result;
    }
}
