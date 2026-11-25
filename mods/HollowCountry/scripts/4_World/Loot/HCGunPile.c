// #338: CE/CE-debug creation queues a weak handle once; storage loads do not enqueue.
// Debug sessions are excluded from acceptance. Minimum age alone does not establish ground correction:
// drain waits for HCGroundCELoot's transient handled marker and the enabled site guard's built grid.
// Build 178 :177 and 179 :189 called compatibility natives in the same statement. The muzzle-count
// guard did not prevent the crash; a null resolved config entry is suspected, not proven.
// This path reads inherited config only, never weapon-instance magazine/muzzle/chamber natives.
// CE accounting remains UNVERIFIED: a positive fresh-item economy nominal is necessary, but cannot
// prove map counting. Lead acceptance needs matched fresh fills, restart and one-client evidence.
// [HC Use] count=1 is a first-use receipt, not the total; later use summaries and placed= carry totals.
// Native signatures inspected in 1.30.164289: Global/Game.c ConfigIsExisting :612,
// ConfigGetFullPath :614 (out TStringArray), ConfigGetType :546, ConfigGetTextArray :558,
// ConfigGetInt :539, ConfigGetText :449; EntityAI.c GetEconomyProfile :888;
// CentralEconomy.c CEItemProfile.GetNominal :754. Capacity is config count, never GetAmmoMax.
class HCGunPileShape
{
    ref array<string> Magazines = new array<string>;
    ref array<int> MagazineCounts = new array<int>;
    ref array<string> Ammo = new array<string>;
    ref array<int> AmmoCounts = new array<int>;
}

class HCGunPile
{
    // Soak 191: 2055 queued + 2716 dropped = 4771 arrivals. 8192 fits that entire
    // burst even before the 0.75 admission roll; deferral reuses slots, never grows the ring.
    static const int QUEUE_CAP = 8192;
    static const int MAGAZINE_LIMIT = 32;
    static const float MIN_AGE_SECONDS = 1.0;
    static const int SUMMARY_MS = 300000;
    static const float OFFSET_MIN = 0.2;
    static const float OFFSET_MAX = 0.5;
    static const float RAY_LIFT = 0.12;
    static const float RAY_EXTRA = 0.12;
    static const float SURFACE_UP = 0.15;
    static const float SURFACE_DOWN = 0.25;
    static const int ATTEMPTS = 3;
    static const float ATTEMPT_STEP = 2.1;
    static const int CACHE_CAP = 512;
    static const int COLD_PER_DRAIN = 2;

    protected static ref array<ItemBase> s_Queue = new array<ItemBase>;
    protected static ref array<float> s_QueuedAt = new array<float>;
    protected static int s_Head;
    protected static int s_Count;
    protected static int s_Cold;
    protected static ref map<string, ref HCGunPileShape> s_Shapes = new map<string, ref HCGunPileShape>;
    protected static ref map<string, string> s_Negative = new map<string, string>;
    protected static ref map<string, bool> s_Economy = new map<string, bool>;
    protected static ref map<string, int> s_Reasons = new map<string, int>;
    protected static int s_DeferredGuard;
    protected static int s_DeferredGround;
    protected static int s_DeferredCold;
    protected static ref HCWorkBudget s_Budget = new HCWorkBudget;
    protected static ref HCGroundSnapStats s_SnapStats = new HCGroundSnapStats;
    protected static bool s_Scheduled;
    protected static bool s_SummaryScheduled;
    protected static bool s_Configured;
    protected static bool s_Enabled = true;
    protected static float s_Chance = 0.75;
    protected static int s_PerTick = 4;
    protected static int s_Queued;
    protected static int s_Placed;
    protected static int s_Skipped;
    protected static int s_Mags;
    protected static int s_Ammo;
    protected static int s_Dropped;
    protected static int s_ChanceSkip;
    // Lifetime distinct-shape receipt, capped at CACHE_CAP (summary saturates at 512).
    // Unlike the resolver caches, never cleared: cache churn must not count a shape twice.
    protected static ref map<string, bool> s_TruncatedShapes = new map<string, bool>;
    protected static string s_LastSummary;

    // Module start: read the validated settings. Guns queued before this wait in the queue.
    static void Configure(bool enabled, float chance, int perTick)
    {
        s_Enabled = enabled;
        s_Chance = chance;
        if (s_Chance < 0) { s_Chance = 0; }
        if (s_Chance > 1) { s_Chance = 1; }
        s_PerTick = perTick;
        if (s_PerTick < 1) { s_PerTick = 1; }
        if (s_PerTick > 16) { s_PerTick = 16; }
        s_Configured = true;
        if (s_Count > 0) { ScheduleDrain(); }
    }

    static bool IsRunning()
    {
        return s_Configured && s_Enabled;
    }

    // Called from the CE create hook only. One chance roll and at most one append; no world query.
    static void Enqueue(Weapon_Base gun)
    {
        if (!GetGame() || !GetGame().IsServer() || !gun) { return; }
        if (s_Configured && !s_Enabled) { return; }
        if (gun.m_HCGunPileQueued) { return; }
        gun.m_HCGunPileQueued = true;
        // 1_Core/proto/EnMath.c:106 RandomFloatInclusive (1.30.164289); roll once,
        // before occupying a slot. Deferred guns retain this decision and their original age.
        ScheduleSummary();
        if (Math.RandomFloatInclusive(0, 1) >= s_Chance)
        {
            s_ChanceSkip++;
            return;
        }
        if (s_Count >= QUEUE_CAP)
        {
            s_Dropped++;
            s_Skipped++;
            return;
        }
        if (s_Queue.Count() == 0)
        {
            s_Queue.Resize(QUEUE_CAP);
            s_QueuedAt.Resize(QUEUE_CAP);
        }
        int tail = (s_Head + s_Count) % QUEUE_CAP;
        s_Queue.Set(tail, gun);
        s_QueuedAt.Set(tail, GetGame().GetTickTime());
        s_Count++;
        s_Queued++;
        ScheduleDrain();
    }

    protected static void ScheduleDrain(int delayMs = 250)
    {
        if (s_Scheduled || !GetGame()) { return; }
        s_Scheduled = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCGunPile.Drain, delayMs, false);
    }

    protected static void ScheduleSummary()
    {
        if (s_SummaryScheduled || !GetGame()) { return; }
        s_SummaryScheduled = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCGunPile.Summary, SUMMARY_MS, true);
    }

    static void Drain()
    {
        s_Scheduled = false;
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (!s_Configured)
        {
            // The module has not started yet: keep the queue (capped), look again in a second.
            ScheduleDrain(1000);
            return;
        }
        if (!s_Enabled)
        {
            s_Queue.Clear();
            s_QueuedAt.Clear();
            s_Head = 0;
            s_Count = 0;
            return;
        }
        if (!HCSiteGuard.HCLootReady())
        {
            s_DeferredGuard++;
            ScheduleDrain();
            return;
        }
        float now = GetGame().GetTickTime();
        s_Cold = 0;
        int available = s_Count;
        s_Budget.HCReset(s_PerTick, HCPerfConfig.HCGet().SliceMs);
        while (available > 0 && s_Count > 0 && s_Budget.HCContinue())
        {
            available--;
            if (now - s_QueuedAt[s_Head] < MIN_AGE_SECONDS) { break; }
            ItemBase gun = s_Queue[s_Head];
            float queuedAt = s_QueuedAt[s_Head];
            s_Queue.Set(s_Head, null);
            s_Head = (s_Head + 1) % QUEUE_CAP;
            s_Count--;
            bool defer = false;
            if (gun && !gun.IsPendingDeletion() && !gun.GetHierarchyParent())
            {
                if (!gun.m_HCGroundCEHandled) { s_DeferredGround++; defer = true; }
                else
                {
                    string key = gun.GetType();
                    key.ToLower();
                    if (!s_Shapes.Contains(key) && !s_Negative.Contains(key) && s_Cold >= COLD_PER_DRAIN)
                    {
                        s_DeferredCold++;
                        defer = true;
                    }
                }
            }
            if (defer)
            {
                int tail = (s_Head + s_Count) % QUEUE_CAP;
                s_Queue.Set(tail, gun);
                s_QueuedAt.Set(tail, queuedAt);
                s_Count++;
            }
            else { ProcessGun(gun); }
        }
        if (s_Count > 0) { ScheduleDrain(); }
    }

    // Named config-ancestry refusal list, including non-firearm Weapon_Base tools.
    // Crossbow is intentionally absent: its loose bolts follow the normal ammunition chain.
    // M79 is absent too (owner, 2026-11-24): it may get a non-lethal 40mm round; LethalRound drops
    // the explosive and gas rounds entry by entry.
    protected static bool SpecialFamily(string name)
    {
        if (name == "flaregun" || name == "flaregun_base") { return true; }
        if (name == "dartgun" || name == "dartgun_base") { return true; }
        if (name == "shockpistol" || name == "shockpistol_base") { return true; }
        if (name == "trumpet" || name == "trumpet_base") { return true; }
        if (name == "ammo_dartsyringe" || name == "ammo_flare") { return true; }
        return name == "nonlethalcore";
    }

    // 40mm explosive and gas rounds never lie beside a launcher; smoke rounds may.
    protected static bool LethalRound(string self, TStringArray chain)
    {
        if (self == "ammo_40mm_explosive" || self == "ammo_40mm_chemgas") { return true; }
        return chain.Find("ammo_40mm_explosive") >= 0 || chain.Find("ammo_40mm_chemgas") >= 0;
    }

    protected static bool ValidToken(string token)
    {
        if (token.Length() < 1 || token.Length() > 64) { return false; }
        for (int i = 0; i < token.Length(); i++)
        {
            string ch = token.Substring(i, 1);
            if (ch == " " || ch == "\t" || ch == "\\" || ch == "/" || ch == "\r" || ch == "\n") { return false; }
        }
        return true;
    }

    protected static bool ValidMagazineToken(string token)
    {
        if (token.Length() > 64 || !ValidToken(token)) { return false; }
        token.ToLower();
        return token.IndexOf("_test") < 0;
    }

    protected static void Refuse(string reason, string type)
    {
        int count;
        s_Reasons.Find(reason, count);
        count++;
        s_Reasons.Set(reason, count);
        if (count <= 8) { Print("[HC Loot] gun pile refuse reason=" + reason + " class=" + type); }
    }

    protected static HCGunPileShape RejectShape(string key, string reason)
    {
        if (s_Negative.Count() >= CACHE_CAP) { s_Negative.Clear(); }
        s_Negative.Set(key, reason);
        return null;
    }

    // Missing arrays mean no entries. Only magazine candidates may use a prefix;
    // muzzle/chamber validation must see the entire bounded list or refuse it.
    // 3_Game/Global/Game.c:612/:546/:558; 1_Core/proto/EnScript.c:476 Resize
    // (1.30.164289): shrinking discards only the tail, retaining config order.
    protected static bool ReadList(string path, int limit, out TStringArray values, out bool truncated, bool allowTruncate = false)
    {
        truncated = false;
        values = new TStringArray;
        if (!GetGame().ConfigIsExisting(path)) { return true; }
        if (GetGame().ConfigGetType(path) != CT_ARRAY) { return false; }
        GetGame().ConfigGetTextArray(path, values);
        if (values.Count() <= limit) { return true; }
        if (!allowTruncate) { return false; }
        values.Resize(limit);
        truncated = true;
        return true;
    }

    protected static void RecordMagazineTruncation(string key)
    {
        if (s_TruncatedShapes.Contains(key) || s_TruncatedShapes.Count() >= CACHE_CAP) { return; }
        s_TruncatedShapes.Set(key, true);
        if (s_TruncatedShapes.Count() == 1)
        {
            Print("[HC Loot] gun pile truncate reason=magazines_limit limit=" + MAGAZINE_LIMIT.ToString());
        }
    }

    protected static bool ValidMuzzles(string root, TStringArray rootAmmo)
    {
        TStringArray muzzles;
        bool truncated;
        if (!ReadList(root + " muzzles", 8, muzzles, truncated)) { return false; }
        if (!GetGame().ConfigIsExisting(root + " muzzles")) { return true; }
        if (muzzles.Count() == 0) { return false; }
        // weapons_pistols.pbo, magnum/config.bin (pbo_config.py inspection): Magnum_Base
        // has this, SecondMuzzle .. SixthMuzzle. SecondMuzzle has magazines[]={},
        // chamberableFrom[]={Ammo_357}; the other four inherit it. Root also accepts
        // Mag_357Speedloader_6Rnd. Accept chamber subsets, never separate launcher ammo.
        for (int u = 0; u < muzzles.Count(); u++)
        {
            string muzzle = muzzles[u];
            if (!ValidToken(muzzle)) { return false; }
            muzzle.ToLower();
            if (u == 0)
            {
                if (muzzle != "this") { return false; }
                continue;
            }
            if (muzzle == "this") { return false; }
            string child = root + " " + muzzle;
            if (!GetGame().ConfigIsExisting(child)) { return false; }
            TStringArray childMags;
            TStringArray childAmmo;
            if (!ReadList(child + " magazines", 0, childMags, truncated)) { return false; }
            if (!ReadList(child + " chamberableFrom", 16, childAmmo, truncated)) { return false; }
            if (childAmmo.Count() == 0) { return false; }
            for (int a = 0; a < childAmmo.Count(); a++)
            {
                string round = childAmmo[a];
                if (!ValidToken(round)) { return false; }
                round.ToLower();
                bool shared = false;
                for (int r = 0; r < rootAmmo.Count(); r++)
                {
                    string rootRound = rootAmmo[r];
                    rootRound.ToLower();
                    if (round == rootRound) { shared = true; break; }
                }
                if (!shared) { return false; }
            }
        }
        return true;
    }

    protected static bool ReadChain(string path, out TStringArray chain)
    {
        chain = new TStringArray;
        if (!GetGame().ConfigIsExisting(path)) { return false; }
        GetGame().ConfigGetFullPath(path, chain);
        if (chain.Count() < 1 || chain.Count() > 64) { return false; }
        for (int i = 0; i < chain.Count(); i++)
        {
            string name = chain[i];
            name.ToLower();
            chain.Set(i, name);
        }
        return true;
    }

    protected static bool ReadItem(string type, bool loose, out string bullet, out int capacity, out bool special)
    {
        special = false;
        if (!ValidToken(type)) { return false; }
        string path = "CfgMagazines " + type;
        TStringArray chain;
        if (!ReadChain(path, chain)) { return false; }
        for (int c = 0; c < chain.Count(); c++)
        {
            if (SpecialFamily(chain[c])) { special = true; return false; }
        }
        string self = type;
        self.ToLower();
        if (LethalRound(self, chain)) { return false; }
        if (HCConfigHelper.GetInt(path + " scope", 0) != 2) { return false; }
        bool ammunition = chain.Find("ammunition_base") >= 0;
        if (loose && !ammunition) { return false; }
        if (!loose && (ammunition || chain.Find("magazine_base") < 0)) { return false; }
        bullet = HCConfigHelper.GetText(path + " ammo", "");
        if (!ValidToken(bullet) || !GetGame().ConfigIsExisting("CfgAmmo " + bullet)) { return false; }
        capacity = HCConfigHelper.GetInt(path + " count", 0);
        if (capacity < 1 || (!loose && capacity <= 1)) { return false; }
        bullet.ToLower();
        return true;
    }

    protected static HCGunPileShape ResolveShape(string type)
    {
        string key = type;
        key.ToLower();
        HCGunPileShape cached;
        if (s_Shapes.Find(key, cached)) { return cached; }
        if (s_Negative.Contains(key)) { return null; }
        s_Cold++;
        if (!ValidToken(type)) { return RejectShape(key, "shape_token"); }
        string root = "CfgWeapons " + type;
        if (!GetGame().ConfigIsExisting(root)) { return RejectShape(key, "missing_root"); }
        TStringArray ancestry;
        if (!ReadChain(root, ancestry)) { return RejectShape(key, "shape_chain"); }
        for (int n = 0; n < ancestry.Count(); n++)
        {
            if (SpecialFamily(ancestry[n])) { return RejectShape(key, "special_family"); }
        }
        TStringArray magazines;
        TStringArray ammo;
        bool truncated;
        if (!ReadList(root + " chamberableFrom", 16, ammo, truncated)) { return RejectShape(key, "shape_chamberable"); }
        if (!ValidMuzzles(root, ammo)) { return RejectShape(key, "shape_muzzles"); }
        // SNAFU_Guns_02.pbo: SNAFUMDAR_Base and its nine variants inherit 33 entries.
        // Keep the first 32 in config order, then validate candidates individually as before.
        if (!ReadList(root + " magazines", MAGAZINE_LIMIT, magazines, truncated, true)) { return RejectShape(key, "shape_magazines"); }
        if (truncated) { RecordMagazineTruncation(key); }
        HCGunPileShape shape = new HCGunPileShape;
        map<string, bool> bullets = new map<string, bool>;
        for (int a = 0; a < ammo.Count(); a++)
        {
            string ammoBullet;
            int ammoCount;
            bool ammoSpecial;
            bool ammoOk = ReadItem(ammo[a], true, ammoBullet, ammoCount, ammoSpecial);
            if (ammoSpecial) { return RejectShape(key, "special_family"); }
            if (!ammoOk) { continue; }
            shape.Ammo.Insert(ammo[a]);
            shape.AmmoCounts.Insert(ammoCount);
            bullets.Set(ammoBullet, true);
        }
        for (int m = 0; m < magazines.Count(); m++)
        {
            if (!ValidMagazineToken(magazines[m])) { continue; }
            string magBullet;
            int magCount;
            bool magSpecial;
            bool magOk = ReadItem(magazines[m], false, magBullet, magCount, magSpecial);
            if (magSpecial) { return RejectShape(key, "special_family"); }
            if (!magOk || !bullets.Contains(magBullet)) { continue; }
            shape.Magazines.Insert(magazines[m]);
            shape.MagazineCounts.Insert(magCount);
        }
        if (shape.Ammo.Count() == 0 && shape.Magazines.Count() == 0) { return RejectShape(key, "no_compatible"); }
        if (s_Shapes.Count() >= CACHE_CAP) { s_Shapes.Clear(); }
        s_Shapes.Set(key, shape);
        return shape;
    }

    protected static void ProcessGun(ItemBase gun)
    {
        if (!gun || gun.IsPendingDeletion() || gun.GetHierarchyParent())
        {
            s_Skipped++;
            return;
        }
        Weapon_Base weapon = Weapon_Base.Cast(gun);
        if (!weapon)
        {
            s_Skipped++;
            return;
        }
        // A gun inside a site box that is still undecided (or refused) may be moved or removed later.
        if (HCSiteGuard.HCLootVerdict(gun) != HCSiteGuard.LOOT_KEEP)
        {
            s_Skipped++;
            Refuse("site_verdict", gun.GetType());
            return;
        }
        HCGunPileShape shape = ResolveShape(gun.GetType());
        if (!shape)
        {
            string key = gun.GetType();
            key.ToLower();
            string reason;
            s_Negative.Find(key, reason);
            Refuse(reason, gun.GetType());
            s_Skipped++;
            return;
        }
        vector origin = gun.GetPosition();
        float angle = Math.RandomFloatInclusive(0, Math.PI2);
        bool anyPlaced = false;
        if (shape.Magazines.Count() > 0)
        {
            int m = Math.RandomInt(0, shape.Magazines.Count());
            if (PlaceOne(gun, origin, shape.Magazines[m], shape.MagazineCounts[m], angle, true)) { anyPlaced = true; }
            angle = angle + ATTEMPT_STEP;
        }
        if (shape.Ammo.Count() > 0)
        {
            int a = Math.RandomInt(0, shape.Ammo.Count());
            if (PlaceOne(gun, origin, shape.Ammo[a], shape.AmmoCounts[a], angle, false)) { anyPlaced = true; }
        }
        if (!anyPlaced)
        {
            s_Skipped++;
            return;
        }
        s_Placed++;
        HCModuleReadiness.HCUse("GunPile", "piles-placed");
    }

    // Tries up to ATTEMPTS angles for one pile item; true when it stands on the surface beside the gun.
    protected static bool PlaceOne(ItemBase gun, vector origin, string type, int capacity, float startAngle, bool isMagazine)
    {
        float angle = startAngle;
        for (int attempt = 0; attempt < ATTEMPTS; attempt++)
        {
            float dist = Math.RandomFloatInclusive(OFFSET_MIN, OFFSET_MAX);
            vector spot;
            if (FindSpot(gun, origin, angle, dist, spot))
            {
                // Once creation is attempted, never retry this item (cleanup must not duplicate loot).
                return Create(type, spot, capacity, isMagazine);
            }
            angle = angle + ATTEMPT_STEP;
        }
        Refuse("no_spot", type);
        return false;
    }

    protected static bool FindSpot(ItemBase gun, vector origin, float angle, float dist, out vector spot)
    {
        float dx = Math.Cos(angle);
        float dz = Math.Sin(angle);
        // Horizontal ray just above the gun's resting level: a wall, shelf upright or prop stops the spot.
        vector rayFrom = Vector(origin[0], origin[1] + RAY_LIFT, origin[2]);
        float reach = dist + RAY_EXTRA;
        vector rayTo = Vector(origin[0] + dx * reach, origin[1] + RAY_LIFT, origin[2] + dz * reach);
        if (RayBlocked(rayFrom, rayTo, gun)) { return false; }
        float x = origin[0] + dx * dist;
        float z = origin[2] + dz * dist;
        float surfaceY;
        if (!SurfaceBelow(x, origin[1], z, gun, surfaceY)) { return false; }
        spot = Vector(x, surfaceY, z);
        return true;
    }

    protected static bool RayBlocked(vector from, vector to, Object ignored)
    {
        RaycastRVParams query = new RaycastRVParams(from, to, ignored);
        query.type = ObjIntersectGeom;
        query.flags = CollisionFlags.NEARESTCONTACT;
        array<ref RaycastRVResult> hits = new array<ref RaycastRVResult>;
        if (!DayZPhysics.RaycastRVProxy(query, hits)) { return false; }
        return hits.Count() > 0;
    }

    // Surface contact under the spot within the band around the gun's level. Another loose item under the
    // ray (not terrain, not a building) refuses the spot: piles never stack on top of loot.
    protected static bool SurfaceBelow(float x, float gunY, float z, Object ignored, out float surfaceY)
    {
        vector start = Vector(x, gunY + SURFACE_UP, z);
        vector finish = Vector(x, gunY - SURFACE_DOWN, z);
        RaycastRVParams query = new RaycastRVParams(start, finish, ignored);
        query.type = ObjIntersectGeom;
        query.flags = CollisionFlags.NEARESTCONTACT;
        array<ref RaycastRVResult> hits = new array<ref RaycastRVResult>;
        if (!DayZPhysics.RaycastRVProxy(query, hits) || hits.Count() == 0) { return false; }
        RaycastRVResult hit = hits[0];
        if (hit.obj && hit.obj.IsInherited(ItemBase)) { return false; }
        if (hit.pos[1] > start[1] || hit.pos[1] < finish[1]) { return false; }
        surfaceY = hit.pos[1];
        return true;
    }

    protected static bool Create(string type, vector spot, int maxCount, bool isMagazine)
    {
        string key = type;
        key.ToLower();
        bool eligible;
        bool known = s_Economy.Find(key, eligible);
        if (known && !eligible) { Refuse("no_economy", type); return false; }
        if (!known && s_Economy.Count() >= CACHE_CAP) { Refuse("economy_cache_full", type); return false; }
        Object created = GetGame().CreateObjectEx(type, spot, ECE_PLACE_ON_SURFACE);
        if (!created) { Refuse("create_failed", type); return false; }
        Magazine mag = Magazine.Cast(created);
        if (!mag)
        {
            GetGame().ObjectDelete(created);
            Refuse("not_magazine", type);
            return false;
        }
        if (!known)
        {
            CEItemProfile profile = mag.GetEconomyProfile();
            eligible = profile && profile.GetNominal() > 0;
            s_Economy.Set(key, eligible);
            if (!eligible)
            {
                GetGame().ObjectDelete(mag);
                Refuse("no_economy", type);
                return false;
            }
        }
        // Never floating: the created item must find support within 0.5 m below, else it is removed.
        if (!HCGroundSnap.Snap(mag, 0.5, 0.03, s_SnapStats))
        {
            GetGame().ObjectDelete(mag);
            Refuse("no_support", type);
            return false;
        }
        int quantity = 1;
        if (maxCount > 1)
        {
            int low = maxCount / 5;
            if (low < 1) { low = 1; }
            int high = maxCount / 5 * 3;
            if (isMagazine) { high = maxCount / 5 * 4; }
            if (high < low) { high = low; }
            quantity = Math.RandomIntInclusive(low, high);
        }
        mag.ServerSetAmmoCount(quantity);
        if (isMagazine) { s_Mags++; }
        else { s_Ammo++; }
        return true;
    }

    // At most one line per 300 s and only when a number changed.
    static void Summary()
    {
        string line = "[HC Loot] gun pile queued=" + s_Queued.ToString() + " placed=" + s_Placed.ToString() + " skipped=" + s_Skipped.ToString() + " dropped=" + s_Dropped.ToString() + " mags=" + s_Mags.ToString() + " ammo=" + s_Ammo.ToString();
        line += " chance_skip=" + s_ChanceSkip.ToString() + " magazine_truncated_shapes=" + s_TruncatedShapes.Count().ToString();
        line += " deferred_guard=" + s_DeferredGuard.ToString() + " deferred_ground=" + s_DeferredGround.ToString() + " deferred_cold=" + s_DeferredCold.ToString();
        // Reasons have a fixed vocabulary; this bounded summary is emitted outside per-item loops.
        foreach (string reason, int count : s_Reasons) { line += " " + reason + "=" + count.ToString(); }
        if (line == s_LastSummary) { return; }
        s_LastSummary = line;
        Print("" + line);
    }

    static string StartLine()
    {
        return "[HC Loot] gun pile started enabled=" + HCV2Admission.OnOff(s_Enabled) + " chance=" + s_Chance.ToString() + " per_tick=" + s_PerTick.ToString() + " cap=" + QUEUE_CAP.ToString() + " runtime=PENDING";
    }
}

class HCGunPileModule : HCModule
{
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected bool m_Running;

    override string GetName() { return "GunPile"; }

    override bool IsEnabled(HCSettings settings)
    {
        bool enabled = settings && settings.GunPileEnabled;
        // OnStart is not called for a disabled module: tell the queue it will never be drained.
        if (!enabled) { HCGunPile.Configure(false, 0, 1); }
        return enabled;
    }

    override void RegisterUses()
    {
        HCModuleReadiness.HCRegisterUse(GetName(), "piles-placed");
    }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Running, "", "", "gun_pile_hook_active");
        return m_Operational;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || m_Running) { return; }
        if (!settings || !settings.GunPileEnabled) { return; }
        HCGunPile.Configure(true, settings.GunPileChance, settings.GunPilePerTick);
        m_Running = true;
        Print(HCGunPile.StartLine());
    }

    override void OnStop()
    {
        m_Running = false;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        HCGunPileModule gunPileModule = new HCGunPileModule;
        Register(gunPileModule);
    }
}

modded class Weapon_Base
{
    bool m_HCGunPileQueued;
    // CE-created guns only (see the file header): queue and return; the work runs later from the drain.
    override void EEOnCECreate()
    {
        super.EEOnCECreate();
        HCGunPile.Enqueue(this);
    }
}
