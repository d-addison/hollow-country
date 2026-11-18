// LC-T501/502 admission only. No engine API calls or client settings transport.
// Shared runtime contract: Core/HCModule.c, HCV2Admission.c, HCV2Gates.c.
// EnableAmbientLife gates this server diagnostic module only; both client layers
// run locally by default, regardless of EnableAmbientLife/EnableSignsOfLife.
class HCPolishModule : HCModule
{
    override string GetName()
    {
        return "Polish";
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableAmbientLife;
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Hints", true, "EXP-POL-1", HCV2Gates.Qualified("EXP-POL-1")));
        Print(HCV2Admission.Line("EnvSound", true, "EXP-POL-2", HCV2Gates.Qualified("EXP-POL-2")));
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCPolishModule);
    }
}
