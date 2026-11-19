// HC-40 / #146/#147. Consume HC-38's existing actor port; no second spawner,
// situation state, waypoint controller, gesture handler or lease owner.
// The supplied pinned Expansion ai/core script roots are absent here. Existing
// HCXEmoteObservation owns wave/warning/surrender/betrayal; its availability
// cannot qualify retreat or a safe road/entrance corridor. HC-36 walking-route
// contract now exists; its provider/geometry evidence remains unverified.
// N16 ray/overlap support and N17 human commands do not expose verified AI move/flee. Never invent provider methods from them.
//
// Lead binds HCSituationActors.HCBindTransit(new HCXAITransitAdapter) at
// addon startup and clears it on stop. The director selects it ONLY for the
// two HCTransitSituation profiles; the survivor binding is independent.
// No registry or per-frame binding from this file.
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
