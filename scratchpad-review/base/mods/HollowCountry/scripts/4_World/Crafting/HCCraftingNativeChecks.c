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
        if (!HCSalvageTools.CheckRegistered(recipe.m_Ingredients[1], toolType))
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

    static bool CheckRecovery(RecipeBase recipe, string className, string toolType, string firstOutput, int firstQuantity, string secondOutput, int secondQuantity, float wear, float animationUnits, bool ruinedOnly)
    {
        if (!recipe || recipe.ClassName() != className || recipe.GetID() != PluginRecipesManager.RecipeIDFromClassname(className))
            return false;
        int sourceCount = HCSalvageSources.SourceCount(className);
        if (sourceCount == 0 || recipe.m_Ingredients[0].Count() != sourceCount)
            return false;
        for (int sourceIndex = 0; sourceIndex < sourceCount; sourceIndex++)
        {
            string sourceType = HCSalvageSources.SourceAt(className, sourceIndex);
            if (recipe.m_Ingredients[0][sourceIndex] != sourceType || !GetGame().ConfigIsExisting("CfgVehicles " + sourceType))
                return false;
        }
        if (!HCSalvageTools.CheckRegistered(recipe.m_Ingredients[1], toolType))
            return false;
        int resultCount = 1;
        if (secondOutput != "")
            resultCount = 2;
        if (recipe.m_NumberOfResults != resultCount)
            return false;
        if (recipe.m_ItemsToCreate[0] != firstOutput || recipe.m_ResultSetQuantity[0] != firstQuantity)
            return false;
        if (resultCount == 2 && (recipe.m_ItemsToCreate[1] != secondOutput || recipe.m_ResultSetQuantity[1] != secondQuantity))
            return false;
        for (int resultIndex = 0; resultIndex < resultCount; resultIndex++)
        {
            string resultPath = "CfgVehicles " + recipe.m_ItemsToCreate[resultIndex];
            if (!GetGame().ConfigIsExisting(resultPath) || GetGame().ConfigGetInt(resultPath + " scope") != 2)
                return false;
            float maxQuantity = GetGame().ConfigGetFloat(resultPath + " varStackMax");
            if (maxQuantity <= 0)
                maxQuantity = GetGame().ConfigGetFloat(resultPath + " varQuantityMax");
            if (recipe.m_ResultSetQuantity[resultIndex] > 1 && maxQuantity < recipe.m_ResultSetQuantity[resultIndex])
                return false;
            if (recipe.m_ResultSetFullQuantity[resultIndex] || recipe.m_ResultReplacesIngredient[resultIndex] != -1 || recipe.m_ResultInheritsColor[resultIndex] != -1)
                return false;
            if (recipe.m_ResultToInventory[resultIndex] != -1 || recipe.m_ResultInheritsHealth[resultIndex] != 0 || recipe.m_ResultUseSoftSkills[resultIndex])
                return false;
        }
        if (!recipe.m_IngredientDestroy[0] || recipe.m_IngredientDestroy[1] || recipe.m_IngredientAddHealth[1] != -wear || recipe.m_IngredientAddQuantity[1] != 0)
            return false;
        if (recipe.m_IngredientUseSoftSkills[0] || recipe.m_IngredientUseSoftSkills[1] || recipe.GetSpecialty() != 0)
            return false;
        if (recipe.IsInstaRecipe() || recipe.IsRepeatable() || recipe.IsRecipeAnywhere() || recipe.GetLengthInSecs() != animationUnits * 4)
            return false;
        if (recipe.m_MaxDamageIngredient[1] != 3)
            return false;
        if (ruinedOnly)
            return recipe.m_MinDamageIngredient[0] == 4 && recipe.m_MaxDamageIngredient[0] == 4;
        return recipe.m_MinDamageIngredient[0] == -1 && recipe.m_MaxDamageIngredient[0] == 3;
    }

    static bool Run()
    {
        PluginRecipesManager manager = PluginRecipesManager.Cast(GetPlugin(PluginRecipesManager));
        if (!manager)
            return false;
        if (!CheckCompletionGuard())
            return false;
        if (!CheckDefinition(manager.HCGetRegisteredSalvage("HCSalvageCamoNet"), "HCSalvageCamoNet", "CamoNet", "KitchenKnife", "Netting", 1, 5))
            return false;
        if (!CheckDefinition(manager.HCGetRegisteredSalvage("HCSalvageCableReel"), "HCSalvageCableReel", "CableReel", "Pliers", "MetalWire", 1, 5))
            return false;
        if (!CheckRecovery(manager.HCGetRegisteredSalvage("HCRecoverLargeLeather"), "HCRecoverLargeLeather", "KitchenKnife", "TannedLeather", 2, "", 0, 5, 2, false))
            return false;
        if (!CheckRecovery(manager.HCGetRegisteredSalvage("HCRecoverMediumLeather"), "HCRecoverMediumLeather", "KitchenKnife", "TannedLeather", 1, "", 0, 5, 2, false))
            return false;
        if (!CheckRecovery(manager.HCGetRegisteredSalvage("HCRecoverBatWood"), "HCRecoverBatWood", "Hacksaw", "WoodenStick", 2, "", 0, 5, 2, false))
            return false;
        if (!CheckRecovery(manager.HCGetRegisteredSalvage("HCRecoverNailedBat"), "HCRecoverNailedBat", "Hacksaw", "WoodenStick", 1, "Nail", 4, 8, 3, false))
            return false;
        if (!CheckRecovery(manager.HCGetRegisteredSalvage("HCRecoverBarbedBat"), "HCRecoverBarbedBat", "Pliers", "MetalWire", 1, "", 0, 8, 3, false))
            return false;
        if (!CheckRecovery(manager.HCGetRegisteredSalvage("HCRecoverRuinedCrate"), "HCRecoverRuinedCrate", "Crowbar", "WoodenPlank", 1, "Nail", 2, 20, 3, true))
            return false;
        return true;
    }
}
