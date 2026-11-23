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
        return phaseBefore == 0 && phaseAfter == 2;
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

    // LC-T407: installed 3_Game/Noise.c:7 AddNoisePos accepts EntityAI;
    // :25 LoadFromPath; Global/Game.c:738 GetNoiseSystem, :1120 IsServer.
    // Position searches use their real source container for an ordinary one-shot
    // noise, never a timed target, virtual player or persistent alert.
    static void EmitAt(EntityAI actor, vector position)
    {
        if (!GetGame() || !GetGame().IsServer() || !actor) return;
        NoiseSystem worldNoise = GetGame().GetNoiseSystem();
        if (!worldNoise) return;
        NoiseParams searchParams = new NoiseParams();
        searchParams.LoadFromPath(NOISE_PATH);
        worldNoise.AddNoisePos(actor, position, searchParams);
    }

    // The same one-shot noise as EmitAt with NoiseSystem.AddNoisePos's native
    // external_strenght_multiplier (installed 3_Game/Noise.c:7; the vanilla horn passes 2.0
    // to AddNoiseTarget, VehicleHornComponent.c:101-107; DayZGame.c explosion and hit noises
    // pass a surface multiplier). The caller owns the clamp; this only refuses a value that
    // is not a positive finite number, which would be a silent no-op or a nonsense noise.
    static void EmitAtScaled(EntityAI actor, vector position, float multiplier)
    {
        if (!GetGame() || !GetGame().IsServer() || !actor) return;
        if (!(multiplier > 0) || multiplier > 100) return;
        NoiseSystem worldNoise = GetGame().GetNoiseSystem();
        if (!worldNoise) return;
        NoiseParams scaledParams = new NoiseParams();
        scaledParams.LoadFromPath(NOISE_PATH);
        worldNoise.AddNoisePos(actor, position, scaledParams, multiplier);
    }

    static void Emit(PlayerBase player)
    {
        if (!GetGame() || !GetGame().IsServer() || !player || !player.IsAlive())
            return;
        HCSearchNoise.EmitAt(player, player.GetPosition());
    }
}
