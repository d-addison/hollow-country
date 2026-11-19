// HC-30: two approved recoveries. Registration/startup wiring belongs to lead.
// Native references below are relative to scripts-1.30.164289 (N3 unless noted).
// RecipeBase.c:159-168,198 defines ingredient/result registration;
// :373-425 debits quantities or destroys inputs, :479-539 owns completion.
// 3_Game/gameplay.c:636: GetGame; 1_Core/proto/EnScript.c:37,380:
// ClassName and array Count. RecipeBase.c:95-112,209: recipe query methods.
// HC-4 HCSalvageRecipe owns allocation validation, commit guard, tool wear,
// selective health/wetness/agents inheritance and the existing crafting gate.
// No controller, polling, RPC, persistence or additional distance is introduced.
class HCCommonRecoveryPolicy
{
    static int HCSourceCount(string recipeName)
    {
        if (recipeName == "HCRecoverTeddyRag") return 4;
        if (recipeName == "HCRecoverFabricRag") return 1;
        return 0;
    }

    static string HCSourceAt(string recipeName, int index)
    {
        if (recipeName == "HCRecoverFabricRag" && index == 0) return "Fabric";
        if (recipeName == "HCRecoverTeddyRag")
        {
            if (index == 0) return "Bear_Beige";
            if (index == 1) return "Bear_Dark";
            if (index == 2) return "Bear_Pink";
            if (index == 3) return "Bear_White";
        }
        return "";
    }

    static bool HCAllowsSource(string recipeName, string actualType)
    {
        int count = HCCommonRecoveryPolicy.HCSourceCount(recipeName);
        for (int i = 0; i < count; i++)
        {
            if (HCCommonRecoveryPolicy.HCSourceAt(recipeName, i) == actualType)
                return true;
        }
        return false;
    }

    // Call only during the deterministic native registration phase on all peers.
    // CraftRag.c:68 is a sound category, NOT a config eligibility category.
    // Its actual source gate is ragQuantity > 0 (:90-94). An existing native
    // route always wins; never register an HC replacement with duplicate yield.
    // N1 3_Game/Global/Game.c:524,539,612: config getters/existence.
    // 1_Core/proto/EnDebug.c:96: Print (all diagnostics in this file).
    static bool HCPreflight(string recipeName)
    {
        int count = HCCommonRecoveryPolicy.HCSourceCount(recipeName);
        if (count == 0 || !GetGame())
            return false;
        if (!GetGame().ConfigIsExisting("CfgVehicles Rag") || GetGame().ConfigGetInt("CfgVehicles Rag scope") != 2)
        {
            Print("[HC Plan] HC-30 refusal=HC30_RESULT_CONFIG_MISSING recipe=" + recipeName);
            return false;
        }
        if (GetGame().ConfigGetFloat("CfgVehicles Rag varQuantityMax") < 1)
        {
            Print("[HC Plan] HC-30 refusal=HC30_RESULT_CAPACITY recipe=" + recipeName);
            return false;
        }
        for (int i = 0; i < count; i++)
        {
            string path = "CfgVehicles " + HCCommonRecoveryPolicy.HCSourceAt(recipeName, i);
            if (!GetGame().ConfigIsExisting(path) || GetGame().ConfigGetInt(path + " scope") != 2)
            {
                Print("[HC Plan] HC-30 refusal=HC30_SOURCE_CONFIG_MISSING recipe=" + recipeName);
                return false;
            }
            if (GetGame().ConfigGetFloat(path + " ragQuantity") > 0)
            {
                Print("[HC Plan] HC-30 refusal=HC30_NATIVE_RAG_ROUTE recipe=" + recipeName);
                return false;
            }
            float capacity = GetGame().ConfigGetFloat(path + " varQuantityMax");
            if (recipeName == "HCRecoverFabricRag" && capacity < 1)
            {
                Print("[HC Plan] HC-30 refusal=HC30_SOURCE_QUANTITY_DRIFT recipe=" + recipeName);
                return false;
            }
            if (recipeName == "HCRecoverTeddyRag" && capacity > 0)
            {
                Print("[HC Plan] HC-30 refusal=HC30_SOURCE_QUANTITY_DRIFT recipe=" + recipeName);
                return false;
            }
        }
        int toolCount = HCSalvageTools.ToolCount("KitchenKnife");
        for (int toolIndex = 0; toolIndex < toolCount; toolIndex++)
        {
            string toolPath = "CfgVehicles " + HCSalvageTools.ToolAt("KitchenKnife", toolIndex);
            if (!GetGame().ConfigIsExisting(toolPath) || GetGame().ConfigGetInt(toolPath + " scope") != 2)
            {
                Print("[HC Plan] HC-30 refusal=HC30_TOOL_CONFIG_MISSING recipe=" + recipeName);
                return false;
            }
        }
        return true;
    }

    // Validate actual registered instances, never freshly reconstructed defaults.
    // Uses HC-4's bounded HCGetRegisteredSalvage and installed public RecipeBase
    // fields (:23-63); no mutation of the native recipe cache.
    static bool HCCheckDefinition(RecipeBase recipe, string recipeName)
    {
        if (!recipe || recipe.ClassName() != recipeName)
            return false;
        int count = HCCommonRecoveryPolicy.HCSourceCount(recipeName);
        if (count == 0 || recipe.m_Ingredients[0].Count() != count)
            return false;
        for (int i = 0; i < count; i++)
        {
            if (recipe.m_Ingredients[0][i] != HCCommonRecoveryPolicy.HCSourceAt(recipeName, i))
                return false;
        }
        if (!HCSalvageTools.CheckRegistered(recipe.m_Ingredients[1], "KitchenKnife"))
            return false;
        if (recipe.m_NumberOfResults != 1 || recipe.m_ItemsToCreate[0] != "Rag" || recipe.m_ResultSetQuantity[0] != 1)
            return false;
        if (recipe.m_ResultSetFullQuantity[0] || recipe.m_ResultReplacesIngredient[0] != -1 || recipe.m_ResultInheritsColor[0] != -1)
            return false;
        if (recipe.m_ResultInheritsHealth[0] != 0 || recipe.m_ResultToInventory[0] != -1 || recipe.m_ResultUseSoftSkills[0])
            return false;
        if (recipe.m_IngredientDestroy[1] || recipe.m_IngredientAddQuantity[1] != 0 || recipe.m_IngredientAddHealth[1] != -5)
            return false;
        if (recipe.m_IngredientUseSoftSkills[0] || recipe.m_IngredientUseSoftSkills[1] || recipe.GetSpecialty() != 0)
            return false;
        if (recipe.IsInstaRecipe() || recipe.IsRepeatable() || recipe.IsRecipeAnywhere() || recipe.GetLengthInSecs() != 8)
            return false;
        if (recipe.m_MinDamageIngredient[0] != -1 || recipe.m_MaxDamageIngredient[0] != 3 || recipe.m_MaxDamageIngredient[1] != 3)
            return false;
        if (recipeName == "HCRecoverFabricRag")
        {
            if (recipe.m_IngredientDestroy[0] || recipe.m_IngredientAddQuantity[0] != -1 || recipe.m_MinQuantityIngredient[0] != 1)
                return false;
            // Source survives a partial-stack debit: unlike destroyed Teddy,
            // source health modifiers are active and must remain inert.
            return recipe.m_IngredientAddHealth[0] == 0 && recipe.m_IngredientSetHealth[0] == -1;
        }
        return recipe.m_IngredientDestroy[0] && recipe.m_IngredientAddQuantity[0] == 0;
    }

    static bool HCMatchesPreflight(RecipeBase recipe, string recipeName)
    {
        // An omitted/refused recipe is a disposition, not failure of HC-4.
        // A registered duplicate or drifted definition still fails closed.
        if (!HCCommonRecoveryPolicy.HCPreflight(recipeName))
            return !recipe;
        return HCCommonRecoveryPolicy.HCCheckDefinition(recipe, recipeName);
    }

    // Lead calls from HCCraftingModule.OnStart after HC-4 Run succeeds and
    // before setting HCCraftingGate.m_Started; existing audit ports stay intact.
    // GetPlugin: 4_World/Plugins/PluginManager.c:327; native class/ID lookup:
    // Plugins/PluginBase/PluginRecipesManager.c:470-475; HC-4 validates ID too.
    static bool HCValidateRegistered()
    {
        PluginRecipesManager manager = PluginRecipesManager.Cast(GetPlugin(PluginRecipesManager));
        if (!manager)
            return false;
        if (!HCCommonRecoveryPolicy.HCMatchesPreflight(manager.HCGetRegisteredSalvage("HCRecoverTeddyRag"), "HCRecoverTeddyRag"))
            return false;
        return HCCommonRecoveryPolicy.HCMatchesPreflight(manager.HCGetRegisteredSalvage("HCRecoverFabricRag"), "HCRecoverFabricRag");
    }

    // One bounded startup receipt; authored/admitted/observed remain separate.
    // Native reused routes are dispositions only, never HC recipe definitions.
    // 1_Core/proto/EnString.c:526: string.Format.
    static void HCReport(bool enabled, bool admitted)
    {
        if (!enabled)
        {
            Print("[HC Plan] HC-30 recoveries=0 native_reused=0 refused=0 state=off authored=2 observed=0 runtime=PENDING");
            return;
        }
        PluginRecipesManager manager = PluginRecipesManager.Cast(GetPlugin(PluginRecipesManager));
        int recoveries = 0;
        int nativeReused = 0;
        int refused = 3;
        if (manager)
        {
            if (admitted && HCCommonRecoveryPolicy.HCCheckDefinition(manager.HCGetRegisteredSalvage("HCRecoverTeddyRag"), "HCRecoverTeddyRag"))
                recoveries = recoveries + 1;
            if (admitted && HCCommonRecoveryPolicy.HCCheckDefinition(manager.HCGetRegisteredSalvage("HCRecoverFabricRag"), "HCRecoverFabricRag"))
                recoveries = recoveries + 1;
            if (manager.HCGetRegisteredSalvage("CraftRag")) nativeReused = nativeReused + 1;
            if (manager.HCGetRegisteredSalvage("SplitBroom")) nativeReused = nativeReused + 1;
            if (manager.HCGetRegisteredSalvage("SplitLongWoodenStick")) nativeReused = nativeReused + 1;
        }
        refused = refused + 2 - recoveries;
        string state = "refused";
        if (recoveries == 2 && nativeReused == 3) state = "ready";
        Print("[HC Plan] HC-30 refusal=HC30_SOURCE_CLASS_UNVERIFIED candidate=WoodenMallet");
        Print("[HC Plan] HC-30 refusal=HC30_SOURCE_CLASS_UNVERIFIED candidate=HockeyStick_Black");
        Print("[HC Plan] HC-30 refusal=HC30_MATERIAL_UNPROVEN candidate=HockeyStick");
        Print(string.Format("[HC Plan] HC-30 recoveries=%1 native_reused=%2 refused=%3 state=%4 authored=2 observed=0 runtime=PENDING", recoveries, nativeReused, refused, state));
    }
}

class HCCommonRecoveryRecipe extends HCSalvageRecipe
{
    // Same HC-4 custody/health/tool policy, with this slice's exact source map.
    // RecipeBase.CheckRecipe (:497) still applies native CheckConditions after
    // CanDo; the native CanDo attachment refusal (:551-560) is also enforced
    // by HC-4's stricter IsOwnedEmptyLooseItem on both ingredients.
    // Object.c:467,517,892,994,1219: type/alive/config/health/ruined;
    // ItemBase.c:3485-3493: quantity; PlayerBase.c:3925: unconscious state.
    // Empty/loose custody is inherited from HC-4, not weakened for containers.
    override bool CanDo(ItemBase ingredients[], PlayerBase player)
    {
        if (!HCCraftingGate.CanPreviewOrCraft() || !player || !player.IsAlive() || player.IsUnconscious())
            return false;
        if (!ingredients[0] || !ingredients[1] || ingredients[0] == ingredients[1])
            return false;
        if (!HCCommonRecoveryPolicy.HCAllowsSource(m_HCInputType, ingredients[0].GetType()) || !HCSalvageTools.Allows(m_HCToolType, ingredients[1].GetType()))
            return false;
        if (!IsSourceConditionValid(ingredients[0]) || ingredients[1].IsRuined())
            return false;
        if (!IsOwnedEmptyLooseItem(ingredients[0], player) || !IsOwnedEmptyLooseItem(ingredients[1], player))
            return false;
        if (ingredients[1].GetHealth("", "") <= m_HCWear)
            return false;
        if (ingredients[0].ConfigGetFloat("ragQuantity") > 0)
            return false;
        if (m_HCInputType == "HCRecoverFabricRag")
            return ingredients[0].HasQuantity() && ingredients[0].GetQuantity() >= 1;
        return !ingredients[0].HasQuantity();
    }
}

class HCRecoverTeddyRag extends HCCommonRecoveryRecipe
{
    override void Init()
    {
        // New seed intentionally adds no sources through HC-4's closed map.
        Configure("Recover rag from empty teddy", "HCRecoverTeddyRag", "KitchenKnife", "Rag", 1, 5, 2);
        InsertIngredient(0, "Bear_Beige");
        InsertIngredient(0, "Bear_Dark");
        InsertIngredient(0, "Bear_Pink");
        InsertIngredient(0, "Bear_White");
    }
}

class HCRecoverFabricRag extends HCCommonRecoveryRecipe
{
    override void Init()
    {
        Configure("Cut one fabric unit into a rag", "HCRecoverFabricRag", "KitchenKnife", "Rag", 1, 5, 2);
        InsertIngredient(0, "Fabric");
        m_IngredientDestroy[0] = false;
        m_MinQuantityIngredient[0] = 1;
        m_IngredientAddQuantity[0] = -1;
    }
}
