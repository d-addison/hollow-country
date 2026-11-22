// Clear: the module admits at most MAX_PROPS rows, so the walk is bounded by an authored cap.
class HCFixCappedModule
{
    static const int MAX_PROPS = 64;
    protected ref array<Object> m_Props = new array<Object>;

    void Add(Object prop)
    {
        if (m_Props.Count() >= MAX_PROPS) { return; }
        m_Props.Insert(prop);
    }

    void OnTick()
    {
        foreach (Object prop : m_Props)
        {
            prop.SetPosition(prop.GetPosition());
        }
    }
}
