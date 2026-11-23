class HCXAICaravanAdapter
{
    ref HCXAIGroupHold m_HCPartnerHold;
    bool HCPartnerHeld() { return m_HCPartnerHold != null; }
}

class HCXAIGroupHold {}

class HCXAITradeAdapter
{
    ref HCXAICaravanAdapter Walker;
}

//# file: mods/HollowCountry/scripts/4_World/Fixture/FixtureOther.c
modded class HCXAICaravanAdapter
{
    int Extra() { return 1; }
}

class HCXAIProbe
{
    ref HCXAITradeAdapter m_Port;
    bool Held()
    {
        return m_Port.Walker.m_PartnerGroup != null;
    }
}
