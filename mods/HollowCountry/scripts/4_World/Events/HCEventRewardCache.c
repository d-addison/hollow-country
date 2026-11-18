// Native: 3_Game/Global/Game.c:703 CreateObjectEx, :705 ObjectDelete, :1120 IsServer,
// :1176 SurfaceY; 3_Game/CE/CentralEconomy.c:30 ECE_NOLIFETIME, :31 ECE_NOPERSISTENCY_WORLD,
// :38 ECE_PLACE_ON_SURFACE; 3_Game/Systems/Inventory/Inventory.c:143 CreateEntityInCargo;
// 4_World/Entities/ItemBase/Gear/Containers/containers.c SmallProtectorCase : Container_Base.
// Barrel_ColorBase.c:15 starts closed, :87 Open, :512 requires open cargo;
// EntityAI.c:3064 SetSynchDirty (net-sync state), ItemBase.c:4124 virtual Open.
// Server-created once per site and session, AFTER the grant is journaled by HCEventRewardLedger.
// ECE_NOPERSISTENCY_WORLD (3_Game/CE/CentralEconomy.c:31 "do not save this object in world") only
// means the case container is not saved in the world. It does not cover character persistence
// (ECE_NOPERSISTENCY_CHAR, :32, deliberately not set: a case a player holds is theirs). Items a
// player takes are ordinary loot and may persist on a character across a restart while the new
// boot replenishes its per-session allowance; that overlap is accepted and bounded by the cap.
// The case keeps ECE_NOLIFETIME and is never deleted by this module once registered, so loot
// a player has dropped is never destroyed. Case cargo capacity is UNOBSERVED: a partial fill is
// kept and logged, an empty case is deleted. Local acceptance of creation is PENDING.
// Same journal/spawner protocol, separate finite allowance so the three supply
// cases keep their existing budget. Two barrels, six mission items per boot.
class HCEventPoliceRewardIO : HCEventRewardIO
{
    void HCEventPoliceRewardIO()
    {
        m_Root = "$profile:HollowCountry/Events/police-rewards";
    }
}
// Native: 3_Game/AI/AIWorld.c:122 SampleNavmeshPosition, :57 PGFilter.SetFlags;
// Game.c GetWorld().GetAIWorld(). Outdoor walkable polygons only (INSIDE excluded).
class HCEventPoliceNav
{
    static vector Sample(vector wanted, float radius)
    {
        if (!GetGame() || !GetGame().GetWorld()) { return vector.Zero; }
        AIWorld world = GetGame().GetWorld().GetAIWorld();
        if (!world) { return vector.Zero; }
        PGFilter filter = new PGFilter;
        filter.SetFlags(PGPolyFlags.WALK, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.INSIDE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        vector found;
        if (!world.SampleNavmeshPosition(wanted, radius, filter, found)) { return vector.Zero; }
        return found;
    }
}
class HCEventCacheSpawner
{
    protected static ref HCEventRewardLedger s_PoliceLedger;
    protected static ref array<ref HCEventTarget> s_PoliceTargets;

    static HCEventRewardLedger PoliceLedger()
    {
        if (!s_PoliceLedger)
        {
            HCEventRewardPool pool = new HCEventRewardPool;
            pool.MaxCaches = 2;
            pool.ItemsPerCache = 3;
            pool.Entries.Insert(HCEventRewardPools.Entry("BandageDressing", 2));
            pool.Entries.Insert(HCEventRewardPools.Entry("SodaCan_Cola", 2));
            pool.Entries.Insert(HCEventRewardPools.Entry("MetalWire", 2));
            s_PoliceLedger = new HCEventRewardLedger;
            s_PoliceLedger.Configure(new HCEventPoliceRewardIO, pool);
        }
        return s_PoliceLedger;
    }
    static HCEventTarget PoliceTarget(string missionId)
    {
        if (!s_PoliceTargets) { return null; }
        foreach (HCEventTarget target : s_PoliceTargets)
        {
            if (target.MissionId == missionId) { return target; }
        }
        return null;
    }
    static HCEventTarget CreatePolice(HCEventMission mission)
    {
        if (!HCEventSites.PoliceSupplies(mission)) { return null; }
        if (!HCEventSitesGate.Admitted() || !GetGame() || !GetGame().IsServer()) { return null; }
        if (!HCEventRuntimePolicy.MissionValid(mission, mission.WorldName)) { return null; }
        HCEventTarget existing = PoliceTarget(mission.Id);
        if (existing) { return existing; }
        // A deterministic source-derived point, not a field-surveyed placement.
        vector anchor = Vector(mission.Source[0] + 6, mission.Source[1], mission.Source[2] + 6);
        Spawn(mission, anchor, mission.ContainerClass, true);
        return PoliceTarget(mission.Id);
    }
    static HCEventTarget Create(HCEventMission mission)
    {
        if (!mission || !mission.RewardCache || mission.Family != HCEventFamily.RECOVERY) { return null; }
        if (!HCEventSitesGate.Admitted() || !GetGame() || !GetGame().IsServer()) { return null; }
        if (!HCEventRuntimePolicy.MissionValid(mission, mission.WorldName)) { return null; }
        return Spawn(mission, mission.Source, mission.ItemClass, false);
    }
    // Shared native creation path for both allowances; every creation is journaled.
    // Ready/observation use a 3D radius around Source; refuse before any journal write
    // when the point would not stay observable. Returns vector.Zero on refusal.
    static vector SpawnPosition(HCEventMission mission, vector anchor, bool police)
    {
        float height = GetGame().SurfaceY(anchor[0], anchor[2]);
        if (height != height)
        {
            if (!police) { Print("[HC Events] reward cache refused for site " + mission.SiteId + "; terrain height differs from the reviewed height"); }
            return vector.Zero;
        }
        vector position;
        if (police)
        {
            // Police Source is the station's stock mapgrouppos model origin, which stands
            // above its ground (stock neighbours sit ~5 m lower). Accept ground up to 12 m
            // below it, then take an outdoor walkable navmesh point so the barrel is not
            // inside a wall. Retries report through BindFailed's bounded (mission, reason) set.
            if (height > mission.Source[1] + 3 || height < mission.Source[1] - 12) { return vector.Zero; }
            position = HCEventPoliceNav.Sample(Vector(anchor[0], height, anchor[2]), 6);
            if (position == vector.Zero) { return vector.Zero; }
        }
        else
        {
            if (Math.AbsFloat(height - mission.Source[1]) > 6)
            {
                Print("[HC Events] reward cache refused for site " + mission.SiteId + "; terrain height differs from the reviewed height");
                return vector.Zero;
            }
            position = Vector(anchor[0], height, anchor[2]);
        }
        if (vector.DistanceSq(position, mission.Source) > mission.Radius * mission.Radius) { return vector.Zero; }
        return position;
    }
    static HCEventTarget Spawn(HCEventMission mission, vector anchor, string containerClass, bool police)
    {
        vector position = SpawnPosition(mission, anchor, police);
        if (position == vector.Zero) { return null; }
        HCEventRewardPlan plan;
        if (police) { plan = PoliceLedger().Commit(mission.SiteId); }
        else { plan = HCEventRewards.Ledger().Commit(mission.SiteId); }
        if (!plan) { return null; }
        int flags = ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD | ECE_NOLIFETIME;
        Object created = GetGame().CreateObjectEx(containerClass, position, flags);
        ItemBase cache = ItemBase.Cast(created);
        if (!cache)
        {
            if (created) { GetGame().ObjectDelete(created); }
            Print("[HC Events] reward cache creation failed; grant stays spent for this session");
            return null;
        }
        if (police)
        {
            // Native barrel cargo admission requires an open lid. Synchronize the
            // new container's state; no synthetic audio/action or forced player move.
            cache.Open();
            cache.SetSynchDirty();
        }
        int made = 0;
        foreach (string className : plan.Items)
        {
            ItemBase cargo = null;
            if (cache.GetInventory()) { cargo = ItemBase.Cast(cache.GetInventory().CreateEntityInCargo(className)); }
            if (cargo)
            {
                made = made + 1;
                if (police)
                {
                    int family = HCEventFamily.RECOVERY;
                    if (className == "SodaCan_Cola") { family = HCEventFamily.DELIVERY; }
                    if (className == "MetalWire") { family = HCEventFamily.STATIC_SALVAGE; }
                    HCEventTarget supply = new HCEventTarget;
                    supply.MissionId = mission.SiteId + "-" + family.ToString();
                    supply.Item = cargo;
                    supply.DeliveryContainer = cache;
                    if (!s_PoliceTargets) { s_PoliceTargets = new array<ref HCEventTarget>(); }
                    s_PoliceTargets.Insert(supply);
                }
            }
        }
        int wanted = plan.Items.Count();
        if (made < 1)
        {
            GetGame().ObjectDelete(cache);
            Print("[HC Events] reward cache held no content; removed, grant stays spent for this session");
            return null;
        }
        Print("[HC Events] reward cache created site " + mission.SiteId + " items " + made.ToString() + "/" + wanted.ToString());
        HCEventTarget result = new HCEventTarget;
        result.MissionId = mission.Id;
        result.Item = cache;
        result.Presence = cache;
        return result;
    }
    // Only for a cache that could not be registered; never for one a player may hold.
    static void Discard(ItemBase cache)
    {
        if (cache && !cache.IsPendingDeletion() && !cache.GetHierarchyRootPlayer() && !cache.GetHierarchyParent())
        {
            GetGame().ObjectDelete(cache);
        }
    }
}
