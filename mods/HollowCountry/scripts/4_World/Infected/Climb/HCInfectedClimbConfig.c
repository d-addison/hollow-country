// Optional $profile:HollowCountry/gc-infected-climb.json for the InfectedReach climb
// (native vault toward an elevated, unreachable target). Absent fields keep these
// defaults; explicit "Enabled": false opts out. Registry rows: 3_Game
// HCInfectedClimbSettingsRegistry.c (InfectedClimb.*), consulted by HCValid.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnConvert.c:30,115 int/float ToString. Bounded HCGroupIO + HCJsonFields.
class HCInfectedClimbConfig
{
    bool Enabled = true;
    float MinHeightMetres = 0.5;
    float MaxHeightMetres = 2.2;
    float MaxHorizontalMetres = 2.5;
    float FacingDegrees = 35;
    float CooldownSeconds = 6;
    int Concurrent = 4;
    float RouteCacheSeconds = 3;
    float OutcomeCapSeconds = 8;
    int RetireAttempts = 12;

    protected string m_LastRefusal;
    void HCRefuse(string reason)
    {
        if (m_LastRefusal == reason) { return; }
        m_LastRefusal = reason;
        Print("[HC Reach] climb config_refused=" + reason + " defaults_retained runtime=PENDING");
    }

    bool HCValid(string key, float value, float low, float high)
    {
        if (!(value >= low && value <= high)) { HCRefuse(key); return false; }
        HCOperatorSettingsRegistry.HCInfectedClimbInit();
        string fullKey = "InfectedClimb." + key;
        if (HCOperatorSettingsRegistry.HCFind(fullKey) && !HCOperatorSettingsRegistry.HCValid(fullKey, value)) { HCRefuse(key); return false; }
        return true;
    }

    void HCLoad()
    {
        HCOperatorSettingsRegistry.HCInfectedClimbInit();
        string path = "$profile:HollowCountry/gc-infected-climb.json";
        if (!FileExist(path)) { return; }
        string text;
        string error;
        HCInfectedClimbConfig decoded;
        if (!HCGroupIO.Read(path, 4096, text)) { HCRefuse("read"); return; }
        if (!JsonFileLoader<HCInfectedClimbConfig>.LoadData(text, decoded, error) || !decoded) { HCRefuse("json"); return; }
        if (HCJsonFields.Has(text, "Enabled")) { Enabled = decoded.Enabled; }
        if (HCJsonFields.Has(text, "MinHeightMetres") && HCValid("MinHeightMetres", decoded.MinHeightMetres, 0.3, 1)) { MinHeightMetres = decoded.MinHeightMetres; }
        if (HCJsonFields.Has(text, "MaxHeightMetres") && HCValid("MaxHeightMetres", decoded.MaxHeightMetres, 1.2, 2.5)) { MaxHeightMetres = decoded.MaxHeightMetres; }
        if (HCJsonFields.Has(text, "MaxHorizontalMetres") && HCValid("MaxHorizontalMetres", decoded.MaxHorizontalMetres, 0.5, 3)) { MaxHorizontalMetres = decoded.MaxHorizontalMetres; }
        if (HCJsonFields.Has(text, "FacingDegrees") && HCValid("FacingDegrees", decoded.FacingDegrees, 5, 60)) { FacingDegrees = decoded.FacingDegrees; }
        if (HCJsonFields.Has(text, "CooldownSeconds") && HCValid("CooldownSeconds", decoded.CooldownSeconds, 2, 60)) { CooldownSeconds = decoded.CooldownSeconds; }
        if (HCJsonFields.Has(text, "Concurrent") && HCValid("Concurrent", decoded.Concurrent, 1, 8)) { Concurrent = decoded.Concurrent; }
        if (HCJsonFields.Has(text, "RouteCacheSeconds") && HCValid("RouteCacheSeconds", decoded.RouteCacheSeconds, 1, 15)) { RouteCacheSeconds = decoded.RouteCacheSeconds; }
        if (HCJsonFields.Has(text, "OutcomeCapSeconds") && HCValid("OutcomeCapSeconds", decoded.OutcomeCapSeconds, 3, 15)) { OutcomeCapSeconds = decoded.OutcomeCapSeconds; }
        if (HCJsonFields.Has(text, "RetireAttempts") && HCValid("RetireAttempts", decoded.RetireAttempts, 3, 50)) { RetireAttempts = decoded.RetireAttempts; }
        if (MinHeightMetres >= MaxHeightMetres)
        {
            HCRefuse("height_band");
            MinHeightMetres = 0.5;
            MaxHeightMetres = 2.2;
        }
    }

    void HCLog()
    {
        Print("[HC Reach] climb effective Enabled=" + HCV2Admission.OnOff(Enabled) + " MinHeightMetres=" + MinHeightMetres.ToString() + " MaxHeightMetres=" + MaxHeightMetres.ToString() + " MaxHorizontalMetres=" + MaxHorizontalMetres.ToString() + " runtime=PENDING");
        Print("[HC Reach] climb effective FacingDegrees=" + FacingDegrees.ToString() + " CooldownSeconds=" + CooldownSeconds.ToString() + " Concurrent=" + Concurrent.ToString() + " RouteCacheSeconds=" + RouteCacheSeconds.ToString() + " OutcomeCapSeconds=" + OutcomeCapSeconds.ToString() + " RetireAttempts=" + RetireAttempts.ToString() + " runtime=PENDING");
    }
}
