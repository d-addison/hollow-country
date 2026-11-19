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

