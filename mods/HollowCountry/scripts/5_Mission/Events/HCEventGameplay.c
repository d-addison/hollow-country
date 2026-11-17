// Native input declaration/binding is coordinator-owned. No native input is
// repurposed; undeclared UAHollowCountryEvents simply cannot open this menu.
modded class MissionGameplay
{
    protected ref HCEventClient m_HCEventClient;
    // Resolved once per mission; undeclared stays null and is not looked up again.
    protected UAInput m_HCEventInput;
    protected bool m_HCEventInputResolved;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsServer()) { return; }
        m_HCEventClient = HCEventClient.Get();
        m_HCEventClient.Start();
        m_HCEventInput = null;
        m_HCEventInputResolved = false;
        if (GetUApi())
        {
            m_HCEventInput = GetUApi().GetInputByName("UAHollowCountryEvents");
            m_HCEventInputResolved = true;
        }
        if (!m_HCEventInput)
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
                    if (!m_HCEventInputResolved)
                    {
                        m_HCEventInput = GetUApi().GetInputByName("UAHollowCountryEvents");
                        m_HCEventInputResolved = true;
                    }
                    if (m_HCEventInput && m_HCEventInput.LocalPress())
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
        m_HCEventInput = null;
        m_HCEventInputResolved = false;
        super.OnMissionFinish();
    }
}
