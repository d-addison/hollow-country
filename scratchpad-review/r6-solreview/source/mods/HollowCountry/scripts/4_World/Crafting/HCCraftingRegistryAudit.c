// Read only the actual registered instances; fresh recipes can hide cache drift.
// Native 1.30 manager exposes m_RecipeList, RecipeIDFromClassname and GetID.
modded class PluginRecipesManager
{
    RecipeBase HCGetRegisteredSalvage(string className)
    {
        int registeredId = RecipeIDFromClassname(className);
        if (registeredId < 0 || registeredId >= m_RecipeList.Count())
            return null;
        RecipeBase recipe = m_RecipeList[registeredId];
        if (!recipe || recipe.ClassName() != className || recipe.GetID() != registeredId)
            return null;
        return recipe;
    }
}
