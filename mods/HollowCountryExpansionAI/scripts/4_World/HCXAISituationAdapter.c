// Installed API evidence: Object.c GetPosition/IsAlive; Expansion eAIGroup
// Count/GetMember, already used by HCW38SituationRuntime. No actor scan.
class HCXSituationAnchor
{
    static bool HCGet(string lease, out vector anchor)
    {
        HCXAISiteState party = HCW38SituationRuntime.HCFind(lease);
        // Selection's cached index may have advanced for another profile while
        // this intent was saving. Resolve the exact lease in a bounded page.
        if (!party)
        {
            HCXAISiteDirector director = HCXAISiteDirector.Active();
            if (!director) { return false; }
            array<ref HCXAISiteState> states = director.States();
            if (!states) { return false; }
            for (int index = 0; index < 24 && index < states.Count(); index++)
            {
                if (!HCServer.HCTickWork().HCTake(1)) { return false; }
                HCXAISiteState candidate = states[index];
                if (candidate && candidate.ProposalId == lease) { party = candidate; break; }
            }
        }
        if (!party || !party.Patrol || !party.Patrol.m_Group || party.Patrol.m_Group.Count() == 0) { return false; }
        eAIBase leader = eAIBase.Cast(party.Patrol.m_Group.GetMember(0));
        if (!leader || !leader.IsAlive()) { return false; }
        anchor = leader.GetPosition();
        return HCEventRuntimePolicy.PositionValid(anchor);
    }
}

// #147: shared live-party implementation and native/provider citations are
// in HCW38SituationRuntime.c. HC-38 owns intent/save/history; HC-10 owns bodies.
class HCXAISituationAdapter : HCSituationActorPort
{
    override bool HCAnchor(string lease, out vector anchor)
    {
        if (HCXSituationAnchor.HCGet(lease, anchor)) { return true; }
        return super.HCAnchor(lease, anchor);
    }

    override bool HCReady() { return HCW38SituationRuntime.HCReady(); }
    override string HCRefusal() { return HCW38SituationRuntime.HCReason(); }
    override string HCSelect(HCSituationState opportunity) { return HCW38SituationRuntime.HCSelect(opportunity); }
    override bool HCBegin(HCSituationState opportunity) { return HCW38SituationRuntime.HCBegin(opportunity); }
    override string HCObserve(HCSituationState opportunity) { return HCW38SituationRuntime.HCObserve(opportunity); }
    override void HCEnd(HCSituationState opportunity) { HCW38SituationRuntime.HCEnd(opportunity); }
}
