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
    protected ref HCWorkBudget m_PrepareBudget = new HCWorkBudget;
    protected bool m_SlicedPack;
    protected ref HCStepTimer m_PackSteps;
    protected int m_PrepareStep;
    protected int m_LoadStep;

    override void OnTick(float deltaTime)
    {
        bool packing = m_PackLoading;
        int packStart = TickCount(0);
        if (m_PackLoading && GetGame().IsServer())
        {
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
            int prepareStart = TickCount(0);
            m_PrepareBudget.HCReset(1, HCPerfConfig.HCGet().SliceMs);
            int prepared = HCW64InteriorLoad.HCPrepare(m_PrepareBudget);
            m_PackSteps.HCAdd(m_PrepareStep, TickCount(prepareStart));
            if (prepared != 0)
            {
                m_PackSteps.HCItem("pack_prepare", TickCount(packStart));
                m_PackSteps.HCEndTick(TickCount(packStart));
                return;
            }
        }
        int loadStart = TickCount(0);
        super.OnTick(deltaTime);
        HCW64InteriorLoad.HCConsumed();
        if (packing && m_PackSteps)
        {
            m_PackSteps.HCAdd(m_LoadStep, TickCount(loadStart));
            m_PackSteps.HCItem("pack_decode_validate", TickCount(packStart));
            m_PackSteps.HCEndTick(TickCount(packStart));
        }
    }

    override void OnStop()
    {
        HCW64InteriorLoad.HCReset();
        m_SlicedPack = false;
        super.OnStop();
    }
}
