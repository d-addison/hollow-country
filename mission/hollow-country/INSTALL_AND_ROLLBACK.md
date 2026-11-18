# Private development installation and rollback

All runtime acceptance is pending. This package contains original code/config,
operator defaults and tooling, with no game assets, vanilla mission dump or keys.
Install DayZ/DayZ Server/DayZ Tools independently through Steam. Use a disposable
local mission/profile/storage copy before production installation.
Performance budgets require calibration at the workload being qualified.

## Package and mod installation

After all source writers finish, from the private source checkout (Linux Python can build this package; Windows Python is not assumed installed):

```powershell
python tools/package/pbo.py handoff --addon mods/HollowCountry --mission mission/hollow-country --out D:\HollowCountryLocal\hollow-country-private-dev.zip
python tools/package/pbo.py verify D:\HollowCountryLocal\hollow-country-private-dev.zip
```

Choose a fresh output file. Verification checks safe archive paths, every file's
SHA-256, PBO contents/prefix/checksum and the source manifest. These checks detect
corruption; they do not authenticate an untrusted sender. The committed CE files are empty no-ops; enable a candidate only through a freshly
generated, reviewed complete-entry delta. The deterministic PBO
contains only config.cpp and original scripts with prefix `HollowCountry`.
`mod.cpp` is at `@HollowCountry/mod.cpp` outside the PBO. The package is explicitly
unsigned-development and `--release` is rejected. Do not publish it.

Unzip the verified handoff into a private directory outside Steam. Keep
`@HollowCountry/addons/hollowcountry.pbo` and `@HollowCountry/mod.cpp` together.
Load the same addon on the normal server and clients with
`-mod=D:\HollowCountryLocal\candidate\@HollowCountry` (quote the whole argument
if its path contains spaces). This addon has client Game/World/Mission script
modules; do not substitute a server-only mod argument. Do not use file patching
as production verification. Keep a copy of the previous addon and hashes before
replacing it, and stop the server before changing any files.

## Operator settings

Copy `mission/hollow-country/operator/settings.json` into
`<the server -profiles directory>\HollowCountry\settings.json`, creating the
HollowCountry directory first. This is an authored default template, not a local
profile. Existing settings are operator state: back them up rather than replacing
them on upgrade. If absent, the core writes defaults at this same path. Invalid
settings disable features and preserve the original file; inspect the script log.

SchemaVersion must be 1. All eight feature preferences default to true:
EnableInteriors, EnableSearch, EnableCrafting, EnableInfected, EnableHordes,
EnableAlertChains, EnableGroups and EnableAtmosphere. A preference is not qualification: each
module still admits only behaviour whose native evidence is recorded and logs
the reason when it refuses. Set a flag to false to disable a feature; explicit
disables are preserved. Search requires interiors; hordes/chains require
infected. Acceptance of each feature remains pending its local-server tests. TickIntervalMs defaults to 1000; MaxTickWorkItems
32; MaxActiveHordes 2; MaxActiveHordeMembers 24; MaxActiveInteriors 12;
MaxPropsPerInterior 5. These are bounded pilot limits, not performance promises.
Module-specific catalogs, state and acceptance belong to each module. No runtime
state is bundled. Enabling a flag does not establish eligibility or acceptance.

Atmosphere remains experimental: admission also requires ChernarusPlus, an exact
engine version of `1.30.164289` or `1.30.164289.70`, no `atmosphere.disable` opt-out marker
(`HollowCountry/acceptance/atmosphere.disable` under the server profile turns it off; it is on by default), and the
generator's canonical disabled, non-resetting `v1-script` cfgweather.xml candidate.
Production qualification remains false. Restart after changing admission inputs.
Missing or non-delegated XML leaves vanilla in control. Admitted atmosphere changes
lightingConfig to the bright-night native config 0 whatever the operator value
(owner rule: no dark nights; the previous value is logged) and leaves
disablePersonalLight untouched. From 20:00 to 05:00 the overcast limit is 0.55 (set at startup and at
each dusk/dawn check, with a transition of at most 60 s; dawn restores 0..1), so
there is no night storm or rain. Other operator values are retained and logged. Seasonal temperature arrays remain native/operator owned. A missing
native noise system preserves the vanilla supplementary relay radius and logs once.
For atmosphere rollback, stop the server, set EnableAtmosphere=false, create the
`atmosphere.disable` marker and restore the backed-up mission/settings before restarting. DayZDiag,
normal PBO/server and two-client visibility/audio acceptance remain pending.

## Server configuration for the friend server (serverDZ.cfg)

The owner's local session gets these lines from the launcher
(`tools/setup/local_test_session.py`). On another host, the operator sets them by
hand in `serverDZ.cfg`. No other tool here edits server configuration. Back the
file up first.

```
thirdPersonView = 2;              // first person on foot, third person in vehicles (owner rule)
disable3rdPerson = 0;             // legacy key; 1 would override thirdPersonView and force first person everywhere
serverTimeAcceleration = 4;       // day runs at 4x
serverNightTimeAcceleration = 8;  // multiplies the day value: 32x at night, about 17 real minutes
enableCfgGameplayFile = 1;        // without it the cfggameplay delta below is ignored
lightingConfig = 0;               // bright nights; admitted atmosphere also forces 0 and logs the old value
verifySignatures = 2;             // keep signature checks on; install the Hollow Country public key under keys
maxPlayers = 6;                   // intended load is 3 to 6 players
```

- Camera: at startup the server logs `[HollowCountry] Camera mode: <mode>`. The
  mode comes from the native `GetThirdPersonViewMode()`. The expected line is
  `first person on foot, third person in vehicles`. Any other mode means a key
  above is missing or overridden.
- Night pace: the 32x figure assumes the BI server rule that the night value
  multiplies the day value. Check it with an in-game clock during local acceptance.
- Mods: the server `-mod` and `-serverMod` lists, and the client `-mod` list, keep the
  launcher's order. Optional weapon and AI dependencies (listed in `docs/FIREARMS.md`
  and the launcher plan) load before HollowCountry and come from the server owner's own Workshop
  subscriptions. They are never repacked or bundled.
- Every value is provisional until the owner's local session checks it with one
  client.
- Which mods each player needs, their load order and the friend server's ports:
  see `docs/FRIEND_SERVER.md`.

## CE generation and installation

Leave the Steam mission read-only. In native Windows create a mission copy under
`D:\HollowCountryLocal\candidate\mpmissions\dayzOffline.chernarusplus`, plus separate
profile/storage directories. Back up mission, profiles and storage while stopped.
The copy uses locally installed files; never add it to Git or the handoff ZIP.
The smoke helper can make a disposable copy automatically.

From the checkout or extracted handoff root:

```powershell
python tools/package/economy.py generate --source "D:\SteamLibrary\steamapps\common\DayZServer\mpmissions\dayzOffline.chernarusplus" --profile mission/hollow-country/economy-profiles/contextual-pilot.json --out D:\HollowCountryLocal\ce-contextual-delta
python tools/package/economy.py install --delta D:\HollowCountryLocal\ce-contextual-delta --target D:\HollowCountryLocal\candidate\mpmissions\dayzOffline.chernarusplus
```

Review `economy-report.json` and `ce/types.xml` before install. For an unchanged
native control choose baseline.json; for a separate logging run choose
diagnostic.json. Fresh output directories prevent mixing stale profiles. Existing
CE extension declarations require operator reconciliation and are rejected. The
generator checks item names, native usage vocabulary, complete stock flags and
valid budgets. The installer checks all five baseline source hashes, output
checksums and patch semantics. Installation into any steamapps directory or
through symlinks is rejected.

Generated types contain only the selected complete stock entries plus authored
usage additions. All retained fields are compared to the exact hashed source
before install. Engine duplicate/merge/default-field behavior is unobserved;
full entries are experiment inputs, with no healthy-economy inference.
Only a CE registration/default logging patch is applied to the copied core.
Stock db/types.xml, placement/prototype XML and other mission bytes stay intact.
Core comments/unknown settings survive. A local `hollow-country` directory stores
the delta, byte-exact core backup and receipt before the atomic core switch.
Never copy that backup/receipt into a distributable package. Do not reset the hive
to make a candidate appear successful. No player-owned inventory is generated.

## Gameplay settings (cfggameplay delta and spawn kit)

The native loader reads `cfggameplay.json` only when the server configuration
(`serverDZ.cfg`) contains `enableCfgGameplayFile = 1`. That one line is an operator
edit; no tool here changes server configuration. Without it every setting below
is silently ignored by the engine.

```powershell
python tools/package/gameplay.py generate --source "<private mission copy>" --profile mission/hollow-country/gameplay-profiles/hollow-country-v1.json --preset mission/hollow-country/gear/hardscrabble.json --out D:\HollowCountryLocal\gameplay-delta
python tools/package/gameplay.py install --delta D:\HollowCountryLocal\gameplay-delta --target "<private mission copy>" --dry-run
python tools/package/gameplay.py install --delta D:\HollowCountryLocal\gameplay-delta --target "<private mission copy>"
python tools/package/gameplay.py rollback --target "<private mission copy>" --dry-run
python tools/package/gameplay.py rollback --target "<private mission copy>"
```

The delta sets only the keys Hollow Country owns and merges them into the copy's
existing file. The native `version`, unknown keys and every other value survive.
The installer checks the source hash, output checksums and that the delta still
respects the ownership list and bounds, refuses a second install, and keeps a
byte-exact backup and receipt in its own `hollow-country-gameplay` directory
(separate from the economy `hollow-country` directory, so both can coexist).
Rollback restores the original bytes and removes only that directory; drift,
unexpected files, symlinks or hard-linked managed files cause refusal. `--dry-run` validates and lists changes without writing.
Chosen values, all provisional and compared with vanilla Chernarus:

| Area | Key | Vanilla | Hollow Country |
| --- | --- | --- | --- |
| Temperature | `WorldsData.environmentMinTemps` / `environmentMaxTemps` | see below | min -2 to -3 C, max -1 to -2 C per month |
| Weapon obstruction | `PlayerData.WeaponObstructionData` `staticMode` / `dynamicMode` | 1 / 1 | 2 / 1 |
| Wet weight | `WorldsData.wetnessWeightModifiers` (dry, damp, wet, soaking, drenched) | 1.0, 1.0, 1.33, 1.66, 2.0 | 1.0, 1.15, 1.5, 1.85, 2.25 |
| Hit indication | `UIData.HitIndicationData` | override off | override on, dynamic direction, 3.5 s, breakpoint 0.5, scatter 4 |
| Spawn kit | `PlayerData.spawnGearPresetFiles` | absent | `hollow-country-gameplay/gear/hardscrabble.json` (worn clothing, knife, bandage, one small item) |
| Infected leg zones | `CfgVehicles` ZombieBase LeftLeg `hitpoints` (in the mod `config.cpp`) | 100 | 50 |

- Obstruction enum (`EWeaponObstructionMode`): 0 disabled (no obstruction, still lifts),
  1 enabled (obstructs, then lifts), 2 always (obstructs, never lifts). Static
  obstacles use 2 and dynamic ones keep 1.
- Temperatures: vanilla Chernarus minimum -3, -2, 0, 4, 9, 14, 18, 17, 13, 11, 9, 0 and
  maximum 3, 5, 7, 14, 19, 24, 26, 25, 18, 14, 10, 5 (January to December). June to
  August stay at minimum 12 or above and maximum 23 or above. The result is
  clearly milder than the Sakhal curve. The vanilla Nasdara curve is itself warm (its
  maximums exceed Chernarus by 8 C or more), so it is not a cold reference.
- Hit indication: the native loader treats absent members as 0 and ignores the
  server block unless `hitDirectionOverrideEnabled` is true, so the delta carries all
  eight keys.
- Weight: the HC stamina HUD reads native `GetPlayerLoad()` (the engine weight,
  wetness included). Hollow Country never recomputes weight, so the wet values need no
  second implementation.
- Hardscrabble: randomised worn civilian clothing (health 0.6 to 0.69, strictly below the native worn cutoff of 0.7) and exactly
  one small item (a rag, a chemlight or one can of food), plus a kitchen knife (`KitchenKnife`) and a bandage
  (`BandageDressing`) on every spawn: the native loader picks one cargo set and spawns every item in it, so each
  set holds the knife, the bandage and its one small item. No firearms or ammunition.
  The native preset replaces the stock starting kit of the mission `init.c`. An existing install keeps the old
  preset until you rerun `generate` and reinstall (roll back first).
- Crawlers: lowering the leg-zone health makes leg hits down an infected sooner. The
  other leg inherits the class and bosses that set their own zones are unchanged.

Single owners. The delta never writes `StaminaData`, `MovementData` (including
`allowStaminaAffectInertia`) or `DrowningData`; they stay vanilla. The
Hollow Country stamina module (`HCStaminaConfiguration`, applied through the HC
profile) is the only owner of the 50 percent exertion drain and the 25 percent faster
recovery. Do not add `StaminaData` keys to this delta.

Ecology budget. This change leaves the native CE globals `ZombieMaxCount` and
`AnimalMaxCount` untouched. Hollow Country horde and ecology budgets are
requests that stay subordinate to those native limits: the operator horde
defaults and the script caps are far below the vanilla zombie cap.

Every value is an offline-tested authoring choice. Whether each setting behaves as
intended in DayZ (crawl rate, hit indicator readability, wet weight feel, the
kit actually spawning, temperature comfort) is pending native and local-server
acceptance with one client. Nothing here is accepted yet.

## Native compile, signature and acceptance

Native Windows Python 3.10+ is an unverified prerequisite: supply a real
executable using -Python; wrappers reject WindowsApps aliases and check the
version before writes. Linux packaging does not depend on it.
Run `tools/package/Invoke-NativeSmoke.ps1` in native Windows PowerShell with a
fresh external RuntimeRoot and the built PBO. It launches the installed server
on loopback, bounds the observation, records compiler errors/hashes and looks for
the core initialization log marker. Unsigned smoke uses verifySignatures=0 and
BattlEye=0 strictly for the fresh disposable runtime, never a live server.
It requests gameplay binding to 127.0.0.1; Steam query can bind 0.0.0.0. This is
not process-wide network isolation. PID-owned UDP/TCP socket observations and
query errors are recorded. The default observation window is 180 seconds. It stops its own process
unless -LeaveRunning was explicitly supplied. A forced stop is recorded and does
not prove persistence. See tools/package/README.md for exact commands.

Use Build-Sign-Verify.ps1 with external private/public keys for the official
DSSignFile and DSCheckSignatures pipeline. Only the public .bikey belongs on the
server in keys; .bisign stays beside its PBO. Never transfer the private key.
A signature still leaves normal client/server load, DayZDiag, two-client races/
audio/visibility, restart/persistence, CE eligibility and representative workload
benchmarks pending. Each destination requires its own final install/join test.

## Rollback

Stop the server and preserve the failed candidate's logs and profile/storage
backup. To undo only this CE install:

```powershell
python tools/package/economy.py rollback --target D:\HollowCountryLocal\candidate\mpmissions\dayzOffline.chernarusplus
```

The receipt must match the installed core, types delta and unchanged stock
sources. The command restores the original core bytes and removes only its own
managed directory. Drift, unexpected files or symlinks cause refusal so operator
changes are preserved for manual reconciliation. An interrupted install with its
receipt/backup and types file complete can also roll back before the core switch;
inspect incomplete earlier writes manually against your stopped backup.

The gameplay delta has its own rollback (`gameplay.py rollback`, see Gameplay
settings) that restores the original `cfggameplay.json` bytes. Roll back the CE
install and the gameplay delta independently; neither touches the other's directory.

For addon rollback, restore the previous @HollowCountry folder and matching client
version while stopped, or remove its -mod argument on both server and clients.
Restore the matching settings/catalog/state backup when reverting schemas. CE
rollback changes configuration, not world history: existing items and persisted
entities are not silently deleted. Use the verified full stopped profile/storage
backup when a tested save rollback is needed. Never wipe a live save as a shortcut.
