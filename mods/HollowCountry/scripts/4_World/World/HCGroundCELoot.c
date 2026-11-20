// Fixed-size allocation per rollover, never a copy/scan of the pending backlog.
// Native EnScript.c: array.Resize/Get/Set; ItemBase references remain non-owning.
class HCGroundCELootChunk
{
    static const int CAPACITY = 256;
    ref array<ItemBase> Items = new array<ItemBase>;
    ref HCGroundCELootChunk Next;
    int Read;
    int Written;

    void HCGroundCELootChunk() { Items.Resize(CAPACITY); }
}

// CE owns creation and inventory. This queue only corrects root world items.
// Retain every admission until examined: no capacity rejection or world rescan.
// Memory follows pending work (plus <512 consumed/unused slots), not lifetime admissions;
// consumed chunks are released without shifting/copying the remaining entries.
class HCGroundCELoot
{
    protected static ref HCGroundCELootChunk s_Head;
    protected static ref HCGroundCELootChunk s_Tail;
    protected static ref HCGroundSnapStats s_Stats = new HCGroundSnapStats;
    protected static ref HCWorkBudget s_Budget = new HCWorkBudget;
    protected static bool s_Scheduled;
    protected static bool s_Reporting;
    protected static int s_Count;
    protected static int s_Enqueued;
    protected static int s_Processed;
    protected static int s_Ineligible;
    protected static int s_Peak;

    static bool Eligible(ItemBase item)
    {
        return item && !item.IsPendingDeletion() && !item.GetHierarchyParent() && !item.IsTransport() && !item.IsBuilding();
    }

    static void Enqueue(ItemBase item)
    {
        if (!GetGame() || !GetGame().IsServer() || !Eligible(item)) { return; }
        if (!s_Tail)
        {
            s_Tail = new HCGroundCELootChunk;
            s_Head = s_Tail;
        }
        else if (s_Tail.Written == HCGroundCELootChunk.CAPACITY)
        {
            s_Tail.Next = new HCGroundCELootChunk;
            s_Tail = s_Tail.Next;
        }
        s_Tail.Items[s_Tail.Written] = item;
        s_Tail.Written++;
        s_Count++;
        s_Enqueued++;
        if (s_Count > s_Peak) { s_Peak = s_Count; }
        if (!s_Reporting)
        {
            s_Reporting = true;
            // Keep the minute receipt after drain completion so pending=0 is visible.
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Summary, 60000, true);
        }
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
            ref HCGroundCELootChunk chunk = s_Head;
            ItemBase item = chunk.Items[chunk.Read];
            chunk.Items[chunk.Read] = null;
            chunk.Read++;
            s_Count--;
            s_Processed++;
            if (chunk.Read == chunk.Written)
            {
                s_Head = chunk.Next;
                chunk.Next = null;
                if (!s_Head) { s_Tail = null; }
            }
            if (Eligible(item)) { HCGroundSnap.Snap(item, 2.5, 0.08, s_Stats); }
            else { s_Ineligible++; }
        }
        bool pending = s_Count > 0;
        if (pending) { GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Drain, 50, false); }
        else { s_Scheduled = false; }
    }

    static void Summary()
    {
        s_Stats.Summary("ce");
        // processed counts dequeued entries, including deleted/reparented items.
        // enqueued = processed + pending; overflow is zero (no capacity drops).
        string line = "[HC Ground] source=ce_queue overflow=0 enqueued=" + s_Enqueued.ToString();
        line += " processed=" + s_Processed.ToString() + " pending=" + s_Count.ToString();
        line += " peak=" + s_Peak.ToString() + " ineligible=" + s_Ineligible.ToString();
        Print("" + line);
        HCGroundSnap.Placed.Summary("hc_placements");
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
