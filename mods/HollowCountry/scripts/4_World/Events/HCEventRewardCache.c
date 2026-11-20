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

    protected static string s_PoliceReason;
    protected static string s_PoliceDetails;

    static string PoliceReason() { return s_PoliceReason; }
    static string PoliceDetails() { return s_PoliceDetails; }
    static void PoliceRefused(string reason, string details = "")
    {
        s_PoliceReason = reason;
        s_PoliceDetails = details;
    }

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
        PoliceRefused("");
        if (!HCEventSites.PoliceSupplies(mission)) { PoliceRefused("police_mission_mismatch"); return null; }
        if (!HCEventSitesGate.Admitted()) { PoliceRefused("police_gate_closed"); return null; }
        if (!GetGame() || !GetGame().IsServer()) { PoliceRefused("police_server_unavailable"); return null; }
        if (!HCEventRuntimePolicy.MissionValid(mission, mission.WorldName)) { PoliceRefused("police_mission_invalid"); return null; }
        HCEventTarget existing = PoliceTarget(mission.Id);
        if (existing) { return existing; }
        // Physical stock lookup is centred on the exact stock station origin.
        // The old +6,+6 placement offset clipped the opposite side of the 15 m
        // lookup sphere; no placement/navmesh operation occurs on this path.
        Spawn(mission, mission.Source, mission.ContainerClass, true);
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
        if (police) { PoliceRefused(""); }
        if (!mission) { if (police) { PoliceRefused("police_mission_invalid"); } return vector.Zero; }
        if (!GetGame() || !GetGame().IsServer()) { if (police) { PoliceRefused("police_server_unavailable"); } return vector.Zero; }
        float height = GetGame().SurfaceY(anchor[0], anchor[2]);
        if (height != height)
        {
            if (police) { PoliceRefused("police_terrain_unavailable"); }
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
            if (height > mission.Source[1] + 3 || height < mission.Source[1] - 12)
            {
                PoliceRefused("police_terrain_height", "; h=" + height.ToString() + "; src=" + mission.Source[1].ToString());
                return vector.Zero;
            }
            position = HCEventPoliceNav.Sample(Vector(anchor[0], height, anchor[2]), 6);
            if (position == vector.Zero) { PoliceRefused("police_navmesh_none"); return vector.Zero; }
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
        if (vector.DistanceSq(position, mission.Source) > mission.Radius * mission.Radius)
        {
            if (police) { PoliceRefused("police_position_outside_radius"); }
            return vector.Zero;
        }
        return position;
    }
    static HCEventTarget Spawn(HCEventMission mission, vector anchor, string containerClass, bool police)
    {
        if (police) { PoliceRefused(""); }
        if (!mission) { if (police) { PoliceRefused("police_mission_invalid"); } return null; }
        if (!GetGame() || !GetGame().IsServer()) { if (police) { PoliceRefused("police_server_unavailable"); } return null; }
        if (!HCEventSitesGate.Admitted()) { if (police) { PoliceRefused("police_gate_closed"); } return null; }
        if (!HCPhysicalEnabled()) { if (police) { PoliceRefused("police_physical_disabled"); } return null; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        if (!policy) { if (police) { PoliceRefused("police_policy_invalid"); } return null; }
        int consumer = HCUnitBudget.HC_WORK_SITUATIONS;
        if (police) { consumer = HCUnitBudget.HC_WORK_POLICE_BIND; }
        if (!HCServer.HCTickWork().HCTakeFor(consumer, 8)) { if (police) { PoliceRefused("police_work_budget"); } return null; }
        array<Object> nearby = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(anchor, mission.Radius, nearby, proxies);
        int remaining = policy.PhysicalScanObjects;
        bool matchingStock = false;
        ItemBase groundItem;
        ItemBase deliveryContainer;
        array<string> classes;
        if (police) { classes = HCW38SituationPolicy.PoliceClasses(mission.Family); }
        foreach (Object candidate : nearby)
        {
            if (remaining <= 0) { break; }
            remaining = remaining - 1;
            ItemBase cache = ItemBase.Cast(candidate);
            if (!HCPhysicalGround(cache)) { continue; }
            if (vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius) { continue; }
            if (police)
            {
                if (!groundItem && cache.HCEventEconomyCandidate() && PoliceItemMatches(cache, mission, classes) && !PoliceItemUsed(cache)) { groundItem = cache; }
                if (cache.GetType() != containerClass || !cache.GetInventory() || !cache.GetInventory().GetCargo()) { continue; }
                matchingStock = true;
                // Delivery still means putting the actual item into the native
                // container at Destination. Empty containers are valid destinations.
                if (vector.DistanceSq(cache.GetPosition(), mission.Destination) <= mission.Radius * mission.Radius) { deliveryContainer = cache; }
                CargoBase cargo = cache.GetInventory().GetCargo();
                int count = cargo.GetItemCount();
                if (count > policy.PhysicalScanCargo) { count = policy.PhysicalScanCargo; }
                int index = 0;
                while (index < count)
                {
                    ItemBase item = ItemBase.Cast(cargo.GetItem(index));
                    index = index + 1;
                    if (!item || item.IsPendingDeletion() || item.IsRuined() || item.GetHierarchyRootPlayer()) { continue; }
                    if (item.GetHierarchyParent() != cache || !PoliceItemMatches(item, mission, classes) || PoliceItemUsed(item)) { continue; }
                    if (mission.Family == HCEventFamily.DELIVERY && !deliveryContainer) { continue; }
                    if (mission.Family == HCEventFamily.DELIVERY) { return RememberPolice(mission, item, deliveryContainer); }
                    return RememberPolice(mission, item, cache);
                }
                continue;
            }
            if (!HCPhysicalStock(cache) || cache.GetType() != containerClass) { continue; }
            HCEventTarget result = new HCEventTarget;
            result.MissionId = mission.Id;
            result.Item = cache;
            result.Presence = cache;
            return result;
        }
        if (police)
        {
            if (groundItem && (mission.Family != HCEventFamily.DELIVERY || deliveryContainer)) { return RememberPolice(mission, groundItem, deliveryContainer); }
            string reason = "police_stock_absent";
            if (matchingStock) { reason = "police_cargo_item_absent"; }
            if (groundItem && mission.Family == HCEventFamily.DELIVERY) { reason = "police_delivery_container_absent"; }
            if (nearby.Count() > policy.PhysicalScanObjects) { reason = "police_scan_limit"; }
            string details = "; wanted=" + mission.ItemClass + "; container=" + containerClass;
            details = details + "; queried=" + nearby.Count().ToString() + "; scan_cap=" + policy.PhysicalScanObjects.ToString();
            PoliceRefused(reason, details);
        }
        HCPhysicalPending();
        return null;
    }

    // Exact configured classes only; retain the original wanted barrel item.
    static bool PoliceItemMatches(ItemBase item, HCEventMission mission, array<string> classes)
    {
        if (item.GetType() == mission.ItemClass) { return true; }
        return classes && classes.Find(item.GetType()) >= 0;
    }
    static bool PoliceItemUsed(ItemBase item)
    {
        if (!s_PoliceTargets) { return false; }
        foreach (HCEventTarget target : s_PoliceTargets)
        {
            if (target.Item == item) { return true; }
        }
        return false;
    }
    static HCEventTarget RememberPolice(HCEventMission mission, ItemBase item, ItemBase container)
    {
        HCEventTarget supply = new HCEventTarget;
        supply.MissionId = mission.Id;
        supply.Item = item;
        supply.DeliveryContainer = container;
        if (!s_PoliceTargets) { s_PoliceTargets = new array<ref HCEventTarget>; }
        s_PoliceTargets.Insert(supply);
        return supply;
    }
    // Rosters are rebuilt on retry. Pin the objective to the actual native class
    // before Announce so Ready and later inventory evidence retain exact matching.
    static void PoliceObjectiveClass(HCEventMission mission)
    {
        if (!HCEventSites.PoliceSupplies(mission)) { return; }
        HCEventTarget supply = PoliceTarget(mission.Id);
        if (supply && supply.Item) { mission.ItemClass = supply.Item.GetType(); }
    }
    static bool HCPhysicalGround(ItemBase item)
    {
        return item && !item.IsPendingDeletion() && !item.IsRuined() && !item.GetHierarchyRootPlayer() && !item.GetHierarchyParent();
    }

    protected static bool s_PhysicalPendingPrinted;
    protected static bool s_PhysicalAdmissionPrinted;
    protected static bool s_PhysicalEnabled;
    static bool HCPhysicalEnabled()
    {
        // Operator marker is probed once per process, like the other acceptance markers.
        if (s_PhysicalAdmissionPrinted) { return s_PhysicalEnabled; }
        s_PhysicalAdmissionPrinted = true;
        s_PhysicalEnabled = !FileExist("$profile:HollowCountry/acceptance/w38_rewards.disable");
        Print(HCV2Admission.Line("PhysicalSpoils", s_PhysicalEnabled, "w38_rewards", false) + " runtime=PENDING");
        return s_PhysicalEnabled;
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
