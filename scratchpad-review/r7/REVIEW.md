**Verdict: MERGE — hc-taped-light-review-007.** Reviewed `c1ffaea99e8ddfc9c3964eb5dd1dc012f419c01f` against `0c9f4ece1cee373ec2b5f13e4d64c5a9a44616fc` with `git show c1ffaea` (complete output in `git-show.txt`). Both principal review-006 findings are **FIXED**. I found no new P0–P2 issue or new proxy-route false qualification. The focused suite passes **418 tests**; all **27 earlier non-equivalent safety mutants** remain killed.

Probe-005 completed and contains this commit's exact **80,397-byte** hook, SHA-256 **`9ae4cbce031509cc09090c713f39a5211136e97415808d31ebb545db73142e51`**. The basename correction works natively: **573/614** proxy config lookups now succeed. All **443** observed hosts list their LODs successfully and completely, and none has a LOD named `view`. The derived report is **qualified=0, geometry_missing=417, excluded=141, pending=26**, with 24 hosts pending on `view_lod_absent_on_server` and two on `proxy_evidence_malformed`. Runtime acceptance and production enablement remain pending.

**Ranked findings and follow-ups.** No new P0–P2 finding requires a change before merging this commit. These inherited, nonblocking limitations remain:

1. **P3 — Coherent leading-slash aliases unnecessarily invalidate FNX45's entire proxy collection.** `tools/audit/taped_light_report.py:426`; producer uniqueness is still raw-string uniqueness at `tools/setup/taped_light_probe.py:759`. This is an existing rule, not a regression introduced here.

   Native failure scenario: FNX45 and FNX45_arrow each contain both `proxy:dz/weapons/attachments/optics/optic_fnp45_mrds.001` and `proxy:/dz/weapons/attachments/optics/optic_fnp45_mrds.001`. `_proxy_name` **already normalizes the leading slash**, so both produce `(dz/weapons/attachments/optics/optic_fnp45_mrds, 001)` and the duplicate-identity rule rejects the host. Their config/model/slot/view readbacks agree; the raw backslash counts differ, as expected (4 versus 5). An unrelated optic alias therefore hides the light's actual pending reason.

   My recommendation: retain canonical path normalization and allow only coherent aliases to collapse to one evidence identity, while preserving raw rows/counts for diagnostics and continuing to reject conflicting readbacks. Do not merely stop stripping the leading slash: that weakens identity comparison. A small report-side alias-collapse change can retain the raw enumeration completeness calculation. Add native-shaped synthetic agreeing/conflicting alias regressions. Removing only the redundant coherent alias **in memory** changes both hosts to `pending/view_lod_absent_on_server`, never qualified (`qualification-checks.log`). This is useful diagnostic cleanup, not evidence that FNX45 renders a light.

2. **P3 — The combined normalized-basename guard mutant still survives the report suite.** `tests/unit/test_taped_light_report.py:1433` (current round-six coverage); protected implementation at `tools/audit/taped_light_report.py:314`. This review-006 coverage limitation is **OPEN**.

   Failure scenario: delete **both** `or not path.rsplit("/", 1)[-1]` and `or path.endswith("/")`. All **138 report tests pass**, but the coherent synthetic selection `proxy:/dz/weapons/attachments/light/.p3d.001`, class `Proxy`, model `/dz/weapons/attachments/light/.p3d` and corresponding view row changes from `pending/proxy_evidence_malformed` to `qualified/native_attach_with_view_lod_proxy_slot`. The guard remains present in the reviewed source, so this is a test gap, not an extant false verdict. Minimal fix: add that coherent post-`.p3d` empty-basename regression. Either single deletion alone is equivalent while the other clause remains. Exact replacements and outputs: `extended_guard_mutations.py` / `.log`.

**Review-006 closures and reproduction output.** The scratch copies of the old scripts import the reviewed authored export. The basename regression's expected absence reason was updated to the newly specified `view_lod_absent_on_server`; its config identity assertions were unchanged. Parent runs retain their actual failures.

| Finding or earlier protection | Status | Actual result |
| --- | --- | --- |
| Normalize raw backslashes before basename extraction | **FIXED** | Parent: `cfg_class="Proxy/dz/weapons/attachments/light/weaponlight_universal", cfg_exists=false`, `FAILED (failures=1)`. Current: `cfg_class="Proxyweaponlight_universal", cfg_exists=true, verdict=pending, reason=view_lod_absent_on_server, live=0`; `Ran 1 test ... OK`. Native probe-005 independently confirms the fixed class and model. |
| `ref`-returning method hides duplicate locals from staging lint | **FIXED** | Parent: `REF_RETURN_BYPASS {'status':'staged-only-not-launched','plan_exists':True,'extra_method_lint':[]}`, `ValueError not raised`, `FAILED (failures=1)`. Current unchanged four-test reproduction: `Ran 4 tests ... OK`; staging raises as required. New product regression also exercises `ref`, `autoptr`, `protected ref`, `static ref`, duplicate locals and long expressions. |
| Whole-path view identity rather than substring coincidence | **FIXED** | `COINCIDENTAL_MODEL {"view":"","slot":"pending","reason":"view_selection_missing","live":0}`; generic selection yields `pending/view_selection_mismatch`. |
| Conflicting view lookup tuples | **FIXED** | Missing selection, selection mismatch, vertex mismatch and vertex-flag mismatch each produce `pending/proxy_evidence_malformed`, `qualified=0`, in both row orders. |
| Failed GetSelections leaves populated output | **FIXED** | `FAILED_VIEW_ENUMERATION {"view_scan_complete":false,"slot":"pending","reason":"view_enumeration_failed","live":0}`. False with a claimed count, selection or completed scan is malformed. |
| Combined normalized-basename mutant adequacy | **OPEN** | Both-guard deletion: 138 tests, zero failures/errors; independent coherent counterexample qualifies only under the mutant. |
| Other normalization differences | **OPEN**, unchanged limitation | An internal repeated separator on only one side produces `pending/view_selection_missing`. The same repeated separator on both sides matches and qualifies in the synthetic model; it does not join two different paths. |
| Formatting-independent lint beyond the actual generator's method layout | **PARTIAL**, inherited | Ref-return support is fixed. Existing one-line class/method and same-line second-method samples still yield unrecognized methods; inline-control compound numeric concatenation is still missed. Actual generated methods are recognized and independently audited. These pre-existing cases are printed by `independent_checks.py`; no general Enforce parser completeness is claimed. |
| Staging displacement protections / matching replacement race | **PARTIAL**, unchanged | Final-walk directory displacement is refused with no plan; symlink leaf replacement is refused. The inherited matching replacement demonstration still returns `staged-only-not-launched`, `outside_bytes=18`, `outside_written=true`, `plan_exists=true`, all within the explicit synthetic r7 fixture. No engine is launched. |

Earlier `red_regressions.py` (7 tests), `new_red_regressions.py` (4), `remaining_regressions.py` (4) and `view_regressions.py` (4) all pass. The ten-case normalization script initially retained its old final assertion that ordinary backslashes **must** be malformed; it now fails precisely because the fix works. That original output is preserved in `normalization-checks-r6-expectation.log` and its unchanged expectation script in `normalization_checks_r6.py`. The revised scratch assertion requires qualification with the explicit positive synthetic view/config fixture; all ten cases pass. This is not native rendering evidence.

**Compile safety and installed API evidence.** Cache root: `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`. Paths below are relative to it. `all_api_audit.py` enumerated **70 external API names** in the complete generated hook and located declarations for each (`all-api-audit.log`). The relevant receiver/argument/return shapes were checked, not inferred from the Python model.

| API | Installed file:line and declaration | Call-site assessment |
| --- | --- | --- |
| String mutation | `1_Core/proto/EnString.c:156` `int Replace(string sample,string replace)`; :171 `int ToLower()` | Mutates the receiver; neither integer return is assigned as string text. `m_HCTLSlash` is ASCII 92 via `int.AsciiToString`, `EnConvert.c:44`. |
| String search and slicing | `EnString.c:240` `int IndexOf(string)`; :253 `int LastIndexOf(string)`; :271 `int IndexOfFrom(int start,string sample)`; :113 `string Substring(int,int)`; :199 `int Length()` | New forward-scan argument order is correct. The `foundPos+1 < Length()` guard precedes IndexOfFrom. LastIndexOf is now used only in diagnostics. Proxy/view basename slicing uses forward-scan results. |
| LOD enumeration | `3_Game/Entities/Object.c:98` `bool GetLODS(notnull out array<LOD>)`; :101 `owned string GetLODName(LOD)` | `array<LOD>` allocated and declared before calls at probe :651/:677; cleared before calls and after false. Native `owned string` is safely assigned to a local string, as in the official wrapper. |
| Named LOD lookup | `Object.c:106` `LOD GetLODByName(string)`; wrapper :109–122; `3_Game/gameplay.c:207` `LOD.NAME_VIEW="view"` | Official wrapper compares lower-cased names. The new walk also requires lower-cased exact `view`. No resolution/geometry/VIEW_PILOT substitution. `view_by_name` is checked against the walk by the report; disagreement is malformed. |
| View selection/vertex | `gameplay.c:216` `bool GetSelections(notnull out array<Selection>)`; :184 `owned string Selection.GetName()`; :185 `int GetVertexCount()`; :186 `int GetLODVertexIndex(int)`; :188 `vector GetVertexPosition(LOD,int)`; :218 `vector LOD.GetVertexPosition(int)` | Allocated predeclared array; output cleared on false. Selection count >0 and LOD index != -1 guard vertex read. Correct Selection overload, not the distinct `LOD.GetName(Object)` overload. |
| Config child scan | `3_Game/Global/Game.c:611` `int ConfigGetChildrenCount(string)`; :594 `bool ConfigGetChildName(string,int,out string)` | `childName` predeclared at probe :1271 before :1280; correct receiver, arity, index and out string. At most 4096 iterations. Its results are header diagnostics. |
| Proxy config | `Game.c:449` `bool ConfigGetText(string,out string)`; :558 `void ConfigGetTextArray(string,out TStringArray)`; :612 `bool ConfigIsExisting(string)` | `modelPath`, `slotText`, `slotNames` predeclared; config read happens only for the prefixed class hit. The bare class result is serialized separately and never becomes cfg_exists/model/slots. |
| Ordinary selections and arrays | `Object.c:382` `void GetSelectionList(out TStringArray)`; `1_Core/proto/EnScript.c:380/:385/:394/:399/:407` array `Count/Clear/Find/Get/Insert` | All receivers and element/index types match. LOD and Selection objects remain engine-owned; no script deletion added. |
| Numeric serialization | `1_Core/proto/EnConvert.c:30` int `ToString()`; :115 float `ToString(bool simple=true)` | New counts/self-test results pass through explicit `.ToString()` or `HCTLIntField`; vertex components also use `.ToString()`. Booleans pass through HCTLBool. |
| Other existing hook APIs | Full file:line inventory in `all-api-audit.log` | Includes inventory creation/readback, slot lookups, memory/bones, object spawning/deletion, queued callbacks, world/version out parameters and file output. `HasAttachmentSlot` is a scripted method at `3_Game/Systems/Inventory/Inventory.c:188`, not an invented native call. |

Independent lexer output, discarding comments/quoted contents and splitting statements on `;{}` rather than newlines:

```text
AUDIT {"bytes":80397,"independent_max_plus":8,"lint_including_out_calls":[],
       "methods":61,"native_types":7190,
       "sha256":"9ae4cbce031509cc09090c713f39a5211136e97415808d31ebb545db73142e51",
       "shared_max_plus":8,"ternary_tokens":0}
EXTERNAL_API_COUNT 70 MISSING []
```

The extended lint includes all relevant out calls, including GetSelections/config reads and GetWorldName/GetVersion in addition to the newly registered GetLODS and ConfigGetChildName. There are no duplicate locals/parameters, native-type identifier collisions, ternaries or non-explicit numeric concatenations in the generated hook. The 27-plus checks still reject ordinary, multiline, inline-brace, CRLF and changed-indent statements. Literal plus signs and increments do not count as binary concatenations.

New helper loops have hard limits of 256 search hits; each advances its start position and tests the end of the string. LOD walks are capped at 128, emitted LOD names at eight, config scan at 4096 and emitted weaponlight children at eight. Existing proxy/selection walks cap at 512/24 and view paths at 256; inventory-slot output caps at eight. String trimming shortens its string on each iteration; digit validation increases an index bounded by that string's length. The searches remain bounded by finite input length even when a long string has no fixed byte cap before parsing. Engine calls themselves cannot be interrupted by the queued watchdog; this pre-existing documented limitation remains.

The completed native capture with the exact staged hook is stronger compile/server-run evidence than offline lint. It does **not** execute the successful view-LOD selection/vertex branch: every native view LOD is absent. No engine/compiler was launched by this review; no client presentation, two-client behavior or production acceptance is inferred.

**Can anything qualify without real view-LOD/config evidence?** For the proxy route, I found no such path. `_model_evidence` at report :531–537 requires a real prefixed config hit, matching normalized model path, matching inventory slot and `_view_problem` passing all LOD/enumeration/path/vertex checks. A bare-basename hit gives `[false,true]` in `cfg_tried_exists` while `cfg_exists` stays false and model/slots stay empty. The independent generated-hook case returns `pending/proxy_config_missing`. Missing view, wrong LOD names, failed view enumeration, failed LOD enumeration and the >128-LOD refusal all stay pending. Consistent positive capped evidence can still qualify; an unknown tail does not invalidate a known matching row.

For the report as a whole, **yes**: the documented selection/memory/bone route at report :522–523/:562–563 still qualifies independently, including when proxy fields are absent. This is not limited by producer version. Actual current generated-hook execution in the explicit synthetic catalogue with no view LOD and no config entries gives:

```text
CURRENT_HOOK_SELECTION_ROUTE {"live":0,"proxy_rows":0,
 "reason":"native_attach_with_rail_handguard_prerequisite","verdict":"qualified","view_lod":false}
LEGACY_ROUTE selection_on_model -> qualified/native_attach_with_model_selection
LEGACY_ROUTE memory_point       -> qualified/native_attach_with_model_selection
LEGACY_ROUTE bone_index         -> qualified/native_attach_with_model_selection
```

That is an existing independently supported model-evidence route, not proxy evidence fabricated from diagnostics. A claim that **every** qualified verdict necessarily has view-LOD/config evidence would be false. Likewise this review does not authenticate arbitrary externally fabricated observations or prove equivalence for every path lossy serialization can truncate.

The header `native_diagnostics` is computed only for output, after verdict aggregation. Across eight generated-hook scenarios and five changed/malformed headers apiece, verdict aggregates, integrity, acceptance and unobserved axes were unchanged. Per-host LOD facts and proxy-name facts are different: their consistency **is** validated and can make a row malformed, and successful LOD absence refines a pending reason. The report's broad prose that all per-host diagnostics “never change a verdict” should be read as the output projections, not as a claim that the corresponding input fields are ignored.

**Probe-005 native diagnostics.** `native_observations.py` ran the actual report CLI from the immutable authored scratch export, with classification from probe-003. It retained only aggregate output and selected identity/diagnostic examples; the full derived report was deleted. Native observations, init and profiles were read only and never copied into the review.

```text
status=complete observed=443 spawned=1839 deleted=1839
observations bytes=1455925
sha256=c1240254f2ed0778ec00c0c260ff234c0d716b701882b5451ef365fc094ba496
cleanup: live_after_release=0 residual_probe_types=0 timeouts=0 residual_other=1
integrity: cleanup_clean=true issues=[] unexpected_rows=[]
```

`string_self_test`:

```json
{"sample":"proxy:/dz/a/b.001","first_slash":6,"last_slash":11,
 "first_dot":13,"last_dot":13,"from_slash_7":9,"from_slash_10":11,
 "from_slash_12":-1,"from_dot_0":13,"loop_last_slash":11,"loop_last_dot":13,
 "bs_length":17,"bs_first":6,"bs_last":11,"bs_loop_last":11,"bs_count":3,
 "slash_code_length":1}
```

Native LastIndexOf agrees with IndexOfFrom and the forward scan on the fixed sample. This run supports the raw-backslash explanation for probe-004's basename failure, rather than a broken LastIndexOf implementation.

All **614** raw proxy rows have `sep_slash=0`. `sep_backslash` distribution is **4:68, 5:494, 6:7, 7:45** rows (3,099 backslashes total). All 118 hosts with proxy rows are represented. All 443 hosts have `lod_list_ok=true`, `lod_names_complete=true`, `view_lod=false`, `view_by_name=false`, `view_list_ok=false`, selection count zero and no successful view/vertex evidence. LOD count distribution is **3:1, 4:16, 5:268, 6:153, 7:5** hosts. Full ordered name-list aggregates are in `native_observations.log` / `supplemental-checks.log`; the names are resolution strings `0`, `1`, `2`, plus `VIEW_PILOT`, `geometry`, `memory`, `landContact`, `geometryView`, `geometryFire`. None equals `view` case-insensitively. These other LODs are not substituted.

`cfg_nonai_scan`: **820** children, **820** scanned, `complete=true`, **332** names starting with `proxy`. The two weaponlight children are:

```text
ProxyWeaponlight_universal -> /dz/weapons/attachments/light/weaponlight_universal.p3d
ProxyWeaponlight_TLR       -> /dz/weapons/attachments/light/weaponlight_TLR.p3d
```

`cfg_tried`: **573** prefixed-class hits, **41** prefixed-class misses, **zero** bare-basename hits. Universal-light rows try `[Proxyweaponlight_universal, weaponlight_universal]`, answer `[true,false]`, **22** rows. TLR rows try `[Proxyweaponlight_tlr, weaponlight_tlr]`, answer `[true,false]`, **7** rows. The successful AK74/Glock19 rows emit the correct matching model paths. Full per-name aggregate counts are retained in `native_observations.log` and `native-summary.log`; all 614 rows are accounted for. Parsing yields **441 ok / 2 malformed** host collections. The two malformed collections are exactly the coherent FNX alias cases discussed above.

Report acceptance remains `PENDING`; beam, switch, two-client presentation, removal by hand, tape consumption and persistence all remain pending. Complete server-side absence on these hosts is measured; its engine/rendering cause, and successful client view-LOD behavior, are not established here.

**Commands and actual output.** Every write was under `scratchpad-review/r7/`. Scripts use Python's standard library and explicit synthetic fixtures. Main runner output is in `checks.log`; sequential supplementary output is in `supplemental-checks.log`. Those files record exact argv/cwd/exit and raw outputs; individual logs are retained locally too. No broad unittest discovery was run: it includes synthetic Git-write fixtures, contrary to the explicit no-Git-write review restriction. The six focused modules were selected using the previous review's confinement audit.

```text
cat AGENTS.md
cat docs/SPECIFICATION.md
# cat: docs/SPECIFICATION.md: No such file or directory
# docs/specs/001-survival-overhaul/spec.md: No such file or directory (explicit existence check).
cat docs/RUNTIME_IMPLEMENTATION_CONTRACT.md
# read successfully
# Read banso-cli/SKILL.md and banso-status/SKILL.md; dispatched review scope applies.

git show c1ffaea
# six requested files only; complete output retained in git-show.txt

PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r7/export_snapshots.py
head c1ffaea tools/tests exported
parent 0c9f4ec tools/tests exported

PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r7/run_checks.py
# Focused inner command, cwd=r7/head; TMPDIR=/code/hc-worktrees/taped-light-review-4/scratchpad-review/r7/tmp:
python3 -B -m unittest tests.unit.test_probe_runtime tests.unit.test_ce_probe tests.unit.test_diagnostic_mission tests.unit.test_flashlight_matrix tests.unit.test_taped_light_probe tests.unit.test_taped_light_report -v
Ran 418 tests in 9.592s
OK
view_regressions.py       Ran 4 tests in 0.038s; OK
red_regressions.py        Ran 7 tests in 0.001s; OK
new_red_regressions.py    Ran 4 tests in 0.046s; OK
remaining_regressions.py  Ran 4 tests in 0.063s; OK
```

Exact mutant summaries from that runner (`failures, errors`):

| Mutant | Tests | Failures, errors | Result |
| --- | ---: | ---: | --- |
| delete_never_executes | 268 | 22,0 | KILLED |
| watchdog_does_not_cleanup | 268 | 1,2 | KILLED |
| census_scans_nothing | 268 | 4,0 | KILLED |
| create_attachment_arguments_reversed | 268 | 0,67 | KILLED |
| timeout_does_not_break | 268 | 3,0 | KILLED |
| found_type_guard_disabled | 268 | 3,0 | KILLED |
| handguard_untracked | 268 | 18,0 | KILLED |
| live_after_release_zeroed | 268 | 2,0 | KILLED |
| complexity_bound_disabled | 418 | 16,0 | KILLED |
| numeric_concat_disabled | 418 | 25,0 | KILLED |
| consecutive_dot_rule_removed | 418 | 4,0 | KILLED |
| ancestor_nofollow_removed | 418 | 18,0 | KILLED |
| leaf_nofollow_removed | 418 | 2,0 | KILLED |
| mission_final_inventory_removed | 418 | 1,0 | KILLED |
| linux_only_requirement_removed | 418 | 2,0 | KILLED |
| host_nested_invalidation_removed | 418 | 16,0 | KILLED |
| probe_nested_invalidation_removed | 418 | 15,0 | KILLED |
| slot_nested_invalidation_removed | 418 | 8,0 | KILLED |
| control_preflight_ignored | 418 | 1,0 | KILLED |
| control_failed_spawn_ignored | 418 | 1,0 | KILLED |
| variant_guard_identity_ignored | 418 | 7,0 | KILLED |
| variant_guard_occupancy_ignored | 418 | 1,0 | KILLED |
| variant_fit_conflict_ignored | 418 | 2,0 | KILLED |
| attach_contradiction_ignored | 418 | 3,0 | KILLED |
| counter_ranges_ignored | 418 | 2,0 | KILLED |
| census_ranges_ignored | 418 | 2,0 | KILLED |
| variant_readback_skipped | 418 | 23,0 | KILLED |

```text
# Same runner also invokes guard_mutations.py (138 tests per mutant):
not_dot_removed                         failures=0 errors=0 (equivalent)
not_number_removed                      failures=2 errors=0 (KILLED)
raw_trailing_slash_guard_removed         failures=1 errors=0 (KILLED)
normalized_empty_basename_guard_removed  failures=0 errors=0 (equivalent with companion guard)
# Both equivalent single deletions: 9331 short inputs each, differences=[]

# Parent red commands (expected exit 1):
python3 -B scratchpad-review/r7/native_basename_regression.py --parent
Ran 1 test in 0.019s
FAILED (failures=1)
python3 -B scratchpad-review/r7/remaining_regressions_parent.py
Ran 4 tests in 0.057s
FAILED (failures=1)

PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r7/supplemental_checks.py
snapshot_integrity.py       head c1ffaea files 162 differences []; parent 0c9f4ec files 162 differences []
closure_checks.py          all 8 ordered conflicts and 4 enumeration cases pass
normalization_checks.py    all 10 explicit end-to-end cases pass (updated fixed-case expectation)
compile_audit.py           bytes=80397 methods=61 native_types=7190 independent_max_plus=8 lint=[] ternary_tokens=0
extended_guard_mutations.py only_rsplit / only_endswith / both: 138 tests each, failures=errors=0; combined counterexample changes pending to qualified
native_basename_regression.py Ran 1 test ... OK; correct prefixed config hit, pending/view_lod_absent_on_server
native_checks.py           synthetic taped hook methods=50/max_plus=8/lint=[]; CE methods=20/max_plus=9/lint=[]
independent_checks.py      earlier report/lint edge outputs; probe-003 aggregate qualified=0 geometry_missing=415 excluded=141 pending=28
compare_ce_parent.py       control 9/9 files differences=[]; treatment 9/9 files differences=[]
all_api_audit.py           EXTERNAL_API_COUNT 70 MISSING []
qualification_checks.py   8 generated-hook scenarios, 40 header changes, 3 independent legacy evidence routes, 2 native alias diagnoses; all assertions pass
native_observations.py    real CLI result and native diagnostics as above
# After extending out-call audit to include world/version and adding current-hook selection route:
python3 -B scratchpad-review/r7/compile_audit.py
# same clean AUDIT output quoted above
python3 -B scratchpad-review/r7/qualification_checks.py
# CURRENT_HOOK_SELECTION_ROUTE and remaining outputs quoted above; exit 0
```

Native CLI executed by `native_observations.py` (cwd is the immutable authored export `scratchpad-review/r7/head`, not the root checkout; the absolute output is outside that exported checkout and inside the allowed review directory):

```text
python3 -B -m tools.audit.taped_light_report --classification /home/david/.cache/hollow-country/experiments/taped-light-probe-003/classification.json --observations /mnt/d/HollowCountryLocal/taped-light-probe-005/profiles/HCTapedLightProbe/observations.json --out /code/hc-worktrees/taped-light-review-4/scratchpad-review/r7/native-report.json
report: qualified=0 geometry_missing=417 excluded=141 pending=26 hosts=584 -> /code/hc-worktrees/taped-light-review-4/scratchpad-review/r7/native-report.json
```

Six independent synthetic cleanup scenarios also pass (`positive`, `no_lod`, `empty`, `getselections_false`, `missing_vertex`, `capped`), each with `status=complete, spawned=deleted=24, live=0`. No offline result is offered as native behavior.

Supplementary checks were rerun sequentially after source-mutating scratch tests finished, with byte-identical snapshot verification. One rerun initially hit a `FileExistsError` because the copied CE comparison helper reused its previous synthetic fixture; `supplemental-checks-initial.log` preserves that output. Its scratch-only helper now clears that fixture before rebuilding, and the final sequential run passes. No production file was fixed or changed.

No lifecycle command, panel/sub-agent, DayZ, Wine or PowerShell was launched. No Git mutator, game asset export, native source dump, signing key operation, public publishing or write under `/mnt/d` was performed. The pre-existing `.banso-brief-007.md` was left unchanged. No commit-message file was written outside r7. Authored scratch exports, full-module mutant copies and synthetic staging outputs are removed after verification; the scripts recreate them. `git diff --stat` is empty, and status shows only the pre-existing brief plus `scratchpad-review/r7/`.
