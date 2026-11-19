// W69: registry extension stays in the same 3_Game layer as its base.
// Only string metadata names HCHearthConfig; no 4_World type is referenced here.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_HearthRegistered;
    static void HCHearthInit()
    {
        HCInit();
        if (s_HearthRegistered) { return; }
        s_HearthRegistered = true;
        HCAdd("HearthFires.Enabled", "bool", 1, 0, 1, "HCHearthConfig");
        HCAdd("HearthFires.MaxHearths", "int", 64, 1, 256, "HCHearthConfig");
        HCAdd("HearthFires.MaxObjects", "int", 128, 1, 512, "HCHearthConfig");
        HCAdd("HearthFires.MaxInventory", "int", 64, 1, 256, "HCHearthConfig");
        HCAdd("HearthFires.HearthsPerTick", "int", 4, 1, 32, "HCHearthConfig");
        HCAdd("HearthFires.HousesPerScan", "int", 16, 1, 64, "HCHearthConfig");
        HCAdd("HearthFires.MaxLit", "int", 4, 1, 24, "HCHearthConfig");
        HCAdd("HearthFires.MaxSmoke", "int", 2, 1, 24, "HCHearthConfig");
        HCAdd("HearthFires.QueryRadius", "float", 30, 1, 100, "HCHearthConfig");
        HCAdd("HearthFires.AnchorTolerance", "float", 0.35, 0.05, 1, "HCHearthConfig");
        HCAdd("HearthFires.ActorRange", "float", 3, 0.5, 5, "HCHearthConfig");
        HCAdd("HearthFires.ObserverRadius", "float", 500, 100, 2000, "HCHearthConfig");
        HCAdd("HearthFires.AttemptSeconds", "int", 60, 10, 3600, "HCHearthConfig");
    }
}
