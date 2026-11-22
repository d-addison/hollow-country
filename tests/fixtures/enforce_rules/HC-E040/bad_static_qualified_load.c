// Load code calls a static helper of another class; the helper counts.
class HCProbeCompat
{
    static void Mark()
    {
        HCModuleReadiness.HCUse("Probe", "restored");
    }
}

class HCProbeStore
{
    void LoadAll()
    {
        HCProbeCompat.Mark();
    }
}
