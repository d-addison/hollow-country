// HC-P011 must flag: the per-item world work is one authored call away.
class HCFixHelperModule
{
    protected ref array<Object> m_Props = new array<Object>;

    void Settle(Object prop)
    {
        prop.SetPosition(prop.GetPosition());
    }

    void OnTick()
    {
        for (int index = 0; index < m_Props.Count(); index++)
        {
            Settle(m_Props[index]);
        }
    }
}
