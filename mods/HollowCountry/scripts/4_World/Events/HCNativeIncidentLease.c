// HC-41/#147: observation leases, never a second CE event/wreck/inventory.
// Native evidence, scripts-1.30.164289 (all paths relative to that snapshot):
// 3_Game/CE/CentralEconomy.c:228-735 CEApi has spawning/debug controls, but
// no DE-instance enumeration, identity/ownership receipt or lifecycle callback.
// EntityAI.c:888 GetEconomyProfile is NOT incident membership evidence.
// 3_Game/Entities/EntityAI.c:3374 GetPersistentID survives restart; consumed
// through HCSearchSupplyRegistry.PersistentId, never GetID/position/class ID.
// 3_Game/Entities/Object.c:215 IsPendingDeletion, :1219 IsRuined;
// 3_Game/Entities/EntityAI.c:882/885 hierarchy; Game.c:1120 IsServer;
// 3_Game/gameplay.c:636 GetGame; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnScript.c:380/394/407 Count/Find/Insert; EnString.c:199 Length.
// 1_Core/proto/EnSystem.c:397 FileExist; EnScript.c:463 Remove.
// 1_Core/proto/EnConvert.c:30 int.ToString. All other calls are existing HC ports.
// No new ranges, query, spawning, lifetime writes, inventory moves or deletion.
// HC-34 owns any eventual same-item custody transfer (currently refuses loose
// incident loot without a qualified source/route). Issuing a handle below is
// an observation claim, NOT proof of transfer or an inventory credit.

class HCNativeIncidentReceipt
{
    EntityAI Anchor;
    ref array<ItemBase> Stock = new array<ItemBase>;
}

// Trusted server-only capability port. No client/config assertion admits CE
// ownership. Integration must prove one family and actual stock association
// before overriding this port; nearby loose loot and CEItemProfile do not.
class HCNativeIncidentSource
{
    // CE callback provenance, never class/position inference. Native:
    // 4_World/Entities/Building/CrashBase.c:15 EEOnCECreate, :46 EEDelete;
    // EntityAI.c:1414 EEOnCECreate; Inventory.c:138 GetCargo;
    // 3_Game/Systems/Inventory/Cargo.c:29 GetItemCount, :34 GetItem.
    // Stock belongs only through direct native cargo ancestry. Vanilla crash
    // loot usually lies on the ground: that missing attribution stays explicit.
    // EntityAI.c:1414 EEOnCECreate has no source/parent parameter and is also
    // called for debug creation. CentralEconomy.c:749-768 CEItemProfile carries
    // economy policy only. Neither can bind a loose item to a crash instance.
    // Registering an item by callback timing/distance would admit unrelated loot.
    protected static ref array<CrashBase> s_Crashes = new array<CrashBase>;
    protected static bool s_AdmissionPrinted;
    protected static bool s_StockPendingPrinted;
    protected static int s_Cursor;

    static void HCRegister(CrashBase crash)
    {
        if (!GetGame() || !GetGame().IsServer() || !crash) { return; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        if (!policy) { return; }
        if (s_Crashes.Find(crash) < 0 && s_Crashes.Count() < policy.MaxIncidents) { s_Crashes.Insert(crash); }
    }

    static void HCRemove(CrashBase crash)
    {
        int index = s_Crashes.Find(crash);
        if (index >= 0) { s_Crashes.Remove(index); }
    }

    protected static bool s_MarkerProbed;
    protected static bool s_MarkerOff;
    bool HCReady()
    {
        // Operator marker is probed once per process, like the other acceptance markers.
        if (!s_MarkerProbed)
        {
            s_MarkerProbed = true;
            s_MarkerOff = FileExist("$profile:HollowCountry/acceptance/w38_incidents.disable");
        }
        bool enabled = !s_MarkerOff;
        if (!GetGame() || !GetGame().IsServer() || !enabled || !HCW38SituationPolicy.HCGet()) { return false; }
        if (!s_AdmissionPrinted)
        {
            s_AdmissionPrinted = true;
            Print(HCV2Admission.Line("NativeIncidents", enabled, "w38_incidents", false) + " runtime=PENDING");
            s_StockPendingPrinted = true;
            Print("[HC Situations] CE_CRASH_LOOSE_STOCK_ATTRIBUTION_PENDING anchor_observation=ready cargo_provenance=direct_ancestry loose_stock=unavailable reason=CE_INSTANCE_MEMBERSHIP_API_UNEXPOSED runtime=PENDING");
        }
        return true;
    }
    string HCRefusal()
    {
        if (!GetGame() || !GetGame().IsServer()) { return "NATIVE_INCIDENT_SERVER_REQUIRED"; }
        if (FileExist("$profile:HollowCountry/acceptance/w38_incidents.disable")) { return "operator_off"; }
        if (!HCW38SituationPolicy.HCGet()) { return "SITUATION_POLICY_INVALID"; }
        return "CE_CRASH_LOOSE_STOCK_ATTRIBUTION_PENDING";
    }
    HCNativeIncidentReceipt HCObserve()
    {
        if (!HCReady() || s_Crashes.Count() == 0) { return null; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        s_Cursor = s_Cursor % s_Crashes.Count();
        CrashBase crash = s_Crashes[s_Cursor];
        s_Cursor++;
        if (!HCPresent(crash)) { return null; }
        HCNativeIncidentReceipt receipt = new HCNativeIncidentReceipt;
        receipt.Anchor = crash;
        if (crash.GetInventory())
        {
            CargoBase cargo = crash.GetInventory().GetCargo();
            if (cargo)
            {
                int count = cargo.GetItemCount();
                if (count > policy.MaxIncidentItems) { return null; }
                for (int index = 0; index < count; index++)
                {
                    ItemBase item = ItemBase.Cast(cargo.GetItem(index));
                    if (HCContains(crash, item)) { receipt.Stock.Insert(item); }
                }
            }
        }
        if (receipt.Stock.Count() == 0 && !s_StockPendingPrinted)
        {
            s_StockPendingPrinted = true;
            Print("[HC Situations] CE_CRASH_LOOSE_STOCK_ATTRIBUTION_PENDING anchor_observation=ready cargo_provenance=direct_ancestry loose_stock=unavailable reason=CE_INSTANCE_MEMBERSHIP_API_UNEXPOSED runtime=PENDING");
        }
        return receipt;
    }
    bool HCPresent(EntityAI anchor)
    {
        CrashBase crash = CrashBase.Cast(anchor);
        return crash && !crash.IsPendingDeletion() && s_Crashes.Find(crash) >= 0;
    }
    bool HCContains(EntityAI anchor, ItemBase item)
    {
        return HCPresent(anchor) && item && !item.IsPendingDeletion() && !item.IsRuined() && !item.GetHierarchyRootPlayer() && item.GetHierarchyParent() == anchor;
    }
}

class HCNativeIncidentRow
{
    string Id;
    string LeaseId;
    string Phase = "leased";
    ref array<string> StockIds = new array<string>;
    ref array<string> IssuedIds = new array<string>;
}

class HCNativeIncidentState
{
    int Version = 1;
    // Permanent tombstones. Full ledger refuses new work; never trim/refill.
    ref array<ref HCNativeIncidentRow> Rows = new array<ref HCNativeIncidentRow>;
}

class HCNativeIncidentLease
{
    protected ref HCNativeIncidentSource m_Source;
    protected ref HCEncounterStore<HCNativeIncidentState> m_Store;
    protected ref HCNativeIncidentState m_State;
    protected ref HCNativeIncidentReceipt m_Receipt;
    protected ref HCNativeIncidentRow m_Active;
    protected ref HCW38SituationPolicy m_Policy;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected bool m_Enabled;
    protected bool m_Fault;
    protected bool m_Opened;
    protected bool m_Busy;
    protected string m_Effective = "off";
    protected string m_Reason = "not_started";
    protected int m_Reports;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;

    static bool HCValid(HCNativeIncidentState state)
    {
        // Persisted schema ceilings retain spent identities even when an operator
        // lowers the admission caps. Runtime work uses HCW38SituationPolicy.
        if (!state || state.Version != 1 || !state.Rows || state.Rows.Count() > 64) { return false; }
        array<string> identities = new array<string>();
        array<ref HCNativeIncidentRow> rows = state.Rows;
        foreach (HCNativeIncidentRow row : rows)
        {
            if (!row || !HCEventDirector.TextValid(row.Id, 96) || !HCEventDirector.TextValid(row.LeaseId, 128)) { return false; }
            if (identities.Find(row.Id) >= 0 || (row.Phase != "leased" && row.Phase != "closed")) { return false; }
            identities.Insert(row.Id);
            if (!row.StockIds || !row.IssuedIds || row.StockIds.Count() > 16 || row.IssuedIds.Count() > row.StockIds.Count()) { return false; }
            array<string> stockSeen = new array<string>();
            array<string> stockIds = row.StockIds;
            foreach (string stockId : stockIds)
            {
                if (!HCEventDirector.TextValid(stockId, 96) || stockSeen.Find(stockId) >= 0) { return false; }
                stockSeen.Insert(stockId);
            }
            array<string> issuedSeen = new array<string>();
            array<string> issuedIds = row.IssuedIds;
            foreach (string issuedId : issuedIds)
            {
                if (stockSeen.Find(issuedId) < 0 || issuedSeen.Find(issuedId) >= 0) { return false; }
                issuedSeen.Insert(issuedId);
            }
        }
        return true;
    }

    void HCReport()
    {
        if (m_Reports >= 16) { return; }
        m_Reports = m_Reports + 1;
        string incidentId = "none";
        string phase = "none";
        int retained = 0;
        if (m_State) { retained = m_State.Rows.Count(); }
        if (m_Active) { incidentId = m_Active.Id; phase = m_Active.Phase; }
        string line = "[HC Plan] HC-41 native_incident=" + incidentId + " lease=" + phase + " stock_owner=native";
        line += " state=" + m_Effective + " refusal=" + m_Reason;
        HCW38SituationPolicy policy = m_Policy;
        string caps = " caps=policy_unavailable";
        if (policy)
        {
            caps = " cap=" + policy.MaxIncidents.ToString() + " active_cap=" + policy.MaxConcurrent.ToString() + " stock_cap=" + policy.MaxIncidentItems.ToString();
        }
        line += " retained=" + retained.ToString() + caps;
        Print(line + " cargo_provenance=direct_ancestry loose_stock=unavailable runtime=PENDING");
    }

    HCOperationalStatus HCStatus()
    {
        // The observer can operate while loose-stock membership is unavailable.
        // Keep that partial capability in the reason; never call it loot-ready.
        m_Status.HCPublish(m_Effective, m_Reason);
        return m_Status;
    }

    protected bool HCRefuse(string reason)
    {
        if (m_Effective == "refused" && m_Reason == reason) { return false; }
        m_Reason = reason;
        m_Effective = "refused";
        HCReport();
        return false;
    }

    protected bool HCCommit()
    {
        if (m_Fault || !HCValid(m_State) || !m_Store.Save(m_State))
        {
            m_Fault = true;
            m_Enabled = false;
            m_Receipt = null;
            m_Source = null;
            return HCRefuse("NATIVE_INCIDENT_STORE_UNCERTAIN");
        }
        HCReport();
        return true;
    }

    bool HCOpen(HCNativeIncidentSource source, bool enabled)
    {
        // Single open per owner. Off/unexposed performs no disk/query work.
        if (m_Opened || m_Fault) { return false; }
        m_Opened = true;
        m_Effective = "off";
        m_Reason = "operator_off";
        if (!HCV2Admission.Admitted(enabled) || FileExist("$profile:HollowCountry/acceptance/w38_incidents.disable")) { HCReport(); return false; }
        if (!GetGame() || !GetGame().IsServer()) { return HCRefuse("NATIVE_INCIDENT_SERVER_REQUIRED"); }
        m_Policy = HCW38SituationPolicy.HCGet();
        if (!m_Policy) { return HCRefuse("SITUATION_POLICY_INVALID"); }
        if (!source || !source.HCReady())
        {
            string reason = "CE_INCIDENT_LIFECYCLE_UNEXPOSED";
            if (source) { reason = source.HCRefusal(); }
            return HCRefuse(reason);
        }
        m_Source = source;
        m_Store = new HCEncounterStore<HCNativeIncidentState>("hc41-native-incidents");
        HCNativeIncidentState initialState = new HCNativeIncidentState;
        m_State = m_Store.Load(initialState, "Rows");
        if (!HCValid(m_State)) { m_Fault = true; m_Source = null; return HCRefuse("NATIVE_INCIDENT_STATE_INVALID"); }
        m_Enabled = true;
        // Hive and journal are not one transaction. Never rebind live intents
        // across restart; all prior identities stay spent even after CE returns.
        bool changed = false;
        array<ref HCNativeIncidentRow> restoredRows = m_State.Rows;
        foreach (HCNativeIncidentRow row : restoredRows)
        {
            if (row.Phase == "leased") { row.Phase = "closed"; changed = true; }
        }
        m_Effective = "ready";
        m_Reason = "anchor_observation_ready_loose_stock_attribution_pending";
        if (changed) { m_Reason = "PAIRED_NATIVE_RESTORE_UNPROVEN"; return HCCommit(); }
        HCReport();
        return true;
    }

    bool HCBorrow(string partyLease)
    {
        if (!m_Enabled || m_Busy || m_Fault || m_Active) { return false; }
        if (!GetGame() || !GetGame().IsServer() || !m_Source.HCReady()) { return false; }
        if (!HCEventDirector.TextValid(partyLease, 128) || !HCWorldMaterializer.HCIdentity(partyLease)) { return HCRefuse("NATIVE_INCIDENT_PARTY_UNOWNED"); }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        if (!policy) { return HCRefuse("SITUATION_POLICY_INVALID"); }
        if (m_State.Rows.Count() >= policy.MaxIncidents) { return HCRefuse("NATIVE_INCIDENT_HISTORY_FULL"); }
        HCNativeIncidentReceipt receipt = m_Source.HCObserve();
        if (!receipt || !receipt.Anchor || receipt.Anchor.IsPendingDeletion()) { return HCRefuse("NATIVE_INCIDENT_DISAPPEARED"); }
        if (!m_Source.HCPresent(receipt.Anchor)) { return HCRefuse("NATIVE_INCIDENT_DISAPPEARED"); }
        string incidentId = HCSearchSupplyRegistry.PersistentId(receipt.Anchor);
        if (!HCEventDirector.TextValid(incidentId, 96)) { return HCRefuse("NATIVE_INCIDENT_ID_UNAVAILABLE"); }
        array<ref HCNativeIncidentRow> priorRows = m_State.Rows;
        foreach (HCNativeIncidentRow prior : priorRows)
        {
            if (prior.Id == incidentId) { return HCRefuse("NATIVE_INCIDENT_ALREADY_LEASED"); }
        }
        if (!receipt.Stock || receipt.Stock.Count() > policy.MaxIncidentItems) { return HCRefuse("NATIVE_INCIDENT_STOCK_OVERFLOW"); }
        if (receipt.Stock.Count() == 0) { return HCRefuse("NATIVE_INCIDENT_STOCK_PENDING"); }
        HCNativeIncidentRow row = new HCNativeIncidentRow;
        row.Id = incidentId;
        row.LeaseId = partyLease;
        HCNativeIncidentReceipt snapshot = new HCNativeIncidentReceipt;
        snapshot.Anchor = receipt.Anchor;
        array<ItemBase> observedStock = receipt.Stock;
        foreach (ItemBase item : observedStock)
        {
            if (!HCStockLive(receipt.Anchor, item)) { return HCRefuse("NATIVE_INCIDENT_STOCK_UNOBSERVED"); }
            string itemId = HCSearchSupplyRegistry.PersistentId(item);
            if (!HCEventDirector.TextValid(itemId, 96) || row.StockIds.Find(itemId) >= 0) { return HCRefuse("NATIVE_INCIDENT_STOCK_ID_INVALID"); }
            row.StockIds.Insert(itemId);
            snapshot.Stock.Insert(item);
        }
        m_Active = row;
        m_State.Rows.Insert(row);
        m_Effective = "ready";
        m_Reason = "native_stock_observed";
        // Barrier BEFORE handing any reference to custody/provider code.
        m_Busy = true;
        bool committed = HCCommit();
        m_Busy = false;
        if (!committed || !m_Enabled) { return false; }
        // Retain only the original handles, never a mutable provider stock list.
        m_Receipt = snapshot;
        return true;
    }

    protected bool HCStockLive(EntityAI anchor, ItemBase item)
    {
        return item && !item.IsPendingDeletion() && !item.IsRuined() && !item.GetHierarchyRootPlayer() && (!item.GetHierarchyParent() || item.GetHierarchyParent() == anchor) && m_Source.HCContains(anchor, item);
    }

    protected bool HCPresent()
    {
        if (!m_Receipt || !m_Receipt.Anchor || m_Receipt.Anchor.IsPendingDeletion()) { return false; }
        return m_Source.HCReady() && m_Source.HCPresent(m_Receipt.Anchor) && HCSearchSupplyRegistry.PersistentId(m_Receipt.Anchor) == m_Active.Id;
    }

    // At most one exact existing handle per snapshot ID; no replacement scan.
    // The barrier consumes this observation claim even if HC-34 later refuses.
    ItemBase HCTakeStock(string itemId)
    {
        if (!m_Enabled || m_Busy || !m_Active || m_Active.Phase != "leased") { return null; }
        if (!GetGame() || !GetGame().IsServer()) { return null; }
        if (!HCPresent()) { HCFinish("NATIVE_INCIDENT_DISAPPEARED"); return null; }
        if (!HCWorldMaterializer.HCIdentity(m_Active.LeaseId)) { HCFinish("NATIVE_INCIDENT_PARTY_LOST"); return null; }
        if (m_Active.StockIds.Find(itemId) < 0 || m_Active.IssuedIds.Find(itemId) >= 0) { return null; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        if (!policy) { return null; }
        if (!m_Receipt.Stock || m_Receipt.Stock.Count() > policy.MaxIncidentItems) { HCFinish("NATIVE_INCIDENT_STOCK_CHANGED"); return null; }
        array<ItemBase> retainedStock = m_Receipt.Stock;
        foreach (ItemBase item : retainedStock)
        {
            if (item && HCSearchSupplyRegistry.PersistentId(item) == itemId)
            {
                if (!HCStockLive(m_Receipt.Anchor, item)) { return null; }
                m_Active.IssuedIds.Insert(itemId);
                m_Busy = true;
                bool committed = HCCommit();
                m_Busy = false;
                if (!committed) { return null; }
                if (!HCPresent() || !HCStockLive(m_Receipt.Anchor, item)) { return null; }
                return item;
            }
        }
        return null;
    }

    protected void HCFinish(string reason)
    {
        if (!m_Enabled || m_Busy || !m_Active || m_Active.Phase != "leased") { return; }
        m_Active.Phase = "closed";
        m_Reason = reason;
        if (reason == "NATIVE_INCIDENT_DISAPPEARED" || reason == "NATIVE_INCIDENT_PARTY_LOST" || reason == "NATIVE_INCIDENT_STOCK_CHANGED") { m_Effective = "refused"; }
        m_Receipt = null;
        HCCommit();
        m_Active = null;
    }

    void HCComplete() { HCFinish("native_observation_complete"); }

    void HCStep()
    {
        if (!m_Enabled || m_Busy || !m_Active || m_Active.Phase != "leased") { return; }
        if (!GetGame() || !GetGame().IsServer()) { return; }
        HCUnitBudget sharedWork = HCServer.HCTickWork();
        if (!sharedWork || !sharedWork.HCTakeFor(HCUnitBudget.HC_WORK_SITUATIONS, 1)) { return; }
        m_Work.HCReset(1);
        if (!m_Work.HCContinue()) { return; }
        if (!HCPresent()) { HCFinish("NATIVE_INCIDENT_DISAPPEARED"); return; }
        if (!HCWorldMaterializer.HCIdentity(m_Active.LeaseId)) { HCFinish("NATIVE_INCIDENT_PARTY_LOST"); }
    }

    void HCClose()
    {
        if (!m_Enabled) { m_Receipt = null; m_Source = null; return; }
        HCFinish("native_observation_stopped");
        m_Enabled = false;
        m_Receipt = null;
        m_Source = null;
        m_Effective = "off";
        if (m_Fault) { m_Effective = "refused"; }
        HCReport();
    }
}

// Observe only actual CE creation, preserving native smoke/sound/lifetime.
modded class CrashBase
{
    override void EEOnCECreate()
    {
        super.EEOnCECreate();
        HCNativeIncidentSource.HCRegister(this);
    }
    override void EEDelete(EntityAI parent)
    {
        HCNativeIncidentSource.HCRemove(this);
        super.EEDelete(parent);
    }
}
