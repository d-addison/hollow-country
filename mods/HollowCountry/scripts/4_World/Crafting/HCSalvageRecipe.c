// Guards synchronous reentry on the native manager's shared recipe instance.
// Deferred source deletion is separately rejected by IsSetForDeletion().
class HCCraftingCommitGuard
{
    protected bool m_Busy;

    bool TryEnter()
    {
        if (m_Busy)
            return false;
        m_Busy = true;
        return true;
    }

    void Release() { m_Busy = false; }
}

// Original salvage policy over installed 1.30.164289 RecipeBase mutations.
// This is NOT an atomic transaction or a persistence/crash-recovery layer.
// Exact alternatives observed in registered native cloth/net cutting recipes.
// KitchenKnife is the existing recipe's selector for this bounded family;
// Pliers remains a distinct single-tool policy. No per-preview allocation.
class HCSalvageTools
{
    static int ToolCount(string seed)
    {
        if (seed == "KitchenKnife")
            return 36;
        if (seed == "Pliers")
            return 1;
        if (seed == "Hacksaw")
            return 2;
        if (seed == "Crowbar")
            return 4;
        return 0;
    }

    static string ToolAt(string seed, int index)
    {
        if (seed == "Pliers" && index == 0)
            return "Pliers";
        if (seed == "Hacksaw" && index == 0) return "Hacksaw";
        if (seed == "Hacksaw" && index == 1) return "HandSaw";
        if (seed == "Crowbar" && index == 0) return "Crowbar";
        if (seed == "Crowbar" && index == 1) return "WoodAxe";
        if (seed == "Crowbar" && index == 2) return "Hatchet";
        if (seed == "Crowbar" && index == 3) return "FirefighterAxe";
        if (seed != "KitchenKnife")
            return "";
        if (index == 0) return "KitchenKnife";
        if (index == 1) return "AK_Bayonet";
        if (index == 2) return "Akinaka";
        if (index == 3) return "BoneKnife";
        if (index == 4) return "BrickTrowel";
        if (index == 5) return "Cleaver";
        if (index == 6) return "CombatKnife";
        if (index == 7) return "Crowbar";
        if (index == 8) return "CrudeMachete";
        if (index == 9) return "DonerKnife";
        if (index == 10) return "FangeKnife";
        if (index == 11) return "FarmingHoe";
        if (index == 12) return "FieldShovel";
        if (index == 13) return "FirefighterAxe";
        if (index == 14) return "Hacksaw";
        if (index == 15) return "HandSaw";
        if (index == 16) return "Hatchet";
        if (index == 17) return "HayHook";
        if (index == 18) return "HuntingKnife";
        if (index == 19) return "Iceaxe";
        if (index == 20) return "Jambiya";
        if (index == 21) return "KukriKnife";
        if (index == 22) return "M9A1_Bayonet";
        if (index == 23) return "Machete";
        if (index == 24) return "Mosin_Bayonet";
        if (index == 25) return "OrientalMachete";
        if (index == 26) return "Pickaxe";
        if (index == 27) return "SKS_Bayonet";
        if (index == 28) return "Scimitar";
        if (index == 29) return "Screwdriver";
        if (index == 30) return "Shovel";
        if (index == 31) return "Sickle";
        if (index == 32) return "SteakKnife";
        if (index == 33) return "StoneKnife";
        if (index == 34) return "Sword";
        if (index == 35) return "WoodAxe";
        return "";
    }

    static bool Allows(string seed, string actualType)
    {
        int count = ToolCount(seed);
        for (int i = 0; i < count; i++)
        {
            if (ToolAt(seed, i) == actualType)
                return true;
        }
        return false;
    }

    static bool CheckRegistered(array<string> tools, string seed)
    {
        int count = ToolCount(seed);
        if (!tools || count == 0 || tools.Count() != count)
            return false;
        for (int i = 0; i < count; i++)
        {
            string tool = ToolAt(seed, i);
            if (tools[i] != tool)
                return false;
            if (!GetGame().ConfigIsExisting("CfgVehicles " + tool))
                return false;
        }
        return true;
    }
}

// Exact installed source classes only; engine ancestry matching is rechecked.
class HCSalvageSources
{
    static int SourceCount(string seed)
    {
        if (seed == "HCRecoverLargeLeather") return 8;
        if (seed == "HCRecoverMediumLeather") return 5;
        if (seed == "HCRecoverBatWood") return 2;
        if (seed == "HCRecoverNailedBat") return 1;
        if (seed == "HCRecoverBarbedBat") return 1;
        if (seed == "HCRecoverRuinedCrate") return 1;
        if (seed == "CamoNet" || seed == "CableReel") return 1;
        return 0;
    }

    static string SourceAt(string seed, int index)
    {
        if (seed == "HCRecoverLargeLeather")
        {
            if (index == 0) return "LeatherJacket_Beige";
            if (index == 1) return "LeatherJacket_Black";
            if (index == 2) return "LeatherJacket_Brown";
            if (index == 3) return "LeatherJacket_Natural";
            if (index == 4) return "LeatherStorageVest_Beige";
            if (index == 5) return "LeatherStorageVest_Black";
            if (index == 6) return "LeatherStorageVest_Brown";
            if (index == 7) return "LeatherStorageVest_Natural";
        }
        if (seed == "HCRecoverMediumLeather")
        {
            if (index == 0) return "LeatherPants_Beige";
            if (index == 1) return "LeatherPants_Black";
            if (index == 2) return "LeatherPants_Brown";
            if (index == 3) return "LeatherPants_Natural";
            if (index == 4) return "LeatherShirt_Natural";
        }
        if (seed == "HCRecoverBatWood")
        {
            if (index == 0) return "BaseballBat";
            if (index == 1) return "XmasBaseballBat";
        }
        if (seed == "HCRecoverNailedBat")
        {
            if (index == 0) return "NailedBaseballBat";
        }
        if (seed == "HCRecoverBarbedBat")
        {
            if (index == 0) return "BarbedBaseballBat";
        }
        if (seed == "HCRecoverRuinedCrate")
        {
            if (index == 0) return "WoodenCrate";
        }
        if ((seed == "CamoNet" || seed == "CableReel") && index == 0) return seed;
        return "";
    }

    static bool AllowsSource(string seed, string actualType)
    {
        int count = SourceCount(seed);
        for (int i = 0; i < count; i++)
        {
            if (SourceAt(seed, i) == actualType)
                return true;
        }
        return false;
    }
}

class HCSalvageRecipe extends RecipeBase
{
    protected string m_HCInputType;
    protected string m_HCToolType;
    protected float m_HCWear;
    protected bool m_HCOutputReady;
    protected bool m_HCRuinedOnly;
    protected float m_HCSourceHealth;
    protected float m_HCSourceWet;
    protected int m_HCSourceAgents;
    protected ref HCCraftingCommitGuard m_HCCommitGuard = new HCCraftingCommitGuard;

    void Configure(string label, string inputType, string toolType, string outputType, int quantity, float wear, float animationUnits)
    {
        m_Name = label;
        m_HCInputType = inputType;
        m_HCToolType = toolType;
        m_HCWear = wear;
        m_IsInstaRecipe = false;
        m_AnywhereInInventory = false;
        m_AnimationLength = animationUnits;
        m_Specialty = 0;
        for (int i = 0; i < MAX_NUMBER_OF_INGREDIENTS; i++)
        {
            m_MinDamageIngredient[i] = -1;
            m_MaxDamageIngredient[i] = 3;
            m_MinQuantityIngredient[i] = -1;
            m_MaxQuantityIngredient[i] = -1;
            m_IngredientAddHealth[i] = 0;
            m_IngredientSetHealth[i] = -1;
            m_IngredientAddQuantity[i] = 0;
            m_IngredientDestroy[i] = false;
            m_IngredientUseSoftSkills[i] = false;
        }
        int sourceCount = HCSalvageSources.SourceCount(inputType);
        for (int sourceIndex = 0; sourceIndex < sourceCount; sourceIndex++)
        {
            InsertIngredient(0, HCSalvageSources.SourceAt(inputType, sourceIndex));
        }
        int toolCount = HCSalvageTools.ToolCount(toolType);
        for (int toolIndex = 0; toolIndex < toolCount; toolIndex++)
        {
            InsertIngredient(1, HCSalvageTools.ToolAt(toolType, toolIndex));
        }
        m_IngredientDestroy[0] = true;
        m_IngredientAddHealth[1] = -wear;
        AddResult(outputType);
        m_ResultSetFullQuantity[0] = false;
        m_ResultSetQuantity[0] = quantity;
        m_ResultSetHealth[0] = -1;
        m_ResultInheritsHealth[0] = 0;
        m_ResultInheritsColor[0] = -1;
        m_ResultToInventory[0] = -1;
        m_ResultUseSoftSkills[0] = false;
        m_ResultReplacesIngredient[0] = -1;
    }

    void AddRecoveryResult(string outputType, int quantity)
    {
        int resultIndex = m_NumberOfResults;
        AddResult(outputType);
        m_ResultSetFullQuantity[resultIndex] = false;
        m_ResultSetQuantity[resultIndex] = quantity;
        m_ResultSetHealth[resultIndex] = -1;
        m_ResultInheritsHealth[resultIndex] = 0;
        m_ResultInheritsColor[resultIndex] = -1;
        m_ResultToInventory[resultIndex] = -1;
        m_ResultUseSoftSkills[resultIndex] = false;
        m_ResultReplacesIngredient[resultIndex] = -1;
    }

    protected bool IsSourceConditionValid(ItemBase item)
    {
        if (m_HCRuinedOnly)
            return item.GetHealthLevel() == 4;
        return !item.IsRuined();
    }

    protected bool IsOwnedEmptyLooseItem(ItemBase item, PlayerBase player)
    {
        if (!item || item.IsSetForDeletion() || !item.GetInventory())
            return false;
        // Reject ground/shared/corpse materials, worn belts and tent/base attachments.
        if (item.GetHierarchyRootPlayer() != player || item.GetInventory().IsAttachment())
            return false;
        if (item.GetInventory().AttachmentCount() > 0)
            return false;
        CargoBase cargo = item.GetInventory().GetCargo();
        if (cargo && cargo.GetItemCount() > 0)
            return false;
        return true;
    }

    override bool CanDo(ItemBase ingredients[], PlayerBase player)
    {
        if (!HCCraftingGate.CanPreviewOrCraft() || !player || !player.IsAlive() || player.IsUnconscious())
            return false;
        if (!ingredients[0] || !ingredients[1] || ingredients[0] == ingredients[1])
            return false;
        // RecipeBase.CheckRecipe checks conditions, not class membership. Recheck types here.
        if (!HCSalvageSources.AllowsSource(m_HCInputType, ingredients[0].GetType()) || !HCSalvageTools.Allows(m_HCToolType, ingredients[1].GetType()))
            return false;
        if (!IsSourceConditionValid(ingredients[0]) || ingredients[1].IsRuined())
            return false;
        if (!IsOwnedEmptyLooseItem(ingredients[0], player) || !IsOwnedEmptyLooseItem(ingredients[1], player))
            return false;
        if (ingredients[1].GetHealth("", "") <= m_HCWear)
            return false;
        if (ingredients[0].IsKindOf("CableReel"))
        {
            if (!ingredients[0].GetCompEM())
                return false;
            if (ingredients[0].GetCompEM().IsPlugged() || ingredients[0].GetCompEM().GetPluggedDevicesCount() > 0)
                return false;
        }
        return super.CanDo(ingredients, player);
    }

    override void PerformRecipe(ItemBase item1, ItemBase item2, PlayerBase player)
    {
        // Client preview is permissive about server settings, never about committing.
        if (!GetGame().IsServer())
            return;
        if (!player || !item1 || !item2)
            return;
        if (!m_HCCommitGuard.TryEnter())
            return;
        m_HCOutputReady = false;
        super.PerformRecipe(item1, item2, player);
        m_HCOutputReady = false;
        m_HCCommitGuard.Release();
    }

    protected void DiscardOutputs(array<ItemBase> spawned_objects)
    {
        // Native SpawnItems supplies only this invocation's fresh allocations.
        for (int outputIndex = 0; outputIndex < spawned_objects.Count(); outputIndex++)
        {
            ItemBase provisional = spawned_objects[outputIndex];
            if (provisional)
                provisional.Delete();
        }
        spawned_objects.Clear();
        m_HCOutputReady = false;
    }

    protected bool OutputsMatch(array<ItemBase> spawned_objects, bool checkQuantity)
    {
        if (spawned_objects.Count() != m_NumberOfResults)
            return false;
        for (int resultIndex = 0; resultIndex < m_NumberOfResults; resultIndex++)
        {
            ItemBase recovery = spawned_objects[resultIndex];
            if (!recovery || recovery.IsSetForDeletion() || recovery.GetType() != m_ItemsToCreate[resultIndex])
                return false;
            if (checkQuantity && recovery.HasQuantity() && recovery.GetQuantity() != m_ResultSetQuantity[resultIndex])
                return false;
            if (checkQuantity && !recovery.HasQuantity() && m_ResultSetQuantity[resultIndex] != 1)
                return false;
        }
        return true;
    }

    override void SpawnItems(ItemBase ingredients[], PlayerBase player, array<ItemBase> spawned_objects)
    {
        m_HCOutputReady = false;
        // Snapshot before native ingredient mutation or deferred source deletion.
        m_HCSourceHealth = ingredients[0].GetHealth01("", "");
        m_HCSourceWet = ingredients[0].GetWet();
        m_HCSourceAgents = ingredients[0].GetAgents();
        super.SpawnItems(ingredients, player, spawned_objects);
        if (!OutputsMatch(spawned_objects, false))
        {
            DiscardOutputs(spawned_objects);
            return;
        }
        m_HCOutputReady = true;
    }

    override void ApplyModificationsResults(ItemBase sorted[], array<ItemBase> results, ItemBase result, PlayerBase player)
    {
        if (!m_HCOutputReady)
            return;
        super.ApplyModificationsResults(sorted, results, result, player);
        if (!OutputsMatch(results, true))
            DiscardOutputs(results);
    }

    override void ApplyModificationsIngredients(ItemBase sorted[], PlayerBase player)
    {
        if (!m_HCOutputReady)
            return;
        super.ApplyModificationsIngredients(sorted, player);
    }

    override void Do(ItemBase ingredients[], PlayerBase player, array<ItemBase> results, float specialty_weight)
    {
        if (!m_HCOutputReady)
            return;
        float condition = m_HCSourceHealth * 0.75;
        if (m_HCRuinedOnly)
            condition = 0.10;
        for (int resultIndex = 0; resultIndex < results.Count(); resultIndex++)
        {
            ItemBase recovery = results[resultIndex];
            recovery.SetHealth("", "", condition * recovery.GetMaxHealth("", ""));
            // Deliberately select only contamination and wetness. Generic variable
            // transfer also copies quantity, energy, ammo and food stage.
            recovery.TransferAgents(m_HCSourceAgents);
            recovery.SetWet(m_HCSourceWet);
        }
        HCCraftingGate.RecordCraft();
    }
}

class HCSalvageCamoNet extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Salvage netting from camo net", "CamoNet", "KitchenKnife", "Netting", 1, 5, 2);
    }
}

class HCSalvageCableReel extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Recover wire from cable reel", "CableReel", "Pliers", "MetalWire", 1, 5, 2);
    }
}

class HCRecoverLargeLeather extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Recover leather panels", "HCRecoverLargeLeather", "KitchenKnife", "TannedLeather", 2, 5, 2);
    }
}

class HCRecoverMediumLeather extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Recover leather panel", "HCRecoverMediumLeather", "KitchenKnife", "TannedLeather", 1, 5, 2);
    }
}

class HCRecoverBatWood extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Saw bat into sticks", "HCRecoverBatWood", "Hacksaw", "WoodenStick", 2, 5, 2);
    }
}

class HCRecoverNailedBat extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Recover sticks and nails", "HCRecoverNailedBat", "Hacksaw", "WoodenStick", 1, 8, 3);
        AddRecoveryResult("Nail", 4);
    }
}

class HCRecoverBarbedBat extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Recover wire from bat", "HCRecoverBarbedBat", "Pliers", "MetalWire", 1, 8, 3);
    }
}

class HCRecoverRuinedCrate extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Recover planks and nails from ruined crate", "HCRecoverRuinedCrate", "Crowbar", "WoodenPlank", 1, 20, 3);
        AddRecoveryResult("Nail", 2);
        m_HCRuinedOnly = true;
        m_MinDamageIngredient[0] = 4;
        m_MaxDamageIngredient[0] = 4;
    }
}
