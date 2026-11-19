// HC-36/#145: original server-only lifecycle port, no provider source copied.
// The brief's pinned Expansion ai/core roots are absent in this environment.
// N17 human command declarations do not expose a verified AI SDK. Explicitly
// refuse walking/arrival/flee observations; never substitute elapsed time,
// player proximity, JSON capability flags or SetPosition for those receipts.
// Corridor and camp endpoints remain unsurveyed, individually pending coverage.
// Future inspected implementation must bind the director's EXISTING HC-10
// caravan role + exact actor/item, call HCInventoryBoundCaravan, require native
// home presence, and confirm BOTH walking legs with Corridor.ArrivalRangeMeters.
// Reuse qualified movement/admission + HCPerfPlayers snapshot + shared cap;
// never create/reserve another party or rebuild/refill its stock on restart.
// No new scans, native calls, save scheduler, module or addon config here.
class HCXAICaravanAdapter : HCCaravanInventory
{
    override bool HCReady() { return false; }
    override string HCRefusal() { return "CARAVAN_PROVIDER_CALLBACKS_UNVERIFIED"; }
    override bool HCBindCaravan(HCCaravanState row) { HCClear(); return false; }
    override bool HCWalkCaravan(HCCaravanState row, bool returning) { return false; }
    override bool HCAtCamp(HCCaravanState row, bool returning) { return false; }
    override bool HCFleeObserved(HCCaravanState row) { return false; }
}
