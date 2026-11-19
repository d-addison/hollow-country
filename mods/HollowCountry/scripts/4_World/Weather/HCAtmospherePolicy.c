// #35 policy over cached optional weather tuning. Native scalar surface: 1_Core/proto/EnConvert.c:112
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
        return elapsed - Math.Floor(elapsed / HCWeatherConfig.HCGet().CycleSeconds) * HCWeatherConfig.HCGet().CycleSeconds;
    }

    static bool IsNight(float daytime)
    {
        // Dusk to dawn: 20:00 inclusive to 05:00 exclusive. Out-of-range or
        // non-finite hours count as day.
        return HCAtmospherePolicy.Finite(daytime) && daytime >= 0 && daytime < 24 && (daytime < HCWeatherConfig.HCGet().NightEndHour || daytime >= HCWeatherConfig.HCGet().NightStartHour);
    }

    static float NightCloudCap()
    {
        return HCWeatherConfig.HCGet().NightCloudCap;
    }

    static float NightCapped(float cloud, float daytime)
    {
        // Owner rule 2026-11-17: never dark nights. The cap is below the 0.65
        // rain threshold, so Rain/WindTarget map it to dry and calm.
        if (HCAtmospherePolicy.IsNight(daytime) && cloud > HCAtmospherePolicy.NightCloudCap())
            return HCAtmospherePolicy.NightCloudCap();
        return cloud;
    }

    static float CloudTarget(float elapsed, float daytime)
    {
        float phase = HCAtmospherePolicy.CyclePosition(elapsed);
        if (phase >= HCWeatherConfig.HCGet().StormStartSeconds && phase < HCWeatherConfig.HCGet().StormEndSeconds)
            return HCAtmospherePolicy.NightCapped(HCWeatherConfig.HCGet().StormCloud, daytime);
        if (phase >= HCWeatherConfig.HCGet().WetStartSeconds && phase < HCWeatherConfig.HCGet().StormStartSeconds)
            return HCAtmospherePolicy.NightCapped(HCWeatherConfig.HCGet().WetCloud, daytime);
        if (phase >= HCWeatherConfig.HCGet().StormEndSeconds)
            return HCWeatherConfig.HCGet().CalmCloud;
        return HCWeatherConfig.HCGet().PlainCloud;
    }

    static float RainTarget(float cloud)
    {
        if (!HCAtmospherePolicy.Finite(cloud) || cloud < HCWeatherConfig.HCGet().RainCloudThreshold || cloud > 1)
            return 0;
        if (cloud >= HCWeatherConfig.HCGet().StormCloudThreshold)
            return HCWeatherConfig.HCGet().StormRain;
        return HCWeatherConfig.HCGet().WetRain;
    }

    static float WindTarget(float cloud)
    {
        if (!HCAtmospherePolicy.Finite(cloud) || cloud < 0 || cloud > 1)
            return HCWeatherConfig.HCGet().PlainWind;
        if (cloud >= HCWeatherConfig.HCGet().StormCloudThreshold)
            return HCWeatherConfig.HCGet().StormWind;
        if (cloud >= HCWeatherConfig.HCGet().RainCloudThreshold)
            return HCWeatherConfig.HCGet().WetWind;
        return HCWeatherConfig.HCGet().PlainWind;
    }

    static float WindDirectionTarget(float elapsed)
    {
        float phase = HCAtmospherePolicy.CyclePosition(elapsed);
        if (phase >= HCWeatherConfig.HCGet().StormStartSeconds && phase < HCWeatherConfig.HCGet().StormEndSeconds)
            return HCWeatherConfig.HCGet().StormWindDirection;
        return HCWeatherConfig.HCGet().PlainWindDirection;
    }

    static float MorningWeight(float daytime)
    {
        if (!HCAtmospherePolicy.Finite(daytime) || daytime <= HCWeatherConfig.HCGet().FogStartHour || daytime >= HCWeatherConfig.HCGet().FogEndHour)
            return 0;
        if (daytime <= HCWeatherConfig.HCGet().FogPeakHour)
            return (daytime - HCWeatherConfig.HCGet().FogStartHour) / (HCWeatherConfig.HCGet().FogPeakHour - HCWeatherConfig.HCGet().FogStartHour);
        return (HCWeatherConfig.HCGet().FogEndHour - daytime) / (HCWeatherConfig.HCGet().FogEndHour - HCWeatherConfig.HCGet().FogPeakHour);
    }

    static float FogTarget(float daytime)
    {
        return HCWeatherConfig.HCGet().FogBaseline + HCAtmospherePolicy.MorningWeight(daytime) * HCWeatherConfig.HCGet().MorningFogLift;
    }

    static float DistanceDensity(float daytime, float cloud, float windSpeed)
    {
        if (!HCAtmospherePolicy.Finite(cloud) || cloud < 0 || cloud > 1)
            cloud = 0;
        if (!HCAtmospherePolicy.Finite(windSpeed) || windSpeed < 0)
            windSpeed = 16;
        if (windSpeed > 16)
            windSpeed = 16;
        float damping = 1 - windSpeed / HCWeatherConfig.HCGet().WindDampingDivisor;
        return (HCWeatherConfig.HCGet().DistanceBase + HCWeatherConfig.HCGet().DistanceMorningLift * HCAtmospherePolicy.MorningWeight(daytime) + HCWeatherConfig.HCGet().DistanceCloudLift * cloud) * damping;
    }

    static float HeightBias(float daytime)
    {
        return HCWeatherConfig.HCGet().HeightBase + HCWeatherConfig.HCGet().HeightMorningLift * HCAtmospherePolicy.MorningWeight(daytime);
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
