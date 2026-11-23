// W6: composed-site guard tunables. Same 3_Game layer as the registry base; only the string owner
// "HCSiteGuard" names the 4_World reader (HCSiteConfig). No 4_World type is referenced here.
// Values are read once from the optional profile file sites-config.json through HCSiteConfig.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_SitesRegistered;
    static void HCSitesInit()
    {
        HCInit();
        if (s_SitesRegistered) { return; }
        s_SitesRegistered = true;
        HCAdd("Sites.DecideDelaySeconds", "int", 60, 30, 600, "HCSiteGuard");
        HCAdd("Sites.QuietWindowSeconds", "int", 10, 5, 120, "HCSiteGuard");
        HCAdd("Sites.BaseMarginM", "int", 15, 5, 60, "HCSiteGuard");
        HCAdd("Sites.UnitsPerGrant", "int", 8, 1, 16, "HCSiteGuard");
        HCAdd("Sites.PlayerClearM", "int", 30, 10, 100, "HCSiteGuard");
        HCAdd("Sites.OccupiedRetryBoots", "int", 3, 1, 10, "HCSiteGuard");
    }
}
