// InfectedClimb (optional $profile:HollowCountry/gc-infected-climb.json) settings keys.
// Consumer: HCInfectedClimbConfig (4_World/Infected/Climb). The registry extension stays
// in the same 3_Game module as its base; only string metadata names the 4_World owner.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_HCInfectedClimbRegistered;
    static void HCInfectedClimbInit()
    {
        HCInit();
        if (s_HCInfectedClimbRegistered) { return; }
        s_HCInfectedClimbRegistered = true;
        HCAdd("InfectedClimb.Enabled", "bool", 1, 0, 1, "HCInfectedClimbConfig");
        HCAdd("InfectedClimb.MinHeightMetres", "float", 0.5, 0.3, 1, "HCInfectedClimbConfig");
        HCAdd("InfectedClimb.MaxHeightMetres", "float", 2.2, 1.2, 2.5, "HCInfectedClimbConfig");
        HCAdd("InfectedClimb.MaxHorizontalMetres", "float", 2.5, 0.5, 3, "HCInfectedClimbConfig");
        HCAdd("InfectedClimb.FacingDegrees", "float", 35, 5, 60, "HCInfectedClimbConfig");
        HCAdd("InfectedClimb.CooldownSeconds", "float", 6, 2, 60, "HCInfectedClimbConfig");
        HCAdd("InfectedClimb.Concurrent", "int", 4, 1, 8, "HCInfectedClimbConfig");
        HCAdd("InfectedClimb.RouteCacheSeconds", "float", 3, 1, 15, "HCInfectedClimbConfig");
        HCAdd("InfectedClimb.OutcomeCapSeconds", "float", 8, 3, 15, "HCInfectedClimbConfig");
        HCAdd("InfectedClimb.RetireAttempts", "int", 12, 3, 50, "HCInfectedClimbConfig");
    }
}
