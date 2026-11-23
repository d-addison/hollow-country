class HCPayload { int m_Value; }

class HCUse
{
    void Run()
    {
        ref array<ref HCPayload> items = new array<ref HCPayload>;
        items.Insert(new HCPayload);
    }
}
