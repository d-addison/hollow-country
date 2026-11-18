// W5 #121 / #125: scalar policy only, no engine observations.
// Native math: scripts-1.30.164289/1_Core/proto/EnMath.c:413 Round,
// :427 Floor, :540 Clamp, :553 Min, :566 Max. Limits remain provisional.
class HCInfectedVarietyPolicy
{
    static float GroupScale(int players)
    {
        if (players <= 1) { return 0.6; }
        if (players < 3) { return 0.6 + 0.2 * (players - 1); }
        if (players < 6) { return 1.0 + 0.1 * (players - 3); }
        return 1.3;
    }

    static int DormantLimit(float scale)
    {
        return Math.Min(12, Math.Max(0, Math.Round(8 * scale)));
    }

    // Existing native-pack journal requires at least three members. Never
    // split/refill a live pack when the online roster changes; future adoption only.
    static int CohortLimit(int requested, int available, float scale)
    {
        int desired = Math.Max(3, Math.Round(requested * scale));
        return Math.Min(available, Math.Min(6, desired));
    }

    static int RunnerLimit(int population, float nightness)
    {
        float share = 0.08 + 0.07 * Math.Clamp(nightness, 0, 1);
        return Math.Floor(Math.Max(0, population) * share);
    }

    static float DormantChance(float nightness, float rain)
    {
        return Math.Clamp(0.55 - 0.25 * nightness - 0.15 * rain, 0.1, 0.6);
    }

    static float NoiseWakeChance(float nightness, float rain)
    {
        return Math.Clamp(0.8 + 0.2 * nightness - 0.3 * rain, 0.4, 1);
    }

    static float MovementLimit(int role, float nativeSpeed)
    {
        if (nativeSpeed <= 0) { return nativeSpeed; }
        if (role == 0) { return Math.Min(nativeSpeed, 1); }
        if (role == 1) { return Math.Min(nativeSpeed, 2); }
        return Math.Min(nativeSpeed, 3);
    }
}
