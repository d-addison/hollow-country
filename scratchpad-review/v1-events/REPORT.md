# V1 optional events writer report — #33 / #46

Source implementation is authored and locally tested. Native compilation,
CE/inventory/death behavior, field surveys and rendered presentation remain
**PENDING**. `HCEventQualification.Qualified()` returns false; only the once-per-
process `$profile:HollowCountry/acceptance/events.enable` marker admits an
EXPERIMENTAL local acceptance run. No native run was performed here.

## Inputs and confinement

Read AGENTS.md, README event/O-key sections, MODULE_STATUS, runtime contract,
event sources/layout/tests, the fuel translator/qualification patterns and the
installed native declarations. The two specification paths named in AGENTS.md
are absent. No local issue bodies were found. `gh issue view 33` and `46` were
not run because this task prohibits network. This report does not invent their
contents. The task contract, README and local spec/plan/tasks files here provide
traceability. The Banso CLI skill's dispatched-worker guidance was followed;
no orchestrator lifecycle, git index/metadata mutation, commit, push, network,
Wine or DayZ command was run.

## Resulting behavior

- Existing native entities are bound using local 3D queries with a 15 m radius,
  at most 128 processed results, refusal on ambiguity, no player-owned or nested
  supply selection, no item/actor factories, and no replacement loot. The native
  query allocates its result before script refusal; 128 is **not** an engine-side
  allocation cap. Pending targets can refresh; active leases cannot rebind.
- Recovery/salvage observe exact existing item custody. Delivery requires the
  exact item directly inside the exact bound container at its destination,
  following an enrolled participant's native inventory transition. Carrying an
  item to coordinates alone does not deliver it. Every later inventory transition
  revokes the prior receipt; leaving/disconnecting also revokes it.
- Investigation requires continuous area samples; presence requires both the
  bound landmark and area reach. Native infected deaths are attributed only from
  the killer/root-player callback to a live, currently enrolled server handle,
  scoped to its bound lease. Corpses, environmental deaths, outsiders, expired
  subscriptions and reconstructed client claims cannot complete an objective.
- Seven roster families: recovery, delivery, investigation, static salvage,
  optional Expansion encounter, incident presence, local infected threat. Two
  source-reviewed ChernarusPlus site candidates ship. Default sweep is one
  family's admission attempt every five seconds, 70 seconds for both sites;
  late CE population can make a previously unavailable mission appear. A
  current-session terminal mission never repeats.
- `HCExpansionAIEventProvider` is selected using a fixed script typename if the
  optional addon exists. Its existing Ready/Start/Observe/Stop/Gone API remains
  authoritative. Core has no Expansion compile dependency; the addon is unchanged.
- Existing journal semantics are retained and exercised end to end: terminal
  progress/tokens, monotonic IDs, session generation and replay protection survive
  restart. **Unfinished events cancel durably on restart; they do not resume.**
  No live handle, enrollment or supply is recreated. Legacy schema-1 delivery
  records missing the additive container fields still load; they cannot start
  container delivery without an actual binding. Torn/corrupt highest writes fail
  closed; readback is not proof of power-loss durability.
- O-key menu now receives bounded server task/site instructions, including the
  container requirement and no-additional-reward statement, with a larger detail
  area. Existing session/revision/receipt/rate-limit/privacy controls remain.
  Public coordinates describe mission sites; player locations/accounts and
  internal handles stay private.

## Site/anchor provenance

`HCEventSites.c` supplies two bounded DATA-REVIEW candidates, both
`Reviewed=true`, `Surveyed=false`, provenance
`stock-mapgrouppos-source-review`. This is a source coordinate review, not an
accepted in-world survey. Neither candidate is synthetic; all offline players,
items, infected, IO, callbacks and widgets in tests are explicitly synthetic.

The reviewed local stock-copy input was
`~/.cache/hollow-country/native-autotest-preparer-001/dayzOffline.chernarusplus/mapgrouppos.xml`,
SHA-256 `3eeaad9786a73c339f61f6e6ad203f0732e36b88f27333978cc8b4beece9cec4`.
Only the two authored anchor rows and source hash are included, not a vanilla dump.

| Site | Stock source row / anchor | Coordinates (x y z) |
| --- | --- | --- |
| coastal-police-source | mapgrouppos.xml:2468, Land_Village_PoliceStation | 3569.727783 13.309641 2431.353027 |
| inland-police-source | mapgrouppos.xml:2395, Land_Village_PoliceStation | 3421.308105 199.735687 13019.891602 |

Source/destination use the same site for a local supply collection/delivery loop.
BandageDressing, SodaCan_Cola, MetalWire and Barrel_Green are selection classes,
not guarantees or creation instructions. A missing/ambiguous existing supply or
container excludes that assignment. Clearance, accessible ground, CE supply,
barrel placement, actor visibility and safe human-AI routes are unreviewed in-world.

## Files

Authored under `mods/HollowCountry/scripts/4_World/Events/`:
`HCEventQualification.c`, `HCEventSites.c`, `HCEventWorldBinding.c`,
`HCEventEconomyObservation.c`, `HCEventAISelection.c`, `HCEventBriefing.c`.

Changed existing event sources:
`3_Game/Events/HCEventRuntimeData.c`, `HCEventTransportData.c`;
`4_World/Events/HCEventConfiguration.c`, `HCEventModule.c`,
`HCEventNativeObserver.c`, `HCEventProviders.c`, `HCEventRPC.c`,
`HCEventRoster.c`, `HCEventRuntime.c`, `HCEventRuntimePolicy.c`;
`5_Mission/Events/HCEventClient.c`, `HCEventMenu.c`.
Layout: `mods/HollowCountry/gui/layouts/hc_events.layout`.
Tests: `tests/unit/test_event_director.py`, `test_event_runtime.py`,
`test_event_integration.py`, `test_event_transport.py`, new
`test_v1_events_behavior.py`. Review artifacts: this directory's spec/plan/tasks,
API citations, RED/GREEN command transcripts and report.

No owner-only source, addon source or shared settings/input/config was edited.
The final BDD binding file is unchanged: targeted `test_event_director.py` uses
its stdlib `load_tests` hook to execute the complete event stack, while ordinary
full discovery loads each file directly.

## TDD and verification

The tests translate authored Enforce method bodies, rather than reimplementing
event decisions in Python. Native collaborators are explicit fakes. Translation
is not an Enforce compiler or native behavior evidence.

| Record | Actual result / scope |
| --- | --- |
| RED-01.txt | 55 collected cases including imported legacy fixtures; eight new errors from missing delivery/presence/infected/site adapters |
| RED-02.txt | 17 cases; one failure and two errors: legacy delivery admission, missing unleased-target reset and integer-division translator seam |
| RED-03.txt | eight cases; two failures and two errors, including sampled-custody delivery incorrectly succeeding without a direct transition receipt |
| RED-04.txt | additive binding metadata failed to reject overlong ContainerClass |
| RED-05.txt | nonfinite native query radius incorrectly reached the engine seam |
| RED-06-bdd-contract.txt | changed BDD filename violated the existing pinned binding; fixed by preserving the filename and expanding targeted test loading |
| GREEN-v1-events.txt | 23 new V1 behavioral cases passed before the final identifier regression |
| RED-07-identifier.txt | new Container member collided with the native inventory Container type; renamed to DeliveryContainer |
| GREEN-final-focused.txt | 24 V1 checks plus seven syntax/override checks passed |
| GREEN-focused.txt | earlier 21 V1 cases plus both 100-restart journal/module regressions passed (23 total) |
| GREEN-syntax.txt | seven script syntax/override checks passed |
| GREEN-bdd-contract.txt | existing pinned BDD binding contract passed after correction |

Commands used for focused iteration:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v1_events_behavior -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_event*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_script_syntax -v
```

Final validation:

- The initial full unit run collected 2,572 tests and exposed one BDD binding
  filename regression (one skip); the complete original transcript is retained
  in RED-full-unit-initial.txt. The fixed binding contract then passed its focused
  check. This failure justified the corrected full-suite run below.
- `python3 -B -m tools.validate.bdd` ran once: **1,453 tests, 61 bound scenarios,
  OK (one skipped)** in 72.269 seconds. Runtime acceptance NOT EXECUTED. This was
  followed by the mechanical native-member rename; final focused/full checks
  execute the renamed source. GREEN-bdd.txt retains the command and complete log.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit`:
  **2,573 tests, OK (one skipped)** in 104.983 seconds. GREEN-full-unit.txt
  retains the complete log for the final source.

No offline result changes native acceptance status.

## Native API evidence and exclusions

See [API-CITATIONS.md](API-CITATIONS.md) for every introduced native API and the
retained native journal/transport/UI seams, with exact installed file:line.

1. **All additional RewardUnits remain zero.** The native event journal has no
   durable CE allocator/reservation/transaction receipt. EntityAI.c:1413–1414
   explicitly describes EEOnCECreate as CE/**Debug** creation; it is not proof of
   CE-only origin. GetEconomyProfile is not an allocation receipt. No arbitrary
   item creation or unqualified inventory transfer was substituted. Ordinary
   existing collected supplies are the only tangible proceeds. Nonzero rewards
   remain explicitly excluded until an authoritative finite allocator and durable
   transfer/reconciliation contract exist.
2. **Origin is conservative and provisional.** CE/Debug callbacks mark only
   current-process candidates behind the experimental gate. Restored entities
   without that new-creation callback are excluded; origin is not inferred from
   persistent ID, class, CE profile or location. Callback ordering and genuine CE
   attribution need observation in a normal CE session without debug creation.
3. **Unfinished restart resumption is excluded.** Journaled cancellation is the
   existing safety contract. No exact target is guessed across restart. New
   session assignments can use only independently eligible current world items;
   no original item or actor is respawned by events.
4. **Human AI prerequisites remain provider-owned.** No fake artifact/permission,
   surveyed route, observer retirement or durable ownership hooks were installed.
   Existing HCXAIAdapter.Install requires them and Ready rejects their absence.
   The API exposes kill-based encounter evidence; rescue/escort/convoy controllers
   and radio audio are not invented from nonexistent objective APIs. These remain
   traceable unsupported provider capabilities for owner/provider follow-up, not
   accepted mission types. No navigation/combat/cleanup qualification is claimed.
5. **Native and multiplayer evidence remains pending.** Source-reviewed sites
   are not surveyed. Marker opt-in does not qualify CE provenance, native callback
   semantics, JSON crash durability, O-key rendering, replication, privacy races
   or target-load budgets. Active user steering schedules one-client acceptance;
   extra-client defects are later user bugs, not claimed passing tests.

## Owner wiring patch

**No owner wiring patch is required (empty patch).** Existing
`mods/HollowCountry/scripts/4_World/Core/HCModule.c:17` registers HCEventModule
exactly once. `config.cpp` already loads all three script roots and points at
`HollowCountry\\inputs.xml`; existing inputs.xml declares UAHollowCountryEvents
with kO. Existing client mission/menu hooks remain in the owned Events directory.
No new HCModule registration was added. The optional addon already registers its
own adapter; the event refresh can admit a provider that becomes ready later.

For an existing profile, settings.json is preserved, including Enabled=false or
an empty Sites array. New profiles receive the two candidate sites. For local
acceptance of an old empty profile, back up settings/state and explicitly copy the
two reviewed candidate DTO rows from HCEventSites.ChernarusPlus into Sites (native
JSON vector form [x,y,z]); do not delete/replace its state journal. This is operator
content selection, not a shared HCSettings or core-source patch.

## Exact later local-server acceptance steps (not executed)

1. Back up the isolated server profile and Events settings/state directory.
   Build the final authored PBO with the normal private package workflow. Compile
   the final source on DayZDiag, then load that exact candidate on the normal
   local dedicated server and one client. Keep build/PBO hashes and logs. Do not
   reuse the earlier director compilation as evidence for these changes.
2. First run without `HollowCountry/acceptance/events.enable` below the server's
   configured profile directory. Confirm the pending-qualification diagnostic,
   no event-native queries/objective mutations/provider start, and no automatic
   enrollment. Stop the process.
3. Create the empty marker file at
   `$profile:HollowCountry/acceptance/events.enable` and restart. Confirm exactly
   one EXPERIMENTAL admission log. Removing/adding the marker in the same process
   must not change admission; only a full process restart re-probes it.
4. Review both supplied anchors in-world. Walk accessible approaches and the
   entire 15 m objective/delivery region. Record exact pose/ground/clearance and
   screenshots, source hash and site IDs. Do not mark Surveyed=true merely because
   the source coordinates matched a building. Use the normal CE with no debug
   item/infected creation when evaluating economy-origin candidates.
5. Press O, then rebind it and repeat. Check instructions fit, selection persists,
   mouse/keyboard focus returns on close, other menus still work, fresh/stale
   states disable the right actions, and opening/closing does not enroll. Join,
   leave, die and reconnect; a new handle must explicitly rejoin. Confirm no
   private player coordinate/account data appears in event packets/menu.
6. At a reviewed site with an actual eligible CE supply/container, allow up to
   70 seconds for the default roster sweep. Missing/ambiguous or already-owned
   supplies stay unavailable. Pick up the bound recovery item and verify one
   completion without any other item appearing. Repeat static salvage at source;
   collecting elsewhere must not count. Inventory identities/quantities and CE
   population must remain ordinary native state.
7. For delivery, join first. Carry the exact item to the destination: this alone
   must not complete. Put it directly into the exact bound barrel and remain in
   range until observation. Test another container, a nested bag, a moved barrel,
   an outsider's transfer, leaving/disconnecting before delivery, removing the
   item before the next tick, and swapping/recreating a same-class item. None may
   consume or grant inventory or accept a stale delivery receipt. If no eligible
   finite CE barrel/supply exists, record that prerequisite failure; never spawn
   a replacement to call the CE test accepted.
8. Test investigation: enter, leave before dwell, return, disconnect and return.
   Only continuous bounded samples after explicit enrollment count. Presence
   additionally needs the exact existing landmark; a missing/deleted/badly bound
   entity must not succeed. Record binding and sample evidence.
9. For infected, identify a genuinely CE-created live candidate already at the
   site, join before the kill, and verify an attributed player kill completes
   once. Killing before joining, a different infected, environmental damage and
   another actor's death must not succeed. Confirm no spawn, teleport, movement,
   perception or blocked-door behavior was added by events. Missing/ambiguous
   candidates stay blocked rather than populating the site artificially.
10. Complete an objective, stop cleanly, restart with the same profile and inspect
    immutable intent/image/commit images: terminal progress/token and monotonic
    ID/session generation remain; in-flight records are cancelled; current
    subscriptions are empty. Repeat with interruption after each journal write
    in a disposable profile. A torn highest triple must block admission and
    preserve bytes instead of loading an older image or replaying rewards. Check
    a legacy delivery image with absent additive fields loads and cancels safely.
11. Run without the optional addon: human AI missions must remain excluded. For
    the separate optional-provider run, install only the reviewed/pinned addon
    and its required trusted hooks/profile/route evidence. Test all existing
    provider Ready/Start/Observe/Stop/Gone obligations, finite ammunition, ordinary
    damage, permission/artifact admission and confirmed cleanup. An unready
    provider must not start actors; uncertain Gone retains reservations. Absence
    of those prerequisites is a recorded blocked AI case, not acceptance.
12. Leave rewards configured at zero. Audit inventory before/after each completion
    and after restart for no duplicate items/quantity gains. Record single-client
    server work/latency at the intended 3–6 player load when that load is available;
    current caps are provisional. Additional-client races/replication become user
    bugs under active steering. Remove the marker and fully restart to return to
    gated operation. No production promotion occurs through the marker alone.
