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

    void RegisterModules() {}

    void Register(HCModule module)
    {
        if (!module || m_Modules.Count() >= 8) return;
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
