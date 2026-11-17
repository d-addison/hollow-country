# Round 9 adversarial review — taped-light #56

Two verified P2 defects; no P0/P1 finding. Review of the current uncommitted diff and `scratchpad-review/r9-fix/REPORT.md`. Findings use current source line numbers. All fixtures below are explicit, synthetic JSON observations. They establish report behavior only.

## Findings, most severe first

1. **P2 — Parser error exits discard detected conflicts and can restore `server_qualified`.** `tools/audit/taped_light_report.py:646` (also `:628`, `:632`, `:828`, `:1099`). Start with two universal-light proxy aliases: one config exists and lists `weaponFlashlight`; the other reports that config absent. Alone, the host and pair correctly stay pending. Add an unrelated legacy whole-path config-class row (`cfg_class="Proxy/dz/other/legacy_proxy"`) and retain an observed positive native slot selection. `_proxies()` detects the original conflict, then returns only `("mismatch",)`. `_implicated()` and the host lose the conflict; `_model_evidence()` takes the selection route. **Host, pair, and slot become `server_qualified`, with no integrity issues and no `proxy_alias_conflict`.** All six permutations reproduce this. An unreadable sibling likewise replaces the conflict with `("malformed",)`; with native refusals, all six permutations produce host/pair `geometry_missing` instead of pending.

   **Minimal fix:** preserve conflict metadata independently of overall parse status, continue collecting readable conflicting rows despite bad siblings, and apply implicated-conflict precedence before selection and refusal branches. Keep the host's sibling-scoped `proxy_alias_conflict` reason. Add mixed-status permutations; do not fix this by invalidating every independent pair indiscriminately.

   Evidence: `test_adversarial.py::test_conflict_survives_unrelated_legacy_name_mismatch_in_every_order`, `::test_conflict_survives_an_unreadable_sibling_in_every_order`; actual failures in `adversarial.log`; compact before/after outputs in `counterexamples.json`. Global `acceptance` remains `PENDING`; the defect is false Tier S qualification and loss of pending evidence.

2. **P2 — Equivalent proxy-path spellings are falsely classified as conflicts, violating rule A.** `tools/audit/taped_light_report.py:635` (raw resolution signature also originates at `:491`). Identity and config-class spelling are normalized, but `lookup` compares the raw model path and raw resolution-selection text. Two copies with equivalent model paths (`\\dz\\weapons\\attachments\\light\\weaponlight_universal.p3d` versus `/DZ/WEAPONS/ATTACHMENTS/LIGHT/WEAPONLIGHT_UNIVERSAL.P3D`) each qualify separately; combining them produces zero usable rows, `proxy_alias_conflict`, and pending. Changing only the resolution proxy selection's case/slashes has the same result. Both orders fail. These copies contain no changed slot membership, config-existence answer, model identity, vertex, or instance number.

   **Minimal fix:** normalize model paths and proxy-name spellings in the comparison signature, preserving instance numbers, exact slot names, vertices, and substantive differences; retain raw diagnostics. Add coherent aliases that vary model and resolution path spelling as well as config-class spelling, and assert one evidence row plus unchanged qualification.

   Evidence: `test_adversarial.py::test_coherent_model_path_spellings_collapse`, `::test_resolution_proxy_spelling_alone_collapses`. Each test first verifies that each copy alone is `server_qualified`, then fails on their combination. Actual output: `adversarial.log`.

## Prior findings and owner rules

| Check | Observed result |
| --- | --- |
| Prior P2-1: conflict outranks refusal | Fixed for readable, correctly named rows by `_evaluate_slot()` at `:914` and the no-compatible-slot guard at `:1013`. Mixed parser-status exits remain defective: finding 1. |
| Prior P2-2: unrelated conflicts preserve independent pairs | Fixed for normal parseable aliases: conflict unions at `:621`, removal of conflicting rows at `:648`, host reason at `:1099`, sibling scope at `:1021`. Both original reviewer regressions and the new writer tests pass. |
| Prior P2-3: exact slot membership | Fixed at `:837`, `:842`, `:843`; no casefold in the inventory-slot join. Scratch checks also confirm that conflict slots named `weaponflashlight` do not implicate exact native `weaponFlashlight`. |
| Prior P2-4: malformed spawn diagnostic | Fixed at `:766`: reject non-dicts before membership tests. Original reviewer regression passes; the new writer test exercises null, scalar, list, and mistyped objects without changing pair verdicts. |
| A: coherent alias collapse | Selection spelling and config-class casing alone collapse; duplicate-row mutant M09 is killed. Model/resolution spellings remain defective: finding 2. |
| B: concrete variants need their own native rows | Pass. `build_report()` indexes exact concrete class names at `:1219`, joins each name separately at `:1226`, and `_evaluate_host()` checks row identity and spawned type. Scratch fixtures leave FNX45_arrow, SCARH_Black, and Glock19_Tan pending without their own rows, despite a qualified base and supplied ancestry/shared-model hints. |
| C: exact slots and scoped conflicts | Pass for readable canonical-class evidence. Six permutations of three distinct conflicting readings union all slots and preserve the truncated-copy `all` flag. Unrelated and case-changed slots leave the independent pair qualified while the host stays pending. Finding 1 identifies the loss of this metadata on other parser exits. |

No missing-host or missing-light native evidence path was found that grants qualification. Empty observed host lists stay pending. `_accepted()` requires observed successful attachment/readback plus model evidence; the legacy selection route also requires native rows. The report's global `acceptance` and all unobserved axes remain pending. This review does not grant runtime acceptance or production enablement.

## Actual test runs

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_report tests.unit.test_taped_light_probe
Ran 304 tests in 16.446s
OK

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
Ran 2430 tests in 190.499s
OK (skipped=1)

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 scratchpad-review/r8-sol-review/test_review_regressions.py
Ran 6 tests in 0.002s
OK

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 scratchpad-review/r9-solreview/test_adversarial.py
Ran 8 tests
FAILED (failures=16)
```

The last run deliberately records the defects without implementing a fix: six legacy-mismatch permutations, six unreadable-sibling permutations, two model-path orders, and two resolution-path orders. The other four test methods pass. Full outputs: `targeted.log`, `full.log`, `prior-regressions.log`, `adversarial.log`. `git diff --check` passes.

## Independent report mutations

`PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r9-solreview/mutations.py`

Each subprocess imports exactly one scratch copy of `tools/audit/taped_light_report.py`, then runs the tracked report/probe tests. The 18 CLI/stager tests are excluded from these mutation subprocesses because they require filesystem destinations outside the checkout; both complete requested suites ran separately above. **Unmutated baseline: 286 tests, OK. Nine independently selected report mutants: six killed, three survived.** Mutation definitions, exact failures, and per-mutant logs are retained in `mutations.py`, `mutation-results.json`, and `mutants/<id>/output.log`.

| ID | Injected fault | Tracked tests |
| --- | --- | --- |
| M01 | Ignore proxy rows after the second; hide later contradictions | KILLED, 8 failures |
| M02 | Ignore different-instance conflicts for one config class | KILLED, 10 failures |
| M03 | Casefold implicated conflict-slot names, widening their scope | SURVIVED, 286 tests OK |
| M04 | Replace accumulated truncation with the last copy's truncation | KILLED, 1 failure |
| M05 | Allow mismatched proxy model paths to qualify | KILLED, 6 failures |
| M06 | Qualify a missing native per-light observation | KILLED, 3 failures |
| M07 | Supply another host's row for a missing concrete variant | SURVIVED, 286 tests OK; independent identity guard still makes the variant pending |
| M08 | Compare config-class spellings case-sensitively in alias identity | SURVIVED, 286 tests OK |
| M09 | Keep coherent aliases as duplicate evidence rows | KILLED, 3 failures |

`check_survivors.py` differentiates the survivors. Current source passes the added exact-conflict-slot and config-class-spelling tests; M03 and M08 fail them. These are verified coverage gaps for currently correct behavior. M07 remains pending under both current source and mutant because the existing row-identity check rejects borrowed evidence; its survival does not demonstrate unsafe inheritance. See `survivors.log` and `survivor-results.json`.

The new tests exercise actual parser results and report verdicts: notably M09 is killed by the new parsed-row-count assertion. I also independently reran the writer harness's three prior probe faults against scratch copies (Q08/Q09/Q10): distinct-object identity reduced to non-nullness, omitted variant bone refresh, and omitted immediate control release. **All three are KILLED, each with one failure in its corresponding new/strengthened test (286 tests per run).** Actual results: `probe-mutation-results.json`, `probe-mutants.log`, and `mutants/Q08..Q10/output.txt`. Together with M09, this independently confirms that all four prior P3 fixture weaknesses now discriminate their original faults. This checks the discriminating fixtures, not engine behavior.

## Scope and provenance

No tracked file or git metadata was modified. No DayZ, Wine, or network commands were run. All reviewer-authored artifacts are under `scratchpad-review/r9-solreview/`. Git status retains the original four tracked modifications and adds only this scratch directory beyond the pre-existing writer scratch directory.

Read AGENTS.md, the runtime contract, the prior review, the writer report, the live source/tests, and their diff. The two AGENTS specification paths are absent from this checkout, and no alternate `spec.md`, `plan.md`, or `tasks.md` was found. The supplied saved diff under `/tmp` is also absent; the live uncommitted diff is the reviewed artifact. The Banso CLI skill's dispatched-worker guidance was applied; no lifecycle command or delegation was used.

Real native compile, DayZDiag, normal PBO/server testing, and required two-client checks remain pending. No production acceptance follows from these offline results.

**Verdict: MERGE-WITH-FIXES**
