// Installed API evidence: Object.c GetPosition/IsAlive; Expansion eAIGroup
// Count/GetMember, already used by HCW38SituationRuntime. No actor scan.
class HCXSituationAnchor
{
    // At most 24 concurrent situation intents; retain only scan offsets, never
    // actor/player positions. Completed/full scans release their entry.
    protected static ref map<string, int> s_Cursors = new map<string, int>();
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
            if (!states || states.Count() == 0) { s_Cursors.Remove(lease); return false; }
            if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_ANCHOR, HCUnitBudget.HC_WORK_SITUATION_RUNTIME, 1)) { return false; }
            int cursor;
            s_Cursors.Find(lease, cursor);
            if (cursor >= states.Count()) { cursor = 0; }
            int examined = 0;
            while (cursor < states.Count() && examined < 16)
            {
                HCXAISiteState candidate = states[cursor];
                cursor++;
                examined++;
                if (candidate && candidate.ProposalId == lease) { party = candidate; break; }
            }
            if (party || cursor >= states.Count()) { s_Cursors.Remove(lease); }
            else
            {
                if (!s_Cursors.Contains(lease) && s_Cursors.Count() >= 24) { s_Cursors.Remove(s_Cursors.GetKey(0)); }
                s_Cursors.Set(lease, cursor);
            }
        }
        if (!party || !party.Patrol || !party.Patrol.m_Group || HCXExpansionBridge.HCGroupCount(party.Patrol.m_Group) == 0) { return false; }
        eAIBase leader = eAIBase.Cast(HCXExpansionBridge.HCGroupGetMember(party.Patrol.m_Group, 0));
        if (!leader || !HCXExpansionBridge.HCBaseIsAlive(leader)) { return false; }
        anchor = HCXExpansionBridge.HCBaseGetPosition(leader);
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
