// Local acceptance is an operator opt-in; no gameplay qualification is inferred.
class HCXAIQualification
{
    protected static bool s_Probed;
    protected static bool s_OptIn;

    // V2 preference is installed by its own module; experiment verdicts stay
    // diagnostic. The legacy marker path below keeps its original meaning.
    protected static bool s_EncountersEnabled;
    static void SetEncountersEnabled(bool enabled) { s_EncountersEnabled = enabled; }
    static bool EncountersEnabled() { return s_EncountersEnabled; }

    // Installed ai_scripts.pbo: 3_Game/DayZExpansion_AI/Settings/
    // ExpansionAISettings.c:51-52 recruiting; Patrols/ExpansionAIPatrolSettings.c:15
    // Enabled; existing adapter reads reload masks.
    static string ProviderProblem()
    {
        if (!GetGame() || !GetGame().IsServer()) { return "server authority required"; }
        if (!HCXExpansionBridge.HCSettings()) { return "Expansion AI settings not loaded"; }
        if (!HCXExpansionBridge.HCPatrolSettings()) { return "provider patrol settings not loaded"; }
        ExpansionAISettings settings = HCXExpansionBridge.HCSettings();
        ExpansionAIPatrolSettings patrols = HCXExpansionBridge.HCPatrolSettings();
        if (!settings || !patrols) { return "Expansion AI settings not loaded"; }
        return HCXAIRules.ProviderProblem(eAIBase.s_eAI_UnlimitedReload == 0 && eAIBase.s_eAI_UnlimitedReloadAll == 0, settings.CanRecruitFriendly, settings.CanRecruitGuards, !patrols.Enabled);
    }

    static bool Qualified() { return false; }
    static bool LocalAcceptanceOptIn()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!s_Probed)
        {
            // The opt-out file named by the V1 admission line (pve_patrols); the
            // literal path stays here for the acceptance-marker inventory.
            s_OptIn = !FileExist("$profile:HollowCountry/acceptance/pve_patrols.disable");
            s_Probed = true;
            Print(HCV1Admission.Line("PvePatrols", s_OptIn, "pve_patrols", false));
        }
        return s_OptIn;
    }
    static bool Admitted()
    {
        return HCXAIQualification.Qualified() || HCXAIQualification.LocalAcceptanceOptIn();
    }
}
