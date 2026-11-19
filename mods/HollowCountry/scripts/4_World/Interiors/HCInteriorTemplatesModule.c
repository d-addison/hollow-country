// W5-PERF bound: furnishing attempts per module tick are limited by a deterministic work-unit
// budget (HCUnitBudget, FURNISH_UNITS_PER_TICK) AND one tick-wide HCPerfSlices
// deadline/count (Performance.InteriorStepsPerTick, issue #138); maintenance
// alternates house/pilot recycle/compaction over four ticks each minute.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// 1_Core/proto/EnMath.c:553 Min; EnSystem.c:397 FileExist; EnDebug.c:96 Print.
// Extend startup without replacing the legacy pilot's persistence/search path.
modded class HCInteriorsModule
{
    protected int m_FurnishedLimit;
    protected ref HCInteriorPlacementCursor m_FurnishWork = new HCInteriorPlacementCursor;
    // Unit ceiling: 3 creation attempts (SLOT_UNITS=8) or 24 cheap deferrals/refusals.
    // The configured tick-wide slice may stop earlier (default: one cursor visit).
    // The previous 16-slot count with a 4 ms clock guard measured 80-135 ms ticks.
    static const int FURNISH_UNITS_PER_TICK = 24;
    // Issue #138 round 2: an attempt is charged the larger of its declared units and its measured
    // cost at 4000 raw ticks per unit (0.4 ms at the boot 028 ticks_per_ms=10000), so a further
    // attempt starts only while the tick has spent < ~9.6 ms; a heavy attempt ends the tick.
    static const int FURNISH_TICKS_PER_UNIT = 4000;
    protected ref HCUnitBudget m_FurnishUnits = new HCUnitBudget;
    protected int m_MaintenancePhase;
    protected float m_SearchRecycleElapsed;

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || s_Instance) { return; }
        m_FurnishedLimit = Math.Min(settings.HCSearchCap("MaxFurnishedProps", settings.MaxFurnishedProps), 1500);
        super.OnStart(settings);
        // Even a missing pilot file must not prevent additive pack admission.
        HCInteriorMeasuredCatalog.MeasuredEnsureLoaded();
        HCInteriorTemplates.EnsureLoaded(m_Config, settings.HCSearchCap("MaxPropsPerInterior", settings.MaxPropsPerInterior));
        // HC-24: the staged pack tick places and reports search readiness once the load finishes
        // (loaded or refused); reporting here would latch templates_loaded=0 before the load.
    }


    // Native 1.30.164289: 3_Game/Global/Game.c:945 GetPlayers(out array<Man>);
    // 1_Core/proto/EnSystem.c:106 TickCount (raw ticks since the given start).
    // The shared module tick owns both placement progress and bounded maintenance. Every tick is
    // sub-timed into HCInteriorTemplatePlacement.HCSteps() ('[HC Step] owner=Interiors', one line per window).
    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (s_Instance != this || !GetGame().IsServer()) { return; }
        HCSettings settings = HCServer.Get().GetSettings();
        if (!IsEnabled(settings)) { OnStop(); return; }
        int tickStart = TickCount(0);
        HCStepTimer steps = HCInteriorTemplatePlacement.HCSteps();
        m_SearchRecycleElapsed += deltaTime;
        bool maintenanceDue = m_MaintenancePhase > 0 || m_SearchRecycleElapsed >= 60.0;
        if (!maintenanceDue)
        {
            if (HCInteriorTemplates.Loaded() && !m_FurnishWork.HCComplete()) { m_FurnishWork.HCBeginTick(); HCFurnish(settings, steps); }
            steps.HCEndTick(TickCount(tickStart));
            return;
        }
        int maintStart = TickCount(0);
        // Maintenance gets its own ticks even when an occupied house keeps a
        // partial furnishing row deferred. Neither work queue starves the other.
        if (m_MaintenancePhase == 0) { m_SearchRecycleElapsed = 0.0; }
        array<Man> players = HCPerfPlayers.HCGet();
        HCSearchHouses houses = HCSearchBinding.Houses();
        HCSearchRefreshPilotHouses pilot = HCSearchRefreshModule.Pilot();
        if (m_MaintenancePhase == 0 && houses) { houses.RecycleSpentBindings(players); }
        if (m_MaintenancePhase == 1 && houses) { houses.CompactSettled(); }
        if (m_MaintenancePhase == 2 && pilot) { pilot.RecycleSpentBindings(players); }
        if (m_MaintenancePhase == 3 && pilot) { pilot.CompactSettled(); }
        m_MaintenancePhase = (m_MaintenancePhase + 1) % 4;
        steps.HCAdd(HCInteriorTemplatePlacement.STEP_MAINT, TickCount(maintStart));
        steps.HCEndTick(TickCount(tickStart));
    }

    // Review P1: one slot per module tick took ~7500 ticks for the 1500-row catalog, so several
    // slots may run per tick, bounded by work units and HCBeginTick: a creation
    // attempt charges at least SLOT_UNITS (more when its measured cost is higher), a cheap deferral
    // CHEAP_UNITS. The cursor keeps its position before yielding.
    protected void HCFurnish(HCSettings settings, HCStepTimer steps)
    {
        m_FurnishUnits.HCReset(FURNISH_UNITS_PER_TICK);
        while (!m_FurnishWork.HCComplete() && m_FurnishUnits.HCTake(HCInteriorPlacementCursor.CHEAP_UNITS))
        {
            int itemStart = TickCount(0);
            m_FurnishWork.HCTick(this, settings, m_Objects);
            int itemTicks = TickCount(itemStart);
            int declared = m_FurnishWork.HCLastCost();
            if (declared >= HCInteriorPlacementCursor.SLOT_UNITS) { steps.HCItem(HCInteriorTemplatePlacement.HCLastType(), itemTicks); }
            m_FurnishUnits.HCChargeMeasured(declared, itemTicks, FURNISH_TICKS_PER_UNIT, HCInteriorPlacementCursor.CHEAP_UNITS);
        }
    }

    override void OnStop()
    {
        super.OnStop();
        HCInteriorTemplatePlacement.ResetPlacement();
        m_FurnishWork = new HCInteriorPlacementCursor;
        m_MaintenancePhase = 0;
        m_SearchRecycleElapsed = 0.0;
    }

    override void PlaceCandidate(int index)
    {
        // The pilot layout is bounded by m_PropLimit; reserve that upper bound
        // before entering its unchanged creation/rollback path.
        if (m_Objects.Count() + m_PropLimit > m_FurnishedLimit)
        {
            Print("[HC Interiors] legacy layout capped by MaxFurnishedProps");
            return;
        }
        super.PlaceCandidate(index);
    }

    void PlaceCandidate(HCInteriorFurnishRow row, HCSettings settings)
    {
        HCInteriorTemplatePlacement.PlaceRow(this, row, settings, m_Objects);
    }
}
