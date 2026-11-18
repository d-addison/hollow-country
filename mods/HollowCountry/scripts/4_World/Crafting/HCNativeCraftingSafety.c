// Surgical guards around the existing registered native instances. No new native
// registration, replacement recipe, synthetic inventory state or yield rewrite.
class HCNativeCraftingSafety
{
    static bool IsScoped(string recipeName)
    {
        // F01
        if (recipeName == "CraftRag") return true;
        if (recipeName == "CraftBurlapStrips") return true;
        if (recipeName == "CraftRagRope") return true;
        if (recipeName == "CraftGutsRope") return true;
        if (recipeName == "CraftArmbandFlag") return true;
        if (recipeName == "CraftArmbandRag") return true;
        if (recipeName == "CraftArmbandRaincoat") return true;
        // F02
        if (recipeName == "CraftGhillieAttachment") return true;
        if (recipeName == "CraftGhillieBushrag") return true;
        if (recipeName == "CraftGhillieHood") return true;
        if (recipeName == "CraftGhillieSuit") return true;
        if (recipeName == "CraftGhillieTop") return true;
        if (recipeName == "DeCraftGhillieAttachment") return true;
        if (recipeName == "DeCraftGhillieBushrag") return true;
        if (recipeName == "DeCraftGhillieHood") return true;
        if (recipeName == "DeCraftGhillieSuit") return true;
        if (recipeName == "DeCraftGhillieTop") return true;
        if (recipeName == "DeCraftCamoNetShelter") return true;
        // F03
        if (recipeName == "CraftTannedLeather") return true;
        if (recipeName == "CraftLeatherBelt") return true;
        if (recipeName == "CraftLeatherHippack") return true;
        if (recipeName == "CraftLeatherSheath") return true;
        if (recipeName == "CraftLeatherSack") return true;
        if (recipeName == "CraftWaterskin") return true;
        if (recipeName == "DeCraftLeatherSack") return true;
        if (recipeName == "DeCraftWaterskin") return true;
        if (recipeName == "CraftFoxHeaddress") return true;
        // F04
        if (recipeName == "CraftCourierBag") return true;
        if (recipeName == "CraftDrysackBag") return true;
        if (recipeName == "CraftImprovisedBag") return true;
        if (recipeName == "CraftLeatherCourierBag") return true;
        if (recipeName == "CraftImprovisedLeatherBag") return true;
        if (recipeName == "DeCraftCourierBag") return true;
        if (recipeName == "DeCraftImprovisedBag") return true;
        if (recipeName == "DeCraftImprovisedLeatherBag") return true;
        if (recipeName == "DeCraftLeatherCourierBag") return true;
        // F05
        if (recipeName == "CraftWoodenCrate") return true;
        if (recipeName == "DeCraftWoodenCrate") return true;
        if (recipeName == "CraftWoodenPlank") return true;
        if (recipeName == "SawWoodenLog") return true;
        if (recipeName == "SplitFirewood") return true;
        if (recipeName == "SplitLongWoodenStick") return true;
        if (recipeName == "SplitBroom") return true;
        if (recipeName == "SplitStones") return true;
        if (recipeName == "CraftFenceKit") return true;
        if (recipeName == "CraftShelterKit") return true;
        if (recipeName == "CraftTerritoryFlagKit") return true;
        if (recipeName == "CraftWatchtowerKit") return true;
        // F06
        if (recipeName == "CraftFishNetTrap") return true;
        if (recipeName == "CraftFishingRod") return true;
        if (recipeName == "CraftRabbitSnare") return true;
        if (recipeName == "CraftSmallFishTrap") return true;
        if (recipeName == "CraftTripWire") return true;
        if (recipeName == "DeCraftFishNetTrap") return true;
        if (recipeName == "DeCraftFishingRod") return true;
        if (recipeName == "DeCraftSnareTrap") return true;
        if (recipeName == "DeCraftTripWire") return true;
        // F07
        if (recipeName == "CraftBoneHook") return true;
        if (recipeName == "CraftBoneKnife") return true;
        if (recipeName == "CraftStoneKnife") return true;
        if (recipeName == "CraftWoodenHook") return true;
        if (recipeName == "CraftSpearBone") return true;
        if (recipeName == "CraftSpearStone") return true;
        if (recipeName == "DeCraftSpear") return true;
        if (recipeName == "SharpenBroom") return true;
        if (recipeName == "SharpenLongStick") return true;
        if (recipeName == "CraftSplint") return true;
        if (recipeName == "DeCraftSplint") return true;
        // F08
        if (recipeName == "CraftFireplace") return true;
        if (recipeName == "CraftHandDrillKit") return true;
        if (recipeName == "CraftHandDrillKitBirch") return true;
        if (recipeName == "CraftHandDrillKitPalm") return true;
        if (recipeName == "CraftTorch") return true;
        if (recipeName == "CraftLongTorch") return true;
        if (recipeName == "CraftCookingStand") return true;
        if (recipeName == "DeCraftCookingStand") return true;
        if (recipeName == "DeCraftHandDrillKit") return true;
        if (recipeName == "DeCraftHandDrillKitBirch") return true;
        if (recipeName == "DeCraftHandDrillKitPalm") return true;
        if (recipeName == "ExtinguishTorch") return true;
        if (recipeName == "UpgradeTorchWithLard") return true;
        if (recipeName == "UpgradeTorchWithLiquidFuel") return true;
        // F09
        if (recipeName == "CraftMetalWire") return true;
        if (recipeName == "CraftTruck01DoubleWheel") return true;
        if (recipeName == "DeCraftTruck01DoubleWheel") return true;
        if (recipeName == "FuelChainsaw") return true;
        // F10
        if (recipeName == "CleanWeapon") return true;
        if (recipeName == "RepairElectric") return true;
        if (recipeName == "RepairEpoxy") return true;
        if (recipeName == "RepairPlanks") return true;
        if (recipeName == "RepairWithLeatherSewingKit") return true;
        if (recipeName == "RepairWithPliers") return true;
        if (recipeName == "RepairWithSewingKit") return true;
        if (recipeName == "RepairWithTape") return true;
        if (recipeName == "RepairWithTireKit") return true;
        if (recipeName == "SharpenMelee") return true;
        // F11
        if (recipeName == "BloodTest") return true;
        if (recipeName == "ChelateWater") return true;
        if (recipeName == "CraftBloodBagIV") return true;
        if (recipeName == "CraftSalineBagIV") return true;
        if (recipeName == "DisinfectItem") return true;
        if (recipeName == "FillSyringe") return true;
        if (recipeName == "PurifyWater") return true;
        if (recipeName == "CraftFeathers") return true;
        if (recipeName == "CutOutPepperSeeds") return true;
        if (recipeName == "CutOutPumpkinSeeds") return true;
        if (recipeName == "CutOutTomatoSeeds") return true;
        if (recipeName == "CutOutZucchiniSeeds") return true;
        if (recipeName == "OpenCan") return true;
        if (recipeName == "PeelPotato") return true;
        if (recipeName == "PrepareCarp") return true;
        if (recipeName == "PrepareCatfish") return true;
        if (recipeName == "PrepareChicken") return true;
        if (recipeName == "PrepareFox") return true;
        if (recipeName == "PrepareLizard") return true;
        if (recipeName == "PrepareMackerel") return true;
        if (recipeName == "PrepareRabbit") return true;
        if (recipeName == "PrepareSteelheadTrout") return true;
        if (recipeName == "PrepareWalleyePollock") return true;
        // F12
        if (recipeName == "CraftBaseBallBatBarbed") return true;
        if (recipeName == "CraftBaseBallBatNailed") return true;
        if (recipeName == "CraftSuppressor") return true;
        if (recipeName == "SawOFFB95") return true;
        if (recipeName == "SawOffIzh18") return true;
        if (recipeName == "SawOffIzh18Shotgun") return true;
        if (recipeName == "SawOffMagnum") return true;
        if (recipeName == "SawoffFAMAS") return true;
        if (recipeName == "SawoffMosin") return true;
        if (recipeName == "SawoffShotgunIzh43") return true;
        // F13
        if (recipeName == "AttachHolsterPouch") return true;
        if (recipeName == "AttachPouchesHolster") return true;
        if (recipeName == "CloseGunCase") return true;
        if (recipeName == "CloseScientificBriefcase") return true;
        if (recipeName == "CraftChristmasLightsHeadband") return true;
        if (recipeName == "CraftGasMask_Filter_Improvised") return true;
        if (recipeName == "CraftImprovisedExplosive") return true;
        if (recipeName == "CraftMortarMix") return true;
        if (recipeName == "CraftWitchHoodCoif") return true;
        if (recipeName == "DeCraftDetonator") return true;
        if (recipeName == "FillGasMask_Filter") return true;
        if (recipeName == "OpenGunCase") return true;
        if (recipeName == "OpenScientificBriefcase") return true;
        if (recipeName == "PokeHolesBarrel") return true;
        return false;
    }

    static bool HasRequiredQuantity(ItemBase ingredient, float debit)
    {
        if (!ingredient || ingredient.IsSetForDeletion())
            return false;
        if (ingredient.IsMagazine())
        {
            if (!Magazine.Cast(ingredient))
                return false;
            return Magazine.Cast(ingredient).GetAmmoCount() >= debit;
        }
        return ingredient.HasQuantity() && ingredient.GetQuantity() >= debit;
    }

    static bool NeedsEmptySource(string recipeName)
    {
        if (recipeName == "CraftRag") return true;
        if (recipeName == "CraftCourierBag") return true;
        if (recipeName == "CraftDrysackBag") return true;
        if (recipeName == "CraftImprovisedBag") return true;
        if (recipeName == "CraftLeatherCourierBag") return true;
        if (recipeName == "CraftImprovisedLeatherBag") return true;
        if (recipeName == "DeCraftCourierBag") return true;
        if (recipeName == "DeCraftImprovisedBag") return true;
        if (recipeName == "DeCraftLeatherCourierBag") return true;
        if (recipeName == "DeCraftImprovisedLeatherBag") return true;
        if (recipeName == "DeCraftWoodenCrate") return true;
        if (recipeName == "DeCraftLeatherSack") return true;
        if (recipeName == "DeCraftWaterskin") return true;
        if (recipeName == "DeCraftFishNetTrap") return true;
        if (recipeName == "DeCraftSnareTrap") return true;
        if (recipeName == "DeCraftTripWire") return true;
        return false;
    }

    static bool NeedsConditionCap(string recipeName)
    {
        if (recipeName == "CraftLeatherSack") return true;
        if (recipeName == "CraftWaterskin") return true;
        if (recipeName == "CraftLeatherBelt") return true;
        if (recipeName == "CraftLeatherHippack") return true;
        if (recipeName == "CraftLeatherSheath") return true;
        if (recipeName == "CraftFoxHeaddress") return true;
        if (recipeName == "DeCraftLeatherSack") return true;
        if (recipeName == "DeCraftWaterskin") return true;
        if (recipeName == "DeCraftWoodenCrate") return true;
        if (recipeName == "DeCraftTruck01DoubleWheel") return true;
        return false;
    }

    static bool NeedsRecoveryState(string recipeName)
    {
        // Native non-food transformations only. Repair/clean/tan/prepare keep
        // their own native semantics (PluginRepairing.c:3,36,106).
        if (HCNativeCraftingSafety.NeedsEmptySource(recipeName) || HCNativeCraftingSafety.NeedsConditionCap(recipeName))
            return true;
        if (recipeName == "CraftBurlapStrips") return true;
        if (recipeName == "CraftRagRope") return true;
        if (recipeName == "CraftGhillieAttachment") return true;
        if (recipeName == "CraftGhillieBushrag") return true;
        if (recipeName == "CraftGhillieHood") return true;
        if (recipeName == "CraftGhillieSuit") return true;
        if (recipeName == "CraftGhillieTop") return true;
        if (recipeName == "DeCraftGhillieAttachment") return true;
        if (recipeName == "DeCraftGhillieBushrag") return true;
        if (recipeName == "DeCraftGhillieHood") return true;
        if (recipeName == "DeCraftGhillieSuit") return true;
        if (recipeName == "DeCraftGhillieTop") return true;
        if (recipeName == "DeCraftCamoNetShelter") return true;
        if (recipeName == "CraftWoodenCrate") return true;
        if (recipeName == "CraftTruck01DoubleWheel") return true;
        if (recipeName == "CraftBaseBallBatNailed") return true;
        if (recipeName == "CraftBaseBallBatBarbed") return true;
        return false;
    }

    static void InheritRecoveryState(ItemBase source, array<ItemBase> results)
    {
        if (!source || !results)
            return;
        // N2, paths relative to the pinned scripts-1.30.164289 snapshot:
        // 3_Game/Entities/Object.c:1001,1008,1015 (health read/cap).
        // 3_Game/Entities/EntityAI.c:812 (deferred deletion).
        // 4_World/Entities/ItemBase.c:3692,3721,3997,4003 (wetness/agent union).
        // Do not transfer generic variables: MiscGameplayFunctions.c:296,319
        // also transfers quantity and energy, which would duplicate state.
        float sourceHealth = source.GetHealth01("", "");
        float sourceWet = source.GetWet();
        int sourceAgents = source.GetAgents();
        for (int resultIndex = 0; resultIndex < results.Count(); resultIndex++)
        {
            ItemBase recovery = results[resultIndex];
            if (!recovery || recovery.IsSetForDeletion())
                continue;
            if (recovery.GetHealth01("", "") > sourceHealth)
                recovery.SetHealth("", "", sourceHealth * recovery.GetMaxHealth("", ""));
            recovery.TransferAgents(sourceAgents);
            if (recovery.GetWet() < sourceWet)
                recovery.SetWet(sourceWet);
        }
    }

    static void DiscardNativeOutputs(array<ItemBase> results)
    {
        if (!results)
            return;
        for (int outputIndex = 0; outputIndex < results.Count(); outputIndex++)
        {
            ItemBase provisional = results[outputIndex];
            if (provisional)
                provisional.Delete();
        }
        results.Clear();
    }

    static void CapNativeRecovery(array<ItemBase> results, float sourceHealth)
    {
        if (!results)
            return;
        for (int resultIndex = 0; resultIndex < results.Count(); resultIndex++)
        {
            ItemBase recovery = results[resultIndex];
            if (recovery && !recovery.IsSetForDeletion() && recovery.GetHealth01("", "") > sourceHealth)
                recovery.SetHealth("", "", sourceHealth * recovery.GetMaxHealth("", ""));
        }
    }
}

modded class RecipeBase
{
    protected ref HCCraftingCommitGuard m_HCNativeCommitGuard = new HCCraftingCommitGuard;
    // 0 unknown, 1 scoped, 2 not scoped. A recipe instance never changes its
    // class name, so the name chain runs once instead of every CheckRecipe.
    protected int m_HCScopedState;

    protected bool HCIsScoped()
    {
        if (m_HCScopedState == 0)
        {
            m_HCScopedState = 2;
            if (HCNativeCraftingSafety.IsScoped(ClassName()))
                m_HCScopedState = 1;
        }
        return m_HCScopedState == 1;
    }

    protected bool HCValidateNativeInputs(ItemBase item1, ItemBase item2, PlayerBase player)
    {
        if (!player || !player.IsAlive() || player.IsUnconscious())
            return false;
        if (!item1 || !item2 || item1 == item2 || item1.IsSetForDeletion() || item2.IsSetForDeletion())
            return false;
        if (!item1.GetInventory() || !item2.GetInventory())
            return false;
        // Native manager already supplies sorted handles. Never move or replace
        // either handle. Grounded double wheels retain their native CanDo rule.
        if (!m_IngredientDestroy[0] && m_IngredientAddQuantity[0] < 0 && !HCNativeCraftingSafety.HasRequiredQuantity(item1, -m_IngredientAddQuantity[0]))
            return false;
        if (!m_IngredientDestroy[1] && m_IngredientAddQuantity[1] < 0 && !HCNativeCraftingSafety.HasRequiredQuantity(item2, -m_IngredientAddQuantity[1]))
            return false;
        if (HCNativeCraftingSafety.NeedsEmptySource(ClassName()))
        {
            if (!item1.IsEmpty() || !item2.IsEmpty())
                return false;
            if (item1.GetInventory().IsAttachment() || item2.GetInventory().IsAttachment())
                return false;
        }
        // N3 4_World/Classes/Recipes/Recipes/DeCraftWaterskin.c:90 checks IsEmpty().
        // N2 EntityAI.c:646 excludes liquid; ItemBase.c:3490 reads its quantity.
        // Refuse rather than silently discard the remaining drink.
        if (ClassName() == "DeCraftWaterskin" && item1.GetQuantity() > 0)
            return false;
        TrapBase trap = TrapBase.Cast(item1);
        if (trap && HCNativeCraftingSafety.NeedsEmptySource(ClassName()) && !trap.IsTakeable())
            return false;
        return true;
    }

    override bool CheckRecipe(ItemBase item1, ItemBase item2, PlayerBase player)
    {
        if (HCIsScoped() && !HCValidateNativeInputs(item1, item2, player))
            return false;
        return super.CheckRecipe(item1, item2, player);
    }

    override void ApplyModificationsResults(ItemBase sorted[], array<ItemBase> results, ItemBase result, PlayerBase player)
    {
        // N3 RecipeBase.c:268,373,532: properties before ingredient mutation.
        // Retain native ragQuantity/yields, colours and custom Do. Only consumed
        // inputs contribute: worn cutting tools never improve recovered health.
        super.ApplyModificationsResults(sorted, results, result, player);
        // Recipes outside the recovery set keep native results unchanged.
        if (HCNativeCraftingSafety.NeedsRecoveryState(ClassName()))
        {
            for (int ingredientIndex = 0; ingredientIndex < MAX_NUMBER_OF_INGREDIENTS; ingredientIndex++)
            {
                if (m_IngredientDestroy[ingredientIndex] || m_IngredientAddQuantity[ingredientIndex] < 0)
                    HCNativeCraftingSafety.InheritRecoveryState(sorted[ingredientIndex], results);
            }
        }
    }

    override void PerformRecipe(ItemBase item1, ItemBase item2, PlayerBase player)
    {
        if (!HCIsScoped())
        {
            super.PerformRecipe(item1, item2, player);
            return;
        }
        if (!GetGame() || !GetGame().IsServer() || !m_HCNativeCommitGuard)
            return;
        if (!m_HCNativeCommitGuard.TryEnter())
            return;
        if (CheckRecipe(item1, item2, player))
        {
            float sourceHealth = item1.GetHealth01("", "");
            array<ItemBase> nativeResults = new array<ItemBase>;
            SpawnItems(m_IngredientsSorted, player, nativeResults);
            bool allocated = nativeResults.Count() == m_NumberOfResults;
            for (int nativeIndex = 0; nativeIndex < nativeResults.Count(); nativeIndex++)
            {
                // N2 EntityAI.c:812: a non-null pending deletion is not output.
                if (!nativeResults[nativeIndex] || nativeResults[nativeIndex].IsSetForDeletion())
                    allocated = false;
            }
            if (allocated)
            {
                ApplyModificationsResults(m_IngredientsSorted, nativeResults, null, player);
                allocated = nativeResults.Count() == m_NumberOfResults;
                // Native result quantity/property mutations can invalidate an
                // allocation. Recheck before the single destructive commit.
                for (int modifiedIndex = 0; modifiedIndex < nativeResults.Count(); modifiedIndex++)
                {
                    if (!nativeResults[modifiedIndex] || nativeResults[modifiedIndex].IsSetForDeletion())
                        allocated = false;
                }
            }
            if (allocated)
            {
                // Keep native order, quantities, custom Do and property transfer.
                ApplyModificationsIngredients(m_IngredientsSorted, player);
                Do(m_IngredientsSorted, player, nativeResults, m_Specialty);
                if (HCNativeCraftingSafety.NeedsConditionCap(ClassName()))
                    HCNativeCraftingSafety.CapNativeRecovery(nativeResults, sourceHealth);
                DeleleIngredientsPass();
            }
            else
            {
                HCNativeCraftingSafety.DiscardNativeOutputs(nativeResults);
            }
        }
        m_HCNativeCommitGuard.Release();
    }
}

// Preserve native durations, wear, colors and all alternatives.
modded class CraftLeatherSack
{
    override void Init()
    {
        super.Init();
        m_MinQuantityIngredient[0] = 2;
        m_MinQuantityIngredient[1] = 10;
    }
}

modded class CraftWaterskin
{
    override void Init()
    {
        super.Init();
        m_MinQuantityIngredient[0] = 2;
        m_MinQuantityIngredient[1] = 10;
    }
}

modded class CraftWoodenHook
{
    override void Init()
    {
        super.Init();
        m_MinQuantityIngredient[0] = 1;
    }
}

modded class DeCraftGhillieBushrag
{
    override void Init()
    {
        super.Init();
        m_ResultInheritsHealth[1] = 0;
    }
}

modded class SplitLongWoodenStick
{
    override void Init()
    {
        super.Init();
        // Repair the literal in place: RemoveIngredient leaves animation data.
        // Keep the native sound category, animation command and showItem flag.
        if (!m_Ingredients[1] || !m_AnimationInfos)
            return;
        for (int toolIndex = 0; toolIndex < m_Ingredients[1].Count(); toolIndex++)
        {
            if (m_Ingredients[1][toolIndex] == "Jambiya;")
                m_Ingredients[1][toolIndex] = "Jambiya";
        }
        for (int animationIndex = 0; animationIndex < m_AnimationInfos.Count(); animationIndex++)
        {
            if (m_AnimationInfos[animationIndex] && m_AnimationInfos[animationIndex].m_IngredientName == "Jambiya;")
                m_AnimationInfos[animationIndex].m_IngredientName = "Jambiya";
        }
    }
}
