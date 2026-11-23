// Siege policy (wh-nav-c, 2026-11-22): pure decisions for the infected siege of an elevated haven.
// The engine gives infected no ladder and no climb, so a player on a roof, container or tower is
// sieged instead of faked-at: the infected that gave up make real
// noise at their own position, and a bounded number of hidden reinforcements are sent. Nothing here
// reads the engine; HCInfectedSiege.c owns every engine call.
// Native evidence, installed scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnConvert.c:30,115 int/float ToString; EnMath.c AbsFloat, Sqrt.
// Optional gc-infected-siege.json: absent fields keep these defaults, explicit false opts out.
// Registry rows: 3_Game/HCInfectedSiegeSettingsRegistry.c (InfectedSiege.*), consulted by HCValid.
class HCInfectedSiegeConfig
{
    bool Enabled = true;
    float GatherSeconds = 8;
    float NoiseSeconds = 20;
    int MaxSieges = 8;
    int ReinforcePerPlayerWindow = 4;

    protected string m_LastRefusal;
    void HCRefuse(string reason)
    {
        if (m_LastRefusal == reason) { return; }
        m_LastRefusal = reason;
        Print("[HC Nav] siege config_refused=" + reason + " defaults_retained runtime=PENDING");
    }

    bool HCValid(string key, float value, float low, float high)
    {
        if (!(value >= low && value <= high)) { HCRefuse(key); return false; }
        HCOperatorSettingsRegistry.HCInfectedSiegeInit();
        string fullKey = "InfectedSiege." + key;
        if (HCOperatorSettingsRegistry.HCFind(fullKey) && !HCOperatorSettingsRegistry.HCValid(fullKey, value)) { HCRefuse(key); return false; }
        return true;
    }

    void HCLoad()
    {
        HCOperatorSettingsRegistry.HCInfectedSiegeInit();
        string path = "$profile:HollowCountry/gc-infected-siege.json";
        if (!FileExist(path)) { return; }
        string text;
        string error;
        HCInfectedSiegeConfig decoded;
        if (!HCGroupIO.Read(path, 2048, text)) { HCRefuse("read"); return; }
        if (!JsonFileLoader<HCInfectedSiegeConfig>.LoadData(text, decoded, error) || !decoded) { HCRefuse("json"); return; }
        if (HCJsonFields.Has(text, "Enabled")) { Enabled = decoded.Enabled; }
        if (HCJsonFields.Has(text, "GatherSeconds") && HCValid("GatherSeconds", decoded.GatherSeconds, 3, 60)) { GatherSeconds = decoded.GatherSeconds; }
        if (HCJsonFields.Has(text, "NoiseSeconds") && HCValid("NoiseSeconds", decoded.NoiseSeconds, 10, 120)) { NoiseSeconds = decoded.NoiseSeconds; }
        if (HCJsonFields.Has(text, "MaxSieges") && HCValid("MaxSieges", decoded.MaxSieges, 1, 8)) { MaxSieges = decoded.MaxSieges; }
        if (HCJsonFields.Has(text, "ReinforcePerPlayerWindow") && HCValid("ReinforcePerPlayerWindow", decoded.ReinforcePerPlayerWindow, 0, 8)) { ReinforcePerPlayerWindow = decoded.ReinforcePerPlayerWindow; }
    }

    void HCLog()
    {
        Print("[HC Nav] siege effective Enabled=" + HCV2Admission.OnOff(Enabled) + " GatherSeconds=" + GatherSeconds.ToString() + " NoiseSeconds=" + NoiseSeconds.ToString() + " MaxSieges=" + MaxSieges.ToString() + " ReinforcePerPlayerWindow=" + ReinforcePerPlayerWindow.ToString() + " runtime=PENDING");
    }
}

class HCInfectedSiegePolicy
{
    static const string END_DOWN = "down";
    static const string END_LEFT = "left";
    static const string END_TIMEOUT = "timeout";
    // Siege evaluations per tick (one navmesh sample and at most one ladder query each) and their slice.
    static const int EVALUATIONS_PER_TICK = 4;
    static const float SLICE_MILLISECONDS = 2;
    // The target walks this far from where the siege opened and the siege is over.
    static const float LEAVE_METRES = 25;
    static const float TIMEOUT_SECONDS = 180;
    static const int MAX_MEMBERS = 6;
    static const float ANCHOR_SAMPLE_METRES = 6;
    // A ladder counts when its top is this close to where the player stands.
    static const float LADDER_TOP_METRES = 12;
    static const int LADDER_SCAN = 8;
    // The bottom of a world-space ladder lies within this of its building.
    static const float LADDER_SPACE_METRES = 50;
    // Reinforcement: one batch per siege, at most 2 bodies and 6 attempts, 3 s apart; the per-player
    // window is the cap on bodies a single player can draw in 10 minutes.
    static const int REINFORCE_BATCH = 2;
    static const int REINFORCE_TRIES = 6;
    static const float REINFORCE_GAP_SECONDS = 3;
    static const float REINFORCE_WINDOW_SECONDS = 600;
    static const int WINDOW_SLOTS = 8;
    // Hidden spawn ring (HCHordeReinforce.HCHidden needs 300 m from every player).
    static const float RING_MIN_METRES = 320;
    static const float RING_MAX_METRES = 360;
    static const float RING_SAMPLE_METRES = 20;
    static const int START_LINES = 8;
    static const int START_LINE_EVERY = 16;

    static float HCHorizontal(vector a, vector b)
    {
        float dx = a[0] - b[0];
        float dz = a[2] - b[2];
        return Math.Sqrt(dx * dx + dz * dz);
    }

    // The siege ends when the target stands near the level of the sieging infected again (down),
    // walks away from the place the siege opened at (left) or the siege has run its cap (timeout).
    // An empty string keeps the siege going.
    static string HCEndReason(float targetY, float baseY, float horizontal, float age, float band)
    {
        if (targetY - baseY < band) { return END_DOWN; }
        if (horizontal > LEAVE_METRES) { return END_LEFT; }
        if (age >= TIMEOUT_SECONDS) { return END_TIMEOUT; }
        return "";
    }

    // The haven test of the census: the target is up by at least the reach band.
    static bool HCHaven(float dy, float band)
    {
        return dy >= band;
    }

    // Ladder positions are world coordinates when the bottom lies near the building; otherwise they are
    // tested as model-space (the caller converts with ModelToWorld). Anything still far away is refused.
    static bool HCLadderSpaceOk(vector bottom, vector host)
    {
        return vector.Distance(bottom, host) <= LADDER_SPACE_METRES;
    }

    static int HCBatch(int cap, int used)
    {
        int remaining = cap - used;
        if (remaining < 1) { return 0; }
        if (remaining > REINFORCE_BATCH) { return REINFORCE_BATCH; }
        return remaining;
    }

    static bool HCWindowExpired(float now, float start)
    {
        return now - start >= REINFORCE_WINDOW_SECONDS;
    }

    // A start line is printed for the first few sieges, then every START_LINE_EVERY-th.
    static bool HCPrintStart(int started)
    {
        if (started <= START_LINES) { return true; }
        return started % START_LINE_EVERY == 0;
    }
}
