// #61 extends #35; EXP-A2 remains unverified. Pure, deterministic policy.
// Installed native snapshot: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 1_Core/proto/EnMath.c:427 Math.Floor, :566 Math.Max.
// HC-51 receipt uses 1_Core/proto/EnConvert.c:30 int.ToString, :115 float.ToString.
// No native weather writes here. HCWeatherDaysModule.c documents the sole owner.
// #247 provisional tuning: 1/5 bad days, at most 1/5 fog mornings.
// Day is the bounded in-game calendar key; restarts do not reroll the profile.
class HCWeatherDays
{
    // HC-51: consume ONLY an active HC-6 phase; "unavailable" preserves the
    // previous policy. No engine writes, persistence, clock or second owner.
    static float HCSeasonCloud(string phase, string profile, float elapsed, float hour)
    {
        float baseline = HCWeatherDays.CloudTarget(profile, elapsed, hour);
        bool calm = profile == "calm" || profile == "fog";
        return HCSeasonVisualPolicy.HCCloud(phase, baseline, HCAtmospherePolicy.IsNight(hour), calm);
    }

    static float HCSeasonRain(string phase, string profile, float cloud, float hour)
    {
        float baseline = HCWeatherDays.RainTarget(profile, cloud, hour);
        bool calm = profile == "calm" || profile == "fog";
        return HCSeasonVisualPolicy.HCRain(phase, baseline, cloud, HCAtmospherePolicy.IsNight(hour), calm);
    }

    static float HCSeasonFog(string phase, int day, float hour, float calmHours)
    {
        // #247: seasonal floors must not reintroduce daily/all-day fog. The
        // weather owner applies observed cloud/wind suppression to this target.
        return HCWeatherDays.FogTarget(day, hour, calmHours);
    }

    static float HCSeasonSnow(string phase, string profile, float cloud, float hour)
    {
        bool calm = profile == "calm" || profile == "fog";
        return HCSeasonVisualPolicy.HCSnowfall(phase, cloud, HCAtmospherePolicy.IsNight(hour), calm);
    }

    // Weather owner calls only on observed owner/phase changes, supplying GetActual snow
    // rather than claiming a target was rendered. count=1 is an admitted phase,
    // not a native weather/terrain success receipt. HC-50 reports its own refusal.
    static string HCSeasonLine(string phase, float observedSnowfall, bool writerAdmitted)
    {
        string state = "off";
        string reason = "HC6_NOT_ADMITTED";
        int admitted = 0;
        if (!writerAdmitted)
        {
            state = "refused";
            reason = "WEATHER_OWNER_NOT_ADMITTED";
            phase = "unavailable";
        }
        else
        {
            if (HCSeasonVisualPolicy.HCValidPhase(phase))
            {
                state = "on";
                reason = "phase_forecast";
                admitted = 1;
            }
            else { phase = "unavailable"; }
        }
        float snowfall = HCSeasonVisualPolicy.HCUnit(observedSnowfall);
        string line = "[HC Plan] HC-51 phase=" + phase + " snowfall=" + snowfall.ToString() + " extra_thermal=0 writer=weather_days";
        line = line + " state=" + state + " reason=" + reason + " count=" + admitted.ToString();
        return line + " native_survival=stock runtime=PENDING";
    }

    static int Seed(int day)
    {
        if (day < 0 || day > 24855) return -1;
        // Bounded integer hash; no random stream, overflow or restart dependence.
        // Review P3: mix the day before bucketing so profiles do not cycle every
        // five days. Each product stays below 2^31 for days up to 24855.
        int mixed = (day * 7919 + 104729) % 9973;
        mixed = (mixed * mixed + day * 31) % 9973;
        return mixed;
    }

    static bool IsFogDay(int day)
    {
        int seed = HCWeatherDays.Seed(day);
        if (seed < 0) { return false; }
        int bucket = seed % 5;
        return bucket >= HCWeatherConfig.HCGet().BadDayBuckets && bucket < HCWeatherConfig.HCGet().FogMorningBuckets;
    }

    static string Profile(int day, float hour, float calmHours)
    {
        int seed = HCWeatherDays.Seed(day);
        if (seed < 0 || !HCAtmospherePolicy.Finite(hour) || hour < 0 || hour >= 24) return "plain";
        if (calmHours > 0) return "calm";
        if (HCAtmospherePolicy.IsNight(hour)) return "plain";
        if (seed % 5 < HCWeatherConfig.HCGet().BadDayBuckets) return "bad";
        if (hour >= HCWeatherConfig.HCGet().FogStartHour && hour < HCWeatherConfig.HCGet().FogEndHour && HCWeatherDays.IsFogDay(day)) return "fog";
        return "plain";
    }

    static float FogTarget(int day, float hour, float calmHours)
    {
        if (HCWeatherDays.Profile(day, hour, calmHours) != "fog") return HCWeatherConfig.HCGet().FogBaseline;
        float baseline = HCWeatherConfig.HCGet().FogBaseline;
        float peak = Math.Max(baseline, HCWeatherConfig.HCGet().FogMorningLevel);
        return baseline + (peak - baseline) * HCAtmospherePolicy.MorningWeight(hour);
    }

    static float CloudTarget(string profile, float elapsed, float hour)
    {
        // Selected fog weather calls for an overcast, calm morning, not clear haze.
        if (profile == "fog") return HCWeatherConfig.HCGet().WetCloud;
        if (profile == "calm") return HCWeatherConfig.HCGet().CalmCloud;
        float phase = HCAtmospherePolicy.CyclePosition(elapsed);
        // Double the storm band on bad days, while retaining a clearing interval.
        if (profile == "bad" && phase >= HCWeatherConfig.HCGet().BadStormStartSeconds && phase < HCWeatherConfig.HCGet().StormEndSeconds)
            return HCAtmospherePolicy.NightCapped(HCWeatherConfig.HCGet().BadCloud, hour);
        return HCAtmospherePolicy.CloudTarget(elapsed, hour);
    }

    static float RainTarget(string profile, float cloud, float hour)
    {
        if (profile == "calm" || profile == "fog" || HCAtmospherePolicy.IsNight(hour)) return 0;
        if (profile == "bad" && cloud >= HCWeatherConfig.HCGet().StormCloudThreshold) return HCWeatherConfig.HCGet().BadRain;
        return HCAtmospherePolicy.RainTarget(cloud);
    }

    static float WindTarget(string profile, float cloud, float hour)
    {
        if (profile == "calm" || profile == "fog") return HCWeatherConfig.HCGet().CalmWind;
        if (HCAtmospherePolicy.IsNight(hour)) return HCWeatherConfig.HCGet().NightWind;
        if (profile == "bad" && cloud >= HCWeatherConfig.HCGet().BadWindCloudThreshold) return HCWeatherConfig.HCGet().BadWind;
        return HCAtmospherePolicy.WindTarget(cloud);
    }

    static float CalmRemaining(float remaining, float gameHours, bool wasWet, float rain, float cloud)
    {
        // Require observed rain/storm ending, never the planned forecast alone.
        if (wasWet && rain <= HCWeatherConfig.HCGet().WetEndRainThreshold && cloud < HCWeatherConfig.HCGet().StormCloudThreshold) return HCWeatherConfig.HCGet().CalmHours;
        if (!HCAtmospherePolicy.Finite(gameHours) || gameHours < 0 || gameHours >= 24) return 0;
        if (remaining <= gameHours) return 0;
        return remaining - gameHours;
    }
}
