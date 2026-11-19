// HC-59: active legacy barns plus a separate bounded regional survey queue.
// No new roof is admitted from class ancestry, a stock point or a route label.
// CandidateCount/GetCandidate are lead integration inputs, never placed scenes.
// Native stock roofs need no new stock, lights, inventory, props or tick loop.
// LC-T206 / LC-TRV-06. Six shared, unowned rural barns; no loot or lead grants.
// Positions verified against stock ChernarusPlus mapgrouppos.xml, read-only:
// /mnt/d/HollowCountryLocal/interior-sampler-120/mpmissions/dayzOffline.chernarusplus/mapgrouppos.xml
// SHA-256: 3eeaad9786a73c339f61f6e6ad203f0732e36b88f27333978cc8b4beece9cec4
// Class at every position: Land_Barn_Wood2. Native placement/pathing remains
// pending EXP-T5 / EXP-S3; source review is not an engine acceptance verdict.
// The windowless west model-side yard is used, away from both end doors and
// the east side door/stairs. No interior furnishing pack is needed or modified.
// Route descriptions are authored design context, not surveyed trail evidence.
// Installed native snapshot 1.30.164289: 1_Core/proto/EnString.c:199 Length,
// 1_Core/proto/EnScript.c:380/407 Count/Insert; no world mutation in this catalog.
class HCShelterEntry
{
    string Name;
    vector Position;
    string History;
    bool Placed = false;
    // Borrowed server scene handle, cleared when the scene is removed.
    Object PlacementAnchor;
    string LeadSlot = "";
}

// HC-59 source-only survey record. A candidate cannot enter Count()/Get(),
// which the existing barn-specific materializer consumes. Native access, rain
// cover, geometry, doors and two-client presentation remain unobserved.
class HCShelterSurvey
{
    string Id;
    string Name;
    string BuildingClass;
    vector Position;
    string LocalityId;
    string Region;
    string RouteClass;
    string Refusal = "hc59_regional_shelter_access_unobserved";
}

class HCShelterCatalog
{
    static const string BUILDING_CLASS = "Land_Barn_Wood2";
    protected static ref array<ref HCShelterEntry> s_Entries = new array<ref HCShelterEntry>;
    protected static ref array<ref HCShelterSurvey> s_Candidates = new array<ref HCShelterSurvey>;

    protected static void HCCandidate(string id, string name, string buildingClass, vector position, string locality, string region, string routeClass)
    {
        HCShelterSurvey row = new HCShelterSurvey;
        row.Id = id;
        row.Name = name;
        row.BuildingClass = buildingClass;
        row.Position = position;
        row.LocalityId = locality;
        row.Region = region;
        row.RouteClass = routeClass;
        s_Candidates.Insert(row);
    }

    protected static void HCEnsureCandidates()
    {
        if (s_Candidates.Count() != 0) return;
        // Exact stock-map anchors, not measured access or interior locations.
        // Residential config exposes these models as HouseNoDestruct scope=1;
        // this is insufficient to assert enterability, roof cover or road access.
        HCCandidate("nw-feed-roof", "Northwest woodland roof", "Land_Misc_FeedShack", "1987.282837 289.981445 12965.870117", "sinystok", "NW", "forest-trail");
        HCCandidate("nc-feed-roof", "Northern woodland roof", "Land_Misc_FeedShack", "7428.081543 131.084442 12732.728516", "kamensk", "NC", "forest-trail");
        HCCandidate("ne-feed-roof", "Northeast woodland roof", "Land_Misc_FeedShack", "12818.673828 126.932716 13117.182617", "novodmitrovsk", "NE", "remote-road");
        HCCandidate("sc-bus-roof", "Central coast road roof", "Land_BusStop_City", "6826.631836 50.728073 3549.387207", "prigorodki", "SC", "coastal-road");
        HCCandidate("se-bus-roof", "Southeast coast road roof", "Land_BusStop_City", "10897.795898 7.027513 2815.425293", "elektrozavodsk", "SE", "coastal-road");
    }

    static int CandidateCount()
    {
        HCEnsureCandidates();
        return s_Candidates.Count();
    }

    static HCShelterSurvey GetCandidate(int index)
    {
        HCEnsureCandidates();
        if (index < 0 || index >= s_Candidates.Count()) return null;
        return s_Candidates[index];
    }

    protected static void Add(string shelterName, vector position, string history)
    {
        HCShelterEntry entry = new HCShelterEntry;
        entry.Name = shelterName;
        entry.Position = position;
        entry.History = history;
        s_Entries.Insert(entry);
    }

    protected static void Ensure()
    {
        if (s_Entries.Count() != 0) return;
        // Zelenogorsk to Drozhino: farm tracks below the western woods.
        Add("Drozhino Hay Refuge", "2585.119873 202.433472 5360.409668", "A family waited out the rain here. Their empty packing box and a chair remain beside the cold cooking grate.");
        // Bor to Komarovo: the inland farm approach above the coast.
        Add("Bor South Rest", "3100.955811 249.415558 4238.387207", "A coastal traveller slept under this roof after abandoning the road. The grate outside was their last dry stopping place.");
        // Zelenogorsk to Sosnovka: northbound farm and woodland edge.
        Add("Sosnovka Track Barn", "3560.896484 337.081543 7004.783203", "A hunter used the barn as a rain hide. Someone later dragged a chair outside and left an empty provisions box.");
        // Pogorevka to Pulkovo: open farmland between wooded ridges.
        Add("Pulkovo Ridge Rest", "5271.449219 308.912933 5515.677246", "Two walkers shared this roof while moving between the farms. Only one chair was left when they continued east.");
        // Guglovo to Dolina: the rural ridge approach west of Dolina.
        Add("Dolina Upper Refuge", "9710.349609 216.305511 6487.099121", "A family avoided the valley road and hid here for a night. They cooked outside so the hay would stay dry and safe.");
        // Gorka to Polana: farm shelter on the southern approach to Polana.
        Add("Polana South Wayhouse", "10677.808594 214.414337 7923.848633", "A farm worker kept a small stopping place for people coming through the woods. The empty box suggests the last supplies went with them.");
    }

    static int Count()
    {
        Ensure();
        return s_Entries.Count();
    }

    static HCShelterEntry Get(int index)
    {
        Ensure();
        if (index < 0 || index >= s_Entries.Count()) return null;
        return s_Entries[index];
    }

    // Runtime-only slot for LC-T306. Leads owns its own durable ledger; this
    // catalog never saves lead state or creates notes, items, or map pins.
    static bool SetLeadSlot(int index, string text)
    {
        HCShelterEntry entry = Get(index);
        if (!entry || text.Length() > 512) return false;
        entry.LeadSlot = text;
        return true;
    }
}
