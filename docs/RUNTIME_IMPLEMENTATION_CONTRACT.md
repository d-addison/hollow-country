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

`HCReached.Mark("search_binding.supply_bound");` is a shared **3_Game** API, usable
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

Marker names describe the observed operation: `.row`, `.job`, `.lease`, `.spawn`
and `.supply_bound` identify concrete work; `.tick`, `.sweep` and `.maintenance`
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
