// HC-34 round 3 / LC-T409: authored population input, not a body/cargo producer.
// World starts before its tick; AddParty owns validation, detached JSON copying,
// duplicate/cap admission, dirty tracking and the shared save scheduler.
// Native scripts-1.30.164289: Game.c:1120 IsServer; gameplay.c:636 GetGame;
// EnScript.c:380/407 Count/Insert; EnDebug.c:96 Print. Loaders reuse inspected
// HCWorldStore/HCPickerSurvey ports; JsonFileLoader.c:69 LoadData. No Expansion calls here.
// Survey LocalityId/home/points derive from this site's HC43 locality/waypoints.
// Runtime acceptance PENDING: ledger input never establishes a live trip.
modded class HCWorldModule
{
    protected ref HCPickerSurvey m_HCPickerSurvey;

    override void OnStart(HCSettings settings)
    {
        if (m_Running) { return; }
        super.OnStart(settings);
        if (!m_Running || !settings.EnableEncounters || !GetGame() || !GetGame().IsServer()) { return; }
        string refusal;
        HCPickerSurvey survey = HCPickerSurvey.HCLoad(refusal);
        HCXAISitePolicy policy = this.HCLoadPickerSites();
        this.HCSeedPickerParties(survey, policy);
    }

    // Read shipped input directly: the profile policy may not be provisioned
    // yet when World starts. Do not depend on addon module registration order.
    HCXAISitePolicy HCLoadPickerSites()
    {
        string text = HCWorldStore.Read("$mission:hollow-country/ai/sites.json");
        if (text == "" || text.Length() > HCWorldStore.MAX_BYTES) { return null; }
        HCXAISitePolicy policy;
        string error;
        if (!JsonFileLoader<HCXAISitePolicy>.LoadData(text, policy, error)) { return null; }
        return policy;
    }

    void HCSeedPickerParties(HCPickerSurvey survey, HCXAISitePolicy policy)
    {
        if (!m_Running || !m_Data) { return; }
        if (!survey || !policy || !policy.Sites)
        {
            Print("[HC Pickers] ledger seed outcome=PICKER_SEED_AUTHORED_DATA_MISSING runtime=PENDING");
            return;
        }
        if (survey.Routes.Count() > survey.MaxRoutes || policy.Sites.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return; }
        m_HCPickerSurvey = survey;
        int added = 0;
        int existing = 0;
        int refused = 0;
        for (int routeIndex = 0; routeIndex < survey.Routes.Count(); routeIndex++)
        {
            HCPickerRoute route = survey.Routes[routeIndex];
            // HC-10 derives route:<party.Id>. Keep that scheme in its one owner;
            // the survey already authors route:<site.Id>, so party.Id = site.Id.
            if (route.RouteId != "route:" + route.SiteId) { refused++; continue; }
            bool present = false;
            for (int partyIndex = 0; partyIndex < m_Data.Parties.Count(); partyIndex++)
            {
                if (m_Data.Parties[partyIndex].Id == route.SiteId) { present = true; break; }
            }
            // Never rewrite surviving rows, including casualties/empty parties.
            if (present) { existing++; continue; }
            HCXAISite homeSite = null;
            for (int siteIndex = 0; siteIndex < policy.Sites.Count(); siteIndex++)
            {
                HCXAISite candidate = policy.Sites[siteIndex];
                if (candidate.Id == route.SiteId) { homeSite = candidate; break; }
            }
            if (!homeSite || homeSite.Kind != "scavenger" || !homeSite.Waypoints || route.HomeIndex >= homeSite.Waypoints.Count()) { refused++; continue; }
            if (homeSite.Waypoints[route.HomeIndex] != route.HCHomePoint()) { refused++; continue; }
            HCWorldParty party = new HCWorldParty();
            party.Id = route.SiteId;
            party.Kind = "PICKER";
            party.FactionId = HCXFactions.HCWorldId(homeSite.Faction);
            party.Size = homeSite.NumberOfAI;
            party.Home = route.LocalityId;
            // A local foraging circuit has two named-place edges within its
            // own locality. Concrete legs belong to the survey, never invented
            // inter-town journeys or abstract item transfers.
            party.Route.Insert(party.Home);
            party.Route.Insert(party.Home);
            if (this.AddParty(party)) { added++; }
            else { refused++; }
        }
        string line = "[HC Pickers] ledger seed added=" + added.ToString() + " existing=" + existing.ToString();
        Print(line + " refused=" + refused.ToString() + " runtime=PENDING");
    }

    override HCWorldProposal MaterializerRow(int rowIndex)
    {
        HCWorldProposal row = super.MaterializerRow(rowIndex);
        if (!row || row.Kind != "PICKER" || !m_HCPickerSurvey) { return row; }
        HCPickerRoute route = m_HCPickerSurvey.HCFind(row.Identity.HCRouteId());
        // The existing interest ring/budgets/claim and native patrol trigger
        // still own spawning. Supply an authored home anchor, never SetPosition.
        if (route && row.PlaceId == route.LocalityId) { row.Position = route.HCHomePoint(); }
        return row;
    }
}
