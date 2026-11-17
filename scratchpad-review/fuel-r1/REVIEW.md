# Fuel siphon #53 — cross-model review R1

**Verdict: FIX-THEN-MERGE.** Three P1 findings and one P2 finding. No P0 or P3 findings. The implementation has suitable native API foundations, but its production admission and interruption boundaries need correction and its new production arithmetic does not preserve the strict no-created-fuel invariant.

Reviewed `git diff eb9ceb8 a1a8595`; HEAD was `a1a85952b04374e38d64c0f85be4194e8ebfeda6`. Scope: the three requested files. No repository source was edited, no git write command, DayZ, Wine, network, or delegated review was used. All authored artifacts are under `scratchpad-review/fuel-r1/`. Source hashes were verified unchanged by the mutation runner. Host-generated Banso telemetry is outside this review's authored artifacts.

Read `AGENTS.md`, `docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`, relevant module/status documentation, the diff and installed natives. `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` do not exist in this checkout, and a file-name search found no replacement spec/plan/tasks artifacts. Their consistency cannot be certified. This does not prevent the requested review; the active user product rules and runtime contract supply its requirements. The Banso CLI dispatched-worker guidance was followed; no lifecycle command or network-backed review panel was run.

All native references below are relative to **N = `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`**. Repository findings use repository-relative file:line. Source inspection and explicitly synthetic tests are not Enforce compilation or DayZ behavior evidence.

## Findings, highest severity first

### F1 — P1: production credit can round above the observed tank loss

**Locations:** `mods/HollowCountry/scripts/4_World/Crafting/HCFuelTransferPolicy.c:177` and `:182`; `mods/HollowCountry/scripts/4_World/Actions/HCFuelSiphon.c:175`.

`SiphonCreditMl` rounds `(before - after) * 1000` to binary32 and never checks whether that rounded value exceeds the exact loss represented by its inputs. It also ignores rounding in the destination quantity addition. Native `Liquid.FillContainer` calls `AddQuantity` (N `4_World/Static/Liquid.c:160–168`); `ItemBase.AddQuantity` performs `SetQuantity(GetQuantity() + value, ...)` (N `4_World/Entities/ItemBase.c:3393–3395`), and SetQuantity stores the clamped float at `:3356`. That addition can round upward even when `creditMl` itself is conservative.

Two explicit synthetic binary32 regressions fail against the actual authored policy, using the existing test transpiler:

1. `SiphonCreditMl(700, f32(0.7), 0)` returns **700 ml**, while the exact difference of those represented liter values is **699.999988079071 ml**.
2. Tank readbacks `10 -> 9.75` liters, step `250 ml`, vessel before `1023.9999389648438 ml`, maximum `20000 ml`: the policy returns `250 ml`. The native-style float addition produces vessel after `1274 ml`, a gain of **250.00006103515625 ml**, greater than the **250 ml** observed tank loss.

These are small arithmetic counterexamples, not evidence of an in-game large-scale duplication exploit. They nevertheless refute the unconditional no-creation claim in policy comments `:7–8`. The existing `CreditQuantum`, `ExactMilliliters`, and destination representability checks explicitly addressed these cases for the diagnostic; the production helpers bypass them. Tests for those old functions still passing do not cover the new callers.

**Fix:** plan a representable bounded debit, conservatively convert the observed loss, and account for the represented destination addition before crediting. Reuse or adapt the existing exact/conservative helpers; do not paper over the invariant with an arbitrary tolerance. Read back destination quantity and stop/report a mismatching receipt. Add regressions for both counterexamples and grids covering every new helper, including nonfinite inputs. No automatic debit replay or compensating refund on ambiguous readback.

### F2 — P1: interruption flush bypasses the eligibility and crafting gate that caused cancellation

**Locations:** `mods/HollowCountry/scripts/4_World/Actions/HCFuelSiphon.c:126`, `:155`, `:167`.

`ActionConditionContinue` checks live/nonruined car and vessel, engine/movement, reach/selection, actor in-vehicle state, and `ServerEnabled`. Once an action is interrupted, `Cancel` unconditionally enters `CalcAndSetQuantity`, whose server branch checks only car/vessel existence, `Liquid.CanFillContainer`, tank amount and capacity. It does not repeat the server admission or the other safety checks. `CanFillContainer` checks fullness, mask and liquid compatibility, **not** ruined state, engine, reach, actor, ownership or feature settings (N `4_World/Static/Liquid.c:235–271`).

Native callback evidence: `AnimatedActionBase.Do` interrupts when `CanContinue` fails (N `4_World/Classes/UserActionsComponent/AnimatedActionBase.c:419–428`); canceled callback completion calls the component's `Interrupt` (`:42–46`); `CABase.Interrupt` calls `Cancel` (N `.../ActionComponents/CABase.c:34–37`). Ordinary release also directly calls Cancel (N `.../Actions/ActionContinuousBase.c:110–115`). `CCIBase.CanContinue` rejects an item no longer in hands (N `.../ItemConditionComponents/CCIBase.c:8–10`), but the final flush ignores that condition too.

Thus pending fuel may still move after, for example, the actor leaves reach, the vessel becomes ruined/leaves hands, the car is destroyed or starts running, or core shutdown makes `ServerEnabled` false. The unsafe operation is one final pending step, not an endless source; its amount is not inherently restricted to 0.5 seconds (see conservation analysis).

**Fix:** make every server debit, including Cancel, revalidate the current server gate and actor/car/held-vessel eligibility. Preserve partial-step flushing on a voluntary release while conditions remain valid. If current eligibility has become unsafe, clear pending work and stop without debiting. Repeated Cancel must be idempotent. Add behavioral traces for each invalidation and voluntary release, not just a check for the flush method's name.

### F3 — P1: registering the action enables unqualified production behavior by default

**Locations:** `mods/HollowCountry/scripts/4_World/Actions/HCFuelSiphon.c:19`, `:215`, `:233`, `:242`.

`ServerEnabled` admits any started core with `EnableCrafting=true`; that preference defaults true (`mods/HollowCountry/scripts/3_Game/HCSettings.c:32`). The action is unconditionally registered and attached to held containers. `HCServer.Start` sets `m_Started=true` after module startup (`.../Core/HCServer.c:34–41`); it is not fuel qualification. No fuel acceptance/admission flag exists on this path. In particular it also bypasses the existing crafting module's `m_Started && m_Validated` gate (`.../Crafting/HCCraftingModule.c:7–17`, `:34–43`). Crafting definition validation alone would not qualify fuel transactions either.

The opening action comment explicitly says DayZDiag and local-server acceptance are pending (`HCFuelSiphon.c:8–9`); its only stated safeguard concerns whether the README calls the feature shipped. That is documentation, not a production execution barrier. `docs/MODULE_STATUS.md:33–37` describes compilation of the **different, unregistered diagnostic**, with actual fuel movement and ordinary client registration outstanding. It supplies no runtime acceptance for this action.

This contradicts AGENTS.md's requirement that production feature enablement wait for DayZDiag and normal PBO/server testing. The active request permits source/package authoring before the client connects; it does not accept missing runtime experiments.

**Fix:** retain the source and registration if desired, but put execution behind explicit fuel admission that defaults closed while acceptance is pending, in addition to `EnableCrafting` and relevant crafting lifecycle state. An isolated diagnostic/local-test opt-in may exercise the candidate. Record DayZDiag compilation, normal PBO/server transfer and interruption receipts, two-client contention/progress behavior, and save/restart recovery as pending until performed. Do not disable crafting globally as a workaround or mark those experiments accepted from offline tests.

### F4 — P2: source-token assertions do not test the production action's behavior

**Locations:** `tests/unit/test_fuel_siphon_production.py:84`, `:94`, `:103`, `:112`; new scalar cases at `:41–66`.

The action tests establish presence/order of names, not executable control flow, arguments, authority or transaction outcomes. The exact requested suite passes all 18 tests, but **15 of 20 independent source mutants survive**. Surviving defects include client-side debits/server no-op, double credit, liter/ml debit error, fabricated tank readback, unreachable cancel flush, ignored feature disable, reversed distance/selection, accepting destroyed cars, replaying pending quantity and never advancing server progress. The old policy's extensive tests exercise the unregistered diagnostic path. New helper validation also lacks an all-argument invalid-input matrix.

**Fix:** add stdlib behavioral tests executing authored action/component control flow against explicitly synthetic native collaborators, or another execution harness that actually observes branches and values. Keep the useful registration contracts. Assert zero mutations on clients, correct server gate behavior, exactly one measured debit/credit, fresh tank/free-space caps, readback refusal, invalidation-safe cancellation, repeated-cancel idempotence, delta limits, and client prediction versus authoritative receipts. Add binary32 grids for the **Siphon** functions. Kill the listed non-equivalent mutants, then retain runtime acceptance separately.

## Native API and compile-rule audit

No missing API, incompatible call arity, or override parameter-name mismatch found by inspection. This is a declaration audit, **not a successful Enforce compile**. The car-only implementation deliberately uses Car/CarScript methods rather than the more general native refuel's Transport wrappers. The inheritance is N `4_World/Entities/Vehicles/CarScript.c:94` (`extends Car`) and N `3_Game/Vehicles/Car.c:87` (`extends Transport`).

| Authored use | Installed 1.30 declaration/evidence |
| --- | --- |
| `GetGame()`; `.IsServer()` | N `3_Game/gameplay.c:636`: `DayZGame GetGame()`; N `3_Game/Global/Game.c:1120`: `proto native bool IsServer()` |
| `CarScript.Cast(target.GetObject())` | N `1_Core/proto/EnScript.c:94`: `proto static Class Cast(Class from)`; N `4_World/Classes/UserActionsComponent/ActionTargets.c:142`: `Object GetObject()`; type chain above |
| `car.GetFluidCapacity(CarFluid.FUEL)` | N `3_Game/Vehicles/Car.c:355`: `proto native float GetFluidCapacity(CarFluid fluid)` |
| `car.GetFluidFraction(CarFluid.FUEL)` | N `3_Game/Vehicles/Car.c:363`: `proto native float GetFluidFraction(CarFluid fluid)` |
| `car.Leak(CarFluid.FUEL, float)` | N `3_Game/Vehicles/Car.c:366`: `proto native void Leak(CarFluid fluid, float amount)`; native fill component's liter conversion N `.../ActionComponents/CAContinuousFillFuel.c:121` |
| `CarFluid.FUEL` | N `3_Game/Vehicles/Car.c:18`: `enum CarFluid : ETransportFluid {}`; N `3_Game/Vehicles/Transport.c:52–54`: base enum FUEL; existing CarScript usages corroborate it |
| `player.IsInVehicle()`; `player.GetDeltaT()` | N `4_World/Entities/DayZPlayerImplement.c:468`: `bool IsInVehicle()`; `:494`: `float GetDeltaT()` |
| `car/item.IsDamageDestroyed()` | N `3_Game/Entities/Object.c:981`: `proto native bool IsDamageDestroyed()` |
| `car.EngineIsOn()`; `car.IsMoving()` | N `3_Game/Vehicles/Car.c:230`: `proto native bool EngineIsOn()`; N `4_World/Entities/Vehicles/CarScript.c:2221`: `override bool IsMoving()` |
| `item.IsLiquidContainer()` | N `4_World/Entities/ItemBase.c:825`: `bool IsLiquidContainer()`; tests config mask at `:827` |
| `item.GetQuantity()`; `.GetQuantityMax()`; `.GetLiquidType()` | N `4_World/Entities/ItemBase.c:3490`: `override float GetQuantity()`; `:3439`: `override int GetQuantityMax()`; `:3887`: `override int GetLiquidType()`; int maximum converts to float at policy call |
| `Liquid.CanFillContainer(item, LIQUID_GASOLINE)` | N `4_World/Static/Liquid.c:235`: `static bool CanFillContainer(ItemBase container, int liquid_type, bool ignore_fullness_check = false)` |
| `Liquid.FillContainer(vessel, LIQUID_GASOLINE, creditMl)` | N `4_World/Static/Liquid.c:160`: `static void FillContainer(ItemBase container, int liquid_type, float amount)`; returns no receipt |
| `car.GetActionDistanceFuel()`; `.GetRefillPointPosWS()`; `.GetActionCompNameFuel()` | N `3_Game/Vehicles/Transport.c:467`: `float GetActionDistanceFuel()`; `:472`: `vector GetRefillPointPosWS()`; `:462`: `string GetActionCompNameFuel()` |
| `vector.DistanceSq(vector, vector)`; `player.GetPosition()` | N `1_Core/proto/EnConvert.c:210`: `proto static native float DistanceSq(vector v1, vector v2)`; N `3_Game/Entities/Object.c:287`: `proto native vector GetPosition()` |
| `car.GetActionComponentNameList(index, selections)`; `target.GetComponentIndex()` | N `3_Game/Entities/Object.c:192`: `proto native owned int GetActionComponentNameList(int componentIndex, TStringArray nameList, string geometry = "")`; N `.../ActionTargets.c:159`: `int GetComponentIndex()` |
| `new TStringArray`, `.Count()`, `.Get(i)`, `actions.Insert(typename)` | N `1_Core/proto/EnScript.c:731`: `typedef array<string> TStringArray`; `:739`: `typedef array<typename> TTypenameArray`; array methods `:380` Count, `:399` Get, `:407` Insert |
| vessel/car `.GetLiquidThroughputCoef()`; `Math.Min(float,float)` | N `3_Game/Entities/EntityAI.c:4019`: `float GetLiquidThroughputCoef()` (inherited vessel default); N `4_World/Entities/ItemBase/Edible_Base/Bottle_Base/CanisterGasoline.c:38` and N `4_World/Entities/Vehicles/CarScript.c:385` overrides; N `1_Core/proto/EnMath.c:553`: `proto static float Min(float x, float y)` |
| component overrides `Setup/Execute/Cancel(ActionData action_data)`, `GetProgress()` | N `.../ActionComponents/CABase.c:20`, `:24`, `:29`, `:62`, with exactly those parameter names; `CAContinuousBase` inherits CABase at `.../CAContinuousBase.c:1` |
| `OnCompletePogress(action_data)` | N `.../ActionComponents/CAContinuousBase.c:8`: `void OnCompletePogress(ActionData action_data)`; spelling matches engine |
| callback `override void CreateActionComponent()` | N `.../AnimatedActionBase.c:63`: `void CreateActionComponent()`; same override in N `.../Actions/Continuous/Vehicles/ActionFillFuel.c:5` |
| action `CreateConditionComponents()`, `ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)`, `ActionConditionContinue(ActionData action_data)` | N `.../Actions/Continuous/Vehicles/ActionFillFuel.c:26`, `:32`; N `.../ActionBase.c:436`, `:441`; names match engine |
| `new CCINonRuined`; `new CCTNone` | N `.../ItemConditionComponents/CCINonRuined.c:1`; N `.../TargetConditionsComponents/CCTNone.c:1`; native refuel uses both at N `.../Actions/Continuous/Vehicles/ActionFillFuel.c:28–29` |
| `RegisterActions(TTypenameArray actions)` plus super | N `.../ActionConstructor.c:27`, identical signature/name |
| `Bottle_Base.SetActions()` plus super; `AddAction(typename)` | N `4_World/Entities/ItemBase/Edible_Base/Bottle_Base.c:356–360`; N `4_World/Entities/ItemBase.c:255`: `void AddAction(typename actionName)` |
| animation/stance/soft-skill constants | N `3_Game/dayzplayer.c:860`, `:633–634`: qualified DayZPlayerConstants members used; N `.../Actions/ActionConstants.c:142`: UASoftSkillsWeight.PRECISE_LOW; native pond fill uses same animation at N `.../Actions/Continuous/ActionFillBottleBase.c:37–40` |
| `UAQuantityConsumed.FUEL`, UA return states, gasoline constant, `float.MAX` | N `.../Actions/ActionConstants.c:17`: 500 ml/s; N `3_Game/constants.c:496`, `:498–499`, `:519`: global integer states; `:582`: global `LIQUID_GASOLINE=8192`; N `1_Core/proto/EnConvert.c:112`: MAX=FLT_MAX |

In this table `.../` within an action-system path means `4_World/Classes/UserActionsComponent/`.

`HCServer.Get`, `IsStarted`, `GetSettings`, `HCSettings.EnableCrafting` and the policy helpers are project APIs, not invented engine calls. Their definitions are `mods/HollowCountry/scripts/4_World/Core/HCServer.c:10`, `:17`, `:16`, `mods/HollowCountry/scripts/3_Game/HCSettings.c:32`, and the reviewed policy file.

Compile-rule inspection of the new action and three new helpers:

- No ternary expression; no line starts with `||` or `&&`.
- No local identifier exactly collides with an installed engine type; no duplicate declarations across sibling scopes. Lowercase `car` is the same ordinary naming pattern used by natives; it is not the type `Car`.
- No statement has more than eight `+` operators; additions are single operations/`+=` (or loop `i++`).
- The sole new loop is bounded by `min(selections.Count(), 32)`, action `:52–55`; the helpers have no loops.
- Enum members are qualified (`CarFluid.FUEL`, `DayZPlayerConstants.*`); `UA_*` and `LIQUID_GASOLINE` are declared global constants, not unqualified enum members. UAQuantityConsumed and UASoftSkillsWeight constants are qualified.
- All override parameter names match their installed base signatures. Registration super calls are present. Constructor arguments and return types match their use.

## Conservation, interruption and prediction analysis

Under finite scalar inputs and exact arithmetic, session = min(tank ml, vessel free ml); step additionally caps pending and remaining session; credit = min(step, observed loss). Fresh tank/free-space reads occur for every server debit. Empty tanks cannot provide fuel; static wrecks fail CarScript cast and ruined cars fail initial eligibility. Client code returns before Leak/FillContainer. These are good structural properties, subject to F1/F2 and native qualification.

Cancel first captures and zeroes `m_PendingMl` (`HCFuelSiphon.c:139–140`), then applies one capped transfer. A second Cancel with no intervening Execute cannot replay the same pending amount. A missing player returns UA_ERROR without debit. A vanished car/vessel or incompatible/full vessel stops before debit. Partial steps on ordinary release do flush, consistent with native `CAContinuousFillFuel.Cancel` at N `.../ActionComponents/CAContinuousFillFuel.c:86–93`. Safety-invalidated cancellation needs F2's guard.

**Large loss:** I did not establish an ordinary successful synchronous base-car/base-container path that discards a large volume. Both tank and capacity bound each request, and the native FillContainer preflight is repeated. However, there is no transaction/receipt guarantee: Leak and FillContainer are separate; FillContainer returns void; destination readback is absent; `m_MovedMl` advances by proposed credit even if the destination did not gain it. A crash or native/mutation refusal after debit can lose that step. The credit helper explicitly clips excess observed loss and continues (policy `:180–182`; its test accepts 1 liter lost for a 250 ml credit at test `:63`). That test does **not** demonstrate that Leak actually overdebits.

The 0.5-second setting is a flush threshold, not an elapsed-time/volume cap. Execute adds the entire `GetDeltaT()` to pending (`:111–116`). With explicit synthetic inputs of default 500 ml/s, 60 seconds delta, 50 liters fuel and 20,000 ml free space, one step is capped at **20,000 ml**, not 250 ml. Such a delta has not been observed in DayZ here. This bounds a conditional failed/crashed-step loss only by the whole session, potentially a canister. Add a finite positive delta check, maximum elapsed/quantum policy with discarded catch-up, destination receipt checks and a stop/diagnostic on unexpected overdebit or failed credit. Do not infer an engine tolerance or retry/refund an ambiguous debit. Qualification must cover this failure boundary.

**Client/server divergence:** client Calc adds requested/clamped ml (`:144–149`), while server adds observed credit (`:169–176`). Setup also snapshots each side's tank/quantity independently (`:95–96`). If a requested 250 ml yields only 125 ml observed credit, one step changes predicted versus authoritative progress by 125 ml; if observed loss is zero, server stops while the client advances. With a synthetic 5,000 ml session and repeated 250 ml requests/125 ml credits, client would reach its session after 20 steps, server after 40 if it could continue. GetProgress uses these differing totals (`:130–134`), and the component sends no authoritative receipt to reconcile them. No local test executes this interaction. Native refuel also uses prediction (N `.../CAContinuousFillFuel.c:108–121`), so a predicted progress bar is not by itself proof of a bug or client-owned fuel. Actual early cancellation, stale UI and two-client contention remain acceptance questions. Test these traces and establish authoritative completion/cancellation behavior; do not treat predicted moved ml as a server receipt.

## Eligibility, registration and native action overlap

| Check | Comparison with installed native ActionFillFuel |
| --- | --- |
| Vehicle kind/destroyed | Native casts Transport (`:37–41`); new action casts CarScript and rejects destroyed cars (`HCFuelSiphon.c:34–36`). Cars are intended; boats/motorbikes are intentionally excluded. Static decorative wrecks cannot pass. |
| Selection/reach | Same component-list selection and strict squared fuel-point distance as native refuel N `.../Actions/Continuous/Vehicles/ActionFillFuel.c:53–63`. New loop only scans first 32 selections; this is a deliberate bound and a possible false negative on custom models, not a distant-target bypass. |
| Engine/movement | Additional checks beyond native refuel. `CarScript.IsMoving` means speedometer absolute >3.5 (N `4_World/Entities/Vehicles/CarScript.c:2221–2223`), so this is not a guarantee of zero movement. No stationary-at-any-speed product rule was supplied. |
| Fuel amount | Native refuel requires fraction <0.98 (`:50`); siphon correctly requires >0. Near-full tanks remain valid siphon sources; the fill cutoff should not be copied to siphon. |
| Destination fullness/type/mask | Native requires a nonempty gasoline donor (`:43–47`); siphon correctly reverses capacity and accepts an empty or gasoline vessel, with CanFillContainer checking mask/fullness/type. Mask failure is enforced, not guessed. |
| Ruined/in vehicle/held item | New Allowed rejects ruined vessel and an actor in a vehicle. CCINonRuined supplies the normal native item check; CCIBase continuation also requires the exact item in hands. New Cancel bypasses those checks (F2). |
| Open/frozen | New comment describes an open vessel but Allowed does not call IsOpen. The intended native canister, WaterBottle and Canteen all return true from IsOpen (N `.../Bottle_Base/CanisterGasoline.c:54`, `WaterBottle.c:55`, `Canteen.c:59`); Pot/Cauldron likewise return true (`:116`, `:89`). No demonstrated closed intended-vessel defect. Custom subclasses with a meaningful closed/frozen state need explicit eligibility if admitted; CanFillContainer does not supply those checks. |
| Feature preference | On server, conditions reject EnableCrafting=false; client always returns true after Allowed, so it can show a prompt the server refuses while disabled. This is not a client-authority bypass. Admission and final-mutation checks still need F2/F3. |

Bottle registration covers intended classes: N `4_World/Entities/ItemBase/Edible_Base/Bottle_Base/CanisterGasoline.c:1`, `WaterBottle.c:1`, `Canteen.c:1` all derive from Bottle_Base and do not replace its SetActions. The hook therefore reaches the gasoline canister, water bottle and canteen. It also reaches other Bottle_Base descendants such as Pot/Cauldron (their SetActions call super and do not remove the new action), subject to their configured liquid mask; this is broader than a canister-only action. Script ancestry does not prove every item's config accepts gasoline; CanFillContainer enforces that at runtime.

There is **intentional simultaneous eligibility** with ActionFillFuel: a partly filled gasoline vessel with spare capacity and a fueled car below native 0.98 fullness can offer both directions at the same fuel selection. Both hooks retain `super.SetActions`; neither replaces the other. They are separate action types/texts with a normal continuous action input, so no source-level overwrite is present. Their menu ordering/discoverability and opposite-direction use by two players require runtime checks. Both set `m_LockTargetOnUse=false` (new `:199`, native FillFuel `:22`), permitting contention. Serial fresh tank reads avoid a stale preplanned shared balance, but neither asynchronous engine atomicity nor crash recovery is established offline; do not label this a proven concurrency duplication exploit.

ActionDrainLiquid cannot target the same car: it requires `ItemBase.Cast(target.GetObject())` and Liquid.CanTransfer (N `.../Actions/Continuous/ActionDrainLiquid.c:33–41`). CarScript is a Car/Transport, not ItemBase. It remains available for draining another real container and does not replace the car siphon.

## Actual verification evidence

Requested command, run against unmodified repository files:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_fuel_siphon_production tests.unit.test_fuel_transfer -v
```

Exit status **0**. Actual complete combined output (`baseline.txt`):

```text
test_action_is_registered_on_held_liquid_containers_like_native_refuel (tests.unit.test_fuel_siphon_production.SiphonActionContractTests.test_action_is_registered_on_held_liquid_containers_like_native_refuel) ... ok
test_eligibility_mirrors_native_refuel_in_reverse (tests.unit.test_fuel_siphon_production.SiphonActionContractTests.test_eligibility_mirrors_native_refuel_in_reverse) ... ok
test_server_gate_follows_the_crafting_preference (tests.unit.test_fuel_siphon_production.SiphonActionContractTests.test_server_gate_follows_the_crafting_preference) ... ok
test_session_and_interruption_follow_native_component (tests.unit.test_fuel_siphon_production.SiphonActionContractTests.test_session_and_interruption_follow_native_component) ... ok
test_transfer_checks_destination_before_debit_and_credits_readback (tests.unit.test_fuel_siphon_production.SiphonActionContractTests.test_transfer_checks_destination_before_debit_and_credits_readback) ... ok
test_credit_is_what_the_tank_actually_lost_capped_by_the_step (tests.unit.test_fuel_siphon_production.SiphonPolicyTests.test_credit_is_what_the_tank_actually_lost_capped_by_the_step) ... ok
test_session_is_bounded_by_real_tank_fuel_and_vessel_space (tests.unit.test_fuel_siphon_production.SiphonPolicyTests.test_session_is_bounded_by_real_tank_fuel_and_vessel_space) ... ok
test_step_never_exceeds_tank_space_or_remaining_session (tests.unit.test_fuel_siphon_production.SiphonPolicyTests.test_step_never_exceeds_tank_space_or_remaining_session) ... ok
test_binary32_overflow_underflow_and_invisible_changes (tests.unit.test_fuel_transfer.FuelTransferTests.test_binary32_overflow_underflow_and_invisible_changes) ... ok
test_credit_and_plan_reject_rounded_up_vessel_gain (tests.unit.test_fuel_transfer.FuelTransferTests.test_credit_and_plan_reject_rounded_up_vessel_gain) ... ok
test_credit_requires_measured_debit_and_fresh_space (tests.unit.test_fuel_transfer.FuelTransferTests.test_credit_requires_measured_debit_and_fresh_space) ... ok
test_finite_predicate_uses_binary32_range (tests.unit.test_fuel_transfer.FuelTransferTests.test_finite_predicate_uses_binary32_range) ... ok
test_given_half_second_then_one_bounded_quantum (tests.unit.test_fuel_transfer.FuelTransferTests.test_given_half_second_then_one_bounded_quantum) ... ok
test_invalid_plan_inputs_fail_closed (tests.unit.test_fuel_transfer.FuelTransferTests.test_invalid_plan_inputs_fail_closed) ... ok
test_readback_checks_reject_invalid_scalars_at_each_position (tests.unit.test_fuel_transfer.FuelTransferTests.test_readback_checks_reject_invalid_scalars_at_each_position) ... ok
test_receipt_conservation_is_not_success_or_atomicity (tests.unit.test_fuel_transfer.FuelTransferTests.test_receipt_conservation_is_not_success_or_atomicity) ... ok
test_rounding_cannot_hide_created_fuel (tests.unit.test_fuel_transfer.FuelTransferTests.test_rounding_cannot_hide_created_fuel) ... ok
test_synthetic_grid_respects_all_caps (tests.unit.test_fuel_transfer.FuelTransferTests.test_synthetic_grid_respects_all_caps) ... ok

----------------------------------------------------------------------
Ran 18 tests in 0.059s

OK
```

Additional review-only red regressions, no production implementation change or claimed green result:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/fuel-r1/test_review_conservation.py
```

Python test process exit status **1**. Actual complete output (`conservation-red.txt`):

```text
test_credit_does_not_round_above_observed_loss (__main__.ReviewConservationTests.test_credit_does_not_round_above_observed_loss) ... FAIL
test_destination_gain_does_not_round_above_credit (__main__.ReviewConservationTests.test_destination_gain_does_not_round_above_credit) ... FAIL

======================================================================
FAIL: test_credit_does_not_round_above_observed_loss (__main__.ReviewConservationTests.test_credit_does_not_round_above_observed_loss)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/v1-fuel/scratchpad-review/fuel-r1/test_review_conservation.py", line 17, in test_credit_does_not_round_above_observed_loss
    self.assertLessEqual(Fraction(credit), exact_loss)
AssertionError: Fraction(700, 1) not less than or equal to Fraction(1468006375, 2097152)

======================================================================
FAIL: test_destination_gain_does_not_round_above_credit (__main__.ReviewConservationTests.test_destination_gain_does_not_round_above_credit)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/v1-fuel/scratchpad-review/fuel-r1/test_review_conservation.py", line 32, in test_destination_gain_does_not_round_above_credit
    self.assertLessEqual(gain, exact_loss)
AssertionError: Fraction(4096001, 16384) not less than or equal to Fraction(250, 1)

----------------------------------------------------------------------
Ran 2 tests in 0.017s

FAILED (failures=2)
credit= 700.0 exact observed loss ml= 699.999988079071
vessel before= 1023.9999389648438 after= 1274.0 gain ml= 250.00006103515625 tank loss ml= 250.0
```

### Source mutation experiment

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/fuel-r1/mutate.py
```

Runner exit status **0**. Twenty independent, non-equivalent source mutations; each starts from the original action/policy and changes only one scratch copy. The runner imports the **existing unchanged tests**, redirects their `ACTION` and `SOURCE` paths to those copies, and runs the same 18-test suite anew for every mutant. The policy extractor reads the redirected file. Diagnostic registration checks continue to read the original unmodified diagnostic. No mutant is applied to repository source. Both original source hashes are checked after the run. No killed mutant failed due to a harness parse/import error.

**5 killed / 15 survived**. A survived token-preserving mutant is not equivalent merely because its test remains green. In particular the invalid scalar guard mutations change behavior for invalid remaining, maximum or after-fuel values absent from the new tests.

| ID | Source | Mutation | Result |
| --- | --- | --- | --- |
| M01 | action | Invert mutation authority guard | **SURVIVED** |
| M02 | action | Double vessel credit | **SURVIVED** |
| M03 | action | Debit milliliters as liters | **SURVIVED** |
| M04 | action | Replace readback with fabricated after value | **SURVIVED** |
| M05 | action | Make Cancel flush unreachable | **SURVIVED** |
| M06 | action | Ignore disabled crafting when settings exist | **SURVIVED** |
| M07 | action | Invert distance eligibility | **SURVIVED** |
| M08 | action | Allow destroyed car | **SURVIVED** |
| M09 | action | Replay pending transfer on next flush | **SURVIVED** |
| M10 | action | Never advance server progress | **SURVIVED** |
| M11 | action | Accept wrong car selection | **SURVIVED** |
| M12 | action | Remove held-item siphon registration | **KILLED** |
| M13 | policy | Session liters conversion off by ten | **KILLED** |
| M14 | policy | Remove pending cap | **KILLED** |
| M15 | policy | Remove remaining cap | **KILLED** |
| M16 | policy | Remove credit step cap | **KILLED** |
| M17 | policy | Remove session maximum finite check (last occurrence only) | **SURVIVED** |
| M18 | policy | Remove remaining finite check | **SURVIVED** |
| M19 | policy | Remove after-fuel finite check | **SURVIVED** |
| M20 | policy | Remove session conversion overflow check (last occurrence only) | **SURVIVED** |

Killed-test details and full per-mutant outputs are retained in `mutations.json`, `mutations.txt` and `mutants/Mxx/test-output.txt`; each directory also contains its two scratch source files. Killed tests: M12 registration contract; M13 session and step tests; M14/M15 step test; M16 credit test. Every survivor ran all 18 tests successfully. This is a targeted diagnostic sample, not a statistical mutation-coverage estimate.

## Exact fix and acceptance list

1. **F1:** make production debit/credit planning conservative under binary32, including actual destination addition; add destination readback/conservation diagnostics. Kill both recorded red regressions and equivalent rounded-step cases without adding a permissive tolerance.
2. **F2:** revalidate server admission, actor state/reach/selection, nonruined live car/engine state, exact held nonruined vessel and liquid capacity immediately before **every** debit, including Cancel. Valid voluntary cancel flushes once; invalidated cancel discards pending work and cannot mutate.
3. **F3:** default fuel execution admission closed pending native qualification, still honoring EnableCrafting and crafting lifecycle. Keep a deliberate isolated test path. Correct status/traceability so new source registration is distinguished from accepted production behavior.
4. Bound finite elapsed time/quantity per transfer and stop/report unexpected debit or destination receipt mismatch. Establish an explicit maximum possible failed-step loss; never replay or refund ambiguous debits automatically.
5. **F4:** replace the action's behavioral blind spots with authored-code execution against explicit synthetic collaborators; add new-helper invalid-input grids and client/server progress traces. Kill the listed non-equivalent survivors. Record actual failing and passing commands when implementing fixes.
6. Keep DayZDiag compilation, normal PBO/server tank/container receipts, ruined/empty/static-wreck refusal, interruption/disconnect, restart/recovery, feature-disable behavior, and two-client contention/prediction acceptance **pending**. No forbidden engine/network work was performed in this review. These experiments are production enablement requirements, not prerequisites to authoring the source fixes.

The design can be repaired within its native action/component structure. Merge the corrected source with execution admission closed; production acceptance requires the recorded native experiments.
