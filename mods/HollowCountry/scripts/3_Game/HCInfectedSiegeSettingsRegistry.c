// InfectedSiege (optional $profile:HollowCountry/gc-infected-siege.json) settings keys.
// Consumer: HCInfectedSiegeConfig (4_World/Infected/Siege). The registry extension stays
// in the same 3_Game module as its base; only string metadata names the 4_World owner.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_HCInfectedSiegeRegistered;
    static void HCInfectedSiegeInit()
    {
        HCInit();
        if (s_HCInfectedSiegeRegistered) { return; }
        s_HCInfectedSiegeRegistered = true;
        HCAdd("InfectedSiege.Enabled", "bool", 1, 0, 1, "HCInfectedSiegeConfig");
        HCAdd("InfectedSiege.GatherSeconds", "float", 8, 3, 60, "HCInfectedSiegeConfig");
        HCAdd("InfectedSiege.NoiseSeconds", "float", 20, 10, 120, "HCInfectedSiegeConfig");
        HCAdd("InfectedSiege.NoiseStrengthMultiplier", "float", 17, 1, 25, "HCInfectedSiegeConfig");
        HCAdd("InfectedSiege.MaxSieges", "int", 8, 1, 8, "HCInfectedSiegeConfig");
        // Retired 2026-11-23 (a siege never spawns infected): still registered so an old operator
        // file loads; the value is ignored and a non-zero one is reported once at start.
        HCAdd("InfectedSiege.ReinforcePerPlayerWindow", "int", 0, 0, 8, "HCInfectedSiegeConfig");
    }
}
