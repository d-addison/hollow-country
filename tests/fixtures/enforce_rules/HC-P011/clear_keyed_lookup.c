// Clear: world work runs only on the one row whose key matches.
class HCFixKeyedModule
{
    protected ref array<Object> m_Props = new array<Object>;

    void Touch(Object wanted)
    {
        foreach (Object prop : m_Props)
        {
            if (prop == wanted)
            {
                prop.SetPosition("0 0 0");
            }
        }
    }

    void OnTick()
    {
        Touch(null);
    }
}
