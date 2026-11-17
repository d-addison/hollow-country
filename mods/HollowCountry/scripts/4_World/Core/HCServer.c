class HCServer
{
    protected static ref HCServer s_Instance;
    protected ref HCSettings m_Settings = new HCSettings();
    protected ref HCModuleRegistry m_Registry;
    protected ref array<ref HCModule> m_Active = new array<ref HCModule>();
    protected bool m_Started;
    protected float m_LastTick;
    protected ref HCPerfSampler m_Perf = new HCPerfSampler();

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
        // A prior startup/stop callback may have aborted before cleanup finished.
        if (m_Active.Count() > 0) Stop();
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
            m_Active.Insert(module);
            module.OnStart(m_Settings);
            Print("[HollowCountry] Requested module start; inspect module admission result: " + module.GetName());
        }
        m_Started = true;
        m_LastTick = GetGame().GetTickTime();
        m_Perf.Start(60);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Tick, m_Settings.TickIntervalMs, true);
        Print("[HollowCountry] Server initialized; feature preferences default enabled; inspect each module's admission result");
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
        int perfStart = TickCount(0);
        foreach (HCModule module : m_Active) module.OnTick(elapsed);
        m_Perf.Sample(elapsed, TickCount(perfStart));
    }

    void Stop()
    {
        if (!m_Started && m_Active.Count() == 0) return;
        m_Started = false;
        m_Perf.Stop();
        if (GetGame()) GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(Tick);
        for (int i = m_Active.Count() - 1; i >= 0; i--)
        {
            HCModule module = m_Active[i];
            // Remove before callback: an abort must not repeat this module's stop.
            m_Active.Remove(i);
            module.OnStop();
        }
        m_Active.Clear();
        Print("[HollowCountry] Server modules stopped");
    }
}
