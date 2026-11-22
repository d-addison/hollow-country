// Clear: no tick root reaches the walk.
class HCFixIdleModule
{
    protected ref array<Object> m_Props = new array<Object>;

    void Rebuild()
    {
        foreach (Object prop : m_Props)
        {
            prop.SetPosition("0 0 0");
        }
    }
}
