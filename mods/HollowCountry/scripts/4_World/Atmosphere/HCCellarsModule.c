// W5 #60 admission only. No server trigger, gameplay state, entity or RPC.
// Native Print: scripts-1.30.164289/1_Core/proto/EnDebug.c:96.
// Work per tick: zero. Client uses its own default-on local visual preference.
class HCCellarsModule : HCModule
{
    override string GetName() { return "Cellars"; }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableAmbientLife;
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Cellars", true, "EXP-A3", HCV2Gates.Qualified("EXP-A3")));
        Print("[HollowCountry] V2 cellars mode=client_below_terrain depth=2m measured_volumes=0 runtime=PENDING");
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCCellarsModule);
    }
}
