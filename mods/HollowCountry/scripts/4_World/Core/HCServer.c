class HCServer
{
    protected static ref HCServer s_Instance;
    protected ref HCSettings m_Settings = new HCSettings();
    protected ref HCModuleRegistry m_Registry;
    protected ref array<ref HCModule> m_Active = new array<ref HCModule>();
    protected bool m_Started;
    protected float m_LastTick;

    static HCServer Get()
    {
        if (!s_Instance) s_Instance = new HCServer();
        return s_Instance;
    }

    HCSettings GetSettings() { return m_Settings; }
    bool IsStarted() { return m_Started; }

    void Start()
    {
        if (m_Started || !GetGame() || !GetGame().IsServer()) return;
        if (!HCNativeSelfTests.Run())
        {
            Print("[HollowCountry] Core native self-test FAILED; no modules started");
            return;
        }
        HCSettings loaded = HCSettings.LoadFromProfile();
        if (!loaded) return;
        m_Settings = loaded;
        m_Registry = new HCModuleRegistry();
        m_Registry.RegisterModules();
        foreach (HCModule module : m_Registry.GetModules())
        {
            if (!module.IsEnabled(m_Settings)) continue;
            module.OnStart(m_Settings);
            m_Active.Insert(module);
            Print("[HollowCountry] Requested module start; inspect module admission result: " + module.GetName());
        }
        m_Started = true;
        m_LastTick = GetGame().GetTickTime();
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Tick, m_Settings.TickIntervalMs, true);
        Print("[HollowCountry] Server initialized; experimental features require explicit settings");
    }

    void Tick()
    {
        if (!m_Started || !GetGame() || !GetGame().IsServer()) return;
        float now = GetGame().GetTickTime();
        float elapsed = now - m_LastTick;
        m_LastTick = now;
        // Preserve real TTL/cooldown time without unbounded catch-up callbacks.
        // A rollback or suspension over five minutes stops modules conservatively.
        if (!(elapsed > 0) || elapsed > 300)
        {
            Print("[HollowCountry] Clock discontinuity; stopping experimental modules");
            Stop();
            return;
        }
        foreach (HCModule module : m_Active) module.OnTick(elapsed);
    }

    void Stop()
    {
        if (!m_Started) return;
        m_Started = false;
        if (GetGame()) GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(Tick);
        for (int i = m_Active.Count() - 1; i >= 0; i--) m_Active[i].OnStop();
        m_Active.Clear();
        Print("[HollowCountry] Server modules stopped");
    }
}
