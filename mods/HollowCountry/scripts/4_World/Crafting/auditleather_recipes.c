// Issue 229. Native evidence relative to scripts-1.30.164289:
// 4_World/Entities/ItemBase/Clothing/LeatherPants_ColorBase.c:1-5 and
// LeatherStorageVest_ColorBase.c:1-5 declare the eight concrete outputs.
// Gear/Tools/SewingKit.c:1 and LeatherSewingKit.c:1 declare tools;
// 4_World/Classes/Recipes/Recipes/CraftLeatherSack.c:26,34 uses
// TannedLeather/LeatherSewingKit; :38 debits kit quantity (finite tool wear).
// RecipeBase.c:159-168,198 InsertIngredient/AddResult; :373-425 native
// quantity debits; :479-539 native check/commit. HC-4 owns server-only commit,
// reentry, allocation failure, custody and health/wetness/agent inheritance.
// No extra polling, module slot, mission data, registry setting or RPC.
class HCAuditLeatherPolicy
{
    // Existing crafting families are source-defined, not JSON-configured.
    // Panel costs exceed salvage yields (pants=1, vest=2), preventing loops.
    static const int PANTS_PANELS = 3;
    static const int VEST_PANELS = 4;
    static const int KIT_UNITS = 10;
    static const float ANIMATION_UNITS = 2;
    static bool m_Ready;

    // 3_Game/gameplay.c:636 GetGame; 3_Game/Global/Game.c:1120 IsServer.
    static bool HCPreviewReady()
    {
        if (!GetGame()) return false;
        if (!GetGame().IsServer()) return true;
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
            int panels = HCAuditLeatherPolicy.PANTS_PANELS;
            if (variant >= 4)
            {
                family = "Vest";
                panels = HCAuditLeatherPolicy.VEST_PANELS;
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
        if (recipe.m_MinQuantityIngredient[1] != HCAuditLeatherPolicy.KIT_UNITS || recipe.m_IngredientAddQuantity[1] != -HCAuditLeatherPolicy.KIT_UNITS) return false;
        if (recipe.m_IngredientAddHealth[1] != 0 || recipe.m_ResultSetQuantity[0] != 1) return false;
        if (recipe.m_ResultReplacesIngredient[0] != -1 || recipe.m_ResultInheritsColor[0] != -1) return false;
        if (!GetGame().ConfigIsExisting("CfgVehicles " + output) || GetGame().ConfigGetInt("CfgVehicles " + output + " scope") != 2) return false;
        if (GetGame().ConfigGetFloat("CfgVehicles TannedLeather varQuantityMax") < panels) return false;
        if (GetGame().ConfigGetFloat("CfgVehicles SewingKit varQuantityMax") < HCAuditLeatherPolicy.KIT_UNITS) return false;
        return GetGame().ConfigGetFloat("CfgVehicles LeatherSewingKit varQuantityMax") >= HCAuditLeatherPolicy.KIT_UNITS;
    }
}

class HCAuditLeatherRecipe extends HCSalvageRecipe
{
    void HCConfigureTailoring(string label, string outputType, int panels)
    {
        Configure(label, "", "", outputType, 1, 0, HCAuditLeatherPolicy.ANIMATION_UNITS);
        InsertIngredient(0, "TannedLeather");
        InsertIngredient(1, "SewingKit");
        InsertIngredient(1, "LeatherSewingKit");
        m_IngredientDestroy[0] = false;
        m_IngredientDestroy[1] = false;
        m_MinQuantityIngredient[0] = panels;
        m_IngredientAddQuantity[0] = -panels;
        m_MinQuantityIngredient[1] = HCAuditLeatherPolicy.KIT_UNITS;
        m_IngredientAddQuantity[1] = -HCAuditLeatherPolicy.KIT_UNITS;
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
        HCConfigureTailoring("Tailor leather pants (beige)", "LeatherPants_Beige", HCAuditLeatherPolicy.PANTS_PANELS);
    }
}

class HCAuditLeatherPantsBlack extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather pants (black)", "LeatherPants_Black", HCAuditLeatherPolicy.PANTS_PANELS);
    }
}

class HCAuditLeatherPantsBrown extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather pants (brown)", "LeatherPants_Brown", HCAuditLeatherPolicy.PANTS_PANELS);
    }
}

class HCAuditLeatherPantsNatural extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather pants (natural)", "LeatherPants_Natural", HCAuditLeatherPolicy.PANTS_PANELS);
    }
}

class HCAuditLeatherVestBeige extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather vest (beige)", "LeatherStorageVest_Beige", HCAuditLeatherPolicy.VEST_PANELS);
    }
}

class HCAuditLeatherVestBlack extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather vest (black)", "LeatherStorageVest_Black", HCAuditLeatherPolicy.VEST_PANELS);
    }
}

class HCAuditLeatherVestBrown extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather vest (brown)", "LeatherStorageVest_Brown", HCAuditLeatherPolicy.VEST_PANELS);
    }
}

class HCAuditLeatherVestNatural extends HCAuditLeatherRecipe
{
    override void Init()
    {
        HCConfigureTailoring("Tailor leather vest (natural)", "LeatherStorageVest_Natural", HCAuditLeatherPolicy.VEST_PANELS);
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
        if (HCCraftingGate.m_Started)
            HCAuditLeatherPolicy.m_Ready = HCAuditLeatherPolicy.HCValidate();
        // Native 1_Core/proto/EnDebug.c:96 Print; admission is not acceptance.
        Print(HCV2Admission.Line("LeatherTailoring", settings && settings.EnableCrafting, "leather-tailoring", false) + " runtime=PENDING");
        if (HCCraftingGate.m_Started && !HCAuditLeatherPolicy.m_Ready)
            Print("[HollowCountry] LeatherTailoring refusal=definition_or_config_checks_failed runtime=PENDING");
    }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCOperationalStatus status = super.HCGetOperationalStatus();
        if (HCCraftingGate.m_Started && !HCAuditLeatherPolicy.m_Ready)
            status.HCPublish("degraded", "leather_tailoring_definition_or_config_checks_failed");
        return status;
    }

    override void OnStop()
    {
        HCAuditLeatherPolicy.m_Ready = false;
        super.OnStop();
    }
}
