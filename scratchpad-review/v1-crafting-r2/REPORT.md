# Crafting v1 fix round 2 — #17 / #52

Source and offline verification only, 2026-11-17. No DayZ, DayZDiag, Wine,
network, push, signing or engine invocation. Runtime acceptance and production
enablement remain pending. Target load remains the active session's 3–6 players.

## Commit handoff and scope

Worktree Git metadata is read-only for this run. This worker issued no git add,
git rm, git commit or index update. Required repository tests may use their own
disposable temporary Git repositories; worktree metadata remains unchanged. Banso must create the
single follow-up commit; its message is in `.banso-writer/commit-message`:

    Fix V1 crafting coverage, ruined recovery and diagnostic safety (#17 #52)

Base HEAD at entry: `41c0676784b57728535328b674d3da6787c68235`.
The new hash cannot exist until Banso commits after this worker exits.

Changed source: Crafting/{HCSalvageRecipe,HCRecipeRegistration,
HCCraftingNativeChecks,HCItemUtilityDiagnostic}.c, tools/audit/item_utility.py,
tests/fixtures/runtime/crafting-contract.json, tests/unit/{test_v1_crafting,
test_v1_crafting_diagnostic,test_crafting_contract,test_crafting_families,
test_utility_review}.py. The utility_review change only updates its crafting
family quantity-gate expectations for the three added sibling rows.

P1-1: `.banso-brief.md` and the previously tracked
`scratchpad-review/v1-crafting/REPORT.md` are working-tree deletions; their bytes
are preserved as backups under `.banso-writer/`, excluded from the commit by the
writer contract. This records the requested removals without writing the index.
Do not include any untracked `scratchpad-review/` contents in the commit,
including this report and the supplied reviewer scratch copies. Those paths
remain untracked. No `.gitignore` or shared module/config file was changed.
No surviving changed source/fixture/test contains a personal absolute home path.

Read AGENTS.md and docs/RUNTIME_IMPLEMENTATION_CONTRACT.md. The ignored required
specs are absent here; read docs/SPECIFICATION.md and
specs/001-survival-overhaul/{spec,plan,tasks}.md in the parent development checkout
at /code/dayzsa_mods/docs. Work maps to FR-007, AC-006, T016/T017 and CRF-001–007;
NET-001/002/003/007 and engine qualification remain open. Followed the Banso CLI
skill's dispatched-worker guidance, without orchestrator lifecycle commands.

## P1-2 exact installed colour evidence

Inspected `~/.cache/hollow-country/item-review-035-full-20261116/workbook.json`:
all eight exact gloves/hat concrete identities occur under CfgVehicles, inherit
the expected colour base, and are retained. Checked the installed script class
declarations in Clothing/LeatherGloves_ColorBase.c and LeatherHat_ColorBase.c.

Read the installed stored PBO config entries with a local standard-library RAP
reader (`config_evidence.py`, local only). Existing tools/package/pbo.py admits
only canonical authored HC PBOs, not arbitrary native archives, so it was not
misrepresented as an installed-config reader. No native source dump or asset is
included in the deliverable. The committed fixture retains only selected derived
facts, hashes, offsets and material identifiers, not the full config.

| Ref | Installed PBO/config.bin hash | Class body offsets / facts |
| --- | --- | --- |
| L1 | characters_gloves.pbo; 269902f105209baebd30dc56eaad0f98ace55476b422e26a9a43a2368038f51a | LeatherGloves_ColorBase 27079: kits [3], costs [25]. Natural 28155; Beige 28767; Black 29344; Brown 29946. Every concrete has scope 2 and three colour-specific leather_gloves material selections. |
| L2 | characters_headgear.pbo; ae7c5ebe2fd14336bf9d63e93ccb7694f5cdacb3573f1a9549d5b05cdc268a66 | LeatherHat_ColorBase 93014: kits [5,2], costs [30,25]. Natural 94163; Beige 94766; Brown 95359; Black 95927. Every concrete has scope 2 and three colour-specific Hat_Leather material selections. |

Added Black/Brown/Natural for each item at source indices 7–12; medium count 13.
Colours differ visually, with no non-leather substitute in these selections.
Native repair permissions stay separate from material recovery: hats do not
acquire LeatherSewingKit eligibility. All eight small garments use the existing
one-panel rule and actual initializer output/wear assertions.

## P1-3 ruined recovery and exclusions

Eleven registered HC recipes now cover 28 distinct sources and 39 source/recipe
alternatives. All new rows use the original server-authoritative native recipe
completion path, exact source/tool policies, empty loose owned inventory, source
destruction, retained tools, output validation and 10 percent output condition.
Damage bounds are exactly 4..4; ordinary rows remain non-ruined, max damage 3.

| Ruined sibling | Ordinary output | Ruined output | Wear / animation units |
| --- | --- | --- | --- |
| HCRecoverRuinedLargeLeather (all 8 jacket/vest variants) | TannedLeather 2 | TannedLeather 1 | 5 / 2 |
| HCRecoverRuinedBatWood (BaseballBat, XmasBaseballBat) | WoodenStick 2 | WoodenStick 1 | 5 / 2 |
| HCRecoverRuinedNailedBat | WoodenStick 1 and Nail 4 | Nail 1 only | 8 / 3 |

Each ruined material vector is componentwise no greater and strictly lower in
at least one component than the ordinary output, with no substitute material.
Native weapon config B1 proves wood/bat health materials; native
CraftBaseBallBatNailed consumes 12 nails. Inspected all installed DeCraft*.c:
no leather jacket/vest/pants/shirt/gloves/hat or bat-family source appears.
Existing native leather sack/courier/improvised bag recipes remain distinct.
Native DeCraftWoodenCrate max damage 3 remains disjoint from HC's ruined crate.
This is T0 source/config overlap evidence, not engine recipe-discovery proof.

Explicit ruined exclusions are in the executable N1 map and committed fixture:

- Medium leather (13 exact sources): ordinary output is one panel, and the
  existing Configure contract takes integer quantities. Installed
  gear_consumables.pbo/config.bin TannedLeather@30720 (SHA-256
  ed0a211a281fb39a545c9fba18b0881ae8f7e5921aa1775a30989f9a0c343223) has minimum
  quantity 0 and destroy-on-minimum 1. There is no positive lower whole-panel
  yield. Leather material selections do not prove a cloth/rag substitute.
- Barbed bat: ordinary output is one wire unit. Installed
  gear_crafting.pbo/config.bin MetalWire@4323 (SHA-256
  28285d6ab07d1429b1461f494d3994e541f7dce9efb7002503f2972940dfa94d) has stack
  max 1, quantity min 0, destroy-on-minimum 1. No positive lower whole-wire
  yield exists under this contract; wood-for-wire would not be below the
  ordinary material vector.

These are explicit balance/representation exclusions backed by native config
and the existing integer policy, not claims that the engine cannot represent
fractional quantities. Fractional salvage/substitute-material policy is deferred.
Synthetic material budgets remain labelled as design units, never native yields.

## P2 / P3 fixes

- P2-1: new authored-body adapter tests exercise ValidRequest, SafeConcrete,
  ObserveObjects review/scope/ancestry gates, bag-only PollCleanup, Summary,
  EnsureActor identity, Stop partial accounting, end-of-queue stopping, ancestry
  depth, snapshot zones and serialized row limits. Explicit native stubs only;
  no engine behavior or native compilation is inferred.
- P2-2: actual PerformRecipe body runs with non-server/server games. The
  non-server case cannot enter the guard, call native completion, destroy source
  or wear the tool; the server control exercises native completion and release.
- P2-3: exact CfgVehicles N1 map for all HC source/recipe rows, implemented and
  excluded statuses, condition, evidence ID and pending runtime acceptance.
  Every source maps to hc-recovery. Root/name lookalikes remain UNKNOWN.
  Inventory eligibility is still NOT_EVALUATED; no gameplay permission is
  granted by metadata. Empty/nonpositive regular-kit cohorts are tested.
- P2-4: no-mutation scan covers every Crafting/*.c except the diagnostic,
  including future gameplay files and the existing fuel policy. A synthetic new
  file with ObjectDelete is rejected; no extra exception was needed.
- P2-5: after creation gates and before EnsureActor/allocation, either stale raw
  fixture handle calls Stop("stale-fixture-partial"). No handle is overwritten.
- P3-1/2: CT_INT/CT_ARRAY replace numeric config-type literals; Contains uses a
  local alphabet string.
- P3-3: all diagnostic classes are inside #ifdef DIAG_DEVELOPER, following the
  HCInteriorSelfTests developer-only native-probe precedent. No production
  reference to these classes exists. Offline packaging/syntax checks are part
  of the full suite; both native compile variants still need actual testing.
- P3-4: removed tautological tool assertion. Test keeps the actual pair and tool
  health, and checks actual medium Init output type, yield and wear arguments.
- P3-5 RabbitSnare: native CraftRabbitSnare consumes one WoodenStick and destroys
  MetalWire, emits RabbitSnareTrap, and is registered. No DeCraftRabbitSnare or
  explicit dismantle action was found in the inspected Trap_RabbitSnare /
  TrapSpawnBase SetActions chain. Folding/deactivation does not prove recovery.
  Recorded as native-action-qualification-pending mechanical candidate in the
  fixture; no engine/native dismantling acceptance or duplicate recipe added.
- P3-6: durable selected evidence and decisions are now in the committed crafting
  fixture/map rather than solely an ignored experiment or this scratch report.
  A general tracked narrative docs pass remains outside this worker's scope.

## Actual RED → GREEN records

Commands use PYTHONDONTWRITEBYTECODE=1 python3 -m unittest; log files are local
under this report directory. These are actual observed outputs, not anticipated
failures. Existing safety gates needed tests, so review mutations supply their
RED evidence and unmodified source supplies GREEN; no gratuitous production
behavior changes were made merely to produce a failing test.

| Change / command suffix | RED observed before implementation | GREEN observed |
| --- | --- | --- |
| tests.unit.test_v1_crafting (colour regression at that stage) | Ran 1 test; FAILED (failures=6). Each added exact colour: AssertionError: False is not true. red-colours.log | tests.unit.test_v1_crafting tests.unit.test_crafting_families tests.unit.test_crafting_contract: Ran 20 tests; OK. green-colours.log |
| tests.unit.test_crafting_families (new ruined family expectations) | Ran 8 tests; FAILED (failures=11, errors=1); missing sources/Init/registration/cache checks. red-ruined.log | tests.unit.test_crafting_families tests.unit.test_crafting_contract tests.unit.test_crafting_completion: Ran 35 tests; OK. green-ruined.log |
| tests.unit.test_v1_crafting_diagnostic | Ran 24 tests; FAILED (failures=2): missing developer gate; stale handles produced ['actor', 'target', 'tool'] instead of ['stale-fixture-partial']. red-diagnostic.log | Same command: Ran 24 tests; OK. green-diagnostic.log |
| tests.unit.test_v1_crafting.V1DecisionTableTests | Ran 3 tests; FAILED (failures=28, errors=2): hc-recovery != UNKNOWN; hc_decisions missing. red-decisions.log | tests.unit.test_v1_crafting tests.unit.test_item_utility: Ran 32 tests; OK. green-decisions.log |
| tests.unit.test_crafting_contract.CraftingContractTests.test_no_mutation_contract_also_rejects_future_gameplay_files | Ran 1 test; FAILED (failures=1): AssertionError not raised. red-mutation-scan.log | This test plus test_native_server_only_commit_and_explicit_recipe_fields: Ran 2 tests; OK. green-mutation-scan.log |
| crafting quantity-gate integration | First copied baseline: Ran 188 tests; FAILED (failures=1), test_all_six_exact_proposals_pass_quantity_gate omitted new sibling statuses | Updated crafting expectation: Ran 1 test; OK. green-quantity-gate.log. Copied baseline: Ran 188 tests; OK. BASELINE.log |
| tests.unit.test_v1_crafting server-authority case | M14: server-guard removal fails test_non_server_perform_recipe_never_calls_native_or_mutates_ingredients (M14.log) | Unmodified source: Ran 2 tests; OK. green-authority.log; included in final baseline/full suite |

The no-mutation test initially used nested subTest, which captures its assertion
instead of propagating it to assertRaises. Removed that wrapper; the detector
now raises with the offending filename. No gameplay code was changed for it.
The first ruined integration also caught an overbroad expected-count update for
pending scenarios; added three explicit pending ruined scenarios rather than
dropping any existing runtime requirement.

## Mutation replay and validation

Replayed the reviewer's M14, D04, D07–D21 and A03 in disposable source copies,
using the reviewer's twelve-module crafting/audit/syntax subset. Unmodified
baseline: `Ran 188 tests in 14.369s`, `OK`. All 18 mutants were killed, none
survived; every kill contains an actual assertion failure rather than a missing
Git/scratch-copy harness error. Exact outputs are in `{id}.log` and
`mutant-results.json`; `mutate.py` retains the replay method. D07 alone required
updating the old literal-Contains pattern to the new alphabet-Contains spelling;
its semantic mutation is unchanged. All other requested patterns matched.

| Mutant | Result | Killing regression |
| --- | --- | --- |

| M14 | killed | test_non_server_perform_recipe_never_calls_native_or_mutates_ingredients |
| D04 | killed | test_safe_concrete_is_exact_and_unknown_definitions_stay_pending |
| D07 | killed | test_request_identity_charset_size_queue_roots_and_kit_bounds |
| D08 | killed | test_request_identity_charset_size_queue_roots_and_kit_bounds |
| D09 | killed | test_bag_alone_blocks_cleanup_and_releases_no_exclusivity |
| D10 | killed | test_begin_requires_opt_in_isolation_empty_server_and_bounded_queue |
| D11 | killed | test_object_creation_requires_review_scope_ancestry_and_safe_concrete |
| D12 | killed | test_object_creation_requires_review_scope_ancestry_and_safe_concrete |
| D13 | killed | test_metadata_ancestry_limit_reports_incomplete_without_unbounded_walk |
| D14 | killed | test_deletion_request_is_once_and_never_confirmation |
| D15 | killed | test_final_row_stops_and_replay_cannot_emit |
| D16 | killed | test_snapshot_zone_limit_is_exact_and_never_claims_truncated_complete |
| D17 | killed | test_summary_completion_requires_full_queue_and_confirmed_cleanup |
| D18 | killed | test_serialized_row_limit_includes_boundary_and_failed_serialization |
| D19 | killed | test_actor_with_identity_is_rejected_before_bag_creation |
| D20 | killed | test_only_discovered_zero_result_maintenance_can_execute_on_owned_handles |
| D21 | killed | test_stop_records_partial_and_deletes_fixtures_once |
| A03 | killed | test_empty_and_nonpositive_repair_cohorts_are_excluded_from_extension |

BDD command: `python3 -B -m tools.validate.bdd` → `Ran 1300 tests in 129.114s`,
`OK (skipped=1)`, `Bound offline scenarios: 61; runtime acceptance: NOT EXECUTED`.

Runtime command: `python3 -B -m tools.validate.runtime` → status pass, errors [].
This is operator settings admission only, not a game runtime test.

`git diff --check` → exit 0, no output.

`python3 -B -m tools.validate.hygiene` → exit 1 (hygiene.json): exactly five
findings, confined to the two tracked deleted files still listed by the read-only
index, one documentation link inside the supplied review scratch copy, and that
copy's two existing synthetic CE fixture filenames flagged as vanilla-dump paths.
No requested production file was a hygiene finding. This worker cannot make the
checkout CLI green by staging deletions or changing ignore policy because both
are outside this run's allowed edits. After Banso commits the deletions and
excludes scratch, the CLI must be rerun on that clean tree.

Supplemental hygiene of the intended commit contents: called the same
check_repository with its discovery list restricted to existing tracked files,
excluding the explicitly removed .banso/scratch paths; all content/link/license
checks are unchanged. `hygiene-intended-commit.json`: valid true, errors [].
This projection is not presented as the failing checkout CLI having passed.
Personal-home-path scan of surviving changed files: no matches.

Full discovery and final focused assertions: results appended below.

Final full discovery command:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit > scratchpad-review/v1-crafting-r2/full-unit.log 2>&1

Observed: `Ran 2521 tests in 126.824s`, `OK (skipped=1)`.
The initial full invocation imported the old six-proposal expectation before its
update and recorded `Ran 2521 tests in 209.607s`, `FAILED (failures=1, skipped=1)`;
that genuine integration RED is retained in full-unit-initial.log. The final
invocation above includes the corrected expectation. During that invocation,
the small-garment identity assertion was further strengthened to retain the
successful CanDo argument array as well as refused arrays, and the N1 test was
changed to enumerate actual HCSalvageSources instead of just its expected test
cohort. Production source was unchanged. Those final test-only assertions were
also verified directly in final-crafting.log:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v1_crafting tests.unit.test_v1_crafting_diagnostic tests.unit.test_crafting_families tests.unit.test_crafting_contract tests.unit.test_item_utility

Observed: `Ran 77 tests in 6.128s`, `OK`.

Developer diagnostic gating/package regression command:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_package tests.unit.test_script_syntax

Observed: `Ran 30 tests in 1.046s`, `OK (skipped=1)` (package-syntax.log).
The skip is the Windows-only native PowerShell helper execution test on this
Linux host. Installed-interface source checks ran; neither source checks nor
this skipped helper establish native compile success.

## Remaining gates

- Banso must create exactly one commit, stage the two requested artifact
  deletions, exclude every untracked scratch review/report and `.banso-writer/`
  file, then rerun checkout hygiene. This worker cannot supply a new commit hash
  while the index is read-only. No source push is authorized or performed.
- Actual Enforce compilation for Diag and normal PBO/server builds; no game or
  packaging/signing artifact was claimed from offline checks.
- Native inventory/manager discovery, both ingredient orders, same tool identity
  and wear, cancellation, cargo/attachments, failed allocations, condition,
  transfer/death/disconnect/crash and two-client races remain pending.
- Medium ruined panels and barbed ruined wire are deliberate whole-unit
  exclusions; fractional material policy and the RabbitSnare mechanical candidate
  remain traceable deferred work, not accepted engine experiments.
- Diagnostic calls remain explicit, developer-only, empty-server/disposable
  fixture operations; a full native caller/runner, real handle invalidation,
  external timeout enforcement and actual action/repair acceptance remain open.
- Benchmark/load budgets are provisional until measured on the target load.

All requested P1/P2 source and test fixes are implemented. Review findings about
artifact tracking require the orchestrator's permitted commit/index step;
checkout hygiene has not been falsely labelled green. No missing engine
experiment is accepted by this report.
