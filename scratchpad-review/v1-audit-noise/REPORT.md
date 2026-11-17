# v1-audit-noise report (branch hc/v1-audit-noise, base 99ff436)

## Files changed
- New  mods/HollowCountry/scripts/4_World/Infected/HCInfectedVision.c
- New  mods/HollowCountry/scripts/4_World/Loot/HCSearchNoise.c
- Edit mods/HollowCountry/scripts/4_World/Interiors/HCInteriorAction.c (search action; OnFinishProgressServer only, 4 lines)
- New  tests/unit/test_v1_native_noise_vision.py (21 tests)
- Logs scratchpad-review/v1-audit-noise/{RED1,GREEN1,full}.log

## 1. Search noise (#15 #20)
Hook: HCActionSearchInterior.OnFinishProgressServer (server-only: ActionContinuousBase.c:257 inside IsServer).
It reads the site phase, calls CommitSearch, then HCSearchNoise.OnCommitted. Emission only if the commit moved the
site phase 0 -> 2 (HCInteriorModule.CommitSearch "Search complete"). Refusal, failure (phase 3 / reset to 0),
cancel (OnEndServer never reaches CommitSearch's success path) and repeat are silent; one emission per completion.
Emit: server, alive actor, NoiseParams.LoadFromPath, NoiseSystem.AddNoisePos(player, player.GetPosition(), params).
Used AddNoisePos (not GenerateAINoiseAtPositionEx, which is AddNoiseTarget, a timed lingering ping).
Citations (N = ~/.cache/hollow-country/native-scripts/scripts-1.30.164289):
- N/3_Game/Noise.c:7 AddNoisePos; :25 LoadFromPath; N/3_Game/Global/Game.c:738 GetNoiseSystem
- N/4_World/Classes/UserActionsComponent/Actions/Interact/ActionOpenDoors.c:78-90 (vanilla pattern); path string also ActionCloseDoors.c:68, ActionOpenFence.c:55, ActionCloseFence.c:55
- N/4_World/Static/MiscGameplayFunctions.c:1830 (task cited 1829)
- N/4_World/Classes/UserActionsComponent/Actions/ActionContinuousBase.c:257,289 OnFinishProgressServer
Config path caveat: "CfgVehicles SurvivorBase NoiseActionDefault" is verified only as a vanilla script string (4 uses);
config.bin was not extracted so the entry itself is not confirmed. A missing entry would silently give zero noise.
Salvage hook: not touched. It would go in the salvage/decraft recipe server completion (RecipeBase.Do /
the HCNativeCraftingSafety override), calling HCSearchNoise.Emit(player) once on a successful craft;
add a policy there if only some recipes should be loud. HCSearchNoise.Emit is public and server-guarded.

## 2. Vision (#20 #35 #56)
modded class AITargetCallbacksPlayer.override float GetMaxVisionRangeModifier(EntityAI pApplicant)
(N/3_Game/Systems/AI/AITarget_callbacks.c:13; N/4_World/Entities/ManBase/PlayerBase/AITargetCallbacksPlayer.c:45-84).
Native result kept (it uses only speed + stance, never GetVisibilityCoef), multiplied by Factor clamped 0.6..1.3.
Inputs, all target-local: PlayerBase.GetVisibilityCoef (N/4_World/Entities/ManBase/PlayerBase.c:5443; mean :5405-5436;
Clothing_Base visibilityModifier N/4_World/Entities/Core/Inherited/InventoryItem.c:975-998, the task cited the wrong
paths); lit light = held item, Headgear slot (EntityAI.c:1897 FindAttachmentBySlotName, PlayerBase.c:6733
GetItemInHands), at most 8 attachments of the held item (Inventory.c:205,220); LitItem uses IsLightSource
(ItemBase.c:865, overrides Headtorch_ColorBase.c:243, UniversalLight.c:117, TLRLight.c:99) or Flashlight/Roadflare/
FlammableBase, then IsIgnited (EntityAI.c:544 = energy manager IsWorking); clock = GetGame().GetDayTime()
(Game.c:440; vanilla use FlashbangEffect.c:53). No allocation, no scans, nothing about the applicant.
Provisional constants: night 21-05 full with 2h dusk/dawn; darkness x0.75 at full night; lit light x1.1 day to
x1.5 night; clothing coef clamped 0.6..1.3; unset/invalid inputs = neutral. Night lit = 1.125 (above unlit 0.75).
Gate: HCInfectedVisionQualification (Qualified() false; marker $profile:HollowCountry/acceptance/infected_vision.enable,
probed once, logged EXPERIMENTAL). Not admitted -> returns exactly the native value. Server-only.
Policy in HCInfectedVisionPolicy, tested by executing the authored Enforce.

## TDD / results
RED: scratchpad-review/v1-audit-noise/RED1.log: "Ran 0 tests ... FAILED (errors=4)" (all four setUpClass errors:
missing authored HCInfectedVision.c / HCSearchNoise.c).
First GREEN run: 20 pass, 1 fail (my test counted "ShouldEmit(" as "Emit("); test fixed.
GREEN: GREEN1.log "Ran 21 tests ... OK".
Full suite (full.log): "Ran 2570 tests in 197.809s / OK (skipped=1)".

## Follow-up fix (owner): private m_Player
RED2.log: new test test_player_comes_from_own_constructor_capture_never_private_m_player failed (m_Player referenced),
Ran 22 tests FAILED (failures=1). Fix: own member + modded constructor capture, null -> exact native value.
GREEN2.log: tests.unit.test_v1_native_noise_vision + test_script_syntax + test_script_identifiers, Ran 32 tests OK.
Full suite not rerun (only HCInfectedVision.c and this test changed; last full run: 2570 tests OK, skipped=1).
The new test fails if the file references m_Player and asserts the constructor capture.

## Local-server acceptance steps
Noise: enable interiors+search, standing 20-30 m from an idle infected with no line of sight, start a search on a
storage site, complete it (6 s). Expect the infected to turn/investigate toward the player; repeat after cancelling
the search at 3 s and confirm no reaction; repeat with one that is refused. Log the player->infected distance at
which the reaction starts; compare against a vanilla door open at the same spot. Confirm the log shows one reaction
per completed search and none on a client-only run.
Vision: create $profile:HollowCountry/acceptance/infected_vision.enable, restart, confirm the
"EXPERIMENTAL local acceptance opt-in active" line. Stand still at fixed range steps with a wandering infected facing
the player: measure detection distance (a) noon unlit baseline vs marker absent, (b) night flashlight on vs off,
(c) headtorch on vs off, (d) ghillie/dark clothing vs plain. Expect night unlit shorter than noon, night lit longer than
night unlit, marker absent identical to vanilla.

## Remaining gaps
- Player capture: the modded constructor `void AITargetCallbacksPlayer(PlayerBase pPlayer)` stores `protected PlayerBase m_HCVisionPlayer`
  (m_Player is private, AITargetCallbacksPlayer.c:5, and is no longer referenced). That a modded-class constructor with
  the vanilla signature runs in addition to the vanilla one (vanilla ctor at AITargetCallbacksPlayer.c:7-12, created at
  PlayerBase.c:6326) is unverified until the next native compile; a null member returns the native value unchanged.
- Noise config entry and AI response unobserved; no salvage noise (other worker); no HCSettings toggle (not my scope).
- Day/night from the clock ignores season/moonlight/overcast; constants provisional; vision multiplier semantics
  (range vs applied to which AI sense) unobserved.
- Noise has no per-player cooldown beyond the 6 s action duration and one-emission-per-completion rule.
- Test cannot execute PlayerFactor/HasLitLight (native objects); only policy math and source shape.
