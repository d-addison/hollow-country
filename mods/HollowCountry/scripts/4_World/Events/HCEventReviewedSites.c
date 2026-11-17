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
    static void Merge(HCEventSettings settings)
    {
        if (!settings || !settings.Sites) { return; }
        array<ref HCEventSite> curated = Curated();
        foreach (HCEventSite candidate : curated)
        {
            bool present = false;
            foreach (HCEventSite existing : settings.Sites)
            {
                if (existing && existing.Id == candidate.Id) { present = true; }
            }
            if (!present && settings.Sites.Count() < 8)
            {
                settings.Sites.Insert(candidate);
            }
        }
    }
}
