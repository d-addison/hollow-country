// Admin world layers on the Expansion M map: real Expansion map markers plus
// an "Admin layers" section inside Expansion's own marker list. Authored
// against installed class/API/widget names only (CC BY-NC-ND; no Expansion
// script or layout text copied). Installed citations:
// - Navigation/navigation_gui.pbo layouts/expansion_map_markerlist.layout:92
//   WrapSpacer MarkerListPanelContent (inside the list scroller, :81); our
//   section follows its server-section look (:301 header 285x30,
//   sdf_MetronBook24 size 14, colour 0.8627, DayZDefaultPanel rows).
// - Core/core_scripts.pbo 3_Game/DayZExpansion_Core/ExpansionIcons.c:15 static
//   registry, :312 Get(string); ExpansionIcon.c:13-17 IconPath. Every icon
//   below is a file path registered there and present in Core/core_gui.pbo.
// - Native scripts-1.30.164289 1_Core/proto/EnWidgets.c:125 Show, :172
//   SetHandler, :173 Unlink, :181 CreateWidgets, :195 SetText, :144 SetColor,
//   :257 LoadImageFile, :349 EditBoxWidget.GetText, :702 GetFocus;
//   1_Core/proto/EnScript.c:470 RemoveOrdered.
// Admin data stays in this UI: nothing here feeds AI, Expansion marker data,
// party sync or server markers.
class HCXAdminMapLayers : ScriptedWidgetEventHandler
{
    protected const string HCX_SECTION_LAYOUT = "HollowCountryExpansionAI/gui/layouts/hcx_admin_map_layers.layout";
    protected const string HCX_ROW_LAYOUT = "HollowCountryExpansionAI/gui/layouts/hcx_admin_map_layer_row.layout";
    // New Expansion marker layouts per frame; a full 384-pin view fills in
    // six frames instead of one long hitch.
    protected const int HCX_CREATE_BUDGET = 64;
    protected const int HCX_MAX_ROWS = 48;

    protected ExpansionMapMenu mHCXMenu;
    protected Widget mHCXRoot;
    protected MapWidget mHCXMap;
    protected Widget mHCXSection;
    protected Widget mHCXRowsHost;
    protected ButtonWidget mHCXToggle;
    protected TextWidget mHCXTitle;
    protected EditBoxWidget mHCXLootFilter;
    protected ButtonWidget mHCXLootRun;
    protected MultilineTextWidget mHCXDetail;
    protected TextWidget mHCXState;
    protected ref array<ref HCXAdminMapMarker> mHCXMarkers = new array<ref HCXAdminMapMarker>;
    protected ref array<Widget> mHCXRows = new array<Widget>;
    protected ref array<Widget> mHCXRowButtons = new array<Widget>;
    protected ref array<TextWidget> mHCXRowNames = new array<TextWidget>;
    protected ref array<ImageWidget> mHCXRowIcons = new array<ImageWidget>;
    protected int mHCXActive;
    protected int mHCXPinVersion = -1;
    protected int mHCXStyleVersion = -1;
    protected bool mHCXOpen;
    // A failed marker layout is not retried until the map is opened again.
    protected bool mHCXCreateFailed;

    // Fixed cycle of verified Expansion icon names (ExpansionIcons.c line of
    // each AddIcon); the layer colour and legend row identify the layer.
    static string HCXIconName(int index)
    {
        switch (index % 16)
        {
            case 0: return "Map Marker";      // :150
            case 1: return "Star";            // :190
            case 2: return "Square";          // :193
            case 3: return "Shield";          // :194
            case 4: return "Ellipse";         // :100
            case 5: return "Exclamationmark"; // :99
            case 6: return "Questionmark";    // :174
            case 7: return "Skull 1";         // :187
            case 8: return "Trader";          // :206
            case 9: return "Vehicle Crash";   // :211
            case 10: return "Water 1";        // :213
            case 11: return "Radiation";      // :177
            case 12: return "Infected 1";     // :135
            case 13: return "Base";           // :62
            case 14: return "Eye";            // :97
            case 15: return "Cross";          // :253
        }
        return "Map Marker";
    }

    void Open(ExpansionMapMenu menu, Widget root, MapWidget mapWidget)
    {
        Close();
        if (!menu || !root || !mapWidget) return;
        mHCXMenu = menu;
        mHCXRoot = root;
        mHCXMap = mapWidget;
        mHCXOpen = true;
        mHCXPinVersion = -1;
        mHCXStyleVersion = -1;
        mHCXActive = 0;
        mHCXCreateFailed = false;
        // The legend lives in Expansion's marker list. If that list is absent
        // (another map mod), markers still draw with every layer on.
        Widget content = root.FindAnyWidget("MarkerListPanelContent");
        if (content) mHCXSection = GetGame().GetWorkspace().CreateWidgets(HCX_SECTION_LAYOUT, content);
        if (mHCXSection)
        {
            mHCXSection.SetHandler(this);
            mHCXRowsHost = mHCXSection.FindAnyWidget("HCXAdminRows");
            mHCXToggle = ButtonWidget.Cast(mHCXSection.FindAnyWidget("HCXAdminToggle"));
            mHCXTitle = TextWidget.Cast(mHCXSection.FindAnyWidget("HCXAdminTitle"));
            mHCXLootFilter = EditBoxWidget.Cast(mHCXSection.FindAnyWidget("HCXAdminLootFilter"));
            mHCXLootRun = ButtonWidget.Cast(mHCXSection.FindAnyWidget("HCXAdminLootRun"));
            mHCXDetail = MultilineTextWidget.Cast(mHCXSection.FindAnyWidget("HCXAdminDetail"));
            mHCXState = TextWidget.Cast(mHCXSection.FindAnyWidget("HCXAdminState"));
            HCXHandle(mHCXToggle);
            HCXHandle(mHCXLootFilter);
            HCXHandle(mHCXLootRun);
            mHCXSection.Show(false);
        }
        // No layout root is passed: the admin client binds no widgets of its own here.
        HCAdminWorldClient.Get().Open(null);
    }

    protected void HCXHandle(Widget widget)
    {
        if (widget) widget.SetHandler(this);
    }

    void Close()
    {
        if (mHCXOpen)
        {
            mHCXOpen = false;
            // Close unregisters Event_OnRPC before any in-flight reply can bind.
            HCAdminWorldClient.Get().Close();
        }
        // Drop every marker from Expansion's list, then delete them; the
        // ExpansionMapWidgetBase destructor unlinks each widget tree.
        if (mHCXMenu) mHCXMenu.HCXTrimAdminMarkers(0);
        mHCXMarkers.Clear();
        mHCXActive = 0;
        mHCXRows.Clear();
        mHCXRowButtons.Clear();
        mHCXRowNames.Clear();
        mHCXRowIcons.Clear();
        if (mHCXSection) mHCXSection.Unlink();
        mHCXSection = null;
        mHCXRowsHost = null;
        mHCXToggle = null;
        mHCXTitle = null;
        mHCXLootFilter = null;
        mHCXLootRun = null;
        mHCXDetail = null;
        mHCXState = null;
        mHCXMenu = null;
        mHCXRoot = null;
        mHCXMap = null;
    }

    // Typing a class name must not trigger Expansion's M close hotkey.
    bool IsTyping()
    {
        return mHCXLootFilter && GetFocus() == mHCXLootFilter;
    }

    // Called from the menu's Update after Expansion has run its own marker loop.
    void Update()
    {
        if (!mHCXOpen || !mHCXMap) return;
        HCAdminWorldClient admin = HCAdminWorldClient.Get();
        admin.Tick(mHCXMap);
        if (mHCXSection && mHCXSection.IsVisible() != admin.Authorized) mHCXSection.Show(admin.Authorized);
        // Re-cluster only after a view/zoom change (throttled) or new data;
        // between collects Expansion moves the markers with the map.
        admin.Refresh(mHCXMap);
        if (admin.PinVersion() != mHCXPinVersion) HCXBindMarkers(admin);
        if (mHCXSection && admin.Authorized && admin.StyleVersion() != mHCXStyleVersion) HCXBindLegend(admin);
    }

    protected void HCXBindMarkers(HCAdminWorldClient admin)
    {
        int wanted = admin.PinCount();
        if (!admin.Authorized) wanted = 0;
        // Hard cap mirrors the wire bound even if a client cap regresses.
        if (wanted > HCAdminWorldWire.DRAW) wanted = HCAdminWorldWire.DRAW;
        int budget = HCX_CREATE_BUDGET;
        bool complete = true;
        int bound = 0;
        for (int index = 0; index < wanted; index++)
        {
            HCAdminWorldPin pin = admin.PinAt(index);
            HCAdminWorldStyle style = admin.StyleOf(pin);
            if (!pin || !pin.Mark || !style) continue;
            if (bound == mHCXMarkers.Count())
            {
                if (mHCXCreateFailed) break;
                if (budget <= 0) { complete = false; break; }
                budget--;
                HCXAdminMapMarker created = new HCXAdminMapMarker(mHCXRoot, mHCXMap);
                if (!created.GetLayoutRoot())
                {
                    mHCXCreateFailed = true;
                    break;
                }
                created.HCXOwn(this, bound);
                mHCXMarkers.Insert(created);
            }
            HCXAdminMapMarker marker = mHCXMarkers[bound];
            // Slots stay stable; only newly active slots join Expansion's loop.
            if (bound >= mHCXActive) mHCXMenu.HCXInsertAdminMarker(marker);
            marker.HCXBind(index, pin.Mark.Position, admin.PinTitle(pin), HCXIconName(style.IconIndex), style.Color);
            bound++;
            if (bound > mHCXActive) mHCXActive = bound;
        }
        if (bound < mHCXActive)
        {
            for (int hide = bound; hide < mHCXActive; hide++) mHCXMarkers[hide].Hide();
            mHCXMenu.HCXTrimAdminMarkers(bound);
            mHCXActive = bound;
        }
        // An incomplete fill (creation budget) resumes on the next frame.
        if (complete) mHCXPinVersion = admin.PinVersion();
        if (mHCXState) mHCXState.SetText(admin.StateText());
    }

    protected void HCXBindLegend(HCAdminWorldClient admin)
    {
        if (mHCXTitle)
        {
            if (admin.LayersVisible()) mHCXTitle.SetText("Admin layers [on]");
            else mHCXTitle.SetText("Admin layers [off]");
        }
        int rows = Math.Min(admin.StyleCount(), HCX_MAX_ROWS);
        for (int index = 0; index < rows; index++)
        {
            HCAdminWorldStyle style = admin.StyleAt(index);
            if (!style) continue;
            if (index == mHCXRows.Count() && !HCXAddRow(style)) break;
            TextWidget name = mHCXRowNames[index];
            ImageWidget icon = mHCXRowIcons[index];
            string text = style.Layer + " (" + style.Count.ToString() + ")";
            int textColor = ARGB(255, 220, 220, 220);
            int iconColor = style.Color;
            if (!style.Visible || !admin.LayersVisible())
            {
                text = text + " - hidden";
                textColor = ARGB(120, 220, 220, 220);
                iconColor = ARGB(90, 220, 220, 220);
            }
            name.SetText(text);
            name.SetColor(textColor);
            icon.SetColor(iconColor);
        }
        mHCXStyleVersion = admin.StyleVersion();
    }

    protected bool HCXAddRow(HCAdminWorldStyle style)
    {
        if (!mHCXRowsHost) return false;
        Widget row = GetGame().GetWorkspace().CreateWidgets(HCX_ROW_LAYOUT, mHCXRowsHost);
        if (!row) return false;
        Widget button = row.FindAnyWidget("HCXAdminLayerButton");
        TextWidget name = TextWidget.Cast(row.FindAnyWidget("HCXAdminLayerName"));
        ImageWidget icon = ImageWidget.Cast(row.FindAnyWidget("HCXAdminLayerIcon"));
        if (!button || !name || !icon)
        {
            row.Unlink();
            return false;
        }
        row.SetHandler(this);
        button.SetHandler(this);
        // One load per row, from the verified Expansion icon registry only.
        ExpansionIcon registered = ExpansionIcons.Get(HCXIconName(style.IconIndex));
        if (registered) icon.LoadImageFile(0, registered.IconPath);
        mHCXRows.Insert(row);
        mHCXRowButtons.Insert(button);
        mHCXRowNames.Insert(name);
        mHCXRowIcons.Insert(icon);
        return true;
    }

    void HCXSelect(int slot)
    {
        HCAdminWorldClient admin = HCAdminWorldClient.Get();
        string detail = admin.Select(admin.PinAt(slot));
        if (detail != "" && mHCXDetail) mHCXDetail.SetText(detail);
    }

    override bool OnClick(Widget w, int x, int y, int button)
    {
        if (!w || !mHCXOpen) return false;
        HCAdminWorldClient admin = HCAdminWorldClient.Get();
        if (!admin.Authorized) return false;
        if (w == mHCXToggle)
        {
            admin.ToggleAll();
            return true;
        }
        if (w == mHCXLootRun)
        {
            if (!mHCXLootFilter) return true;
            string status = admin.RequestLoot(mHCXLootFilter.GetText(), mHCXMap);
            if (status != "" && mHCXDetail) mHCXDetail.SetText(status);
            return true;
        }
        int row = mHCXRowButtons.Find(w);
        if (row >= 0)
        {
            admin.ToggleLayer(row);
            return true;
        }
        // Clicks inside our section never reach Expansion's list handler.
        return w == mHCXLootFilter || w == mHCXSection;
    }
}
