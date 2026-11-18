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
        float cautionRange = 30;
        if (relation < 0) { cautionRange = 60; }
        if (recentGunfire) { cautionRange = 80; }
        if (distance <= cautionRange) { return HCStancePolicy.WARN; }
        return HCStancePolicy.WATCH;
    }
}
