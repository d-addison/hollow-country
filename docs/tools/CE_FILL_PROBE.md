# CE initial-fill probe and diagnostic variants

The lead runs disposable treatments serially with no other DayZ server running.
Workers stage and test tooling only. No economy policy is edited by this probe.

All treatments load the **same complete installed friend mod set**, including t0.
Authority is `friend-local-1/start-server.bat`, checked against its SHA-256 in
`hollow-country-install-receipt.json`. The inspected launcher has 17 `-mod` folders
and no `-serverMod`. Mod folders stay in place on E:, read-only; every PBO path and
SHA-256 is recorded. The launcher rejects missing, added or changed PBOs, symlinks,
and unexpected switches before starting. Other probe kinds retain their fixed
argument lists. Stop remains `CloseMainWindow` with a bounded wait, never kill.

The source control is the existing hash-verified `vanilla-p0-001` runtime. The
brief's `bundle-src-005/server/mpmissions/dayzOffline.chernarusplus` is **already
HC-layered** (HC base, Tactical Flava, travel and optional-pack registrations); it
cannot serve as stock t0. This choice is recorded in each plan. Fresh storage is
mandatory. All treatments use the same generated mission hook and fresh authored
profile defaults, without inheriting installed profile state or identities.

The small treatment table lives in `ce_fill_probe.TREATMENTS` (hard cap 8):

| Treatment | Economy layers |
| --- | --- |
| t0 | Stock CE XML/maps; full mods and HC scripting support |
| t1 | HC base economy |
| t2 | t1 + loot boost / shipped floor policy |
| t3 | t2 + both weapon packs at the existing shipped 2x policy |
| t4 | Full friend stack, in the friend's installer order |

Common HC mission JSON and gameplay support come from `friend_bundle` generators
and `optional_overlays.bundle_candidate`/`install`. t0 selects that candidate's
JSON outputs while retaining stock CE XML/maps. Profiles use
`friend_bundle.repo_profile_sources`/`profile_bytes` and `friend_install.do_files`.
The HC startup hook is already in the loaded mod's `MissionServer`; the inspected
friend `init.c` uses the stock `CustomMission` factory. No installed mission script
or profile JSON is hand-copied. Remaining layers reuse `travel.install`,
`optional_overlays.plan/install`, `loot_boost.install`, `infected_variety.install`,
`map_overlay.load_source/install`, `tactical_flava_optional.apply_weapon_packs`,
and `hc_events.install`. t4 restores their actual ordering (travel/optional before
boost, map before weapons, events last), rather than installing onto t3's receipts.
Installer refusals stop staging. Default Workshop evidence is read from the same
G: content root used by the release tooling; `--workshop` overrides it.

Stage each treatment into a distinct, previously absent destination:

```bash
python3 -B -m tools.setup.ce_fill_probe stage \
  --destination /mnt/d/HollowCountryLocal/ce-fill-t0-001 --treatment t0 --dry-run
# Repeat t1 through t4. Omit --dry-run to retain the staged runtime.
```

Dry-run rehearses the entire selected stack on temporary copies, verifies stock
and mod hashes, and checks launcher compatibility. It writes no destination.
A retained runtime contains the plan, exact staged-file pins and fresh defaults.
The launcher permits only those pinned profile files for this kind; storage stays
empty. Reusing a launched destination is refused.

The lead launches from Windows PowerShell:

```powershell
.\tools\setup\Start-CEProbeServer.ps1 -Kind ce-fill-probe `
  -Runtime 'D:\HollowCountryLocal\ce-fill-t0-001'
```

The hook holds at least 240 seconds after mission `OnInit` and prints begin/done
markers bound to stock, mod inventory, treatment, executable, run nonce and hold.
The launcher waits for its sentinel, then requests a graceful stop. Ingest only
complete logs from that runtime:

```bash
python3 -B -m tools.setup.ce_fill_probe ingest \
  --rpt /mnt/d/HollowCountryLocal/ce-fill-t0-001/profiles/<run>.RPT \
  --plan /mnt/d/HollowCountryLocal/ce-fill-t0-001/ce-fill-probe-plan.json \
  --out /mnt/d/HollowCountryLocal/ce-fill-t0-001-summary.json
```

JSON retains per-type counts, first/last timestamps (seconds since midnight), CE
init summaries, actual hold duration and plan/RPT/source provenance (including authored-input and generator hashes). Pre-OnInit
initial-fill warnings are included. Missing/duplicate/mismatched markers, a short
hold, missing CE summaries, malformed warnings or warnings after completion refuse
ingest. A zero-warning control is valid. Keep outputs outside Git. Compare the
first treatment where warnings rise before selecting a small targeted variant;
use the receipted variants below to test the hypotheses.

The new diagnostic checks **all** building-routed categories together:

```bash
python3 -B -m tools.package.ce_slot_pressure \
  /mnt/e/HollowCountryLocal/friend-local-1/mpmissions/dayzOffline.chernarusplus \
  --all-categories
```

It uses category/tag intersections, usages, placed tier sets, shared container caps
and shared group caps, with integral maximum flow instead of equal usage shares. Unassigned route groups
are one allocation witness, not causal type attribution or a nominal-cut policy.
Observed static results during this worker run:

| Input | Nominal demand | Optimistic assignable bound | Deficit | Unreachable nominal |
| --- | ---: | ---: | ---: | ---: |
| Installed build 159 | 42,507 | 39,285 | 3,222 | 16 |
| Verified vanilla control | 20,342 | 19,088 | 1,254 | 1,008 |

Categories checked include clothes, containers, explosives, food, lootdispatch,
tools, vehiclesparts and weapons when present. Exit 1 means the **static bound**
is infeasible. This is not a qualified predictor of hard-to-place warnings:
vanilla is infeasible too, while the fresh 240-second control logged only 71 warnings. Even excluding
unreachable nominal leaves vanilla infeasible. Consequently the existing installer
`problems()` gate and its `friend_install` caller are unchanged; promoting this
bound to a gate would introduce a known false positive. The old weapons-only pass
also cannot establish successful native fill.

The available static inputs do not reveal CE's actual retry/selection behaviour,
loaded class dimensions, collision rejection, point range/height acceptance or
runtime registration semantics. Nominal is not evidence that the engine must fill
all matching proxies simultaneously. These observations prevent a defensible
warning threshold or causal installer fix from this round's offline evidence.
The bound supplies an additional constraint to investigate, not a finding that
capacity caused the flood. Targeted native variant runs and a correctly qualified installer gate remain pending. Nothing here establishes
native compilation, successful boot/fill, runtime acceptance or multiplayer.


## Native initial-fill evidence (lead, 2026-11-21)

Same installed friend mod set, fresh storage and a 240-second hold:

| Treatment | Hard-to-place lines | Types |
| --- | ---: | ---: |
| t0 stock CE | 71 | 40 |
| t1 HC base | 85 | 43 |
| t2 + loot boost | 2,181 | 136 |
| t3 + both weapon packs (2x policy) | 17,090 | 406 |
| t4 full friend stack | 10,120 | 371 |

Every type's warnings shared one timestamp (last minus first = 0 seconds).
This was a single initial-fill burst. Build 159 likewise logged all 12,742 lines
in the first minute and none later. In t3, 14,419 lines were from pack types absent
in t2. Their weapons-category signatures were Military+Police / Tier3+Tier4
(5,181), Military+Police / Tier3 (4,662), Military+Police+Prison / Tier2–4
(2,242), and Military+Police+Prison / Tier2–3 (1,402). Vanilla Military clothes
and containers also began failing after packs were added.

In t4, 22 pack types with nominal/min 1/1, Military+Police and Tier3+Tier4 each
logged exactly 173 lines: every initial-fill attempt failed. Broad-usage pack
weapons (Farm/Hunting/Town/Village, Tier1–4) still contributed about 860 lines.
The all-category static deficit was 845 for both t2 and t3 while weapons demand
rose from 3,641 to 6,559. The static model is uncalibrated and does not predict
this native burst. Greedy fill exhausting Military/Police weapons slots at
Tier3/4 is a working hypothesis, unproven. Boost deliberately leaves weapons-only
container lootmax unscaled.

## Targeted variants: lead run order

Variants are diagnostics, not acceptance. They never change shipped installers.
Keep the unchanged t3 summary as the baseline, then stage these independent runs
in order (the lead omits `--dry-run` to retain each fresh runtime):

```bash
python3 -B -m tools.setup.ce_fill_probe stage --treatment t3 \
  --variant weapons_capacity=2 --destination /mnt/d/HollowCountryLocal/ce-fill-cap2-001 --dry-run
python3 -B -m tools.setup.ce_fill_probe stage --treatment t3 \
  --variant weapons_capacity=4 --destination /mnt/d/HollowCountryLocal/ce-fill-cap4-001 --dry-run
python3 -B -m tools.setup.ce_fill_probe stage --treatment t3 \
  --variant pack_nominal=0.5 --destination /mnt/d/HollowCountryLocal/ce-fill-nomhalf-001 --dry-run
python3 -B -m tools.setup.ce_fill_probe stage --treatment t3 \
  --variant pack_tiers=widen --destination /mnt/d/HollowCountryLocal/ce-fill-tier2-001 --dry-run
```

Launch, hold and ingest each run using the commands above before proceeding to
the next. Use t4 repetitions afterwards to check whether the full stack changes
the response. Repeatable `--variant NAME=VALUE` knobs compose after every treatment
layer, in a deterministic order. Unknown/duplicate knobs, invalid ranges and knobs
on treatments without the weapons layer refuse. The treatment table retains its
hard cap of 8; variants do not add treatments or launch a sweep automatically.

`weapons_capacity` accepts 1 < factor ≤ 4. It multiplies resolved container
lootmax (explicit, prototype default, or native fallback 8), rounding upward,
only for weapons-accepting containers in enabled Military or Police groups. Each touched
group cap is raised to at least the sum of its container caps. Receipts report
container and group counts and before/after caps. No points, categories, usages
or geometry change: actual usable capacity can remain limited by native point
selection and collisions. This experiment tests the cap hypothesis only.

`pack_nominal` accepts 0 < factor < 1 and rounds nominal/min to nearest integer
(half upward), including allowing a small budget to become zero. Only the two
weapon-pack managed type files change. **This can never be a shipped policy:
the owner fixed both packs at 2x.** `pack_tiers=widen` adds Tier2 only to pack
rows with nonempty usages contained in Military/Police/Prison and lacking Tier2.
Other pack rows, stock rows and other managed files remain unchanged.

Each plan contains normalized variants and per-file edit receipts with before/after
SHA-256 and counts. The binding also covers a SHA-256 pin for the staged type
catalog, derived from that runtime's own `cfgeconomycore.xml` registrations (including
multi-line CE blocks), with stock rows first and later definitions taking precedence.
The catalog is a pinned staged file; ingest verifies its hash, so keep it beside
the plan. It records defining-file hashes and category/usage/tier sets. Ingest
carries variants, receipts and per-warning-type definitions into the summary.
Unregistered types remain unattributed and prevent comparison; no attribution is
guessed from prefixes or a different installation.

```bash
python3 -B -m tools.setup.ce_fill_probe compare \
  /mnt/d/HollowCountryLocal/ce-fill-t3-001-summary.json \
  /mnt/d/HollowCountryLocal/ce-fill-cap2-001-summary.json \
  /mnt/d/HollowCountryLocal/ce-fill-cap4-001-summary.json
```

Compare accepts two or more summaries, reports total lines, counts per defining
file and per (category, usage, tier) signature, and types that went to zero or rose
against the first summary. Different executable or stock-mission hashes refuse.
Older summaries without staged attribution must be restaged and re-ingested to
compare. The comparison reports observations only; native dose response and any
resulting installer fix remain pending with the lead.
