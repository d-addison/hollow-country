// Optional tuning only; absent keys retain declared defaults (native JSON zero-fills).
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print.
// HCGroupIO.Read owns bounded native file IO; HCJsonFields owns key presence.
class HCFuelSiphonConfig
{
    float ReachMeters = 2.0;
    float ContactToleranceMeters = 0.5;
    int MaxSessions = 96;
    int LeaseMs = 10000;
    float DiagnosticStepSeconds = 1.0;
    float RepeatSeconds = 0.5;
    protected static ref HCFuelSiphonConfig s_Config;

    bool HCNormalize(string text)
    {
        bool invalid = false;
        if (!HCJsonFields.Has(text, "ReachMeters")) { this.ReachMeters = 2.0; }
        if (!(this.ReachMeters >= 0.5 && this.ReachMeters <= 2)) { this.ReachMeters = 2.0; invalid = true; }
        if (!HCJsonFields.Has(text, "ContactToleranceMeters")) { this.ContactToleranceMeters = 0.5; }
        if (!(this.ContactToleranceMeters >= 0.01 && this.ContactToleranceMeters <= 0.5)) { this.ContactToleranceMeters = 0.5; invalid = true; }
        if (!HCJsonFields.Has(text, "MaxSessions")) { this.MaxSessions = 96; }
        if (!(this.MaxSessions >= 1 && this.MaxSessions <= 96)) { this.MaxSessions = 96; invalid = true; }
        if (!HCJsonFields.Has(text, "LeaseMs")) { this.LeaseMs = 10000; }
        if (!(this.LeaseMs >= 1000 && this.LeaseMs <= 10000)) { this.LeaseMs = 10000; invalid = true; }
        if (!HCJsonFields.Has(text, "DiagnosticStepSeconds")) { this.DiagnosticStepSeconds = 1.0; }
        if (!(this.DiagnosticStepSeconds >= 0.1 && this.DiagnosticStepSeconds <= 1)) { this.DiagnosticStepSeconds = 1.0; invalid = true; }
        if (!HCJsonFields.Has(text, "RepeatSeconds")) { this.RepeatSeconds = 0.5; }
        if (!(this.RepeatSeconds >= 0.1 && this.RepeatSeconds <= 1)) { this.RepeatSeconds = 0.5; invalid = true; }
        return invalid;
    }
    static HCFuelSiphonConfig Get()
    {
        if (s_Config) { return s_Config; }
        s_Config = new HCFuelSiphonConfig;
        string path = "$profile:HollowCountry/fuel-siphon.json";
        if (!FileExist(path)) { return s_Config; }
        string text;
        string error;
        HCFuelSiphonConfig loaded;
        if (!HCGroupIO.Read(path, 16384, text) || !JsonFileLoader<HCFuelSiphonConfig>.LoadData(text, loaded, error) || !loaded)
        {
            Print("[HC Config] HCFuelSiphonConfig invalid_json defaults_restored runtime=PENDING");
            return s_Config;
        }
        bool invalid = loaded.HCNormalize(text);
        s_Config = loaded;
        if (invalid) { Print("[HC Config] HCFuelSiphonConfig invalid_range defaults_restored runtime=PENDING"); }
        return s_Config;
    }
}

