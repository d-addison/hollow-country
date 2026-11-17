# Round 11 adversarial re-review — taped-light #56

**Verdict: MERGE** for the report-tooling diff. **No verified defects.** Both r9 P2 findings are fixed. The focused suite, original r9 adversarial cases, and relevant mutation checks pass. The full-suite attempt has a confinement limitation detailed below; it is **not a passing full-suite result**.

Scope: current uncommitted `tools/audit/taped_light_report.py` and `tests/unit/test_taped_light_report.py`, on committed HEAD. Compared with `r9-solreview/REPORT.md` and `r10-fix/REPORT.md`. Synthetic fixtures establish report logic only.

## Findings, most severe first

None. No new false `server_qualified` path was reproduced.

## Required fix verification

| Requirement | Verified result |
| --- | --- |
| r9 P2-1: conflicts survive mismatch/malformed/wrong-class siblings | Fixed. `_proxies()` at lines 602–665 accumulates readable conflicts while scanning past unreadable and legacy-class siblings, then returns the conflict independently of parse status. The original six-order mismatch and malformed regressions pass. Additional tests cover six sibling shapes, six orders and eight attach/prerequisite routes: **288 cases**, all pending with the original conflict scope retained. |
| Conflict precedence before selection and refusal | Fixed. `_implicated()` reads metadata for every parse status; `_model_evidence()` checks implicated conflicts before malformed status and positive selections. `_evaluate_slot()` handles the conflict before native attach outcomes; the no-compatible-slot branch also checks implicated host slots. Positive selection, direct refusal, absent/unmet/satisfied prerequisite evidence, and refused/successful prerequisite variants cannot bypass the conflict. |
| r9 P2-2: spelling-only signature differences | Fixed. Resolution signatures use `_selection_key()` at lines 491–499; model signatures use `_path()` at line 646; config classes use casefold. The original r9 model/resolution regressions pass. A product of selection, model, config-class and resolution spellings gives **162 ordered two-row cases** that collapse to one row and qualify only with native attach evidence. Removing the native UniversalLight row makes all 162 pending. |
| Substantive differences remain conflicts | Pass. Tracked regressions retain different model identities, resolution instance numbers, vertices, exact slot names and slot counts as conflicts. Supplemental tests mix normalized model spellings with changed resolution instances, vertices and vertex availability; both orders remain pending. |
| A: coherent aliases collapse | Pass, including model/resolution/config spelling changes and parsed-row counts. M09 remains killed. |
| B: concrete variants require their own evidence | Pass. Original r9 fixtures keep missing FNX45_arrow, SCARH_Black and Glock19_Tan pending despite base evidence and ancestry/shared-model hints. M07 still survives tracked tests, but independent replay confirms that even its borrowed row is rejected by the spawned-type guard; it does not qualify the variant. |
| C: exact slots and implicated scope only | Pass. Original r9 tests preserve three-reading slot/truncation unions and independent pairs. M03 is killed by the tracked exact-conflict-slot test; `weaponflashlight` does not implicate `weaponFlashlight`. |

A **1,596-case** differential check against committed HEAD enumerated explicit proxy combinations, selection presence and native positive/refusal outcomes. There were **60 pair promotions**, all involving only coherent spellings of the same proxy/config/resolution evidence. No promotion involved absent config evidence, a substantive model change, malformed names, legacy-class siblings or native refusal. This is bounded synthetic coverage, not proof over every possible input. Evidence: `test_supplemental.py`, `supplemental.log`, `differential.json`.

## Remaining generic-malformed case

**Acceptable under adopted rules A/B/C; not a verified defect.** Reproduced with one valid proxy and one unreadable, non-conflicting sibling. `_proxies()` returns malformed with no alias-conflict metadata. A successful native attach stays pending with `proxy_evidence_malformed`, including when a legacy model selection is positive. A typed native refusal on the observed compatible slot remains `geometry_missing` when prerequisite evidence establishes that no unmet rail prerequisite explains it.

That negative conclusion comes from the native refusal, not from the unreadable proxy geometry. Rules A/B/C require coherent collapse, concrete identity and scoped conflict precedence; they do not require an unrelated malformed diagnostic to erase an independently evidenced negative. The stronger precedence for implicated conflicting readings now works. Missing prerequisite evidence and an unmet prerequisite without a resolving variant still return pending. None of these generic-malformed cases becomes `server_qualified`. Actual six-case outputs: `generic-malformed.json`.

## Original r9 scripts and mutations

Copied `r9-solreview/test_adversarial.py` and `mutations.py` unchanged into this directory before execution, because the originals write beside themselves. Their copies import the current worktree source. The original tracked `r9-solreview/counterexamples.json` was not rewritten.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 scratchpad-review/r11-solreview/test_adversarial.py
Ran 8 tests in 0.013s — OK

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r11-solreview/mutations.py
Unmutated baseline: Ran 298 tests in 15.200s — OK
```

The mutation harness excludes the same 18 CLI/stager tests as r9; they are included in the separate 316-test focused run. Mutation failures below are expected injected-fault results, not findings in the current source.

| Mutant | Result | Actual failures |
| --- | --- | --- |
| M01: ignore late proxy rows | KILLED | 28 failures, 3 errors |
| M02: ignore same-class/different-instance conflicts | KILLED | 11 failures, 1 error |
| **M03: casefold implicated slot names** | **KILLED** | **1 failure** |
| M04: overwrite accumulated truncation | KILLED | 2 failures |
| M05: permit mismatched proxy model | KILLED | 6 failures |
| M06: qualify missing native light row | KILLED | 3 failures |
| M07: borrow a base row for a missing concrete variant | SURVIVED, contained | Independent identity guard keeps variant pending |
| **M08: compare config-class identity case-sensitively** | **KILLED** | **10 failures** |
| M09: retain coherent duplicate rows | KILLED | 20 failures |

Replayed the unchanged r9 `check_survivors.py` in scratch as well: both baseline checks pass, M03/M08 fail their independent adversarial checks, and the identity guard passes for baseline and M07. Evidence: `mutation-results.json`, `mutants/*/output.log`, `survivor-results.json`.

## Probe-006 rejoin

Read the existing probe-003 classification and probe-006 observations from `~/.cache/hollow-country/experiments/`; no native process was launched. Joined both committed HEAD and the current source to these same inputs. **Every host and light-pair verdict is unchanged**, not only the aggregate counts.

| Host verdict | Count |
| --- | ---: |
| server_qualified | 26 |
| geometry_missing | 0 |
| not_server_evidencable | 415 |
| excluded | 141 |
| pending | 2 |
| total | 584 |

Pair counts: server_qualified=26, geometry_missing=28, not_server_evidencable=830, pending=2. R12 and Mich2001Helmet remain `pending_client`. Integrity issues are empty; no host has `proxy_alias_conflict`. Global acceptance remains `PENDING`. Input hashes and both summaries: `rejoin.json`.

## Focused and full-suite execution

All review/test writes were confined to this directory. The focused and full suites ran against a byte-identical copy of all 301 tracked non-review files under `source-snapshot/`, with `TMPDIR` set to this directory's `tmp/`. No test assertions or production code were patched. `snapshot-manifest.json` records the copied hashes, verified against the worktree before testing and rechecked afterward. The disposable source copy was then removed to avoid retaining a duplicate repository.

Focused command, run in that snapshot:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_report tests.unit.test_taped_light_probe
Ran 316 tests in 24.124s
OK
```

Full suite executed **once**, in the same snapshot, with output captured at the requested `scratchpad-review/r11-solreview/full.log`:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
Ran 2442 tests in 145.812s
FAILED (failures=1, errors=155, skipped=1)
```

Verified cause: the broader deployment/probe fixtures explicitly reject destinations beneath **any** Git checkout. Although scratch temporary storage was outside the copied source root, the original worktree's `.git` remained an ancestor. The log contains 40 deployment guard errors, one deployment CLI assertion caused by that guard, 114 probe guard errors, and one secondary `UnboundLocalError` after blocked fixture setup. No failure is in the taped-light report/probe suites. `full-summary.json` classifies every failed outcome; this run cannot establish a green full suite under the write confinement. It was not rerun elsewhere or with weakened guards.

Supplemental synthetic suite: **5 tests, OK**, 3.068s. `git diff --check` passes.

## Scope and acceptance limits

No tracked worktree file or original reviewer artifact was changed. Final SHA-256 comparison checked all **424 tracked files** with zero changes; Git status is unchanged from the captured review baseline (`integrity.json`). No commands to mutate the worktree's Git metadata, no DayZ/Wine execution and no network operations were performed. Temporary Git repositories created by existing hygiene tests were synthetic fixtures inside this scratch directory and were cleaned up by those tests. No commit-message file was written outside the authorized scratch scope.

The two required specification paths are absent in this checkout. Read their available counterparts in `/code/dayzsa_mods/docs/`, the related implementation plan and this checkout's runtime contract; active user decisions remain authoritative. Applied the Banso CLI skill's task-contract guidance without lifecycle commands or delegation.

Native compilation, DayZDiag, normal PBO/server testing and required two-client checks remain pending. **MERGE approves this source/report change, not runtime acceptance or production enablement.**
