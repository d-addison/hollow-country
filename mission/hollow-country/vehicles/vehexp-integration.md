# Expansion vehicle source implementation

Owner scope veh-expansion, 2026-11-19. The evening owner override permits source
implementation and only lint, compile guards and settings consistency checks.
No behavioural tests were authored, edited or run. No runtime evidence exists.
The referenced docs/SPECIFICATION.md and docs/specs/001-survival-overhaul/spec.md
are absent from this checkout. The audit-code excludes Expansion Vehicles from
its older assignments; this explicit vehicle assignment supersedes that exclusion.
README travel rows 74-75 and runtime contract were read; no replacement gameplay
controller is introduced.

## Specification and disposition

- Existing native sedan/hatchback/offroad families remain repairable and retain
  their budgets. The Expansion sedan/hatchback packs extend those exact native
  class names; separate ExpansionSedan/ExpansionHatchback names are not invented.
- Existing 28 native motorbikes remain
  intact; the bicycle overlay was retired on 2026-11-22. The installed Expansion TT650/250N/OldBike are scope-0 legacy prototypes,
  not usable CE additions. Their vehicle base is obsolete; changing scope is not
  an implementation of working vehicle simulation. No third-party source is copied.
- Seven Land Rover/UAZ variants share the existing nine-offroad budget. Native
  trucks plus three buses and four tractors share a seven-vehicle truck event.
  Three Expansion boat variants share the existing six-boat coastal event, so
  this does not add six more boats. Stock boat positions remain unchanged.
- Six helicopter variants (including small/big gyrocopter) share one four-vehicle
  event. WorldCap=4, MaxTracked=16, MaxTypeCache=128 and SpawnFuelMaxFraction=0.1
  remain existing operator controls. VehicleClasses now accepts editor categories
  and real CfgVehicles bases; no new numeric setting is introduced.
- Ground hull CE damage is 10-40%; wheels 70%, service parts 35%, panels 65%.
  Air hull CE damage is 30-65%, service parts 25%, panels 65%. No cargo is seeded.
  New Expansion loose repair parts have finite nominal=6/min=3 and 35-70% damage.
  Ground fuel follows existing native CE 0-35% random fill. Fresh CE helicopter
  fuel is capped at SpawnFuelMaxFraction; absent ignition means zero fuel.
  Saved tanks are untouched on restart. Parts probabilities and event budgets
  are explicit XML operator configuration, provisional until target-load testing.
- An-2 is also only Vehicle_ExpansionAn2 (scope=0). Its installed prototype derives
  from obsolete ExpansionVehiclePlaneBase. No flight controller is invented.
  The working providers for these four legacy families cannot be authored from
  class/config names alone under the read-only/no-copy dependency contract.
  C-130J and the carrier/LHD have no CE, spawnable or types additions.
- CE is the sole spawn owner. The new air event has saferadius/distanceradius=1000;
  ground/coastal events retain 500. These are CE proximity controls, not proof of
  occlusion from every player. The sixteen air points are a limited selection of
  installed vanilla StaticHeliCrash open-field coordinates, not surveyed aircraft
  footprints. Rotor clearance, terrain slope, depth, persistence and all-player
  sight acceptance require native/two-client observation.

## Plan/tasks completed in scope

1. Inspect installed config class inheritance, public scopes, attachment slots,
   script hooks and existing CE/policy/incident ownership.
2. Extend existing CE family children; add one truck-family override and one
   shared rare-air event; author damage/parts and exact shared types merge rows.
3. Extend existing HCHeliPolicy classification and fresh-CE fuel shaping without
   adding a controller, module slot, scan, spawn or inventory grant.
4. Bridge provider landing transitions and native helicopter death into the
   existing bounded incident registry. Initial CE/restart state creates no
   landing event. Departure/delete retires the anchored incident; a crash retires
   a landing before publishing so anchor coalescing cannot retain the wrong kind.
   Dead helicopters leave live-policy tracking. Per-kind success logs print once.
5. Run only the owner-authorized lint, compile guards and settings consistency.
   Integration and runtime tasks below remain explicitly outstanding.

## Exact integration edits requested (outside assigned ownership)

1. In mods/HollowCountry/config.cpp, append
   `"DayZExpansion_Vehicles_Scripts"` to CfgPatches/HollowCountry/requiredAddons[].
   This orders the guarded modded ExpansionHelicopterScript landing link after
   its provider. The existing vehicle preload defines EXPANSIONMODVEHICLE.
2. Cov-items: merge **every exact type element** from
   `vehicles/vehexp-types.append.xml` into `ce/types.xml`, replacing by case-folded
   name if a row already exists. Do not also register the append document as a CE
   file. Its 23 vehicle rows have nominal/min zero and its 36 part rows are finite.
   Native trucks and existing native vehicle rows remain under their existing
   zero loose-loot budgets. Do not add scope-0 legacy bikes/An-2 types rows.
3. In tools/package/pbo.py MISSION_FILES add these exact relative strings:
   `vehicles/vehexp-eventspawns.xml`, `vehicles/vehexp-types.append.xml`,
   `vehicles/vehexp-roster.json`, `vehicles/vehexp-integration.md`.
4. The stopped-mission installer must merge the single event in
   `vehicles/vehexp-eventspawns.xml` into the target `cfgeventspawns.xml` by event
   name, rejecting an existing conflicting VehicleHCExpansionAir definition and
   retaining a receipt of the original bytes for rollback. Do not replace the
   entire eventposdef or append that event on repeated installation. Existing
   family names use their installed stock positions, including coastal boats.
5. tools/package/travel.py currently rejects this authorized expanded roster.
   Keep its uniqueness, zero-loose-budget, native repair and bounds checks. Exact
   source data for the additional family children is
   `vehicles/vehexp-roster.json` / `families`. In validate(), extend expected with
   `VehicleTruck01: 7` and `VehicleHCExpansionAir: 4`; other counts stay unchanged.
   In _roster(), construct expected family sets by extending NATIVE_FAMILIES with
   each manifest family list (set union, no duplicate type owners), and include
   VehicleTruck01 in expected event owners. Keep the truck native-stock template
   exemption: its three Truck_01 variants intentionally retain installed stock
   repair templates. Require every other expected vehicle to have one authored
   spawnable template. For Expansion attachment multiplicities, use the authored
   XML plus installed attachment slots, not repair_parts()'s native-only table.
   Do not weaken unknown-event/class admission globally. Add receipt-backed
   position installation/rollback from item 4 to that stopped-server installer.

No HCModule slot, unit-budget consumer id, settings-registry row or debug snapshot
entry is requested. Existing HCHeliPolicy status/contributor registration remains.
The expanded source cannot currently pass the old travel installer roster pin;
that out-of-scope integration work is required before packaging/installing it.

## API and data provenance (read-only)

Native snapshot `~/.cache/hollow-country/native-scripts/scripts-1.30.164289`:
Game.c:1437 IsKindOf; Object.c:287 GetPosition, :517 IsAlive;
EntityAI.c:1104 EEKilled, :1897 FindAttachmentBySlotName. Existing policy header
retains citations for its pre-existing init/delete/CE/fuel/config/store calls.

Installed 2291785437 `vehicles_scripts.pbo`, member
`4_World/DayZExpansion_Vehicles/Entities/Vehicles/ExpansionHelicopterScript.c`:
769 EOnPostSimulate; 1113 IsLanded; 302 CE hydraulic fill. The landing bridge
calls only super.EOnPostSimulate and IsLanded, reusing provider contact state.
`0_vehicles_preload.pbo/Common/DayZExpansion_Vehicles_Defines.c:13` defines
EXPANSIONMODVEHICLE. No Expansion code is copied or repacked.

Vehicle class/attachment evidence is installed CfgVehicles in config.bin (binary
configs have no source line numbers): 2291785437 vehicles_ground_landrover,
vehicles_ground_uaz, vehicles_air_gyro, vehicles_air_hatchbird,
vehicles_water_zodiac, vehicles_objects_gear and vehicles_scripts PBOs;
2116157322 vehicles_ground_bus, vehicles_ground_tractor, vehicles_air_mh6,
vehicles_air_uh1h, vehicles_air_merlin, vehicles_water_utility PBOs.
Legacy scope-0 evidence: vehicles_ground_oldbike (2291785437),
vehicles_ground_tt650, vehicles_ground_250n, vehicles_air_an2 (2116157322).
Parts slots use exact installed identities; dummy Niva slots on skid helicopters
are not populated with invented wheels. Expansion sedans/hatchbacks/trucks extend
native class names rather than adding a second vehicle family.

Existing local incident hooks: HCIncidentSources.c:42 HCCrash;
HCWorldIncidents.c:242 HCPublish and :264 HCRetire; defaults :73 crash investigate
and :75 scene react. HCXAIIncidentResponse.c:204 HCOffer, :379 HCPerceives call;
existing budgets/cooldowns/leases limit work. Landing uses visual-only `scene`
policy, crash uses `crash`; no AI gets coordinates without existing member
perception. No rewards, markers, dialogue or remote inventory state is added.

## Operator and native acceptance

EnableTravel=false opts out at installation; stopped-server event `active=0`
opts out per CE family. Existing receipt rollback removes installed travel data.
`acceptance/helicopters.disable` opts out of helicopter policy/landing publication;
`world_incidents.disable` controls incident registry and existing AI incident
controls remain authoritative. Event XML and disabled script policy are separate:
disabling script fuel policy does not remove already installed CE content.

Grep boot for `V2 admission feature=Helicopters`,
`[HC Helicopters] incident_hooks=crash_and_landing`,
`[HC Helicopters] ready reason=provider_loaded_policy_active_runtime_pending`,
`[HC Vehicles] legacy_roster=unavailable`, and any `HELI_` refusal.
On first relevant events grep `[HC Helicopters] spawn_fuel_capped`,
`[HC Helicopters] incident=scene source=vehicle_hook` and
`[HC Helicopters] incident=crash source=vehicle_hook`.
`landing_hook=missing_vehicle_script_provider` means the bridge was not compiled.

Boot a normal PBO/server after the shared edits; inspect CE class/slot warnings
and verify no duplicate type/event registrations. Check all native and Expansion
families, six total boats along coasts, at most four live helicopters, missing
parts and fresh-CE fuel. Repair/refuel, save/restart and verify saved state remains.
With two clients on opposite approaches, observe spawn/replacement visibility,
landing/takeoff/crash, nearby AI sight/hearing versus distant/unaware groups,
incident cooldowns, deletion and destroyed-aircraft replacement. Test opt-outs
and rollback without wiping storage. Record all outcomes as native evidence;
offline checks cannot establish any of these behaviours.

Nothing observed in DayZ yet.

## Authorized source checks

- `python3 -B -m tools.validate.enforce_lint --no-native`:
  pass, findings=1 new=0 stale=0 native=no.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_script_syntax tests.unit.test_enforce_locals tests.unit.test_script_identifiers`:
  15 tests, OK (27.781s).
- `python3 -B -m tools.validate.settings_consistency`: status=pass, errors=[].

No behavioural test modules were run or changed. Git metadata was left untouched;
the proposed commit message is in `.banso-writer/commit-message` for Banso.
