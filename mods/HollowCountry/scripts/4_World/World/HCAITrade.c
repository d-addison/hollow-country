// HC-35/#145: one reciprocal recipe, two EXISTING HC-10-funded parties.
// Spec/plan/task: HC-16 funding -> HC-10 custody -> HC-34 same-item barriers
// -> rendezvous -> observed gestures -> two moves -> receipt or quarantine.
// No abstract bargain creates cargo; no stock credit/debit, rewards or UI.
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
// SDK. Pinned Expansion ai/core sources absent: named refusal in addon port.
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

    bool HCValid()
    {
        HCScavengeDefaults pickup = new HCScavengeDefaults;
        if (Version != 1 || RecipeId != "bandage-for-drink") { return false; }
        if (LeftClass != "BandageDressing" || RightClass != "SodaCan_Kvass") { return false; }
        if (TimeoutSeconds < 1 || TimeoutSeconds > 300) { return false; }
        return TransferRangeMeters > 0 && TransferRangeMeters <= pickup.TransferRangeMeters;
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

    // One first encounter identity for this content slice, never reset/evict.
    // Existing HC-10 leases already own the finite HC-16 funded party budgets.
    // No independent actor reservation, abstract debit or cargo mint here.
    bool HCBegin(string leftLease, string rightLease, int now)
    {
        if (!m_Enabled || !m_Ready || m_Busy || !m_State || m_State.Phase != "idle" || !m_IO) { return false; }
        if (now < 1 || now > 2146878847 || leftLease == rightLease) { return false; }
        if (!m_IO.HCReady()) { m_State.Refusal = m_IO.HCRefusal(); HCLog(); return false; }
        HCAIPartyIdentity left = HCWorldMaterializer.HCIdentity(leftLease);
        HCAIPartyIdentity right = HCWorldMaterializer.HCIdentity(rightLease);
        if (!HCAIPartyIdentity.HCValid(left) || !HCAIPartyIdentity.HCValid(right)) { return false; }
        if (left.HCPartyId() == right.HCPartyId() || left.HCCargoId() == right.HCCargoId()) { return false; }
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
        if (now < m_State.StartedAt || now >= m_State.EndsAt) { HCAbort("TRADE_RENDEZVOUS_TIMEOUT"); return; }
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
        string effective = "refused";
        if (!m_Enabled) { effective = "off"; }
        else if (m_Ready && m_IO && m_IO.HCReady() && m_State.Phase != "quarantined") { effective = "ready"; }
        string id = "none";
        string bound = "0";
        string observed = "0";
        if (m_State.Id != "") { id = m_State.Id; bound = "1"; }
        if (m_State.Phase == "complete") { observed = "1"; }
        string line = "[HC Plan] HC-35 trade=" + id + " phase=" + m_State.Phase;
        line += " transfer=" + m_State.Transfer + " state=" + effective + " refusal=" + m_State.Refusal;
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

    static HCAITrade HCGet() { return s_Instance; }
    static void HCBindProvider(HCTradeInventory port) { s_Provider = port; }
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
        if (!parsed || !recipe || !recipe.HCValid())
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
        if (m_Trade.m_State.Phase != "quarantined")
        {
            m_Status.HCPublish("refused", "TRADE_RENDEZVOUS_EMOTE_ACK_UNVERIFIED");
            m_Trade.m_State.Refusal = "TRADE_RENDEZVOUS_EMOTE_ACK_UNVERIFIED";
        }
        else { m_Status.HCPublish("refused", m_Trade.m_State.Refusal); }
        m_Trade.HCLog();
    }

    // Lead's provider activity calls with two already claimed/funded leases.
    // Shipping adapter refuses, so there is no scan or repeated offer loop.
    bool HCBegin(string leftLease, string rightLease)
    {
        if (!GetGame() || !GetGame().IsServer() || !m_Trade || !s_Provider) { return false; }
        s_Provider.Recipe = m_Trade.m_Recipe;
        m_Trade.m_IO = s_Provider;
        return m_Trade.HCBegin(leftLease, rightLease, HCWorldClock.UTC());
    }

    bool HCObservedComplete(string tradeId)
    {
        if (!GetGame() || !GetGame().IsServer() || !m_Trade || !m_Trade.m_State) { return false; }
        return tradeId == m_Trade.m_State.Id && m_Trade.HCComplete();
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Trade || !m_Trade.m_Enabled || !m_Trade.m_Ready || !m_Trade.HCActive()) { return; }
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
