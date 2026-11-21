// One post-transform 3D region per committed layout/template. Geometry and
// engine calls live in 3_Game; readiness and bounded receipts stay in 4_World.
class HCInteriorPathgraph
{
    protected static int s_Marked;
    protected static int s_Regions;
    protected static int s_Skipped;

    static HCPathgraphRefresh Bounds(array<Object> placed)
    {
        HCPathgraphRefresh region = new HCPathgraphRefresh;
        foreach (Object object : placed) { region.Include(object); }
        return region;
    }

    static int Schedule(array<Object> placed)
    {
        if (!placed) { return 0; }
        HCPathgraphRefresh region = Bounds(placed);
        return Queue(region);
    }

    static int Queue(HCPathgraphRefresh region)
    {
        if (!region || !GetGame()) { return 0; }
        if (!GetGame().IsServer()) { return 0; }
        s_Marked += region.Marked;
        s_Skipped += region.SkippedNoGeom;
        if (!region.HasBounds) { return 0; }
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
        Print("" + "[HC Pathgraph] domain=interiors marked=" + s_Marked.ToString() + " regions=" + s_Regions.ToString() + " skipped_no_geom=" + s_Skipped.ToString());
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
