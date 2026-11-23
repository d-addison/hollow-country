class HCPayload { int m_Value; }

class HCSink
{
    void Use(HCPayload payload) { int seen = payload.m_Value; }
}

modded class HCSink
{
    void Other() {}
}

class HCUse
{
    void Run()
    {
        HCSink sink = new HCSink;
        sink.Use(new HCPayload);
    }
}
