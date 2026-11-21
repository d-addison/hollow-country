// M-map-only, targeted server replies. Native scripts-1.30.164289:
// gameplay.c:104-117/322-333 RPC + MapWidget projection/scale/centre;
// DayZGame.c:991 Event_OnRPC; EnWidgets.c:125/140/144/153/154 Show/position/size;
// EnScript.c:857/902/917 map Clear/Set/Contains. No entity queries here.
class HCAdminWorldStyle
{
    string Layer;
    string Texture;
    int Color;
    bool Visible = true;
    int Count;
}
class HCAdminWorldPin
{
    HCAdminMark Mark;
    vector Screen;
    int Count;
}
class HCAdminWorldClient
{
    protected static ref HCAdminWorldClient s_Instance;
    protected static int s_Session;
    ref array<ref HCAdminMark> StaticRows = new array<ref HCAdminMark>;
    ref array<ref HCAdminMark> DynamicRows = new array<ref HCAdminMark>;
    protected ref array<ref HCAdminMark> m_Incoming = new array<ref HCAdminMark>;
    protected ref array<ref HCAdminWorldStyle> m_Styles = new array<ref HCAdminWorldStyle>;
    protected ref map<string, int> m_StyleIndex = new map<string, int>;
    protected ref map<string, int> m_Cells = new map<string, int>;
    protected ref array<ref HCAdminWorldPin> m_Pins = new array<ref HCAdminWorldPin>;
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
    protected bool m_Visible = true;
    protected bool m_Dirty = true;
    protected bool m_ListDirty = true;
    protected vector m_Centre;
    protected float m_Scale;
    protected float m_Width;
    protected float m_Height;
    protected int m_PoolStart = -1;
    protected int m_PoolCount;
    protected float m_IconScale;
    protected float m_LabelScale;
    protected float m_SendAt;
    protected float m_ReplyAt;
    protected int m_Dropped;
    protected int m_DrawLimit = 384;
    bool Authorized;

    static HCAdminWorldClient Get()
    {
        if (!s_Instance) { s_Instance = new HCAdminWorldClient; }
        return s_Instance;
    }
    void Open(Widget root)
    {
        if (m_Open) { Close(); }
        m_Panel = root.FindAnyWidget("HCAdminWorldPanel");
        m_Toggle = ButtonWidget.Cast(root.FindAnyWidget("HCAdminWorldToggle"));
        m_Legend = TextListboxWidget.Cast(root.FindAnyWidget("HCAdminWorldLegend"));
        m_Detail = MultilineTextWidget.Cast(root.FindAnyWidget("HCAdminWorldDetail"));
        m_LootFilter = EditBoxWidget.Cast(root.FindAnyWidget("HCAdminWorldLootFilter"));
        m_State = TextWidget.Cast(root.FindAnyWidget("HCAdminWorldState"));
        if (m_Panel) { m_Panel.Show(false); }
        m_Open = true;
        m_Access = false;
        m_Subscribed = false;
        Authorized = false;
        s_Session++;
        m_SessionId = s_Session;
        m_Sequence = 0;
        m_Chunk = 0;
        m_SendAt = 0;
        m_Incoming.Clear();
        DynamicRows.Clear();
        m_Pins.Clear();
        m_Dirty = true;
        m_ListDirty = true;
        DayZGame.Event_OnRPC.Insert(Receive);
    }
    protected void Send(bool open, MapWidget mapWidget)
    {
        HCAdminWorldRequest request = new HCAdminWorldRequest;
        request.Session = m_SessionId;
        request.Open = open;
        m_Subscribed = open;
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
        DynamicRows.Clear();
        m_Incoming.Clear();
        m_Pins.Clear();
        m_Cells.Clear();
        if (m_Panel) { m_Panel.Show(false); }
        m_Panel = null;
        m_Toggle = null;
        m_Legend = null;
        m_Detail = null;
        m_State = null;
        m_LootFilter = null;
    }
    void Tick(MapWidget mapWidget, bool hasMap)
    {
        if (!m_Open || !mapWidget) { return; }
        float now = GetGame().GetTickTime();
        m_Access = hasMap;
        if (!hasMap)
        {
            if (m_Subscribed) { Send(false, mapWidget); }
            Authorized = false;
            if (m_Panel) { m_Panel.Show(false); }
            return;
        }
        if (now >= m_SendAt)
        {
            Send(true, mapWidget);
            m_SendAt = now + 4;
        }
        if (Authorized && now - m_ReplyAt > 30)
        {
            Authorized = false;
            DynamicRows.Clear();
            m_Pins.Clear();
            if (m_Panel) { m_Panel.Show(false); }
        }
        float width, height;
        mapWidget.GetScreenSize(width, height);
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
        if (m_Panel) { m_Panel.Show(true); }
        if (!reply.Last) { return; }
        if (m_Incoming.Count() != reply.Total) { return; }
        // Publish atomically only after every reliable chunk arrived in sequence.
        if (reply.IsStatic) { StaticRows = m_Incoming; m_Version = reply.CatalogRevision; }
        else { DynamicRows = m_Incoming; }
        m_Incoming = new array<ref HCAdminMark>;
        m_Dropped = reply.Truncated;
        m_Dirty = true;
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
        // Vanilla icon table; native scripts-1.30.164289/3_Game/gameplay.c
        // MapMarkerTypes.GetMarkerTypeFromID is observed at
        // 5_Mission/GUI/MapMarkersInfo.c:42-45 and reused by HCGroupMapLayers.
        int icon = index % eMapMarkerTypes.MARKERTYPE_MAX;
        style.Texture = MapMarkerTypes.GetMarkerTypeFromID(icon);
        m_StyleIndex.Set(layer, index);
        m_Styles.Insert(style);
        return style;
    }
    protected void Collect(MapWidget mapWidget, array<ref HCAdminMark> rows)
    {
        float left, top, width, height;
        mapWidget.GetScreenPos(left, top);
        mapWidget.GetScreenSize(width, height);
        // Pixel grid follows the real viewport/zoom. Zoomed-in marks remain individual.
        float grid = 0;
        if (mapWidget.GetScale() >= 0.20) { grid = 64; }
        for (int index = 0; index < rows.Count(); index++)
        {
            HCAdminMark mark = rows[index];
            HCAdminWorldStyle style = Style(mark.Layer);
            if (!style) { continue; }
            style.Count++;
            if (!m_Visible || !style.Visible) { continue; }
            vector screen = mapWidget.MapToScreen(mark.Position);
            if (screen[0] < left || screen[1] < top || screen[0] > left + width || screen[1] > top + height) { continue; }
            string key = "";
            if (grid > 0)
            {
                int cellX = Math.Floor((screen[0] - left) / grid);
                int cellY = Math.Floor((screen[1] - top) / grid);
                key = mark.Layer + ":" + cellX.ToString() + ":" + cellY.ToString();
                int found;
                if (m_Cells.Find(key, found)) { m_Pins[found].Count++; continue; }
            }
            if (m_Pins.Count() >= m_DrawLimit) { continue; }
            HCAdminWorldPin pin = new HCAdminWorldPin;
            pin.Mark = mark;
            pin.Screen = screen;
            pin.Count = 1;
            if (key != "") { m_Cells.Set(key, m_Pins.Count()); }
            m_Pins.Insert(pin);
        }
    }
    void Draw(HCGroupMapLayers pool, MapWidget mapWidget, HCGroupSettings settings)
    {
        if (!Authorized || !m_Open) { return; }
        bool changed = m_Dirty;
        if (m_Dirty)
        {
            m_Pins.Clear();
            m_Cells.Clear();
            for (int reset = 0; reset < m_Styles.Count(); reset++) { m_Styles[reset].Count = 0; }
            // Dynamic bodies get drawing priority; all layers retain legend counts.
            Collect(mapWidget, DynamicRows);
            Collect(mapWidget, StaticRows);
            m_Dirty = false;
        }
        int start = pool.HCUsed();
        bool reuse = !changed && start == m_PoolStart && settings.IconScale == m_IconScale && settings.LabelScale == m_LabelScale;
        if (reuse) { reuse = pool.HCKeep(m_PoolCount); }
        if (!reuse)
        {
            for (int index = 0; index < m_Pins.Count(); index++)
            {
                HCAdminWorldPin pin = m_Pins[index];
                HCAdminWorldStyle style = Style(pin.Mark.Layer);
                string title = "[" + style.Layer + "] " + pin.Mark.Label;
                if (pin.Count > 1) { title = "[" + style.Layer + "] x" + pin.Count.ToString(); }
                pool.Pin(mapWidget, pin.Mark.Position, title, style.Color, style.Texture, settings);
            }
            m_PoolStart = start;
            m_PoolCount = pool.HCUsed() - start;
            m_IconScale = settings.IconScale;
            m_LabelScale = settings.LabelScale;
        }
        if (m_ListDirty && m_Legend)
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
            m_ListDirty = false;
        }
        if (m_State) { m_State.SetText("Admin: " + m_Pins.Count().ToString() + "/" + m_DrawLimit.ToString() + " pins | source omitted=" + m_Dropped.ToString()); }
    }
    bool Click(Widget widget, MapWidget mapWidget, int x, int y)
    {
        if (!Authorized || !widget) { return false; }
        if (widget.GetName() == "HCAdminWorldLootRun" && m_LootFilter)
        {
            string filter = m_LootFilter.GetText();
            if (HCAdminLootMap.HCValidFilter(filter))
            {
                m_LootRequest = filter;
                Send(true, mapWidget);
                m_SendAt = GetGame().GetTickTime() + 4;
                if (m_Detail) { m_Detail.SetText("Loot ground query requested. Existing query caps/cooldown apply; results appear as lootmap pins."); }
            }
            else if (m_Detail) { m_Detail.SetText("Enter a valid class or class prefix for a bounded ground loot query."); }
            return true;
        }
        if (widget == m_Toggle)
        {
            m_Visible = !m_Visible;
            m_Dirty = true;
            string label = "Admin [on]";
            if (!m_Visible) { label = "Admin [off]"; }
            m_Toggle.SetText(label);
            return true;
        }
        if (widget.GetName() == "HCAdminWorldLayerToggle" && m_Legend)
        {
            int selected = m_Legend.GetSelectedRow();
            if (selected >= 0 && selected < m_Styles.Count())
            {
                m_Styles[selected].Visible = !m_Styles[selected].Visible;
                m_Dirty = true;
                m_ListDirty = true;
            }
            return true;
        }
        if (widget != mapWidget || !m_Detail) { return false; }
        for (int index = 0; index < m_Pins.Count(); index++)
        {
            HCAdminWorldPin pin = m_Pins[index];
            float dx = pin.Screen[0] - x;
            float dy = pin.Screen[1] - y;
            if (dx * dx + dy * dy > 400) { continue; }
            string detail = pin.Mark.Layer + " | " + pin.Mark.Label + "\n" + pin.Mark.Detail;
            if (pin.Count > 1) { detail = pin.Mark.Layer + ": " + pin.Count.ToString() + " rows in this cell. Zoom in for individual details."; }
            m_Detail.SetText(detail);
            return true;
        }
        return false;
    }
}
