// Runtime consumption belongs to the existing bounded HC-18 site owner.
// Native scripts-1.30.164289: 1_Core/proto/EnConvert.c:196 Distance,
// EnScript.c:380/407 Count/Insert; EnDebug.c:96 Print. No Expansion calls.
// Bind delegates ground sampling, route-key
// hashing, native FindPath qualification, actor caps, sight and materialisation
// to HCXAISiteDirector. Source citations live in gapcode_routes_catalog.c and
// the inherited HCXAISites.c. No actors/items/leases are created here.
class HCStartupRoutes : HCStartupOwner
{
    HCXAISiteDirector Director;
    override bool HCNeedsWork() { return Director && Director.HCStartupRoutesPending(); }
    override void HCSlice() { if (Director && Director.HCStartupRoutesPending()) { Director.HCStartupRoutesSlice(); } }
}

modded class HCXAISiteDirector
{
    protected ref HCGapcodeRoutesCatalog m_GapcodeRoutes;
    protected bool m_HCRouteCatalogTurn;
    protected ref HCStartupRoutes m_StartupRoutes;

    override void Start()
    {
        super.Start();
        if (HCXAISiteDirector.Active() != this || m_Phase == "off" || m_Phase == "refused")
        {
            Print("[HC Routes] catalog=degraded reason=ROUTE_SITE_OWNER_NOT_STARTED runtime=PENDING");
            return;
        }
        m_GapcodeRoutes = new HCGapcodeRoutesCatalog;
        m_GapcodeRoutes.HCOpen();
        m_StartupRoutes = new HCStartupRoutes;
        m_StartupRoutes.Director = this;
        HCStartupPump.HCRegister(m_StartupRoutes, "routes_catalog");
    }
    bool HCStartupRoutesPending()
    {
        return m_GapcodeRoutes && m_GapcodeRoutes.HCNeedsWork() && m_Phase != "off" && m_Phase != "stopped" && m_Phase != "refused";
    }
    void HCStartupRoutesSlice() { m_GapcodeRoutes.HCStep(m_Localities, m_Policy); }
    override void Step()
    {
        // Pump owns catch-up; ordinary ticks only advance after its deadline.
        if (m_GapcodeRoutes && m_GapcodeRoutes.HCNeedsWork() && (!m_StartupRoutes || m_StartupRoutes.Finished) && m_Phase != "off" && m_Phase != "stopped" && m_Phase != "refused")
        {
            m_HCRouteCatalogTurn = !m_HCRouteCatalogTurn;
            if (m_HCRouteCatalogTurn) { m_GapcodeRoutes.HCStep(m_Localities, m_Policy); return; }
        }
        super.Step();
    }
    override void Stop()
    {
        HCStartupPump.HCFinish(m_StartupRoutes);
        if (m_GapcodeRoutes) { m_GapcodeRoutes.HCStop(); m_GapcodeRoutes = null; }
        super.Stop();
    }
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCOperationalStatus inheritedStatus = super.HCGetOperationalStatus();
        if (!m_GapcodeRoutes || inheritedStatus.HCState() != "ready") { return inheritedStatus; }
        HCOperationalStatus routeStatus = m_GapcodeRoutes.HCGetOperationalStatus(inheritedStatus);
        // An opted-out supplement leaves the original site's status intact.
        if (routeStatus.HCState() == "off") { return inheritedStatus; }
        return routeStatus;
    }
    override protected bool HCSurveyReady()
    {
        return !m_GapcodeRoutes || !m_GapcodeRoutes.HCNeedsWork();
    }
    override protected void Bind(HCXAISiteState state)
    {
        if (!state || state.Bound || state.Failed) { return; }
        if (m_GapcodeRoutes && state && !state.Transient && state.Site && state.LocalityId != "")
        {
            HCGapcodeRoutesRow route = m_GapcodeRoutes.HCFind(state.LocalityId);
            // Keep curated routes, checkpoints and holdouts intact. Only the
            // generated named-locality two-anchor fallback takes a road route.
            string fallbackId = "gapcov-" + state.LocalityId;
            if (route && state.Site.Id == fallbackId && state.Site.Kind == "patrol" && !state.Site.Checkpoint && state.Site.Waypoints && state.Site.Waypoints.Count() >= 2)
            {
                HCXAISite sourceSite = state.Site;
                HCGapcodeRoutesLimits limits = m_GapcodeRoutes.Data.limits;
                // The source fallback uses y=0. Compare horizontal approach;
                // native ground/navmesh qualification still owns the real leg.
                vector sourcePoint = sourceSite.Waypoints[0];
                vector roadPoint = route.Points[0];
                sourcePoint[1] = roadPoint[1];
                float approach = vector.Distance(sourcePoint, roadPoint);
                if (approach <= limits.approach_metres && limits.segment_metres <= m_Policy.MaxLegLength)
                {
                    // Per-state copy: shared policy/mission Routes never change.
                    HCXAISite candidateSite = new HCXAISite;
                    candidateSite.Id = sourceSite.Id;
                    candidateSite.Kind = sourceSite.Kind;
                    candidateSite.Faction = sourceSite.Faction;
                    candidateSite.ContentRole = sourceSite.ContentRole;
                    candidateSite.Loadout = sourceSite.Loadout;
                    candidateSite.NumberOfAI = sourceSite.NumberOfAI;
                    candidateSite.NumberOfAIMax = sourceSite.NumberOfAIMax;
                    candidateSite.Behaviour = "ALTERNATE";
                    candidateSite.Speed = sourceSite.Speed;
                    candidateSite.ActivationRadius = sourceSite.ActivationRadius;
                    candidateSite.DespawnSeconds = sourceSite.DespawnSeconds;
                    candidateSite.RespawnSeconds = sourceSite.RespawnSeconds;
                    candidateSite.Reviewed = sourceSite.Reviewed;
                    array<vector> points = route.Points;
                    foreach (vector roadWaypoint : points) { candidateSite.Waypoints.Insert(roadWaypoint); }
                    state.Site = candidateSite;
                    HCModuleReadiness.HCUse("optional-expansion-human-ai", "regional_road_site_binding");
                }
                else
                {
                    m_GapcodeRoutes.HCBindingRefuse(route, "ROUTE_SITE_APPROACH_OR_LEG_LIMIT");
                }
            }
        }
        super.Bind(state);
    }
}
