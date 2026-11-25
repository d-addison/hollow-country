// Observe the existing group handshake without changing admission, validation or transport.
modded class HCGroupClient
{
    protected int m_HCDriverFrames;
    protected int m_HCDriverRejected;
    protected bool m_HCDriverDisabled;

    override bool ReceiveSnapshot(HCGroupSnapshot frame)
    {
        bool accepted = super.ReceiveSnapshot(frame);
        if (m_HCDriverFrames < 1000000) { m_HCDriverFrames++; }
        if (!accepted && m_HCDriverRejected < 1000000) { m_HCDriverRejected++; }
        if (accepted) { m_HCDriverDisabled = !frame.Enabled; }
        return accepted;
    }

    bool HCDriverServiceDisabled() { return m_HCDriverDisabled; }

    string HCDriverReadiness()
    {
        int listening = 0;
        int session = 0;
        int sync = 0;
        if (m_Listening) { listening = 1; }
        if (m_Session != "") { session = 1; }
        if (m_SyncTicket != 0) { sync = 1; }
        return " listening=" + listening.ToString() + " session=" + session.ToString() + " sync_pending=" + sync.ToString() + " frames=" + m_HCDriverFrames.ToString() + " rejected=" + m_HCDriverRejected.ToString();
    }
}
