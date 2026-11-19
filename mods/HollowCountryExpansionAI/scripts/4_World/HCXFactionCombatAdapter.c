// HC-37 combat producer and port for the Expansion AI addon (wave 16). Original code; Expansion
// is read, never copied. Server-only, read-only: this port observes existing site
// patrols and groups. It never moves, spawns, deletes, heals or targets anything.
// Additional Expansion: Classes/eAIGroup.c:1194 DeceasedCount;
// Core/3_Game/DayZExpansion_Core/ExpansionSHA256.c:51 Reset, :162 Update, :235 HexDigest.
// Native Man.c:21 GetIdentity; Object.c:517 IsAlive; EnScript.c:94 Cast.
// Native/Expansion citations (installed ai_scripts, inspected locally):
// 4_World/DayZExpansion_AI/Entities/DayZPlayerImplement.c:234 GetGroup;
// Classes/eAIGroup.c:671 GetFaction, :1123 IsInCombat, :1139 GetMember, :1185 Count.
// Existing addon owners used: HCXAISiteDirector.Active/Phase/States (HCXAISites.c),
// HCXAISiteState.Qualified/Failed/Transient/ProposalId/Patrol.m_HCLive/m_Group,
// HCXFactions.HCWorldId/Id (HCXFactions.c), HCXAIQualification.EncountersEnabled,
// HCWorldMaterializer.HCIdentity/HCDebugGet (base). Runtime acceptance PENDING.
// "Surveyed" means a route the site director itself qualified, or an opaque
// hash of two qualified transient routes whose leases share the offered place. An offer that does not match
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
        if (place != m_OfferedPlace || survey != m_OfferedSurvey) { return null; }
        HCXAISiteState left = HCLeaseState(m_OfferedLeft);
        HCXAISiteState right = HCLeaseState(m_OfferedRight);
        if (!left || !right || left == right) { return null; }
        if (!HCLeaseAtPlace(m_OfferedLeft, place) || !HCLeaseAtPlace(m_OfferedRight, place)) { return null; }
        return left;
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
        m_SeenCombat = false;
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

    // Disengaged means a witnessed fight ended and no group still reports combat. A deleted group
    // cannot be fighting; the module checks actor absence separately.
    override bool HCDisengaged(string encounter)
    {
        if (m_Groups.Count() < 1) { return false; }
        for (int index = 0; index < m_Groups.Count(); index++)
        {
            eAIGroup group = m_Groups[index];
            if (group && group.IsInCombat()) { m_SeenCombat = true; return false; }
            if (group && group.DeceasedCount() > 0) { m_SeenCombat = true; }
        }
        return m_SeenCombat;
    }
    protected string m_OfferedPlace;
    protected string m_OfferedSurvey;
    protected string m_OfferedLeft;
    protected string m_OfferedRight;
    protected bool m_SeenCombat;
    protected int m_OfferLeftCursor;
    protected int m_OfferRightCursor = 1;

    protected bool HCOfferState(HCXAISiteState state, string place, string faction)
    {
        if (!state || !state.Transient || !state.Qualified || state.Failed || state.Completed) { return false; }
        if (!state.Patrol || !state.Patrol.m_HCLive || !state.Patrol.m_Group) { return false; }
        if (!HCLeaseAtPlace(state.ProposalId, place)) { return false; }
        return HCXFactions.HCWorldId(HCXFactions.Id(state.Patrol.m_Group.GetFaction())) == faction;
    }

    override bool HCActiveAt(string placeId)
    {
        HCXAISiteDirector director = HCRunningDirector();
        if (!director) { return false; }
        array<ref HCXAISiteState> states = director.States();
        foreach (HCXAISiteState state : states)
        {
            if (!state || !state.Patrol || !state.Patrol.m_HCLive || !state.Patrol.m_Group) { continue; }
            if (state.Transient && HCLeaseAtPlace(state.ProposalId, placeId)) { return true; }
        }
        return false;
    }

    protected void HCOfferBodies(eAIGroup group, array<Object> actors)
    {
        int count = group.Count();
        if (count < 1 || count > HCAILimits.SIZE_CEILING) { return; }
        for (int actorIndex = 0; actorIndex < count; actorIndex++)
        {
            DayZPlayerImplement actor = group.GetMember(actorIndex);
            if (!actor || !actor.IsAlive() || actor.GetIdentity()) { actors.Clear(); return; }
            actors.Insert(actor);
        }
    }

    override bool HCOffer(string placeId, string leftFaction, string rightFaction)
    {
        HCXAISiteDirector director = HCRunningDirector();
        if (!director || HCWorldFactionCatalog.Relation(leftFaction, rightFaction) != -1) { return false; }
        array<ref HCXAISiteState> states = director.States();
        int total = states.Count();
        if (total < 2) { return false; }
        // One state pair per offer. The director already bounds its catalog.
        if (m_OfferRightCursor >= total) { m_OfferLeftCursor++; m_OfferRightCursor = m_OfferLeftCursor + 1; }
        if (m_OfferLeftCursor >= total - 1) { m_OfferLeftCursor = 0; m_OfferRightCursor = 1; }
        HCXAISiteState left = states[m_OfferLeftCursor];
        HCXAISiteState right = states[m_OfferRightCursor];
        m_OfferRightCursor++;
        if (!HCOfferState(left, placeId, leftFaction) || !HCOfferState(right, placeId, rightFaction))
        {
            HCXAISiteState swap = left;
            left = right;
            right = swap;
            if (!HCOfferState(left, placeId, leftFaction) || !HCOfferState(right, placeId, rightFaction)) { return false; }
        }
        // These routes already passed the native path qualification. Hash is
        // an opaque in-process receipt, never a new geometry or native verdict.
        string routeIdentity = left.Key + ":" + right.Key;
        ExpansionSHA256.Update(routeIdentity);
        string survey = ExpansionSHA256.HexDigest();
        ExpansionSHA256.Reset();
        m_OfferedPlace = placeId;
        m_OfferedSurvey = survey;
        m_OfferedLeft = left.ProposalId;
        m_OfferedRight = right.ProposalId;
        array<Object> leftBodies = new array<Object>;
        array<Object> rightBodies = new array<Object>;
        HCOfferBodies(left.Patrol.m_Group, leftBodies);
        HCOfferBodies(right.Patrol.m_Group, rightBodies);
        string encounter = HCFactionConflict.HCBegin(placeId, survey, left.ProposalId, leftFaction, leftBodies, right.ProposalId, rightFaction, rightBodies);
        return encounter != "";
    }


}
