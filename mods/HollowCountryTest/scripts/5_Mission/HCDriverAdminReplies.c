// Driver-only observation of the product's validated, correlated reply. UI Revision also changes
// on mark expiry; it is not a reply serial. No RPC is read twice and no product behavior changes.
modded class HCAdminClient
{
    protected int m_HCDriverReplySerial;
    protected string m_HCDriverReplyNotice;

    override void HCReceive(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        // A reconnect can make HCReceive call HCStop instead of consuming a reply.
        bool pending = m_Pending && m_Player == GetGame().GetPlayer();
        super.HCReceive(sender, target, rpcType, ctx);
        if (pending && !m_Pending && rpcType == HCAdminWire.REPLY)
        {
            m_HCDriverReplySerial++;
            m_HCDriverReplyNotice = Notice;
        }
    }

    int HCDriverReplySerial() { return m_HCDriverReplySerial; }
    string HCDriverReplyNotice() { return m_HCDriverReplyNotice; }
}
