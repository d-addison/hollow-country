class HCPayload { int m_Value; }

class HCStatic
{
    static void Read(HCPayload payload) { int seen = payload.m_Value; }
}

class HCUse
{
    void Run()
    {
        HCStatic.Read(new HCPayload);
    }
}
