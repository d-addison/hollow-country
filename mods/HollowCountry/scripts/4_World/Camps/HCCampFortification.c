// Native BaseBuildingBase.c:136/264/348/811 exposes native part replication,
// physics/navmesh and save state. No OnStore overrides, free kits or cargo.
// FullyBuild is deliberately avoided: it requires a notnull player and creates
// a recoverable kit. Only native wooden parts are admitted here.
modded class BaseBuildingBase
{
    bool HCBuildCampFortification()
    {
        if (!GetGame().IsServer() || (!Fence.Cast(this) && !Watchtower.Cast(this))) { return false; }
        Construction construction = GetConstruction();
        if (!construction) { return false; }
        array<ConstructionPart> parts = construction.GetConstructionParts().GetValueArray();
        if (!parts || parts.Count() < 1 || parts.Count() > 128) { return false; }
        int built;
        foreach (ConstructionPart part : parts)
        {
            string partName = part.GetPartName();
            if (partName.Length() > 128) { return false; }
            if (part.IsGate() || partName.Contains("_metal_")) { continue; }
            if (part.IsBase()) { SetBaseState(true); }
            RegisterPartForSync(part.GetId());
            SetPartFromSyncData(part);
            built++;
        }
        SynchronizeBaseState();
        construction.UpdateVisuals();
        UpdateVisuals();
        UpdateNavmesh();
        SetSynchDirty();
        return built > 0 && HasBase();
    }
}

class HCCampFortification
{
    // Deferred, merged-per-object pathgraph rebuild after the final snap.
    static const int PATHGRAPH_DELAY_MS = 100;
    protected static int s_PathgraphMarked;
    protected static int s_PathgraphRegions;
    protected static int s_PathgraphSkipped;

    // Same CE-persistent flags as HCGroundObjectSpawner's enableCEPersistency
    // path; HCGroundSnap owns support correction. No lifetime refresh loop.
    // Native Game.c:1366 clearance box; EntityAI defaults own CE lifetime.
    // ECE_UPDATEPATHGRAPH is deliberately absent: it would rebuild the graph
    // at the pre-snap pose. The post-snap region goes through HCPathgraphRefresh.
    static BaseBuildingBase Place(string kind, vector at, vector angles)
    {
        if (!GetGame() || !GetGame().IsServer() || (kind != "Fence" && kind != "Watchtower")) { return null; }
        int flags = ECE_SETUP | ECE_CREATEPHYSICS | ECE_OBJECT_SPAWNER;
        BaseBuildingBase fort = BaseBuildingBase.Cast(GetGame().CreateObjectEx(kind, at, flags, RF_IGNORE));
        if (!fort) { return null; }
        fort.SetOrientation(angles);
        if (!HCGroundSnap.Snap(fort, 3, 0.01) || !fort.HCBuildCampFortification())
        {
            GetGame().ObjectDelete(fort);
            return null;
        }
        HCQueuePathgraph(fort);
        return fort;
    }

    // Final pose and built parts are known here; the bounds include every part.
    protected static void HCQueuePathgraph(BaseBuildingBase fort)
    {
        HCPathgraphRefresh region = new HCPathgraphRefresh;
        region.Include(fort);
        s_PathgraphMarked += region.Marked;
        s_PathgraphSkipped += region.SkippedNoGeom;
        if (!region.HasBounds) { return; }
        if (!HCPathgraphRefresh.Hold(region))
        {
            // Pending cap reached: update at once rather than drop the region.
            HCTimedPathgraph(region);
            return;
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCCampFortification.HCTimedPathgraph, PATHGRAPH_DELAY_MS, false, region);
    }

    static void HCTimedPathgraph(HCPathgraphRefresh region)
    {
        if (!GetGame() || !region) { return; }
        region.Update();
        HCPathgraphRefresh.Release(region);
        s_PathgraphRegions++;
        HCModuleReadiness.HCUse("Camps", "pathgraph_refresh");
    }

    static void HCPathgraphSummary()
    {
        if (s_PathgraphMarked + s_PathgraphSkipped == 0) { return; }
        Print("" + "[HC Pathgraph] domain=camp_fortification marked=" + s_PathgraphMarked.ToString() + " affected=" + s_PathgraphRegions.ToString() + " skipped_no_geom=" + s_PathgraphSkipped.ToString());
    }
}

// Bounded periodic receipt next to the other [HC Pathgraph] domains. The use
// counter is lazy: it exists only once an AI fortification was actually placed.
modded class HCModuleReadiness
{
    override static void HCSummary()
    {
        super.HCSummary();
        HCCampFortification.HCPathgraphSummary();
    }
}
