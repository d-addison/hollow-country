// Once per server process. Availability is a source disposition, not native
// acceptance. #34 observation work must never imply resource use or migration.
class HCEcologyDisposition
{
    protected static bool s_Reported;

    static void Report()
    {
        if (s_Reported) { return; }
        s_Reported = true;
        Print("[HC Ecology] observation_path=available; reason=bounded registered cohort and native geometry queries only; runtime acceptance PENDING");
        Print("[HC Ecology] coverage=partial; reason=EEInit cohort capped at configured budgets, not a world census");
        Print("[HC Ecology] feeding=native_graze_input; terrain_field_goals=enabled_by_cycle; consumption_transaction=unavailable runtime=PENDING");
        Print("[HC Ecology] drinking=native_drink_input; inland_shore_goals=enabled_by_cycle; water_quantities=untouched runtime=PENDING");
        Print("[HC Ecology] migration=native_input_leases_and_owned_pack_waypoints; ce_weights=unchanged runtime=PENDING");
    }
}

// Core lifecycle seam for the bounded ecology observation service (#34).
// Calls only the reviewed HCEcologyRuntime Start/Tick/Stop surface. When the
// service will not run, the pre-start registration cohort is released.
// HC-49 consumes the same lifecycle. Native 1.30.164289:
// 3_Game/Global/Game.c:1535 GetTime (mission milliseconds), :1120 IsServer,
// :914 GetTickTime (HC-25 cached owner freshness only);
// HCGroupClock.Utc validates the EnSystem.c:76/100 date/time sample and
// returns -1 on invalid/rewound UTC. No separate clock-validity method exists.
class HCEcologyRuntimeModule : HCModule
{
    protected static HCEcologyRuntimeModule s_Instance;
    protected ref HCEcologyRuntimeSettings m_Settings;
    protected ref HCEcologyCycle m_Cycle;
    protected bool m_MigrationStarted;
    protected ref HCWildlifeScenes m_WildlifeScenes;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCOperationalStatus m_WildlifeStatus = new HCOperationalStatus;
    protected bool m_Started;

    void HCEcologyRuntimeModule()
    {
        m_Status.HCPublish("off", "not_started");
        m_WildlifeStatus.HCPublish("off", "not_started");
    }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }
    HCOperationalStatus HCGetWildlifeStatus() { return m_WildlifeStatus; }

    // HC-49 is a child service, not a second module/registry/timer. Publish its
    // independently observed status through HC-25's bounded cached owner path.
    protected void HCObserveWildlife(bool requested)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        HCOperationalOwner wildlifeOwner = HCOperationalContributors.HCRegisterOwner("HC-49");
        if (wildlifeOwner)
        {
            wildlifeOwner.HCObserve(requested, HCGetWildlifeStatus(), GetGame().GetTickTime());
        }
    }
    static HCWildlifeScenes HCWildlife()
    {
        if (!s_Instance) { return null; }
        return s_Instance.m_WildlifeScenes;
    }

    override string GetName() { return "Ecology"; }

    override void PerfSampleCosts(HCPerfSampler sampler, int slot, float ticksPerMs)
    {
        HCEcologyRuntime runtime = HCEcologyRuntime.HCPeek();
        if (!runtime) { return; }
        runtime.HCSetCalibration(ticksPerMs);
        sampler.SampleCost(slot, 0, runtime.HCStartupTicks());
        sampler.SampleCost(slot, 1, runtime.HCCallbackTicks());
        sampler.SampleCost(slot, 2, runtime.HCSaveTicks());
        sampler.SampleCost(slot, 3, runtime.HCAdmissionTicks());
        runtime.HCResetCostTicks();
    }

    override string PerfExtraSummary()
    {
        HCEcologyRuntime runtime = HCEcologyRuntime.HCPeek();
        if (!runtime) { return ""; }
        return " visited=" + runtime.HCVisited().ToString() + " deferred=" + runtime.HCDeferred().ToString();
    }

    override bool IsEnabled(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer()) { m_Status.HCPublish("off", "server_required"); return false; }
        HCEcologyDisposition.Report();
        m_Settings = HCEcologyRuntimeIO.Settings();
        if (!m_Settings)
        {
            Print("[HC Ecology] settings unreadable or invalid; disabled");
            HCEcologyRuntime.CloseCollection();
            HCWildlifeObservation.HCStart(false);
            m_Status.HCPublish("refused", "ecology_settings_invalid");
            m_WildlifeStatus.HCPublish("refused", "ecology_settings_invalid");
            HCEcologyNative.HCHabitatRefusals("refused");
            HCObserveWildlife(false);
            Print("[HC Plan] HC-49 state=refused refusal=ecology_settings_invalid retained=0 active=0 runtime=PENDING");
            return false;
        }
        if (!m_Settings.Enabled || !settings || !settings.EnableAmbientLife)
        {
            Print("[HC Ecology] explicitly disabled by operator");
            HCEcologyRuntime.CloseCollection();
            HCWildlifeObservation.HCStart(false);
            m_Status.HCPublish("off", "ecology_operator_off");
            m_WildlifeStatus.HCPublish("off", "ecology_operator_off");
            HCEcologyNative.HCHabitatRefusals("off");
            HCObserveWildlife(false);
            Print("[HC Plan] HC-49 state=off refusal=ecology_operator_off retained=0 active=0 runtime=PENDING");
            return false;
        }
        return true;
    }

    override void OnStart(HCSettings settings)
    {
        if (s_Instance || m_Started) { return; }
        m_Started = HCEcologyRuntime.Start(m_Settings, GetGame().GetWorldName(), Session());
        if (m_Started)
        {
            m_MigrationStarted = HCEcologyMigration.Start(GetGame().GetWorldName());
            m_Cycle = new HCEcologyCycle;
            if (!m_Cycle.Open()) { m_Status.HCPublish("refused", "ecology_cycle_store_or_settings"); }
            HCWildlifeObservation.HCStart(true);
            s_Instance = this;
            m_WildlifeScenes = new HCWildlifeScenes;
            m_WildlifeScenes.HCOpen(true);
            m_WildlifeStatus = m_WildlifeScenes.HCStatus();
            if (m_Cycle.Healthy() && (!m_Cycle.NeedsMigration() || m_MigrationStarted)) { m_Status.HCPublish("ready", "ecology_cycle_started_runtime_pending"); }
            else { m_Status.HCPublish("refused", "ecology_cycle_or_migration_unavailable"); }
            HCEcologyNative.HCHabitatRefusals("ready");
        }
        if (!m_Started)
        {
            Print("[HC Ecology] admission rejected; observation service not running");
            HCEcologyRuntime.CloseCollection();
            HCWildlifeObservation.HCStart(false);
            m_Status.HCPublish("refused", "ecology_admission_rejected");
            m_WildlifeStatus.HCPublish("refused", "ecology_admission_rejected");
            HCEcologyNative.HCHabitatRefusals("refused");
            Print("[HC Plan] HC-49 state=refused refusal=ecology_admission_rejected retained=0 active=0 runtime=PENDING");
        }
        HCObserveWildlife(m_Started);
    }

    override void OnTick(float deltaTime)
    {
        int ecologyStart = TickCount(0);
        HCEcologySteps.Begin();
        int ecologyPart = TickCount(0);
        HCEcologyRuntime.Tick(GetGame().GetTime());
        HCEcologySteps.Record(0, ecologyPart, "hc29");
        ecologyPart = TickCount(0);
        if (m_Started && m_Cycle)
        {
            m_Cycle.Tick();
            if (!m_Cycle.Healthy()) { m_Status.HCPublish("refused", "ecology_cycle_save_or_clock"); }
            else if (m_Cycle.NeedsMigration() && (!m_MigrationStarted || !HCEcologyMigration.Operational())) { m_Status.HCPublish("refused", "ecology_migration_store_unavailable"); }
        }
        HCEcologySteps.Cycle(ecologyPart);
        ecologyPart = TickCount(0);
        if (m_Started) { HCWildlifeObservation.HCTick(GetGame().GetTime()); }
        HCEcologySteps.Record(6, ecologyPart, "wildlife");
        ecologyPart = TickCount(0);
        if (m_Started) { HCReached.Mark("ecology.observation_tick"); }
        if (m_Started && m_WildlifeScenes && m_WildlifeScenes.HCActive())
        {
            int utc = HCGroupClock.Utc();
            if (utc >= 1577836801) { m_WildlifeScenes.HCStep(utc - 1577836800, GetGame().GetTime()); }
        }
        HCEcologySteps.Record(7, ecologyPart, "scenes");
        HCObserveWildlife(m_Started);
        HCEcologySteps.End(ecologyStart);
    }

    override void OnStop()
    {
        if (m_Cycle) { m_Cycle.Close(); }
        m_Cycle = null;
        if (m_WildlifeScenes) { m_WildlifeScenes.HCClose(); }
        m_WildlifeScenes = null;
        if (s_Instance == this) { s_Instance = null; }
        m_Status.HCPublish("off", "owner_closed");
        m_WildlifeStatus.HCPublish("off", "owner_closed");
        HCObserveWildlife(false);
        HCWildlifeObservation.HCStop();
        HCEcologyMigration.Stop();
        HCEcologyRuntime.Stop();
        m_Started = false;
    }

    string Session()
    {
        int year;
        int month;
        int day;
        int hour;
        int minute;
        int second;
        GetYearMonthDayUTC(year, month, day);
        GetHourMinuteSecondUTC(hour, minute, second);
        return SessionToken(year, month, day, hour, minute, second, Math.RandomIntInclusive(0, 999999));
    }

    // Token alphabet only (HCEcologyRuntimeRules.Token): digits, 's' and '-'.
    static string SessionToken(int year, int month, int day, int hour, int minute, int second, int nonce)
    {
        string date = year.ToStringLen(4) + month.ToStringLen(2) + day.ToStringLen(2);
        string time = hour.ToStringLen(2) + minute.ToStringLen(2) + second.ToStringLen(2);
        return "s" + date + "-" + time + "-" + nonce.ToStringLen(6);
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCEcologyRuntimeModule);
    }
}
