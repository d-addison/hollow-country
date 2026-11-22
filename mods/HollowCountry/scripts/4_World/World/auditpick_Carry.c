// Pick-carry: additive HC-34 receipts, no Hive rebind or replay. Search still owns
// the pickup transaction. Each receipt is durable BEFORE that commit; each home
// move has its own intent/result barrier in the SAME atomic trip store.
// Native scripts-1.30.164289: EntityAI.c:882 GetHierarchyRootPlayer, :3374
// GetPersistentID (via HCSearchSupplyRegistry); EnScript.c:380 Count, :385 Clear,
// :407 Insert; EnDebug.c:96 Print. HCMove's native citations are in HCPickers.c.
// No new engine/Expansion API. Runtime acceptance PENDING.
class HCPickCarryReceipt
{
    string ItemId;
    string Phase;
}

// Reuse the identical HC-16/34 same-item native custody path, without swapping
// the primary item or its journal id. Lease and arrival retain the LIVE provider's
// guards (including any theft guard). This short-lived port never owns the party.
class HCPickCarryInventory : HCScavengeInventory
{
    HCScavengeInventory CarrierPort;
    HCScavengeState CarrierRow;

    override bool HCPartyCurrent(HCScavengeState row)
    {
        return CarrierPort && CarrierPort.HCPartyCurrent(row);
    }

    // Repeat the provider's observer/lock veto after native preflight callbacks.
    override bool HCAccessible(EntityAI cache)
    {
        if (!CarrierPort || !HCCampTheft.HCGuard(CarrierPort, CarrierRow)) { return false; }
        return CarrierPort.HCAccessible(cache);
    }

    override bool HCAtHome()
    {
        return CarrierPort && CarrierPort.HCAtHome();
    }
}

class HCPickCarry
{
    // Weak live handles only. Persistent ids live in the trip journal; restart
    // quarantines the trip, never searches bodies or reconstructs an item.
    ref array<EntityAI> Handles = new array<EntityAI>;

    protected int m_Unloaded;
    protected bool m_UnloadReported;

    void HCClear() { Handles.Clear(); m_Unloaded = 0; m_UnloadReported = false; }

    bool HCPrepare(HCScavengeInventory port, HCScavengeTrip trip, EntityAI goods, HCScavengeState row)
    {
        if (!trip || !trip.m_Ready || trip.m_Busy || trip.m_State != row) { return false; }
        if (!row || row.Phase != "leaving" || !port.Survey || !port.HCLive() || !port.HCPartyCurrent(row)) { return false; }
        string itemId = HCSearchSupplyRegistry.PersistentId(goods);
        if (!goods || itemId == "") { return false; }
        if (!row.HouseGoods) { row.HouseGoods = new array<ref HCPickCarryReceipt>(); }
        if (row.HouseGoods.Count() >= port.Survey.RunMaxCarriedHouseGoods) { return false; }
        for (int priorIndex = 0; priorIndex < row.HouseGoods.Count(); priorIndex++)
        {
            if (row.HouseGoods[priorIndex].ItemId == itemId) { return false; }
        }
        HCPickCarryReceipt receipt = new HCPickCarryReceipt;
        receipt.ItemId = itemId;
        receipt.Phase = "claim";
        row.HouseGoods.Insert(receipt);
        Handles.Insert(goods);
        return trip.HCCheckpoint();
    }

    bool HCResult(HCScavengeInventory port, HCScavengeTrip trip, bool committed, HCScavengeState row)
    {
        if (!trip || !trip.m_Ready || trip.m_State != row || row.Phase != "leaving") { return false; }
        int last = row.HouseGoods.Count() - 1;
        HCPickCarryReceipt receipt = row.HouseGoods[last];
        EntityAI goods = Handles[last];
        receipt.Phase = "refused";
        if (committed && goods && HCSearchSupplyRegistry.PersistentId(goods) == receipt.ItemId && goods.GetHierarchyRootPlayer() == port.Actor)
        {
            receipt.Phase = "held";
        }
        return trip.HCCheckpoint();
    }

    // One receipt per tick, charged to shared work. Full/refused is terminal for
    // this receipt: retain the physical item and log once; no retry or refund.
    string HCUnload(HCScavengeInventory port, HCScavengeTrip trip, HCScavengeState row)
    {
        if (!trip || !trip.m_Ready || trip.m_Busy || trip.m_State != row) { return ""; }
        if (!row || row.Phase != "returning" || !row.HouseGoods) { return ""; }
        if (!port.HCLive() || !port.HCPartyCurrent(row) || !port.HCAtHome()) { return ""; }
        int count = row.HouseGoods.Count();
        if (count > port.Survey.RunMaxCarriedHouseGoods || Handles.Count() != count) { return "RUN_ABORT_HOUSE_HANDLES_UNAVAILABLE"; }
        for (int carryIndex = 0; carryIndex < count; carryIndex++)
        {
            HCPickCarryReceipt receipt = row.HouseGoods[carryIndex];
            if (receipt.Phase != "held") { continue; }
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_PICK_CARRY, 1)) { return HCPickRunner.HOLD; }
            ItemBase goods = ItemBase.Cast(Handles[carryIndex]);
            receipt.Phase = "absent";
            if (!goods || HCSearchSupplyRegistry.PersistentId(goods) != receipt.ItemId || goods.GetHierarchyRootPlayer() != port.Actor)
            {
                if (!trip.HCCheckpoint()) { return "RUN_ABORT_HOUSE_JOURNAL"; }
                return HCPickRunner.HOLD;
            }
            receipt.Phase = "depositing";
            trip.m_Busy = true;
            if (!trip.HCCheckpoint()) { trip.m_Busy = false; return "RUN_ABORT_HOUSE_JOURNAL"; }
            HCPickCarryInventory transfer = new HCPickCarryInventory;
            transfer.CarrierPort = port;
            transfer.CarrierRow = row;
            transfer.Actor = port.Actor;
            transfer.Source = port.Source;
            transfer.Home = port.Home;
            transfer.Item = goods;
            transfer.Defaults = port.Defaults;
            transfer.Survey = port.Survey;
            int result = transfer.HCMove(true, row);
            trip.m_Busy = false;
            // A cancellation inside a native callback owns the terminal evidence.
            if (!trip.m_Ready || row.Phase != "returning") { return "RUN_ABORT_HOUSE_INTERRUPTED"; }
            receipt.Phase = "uncertain";
            if (result == 2) { receipt.Phase = "deposited"; }
            if (result == 4) { receipt.Phase = "retained"; }
            if (!trip.HCCheckpoint()) { return "RUN_ABORT_HOUSE_JOURNAL"; }
            m_Unloaded++;
            if (result == 3) { return "RUN_ABORT_HOUSE_CUSTODY_UNCERTAIN"; }
            return HCPickRunner.HOLD;
        }
        if (!m_UnloadReported)
        {
            m_UnloadReported = true;
            Print("[HC Pickers] run goods processed=" + m_Unloaded.ToString() + " runtime=PENDING");
        }
        return "";
    }
}
