// Scheduler throughput metadata stays in the registry's 3_Game module.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_HCSaveThroughputRegistered;

    static void HCSaveThroughputInit()
    {
        HCInit();
        if (s_HCSaveThroughputRegistered) { return; }
        s_HCSaveThroughputRegistered = true;
        HCAdd("WorldRuntime.SaveStagesPerTick", "int", 8, 1, 8, "HCWorldRuntimeConfig");
    }
}
