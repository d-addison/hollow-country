**Verdict: MERGE-WITH-FIXES — hc-taped-light-review-006.** Reviewed `0c9f4ece1cee373ec2b5f13e4d64c5a9a44616fc` against `691b11559dc361301c24147583dafec2484a2a7c` with `git show 0c9f4ec` (full output: `git-show.txt`). All three review-005 findings are **FIXED**. No new P0/P1 or false-qualification regression was found in the diff. One newly observed P2 needs a follow-up: ordinary backslash proxy selections produce invalid config class names. That defect also reproduces on the parent; it is not introduced by this fix commit. The recommendation permits merging the three fixes while requiring the native proxy extraction correction before treating the probe as usable evidence.

The focused suite passes **389 tests**; all **27 earlier mutants** remain killed. The full generated hook is **70,329 bytes**, SHA-256 **`c7b64082b046f50c56647ea4d3c684ced9a66b13826f36ad2294ed90a3f9d83a`**, max **8** binary `+` operators per statement. Probe-004 completed and its staged init contains this exact hook. Its data yields **zero qualified hosts** and no successful view-LOD evidence. Runtime acceptance and production enablement remain pending.

**Ranked finding.**

1. **P2 — Normalize ordinary proxy separators before extracting the basename.** `tools/setup/taped_light_probe.py:458` (`HCTLProxyBase`; called at :559).

   Failure scenario: an ordinary model selection is `proxy:\dz\weapons\attachments\light\weaponlight_universal.001`. `LastIndexOf("/")` finds no separator in those raw bytes. The resulting class is the entire path prefixed with `Proxy`, not `Proxyweaponlight_universal`. Config lookup fails; serialization subsequently changes the backslashes to forward slashes, producing `cfg_class="Proxy/dz/weapons/attachments/light/weaponlight_universal"`. The report correctly rejects that class/path contradiction as `proxy_evidence_malformed` before reaching the view check.

   This is visible in probe-004's AK74 and Glock19 rows. Across that capture, **118 hosts have 614 proxy rows, zero rows report `cfg_exists=true`, and all 118 proxy collections parse as malformed**. All 27 pending classified hosts have `proxy_evidence_malformed`. The native output alone does not expose the pre-serialization bytes; the explicit synthetic backslash reproduction produces the same bad class and establishes the source-level failure mechanism.

   Minimal fix: immediately after extracting `text` at :457, call `text.Replace(m_HCTLSlash, "/");`, then retain the existing basename/suffix extraction. Add an ordinary-selection backslash regression; the new uppercase/backslash *view* selection test does not cover this path. `native_basename_regression.py` fails identically on HEAD and parent. Applying just that line to generated text **in memory** passes: class `Proxyweaponlight_universal`, config found, and with the synthetic absent view LOD the report returns `pending/view_lod_missing`. No product file was changed, and this offline correction is not native acceptance.

**Review-005 closures and actual reproduction output.** `view_regressions.log` reruns the unchanged four r5 behavioral assertions against HEAD. `closure_checks.log` additionally prints both row orders and flag-only conflicts.

| Previous finding | Status | Actual HEAD output |
| --- | --- | --- |
| probe:506 substring model match | **FIXED** | `COINCIDENTAL_MODEL {"view":"","slot":"pending","reason":"view_selection_missing","live":0}`; `GENERIC_SELECTION {"slot":"pending","reason":"view_selection_mismatch"}` |
| report:333 conflicting view tuples | **FIXED** | Missing selection, different selection, different vertex, and flag-only disagreement all give `pending/proxy_evidence_malformed`, `qualified=0`, in **both** row orders. |
| probe:587 failed enumeration with populated output | **FIXED** | `FAILED_VIEW_ENUMERATION {"view_scan_complete":false,"slot":"pending","reason":"view_enumeration_failed","live":0}`. The hook clears before the call and again after false; count is zero and proxy view fields are empty/false. False with a claimed count, selection, or complete scan is malformed. |

Whole-path comparison now checks the prefix and nonempty ASCII-digit instance suffix in the hook, compares complete keys, and rechecks identity through `_view_path` in the report. There is no executable `Contains()` match. The repeated per-config lookup tuple includes all three view fields. Existing positive, capped-positive, prerequisite and cleanup behavior still passes the focused suite. The six independent cleanup scenarios each report `status=complete`, `spawned=deleted=24`, `live=0`; these are synthetic engine models.

Earlier r5 reproductions: seven original red assertions pass; four additional red assertions pass; three of the four `remaining_regressions.py` assertions pass. Its **unchanged pre-existing ref-return lint bypass remains OPEN**, with `FAILED (failures=1)` and `REF_RETURN_BYPASS {'status':'staged-only-not-launched','plan_exists':True,'extra_method_lint':[]}`. It is not a defect added by this diff. The actual generated hook has ordinary recognized method signatures and passes the checks below. Prior scan-swap refusal and the documented matching-replacement residual reproduce unchanged. CE control/treatment comparison has nine files each and zero byte differences against the parent.

**Compile safety and pinned API evidence.** Declarations were read from `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`; the paths below are relative to that cache. Full declarations and call checks are in `compile_audit.log`, `native_api_audit.log`, and `native_checks.log`.

| API used by the proxy/view code | Installed declaration | Assessment |
| --- | --- | --- |
| `Object.GetSelectionList` | `3_Game/Entities/Object.c:382`, `void GetSelectionList(out TStringArray)` | Allocated, predeclared string array. |
| `Object.GetLODByName` / `LOD.NAME_VIEW` | `Object.c:106`, `LOD GetLODByName(string)`; `3_Game/gameplay.c:207`, constant `"view"` | Correct receiver/argument/return; missing LOD is null. Wrapper predeclares `array<LOD>` before `GetLODS` at Object.c:98/:109. |
| `LOD.GetSelections` | `gameplay.c:216`, `bool GetSelections(notnull out array<Selection>)` | Array declared/allocated at probe:609, cleared before the call, bool retained, failure output cleared. No API promise of empty output on false is assumed. |
| Array operations | `1_Core/proto/EnScript.c:374`, generic `array<Class T>`; :380 `int Count()`; :385 `void Clear()`; :394 `int Find(T)`; :399 `T Get(int)`; :407 `int Insert(T)` | Receiver/element/index types match. Processed view names and selection indices remain aligned. |
| String operations | `1_Core/proto/EnString.c:113` `string Substring(int,int)`; :156 `int Replace(string,string)`; :171 `int ToLower()`; :199 `int Length()`; :240 `int IndexOf(string)`; :253 `int LastIndexOf(string)` | Mutating Replace/ToLower results are not assigned to strings; indices and lengths are integers. Prefix/dot/digit/loop guards precede the corresponding substrings. New code adds no unsupported string API. |
| Selection name and vertex | `gameplay.c:184` `owned string GetName()`; :185 `int GetVertexCount()`; :186 `int GetLODVertexIndex(int)`; :188 `vector GetVertexPosition(LOD,int)`; :218 `LOD.GetVertexPosition(int)` | Name is read from Selection, not the distinct LOD.GetName(Object). Count > 0 and index != -1 guard the scripted vertex read. |
| Config queries | `3_Game/Global/Game.c:449` `bool ConfigGetText(string,out string)`; :558 `void ConfigGetTextArray(string,out TStringArray)`; :612 `bool ConfigIsExisting(string)` | String/array out arguments declared before calls; correct arity/types. Finding 1 concerns the path content, not an unavailable API. |
| Numeric string conversion | `1_Core/proto/EnConvert.c:30` `int.ToString()`; :115 `float.ToString(bool simple=true)` | Counts and all three vector components use explicit `.ToString()`; booleans use HCTLBool. |

Full-hook lint uses **7,190 native type names**, explicit-number checking, and an in-memory extension of the out-call table for GetSelections/GetLODS/config reads. Actual output: `lint_including_out_calls=[]`, **54 methods**, `ternary_tokens=0`. No local/parameter collides with an engine type; no duplicate locals or inline undeclared out argument was found. An independent lexer discards quoted strings/comments and splits on statement/block terminators, not newlines: **max 8**. The r5 27-plus probes are still detected across normal, multiline, inline-brace, CRLF and altered indentation layouts. Literal plus signs and increments are not counted as binary concatenations.

Probe-004's completion plus the exact matching staged hook is native compile/server-run evidence consistent with the user's run attribution. This review launched no engine and inspected no compiler log. The all-absent view data does not exercise the successful GetSelections/name/vertex branches, and does not prove client rendering or two-client behavior.

**Normalization question.** `normalization_checks.log` records ten explicit end-to-end synthetic cases using the actual generated-hook model and report.

The hook retains internal repeated separators; the report collapses them. When only the model or only the view has a repeated separator, the hook emits **no view selection**, and the report stays `pending/view_selection_missing`. Report normalization cannot invent an omitted match. When **both** paths have the same repeated separator, their hook keys match and their report keys also match; that case **does qualify**, even though the two programs' normalized key strings differ. It is a same-model match, not a false qualification. Thus the unqualified claim that every normalization difference must end pending is too broad.

Nor is the hook parser globally stricter on every malformed spelling: it can return a key ending in `/`, while report `_proxy_name` rejects an empty basename. Those cases remain pending; the report re-verifies rather than trusting the emitted match. For an ordinary short, faithfully serialized emitted path, there is no demonstrated route from a failed hook equality to a proxy-qualified verdict. This conclusion is about the proxy route: independent legacy selection/memory/bone evidence can qualify without a successful proxy view match. Existing serialization caps remain, so no claim of equivalence for arbitrary lossy strings is made.

**Mutation equivalence.** Exact replacements are retained in the scripts/logs; the worker's name alone does not specify which clauses were removed.

| Deletion from `_proxy_name` | Current report suite | Independent assessment |
| --- | --- | --- |
| Only `not dot or` | 125 tests, zero failures/errors | Equivalent: absent separator leaves empty stem, rejected by `not path`. |
| Only `not number or` | 125 tests, **2 failures** | Killed; coherent empty suffix changes pending to qualified. |
| Only `or stem.endswith("/")` | 125 tests, **1 failure** | Killed by the newly added coherent raw-empty-basename regression. This closes the r5 test gap. |
| Only `or not path.rsplit("/", 1)[-1]` | 125 tests, zero failures/errors | Equivalent while `not path` and `path.endswith("/")` remain. |
| Only `or path.endswith("/")` | 125 tests, zero failures/errors | Equivalent while `not path` and the rsplit guard remain. |
| **Both** rsplit and endswith subclauses | 125 tests, **zero failures/errors** | **Not equivalent; surviving test gap.** `proxy:/dz/weapons/attachments/light/.p3d.001`, with coherent `cfg_class="Proxy"`, model `.../light/.p3d` and matching view row, changes from pending malformed to qualified. Stripping `.p3d` exposes the empty basename. |

The two single-clause equivalence claims are sound. A claim about deleting the combined rsplit/endswith check is false. The combined guard is present in HEAD, so this is a mutation-coverage limitation, not a current false-qualified result. Add that coherent `.p3d` counterexample if the combined mutant is part of the claimed adequacy set. Finite enumeration of 9,331 short spellings for each original redundant deletion found zero differences; the structural arguments establish the single-clause equivalences beyond that sample.

**Commands and actual output.** All review artifacts are under `scratchpad-review/r6/`. Reproductions use explicit synthetic fixtures except the clearly identified native reads. Snapshot scripts use read-only `git archive`; `run_checks.py` records exact argv/cwd/exit values and raw output in `checks.log` plus each named log. Temporary source mutations are sequential and apply only to the scratch export.

```text
# Initial read-only inspection:
cat AGENTS.md
cat docs/SPECIFICATION.md docs/specs/001-survival-overhaul/spec.md docs/RUNTIME_IMPLEMENTATION_CONTRACT.md
# first two files: No such file or directory; runtime contract read successfully

git show 0c9f4ec
# four requested files only; full output git-show.txt

# Recreate snapshots (the setup used these same git archive inputs):
PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r6/export_snapshots.py
head 0c9f4ec tools/tests exported
parent 691b115 tools/tests exported

PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad-review/r6/run_checks.py
# Focused command executed from r6/head with absolute TMPDIR=r6/tmp:
python3 -B -m unittest tests.unit.test_probe_runtime tests.unit.test_ce_probe tests.unit.test_diagnostic_mission tests.unit.test_flashlight_matrix tests.unit.test_taped_light_probe tests.unit.test_taped_light_report -v
Ran 389 tests in 6.675s
OK
# Individual reproductions invoked by run_checks.py:
view_regressions.py       Ran 4 tests in 0.032s; OK
red_regressions.py        Ran 7 tests in 0.001s; OK
new_red_regressions.py    Ran 4 tests in 0.042s; OK
remaining_regressions.py  Ran 4 tests in 0.058s; FAILED (failures=1)
# Only remaining failure is the pre-existing ref-return lint bypass.

# mutations.py: (failures, errors), 240 tests each
 delete_never_executes                 KILLED (20, 0)
 watchdog_does_not_cleanup             KILLED (1, 2)
 census_scans_nothing                  KILLED (4, 0)
 create_attachment_arguments_reversed KILLED (0, 53)
 timeout_does_not_break                KILLED (3, 0)
 found_type_guard_disabled             KILLED (3, 0)
 handguard_untracked                  KILLED (16, 0)
 live_after_release_zeroed             KILLED (2, 0)

# new_mutations.py: failures, no errors; 389 tests each
 complexity_bound_disabled          KILLED 12
 numeric_concat_disabled            KILLED 25
 consecutive_dot_rule_removed       KILLED 4
 ancestor_nofollow_removed           KILLED 18
 leaf_nofollow_removed               KILLED 2
 mission_final_inventory_removed     KILLED 1
 linux_only_requirement_removed      KILLED 2
 host_nested_invalidation_removed    KILLED 16
 probe_nested_invalidation_removed   KILLED 15
 slot_nested_invalidation_removed    KILLED 8
 control_preflight_ignored           KILLED 1
 control_failed_spawn_ignored        KILLED 1
 variant_guard_identity_ignored      KILLED 7
 variant_guard_occupancy_ignored     KILLED 1
 variant_fit_conflict_ignored        KILLED 2
 attach_contradiction_ignored        KILLED 3
 counter_ranges_ignored              KILLED 2
 census_ranges_ignored               KILLED 2
 variant_readback_skipped            KILLED 19

# Also invoked by run_checks.py; outputs retained separately:
guard_mutations.py       # exact guard results above
native_api_audit.py      # bytes=70329, max_plus=8, methods=54, lint=[]; six clean synthetic scenarios
deep_checks.py           # layout checks, report cases and scan-swap behavior; deep_checks.log
residual_race.py          # staged-only-not-launched, outside_bytes=18, outside_written=true, plan_exists=true

# Additional commands, each with PYTHONDONTWRITEBYTECODE=1 python3 -B and the r6/ prefix:
closure_checks.py        # eight ordered conflicts plus four enumeration combinations; all assertions pass
normalization_checks.py  # ten cases described above; all assertions pass
compile_audit.py         # independent_max_plus=8, shared_max_plus=8, ternary_tokens=0, lint=[]
extended_guard_mutations.py # three exact mutants; combined guard counterexample changes verdict
native_basename_regression.py          # Ran 1 test in 0.016s; FAILED (failures=1)
native_basename_regression.py --parent # Ran 1 test in 0.017s; FAILED (failures=1)
native_basename_regression.py --fixed  # Ran 1 test in 0.022s; OK (generated-text change in memory only)
independent_checks.py    # probe-003 aggregate still qualified=0/geometry_missing=415/excluded=141/pending=28
native_checks.py         # 7190 types; synthetic taped hook methods=43/max_plus=8/lint=[]
compare_ce_parent.py     # control 9/9 files differences=[]; treatment 9/9 files differences=[]
native_observations.py   # runs the following real CLI; retains only aggregates and two config-identity examples
```

Native CLI (cwd `scratchpad-review/r6/head`, immutable authored export; absolute output outside that exported source root and inside the allowed review directory):

```text
python3 -B -m tools.audit.taped_light_report --classification /home/david/.cache/hollow-country/experiments/taped-light-probe-003/classification.json --observations /mnt/d/HollowCountryLocal/taped-light-probe-004/profiles/HCTapedLightProbe/observations.json --out /code/hc-worktrees/taped-light-review-4/scratchpad-review/r6/native-report.json
report: qualified=0 geometry_missing=416 excluded=141 pending=27 hosts=584 -> /code/hc-worktrees/taped-light-review-4/scratchpad-review/r6/native-report.json
```

`native-summary.log` records observations SHA-256 `f1af7231e72c037228f21e0a89baec7627a904c8a2cdb66293d9480fd76d4b29`, 1,299,600 bytes, sentinel `status=complete observed=443 spawned=1839 deleted=1839`, cleanup `live_after_release=0`, `residual_probe_types=0`, `timeouts=0`, `residual_other=1`, report integrity issues `[]`. Every observed host has `view_lod=false`, `view_list_ok=false`, `view_scan_complete=false`, `view_selection_count=0`. The emitted absence/failure bookkeeping is coherent; successful view enumeration and vertices remain unobserved. A missing view LOD is not an observed failed GetSelections call. All six unobserved acceptance axes stay pending. The full derived report was deleted after aggregate inspection; no native observations, init, native source tree or full profile was copied into the review.

**Execution scope and limitations.** Banso dispatched-worker guidance and the runtime contract were read. The two requested specification files are absent. No lifecycle command, panel, sub-agent, DayZ, Wine or PowerShell was launched. No implementation files, Git metadata or `/mnt/d` files were intentionally changed; the runtime and native cache were read only. The unrelated existing `.banso-brief-006.md` was left untouched. No commit-message file was written outside r6.

There was one confinement mistake: the first focused command used `TMPDIR="$PWD/scratchpad-review/r6/tmp"` while its cwd was already `r6/head`, producing an invalid nested path. Python fell back to `/tmp` for that run's temporary fixtures; the tests cleaned them up. The passing command recorded above was rerun with a validated absolute `r6/tmp` path. Also, the first native CLI attempt used `--out ../native-report.json`; its lexical checkout guard refused it with `taped_light_report: report output must be outside the source checkout`, and no output was written. The successful invocation uses the absolute allowed output path.

Broad unittest discovery was not executed: r5 established that it runs synthetic Git-write fixtures, contrary to this review's explicit confinement. No full-suite pass is claimed. Before cleanup, both scratch snapshots were compared byte-for-byte with fresh Git archives: `head 0c9f4ec files 162 differences []`; `parent 691b115 files 162 differences []` (`snapshot-integrity.log`). `git diff --stat` was empty; status showed only the pre-existing brief and the new r6 directory. Scratch snapshots, generated full-module mutant copies and synthetic staging outputs are removed after verification; `export_snapshots.py` recreates the source inputs for reruns. Scripts and actual output logs remain.
