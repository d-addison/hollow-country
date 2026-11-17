**Verdict: BLOCK — hc-taped-light-review-003, commit 06e00be6bf563b0879896ac4c16cb16db7665e46 against fb05ff1.**

Round 2 fixes the seven old red assertions and all eight old mutants remain killed. The generated taped-light hook is now within the observed expression budget. Three P2 source issues remain: a final directory scan can certify a tree containing a substituted symlink; method formatting bypasses expression lint; and contradictory attachment read-back still passes report gates. No new P0 or P1 was found.

This is a source review with explicit synthetic fixtures. All writes were under `scratchpad-review/`; repository implementation and git metadata were not deliberately modified. No DayZ, Wine, PowerShell, or /mnt/d staging was invoked. Native declarations were read from the supplied 1.30.164289 cache. AGENTS.md, the runtime contract, the prior review/scripts, and the complete commit diff were read. `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` remain absent; no available Banso spec/plan/tasks artifacts were found in this checkout. The supplied task contract controls this read-only review.

**Ranked findings.** References are to 06e00be, not the exported mutant modules.

1. **P2 — An opened directory is never checked against its current pathname before staging succeeds.** `tools/setup/diagnostic_mission.py:259`, especially `:279`; write-side counterpart `:194`. During the last `walk_plain` inside `launcher_problems`, let `_open_child_dir` open `mpmissions/dayzOffline.chernarusplus/db`, then rename that directory to another scratch location and put a symlink at its original name. The scanner examines the retained descriptor of the moved directory. It never rechecks the link now occupying the name, returns the expected inventory, and `write_plan` writes a completed plan. Actual reproduction: `outcome=ACCEPTED`, `plan_exists=true`, `symlinks=["mpmissions/dayzOffline.chernarusplus/db"]`. This happens on the ordinary local Linux filesystem, independently of DrvFs.

   There is also a refusal residue: move destination `battleye` after its descriptor is opened but before `open_file_at` creates the DLL. The retained descriptor receives an 18-byte DLL in the moved directory outside the requested destination. Staging subsequently refuses it, with no plan. The fix closes the old *before-open* link replacement, but the comment claiming refusal of a component swapped “at any moment” is too strong.

   Minimal fix for the successful certification gap: retain parent descriptors and entry names/identities during traversal, compare each opened directory's `(dev, ino)` with a no-follow stat of its name after scanning, and refuse displaced/replaced directories before publishing a plan. Apply identity checking to the root as well. If the contract also promises no outside-destination write under concurrent renames, descriptor traversal alone cannot guarantee that: staging needs a protected directory/ancestor namespace or an explicitly narrower concurrency contract. Add the after-open rename cases to the behavioral tests. Repeated Windows launcher checks mitigate launching an already linked tree, but cannot undo an earlier write or make this staging result accurate. Evidence: `deep-checks.log`, `new-red-regressions.log`.

2. **P2 — Expression complexity checks silently skip valid method layouts.** `tools/setup/probe_runtime.py:334`, relying on `_FUNCTION` at `:159`. `_expression_issues` counts operators only within functions matched by the exact four-space, next-line-brace regex. Put the opening brace on the declaration line, or indent the declaration eight spaces: a statement containing 27 binary `+` operators receives `lint_hook(..., explicit_numbers=True) == []`, although `max_statement_plus` correctly returns 27. `staged_lint_bypass.py` injects such a helper into the otherwise unchanged generated hook; the real taped-light stager returns `staged-only-not-launched` and writes its plan.

   Minimal fix: enforce the statement complexity bound over **all** cleaned statements, independently of function recognition. For rules needing scope, parse accepted layouts or reject unrecognized method bodies instead of skipping them. Add inline-brace and indentation regressions at the stager boundary. This is a lint bypass; no compilation of the injected hook was attempted. The normal current generator has maximum 8 and passes.

   The optional numeric rule also misses `row += count`, `row += "n=" + count`, and `row = "n=" + (count)` with `int count`. Handle compound assignments as concatenations when their destination is a string, and normalize parenthesized terms. These are gaps in the opt-in policy, not independent proof that the native compiler rejects bare numbers. Evidence: `deep-checks.log`, `staged-lint-bypass.log`, `new-red-regressions.log`.

3. **P2 — The attachment contradiction check covers only one implication.** `tools/audit/taped_light_report.py:203`, with control consumption at `:360` and raw control-hit detection at `:496`. Keep a control attempt's `can_add=false, attach_ok=false`, but set `found_type="Flashlight"`. The host and UniversalLight pair remain **qualified**, `integrity.issues=[]`, and `control.unexpected_attachments=[]`. A representative with `can_add=false, attach_ok=false, found_type="UniversalLight"` becomes **geometry_missing/native_attach_refused** rather than pending. These states contradict the producer: it initializes `found_type` empty and fills it only after successful creation/read-back. The new guard rejects `attach_ok && !can_add`, but accepts a found item despite no successful attach.

   Minimal fix: reject nonempty `found_type` when `attach_ok` is false before positive or negative evaluation, and make control validation treat contradictory read-back as invalid evidence. Retain representative type matching and propagate pending to affected pairs/slots. Add both control and representative cases. Evidence: `deep-checks.log`, `new-red-regressions.log`.

The deeper checks also show `spawned=deleted=0` with populated spawn/attachment observations still qualifies, and negative unused `attach_ok`, `timeouts`, and `residual_other` counters are ignored. The exact prior negative-spawn/census case is fixed. These additional counter consistency gaps are recorded in `deep-checks.log`; they are not needed to establish finding 3.

**Disposition of each prior ranked finding.**

| Prior finding in review 002 | Status | Actual rerun evidence |
| --- | --- | --- |
| 1. Host/probe invalidation leaves qualified nested pairs/slots | FIXED | Partial status, dirty cleanup, wrong host type, config disagreement and control hit now demote the qualified pair; old red assertions pass. `adversarial.log` shows qualified pair count removed in those cases. Host invalidation also demotes geometry_missing siblings. |
| 2. Control completeness/identity bypasses | FIXED for the reported missing/duplicate/type/spawn/fit cases | Missing or duplicate control preflight, wrong type, preflight/host spawned=false and fit disagreement all produce host=pending and UniversalLight=pending. The separate contradictory read-back remains under finding 3 above. |
| 3. Prerequisite fit and identity bypasses | FIXED | Wrong handguard -> pending/prerequisite_variant_invalid; wrong variant fit -> pending/preflight_variant_disagree; missing fit and duplicate variant light -> pending. Read-back type, occupancy and rail fields are emitted and checked; removing those checks is killed by tests. |
| 4. Path check followed by unanchored open/write | PARTIAL | All old before-open swaps are refused. Old redirected DLL write now has outside_dest_written=False. Standalone admitted same-byte leaf link is refused before the marker. After-open directory replacement still yields an accepted linked tree or an outside write on refusal (finding 1). |
| 5. Contradictory evidence and impossible ranges | PARTIAL | can_add=false + attach_ok=true now -> pending/slot_evidence_invalid. Negative spawned/deleted/census values now -> pending with counters_out_of_range/census_out_of_range. Found-type-without-success contradictions still pass (finding 3). |
| 6. Python/PS1 name mismatch | FIXED | a..b and a...b are refused by Python and the statically mirrored PS1 rule; full a..b staging refuses before destination creation. PS1 is unchanged and was not executed. |
| 7. ce_probe public imported names disappeared | FIXED | ce_probe: baseline_count=54, missing=[]; diagnostic_mission: 17, missing=[]; test_ce_probe: 50, missing=[]. datetime/hashlib/PureWindowsPath are restored. |

For the prior nine reproduction families: Windows aliases, prerequisite handling, cleanup/time bounds, and original mutation coverage are fixed within the tested scope. Source-copy/race handling and attachment conflicts remain partial as described above. Missing/mistyped evidence and identity/config cases now produce pending for the original reproductions; probe-integrity invalidation no longer leaks qualified pairs. A missing sibling light deliberately leaves an independently valid pair qualified while making its host pending, as permitted in review 002.

**Native hook and compatibility checks.**

The supplied source cache declares 7190 native type names. Full current generated hooks pass the shared lint with those names: taped-light has 36 recognized methods, maximum 8 binary `+` per statement, and no explicit-number findings; CE has 20 methods, maximum 9, and no default findings. Existing checks cover leading boolean continuations, ternaries, exponent literals, native type collisions, duplicate locals and required out variables. This establishes source shapes, not native compilation.

`3_Game/Systems/Inventory/Inventory.c:215` declares `CreateAttachmentEx(string typeName, int slotId)`; `:224` declares `FindAttachment(int slot)`. The variant calls both in that order with the slot ID obtained from `InventorySlots.GetSlotIdFromString`, using the prerequisite index from an already validated native slot. InventorySlots.c:42/:59 declare lookup/validity. `UniversalLight.c:39-40` reads the occupant and its `hasRailFunctionality`; :128-130 lists the same M4/AK/MP5 slots used by the probe. Native AKM/AK101/M4A1/MP5 source contains the selected rail-handguard names. The read-back code uses verified API shapes and treats a wrong occupant/nonrail result as unusable in the report.

All returning handguard paths are tracked: successful creation inserts the returned handguard before observing lights; failure retains only the host where applicable; common host release and watchdog finish release tracked objects in reverse order. Synthetic reruns: normal spawned=deleted=24/no live entities; refused guard 21/21/no live entities; refused variant host 20/20/no live entities; watchdog partial 5/5/no live entities; stuck guard live_after_release=1 and integrity failure; 2049 census objects -> census_incomplete. The queued watchdog still cannot interrupt a synchronous hang, as documented. Actual object deletion/nulling, native compile and runtime acceptance remain pending.

The CE bare-number claim is supported by its generator, including `Print(... + m_HCProbeClasses.Count())`, `HCProbeVector` numeric components, and numeric row fields. Combined with the user-supplied successful CE native run, it is reasonable to keep the explicit-number policy opt-in. The previous native failure combined high complexity with a bare integer; it did not isolate numeric conversion as the cause. CE's unchanged bytes do not require falsely claiming bare numbers are always compiler errors. The synthetic strict-string model is an authoring policy, not new engine evidence.

The complexity check **does** count one statement across multiple lines and normalizes CRLF. Literal plus signs are ignored, normal `++` and `+=` updates do not inflate the binary-plus count, and independent statements are counted separately. Compound-string numeric and method-layout bypasses are documented in finding 2. The 9 bound is the observed CE maximum, not a general measured compiler threshold for every expression shape.

The taped output claim needs qualification: default and stuck/background runs differ literally from the parent by the three new variant read-back fields (12184 -> 12287 bytes). Removing exactly those fields makes the text byte-identical to the prior golden in all four tested scenarios; printed output is identical. Timeout/watchdog scenarios without a variant are literally unchanged. `hook-golden.log` records hashes and comparisons.

CE control and treatment staging are literally byte-identical to 76678fe for the same synthetic paths/time: 9 versus 9 files, differences=[] in both cases, including init.c, manifest and plan. No JSON normalization was used. This is fixture compatibility, not a new native CE run.

**Filesystem scope and refusal residues.**

The new Linux-only dir_fd primitives walk from `/` using O_DIRECTORY|O_NOFOLLOW, and leaf operations use dir_fd with no-follow/exclusive creation. Unsupported platform/dir_fd capability cases refuse. Pre-existing symlinks, changed config, and newly added sensitive mission paths refuse before creating a destination. Mission byte drift, corrupt writes and late destination links can leave a partial destination without a plan; this is the existing documented preserve-on-failure policy and is not independently a defect. The after-open outside write and completed linked-tree result are separate findings.

DrvFs junction/reparse behavior was not tested, and nothing was accessed under /mnt/d. The code explicitly documents that Windows-side replacements remain a residual; its “pinned” test checks documentation and launcher text, not filesystem behavior. PS1 contains two reparse scans, including one before launch. Those are useful later checks, not proof of an atomic staging/launch boundary. The ordinary Linux race in finding 1 means the residual is broader than DrvFs junctions alone.

**Commands and actual output.** All authored code/logs/fixtures were confined to this scratch directory. Tests imported immutable git exports so their scratch temp paths were outside each exported module's own checkout. Snapshot modules changed by the mutation harness were restored byte-for-byte afterward. To recreate exports after artifact cleanup, run `PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/export_snapshots.py` first.

```text
git show 06e00be > scratchpad-review/commit.diff
# complete diff retained

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/red_regressions.py
Ran 7 tests in 0.001s
OK

# cwd scratchpad-review/head, with TMPDIR=/code/hc-worktrees/taped-light-review-3/scratchpad-review/tmp
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_probe_runtime tests.unit.test_ce_probe tests.unit.test_diagnostic_mission tests.unit.test_flashlight_matrix tests.unit.test_taped_light_probe tests.unit.test_taped_light_report -v
Ran 283 tests in 4.799s
OK

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutations.py
# Each mutant runs 161 tests. Actual (failures, errors):
delete_never_executes:                 KILLED (10, 0)
watchdog_does_not_cleanup:             KILLED (1, 2)
census_scans_nothing:                  KILLED (4, 0)
create_attachment_arguments_reversed: KILLED (0, 15)
timeout_does_not_break:                KILLED (3, 0)
found_type_guard_disabled:             KILLED (2, 0)
handguard_untracked:                   KILLED (6, 0)
live_after_release_zeroed:             KILLED (2, 0)

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/new_mutations.py
# Independently selected 19 mutants, not a recovered worker harness; each runs 283 tests.
# 19 KILLED, 0 SURVIVED. Full names and actual failure counts: new-mutations.log.

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/compare_ce.py
PUBLIC ce_probe baseline_count= 54 missing= []
PUBLIC diagnostic_mission baseline_count= 17 missing= []
PUBLIC test_ce_probe baseline_count= 50 missing= []
MAX_HOOK_BYTES= 262144
BYTE-COMPARE control files= 9 9 differences= []
BYTE-COMPARE treatment files= 9 9 differences= []

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/staging_checks.py
# Original script adapted only to continue after the two newly expected refusals.
FULL STAGE a..b: REFUSED ...; destination_exists=False
REDIRECTED WRITE: refused=symlinked or non-directory path component refused: battleye; outside_dest_written=False; outside_bytes=None
STANDALONE ADMITTED MISSION destination symlink before reread: REFUSED symlinked or non-directory path component refused: types.xml; marker_exists=False

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/staged_lint_bypass.py
bad_hook_max_statement_plus= 27
bad_hook_lint= []
stage_status= staged-only-not-launched plan_exists= True

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/deep_checks.py
# Full JSON rows: deep-checks.log. Key actual fields:
# db swapped after final walk opened it: outcome=ACCEPTED; plan_exists=true; symlinks=[.../db]
# battleye moved after directory open before leaf write: refused; outside_written=true; outside_bytes=18; plan_exists=false
# control found despite failed create: host=qualified; integrity=[]; control_hits=[]
# representative found despite failed create: host=geometry_missing

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/new_red_regressions.py
Ran 4 tests in 0.037s
FAILED (failures=4)
# Intentional red assertions for the remaining scan, complexity, numeric-policy and control-readback gaps.

# In scratchpad-review/parent and scratchpad-review/head with the same scratch TMPDIR:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
parent: Ran 1991 tests in 54.867s; FAILED (failures=1, errors=155, skipped=1)
head:   Ran 2041 tests in 56.304s; FAILED (failures=1, errors=155, skipped=1)
full-discovery failure labels identical: True
parent-only: []
head-only: []
# Deployment/native-startup fixtures reject scratch TMPDIR paths under a source checkout;
# baseline reproduces the same labels. This is not a clean full-suite pass or a new regression.
```

`adversarial.log`, `hook-paths.log`, `hook-golden.log` and `native-checks.log` contain the other rerun outputs. Existing focused tests and mutation kills do not override the new failing assertions. No production enablement or runtime acceptance is established by this review.
