// Authored API bridge; no Expansion script text copied. Installed
// Navigation/navigation_scripts.pbo:5_Mission/DayZExpansion_Navigation/
// ExpansionMapMenu.c:151 Init, :1058 GetMapMenuRoot, :1098 GetMap,
// :1261 OnClick, :1269 OnShow, :1297 OnHide, :1326 Update.
// Init owns/reuses layoutRoot; OnShow/OnHide/OnClick chain to super;
// Update may close the menu. Preserve every inherited lifecycle call.
// Native scripts-1.30.164289/1_Core/proto/EnWidgets.c:125 Show,
// :142-143 SetScreenPos/SetScreenSize, :153-154 GetScreenPos/GetScreenSize,
// :169 FindAnyWidget, :181 CreateWidgets;
// 3_Game/GUI/UIScriptedMenu.c:16-17 IsVisible/IsClosing.
modded class ExpansionMapMenu
{
    protected Widget mHCXAdminOverlay;
    protected Widget mHCXAdminPins;
    protected ref HCGroupMapLayers mHCXAdminLayers;
    protected ref HCGroupSettings mHCXAdminDefaults = new HCGroupSettings;
    protected bool mHCXAdminOpen;

    override Widget Init()
    {
        Widget root = super.Init();
        if (!root || mHCXAdminOverlay) return root;
        mHCXAdminOverlay = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_admin_world_overlay.layout", root);
        if (mHCXAdminOverlay)
        {
            mHCXAdminPins = mHCXAdminOverlay.FindAnyWidget("HCMapOverlay");
            mHCXAdminLayers = new HCGroupMapLayers;
            mHCXAdminLayers.Init(mHCXAdminOverlay);
            mHCXAdminOverlay.Show(false);
        }
        return root;
    }

    override void OnShow()
    {
        super.OnShow();
        if (!mHCXAdminOverlay || !mHCXAdminPins || !mHCXAdminLayers) return;
        mHCXAdminOverlay.Show(false);
        HCAdminWorldClient.Get().Open(mHCXAdminOverlay);
        mHCXAdminOpen = true;
    }

    override void Update(float timeslice)
    {
        super.Update(timeslice);
        if (!mHCXAdminOpen || IsClosing() || !IsVisible()) return;
        MapWidget mapWidget = GetMap();
        if (!mapWidget) return;
        HCAdminWorldClient admin = HCAdminWorldClient.Get();
        admin.Tick(mapWidget);
        mHCXAdminOverlay.Show(admin.Authorized);
        // Match the actual viewport, including Expansion legend/layout changes.
        float left, top, width, height;
        mapWidget.GetScreenPos(left, top);
        mapWidget.GetScreenSize(width, height);
        mHCXAdminPins.SetScreenPos(left, top);
        mHCXAdminPins.SetScreenSize(width, height);
        HCGroupSettings settings = mHCXAdminDefaults;
        HCGroupClient groups = HCGroupClient.Get();
        HCGroupSnapshot frame;
        if (groups) frame = groups.GetSnapshot();
        if (frame && frame.Settings) settings = frame.Settings;
        // Reuse the existing dirty cache, pool and server-provided draw cap.
        mHCXAdminLayers.DrawAdminOverlay(mapWidget, settings);
    }

    override bool OnClick(Widget w, int x, int y, int button)
    {
        if (mHCXAdminOpen && HCAdminWorldClient.Get().Click(w, GetMap(), x, y)) return true;
        return super.OnClick(w, x, y, button);
    }

    override void OnHide()
    {
        if (mHCXAdminOpen)
        {
            mHCXAdminOpen = false;
            // Close unregisters Event_OnRPC before any in-flight reply can bind.
            HCAdminWorldClient.Get().Close();
        }
        if (mHCXAdminLayers) mHCXAdminLayers.Clear();
        if (mHCXAdminOverlay) mHCXAdminOverlay.Show(false);
        super.OnHide();
    }
}
