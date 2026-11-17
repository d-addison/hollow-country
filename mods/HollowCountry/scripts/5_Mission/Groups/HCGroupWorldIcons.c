// Server-supplied positions only; no player/entity enumeration or extrapolation.
class HCGroupWorldIcons
{
    protected ref array<Widget> mHCPool = new array<Widget>();
    protected int mHCGroup;
    protected int mHCEpoch;

    void Clear()
    {
        foreach (Widget widget : mHCPool)
            if (widget) widget.Unlink();
        mHCPool.Clear();
        mHCGroup = 0;
        mHCEpoch = 0;
    }

    void HideUnused(int used)
    {
        for (int i = used; i < mHCPool.Count(); i++)
            mHCPool.Get(i).Show(false);
    }

    Widget FindIconSlot(int index)
    {
        if (index < 0 || index >= 90) return null;
        if (index == mHCPool.Count())
        {
            Widget widget = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_group_icon.layout");
            if (!widget) return null;
            mHCPool.Insert(widget);
        }
        return mHCPool.Get(index);
    }

    static void Scale(Widget root, TextWidget label, ImageWidget image, HCGroupSettings settings)
    {
        float iconSize = 16 * settings.IconScale;
        float textHeight = 24 * settings.LabelScale;
        float labelLeft = iconSize + 8;
        root.SetSize(labelLeft + 180 * settings.LabelScale, Math.Max(iconSize, textHeight));
        image.SetPos(0, 0);
        image.SetSize(iconSize, iconSize);
        label.SetPos(labelLeft, 0);
        label.SetSize(180 * settings.LabelScale, textHeight);
        label.SetTextExactSize(Math.Round(textHeight));
        label.SetColor(ARGB(255,255,255,255));
    }

    static string RoleLabel(int role)
    {
        if (role == HCGroupRole.OWNER) return "Owner";
        if (role == HCGroupRole.OFFICER) return "Officer";
        return "Member";
    }

    void Update(HCGroupSnapshot frame)
    {
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!frame || !viewer || !viewer.IsAlive())
        { Clear(); return; }
        if (viewer.IsUnconscious())
        {
            Clear();
            return;
        }
        if (!frame.Enabled || frame.GroupId < 1 || !frame.Settings.WorldIcons)
        { Clear(); return; }
        if (frame.GroupId != mHCGroup || frame.Epoch != mHCEpoch)
        {
            Clear();
            mHCGroup = frame.GroupId;
            mHCEpoch = frame.Epoch;
        }
        if (GetGame().GetUIManager().GetMenu() || !viewer.GetIdentity())
        { HideUnused(0); return; }
        string localId = viewer.GetIdentity().GetId();
        vector camera = GetGame().GetCurrentCameraPosition();
        vector forward = GetGame().GetCurrentCameraDirection();
        int used;
        foreach (HCGroupMember member : frame.Members)
        {
            if (used >= 90) break;
            if (!member.HasPosition || !member.Online || !member.Alive)
                continue;
            if (member.Id == localId) continue;
            vector delta = member.Position - viewer.GetPosition();
            float squared = delta[0]*delta[0] + delta[1]*delta[1] + delta[2]*delta[2];
            float maximum = frame.Settings.MaxIconDistance;
            if (squared > maximum*maximum) continue;
            vector facing = member.Position - camera;
            float dot = facing[0]*forward[0] + facing[1]*forward[1] + facing[2]*forward[2];
            if (!(dot > 0)) continue;
            vector relative = GetGame().GetScreenPosRelative(member.Position);
            if (relative[0] < 0 || relative[0] > 1) continue;
            if (relative[1] < 0 || relative[1] > 1) continue;
            Widget root = FindIconSlot(used);
            if (!root) break;
            TextWidget label = TextWidget.Cast(root.FindAnyWidget("HCLabel"));
            if (!label) { Clear(); return; }
            ImageWidget image = ImageWidget.Cast(root.FindAnyWidget("HCMark"));
            if (!image) { Clear(); return; }
            Scale(root, label, image, frame.Settings);
            image.SetColor(ARGB(255,86,180,233));
            label.SetText("[Team] " + member.Name);
            vector screen = GetGame().GetScreenPos(member.Position);
            root.SetPos(screen[0] - 90, screen[1] - 24);
            root.Show(true);
            used++;
        }
        HideUnused(used);
    }

    static void DrawMap(MapWidget widget, HCGroupSnapshot frame)
    {
        if (!widget) return;
        widget.ClearUserMarks();
        if (!frame || !frame.Enabled || frame.GroupId < 1) return;
        string texture = "\\dz\\gear\\navigation\\data\\map_tree_ca.paa";
        int utc = HCGroupClock.Utc();
        foreach (HCGroupMarker marker : frame.Markers)
        {
            if (marker.Icon < 0 || marker.Icon >= eMapMarkerTypes.MARKERTYPE_MAX)
                continue;
            if (marker.ExpiresUtc > 0)
            {
                if (utc < 1 || marker.ExpiresUtc <= utc) continue;
            }
            string markerTexture = MapMarkerTypes.GetMarkerTypeFromID(marker.Icon);
            if (markerTexture == "")
                continue;
            widget.AddUserMark(marker.Position, marker.Name, marker.Color, markerTexture);
        }
        if (!frame.Settings.MapIcons) return;
        foreach (HCGroupMember member : frame.Members)
        {
            if (!member.HasPosition || !member.Online || !member.Alive)
                continue;
            widget.AddUserMark(member.Position, member.Name, ARGB(255,70,200,220), texture);
        }
    }
}
