// Read-only native checks executed on enabled server start. No test items spawned.
// Passing validates definitions/config only, NOT inventory or multiplayer behavior.
class HCCraftingNativeChecks
{
    static bool CheckDefinition(RecipeBase recipe, string className, string inputType, string toolType, string outputType, int quantity, float wear)
    {
        if (PluginRecipesManager.RecipeIDFromClassname(className) < 0)
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
        if (!CheckCompletionGuard())
            return false;
        if (!CheckDefinition(new HCSalvageCamoNet, "HCSalvageCamoNet", "CamoNet", "KitchenKnife", "Netting", 2, 5))
            return false;
        if (!CheckDefinition(new HCSalvageCableReel, "HCSalvageCableReel", "CableReel", "Pliers", "MetalWire", 1, 5))
            return false;
        if (!CheckDefinition(new HCSalvageLeatherBelt, "HCSalvageLeatherBelt", "LeatherBelt_ColorBase", "KitchenKnife", "TannedLeather", 1, 3))
            return false;
        return true;
    }
}
