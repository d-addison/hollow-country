// #226 optional client-local tuning, defaults ON. No server/gameplay writes.
// Native scripts-1.30.164289: EnSystem.c:397 FileExist (1_Core/proto),
// 3_Game/tools/JsonFileLoader.c:69 LoadData; EnDebug.c:96 Print (1_Core/proto).
// HCGroupIO bounds reads; HCJsonFields prevents zero-fill erasing defaults.
// Restart client to reload. Existing HC-27 grade preference remains authoritative.
class auditleaves_Config
{
    bool Enabled = true;
    float SampleSeconds = 0.5;
    float QuerySeconds = 10;
    float QueryRadius = 12;
    int MaxObjects = 64;
    float LifetimeSeconds = 3;
    float MinTreeHeight = 3;
    float MaxTreeHeight = 40;
    float CanopyFraction = 0.75;
    static auditleaves_Config HCLoad()
    {
        HCOperatorSettingsRegistry.HCAuditLeavesInit();
        auditleaves_Config config = new auditleaves_Config;
        string path = "$profile:HollowCountry/auditleaves_settings.json";
        if (!FileExist(path)) { return config; }
        string image;
        string error;
        auditleaves_Config decoded;
        if (!HCGroupIO.Read(path, 4096, image) || !JsonFileLoader<auditleaves_Config>.LoadData(image, decoded, error) || !decoded)
        {
            config.Enabled = false;
            Print("[HC Leaves] HC_LEAVES_CONFIG_REFUSED runtime=PENDING");
            return config;
        }
        config.HCApply(decoded, image);
        if (config.MinTreeHeight > config.MaxTreeHeight) { config.Enabled = false; }
        return config;
    }

    void HCApply(auditleaves_Config decoded, string image)
    {
        if (HCJsonFields.Has(image, "Enabled") && HCOperatorSettingsRegistry.HCValid("SeasonLeaves.Enabled", decoded.Enabled)) { Enabled = decoded.Enabled; }
        if (HCJsonFields.Has(image, "SampleSeconds") && HCOperatorSettingsRegistry.HCValid("SeasonLeaves.SampleSeconds", decoded.SampleSeconds)) { SampleSeconds = decoded.SampleSeconds; }
        if (HCJsonFields.Has(image, "QuerySeconds") && HCOperatorSettingsRegistry.HCValid("SeasonLeaves.QuerySeconds", decoded.QuerySeconds)) { QuerySeconds = decoded.QuerySeconds; }
        if (HCJsonFields.Has(image, "QueryRadius") && HCOperatorSettingsRegistry.HCValid("SeasonLeaves.QueryRadius", decoded.QueryRadius)) { QueryRadius = decoded.QueryRadius; }
        if (HCJsonFields.Has(image, "MaxObjects") && HCOperatorSettingsRegistry.HCValid("SeasonLeaves.MaxObjects", decoded.MaxObjects)) { MaxObjects = decoded.MaxObjects; }
        if (HCJsonFields.Has(image, "LifetimeSeconds") && HCOperatorSettingsRegistry.HCValid("SeasonLeaves.LifetimeSeconds", decoded.LifetimeSeconds)) { LifetimeSeconds = decoded.LifetimeSeconds; }
        if (HCJsonFields.Has(image, "MinTreeHeight") && HCOperatorSettingsRegistry.HCValid("SeasonLeaves.MinTreeHeight", decoded.MinTreeHeight)) { MinTreeHeight = decoded.MinTreeHeight; }
        if (HCJsonFields.Has(image, "MaxTreeHeight") && HCOperatorSettingsRegistry.HCValid("SeasonLeaves.MaxTreeHeight", decoded.MaxTreeHeight)) { MaxTreeHeight = decoded.MaxTreeHeight; }
        if (HCJsonFields.Has(image, "CanopyFraction") && HCOperatorSettingsRegistry.HCValid("SeasonLeaves.CanopyFraction", decoded.CanopyFraction)) { CanopyFraction = decoded.CanopyFraction; }
    }
}

// Scoped registry initialization follows the existing HCHearthInit pattern.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_AuditLeavesRegistered;
    static void HCAuditLeavesInit()
    {
        HCInit();
        if (s_AuditLeavesRegistered) { return; }
        s_AuditLeavesRegistered = true;
        HCAdd("SeasonLeaves.Enabled", "bool", 1, 0, 1, "auditleaves_Config");
        HCAdd("SeasonLeaves.SampleSeconds", "float", 0.5, 0.1, 2, "auditleaves_Config");
        HCAdd("SeasonLeaves.QuerySeconds", "float", 10, 2, 120, "auditleaves_Config");
        HCAdd("SeasonLeaves.QueryRadius", "float", 12, 2, 30, "auditleaves_Config");
        HCAdd("SeasonLeaves.MaxObjects", "int", 64, 1, 256, "auditleaves_Config");
        HCAdd("SeasonLeaves.LifetimeSeconds", "float", 3, 0.5, 10, "auditleaves_Config");
        HCAdd("SeasonLeaves.MinTreeHeight", "float", 3, 1, 10, "auditleaves_Config");
        HCAdd("SeasonLeaves.MaxTreeHeight", "float", 40, 10, 60, "auditleaves_Config");
        HCAdd("SeasonLeaves.CanopyFraction", "float", 0.75, 0.25, 1, "auditleaves_Config");
    }
}
