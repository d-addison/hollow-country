// Executed inside the actual server script VM when the addon is loaded.
// A source file or Python PASS is not evidence that these have run.
class HCNativeSelfTests
{
    static bool Run()
    {
        HCSettings settings = new HCSettings();
        if (HCSettings.AcceptDocumentLength(0) || HCSettings.AcceptDocumentLength(16385)) return false;
        if (!HCSettings.AcceptDocumentLength(1) || !HCSettings.AcceptDocumentLength(16384)) return false;
        string error;
        if (!settings.Validate(error)) return false;
        if (settings.EnableInteriors || settings.EnableSearch || settings.EnableCrafting || settings.EnableInfected || settings.EnableHordes || settings.EnableAlertChains) return false;
        settings.MaxTickWorkItems = 0;
        if (settings.Validate(error)) return false;
        settings.MaxTickWorkItems = 32;
        settings.EnableSearch = true;
        if (settings.Validate(error)) return false;
        settings.EnableInteriors = true;
        if (!settings.Validate(error)) return false;
        settings.SchemaVersion = 2;
        if (settings.Validate(error)) return false;
        Print("[HollowCountry][SelfTest] Core settings PASS in native script VM");
        return true;
    }
}
