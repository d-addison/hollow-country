// The counter is on the gameplay path only; init never reaches it.
class HCProbeModule : HCModule
{
    override void OnStart(HCSettings settings)
    {
        m_Started = true;
    }

    void OnActionDone(PlayerBase player)
    {
        HCModuleReadiness.HCUse("Probe", "action_done");
    }
    protected bool m_Started;
}
