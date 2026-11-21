// Reference: scripts-1.30.164289. Matching trusted settings required on both peers.
class HCStaminaIntegration
{
    static bool InstallTrusted(HCStaminaSettings settings)
    {
        return HCStaminaConfiguration.InstallTrusted(settings);
    }

    static bool Enabled() { return HCStaminaConfiguration.Enabled(); }
    static float ExertionScale() { return HCStaminaConfiguration.ExertionScale(); }
    static float RecoveryScale() { return HCStaminaConfiguration.RecoveryScale(); }
    static float WeightPenaltyScale() { return HCStaminaConfiguration.WeightPenaltyScale(); }
}

modded class StaminaHandler
{
    protected bool m_HCUseStamina;
    override void RecalculateStaminaCap()
    {
        if (!HCStaminaIntegration.Enabled())
        {
            super.RecalculateStaminaCap();
            return;
        }
        float loss = CfgGameplayHandler.GetStaminaKgToStaminaPercentPenalty() * HCStaminaIntegration.WeightPenaltyScale();
        float capacity = HCStaminaPolicy.CapacityUnits(m_PlayerLoad, CfgGameplayHandler.GetStaminaMax(), CfgGameplayHandler.GetStaminaMinCap(), CfgGameplayHandler.GetStaminaWeightLimitThreshold(), loss);
        if (capacity < 0)
        {
            super.RecalculateStaminaCap();
            return;
        }
        m_StaminaCap = capacity;
        m_StaminaCapSynced = capacity;
    }

    override protected void ProcessStaminaChanges(float deltaT, bool isServerOrSingleplayer)
    {
        if (!HCStaminaIntegration.Enabled())
        {
            super.ProcessStaminaChanges(deltaT, isServerOrSingleplayer);
            return;
        }
        // Pure prediction calculation; actual authority passes unchanged to super.
        bool simulationOwner = isServerOrSingleplayer || (m_Player && m_Player.GetInstanceType() == DayZPlayerInstanceType.INSTANCETYPE_CLIENT);
        float rate = m_StaminaDelta;
        // Validate only; native owns event ordering, final clamp and cap snap.
        float proposed = -1;
        if (simulationOwner && HCStaminaPolicy.Within(m_StaminaDepletion, 0.0, 500.0))
        {
            proposed = HCStaminaPolicy.StepUnits(simulationOwner, true, m_Stamina, m_StaminaCap, deltaT, rate, 0.0, m_StaminaDepletionMultiplier, m_StaminaRecoveryMultiplier, HCStaminaIntegration.ExertionScale(), HCStaminaIntegration.RecoveryScale(), 0.0);
        }
        if (proposed < 0)
        {
            super.ProcessStaminaChanges(deltaT, isServerOrSingleplayer);
            return;
        }
        float savedRate = m_StaminaDelta;
        if (rate < 0)
        {
            m_StaminaDelta = rate * HCStaminaIntegration.ExertionScale();
        }
        else
        {
            m_StaminaDelta = rate * HCStaminaIntegration.RecoveryScale();
        }
        // Native event costs and condition multipliers remain native-owned.
        float useStaminaBefore = m_Stamina;
        super.ProcessStaminaChanges(deltaT, isServerOrSingleplayer);
        m_StaminaDelta = savedRate;
        if (!m_HCUseStamina && m_Stamina != useStaminaBefore)
        {
            m_HCUseStamina = true;
            HCModuleReadiness.HCUse("SurvivalAlignment", "stamina_applied");
        }
    }
}
