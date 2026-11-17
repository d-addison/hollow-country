// Register in the native constructor/cache phase on EVERY peer, in identical order.
// Never gate registration on profile settings or mission/module initialization.
modded class PluginRecipesManager
{
    override void RegisterRecipies()
    {
        super.RegisterRecipies();
        RegisterRecipe(new HCSalvageCamoNet);
        RegisterRecipe(new HCSalvageCableReel);
        RegisterRecipe(new HCRecoverLargeLeather);
        RegisterRecipe(new HCRecoverMediumLeather);
        RegisterRecipe(new HCRecoverBatWood);
        RegisterRecipe(new HCRecoverNailedBat);
        RegisterRecipe(new HCRecoverBarbedBat);
        RegisterRecipe(new HCRecoverRuinedCrate);
    }
}
