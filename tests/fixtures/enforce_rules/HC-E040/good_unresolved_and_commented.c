// Calls on a receiver whose type is unknown are not followed, a same-named method on
// another class is not the callee, and comments or strings are not code.
class HCProbeOther
{
    void Record()
    {
        HCModuleReadiness.HCUse("Probe", "other_record");
    }
}

class HCProbeModule : HCModule
{
    override void OnStart(HCSettings settings)
    {
        // HCModuleReadiness.HCUse("Probe", "commented");
        string text = "HCModuleReadiness.HCUse(a, b);";
        m_Unknown.Record();
        Print(text);
    }
}
