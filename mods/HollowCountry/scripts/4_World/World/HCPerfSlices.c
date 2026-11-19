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
