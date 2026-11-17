// Native input declaration/binding is coordinator-owned. No native input is
// repurposed; undeclared UAHollowCountryEvents simply cannot open this menu.
modded class MissionGameplay
{
    protected ref HCEventClient m_HCEventClient;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsServer()) { return; }
        m_HCEventClient = HCEventClient.Get();
        m_HCEventClient.Start();
        if (!GetUApi() || !GetUApi().GetInputByName("UAHollowCountryEvents"))
        {
            Print("[HC Events] optional menu input UAHollowCountryEvents is not declared/bound");
        }
    }
    override void OnUpdate(float timeslice)
    {
        if (m_HCEventClient)
        {
            m_HCEventClient.Update();
            PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
            if (viewer && viewer.IsAlive() && !viewer.IsUnconscious())
            {
                if (!IsControlDisabled() && !GetGame().GetUIManager().GetMenu() && GetUApi())
                {
                    UAInput input = GetUApi().GetInputByName("UAHollowCountryEvents");
                    if (input && input.LocalPress())
                    {
                        GetGame().GetUIManager().EnterScriptedMenu(HCEventWire.MENU_EVENTS, null);
                    }
                }
            }
        }
        super.OnUpdate(timeslice);
    }
    override void OnMissionFinish()
    {
        UIScriptedMenu menu = GetGame().GetUIManager().FindMenu(HCEventWire.MENU_EVENTS);
        if (menu) { menu.Close(); }
        if (m_HCEventClient) { m_HCEventClient.Stop(); }
        m_HCEventClient = null;
        super.OnMissionFinish();
    }
}
