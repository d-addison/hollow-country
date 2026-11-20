// ZoneGuards (HollowCountryExpansionAI) settings keys. The registry extension stays in the
// same 3_Game module as its base; only string metadata names HCXZoneGuardsConfig.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_HCZonesRegistered;
    static void HCZoneGuardsInit()
    {
        HCInit();
        if (s_HCZonesRegistered) { return; }
        s_HCZonesRegistered = true;
        HCAdd("HCZoneGuards.Disabled", "bool", 0, 0, 1, "HCXZoneGuardsConfig");
        HCAdd("HCZoneGuards.CooldownDays", "int", 2, 1, 30, "HCXZoneGuardsConfig");
        HCAdd("HCZoneGuards.MaxChangesPerDay", "int", 2, 1, 2, "HCXZoneGuardsConfig");
        HCAdd("HCZoneGuards.MaxZones", "int", 128, 1, 128, "HCXZoneGuardsConfig");
        HCAdd("HCZoneGuards.MaxOverrunMembers", "int", 6, 3, 6, "HCXZoneGuardsConfig");
    }
}
