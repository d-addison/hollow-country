// Original overlays over the native pannable/zoomable MapWidget. Public missions
// come from the server's pushed beacon snapshot (HCMissionBeaconStore): a labelled
// pin plus a zone ring per mission, drawn on the existing HCGrid canvas through
// MapToScreen. The zone centre is already offset from the site by the server.
// V2 pins reuse Pin() and validated frame.Places; native evidence in
// HCInfoLayers.c (labels/logging); scripts-1.30.164289/3_Game/gameplay.c:324,332
// (ClearUserMarks/MapToScreen), 1_Core/proto/EnWidgets.c:125,140,144,153,154,
// 169,173,181,195,257,267 (existing widget pooling/drawing path).
// Pins never call LoadImageFile: hc_group_icon.layout carries the verified
// vanilla imageset circle (dayz_gui.imageset image "circle", used by vanilla
// day_z_hud.layout) and each layer is identified by colour and text prefix.
// The build 149 client logged thousands of ImageWidget::LoadImageFile errors
// for \dz\gear\navigation\data\map_*_ca.paa (AddUserMark-only textures),
// retried whenever a pooled slot changed layer.
class HCGroupMapLayers
{
    protected Widget mHCOverlay;
    protected CanvasWidget mHCGrid;
    protected TextWidget mHCNavigation;
    protected TextListboxWidget mHCEvents;
    protected ref array<Widget> mHCPool = new array<Widget>();
    protected int mHCUsed;
    protected ref HCGroupEquipment mHCEquipment;
    protected PlayerBase mHCViewer;
    protected float mHCEquipmentTime;
    protected ref HCInfoEventCache mHCInfoEvents = new HCInfoEventCache;

    void Init(Widget root)
    {
        mHCOverlay = root.FindAnyWidget("HCMapOverlay");
        mHCGrid = CanvasWidget.Cast(root.FindAnyWidget("HCGrid"));
        mHCNavigation = TextWidget.Cast(root.FindAnyWidget("HCNavigation"));
        mHCEvents = TextListboxWidget.Cast(root.FindAnyWidget("HCKnownEvents"));
    }

    void Clear()
    {
        foreach (Widget iconRoot : mHCPool)
            if (iconRoot) iconRoot.Unlink();
        mHCPool.Clear();
        mHCEquipment = null;
        mHCViewer = null;
        mHCInfoEvents.Clear();
        if (mHCGrid) mHCGrid.Clear();
        if (mHCNavigation) mHCNavigation.SetText("");
        if (mHCEvents) mHCEvents.ClearItems();
        mHCUsed = 0;
    }

    // Preserve unchanged admin slots between group redraws. A changed group
    // prefix forces the admin view to bind its slots again from the same pool.
    int HCUsed() { return mHCUsed; }
    bool HCKeep(int count)
    {
        if (count < 0 || mHCUsed + count > mHCPool.Count()) { return false; }
        mHCUsed += count;
        return true;
    }

    void Pin(MapWidget mapWidget, vector position, string title, int color, HCGroupSettings settings, bool labelBackdrop = true)
    {
        int cap = 602;
        if (HCAdminWorldClient.Get().Authorized) { cap = cap + HCAdminWorldWire.DRAW; }
        if (!mHCOverlay || mHCUsed >= cap) return;
        float left, top, width, height;
        mHCOverlay.GetScreenPos(left, top);
        mHCOverlay.GetScreenSize(width, height);
        vector screen = mapWidget.MapToScreen(position);
        float x = screen[0] - left;
        float y = screen[1] - top;
        if (x < 0 || y < 0 || x > width || y > height) return;
        if (mHCUsed == mHCPool.Count())
        {
            Widget created = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_group_icon.layout", mHCOverlay);
            if (!created) return;
            mHCPool.Insert(created);
        }
        Widget pinRoot = mHCPool.Get(mHCUsed);
        TextWidget label = TextWidget.Cast(pinRoot.FindAnyWidget("HCLabel"));
        ImageWidget image = ImageWidget.Cast(pinRoot.FindAnyWidget("HCMark"));
        if (!label || !image) return;
        HCGroupWorldIcons.Scale(pinRoot, label, image, settings);
        label.SetText(title);
        // Native 1_Core/proto/EnWidgets.c:125 Show, :169 FindAnyWidget.
        // Empty admin titles mean icon-only; compact counts need no wide backdrop.
        // Default restores the existing group label appearance on slot reuse.
        label.Show(title != "");
        Widget backdrop = pinRoot.FindAnyWidget("HCBackdrop");
        if (backdrop) backdrop.Show(title != "" && labelBackdrop);
        image.SetImage(0);
        image.SetColor(color);
        pinRoot.SetPos(x, y);
        pinRoot.Show(true);
        mHCUsed++;
    }

    void Navigation(MapWidget mapWidget, PlayerBase viewer, HCGroupSettings settings)
    {
        if (mHCGrid) mHCGrid.Clear();
        if (mHCNavigation) mHCNavigation.SetText("");
        if (!settings.NavigationLayer) return;
        float now = GetGame().GetTickTime();
        if (!mHCEquipment || mHCViewer != viewer || now < mHCEquipmentTime || now - mHCEquipmentTime >= 1.0)
        {
            mHCEquipment = HCGroupEquipment.Read(viewer);
            mHCViewer = viewer;
            mHCEquipmentTime = now;
        }
        HCGroupEquipment equipment = mHCEquipment;
        if (!equipment.HasMap) return;
        // 1 km navigation grid, bounded to 51 lines per axis on supported worlds.
        float worldSize = GetGame().GetWorld().GetWorldSize();
        if (!(worldSize >= 1 && worldSize <= 50000)) return;
        if (mHCGrid)
        {
            for (int cell = 0; cell <= 50; cell++)
            {
                float meters = cell * 1000;
                if (meters > worldSize) break;
                vector south = mapWidget.MapToScreen(Vector(meters, 0, 0));
                vector north = mapWidget.MapToScreen(Vector(meters, 0, worldSize));
                vector west = mapWidget.MapToScreen(Vector(0, 0, meters));
                vector east = mapWidget.MapToScreen(Vector(worldSize, 0, meters));
                mHCGrid.DrawLine(south[0], south[1], north[0], north[1], 1, ARGB(100,255,255,255));
                mHCGrid.DrawLine(west[0], west[1], east[0], east[1], 1, ARGB(100,255,255,255));
            }
        }
        if (!mHCNavigation) return;
        mHCNavigation.SetTextExactSize(Math.Round(18 * settings.LabelScale));
        if (!equipment.HasGPS)
        {
            mHCNavigation.SetText("Navigation: 1 km grid. Carry a powered GPS for own coordinates.");
            return;
        }
        // Own coordinates always need a working GPS. RequireGPS separately
        // retains the existing native navigation gate on teammate positions.
        vector actual = viewer.GetPosition();
        int eastMeters = Math.Round(actual[0]);
        int northMeters = Math.Round(actual[2]);
        mHCNavigation.SetText("Own coordinates E " + eastMeters.ToString() + " / N " + northMeters.ToString() + " m | Grid 1 km");
    }

    // Mission list for the side panel, from the pushed snapshot only.
    void Missions(HCGroupSettings settings)
    {
        if (!mHCEvents) return;
        mHCEvents.ClearItems();
        if (!settings.MissionLayer) return;
        HCMissionBeaconStore store = HCMissionBeaconStore.Get();
        float now = GetGame().GetTickTime();
        store.Poll(now);
        int used = 0;
        for (int index = 0; index < store.Count(); index++)
        {
            HCBeaconRow row = store.At(index);
            if (!row) continue;
            mHCEvents.AddItem(row.Title + ", " + row.Place + " (" + HCInfoEventCache.MinutesLeft(store.Remaining(row, now)) + " min)", null, 0);
            used++;
        }
        if (used == 0) mHCEvents.AddItem("No active missions", null, 0);
    }

    // Zone rings on the HCGrid canvas, after Navigation/HideNavigation cleared it.
    // Radius in pixels comes from one extra MapToScreen per zone; the ring is then
    // 48 short lines in screen space (same canvas coordinates as the grid).
    void DrawZones(MapWidget mapWidget, array<ref HCInfoPin> zones)
    {
        if (!mHCGrid || !mapWidget || !zones) return;
        foreach (HCInfoPin zone : zones)
        {
            if (zone.Radius < 1) continue;
            vector centre = mapWidget.MapToScreen(zone.Position);
            vector edge = mapWidget.MapToScreen(Vector(zone.Position[0] + zone.Radius, 0, zone.Position[2]));
            float pixels = Math.AbsFloat(edge[0] - centre[0]);
            if (!(pixels >= 3 && pixels <= 6000)) continue;
            float lastX = centre[0] + pixels;
            float lastY = centre[1];
            for (int segment = 1; segment <= 48; segment++)
            {
                float angle = segment * Math.PI2 / 48;
                float nextX = centre[0] + Math.Cos(angle) * pixels;
                float nextY = centre[1] + Math.Sin(angle) * pixels;
                mHCGrid.DrawLine(lastX, lastY, nextX, nextY, 3, ARGB(230,213,94,0));
                lastX = nextX;
                lastY = nextY;
            }
        }
    }

    // Client-only toggles hide drawing; they never widen what the server sent.
    void HideNavigation()
    {
        if (mHCGrid) mHCGrid.Clear();
        if (mHCNavigation) mHCNavigation.SetText("");
    }

    void HideMissions()
    {
        if (mHCEvents) mHCEvents.ClearItems();
    }

    // Admin layers only, for an allowlisted admin who carries no map item.
    void DrawAdmin(MapWidget mapWidget, HCGroupSnapshot frame)
    {
        mapWidget.ClearUserMarks();
        DrawAdminOverlay(mapWidget, frame.Settings);
    }

    // Admin pins only, from our pooled widgets; settings are passed directly so
    // no group snapshot is needed. The Expansion map uses its own marker
    // widgets instead (HollowCountryExpansionAI HCXAdminMapLayers).
    void DrawAdminOverlay(MapWidget mapWidget, HCGroupSettings settings)
    {
        if (!mapWidget || !settings) return;
        mHCUsed = 0;
        HideNavigation();
        HideMissions();
        HCAdminWorldClient.Get().Draw(this, mapWidget, settings);
        for (int unused = mHCUsed; unused < mHCPool.Count(); unused++)
            mHCPool.Get(unused).Show(false);
    }

    void Draw(MapWidget mapWidget, HCGroupSnapshot frame, PlayerBase viewer)
    {
        mapWidget.ClearUserMarks();
        mHCUsed = 0;
        HCInfoLayerFlags flags = HCInfoLayerFlags.Get();
        if (flags.ShowGrid) Navigation(mapWidget, viewer, frame.Settings);
        else HideNavigation();
        if (flags.ShowEvents) Missions(frame.Settings);
        else HideMissions();
        array<ref HCInfoPin> sites;
        if (flags.ShowEvents && frame.Settings.MissionLayer)
        {
            sites = mHCInfoEvents.Pins(GetGame().GetTickTime(), GetGame().GetWorld().GetWorldSize());
            DrawZones(mapWidget, sites);
        }
        int utc = HCGroupClock.Utc();
        HCInfoMapPins.Log(frame, utc);
        // The bound is validated by HCGroupClient; hidden entries never enter
        // this cache. Text prefixes make the palette usable without colour.
        if (flags.ShowMarkers)
        {
            foreach (HCGroupMarker marker : frame.Markers)
            {
                if (marker.ExpiresUtc > 0 && (utc < 1 || marker.ExpiresUtc <= utc)) continue;
                if (marker.Icon < 0 || marker.Icon >= eMapMarkerTypes.MARKERTYPE_MAX) continue;
                Pin(mapWidget, marker.Position, "[Marker] " + marker.Name, ARGB(255,230,159,0), frame.Settings);
            }
        }
        // Mission zone centres come from the server's public snapshot only.
        if (sites)
        {
            foreach (HCInfoPin site : sites)
                Pin(mapWidget, site.Position, site.Label, ARGB(255,213,94,0), frame.Settings);
        }
        if (flags.ShowVisited && frame.Settings.DiscoveryLayer)
        {
            foreach (HCGroupPlace place : frame.Places)
            {
                string placeLabel = HCInfoMapPins.Label(place, utc);
                if (placeLabel == "") continue;
                int placeColor = ARGB(255,240,228,66);
                if (place.Id.IndexOf("hc-lead:") == 0) placeColor = ARGB(255,204,121,167);
                if (place.Id.IndexOf("hc-found:") == 0) placeColor = ARGB(255,0,158,115);
                Pin(mapWidget, place.Position, placeLabel, placeColor, frame.Settings);
            }
        }
        if (flags.ShowTeam && frame.Settings.MapIcons)
        {
            foreach (HCGroupMember member : frame.Members)
            {
                if (!member.HasPosition || !member.Online || !member.Alive) continue;
                Pin(mapWidget, member.Position, "[Team] " + member.Name, ARGB(255,86,180,233), frame.Settings);
            }
        }
        HCAdminWorldClient.Get().Draw(this, mapWidget, frame.Settings);
        for (int unused = mHCUsed; unused < mHCPool.Count(); unused++)
            mHCPool.Get(unused).Show(false);
    }
}
