// Clear: OnStop drains the collection once at shutdown; shutdown is not tick work.
class HCFixStopModule
{
    protected ref array<Object> m_Props = new array<Object>;

    void OnTick()
    {
        Stop();
    }

    void Stop()
    {
        foreach (Object prop : m_Props)
        {
            prop.SetPosition("0 0 0");
        }
    }
}
