// Optional scoped melee settings; absent fields retain the recommended defaults.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print.
// HCGroupIO bounds the read; HCJsonFields distinguishes absence from false/zero.
class HCMeleeSettings
{
    bool HeadExecute = true;
    float HeadExecuteMinHeavyDamage = 22;
    float HeadLightMultiplier = 1.75;
    float HeadArmoredThreshold = 0.6;
    float HeadArmoredHeavyMultiplier = 2.0;
    bool LegCripple = true;
    float LegCrippleMinHeavyDamage = 27;
    bool ArmWeaken = true;
    int ArmWeakLightHits = 2;
    float ArmWeakCooldownMultiplier = 1.5;
    float ArmGlanceChance = 0.25;
    bool InfectedPoise = true;
    int InfectedPoiseLightStaggers = 2;
    float InfectedPoiseWindowSeconds = 3.0;
    bool StaggerImmunity = true;
    float StaggerImmunitySeconds = 1.5;
    float PlausibilityTolerance = 0.5;
    float ZoneTolerance = 0.9;
    float BlockStaminaCost = 6;
    bool GuardBreak = true;
    float GuardBreakChipFraction = 0.5;
    bool BlockCounter = true;
    float CounterWindowSeconds = 0.9;
    int LogLimit = 16;
    bool WeightStamina = true;
    float WeightStaminaBase = 0.6;
    float WeightStaminaPerKg = 0.25;
    float WeightStaminaMin = 0.75;
    float WeightStaminaMax = 1.6;
    float WeightStaminaFist = 0.75;
    bool InPlaceLight = true;
    float InPlaceDistance = 2.0;
    // Hard veto of melee hits on infected/AI whose head-to-zone line crosses a wall or closed door.
    bool WallVeto = true;
}

class HCMeleeConfig
{
    protected static ref HCMeleeSettings s_Settings;

    static HCMeleeSettings HCGet()
    {
        if (!s_Settings) { s_Settings = new HCMeleeSettings; }
        return s_Settings;
    }

    // Returns false only for unreadable/malformed documents. Invalid individual
    // values log once per row and retain the fresh default; optional absence succeeds.
    static bool HCLoad(string path)
    {
        HCOperatorSettingsRegistry.HCMeleeInit();
        s_Settings = new HCMeleeSettings;
        if (!FileExist(path)) { return true; }
        string image;
        string error;
        HCMeleeSettings decoded;
        if (!HCGroupIO.Read(path, 8192, image) || !JsonFileLoader<HCMeleeSettings>.LoadData(image, decoded, error) || !decoded)
        {
            Print("[HC Melee] config_unreadable defaults_retained runtime=PENDING");
            return false;
        }
        if (HCJsonFields.Has(image, "HeadExecute") && HCMeleeConfig.HCAccept("Melee.HeadExecute", decoded.HeadExecute)) { s_Settings.HeadExecute = decoded.HeadExecute; }
        if (HCJsonFields.Has(image, "HeadExecuteMinHeavyDamage") && HCMeleeConfig.HCAccept("Melee.HeadExecuteMinHeavyDamage", decoded.HeadExecuteMinHeavyDamage)) { s_Settings.HeadExecuteMinHeavyDamage = decoded.HeadExecuteMinHeavyDamage; }
        if (HCJsonFields.Has(image, "HeadLightMultiplier") && HCMeleeConfig.HCAccept("Melee.HeadLightMultiplier", decoded.HeadLightMultiplier)) { s_Settings.HeadLightMultiplier = decoded.HeadLightMultiplier; }
        if (HCJsonFields.Has(image, "HeadArmoredThreshold") && HCMeleeConfig.HCAccept("Melee.HeadArmoredThreshold", decoded.HeadArmoredThreshold)) { s_Settings.HeadArmoredThreshold = decoded.HeadArmoredThreshold; }
        if (HCJsonFields.Has(image, "HeadArmoredHeavyMultiplier") && HCMeleeConfig.HCAccept("Melee.HeadArmoredHeavyMultiplier", decoded.HeadArmoredHeavyMultiplier)) { s_Settings.HeadArmoredHeavyMultiplier = decoded.HeadArmoredHeavyMultiplier; }
        if (HCJsonFields.Has(image, "LegCripple") && HCMeleeConfig.HCAccept("Melee.LegCripple", decoded.LegCripple)) { s_Settings.LegCripple = decoded.LegCripple; }
        if (HCJsonFields.Has(image, "LegCrippleMinHeavyDamage") && HCMeleeConfig.HCAccept("Melee.LegCrippleMinHeavyDamage", decoded.LegCrippleMinHeavyDamage)) { s_Settings.LegCrippleMinHeavyDamage = decoded.LegCrippleMinHeavyDamage; }
        if (HCJsonFields.Has(image, "ArmWeaken") && HCMeleeConfig.HCAccept("Melee.ArmWeaken", decoded.ArmWeaken)) { s_Settings.ArmWeaken = decoded.ArmWeaken; }
        if (HCJsonFields.Has(image, "ArmWeakLightHits") && HCMeleeConfig.HCAccept("Melee.ArmWeakLightHits", decoded.ArmWeakLightHits)) { s_Settings.ArmWeakLightHits = decoded.ArmWeakLightHits; }
        if (HCJsonFields.Has(image, "ArmWeakCooldownMultiplier") && HCMeleeConfig.HCAccept("Melee.ArmWeakCooldownMultiplier", decoded.ArmWeakCooldownMultiplier)) { s_Settings.ArmWeakCooldownMultiplier = decoded.ArmWeakCooldownMultiplier; }
        if (HCJsonFields.Has(image, "ArmGlanceChance") && HCMeleeConfig.HCAccept("Melee.ArmGlanceChance", decoded.ArmGlanceChance)) { s_Settings.ArmGlanceChance = decoded.ArmGlanceChance; }
        if (HCJsonFields.Has(image, "InfectedPoise") && HCMeleeConfig.HCAccept("Melee.InfectedPoise", decoded.InfectedPoise)) { s_Settings.InfectedPoise = decoded.InfectedPoise; }
        if (HCJsonFields.Has(image, "InfectedPoiseLightStaggers") && HCMeleeConfig.HCAccept("Melee.InfectedPoiseLightStaggers", decoded.InfectedPoiseLightStaggers)) { s_Settings.InfectedPoiseLightStaggers = decoded.InfectedPoiseLightStaggers; }
        if (HCJsonFields.Has(image, "InfectedPoiseWindowSeconds") && HCMeleeConfig.HCAccept("Melee.InfectedPoiseWindowSeconds", decoded.InfectedPoiseWindowSeconds)) { s_Settings.InfectedPoiseWindowSeconds = decoded.InfectedPoiseWindowSeconds; }
        if (HCJsonFields.Has(image, "StaggerImmunity") && HCMeleeConfig.HCAccept("Melee.StaggerImmunity", decoded.StaggerImmunity)) { s_Settings.StaggerImmunity = decoded.StaggerImmunity; }
        if (HCJsonFields.Has(image, "StaggerImmunitySeconds") && HCMeleeConfig.HCAccept("Melee.StaggerImmunitySeconds", decoded.StaggerImmunitySeconds)) { s_Settings.StaggerImmunitySeconds = decoded.StaggerImmunitySeconds; }
        if (HCJsonFields.Has(image, "PlausibilityTolerance") && HCMeleeConfig.HCAccept("Melee.PlausibilityTolerance", decoded.PlausibilityTolerance)) { s_Settings.PlausibilityTolerance = decoded.PlausibilityTolerance; }
        if (HCJsonFields.Has(image, "ZoneTolerance") && HCMeleeConfig.HCAccept("Melee.ZoneTolerance", decoded.ZoneTolerance)) { s_Settings.ZoneTolerance = decoded.ZoneTolerance; }
        if (HCJsonFields.Has(image, "BlockStaminaCost") && HCMeleeConfig.HCAccept("Melee.BlockStaminaCost", decoded.BlockStaminaCost)) { s_Settings.BlockStaminaCost = decoded.BlockStaminaCost; }
        if (HCJsonFields.Has(image, "GuardBreak") && HCMeleeConfig.HCAccept("Melee.GuardBreak", decoded.GuardBreak)) { s_Settings.GuardBreak = decoded.GuardBreak; }
        if (HCJsonFields.Has(image, "GuardBreakChipFraction") && HCMeleeConfig.HCAccept("Melee.GuardBreakChipFraction", decoded.GuardBreakChipFraction)) { s_Settings.GuardBreakChipFraction = decoded.GuardBreakChipFraction; }
        if (HCJsonFields.Has(image, "BlockCounter") && HCMeleeConfig.HCAccept("Melee.BlockCounter", decoded.BlockCounter)) { s_Settings.BlockCounter = decoded.BlockCounter; }
        if (HCJsonFields.Has(image, "CounterWindowSeconds") && HCMeleeConfig.HCAccept("Melee.CounterWindowSeconds", decoded.CounterWindowSeconds)) { s_Settings.CounterWindowSeconds = decoded.CounterWindowSeconds; }
        if (HCJsonFields.Has(image, "LogLimit") && HCMeleeConfig.HCAccept("Melee.LogLimit", decoded.LogLimit)) { s_Settings.LogLimit = decoded.LogLimit; }
        if (HCJsonFields.Has(image, "WeightStamina") && HCMeleeConfig.HCAccept("Melee.WeightStamina", decoded.WeightStamina)) { s_Settings.WeightStamina = decoded.WeightStamina; }
        if (HCJsonFields.Has(image, "WeightStaminaBase") && HCMeleeConfig.HCAccept("Melee.WeightStaminaBase", decoded.WeightStaminaBase)) { s_Settings.WeightStaminaBase = decoded.WeightStaminaBase; }
        if (HCJsonFields.Has(image, "WeightStaminaPerKg") && HCMeleeConfig.HCAccept("Melee.WeightStaminaPerKg", decoded.WeightStaminaPerKg)) { s_Settings.WeightStaminaPerKg = decoded.WeightStaminaPerKg; }
        if (HCJsonFields.Has(image, "WeightStaminaMin") && HCMeleeConfig.HCAccept("Melee.WeightStaminaMin", decoded.WeightStaminaMin)) { s_Settings.WeightStaminaMin = decoded.WeightStaminaMin; }
        if (HCJsonFields.Has(image, "WeightStaminaMax") && HCMeleeConfig.HCAccept("Melee.WeightStaminaMax", decoded.WeightStaminaMax)) { s_Settings.WeightStaminaMax = decoded.WeightStaminaMax; }
        if (HCJsonFields.Has(image, "WeightStaminaFist") && HCMeleeConfig.HCAccept("Melee.WeightStaminaFist", decoded.WeightStaminaFist)) { s_Settings.WeightStaminaFist = decoded.WeightStaminaFist; }
        if (HCJsonFields.Has(image, "InPlaceLight") && HCMeleeConfig.HCAccept("Melee.InPlaceLight", decoded.InPlaceLight)) { s_Settings.InPlaceLight = decoded.InPlaceLight; }
        if (HCJsonFields.Has(image, "InPlaceDistance") && HCMeleeConfig.HCAccept("Melee.InPlaceDistance", decoded.InPlaceDistance)) { s_Settings.InPlaceDistance = decoded.InPlaceDistance; }
        if (HCJsonFields.Has(image, "WallVeto") && HCMeleeConfig.HCAccept("Melee.WallVeto", decoded.WallVeto)) { s_Settings.WallVeto = decoded.WallVeto; }
        return true;
    }

    protected static bool HCAccept(string key, float value)
    {
        if (HCOperatorSettingsRegistry.HCValid(key, value)) { return true; }
        Print("[HC Melee] config_rejected key=" + key + " default_retained runtime=PENDING");
        return false;
    }
}

// Lead mirrors these scoped rows in shared_settings.json.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_MeleeRegistered;

    static void HCMeleeInit()
    {
        HCInit();
        if (s_MeleeRegistered) { return; }
        s_MeleeRegistered = true;
        HCAdd("Melee.HeadExecute", "bool", 1, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.HeadExecuteMinHeavyDamage", "float", 22, 0, 100, "HCMeleeConfig");
        HCAdd("Melee.HeadLightMultiplier", "float", 1.75, 1, 4, "HCMeleeConfig");
        HCAdd("Melee.HeadArmoredThreshold", "float", 0.6, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.HeadArmoredHeavyMultiplier", "float", 2.0, 1, 4, "HCMeleeConfig");
        HCAdd("Melee.LegCripple", "bool", 1, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.LegCrippleMinHeavyDamage", "float", 27, 0, 100, "HCMeleeConfig");
        HCAdd("Melee.ArmWeaken", "bool", 1, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.ArmWeakLightHits", "int", 2, 1, 10, "HCMeleeConfig");
        HCAdd("Melee.ArmWeakCooldownMultiplier", "float", 1.5, 1, 3, "HCMeleeConfig");
        HCAdd("Melee.ArmGlanceChance", "float", 0.25, 0, 0.5, "HCMeleeConfig");
        HCAdd("Melee.InfectedPoise", "bool", 1, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.InfectedPoiseLightStaggers", "int", 2, 1, 10, "HCMeleeConfig");
        HCAdd("Melee.InfectedPoiseWindowSeconds", "float", 3.0, 0.5, 10, "HCMeleeConfig");
        HCAdd("Melee.StaggerImmunity", "bool", 1, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.StaggerImmunitySeconds", "float", 1.5, 0, 5, "HCMeleeConfig");
        HCAdd("Melee.PlausibilityTolerance", "float", 0.5, 0, 2, "HCMeleeConfig");
        HCAdd("Melee.ZoneTolerance", "float", 0.9, 0.1, 1.5, "HCMeleeConfig");
        HCAdd("Melee.BlockStaminaCost", "float", 6, 0, 30, "HCMeleeConfig");
        HCAdd("Melee.GuardBreak", "bool", 1, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.GuardBreakChipFraction", "float", 0.5, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.BlockCounter", "bool", 1, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.CounterWindowSeconds", "float", 0.9, 0.2, 2, "HCMeleeConfig");
        HCAdd("Melee.LogLimit", "int", 16, 0, 256, "HCMeleeConfig");
        HCAdd("Melee.WeightStamina", "bool", 1, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.WeightStaminaBase", "float", 0.6, 0, 2, "HCMeleeConfig");
        HCAdd("Melee.WeightStaminaPerKg", "float", 0.25, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.WeightStaminaMin", "float", 0.75, 0.25, 1, "HCMeleeConfig");
        HCAdd("Melee.WeightStaminaMax", "float", 1.6, 1, 3, "HCMeleeConfig");
        HCAdd("Melee.WeightStaminaFist", "float", 0.75, 0.25, 2, "HCMeleeConfig");
        HCAdd("Melee.InPlaceLight", "bool", 1, 0, 1, "HCMeleeConfig");
        HCAdd("Melee.InPlaceDistance", "float", 2.0, 1.5, 3, "HCMeleeConfig");
        HCAdd("Melee.WallVeto", "bool", 1, 0, 1, "HCMeleeConfig");
    }
}
