// #305/#291: observe a whole tick of stages, rather than one stage.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:106 TickCount;
// 1_Core/proto/EnDebug.c:96 Print; EnConvert.c:115 float.ToString.
// One native IO/JSON operation cannot be cancelled. This diagnostic is a peak,
// never a claim that the configured target was enforced inside that operation.
// Shared by the scheduler deadline and this receipt; retain the same slice clock. It
// starts immediately before dispatching this tick's bounded group of save stages.
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

    // Runs after every dispatch, per-frame urgent ones included (issue #333).
    override protected void HCAfterDispatch()
    {
        if (m_TickStages == 0) { return; }
        float elapsedMs = m_StageBudget.HCElapsedMs();
        if (elapsedMs <= HCPerfConfig.HCGet().SaveStageTargetMs || elapsedMs <= m_PeakStageMs) { return; }
        m_PeakStageMs = elapsedMs;
        Print("[HC PerfControl] WorldSaves stage_over_target_ms=" + elapsedMs.ToString() + " stages=" + m_TickStages.ToString() + " scope=dispatch_stages runtime=PENDING");
    }
}
