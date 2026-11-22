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
// One orphan repair ever: spent .txt, no .pos/.repair and no ground barrel in the
// completed capped scan. The scan only marks the site eligible in process memory;
// Commit writes the immutable .repair when it grants, so a refused SpawnPosition or a
// restart before the grant leaves the repair available for the next boot.
// Existing HCEventJournalIO provides bounded write/readback; no other replay or refund.
class HCEventPoliceStockLedger : HCEventRewardLedger
{
    protected ref array<string> m_RepairChecked = new array<string>;
    protected ref array<string> m_RepairPending = new array<string>;

    // A positive barrel observation may refuse early; absence requires a completed scan.
    void HCRepairOrphan(string siteId, bool barrelPresent)
    {
        if (siteId != "coastal-police-source" && siteId != "inland-police-source") { return; }
        if (m_RepairChecked.Find(siteId) >= 0 || !m_IO || m_Fault || !m_IO.Ensure()) { return; }
        m_RepairChecked.Insert(siteId);
        if (m_Granted.Find(siteId) >= 0 || !m_IO.Exists(siteId + ".txt") || m_IO.Exists(siteId + ".pos") || m_IO.Exists(siteId + ".repair")) { return; }
        if (barrelPresent)
        {
            Print("[HC Events] police grant orphan kept; " + siteId + "; reason=barrel_present runtime=PENDING");
            return;
        }
        m_RepairPending.Insert(siteId);
    }

    override HCEventRewardPlan Commit(string siteId)
    {
        if (siteId != "coastal-police-source" && siteId != "inland-police-source") { return null; }
        if (!m_IO || !m_IO.Ensure() || m_Fault) { return null; }
        string name = siteId + ".txt";
        if (m_Granted.Find(siteId) >= 0 || m_IO.Exists(siteId + ".pos")) { return null; }
        int repair = m_RepairPending.Find(siteId);
        if (repair < 0 && (m_IO.Exists(name) || m_IO.Exists(siteId + ".repair"))) { return null; }
        if (repair >= 0)
        {
            m_RepairPending.Remove(repair);
            // The marker is the spend: it is durable before any native creation.
            if (m_IO.Exists(siteId + ".repair")) { return null; }
            if (!m_IO.WriteNew(siteId + ".repair", "HC-POLICE-STOCK-REPAIR v1 " + siteId, 128)) { Fault(); return null; }
            Print("[HC Events] police grant orphan repaired; " + siteId + "; runtime=PENDING");
        }
        m_Granted.Insert(siteId);
        HCEventRewardPlan plan = new HCEventRewardPlan;
        plan.SiteId = siteId;
        plan.Items.Insert("BandageDressing");
        plan.Items.Insert("SodaCan_Cola");
        plan.Items.Insert("MetalWire");
        // A repair consumes its marker-backed allowance without rewriting the spent .txt.
        if (repair < 0 && !m_IO.WriteNew(name, "HC-POLICE-STOCK v1 " + siteId, 128)) { Fault(); return null; }
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
// Retain native query order with a capped cargo handle snapshot per container.
// No inventory is cloned; fallbacks start only after the full capped scan.
class HCEventPoliceStockSlice
{
    ref array<Object> Nearby;
    int Next;
    int Stage;
    Barrel_Green OwnedCache;
    vector OwnedPosition;
    bool HasOwnedPosition;
    bool GroundBarrelPresent;
    ItemBase GroundItem;
    ItemBase DeliveryContainer;
    ItemBase CargoOwner;
    int CargoNext;
    ref array<ItemBase> CargoItems;
}
class HCEventCacheSpawner
{
    // Upper bound for the native physical-stock sphere around a mission source (metres).
    static const float SCAN_RADIUS_MAX = 25;
    protected static ref map<string, ref HCEventPoliceStockSlice> s_StockSlices = new map<string, ref HCEventPoliceStockSlice>;
    protected static ref HCEventRewardLedger s_PoliceLedger;
    protected static ref array<ref HCEventTarget> s_PoliceTargets;

    protected static int s_PoliceQueryPeak;
    protected static int s_CacheQueryPeak;
    // The native query allocates the entire sphere before returning. Isolate
    // its peak from inspection/cargo/ledger work without changing stock order,
    // overflow refusal, radius, retry semantics or the durability barrier.
    static void HCStockQueryCost(int began, bool police)
    {
        int cost = TickCount(began);
        string consumer = "SITUATIONS";
        if (police)
        {
            if (cost <= s_PoliceQueryPeak) { return; }
            s_PoliceQueryPeak = cost;
            consumer = "POLICE_BIND";
        }
        else
        {
            if (cost <= s_CacheQueryPeak) { return; }
            s_CacheQueryPeak = cost;
        }
        if (cost >= 40000)
        {
            Print("[HC Events] stock_query consumer=" + consumer + " ticks_max=" + cost.ToString() + " atomic=1 runtime=PENDING");
        }
    }

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
        SpawnPoliceSlice(mission);
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
    // One shared admission owner for stock and infected bind continuations.
    // Their roster slot is serialized by HCEventModule, so they cannot consume
    // each other's sole starvation grant in the same refresh.
    static bool PoliceWork()
    {
        return HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_POLICE_BIND, 8);
    }

    static HCEventTarget SpawnPoliceSlice(HCEventMission mission)
    {
        PoliceRefused("police_work_budget");
        if (!HCPhysicalEnabled()) { PoliceRefused("police_physical_disabled"); return null; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        if (!policy) { PoliceRefused("police_policy_invalid"); return null; }
        if (!PoliceWork()) { return null; }
        HCEventPoliceStockSlice job = s_StockSlices.Get(mission.Id);
        if (!job)
        {
            job = new HCEventPoliceStockSlice;
            job.Nearby = new array<Object>;
            array<CargoBase> proxies = new array<CargoBase>;
            int began = TickCount(0);
            GetGame().GetObjectsAtPosition3D(mission.Source, Math.Min(mission.Radius, SCAN_RADIUS_MAX), job.Nearby, proxies);
            HCStockQueryCost(began, true);
            s_StockSlices.Set(mission.Id, job);
            return null;
        }
        if (job.Stage == 0)
        {
            HCEventPoliceStockLedger ledger = HCEventPoliceStockLedger.Cast(PoliceLedger());
            job.HasOwnedPosition = ledger && ledger.CachePosition(mission.SiteId, job.OwnedPosition);
            job.Stage = 1;
            return null;
        }
        if (job.Stage == 1)
        {
            array<string> classes = HCW38SituationPolicy.PoliceClasses(mission.Family);
            HCWorkBudget slice = new HCWorkBudget;
            slice.HCReset(32, Math.Min(HCPerfConfig.HCGet().SliceMs, 2));
            while (slice.HCContinue())
            {
                if (job.CargoOwner)
                {
                    ItemBase cargoOwner = job.CargoOwner;
                    // Validate the retained owner before any native inventory access.
                    if (!HCPhysicalGround(cargoOwner) || vector.DistanceSq(cargoOwner.GetPosition(), mission.Source) > mission.Radius * mission.Radius)
                    {
                        job.CargoOwner = null;
                        job.CargoItems = null;
                        continue;
                    }
                    CargoBase cargo;
                    if (cargoOwner.GetInventory()) { cargo = cargoOwner.GetInventory().GetCargo(); }
                    if (!cargo)
                    {
                        job.CargoOwner = null;
                        job.CargoItems = null;
                        continue;
                    }
                    if (!job.CargoItems)
                    {
                        // One grant snapshots at most 64 weak item handles in
                        // native order. No yield can shift indices mid-copy.
                        job.CargoItems = new array<ItemBase>;
                        int cargoCount = Math.Min(cargo.GetItemCount(), policy.PhysicalScanCargo);
                        for (int cargoIndex = 0; cargoIndex < cargoCount; cargoIndex++)
                        {
                            job.CargoItems.Insert(ItemBase.Cast(cargo.GetItem(cargoIndex)));
                        }
                        return null;
                    }
                    if (job.CargoNext >= job.CargoItems.Count())
                    {
                        job.CargoOwner = null;
                        job.CargoItems = null;
                        continue;
                    }
                    ItemBase item = job.CargoItems[job.CargoNext];
                    job.CargoNext++;
                    if (!item || item.IsSetForDeletion() || item.IsRuined() || item.GetHierarchyRootPlayer()) { continue; }
                    if (item.GetHierarchyParent() != cargoOwner || !PoliceItemMatches(item, mission, classes) || PoliceItemUsed(item)) { continue; }
                    if (mission.Family == HCEventFamily.DELIVERY && !PoliceDeliveryValid(mission, job.DeliveryContainer)) { continue; }
                    s_StockSlices.Remove(mission.Id);
                    if (mission.Family == HCEventFamily.DELIVERY) { return RememberPolice(mission, item, job.DeliveryContainer); }
                    return RememberPolice(mission, item, cargoOwner);
                }
                if (job.Next >= job.Nearby.Count() || job.Next >= policy.PhysicalScanObjects)
                {
                    job.Stage = 2;
                    return null;
                }
                ItemBase cache = ItemBase.Cast(job.Nearby[job.Next]);
                job.Next++;
                // Even a ruined ground barrel blocks repair; it may be the old HC cache.
                Barrel_Green nearbyBarrel = Barrel_Green.Cast(cache);
                if (!job.GroundBarrelPresent && nearbyBarrel && !nearbyBarrel.IsSetForDeletion() && !nearbyBarrel.GetHierarchyParent() && !nearbyBarrel.GetHierarchyRootPlayer() && vector.DistanceSq(nearbyBarrel.GetPosition(), mission.Source) <= mission.Radius * mission.Radius)
                {
                    job.GroundBarrelPresent = true;
                    HCEventPoliceStockLedger barrelLedger = HCEventPoliceStockLedger.Cast(PoliceLedger());
                    if (barrelLedger) { barrelLedger.HCRepairOrphan(mission.SiteId, true); }
                }
                if (!HCPhysicalGround(cache)) { continue; }
                if (vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius) { continue; }
                Barrel_Green tagged = Barrel_Green.Cast(cache);
                if (tagged && job.HasOwnedPosition && vector.DistanceSq(tagged.GetPosition(), job.OwnedPosition) <= 4) { job.OwnedCache = tagged; }
                if (!job.GroundItem && PoliceItemMatches(cache, mission, classes) && !PoliceItemUsed(cache)) { job.GroundItem = cache; }
                if (cache.GetType() != mission.ContainerClass || !cache.GetInventory() || !cache.GetInventory().GetCargo()) { continue; }
                if (vector.DistanceSq(cache.GetPosition(), mission.Destination) <= mission.Radius * mission.Radius) { job.DeliveryContainer = cache; }
                job.CargoOwner = cache;
                job.CargoNext = 0;
                job.CargoItems = null;
                // Isolate the bounded snapshot from object inspection work.
                return null;
            }
            return null;
        }
        if (job.Stage == 2)
        {
            // A retained ground item may have been picked up between grants.
            // Refuse that attempt rather than borrowing a different target.
            if (job.GroundItem && (!HCPhysicalGround(job.GroundItem) || PoliceItemUsed(job.GroundItem) || vector.DistanceSq(job.GroundItem.GetPosition(), mission.Source) > mission.Radius * mission.Radius))
            {
                s_StockSlices.Remove(mission.Id);
                PoliceRefused("police_target_changed");
                return null;
            }
            if (job.DeliveryContainer && !PoliceDeliveryValid(mission, job.DeliveryContainer))
            {
                if (mission.Family == HCEventFamily.DELIVERY)
                {
                    s_StockSlices.Remove(mission.Id);
                    PoliceRefused("police_target_changed");
                    return null;
                }
                job.DeliveryContainer = null;
            }
            if (job.GroundItem && (mission.Family != HCEventFamily.DELIVERY || PoliceDeliveryValid(mission, job.DeliveryContainer)))
            {
                s_StockSlices.Remove(mission.Id);
                return RememberPolice(mission, job.GroundItem, job.DeliveryContainer);
            }
            if (job.Nearby.Count() > policy.PhysicalScanObjects)
            {
                s_StockSlices.Remove(mission.Id);
                PoliceRefused("police_scan_limit", "; queried=" + job.Nearby.Count().ToString() + "; scan_cap=" + policy.PhysicalScanObjects.ToString());
                return null;
            }
            if (job.OwnedCache)
            {
                s_StockSlices.Remove(mission.Id);
                return PoliceStockTarget(mission, job.OwnedCache);
            }
            HCEventPoliceStockLedger repairLedger = HCEventPoliceStockLedger.Cast(PoliceLedger());
            if (repairLedger) { repairLedger.HCRepairOrphan(mission.SiteId, job.GroundBarrelPresent); }
            // No native creation handle or partially initialized cache crosses a grant.
            s_StockSlices.Remove(mission.Id);
            Barrel_Green created = CreatePoliceStock(mission);
            if (created) { return PoliceStockTarget(mission, created); }
            return null;
        }
        return null;
    }

    // Restore the pre-slicing creation order (4b12d4f0) within one PoliceWork grant.
    // The plan is fixed at three items; only the capped world/cargo scan yields.
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
        cache.Open();
        foreach (string itemClass : plan.Items)
        {
            // Preserve 60a261e3: never delete the cache or its cargo on failure.
            // The durable allocation stays spent, including partial stocking.
            if (!HCPhysicalGround(cache) || !cache.IsOpen() || !cache.GetInventory() || !cache.GetInventory().CreateInInventory(itemClass))
            {
                PoliceRefused("police_cache_cargo_failed");
                return null;
            }
        }
        Print("[HC Events] police cache created; " + mission.SiteId + "; stock=finite; refill=never runtime=PENDING");
        return cache;
    }

    static bool PoliceDeliveryValid(HCEventMission mission, ItemBase container)
    {
        if (!HCPhysicalGround(container) || container.GetType() != mission.ContainerClass || !container.GetInventory() || !container.GetInventory().GetCargo()) { return false; }
        return vector.DistanceSq(container.GetPosition(), mission.Source) <= mission.Radius * mission.Radius && vector.DistanceSq(container.GetPosition(), mission.Destination) <= mission.Radius * mission.Radius;
    }

    static HCEventTarget Spawn(HCEventMission mission, vector anchor, string containerClass, bool police)
    {
        // Police owns a retained job; ordinary recovery keeps its bounded lookup.
        if (police) { return SpawnPoliceSlice(mission); }
        if (!mission || !GetGame() || !GetGame().IsServer() || !HCEventSitesGate.Admitted() || !HCPhysicalEnabled()) { return null; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        int consumer = HCUnitBudget.HC_WORK_SITUATIONS;
        if (!policy || !HCServer.HCTickWork().HCTakeFor(consumer, 8)) { return null; }
        array<Object> nearby = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        int began = TickCount(0);
        GetGame().GetObjectsAtPosition3D(anchor, Math.Min(mission.Radius, SCAN_RADIUS_MAX), nearby, proxies);
        HCStockQueryCost(began, false);
        int remaining = policy.PhysicalScanObjects;
        foreach (Object candidate : nearby)
        {
            if (remaining <= 0) { break; }
            remaining--;
            ItemBase cache = ItemBase.Cast(candidate);
            if (!HCPhysicalGround(cache) || vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius) { continue; }
            if (!HCPhysicalStock(cache) || cache.GetType() != containerClass) { continue; }
            HCEventTarget result = new HCEventTarget;
            result.MissionId = mission.Id;
            result.Item = cache;
            result.Presence = cache;
            return result;
        }
        HCPhysicalPending();
        return null;
    }

    static HCEventTarget PoliceStockTarget(HCEventMission mission, Barrel_Green cache)
    {
        // OwnedCache can come from an earlier scan grant: validate before dereference.
        if (!HCPhysicalGround(cache) || !cache.GetInventory() || vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius)
        {
            PoliceRefused("police_target_changed");
            return null;
        }
        CargoBase cargo = cache.GetInventory().GetCargo();
        if (!cargo) { PoliceRefused("police_cache_depleted"); return null; }
        int count = cargo.GetItemCount();
        if (count > 16) { count = 16; }
        for (int index = 0; index < count; index++)
        {
            ItemBase item = ItemBase.Cast(cargo.GetItem(index));
            if (!item || item.IsSetForDeletion() || item.IsRuined() || item.GetHierarchyRootPlayer()) { continue; }
            if (item.GetHierarchyParent() != cache || item.GetType() != mission.ItemClass || PoliceItemUsed(item)) { continue; }
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
        if (supply && supply.Item && !supply.Item.IsSetForDeletion()) { mission.ItemClass = supply.Item.GetType(); }
    }
    static bool HCPhysicalGround(ItemBase item)
    {
        return item && !item.IsSetForDeletion() && !item.IsRuined() && !item.GetHierarchyRootPlayer() && !item.GetHierarchyParent();
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
        if (!cache || cache.IsSetForDeletion() || cache.IsRuined()) { return false; }
        if (cache.GetHierarchyRootPlayer() || cache.GetHierarchyParent() || !cache.GetInventory()) { return false; }
        CargoBase cargo = cache.GetInventory().GetCargo();
        return cargo && cargo.GetItemCount() > 0;
    }
    // Borrowed physical stock always stays with its native owner.
    static void Discard(ItemBase cache) {}
}
