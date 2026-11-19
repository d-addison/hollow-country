// HC-59 / issue 200: legacy barns plus authored regional exterior scenes.
// Class bounds and stock identity are source inputs; native access is PENDING.
// Full roof + walk-around envelopes stay clear; no interior path is invented.
// Native 3_Game/tools/JsonFileLoader.c:69 LoadData; HCWorldStore.Read/HCJsonFields reused.
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
    ref HCShelterRegionalScene Scene;
    bool Attempted;
    string Name;
    vector Position;
    string History;
    bool Placed = false;
    // Borrowed server scene handle, cleared when the scene is removed.
    Object PlacementAnchor;
    string LeadSlot = "";
}

// HC-59 provenance record. Regional Count/Get entries are loaded separately
// from their exterior scene data; they never use the barn-specific yard.
// Native access, rain cover and two-client presentation remain unobserved.
class HCShelterSurvey
{
    string Id;
    string Name;
    string BuildingClass;
    vector Position;
    string LocalityId;
    string Region;
    string RouteClass;
    string Refusal;
}

class HCShelterCatalog
{
    static const string BUILDING_CLASS = "Land_Barn_Wood2";
    protected static bool s_RegionalLoaded;
    protected static string s_RegionalFault;
    protected static ref HCShelterRegionalConfig s_Regional;
    protected static ref array<ref HCShelterEntry> s_Entries = new array<ref HCShelterEntry>;
    protected static ref array<ref HCShelterSurvey> s_Candidates = new array<ref HCShelterSurvey>;

    protected static void HCCandidate(string id, string name, string buildingClass, vector position, string locality, string region, string routeClass, string refusal)
    {
        HCShelterSurvey row = new HCShelterSurvey;
        row.Id = id;
        row.Name = name;
        row.BuildingClass = buildingClass;
        row.Position = position;
        row.LocalityId = locality;
        row.Region = region;
        row.RouteClass = routeClass;
        row.Refusal = refusal;
        s_Candidates.Insert(row);
    }

    protected static void HCEnsureCandidates()
    {
        if (s_Candidates.Count() != 0) return;
        // Exact stock-map anchors. Exterior slots now live in the regional
        // scene file; generic interior path measurements remain untested.
        HCCandidate("nw-feed-roof", "Northwest woodland roof", "Land_Misc_FeedShack", "1987.282837 289.981445 12965.870117", "sinystok", "NW", "forest-trail", "runtime_access_clearance_pending");
        HCCandidate("nc-feed-roof", "Northern woodland roof", "Land_Misc_FeedShack", "7428.081543 131.084442 12732.728516", "kamensk", "NC", "forest-trail", "runtime_access_clearance_pending");
        HCCandidate("ne-feed-roof", "Northeast woodland roof", "Land_Misc_FeedShack", "12818.673828 126.932716 13117.182617", "novodmitrovsk", "NE", "remote-road", "runtime_access_clearance_pending");
        HCCandidate("sc-bus-roof", "Central coast road roof", "Land_BusStop_City", "6826.631836 50.728073 3549.387207", "prigorodki", "SC", "coastal-road", "runtime_access_clearance_pending");
        HCCandidate("se-bus-roof", "Southeast coast road roof", "Land_BusStop_City", "10897.795898 7.027513 2815.425293", "elektrozavodsk", "SE", "coastal-road", "runtime_access_clearance_pending");
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
        HCLoadRegional();
        return s_Entries.Count();
    }

    static HCShelterEntry Get(int index)
    {
        Ensure();
        HCLoadRegional();
        if (index < 0 || index >= s_Entries.Count()) return null;
        return s_Entries[index];
    }

    static HCShelterRegionalConfig HCRegionalConfig()
    {
        Ensure();
        HCLoadRegional();
        return s_Regional;
    }

    static string HCRegionalFault() { return s_RegionalFault; }

    // Once per process; bounded five-row source file, never persistent scene state.
    protected static void HCLoadRegional()
    {
        if (s_RegionalLoaded) { return; }
        s_RegionalLoaded = true;
        string content = HCWorldStore.Read("$mission:hollow-country/travel/auditshelter_scenes.json");
        string error;
        HCShelterRegionalConfig loaded;
        s_RegionalFault = "regional_scene_data_missing_or_invalid";
        if (!HCJsonFields.Has(content, "Enabled") || !HCJsonFields.Has(content, "Scenes")) { return; }
        if (!HCJsonFields.Every(content, "Enabled", 3)) { return; }
        if (!JsonFileLoader<HCShelterRegionalConfig>.LoadData(content, loaded, error) || !HCRegionalValid(loaded)) { return; }
        s_Regional = loaded;
        s_RegionalFault = "";
        if (!loaded.Enabled) { return; }
        array<ref HCShelterRegionalScene> scenes = loaded.Scenes;
        foreach (HCShelterRegionalScene scene : scenes)
        {
            if (!scene.Enabled) { continue; }
            HCShelterEntry regional = new HCShelterEntry;
            regional.Name = scene.Name;
            regional.Position = HCInteriorTemplates.AsVector(scene.Position);
            regional.History = scene.History;
            regional.Scene = scene;
            s_Entries.Insert(regional);
        }
    }

    static bool HCRegionalBox(array<float> minimum, array<float> maximum)
    {
        return HCInteriorTemplates.BoxValid(minimum, maximum);
    }

    static bool HCRegionalValid(HCShelterRegionalConfig config)
    {
        if (!config || config.SchemaVersion != 1 || !config.Scenes || config.Scenes.Count() != CandidateCount()) { return false; }
        if (!HCObserverTransitionGate.Finite(config.ObserverDistance) || config.ObserverDistance < 500 || config.ObserverDistance > 10000) { return false; }
        if (config.WorkUnits < 24 || config.WorkUnits > 256) { return false; }
        if (!HCObserverTransitionGate.Finite(config.BoundsToleranceSquared) || config.BoundsToleranceSquared <= 0 || config.BoundsToleranceSquared > 0.04) { return false; }
        array<ref HCShelterRegionalScene> scenes = config.Scenes;
        int sceneIndex = 0;
        foreach (HCShelterRegionalScene scene : scenes)
        {
            HCShelterSurvey candidate = GetCandidate(sceneIndex);
            sceneIndex = sceneIndex + 1;
            if (!scene || scene.Id != candidate.Id || scene.BuildingClass != candidate.BuildingClass || scene.Name != candidate.Name) { return false; }
            if (!scene.Position || scene.Position.Count() != 3 || HCInteriorTemplates.AsVector(scene.Position) != candidate.Position) { return false; }
            if (!HCRegionalBox(scene.ClipMin, scene.ClipMax) || !HCRegionalBox(scene.AccessMin, scene.AccessMax) || !HCRegionalBox(scene.YardMin, scene.YardMax)) { return false; }
            if (scene.AccessMin[0] > scene.ClipMin[0] - 2 || scene.AccessMax[0] < scene.ClipMax[0] + 2) { return false; }
            if (scene.AccessMin[2] > scene.ClipMin[2] - 2 || scene.AccessMax[2] < scene.ClipMax[2] + 2) { return false; }
            if (scene.AccessMin[1] > -20 || scene.AccessMax[1] < 20) { return false; }
            if (!scene.Slots || scene.Slots.Count() != 3 || scene.History.Length() == 0) { return false; }
            array<ref array<float>> slots = scene.Slots;
            foreach (array<float> slot : slots)
            {
                if (!slot || slot.Count() != 3) { return false; }
                vector point = HCInteriorTemplates.AsVector(slot);
                if (!HCInteriorRules.SaneVector(point, 30)) { return false; }
                if (point[0] + 1.5 >= scene.AccessMin[0]) { return false; }
                if (point[0] - 1.5 <= scene.YardMin[0] || point[0] + 1.5 >= scene.YardMax[0]) { return false; }
                if (point[2] - 1.5 <= scene.YardMin[2] || point[2] + 1.5 >= scene.YardMax[2]) { return false; }
            }
        }
        return true;
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

// Mission-owned policy fields are explicit: missing numeric/array values fail
// validation rather than inheriting defaults after JsonFileLoader zero-fill.
class HCShelterRegionalScene
{
    string Id;
    string Name;
    string BuildingClass;
    string History;
    bool Enabled;
    ref array<float> Position;
    ref array<float> ClipMin;
    ref array<float> ClipMax;
    ref array<float> AccessMin;
    ref array<float> AccessMax;
    ref array<float> YardMin;
    ref array<float> YardMax;
    ref array<ref array<float>> Slots;
}
class HCShelterRegionalConfig
{
    int SchemaVersion;
    bool Enabled;
    float ObserverDistance;
    int WorkUnits;
    float BoundsToleranceSquared;
    ref array<ref HCShelterRegionalScene> Scenes;
}
