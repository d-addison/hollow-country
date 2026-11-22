// P2.1 shared infected route cache: 256 entries, least-recently-used eviction, world epoch.
// Installed scripts-1.30.164289: 3_Game/Entities/Building.c:102-139 door callbacks (OnDoorOpenStart,
// OnDoorCloseStart, OnDoorLocked, OnDoorUnlocked), 1_Core/proto/EnScript.c array Insert/Clear.
//
// An entry is (profile, 4 m start cell, 2 m goal cell) -> the FindPath polyline, or a "no route"
// verdict. Nothing is stored per tick: the arrays are sized once and entry paths are reused in
// place. Any door state change or pathgraph refresh bumps the world epoch (HCNavEpoch, 3_Game) in O(1); entries from an
// older epoch are dropped when looked up. Runtime only, never persisted, so there is no stored
// format to migrate.
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

    protected static bool s_Ready;
    protected static int s_Stamp;
    protected static ref array<int> s_FromKey;
    protected static ref array<int> s_ToKey;
    protected static ref array<int> s_Profile;
    protected static ref array<int> s_EntryEpoch;
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
        if (cell > 4095) { cell = 4095; }
        return cell;
    }

    // Plain integer keys (no shifts, no string building): cell x * 4096 + cell z.
    static int HCKey(vector position, float size)
    {
        return HCCell(position[0], size) * 4096 + HCCell(position[2], size);
    }

    static int HCEpoch() { return HCNavEpoch.HCValue(); }

    // O(1). Every door open/close/lock change and every pathgraph refresh lands here.
    static void HCInvalidate()
    {
        HCNavEpoch.HCBump();
    }

    protected static int HCFind(int profile, int fromKey, int toKey, float now)
    {
        for (int slot = 0; slot < CAPACITY; slot++)
        {
            if (s_FromKey[slot] != fromKey || s_ToKey[slot] != toKey || s_Profile[slot] != profile) { continue; }
            if (s_EntryEpoch[slot] != HCNavEpoch.HCValue()) { s_FromKey[slot] = -1; return -1; }
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
        int slot = HCFind(profile, HCKey(from, 4), HCKey(goal, 2), now);
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
        int slot = HCFind(profile, fromKey, toKey, now);
        if (slot < 0)
        {
            slot = HCVictim();
        }
        s_Stamp++;
        s_FromKey[slot] = fromKey;
        s_ToKey[slot] = toKey;
        s_Profile[slot] = profile;
        s_EntryEpoch[slot] = HCNavEpoch.HCValue();
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
            if (s_FromKey[slot] < 0 || s_EntryEpoch[slot] != HCNavEpoch.HCValue()) { return slot; }
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
        line = line + " evictions=" + s_Evictions.ToString() + " invalidations=" + HCNavEpoch.HCBumps().ToString() + " epoch=" + HCNavEpoch.HCValue().ToString();
        return line;
    }
}
