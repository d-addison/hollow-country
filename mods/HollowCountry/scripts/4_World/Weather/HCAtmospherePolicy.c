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

    // Native 3_Game/Global/Game.c:931 GetWorld; Global/World.c:28 GetDate.
    // One constant-time read on the existing weather path. A calendar key, not
    // elapsed/UTC time: accelerated days and restarts retain their own selection.
    static int FogDay()
    {
        if (!GetGame() || !GetGame().GetWorld()) { return -1; }
        int year, month, day, hour, minute;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
        if (year < 1 || month < 1 || month > 12 || day < 1 || day > 31) { return -1; }
        // Distinct dates over 64 years; stays inside Seed's bounded integer domain.
        return (year % 64) * 372 + (month - 1) * 31 + day - 1;
    }

    // Native 1_Core/proto/EnMath.c:540 Clamp, :553 Min, :566 Max.
    // Daily eligibility is a pure date hash, never a per-tick random roll.
    // Weather only fades its amplitude: clear (<=0.35) or windy (>=3 m/s) is zero.
    static float FogWeatherWeight(float cloud, float windSpeed)
    {
        if (!HCAtmospherePolicy.Finite(cloud) || !HCAtmospherePolicy.Finite(windSpeed) || windSpeed < 0) { return 0; }
        return Math.Clamp((cloud - 0.35) / 0.30, 0, 1) * Math.Clamp(3 - windSpeed, 0, 1);
    }

    static float FogTarget(float daytime, int day, float cloud, float windSpeed)
    {
        float baseline = HCWeatherConfig.HCGet().FogBaseline;
        if (!HCWeatherDays.IsFogDay(day)) { return baseline; }
        float lift = Math.Min(HCWeatherConfig.HCGet().MorningFogLift, Math.Max(0, HCWeatherConfig.HCGet().FogMorningLevel - baseline));
        return baseline + lift * HCAtmospherePolicy.MorningWeight(daytime) * HCAtmospherePolicy.FogWeatherWeight(cloud, windSpeed);
    }

    static float FogStrength(float fog)
    {
        // Same normalized target drives both volumetric components. No 0.95 floor.
        return Math.Clamp((fog - HCWeatherConfig.HCGet().FogBaseline) / 0.30, 0, 1);
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

    // Volumetric fog writes. Only distance density follows the fog strength.
    // Height density stays in the vanilla 0.8..1 band (ChernarusPlus.c:477,
    // :502, :508); at 0 the fog no longer thins with altitude and fills hilltops.
    static float VolDistanceDensity(float density, float strength)
    {
        return Math.Clamp(Math.Max(HCWeatherConfig.HCGet().DistanceBase, density * strength), 0, 1);
    }

    static float VolHeightDensity(float cloud)
    {
        if (!HCAtmospherePolicy.Finite(cloud) || cloud < 0 || cloud > 1)
            cloud = 0;
        return Math.Lerp(0.9, 1.0, cloud);
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
