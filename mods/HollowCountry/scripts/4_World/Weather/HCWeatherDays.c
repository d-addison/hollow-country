// #61 extends #35; EXP-A2 remains unverified. Pure, deterministic policy.
// Installed native snapshot: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 1_Core/proto/EnMath.c:427 Math.Floor (via HCAtmospherePolicy.CyclePosition).
// No native weather writes here. HCWeatherDaysModule.c documents the sole owner.
// Provisional tuning: 1/5 bad days, 2/5 fog mornings, three IN-GAME hours of calm.
// Day is the UTC epoch day from HCGroupClock, independent of accelerated world date.
class HCWeatherDays
{
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

    static string Profile(int day, float hour, float calmHours)
    {
        int seed = HCWeatherDays.Seed(day);
        if (seed < 0 || !HCAtmospherePolicy.Finite(hour) || hour < 0 || hour >= 24) return "plain";
        if (calmHours > 0) return "calm";
        if (HCAtmospherePolicy.IsNight(hour)) return "plain";
        if (seed % 5 == 0) return "bad";
        if (hour >= 5 && hour < 9 && seed % 5 <= 2) return "fog";
        return "plain";
    }

    static float FogTarget(int day, float hour, float calmHours)
    {
        if (HCWeatherDays.Profile(day, hour, calmHours) != "fog") return 0.04;
        if (hour <= 7) return 0.60;
        return 0.04 + 0.56 * (9 - hour) / 2;
    }

    static float CloudTarget(string profile, float elapsed, float hour)
    {
        if (profile == "calm" || profile == "fog") return 0.25;
        float phase = HCAtmospherePolicy.CyclePosition(elapsed);
        // Double the storm band on bad days, while retaining a clearing interval.
        if (profile == "bad" && phase >= 1800 && phase < 5400)
            return HCAtmospherePolicy.NightCapped(0.98, hour);
        return HCAtmospherePolicy.CloudTarget(elapsed, hour);
    }

    static float RainTarget(string profile, float cloud, float hour)
    {
        if (profile == "calm" || profile == "fog" || HCAtmospherePolicy.IsNight(hour)) return 0;
        if (profile == "bad" && cloud >= 0.85) return 0.9;
        return HCAtmospherePolicy.RainTarget(cloud);
    }

    static float WindTarget(string profile, float cloud, float hour)
    {
        if (profile == "calm" || profile == "fog") return 2;
        if (HCAtmospherePolicy.IsNight(hour)) return 4;
        if (profile == "bad" && cloud >= 0.65) return 16;
        return HCAtmospherePolicy.WindTarget(cloud);
    }

    static float CalmRemaining(float remaining, float gameHours, bool wasWet, float rain, float cloud)
    {
        // Require observed rain/storm ending, never the planned forecast alone.
        if (wasWet && rain <= 0.02 && cloud < 0.85) return 3;
        if (!HCAtmospherePolicy.Finite(gameHours) || gameHours < 0 || gameHours >= 24) return 0;
        if (remaining <= gameHours) return 0;
        return remaining - gameHours;
    }
}
