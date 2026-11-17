// Native: 3_Game/Global/Game.c:738 GetNoiseSystem;
// 3_Game/Noise.c:13 GetEnvironmentNoiseReduction(vector pos).
// Snapshot: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/.
// A source-position sample affects only the supplementary relay radius.
class HCAtmosphereRelay
{
    static float RangeAtSource(float baseRadius, vector sourcePosition)
    {
        if (!HCAtmosphereQualification.Enabled())
            return baseRadius;
        NoiseSystem relayNoise = GetGame().GetNoiseSystem();
        if (!relayNoise)
            return baseRadius * 0.35;
        float reduction = relayNoise.GetEnvironmentNoiseReduction(sourcePosition);
        return HCAtmospherePolicy.RelayRange(baseRadius, reduction);
    }
}
