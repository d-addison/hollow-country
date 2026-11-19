// #147: shared live-party implementation and native/provider citations are
// in HCW38SituationRuntime.c. HC-38 owns intent/save/history; HC-10 owns bodies.
class HCXAITransitAdapter : HCSituationActorPort
{
    override bool HCReady() { return HCW38SituationRuntime.HCReady(); }
    override string HCRefusal() { return HCW38SituationRuntime.HCReason(); }
    override string HCSelect(HCSituationState opportunity) { return HCW38SituationRuntime.HCSelect(opportunity); }
    override bool HCBegin(HCSituationState opportunity) { return HCW38SituationRuntime.HCBegin(opportunity); }
    override string HCObserve(HCSituationState opportunity) { return HCW38SituationRuntime.HCObserve(opportunity); }
    override void HCEnd(HCSituationState opportunity) { HCW38SituationRuntime.HCEnd(opportunity); }
}
