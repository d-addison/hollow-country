# Static wiring audit

Run against the release checkout before building:

```sh
python3 -B -m tools.validate.wiring_audit
python3 -B -m tools.validate.wiring_audit --json
```

Exit **0** means no new findings, **1** means findings need resolution, and **2**
means an input or parser failure. JSON mode emits one object, including on input
failure. Findings include check, class/key/path, source file, line, explanation and
`new`. The summary includes total/new counts for every check and class-index coverage.
This is source evidence, not native compile, CE behavior, readiness, or gameplay
acceptance. Acceptance still requires one server and at most one client.

| Check | Evidence required / finding |
| --- | --- |
| W001 | Config class lacks a statically resolved production creation route. Routes include positive CE types, event children, spawnable attachments/cargo, enabled object-spawner layers, generated infected CE substitutions, class values flowing to CreateObject*/SpawnEntity*/CreateInInventory, or ammo descriptors flowing to native damage calls. Diagnostic strings, config queries and unused catalogues do not count. Admin-only routes are identified separately. |
| W001b | Public indexed class has nominal zero in every authored HC types row. This older census remains advisory triage; W009 is the mandatory shipped-row check. |
| W002 | Authored mission/profile file has no consumer or shipping reference. Being shipped does not prove runtime consumption. |
| W003 | Registered key lacks a resolved getter-key, owner field or typed receiver read. HCAdd's declared owner takes precedence over the shared settings mirror. Methods returning another settings DTO connect wrapper owners to that DTO. Same-named fields, including `Enabled`, cannot satisfy another owner's key. Unresolved receiver matches remain findings. |
| W004 | Script class has no reference outside its definition file; engine callbacks and local helpers require review. |
| W005 | HCModule lacks construction/registration, or shared readiness capture/report wiring is incomplete. |
| W006 | Reserved RPC has missing sender/receiver endpoints. Syntactic endpoints do not prove installed listeners or delivery. |
| W007 | Authored CE type is absent from the shared config index. Missing external indexes are coverage debt, not proven invalid classes. |
| W008 | Literal creation argument is absent from that same class index. |
| W009 | Shipped fragment row has nominal zero without an exact deliberate exception, min greater than nominal, or previously positive vanilla/pack supply has neither an effective shipped row nor another creation route. |
| W010 | Portable installer/tool transitive local import or literal repository data dependency is absent from the friend bundle. |

W009 and W010 are always enabled, ignore general allowlists, cannot be baselined,
and always fail while findings remain. A baseline containing either ID is an input
error. Other checks can be configured in `config/wiring-audit.json`.

## Spawn evidence and limits

W001 parses CE XML rather than searching its prose. Map layers must be enabled in
`config/map-overlays/profile.json`; their composition expansion uses the packaging
module. Native `Objects` JSON must have a gameplay configuration registration.
Dynamic JSON fields/lists require a read in a spawning consumer and a matching
class argument or selected list member. Arbitrary class strings in diagnostics,
reference documents and unused catalogues provide no route.

The bounded string-flow pass follows literals, local assignments, simple string
returns and factory parameters to a creation call. Class-qualified method names
resolve before unique short names. Instance methods are potential engine/module
roots; static helpers require callers. The production and admin lanes are separate.
This is deliberately a conservative syntactic analysis: conditions, dynamic dispatch,
reflection, complex expressions, array aliases and full engine callback reachability
remain unproven. A finding means no route was resolved, not that no engine route can
exist. CfgAmmo damage descriptors are native damage effects rather than inventory
entities. The flow pass follows argument four of `ProcessDirectDamage` and
`CloseCombatDamage`, including class-qualified string constants. The inspected
native `DayZPlayerMeleeFightLogic_LightHeavy.DummyHitSelector` out-ammo callback
also feeds `CloseCombatDamage` (native script lines 673-699). Arbitrary out
parameters and config-query strings do not count. Native `Object.c:1130-1138`
defines the fourth direct-damage argument as the ammo damage descriptor.

Infected substitutions use `infected_variety.POLICY` and its actual pure
`substitute(stock, stock, policy)` transform against the approved stock events.
The transform checks its pinned stock hash, donor availability, positive shares
and conserved child budgets before the resulting CE children count as routes.
A disabled policy contributes no substituted routes. The installer invokes this
production transform by default; merely mentioning a variant in JSON does not
establish a route. No HC variant class names are hardcoded in the audit.

At this checkout, `HC_ZmbM_Sitter` has a source route through Variety's selected
`bodyClass`, `HCLODMaterialize(type, ...)`, and `CreateObjectEx(type, ...)`. Its admin
helper and diagnostic mentions alone do not establish that route. None of these
source facts proves that a sitter actually spawned or that readiness counters move.

W003 resolves receivers per method, keeping local symbols and DTO field types
separate. It excludes schema/default restoration and metadata checks. It does not
execute Enforce or treat a write as a read. Object container keys are represented by
their registered child keys. Ambiguous receiver types do not count as resolved reads.

## W009: no silently zeroed items

The stock input is a read-only vanilla Chernarus mission in the approved cache. Its
default is `~/.cache/hollow-country/wine-server-20261116/mpmissions/dayzOffline.chernarusplus`.
Supply another stock snapshot under the checkout or approved cache with
`--vanilla-mission PATH`, or configure `vanilla_mission`. Missing inputs fail with
exit 2; an HC-installed economy core is refused. Installed friend mission/profile
bytes are never used as bundle provenance.

The audit runs the pure row pipeline used by packaging, in memory:

- Stock types remain effective unless a generated/authored row replaces them; a
  missing HC override alone does not mean vanilla supply was removed.
- Firearms use `selected_roster` and `roster_items`, including datamined firearms;
  authored CE owners are excluded exactly as `economy.generate` excludes them.
- The contextual economy's usage additions retain stock quantities. Datamined
  non-weapon supply uses `supply_rows` and `type_rows` with the build's floor policy.
- Every committed HC XML document whose root is `types` is included.
- Both optional weapon-pack generators use their actual `_scaled_entries` and
  `_new_type` row transforms and default abundance multiplier. No verification
  report is fabricated and no Workshop files are read.
- `loot_boost.scale_types` applies the shipped multiplier and firearms exemptions.
  Floor retagging does not change quantities. This checkout contains no
  `military_loot.py`; native military quantity policy lives in the firearms roster.

Findings show class, source, previous vanilla/pack nominal (or `unknown`) and the
reason the row is invalid/missing. A minimum above nominal cannot be exempted.
Generator input budgets that the firearm build refuses are surfaced as W009 rather
than silently normalized by this audit. The audit examines configured pack rows,
not installation entitlement, verification results or runtime CE eligibility.

`config/zeroed-items.json` maps **exact class names** to one-line deliberate reasons.
The seed contains exactly the 24 nominal-zero authored rows at the fix-round HEAD:
23 Expansion vehicle entities, each checked against an exact `events.xml` child,
and Cannabis, deliberately excluded as a plant entity rather than inventory loot.
Vehicle spawning and horticulture behavior remain unverified. These exceptions do
not exempt future classes. Both formerly zeroed pack magazine rows now pass the
mandatory shipped-row check without adding exceptions.

## W010: portable bundle closure

The shipped set comes from `friend_bundle.BUNDLE_TOOLS`, `SETUP_TOOLS`, explicit
portable helper plan entries, authored mission data, and map-overlay JSON. Starting
with every shipped Python tool, AST import discovery traverses all local `tools.*`
imports, including function-local imports and imports of modules already missing
from the bundle. Each missing dependency edge is reported at its importing source.

Repository data discovery handles full literal JSON/XML paths, constant Path joins,
and `with_name` defaults. Only repository source files count as repository data;
absent generated/operator input paths (such as the explicitly optional CE coverage
sampler result) are not fabricated as shipped artifacts. Dynamic paths and runtime
plugin imports require separate review. Diagnostic/points CLI branches in a shipped
module are included in closure because the tool itself ships. The audit never runs
an installer, builds a bundle or writes to the installed mission.

At the r11 starting checkout the previously reported bundle dependency gaps are
resolved: W010 reports zero missing edges. This worker did not change the bundle
catalogue or relax closure checks.

## Class-index coverage and baseline

Config parsing/inheritance reuse `tools.audit.pbo_config`. `class_sources` supports
plain config, rap, JSON class tables, and the primitive-only local census pickle.
Inputs are bounded to 64 MiB and must resolve within the checkout or approved cache;
symlink escapes are refused. No config dumps, game assets or Workshop code ship.

The current optional vanilla index covers CfgVehicles/CfgWeapons/CfgMagazines,
not CfgAmmo. Fifteen declared dependencies lack class indexes. The existing W007
baseline retains 118 unresolved candidates, including Expansion classes; it is not
proof of class validity or native acceptance. Additional native cache gaps must be
reviewed individually before adding an exact baseline entry with a nonempty reason.

```sh
python3 -B -m tools.validate.wiring_audit --update-baseline
```

This now **only prunes resolved existing entries**. It never auto-accepts new
findings. Identity remains `(id, subject, file)` so line movement is quiet.
Round r11 adds only the five explicitly reviewed source-local helper entries
listed below; no new class-index gaps are accepted. Existing intentional
source-locality entries remain review debt.

## Round r11 result (2026-11-20)

Before: **472 total / 16 new**. After: **462 total / 1 new**; exit **1**.
The requested zero-new end state is **not yet reached** because the remaining
HC43 binding belongs to another worker's provider file.

| Check | Before total / new | After total / new |
| --- | ---: | ---: |
| W001 | 8 / 8 | 0 / 0 |
| W003 | 1 / 1 | 0 / 0 |
| W004 | 340 / 7 | 339 / 1 |
| W009 | 0 / 0 | 0 / 0 |
| W010 | 0 / 0 | 0 / 0 |

W001 now resolves all four melee damage descriptors and all four newly flagged
CE infected classes through production routes. `WildlifeProviders.TargetPairsEnabled`
already has runtime reads (contact sweeps/recording); W003 sees them. Provider
validation now explicitly rejects unsupported `config.Version` before registry
range validation, making the schema decision a real resolved consumer.

Removed `HCEventBriefing`: an uncalled string formatter with no presentation,
notification or environmental clue consumer. No event lifecycle or gameplay
provider depended on it. Removed `HCTapedHelmetQualification`: an unconstructed
duplicate of the shared `HCTapedLightV1Qualification` wearable adapter. Live held
mount actions already construct the shared adapter, whose exact helmet branch
checks `HCTapedWearableCatalog.Admitted()`. No mount route was disabled.

Five exact W004 baseline additions document actual same-file consumers:

- `HCPresentationTuningServer`: MissionServer start/connect/finish callbacks.
- `HCXAIFortification`: HCXAIAdapter lifecycle and HCXAISiteDirector spawn callback.
- `HCXAIFortificationSite`: the fortification service's Admit/Step queue DTO.
- `HCXAIFortificationState`: the service's load/save persistence DTO.
- `HCTapedLightV1Qualification`: the live taped-light runtime's shared adapter,
  now source-local after removal of its duplicate helmet wrapper.

Nine resolved prior baseline entries were pruned. The baseline has 461 entries,
all with reasons; W009/W010 remain mandatory and unbaselinable. No new allowlists,
zeroed-item exceptions, settings keys or module slots were added.

### Integration still needed from other owners

**HC43 remains NEW W004, deliberately unbaselined.** `mission/hollow-country/ai/sites.json`
contains an authored `HC43` block; `HCWorldData.c` declares the intended shared DTO.
`HCXAISitePolicy` in `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIData.c`
has no `HC43` field. The provider owner must bind `ref HC43ContentManifest HC43`
and consume/validate the manifest in its locality/content selection or receipt
path, or explicitly replace that authored contract with its current equivalent.
Adding a field alone establishes decoding, not selection or native eligibility.
This worker cannot edit the HCX owner's file or reference HCX classes from base HC.
The source comment now records the missing binding honestly.

**Retire the legacy `EnableMealBuffs` key through settings ownership.** Meal heat
hooks are already retired by HC-2/#150. The live V2 summary no longer reads/logs
a fake preference and the non-module receipt says `MealBuffs=retired`. The
settings owner must remove the key from `shared_settings.json`, regenerate the
compiled registry through `settings_consistency`'s render path, and remove its
HCSettings DTO field, missing-field default restoration and effective-value log.
Check shipped settings JSON for stale entries as part of that owner's change.
W003 still sees HCSettings' own effective-value log, so zero findings do not prove
this legacy key has been removed. No meal feature was newly disabled here.

Validation tails:

```text
enforce_lint: pass findings=1 new=0 stale=0 native=yes
enforce_perf: pass findings=65 new=0
```

Python AST parsing and `git diff --check` pass. No existing unit tests target
`wiring_audit.py`; no unit tests, Enforce translators or engine harnesses were
added or run. Native compile/boot is reserved for the lead, and native damage,
shove, CE spawning, helmet geometry, persistence and one-server/one-client
behavior remain unproven.

Suggested README/MODULE_STATUS line: “Static wiring audit resolves native melee
ammo and generated CE variant routes; W001/W003/W009/W010 have no new findings.
HC43 provider binding remains open; legacy meal-buff setting retirement needs
settings integration. Native compile/boot and one-client gameplay remain pending.”
