// Coverage diagnostics over the admitted pack, not a new placement controller.
// Keep the measured clearance/pathgraph placement owner unchanged. Summarize refused
// classes once per pack pin, with bounded work through the maintenance budget.
// Native 1.30.164289: 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnScript.c:380 Count. Runtime acceptance remains pending.
modded class HCInteriorTemplates
{
    static array<ref HCInteriorTemplateClassRow> HCLootCoverageRows()
    {
        if (!s_Loaded) return null;
        return s_Classes;
    }
}

class HCLootInteriorCoverage
{
    protected string m_Pin;
    protected int m_Next;
    protected int m_Refused;
    protected bool m_Reported;

    void HCTick()
    {
        if (!HCInteriorTemplates.Loaded()) return;
        string pin = HCInteriorTemplates.SourcePin();
        if (pin != m_Pin)
        {
            m_Pin = pin;
            m_Next = 0;
            m_Refused = 0;
            m_Reported = false;
        }
        array<ref HCInteriorTemplateClassRow> rows = HCInteriorTemplates.HCLootCoverageRows();
        if (!rows) return;
        HCUnitBudget work = HCServer.HCTickWork();
        int examined;
        while (m_Next < rows.Count() && examined < HCInteriorTemplates.TEMPLATE_CHECKS_PER_STEP)
        {
            if (!work.HCTakeFor(HCUnitBudget.HC_WORK_SEARCH_COVERAGE, 1)) return;
            HCInteriorTemplateClassRow row = rows[m_Next];
            m_Next++;
            examined++;
            if (row && row.Furniture != "covered")
            {
                m_Refused++;
            }
        }
        if (m_Next >= rows.Count() && !m_Reported)
        {
            m_Reported = true;
            Print("[HC Interiors] furnishing coverage sweep classes=" + rows.Count().ToString() + " refused=" + m_Refused.ToString() + " runtime=PENDING");
        }
    }
}

modded class HCInteriorsModule
{
    protected ref HCLootInteriorCoverage m_LootCoverage = new HCLootInteriorCoverage;

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (HCInteriorsModule.Get() != this) return;
        m_LootCoverage.HCTick();
    }

    override void OnStop()
    {
        super.OnStop();
        m_LootCoverage = new HCLootInteriorCoverage;
    }
}
