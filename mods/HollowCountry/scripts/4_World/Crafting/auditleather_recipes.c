// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; EnDebug.c:96 Print.
// EnConvert.c:3,30,115 bool/int/float.ToString; EnDebug.c:96 Print.
// Bounded HCGroupIO read; absent/invalid fields retain constructor defaults.
class HCAuditLeatherConfig
{
    bool Enabled = true;
    int PantsPanels = 3;
    int VestPanels = 4;
    int KitUnits = 10;
    float AnimationUnits = 2;
    protected static ref HCAuditLeatherConfig s_Config;
    static HCAuditLeatherConfig HCGet()
    {
        if (s_Config) { return s_Config; }
        HCOperatorSettingsRegistry.HCLocalPolicyInit();
        s_Config = new HCAuditLeatherConfig;
        string path = "$profile:HollowCountry/leather-tailoring.json";
        if (FileExist(path))
        {
            string text;
            string error;
            HCAuditLeatherConfig decoded;
            if (HCGroupIO.Read(path, 4096, text) && JsonFileLoader<HCAuditLeatherConfig>.LoadData(text, decoded, error) && decoded)
                s_Config.HCApply(decoded, text);
            else
                Print("[HC Config] HCAuditLeatherConfig invalid_json defaults_restored runtime=PENDING");
        }
        Print("[HC Config] HCAuditLeatherConfig enabled=" + s_Config.Enabled.ToString() + " pants=" + s_Config.PantsPanels.ToString() + " vest=" + s_Config.VestPanels.ToString() + " runtime=PENDING");
        Print("[HC Config] HCAuditLeatherConfig kit=" + s_Config.KitUnits.ToString() + " animation_units=" + s_Config.AnimationUnits.ToString() + " runtime=PENDING");
        return s_Config;
    }
    void HCApply(HCAuditLeatherConfig decoded, string text)
    {
        if (HCJsonFields.Has(text, "Enabled"))
        {
            Enabled = decoded.Enabled;
        }
        if (HCJsonFields.Has(text, "PantsPanels"))
        {
            if (HCOperatorSettingsRegistry.HCValid("LeatherTailoring.PantsPanels", decoded.PantsPanels)) { PantsPanels = decoded.PantsPanels; }
            else { Print("[HC Config] LeatherTailoring.PantsPanels invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "VestPanels"))
        {
            if (HCOperatorSettingsRegistry.HCValid("LeatherTailoring.VestPanels", decoded.VestPanels)) { VestPanels = decoded.VestPanels; }
            else { Print("[HC Config] LeatherTailoring.VestPanels invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "KitUnits"))
        {
            if (HCOperatorSettingsRegistry.HCValid("LeatherTailoring.KitUnits", decoded.KitUnits)) { KitUnits = decoded.KitUnits; }
            else { Print("[HC Config] LeatherTailoring.KitUnits invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "AnimationUnits"))
        {
            if (HCOperatorSettingsRegistry.HCValid("LeatherTailoring.AnimationUnits", decoded.AnimationUnits)) { AnimationUnits = decoded.AnimationUnits; }
            else { Print("[HC Config] LeatherTailoring.AnimationUnits invalid_range default_retained runtime=PENDING"); }
        }
    }
}

// Issue 229. Native evidence relative to scripts-1.30.164289:
// 4_World/Entities/ItemBase/Clothing/LeatherPants_ColorBase.c:1-5 and
// LeatherStorageVest_ColorBase.c:1-5 declare the eight concrete outputs.
// Gear/Tools/SewingKit.c:1 and LeatherSewingKit.c:1 declare tools;
// 4_World/Classes/Recipes/Recipes/CraftLeatherSack.c:26,34 uses
// TannedLeather/LeatherSewingKit; :38 debits kit quantity (finite tool wear).
// RecipeBase.c:159-168,198 InsertIngredient/AddResult; :373-425 native
// quantity debits; :479-539 native check/commit. HC-4 owns server-only commit,
// reentry, allocation failure, custody and health/wetness/agent inheritance.
// No extra polling, module slot, mission data or RPC.
// Profile tuning affects local previews only on clients; server recipe fields
// own checks/debits/time. Deploy matching leather-tailoring.json to clients
// when changing defaults to keep native preview/progress presentation aligned.
// RecipeBase.c:95-98 GetLengthInSecs; CAContinuousCraft.c:22,46-63 timer.
class HCAuditLeatherPolicy
{
    // Minimum panel costs stay above salvage yields (pants=1, vest=2).
    static bool m_Ready;

    // 3_Game/gameplay.c:636 GetGame; 3_Game/Global/Game.c:1120 IsServer.
    static bool HCPreviewReady()
    {
        if (!GetGame()) return false;
        if (!GetGame().IsServer()) return true;
        if (!HCAuditLeatherConfig.HCGet().Enabled) return false;
        return HCAuditLeatherPolicy.m_Ready;
    }

    // Validate actual cached recipes, not freshly constructed defaults.
    // 4_World/Plugins/PluginManager.c:327 GetPlugin;
    // PluginRecipesManager.c:470-475 native ID lookup (HC-4 audited wrapper);
    // 1_Core/proto/EnScript.c:94 Class.Cast.
    static bool HCValidate()
    {
        PluginRecipesManager manager = PluginRecipesManager.Cast(GetPlugin(PluginRecipesManager));
        if (!manager) return false;
        for (int variant = 0; variant < 8; variant++)
        {
            string family = "Pants";
            int panels = HCAuditLeatherConfig.HCGet().PantsPanels;
            if (variant >= 4)
            {
                family = "Vest";
                panels = HCAuditLeatherConfig.HCGet().VestPanels;
            }
            string color = "Beige";
            int colorIndex = variant % 4;
            if (colorIndex == 1) color = "Black";
            if (colorIndex == 2) color = "Brown";
            if (colorIndex == 3) color = "Natural";
            RecipeBase recipe = manager.HCGetRegisteredSalvage("HCAuditLeather" + family + color);
            string output = "LeatherPants_" + color;
            if (family == "Vest") output = "LeatherStorageVest_" + color;
            if (!HCAuditLeatherPolicy.HCCheckDefinition(recipe, output, panels)) return false;
        }
        return true;
    }

    // 1_Core/proto/EnScript.c:380 Count; RecipeBase.c:23-63 public fields;
    // 3_Game/Global/Game.c:524,539,612 config accessors/existence.
    static bool HCCheckDefinition(RecipeBase recipe, string output, int panels)
    {
        if (!recipe || recipe.m_NumberOfResults != 1 || recipe.m_ItemsToCreate[0] != output) return false;
        if (recipe.m_Ingredients[0].Count() != 1 || recipe.m_Ingredients[0][0] != "TannedLeather") return false;
        if (recipe.m_Ingredients[1].Count() != 2) return false;
        if (recipe.m_Ingredients[1][0] != "SewingKit" || recipe.m_Ingredients[1][1] != "LeatherSewingKit") return false;
        if (recipe.m_IngredientDestroy[0] || recipe.m_IngredientDestroy[1]) return false;
        if (recipe.m_MinQuantityIngredient[0] != panels || recipe.m_IngredientAddQuantity[0] != -panels) return false;
        if (recipe.m_MinQuantityIngredient[1] != HCAuditLeatherConfig.HCGet().KitUnits || recipe.m_IngredientAddQuantity[1] != -HCAuditLeatherConfig.HCGet().KitUnits) return false;
        if (recipe.m_AnimationLength != HCAuditLeatherConfig.HCGet().AnimationUnits) return false;
        if (recipe.m_IngredientAddHealth[1] != 0 || recipe.m_ResultSetQuantity[0] != 1) return false;
        if (recipe.m_ResultReplacesIngredient[0] != -1 || recipe.m_ResultInheritsColor[0] != -1) return false;
        if (!GetGame().ConfigIsExisting("CfgVehicles " + output) || GetGame().ConfigGetInt("CfgVehicles " + output + " scope") != 2) return false;
        if (GetGame().ConfigGetFloat("CfgVehicles TannedLeather varQuantityMax") < panels) return false;
        if (GetGame().ConfigGetFloat("CfgVehicles SewingKit varQuantityMax") < HCAuditLeatherConfig.HCGet().KitUnits) return false;
        return GetGame().ConfigGetFloat("CfgVehicles LeatherSewingKit varQuantityMax") >= HCAuditLeatherConfig.HCGet().KitUnits;
    }
}

class HCAuditLeatherRecipe extends HCSalvageRecipe
{
    void HCConfigureTailoring(string label, string outputType, int panels)
    {
        Configure(label, "", "", outputType, 1, 0, HCAuditLeatherConfig.HCGet().AnimationUnits);
        InsertIngredient(0, "TannedLeather");
        InsertIngredient(1, "SewingKit");
        InsertIngredient(1, "LeatherSewingKit");
        m_IngredientDestroy[0] = false;
        m_IngredientDestroy[1] = false;
        m_MinQuantityIngredient[0] = panels;
        m_IngredientAddQuantity[0] = -panels;
        m_MinQuantityIngredient[1] = HCAuditLeatherConfig.HCGet().KitUnits;
        m_IngredientAddQuantity[1] = -HCAuditLeatherConfig.HCGet().KitUnits;
        m_IngredientAddHealth[1] = 0;
    }

    // Object.c:467,517,1219 GetType/IsAlive/IsRuined;
    // PlayerBase.c:3925 IsUnconscious; ItemBase.c:3485-3493 HasQuantity/GetQuantity.
    // HC-4 custody includes the native attachment refusal and loose ownership.
    // Native CheckRecipe still checks hand position and damage/quantity fields.
    override bool CanDo(ItemBase ingredients[], PlayerBase player)
    {
        if (!HCCraftingGate.CanPreviewOrCraft() || !HCAuditLeatherPolicy.HCPreviewReady()) return false;
        if (!player || !player.IsAlive() || player.IsUnconscious()) return false;
        if (!ingredients[0] || !ingredients[1] || ingredients[0] == ingredients[1]) return false;
        if (ingredients[0].GetType() != "TannedLeather") return false;
        string toolKind = ingredients[1].GetType();
        if (toolKind != "SewingKit" && toolKind != "LeatherSewingKit") return false;
        if (ingredients[0].IsRuined() || ingredients[1].IsRuined()) return false;
        if (!IsOwnedEmptyLooseItem(ingredients[0], player) || !IsOwnedEmptyLooseItem(ingredients[1], player)) return false;
        if (!ingredients[0].HasQuantity() || !ingredients[1].HasQuantity()) return false;
        return ingredients[0].GetQuantity() >= m_MinQuantityIngredient[0] && ingredients[1].GetQuantity() >= m_MinQuantityIngredient[1];
    }
}

class HCAuditLeatherPantsBeige extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather pants (beige)", "LeatherPants_Beige", HCAuditLeatherConfig.HCGet().PantsPanels);
    }
}

class HCAuditLeatherPantsBlack extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather pants (black)", "LeatherPants_Black", HCAuditLeatherConfig.HCGet().PantsPanels);
    }
}

class HCAuditLeatherPantsBrown extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather pants (brown)", "LeatherPants_Brown", HCAuditLeatherConfig.HCGet().PantsPanels);
    }
}

class HCAuditLeatherPantsNatural extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather pants (natural)", "LeatherPants_Natural", HCAuditLeatherConfig.HCGet().PantsPanels);
    }
}

class HCAuditLeatherVestBeige extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather vest (beige)", "LeatherStorageVest_Beige", HCAuditLeatherConfig.HCGet().VestPanels);
    }
}

class HCAuditLeatherVestBlack extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather vest (black)", "LeatherStorageVest_Black", HCAuditLeatherConfig.HCGet().VestPanels);
    }
}

class HCAuditLeatherVestBrown extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather vest (brown)", "LeatherStorageVest_Brown", HCAuditLeatherConfig.HCGet().VestPanels);
    }
}

class HCAuditLeatherVestNatural extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather vest (natural)", "LeatherStorageVest_Natural", HCAuditLeatherConfig.HCGet().VestPanels);
    }
}

// Deterministic registration on every peer, independent of profile preferences.
// Native PluginRecipesManagerBase.c:11,17-18; manager :443-453 accepts new
// RecipeBase through this native registration API (the standard exception).
modded class PluginRecipesManager
{
    override void RegisterRecipies()
    {
        super.RegisterRecipies();
        RegisterRecipe(new HCAuditLeatherPantsBeige);
        RegisterRecipe(new HCAuditLeatherPantsBlack);
        RegisterRecipe(new HCAuditLeatherPantsBrown);
        RegisterRecipe(new HCAuditLeatherPantsNatural);
        RegisterRecipe(new HCAuditLeatherVestBeige);
        RegisterRecipe(new HCAuditLeatherVestBlack);
        RegisterRecipe(new HCAuditLeatherVestBrown);
        RegisterRecipe(new HCAuditLeatherVestNatural);
    }
}

// Extend the existing lifecycle/status owner, with no additional module slot.
modded class HCCraftingModule
{
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        HCAuditLeatherPolicy.m_Ready = false;
        if (HCCraftingGate.m_Started && HCAuditLeatherConfig.HCGet().Enabled)
            HCAuditLeatherPolicy.m_Ready = HCAuditLeatherPolicy.HCValidate();
        // Native 1_Core/proto/EnDebug.c:96 Print; admission is not acceptance.
        Print(HCV2Admission.Line("LeatherTailoring", settings && settings.EnableCrafting && HCAuditLeatherConfig.HCGet().Enabled, "leather-tailoring", false) + " runtime=PENDING");
        if (HCCraftingGate.m_Started && HCAuditLeatherConfig.HCGet().Enabled && !HCAuditLeatherPolicy.m_Ready)
            Print("[HollowCountry] LeatherTailoring refusal=definition_or_config_checks_failed runtime=PENDING");
    }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCOperationalStatus status = super.HCGetOperationalStatus();
        if (HCCraftingGate.m_Started && HCAuditLeatherConfig.HCGet().Enabled && !HCAuditLeatherPolicy.m_Ready)
            status.HCPublish("degraded", "leather_tailoring_definition_or_config_checks_failed");
        return status;
    }

    override void OnStop()
    {
        HCAuditLeatherPolicy.m_Ready = false;
        super.OnStop();
    }
}
