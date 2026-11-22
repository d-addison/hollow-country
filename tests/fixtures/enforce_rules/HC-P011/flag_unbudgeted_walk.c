// HC-P011 must flag: a tick walks a module-owned prop list and moves each prop, with no budget.
class HCFixWalkModule
{
    protected ref array<Object> m_Props = new array<Object>;

    void OnTick()
    {
        foreach (Object prop : m_Props)
        {
            prop.SetPosition(prop.GetPosition() + "0 0.01 0");
        }
    }
}
