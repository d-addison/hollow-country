// HC-1 native scripts-1.30.164289: 3_Game/Global/Game.c:914,1120,1550
// GetTickTime/IsServer/GetCallQueue; existing mission lifecycle owns Start/Stop.
// 1_Core/proto/EnDebug.c:96 Print; EnScript.c:380,385,407,463 arrays;
// EnSystem.c:106 TickCount. Queue scheduling is unchanged by HC-1.
// HCModule.HCGetOperationalStatus is the lead-owned default-null cached hook.
class HCServer
{
    protected static ref HCServer s_Instance;
    // Idle budget for callers outside a core tick; allocated once on first use, never per tick.
    protected static ref HCUnitBudget s_IdleWork;
    protected ref HCSettings m_Settings = new HCSettings();
    protected ref HCModuleRegistry m_Registry;
    protected ref array<ref HCModule> m_Active = new array<ref HCModule>();
    protected ref HCOperationalStatusCache m_Operational = new HCOperationalStatusCache();
    // Wave 16: boot-time state/reason of each ACTIVE module (same order as m_Active) for late readiness lines.
    protected ref HCOperationalChanges m_Changes = new HCOperationalChanges();
    protected bool m_Started;
    protected bool m_SettingsRefusalLogged;
    protected float m_LastTick;
    // False until the first queued Tick after Start rebaselines the clock.
    protected bool m_TickBaselined;
    protected float m_OperationalRefreshAt;
    protected ref HCPerfSampler m_Perf = new HCPerfSampler();
    // Wave 13 (#138): ONE shared per-tick work budget, reset to MaxTickWorkItems at the top of Tick()
    // and read by every module item loop through HCServer.HCTickWork(). Allocated once, no per-tick
    // allocation. m_TickActive is true only while Tick() is running the module callbacks.
    protected ref HCUnitBudget m_TickWork = new HCUnitBudget();
    protected ref HCUnitProfile m_TickProfile;
    protected int m_TickCostWindow;
    protected bool m_TickActive;

    static HCServer Get()
    {
        if (!s_Instance) s_Instance = new HCServer();
        return s_Instance;
    }

    HCSettings GetSettings() { return m_Settings; }

    // The shared core-tick work budget (see HCUnitBudget header for the no-starvation rule). Null-safe:
    // with no HCServer instance, or outside a core tick (tests, a module ticking on its own, a player
    // action), it returns the idle budget that never refuses. Fetch it once per tick, not per item.
    static HCUnitBudget HCTickWork()
    {
        if (s_Instance && s_Instance.m_TickActive) { return s_Instance.m_TickWork; }
        if (!s_IdleWork) { s_IdleWork = new HCUnitBudget(); }
        s_IdleWork.HCReset(HCUnitBudget.HC_WORK_UNBOUNDED);
        return s_IdleWork;
    }
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
        HCReached.Begin();
        HCInfectedVisionQualification.HCThreatReset(false);
        m_Operational.HCReset();
        m_Changes.HCReset();
        HCOperationalContributors.HCReset();
        m_OperationalRefreshAt = 0;
        if (!HCNativeSelfTests.Run())
        {
            Print("[HollowCountry] Core native self-test FAILED; no modules started");
            return;
        }
        HCSettings loaded = HCSettings.LoadFromProfile();
        if (!loaded)
        {
            // Settings refusal already printed its own reason. Give every registered
            // module its readiness line once, without IsEnabled, status or OnStart.
            if (!m_SettingsRefusalLogged)
            {
                m_SettingsRefusalLogged = true;
                HCModuleRegistry refusedRegistry = new HCModuleRegistry();
                refusedRegistry.RegisterModules();
                array<ref HCModule> refusedModules = refusedRegistry.GetModules();
                foreach (HCModule refusedModule : refusedModules)
                {
                    HCOperationalStatus settingsRefused = new HCOperationalStatus();
                    settingsRefused.HCPublish("refused", "settings_unavailable");
                    refusedModule.HCReadyCapture(false, false, settingsRefused);
                    refusedModule.HCReadyReport();
                }
            }
            return;
        }
        m_SettingsRefusalLogged = false;
        m_Settings = loaded;
        m_Registry = new HCModuleRegistry();
        m_Registry.RegisterModules();
        // Named locals only: boot 040 and 041 showed the foreach over the
        // returned registry array losing its array ("NULL pointer to instance"
        // on the foreach line) once the body passed a returned status object
        // straight into a call. Keep the array and status in locals.
        array<ref HCModule> modules = m_Registry.GetModules();
        bool saveServiceRefused = false;
        bool dependsOnSharedSaves = false;
        string sharedSaveOwnerName = "";
        bool moduleEnabled = false;
        bool moduleStarted = false;
        HCOperationalStatus reported = null;
        HCOperationalOwner opOwner = null;
        foreach (HCModule module : modules)
        {
            // Exactly one lifecycle admission read; it may load local config.
            moduleEnabled = module.IsEnabled(m_Settings);
            sharedSaveOwnerName = module.GetName();
            // Includes embedded persistence: Camps owns BuildingClaim;
            // WeatherDays starts VisualSeasons. Refuse before either start hook.
            dependsOnSharedSaves = sharedSaveOwnerName == "World" || sharedSaveOwnerName == "SettlementDecay" || sharedSaveOwnerName == "Escalation" || sharedSaveOwnerName == "Scenes";
            dependsOnSharedSaves = dependsOnSharedSaves || sharedSaveOwnerName == "Ecology" || sharedSaveOwnerName == "Forage" || sharedSaveOwnerName == "Leads" || sharedSaveOwnerName == "Progression";
            dependsOnSharedSaves = dependsOnSharedSaves || sharedSaveOwnerName == "Camps" || sharedSaveOwnerName == "InfectedLOD" || sharedSaveOwnerName == "WeatherDays";
            saveServiceRefused = moduleEnabled && dependsOnSharedSaves && !HCPerfConfig.HCGet().EnableSharedSaves;
            moduleStarted = false;
            if (moduleEnabled && !saveServiceRefused)
            {
                m_Active.Insert(module);
                module.OnStart(m_Settings);
                moduleStarted = true;
            }
            reported = null;
            if (saveServiceRefused)
            {
                reported = new HCOperationalStatus();
                reported.HCPublish("refused", "shared_save_service_operator_off");
            }
            if (!saveServiceRefused) { reported = module.HCGetOperationalStatus(); }
            m_Operational.HCCapture(module.GetName(), moduleEnabled, reported);
            if (moduleStarted) { m_Changes.HCBaseline(reported); }
            opOwner = HCOperationalContributors.HCRegisterOwner(module.GetName());
            if (opOwner) { opOwner.HCObserve(moduleEnabled, reported, GetGame().GetTickTime()); }
            module.HCReadyCapture(moduleEnabled, moduleStarted, reported);
        }
        // All active modules have now returned from OnStart; no new admission reads.
        foreach (HCModule readyModule : modules) { readyModule.HCReadyReport(); }
        m_Started = true;
        m_LastTick = GetGame().GetTickTime();
        m_TickBaselined = false;
        m_OperationalRefreshAt = m_LastTick + 15;
        m_Perf.Start(60);
        m_TickActive = false;
        m_TickWork.HCWindowReset();
        if (!m_TickProfile) { m_TickProfile = new HCUnitProfile; }
        m_TickProfile.HCReset();
        m_TickWork.HCSetProfile(m_TickProfile);
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
        // Native mission and CE init run between Start and the first queued tick and can take
        // minutes on slow disks (10 min observed on an HDD install). That gap is not a clock
        // jump: rebaseline once, then the discontinuity guard applies to every later tick.
        if (!m_TickBaselined)
        {
            m_TickBaselined = true;
            m_LastTick = now;
            m_OperationalRefreshAt = now + 15;
            return;
        }
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
        // Shared budget: reset once, before the first module; every consumer draws from it.
        m_TickWork.HCReset(m_Settings.MaxTickWorkItems);
        m_TickActive = true;
        int perfStart = TickCount(0);
        int moduleIndex = 0;
        foreach (HCModule module : m_Active)
        {
            int moduleStart = TickCount(0);
            module.OnTick(elapsed);
            m_TickWork.HCCloseSpan();
            // #196: a module may call Stop() from OnTick. Stop clears m_Active and retires the perf
            // sampler, so leave the loop at once: no later module ticks (they would draw the unbounded
            // idle budget), no further foreach step over the cleared array, no window roll.
            if (!m_Started) { break; }
            m_Perf.SampleModule(moduleIndex, TickCount(moduleStart));
            moduleIndex++;
        }
        if (!m_Started) { return; }
        m_TickActive = false;
        // One line per perf window (same 60 s as m_Perf.Start): shared_used_max / shared_starved.
        if (m_TickWork.HCEndTick(elapsed, 60))
        {
            m_TickCostWindow++;
            m_TickProfile.HCPrintWindow(m_TickCostWindow);
            Print("" + m_TickWork.HCWindowReport());
        }
        // Publish cached owner state on the lifecycle path, never on requests.
        // The registry caps 128; keep the refresh independently bounded as well.
        if (now >= m_OperationalRefreshAt)
        {
            m_OperationalRefreshAt = now + 15;
            int refreshIndex = 0;
            HCOperationalOwner refreshOwner = null;
            HCOperationalStatus refreshStatus = null;
            string refreshLine = "";
            foreach (HCModule refreshModule : m_Active)
            {
                if (refreshIndex >= HCOperationalChanges.HC_CAP) { break; }
                refreshIndex++;
                refreshOwner = HCOperationalContributors.HCRegisterOwner(refreshModule.GetName());
                if (refreshOwner)
                {
                    refreshStatus = refreshModule.HCGetOperationalStatus();
                    refreshOwner.HCObserve(true, refreshStatus, now);
                    refreshModule.HCReadyLate(refreshStatus);
                    // Wave 16: one line per state change after boot ("" when unchanged: no allocation).
                    refreshLine = m_Changes.HCChange(refreshIndex - 1, refreshModule.GetName(), refreshStatus);
                    if (refreshLine != "") { Print("" + refreshLine); }
                }
            }
        }
        m_Perf.Sample(elapsed, TickCount(perfStart));
    }

    void Stop()
    {
        if (!m_Started && m_Active.Count() == 0) return;
        m_Started = false;
        m_TickActive = false;
        // Retain off/unknown receipts even if a later stop callback aborts.
        m_Operational.HCStopAll();
        m_Changes.HCReset();
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
        HCReached.Summary();
        m_Perf.Stop();
        m_Active.Clear();
        Print("[HollowCountry] Server modules stopped");
    }
}
