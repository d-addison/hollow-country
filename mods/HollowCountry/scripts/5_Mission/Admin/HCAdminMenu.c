// Native evidence (installed scripts-1.30.164289):
// 1_Core/proto/EnWidgets.c: Widget Show/Enable/SetColor/Unlink/Update,
// Workspace.CreateWidgets; Button.SetText; MultilineText.SetText;
// EditBox.GetText/SetText; Scroll.VScrollToPos01; GridSpacerWidget.
// 3_Game/gameplay.c MapWidget; UIScriptedMenu.c Init/OnShow/OnHide/Close.
// Vanilla gui.pbo: camera_tools.layout scroll/spacers; connection dialogue
// MultilineText wrap/size-to-text. Original layouts; no COT source used.
// Widgets: tabs once at open, cards once per tab switch, 50 console rows once.
// Reply-driven refresh. Update only checks session/busy; no widget allocation.
class HCAdminCard
{
    ref HCAdminCommand Entry;
    Widget Root;
    ButtonWidget Run;
    ButtonWidget Minus;
    ButtonWidget Plus;
    EditBoxWidget Edit;
    int Value;

    bool HCBind(Widget root, HCAdminCommand entry)
    {
        Root = root;
        Entry = entry;
        Value = entry.DefaultValue;
        Run = ButtonWidget.Cast(root.FindAnyWidget("HCAdminRun"));
        Minus = ButtonWidget.Cast(root.FindAnyWidget("HCAdminMinus"));
        Plus = ButtonWidget.Cast(root.FindAnyWidget("HCAdminPlus"));
        Edit = EditBoxWidget.Cast(root.FindAnyWidget("HCAdminValue"));
        TextWidget label = TextWidget.Cast(root.FindAnyWidget("HCAdminCardLabel"));
        TextWidget help = TextWidget.Cast(root.FindAnyWidget("HCAdminCardHelp"));
        TextWidget tag = TextWidget.Cast(root.FindAnyWidget("HCAdminCardTag"));
        TextWidget range = TextWidget.Cast(root.FindAnyWidget("HCAdminRange"));
        TextWidget position = TextWidget.Cast(root.FindAnyWidget("HCAdminPosition"));
        Widget controls = root.FindAnyWidget("HCAdminValueControls");
        if (!Run || !Minus || !Plus || !Edit || !label || !help || !tag || !range || !position || !controls) { return false; }
        label.SetText(entry.Label);
        help.SetText(entry.Help);
        tag.SetText("WORLD-CHANGING");
        tag.SetColor(ARGB(255, 245, 181, 90));
        if (entry.ReadOnly)
        {
            tag.SetText("READ-ONLY");
            tag.SetColor(ARGB(255, 112, 210, 165));
        }
        position.SetText("Server-authorized; normal module caps apply");
        if (entry.AtPosition) { position.SetText("Acts at my position / nearby state"); }
        controls.Show(entry.Integer);
        range.SetText(entry.HCRange());
        Edit.SetText(Value.ToString());
        return true;
    }

    bool HCReadValue()
    {
        if (!Entry.Integer) { return true; }
        string text = Edit.GetText();
        string digits = "0123456789";
        if (text.Length() < 1 || text.Length() > 11) { return false; }
        int start = 0;
        string limit = "2147483647";
        // A future signed catalog range needs no new menu dispatch/validation.
        if (text.Get(0) == "-" && Entry.HCClamp(-1) < 0)
        {
            start = 1;
            limit = "2147483648";
        }
        int count = text.Length() - start;
        if (count < 1 || count > 10) { return false; }
        for (int index = start; index < text.Length(); index++)
        {
            if (digits.IndexOf(text.Get(index)) < 0) { return false; }
        }
        // Validate the native int boundary before ToInt; never overflow into 0.
        if (count == 10)
        {
            for (int digitIndex = 0; digitIndex < count; digitIndex++)
            {
                int digit = digits.IndexOf(text.Get(start + digitIndex));
                int maximum = digits.IndexOf(limit.Get(digitIndex));
                if (digit > maximum) { return false; }
                if (digit < maximum) { break; }
            }
        }
        Value = Entry.HCClamp(text.ToInt());
        Edit.SetText(Value.ToString());
        return true;
    }
}

class HCAdminTab
{
    ref HCAdminSection Section;
    ButtonWidget Button;
}

class HCAdminMenu : UIScriptedMenu
{
    protected HCAdminClient m_Client;
    protected MapWidget m_Map;
    protected CanvasWidget m_Routes;
    protected TextListboxWidget m_Layers;
    protected TextWidget m_State;
    protected TextWidget m_SectionTitle;
    protected TextWidget m_SectionHelp;
    protected ButtonWidget m_Checks;
    protected Widget m_MapPanel;
    protected GridSpacerWidget m_CardHost;
    protected GridSpacerWidget m_TabHost;
    protected GridSpacerWidget m_ConsoleHost;
    protected ScrollWidget m_CardScroll;
    protected ScrollWidget m_ConsoleScroll;
    protected ref array<ref HCAdminCard> m_Cards = new array<ref HCAdminCard>;
    protected ref array<ref HCAdminTab> m_Tabs = new array<ref HCAdminTab>;
    protected ref array<MultilineTextWidget> m_ConsoleRows = new array<MultilineTextWidget>;
    protected ref array<string> m_LayerNames = new array<string>;
    protected string m_Section;
    protected bool m_WasBusy;
    protected bool m_Listening;

    override Widget Init()
    {
        m_Client = HCAdminClient.HCGet();
        if (!m_Client.HCValid()) { return null; }
        layoutRoot = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_admin.layout");
        if (!layoutRoot) { return null; }
        m_Map = MapWidget.Cast(layoutRoot.FindAnyWidget("HCAdminMap"));
        m_Routes = CanvasWidget.Cast(layoutRoot.FindAnyWidget("HCAdminRoutes"));
        m_Layers = TextListboxWidget.Cast(layoutRoot.FindAnyWidget("HCAdminLayers"));
        m_State = TextWidget.Cast(layoutRoot.FindAnyWidget("HCAdminState"));
        m_SectionTitle = TextWidget.Cast(layoutRoot.FindAnyWidget("HCAdminSectionTitle"));
        m_SectionHelp = TextWidget.Cast(layoutRoot.FindAnyWidget("HCAdminSectionHelp"));
        m_Checks = ButtonWidget.Cast(layoutRoot.FindAnyWidget("HCAdminChecks"));
        m_MapPanel = layoutRoot.FindAnyWidget("HCAdminMapPanel");
        m_CardHost = GridSpacerWidget.Cast(layoutRoot.FindAnyWidget("HCAdminCards"));
        m_TabHost = GridSpacerWidget.Cast(layoutRoot.FindAnyWidget("HCAdminTabs"));
        m_ConsoleHost = GridSpacerWidget.Cast(layoutRoot.FindAnyWidget("HCAdminConsole"));
        m_CardScroll = ScrollWidget.Cast(layoutRoot.FindAnyWidget("HCAdminCardScroll"));
        m_ConsoleScroll = ScrollWidget.Cast(layoutRoot.FindAnyWidget("HCAdminConsoleScroll"));
        if (!m_Map || !m_Routes || !m_Layers || !m_State || !m_SectionTitle || !m_SectionHelp || !m_Checks || !m_MapPanel || !m_CardHost || !m_TabHost || !m_ConsoleHost || !m_CardScroll || !m_ConsoleScroll)
        {
            layoutRoot.Unlink();
            layoutRoot = null;
            return null;
        }
        if (!HCBuildTabs() || !HCBuildConsole())
        {
            HCDestroyWidgets();
            layoutRoot.Unlink();
            layoutRoot = null;
            return null;
        }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (player) { m_Map.SetMapPos(player.GetPosition()); }
        m_Map.SetScale(0.2);
        HCSelect(m_Tabs[0].Section);
        m_Client.Changed.Insert(HCRefresh);
        m_Listening = true;
        HCRefresh();
        return layoutRoot;
    }

    protected bool HCBuildTabs()
    {
        array<ref HCAdminSection> sections = HCAdminCatalog.Sections();
        for (int index = 0; index < sections.Count(); index++)
        {
            Widget root = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_admin_tab.layout", m_TabHost);
            if (!root) { return false; }
            HCAdminTab tab = new HCAdminTab;
            tab.Section = sections[index];
            tab.Button = ButtonWidget.Cast(root);
            if (!tab.Button) { root.Unlink(); return false; }
            tab.Button.SetText(tab.Section.Label);
            m_Tabs.Insert(tab);
        }
        m_TabHost.Update();
        return m_Tabs.Count() > 0;
    }

    protected bool HCBuildConsole()
    {
        for (int index = 0; index < 50; index++)
        {
            Widget root = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_admin_line.layout", m_ConsoleHost);
            if (!root) { return false; }
            MultilineTextWidget row = MultilineTextWidget.Cast(root);
            if (!row) { root.Unlink(); return false; }
            row.Show(false);
            m_ConsoleRows.Insert(row);
        }
        return true;
    }

    protected void HCClearCards()
    {
        for (int index = 0; index < m_Cards.Count(); index++) { m_Cards[index].Root.Unlink(); }
        m_Cards.Clear();
    }

    protected bool HCBuildCards()
    {
        HCClearCards();
        array<ref HCAdminCommand> entries = HCAdminCatalog.Commands();
        for (int index = 0; index < entries.Count(); index++)
        {
            HCAdminCommand entry = entries[index];
            if (entry.Section != m_Section) { continue; }
            Widget root = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_admin_card.layout", m_CardHost);
            if (!root) { return false; }
            HCAdminCard card = new HCAdminCard;
            if (!card.HCBind(root, entry)) { root.Unlink(); return false; }
            m_Cards.Insert(card);
        }
        m_CardHost.Update();
        m_CardScroll.VScrollToPos01(0);
        HCApplyBusy();
        return true;
    }

    protected void HCSelect(HCAdminSection section)
    {
        if (m_Section == section.Id) { return; }
        m_Section = section.Id;
        m_SectionTitle.SetText(section.Label);
        m_SectionHelp.SetText(section.Help);
        bool overview = m_Section == "overview";
        bool showMap = m_Section == "map";
        m_Checks.Show(overview);
        m_MapPanel.Show(showMap);
        m_CardScroll.Show(!showMap);
        if (overview)
        {
            m_CardScroll.SetPos(0, 0.36);
            m_CardScroll.SetSize(1, 0.64);
        }
        else
        {
            m_CardScroll.SetPos(0, 0.23);
            m_CardScroll.SetSize(1, 0.77);
        }
        for (int index = 0; index < m_Tabs.Count(); index++)
        {
            HCAdminTab tab = m_Tabs[index];
            tab.Button.SetText(tab.Section.Label);
            tab.Button.SetColor(ARGB(255, 155, 166, 180));
            if (tab.Section.Id == m_Section)
            {
                tab.Button.SetText("> " + tab.Section.Label);
                tab.Button.SetColor(ARGB(255, 245, 190, 65));
            }
        }
        if (!HCBuildCards()) { Close(); return; }
        if (showMap) { HCRenderRoutes(); }
    }

    protected void HCApplyBusy()
    {
        bool busy = m_Client.HCBusy();
        m_WasBusy = busy;
        m_State.SetText(m_Client.HCState());
        m_Checks.Enable(!busy);
        for (int index = 0; index < m_Cards.Count(); index++)
        {
            HCAdminCard card = m_Cards[index];
            card.Run.Enable(!busy);
            card.Minus.Enable(!busy);
            card.Plus.Enable(!busy);
            card.Edit.Enable(!busy);
        }
    }

    // ScriptInvoker callback, only on request/reply/timeout/snapshot expiry.
    protected void HCRefresh()
    {
        if (!layoutRoot) { return; }
        HCApplyBusy();
        if (!m_Client.HCValid()) { return; }
        HCRenderMap();
        array<ref HCAdminConsoleLine> lines = m_Client.HCConsole();
        for (int index = 0; index < m_ConsoleRows.Count(); index++)
        {
            MultilineTextWidget row = m_ConsoleRows[index];
            row.Show(index < lines.Count());
            if (index >= lines.Count()) { continue; }
            HCAdminConsoleLine line = lines[index];
            row.SetText(line.Text);
            row.SetColor(ARGB(255, 240, 120, 120));
            if (line.Ok) { row.SetColor(ARGB(255, 112, 210, 165)); }
        }
        // Native wrap + size-to-text-v grow rows; spacer/scroll retain full text.
        m_ConsoleHost.Update();
        m_ConsoleScroll.Update();
        m_ConsoleScroll.VScrollToPos01(0);
    }

    protected void HCRenderMap()
    {
        m_Map.ClearUserMarks();
        m_Routes.Clear();
        m_Layers.ClearItems();
        m_LayerNames.Clear();
        if (!m_Client.View) { return; }
        for (int markIndex = 0; markIndex < m_Client.View.Marks.Count(); markIndex++)
        {
            HCAdminMark mark = m_Client.View.Marks[markIndex];
            if (m_LayerNames.Find(mark.Layer) < 0 && m_LayerNames.Count() < 16) { m_LayerNames.Insert(mark.Layer); }
            if (m_Client.Hidden.Find(mark.Layer) >= 0) { continue; }
            if (mark.Route == 0)
            {
                m_Map.AddUserMark(mark.Position, mark.Layer + ": " + mark.Label + " | " + mark.Detail, ARGB(255, 245, 190, 65), "\\dz\\gear\\navigation\\data\\map_tree_ca.paa");
            }
        }
        for (int layerIndex = 0; layerIndex < m_LayerNames.Count(); layerIndex++)
        {
            string flag = "[on] ";
            if (m_Client.Hidden.Find(m_LayerNames[layerIndex]) >= 0) { flag = "[off] "; }
            m_Layers.AddItem(flag + m_LayerNames[layerIndex], null, 0);
        }
        HCRenderRoutes();
    }

    protected void HCRenderRoutes()
    {
        m_Routes.Clear();
        if (m_Section != "map" || !m_Client.View) { return; }
        float originX;
        float originY;
        m_Routes.GetScreenPos(originX, originY);
        HCAdminMark previous;
        for (int routeIndex = 0; routeIndex < m_Client.View.Marks.Count(); routeIndex++)
        {
            HCAdminMark mark = m_Client.View.Marks[routeIndex];
            if (mark.Route == 0 || m_Client.Hidden.Find(mark.Layer) >= 0) { previous = null; continue; }
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
        if (!m_Client.HCValid()) { Close(); return; }
        if (m_WasBusy != m_Client.HCBusy()) { HCApplyBusy(); }
    }

    override bool OnClick(Widget w, int x, int y, int button)
    {
        if (!w) { return false; }
        if (w.GetName() == "HCAdminClose") { Close(); return true; }
        if (!m_Client.HCValid()) { Close(); return true; }
        for (int tabIndex = 0; tabIndex < m_Tabs.Count(); tabIndex++)
        {
            if (w == m_Tabs[tabIndex].Button) { HCSelect(m_Tabs[tabIndex].Section); return true; }
        }
        if (w.GetName() == "HCAdminToggle")
        {
            int selected = m_Layers.GetSelectedRow();
            if (selected < 0 || selected >= m_LayerNames.Count()) { return true; }
            string layer = m_LayerNames[selected];
            int hidden = m_Client.Hidden.Find(layer);
            if (hidden >= 0) { m_Client.Hidden.RemoveOrdered(hidden); }
            else { m_Client.Hidden.Insert(layer); }
            HCRenderMap();
            return true;
        }
        if (m_Client.HCBusy()) { return true; }
        if (w == m_Checks) { m_Client.HCChecks(); HCApplyBusy(); return true; }
        for (int cardIndex = 0; cardIndex < m_Cards.Count(); cardIndex++)
        {
            HCAdminCard card = m_Cards[cardIndex];
            if (w != card.Run && w != card.Minus && w != card.Plus) { continue; }
            if (!card.HCReadValue())
            {
                m_Client.HCFeedback("Enter a whole number in the shown range: " + card.Entry.HCRange());
                return true;
            }
            if (w == card.Minus) { card.Value = card.Entry.HCStep(card.Value, -1); }
            else if (w == card.Plus) { card.Value = card.Entry.HCStep(card.Value, 1); }
            else { m_Client.HCSend(card.Entry.Id, card.Value); }
            card.Edit.SetText(card.Value.ToString());
            HCApplyBusy();
            return true;
        }
        return super.OnClick(w, x, y, button);
    }

    override bool OnChange(Widget w, int x, int y, bool finished)
    {
        if (finished)
        {
            for (int index = 0; index < m_Cards.Count(); index++)
            {
                HCAdminCard card = m_Cards[index];
                if (w != card.Edit) { continue; }
                if (!card.HCReadValue())
                {
                    // Keep invalid text visible. Resetting it on focus loss
                    // could let the following Run click send the old default.
                    m_Client.HCFeedback("Enter a whole number in the shown range: " + card.Entry.HCRange());
                }
                return true;
            }
        }
        return super.OnChange(w, x, y, finished);
    }

    // Reproject on native map interaction, not a per-frame map poll.
    override bool OnMouseWheel(Widget w, int x, int y, int wheel)
    {
        bool handled = super.OnMouseWheel(w, x, y, wheel);
        HCRenderRoutes();
        return handled;
    }

    override bool OnMouseButtonUp(Widget w, int x, int y, int button)
    {
        bool handled = super.OnMouseButtonUp(w, x, y, button);
        HCRenderRoutes();
        return handled;
    }

    protected void HCDestroyWidgets()
    {
        HCClearCards();
        for (int tabIndex = 0; tabIndex < m_Tabs.Count(); tabIndex++) { m_Tabs[tabIndex].Button.Unlink(); }
        m_Tabs.Clear();
        for (int rowIndex = 0; rowIndex < m_ConsoleRows.Count(); rowIndex++) { m_ConsoleRows[rowIndex].Unlink(); }
        m_ConsoleRows.Clear();
    }

    override void OnHide()
    {
        if (m_Listening) { m_Client.Changed.Remove(HCRefresh); m_Listening = false; }
        m_Client.HCCancelChecks();
        if (m_Map) { m_Map.ClearUserMarks(); }
        if (m_Routes) { m_Routes.Clear(); }
        m_LayerNames.Clear();
        HCDestroyWidgets();
        // UIScriptedMenu owns cursor, focus, input unlock and root destruction.
        super.OnHide();
    }
}
