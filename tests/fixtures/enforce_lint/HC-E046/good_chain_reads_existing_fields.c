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

class HCXAIProbe
{
    ref HCXAITradeAdapter m_Port;
    bool Held()
    {
        return m_Port.Walker.m_HCPartnerHold != null;
    }
}
