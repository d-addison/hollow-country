// Gun piles (#338, owner 2026-11-22/23): a gun the CE creates in the world is usually found with its own
// magazine and ammo lying beside it as a small pile (loose items, never attached or loaded).
//
// Hook: Weapon_Base extends Weapon extends InventoryItemSuper, and `typedef ItemBase InventoryItemSuper`
// (4_World/Entities/Game/Super/InventoryItem.c:4), so a gun IS an ItemBase. EEOnCECreate is declared on
// EntityAI (3_Game/Entities/EntityAI.c:1414, no parameters) and overridden by ItemBase (ItemBase.c:4111);
// Weapon_Base does not override it. It runs for entities the CE (or the debug spawner) creates as new, never
// for an entity loaded from storage (that path is AfterStoreLoad), so a reloaded gun never gets a second pile.
// Script-created guns (traders, AI loadouts, players, admin tools) never reach it either.
//
// Work: the hook only queues the gun (weak reference, cap 2048, time stamped). A 250 ms drain examines at
// most GunPilePerTick guns per call inside an HCWorkBudget slice, and only guns queued at least one second
// ago, so HCGroundCELoot (50 ms) has already shifted and snapped the gun. Per gun, one roll against
// GunPileChance, then at most one magazine (guns that take detachable magazines; random compatible type,
// random partial count) and one ammo stack (random chamberable type, random partial quantity). A gun that
// takes an internal magazine gets the ammo stack only.
//
// Placement: 0.2-0.5 m beside the gun on the same supporting surface. Each spot is tested with a horizontal
// geometry ray from the gun (stopped by any wall or prop, extended 0.12 m past the spot) and a downward ray
// whose contact must lie within 0.25 m under to 0.15 m over the gun and must not be another loose item. The
// item is created at the contact with ECE_PLACE_ON_SURFACE and verified with HCGroundSnap.Snap (support
// below, drop-only); an item that cannot be settled is deleted again. Three angles are tried per item; no
// valid spot counts `skipped`, never a forced placement.
//
// Economy: the pile items are script-created world items of CE-known classes, so they count in map like any
// loot and the CE spawns fewer loose magazines and ammo to stay at nominal. Scripts cannot query types.xml;
// the class filter is the vanilla and pack data itself (every magazine and ammo class a gun lists is a
// scope-2 item the shipped economy carries). The lead's CE census must show magazines and ammo in map
// within nominal +10% after a fresh fill; the offline nominal offset is a later step after econ r5.
//
// Native evidence, installed scripts-1.30.164289: Weapon.c GetMagazineTypeCount, GetRandomMagazineTypeName,
// GetRandomChamberableAmmoTypeName (muzzle 0); Magazine.c:68,70 GetAmmoCount, ServerSetAmmoCount, :160
// GetAmmoMax; Game.c:703 CreateObjectEx; CentralEconomy.c:38 ECE_PLACE_ON_SURFACE; DayZPhysics.c
// RaycastRVProxy; EnMath.c Cos, Sin, RandomIntInclusive, RandomFloatInclusive; EnDebug.c Print.
class HCGunPile
{
    static const int QUEUE_CAP = 2048;
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
    static const int NO_MUZZLE_LINES = 8;

    protected static ref array<ItemBase> s_Queue = new array<ItemBase>;
    protected static ref array<float> s_QueuedAt = new array<float>;
    protected static int s_Cursor;
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
    protected static int s_NoMuzzle;
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
        if (s_Queue.Count() > s_Cursor) { ScheduleDrain(); }
    }

    static bool IsRunning()
    {
        return s_Configured && s_Enabled;
    }

    // Called from the CE create hook only. Cheap: one append, no world query.
    static void Enqueue(ItemBase gun)
    {
        if (!GetGame() || !GetGame().IsServer() || !gun) { return; }
        if (s_Configured && !s_Enabled) { return; }
        if (s_Queue.Count() - s_Cursor >= QUEUE_CAP)
        {
            s_Dropped++;
            s_Skipped++;
            return;
        }
        s_Queue.Insert(gun);
        s_QueuedAt.Insert(GetGame().GetTickTime());
        s_Queued++;
        ScheduleDrain();
        ScheduleSummary();
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
            s_Cursor = 0;
            return;
        }
        float now = GetGame().GetTickTime();
        s_Budget.HCReset(s_PerTick, HCPerfConfig.HCGet().SliceMs);
        while (s_Cursor < s_Queue.Count() && s_Budget.HCContinue())
        {
            if (now - s_QueuedAt[s_Cursor] < MIN_AGE_SECONDS) { break; }
            ItemBase gun = s_Queue[s_Cursor];
            s_Queue.Set(s_Cursor, null);
            s_Cursor++;
            ProcessGun(gun);
        }
        if (s_Cursor >= s_Queue.Count())
        {
            s_Queue.Clear();
            s_QueuedAt.Clear();
            s_Cursor = 0;
            return;
        }
        ScheduleDrain();
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
        if (Math.RandomFloatInclusive(0, 1) >= s_Chance) { return; }
        // A gun inside a site box that is still undecided (or refused) may be moved or removed later.
        if (HCSiteGuard.HCLootVerdict(gun) != HCSiteGuard.LOOT_KEEP)
        {
            s_Skipped++;
            return;
        }
        // The muzzle natives index the weapon's muzzle array without a bounds check: on a weapon with no
        // muzzle, muzzle 0 is a native crash (soak 2026-11-23, GetMagazineTypeCount(0)). Vanilla Weapon.c
        // always loops i < GetMuzzleCount() before it reads a muzzle; so does this.
        if (weapon.GetMuzzleCount() < 1)
        {
            s_Skipped++;
            s_NoMuzzle++;
            if (s_NoMuzzle <= NO_MUZZLE_LINES) { Print("[HC Loot] gun pile skip reason=no_muzzle class=" + gun.GetType()); }
            return;
        }
        string magType = "";
        if (weapon.GetMagazineTypeCount(0) > 0) { magType = weapon.GetRandomMagazineTypeName(0); }
        string ammoType = weapon.GetRandomChamberableAmmoTypeName(0);
        if (magType == "" && ammoType == "")
        {
            s_Skipped++;
            return;
        }
        vector origin = gun.GetPosition();
        float angle = Math.RandomFloatInclusive(0, Math.PI2);
        bool anyPlaced = false;
        if (magType != "")
        {
            if (PlaceOne(gun, origin, magType, angle, true)) { anyPlaced = true; }
            angle = angle + ATTEMPT_STEP;
        }
        if (ammoType != "")
        {
            if (PlaceOne(gun, origin, ammoType, angle, false)) { anyPlaced = true; }
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
    protected static bool PlaceOne(ItemBase gun, vector origin, string type, float startAngle, bool isMagazine)
    {
        float angle = startAngle;
        for (int attempt = 0; attempt < ATTEMPTS; attempt++)
        {
            float dist = Math.RandomFloatInclusive(OFFSET_MIN, OFFSET_MAX);
            vector spot;
            if (FindSpot(gun, origin, angle, dist, spot))
            {
                if (Create(type, spot, isMagazine)) { return true; }
            }
            angle = angle + ATTEMPT_STEP;
        }
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

    protected static bool Create(string type, vector spot, bool isMagazine)
    {
        Object created = GetGame().CreateObjectEx(type, spot, ECE_PLACE_ON_SURFACE);
        if (!created) { return false; }
        Magazine mag = Magazine.Cast(created);
        if (!mag)
        {
            GetGame().ObjectDelete(created);
            return false;
        }
        // Never floating: the created item must find support within 0.5 m below, else it is removed.
        if (!HCGroundSnap.Snap(mag, 0.5, 0.03, s_SnapStats))
        {
            GetGame().ObjectDelete(mag);
            return false;
        }
        int maxCount = mag.GetAmmoMax();
        if (maxCount > 1)
        {
            int low = maxCount / 5;
            if (low < 1) { low = 1; }
            int high = maxCount * 3 / 5;
            if (isMagazine) { high = maxCount * 4 / 5; }
            if (high < low) { high = low; }
            mag.ServerSetAmmoCount(Math.RandomIntInclusive(low, high));
        }
        if (isMagazine) { s_Mags++; }
        else { s_Ammo++; }
        return true;
    }

    // At most one line per 300 s and only when a number changed.
    static void Summary()
    {
        string line = "[HC Loot] gun pile queued=" + s_Queued.ToString() + " placed=" + s_Placed.ToString() + " skipped=" + s_Skipped.ToString() + " dropped=" + s_Dropped.ToString() + " mags=" + s_Mags.ToString() + " ammo=" + s_Ammo.ToString() + " no_muzzle=" + s_NoMuzzle.ToString();
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
    // CE-created guns only (see the file header): queue and return; the work runs later from the drain.
    override void EEOnCECreate()
    {
        super.EEOnCECreate();
        HCGunPile.Enqueue(this);
    }
}
