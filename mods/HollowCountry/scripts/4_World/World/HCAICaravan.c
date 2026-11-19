// HC-36/#145 spec -> plan -> task: HC-18 locality + HC-35 finite native cargo
// -> one surveyed walking corridor -> observed outbound/return or retained loss.
// Adjunct of the EXISTING AI lifecycle; no registry/config/module addition.
// HC-10 keeps party/cargo identity and the shared population reservation.
// Reuse HCTradeInventory's native item/actor IDs and handle cleanup. One existing
// stack is the finite supply slice; no stock grants, debits, copies or transfer UI.
// HCEncounterStore uses verified intent/backup/copy/readback, NOT atomic with
// Hive. These are synchronous transition barriers; no routine dirty/save loop.
// HCSaveScheduler remains the sole routine save owner. Back up Hive + journals.
// Native scripts-1.30.164289, inspected N1/N2/N17:
// 3_Game/Global/Game.c:1120 IsServer; gameplay.c:636 GetGame;
// 3_Game/Entities/Object.c:467 GetType, :517 IsAlive, :1219 IsRuined;
// Entities/EntityAI.c:882 GetHierarchyRootPlayer, :3374 GetPersistentID
// (via existing HCSearchSupplyRegistry.PersistentId / HCTradeInventory);
// Entities/Man.c:21 GetIdentity; 4_World/Entities/ManBase/PlayerBase.c:3925
// IsUnconscious; Entities/ItemBase.c:3490 GetQuantity;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnString.c:199
// Length; EnConvert.c:30 ToString; EnDebug.c:96 Print.
// Wave 6: N1 3_Game/Global/Game.c:914 GetTickTime (seconds, monotonic
// within a process); EnScript.c:380,407,470 Count/Insert/RemoveOrdered.
// The addon now binds installed-road walking callbacks. Geometry, combat
// recovery and two-client observations remain admitted unverified.
// All status lines below are proposed diagnostics; runtime acceptance PENDING.
// Wave 8 #185: fresh idle-stock ceilings, terminal-history retention upgrades
// and failed-provider-bind cleanup; the same custody/save barriers still apply.

class HCCaravanCorridor
{
    int Version = 1;
    string CorridorId = "hc36-first-corridor";
    string FromCamp;
    string ToCamp;
    string SurveySha256;
    // 0.25% of the approximately 1000 m vanilla network bubble/rifle report
    // range, capped by the existing native pickup envelope. NOT perception.
    float ArrivalRangeMeters = 2.5;
    int CooldownSeconds = 900;
    // Includes the current trip; only oldest terminal receipts can be evicted.
    int MaxTripHistory = 16;

    // Read the installed Expansion data in bounded slices. No redistributed
    // road geometry, invented survey hash or native verdict in mission data.
    string RoadDataPath = "DayZExpansion/AI/Scripts/Data/Roads/ChernarusPlus.roads";
    int RoadMapWidth = 14200;
    int RoadMapHeight = 15500;
    int MaxRoadNodes = 40000;
    int MaxRoadDegree = 8;
    int RoadWorkPerTick = 256;
    int RoadNodesPerWorkUnit = 8;
    int MaxRouteNodes = 128;
    float MaxApproachMeters = 100;
    float MaxJourneyMeters = 250;
    int ReturnTimeoutSeconds = 600;

    void HCApplyDefaults(string encoded)
    {
        if (!HCJsonFields.Has(encoded, "ReturnTimeoutSeconds")) { ReturnTimeoutSeconds = 600; }
        if (!HCJsonFields.Has(encoded, "RoadDataPath")) { RoadDataPath = "DayZExpansion/AI/Scripts/Data/Roads/ChernarusPlus.roads"; }
        if (!HCJsonFields.Has(encoded, "RoadMapWidth")) { RoadMapWidth = 14200; }
        if (!HCJsonFields.Has(encoded, "RoadMapHeight")) { RoadMapHeight = 15500; }
        if (!HCJsonFields.Has(encoded, "MaxRoadNodes")) { MaxRoadNodes = 40000; }
        if (!HCJsonFields.Has(encoded, "MaxRoadDegree")) { MaxRoadDegree = 8; }
        if (!HCJsonFields.Has(encoded, "RoadNodesPerWorkUnit")) { RoadNodesPerWorkUnit = 8; }
        if (!HCJsonFields.Has(encoded, "RoadWorkPerTick")) { RoadWorkPerTick = 256; }
        if (!HCJsonFields.Has(encoded, "MaxRouteNodes")) { MaxRouteNodes = 128; }
        if (!HCJsonFields.Has(encoded, "MaxApproachMeters")) { MaxApproachMeters = 100; }
        if (!HCJsonFields.Has(encoded, "MaxJourneyMeters")) { MaxJourneyMeters = 250; }
    }
    bool HCNetworkValid()
    {
        if (RoadDataPath != "DayZExpansion/AI/Scripts/Data/Roads/ChernarusPlus.roads") { return false; }
        if (RoadMapWidth != 14200 || RoadMapHeight != 15500) { return false; }
        if (MaxRoadNodes < 1 || MaxRoadNodes > 50000 || MaxRoadDegree < 1 || MaxRoadDegree > 16) { return false; }
        if (RoadWorkPerTick < 1 || RoadWorkPerTick > 512 || MaxRouteNodes < 2 || MaxRouteNodes > 256) { return false; }
        if (RoadNodesPerWorkUnit < 1 || RoadNodesPerWorkUnit > 16) { return false; }
        if (ReturnTimeoutSeconds < 60 || ReturnTimeoutSeconds > 3600) { return false; }
        return MaxApproachMeters > 0 && MaxApproachMeters <= 200 && MaxJourneyMeters > 0 && MaxJourneyMeters <= 400;
    }

    bool HCValid()
    {
        HCScavengeDefaults pickup = new HCScavengeDefaults;
        // Native JSON zero-fills fields missing from legacy version-1 input.
        if (CooldownSeconds == 0) { CooldownSeconds = 900; }
        if (MaxTripHistory == 0) { MaxTripHistory = 16; }
        // Missing JSON int zero is explicitly rejected; no legacy upgrade.
        if (Version != 1 || CorridorId != "hc36-first-corridor") { return false; }
        if (FromCamp.Length() > 96 || ToCamp.Length() > 96 || SurveySha256.Length() > 64) { return false; }
        if (CooldownSeconds < 1 || CooldownSeconds > 604800) { return false; }
        if (MaxTripHistory < 1 || MaxTripHistory > 64) { return false; }
        return ArrivalRangeMeters > 0 && ArrivalRangeMeters <= pickup.TransferRangeMeters;
    }

    string HCAdmissionRefusal()
    {
        if (!HCValid()) { return "CARAVAN_CONFIG_INVALID"; }
        if (!HCWorldLimits.Token(FromCamp) || !HCWorldLimits.Token(ToCamp)) { return "CARAVAN_CORRIDOR_UNSURVEYED"; }
        if (FromCamp == ToCamp) { return "CARAVAN_CORRIDOR_UNSURVEYED"; }
        // A hash in JSON is an input, never provider/survey qualification.
        return "";
    }
}

// Small immutable terminal receipt, not a nested live trip or cargo grant.
class HCCaravanReceipt
{
    string Id;
    int TripSequence;
    string Leg;
    string CargoReceipt;
    string ItemId;
    float Quantity;
}

class HCCaravanState
{
    int Version = 1;
    string Id;
    string Leg = "idle";
    string CargoReceipt = "none";
    string Refusal;
    string LeaseId;
    string PartyId;
    string CargoId;
    string RouteId;
    int Generation;
    string ActorId;
    string ItemId;
    string ItemClass;
    float Quantity;
    // Missing legacy sequence 0 retains the old corridor-id tombstone. New
    // identities always advance; evicting history never resets this counter.
    int TripSequence;
    ref array<ref HCCaravanReceipt> History = new array<ref HCCaravanReceipt>;
}

// Trusted server port: only the existing director can bind its current HC-10
// role/body/item. No RPC, profile flag or JSON observation qualifies the port.
class HCCaravanInventory : HCTradeInventory
{
    ref HCCaravanCorridor Corridor;
    override bool HCReady() { return false; }
    override string HCRefusal() { return "CARAVAN_PROVIDER_CALLBACKS_UNVERIFIED"; }
    bool HCBindCaravan(HCCaravanState row) { return false; }
    bool HCWalkCaravan(HCCaravanState row, bool returning) { return false; }
    bool HCAtCamp(HCCaravanState row, bool returning) { return false; }
    bool HCFleeObserved(HCCaravanState row) { return false; }

    override bool HCLive()
    {
        if (!GetGame() || !GetGame().IsServer() || !LeftActor || LeftActor.GetIdentity()) { return false; }
        return LeftActor.IsAlive() && !LeftActor.IsUnconscious();
    }

    bool HCCurrentCaravan(HCCaravanState row)
    {
        if (!row || !LeftActor || HCActorId(true) != row.ActorId) { return false; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(row.LeaseId);
        if (!HCAIPartyIdentity.HCValid(identity)) { return false; }
        if (identity.HCPartyId() != row.PartyId || identity.HCCargoId() != row.CargoId) { return false; }
        return identity.HCGeneration() == row.Generation && identity.HCRouteId() == row.RouteId;
    }

    string HCCargoReceipt(HCCaravanState row)
    {
        // Missing handles are uncertainty, never evidence of theft or a new item.
        if (!GetGame() || !GetGame().IsServer() || !row || !LeftItem || !LeftActor) { return "unknown"; }
        if (HCItemId(true) != row.ItemId || HCActorId(true) != row.ActorId) { return "unknown"; }
        if (LeftItem.GetType() != row.ItemClass) { return "unknown"; }
        if (LeftItem.GetHierarchyRootPlayer() != LeftActor || LeftItem.IsRuined()) { return "lost"; }
        // A depleted/split stack cannot be silently refilled. No inventory move.
        if (LeftItem.GetQuantity() < row.Quantity) { return "lost"; }
        if (LeftItem.GetQuantity() != row.Quantity) { return "unknown"; }
        return "retained";
    }

    float HCRemainingQuantity(HCCaravanState row)
    {
        // Read only the same observed native item. Unknown never grants stock;
        // loss of custody/ruin consumes the remaining ceiling conservatively.
        if (HCCargoReceipt(row) == "unknown") { return -1; }
        if (LeftItem.GetHierarchyRootPlayer() != LeftActor || LeftItem.IsRuined()) { return 0; }
        return LeftItem.GetQuantity();
    }

    bool HCInventoryBoundCaravan(HCCaravanState row)
    {
        if (!row || !HCLive() || !LeftItem) { return false; }
        row.ActorId = HCActorId(true);
        row.ItemId = HCItemId(true);
        row.ItemClass = LeftItem.GetType();
        row.Quantity = LeftItem.GetQuantity();
        if (!HCWorldLimits.Token(row.ActorId) || !HCWorldLimits.Token(row.ItemId)) { return false; }
        return HCCurrentCaravan(row) && HCCargoReceipt(row) == "retained";
    }
}

class HCAICaravan
{
    ref HCCaravanState m_State;
    ref HCCaravanCorridor m_Corridor;
    ref HCEncounterStore<HCCaravanState> m_Store;
    ref HCCaravanInventory m_IO;
    ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    bool m_Enabled;
    bool m_Ready;
    bool m_Busy;
    int m_Reports;
    string m_ProviderRefusal = "CARAVAN_PROVIDER_UNAVAILABLE";
    // Conservative full cooldown after reopening a terminal journal. Process
    // timestamps are never persisted/reused across restart or clock rollback.
    float m_TerminalAt = -1;

    HCOperationalStatus HCGetOperationalStatus()
    {
        if (m_Enabled && m_Ready && m_IO)
        {
            string fault = m_IO.HCOperationalFault();
            if (fault != "") { m_Status.HCPublish("refused", fault); }
        }
        return m_Status;
    }

    bool HCTerminal(string leg) { return leg == "returned" || leg == "lost"; }

    bool HCValidTripId(string id, int sequence)
    {
        if (sequence < 0 || sequence > 1000000000) { return false; }
        if (sequence == 0) { return id == "hc36-first-corridor"; }
        return id == "hc36-first-corridor:trip:" + sequence.ToString();
    }

    bool HCValidHistory(HCCaravanState row)
    {
        // A missing legacy array is empty, never evidence of an old trip reset.
        if (!row.History) { return row.TripSequence == 0; }
        // Validate the shipped hard bound before applying a smaller operator
        // retention cap. Historical receipts are terminal-only, never live work.
        if (row.History.Count() >= 64) { return false; }
        int previous = -1;
        foreach (HCCaravanReceipt receipt : row.History)
        {
            if (!receipt || !HCTerminal(receipt.Leg)) { return false; }
            if (!HCValidTripId(receipt.Id, receipt.TripSequence)) { return false; }
            if (receipt.TripSequence <= previous || receipt.TripSequence >= row.TripSequence) { return false; }
            if (receipt.CargoReceipt != "retained" && receipt.CargoReceipt != "lost") { return false; }
            if (receipt.Leg == "lost" && receipt.CargoReceipt != "lost") { return false; }
            if (!HCWorldLimits.Token(receipt.ItemId) || !(receipt.Quantity >= 0) || !(receipt.Quantity <= float.MAX)) { return false; }
            previous = receipt.TripSequence;
        }
        return true;
    }

    bool HCTrimHistory()
    {
        // Validate ALL receipts before eviction so an unresolved/malformed row
        // cannot disappear merely because the operator reduced retention.
        if (!HCValidState(m_State)) { return false; }
        if (!m_State.History || m_State.History.Count() < m_Corridor.MaxTripHistory) { return true; }
        while (m_State.History.Count() >= m_Corridor.MaxTripHistory)
        {
            m_State.History.RemoveOrdered(0);
        }
        // Existing synchronous transition barrier; no new routine save loop.
        return m_Store.Save(m_State);
    }

    bool HCValidState(HCCaravanState row)
    {
        if (!row || row.Version != 1 || row.Refusal.Length() > 96) { return false; }
        if (!HCValidHistory(row)) { return false; }
        if (row.Leg == "idle")
        {
            return row.Id == "" && row.CargoReceipt == "none" && row.LeaseId == "" && row.ItemId == "" && row.Generation == 0 && row.TripSequence == 0;
        }
        if (!HCValidTripId(row.Id, row.TripSequence) || !HCWorldLimits.Token(row.RouteId)) { return false; }
        if (!HCWorldLimits.Token(row.LeaseId) || !HCWorldLimits.Token(row.PartyId) || !HCWorldLimits.Token(row.CargoId)) { return false; }
        if (!HCWorldLimits.Token(row.ActorId) || !HCWorldLimits.Token(row.ItemId) || !HCWorldLimits.Token(row.ItemClass)) { return false; }
        if (row.Generation < 1 || !(row.Quantity >= 0) || !(row.Quantity <= float.MAX)) { return false; }
        if (row.Leg == "quarantined") { return row.CargoReceipt == "unknown" || row.CargoReceipt == "lost"; }
        if (row.Leg == "lost") { return row.CargoReceipt == "lost"; }
        if (row.CargoReceipt != "retained" && row.CargoReceipt != "lost") { return false; }
        if (row.Leg == "outbound" || row.Leg == "fleeing_outbound" || row.Leg == "return_pending" || row.Leg == "fleeing_return_pending") { return true; }
        return row.Leg == "returning" || row.Leg == "fleeing_returning" || row.Leg == "returned";
    }

    bool HCActive()
    {
        if (!m_State) { return false; }
        string leg = m_State.Leg;
        return leg == "outbound" || leg == "fleeing_outbound" || leg == "return_pending" || leg == "fleeing_return_pending" || leg == "returning" || leg == "fleeing_returning";
    }

    bool HCCheckpoint()
    {
        if (!m_Ready || !m_Store || !HCValidState(m_State) || !m_Store.Save(m_State))
        {
            m_Ready = false;
            m_State.Leg = "quarantined";
            if (m_State.CargoReceipt != "lost") { m_State.CargoReceipt = "unknown"; }
            m_State.Refusal = "CARAVAN_JOURNAL_UNCERTAIN";
            m_Status.HCPublish("refused", m_State.Refusal);
            HCLog();
            return false;
        }
        if (HCTerminal(m_State.Leg) && m_TerminalAt < 0) { m_TerminalAt = GetGame().GetTickTime(); }
        HCLog();
        return true;
    }

    // Called once by HCXAIAdapter.OnStart; never registered as another module.
    void Open(HCSettings settings, HCCaravanInventory provider)
    {
        m_Ready = false;
        m_Busy = false;
        m_Reports = 0;
        m_TerminalAt = -1;
        m_ProviderRefusal = "CARAVAN_PROVIDER_UNAVAILABLE";
        m_Enabled = settings && settings.EnableEncounters;
        m_State = new HCCaravanState;
        if (!m_Enabled) { m_Status.HCPublish("off", "operator_disabled"); HCLog(); return; }
        if (!GetGame() || !GetGame().IsServer()) { m_Enabled = false; return; }
        // Native EnSystem.c:397; independent operator opt-out.
        if (FileExist("$profile:HollowCountry/acceptance/ai_caravans.disable"))
        {
            m_Enabled = false;
            m_Status.HCPublish("off", "operator_opt_out");
            HCLog(); return;
        }
        Print(HCV2Admission.Line("AICaravan", true, "HC36-WALKING-CORRIDOR", false));
        string encoded = HCWorldStore.Read("$mission:hollow-country/ai/caravans.json");
        string error;
        bool parsed = false;
        if (encoded.Length() > 0 && encoded.Length() <= 4096)
        {
            parsed = JsonFileLoader<HCCaravanCorridor>.LoadData(encoded, m_Corridor, error);
        }
        if (parsed && m_Corridor) { m_Corridor.HCApplyDefaults(encoded); }
        if (!parsed || !m_Corridor || !m_Corridor.HCValid() || !m_Corridor.HCNetworkValid())
        {
            m_State.Refusal = "CARAVAN_CONFIG_INVALID";
            m_Status.HCPublish("refused", m_State.Refusal);
            HCLog();
            return;
        }
        m_Store = new HCEncounterStore<HCCaravanState>("hc36-first-caravan");
        m_State = m_Store.Load(new HCCaravanState, "Leg");
        if (!HCValidState(m_State))
        {
            m_Status.HCPublish("refused", "CARAVAN_JOURNAL_INVALID");
            Print("[HC Caravan] HC-36 leg=refused cargo=unknown reason=CARAVAN_JOURNAL_INVALID state=refused count=0 runtime=PENDING");
            return;
        }
        if (!HCTrimHistory())
        {
            m_State.Refusal = "CARAVAN_JOURNAL_UNCERTAIN";
            m_Status.HCPublish("refused", m_State.Refusal);
            HCLog();
            return;
        }
        m_IO = provider;
        if (m_IO)
        {
            m_IO.Corridor = m_Corridor;
            m_ProviderRefusal = m_IO.HCRefusal();
        }
        m_Ready = true;
        HCRestore();
        if (m_State.Leg != "quarantined")
        {
            m_State.Refusal = m_Corridor.HCAdmissionRefusal();
            if (m_State.Refusal == "" && m_IO) { m_State.Refusal = m_ProviderRefusal; }
            if (m_State.Refusal == "") { m_State.Refusal = "CARAVAN_PROVIDER_CALLBACKS_UNVERIFIED"; }
        }
        if (m_State.Leg == "quarantined") { m_Status.HCPublish("refused", m_State.Refusal); }
        else { m_Status.HCPublish("ready", "journal_loaded_waiting_funded_road_pair"); }
        HCLog();
    }

    bool HCBegin(string lease)
    {
        if (!m_Enabled || !m_Ready || m_Busy || !m_State || !m_IO) { return false; }
        if (!m_Corridor || m_Corridor.HCAdmissionRefusal() != "" || !m_IO.HCReady()) { return false; }
        if (!HCValidState(m_State) || m_State.TripSequence >= 1000000000) { return false; }
        bool repeated = m_State.Leg != "idle";
        if (repeated)
        {
            // Quarantine is unresolved, never an evictable terminal receipt.
            if (!HCTerminal(m_State.Leg)) { return false; }
            float now = GetGame().GetTickTime();
            if (m_TerminalAt < 0 || now < m_TerminalAt) { m_TerminalAt = now; return false; }
            if (now - m_TerminalAt < m_Corridor.CooldownSeconds) { return false; }
        }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(lease);
        if (!HCAIPartyIdentity.HCValid(identity)) { return false; }
        HCCaravanState nextTrip = new HCCaravanState;
        nextTrip.TripSequence = m_State.TripSequence + 1;
        nextTrip.Id = m_Corridor.CorridorId + ":trip:" + nextTrip.TripSequence.ToString();
        nextTrip.LeaseId = lease;
        nextTrip.PartyId = identity.HCPartyId();
        nextTrip.CargoId = identity.HCCargoId();
        // HC-10 route provenance is immutable (route:<party>), distinct from
        // this corridor content ID. Provider must qualify their connection.
        nextTrip.RouteId = identity.HCRouteId();
        nextTrip.Generation = identity.HCGeneration();
        m_Busy = true;
        bool bound = m_IO.HCBindCaravan(nextTrip);
        m_Busy = false;
        if (!bound && m_IO) { m_IO.HCClear(); }
        if (!m_Enabled || !m_Ready || !bound) { return false; }
        if (!m_IO.HCCurrentCaravan(nextTrip) || !m_IO.HCLive()) { return false; }
        if (m_IO.HCCargoReceipt(nextTrip) != "retained" || !m_IO.HCAtCamp(nextTrip, true)) { return false; }
        if (repeated)
        {
            // Same finite native stock and HC-10 identity. The provider reads
            // remaining quantity; this handler never replenishes or moves it.
            if (nextTrip.LeaseId != m_State.LeaseId || nextTrip.PartyId != m_State.PartyId || nextTrip.CargoId != m_State.CargoId) { return false; }
            if (nextTrip.Generation != m_State.Generation || nextTrip.ActorId != m_State.ActorId || nextTrip.RouteId != m_State.RouteId) { return false; }
            // Binding may carry an old quantity. Re-read the same native stock
            // against the previous ceiling, and retain any observed idle loss
            // BEFORE admission, even when the new bound quantity then refuses.
            float remaining = m_IO.HCRemainingQuantity(m_State);
            if (!(remaining >= 0) || remaining > m_State.Quantity) { return false; }
            if (remaining < m_State.Quantity)
            {
                m_State.Quantity = remaining;
                m_State.CargoReceipt = "lost";
                m_State.Refusal = "CARAVAN_CARGO_LOST";
                if (!HCCheckpoint()) { return false; }
            }
            if (nextTrip.ItemId != m_State.ItemId || nextTrip.ItemClass != m_State.ItemClass || !(nextTrip.Quantity > 0) || nextTrip.Quantity > m_State.Quantity) { return false; }
            if (m_State.History)
            {
                foreach (HCCaravanReceipt prior : m_State.History) { nextTrip.History.Insert(prior); }
            }
            HCCaravanReceipt terminal = new HCCaravanReceipt;
            terminal.Id = m_State.Id;
            terminal.TripSequence = m_State.TripSequence;
            terminal.Leg = m_State.Leg;
            terminal.CargoReceipt = m_State.CargoReceipt;
            terminal.ItemId = m_State.ItemId;
            terminal.Quantity = m_State.Quantity;
            nextTrip.History.Insert(terminal);
            // HCValidHistory bounded the input to 63 terminal-only rows.
            if (nextTrip.History.Count() >= m_Corridor.MaxTripHistory) { nextTrip.History.RemoveOrdered(0); }
        }
        nextTrip.Leg = "outbound";
        nextTrip.CargoReceipt = "retained";
        m_State = nextTrip;
        m_TerminalAt = -1;
        if (!HCCheckpoint()) { return false; }
        return HCRequestWalk(false);
    }

    bool HCRequestWalk(bool returning)
    {
        m_Busy = true;
        bool requested = m_IO.HCWalkCaravan(m_State, returning);
        m_Busy = false;
        if (!m_Enabled || !m_Ready || !HCActive()) { return false; }
        if (!requested) { HCQuarantine("CARAVAN_WALK_UNCONFIRMED"); return false; }
        m_Status.HCPublish("ready", "existing_party_walk_requested_runtime_pending");
        return true;
    }

    void HCQuarantine(string reason)
    {
        m_State.Leg = "quarantined";
        if (m_State.CargoReceipt != "lost") { m_State.CargoReceipt = "unknown"; }
        m_State.Refusal = reason;
        m_Status.HCPublish("refused", reason);
        HCCheckpoint();
    }

    void HCRestore()
    {
        if (HCTerminal(m_State.Leg)) { m_TerminalAt = GetGame().GetTickTime(); }
        if (HCActive()) { HCQuarantine("CARAVAN_PAIRED_NATIVE_RESTORE_UNPROVEN"); }
        // No actor/item rebind or travel replay on restore. Only a NEW trip can
        // consume observed remaining stock after cooldown + fresh admission.
    }

    void HCStep()
    {
        if (!m_Enabled || !m_Ready || m_Busy || !HCActive() || !m_IO) { return; }
        if (!m_IO.HCCurrentCaravan(m_State)) { HCQuarantine("CARAVAN_LEASE_UNRESOLVED"); return; }
        if (!m_IO.HCLive())
        {
            // Unconscious is not death: provider body loss is not inferred.
            HCQuarantine("CARAVAN_CARRIER_UNAVAILABLE");
            return;
        }
        string receipt = m_IO.HCCargoReceipt(m_State);
        if (receipt == "unknown") { HCQuarantine("CARAVAN_CARGO_UNRESOLVED"); return; }
        if (receipt != "retained" && receipt != "lost") { HCQuarantine("CARAVAN_RECEIPT_INVALID"); return; }
        if (receipt == "lost")
        {
            bool newLoss = m_State.CargoReceipt != "lost";
            m_State.CargoReceipt = "lost";
            float remaining = m_IO.HCRemainingQuantity(m_State);
            if (!(remaining >= 0) || remaining > m_State.Quantity) { HCQuarantine("CARAVAN_REMAINING_STOCK_UNRESOLVED"); return; }
            if (newLoss || remaining < m_State.Quantity)
            {
                m_State.Quantity = remaining;
                m_State.Refusal = "CARAVAN_CARGO_LOST";
                if (!HCCheckpoint()) { return; }
            }
        }
        // Lost is sticky even if somebody gives the same item back. No restock.
        bool returning = m_State.Leg == "returning" || m_State.Leg == "fleeing_returning";
        if (m_IO.HCFleeObserved(m_State))
        {
            string fleeLeg = "fleeing_outbound";
            if (returning) { fleeLeg = "fleeing_returning"; }
            if (m_State.Leg == "return_pending" || m_State.Leg == "fleeing_return_pending") { fleeLeg = "fleeing_return_pending"; }
            if (m_State.Leg != fleeLeg) { m_State.Leg = fleeLeg; HCCheckpoint(); }
            return;
        }
        // No forced flee/combat override; provider owns pathing and recovery.
        if (m_State.Leg == "fleeing_return_pending")
        {
            m_State.Leg = "return_pending";
            if (!HCCheckpoint()) { return; }
        }
        if (m_State.Leg == "return_pending")
        {
            m_State.Leg = "returning";
            if (HCCheckpoint()) { HCRequestWalk(true); }
            return;
        }
        if (m_State.Leg == "fleeing_outbound") { m_State.Leg = "outbound"; if (!HCCheckpoint()) { return; } }
        if (m_State.Leg == "fleeing_returning") { m_State.Leg = "returning"; if (!HCCheckpoint()) { return; } }
        if (!m_IO.HCAtCamp(m_State, returning)) { return; }
        m_State.Leg = "return_pending";
        if (returning) { m_State.Leg = "returned"; }
        HCCheckpoint();
    }

    bool HCConfirmedReturn()
    {
        if (!m_Enabled || !m_Ready || m_Busy || !m_State || m_State.Leg != "returned" || !m_IO) { return false; }
        return m_IO.HCCurrentCaravan(m_State) && m_IO.HCLive() && m_IO.HCAtCamp(m_State, true);
    }

    void Step()
    {
        if (!m_Enabled || !m_Ready || !HCActive()) { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        HCStep();
    }

    void HCLog()
    {
        if (!m_State || m_Reports >= 16) { return; }
        m_Reports++;
        string effective = m_Status.HCState();
        string id = "none";
        string count = "0";
        if (m_State.Id != "") { id = m_State.Id; count = "1"; }
        string line = "[HC Caravan] HC-36 caravan=" + id + " leg=" + m_State.Leg;
        line += " cargo=" + m_State.CargoReceipt + " refused=" + m_State.Refusal;
        line += " state=" + effective + " authored=1 count=" + count;
        line += " reason=" + m_Status.HCReason();
        line += " provider_refused=" + m_ProviderRefusal;
        Print(line + " count_cap=1 runtime=PENDING");
    }

    void HCClose()
    {
        if (m_Enabled && m_Ready && HCActive()) { HCQuarantine("CARAVAN_STOPPED_RECONCILIATION_REQUIRED"); }
        m_Enabled = false;
        if (m_IO) { m_IO.HCClear(); }
        m_IO = null;
        m_Store = null;
        m_Ready = false;
        m_Status.HCPublish("off", "stopped");
    }
}
