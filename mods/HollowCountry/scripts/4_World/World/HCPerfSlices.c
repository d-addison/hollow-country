// w45 #138/#203. Optional $profile:HollowCountry/performance.json, read once.
// Missing keys retain defaults through HCJsonFields (native loader zero-fills).
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist; 3_Game/tools/JsonFileLoader.c:69
// LoadData; 1_Core/proto/EnMath.c:553 Min; EnDebug.c:96 Print.
// HCGroupIO uses bounded verified native file IO.
class HCPerfConfig
{
    bool EnableSharedSaves = true;
    int SliceMs = 4;
    int StartupFrameMs = 4;
    int StartupDeadlineSeconds = 30;
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
    protected string m_WeightText;
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

    // Boot-only lookup in the already size-bounded, successfully parsed JSON.
    // Reuse shared text windows/key matching (including escaped JSON keys).
    // The native JSON loader validates the numeric token; strings, fractions,
    // nested lookalikes and out-of-range values retain the table default.
    int HCWeight(string name, int defaultWeight)
    {
        HCTextWindow text = new HCTextWindow(m_WeightText);
        string key = "TickWeight_" + name;
        int depth = 0;
        int cursor = 0;
        while (cursor < text.Length())
        {
            string token = text.At(cursor);
            if (token == "\"")
            {
                int start = cursor + 1;
                cursor = start;
                while (cursor < text.Length() && text.At(cursor) != "\"")
                {
                    if (text.At(cursor) == "\\") { cursor++; }
                    cursor++;
                }
                int stop = cursor;
                cursor++;
                while (cursor < text.Length() && HCWeightSpace(text.At(cursor))) { cursor++; }
                if (depth == 1 && text.At(cursor) == ":" && HCJsonFields.KeyMatchesAt(text, start, stop, key))
                {
                    cursor++;
                    while (cursor < text.Length() && HCWeightSpace(text.At(cursor))) { cursor++; }
                    int valueStart = cursor;
                    while (cursor < text.Length() && text.At(cursor) != "," && text.At(cursor) != "}") { cursor++; }
                    int value;
                    string error;
                    string number = text.Range(valueStart, cursor - valueStart);
                    if (JsonFileLoader<int>.LoadData(number, value, error) && HCOperatorSettingsRegistry.HCValid("Performance." + key, value)) { return value; }
                    return defaultWeight;
                }
                continue;
            }
            if (token == "{" || token == "[") { depth++; }
            if (token == "}" || token == "]") { depth--; }
            cursor++;
        }
        return defaultWeight;
    }

    protected bool HCWeightSpace(string token)
    {
        return token == " " || token == "\t" || token == "\r" || token == "\n";
    }

    void HCApply(HCPerfConfig decoded, string text)
    {
        m_WeightText = text;
        if (HCJsonFields.Has(text, "EnableSharedSaves")) { EnableSharedSaves = decoded.EnableSharedSaves; }
        if (HCJsonFields.Has(text, "StartupFrameMs") && HCOperatorSettingsRegistry.HCValid("Performance.StartupFrameMs", decoded.StartupFrameMs)) { StartupFrameMs = decoded.StartupFrameMs; }
        if (HCJsonFields.Has(text, "StartupDeadlineSeconds") && HCOperatorSettingsRegistry.HCValid("Performance.StartupDeadlineSeconds", decoded.StartupDeadlineSeconds)) { StartupDeadlineSeconds = decoded.StartupDeadlineSeconds; }
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
        if (m_Profile == "ZoneGuards") { limit = Math.Min(limit, 1); }
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
    // Compatibility surface: all retained slices now use HCWorkBudget's clock.
    void HCFrame(float deltaTime) { HCWorkBudget.HCCalibrate(); }
}
