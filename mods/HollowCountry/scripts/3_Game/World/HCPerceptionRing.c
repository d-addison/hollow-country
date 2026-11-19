// W68 shared spawn/event perception policy. No engine perception claims.
// Existing EnableEncounters / acceptance/pve_patrols.disable remain opt-outs.
// Native Print: scripts-1.30.164289/1_Core/proto/EnDebug.c:96.
// Native float.ToString: scripts-1.30.164289/1_Core/proto/EnConvert.c:115.
class HCPerceptionRing
{
    float ViewRangeMeters = 1000;
    float HearingRangeMeters = 1000;
    float SpawnMarginMeters = 100;
    float SpawnBandMeters = 400;
    protected static ref HCPerceptionRing s_Config;
    protected static bool s_Printed;

    static HCPerceptionRing HCGet()
    {
        if (!s_Config) { s_Config = new HCPerceptionRing; }
        return s_Config;
    }

    static float HCValue(string key, float value)
    {
        string registryKey = "PerceptionRing." + key;
        if (value == 0) { return HCOperatorSettingsRegistry.HCDefault(registryKey); }
        if (HCOperatorSettingsRegistry.HCValid(registryKey, value)) { return value; }
        return HCOperatorSettingsRegistry.HCDefault(registryKey);
    }

    void HCValidate()
    {
        ViewRangeMeters = HCPerceptionRing.HCValue("ViewRangeMeters", ViewRangeMeters);
        HearingRangeMeters = HCPerceptionRing.HCValue("HearingRangeMeters", HearingRangeMeters);
        SpawnMarginMeters = HCPerceptionRing.HCValue("SpawnMarginMeters", SpawnMarginMeters);
        SpawnBandMeters = HCPerceptionRing.HCValue("SpawnBandMeters", SpawnBandMeters);
    }

    static void HCUse(HCPerceptionRing config)
    {
        HCPerceptionRing effective = config;
        if (!effective) { effective = new HCPerceptionRing; }
        effective.HCValidate();
        s_Config = effective;
        if (s_Printed) { return; }
        s_Printed = true;
        float minimum = HCPerceptionRing.HCSpawnMin();
        float maximum = HCPerceptionRing.HCSpawnMax();
        Print("[HC PerceptionRing] admitted unverified spawn_min=" + minimum.ToString() + " spawn_max=" + maximum.ToString() + " runtime=PENDING");
    }

    static float HCSeenRange() { return HCPerceptionRing.HCGet().ViewRangeMeters; }
    static float HCHeardRange() { return HCPerceptionRing.HCGet().HearingRangeMeters; }
    static float HCSpawnMin()
    {
        float range = HCPerceptionRing.HCSeenRange();
        float hearing = HCPerceptionRing.HCHeardRange();
        if (hearing > range) { range = hearing; }
        return range + HCPerceptionRing.HCGet().SpawnMarginMeters;
    }
    static float HCSpawnMax()
    {
        return HCPerceptionRing.HCSpawnMin() + HCPerceptionRing.HCGet().SpawnBandMeters;
    }
    // Authored/scaled site radius is a lower bound; it cannot narrow the ring.
    // Ceiling is derived from validated component maxima, never a hidden tune.
    static float HCCeiling()
    {
        float ceiling = HCOperatorSettingsRegistry.HCMaximum("PerceptionRing.ViewRangeMeters");
        float hearingCeiling = HCOperatorSettingsRegistry.HCMaximum("PerceptionRing.HearingRangeMeters");
        if (hearingCeiling > ceiling) { ceiling = hearingCeiling; }
        ceiling += HCOperatorSettingsRegistry.HCMaximum("PerceptionRing.SpawnMarginMeters");
        ceiling += HCOperatorSettingsRegistry.HCMaximum("PerceptionRing.SpawnBandMeters");
        return ceiling;
    }
    static float HCClampActivation(float radius)
    {
        float ceiling = HCPerceptionRing.HCCeiling();
        if (!(radius >= HCPerceptionRing.HCSpawnMax())) { return HCPerceptionRing.HCSpawnMax(); }
        if (radius > ceiling) { return ceiling; }
        return radius;
    }
    static bool HCOutside(float nearest)
    {
        return nearest >= HCPerceptionRing.HCSpawnMin();
    }
}

// Owned additive settings seam: keep the shared HCSettings source outside the
// generated registry untouched. Missing JSON object -> null -> constructor;
// missing/zero scalar -> validated registry default (all minima are positive).
modded class HCSettings
{
    ref HCPerceptionRing PerceptionRing = new HCPerceptionRing;
    override bool Validate(out string error)
    {
        if (!super.Validate(error)) { return false; }
        if (!PerceptionRing) { PerceptionRing = new HCPerceptionRing; }
        HCPerceptionRing.HCUse(PerceptionRing);
        return true;
    }
}
