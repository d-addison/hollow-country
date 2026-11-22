// Clear: a literal bound of at most 16 limits the loop.
class HCFixSmallModule
{
    protected ref array<Object> m_Props = new array<Object>;

    void OnTick()
    {
        for (int index = 0; index < m_Props.Count() && index < 3; index++)
        {
            m_Props[index].SetPosition("0 0 0");
        }
    }
}
