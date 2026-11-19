// HC-37 combat port for the Expansion AI addon (wave 16). Original code; Expansion
// is read, never copied. Server-only, read-only: this port observes existing site
// patrols and groups. It never moves, spawns, deletes, heals or targets anything.
// Native/Expansion citations (installed ai_scripts, inspected locally):
// 4_World/DayZExpansion_AI/Entities/DayZPlayerImplement.c:234 GetGroup;
// Classes/eAIGroup.c:671 GetFaction, :1123 IsInCombat, :1139 GetMember, :1185 Count.
// Existing addon owners used: HCXAISiteDirector.Active/Phase/States (HCXAISites.c),
// HCXAISiteState.Qualified/Failed/Transient/ProposalId/Patrol.m_HCLive/m_Group,
// HCXFactions.HCWorldId/Id (HCXFactions.c), HCXAIQualification.EncountersEnabled,
// HCWorldMaterializer.HCIdentity/HCDebugGet (base). Runtime acceptance PENDING.
// "Surveyed" means a route the site director itself qualified (its route key is the
// survey hash) at a site whose id is the offered place. An offer that does not match
// is declined by the module and logged once; nothing here guesses a match.
class HCXFactionCombatAdapter : HCFactionCombatPort
{
    static const int MAX_RECORDED_GROUPS = 2;
    // Weak group handles recorded by HCOwns for the current offer; HCDisengaged
    // reads them. Cleared by every new HCSurveyed. Never persisted.
    protected ref array<eAIGroup> m_Groups = new array<eAIGroup>();

    protected HCXAISiteDirector HCRunningDirector()
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director || director.Phase() != "run" || !HCXAIQualification.EncountersEnabled()) { return null; }
        return director;
    }

    // The surveyed, qualified, non-failed route state for this place and survey.
    protected HCXAISiteState HCSurveyState(string place, string survey)
    {
        HCXAISiteDirector director = HCRunningDirector();
        if (!director) { return null; }
        array<ref HCXAISiteState> states = director.States();
        foreach (HCXAISiteState state : states)
        {
            if (!state || !state.Site || state.Transient || !state.Qualified || state.Failed) { continue; }
            if (state.Site.Id == place && state.Key == survey) { return state; }
        }
        return null;
    }

    // The qualified live patrol the materializer lease owns (transient site).
    protected HCXAISiteState HCLeaseState(string lease)
    {
        HCXAISiteDirector director = HCRunningDirector();
        if (!director) { return null; }
        array<ref HCXAISiteState> states = director.States();
        foreach (HCXAISiteState state : states)
        {
            if (!state || !state.Transient || state.ProposalId != lease) { continue; }
            if (!state.Qualified || state.Failed || !state.Patrol || !state.Patrol.m_HCLive || !state.Patrol.m_Group) { continue; }
            return state;
        }
        return null;
    }

    // The lease is a claimed proposal at exactly this place (read-only debug seam).
    protected bool HCLeaseAtPlace(string lease, string place)
    {
        HCWorldMaterializer materializer = HCWorldMaterializer.HCDebugGet();
        if (!materializer) { return false; }
        int total = materializer.HCDebugProposalCount();
        for (int index = 0; index < total; index++)
        {
            HCDebugProposalRow proposal = materializer.HCDebugProposal(index);
            if (!proposal || proposal.Id != lease) { continue; }
            return proposal.PlaceId == place && proposal.State == "claimed";
        }
        return false;
    }

    override bool HCSurveyed(string placeId, string survey)
    {
        m_Groups.Clear();
        return HCSurveyState(placeId, survey) != null;
    }

    override bool HCOwns(string lease, string faction, Object actor, string placeId, string survey)
    {
        eAIBase body = eAIBase.Cast(actor);
        if (!body || !body.IsAlive() || body.GetIdentity()) { return false; }
        if (!HCSurveyState(placeId, survey)) { return false; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(lease);
        if (!HCAIPartyIdentity.HCValid(identity) || !HCLeaseAtPlace(lease, placeId)) { return false; }
        HCXAISiteState owner = HCLeaseState(lease);
        if (!owner) { return false; }
        eAIGroup group = body.GetGroup();
        if (!group || group != owner.Patrol.m_Group) { return false; }
        if (HCXFactions.HCWorldId(HCXFactions.Id(group.GetFaction())) != faction || faction == "") { return false; }
        if (m_Groups.Find(group) >= 0) { return true; }
        if (m_Groups.Count() >= HCXFactionCombatAdapter.MAX_RECORDED_GROUPS) { return false; }
        m_Groups.Insert(group);
        return true;
    }

    // Disengaged means no recorded group still reports combat. A deleted group
    // cannot be fighting; the module checks actor absence separately.
    override bool HCDisengaged(string encounter)
    {
        if (m_Groups.Count() < 1) { return false; }
        for (int index = 0; index < m_Groups.Count(); index++)
        {
            eAIGroup group = m_Groups[index];
            if (group && group.IsInCombat()) { return false; }
        }
        return true;
    }
}
