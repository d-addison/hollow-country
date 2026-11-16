# Diagnostic measured-room catalog source completion

Date: 2026-11-16. Scope: FR-008/FR-009, SPECIFICATION §6.5 and existing
`HCInfectedRoomCatalog` entry points. Source implementation and offline behavioral
verification only. No measured room survey, DayZDiag run or production acceptance
is claimed. The handoff is design input.

## Ownership and frozen source

Changed only:

- `mods/HollowCountry/scripts/4_World/Infected/HCInfectedRooms.c`
- `tests/unit/test_room_catalog_completion.py`
- this report

Rooms ownership was sent to coordinator thread
`01a1e5a3-8cd0-7161-b339-a1731ba3d474`, with a request to relay to Nash. Only the
parent thread was listed by the available thread tool. All other infected source
remains Nash's. Source freeze and a request to notify reviewer Hegel were sent to
the same coordinator. No module hook was needed; no plan, flags, normal-PBO
configuration, production coordinates or other workers' files were changed.

Frozen SHA-256:

```
HCInfectedRooms.c
eac8684b5bb24cf92fcdffa1e092652e27c1efca343313beaa03620c8faa0455
test_room_catalog_completion.py
c8d6ee336f65e7f301faee3f53ca2b92df84f4b91b289b32256393b454b37198
```

## Installed declarations inspected before use

Exact private installed snapshot: scripts-1.30.164289 under
`/home/david/.cache/hollow-country/native-scripts`. Its scripts.pbo hash is
`09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a`.
No native source was copied into the repository.

- `3_Game/tools/JsonFileLoader.c`: `LoadData(string, out T, out string)` uses
  `JsonSerializer.ReadFromString`; `LoadFile` reads up to 100,000,000 bytes.
  The new loader instead uses the existing 64 KiB `HCInfectedStore.ReadBounded`.
- `1_Core/proto/EnSystem.c:417,425`: `OpenFile`, `ReadFile` declarations;
  existing shared bounded reader was inspected without changing it.
- `3_Game/Global/Game.c:930`: `GetObjectsAtPosition3D` with object and cargo
  output arrays; adjacent world-name declarations and wrapper.
- `3_Game/Entities/Object.c:287,305,467,873,874`: position, orientation, class,
  model/world transform surfaces already used by Rooms.
- `4_World/Entities/Game/Super/Building.c:485`: `House : BuildingBase`;
  `4_World/Classes/ConstructionBase.c:1632`: native `House.Cast` use.
- `1_Core/proto/EnString.c:86,113,199,448`: `ToAscii`, `Substring`, `Length`,
  `Get`. `1_Core/proto/EnConvert.c:613,619` and `3_Game/tools/BitArray.c:95`
  demonstrate integer bit masks and the nonreserved identifier `bit`.

## Behavior implemented

`BuildOrder` validates its request before invoking `EnsureDiagnosticLoaded`.
Only a `DIAG_DEVELOPER` server can read or register a catalog. One attempt is
claimed before I/O, including missing/rejected files; module stop already calls
`Clear`, which resets that attempt. An existing manual registration is preserved
and suppresses lazy file import. Normal PBOs and clients cannot import/register.

The sole import path is
`$profile:HollowCountry/Infected/measured-rooms.json`. No directories, files or
example production catalogs are created. Native JSON grammar/type validation is
preceded by a bounded field-set pass rejecting unknown, duplicate and missing
object keys, multiple root objects and object depth above four. All string
escapes are deliberately rejected, including escaped key aliases. This is a
restricted diagnostic format; identifiers must use literal unescaped strings.
The native parser remains responsible for JSON grammar, value types and array
shape; its behavior is not established by the Python parser double.

Required field sets, with case-sensitive names and arbitrary key order:

| Object | Required keys |
| --- | --- |
| Root | SchemaVersion, EnableDiagnostic, Build, WorldName, Buildings |
| Buildings entry | Position, Orientation, Survey |
| Survey | Build, WorldName, BuildingClass, EvidenceId, Revision, Measured, Anchors |
| Anchor | Id, LocalPosition, LocalMin, LocalMax |

Root `SchemaVersion` must be 1; `EnableDiagnostic` must be true; root and each
survey must match pinned build `1.30.164289` and the actual world name. Each survey
must assert `Measured=true`, have positive revision and an evidence identifier
of 1–128 characters. These assertions are admission data, not proof of a survey.

There must be 1–4 building records. Positions must pass the existing finite
position bounds; orientation components must be finite within [-360,360]. Each
record performs one native query of radius 0.25 m; results above 64 objects or
64 cargo proxies are rejected before iteration. A unique actual `House`, exact
class, origin within 0.01 m and orientation-vector distance within 0.01 degrees
is required. No object is created, moved, teleported or substituted. Duplicate
house bindings reject the catalog.

The original admission policy is reused: 1–6 anchors per survey, bounded unique
IDs, finite contained points, ordered local bounds within [-32,32], and separated
anchor positions. Surveys and anchors are deep-copied into staged bindings.
All records must pass before the binding array is published. A null/malformed
later record cannot partially publish earlier records. Existing ordering,
pose-stability rejection and downstream native reachability checks remain.

Work is bounded by 65,536 input bytes, four object nesting levels in the key
pass, four spatial queries, at most 64 iterated candidates per query, and the
existing four-house/six-anchor/three-waypoint limits. Native query result
allocation and native deserializer internals are engine-owned; this does not
establish a native execution-time or allocation bound. No per-tick file retry or
world scan was introduced.

## Actual RED/GREEN

First command, run before implementation:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_room_catalog_completion.py -v
```

Actual RED: 12 tests, 39 failures including subtests, all initially reporting
`AssertionError: missing actual room catalog method: DiagnosticServer`. This
records the missing executable loading/binding surface, not native behavior.

During implementation, the restricted harness needed an explicit mapping of
native out-return `BuildOrder` results and nonnull empty array references; its
initial `None != []` failures were harness defects, not gameplay defects.
After those corrections a new null-record behavioral test produced actual RED:
13 tests, one error, `AttributeError: 'NoneType' object has no attribute 'Survey'`
in the translated authored `BindDiagnostic`. A null guard fixed that defect.

Final actual GREEN with the same discovery command: **13 tests passed**.
Methods are extracted from the current authored source and executed through a
restricted translation. Engine objects, vector transforms, file reads and native
JSON out parameters are explicit synthetic doubles. The parser double checks
Python JSON grammar and supplies a synthetic DTO; it does not implement or
certify native deserialization/coercion. Test coordinates and the asserted
`Measured` flag are explicitly synthetic and are never exported as surveys.

The Given/When/Then loading case exercises actual `BuildOrder` → one-shot loader
→ strict keys → parser boundary → staged binding → ordering. Other cases cover
normal/client gating, opt-in/version/world/build, finite poses, ambiguous or
duplicate houses, dense lookup results, null records, deep copy, malformed and
oversize reads, restart reset, capacity, rejected invalid requests and existing
survey constraints.

Additional final command:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_infected_completion.py -v
```

Actual GREEN: **21 tests passed**, including identifier, Enforce expression
complexity and prior room/navigation contracts. `git diff --check` passed.

## Remaining acceptance and engine constraints

- Latest actual compiler 014 predates this Rooms change. Coordinator reports
  native 016 held for 210 seconds without an empty journal; that remains pending
  and does not compile or validate this loader. A new real compiler pass and
  review of this frozen snapshot are required.
- Actual DayZDiag deserialization, native vector serialization format, malformed
  types/array nesting and native query behavior at measured house origins need
  engine probes. The field-set preflight is not a replacement JSON grammar
  parser and does not separately bound array nesting inside native parsing.
- No actual measured catalog exists here. `Measured` and `EvidenceId` are local
  operator assertions; no artifact hash, signature or geometric truth is verified
  by this runtime loader. Evidence review must precede diagnostic use. Exact
  pinned build matching is an existing catalog admission check, not a new runtime
  game-version attestation.
- Actual local bounds, anchor containment, door/floor connectivity, collision,
  pathfinding, audible locomotion, expiry/disengagement and two-client fairness
  remain unaccepted. Successful source binding does not prove route traversal.
- Production measured catalogs and normal-PBO enablement remain absent. A
  missing/invalid catalog produces no semantic extension and preserves native
  fallback; no requirement is waived or marked engine accepted.

No commits. Source remains frozen for coordinator compiler passes and Hegel's
independent review; completion-plan was left unchanged during this scoped work.
