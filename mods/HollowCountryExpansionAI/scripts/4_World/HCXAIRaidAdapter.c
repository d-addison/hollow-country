// HC-39 / #147. Original server adapter, no copied provider implementation.
// The pinned permitted Expansion AI/Core source directories in the worker
// brief are absent. Inspected native 3_Game/dayzplayer.c:1171 DayZPlayer and
// 4_World/Entities/DayZPlayerImplement.c:86 DayZPlayerImplement are human command
// interfaces, NOT a group walking/combat/cargo/retreat SDK. HCXAIAdapter's
// existing patrol calls do not establish raid route exits or custody transfer.
// Therefore no new engine/provider API is called and no body is commandeered.
// Native/runtime acceptance remains PENDING; no ready flag can enable this.
// Lead binds HCCampRaidActors.HCBind(new HCXAIRaidAdapter) during adapter
// startup, also HCSituationActors.HCBindRaid with that SAME instance;
// clears both bindings on stop. No module, tick, player scan or second actor cap.
class HCXAIRaidAdapter : HCCampRaidActorPort
{
    override bool HCReady() { return false; }
    override string HCSelect(HCSituationState opportunity) { return ""; }
    override bool HCBegin(HCSituationState opportunity) { return false; }
    override string HCObserve(HCSituationState opportunity) { return ""; }
    override string HCRefusal()
    {
        return "RAID_FOOT_ROUTE_COMBAT_CUSTODY_UNVERIFIED";
    }
}
