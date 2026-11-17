**Verdict: MERGE-WITH-FIXES — cross-model review 008, commit `182db381f88becdca6c33ba589bca09309041a96`, parent `73241f64751c754c6184749adb5e3cd3f8bdb487`.** The two principal r7 follow-ups are fixed. The focused suite passes **436 tests**, but probe-006 contains **199 new `scanLod` null-instance VM exceptions**, and two successfully attached hosts are called `geometry_missing` despite unavailable resolution selections. Fix those observation/report problems before relying on this probe as the firearm geometry evidence source. No host is currently qualified; runtime acceptance remains pending.

Reviewed `git show 182db38` (retained in [git-show.txt](git-show.txt)), all five changed files, r7's review and reproduction/mutation scripts, the installed native declarations and callers, and the allowed native archives. This is a single-reviewer assessment, not a voting panel. No production source was changed.

**Ranked findings.**

1. **P2 — Check the LOD instance before calling its method.** `tools/setup/taped_light_probe.py:636` (`HCTLResolutionScan`, instance obtained at :627).

   Failure scenario: the server enumerates a numeric LOD name, but the script instance is unavailable. The hook unconditionally invokes `scanLod.GetSelections`. Probe-006's script log contains **199** instances of:

   ```text
   Reason: NULL pointer to instance. Variable 'scanLod' during call 'LOD.GetSelections'
   Class: 'HCDisposableDiagnosticMission'
   Function: 'HCTLResolutionScan'
   ...init.c:1092 Function HCTLResolutionScan
   ...init.c:1327 Function HCTLProxyFacts
   ```

   Zero `Can't compile` messages and a completion sentinel do not make these successful native calls. In particular, the emitted `list_ok=false` must not be described as proof that a valid LOD method returned false. The archive establishes an unavailable/error path; its engine cause remains unproved.

   Minimal fix: initialize `selectionsListed=false` for each LOD, invoke `GetSelections` only when `scanLod` is valid, preserve the empty/unknown bookkeeping for unavailable instances, and distinguish unavailable instance from a genuine false return in diagnostics. Do not substitute another LOD or turn unknown into success. The installed callers also check their LOD instance before use. An explicit synthetic unavailable-instance regression currently errors; the in-memory two-line guard makes that test pass. This does not prove the corrected native run; that experiment is still required.

2. **P2 — Unavailable resolution evidence becomes a geometry negative when no candidate proxy reaches the join.** `tools/audit/taped_light_report.py:677`, reached through :659–676; negative verdict at :692.

   Failure scenario: **R12** has two numeric LODs named `1`, both `list_ok=false`. Its only generic proxy row is an ACOG optic. **Mich2001Helmet** has one numeric LOD named `1`, `list_ok=false`, and no generic proxy rows. Both accept UniversalLight and read it back successfully. Nevertheless `_model_evidence` returns `none` without consulting the failed resolution scan, and both receive `geometry_missing/attached_without_model_selection`. See [native-negative-cases.log](native-negative-cases.log).

   These observations establish no positive geometry evidence; they do not establish absence in the unreadable resolution LODs. The report correctly keeps false unknown for a *matching candidate* at :576–577, but not for these two cases. This distinction answers the question about false: the protection is **PARTIAL**, not universal.

   Minimal fix: before returning `none`, propagate unavailable/incomplete model inspection as pending when no independent positive model evidence exists. Use an explicit `client_required` capability/reason for the affected firearm geometry axis. Keep the no-native-slot denominator based on its actual slot observation. A review-only in-memory guard moves exactly these two hosts from geometry_missing to pending: **qualified=0, geometry_missing=415, excluded=141, pending=28**. The two new negative-case subtests fail on the reviewed source and pass with that guard. Do not label the original 417 as 417 observed geometry failures.

3. **P2, inherited — The legacy route accepts positive flags without the selection name they supposedly measured.** `tools/audit/taped_light_report.py:223` and :651.

   Failure scenario: supply a complete, otherwise coherent synthetic observation with successful native attach/readback, `selection=""`, and either `selection_on_model=true`, `memory_point=true`, or `bone_index=0`. All three independently produce `qualified/native_attach_with_model_selection`, with no proxy evidence. `_host_slots` drops the selection name entirely. The current producer at `tools/setup/taped_light_probe.py:1031` queries those flags only under `selectionKnown && selection != ""`, so these are contradictory observations that it could not legitimately emit.

   Minimal fix: type-check and retain the queried selection name, refuse a positive legacy claim without a nonempty name, and check its agreement with the observed slot-to-selection mapping where available. Preserve genuinely unknown mappings as pending. Do not fabricate a name from the slot label. The independent regression fails in all three subtests; the proposed name-validation guard passes them. This predates r7 and is **not** evidence that probe-006 fabricated a positive result: all **1,329** native host/slot rows have `(selection_on_model=false, memory_point=false, bone_index=-1)`.

4. **P3 — Important geometry guards survive mutation because the fixtures do not distinguish their inputs.** `tests/unit/test_taped_light_report.py:1407` and `tests/unit/test_taped_light_probe.py:877`; protected code at report :380/:446/:545/:548 and probe :755.

   Failure scenarios and minimal tests: use `1e999` to exercise finite-number rejection after valid numeric parsing; `"1\n"` to exercise whole-string parsing; an incomplete diagnostic name list plus resolution name `1junk`; a row/host `list_ok` disagreement on one LOD while another LOD qualifies; and decouple positive vertex count from index `-1` (and zero count from a valid index). The six nonredundant mutants below survive **all 436 tests**, yet those explicit counterexamples change pending/malformed evidence to qualification or invoke the erroring vertex read. The production guards are present; this finding is about regression strength. Add these cases, retaining the existing guards.

5. **P3, inherited — The report projects the base attach fields even when it evaluated the prerequisite variant.** `tools/audit/taped_light_report.py:781`.

   Failure scenario: AK74 and M4A1 report `requires_prerequisite=true, can_add=false, attach_ok=false`, although their variants successfully created/read back the rail handguard **and UniversalLight**. A synthetic legacy-positive variant even returns `qualified` with those false base fields. The denominator uses the variant correctly; the evidence projection obscures its provenance. Minimal fix: retain explicitly named base and variant attempts, handguard readback, and the attempt selected for evaluation. Do not overwrite or relabel the raw base facts.

**Server-side evidence route and recommendation for question 2.** No usable firearm proxy-position route has been demonstrated on this dedicated-server snapshot. Do **not** conclude that the API is universally impossible on every dedicated server or model. The same run has 240 hosts with at least one listable numeric LOD, and UMP45 lists ten selections; however, UMP45's matching proxy lacks a usable first vertex. Every other firearm slot host, including R12, has unavailable selection lists. The widespread null-instance exceptions further limit what can be inferred about actual `GetSelections` return values.

Installed source evidence, paths relative to `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`:

| Source | What it establishes |
| --- | --- |
| `3_Game/Entities/Object.c:98`, :101, :106–122 | `GetLODS(out array<LOD>) -> bool`, `GetLODName(LOD)`, and the script `GetLODByName` wrapper. The wrapper enumerates names and returns a matching entry. This is not a promise that numeric firearm LOD instances support server-side selection enumeration. |
| `3_Game/gameplay.c:184–218` | Selection name/count/index, guarded `GetVertexPosition`, and `LOD.GetSelections(out array<Selection>) -> bool`. `Selection.GetVertexPosition` calls `Error("Vertex doesn't exist")` for index `-1`. |
| `4_World/Classes/UserActionsComponent/Actions/Interact/ActionEnterLadder.c:30–37` | Looks up a **building memory LOD**, checks for null, and at :36 returns false when `GetSelections` fails. This supports checking the return and receiver. It does not establish firearm resolution-LOD availability or a dedicated-server firearm route. |
| `4_World/Systems/Inventory/AttachmentsOutOfReach.c:112–122` | Checks a named `view` LOD and reads its selections for attachment reachability. Every external `IsAttachmentReachable` caller in this snapshot is under `5_Mission/GUI/InventoryNew` (`Attachments.c:173/:388`, `ContainedItems/Icon.c:874`, `Inventory.c:1446`, `Inherited/AttachmentCategoriesRow.c:727`). This client inventory path is not server geometry proof. |
| `5_Mission/GUI/ActionTargetsCursor.c:481–485` | A client GUI cursor reads a **memory LOD**, after checking its receiver. This is also not a server firearm resolution-LOD example. |
| `3_Game/gameplay.c:222–225` | `GetSelectionByName` simply wraps `GetSelections`; it does not supply an independent successful server route. |
| `4_World/Entities/ItemBase/Switchable_Base/UniversalLight.c:49–54` | Creates/attaches the beam light only on the client/non-multiplayer branch, using `beamStart`/`beamEnd` on the light. Server memory-point facts alone do not prove visible beam placement. |

The snapshot search finds no other scripted `GetLODS` consumer beyond the wrapper, and no successful dedicated-server firearm resolution-selection example. Probe-005 established lack of a LOD named `view`; switching to numeric names in r7 was a testable hypothesis, not established success. Probe-006 has now failed to provide qualifying firearm geometry.

**Explicit recommendation: classify firearm model-proxy/placement evidence as `client_required`, with verdict `pending`, until a client supplies the missing model evidence.** Keep server observation of slot ownership, light fit, native refusal/creation/readback, and verified prerequisites. Retain successful server model measurements as diagnostic evidence where actually available; do not infer their availability on the firearm classes from a Python fixture or another model. UMP45 also remains pending because its required vertex is missing. An optional follow-up server experiment may test guarded receiver availability, but it must not be a prerequisite for source authoring or be marked accepted before it runs.

The minimal honest rule is:

1. Structural/native attach evidence requires an actually observed host slot, compatible light preflight, successful native check/create, exact slot readback, and any required handguard occupant/property readback, from the **same evaluated base or prerequisite variant**.
2. A proxy-geometry-qualified result additionally requires the real proxy config identity/model/slot join, successfully inspected actual LOD membership with a whole-path match, and the finite vertex named by the rule. If the server cannot obtain that evidence, leave geometry pending/client_required. A slot label, config declaration, generic proxy name, successful attach, or an unavailable selection list cannot supply it.
3. If retaining the existing *separate* named-selection/memory/bone server-evidence route, name that weaker evidence explicitly and validate the selection identity. It is not proxy geometry or visual placement. Do not use that route to satisfy a rule requiring a proxy vertex, or to bypass the new firearm client requirement. Keeping a separately named server-attach result is preferable to overloading geometry `qualified`.

There is no recommendation to grant qualified merely because something is `client_required`. Beam, switch, removal by hand, tape consumption, persistence and two-client presentation remain pending; production enablement requires the repository's native acceptance checks.

**Duplicate-named LODs.** Correct in the reviewed producer and join. `HCTLResolutionScan` retains each engine LOD instance in order, including repeated names. `_proxy_row` zips row entries against host entries, `_lods_agree` compares ordered numeric-name lists, and `_resolution_check` evaluates each entry. There is no map keyed by name and no accidental deduplication. An independent two-entry `0,0` fixture with first unavailable and second positive qualifies; swapping their row facts is malformed. This does not establish native availability. For audit clarity, consider emitting the LOD ordinal with the qualifying name, since `resolution_lod="0"` alone cannot distinguish two entries; the current join itself remains positional.

**Legacy route: true, but limited.** The worker's statement is literally true. `_model_evidence` returns `selection` before checking missing proxy/LOD evidence, and `_accepted` grants `native_attach_with_model_selection`; the prerequisite reason is `native_attach_with_rail_handguard_prerequisite`. Independent generated-hook execution with the synthetic selection-bearing catalogue, no proxy config and no proxy rows returns qualified, with an empty resolution selection list and no live objects. Each of the three legacy flags independently qualifies in the report-only fixture.

That route is an explicitly documented older alternative, not a new r7 shortcut. A real nonempty slot-associated selection/memory point/bone can support the limited claim that it exists on the loaded server object. It does **not** prove the resolution proxy/config/vertex chain, transform, orientation or beam placement. Thus it is a bypass **of any uniform proxy-geometry qualification rule**, and must not rescue firearm client-required geometry. Finding 3 identifies a concrete additional validation bypass even under its own narrower rule. Native probe-006 has no positive legacy flags to use.

**Prerequisite chain and denominator.** The probe already tests it; no missing-handguard implementation should be alleged. `HCTLPrereqVariant` at probe :1225–1267 creates a fresh host, uses `CreateAttachmentEx(handguardName, slotId)` (:1247), verifies the actual `FindAttachment(slotId)` occupant/type and `hasRailFunctionality`, then calls `HCTLHostLightRows` (:1261). The native prerequisite itself is `UniversalLight.CanPutAsAttachment`, native file :25–45; the checked slots are initialized at :123–132. The selected AK/M4/MP5 rail types are also used in native firearm debug spawning.

Probe-006 records **12 performed variants**, all with the correct occupied rail-functional handguard: **8 AK_RailHndgrd, 3 M4_RISHndgrd, 1 MP5_RailHndgrd**. All 12 then report weaponFlashlight `can_add=true, attach_ok=true, found_type="UniversalLight"`. AK74 and M4A1 are concrete examples. Conversely, the base `false,false` observations are expected while their rail is absent. Guns without one of those handguard slots need no fabricated prerequisite; a UniversalLight attempt on a pistol's incompatible slot is not a compatible-light trial.

`_evaluate_slot` (:724–738) uses the verified variant and only then sets `requires_prerequisite=true`; it does not count these twelve as a final bare-host refusal. The host denominator remains one host, not twelve extra hosts, and the geometry join leaves them pending. The requested minimal native probe change for the prerequisite chain is therefore **none**: that native-API sequence is already implemented and observed. Keep it; fix the receiver guard and report provenance. The native `attach_ok` counter is 28, while host-qualified is zero; those measure different things.

**Every carried r7 finding/protection.** Outputs are retained in [prior-checks.log](prior-checks.log), [reproductions.log](reproductions.log), and the named individual logs.

| r7 finding/protection | Status | Actual reproduction output |
| --- | --- | --- |
| Coherent FNX leading-slash aliases unnecessarily invalidate the collection (r7 P3a) | **FIXED** | Probe-006: `_proxies` parses **443 ok / 0 malformed** hosts; FNX45 and FNX45_arrow each collapse one alias and reach pending/resolution_enumeration_failed. Conflicting config/resolution readbacks in both orders remain malformed. |
| Combined normalized empty-basename guard mutant survives (r7 P3b) | **FIXED** | Combined deletion: **143 tests, failures=1, errors=0, KILLED**. Coherent `.p3d.001` counterexample is pending/malformed normally, qualified only under the mutant. Either single guard deletion still passes: the companion guard is equivalent protection. |
| Backslashes normalized before basename extraction | **FIXED** | Generated-hook backslash case: `cfg="Proxyweaponlight_universal"`, successful proxy join in the explicit positive synthetic resolution fixture, `live=0`; native rows show the correct config class. |
| Ref-returning methods hiding duplicate locals | **FIXED** | Unchanged carried staging regression: `Ran 4 tests ... OK`; injected duplicate-local method is rejected. |
| Whole-path identity, not substring coincidence | **FIXED** | Generated longer-model case: pending/resolution_proxy_missing, live=0; report rejects generic/other-path claims. New path-check mutant is killed by 13 report failures. |
| Conflicting view lookup tuples (now resolution tuples) | **FIXED** | Eight independent ordered selection/missing/vertex/flag conflicts all return pending/proxy_evidence_malformed, qualified=0. |
| Failed GetSelections leaves populated output | **PARTIAL** | Matching candidate: list_ok=false, selection_count=0, incomplete, pending/resolution_enumeration_failed, live=0. The new clear-removal mutant is killed. Null receiver and unmatched/no-proxy negative cases remain findings 1–2. |
| Other repeated-separator normalization differences | **OPEN** | One-sided repeated separator: pending/resolution_proxy_missing. Same repeated separator in both model and resolution path: qualified only in the explicit synthetic positive fixture; live=0. This is the carried producer/report normalization difference, not a native placement result. |
| Formatting-independent lint beyond actual generator layout | **PARTIAL** | One-line method: methods=0/issues=[]; same-line second method: methods=1/issues=[]; inline-control numeric compound concatenation: methods=1/issues=[]. Actual generated hook is recognized/audited cleanly. |
| Staging displacement protections / matching replacement race | **PARTIAL** | Final-walk displacement regression passes refusal. Carried matching replacement still returns `staged-only-not-launched`, `outside_written=true`, `outside_bytes=18`, `plan_exists=true`, all inside the explicit scratch synthetic fixture. No engine launched. |
| Native geometry/client acceptance uncertainty | **OPEN** | All actual qualifications remain zero. View-LOD absence was replaced by resolution probing, which did not establish firearm geometry; no client acceptance evidence exists. |

The carried seven-test red-regression suite, four-test new-red suite and four-test remaining suite all pass. I have not represented the older 27-mutant campaign as rerun: this review mutates the new/changed protections listed below.

**Compile shape.** The generated hook matches the archived plan's **87,154 B** and SHA-256 **`3b838473f5d27f34fe007fba94186f6c1bbd0522ba4d64ecd45394a402c50e88`**. The archive has a manifest, not the original staged init.c, so this independently verifies generated bytes against the recorded fingerprint, not a fresh readback of that init.c.

```text
AUDIT {"bytes":87154,"independent_max_plus":8,"lint_including_out_calls":[],
 "methods":63,"native_types":7190,
 "sha256":"3b838473f5d27f34fe007fba94186f6c1bbd0522ba4d64ecd45394a402c50e88",
 "shared_max_plus":8,"ternary_tokens":0}
EXTERNAL_API_COUNT 70 MISSING []
OVERRIDES [('OnInit', '')]
FULL_LINT []
LEADING_LOGICAL_OPERATORS 0
```

The independent lexer removes comments/strings and splits statements on `;{}`; line breaks/indentation do not reset the `+` count, and increments/compound assignment are excluded. The maximum is **8**, not a count per printed line. Actual serialization uses explicit `.ToString()` for counts/indices/components and `HCTLBool` for boolean text. There are no detected duplicate locals/parameters, identifiers colliding with 7,190 installed engine types, leading logical continuation operators, ternaries, or undeclared/late out arguments in this hook. The out audit includes `GetSelections`, `GetLODS`, config reads, slot selection/bone lookups, and world/version outputs. `lodSelections` is allocated at probe :607 before :636. The only override is `OnInit()` with no parameters, matching the native mission prototype (`5_Mission/mission/missionServer.c:85`). The added GetSelections out-argument lint regression kills its removal mutant. General parser limitations remain as carried above.

The archived completed run is real compile/execution evidence, with the explicit VM-error limits already described. It does not make the synthetic positive vertex branch a successful native firearm experiment.

**Mutation results.** Exact replacements, argv, exits and summaries are in [mutations.py](mutations.py), [mutations.json](mutations.json), [mutations.log](mutations.log) and `mutation-logs/`. **29 mutations: 21 killed, 8 survived.** Report mutations initially ran 143 report tests; generator/shared-lint mutations ran all 436 focused tests. Every report survivor was then rerun against all 436 focused tests and still survived ([survivors.log](survivors.log)). Counterexamples are in [counterexamples.log](counterexamples.log).

| Surviving mutation | All-focused result | Independent assessment |
| --- | --- | --- |
| Remove row/host `list_ok` agreement | 436, OK | Nonredundant: a disagreement in an empty row while another LOD qualifies changes baseline malformed to qualified. |
| Remove `math.isfinite` | 436, OK | Nonredundant: numeric text `1e999` becomes Infinity and changes pending/invalid to qualified. Existing nan/inf spelling tests are rejected by the numeric grammar first. |
| Vertex `fullmatch` → `match` | 436, OK | Nonredundant: `"1\n"` changes pending/invalid to qualified. |
| Remove `known != reading`, retain global config-lookup agreement | 436, OK | Redundant under the other checks: a canonical identity implies the same validated config class; the retained lookup tuple includes every differing field of `reading`. No safety counterexample found or claimed. |
| Skip coherent-alias internal collapse (`if True`) | 436, OK | Internal representation gap: parsed evidence rows change 1→2. Diagnostics still count one collapse; verdicts are unchanged because both rows agree and matching is existential. This is not a false-qualification witness. |
| Numeric LOD validator `fullmatch` → `match` | 436, OK | Nonredundant: `1junk` plus an incomplete diagnostic name list changes malformed to qualified. |
| Remove vertex-index `!= -1` guard | 436, OK | Nonredundant: positive count with index -1 changes pending to `AssertionError: Error(Vertex doesn't exist)` in the synthetic native-shaped wrapper. |
| Remove vertex-count `> 0` guard | 436, OK | Nonredundant: zero count with a valid index changes pending/vertex_missing to qualified in the explicit synthetic fixture. APIs expose these as distinct observations; the fixture had correlated them. |

Killed changes cover LOD order/count, positive selection after a failed/empty list, scan completeness, whole-path identity, vertex flag/parsing, LOD cross-checks, conflicting aliases/config results, alias diagnostic count, inspecting only the first LOD, the combined empty-basename guards, unknown→negative reason, clearing failed outputs, the 16/512/128 bounds, accepting nonnumeric LODs, numeric-name endpoint guards and out-argument lint. None of these offline results establishes native DayZ behavior.

**Native archive verification and exact outputs.** [native-evidence.log](native-evidence.log) retains the command and aggregates. The regenerated report matches the saved `report-182db38.json` for every non-provenance field, including all host results. The CLI's fresh provenance paths necessarily differ.

```text
plan: variant=probe port=2302 clients=0
world=chernarusplus version=1.30.164289.70
capture outcome=sentinel-seen status=observed-not-accepted server_exited=true exit_code=-1
status=complete observed=443 spawned=1839 deleted=1839
Can't compile count=0
cleanup_clean=true issues=[] unexpected_rows=[]
live_after_release=0 residual_probe_types=0 timeouts=0 residual_other=1
report: qualified=0 geometry_missing=417 excluded=141 pending=26 hosts=584
reasons: no_native_light_slot=415 resolution_enumeration_failed=25
 resolution_vertex_missing=1 no_compatible_native_slot=2
 attached_without_model_selection=2 classification_excluded=141
RES_LOD_TUPLES:
 ('1',true,true)=193 ('1',false,false)=144
 ('0',false,false)=119 ('0',true,true)=46 ('2',true,true)=1
HOSTS_WITH_LISTABLE_RES=240
PROXY_PARSE_KINDS={'ok':443}
LEGACY_SLOT_FLAGS={(false,false,-1):1329}
```

The tuples are `(name,list_ok,has selections)`. All host Object.GetLODS lists succeeded; repeated names were retained. The script's 199 scanLod exceptions are additional to these persisted output facts, not contradicted by them. Other archived vanilla errors include unused weapon FSM validation and one EffectSound cleanup null pointer; they are not attributed to the new resolution code. Exit -1 after the sentinel is recorded, not silently relabeled as a clean process exit or used to erase the completed observations.

**Commands run and actual verification outputs.** All Python executions used `-B`/`PYTHONDONTWRITEBYTECODE=1`; test/staging temporaries used `TMPDIR=/code/hc-worktrees/taped-r7/scratchpad-review/r8/tmp`. Reusable commands below run from this worktree unless a cwd is specified. Full output is in the linked logs; `git-show.txt` preserves the requested complete diff.

```text
cat AGENTS.md docs/SPECIFICATION.md docs/specs/001-survival-overhaul/spec.md docs/RUNTIME_IMPLEMENTATION_CONTRACT.md
# AGENTS and runtime contract read.
# cat: docs/SPECIFICATION.md: No such file or directory
# cat: docs/specs/001-survival-overhaul/spec.md: No such file or directory
git ls-tree -r --name-only 182db38 docs/SPECIFICATION.md docs/specs/001-survival-overhaul/spec.md
# no entries; also absent in the prior review worktree. Spec/plan validation is limited accordingly.
git show 182db38
# five files; 1252 insertions(+), 604 deletions(-); complete output: git-show.txt
git rev-parse HEAD 182db38^
182db381f88becdca6c33ba589bca09309041a96
73241f64751c754c6184749adb5e3cd3f8bdb487

PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/bootstrap.py
# head 182db38 tools/tests exported
# parent 73241f6 tools/tests exported
# Runs from r8/head:
python3 -B -m unittest tests.unit.test_probe_runtime tests.unit.test_ce_probe tests.unit.test_diagnostic_mission tests.unit.test_flashlight_matrix tests.unit.test_taped_light_probe tests.unit.test_taped_light_report -v
Ran 436 tests in 12.360s
OK

PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/native_evidence.py
# Actual inner command, cwd=r8/head:
python3 -B -m tools.audit.taped_light_report --classification /home/david/.cache/hollow-country/experiments/taped-light-probe-003/classification.json --observations /home/david/.cache/hollow-country/experiments/taped-light-probe-006/observations.json --out /code/hc-worktrees/taped-r7/scratchpad-review/r8/native-report.json
report: qualified=0 geometry_missing=417 excluded=141 pending=26 hosts=584 -> /code/hc-worktrees/taped-r7/scratchpad-review/r8/native-report.json
# exit 0; aggregate/identity/error outputs above; derived full report removed after comparison.

PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/run_prior.py
red_regressions: Ran 7 tests in 0.001s; OK
new_red_regressions: Ran 4 tests in 0.066s; OK
remaining_regressions: Ran 4 tests in 0.090s; OK
residual_race: {"outcome":"staged-only-not-launched","outside_bytes":18,"outside_written":true,"plan_exists":true,"symlinks":[]}
compile_audit: bytes=87154 methods=63 independent_max_plus=8 lint=[]
native_checks: taped methods=52/max_plus=8/lint=[]; CE methods=20/max_plus=9/lint=[]
all_api_audit: EXTERNAL_API_COUNT 70 MISSING []
extended_guard_mutations: 143 tests each; single deletions 0 failures; combined deletion 1 failure

PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/reproductions.py
# exit 0; eight ordered conflicts, six generated-hook cases, three independent legacy routes,
# empty-name counterexamples, current-hook legacy example, duplicate-name LODs and inherited lint limits.
PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/reproductions.py --null-red
Ran 1 test in 0.019s
FAILED (errors=1)
# RuntimeError: SYNTHETIC null/unavailable LOD instance was dereferenced
PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/reproductions.py --null-fixed
Ran 1 test in 0.032s
OK
# Proposed guard injected into generated text in memory only; no engine result claimed.
PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/reproductions.py --unknown-red
Ran 1 test in 0.001s
FAILED (failures=2)
# AssertionError: 'pending' != 'geometry_missing'
PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/reproductions.py --legacy-red
Ran 1 test in 0.001s
FAILED (failures=3)
# AssertionError: 'qualified' == 'qualified'
PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/proposed_report_guards.py
Ran 2 tests in 0.001s
OK
# Review-only in-memory guards: qualified=0 geometry_missing=415 excluded=141 pending=28.

PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/mutations.py
# 29 exact mutants; 21 KILLED / 8 SURVIVED; counts/exits in mutations.json and mutations.log.
PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/survivors.py
# Six report survivors rerun: 436 tests each, all OK; other two already survived 436 tests.
PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/counterexamples.py
# exit 0; four independent report counterexamples and two hook counterexamples quoted above.
PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/final_checks.py
SNAPSHOT head 182db38 files 166 differences []
SNAPSHOT parent 73241f6 files 166 differences []
OVERRIDES [('OnInit', '')]
FULL_LINT []
LEADING_LOGICAL_OPERATORS 0
HOOK_IDENTITY 87154 3b838473f5d27f34fe007fba94186f6c1bbd0522ba4d64ecd45394a402c50e88
TRACKED_DIFF ''
PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r8/cleanup.py
Removed head, parent and tmp under scratchpad-review/r8; scripts, reports and logs retained.
git diff --no-ext-diff --stat
# no output: no tracked repository change
```

Read-only source inspection also used `rg`, `sed`, `nl`, `cat`, `git diff --no-ext-diff`, and `git archive` for authored tools/tests. The required broad unittest discovery was deliberately not run: `tests/unit/test_hygiene.py:20/:76/:85` invokes Git init/add in fixtures, conflicting with this review's explicit no-Git-write scope. The six focused modules cover this change and shared staging consumers. Initial scratch harness mistakes (a synthetic object's attribute name, and one shell quoting error) were corrected before recording the cited results; neither was a product failure.

Every authored/exported/mutated file was confined to `scratchpad-review/r8/`. No Banso lifecycle/panel command, sub-agent, DayZ, Wine, PowerShell, Git mutator, write under `/mnt/d`, external publishing, asset dump, key operation, or commit-message file outside the permitted directory was used. Temporary authored exports and synthetic staging trees are removed after final integrity verification; `bootstrap.py` recreates them. This review supplies findings and concrete review-only regressions, not production fixes or accepted engine experiments.
