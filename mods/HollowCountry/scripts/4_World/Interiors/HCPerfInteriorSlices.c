// Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print;
// EnSystem.c:106 TickCount; 3_Game/Global/Game.c:1120 IsServer.
// w45 #138. Final modded link: the pack reader declares m_PackBudget in
// HCInteriorTemplates.c. Earlier links never call methods introduced here.
// Cap BOTH metadata and leaf/validation steps using the existing reader cursor.
modded class HCInteriorsModule
{
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        m_PackBudget = new HCPerfSlices("Interiors");
        Print("[HC PerfControl] Interiors pack slicing admitted; tokens resumable; runtime=PENDING");
    }
    protected ref HCPerfBootBudget m_PrepareBudget = new HCPerfBootBudget;
    protected bool m_SlicedPack;
    protected ref HCStepTimer m_PackSteps;
    protected int m_PrepareStep;
    protected int m_LoadStep;

    override void OnTick(float deltaTime)
    {
        if (!m_PackLoading || !GetGame().IsServer())
        {
            super.OnTick(deltaTime);
            return;
        }
        if (!m_SlicedPack)
        {
            m_PackBudget = new HCW64InteriorPackBudget;
            m_PackSteps = new HCStepTimer("InteriorsPack");
            m_PrepareStep = m_PackSteps.HCDefine("prepare");
            m_LoadStep = m_PackSteps.HCDefine("decode_validate");
            m_SlicedPack = true;
        }
        HCSettings settings = HCServer.Get().GetSettings();
        if (!IsEnabled(settings)) { OnStop(); return; }
        HCPerfConfig config = HCPerfConfig.HCGet();
        float sliceMs = config.InteriorPackOnlineMs;
        array<Man> players = HCPerfPlayers.HCGet();
        if (players.Count() == 0) { sliceMs = config.InteriorPackEmptyMs; }
        m_PrepareBudget.HCFrame(deltaTime);
        m_PrepareBudget.HCReset(config.InteriorPackUnitsPerTick, sliceMs);
        int packStart = TickCount(0);
        while (m_PackLoading && m_PrepareBudget.HCContinue())
        {
            int prepareStart = TickCount(0);
            int prepared = HCW64InteriorLoad.HCPrepare(m_PrepareBudget);
            int prepareTicks = TickCount(prepareStart);
            m_PackSteps.HCAdd(m_PrepareStep, prepareTicks);
            m_PackSteps.HCItem("pack_prepare", prepareTicks);
            if (prepared == 1) { continue; }
            if (prepared == 0 && !m_PrepareBudget.HCContinue()) { break; }
            // Refusal must pass through the reader once to publish its status.
            int loadStart = TickCount(0);
            super.OnTick(deltaTime);
            HCW64InteriorLoad.HCConsumed();
            int loadTicks = TickCount(loadStart);
            m_PackSteps.HCAdd(m_LoadStep, loadTicks);
            m_PackSteps.HCItem("pack_decode_validate", loadTicks);
            if (prepared == 2) { break; }
        }
        m_PackSteps.HCEndTick(TickCount(packStart));
    }

    override void OnStop()
    {
        HCW64InteriorLoad.HCReset();
        m_SlicedPack = false;
        m_PrepareBudget = new HCPerfBootBudget;
        super.OnStop();
    }
}
