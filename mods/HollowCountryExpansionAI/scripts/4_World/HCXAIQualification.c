// Local acceptance is an operator opt-in; no gameplay qualification is inferred.
class HCXAIQualification
{
    protected static bool s_Probed;
    protected static bool s_OptIn;

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
