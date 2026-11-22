class HCXMissionMap
{
    void Scan(array<Object> found)
    {
        foreach (int index, Object owned : found)
        {
            Print(index);
        }
    }
}
