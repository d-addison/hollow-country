class HCModule
{
    protected ref HCOperationalStatus m_HCReadyStatus;
    protected bool m_HCReadyEnabled;
    protected bool m_HCReadyStarted;
    // Snapshot the existing owner state, then emit only after all start hooks finish.
    void HCReadyCapture(bool enabled, bool started, HCOperationalStatus status)
    {
        m_HCReadyEnabled = enabled;
        m_HCReadyStarted = started;
        m_HCReadyStatus = new HCOperationalStatus();
        m_HCReadyStatus.HCCapture(GetName(), started, status);
    }

    void HCReadyReport()
    {
        HCModuleReadiness.HCPrint(GetName(), m_HCReadyEnabled, m_HCReadyStarted, m_HCReadyStatus);
        m_HCReadyStatus = null;
    }

    void HCReadyLate(HCOperationalStatus status)
    {
        HCModuleReadiness.HCPrintLate(GetName(), m_HCReadyEnabled, m_HCReadyStarted, status);
    }

    string GetName() { return "unnamed"; }
    bool IsEnabled(HCSettings settings) { return false; }
    void OnStart(HCSettings settings) {}
    void OnTick(float deltaTime) {}
    void OnStop() {}
    // HC-1: a module may return its cached admission status; null means unknown.
    HCOperationalStatus HCGetOperationalStatus() { return null; }
}

class HCModuleRegistry
{
    protected ref array<ref HCModule> m_Modules = new array<ref HCModule>();

    void RegisterModules()
    {
        Register(new HCGroupModule());
        Register(new HCEventModule());
    }

    void Register(HCModule module)
    {
        if (!module) return;
        // Matches HC_PERF_MAX_MODULES (64) so every registered module can be sampled.
        if (m_Modules.Count() >= 64)
        {
            Print("[HollowCountry] Module registration refused (cap 64): " + module.GetName());
            return;
        }
        foreach (HCModule existing : m_Modules)
        {
            if (existing.GetName() == module.GetName())
            {
                Print("[HollowCountry] Duplicate module registration rejected: " + module.GetName());
                return;
            }
        }
        m_Modules.Insert(module);
    }

    array<ref HCModule> GetModules() { return m_Modules; }
}
