// Clear: the loop head spends the shared HCWorkBudget.
class HCFixBudgetModule
{
    protected ref array<Object> m_Props = new array<Object>;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;

    void OnTick()
    {
        m_Work.HCReset(8);
        foreach (Object prop : m_Props)
        {
            if (!m_Work.HCContinue()) { break; }
            prop.SetPosition(prop.GetPosition());
        }
    }
}
