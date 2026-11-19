// HC-2 / #150: meal warmth is retired, including legacy EnableMealBuffs=true.
// No consumption/environment/player hooks, thermal state, tick work or saves.
// Native scripts-1.30.164289 inspected (native behavior remains unqualified):
// 4_World/Entities/ItemBase/Edible_Base.c:95-109 native consumption/heat damage;
// 4_World/Classes/Environment/Environment.c:1253,1329 native heat comfort;
// 4_World/Classes/StaminaHandler.c:614-628 native rate/event cost separation,
// :656-671 native weight cap. HCStaminaConfiguration remains the single owner.
// Native APIs called here: 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnConvert.c:115 float.ToString.
// HCServer starts modules on the server; this is a bounded startup receipt only.
class HCSurvivalAlignmentModule : HCModule
{
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "SurvivalAlignment"; }
    override bool IsEnabled(HCSettings settings) { return true; }

    // Wave 16: cached readiness from the live started flag (the stamina scale receipt was logged).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", "", "stamina_alignment_receipt_logged");
        return m_Operational;
    }

    override void OnStop() { m_Started = false; }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("SurvivalAlignment", true, "HC-2", false));
        float drain = HCStaminaIntegration.ExertionScale();
        float recovery = HCStaminaIntegration.RecoveryScale();
        string stamina = "off";
        if (HCStaminaIntegration.Enabled()) { stamina = "on"; }
        Print("[HC Plan] HC-2 stamina_drain=" + drain.ToString() + " recovery=" + recovery.ToString() + " stamina=" + stamina + " meal_heat=off hooks=0 runtime=PENDING");
        m_Started = true;
    }
}

// Temporary compatibility name keeps the worker-owned registration unchanged.
// Lead replaces its registration with HCSurvivalAlignmentModule at integration.
class HCMealBuffsModule : HCSurvivalAlignmentModule
{
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCMealBuffsModule);
    }
}
