// HC-38: deliberately no new Expansion/engine calls. The two pinned installed
// ai/core source roots in the worker brief were absent during authoring.
// Native dayzplayer.c/DayZPlayerImplement.c are NOT an AI placement/action SDK.
// Existing HCXAIEncounters bind patrol kills, not an independently threatened
// survivor; HCXAICampRoutine requests cannot establish rescue or safe egress.
// Therefore source/package support stops at a named admission refusal.
//
// Lead binds this through HCSituationActors.HCBind(new HCXAISituationAdapter)
// in HCXAIAdapter.OnStart; clears it on stop. No registry insertion or tick.
// To replace this refusal: inspect permitted pinned Expansion sources, qualify
// an existing HC-10 lease + survivor/threat ownership, verified placement and
// a bounded emote-only action. Keep native death/departure observation separate
// from requested actions. No new actor/cargo, player task or reward controller.
class HCXAISituationAdapter : HCSituationActorPort
{
    override string HCRefusal()
    {
        return "SURVIVOR_PLACEMENT_ACTION_API_UNVERIFIED";
    }
    override bool HCReady() { return false; }
    override string HCSelect(HCSituationState opportunity) { return ""; }
}
