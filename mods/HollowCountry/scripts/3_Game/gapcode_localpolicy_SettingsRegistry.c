// Scoped tuning registry lives with its base in 3_Game; no 4_World type calls.
// Native map access/Print are inherited from HCOperatorSettingsRegistry.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_LocalPolicyRegistered;
    static void HCLocalPolicyInit()
    {
        HCInit();
        if (s_LocalPolicyRegistered) { return; }
        s_LocalPolicyRegistered = true;
        HCAdd("SignsOfLife.MaxFlies", "int", 6, 0, 6, "HCSignsConfig");
        HCAdd("SignsOfLife.MaxObjects", "int", 512, 1, 512, "HCSignsConfig");
        HCAdd("SignsOfLife.MaxForceLit", "int", 24, 0, 24, "HCSignsConfig");
        HCAdd("SignsOfLife.HouseRadius", "float", 125, 1, 125, "HCSignsConfig");
        HCAdd("SignsOfLife.FlyRadius", "float", 25, 1, 25, "HCSignsConfig");
        HCAdd("SignsOfLife.ScanSeconds", "float", 10, 10, 3600, "HCSignsConfig");
        HCAdd("SignsOfLife.ColdC", "float", 10, -40, 40, "HCSignsConfig");
        HCAdd("SignsOfLife.SummarySeconds", "float", 60, 60, 3600, "HCSignsConfig");
        HCAdd("SignsOfLife.SummaryAreas", "int", 6, 1, 6, "HCSignsConfig");
        HCAdd("SignsOfLife.SnapshotPlayers", "int", 90, 1, 90, "HCSignsConfig");
        HCAdd("LeatherTailoring.Enabled", "bool", 1, 0, 1, "HCAuditLeatherConfig");
        HCAdd("LeatherTailoring.PantsPanels", "int", 3, 2, 8, "HCAuditLeatherConfig");
        HCAdd("LeatherTailoring.VestPanels", "int", 4, 3, 8, "HCAuditLeatherConfig");
        HCAdd("LeatherTailoring.KitUnits", "int", 10, 1, 100, "HCAuditLeatherConfig");
        HCAdd("LeatherTailoring.AnimationUnits", "float", 2, 1, 10, "HCAuditLeatherConfig");
        HCAdd("Signals.Enabled", "bool", 1, 0, 1, "HCSignalConfig");
        HCAdd("Signals.CooldownMs", "int", 30000, 1000, 3600000, "HCSignalConfig");
        HCAdd("Signals.MaxNotices", "int", 128, 1, 128, "HCSignalConfig");
    }
}
