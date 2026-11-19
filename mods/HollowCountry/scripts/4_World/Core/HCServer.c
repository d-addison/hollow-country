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
    protected float m_OperationalRefreshAt;
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
        HCOperationalContributors.HCReset();
        m_OperationalRefreshAt = 0;
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
        bool moduleStarted = false;
        bool moduleReady = false;
        bool moduleConflicted = false;
        HCOperationalStatus reported = null;
        HCOperationalOwner opOwner = null;
        foreach (HCModule module : modules)
        {
            // Exactly one lifecycle admission read; it may load local config.
            moduleEnabled = module.IsEnabled(m_Settings);
            moduleStarted = false;
            moduleReady = false;
            moduleConflicted = false;
            if (moduleEnabled)
            {
                m_Active.Insert(module);
                module.OnStart(m_Settings);
                moduleStarted = true;
            }
            reported = module.HCGetOperationalStatus();
            m_Operational.HCCapture(module.GetName(), moduleEnabled, reported);
            opOwner = HCOperationalContributors.HCRegisterOwner(module.GetName());
            if (opOwner) { opOwner.HCObserve(moduleEnabled, reported, GetGame().GetTickTime()); }
            // OnStart returning alone is not readiness. Internal started flags
            // are private to owners: their existing cached hook publishes them.
            // Missing evidence is never ready; never repeat IsEnabled/config reads.
            // A started module without a status hook says so rather than "off".
            if (reported)
            {
                moduleReady = moduleEnabled && moduleStarted && reported.HCState() == "ready";
                moduleConflicted = !moduleStarted && (reported.HCState() == "ready" || reported.HCState() == "degraded" || reported.HCState() == "requested");
                if (moduleReady) { Print("[HC " + module.GetName() + "] ready"); }
                if (moduleConflicted) { Print("[HC " + module.GetName() + "] off reason=owner_report_conflicts_with_no_start"); }
                if (!moduleReady && !moduleConflicted) { Print("[HC " + module.GetName() + "] off reason=" + reported.HCReason()); }
            }
            if (!reported && !moduleEnabled) { Print("[HC " + module.GetName() + "] off reason=module_not_enabled"); }
            if (!reported && moduleEnabled) { Print("[HC " + module.GetName() + "] started reason=owner_state_unreported"); }
        }
        m_Started = true;
        m_LastTick = GetGame().GetTickTime();
        m_OperationalRefreshAt = m_LastTick + 15;
        m_Perf.Start(60);
        foreach (HCModule perfModule : m_Active)
        {
            m_Perf.RegisterModule(perfModule.GetName());
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Tick, m_Settings.TickIntervalMs, true);
        Print(HCV2Admission.Summary(m_Settings));
        Print(HCV2Admission.OperationalSummary(m_Operational));
        Print(HCV2Admission.NonModuleSummary());
        HCOperationalContributors.HCReport();
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
        // Publish cached owner state on the lifecycle path, never on requests.
        // The registry caps 64; keep the refresh independently bounded as well.
        if (now >= m_OperationalRefreshAt)
        {
            m_OperationalRefreshAt = now + 15;
            int refreshIndex = 0;
            HCOperationalOwner refreshOwner = null;
            HCOperationalStatus refreshStatus = null;
            foreach (HCModule refreshModule : m_Active)
            {
                if (refreshIndex >= 64) { break; }
                refreshIndex++;
                refreshOwner = HCOperationalContributors.HCRegisterOwner(refreshModule.GetName());
                if (refreshOwner)
                {
                    refreshStatus = refreshModule.HCGetOperationalStatus();
                    refreshOwner.HCObserve(true, refreshStatus, now);
                }
            }
        }
        m_Perf.Sample(elapsed, TickCount(perfStart));
    }

    void Stop()
    {
        if (!m_Started && m_Active.Count() == 0) return;
        m_Started = false;
        // Retain off/unknown receipts even if a later stop callback aborts.
        m_Operational.HCStopAll();
        if (GetGame()) GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(Tick);
        float stopNow = -1;
        if (GetGame()) { stopNow = GetGame().GetTickTime(); }
        HCOperationalOwner stopOwner = null;
        for (int i = m_Active.Count() - 1; i >= 0; i--)
        {
            HCModule module = m_Active[i];
            // Remove before callback: an abort must not repeat this module's stop.
            m_Active.Remove(i);
            stopOwner = HCOperationalContributors.HCRegisterOwner(module.GetName());
            if (stopOwner) { stopOwner.HCStop(stopNow); }
            module.OnStop();
        }
        // Stop consumes the final cached save/refusal costs after OnStop.
        m_Perf.Stop();
        m_Active.Clear();
        Print("[HollowCountry] Server modules stopped");
    }
}
