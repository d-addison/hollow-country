// HC-40 / #146/#147. Consume HC-38's existing actor port; no second spawner,
// situation state, waypoint controller, gesture handler or lease owner.
// The supplied pinned Expansion ai/core script roots are absent here. Existing
// HCXEmoteObservation owns wave/warning/surrender/betrayal; its availability
// cannot qualify retreat or a safe road/entrance corridor. HC-36 walking-route
// contract is also absent. N16 ray/overlap support and N17 human commands do
// not expose verified AI move/flee. Never invent provider methods from them.
//
// Lead may select this port ONLY for the two HCTransitSituation profiles in
// the existing director's profile dispatch; do not replace HC-38's survivor
// binding globally. No registry or per-frame binding from this file.
// To open admission later: inspect permitted pinned provider scripts, bind
// exact existing HC-10 bodies, reuse HC-36 surveyed finite exit routes and
// HCPerfPlayers snapshots, qualify native corridor clearance, and delegate
// signals to HC-5/37. Observe native death/departure separately from requests.
// Intent/save barriers, identity history and stop/restart remain with HC-38.
// Runtime acceptance PENDING. This adapter performs no engine calls or scans.
class HCXAITransitAdapter : HCSituationActorPort
{
    override bool HCReady() { return false; }
    override string HCRefusal()
    {
        return "TRANSIT_PROVIDER_SOURCE_ROUTE_CLEARANCE_UNVERIFIED";
    }
    override string HCSelect(HCSituationState opportunity) { return ""; }
    override bool HCBegin(HCSituationState opportunity) { return false; }
    override string HCObserve(HCSituationState opportunity) { return ""; }
}
