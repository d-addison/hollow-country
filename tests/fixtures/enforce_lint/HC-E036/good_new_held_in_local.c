class HCPayload { int m_Value; }

class HCSink
{
    void Use(HCPayload payload) { int seen = payload.m_Value; }
    void Keep(HCPayload payload) { m_Held = payload; }
    ref HCPayload m_Held;
}

class HCUse
{
    void Run()
    {
        HCSink sink = new HCSink;
        HCPayload payload = new HCPayload;
        sink.Use(payload);
    }
}
