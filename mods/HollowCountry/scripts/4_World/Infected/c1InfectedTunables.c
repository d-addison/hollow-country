// c1 config migration: scalar DTOs, no native gameplay calls. Defaults retain
// shipped behaviour. Positive ranges distinguish JsonFileLoader zero-fill.
// Print: native 1_Core/proto/EnDebug.c:96. All runtime verdicts remain pending.
class HCC1Range
{
    static bool s_Invalid;
    // First refused value and its bounds, for the one-time boot log line.
    static string s_Detail;
    static float Value(float value, float minimum, float maximum, float fallback)
    {
        if (value >= minimum && value <= maximum) { return value; }
        if (!s_Invalid) { s_Detail = value.ToString() + " outside " + minimum.ToString() + ".." + maximum.ToString() + " default=" + fallback.ToString(); }
        s_Invalid = true;
        return fallback;
    }
}

class HCC1Doors
{
    int OpenMinSeconds = 6;
    int OpenMaxSeconds = 10;
    int HitsMin = 4;
    int HitsMax = 6;
    float HitInterval = 1.5;
    float Grace = 3.0;
    float MaxStep = 2.0;
    float Cooldown = 45.0;
    float WatchSeconds = 10.0;
    float WatchRadius = 8.0;
    float NearRadius = 2.5;
    float DoorRadius = 2.0;

    void Normalize()
    {
        OpenMinSeconds = HCC1Range.Value(OpenMinSeconds, 1, 60, 6);
        OpenMaxSeconds = HCC1Range.Value(OpenMaxSeconds, 1, 120, 10);
        HitsMin = HCC1Range.Value(HitsMin, 1, 20, 4);
        HitsMax = HCC1Range.Value(HitsMax, 1, 30, 6);
        HitInterval = HCC1Range.Value(HitInterval, 0.1, 30, 1.5);
        Grace = HCC1Range.Value(Grace, 0.1, 30, 3.0);
        MaxStep = HCC1Range.Value(MaxStep, 0.1, 10, 2.0);
        Cooldown = HCC1Range.Value(Cooldown, 1, 600, 45.0);
        WatchSeconds = HCC1Range.Value(WatchSeconds, 1, 120, 10.0);
        WatchRadius = HCC1Range.Value(WatchRadius, 1, 30, 8.0);
        NearRadius = HCC1Range.Value(NearRadius, 0.1, 8, 2.5);
        DoorRadius = HCC1Range.Value(DoorRadius, 0.1, 8, 2.0);
        if (OpenMinSeconds > OpenMaxSeconds)
        {
            OpenMinSeconds = 6;
            OpenMaxSeconds = 10;
            HCC1Range.s_Invalid = true;
        }
        if (HitsMin > HitsMax)
        {
            HitsMin = 4;
            HitsMax = 6;
            HCC1Range.s_Invalid = true;
        }
        if (NearRadius >= WatchRadius)
        {
            NearRadius = 2.5;
            WatchRadius = 8.0;
            HCC1Range.s_Invalid = true;
        }
    }
}

class HCC1Reach
{
    float ElevatedMin = 0.8;
    float ElevatedMax = 2.3;
    float VaultMin = 0.8;
    float VaultMax = 2.0;
    float VaultLow = 1.1;
    float VaultHigh = 1.6;
    int VaultConcurrent = 4;
    float VaultCooldown = 15.0;
    float UnreachableQuietSeconds = 6.0;
    float VaultHorizontal = 1.6;
    float VaultFacing = 25.0;

    void Normalize()
    {
        ElevatedMin = HCC1Range.Value(ElevatedMin, 0.1, 2.3, 0.8);
        ElevatedMax = HCC1Range.Value(ElevatedMax, 0.1, 2.3, 2.3);
        VaultMin = HCC1Range.Value(VaultMin, 0.1, 2, 0.8);
        VaultMax = HCC1Range.Value(VaultMax, 0.1, 2, 2.0);
        VaultLow = HCC1Range.Value(VaultLow, 0.1, 2, 1.1);
        VaultHigh = HCC1Range.Value(VaultHigh, 0.1, 2, 1.6);
        VaultConcurrent = HCC1Range.Value(VaultConcurrent, 1, 4, 4);
        VaultCooldown = HCC1Range.Value(VaultCooldown, 1, 60, 15.0);
        UnreachableQuietSeconds = HCC1Range.Value(UnreachableQuietSeconds, 1, 60, 6.0);
        VaultHorizontal = HCC1Range.Value(VaultHorizontal, 0.1, 1.6, 1.6);
        VaultFacing = HCC1Range.Value(VaultFacing, 1, 90, 25.0);
        if (ElevatedMin >= ElevatedMax)
        {
            ElevatedMin = 0.8;
            ElevatedMax = 2.3;
            HCC1Range.s_Invalid = true;
        }
        // Resolve the quartet as one unit: partial repairs can invert an
        // already-checked neighbour after a later pair falls back.
        if (!(VaultMin < VaultLow && VaultLow < VaultHigh && VaultHigh < VaultMax))
        {
            VaultMin = 0.8;
            VaultLow = 1.1;
            VaultHigh = 1.6;
            VaultMax = 2.0;
            HCC1Range.s_Invalid = true;
        }
    }
}

class HCC1Vision
{
    float FactorMin = 0.6;
    float FactorMax = 1.3;
    float DarkFactor = 0.75;
    float LightDay = 1.1;
    float LightNight = 1.5;
    float LightNightIncrement = 0.4;
    float DuskStart = 19.0;
    float NightStart = 21.0;
    float DawnStart = 5.0;
    float DawnEnd = 7.0;

    void Normalize()
    {
        FactorMin = HCC1Range.Value(FactorMin, 0.1, 1, 0.6);
        FactorMax = HCC1Range.Value(FactorMax, 1, 3, 1.3);
        DarkFactor = HCC1Range.Value(DarkFactor, 0.1, 1, 0.75);
        LightDay = HCC1Range.Value(LightDay, 1, 3, 1.1);
        LightNight = HCC1Range.Value(LightNight, 1, 3, 1.5);
        LightNightIncrement = HCC1Range.Value(LightNightIncrement, 0.001, 2, 0.4);
        DuskStart = HCC1Range.Value(DuskStart, 12, 22, 19.0);
        NightStart = HCC1Range.Value(NightStart, 12, 23, 21.0);
        DawnStart = HCC1Range.Value(DawnStart, 0.1, 10, 5.0);
        DawnEnd = HCC1Range.Value(DawnEnd, 0.1, 12, 7.0);
        if (DuskStart >= NightStart)
        {
            DuskStart = 19.0;
            NightStart = 21.0;
            HCC1Range.s_Invalid = true;
        }
        if (DawnStart >= DawnEnd)
        {
            DawnStart = 5.0;
            DawnEnd = 7.0;
            HCC1Range.s_Invalid = true;
        }
    }
}

class HCC1Memory
{
    float DecaySeconds = 259200.0;
    int CohortBase = 30;
    int CohortHeat = 10;
    int ResponseBase = 6;
    int ResponseHeat = 6;
    float CellMetres = 500.0;
    float LoudnessGain = 0.35;
    float SuppressedLoudness = 0.15;

    void Normalize()
    {
        DecaySeconds = HCC1Range.Value(DecaySeconds, 1, 2592000, 259200.0);
        CohortBase = HCC1Range.Value(CohortBase, 30, HCHordeLimits.MAX_PACK, 30);
        CohortHeat = HCC1Range.Value(CohortHeat, 0, HCHordeLimits.MAX_PACK - 30, 10);
        ResponseBase = HCC1Range.Value(ResponseBase, 1, 12, 6);
        ResponseHeat = HCC1Range.Value(ResponseHeat, 1, 6, 6);
        CellMetres = HCC1Range.Value(CellMetres, 50, 2000, 500.0);
        LoudnessGain = HCC1Range.Value(LoudnessGain, 0.001, 1, 0.35);
        SuppressedLoudness = HCC1Range.Value(SuppressedLoudness, 0.001, 1, 0.15);
    }
}

class HCC1Chain
{
    float ClueTTL = 30.0;
    float MinStrength = 0.2;
    int MaxHops = 2;
    float Attenuation = 0.5;
    float EmissionAge = 2.0;
    int TrackedCap = 256;
    int RootCap = 8;

    void Normalize()
    {
        ClueTTL = HCC1Range.Value(ClueTTL, 1, 30, 30.0);
        MinStrength = HCC1Range.Value(MinStrength, 0.001, 1, 0.2);
        MaxHops = HCC1Range.Value(MaxHops, 1, 2, 2);
        Attenuation = HCC1Range.Value(Attenuation, 0.001, 1, 0.5);
        EmissionAge = HCC1Range.Value(EmissionAge, 0.1, 10, 2.0);
        TrackedCap = HCC1Range.Value(TrackedCap, 1, 256, 256);
        RootCap = HCC1Range.Value(RootCap, 1, 8, 8);
    }
}

class HCC1Navigation
{
    float SampleRadius = 1.5;
    float VerticalTolerance = 1.5;
    float WaypointRadius = 1.5;
    float SearchRing = 24.0;

    void Normalize()
    {
        SampleRadius = HCC1Range.Value(SampleRadius, 0.1, 5, 1.5);
        VerticalTolerance = HCC1Range.Value(VerticalTolerance, 0.1, 5, 1.5);
        WaypointRadius = HCC1Range.Value(WaypointRadius, 0.1, 5, 1.5);
        SearchRing = HCC1Range.Value(SearchRing, 1, 120, 24.0);
    }
}

class HCC1LOD
{
    float ObserverSpeed = 60.0;
    float SampleAge = 3.0;
    float HitQuiet = 120.0;
    int PosedFallback = 12;

    void Normalize()
    {
        ObserverSpeed = HCC1Range.Value(ObserverSpeed, 60, 120, 60.0);
        SampleAge = HCC1Range.Value(SampleAge, 0.1, 3, 3.0);
        HitQuiet = HCC1Range.Value(HitQuiet, 1, 3600, 120.0);
        PosedFallback = HCC1Range.Value(PosedFallback, 1, 24, 12);
    }
}

class HCC1GroupScaling
{
    float Solo = 0.6;
    float DuoIncrement = 0.2;
    float Trio = 1.0;
    float PartyIncrement = 0.1;
    float LargeParty = 1.3;

    void Normalize()
    {
        Solo = HCC1Range.Value(Solo, 0.01, 2, 0.6);
        DuoIncrement = HCC1Range.Value(DuoIncrement, 0.001, 1, 0.2);
        Trio = HCC1Range.Value(Trio, 0.01, 2, 1.0);
        PartyIncrement = HCC1Range.Value(PartyIncrement, 0.001, 1, 0.1);
        LargeParty = HCC1Range.Value(LargeParty, 0.01, 3, 1.3);
    }
}

class HCC1Variety
{
    // #316 composition
    bool EnableComposition = true;
    // #316 individual locomotion
    bool EnableIndividualLocomotion = true;
    // #316 activity variation
    bool EnableActivityVariation = true;

    float DormantShare = 0.6666666666666666;
    float RunnerDay = 0.08;
    float RunnerNightIncrement = 0.07;
    float DormantBase = 0.55;
    float DormantNightReduction = 0.25;
    float DormantRainReduction = 0.15;
    float DormantMin = 0.1;
    float DormantMax = 0.6;
    float WakeBase = 0.8;
    float WakeNightIncrement = 0.2;
    float WakeRainReduction = 0.3;
    float WakeMin = 0.4;
    float WakeMax = 1.0;

    void Normalize()
    {
        DormantShare = HCC1Range.Value(DormantShare, 0.001, 1, 0.6666666666666666);
        RunnerDay = HCC1Range.Value(RunnerDay, 0.001, 1, 0.08);
        RunnerNightIncrement = HCC1Range.Value(RunnerNightIncrement, 0.001, 1, 0.07);
        DormantBase = HCC1Range.Value(DormantBase, 0.001, 1, 0.55);
        DormantNightReduction = HCC1Range.Value(DormantNightReduction, 0.001, 1, 0.25);
        DormantRainReduction = HCC1Range.Value(DormantRainReduction, 0.001, 1, 0.15);
        DormantMin = HCC1Range.Value(DormantMin, 0.001, 1, 0.1);
        DormantMax = HCC1Range.Value(DormantMax, 0.001, 1, 0.6);
        WakeBase = HCC1Range.Value(WakeBase, 0.001, 1, 0.8);
        WakeNightIncrement = HCC1Range.Value(WakeNightIncrement, 0.001, 1, 0.2);
        WakeRainReduction = HCC1Range.Value(WakeRainReduction, 0.001, 1, 0.3);
        WakeMin = HCC1Range.Value(WakeMin, 0.001, 1, 0.4);
        WakeMax = HCC1Range.Value(WakeMax, 0.001, 1, 1.0);
        if (DormantMin >= DormantMax)
        {
            if (!HCC1Range.s_Invalid) { HCC1Range.s_Detail = "DormantMin>=DormantMax"; }
            DormantMin = 0.1;
            DormantMax = 0.6;
            HCC1Range.s_Invalid = true;
        }
        if (WakeMin >= WakeMax)
        {
            if (!HCC1Range.s_Invalid) { HCC1Range.s_Detail = "WakeMin>=WakeMax"; }
            WakeMin = 0.4;
            WakeMax = 1.0;
            HCC1Range.s_Invalid = true;
        }
    }
}

// Published by existing DTO validation after the owner loads its JSON.
// Lazy defaults also cover consumers that start before the infected owner.
class HCInfectedTuning
{
    protected static ref HCInfectedConfig s_Config;
    protected static ref HCInfectedVarietyConfig s_Variety;
    static HCInfectedConfig Get()
    {
        if (!s_Config) { s_Config = new HCInfectedConfig; }
        return s_Config;
    }
    static HCInfectedVarietyConfig Variety()
    {
        if (!s_Variety) { s_Variety = new HCInfectedVarietyConfig; }
        return s_Variety;
    }
    static void Set(HCInfectedConfig config) { s_Config = config; }
    static void SetVariety(HCInfectedVarietyConfig config) { s_Variety = config; }
}
