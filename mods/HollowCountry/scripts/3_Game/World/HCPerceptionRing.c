// W68 shared spawn/event perception policy. No engine perception claims.
// Existing EnableEncounters / acceptance/pve_patrols.disable remain opt-outs.
// Native Print: scripts-1.30.164289/1_Core/proto/EnDebug.c:96.
// Native float.ToString: scripts-1.30.164289/1_Core/proto/EnConvert.c:115.
// Search output is a proposal, never permission to create actors. The site owner
// must navmesh/place it and recheck every observer's distance AND visibility.
class HCPerceptionRingPick
{
    vector Position;
    int Attempts;
    string Reason = "spawn_ring_no_safe_land";
}

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
    // maxCandidates is the caller's remaining configured tick-work allowance
    // (HCSettings.MaxTickWorkItems), not a separate hidden search limit. Charge
    // Attempts through the shared work budget. No work when the caller is off.
    // Native snapshot scripts-1.30.164289: 3_Game/gameplay.c:636 GetGame;
    // 3_Game/Global/Game.c:1120 IsServer,
    // :1176 SurfaceY, :1196 SurfaceIsSea, :1197 SurfaceIsPond;
    // 1_Core/proto/EnMath.c:17 DEG2RAD, :331 Sin, :343 Cos;
    // 1_Core/proto/EnMath3D.c:18 Vector; 1_Core/proto/EnScript.c:380 Count.
    static HCPerceptionRingPick HCFindLand(vector centre, float preferredDegrees, array<vector> observers, int maxCandidates)
    {
        HCPerceptionRingPick result = new HCPerceptionRingPick();
        if (!GetGame() || !GetGame().IsServer() || !observers || maxCandidates <= 0)
        {
            result.Reason = "spawn_ring_search_unavailable";
            return result;
        }
        if (maxCandidates > HCOperatorSettingsRegistry.HCMaximum("MaxTickWorkItems") || observers.Count() == 0 || !(preferredDegrees >= 0 && preferredDegrees <= 360))
        {
            result.Reason = "spawn_ring_search_unavailable";
            return result;
        }
        // Mid-band avoids floating-point equality at the minimum safety floor.
        float radius = HCPerceptionRing.HCSpawnMin() + HCPerceptionRing.HCGet().SpawnBandMeters * 0.5;
        int candidateIndex = 0;
        while (candidateIndex < maxCandidates)
        {
            float radians = (preferredDegrees + 360.0 * candidateIndex / maxCandidates) * Math.DEG2RAD;
            float px = centre[0] + radius * Math.Sin(radians);
            float pz = centre[2] + radius * Math.Cos(radians);
            candidateIndex++;
            result.Attempts = candidateIndex;
            if (GetGame().SurfaceIsSea(px, pz) || GetGame().SurfaceIsPond(px, pz)) { continue; }
            vector point = Vector(px, GetGame().SurfaceY(px, pz), pz);
            if (!HCPerceptionRing.HCClearOfObservers(point, observers)) { continue; }
            result.Position = point;
            result.Reason = "";
            return result;
        }
        return result;
    }

    // Horizontal distance is conservative even on cliffs. Missing/NaN observer
    // coordinates fail closed. Snapshot must include every live player; the
    // caller retains its existing final SeenByPlayer/MemberProblemFor checks.
    static bool HCClearOfObservers(vector point, array<vector> observers)
    {
        float minimum = HCPerceptionRing.HCSpawnMin();
        array<vector> observerPositions = observers;
        foreach (vector observerPosition : observerPositions)
        {
            float dx = point[0] - observerPosition[0];
            float dz = point[2] - observerPosition[2];
            if (!(dx * dx + dz * dz >= minimum * minimum)) { return false; }
        }
        return true;
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
