// Extend startup without replacing the legacy pilot's persistence/search path.
modded class HCInteriorsModule
{
    protected int m_FurnishedLimit;
    protected int m_FurnishNext;
    protected float m_SearchRecycleElapsed;

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || s_Instance) return;
        m_FurnishedLimit = Math.Min(settings.MaxFurnishedProps, 1500);
        super.OnStart(settings);
        // Even a missing pilot file must not prevent additive pack admission.
        HCInteriorMeasuredCatalog.MeasuredEnsureLoaded();
        HCInteriorTemplates.EnsureLoaded(m_Config, settings.MaxPropsPerInterior);
        HCInteriorTemplatePlacement.Place(this, settings, m_Objects);
        m_FurnishNext = 10;
        if (HCInteriorTemplates.Loaded())
        {
            s_Instance = this;
            if (!FileExist("$profile:HollowCountry/interiors.json")) Print("[HC Interiors] legacy pilot absent; template path in use");
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
        if (HCInteriorTemplates.Loaded() && (m_FurnishNext < HCInteriorTemplates.FurnishRows().Count() || HCInteriorTemplatePlacement.DeferredPlacementPending()))
        {
            HCInteriorTemplatePlacement.Place(this, settings, m_Objects, m_FurnishNext);
            if (m_FurnishNext < HCInteriorTemplates.FurnishRows().Count())
            {
                m_FurnishNext = m_FurnishNext + 10;
            }
        }
        m_SearchRecycleElapsed += deltaTime;
        if (m_SearchRecycleElapsed < 60.0) { return; }
        m_SearchRecycleElapsed = 0.0;
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        HCSearchHouses houses = HCSearchBinding.Houses();
        HCSearchRefreshPilotHouses pilot = HCSearchRefreshModule.Pilot();
        if (houses)
        {
            houses.RecycleSpentBindings(players);
            houses.CompactSettled();
        }
        if (pilot)
        {
            pilot.RecycleSpentBindings(players);
            pilot.CompactSettled();
        }
    }

    override void OnStop()
    {
        super.OnStop();
        HCInteriorTemplatePlacement.ResetPlacement();
        m_FurnishNext = 0;
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
