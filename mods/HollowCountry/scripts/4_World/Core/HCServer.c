// HC-1 native scripts-1.30.164289: 3_Game/Global/Game.c:914,1120,1550
// GetTickTime/IsServer/GetCallQueue; existing mission lifecycle owns Start/Stop.
// 1_Core/proto/EnDebug.c:96 Print; EnScript.c:380,385,407,463 arrays;
// EnSystem.c:106 TickCount. Queue scheduling is unchanged by HC-1.
// HCModule.HCGetOperationalStatus is the lead-owned default-null cached hook.
class HCServer
{
    protected static ref HCServer s_Instance;
    protected ref HCSettings m_Settings = new HCSettings();
    protected ref HCModuleRegistry m_Registry;
    protected ref array<ref HCModule> m_Active = new array<ref HCModule>();
    protected ref HCOperationalStatusCache m_Operational = new HCOperationalStatusCache();
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

    // Passive operator/debug ports: cached strings, no module callbacks or IO.
    int HCOperationalCount() { return m_Operational.HCCount(); }
    string HCOperationalLine(int index) { return m_Operational.HCLine(index); }
    string HCOperationalSummary() { return HCV2Admission.OperationalSummary(m_Operational); }

    void Start()
    {
        if (m_Started || !GetGame() || !GetGame().IsServer()) return;
        // A prior startup/stop callback may have aborted before cleanup finished.
        if (m_Active.Count() > 0) Stop();
        HCInfectedVisionQualification.HCThreatReset(false);
        m_Operational.HCReset();
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
        // Named locals only: boot 040 and 041 showed the foreach over the
        // returned registry array losing its array ("NULL pointer to instance"
        // on the foreach line) once the body passed a returned status object
        // straight into a call. Keep the array and status in locals.
        array<ref HCModule> modules = m_Registry.GetModules();
        bool moduleEnabled = false;
        HCOperationalStatus reported = null;
        foreach (HCModule module : modules)
        {
            // Exactly one lifecycle admission read; it may load local config.
            moduleEnabled = module.IsEnabled(m_Settings);
            if (moduleEnabled)
            {
                m_Active.Insert(module);
                module.OnStart(m_Settings);
            }
            reported = module.HCGetOperationalStatus();
            m_Operational.HCCapture(module.GetName(), moduleEnabled, reported);
            if (moduleEnabled)
            {
                Print("[HollowCountry] Requested module start; inspect module admission result: " + module.GetName());
            }
        }
        m_Started = true;
        m_LastTick = GetGame().GetTickTime();
        m_Perf.Start(60);
        foreach (HCModule perfModule : m_Active)
        {
            m_Perf.RegisterModule(perfModule.GetName());
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Tick, m_Settings.TickIntervalMs, true);
        Print(HCV2Admission.Summary(m_Settings));
        Print(HCV2Admission.OperationalSummary(m_Operational));
        Print(HCV2Admission.NonModuleSummary());
        Print(HCInfectedReachPolicy.HCThreatSummary(m_Settings.EnableInfected));
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
        int moduleIndex = 0;
        foreach (HCModule module : m_Active)
        {
            int moduleStart = TickCount(0);
            module.OnTick(elapsed);
            m_Perf.SampleModule(moduleIndex, TickCount(moduleStart));
            moduleIndex++;
        }
        m_Perf.Sample(elapsed, TickCount(perfStart));
    }

    void Stop()
    {
        if (!m_Started && m_Active.Count() == 0) return;
        m_Started = false;
        // Retain off/unknown receipts even if a later stop callback aborts.
        m_Operational.HCStopAll();
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
