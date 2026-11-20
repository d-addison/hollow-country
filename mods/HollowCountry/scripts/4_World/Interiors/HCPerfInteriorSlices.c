// Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print;
// EnSystem.c:106 TickCount; 3_Game/Global/Game.c:1120 IsServer;
// 2_GameLib/tools.c:61/65 ScriptCallQueue.CallLater/Remove; EnMath.c:553 Min.
// w45 #138. Final modded link: the pack reader declares m_PackBudget and HCPackAdvance in
// HCInteriorTemplates.c. Earlier links never call methods introduced here.
// Every pack slice is capped at PACK_SLICE_MS of raw ticks (and the configured pack slice
// when lower). While the pack loads, a call-queue pump adds a slice every PACK_PUMP_MS so the
// 1 Hz module tick is not the only driver; the module tick still publishes the finished load.
modded class HCInteriorsModule
{
    static const float PACK_SLICE_MS = 10;
    static const int PACK_PUMP_MS = 100;

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        m_PackBudget = new HCPerfSlices("Interiors");
        Print("[HC PerfControl] Interiors pack slicing admitted; slice_ms<=10 pump_ms=100; runtime=PENDING");
    }
    protected ref HCPerfBootBudget m_PrepareBudget = new HCPerfBootBudget;
    protected ref HCW64InteriorPackBudget m_PackSlice;
    protected bool m_SlicedPack;
    protected bool m_PackPumping;
    protected ref HCStepTimer m_PackSteps;
    protected int m_LoadStep;

    protected float HCPackSliceMs()
    {
        HCPerfConfig config = HCPerfConfig.HCGet();
        float sliceMs = config.InteriorPackOnlineMs;
        array<Man> players = HCPerfPlayers.HCGet();
        if (players.Count() == 0) { sliceMs = config.InteriorPackEmptyMs; }
        return Math.Min(sliceMs, PACK_SLICE_MS);
    }

    // One budgeted slice of load steps; returns the raw ticks it took.
    protected int HCPackSlice()
    {
        int sliceStart = TickCount(0);
        HCPerfConfig config = HCPerfConfig.HCGet();
        m_PrepareBudget.HCReset(config.InteriorPackUnitsPerTick, HCPackSliceMs());
        int stepLimit = HCInteriorTemplates.HCLoadStepLimit(m_Config);
        bool more = true;
        // Each load step spends at least one outer unit, so the unit cap ends this loop.
        while (more && m_PackLoading && !HCInteriorTemplates.HCLoadFinished())
        {
            m_PackSlice.HCReset(stepLimit);
            more = HCPackAdvance(stepLimit) && !m_PackSlice.HCSpent();
        }
        return TickCount(sliceStart);
    }

    void HCPackPump()
    {
        if (!m_PackLoading || !m_SlicedPack || !GetGame().IsServer())
        {
            HCPackPumpStop();
            return;
        }
        int packTicks = HCPackSlice();
        if (m_PackSteps) { m_PackSteps.HCDeferred(packTicks); }
        if (HCInteriorTemplates.HCLoadFinished()) { HCPackPumpStop(); }
    }

    protected void HCPackPumpStop()
    {
        if (!m_PackPumping) { return; }
        m_PackPumping = false;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCPackPump);
    }

    override void OnTick(float deltaTime)
    {
        if (!m_PackLoading || !GetGame().IsServer())
        {
            HCPackPumpStop();
            super.OnTick(deltaTime);
            return;
        }
        if (!m_SlicedPack)
        {
            m_PackSlice = new HCW64InteriorPackBudget;
            m_PackSlice.HCBind(m_PrepareBudget);
            m_PackBudget = m_PackSlice;
            m_PackSteps = new HCStepTimer("InteriorsPack");
            m_LoadStep = m_PackSteps.HCDefine("decode_validate");
            m_SlicedPack = true;
        }
        HCSettings settings = HCServer.Get().GetSettings();
        if (!IsEnabled(settings)) { OnStop(); return; }
        m_PrepareBudget.HCFrame(deltaTime);
        int packTicks = HCPackSlice();
        m_PackSteps.HCAdd(m_LoadStep, packTicks);
        m_PackSteps.HCItem("pack_slice", packTicks);
        // The reader link publishes a finished load; its own step finds this slice spent.
        super.OnTick(deltaTime);
        m_PackSteps.HCEndTick(packTicks);
        if (!m_PackLoading)
        {
            HCPackPumpStop();
            return;
        }
        if (!m_PackPumping)
        {
            m_PackPumping = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCPackPump, PACK_PUMP_MS, true);
        }
    }

    override void OnStop()
    {
        HCPackPumpStop();
        m_SlicedPack = false;
        m_PrepareBudget = new HCPerfBootBudget;
        super.OnStop();
    }
}
