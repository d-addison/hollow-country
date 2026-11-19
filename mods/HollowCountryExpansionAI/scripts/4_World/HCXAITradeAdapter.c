// HC-35: original trusted server port, no copied Expansion source/content.
// The pinned ai/core source roots supplied to this worker are absent. N17
// human commands are not a provider SDK. Waypoint request != arrival/emote
// acknowledgement. Do not infer completion, spawn/fund parties or mint cargo.
// Lead binds HCBindProvider(new HCXAITradeAdapter) in HCXAIAdapter.OnStart,
// clears on stop; existing qualified activity calls HCAITrade.HCGet().HCBegin
// and reads HCObservedComplete("hc35-first-barter"). No new config class.
// A future qualified implementation must bind exact HC-10 lease bodies and
// existing item handles, call HCInventoryBound, request a surveyed walking
// route, and observe BOTH native gesture completions. No client assertions.
// HCPerfPlayers is the shared snapshot if future route admission needs player
// proximity; this refusal performs no player/world/inventory discovery.
class HCXAITradeAdapter : HCTradeInventory
{
    override bool HCReady() { return false; }
    override string HCRefusal() { return "TRADE_RENDEZVOUS_EMOTE_ACK_UNVERIFIED"; }
    override bool HCBind(HCTradeState row) { return false; }
    override bool HCBeginWalk(HCTradeState row) { return false; }
    override bool HCObservedGestures(HCTradeState row) { return false; }
}
