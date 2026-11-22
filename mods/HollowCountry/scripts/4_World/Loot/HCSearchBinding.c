// House search service owner; never a loot spawner.
// Native snapshot 1.30.164289 (paths relative to the installed native cache):
//   3_Game/gameplay.c:636 GetGame
//   3_Game/Global/Game.c:1120 IsServer; :1550 GetCallQueue
//   1_Core/proto/EnConvert.c:30 int.ToString; 1_Core/proto/EnDebug.c:96 Print
// The lazy House search service lives here; supply is stock CE and is never spawned or
// bound at start. Runtime acceptance stays pending.

// Core integration: Register(new HCSearchBinding); in HCModuleRegistry.RegisterModules
// before the interior module is started. This gives mission finish an OnStop owner.
class HCSearchBinding : HCModule
{
    protected static HCSearchBinding s_Instance;
    protected bool m_Started;
    protected bool m_Stopped;
    protected string m_Refusal;
    protected string m_Fault;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected ref HCSettings m_Settings;
    // Lazy House search (contract section 8). Started and stopped with this module so it never
    // needs an extra HCModuleRegistry slot; it does nothing until a valid House search start.
    protected ref HCSearchHouses m_Houses;

    override string GetName()
    {
        return "SearchBinding";
    }

    // Wave 16: started = the lazy search service is up and not stopped; a refused measured-interior hand-over
    // after start is a real degradation (m_Fault); a missing admission marker or a stopped module is a refusal.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        bool running = false;
        if (m_Started && !m_Stopped && m_Houses && m_Houses.HCJournalReady()) { running = true; }
        string refusal = m_Refusal;
        string fault = m_Fault;
        if (m_Started && !running && refusal == "")
        {
            if (!HCInteriorTemplates.Loaded()) { refusal = "templates_not_loaded"; }
            else if (m_Houses && m_Houses.HCJournalWaiting()) { refusal = "house_journal_recovering"; }
        }
        if (m_Houses && m_Houses.HCJournalFaulted())
        {
            running = m_Started && !m_Stopped;
            fault = "house_journal_fault";
        }
        HCModuleReadiness.HCDerive(m_Operational, running, refusal, fault, "search_service_started_supply_lazy");
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableInteriors && settings.EnableSearch;
    }

    override void OnStart(HCSettings settings)
    {
        if (m_Started || !GetGame() || !GetGame().IsServer() || !IsEnabled(settings)) return;
        if (m_Stopped)
        {
            Print("[HC Search Binding] start refused: module already stopped; search remains refused");
            m_Refusal = "module_already_stopped";
            return;
        }
        if (!HCInteriorRules.SearchAdmitted())
        {
            Print("[HC Search Binding] off: search admission marker absent; search remains refused");
            m_Refusal = "search_admission_marker_absent";
            return;
        }
        if (!HCSearchLimits.HCGet().Healthy()) { m_Refusal = "search_limits_invalid"; return; }
        if (s_Instance && s_Instance != this) return;
        m_Started = true;
        m_Refusal = "";
        m_Fault = "";
        m_Settings = settings;
        m_Houses = new HCSearchHouses;
        m_Houses.Start(settings);
        s_Instance = this;
        Print(HCV2Admission.Line("SearchBinding", true, "interior_search", false) + " runtime=PENDING");
    }

    // The running House search service, or null when this module is stopped or never started.
    static HCSearchHouses Houses()
    {
        if (!s_Instance || s_Instance.m_Stopped) return null;
        return s_Instance.m_Houses;
    }

    override void OnTick(float deltaTime)
    {
        // Opening only schedules recovery; report readiness after its final slice.
        if (m_Started && !m_Stopped && m_Houses && HCInteriorTemplates.Loaded()) { m_Houses.ReportReadiness(); }
    }

    // Reports search readiness once the template load has finished (loaded or refused).
    static void TemplatesComplete(HCInteriorsModule owner)
    {
        if (!GetGame() || !GetGame().IsServer() || !owner) return;
        HCSearchHouses houses = Houses();
        if (houses)
        {
            houses.ReportReadiness();
            return;
        }
        int templatesLoaded;
        int markerPresent;
        if (HCInteriorTemplates.Loaded()) templatesLoaded = 1;
        if (HCInteriorRules.SearchOptIn()) markerPresent = 1;
        Print("[HC Search Houses] armed=0 templates_loaded=" + templatesLoaded.ToString() + " service_started=0 journal_healthy=0 marker_present=" + markerPresent.ToString() + "; supply=lazy stock CE; runtime acceptance PENDING");
    }

    override void OnStop()
    {
        m_Stopped = true;
        if (m_Houses)
        {
            m_Houses.Stop();
            m_Houses = null;
        }
        m_Settings = null;
        if (s_Instance == this) s_Instance = null;
    }
}
