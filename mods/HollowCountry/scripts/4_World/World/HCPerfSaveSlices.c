// w45 #138: observe the cooperative target without assuming raw TickCount units.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:914 GetTickTime;
// 1_Core/proto/EnDebug.c:96 Print; EnConvert.c:115 float.ToString.
// One native IO/JSON operation cannot be cancelled. This diagnostic is a peak,
// never a claim that the configured target was enforced inside that operation.
modded class HCSaveScheduler
{
    protected float m_PeakStageMs;

    override void OnTick(float deltaTime)
    {
        float began = GetGame().GetTickTime();
        super.OnTick(deltaTime);
        float elapsedMs = (GetGame().GetTickTime() - began) * 1000;
        if (elapsedMs <= HCPerfConfig.HCGet().SaveStageTargetMs || elapsedMs <= m_PeakStageMs) { return; }
        m_PeakStageMs = elapsedMs;
        Print("[HC PerfControl] WorldSaves stage_over_target_ms=" + elapsedMs.ToString() + " runtime=PENDING");
    }
}
