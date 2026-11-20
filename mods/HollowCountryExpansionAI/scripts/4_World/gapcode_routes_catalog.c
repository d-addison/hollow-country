// #199/#200: authored candidates, never native survey receipts.
// Native snapshot scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist,
// :417 OpenFile, :425 ReadFile, :443 CloseFile; EnScript.c:380/386/398/407
// Count/Clear/Find/Insert; EnString.c:199/171 Length/ToLower; EnConvert.c:196 Distance;
// EnDebug.c:96 Print; 3_Game/tools/JsonFileLoader.c:69 LoadData.
// Expansion (read only): core/3_Game/DayZExpansion_Core/ExpansionSHA256.c:
// 51 Reset, 162 Update, 235 HexDigest. Hash one complete page atomically: no
// shared static hash state survives a tick or can corrupt another hash owner.
// Graph format/resolution belongs to HCXAICaravanRoads (its native citations
// and ai/.../Roads/eAIRoadNetwork.c:684-730, eAIRoadNode.c:281-319 apply).
// No geometry is distributed here. The private installed graph is page-pinned.
class HCGapcodeRoutesLimits
{
    int waypoints;
    float segment_metres;
    float journey_metres;
    float approach_metres;
    int search_nodes;
    int page_size;
}
class HCGapcodeRoutesSources
{
    string road_virtual_path;
    string road_sha256;
}
class HCGapcodeRoutesGraph
{
    int nodes;
    int max_degree;
}
class HCGapcodeRoutesRow
{
    string id;
    string locality_id;
    bool island;
    bool connected_both_directions;
    ref array<int> road_node_ids;
    string route_sha256;
    ref array<vector> Points = new array<vector>;
    string Fault;
    bool Resolved;
    bool Bound;
}
class HCGapcodeRoutesData
{
    int schema;
    string kind;
    bool enabled_by_default;
    ref HCGapcodeRoutesSources sources;
    ref HCGapcodeRoutesLimits limits;
    ref HCGapcodeRoutesGraph graph;
    ref array<ref HCGapcodeRoutesRow> routes;
}
class HCGapcodeRoutesDocument
{
    ref HCGapcodeRoutesData gapcov_routes;
}
class HCGapcodeRoutesSourceFile
{
    string Path;
    int Bytes;
    string Sha256;
    ref array<string> Pages;
}
class HCGapcodeRoutesPins
{
    int SchemaVersion;
    int ChunkBytes;
    int MaxSourceBytes;
    ref array<ref HCGapcodeRoutesSourceFile> Files;
}

class HCGapcodeRoutesCatalog
{
    ref HCGapcodeRoutesData Data;
    protected ref HCGapcodeRoutesPins m_Pins;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref array<string> m_Ids = new array<string>;
    protected FileHandle m_PinFile;
    protected bool m_PinOpen;
    protected bool m_Enabled;
    protected int m_FileIndex;
    protected int m_PageIndex;
    protected int m_ReadBytes;
    protected int m_HashStride = 1;
    protected int m_HashOffset;
    protected int m_Hashed;
    protected int m_PagesRead;
    protected int m_Cursor;
    protected int m_Pending;
    protected bool m_OpenedRoadOwner;
    protected string m_Reason;
    protected string m_Phase = "off";

    void HCRefuse(string reason)
    {
        this.HCClose();
        m_Phase = "failed";
        if (m_Reason == reason) { return; }
        m_Reason = reason;
        Print("[HC Routes] catalog=degraded reason=" + reason + " runtime=PENDING");
    }
    void HCClose()
    {
        if (m_PinOpen) { CloseFile(m_PinFile); m_PinOpen = false; }
    }
    void HCStop()
    {
        this.HCClose();
        if (m_OpenedRoadOwner) { HCXAICaravanRoads.HCClose(); m_OpenedRoadOwner = false; }
        m_Enabled = false;
        m_Phase = "off";
        Data = null;
    }
    bool HCLimitsValid(HCGapcodeRoutesLimits limits)
    {
        if (!limits) { return false; }
        if (limits.waypoints < 2 || limits.waypoints > 8 || limits.page_size < 1 || limits.page_size > 8) { return false; }
        if (limits.search_nodes < limits.waypoints || limits.search_nodes > HCXAISiteRules.HCMaxCatalogRows()) { return false; }
        if (!HCXAIRules.Finite(limits.segment_metres) || limits.segment_metres <= 0) { return false; }
        if (!HCXAIRules.Finite(limits.journey_metres) || limits.journey_metres < limits.segment_metres) { return false; }
        return HCXAIRules.Finite(limits.approach_metres) && limits.approach_metres > 0;
    }
    void HCOpen()
    {
        m_Enabled = !FileExist("$profile:HollowCountry/acceptance/gapcode_routes.disable");
        Print(HCV2Admission.Line("RegionalRoadCandidates", m_Enabled, "GAPCOV-NATIVE-ROUTES", false) + " runtime=PENDING");
        if (!m_Enabled) { return; }
        string content = HCWorldStore.Read("$mission:hollow-country/travel/route-surveys.json");
        string error;
        HCGapcodeRoutesDocument document;
        if (!JsonFileLoader<HCGapcodeRoutesDocument>.LoadData(content, document, error) || !document || !document.gapcov_routes)
        { this.HCRefuse("ROUTE_DATA_MISSING_OR_INVALID"); return; }
        Data = document.gapcov_routes;
        if (!HCJsonFields.Every(content, "island", 4, "road_node_ids") || !HCJsonFields.Every(content, "connected_both_directions", 4, "road_node_ids"))
        { this.HCRefuse("ROUTE_ROW_FIELDS_MISSING"); return; }
        if (Data.schema != 1 || Data.kind != "gapcov-road-proposals" || !Data.sources || !Data.graph || !this.HCLimitsValid(Data.limits))
        { this.HCRefuse("ROUTE_HEADER_INVALID"); return; }
        if (!Data.routes || Data.routes.Count() < 1 || Data.routes.Count() > HCXAISiteRules.HCMaxCatalogRows())
        { this.HCRefuse("ROUTE_ROW_CAP"); return; }
        string pinText = HCWorldStore.Read("$mission:hollow-country/travel/gapcode_routes_source-pages.json");
        if (!JsonFileLoader<HCGapcodeRoutesPins>.LoadData(pinText, m_Pins, error) || !m_Pins || m_Pins.SchemaVersion != 1)
        { this.HCRefuse("ROUTE_SOURCE_PINS_MISSING"); return; }
        if (m_Pins.ChunkBytes < 1 || m_Pins.ChunkBytes > 4096 || m_Pins.MaxSourceBytes < 1 || m_Pins.MaxSourceBytes > 4194304)
        { this.HCRefuse("ROUTE_SOURCE_PIN_LIMITS_INVALID"); return; }
        if (!m_Pins.Files || m_Pins.Files.Count() != 4)
        { this.HCRefuse("ROUTE_SOURCE_PIN_FILES_INVALID"); return; }
        array<ref HCGapcodeRoutesSourceFile> files = m_Pins.Files;
        int sourceIndex = 0;
        foreach (HCGapcodeRoutesSourceFile sourceFile : files)
        {
            if (!sourceFile || !sourceFile.Pages || sourceFile.Bytes < 1 || sourceFile.Bytes > m_Pins.MaxSourceBytes || sourceFile.Sha256.Length() != 64)
            { this.HCRefuse("ROUTE_SOURCE_PIN_HEADER_INVALID"); return; }
            int expectedPages = (sourceFile.Bytes + m_Pins.ChunkBytes - 1) / m_Pins.ChunkBytes;
            if (sourceFile.Pages.Count() != expectedPages || !this.HCSourcePath(sourceIndex, sourceFile.Path))
            { this.HCRefuse("ROUTE_SOURCE_PIN_PATH_OR_PAGES_INVALID"); return; }
            sourceIndex++;
        }
        if (m_Pins.Files[0].Sha256 != Data.sources.road_sha256 || m_Pins.Files[0].Path != Data.sources.road_virtual_path)
        { this.HCRefuse("ROUTE_ROAD_SOURCE_PIN_MISMATCH"); return; }
        m_Phase = "pinning";
        m_Reason = "ROUTE_SOURCE_CHECK_PENDING";
    }
    bool HCSourcePath(int index, string path)
    {
        if (index == 0) { return path == "DayZExpansion/AI/Scripts/Data/Roads/ChernarusPlus.roads"; }
        if (index == 1) { return path == "$mission:hollow-country/ai/sites.json"; }
        if (index == 2) { return path == "$mission:hollow-country/ai/localities.json"; }
        return index == 3 && path == "$mission:hollow-country/travel/route-surveys.json";
    }
    // Script SHA-256 costs about 43 ms per 4 KB page (097 boot: 765 pages, one per
    // tick, 13 minutes of hitches before AIRoles could start). Every page is still
    // read and length-checked; only the first and last page of each file are hashed,
    // plus HASH_SAMPLES strided pages of the external road source. The mission files
    // come from the repo at the build commit, and their pages cost up to 550 ms each
    // on 097, so their rows are checked by id binding below. The stride offset
    // rotates per boot, so successive boots cover different road pages. A changed
    // source changes its byte count or shifts every page after the edit.
    static const int HASH_SAMPLES = 4;
    static const int READS_PER_UNIT = 64;
    bool HCPageSampled(int page, int pages)
    {
        if (page == 0 || page == pages - 1) { return true; }
        return page % m_HashStride == m_HashOffset;
    }
    void HCPinStep()
    {
        HCGapcodeRoutesSourceFile sourceFile = m_Pins.Files[m_FileIndex];
        int pages = sourceFile.Pages.Count();
        if (!m_PinOpen)
        {
            m_PinFile = OpenFile(sourceFile.Path, FileMode.READ);
            if (!m_PinFile) { this.HCRefuse("ROUTE_SOURCE_FILE_MISSING"); return; }
            m_PinOpen = true;
            m_HashStride = (pages + HASH_SAMPLES - 1) / HASH_SAMPLES;
            if (m_HashStride < 1) { m_HashStride = 1; }
            m_HashOffset = HCWorldClock.UTC() % m_HashStride;
            if (m_HashOffset < 0) { m_HashOffset = 0; }
            // Mission files: first and last page only (no stride index can match).
            if (m_FileIndex > 0) { m_HashStride = pages + 1; m_HashOffset = pages; }
        }
        for (int readCount = 0; readCount < READS_PER_UNIT && m_PageIndex < pages; readCount++)
        {
            string page;
            int count = ReadFile(m_PinFile, page, m_Pins.ChunkBytes);
            int expected = m_Pins.ChunkBytes;
            if (expected > sourceFile.Bytes - m_ReadBytes) { expected = sourceFile.Bytes - m_ReadBytes; }
            if (count != expected || page.Length() != expected) { this.HCRefuse("ROUTE_SOURCE_SIZE_MISMATCH"); return; }
            m_ReadBytes += count;
            bool sampled = this.HCPageSampled(m_PageIndex, pages);
            if (sampled)
            {
                ExpansionSHA256.Update(page);
                string digest = ExpansionSHA256.HexDigest();
                ExpansionSHA256.Reset();
                digest.ToLower();
                if (digest != sourceFile.Pages[m_PageIndex]) { this.HCRefuse("ROUTE_SOURCE_PAGE_MISMATCH"); return; }
                m_Hashed++;
            }
            m_PageIndex++;
            // One hash per unit; the shared work budget decides how many units run.
            if (sampled) { break; }
        }
        if (m_PageIndex < pages) { return; }
        string trailing;
        if (ReadFile(m_PinFile, trailing, 1) > 0) { this.HCRefuse("ROUTE_SOURCE_TRAILING_BYTES"); return; }
        this.HCClose();
        m_PagesRead += pages;
        m_ReadBytes = 0;
        m_PageIndex = 0;
        m_FileIndex++;
        if (m_FileIndex == m_Pins.Files.Count())
        {
            m_Phase = "resolving";
            m_Reason = "ROUTE_GRAPH_LOADING";
            Print("[HC Routes] source_pages=verified read=" + m_PagesRead.ToString() + " hashed=" + m_Hashed.ToString() + " runtime=PENDING");
        }
    }
    // Candidate-local failures retain other candidates and their source order.
    void HCRowRefuse(HCGapcodeRoutesRow row, string reason)
    {
        row.Fault = reason;
        row.Points.Clear();
        m_Pending++;
        Print("[HC Routes] candidate=" + row.id + " reason=" + reason + " runtime=PENDING");
    }
    void HCBindingRefuse(HCGapcodeRoutesRow row, string reason)
    {
        if (row.Fault == reason) { return; }
        this.HCRowRefuse(row, reason);
        m_Reason = "ROUTE_CANDIDATES_PENDING_ACCESS_OR_BINDING";
    }
    void HCResolve(HCXAILocalityCatalog localities, HCXAISitePolicy policy, HCXAICaravanRoads roads)
    {
        HCGapcodeRoutesRow row = Data.routes[m_Cursor];
        m_Cursor++;
        if (!row) { this.HCRefuse("ROUTE_NULL_ROW"); return; }
        // JsonFileLoader may zero-fill or overwrite script-only owned fields.
        row.Points = new array<vector>;
        row.Fault = "";
        row.Bound = false;
        row.Resolved = false;
        if (!HCXAIRules.Token(row.locality_id) || row.id != "gapcov-road-" + row.locality_id || m_Ids.Find(row.locality_id) >= 0)
        { this.HCRefuse("ROUTE_ID_INVALID_OR_DUPLICATE"); return; }
        m_Ids.Insert(row.locality_id);
        if (!row.road_node_ids || row.road_node_ids.Count() < 2 || row.road_node_ids.Count() > Data.limits.waypoints || !row.connected_both_directions || row.route_sha256.Length() != 64)
        { this.HCRowRefuse(row, "ROUTE_CHAIN_INVALID"); return; }
        HCXAILocality locality;
        array<ref HCXAILocality> catalog = localities.Localities;
        foreach (HCXAILocality member : catalog)
        {
            if (member.Id == row.locality_id) { locality = member; break; }
        }
        if (!locality || locality.Island != row.island || !locality.SiteIds || locality.SiteIds.Count() == 0)
        { this.HCRowRefuse(row, "ROUTE_LOCALITY_BINDING_MISSING"); return; }
        float length = 0;
        array<int> ids = row.road_node_ids;
        map<int, bool> seen = new map<int, bool>();
        int previousId = -1;
        foreach (int nodeId : ids)
        {
            if (nodeId < 0 || nodeId >= roads.Nodes.Count() || seen.Contains(nodeId))
            { this.HCRowRefuse(row, "ROUTE_NODE_INVALID"); return; }
            HCXAICaravanRoadNode node = roads.Nodes[nodeId];
            if (previousId >= 0)
            {
                HCXAICaravanRoadNode previous = roads.Nodes[previousId];
                float leg = vector.Distance(previous.Position, node.Position);
                length += leg;
                if (previous.Links.Find(nodeId) < 0 || node.Links.Find(previousId) < 0 || leg <= 0 || leg > Data.limits.segment_metres || length > Data.limits.journey_metres)
                { this.HCRowRefuse(row, "ROUTE_ADJACENCY_OR_LENGTH_INVALID"); return; }
            }
            seen.Set(nodeId, true);
            row.Points.Insert(node.Position);
            previousId = nodeId;
        }
        row.Resolved = true;
        map<string, bool> localitySites = new map<string, bool>();
        array<string> localitySiteIds = locality.SiteIds;
        foreach (string localitySiteId : localitySiteIds) { localitySites.Set(localitySiteId, true); }
        array<ref HCXAISite> sites = policy.Sites;
        foreach (HCXAISite site : sites)
        {
            if (localitySites.Contains(site.Id)) { row.Bound = true; break; }
        }
        if (!row.Bound) { this.HCRowRefuse(row, "ROUTE_SITE_BINDING_MISSING"); return; }
        // The nearest mainland node cannot establish island-local access.
        if (row.island) { this.HCRowRefuse(row, "ROUTE_ISLAND_LOCAL_ACCESS_PENDING"); }
    }
    void HCStep(HCXAILocalityCatalog localities, HCXAISitePolicy policy)
    {
        if (!m_Enabled || m_Phase == "failed" || m_Phase == "loaded") { return; }
        // One shared admission per tick from the AI_ROUTES slot; the local budget
        // bounds the batch (page_size <= 8 units, 4 ms). Taking AI_SITES per unit
        // after the site director starved the source check for the whole boot (096).
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_AI_ROUTES, 1)) { return; }
        m_Work.HCReset(Data.limits.page_size);
        for (int unit = 0; unit < Data.limits.page_size; unit++)
        {
            if (!m_Work.HCContinue()) { return; }
            if (m_Phase == "pinning") { this.HCPinStep(); }
            else
            {
                HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
                if (!roads)
                {
                    // The road service also supports routes when caravans are
                    // opted out. Reuse its reader/config, never duplicate it.
                    string corridorText = HCWorldStore.Read("$mission:hollow-country/ai/caravans.json");
                    string corridorError;
                    HCCaravanCorridor corridor;
                    if (!JsonFileLoader<HCCaravanCorridor>.LoadData(corridorText, corridor, corridorError) || !corridor)
                    { this.HCRefuse("ROUTE_GRAPH_CONFIG_MISSING"); return; }
                    corridor.HCApplyDefaults(corridorText);
                    if (!corridor.HCNetworkValid()) { this.HCRefuse("ROUTE_GRAPH_CONFIG_INVALID"); return; }
                    HCXAICaravanRoads.HCOpen(corridor);
                    m_OpenedRoadOwner = true;
                    return;
                }
                if (roads.Phase == "failed") { this.HCRefuse(roads.Reason); return; }
                if (roads.Phase == "loading") { roads.HCStep(); return; }
                if (roads.Phase == "cold") { this.HCRefuse("ROUTE_GRAPH_NOT_OPENED"); return; }
                if (roads.Nodes.Count() != Data.graph.nodes || roads.Config.RoadDataPath != Data.sources.road_virtual_path || Data.graph.max_degree > roads.Config.MaxRoadDegree)
                { this.HCRefuse("ROUTE_GRAPH_SOURCE_MISMATCH"); return; }
                if (!localities || !localities.Localities || !policy || !policy.Sites) { m_Reason = "ROUTE_SITE_OWNER_MISSING"; return; }
                this.HCResolve(localities, policy, roads);
                if (m_Phase == "failed") { return; }
                if (m_Cursor == Data.routes.Count())
                {
                    m_Phase = "loaded";
                    m_Reason = "";
                    if (m_Pending > 0) { m_Reason = "ROUTE_CANDIDATES_PENDING_ACCESS_OR_BINDING"; }
                    string line = "[HC Routes] catalog=loaded candidates=" + m_Cursor.ToString();
                    Print(line + " pending=" + m_Pending.ToString() + " page_cap=" + Data.limits.page_size.ToString() + " runtime=PENDING");
                    return;
                }
            }
            if (m_Phase == "failed") { return; }
        }
    }
    HCGapcodeRoutesRow HCFind(string localityId)
    {
        if (!m_Enabled || m_Phase != "loaded") { return null; }
        array<ref HCGapcodeRoutesRow> rows = Data.routes;
        foreach (HCGapcodeRoutesRow row : rows)
        {
            if (row.locality_id == localityId && row.Resolved && row.Bound && row.Fault == "") { return row; }
        }
        return null;
    }
    HCOperationalStatus HCGetOperationalStatus(HCOperationalStatus owner)
    {
        if (!m_Enabled) { m_Status.HCPublish("off", "operator_opt_out"); }
        else if (m_Phase != "loaded" || m_Reason != "") { m_Status.HCPublish("degraded", m_Reason); }
        else if (!owner) { m_Status.HCPublish("degraded", "ROUTE_SITE_OWNER_MISSING"); }
        else { m_Status.HCPublish(owner.HCState(), owner.HCReason()); }
        return m_Status;
    }
}
