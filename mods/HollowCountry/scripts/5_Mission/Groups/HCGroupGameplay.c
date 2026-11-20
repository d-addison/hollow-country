// Coordinator-owned CreateScriptedMenu must bind HCGroupProtocol.MENU_MAP.
modded class MissionGameplay
{
    protected ref HCGroupClient mHCGroupClient;
    protected ref HCGroupWorldIcons mHCGroupIcons;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsServer()) return;
        mHCGroupClient = HCGroupClient.Get();
        mHCGroupClient.Start();
        mHCGroupIcons = new HCGroupWorldIcons;
    }

    override void OnUpdate(float timeslice)
    {
        if (mHCGroupClient)
        {
            mHCGroupClient.Update();
            HCGroupSnapshot frame = mHCGroupClient.GetSnapshot();
            PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
            bool conscious = false;
            if (viewer && viewer.IsAlive())
            {
                conscious = !viewer.IsUnconscious();
            }
            if (frame && frame.Enabled && conscious)
            {
                if (!IsControlDisabled() && !GetGame().GetUIManager().GetMenu())
                {
                    if (GetGame().GetInput().LocalPress_ID(UAMapToggle))
                        GetGame().GetUIManager().EnterScriptedMenu(HCGroupProtocol.MENU_MAP, null);
                }
            }
            if (mHCGroupIcons) mHCGroupIcons.Update(frame);
        }
        super.OnUpdate(timeslice);
    }

    override void OnMissionFinish()
    {
        UIScriptedMenu groupMenu = GetGame().GetUIManager().FindMenu(HCGroupProtocol.MENU_MAP);
        if (groupMenu) groupMenu.Close();
        if (mHCGroupIcons) mHCGroupIcons.Clear();
        if (mHCGroupClient) mHCGroupClient.Stop();
        mHCGroupIcons = null;
        mHCGroupClient = null;
        super.OnMissionFinish();
    }
}
