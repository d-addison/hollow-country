// HC-51 / #150: authored presentation defaults, runtime acceptance pending.
// HC-6 supplies the phase, HCWeatherDaysModule remains the SOLE weather writer.
// These normalized values are provisional visual tuning, not survival modifiers.
// No calendar, temperature, clothing, wetness, loot or terrain writes. Native
// snowfall's STOCK environment effects remain (Environment.c:889-938, 1742).
// HC-50 alone admits white terrain; falling snow never qualifies that track.
// No new distances. Snowflake scale stays at the native/operator value: Weather.c
// :328 is explicitly unsynchronized; no extra scale owner is needed here.
class HCSeasonVisualPolicy
{
    static const int VERSION = 1;
    static const float SNAPSHOT_TTL_SECONDS = 90;
    static const float SNAPSHOT_HEARTBEAT_SECONDS = 30;
    static const float SUMMER_RAIN_SCALE = 0.5;
    static const float AUTUMN_RAIN_MIN = 0.45;
    static const float AUTUMN_FOG_MIN = 0.18;
    static const float WINTER_FOG_MIN = 0.08;
    static const float AUTUMN_CLOUD_MIN = 0.75;
    static const float WINTER_CLOUD_MIN = 0.80;
    // Same 0.6 lower threshold documented by native Weather.c:309; retain the
    // native 1 upper threshold and 30-second stopping time at lead integration.
    static const float SNOW_CLOUD_THRESHOLD = 0.6;
    static const float WINTER_SNOWFALL = 0.55;
    static const float SPRING_GRADE = 0.06;
    static const float SUMMER_GRADE = 0.04;
    static const float AUTUMN_GRADE = 0.14;
    static const float WINTER_GRADE = 0.12;

    static bool HCValidPhase(string phase)
    {
        return phase == "spring" || phase == "summer" || phase == "autumn" || phase == "winter";
    }

    static string HCPhaseName(int phaseCode)
    {
        if (phaseCode == 0) { return "spring"; }
        if (phaseCode == 1) { return "summer"; }
        if (phaseCode == 2) { return "autumn"; }
        if (phaseCode == 3) { return "winter"; }
        return "unavailable";
    }

    static float HCUnit(float value)
    {
        if (!(value >= 0) || !(value <= 1)) { return 0; }
        return value;
    }

    static float HCCloud(string phase, float baseline, bool night, bool calm)
    {
        float result = HCUnit(baseline);
        if (night || calm) { return result; }
        if (phase == "autumn" && result < AUTUMN_CLOUD_MIN) { return AUTUMN_CLOUD_MIN; }
        if (phase == "winter" && result < WINTER_CLOUD_MIN) { return WINTER_CLOUD_MIN; }
        return result;
    }

    static float HCRain(string phase, float baseline, float cloud, bool night, bool calm)
    {
        float result = HCUnit(baseline);
        if (!HCValidPhase(phase)) { return result; }
        if (phase == "winter" || night || calm) { return 0; }
        if (phase == "summer") { return result * SUMMER_RAIN_SCALE; }
        if (phase == "autumn" && cloud >= 0.65 && cloud <= 1 && result < AUTUMN_RAIN_MIN) { return AUTUMN_RAIN_MIN; }
        return result;
    }

    static float HCFog(string phase, float baseline, bool night, bool calm)
    {
        float result = HCUnit(baseline);
        if (night || calm) { return result; }
        if (phase == "autumn" && result < AUTUMN_FOG_MIN) { return AUTUMN_FOG_MIN; }
        if (phase == "winter" && result < WINTER_FOG_MIN) { return WINTER_FOG_MIN; }
        return result;
    }

    static float HCSnowfall(string phase, float cloud, bool night, bool calm)
    {
        if (phase != "winter" || night || calm) { return 0; }
        if (!(cloud >= SNOW_CLOUD_THRESHOLD) || !(cloud <= 1)) { return 0; }
        return WINTER_SNOWFALL;
    }

    static string HCGradeName(string phase)
    {
        if (phase == "spring" || phase == "summer" || phase == "autumn") { return "dusk_warm"; }
        if (phase == "winter") { return "dusk_cold"; }
        return "vanilla";
    }

    static float HCGradeWeight(string phase)
    {
        if (phase == "spring") { return SPRING_GRADE; }
        if (phase == "summer") { return SUMMER_GRADE; }
        if (phase == "autumn") { return AUTUMN_GRADE; }
        if (phase == "winter") { return WINTER_GRADE; }
        return 0;
    }
}
