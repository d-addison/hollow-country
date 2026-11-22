// WD-2A-9 pack route sharing: a pack member (or a neighbouring pack) heading for the same 2 m goal
// cell with the same filter profile reuses a route that was found from a start within 32 m, instead
// of spending another FindPath. At most 32 entries, written round-robin, 90 s lifetime, and the
// whole cache is stale after any HCNavRouteCache epoch change (door state, pathgraph refresh).
// The caller still checks length and endpoint against its own start and goal, so a shared route can
// only ever answer "reachable" when that member's own geometry agrees. Runtime only; nothing stored.
class HCHordeFlowCache
{
    static const int CAPACITY = 32;
    static const float SHARE_RADIUS = 32;
    static const float LIFETIME_SECONDS = 90;

    protected static bool s_Ready;
    protected static int s_Next;
    protected static int s_Shares;
    protected static int s_Stores;
    protected static ref array<vector> s_Start;
    protected static ref array<int> s_Goal;
    protected static ref array<int> s_Profile;
    protected static ref array<int> s_Epoch;
    protected static ref array<float> s_Stored;
    protected static ref array<ref TVectorArray> s_Paths;

    protected static void HCInit()
    {
        if (s_Ready) { return; }
        s_Ready = true;
        s_Start = new array<vector>;
        s_Goal = new array<int>;
        s_Profile = new array<int>;
        s_Epoch = new array<int>;
        s_Stored = new array<float>;
        s_Paths = new array<ref TVectorArray>;
        for (int slot = 0; slot < CAPACITY; slot++)
        {
            s_Start.Insert(Vector(0, 0, 0));
            s_Goal.Insert(-1);
            s_Profile.Insert(0);
            s_Epoch.Insert(0);
            s_Stored.Insert(0);
            s_Paths.Insert(null);
        }
    }

    // True and `path` filled when a live shared route starts within 32 m of `from`.
    static bool HCShare(int profile, vector from, vector goal, TVectorArray path)
    {
        HCInit();
        if (!path) { return false; }
        path.Clear();
        int goalKey = HCNavRouteCache.HCKey(goal, 2);
        float now = GetGame().GetTickTime();
        for (int slot = 0; slot < CAPACITY; slot++)
        {
            if (s_Goal[slot] != goalKey || s_Profile[slot] != profile) { continue; }
            if (s_Epoch[slot] != HCNavRouteCache.HCEpoch() || now - s_Stored[slot] > LIFETIME_SECONDS) { continue; }
            if (vector.DistanceSq(s_Start[slot], from) > SHARE_RADIUS * SHARE_RADIUS) { continue; }
            TVectorArray stored = s_Paths[slot];
            if (!stored || stored.Count() < 2) { continue; }
            for (int point = 0; point < stored.Count(); point++) { path.Insert(stored[point]); }
            s_Shares++;
            HCModuleReadiness.HCUse("Infected", "flow_reuse");
            return true;
        }
        return false;
    }

    static void HCStore(int profile, vector from, vector goal, TVectorArray path)
    {
        HCInit();
        if (!path || path.Count() < 2 || path.Count() > HCNavRouteCache.MAX_POINTS) { return; }
        int slot = s_Next;
        s_Next = (s_Next + 1) % CAPACITY;
        s_Start[slot] = from;
        s_Goal[slot] = HCNavRouteCache.HCKey(goal, 2);
        s_Profile[slot] = profile;
        s_Epoch[slot] = HCNavRouteCache.HCEpoch();
        s_Stored[slot] = GetGame().GetTickTime();
        TVectorArray stored = s_Paths[slot];
        if (!stored)
        {
            stored = new TVectorArray;
            s_Paths[slot] = stored;
        }
        stored.Clear();
        for (int point = 0; point < path.Count(); point++) { stored.Insert(path[point]); }
        s_Stores++;
    }

    static string HCStats()
    {
        return "flow_cache shares=" + s_Shares.ToString() + " stores=" + s_Stores.ToString();
    }
}
