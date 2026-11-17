# Interior tooling r6 adversarial re-review

Verdict: **MERGE-WITH-FIXES**. Five verified defects remain (four P2, one P3). This is not approval to merge the present diff or enable production behavior.

Reviewed the uncommitted changes to `tools/audit/interior_points.py`, `tools/setup/interior_sampler.py`, and their two unit-test files on top of `9cbef6f`; read `scratchpad-review/sol-r5/REVIEW.md` and `scratchpad-review/r6-fix/REPORT.md`. All references below use the original worktree's line numbers. Everything written by this review is under `scratchpad-review/r6-solreview/`. No tracked files or worktree Git metadata were changed. No DayZ, Wine, network, signing, publishing, or agent delegation was used. The scope files' original hashes still match `before.sha256`.

`docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent in this worktree, as they were in r5. No feature spec/plan/tasks were available here. Read `AGENTS.md` and `docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`; did not fabricate missing requirements or lifecycle acceptance. The Banso CLI skill's dispatched-worker guidance was applied without running lifecycle commands.

## Verified findings, most severe first

### 1. P2 — Player treatment contributors can bypass door-run validation

**Location:** `tools/audit/interior_points.py:350` (skip), `:403` / `:408` (candidate use).

`door_semantics` skips a row when its as-found `player_codes` is absent, before checking `door_run`. `class_candidates` still uses that same row's `open_player_codes` when the player control/entry gate passes. Other rows can establish the global semantics check.

**Reproduction:** Starting from the explicit synthetic `full_census()` fixture, attach valid player open/closed codes and tested controls to all 16 rows. Remove `player_codes` only from the eight tenement rows. In those rows, respectively remove `door_run`, set `restored=0,state="not-restored"`, or set `observed_open=0,state="open-stalled"`. Every variant returns **status `ok`, 2,967 treatment bytes**, `rows_compared=8`, `invalid_rows=0`, `observed=true`. The eight calibration rows supply the global observation while all eight tenement rows contribute treatment without their door evidence being checked.

**Minimal fix:** Validate door evidence for every usable, gated row that can contribute candidates, independently of availability of the paired comparison arrays. Require the selected source's as-found array as well, or make rows missing it ineligible/unknown. A missing paired array must not suppress validation of a contributing row.

Evidence: `adversarial.log`, `player-skip-*-census.json`, `player-skip-*-report.json`; RED test `test_player_contributor_without_closed_codes_still_requires_door_evidence` has three assertion failures.

### 2. P2 — Legacy requested-phase observations still qualify as actual-phase evidence

**Location:** `tools/audit/interior_points.py:330` (accepts five-field door records; no producer/evidence version gate).

The revised hook samples actual phase, but the builder accepts the previous hook's indistinguishable schema-1 evidence. New phase/settle fields are not required. Thus installing the fixed sampler does not invalidate observations produced with the exact r5 state-observation bug.

**Reproduction:** Loaded the authored sampler source directly from `git show 9cbef6f:tools/setup/interior_sampler.py` into an isolated module, rendered its hook, and executed it using the current explicit synthetic requested/actual door model with a stuck close. The old hook reports `opened=observed_open=restored=1,state="done"` and a five-field door record, while the mock reports **actual_open=true, actual_closed=false**. Substituting that emitted `door_run` into all rows of the otherwise valid synthetic census still produces **status `ok`, 2,967 treatment bytes**, `invalid_rows=0`.

This demonstrates a legacy-input acceptance hole, not a claim that a native engine close was observed failing in this review.

**Minimal fix:** Version the actual-phase evidence contract in the generated census and require it in the builder; reject legacy requested-phase runs. Require the new record shape and bounded observation/settle metadata for that version. Update the old five-field synthetic fixtures accordingly. This is input consistency/provenance validation, not cryptographic authentication of arbitrary JSON.

Evidence: `legacy-stalled-close-row.json`, `legacy-stalled-close-accepted-*`, `adversarial.py`; RED test `test_legacy_requested_state_observations_cannot_qualify_actual_phase_evidence` fails.

### 3. P2 — Per-door flags and phases are never reconciled with summary counts

**Location:** `tools/audit/interior_points.py:329`.

The validator only checks that the 5–6 values are finite numbers. It accepts nonbinary lock/open flags, unknown phase codes, and records that contradict the claimed opening count.

**Reproduction:** Keep the valid fixture's summary `count=1,locked=0,opened=observed_open=restored=1,state="done"`. Replace its sole per-door record on all rows with each of:

- `[0,0,0,0,1,1]`: only door already fully open;
- `[0,0,0,1,0,0]`: only door locked;
- `[0,0,0,0,0,99]`: unknown phase;
- `[0,0,0,4,-2,0]`: invalid flags.

All four produce **status `ok`, 2,967 treatment bytes**, `invalid_rows=0`. The first two have no eligible initially closed/unlocked door, yet claim one was opened and restored.

**Minimal fix:** Validate flag/phase domains and the relation between open flag and phase. Reconcile locked/open/ajar/moving summary counts with individual records and ensure the claimed opened count is possible given initially closed, unlocked doors. Record opened door indices if exact reconciliation needs them. Do not merely trust `state="done"` and matching totals.

Evidence: `forged-*-census.json`, `forged-*-report.json`; RED test `test_per_door_flags_and_phases_must_agree_with_the_counts` has four assertion failures.

### 4. P2 — Refusal output can follow a swapped parent into the checkout

**Location:** `tools/audit/interior_points.py:955` and `:978`.

`resolve()`/checkout validation and file creation are separate path traversals. Exclusive creation protects the leaf from replacement, but does not protect parent components from symlink substitution.

**Reproduction:** Exercise the real parser-refusal path (`--radius bad --report <outside-parent>/refusal.json`). Between `_report_path_from` validating the path and the real `_write_refusal`, deterministically replace the outside parent with a symlink into the byte-identical copied source checkout. The CLI returns 1 and **creates `refusal.json` inside that checkout**. The wrapper only schedules the filesystem swap; all validation/creation runs in production code. This requires a concurrent writer able to replace the destination parent. No original tracked file was touched.

Static inside-checkout and `..` destinations are refused. Repeating creation against the existing leaf preserves its bytes: **no overwrite defect was verified**.

**Minimal fix:** Traverse/open the output parent with directory descriptors and refuse symlink/reparse components, then create the leaf relative to that verified descriptor using exclusive creation. Rechecking `resolve()` alone leaves another race.

Evidence: `adversarial.py`, `adversarial-results.json`, `source/review-probe-output/refusal.json`; RED test `test_cli_refusal_cannot_follow_a_swapped_parent_into_the_checkout` fails.

### 5. P3 — Finite numeric extremes still escape refusal reporting

**Location:** `tools/audit/interior_points.py:410`; validation at `:137` / `:139` permits the inputs; exception envelope at `:826` and `:1060` does not catch the overflow.

Catching `OverflowError` in `_number` fixes huge JSON integers. It does not prevent arithmetic on individually finite floats from producing infinity before `round()`.

**Reproduction:** Two separate synthetic census variants: (a) first hit x=`1e308`, first row box_min.x=`-1e308`; (b) first row grid.step=`1e-320`. Each passes the finite-number/positive-step checks, then the real CLI raises **`OverflowError: cannot convert float infinity to integer`**, with **no attached report, no report file, no treatment**.

**Minimal fix:** Bound coordinates/grid step to the sampler's actual output domain and check computed grid coordinates before rounding. Normalize any remaining arithmetic overflow into a report-bearing validation refusal. Add CLI coverage for finite arithmetic overflow, in addition to `10**400`.

Evidence: `numeric-probe.log`, `numeric-results.json`, `finite-overflow/`, `tiny-grid/`; RED test `test_finite_numeric_overflow_is_refused_with_a_report` raises two overflow errors.

## Disposition of the four r5 findings

- **Door-run gating:** ordinary compared-row missing/zero/stalled/not-restored cases are fixed and the new tests pass. Finding 1 leaves a contributing-row bypass; finding 3 leaves contradictory records accepted.
- **Actual door phase:** fixed in the newly generated hook, supported by the authoritative declarations and synthetic delayed/stalled tests. Finding 2 leaves old requested-phase observations admissible. Native behavior remains untested.
- **CLI parse failures:** the reported `--radius oops`/invalid choice/missing-required-option cases now return 1 with `invalid-input` reports at safe destinations. `--help` remains zero. Finding 4 is an additional confinement race.
- **Huge integer overflow:** the reported `10**400` cases are fixed and the focused suite passes. Finding 5 is an additional finite arithmetic path.

One additional probe marks a single failed-restoration row's open control `not-entered`; the global treatment still succeeds with 15 compared rows. That row's candidates become unknown, so it is recorded as context in `adversarial-results.json`, not counted as a separate verified candidate-evidence defect.

## Generated hook / native API audit

Authoritative cache: `~/.cache/hollow-country/native-scripts/scripts-1.30.164289`. Lines below are relative to that root, read directly in this review:

| Declaration | Native file:line |
| --- | --- |
| `bool IsDoorOpen(int index)` — **wanted** phase >0.5 | `3_Game/Entities/Building.c:34` (comment :33) |
| `bool IsDoorOpened(int index)` — actual open target | `3_Game/Entities/Building.c:46` |
| `bool IsDoorOpenedAjar(int index)` — actual ajar target | `3_Game/Entities/Building.c:49` |
| `bool IsDoorClosed(int index)` — actual closed target | `3_Game/Entities/Building.c:52` |
| `int GetDoorCount()` / `bool IsDoorLocked(int index)` | same file :31 / :55 |
| `void OpenDoor(int index)` / `void CloseDoor(int index)` | same file :61 / :64 |
| `vector GetDoorSoundPos(int index)` | same file :73 |
| `RaycastRV(begPos,endPos,out contactPos,out contactDir,out contactComponent,results=NULL,with=NULL,ignore=NULL,sorted=false,ground_only=false,iType=ObjIntersectView,radius=0,flags=NEARESTCONTACT)` | `3_Game/Global/DayZPhysics.c:199` |
| PGFilter getters, `SetFlags(int,int,int)`, `SetCost(PGAreaType,float)` | `3_Game/AI/AIWorld.c:62`–`:67` |
| `bool FindPath(vector,vector,PGFilter,out TVectorArray)` | same file :98 |
| `bool SampleNavmeshPosition(vector,float,PGFilter,out vector)` | same file :122 |
| `CoordToParent(vector)` / `CoordToLocal(vector)` / entity `GetParent()` | `1_Core/proto/EnEntity.c:473` / :499 / :571 |
| `GetPosition()` / `GetOrientation()` / `ClippingInfo(out vector minMax[2])` / `GetType()` | `3_Game/Entities/Object.c:287` / :305 / :358 / :467 |
| `GetAIWorld()` | `3_Game/Global/World.c:116` |
| World/version/position/time queries | `3_Game/Global/Game.c` — exact declarations in `native-audit.log` |
| `CallLater(func,int=0,bool=false,void param1=NULL,...)` | `2_GameLib/tools.c:61` |
| FileExist/OpenFile/CloseFile/FPrintln/MakeDirectory | `1_Core/proto/EnSystem.c:397` / :417 / :443 / :481 / :525 |
| integer/float ToString, AsciiToString, vector.Distance | `1_Core/proto/EnConvert.c:30` / :115 / :44 / :196 |
| Substring/Replace/Length; AbsFloat/Sqrt | `1_Core/proto/EnString.c:113` / :156 / :199; `1_Core/proto/EnMath.c:225` / :305 |

Call signatures match the generated source. No uncached engine API use was verified. Collection methods and casts are native language/core operations; internal `HCProbe*` methods are authored helpers. The default hook has no `IsDoorOpen(...)` call.

`native_audit.py` checked both the default 16-target hook and a 64-target/64-frame-point hook against all **7,190 cached native type names**. Both return `lint_sampler_hook == []`; maximum binary `+` count per statement is **8**. No ternary, leading `||`/`&&`, engine-type identifier, duplicate sibling-scope local, or undeclared-before-call output argument was found. Raycast outputs, navmesh sampled outputs, path array, world/version strings and clipping array are declared before use. Hook bytes/hashes:

- Default: **75,460**, SHA-256 `b539dae598a04e9046b360aeff5e8bb0630f0ba681d4a17b6a258317a2ceee14` (matches writer report).
- Maximum shape: **83,681**, SHA-256 `d86c1e6d26f005b6ae900758c9f637ec7194fafd8f8e093caad50cfd59c7c739`.

Loops are finite/bounded: validated box extents <=500 with fixed positive 1 m grid step; ray descent uses the configured bounded step limit; doors <=64; object lookup <=256; fixed 16/30 attempt loops; open-floor chunk <=100; targets <=64; frame points <=64; diagnostic/collection loops consume bounded arrays. Delay is 30 ticks plus at most 30 settle ticks per transition. The continuation is scheduled once per tick and stops after finite target/phase progress.

The new hook opens only unlocked, actually closed doors (`interior_sampler.py:1446`), tracks every attempted door, closes all attempts at :1558, and observes actual closure at :1572. Unobserved opening skips the open pass and routes through closure (:1496); failed restoration records `not-restored` and prints a warning (:1578). Initially open/ajar/moving doors are untouched. The 64-door cap means doors beyond it are untouched. No lock/unlock, teleport, deletion, or door-blocking call was found. This establishes static control flow and explicit synthetic behavior only; process termination/external interference and native replication/animation/navmesh behavior are not proven.

## Own mutants

Mutants are saved as `M*.py`, loaded in memory with the original module filename/package, and scoped to a targeted existing test. No original source was patched. See `mutants.py`, `mutants.log`, `mutant-results.json`, and each mutant's log.

| Mutant | Behavioral check | Result |
| --- | --- | --- |
| M1: ignore invalid-door-row gate | one bad compared row must refuse | **Killed**, 1 assertion failure |
| M2: ignore restored/opened mismatch | contradictory restoration must refuse | **Killed**, 1 assertion failure |
| M3: use wanted open phase | slow door must wait for actual opening | **Killed**, 1 assertion failure |
| M4: omit CloseDoor | opened door must end actually closed | **Killed**, 1 assertion failure |
| M5: accept integer overflow in `_number` | huge integer must be rejected | **Killed**, 1 assertion failure |
| M6: parser exits before report | invalid CLI values must report | **Killed**, 5 `SystemExit(2)` errors across subtests |
| M7: ignore unobserved opening | stalled open must skip open pass and close | **Killed**, 1 assertion failure |

**7 killed, 0 survived.** M6 errors are the deliberately restored parser behavior, not an import/setup failure. These tests discriminate the fixes they cover; they do not cover the additional acceptance paths above.

## Test commands and actual outcomes

The write restriction and tools' refusal to output within their own checkout conflict with running the tests directly with an in-checkout TMPDIR. Initial direct focused/full attempts using a scratch TMPDIR were interrupted after those environment refusals; `focused.log` / `full.log` retain the partial output and are not pass results.

To preserve every original byte, copied 305 tracked files into `source/` (excluding Git metadata and Banso session data), with SHA-256 inventory `source-manifest.json`. The copied subject files are byte-identical to the originals. Ran the requested commands from that source copy with temporary files in its sibling `tmp/`, all within this review directory:

```sh
TMPDIR="$PWD/../tmp" PYTHONPATH="$PWD/../guard" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_interior_points tests.unit.test_interior_sampler
# Ran 302 tests in 85.001s — OK

TMPDIR="$PWD/../tmp" PYTHONPATH="$PWD/../guard" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
# Ran 2663 tests in 182.429s
# FAILED (failures=1, errors=155, skipped=36)
```

`guard/sitecustomize.py` prevents mutating Git subprocesses (including synthetic fixture repositories), DayZ/Wine/network, and file-content writes outside this review directory. The full suite completed once in this arrangement; it is **not green**. Failure accounting: 40 deployment errors reject destinations beneath an ancestor `.git`; 114 probe/startup errors reject paths beneath any Git checkout; one secondary startup test `UnboundLocalError` follows the path-refusal subtests; the single deployment CLI assertion expects success but receives that same confinement refusal. Thirty-five hygiene tests skip because their setup invokes `git init`, which this review must not run; the remaining skip is the existing native Windows PowerShell test. These are limits of the authorized environment, not verified defects in the subject. Logs: `focused-snapshot.log`, `full-snapshot.log`.

Own behavioral RED command:

```sh
TMPDIR="$PWD/scratchpad-review/r6-solreview/tmp" PYTHONPATH="$PWD/scratchpad-review/r6-solreview/guard" PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r6-solreview/test_review_regressions.py
# Ran 6 tests in 0.042s; FAILED (failures=9, errors=2)
```

The valid baseline passes. The other five test methods expose the five findings, including their subcases. Evidence is retained in `review-red.log`. No fix was made, per the read-only contract.

DayZDiag compilation, normal PBO/server testing, actual phase/navmesh timing, target-load budgets, and any applicable two-client acceptance remain **pending**. No engine experiment is marked accepted by this review.
