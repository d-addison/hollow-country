// An early return about the caller's own inputs is not evidence of use: still flagged.
class HCProbeModule : HCModule
{
    protected bool m_Enabled;

    override void OnStart(HCSettings settings)
    {
        if (!m_Enabled) { return; }
        HCModuleReadiness.HCUse("Probe", "enabled_start");
    }
}
