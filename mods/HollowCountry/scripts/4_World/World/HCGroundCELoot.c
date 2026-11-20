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
    protected static bool s_FirstEnqueueLogged;
    protected static int s_Count;
    protected static int s_CECalls;
    protected static int s_Rejected;
    protected static int s_Parented;
    protected static int s_Deleting;
    protected static int s_Enqueued;
    protected static int s_Processed;
    protected static int s_Ineligible;
    protected static int s_Peak;

    static bool Eligible(ItemBase item)
    {
        return item && !item.IsPendingDeletion() && !item.GetHierarchyParent() && !item.IsTransport() && !item.IsBuilding();
    }

    // A restored economy can create no fresh loot. Report even then, without
    // admitting restored/script-created objects or scanning the world/backlog.
    static void StartReporting()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (!s_Reporting)
        {
            s_Reporting = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCGroundCELoot.Summary, 60000, false);
        }
    }

    static void ObserveCECreate()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        s_CECalls++;
        StartReporting();
    }

    static void RecordRejection(ItemBase item)
    {
        s_Rejected++;
        if (!item) { return; }
        if (item.GetHierarchyParent()) { s_Parented++; }
        if (item.IsPendingDeletion()) { s_Deleting++; }
    }

    static void Enqueue(ItemBase item)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (!Eligible(item)) { RecordRejection(item); return; }
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
        if (!s_FirstEnqueueLogged)
        {
            s_FirstEnqueueLogged = true;
            Print("[HC Ground] source=ce_queue first_enqueue type=" + item.GetType() + " runtime=PENDING");
        }
        StartReporting();
        if (!s_Scheduled)
        {
            s_Scheduled = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCGroundCELoot.Drain, 50, false);
        }
    }

    static void Drain()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
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
        if (pending) { GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCGroundCELoot.Drain, 50, false); }
        else { s_Scheduled = false; }
    }

    static void Summary()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        // processed counts dequeued entries, including deleted/reparented items.
        // enqueued = processed + pending; overflow is zero (no capacity drops).
        string line = "[HC Ground] source=ce_queue ce_calls=" + s_CECalls.ToString();
        line += " rejected=" + s_Rejected.ToString();
        line += " parented=" + s_Parented.ToString() + " deleting=" + s_Deleting.ToString();
        line += " overflow=0 enqueued=" + s_Enqueued.ToString();
        line += " processed=" + s_Processed.ToString() + " pending=" + s_Count.ToString();
        line += " peak=" + s_Peak.ToString() + " ineligible=" + s_Ineligible.ToString();
        Print("" + line);
        s_Stats.Summary("ce");
        HCGroundSnap.Placed.Summary("hc_placements");
        // Constant work once per minute, including when CE only restores storage.
        // A zero ce_calls receipt distinguishes no observed callback from rejection.
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCGroundCELoot.Summary, 60000, false);
    }
}

modded class ItemBase
{
    // Constructors cannot lose a super chain to a subclass callback override.
    // This starts diagnostics only: admission remains strictly CE/Debug creation.
    void ItemBase()
    {
        HCGroundCELoot.StartReporting();
    }

    // Native EntityAI.c:1413 distinguishes new CE/Debug creation from DB load
    // (AfterStoreLoad). Native ItemBase.c:4111 is the root loot implementation.
    // Vanilla food/firework overrides omitting super remain outside this hook.
    override void EEOnCECreate()
    {
        HCGroundCELoot.ObserveCECreate();
        super.EEOnCECreate();
        HCGroundCELoot.Enqueue(this);
    }
}
