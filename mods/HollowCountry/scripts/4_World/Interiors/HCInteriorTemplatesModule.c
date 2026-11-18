// W5-PERF bound: furnishing attempts per module tick are limited by a deterministic work-unit
// budget (HCUnitBudget, FURNISH_UNITS_PER_TICK, issue #138); maintenance
// alternates house/pilot recycle/compaction over four ticks each minute.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// 1_Core/proto/EnMath.c:553 Min; EnSystem.c:397 FileExist; EnDebug.c:96 Print.
// Extend startup without replacing the legacy pilot's persistence/search path.
modded class HCInteriorsModule
{
    protected int m_FurnishedLimit;
    protected ref HCInteriorPlacementCursor m_FurnishWork = new HCInteriorPlacementCursor;
    // Units per module tick: 3 creation attempts (SLOT_UNITS=8) or 24 cheap deferrals/refusals.
    // The previous 16-slot count with a 4 ms clock guard measured 80-135 ms ticks.
    static const int FURNISH_UNITS_PER_TICK = 24;
    protected ref HCUnitBudget m_FurnishUnits = new HCUnitBudget;
    protected int m_MaintenancePhase;
    protected float m_SearchRecycleElapsed;

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || s_Instance) { return; }
        m_FurnishedLimit = Math.Min(settings.MaxFurnishedProps, 1500);
        super.OnStart(settings);
        // Even a missing pilot file must not prevent additive pack admission.
        HCInteriorMeasuredCatalog.MeasuredEnsureLoaded();
        HCInteriorTemplates.EnsureLoaded(m_Config, settings.MaxPropsPerInterior);
        HCInteriorTemplatePlacement.Place(this, settings, m_Objects, -1);
        if (HCInteriorTemplates.Loaded())
        {
            s_Instance = this;
            if (!FileExist("$profile:HollowCountry/interiors.json")) { Print("[HC Interiors] legacy pilot absent; template path in use"); }
        }
        HCSearchBinding.TemplatesComplete(this);
    }


    // Native 1.30.164289: 3_Game/Global/Game.c:945 GetPlayers(out array<Man>).
    // The shared module tick owns both placement progress and bounded maintenance.
    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (s_Instance != this || !GetGame().IsServer()) { return; }
        HCSettings settings = HCServer.Get().GetSettings();
        if (!IsEnabled(settings)) { OnStop(); return; }
        m_SearchRecycleElapsed += deltaTime;
        bool maintenanceDue = m_MaintenancePhase > 0 || m_SearchRecycleElapsed >= 60.0;
        if (!maintenanceDue)
        {
            // Review P1: one slot per module tick took ~7500 ticks for the 1500-row catalog, so
            // several slots run per tick, bounded by work units (no clock): the first slot is always
            // admitted, a creation attempt charges SLOT_UNITS, a cheap deferral CHEAP_UNITS.
            if (HCInteriorTemplates.Loaded() && !m_FurnishWork.HCComplete())
            {
                m_FurnishUnits.HCReset(FURNISH_UNITS_PER_TICK);
                while (!m_FurnishWork.HCComplete() && m_FurnishUnits.HCTake(HCInteriorPlacementCursor.CHEAP_UNITS))
                {
                    m_FurnishWork.HCTick(this, settings, m_Objects);
                    m_FurnishUnits.HCCharge(m_FurnishWork.HCLastCost() - HCInteriorPlacementCursor.CHEAP_UNITS);
                }
            }
            return;
        }
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
