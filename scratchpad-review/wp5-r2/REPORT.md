# WP5 round 2 report — #20 / #22

Source corrections and offline regressions are implemented. No native
runtime acceptance or full-denominator coverage is claimed. No DayZ, Wine,
PowerShell, /mnt/d access, git mutation, commit, staging, or publishing was used.

## Scope and traceability

Edited source/tests:

- `mods/HollowCountry/scripts/4_World/Infected/HCInfectedRooms.c`
- `tests/unit/test_infected_production_rooms.py`
- `tests/unit/test_room_catalog_completion.py`

This report and adjacent `.out` files record actual verification. The writer
commit message is in `.banso-writer/commit-message` for the orchestrator.
`HCInfectedModule.c`, Navigation and other workers' files were not edited.

Read `AGENTS.md`, the runtime implementation contract, reviewer `REVIEW.md`,
`mutate.py` and `mutate.out`. This worktree omits `docs/SPECIFICATION.md` and
`docs/specs/001-survival-overhaul/{spec,plan,tasks}.md`; the corresponding files
were read from `/code/dayzsa_mods/` without modifying them. Current user/worktree
instructions supersede stale load/publication assumptions there. Traceability:
AI-03/04, PHY-01, FR-008, NFR-001/003/006, AC-007; T019/T020 and C10 room-catalog
completion. The active round-2 request supplies the ten bounded review tasks;
no external spec/task or runtime gate has been marked accepted.

## Changes by requested finding

| Finding | Result |
| --- | --- |
| 1 | Through `EnsureProductionLoaded`, json.loads-valid unknown keys, duplicate keys, 17 anchors and a `\u0041` string escape each result in zero LoadData calls, empty published state and `rooms_json`. Array preflight no longer overwrites this reason with `rooms_limits`; direct DTO limits still report `rooms_limits`. |
| 2 | A lifecycle test admits, calls public `Clear()`, checks bindings/classes/reason/attempt reset, verifies order does not reload, then explicitly loads again and checks a second read/log. Existing `ClearProduction()` call was retained. |
| 3 | Separate tests isolate native prefix, fixture marker, selftest marker and seven/eight-character run IDs. Owned anchor checks independently assert SourceRunId, SourceSha256 and EvidenceKind values and copy isolation. |
| 4 | Separate direct-bind tests isolate doc/runtime both 1.31.1, 257 total anchors, 65 houses, 17 anchors (otherwise inside house bounds), no anchors, BoxMin -513, Id 65, duplicate Id at distinct valid points, sub-one spacing with distinct Ids, position below room minimum, zero-volume room containing its point, non-House padding while omitting a real House, and a second otherwise-valid bind. Additional tests cover the 2049th declared class, direct JSON 1MiB+1 and missing fraction digits. |
| 5 | Synthetic class fixtures now use `Synthetic_House_1` / `Synthetic_Shed_1`, including the shared diagnostic House default. A rejection of underscore characters fails normal admission tests. |
| 6 | The bounded config census completes despite omitted classes, preserving the actual House count. Above 2048 it refuses as `rooms_house_class_cap`, logging observed config/House counts once without publishing any coverage. Boundary fixture: 2050 config children, 2049 House classes; all values are fabricated. The 32768 config and 2048 House caps remain provisional. |
| 7 | `HCInfectedProductionRoomAnchor` is a flat input DTO declaring all seven fields and Contains. `HCInfectedOwnedProductionRoomAnchor` is a distinct runtime-only subtype used for the existing base-anchor ordering interface, retaining provenance. The owned subtype is never deserialized. |
| 8 | `BuildProductionOrder` returns empty before admission; it never calls EnsureProductionLoaded. Explicit startup load is required; precise out-of-scope change follows below. Existing diagnostic BuildOrder consumer stays intact. |
| 9 | A build refusal includes at most 32 printable observed version characters (controls become `?`) in its single lifecycle log. Production reading checks nonnegative byte count == received string length and the independent 1MiB length cap. Comments explain the comparison with ReadBounded and pending native semantics. |
| 10 | Get results are assigned to string locals before ToAscii, including the JSON empty-string closing quote. Source check rejects a chained Get(...).ToAscii call. |

## Actual RED → GREEN

Failing tests were written before source changes. The common focused command was:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_production_rooms tests.unit.test_room_catalog_completion tests.unit.test_script_syntax -v
```

Initial actual RED (`red.out`):

```text
Ran 60 tests in 4.159s
FAILED (failures=10)
```

Actual representative behavioral failure:

```text
FAIL: test_json_preflight_guards_native_load_path (tests.unit.test_infected_production_rooms.InfectedProductionRoomTests.test_json_preflight_guards_native_load_path) (name='17 anchors')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/b04-wp5-r2/tests/unit/test_infected_production_rooms.py", line 370, in test_json_preflight_guards_native_load_path
    self.assertEqual("rooms_json", ns["ProductionReason"]())
AssertionError: 'rooms_json' != 'rooms_limits'
- rooms_json
+ rooms_limits


```

Other initial failures: lazy load through normal ordering and after Clear,
missing bounded build labels (three subcases), missing cap diagnostic, inherited
DTO, chained ToAscii, and the existing oversized-array reason expectation updated
to the requested JSON refusal. Already-correct guard behavior was preserved;
new independent tests strengthen it rather than inducing artificial source bugs.
A subsequent mutation exposed that invalid order requests must also be checked
after admission. That assertion now kills removal of the production budget
upper bound; `budget-mutation.out` records the actual one-test RED
(`Ran 1 test in 0.056s`, `FAILED (failures=1)`), followed by the focused GREEN below.

The first implementation attempt (`green-initial.out`) ran 60 tests and had five
Python boundary errors: its mutable Text stand-in could not concatenate with a
string. Initializing the native helper's label explicitly to `""` fixed this;
the harness's loop translation remains generic and unchanged.

Final focused GREEN (`green.out`):

```text
----------------------------------------------------------------------
Ran 63 tests in 6.117s

OK
```
Full discovery command (final run after the post-admission assertion):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
```

Actual final discovery GREEN (`full-suite.out`):

```text
Ran 2527 tests in 108.955s

OK (skipped=1)
```

The focused run includes the required syntax suite. Discovery also includes
script identifier collision checks and `test_infected_completion.py:189–190`;
Navigation still calls `HCInfectedRoomCatalog.BuildOrder` before CreateGroup.
`git --no-optional-locks diff --check` passed. A separate source scan found a
maximum of six binary + operators per statement and no ternary; changed scopes,
predeclared out locals, bounded loops and qualified FileMode.READ were inspected.
See `source-checks.out`. These checks do not establish native compilation.

## Mutation rerun

The supplied reviewer script was executed with standard-library Python in a
fresh TemporaryDirectory containing copies of authored `mods` and `tests`.
Only its hard-coded `R` assignment was replaced with the temporary root; all 73
original mutation definitions and its two-module unittest command were retained.
The worktree source and reviewer script were never mutated. No git archive/index
operation was needed. Captured stdout: `mutate-final.out` (the earlier exploratory
snapshot is retained as `mutate.out`). Invocation was
`PYTHONDONTWRITEBYTECODE=1 python3 -` with stdout/stderr redirected to that file;
the wrapper used `shutil.copytree`, replaced the single R assignment, then
`exec(compile(source, 'reviewer-mutate.py', 'exec'))`.

Actual reviewer rerun: **65 KILLED, 4 SURVIVED, 4 SKIPPED**. Skips were the changed
House-cap/unknown-class anchor shapes (zero matches) and the original ambiguous
production/diagnostic Id bounds (two matches). All four were rerun against unique
production source anchors and **all four were KILLED**:

```text
KILLED house cap new shape
KILLED unknown house class new shape
KILLED production id lower bound
KILLED production id upper bound
```

The original final probe snapshot survived `budget guard prod`; the subsequent
post-admission assertion and focused rerun **KILLED** it. Its actual failure is in
`budget-mutation.out` and the current focused/full suites are GREEN. Thus all 73
original probe intents have results: **70 killed, 3 remaining survivors** after
retargeting and the budget follow-up. The four-survivor line in the main rerun
log predates that last assertion; it must be read together with the follow-up.

| Remaining survivor | Why it remains |
| --- | --- |
| `dup class` | Redundant under unique CfgVehicles child names: full House membership plus equal counts already make duplicate document rows fail. No distinct admission bypass demonstrated. |
| `box order` | Implied by the mandatory nonempty anchor set and strictly positive room boxes contained within the house box. |
| `hash lower` | No-op: the mutation adds exclusion of uppercase ASCII to a range already restricted to lowercase a–f. |

The extra direct 1MiB and fractional-digit tests kill the former `json len cap`
and `num float frac` survivors. Underscore fixtures, independent evidence and
bounds, public Clear, preflight-through-load, source SHA copy and rebind probes
also kill their former survivors. This is mutation evidence for the offline
source translation, not native compilation or engine acceptance.

## Required WP1 startup integration (not edited)

In `HCInfectedModule.OnStart`, immediately after the existing validated-config
block (`if (!m_Config || !m_Config.IsValid() || ... ) { Quarantine(...); return; }`)
and before the Preferences comment / `m_Admission = HCInfectedAdmission.Evaluate(m_Config);`,
insert exactly:

```c
HCInfectedRoomCatalog.EnsureProductionLoaded();
```

The existing initial guard already restricts startup to the enabled server
module, and the profile directories have already been created. This is data
admission/reporting only. Keep public Clear at module stop, and keep routing behind
Investigation AND NativePackRoutes qualifications and all native path/fairness
checks. Do not reintroduce a load into BuildProductionOrder or AI ticks. Current
module source has no production startup caller, so this integration remains
pending for its owner. Existing Navigation remains on diagnostic BuildOrder as
requested; this change does not enable production movement.

## Installed API inspection and remaining gates

Inspected only the pinned external native cache
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`:
`3_Game/gameplay.c:49–90` JsonSerializer flat/nested/vector shapes,
`3_Game/tools/JsonFileLoader.c:69–83` LoadData boolean/out error,
`1_Core/proto/EnSystem.c:417–425` OpenFile and ReadFile(string) byte-count declaration,
`3_Game/Global/Game.c:594/611` config enumeration, `:942` GetVersion out string,
and `:1437–1470` IsKindOf's config-path lookup. Also inspected `1_Core/proto/EnString.c:86/448` ToAscii/Get signatures.
Strings use the existing pinned Get/ToAscii/Substring/ToLower/Length API; array methods and vector.DistanceSq remain
as reviewed in `../wp5-review/REVIEW.md`. No native assets/dumps were copied in.

Still unobserved and required before production enablement:

- **JsonSerializer:** actual flat production DTO, vectors, nested arrays and
  refusal behavior in DayZDiag and normal PBO/server. Python copies supplied DTOs
  after json.loads; it does not emulate native deserialization or compilation.
- **ReadFile count:** capture requested size, returned count and received string
  Length for empty/valid/truncated/oversized files and ASCII/non-ASCII contents.
  HCInfectedState.ReadBounded currently ignores the returned count and trusts
  received string length. Production uses the same independent length bound
  plus the stricter fail-closed byte/length consistency check. There is no claim
  that this extra equality has been observed to match native string semantics.
- **GetVersion format:** observe exact build text in both runtime types; the
  admission pin remains exact `1.30.164289`. Bounded refusal logging supplies
  diagnostics but does not establish its native format.
- **House-class count:** measure all loaded CfgVehicles/House classes on target
  configs, including non-enterable/static assets. The actual count and startup
  cost are unknown; the cap may prevent all admission. Set a measured cap plus
  margin in follow-up, considering 1MiB JSON and startup budgets. No measured
  full-denominator coverage or performance at 3–6 players is claimed.
- Source hash/run provenance and BoxMin/BoxMax remain operator assertions; no
  native extent comparison, authenticated survey, path/door/stair reachability,
  locomotion audio, client replication or fairness acceptance was manufactured.
  All-excluded admitted data can have zero instances; consumers must check data.
  Two clients remain required for network/audio/visibility acceptance.
