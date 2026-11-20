# CE encounter events

Authored 2026-11-20 for ChernarusPlus 1.30. Native acceptance remains **PENDING**.
The owner’s “Lots” policy is now 48 nominal HC instances across 16 event types.
Nominal is a CE population target; no active count has been observed in DayZ.

| Event (`StaticHC` prefix) | Nominal | Anchors | Story composition |
| --- | ---: | ---: | --- |
| ConvoyAmbush | 3 | 12 | Ural and abandoned UAZ with scattered supply crates |
| ArmorRecovery | 3 | 13 | BMP and recovery Ural abandoned with weapons cargo |
| SupplyTruck | 3 | 12 | Ural carrying weapons, medical and ration crates |
| PoliceEvidence | 3 | 12 | Police wreck and UAZ carrying seized weapons |
| PrisonTransfer | 3 | 13 | Bus and police escort stopped with transfer supplies |
| BanditCache | 3 | 13 | UAZ beside two weapons crates and provisions |
| SniperExtraction | 3 | 12 | BRDM extraction point with weapons and provisions |
| FieldHospital | 3 | 12 | Medical van, UAZ and medical supply crates |
| TransportDown | 3 | 13 | UH-1Y crash and scattered elevated cargo |
| CargoSpill | 3 | 13 | Mi-8 crash with two weapons crates and provisions |
| APCColumn | 3 | 13 | BMP-2 and Stryker column abandoned with recovery cargo |
| MedicalEvacuation | 3 | 13 | Medical van and medical offroad evacuation rendezvous |
| HuntersLastStand | 3 | 13 | Abandoned offroad vehicle and hidden weapons stock |
| SmugglerExchange | 3 | 13 | Closed trailer and police wreck at a failed exchange |
| FireResponse | 3 | 13 | Fire truck and ambulance stranded with response supplies |
| SupplyTrailer | 3 | 12 | Cargo truck, flat trailer and dispersed supply boxes |
| **Total** | **48** | **202** | **16 groups; 100 authored object entries** |

The previous policy was 10 types, nominal 24, 200 anchors and 62 object entries.
All new identities resolve as scope 2 in the installed vanilla
`structures_wrecks.pbo` and `structures_military.pbo`: 22/22 scene classes checked.
Only authored configuration and selected class/coordinate evidence ship, never
models, game dumps or Workshop assets.

## Lifecycle, geography and loot

Each type has a 40–55 minute lifetime, 300-second restock, 200 m player safety
radius, 300 m distance radius and 1000 m cleanup radius. Secondary populations
remain disabled. At the nominal population the authored compositions contain
300 scene objects. These are provisional ceilings, not measured engine costs.

All HC candidate centers are mutually separated by at least **401.517 m**;
validation refuses separation below 340 m. There are 13 candidates per type for
three nominal instances. Source pools contribute 72 helicopter, 84 police-car,
18 police-situation, 13 military-convoy and 21 bonfire seeds. Roadside seeds are
shifted laterally by 90 or 130 m using their stock orientation, instead of placing
large compositions on the original roadside anchors. Other seeds retain stock
coordinates (rounded to millimeters). `hc-event-sites.json` schema 2 records
both original attributes and authored coordinates for every candidate.

Authoring filters exclude a 120 m margin around static contamination areas and
require 80 m from mapped building origins. Install checks those exclusions again
against the destination mission. This is a coarse town/building clearance check;
it does not survey settlement boundaries, actual road edges, terrain, vegetation
or slopes. **Road clearance, native surface fit and unobstructed access remain
unproven**, particularly at displaced seeds. No scene is accepted as collision
safe on the strength of these coordinate checks. Inspect all families and the
shifted candidates in DayZ before marking placement accepted.

The installer transfers each exact source seed out of its original stock pool,
retaining at least ten positions per affected pool. On the inspected mission the
remaining pools are heli 23, police car 216, police situation 21, military convoy
10 and bonfire 42. Total position count stays 1647. This prevents reuse of the
same source seed; proximity to unrelated stock events and actual CE spacing still
need engine observation.

Every scene has the native supply-box weapons class. Its existing prototype is
replaced with Military usage, Tier3/Tier4 values, weapons category and three
native elevated crate-top points (about 0.43 m high). The installer checks those
points against the destination prototype. Each weapons crate requests three CE
items; ration and medical boxes each allow zero to one. Decorative wreck loot is
disabled to avoid their ground points. At nominal there are 189 elevated weapons
slots versus at most 81 other supply slots. These are CE capacities, not a promise
that scarcity/accounting will fill every slot. No scripted loot is created.
The prototype change also affects other uses of the same supply-box class.

## Bundle integration and rollback

`friend_bundle.py` exports `hc_events.py` and validates the event sources. The
five `ce/hc-*` files are in the private-handoff/export allowlist. `ce/events.xml`
remains the unchanged vehicle roster; HC events have one separate registration.

The actual friend-bundle rehearsal and apply stacks are in
`optional_overlays.bundle_apply`, rather than `friend_bundle.py`. Both now call
`hc_events.install(Path(bundle) / 'mission/hollow-country', mission)` last
(using the scratch mission during rehearsal). Automatic undo, bundle rollback
and original-layer recovery remove events before lower CE layers. Installed
mission export also removes the event layer first on scratch.

The guided friend installer removes events before replacing base, map or weapon
layers, and reinstalls them after the map/weapon install. Weapon rehearsal also
includes the final events layer. Its existing transaction journal retains the
mission tree for whole-install recovery.

Receipts preserve exact original bytes and before/after SHA-256 digests. Complete
repeat installation is idempotent. Source changes require rollback first. Drift
refuses before any rollback mutation. Interrupted installation can be rolled back
from either original or installed bytes. Hive entities are not erased by XML
rollback; native cleanup/restart behavior remains pending.

## Scratch evidence, 2026-11-20

The live mission was read only. A storage/log-free copy was made under `.scratch/` during work and removed
before handoff because that directory is unignored here. Composed installers
ran on temporary external copies because their
existing dependency-data guard refuses checkout ancestors.

The event layer on the installed mission copy passed:

| Measure | Before | Installed | Rolled back |
| --- | ---: | ---: | ---: |
| Effective event XML rows | 78 | 94 | 78 |
| Event-position definitions | 38 | 54 | 38 |
| Root event groups | 83 | 99 | 83 |
| Total candidate positions | 1647 | 1647 | 1647 |
| HC candidate positions | 0 | 208 | 0 |
| HC nominal sum | 0 | 48 | 0 |

```text
idempotent True
drift_refused encounter target drift: cfgeventgroups.xml True
rollback_byte_exact_all_files True
interrupted_after_write 1 byte_exact_all_files True
interrupted_after_write 3 byte_exact_all_files True
interrupted_after_write 6 byte_exact_all_files True
runtime PENDING
```

The **unmodified composed bundle rehearsal is blocked**, not accepted:

1. Export baseline recovery sees unregistered `hollow-country` source leftovers
   after the installed receipt layers roll back, and refuses with
   `no valid receipt and unexpected managed content`. On scratch only, these
   leftovers were quarantined after confirming the recovered core had no CE
   registrations. No receipt guard was weakened.
2. The actual bundle apply rehearsal then refuses 81 duplicate loot-point groups
   shared by `additions.json` and `additions-interiors.json`.
3. With only those duplicate rows removed on a conditional scratch bundle,
   rehearsal reaches travel and refuses `travel class/event has another CE owner;
   reconcile first`. No successful full-stack result is claimed. These baseline
   and non-event input fixes belong to their owners; this worker did not edit them.

No Enforce code changed. The lead must keep native boot, observed active count,
placement, loot pickup, lifecycle/rotation, restart persistence, stock-event
spacing and frame-cost checks pending in `docs/MODULE_STATUS.md` (outside scope).
Acceptance is one server and at most one client. Multiplayer is not proven.

Tooling checks: Python syntax passed. `tests.unit.test_package_manifest` passed
31/31. The three focused slow fixture modules reported failures and were stopped
after more than ten minutes under blocked filesystem I/O; no all-pass result is
claimed. A focused exporter fixture reproduces the expected
`repo data or generators differ from build commit` refusal in this uncommitted
worker checkout. The committed-input guard was preserved. No unit tests were
added or modified.

The focused optional-overlay smoke module finished 5/6 passing. Its remaining
assertion expects the Expansion-AI/Navigation dependency order while the current
manifest supplies Licensed/Vehicles; the event functions do not select that order.
Those manifest/test changes are outside this worker’s scope.
