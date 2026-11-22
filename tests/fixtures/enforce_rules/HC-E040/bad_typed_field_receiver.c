// The counter sits behind a call on a typed member (m_Ledger) made from OnStart.
class HCProbeLedger
{
    void Record()
    {
        HCModuleReadiness.HCUse("Probe", "ledger_record");
    }
}

class HCProbeModule : HCModule
{
    protected ref HCProbeLedger m_Ledger = new HCProbeLedger();

    override void OnStart(HCSettings settings)
    {
        m_Ledger.Record();
    }
}
