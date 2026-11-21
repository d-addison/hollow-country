// s1-formations. Context-driven formation and movement style for HC site groups.
// Everything is read-only context plus the existing Expansion group/member setters.
// No teleport, no position or target write, no door or path change, no player
// knowledge: the context is the leader's own surface, an authored site house and
// the group's own combat flag.
//
// Expansion AI 1.9.84 (installed ai_scripts.pbo; reference copy not committed):
//   Classes/Formations/eAIFormation.c:37 GetPosition (abstract, local space),
//     :42 GetDirection (idle look direction), :47 SetLooseness.
//   Classes/eAIGroup.c:933 SetFormation, :903 GetFormation, :923 GetFormationLeader,
//     :1123 IsInCombat, :1139 GetMember, :1185 Count, :222 GetWaypoints,
//     :37 m_CurrentWaypointIndex. :816-855 GetFormationPosition asks the group
//     formation for GetPosition/GetDirection of each member every 2-4 s, so a
//     formation subclass is the native way to change shape.
//   Entities/AI/eAIBase.c:5871 SetMovementSpeedLimits, :5926/:5931 limit getters,
//     :241 m_eAI_Halt, :11771 eAI_SetHalt (:7598 a halt zeroes the speed limit),
//     :2028 GetThreatToSelf. Native idle looks while standing: :7795-7820 (dice) and
//     :7940-7960 (formation direction is one of the sectors).
//   3_Game/DayZExpansion_AI/Enums/AIenums.c:55 eAIMovementSpeed (WALK, JOG).
//   core Entities/ManBase/DayZPlayerImplement.c:369 Expansion_GetMovementSpeed.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1181 SurfaceGetType (the same
// call HCForage and HCW38SituationRuntime use), 3_Game/Entities/Object.c:287
// GetPosition, :517 IsAlive; 1_Core/proto/EnConvert.c:196 vector.Distance;
// EnString.c:223 string.Hash, :113 IndexOf; EnMath.c:17 DEG2RAD, :16 RAD2DEG,
// :331 Sin, :343 Cos, :379 Acos, :305 Sqrt, :427 Floor, :540 Clamp;
// 3_Game/tools/JsonFileLoader.c:69 LoadData.
// A route "junction" is a turn vertex of the group's own waypoint list: the road
// graph is only loaded for caravans, so no road topology is claimed here.
// Not observed in DayZ: runtime acceptance and the native speed/halt persistence
// are pending (runtime=PENDING).

// JSON/DTO. Every tunable lives here and in expansion-ai-formations.json.
// JsonFileLoader zero-fills absent fields, so an absent number fails validation
// by name (refused) instead of silently meaning zero.
class HCXAIFormationConfig
{
    int SchemaVersion;
    // Operator opt-out. Absent means false, so the feature is on by default.
    bool Disabled;
    int GroupsPerTick;
    int RefreshSeconds;
    int MinMembers;
    ref array<string> RoadSurfaces = new array<string>();
    float NearBuildingRadius;
    float TownRadius;
    int RegroupSeconds;
    int ThreatPercent;
    float ColumnSpacing;
    float WedgeSpacing;
    float StaggerSpacing;
    float TightSpacing;
    float SpreadSpacing;
    float RegroupSpacing;
    float ColumnLane;
    float WedgeWidth;
    float StaggerWidth;
    float SpreadDepth;
    float LookOutDegrees;
    float SpacingJitter;
    int JogPercentRoad;
    int JogPercentOpen;
    int JogPercentTown;
    int JogPercentTight;
    int JogPercentRegroup;
    int PaceEpochSeconds;
    int PauseChancePercent;
    int PauseMinSeconds;
    int PauseMaxSeconds;
    int PauseCooldownSeconds;
    float JunctionTurnDegrees;
    float JunctionRadius;
    int JunctionPauseSeconds;
}

// Pure rules: no engine reads, integer arithmetic that cannot overflow.
class HCXAIFormationRules
{
    static const int SCHEMA_VERSION = 1;
    static const int MODE_COLUMN = 0;
    static const int MODE_WEDGE = 1;
    static const int MODE_STAGGER = 2;
    static const int MODE_TIGHT = 3;
    static const int MODE_SPREAD = 4;
    static const int MODE_REGROUP = 5;
    // Prime below sqrt(2^31): h * h stays inside a signed 32-bit int.
    static const int MODULUS = 46337;
    static const int MAX_SURFACES = 8;
    static const int MAX_SURFACE_LENGTH = 32;

    static string RangeProblem(string field, float value, float low, float high)
    {
        if (value >= low && value <= high) { return ""; }
        return field + " out of range " + low.ToString() + ".." + high.ToString();
    }

    static string ConfigProblem(HCXAIFormationConfig cfg)
    {
        if (!cfg) { return "config missing"; }
        if (cfg.SchemaVersion != HCXAIFormationRules.SCHEMA_VERSION) { return "SchemaVersion must be 1"; }
        string problem = HCXAIFormationRules.RangeProblem("GroupsPerTick", cfg.GroupsPerTick, 1, 8);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("RefreshSeconds", cfg.RefreshSeconds, 2, 120);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("MinMembers", cfg.MinMembers, 2, 12);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("NearBuildingRadius", cfg.NearBuildingRadius, 2.0, 100.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("TownRadius", cfg.TownRadius, 10.0, 500.0);
        if (problem != "") { return problem; }
        if (cfg.TownRadius < cfg.NearBuildingRadius) { return "TownRadius below NearBuildingRadius"; }
        problem = HCXAIFormationRules.RangeProblem("RegroupSeconds", cfg.RegroupSeconds, 5, 300);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("ThreatPercent", cfg.ThreatPercent, 5, 100);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("ColumnSpacing", cfg.ColumnSpacing, 1.0, 30.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("WedgeSpacing", cfg.WedgeSpacing, 1.0, 30.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("StaggerSpacing", cfg.StaggerSpacing, 1.0, 30.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("TightSpacing", cfg.TightSpacing, 1.0, 30.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("SpreadSpacing", cfg.SpreadSpacing, 1.0, 40.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("RegroupSpacing", cfg.RegroupSpacing, 1.0, 30.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("ColumnLane", cfg.ColumnLane, 0.0, 4.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("WedgeWidth", cfg.WedgeWidth, 0.2, 3.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("StaggerWidth", cfg.StaggerWidth, 0.1, 2.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("SpreadDepth", cfg.SpreadDepth, 0.0, 1.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("LookOutDegrees", cfg.LookOutDegrees, 0.0, 120.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("SpacingJitter", cfg.SpacingJitter, 0.0, 0.5);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("JogPercentRoad", cfg.JogPercentRoad, 0, 100);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("JogPercentOpen", cfg.JogPercentOpen, 0, 100);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("JogPercentTown", cfg.JogPercentTown, 0, 100);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("JogPercentTight", cfg.JogPercentTight, 0, 100);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("JogPercentRegroup", cfg.JogPercentRegroup, 0, 100);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("PaceEpochSeconds", cfg.PaceEpochSeconds, 10, 900);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("PauseChancePercent", cfg.PauseChancePercent, 0, 100);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("PauseMinSeconds", cfg.PauseMinSeconds, 1, 60);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("PauseMaxSeconds", cfg.PauseMaxSeconds, 1, 120);
        if (problem != "") { return problem; }
        if (cfg.PauseMaxSeconds < cfg.PauseMinSeconds) { return "PauseMaxSeconds below PauseMinSeconds"; }
        problem = HCXAIFormationRules.RangeProblem("PauseCooldownSeconds", cfg.PauseCooldownSeconds, 10, 1800);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("JunctionTurnDegrees", cfg.JunctionTurnDegrees, 20.0, 150.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("JunctionRadius", cfg.JunctionRadius, 2.0, 40.0);
        if (problem != "") { return problem; }
        problem = HCXAIFormationRules.RangeProblem("JunctionPauseSeconds", cfg.JunctionPauseSeconds, 1, 60);
        if (problem != "") { return problem; }
        array<string> surfaces = cfg.RoadSurfaces;
        if (!surfaces || surfaces.Count() > HCXAIFormationRules.MAX_SURFACES) { return "RoadSurfaces must list at most 8 prefixes"; }
        foreach (string prefix : surfaces)
        {
            if (prefix == "" || prefix.Length() > HCXAIFormationRules.MAX_SURFACE_LENGTH) { return "RoadSurfaces entries must be 1..32 characters"; }
        }
        return "";
    }

    // Site-stable seed. Hash is native and noncryptographic; the mask keeps it
    // non-negative so the later modulo arithmetic is identical everywhere.
    static int SeedOf(string identity)
    {
        int hashed = identity.Hash();
        return hashed & 2147483647;
    }

    static int Mix(int seed, int salt)
    {
        int x = seed % 32749;
        int y = salt % 32749;
        if (x < 0) { x = x + 32749; }
        if (y < 0) { y = y + 32749; }
        int h = (x * 7919 + y * 3331 + 13) % HCXAIFormationRules.MODULUS;
        h = (h * h + 1597) % HCXAIFormationRules.MODULUS;
        h = (h * 24593 + 79) % HCXAIFormationRules.MODULUS;
        return h;
    }

    static float Unit(int seed, int salt)
    {
        float mixed = HCXAIFormationRules.Mix(seed, salt);
        return mixed / HCXAIFormationRules.MODULUS;
    }

    static float SignedUnit(int seed, int salt)
    {
        return HCXAIFormationRules.Unit(seed, salt) * 2.0 - 1.0;
    }

    // Under fire spreads, right after contact regroups, then the ground decides.
    static int Context(bool combat, bool regroup, bool road, float houseDistance, float nearRadius, float townRadius)
    {
        if (combat) { return HCXAIFormationRules.MODE_SPREAD; }
        if (regroup) { return HCXAIFormationRules.MODE_REGROUP; }
        if (road) { return HCXAIFormationRules.MODE_COLUMN; }
        if (houseDistance >= 0.0 && houseDistance <= nearRadius) { return HCXAIFormationRules.MODE_TIGHT; }
        if (houseDistance >= 0.0 && houseDistance <= townRadius) { return HCXAIFormationRules.MODE_STAGGER; }
        return HCXAIFormationRules.MODE_WEDGE;
    }

    static float Spacing(HCXAIFormationConfig cfg, int mode)
    {
        if (mode == HCXAIFormationRules.MODE_COLUMN) { return cfg.ColumnSpacing; }
        if (mode == HCXAIFormationRules.MODE_STAGGER) { return cfg.StaggerSpacing; }
        if (mode == HCXAIFormationRules.MODE_TIGHT) { return cfg.TightSpacing; }
        if (mode == HCXAIFormationRules.MODE_SPREAD) { return cfg.SpreadSpacing; }
        if (mode == HCXAIFormationRules.MODE_REGROUP) { return cfg.RegroupSpacing; }
        return cfg.WedgeSpacing;
    }

    static float WingSide(int index)
    {
        if (index % 2 == 1) { return 1.0; }
        return -1.0;
    }

    static float WingRank(int index)
    {
        return Math.Floor((index + 1) * 0.5);
    }

    static float BaseX(HCXAIFormationConfig cfg, int mode, int index)
    {
        if (index < 1) { return 0.0; }
        float spacing = HCXAIFormationRules.Spacing(cfg, mode);
        float side = HCXAIFormationRules.WingSide(index);
        float rank = HCXAIFormationRules.WingRank(index);
        if (mode == HCXAIFormationRules.MODE_COLUMN) { return side * cfg.ColumnLane; }
        if (mode == HCXAIFormationRules.MODE_STAGGER || mode == HCXAIFormationRules.MODE_TIGHT) { return side * spacing * cfg.StaggerWidth; }
        if (mode == HCXAIFormationRules.MODE_SPREAD) { return side * rank * spacing; }
        return side * rank * spacing * cfg.WedgeWidth;
    }

    static float BaseZ(HCXAIFormationConfig cfg, int mode, int index)
    {
        if (index < 1) { return 0.0; }
        float spacing = HCXAIFormationRules.Spacing(cfg, mode);
        float rank = HCXAIFormationRules.WingRank(index);
        if (mode == HCXAIFormationRules.MODE_SPREAD) { return -rank * spacing * cfg.SpreadDepth; }
        if (mode == HCXAIFormationRules.MODE_WEDGE || mode == HCXAIFormationRules.MODE_REGROUP) { return -rank * spacing; }
        return -index * spacing;
    }

    // Bounded personal offset: at most SpacingJitter of the context spacing per
    // axis. The leader (index 0) is the formation origin and never jitters.
    static float SlotX(HCXAIFormationConfig cfg, int mode, int index, int seed)
    {
        if (index < 1) { return 0.0; }
        float jitter = cfg.SpacingJitter * HCXAIFormationRules.Spacing(cfg, mode);
        return HCXAIFormationRules.BaseX(cfg, mode, index) + HCXAIFormationRules.SignedUnit(seed, index * 2) * jitter;
    }

    static float SlotZ(HCXAIFormationConfig cfg, int mode, int index, int seed)
    {
        if (index < 1) { return 0.0; }
        float jitter = cfg.SpacingJitter * HCXAIFormationRules.Spacing(cfg, mode);
        return HCXAIFormationRules.BaseZ(cfg, mode, index) + HCXAIFormationRules.SignedUnit(seed, index * 2 + 1) * jitter;
    }

    // Idle look direction in the formation frame: members face outward on their
    // own wing (the native idle-look dice pick this direction some of the time).
    static float LookDegrees(HCXAIFormationConfig cfg, int mode, int index)
    {
        if (index < 1 || mode == HCXAIFormationRules.MODE_REGROUP) { return 0.0; }
        float side = HCXAIFormationRules.WingSide(index);
        if (mode == HCXAIFormationRules.MODE_COLUMN) { return side * cfg.LookOutDegrees * 0.5; }
        return side * cfg.LookOutDegrees;
    }

    static int JogPercent(HCXAIFormationConfig cfg, int mode)
    {
        if (mode == HCXAIFormationRules.MODE_COLUMN) { return cfg.JogPercentRoad; }
        if (mode == HCXAIFormationRules.MODE_STAGGER) { return cfg.JogPercentTown; }
        if (mode == HCXAIFormationRules.MODE_TIGHT) { return cfg.JogPercentTight; }
        if (mode == HCXAIFormationRules.MODE_REGROUP) { return cfg.JogPercentRegroup; }
        return cfg.JogPercentOpen;
    }

    // Walk/jog mix: a seeded per-member roll that changes only when the pace epoch does.
    static bool IsJog(HCXAIFormationConfig cfg, int mode, int seed, int index, int epoch)
    {
        float roll = HCXAIFormationRules.Unit(seed, index * 131 + epoch * 7 + 1) * 100.0;
        return roll < HCXAIFormationRules.JogPercent(cfg, mode);
    }

    // Turn angle at corner b of the route a -> b -> c on the ground plane.
    static float TurnDegrees(float ax, float az, float bx, float bz, float cx, float cz)
    {
        float ux = bx - ax;
        float uz = bz - az;
        float vx = cx - bx;
        float vz = cz - bz;
        float lu = Math.Sqrt(ux * ux + uz * uz);
        float lv = Math.Sqrt(vx * vx + vz * vz);
        if (lu < 0.01 || lv < 0.01) { return 0.0; }
        float cosine = (ux * vx + uz * vz) / (lu * lv);
        cosine = Math.Clamp(cosine, -1.0, 1.0);
        return Math.Acos(cosine) * Math.RAD2DEG;
    }

    static bool IsJunction(HCXAIFormationConfig cfg, float turn)
    {
        return turn >= cfg.JunctionTurnDegrees;
    }

    static bool PauseRoll(HCXAIFormationConfig cfg, int seed, int salt)
    {
        float roll = HCXAIFormationRules.Unit(seed, salt * 3 + 11) * 100.0;
        return roll < cfg.PauseChancePercent;
    }

    static int PauseSeconds(HCXAIFormationConfig cfg, int seed, int salt)
    {
        float span = cfg.PauseMaxSeconds - cfg.PauseMinSeconds + 1;
        int offset = Math.Floor(HCXAIFormationRules.Unit(seed, salt * 5 + 3) * span);
        return cfg.PauseMinSeconds + offset;
    }

    static bool IsRoadSurface(HCXAIFormationConfig cfg, string surface)
    {
        // Surface type names are short material ids; IndexOf is only trusted on text of at most 1 KB.
        if (surface == "" || surface.Length() > 1024) { return false; }
        array<string> prefixes = cfg.RoadSurfaces;
        if (!prefixes) { return false; }
        foreach (string prefix : prefixes)
        {
            if (prefix != "" && surface.IndexOf(prefix) == 0) { return true; }
        }
        return false;
    }
}

// The group's own formation. Expansion asks it for each member's slot and idle
// look direction (eAIGroup.c:816-855); the mode is switched by the controller.
class HCXAIStyleFormation : eAIFormation
{
    protected ref HCXAIFormationConfig m_HCConfig;
    protected int m_HCMode = 1;
    protected int m_HCSeed;

    void HCConfigure(HCXAIFormationConfig config, int seed)
    {
        m_HCConfig = config;
        m_HCSeed = seed;
        // Seeded jitter replaces the native per-refresh random looseness.
        HCXExpansionBridge.HCFormationSetLooseness(this, 0.0);
    }

    void HCSetMode(int mode)
    {
        m_HCMode = mode;
    }

    int HCMode()
    {
        return m_HCMode;
    }

    override vector GetPosition(int member_no)
    {
        if (!m_HCConfig) { return vector.Zero; }
        float x = HCXAIFormationRules.SlotX(m_HCConfig, m_HCMode, member_no, m_HCSeed);
        float z = HCXAIFormationRules.SlotZ(m_HCConfig, m_HCMode, member_no, m_HCSeed);
        return Vector(x, 0, z);
    }

    override vector GetDirection(int member_no)
    {
        if (!m_HCConfig) { return vector.Forward; }
        float angle = HCXAIFormationRules.LookDegrees(m_HCConfig, m_HCMode, member_no) * Math.DEG2RAD;
        return Vector(Math.Sin(angle), 0, Math.Cos(angle));
    }
}

// Per-group runtime record, kept on the site state. Weak pointers only for
// engine objects: the group owns its formation, the group owns its members.
class HCXAIGroupStyle
{
    eAIGroup GroupRef;
    HCXAIStyleFormation FormRef;
    ref array<eAIBase> Halted = new array<eAIBase>();
    int Seed;
    int Evals;
    int NextEvalAt;
    int NextPauseAt;
    int PauseUntil;
    int RegroupUntil;
    int Mode = -1;
    int PaceEpoch;
    int PaceEpochStart;
    int LastJunction = -1;
    bool Foreign;
    // True only while our own formation is installed on the group.
    bool Styled;
}

modded class HCXAISiteState
{
    ref HCXAIGroupStyle HCStyle;
}

class HCXAIFormationLoader
{
    static const string FILE = "expansion-ai-formations.json";
    protected static string s_Problem;

    static string Problem()
    {
        return s_Problem;
    }

    // Profile copy first (operator edits survive), the shipped default otherwise.
    static HCXAIFormationConfig Load()
    {
        s_Problem = "";
        HCProfileDefaults.Ensure(HCXAIFormationLoader.FILE, HCXAIDefaults.Shipped());
        string path = HCProfileDefaults.Resolve(HCXAIFormationLoader.FILE, HCXAIDefaults.Shipped());
        string text = HCProfileDefaults.ReadText(path);
        if (text == "")
        {
            s_Problem = "config_unreadable";
            return null;
        }
        string error;
        HCXAIFormationConfig config;
        if (!JsonFileLoader<HCXAIFormationConfig>.LoadData(text, config, error) || !config)
        {
            s_Problem = "config_parse_failed";
            return null;
        }
        return config;
    }
}

// A cursor over the site director's states, a few groups per tick, charged to the
// shared core budget. Groups that are not due cost a field compare only.
class HCXAIFormationController
{
    // Freshness cadence of the HC-1 owner (its source age limit is 60 s).
    static const int OBSERVE_SECONDS = 10;
    protected bool m_Enabled;
    protected bool m_Closed;
    protected bool m_Requested;
    protected int m_Cursor;
    protected int m_Refused;
    protected int m_Worked;
    protected int m_Pauses;
    protected int m_Junctions;
    protected int m_ObserveAt;
    protected string m_Refusal;
    protected string m_ConfigProblem;
    protected ref HCXAIFormationConfig m_Config;
    protected ref HCOperationalOwner m_Owner;
    protected ref array<ref HCXAIGroupStyle> m_Holding = new array<ref HCXAIGroupStyle>();

    void Open(HCXAIFormationConfig config, string loadProblem, bool encountersOn)
    {
        m_Config = config;
        m_Closed = false;
        m_Enabled = false;
        m_Cursor = 0;
        m_Refusal = "";
        m_ConfigProblem = "";
        if (!m_Owner) { m_Owner = HCOperationalContributors.HCRegisterOwner("hcx-formations"); }
        m_Requested = encountersOn;
        if (config && config.Disabled) { m_Requested = false; }
        if (!config)
        {
            m_ConfigProblem = loadProblem;
            if (m_ConfigProblem == "") { m_ConfigProblem = "config_unreadable"; }
        }
        if (config) { m_ConfigProblem = HCXAIFormationRules.ConfigProblem(config); }
        string note = "ok";
        if (m_ConfigProblem != "") { note = m_ConfigProblem; }
        Print(HCV2Admission.Line("Formations", m_Requested, "formation-movement-style", false) + " config=" + note + " runtime=PENDING");
        m_Enabled = m_Requested && m_ConfigProblem == "";
    }

    // Releases every pause this controller set. The formation stays installed:
    // the AI keep a valid group shape and the groups end with the site.
    void Close()
    {
        m_Closed = true;
        m_Enabled = false;
        m_Cursor = 0;
        int now = HCWorldClock.UTC();
        while (m_Holding.Count() > 0)
        {
            ReleaseStyle(m_Holding[0], now);
            m_Holding.Remove(0);
        }
    }

    protected void HCRefuse(string reason)
    {
        if (m_Refusal == reason) { return; }
        m_Refusal = reason;
        Print("[HC Plan] Formations state=refused refusal=" + reason + " runtime=PENDING");
    }

    HCOperationalStatus HCGetOperationalStatus()
    {
        HCOperationalStatus status = new HCOperationalStatus;
        if (!m_Requested) { status.HCPublish("off", "operator_disabled_or_encounters_off"); return status; }
        if (m_ConfigProblem != "") { status.HCPublish("refused", "config_" + m_ConfigProblem); return status; }
        if (m_Closed) { status.HCPublish("off", "closed"); return status; }
        int live = LiveCount();
        if (live > 0 && m_Refusal != "") { status.HCPublish("degraded", "cached_" + m_Refusal); return status; }
        if (live > 0) { status.HCPublish("ready", "live_groups_styled"); return status; }
        if (m_Refusal != "") { status.HCPublish("degraded", "no_live_group_" + m_Refusal); return status; }
        status.HCPublish("requested", "no_group_styled_yet");
        return status;
    }

    // Groups that currently carry our installed formation: not completed, still
    // the same group instance, formation not replaced. Derived on demand so a
    // completed or lost group stops counting at once.
    protected int LiveCount()
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return 0; }
        array<ref HCXAISiteState> states = director.States();
        if (!states) { return 0; }
        int live = 0;
        for (int i = 0; i < states.Count(); i++)
        {
            HCXAISiteState state = states[i];
            if (!state || state.Completed || !state.Patrol || !state.Patrol.m_Group) { continue; }
            HCXAIGroupStyle style = state.HCStyle;
            if (!style || !style.Styled || style.Foreign) { continue; }
            if (style.GroupRef != state.Patrol.m_Group) { continue; }
            live++;
        }
        return live;
    }

    protected void Observe()
    {
        if (!m_Owner) { return; }
        int now = GetGame().GetTickTime();
        if (now < m_ObserveAt) { return; }
        m_ObserveAt = now + HCXAIFormationController.OBSERVE_SECONDS;
        m_Owner.HCObserve(m_Requested, HCGetOperationalStatus(), GetGame().GetTickTime());
        int cap = 0;
        if (m_Config) { cap = m_Config.GroupsPerTick; }
        string exception = "bounded_cursor";
        if (m_Worked == 0) { exception = "no_work"; }
        m_Owner.HCCounters(m_Worked, cap, m_Refused, exception, GetGame().GetTickTime());
    }

    void Step()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        Observe();
        if (!m_Enabled || m_Closed) { return; }
        m_Worked = 0;
        int now = HCWorldClock.UTC();
        // Hot pass: a halted AI must never stand under fire, so holds are
        // checked every tick whatever the cursor does.
        ReleasePass(now);
        array<Man> players = HCPerfPlayers.HCGet();
        if (!players || players.Count() == 0) { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director || director.Phase() != "run") { return; }
        array<ref HCXAISiteState> states = director.States();
        if (!states || states.Count() == 0) { return; }
        int count = states.Count();
        m_Cursor = m_Cursor % count;
        int scanned = 0;
        while (scanned < count && m_Worked < m_Config.GroupsPerTick)
        {
            HCXAISiteState state = states[m_Cursor];
            if (!Due(state, now))
            {
                m_Cursor = (m_Cursor + 1) % count;
                scanned++;
                continue;
            }
            // A refused request keeps the cursor on this group for the next tick.
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_FORMATION, 1)) { return; }
            m_Cursor = (m_Cursor + 1) % count;
            scanned++;
            m_Worked++;
            StepGroup(state, now);
        }
    }

    protected bool Due(HCXAISiteState state, int now)
    {
        if (!state || state.Completed || !state.Patrol) { return false; }
        if (!state.Patrol.m_Group || state.Patrol.m_HCPendingMembers > 0) { return false; }
        if (!state.HCStyle) { return true; }
        return now >= state.HCStyle.NextEvalAt;
    }

    protected void ReleasePass(int now)
    {
        int held = 0;
        while (held < m_Holding.Count())
        {
            HCXAIGroupStyle style = m_Holding[held];
            if (HoldEnded(style, now))
            {
                ReleaseStyle(style, now);
                m_Holding.Remove(held);
            }
            else { held++; }
        }
    }

    protected bool HoldEnded(HCXAIGroupStyle style, int now)
    {
        if (now >= style.PauseUntil) { return true; }
        eAIGroup group = style.GroupRef;
        if (!group || HCXExpansionBridge.HCGroupIsInCombat(group)) { return true; }
        for (int i = 0; i < style.Halted.Count(); i++)
        {
            eAIBase ai = style.Halted[i];
            if (ai && HCXExpansionBridge.HCBaseGetThreatToSelf(ai) >= m_Config.ThreatPercent * 0.01) { return true; }
        }
        return false;
    }

    protected void ReleaseStyle(HCXAIGroupStyle style, int now)
    {
        for (int i = 0; i < style.Halted.Count(); i++)
        {
            eAIBase ai = style.Halted[i];
            if (ai) { HCXExpansionBridge.HCBaseSetHalt(ai, false); }
        }
        style.Halted.Clear();
        style.PauseUntil = 0;
        style.NextPauseAt = now + m_Config.PauseCooldownSeconds;
    }

    protected void ForgetStyle(HCXAISiteState state)
    {
        HCXAIGroupStyle style = state.HCStyle;
        if (!style) { return; }
        int found = m_Holding.Find(style);
        if (found >= 0)
        {
            ReleaseStyle(style, HCWorldClock.UTC());
            m_Holding.Remove(found);
        }
        state.HCStyle = null;
    }

    protected string SurfaceAt(vector at)
    {
        string surface;
        GetGame().SurfaceGetType(at[0], at[2], surface);
        return surface;
    }

    protected int ContextOf(HCXAISiteState state, vector at, bool combat, bool regroup)
    {
        bool road = false;
        if (!combat && !regroup) { road = HCXAIFormationRules.IsRoadSurface(m_Config, SurfaceAt(at)); }
        float house = -1.0;
        if (state.HouseObject) { house = vector.Distance(at, state.HouseObject.GetPosition()); }
        return HCXAIFormationRules.Context(combat, regroup, road, house, m_Config.NearBuildingRadius, m_Config.TownRadius);
    }

    protected void StepGroup(HCXAISiteState state, int now)
    {
        eAIGroup group = state.Patrol.m_Group;
        if (HCXExpansionBridge.HCGroupCount(group) < 1)
        {
            ForgetStyle(state);
            return;
        }
        DayZPlayerImplement leader = HCXExpansionBridge.HCGroupGetFormationLeader(group);
        if (!leader || !leader.IsAlive()) { return; }
        HCXAIGroupStyle style = state.HCStyle;
        if (!style || style.GroupRef != group)
        {
            ForgetStyle(state);
            HCXAIGroupStyle fresh = new HCXAIGroupStyle();
            fresh.GroupRef = group;
            string identity = state.ProposalId;
            if (identity == "" && state.Site) { identity = state.Site.Id; }
            fresh.Seed = HCXAIFormationRules.SeedOf(identity);
            state.HCStyle = fresh;
            style = fresh;
        }
        style.NextEvalAt = now + m_Config.RefreshSeconds;
        style.Evals++;
        bool combat = HCXExpansionBridge.HCGroupIsInCombat(group);
        if (combat) { style.RegroupUntil = now + m_Config.RegroupSeconds; }
        bool regroup = false;
        if (!combat && now < style.RegroupUntil) { regroup = true; }
        vector at = leader.GetPosition();
        int mode = ContextOf(state, at, combat, regroup);
        if (HCXExpansionBridge.HCGroupCount(group) >= m_Config.MinMembers) { ApplyFormation(group, style, mode); }
        style.Mode = mode;
        if (combat) { return; }
        ApplyPace(group, style, mode, now);
        if (regroup || mode == HCXAIFormationRules.MODE_SPREAD) { return; }
        ConsiderPause(group, leader, style, at, now);
    }

    protected void ApplyFormation(eAIGroup group, HCXAIGroupStyle style, int mode)
    {
        if (!style.FormRef)
        {
            HCXAIStyleFormation fresh = new HCXAIStyleFormation();
            fresh.HCConfigure(m_Config, style.Seed);
            HCXExpansionBridge.HCGroupSetFormation(group, fresh);
            style.FormRef = fresh;
            style.Styled = true;
        }
        else if (HCXExpansionBridge.HCGroupGetFormation(group) != style.FormRef)
        {
            // Another owner installed its own formation: never fight it.
            style.Styled = false;
            if (!style.Foreign)
            {
                style.Foreign = true;
                m_Refused++;
                HCRefuse("formation_replaced");
            }
            return;
        }
        style.FormRef.HCSetMode(mode);
    }

    protected void ApplyPace(eAIGroup group, HCXAIGroupStyle style, int mode, int now)
    {
        if (now >= style.PaceEpochStart + m_Config.PaceEpochSeconds)
        {
            style.PaceEpoch++;
            style.PaceEpochStart = now;
        }
        for (int i = 0; i < HCXExpansionBridge.HCGroupCount(group); i++)
        {
            eAIBase ai = eAIBase.Cast(HCXExpansionBridge.HCGroupGetMember(group, i));
            if (!ai || !HCXExpansionBridge.HCBaseIsAlive(ai)) { continue; }
            int speed = eAIMovementSpeed.WALK;
            if (HCXAIFormationRules.IsJog(m_Config, mode, style.Seed, i, style.PaceEpoch)) { speed = eAIMovementSpeed.JOG; }
            // The under-threat limit is passed through unchanged.
            if (HCXExpansionBridge.HCBaseGetMovementSpeedLimit(ai) != speed) { HCXExpansionBridge.HCBaseSetMovementSpeedLimits(ai, speed, HCXExpansionBridge.HCBaseGetMovementSpeedLimitUnderThreat(ai)); }
        }
    }

    protected void ConsiderPause(eAIGroup group, DayZPlayerImplement leader, HCXAIGroupStyle style, vector at, int now)
    {
        if (style.Halted.Count() > 0 || now < style.NextPauseAt) { return; }
        if (leader.Expansion_GetMovementSpeed() <= 0.0) { return; }
        if (ThreatFelt(group)) { return; }
        int seconds = 0;
        int junction = JunctionIndex(group, at, style.LastJunction);
        if (junction == -2) { return; }
        if (junction >= 0)
        {
            style.LastJunction = junction;
            seconds = m_Config.JunctionPauseSeconds;
        }
        else
        {
            style.LastJunction = -1;
            if (HCXAIFormationRules.PauseRoll(m_Config, style.Seed, style.Evals)) { seconds = HCXAIFormationRules.PauseSeconds(m_Config, style.Seed, style.Evals); }
        }
        if (seconds < 1) { return; }
        if (BeginPause(group, style, seconds, now) && junction >= 0) { m_Junctions++; }
    }

    // Never start a pause on a group that already feels a threat: the hold pass
    // would only release it a tick later and a halted AI ignores threat
    // (eAIBase.c:7598). eAIBase.c:2028 GetThreatToSelf.
    protected bool ThreatFelt(eAIGroup group)
    {
        for (int t = 0; t < HCXExpansionBridge.HCGroupCount(group); t++)
        {
            eAIBase watcher = eAIBase.Cast(HCXExpansionBridge.HCGroupGetMember(group, t));
            if (watcher && HCXExpansionBridge.HCBaseIsAlive(watcher) && HCXExpansionBridge.HCBaseGetThreatToSelf(watcher) >= m_Config.ThreatPercent * 0.01) { return true; }
        }
        return false;
    }

    // Halts only members whose native halt is not already set by something else.
    protected bool BeginPause(eAIGroup group, HCXAIGroupStyle style, int seconds, int now)
    {
        for (int i = 0; i < HCXExpansionBridge.HCGroupCount(group); i++)
        {
            eAIBase ai = eAIBase.Cast(HCXExpansionBridge.HCGroupGetMember(group, i));
            if (!ai || !HCXExpansionBridge.HCBaseIsAlive(ai) || ai.m_eAI_Halt) { continue; }
            HCXExpansionBridge.HCBaseSetHalt(ai, true);
            style.Halted.Insert(ai);
        }
        if (style.Halted.Count() < 1)
        {
            // Every member already carries a halt set elsewhere: take over nothing.
            m_Refused++;
            HCRefuse("halt_owned_elsewhere");
            return false;
        }
        style.PauseUntil = now + seconds;
        m_Holding.Insert(style);
        m_Pauses++;
        return true;
    }

    // -1: no turn vertex in reach. -2: in reach, already paused for this visit.
    // Otherwise the waypoint index of the turn vertex the leader is at. The
    // current index and the one before it are both checked because it is not
    // observed whether the patrol advances the index on arrival or after it.
    protected int JunctionIndex(eAIGroup group, vector at, int lastIndex)
    {
        array<vector> route = HCXExpansionBridge.HCGroupGetWaypoints(group);
        if (!route || route.Count() < 3) { return -1; }
        int current = group.m_CurrentWaypointIndex;
        float reach = m_Config.JunctionRadius * m_Config.JunctionRadius;
        for (int k = 0; k < 2; k++)
        {
            int index = current - k;
            if (index < 1 || index > route.Count() - 2) { continue; }
            vector corner = route[index];
            float dx = at[0] - corner[0];
            float dz = at[2] - corner[2];
            if (dx * dx + dz * dz > reach) { continue; }
            float turn = HCXAIFormationRules.TurnDegrees(route[index - 1][0], route[index - 1][2], corner[0], corner[2], route[index + 1][0], route[index + 1][2]);
            if (!HCXAIFormationRules.IsJunction(m_Config, turn)) { continue; }
            if (index == lastIndex) { return -2; }
            return index;
        }
        return -1;
    }
}

// Hooks live in this addon file: modded links of the existing adapter, so no
// existing addon file changes. OnStart/OnTick/OnStop exist on the base module.
modded class HCXAIAdapter
{
    protected ref HCXAIFormationController m_HCFormations;

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (!GetGame() || !GetGame().IsServer()) { return; }
        m_HCFormations = new HCXAIFormationController();
        HCXAIFormationConfig config = HCXAIFormationLoader.Load();
        bool encounters = settings && settings.EnableEncounters;
        m_HCFormations.Open(config, HCXAIFormationLoader.Problem(), encounters);
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (m_HCFormations) { m_HCFormations.Step(); }
    }

    override void OnStop()
    {
        if (m_HCFormations) { m_HCFormations.Close(); }
        super.OnStop();
    }
}
