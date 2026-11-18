// LC-T104 / EXP-A2. Admission only; all renderer work is client-local.
// HCModule/HCModuleRegistry contract: 4_World/Core/HCModule.c:1,11,16,22.
// Native Print: installed scripts-1.30.164289/1_Core/proto/EnDebug.c:96.
class HCLightingModule: HCModule
{
    override string GetName() { return "Lighting"; }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableGrade;
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Lighting", true, "EXP-A2", HCV2Gates.Qualified("EXP-A2")));
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCLightingModule);
    }
}
