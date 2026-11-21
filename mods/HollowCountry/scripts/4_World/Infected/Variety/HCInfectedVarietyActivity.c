// #316 activity variation. Scalar helpers only: the policy owner supplies the
// existing shared time/rain sample and a stable pack/place key, never position
// refreshed each tick. No census, timer, sampler or retained pack map.
// Native 1_Core/proto/EnString.c:223 Hash; EnMath.c:540 Clamp.
class HCInfectedVarietyActivity
{
    static bool HCEnabled()
    {
        return HCInfectedTuning.Variety().Variety.EnableActivityVariation;
    }

    static void HCStart()
    {
        int enabled;
        if (HCEnabled()) { enabled = 1; }
        Print("[HC Variety] activity_variation enabled=" + enabled.ToString() + " routes=authored bias=pack_key policy_hook=PENDING runtime=PENDING");
    }

    // Modulo before negation avoids signed minimum overflow. Empty keys retain
    // the existing odds; callers must not collapse ungrouped actors to one key.
    static float HCBias(string packKey)
    {
        if (!HCEnabled() || packKey == "") { return 0; }
        int bucket = packKey.Hash() % 2001;
        if (bucket < 0) { bucket = -bucket; }
        return (bucket - 1000) / 1000.0;
    }

    // +/- 0.08 dormant and +/- 0.02 runner probability, bounded by existing
    // tuning and caps at the caller. Never promote or wake an actor here.
    static float HCDormantChance(string packKey, float nightness, float rain)
    {
        HCC1Variety tuning = HCInfectedTuning.Variety().Variety;
        float chance = HCInfectedVarietyPolicy.DormantChance(nightness, rain);
        if (!HCEnabled()) { return chance; }
        return Math.Clamp(chance + HCBias(packKey) * 0.08, tuning.DormantMin, tuning.DormantMax);
    }

    static float HCRunnerChance(string packKey, float nightness)
    {
        HCC1Variety tuning = HCInfectedTuning.Variety().Variety;
        float chance = tuning.RunnerDay + tuning.RunnerNightIncrement * Math.Clamp(nightness, 0, 1);
        if (!HCEnabled()) { return Math.Clamp(chance, 0, 1); }
        return Math.Clamp(chance - HCBias(packKey) * 0.02, 0, 1);
    }
}

modded class HCInfectedVarietyConfig
{
    override void HCApplyTuningDefaults(string content)
    {
        super.HCApplyTuningDefaults(content);
        // JsonFileLoader may zero-fill a missing bool inside an existing block.
        // Explicit false survives for authored data and profile overrides alike.
        if (!HCJsonFields.Has(content, "EnableActivityVariation")) { Variety.EnableActivityVariation = true; }
    }
}
