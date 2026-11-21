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

    // Installed Core/core_scripts.pbo 3_Game/DayZExpansion_Core/ExpansionIcons.c:
    // registry names verified in place; API/name references only, no borrowed text.
    static string HCXIconName(string layer)
    {
        layer.ToLower();
        if (layer.IndexOf("infected") >= 0 || layer.IndexOf("horde") >= 0) return "Infected 1"; // :135
        if (layer.IndexOf("radiation") >= 0 || layer.IndexOf("gas") >= 0) return "Radiation"; // :177
        if (layer.IndexOf("trader") >= 0) return "Trader"; // :206
        if (layer.IndexOf("water") >= 0) return "Water 1"; // :213
        if (layer.IndexOf("loot") >= 0 || layer.IndexOf("ce-spawns") >= 0 || layer == "supply-dumps" || layer == "dead_drops") return "Backpack"; // :52
        if (layer.IndexOf("crash") >= 0) return "Vehicle Crash"; // :211
        if (layer.IndexOf("event") >= 0 || layer == "scenes") return "Exclamationmark"; // :99
        if (layer.IndexOf("vehicle") >= 0 || layer.IndexOf("convoy") >= 0) return "Car 2"; // :70
        if (layer.IndexOf("camp") >= 0 || layer.IndexOf("base") >= 0 || layer == "holdouts" || layer.IndexOf("shelter") >= 0 || layer.IndexOf("tent") >= 0 || layer.IndexOf("outpost") >= 0) return "Base"; // :62
        if (layer == "ai" || layer.IndexOf("ai-") == 0 || layer.IndexOf("patrol") >= 0) return "Soldier"; // :202
        return "Map Marker"; // :150; shared fallback for pins and legend
    }

    static ExpansionIcon HCXIcon(string layer)
    {
        ExpansionIcon icon = ExpansionIcons.Get(HCXIconName(layer));
        if (!icon) icon = ExpansionIcons.Get("Map Marker"); // ExpansionIcons.c:150,312
        return icon;
    }

    void Open(ExpansionMapMenu menu, Widget root, MapWidget mapWidget)
    {
        Close();
        if (!menu || !root || !mapWidget) return;
        // Reuse widgets only while Expansion retains the same menu root.
        // A newly constructed menu cannot reuse widgets parented to its predecessor.
        if (mHCXRoot != root || mHCXMap != mapWidget) ReleaseWidgets();
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
        if (content && !mHCXSection) mHCXSection = GetGame().GetWorkspace().CreateWidgets(HCX_SECTION_LAYOUT, content);
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
        for (int row = 0; row < mHCXRows.Count(); row++)
        {
            mHCXRows[row].SetHandler(this);
            mHCXRowButtons[row].SetHandler(this);
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
        // Remove every active entry from Expansion's projection loop. Retain
        // hidden widgets for this menu's next OnShow; no callbacks remain live.
        if (mHCXMenu) mHCXMenu.HCXTrimAdminMarkers(0);
        for (int hide = 0; hide < mHCXMarkers.Count(); hide++) mHCXMarkers[hide].HCXSuspend();
        mHCXActive = 0;
        if (mHCXSection)
        {
            mHCXSection.Show(false);
            mHCXSection.SetHandler(null);
        }
        if (mHCXToggle) mHCXToggle.SetHandler(null);
        if (mHCXLootFilter) mHCXLootFilter.SetHandler(null);
        if (mHCXLootRun) mHCXLootRun.SetHandler(null);
        for (int row = 0; row < mHCXRows.Count(); row++)
        {
            mHCXRows[row].SetHandler(null);
            mHCXRowButtons[row].SetHandler(null);
        }
    }

    void ReleaseWidgets()
    {
        mHCXMarkers.Clear();
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
            marker.HCXBind(index, pin.Mark.Position, admin.PinTitle(pin), admin.PinName(pin), HCXIconName(style.Layer), style.Color);
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
        int budget = 4; // Legend layouts are also created over bounded frames.
        bool complete = true;
        for (int index = 0; index < rows; index++)
        {
            HCAdminWorldStyle style = admin.StyleAt(index);
            if (!style) continue;
            if (index == mHCXRows.Count())
            {
                if (budget <= 0) { complete = false; break; }
                budget--;
                if (!HCXAddRow(style)) break;
            }
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
            // Cached rows may be rebound after authorization/cache expiry.
            ExpansionIcon registered = HCXIcon(style.Layer);
            if (registered) icon.LoadImageFile(0, registered.IconPath);
            icon.Show(registered != null);
            icon.SetColor(iconColor);
        }
        for (int hide = 0; hide < mHCXRows.Count(); hide++) mHCXRows[hide].Show(hide < rows);
        if (complete) mHCXStyleVersion = admin.StyleVersion();
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
