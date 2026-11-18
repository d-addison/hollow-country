// W6 #123/#133. Native scripts-1.30.164289:
// 5_Mission/mission/missionGameplay.c:102 OnInit, :318 UIManager.FindMenu,
// :287 OnUpdate, :1119 IsControlDisabled; 3_Game/InputAPI/UAInput.c:60 LocalPress, :218 GetInputByName,
// :279 GetUApi; Global/Game.c:1120 IsServer; 5_Mission/mission/missionBase.c:198
// CreateScriptedMenu; 3_Game/tools/UIScriptedMenu.c:146 SetID, :31 Close.
// Global/Game.c:943 GetUIManager; gameplay.c:636 GetGame;
// 3_Game/tools/UIManager.c:59 GetMenu, :159 FindMenu.
// One input check/frame. No client allocation or request until the key is used.
modded class MissionGameplay
{
    protected UAInput m_HCAdminInput;
    protected ref HCAdminClient m_HCAdminClient;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsServer()) { return; }
        if (GetUApi()) { m_HCAdminInput = GetUApi().GetInputByName("UAHollowCountryAdmin"); }
    }

    override void OnUpdate(float timeslice)
    {
        if (m_HCAdminClient) { m_HCAdminClient.HCTick(); }
        if (m_HCAdminInput && m_HCAdminInput.LocalPress())
        {
            if (!IsControlDisabled() && !GetGame().GetUIManager().GetMenu())
            {
                m_HCAdminClient = HCAdminClient.HCGet();
                m_HCAdminClient.HCOpen();
            }
        }
        super.OnUpdate(timeslice);
    }

    override void OnMissionFinish()
    {
        UIScriptedMenu menu = GetGame().GetUIManager().FindMenu(HCAdminWire.MENU);
        if (menu) { menu.Close(); }
        if (m_HCAdminClient) { m_HCAdminClient.HCStop(); }
        m_HCAdminClient = null;
        m_HCAdminInput = null;
        super.OnMissionFinish();
    }
}

modded class MissionBase
{
    override UIScriptedMenu CreateScriptedMenu(int id)
    {
        if (id == HCAdminWire.MENU)
        {
            HCAdminClient client = HCAdminClient.HCGet();
            if (!client.HCValid()) { return null; }
            UIScriptedMenu menu = new HCAdminMenu;
            menu.SetID(id);
            return menu;
        }
        return super.CreateScriptedMenu(id);
    }
}
