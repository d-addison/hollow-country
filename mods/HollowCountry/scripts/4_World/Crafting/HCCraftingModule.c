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
    override string GetName() { return "Crafting"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableCrafting; }

    override void OnStart(HCSettings settings)
    {
        HCCraftingGate.m_Started = false;
        HCCraftingGate.m_Validated = false;
        if (!GetGame() || !GetGame().IsServer() || !IsEnabled(settings))
            return;
        HCCraftingGate.m_Validated = HCCraftingNativeChecks.Run();
        HCCraftingGate.m_Started = HCCraftingGate.m_Validated;
        if (!HCCraftingGate.m_Validated)
            Print("[HollowCountry] Crafting native definition/config checks FAILED; salvage disabled");
        else
            Print("[HollowCountry] Crafting definition/config checks passed; runtime acceptance PENDING");
    }

    // Action-driven only: no world/inventory scans, timers, RPC or custom persistence.
    override void OnStop()
    {
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
