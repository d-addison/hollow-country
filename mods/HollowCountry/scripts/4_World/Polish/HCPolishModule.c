// LC-T501/502 admission only. No engine API calls or client settings transport.
// Shared runtime contract: Core/HCModule.c, HCV2Admission.c, HCV2Gates.c.
// EnableAmbientLife gates this server diagnostic module only; both client layers
// run locally by default, regardless of EnableAmbientLife/EnableSignsOfLife.
class HCPolishModule : HCModule
{
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName()
    {
        return "Polish";
    }

    // Wave 16: cached readiness from the live started flag (never hard-coded).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", "", "server_admission_logged_client_runtime_pending");
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableAmbientLife;
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Hints", true, "EXP-POL-1", HCV2Gates.Qualified("EXP-POL-1")));
        Print(HCV2Admission.Line("EnvSound", true, "EXP-POL-2", HCV2Gates.Qualified("EXP-POL-2")));
        m_Started = true;
    }

    override void OnStop() { m_Started = false; }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCPolishModule);
    }
}
