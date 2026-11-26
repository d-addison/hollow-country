// Shared lifecycle capacity; telemetry owners must use the same bound.
const int HC_MAX_MODULES = 128;
const int HC_PHASE_CORE = 0;
const int HC_PHASE_PROVIDER = 1;
const int HC_PHASE_FEATURE = 2;
const int HC_PHASE_ADDON = 3;

class HCModule
{
    // Compatibility until store owners override RequiresSharedSaves in Wave 2.
    // Includes embedded BuildingClaim (Camps) and VisualSeasons (WeatherDays).
    protected static ref array<string> s_HCLegacySaveOwners = {"World", "SettlementDecay", "Escalation", "Scenes", "Ecology", "Forage", "Leads", "Progression", "Camps", "InfectedLOD", "WeatherDays"};
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
    // Stable ties preserve registration order until module owners adopt phases.
    int StartupPhase() { return HC_PHASE_FEATURE; }
    bool RequiresSharedSaves() { return s_HCLegacySaveOwners.Find(GetName()) >= 0; }
    // Override with owned HCRegisterUse calls; legacy declarations remain available
    // for modules and modded registration extensions not migrated in this wave.
    void RegisterUses() { HCModuleReadiness.HCRegisterModuleUses(GetName()); }
    // All OnStart hooks return before any post-start hook or readiness snapshot.
    // Peer binding belongs here; bulk warmup still belongs on the startup pump.
    void OnAllModulesStarted() {}
    void OnStart(HCSettings settings) {}
    void OnTick(float deltaTime) {}
    void OnStop() {}
    // Passive telemetry only: implementations forward cached maxima, never scan.
    void PerfSampleCosts(HCPerfSampler sampler, int slot, float ticksPerMs) {}
    string PerfExtraSummary() { return ""; }
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
        // One shared lifecycle bound for registration and readiness.
        if (m_Modules.Count() >= HC_MAX_MODULES)
        {
            Print("[HollowCountry] Module registration refused (cap " + HC_MAX_MODULES.ToString() + "): " + module.GetName());
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

    // Boot-only stable insertion sort: bounded by HC_MAX_MODULES squared.
    // Cache each phase once; sorting must not repeatedly call module hooks.
    void HCSortStartup()
    {
        array<int> phases = new array<int>();
        foreach (HCModule module : m_Modules) { phases.Insert(module.StartupPhase()); }
        for (int index = 1; index < m_Modules.Count(); index++)
        {
            ref HCModule selected = m_Modules[index];
            int phase = phases[index];
            int previous = index - 1;
            while (previous >= 0)
            {
                if (phases[previous] <= phase) { break; }
                m_Modules[previous + 1] = m_Modules[previous];
                phases[previous + 1] = phases[previous];
                previous--;
            }
            m_Modules[previous + 1] = selected;
            phases[previous + 1] = phase;
        }
    }

    array<ref HCModule> GetModules() { return m_Modules; }
}
