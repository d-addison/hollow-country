// Authored API bridge; no Expansion script text copied. Installed
// Navigation/navigation_scripts.pbo:5_Mission/DayZExpansion_Navigation/
// ExpansionMapMenu.c:19 m_Markers (array<ref ExpansionMapWidgetBase>), :209
// player arrow inserted the same way, :1058 GetMapMenuRoot, :1098 GetMap,
// :1269 OnShow, :1297 OnHide, :1326 Update, :1343 M toggle gated by
// IsEditingMarker, :1354-1363 per-frame Update of every m_Markers entry,
// :1497 IsEditingMarker. Expansion removes only its own markers by identity
// (Find/Remove) or after casting to ExpansionMapMarker (:844-847, :1121-1124),
// so HC admin markers are never edited, deleted, saved or synced by it.
// Native scripts-1.30.164289/3_Game/tools/UIScriptedMenu.c:16-17
// IsVisible/IsClosing; 1_Core/proto/EnScript.c:407 Insert, :470 RemoveOrdered.
modded class ExpansionMapMenu
{
    protected ref HCXAdminMapLayers mHCXAdmin;

    void ~ExpansionMapMenu()
    {
        if (mHCXAdmin)
        {
            mHCXAdmin.Close();
            mHCXAdmin.ReleaseWidgets();
        }
    }

    override void OnShow()
    {
        super.OnShow();
        if (!mHCXAdmin) mHCXAdmin = new HCXAdminMapLayers;
        mHCXAdmin.Open(this, GetMapMenuRoot(), GetMap());
    }

    override void Update(float timeslice)
    {
        super.Update(timeslice);
        // super.Update may have closed the menu.
        if (!mHCXAdmin || IsClosing() || !IsVisible()) return;
        mHCXAdmin.Update();
    }

    override bool IsEditingMarker()
    {
        if (mHCXAdmin && mHCXAdmin.IsTyping()) return true;
        return super.IsEditingMarker();
    }

    override void OnHide()
    {
        if (mHCXAdmin) mHCXAdmin.Close();
        super.OnHide();
    }

    // Client-local transient admin markers join Expansion's own projection loop.
    void HCXInsertAdminMarker(ExpansionMapWidgetBase marker)
    {
        if (marker && m_Markers) m_Markers.Insert(marker);
    }

    // Drop admin markers whose pool slot is >= keep (0 drops all of them).
    void HCXTrimAdminMarkers(int keep)
    {
        if (!m_Markers) return;
        for (int index = m_Markers.Count() - 1; index >= 0; index--)
        {
            HCXAdminMapMarker marker = HCXAdminMapMarker.Cast(m_Markers[index]);
            if (marker && marker.HCXSlot() >= keep) m_Markers.RemoveOrdered(index);
        }
    }
}
