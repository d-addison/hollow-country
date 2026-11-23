class HCCraftingGate
{
    static bool m_Started;
    static bool m_Validated;
    static int m_Crafted;
    protected static ref HCActivityCounters s_Activity;
    static HCActivityCounters HCActivity()
    {
        if (!s_Activity) s_Activity = new HCActivityCounters("attempts completed refused HCSalvageCamoNet HCSalvageCableReel HCRecoverLargeLeather HCRecoverMediumLeather HCRecoverBatWood HCRecoverNailedBat HCRecoverBarbedBat HCRecoverRuinedCrate HCRecoverRuinedLargeLeather HCRecoverRuinedBatWood HCRecoverRuinedNailedBat HCRecoverTeddyRag HCRecoverFabricRag HCAuditLeatherPantsBeige HCAuditLeatherPantsBlack HCAuditLeatherPantsBrown HCAuditLeatherPantsNatural HCAuditLeatherVestBeige HCAuditLeatherVestBlack HCAuditLeatherVestBrown HCAuditLeatherVestNatural", "[HollowCountry] Crafting");
        return s_Activity;
    }

    static bool CanPreviewOrCraft()
    {
        if (!GetGame())
            return false;
        if (!GetGame().IsServer())
            return true;
        // A later module may abort startup before the core admits any actions.
        if (!HCServer.Get().IsStarted())
            return false;
        HCSettings settings = HCServer.Get().GetSettings();
        return m_Started && m_Validated && settings && settings.EnableCrafting;
    }

    static void RecordCraft()
    {
        if (m_Crafted < 2147483647)
            m_Crafted++;
            HCModuleReadiness.HCUse("Crafting", "recipe_completed");
    }
}

class HCCraftingModule extends HCModule
{
    protected string m_Refusal;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "Crafting"; }

    // Wave 16: ready only when the definition/config checks passed (HCCraftingGate.m_Started).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, HCCraftingGate.m_Started, m_Refusal, "", "definition_checks_passed");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings)
    {
        bool enabled = settings && settings.EnableCrafting;
        // Core reads admission once and skips OnStart for a disabled module.
        if (!enabled)
            HCCommonRecoveryPolicy.HCReport(false, false);
        return enabled;
    }

    override void OnStart(HCSettings settings)
    {
        HCCraftingGate.HCActivity();
        HCFuelSiphon.HCActivity();
        HCCraftingGate.m_Started = false;
        HCCraftingGate.m_Validated = false;
        m_Refusal = "";
        if (!GetGame() || !GetGame().IsServer() || !settings || !settings.EnableCrafting)
        {
            HCCommonRecoveryPolicy.HCReport(false, false);
            return;
        }
        HCCraftingGate.m_Validated = HCCraftingNativeChecks.Run() && HCCommonRecoveryPolicy.HCValidateRegistered();
        HCCraftingGate.m_Started = HCCraftingGate.m_Validated;
        HCActionSiphonFuel.ProductionStart(HCCraftingGate.m_Validated);
        HCCommonRecoveryPolicy.HCReport(true, HCCraftingGate.m_Validated);
        HCReached.Mark("crafting.definitions_checked");
        if (!HCCraftingGate.m_Validated)
        {
            m_Refusal = "native_definition_checks_failed";
            Print("[HollowCountry] Crafting native definition/config checks FAILED; salvage disabled");
        }
        else
            Print("[HollowCountry] Crafting definition/config checks passed; runtime acceptance PENDING");
    }

    // Tick emits only bounded telemetry; no world/inventory scans or timers.
    override void OnTick(float deltaTime)
    {
        HCCraftingGate.HCActivity().Report();
        HCFuelSiphon.HCActivity().Report();
    }

    override void OnStop()
    {
        HCCraftingGate.HCActivity().Report("", true);
        HCFuelSiphon.HCActivity().Report("", true);
        HCActionSiphonFuel.ProductionStop();
        HCCraftingGate.m_Started = false;
        HCCraftingGate.m_Validated = false;
        Print("[HollowCountry] Crafting stopped; completed recipes=" + HCCraftingGate.m_Crafted.ToString());
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCCraftingModule);
    }
}

// Keep native recipe transaction ordering and count only the server commit path.
modded class HCSalvageRecipe
{
    override void PerformRecipe(ItemBase item1, ItemBase item2, PlayerBase player)
    {
        if (!GetGame().IsServer()) { super.PerformRecipe(item1, item2, player); return; }
        HCCraftingGate.HCActivity().Add("attempts");
        int before = HCCraftingGate.m_Crafted;
        super.PerformRecipe(item1, item2, player);
        if (HCCraftingGate.m_Crafted == before) HCCraftingGate.HCActivity().Add("refused");
    }

    override void Do(ItemBase ingredients[], PlayerBase player, array<ItemBase> results, float specialty_weight)
    {
        bool ready = m_HCOutputReady;
        super.Do(ingredients, player, results, specialty_weight);
        if (!GetGame().IsServer() || !ready) return;
        HCCraftingGate.HCActivity().Add("completed");
        HCCraftingGate.HCActivity().Add(ClassName());
    }
}
