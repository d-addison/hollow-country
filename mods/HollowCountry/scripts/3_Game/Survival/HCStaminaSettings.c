// Settings DTO; HCStaminaConfiguration owns trusted profile/session admission.
class HCStaminaSettings
{
    int SchemaVersion = 1;
    bool Enabled = true;
    float ContinuousExertionScale = 0.5;
    float RecoveryScale = 1.25;

    bool Validate()
    {
        return (SchemaVersion == 1 && ContinuousExertionScale >= 0.05 && ContinuousExertionScale <= 5.0 && RecoveryScale >= 0.05 && RecoveryScale <= 5.0);
    }
}
