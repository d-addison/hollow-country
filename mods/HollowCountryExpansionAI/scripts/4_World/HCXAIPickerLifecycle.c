// HC-34 / LC-T409 round 2: HC-18 owns admission, materialisation and retirement.
// One state/candidate per existing StepTransients invocation, no new scheduler.
// Native scripts-1.30.164289: Global/Game.c:1120 IsServer; gameplay.c:636
// GetGame; Entities/Object.c:287 GetPosition; EnConvert.c:210 DistanceSq.
// Verified read-only .banso-writer/xref/{ai,core} (CC BY-NC-ND), PBO paths:
// ai/4_World/DayZExpansion_AI/Classes/eAIGroup.c:1123 bool IsInCombat(),
// :1139 DayZPlayerImplement GetMember(int), :1185 int Count();
// ai/4_World/DayZExpansion_AI/Entities/DayZPlayerImplement.c:234 eAIGroup GetGroup();
// UTC epoch uses HCXExpansionBridge.HCGetTimestamp; negative means refusal.
// #144: HCPartyRefusal/Deferred are HC-owned policy calls (no new Expansion API).
// Runtime acceptance PENDING. Never creates an actor, lease, group or item.
modded class HCXAISiteState
{
    int HCPickerEligibleAt;
    int HCPickerSiteCursor;
    ref HCXAISite HCPickerHomeSite;
    string HCPickerRefusal;

    void HCRefusePicker(string reason, string partyId, string routeId)
    {
        if (reason == HCPickerRefusal) { return; }
        HCPickerRefusal = reason;
        if (reason == "") { return; }
        string line = "[HC Pickers] admission party=" + partyId + " route=" + routeId;
        Print(line + " outcome=" + reason + " runtime=PENDING");
    }
}

modded class HCXAISiteDirector
{
    protected int m_HCPickerCursor;

    override void StepTransients()
    {
        super.StepTransients();
        if (!GetGame() || !GetGame().IsServer() || !HCPickers.Get()) { return; }
        if (m_States.Count() == 0 || !HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_PICKER_PARTY, HCUnitBudget.HC_WORK_AI_SITES, 1)) { return; }
        int now = HCXExpansionBridge.HCGetTimestamp();
        if (now < 0) { return; }
        if (m_HCPickerCursor >= m_States.Count()) { m_HCPickerCursor = 0; }
        HCXAISiteState pickerState = m_States[m_HCPickerCursor];
        m_HCPickerCursor++;
        this.HCParty(pickerState, now);
    }

    // This is the HCParty(lease) seam: only HC-10-claimed transient states
    // supply a lease. Ordinary catalog patrols have no identity; never mint one.
    void HCParty(HCXAISiteState state, int now)
    {
        if (!state || !state.Transient || !state.Materialized || state.Completed) { return; }
        HCPickers pickers = HCPickers.Get();
        if (!pickers || !GetGame() || !GetGame().IsServer()) { return; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
        if (!HCAIPartyIdentity.HCValid(identity)) { state.HCRefusePicker("PICKER_IDENTITY_INVALID", "none", "none"); return; }
        HCScavengeTrip trip = pickers.HCTrip();
        if (!trip || !trip.m_IO || !trip.m_IO.Survey) { return; }
        string partyId = identity.HCPartyId();
        string routeId = identity.HCRouteId();
        HCPickerRoute route = trip.m_IO.Survey.HCFind(routeId);
        if (!route) { state.HCRefusePicker("PICKER_ROUTE_UNSURVEYED", partyId, routeId); return; }
        if (!state.Patrol || !state.Patrol.m_Group) { state.HCRefusePicker("PICKER_ACTOR_GROUP_MISSING", partyId, routeId); return; }
        if (HCXExpansionBridge.HCGroupCount(state.Patrol.m_Group) < 1) { return; }
        if (state.Patrol.m_HCPendingMembers > 0 || HCXExpansionBridge.HCGroupIsInCombat(state.Patrol.m_Group)) { state.HCRefusePicker("PICKER_PARTY_BUSY", partyId, routeId); return; }
        PlayerBase actor = PlayerBase.Cast(HCXExpansionBridge.HCGroupGetMember(state.Patrol.m_Group, 0));
        if (!actor || !HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor)) { state.HCRefusePicker("PICKER_ACTOR_GROUP_MISSING", partyId, routeId); return; }
        // Resolve the actual surveyed home site's existing raid cooldown. One
        // policy candidate per visit; no unbounded catalog scan or new timer.
        if (!state.HCPickerHomeSite)
        {
            if (!m_Policy || state.HCPickerSiteCursor >= m_Policy.Sites.Count())
            {
                state.HCRefusePicker("PICKER_HOME_SITE_MISSING", partyId, routeId);
                return;
            }
            HCXAISite candidate = m_Policy.Sites[state.HCPickerSiteCursor];
            state.HCPickerSiteCursor++;
            if (candidate.Id != route.SiteId) { return; }
            state.HCPickerHomeSite = candidate;
        }
        if (this.RaidLocked(state.HCPickerHomeSite, now)) { state.HCRefusePicker("PICKER_SITE_COOLDOWN", partyId, routeId); return; }
        if (trip.m_State && trip.m_State.PartyId == partyId && trip.m_State.NextTripAt > state.HCPickerEligibleAt)
        {
            state.HCPickerEligibleAt = trip.m_State.NextTripAt;
        }
        // #144: a run needs a 2..4 member party (survey bounds); re-check later, not every visit.
        string sized = pickers.HCPartyRefusal(HCXExpansionBridge.HCGroupCount(state.Patrol.m_Group));
        if (sized != "")
        {
            if (now >= state.HCPickerEligibleAt) { state.HCPickerEligibleAt = now + pickers.HCRecheckSeconds(); }
            state.HCRefusePicker(sized, partyId, routeId);
            return;
        }
        string refusal = pickers.HCTryParty(identity, state.ProposalId, actor, now, state.HCPickerEligibleAt);
        if (HCPickPolicy.Deferred(refusal)) { state.HCPickerEligibleAt = now + pickers.HCRecheckSeconds(); }
        state.HCRefusePicker(refusal, partyId, routeId);
    }

    override void FinishTransient(HCXAISiteState state, bool materialized, int survivors)
    {
        // Base StepTransients may retire an absent group before the admission
        // cursor reaches it. Name that refusal while its claimed lease exists.
        if (materialized && (!state.Patrol || !state.Patrol.m_Group))
        {
            int now = HCXExpansionBridge.HCGetTimestamp();
            if (now >= 0) { this.HCParty(state, now); }
        }
        // Clock refusal must not skip durable loss or native retirement below.
        HCPickers pickers = HCPickers.Get();
        HCScavengeTrip trip;
        if (pickers) { trip = pickers.HCTrip(); }
        if (trip && trip.m_State && trip.m_State.LeaseId == state.ProposalId)
        {
            string phase = trip.m_State.Phase;
            if (phase == "leaving" || phase == "returning" || phase == "acquiring" || phase == "depositing") { trip.HCLose("PARTY_LEASE_LOST"); }
        }
        // Durable loss and patrol restoration precede native handle deletion
        // and the bridge's lease release. No cargo deletion/refund/replay.
        super.FinishTransient(state, materialized, survivors);
    }
}
