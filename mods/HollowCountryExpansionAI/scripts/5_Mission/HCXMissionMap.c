// Public mission zones on the Expansion M map: one read-only labelled marker plus
// a translucent disc of the zone radius per mission. Client-only, display-only:
// the rows come from HCMissionBeaconStore (the server's pushed snapshot), nothing
// is written to Expansion marker data, party sync or server state.
// Authored against installed Expansion class/API names only (CC BY-NC-ND; no
// Expansion script or layout text copied). Same installed precedent as the admin
// layers (see HCXAdminMapMarker.c / HCXAdminExpansionMap.c for the full list):
// Core/core_scripts.pbo 5_Mission/DayZExpansion_Core/ExpansionMapWidgetBase.c:37-45
// ctor, :112-119 Update projection, :174 SetPosition, :207 Show, :229 SetName,
// :241 SetIcon, :264 SetPrimaryColor, :280 SetHoverColour, :190 OnMarkerClick,
// :79 GetDropSoundEffect, :89 IsDragWidget, :347 CanDrag;
// Core/core_scripts.pbo 3_Game/DayZExpansion_Core/ExpansionIcons.c:99 "Exclamationmark",
// :150 "Map Marker", :312 Get(string); Navigation/navigation_scripts.pbo
// 5_Mission/DayZExpansion_Navigation/ExpansionMapMenu.c:19 m_Markers,
// :177-209 marker insertion, :1058 GetMapMenuRoot, :1098 GetMap, :1269 OnShow,
// :1297 OnHide, :1326 Update, :1354-1363 per-frame marker Update.
// The zone disc is the owned hc_group_icon.layout circle (vanilla dayz_gui imageset
// "circle"); no texture path is built at runtime. Expansion has no canvas to draw on.
// Native scripts-1.30.164289: 1_Core/proto/EnWidgets.c:125 Show, :129 SetSort,
// :140 SetPos, :141 SetSize, :144 SetColor, :154 GetScreenSize, :169 FindAnyWidget,
// :173 Unlink, :181 CreateWidgets; 3_Game/gameplay.c:332 MapToScreen;
// 3_Game/Global/Game.c:914 GetTickTime; 1_Core/proto/EnMath.c AbsFloat.
class HCXMissionMapMarker : ExpansionMapWidgetBase
{
    protected string mHCXIconName;
    protected string mHCXTitle;
    protected bool mHCXNamed;
    protected int mHCXSlot;

    void HCXMissionMapMarker(Widget parent, MapWidget mapWidget, bool autoInit = true)
    {
        SetHoverColour(ARGB(255, 255, 255, 255));
        // Hidden until bound; an unbound marker would sit in the top-left corner.
        Hide();
    }

    void HCXOwn(int slot) { mHCXSlot = slot; }
    int HCXSlot() { return mHCXSlot; }

    void HCXBind(vector position, string title, string iconName, int color)
    {
        if (iconName != mHCXIconName)
        {
            // Registry icons only; the name is cached so a failed lookup is never retried per bind.
            mHCXIconName = iconName;
            ExpansionIcon icon = ExpansionIcons.Get(iconName);
            if (!icon) icon = ExpansionIcons.Get("Map Marker");
            if (icon)
            {
                SetIcon(icon);
                if (m_Icon) m_Icon.Show(true);
            }
            else if (m_Icon) m_Icon.Show(false);
        }
        // The Expansion marker layout ships placeholder text, so the first bind always names it.
        if (!mHCXNamed || title != mHCXTitle)
        {
            mHCXNamed = true;
            mHCXTitle = title;
            SetName(title);
        }
        SetPrimaryColor(color);
        SetPosition(position);
        Show(true);
    }

    void HCXSuspend()
    {
        Hide();
        m_MouseHover = false;
    }

    // Mission markers are read-only: no drag, no drop sound, no edit, no click action.
    override string GetDropSoundEffect()
    {
        return "";
    }

    override bool CanDrag()
    {
        return false;
    }

    override bool IsDragWidget(Widget w)
    {
        return false;
    }

    override void OnMarkerClick()
    {
    }
}

// Pooled marker + disc slots for the open Expansion map menu (at most 16).
class HCXMissionMapLayer
{
    protected const string HCX_DISC_LAYOUT = "HollowCountry/gui/layouts/hc_group_icon.layout";
    protected const int HCX_MAX_SLOTS = 16;
    // New Expansion marker layouts per frame (a full table fills in four frames).
    protected const int HCX_CREATE_BUDGET = 4;

    protected ExpansionMapMenu mHCXMenu;
    protected Widget mHCXRoot;
    protected MapWidget mHCXMap;
    protected bool mHCXOpen;
    protected bool mHCXCreateFailed;
    protected int mHCXVersion = -1;
    protected float mHCXStamp = -100;
    protected int mHCXActive;
    protected ref array<ref HCXMissionMapMarker> mHCXMarkers = new array<ref HCXMissionMapMarker>;
    protected ref array<Widget> mHCXDiscs = new array<Widget>;
    protected ref array<ImageWidget> mHCXDiscMarks = new array<ImageWidget>;
    // World position and radius per active slot, copied at bind; Update only reprojects.
    protected ref array<vector> mHCXCentres = new array<vector>;
    protected ref array<float> mHCXRadii = new array<float>;

    void Open(ExpansionMapMenu menu, Widget root, MapWidget mapWidget)
    {
        Close();
        if (!menu || !root || !mapWidget) return;
        // A newly constructed menu cannot reuse widgets parented to its predecessor.
        if (mHCXRoot != root || mHCXMap != mapWidget) ReleaseWidgets();
        mHCXMenu = menu;
        mHCXRoot = root;
        mHCXMap = mapWidget;
        mHCXOpen = true;
        mHCXVersion = -1;
        mHCXStamp = -100;
        mHCXActive = 0;
        mHCXCreateFailed = false;
    }

    void Close()
    {
        mHCXOpen = false;
        if (mHCXMenu) mHCXMenu.HCXTrimMissionMarkers(0);
        for (int hide = 0; hide < mHCXMarkers.Count(); hide++) mHCXMarkers[hide].HCXSuspend();
        for (int disc = 0; disc < mHCXDiscs.Count(); disc++) mHCXDiscs[disc].Show(false);
        mHCXActive = 0;
    }

    void ReleaseWidgets()
    {
        mHCXMarkers.Clear();
        foreach (Widget owned : mHCXDiscs)
        {
            if (owned) owned.Unlink();
        }
        mHCXDiscs.Clear();
        mHCXDiscMarks.Clear();
        mHCXCentres.Clear();
        mHCXRadii.Clear();
        mHCXMenu = null;
        mHCXRoot = null;
        mHCXMap = null;
    }

    // Called from the menu's Update after Expansion ran its own marker loop. Rows
    // are rebound only when the store changed or every ten seconds (minutes left);
    // the per-frame work is two MapToScreen calls per active zone.
    void Update()
    {
        if (!mHCXOpen || !mHCXMap) return;
        HCMissionBeaconStore store = HCMissionBeaconStore.Get();
        float now = GetGame().GetTickTime();
        int revision = store.Poll(now);
        bool stale = now < mHCXStamp || now - mHCXStamp >= 10;
        if (revision != mHCXVersion || stale) HCXBind(store, now, revision);
        HCXProjectDiscs();
    }

    protected bool HCXEnsureSlot(int slot, inout int budget)
    {
        if (slot < mHCXMarkers.Count()) return true;
        if (mHCXCreateFailed || budget <= 0) return false;
        budget--;
        HCXMissionMapMarker created = new HCXMissionMapMarker(mHCXRoot, mHCXMap);
        if (!created.GetLayoutRoot())
        {
            mHCXCreateFailed = true;
            return false;
        }
        Widget disc = GetGame().GetWorkspace().CreateWidgets(HCX_DISC_LAYOUT, mHCXRoot);
        ImageWidget mark;
        if (disc) mark = ImageWidget.Cast(disc.FindAnyWidget("HCMark"));
        if (!disc || !mark)
        {
            if (disc) disc.Unlink();
            mHCXCreateFailed = true;
            return false;
        }
        // Behind the markers and labels; the disc never takes the pointer.
        disc.SetSort(1);
        disc.Show(false);
        Widget backdrop = disc.FindAnyWidget("HCBackdrop");
        if (backdrop) backdrop.Show(false);
        Widget label = disc.FindAnyWidget("HCLabel");
        if (label) label.Show(false);
        mark.SetImage(0);
        mark.SetColor(ARGB(70, 213, 94, 0));
        created.HCXOwn(slot);
        mHCXMarkers.Insert(created);
        mHCXDiscs.Insert(disc);
        mHCXDiscMarks.Insert(mark);
        mHCXCentres.Insert(Vector(0, 0, 0));
        mHCXRadii.Insert(0);
        return true;
    }

    protected void HCXBind(HCMissionBeaconStore store, float now, int revision)
    {
        int wanted = store.Count();
        if (wanted > HCX_MAX_SLOTS) wanted = HCX_MAX_SLOTS;
        int budget = HCX_CREATE_BUDGET;
        bool complete = true;
        int bound = 0;
        for (int index = 0; index < wanted; index++)
        {
            HCBeaconRow row = store.At(index);
            if (!row) continue;
            if (!HCXEnsureSlot(bound, budget))
            {
                if (!mHCXCreateFailed) complete = false;
                break;
            }
            if (bound >= mHCXMarkers.Count()) break;
            if (bound >= mHCXActive) mHCXMenu.HCXInsertMissionMarker(mHCXMarkers[bound]);
            vector centre = Vector(row.X, 0, row.Z);
            mHCXCentres[bound] = centre;
            mHCXRadii[bound] = row.Radius;
            string title = "Mission: " + row.Title + " ~" + HCInfoEventCache.MinutesLeft(store.Remaining(row, now)) + " min";
            mHCXMarkers[bound].HCXBind(centre, title, "Exclamationmark", ARGB(255, 213, 94, 0));
            bound++;
            if (bound > mHCXActive) mHCXActive = bound;
        }
        if (bound < mHCXActive)
        {
            for (int hide = bound; hide < mHCXActive; hide++)
            {
                mHCXMarkers[hide].HCXSuspend();
                mHCXDiscs[hide].Show(false);
            }
            mHCXMenu.HCXTrimMissionMarkers(bound);
            mHCXActive = bound;
        }
        // An incomplete fill (creation budget) resumes on the next frame.
        if (complete)
        {
            mHCXVersion = revision;
            mHCXStamp = now;
        }
    }

    // Disc geometry follows the map's pan/zoom: radius in pixels from one extra
    // projection per zone. Hidden when the centre is off the map or the size is
    // implausible; a disc that would overhang the map edge is shrunk to fit inside it.
    protected void HCXProjectDiscs()
    {
        if (mHCXActive < 1 || !mHCXRoot) return;
        float rootLeft;
        float rootTop;
        mHCXRoot.GetScreenPos(rootLeft, rootTop);
        float mapLeft;
        float mapTop;
        float mapWidth;
        float mapHeight;
        mHCXMap.GetScreenPos(mapLeft, mapTop);
        mHCXMap.GetScreenSize(mapWidth, mapHeight);
        for (int slot = 0; slot < mHCXActive; slot++)
        {
            Widget disc = mHCXDiscs[slot];
            vector world = mHCXCentres[slot];
            vector centre = mHCXMap.MapToScreen(world);
            vector edge = mHCXMap.MapToScreen(Vector(world[0] + mHCXRadii[slot], 0, world[2]));
            float pixels = Math.AbsFloat(edge[0] - centre[0]);
            bool inside = centre[0] >= mapLeft && centre[0] <= mapLeft + mapWidth && centre[1] >= mapTop && centre[1] <= mapTop + mapHeight;
            if (!inside || !(pixels >= 3 && pixels <= 20000))
            {
                disc.Show(false);
                continue;
            }
            // Never larger than fits inside the map rectangle around the zone centre, so a
            // zoomed-in disc cannot cover the Expansion side panels or toolbar.
            float room = centre[0] - mapLeft;
            room = Math.Min(room, mapLeft + mapWidth - centre[0]);
            room = Math.Min(room, centre[1] - mapTop);
            room = Math.Min(room, mapTop + mapHeight - centre[1]);
            if (pixels > room) pixels = room;
            if (pixels < 3)
            {
                disc.Show(false);
                continue;
            }
            float side = pixels * 2;
            disc.SetPos(centre[0] - pixels - rootLeft, centre[1] - pixels - rootTop);
            disc.SetSize(side, side);
            ImageWidget mark = mHCXDiscMarks[slot];
            mark.SetPos(0, 0);
            mark.SetSize(side, side);
            disc.Show(true);
        }
    }
}

// Second modded layer next to the admin one (HCXAdminExpansionMap.c); every
// override calls super so the layers chain. Installed ExpansionMapMenu.c lines are
// cited in the header above.
modded class ExpansionMapMenu
{
    protected ref HCXMissionMapLayer mHCXMissions;

    override void OnShow()
    {
        super.OnShow();
        if (!mHCXMissions) mHCXMissions = new HCXMissionMapLayer;
        mHCXMissions.Open(this, GetMapMenuRoot(), GetMap());
    }

    override void Update(float timeslice)
    {
        super.Update(timeslice);
        // super.Update may have closed the menu.
        if (!mHCXMissions || IsClosing() || !IsVisible()) return;
        mHCXMissions.Update();
    }

    override void OnHide()
    {
        if (mHCXMissions) mHCXMissions.Close();
        super.OnHide();
    }

    // Client-local transient mission markers join Expansion's own projection loop.
    void HCXInsertMissionMarker(ExpansionMapWidgetBase marker)
    {
        if (marker && m_Markers) m_Markers.Insert(marker);
    }

    // Drop mission markers whose pool slot is >= keep (0 drops all of them).
    void HCXTrimMissionMarkers(int keep)
    {
        if (!m_Markers) return;
        for (int index = m_Markers.Count() - 1; index >= 0; index--)
        {
            HCXMissionMapMarker marker = HCXMissionMapMarker.Cast(m_Markers[index]);
            if (marker && marker.HCXSlot() >= keep) m_Markers.RemoveOrdered(index);
        }
    }
}
