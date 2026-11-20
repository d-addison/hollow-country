// #279 CE-owned HC infected variants: server-side counters only.
// The HollowCountryAnims classes (HC_ZmbM_Sitter/Sleeper/Riser/Feeder/Crawler,
// spawned by the vanilla CE through db/events.xml children) report here; the
// base mod never references them. Every call is O(1) with no IO; the arrays are
// allocated once. HCInfectedVarietyModule prints one summary per window.
// Counted facts are server script observations (EEInit ran, a slot was taken,
// the scripted command became current, the native crawl command became current,
// the mind state reached ALERTED, a hit landed). They never prove client playback.
// Native API (scripts-1.30.164289): 1_Core/proto/EnScript.c:380 Count, :407 Insert;
// 1_Core/proto/EnConvert.c:30 int.ToString; 1_Core/proto/EnDebug.c:96 Print.
class HCVarietyCounters
{
    // Kinds equal the CMD_HC_POSE value; the crawler uses the vanilla graph.
    static const int KIND_SIT = 1;
    static const int KIND_SLEEP = 2;
    static const int KIND_RISER = 3;
    static const int KIND_FEED = 4;
    static const int KIND_CRAWL = 5;

    // Slots 0..5 are spawned-per-kind (0 = unknown kind).
    static const int POSED = 6;          // a MaxPosed slot was taken
    static const int PLAYING = 7;        // our scripted command became the current command
    static const int CRAWLING = 8;       // the native crawl command became the current command
    static const int REFUSED_BUDGET = 9;
    static const int REFUSED_ADMISSION = 10;
    static const int REFUSED_OPTOUT = 11;
    static const int WOKEN_MIND = 12;    // native perception: mind state reached ALERTED or higher
    static const int WOKEN_HIT = 13;     // damage landed while posed
    static const int WOKEN_OTHER = 14;   // Variety wake (fresh-queue paths, stop, cap)
    static const int RISEN = 15;         // the get-up finished and vanilla movement resumed
    static const int INTERRUPTED = 16;   // a vanilla command (hit, death, attack) replaced the pose
    static const int DELETED = 17;       // CE cleanup or death removed a held body
    static const int SLOTS = 18;
    static const int DETAIL_PRINTS = 24; // per-body detail lines per server run

    protected static ref array<int> s_Window;
    protected static ref array<int> s_Total;
    protected static int s_Held;
    protected static int s_Detail;

    protected static void HCEnsure()
    {
        if (s_Window) { return; }
        s_Window = new array<int>;
        s_Total = new array<int>;
        for (int i = 0; i < SLOTS; i++)
        {
            s_Window.Insert(0);
            s_Total.Insert(0);
        }
    }

    static void HCAdd(int slot)
    {
        if (slot < 0 || slot >= SLOTS) { return; }
        HCEnsure();
        s_Window[slot] = s_Window[slot] + 1;
        s_Total[slot] = s_Total[slot] + 1;
    }

    static void HCSpawned(int kind)
    {
        if (kind < 1 || kind > KIND_CRAWL) { kind = 0; }
        HCAdd(kind);
    }

    static void HCSetHeld(int held)
    {
        s_Held = held;
    }

    //! True for the first DETAIL_PRINTS per-body lines; the counters carry the rest.
    static bool HCDetail()
    {
        if (s_Detail >= DETAIL_PRINTS) { return false; }
        s_Detail++;
        return true;
    }

    static string HCKindName(int kind)
    {
        if (kind == KIND_SIT) { return "sit"; }
        if (kind == KIND_SLEEP) { return "sleep"; }
        if (kind == KIND_RISER) { return "riser"; }
        if (kind == KIND_FEED) { return "feed"; }
        if (kind == KIND_CRAWL) { return "crawl"; }
        return "other";
    }

    protected static string HCPart(array<int> values)
    {
        string spawned = "sit=" + values[KIND_SIT].ToString() + " sleep=" + values[KIND_SLEEP].ToString() + " riser=" + values[KIND_RISER].ToString() + " feed=" + values[KIND_FEED].ToString() + " crawl=" + values[KIND_CRAWL].ToString();
        string pose = " posed=" + values[POSED].ToString() + " playing=" + values[PLAYING].ToString() + " crawling=" + values[CRAWLING].ToString();
        string refused = " refused_budget=" + values[REFUSED_BUDGET].ToString() + " refused_admission=" + values[REFUSED_ADMISSION].ToString() + " refused_optout=" + values[REFUSED_OPTOUT].ToString();
        string woken = " woken_mind=" + values[WOKEN_MIND].ToString() + " woken_hit=" + values[WOKEN_HIT].ToString() + " woken_other=" + values[WOKEN_OTHER].ToString();
        string ended = " risen=" + values[RISEN].ToString() + " interrupted=" + values[INTERRUPTED].ToString() + " deleted=" + values[DELETED].ToString();
        return spawned + pose + refused + woken + ended;
    }

    //! One summary line; resets the window. Called once per window by the module.
    static string HCSummary(int windowSeconds)
    {
        HCEnsure();
        string line = "[HC Variety] ce_variants window=" + windowSeconds.ToString() + "s " + HCPart(s_Window) + " held=" + s_Held.ToString() + " | total " + HCPart(s_Total) + " runtime=PENDING";
        for (int i = 0; i < SLOTS; i++) { s_Window[i] = 0; }
        return line;
    }
}
