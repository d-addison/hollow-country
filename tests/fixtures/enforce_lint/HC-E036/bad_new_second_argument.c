class HCPayload { int m_Value; }

class HCSink
{
    void Pair(int a, HCPayload payload) { int seen = payload.m_Value; }
}

class HCUse
{
    void Run()
    {
        HCSink sink = new HCSink;
        sink.Pair(1, new HCPayload);
    }
}
