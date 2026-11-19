// w45 #138/#203: same script layer as the base registry; no later-layer hook.
// Scoped controls reuse HCAdd/HCValid. The authoring JSON/validator scope is
// owned by the lead; exact integration rows are in the w45 report.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_PerfRegistered;
    static void HCPerfInit()
    {
        HCInit();
        if (s_PerfRegistered) { return; }
        s_PerfRegistered = true;
        HCAdd("Performance.EnableSharedSaves", "bool", 1, 0, 1, "HCPerfConfig");
        HCAdd("Performance.SliceMs", "int", 4, 1, 10, "HCPerfConfig");
        HCAdd("Performance.SaveStageTargetMs", "int", 10, 1, 10, "HCPerfConfig");
        HCAdd("Performance.EcologyRowsPerTick", "int", 4, 1, 32, "HCPerfConfig");
        HCAdd("Performance.InteriorStepsPerTick", "int", 1, 1, 4, "HCPerfConfig");
        HCAdd("Performance.HoldoutRowsPerTick", "int", 1, 1, 4, "HCPerfConfig");
        HCAdd("Performance.InteriorPackOnlineMs", "int", 25, 1, 50, "HCPerfConfig");
        HCAdd("Performance.InteriorPackEmptyMs", "int", 150, 1, 250, "HCPerfConfig");
        HCAdd("Performance.InteriorPackUnitsPerTick", "int", 4096, 2, 65536, "HCPerfConfig");
        HCAdd("Performance.DebugSnapshotIntervalSeconds", "int", 300, 30, 3600, "HCPerfConfig");
    }
}
