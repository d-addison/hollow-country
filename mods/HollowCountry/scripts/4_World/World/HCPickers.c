// HC-34: one finite trip, one native transfer at each durable barrier.
// Shared guard precedes route/native work; journal barriers remain synchronous.
// Native timing evidence: HCWorkBudget.c (Game.c:914).
// LC-T407/409, #101. Native evidence in installed scripts-1.30.164289:
// 3_Game/Entities/Object.c:287 GetPosition, :305 GetOrientation, :873 ModelToWorld;
// 3_Game/Global/Game.c:1120 IsServer; gameplay.c:636 GetGame;
// 1_Core/proto/EnScript.c:394 Find, :385 Clear; EnConvert.c:30 int.ToString;
// 3_Game/Entities/EntityAI.c:885 GetHierarchyParent, :1884 GetInventory;
// 3_Game/Systems/Inventory/Inventory.c:138 GetCargo; Cargo.c:28 GetItemCount, :32 GetItem;
// 1_Core/proto/EnScript.c:380 Count, :407 Insert; EnDebug.c:96 Print.
// Files/journal use HCSearchHouseJournal/HCEncounterStore, clock uses HCWorldClock.
// HC-34 retires abstract inventory hops; old journal evidence stays immutable.
// Wave 16 w32-pickers: the route survey is mission/hollow-country/ai/picker-routes.json,
// DERIVED from the scavenger sites of ai/sites.json (waypoints verbatim). The module is
// `ready` once the journal and the survey load; the one part this file cannot supply
// (an Expansion AI actor + group walk port) is a named one-time log line, not a refusal.
// Native evidence: 3_Game/Global/Game.c:930 GetObjectsAtPosition3D, :932 GetWorldName;
// Inventory.c:138 GetCargo; Cargo.c:28 GetItemCount, :32 GetItem; ItemBase.c:4372 IsTakeable.
// Runtime acceptance PENDING.
class HCPickerPolicy
{
    static int ChargeAfterVisit(int used, int phase)
    {
        if (phase == 2) return used + 1;
        return used;
    }

    static bool MayVisit(int used, int recordedDay, int today, bool visited)
    {
        return used >= 0 && used < 6 && recordedDay == today && !visited;
    }
}

// Shared immutable journal transaction. Entry phase 0 was durably bound by the
// caller. Phase 1 is installed before callbacks. Neither failure nor restart
// ever reopens the row. There is exactly one native move and no compensation.
class HCNonPlayerMoves
{
    ref HCSearchHouseJournal m_Journal;
    ref HCSearchSupplyRegistry m_Registry;

    int CommitMove(HCSearchEntry entry, EntityAI destination, string actorId, int index)
    {
        if (!m_Journal || !m_Registry || !m_Journal.Healthy()) return 3;
        if (!m_Journal.Row(index)) return 3;
        int prior = m_Journal.Row(index).Phase;
        if (prior == 2 || prior == 3 || prior == 4) return prior;
        if (prior != 0) return 3;
        m_Journal.SetPhase(index, 1);
        int phase = 3;
        if (m_Journal.Write(index, "claim", actorId, 1))
        {
            if (m_Journal.Write(index, "attempt", actorId, 1))
            {
                phase = m_Registry.Transfer(entry, destination, actorId);
            }
            if (!m_Journal.Write(index, "result", actorId, phase)) phase = 3;
        }
        m_Journal.SetPhase(index, phase);
        return phase;
    }
}

// Compatibility seam for old callers; house stock is no longer moved remotely.
modded class HCSearchHouses
{
    int V2Visit(Object structure, EntityAI destination, string actorId, int siteNumber)
    {
        // HC-34: this old port had no body, reachable route or local pickup.
        // All callers, including legacy holdout upkeep, now refuse the hop.
        return 4;
    }

    // Callers check this before spending a finite attempt or saving.
    bool V2VisitAvailable()
    {
        return false;
    }
}

// A second, finite journal is exclusively for withdrawals from real caches.
// Different root from template search: same item can make another journaled hop,
// but no identical source-cache/item pair can ever replay here.
class HCCacheMoveJournal : HCSearchHouseJournal
{
    protected bool m_OpenAttempted;
    override bool Open(string sourceId, string sourcePin, string worldName, string build)
    {
        if (m_Open || m_Fault || !GetGame().IsServer()) return false;
        if (m_OpenAttempted) { return false; }
        m_OpenAttempted = true;
        m_SourceId = sourceId;
        m_SourcePin = sourcePin;
        m_WorldName = worldName;
        m_Build = build;
        m_Root = "$profile:HollowCountry/CacheMoves";
        if (!FileExist(m_Root) && !MakeDirectory(m_Root)) return Fail("cache journal unavailable");
        m_Open = true;
        return Restore();
    }
}

class HCCacheMoves
{
    protected static ref HCCacheMoves s_Shared;

    static HCCacheMoves Shared()
    {
        if (!s_Shared) s_Shared = new HCCacheMoves;
        return s_Shared;
    }

    protected ref HCSearchHouseJournal m_Journal;
    protected ref HCSearchSupplyRegistry m_Registry;
    protected bool m_Fault;
    static const string PIN = "cace000100000000000000000000000000000000000000000000000000000000";

    int TakeOne(EntityAI source, EntityAI destination, string actorId, array<string> allowed)
    {
        // Legacy shared callers cannot bypass an actual carrier and route.
        return 4;
    }

    void Stop()
    {
        if (m_Registry) m_Registry.Retire();
        if (s_Shared == this) s_Shared = null;
        m_Fault = true;
    }
}

// HC-34 / #144 -> LC-T407/409. One finite, same-item custody chain.
// The former abstract picker party is retired, without rewriting its history.
// HC-10 alone owns party/cargo identity. No new party or provider population.
// N2 evidence, inspected in native scripts-1.30.164289:
// 3_Game/Systems/Inventory/Inventory.c:268 GetCurrentInventoryLocation,
// :276 FindFreeLocationFor, :808 IsInventoryLocked, :1057 TakeToDst SERVER;
// InventoryLocation.c:52 GetParent, :62 GetItem, :210 CompareLocationOnly;
// 3_Game/Entities/EntityAI.c:879 GetHierarchyRoot, :882 GetHierarchyRootPlayer,
// :885 GetHierarchyParent, :1884 GetInventory, :3374 GetPersistentID;
// 3_Game/Entities/Object.c:287 GetPosition, :467 GetType, :517 IsAlive,
// :1219 IsRuined; 3_Game/Entities/Man.c:21 GetIdentity;
// 4_World/Entities/ManBase/PlayerBase.c:3925 IsUnconscious;
// 4_World/Entities/ItemBase.c:3490 GetQuantity, :4372 IsTakeable;
// 3_Game/Global/Game.c:1120 IsServer; gameplay.c:636 GetGame;
// 1_Core/proto/EnConvert.c:210 DistanceSq; EnDebug.c:96 Print.
// N17 is not an AI SDK. The optional Expansion addon binds the walk port;
// its inspected API citations live there. The base walk still refuses safely.
// All checkpoint writes are transaction barriers, synchronous verified store
// writes. No periodic state changes/save job; no second scheduler is needed.
class HCScavengeDefaults
{
    // Native search pickup is 2.5 m (HCSearchNativeSupply), 0.25% of the
    // approximately 1000 m network bubble/rifle report range. Not perception.
    float TransferRangeMeters = 2.5;
    // One journal/port is the structural ceiling, even if raised by an operator.
    int MaxConcurrentTrips = 1;
    int PartyCooldownSeconds = 900;
}

class HCScavengeState
{
    int Version = 1;
    // #201 additive receipt fields: absent in V1 journals = no theft attempts.
    // Retained when terminal trips rearm; restart never resets the daily debit.
    int HCTheftDay;
    int HCTheftAttempts;
    string Phase = "idle";
    string PartyId;
    string RouteId;
    int NextTripAt;
    string CargoId;
    int Generation;
    string LeaseId;
    string SourceId;
    string ActorId;
    string HomeId;
    string ItemId;
    string CargoOwner;
    string Refusal;
    ref array<ref HCPickCarryReceipt> HouseGoods;
}

// Survey point, copied verbatim from a scavenger site waypoint of ai/sites.json.
class HCPickerPoint
{
    float X;
    float Y;
    float Z;

    vector HCPosition() { return Vector(X, Y, Z); }
}

// One surveyed home -> source -> home loop. RouteId is the HC-10 route id the party
// carries ("route:" + the scavenger site id); HomeIndex/SourceIndex pick anchors out of
// the site's own waypoint loop, so the patrol's native LOOP order visits both.
class HCPickerRoute
{
    string RouteId;
    string SiteId;
    string LocalityId;
    int HomeIndex;
    int SourceIndex;
    ref array<ref HCPickerPoint> Waypoints = new array<ref HCPickerPoint>;

    vector HCHomePoint() { return Waypoints[HomeIndex].HCPosition(); }
    vector HCSourcePoint() { return Waypoints[SourceIndex].HCPosition(); }

    // Forward loop order, excluding the starting anchor and ending on the other anchor.
    void HCLegPoints(bool returning, array<vector> points)
    {
        int cursor = HomeIndex;
        int finish = SourceIndex;
        if (returning)
        {
            cursor = SourceIndex;
            finish = HomeIndex;
        }
        int guard = 0;
        while (guard < Waypoints.Count())
        {
            cursor = (cursor + 1) % Waypoints.Count();
            points.Insert(Waypoints[cursor].HCPosition());
            if (cursor == finish) { return; }
            guard++;
        }
    }
}

// Every number the survey uses is a named field of the file (no literal limits in code).
class HCPickerSurvey
{
    static const int MAX_BYTES = 16384;
    int Version;
    string WorldName;
    string DerivedFrom;
    float MaxLegMeters;
    float ArrivalRangeMeters;
    float MapExtentMeters;
    int MaxRoutes;
    int MaxWaypoints;
    int MaxScannedObjects;
    int MaxCargoScan;
    // #144 scavenging-run limits (HCPickPolicy). Every number is a named survey field.
    int RunMinMembers;
    int RunMaxMembers;
    int RunMaxHousesPerRun;
    int RunMaxCarriedHouseGoods;
    int RunMaxHouseAttempts;
    int RunMaxHouseCandidates;
    float RunHouseSearchRadiusMeters;
    float RunHouseSearchSeconds;
    float RunHouseWalkSeconds;
    int RunNeedStashItems;
    int RunNeedPercentSpring;
    int RunNeedPercentSummer;
    int RunNeedPercentAutumn;
    int RunNeedPercentWinter;
    int RunNeedRecheckSeconds;
    float RunDangerHeatAvoid;
    int RunDangerClueSeconds;
    int RunDangerMaxClues;
    int RunCombatAbortSeconds;
    int RunMaxPartiesPerCamp;
    int RunMaxActiveRuns;
    ref array<ref HCPickerRoute> Routes = new array<ref HCPickerRoute>;

    // First defect by name, "" when the survey is usable.
    string HCRefusal()
    {
        HCScavengeDefaults pickup = new HCScavengeDefaults;
        if (Version != 1) { return "PICKER_SURVEY_VERSION"; }
        if (MaxLegMeters <= 0 || MapExtentMeters <= 0 || ArrivalRangeMeters <= 0 || ArrivalRangeMeters > pickup.TransferRangeMeters) { return "PICKER_SURVEY_LIMITS"; }
        if (MaxRoutes < 1 || MaxWaypoints < 2 || MaxScannedObjects < 1 || MaxCargoScan < 1) { return "PICKER_SURVEY_LIMITS"; }
        if (!Routes || Routes.Count() < 1) { return "PICKER_SURVEY_EMPTY"; }
        if (Routes.Count() > MaxRoutes) { return "PICKER_SURVEY_ROUTE_CAP"; }
        for (int routeIndex = 0; routeIndex < Routes.Count(); routeIndex++)
        {
            HCPickerRoute route = Routes[routeIndex];
            if (!route || !HCWorldLimits.Token(route.RouteId) || !HCWorldLimits.Token(route.SiteId)) { return "PICKER_ROUTE_ID_INVALID"; }
            for (int priorIndex = 0; priorIndex < routeIndex; priorIndex++)
            {
                if (Routes[priorIndex].RouteId == route.RouteId) { return "PICKER_ROUTE_ID_DUPLICATE"; }
            }
            if (!route.Waypoints) { return "PICKER_ROUTE_WAYPOINTS"; }
            int count = route.Waypoints.Count();
            if (count < 2 || count > MaxWaypoints) { return "PICKER_ROUTE_WAYPOINTS"; }
            if (route.HomeIndex < 0 || route.SourceIndex < 0 || route.HomeIndex >= count || route.SourceIndex >= count || route.HomeIndex == route.SourceIndex) { return "PICKER_ROUTE_ANCHORS"; }
            for (int pointIndex = 0; pointIndex < count; pointIndex++)
            {
                HCPickerPoint point = route.Waypoints[pointIndex];
                HCPickerPoint following = route.Waypoints[(pointIndex + 1) % count];
                if (!point || !following) { return "PICKER_ROUTE_POINT_INVALID"; }
                if (point.X <= 0 || point.Z <= 0 || point.X >= MapExtentMeters || point.Z >= MapExtentMeters) { return "PICKER_ROUTE_POINT_INVALID"; }
                if (following.X <= 0 || following.Z <= 0 || following.X >= MapExtentMeters || following.Z >= MapExtentMeters) { return "PICKER_ROUTE_POINT_INVALID"; }
                float deltaX = following.X - point.X;
                float deltaZ = following.Z - point.Z;
                if (deltaX * deltaX + deltaZ * deltaZ > MaxLegMeters * MaxLegMeters) { return "PICKER_ROUTE_LEG_TOO_LONG"; }
            }
        }
        return "";
    }

    HCPickerRoute HCFind(string routeId)
    {
        for (int findIndex = 0; findIndex < Routes.Count(); findIndex++)
        {
            if (Routes[findIndex].RouteId == routeId) { return Routes[findIndex]; }
        }
        return null;
    }

    // Native JSON zero-fills missing fields (lint HC-S005): every field must be written.
    static bool HCFieldsPresent(string text)
    {
        if (!HCJsonFields.Has(text, "Version") || !HCJsonFields.Has(text, "WorldName") || !HCJsonFields.Has(text, "MaxLegMeters") || !HCJsonFields.Has(text, "ArrivalRangeMeters")) { return false; }
        if (!HCJsonFields.Has(text, "MapExtentMeters") || !HCJsonFields.Has(text, "MaxRoutes") || !HCJsonFields.Has(text, "MaxWaypoints")) { return false; }
        if (!HCJsonFields.Has(text, "MaxScannedObjects") || !HCJsonFields.Has(text, "MaxCargoScan")) { return false; }
        if (!HCJsonFields.Has(text, "RunMaxCarriedHouseGoods")) { return false; }
        if (!HCPickerSurvey.HCRunFieldsPresent(text)) { return false; }
        // Route objects are the depth-3 objects with Waypoints; CacheLoot rows share that depth.
        if (!HCJsonFields.Every(text, "RouteId", 3, "Waypoints") || !HCJsonFields.Every(text, "SiteId", 3, "Waypoints")) { return false; }
        if (!HCJsonFields.Every(text, "HomeIndex", 3, "Waypoints") || !HCJsonFields.Every(text, "SourceIndex", 3, "Waypoints")) { return false; }
        return HCJsonFields.Every(text, "X", 5) && HCJsonFields.Every(text, "Y", 5) && HCJsonFields.Every(text, "Z", 5);
    }

    // #144: the run limits are read by name too; a missing one would zero-fill silently.
    static bool HCRunFieldsPresent(string text)
    {
        if (!HCJsonFields.Has(text, "RunMinMembers") || !HCJsonFields.Has(text, "RunMaxMembers") || !HCJsonFields.Has(text, "RunMaxHousesPerRun")) { return false; }
        if (!HCJsonFields.Has(text, "RunMaxHouseAttempts") || !HCJsonFields.Has(text, "RunMaxHouseCandidates") || !HCJsonFields.Has(text, "RunHouseSearchRadiusMeters")) { return false; }
        if (!HCJsonFields.Has(text, "RunHouseSearchSeconds") || !HCJsonFields.Has(text, "RunHouseWalkSeconds") || !HCJsonFields.Has(text, "RunNeedStashItems")) { return false; }
        if (!HCJsonFields.Has(text, "RunNeedPercentSpring") || !HCJsonFields.Has(text, "RunNeedPercentSummer") || !HCJsonFields.Has(text, "RunNeedPercentAutumn")) { return false; }
        if (!HCJsonFields.Has(text, "RunNeedPercentWinter") || !HCJsonFields.Has(text, "RunNeedRecheckSeconds") || !HCJsonFields.Has(text, "RunDangerHeatAvoid")) { return false; }
        return HCJsonFields.Has(text, "RunDangerClueSeconds") && HCJsonFields.Has(text, "RunDangerMaxClues") && HCJsonFields.Has(text, "RunCombatAbortSeconds") && HCJsonFields.Has(text, "RunMaxPartiesPerCamp") && HCJsonFields.Has(text, "RunMaxActiveRuns");
    }

    // Null and a named refusal when the file is missing, malformed, foreign or invalid.
    static HCPickerSurvey HCLoad(out string refusal)
    {
        refusal = "PICKER_SURVEY_UNAVAILABLE";
        string text = HCWorldStore.Read("$mission:hollow-country/ai/picker-routes.json");
        if (text.Length() < 1 || text.Length() > HCPickerSurvey.MAX_BYTES) { return null; }
        refusal = "PICKER_SURVEY_FIELDS_MISSING";
        if (!HCPickerSurvey.HCFieldsPresent(text)) { return null; }
        refusal = "PICKER_SURVEY_PARSE";
        HCPickerSurvey survey = new HCPickerSurvey;
        string error;
        if (!JsonFileLoader<HCPickerSurvey>.LoadData(text, survey, error)) { return null; }
        refusal = survey.HCRefusal();
        if (refusal != "") { return null; }
        // #144: run limits are checked after every route element is known to be present.
        refusal = HCPickPolicy.RunRefusal(survey);
        if (refusal != "") { return null; }
        string world = GetGame().GetWorldName();
        world.ToLower();
        refusal = "PICKER_SURVEY_WORLD";
        if (survey.WorldName != world) { return null; }
        refusal = "";
        return survey;
    }
}

// Trusted server native inventory port. Handles are never restored from JSON.
// Wave 16: HCRouteReady is answered by the route survey and HCBindSurveyed binds the
// actor, the two real crates at the surveyed anchors and one real item. HCWalk stays a
// provider port (an Expansion group walk): the base refuses it and names that refusal.
class HCScavengeInventory
{
    // #201 server-only live camp guard; never restored or serialized handles.
    ref HCCampRecord HCTheftCamp;
    HCCampModule HCTheftOwner;

    bool HCTheftNear(EntityAI crate)
    {
        if (!HCLive() || !crate) { return false; }
        float range = Defaults.TransferRangeMeters;
        if (Survey && Survey.ArrivalRangeMeters < range) { range = Survey.ArrivalRangeMeters; }
        return vector.DistanceSq(Actor.GetPosition(), crate.GetPosition()) <= range * range;
    }

    // #201 same bounded cargo envelope as surveyed stock; unsafe cargo does
    // not hide a later eligible real item. No recursive or recreated stock.
    ItemBase HCTheftFirstItem(EntityAI crate)
    {
        if (!Survey || !crate || !crate.GetInventory()) { return null; }
        CargoBase cargo = crate.GetInventory().GetCargo();
        if (!cargo) { return null; }
        int count = cargo.GetItemCount();
        if (count > Survey.MaxCargoScan) { count = Survey.MaxCargoScan; }
        for (int theftIndex = 0; theftIndex < count; theftIndex++)
        {
            ItemBase stock = ItemBase.Cast(cargo.GetItem(theftIndex));
            if (HCCampTheft.SafeItem(stock) && stock.IsTakeable() && HCSearchSupplyRegistry.PersistentId(stock) != "") { return stock; }
        }
        return null;
    }

    // #144 run seams. Danger and Houses are owned by HCPickers and shared at bind.
    ref HCPickRunner Runner;
    ref HCPickCarry Carry = new HCPickCarry;
    HCScavengeTrip CustodyTrip;
    HCPickDanger Danger;
    HCPickHousePort Houses;

    PlayerBase Actor;
    EntityAI Source;
    EntityAI Home;
    ItemBase Item;
    string LeaseId;
    ref HCScavengeDefaults Defaults = new HCScavengeDefaults;

    ref HCPickerSurvey Survey;

    // A route is ready only when the survey lists this party's exact HC-10 route id.
    bool HCRouteReady(HCAIPartyIdentity identity, string lease)
    {
        if (!Survey || !HCAIPartyIdentity.HCValid(identity) || lease == "") { return false; }
        return Survey.HCFind(identity.HCRouteId()) != null;
    }

    // Provider port: an addon override sets the group's surveyed leg (HCPickerRoute.HCLegPoints)
    // and returns true once the request is made. Arrival is observed by HCAtSource/HCAtHome only.
    bool HCWalk(bool returning) { return false; }
    string HCWalkRefusal() { return "PICKER_WALK_PORT_UNBOUND_EXPANSION_GROUP"; }

    // #144 provider ports, refused by default: one detour waypoint on the claimed
    // party, the live member count (-1 unknown) and the party's combat flag.
    bool HCWalkTo(vector point) { return false; }
    int HCPartyMembers() { return -1; }
    bool HCPartyInCombat() { return false; }

    // Same persistent id the HC-34 journal records for the carrier.
    string HCActorKey() { return HCSearchSupplyRegistry.PersistentId(Actor); }

    // Real cargo count of the home crate inside the surveyed scan bound; -1 unreadable.
    int HCStashItems()
    {
        if (!Survey || !Home || !Home.GetInventory()) { return -1; }
        CargoBase cargo = Home.GetInventory().GetCargo();
        if (!cargo) { return -1; }
        int count = cargo.GetItemCount();
        if (count > Survey.MaxCargoScan) { count = Survey.MaxCargoScan; }
        return count;
    }

    // "" = proceed, HCPickRunner.HOLD = wait this tick, else the abort reason that loses the trip.
    string HCRunHold(bool returning, HCScavengeState row)
    {
        if (!Survey || !row || !Houses) { return ""; }
        if (!Runner) { Runner = new HCPickRunner; }
        return Runner.HCRun(this, returning, row);
    }

    bool HCCarryPrepare(EntityAI goods, HCScavengeState row)
    {
        return Carry.HCPrepare(this, CustodyTrip, goods, row);
    }

    bool HCCarryResult(bool committed, HCScavengeState row)
    {
        return Carry.HCResult(this, CustodyTrip, committed, row);
    }

    string HCCarryUnload(HCScavengeState row)
    {
        return Carry.HCUnload(this, CustodyTrip, row);
    }

    // Existing vanilla crate at a surveyed anchor, found with one bounded native scan.
    ItemBase HCFindCrate(vector anchor)
    {
        array<Object> objects = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(anchor, Survey.ArrivalRangeMeters, objects, cargos);
        if (objects.Count() > Survey.MaxScannedObjects || cargos.Count() > Survey.MaxScannedObjects) { return null; }
        for (int scanIndex = 0; scanIndex < objects.Count(); scanIndex++)
        {
            ItemBase crate = ItemBase.Cast(objects[scanIndex]);
            if (crate && crate.IsKindOf("WoodenCrate") && HCAccessible(crate)) { return crate; }
        }
        return null;
    }

    // First real, takeable, identified item of a crate; no list, no copy, no synthesis.
    ItemBase HCFirstItem(EntityAI crate)
    {
        if (!crate || !crate.GetInventory()) { return null; }
        CargoBase cargo = crate.GetInventory().GetCargo();
        if (!cargo) { return null; }
        int count = cargo.GetItemCount();
        if (count > Survey.MaxCargoScan) { count = Survey.MaxCargoScan; }
        for (int cargoIndex = 0; cargoIndex < count; cargoIndex++)
        {
            ItemBase candidate = ItemBase.Cast(cargo.GetItem(cargoIndex));
            if (candidate && !candidate.IsRuined() && candidate.IsTakeable() && HCSearchSupplyRegistry.PersistentId(candidate) != "") { return candidate; }
        }
        return null;
    }

    // Binds nothing unless the actor, both crates and an item are all real.
    bool HCBindSurveyed(PlayerBase actor, HCPickerRoute route, string lease)
    {
        HCClear();
        if (!Survey || !actor || !route || lease == "") { return false; }
        ItemBase homeCrate = HCFindCrate(route.HCHomePoint());
        ItemBase sourceCrate = HCFindCrate(route.HCSourcePoint());
        if (!homeCrate || !sourceCrate || homeCrate == sourceCrate) { return false; }
        ItemBase stock = HCFirstItem(sourceCrate);
        if (!stock) { return false; }
        Actor = actor;
        Home = homeCrate;
        Source = sourceCrate;
        Item = stock;
        LeaseId = lease;
        return true;
    }

    bool HCPartyCurrent(HCScavengeState row)
    {
        if (!row) { return false; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(row.LeaseId);
        if (!HCAIPartyIdentity.HCValid(identity) || !HCMatches(row)) { return false; }
        return identity.HCPartyId() == row.PartyId && identity.HCCargoId() == row.CargoId && identity.HCGeneration() == row.Generation;
    }

    bool HCLive()
    {
        return GetGame() && GetGame().IsServer() && Actor && Actor.IsAlive() && !Actor.IsUnconscious() && !Actor.GetIdentity();
    }

    string HCOwner()
    {
        if (!Item) { return "unknown"; }
        EntityAI parent = Item.GetHierarchyParent();
        if (parent == Source && Source) { return HCSearchSupplyRegistry.PersistentId(Source); }
        if (parent == Home && Home) { return HCSearchSupplyRegistry.PersistentId(Home); }
        if (Actor && Item.GetHierarchyRootPlayer() == Actor) { return HCSearchSupplyRegistry.PersistentId(Actor); }
        return "unknown";
    }

    bool HCAtSource()
    {
        if (!HCLive() || !Source) { return false; }
        float sourceRange = Defaults.TransferRangeMeters;
        if (Survey) { sourceRange = Survey.ArrivalRangeMeters; }
        return vector.DistanceSq(Actor.GetPosition(), Source.GetPosition()) <= sourceRange * sourceRange;
    }

    bool HCAtHome()
    {
        if (!HCLive() || !Home) { return false; }
        float homeRange = Defaults.TransferRangeMeters;
        if (Survey) { homeRange = Survey.ArrivalRangeMeters; }
        return vector.DistanceSq(Actor.GetPosition(), Home.GetPosition()) <= homeRange * homeRange;
    }

    bool HCAccessible(EntityAI cache)
    {
        ItemBase crate = ItemBase.Cast(cache);
        if (!crate || crate.IsRuined() || crate.GetHierarchyParent() || crate.GetHierarchyRootPlayer()) { return false; }
        // Only inspected vanilla crate with no provider lock/attachment layout.
        if (!HCCampTheft.Unlocked(crate) || !HCLockTable.CampUnlocked(crate)) { return false; }
        return !crate.GetInventory().IsInventoryLocked();
    }

    bool HCMatches(HCScavengeState row)
    {
        if (!row || !Item || !Source || !Home || !Actor) { return false; }
        if (row.SourceId != HCSearchSupplyRegistry.PersistentId(Source) || row.HomeId != HCSearchSupplyRegistry.PersistentId(Home)) { return false; }
        return row.ItemId == HCSearchSupplyRegistry.PersistentId(Item) && row.ActorId == HCSearchSupplyRegistry.PersistentId(Actor);
    }

    // 2 readback confirmed, 3 ambiguous, 4 refused. Never retry or compensate.
    // Caller persists acquiring/depositing with unknown custody BEFORE entry.
    int HCMove(bool returning, HCScavengeState row)
    {
        if (!HCPartyCurrent(row) || !HCLive() || !Item || Item.IsRuined() || !Item.IsTakeable()) { return 4; }
        EntityAI destination = Actor;
        EntityAI expectedParent = Source;
        if (returning) { destination = Home; expectedParent = Actor; }
        if (!HCAccessible(Home) || !HCAccessible(Source)) { return 4; }
        if (returning && !HCAtHome()) { return 4; }
        if (!returning && !HCAtSource()) { return 4; }
        string expectedOwner = HCSearchSupplyRegistry.PersistentId(expectedParent);
        if (expectedOwner == "" || HCOwner() != expectedOwner) { return 4; }
        InventoryLocation before = new InventoryLocation;
        InventoryLocation target = new InventoryLocation;
        InventoryLocation current = new InventoryLocation;
        if (!Item.GetInventory().GetCurrentInventoryLocation(before)) { return 4; }
        if (!destination.GetInventory().FindFreeLocationFor(Item, FindInventoryLocationType.CARGO, target)) { return 4; }
        EntityAI targetParent = target.GetParent();
        if (!targetParent) { return 4; }
        if (returning && targetParent != Home) { return 4; }
        if (!returning && targetParent != Actor && targetParent.GetHierarchyRootPlayer() != Actor) { return 4; }
        // Inventory preflight may call other scripts. Recheck custody/locks/range.
        if (!HCPartyCurrent(row) || !HCLive() || !HCAccessible(Source) || !HCAccessible(Home)) { return 4; }
        if (returning && !HCAtHome()) { return 4; }
        if (!returning && !HCAtSource()) { return 4; }
        if (!Item || HCOwner() != expectedOwner) { return 4; }
        if (!Item.GetInventory().GetCurrentInventoryLocation(current) || !current.CompareLocationOnly(before)) { return 4; }
        string itemId = HCSearchSupplyRegistry.PersistentId(Item);
        string itemClass = Item.GetType();
        float quantity = Item.GetQuantity();
        bool moved = destination.GetInventory().TakeToDst(InventoryMode.SERVER, before, target);
        if (!Item || HCSearchSupplyRegistry.PersistentId(Item) != itemId || Item.GetType() != itemClass) { return 3; }
        if (Item.GetQuantity() != quantity) { return 3; }
        string destinationId = HCSearchSupplyRegistry.PersistentId(destination);
        if (moved && destinationId != "" && HCOwner() == destinationId) { return 2; }
        return 3;
    }

    void HCClear()
    {
        this.HCTheftCamp = null;
        this.HCTheftOwner = null;
        Actor = null;
        Source = null;
        Home = null;
        Item = null;
        LeaseId = "";
        if (Runner) { Runner.HCReset(this); }
        Carry.HCClear();
    }
}

class HCScavengeTrip
{
    ref HCScavengeState m_State;
    ref HCEncounterStore<HCScavengeState> m_Store;
    ref HCScavengeInventory m_IO;
    bool m_Ready;
    bool m_Busy;
    protected int m_Reports;

    void HCOpen()
    {
        m_Store = new HCEncounterStore<HCScavengeState>("hc34-scavenge");
        m_State = m_Store.Load(new HCScavengeState, "Phase");
        m_IO = new HCScavengeInventory;
        m_IO.CustodyTrip = this;
        if (!m_State || m_State.Version != 1) { return; }
        string phase = m_State.Phase;
        if (phase != "idle" && phase != "leaving" && phase != "acquiring" && phase != "returning" && phase != "depositing" && phase != "returned" && phase != "lost" && phase != "quarantined") { return; }
        m_Ready = true;
        HCRestore();
    }

    // #201: substitute only an observed local source before the first debit.
    // The existing HCStep owns acquire/return intents and the same-item TakeToDst.
    // One item per trip is the existing structural custody ceiling.
    string HCTheftPickup(HCCampModule owner, HCCampRecord camp, ItemBase crate, int now, int dailyLimit)
    {
        if (!m_Ready || m_Busy || !m_State || !m_IO) { return "THEFT_PICKER_UNAVAILABLE"; }
        if (m_State.Phase != "leaving" || m_IO.HCTheftCamp) { return "THEFT_NO_EMPTY_TRAVELLING_PARTY"; }
        if (!m_IO.HCPartyCurrent(m_State) || !m_IO.HCLive()) { return "THEFT_PARTY_LEASE_LOST"; }
        if (!m_IO.HCTheftNear(crate)) { return "THEFT_NO_PARTY_NEAR_CAMP"; }
        if (!HCCampTheft.HCAllowed(owner, camp, crate)) { return "THEFT_ATTENDED_OR_OBSERVED"; }
        if (crate == m_IO.Home) { return "THEFT_SOURCE_IS_HOME"; }
        int today = now / 86400;
        if (now < 1 || today < m_State.HCTheftDay) { return "THEFT_CLOCK_ROLLBACK"; }
        if (m_State.HCTheftAttempts < 0 || dailyLimit < 1) { return "THEFT_DAILY_CAP"; }
        if (today == m_State.HCTheftDay && m_State.HCTheftAttempts >= dailyLimit) { return "THEFT_DAILY_CAP"; }
        ItemBase stock = m_IO.HCTheftFirstItem(crate);
        if (!HCCampTheft.SafeItem(stock)) { return "THEFT_SAFE_STOCK_ABSENT"; }
        string sourceId = HCSearchSupplyRegistry.PersistentId(crate);
        string itemId = HCSearchSupplyRegistry.PersistentId(stock);
        if (sourceId == "" || itemId == "") { return "THEFT_PERSISTENT_ID_ABSENT"; }
        // Two stores cannot be atomic with Hive. A partial barrier spends the
        // opportunity conservatively; never roll back/replay a native transfer.
        camp.LastTheft = now;
        if (!owner.Commit(now)) { return "THEFT_CAMP_STORE_UNAVAILABLE"; }
        if (today != m_State.HCTheftDay) { m_State.HCTheftAttempts = 0; }
        m_State.HCTheftDay = today;
        m_State.HCTheftAttempts = m_State.HCTheftAttempts + 1;
        m_IO.Source = crate;
        m_IO.Item = stock;
        m_IO.HCTheftCamp = camp;
        m_IO.HCTheftOwner = owner;
        m_State.SourceId = sourceId;
        m_State.ItemId = itemId;
        m_State.CargoOwner = sourceId;
        if (!HCCheckpoint()) { return "THEFT_JOURNAL_UNCERTAIN"; }
        HCStep();
        return "";
    }

    bool HCCheckpoint()
    {
        if (!m_Ready || !m_State || !m_Store.Save(m_State))
        {
            m_Ready = false;
            if (m_State) { m_State.Phase = "quarantined"; m_State.CargoOwner = "unknown"; m_State.Refusal = "JOURNAL_UNCERTAIN"; }
            return false;
        }
        HCLog();
        return true;
    }

    bool HCLeave(HCAIPartyIdentity identity, string lease, string sourceId, string actorId, string homeId, string itemId)
    {
        if (!m_Ready || m_Busy || !m_State || m_State.Phase != "idle" || !m_IO) { return false; }
        if (!HCAIPartyIdentity.HCValid(identity) || lease == "" || sourceId == "" || actorId == "" || homeId == "" || itemId == "") { return false; }
        if (sourceId == homeId || actorId == sourceId || actorId == homeId) { return false; }
        // The provider must bind real handles, the current lease and the exact
        // surveyed route before this durable departure barrier.
        if (!m_IO.HCRouteReady(identity, lease)) { return false; }
        m_State.HouseGoods = null;
        m_State.PartyId = identity.HCPartyId();
        m_State.RouteId = identity.HCRouteId();
        m_State.CargoId = identity.HCCargoId();
        m_State.Generation = identity.HCGeneration();
        m_State.LeaseId = lease;
        m_State.SourceId = sourceId;
        m_State.ActorId = actorId;
        m_State.HomeId = homeId;
        m_State.ItemId = itemId;
        m_State.CargoOwner = sourceId;
        m_State.Phase = "leaving";
        if (!HCCheckpoint()) { return false; }
        if (!m_IO.HCWalk(false)) { HCLose("DEPARTURE_UNOBSERVED"); return false; }
        return m_Ready && m_State.Phase == "leaving";
    }

    void HCLose(string reason)
    {
        if (!m_Ready || !m_State || m_State.Phase == "idle" || m_State.Phase == "quarantined" || m_State.Phase == "lost") { return; }
        m_State.Phase = "lost";
        m_State.Refusal = reason;
        m_State.CargoOwner = m_IO.HCOwner();
        if (m_Busy) { m_State.Phase = "quarantined"; m_State.CargoOwner = "unknown"; }
        HCCheckpoint();
    }

    void HCRestore()
    {
        if (!m_Ready || !m_State || m_State.Phase == "idle" || m_State.Phase == "lost" || m_State.Phase == "quarantined") { return; }
        // Hive/journal are not one atomic store. No body/inventory rebind API
        // has been qualified: retain uncertainty, including a stale return.
        m_State.Phase = "quarantined";
        m_State.CargoOwner = "unknown";
        m_State.Refusal = "PAIRED_NATIVE_RESTORE_UNPROVEN";
        HCCheckpoint();
    }

    void HCStep()
    {
        if (!m_Ready || m_Busy || !m_State || !m_IO) { return; }
        bool returning = m_State.Phase == "returning";
        if (!returning && m_State.Phase != "leaving") { return; }
        if (!m_IO.HCPartyCurrent(m_State)) { HCLose("PARTY_LEASE_LOST"); return; }
        if (!m_IO.HCLive()) { HCLose("CARRIER_LOST"); return; }
        string expected = m_State.SourceId;
        if (returning) { expected = m_State.ActorId; }
        if (m_IO.HCOwner() != expected) { HCLose("CARGO_LOST"); return; }
        // #144: combat abort and the bounded house stage. HCLose keeps cargo where it is.
        string hold = m_IO.HCRunHold(returning, m_State);
        if (hold == HCPickRunner.HOLD) { return; }
        if (hold != "") { HCLose(hold); return; }
        if (returning && !m_IO.HCAtHome()) { return; }
        if (!returning && !m_IO.HCAtSource()) { return; }
        m_Busy = true;
        m_State.Phase = "acquiring";
        if (returning) { m_State.Phase = "depositing"; }
        m_State.CargoOwner = "unknown";
        if (!HCCheckpoint()) { m_Busy = false; return; }
        int result = m_IO.HCMove(returning, m_State);
        // Stop/cancel may run inside native callbacks. Never overwrite their
        // terminal evidence with a late success from the interrupted move.
        if (!m_Ready || (m_State.Phase != "acquiring" && m_State.Phase != "depositing")) { m_Busy = false; return; }
        string owner = m_IO.HCOwner();
        string target = m_State.ActorId;
        if (returning) { target = m_State.HomeId; }
        if (result == 2 && owner == target)
        {
            m_State.Phase = "returning";
            if (returning) { m_State.Phase = "returned"; }
            m_State.CargoOwner = owner;
            if (HCCheckpoint() && !returning)
            {
                if (!m_IO.HCWalk(true)) { HCLose("RETURN_ROUTE_UNOBSERVED"); }
            }
        }
        else
        {
            m_State.Phase = "quarantined";
            m_State.CargoOwner = "unknown";
            m_State.Refusal = "NATIVE_TRANSFER_UNCERTAIN";
            if (result == 4) { m_State.Phase = "lost"; m_State.CargoOwner = owner; m_State.Refusal = "NATIVE_TRANSFER_REFUSED"; }
            HCCheckpoint();
        }
        m_Busy = false;
    }

    // Observation only: no logical stock credit, no item list, no replay token.
    // A future HC-16 credit needs a shared durable continuation, not two saves.
    bool HCConfirmedReturn()
    {
        if (!m_Ready || m_Busy || !m_State || m_State.Phase != "returned") { return false; }
        return m_IO.HCPartyCurrent(m_State) && m_IO.HCOwner() == m_State.HomeId;
    }

    void HCLog()
    {
        if (!m_State || m_Reports >= 16) { return; }
        m_Reports++;
        string line = "[HC Plan] HC-34 party=" + m_State.PartyId + " phase=" + m_State.Phase;
        line += " cargo_owner=" + m_State.CargoOwner + " state=refused count=1 refusal=" + m_State.Refusal;
        Print(line + " runtime=PENDING");
    }

    void HCClose()
    {
        // No inventory deletion/refund on stop, death or cancellation.
        m_Ready = false;
        if (m_IO) { m_IO.HCClear(); }
    }
}

// w29-debugmap #194: detached read-only row for the `pickers` debug layer. Phase,
// the locator that produced the position, and the position only: no party, cargo,
// actor, source or home ids and no entity handles leave the owner.
class HCDebugPickerRow
{
    string Phase;
    string Locator = "none";
    bool HasPosition;
    vector Position;
    int Generation;
}

class HCPickers : HCModule
{
    protected static HCPickers s_Instance;
    protected ref HCScavengeTrip m_Trip;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_WorkBudget = new HCWorkBudget;
    protected ref HCPickerSurvey m_Survey;
    protected string m_SurveyRefusal;
    protected bool m_ProviderLogged;
    // #144: the module owns remembered danger and the house port across port rebinds.
    protected ref HCPickDanger m_Danger = new HCPickDanger;
    protected ref HCPickHousePort m_Houses = new HCPickSearchHousePort;
    protected bool m_RunsOn;

    static HCPickers Get() { return s_Instance; }
    HCScavengeTrip HCTrip() { return m_Trip; }
    override string GetName() { return "Pickers"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    override void OnStart(HCSettings settings)
    {
        if (!settings || !settings.EnableEncounters)
        {
            m_Status.HCPublish("off", "operator_disabled");
            Print("[HC Plan] HC-34 party=none phase=off cargo_owner=none state=off count=0 runtime=PENDING");
            return;
        }
        if (!GetGame() || !GetGame().IsServer()) { return; }
        Print(HCV2Admission.Line("Pickers", true, "EXP-L5", HCV2Gates.Qualified("EXP-L5")));
        m_Trip = new HCScavengeTrip;
        m_Trip.HCOpen();
        s_Instance = this;
        m_Survey = HCPickerSurvey.HCLoad(m_SurveyRefusal);
        if (m_Trip.m_IO)
        {
            m_Trip.m_IO.Survey = m_Survey;
            m_Trip.m_IO.Danger = m_Danger;
            m_Trip.m_IO.Houses = m_Houses;
        }
        m_RunsOn = HCPickPolicy.Enabled();
        HCPublishReadiness();
        string phase = "idle";
        if (m_Trip.m_State) { phase = m_Trip.m_State.Phase; }
        string survey = "routes=0";
        if (m_Survey) { survey = "routes=" + m_Survey.Routes.Count().ToString(); }
        Print("[HC Plan] HC-34 party=none phase=" + phase + " cargo_owner=none state=" + m_Status.HCState() + " count=0 " + survey + " reason=" + m_Status.HCReason() + " runtime=PENDING");
        HCLogProvider();
        HCLogRuns();
    }

    // One start line per boot and one per house-port bind, derived from the live state.
    void HCLogRuns()
    {
        string line = "[HC Pickers] runs enabled=" + m_RunsOn.ToString() + " opt_out=scavenge_runs.disable";
        if (m_Survey) { line += " members=" + m_Survey.RunMinMembers.ToString() + "-" + m_Survey.RunMaxMembers.ToString() + " houses_per_run=" + m_Survey.RunMaxHousesPerRun.ToString(); }
        string housePort = m_Houses.HCRefusal();
        if (housePort == "") { housePort = "bound"; }
        if (m_Survey) { line += " carry_cap=" + m_Survey.RunMaxCarriedHouseGoods.ToString(); }
        Print(line + " house_port=" + housePort + " runtime=PENDING");
    }

    // Derived from the real journal and survey state; never hard-coded.
    void HCPublishReadiness()
    {
        string state = "ready";
        string reason = "journal_and_survey_loaded";
        if (!m_Trip || !m_Trip.m_Ready)
        {
            state = "refused";
            reason = "HC34_JOURNAL_UNAVAILABLE";
        }
        else if (!m_Survey)
        {
            state = "degraded";
            reason = m_SurveyRefusal;
        }
        if (m_Status.HCState() != state || m_Status.HCReason() != reason) { m_Status.HCPublish(state, reason); }
    }

    // The one part this module cannot supply itself, named once (derived from the bound port).
    void HCLogProvider()
    {
        if (m_ProviderLogged || !m_Trip || !m_Trip.m_IO) { return; }
        m_ProviderLogged = true;
        string gap = m_Trip.m_IO.HCWalkRefusal();
        if (gap == "")
        {
            Print("[HC Pickers] provider walk=bound runtime=PENDING");
            return;
        }
        Print("[HC Pickers] provider walk=unbound reason=" + gap + " parts_ready=journal,survey,bind,tick runtime=PENDING");
    }

    // Addon seam: bind a port whose HCWalk drives the group. Only between trips.
    bool HCBindProvider(HCScavengeInventory port)
    {
        if (!port || !m_Trip || !m_Trip.m_Ready || m_Trip.m_Busy || !m_Trip.m_State || m_Trip.m_State.Phase != "idle") { return false; }
        port.Survey = m_Survey;
        port.Danger = m_Danger;
        port.Houses = m_Houses;
        port.CustodyTrip = m_Trip;
        m_Trip.m_IO = port;
        m_ProviderLogged = false;
        HCLogProvider();
        return true;
    }

    // Addon/integration seam: the shared house reservation bridge. Only between trips.
    bool HCBindHousePort(HCPickHousePort port)
    {
        if (!port || !m_Trip || !m_Trip.m_Ready || m_Trip.m_Busy || !m_Trip.m_State || m_Trip.m_State.Phase != "idle") { return false; }
        m_Houses = port;
        if (m_Trip.m_IO) { m_Trip.m_IO.Houses = port; }
        HCLogRuns();
        return true;
    }

    // #144 party-size bound (2..4 by survey); "" when runs are off or the size is in range.
    string HCPartyRefusal(int members)
    {
        if (!m_RunsOn) { return ""; }
        return HCPickPolicy.PartyRefusal(m_Survey, members);
    }

    int HCRecheckSeconds()
    {
        if (!m_Survey) { return 0; }
        return m_Survey.RunNeedRecheckSeconds;
    }

    // HC-18 lifecycle entry, never a scheduler. The site keeps its per-party
    // cooldown while materialised; the last terminal journal carries it across
    // restart. A quarantined journal is never rearmed automatically.
    string HCTryParty(HCAIPartyIdentity identity, string lease, PlayerBase actor, int now, int eligibleAt)
    {
        if (!GetGame() || !GetGame().IsServer()) { return "PICKER_NOT_SERVER"; }
        if (!m_Trip || !m_Trip.m_Ready || !m_Trip.m_State || !m_Trip.m_IO || !m_Survey) { return "PICKER_NOT_READY"; }
        if (!HCAIPartyIdentity.HCValid(identity) || lease == "" || !actor) { return "PICKER_IDENTITY_INVALID"; }
        HCScavengeState row = m_Trip.m_State;
        string phase = row.Phase;
        if (phase == "quarantined") { return "PICKER_JOURNAL_QUARANTINED"; }
        HCPickerRoute route = m_Survey.HCFind(identity.HCRouteId());
        if (m_Trip.m_Busy || (phase != "idle" && phase != "returned" && phase != "lost"))
        {
            // #144: another party's live run is named by the cap that holds it. The single
            // HC-34 journal admits one trip, so the world cap is the structural limit.
            if (m_RunsOn && route && HCPickPolicy.ActiveTrip(phase) && row.PartyId != identity.HCPartyId())
            {
                int liveInCamp = 0;
                HCPickerRoute liveRoute = m_Survey.HCFind(row.RouteId);
                if (liveRoute && liveRoute.LocalityId == route.LocalityId) { liveInCamp = 1; }
                string capped = HCPickPolicy.CapRefusal(m_Survey, route, 1, liveInCamp);
                if (capped != "") { return capped; }
            }
            return "PICKER_TRIP_ACTIVE";
        }
        if (m_Trip.m_IO.Defaults.MaxConcurrentTrips < 1) { return "PICKER_GLOBAL_CAP"; }
        if (!route) { return "PICKER_ROUTE_UNSURVEYED"; }
        // Last terminal receipt may conservatively hold other parties too;
        // never discard it early just to admit another lease.
        if (now <= 0 || now < eligibleAt || now < row.NextTripAt) { return "PICKER_PARTY_COOLDOWN"; }
        if (m_RunsOn)
        {
            // #144 danger from the party's own clues and remembered noise, never from players.
            string refusal = HCPickPolicy.RouteDanger(m_Survey, m_Danger, route, now);
            if (refusal != "") { return refusal; }
        }
        float arrival = m_Survey.ArrivalRangeMeters;
        if (vector.DistanceSq(actor.GetPosition(), route.HCHomePoint()) > arrival * arrival) { return "PICKER_NOT_AT_HOME"; }
        if (!HCServer.HCTickWork().HCTake(1)) { return "PICKER_WORK_BUDGET"; }
        if (phase == "returned" || phase == "lost")
        {
            m_Trip.m_IO.HCClear();
            row.Phase = "idle";
            row.Refusal = "";
            if (!m_Trip.HCCheckpoint()) { return "PICKER_JOURNAL_UNAVAILABLE"; }
        }
        return HCBeginSurveyed(identity, lease, actor);
    }

    // Provider entry: begin the one journaled trip for this exact lease and a live actor.
    // Returns "" when the trip left, else the named refusal. One native bind + one journal write.
    string HCBeginSurveyed(HCAIPartyIdentity identity, string lease, PlayerBase actor)
    {
        if (m_Trip) { HCPublishReadiness(); }
        if (!m_Trip || !m_Trip.m_Ready || !m_Trip.m_IO || !m_Trip.m_State || !m_Survey) { return "PICKER_NOT_READY"; }
        // Admission must precede binding: rejected requests retain the active custody chain.
        if (m_Trip.m_Busy || m_Trip.m_State.Phase != "idle") { return "PICKER_LEAVE_REFUSED"; }
        if (!actor || !HCAIPartyIdentity.HCValid(identity) || lease == "") { return "PICKER_IDENTITY_INVALID"; }
        m_Units.HCReset(1);
        if (!m_Units.HCTake(1)) { return "PICKER_BUDGET"; }
        HCPickerRoute route = m_Survey.HCFind(identity.HCRouteId());
        if (!route) { return "PICKER_ROUTE_UNSURVEYED"; }
        HCScavengeInventory port = m_Trip.m_IO;
        if (!port.HCBindSurveyed(actor, route, lease)) { port.HCClear(); return "PICKER_ANCHOR_STOCK_ABSENT"; }
        // #144/#150: a run starts only for a camp need; the target scales with the season phase.
        int seasonPhase = -1;
        int stash = -1;
        if (m_RunsOn)
        {
            seasonPhase = HCPickPolicy.SeasonPhase();
            stash = port.HCStashItems();
            if (!HCPickPolicy.NeedsSupplies(m_Survey, stash, seasonPhase)) { port.HCClear(); return HCPickPolicy.NEED_REFUSAL; }
        }
        // Reject an unbound walk before journal departure; keep the named cause.
        string walkRefusal = port.HCWalkRefusal();
        if (walkRefusal != "") { port.HCClear(); return walkRefusal; }
        string sourceId = HCSearchSupplyRegistry.PersistentId(port.Source);
        string homeId = HCSearchSupplyRegistry.PersistentId(port.Home);
        string itemId = HCSearchSupplyRegistry.PersistentId(port.Item);
        string actorId = HCSearchSupplyRegistry.PersistentId(port.Actor);
        bool left = m_Trip.HCLeave(identity, lease, sourceId, actorId, homeId, itemId);
        HCPublishReadiness();
        if (!left) { port.HCClear(); return "PICKER_LEAVE_REFUSED"; }
        if (m_RunsOn)
        {
            string needLine = "[HC Pickers] run start party=" + identity.HCPartyId() + " route=" + identity.HCRouteId() + " stash=" + stash.ToString();
            needLine += " target=" + HCPickPolicy.NeedTarget(m_Survey, seasonPhase).ToString() + " season=" + HCSeasonVisualPolicy.HCPhaseName(seasonPhase);
            Print(needLine + " runtime=PENDING");
        }
        return "";
    }

    // w29-debugmap #194: read-only debug seam. One picker trip at most; a trip in
    // any phase but idle is listed (quarantined/lost ones have no position and the
    // layer counts them `unplaced`). Never steps, saves, scans houses or players.
    // Runtime acceptance pending; the survey is design input, not runtime proof.
    int HCDebugPickerCount()
    {
        // m_Ready false = the journal is unavailable or invalid: no row, whatever the phase text.
        if (!m_Trip || !m_Trip.m_Ready || !m_Trip.m_State) { return 0; }
        if (m_Trip.m_State.Phase == "idle") { return 0; }
        return 1;
    }

    // Detached copy: position from the live carrier, else the source, else home.
    HCDebugPickerRow HCDebugPicker(int wanted)
    {
        if (wanted != 0 || !m_Trip || !m_Trip.m_Ready || !m_Trip.m_State || !m_Trip.m_IO) { return null; }
        if (m_Trip.m_State.Phase == "idle") { return null; }
        HCDebugPickerRow row = new HCDebugPickerRow;
        row.Phase = m_Trip.m_State.Phase;
        row.Generation = m_Trip.m_State.Generation;
        HCScavengeInventory inventory = m_Trip.m_IO;
        if (inventory.HCLive())
        {
            row.Locator = "actor";
            row.HasPosition = true;
            row.Position = inventory.Actor.GetPosition();
        }
        else if (inventory.Source)
        {
            row.Locator = "source";
            row.HasPosition = true;
            row.Position = inventory.Source.GetPosition();
        }
        else if (inventory.Home)
        {
            row.Locator = "home";
            row.HasPosition = true;
            row.Position = inventory.Home.GetPosition();
        }
        return row;
    }

    override void OnTick(float deltaTime)
    {
        // Preserve off status when no trip was started. Refresh before every tick early return.
        if (m_Trip) { HCPublishReadiness(); }
        // Refused/off path does not scan houses, players, inventory or saves.
        if (!m_Trip || !m_Trip.m_Ready || !m_Trip.m_State) { return; }
        if (m_Trip.m_State.Phase != "leaving" && m_Trip.m_State.Phase != "returning") { return; }
        m_Units.HCReset(1);
        m_WorkBudget.HCReset(1);
        if (!m_Units.HCTake(1) || !m_WorkBudget.HCContinue()) { return; }
        m_Trip.HCStep();
        HCReached.Mark("pickers.trip_step");
        HCPublishReadiness();
    }

    override void OnStop()
    {
        if (m_Trip) { m_Trip.HCClose(); }
        if (s_Instance == this) { s_Instance = null; }
        m_Status.HCPublish("off", "server_stop_requested");
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCPickers);
    }
}
