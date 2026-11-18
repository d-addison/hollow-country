// W6 #123/#133. Installed scripts-1.30.164289 native APIs:
// 3_Game/gameplay.c:324-333 MapWidget ClearUserMarks/AddUserMark/SetMapPos/
// SetScale/MapToScreen; 1_Core/proto/EnWidgets.c:153 GetScreenPos, :169
// FindAnyWidget, :173 Unlink, :195 SetText, :343-344 Canvas.DrawLine/Clear,
// :349 EditBox.GetText, :442 TextListbox.AddItem, :430 GetSelectedRow,
// :427 ClearItems, :121 GetName; 1_Core/proto/proto.c:322 ARGB;
// 3_Game/tools/UIScriptedMenu.c:31 Close, :173/:184 OnShow/OnHide;
// 1_Core/proto/EnString.c:20 ToInt, :240 IndexOf, :448 Get;
// EnScript.c:385 Clear, :470 RemoveOrdered;
// Workspace creation: 1_Core/proto/EnWidgets.c:181 CreateWidgets.
// 3_Game/Global/Game.c:85 GetWorkspace, :944 GetPlayer; gameplay.c:636 GetGame;
// Entities/Object.c:287 GetPosition; 1_Core/proto/EnScript.c:94 Class.Cast.
// Every 0.25s <=512 route vertices; only changed views redraw <=512 pins.
// Layers <=16; <=64 module lines. No map polling or gameplay on open/close.
class HCAdminMenu : UIScriptedMenu
{
    protected MapWidget m_Map;
    protected CanvasWidget m_Routes;
    protected TextWidget m_Notice;
    protected TextListboxWidget m_Layers;
    protected TextListboxWidget m_Status;
    protected EditBoxWidget m_Day;
    protected ref array<string> m_LayerNames = new array<string>;
    protected int m_Revision = -1;
    protected float m_Elapsed;

    override Widget Init()
    {
        if (!HCAdminClient.HCGet().HCValid()) { return null; }
        layoutRoot = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_admin.layout");
        if (!layoutRoot) { return null; }
        m_Map = MapWidget.Cast(layoutRoot.FindAnyWidget("HCAdminMap"));
        m_Routes = CanvasWidget.Cast(layoutRoot.FindAnyWidget("HCAdminRoutes"));
        m_Notice = TextWidget.Cast(layoutRoot.FindAnyWidget("HCAdminNotice"));
        m_Layers = TextListboxWidget.Cast(layoutRoot.FindAnyWidget("HCAdminLayers"));
        m_Status = TextListboxWidget.Cast(layoutRoot.FindAnyWidget("HCAdminStatusRows"));
        m_Day = EditBoxWidget.Cast(layoutRoot.FindAnyWidget("HCAdminDayValue"));
        if (!m_Map || !m_Routes || !m_Notice || !m_Layers || !m_Status || !m_Day)
        {
            layoutRoot.Unlink();
            layoutRoot = null;
            return null;
        }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (player) { m_Map.SetMapPos(player.GetPosition()); }
        m_Map.SetScale(0.2);
        return layoutRoot;
    }

    protected void HCRender(HCAdminClient client)
    {
        m_Map.ClearUserMarks();
        m_Routes.Clear();
        m_Layers.ClearItems();
        m_Status.ClearItems();
        m_LayerNames.Clear();
        m_Notice.SetText(client.Notice);
        if (!client.View) { return; }
        for (int markIndex = 0; markIndex < client.View.Marks.Count(); markIndex++)
        {
            HCAdminMark mark = client.View.Marks[markIndex];
            if (m_LayerNames.Find(mark.Layer) < 0 && m_LayerNames.Count() < 16) { m_LayerNames.Insert(mark.Layer); }
            if (client.Hidden.Find(mark.Layer) >= 0) { continue; }
            if (mark.Route == 0)
            {
                m_Map.AddUserMark(mark.Position, mark.Layer + ": " + mark.Label + " | " + mark.Detail, ARGB(255, 245, 190, 65), "\\dz\\gear\\navigation\\data\\map_tree_ca.paa");
            }
        }
        for (int layerIndex = 0; layerIndex < m_LayerNames.Count(); layerIndex++)
        {
            string flag = "[on] ";
            if (client.Hidden.Find(m_LayerNames[layerIndex]) >= 0) { flag = "[off] "; }
            m_Layers.AddItem(flag + m_LayerNames[layerIndex], null, 0);
        }
        for (int lineIndex = 0; lineIndex < client.View.Lines.Count(); lineIndex++) { m_Status.AddItem(client.View.Lines[lineIndex], null, 0); }
    }

    protected void HCRenderRoutes(HCAdminClient client)
    {
        m_Routes.Clear();
        if (!client.View) { return; }
        float originX;
        float originY;
        m_Routes.GetScreenPos(originX, originY);
        HCAdminMark previous;
        for (int routeIndex = 0; routeIndex < client.View.Marks.Count(); routeIndex++)
        {
            HCAdminMark mark = client.View.Marks[routeIndex];
            if (mark.Route == 0 || client.Hidden.Find(mark.Layer) >= 0) { previous = null; continue; }
            if (previous && previous.Route == mark.Route)
            {
                vector from = m_Map.MapToScreen(previous.Position);
                vector to = m_Map.MapToScreen(mark.Position);
                m_Routes.DrawLine(from[0] - originX, from[1] - originY, to[0] - originX, to[1] - originY, 2, ARGB(255, 245, 190, 65));
            }
            previous = mark;
        }
    }

    override void Update(float timeslice)
    {
        super.Update(timeslice);
        HCAdminClient client = HCAdminClient.HCGet();
        if (!client.HCValid()) { Close(); return; }
        m_Elapsed += timeslice;
        if (m_Elapsed < 0.25) { return; }
        m_Elapsed = 0;
        if (m_Revision != client.Revision) { HCRender(client); m_Revision = client.Revision; }
        HCRenderRoutes(client);
    }

    override bool OnClick(Widget w, int x, int y, int button)
    {
        if (!w) { return false; }
        HCAdminClient client = HCAdminClient.HCGet();
        if (!client.HCValid()) { Close(); return true; }
        string name = w.GetName();
        if (name == "HCAdminClose") { Close(); return true; }
        if (name == "HCAdminToggle")
        {
            int selected = m_Layers.GetSelectedRow();
            if (selected < 0 || selected >= m_LayerNames.Count()) { return true; }
            string layer = m_LayerNames[selected];
            int hidden = client.Hidden.Find(layer);
            if (hidden >= 0) { client.Hidden.RemoveOrdered(hidden); }
            else { client.Hidden.Insert(layer); }
            client.Revision++;
            return true;
        }
        string command;
        if (name == "HCAdminRefresh") { command = "snapshot"; }
        else if (name == "HCAdminStatus") { command = "status"; }
        else if (name == "HCAdminSitter") { command = "sitter"; }
        else if (name == "HCAdminDormant") { command = "dormant"; }
        else if (name == "HCAdminHorde") { command = "horde"; }
        else if (name == "HCAdminScene") { command = "scene"; }
        else if (name == "HCAdminEvent") { command = "event"; }
        else if (name == "HCAdminCamp") { command = "camp"; }
        else if (name == "HCAdminHoldout") { command = "holdout"; }
        else if (name == "HCAdminDay")
        {
            string text = m_Day.GetText();
            string digits = "0123456789";
            if (text.Length() < 1 || text.Length() > 4) { client.Notice = "Enter day 0 to 3650; changes escalation only."; client.Revision++; return true; }
            // Require decimal digits: malformed text must not silently become 0.
            for (int digitIndex = 0; digitIndex < text.Length(); digitIndex++)
            {
                if (digits.IndexOf(text.Get(digitIndex)) < 0) { client.Notice = "Day must contain decimal digits."; client.Revision++; return true; }
            }
            client.HCSend("day", text.ToInt());
            return true;
        }
        if (command != "") { client.HCSend(command); return true; }
        return super.OnClick(w, x, y, button);
    }

    override void OnHide()
    {
        if (m_Map) { m_Map.ClearUserMarks(); }
        if (m_Routes) { m_Routes.Clear(); }
        m_LayerNames.Clear();
        super.OnHide();
    }
}
