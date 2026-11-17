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

SchemaVersion must be 1. All six feature flags are false: EnableInteriors,
EnableSearch, EnableCrafting, EnableInfected, EnableHordes, EnableAlertChains.
Keep them false pending the corresponding native tests. Search requires interiors;
hordes/chains require infected. TickIntervalMs defaults to 1000; MaxTickWorkItems
32; MaxActiveHordes 2; MaxActiveHordeMembers 24; MaxActiveInteriors 12;
MaxPropsPerInterior 5. These are bounded pilot limits, not performance promises.
Module-specific catalogs, state and acceptance belong to each module. No runtime
state is bundled. Enabling a flag does not establish eligibility or acceptance.

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

For addon rollback, restore the previous @HollowCountry folder and matching client
version while stopped, or remove its -mod argument on both server and clients.
Restore the matching settings/catalog/state backup when reverting schemas. CE
rollback changes configuration, not world history: existing items and persisted
entities are not silently deleted. Use the verified full stopped profile/storage
backup when a tested save rollback is needed. Never wipe a live save as a shortcut.
