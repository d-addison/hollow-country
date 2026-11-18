class HCModule
{
    string GetName() { return "unnamed"; }
    bool IsEnabled(HCSettings settings) { return false; }
    void OnStart(HCSettings settings) {}
    void OnTick(float deltaTime) {}
    void OnStop() {}
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
