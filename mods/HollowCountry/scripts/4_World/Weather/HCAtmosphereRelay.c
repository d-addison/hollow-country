// Native: 3_Game/Global/Game.c:738 GetNoiseSystem;
// 3_Game/Noise.c:13 GetEnvironmentNoiseReduction(vector pos).
// Snapshot: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/.
// A source-position sample affects only the supplementary relay radius.
class HCAtmosphereRelay
{
    protected static bool s_NoiseReported;

    static float RangeAtSource(float baseRadius, vector sourcePosition)
    {
        if (!HCAtmosphereQualification.Enabled())
            return baseRadius;
        NoiseSystem relayNoise = GetGame().GetNoiseSystem();
        if (!relayNoise)
        {
            if (!s_NoiseReported)
            {
                s_NoiseReported = true;
                Print("[HollowCountry][Atmosphere] noise system unavailable; vanilla relay radius retained");
            }
            return baseRadius;
        }
        float reduction = relayNoise.GetEnvironmentNoiseReduction(sourcePosition);
        return HCAtmospherePolicy.RelayRange(baseRadius, reduction);
    }
}
