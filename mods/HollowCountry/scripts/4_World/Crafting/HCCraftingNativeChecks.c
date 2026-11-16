// Read-only native checks executed on enabled server start. No test items spawned.
// Passing validates definitions/config only, NOT inventory or multiplayer behavior.
class HCCraftingNativeChecks
{
    static bool CheckDefinition(RecipeBase recipe, string className, string inputType, string toolType, string outputType, int quantity, float wear)
    {
        if (!recipe || recipe.ClassName() != className)
            return false;
        int registeredId = PluginRecipesManager.RecipeIDFromClassname(className);
        if (registeredId < 0 || recipe.GetID() != registeredId)
            return false;
        if (recipe.m_NumberOfResults != 1 || recipe.m_ItemsToCreate[0] != outputType)
            return false;
        if (recipe.m_Ingredients[0].Count() != 1 || recipe.m_Ingredients[0][0] != inputType)
            return false;
        if (recipe.m_Ingredients[1].Count() != 1 || recipe.m_Ingredients[1][0] != toolType)
            return false;
        if (!recipe.m_IngredientDestroy[0] || recipe.m_IngredientDestroy[1])
            return false;
        if (recipe.m_IngredientAddHealth[1] != -wear || recipe.m_ResultSetQuantity[0] != quantity)
            return false;
        // Native full-stack fill wins over fixed quantity; replacement transfers
        // source variables (including quantity) after setting the result yield.
        if (recipe.m_ResultSetFullQuantity[0] || recipe.m_ResultReplacesIngredient[0] != -1)
            return false;
        // Native color inheritance changes the classname before result spawning.
        if (recipe.m_ResultInheritsColor[0] != -1)
            return false;
        // Tool quantity changes run independently after native health wear.
        if (recipe.m_IngredientAddQuantity[1] != 0)
            return false;
        if (recipe.IsInstaRecipe() || recipe.IsRepeatable() || recipe.IsRecipeAnywhere() || recipe.GetLengthInSecs() != 8)
            return false;
        if (recipe.m_ResultToInventory[0] != -1 || recipe.m_ResultInheritsHealth[0] != 0)
            return false;
        string outputPath = "CfgVehicles " + outputType;
        if (!GetGame().ConfigIsExisting("CfgVehicles " + inputType) || !GetGame().ConfigIsExisting("CfgVehicles " + toolType))
            return false;
        if (!GetGame().ConfigIsExisting(outputPath) || GetGame().ConfigGetInt(outputPath + " scope") != 2)
            return false;
        // Native singleton items may have no quantity at all (SetQuantity is a no-op).
        // Split stacks prefer varStackMax over varQuantityMax in ItemBase.
        float maxQuantity = GetGame().ConfigGetFloat(outputPath + " varStackMax");
        if (maxQuantity <= 0)
            maxQuantity = GetGame().ConfigGetFloat(outputPath + " varQuantityMax");
        if (quantity > 1 && maxQuantity < quantity)
            return false;
        return true;
    }

    static bool CheckCompletionGuard()
    {
        HCCraftingCommitGuard guard = new HCCraftingCommitGuard;
        if (!guard.TryEnter() || guard.TryEnter())
            return false;
        guard.Release();
        if (!guard.TryEnter())
            return false;
        guard.Release();
        return true;
    }

    static bool Run()
    {
        PluginRecipesManager manager = PluginRecipesManager.Cast(GetPlugin(PluginRecipesManager));
        if (!manager)
            return false;
        if (!CheckCompletionGuard())
            return false;
        if (!CheckDefinition(manager.HCGetRegisteredSalvage("HCSalvageCamoNet"), "HCSalvageCamoNet", "CamoNet", "KitchenKnife", "Netting", 2, 5))
            return false;
        if (!CheckDefinition(manager.HCGetRegisteredSalvage("HCSalvageCableReel"), "HCSalvageCableReel", "CableReel", "Pliers", "MetalWire", 1, 5))
            return false;
        if (!CheckDefinition(manager.HCGetRegisteredSalvage("HCSalvageLeatherBelt"), "HCSalvageLeatherBelt", "LeatherBelt_ColorBase", "KitchenKnife", "TannedLeather", 1, 3))
            return false;
        return true;
    }
}
