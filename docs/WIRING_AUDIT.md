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
  Floor retagging does not change quantities. The shared military budgets live in
  `tools/package/military_loot.py` (applied to the firearms roster by
  `tools/package/firearms.py`); the audit does not import that module itself.

Findings show class, source, previous vanilla/pack nominal (or `unknown`) and the
reason the row is invalid/missing. A minimum above nominal cannot be exempted.
Generator input budgets that the firearm build refuses are surfaced as W009 rather
than silently normalized by this audit. The audit examines configured pack rows,
not installation entitlement, verification results or runtime CE eligibility.

`config/zeroed-items.json` maps **exact class names** to one-line deliberate reasons.
The file holds 21 keys: 20 Expansion vehicle entities reserved for native vehicle
events, and Cannabis, deliberately excluded as a plant entity rather than inventory loot.
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

W010 reports zero missing edges on the current tree; the bundle catalogue and closure
checks are not relaxed.

## Class-index coverage and baseline

Config parsing/inheritance reuse `tools.audit.pbo_config`. `class_sources` supports
plain config, rap, JSON class tables, and the primitive-only local census pickle.
Inputs are bounded to 64 MiB and must resolve within the checkout or approved cache;
symlink escapes are refused. No config dumps, game assets or Workshop code ship.

The class index is built by `tools.validate.class_index` (see `docs/tools/CLASS_INDEX.md`)
and consumed through the `class-index` source format: class names, parents and declared
scope of CfgVehicles, CfgWeapons, CfgMagazines and CfgAmmo from the vanilla base and DLC
folders and every declared Workshop dependency. When the index covers vanilla and every
declared dependency of the current manifest, a W007/W008 finding means the declared stack
does not define the class; with any gap the finding keeps the "absence is not proof" wording
and the coverage note names the gap. W001b skips a class whose nominal-0 state is explained by
a statically resolved production creation route or by `crafted="1"` on every authored row.

```sh
python3 -B -m tools.validate.wiring_audit --update-baseline
```

This now **only prunes resolved existing entries**. It never auto-accepts new
findings. Identity remains `(id, subject, file)` so line movement is quiet.
The committed baseline is empty; any entry added later needs a reviewed reason, and
no class-index gap is accepted.

## Current result (dev at 2d2c075c, 2026-11-22)

`python3 -B -m tools.validate.wiring_audit` exits **0** with every check W001 to W010
at 0 total and 0 new findings; `tools/validate/wiring_audit_baseline.json` is empty
(`"findings": []`); a baseline row whose finding disappears is reported as stale and
pruned by `--update-baseline`. W009 and W010 stay mandatory and unbaselinable.

Coverage debt is stated, not hidden: the run notes that Workshop class-index coverage is
incomplete on this host (22 declared dependencies lack a local cache), so W007/W008 keep
the "absence is not proof" wording. The run measured 1,382 production creation routes
(0 admin-only), 1,314 shipped fragment rows against 2,382 stock rows for W009, and 43
transitive installer modules for W010.

Companion gates on the same commit: `enforce_lint` reports `findings=0 new=0 stale=0
native=yes` with an empty baseline, and `enforce_perf` reports `findings=23 new=0
stale=0` (23 reviewed rows in `tools/validate/enforce_perf_baseline.json`). These are
source-level results, below the compile gate and boot evidence; they do not establish
CE spawning, native damage, geometry, persistence or one-server/one-client behaviour.

Items from earlier rounds, as they stand in the source:

- **HC43 binding is closed for decoding and selection.** `HCXAISitePolicy` declares
  `ref HC43ContentManifest HC43`, validates it (schema, caps, role and locality
  cross-checks) and binds the authored content into site and locality selection, with a
  `[HC Expansion AI] HC43 content bound=...` receipt. Native eligibility, actor
  admission and in-game behaviour remain unverified. One comment in `HCWorldData.c`
  still says the provider binding is pending; it is stale.
- **`EnableMealBuffs` is retired.** `HCMealBuffs.c` keeps the retirement (HC-2/#150) and
  `HCSettings.c` ignores the legacy key through `HCRetiredKey` (it has no DTO field and no
  registry row and logs `[HC Settings] retired key ignored` when an old file carries it);
  no meal feature reads it.
- **Unit tests exist.** `tests/unit/test_wiring_audit.py` covers the audit; run it with
  `python3 -B -m unittest tests.unit.test_wiring_audit` when `wiring_audit.py` changes.
