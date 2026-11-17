# Groups v1 fix round 2 — #31 / #37

Source and synthetic checks implemented. **Runtime acceptance and production enablement remain pending.** No DayZ, Wine, network, staging, commit, or other git metadata mutation was used. The dispatcher owns the commit; its message is in `.banso-writer/commit-message`.

## Inputs and scope

Read worktree `AGENTS.md`, the runtime implementation contract, the Sonnet review and mutation definitions, and the groups sources/tests. Applied the Banso CLI skill's dispatched-worker instructions: no orchestrator lifecycle commands. `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent here, as previously recorded; they were not recreated or accepted as runtime evidence. The active task is the specification for this confined fix. The specification/plan/tasks trace below stays in the requested report because orchestrator state and documentation are outside the source ownership boundary.

An out-of-scope `.banso-brief.md` change is visible; this worker did not author or modify it. The existing reviewer inputs were not edited. Mutation working copies contain only copies of repository-authored sources/fixtures and are disposable.

## Specification, plan and task trace

| Finding / required behavior | Implementation and synthetic evidence | Status |
| --- | --- | --- |
| P2-1: ray fairness, bounded caching, no duplicate position round | Default 56 rays covers 8 x 7 directed pairs. Tick resets quota and rotates the peer start; emitted rounds additionally rotate independently so the two-second position interval cannot alias an eight-peer list. Directed verdict cache holds at most 256 entries for less than one second, keyed by both account IDs and connection sessions; both positive and negative verdicts expire. FULL broadcasts suppress POSITIONS in that Tick. Tests exercise eight members with seven rays, real one-second Tick/two-second snapshot cadence, expiry, reconnect, cap and reset. | Authored / offline GREEN |
| P2-2: discovery work only for nearby unrecorded places | Distance rejection precedes HasVisit, Clone and RecordVisit; RecordVisit also rejects distance before text/catalog validation. Candidate is cloned lazily on the first nearby unknown place, at most once per six-peer pass. LIMIT backs off 60 seconds. Already-known and distant passes do not clone; fixtures pin zero RecordVisit calls for distant places. Inactive journal cleanup also runs before explorer-slot admission. | Authored / offline GREEN |
| P2-3: missing guard coverage | Individual tests cover M03/M04, M05/M06, M13–M15, M18/M19, M21/M23/M24, M30/M31, M39–M45, M49–M52, M56–M58 and M61/M62. M58 covers both new ID lists and legacy full-place migration input. M12's invalid owner-role request is now covered too. | Authored; mutation results below |
| P2-4: same-vehicle LOS | Native ray's `with` argument ignores the shared parent; `ignore` still ignores the source player. Parent is cast from native IEntity to Object. No unconditional same-vehicle visibility bypass was added. | Authored; DayZDiag pending |
| P3: protocol | Protocol constant and request/snapshot/reply defaults are 3; native synthetic fixture pins/logs wire 3. Durable schema remains 1. | Authored / offline GREEN |
| P3: journal size and retention | New visits store IDs in PlaceIds; current catalog resolves titles/positions for KnownPlaces, so removed places disappear and renamed places update. Legacy Visits objects validate, migrate on Open and are cleared before subsequent production saves. Connected activity refreshes LastSeenUtc in memory each Tick and is persisted on the next successful transaction. Offline ungrouped explorers expire after 30 days; byte or explorer-slot pressure evicts eligible offline ungrouped accounts, oldest first. Connected accounts and group members are protected. Serialization/admission stays bounded by MaxStoreBytes; protected data can still cause LIMIT instead of an oversized write. | Authored / offline GREEN |
| P3: equipment cost | One lazily cached equipment result per peer per Tick, with a one-second freshness bound for RPC work between ticks. Client navigation equipment also refreshes at most once per second or when viewer changes. | Authored / offline GREEN |
| P3: map rendering and semantics | Each pooled icon remembers its texture, reloading only when the slot's texture changes. Clear resets the texture cache. HasMap observes GetMapIgnoreMapOwnership even without a physical map. GPS text asks for a powered GPS; own coordinates still require powered, owned, non-ruined equipment. Teammate RequireGPS retains native navigation's possession semantics. | Authored / offline GREEN |
| P3: native Names overflow | At most 512 native entries are examined and at most 256 valid places retained. Overflow truncates with an explicit log line. Operator JSON remains validated/fail-closed at 256 entries. | Authored / offline GREEN |

Implementation order: add RED fixtures; fix bounded LOS/discovery and DTO/journal behavior; extend adapters and guard tests; verify additional capacity/cadence failures; run focused checks, reviewer mutations and the full suite. Later presentation tests were also run against original HEAD source in a scratch copy; that is retrospective regression evidence, not a claim that those tests preceded every presentation edit.

## Files authored

Source files under `mods/HollowCountry/scripts/`:

- `3_Game/Groups/HCGroupData.c`
- `3_Game/Groups/HCGroupProtocol.c`
- `4_World/Groups/HCGroupNativeChecks.c`
- `4_World/Groups/HCGroupPlaces.c`
- `4_World/Groups/HCGroupRules.c`
- `4_World/Groups/HCGroupService.c`
- `4_World/Groups/HCGroupStore.c`
- `4_World/Groups/HCGroupVisibility.c`
- `5_Mission/Groups/HCGroupMapLayers.c`

Groups tests: `tests/unit/test_group_round2.py` (new), `test_group_server.py`, `test_group_client.py`, `test_group_native_checks.py`, `test_v1_groups.py`. Shared test interpreter changes adapt native type/receiver/loop syntax and bind authored helper bodies; they do not implement an alternate gameplay policy. Existing synthetic wire fixtures now use protocol 3.

Other authored output: this report, its scratch logs/reproducer and `.banso-writer/commit-message`.

## Actual RED and GREEN records

All paths below are relative to this report's directory. Fixtures are explicitly synthetic; none establishes engine compilation, native inventory, raycast pose, persistence durability or replication correctness.

Initial command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_group_round2 > scratchpad-review/v1-groups-r2/RED.txt 2>&1
```

Actual `RED.txt` lines: `Ran 48 tests in 0.846s`; `FAILED (failures=8, errors=8)`. Behavioral failures included default rays `56 > 32`, two ray calls for the same cached pair, a second LIMIT commit without backoff, distant/already-known clones, missing ID-only visits, wire 2 and the shared-vehicle ignore argument. Some errors were missing new methods or syntax adapters, so this log is not presented as 16 independent behavioral assertions.

Additional actual failures before their fixes:

- `RED-explorer-cap.txt`: `Ran 1 test in 0.036s`; `FAILED (failures=1)`; expected one discovery commit, got zero when an inactive account occupied the only explorer slot.
- `RED-cadence.txt`: `Ran 1 test in 0.968s`; `FAILED (failures=1)`; recipients 1, 3, 5 and 7 were starved at one-second Tick/two-second position cadence.
- `RED-original-presentation.txt`: original HEAD presentation/equipment/catalog code in a scratch copy, current synthetic tests: `Ran 4 tests in 0.043s`; `FAILED (failures=3, errors=1)`. Texture reuse, native ownership override and powered-GPS wording failed assertions; original oversized Names returned null. This was a later regression cross-check.

Focused GREEN command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_group_round2 tests.unit.test_group_server tests.unit.test_group_client tests.unit.test_v1_groups tests.unit.test_group_ui tests.unit.test_group_persistence tests.unit.test_group_native_checks tests.unit.test_script_syntax tests.unit.test_script_identifiers > scratchpad-review/v1-groups-r2/GREEN-focused.txt 2>&1
```

Actual lines: `Ran 172 tests in 6.703s`; `OK`. This includes installed-interface identifier and override checks and authored syntax checks. A later syntax-only adapter for native `this` was separately checked in `GREEN-start.txt`: `Ran 1 test in 0.038s`; `OK`.

The full suite ran once:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit > scratchpad-review/v1-groups-r2/GREEN-full.txt 2>&1
```

Actual lines: `Ran 2569 tests in 119.219s`; `OK (skipped=1)`. Expected negative-fixture tool diagnostics also appear in the log. `git diff --check` passed. No game/compiler executable was invoked.

## Mutation results

The unchanged reviewer runner ran against an isolated repository copy:

```sh
python3 -B scratchpad-review/v1-groups-sonnet-review/run_mutants.py > scratchpad-review/v1-groups-r2/mutants-final.txt 2>&1
```

Actual results: **58 assertion kills**, one M62 interpreter error, three PATTERN-MISSING definitions, and M00 baseline SURVIVED (the required passing control). The interpreter error and missing patterns are not counted as successful kills.

`run_mutants_adapted.py` is a retained copy of the reviewer runner with its scratch destination changed and exactly three pattern updates:

| Definition | Updated target | Result |
| --- | --- | --- |
| M17 | `found.PlaceIds.Count() >= c.MaxDiscoveries` replaces the old Visits count | KILLED by discovery-cap assertion |
| M28 | Replace `verdict.Visible = HCGroupVisibility.HasLOS(...)` with true | KILLED by LOS-denial assertion |
| M60 | Remove Broadcast from the discovery-specific storage-result/OK-result tail | KILLED by single-commit broadcast assertion |

Command: `python3 -B scratchpad-review/v1-groups-r2/run_mutants_adapted.py M17 M28 M60 > scratchpad-review/v1-groups-r2/mutants-adapted.txt 2>&1`. All three actual lines are KILLED with FAIL, not interpreter errors.

M62's first mutation reached native `this`, which the synthetic adapter had not translated. The syntax adapter now maps that receiver to Python self. A separate rerun used the **unchanged M62 mutation definition**, together with M00 as control:

```sh
python3 -B scratchpad-review/v1-groups-r2/run_mutants_adapted.py M00 M62 > scratchpad-review/v1-groups-r2/mutants-start.txt 2>&1
```

Actual lines: `M00 baseline unmutated SURVIVED`; `M62 DiscoveryLayer start refusal off KILLED FAIL: test_M62_start_refuses_bad_catalog ...`.

Combined valid results: **62 / 62 mutation definitions killed, zero surviving mutations; M00 unmutated control passes.** M12, previously considered near-equivalent, is also killed by the explicit invalid-role assertion. The named former survivors are pinned by individual authored-body tests, including M21's other-group discovery privacy boundary.

Earlier `mutants-RED.txt` ran while new tests were still RED and is excluded from the score. `mutants.txt` is an intermediate run, also superseded by the final logs. These logs are retained to make the chronology visible. For pre-existing correct guards, the isolated mutation assertion is the actual RED evidence; no production guard was deliberately broken in this worktree. Generated mutation/original-source copy trees were removed after their logs were retained; reviewer REVIEW.md, run_mutants.py and mutants.txt inputs were not edited.

## Native interface evidence

Read the authoritative local cache at `~/.cache/hollow-country/native-scripts/scripts-1.30.164289`; no native files were copied into authored source or committed artifacts.

- `3_Game/Global/DayZPhysics.c:136–137` documents both `with` and `ignore` as excluded collision objects; line 199 declares RaycastRV with those arguments and NEARESTCONTACT. The vehicle uses `with`, while source uses `ignore`.
- `1_Core/proto/EnEntity.c:571` returns IEntity from GetParent; `4_World/Classes/Environment/Environment.c:538` demonstrates `Object.Cast(m_Player.GetParent())`.
- `3_Game/human.c:1417` declares GetBoneIndexByName; the installed Object interface exposes GetBonePositionWS. This establishes API existence, not remote server pose correctness.
- `3_Game/CfgGameplayHandler.c` exposes GetMapIgnoreMapOwnership; native `5_Mission/GUI/MapMenu.c` consumes it. Existing owned/working inventory and radio checks remain bounded.

## Owner patches

None required for this round. `HCModule.c`, `config.cpp`, `inputs.xml` and `HCSettings.c` were not edited. There is no pending patch to those files.

## Remaining gaps / runtime checklist

- **Pending DayZDiag:** dedicated/local server head-bone pose for remote standing/crouched/prone players, invalid-bone fail-closed behavior, and head positions while seated. API inspection does not establish a live server skeleton pose.
- **Pending two-client DayZDiag and normal PBO/server tests:** same-parent vehicle teammates, different vehicles, intervening vehicle/world geometry, LOS occlusion and revocation/cache expiry; powered radio frequency matching; GPS/map settings; dead/unconscious/disconnected privacy; FULL versus POSITIONS replication; group role changes and discovery sharing/revocation.
- **Pending rendered UI:** texture slot changes, panning/zoom clipping, navigation grid, mission expiry, input bindings, scale and labels; possession override and power transitions across the one-second equipment cache.
- **Pending real journal migration/restart/rollback:** ID migration, retention and byte-pressure eviction. Legacy LastSeenUtc defaults to zero, making offline ungrouped legacy explorers eligible as the oldest inactive accounts; connected/grouped accounts remain protected. Old builds do not understand PlaceIds, so rollback can discard newly stored discoveries. Durable schema 1 remains additive; no old-build rollback compatibility is claimed.
- **Pending target-load measurements:** intended 3–6 players, eight-member default ray capacity, multiple groups and quota exhaustion, 256-entry catalogs, inventory bounds, serialization/eviction hitch cost. Limits are provisional, not measured performance promises. Extremely small custom ray quotas may still omit individual source pairs; fairness tests cover the full seven rays per recipient in an eight-member group.
- Missing private spec files remain missing design inputs, not accepted engine experiments. No runtime acceptance or production gate is marked complete.
