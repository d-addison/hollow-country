// Migration code uses the fixture counter variant.
class HCProbeStore
{
    void MigrateV1()
    {
        HCModuleReadiness.HCUseFixture("Probe", "migrated");
    }
}
