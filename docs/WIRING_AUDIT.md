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
| W001 | Config class lacks a statically resolved production creation route. Routes include positive CE types, event children, spawnable attachments/cargo, enabled object-spawner layers, or class values flowing to CreateObject*/SpawnEntity*/CreateInInventory. Diagnostic strings, config queries and unused catalogues do not count. Admin-only routes are identified separately. |
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
exist. CfgAmmo damage descriptors may be native damage effects rather than inventory
entities; their W001 findings require that distinction to be reviewed.

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
not exempt future classes or the two newly detected zeroed pack magazines.

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

The lead must extend `BUNDLE_TOOLS` with these existing package entries:

```text
pbo.py
ce_coverage.py
interior_templates.py
interior_catalog.py
search_context.py
essential_routes.json
interior_prop_boxes.json
```

The lead must also ship these paths explicitly (the package catalogue cannot place
files in `tools/audit`, `tools/setup`, or `config`):

```text
tools/audit/interior_points.py
tools/setup/interior_sampler.py
tools/setup/ce_probe.py
tools/setup/diagnostic_mission.py
tools/setup/probe_runtime.py
config/loot-dispositions.json
```

That is 13 unique missing files. The detailed dependency-edge list below is the
source of truth; several importers need the same missing file. Adding all these
files requires rerunning closure against the resulting bundle catalogue.

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
findings. Identity remains `(id, subject, file)` so line movement is quiet. The fix
round adds no baseline acceptances: there are no new genuine class-index gaps.
Existing intentional source-locality entries remain existing review debt.

No Enforce source changed. There are no existing unit tests for this new Python
module; no new unit tests, Enforce translator or engine harness were added. Native
compile/boot and one-server/one-client behavior remain for the lead.

## Fix-round result (2026-11-20)

Before: **469 total / 4 new**. After: **494 total / 29 new**; exit **1**.

| Check | Total | New |
| --- | ---: | ---: |
| W001 | 4 | 4 |
| W001b | 1 | 0 |
| W002 | 0 | 0 |
| W003 | 2 | 2 |
| W004 | 345 | 3 |
| W005 | 1 | 0 |
| W006 | 3 | 0 |
| W007 | 118 | 0 |
| W008 | 0 | 0 |
| W009 | 2 | 2 |
| W010 | 18 | 18 |

Baseline: 465 entries, zero stale entries, no new acceptances and no W009/W010 entries.
W009: 2,382 retained stock rows and 1,336 fragment rows inspected.
W010: 32 transitive installer modules inspected; 18 missing edges / 13 unique files.

Every new finding follows. Ammo descriptors require native damage-route review;
source-local classes and unread settings require their owning module review.

| Check | Subject | Source | Explanation |
| --- | --- | --- | --- |
| W001 | `HCMeleeChip` | `mods/HollowCountry/config.cpp:1299` | No statically resolved production creation route |
| W001 | `HCMeleeCripple` | `mods/HollowCountry/config.cpp:1286` | No statically resolved production creation route |
| W001 | `HCMeleeExecute` | `mods/HollowCountry/config.cpp:1273` | No statically resolved production creation route |
| W001 | `HCMeleeShove` | `mods/HollowCountry/config.cpp:1272` | No statically resolved production creation route |
| W003 | `WildlifeProviders.TargetPairsEnabled` | `mods/HollowCountry/scripts/3_Game/HCSettings.c:292` | Registered key has no resolved getter-key, member or owning-class field read |
| W003 | `WildlifeProviders.Version` | `mods/HollowCountry/scripts/3_Game/HCSettings.c:280` | Registered key has no resolved getter-key, member or owning-class field read; ambiguous receiver matches require review |
| W004 | `HC43ContentManifest` | `mods/HollowCountry/scripts/3_Game/World/HCWorldData.c:264` | No reference outside definition file (engine/config callbacks may be intentional) |
| W004 | `HCEventBriefing` | `mods/HollowCountry/scripts/4_World/Events/HCEventBriefing.c:4` | No reference outside definition file (engine/config callbacks may be intentional) |
| W004 | `HCTapedHelmetQualification` | `mods/HollowCountry/scripts/4_World/Survival/HCTapedHelmetMounts.c:83` | No reference outside definition file (engine/config callbacks may be intentional) |
| W009 | `TF_Mag_AKM_PMAG30Rnd_Banana` | `tools/package/tactical_flava_allowlist.json:227` | previous nominal=0; shipped nominal=0 min=0; zeroed spawnable has no exact reason in config/zeroed-items.json |
| W009 | `TF_Mag_SCAR_H_20Rnd_Shd` | `tools/package/tactical_flava_allowlist.json:679` | previous nominal=0; shipped nominal=0 min=0; zeroed spawnable has no exact reason in config/zeroed-items.json |
| W010 | `config/loot-dispositions.json` | `tools/package/datamined_items.py:23` | Install-time repository data is absent from bundle |
| W010 | `tools/audit/interior_points.py` | `tools/package/interior_templates.py:35` | Transitive install-time local import is absent from bundle |
| W010 | `tools/audit/interior_points.py` | `tools/package/loot_boost.py:1091` | Transitive install-time local import is absent from bundle |
| W010 | `tools/audit/interior_points.py` | `tools/package/search_context.py:17` | Transitive install-time local import is absent from bundle |
| W010 | `tools/audit/interior_points.py` | `tools/setup/interior_sampler.py:52` | Transitive install-time local import is absent from bundle |
| W010 | `tools/package/ce_coverage.py` | `tools/package/loot_boost.py:1126` | Transitive install-time local import is absent from bundle |
| W010 | `tools/package/essential_routes.json` | `tools/package/economy.py:492` | Install-time repository data is absent from bundle |
| W010 | `tools/package/interior_catalog.py` | `tools/package/interior_templates.py:36` | Transitive install-time local import is absent from bundle |
| W010 | `tools/package/interior_prop_boxes.json` | `tools/package/interior_templates.py:1261` | Install-time repository data is absent from bundle |
| W010 | `tools/package/interior_templates.py` | `tools/package/loot_boost.py:1060` | Transitive install-time local import is absent from bundle |
| W010 | `tools/package/pbo.py` | `tools/package/overlay_remove.py:97` | Transitive install-time local import is absent from bundle |
| W010 | `tools/package/search_context.py` | `tools/package/interior_templates.py:1026` | Transitive install-time local import is absent from bundle |
| W010 | `tools/setup/ce_probe.py` | `tools/setup/interior_sampler.py:45` | Transitive install-time local import is absent from bundle |
| W010 | `tools/setup/diagnostic_mission.py` | `tools/setup/ce_probe.py:28` | Transitive install-time local import is absent from bundle |
| W010 | `tools/setup/diagnostic_mission.py` | `tools/setup/probe_runtime.py:25` | Transitive install-time local import is absent from bundle |
| W010 | `tools/setup/interior_sampler.py` | `tools/package/interior_templates.py:267` | Transitive install-time local import is absent from bundle |
| W010 | `tools/setup/probe_runtime.py` | `tools/setup/ce_probe.py:29` | Transitive install-time local import is absent from bundle |
| W010 | `tools/setup/probe_runtime.py` | `tools/setup/interior_sampler.py:46` | Transitive install-time local import is absent from bundle |

Validation: Python `compile()` and all JSON inputs passed; `git diff --check` passed.
No existing unit tests target `wiring_audit.py`; none were added or run.
Enforce lint/perf gates are not applicable because no `.c` source changed.
Native compile, native boot, observed CE supply, RPC/gameplay behavior and
one-server/one-client acceptance remain unproven.

Suggested README/MODULE_STATUS line: “Static wiring audit now checks typed setting
reads, production creation routes, zeroed item supply and portable bundle closure;
29 new source findings remain for owner fixes/review; DayZ acceptance pending.”

Integration note: `/docs/*` currently ignores this document. The lead must add an
exact `.gitignore` exception or explicitly include this file; the worker cannot
edit that lead-owned file or write Git metadata.
