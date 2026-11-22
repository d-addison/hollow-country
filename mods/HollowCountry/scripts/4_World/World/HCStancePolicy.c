// LC-T404/T405 / EXP-L3: pure observable policy. No native API, identity or standing.
// Synthetic smoke is not native acceptance. Warning duration is body-local.
class HCStancePolicy
{
    static const int WATCH = 0;
    static const int WARN = 1;

    static int Evaluate(bool weaponRaised, float distance, bool recentGunfire, int relation)
    {
        // Lowering always de-escalates, including a hostile faction encounter.
        if (!weaponRaised) { return HCStancePolicy.WATCH; }
        if (distance != distance || distance < 0 || distance > 100) { return HCStancePolicy.WATCH; }
        // Ranges are cached once from AILimits at settings load (defaults 30/60/80 m).
        float cautionRange = HCAILimits.CAUTION_RANGE;
        if (relation < 0) { cautionRange = HCAILimits.CAUTION_HOSTILE_RANGE; }
        if (recentGunfire) { cautionRange = HCAILimits.CAUTION_GUNFIRE_RANGE; }
        if (distance <= cautionRange) { return HCStancePolicy.WARN; }
        return HCStancePolicy.WATCH;
    }
    // HC-5: authoritative observed facts only. Gesture identity/serial come from
    // executed native callbacks, never a client claim or pending generic emote.
    static bool ReplyWave(bool server, bool observed, bool neutral, bool raised, bool grudge, int serial, int consumed, int nowMs, int nextMs)
    {
        return server && observed && neutral && !raised && !grudge && serial > 0 && serial > consumed && nowMs >= 0 && nowMs >= nextMs;
    }

    static bool CeaseForSurrender(bool server, bool observed, bool surrendered)
    {
        return server && observed && surrendered;
    }

    static bool WarningDue(int nowMs, int nextMs)
    {
        return nowMs >= 0 && nowMs >= nextMs;
    }
}
