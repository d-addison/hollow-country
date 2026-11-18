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
        if (!GetExpansionSettings() || !GetExpansionSettings().GetAI() || !GetExpansionSettings().GetAI().IsLoaded()) { return "Expansion AI settings not loaded"; }
        if (!GetExpansionSettings().GetAIPatrol(false) || !GetExpansionSettings().GetAIPatrol(false).IsLoaded()) { return "provider patrol settings not loaded"; }
        ExpansionAISettings settings = GetExpansionSettings().GetAI();
        return HCXAIRules.ProviderProblem(eAIBase.s_eAI_UnlimitedReload == 0 && eAIBase.s_eAI_UnlimitedReloadAll == 0, settings.CanRecruitFriendly, settings.CanRecruitGuards, !GetExpansionSettings().GetAIPatrol(false).Enabled);
    }

    static bool Qualified() { return false; }
    static bool LocalAcceptanceOptIn()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!s_Probed)
        {
            s_OptIn = !FileExist("$profile:HollowCountry/acceptance/pve_patrols.disable");
            s_Probed = true;
            if (s_OptIn) { Print("[HC Expansion AI] EXPERIMENTAL on by default (opt out: pve_patrols.disable); qualification pending"); }
        }
        return s_OptIn;
    }
    static bool Admitted()
    {
        return HCXAIQualification.Qualified() || HCXAIQualification.LocalAcceptanceOptIn();
    }
}
