// W5-PERF bound: one furnishing prop attempt per module tick; maintenance
// alternates house/pilot recycle/compaction over four ticks each minute.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// 1_Core/proto/EnMath.c:553 Min; EnSystem.c:397 FileExist; EnDebug.c:96 Print.
// Extend startup without replacing the legacy pilot's persistence/search path.
modded class HCInteriorsModule
{
    protected int m_FurnishedLimit;
    protected ref HCInteriorPlacementCursor m_FurnishWork = new HCInteriorPlacementCursor;
    protected ref HCWorkBudget m_FurnishBudget = new HCWorkBudget;
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
            // Review P1: one slot per module tick took ~7500 ticks for the
            // 1500-row catalog. Run up to 16 slots per tick within a 4 ms slice.
            if (HCInteriorTemplates.Loaded() && !m_FurnishWork.HCComplete())
            {
                m_FurnishBudget.HCReset(16);
                while (!m_FurnishWork.HCComplete() && m_FurnishBudget.HCContinue())
                {
                    m_FurnishWork.HCTick(this, settings, m_Objects);
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
