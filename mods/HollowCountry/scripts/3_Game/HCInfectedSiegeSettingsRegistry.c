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
        HCAdd("InfectedSiege.MaxSieges", "int", 8, 1, 8, "HCInfectedSiegeConfig");
        HCAdd("InfectedSiege.ReinforcePerPlayerWindow", "int", 4, 0, 8, "HCInfectedSiegeConfig");
    }
}
