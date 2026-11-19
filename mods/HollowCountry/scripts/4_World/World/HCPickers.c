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
// Provider source/route missing: explicit refusal, runtime acceptance PENDING.
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
    override bool Open(string sourceId, string sourcePin, string worldName, string build)
    {
        if (m_Open || m_Fault || !GetGame().IsServer()) return false;
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
// N17 is NOT an AI SDK. Installed Expansion source directory supplied for this
// worker is absent. HCRouteReady/HCWalk explicitly refuse; no invented movement.
// All checkpoint writes are transaction barriers, synchronous verified store
// writes. No periodic state changes/save job; no second scheduler is needed.
class HCScavengeDefaults
{
    // Native search pickup is 2.5 m (HCSearchNativeSupply), 0.25% of the
    // approximately 1000 m network bubble/rifle report range. Not perception.
    float TransferRangeMeters = 2.5;
}

class HCScavengeState
{
    int Version = 1;
    string Phase = "idle";
    string PartyId;
    string CargoId;
    int Generation;
    string LeaseId;
    string SourceId;
    string ActorId;
    string HomeId;
    string ItemId;
    string CargoOwner;
    string Refusal;
}

// Trusted server native inventory port. Handles are never restored from JSON.
// The provider adapter must supply a real, surveyed route before overriding the
// two refusal ports. A preference, radius or client assertion cannot do that.
class HCScavengeInventory
{
    PlayerBase Actor;
    EntityAI Source;
    EntityAI Home;
    ItemBase Item;
    string LeaseId;
    ref HCScavengeDefaults Defaults = new HCScavengeDefaults;

    bool HCRouteReady(HCAIPartyIdentity identity, string lease) { return false; }
    bool HCWalk(bool returning) { return false; }

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
        return vector.DistanceSq(Actor.GetPosition(), Source.GetPosition()) <= Defaults.TransferRangeMeters * Defaults.TransferRangeMeters;
    }

    bool HCAtHome()
    {
        if (!HCLive() || !Home) { return false; }
        return vector.DistanceSq(Actor.GetPosition(), Home.GetPosition()) <= Defaults.TransferRangeMeters * Defaults.TransferRangeMeters;
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
        Actor = null;
        Source = null;
        Home = null;
        Item = null;
        LeaseId = "";
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
        if (!m_State || m_State.Version != 1) { return; }
        string phase = m_State.Phase;
        if (phase != "idle" && phase != "leaving" && phase != "acquiring" && phase != "returning" && phase != "depositing" && phase != "returned" && phase != "lost" && phase != "quarantined") { return; }
        m_Ready = true;
        HCRestore();
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
        // No route is enabled in this source slice. Later provider qualification
        // MUST bind these handles, the current identity and surveyed route here.
        if (!m_IO.HCRouteReady(identity, lease)) { return false; }
        m_State.PartyId = identity.HCPartyId();
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

class HCPickers : HCModule
{
    protected static HCPickers s_Instance;
    protected ref HCScavengeTrip m_Trip;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_WorkBudget = new HCWorkBudget;

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
        m_Status.HCPublish("refused", "HC34_PROVIDER_SOURCE_MISSING_ROUTE_UNSURVEYED");
        if (!m_Trip.m_Ready) { m_Status.HCPublish("refused", "HC34_JOURNAL_UNAVAILABLE"); }
        Print("[HC Plan] HC-34 party=none phase=idle cargo_owner=none state=refused count=0 refusal=PROVIDER_SOURCE_MISSING_ROUTE_UNSURVEYED runtime=PENDING");
    }

    override void OnTick(float deltaTime)
    {
        // Refused/off path does not scan houses, players, inventory or saves.
        if (!m_Trip || !m_Trip.m_Ready || !m_Trip.m_State) { return; }
        if (m_Trip.m_State.Phase != "leaving" && m_Trip.m_State.Phase != "returning") { return; }
        m_Units.HCReset(1);
        m_WorkBudget.HCReset(1);
        if (!m_Units.HCTake(1) || !m_WorkBudget.HCContinue()) { return; }
        m_Trip.HCStep();
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
