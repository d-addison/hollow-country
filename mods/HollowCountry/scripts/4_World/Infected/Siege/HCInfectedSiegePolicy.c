// Siege policy (wh-nav-c, 2026-11-22): pure decisions for the infected siege of an elevated haven.
// The engine gives infected no ladder and no climb, so a player on a roof, container or tower is
// sieged instead of faked-at: the infected that gave up make real
// noise at their own position, amplified through the native noise strength multiplier so the ambient
// population hears it from a wider perimeter. A siege never spawns infected (owner 2026-11-23, #354).
// Nothing here reads the engine; HCInfectedSiege.c owns every engine call.
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
    // Multiplier on the siege noise strength (NoiseSystem.AddNoisePos external_strenght_multiplier).
    // Arithmetic: the installed config entry CfgVehicles SurvivorBase NoiseActionDefault has strength = 10
    // (characters_data.pbo config.bin, 1.30.164289; the shipped game, not the scripts). Taking strength as
    // metres of hearing radius (the unobserved assumption the old reinforce ring also made; the engine's
    // exact mapping is not in the scripts), 10 m x 17 = 170 m, inside the 150-200 m aim, before the
    // environment reduction (Noise.c:13, an absolute subtraction) which only shortens it. The runtime clamp
    // (HCInfectedSiegePolicy.HCNoiseMultiplier) keeps strength x multiplier at or under 250 m.
    float NoiseStrengthMultiplier = 17;
    int MaxSieges = 8;
    // Retired 2026-11-23: a siege never spawns infected. Still decoded and registered so an operator file that
    // sets it loads; the value is ignored and a non-zero one is reported once at start.
    int ReinforcePerPlayerWindow = 0;

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
        if (HCJsonFields.Has(text, "NoiseStrengthMultiplier") && HCValid("NoiseStrengthMultiplier", decoded.NoiseStrengthMultiplier, 1, 25)) { NoiseStrengthMultiplier = decoded.NoiseStrengthMultiplier; }
        if (HCJsonFields.Has(text, "MaxSieges") && HCValid("MaxSieges", decoded.MaxSieges, 1, 8)) { MaxSieges = decoded.MaxSieges; }
        if (HCJsonFields.Has(text, "ReinforcePerPlayerWindow") && HCValid("ReinforcePerPlayerWindow", decoded.ReinforcePerPlayerWindow, 0, 8)) { ReinforcePerPlayerWindow = decoded.ReinforcePerPlayerWindow; }
        if (ReinforcePerPlayerWindow != 0) { Print("[HC Nav] siege retired key ignored key=ReinforcePerPlayerWindow value=" + ReinforcePerPlayerWindow.ToString() + " (a siege never spawns infected; safe to remove) runtime=PENDING"); }
    }

    void HCLog()
    {
        Print("[HC Nav] siege effective Enabled=" + HCV2Admission.OnOff(Enabled) + " GatherSeconds=" + GatherSeconds.ToString() + " NoiseSeconds=" + NoiseSeconds.ToString() + " NoiseStrengthMultiplier=" + NoiseStrengthMultiplier.ToString() + " MaxSieges=" + MaxSieges.ToString() + " runtime=PENDING");
    }
}

class HCInfectedSiegePolicy
{
    static const string END_DOWN = "down";
    static const string END_LEFT = "left";
    static const string END_TIMEOUT = "timeout";
    static const string END_NO_LIVE_MEMBER = "no_live_member";
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
    // The strength of NoiseActionDefault in the installed config (10), used only when the config read gives
    // nothing. The siege noise is never allowed an effective strength above NOISE_RADIUS_CAP_METRES.
    static const float NOISE_BASE_STRENGTH = 10;
    static const float NOISE_RADIUS_CAP_METRES = 250;
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

    // The multiplier the siege noise really uses: the requested one, at least 1 (vanilla strength) and never
    // so large that base strength x multiplier passes the radius cap. A base strength of 0 or less (entry
    // absent or unreadable) falls back to the installed value so the cap still bites.
    static float HCNoiseMultiplier(float requested, float baseStrength)
    {
        float perUnit = baseStrength;
        if (!(perUnit > 0)) { perUnit = NOISE_BASE_STRENGTH; }
        float ceiling = NOISE_RADIUS_CAP_METRES / perUnit;
        float used = requested;
        if (!(used >= 1)) { used = 1; }
        if (used > ceiling) { used = ceiling; }
        if (used < 1) { used = 1; }
        return used;
    }

    // A start line is printed for the first few sieges, then every START_LINE_EVERY-th.
    static bool HCPrintStart(int started)
    {
        if (started <= START_LINES) { return true; }
        return started % START_LINE_EVERY == 0;
    }
}
