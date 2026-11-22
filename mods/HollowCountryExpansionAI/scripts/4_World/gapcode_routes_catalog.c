// #199/#200: authored candidates, never native survey receipts.
// Native snapshot scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist,
// :417 OpenFile, :425 ReadFile, :443 CloseFile; EnScript.c:380/386/398/407
// Count/Clear/Find/Insert; EnString.c:199/171 Length/ToLower; EnConvert.c:196 Distance;
// EnDebug.c:96 Print; 3_Game/tools/JsonFileLoader.c:69 LoadData.
// Expansion (read only): core/3_Game/DayZExpansion_Core/ExpansionSHA256.c:
// 51 Reset, 162 Update(input, reset, finalize), 235 HexDigest. The installed
// protected hash/bits/buffer fields are read/written only by the adapter below.
// The adapter below retains an independent context between 128-byte parts and
// restores the provider's incoming static context before returning.
// Graph format/resolution belongs to HCXAICaravanRoads (its native citations
// and ai/.../Roads/eAIRoadNetwork.c:684-730, eAIRoadNode.c:281-319 apply).
// The build pins the installed graph; admitted sources skip runtime hashing.
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
    string localities_sha256;
    string sites_sha256;
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
    string status;
    ref array<vector> Points = new array<vector>;
    string Fault;
    bool Resolved;
    bool Bound;
}
class HCGapcodeRoutesData
{
    int schema;
    string kind;
    int row_count;
    // Index-page envelopes reuse this DTO before root manifest admission.
    int page_start;
    string identity_sha256;
    ref array<ref HCGapcodeRoutesPageIdentity> pages;
    ref array<ref HCGapcodeRoutesPageIdentity> index_pages;
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
    int PageStart;
    int PageCount;
}
class HCGapcodeRoutesPins
{
    int SchemaVersion;
    int ChunkBytes;
    int MaxSourceBytes;
    ref array<ref HCGapcodeRoutesSourceFile> Files;
}

// Generated with the mission bundle; preland verifies all bytes/digests offline.
// Runtime compares source identities; small manifest pages are hashed incrementally.
class HCGapcodeRoutesManifest : HCGapcodeRoutesPins
{
    int CatalogPageStart;
    int HashPageVersion;
    ref array<ref HCGapcodeRoutesSourceFile> HashPages;
    // Bounded hash-page documents use the same manifest envelope.
    int PageStart;
    ref array<string> Hashes;
    string CatalogPath;
    string CatalogSha256;
    string CatalogIdentitySha256;
    ref array<ref HCGapcodeRoutesPageIdentity> CatalogPages;
    string SourcePagesSha256;
    int SourceCount;
    int PageCount;
    string RoadGraphPath;
    string RoadGraphSha256;
}

// Header only: the large numeric arrays are streamed, never deserialized in
// one atomic JsonFileLoader call. Generated key order is part of schema 1.
class HCXRoadCompactHeader
{
    int SchemaVersion;
    string SourcePath;
    string SourceSha256;
    int RoadVersion;
    int Width;
    int Height;
    int NodeCount;
    int EdgeCount;
}

// Save/restore only the installed provider's protected hashing context. No hash
// algorithm is duplicated. Each visit updates <=128 original page bytes; other
// hash users see exactly their incoming context even between route visits.
// Installed ExpansionSHA256: protected s_Hash[8], s_TotalBits[2],
// s_Buffer[64], s_BufferIndex; Update(input, reset, finalize), Reset, HexDigest.
class HCGapcodeRouteHashState
{
    CF_Uint Hash[8];
    CF_Uint Bits[2];
    CF_Uint Buffer[64];
    int Index;
    bool Started;
}
class HCGapcodeRouteHash : ExpansionSHA256
{
    static void HCRouteCapture(HCGapcodeRouteHashState state)
    {
        for (int hashIndex = 0; hashIndex < 8; hashIndex++) { state.Hash[hashIndex] = s_Hash[hashIndex]; }
        for (int bitIndex = 0; bitIndex < 2; bitIndex++) { state.Bits[bitIndex] = s_TotalBits[bitIndex]; }
        for (int byteIndex = 0; byteIndex < 64; byteIndex++) { state.Buffer[byteIndex] = s_Buffer[byteIndex]; }
        state.Index = s_BufferIndex;
    }
    static void HCRouteRestore(HCGapcodeRouteHashState state)
    {
        for (int hashIndex = 0; hashIndex < 8; hashIndex++) { s_Hash[hashIndex] = state.Hash[hashIndex]; }
        for (int bitIndex = 0; bitIndex < 2; bitIndex++) { s_TotalBits[bitIndex] = state.Bits[bitIndex]; }
        for (int byteIndex = 0; byteIndex < 64; byteIndex++) { s_Buffer[byteIndex] = state.Buffer[byteIndex]; }
        s_BufferIndex = state.Index;
    }
    static string HCRoutePart(HCGapcodeRouteHashState state, string part, bool last)
    {
        HCGapcodeRouteHashState ambient = new HCGapcodeRouteHashState;
        HCRouteCapture(ambient);
        if (state.Started) { HCRouteRestore(state); }
        else { Reset(); state.Started = true; }
        Update(part, false, last);
        string digest;
        if (last) { digest = HexDigest(); }
        else { HCRouteCapture(state); }
        HCRouteRestore(ambient);
        return digest;
    }
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
    protected string m_HashPage;
    protected int m_HashCursor;
    protected ref HCGapcodeRouteHashState m_PageHash;
    protected int m_PagesRead;
    protected int m_Cursor;
    protected int m_IndexPage;
    protected int m_IndexRows;
    protected int m_CatalogPage;
    protected int m_CatalogRows;
    protected int m_PinPeakTicks;
    protected int m_Pending;
    protected ref map<string, int> m_Refusals = new map<string, int>;
    protected bool m_RefusalsDirty;
    protected int m_ValidityMismatch;
    protected bool m_ManifestAdmitted;
    protected ref HCGapcodeRoutesManifest m_Manifest;
    protected int m_ManifestPage;
    protected int m_ManifestHashes;
    protected int m_ManifestCatalogPages;
    protected int m_ManifestCatalogRows;
    protected string m_ManifestText;
    protected ref HCGapcodeRouteHashState m_ManifestHash;
    protected int m_ManifestHashCursor;
    protected bool m_ManifestHashVerified;
    protected float m_ManifestMs;
    protected float m_PageMsMax;
    protected float m_GraphOpenMs;
    protected int m_Slices;
    protected int m_Units;
    protected int m_ResolvePeakTicks;
    protected float m_Started;
    protected bool m_OpenedRoadOwner;
    protected string m_Reason;
    protected string m_Phase = "off";

    void HCRefuse(string reason, string sourcePath = "", int pageIndex = -1)
    {
        this.HCClose();
        m_Phase = "failed";
        if (m_Reason == reason) { return; }
        m_Reason = reason;
        string sourceContext;
        if (sourcePath != "")
        {
            // Only HCSourcePath-validated virtual paths reach this diagnostic.
            // Zero-based page index identifies the exact pin to regenerate/check.
            sourceContext = " file=" + sourcePath + " page_index=" + pageIndex.ToString();
        }
        Print("[HC Routes] catalog=degraded reason=" + reason + sourceContext + " runtime=PENDING");
        if (m_ValidityMismatch > 0)
        { Print("[HC Routes] validity_mismatch=" + m_ValidityMismatch.ToString() + " reason=" + reason + " runtime=PENDING"); }
    }
    void HCClose()
    {
        if (m_PinOpen) { CloseFile(m_PinFile); m_PinOpen = false; }
    }
    void HCStop()
    {
        this.HCClose();
        if (m_RefusalsDirty)
        {
            Print("[HC Routes] catalog=stopped" + this.HCRefusalSummary() + " runtime=PENDING");
        }
        m_Manifest = null;
        m_ManifestHash = null;
        m_ManifestText = "";
        m_PageHash = null;
        m_HashPage = "";
        m_HashCursor = 0;
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
        m_Started = GetGame().GetTickTime();
        m_Enabled = !FileExist("$profile:HollowCountry/acceptance/gapcode_routes.disable");
        Print(HCV2Admission.Line("RegionalRoadCandidates", m_Enabled, "GAPCOV-NATIVE-ROUTES", false) + " runtime=PENDING");
        if (!m_Enabled) { return; }
        HCModuleReadiness.HCRegisterUse("optional-expansion-human-ai", "regional_road_site_binding");
        string content;
        if (!this.HCReadBounded("$mission:hollow-country/travel/gapcov-roads/index.json", 4096, content))
        { this.HCRefuse("ROUTE_HEADER_SIZE_OR_MISSING"); return; }
        string error;
        if (!JsonFileLoader<HCGapcodeRoutesData>.LoadData(content, Data, error) || !Data)
        { this.HCRefuse("ROUTE_DATA_MISSING_OR_INVALID"); return; }
        if (Data.schema != 1 || Data.kind != "gapcov-road-proposals" || !Data.sources || !Data.graph || !this.HCLimitsValid(Data.limits))
        { this.HCRefuse("ROUTE_HEADER_INVALID"); return; }
        if (Data.row_count < 1 || Data.row_count > HCXAISiteRules.HCMaxCatalogRows() || !Data.index_pages || Data.index_pages.Count() < 1 || Data.index_pages.Count() > 32)
        { this.HCRefuse("ROUTE_ROW_CAP"); return; }
        Data.routes = new array<ref HCGapcodeRoutesRow>;
        Data.pages = new array<ref HCGapcodeRoutesPageIdentity>;
        m_Phase = "index";
        m_Reason = "ROUTE_INDEX_PENDING";
    }
    // Read at most cap+1 bytes; reject oversized inputs before JSON parsing.
    bool HCReadBounded(string path, int cap, out string content)
    {
        FileHandle file = OpenFile(path, FileMode.READ);
        if (!file) { return false; }
        int count = ReadFile(file, content, cap + 1);
        CloseFile(file);
        return count > 0 && count <= cap && content.Length() == count;
    }
    bool HCIndexRefuse(string reason)
    {
        m_ValidityMismatch++;
        this.HCRefuse(reason);
        return false;
    }
    // One bounded read, <=128-byte hash update, or <=4 KiB parse per visit.
    // Reuse the manifest scratch state; the phases never overlap.
    bool HCIndexPageStep()
    {
        HCGapcodeRoutesPageIdentity identity = Data.index_pages[m_IndexPage];
        string suffix = m_IndexPage.ToString();
        if (m_IndexPage < 10) { suffix = "00" + suffix; }
        else { suffix = "0" + suffix; }
        string expected = "$mission:hollow-country/travel/gapcov-roads/index-";
        expected += suffix;
        expected += ".json";
        if (!identity) { return this.HCIndexRefuse("ROUTE_INDEX_PAGE_INVALID"); }
        if (identity.Path != expected) { return this.HCIndexRefuse("ROUTE_INDEX_PAGE_PATH"); }
        if (identity.Bytes < 1 || identity.Bytes > 4096)
        { return this.HCIndexRefuse("ROUTE_INDEX_PAGE_SIZE"); }
        if (identity.Sha256.Length() != 64 || identity.IdentitySha256.Length() != 64)
        { return this.HCIndexRefuse("ROUTE_INDEX_PAGE_INVALID"); }
        if (m_ManifestText == "")
        {
            if (!this.HCReadBounded(expected, identity.Bytes, m_ManifestText) || m_ManifestText.Length() != identity.Bytes)
            { return this.HCIndexRefuse("ROUTE_INDEX_PAGE_SIZE_OR_MISSING"); }
            m_ManifestHash = new HCGapcodeRouteHashState;
            m_ManifestHashCursor = 0;
            m_ManifestHashVerified = false;
            return false;
        }
        if (!m_ManifestHashVerified)
        {
            int count = Math.Min(HASH_BYTES_PER_STEP, m_ManifestText.Length() - m_ManifestHashCursor);
            bool last = m_ManifestHashCursor + count == m_ManifestText.Length();
            string digest = HCGapcodeRouteHash.HCRoutePart(m_ManifestHash, m_ManifestText.Substring(m_ManifestHashCursor, count), last);
            m_ManifestHashCursor += count;
            if (!last) { return false; }
            digest.ToLower();
            if (digest != identity.Sha256) { return this.HCIndexRefuse("ROUTE_INDEX_PAGE_MISMATCH"); }
            m_ManifestHashVerified = true;
            m_ManifestHash = null;
            return false;
        }
        string error;
        HCGapcodeRoutesData page;
        if (!JsonFileLoader<HCGapcodeRoutesData>.LoadData(m_ManifestText, page, error) || !page)
        { return this.HCIndexRefuse("ROUTE_INDEX_PAGE_INVALID"); }
        if (page.schema != 1 || page.kind != "gapcov-road-index-page" || page.identity_sha256 != identity.IdentitySha256)
        { return this.HCIndexRefuse("ROUTE_INDEX_PAGE_INVALID"); }
        if (!page.pages || page.pages.Count() < 1 || page.pages.Count() > 12 || page.page_start != Data.pages.Count())
        { return this.HCIndexRefuse("ROUTE_INDEX_PAGE_ORDER"); }
        foreach (HCGapcodeRoutesPageIdentity pin : page.pages)
        {
            int number = Data.pages.Count();
            if (number >= 256) { return this.HCIndexRefuse("ROUTE_INDEX_PAGE_TOTAL"); }
            string catalogSuffix = number.ToString();
            if (number < 10) { catalogSuffix = "00" + catalogSuffix; }
            else if (number < 100) { catalogSuffix = "0" + catalogSuffix; }
            string catalogPath = "$mission:hollow-country/travel/gapcov-roads/page-";
            catalogPath += catalogSuffix;
            catalogPath += ".json";
            if (!HCPageMatches(pin, pin, catalogPath)) { return this.HCIndexRefuse("ROUTE_INDEX_CATALOG_PIN"); }
            Data.pages.Insert(pin);
            m_IndexRows += pin.Rows;
        }
        m_IndexPage++;
        m_ManifestText = "";
        if (m_IndexPage < Data.index_pages.Count()) { return false; }
        if (m_IndexRows != Data.row_count) { return this.HCIndexRefuse("ROUTE_INDEX_ROW_TOTAL"); }
        m_Phase = "manifest";
        m_Reason = "ROUTE_MANIFEST_PENDING";
        return true;
    }
    void HCLoadCatalogPage()
    {
        HCGapcodeRoutesPageIdentity identity = Data.pages[m_CatalogPage];
        string content;
        if (!this.HCReadBounded(identity.Path, identity.Bytes, content) || content.Length() != identity.Bytes)
        { m_ValidityMismatch++; this.HCRefuse("ROUTE_PAGE_SIZE_OR_MISSING"); return; }
        string error;
        HCGapcodeRoutesPage page;
        if (!JsonFileLoader<HCGapcodeRoutesPage>.LoadData(content, page, error) || !page || page.schema != 1 || page.kind != "gapcov-road-page" || page.identity_sha256 != identity.IdentitySha256 || !page.routes || page.routes.Count() != identity.Rows)
        { m_ValidityMismatch++; this.HCRefuse("ROUTE_PAGE_INVALID"); return; }
        if (!HCJsonFields.Every(content, "island", 4, "road_node_ids") || !HCJsonFields.Every(content, "connected_both_directions", 4, "road_node_ids"))
        { this.HCRefuse("ROUTE_ROW_FIELDS_MISSING"); return; }
        foreach (HCGapcodeRoutesRow row : page.routes) { Data.routes.Insert(row); }
        m_CatalogRows += identity.Rows;
        m_CatalogPage++;
    }
    bool HCManifestMatches()
    {
        string text;
        if (!this.HCReadBounded("$mission:hollow-country/travel/routes-manifest.json", 6144, text)) { return false; }
        string error;
        HCGapcodeRoutesManifest manifest;
        if (!JsonFileLoader<HCGapcodeRoutesManifest>.LoadData(text, manifest, error) || !manifest) { return false; }
        if (manifest.HashPageVersion != 1 || !manifest.HashPages) { return false; }
        if (manifest.HashPages.Count() < 2 || manifest.HashPages.Count() > 32) { return false; }
        if (manifest.SchemaVersion != 1 || manifest.SourceCount != 4 || !manifest.Files || manifest.Files.Count() != 4) { return false; }
        if (manifest.SourcePagesSha256.Length() != 64 || manifest.RoadGraphSha256.Length() != 64 || manifest.ChunkBytes != 4096) { return false; }
        if (manifest.RoadGraphPath != "$mission:hollow-country/ai/road-graph.compact.json") { return false; }
        int pages = 0;
        for (int index = 0; index < 4; index++)
        {
            HCGapcodeRoutesSourceFile source = manifest.Files[index];
            if (!source || !this.HCSourcePath(index, source.Path) || source.Bytes < 1 || source.Bytes > 4194304 || source.Sha256.Length() != 64) { return false; }
            if (source.PageStart != pages || source.PageCount != (source.Bytes + 4095) / 4096) { return false; }
            pages += source.PageCount;
        }
        if (pages != manifest.PageCount || manifest.Files[0].Sha256 != Data.sources.road_sha256 || manifest.Files[0].Path != Data.sources.road_virtual_path) { return false; }
        // Retain the survey's mission-source binding on the no-hash path.
        // A partial upgrade must not silently admit routes from another bundle.
        if (manifest.Files[1].Sha256 != Data.sources.sites_sha256)
        { m_ValidityMismatch++; this.HCRefuse("ROUTE_MANIFEST_SITES_DRIFT"); return false; }
        if (manifest.Files[2].Sha256 != Data.sources.localities_sha256)
        { m_ValidityMismatch++; this.HCRefuse("ROUTE_MANIFEST_LOCALITIES_DRIFT"); return false; }
        // Native compile refuses long || chains ("Formula too complex"): one test per line.
        bool catalogOk = manifest.CatalogPath == "$mission:hollow-country/travel/gapcov-roads/index.json";
        if (catalogOk) { catalogOk = manifest.CatalogSha256.Length() == 64 && Data.identity_sha256.Length() == 64; }
        if (catalogOk) { catalogOk = manifest.CatalogIdentitySha256 == Data.identity_sha256; }
        if (!catalogOk) { m_ValidityMismatch++; this.HCRefuse("ROUTE_MANIFEST_CATALOG_DRIFT"); return false; }
        m_Manifest = manifest;
        return true;
    }
    // Each visit does one bounded read, one <=128-byte provider hash update, or
    // one <=4 KiB parse. Never combine the final hash block with JSON parsing.
    bool HCManifestPageStep()
    {
        HCGapcodeRoutesSourceFile identity = m_Manifest.HashPages[m_ManifestPage];
        string suffix = m_ManifestPage.ToString();
        if (m_ManifestPage < 10) { suffix = "00" + suffix; }
        else { suffix = "0" + suffix; }
        string expected = "$mission:hollow-country/travel/routes-manifest-";
        expected += suffix;
        expected += ".json";
        if (!identity) { this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_INVALID"); return false; }
        if (identity.Path != expected) { this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_PATH"); return false; }
        if (identity.Bytes < 1 || identity.Bytes > 4096 || identity.Sha256.Length() != 64)
        { this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_INVALID"); return false; }
        if (m_ManifestText == "")
        {
            if (!this.HCReadBounded(expected, identity.Bytes, m_ManifestText) || m_ManifestText.Length() != identity.Bytes)
            { this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_SIZE_OR_MISSING"); return false; }
            m_ManifestHash = new HCGapcodeRouteHashState;
            m_ManifestHashCursor = 0;
            m_ManifestHashVerified = false;
            return false;
        }
        if (!m_ManifestHashVerified)
        {
            int count = Math.Min(HASH_BYTES_PER_STEP, m_ManifestText.Length() - m_ManifestHashCursor);
            bool last = m_ManifestHashCursor + count == m_ManifestText.Length();
            string digest = HCGapcodeRouteHash.HCRoutePart(m_ManifestHash, m_ManifestText.Substring(m_ManifestHashCursor, count), last);
            m_ManifestHashCursor += count;
            if (!last) { return false; }
            digest.ToLower();
            if (digest != identity.Sha256) { m_ValidityMismatch++; this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_MISMATCH"); return false; }
            m_ManifestHashVerified = true;
            m_ManifestHash = null;
            return false;
        }
        string error;
        HCGapcodeRoutesManifest page;
        if (!JsonFileLoader<HCGapcodeRoutesManifest>.LoadData(m_ManifestText, page, error) || !page)
        { this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_INVALID"); return false; }
        if (page.SchemaVersion != 1 || !page.Hashes || !page.CatalogPages)
        { this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_INVALID"); return false; }
        if (page.PageStart != m_ManifestHashes || page.Hashes.Count() > 80)
        { this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_ORDER"); return false; }
        if (page.CatalogPageStart != m_ManifestCatalogPages)
        { this.HCRefuse("ROUTE_MANIFEST_CATALOG_DRIFT"); return false; }
        if (page.CatalogPages.Count() > 0)
        {
            if (page.Hashes.Count() != 0 || m_ManifestHashes != 0)
            { this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_ORDER"); return false; }
        }
        else if (page.Hashes.Count() < 1 || m_ManifestCatalogPages != Data.pages.Count())
        { this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_ORDER"); return false; }
        foreach (string hash : page.Hashes)
        {
            if (hash.Length() != 64) { this.HCRefuse("ROUTE_MANIFEST_HASH_INVALID"); return false; }
        }
        int totalRows = 0;
        for (int pageIndex = 0; pageIndex < page.CatalogPages.Count(); pageIndex++)
        {
            int catalogIndex = m_ManifestCatalogPages + pageIndex;
            if (catalogIndex >= Data.pages.Count()) { this.HCRefuse("ROUTE_MANIFEST_PAGE_DRIFT"); return false; }
            HCGapcodeRoutesPageIdentity catalogPage = Data.pages[catalogIndex];
            if (!catalogPage) { this.HCRefuse("ROUTE_MANIFEST_PAGE_DRIFT"); return false; }
            if (!HCPageMatches(catalogPage, page.CatalogPages[pageIndex], catalogPage.Path))
            { this.HCRefuse("ROUTE_MANIFEST_PAGE_DRIFT"); return false; }
            // Preserve the fixed catalog path allowlist independently of pins.
            string catalogSuffix = catalogIndex.ToString();
            if (catalogIndex < 10) { catalogSuffix = "00" + catalogSuffix; }
            else if (catalogIndex < 100) { catalogSuffix = "0" + catalogSuffix; }
            string catalogPath = "$mission:hollow-country/travel/gapcov-roads/page-";
            catalogPath += catalogSuffix;
            catalogPath += ".json";
            if (catalogPage.Path != catalogPath) { this.HCRefuse("ROUTE_MANIFEST_PAGE_DRIFT"); return false; }
            totalRows += catalogPage.Rows;
        }
        m_ManifestCatalogRows += totalRows;
        m_ManifestCatalogPages += page.CatalogPages.Count();
        m_ManifestHashes += page.Hashes.Count();
        m_ManifestPage++;
        m_ManifestText = "";
        if (m_ManifestPage < m_Manifest.HashPages.Count()) { return false; }
        if (m_ManifestHashes != m_Manifest.PageCount || m_ManifestCatalogPages != Data.pages.Count())
        { this.HCRefuse("ROUTE_MANIFEST_HASH_PAGE_TOTAL"); return false; }
        if (m_ManifestCatalogRows != Data.row_count)
        { this.HCRefuse("ROUTE_PAGE_ROW_TOTAL"); return false; }
        m_Manifest = null;
        return true;
    }
    // Split page identity checks; the native compiler rejects one long condition.
    static bool HCPageMatches(HCGapcodeRoutesPageIdentity page, HCGapcodeRoutesPageIdentity pinned, string expected)
    {
        if (!page || !pinned) { return false; }
        if (page.Path != expected) { return false; }
        if (page.Bytes < 1 || page.Bytes > 4096) { return false; }
        if (page.Rows < 1 || page.Rows > 5) { return false; }
        if (page.Sha256.Length() != 64 || page.IdentitySha256.Length() != 64) { return false; }
        if (pinned.IdentitySha256 != page.IdentitySha256 || pinned.Path != page.Path) { return false; }
        if (pinned.Bytes != page.Bytes || pinned.Rows != page.Rows) { return false; }
        return pinned.Sha256 == page.Sha256;
    }
    bool HCSourcePath(int index, string path)
    {
        if (index == 0) { return path == "DayZExpansion/AI/Scripts/Data/Roads/ChernarusPlus.roads"; }
        if (index == 1) { return path == "$mission:hollow-country/ai/sites.json"; }
        if (index == 2) { return path == "$mission:hollow-country/ai/localities.json"; }
        return index == 3 && path == "$mission:hollow-country/travel/route-surveys.json";
    }
    // Script SHA-256 used to cost about 43 ms per 4 KB page (097 boot: 765 pages, one per
    // tick, 13 minutes of hitches before AIRoles could start). Every page is still
    // read and length-checked; only the first and last page of each file are hashed,
    // plus HASH_SAMPLES strided pages of the external road source. The mission files
    // come from the repo at the build commit, and their pages cost up to 550 ms each
    // on 097, so their rows are checked by id binding below. The stride offset
    // rotates per boot, so successive boots cover different road pages. A changed
    // source changes its byte count or shifts every page after the edit.
    static const int HASH_SAMPLES = 4;
    static const int READS_PER_UNIT = 8;
    static const int HASH_BYTES_PER_STEP = 128;
    bool HCPageSampled(int page, int pages)
    {
        if (page == 0 || page == pages - 1) { return true; }
        return page % m_HashStride == m_HashOffset;
    }
    // These four sources jointly bind every regional candidate: page offsets
    // do not identify JSON rows. Refuse this catalog on drift rather than admit
    // routes against a partially trusted site/locality/road binding. Independent
    // site qualification remains owned by the site provider.
    void HCPinStep()
    {
        HCGapcodeRoutesSourceFile sourceFile = m_Pins.Files[m_FileIndex];
        int pages = sourceFile.Pages.Count();
        if (m_PageHash)
        {
            int partBytes = Math.Min(HASH_BYTES_PER_STEP, m_HashPage.Length() - m_HashCursor);
            bool lastPart = m_HashCursor + partBytes == m_HashPage.Length();
            string digest = HCGapcodeRouteHash.HCRoutePart(m_PageHash, m_HashPage.Substring(m_HashCursor, partBytes), lastPart);
            m_HashCursor += partBytes;
            if (!lastPart) { return; }
            digest.ToLower();
            m_PageHash = null;
            m_HashPage = "";
            m_HashCursor = 0;
            if (digest != sourceFile.Pages[m_PageIndex]) { this.HCRefuse("ROUTE_SOURCE_PAGE_MISMATCH", sourceFile.Path, m_PageIndex); return; }
            m_Hashed++;
            m_PageIndex++;
            return;
        }
        if (!m_PinOpen)
        {
            m_PinFile = OpenFile(sourceFile.Path, FileMode.READ);
            if (!m_PinFile) { this.HCRefuse("ROUTE_SOURCE_FILE_MISSING", sourceFile.Path, m_PageIndex); return; }
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
            if (count != expected || page.Length() != expected) { this.HCRefuse("ROUTE_SOURCE_SIZE_MISMATCH", sourceFile.Path, m_PageIndex); return; }
            m_ReadBytes += count;
            bool sampled = this.HCPageSampled(m_PageIndex, pages);
            if (sampled)
            {
                m_HashPage = page;
                m_HashCursor = 0;
                m_PageHash = new HCGapcodeRouteHashState;
                return;
            }
            m_PageIndex++;
        }
        if (m_PageIndex < pages) { return; }
        string trailing;
        if (ReadFile(m_PinFile, trailing, 1) > 0) { this.HCRefuse("ROUTE_SOURCE_TRAILING_BYTES", sourceFile.Path, m_PageIndex); return; }
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
        int count;
        m_Refusals.Find(reason, count);
        m_Refusals.Set(reason, count + 1);
        m_RefusalsDirty = true;
    }
    // One boot summary; post-load binding refusals are also flushed at stop.
    // Keys come only from the finite refusal reasons below, never mission text.
    string HCRefusalSummary()
    {
        string summary = " refusals=";
        for (int index = 0; index < m_Refusals.Count(); index++)
        {
            if (index > 0) { summary += ","; }
            summary += m_Refusals.GetKey(index) + ":" + m_Refusals.GetElement(index).ToString();
        }
        if (m_Refusals.Count() == 0) { summary += "none"; }
        m_RefusalsDirty = false;
        return summary;
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
        // Explicit offline-unresolved anchors are inventoried, never bound.
        // Retain the ordinary chain checks for malformed or unknown statuses.
        if (row.status == "anchor-runtime-resolved" && row.road_node_ids && row.road_node_ids.Count() == 0 && !row.connected_both_directions && row.route_sha256.Length() == 64)
        { this.HCRowRefuse(row, "ROUTE_ANCHOR_RUNTIME_RESOLUTION_PENDING"); return; }
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
                if (!roads.HCLinked(previousId, nodeId) || !roads.HCLinked(nodeId, previousId) || leg <= 0 || leg > Data.limits.segment_metres || length > Data.limits.journey_metres)
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
    bool HCNeedsWork() { return m_Enabled && m_Phase != "failed" && m_Phase != "loaded"; }

    HCXAICaravanRoads HCGraph()
    {
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (roads) { return roads; }
        // Open the shared reader while pinning is in progress. No candidate is
        // resolved/admitted until every original source check has completed.
        string corridorText = HCWorldStore.Read("$mission:hollow-country/ai/caravans.json");
        string corridorError;
        HCCaravanCorridor corridor;
        if (!JsonFileLoader<HCCaravanCorridor>.LoadData(corridorText, corridor, corridorError) || !corridor)
        { this.HCRefuse("ROUTE_GRAPH_CONFIG_MISSING"); return null; }
        corridor.HCApplyDefaults(corridorText);
        if (!corridor.HCNetworkValid()) { this.HCRefuse("ROUTE_GRAPH_CONFIG_INVALID"); return null; }
        HCXAICaravanRoads.HCOpen(corridor);
        m_OpenedRoadOwner = true;
        return HCXAICaravanRoads.HCGet();
    }
    void HCStep(HCXAILocalityCatalog localities, HCXAISitePolicy policy)
    {
        if (!m_Enabled || m_Phase == "failed" || m_Phase == "loaded") { return; }
        if (m_Phase == "index")
        {
            if (!HCStartupPump.HCInSlice() && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_AI_ROUTES, Data.limits.page_size)) { return; }
            m_Slices++;
            int indexBegan = TickCount(0);
            this.HCIndexPageStep();
            float indexMs = (float)TickCount(indexBegan) / HCWorkBudget.HCTicksPerMs();
            if (indexMs > m_PageMsMax) { m_PageMsMax = indexMs; }
            return;
        }
        if (m_Phase == "manifest")
        {
            if (!HCStartupPump.HCInSlice() && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_AI_ROUTES, Data.limits.page_size)) { return; }
            m_Slices++;
            int manifestBegan = TickCount(0);
            bool manifestComplete = false;
            if (!m_Manifest)
            {
                if (!this.HCManifestMatches())
                {
                    if (m_Phase != "failed") { this.HCRefuse("ROUTE_MANIFEST_MISSING_OR_INVALID"); }
                }
            }
            else { manifestComplete = this.HCManifestPageStep(); }
            float manifestMs = (float)TickCount(manifestBegan) / HCWorkBudget.HCTicksPerMs();
            if (manifestMs > m_ManifestMs) { m_ManifestMs = manifestMs; }
            if (!manifestComplete || m_Phase == "failed") { return; }
            m_ManifestAdmitted = true;
            m_Phase = "resolving";
            m_Reason = "ROUTE_GRAPH_LOADING";
            return;
        }
        // ROADS shares the startup frame budget and retains its 4 ms slice cap.
        // Pump independently of AI_ROUTES so source checks and node parsing overlap.
        bool graphWasOpen = HCXAICaravanRoads.HCGet() != null;
        int graphBegan = TickCount(0);
        HCXAICaravanRoads roads = this.HCGraph();
        if (!graphWasOpen) { m_GraphOpenMs = (float)TickCount(graphBegan) / HCWorkBudget.HCTicksPerMs(); }
        if (!roads || m_Phase == "failed" || !graphWasOpen) { return; }
        if (roads.Phase == "failed") { this.HCRefuse(roads.Reason); return; }
        if (roads.Phase == "loading" && !HCStartupPump.HCInSlice()) { roads.HCStep(); }
        // #275: the owner visits every other core tick. One row per visit
        // paced 88 cheap bindings over 176 s even after the graph was loaded
        // (131: graph 33.496 s, source checks ~71 s). Admit one bounded page,
        // charging its full cap even under starvation, and retain the cursor.
        // The same page/time cap lets cheap source reads reach the next hash
        // without waiting another two seconds per 64 reads. Never run a second
        // completed page digest in this visit or combine it with candidate work.
        int limit = Data.limits.page_size;
        if (!HCStartupPump.HCInSlice() && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_AI_ROUTES, limit)) { return; }
        // Half-slice headroom for the final non-preemptible hash block.
        m_Work.HCReset(limit, HCStartupPump.HCSliceMs(Math.Min(HCPerfConfig.HCGet().SliceMs, 2)));
        m_Slices++;
        if (m_Cursor == Data.routes.Count() && m_CatalogPage < Data.pages.Count())
        {
            // One bounded JSON page per grant, independently of row time caps.
            int pageBegan = TickCount(0);
            this.HCLoadCatalogPage();
            float pageMs = (float)TickCount(pageBegan) / HCWorkBudget.HCTicksPerMs();
            if (pageMs > m_PageMsMax) { m_PageMsMax = pageMs; }
            return;
        }
        int hashedBefore = m_Hashed;
        while (m_Work.HCContinue())
        {
            m_Units++;
            if (m_Phase == "pinning")
            {
                int pinBegan = TickCount(0);
                this.HCPinStep();
                int pinTicks = TickCount(pinBegan);
                if (pinTicks > m_PinPeakTicks)
                {
                    m_PinPeakTicks = pinTicks;
                }
                if (m_Hashed != hashedBefore || m_Phase != "pinning") { return; }
            }
            else
            {
                if (roads.Phase == "loading") { return; }
                if (roads.Phase == "failed") { this.HCRefuse(roads.Reason); return; }
                if (roads.Phase == "cold") { this.HCRefuse("ROUTE_GRAPH_NOT_OPENED"); return; }
                if (roads.Nodes.Count() != Data.graph.nodes || roads.Config.RoadDataPath != Data.sources.road_virtual_path || Data.graph.max_degree > roads.Config.MaxRoadDegree)
                { this.HCRefuse("ROUTE_GRAPH_SOURCE_MISMATCH"); return; }
                if (!localities || !localities.Localities || !policy || !policy.Sites) { m_Reason = "ROUTE_SITE_OWNER_MISSING"; return; }
                int resolveBegan = TickCount(0);
                this.HCResolve(localities, policy, roads);
                int resolveTicks = TickCount(resolveBegan);
                if (resolveTicks > m_ResolvePeakTicks) { m_ResolvePeakTicks = resolveTicks; }
                if (m_Phase == "failed") { return; }
                if (m_Cursor == Data.routes.Count() && m_CatalogRows == Data.row_count)
                {
                    m_Phase = "loaded";
                    m_Reason = "";
                    if (m_Pending > 0) { m_Reason = "ROUTE_CANDIDATES_PENDING_ACCESS_OR_BINDING"; }
                    string line = "[HC Routes] catalog=loaded candidates=" + m_Cursor.ToString();
                    line += " pending=" + m_Pending.ToString() + " page_cap=" + limit.ToString();
                    line += " manifest=" + m_ManifestAdmitted.ToString() + " validity_mismatch=" + m_ValidityMismatch.ToString();
                    line += " pin_ticks_max=" + m_PinPeakTicks.ToString();
                    line += " slices=" + m_Slices.ToString() + " units=" + m_Units.ToString();
                    float elapsed = GetGame().GetTickTime() - m_Started;
                    line += " elapsed_s=" + elapsed.ToString() + " resolve_ticks_max=" + m_ResolvePeakTicks.ToString();
                    line += " manifest_ms=" + m_ManifestMs.ToString();
                    line += " page_ms_max=" + m_PageMsMax.ToString();
                    line += " graph_open_ms=" + m_GraphOpenMs.ToString();
                    Print(line + this.HCRefusalSummary() + " runtime=PENDING");
                    return;
                }
            }
            if (m_Phase == "failed" || m_Cursor == Data.routes.Count()) { return; }
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
        else if (m_Phase == "failed") { m_Status.HCPublish("degraded", m_Reason); }
        else if (m_Phase != "loaded")
        {
            HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
            string loadingReason = "catalog_loading";
            if (!roads || roads.Phase == "cold" || roads.Phase == "loading") { loadingReason = "roads_loading"; }
            m_Status.HCPublish("degraded", loadingReason);
        }
        else if (!owner) { m_Status.HCPublish("degraded", "ROUTE_SITE_OWNER_MISSING"); }
        // Candidate-local refusals (island access, a site binding) keep every other
        // candidate running, so they are admitted coverage gaps, not an owner fault
        // (101: 4 of 88 island candidates left both AI modules degraded all boot).
        else if (m_Reason == "ROUTE_CANDIDATES_PENDING_ACCESS_OR_BINDING" && owner.HCState() == "ready")
        { m_Status.HCPublish("ready", "routes_loaded_candidates_pending_access_or_binding"); }
        else if (m_Reason != "") { m_Status.HCPublish("degraded", m_Reason); }
        else { m_Status.HCPublish(owner.HCState(), owner.HCReason()); }
        return m_Status;
    }
}
