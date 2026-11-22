# Runtime integration contract

User steering: implement/package before their client connection; defer client
acceptance rather than blocking source work. Engine APIs must still be inspected
in the exact installed snapshot and runtime results must not be invented.

Single authored addon: `mods/HollowCountry`, PBO prefix `HollowCountry`.
Core owns config.cpp, scripts/3_Game, scripts/4_World/Core and scripts/5_Mission.
Workers own only their respective scripts/4_World/{Interiors,Crafting,Infected}
directories and assigned tests/research. No purchased assets are included.

Installed source snapshot (local, never commit): use an external directory
containing the scripts extracted from the installed DayZ 1.30.164289 build.
Supply its actual path to tools through their `--scripts-root` option.
Server scripts.pbo SHA-256:
`09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a`.
All 3076 entries use stored/uncompressed method 0. Official BankRev was tried
under isolated Wine; missing 32-bit ntdll prevented execution. Bounded direct
stored-entry extraction was used locally, with no source committed.

Shared 4_World API owned by core:

```c
class HCModule
{
    string GetName();
    bool IsEnabled(HCSettings settings);
    void OnStart(HCSettings settings);
    void OnTick(float deltaTime);
    void OnStop();
}
class HCModuleRegistry
{
    void RegisterModules();
    void Register(HCModule module);
}
```

Each worker extends `HCModule` and adds `modded class HCModuleRegistry` overriding
`RegisterModules`, calling `super.RegisterModules()` then `Register(new ...)`.
Core starts modules on server mission initialization, ticks once per second,
and stops/flushes through the verified mission finish hook. Module tick work must
be bounded and scan intervals may be longer than core ticks.

`HCSettings` in 3_Game has SchemaVersion=1 and default-true feature preferences:
EnableInteriors, EnableSearch, EnableCrafting, EnableInfected, EnableHordes,
EnableAlertChains, EnableGroups, EnableAtmosphere. Explicit disables in existing operator files
remain authoritative. Enabled preferences never imply provider availability,
measured geometry, native qualification or runtime success. Missing prerequisites
must produce a clear admission diagnostic. Additional core limits: TickIntervalMs=1000,
MaxTickWorkItems=32, MaxActiveHordes=2, MaxActiveHordeMembers=24,
MaxActiveInteriors=12, MaxPropsPerInterior=5. Modules use their own validated
JSON DTO/config/state types and never change shared fields. These are pilot
limits, not calibrated product promises. Persistence roots are under
`$profile:HollowCountry`; create directories explicitly. Native API evidence and
red/green regression records accompany every module. Python models/checks do
not establish native transaction, collision, audio or replication correctness.

Atmosphere uses the admitted Chernarus world-data owner and HCServer.Start hook
instead of a module slot. Its exact local build gate accepts `1.30.164289` and
`1.30.164289.70` only; production qualification remains false. The atmosphere
owner alone adjusts lightingConfig and disablePersonalLight at runtime, and only
from native defaults 0/false. Existing operator values are retained and logged.
The separate cfgGameplay delta owner must not write those two settings.

Search/crafting use native actions/recipes and server inventory authority; do
not invent a generic client command RPC. Cross-module requests must be narrow,
validated and bounded. Unknown native feasibility is recorded and gated, not
filled with physics cheats, phantom sounds or unsupported methods.

### Bounded readiness and first-reached receipts

After all module start hooks return, the shared core emits:

```text
[HC Ready] module=<name> enabled=<true|false> ready=<true|false> reason=<token> runtime=PENDING
[HC Reached] feature=<token> first_s=<seconds since core start>
```

Readiness snapshots the existing `HCGetOperationalStatus()` result; only an enabled,
started module reporting `ready` gets `ready=true`. Refused, degraded and unknown
states remain false. Disabled modules also get a receipt. Names/reasons are at most
64 characters; characters outside ASCII letters, digits, underscore, dot and hyphen
become underscores. No additional module admission/configuration reads are made.
The existing 15-second status refresh emits at most one additional receipt when an
initially non-ready module becomes ready. These bounds survive core stop/start
retries within the same script lifetime. Existing detailed state-change diagnostics
remain available. Settings-load failure reports `enabled=false ready=false
reason=settings_unavailable` because preferences could not be read; this is not
proof of an operator opt-out.

`HCReached.Mark("dead_drops.row");` is a shared **3_Game** API, usable
from World/Mission and from addons already depending on HollowCountry. ExpansionAI
already declares that dependency in `requiredAddons`; no dependency was added.
Core calls `HCReached.Begin()` before starting modules. Marks are server-only,
accept literal tokens of 1–64 characters from the alphabet above, and print only
the first occurrence of each token. At most 64 tokens are retained per boot.
Further valid, unretained calls increment a saturating counter (not an unbounded
set of distinct overflow strings). On core stop, `HCReached.Summary()` emits once:
`[HC Reached Summary] token_cap=64 overflow_calls=<count>`. A crash/forced exit
cannot guarantee that shutdown summary. Repeated retained tokens cost only a
bounded lookup and never print again.

Marker names describe the observed operation: `.row`, `.job`, `.lease`
and `.spawn` identify concrete work; `.tick`, `.sweep` and `.maintenance`
identify entry into that maintenance path. Startup-only owners use explicit
`.admission_logged`, `.catalog_read`, `.config_probed` or `.definitions_checked`
markers. These do not prove successful client presentation, crafting, mounting,
spawn, or native gameplay acceptance. Morse is disabled/folded into Radio and has
no separate main path to mark. `runtime=PENDING` remains unchanged by any marker.

Events instrumentation is deferred to its directory owner (no Events files changed):
put `HCReached.Mark("events.police_bind");` in
`HCEventWorldBinding.BindPolice` after successful target/container registration
beside the `police supply bound` diagnostic, including its already-bound success
branch when a real target/container is confirmed. A generic `Bind` return alone
is insufficient: some families return true without a physical source.
Native compilation, readiness/late-update ordering, time values, overflow shutdown
summary and actual marker paths still require an engine run; offline lint does not
establish those behaviours.

### Events public mission beacon (implemented-unverified)

The Events module owns the public mission table. The server reads committed
mission records (announced or active, current session, not yet expiring), keeps at
most `Events.MissionMapMaxRows` rows (hard cap 16) and pushes one full versioned
snapshot over the server-to-client RPC id 4853803 whenever the set changes, and
once per connecting or respawning player. The wire carries version, sequence, row
count, then per row id, kind, title, place, zone centre, radius and remaining
seconds. There is no client request, so the existing refusal-only event RPC is
unchanged. The client validates every field, refuses an unknown version, a short
read, an out-of-bounds count or a bad row with one logged reason, and counts the
remaining time locally so a lost end push cannot leave a stale zone. Both map
renderers (the group map and the Expansion map addon layer) read the same client
store; neither writes to server state or Expansion marker storage, and neither
queries the engine per frame beyond projecting the cached rows. Server work runs
through the shared situations work-budget unit, one poll every two seconds.
Notifications use the vanilla notification system, at most two per mission per
player and twelve per minute server-wide; a late joiner receives one summary
toast. Counters: `[HC Use] module=Events feature=mission_marker` and
`feature=mission_notice`. Native compile, client display and the one-client check
(toast, Expansion marker and circle, group map zone, removal at end, 0 missing
textures, 0 client script errors) remain pending.

### Shared startup catch-up (implemented, retail verification pending)

`HCStartupPump` registers bounded startup owners through `HCStartupOwner` and uses
one SYSTEM update callback for routes source-pin/resolve, HC-42 source parsing,
Interiors template packs and the shared Expansion road graph. Native API inspection:
`scripts-1.30.164289/3_Game/Global/Game.c:1552`, `3_Game/DayZGame.c:3027`,
`2_GameLib/tools.c:115-124`; raw counter: `1_Core/proto/EnSystem.c:106`.
Core probes `$profile:HollowCountry/acceptance/startup_catchup.disable` once before
starting modules. Present means normal tick cadence for all four owners, including
road loading and the former 100 ms Interiors pump.

The settings registry owns `Performance.StartupFrameMs` (default 4, range 1–4 ms)
and `Performance.StartupDeadlineSeconds` (default 30, range 1–300 seconds per owner
since registration). The persistent round-robin cursor shares one raw-counter
frame deadline, using HCWorkBudget's existing counter conversion. Each owner
receives at most the remaining frame time and its existing slice cap; at most
32 slices and 32 retained registrations are allowed. Finished registrations stay
bounded until core stop; the callback detaches when all finish. Deadline, failure,
stop and opt-out end catch-up; normal tick drivers remain. One receipt per owner:
`[HC Startup] owner=... wait_s=... catchup_s=... frames=... slices=... ms_max=...`.
`wait_s` is registration to first pumped frame (the SYSTEM queue does not tick
during server load); the deadline and `catchup_s` start at that first frame.
`frames` counts frames served; `ms_max` is the largest measured owner slice.

Startup registrations use small adapters with non-owning back pointers; the story,
routes and roads loaders do not inherit pump bookkeeping fields. Inside a pump
slice, `HCStartupPump.HCInSlice()` replaces tick-pool admission for AI_ROUTES,
STORY_INDEX loading, INTERIORS pack loading and ROADS loading with the shared frame
deadline. Normal tick admission is unchanged, including story observer selection.
Each loader retains its unit/line cap and slice clock; roads only loads on its own
round-robin turn during catch-up. Story loading preserves its scene owner when
called without one, and source parsing/refusal/logging never dereferences it.

No slice can preempt an atomic engine operation. Existing row/line limits,
READS_PER_UNIT, page length checks, sampling policy and hash context isolation are unchanged. The existing hasher
processes 128-byte parts with private saved context and restores Expansion's incoming
global context before every return; the pump never retains that global state. Routes, story and Interiors retain their 2 ms slice ceilings; road
loading retains 4 ms and its existing line ceiling. No new trusted cache exists.
The earlier road-only frame pump in `HCXAICaravanAdapter.c` joins this budget
because routes also wait for `roads.Phase == "loading"`. Locality site paging
continues normally: `HCXAISites.StepWait` publishes `run` before its incremental
locality survey; it is not another startup source-load readiness wait. HC-42
observer selection and actual site/actor qualification remain on their own ticks.

At the existing provisional 10,000 raw ticks/ms, `resolve_ticks_max=826` is
0.0826 ms and the source-page guard of 40,000 ticks is 4 ms (a diagnostic guard,
not a proven worst case). A 4 ms shared allowance plus a final non-preemptible
4 ms source-pin operation suggests about 8 ms of catch-up frame work at that guard,
excluding normal server work. About 1 s CPU needs roughly 250 full 4 ms frame
allowances: 4.2 s at 60 FPS, 8.3 s at 30 FPS or 25 s at 10 FPS, before contention
and atomic overhead. These estimates do not establish readiness by vanilla +30 s
or R2 <=20 ms. The lead must measure both on retail, including deadline/opt-out
fallback, default-on readiness and upgrade recovery.

Legacy route rows without ValidityKey are filtered in one bounded boot-image pass,
with one aggregate count and one shared-save dirty notification after provider
admission. Modern rows retain normal validity and geometry review. Settlement decay
logs a town only when changed, and one receipt per completed cursor pass with towns,
changed and saved. Saved counts completed routine checkpoints since the prior pass;
a newly dirty row can be checkpointed during the next pass. HC Use is unchanged.

### Regional shelter side fallback (build 167 follow-up; implemented-unverified)

`HCShelterModule.HCRegionalShift` retains the original 35 nearby layouts on the
authored −X side, then tries the same pattern on +X, −Z and +Z (`side=0..3`).
The fixed total is 140 layouts per site (`layouts_per_site=140`). The transformed
slots and yard preserve distance from each measured clipping edge; Z-end layouts
rotate the slot offsets and prop orientation by a quarter turn. Prop bounds are
rotated back into the building frame for the yard/access test. The original full
roof plus access box stays fixed on every side. All observer, occupied, collision,
ground support, water and four-corner terrain checks remain authoritative, including
the 0.25 m maximum footprint rise. Each retained substep and rollback deletion still
requires its existing SHELTER admission; no loop attempts multiple variants in one
grant. Observation defers the current variant without consuming it.

A successful transaction emits `regional_placed=<id> variant=<n> side=<n>`.
`regional_summary` retains its existing keys and adds `candidate_refused_by_side`
(counts by side number). Exhaustion still emits `regional_refused`; any terminal
site failure still degrades the module. The bounded summary also prints
`[HC Shelters] degraded reason=regional_scene_placement_failed sites=<ids>`.
There is no engine evidence that the four build-167 failures are unplaceable on
all sides, nor evidence supporting a one/two-site readiness waiver.

The AdditionalScenes generator is `tools/audit/gapcov_habitats.py`. It has stock
building positions and measured class envelopes, but no site terrain/occupancy
samples from which to choose a flatter side. Its data is unchanged: the runtime
derives all four candidate yards from those envelopes and validates each on site.
No offline terrain or allowed-side acceptance is inferred.

Regional props use `ECE_NOPERSISTENCY_WORLD` (installed CentralEconomy contract:
“do not save this object in world”). Placement state is in-memory only, reset at
startup, and owned props are deleted on stop. Earlier-build regional props use the
same flags: upgrade reconstructs the scenes fresh, with no stored placement to
migrate or duplicate. Rollback removes partial candidates before another variant.
Native compile-to-Mission, retail placement receipts (especially Bor, Nagornoye,
Orlovets and Tisy military), one-client access/rain checks and restart verification
remain pending with the lead. Offline validation does not establish placement.
