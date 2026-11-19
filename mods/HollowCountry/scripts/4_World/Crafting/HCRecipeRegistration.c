// Register in the native constructor/cache phase on EVERY peer, in identical order.
// Never gate registration on profile settings or mission/module initialization.
modded class PluginRecipesManager
{
    override void RegisterRecipies()
    {
        super.RegisterRecipies();
        // Native PluginRecipesManagerBase.c:11,131-141 (1.30.164289).
        UnregisterRecipe("CraftFenceKit");
        UnregisterRecipe("CraftWatchtowerKit");
        UnregisterRecipe("CraftTerritoryFlagKit");
        UnregisterRecipe("CraftShelterKit");
        RegisterRecipe(new HCSalvageCamoNet);
        RegisterRecipe(new HCSalvageCableReel);
        RegisterRecipe(new HCRecoverLargeLeather);
        RegisterRecipe(new HCRecoverMediumLeather);
        RegisterRecipe(new HCRecoverBatWood);
        RegisterRecipe(new HCRecoverNailedBat);
        RegisterRecipe(new HCRecoverBarbedBat);
        RegisterRecipe(new HCRecoverRuinedCrate);
        RegisterRecipe(new HCRecoverRuinedLargeLeather);
        RegisterRecipe(new HCRecoverRuinedBatWood);
        RegisterRecipe(new HCRecoverRuinedNailedBat);
    }
}
