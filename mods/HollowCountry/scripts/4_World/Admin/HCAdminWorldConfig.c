// Reuses bounded HCGroupIO/HCJsonFields configuration IO. Native:
// scripts-1.30.164289/3_Game/tools/JsonFileLoader.c:69 LoadData;
// 1_Core/proto/EnSystem.c:397 FileExist. Missing file/keys retain defaults.
class HCAdminWorldConfig
{
    int RefreshSeconds = 4;
    int RowsPerTick = 32;
    int MaxRows = 8192;
    int MaxDraw = 384;
    static HCAdminWorldConfig Load()
    {
        HCOperatorSettingsRegistry.HCAdminWorldInit();
        HCAdminWorldConfig config = new HCAdminWorldConfig;
        string path = "$profile:HollowCountry/admin-world.json";
        if (!FileExist(path)) { return config; }
        string text;
        string error;
        HCAdminWorldConfig loaded;
        if (!HCGroupIO.Read(path, 4096, text) || !JsonFileLoader<HCAdminWorldConfig>.LoadData(text, loaded, error) || !loaded) { return config; }
        if (HCJsonFields.Has(text, "RefreshSeconds") && HCOperatorSettingsRegistry.HCValid("AdminWorld.RefreshSeconds", loaded.RefreshSeconds)) { config.RefreshSeconds = loaded.RefreshSeconds; }
        if (HCJsonFields.Has(text, "RowsPerTick") && HCOperatorSettingsRegistry.HCValid("AdminWorld.RowsPerTick", loaded.RowsPerTick)) { config.RowsPerTick = loaded.RowsPerTick; }
        if (HCJsonFields.Has(text, "MaxRows") && HCOperatorSettingsRegistry.HCValid("AdminWorld.MaxRows", loaded.MaxRows)) { config.MaxRows = loaded.MaxRows; }
        if (HCJsonFields.Has(text, "MaxDraw") && HCOperatorSettingsRegistry.HCValid("AdminWorld.MaxDraw", loaded.MaxDraw)) { config.MaxDraw = loaded.MaxDraw; }
        return config;
    }
}
// Read-only access to the same validated rate HCWorkBudget snapshots per slice.
modded class HCWorkBudget
{
    static float HCAdminMilliseconds(int ticks) { return ticks / s_TicksPerMs; }
}
