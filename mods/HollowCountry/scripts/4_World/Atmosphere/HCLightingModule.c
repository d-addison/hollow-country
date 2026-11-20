// LC-T104 / EXP-A2. Admission only; all renderer work is client-local.
// HCModule/HCModuleRegistry contract: 4_World/Core/HCModule.c:1,11,16,22.
// Native Print: installed scripts-1.30.164289/1_Core/proto/EnDebug.c:96.
class HCLightingModule: HCModule
{
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "Lighting"; }

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
        Print(HCV2Admission.Line("Lighting", true, "EXP-A2", HCV2Gates.Qualified("EXP-A2")));
        m_Started = true;
        HCReached.Mark("lighting.admission_logged");
    }

    override void OnStop() { m_Started = false; }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCLightingModule);
    }
}
