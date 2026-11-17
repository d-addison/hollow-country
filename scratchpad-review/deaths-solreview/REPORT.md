# Hollow Country #32 adversarial review

**Verdict: MERGE-WITH-FIXES.** Fix the CLI policy reader and include the audit document with its mandatory tests before merging. Also reject the silently ignored CLI option. The production implementation has no verified native-API or scalar-policy defect in this review; native compilation, appearance, crawler behavior and multiplayer replication remain pending. The receipt-window finding below is inherited, and should be addressed without changing absent-option legacy bytes.

## Verified findings, most severe first

### P2 — The documented CLI cannot read the production policy from the checkout

**Location:** `tools/setup/death_selection_probe.py:420`; documented trigger at `docs/INFECTED_DEATHS.md:166`.

With `--selection policy --policy-source mods/HollowCountry/scripts/4_World/Infected/HCInfectedDeathPolicy.c`, `main()` calls the imported `_read()`. That reader goes through `infected_death_probe._safe()` and `diagnostic_mission._safe_path()`, which rejects every file inside the source checkout with `ValueError: mission must be outside source checkout`. This is appropriate for disposable mission inputs, but rejects the authored source file explicitly required by the new instructions. Staging never reaches `generate_probe()` or creates the addon. Relative and absolute forms of the repository policy path both encounter the same check.

**Evidence:** `checks.log` records direct rejection by the actual reader. `review_regressions.py::test_documented_cli_can_read_the_production_policy` reaches the real policy reader through `main()` and errors at line 420; only the synthetic stock/interface input reads are stubbed to obey the scratch-only write restriction. The policy reader itself is not stubbed. `regressions.log` contains the traceback. The shipped CLI test uses a policy outside the checkout under ordinary temporary-directory settings, so it misses this case.

**Minimal fix:** use a bounded, regular-file reader for authored policy source that permits repository files while retaining traversal/symlink/reparse/change checks. Keep the external-mission restriction for mission inputs. Add a CLI regression using the actual repository policy path and synthetic external mission/interfaces.

### P2 — New mandatory tests depend on an audit document excluded from the commit

**Location:** `tests/unit/test_infected_death_selection.py:194` and `:203`; `.gitignore:61`.

Both audit tests unconditionally read `docs/INFECTED_DEATHS.md`. It exists locally, but `git ls-files docs/INFECTED_DEATHS.md` is empty and `git check-ignore -v` identifies `/docs/*` as the matching rule. The file is not among the explicit documentation exceptions. A normal collection of the new source/tests therefore omits their required input; a fresh checkout raises `FileNotFoundError` in both tests and loses the native audit and operating instructions referenced by production source and CLI output.

**Minimal fix:** explicitly include this authored document in the reviewed change, following the repository's documentation allowlist pattern, or put the required audit in an existing tracked documentation destination and update both tests and references. Do not silently skip the tests to hide a missing deliverable. This reviewer did not stage files or change ignore rules.

### P2 — A successful receipt need not contain the claimed post-command observation window (inherited)

**Location:** `tools/setup/death_selection_probe.py:353`; producer cleanup condition at `:791`.

The validator's “real post-command observation window” checks `samples[-1].elapsed - damage_elapsed >= 2`, rather than time since `command_elapsed`. Starting with the valid synthetic policy receipt, moving each command timestamp to `delete_elapsed - 0.01` still returns `death-selection-observations-complete`. The final sample then follows the reported command by only 10 ms. The producer likewise permits cleanup two seconds after damage as soon as a command and a later frame have appeared. It need not observe the selected command for two seconds. Thus a delayed command can be accepted without the observation period suggested by the validator comment.

A second accepted data mutant places the final sample on the command frame, rather than a later frame. All samples can also have `death_processed=0` and pass; this last fact is a limit on the evidence, not independently a proven native defect, since native processing semantics were not executed here.

**Evidence:** `checks.log`; the expected-red `test_policy_receipt_requires_two_seconds_after_the_command` in `regressions.log`. This weakness is present in HEAD and was not introduced by the extension. It cannot establish visual or gameplay acceptance, which the validator correctly leaves false.

**Minimal fix:** for policy-mode evidence, measure the required window from command observation and require a genuinely later final sample frame in both producer and validator. Keep the absent-option legacy bytes unchanged by making new producer behavior conditional on policy mode; retain/document weaker legacy observations separately. If only a post-damage window is intended, describe that narrower guarantee explicitly instead of calling it post-command evidence.

### P3 — `--policy-source` without `--selection policy` is silently ignored

**Location:** `tools/setup/death_selection_probe.py:418`.

The CLI only reads `args.policy_source` inside `if args.selection`. Supplying a policy file without `--selection` therefore stages the legacy `impulse-selection` fixture with no policy file, even though `generate_probe()` deliberately rejects a policy supplied without policy mode. The operator's explicit source argument is lost, and a forced-selection experiment is created instead of the intended policy experiment.

**Evidence:** `checks.log` records `cases=["vanilla", "impulse-selection"]` and `policy_staged=false`; the expected-red CLI exclusivity test fails in `regressions.log`. This isolated CLI test stubs only bounded synthetic input reads because all fixtures must live in scratch.

**Minimal fix:** validate that `--selection policy` and `--policy-source` appear together immediately after argument parsing; reject either unmatched option with a clear parser error. Test both directions at the CLI boundary.

## Native-cache cross-check

Inspected `~/.cache/hollow-country/native-scripts/scripts-1.30.164289` directly. No native source was copied into scratch or committed. Source inspection is not runtime evidence.

- `ZombieBase.c:363`: exact declaration is `bool EvaluateDeathAnimationEx(EntityAI pSource, ZombieHitData data, out int pAnimType, out float pAnimHitDir)`. The new override's names, order, types and `out` modifiers match. The super call passes variables normally; call-site `out` keywords are not required.
- `ZombieBase.c:365–391`: the wrapper returns the delegated evaluator's bool. Vanilla assigns the ammo `doPhxImpulse > 0` result into `pAnimType`, computes direction, optionally applies its own impulse, and returns true. The mod returns that bool unchanged. `EEHitBy` at `:993` passes `m_DeathType` and `m_DamageHitDirection` and ignores the bool. The mod changes only the type after super; it does not suppress vanilla's ammo impulse or replace the command pipeline.
- `DayZInfected.c:29–35`: DEFAULT=0, IMPULSE=1, BACKSTAB=2, NECKSTAB=3. All enum references are qualified correctly.
- `ZombieBase.c:907`: vanilla heavy classification is exactly `hitAnimation > 0 || m_HeavyHitOverride`, matching the policy. `DayZInfected.c:193–202` sets the override for sufficiently large torso/head special-zone shock damage; that helper is called under the `transferShockToDamage == 1` branch at `:144–149`. The new code reads the native flag rather than inventing a second shock threshold.
- `HandleDeath` at `ZombieBase.c:349–361` starts the native command with the selected fields. The type/direction are not additional mod-owned inventory or replicated state.
- **Finishers:** `SetBeingBackstabbed` at `:1065–1087` sets BACKSTAB/NECKSTAB and the finisher flag before the command can start. Vanilla's later death evaluator unconditionally assigns type 0/1; calling super can therefore overwrite the field even for a finisher. The new policy's finisher branch leaves the *post-super* result alone, so it adds no extra finisher rewrite relative to vanilla. Its scalar tests preserving inputs 2/3 should not be mistaken for proof those values survive a vanilla fatal `EEHitBy`. The mod must not skip required vanilla side effects merely to preserve an earlier field value without a separate justified change.
- **Crawlers:** native alive-hit crawl selection is in the other branch of `EEHitBy` (`:998`), with transition handling at `:811–849`; death is handled first in `CommandHandler`. There is no crawler-specific branch in vanilla `EvaluateDeathAnimation`. The policy leaves leg-zone kills unchanged, but it will upgrade a heavy frontal torso/head kill of an already crawling infected. There is no `IsCrawling()` exclusion. That follows the stated scalar rule; whether IMPULSE is valid/looks correct from crawl or during transition remains an engine test, not an offline pass or a demonstrated bug.
- **Server and clients:** `ZombieBase.EEHitByRemote` at `:1014` only delegates; it does not run death evaluation. The new policy therefore adds no client-side recomputation through the remote-hit path. However, `m_DeathType`/direction are not registered net-sync variables in `ZombieBase.Init()` (`:54–57`), and `HandleDeath`/`CommandHandler` themselves have no script-level server guard. Native command replication/callback execution is engine-owned and not visible in this cache. `SetSynchDirty()` alone does not prove animation-type delivery. Server-only correctness is consequently plausible from native usage, **not established**. Require two clients (attacker plus bystander), including observer/relevance transitions, before production enablement; do not add a speculative RPC to fill the evidence gap.
- **Compile-shape checks:** neither new production source contains a ternary or leading `||`/`&&`; exact override-name tests pass against the installed cache. Primitive variable/parameter declarations have no exact identifier collision with native class/enum declarations. Generated guards use the previously accepted single-line shape. These checks are not an Enforce compilation.
- `Qualified()` stays false, admission is cached per process, and the decision log is capped at 16 entries (plus at most one admission diagnostic). The unsafe runtime questions do not become accepted because a marker enables a local experiment. The qualification comment's one-client run is insufficient for replication acceptance; the document correctly also calls for two clients.

## Probe safety, identity and package checks

`review_checks.py` verifies all five generated legacy bundle files, including the manifest, are **byte-identical to HEAD** with identical stock bytes, request, interface bytes and nonce. Hashes and per-file comparisons are in `checks.log`. This is stronger than the shipped legacy test's token checks; no legacy-byte regression was found in the current implementation.

Requests require exact required/optional keys, fixed world/build, a hex stock digest and nonce, finite exact numeric vector components, world-coordinate bounds and a 1–5 m input distance. Spawn profiles and selection are allowlisted strings. Numeric values are rendered numerically rather than concatenated as raw input. Quotes/statements in spawn-profile/selection/vector fields and NaN coordinates are rejected before generation in explicit synthetic checks. `init.c` instrumentation uses the existing bounded stock parser and pins supplied stock bytes; it is not a sandbox for arbitrary operator-supplied source. Optional request text is not injected into `init.c`.

Policy input is deliberately executable authored code. The class/signature substring checks and forbidden-token list are not a general-purpose security sandbox or proof that the selector is correct. File hashes pin exactly the supplied code, and the validator describes its correlations as unauthenticated. No finding here assumes a trusted operator-supplied policy is hostile input.

An independent stored-PBO parser checked every packed entry name, payload length/content, prefix, terminal header and SHA-1 trailer against the policy bundle. All three actual entries pass. No package-format defect was found. Fixed bundle filenames constrain staging paths; staging refuses an existing destination and does not execute anything. Filesystem races against hostile concurrent namespace changes were not established or claimed safe by this review.

Receipt checks do reject wrong nonce/build/world, bundle drift, wrong policy/command type, rear policy selection, unexpected fields, nonfinite numbers, invalid lifecycle ordering, missing cleanup and acceptance claims. They correlate observations to supplied bundle bytes; they cannot authenticate a receipt, prove rendering, or establish replication.

## Mutation results

Every mutant is a complete authored scratch copy under `mutants/`; production sources and tracked tests were not edited. Policy tests execute their restricted scalar translation of the scratch policy; production contract tests read the scratch wrapper. Probe tests import each scratch Python module. Native APIs are never executed.

| Mutant | Focused tests | Result |
| --- | ---: | --- |
| Frontal limit 60 → 90 degrees | 19 | KILLED, 2 failures |
| Ignore finisher flag | 19 | KILLED, 2 failures |
| Ignore ordinary ammo-heavy values | 19 | KILLED, 1 failure |
| Allow rewriting nondefault native types | 19 | KILLED, 2 failures |
| Reverse server guard | 19 | SURVIVED |
| Reverse admission guard | 19 | SURVIVED |
| Invert heavy-override argument at production call | 19 | SURVIVED |
| `surface-only` uses AI-only flags | 28 | KILLED, 1 failure |
| Accept side/rear policy receipts | 28 | KILLED, 2 failures |
| Corrupt each packed entry length by +1 | 28 | SURVIVED |
| Change emitted legacy CE guard bytes | 28 | SURVIVED |

**6 killed / 5 survived.** Detailed counts are in `mutations.json`; each mutant has its own `focused.log`. The CLI staging test is excluded from probe mutant scoring because it independently errors with scratch-local temporary fixtures; the other 28 probe tests have no baseline errors. Survivors are test-coverage gaps, not assertions that those mutations exist in production. Add behavioral wrapper coverage for authority/admission/input forwarding, a parsed PBO round trip, and a pinned full legacy-output comparison. The current shipped syntax/token checks do not establish those contracts.

## Verification record and confinement

- `PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/deaths-solreview/review_checks.py > scratchpad-review/deaths-solreview/checks.log 2>&1` completed successfully. The focused shipped suite ran 57 tests: 56 passed and one errored because the CLI fixture is inside the checkout. `focused.log` contains the exact traceback. Mutation results and the independent package/identity checks are separate from that environment error.
- `PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/deaths-solreview/review_regressions.py > scratchpad-review/deaths-solreview/regressions.log 2>&1` intentionally failed: 3 review regression tests, 2 failures and 1 error, reproducing the findings above. No fixes were applied in this read-only review.
- Full suite ran **once**, with `TMPDIR` set to the absolute `scratchpad-review/deaths-solreview/tmp` directory to honor the write confinement, and the requested command `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit > scratchpad-review/deaths-solreview/full.log 2>&1`. Result: **2,582 tests in 160.219 s; 38 failures, 280 errors, 1 skip; exit 1**. Of 280 error sections, 278 end in checkout-path policy rejections (123 experiment, 112 mission, 40 deployment destination, 3 generated experiment); the other two are a missing synthetic fixture and an unbound result after setup failure. Failures likewise include early-refusal expectations and hooks that never ran. This constrained run is not a clean CI result, and those unrelated failures must not be attributed to #32 without a normal external-temp run. No second full run was made.
- The worktree lacks `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md`. Their parent-checkout versions, plan/tasks, and the worktree runtime interface contract were inspected as design input. Active-session 3–6-player/private-source instructions take precedence over older public-load assumptions. No missing experiment was accepted.
- No DayZ, Wine, network, commits, staging or source fixes were performed. Only scratch artifacts were authored; temporary test output was routed there and bytecode writing disabled. Final read-only git status retains the original source changes plus the new scratch directory. No file was written under `.banso-writer/`, since the explicit scratch-only review scope forbids it. Personal home paths in saved logs are normalized to `~`; native content was not saved.
