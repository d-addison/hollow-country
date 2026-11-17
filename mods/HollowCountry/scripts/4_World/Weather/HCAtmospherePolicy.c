// #35 pure policy. Native scalar surface: 1_Core/proto/EnConvert.c:112
// float.MAX; 1_Core/proto/EnMath.c:427 Math.Floor. Installed snapshot:
// ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/.
// These provisional bounds are design choices, not measured visual/acoustic facts.
class HCAtmospherePolicy
{
    static bool Finite(float value)
    {
        return value == value && value <= float.MAX && value >= -float.MAX;
    }

    static float CyclePosition(float elapsed)
    {
        // Avoid huge-clock subtraction/cancellation; normal server uptime only.
        if (!HCAtmospherePolicy.Finite(elapsed) || elapsed < 0 || elapsed > 31536000)
            return 0;
        return elapsed - Math.Floor(elapsed / 7200) * 7200;
    }

    static float CloudTarget(float elapsed, float daytime)
    {
        float phase = HCAtmospherePolicy.CyclePosition(elapsed);
        if (phase >= 3600 && phase < 5400)
            return 0.95;
        if (phase >= 2700 && phase < 3600)
            return 0.72;
        float target = 0.35;
        if (phase >= 5400)
            target = 0.25;
        // Native cloud cover supplies darker nights without client PPE hooks.
        if (HCAtmospherePolicy.Finite(daytime) && daytime >= 0 && daytime < 24 && (daytime < 5 || daytime >= 20))
            target = 0.55;
        return target;
    }

    static float RainTarget(float cloud)
    {
        if (!HCAtmospherePolicy.Finite(cloud) || cloud < 0.65 || cloud > 1)
            return 0;
        if (cloud >= 0.85)
            return 0.85;
        return 0.25;
    }

    static float WindTarget(float cloud)
    {
        if (!HCAtmospherePolicy.Finite(cloud) || cloud < 0 || cloud > 1)
            return 4;
        if (cloud >= 0.85)
            return 14;
        if (cloud >= 0.65)
            return 8;
        return 4;
    }

    static float WindDirectionTarget(float elapsed)
    {
        float phase = HCAtmospherePolicy.CyclePosition(elapsed);
        if (phase >= 3600 && phase < 5400)
            return 0.8;
        return -1.2;
    }

    static float MorningWeight(float daytime)
    {
        if (!HCAtmospherePolicy.Finite(daytime) || daytime <= 5 || daytime >= 9)
            return 0;
        if (daytime <= 7)
            return (daytime - 5) / 2;
        return (9 - daytime) / 2;
    }

    static float FogTarget(float daytime)
    {
        return 0.04 + HCAtmospherePolicy.MorningWeight(daytime) * 0.20;
    }

    static float DistanceDensity(float daytime, float cloud, float windSpeed)
    {
        if (!HCAtmospherePolicy.Finite(cloud) || cloud < 0 || cloud > 1)
            cloud = 0;
        if (!HCAtmospherePolicy.Finite(windSpeed) || windSpeed < 0)
            windSpeed = 16;
        if (windSpeed > 16)
            windSpeed = 16;
        float damping = 1 - windSpeed / 20;
        return (0.015 + 0.04 * HCAtmospherePolicy.MorningWeight(daytime) + 0.01 * cloud) * damping;
    }

    static float HeightBias(float daytime)
    {
        return 50 + 40 * HCAtmospherePolicy.MorningWeight(daytime);
    }

    static float TransitionTime(float requested)
    {
        if (!HCAtmospherePolicy.Finite(requested) || requested < 0)
            return 300;
        if (requested > 900)
            return 900;
        return requested;
    }

    static float RelayScale(float reduction)
    {
        // Noise.c:13 is an ABSOLUTE noise-strength reduction, not a distance
        // multiplier. This monotone mapping is our policy: 1/(1+r), [0.35,1].
        // Missing/nonfinite samples use the shortest allowed range.
        if (!HCAtmospherePolicy.Finite(reduction))
            return 0.35;
        if (reduction < 0)
            reduction = 0;
        if (reduction > 2)
            reduction = 2;
        float scale = 1 / (1 + reduction);
        if (scale < 0.35)
            scale = 0.35;
        return scale;
    }

    static float RelayRange(float baseRadius, float reduction)
    {
        if (!HCAtmospherePolicy.Finite(baseRadius) || baseRadius < 0)
            return 0;
        return baseRadius * HCAtmospherePolicy.RelayScale(reduction);
    }
}
