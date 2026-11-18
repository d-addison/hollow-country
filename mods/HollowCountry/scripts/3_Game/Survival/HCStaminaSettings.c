// Settings DTO; HCStaminaConfiguration owns trusted profile/session admission.
class HCStaminaSettings
{
    int SchemaVersion = 1;
    bool Enabled = true;
    float ContinuousExertionScale = 0.25;
    float RecoveryScale = 2.5;
    float WeightPenaltyScale = 0.5;

    bool Validate()
    {
        return (SchemaVersion == 1 && ContinuousExertionScale >= 0.05 && ContinuousExertionScale <= 5.0 && RecoveryScale >= 0.05 && RecoveryScale <= 5.0 && WeightPenaltyScale >= 0.0 && WeightPenaltyScale <= 1.0);
    }
}
