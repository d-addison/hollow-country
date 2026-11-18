# Deterministic checks for Hollow Country

Status: design plus a first implemented slice (2026-11-18). Each check here runs
offline, is deterministic and needs only the standard library. A green offline
check is not DayZ evidence. Runtime acceptance still needs DayZDiag, a normal
PBO/server boot and, where AGENTS.md requires it, two clients.

## 1. Why we need this

The bugs that cost the most time came from a small number of repeated shapes.
None of them failed a unit test, and most were invisible until a native boot or
a player hit them:

| # | Observed failure | Shape |
|---|---|---|
| A | Search Interior spins, then nothing (owner, 2026-11-18) | The client predicts the action. On the server, `HCSearchHouses.Begin` / `Gate` / `CanContinue` return early with no log line and no message, and the pilot `HCInteriorModule.BeginSearch/SearchGate` does the same. |
| B | `HCBuildIdentity.Matches` hard-pins one build string | An identity gate refuses silently when the world or build differs. |
| C | Launcher does not list the mod; server shows "Choose action" | The packaging output did not match what the launcher expects: VDF tag `Mod` (aa93e42), `meta.cpp` publishedid (3ab98d0), and the anims PBO dropped from the bundle (#140). |
| D | Native compile/boot stops | Ordering, ownership and binding traps (see the list after this table). |
| E | A feature is silently off, or modules disagree | An admission flag or `IsEnabled` false skips `OnStart` with no line. Shared distances differ per module (120 / 200 / 300 m). |

The compile/boot traps under D:

- boot 021: an earlier modded link calls a method that only a later link adds
- boot 022: `new` on a weak member
- boot 023: unbounded `Substring`
- boot 026: a method named like vanilla `Slot`
- earlier boots: layer visibility, ternary, duplicate locals

## 2. Taxonomy: bug class to check

| Class | Offline deterministic check (all together about 30 s) | Optional runtime self-check / receipt |
|---|---|---|
| Compile traps (D) | **`tools/validate/enforce_lint.py` rules HC-E001..E007 and HC-L001 (implemented)**, plus the existing `test_script_syntax`, `test_enforce_locals` and `test_script_identifiers` | DayZDiag compile: `0 SCRIPT (E)` in the boot log (already captured by native boot runs) |
| Silent server refusal (A, B) | **HC-S001 / HC-S002 (implemented, baselined)** | Each refusal emits `[HC <Module>] refuse reason=<code> actor=<id>`, rate-limited. The admin debug snapshot counts refusals per reason. |
| Predicted action with no player feedback (A) | **HC-S003 (implemented, baselined)** | Server `MessageStatus` on the refusal path. Two-client check for the networked ones. |
| Feature silently off (E) | WP-5: a readiness-line registry test. Every `HCModule` subclass has one `[HC <Name>] ready` / `[HC <Name>] off reason=` print, and `HCServer` logs the modules it skips. | Boot log grep: one line per registered module, no gaps. |
| Identity gate (B) | WP-4: lint rule HC-S004 flags string equality against a literal build/world id in a gate. The convention is tolerant matching, or log the mismatch once. | `[HC Identity] build=<x> world=<y> accepted=<bool> reason=` |
| Packaging (C) | WP-1: `tools/validate/package_manifest.py` (section 5) | Launcher/Workshop observation stays manual. |
| Settings drift (E) | WP-6: `tools/validate/settings_consistency.py` (section 6) | `[HC Settings] effective <key>=<value>` for shared keys at boot |

## 3. Per-module conventions

These are what the silent-refusal rules enforce. New code follows them now. The
legacy code stays in the baseline until its WP converts it.

1. **Reason codes, not bare bools.** A gate returns an `int` reason, with
   `HCRefusal.NONE == 0`. A `bool Gate()` wrapper may stay, but it delegates to
   `int GateReason(...)`. Commit points (`Begin*`, `Start*`, `Commit*`,
   `Grant*`, `Claim*`, `OnStart`, `On*Server`) never `return;` from a branch
   without one of these:
   - a log call
   - a `reason =` assignment (or an out-param)
   - a player message
   - a call that owns the refusal
2. **Predicted actions report refusals.** A client-predicted `Action*Base`
   subclass whose `ActionCondition` branches on `IsServer/IsClient` must, on its
   server path, call a single helper `HCRefusalReport(player, module, reason)`
   (WP-2, 3_Game Core). It does two things:
   - a rate-limited `Print` (one per actor+reason per 10 s, using the existing
     Core budget/unit-budget style, with no timers)
   - `player.MessageStatus(<short text>)`, so the progress ring never ends
     without feedback
3. **One readiness line per feature.** `OnStart` ends with exactly one of
   `[HC <Name>] ready ...` or `[HC <Name>] off reason=<code>`. `HCServer` prints
   `[HC Server] skip <Name> reason=disabled` for modules where `IsEnabled` is
   false. Today they are skipped silently.
4. **Identity is tolerant or explicit.** A build or world identity compare
   either accepts a declared family (prefix/major) or logs the mismatch once,
   with both values. It never silently refuses.
5. **Harness code is exempt.** Classes or paths matching
   `NativeChecks|SelfTest|Diagnostic|Probe|Audit|Experiment|Census|Sampler` are
   test harnesses, not gameplay gates, and are outside the S rules.

## 4. Project-wide static linter (implemented slice)

- **Files:**
  - `tools/validate/enforce_source.py`: the structural model. It blanks comments,
    strings and preprocessor lines while keeping offsets, and finds classes,
    fields, methods, typedefs and layers.
  - `tools/validate/enforce_lint.py`: the rules, baseline and CLI.
  - `tools/validate/enforce_lint_baseline.json`: the reviewed exceptions.
  - `tests/unit/test_enforce_lint.py`: the tests.
- **Speed and modes.** It parses 260 files, 816 classes and 3109 methods in
  about 0.5 s and lints in about 1.3 s.
  - Pinned mode (`--no-native`, used by CI and the tree test) uses
    `probe_runtime.ENGINE_TYPE_NAMES` plus a pinned layer table.
  - Native mode reads the local engine-script cache
    (`HC_NATIVE_SCRIPTS` or `~/.cache/hollow-country/native-scripts/...`) when
    it is present. On the current tree both modes give the same 152 findings.

| Rule | Catches | Source of the shape |
|---|---|---|
| HC-E001 | ternary `?:` | earlier native compile rejects |
| HC-E002 | type used in a lower layer than the one that defines it | layer visibility |
| HC-E003 | `new` assigned to a weak (non-ref/autoptr) member | boot 022, `HCCellarSampler.m_Instance` |
| HC-E004 | `new` inserted into an array/set/map whose element type is not `ref` | same ownership trap in collections |
| HC-E005 | an earlier modded link calls a method only a later link declares (load order = mod, then path) | boot 021, `HCHordeMigration` → `HCVarietyWalkerHerd` |
| HC-E006 | `Substring` without a `Length()` bound or a checked `IndexOf` | boot 023, `DisabledXmlRoot` |
| HC-E007 | a method named like a visible type and called unqualified | boot 026, `HCXGrudge.Slot` |
| HC-L001 | `Print(variable)` logs `string name = '...'` instead of the text; print an expression such as `"" + line` | boot 032 RPT, `[HC XAI] live` and `[HC InfectedLOD] stats` lines; member access (`obj.m_X`) and `PrintToRPT`/`ErrorEx` are not observed and not flagged |
| HC-S001 | silent early `return;` in a server commit point | issue A |
| HC-S002 | silent `return false;` in a gate | issue A/B |
| HC-S003 | predicted action whose server path never messages the player | issue A |

- **Historical validation** (run with `--root` on archived pre-fix trees):
  - `6daeb18^`: E005 at `HCHordeMigration.c:156`, E003 at
    `HCCellarSampler.c:312`, E006 at `HCAtmosphereQualification.c:151/156`
  - `acab865^`: E007 at `HCXDefence.c:77`
- **Baseline.** Identity is `(rule, path, symbol, normalized line text)`. Line
  numbers are recorded but are not part of identity.
  - A new finding fails.
  - A baselined finding that disappears also fails as stale, so the baseline
    only ratchets down.
  - E-rules (other than the four E006 Substring cases) may not be baselined.
    `test_the_compile_trap_rules_have_no_baselined_exceptions` enforces this.
- **Existing sibling detectors** (`test_script_syntax`, `test_enforce_locals`,
  `test_script_identifiers`, `probe_runtime.lint_hook`) stay where they are. WP-7
  moves them onto `enforce_source` so there is one lexer.

## 5. Package-manifest check (design, WP-1)

`tools/validate/package_manifest.py` describes the expected layout once and
checks three places against it:

1. the built folder from `tools/package/pbo.py` / `Build-Sign-Verify.ps1`
2. the `tools/setup/local_test_session.py` staging
3. `tools/setup/friend_bundle.py` output

It checks:

- **PBOs:**
  - `@HollowCountry/addons/hollowcountry.pbo` and `hollowcountryanims.pbo`
    (#140 dropped the latter)
  - `@HollowCountryExpansionAI/addons/hollowcountryexpansionai.pbo`
- **Mod files:**
  - `mod.cpp` and `meta.cpp` at each mod root, never inside a PBO
  - `meta.cpp` publishedid is `3841628320` / `3841637854`
- **Signatures and keys:**
  - one `.bisign` per PBO, carrying the same key name
  - `keys/*.bikey` present
  - no private key anywhere
- **Workshop VDF:** `tags` contains `Mod`, `publishedfileid` matches `meta.cpp`,
  and `contentfolder` is the staged folder.

The check reads files only. It does not run Steam or DayZ. For a check with no
build output present, the test builds synthetic folders and runs the check on
them. For the real tree, it runs on whatever `pbo`/staging output a test already
builds into a temp directory.

## 6. Settings cross-consistency (design, WP-6)

Some distances are shared across modules, and each module has its own default.
Examples:

| Module | Setting | Default |
|---|---|---|
| `HCInfectedLODStore` | `MinSpawnDistance` | 120 |
| `HCXAIData` | `MinPlayerDistance` | 200 |
| `HCXAIData` | `CacheClearRadius` | 300 |
| `HCSettlementDecay` | far-distance bounds | 300..1200 |

These may be correct as separate concepts. Nothing checks that they agree where
they mean the same thing (observer veto, minimum spawn distance from any player).
WP-6 does three things:

- adds a small registry, `tools/validate/shared_settings.json`, that maps a
  concept to its `(file, class, field)` list and a relation: `equal`, `<=` or
  `range`
- has `settings_consistency.py` parse the defaults with `enforce_source`
- checks the registry against `config/hollow-country-settings.json` and the
  `tools/validate/runtime.py` LIMITS

A deliberate difference is recorded in the registry with a reason.

## 7. Where checks plug in

- **unittest discovery:** `tests/unit/test_enforce_lint.py` is picked up by
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit`. It
  therefore already runs in the CI `offline` job (`.github/workflows/static.yml`,
  step "TDD behavior suites") in pinned mode.
- **CLI:**
  - `python3 -B -m tools.validate.enforce_lint --no-native` prints per-rule
    totals and new/stale findings, and exits 1 on any new or stale finding.
    `--json` gives machine output.
  - `--all` also prints the baselined findings.
  - `--write-baseline "<review note>"` rewrites the baseline. It is for
    reviewed legacy cases only.
- **pre-push (suggested, not installed):** `python3 -B -m tools.validate.enforce_lint --no-native && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit`
- **CI:** add an explicit step, "Enforce static lint", to the `offline` job,
  `python3 -B -m tools.validate.enforce_lint --no-native`. The output is then
  readable without the unittest noise. This is WP-0 and needs a workflow edit
  outside this brief's scope.

## 8. Work packages (ordered by payoff)

| WP | Payoff | Owned files | Done when |
|---|---|---|---|
| WP-0 | Lint gate visible in CI (this slice is already in discovery) | `.github/workflows/static.yml` | the step is green on main |
| WP-1 | Packaging regressions (C) never reach the owner again | `tools/validate/package_manifest.py`, `tests/unit/test_package_manifest.py` | a synthetic missing anims PBO, missing `meta.cpp`, missing `Mod` tag or missing bisign each fail; real staging passes |
| WP-2 | The search spin (A) and every predicted action explain refusals | `mods/HollowCountry/scripts/3_Game/Core/HCRefusal.c` (enum + `HCRefusalReport`), `4_World/Loot/HCSearchHouses.c`, `4_World/Interiors/HCInteriorModule.c`, the six S003 actions; baseline entries removed | S001/S002/S003 entries for those files gone from the baseline; DayZDiag shows `[HC Search] refuse reason=` plus a client message |
| WP-3 | Real Substring risk | `HCEventNativeObserver.c:343` (LastIndexOf may be -1) and the three other E006 entries | E006 baseline empty |
| WP-4 | Identity gate (B) | `HCBuildIdentity.c`, new rule HC-S004 in `enforce_lint.py`, its test | a literal build compare without a log is flagged; Matches logs the mismatch once |
| WP-5 | Silent feature-off (E) | `3_Game/Core/HCServer.c` skip line, readiness lint rule HC-S005, test | every `HCModule` has one ready/off line; skipped modules are logged |
| WP-6 | Settings drift (E) | `tools/validate/shared_settings.json`, `tools/validate/settings_consistency.py`, its test | registry covers observer/spawn distances; deliberate differences carry reasons |
| WP-7 | One lexer | `tests/unit/test_script_syntax.py`, `test_enforce_locals.py`, `test_script_identifiers.py` moved onto `enforce_source` | same findings, one parser |
| WP-8 | Burn down S001/S002 in the remaining modules | per-module source owners | baseline ratchets to zero, module by module |

## 9. Limits

- The lint is a structural model, not the Enforce compiler. A rule that misses
  a shape is fixed by adding a fixture first.
- Call resolution for S003 reachability is name-based (depth 6, names declared
  by 3 or fewer classes). The S rules are heuristics with a reviewed baseline.
  They are not proof that a path reports.
- The modded-link order assumption is mod load order, then case-insensitive
  path. It matches the observed boot 021 failure and the compiling
  Weather/Atmosphere pair. A native compile remains the authority.

## 10. GitHub #161: optional CE composition (offline)

Spec: admit the bundle's own registered CE folders for optional weapon generation
and installation; name and refuse unknown folders (including unknown
`hollow-country*` names). Stock and every registered types file retain class
ownership, including case aliases. Pack installation is sequential and rollback
is last installed first, restoring exact bytes before bundle rollback.

Plan/tasks: add explicit synthetic behavioral fixtures, record RED, share the
registration/class checks, update the friend runbook, then run focused tests,
hygiene and full discovery. Local Banso spec/plan/tasks are under
`.banso/specs/161-optional-ce/`. The two specification paths referenced by
AGENTS.md are absent in this checkout. `banso status --output json` could not
resolve its configured read-only layout; no acceptance gate was advanced.

Actual RED, before implementation:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_optional_ce_composition -v
ValueError: existing CE extensions need explicit operator reconciliation
Ran 4 tests in 1.056s
FAILED (errors=23)
```

The synthetic fixture installs base, travel, living-pack and loot-boost layers
through real receipted installers. It exercises each pack alone and both orders,
all stock/base/travel/living types collision locations, unknown-folder errors at
both generate and install, and byte-exact pack then bundle rollback. It uses
invented mod PBOs/classes and tiny XML, never an installed DayZ mission.

Additional packaging RED, before adding the shared helper to the bundle allowlist:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_friend_bundle.FriendBundleTests.test_bundle_ships_shared_ce_guard_without_requiring_optional_weapon_tools -v
AssertionError: 'tools/package/ce_extensions.py' not found in [exported files]
Ran 1 test in 0.071s
FAILED (failures=1)
```

The assertion above abbreviates only the exported file list. The isolated
subprocess check now passes without access to the private tools checkout.
Folder names come from the writers' constants, with strict file-declaration
validation; no prefix wildcard admits arbitrary folders. Every registered types
file is read with the existing path/regular-file checks, and collisions are
rechecked immediately before installation writes.

GREEN:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_optional_ce_composition -v
Ran 4 tests in 1.621s
OK
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_friend_bundle.FriendBundleTests.test_bundle_ships_shared_ce_guard_without_requiring_optional_weapon_tools -v
Ran 1 test in 0.192s
OK
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_snafu_optional tests.unit.test_tactical_flava_optional tests.unit.test_economy_contract tests.unit.test_v2_optional_overlays tests.unit.test_optional_ce_composition tests.unit.test_friend_bundle -v
Ran 190 tests in 26.097s
OK
python3 -B -m tools.validate.hygiene
"valid": true
```

These are offline packaging results. DayZDiag, normal PBO/server testing,
two-client behavior and 3–6-player budget measurements remain pending. No
network, Windows or DayZ commands, commits, staging or pushes were performed.

Full discovery GREEN:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
Ran 5605 tests in 535.713s
OK (skipped=1, expected failures=3)
```

That discovery recorded one skipped check and three expected failures; the
groups null-context failure is now resolved by hardening (offline only).
The explicit banned-text scan found no pack
names or IDs in `mods/`, `mission/` or `config/`. `git diff --check` passed.

Discovery metadata identifies the skip as
`test_package.PackageBehavior.test_native_smoke_verified_copy_rejects_drift_and_overwrite`
(Windows-only helper execution). The two remaining expected failures are
`test_v1_combined_flags.CombinedWorkTests.test_all_modules_tick_within_shared_work_budget`
and `test_v1_combined_flags.CombinedWorkTests.test_stop_removes_queued_interior_updates_as_well_as_core_tick`.
