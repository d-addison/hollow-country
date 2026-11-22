// Scoped interiors-query.json preference; same script layer as the registry.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_InteriorQueryRegistered;
    static void HCInteriorQueryInit()
    {
        HCInit();
        if (s_InteriorQueryRegistered) { return; }
        s_InteriorQueryRegistered = true;
        HCAdd("InteriorsQuery.UseSphereLookup", "bool", 1, 0, 1, "HCInteriorQueryConfig");
    }
}
