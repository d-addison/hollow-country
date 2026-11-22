// Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print;
// EnSystem.c:106 TickCount; 3_Game/Global/Game.c:1120 IsServer;
// Shared frame API citations live in Core/HCStartupPump.c; EnMath.c:553 Min.
// w45 #138. Final modded link: the pack reader declares m_PackBudget and HCPackAdvance in
// HCInteriorTemplates.c. Earlier links never call methods introduced here.
// Every pack slice is capped at PACK_SLICE_MS of raw ticks (and the configured pack slice
// when lower). The shared startup frame pump adds slices until ready/deadline/opt-out;
// the 1 Hz module tick remains the fallback and publishes the finished load.
modded class HCInteriorsModule
{
    static const float PACK_SLICE_MS = 2;

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        m_PackBudget = new HCPerfSlices("Interiors");
        Print("[HC PerfControl] Interiors pack slicing admitted; slice_ms<=2 shared_startup_frame=true; runtime=PENDING");
    }
    protected ref HCWorkBudget m_PrepareBudget = new HCWorkBudget;
    protected ref HCW64InteriorPackBudget m_PackSlice;
    protected bool m_SlicedPack;
    protected ref HCStartupInteriors m_StartupPack;
    protected ref HCStepTimer m_PackSteps;
    protected int m_LoadStep;

    protected float HCPackSliceMs()
    {
        HCPerfConfig config = HCPerfConfig.HCGet();
        float sliceMs = config.InteriorPackOnlineMs;
        array<Man> players = HCPerfPlayers.HCGet();
        if (players.Count() == 0) { sliceMs = config.InteriorPackEmptyMs; }
        return HCStartupPump.HCSliceMs(Math.Min(sliceMs, PACK_SLICE_MS));
    }

    // One budgeted slice of load steps; returns the raw ticks it took.
    protected int HCPackSlice()
    {
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INTERIORS, 1)) { return 0; }
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

    bool HCStartupPackPending()
    {
        return m_PackLoading && m_SlicedPack && !HCInteriorTemplates.HCLoadFinished();
    }
    protected void HCPackPumpStop() { HCStartupPump.HCFinish(m_StartupPack); }

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
            m_StartupPack = new HCStartupInteriors;
            m_StartupPack.Module = this;
            HCStartupPump.HCRegister(m_StartupPack, "interiors_pack");
        }
        HCSettings settings = HCServer.Get().GetSettings();
        if (!IsEnabled(settings)) { OnStop(); return; }
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
    }

    override void OnStop()
    {
        HCPackPumpStop();
        m_SlicedPack = false;
        m_PrepareBudget = new HCWorkBudget;
        super.OnStop();
    }
}
