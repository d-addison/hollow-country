class HCCraftingGate
{
    static bool m_Started;
    static bool m_Validated;
    static int m_Crafted;

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

    // Action-driven only: no world/inventory scans, timers, RPC or custom persistence.
    override void OnStop()
    {
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
