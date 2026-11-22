// A constructor counts a use.
class HCProbeService
{
    void HCProbeService()
    {
        HCModuleReadiness.HCUse("Probe", "service_created");
    }
}
