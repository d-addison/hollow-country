// Original overlays over the native pannable/zoomable MapWidget. The Events
// public view has no location: render known titles, never infer mission pins.
class HCGroupMapLayers
{
    protected Widget mHCOverlay;
    protected CanvasWidget mHCGrid;
    protected TextWidget mHCNavigation;
    protected TextListboxWidget mHCEvents;
    protected ref array<Widget> mHCPool = new array<Widget>();
    protected int mHCUsed;
    protected ref array<string> mHCTextures = new array<string>();
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
        mHCTextures.Clear();
        mHCEquipment = null;
        mHCViewer = null;
        mHCInfoEvents.Clear();
        if (mHCGrid) mHCGrid.Clear();
        if (mHCNavigation) mHCNavigation.SetText("");
        if (mHCEvents) mHCEvents.ClearItems();
        mHCUsed = 0;
    }

    void Pin(MapWidget mapWidget, vector position, string title, int color, string texture, HCGroupSettings settings)
    {
        if (!mHCOverlay || mHCUsed >= 602) return;
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
            mHCTextures.Insert("");
        }
        Widget pinRoot = mHCPool.Get(mHCUsed);
        TextWidget label = TextWidget.Cast(pinRoot.FindAnyWidget("HCLabel"));
        ImageWidget image = ImageWidget.Cast(pinRoot.FindAnyWidget("HCMark"));
        if (!label || !image) return;
        HCGroupWorldIcons.Scale(pinRoot, label, image, settings);
        label.SetText(title);
        if (mHCTextures.Get(mHCUsed) != texture)
        {
            image.LoadImageFile(0, texture);
            mHCTextures.Set(mHCUsed, texture);
        }
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

    void Missions(HCGroupSettings settings)
    {
        if (!mHCEvents) return;
        mHCEvents.ClearItems();
        if (!settings.MissionLayer) return;
        HCEventClient events = HCEventClient.Get();
        if (!events || !events.Fresh())
        {
            mHCEvents.AddItem("Missions: waiting for fresh known events", null, 0);
            return;
        }
        HCEventPublicView known = events.GetView();
        if (!known || !known.Enabled) return;
        int used = 0;
        foreach (HCEventPublicRow row : known.Rows)
        {
            if (used >= 32) break;
            if (row.RemainingSeconds <= 0 || row.Status < HCEventStatus.ANNOUNCED || row.Status > HCEventStatus.ACTIVE) continue;
            string participation = "[Known] ";
            if (row.Joined) participation = "[Joined] ";
            mHCEvents.AddItem(participation + row.Title + " (" + row.RemainingSeconds.ToString() + "s)", null, 0);
            used++;
        }
        if (used == 0) mHCEvents.AddItem("No active known missions", null, 0);
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

    void Draw(MapWidget mapWidget, HCGroupSnapshot frame, PlayerBase viewer)
    {
        mapWidget.ClearUserMarks();
        mHCUsed = 0;
        HCInfoLayerFlags flags = HCInfoLayerFlags.Get();
        if (flags.ShowGrid) Navigation(mapWidget, viewer, frame.Settings);
        else HideNavigation();
        if (flags.ShowEvents) Missions(frame.Settings);
        else HideMissions();
        string texture = "\\dz\\gear\\navigation\\data\\map_tree_ca.paa";
        int utc = HCGroupClock.Utc();
        // The bound is validated by HCGroupClient; hidden entries never enter
        // this cache. Text prefixes make the palette usable without colour.
        if (flags.ShowMarkers)
        {
            foreach (HCGroupMarker marker : frame.Markers)
            {
                if (marker.ExpiresUtc > 0 && (utc < 1 || marker.ExpiresUtc <= utc)) continue;
                if (marker.Icon < 0 || marker.Icon >= eMapMarkerTypes.MARKERTYPE_MAX) continue;
                string markerTexture = MapMarkerTypes.GetMarkerTypeFromID(marker.Icon);
                Pin(mapWidget, marker.Position, "[Marker] " + marker.Name, ARGB(255,230,159,0), markerTexture, frame.Settings);
            }
        }
        // Known-event sites come from the already-public event rows only.
        if (flags.ShowEvents && frame.Settings.MissionLayer)
        {
            float worldSize = GetGame().GetWorld().GetWorldSize();
            array<ref HCInfoPin> sites = mHCInfoEvents.Pins(GetGame().GetTickTime(), worldSize);
            foreach (HCInfoPin site : sites)
                Pin(mapWidget, site.Position, site.Label, ARGB(255,213,94,0), texture, frame.Settings);
        }
        if (flags.ShowVisited && frame.Settings.DiscoveryLayer)
        {
            foreach (HCGroupPlace place : frame.Places)
                Pin(mapWidget, place.Position, "[Visited] " + place.Name, ARGB(255,240,228,66), texture, frame.Settings);
        }
        if (flags.ShowTeam && frame.Settings.MapIcons)
        {
            foreach (HCGroupMember member : frame.Members)
            {
                if (!member.HasPosition || !member.Online || !member.Alive) continue;
                Pin(mapWidget, member.Position, "[Team] " + member.Name, ARGB(255,86,180,233), texture, frame.Settings);
            }
        }
        for (int unused = mHCUsed; unused < mHCPool.Count(); unused++)
            mHCPool.Get(unused).Show(false);
    }
}
