// Optional gc-actors-defence.json; absent fields retain these defaults, explicit false opts out.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnConvert.c:30,115 int/float ToString.
// Bounded HCGroupIO + HCJsonSchema loader; HCJsonFields retains optional-field guards; no engine/Expansion gameplay calls added.
class GCActorsDefenceConfig
{
    bool Enabled = true;
    int GRUDGE_CAP = 64;
    int SHOT_WINDOW_CAP = 6;
    int SHOT_SPACING_MS = 750;
    int LOS_MEMORY_MS = 15000;
    int SEED_WINDOW_MS = 20000;
    int RESCUE_WINDOW_MS = 30000;
    int RAYCASTS_PER_SHOT = 4;
    float INFECTED_RADIUS = 25.0;
    float PASS_RADIUS = 4.0;
    float PASS_REACH = 200.0;
    float PASS_MARGIN = 2.0;
    float CLOSE_RADIUS = 12.0;
    float FIGHT_THREAT = 0.6;
    float ORIGIN_REACH = 150.0;
    int HitHoldMs = 240000;
    int KillHoldMs = 300000;
    int MissHoldMs = 90000;

    protected string m_LastRefusal;
    void HCRefuse(string reason)
    {
        if (m_LastRefusal == reason) { return; }
        m_LastRefusal = reason;
        Print("[HCX Defence] config_refused=" + reason + " defaults_retained runtime=PENDING");
    }

    bool HCValid(string key, float value, float low, float high)
    {
        // Local ceilings remain effective until the lead merges the shared registry rows.
        if (!(value >= low && value <= high)) { HCRefuse(key); return false; }
        string fullKey = "ActorDefence." + key;
        if (HCOperatorSettingsRegistry.HCFind(fullKey) && !HCOperatorSettingsRegistry.HCValid(fullKey, value)) { HCRefuse(key); return false; }
        return true;
    }

    void HCLoad()
    {
        string path = "$profile:HollowCountry/gc-actors-defence.json";
        if (!FileExist(path)) { return; }
        string text;
        string error;
        GCActorsDefenceConfig decoded;
        if (!HCGroupIO.Read(path, 4096, text)) { HCRefuse("read"); return; }
        if (!HCJsonSchemaLoader<GCActorsDefenceConfig>.HCLoadData(text, decoded, error) || !decoded) { HCRefuse("json"); return; }
        if (HCJsonFields.Has(text, "Enabled")) { Enabled = decoded.Enabled; }
        if (HCJsonFields.Has(text, "GRUDGE_CAP") && HCValid("GRUDGE_CAP", decoded.GRUDGE_CAP, 1, 64)) { GRUDGE_CAP = decoded.GRUDGE_CAP; }
        if (HCJsonFields.Has(text, "SHOT_WINDOW_CAP") && HCValid("SHOT_WINDOW_CAP", decoded.SHOT_WINDOW_CAP, 1, 6)) { SHOT_WINDOW_CAP = decoded.SHOT_WINDOW_CAP; }
        if (HCJsonFields.Has(text, "SHOT_SPACING_MS") && HCValid("SHOT_SPACING_MS", decoded.SHOT_SPACING_MS, 750, 60000)) { SHOT_SPACING_MS = decoded.SHOT_SPACING_MS; }
        if (HCJsonFields.Has(text, "LOS_MEMORY_MS") && HCValid("LOS_MEMORY_MS", decoded.LOS_MEMORY_MS, 1, 15000)) { LOS_MEMORY_MS = decoded.LOS_MEMORY_MS; }
        if (HCJsonFields.Has(text, "SEED_WINDOW_MS") && HCValid("SEED_WINDOW_MS", decoded.SEED_WINDOW_MS, 1, 20000)) { SEED_WINDOW_MS = decoded.SEED_WINDOW_MS; }
        if (HCJsonFields.Has(text, "RESCUE_WINDOW_MS") && HCValid("RESCUE_WINDOW_MS", decoded.RESCUE_WINDOW_MS, 1, 30000)) { RESCUE_WINDOW_MS = decoded.RESCUE_WINDOW_MS; }
        if (HCJsonFields.Has(text, "RAYCASTS_PER_SHOT") && HCValid("RAYCASTS_PER_SHOT", decoded.RAYCASTS_PER_SHOT, 1, 4)) { RAYCASTS_PER_SHOT = decoded.RAYCASTS_PER_SHOT; }
        if (HCJsonFields.Has(text, "INFECTED_RADIUS") && HCValid("INFECTED_RADIUS", decoded.INFECTED_RADIUS, 1, 25)) { INFECTED_RADIUS = decoded.INFECTED_RADIUS; }
        if (HCJsonFields.Has(text, "PASS_RADIUS") && HCValid("PASS_RADIUS", decoded.PASS_RADIUS, 0.1, 4)) { PASS_RADIUS = decoded.PASS_RADIUS; }
        if (HCJsonFields.Has(text, "PASS_REACH") && HCValid("PASS_REACH", decoded.PASS_REACH, 1, 200)) { PASS_REACH = decoded.PASS_REACH; }
        if (HCJsonFields.Has(text, "PASS_MARGIN") && HCValid("PASS_MARGIN", decoded.PASS_MARGIN, 0.1, 2)) { PASS_MARGIN = decoded.PASS_MARGIN; }
        if (HCJsonFields.Has(text, "CLOSE_RADIUS") && HCValid("CLOSE_RADIUS", decoded.CLOSE_RADIUS, 0.1, 12)) { CLOSE_RADIUS = decoded.CLOSE_RADIUS; }
        if (HCJsonFields.Has(text, "FIGHT_THREAT") && HCValid("FIGHT_THREAT", decoded.FIGHT_THREAT, 0.1, 0.6)) { FIGHT_THREAT = decoded.FIGHT_THREAT; }
        if (HCJsonFields.Has(text, "ORIGIN_REACH") && HCValid("ORIGIN_REACH", decoded.ORIGIN_REACH, 1, 150)) { ORIGIN_REACH = decoded.ORIGIN_REACH; }
        if (HCJsonFields.Has(text, "HitHoldMs") && HCValid("HitHoldMs", decoded.HitHoldMs, 1, 240000)) { HitHoldMs = decoded.HitHoldMs; }
        if (HCJsonFields.Has(text, "KillHoldMs") && HCValid("KillHoldMs", decoded.KillHoldMs, 1, 300000)) { KillHoldMs = decoded.KillHoldMs; }
        if (HCJsonFields.Has(text, "MissHoldMs") && HCValid("MissHoldMs", decoded.MissHoldMs, 1, 90000)) { MissHoldMs = decoded.MissHoldMs; }
        if (HitHoldMs > KillHoldMs) { HitHoldMs = KillHoldMs; }
        if (MissHoldMs > HitHoldMs) { MissHoldMs = HitHoldMs; }
        if (PASS_MARGIN > PASS_REACH) { PASS_MARGIN = PASS_REACH; }
    }

    void HCLog()
    {
        Print("[HCX Defence] effective Enabled=" + HCV2Admission.OnOff(Enabled) + " runtime=PENDING");
        Print("[HCX Defence] effective" + " GRUDGE_CAP=" + GRUDGE_CAP.ToString() + " SHOT_WINDOW_CAP=" + SHOT_WINDOW_CAP.ToString() + " SHOT_SPACING_MS=" + SHOT_SPACING_MS.ToString() + " runtime=PENDING");
        Print("[HCX Defence] effective" + " LOS_MEMORY_MS=" + LOS_MEMORY_MS.ToString() + " SEED_WINDOW_MS=" + SEED_WINDOW_MS.ToString() + " RESCUE_WINDOW_MS=" + RESCUE_WINDOW_MS.ToString() + " runtime=PENDING");
        Print("[HCX Defence] effective" + " RAYCASTS_PER_SHOT=" + RAYCASTS_PER_SHOT.ToString() + " INFECTED_RADIUS=" + INFECTED_RADIUS.ToString() + " PASS_RADIUS=" + PASS_RADIUS.ToString() + " runtime=PENDING");
        Print("[HCX Defence] effective" + " PASS_REACH=" + PASS_REACH.ToString() + " PASS_MARGIN=" + PASS_MARGIN.ToString() + " CLOSE_RADIUS=" + CLOSE_RADIUS.ToString() + " runtime=PENDING");
        Print("[HCX Defence] effective" + " FIGHT_THREAT=" + FIGHT_THREAT.ToString() + " ORIGIN_REACH=" + ORIGIN_REACH.ToString() + " HitHoldMs=" + HitHoldMs.ToString() + " runtime=PENDING");
        Print("[HCX Defence] effective" + " KillHoldMs=" + KillHoldMs.ToString() + " MissHoldMs=" + MissHoldMs.ToString() + " runtime=PENDING");
    }
}

// HCX self-defence pure policy (owner bug 2026-11-18). Numbers only: no native
// API, entity or identity in its decisions; optional tuning loads at startup. Synthetic
// results are not native acceptance; hostility, noise and impact behaviour stay
// runtime-pending until a server session is observed.
// Proportional response: a hit holds a grudge for minutes, a kill a little
// longer, a near miss only briefly. Every grudge expires; none is server-wide.
class HCXDefencePolicy
{
    static const int KIND_HIT = 1;
    static const int KIND_KILL = 2;
    static const int KIND_MISS = 3;
    static const int KIND_RESCUE = 4;
    static const int NEAR_NONE = 0;
    static const int NEAR_PASS = 1;
    static const int NEAR_CLOSE = 2;
    static int GRUDGE_CAP = 64;
    static int SHOT_WINDOW_CAP = 6;
    static int SHOT_SPACING_MS = 750;
    static int LOS_MEMORY_MS = 15000;
    static int SEED_WINDOW_MS = 20000;
    static int RESCUE_WINDOW_MS = 30000;
    static int RAYCASTS_PER_SHOT = 4;
    static float INFECTED_RADIUS = 25.0;
    static float PASS_RADIUS = 4.0;
    static float PASS_REACH = 200.0;
    static float PASS_MARGIN = 2.0;
    static float CLOSE_RADIUS = 12.0;
    static float FIGHT_THREAT = 0.6;
    static float ORIGIN_REACH = 150.0;

    protected static ref GCActorsDefenceConfig s_Limits;

    static void HCLoadLimits()
    {
        s_Limits = new GCActorsDefenceConfig;
        s_Limits.HCLoad();
        s_Limits.HCLog();
        HCXDefencePolicy.GRUDGE_CAP = s_Limits.GRUDGE_CAP;
        HCXDefencePolicy.SHOT_WINDOW_CAP = s_Limits.SHOT_WINDOW_CAP;
        HCXDefencePolicy.SHOT_SPACING_MS = s_Limits.SHOT_SPACING_MS;
        HCXDefencePolicy.LOS_MEMORY_MS = s_Limits.LOS_MEMORY_MS;
        HCXDefencePolicy.SEED_WINDOW_MS = s_Limits.SEED_WINDOW_MS;
        HCXDefencePolicy.RESCUE_WINDOW_MS = s_Limits.RESCUE_WINDOW_MS;
        HCXDefencePolicy.RAYCASTS_PER_SHOT = s_Limits.RAYCASTS_PER_SHOT;
        HCXDefencePolicy.INFECTED_RADIUS = s_Limits.INFECTED_RADIUS;
        HCXDefencePolicy.PASS_RADIUS = s_Limits.PASS_RADIUS;
        HCXDefencePolicy.PASS_REACH = s_Limits.PASS_REACH;
        HCXDefencePolicy.PASS_MARGIN = s_Limits.PASS_MARGIN;
        HCXDefencePolicy.CLOSE_RADIUS = s_Limits.CLOSE_RADIUS;
        HCXDefencePolicy.FIGHT_THREAT = s_Limits.FIGHT_THREAT;
        HCXDefencePolicy.ORIGIN_REACH = s_Limits.ORIGIN_REACH;
    }

    static bool HCEnabled() { return s_Limits && s_Limits.Enabled; }

    // Milliseconds a grudge lasts after the last aggression of this kind.
    static int HoldMs(int kind)
    {
        if (!s_Limits) { HCLoadLimits(); }
        if (kind == HCXDefencePolicy.KIND_KILL) { return s_Limits.KillHoldMs; }
        if (kind == HCXDefencePolicy.KIND_HIT) { return s_Limits.HitHoldMs; }
        if (kind == HCXDefencePolicy.KIND_MISS) { return s_Limits.MissHoldMs; }
        if (kind == HCXDefencePolicy.KIND_RESCUE) { return HCXDefencePolicy.RESCUE_WINDOW_MS; }
        return 0;
    }

    // A grudge applies only until its deadline, only near where it happened, and
    // only to an actor that perceived the attacker: live LOS, LOS within
    // LOS_MEMORY_MS, or the short native hit-direction window after Expansion
    // itself seeded this very actor (seededAtMs). The Expansion seeded flag is not
    // perception, so it is never an input here.
    static bool Active(int nowMs, int untilMs, float distanceToOrigin, bool los, int lastLosMs, int seededAtMs)
    {
        if (untilMs <= 0 || nowMs >= untilMs) { return false; }
        if (distanceToOrigin != distanceToOrigin || distanceToOrigin > HCXDefencePolicy.ORIGIN_REACH) { return false; }
        if (los) { return true; }
        if (lastLosMs > 0 && nowMs >= lastLosMs && nowMs - lastLosMs <= HCXDefencePolicy.LOS_MEMORY_MS) { return true; }
        if (seededAtMs > 0 && nowMs >= seededAtMs && nowMs - seededAtMs <= HCXDefencePolicy.SEED_WINDOW_MS) { return true; }
        return false;
    }

    // First non-lethal hit on a friendly or allied actor while infected are near
    // is a stray rescue round: excused once per RESCUE_WINDOW_MS. priorUntilMs is
    // the deadline of the latest record for this group and player (0 when none);
    // a real grudge or an unexpired excuse makes the next hit count.
    static bool RescueHitExcused(bool friendly, int infectedNear, bool lethal, int nowMs, int priorUntilMs)
    {
        if (!friendly || lethal || infectedNear <= 0) { return false; }
        return nowMs >= priorUntilMs;
    }

    // End of the near-miss ray: the first raycast hit plus a small margin, never
    // beyond PASS_REACH. A negative or zero hit distance means no hit.
    static float PassEnd(float hitDistance)
    {
        if (hitDistance != hitDistance || hitDistance <= 0) { return HCXDefencePolicy.PASS_REACH; }
        return Math.Min(HCXDefencePolicy.PASS_REACH, hitDistance + HCXDefencePolicy.PASS_MARGIN);
    }

    // Lifts a watching or eyeballing actor to the fight threat; never lowers a
    // stronger native threat.
    static float Threat(float baseThreat, bool active)
    {
        if (!active) { return baseThreat; }
        return Math.Max(baseThreat, HCXDefencePolicy.FIGHT_THREAT);
    }

    // A shot near a person who is also being attacked by infected is a rescue,
    // not aggression: any infected near the shooter or the actor excuses it.
    static bool Excused(int infectedNearShooter, int infectedNearActor)
    {
        return infectedNearShooter > 0 || infectedNearActor > 0;
    }

    // along: metres along the shot ray to the point closest to the actor;
    // perp: perpendicular metres from the ray to the actor; shooterDistance:
    // metres shooter to actor. A bullet passing within PASS_RADIUS is a near
    // miss only before passEnd (the bullet's first hit); a loud weapon fired within CLOSE_RADIUS of the actor is a close shot.
    static int Classify(float along, float perp, float shooterDistance, bool loud, float passEnd)
    {
        if (along != along || perp != perp || shooterDistance != shooterDistance) { return HCXDefencePolicy.NEAR_NONE; }
        if (along > 0 && along <= passEnd && perp <= HCXDefencePolicy.PASS_RADIUS) { return HCXDefencePolicy.NEAR_PASS; }
        if (loud && shooterDistance <= HCXDefencePolicy.CLOSE_RADIUS) { return HCXDefencePolicy.NEAR_CLOSE; }
        return HCXDefencePolicy.NEAR_NONE;
    }

    // Per-player spacing and a shared window cap bound the near-miss work.
    static bool ShotAllowed(int nowMs, int nextMs, int windowCount, int windowCap)
    {
        if (nowMs < nextMs) { return false; }
        if (windowCount >= windowCap) { return false; }
        return true;
    }

    // Index of the grudge to replace when the store is full (the oldest), else -1.
    static int EvictIndex(int count, int cap)
    {
        if (count < cap) { return -1; }
        return 0;
    }
}

// Reuse the existing service/module slot. Load once before direct field consumers
// run; do not call the legacy startup with its fixed-value diagnostic.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer.
modded class HCXDefenceModule
{
    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings)) { return; }
        if (HCXDefence.Running())
        {
            Print("[HCX Defence] start ignored: already running");
            return;
        }
        HCXDefencePolicy.HCLoadLimits();
        if (!HCXDefencePolicy.HCEnabled())
        {
            m_Operational.HCPublish("off", "defence_operator_off");
            return;
        }
        HCXDefence.Start();
        Print(HCV2Admission.Line("AISelfDefence", true, "W7-AIDEF", false));
        Print("[HCX Defence] started configured_policy=gc-actors-defence.json runtime=PENDING");
    }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        if (!HCXDefencePolicy.HCEnabled()) { m_Operational.HCPublish("off", "defence_not_started_or_operator_off"); }
        else { HCModuleReadiness.HCDerive(m_Operational, HCXDefence.Running(), "", "", "defence_grudge_service_running"); }
        return m_Operational;
    }
}
