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
    bool Held(HCXAITradeAdapter port)
    {
        return port.Walker.m_PartnerGroup != null;
    }
}
