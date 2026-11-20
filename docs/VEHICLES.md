# First common car

Issue #256, first vehicle repair; owner direction: repairable common cars, default on.
Source policy updated 2026-11-20. DayZ gameplay acceptance remains **pending**.

A fresh character should be able to find a viable common car and complete its
repair by searching two or three villages, particularly garages, sheds and nearby
industrial/farm buildings. This is the play-test target, not an observed outcome
or a promise from map-wide CE counts.

## Classes and CE ownership

| Car | Native vehicle class | Matching wheel |
| :--- | :--- | :--- |
| Sarka | `Sedan_02` | `Sedan_02_Wheel` |
| Olga | `CivilianSedan` | `CivSedanWheel` |
| Gunter | `Hatchback_02` | `Hatchback_02_Wheel` |
| Ada | `OffroadHatchback` | `HatchbackWheel` |

These public classes, their two colour variants each, and the matching wheel
inventory slots were checked with `tools.audit.pbo_config` against installed DayZ
`vehicles_wheeled.pbo/config.bin`. Battery, radiator, spark plug and `HeadlightH7`
slots/public scope were checked in `vehicles_parts.pbo`; tools in `gear_tools.pbo`.
`CanisterGasoline` is public in `vehicles_parts.pbo`, with native capacity 20,000 ml.
Native scripts inspected: `CarScript.EEOnCECreate` and `CanisterGasoline`.

`mission/hollow-country/ce/events.xml` already has active `VehicleCivilianSedan`,
`VehicleHatchback02`, `VehicleOffroadHatchback` and `VehicleSedan02` events, each
nominal/min/max **9/6/11**. These are unchanged: 36 common-car family nominal,
within the existing 39-car roster. The Ada family shares its event with Expansion
cars; its three native variants retain child minimum two each. Event counts are
configured budgets, not a live vehicle census. Cars stay event-owned with no new
loose-loot vehicle budgets or scripted vehicle creation.

## Repairable starting condition

`mission/hollow-country/ce/travel-spawnabletypes.xml` is the existing registered
cfgspawnabletypes overlay. All 12 common-car variants receive this policy:

| Attachment/condition | Before | After |
| :--- | :--- | :--- |
| Five wheel groups including spare | Each: usable 65%, ruined 20% | Usable 100%, 100%, 75%, 75%, 25%; ruined 0% |
| Battery / radiator | Each 25% | Each 75% |
| Spark plug | 25% | 0%; must find a plug |
| Two headlight bulbs | Each 40% | Each 65% |
| Matching usable wheel damage fraction | 0.55–0.90 | 0.10–0.30 |
| Car body damage fraction | 0.10–0.30 | Unchanged |
| Doors, hood and trunk | Each 65% | Unchanged |

Two wheel attachment groups are certain in the authored XML; other wheel groups
can be missing. Native slot allocation, including which wheel goes to the spare
slot, still needs observation. Zero-chance ruined-wheel and spark-plug rows retain
the existing tool-validated attachment roster without offering those attachments.
A missing plug makes every fresh spawn a repair project. Matching wheel templates
also govern loose CE wheels. Already persisted vehicles are not retrofitted.

Fuel remains native: `CarScript.EEOnCECreate` fills 0–35% of tank capacity.
The jerry-can row retains stock quantity bounds **30–70%**; native gasoline and
fuel-pump/refuelling behaviour supply the route to a dry tank. No custom fuel
item, cargo reward, scripted refill or duplicate part source is added. Bring
water for the radiator before driving; missing coolant can destroy the engine.
Tools secure/remove attachments through native actions; bulbs are for safe night
travel, not an ignition requirement. Installed vehicle dependencies may add tool
requirements, which must be checked during the same play test.

`mission/hollow-country/ai/car-repair.json` stays unchanged and enabled. Its bounded
AI mechanic jobs use actual carried/stashed parts and tools; it is not the player
loot supply policy and does not grant a starter kit.

## Loose parts and tools

The 12 complete rows below are authored in `mission/hollow-country/ce/types.xml`,
using native `db/types.xml` as the field baseline. Budgets, routes and eligible
buildings were checked through `tools.package.economy`; installation and rollback
reuse `tools.package.travel`. No weapon entry changes.

Before means native baseline (these rows were absent from the HC types overlay).
Numbers are **nominal/min**, map-wide targets. Default bundle numbers include the
existing general loot multiplier of two; the separate three-times firearm policy
is unchanged. All 12 rows use the native single `tools` category and receive that multiplier;
wheels move from `lootdispatch` to `tools` to reach garages and sheds.

| Item | Before | Authored after | Default bundle after |
| :--- | ---: | ---: | ---: |
| `CivSedanWheel` | 40/30 | 80/60 | 160/120 |
| `Hatchback_02_Wheel` | 40/30 | 80/60 | 160/120 |
| `HatchbackWheel` | 40/30 | 80/60 | 160/120 |
| `Sedan_02_Wheel` | 40/30 | 80/60 | 160/120 |
| `SparkPlug` | 120/80 | 160/120 | 320/240 |
| `CarBattery` | 120/80 | 140/100 | 280/200 |
| `CarRadiator` | 120/80 | 140/100 | 280/200 |
| `HeadlightH7` | 0/0 | 120/80 | 240/160 |
| `Wrench` | 140/100 | 140/100 | 280/200 |
| `LugWrench` | 120/80 | 140/100 | 280/200 |
| `Screwdriver` | 100/60 | 120/80 | 240/160 |
| `CanisterGasoline` | 100/60 | 120/80 | 240/160 |

All 12 rows explicitly use `Industrial`, `Farm`, `Village` and `Tier1`–`Tier4`,
retaining native shelf tags. Garage/shed are building classes, not valid usage
flags. Using `tools` gives wheels a route to ordinary garages/sheds; the original
wheel-only `lootdispatch` category matched none of the audited garage/shed classes.
Headlight bulbs now have a finite loose budget and `crafted=0` to admit CE supply.
All other native flags, quantities, lifetime, restock and cost are retained.
Only loose map items count toward budgets; moving parts into cargo does not mint
replacements directly, but CE can replenish map supply within its own rules.

Offline route counting against the installed mission's map prototypes/placements
finds **908 eligible placed garages/sheds across eight building classes** for
`tools` with shelf compatibility (including small/row garages and M4/W5/W6 sheds).
This is eligibility, not simultaneous loot capacity or measured spawn frequency.
`economy.route_report` passes all 12 rows across Farm/Industrial/Village. Tier
matching, object fit, shelf reachability and competition with other loot need
engine observation. Empty native usage lists mean unconstrained usage under the
tool's assumptions; the Sarka wheel previously had no explicit usage restriction.

## Validation and outstanding acceptance

Offline checks on 2026-11-20:

- `python3 -B -m tools.package.travel validate`: nine families parse; all roster,
  attachment compatibility, event budget and unique-owner checks pass.
- Travel install, repeated install and rollback pass on a temporary ignored mission
  copy reconstructed from the installed travel receipt's baseline XML backups;
  rollback restores baseline XML byte-for-byte. Live mission remains read only.
- XML scope comparison against HEAD: exactly 12 supply rows added, all pre-existing
  types unchanged; exactly 12 common-car and four matching wheel templates changed.
- `enforce_lint`: `pass findings=1 new=0 stale=0 native=yes`.
- `enforce_perf`: `pass findings=64 new=0`.
- No Enforce/Python implementation changes, unit tests or gameplay harnesses.

Native compile and boot are lead-owned and were not run here. Use one server and
at most one client. On a fresh CE population, inspect at least one spawn per common
car family for usable engine/wheels and missing plug; check allocation of wheel
and spare slots and actual attachment health. Then start a fresh character, choose
a car and record every missing part, search route, villages visited and elapsed
time. Confirm matching wheels, plug, charged battery, radiator, bulbs, tools and
fuel can be found and carried from CE loot, including accessible shelves; add
coolant and fuel, start the engine and complete a short drive. Check persistence
of installed parts/fuel across restart without duplicate supply. If the kit cannot
be completed in two or three villages, retain this gate as pending and tune the
measured limiting part/location rather than declaring the budget accepted.

Install via the normal stopped-server bundle/receipt workflow. Existing receipts
must be rolled back through the owning installer before applying changed content;
do not patch a running mission or delete persistence to force fresh cars.
