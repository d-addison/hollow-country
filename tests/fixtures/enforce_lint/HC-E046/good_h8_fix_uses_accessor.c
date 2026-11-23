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

class HCXAITradeProducer
{
    ref HCXAITradeAdapter m_Port;
    void Settle()
    {
        if (m_Port.Walker && m_Port.Walker.HCPartnerHeld()) { return; }
    }
}
