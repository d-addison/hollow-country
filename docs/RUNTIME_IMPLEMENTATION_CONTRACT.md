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
owner alone adjusts lightingConfig at runtime, forcing the bright-night native
config 0 whatever the operator value (owner rule 2026-11-17: no dark nights; the
previous value is logged). It does not write disablePersonalLight. Between 20:00
and 05:00 the native overcast limit is 0.55 (server only; applied at startup and by
an idempotent 10 s dusk/dawn check, at most a 60 s transition, dawn restores 0..1),
and the forecast, rain and wind derived from cloud are capped too, so a storm band
cannot darken the night; daytime storms are unchanged. The separate
cfgGameplay delta owner must not write those two settings.

Search/crafting use native actions/recipes and server inventory authority; do
not invent a generic client command RPC. Cross-module requests must be narrow,
validated and bounded. Unknown native feasibility is recorded and gated, not
filled with physics cheats, phantom sounds or unsupported methods.
