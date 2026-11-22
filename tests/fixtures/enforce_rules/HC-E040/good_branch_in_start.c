// A count behind a branch, loop or short-circuit depends on an outcome.
class HCProbeModule : HCModule
{
    protected int m_Restored;

    override void OnStart(HCSettings settings)
    {
        if (m_Restored > 0)
        {
            HCModuleReadiness.HCUse("Probe", "restored_rows");
        }
        if (m_Restored > 1) HCModuleReadiness.HCUse("Probe", "restored_many");
        foreach (int row : m_Rows)
        {
            HCModuleReadiness.HCUse("Probe", "row_loaded");
        }
        bool counted = m_Restored > 2 && Count();
    }

    protected bool Count()
    {
        HCModuleReadiness.HCUse("Probe", "short_circuit");
        return true;
    }
    protected ref array<int> m_Rows;
}
