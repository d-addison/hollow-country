// Extend startup without replacing the legacy pilot's persistence/search path.
modded class HCInteriorsModule
{
    protected int m_FurnishedLimit;

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || s_Instance) return;
        m_FurnishedLimit = Math.Min(settings.MaxFurnishedProps, 1500);
        super.OnStart(settings);
        // Even a missing pilot file must not prevent additive pack admission.
        HCInteriorMeasuredCatalog.MeasuredEnsureLoaded();
        HCInteriorTemplates.EnsureLoaded(m_Config, settings.MaxPropsPerInterior);
        HCInteriorTemplatePlacement.Place(this, settings, m_Objects);
        if (HCInteriorTemplates.Loaded())
        {
            s_Instance = this;
            if (!FileExist("$profile:HollowCountry/interiors.json")) Print("[HC Interiors] legacy pilot absent; template path in use");
        }
        HCSearchBinding.TemplatesComplete(this);
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
