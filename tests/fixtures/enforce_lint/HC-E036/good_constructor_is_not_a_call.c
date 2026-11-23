class HCPayload { int m_Value; }

class HCUse
{
    void Run()
    {
        HCPayload payload = new HCPayload;
        payload.m_Value = 1;
    }
}
