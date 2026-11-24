// Fixed-size allocation per rollover, never a copy/scan of the pending backlog.
// Native EnScript.c: array.Resize/Get/Set; ItemBase references remain non-owning.
class HCGroundCELootChunk
{
    static const int CAPACITY = 256;
    ref array<ItemBase> Items = new array<ItemBase>;
    ref array<int> Kinds = new array<int>;
    ref HCGroundCELootChunk Next;
    int Read;
    int Written;

    void HCGroundCELootChunk() { Items.Resize(CAPACITY); Kinds.Resize(CAPACITY); }
}

// CE owns creation and inventory. This queue only corrects root world items.
// Retain every admission until examined: no capacity rejection or world rescan.
// Memory follows pending work (plus <512 consumed/unused slots), not lifetime admissions;
// consumed chunks are released without shifting/copying the remaining entries.
class HCGroundCELoot
{
    static const int KIND_CE = 0;
    static const int KIND_RESTORED = 1;
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
    static const int HELD_CAP = 1024;
    static const float HELD_TIMEOUT_S = 900;
    protected static ref array<ItemBase> s_Held = new array<ItemBase>;
    protected static ref array<float> s_HeldAt = new array<float>;
    protected static int s_SiteOverflow;
    protected static int s_SiteTimeout;
    protected static bool s_HeldScheduled;
    protected static int s_SiteDropped;
    protected static int s_SiteHeldTotal;
    protected static int s_Shifted;
    protected static int s_Settled;
    protected static int s_Retried;
    protected static int s_RetryFailed;
    protected static int s_Restored;
    protected static int s_RestoredSettled;
    protected static int s_RestoredWaiting;
    protected static ref HCGroundSnapStats s_RetryStats = new HCGroundSnapStats;
    protected static string s_LastOursReceipt;
    protected static float s_LastOursReceiptAt;
    protected static string s_LastReceipt;
    protected static float s_LastReceiptAt;
    protected static string s_LastCEStats;
    protected static float s_LastCEStatsAt;
    protected static string s_LastPlacedStats;
    protected static float s_LastPlacedStatsAt;

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

    // Items restored from storage are only re-examined inside a placed HC footprint, and never
    // player-built structures or buried stashes.
    static void EnqueueRestored(ItemBase item)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (!Eligible(item) || item.IsInherited(BaseBuildingBase) || item.IsInherited(TentBase) || item.IsInherited(UndergroundStash)) { return; }
        float shift;
        if (!HCGroundPlaced.Find(item.GetPosition(), shift)) { return; }
        Enqueue(item, KIND_RESTORED);
    }

    static void Enqueue(ItemBase item, int kind = 0)
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
        s_Tail.Kinds[s_Tail.Written] = kind;
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

    // CE creates loot at the authored group height; inside one of our placed footprints it moves with
    // its building (the placer's shift), then rests on the surface below. An item still hanging after
    // the 2.5 m snap gets one long drop onto the first surface below (floor or terrain). Restored items
    // are only dropped onto a surface, never lifted or shifted: storage already holds their last position.
    static void Correct(ItemBase item, int kind)
    {
        vector pos = item.GetPosition();
        float shift;
        bool ours = HCGroundPlaced.Find(pos, shift);
        if (kind == KIND_RESTORED)
        {
            s_Restored++;
            if (!ours) { return; }
            // A restored item may rest on a raised floor or shelf of a composed site. Its drop-only ray would
            // pass through geometry that is not spawned yet, so it is settled only once the guard has
            // admitted the owning site (every piece stands). Items of an undecided, refused or retired box
            // keep their stored position; the orphan sweep settles bare items of retired boxes.
            if (HCSiteGuard.HCLootVerdict(item) != HCSiteGuard.LOOT_KEEP)
            {
                s_RestoredWaiting++;
                return;
            }
            if (HCGroundSnap.Settle(item, 12, 0.08)) { s_RestoredSettled++; }
            return;
        }
        // Transient marker: this CE item has reached its correction pass, even if no support is found.
        item.m_HCGroundCEHandled = true;
        if (ours && shift != 0)
        {
            pos[1] = pos[1] + shift;
            item.SetPosition(pos);
            s_Shifted++;
        }
        if (HCGroundSnap.Snap(item, 2.5, 0.08, s_Stats)) { return; }
        if (!ours) { return; }
        s_Retried++;
        if (HCGroundSnap.Snap(item, 12, 0.08, s_RetryStats)) { s_Settled++; }
        else { s_RetryFailed++; }
    }

    // W6 site guard: fresh CE loot inside a loot box of a refused or retired site is removed (it never held a
    // player item: Eligible() excludes anything with a parent), and loot inside a box of a site that is still
    // undecided waits in a bounded held queue. Everything else is corrected as before.
    // Pre-guard rule: loot enqueued before the guard has built its box grid (HCSiteGuard.HCLootVerdict answers KEEP
    // until then) is corrected as ordinary loot. Holding it would stall the whole CE boot burst behind the guard;
    // retired boxes are covered by the orphan sweep instead, and loot left in a refused box stays ordinary loot.
    // Held items leave the queue three ways: a decision (keep or drop), the hold timeout, or the cap. A timed-out
    // or over-cap item is only settled onto the surface below (the orphan-sweep action: drop-only, no shift into a
    // footprint, never deleted), so a site that never decides cannot trap loot and the queue cannot grow.
    static void SiteRoute(ItemBase item)
    {
        int verdict = HCSiteGuard.HCLootVerdict(item);
        if (verdict == HCSiteGuard.LOOT_DROP)
        {
            s_SiteDropped++;
            item.DeleteSafe();
            return;
        }
        if (verdict == HCSiteGuard.LOOT_HOLD)
        {
            if (s_Held.Count() < HELD_CAP)
            {
                s_Held.Insert(item);
                s_HeldAt.Insert(GetGame().GetTickTime());
                s_SiteHeldTotal++;
                ScheduleHeld();
                return;
            }
            s_SiteOverflow++;
            HCGroundSnap.Settle(item, 12, 0.08);
            item.m_HCGroundCEHandled = true;
            return;
        }
        Correct(item, KIND_CE);
    }

    protected static void ScheduleHeld()
    {
        if (s_HeldScheduled || s_Held.Count() < 1) { return; }
        s_HeldScheduled = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCGroundCELoot.DrainHeld, 1000, false);
    }

    // At most four held items per second, front to back; an item whose site is still undecided rotates to the back
    // until its hold times out.
    static void DrainHeld()
    {
        s_HeldScheduled = false;
        if (!GetGame() || !GetGame().IsServer()) { return; }
        float now = GetGame().GetTickTime();
        int examine = Math.Min(4, s_Held.Count());
        for (int step = 0; step < examine; step++)
        {
            ItemBase held = s_Held[0];
            float heldAt = s_HeldAt[0];
            s_Held.RemoveOrdered(0);
            s_HeldAt.RemoveOrdered(0);
            if (!Eligible(held))
            {
                s_Ineligible++;
                continue;
            }
            int verdict = HCSiteGuard.HCLootVerdict(held);
            if (verdict == HCSiteGuard.LOOT_HOLD)
            {
                if (now - heldAt >= HELD_TIMEOUT_S)
                {
                    s_SiteTimeout++;
                    HCGroundSnap.Settle(held, 12, 0.08);
                    held.m_HCGroundCEHandled = true;
                }
                else
                {
                    s_Held.Insert(held);
                    s_HeldAt.Insert(heldAt);
                }
            }
            else if (verdict == HCSiteGuard.LOOT_DROP)
            {
                s_SiteDropped++;
                held.DeleteSafe();
            }
            else { Correct(held, KIND_CE); }
        }
        ScheduleHeld();
    }

    static void Drain()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        s_Budget.HCReset(4, HCPerfConfig.HCGet().SliceMs);
        while (s_Count > 0 && s_Budget.HCContinue())
        {
            ref HCGroundCELootChunk chunk = s_Head;
            ItemBase item = chunk.Items[chunk.Read];
            int kind = chunk.Kinds[chunk.Read];
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
            if (!Eligible(item)) { s_Ineligible++; continue; }
            if (kind == KIND_CE) { SiteRoute(item); }
            else { Correct(item, kind); }
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
        line += " site_dropped=" + s_SiteDropped.ToString() + " site_held=" + s_Held.Count().ToString();
        line += " site_overflow=" + s_SiteOverflow.ToString() + " site_timeout=" + s_SiteTimeout.ToString();
        // Each of the three lines has an independent change/heartbeat receipt.
        float receiptNow = GetGame().GetTickTime();
        if (line != s_LastReceipt || receiptNow < s_LastReceiptAt || receiptNow - s_LastReceiptAt >= 1800)
        {
            s_LastReceipt = line;
            s_LastReceiptAt = receiptNow;
            Print("" + line);
        }
        string ceStats = s_Stats.Snapped.ToString() + " " + s_Stats.AlreadyOk.ToString();
        ceStats += " " + s_Stats.NoSupport.ToString() + " " + s_Stats.NoHit.ToString() + " " + s_Stats.ContactAboveStart.ToString();
        ceStats += " " + s_Stats.ContactBelowFinish.ToString() + " " + s_Stats.CorrectionOutOfRange.ToString() + " " + s_Stats.ReprobeLifted.ToString();
        ceStats += " " + s_Stats.MaxCorrection.ToString();
        if (ceStats != s_LastCEStats || receiptNow < s_LastCEStatsAt || receiptNow - s_LastCEStatsAt >= 1800)
        {
            s_LastCEStats = ceStats;
            s_LastCEStatsAt = receiptNow;
            s_Stats.Summary("ce");
        }
        string placedStats = HCGroundSnap.Placed.Snapped.ToString() + " " + HCGroundSnap.Placed.AlreadyOk.ToString();
        placedStats += " " + HCGroundSnap.Placed.NoSupport.ToString() + " " + HCGroundSnap.Placed.NoHit.ToString() + " " + HCGroundSnap.Placed.ContactAboveStart.ToString();
        placedStats += " " + HCGroundSnap.Placed.ContactBelowFinish.ToString() + " " + HCGroundSnap.Placed.CorrectionOutOfRange.ToString() + " " + HCGroundSnap.Placed.ReprobeLifted.ToString();
        placedStats += " " + HCGroundSnap.Placed.MaxCorrection.ToString();
        if (placedStats != s_LastPlacedStats || receiptNow < s_LastPlacedStatsAt || receiptNow - s_LastPlacedStatsAt >= 1800)
        {
            s_LastPlacedStats = placedStats;
            s_LastPlacedStatsAt = receiptNow;
            HCGroundSnap.Placed.Summary("hc_placements");
        }
        string ours = " shifted=" + s_Shifted.ToString() + " retried=" + s_Retried.ToString() + " settled=" + s_Settled.ToString();
        ours += " retry_failed=" + s_RetryFailed.ToString() + " restored=" + s_Restored.ToString();
        ours += " restored_settled=" + s_RestoredSettled.ToString() + " restored_waiting=" + s_RestoredWaiting.ToString() + " footprints=" + HCGroundPlaced.Count().ToString();
        if (ours != s_LastOursReceipt || receiptNow < s_LastOursReceiptAt || receiptNow - s_LastOursReceiptAt >= 1800)
        {
            s_LastOursReceipt = ours;
            s_LastOursReceiptAt = receiptNow;
            Print("[HC Ground] source=ce_ours" + ours);
        }
        // Constant work once per minute, including when CE only restores storage;
        // unchanged receipts print at most once per 30 minutes.
        // A zero ce_calls receipt distinguishes no observed callback from rejection.
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCGroundCELoot.Summary, 60000, false);
    }
}

modded class ItemBase
{
    bool m_HCGroundCEHandled;
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

    // Storage restore (not CE creation): a persisted item inside one of our placed footprints is dropped onto
    // the surface below once, so loot stored in the air by an earlier placement self-repairs on upgrade.
    override void AfterStoreLoad()
    {
        super.AfterStoreLoad();
        // Tents and storage restored from storage tell the site guard the storage load is still running.
        if (m_HCBasesRegistered) { HCSiteBaseRegistry.Touch(); }
        HCGroundCELoot.EnqueueRestored(this);
    }
}
