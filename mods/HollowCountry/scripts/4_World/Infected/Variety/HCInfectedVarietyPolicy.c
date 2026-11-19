// W5 #121 / #125: scalar policy only, no engine observations.
// Native math: scripts-1.30.164289/1_Core/proto/EnMath.c:413 Round,
// :427 Floor, :540 Clamp, :553 Min, :566 Max. Limits remain provisional.
class HCInfectedVarietyPolicy
{
    // Hold for a non-calm (aggro'd) native crawler before the next rest roll.
    // lod.json VarietyNonCalmHoldSeconds; the default equals the shipped 600 s
    // failed-roll cooldown (ZombieBase.HC_VARIETY_RETRY_SECONDS), so behaviour is
    // unchanged until an operator edits it. Provisional until measured.
    static const float DEFAULT_NONCALM_HOLD_SECONDS = 600;
    static const float MIN_NONCALM_HOLD_SECONDS = 30;
    static const float MAX_NONCALM_HOLD_SECONDS = 3600;

    // A native zero-fill (missing key) is below the minimum, so it never validates.
    static bool ValidNonCalmHold(float seconds)
    {
        return seconds >= MIN_NONCALM_HOLD_SECONDS && seconds <= MAX_NONCALM_HOLD_SECONDS;
    }

    // Zero-based group ordinal; named config cadence 0 disables standing only.
    static bool HCStandingFresh(int ordinal, int every)
    {
        return every > 0 && ordinal >= 0 && (ordinal + 1) % every == 0;
    }

    // Source context chooses the role; the existing runner cap remains authoritative.
    static int HCContextRole(string context, bool runnerRoom)
    {
        if (context == "roadside" && runnerRoom) { return 2; }
        if (context == "roadside" || context == "wreck") { return 0; }
        return 1;
    }

    static bool HCShouldWakeDormant(bool overCap, bool nativeAlert)
    {
        return overCap || nativeAlert;
    }

    static float GroupScale(int players)
    {
        if (players <= 1) { return HCInfectedTuning.Variety().GroupScaling.Solo; }
        if (players < 3) { return HCInfectedTuning.Variety().GroupScaling.Solo + HCInfectedTuning.Variety().GroupScaling.DuoIncrement * (players - 1); }
        if (players < 6) { return HCInfectedTuning.Variety().GroupScaling.Trio + HCInfectedTuning.Variety().GroupScaling.PartyIncrement * (players - 3); }
        return HCInfectedTuning.Variety().GroupScaling.LargeParty;
    }

    static int DormantLimit(float scale)
    {
        return DormantLimitAt(scale, 12);
    }

    // #135 tiered posed budget (lod.json PosedBudget, ship default 12 until
    // measured). Budget 12 gives exactly the shipped Min(12, Round(8 * scale)).
    static int DormantLimitAt(float scale, int budget)
    {
        if (budget < 1) { return 0; }
        return Math.Min(budget, Math.Max(0, Math.Round(scale * budget * HCInfectedTuning.Variety().Variety.DormantShare)));
    }

    // Per-tier posed sub-budgets: near players (full AI tier) or middle range.
    static bool PosedRoom(bool nearPlayers, int fullPosed, int idlePosed, int fullBudget, int idleBudget)
    {
        if (!HCPostureAdmission.HCCanEnter("native_crawler_idle")) { return false; }
        if (nearPlayers) { return fullPosed < fullBudget; }
        return idlePosed < idleBudget;
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
        float share = HCInfectedTuning.Variety().Variety.RunnerDay + HCInfectedTuning.Variety().Variety.RunnerNightIncrement * Math.Clamp(nightness, 0, 1);
        return Math.Floor(Math.Max(0, population) * share);
    }

    static float DormantChance(float nightness, float rain)
    {
        return Math.Clamp(HCInfectedTuning.Variety().Variety.DormantBase - HCInfectedTuning.Variety().Variety.DormantNightReduction * nightness - HCInfectedTuning.Variety().Variety.DormantRainReduction * rain, HCInfectedTuning.Variety().Variety.DormantMin, HCInfectedTuning.Variety().Variety.DormantMax);
    }

    static float NoiseWakeChance(float nightness, float rain)
    {
        return Math.Clamp(HCInfectedTuning.Variety().Variety.WakeBase + HCInfectedTuning.Variety().Variety.WakeNightIncrement * nightness - HCInfectedTuning.Variety().Variety.WakeRainReduction * rain, HCInfectedTuning.Variety().Variety.WakeMin, HCInfectedTuning.Variety().Variety.WakeMax);
    }

    // Native ZombieBase.c:96-99 samples [0,4); no custom graph/idle values.
    // Walker/shambler/runner use 0/1/3, the existing military policy retains 2.
    static int HCStanceForRole(int role, bool military)
    {
        if (military) { return 2; }
        if (role == 2) { return 3; }
        if (role == 1) { return 1; }
        return 0;
    }

    static float MovementLimit(int role, float nativeSpeed)
    {
        if (nativeSpeed <= 0) { return nativeSpeed; }
        if (role == 0) { return Math.Min(nativeSpeed, 1); }
        if (role == 1) { return Math.Min(nativeSpeed, 2); }
        return Math.Min(nativeSpeed, 3);
    }
}
