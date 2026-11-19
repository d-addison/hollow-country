// #213: publish operator/data/dependency observations through the shared hook.
// Native pending verdicts alone do not refuse the admitted source lifecycle.
modded class HCInfectedVarietyModule
{
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCOperationalStatus observed = super.HCGetOperationalStatus();
        if (!m_Running) { return observed; }
        string fault = HCInfectedVariety.HCFault();
        if (fault == "infected_variety_disabled" || fault == "operator_preference")
        {
            observed.HCPublish("off", fault);
        }
        else if (m_Variety && fault != "") { observed.HCPublish("degraded", fault); }
        else if (m_Variety && !HCInfectedModule.Instance)
        {
            observed.HCPublish("degraded", "infected_owner_unavailable");
        }
        else if (m_Variety && HCInfectedVarietyRoutes.HCFault() != "")
        {
            observed.HCPublish("degraded", HCInfectedVarietyRoutes.HCFault());
        }
        else { HCRefreshVarietyStatus(); }
        return observed;
    }
}
