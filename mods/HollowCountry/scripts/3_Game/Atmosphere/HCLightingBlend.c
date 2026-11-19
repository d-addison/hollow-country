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
        if (HCLightingBlend.Daylight(hour) <= 0) { return "vanilla"; }
        return HCSeasonVisualPolicy.HCGradeName(phase);
    }

    static float HCSeasonWeight(string phase, float hour)
    {
        return HCLightingBlend.Daylight(hour) * HCSeasonVisualPolicy.HCGradeWeight(phase);
    }

    static float Unit(float value)
    {
        if (value != value || value < 0) return 0;
        if (value > 1) return 1;
        return value;
    }

    static float Daylight(float hour)
    {
        // Invalid time fails to vanilla. Fade at both edges of the weather
        // owner's night interval, never carry a darkening blend into night.
        if (hour != hour || hour <= 5 || hour >= 20) return 0;
        if (hour < 6) return hour - 5;
        if (hour > 19) return 20 - hour;
        return 1;
    }

    static float Dusk(float hour)
    {
        // A four-hour authored warm-to-cold envelope, rather than a short
        // sunset flash. Two user tables are switched only at zero weight.
        if (hour != hour || hour <= 16 || hour >= 20) return 0;
        if (hour < 18) return (hour - 16) / 2;
        return (20 - hour) / 2;
    }

    static float Cloud(float overcast, float fog)
    {
        return HCLightingBlend.Unit((HCLightingBlend.Unit(overcast) - 0.55) / 0.45 + HCLightingBlend.Unit(fog) * 0.15);
    }

    static float Storm(float overcast, float rain)
    {
        return HCLightingBlend.Unit((HCLightingBlend.Unit(overcast) - 0.65) / 0.35) * HCLightingBlend.Unit(rain);
    }

    static string Name(float hour, float overcast, float rain, float fog)
    {
        if (HCLightingBlend.Daylight(hour) <= 0) return "vanilla";
        if (HCLightingBlend.Storm(overcast, rain) > 0.15) return "storm";
        if (HCLightingBlend.Cloud(overcast, fog) > 0.25) return "overcast";
        if (HCLightingBlend.Dusk(hour) <= 0) return "vanilla";
        if (hour < 18.5) return "dusk_warm";
        return "dusk_cold";
    }

    static float Weight(float hour, float overcast, float rain, float fog)
    {
        string name = HCLightingBlend.Name(hour, overcast, rain, fog);
        float daylight = HCLightingBlend.Daylight(hour);
        if (name == "storm") return daylight * (0.12 + HCLightingBlend.Storm(overcast, rain) * 0.38);
        if (name == "overcast") return daylight * HCLightingBlend.Cloud(overcast, fog) * 0.35;
        if (name == "dusk_warm" || name == "dusk_cold") return daylight * HCLightingBlend.Dusk(hour) * 0.30;
        return 0;
    }

    static float Step(float current, float target, float daylight)
    {
        // Hard night clamp bypasses smoothing, including a stale storm value.
        if (daylight <= 0) return 0;
        float boundedCurrent = HCLightingBlend.Unit(current);
        float boundedTarget = HCLightingBlend.Unit(target);
        if (boundedCurrent < boundedTarget - 0.10) return boundedCurrent + 0.10;
        if (boundedCurrent > boundedTarget + 0.10) return boundedCurrent - 0.10;
        return boundedTarget;
    }
}
