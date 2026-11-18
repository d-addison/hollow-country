// LC-T101..103 / EXP-A1. Server admission only; no server weather/PPE changes.
// Project APIs: Core/HCModule.c:1-8, :15-32; Core/HCV2Admission.c:21;
// Core/HCV2Gates.c:12. Owner decision 2026-11-17: gate verdict is diagnostic.
class HCGradeModule extends HCModule
{
    override string GetName() { return "Grade"; }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableGrade;
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Grade", true, "EXP-A1", HCV2Gates.Qualified("EXP-A1")));
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCGradeModule);
    }
}
