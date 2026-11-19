// Client-side information layers for the group map. Server data remains
// authoritative: these classes only choose what the client draws from
// payloads it was already sent (the validated group frame and the public event
// view). Nothing here reads other characters, items, infected or world state.
// Native: 1_Core/proto/EnString.c IndexOf/IndexOfFrom/Substring/Length/Trim/
// Get/ToFloat; 1_Core/proto/EnWidgets.c CreateWidgets/FindAnyWidget/GetName/
// ButtonWidget.SetText.
// V2 pins: scripts-1.30.164289/1_Core/proto/EnString.c:240 (IndexOf),
// 3_Game/Global/Game.c:914 (GetTickTime), 1_Core/proto/EnConvert.c:30
// (int.ToString), 1_Core/proto/EnDebug.c:96 (Print). Only validated frame data.

class HCInfoMapPins
{
    protected static float s_HCLastLog = -60;

    static string Label(HCGroupPlace place, int utc)
    {
        if (place.Id.IndexOf("hc-ping:") == 0)
        {
            if (utc < 1 || place.HCPinExpiresUtc <= utc) { return ""; }
            return "[Team ping] " + place.Name;
        }
        if (place.Id.IndexOf("hc-found:") == 0) { return "found: " + place.Name; }
        if (place.Id.IndexOf("hc-death:") == 0)
        {
            if (utc < 1 || place.HCPinExpiresUtc <= utc) { return ""; }
            return place.Name;
        }
        if (place.Id.IndexOf("hc-lead:") == 0)
        {
            if (utc < 1 || place.HCPinExpiresUtc <= utc) { return ""; }
            return "lead: " + place.Name;
        }
        return "[Visited] " + place.Name;
    }

    // Static cadence survives closing/reopening the map and counts received,
    // unexpired pins, including ones currently outside the map viewport.
    static void Log(HCGroupSnapshot frame, int utc)
    {
        float now = GetGame().GetTickTime();
        if (now >= s_HCLastLog && now - s_HCLastLog < 60) { return; }
        s_HCLastLog = now;
        int trailCount = 0;
        int leadCount = 0;
        int deathCount = 0;
        foreach (HCGroupPlace pin : frame.Places)
        {
            if (pin.Id.IndexOf("hc-found:") == 0) { trailCount++; }
            if (pin.Id.IndexOf("hc-lead:") == 0 && Label(pin, utc) != "") { leadCount++; }
            if (pin.Id.IndexOf("hc-death:") == 0 && Label(pin, utc) != "") { deathCount++; }
        }
        Print("[HollowCountry] V2 client map pins trail=" + trailCount.ToString() + " leads=" + leadCount.ToString() + " deaths=" + deathCount.ToString());
    }
}

// One drawable known-event site: a label, a position and the joined flag.
class HCInfoPin
{
    vector Position;
    string Label;
    bool Joined = false;
}

// Legacy parser retained for source compatibility. HC-38 Collect never
// promotes even a parseable stale quest briefing into a task marker.
class HCInfoEventSites
{
    static bool NumberText(string text)
    {
        int length = text.Length();
        if (length < 1 || length > 16)
        {
            return false;
        }
        string allowed = "0123456789";
        int digits = 0;
        int dots = 0;
        for (int index = 0; index < length; index++)
        {
            string glyph = text.Get(index);
            if (glyph == "-" && index == 0)
            {
                continue;
            }
            if (glyph == ".")
            {
                dots++;
                if (dots > 1)
                {
                    return false;
                }
                continue;
            }
            if (allowed.IndexOf(glyph) < 0)
            {
                return false;
            }
            digits++;
        }
        return digits > 0;
    }

    static bool ParseSite(string briefing, float worldSize, HCInfoPin pin)
    {
        if (!pin || briefing.Length() < 14 || briefing.Length() > 1024)
        {
            return false;
        }
        if (briefing.IndexOf("Site ") != 0)
        {
            return false;
        }
        int lineEnd = briefing.IndexOf("\n");
        if (lineEnd < 0)
        {
            lineEnd = briefing.Length();
        }
        string line = briefing.Substring(0, lineEnd);
        int siteAt = line.IndexOf(" at <");
        // Site ids are 1..48 characters after the five-character prefix.
        if (siteAt < 6 || siteAt > 53)
        {
            return false;
        }
        int closeAt = line.IndexOfFrom(siteAt + 5, ">");
        if (closeAt != line.Length() - 1)
        {
            return false;
        }
        string inner = line.Substring(siteAt + 5, closeAt - siteAt - 5);
        int first = inner.IndexOf(",");
        if (first < 1)
        {
            return false;
        }
        int second = inner.IndexOfFrom(first + 1, ",");
        if (second < first + 2)
        {
            return false;
        }
        if (inner.IndexOfFrom(second + 1, ",") >= 0)
        {
            return false;
        }
        string xText = inner.Substring(0, first).Trim();
        string yText = inner.Substring(first + 1, second - first - 1).Trim();
        string zText = inner.Substring(second + 1, inner.Length() - second - 1).Trim();
        if (!NumberText(xText) || !NumberText(yText) || !NumberText(zText))
        {
            return false;
        }
        float x = xText.ToFloat();
        float z = zText.ToFloat();
        vector position = Vector(x, yText.ToFloat(), z);
        if (!HCGroupRules.PositionValid(position))
        {
            return false;
        }
        if (x > worldSize || z > worldSize)
        {
            return false;
        }
        pin.Position = position;
        return true;
    }

    // HC-38: even an old/stale public view cannot create task markers.
    static void Collect(HCEventPublicView view, float worldSize, array<ref HCInfoPin> pins)
    {
        if (pins) { pins.Clear(); }
    }
}

// HC-38: always empty; map redraws perform no event/network/clock query.
class HCInfoEventCache
{
    protected ref array<ref HCInfoPin> mHCPins = new array<ref HCInfoPin>();
    protected float mHCStamp = -100.0;

    void Clear()
    {
        mHCPins.Clear();
        mHCStamp = -100.0;
    }

    array<ref HCInfoPin> Pins(float now, float worldSize)
    {
        Clear();
        return mHCPins;
    }
}

// Session-only visibility switches. They hide client drawing; they never
// request, widen or cache anything from the server.
class HCInfoLayerFlags
{
    protected static ref HCInfoLayerFlags s_Instance;
    bool ShowEvents = false;
    bool ShowVisited = true;
    bool ShowTeam = true;
    bool ShowMarkers = true;
    bool ShowGrid = true;

    static HCInfoLayerFlags Get()
    {
        if (!s_Instance)
        {
            s_Instance = new HCInfoLayerFlags;
        }
        return s_Instance;
    }

    static string StateText(string name, bool on)
    {
        if (on)
        {
            return name + ": on";
        }
        return name + ": off";
    }

    bool Toggle(string action)
    {
        if (action == "HCInfoToggleEvents")
        {
            ShowEvents = false;
            return true;
        }
        if (action == "HCInfoToggleVisited")
        {
            ShowVisited = !ShowVisited;
            return true;
        }
        if (action == "HCInfoToggleTeam")
        {
            ShowTeam = !ShowTeam;
            return true;
        }
        if (action == "HCInfoToggleMarkers")
        {
            ShowMarkers = !ShowMarkers;
            return true;
        }
        if (action == "HCInfoToggleGrid")
        {
            ShowGrid = !ShowGrid;
            return true;
        }
        return false;
    }

    string Label(string action)
    {
        if (action == "HCInfoToggleEvents")
        {
            return "";
        }
        if (action == "HCInfoToggleVisited")
        {
            return StateText("Visited", ShowVisited);
        }
        if (action == "HCInfoToggleTeam")
        {
            return StateText("Team", ShowTeam);
        }
        if (action == "HCInfoToggleMarkers")
        {
            return StateText("Markers", ShowMarkers);
        }
        if (action == "HCInfoToggleGrid")
        {
            return StateText("Grid", ShowGrid);
        }
        return "";
    }
}

// Owns the toggle strip widget created over the map.
class HCInfoLayerControls
{
    protected Widget mHCPanel;

    void Init(Widget root)
    {
        mHCPanel = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_info_layers.layout", root);
        Refresh();
    }

    bool OnClick(Widget w)
    {
        if (!w || !mHCPanel)
        {
            return false;
        }
        if (!HCInfoLayerFlags.Get().Toggle(w.GetName()))
        {
            return false;
        }
        Refresh();
        return true;
    }

    void Refresh()
    {
        SetLabel("HCInfoToggleEvents");
        SetLabel("HCInfoToggleVisited");
        SetLabel("HCInfoToggleTeam");
        SetLabel("HCInfoToggleMarkers");
        SetLabel("HCInfoToggleGrid");
    }

    protected void SetLabel(string action)
    {
        if (!mHCPanel)
        {
            return;
        }
        ButtonWidget button = ButtonWidget.Cast(mHCPanel.FindAnyWidget(action));
        if (button)
        {
            // Native EnWidgets.c:125 Show. No quest toggle in the map strip.
            if (action == "HCInfoToggleEvents") { button.Show(false); return; }
            button.SetText(HCInfoLayerFlags.Get().Label(action));
        }
    }
}
