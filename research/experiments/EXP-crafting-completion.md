# EXP-crafting-completion — C06 registered recipes and lifecycle admission

Date: 2026-11-16. Installed native source: DayZ 1.30.164289.
Status: two concrete source defects corrected; focused offline tests GREEN.
**Actual compiler/runtime acceptance of this C06 snapshot remains PENDING.**
The coordinator owns the subsequent real compiler/PBO build. Earlier compiler
runs do not establish compilation of this new source. Native Windows, DayZDiag,
normal client/server gameplay and two-client acceptance remain distinct gates.

## Requirements and scope

Read AGENTS.md, docs/SPECIFICATION.md (especially section 5), canonical
docs/specs/001-survival-overhaul/spec.md, plan.md, completion-plan.md,
docs/MODULE_STATUS.md and docs/RUNTIME_IMPLEMENTATION_CONTRACT.md. Followed the
Banso worker contract without mutating coordinator lifecycle/spec/task state.
C06 maps T017/T023, FR-007 and AC-006 to native recipe execution and integrated
lifecycle failure boundaries. FR-011 still requires build-specific evidence.

Only Crafting source, a new crafting-specific test module, its explicit synthetic
evidence fixtures and this report were changed. Existing three salvage pilots,
registration order, balance, recipe duration, shared core/settings and other
workers' files are unchanged. No commit, client requirement or enablement change.

## Native inspection before API use

Private source root (never copied into this repository):
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289`.
Pinned installed scripts.pbo SHA-256:
`09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a`.

| Inspected native file, relative to snapshot | SHA-256 |
| --- | --- |
| 4_World/Plugins/PluginBase/PluginRecipesManager.c | 8245733df634257b8ecb19e0f4e06eddaa912d8bcf4a2a11e0e47750a68ec859 |
| 4_World/Classes/Recipes/RecipeBase.c | 88211d21144f20828981ba3f9663057c010cdf13ac38babc6648e7d8382f1178 |
| 4_World/Classes/Recipes/Recipes/PluginRecipesManagerBase.c | 55e2cd3d780d41ea988c604341c5caca651be812639714416fab7ea77497c979 |
| 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWorldCraft.c | c17963bdbf7fbfb9171b581bd23ae4b396e4f6bdfb8d90f0c0bbc0c3ebc234f2 |

Manager lines 40–41 expose the actual registered recipe array and name map;
constructor lines 52–56 registers before generating its cache. RegisterRecipe
443–456 inserts the instance, assigns GetID/SetID identity and records its name.
UnregisterRecipe 458–467 can leave a null array entry. RecipeIDFromClassname
470–476 returns -1 for missing names. RecipeBase 568–577 exposes GetID/SetID.
The new read-only lookup uses these observed declarations, with no guessed API.
GetPlugin/PluginRecipesManager.Cast are already used by native ActionWorldCraft.
RecipeBase 215–265, 362–426 and 521–545 were inspected again for actual mutation
and deletion ordering. Prior full recipe/pilot audit is recorded separately in
EXP-crafting-implementation.md and crafting-native-audit.json.

## Concrete defects and source fixes

1. **A pristine replacement could conceal a broken registered recipe.** Startup
   checks constructed new HCSalvage* objects and only checked that their names had
   nonnegative IDs. Thus changing the manager's actual registered yield to 200
   still passed the old startup audit. HCCraftingRegistryAudit.c now adds a
   read-only manager lookup with a signed lower/upper index bound, null check,
   exact classname and instance GetID agreement. HCCraftingNativeChecks.Run
   obtains the actual native plugin and checks all three cached instances.
   Missing plugin, missing name, out-of-range ID, null entry or identity mismatch
   rejects admission before unsafe dereference. CheckDefinition independently
   rejects null/wrong-class/wrong-ID inputs. Unconditional peer registration is
   preserved in HCRecipeRegistration.c.
2. **Module flags could outlive failed core startup.** A later module callback can
   abort startup before HCServer publishes IsStarted=true; Crafting's own static
   flags were already true. CanPreviewOrCraft now requires the actual server core
   to be started before consulting settings. This also denies a stopped core
   whose crafting callback has not yet run. The client-preview early return stays
   before all server-core access; commit remains server-owned through native
   PerformRecipe. Synthetic tests exercise every combination of core, module,
   validation and setting admission flags.

Startup audit is bounded: three O(1) lookups and fixed recipe/config checks. It
creates no entities, scans no inventory/world, registers no timers and adds no
retry, RPC, persistence, migration or claimed rollback mechanism. API/identifier
review avoided known Enforce keywords and native type-name collisions; no new
vector arithmetic or formula-heavy gameplay code was introduced. That review is
not an Enforce compiler result.

## Actual RED/GREEN and BDD-shaped scenarios

New `tests/unit/test_crafting_completion.py` extracts and executes the authored
flat admission/lookup/audit methods through a deliberately restricted translator.
Synthetic recipe/plugin/game DTOs are explicit. This executes the scalar policy
being changed; it is not a second gameplay implementation or a native interpreter.
Config responses in this harness are synthetic, not measured engine values.

- Given a registered recipe whose yield drifts, when startup audits it, then
  admission fails despite unchanged fresh defaults.
- Given stale module flags after failed/stopped core startup, when the server
  checks recipe eligibility, then admission fails.
- Given missing/null/inconsistent registration or manager, when audited, then
  admission fails without unbounded scanning or invalid indexing.
- Given client preview, when evaluated, then server core/profile is not accessed.

Actual commands and captured output under tests/fixtures/runtime:

1. `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_crafting_completion.py -v`
   initially produced 7 tests, 4 failures and 2 harness errors; captured in
   crafting-completion-tdd-red.txt. The translator initially omitted indexed
   array Count calls. Corrected that test helper before touching gameplay source.
2. The same command against unchanged gameplay source then produced **7 tests,
   6 actual assertion failures, no errors**; crafting-completion-cache-red.txt.
   The cached-yield mutation and stopped-core admission both returned true;
   missing-manager admission also incorrectly returned true. Lookup tests failed
   because the required bounded lookup did not exist. Client preview passed.
3. After implementing the two source fixes:
   `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_crafting*.py' -v`
   produced **18 tests passed**, including all 11 existing crafting tests and
   seven new tests; crafting-completion-green.txt. No expectations were relaxed
   to obtain GREEN.
4. `git diff --check -- mods/HollowCountry/scripts/4_World/Crafting` passed.

Coordinator owns full-suite/BDD bindings and final compiler integration. The
source snapshot was announced frozen after this GREEN. No full-suite, native
definition self-test execution or game acceptance is claimed here.

## Shared-core defects reported, not changed

Source inspection of HCServer.Start/Stop identifies incomplete lifecycle failure
handling. These are source failure boundaries, not observed injected engine faults:

- Start inserts every requested module into m_Active regardless of its own
  admission outcome; HCModule.OnStart has no result. Current log correctly calls
  this a requested start, so it must not be interpreted as successful admission.
- If a later startup callback aborts, earlier callbacks have run while the core
  remains unstarted. Stop immediately returns for an unstarted core and cannot
  unwind that partially populated m_Active list. A retry does not first clear or
  reconcile it. The new crafting gate conservatively denies actions in that state.
- Stop clears m_Started before invoking reverse callbacks. A callback abort could
  leave later callbacks/state uncleared while subsequent Stop immediately returns.
  The crafting core check denies further crafts even if its own callback was skipped.

Shared core is outside C06 worker ownership. Coordinator should determine its
supported abort/retry semantics and add core-specific failure-injection tests.
Enforce callback fault propagation itself still requires an actual engine probe.

## Remaining engine and atomicity constraints

Native RecipeBase performs **spawn results -> modify results -> modify
ingredients -> Do -> deferred ingredient deletion**. A result can therefore exist
before source consumption/deletion. Current single-result null-spawn guard avoids
consumption if both native inventory and ground creation fail; the synchronous
recipe guard rejects reentry on that instance. Neither supplies durable inventory
atomicity, rollback, idempotency across restart or recovery after a native fault.
A failure after spawning can leave source/result/tool inconsistent. A callback
abort can also leave the per-recipe busy flag set: conservative refusal afterward
is not a repair of that partial engine mutation. No demonstrated durable native
transaction API was found in these inspected recipe declarations. This task does
not claim no such capability could exist elsewhere in the engine.

Required remaining acceptance: compile this exact source/PBO, run authored native
definition/config checks, DayZDiag and normal PBO server/client load; full inventory
and forced null-spawn behavior; health/quantity boundaries and stack splitting;
cancel/death/unconsciousness/tool destruction; disablement during action; two-client
same-source completion, ownership transfer and disconnect/reconnect; native audio,
animation and compatible rifle wrap; server kills at spawn/consume/delete boundaries
with actual persisted item identities/counts after restart; 3–6-player performance.
The scoped algebraic graph remains a bounded review model, not proof of every
vanilla/mod economy transition. Native sound is inherited, not measured here.
Keep production acceptance and multiplayer-safe atomicity gates pending. No
feature flag was enabled and no measured transform or runtime outcome was invented.

## Authorized HCServer lifecycle addendum — 2026-11-16

The coordinator explicitly extended this worker's ownership to HCServer.c,
new tests/unit/test_core_lifecycle.py and this addendum. This supersedes the
earlier report's instruction to leave those concrete shared-core findings to
another worker. No other shared-core file or default was changed; no commit.

Implemented the requested conservative cleanup contract:

- Start retries clean a stale nonempty active list before self-tests, settings
  loading, registration or new module startup. An already running server remains
  a no-op, as do missing-game/client Start calls.
- Each enabled module is inserted before its OnStart call, so a callback abort
  leaves that module tracked for cleanup. Successful startup order is unchanged.
- Stop handles nonempty active state even when m_Started is false. It still
  clears the started flag and removes the tick callback before module cleanup.
- Reverse cleanup retains a local module reference, removes its active entry,
  then calls OnStop. If the callback aborts, a subsequent Stop or Start retry can
  finish remaining entries without repeating that callback. Empty repeated Stop
  is a no-op. Successful shutdown order remains the reverse of startup.

No Enforce try/catch or assumed exception facility was introduced. The callback
is allowed to abort the current call. Removal is progress tracking, not proof
that an aborting OnStop completed its own resource cleanup: that callback is
deliberately not retried, and any residue it leaves needs module-specific handling.

Before using array Remove, inspected the installed snapshot's
1_Core/proto/EnScript.c:457–470. Remove(int index) swaps the last entry into the
removed position. The lifecycle loop removes the last remaining index on each
iteration, so earlier module order is preserved; removal is constant time and
there are at most eight registered modules under the existing registry cap.
The synthetic array models that native swap behavior. Inspected file SHA-256:
`ec643bbf52113f3ab199affd12c10654a12eaeebfa56c13e2d49f4001433566f`.
No new native API beyond this inspected array method was used.

The new tests extract the **actual Start/Stop bodies** and translate their
restricted if/foreach/reverse-for/call/assignment syntax. They do not reproduce
the lifecycle algorithm in a separate implementation. Game, queue, registry,
settings and modules are explicit synthetic objects. A Python AbortCallback
exception models termination at a callback boundary; it does not establish
Enforce runtime fault propagation or native exception support.

Actual test command:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_core_lifecycle.py -v
```

The first harness run had five assertion failures and five translation errors
because its greedy if parser swallowed parentheses from an inline callback.
Corrected the parser to balance parentheses before changing HCServer source.
The corrected harness against unchanged HCServer produced the actual RED:

```text
Ran 9 tests in 0.007s
FAILED (failures=8)
```

Those failures covered both rejected-start retry subcases, initial partial stop,
stop without a game object, stale retry order, aborted retry cleanup, the
untracked aborting startup module and the repeated aborting stop entry. Normal
enabled filtering/order and empty/nonserver no-op cases already passed. After
the source fix, and again with native swap removal modeled, actual GREEN was:

```text
Ran 9 tests in 0.011s
OK
```

Adjacent regressions also passed: crafting discovery (`-p 'test_crafting*.py'`)
18 tests; settings discovery (`-p test_runtime_settings.py`) six tests. Total:
**33 focused tests passed**. Scoped git diff --check passed. Full-suite integration
is coordinator-owned. This addendum records actual tool output; no new runtime
fixture files were added outside the expressly assigned scope.

HCServer source frozen after GREEN, SHA-256:
`dc2b4dcd496eaaea42be5d7ec65df4346c3db5c64136af029181bfa73349f0ed`.
Coordinator was notified immediately for the final actual compiler pass. Compile
and engine fault-injection evidence for this source remain pending. These changes
do not supply durable inventory atomicity, guarantee cleanup after process death,
or turn a requested module start into an admitted module start; the shared void
OnStart interface and each module's internal admission flags remain unchanged.

## CR05 P2 addendum — native mutation precedence before compiler 010

Independent review identified a concrete admission hole: a cached recipe with
m_ResultSetFullQuantity[0]=true still passed the audited fixed quantity check.
The coordinator reported compiler 009 passed current World/Mission/init; that
does not establish compilation or execution of this subsequent CR05 correction.
This worker changed only HCCraftingNativeChecks.c, test_crafting_completion.py
and this addendum for the correction. No commit or production enablement change.

Reinspected the pinned installed RecipeBase.c, especially SpawnItems 224–231,
ApplyModificationsResults 295–355 and ApplyModificationsIngredients 379–426.
Also inspected MiscGameplayFunctions.c:271–316, whose SHA-256 is
`40a02625fba5ac9dd28568e511d988f5ed5e91cdc0177af1a07c3a0f9097d4e2`.
Concrete active precedence holes are now rejected on the actual registered
instance before Crafting admission:

| Field/branch | Observed native effect | Audit requirement |
| --- | --- | --- |
| m_ResultSetFullQuantity[0] | SetQuantityMax/ServerSetAmmoMax wins over the else-if fixed quantity | false |
| m_ResultReplacesIngredient[0] | After fixed result modifications, TransferItemProperties(..., true, true, false, false) transfers source variables without excluding quantity, followed by inventory transfer | -1 |
| m_ResultInheritsColor[0] | Appends ingredient color to the classname before spawning, bypassing the audited literal output class | -1 |
| m_IngredientAddQuantity[1] | Runs independently after tool health wear; can add material or consume additional tool quantity | 0 |

Other precedence was inspected without inventing nonexistent fields or blanket
checks on inactive switches:

- RecipeBase exposes no separate result-inherits-quantity flag here. Quantity
  inheritance is reachable through the replacement/property-transfer path above.
- m_ResultSetHealth runs before m_ResultInheritsHealth. Existing audit requires
  inheritance from source index 0; native inheritance overwrites the set-health
  value and our Do then applies the source's normalized health times 0.75.
  Changed inheritance index, disabled inheritance and averaged health are already
  rejected. No unsupported health-percentage flag was added.
- Input Destroy takes precedence over that input's health/quantity modifications.
  Existing audit requires source Destroy=true and tool Destroy=false. Tool's
  nonzero negative AddHealth takes precedence over its SetHealth; tool quantity
  changes are a separate active branch, now rejected. Destroyed-source modifiers
  and shadowed set-health values were not misclassified as active overrides.
- Soft-skill fields are declared but unused by these inspected native mutation
  methods; no invented soft-skill mutation path was added.

Seven new behavioral tests use the existing restricted actual-method harness,
with explicit synthetic DTO fields for the inspected native modifiers. Each
active-mutation test first verifies baseline admission, changes one field on each
of the three actual synthetic cached instances, then requires rejection. Guard
tests also exercise the already-enforced destroy/health inheritance rules and
confirm shadowed fields do not create artificial audit failures. These tests
execute authored admission policy; they do not execute native inventory mutation
or demonstrate whether transient health changes have engine-side callbacks.

Actual RED command before the source correction:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_crafting_completion.py -v
Ran 14 tests in 0.059s
FAILED (failures=21)
```

The 21 failed subtests were full quantity (three recipes), replacement (two input
indices times three), color inheritance (two indices times three), and signed
tool quantity changes (two deltas times three). No harness errors occurred.
After the source correction, the actual combined crafting command was:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_crafting*.py' -v
Ran 25 tests in 0.074s
OK
```

Scoped git diff --check passed. HCCraftingNativeChecks.c frozen SHA-256:
`cd966e7136621b86bb91e629b03e66f2227306783162c3aec8f5c355c268db0b`.
Coordinator was notified immediately after GREEN for compiler 010's enabled
Crafting native check. That check, actual inventory behavior, and all durable
atomicity/multiplayer acceptance remain pending until recorded separately.

## Independently inspected compiler 010 — enabled Crafting native PASS

Inspected on 2026-11-16 after the coordinator supplied the completed run. This
entry supersedes the earlier pending compiler/native-definition-check status
for this exact snapshot. It does not supersede inventory or client acceptance.

Repository evidence: [compiler-010-crafting-wine.json](../evidence/compiler-010-crafting-wine.json).
Private actual-run root:
`/home/david/.cache/hollow-country/wine-server-20261116/experiments/compile-010-crafting`.
The repository report and cached compiler-report.json independently hash to the
same SHA-256:
`c0b82559754f5679c382d2029420fd84d723775966bf5674a9d2f8d3c0c0e037`.
Recomputed all five log hashes in that report against the actual cached files;
every hash matched. Independently verified these principal artifacts:

| Artifact | SHA-256 |
| --- | --- |
| @HollowCountry/addons/hollowcountry.pbo | 1ba4caa424f5ebf84362196aee6a73d242c8b2d3e4e30d9a0a919207b9dae502 |
| profiles/script_2026-11-16_16-20-27.log | 7d1ace791249c529ee04d7833d1bae45159cc3516a1378a7beb35042dc47619a |
| profiles/HollowCountry/settings.json | 74ea6001c7c8ed6680d573256b9e1e8b7293ce6ca9f0dac7d3bd06f1694902b0 |

Parsed and checksum-validated the actual PBO using tools.package.pbo.parse,
without extracting or changing files. Its HCServer.c, HCCraftingNativeChecks.c,
HCCraftingRegistryAudit.c, HCCraftingModule.c and HCSalvageRecipe.c entries match
the frozen repository source byte-for-byte. In particular, the PBO includes the
CR05 native-precedence correction and partial-start cleanup source with the
frozen hashes recorded above. This ties the observed VM result to those fixes.

Read the actual script log and settings. EnableCrafting=true, all other gameplay
feature flags=false. The server script log shows World loaded at 16:20:42.285,
Mission loaded at 16:21:42.721, then the following actual native VM messages:

```text
16:21:43.476 [HollowCountry][SelfTest] Core settings PASS in native script VM
16:21:43.483 [HollowCountry] Crafting definition/config checks passed; runtime acceptance PENDING
16:21:43.483 [HollowCountry] Requested module start; inspect module admission result: Crafting
16:21:43.484 [HollowCountry] Server initialized; experimental features require explicit settings
```

Thus the actual DayZServer executable under Wine compiled/loaded this PBO and
executed the enabled Crafting startup admission checks successfully. The real
PluginRecipesManager lookup, three registered-instance definitions, required
native config/output limits and synchronous completion-guard self-check passed
in the engine's script VM. The successful startup alone does not test the new
HCServer abort/retry cleanup branches or recipe mutation rejection branches.

Limitations remain explicit. The report records client_count=0,
signature_verified=false, forced_stop=true and launcher exit -15. This was a
bounded server probe under Wine, not native Windows, DayZDiag, a client join or
graceful-stop/restart acceptance. Error/RPT logs still contain missing animation
skeleton references (including the mod path), native declaration/link warnings
and other asset/geometry/audio warnings. They were observed, not declared fixed;
server initialization succeeded despite them, so this is not a warning-free
runtime acceptance result.

No actual craft, inventory/ground output, item quantity or condition mutation,
interruption, full inventory, two-client race, disconnect, durable crash recovery,
audio/animation/visibility or load benchmark was exercised. These gameplay and
atomicity gates remain PENDING. No production setting, source or test file was
changed for this evidence update; only this experiment record was appended.
