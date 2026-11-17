**Verdict: BLOCK — hc-taped-light-review-004, commit 509d47b36d8a95919576bf7724f6b98a183b8d26 against 82d3042.**

Two new P2 report-evidence defects remain: contradictory proxy rows can qualify, and a per-proxy slot-array cap silently converts omitted evidence into a negative finding. The exact four red assertions from review 003 now pass. All 27 earlier mutants remain killed; 346 focused tests pass. No new P0 or P1 was found.

Only this commit is reviewed. Older revisions were exported as immutable compatibility/test inputs, not reviewed again. Writes were confined to `scratchpad-review/`; no implementation files, git metadata, DayZ, Wine, PowerShell or /mnt/d operations were deliberately changed/run. The supplied native observations were read in place; neither their contents nor a full derived report were copied here. Only aggregate results are recorded. AGENTS.md and the runtime contract were read. `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent. The dispatched Banso CLI guidance was followed without lifecycle commands or additional agents.

**Ranked findings.** Lines refer to the reviewed commit.

1. **P2 — Validate the complete proxy collection before accepting a positive row.** `tools/audit/taped_light_report.py:274`, `:283`, with consumption at `:298`. Put the same exact proxy selection into `proxies` twice: one row has the matching model/slot and `cfg_exists=true`; the other has `cfg_exists=false`, an empty model and no slots. Set `proxy_count=2` and `proxy_scan_complete=true`. Both rows pass `_proxies`; `_model_evidence` returns at the first positive match. The host/light pair becomes **qualified/native_attach_with_proxy_slot** despite contradictory read-back for the same config lookup. This collection cannot come from the hook's exact-selection de-duplication at `tools/setup/taped_light_probe.py:522`; it must be treated as malformed evidence, like other duplicate observation sets.

   The new parser also accepts a `.garbage` instance suffix, or no instance suffix at all, as the documented `proxy:<path>.<nnn>` shape. With otherwise matching config fields these qualify too. No native experiment establishes that those arbitrary selection names denote renderable proxies. This is a fail-closed evidence-validation issue, not a claim that a new native run used those names.

   Minimal fix: index/validate the proxy rows before evaluation, reject duplicate/conflicting identities, and validate a nonempty proxy model reference with the supported numeric instance suffix before stripping it. Keep prefix matching case-insensitive and normalize the path consistently. Malformed evidence must produce pending before any positive row or old selection fallback is used. Add contradictory-duplicate and malformed-name regressions. Actual outputs: `independent-checks.log`, and the two corresponding failing assertions in `remaining-regressions.log`.

2. **P2 — Signal truncation of each proxy's inventorySlot list.** `tools/setup/taped_light_probe.py:488` and `:497`; report-side completeness handling at `tools/audit/taped_light_report.py:284` and `:302`. The hook emits at most eight slot names, but emits neither the original slot count nor a completeness flag for that list. `proxy_scan_complete` only describes the selection scan. With one matching configured proxy and an explicit synthetic nine-element `inventorySlot` array whose ninth entry is `weaponFlashlight`, the hook emits eight unrelated entries and `proxy_scan_complete=true`. The native-call model successfully attaches the variant light; the report still declares **geometry_missing/attached_without_model_selection**. It has mistaken omitted evidence for a complete negative.

   Minimal fix: emit and consume a slot-count/completeness marker per proxy, or propagate any slot-list truncation into a completeness signal the report actually checks. A missing match in truncated data must remain pending. A verified positive match can still stand when only irrelevant trailing data is omitted. Add the nine-entry hook-to-report regression. The fixture is synthetic; this review does not claim an installed vanilla proxy has nine slots. There is no inspected native API bound establishing that eight is exhaustive. Actual output: `HOOK slot cap` in `independent-checks.log`; expected-pending assertion fails in `remaining-regressions.log`.

**Disposition of review 003's three P2 findings.**

| Prior finding | Status | Actual rerun result |
| --- | --- | --- |
| Opened directory can be displaced during the final scan and still yield a plan | FIXED for the reported scan-swap; PARTIAL as a general concurrency guarantee | The original `db` swap now raises `ValueError: staged directory was displaced during the scan: mpmissions/dayzOffline.chernarusplus/db/`; `plan_exists=false`. The ordinary after-open leaf-write residue remains, and unconditional refusal is not guaranteed under a matching replacement (below). |
| Method formatting bypasses expression lint | FIXED for the binary-plus bound and the reported numeric examples; PARTIAL for scope-dependent lint overall | Inline brace, eight-space indent, multiline and CRLF versions of 27 plus operators are all rejected. `row += count`, `row += "n=" + count` and `row = "n=" + (count)` are caught in recognized methods. A `ref`-returning method still escapes duplicate-local checks; it also escaped the parent and is recorded as a residual, not a newly introduced P2. |
| Contradictory found_type versus attach_ok | FIXED | Original control and representative contradictions now produce pending. Focused tests cover base, control and prerequisite-variant contradictions in both directions. |

`new_red_regressions.py` is the previous review's four assertions without changing their expectations: **4 tests, OK**. The older seven red assertions also pass. Old Windows-name, before-open source/destination-link, source-drift, nested invalidation, prerequisite and cleanup mutation cases remain covered by the reruns. A missing sibling light still leaves an independently supported pair usable while its host is pending, as previously permitted.

**Native basis and limits of the proxy join.**

The inspected cache supports a native **slot-location mapping** through `CfgNonAIVehicles`; it does not by itself prove client rendering. In `4_World/Systems/Inventory/AttachmentsOutOfReach.c`, lines 80–95 read the host's configured attachments under CfgVehicles/CfgWeapons/CfgMagazines, line 97 enumerates CfgNonAIVehicles, line 105 reads `inventorySlot`, and line 110 reads `model`. Lines 114–131 examine the host's **view LOD**, remove the model extension, lowercase names, match the model path in a selection, and associate the selection position with the slot ID. This is native script code for attachment reachability/position, not the renderer's C++ implementation.

The proposed exact normalized model-path match is more selective than that script's substring match. A valid same-row config/model/slot join plus successful native attachment/read-back is a reasonable source basis for an attachment-slot geometry candidate. It need not additionally equal the **attached item's** model path: the native script maps the proxy placeholder to a slot without comparing the occupant's model. Therefore a different placeholder model with a genuinely existing matching config entry for the same slot is not automatically an unrelated proxy. A proxy mapped only to another slot does not qualify in the independent check.

A valid positive row can logically survive an incomplete unrelated tail: proving that one mapping exists does not require proving that no other mapping exists. The report intentionally qualifies a known positive with `proxy_count=99, proxy_scan_complete=false`, and a known positive alongside a different cfg-absent proxy. Those outcomes are defensible under that existential rule. They differ from contradictory duplicate identity evidence (finding 1). Without a positive, a truncated selection/proxy list or missing config must remain pending; unmarked slot-array truncation breaks that rule (finding 2).

The new hook calls `Object.GetSelectionList`, not `GetSelectionNames`. `3_Game/Entities/Object.c:382` declares `GetSelectionList(out TStringArray)`; `HasSelection` at :405–416 uses it for selections in the p3d file. That declaration does not document its LOD coverage. The new hook does not establish the view-LOD membership used by AttachmentsOutOfReach. Accordingly, **do not translate this mapping into proof that the host renders the light**. Keep client presentation pending; for stronger geometry evidence, collect the view-LOD selections using the native pattern before native/two-client acceptance. The supplied script cache also does not contain the actual weapon proxy config definitions establishing every `Proxy<basename>` lookup. The hook reads those from the running config, and absence stays pending; the lookup convention still needs the new native probe.

The added API signatures and their call shapes match the cache: `Game.c:449` is `ConfigGetText(string path, out string value)`, :558 is `ConfigGetTextArray(string path, out TStringArray values)`, and :612 is `ConfigIsExisting(string path)`. The hook declares its out values first. `SceneEditorMenu.c:1362/:1385` uses array read followed by scalar-text fallback for inventorySlot; `EntityAI.c:3996` also reads the scalar form. `EnString.c:113/:171/:240/:253` supports Substring/ToLower/IndexOf/LastIndexOf. These checks establish source API availability, not compilation of this revision.

Selection processing is capped at 512 names, unique proxy rows at 24, and slots per row at eight. The first two omissions are represented by `proxy_count` and `proxy_scan_complete`; the third is not. Count can describe only the scanned prefix when total selections exceed 512, but `proxy_scan_complete=false` keeps a negative result pending. De-duplication is exact-case in the producer. Prefix filtering is case-insensitive. The report normalizes model path case, slashes and the .p3d extension; the hook's basename extraction itself assumes forward slashes in selection names.

The full hook rendered from the local native classification has exactly **63,729 bytes**, SHA-256 **16c2a23443936b558bb2ad4a98fd4b17608814cdd237232e8163a0f90c49f1f7**, maximum **8** binary plus operators per statement and no shared-lint findings against **7,190** cached native type names. It has 39 recognized methods. The synthetic CE hook remains at maximum nine and passes default lint. The complexity bound remains an observed successful-source budget, not a universal measured compiler threshold.

The supplied probe-003 observations, consumed in place with this revision's report, give exactly **qualified=0, geometry_missing=415, excluded=141, pending=28**, all 28 host pending reasons `proxy_evidence_missing`. Pair counts are 858 geometry_missing and 28 pending. This confirms that old data is no longer misrepresented as 28 completed geometry negatives. It does not validate the newly emitted proxy fields natively: probe-003 used the older 06e00be hook. Runtime acceptance, beam, switch, removal, persistence and two-client presentation remain pending.

**Remaining lint limitations and the filesystem race.**

Scope-dependent rules still depend on `_FUNCTION` at `tools/setup/probe_runtime.py:160`. It omits the native `ref` return modifier and still requires a method to start a physical line. A `ref array<string> HCReview()` containing two `int sample` declarations returns no lint findings; injected into the otherwise unchanged hook, the actual stager writes a plan with status `staged-only-not-launched`. The same declaration form exists natively at `4_World/Entities/Core/Inherited/ItemOptics.c:577`. The parent 82d3042 also returns `[]` for this input, so this is a remaining pre-existing limitation rather than a new diff regression. Parsing/rejecting unrecognized method bodies is the robust fix. `if (true) row += n` also escapes the optional numeric policy because `_compound_destination` expects a bare destination. Bare-number policy failures alone are not native compiler failures; the successful CE evidence remains authoritative on that distinction. The binary-plus bound now runs outside method recognition and is fixed for these layouts.

The original Linux scan race is fixed: `walk_plain` records scanned root/descendant directory identities and reopens them through no-follow parents for comparison. Ancestor symlinks are refused during the reopen, but ancestor inode identities are not separately retained. This is not an atomic snapshot or a protected namespace.

The documented single-move residue reproduces: a battleye directory moved after opening receives an 18-byte synthetic DLL outside the destination; staging refuses and no plan exists. **The new comment at `tools/setup/diagnostic_mission.py:148` overstates this as an unconditional refusal guarantee.** A second synthetic case moves that directory after opening, puts a fresh ordinary directory under the old name, then supplies a same-byte DLL there after the descriptor write. Staging succeeds: `outside_written=true`, `outside_bytes=18`, `plan_exists=true`, `symlinks=[]`. The final tree is valid; the historical outside write remains invisible to tree validation. This requires a concurrent writer that replaces the path and supplies matching content; it is not a passive one-rename case. `residual_race.py` documents the interleaving.

This is the acknowledged descriptor/rename limitation, not a claim that O_NOFOLLOW can solve concurrent renames. For the current local staging workflow, the honest contract is a stable, trusted destination/ancestor namespace; refusal is assured only for displacements that remain detectable, not for every historical displacement. Minimal documentation fix: remove the unconditional no-plan promise and state this matching-replacement case explicitly. If unconditional confinement/refusal is a required safety boundary, protect the namespace; adding another final scan cannot establish it. Windows launcher checks help validate the current tree but cannot detect an outside copy left behind. No DrvFs/junction behavior was tested.

**Commands and actual output.** Logs retain complete outputs; fixtures are synthetic except the in-place aggregate native report check. Exported snapshots were restored byte-for-byte after mutation runs and then removed to avoid committing duplicate source trees. Recreate them before rerunning snapshot-based scripts:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/export_snapshots.py
base 76678fe exported
parent 82d3042 exported
head 509d47b exported

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/new_red_regressions.py
Ran 4 tests in 0.061s
OK

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/red_regressions.py
Ran 7 tests in 0.001s
OK

# cwd scratchpad-review/head; TMPDIR=/code/hc-worktrees/taped-light-review-4/scratchpad-review/tmp
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_probe_runtime tests.unit.test_ce_probe tests.unit.test_diagnostic_mission tests.unit.test_flashlight_matrix tests.unit.test_taped_light_probe tests.unit.test_taped_light_report -v
Ran 346 tests in 7.415s
OK

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutations.py
# Actual results, 199 tests per mutant, (failures, errors):
delete_never_executes:                 KILLED (12, 0)
watchdog_does_not_cleanup:             KILLED (1, 2)
census_scans_nothing:                  KILLED (4, 0)
create_attachment_arguments_reversed: KILLED (0, 25)
timeout_does_not_break:                KILLED (3, 0)
found_type_guard_disabled:             KILLED (3, 0)
handguard_untracked:                   KILLED (8, 0)
live_after_release_zeroed:             KILLED (2, 0)

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/new_mutations.py
# Actual results, 346 tests per mutant; failure counts, no errors:
complexity_bound_disabled:           KILLED 12
numeric_concat_disabled:             KILLED 25
consecutive_dot_rule_removed:        KILLED 4
ancestor_nofollow_removed:           KILLED 18
leaf_nofollow_removed:               KILLED 2
mission_final_inventory_removed:     KILLED 1
linux_only_requirement_removed:      KILLED 2
host_nested_invalidation_removed:    KILLED 16
probe_nested_invalidation_removed:   KILLED 15
slot_nested_invalidation_removed:    KILLED 8
control_preflight_ignored:           KILLED 1
control_failed_spawn_ignored:        KILLED 1
variant_guard_identity_ignored:      KILLED 7
variant_guard_occupancy_ignored:      KILLED 1
variant_fit_conflict_ignored:         KILLED 2
attach_contradiction_ignored:        KILLED 3
counter_ranges_ignored:              KILLED 2
census_ranges_ignored:               KILLED 2
variant_readback_skipped:            KILLED 4

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/staged_lint_bypass.py
bad_hook_max_statement_plus=27
bad_hook_lint=[...Formula too complex...]
ValueError: generated hook violates native compile rules: ...27 binary '+' operators...
# This old bypass script now exits 1 at the intended refusal.

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/remaining_regressions.py
Ran 4 tests in 0.058s
FAILED (failures=4)
REF_RETURN_BYPASS {'status': 'staged-only-not-launched', 'plan_exists': True, 'extra_method_lint': []}
# Expected-red: conflicting duplicate proxy, malformed proxy suffix, unmarked slot-array cap,
# and pre-existing ref-returning-method lint limitation. No implementation fixes were authorized.

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/independent_checks.py
REPORT conflicting exact proxy readbacks {"verdict":"qualified","reason":"native_attach_with_proxy_slot","model":"proxy_slot"}
REPORT invalid proxy suffix {"verdict":"qualified","reason":"native_attach_with_proxy_slot","model":"proxy_slot"}
HOOK slot cap {"native_config_slots":9,"emitted_slots":8,"proxy_scan_complete":true,"variant_attach_ok":true,"slot_verdict":"geometry_missing","reason":"attached_without_model_selection"}
# Also prints aggregate native counts and full-hook metadata recorded above.

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/deep_checks.py
# Original final db scan-swap: refused; plan_exists=false.
# Original after-open battleye move: refused; outside_written=true; outside_bytes=18; plan_exists=false.
# Original control contradiction: host=pending; UniversalLight=pending.
# Original representative contradiction: host=pending; slot_evidence_invalid.

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/residual_race.py
{"outcome":"staged-only-not-launched","outside_bytes":18,"outside_written":true,"plan_exists":true,"symlinks":[]}

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/compare_ce.py
# Versus 76678fe:
BYTE-COMPARE control files=9 9 differences=[]
BYTE-COMPARE treatment files=9 9 differences=[]

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/compare_ce_parent.py
# Directly versus 82d3042:
BYTE-COMPARE control files=9 9 differences=[]
BYTE-COMPARE treatment files=9 9 differences=[]
```

`staging-checks.log` records before-open link refusals, source/hash drift refusals, a..b/a...b refusal and no outside write for the original before-open redirected-write case. `adversarial.log` records the older report mutation families. `native-checks.log` records cached type/API and generated-hook lint checks. CE comparison is literal bytes of all nine files, including the plan, for the same synthetic paths/time in control and treatment; no JSON normalization was used. The full repository discovery suite was not rerun; the passing evidence here is the stated 346-test focused suite, not a claim of a clean full suite or native acceptance.
