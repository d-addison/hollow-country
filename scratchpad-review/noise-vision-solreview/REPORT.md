**Verdict: MERGE-WITH-FIXES.** Source review only; runtime acceptance and production enablement remain pending.

1. **P2 — Working chemlights and gas lamps are classified as unlit.**
   `mods/HollowCountry/scripts/4_World/Infected/HCInfectedVision.c:133` and `:135`.
   With local vision acceptance admitted, holding a working `Chemlight_ColorBase`
   or `PortableGasLamp` returns false from `LitItem`. Both inherit `ItemBase`,
   whose `IsLightSource()` returns false, and neither is in the fallback casts.
   At neutral clothing and 02:00, the authored policy therefore produces 0.75
   instead of the 1.125 it produces for a recognized working light. This violates
   the requested coverage of any lit held light; it does not establish an actual
   detection distance in DayZ.
   Native evidence: N/4_World/Entities/ItemBase.c:865–868;
   N/4_World/Entities/ItemBase/ChemLight.c:1, :66–74, :141–154;
   N/4_World/Entities/ItemBase/PortableGasLamp.c:1, :34–43;
   N/3_Game/Entities/EntityAI.c:544–548. The two native classes have no
   `IsLightSource` override. **Minimal fix:** include `Chemlight_ColorBase` and
   `PortableGasLamp` in the existing cast fallback, preserving `IsIgnited()`,
   and add working/off classification regressions. Actual failure reproduced in
   `light-red.log` (3 tests, 2 failures); the minimal scratch candidate passes
   all 3 in `light-green.log`. Production source was not changed.

2. **P2 — Integration tests permit admission, server-authority and loop-bound regressions.**
   `tests/unit/test_v1_native_noise_vision.py:175`, `:187`, `:227`, `:282`.
   These tests inspect tokens/order rather than execute the gate, override,
   emitter or light scan. Independent mutants forcing `Admitted()` to return
   true, reversing either server guard, ignoring headgear, removing the actual
   attachment cap, discarding the factor and disabling recognized light results
   all pass the writer's entire 22-test noise/vision module. A regression could
   enable unqualified vision or client noise while CI stays green. **Minimal
   fix:** execute the authored adapter methods with explicit native-object
   fixtures, assert native fallback and zero downstream calls for client/closed
   gate cases, and count emissions/attachment visits. Preserve actual engine
   acceptance separately. `test_review_contracts.py` demonstrates eight passing
   offline adapter/bounds checks against the current implementation; it does
   not establish engine behavior. Mutation results below are against the
   writer's tests, without these added checks.

No P0/P1 defect, invalid native call, unbounded authored multiplier, or duplicate
search emission was verified in this review.

**Scope and evidence limits**

Reviewed the current four-file uncommitted diff, the writer's report, the
runtime implementation contract, and the installed 1.30.164289 script cache.
N below means `~/.cache/hollow-country/native-scripts/scripts-1.30.164289`.
The two required design documents are absent from this worktree. Read their
copies in `/code/dayzsa_mods/docs/`, plus that checkout's Banso spec/plan/tasks,
as design context only. Active instructions retain the private-source,
3–6-player and source-before-client constraints where those documents differ.
Relevant traceability remains FR-006/008/011, NFR-001/003/006 and AC-005/007/010/012;
plan T018–T021 and T023 retain native and multiplayer acceptance.

The owner-supplied successful native compile is accepted as supplied evidence;
this reviewer ran no DayZ, Wine or network operations. No git mutation commands
were used. All review files and temporary test writes are under this directory.
The production diff SHA-256 before and after review was identical:
`905128d8cbbd09626e3a247dfe35ab2cce1e839ae2097373dcd9533f4bb572cc`.

**Native API audit**

All native/script interface calls introduced by the change exist with compatible
argument and return types. Optional arguments below account for shorter calls.

| Used interface | Authoritative declaration or definition |
|---|---|
| `DayZGame GetGame()` | N/3_Game/gameplay.c:636 |
| `bool Game.IsServer()` | N/3_Game/Global/Game.c:1120 |
| `bool FileExist(string name)` | N/1_Core/proto/EnSystem.c:397 |
| `void Print(void var)` | N/1_Core/proto/EnDebug.c:96 |
| `Class.Cast(Class from)` safe type casts | N/1_Core/proto/EnScript.c:80–94; covers ItemBase, Flashlight, Roadflare, FlammableBase and HCInteriorActionData casts |
| `void AITargetCallbacksPlayer(PlayerBase pPlayer)` | N/4_World/Entities/ManBase/PlayerBase/AITargetCallbacksPlayer.c:7 |
| `float GetMaxVisionRangeModifier(EntityAI pApplicant)` | N/3_Game/Systems/AI/AITarget_callbacks.c:13; native player implementation N/4_World/Entities/ManBase/PlayerBase/AITargetCallbacksPlayer.c:45–84 |
| `ItemBase PlayerBase.GetItemInHands()` | N/4_World/Entities/ManBase/PlayerBase.c:6733–6735 |
| `EntityAI FindAttachmentBySlotName(string slot_name)` | N/3_Game/Entities/EntityAI.c:1897–1906 |
| `GameInventory EntityAI.GetInventory()` | N/3_Game/Entities/EntityAI.c:1884 |
| `int GameInventory.AttachmentCount()` | N/3_Game/Systems/Inventory/Inventory.c:205 |
| `EntityAI GameInventory.GetAttachmentFromIndex(int index)` | N/3_Game/Systems/Inventory/Inventory.c:220 |
| `bool ItemBase.IsLightSource()` | N/4_World/Entities/ItemBase.c:865–868; true overrides Headtorch_ColorBase.c:243, UniversalLight.c:117, TLRLight.c:99 under ItemBase subdirectories |
| `bool EntityAI.IsIgnited()` | N/3_Game/Entities/EntityAI.c:544–548; reads energy manager working state; FlammableBase override N/4_World/Entities/ItemBase/Torch.c:141–144 |
| `float PlayerBase.GetVisibilityCoef()` | N/4_World/Entities/ManBase/PlayerBase.c:5443–5445 |
| `float Game.GetDayTime()` | N/3_Game/Global/Game.c:437–440; documented as current server daytime |
| `bool Object.IsAlive()` | N/3_Game/Entities/Object.c:517–519 |
| `vector Object.GetPosition()` | N/3_Game/Entities/Object.c:287 |
| `NoiseSystem Game.GetNoiseSystem()` | N/3_Game/Global/Game.c:738 |
| `void NoiseParams()`; `void LoadFromPath(string noise_path)` | N/3_Game/Noise.c:18–25 |
| `void NoiseSystem.AddNoisePos(EntityAI source_entity, vector pos, NoiseParams noise_params, float external_strenght_multiplier = 1.0)` | N/3_Game/Noise.c:7 |
| `OnFinishProgressServer(ActionData action_data)` hook | N/4_World/Classes/UserActionsComponent/Actions/ActionContinuousBase.c:289 |

`HCInteriorsModule.Get/CommitSearch`, the policy/helper methods, and
`HCInteriorSite.Phase` are authored interfaces rather than engine APIs.
The noise config path is an exact vanilla precedent in
N/4_World/Classes/UserActionsComponent/Actions/Interact/ActionOpenDoors.c:78–90.
This verifies the script usage, not effective config data, loudness, audible
player sound or infected response. `AddNoisePos` is an AI noise interface;
rendered rummaging audio is not proved or implemented by that call.

**Dedicated-server callback context**

N/4_World/Entities/ManBase/PlayerBase.c:6317–6326 registers
`SetAITargetCallbacks(new AITargetCallbacksPlayer(this))` specifically for
`INSTANCETYPE_SERVER` or single player. The registration interface is native at
N/3_Game/Entities/EntityAI.c:3279. The captured player is the target:
N/4_World/Entities/ManBase/PlayerBase/AITargetCallbacksPlayer.c:7–11.
`pApplicant` is the observer in the sibling vision-point method: that method
casts it to `DayZInfected`, reads its mind state, and returns a point on the
target player (same file :21–42). The range modifier itself reads the target's
movement/stance and ignores the applicant (:45–84). The change forwards the
same applicant to super and derives its new factor from the captured target.

Thus this is a real server-registered AI-target callback, not a client UI hook.
A complete cache search finds the base declaration and player override, but no
script call expression invoking `GetMaxVisionRangeModifier`: invocation is
behind the native boundary. The exact engine invocation, constructor capture at
runtime, callback frequency, affected AI species and resulting sense/range
semantics cannot be proved from this cache. In particular, the override does
not restrict `pApplicant` to infected; any other engine consumer would receive
the factor too. No unobserved animal behavior is asserted as a verified defect.
Keep the closed qualification gate and observe these points during acceptance.

**Numerical and unset-state audit**

At HCInfectedVision.c:55–119, `Finite` uses ordered bounded comparisons, which
reject NaN and both infinities in the repository's explicit binary32 model.
It also intentionally rejects finite magnitudes above 1,000,000.
Clothing <=0 or rejected values use a neutral clothing component; positive
values clamp to 0.6–1.3. Invalid hours (<0, >=24, nonfinite) give zero nightness;
valid hours yield 0–1. Invalid lit values give no light bonus; the runtime adapter
only supplies 0 or 1. A null captured player returns the native value; a null
`PlayerFactor` input returns 1.0. Native clothing initializes to 1.0 at
N/4_World/Entities/ManBase/PlayerBase.c:390, then recomputes on attach/detach
(:1502–1511, :1551–1559). The coefficient is the ten-slot mean (:5405–5436),
fed by `visibilityModifier` in
N/4_World/Entities/Core/Inherited/InventoryItem.c:977–998.

The product is bounded before the final finite check: clothing 0.6–1.3,
darkness 0.75–1.0, light 1.0–1.5. The final finite check precedes both clamps,
so NaN cannot bypass comparison-only clamping. Final factor is 0.6–1.3;
there is no zero, negative, infinity or NaN factor in the tested arithmetic.
An invalid individual component becomes neutral for that component, not
necessarily a neutral whole result: e.g. invalid clothing at night still gives
darkness 0.75. Also, the policy comment's “1.0 means lit, anything else unlit”
is narrower than the actual >=0.5 finite predicate; the adapter supplies only
0/1, so neither wording issue is reported as a reachable gameplay defect.

Native super uses finite speed/stance constants
(N/3_Game/PlayerConstants.c:263–268), producing 0.225–1.25. With this factor,
the combined result is about 0.135–1.625; 0.6–1.3 bounds the added factor, not
the whole native result. No numerical blindness or omniscience was verified.
This statement assumes the pinned vanilla super; other mods replacing its
return value are outside the reviewed diff. Engine LOS remains native, and its
interaction with the factor remains unobserved.

**Search emission and race audit**

HCInteriorAction.c:68–74 reads the before phase, synchronously calls
`CommitSearch`, then checks the after phase. HCSearchNoise.c:22–24 admits only
0→2. `CommitSearch` in HCInteriorModule.c:494–523 refuses invalid/early actions,
reserves phase 1 before grant I/O (:503), resets to 0 on a negative result,
sets 3 for stopped results, and sets 2 only for result 2 (:513). Reentry while
phase 1 cannot qualify as 0→2; a repeated completion after success sees 2→2.
Session/owner checks are at :438–459 and :502. End/cancel clears the bound site
at :525–537; no cancel/end hook was given a noise call. The action's six-second
component is at HCInteriorAction.c:10.

Native completion dispatch is server-only in
N/4_World/Classes/UserActionsComponent/Actions/ActionContinuousBase.c:247–267.
HCSearchNoise.c:53 also checks server, player and alive state. A missing game,
player or noise system suppresses emission. Successful emission allocates one
`NoiseParams`, loads one vanilla path and calls `AddNoisePos` once; there is no
timer, recursion, loop or `AddNoiseTarget`. No script-level interleaving between
the phase read and `CommitSearch` was found, and no concrete native reentrant
callback was found that duplicates emission. This is source reasoning, not
proof of engine scheduling. A missing/dead actor or unavailable noise system
can legitimately suppress noise after a committed search. The bound is at
most one noise per completed site, not a global cooldown or proof of loudness.

**Cost and Enforce audit**

The added vision helpers allocate no objects on the admitted path. Super still
allocates `HumanMovementState` on every call
(N/4_World/Entities/ManBase/PlayerBase/AITargetCallbacksPlayer.c:47); this is
existing vanilla cost, including when the added feature is closed. Gate file
existence and admission logging occur once per VM lifetime. The admitted path
checks held item and headgear, then at most eight direct held-item attachments,
short-circuiting when it finds a light. No player/world scans or recursion.
Each call also does a headgear slot-name lookup
(N/3_Game/Entities/EntityAI.c:1897–1904), clothing getter and one `GetDayTime`.
The clock is a native prototype; its implementation/cost and the callback rate
are not exposed. There is no evidence supporting a measured cost claim or
budget acceptance at 3–6 players. Runtime profiling remains required.

`enforce-audit.log` records no ternary, leading logical operator, type-name
collision or override-parameter mismatch in the three changed Enforce files.
The added calls use no out arguments. Local names are unique within each new
method, including sibling scopes. Maximum '+' tokens per semicolon statement
is 2 (the bounded loop increment); the other changed files have 0. The sole
new loop is capped at eight. Constructor `pPlayer` and override `pApplicant`
match the installed declarations. No syntax defect was verified; the supplied
native compile additionally supports syntax acceptance.

**Independent mutation results**

Command: `PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/noise-vision-solreview/run_mutants.py`.
The unmodified scratch baseline passes all 22 subject tests. Each mutant gets
its own three authored source copies and full 22-test run. Mutations are never
written into `mods/` or tracked tests. Every killed mutant has assertion
failures, with zero harness errors. Logs live under `mutants/<name>/tests.log`;
machine-readable results are in `mutation-results.json`.

| Mutant | Changed behavior | Writer suite |
|---|---|---|
| 01_zero_floor | Final lower clamp returns 0 | KILLED, 1 failure |
| 02_raise_ceiling | Final upper clamp returns 13 | KILLED, 2 failures |
| 03_noise_either_phase | Noise phase test uses OR | KILLED, 1 failure |
| 04_ignore_clock | Factor always uses noon | KILLED, 2 failures |
| 05_force_admission | Admitted returns true regardless of marker | SURVIVED |
| 06_reverse_vision_server_guard | Client admitted; server refused | SURVIVED |
| 07_ignore_headgear | Headgear branch always false | SURVIVED |
| 08_remove_actual_loop_cap | Count overwritten with uncapped count | SURVIVED |
| 09_discard_computed_factor | Factor overwritten with 1 before return | SURVIVED |
| 10_reverse_noise_server_guard | Client emission allowed; server refused | SURVIVED |
| 11_notify_before_commit | Noise check moved before commit | KILLED, 1 failure |
| 12_lights_always_unlit | IsLightSource branch always returns false | SURVIVED |

The scalar policies are behavioral tests executing authored Enforce text through
the repository's binary32 Python translator. The noise truth table is behavioral
for its predicate. The existing native-object integration tests are source-shape
checks. Neither category is a DayZ observation. Result: 5 killed, 7 survived.

**Commands and observed results**

Temporary writes were confined by prefixing the requested unittest commands
with `TMPDIR="$PWD/scratchpad-review/noise-vision-solreview/tmp"` and keeping
`PYTHONDONTWRITEBYTECODE=1`. No full-suite rerun was performed.

| Command | Observed result | Log |
|---|---|---|
| `python3 -m unittest tests.unit.test_v1_native_noise_vision tests.unit.test_script_syntax` | 29 tests, OK, 1.112 s | targeted.log |
| `python3 -m unittest discover -s tests/unit -v` | 2571 tests; 38 failures, 279 errors, 1 skipped; 102.712 s | full.log |
| `python3 scratchpad-review/noise-vision-solreview/test_light_classification.py` | 3 tests; 2 expected regression failures | light-red.log |
| Same command with `--fixed` | 3 tests, OK; only scratch candidate changed | light-green.log |
| `python3 scratchpad-review/noise-vision-solreview/test_review_contracts.py` | 8 tests, OK | review-contracts.log |

The full suite is **not green**. Of its errors, 277 are explicit checkout-path
refusals: 123 “experiment cannot be inside source checkout”, 111 “mission must
be outside source checkout”, 40 “destination must be outside source/root
directories”, and 3 “generated experiment must be outside the checkout”. The
other two errors are a dependent unassigned `result` and a missing staged
fixture. The 38 failures include expected success/exception/race hooks that
cannot be reached after those early refusals. All subject noise/vision and
script-syntax tests pass in that discovery run. This run cannot establish a
clean repository baseline under the permitted in-checkout temporary directory;
the failures are not attributed to this gameplay diff. A normal external-temp
suite run remains necessary in an appropriately authorized environment.

The first adapter-check attempt hit an existing translator limitation:
`new NoiseParams()` becomes `NoiseParams()()`. The synthetic constructor factory
was adjusted in the review harness only; the initial diagnostic is retained in
`review-contracts-initial.log`. It is not a product failure.

Before production acceptance, retain the writer's pending DayZDiag and normal
PBO/server checks, two-client light/noise/visibility observations, actual config
and AI response checks, constructor/callback observations, and measured callback
cost. No missing engine experiment is accepted by this report.
