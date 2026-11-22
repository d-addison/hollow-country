// The guarded API refuses init-path counts at runtime, so calling it from init is safe.
class HCModuleReadiness
{
    static bool HCUseGuarded(string module, string feature, Class evidence)
    {
        if (!evidence) { return false; }
        HCUse(module, feature);
        return true;
    }
    static void HCUse(string module, string feature) {}
}

class HCProbeModule : HCModule
{
    override void OnStart(HCSettings settings)
    {
        HCModuleReadiness.HCUseGuarded("Probe", "guarded", this);
    }
}
