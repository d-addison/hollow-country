// #147 physical spoils: expose existing CE/camp stock in place. No item mint,
// move, quantity write, grant prompt or deletion. Taking loot is native inventory.
// Items a player takes are ordinary loot; native persistence remains authoritative.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:930 GetObjectsAtPosition3D,
// :1120 IsServer; Entities/Object.c:215 IsPendingDeletion, :287 GetPosition;
// Entities/EntityAI.c:882/885 hierarchy; Inventory.c:138 GetCargo;
// 3_Game/Systems/Inventory/Cargo.c:28 GetItemCount, :33 GetItem;
// Object.c:467 GetType; EnConvert.c:210 DistanceSq; EnScript.c:380/407 Count/Insert.
// Existing journal API remains for older callers; this path never replenishes
// an allowance on restart. A real container can be referenced twice, never cloned.
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
            HCEventPoliceRewardIO policeIO = new HCEventPoliceRewardIO;
            s_PoliceLedger.Configure(policeIO, pool);
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
    // Legacy terrain helper retained for caller compatibility. Physical stock
    // lookup never materializes at this point or alters its native owner.
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
        if (!mission || !GetGame() || !GetGame().IsServer()) { return null; }
        if (!HCEventSitesGate.Admitted()) { return null; }
        if (!HCPhysicalEnabled()) { return null; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        if (!policy) { return null; }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATIONS, 8)) { return null; }
        array<Object> nearby = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(anchor, mission.Radius, nearby, proxies);
        int remaining = policy.PhysicalScanObjects;
        foreach (Object candidate : nearby)
        {
            if (remaining <= 0) { break; }
            remaining = remaining - 1;
            ItemBase cache = ItemBase.Cast(candidate);
            if (!HCPhysicalStock(cache) || cache.GetType() != containerClass) { continue; }
            if (vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius) { continue; }
            if (police)
            {
                CargoBase cargo = cache.GetInventory().GetCargo();
                int count = cargo.GetItemCount();
                if (count > policy.PhysicalScanCargo) { count = policy.PhysicalScanCargo; }
                int index = 0;
                while (index < count)
                {
                    ItemBase item = ItemBase.Cast(cargo.GetItem(index));
                    index = index + 1;
                    if (!item || item.IsRuined()) { continue; }
                    int family = 0;
                    if (item.GetType() == "BandageDressing") { family = HCEventFamily.RECOVERY; }
                    if (item.GetType() == "SodaCan_Cola") { family = HCEventFamily.DELIVERY; }
                    if (item.GetType() == "MetalWire") { family = HCEventFamily.STATIC_SALVAGE; }
                    if (family == 0) { continue; }
                    string targetId = mission.SiteId + "-" + family.ToString();
                    if (PoliceTarget(targetId)) { continue; }
                    HCEventTarget supply = new HCEventTarget;
                    supply.MissionId = targetId;
                    supply.Item = item;
                    supply.DeliveryContainer = cache;
                    if (!s_PoliceTargets) { s_PoliceTargets = new array<ref HCEventTarget>; }
                    s_PoliceTargets.Insert(supply);
                }
            }
            HCEventTarget result = new HCEventTarget;
            result.MissionId = mission.Id;
            result.Item = cache;
            result.Presence = cache;
            return result;
        }
        HCPhysicalPending();
        return null;
    }

    protected static bool s_PhysicalPendingPrinted;
    protected static bool s_PhysicalAdmissionPrinted;
    static bool HCPhysicalEnabled()
    {
        bool enabled = !FileExist("$profile:HollowCountry/acceptance/w38_rewards.disable");
        if (!s_PhysicalAdmissionPrinted)
        {
            s_PhysicalAdmissionPrinted = true;
            Print(HCV2Admission.Line("PhysicalSpoils", enabled, "w38_rewards", false) + " runtime=PENDING");
        }
        return enabled;
    }

    static void HCPhysicalPending()
    {
        if (s_PhysicalPendingPrinted) { return; }
        s_PhysicalPendingPrinted = true;
        Print("[HC Events] physical_stock=waiting EXISTING_CE_CAMP_STOCK_PENDING runtime=PENDING");
    }

    static bool HCPhysicalStock(ItemBase cache)
    {
        if (!cache || cache.IsPendingDeletion() || cache.IsRuined()) { return false; }
        if (cache.GetHierarchyRootPlayer() || cache.GetHierarchyParent() || !cache.GetInventory()) { return false; }
        CargoBase cargo = cache.GetInventory().GetCargo();
        return cargo && cargo.GetItemCount() > 0;
    }
    // Borrowed physical stock always stays with its native owner.
    static void Discard(ItemBase cache) {}
}
