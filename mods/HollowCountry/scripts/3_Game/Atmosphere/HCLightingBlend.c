// LC-T104 / LC-ATM-04, EXP-A2. Pure authored scalar policy; no engine calls.
// Read-only coordination: HCAtmospherePolicy.IsNight uses 20:00..05:00.
// The client also uses native World.IsNight for seasonal sunset/dawn safety.
// Native delivery is isolated in 5_Mission/Atmosphere/HCLightingClient.c.
class HCLightingBlend
{
    // HC-51 reuses closed authored tables through the SAME client owner. No
    // seasonal overlay at night; existing weather grades retain precedence.
    static string HCSeasonName(string phase, float hour)
    {
        if (HCLightingBlend.Daylight(hour) <= 0.0) { return "vanilla"; }
        return HCSeasonVisualPolicy.HCGradeName(phase);
    }

    static float HCSeasonWeight(string phase, float hour)
    {
        return HCLightingBlend.Daylight(hour) * HCSeasonVisualPolicy.HCGradeWeight(phase);
    }

    static float Unit(float value)
    {
        if (value != value || value < 0.0) return 0.0;
        if (value > 1.0) return 1.0;
        return value;
    }

    static float Daylight(float hour)
    {
        // Invalid time fails to vanilla. Fade at both edges of the weather
        // owner's night interval, never carry a darkening blend into night.
        if (hour != hour || hour <= HCc2PresentationConfig.HCGet().LightDawnStart || hour >= HCc2PresentationConfig.HCGet().LightDuskEnd) return 0.0;
        if (hour < HCc2PresentationConfig.HCGet().LightDawnEnd) return (hour - HCc2PresentationConfig.HCGet().LightDawnStart) / (HCc2PresentationConfig.HCGet().LightDawnEnd - HCc2PresentationConfig.HCGet().LightDawnStart);
        if (hour > HCc2PresentationConfig.HCGet().LightDuskStart) return (HCc2PresentationConfig.HCGet().LightDuskEnd - hour) / (HCc2PresentationConfig.HCGet().LightDuskEnd - HCc2PresentationConfig.HCGet().LightDuskStart);
        return 1.0;
    }

    static float Dusk(float hour)
    {
        // A four-hour authored warm-to-cold envelope, rather than a short
        // sunset flash. Two user tables are switched only at zero weight.
        if (hour != hour || hour <= HCc2PresentationConfig.HCGet().DuskStart || hour >= HCc2PresentationConfig.HCGet().DuskEnd) return 0.0;
        if (hour < HCc2PresentationConfig.HCGet().DuskPeak) return (hour - HCc2PresentationConfig.HCGet().DuskStart) / (HCc2PresentationConfig.HCGet().DuskPeak - HCc2PresentationConfig.HCGet().DuskStart);
        return (HCc2PresentationConfig.HCGet().DuskEnd - hour) / (HCc2PresentationConfig.HCGet().DuskEnd - HCc2PresentationConfig.HCGet().DuskPeak);
    }

    static float Cloud(float overcast, float fog)
    {
        return HCLightingBlend.Unit((HCLightingBlend.Unit(overcast) - HCc2PresentationConfig.HCGet().CloudThreshold) / (1.0 - HCc2PresentationConfig.HCGet().CloudThreshold) + HCLightingBlend.Unit(fog) * HCc2PresentationConfig.HCGet().FogCloudWeight);
    }

    static float Storm(float overcast, float rain)
    {
        return HCLightingBlend.Unit((HCLightingBlend.Unit(overcast) - HCc2PresentationConfig.HCGet().StormThreshold) / (1.0 - HCc2PresentationConfig.HCGet().StormThreshold)) * HCLightingBlend.Unit(rain);
    }

    static string Name(float hour, float overcast, float rain, float fog)
    {
        if (HCLightingBlend.Daylight(hour) <= 0.0) return "vanilla";
        if (HCLightingBlend.Storm(overcast, rain) > HCc2PresentationConfig.HCGet().StormBand) return "storm";
        if (HCLightingBlend.Cloud(overcast, fog) > HCc2PresentationConfig.HCGet().CloudBand) return "overcast";
        if (HCLightingBlend.Dusk(hour) <= 0.0) return "vanilla";
        if (hour < HCc2PresentationConfig.HCGet().DuskColdHour) return "dusk_warm";
        return "dusk_cold";
    }

    static float Weight(float hour, float overcast, float rain, float fog)
    {
        string name = HCLightingBlend.Name(hour, overcast, rain, fog);
        float daylight = HCLightingBlend.Daylight(hour);
        if (name == "storm") return daylight * (HCc2PresentationConfig.HCGet().StormWeightBase + HCLightingBlend.Storm(overcast, rain) * HCc2PresentationConfig.HCGet().StormWeightGain);
        if (name == "overcast") return daylight * HCLightingBlend.Cloud(overcast, fog) * HCc2PresentationConfig.HCGet().CloudWeight;
        if (name == "dusk_warm" || name == "dusk_cold") return daylight * HCLightingBlend.Dusk(hour) * HCc2PresentationConfig.HCGet().DuskWeight;
        return 0.0;
    }

    static float Step(float current, float target, float daylight)
    {
        // Hard night clamp bypasses smoothing, including a stale storm value.
        if (daylight <= 0.0) return 0.0;
        float boundedCurrent = HCLightingBlend.Unit(current);
        float boundedTarget = HCLightingBlend.Unit(target);
        if (boundedCurrent < boundedTarget - HCc2PresentationConfig.HCGet().BlendStep) return boundedCurrent + HCc2PresentationConfig.HCGet().BlendStep;
        if (boundedCurrent > boundedTarget + HCc2PresentationConfig.HCGet().BlendStep) return boundedCurrent - HCc2PresentationConfig.HCGet().BlendStep;
        return boundedTarget;
    }
}
