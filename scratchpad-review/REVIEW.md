**Verdict: BLOCK — fb05ff1228657e8dcc457e8a5c986e85d0ee24a4 against 76678fe.**

The fix round closes the original literal Windows aliases, ordinary symlink inputs, unadmitted mission additions, changed config copying, and the six original mutation survivors. CE control and treatment output is literally byte-identical for the same synthetic inputs. Report qualification still escapes several evidence gates, and the filesystem hardening still has reproducible link races.

This was a read-only source review. Repository source was not edited, git metadata was not deliberately written, and no DayZ, Wine, PowerShell, or /mnt/d staging was run. All authored scripts, exported snapshots, temporary fixtures and logs are under scratchpad-review/. Python bytecode writing was disabled. These synthetic checks do not establish DayZ behavior or native compilation.

AGENTS.md and docs/RUNTIME_IMPLEMENTATION_CONTRACT.md were read. docs/SPECIFICATION.md and docs/specs/001-survival-overhaul/spec.md are absent. The requested worker adaptation directory `/tmp/claude-1000/-code-dayzsa-mods/c2f49688-a754-49e7-ae80-940623b5a25a/scratchpad/` is also absent. I read the original scripts/logs at `/code/hc-worktrees/taped-light-review/scratchpad-review/`; I did not execute or rely on worker-adapted scripts. The earlier final review text was not provided: the nine titles below reconstruct its reproduction families, rather than claiming to reproduce unavailable wording. The worker tests label the middle four families P1-3 through P1-6.

**Ranked remaining findings.** All line references below are in fb05ff1.

1. **P1 — Host/probe invalidation leaves qualified pairs and slots in the exported matrix.** `tools/audit/taped_light_report.py:426`, also :352 and :468. Set the baseline observation status to `partial`, change cleanup to `deleted=9,residual_probe_types=1`, or attach the control. The host becomes pending, but its UniversalLight record and weaponFlashlight slot stay qualified, and `denominators.host_light_pairs.qualified` remains 1. Setting `hosts[0].type="OtherHost"` or changing the classified host slot has the same nested qualification leak. Consumers of the host/light matrix can still select unsupported results. Minimal fix: apply probe-wide and host-identity/config invalidation to affected light and slot verdicts before computing pair counts. A missing sibling light alone need not invalidate independently valid pairs; the problem here is evidence that invalidates the pair itself or its entire run. Evidence: `adversarial.log`, `red-regressions.log`.

2. **P2 — Control completeness and identity checks are bypassed.** `tools/audit/taped_light_report.py:344`. The control branch never consults `context["preflights"]`, and explicitly exempts `light_not_spawned`. Removing Flashlight's preflight, duplicating it, changing its type, setting its preflight or host observation spawned=false, or contradicting its preflight fit all leave the host qualified with `integrity.issues=[]`. A missing control row is pending, so the spawned=false exemption defeats that completeness rule. Minimal fix: require one successful, typed, identity-consistent preflight and full host per-slot evidence for each expected control, validate fit agreement, and propagate failure into the evidence gate. Evidence: `adversarial.log`, `red-regressions.log`.

3. **P2 — Prerequisite variants bypass the fit and prerequisite identity checks.** `tools/audit/taped_light_report.py:246`, also :159; producer `tools/setup/taped_light_probe.py:774`. On an AK handguard variant, changing the UniversalLight weapon-slot `light_fits` to false still produces `qualified/native_attach_with_rail_handguard_prerequisite`, although the preflight says true. Changing `handguard` to `AK_PlasticHndgrd` also retains that reason. The emitter records the requested handguard name and a non-null CreateAttachmentEx result, rather than its observed type, slot occupant and rail functionality; the report accepts any string as the name. Minimal fix: run variant attempts through the same fit/consistency checks as base attempts, bind the handguard name to the selected slot, and emit/check the observed handguard type, occupancy and rail property using the already inspected APIs. Missing/contradictory prerequisite proof must remain pending. Evidence: `adversarial.log`, `red-regressions.log`.

4. **P2 — Link refusal is a path check followed by an unanchored open/write.** `tools/setup/probe_runtime.py:67`, :110 and :436; `tools/setup/diagnostic_mission.py:205` and :310. Moving source/battleye to another scratch directory and replacing it with a symlink immediately before `_open_regular` opens the DLL is accepted, including a completed staging plan. O_NOFOLLOW protects only the final component; check_unchanged lstats that component through its parent link and accepts the same inode. Replacing destination/battleye with a symlink immediately before new_file writes produces an 18-byte DLL outside the destination before the final scan refuses the run. A standalone *admitted* diagnostic mission can replace a staged file with a same-byte symlink immediately before `_reread_digest`; it returns success and writes its marker with the symlink still present. These are controlled race injections, not claims that arbitrary unpinned bytes defeat the hashes. Minimal fix: traverse/open relative to retained directory descriptors with no-follow handling at each component, create and reread outputs relative to those descriptors, and verify directory identities/final inventory before success. For supported Windows execution, refuse reparse attributes as well. A repeated pathname-only precheck does not close the race. Evidence: `staging-checks.log`.

5. **P2 — Typed evidence is accepted despite impossible relationships or ranges.** `tools/audit/taped_light_report.py:228` and :377. Setting a representative's can_add=false while attach_ok=true and found_type=UniversalLight produces geometry_missing/native_attach_refused, rather than pending for contradiction. Setting spawned=deleted=-1 and census_total=census_scanned=-2 produces a qualified host with no integrity issues. Minimal fix: reject contradictory attach/found combinations before either positive or negative evaluation, and validate nonnegative counts plus `0 <= scanned <= total` and the census scan cap. Evidence: `adversarial.log`, `red-regressions.log`.

6. **P2 — Python and PS1 runtime-name acceptance still differ.** `tools/setup/Start-CEProbeServer.ps1:77`, versus `tools/setup/probe_runtime.py:332`. Python accepts `a..b` and `a...b`; full synthetic staging into a..b writes a completed plan. The launcher's `$root -match '\.\.'` rejects both before reading that plan. The new trailing-dot/device subexpressions otherwise agree on the tested ASCII domain. Minimal fix: use a shared set of executable name cases and either reject consecutive dots consistently in Python and launcher_problems or remove the launcher's broader substring rule while retaining direct-child/traversal checks. Evidence: `staging-checks.log`. This comparison is static; PowerShell was not executed.

7. **P3 compatibility note — Three previously public imported names disappeared.** `tools/setup/ce_probe.py:17`. At 76678fe ce_probe exposes datetime, hashlib and PureWindowsPath; all three imports now fail. Every authored public name remains, and no in-repository caller of these three was identified, so this is lower priority than the evidence bugs. Minimal fix, if the promised entire public namespace is the contract: restore the three imports/re-exports. All diagnostic_mission public names, including MAX_HOOK_BYTES=262144, and all 50 baseline public test_ce_probe names remain importable. Evidence: `compare-ce.log`.

**Nine original reproduction families.** Status includes the remaining related cases above; literal original cases are called out so the fix round gets credit for what it closes.

| Family | Status | Actual independent output |
| --- | --- | --- |
| 1. Windows alias of verified runtime | FIXED | `vanilla-p0-001.` -> ValueError/plain name; CON and nul.txt -> ValueError/reserved name; name. refused. The a..b launcher mismatch is finding 6 above. |
| 2. Source/staging copy integrity and symlinks | PARTIAL | Each original linked config/DLL/plan is refused with destination_exists=False; changed config and newly added credentials.json refused before destination creation. Remaining source-parent link race -> ACCEPTED, plan_exists=True; destination redirection writes before refusal. |
| 3. Missing/mistyped evidence (worker label P1-3) | PARTIAL | Missing TLRLight, missing slot/can_add, null slots/per_slot and empty no-slot evidence all -> host pending. Missing control preflight / spawned=false control -> host qualified. |
| 4. Duplicates and conflicts (P1-4) | PARTIAL | All original host-slot/light/per-slot/preflight duplicates -> pending; duplicate-hidden control hit is detected. Control preflight duplicates still qualify; can_add=false + attach_ok=true becomes geometry_missing. |
| 5. Identity/config disagreement (P1-5) | PARTIAL | Wrong host type/config slots -> host pending, but UniversalLight and pair count remain qualified; wrong representative preflight -> pending. Wrong control type or variant fit still qualifies the host. |
| 6. Rail-handguard prerequisite (P1-6) | PARTIAL | Native-rule slots/types verified; refusal without variant -> pending/refusal_may_depend_on_prerequisite; valid synthetic variant -> qualified; false variant fit / wrong handguard label also -> qualified. |
| 7. Probe integrity gates | PARTIAL | Partial status, dirty cleanup and control hit demote hosts; nested pairs/slots remain qualified. Negative counters are accepted. Truncated census now correctly records census_incomplete. |
| 8. Cleanup/live counter/census/time budget | FIXED in returning synthetic paths | Normal run spawned=deleted=24, no live objects; refused guard/variant creation leaves no objects; watchdog -> partial and no live objects; stuck guard -> live_after_release=1/integrity failure; 2049-object census -> census_incomplete. Existing tests catch the last-observation timeout and timeout-loop mutation. A synchronous hang remains explicitly uninterruptible by the queued watchdog. |
| 9. Missing behavioral regression coverage | FIXED for original mutants | All six original mutants KILLED by the current tests. Extra untracked-handguard and zeroed-live-counter mutants also KILLED. This is synthetic text/model coverage, not engine acceptance. |

**CE refactor and hook checks.**

`compare_ce.py` exports 76678fe and fb05ff1 without git metadata, imports each in isolation, and stages the same source and destination paths with a fixed UTC time. No JSON normalization or path rewriting is used for comparison. Both control and treatment: 9 files versus 9 files, differences=[]; this includes the marker, instrumented init.c and plan.

Public surface comparison: ce_probe baseline_count=54, missing=[PureWindowsPath, datetime, hashlib]; diagnostic_mission baseline_count=17, missing=[]; test_ce_probe baseline_count=50, missing=[]. MAX_HOOK_BYTES=262144. The preserved callable test helpers include build_model, count_scenarios, default_counts, enforce_to_python, fragment_json, local_inside, make_source_runtime, placement_world, pos_xml, scenario_mismatches, sha, targets_for.

The cache has 7190 declared native type names. Rendered-hook lint=[] across 36 methods; leading boolean operators=[], ternary tokens=0, exponent literals=[]. No engine type-name identifiers, duplicate function locals or undeclared out arguments were reported; manual inspection agrees with the relevant new methods. The taped-light hook needs no FLT_MAX sentinel. Native Inventory.c:215 confirms CreateAttachmentEx(string typeName, int slotId); InventorySlots.c:80/:86 and Game.c:930 confirm the inspected out-argument shapes. No native compile was run.

UniversalLight.c:25-45 and :123-132 match the prerequisite slots. AKM.c:48 and AK101.c:15 use AK_RailHndgrd, M4A1.c:16 uses M4_RISHndgrd, and MP5.c:48 uses MP5_RailHndgrd. The pre-existing local config capture also has the corresponding inventorySlot tokens and hasRailFunctionality=1 for all three (not re-admitted; array element kinds were originally unresolved). These checks establish source/config references, not successful native attachment.

The variant's successful host and handguard are registered in m_HCTLLive and the common release runs after the variant row. All early returns before creation allocate nothing. Refused host/guard creation paths retain the appropriate tracked host until that release. The watchdog uses HCTLFinish -> release. The returning synthetic scenarios confirm those paths; removing guard tracking is killed by four tests. A native failure/hang remains pending.

**Copy refusal residues.** Pre-existing links, added sensitive entries and config drift are refused without creating the destination. Changed mission bytes, corrupted mission/config writes, and late destination links leave a partial destination without a probe plan. This preservation is explicitly documented in diagnostic_mission.py and is not itself an additional defect. Fresh-destination checks prevent reuse. The outside-destination write and standalone success-with-link in finding 4 are separate integrity problems. The normal launcher has reparse checks; their actual Windows behavior was not exercised.

**Commands and actual output.** Commands below were run from the review worktree unless a working directory is specified. All tests use the exported immutable source snapshots so their tempfile fixtures can live under scratchpad-review/tmp without the changed mission helper treating them as part of its own checkout.

```text
git show fb05ff1 > scratchpad-review/commit.diff
# successful; complete diff retained

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/compare_ce.py
PUBLIC ce_probe baseline_count= 54 missing= ['PureWindowsPath', 'datetime', 'hashlib']
PUBLIC diagnostic_mission baseline_count= 17 missing= []
PUBLIC test_ce_probe baseline_count= 50 missing= []
MAX_HOOK_BYTES= 262144
BYTE-COMPARE control files= 9 9 differences= []
BYTE-COMPARE treatment files= 9 9 differences= []

# cwd scratchpad-review/head, TMPDIR=/code/hc-worktrees/taped-light-review-2/scratchpad-review/tmp
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_probe_runtime tests.unit.test_ce_probe tests.unit.test_diagnostic_mission tests.unit.test_flashlight_matrix tests.unit.test_taped_light_probe tests.unit.test_taped_light_report -v
Ran 233 tests in 5.017s
OK

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutations.py
# each runs 137 tests
mutation                              outcome   failures errors
delete_never_executes                  KILLED    6        0
watchdog_does_not_cleanup              KILLED    1        1
census_scans_nothing                   KILLED    3        0
create_attachment_arguments_reversed  KILLED    0        10
timeout_does_not_break                 KILLED    1        0
found_type_guard_disabled             KILLED    3        0
handguard_untracked                    KILLED    4        0
live_after_release_zeroed             KILLED    1        0

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/adversarial.py
# Full JSON rows in adversarial.log; representative literal fields:
partial overall status: host=pending light=qualified pair_counts.qualified=1
wrong spawned host type: host=pending light=qualified pair_counts.qualified=1
control preflight missing: host=qualified integrity=[]
prerequisite wrong fit: host=qualified integrity=[]
can_add false but attach_ok true: host=geometry_missing integrity=[]
negative cleanup counts: host=qualified integrity=[]

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/staging_checks.py
# Full outputs in staging-checks.log:
battleye parent swapped to symlink just before open: ACCEPTED; destination_exists=True; plan_exists=True
FULL STAGE a..b: staged-only-not-launched; plan_exists=True
REDIRECTED WRITE: refused=staged runtime contains a link or special file; outside_dest_written=True; outside_bytes=18
STANDALONE ADMITTED MISSION destination symlink before reread: ACCEPTED; symlinks=['db/types.xml']; marker_exists=True

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/red_regressions.py
Ran 7 tests in 0.002s
FAILED (failures=7)
# Intentional independent red assertions for the remaining report defects.

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/hook_paths.py
# Full JSON rows in hook-paths.log; normal: spawned=24 deleted=24 live_entities=[]
# guard creation refused: spawned=21 deleted=21 live_entities=[]
# variant host creation refused: spawned=20 deleted=20 live_entities=[]
# watchdog: status=partial spawned=5 deleted=5 live_entities=[]
# stuck guard: live_after_release=1; integrity=[live_after_release_nonzero]
# truncated census: census_total=2049; integrity=[census_incomplete]

# In both scratchpad-review/base and scratchpad-review/head with scratch TMPDIR:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
base: Ran 1850 tests in 53.679s; FAILED (failures=1, errors=155, skipped=1)
head: Ran 1991 tests in 84.903s; FAILED (failures=1, errors=155, skipped=1)
full-discovery failure labels identical: True
baseline-only: []
head-only: []
# Deployment fixtures reject the scratch TMPDIR because it is inside a source checkout.
# These failures are reproduced at baseline; they do not establish a new regression.

git diff --exit-code fb05ff1 --
# exit 0, no tracked edits
```

`native-checks.log` retains the source/lint inspection output; `handguard-capture.log` retains the three small captured field records. `classification.log` reruns the original local-capture classification check: hosts=584, slot_host=28, no_slot_host=415, excluded=141; helmet slot hosts=Mich2001Helmet; scope-2 model_empty and scope_below_2 exclusions both 0. That capture was not re-admitted and is not runtime evidence.

No production enablement or native runtime acceptance is established by this review.
