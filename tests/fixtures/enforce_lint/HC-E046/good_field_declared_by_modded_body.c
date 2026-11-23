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

modded class HCXAICaravanAdapter
{
    ref HCXAIGroupHold m_PartnerGroup;
}

class HCXAIProbe
{
    ref HCXAITradeAdapter m_Port;
    bool Held()
    {
        return m_Port.Walker.m_PartnerGroup != null;
    }
}
