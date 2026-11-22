// OnStart reaches the counter through two unqualified helpers.
class HCProbeModule : HCModule
{
    override void OnStart(HCSettings settings)
    {
        Prepare();
    }

    protected void Prepare()
    {
        Announce();
    }

    protected void Announce()
    {
        HCModuleReadiness.HCUse("Probe", "announced");
    }
}
