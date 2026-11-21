// LOG ONLY. Server-owned head/zone geometry; no gameplay decisions consume this.
// Native scripts-1.30.164289 (relative paths):
// 3_Game/human.c:1417 GetBoneIndexByName; Entities/Object.c:238,287,1159
// GetBonePositionWS/GetPosition/GetDamageZonePos (world space).
// 4_World/Entities/DayZPlayerImplementMeleeCombat.c:313-323,339,359:
// weapon mode range + 0.65, head -> zone squared distance. This is a range
// proxy, not a replay of camera/cone selection, finishers or client targeting.
// 3_Game/Global/DayZPhysics.c:1-44,211 RayCastBullet and layer constants;
// 4_World/Classes/MeleeTargeting.c:74,272-288 uses the same ray API.
// Static-world subset excludes vehicles/items/characters; movable obstacles
// are intentionally outside this wall diagnostic. No shift of layer constants.
// 1_Core/proto/EnConvert.c vector.DistanceSq; EnMath.c Sqrt/AbsFloat/Atan2/RAD2DEG.
// ZombieBase.c:1090 IsCrawling; HCVarietyPosed is the existing HC pose accessor.
class HCMeleeTargetingParity
{
    protected static int s_Agree;
    protected static int s_OursOnly;
    protected static int s_VanillaOnly;
    protected static int s_Wall;
    protected static int s_Crawler;
    protected static int s_Posed;
    protected static int s_Unknown;
    protected static float s_MaxDelta;
    protected static float s_LowMaxPitch;
    protected static float s_LowMinDY;
    protected static float s_LowMaxDY;
    protected static bool s_HasLow;
    protected static bool s_HasSample;
    protected static float s_MaxPitch;
    protected static float s_MinDY;
    protected static float s_MaxDY;

    static void Reset()
    {
        s_Agree = 0;
        s_OursOnly = 0;
        s_VanillaOnly = 0;
        s_Wall = 0;
        s_Crawler = 0;
        s_Posed = 0;
        s_Unknown = 0;
        s_MaxDelta = 0;
        s_LowMaxPitch = 0;
        s_LowMinDY = 0;
        s_LowMaxDY = 0;
        s_HasLow = false;
        s_HasSample = false;
        s_MaxPitch = 0;
        s_MinDY = 0;
        s_MaxDY = 0;
    }

    protected static int Increment(int count)
    {
        if (count < 2147483647) { count++; }
        return count;
    }

    static void Observe(PlayerBase attacker, ZombieBase target, string zone, vector modelPos)
    {
        if (!HCMeleeModule.Active()) { return; }
        // Non-player melee (e.g. infected versus infected) has no player range.
        if (!attacker || !target) { return; }
        if (zone == "") { s_Unknown = Increment(s_Unknown); return; }
        int headBone = attacker.GetBoneIndexByName("Head");
        float limit = HCMeleeTarget.ParityVanillaRange(attacker);
        if (headBone < 0 || limit <= 0) { s_Unknown = Increment(s_Unknown); return; }
        vector head = attacker.GetBonePositionWS(headBone);
        vector zonePos = target.GetDamageZonePos(zone);
        vector offset = zonePos - head;
        float distanceSq = vector.DistanceSq(head, zonePos);
        float feetSq = vector.DistanceSq(attacker.GetPosition(), target.GetPosition());
        // Reject degenerate/non-finite probes; never trace an unbounded segment.
        // This diagnostic cap does not alter either gameplay reach or damage.
        if (!(distanceSq > 0) || !(distanceSq <= 10000) || !(feetSq <= 10000))
        {
            s_Unknown = Increment(s_Unknown);
            return;
        }
        float distance = Math.Sqrt(distanceSq);
        float feet = Math.Sqrt(feetSq);
        float delta = Math.AbsFloat(distance - feet);
        if (delta > s_MaxDelta) { s_MaxDelta = delta; }
        float horizontal = Math.Sqrt(offset[0] * offset[0] + offset[2] * offset[2]);
        float pitch = Math.Atan2(offset[1], horizontal) * Math.RAD2DEG;
        float absPitch = Math.AbsFloat(pitch);
        if (absPitch > s_MaxPitch) { s_MaxPitch = absPitch; }
        // All-hit extrema also retain posed-hit geometry if an outer EEHitBy
        // hook already cleared the variety pose flag while starting a get-up.
        if (!s_HasSample || offset[1] < s_MinDY) { s_MinDY = offset[1]; }
        if (!s_HasSample || offset[1] > s_MaxDY) { s_MaxDY = offset[1]; }
        s_HasSample = true;
        bool crawling = target.IsCrawling();
        bool posed = target.HCVarietyPosed();
        if (crawling) { s_Crawler = Increment(s_Crawler); }
        if (posed) { s_Posed = Increment(s_Posed); }
        if (crawling || posed)
        {
            if (absPitch > s_LowMaxPitch) { s_LowMaxPitch = absPitch; }
            if (!s_HasLow || offset[1] < s_LowMinDY) { s_LowMinDY = offset[1]; }
            if (!s_HasLow || offset[1] > s_LowMaxDY) { s_LowMaxDY = offset[1]; }
            s_HasLow = true;
        }
        Object hitObject;
        vector hitPosition, hitNormal;
        float hitFraction;
        PhxInteractionLayers layers = PhxInteractionLayers.BUILDING | PhxInteractionLayers.DOOR | PhxInteractionLayers.ROADWAY | PhxInteractionLayers.TERRAIN | PhxInteractionLayers.FENCE;
        bool blocked = DayZPhysics.RayCastBullet(head, zonePos, layers, attacker, hitObject, hitPosition, hitNormal, hitFraction);
        bool oursOK = HCMeleeTarget.ImplausibleReason(attacker, target, zone, modelPos) == "";
        bool vanillaOK = distanceSq <= limit * limit;
        // Exclusive buckets: wall takes precedence; agree includes both rejected.
        // oursOK includes HC's unchanged model-hit/zone tolerance as well as reach.
        if (blocked) { s_Wall = Increment(s_Wall); }
        else if (!oursOK && vanillaOK) { s_OursOnly = Increment(s_OursOnly); }
        else if (oursOK && !vanillaOK) { s_VanillaOnly = Increment(s_VanillaOnly); }
        else { s_Agree = Increment(s_Agree); }
        HCModuleReadiness.HCUse("Melee", "parity_probe");
    }

    static void Summary()
    {
        string line = "[HC Melee] parity agree=" + s_Agree.ToString() + " ours_only=" + s_OursOnly.ToString();
        line += " vanilla_only=" + s_VanillaOnly.ToString() + " wall_blocked=" + s_Wall.ToString();
        line += " crawler=" + s_Crawler.ToString() + " posed=" + s_Posed.ToString() + " unknown=" + s_Unknown.ToString();
        line += " max_delta_m=" + s_MaxDelta.ToString() + " low_max_abs_pitch_deg=" + s_LowMaxPitch.ToString();
        line += " low_min_dy_m=" + s_LowMinDY.ToString() + " low_max_dy_m=" + s_LowMaxDY.ToString();
        line += " max_abs_pitch_deg=" + s_MaxPitch.ToString();
        line += " min_dy_m=" + s_MinDY.ToString() + " max_dy_m=" + s_MaxDY.ToString();
        Print(line + " runtime=PENDING");
    }
}

// Extend the existing lifecycle cadence without another timer or per-hit Print.
modded class HCMeleeLog
{
    override static void Reset()
    {
        super.Reset();
        HCMeleeTargetingParity.Reset();
    }

    override static void Summary()
    {
        super.Summary();
        HCMeleeTargetingParity.Summary();
    }
}

modded class HCModuleReadiness
{
    override static void HCRegisterModuleUses(string module)
    {
        super.HCRegisterModuleUses(module);
        if (module == "Melee") { HCRegisterUse("Melee", "parity_probe"); }
    }
}
