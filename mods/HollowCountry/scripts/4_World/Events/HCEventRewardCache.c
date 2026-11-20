// Police: borrow real stock first; otherwise reserve one finite HC cache per site.
// Native persistence owns the cache and its cargo after creation; depleted caches
// are never refilled. The durable reservation precedes creation, including failures.
// Native scripts-1.30.164289: Global/Game.c:703/705 CreateObjectEx/ObjectDelete;
// CE/CentralEconomy.c:9/17/28 ECE_SETUP/CREATEPHYSICS/KEEPHEIGHT;
// Systems/Inventory/Inventory.c:876 CreateInInventory; Entities/Object.c:287 GetPosition.
class HCEventPoliceRewardIO : HCEventRewardIO
{
    void HCEventPoliceRewardIO()
    {
        m_Root = "$profile:HollowCountry/Events/police-cache-stock";
    }
}
// Unlike the legacy per-boot allowance, these immutable site grants survive restart.
// Existing HCEventJournalIO provides bounded write/readback; no replay or refund.
class HCEventPoliceStockLedger : HCEventRewardLedger
{
    override HCEventRewardPlan Commit(string siteId)
    {
        if (siteId != "coastal-police-source" && siteId != "inland-police-source") { return null; }
        if (!m_IO || !m_IO.Ensure() || m_Fault) { return null; }
        string name = siteId + ".txt";
        if (m_IO.Exists(name) || m_Granted.Find(siteId) >= 0) { return null; }
        m_Granted.Insert(siteId);
        HCEventRewardPlan plan = new HCEventRewardPlan;
        plan.SiteId = siteId;
        plan.Items.Insert("BandageDressing");
        plan.Items.Insert("SodaCan_Cola");
        plan.Items.Insert("MetalWire");
        if (!m_IO.WriteNew(name, "HC-POLICE-STOCK v1 " + siteId, 128)) { Fault(); return null; }
        return plan;
    }

    // Ownership lives in this ledger, never in entity storage: extending Barrel_Green
    // OnStoreSave broke every persisted barrel ("Scripted variables corrupted", 103 boot).
    bool RecordCache(string siteId, vector position)
    {
        if (!m_IO || m_Fault) { return false; }
        return m_IO.WriteNew(siteId + ".pos", position.ToString(false), 96);
    }

    bool CachePosition(string siteId, out vector position)
    {
        position = vector.Zero;
        if (!m_IO || m_Fault || !m_IO.Exists(siteId + ".pos")) { return false; }
        string text = m_IO.Read(siteId + ".pos", 96);
        if (text == "") { return false; }
        text.Trim();
        position = text.ToVector();
        return position != vector.Zero;
    }
}
// Native: 3_Game/AI/AIWorld.c:122 SampleNavmeshPosition, :65 PGFilter.SetFlags;
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
    // Upper bound for the native physical-stock sphere around a mission source (metres).
    static const float SCAN_RADIUS_MAX = 25;
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
            s_PoliceLedger = new HCEventPoliceStockLedger;
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
        // Keep the CE lookup at the exact origin; only the HC fallback uses navmesh.
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
    // Used only for newly reserved HC stock; never moves existing world stock.
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
        // The native query cost grows with every object in the sphere (a 65 m sphere in a town
        // cost 441 ms in one unit on build 102); the scan cap below only limits inspection.
        // Caches sit at the source and police stock falls back to the owned cache, so a
        // bounded sphere is enough. Native: 3_Game/Global/Game.c:930 GetObjectsAtPosition3D.
        float scanRadius = Math.Min(mission.Radius, SCAN_RADIUS_MAX);
        GetGame().GetObjectsAtPosition3D(anchor, scanRadius, nearby, proxies);
        int remaining = policy.PhysicalScanObjects;
        bool matchingStock = false;
        Barrel_Green ownedCache;
        vector ownedPosition;
        HCEventPoliceStockLedger stockLedger = HCEventPoliceStockLedger.Cast(PoliceLedger());
        bool hasOwnedPosition = stockLedger && stockLedger.CachePosition(mission.SiteId, ownedPosition);
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
                Barrel_Green tagged = Barrel_Green.Cast(cache);
                if (tagged && hasOwnedPosition && vector.DistanceSq(tagged.GetPosition(), ownedPosition) <= 4) { ownedCache = tagged; }
                // Persisted stock has no new-CE callback this boot. Borrow the
                // actual uncarried item; this path neither clones nor claims CE ownership.
                if (!groundItem && PoliceItemMatches(cache, mission, classes) && !PoliceItemUsed(cache)) { groundItem = cache; }
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
            // Never create after an incomplete scan: a persisted cache may be omitted.
            if (nearby.Count() <= policy.PhysicalScanObjects)
            {
                if (!ownedCache) { ownedCache = CreatePoliceStock(mission); }
                if (ownedCache) { return PoliceStockTarget(mission, ownedCache); }
                if (PoliceReason() != "") { return null; }
            }
            PoliceRefused(reason, details);
        }
        HCPhysicalPending();
        return null;
    }

    static Barrel_Green CreatePoliceStock(HCEventMission mission)
    {
        vector position = SpawnPosition(mission, mission.Source, true);
        if (position == vector.Zero) { return null; }
        HCEventRewardPlan plan = PoliceLedger().Commit(mission.SiteId);
        if (!plan) { PoliceRefused("police_cache_reserved_or_spent"); return null; }
        Barrel_Green cache = Barrel_Green.Cast(GetGame().CreateObjectEx("Barrel_Green", position, ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS));
        if (!cache) { PoliceRefused("police_cache_create_failed"); return null; }
        HCGroundSnap.Snap(cache);
        HCEventPoliceStockLedger owner = HCEventPoliceStockLedger.Cast(PoliceLedger());
        if (!owner || !owner.RecordCache(mission.SiteId, cache.GetPosition()))
        {
            // Reservation already spent; an unrecorded cache is still finite native loot.
            Print("[HC Events] police cache position not recorded; " + mission.SiteId + " runtime=PENDING");
        }
        // Native: ItemBase/Barrel_ColorBase.c:87 Open, :512 cargo requires IsOpen.
        // Open only the new owned cache before its initial cargo is created.
        cache.Open();
        foreach (string itemClass : plan.Items)
        {
            if (!cache.GetInventory().CreateInInventory(itemClass))
            {
                // Only our unpublished cache is deleted; never borrowed CE stock.
                GetGame().ObjectDelete(cache);
                PoliceRefused("police_cache_cargo_failed");
                return null;
            }
        }
        Print("[HC Events] police cache created; " + mission.SiteId + "; stock=finite; refill=never runtime=PENDING");
        return cache;
    }
    static HCEventTarget PoliceStockTarget(HCEventMission mission, Barrel_Green cache)
    {
        CargoBase cargo = cache.GetInventory().GetCargo();
        int count = cargo.GetItemCount();
        if (count > 16) { count = 16; }
        for (int index = 0; index < count; index++)
        {
            ItemBase item = ItemBase.Cast(cargo.GetItem(index));
            if (!item || item.IsPendingDeletion() || item.IsRuined() || item.GetType() != mission.ItemClass || PoliceItemUsed(item)) { continue; }
            return RememberPolice(mission, item, cache);
        }
        PoliceRefused("police_cache_depleted");
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
