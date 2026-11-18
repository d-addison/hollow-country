// Issue #138 round 2: cheap per-tick sub-step timer shared by modules (Core framework piece).
// The CALLER measures with EnSystem.c:106 TickCount(start) (raw ticks; boot 028 [HC Perf]
// ticks_per_ms=10000) and hands the values in; this class reads no clock, allocates only its three
// step arrays at construction and does integer bookkeeping per call.
// Window rule: every WINDOW_TICKS owner ticks it keeps the WORST tick (largest measured total) with
// its per-step split, and prints at most ONE line, only when the window had items or out-of-tick
// work, or when its worst tick is a new peak (maintenance-only spikes still show once):
//   [HC Step] owner=<o> window=<n> ticks=<t> worst_tick_ticks=<T> worst_tick_items=<i>
//   <step>=<ticks>... other=<T minus the steps> heaviest_item_ticks=<h> heaviest=<type>
//   deferred_n=<n> deferred_max_ticks=<m>; raw TickCount units; runtime acceptance pending
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380/407 Count/Insert; EnDebug.c:96 Print;
// EnConvert.c:30 int.ToString.
class HCStepTimer
{
    static const int MAX_STEPS = 8;
    static const int WINDOW_TICKS = 60;
    protected string m_Owner;
    protected ref array<string> m_Names = new array<string>;
    protected ref array<int> m_Current = new array<int>;
    protected ref array<int> m_Worst = new array<int>;
    protected int m_CurrentItems;
    protected int m_WorstTotal;
    protected int m_WorstItems;
    protected int m_ItemMax;
    protected string m_ItemType;
    protected int m_DeferredCount;
    protected int m_DeferredMax;
    protected int m_Ticks;
    protected int m_Window;
    protected int m_Peak;
    protected bool m_Work;

    void HCStepTimer(string owner)
    {
        m_Owner = owner;
    }

    // Returns the step index, or -1 once MAX_STEPS are defined.
    int HCDefine(string name)
    {
        if (m_Names.Count() >= MAX_STEPS) { return -1; }
        m_Names.Insert(name);
        m_Current.Insert(0);
        m_Worst.Insert(0);
        return m_Names.Count() - 1;
    }

    void HCAdd(int step, int ticks)
    {
        if (step < 0 || step >= m_Current.Count() || ticks <= 0) { return; }
        m_Current[step] = m_Current[step] + ticks;
    }

    // One unit of owner work (for Interiors: one creation attempt) and its measured cost.
    void HCItem(string type, int ticks)
    {
        m_CurrentItems = m_CurrentItems + 1;
        if (ticks > m_ItemMax)
        {
            m_ItemMax = ticks;
            m_ItemType = type;
        }
    }

    // Work the owner scheduled outside its own tick (for Interiors: the deferred pathgraph update).
    void HCDeferred(int ticks)
    {
        if (ticks < 0) { return; }
        m_DeferredCount = m_DeferredCount + 1;
        if (ticks > m_DeferredMax) { m_DeferredMax = ticks; }
    }

    void HCEndTick(int totalTicks)
    {
        int index = 0;
        if (m_CurrentItems > 0) { m_Work = true; }
        if (totalTicks > m_WorstTotal)
        {
            m_WorstTotal = totalTicks;
            m_WorstItems = m_CurrentItems;
            while (index < m_Current.Count())
            {
                m_Worst[index] = m_Current[index];
                index = index + 1;
            }
        }
        index = 0;
        while (index < m_Current.Count())
        {
            m_Current[index] = 0;
            index = index + 1;
        }
        m_CurrentItems = 0;
        m_Ticks = m_Ticks + 1;
        if (m_Ticks >= WINDOW_TICKS) { HCCloseWindow(); }
    }

    void HCCloseWindow()
    {
        m_Window = m_Window + 1;
        if (m_DeferredCount > 0) { m_Work = true; }
        if (m_Work || m_WorstTotal > m_Peak)
        {
            if (m_WorstTotal > m_Peak) { m_Peak = m_WorstTotal; }
            Print(HCLine());
        }
        int index = 0;
        while (index < m_Worst.Count())
        {
            m_Worst[index] = 0;
            index = index + 1;
        }
        m_WorstTotal = 0;
        m_WorstItems = 0;
        m_ItemMax = 0;
        m_ItemType = "";
        m_DeferredCount = 0;
        m_DeferredMax = 0;
        m_Ticks = 0;
        m_Work = false;
    }

    string HCLine()
    {
        string line = "[HC Step] owner=" + m_Owner + " window=" + m_Window.ToString() + " ticks=" + m_Ticks.ToString();
        line = line + " worst_tick_ticks=" + m_WorstTotal.ToString() + " worst_tick_items=" + m_WorstItems.ToString();
        int other = m_WorstTotal;
        int index = 0;
        while (index < m_Worst.Count())
        {
            int stepTicks = m_Worst[index];
            line = line + " " + m_Names[index] + "=" + stepTicks.ToString();
            other = other - stepTicks;
            index = index + 1;
        }
        line = line + " other=" + other.ToString() + " heaviest_item_ticks=" + m_ItemMax.ToString() + " heaviest=" + m_ItemType;
        line = line + " deferred_n=" + m_DeferredCount.ToString() + " deferred_max_ticks=" + m_DeferredMax.ToString();
        return line + "; raw TickCount units; runtime acceptance pending";
    }
}
