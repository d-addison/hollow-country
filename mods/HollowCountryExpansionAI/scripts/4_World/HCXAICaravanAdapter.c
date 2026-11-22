// #145 original integration; no Expansion source/data copied or repackaged.
// Installed Expansion xref (read only):
// ai/4_World/DayZExpansion_AI/Classes/eAIGroup.c:213 AddWaypoint, :241
// ClearWaypoints, :251 SetWaypointBehaviour, :1123 IsInCombat, :1139
// GetMember, :1185 Count; Entities/DayZPlayerImplement.c:234 GetGroup.
// Roads/eAIRoadNetwork.c:678-730 and eAIRoadNode.c:281-319 document the
// installed version-4 road-file format. Its FindPath at :805 is a NO-OP and
// ExpansionWorld.c:30 does not initialise the network. We therefore read the
// provider's installed data incrementally; never call that stub or redistribute
// the data. Own BFS retains cursors, caps degrees/nodes/path and charges work.
// Native scripts-1.30.164289: EnSystem.c:417/443/501 OpenFile/CloseFile/FGets;
// EnString.c:199/20/59 Length/ToInt/ToVector; Global/Game.c:1120 IsServer;
// Object.c:287 GetPosition; EnConvert.c:210/196 DistanceSq/Distance; EnScript.c:380/407
// arrays Count/Insert. Inherited item/actor calls are cited by HCTradeInventory.
// Timing API inspected in scripts-1.30.164289: EnSystem.c:106 TickCount;
// 3_Game/Global/Game.c:914 GetTickTime, :1535 GetTime.
// All walking/geometry/arrival/loot/replication acceptance remains runtime=PENDING.
class HCXRoadVisit
{
    int Parent = -1;
    float Cost;
    float Score;
    int Heap = -1;
    bool Closed;
}

// One candidate per step; only the nine cells around the query are visited.
class HCXRoadNearest
{
    vector Position;
    float Gap;
    int Best = -1;
    int Cell;
    int Offset;

    void HCStart(vector position, float radius)
    {
        Position = position;
        Gap = radius * radius;
        Best = -1;
        Cell = 0;
        Offset = 0;
    }

    bool HCStep(HCXAICaravanRoads roads)
    {
        if (Cell >= 9) { return true; }
        int x = Math.Floor(Position[0] / HCXAICaravanRoads.HC_CELL_METERS);
        int z = Math.Floor(Position[2] / HCXAICaravanRoads.HC_CELL_METERS);
        int dx = Cell % 3 - 1;
        int dz = Cell / 3 - 1;
        array<int> bucket = roads.Grid.Get(roads.HCGridKey(x + dx, z + dz));
        if (!bucket || Offset >= bucket.Count()) { Cell++; Offset = 0; return false; }
        int node = bucket[Offset];
        Offset++;
        float gap = HCXConvoyRoute.HCFlatSq(Position, roads.Nodes[node].Position);
        if (gap <= Gap) { Gap = gap; Best = node; }
        return false;
    }
}

class HCXAICaravanRoadNode
{
    vector Position;
    ref array<int> Links = new array<int>;
    // Compatibility view for HCXConvoyRoute; no per-node map allocation.
}
class HCStartupRoads : HCStartupOwner
{
    HCXAICaravanRoads Roads;
    override bool HCNeedsWork() { return Roads && Roads.Phase == "loading"; }
    override void HCSlice() { if (Roads && Roads.Phase == "loading") { Roads.HCLoadFrame(0); } }
}

class HCXAICaravanRoads : Managed
{
    protected static ref HCXAICaravanRoads s_Instance;
    protected ref HCStartupRoads m_StartupRoads;
    ref HCCaravanCorridor Config;
    ref array<ref HCXAICaravanRoadNode> Nodes = new array<ref HCXAICaravanRoadNode>;
    static const float HC_CELL_METERS = 250;
    ref map<int, ref array<int>> Grid = new map<int, ref array<int>>;
    ref HCXConvoyRoute Planner = new HCXConvoyRoute;
    ref array<vector> Path = new array<vector>;
    string Phase = "cold";
    string Reason;
    FileHandle m_File;
    // FileHandle is typedef int[]: it compares with 0 but cannot be assigned 0.
    bool m_FileOpen;
    int m_Count;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    // Loading retains one line cursor and yields through the shared deadline.
    protected ref HCXAICaravanRoadNode m_LoadNode;
    protected int m_LoadField;
    protected int m_LoadDegree;
    protected int m_LoadEdge;
    protected int m_LoadTick = -1;
    protected int m_LoadSlices;
    protected int m_LoadTicks;
    protected int m_LoadMaxTicks;
    protected float m_LoadStarted;
    protected bool m_Compact;
    protected bool m_CompactHeaderRead;
    protected bool m_CompactProject;
    protected string m_ReadWindow;
    protected int m_ReadCursor;
    protected bool m_WindowEof;
    protected bool m_InstalledPending;
    protected bool m_InstalledHeader;
    // One ReadFile of this many bytes per visit refills the parse window; a unit of
    // parsing (a token, the compact tail, an installed header) consumes well under
    // HC_WINDOW_LOW bytes, so the parse never reads and never straddles a refill.
    static const int HC_WINDOW_BYTES = 4096;
    static const int HC_WINDOW_LOW = 1152;
    static const int HC_WINDOW_MAX = 5248;
    static const int HC_INSTALLED_BYTES = 67108864;
    protected int m_WindowBracket = -1;
    protected int m_CompactBytes;
    protected int m_CompactArray;
    protected int m_ArrayValues;
    protected bool m_ExpectValue = true;
    protected bool m_StreamFault;
    protected int m_ProjectCursor;
    protected int m_EdgeCount;
    protected int m_ValidityMismatch;
    // CSR data stays flat. Existing convoy consumers require the bounded Links
    // view; build that view on the same pump rather than allocating node maps.
    protected ref array<int> m_Offsets = new array<int>;
    protected ref array<int> m_Edges = new array<int>;
    protected ref HCGapcodeRoutesManifest m_Manifest;
    float m_Length;
    vector From;
    vector To;

    static HCXAICaravanRoads HCGet() { return s_Instance; }
    static void HCOpen(HCCaravanCorridor config)
    {
        if (s_Instance || !config) { return; }
        s_Instance = new HCXAICaravanRoads;
        s_Instance.Config = config;
        s_Instance.HCLoad();
    }
    static void HCClose()
    {
        if (s_Instance) { s_Instance.HCStopLoading(); }
        if (s_Instance && s_Instance.m_FileOpen) { CloseFile(s_Instance.m_File); s_Instance.m_FileOpen = false; }
        s_Instance = null;
    }
    // Next installed-source line from the prefetched window (no native call): at
    // most 96 bytes, a CR before the newline is dropped, a last line may lack a newline.
    // An empty line is refused (it is a torn or corrupt record, never a value) except
    // for the provider flags field, whose content this reader never uses.
    string HCLine(bool allowEmpty = false)
    {
        int end = -1;
        if (m_FileOpen && m_ReadCursor < m_ReadWindow.Length()) { end = m_ReadWindow.IndexOfFrom(m_ReadCursor, "\n"); }
        if (end < 0 && m_FileOpen && m_WindowEof && m_ReadCursor < m_ReadWindow.Length()) { end = m_ReadWindow.Length(); }
        if (end < 0 || end - m_ReadCursor > 97)
        {
            HCRefuse("CARAVAN_ROAD_DATA_TRUNCATED");
            return "";
        }
        string line = m_ReadWindow.Substring(m_ReadCursor, end - m_ReadCursor);
        m_ReadCursor = end + 1;
        if (line.Length() > 0 && line.Get(line.Length() - 1) == "\r") { line = line.Substring(0, line.Length() - 1); }
        if (line.Length() > 96)
        {
            HCRefuse("CARAVAN_ROAD_DATA_TRUNCATED");
            return "";
        }
        if (line.Length() == 0 && !allowEmpty)
        {
            HCRefuse("CARAVAN_ROAD_DATA_EMPTY_LINE");
            return "";
        }
        return line;
    }
    // Native Game.c:1552 / DayZGame.c:3027: SYSTEM update invokes timeslice
    // every server frame, independently of the one-second core module cadence.
    void HCLoadFrame(float timeslice)
    {
        if (Phase == "loading") { HCStep(true); }
    }
    void HCStopLoading()
    {
        HCStartupPump.HCFinish(m_StartupRoads);
    }
    void HCRefuse(string reason)
    {
        HCStopLoading();
        m_LoadNode = null;
        Phase = "failed";
        if (m_FileOpen) { CloseFile(m_File); m_FileOpen = false; }
        if (Reason == reason) { return; }
        Reason = reason;
        Print("[HC Caravan] roads=unavailable reason=" + reason + " runtime=PENDING");
    }
    void HCLoad()
    {
        m_LoadStarted = GetGame().GetTickTime();
        string manifestText = HCWorldStore.Read("$mission:hollow-country/travel/routes-manifest.json");
        string manifestError;
        if (JsonFileLoader<HCGapcodeRoutesManifest>.LoadData(manifestText, m_Manifest, manifestError) && m_Manifest && m_Manifest.SchemaVersion == 1 && m_Manifest.Files && m_Manifest.Files.Count() == 4 && m_Manifest.Files[0])
        {
            if (m_Manifest.RoadGraphPath == "$mission:hollow-country/ai/road-graph.compact.json" && m_Manifest.RoadGraphSha256.Length() == 64 && m_Manifest.Files[0].Path == Config.RoadDataPath)
            {
                m_File = OpenFile(m_Manifest.RoadGraphPath, FileMode.READ);
                if (m_File)
                {
                    m_FileOpen = true;
                    m_Compact = true;
                    this.HCStartLoading();
                    return;
                }
            }
        }
        this.HCCompactFallback();
    }
    // Installed-source header: four lines from the prefetched window, one loop unit.
    void HCLoadInstalledHeader()
    {
        string version = HCLine();
        string width = HCLine();
        string height = HCLine();
        string count = HCLine();
        m_Count = count.ToInt();
        if (Phase == "failed") { return; }
        if (version.ToInt() != 4 || width.ToInt() != Config.RoadMapWidth || height.ToInt() != Config.RoadMapHeight || m_Count < 1 || m_Count > Config.MaxRoadNodes)
        {
            HCRefuse("CARAVAN_ROAD_DATA_HEADER_INVALID"); return;
        }
        m_InstalledHeader = true;
    }
    bool HCWindowLow()
    {
        return m_FileOpen && !m_WindowEof && m_ReadWindow.Length() - m_ReadCursor < HC_WINDOW_LOW;
    }
    // At most ONE native file call per visit, ahead of the parse loop: the deferred
    // open of the installed source, else one window refill. The parse loop itself
    // never reads; it stops at the low-water mark and the next visit refills.
    void HCStepIO()
    {
        if (m_InstalledPending)
        {
            m_InstalledPending = false;
            m_File = OpenFile(Config.RoadDataPath, FileMode.READ);
            if (m_File == 0) { HCRefuse("CARAVAN_INSTALLED_ROAD_DATA_MISSING"); return; }
            m_FileOpen = true;
            return;
        }
        if (!this.HCWindowLow()) { return; }
        // Keep the unparsed tail (below the low-water mark) and append one read.
        int remaining = m_ReadWindow.Length() - m_ReadCursor;
        if (remaining > HC_WINDOW_LOW) { HCRefuse("CARAVAN_ROAD_DATA_TRUNCATED"); return; }
        if (remaining > 0) { m_ReadWindow = m_ReadWindow.Substring(m_ReadCursor, remaining); }
        else { m_ReadWindow = ""; }
        m_ReadCursor = 0;
        string chunk;
        int bytes = ReadFile(m_File, chunk, HC_WINDOW_BYTES);
        m_CompactBytes += bytes;
        // The compact road graph's cap is the literal below: the loader-cap gate
        // (tools/validate/json_loader_caps) reads it from this comparison.
        bool overCap = m_CompactBytes > HC_INSTALLED_BYTES;
        if (m_Compact) { overCap = m_CompactBytes > 4194304; }
        if (bytes < 0 || bytes != chunk.Length() || overCap)
        {
            if (m_Compact) { this.HCCompactFallback(); }
            else { HCRefuse("CARAVAN_ROAD_DATA_TRUNCATED"); }
            return;
        }
        if (bytes == 0) { m_WindowEof = true; }
        m_ReadWindow = m_ReadWindow + chunk;
        // Scan once per window; the large Positions array has no closing
        // bracket in most windows. Repeating this per token was quadratic.
        m_WindowBracket = m_ReadWindow.IndexOfFrom(0, "]");
    }
    void HCStartLoading()
    {
        Phase = "loading";
        if (m_StartupRoads) { return; }
        m_StartupRoads = new HCStartupRoads;
        m_StartupRoads.Roads = this;
        HCStartupPump.HCRegister(m_StartupRoads, "road_graph");
    }
    void HCCompactFallback()
    {
        if (m_FileOpen) { CloseFile(m_File); m_FileOpen = false; }
        m_Compact = false;
        m_ValidityMismatch++;
        // This is a downgrade to installed-source validation, never a cache hit.
        Print("[HC Caravan] compact=fallback reason=validity_mismatch count=" + m_ValidityMismatch.ToString() + " runtime=PENDING");
        Nodes.Clear();
        Grid.Clear();
        m_Offsets.Clear();
        m_Edges.Clear();
        m_CompactHeaderRead = false;
        m_CompactProject = false;
        m_ReadWindow = "";
        m_ReadCursor = 0;
        m_WindowBracket = -1;
        m_CompactBytes = 0;
        m_CompactArray = 0;
        m_ArrayValues = 0;
        m_ExpectValue = true;
        m_StreamFault = false;
        m_ProjectCursor = 0;
        m_EdgeCount = 0;
        m_Count = 0;
        m_LoadDegree = 0;
        m_LoadEdge = 0;
        m_LoadTick = -1;
        m_LoadField = 0;
        m_LoadNode = null;
        m_WindowEof = false;
        m_InstalledHeader = false;
        // The installed source opens on a later visit (HCStepIO), never inside the parse loop.
        m_InstalledPending = true;
        this.HCStartLoading();
    }
    // Native EnSystem.c:425 ReadFile (HCStepIO), EnString.c:448 Get. The parse reads
    // the prefetched window only: no whole-file character scans or growing image.
    // "" means end of the stream (or window), exactly as the old zero-byte read.
    string HCStreamAt()
    {
        if (m_ReadCursor >= m_ReadWindow.Length()) { return ""; }
        return m_ReadWindow.Get(m_ReadCursor);
    }
    // Canonical generated JSON contains no escapes or whitespace in tokens.
    // Each token is capped at 96 bytes; a token crossing windows stays bounded.
    string HCStreamToken()
    {
        string token;
        bool quoted = false;
        for (int index = 0; index < 98; index++)
        {
            string character = this.HCStreamAt();
            if (character == "") { return token; }
            if (token == "" && (character == " " || character == "\n" || character == "\r" || character == "\t"))
            { m_ReadCursor++; continue; }
            if (character == "\\") { m_StreamFault = true; return ""; }
            if (!quoted && (character == "," || character == ":" || character == "[" || character == "]" || character == "{" || character == "}"))
            {
                if (token != "") { return token; }
                m_ReadCursor++;
                return character;
            }
            if (!quoted && token != "" && (character == " " || character == "\n" || character == "\r" || character == "\t")) { return token; }
            token += character;
            m_ReadCursor++;
            if (character == "\"")
            {
                if (quoted) { return token; }
                if (token.Length() != 1) { m_StreamFault = true; return ""; }
                quoted = true;
            }
            if (token.Length() > 96) { m_StreamFault = true; return ""; }
        }
        m_StreamFault = true;
        return "";
    }
    string HCStreamArrayToken()
    {
        // Native EnString.c:271 IndexOfFrom. Scan delimiters in C++ on a
        // bounded window instead of visiting every numeric character in script.
        string token;
        for (int part = 0; part < 2; part++)
        {
            string first = this.HCStreamAt();
            if (first == "" || m_StreamFault || m_ReadWindow.Length() > HC_WINDOW_MAX) { return ""; }
            int stop = m_ReadWindow.IndexOfFrom(m_ReadCursor, ",");
            if (m_WindowBracket >= 0 && m_WindowBracket < m_ReadCursor)
            { m_WindowBracket = m_ReadWindow.IndexOfFrom(m_ReadCursor, "]"); }
            int bracket = m_WindowBracket;
            if (stop < 0 || (bracket >= 0 && bracket < stop)) { stop = bracket; }
            if (stop == m_ReadCursor)
            {
                if (token != "") { return token; }
                m_ReadCursor++;
                return first;
            }
            int end = stop;
            if (end < 0) { end = m_ReadWindow.Length(); }
            int length = end - m_ReadCursor;
            if (length < 1 || length + token.Length() > 32) { m_StreamFault = true; return ""; }
            token += m_ReadWindow.Substring(m_ReadCursor, length);
            m_ReadCursor = end;
            if (stop >= 0) { return token; }
        }
        m_StreamFault = true;
        return "";
    }
    bool HCFloatToken(string token)
    {
        // Strict JSON number grammar on <=32 bytes, including exponent digits.
        if (token == "" || token.Length() > 32) { return false; }
        int cursor = 0;
        if (token.Get(0) == "-") { cursor++; }
        int digits = 0;
        bool zero = false;
        if (cursor < token.Length()) { zero = token.Get(cursor) == "0"; }
        while (cursor < token.Length())
        {
            int ascii = token.Get(cursor).ToAscii();
            if (ascii < 48 || ascii > 57) { break; }
            cursor++; digits++;
        }
        if (digits == 0 || (zero && digits > 1)) { return false; }
        if (cursor < token.Length() && token.Get(cursor) == ".")
        {
            cursor++;
            digits = 0;
            while (cursor < token.Length())
            {
                int fraction = token.Get(cursor).ToAscii();
                if (fraction < 48 || fraction > 57) { break; }
                cursor++; digits++;
            }
            if (digits == 0) { return false; }
        }
        if (cursor < token.Length() && (token.Get(cursor) == "e" || token.Get(cursor) == "E"))
        {
            cursor++;
            if (cursor < token.Length() && (token.Get(cursor) == "+" || token.Get(cursor) == "-")) { cursor++; }
            digits = 0;
            while (cursor < token.Length())
            {
                int exponent = token.Get(cursor).ToAscii();
                if (exponent < 48 || exponent > 57) { break; }
                cursor++; digits++;
            }
            if (digits == 0) { return false; }
        }
        return cursor == token.Length() && HCXAIRules.Finite(token.ToFloat());
    }
    bool HCCompactHeader()
    {
        // The small prefix ends at Positions; reconstruct only the header DTO.
        string prefix;
        for (int index = 0; index < 1024; index++)
        {
            string character = this.HCStreamAt();
            if (character == "" || m_StreamFault) { return false; }
            m_ReadCursor++;
            if (character == "[") { break; }
            prefix += character;
        }
        string suffix = ",\"Positions\":";
        if (prefix.Length() < suffix.Length() || prefix.Substring(prefix.Length() - suffix.Length(), suffix.Length()) != suffix) { return false; }
        prefix = prefix.Substring(0, prefix.Length() - suffix.Length()) + "}";
        string error;
        HCXRoadCompactHeader header;
        if (!JsonFileLoader<HCXRoadCompactHeader>.LoadData(prefix, header, error) || !header) { return false; }
        if (header.SchemaVersion != 1 || header.SourcePath != Config.RoadDataPath || header.SourceSha256 != m_Manifest.Files[0].Sha256 || header.SourceSha256.Length() != 64) { return false; }
        if (header.RoadVersion != 4 || header.Width != Config.RoadMapWidth || header.Height != Config.RoadMapHeight) { return false; }
        if (header.NodeCount < 1 || header.NodeCount > Config.MaxRoadNodes || header.EdgeCount < 0 || header.EdgeCount > header.NodeCount * Config.MaxRoadDegree) { return false; }
        m_Count = header.NodeCount;
        m_EdgeCount = header.EdgeCount;
        m_CompactHeaderRead = true;
        return true;
    }
    bool HCCompactNumber(string token)
    {
        if (token == "" || token.Length() > 32) { return false; }
        if (m_CompactArray == 0 && !this.HCFloatToken(token)) { return false; }
        for (int index = 0; index < token.Length(); index++)
        {
            string character = token.Get(index);
            int ascii = character.ToAscii();
            if (ascii >= 48 && ascii <= 57) { continue; }
            if (m_CompactArray == 0 && (character == "." || character == "-" || character == "+" || character == "e" || character == "E")) { continue; }
            if (m_CompactArray == 1 && index == 0 && character == "-") { continue; }
            return false;
        }
        int value = token.ToInt();
        if (m_CompactArray != 0 && value.ToString() != token) { return false; }
        if (m_CompactArray == 0)
        {
            if (m_ArrayValues >= m_Count * 3) { return false; }
            if (m_ArrayValues % 3 == 0)
            {
                // Compact IDs are implicit: XYZ triple i must publish node i.
                if (m_ArrayValues / 3 != Nodes.Count()) { return false; }
                m_LoadNode = new HCXAICaravanRoadNode;
            }
            m_LoadNode.Position[m_ArrayValues % 3] = token.ToFloat();
            if (m_ArrayValues % 3 == 2)
            {
                if (!HCWorldLimits.Position(m_LoadNode.Position)) { return false; }
                Nodes.Insert(m_LoadNode);
                m_LoadNode = null;
            }
        }
        else if (m_CompactArray == 1) { if (m_ArrayValues >= m_Count) { return false; } }
        else if (m_CompactArray == 2)
        {
            if (m_ArrayValues > m_Count || value < 0 || value > m_EdgeCount) { return false; }
            if (m_ArrayValues == 0 && value != 0) { return false; }
            if (m_ArrayValues > 0 && (value < m_Offsets[m_ArrayValues - 1] || value - m_Offsets[m_ArrayValues - 1] > Config.MaxRoadDegree)) { return false; }
            m_Offsets.Insert(value);
        }
        else
        {
            if (m_ArrayValues >= m_EdgeCount || value < 0 || value >= m_Count) { return false; }
            m_Edges.Insert(value);
        }
        m_ArrayValues++;
        m_ExpectValue = false;
        return true;
    }
    bool HCCompactArrayEnd()
    {
        int expected = m_Count * 3;
        string next = "\"Flags\"";
        if (m_CompactArray == 1) { expected = m_Count; next = "\"Offsets\""; }
        if (m_CompactArray == 2) { expected = m_Count + 1; next = "\"Edges\""; }
        if (m_CompactArray == 3) { expected = m_EdgeCount; }
        if (m_ArrayValues != expected || (m_ArrayValues > 0 && m_ExpectValue)) { return false; }
        if (m_CompactArray == 3)
        {
            if (m_Offsets[m_Count] != m_EdgeCount) { return false; }
            if (this.HCStreamToken() != "," || this.HCStreamToken() != "\"Runtime\"" || this.HCStreamToken() != ":" || this.HCStreamToken() != "\"PENDING\"" || this.HCStreamToken() != "}" || this.HCStreamToken() != "" || m_StreamFault) { return false; }
            CloseFile(m_File); m_FileOpen = false;
            m_ReadWindow = "";
            m_CompactProject = true;
            return true;
        }
        if (this.HCStreamToken() != "," || this.HCStreamToken() != next || this.HCStreamToken() != ":" || this.HCStreamToken() != "[") { return false; }
        m_CompactArray++;
        m_ArrayValues = 0;
        m_ExpectValue = true;
        return true;
    }
    void HCLoadCompact()
    {
        if (!m_CompactHeaderRead)
        {
            if (!this.HCCompactHeader()) { this.HCCompactFallback(); }
            return;
        }
        if (m_CompactProject)
        {
            HCXAICaravanRoadNode node = Nodes[m_ProjectCursor];
            int end = m_Offsets[m_ProjectCursor + 1];
            for (int edge = m_Offsets[m_ProjectCursor]; edge < end; edge++) { node.Links.Insert(m_Edges[edge]); }
            this.HCIndexNode(node, m_ProjectCursor);
            m_ProjectCursor++;
            if (m_ProjectCursor == m_Count)
            {
                Phase = "idle";
                this.HCStopLoading();
            }
            return;
        }
        string token = this.HCStreamArrayToken();
        if (m_StreamFault) { this.HCCompactFallback(); return; }
        if (token == "]")
        {
            if (!this.HCCompactArrayEnd()) { this.HCCompactFallback(); }
        }
        else if (!m_ExpectValue && token == ",") { m_ExpectValue = true; }
        else if (!m_ExpectValue || !this.HCCompactNumber(token)) { this.HCCompactFallback(); }
    }
    void HCIndexNode(HCXAICaravanRoadNode node, int index)
    {
        int x = Math.Floor(node.Position[0] / HC_CELL_METERS);
        int z = Math.Floor(node.Position[2] / HC_CELL_METERS);
        int key = HCGridKey(x, z);
        array<int> bucket = Grid.Get(key);
        if (!bucket)
        {
            bucket = new array<int>;
            Grid.Set(key, bucket);
        }
        bucket.Insert(index);
    }
    void HCLoadNode()
    {
        // One file line per unit, including each edge. A high-degree node can
        // no longer consume an entire slice without a shared deadline check.
        string value = HCLine(m_LoadField == 2);
        if (Phase == "failed") { return; }
        if (m_LoadField == 0)
        {
            if (value.ToInt() != Nodes.Count()) { HCRefuse("CARAVAN_ROAD_NODE_INVALID"); return; }
            m_LoadNode = new HCXAICaravanRoadNode;
        }
        else if (m_LoadField == 1)
        {
            m_LoadNode.Position = value.ToVector();
            if (!HCWorldLimits.Position(m_LoadNode.Position)) { HCRefuse("CARAVAN_ROAD_POSITION_INVALID"); return; }
        }
        // Field 2 is the provider's flags, as before.
        else if (m_LoadField == 3)
        {
            m_LoadDegree = value.ToInt();
            m_LoadEdge = 0;
            if (m_LoadDegree < 0 || m_LoadDegree > Config.MaxRoadDegree) { HCRefuse("CARAVAN_ROAD_NODE_INVALID"); return; }
        }
        else if (m_LoadField == 4)
        {
            int target = value.ToInt();
            if (target < 0 || target >= m_Count) { HCRefuse("CARAVAN_ROAD_LINK_INVALID"); return; }
            m_LoadNode.Links.Insert(target);
            m_LoadEdge++;
        }
        if (m_LoadField < 4) { m_LoadField++; }
        if (m_LoadField == 4 && m_LoadEdge == m_LoadDegree)
        {
            this.HCIndexNode(m_LoadNode, Nodes.Count());
            Nodes.Insert(m_LoadNode);
            m_LoadNode = null;
            m_LoadField = 0;
            if (Nodes.Count() == m_Count)
            {
                CloseFile(m_File); m_FileOpen = false;
                HCStopLoading();
                Phase = "idle";
            }
        }
    }
    bool HCLinked(int source, int target)
    {
        // Degree is bounded by Config.MaxRoadDegree (8 in the shipped graph).
        return Nodes[source].Links.Find(target) >= 0;
    }
    // World limits keep cell coordinates below 1,024; offset covers edge queries.
    int HCGridKey(int x, int z) { return (x + 1) * 1024 + z + 1; }

    HCConvoyPolicy HCWalkingPolicy()
    {
        HCConvoyPolicy policy = new HCConvoyPolicy;
        policy.RoadNodesPerTick = Config.RoadWorkPerTick;
        policy.RoadNodesPerWorkUnit = Config.RoadNodesPerWorkUnit;
        policy.MaxPlanNodes = Config.MaxRoadNodes;
        policy.MaxApproachMeters = Config.MaxApproachMeters;
        policy.MaxRouteNodes = Config.MaxRouteNodes;
        policy.MaxDriveMeters = Config.MaxJourneyMeters;
        policy.MinDriveMeters = 0;
        policy.DismountMeters = 0;
        policy.DetourMeters = Config.MaxJourneyMeters;
        return policy;
    }

    bool HCPlan(vector origin, vector destination)
    {
        if (Phase == "cold" || Phase == "loading" || Phase == "failed") { return false; }
        From = origin;
        To = destination;
        Path.Clear();
        Reason = "";
        HCConvoyPolicy policy = HCWalkingPolicy();
        if (!Planner.HCPlan(origin, destination, policy, true)) { Reason = Planner.mHCReason; return false; }
        Phase = "planning";
        return true;
    }
    void HCStep(bool loadFrame = false)
    {
        if (Phase == "idle" || Phase == "ready" || Phase == "failed") { return; }
        if (Phase == "planning")
        {
            Planner.HCStep();
            if (Planner.mHCPhase == "failed") { Phase = "idle"; Reason = Planner.mHCReason; }
            else if (Planner.mHCPhase == "ready")
            {
                // Caravan contract retains destination -> source order.
                for (int index = Planner.mHCPath.Count() - 1; index >= 0; index--) { Path.Insert(Planner.mHCPath[index]); }
                m_Length = Planner.mHCLength;
                if (m_Length > Config.MaxJourneyMeters) { Path.Clear(); Phase = "idle"; Reason = "CARAVAN_ROUTE_LENGTH_CAP"; }
                else { Phase = "ready"; }
            }
            return;
        }
        if (Phase == "loading" && !loadFrame && m_StartupRoads && !m_StartupRoads.Finished) { return; }
        if (Phase == "loading" && !loadFrame)
        {
            if (m_LoadTick == GetGame().GetTime()) { return; }
            m_LoadTick = GetGame().GetTime();
        }
        // Normal visits retain ROADS admission. Catch-up uses the shared frame
        // deadline instead; the same line/unit and elapsed slice caps remain.
        if (!HCStartupPump.HCInSlice() && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_ROADS, 1)) { return; }
        bool loading = Phase == "loading";
        int limit = Config.RoadWorkPerTick;
        if (loading)
        {
            // Shared frame pump during catch-up; one normal tick visit after
            // its deadline/opt-out. Keep the same line/unit ceiling.
            limit = Math.Min(limit * 64, 32768);
        }
        int began = TickCount(0);
        // Reserve headroom below the 8 ms target; native calls are cooperative.
        if (loading) { m_Work.HCReset(limit, HCStartupPump.HCSliceMs(Math.Min(HCPerfConfig.HCGet().SliceMs, 4))); }
        else { m_Work.HCReset(limit); }
        // The only native file call of the visit (open or one window refill), before the loop.
        if (loading) { this.HCStepIO(); }
        int unit = 0;
        for (unit = 0; unit < limit; unit++)
        {
            if (Phase != "loading" || m_InstalledPending || this.HCWindowLow()) { break; }
            if (!m_Work.HCContinue()) { break; }
            if (m_Compact) { this.HCLoadCompact(); }
            else if (!m_InstalledHeader) { this.HCLoadInstalledHeader(); }
            else { HCLoadNode(); }
        }
        if (loading)
        {
            int ticks = TickCount(began);
            m_LoadSlices++;
            m_LoadTicks += ticks;
            if (ticks > m_LoadMaxTicks) { m_LoadMaxTicks = ticks; }
            if (Phase == "idle")
            {
                float elapsed = GetGame().GetTickTime() - m_LoadStarted;
                string source = "installed_expansion";
                if (m_Compact) { source = "compact_manifest"; }
                string line = "[HC Caravan] roads=loaded source=" + source + " nodes=" + Nodes.Count().ToString();
                line += " validity_mismatch=" + m_ValidityMismatch.ToString();
                line += " slices=" + m_LoadSlices.ToString() + " elapsed_s=" + elapsed.ToString();
                line += " ticks_sum=" + m_LoadTicks.ToString() + " ticks_max=" + m_LoadMaxTicks.ToString();
                Print(line + " route_acceptance=unverified runtime=PENDING");
            }
        }
    }
}

class HCXAICaravanAdapter : HCCaravanInventory
{
    vector m_From;
    vector m_To;
    string m_Lease;
    ref array<vector> m_Original = new array<vector>;
    int m_Behaviour;
    ref array<vector> m_PartnerOriginal = new array<vector>;
    int m_PartnerBehaviour;
    ref HCXAITradeAdapter m_StockReader;
    ref HCXAIStuckRecovery m_Recovery = new HCXAIStuckRecovery;
    // #334: the caravan and its partner party are reached only through these bridge handles.
    protected ref HCXAIGroupHold m_HCHold;
    protected ref HCXAIGroupHold m_HCPartnerHold;

    void ~HCXAICaravanAdapter()
    {
        HCXAIGroupHolds.Retire(m_HCHold);
        HCXAIGroupHolds.Retire(m_HCPartnerHold);
    }

    override bool HCReady()
    {
        if (!GetGame() || !GetGame().IsServer() || !HCXAIQualification.EncountersEnabled()) { return false; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        return director && director.Phase() == "run" && roads && roads.Phase != "failed" && roads.Phase != "loading";
    }
    override string HCOperationalFault()
    {
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (roads && roads.Phase == "failed") { return roads.Reason; }
        if (m_Recovery.GivenUp) { return m_Recovery.Reason; }
        return "";
    }
    override string HCRefusal() { return "CARAVAN_WAITING_FUNDED_ROAD_PAIR"; }

    // Same qualified existing group; never CreateGroup/CreateObject/teleport.
    bool HCPrepare(string lease, PlayerBase carrier, vector destination)
    {
        eAIBase actor = eAIBase.Cast(carrier);
        if (!HCReady() || !actor || !HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor) || HCXExpansionBridge.HCBaseGetIdentity(actor)) { return false; }
        m_Recovery = new HCXAIStuckRecovery;
        m_Lease = lease;
        m_HCHold = HCXAIGroupHolds.Follow(m_HCHold, HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor));
        if (!m_HCHold) { return false; }
        LeftActor = actor;
        m_From = HCXExpansionBridge.HCBaseGetPosition(actor); m_To = destination;
        m_Original.Clear();
        array<vector> original = HCXExpansionBridge.HCHoldGetWaypoints(m_HCHold);
        if (original.Count() > Corridor.MaxRouteNodes) { return false; }
        foreach (vector point : original) { m_Original.Insert(point); }
        m_Behaviour = HCXExpansionBridge.HCHoldGetWaypointBehaviour(m_HCHold);
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        return roads.HCPlan(m_From, m_To);
    }
    bool HCHoldPartner(PlayerBase partner)
    {
        eAIBase actor = eAIBase.Cast(partner);
        if (!actor || !HCXExpansionBridge.HCBaseIsAlive(actor) || !HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor) || HCXExpansionBridge.HCHoldSame(m_HCHold, HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor)) || HCXExpansionBridge.HCGroupIsInCombat(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor))) { return false; }
        eAIGroup partnerGroup = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor);
        array<vector> waypoints = HCXExpansionBridge.HCGroupGetWaypoints(partnerGroup);
        if (waypoints.Count() > Corridor.MaxRouteNodes) { return false; }
        m_HCPartnerHold = HCXAIGroupHolds.Follow(m_HCPartnerHold, partnerGroup);
        if (!m_HCPartnerHold) { return false; }
        m_PartnerOriginal.Clear();
        foreach (vector waypoint : waypoints) { m_PartnerOriginal.Insert(waypoint); }
        m_PartnerBehaviour = HCXExpansionBridge.HCHoldGetWaypointBehaviour(m_HCPartnerHold);
        m_To = HCXExpansionBridge.HCBaseGetPosition(actor);
        HCXExpansionBridge.HCHoldClearWaypoints(m_HCPartnerHold);
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(m_HCPartnerHold, eAIWaypointBehavior.HALT);
        HCXExpansionBridge.HCHoldAddWaypoint(m_HCPartnerHold, m_To);
        return true;
    }
    void HCReleasePartner()
    {
        if (!m_HCPartnerHold || HCXExpansionBridge.HCHoldIsInCombat(m_HCPartnerHold)) { return; }
        HCXExpansionBridge.HCHoldClearWaypoints(m_HCPartnerHold);
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(m_HCPartnerHold, m_PartnerBehaviour);
        array<vector> waypoints = m_PartnerOriginal;
        foreach (vector waypoint : waypoints) { HCXExpansionBridge.HCHoldAddWaypoint(m_HCPartnerHold, waypoint); }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (director) { director.HCResetPartyJourney(m_HCPartnerHold); }
        HCXAIGroupHolds.Retire(m_HCPartnerHold);
        m_HCPartnerHold = null;
    }

    // eAIGroup.c:222 GetWaypoints, :304 GetWaypointBehaviour. Restore the
    // existing owner's route only after real home arrival, never force position.
    bool HCRestoreRoute()
    {
        HCReleasePartner();
        if (!m_HCHold) { return true; }
        if (HCXExpansionBridge.HCHoldIsInCombat(m_HCHold)) { return false; }
        HCXExpansionBridge.HCHoldClearWaypoints(m_HCHold);
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(m_HCHold, m_Behaviour);
        array<vector> original = m_Original;
        foreach (vector point : original) { HCXExpansionBridge.HCHoldAddWaypoint(m_HCHold, point); }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (director) { director.HCResetPartyJourney(m_HCHold); }
        return true;
    }
    bool HCRequest(bool returning)
    {
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (!HCReady() || !HCXExpansionBridge.HCHoldAlive(m_HCHold) || HCXExpansionBridge.HCHoldIsInCombat(m_HCHold) || !roads || roads.Phase != "ready") { return false; }
        // Path is destination -> source. Installed Expansion
        // eAIState_TraversingWaypoints treats HALT as final at the CURRENT
        // waypoint, so multi-point paths use ONCE, which advances to the last
        // waypoint and stops there. No combat/speed override or forced recovery.
        HCXExpansionBridge.HCHoldClearWaypoints(m_HCHold);
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(m_HCHold, eAIWaypointBehavior.ONCE);
        if (returning)
        {
            for (int back = 0; back < roads.Path.Count(); back++) { HCXExpansionBridge.HCHoldAddWaypoint(m_HCHold, roads.Path[back]); }
            HCXExpansionBridge.HCHoldAddWaypoint(m_HCHold, m_From);
        }
        else
        {
            for (int forward = 0; forward < roads.Path.Count(); forward++) { HCXExpansionBridge.HCHoldAddWaypoint(m_HCHold, roads.Path[roads.Path.Count() - 1 - forward]); }
            HCXExpansionBridge.HCHoldAddWaypoint(m_HCHold, m_To);
        }
        // Legacy in-progress journals may still request a route. Recovery stays
        // dormant until a caller owns its give-up/abort lifecycle; arrival polling
        // alone cannot complete that lifecycle after an observer gives up.
        return true;
    }
    override bool HCBindCaravan(HCCaravanState row)
    {
        HCClear();
        if (!row || !Corridor || row.LeaseId != m_Lease || !m_HCHold || !HCReady()) { return false; }
        if (!m_StockReader) { m_StockReader = new HCXAITradeAdapter; }
        HCTradeRecipe stockRecipe = new HCTradeRecipe;
        m_StockReader.Recipe = stockRecipe;
        ItemBase stock;
        eAIBase holder = m_StockReader.HCHolder(row.LeaseId, stockRecipe.LeftClass, stock);
        if (!holder || !stock) { return false; }
        LeftActor = holder; LeftItem = stock;
        return HCInventoryBoundCaravan(row);
    }
    override bool HCWalkCaravan(HCCaravanState row, bool returning)
    {
        return row && HCCurrentCaravan(row) && HCRequest(returning);
    }
    override bool HCAtCamp(HCCaravanState row, bool returning)
    {
        if (!row || !LeftActor || !Corridor || !HCCurrentCaravan(row)) { return false; }
        vector destination = m_To;
        if (returning) { destination = m_From; }
        bool arrived = vector.DistanceSq(LeftActor.GetPosition(), destination) <= Corridor.ArrivalRangeMeters * Corridor.ArrivalRangeMeters;
        // Trade Walker arrival polling does not call this port (deferred).
        if (!arrived)
        {
            eAIGroup liveGroup = m_HCHold.HCResolve();
            if (liveGroup) { m_Recovery.HCCheck(liveGroup, LeftActor.GetPosition(), GetGame().GetTime()); }
        }
        return arrived;
    }
    override bool HCFleeObserved(HCCaravanState row) { return m_HCHold && HCXExpansionBridge.HCHoldIsInCombat(m_HCHold); }
}

// #256: one current physical party per director visit, one bounded native
// path query. The existing provider retains spawn, caps and despawn ownership.
modded class HCXAISiteState
{
    ref HCXAIStuckRecovery HCJourneyRecovery;
    bool HCJourneyWalking;
    vector HCJourneyEnd;
    float HCJourneyRetry;
    float HCJourneyStarted;
    int HCJourneyRecoveryChecks;
    int HCJourneyRetryVisits;
    ref TVectorArray HCJourneyPath = new TVectorArray;
    vector HCJourneySampled;
    vector HCJourneySampleTarget;
    int HCJourneyPathStage;
    int HCJourneyPathFailures;

    // Failures wait at least 15/30 seconds AND skip one/two eligible visits.
    // Visit backoff still matters when the director rotation exceeds that time.
    void HCFailJourneyLeg()
    {
        HCJourneyPathStage = 0;
        HCJourneyPath.Clear();
        HCJourneyPathFailures = Math.Min(HCJourneyPathFailures + 1, 2);
        HCJourneyRetry = GetGame().GetTickTime() + 15 * HCJourneyPathFailures;
        HCJourneyRetryVisits = HCJourneyPathFailures;
    }

    void HCResetJourney()
    {
        HCStopJourney();
        HCJourneyPath.Clear();
        HCJourneyPathStage = 0;
        HCJourneyPathFailures = 0;
    }

    // Stop motion observation; callers invalidating geometry use HCResetJourney.
    void HCStopJourney()
    {
        HCXJourneyReplans.HCRelease(this);
        HCJourneyWalking = false;
        HCJourneyRecovery = null;
        HCJourneyStarted = 0;
        HCJourneyRecoveryChecks = 0;
        HCJourneyRetry = 0;
        HCJourneyRetryVisits = 0;
    }
}

// One server-wide FIFO. No planner exists while waiting; only the head gets
// one HCCheck/HCStep per core tick. Array work is bounded independently of N.
class HCXJourneyReplans
{
    static const int HC_QUEUE_CAP = 64;
    protected static ref array<ref HCXJourneyReplanTurn> s_Queue = new array<ref HCXJourneyReplanTurn>;
    protected static int s_Frame = -1;

    static void HCRelease(HCXAISiteState state)
    {
        for (int index = s_Queue.Count() - 1; index >= 0; index--)
        {
            if (s_Queue[index].State == state)
            {
                HCClearFixture(s_Queue[index]);
                s_Queue.RemoveOrdered(index);
            }
        }
    }
    // The turn owns its recovery observer, including the per-request fixture mark.
    static void HCClearFixture(HCXJourneyReplanTurn turn)
    {
        turn.Recovery.Fixture = false;
    }
    static void HCClear()
    {
        foreach (HCXJourneyReplanTurn turn : s_Queue) { HCClearFixture(turn); }
        s_Queue.Clear();
        s_Frame = -1;
    }

    static void HCQueue(HCXAISiteState state, eAIGroup group, vector destination)
    {
        foreach (HCXJourneyReplanTurn existing : s_Queue)
        {
            if (existing.State == state) { return; }
        }
        if (s_Queue.Count() >= HC_QUEUE_CAP) { state.HCJourneyRecovery.HCGiveUp("JOURNEY_REPLAN_QUEUE_CAP"); return; }
        HCXAIGroupHold hold = HCXAIGroupHolds.Follow(null, group);
        if (!hold) { state.HCJourneyRecovery.HCGiveUp("JOURNEY_REPLAN_HANDLE_REFUSED"); return; }
        HCXJourneyReplanTurn turn = new HCXJourneyReplanTurn;
        turn.State = state;
        turn.Recovery = state.HCJourneyRecovery;
        turn.Hold = hold;
        turn.Destination = destination;
        turn.Recovery.Reason = "JOURNEY_REPLAN_QUEUED";
        s_Queue.Insert(turn);
        string line = "[HC XAI] recovery=waiting party=journey reason=JOURNEY_REPLAN_QUEUED";
        if (turn.Recovery.Fixture) { line += " fixture=1"; }
        Print(line + " runtime=PENDING");
    }

    static void HCTick()
    {
        int now = GetGame().GetTime();
        if (s_Frame == now) { return; }
        s_Frame = now;
        if (s_Queue.Count() == 0) { return; }
        HCXJourneyReplanTurn turn = s_Queue[0];
        if (!turn.Active) { turn.Active = true; turn.Started = now; }
        // Even perpetual admission refusal cannot retain the active slot.
        if (now < turn.Started || now - turn.Started >= HCXConvoyRoute.HC_PLAN_TIMEOUT_MS)
        {
            turn.Recovery.HCGiveUp("JOURNEY_REPLAN_TIMEOUT");
            turn.State.HCResetJourney();
            return;
        }
        // Separate observation admission leaves HC_WORK_CONVOY_ROUTE for the
        // planner's existing per-work-unit HCTakeFor and HCWorkBudget deadline.
        if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_CARAVAN, HCUnitBudget.HC_WORK_ROADS, 2)) { return; }
        HCXAISiteState state = turn.State;
        if (!state.Transient || !state.Materialized || state.Completed || !state.Patrol || !HCXExpansionBridge.HCHoldSame(turn.Hold, state.Patrol.m_Group) || state.HCJourneyRecovery != turn.Recovery || !state.HCJourneyWalking || turn.Recovery.GivenUp)
        {
            state.HCResetJourney();
            return;
        }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
        HCWorldModule world = HCWorldModule.Get();
        vector destination;
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (!identity || !world || !world.HCJourneyTarget(identity.HCPartyId(), destination) || destination != turn.Destination || HCW38SituationRuntime.HCUsed(state.ProposalId) || HCAITrade.HCJourneyBusy(state.ProposalId) || (adapter && adapter.HCJourneyBusy(state.ProposalId)))
        {
            state.HCResetJourney();
            return;
        }
        DayZPlayerImplement leader = HCXExpansionBridge.HCHoldGetFormationLeader(turn.Hold);
        if (HCXExpansionBridge.HCHoldCount(turn.Hold) < 1 || state.Patrol.m_HCPendingMembers > 0 || !leader || !leader.IsAlive() || HCXExpansionBridge.HCHoldIsInCombat(turn.Hold))
        {
            state.HCResetJourney();
            return;
        }
        vector position = leader.GetPosition();
        if (vector.DistanceSq(position, state.HCJourneyEnd) <= 64) { state.HCResetJourney(); return; }
        eAIGroup liveGroup = turn.Hold.HCResolve();
        if (!liveGroup) { state.HCResetJourney(); return; }
        turn.Recovery.HCCheck(liveGroup, position, now, true);
        if (turn.Recovery.GivenUp) { state.HCResetJourney(); return; }
        if (turn.Recovery.Replan) { turn.Recovery.Replan.mHCStarted = turn.Started; }
        if (!turn.Recovery.AwaitingReplan) { HCRelease(state); }
    }
}

modded class HCXAISiteDirector
{
    protected int m_HCJourneyCursor;

    void HCResetPartyJourney(HCXAIGroupHold party)
    {
        foreach (HCXAISiteState released : m_States)
        {
            if (released && released.Patrol && HCXExpansionBridge.HCHoldSame(party, released.Patrol.m_Group)) { released.HCResetJourney(); }
        }
    }

    // Despawned and the last-member-death path both finish here. Release
    // before the provider deletes the patrol or removes the director state.
    override protected void FinishTransient(HCXAISiteState state, bool materialized, int survivors)
    {
        state.HCResetJourney();
        super.FinishTransient(state, materialized, survivors);
    }

    override void Spawned(HCXAISitePatrol patrol)
    {
        foreach (HCXAISiteState fresh : m_States)
        {
            if (fresh && fresh.Patrol == patrol) { fresh.HCResetJourney(); }
        }
        super.Spawned(patrol);
    }

    // The caller admits the complete visit before observation or native work.
    // Sampling yields; FindPath uses the current leader position and shares its
    // visit with bounded validation and issue. Never cache an origin across visits.
    bool HCJourneyLeg(HCXAISiteState state, vector position, vector wanted, vector destination)
    {
        if (state.HCJourneyPathStage != 0 && state.HCJourneySampleTarget != destination)
        {
            state.HCJourneyPathStage = 0;
            state.HCJourneyPath.Clear();
        }
        if (state.HCJourneyPathStage == 0)
        {
            state.HCJourneySampleTarget = destination;
            state.HCJourneySampled = this.NavSample(wanted, 12, m_Filter);
            if (state.HCJourneySampled == vector.Zero) { state.HCFailJourneyLeg(); return false; }
            state.HCJourneyPathStage = 1;
            return false;
        }
        AIWorld navigation = GetGame().GetWorld().GetAIWorld();
        TVectorArray path = state.HCJourneyPath;
        path.Clear();
        if (!navigation || !navigation.FindPath(position, state.HCJourneySampled, m_Filter, path))
        {
            state.HCFailJourneyLeg();
            return false;
        }
        bool valid = path.Count() >= 2 && path.Count() <= 32;
        if (valid) { valid = HCXConvoyRoute.HCFlatSq(path[0], position) <= 64 && vector.DistanceSq(path[path.Count() - 1], state.HCJourneySampled) <= 4; }
        float length = 0;
        if (valid)
        {
            for (int index = 1; index < path.Count(); index++) { length += vector.Distance(path[index - 1], path[index]); }
        }
        if (valid && length <= 240) { state.HCJourneyPathStage = 0; state.HCJourneyPathFailures = 0; return true; }
        state.HCFailJourneyLeg();
        return false;
    }

    override protected void StepTransients()
    {
        super.StepTransients();
        if (m_States.Count() == 0) { return; }
        m_HCJourneyCursor = m_HCJourneyCursor % m_States.Count();
        HCXAISiteState state = m_States[m_HCJourneyCursor];
        m_HCJourneyCursor++;
        if (!state) { return; }
        if (!state.Transient || !state.Materialized || state.Completed || !state.Patrol || !state.Patrol.m_Group) { state.HCResetJourney(); return; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
        HCWorldModule world = HCWorldModule.Get();
        vector destination;
        if (!identity || !world || !world.HCJourneyTarget(identity.HCPartyId(), destination)) { state.HCResetJourney(); return; }
        eAIGroup party = state.Patrol.m_Group;
        if (HCXExpansionBridge.HCGroupCount(party) < 1 || state.Patrol.m_HCPendingMembers > 0) { state.HCResetJourney(); return; }
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (HCW38SituationRuntime.HCUsed(state.ProposalId) || HCAITrade.HCJourneyBusy(state.ProposalId)) { state.HCResetJourney(); return; }
        if (adapter && adapter.HCJourneyBusy(state.ProposalId)) { state.HCResetJourney(); return; }
        DayZPlayerImplement leader = HCXExpansionBridge.HCGroupGetFormationLeader(party);
        if (!leader || !leader.IsAlive()) { state.HCResetJourney(); return; }
        vector position = leader.GetPosition();
        float now = GetGame().GetTickTime();
        bool combat = HCXExpansionBridge.HCGroupIsInCombat(party);
        bool recoveryVisit = state.HCJourneyWalking && vector.DistanceSq(position, state.HCJourneyEnd) > 64;
        int cost = 1;
        if (!combat)
        {
            if (recoveryVisit) { cost = 2; }
            else if (state.HCJourneyRetryVisits == 0 && now >= state.HCJourneyRetry && vector.DistanceSq(position, destination) > 64) { cost = 65; }
        }
        // Exactly one take, first for this consumer: the bounded first-item
        // overshoot admits even native work under MaxTickWorkItems=32.
        if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_CARAVAN, HCUnitBudget.HC_WORK_ROADS, cost)) { return; }
        world.HCJourneyObserved(identity.HCPartyId(), position);
        if (combat) { state.HCResetJourney(); return; }
        // Installed eAIDynamicPatrol.c:760-765 measures despawn distance
        // from the formation leader, so visible travelling parties stay live.
        if (recoveryVisit)
        {
            if (state.HCJourneyRecovery)
            {
                state.HCJourneyRecovery.HCCheck(party, position, GetGame().GetTime());
                if (state.HCJourneyRecovery.AwaitingReplan) { HCXJourneyReplans.HCQueue(state, party, destination); }
                state.HCJourneyRecoveryChecks = Math.Min(state.HCJourneyRecoveryChecks + 1, 24);
            }
            bool gaveUp = state.HCJourneyRecovery && state.HCJourneyRecovery.GivenUp;
            bool refresh = state.HCJourneyRecoveryChecks >= 4 && now - state.HCJourneyStarted >= 90;
            // Preserve the ladder window after an issued rung, but only up to
            // 24 checks. Pending samples/replans cannot defeat that hard cap.
            bool ladderWindow = state.HCJourneyRecovery && state.HCJourneyRecovery.LadderStep > 0 && state.HCJourneyRecoveryChecks < 24;
            if (state.HCJourneyRecovery && (state.HCJourneyRecovery.Checks > 0 || state.HCJourneyRecovery.Replan || state.HCJourneyRecovery.AwaitingReplan || ladderWindow)) { refresh = false; }
            if (state.HCJourneyRecoveryChecks >= 24) { refresh = true; }
            if (!gaveUp && !refresh) { return; }
            // Give-up and timed refresh both discard possibly failed geometry.
            state.HCResetJourney();
            // This visit admitted recovery only; native planning gets its own visit.
            return;
        }
        if (state.HCJourneyRetryVisits > 0) { state.HCJourneyRetryVisits--; return; }
        if (now < state.HCJourneyRetry || cost != 65) { return; }
        state.HCJourneyRetry = now + 1;
        HCXJourneyReplans.HCRelease(state);
        state.HCJourneyWalking = false;
        state.HCJourneyRecovery = null;
        if (!world.HCJourneyTarget(identity.HCPartyId(), destination)) { return; }
        vector direction = destination - position;
        direction[1] = 0;
        float distance = direction.Length();
        if (distance <= 8) { return; }
        direction.Normalize();
        vector wanted = position + direction * Math.Min(100, distance);
        wanted[1] = GetGame().SurfaceY(wanted[0], wanted[2]);
        if (!HCJourneyLeg(state, position, wanted, destination)) { return; }
        TVectorArray path = state.HCJourneyPath;
        HCXExpansionBridge.HCGroupClearWaypoints(party);
        // ONCE walks the whole navmesh path; HALT would stop at path[0].
        HCXExpansionBridge.HCGroupSetWaypointBehaviour(party, eAIWaypointBehavior.ONCE);
        foreach (vector point : path) { HCXExpansionBridge.HCGroupAddWaypoint(party, point); }
        state.HCJourneyRecovery = new HCXAIStuckRecovery;
        state.HCJourneyRecovery.Kind = "journey";
        state.HCJourneyRecovery.JourneyScheduled = true;
        state.HCJourneyRecovery.HCStart(path, GetGame().GetTime(), 32);
        state.HCJourneyRecoveryChecks = 0;
        state.HCJourneyEnd = state.HCJourneySampled;
        state.HCJourneyWalking = true;
        state.HCJourneyStarted = now;
        HCReached.Mark("caravan.physical_leg");
    }
}

// HCX loads after the base materializer has added MaterializerRow.
modded class HCWorldModule
{
    override HCWorldProposal MaterializerRow(int rowIndex)
    {
        HCWorldProposal proposal = super.MaterializerRow(rowIndex);
        int index = rowIndex - HCAILimits.Get().MaxHoldouts;
        if (!proposal || index < 0 || index >= m_Data.Parties.Count()) { return proposal; }
        HCWorldParty party = m_Data.Parties[index];
        HCWorldPlace next = m_Data.Place(party.Route[(party.Edge + 1) % party.Route.Count()]);
        if (!next) { return null; }
        proposal.Position = proposal.Position + (next.Position - proposal.Position) * party.Progress;
        vector current = proposal.Position;
        current[1] = GetGame().SurfaceY(current[0], current[2]);
        proposal.Position = current;
        return proposal;
    }

}

// Higher-priority finite cargo trips retain their existing waypoint ownership.
modded class HCAITrade
{
    static bool HCJourneyBusy(string lease)
    {
        HCXAITradeAdapter port = HCXAITradeAdapter.Cast(s_Provider);
        if (!port || !port.Producer) { return false; }
        return port.Producer.m_LeftLease == lease || port.Producer.m_RightLease == lease;
    }
}

modded class HCXAIAdapter
{
    bool HCJourneyBusy(string lease)
    {
        return m_Caravan && m_Caravan.HCActive() && m_Caravan.m_State.LeaseId == lease;
    }
}
