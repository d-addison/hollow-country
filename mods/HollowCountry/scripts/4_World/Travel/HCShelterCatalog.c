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
    int PlacementVariant;
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
    protected static string s_RegionalReason;
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
        // Authored stock identities from GapcovIntegration; runtime access remains pending.
        HCCandidate("gapcov-balota-roof", "balota exterior rest", "Land_Misc_FeedShack", "4544.932617 59.827011 3130.591064", "balota", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-belaya-polyana-roof", "belaya-polyana exterior rest", "Land_Barn_Wood2", "14188.152344 131.525253 14838.943359", "belaya-polyana", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-berezhki-roof", "berezhki exterior rest", "Land_Misc_FeedShack", "14917.326172 159.152939 14257.607422", "berezhki", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-berezino-roof", "berezino exterior rest", "Land_BusStop_City", "12360.422852 10.900807 9651.760742", "berezino", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-bogatyrka-roof", "bogatyrka exterior rest", "Land_Barn_Wood2", "1808.760254 293.057983 9146.089844", "bogatyrka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-bor-roof", "bor exterior rest", "Land_Barn_Wood2", "3100.955811 249.415558 4238.387207", "bor", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-chernaya-polyana-roof", "chernaya-polyana exterior rest", "Land_BusStop_City", "12141.347656 96.841225 13641.462891", "chernaya-polyana", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-chernogorsk-roof", "chernogorsk exterior rest", "Land_BusStop_City", "6342.815918 10.309018 2502.824951", "chernogorsk", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-devils-castle-roof", "devils-castle exterior rest", "Land_Misc_FeedShack", "6889.009277 340.438019 10862.524414", "devils-castle", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-dobroye-roof", "dobroye exterior rest", "Land_Barn_Wood2", "13314.882813 38.745819 14760.651367", "dobroye", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-dubovo-roof", "dubovo exterior rest", "Land_Barn_Wood2", "6653.661621 17.15004 3096.433838", "dubovo", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-dubrovka-roof", "dubrovka exterior rest", "Land_Misc_FeedShack", "10873.338867 86.26506 10268.777344", "dubrovka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-galkino-roof", "galkino exterior rest", "Land_Misc_FeedShack", "1292.366821 240.988266 7988.322266", "galkino", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-gorka-roof", "gorka exterior rest", "Land_Misc_FeedShack", "9656.139648 294.76709 9187.803711", "gorka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-guglovo-roof", "guglovo exterior rest", "Land_Misc_FeedShack", "8855.47168 344.730774 6983.57666", "guglovo", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-gvozdno-roof", "gvozdno exterior rest", "Land_Misc_FeedShack", "8633.587891 180.257217 12096.203125", "gvozdno", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-kabanino-roof", "kabanino exterior rest", "Land_Barn_Wood2", "5347.12793 336.546448 8650.952148", "kabanino", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-kalinovka-roof", "kalinovka exterior rest", "Land_Barn_Wood2", "7731.844727 172.662537 13149.407227", "kalinovka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-kamenka-roof", "kamenka exterior rest", "Land_Misc_FeedShack", "1354.851318 8.170421 2457.874268", "kamenka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-kamyshovo-roof", "kamyshovo exterior rest", "Land_Misc_FeedShack", "11816.854492 60.724621 4013.427734", "kamyshovo", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-karmanovka-roof", "karmanovka exterior rest", "Land_Misc_FeedShack", "12624.743164 110.643318 14528.345703", "karmanovka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-khelm-roof", "khelm exterior rest", "Land_Barn_Wood2", "12241.135742 95.680054 10614.205078", "khelm", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-kozlovka-roof", "kozlovka exterior rest", "Land_Misc_FeedShack", "4444.75293 317.184357 5074.055664", "kozlovka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-krasnostav-roof", "krasnostav exterior rest", "Land_BusStop_City", "11212.105469 196.35141 12197.904297", "krasnostav", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-krasnoye-roof", "krasnoye exterior rest", "Land_Misc_FeedShack", "6220.273438 465.571747 15337.134766", "krasnoye", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-kumyrna-roof", "kumyrna exterior rest", "Land_Misc_FeedShack", "8171.711426 184.208511 5446.868652", "kumyrna", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-lopatino-roof", "lopatino exterior rest", "Land_Misc_FeedShack", "2563.891602 261.918457 9221.756836", "lopatino", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-mogilevka-roof", "mogilevka exterior rest", "Land_Misc_FeedShack", "6997.211426 217.29245 4549.72168", "mogilevka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-msta-roof", "msta exterior rest", "Land_Misc_FeedShack", "11756.543945 200.672852 5805.47998", "msta", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-myshkino-roof", "myshkino exterior rest", "Land_Misc_FeedShack", "2543.650391 366.802979 7593.288574", "myshkino", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-nadezhdino-roof", "nadezhdino exterior rest", "Land_Misc_FeedShack", "5263.218262 295.056061 4857.912109", "nadezhdino", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-nagornoye-roof", "nagornoye exterior rest", "Land_Barn_Wood2", "9164.732422 294.66864 14844.21582", "nagornoye", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-nizhnee-roof", "nizhnee exterior rest", "Land_Barn_Wood2", "12942.088867 13.62428 8130.702637", "nizhnee", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-novaya-petrovka-roof", "novaya-petrovka exterior rest", "Land_BusStop_City", "3689.553467 190.512543 13081.108398", "novaya-petrovka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-novoselki-roof", "novoselki exterior rest", "Land_BusStop_Village2", "6078.25 20.931112 2827.880371", "novoselki", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-novy-sobor-roof", "novy-sobor exterior rest", "Land_Misc_FeedShack", "8118.444824 407.60434 8237.876953", "novy-sobor", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-nw-airfield-roof", "nw-airfield exterior rest", "Land_Misc_FeedShack", "5026.818359 267.413544 11275.800781", "nw-airfield", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-olsha-roof", "olsha exterior rest", "Land_Barn_Wood2", "13791.62207 43.747513 12868.035156", "olsha", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-orlovets-roof", "orlovets exterior rest", "Land_Misc_FeedShack", "12378.510742 105.373116 7740.572266", "orlovets", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-pavlovo-roof", "pavlovo exterior rest", "Land_Barn_Wood2", "1409.074463 141.003555 4047.021729", "pavlovo", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-polana-roof", "polana exterior rest", "Land_Barn_Wood2", "10677.808594 214.414337 7923.848633", "polana", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-polesovo-roof", "polesovo exterior rest", "Land_Misc_FeedShack", "5298.107422 213.97818 13590.946289", "polesovo", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-pulkovo-roof", "pulkovo exterior rest", "Land_Barn_Wood2", "5271.449219 308.912933 5515.677246", "pulkovo", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-pusta-roof", "pusta exterior rest", "Land_Barn_Wood2", "9200.192383 231.352341 3976.314941", "pusta", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-pustoshka-roof", "pustoshka exterior rest", "Land_Barn_Wood2", "3215.144287 313.942108 7776.054199", "pustoshka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-rogovo-roof", "rogovo exterior rest", "Land_Misc_FeedShack", "5097.820801 289.098145 6386.413574", "rogovo", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-severograd-roof", "severograd exterior rest", "Land_BusStop_City", "8068.223145 121.205116 12586.291992", "severograd", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-shakhovka-roof", "shakhovka exterior rest", "Land_Barn_Wood2", "9710.349609 216.305511 6487.099121", "shakhovka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-skvsch-biathlon-arena-roof", "skvsch-biathlon-arena exterior rest", "Land_Misc_FeedShack", "80.261421 411.262756 10449.132813", "skvsch-biathlon-arena", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-sosnovka-roof", "sosnovka exterior rest", "Land_Misc_FeedShack", "2057.715088 314.685272 6277.850586", "sosnovka", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-staroye-roof", "staroye exterior rest", "Land_Misc_FeedShack", "10643.481445 247.555817 6059.513672", "staroye", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-stary-yar-roof", "stary-yar exterior rest", "Land_Barn_Wood2", "4850.998047 476.733582 15220.709961", "stary-yar", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-svergino-roof", "svergino exterior rest", "Land_BusStop_City", "9667.137695 77.460258 13778.698242", "svergino", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-svetloyarsk-roof", "svetloyarsk exterior rest", "Land_BusStop_City", "13980.379883 18.696783 13250.694336", "svetloyarsk", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-svyatoy-roman-ski-resort-roof", "svyatoy-roman-ski-resort exterior rest", "Land_Misc_FeedShack", "196.072708 541.651978 11741.008789", "svyatoy-roman-ski-resort", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-tisy-roof", "tisy exterior rest", "Land_Barn_Wood2", "3905.636963 418.40564 15270.59082", "tisy", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-tisy-military-roof", "tisy-military exterior rest", "Land_Misc_FeedShack", "2171.249023 407.516541 13767.192383", "tisy-military", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-topolniki-roof", "topolniki exterior rest", "Land_Barn_Wood2", "2766.59082 230.615921 12138.327148", "topolniki", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-tulga-roof", "tulga exterior rest", "Land_Misc_FeedShack", "13331.621094 7.484608 5062.072754", "tulga", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-turovo-roof", "turovo exterior rest", "Land_Barn_Wood2", "13746.259766 30.365343 14129.463867", "turovo", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-vavilovo-roof", "vavilovo exterior rest", "Land_Barn_Wood2", "2256.535645 272.844635 10899.652344", "vavilovo", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-vybor-roof", "vybor exterior rest", "Land_BusStop_City", "3849.562256 311.902374 8854.833984", "vybor", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-vybor-military-roof", "vybor-military exterior rest", "Land_Barn_Wood2", "4431.20166 315.407806 8233.883789", "vybor-military", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-vyshnoye-roof", "vyshnoye exterior rest", "Land_Misc_FeedShack", "6155.063965 231.612427 5688.321777", "vyshnoye", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-vysotovo-roof", "vysotovo exterior rest", "Land_BusStop_City", "5716.401367 58.884052 2425.210205", "vysotovo", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-zabolotye-roof", "zabolotye exterior rest", "Land_Barn_Wood2", "1029.501343 341.571014 9965.56543", "zabolotye", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-zaprudnoye-roof", "zaprudnoye exterior rest", "Land_BusStop_City", "5387.128418 161.014206 12627.210938", "zaprudnoye", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-zelenogorsk-roof", "zelenogorsk exterior rest", "Land_BusStop_City", "2837.758301 205.57312 5262.322754", "zelenogorsk", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
        HCCandidate("gapcov-zvir-roof", "zvir exterior rest", "Land_Barn_Wood2", "555.201538 152.866577 5393.116211", "zvir", "map-wide", "exterior-rest", "runtime_access_clearance_pending");
    }

    static int CandidateCount()
    {
        HCEnsureCandidates();
        // Keep legacy five-scene operator catalogs safe for indexed consumers.
        if (s_Regional) { return s_Regional.Scenes.Count(); }
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

    protected static void HCRegionalReport()
    {
        Print("[HC Shelters] regional_scenes refused reason=" + s_RegionalReason + " runtime=PENDING");
    }

    // Once per process; finite authored catalog, never persistent scene state.
    protected static void HCLoadRegional()
    {
        if (s_RegionalLoaded) { return; }
        s_RegionalLoaded = true;
        string content = HCWorldStore.Read("$mission:hollow-country/travel/auditshelter_scenes.json");
        string error;
        HCShelterRegionalConfig loaded;
        s_RegionalFault = "regional_scene_data_missing_or_invalid";
        if (!JsonFileLoader<HCShelterRegionalConfig>.LoadData(content, loaded, error) || !loaded || !loaded.Scenes)
        {
            s_RegionalReason = "load length=" + content.Length().ToString() + " error=" + error;
            HCRegionalReport();
            return;
        }
        int baseCount = loaded.Scenes.Count();
        int additionalCount = 0;
        if (loaded.AdditionalScenes)
        {
            array<ref HCShelterRegionalScene> additional = loaded.AdditionalScenes;
            additionalCount = additional.Count();
            foreach (HCShelterRegionalScene extraScene : additional) { loaded.Scenes.Insert(extraScene); }
        }
        // Validate the merged image, including every additional Enabled field.
        if (!HCRegionalValid(loaded)) { HCRegionalReport(); return; }
        if (!HCJsonFields.Has(content, "Enabled") || !HCJsonFields.Has(content, "Scenes")) { s_RegionalReason = "fields_missing"; HCRegionalReport(); return; }
        if (!HCJsonFields.Every(content, "Enabled", 3)) { s_RegionalReason = "scene_enabled_missing"; HCRegionalReport(); return; }
        Print("[HC Shelters] regional_scenes base=" + baseCount.ToString() + " additional=" + additionalCount.ToString() + " runtime=PENDING");
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

    // Names the first refused check and scene index in the boot log.
    static bool HCRegionalRefuse(string check, int sceneIndex)
    {
        s_RegionalReason = check + " scene=" + sceneIndex.ToString();
        return false;
    }

    static bool HCRegionalValid(HCShelterRegionalConfig config)
    {
        HCEnsureCandidates();
        int sceneIndex = -1;
        if (!config || config.SchemaVersion != 1 || !config.Scenes) { return HCRegionalRefuse("check1", sceneIndex); }
        // Historical catalogs contain exactly the original five identities.
        // Expanded catalogs contain all registered identities in source order.
        int sceneCount = config.Scenes.Count();
        if (sceneCount != 5 && sceneCount != s_Candidates.Count()) { return HCRegionalRefuse("check2", sceneIndex); }
        if (!HCObserverTransitionGate.Finite(config.ObserverDistance) || config.ObserverDistance < 500 || config.ObserverDistance > 10000) { return HCRegionalRefuse("check3", sceneIndex); }
        if (config.WorkUnits < 24 || config.WorkUnits > 256) { return HCRegionalRefuse("check4", sceneIndex); }
        if (!HCObserverTransitionGate.Finite(config.BoundsToleranceSquared) || config.BoundsToleranceSquared <= 0 || config.BoundsToleranceSquared > 0.04) { return HCRegionalRefuse("check5", sceneIndex); }
        array<ref HCShelterRegionalScene> scenes = config.Scenes;
        sceneIndex = 0;
        foreach (HCShelterRegionalScene scene : scenes)
        {
            HCShelterSurvey candidate = GetCandidate(sceneIndex);
            if (!candidate) { return HCRegionalRefuse("candidate", sceneIndex); }
            if (!scene || scene.Id != candidate.Id || scene.BuildingClass != candidate.BuildingClass || scene.Name != candidate.Name) { return HCRegionalRefuse("check6", sceneIndex); }
            // Authored access boxes sit exactly 2 m outside the clip box; a 1 mm
            // allowance absorbs float32 rounding of that boundary.
            if (!scene.Position || scene.Position.Count() != 3 || vector.DistanceSq(HCInteriorTemplates.AsVector(scene.Position), candidate.Position) > config.BoundsToleranceSquared) { return HCRegionalRefuse("check7", sceneIndex); }
            if (!HCRegionalBox(scene.ClipMin, scene.ClipMax) || !HCRegionalBox(scene.AccessMin, scene.AccessMax) || !HCRegionalBox(scene.YardMin, scene.YardMax)) { return HCRegionalRefuse("check8", sceneIndex); }
            if (scene.AccessMin[0] > scene.ClipMin[0] - 1.999 || scene.AccessMax[0] < scene.ClipMax[0] + 1.999) { return HCRegionalRefuse("check9", sceneIndex); }
            if (scene.AccessMin[2] > scene.ClipMin[2] - 1.999 || scene.AccessMax[2] < scene.ClipMax[2] + 1.999) { return HCRegionalRefuse("check10", sceneIndex); }
            if (scene.AccessMin[1] > -20 || scene.AccessMax[1] < 20) { return HCRegionalRefuse("check11", sceneIndex); }
            if (!scene.Slots || scene.Slots.Count() != 3 || scene.History.Length() == 0) { return HCRegionalRefuse("check12", sceneIndex); }
            array<ref array<float>> slots = scene.Slots;
            foreach (array<float> slot : slots)
            {
                if (!slot || slot.Count() != 3) { return HCRegionalRefuse("check13", sceneIndex); }
                vector point = HCInteriorTemplates.AsVector(slot);
                if (!HCInteriorRules.SaneVector(point, 30)) { return HCRegionalRefuse("check14", sceneIndex); }
                if (point[0] + 1.5 >= scene.AccessMin[0]) { return HCRegionalRefuse("check15", sceneIndex); }
                if (point[0] - 1.5 <= scene.YardMin[0] || point[0] + 1.5 >= scene.YardMax[0]) { return HCRegionalRefuse("check16", sceneIndex); }
                if (point[2] - 1.5 <= scene.YardMin[2] || point[2] + 1.5 >= scene.YardMax[2]) { return HCRegionalRefuse("check17", sceneIndex); }
            }
            sceneIndex = sceneIndex + 1;
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
    ref array<ref HCShelterRegionalScene> AdditionalScenes;
}
