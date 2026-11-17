# B04 WP5 — production room data admission (#20)

Status: source implemented; runtime acceptance and production feature enablement **PENDING**. No native compilation, DayZDiag, normal PBO/server run, client connection or multiplayer observation was performed. Investigation and NativePackRoutes remain unqualified. This catalog provides data only.

## Scope and design trace

Changed only these source/test files:

- `mods/HollowCountry/scripts/4_World/Infected/HCInfectedRooms.c`
- `tests/unit/test_room_catalog_completion.py`
- new `tests/unit/test_infected_production_rooms.py`

This report and `.banso-writer/commit-message` are the requested ancillary deliverables. Shared Module, State, Navigation, Policy, Profiles and sampler tools were not edited. No git commands, DayZ, Wine or PowerShell were run, and nothing was written under `/mnt/d`. Base `main 73241f6` is user-supplied, not independently checked through git.

Read worktree `AGENTS.md`, `docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`, audit #20 room/search rows, Native API evidence and ranked WP5. The two requested specification paths are absent here. Read external design copies at `/code/dayzsa_mods/docs/SPECIFICATION.md`, `docs/specs/001-survival-overhaul/spec.md`, `plan.md` and `completion-plan.md`; their identity with historical worktree versions is unproven. The Banso CLI skill's dispatched-worker rule was followed: task contract rather than orchestrator lifecycle mutations.

Trace: #20 AC-007.c; #20.P1–P4; AI-005; confirmed AI-03; FR-008; plan T020 / prior completion-plan C10. The scope covers normal-server data import, complete class dispositions and bounded room ordering. Native traversal, observation provenance, room measurements and safety acceptance are retained as outstanding work, not accepted by these tests.

## Actual RED / GREEN

Required command, executed before production source changes:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_room_catalog_completion tests.unit.test_infected_production_rooms -v
Ran 23 tests in 0.625s
FAILED (failures=10)
AssertionError: missing actual room catalog method: ClearProduction
```

All 13 original diagnostic tests passed in that RED run; 10 new production behavioral tests failed for the absent admission methods. An earlier invocation hit existing unqualified sibling imports; the owned test imports were fixed to work with both the required module command and discovery before recording behavioral RED.

An additional hardening RED used the same command after adding native-read and integer-overflow counterexamples:

```text
Ran 28 tests in 2.232s
FAILED (failures=2)
test_native_read_failure_or_inconsistent_byte_count_does_not_parse ... FAIL
'rooms_read' != 'rooms_admitted_measurements_path_audio_doors_pending'
test_truncated_json_never_reads_beyond_string_and_integer_overflow_is_not_coerced ... FAIL
AssertionError: True is not false
```

Final focused GREEN, same required command:

```text
Ran 28 tests in 2.492s
OK
```

The tests execute translated authored methods with explicit synthetic native/JSON boundaries, rather than a second independent admission model. They cover normal-server load-once/log-once, client refusal, runtime/document build and world pins, class denominator completeness and exclusions, typed JSON grammar/keys/duplicates, every truncated prefix, integer overflow, evidence fields/known synthetic markers, measured box/anchor bounds, caps including 256 anchors, atomic publication, deep copies, ambiguous/moved houses, read failures, and unchanged diagnostic rejection on normal PBO/client paths. Their coordinates, hashes and measured claims are fabricated test input, never production catalog data.

Final broad checks (all exit 0):

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
Ran 2376 tests in 69.094s
OK (skipped=1)

python3 -B -m tools.validate.bdd
Ran 1276 tests in 28.935s
OK (skipped=1)
Bound offline scenarios: 61; runtime acceptance: NOT EXECUTED

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_script_*.py' -v
Ran 8 tests in 0.824s
OK
```

Expected negative-test CLI messages occurred during the broad suites. Native safety or JSON/config behavior is not established by Python execution. Temporary console capture files were folded into this report and removed so only the requested report remains in its scratch directory.

## Production DTO schema v1

Fixed server-only input:

```text
$profile:HollowCountry/Infected/production-rooms.json
```

No alternative path argument, RPC input, generated profile, shipped pose, client import or diagnostic fallback is provided. Operators install the file. Existing `measured-rooms.json`, DIAG admission and self-tests retain their original role.

All fields below are required; no others are accepted. This is a schema description, **not a production fixture**:

```text
HCInfectedProductionRoomDocument {
  SchemaVersion: integer = 1,
  Build: string = "1.30.164289",
  WorldName: string = exact GetWorldName(),
  Classes: HCInfectedProductionRoomClass[],
  Buildings: HCInfectedProductionRoomRecord[]
}
HCInfectedProductionRoomClass {
  BuildingClass: string,
  Disposition: "covered" | "unmeasured" | "not_enterable" |
               "path_pending" | "door_pending" | "unsupported_geometry"
}
HCInfectedProductionRoomRecord {
  BuildingClass: string,
  Position: [number, number, number],
  Orientation: [number, number, number],
  BoxMin: [number, number, number],
  BoxMax: [number, number, number],
  Anchors: HCInfectedProductionRoomAnchor[]
}
HCInfectedProductionRoomAnchor : HCInfectedRoomAnchor {
  Id: integer,
  LocalPosition: [number, number, number],
  LocalMin: [number, number, number],
  LocalMax: [number, number, number],
  SourceRunId: string,
  SourceSha256: string,
  EvidenceKind: "native-room-survey-v1"
}
```

Bounds and invariants:

- File: nonempty, at most 1,048,576 bytes; read at most 1,048,577, always close an opened handle, and require nonnegative byte count equal to string length before decoding. The schema is ASCII; escapes and control characters in strings are refused. Whitespace follows JSON's four ASCII whitespace characters. Strings are capped at 128 characters during preflight.
- Root identity: exact schema version, pinned build **and actual GetVersion(out currentBuild)** match, exact current world. World token is 1–64 characters from `[A-Za-z0-9_-]`. No version normalization or inferred build match.
- Class denominator: **every loaded `CfgVehicles` class for which native `IsKindOf(className, "House")` returns true**, including base/non-enterable/closed classes. Every such class must occur once in `Classes`; unknown, duplicate or omitted classes reject the whole import. Non-House config classes are outside this explicit denominator. At most 32,768 config children and 2,048 House class rows. Class names are 1–128 token characters.
- Allowlist: only `Disposition="covered"` classes may supply house records, and each covered class must have at least one admitted instance. Other dispositions explicitly exclude the class. `covered` means **at least one measured instance**, never every placement of that class in the world. Unlisted instances receive no anchors. All-excluded/zero-building documents may report honest zero coverage without granting any route data.
- Instances: at most 64, unique resolved native House object; no class-wide expansion to other poses. Position is finite within ±200,000 on each axis, orientation finite within ±360. Resolve with radius 0.25, refuse more than 64 objects or cargos, require exact class and squared position/orientation differences ≤0.0001; multiple matching candidates reject. Recheck class/pose before ordering.
- Anchors: 1–16 per house; at most 256 total; unique integer Id 1–64 per house and positions at least one unit apart. The route request budget stays 1–3. Oversized arrays are stopped by typed preflight before native DTO allocation. Integer lexemes are at most nine characters, avoiding native int overflow/coercion; number lexemes at most 32.
- Geometry: measured house BoxMin/BoxMax strictly ordered on every axis and within ±512. Each anchor's semantic room LocalMin/LocalMax is strictly ordered and wholly inside the measured house box. LocalPosition must lie inside that room box. Positive comparisons reject NaN/infinity. Bounds are conservative source limits, not measured performance or safety guarantees.
- Evidence per anchor: nonempty 8–96 character token SourceRunId with case-insensitive `native-` prefix; known `synthetic`, `fixture`, `selftest` markers refused case-insensitively. SourceSha256 must be 64 lowercase hex characters and not all zero. EvidenceKind must be exactly `native-room-survey-v1`. Owned production anchor copies retain all three fields.

The trusted author is the server operator. These checks require and bound provenance declarations; **they do not cryptographically authenticate a run or recompute SHA-256 over external native evidence**. FileExist is only a presence check. No SHA-256 API was found in the inspected pinned 1_Core/3_Game tools surface; string.Hash is not substituted for SHA-256. The converter/operator must verify the real artifact hash and native origin before installation. Known-marker rejection cannot detect an operator falsely labeling synthetic coordinates as native measurements. Data admission explicitly leaves measurements and safety qualification pending.

## Covered/excluded report and reason codes

`ProductionCoverage(out TStringArray covered, out TStringArray excluded)` returns fresh server-only arrays after admission. Covered rows contain exact class names; excluded rows contain `BuildingClass=Disposition`. This exposes every admitted denominator row without a huge log line or mutable internal references. `ProductionReason()` returns the fixed status. Loading emits one summary log with that status and class/instance counts per lifecycle, with no user input/native serializer error text. A missing or rejected file is not polled again; Clear resets the attempt on module lifecycle shutdown.

No real production catalog is supplied or loaded by this run. Actual class names/counts/measurements therefore remain unknown here; there are **zero shipped production bindings**. The full-denominator check/report is implemented, not a claim that a four-class sampler cohort covers installed content.

| Code | Meaning |
|---|---|
| `rooms_not_loaded` | Initial/reset data status. |
| `rooms_missing` | Fixed operator file absent. |
| `rooms_read` | Open failure, negative native read result or inconsistent byte count. |
| `rooms_size` | Empty or oversized input. |
| `rooms_json` | Invalid typed grammar, unknown/duplicate/missing key, wrong scalar/container/vector shape, forbidden escape/string, number lexical overflow, or native deserialization failure. |
| `rooms_schema` | Null DTO or wrong schema version. |
| `rooms_build` | Wrong declared or running build. |
| `rooms_world` | Invalid/mismatched world. |
| `rooms_limits` | Class/instance/per-house/total anchor cap or missing required collections. |
| `rooms_denominator_cap` | Missing/oversized installed config census. |
| `rooms_coverage` | Unknown/missing/duplicate class, invalid exclusion, excluded class used, missing measured instance for covered class, or incomplete denominator. |
| `rooms_geometry` | Invalid measured/semantic box, nonfinite/outside anchor, bad/duplicate id or insufficient anchor spacing. |
| `rooms_evidence` | Missing/invalid run/hash/kind or known synthetic marker. |
| `rooms_binding` | Missing/ambiguous/duplicate native House, class/pose mismatch or invalid pose. |
| `rooms_admitted_measurements_path_audio_doors_pending` | Data copied and admitted; measurements, paths, audio and door safety still need native evidence. Grants no capability. |

Failures publish neither new coverage nor partial bindings. A second direct BindProduction after successful publication is refused without replacing the accepted snapshot. Client calls perform no profile/config/query/log work. There is no production write/save path.

## Sampler mapping for a later converter

The requested sampler paths are absent in this worktree. Read-only project copies were inspected at `/code/hc-worktrees/interior-r3/tools/setup/interior_sampler.py` and `tools/audit/interior_points.py`. They are not imported as test dependencies or edited here.

The census is a **suitable partial evidence source**, not a complete room catalog:

1. Require real native origin and matching run/artifact receipts outside this loader. Validate census `kind="interior-sampler-census"`, `schema=1`, `summary.complete=true`, finite/bounded fields, and no relevant ray/output/step/floor caps; do not treat absent flags/receipts as success. Existing interior_points.parse_census / _usable / eligible help with some floor-point checks, but are not sufficient infected room or provenance validation.
2. Census `version` → DTO Build (exact pinned match); `world` → WorldName. Reject mismatches; do not overwrite metadata to make it match.
3. For a found placement, `class` → BuildingClass; `actual` → Position; `orientation` → Orientation; `box_min`/`box_max` → measured BoxMin/BoxMax after validating their source and all three finite ordered components. Never use an intended target pose in place of the observed actual pose.
4. Individual hit `[x,y,z,clearance,normalY,strictReachCode]` supplies a **candidate** LocalPosition. Keep the census placement/hit index in the evidence manifest. Reach code 1 is a floor-sampler result; unknown, nonav, unqualified, capped or failed results cannot become successful infected traversal evidence. `player_codes` are separately labeled player-filter observations and must never silently substitute for strict/infected evidence. Aggregated interior_points selections may average across placements; do not substitute those means for exact instance measurements.
5. The sampler does **not** measure semantic room LocalMin/LocalMax, infected clearance/door/contact/audio safety, full class coverage or an authenticated SourceRunId. Obtain reviewed native room extents and those experiment dispositions separately. Do not manufacture room boxes from grid step, house extents or loot point radius. Until semantic measurements exist, exclude the class/instance instead of generating anchors.
6. Produce a reviewed native-room-survey-v1 evidence artifact linking the original census hash/run, exact placement and hit indices, native semantic-room measurements and measurement method. Assign its real `native-...` run id to every derived anchor, compute its SHA-256 from the actual artifact bytes using standard-library tooling, and use that artifact's digest as SourceSha256. Preserve the original raw census digest in that artifact. The census alone cannot be relabeled as native-room-survey-v1.
7. Export all installed House config names to form Classes, mark measured-supported classes covered only when a matching instance/anchor exists, and give **each other class** a reviewed allowed exclusion. The sampler's default four classes (two tenements, two calibration classes) are not the denominator. Retain all omitted map instances as unmeasured scope; never expand a measured pose class-wide.

No converter is implemented in the owned scope. No synthetic production poses, measured records or full vanilla dumps ship.

## Exact WP1 / WP2 interfaces

All methods are static on `HCInfectedRoomCatalog`:

```c
void EnsureProductionLoaded();
string ProductionReason();
void ProductionCoverage(out TStringArray covered, out TStringArray excluded);
void BuildProductionOrder(vector observedClue, int budget, out TVectorArray points);
void ClearProduction();
void Clear(); // existing lifecycle reset now also resets production data
```

WP1 (Module owner): call EnsureProductionLoaded once on server startup when reporting data prerequisites; expose ProductionReason and copied covered/excluded rows in operator diagnostics. Keep the existing Clear on stop. **Never** promote Investigation or NativePackRoutes because the catalog loaded, because preferences are true, or because self-tests passed. Both qualifications are unqualified today. The catalog status explicitly retains pending measurement/path/audio/door evidence. No shared settings, qualification fields or runtime capability flags were changed here.

WP2 (Navigation owner): the existing `BuildOrder(observedClue,budget,out points)` remains DIAG-only and retains its diagnostic loading behavior. When WP1 has independently admitted **both Investigation and NativePackRoutes** and native room prerequisites have been qualified, request production data with `BuildProductionOrder(observedClue,budget,points)` instead. Declare `TVectorArray points` before the out call. Supply only the valid frozen observed clue and existing bounded budget; retain expiry, native path/navmesh/door checks, interruption/retry/release controls and fallback. Empty data must preserve native fallback. Do not add an ungated normal-server caller or a live hidden-target position.

OrderBindings is shared ordering implementation only: the wrapper keeps diagnostic and production snapshots separate; no actor/group/waypoint, perception, movement, door or audio APIs were added. If WP1/WP2 need a different signature, coordinate that change rather than editing their files in WP5. The new production tests are executed by unit discovery; adding a production-room Gherkin binding belongs to the integration owner because feature/binding files are outside this scope.

## Pinned native API citations

All paths below are relative to `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`; each cited declaration/implementation was inspected read-only. They establish source availability, not successful native execution.

| API used | Pinned file:line |
|---|---|
| GetGame | `3_Game/gameplay.c:636` |
| IsServer | `3_Game/Global/Game.c:1120` |
| GetVersion (out) | `3_Game/Global/Game.c:942` |
| GetWorldName wrapper | `3_Game/Global/Game.c:934` (out declaration `:932`) |
| ConfigGetChildrenCount / ConfigGetChildName (out) | `3_Game/Global/Game.c:611`, `:594` |
| IsKindOf | `3_Game/Global/Game.c:1437` |
| GetObjectsAtPosition3D (out arrays) | `3_Game/Global/Game.c:930` |
| House inheritance | `4_World/Entities/Game/Super/Building.c:485` |
| Class.Cast (House.Cast) | `1_Core/proto/EnScript.c:94` |
| GetPosition / GetOrientation / GetType | `3_Game/Entities/Object.c:287`, `:305`, `:467` |
| ModelToWorld / WorldToModel | `3_Game/Entities/Object.c:873`, `:874` |
| JsonFileLoader.LoadData | `3_Game/tools/JsonFileLoader.c:69` (LoadFile's 100MB bound `:3`, not used) |
| FileExist | `1_Core/proto/EnSystem.c:397` |
| OpenFile / ReadFile / CloseFile | `1_Core/proto/EnSystem.c:417`, `:425`, `:443` |
| FileMode.READ | `1_Core/proto/EnSystem.c:382` (READ `:384`) |
| Print | `1_Core/proto/EnDebug.c:96` |
| string.ToAscii / Substring / ToLower / Length / Contains / Get | `1_Core/proto/EnString.c:86`, `:113`, `:171`, `:199`, `:286`, `:448` |
| int.ToString / vector.DistanceSq | `1_Core/proto/EnConvert.c:30`, `:210` |
| array.Count / Clear / Find / Insert / Remove; indexed access | `1_Core/proto/EnScript.c:380`, `:385`, `:394`, `:407`, `:463`; `:399` Get / `:389` Set |
| TStringArray / TVectorArray | `1_Core/proto/EnScript.c:731`, `:738` |

HCInfectedStore.ReadBounded / ValidPosition and HCInfectedPolicy.AdmitRoomCatalog / PreferRoom are existing authored shared helpers, not new engine APIs. Native navmesh/path APIs remain in the consumer scope; none are added here. Candidate native surfaces from audit N1/N10 still require experiments.

Compile-shape review: no ternaries, duplicate method locals, leading `||`/`&&` lines, or engine-type identifier collisions found; out values declared before calls; numeric log counts use explicit ToString. Max binary `+` per statement measured as **5**, below the required 8. All loops are bounded by byte/field/axis/collection caps; typed parser recursion has fixed schema depth. These checks do not substitute for the DayZ compiler.

## Remaining gaps and acceptance

- Review/produce real native survey artifacts and complete class/exclusion census; authenticate their artifact hashes outside the loader. Native GetVersion's exact returned format, config House denominator and native JSON DTO behavior must be observed. Any different/unknown runtime version is refused, not normalized optimistically.
- Implement/review converter and integration calls in the owning scopes; preserve unqualified gates. No real production content or route activation is claimed by this package.
- Execute DayZDiag compilation and measured room, stair, doorway, closed/locked door, blocked-route, uncertainty/escape and timeout trials. Run normal PBO/server parity/regressions. Two clients are required for network/audio/visibility acceptance.
- Measure startup census/import cost and ongoing order cost at the target 3–6-player load. Counts/geometry/performance limits here are provisional conservative caps, not calibrated budgets.
- Bind production BDD scenarios in the shared catalog if the integration owner chooses; existing BDD validation remains meaningful only for its existing offline bindings.

Runtime acceptance remains **PENDING**.

## Input and deliverable SHA-256

Hashes pin inspected local source/design inputs; they do not bind a running engine or accepted package.

- `mods/HollowCountry/scripts/4_World/Infected/HCInfectedRooms.c`: `67b3afc0512d6a305cef6019aeff930bfc87934f5590bd01e21834863a46b5c2`
- `tests/unit/test_room_catalog_completion.py`: `4a4cce40065c2c84f95bab3ac69f3e56ddf7fbe7830f834ff1e21851793a1885`
- `tests/unit/test_infected_production_rooms.py`: `f802f478e6a6b4e5657e6514facc500c012469be705d14ce052b3af29c7dfac5`
- `/code/hc-worktrees/b04-audit/scratchpad-review/b04/AUDIT.md`: `2ac46d8c4c09a206edba732ce1848491254fb7c861a1df23c6e5feba2ac0a488`
- `/code/dayzsa_mods/docs/SPECIFICATION.md`: `8d6bfe974dd91b8433d02af6a6661be84f9b775b1a1146d3e5c2d47928123d79`
- `/code/dayzsa_mods/docs/specs/001-survival-overhaul/spec.md`: `7059a05771ebb06f55a4f1cb477cef5bec9dddaa79ea7bb74539bd05476fde8c`
- `/code/dayzsa_mods/docs/specs/001-survival-overhaul/plan.md`: `4b2c079fdec305a3f78d02f4a7bce41c541b4c1efaf4f780959f6d5d36c94821`
- `/code/dayzsa_mods/docs/specs/001-survival-overhaul/completion-plan.md`: `19ca99f471a2f7ead21606aaa001d87fa608c073522df6e6635246b0e41e3e83`
- `/code/hc-worktrees/interior-r3/tools/setup/interior_sampler.py`: `c262115b9d477d35767c9467675572aba63c301c6b2bc1c62c078ce28d07fb36`
- `/code/hc-worktrees/interior-r3/tools/audit/interior_points.py`: `d39eded374dabbee7a61a3aa216b45b1ee48d6f196fddf16c42263cdc414094b`
