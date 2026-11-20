// Server-supplied positions only; no player/entity enumeration or extrapolation.
class HCGroupWorldIcons
{
    protected ref array<Widget> mHCPool = new array<Widget>();
    // Per pool slot caches, index-parallel with mHCPool. They remove the
    // per-frame FindAnyWidget lookups and redundant Scale/SetText writes.
    protected ref array<TextWidget> mHCLabels = new array<TextWidget>();
    protected ref array<ImageWidget> mHCImages = new array<ImageWidget>();
    protected ref array<string> mHCNames = new array<string>();
    protected ref array<bool> mHCTexted = new array<bool>();
    protected ref array<int> mHCStyled = new array<int>();
    protected int mHCStyleEpoch = 1;
    protected float mHCStyleIcon;
    protected float mHCStyleLabel;
    protected int mHCGroup;
    protected int mHCEpoch;

    void Clear()
    {
        foreach (Widget widget : mHCPool)
            if (widget) widget.Unlink();
        mHCPool.Clear();
        mHCLabels.Clear();
        mHCImages.Clear();
        mHCNames.Clear();
        mHCTexted.Clear();
        mHCStyled.Clear();
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
            TextWidget label = TextWidget.Cast(widget.FindAnyWidget("HCLabel"));
            ImageWidget image = ImageWidget.Cast(widget.FindAnyWidget("HCMark"));
            if (!label || !image)
            {
                widget.Unlink();
                Clear();
                return null;
            }
            mHCPool.Insert(widget);
            mHCLabels.Insert(label);
            mHCImages.Insert(image);
            mHCNames.Insert("");
            mHCTexted.Insert(false);
            mHCStyled.Insert(0);
        }
        return mHCPool.Get(index);
    }

    static void Scale(Widget root, TextWidget label, ImageWidget image, HCGroupSettings settings)
    {
        float iconSize = 16 * settings.IconScale;
        float textHeight = 24 * settings.LabelScale;
        float labelLeft = iconSize + 8;
        root.SetSize(labelLeft + 360 * settings.LabelScale, Math.Max(iconSize, textHeight));
        image.SetPos(0, 0);
        image.SetSize(iconSize, iconSize);
        label.SetPos(labelLeft, 0);
        label.SetSize(360 * settings.LabelScale, textHeight);
        label.SetTextExactSize(Math.Round(textHeight));
        label.SetColor(ARGB(255,255,255,255));
    }

    // Native 1.30.164289: 1_Core/proto/EnConvert.c:30 int.ToString.
    static string StatusLabel(HCGroupMember member, bool compact = false)
    {
        if (!member.HasPosition || !member.Online || !member.Alive) return "";
        if (member.HealthBand < 0 || member.BloodBand < 0) return "";
        string text = "  HP " + member.HealthBand.ToString() + "/4  BL " + member.BloodBand.ToString() + "/4";
        if (compact) text = " H" + member.HealthBand.ToString() + " B" + member.BloodBand.ToString();
        if (member.Bleeding)
        {
            if (compact) text += " BLEED";
            else text += " BLEEDING";
        }
        if (member.Unconscious)
        {
            if (compact) text += " UNC";
            else text += " UNCONSCIOUS";
        }
        return text;
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
        if (frame.Settings.IconScale != mHCStyleIcon || frame.Settings.LabelScale != mHCStyleLabel)
        {
            // Scale() depends on these two values only. A new epoch makes every
            // slot restyle once on its next use.
            mHCStyleIcon = frame.Settings.IconScale;
            mHCStyleLabel = frame.Settings.LabelScale;
            mHCStyleEpoch++;
        }
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
            if (mHCStyled.Get(used) != mHCStyleEpoch)
            {
                Scale(root, mHCLabels.Get(used), mHCImages.Get(used), frame.Settings);
                mHCImages.Get(used).SetColor(ARGB(255,86,180,233));
                mHCStyled.Set(used, mHCStyleEpoch);
            }
            string displayName = "[Team] " + member.Name + StatusLabel(member, true);
            if (!mHCTexted.Get(used) || mHCNames.Get(used) != displayName)
            {
                mHCLabels.Get(used).SetText(displayName);
                mHCNames.Set(used, displayName);
                mHCTexted.Set(used, true);
            }
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
