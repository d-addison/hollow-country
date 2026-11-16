# Measured interior and contextual policy candidate seam

Status: bounded utility/schema source frozen for independent review; native acceptance remains pending.
Scope: only `tools/package/interior_catalog.py`,
`tests/unit/test_interior_catalog.py`, and this report. No gameplay source edits.

## Specification and plan

This diagnostic source follow-up implements the bounded data seam identified in
the completion-plan audit under original T013–T015, INT-01–04, LOOT-02/04/05,
FR-005/006 and AC-005. It does not complete those requirements. The canonical
Banso spec/plan/tasks and runtime contract were read; shared artifacts remain
coordinator-owned. Other workers own room, observer, hygiene and package work.

Sequence: inspect existing catalog/rules/store and pilot asset evidence; write
executable synthetic-survey behavior tests; record RED; implement the smallest
candidate exporter; execute focused GREEN and review malformed/unsafe cases.
Full suite, main BDD and CI are coordinator-owned.

## Actual TDD evidence

Command (2026-11-16):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_interior_catalog.py -v
```

Before implementation, exit 1:

```text
ERROR: test_interior_catalog (unittest.loader._FailedTest.test_interior_catalog)
ImportError: cannot import name 'interior_catalog' from 'tools.package' (unknown location)
Ran 1 test in 0.000s
FAILED (errors=1)
```

The fixtures are explicitly synthetic, generated only in tests and temporary
folders. They are not real house measurements or runtime acceptance artifacts.

Follow-up schema review RED, same command: 14 tests, exit 1,
`FAILED (failures=1, errors=4)`. The new measured-instance fields were not yet
accepted; malformed observation Kind leaked `TypeError: unhashable type: list`.
Implemented the explicit instance/asset context and clean enum type validation,
and checked current source search/item allowlists and supplementary caps.
An intermediate sandbox run could not create temporary directories; it was
rerun with filesystem permission rather than counted as a utility failure.

Final focused GREEN (2026-11-16), same command, exit 0:

```text
Ran 14 tests in 0.285s
OK
```

The final repeat after a finite-number short-circuit correction is recorded below.
The three CLI tests execute subprocesses against real temporary files, including
fresh-output preservation, malformed/oversized input and symlink rejection.
These are executable Given/When/Then behaviors under unittest; the shared main
BDD catalog, full-suite integration and CI remain coordinator-owned.

## Inspected existing surfaces

- `HCInteriorCatalog.c`: HCInteriorProp fields Type/Position/Orientation/
  Searchable/SearchPoint; HCInteriorLayout Id/History/Props; one building class,
  catalog version 1, three layouts/two histories and six native prop classes.
- `HCInteriorRules.c`: existing searchable allocation allows only empty/Rag/
  Battery9V, at most 12 slots/four Rag/two batteries per supplementary epoch.
  Both normal placement/search acceptance methods remain false.
- `HCInteriorStore.c`: input JSON remains below 32 KiB; immutable manifest,
  journal identity and conservative quarantine. This utility never changes it.
- `EXP-interiors-implementation.md` and `interiors-inspection.json`: prior
  installed native class/config audit and exact pinned scripts/asset PBO hashes.
  No new native calls are introduced, and no game source/assets are copied.

The adapter checks actual current layout IDs/history/prop lists, SearchType and
ItemAllowed allowlists, and PoolWithinBounds caps. This is a narrow adapter for
these reviewed pilot surfaces, not an Enforce parser or compiler. Exact hashes
of all three caller-supplied source files must match the measurement record.
Any incompatible pilot change requires adapter review; a source hash is not a
license grant, runtime proof or assurance that arbitrary source is trustworthy.

## Caller record contract, schema 1

Every object has an exact field set; additional enablement, balance, inventory
or unrelated fields fail admission. The executable synthetic `fixture()` in the
assigned test file is the complete example shape, not production data.

| Object | Required content and validation |
| --- | --- |
| Root | SchemaVersion=1, explicit boolean Synthetic, Context, SourceSha256, BuildingType=Land_House_1W01, CatalogVersion=1, Layouts, Observations, Policy |
| Context | World=chernarusplus; exact 1.30.164289 build/scripts PBO SHA; SurveyId; actual surveyed BuildingPosition/BuildingOrientation; both installed asset PBO hashes; Operator; ISO MeasuredAt with timezone; Method DayZDiag/Workbench/normal-server-survey; CoordinateBasis=building-model-local-metres; BuildObservation and AssetObservation |
| SourceSha256 | Exact keys HCInteriorCatalog.c, HCInteriorRules.c, HCInteriorStore.c, each matching supplied current source bytes |
| Observations | 5–16 distinct portable relative Path/Sha256/Kind entries; bytes required; native-build, asset-config, geometry, door-clearance, stairs-clearance roles are checked at each reference |
| Layouts | Exactly the three current pilot IDs in catalog order; preserve family/ransacked histories and each current prop type/searchability. Props use existing DTO names; numeric vectors are not rewritten, rotated, rounded, normalized or replaced |
| Survey | Bounds, measured prop Index/Room/Bounds/Observation, explicit Stairs present/absent, DoorObservation/StairObservation, caller-measured MinimumClearanceMetres, 1–32 identified door/stairs Keepouts. Absence of stairs still needs observed evidence |
| Policy | ItemGroups, exactly one Rules entry per measured searchable site, and Limits. Groups contain only Rag/Battery9V; all groups must be referenced. Rule LayoutId/Room/History must match the measured site; explicit caller Risk, Rationale and geometry Observation are required |

Vector controls: local positions/bounds within +/-100 m, surveyed building
position within +/-30000 m, orientation components within +/-360 degrees and
prop-local SearchPoint within +/-3 m. Booleans, strings and nonfinite components
are rejected as numbers. Prop anchors and bounds must be inside surveyed bounds;
prop AABBs cannot overlap/touch, and their Euclidean AABB separation from each
movement keepout must meet the caller's observed clearance (0.001–5 m).
These are diagnostic parser limits, not measured gameplay or collision budgets.
Bounds are building-model-local AABBs encompassing the full oriented asset;
SearchPoint is prop-local, as in HCInteriorProp. The tool does not compute an
asset's collision bounds, native floor support, proxy targeting or rotated
search-point reachability. A forged box/log cannot establish safe fit.

Policy requires EmptyAllowed=true, MaxItems=1,
Selection=unweighted-review-only, Condition=unmodified-native and
Storage=added-searchable-prop. Caller caps may only narrow existing pilot limits;
referenced item groups cannot use a zero cap. No weights, rarity probabilities,
condition multipliers, live distribution choices, replenishment or guaranteed
items are authored. Risk is a descriptive caller tag with rationale, not a
calculated rarity or military tier. The policy is review data; it never replaces
HCInteriorRules.Allocation or modifies an existing manifest/journal.

## Actual utility and export seam

From the repository root, with genuine caller measurements and evidence:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.package.interior_catalog \
  --record /private/surveys/interiors.json \
  --sources mods/HollowCountry/scripts/4_World/Interiors \
  --artifacts /private/surveys/evidence \
  --out /private/review/interiors-candidate-new
```

The output parent must already exist; the output directory must be fresh and
outside input trees. The utility emits only four files:

- `measured-record.json`: original measurement bytes, unchanged.
- `interior-layouts.candidate.json`: version/building metadata, explicit Synthetic
  marker and record hash, plus exact Id/History/Props DTO records for a future
  reviewed diagnostic loader to import. Surveys remain in the original record.
- `context-policy.candidate.json`: caller's validated policy, without defaults,
  sampling, changes to caps, or runtime allocation.
- `interior-report.json`: source/record/observation/output hashes, synthetic or
  native-validation-required status and explicit uncompleted gates.

Input record <=32767 bytes; each source <=64 KiB; each observation <=1 MiB,
aggregate <=8 MiB. JSON rejects duplicate keys, invalid UTF-8, nonfinite numbers
and excessive nesting; the observation-list bound is validated before artifact reads.
All filesystem inputs are regular files, with symlink/traversal rejection on
paths and ancestors. The final file open uses O_NOFOLLOW where available.
Output uses exclusive creation; existing outputs and input files are preserved.
This local review utility assumes operators do not concurrently replace its
ancestor directories; it does not claim hostile concurrent filesystem isolation.
No automatic cleanup/replay occurs after an interrupted output; retain the
incomplete review directory and select a fresh one.

## Freeze and uncompleted gates

Only the three assigned new files were authored. No commit, installation,
profile write, production coordinates or purchased assets were produced.
The source/export seam is implemented. Runtime loading is **not wired**; no
HCInteriorLayout, contextual allocator or diagnostic live-building loader reads
these candidates yet. Source changes, guarded integration and native tests must
precede any consumption by gameplay. Both runtime_loader_wired and
production_accepted always report false, including Synthetic=false records.
Hashes prove byte consistency only; actual caller measurement authenticity,
complete door/stair coverage, collision/nav fit, native target reachability,
normal-PBO persistence and restart/two-client behavior remain pending.
CE ownership/debit/reconciliation and inventory-plus-ledger atomicity are not
implemented or claimed. Rarity/balance and 3–6-player benchmark budgets remain
unmeasured. Existing hard acceptance gates stay in force.

Coordinator: integrate full unit/main BDD/CI and final package after remaining
worker freezes. Independent reviewer Hegel was supplied by the user; notify
thread 01a1e623-1c01-7a71-9a66-04285c841a25 after the final file hashes are read.

Final repeat: exit 0, `Ran 14 tests in 0.279s`, `OK`.

Frozen utility/test SHA-256:

- `tools/package/interior_catalog.py`: `b826594ab552588059c44278379fb92a6caee16097d402916d723af6140ee5fc`
- `tests/unit/test_interior_catalog.py`: `b58e3b49c05a44ca7d7a642af74fe016df6c4d55646373c5eccd990b20964bd5`
