// #305/#291: observe a whole tick of stages, rather than one stage.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:106 TickCount;
// 1_Core/proto/EnDebug.c:96 Print; EnConvert.c:115 float.ToString.
// One native IO/JSON operation cannot be cancelled. This diagnostic is a peak,
// never a claim that the configured target was enforced inside that operation.
// Expose only the elapsed conversion; HCWorkBudget's limits and clock stay shared.
class HCSaveStageBudget : HCWorkBudget
{
    float HCElapsedMs()
    {
        int ticks = TickCount(m_SliceStart);
        if (ticks < 0) { return -1; }
        return (float)ticks / m_SliceTicksPerMs;
    }
}

modded class HCSaveScheduler
{
    protected float m_PeakStageMs;

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (m_TickStages == 0) { return; }
        float elapsedMs = m_StageBudget.HCElapsedMs();
        if (elapsedMs <= HCPerfConfig.HCGet().SaveStageTargetMs || elapsedMs <= m_PeakStageMs) { return; }
        m_PeakStageMs = elapsedMs;
        Print("[HC PerfControl] WorldSaves stage_over_target_ms=" + elapsedMs.ToString() + " stages=" + m_TickStages.ToString() + " scope=tick_stages runtime=PENDING");
    }
}
