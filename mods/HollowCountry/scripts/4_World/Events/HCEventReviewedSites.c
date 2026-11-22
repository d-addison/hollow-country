// Native: 1_Core/proto/EnMath3D.c:18 Vector; EnScript.c:407 array.Insert.
// Bounded DATA REVIEW, 2026-11-17, of three stock ChernarusPlus static-event
// placements (dayzOffline.chernarusplus/cfgeventspawns.xml, SHA-256 below).
// Each site is the stock event origin plus a fixed (6.0, 10.4) x/z offset that
// clears every solid child of that event group by at least 12 m. Clearances from
// map groups and player spawns are recorded in docs/events/sites.json.
// Surveyed stays false: no field survey, walkability or slope check exists. The
// sites exist only when HCEventSitesGate admits them and are merged in memory,
// never written to settings.json. No spawning happens here.
class HCEventReviewedSites
{
    static HCEventSite Build(string siteId, string eventGroup, float x, float y, float z)
    {
        HCEventSite site = new HCEventSite;
        site.Id = siteId;
        site.WorldName = "chernarusplus";
        site.Reviewed = true;
        site.Surveyed = false;
        site.Position = Vector(x, y, z);
        site.Destination = Vector(x, y, z);
        site.ItemClass = "SmallProtectorCase";
        site.RewardCache = true;
        site.Provenance = "stock-cfgeventspawns-source-review:" + eventGroup;
        site.SourceSha256 = "7474b95f7a9349eb98ee19b9a44ba8e41c8dfe767104ea9d571654aba4aaad6c";
        return site;
    }
    static array<ref HCEventSite> Curated()
    {
        array<ref HCEventSite> sites = new array<ref HCEventSite>();
        sites.Insert(Build("kamenka-supply-cache", "Supply_Kamenka", 2512.352, 6.736, 2054.215));
        sites.Insert(Build("staroye-traffic-cache", "Traffic_Staroye", 10676.524, 125.785, 4579.396));
        sites.Insert(Build("kumyrna-ambush-cache", "Ambush_Kumyrna", 8393.078, 292.062, 5998.555));
        return sites;
    }
    // Authored stock for the single fill of each CE-created (empty) scene cache case: 3-5 vanilla
    // survival or field items per site, one fill per case identity (HCEventCacheFill). Null for a
    // site without a row: that case is never filled and the refusal is logged with a reason.
    static HCEventRewardPlan StockPlan(string siteId)
    {
        HCEventRewardPlan plan = new HCEventRewardPlan;
        plan.SiteId = siteId;
        if (siteId == "kamenka-supply-cache")
        {
            plan.Items.Insert("BandageDressing");
            plan.Items.Insert("TunaCan");
            plan.Items.Insert("SodaCan_Cola");
            plan.Items.Insert("Matchbox");
            return plan;
        }
        if (siteId == "staroye-traffic-cache")
        {
            plan.Items.Insert("MetalWire");
            plan.Items.Insert("Battery9V");
            plan.Items.Insert("Chemlight_Green");
            plan.Items.Insert("Rag");
            return plan;
        }
        if (siteId == "kumyrna-ambush-cache")
        {
            plan.Items.Insert("BandageDressing");
            plan.Items.Insert("Chemlight_Green");
            plan.Items.Insert("TunaCan");
            return plan;
        }
        return null;
    }
    // V2 scene variety reuses INVESTIGATION and the exact reviewed anchors.
    // This definition grants no cache, item, AI body or reward capability.
    static HCEventMission SceneMission(HCEventSite site, string missionId, int lifetime)
    {
        if (!site || !site.Reviewed) { return null; }
        HCEventMission mission = new HCEventMission;
        mission.Id = missionId;
        mission.SiteId = site.Id;
        mission.WorldName = site.WorldName;
        mission.Reviewed = true;
        mission.Family = HCEventFamily.INVESTIGATION;
        mission.Source = site.Position;
        mission.Destination = site.Position;
        mission.Radius = 25;
        mission.DwellSeconds = 20;
        mission.LifetimeSeconds = lifetime;
        return mission;
    }
    static void Merge(HCEventSettings settings)
    {
        if (!settings || !settings.Sites) { return; }
        array<ref HCEventSite> curated = Curated();
        // Native EnScript.c:902/917 map.Set/Contains; preserve curated insertion order.
        map<string, bool> present = new map<string, bool>;
        foreach (HCEventSite existing : settings.Sites)
        {
            if (existing) { present.Set(existing.Id, true); }
        }
        foreach (HCEventSite candidate : curated)
        {
            if (!present.Contains(candidate.Id) && settings.Sites.Count() < 8)
            {
                settings.Sites.Insert(candidate);
                present.Insert(candidate.Id, true);
            }
        }
    }
}
