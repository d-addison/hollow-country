// #138: the pack reader's inner budget. It spends the units and the raw-tick deadline of the
// slice owner's HCPerfBootBudget (HCPerfInteriorSlices), so every load step, file and row batch
// draws on one shared slice. The owner resets the outer budget; HCReset here only re-arms.
// A native read or LoadData of one <=32767-byte file cannot be preempted.
class HCW64InteriorPackBudget : HCWorkBudget
{
    protected ref HCWorkBudget m_Outer;
    protected bool m_Spent;

    void HCBind(HCWorkBudget outer)
    {
        m_Outer = outer;
        m_Spent = false;
    }

    override void HCReset(int limit, float milliseconds = 4)
    {
        m_Spent = false;
    }

    override bool HCContinue()
    {
        if (m_Spent || !m_Outer)
        {
            return false;
        }
        if (!m_Outer.HCContinue())
        {
            m_Spent = true;
            return false;
        }
        return true;
    }

    bool HCSpent()
    {
        return m_Spent;
    }
}
