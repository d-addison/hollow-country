// Clear: the walk is an HCBoundedJob, which is the budget.
class HCBoundedJob
{
    int HCItemCount() { return 0; }
    int HCStepItem(int index) { return 0; }
}

class HCFixJob : HCBoundedJob
{
    protected ref array<Object> m_Props = new array<Object>;

    override int HCItemCount() { return m_Props.Count(); }

    override int HCStepItem(int index)
    {
        m_Props[index].SetPosition("0 0 0");
        return 0;
    }

    void OnTick()
    {
        foreach (Object prop : m_Props)
        {
            prop.SetPosition("0 0 0");
        }
    }
}
