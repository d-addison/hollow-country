// Entity init counts through a helper that takes a typed parameter receiver.
class HCProbeTracker
{
    void Bind()
    {
        HCModuleReadiness.HCUse("Probe", "bound");
    }
}

class HCProbeHelper
{
    static void Attach(HCProbeTracker tracker)
    {
        tracker.Bind();
    }
}

modded class ItemBase
{
    override void EEInit()
    {
        super.EEInit();
        HCProbeTracker tracker = new HCProbeTracker();
        HCProbeHelper.Attach(tracker);
    }
}
