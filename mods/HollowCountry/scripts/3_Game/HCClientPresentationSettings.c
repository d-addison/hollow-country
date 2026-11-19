// HC-27 wire contract. Presentation only: never gameplay/inventory authority.
// Lead sends three ints (VERSION, increasing revision, supported mask), global
// reliable RPC_SETTINGS, targeted to the joining/reconnecting identity. No
// client preference RPC; a client can only veto locally. New mission = new DTO.
class HCClientPresentationSettings
{
    static const int VERSION = 1;
    static const int RPC_SETTINGS = 4854001;
    static const int HINTS = 1;
    static const int GRADE = 2;
    static const int SIGNS = 4;
    static const int AMBIENT = 8;
    static const int ALL = 15;
    protected int m_Revision;
    protected int m_ServerMask;
    protected bool m_Valid;

    static bool HCValidMask(int mask) { return mask >= 0 && mask <= ALL; }

    static int HCBit(string key)
    {
        if (key == "hints") { return HINTS; }
        if (key == "grade") { return GRADE; }
        if (key == "signs") { return SIGNS; }
        if (key == "ambient") { return AMBIENT; }
        return -1;
    }

    void HCInvalidate()
    {
        m_Valid = false;
        m_ServerMask = 0;
    }

    int HCEffective(int localMask)
    {
        if (!m_Valid || !HCValidMask(localMask)) { return 0; }
        return m_ServerMask & localMask;
    }

    // 1 = accepted, 0 = stale/identical, -1 = fail closed. Invalid new packets
    // retain their sane revision barrier so an older enable cannot revive them.
    int HCAccept(int version, int revision, int mask)
    {
        if (revision > 0 && revision < m_Revision) { return 0; }
        if (revision == m_Revision && m_Revision > 0)
        {
            if (m_Valid && version == VERSION && mask == m_ServerMask) { return 0; }
            m_Valid = false;
            m_ServerMask = 0;
            return -1;
        }
        m_Valid = false;
        m_ServerMask = 0;
        if (revision < 1 || revision > 2000000000) { return -1; }
        m_Revision = revision;
        if (version != VERSION || !HCValidMask(mask)) { return -1; }
        m_ServerMask = mask;
        m_Valid = true;
        return 1;
    }
}
