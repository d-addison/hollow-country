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
        return 0;
    }

    static string ToolAt(string seed, int index)
    {
        if (seed == "Pliers" && index == 0)
            return "Pliers";
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

class HCSalvageRecipe extends RecipeBase
{
    protected string m_HCInputType;
    protected string m_HCToolType;
    protected float m_HCWear;
    protected bool m_HCOutputReady;
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
        InsertIngredient(0, inputType);
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

    protected bool IsOwnedEmptyLooseItem(ItemBase item, PlayerBase player)
    {
        if (!item || item.IsRuined() || item.IsSetForDeletion() || !item.GetInventory())
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
        if (!ingredients[0].IsKindOf(m_HCInputType) || !HCSalvageTools.Allows(m_HCToolType, ingredients[1].GetType()))
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

    override void SpawnItems(ItemBase ingredients[], PlayerBase player, array<ItemBase> spawned_objects)
    {
        m_HCOutputReady = false;
        super.SpawnItems(ingredients, player, spawned_objects);
        // Exactly one result stack. If inventory AND native ground spawning fail,
        // leave ingredients/tool untouched. Do not retry or invent another spawn.
        if (spawned_objects.Count() == 1 && spawned_objects[0])
            m_HCOutputReady = true;
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
        // Native inheritance already copied source condition. Salvage loses another
        // quarter of normalized condition; no pristine output from damaged stock.
        ItemBase result = results[0];
        float condition = ingredients[0].GetHealth01("", "") * 0.75;
        result.SetHealth("", "", condition * result.GetMaxHealth("", ""));
        HCCraftingGate.RecordCraft();
    }
}

class HCSalvageCamoNet extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Salvage netting from camo net", "CamoNet", "KitchenKnife", "Netting", 2, 5, 2);
    }
}

class HCSalvageCableReel extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Recover wire from cable reel", "CableReel", "Pliers", "MetalWire", 1, 5, 2);
    }
}

class HCSalvageLeatherBelt extends HCSalvageRecipe
{
    override void Init()
    {
        Configure("Salvage leather from empty belt", "LeatherBelt_ColorBase", "KitchenKnife", "TannedLeather", 1, 3, 2);
    }
}
