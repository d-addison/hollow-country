// One post-transform 3D region per committed layout/template. Geometry and
// engine calls live in 3_Game; readiness and bounded receipts stay in 4_World.
class HCInteriorPathgraph
{
    protected static int s_Marked;
    protected static int s_Regions;
    protected static int s_Skipped;
    protected static int s_RemovedRegions;
    // Removal regions wait here (bounded by prop count) and drain one per CallLater under HCWorkBudget.
    static const int REMOVAL_CELL_METRES = 32;
    static const int REMOVAL_DRAIN_MS = 100;
    protected static ref array<ref HCPathgraphRefresh> s_RemovedPending = new array<ref HCPathgraphRefresh>;
    protected static ref HCWorkBudget s_RemovalBudget;
    protected static bool s_RemovalDrainQueued;

    static HCPathgraphRefresh Bounds(array<Object> placed)
    {
        HCPathgraphRefresh region = new HCPathgraphRefresh;
        foreach (Object object : placed) { region.Include(object); }
        return region;
    }

    // Interiors furniture: the prop's own config decides whether it cuts the navmesh.
    static HCPathgraphRefresh BoundsRespectConfig(array<Object> placed)
    {
        HCPathgraphRefresh region = new HCPathgraphRefresh;
        foreach (Object object : placed) { region.IncludeRespectConfig(object); }
        return region;
    }

    static int Schedule(array<Object> placed)
    {
        if (!placed) { return 0; }
        HCPathgraphRefresh region = BoundsRespectConfig(placed);
        return HCQueueRegion(region);
    }

    // Call before the props are deleted: the boxes are captured now and no object is held. Props are
    // grouped by 32 m cell so one far-apart set never becomes one map-sized rebuild region.
    // Returns the number of regions queued.
    static int QueueRemoval(array<Object> removed)
    {
        if (!removed || !GetGame()) { return 0; }
        if (!GetGame().IsServer()) { return 0; }
        map<int, ref HCPathgraphRefresh> cells = new map<int, ref HCPathgraphRefresh>;
        int queued = 0;
        foreach (Object prop : removed)
        {
            if (!prop) { continue; }
            vector position = prop.GetPosition();
            int cellX = Math.Floor(position[0] / REMOVAL_CELL_METRES);
            int cellZ = Math.Floor(position[2] / REMOVAL_CELL_METRES);
            int key = (cellX + 4096) * 100000 + (cellZ + 4096);
            HCPathgraphRefresh cell = cells.Get(key);
            if (!cell)
            {
                cell = new HCPathgraphRefresh;
                cells.Insert(key, cell);
            }
            cell.IncludeRemoved(prop);
        }
        for (int index = 0; index < cells.Count(); index++)
        {
            HCPathgraphRefresh pending = cells.GetElement(index);
            if (!pending || !pending.HasBounds) { continue; }
            s_RemovedPending.Insert(pending);
            queued++;
        }
        if (queued > 0 && !s_RemovalDrainQueued)
        {
            s_RemovalDrainQueued = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCDrainRemoval, REMOVAL_DRAIN_MS, false);
        }
        return queued;
    }

    // Drop every queued removal region and the pending drain call. Called at module start and when the
    // module stops with the core already stopped, so nothing rebuilds the pathgraph after the props are gone.
    static void HCCancelRemoval()
    {
        s_RemovedPending.Clear();
        s_RemovalDrainQueued = false;
        if (GetGame()) { GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCDrainRemoval); }
    }

    // One region per call, gated by HCWorkBudget; re-arms itself until the queue is empty.
    static void HCDrainRemoval()
    {
        s_RemovalDrainQueued = false;
        if (!GetGame()) { return; }
        // The drain runs only while the core is up; a stopped core discards what is left.
        if (!HCServer.Get().IsStarted()) { s_RemovedPending.Clear(); return; }
        if (!s_RemovalBudget) { s_RemovalBudget = new HCWorkBudget; }
        s_RemovalBudget.HCReset(1);
        while (s_RemovedPending.Count() > 0 && s_RemovalBudget.HCContinue())
        {
            ref HCPathgraphRefresh region = s_RemovedPending.Get(0);
            s_RemovedPending.RemoveOrdered(0);
            if (!region) { continue; }
            region.Update();
            s_RemovedRegions++;
            Applied();
        }
        if (s_RemovedPending.Count() > 0)
        {
            s_RemovalDrainQueued = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCDrainRemoval, REMOVAL_DRAIN_MS, false);
        }
    }

    static int HCQueueRegion(HCPathgraphRefresh region)
    {
        if (!region || !GetGame()) { return 0; }
        if (!GetGame().IsServer()) { return 0; }
        s_Marked += region.Marked;
        s_Skipped += region.SkippedNoGeom;
        if (!region.HasBounds) { return 0; }
        if (!HCPathgraphRefresh.Hold(region))
        {
            HCInteriorTemplatePlacement.HCTimedPathgraph(region);
            return 1;
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCInteriorTemplatePlacement.HCTimedPathgraph, 100, false, region);
        return 1;
    }

    static void Applied()
    {
        s_Regions++;
        HCModuleReadiness.HCUse("Interiors", "pathgraph_refresh");
    }

    static void Summary()
    {
        Print("" + "[HC Pathgraph] domain=interiors marked=" + s_Marked.ToString() + " affected=" + s_Regions.ToString() + " skipped_no_geom=" + s_Skipped.ToString() + " removed_regions=" + s_RemovedRegions.ToString());
    }
}

// Keep the feature inventory in the existing registration dispatch without
// changing the shared core file owned by another worker.
modded class HCModuleReadiness
{
    override static void HCRegisterModuleUses(string module)
    {
        super.HCRegisterModuleUses(module);
        if (module == "Interiors")
        {
            HCRegisterUse("Interiors", "pathgraph_refresh");
            HCRegisterUse("Interiors", "house_search_completed");
        }
        if (module == "Shelters") { HCRegisterUse("Shelters", "pathgraph_refresh"); }
        if (module == "ObjectSpawner") { HCRegisterUse("ObjectSpawner", "pathgraph_refresh"); }
    }

    override static void HCUseBegin()
    {
        super.HCUseBegin();
        // The synchronous boot batch has already returned to vanilla's single
        // marked-object flush. Report its first use from the World layer.
        HCRegisterModuleUses("ObjectSpawner");
        if (ObjectSpawnerHandler.HCPathgraphMarked > 0)
        {
            HCUse("ObjectSpawner", "pathgraph_refresh");
        }
    }

    override static void HCSummary()
    {
        super.HCSummary();
        HCInteriorPathgraph.Summary();
    }
}
