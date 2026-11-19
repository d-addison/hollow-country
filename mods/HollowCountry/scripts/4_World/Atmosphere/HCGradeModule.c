// LC-T101..103 / EXP-A1. Server admission only; no server weather/PPE changes.
// Project APIs: Core/HCModule.c:1-8, :15-32; Core/HCV2Admission.c:21;
// Core/HCV2Gates.c:12. Owner decision 2026-11-17: gate verdict is diagnostic.
class HCGradeModule extends HCModule
{
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "Grade"; }

    // Wave 16: cached readiness from the live started flag (never hard-coded).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", "", "server_admission_logged_client_runtime_pending");
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableGrade;
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Grade", true, "EXP-A1", HCV2Gates.Qualified("EXP-A1")));
        m_Started = true;
    }

    override void OnStop() { m_Started = false; }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCGradeModule);
    }
}
