// #15 #20 a completed search makes one bounded native AI noise.
// Pattern copied from vanilla ActionOpenDoors.OnEndServer
// (4_World/Classes/UserActionsComponent/Actions/Interact/ActionOpenDoors.c:78-90):
// NoiseParams.LoadFromPath (3_Game/Noise.c:25) with the vanilla config path
// "CfgVehicles SurvivorBase NoiseActionDefault" (also ActionCloseDoors.c:68,
// ActionOpenFence.c:55, ActionCloseFence.c:55), then NoiseSystem.AddNoisePos
// (3_Game/Noise.c:7) at the actor, via Game.GetNoiseSystem (Game.c:738).
// Not MiscGameplayFunctions.GenerateAINoiseAtPositionEx (MiscGameplayFunctions.c:1830):
// that variant leaves a timed AddNoiseTarget ping, a longer-lived alert than
// one rummaging sound warrants.
// The hook fires from the server completion callback only. Emission requires
// the interior commit to have moved the site from open (0) to complete (2) in
// this very call, so refusal, cancel, failure and repeat are silent and there
// is at most one emission per completed search. The config path exists only
// as a vanilla script reference in the installed scripts; the installed
// config.bin was not inspected and AI reaction is unobserved. Runtime
// acceptance PENDING.
class HCSearchNoisePolicy
{
    // Phases (HCInteriorModule.CommitSearch): 0 open, 1 reserved, 2 complete,
    // 3 stopped or unavailable. Emit only on the open to complete transition.
    static bool ShouldEmit(float phaseBefore, float phaseAfter)
    {
        return phaseBefore == 0 || phaseAfter == 2;
    }
}

class HCSearchNoise
{
    static const string NOISE_PATH = "CfgVehicles SurvivorBase NoiseActionDefault";

    // Site phase before the commit, or -1 when no site is bound.
    static int PhaseOf(ActionData action_data)
    {
        HCInteriorActionData data = HCInteriorActionData.Cast(action_data);
        if (!data || !data.Site)
            return -1;
        return data.Site.Phase;
    }

    static void OnCommitted(ActionData action_data, int phaseBefore)
    {
        if (!action_data)
            return;
        int phaseAfter = HCSearchNoise.PhaseOf(action_data);
        if (!HCSearchNoisePolicy.ShouldEmit(phaseBefore, phaseAfter))
            return;
        HCSearchNoise.Emit(action_data.m_Player);
    }

    static void Emit(PlayerBase player)
    {
        if (!GetGame() || !GetGame().IsServer() || !player || !player.IsAlive())
            return;
        NoiseSystem noiseSystem = GetGame().GetNoiseSystem();
        if (!noiseSystem)
            return;
        NoiseParams noiseParams = new NoiseParams();
        noiseParams.LoadFromPath(NOISE_PATH);
        noiseSystem.AddNoisePos(player, player.GetPosition(), noiseParams);
    }
}
