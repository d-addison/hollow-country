// M-map-only, targeted server replies. Native scripts-1.30.164289:
// gameplay.c:104-117/322-333 RPC + MapWidget projection/scale/centre;
// DayZGame.c:991 Event_OnRPC; EnWidgets.c:125/140/144/153/154 Show/position/size;
// EnScript.c:857/902/917 map Clear/Set/Contains. No entity queries here.
// Rendering is pluggable: the base HC group map binds pooled circle pins
// (HCGroupMapLayers.Pin), the Expansion addon binds real Expansion map
// markers. Both read the same clustered, capped pin set through Refresh.
class HCAdminWorldStyle
{
    string Layer;
    // Stable per-layer index; each renderer maps it to a verified texture.
    int IconIndex;
    int Color;
    bool Visible = true;
    int Count;
    int StaticCount;
    int DynamicCount;
}
class HCAdminWorldPin
{
    HCAdminMark Mark;
    HCAdminWorldStyle Style;
    vector Screen;
    int Count;
}
// Native CachedEquipmentStorage.c uses maps of ref arrays. Snapshot entries
// reuse the pin DTO, resolving its style once before the pan/zoom hot path.
typedef array<ref HCAdminWorldPin> HCAdminWorldBucket;
typedef map<int, ref HCAdminWorldBucket> HCAdminWorldGrid;
class HCAdminWorldClient
{
    protected static ref HCAdminWorldClient s_Instance;
    protected static int s_Session;
    ref array<ref HCAdminMark> StaticRows = new array<ref HCAdminMark>;
    ref array<ref HCAdminMark> DynamicRows = new array<ref HCAdminMark>;
    protected ref array<ref HCAdminMark> m_Incoming = new array<ref HCAdminMark>;
    protected ref array<ref HCAdminWorldStyle> m_Styles = new array<ref HCAdminWorldStyle>;
    protected ref map<string, int> m_StyleIndex = new map<string, int>;
    // Valid wire positions span 0..15360: at most 16 x 16 one-km buckets.
    protected ref HCAdminWorldGrid m_StaticGrid = new HCAdminWorldGrid;
    protected ref HCAdminWorldGrid m_DynamicGrid = new HCAdminWorldGrid;
    protected ref map<string, int> m_Cells = new map<string, int>;
    protected ref array<ref HCAdminWorldPin> m_Pins = new array<ref HCAdminWorldPin>;
    // Optional base-menu panel (hc_group_map.layout); null on the Expansion map.
    protected Widget m_Panel;
    protected ButtonWidget m_Toggle;
    protected TextListboxWidget m_Legend;
    protected MultilineTextWidget m_Detail;
    protected TextWidget m_State;
    protected EditBoxWidget m_LootFilter;
    protected string m_LootRequest;
    protected int m_Version;
    protected int m_Sequence;
    protected int m_Chunk;
    protected int m_SessionId;
    protected bool m_IncomingStatic;
    protected int m_IncomingVersion;
    protected int m_IncomingTotal;
    protected bool m_Open;
    protected bool m_Subscribed;
    protected bool m_Access;
    // Cache only a recently authorized player instance, never another login.
    protected PlayerBase m_CachePlayer;
    protected bool m_CacheAuthorized;
    protected bool m_RequestPending;
    protected float m_RequestAt;
    protected const float REQUEST_SECONDS = 4;
    protected const float STALE_SECONDS = 45; // Allows configured 30 s server refresh + capture.

    protected bool m_Visible = true;
    protected bool m_Dirty = true;
    // New rows or toggles: collect at once instead of waiting for the throttle.
    protected bool m_DataDirty = true;
    protected bool m_ListDirty = true;
    protected vector m_Centre;
    protected float m_Scale;
    // Native 3_Game/gameplay.c:328 GetScale; smaller scales zoom in.
    protected const float LABEL_SCALE = 0.20;
    // Names stay readable only when few pins share the view (#324 client check).
    protected const int LABEL_PINS = 30;
    // View changes re-cluster at most four times a second; renderers keep
    // their markers between collects (Expansion projects them itself).
    protected const float COLLECT_SECONDS = 0.25;
    protected ref HCAdminMark m_Selected;
    protected float m_Left;
    protected float m_Top;
    protected float m_Width;
    protected float m_Height;
    protected int m_PoolStart = -1;
    protected int m_PoolCount;
    protected int m_PoolVersion = -1;
    protected int m_LegendVersion = -1;
    protected float m_IconScale;
    protected float m_LabelScale;
    protected float m_SendAt;
    protected float m_ReplyAt;
    protected float m_CollectAt;
    protected int m_PinVersion;
    protected int m_StyleVersion;
    protected int m_Dropped;
    protected int m_DrawLimit = 384;
    bool Authorized;

    static HCAdminWorldClient Get()
    {
        if (!s_Instance) { s_Instance = new HCAdminWorldClient; }
        return s_Instance;
    }
    // root may be null: the Expansion map renders through its own markers.
    void Open(Widget root)
    {
        if (m_Open) { Close(); }
        m_Panel = null;
        m_Toggle = null;
        m_Legend = null;
        m_Detail = null;
        m_LootFilter = null;
        m_State = null;
        if (root)
        {
            m_Panel = root.FindAnyWidget("HCAdminWorldPanel");
            m_Toggle = ButtonWidget.Cast(root.FindAnyWidget("HCAdminWorldToggle"));
            m_Legend = TextListboxWidget.Cast(root.FindAnyWidget("HCAdminWorldLegend"));
            m_Detail = MultilineTextWidget.Cast(root.FindAnyWidget("HCAdminWorldDetail"));
            m_LootFilter = EditBoxWidget.Cast(root.FindAnyWidget("HCAdminWorldLootFilter"));
            m_State = TextWidget.Cast(root.FindAnyWidget("HCAdminWorldState"));
        }
        if (m_Panel) { m_Panel.Show(false); }
        m_Open = true;
        m_Access = false;
        m_Subscribed = false;
        Authorized = m_CacheAuthorized && m_CachePlayer && m_CachePlayer == GetGame().GetPlayer() && GetGame().GetTickTime() - m_ReplyAt <= STALE_SECONDS;
        if (!Authorized) ClearCache();
        s_Session++;
        m_SessionId = s_Session;
        m_Sequence = 0;
        m_Chunk = 0;
        m_SendAt = 0;
        m_RequestPending = false;
        m_LootRequest = "";
        m_CollectAt = 0;
        m_Incoming.Clear();
        m_Selected = null;
        m_Dirty = true;
        m_DataDirty = true;
        m_ListDirty = true;
        m_PinVersion++;
        m_StyleVersion++;
        DayZGame.Event_OnRPC.Insert(Receive);
    }
    protected void Send(bool open, MapWidget mapWidget)
    {
        HCAdminWorldRequest request = new HCAdminWorldRequest;
        request.Session = m_SessionId;
        request.Open = open;
        m_Subscribed = open;
        if (open)
        {
            m_RequestPending = true;
            m_RequestAt = GetGame().GetTickTime();
        }
        request.LootFilter = m_LootRequest;
        m_LootRequest = "";
        request.StaticVersion = m_Version;
        request.Centre = m_Centre;
        request.Scale = m_Scale;
        if (mapWidget)
        {
            request.Centre = mapWidget.GetMapPos();
            request.Scale = mapWidget.GetScale();
        }
        request.Centre[0] = Math.Clamp(request.Centre[0], 0, 15360);
        request.Centre[2] = Math.Clamp(request.Centre[2], 0, 15360);
        if (!(request.Scale >= 0.001)) { request.Scale = 0.33; }
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(request);
        rpc.Send(null, HCAdminWorldWire.REQUEST, true, null);
    }
    void Close()
    {
        if (!m_Open) { return; }
        Send(false, null);
        DayZGame.Event_OnRPC.Remove(Receive);
        m_Open = false;
        Authorized = false;
        m_RequestPending = false;
        m_LootRequest = "";
        m_Incoming.Clear();
        m_Cells.Clear();
        m_Selected = null;
        m_PinVersion++;
        if (m_Panel) { m_Panel.Show(false); }
        m_Panel = null;
        m_Toggle = null;
        m_Legend = null;
        m_Detail = null;
        m_State = null;
        m_LootFilter = null;
    }
    protected void ClearCache()
    {
        m_CacheAuthorized = false;
        m_CachePlayer = null;
        m_Version = 0;
        m_StaticGrid.Clear();
        m_DynamicGrid.Clear();
        StaticRows.Clear();
        DynamicRows.Clear();
        m_Pins.Clear();
        m_Cells.Clear();
        m_Styles.Clear();
        m_StyleIndex.Clear();
        m_Selected = null;
        m_PinVersion++;
        m_StyleVersion++;
        m_DataDirty = true;
        m_ListDirty = true;
    }

    // The admin view does not need a carried map item: the server checks the
    // allowlist on every request and never replies to anyone else.
    void Tick(MapWidget mapWidget)
    {
        if (!m_Open || !mapWidget) { return; }
        float now = GetGame().GetTickTime();
        m_Access = true;
        // One subscription request outstanding. Chunks extend the wait; do
        // not interrupt a long static transfer with a stale catalog version.
        if (m_RequestPending && now - m_RequestAt > STALE_SECONDS) m_RequestPending = false;
        if (!m_RequestPending && now >= m_SendAt)
        {
            Send(true, mapWidget);
            m_SendAt = now + REQUEST_SECONDS;
        }
        if (Authorized && (m_CachePlayer != GetGame().GetPlayer() || now - m_ReplyAt > STALE_SECONDS))
        {
            Authorized = false;
            ClearCache();
            if (m_Panel) { m_Panel.Show(false); }
        }
        // Foreign map layouts can move their viewport without changing zoom.
        // Native EnWidgets.c:153 GetScreenPos; cached hit positions must follow.
        float left, top, width, height;
        mapWidget.GetScreenPos(left, top);
        mapWidget.GetScreenSize(width, height);
        if (left != m_Left || top != m_Top) { m_Left = left; m_Top = top; m_Dirty = true; }
        if (width != m_Width || height != m_Height) { m_Width = width; m_Height = height; m_Dirty = true; }
        vector centre = mapWidget.GetMapPos();
        float scale = mapWidget.GetScale();
        if (centre != m_Centre || scale != m_Scale) { m_Centre = centre; m_Scale = scale; m_Dirty = true; }
    }
    void Receive(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        // Server-to-client only. Session prevents late replies reviving a closed map.
        if (!m_Open || !m_Access || GetGame().IsServer() || sender || target || rpcType != HCAdminWorldWire.REPLY || !ctx) { return; }
        HCAdminWorldReply reply;
        if (!ctx.Read(reply) || !reply || reply.Session != m_SessionId) { return; }
        if (reply.DrawLimit < 64 || reply.DrawLimit > HCAdminWorldWire.DRAW) { return; }
        m_DrawLimit = reply.DrawLimit;
        if (!reply.Marks || reply.Marks.Count() > HCAdminWorldWire.CHUNK || reply.Total < 0 || reply.Total > HCAdminWorldWire.ROWS) { return; }
        if (reply.Chunk < 0 || reply.Chunk >= 128 || reply.Sequence < m_Sequence) { return; }
        if (reply.Chunk == 0)
        {
            if (reply.Sequence <= m_Sequence) { return; }
            m_Sequence = reply.Sequence;
            m_Chunk = 0;
            m_Incoming.Clear();
            m_IncomingStatic = reply.IsStatic;
            m_IncomingVersion = reply.CatalogRevision;
            m_IncomingTotal = reply.Total;
        }
        if (reply.Sequence != m_Sequence || reply.Chunk != m_Chunk || reply.IsStatic != m_IncomingStatic || reply.CatalogRevision != m_IncomingVersion || reply.Total != m_IncomingTotal) { return; }
        if (m_Incoming.Count() + reply.Marks.Count() > reply.Total) { return; }
        for (int index = 0; index < reply.Marks.Count(); index++)
        {
            HCAdminMark mark = reply.Marks[index];
            if (!mark || mark.Layer.Length() > 48 || mark.Label.Length() > 128 || mark.Detail.Length() > 256 || !HCDebugSnapshot.HCPositionValid(mark.Position)) { return; }
        }
        // InsertAll refuses array<ref T> into array<ref T> here; copy row by row (<=64).
        for (int copy = 0; copy < reply.Marks.Count(); copy++) { m_Incoming.Insert(reply.Marks[copy]); }
        m_Chunk++;
        Authorized = true;
        m_ReplyAt = GetGame().GetTickTime();
        m_CachePlayer = PlayerBase.Cast(GetGame().GetPlayer());
        m_CacheAuthorized = true;
        m_RequestPending = true;
        m_RequestAt = m_ReplyAt;
        if (m_Panel) { m_Panel.Show(true); }
        if (!reply.Last) { return; }
        if (m_Incoming.Count() != reply.Total) { return; }
        m_RequestPending = false;
        // Publish atomically only after every reliable chunk arrived in sequence.
        if (reply.IsStatic)
        {
            StaticRows = m_Incoming;
            m_Version = reply.CatalogRevision;
            BuildGrid(StaticRows, m_StaticGrid, true);
        }
        else
        {
            DynamicRows = m_Incoming;
            BuildGrid(DynamicRows, m_DynamicGrid, false);
        }
        m_Incoming = new array<ref HCAdminMark>;
        m_Dropped = reply.Truncated;
        m_Dirty = true;
        m_DataDirty = true;
        m_ListDirty = true;
    }
    protected HCAdminWorldStyle Style(string layer)
    {
        int index;
        if (m_StyleIndex.Find(layer, index)) { return m_Styles[index]; }
        if (m_Styles.Count() >= 48) { return null; }
        index = m_Styles.Count();
        HCAdminWorldStyle style = new HCAdminWorldStyle;
        style.Layer = layer;
        // Distinct deterministic palette; prefix + legend also identify each layer.
        int red = 75 + (index * 79) % 180;
        int green = 75 + (index * 113) % 180;
        int blue = 75 + (index * 47) % 180;
        style.Color = ARGB(255, red, green, blue);
        // No texture path here. The build 149 client could not load the
        // MapMarkerTypes paths into an ImageWidget (map_*_ca.paa are
        // MapWidget.AddUserMark textures only) and spammed the RPT.
        style.IconIndex = index;
        m_StyleIndex.Set(layer, index);
        m_Styles.Insert(style);
        m_StyleVersion++;
        return style;
    }
    protected void BuildGrid(array<ref HCAdminMark> rows, HCAdminWorldGrid buckets, bool isStatic)
    {
        buckets.Clear();
        foreach (HCAdminWorldStyle previous : m_Styles)
        {
            if (isStatic) { previous.StaticCount = 0; }
            else { previous.DynamicCount = 0; }
        }
        // Snapshot count is wire-capped at ROWS; no row scan on view changes.
        foreach (HCAdminMark mark : rows)
        {
            HCAdminWorldStyle style = Style(mark.Layer);
            if (!style) { continue; }
            if (isStatic) { style.StaticCount++; }
            else { style.DynamicCount++; }
            int cellX = Math.Floor(mark.Position[0] / 1000);
            int cellZ = Math.Floor(mark.Position[2] / 1000);
            int key = cellZ * 16 + cellX;
            HCAdminWorldBucket bucket;
            if (!buckets.Find(key, bucket))
            {
                bucket = new HCAdminWorldBucket;
                buckets.Set(key, bucket);
            }
            HCAdminWorldPin entry = new HCAdminWorldPin;
            entry.Mark = mark;
            entry.Style = style;
            bucket.Insert(entry);
        }
        foreach (HCAdminWorldStyle counted : m_Styles) { counted.Count = counted.StaticCount + counted.DynamicCount; }
    }
    protected void CollectBucket(MapWidget mapWidget, HCAdminWorldBucket bucket, float grid)
    {
        foreach (HCAdminWorldPin entry : bucket)
        {
            HCAdminMark mark = entry.Mark;
            HCAdminWorldStyle style = entry.Style;
            if (!style.Visible) { continue; }
            vector screen = mapWidget.MapToScreen(mark.Position);
            if (screen[0] < m_Left || screen[1] < m_Top || screen[0] > m_Left + m_Width || screen[1] > m_Top + m_Height) { continue; }
            string key = "";
            if (grid > 0)
            {
                int cellX = Math.Floor((screen[0] - m_Left) / grid);
                int cellY = Math.Floor((screen[1] - m_Top) / grid);
                key = mark.Layer + ":" + cellX.ToString() + ":" + cellY.ToString();
                int found;
                if (m_Cells.Find(key, found)) { m_Pins[found].Count++; continue; }
            }
            if (m_Pins.Count() >= m_DrawLimit) { continue; }
            HCAdminWorldPin pin = new HCAdminWorldPin;
            pin.Mark = mark;
            pin.Style = style;
            pin.Screen = screen;
            pin.Count = 1;
            if (key != "") { m_Cells.Set(key, m_Pins.Count()); }
            m_Pins.Insert(pin);
        }
    }
    protected void Collect(MapWidget mapWidget, HCAdminWorldGrid buckets)
    {
        if (!m_Visible || m_Width <= 0 || m_Height <= 0) { return; }
        // Native MapWidget.ScreenToMap consumes screen pixels (gameplay.c:333).
        vector first = mapWidget.ScreenToMap(Vector(m_Left, m_Top, 0));
        vector last = mapWidget.ScreenToMap(Vector(m_Left + m_Width, m_Top + m_Height, 0));
        int minX = Math.Clamp(Math.Floor(Math.Min(first[0], last[0]) / 1000), 0, 15);
        int maxX = Math.Clamp(Math.Floor(Math.Max(first[0], last[0]) / 1000), 0, 15);
        int minZ = Math.Clamp(Math.Floor(Math.Min(first[2], last[2]) / 1000), 0, 15);
        int maxZ = Math.Clamp(Math.Floor(Math.Max(first[2], last[2]) / 1000), 0, 15);
        float grid = 0;
        if (mapWidget.GetScale() >= 0.20) { grid = 64; }
        // At most 256 bucket lookups; project only rows in intersecting cells.
        for (int z = minZ; z <= maxZ; z++)
        {
            for (int x = minX; x <= maxX; x++)
            {
                HCAdminWorldBucket bucket;
                if (buckets.Find(z * 16 + x, bucket)) { CollectBucket(mapWidget, bucket, grid); }
            }
        }
    }
    // Re-cluster only when the view or data changed, throttled for view
    // changes. Returns true when the pin set was rebuilt (bind markers again).
    bool Refresh(MapWidget mapWidget)
    {
        if (!Authorized || !m_Open || !mapWidget) { return false; }
        if (!m_Dirty && !m_DataDirty) { return false; }
        float now = GetGame().GetTickTime();
        if (!m_DataDirty && now < m_CollectAt) { return false; }
        m_Pins.Clear();
        m_Cells.Clear();
        // Dynamic bodies get drawing priority; all layers retain legend counts.
        Collect(mapWidget, m_DynamicGrid);
        Collect(mapWidget, m_StaticGrid);
        m_Dirty = false;
        m_DataDirty = false;
        m_CollectAt = now + COLLECT_SECONDS;
        m_PinVersion++;
        if (m_ListDirty) { m_StyleVersion++; m_ListDirty = false; }
        return true;
    }
    int PinVersion() { return m_PinVersion; }
    int StyleVersion() { return m_StyleVersion; }
    int PinCount() { return m_Pins.Count(); }
    HCAdminWorldPin PinAt(int index)
    {
        if (index < 0 || index >= m_Pins.Count()) { return null; }
        return m_Pins[index];
    }
    int StyleCount() { return m_Styles.Count(); }
    HCAdminWorldStyle StyleAt(int index)
    {
        if (index < 0 || index >= m_Styles.Count()) { return null; }
        return m_Styles[index];
    }
    HCAdminWorldStyle StyleOf(HCAdminWorldPin pin)
    {
        if (!pin || !pin.Mark) { return null; }
        return pin.Style;
    }
    bool LayersVisible() { return m_Visible; }
    bool IsSelected(HCAdminWorldPin pin)
    {
        if (!pin || !pin.Mark || !m_Selected) { return false; }
        // Selection survives a refreshed row object with the same identity.
        return m_Selected.Layer == pin.Mark.Layer && m_Selected.Label == pin.Mark.Label && m_Selected.Position == pin.Mark.Position;
    }
    // Meaning comes only from the source layer/label. Clusters describe the
    // layer, never pretend the representative row names every member.
    string PinName(HCAdminWorldPin pin)
    {
        if (!pin || !pin.Mark) { return ""; }
        string layer = pin.Mark.Layer;
        layer.TrimInPlace();
        if (layer == "") layer = "Map pin";
        if (pin.Count > 1) return layer + " x" + pin.Count.ToString();
        string label = pin.Mark.Label;
        label.TrimInPlace();
        if (label == "" || label == "MARKER NAME") return layer;
        return "[" + layer + "] " + label;
    }
    // Normal labels disappear at low zoom/high counts; selection and hover
    // use PinName so neither can expose placeholder or stale pooled text.
    string PinTitle(HCAdminWorldPin pin)
    {
        if (!pin || !pin.Mark || !PinLabelled(pin)) { return ""; }
        return PinName(pin);
    }
    bool PinLabelled(HCAdminWorldPin pin)
    {
        return IsSelected(pin) || (m_Scale < LABEL_SCALE && m_Pins.Count() <= LABEL_PINS);
    }
    string StateText()
    {
        return "Admin: " + m_Pins.Count().ToString() + "/" + m_DrawLimit.ToString() + " pins | source omitted=" + m_Dropped.ToString();
    }
    void ToggleAll()
    {
        m_Visible = !m_Visible;
        m_Dirty = true;
        m_DataDirty = true;
        m_StyleVersion++;
    }
    void ToggleLayer(int index)
    {
        if (index < 0 || index >= m_Styles.Count()) { return; }
        m_Styles[index].Visible = !m_Styles[index].Visible;
        m_Dirty = true;
        m_DataDirty = true;
        m_StyleVersion++;
    }
    // Returns the detail text for a clicked pin and marks it selected.
    string Select(HCAdminWorldPin pin)
    {
        if (!pin || !pin.Mark) { return ""; }
        m_Selected = pin.Mark;
        // Labels change for the selected pin; renderers rebind once.
        m_PinVersion++;
        m_PoolStart = -1;
        if (pin.Count > 1) { return pin.Mark.Layer + ": " + pin.Count.ToString() + " rows in this cell. Zoom in for individual details."; }
        return PinName(pin) + "\n" + pin.Mark.Detail;
    }
    // Bounded ground loot query; the server keeps its own caps and cooldown.
    string RequestLoot(string filter, MapWidget mapWidget)
    {
        if (!Authorized) { return ""; }
        if (!HCAdminLootMap.HCValidFilter(filter)) { return "Enter a valid class or class prefix for a bounded ground loot query."; }
        m_LootRequest = filter;
        // Queue behind any snapshot in flight; Tick owns the only open send.
        m_SendAt = 0;
        return "Loot ground query requested. Existing query caps/cooldown apply; results appear as lootmap pins.";
    }
    // Base HC group map renderer: pooled circle pins from hc_group_icon.layout.
    void Draw(HCGroupMapLayers pool, MapWidget mapWidget, HCGroupSettings settings)
    {
        if (!Authorized || !m_Open) { return; }
        // The pooled widgets are placed in screen space at bind time, so any
        // view change rebinds them; the base menu calls this every 0.25 s.
        bool moved = m_Dirty;
        Refresh(mapWidget);
        int start = pool.HCUsed();
        bool reuse = !moved && m_PoolVersion == m_PinVersion && start == m_PoolStart && settings.IconScale == m_IconScale && settings.LabelScale == m_LabelScale;
        if (reuse) { reuse = pool.HCKeep(m_PoolCount); }
        if (!reuse)
        {
            for (int index = 0; index < m_Pins.Count(); index++)
            {
                HCAdminWorldPin pin = m_Pins[index];
                HCAdminWorldStyle style = Style(pin.Mark.Layer);
                if (!style) { continue; }
                pool.Pin(mapWidget, pin.Mark.Position, PinTitle(pin), style.Color, settings, PinLabelled(pin));
            }
            m_PoolStart = start;
            m_PoolCount = pool.HCUsed() - start;
            m_PoolVersion = m_PinVersion;
            m_IconScale = settings.IconScale;
            m_LabelScale = settings.LabelScale;
        }
        if (m_Legend && m_LegendVersion != m_StyleVersion)
        {
            m_Legend.ClearItems();
            for (int layer = 0; layer < m_Styles.Count(); layer++)
            {
                HCAdminWorldStyle entry = m_Styles[layer];
                string flag = "[on] ";
                if (!entry.Visible) { flag = "[off] "; }
                int row = m_Legend.AddItem(flag + entry.Layer + " (" + entry.Count.ToString() + ")", null, 0);
                m_Legend.SetItemColor(row, 0, entry.Color);
            }
            m_LegendVersion = m_StyleVersion;
        }
        if (m_State) { m_State.SetText(StateText()); }
    }
    // Base HC group map controls (hc_group_map.layout HCAdminWorldPanel).
    bool Click(Widget widget, MapWidget mapWidget, int x, int y)
    {
        if (!Authorized || !widget) { return false; }
        if (widget.GetName() == "HCAdminWorldLootRun" && m_LootFilter)
        {
            string status = RequestLoot(m_LootFilter.GetText(), mapWidget);
            if (m_Detail && status != "") { m_Detail.SetText(status); }
            return true;
        }
        if (widget == m_Toggle)
        {
            ToggleAll();
            string label = "Admin [on]";
            if (!m_Visible) { label = "Admin [off]"; }
            m_Toggle.SetText(label);
            return true;
        }
        if (widget.GetName() == "HCAdminWorldLayerToggle" && m_Legend)
        {
            ToggleLayer(m_Legend.GetSelectedRow());
            return true;
        }
        if (widget != mapWidget || !m_Detail) { return false; }
        for (int index = 0; index < m_Pins.Count(); index++)
        {
            HCAdminWorldPin pin = m_Pins[index];
            float dx = pin.Screen[0] - x;
            float dy = pin.Screen[1] - y;
            if (dx * dx + dy * dy > 400) { continue; }
            m_Detail.SetText(Select(pin));
            return true;
        }
        return false;
    }
}
