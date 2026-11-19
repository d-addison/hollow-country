// HC-35/#145: one reciprocal recipe, two EXISTING HC-10-funded parties.
// Spec/plan/task: HC-16 funding -> HC-10 custody -> HC-34 same-item barriers
// -> rendezvous -> observed gestures -> two moves -> receipt or quarantine.
// No abstract bargain creates cargo; no stock credit, rewards or UI.
// Confirmed caravan loss reduces both existing camp allocations once.
// All writes are synchronous transaction barriers through HCEncounterStore's
// verified intent/backup/copy/readback, NOT atomic with Hive. Back up both.
// No routine dirty state: HCSaveJob/HCSaveScheduler remain the sole routine
// save owner. Restart NEVER rebinds, refunds or replays an issued trade.
// Native evidence, inspected scripts-1.30.164289 (N2/N5/N17):
// 3_Game/Global/Game.c:1120 IsServer; gameplay.c:636 GetGame;
// 3_Game/Entities/Object.c:287 GetPosition, :467 GetType, :517 IsAlive,
// :1219 IsRuined; Entities/Man.c:21 GetIdentity;
// Entities/EntityAI.c:882 GetHierarchyRootPlayer, :1884 GetInventory,
// :3374 GetPersistentID (via HCSearchSupplyRegistry.PersistentId);
// Systems/Inventory/Inventory.c:268 GetCurrentInventoryLocation,
// :276 FindFreeLocationFor, :808 IsInventoryLocked, :1057 TakeToDst:
// SERVER calls LocationSyncMoveEntity and SendServerMove on success;
// InventoryLocation.c:52 GetParent, :210 CompareLocationOnly;
// 4_World/Entities/ItemBase.c:3490 GetQuantity, :4372 IsTakeable;
// Entities/ManBase/PlayerBase.c:3925 IsUnconscious, :8962 IsSurrendered;
// Classes/EmoteManager.c:236 GetGesture, :1328 IsEmotePlaying inspected ONLY:
// neither proves provider command acknowledgement. No emote calls here.
// 3_Game/dayzplayer.c + 4_World/Entities/DayZPlayerImplement.c are NOT an AI
// SDK. Inspected installed Expansion calls are cited in the addon ports.
// 3_Game/tools/JsonFileLoader.c:69 LoadData; CfgGameplayHandler.c:3 $mission:;
// 1_Core/proto/EnConvert.c:210 DistanceSq, :30 ToString; EnString.c:199
// Length; EnDebug.c:96 Print. Runtime acceptance PENDING.

class HCTradeRecipe
{
    int Version = 1;
    string RecipeId = "bandage-for-drink";
    string LeftClass = "BandageDressing";
    string RightClass = "SodaCan_Kvass";
    int TimeoutSeconds = 120;
    // Same 2.5 m local pickup envelope as HC-34, 0.25% of the approximately
    // 1000 m vanilla network bubble/rifle report range. Never perception.
    float TransferRangeMeters = 2.5;
    // Wave 16: emote requests per exchange, and the item-scan bound for the
    // provider bind. Named fields; the default applies only when the authored
    // file omits the key (native JSON zero-fills a missing int).
    int GestureRequests = 3;
    int InventoryScanLimit = 64;
    // Infrequent, single active pair; these are provisional pilot budgets.
    int OfferIntervalSeconds = 900;
    int MinimumCampReserve = 4;
    int MinimumCampMembers = 2;
    int LossSupplyDebit = 1;
    int MaxLossReceipts = 128;
    int PairCandidatesPerTick = 1;
    static const int DEFAULT_GESTURE_REQUESTS = 3;
    static const int DEFAULT_INVENTORY_SCAN_LIMIT = 64;

    void HCApplyDefaults(string encoded)
    {
        if (!HCJsonFields.Has(encoded, "OfferIntervalSeconds")) { OfferIntervalSeconds = 900; }
        if (!HCJsonFields.Has(encoded, "MinimumCampMembers")) { MinimumCampMembers = 2; }
        if (!HCJsonFields.Has(encoded, "MinimumCampReserve")) { MinimumCampReserve = 4; }
        if (!HCJsonFields.Has(encoded, "LossSupplyDebit")) { LossSupplyDebit = 1; }
        if (!HCJsonFields.Has(encoded, "MaxLossReceipts")) { MaxLossReceipts = 128; }
        if (!HCJsonFields.Has(encoded, "PairCandidatesPerTick")) { PairCandidatesPerTick = 1; }
        if (!HCJsonFields.Has(encoded, "GestureRequests")) { GestureRequests = HCTradeRecipe.DEFAULT_GESTURE_REQUESTS; }
        if (!HCJsonFields.Has(encoded, "InventoryScanLimit")) { InventoryScanLimit = HCTradeRecipe.DEFAULT_INVENTORY_SCAN_LIMIT; }
    }

    bool HCOfferConfigValid()
    {
        return MinimumCampMembers >= 2 && MinimumCampMembers <= HCAILimits.SIZE_CEILING && OfferIntervalSeconds >= 60 && OfferIntervalSeconds <= 86400 && MinimumCampReserve >= 1 && MinimumCampReserve <= 24 && LossSupplyDebit >= 1 && LossSupplyDebit <= MinimumCampReserve && MaxLossReceipts >= 1 && MaxLossReceipts <= 256 && PairCandidatesPerTick == 1;
    }

    bool HCValid()
    {
        HCScavengeDefaults pickup = new HCScavengeDefaults;
        if (Version != 1 || LeftClass != "BandageDressing") { return false; }
        bool legacyDrink = RecipeId == "bandage-for-drink" && RightClass == "SodaCan_Kvass";
        bool fundedFood = RecipeId == "bandage-for-food" && RightClass == "TunaCan";
        if (!legacyDrink && !fundedFood) { return false; }
        if (TimeoutSeconds < 1 || TimeoutSeconds > 300) { return false; }
        if (GestureRequests < 1 || GestureRequests > 10 || InventoryScanLimit < 1 || InventoryScanLimit > 256) { return false; }
        return TransferRangeMeters > 0 && TransferRangeMeters <= pickup.TransferRangeMeters;
    }
}

// Wave 16: the emote acknowledgement is admitted unverified. The server-side
// observation is a NEW emote callback on BOTH actors after the request (the
// addon's EmoteManager serial); a request alone, or one actor, is never enough.
// The client-visible acknowledgement has no recorded native/two-client verdict
// (runtime=PENDING). Request count per exchange is the recipe's GestureRequests.
class HCTradeGestureGate
{
    string m_Trade;
    int m_LeftSerial;
    int m_RightSerial;
    int m_Requests;
    int m_MaxRequests;

    static string HCKey(HCTradeState row)
    {
        if (!row) { return ""; }
        return row.Id + ":" + row.StartedAt.ToString();
    }

    bool HCArmedFor(string key) { return m_Trade != "" && m_Trade == key; }

    void HCArm(string key, int leftSerial, int rightSerial, int maxRequests)
    {
        m_Trade = key;
        m_LeftSerial = leftSerial;
        m_RightSerial = rightSerial;
        m_Requests = 0;
        m_MaxRequests = maxRequests;
    }

    bool HCTakeRequest()
    {
        if (m_Trade == "" || m_Requests >= m_MaxRequests) { return false; }
        m_Requests++;
        return true;
    }

    bool HCObserved(int leftSerial, int rightSerial)
    {
        return m_Trade != "" && leftSerial > m_LeftSerial && rightSerial > m_RightSerial;
    }

    void HCReset()
    {
        m_Trade = "";
        m_LeftSerial = 0;
        m_RightSerial = 0;
        m_Requests = 0;
        m_MaxRequests = 0;
    }
}

// Module readiness reason from the real provider state (never hard-coded).
class HCTradeReadiness
{
    static string HCTradeReadinessReason(bool providerBound, bool providerReady)
    {
        if (!providerBound) { return "provider_absent_base_only"; }
        if (!providerReady) { return "provider_bound_waiting_site_director"; }
        return "provider_bound_awaiting_funded_pair";
    }
}

class HCTradeState
{
    int Version = 1;
    string Id;
    string Phase = "idle";
    string Transfer = "none";
    string Refusal;
    string LeftLease;
    string RightLease;
    string LeftParty;
    string RightParty;
    string LeftCargo;
    string RightCargo;
    int LeftGeneration;
    int RightGeneration;
    string LeftActor;
    string RightActor;
    string LeftItem;
    string RightItem;
    float LeftQuantity;
    float RightQuantity;
    int StartedAt;
    int EndsAt;
}

// Trusted server-only port. Provider binds existing actors/items and surveyed
// walking routes; never a JSON/client capability or another materializer.
// HCBind must call HCInventoryBound after binding the exact HC-10 lease bodies.
class HCTradeInventory
{
    PlayerBase LeftActor;
    PlayerBase RightActor;
    ItemBase LeftItem;
    ItemBase RightItem;
    ref HCTradeRecipe Recipe;

    bool HCReady() { return false; }
    string HCOperationalFault() { return ""; }
    string HCRefusal() { return "TRADE_PROVIDER_UNAVAILABLE"; }
    bool HCBind(HCTradeState row) { return false; }
    bool HCBeginWalk(HCTradeState row) { return false; }
    bool HCObservedGestures(HCTradeState row) { return false; }

    string HCActorId(bool leftSide)
    {
        if (leftSide) { return HCSearchSupplyRegistry.PersistentId(LeftActor); }
        return HCSearchSupplyRegistry.PersistentId(RightActor);
    }

    string HCItemId(bool leftSide)
    {
        if (leftSide) { return HCSearchSupplyRegistry.PersistentId(LeftItem); }
        return HCSearchSupplyRegistry.PersistentId(RightItem);
    }

    bool HCLive()
    {
        if (!GetGame() || !GetGame().IsServer() || !LeftActor || !RightActor || LeftActor == RightActor) { return false; }
        if (LeftActor.GetIdentity() || RightActor.GetIdentity()) { return false; }
        if (!LeftActor.IsAlive() || !RightActor.IsAlive()) { return false; }
        if (LeftActor.IsUnconscious() || RightActor.IsUnconscious()) { return false; }
        return !LeftActor.IsSurrendered() && !RightActor.IsSurrendered();
    }

    bool HCAtMeeting()
    {
        if (!HCLive() || !Recipe || !Recipe.HCValid()) { return false; }
        return vector.DistanceSq(LeftActor.GetPosition(), RightActor.GetPosition()) <= Recipe.TransferRangeMeters * Recipe.TransferRangeMeters;
    }

    bool HCCurrent(HCTradeState row)
    {
        if (!row || !LeftActor || !RightActor || !LeftItem || !RightItem || LeftItem == RightItem) { return false; }
        HCAIPartyIdentity left = HCWorldMaterializer.HCIdentity(row.LeftLease);
        HCAIPartyIdentity right = HCWorldMaterializer.HCIdentity(row.RightLease);
        if (!HCAIPartyIdentity.HCValid(left) || !HCAIPartyIdentity.HCValid(right)) { return false; }
        if (left.HCPartyId() != row.LeftParty || right.HCPartyId() != row.RightParty) { return false; }
        if (left.HCCargoId() != row.LeftCargo || right.HCCargoId() != row.RightCargo) { return false; }
        if (left.HCGeneration() != row.LeftGeneration || right.HCGeneration() != row.RightGeneration) { return false; }
        if (HCActorId(true) != row.LeftActor || HCActorId(false) != row.RightActor) { return false; }
        if (HCItemId(true) != row.LeftItem || HCItemId(false) != row.RightItem) { return false; }
        if (!Recipe || LeftItem.GetType() != Recipe.LeftClass || RightItem.GetType() != Recipe.RightClass) { return false; }
        return LeftItem.GetQuantity() == row.LeftQuantity && RightItem.GetQuantity() == row.RightQuantity;
    }

    bool HCOwners(HCTradeState row, bool exchanged)
    {
        if (!HCCurrent(row)) { return false; }
        if (exchanged) { return LeftItem.GetHierarchyRootPlayer() == RightActor && RightItem.GetHierarchyRootPlayer() == LeftActor; }
        return LeftItem.GetHierarchyRootPlayer() == LeftActor && RightItem.GetHierarchyRootPlayer() == RightActor;
    }

    bool HCInventoryBound(HCTradeState row)
    {
        if (!row || !HCLive() || !Recipe || !Recipe.HCValid() || !LeftItem || !RightItem) { return false; }
        row.LeftActor = HCActorId(true);
        row.RightActor = HCActorId(false);
        row.LeftItem = HCItemId(true);
        row.RightItem = HCItemId(false);
        row.LeftQuantity = LeftItem.GetQuantity();
        row.RightQuantity = RightItem.GetQuantity();
        if (row.LeftActor == "" || row.RightActor == "" || row.LeftActor == row.RightActor) { return false; }
        if (row.LeftItem == "" || row.RightItem == "" || row.LeftItem == row.RightItem) { return false; }
        return HCOwners(row, false);
    }

    bool HCMoveAllowed(string step, HCTradeState row)
    {
        if (!row || row.Phase != "intent_" + step) { return false; }
        if (!HCCurrent(row) || !HCLive() || !HCAtMeeting()) { return false; }
        if (LeftItem.IsRuined() || RightItem.IsRuined() || !LeftItem.IsTakeable() || !RightItem.IsTakeable()) { return false; }
        if (LeftActor.GetInventory().IsInventoryLocked() || RightActor.GetInventory().IsInventoryLocked()) { return false; }
        if (step == "left") { return HCOwners(row, false); }
        if (step != "right" && step != "rollback") { return false; }
        return LeftItem.GetHierarchyRootPlayer() == RightActor && RightItem.GetHierarchyRootPlayer() == RightActor;
    }

    // 2=confirmed native move; 4=NO mutation attempted; 3=uncertain after call.
    // False native return does not authorize refund. No split, clone or create.
    int HCMove(string step, HCTradeState row)
    {
        if (!HCMoveAllowed(step, row)) { return 4; }
        ItemBase stock = LeftItem;
        PlayerBase destination = RightActor;
        if (step == "right") { stock = RightItem; destination = LeftActor; }
        if (step == "rollback") { destination = LeftActor; }
        InventoryLocation before = new InventoryLocation;
        InventoryLocation target = new InventoryLocation;
        InventoryLocation current = new InventoryLocation;
        if (!stock.GetInventory().GetCurrentInventoryLocation(before)) { return 4; }
        if (!destination.GetInventory().FindFreeLocationFor(stock, FindInventoryLocationType.CARGO, target)) { return 4; }
        EntityAI targetParent = target.GetParent();
        if (!targetParent || (targetParent != destination && targetParent.GetHierarchyRootPlayer() != destination)) { return 4; }
        // Other scripts may run in preflight. Recheck both items, parties and
        // original location immediately before entering the native mutation.
        if (!HCMoveAllowed(step, row)) { return 4; }
        if (!stock.GetInventory().GetCurrentInventoryLocation(current) || !current.CompareLocationOnly(before)) { return 4; }
        bool moved = destination.GetInventory().TakeToDst(InventoryMode.SERVER, before, target);
        if (!moved || !HCCurrent(row) || !HCLive() || !stock || stock.GetHierarchyRootPlayer() != destination) { return 3; }
        if (step == "left" && RightItem.GetHierarchyRootPlayer() != RightActor) { return 3; }
        if (step == "right" && !HCOwners(row, true)) { return 3; }
        if (step == "rollback" && !HCOwners(row, false)) { return 3; }
        return 2;
    }

    void HCClear()
    {
        LeftActor = null;
        RightActor = null;
        LeftItem = null;
        RightItem = null;
    }
}

class HCTradeTransaction
{
    ref HCTradeState m_State;
    ref HCEncounterStore<HCTradeState> m_Store;
    ref HCTradeInventory m_IO;
    ref HCTradeRecipe m_Recipe;
    ref HCOperationalStatus m_Status = new HCOperationalStatus;
    bool m_Ready;
    bool m_Enabled;
    bool m_Busy;
    int m_Reports;
    int m_Released;
    // #194: refusal text shown by HCLog after a failed idle save; the journal itself stays untouched.
    string m_LogRefusal;

    bool HCValidState(HCTradeState row)
    {
        if (!row || row.Version != 1 || row.Refusal.Length() > 96) { return false; }
        if (row.Phase == "idle")
        {
            return row.Id == "" && row.Transfer == "none" && row.LeftLease == "" && row.RightLease == "" && row.StartedAt == 0 && row.EndsAt == 0;
        }
        if (row.Id != "hc35-first-barter") { return false; }
        if (!HCWorldLimits.Token(row.LeftLease) || !HCWorldLimits.Token(row.RightLease) || row.LeftLease == row.RightLease) { return false; }
        if (!HCWorldLimits.Token(row.LeftParty) || !HCWorldLimits.Token(row.RightParty) || row.LeftParty == row.RightParty) { return false; }
        if (!HCWorldLimits.Token(row.LeftCargo) || !HCWorldLimits.Token(row.RightCargo) || row.LeftCargo == row.RightCargo) { return false; }
        if (!HCWorldLimits.Token(row.LeftActor) || !HCWorldLimits.Token(row.RightActor) || row.LeftActor == row.RightActor) { return false; }
        if (!HCWorldLimits.Token(row.LeftItem) || !HCWorldLimits.Token(row.RightItem) || row.LeftItem == row.RightItem) { return false; }
        if (row.LeftGeneration < 1 || row.RightGeneration < 1) { return false; }
        if (!(row.LeftQuantity >= 0) || !(row.LeftQuantity <= float.MAX)) { return false; }
        if (!(row.RightQuantity >= 0) || !(row.RightQuantity <= float.MAX)) { return false; }
        if (row.StartedAt < 1 || row.StartedAt > 2146878847 || row.EndsAt <= row.StartedAt) { return false; }
        if (row.EndsAt - row.StartedAt > 300) { return false; }
        if (row.Phase == "meeting" || row.Phase == "left_pending") { return row.Transfer == "none"; }
        if (row.Phase == "intent_left" || row.Phase == "intent_right" || row.Phase == "intent_rollback" || row.Phase == "quarantined") { return row.Transfer == "unknown"; }
        if (row.Phase == "right_pending") { return row.Transfer == "left_confirmed"; }
        if (row.Phase == "rollback_pending") { return row.Transfer == "right_refused_before_mutation"; }
        if (row.Phase == "complete") { return row.Transfer == "reciprocal_confirmed"; }
        if (row.Phase == "rolled_back") { return row.Transfer == "same_item_return_confirmed"; }
        if (row.Phase == "cancelled") { return row.Transfer == "none" || row.Transfer == "left_refused"; }
        return false;
    }

    bool HCActive()
    {
        if (!m_State) { return false; }
        string phase = m_State.Phase;
        return phase == "meeting" || phase == "left_pending" || phase == "right_pending" || phase == "rollback_pending" || phase == "intent_left" || phase == "intent_right" || phase == "intent_rollback";
    }

    // Finished exchange evidence: the single slot may be reused. Quarantined is
    // NOT terminal here (uncertain native state keeps the slot until operator action).
    bool HCTerminal()
    {
        if (!m_State) { return false; }
        string phase = m_State.Phase;
        return phase == "cancelled" || phase == "rolled_back" || phase == "complete";
    }

    // Persist an idle journal for a terminal one. Called only once admission is
    // otherwise possible, so a refusing provider never rewrites the journal. The idle row
    // is saved as a separate candidate and the in-memory journal is released only after
    // that save succeeds (#193): a failed save leaves memory equal to the disk copy (the
    // terminal journal and its evidence) and fails closed (no retry until restart) rather
    // than quarantining over it. Log line bounded at 16.
    bool HCReleaseSlot()
    {
        if (!HCTerminal()) { return true; }
        HCTradeState idle = new HCTradeState;
        if (!m_Ready || !m_Store || !HCValidState(idle) || !m_Store.Save(idle))
        {
            m_Ready = false;
            m_Status.HCPublish("refused", "TRADE_JOURNAL_UNCERTAIN");
            m_LogRefusal = "TRADE_JOURNAL_UNCERTAIN";
            HCLog();
            return false;
        }
        string prior = m_State.Phase;
        string priorRefusal = m_State.Refusal;
        m_State.Id = "";
        m_State.Phase = "idle";
        m_State.Transfer = "none";
        m_State.Refusal = "";
        m_State.LeftLease = "";
        m_State.RightLease = "";
        m_State.LeftParty = "";
        m_State.RightParty = "";
        m_State.LeftCargo = "";
        m_State.RightCargo = "";
        m_State.LeftGeneration = 0;
        m_State.RightGeneration = 0;
        m_State.LeftActor = "";
        m_State.RightActor = "";
        m_State.LeftItem = "";
        m_State.RightItem = "";
        m_State.LeftQuantity = 0;
        m_State.RightQuantity = 0;
        m_State.StartedAt = 0;
        m_State.EndsAt = 0;
        HCLog();
        if (m_Released < 16)
        {
            m_Released++;
            string line = "[HC Plan] HC-35 trade slot released prior=" + prior;
            line += " prior_refusal=" + priorRefusal + " persisted=1 release_cap=16 runtime=PENDING";
            Print("" + line);
        }
        return true;
    }

    bool HCCheckpoint()
    {
        if (!m_Ready || !m_Store || !HCValidState(m_State) || !m_Store.Save(m_State))
        {
            m_Ready = false;
            m_State.Phase = "quarantined";
            m_State.Transfer = "unknown";
            m_State.Refusal = "TRADE_JOURNAL_UNCERTAIN";
            m_Status.HCPublish("refused", m_State.Refusal);
            HCLog();
            return false;
        }
        HCLog();
        return true;
    }

    // One exchange slot for this content slice. A terminal journal (cancelled,
    // rolled_back, complete) releases it on the next admission; quarantine never does.
    // Existing HC-10 leases already own the finite HC-16 funded party budgets.
    // No independent actor reservation, abstract debit or cargo mint here.
    bool HCBegin(string leftLease, string rightLease, int now)
    {
        if (!m_Enabled || !m_Ready || m_Busy || !m_State || !m_IO) { return false; }
        if (m_State.Phase != "idle" && !HCTerminal()) { return false; }
        if (now < 1 || now > 2146878847 || leftLease == rightLease) { return false; }
        if (!m_IO.HCReady()) { m_State.Refusal = m_IO.HCRefusal(); HCLog(); return false; }
        HCAIPartyIdentity left = HCWorldMaterializer.HCIdentity(leftLease);
        HCAIPartyIdentity right = HCWorldMaterializer.HCIdentity(rightLease);
        if (!HCAIPartyIdentity.HCValid(left) || !HCAIPartyIdentity.HCValid(right)) { return false; }
        if (left.HCPartyId() == right.HCPartyId() || left.HCCargoId() == right.HCCargoId()) { return false; }
        if (!HCReleaseSlot()) { return false; }
        m_State.LeftLease = leftLease;
        m_State.RightLease = rightLease;
        m_State.LeftParty = left.HCPartyId();
        m_State.RightParty = right.HCPartyId();
        m_State.LeftCargo = left.HCCargoId();
        m_State.RightCargo = right.HCCargoId();
        m_State.LeftGeneration = left.HCGeneration();
        m_State.RightGeneration = right.HCGeneration();
        m_Busy = true;
        bool bound = m_IO.HCBind(m_State);
        m_Busy = false;
        if (!m_Enabled || !m_Ready || m_State.Phase != "idle" || !bound) { return false; }
        if (!m_IO.HCOwners(m_State, false)) { return false; }
        m_State.LeftActor = m_IO.HCActorId(true);
        m_State.RightActor = m_IO.HCActorId(false);
        m_State.LeftItem = m_IO.HCItemId(true);
        m_State.RightItem = m_IO.HCItemId(false);
        m_State.Id = "hc35-first-barter";
        m_State.StartedAt = now;
        m_State.EndsAt = now + m_Recipe.TimeoutSeconds;
        m_State.Phase = "meeting";
        m_State.Refusal = "";
        if (!HCCheckpoint()) { return false; }
        // Publish intent before requesting provider movement/gestures. A
        // requested action is never an observed acknowledgement.
        m_Busy = true;
        bool requested = m_IO.HCBeginWalk(m_State);
        m_Busy = false;
        if (!m_Enabled || !m_Ready || m_State.Phase != "meeting") { return false; }
        if (!requested) { HCAbort("TRADE_WALK_REFUSED"); return false; }
        m_Status.HCPublish("ready", "bound_existing_funded_pair");
        return true;
    }

    void HCQuarantine(string reason)
    {
        if (!m_State) { return; }
        m_State.Phase = "quarantined";
        m_State.Transfer = "unknown";
        m_State.Refusal = reason;
        m_Status.HCPublish("refused", reason);
        HCCheckpoint();
    }

    void HCAbort(string reason)
    {
        if (!m_Ready || !HCActive()) { return; }
        if (m_Busy || m_State.Phase != "meeting") { HCQuarantine(reason); return; }
        // No native mutation issued yet. Leave actual cargo with its owner.
        m_State.Phase = "cancelled";
        m_State.Refusal = reason;
        HCCheckpoint();
    }

    void HCRestore()
    {
        if (HCActive()) { HCQuarantine("TRADE_PAIRED_NATIVE_RESTORE_UNPROVEN"); }
    }

    void HCMoveStep(string step)
    {
        m_Busy = true;
        string intent = "intent_" + step;
        m_State.Phase = intent;
        m_State.Transfer = "unknown";
        if (!HCCheckpoint()) { m_Busy = false; return; }
        int result = m_IO.HCMove(step, m_State);
        m_Busy = false;
        // Death/stop/theft callbacks may have invalidated this intent while
        // native code ran. Never overwrite terminal evidence with late success.
        if (!m_Enabled || !m_Ready || m_State.Phase != intent) { return; }
        if (result == 3) { HCQuarantine("TRADE_NATIVE_TRANSFER_UNCERTAIN"); return; }
        if (result != 2 && result != 4) { HCQuarantine("TRADE_INVALID_RECEIPT"); return; }
        if (step == "left")
        {
            m_State.Phase = "cancelled";
            m_State.Transfer = "left_refused";
            if (result == 2) { m_State.Phase = "right_pending"; m_State.Transfer = "left_confirmed"; }
        }
        if (step == "right")
        {
            m_State.Phase = "rollback_pending";
            m_State.Transfer = "right_refused_before_mutation";
            if (result == 2) { m_State.Phase = "complete"; m_State.Transfer = "reciprocal_confirmed"; }
        }
        if (step == "rollback")
        {
            if (result != 2) { HCQuarantine("TRADE_ROLLBACK_REFUSED"); return; }
            m_State.Phase = "rolled_back";
            m_State.Transfer = "same_item_return_confirmed";
        }
        HCCheckpoint();
    }

    void HCStep(int now)
    {
        if (!m_Enabled || !m_Ready || m_Busy || !HCActive() || !m_IO) { return; }
        bool expired = now < m_State.StartedAt || now >= m_State.EndsAt;
        // After the left item moved, a timeout still returns that same item before
        // quarantine: right is refused before mutation, then the rollback is tried.
        if (expired && m_State.Phase == "right_pending")
        {
            m_State.Phase = "rollback_pending";
            m_State.Transfer = "right_refused_before_mutation";
            if (!HCCheckpoint()) { return; }
        }
        if (expired && m_State.Phase == "rollback_pending")
        {
            if (!m_IO.HCCurrent(m_State) || !m_IO.HCLive()) { HCAbort("TRADE_PARTY_OR_ITEM_INTERRUPTED"); return; }
            HCMoveStep("rollback");
            return;
        }
        if (expired) { HCAbort("TRADE_RENDEZVOUS_TIMEOUT"); return; }
        if (!m_IO.HCCurrent(m_State) || !m_IO.HCLive()) { HCAbort("TRADE_PARTY_OR_ITEM_INTERRUPTED"); return; }
        if (m_State.Phase == "meeting")
        {
            if (!m_IO.HCOwners(m_State, false)) { HCAbort("TRADE_CARGO_INTERRUPTED"); return; }
            if (!m_IO.HCAtMeeting() || !m_IO.HCObservedGestures(m_State)) { return; }
            m_State.Phase = "left_pending";
        }
        // One native move per slice. Retained phase is the bounded cursor.
        if (m_State.Phase == "left_pending") { HCMoveStep("left"); return; }
        if (m_State.Phase == "right_pending") { HCMoveStep("right"); return; }
        if (m_State.Phase == "rollback_pending") { HCMoveStep("rollback"); }
    }

    // Observed-completion callback port: NO world stock credit, lease release,
    // casualty debit or item grants. Late provider results are read-only.
    bool HCComplete()
    {
        if (!m_Enabled || !m_Ready || m_Busy || !m_State || m_State.Phase != "complete" || !m_IO) { return false; }
        return m_IO.HCCurrent(m_State) && m_IO.HCLive() && m_IO.HCOwners(m_State, true);
    }

    void HCLog()
    {
        if (!m_State || m_Reports >= 16) { return; }
        m_Reports++;
        string effective = m_Status.HCState();
        string id = "none";
        string bound = "0";
        string observed = "0";
        if (m_State.Id != "") { id = m_State.Id; bound = "1"; }
        if (m_State.Phase == "complete") { observed = "1"; }
        string shown = m_State.Refusal;
        if (m_LogRefusal != "") { shown = m_LogRefusal; }
        string line = "[HC Plan] HC-35 trade=" + id + " phase=" + m_State.Phase;
        line += " transfer=" + m_State.Transfer + " state=" + effective + " refusal=" + shown;
        line += " authored=1 count=" + bound + " observed_complete=" + observed;
        Print(line + " count_cap=1 runtime=PENDING");
    }

    void HCClose()
    {
        if (!m_Enabled) { return; }
        HCAbort("TRADE_STOPPED");
        m_Enabled = false;
        if (m_IO) { m_IO.HCClear(); }
        m_Status.HCPublish("off", "stopped");
    }
}

// Lead registers exactly ONE module; provider is a lifecycle port, no second
// population owner or tick loop. Off/refused/terminal paths never scan/save.
class HCAITrade : HCModule
{
    protected static HCAITrade s_Instance;
    protected static ref HCTradeInventory s_Provider;
    protected ref HCTradeTransaction m_Trade;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected string m_StatusReason;
    protected bool m_ProviderLogged;
    static const string OPT_OUT = "$profile:HollowCountry/acceptance/ai_trade_emote_ack.disable";

    static HCAITrade HCGet() { return s_Instance; }
    static void HCBindProvider(HCTradeInventory port)
    {
        s_Provider = port;
        if (s_Instance) { s_Instance.HCRefreshStatus(); }
    }

    // Wave 16: module state is derived from the real provider state each tick
    // (cheap string compare; publishes only on change). Ready means started, recipe
    // and journal loaded, tick running. A quarantined journal or failed save keeps
    // its own refusal and is never overwritten here.
    void HCRefreshStatus()
    {
        if (!m_Trade || !m_Trade.m_Enabled || !m_Trade.m_State) { return; }
        if (!m_Trade.m_Ready || m_Trade.m_State.Phase == "quarantined")
        {
            string journalReason = m_Trade.m_State.Refusal;
            if (m_Trade.m_LogRefusal != "") { journalReason = m_Trade.m_LogRefusal; }
            m_Status.HCPublish("refused", journalReason);
            return;
        }
        if (s_Provider)
        {
            string providerFault = s_Provider.HCOperationalFault();
            if (providerFault != "")
            {
                m_StatusReason = "";
                m_Status.HCPublish("refused", providerFault);
                return;
            }
        }
        bool bound = false;
        bool providerReady = false;
        if (s_Provider) { bound = true; providerReady = s_Provider.HCReady(); }
        string reason = HCTradeReadiness.HCTradeReadinessReason(bound, providerReady);
        if (reason == m_StatusReason) { return; }
        m_StatusReason = reason;
        m_Status.HCPublish("ready", reason);
    }

    // One line, first tick: every module has started by then, so a missing addon
    // is a fact and not a start-order artefact. Never repeats.
    protected void HCProviderLine()
    {
        if (m_ProviderLogged) { return; }
        m_ProviderLogged = true;
        if (s_Provider)
        {
            Print("[HC Plan] HC-35 provider=bound trade=ai_only rendezvous_route=installed_road_plan_per_pair runtime=PENDING");
            return;
        }
        Print("[HC Plan] HC-35 provider=absent reason=expansion_ai_addon_not_loaded trade=none runtime=PENDING");
    }
    override string GetName() { return "AITrade"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings))
        {
            m_Status.HCPublish("off", "operator_disabled");
            Print("[HC Plan] HC-35 trade=none phase=off transfer=none state=off count=0 runtime=PENDING");
            return;
        }
        if (!GetGame() || !GetGame().IsServer()) { return; }
        Print(HCV2Admission.Line("AITrade", true, "HC35-NATIVE-BARTER", false));
        if (FileExist(HCAITrade.OPT_OUT)) // EnSystem.c:397
        {
            m_Status.HCPublish("off", "operator_opt_out");
            Print("[HC Plan] HC-35 trade=none phase=off transfer=none state=off refusal=OPERATOR_OPT_OUT count=0 runtime=PENDING");
            return;
        }
        m_Trade = new HCTradeTransaction;
        m_Trade.m_Status = m_Status;
        string error;
        HCTradeRecipe recipe;
        string encoded = HCWorldStore.Read("$mission:hollow-country/ai/trade-recipes.json");
        bool parsed = false;
        if (encoded.Length() > 0 && encoded.Length() <= 4096)
        {
            parsed = JsonFileLoader<HCTradeRecipe>.LoadData(encoded, recipe, error);
        }
        if (parsed && recipe) { recipe.HCApplyDefaults(encoded); }
        if (!parsed || !recipe || !recipe.HCValid() || !recipe.HCOfferConfigValid())
        {
            m_Status.HCPublish("refused", "TRADE_RECIPE_INVALID");
            Print("[HC Plan] HC-35 trade=none phase=refused transfer=none state=refused refusal=TRADE_RECIPE_INVALID count=0 runtime=PENDING");
            return;
        }
        m_Trade.m_Recipe = recipe;
        m_Trade.m_Store = new HCEncounterStore<HCTradeState>("hc35-first-trade");
        m_Trade.m_State = m_Trade.m_Store.Load(new HCTradeState, "Phase");
        if (!m_Trade.HCValidState(m_Trade.m_State))
        {
            m_Status.HCPublish("refused", "TRADE_JOURNAL_INVALID");
            Print("[HC Plan] HC-35 trade=none phase=refused transfer=unknown state=refused refusal=TRADE_JOURNAL_INVALID count=0 runtime=PENDING");
            return;
        }
        m_Trade.m_Enabled = true;
        m_Trade.m_Ready = true;
        m_Trade.HCRestore();
        s_Instance = this;
        // Wave 16 owner decision: the emote acknowledgement has no recorded native or
        // two-client verdict, so it is admitted unverified (never claimed as proven).
        // Operator opt-out: acceptance/ai_trade_emote_ack.disable in the profile.
        string admission = "[HC Plan] HC-35 emote_ack=admitted unverified gate=TRADE_RENDEZVOUS_EMOTE_ACK_UNVERIFIED";
        Print(admission + " opt_out=acceptance/ai_trade_emote_ack.disable runtime=PENDING");
        if (m_Trade.m_State.Phase != "quarantined") { m_Status.HCPublish("ready", "awaiting_provider_bind"); }
        else { m_Status.HCPublish("refused", m_Trade.m_State.Refusal); }
        m_Trade.HCLog();
    }

    // Lead's provider activity calls with two already claimed/funded leases.
    // The adapter only starts a swap when the pair is funded; no scan or repeated offer loop.
    // CONSUMER NOTE (#193): ANY HCBegin releases a terminal journal (cancelled, rolled_back
    // or complete) to idle before it admits the next exchange. A consumer that wants the
    // result of a complete exchange must read HCObservedComplete(tradeId) BEFORE its next
    // HCBegin, or latch its own result; after the release the completion is gone.
    // Wave 16: HCXAITradeAdapter binds itself from the addon (modded HCXAIAdapter.OnStart).
    bool HCBegin(string leftLease, string rightLease)
    {
        if (!GetGame() || !GetGame().IsServer() || !m_Trade || !s_Provider) { return false; }
        s_Provider.Recipe = m_Trade.m_Recipe;
        m_Trade.m_IO = s_Provider;
        return m_Trade.HCBegin(leftLease, rightLease, HCWorldClock.UTC());
    }

    HCTradeRecipe HCRecipe() { if (m_Trade) { return m_Trade.m_Recipe; } return null; }
    HCTradeState HCState() { if (m_Trade) { return m_Trade.m_State; } return null; }
    bool HCTrading() { return m_Trade && m_Trade.HCActive(); }

    bool HCObservedComplete(string tradeId)
    {
        if (!GetGame() || !GetGame().IsServer() || !m_Trade || !m_Trade.m_State) { return false; }
        return tradeId == m_Trade.m_State.Id && m_Trade.HCComplete();
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Trade || !m_Trade.m_Enabled || !m_Trade.m_Ready) { return; }
        HCProviderLine();
        HCRefreshStatus();
        if (!m_Trade.HCActive()) { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        m_Trade.HCStep(HCWorldClock.UTC());
    }

    override void OnStop()
    {
        if (m_Trade) { m_Trade.HCClose(); }
        if (s_Instance == this) { s_Instance = null; }
        m_Status.HCPublish("off", "stopped");
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCAITrade);
    }
}

// #145: pure admission policy shared with the funded-pair producer. Supply is
// the existing HC-16 allocation, never a grant of native inventory.
class HCTradeOfferPolicy
{
    static bool HCEligible(string leftCamp, string rightCamp, int relation, int leftSupply, int rightSupply, int reserve)
    {
        return leftCamp != "" && rightCamp != "" && leftCamp != rightCamp && relation > 0 && leftSupply > reserve && rightSupply > reserve;
    }
    static bool HCDue(int now, int previous, int interval)
    {
        return now > 0 && now >= previous && (previous == 0 || now - previous >= interval);
    }
}

class HCTradeLossRow
{
    string Key;
    string Phase = "new";
    string LeftCamp;
    string RightCamp;
    int Debit;
}
class HCTradeLossData
{
    int Version = 1;
    ref array<ref HCTradeLossRow> Rows = new array<ref HCTradeLossRow>;
}
// A synchronous intent is durable BEFORE the single two-camp save. A crash
// between stores leaves intent UNKNOWN, never replayed or silently accepted.
// No distributed atomicity/Hive claim. Completed rows also remember the damaged
// camp relationship; the producer does not immediately offer the same pair.
class HCTradeLossBarrier
{
    ref HCTradeLossRow m_Row;
    ref HCTradeLossData m_Data;
    ref HCEncounterStore<HCTradeLossData> m_Store;
    bool m_Ready;
    bool HCDebit(HCTradeLossRow row)
    {
        HCHoldouts homes = HCHoldouts.Get();
        return homes && homes.HCTradeDebit(row.LeftCamp, row.RightCamp, row.Debit);
    }
    bool HCApply()
    {
        if (!m_Ready || !m_Row || !m_Store) { return false; }
        if (m_Row.Phase == "complete") { return true; }
        if (m_Row.Phase != "new") { return false; }
        m_Row.Phase = "intent";
        if (!m_Store.Save(m_Data)) { m_Ready = false; return false; }
        if (!HCDebit(m_Row)) { m_Ready = false; return false; }
        m_Row.Phase = "complete";
        if (!m_Store.Save(m_Data)) { m_Ready = false; return false; }
        return true;
    }
}

// Native 1_Core/proto/EnMath.c:566 Max.
// Narrow HC-16 mutation seam implemented in this area's file. One owner save
// changes BOTH already-funded allocations; no direct world-ledger alias escapes.
modded class HCHoldouts
{
    bool HCTradeCanDebit(string leftHome, string rightHome)
    {
        if (!m_Ready || !m_State || leftHome == rightHome) { return false; }
        bool leftReady = false;
        bool rightReady = false;
        array<ref HCHoldoutRow> homes = m_State.Rows;
        foreach (HCHoldoutRow candidate : homes)
        {
            if (candidate.Ledger.Id == leftHome && candidate.Camp.Allocated) { leftReady = true; }
            if (candidate.Ledger.Id == rightHome && candidate.Camp.Allocated) { rightReady = true; }
        }
        return leftReady && rightReady;
    }
    bool HCTradeDebit(string leftHome, string rightHome, int debit)
    {
        if (!m_Ready || !m_State || leftHome == rightHome || debit < 1) { return false; }
        HCHoldoutRow leftRow;
        HCHoldoutRow rightRow;
        array<ref HCHoldoutRow> homes = m_State.Rows;
        foreach (HCHoldoutRow candidate : homes)
        {
            if (candidate.Ledger.Id == leftHome) { leftRow = candidate; }
            if (candidate.Ledger.Id == rightHome) { rightRow = candidate; }
        }
        if (!leftRow || !rightRow || !leftRow.Camp.Allocated || !rightRow.Camp.Allocated) { return false; }
        // Never underflow after intervening upkeep/raid; an empty allocation
        // loses its remaining stock, not newly invented debt or population.
        leftRow.Camp.Supply = Math.Max(0, leftRow.Camp.Supply - debit);
        rightRow.Camp.Supply = Math.Max(0, rightRow.Camp.Supply - debit);
        m_Dirty = true;
        return SaveChanged();
    }
}
