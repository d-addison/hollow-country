class HCPayload { int m_Value; }

void Consume(HCPayload payload)
{
    int seen = payload.m_Value;
}

class HCUse
{
    void Run()
    {
        Consume(new HCPayload);
    }
}
