# C11 / IC-07 observer transition veto contract

Date: 2026-11-16. Status: **authored diagnostic policy, integration pending**.
This is a reusable prerequisite for later lifecycle work, not implemented hordes,
observer coverage, transition permission, or accepted gameplay.

Scope is exactly these new files:

- `mods/HollowCountry/scripts/4_World/Infected/HCObserverTransitionGate.c`
- `tests/unit/test_observer_transition.py`
- `research/experiments/EXP-observer-transition.md`

No existing infected files, settings, module hooks, shared plans, packaging or CI
were edited by this worker. No commit was made. Nash owns the existing infected
integration files. Full-suite/BDD/CI and final compile belong to the coordinator.

## Requirement and plan trace

[Canonical spec](../../docs/specs/001-survival-overhaul/spec.md): FR-009,
NFR-001/002/003/006, AC-008. [Completion plan](../../docs/specs/001-survival-overhaul/completion-plan.md):
C11, IC-07 and T022. [Original specification](../../docs/SPECIFICATION.md),
section 6.4 and [canonical plan](../../docs/specs/001-survival-overhaul/plan.md)
T022 require multi-observer transition safety, hysteresis and no visible removal
or reappearance. HOR-006/HOR-007 remain unaccepted runtime tests.
[Runtime contract](../../docs/RUNTIME_IMPLEMENTATION_CONTRACT.md) keeps engine
acceptance separate from offline source work.

This change uses pure caller-supplied data and language-level arithmetic, reference
checks and bounded array traversal. It calls no gameplay, camera, CE, movement,
creation, deletion, teleport or networking API. No new native declaration is
assumed. The previous installed-API audit in
[EXP-infected-completion.md](EXP-infected-completion.md), IC-07, explains why
player proximity and local camera getters cannot establish remote spectator or
optics visibility coverage. No provider is implemented here.

## Reusable caller contract

`HCObserverTransitionPolicy` has no accepted default. All numeric defaults are
invalid zero values. The caller must explicitly set `ProvisionalDiagnostic=true`,
positive revision, finite positive time/distance/duration bounds, two ordered
near/far distances, positive freshness/grace/quiet/cooldown durations within the
supplied bounds, and observer/sample capacities. Units must be internally
consistent. The sample capacity is structurally capped at 32 and observer capacity
cannot exceed it. These are bounded-work limits, not calibrated gameplay budgets.
No distance or duration in the test fixture is a production recommendation.

`Configure(state, policy)` validates and copies policy fields. Any configuration
attempt clears accumulated quiet evidence; invalid configuration removes the
policy. Caller mutation of the original policy cannot relax an existing window.
Do not modify `state.Policy` directly. State belongs to one diagnostic cohort,
world and epoch. It is not a persistence schema or an untrusted client payload.
Create a fresh state after restart/world change; do not restore quiet evidence.

`HCObserverTransitionInput` describes one complete observer snapshot with:

- Explicit known/unknown global roster, spectator and optics coverage, capture
  time, positive monotonic roster revision, expected count and actual samples.
- Explicit known/resolved membership, known CE authority and durable intent,
  known population-budget compliance, native combat and transition history.
- A unique positive identifier and capture time for each expected observer, with
  separate known bits for coverage, spectator state, optics, current visibility,
  recent visibility, native combat, proximity and recent proximity.
- Current visibility/combat/spectator/optics flags, scalar observed distance and
  last-visible/last-near timestamps. `-1` means known-never only with the relevant
  known bit true. It never converts unknown history into known safety.

A future authoritative provider must increment roster revision for changes to
membership, camera identity/coverage or observer configuration, even if count
stays the same. Counts and booleans are declarations, not proof of enumeration,
CE ownership or durable transactions. Do not infer coverage from player positions
or set these flags true merely to exercise the gate. Zero observers is diagnostic
input only when the entire observer/camera roster is explicitly known complete.
No real provider currently satisfies this contract.

`Evaluate(state, snapshot, now)` returns diagnostic codes:

| Code | Meaning | Executable transition permission |
| --- | --- | --- |
| 0 | Missing, stale, malformed, replayed or unknown prerequisite | Rejected |
| 1 | Observed danger or grace/cooldown veto | Rejected |
| 2 | Waiting for far-entry or a continuous quiet interval | Rejected |
| 3 | Supplied diagnostic inputs satisfied the quiet-window policy | Rejected |

`CanTransition()` delegates to `ProviderCapabilityResolved()`, which is always
false. There is no caller override. `HCInfectedPolicy.CanAbstract()` and
`CanMaterialize()` remain false and were not edited. Code 3 must never be treated
as gameplay admission. No live caller is wired in this change; coordinator-owned
future diagnostics may call this seam without enabling lifecycle operations.

## State, safety and bounded work

Both current and snapshot clocks must be finite, nonnegative and bounded. Clock
rollback rejects and retains the previous high-water mark. Invalid/missing
inputs clear quiet evidence. Reconfiguration cannot erase the clock high-water
or accepted snapshot history. Snapshot/sample age at the TTL boundary is stale.
Every accepted batch and every observer reading must be newer than the previously
accepted snapshot; identical batches or aging observer samples cannot become
ready merely because wall time passed. Event history cannot be future-dated,
less than the `-1` sentinel or non-finite; transition history cannot regress.

At most 32 observer records are examined, with at most 496 prior-ID comparisons.
Overflow/missing-count admission occurs before sample access. Duplicate IDs,
missing samples and unknown per-observer channels reject. There is no world scan,
queue, timer, allocation of gameplay entities or per-frame hook. Configuration
allocates one policy DTO; the caller owns already bounded input allocations.

Visible subjects, active spectator/optics use, native combat, near proximity,
recent visibility/proximity and recent transitions veto. Visible and near events
and positive recent-history timestamps are retained in the diagnostic state so
later reports of known-never cannot erase danger, including across roster changes
or reconfiguration. Native combat has no invented extra duration; it resets quiet
evidence and must be explicitly clear in later complete snapshots.

Every observer must be strictly beyond the far distance to start a quiet window.
An existing window may remain in the near/far band, but crossing the near boundary
vetoes and restarts grace. TTL-sized observation gaps, roster changes, transitions,
unknown inputs and danger reset continuity. Grace/cooldown expire at their exact
supplied duration; quiet readiness begins at its supplied duration. These are
synthetic policy semantics, not measured engine observations.

## Actual TDD and executable scenario evidence

The tests use only Python's standard library. A restricted translator reads the
DTO initializers and executes the authored static methods, including the same
bounded loops, calls, assignments and state mutations. It contains no independent
Python transition decision model. This does not emulate Enforce precision, native
scheduling or engine behavior. Unsupported control-flow syntax fails explicitly.
The fixtures are marked synthetic in the test module and give their values next
to the policy setup.

Before source authoring, focused discovery failed all 20 original tests with
`AssertionError: C11 observer transition contract has not been authored`.
A subsequent scaffold with `Evaluate` returning unknown provided an actual
behavioral RED against authored code. After correcting a Python fixture's float
argument to `range`, this command was run before implementing quiet readiness:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_observer_transition.py -k continuously_clear -v
```

Actual RED excerpt, exit 1:

```text
test_given_two_fresh_observers_when_continuously_clear_then_diagnostic_only ... FAIL
AssertionError: Lists differ: [2, 2, 2, 3] != [0, 0, 0, 0]
Ran 1 test in 0.002s
FAILED (failures=1)
```

After initial validation/hysteresis authoring, the history-erasure regression was
written and run before adding retained visibility/proximity event state:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_observer_transition.py -k cannot_be_erased -v
```

Actual RED excerpt, exit 1 (four subcases: current visible, current near, recent
visible and recent near):

```text
AssertionError: 1 != 2
Ran 1 test in 0.004s
FAILED (failures=4)
```

The smallest behavioral correction retains these observed event timestamps and
checks their supplied grace periods before starting another quiet window.
Intermediate test runs also exposed synthetic roster-count changes without a
revision change and repeated snapshots reused across separate subcases. Fixtures
were corrected to retain their intended roster or use a fresh state; the gate's
replay and roster checks were preserved. The hysteresis fixture now expects the
retained proximity grace before a new far-entry window.

Focused GREEN, exit 0:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_observer_transition.py -v
```

```text
Ran 23 tests in 0.083s
OK
```

Executable Given/When/Then-style cases cover two-observer quiet readiness, unknown
global/per-observer channels, second-observer vetoes, finite bounds, NaN/infinity,
rollback/high-water preservation, stale/replayed snapshots, missing/duplicate/
overflow observers, exact maximum capacity, empty but declared-complete roster,
near/far hysteresis, retained grace, transition cooldown/history regression,
policy copying/reconfiguration, corrupted state and permanently closed runtime
capabilities. The shared BDD feature/runner files remain coordinator-owned.

## Unmet integration and acceptance gates

Independent source review remains pending at this freeze. The coordinator's
new normal-server compile 018 includes this exact observer source; verification
is recorded below. Earlier probes cannot cover this file. Coordinator owns
package freeze/build, full-suite/main CI and broader engine evidence. Compilation
establishes syntax/load only, not provider validity or gameplay.

Still required: trustworthy complete remote observer/camera enumeration, measured
current/recent visibility including long-range optics and spectators, native
combat/proximity/history binding, cohort/world/epoch identity, authoritative CE
ownership and population replenishment, member/corpse/inventory/crash reservation
reconciliation, and durable transition commits. Those capabilities are unresolved
and rejected here. DayZDiag, final normal PBO/server and two simultaneous clients
must establish the applicable original HOR/NET/audio/visibility acceptance tests.
Distances, times and load budgets still need target-load measurement at 3–6
players. No spawning, deleting, teleporting, horde activation or production
feature enablement is implemented or authorized by these offline results.


## Frozen-source normal-server compilation

The coordinator ran actual DayZ Server under Wine, experiment
`compile-018-integrated`; the [recorded report](../evidence/compiler-018-integrated-wine.json)
has status `initialized`, `client_count=0`, `signature_verified=false`,
`forced_stop=true`, and `runtime_acceptance=pending`. The script log records
Game, World and Mission modules loaded and the core settings self-test/startup
message. It does not record execution of this unwired observer policy.

Independently read the experiment PBO with `tools.package.pbo.parse`, verified
its SHA-256 against the report, compared the observer entry byte-for-byte with
the frozen source and verified all five recorded log hashes against their files.
Actual verification output:

```text
compile-018 initialized; PBO checksum and all recorded log hashes match
observer source matches PBO byte-for-byte: c6d3c0be35997b2e332d95b2752bd06341bd5588e8b0535d3b2735c83c0f4d95
PBO: 038a420209dbe4b830fbf41ba44e16be7e6c82fa9759a9bb32bf81a6bfd9cf6c
compiler report: 32fec4693857d8055ce3ccb14ca82d3a2c94d3a83307d973f74480dae295be53
```

Focused test freeze SHA-256:
`cf2814e82eda34035dabc80b0ea4128a7f08669d6d7c0885a7fde2329ace60a5`.
The report-only addition does not change compiled source. This is normal-server
compilation/loading in Wine, not Windows/DayZDiag, signed multiplayer loading,
observer-provider execution or any gameplay acceptance. Independent reviewer
Hegel and the coordinator have been notified of the frozen source and tests.
