// w45 #138/#203. Optional $profile:HollowCountry/performance.json, read once.
// Missing keys retain defaults through HCJsonFields (native loader zero-fills).
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist; 3_Game/tools/JsonFileLoader.c:69
// LoadData; 1_Core/proto/EnMath.c:553 Min; EnDebug.c:96 Print.
// HCGroupIO uses bounded verified native file IO.
class HCPerfConfig
{
    bool EnableSharedSaves = true;
    int SliceMs = 4;
    int SaveStageTargetMs = 10;
    int EcologyRowsPerTick = 4;
    int InteriorStepsPerTick = 1;
    int HoldoutRowsPerTick = 1;
    int InteriorPackOnlineMs = 25;
    int InteriorPackEmptyMs = 150;
    int InteriorPackUnitsPerTick = 4096;
    int DebugSnapshotIntervalSeconds = 300;
    // Per-consumer multipliers of existing caller costs; 1 preserves provisional defaults.
    // Read once at startup; invalid/missing entries retain 1 (registry range 1..64).
    int TickWeight_INFECTED = 1;
    int TickWeight_INTERIORS = 1;
    int TickWeight_SEARCH_BIND = 1;
    int TickWeight_SEARCH_MAINT = 1;
    int TickWeight_SEARCH_REFRESH = 1;
    int TickWeight_SEARCH_DETACHED = 1;
    int TickWeight_LOD_CLASSIFY = 1;
    int TickWeight_LOD_HERD = 1;
    int TickWeight_BASES = 1;
    int TickWeight_CONFLICT = 1;
    int TickWeight_TRADE = 1;
    int TickWeight_SITUATIONS = 1;
    int TickWeight_BASE_RAID = 1;
    int TickWeight_ROLES = 1;
    int TickWeight_FORMATION = 1;
    int TickWeight_CARFIX = 1;
    int TickWeight_HEARTH = 1;
    int TickWeight_INCIDENTS = 1;
    int TickWeight_INCIDENT_RESPONSE = 1;
    int TickWeight_AI_RESPAWN = 1;
    int TickWeight_SEARCH_COMPACT = 1;
    int TickWeight_SHELTER = 1;
    int TickWeight_AI_SITES = 1;
    int TickWeight_STORY_INDEX = 1;
    int TickWeight_AI_ROUTES = 1;
    int TickWeight_POLICE_BIND = 1;
    int TickWeight_ROADS = 1;
    protected static ref HCPerfConfig s_Config;

    static HCPerfConfig HCGet()
    {
        if (s_Config) { return s_Config; }
        HCOperatorSettingsRegistry.HCPerfInit();
        s_Config = new HCPerfConfig;
        string path = "$profile:HollowCountry/performance.json";
        if (!FileExist(path)) { return s_Config; }
        string text;
        string error;
        HCPerfConfig decoded;
        if (!HCGroupIO.Read(path, 4096, text) || !JsonFileLoader<HCPerfConfig>.LoadData(text, decoded, error) || !decoded)
        {
            Print("[HC PerfControl] performance.json unreadable; defaults retained runtime=PENDING");
            return s_Config;
        }
        s_Config.HCApply(decoded, text);
        if (!s_Config.EnableSharedSaves)
        {
            Print("[HC PerfControl] WorldSaves operator_off; dirty state retained; owner shutdown/barrier flushes active runtime=PENDING");
        }
        return s_Config;
    }

    void HCApply(HCPerfConfig decoded, string text)
    {
        if (HCJsonFields.Has(text, "TickWeight_INFECTED") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_INFECTED", decoded.TickWeight_INFECTED)) { TickWeight_INFECTED = decoded.TickWeight_INFECTED; }
        if (HCJsonFields.Has(text, "TickWeight_INTERIORS") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_INTERIORS", decoded.TickWeight_INTERIORS)) { TickWeight_INTERIORS = decoded.TickWeight_INTERIORS; }
        if (HCJsonFields.Has(text, "TickWeight_SEARCH_BIND") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_SEARCH_BIND", decoded.TickWeight_SEARCH_BIND)) { TickWeight_SEARCH_BIND = decoded.TickWeight_SEARCH_BIND; }
        if (HCJsonFields.Has(text, "TickWeight_SEARCH_MAINT") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_SEARCH_MAINT", decoded.TickWeight_SEARCH_MAINT)) { TickWeight_SEARCH_MAINT = decoded.TickWeight_SEARCH_MAINT; }
        if (HCJsonFields.Has(text, "TickWeight_SEARCH_REFRESH") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_SEARCH_REFRESH", decoded.TickWeight_SEARCH_REFRESH)) { TickWeight_SEARCH_REFRESH = decoded.TickWeight_SEARCH_REFRESH; }
        if (HCJsonFields.Has(text, "TickWeight_SEARCH_DETACHED") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_SEARCH_DETACHED", decoded.TickWeight_SEARCH_DETACHED)) { TickWeight_SEARCH_DETACHED = decoded.TickWeight_SEARCH_DETACHED; }
        if (HCJsonFields.Has(text, "TickWeight_LOD_CLASSIFY") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_LOD_CLASSIFY", decoded.TickWeight_LOD_CLASSIFY)) { TickWeight_LOD_CLASSIFY = decoded.TickWeight_LOD_CLASSIFY; }
        if (HCJsonFields.Has(text, "TickWeight_LOD_HERD") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_LOD_HERD", decoded.TickWeight_LOD_HERD)) { TickWeight_LOD_HERD = decoded.TickWeight_LOD_HERD; }
        if (HCJsonFields.Has(text, "TickWeight_BASES") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_BASES", decoded.TickWeight_BASES)) { TickWeight_BASES = decoded.TickWeight_BASES; }
        if (HCJsonFields.Has(text, "TickWeight_CONFLICT") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_CONFLICT", decoded.TickWeight_CONFLICT)) { TickWeight_CONFLICT = decoded.TickWeight_CONFLICT; }
        if (HCJsonFields.Has(text, "TickWeight_TRADE") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_TRADE", decoded.TickWeight_TRADE)) { TickWeight_TRADE = decoded.TickWeight_TRADE; }
        if (HCJsonFields.Has(text, "TickWeight_SITUATIONS") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_SITUATIONS", decoded.TickWeight_SITUATIONS)) { TickWeight_SITUATIONS = decoded.TickWeight_SITUATIONS; }
        if (HCJsonFields.Has(text, "TickWeight_BASE_RAID") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_BASE_RAID", decoded.TickWeight_BASE_RAID)) { TickWeight_BASE_RAID = decoded.TickWeight_BASE_RAID; }
        if (HCJsonFields.Has(text, "TickWeight_ROLES") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_ROLES", decoded.TickWeight_ROLES)) { TickWeight_ROLES = decoded.TickWeight_ROLES; }
        if (HCJsonFields.Has(text, "TickWeight_FORMATION") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_FORMATION", decoded.TickWeight_FORMATION)) { TickWeight_FORMATION = decoded.TickWeight_FORMATION; }
        if (HCJsonFields.Has(text, "TickWeight_CARFIX") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_CARFIX", decoded.TickWeight_CARFIX)) { TickWeight_CARFIX = decoded.TickWeight_CARFIX; }
        if (HCJsonFields.Has(text, "TickWeight_HEARTH") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_HEARTH", decoded.TickWeight_HEARTH)) { TickWeight_HEARTH = decoded.TickWeight_HEARTH; }
        if (HCJsonFields.Has(text, "TickWeight_INCIDENTS") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_INCIDENTS", decoded.TickWeight_INCIDENTS)) { TickWeight_INCIDENTS = decoded.TickWeight_INCIDENTS; }
        if (HCJsonFields.Has(text, "TickWeight_INCIDENT_RESPONSE") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_INCIDENT_RESPONSE", decoded.TickWeight_INCIDENT_RESPONSE)) { TickWeight_INCIDENT_RESPONSE = decoded.TickWeight_INCIDENT_RESPONSE; }
        if (HCJsonFields.Has(text, "TickWeight_AI_RESPAWN") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_AI_RESPAWN", decoded.TickWeight_AI_RESPAWN)) { TickWeight_AI_RESPAWN = decoded.TickWeight_AI_RESPAWN; }
        if (HCJsonFields.Has(text, "TickWeight_SEARCH_COMPACT") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_SEARCH_COMPACT", decoded.TickWeight_SEARCH_COMPACT)) { TickWeight_SEARCH_COMPACT = decoded.TickWeight_SEARCH_COMPACT; }
        if (HCJsonFields.Has(text, "TickWeight_SHELTER") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_SHELTER", decoded.TickWeight_SHELTER)) { TickWeight_SHELTER = decoded.TickWeight_SHELTER; }
        if (HCJsonFields.Has(text, "TickWeight_AI_SITES") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_AI_SITES", decoded.TickWeight_AI_SITES)) { TickWeight_AI_SITES = decoded.TickWeight_AI_SITES; }
        if (HCJsonFields.Has(text, "TickWeight_STORY_INDEX") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_STORY_INDEX", decoded.TickWeight_STORY_INDEX)) { TickWeight_STORY_INDEX = decoded.TickWeight_STORY_INDEX; }
        if (HCJsonFields.Has(text, "TickWeight_AI_ROUTES") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_AI_ROUTES", decoded.TickWeight_AI_ROUTES)) { TickWeight_AI_ROUTES = decoded.TickWeight_AI_ROUTES; }
        if (HCJsonFields.Has(text, "TickWeight_POLICE_BIND") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_POLICE_BIND", decoded.TickWeight_POLICE_BIND)) { TickWeight_POLICE_BIND = decoded.TickWeight_POLICE_BIND; }
        if (HCJsonFields.Has(text, "TickWeight_ROADS") && HCOperatorSettingsRegistry.HCValid("Performance.TickWeight_ROADS", decoded.TickWeight_ROADS)) { TickWeight_ROADS = decoded.TickWeight_ROADS; }
        if (HCJsonFields.Has(text, "EnableSharedSaves")) { EnableSharedSaves = decoded.EnableSharedSaves; }
        if (HCJsonFields.Has(text, "SliceMs") && HCOperatorSettingsRegistry.HCValid("Performance.SliceMs", decoded.SliceMs)) { SliceMs = decoded.SliceMs; }
        if (HCJsonFields.Has(text, "SaveStageTargetMs") && HCOperatorSettingsRegistry.HCValid("Performance.SaveStageTargetMs", decoded.SaveStageTargetMs)) { SaveStageTargetMs = decoded.SaveStageTargetMs; }
        if (HCJsonFields.Has(text, "EcologyRowsPerTick") && HCOperatorSettingsRegistry.HCValid("Performance.EcologyRowsPerTick", decoded.EcologyRowsPerTick)) { EcologyRowsPerTick = decoded.EcologyRowsPerTick; }
        if (HCJsonFields.Has(text, "InteriorStepsPerTick") && HCOperatorSettingsRegistry.HCValid("Performance.InteriorStepsPerTick", decoded.InteriorStepsPerTick)) { InteriorStepsPerTick = decoded.InteriorStepsPerTick; }
        if (HCJsonFields.Has(text, "HoldoutRowsPerTick") && HCOperatorSettingsRegistry.HCValid("Performance.HoldoutRowsPerTick", decoded.HoldoutRowsPerTick)) { HoldoutRowsPerTick = decoded.HoldoutRowsPerTick; }
        if (HCJsonFields.Has(text, "InteriorPackOnlineMs") && HCOperatorSettingsRegistry.HCValid("Performance.InteriorPackOnlineMs", decoded.InteriorPackOnlineMs)) { InteriorPackOnlineMs = decoded.InteriorPackOnlineMs; }
        if (HCJsonFields.Has(text, "InteriorPackEmptyMs") && HCOperatorSettingsRegistry.HCValid("Performance.InteriorPackEmptyMs", decoded.InteriorPackEmptyMs)) { InteriorPackEmptyMs = decoded.InteriorPackEmptyMs; }
        if (HCJsonFields.Has(text, "InteriorPackUnitsPerTick") && HCOperatorSettingsRegistry.HCValid("Performance.InteriorPackUnitsPerTick", decoded.InteriorPackUnitsPerTick)) { InteriorPackUnitsPerTick = decoded.InteriorPackUnitsPerTick; }
        if (HCJsonFields.Has(text, "DebugSnapshotIntervalSeconds") && HCOperatorSettingsRegistry.HCValid("Performance.DebugSnapshotIntervalSeconds", decoded.DebugSnapshotIntervalSeconds)) { DebugSnapshotIntervalSeconds = decoded.DebugSnapshotIntervalSeconds; }
    }
}

// Reuses the existing clock guard and retained caller cursors. A path probe/file
// read cannot be preempted; always report native acceptance as pending.
class HCPerfSlices : HCWorkBudget
{
    protected string m_Profile;
    void HCPerfSlices(string profile) { m_Profile = profile; }

    override void HCReset(int limit, float milliseconds = 4)
    {
        HCPerfConfig config = HCPerfConfig.HCGet();
        // Ecology reserves its first row before consulting the clock guard.
        if (m_Profile == "Ecology") { limit = Math.Min(limit, config.EcologyRowsPerTick) - 1; }
        if (m_Profile == "Interiors") { limit = Math.Min(limit, config.InteriorStepsPerTick); }
        if (m_Profile == "Holdouts") { limit = Math.Min(limit, config.HoldoutRowsPerTick); }
        milliseconds = Math.Min(milliseconds, config.SliceMs);
        super.HCReset(limit, milliseconds);
    }
}


// perfboot: high-resolution cooperative clock for retained boot/save work.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:106 TickCount.
// Calibrate across owner ticks using the core's elapsed seconds, never assume
// CPU-counter units. Before the second tick admit only one atomic unit.
// Deadlines cannot interrupt a native call; retain the item cap as a backstop.
class HCPerfBootBudget : HCWorkBudget
{
    protected bool m_ClockSeeded;
    protected int m_PreviousTick;
    protected float m_TicksPerMs;
    protected int m_RawStart;
    protected float m_RawDeadline;

    void HCFrame(float deltaTime)
    {
        if (m_ClockSeeded && deltaTime > 0)
        {
            int elapsedTicks = TickCount(m_PreviousTick);
            if (elapsedTicks > 0) { m_TicksPerMs = elapsedTicks / (deltaTime * 1000); }
        }
        m_PreviousTick = TickCount(0);
        m_ClockSeeded = true;
    }

    override void HCReset(int limit, float milliseconds = 4)
    {
        m_RawStart = TickCount(0);
        m_RawDeadline = milliseconds * m_TicksPerMs;
        m_Limit = limit;
        if (!(m_TicksPerMs > 0)) { m_Limit = 1; }
        m_Used = 0;
    }

    override bool HCContinue()
    {
        if (m_Used >= m_Limit) { return false; }
        if (m_TicksPerMs > 0 && TickCount(m_RawStart) >= m_RawDeadline) { return false; }
        m_Used = m_Used + 1;
        return true;
    }
}
