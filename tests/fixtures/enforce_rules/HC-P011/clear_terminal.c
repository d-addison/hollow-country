// Clear: the first hit leaves the loop, so one pass does the work on one item.
class HCFixTerminalModule
{
    protected ref array<Object> m_Props = new array<Object>;

    void OnTick()
    {
        foreach (Object prop : m_Props)
        {
            if (prop.IsPendingDeletion())
            {
                prop.SetPosition("0 0 0");
                return;
            }
        }
    }
}
