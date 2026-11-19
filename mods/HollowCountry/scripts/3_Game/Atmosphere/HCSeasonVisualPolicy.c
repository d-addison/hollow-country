// HC-51 / #150: authored presentation defaults, runtime acceptance pending.
// HC-6 supplies the phase, HCWeatherDaysModule remains the SOLE weather writer.
// These normalized values are provisional visual tuning, not survival modifiers.
// No calendar, temperature, clothing, loot or terrain writes. Native snow
// keeps stock wetness effects (Environment.c:889-938, 1742).
// HC-50 alone admits white terrain; falling snow never qualifies that track.
// No new distances. Snowflake scale stays at the native/operator value: Weather.c
// :328 is explicitly unsynchronized; no extra scale owner is needed here.
class HCSeasonVisualPolicy
{
    static const int VERSION = 1;
    static float SNAPSHOT_TTL_SECONDS = 90.0;
    static float SNAPSHOT_HEARTBEAT_SECONDS = 30.0;
    static float FOG_BLEND_HOURS = 0.5;
    static float BASELINE_FOG = 0.04;
    static float SUMMER_RAIN_SCALE = 0.5;
    static float AUTUMN_RAIN_MIN = 0.45;
    static float AUTUMN_FOG_MIN = 0.18;
    static float WINTER_FOG_MIN = 0.08;
    static float AUTUMN_CLOUD_MIN = 0.75;
    static float WINTER_CLOUD_MIN = 0.80;
    // Same 0.6 lower threshold documented by native Weather.c:309; retain the
    // native 1 upper threshold and 30-second stopping time in the existing weather owner.
    static float SNOW_CLOUD_THRESHOLD = 0.6;
    static float WINTER_SNOWFALL = 0.55;
    static float SPRING_GRADE = 0.06;
    static float SUMMER_GRADE = 0.04;
    static float AUTUMN_GRADE = 0.14;
    static float WINTER_GRADE = 0.12;

    static void HCConfigure(HCc2SeasonTuning config)
    {
        HCc2SeasonTuning.HCSet(config);
        HCSeasonVisualPolicy.SNAPSHOT_TTL_SECONDS = config.SNAPSHOT_TTL_SECONDS;
        HCSeasonVisualPolicy.SNAPSHOT_HEARTBEAT_SECONDS = config.SNAPSHOT_HEARTBEAT_SECONDS;
        HCSeasonVisualPolicy.FOG_BLEND_HOURS = config.FOG_BLEND_HOURS;
        HCSeasonVisualPolicy.BASELINE_FOG = config.BASELINE_FOG;
        HCSeasonVisualPolicy.SUMMER_RAIN_SCALE = config.SUMMER_RAIN_SCALE;
        HCSeasonVisualPolicy.AUTUMN_RAIN_MIN = config.AUTUMN_RAIN_MIN;
        HCSeasonVisualPolicy.AUTUMN_FOG_MIN = config.AUTUMN_FOG_MIN;
        HCSeasonVisualPolicy.WINTER_FOG_MIN = config.WINTER_FOG_MIN;
        HCSeasonVisualPolicy.AUTUMN_CLOUD_MIN = config.AUTUMN_CLOUD_MIN;
        HCSeasonVisualPolicy.WINTER_CLOUD_MIN = config.WINTER_CLOUD_MIN;
        HCSeasonVisualPolicy.SNOW_CLOUD_THRESHOLD = config.SNOW_CLOUD_THRESHOLD;
        HCSeasonVisualPolicy.WINTER_SNOWFALL = config.WINTER_SNOWFALL;
        HCSeasonVisualPolicy.SPRING_GRADE = config.SPRING_GRADE;
        HCSeasonVisualPolicy.SUMMER_GRADE = config.SUMMER_GRADE;
        HCSeasonVisualPolicy.AUTUMN_GRADE = config.AUTUMN_GRADE;
        HCSeasonVisualPolicy.WINTER_GRADE = config.WINTER_GRADE;
    }

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
        if (!(value >= 0.0) || !(value <= 1.0)) { return 0.0; }
        return value;
    }

    static float HCCloud(string phase, float baseline, bool night, bool calm)
    {
        float result = HCUnit(baseline);
        if (night || calm) { return result; }
        if (phase == "autumn" && result < HCc2SeasonTuning.HCGet().AUTUMN_CLOUD_MIN) { return HCc2SeasonTuning.HCGet().AUTUMN_CLOUD_MIN; }
        if (phase == "winter" && result < HCc2SeasonTuning.HCGet().WINTER_CLOUD_MIN) { return HCc2SeasonTuning.HCGet().WINTER_CLOUD_MIN; }
        return result;
    }

    static float HCRain(string phase, float baseline, float cloud, bool night, bool calm)
    {
        float result = HCUnit(baseline);
        if (!HCValidPhase(phase)) { return result; }
        if (phase == "winter" || night || calm) { return 0.0; }
        if (phase == "summer") { return result * HCc2SeasonTuning.HCGet().SUMMER_RAIN_SCALE; }
        if (phase == "autumn" && cloud >= HCc2SeasonTuning.HCGet().AutumnRainCloudThreshold && cloud <= 1.0 && result < HCc2SeasonTuning.HCGet().AUTUMN_RAIN_MIN) { return HCc2SeasonTuning.HCGet().AUTUMN_RAIN_MIN; }
        return result;
    }

    static float HCFog(string phase, float baseline, bool night, bool calm)
    {
        float result = HCUnit(baseline);
        if (night || calm) { return result; }
        if (phase == "autumn" && result < HCc2SeasonTuning.HCGet().AUTUMN_FOG_MIN) { return HCc2SeasonTuning.HCGet().AUTUMN_FOG_MIN; }
        if (phase == "winter" && result < HCc2SeasonTuning.HCGet().WINTER_FOG_MIN) { return HCc2SeasonTuning.HCGet().WINTER_FOG_MIN; }
        return result;
    }

    // Fade inside the daylight interval; never add seasonal fog at night.
    static float HCFogDaylight(float hour)
    {
        if (!(hour > HCc2SeasonTuning.HCGet().FogDayStartHour) || !(hour < HCc2SeasonTuning.HCGet().FogDayEndHour)) { return 0.0; }
        if (hour < HCc2SeasonTuning.HCGet().FogDayStartHour + HCc2SeasonTuning.HCGet().FOG_BLEND_HOURS) { return (hour - HCc2SeasonTuning.HCGet().FogDayStartHour) / HCc2SeasonTuning.HCGet().FOG_BLEND_HOURS; }
        if (hour > HCc2SeasonTuning.HCGet().FogDayEndHour - HCc2SeasonTuning.HCGet().FOG_BLEND_HOURS) { return (HCc2SeasonTuning.HCGet().FogDayEndHour - hour) / HCc2SeasonTuning.HCGet().FOG_BLEND_HOURS; }
        return 1.0;
    }

    static float HCSnowfall(string phase, float cloud, bool night, bool calm)
    {
        if (phase != "winter" || night || calm) { return 0.0; }
        if (!(cloud >= HCc2SeasonTuning.HCGet().SNOW_CLOUD_THRESHOLD) || !(cloud <= 1.0)) { return 0.0; }
        return HCc2SeasonTuning.HCGet().WINTER_SNOWFALL;
    }

    static string HCGradeName(string phase)
    {
        if (phase == "spring" || phase == "summer" || phase == "autumn") { return "dusk_warm"; }
        if (phase == "winter") { return "dusk_cold"; }
        return "vanilla";
    }

    static float HCGradeWeight(string phase)
    {
        if (phase == "spring") { return HCc2SeasonTuning.HCGet().SPRING_GRADE; }
        if (phase == "summer") { return HCc2SeasonTuning.HCGet().SUMMER_GRADE; }
        if (phase == "autumn") { return HCc2SeasonTuning.HCGet().AUTUMN_GRADE; }
        if (phase == "winter") { return HCc2SeasonTuning.HCGet().WINTER_GRADE; }
        return 0.0;
    }
}
