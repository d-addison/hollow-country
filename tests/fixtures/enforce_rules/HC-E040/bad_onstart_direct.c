// A module counts a feature use straight from OnStart: nothing was used yet.
class HCProbeModule : HCModule
{
    override void OnStart(HCSettings settings)
    {
        m_Started = true;
        HCModuleReadiness.HCUse("Probe", "probe_ready");
    }
    protected bool m_Started;
}
