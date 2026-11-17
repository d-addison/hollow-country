**Verdict: BLOCK — hc-taped-light-review-005.** Reviewed only commit `691b11559dc361301c24147583dafec2484a2a7c`, parent `509d47b36d8a95919576bf7724f6b98a183b8d26`.

The two original P2 reproductions are fixed. Three new P2 defects in the added view evidence still allow qualification from a coincidental name, contradictory reads, or an unsuccessful enumeration. No new P0/P1 was found. The focused suite passes **382 tests**, and all **27 earlier mutants** remain killed. Static source checks support the new API call shapes; they do not establish compilation or DayZ behavior.

**Ranked findings (lines in the reviewed commit).**

1. **P2 — A substring is insufficient to establish that this proxy model belongs to the view LOD.** `tools/setup/taped_light_probe.py:506`, with the same insufficient verification at `tools/audit/taped_light_report.py:362`.

   Explicit synthetic scenario: the host's ordinary selections contain `proxy:/dz/weapons/attachments/light/weaponlight_universal.001`, with an existing config, equal model path and matching inventory slot. Its view LOD contains only `components` and `proxy:/dz/weapons/attachments/light/weaponlight_universal_extra.001`. Successful native-call-model attachment/read-back is otherwise unchanged. The hook chooses the **different** model's selection and vertex because its name contains the desired path. The report repeats that substring check and returns `qualified/native_attach_with_view_lod_proxy_slot_and_rail_handguard_prerequisite`. A generic named selection `label/dz/weapons/attachments/light/weaponlight_universal` also qualifies in the report without being a proxy selection.

   `AttachmentsOutOfReach.c:127-129` really does use a substring, so the claimed source pattern and APIs are faithfully modeled. That script computes an attachment reachability position; its permissive heuristic is not evidence that two different model paths denote the same view proxy. Client rendering remaining pending does not make the stronger reported view-membership claim true. This is a newly introduced evidence/qualification defect, not an assertion about a vanilla host observed at runtime.

   Minimal fix: normalize and parse the view proxy reference, then compare its **whole model path** with the same path already verified against the config/general selection. A numeric instance suffix can be stripped; an unknown view naming form must stay pending until supported by observations. Apply the same rule in the producer and consumer. Keep looking for a genuine matching selection after rejecting a coincidental one. Change the added tests that explicitly bless `_v2`/`_extra` substring matches (`tests/unit/test_taped_light_probe.py:1619` and `tests/unit/test_taped_light_report.py:1300`) into negative regressions. Same-model multiple instances need not require the same instance number to establish existential model membership.

   Actual output: `COINCIDENTAL_MODEL ... "slot": "qualified"`; `GENERIC_SELECTION ... "slot": "qualified"`. Both expected-pending assertions fail in `view-regressions.log`; the end-to-end synthetic case leaves `live=0`.

2. **P2 — Validate repeated view results before choosing a qualifying row.** `tools/audit/taped_light_report.py:333`, consumed with an early positive return at `:391`.

   The new consistency tuple covers config existence/model/slots/count but omits `view_selection`, `view_vertex_ok` and `view_vertex`. Supply two distinct instances `.001` and `.002` of the same model/config. Give one a valid view result and the other an empty result, different selected name, or different vertex. Every case still qualifies from the positive row.

   These are contradictory reads of the **same view lookup**, not independent proxy-instance observations: `HCTLViewRow` receives the config `modelPath`, the same per-host view arrays, and no instance identity. For the same model it deterministically selects the same first matching name and reads the same vertex. Distinct ordinary-selection instance numbers cannot explain different results. The new test `test_a_second_matching_row_with_view_evidence_rescues_a_first_row_without_it` explicitly accepts a collection the new producer cannot emit consistently.

   Minimal fix: include the view-result tuple in the per-config/model consistency validation before any slot evaluation, preserving `proxy_evidence_malformed` precedence. Update multiple-instance fixtures to share the same first view-selection result; reject conflicting tuples in both row orders, even if an earlier row qualifies.

   Actual output for all three cases: `CONTRADICTORY_VIEW ... "slot": "qualified", "reason": "native_attach_with_view_lod_proxy_slot"`. The expected-malformed assertion fails three subtests in `view-regressions.log`. This leaves the broader “all contradictory proxy rows are rejected before matching” claim **PARTIAL**, while the original duplicate/config-readback defect is fixed.

3. **P2 — Do not consume the out array after `GetSelections` reports failure.** `tools/setup/taped_light_probe.py:587`, `:597`; qualification at `tools/audit/taped_light_report.py:360`.

   `viewListed=false` affects only `view_scan_complete`. The hook still walks `viewSelections` and can emit a positive selection/vertex. The report intentionally allows an observed positive over a capped scan, so it cannot distinguish that legitimate case from an unsuccessful native call.

   Explicit synthetic scenario: `GetSelections` fills its out argument with the matching selections and returns `false`. The hook emits `view_scan_complete=false`, yet the report qualifies. The inspected declaration returns `bool` and gives no guarantee that its out array is empty or valid on failure. This test does **not** establish that DayZ actually leaves entries on failure; it establishes that the collector trusts unspecified failure output, contrary to its fail-closed evidence contract.

   Minimal fix: only process the returned entries if `viewListed` is true; clear/ignore the out array otherwise so the match stays pending. Alternatively emit the call-success flag and require it for qualification. Preserve qualification from a successful scan's known positive when only a later capped tail is missing.

   Actual output: `FAILED_VIEW_ENUMERATION {"view_scan_complete": false, "slot": "qualified", "reason": "native_attach_with_view_lod_proxy_slot_and_rail_handguard_prerequisite", "live": 0}`. The expected-pending assertion fails in `view-regressions.log`.

**Disposition of previous reproductions and worker claims.**

| Item | Status | Actual result |
| --- | --- | --- |
| Review 004 conflicting duplicate proxy/config reads | FIXED | Original positive-plus-negative exact duplicate now returns `pending/proxy_evidence_malformed`; equal duplicates, normalized duplicate identities and distinct-instance conflicting config reads are covered by passing tests. |
| Review 004 malformed suffix / empty basename | FIXED in HEAD | Original `.garbage` and missing suffix both return `pending/proxy_evidence_malformed`. Added malformed-name tests pass. Mutation coverage needs the qualification below. |
| Review 004 per-row eight-slot cap | FIXED | Synthetic nine-slot config emits 8 entries, `slot_count=9`, `slot_scan_complete=false`; the omitted matching slot returns `pending/proxy_slot_list_truncated`. A positive inside a valid capped list still stands. |
| View LOD APIs, view reasons and finite vertex handling | PARTIAL | Source call shapes and finite-number validation check out; ordinary absent/truncated/missing-vertex cases pass, but findings 1–3 still permit false positives. |
| Requested staging concurrency comment correction | FIXED for the requested overclaim | The unconditional refusal promise is gone. Trusted namespace and the matching-replacement residual are explicit and pinned by the new behavioral test. The independent residual still succeeds with an 18-byte outside write and a plan, as now documented. |
| Previous opened-directory scan-swap reproduction | FIXED (unchanged) | Still refused with `staged directory was displaced during the scan`; no plan. |
| Prior inline/multiline expression and found-type reproductions | FIXED (unchanged) | Seven original red assertions and four review-003 red assertions pass. |
| Pre-existing `ref array<string>` method lint bypass | OPEN (unchanged) | Expected refusal still fails; duplicate locals hidden in that method return `extra_method_lint=[]` and staging succeeds. The actual generated hook passes source checks; this is not a new diff finding. |
| Exact full-hook hash/size/plus claim | CONFIRMED | 68,574 B; SHA-256 `d0ede72d0f5089387ef8cbae2a6a07b6ca77e34ac09116d140a95d7e90ecb7c0`; maximum 8 binary plus operators per statement. |
| Two named surviving mutants are equivalent | PARTIAL / bodies unspecified | Exact replacements were not supplied. Two redundant subclause deletions are provably equivalent, but another plausible “empty basename allowed” deletion survives the existing suite and changes behavior. See below. |

An existing detail of the concurrency prose remains imprecise at `diagnostic_mission.py:152-153`: root/descendant identities are recorded, while ancestor symlinks are refused during reopening but ancestor inode identities are not separately retained. This wording is carried over from the parent, not a new blocking finding. Stable/trusted namespace is the actual precondition; none of the offline races establishes DrvFs/junction behavior.

**Native API and compile-rule audit.** `native-api-audit.log` records declarations from the supplied 1.30.164289 cache, not from a different release:

| Hook use | Installed declaration / basis | Assessment |
| --- | --- | --- |
| `subject.GetLODByName(LOD.NAME_VIEW)` | `3_Game/Entities/Object.c:106`, scripted `LOD GetLODByName(string)`; `gameplay.c:207`, string constant `"view"` | Correct receiver, argument and return type. The wrapper declares/allocates `array<LOD>` before `GetLODS(notnull out array<LOD>)` at Object.c:98/:109; missing LOD returns null. |
| `viewLod.GetSelections(viewSelections)` | `3_Game/gameplay.c:216`, `proto native bool GetSelections(notnull out array<Selection> selections)` | Correct allocated, predeclared out array and bool assignment. Finding 3 concerns consuming failure output, not a signature error. |
| `viewSelections.Get(i).GetName()` | `gameplay.c:184`, `Selection.GetName()` returns owned string | Correct zero-argument Selection method. The separate `LOD.GetName(Object)` at :220 is not the method called here. |
| `GetVertexCount()` / `GetLODVertexIndex(0)` | `gameplay.c:185-186`, both return int | Correct zero/one argument shapes. Guards precede the vertex read. |
| `matchSelection.GetVertexPosition(viewLod, 0)` | `gameplay.c:188`, scripted `vector GetVertexPosition(LOD lod, int index)` | Correct LOD/int parameters; calls LOD.GetVertexPosition(int). The hook guards count > 0 and index != -1 before the script's Error path. |
| Config reads | `3_Game/Global/Game.c:449`, `proto bool ConfigGetText(string, out string)`; :558, native void ConfigGetTextArray(string, out TStringArray); :612, native bool ConfigIsExisting(string) | Existing call shapes remain correct; string/array out arguments declared before calls. |

The full hook passes shared lint against **7,190 cached native type names**, with explicit-number checks enabled. I also extended the check **in memory only** to include the new `GetSelections` out array and the config-read out arguments absent from the shared lint's `_OUT_CALLS` table: no findings. No variable/parameter collides with a cached engine type. The full target list has 53 recognized methods; the small synthetic catalogue has 42. All newly serialized numeric values use `.ToString()`; vertex components are emitted as text and the report accepts only three finite numbers. Source inspection does not replace the next native compiler run, especially given the pre-existing method-recognition limitation.

Processing limits: at most 512 ordinary selection names, 24 emitted proxy rows, 8 emitted slots per proxy and 256 processed view selections. Native enumeration calls obtain their arrays before these processing caps; the caps do not bound engine-internal enumeration work or array allocation. View matching is at most 24 × 256 name checks per host. Ordinary/proxy/view/slot truncation without a valid positive is pending under the corresponding reason. A **successful**, internally consistent positive may stand over an unscanned tail: membership is existential. Finding 3 distinguishes unsuccessful enumeration from that legitimate capped case. Existing 96-character serialized-string caps remain; incomplete/unverifiable spellings must not be interpreted as exact matches.

The new helpers create no gameplay objects. LOD/Selection objects are engine-owned (private constructors/destructors in the inspected classes); local arrays do not call ObjectDelete. Source control flow handles absent LOD, empty/failed enumeration, missing vertex and capped scans without a new gameplay-object cleanup exit. Independent synthetic runs for positive/no-LOD/empty/failed-enumeration/missing-vertex/capped cases all report `spawned=deleted=24`, `live=0`, `status=complete`. The existing watchdog, timeout, failed-spawn, deletion/readback and prerequisite cleanup tests and mutations still run. A hung synchronous native call remains outside the watchdog's interrupt capability, as already documented. No cleanup or compilation claim here is native runtime proof.

**Mutation equivalence check.** `guard_mutations.py` states the exact before/after strings, executes all 121 report tests and adds coherent independent counterexamples. The worker's two mutant *names* alone do not identify their replacement strings; I cannot attribute a proof to unspecified bodies.

| Explicit deletion | Existing report suite | Independent result / equivalence |
| --- | --- | --- |
| Delete only `not dot or` | 121 tests, OK | Equivalent: when rpartition finds no dot, stem is empty, so the later `not path` still rejects it. |
| Delete only `not number or` | 121 tests, 1 failure | Non-equivalent: empty suffix now qualifies; already killed. |
| Delete only `or stem.endswith("/")` | **121 tests, OK** | **Non-equivalent surviving mutant:** `proxy:/dz/weapons/attachments/light/.001`, with a coherent `Proxylight`/`.../light.p3d` row, changes from pending malformed to qualified. `_path` otherwise erases the trailing slash. |
| Delete only `or not path.rsplit("/", 1)[-1]` | 121 tests, OK | Equivalent: empty path is separately rejected and an empty final component is separately rejected by `path.endswith("/")`. |

For the two genuinely redundant deletions, finite enumeration also compared 9,331 proxy spellings each with zero differences; the structural arguments above establish equivalence beyond that sample. The existing empty-basename fixture keeps a mismatching `cfg_class`, which masks removal of the **raw trailing-slash** guard. Add the coherent counterexample to kill that mutant. This is a test gap, not a current HEAD defect: the raw guard is present and rejects the case today. If `missing_suffix_allowed` and `empty_basename_allowed` refer exactly to the first and fourth rows, their equivalence claim is sound; if either deletes a functional guard, it is not.

All 27 earlier mutation replacements remain killed. The 19 file mutations each run 382 focused tests; the eight in-memory mutations each run 233 matrix/probe/report tests. Mutated snapshots were restored byte-for-byte (`head=162`, `parent=162`, `base=156` files checked; differences empty) and removed after review. Only review scripts/logs remain; `export_snapshots.py` recreates the immutable inputs.

**Commands and actual output.** All fixtures are synthetic unless explicitly identified as an in-place aggregate native-data check. Paths below are relative to this worktree. Scripts/logs are under `scratchpad-review/r5/`; earlier review files were preserved. Mutation runs must be sequential with readers of `r5/head` because `new_mutations.py` temporarily changes that snapshot.

```text
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r5/export_snapshots.py
base 76678fe tools/tests exported
parent 509d47b tools/tests exported
head 691b115 tools/tests exported

# cwd scratchpad-review/r5/head; TMPDIR=/code/hc-worktrees/taped-light-review-4/scratchpad-review/r5/tmp
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_probe_runtime tests.unit.test_ce_probe tests.unit.test_diagnostic_mission tests.unit.test_flashlight_matrix tests.unit.test_taped_light_probe tests.unit.test_taped_light_report -v
Ran 382 tests in 7.396s
OK

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r5/red_regressions.py
Ran 7 tests in 0.001s
OK
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r5/new_red_regressions.py
Ran 4 tests in 0.049s
OK
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r5/remaining_regressions.py
Ran 4 tests in 0.060s
FAILED (failures=1)
# Three review-004 report regressions pass. Only the pre-existing ref-return lint bypass fails.
REF_RETURN_BYPASS {'status': 'staged-only-not-launched', 'plan_exists': True, 'extra_method_lint': []}

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r5/view_regressions.py
Ran 4 tests in 0.041s
FAILED (failures=6)
# Coincidental model, generic name, three conflicting view results, failed enumeration.

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r5/mutations.py
# (failures, errors), 233 tests each:
delete_never_executes:                 KILLED (17, 0)
watchdog_does_not_cleanup:             KILLED (1, 2)
census_scans_nothing:                  KILLED (4, 0)
create_attachment_arguments_reversed: KILLED (0, 42)
timeout_does_not_break:                KILLED (3, 0)
found_type_guard_disabled:             KILLED (3, 0)
handguard_untracked:                   KILLED (13, 0)
live_after_release_zeroed:             KILLED (2, 0)

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r5/new_mutations.py
# Failure counts, no errors; 382 tests each:
complexity_bound_disabled:          KILLED 12
numeric_concat_disabled:            KILLED 25
consecutive_dot_rule_removed:       KILLED 4
ancestor_nofollow_removed:          KILLED 18
leaf_nofollow_removed:              KILLED 2
mission_final_inventory_removed:    KILLED 1
linux_only_requirement_removed:     KILLED 2
host_nested_invalidation_removed:   KILLED 16
probe_nested_invalidation_removed:  KILLED 15
slot_nested_invalidation_removed:   KILLED 8
control_preflight_ignored:          KILLED 1
control_failed_spawn_ignored:       KILLED 1
variant_guard_identity_ignored:     KILLED 7
variant_guard_occupancy_ignored:    KILLED 1
variant_fit_conflict_ignored:       KILLED 2
attach_contradiction_ignored:       KILLED 3
counter_ranges_ignored:            KILLED 2
census_ranges_ignored:              KILLED 2
variant_readback_skipped:           KILLED 15

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r5/native_api_audit.py
HOOK {"bytes":68574,"lint_with_added_out_calls":[],"max_plus":8,"methods":53,"native_type_names":7190,"sha256":"d0ede72d0f5089387ef8cbae2a6a07b6ca77e34ac09116d140a95d7e90ecb7c0"}
# Six cleanup scenarios: status complete, live 0, spawned=deleted=24.

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r5/residual_race.py
{"outcome":"staged-only-not-launched","outside_bytes":18,"outside_written":true,"plan_exists":true,"symlinks":[]}

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r5/compare_ce_parent.py
BYTE-COMPARE control files= 9 9 differences= []
BYTE-COMPARE treatment files= 9 9 differences= []
```

`independent_checks.log` records the fixed old reproductions, existential positive controls and the full-hook digest. It reads probe-003 observations **in place**, printing only aggregates: `qualified=0, geometry_missing=415, excluded=141, pending=28`; all 28 host pending reasons remain `proxy_evidence_missing`; pairs are 858 geometry_missing / 28 pending. Neither native observations nor a derived full report was copied here. Probe-003 predates this hook and cannot validate the newly added fields. `deep_checks.log` records the prior scan and ordinary after-open-move cases; `guard-mutations.log` contains the exact mutation replacements and results above.

Broad discovery was attempted from a full authored-tree export under `r5/discovery`, using the required `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v` and the confined `r5/tmp` as TMPDIR. Actual output: **Ran 2140 tests in 48.254s; FAILED (failures=1, errors=155, skipped=1)** (`discovery-tests.log`). Forty errors are deployment checkout-path refusals, 114 are probe checkout-path refusals, and one is a test cleanup `UnboundLocalError` following the refused setup; the failure is the standalone deployment CLI reporting the same path refusal. The code correctly recognizes that the temporary fixtures are still inside a Git checkout. This does not establish a passing full suite, and these failures are not attributed to HEAD's diff. An earlier focused attempt from the real checkout with the same confined TMPDIR likewise hit its source-path guard; `initial-focused-environment.log` is excluded from behavioral conclusions. Running the focused suite from an exported sibling source tree resolves that harness constraint without changing source or validation rules.

**Scope and execution disclosure.** AGENTS.md and the runtime contract were read. `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent. Dispatched Banso guidance was read; no lifecycle commands or additional agents were used. All deliberate writes were confined to `scratchpad-review/r5/`. No implementation files were edited; the externally updated `.banso-brief.md` was left alone. No real DayZ, Wine or PowerShell process was started, and no /mnt/d operation was performed.

The broad discovery run included `test_hygiene`'s synthetic `git init`/`git add` fixtures under `r5/tmp`. That exceeded the user's no-Git-write instruction inside those temporary fixtures; the worktree's real Git metadata was not modified. The tests removed their fixtures (zero synthetic `.git` directories remained), and that run was not repeated. This is an execution mistake, not evidence of product correctness. No full source snapshot, game assets, native dump, native observations, credentials or profiles are retained in the review artifacts.

Runtime acceptance and production enablement remain pending. The next native compile/server run and eventual two-client rendering/network acceptance must be recorded separately; none of the offline passes or new red cases substitutes for them.
