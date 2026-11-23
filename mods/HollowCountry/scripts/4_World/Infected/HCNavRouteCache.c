// P2.1 shared infected route cache: 256 entries, least-recently-used eviction, world epoch.
// Installed scripts-1.30.164289: 3_Game/Entities/Building.c:102-139 door callbacks (OnDoorOpenStart,
// OnDoorCloseStart, OnDoorLocked, OnDoorUnlocked), 1_Core/proto/EnScript.c array Insert/Clear.
//
// An entry is (profile, 4 m start cell, 2 m goal cell) -> the FindPath polyline, or a "no route"
// verdict. Nothing is stored per tick: the arrays are sized once and entry paths are reused in
// place. A pathgraph refresh bumps the world epoch (HCNavEpoch, 3_Game) in O(1) and entries from an
// older epoch are dropped when looked up. A door state change bumps only the regional epoch around the
// building (HCNavRegionEpoch): an entry is dropped only when a door near its route (start, polyline,
// goal box) changed after it was stored. The cell key is only a lookup index: the stored goal point is
// compared too, and a goal more than 2 m off the stored one is a miss (the caller re-paths), never a
// refusal. Runtime only, never persisted, so there is no stored format to migrate.
class HCNavRouteCache
{
    static const int CAPACITY = 256;
    static const int MAX_POINTS = 32;
    static const int HIT_NONE = 0;
    static const int HIT_ROUTE = 1;
    static const int HIT_NO_ROUTE = 2;
    // A "no route" verdict is retried after this long even without an epoch change.
    static const float NEGATIVE_SECONDS = 120;
    static const float ENTRY_SECONDS = 600;
    // A cached goal further than this from the asked goal is a miss (Reachable accepts a route end within 2 m).
    static const float GOAL_TOLERANCE = 2;
    // Key = cell x * 8192 + cell z with each cell clamped to 0..8191: at 2 m that covers 16382 m (Chernarus is
    // 15360 m). The largest key is 8191 * 8192 + 8191 = 67108863, far below the int maximum 2147483647.
    static const int KEY_CELLS = 8192;
    static const int KEY_CELL_MAX = 8191;

    protected static bool s_Ready;
    protected static int s_Stamp;
    protected static ref array<int> s_FromKey;
    protected static ref array<int> s_ToKey;
    protected static ref array<int> s_Profile;
    protected static ref array<int> s_EntryEpoch;
    protected static ref array<int> s_EntryRegion;
    protected static ref array<int> s_Box;
    protected static ref array<vector> s_Goal;
    protected static ref array<int> s_Used;
    protected static ref array<float> s_Stored;
    protected static ref array<bool> s_Negative;
    protected static ref array<ref TVectorArray> s_Paths;
    protected static int s_Hits;
    protected static int s_NegativeHits;
    protected static int s_Misses;
    protected static int s_Evictions;

    protected static void HCInit()
    {
        if (s_Ready) { return; }
        s_Ready = true;
        s_FromKey = new array<int>;
        s_ToKey = new array<int>;
        s_Profile = new array<int>;
        s_EntryEpoch = new array<int>;
        s_EntryRegion = new array<int>;
        s_Box = new array<int>;
        s_Goal = new array<vector>;
        s_Used = new array<int>;
        s_Stored = new array<float>;
        s_Negative = new array<bool>;
        s_Paths = new array<ref TVectorArray>;
        for (int slot = 0; slot < CAPACITY; slot++)
        {
            s_FromKey.Insert(-1);
            s_ToKey.Insert(-1);
            s_Profile.Insert(0);
            s_EntryEpoch.Insert(0);
            s_EntryRegion.Insert(0);
            s_Goal.Insert(Vector(0, 0, 0));
            s_Box.Insert(0);
            s_Box.Insert(0);
            s_Box.Insert(0);
            s_Box.Insert(0);
            s_Used.Insert(0);
            s_Stored.Insert(0);
            s_Negative.Insert(false);
            s_Paths.Insert(null);
        }
    }

    protected static int HCCell(float value, float size)
    {
        int cell = Math.Floor(value / size);
        if (cell < 0) { cell = 0; }
        if (cell > KEY_CELL_MAX) { cell = KEY_CELL_MAX; }
        return cell;
    }

    // Plain integer keys (no shifts, no string building): cell x * 8192 + cell z (max 67108863, fits an int).
    static int HCKey(vector position, float size)
    {
        return HCCell(position[0], size) * KEY_CELLS + HCCell(position[2], size);
    }

    static int HCEpoch() { return HCNavEpoch.HCValue(); }

    // O(1). Every pathgraph refresh lands here (door changes bump the regional epoch instead).
    static void HCInvalidate()
    {
        HCNavEpoch.HCBump();
    }

    // An entry is current while the world epoch is unchanged and no door near its route changed since it was stored.
    protected static bool HCCurrent(int slot)
    {
        if (s_EntryEpoch[slot] != HCNavEpoch.HCValue()) { return false; }
        return HCNavRegionEpoch.HCLive(s_EntryRegion[slot], s_Box, slot * 4);
    }

    protected static int HCFind(int profile, int fromKey, int toKey, vector goal, float now)
    {
        for (int slot = 0; slot < CAPACITY; slot++)
        {
            if (s_FromKey[slot] != fromKey || s_ToKey[slot] != toKey || s_Profile[slot] != profile) { continue; }
            if (vector.DistanceSq(s_Goal[slot], goal) > GOAL_TOLERANCE * GOAL_TOLERANCE) { continue; }
            if (!HCCurrent(slot)) { s_FromKey[slot] = -1; return -1; }
            float age = now - s_Stored[slot];
            if (age > ENTRY_SECONDS || (s_Negative[slot] && age > NEGATIVE_SECONDS)) { s_FromKey[slot] = -1; return -1; }
            return slot;
        }
        return -1;
    }

    // HIT_ROUTE fills `path` (caller-allocated, cleared here); HIT_NO_ROUTE leaves it empty.
    static int HCLookup(int profile, vector from, vector goal, TVectorArray path)
    {
        HCInit();
        if (!path) { return HIT_NONE; }
        path.Clear();
        float now = GetGame().GetTickTime();
        int slot = HCFind(profile, HCKey(from, 4), HCKey(goal, 2), goal, now);
        if (slot < 0)
        {
            s_Misses++;
            return HIT_NONE;
        }
        s_Stamp++;
        s_Used[slot] = s_Stamp;
        s_Hits++;
        HCModuleReadiness.HCUse("Infected", "route_cache_hit");
        if (s_Negative[slot])
        {
            s_NegativeHits++;
            return HIT_NO_ROUTE;
        }
        TVectorArray stored = s_Paths[slot];
        for (int point = 0; point < stored.Count(); point++) { path.Insert(stored[point]); }
        return HIT_ROUTE;
    }

    // Store a polyline (route) or, with a null/empty path and negative=true, a "no route" verdict.
    static void HCStore(int profile, vector from, vector goal, TVectorArray path, bool negative)
    {
        HCInit();
        if (!negative && (!path || path.Count() < 2 || path.Count() > MAX_POINTS)) { return; }
        float now = GetGame().GetTickTime();
        int fromKey = HCKey(from, 4);
        int toKey = HCKey(goal, 2);
        int slot = HCFind(profile, fromKey, toKey, goal, now);
        if (slot < 0)
        {
            slot = HCVictim();
        }
        s_Stamp++;
        s_FromKey[slot] = fromKey;
        s_ToKey[slot] = toKey;
        s_Profile[slot] = profile;
        s_EntryEpoch[slot] = HCNavEpoch.HCValue();
        s_EntryRegion[slot] = HCNavRegionEpoch.HCNow();
        s_Goal[slot] = goal;
        HCNavRegionEpoch.HCBox(from, goal, path, s_Box, slot * 4);
        s_Used[slot] = s_Stamp;
        s_Stored[slot] = now;
        s_Negative[slot] = negative;
        TVectorArray stored = s_Paths[slot];
        if (!stored)
        {
            stored = new TVectorArray;
            s_Paths[slot] = stored;
        }
        stored.Clear();
        if (negative) { return; }
        for (int point = 0; point < path.Count(); point++) { stored.Insert(path[point]); }
    }

    // A free or stale slot first, else the least recently used one.
    protected static int HCVictim()
    {
        int oldest = 0;
        int oldestStamp = 2147483647;
        for (int slot = 0; slot < CAPACITY; slot++)
        {
            if (s_FromKey[slot] < 0 || !HCCurrent(slot)) { return slot; }
            if (s_Used[slot] < oldestStamp)
            {
                oldestStamp = s_Used[slot];
                oldest = slot;
            }
        }
        s_Evictions++;
        return oldest;
    }

    static string HCStats()
    {
        string line = "route_cache hits=" + s_Hits.ToString() + " negative=" + s_NegativeHits.ToString() + " misses=" + s_Misses.ToString();
        line = line + " evictions=" + s_Evictions.ToString() + " invalidations=" + HCNavEpoch.HCBumps().ToString() + " door_regions=" + HCNavRegionEpoch.HCBumps().ToString() + " epoch=" + HCNavEpoch.HCValue().ToString();
        return line;
    }
}
