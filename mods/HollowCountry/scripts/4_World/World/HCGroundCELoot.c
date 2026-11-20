// CE owns creation and inventory. This queue only corrects root world items.
class HCGroundCELoot
{
    static const int CAPACITY = 16384;
    protected static ref array<ItemBase> s_Items = new array<ItemBase>;
    protected static ref HCGroundSnapStats s_Stats = new HCGroundSnapStats;
    protected static ref HCWorkBudget s_Budget = new HCWorkBudget;
    protected static bool s_Scheduled;
    protected static int s_Head;
    protected static int s_Tail;
    protected static int s_Count;
    protected static int s_Overflow;
    protected static float s_LogAfter;

    static bool Eligible(ItemBase item)
    {
        return item && !item.IsPendingDeletion() && !item.GetHierarchyParent() && !item.IsTransport() && !item.IsBuilding();
    }

    static void Enqueue(ItemBase item)
    {
        if (!GetGame() || !GetGame().IsServer() || !Eligible(item)) { return; }
        if (s_Count >= CAPACITY) { s_Overflow++; return; }
        if (s_Items.Count() == 0) { s_Items.Resize(CAPACITY); }
        s_Items[s_Tail] = item;
        s_Tail++;
        if (s_Tail == CAPACITY) { s_Tail = 0; }
        s_Count++;
        if (!s_Scheduled)
        {
            s_Scheduled = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Drain, 50, false);
        }
    }

    static void Drain()
    {
        s_Budget.HCReset(4, HCPerfConfig.HCGet().SliceMs);
        while (s_Count > 0 && s_Budget.HCContinue())
        {
            ItemBase item = s_Items[s_Head];
            s_Items[s_Head] = null;
            s_Head++;
            if (s_Head == CAPACITY) { s_Head = 0; }
            s_Count--;
            if (Eligible(item)) { HCGroundSnap.Snap(item, 2.5, 0.08, s_Stats); }
        }
        bool pending = s_Count > 0;
        float now = GetGame().GetTickTime();
        if (now >= s_LogAfter)
        {
            s_Stats.Summary("ce");
            Print("[HC Ground] source=ce_queue overflow=" + s_Overflow.ToString());
            HCGroundSnap.Placed.Summary("hc_placements");
            s_LogAfter = now + 60;
        }
        if (pending) { GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Drain, 50, false); }
        else { s_Scheduled = false; }
    }
}

modded class ItemBase
{
    override void EEOnCECreate()
    {
        super.EEOnCECreate();
        HCGroundCELoot.Enqueue(this);
    }
}
