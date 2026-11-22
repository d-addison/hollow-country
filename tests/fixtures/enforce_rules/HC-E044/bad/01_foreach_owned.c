// HCInteriorModule and HCXMissionMap before a33d66f6.
class HCInteriorModule
{
    void Scan(array<Object> found)
    {
        foreach (Object owned : found)
        {
            Print(owned);
        }
    }
}
