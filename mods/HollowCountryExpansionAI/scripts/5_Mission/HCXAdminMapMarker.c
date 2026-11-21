// Client-local, transient admin world marker on the Expansion M map.
// Authored against installed Expansion class/API names only (CC BY-NC-ND;
// no Expansion script text copied). Installed Core/core_scripts.pbo:
// 5_Mission/DayZExpansion_Core/ExpansionMapWidgetBase.c:37-45 ctor creates
// DayZExpansion/Core/GUI/layouts/map/expansion_map_marker.layout under the
// parent and sets this as handler; :47-51 dtor unlinks it; :112-119 Update
// projects m_WorldPosition with MapToScreen (called by the menu, below);
// :121-129 OnClick -> :190 OnMarkerClick; :79 GetDropSoundEffect; :89
// IsDragWidget; :347 CanDrag; :174 SetPosition(vector); :207 Show; :229 SetName;
// :236 GetName; :241 SetIcon(ExpansionIcon) loads icon.IconPath; :264
// SetPrimaryColor; :280 SetHoverColour. ExpansionMapMarkerPlayerArrow.c:13-24
// is the installed precedent: a direct ExpansionMapWidgetBase subclass that
// ExpansionMapMenu inserts into m_Markers (navigation_scripts.pbo
// 5_Mission/DayZExpansion_Navigation/ExpansionMapMenu.c:177-209) and projects
// in its Update loop (:1354-1363). This class never touches
// ExpansionMarkerData/ExpansionMarkerModule: nothing is saved, synced or sent.
class HCXAdminMapMarker : ExpansionMapWidgetBase
{
    // Weak back-reference; the owner deletes its markers before it goes away.
    protected HCXAdminMapLayers mHCXOwner;
    // Pool slot (fixed at creation) and the admin pin it currently shows.
    protected int mHCXSlot;
    protected int mHCXPin = -1;
    protected string mHCXIconName;
    protected string mHCXTitle;
    protected string mHCXFullName;
    // The Expansion marker layout ships placeholder text ("MARKER NAME"), so the
    // first bind always writes the name, even when an unlabelled pin passes "".
    protected bool mHCXNamed;

    void HCXAdminMapMarker(Widget parent, MapWidget mapWidget, bool autoInit = true)
    {
        SetHoverColour(ARGB(255, 255, 255, 255));
        // Hidden until bound; an unbound marker would sit in the top-left corner.
        Hide();
    }

    void HCXOwn(HCXAdminMapLayers owner, int slot)
    {
        mHCXOwner = owner;
        mHCXSlot = slot;
    }

    int HCXSlot()
    {
        return mHCXSlot;
    }

    void HCXBind(int pin, vector position, string title, string fullName, string iconName, int color)
    {
        GetLayoutRoot().SetHandler(this);
        mHCXPin = pin;
        mHCXFullName = fullName;
        if (iconName != mHCXIconName)
        {
            // Only verified registry icons, never a raw path. The name is cached
            // even if lookup fails, so a missing icon is never retried per bind.
            mHCXIconName = iconName;
            ExpansionIcon icon = ExpansionIcons.Get(iconName);
            // Never leave a previous pooled pin's image after a failed lookup.
            // Installed Core/core_scripts.pbo ExpansionIcons.c:150,312.
            if (!icon) icon = ExpansionIcons.Get("Map Marker");
            if (icon)
            {
                SetIcon(icon);
                if (m_Icon) m_Icon.Show(true);
            }
            else if (m_Icon) m_Icon.Show(false);
        }
        if (!mHCXNamed || title != mHCXTitle)
        {
            mHCXNamed = true;
            mHCXTitle = title;
            SetName(title);
        }
        // Hover has its own full name even when normal labels are suppressed.
        // ExpansionMapWidgetBase.c:290 IsMouseHovering, :321/:334 hover hooks.
        if (IsMouseHovering()) SetName(mHCXFullName);
        else SetName(mHCXTitle);
        SetPrimaryColor(color);
        SetPosition(position);
        Show(true);
    }

    void HCXSuspend()
    {
        Hide();
        m_MouseHover = false;
        GetLayoutRoot().SetHandler(null);
    }

    override bool OnMouseEnter(Widget w, int x, int y)
    {
        bool handled = super.OnMouseEnter(w, x, y);
        if (IsMouseHovering()) SetName(mHCXFullName);
        return handled;
    }

    override bool OnMouseLeave(Widget w, Widget enterW, int x, int y)
    {
        bool handled = super.OnMouseLeave(w, enterW, x, y);
        if (!IsMouseHovering()) SetName(mHCXTitle);
        return handled;
    }

    // Admin pins are read-only: no drag, no drop sound, no edit.
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
        if (mHCXOwner && mHCXPin >= 0) mHCXOwner.HCXSelect(mHCXPin);
    }
}
