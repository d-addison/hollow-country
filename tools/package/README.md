# Original-source package tooling

Status: unsigned development; native Windows execution and all runtime acceptance
pending. Run after shared-addon writers have finished. Python tools use only the
standard library; Python 3.10+ is required. Linux Python is installed here;
Windows Python is **not verified**. Supply a real native executable using -Python
for the Windows wrappers. They discover the executable, reject WindowsApps store
aliases, and verify the version before writing. Unknown Windows prerequisites do
not block building source packages on Linux.

## Deterministic build and verification

From the source checkout, create the output parent first; choose fresh filenames:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/package/pbo.py pbo --addon mods/HollowCountry --out tools/package/artifacts/hollowcountry-dev.pbo
PYTHONDONTWRITEBYTECODE=1 python3 tools/package/pbo.py verify tools/package/artifacts/hollowcountry-dev.pbo
PYTHONDONTWRITEBYTECODE=1 python3 tools/package/pbo.py handoff --addon mods/HollowCountry --mission mission/hollow-country --out tools/package/artifacts/hollow-country-private-dev.zip
PYTHONDONTWRITEBYTECODE=1 python3 tools/package/pbo.py verify tools/package/artifacts/hollow-country-private-dev.zip
```

Do not commit generated archives. The PBO has exact prefix HollowCountry, sorted
stored entries, zero metadata timestamps and a checked SHA-1 trailer. ZIP members
are stored, sorted, with fixed timestamps/modes. SHA-256 manifests cover each
payload and original PBO source. Rebuild with identical inputs to compare hashes.
A checksum is not a signature or sender authentication. `--release` fails closed.

Only original UTF-8 config.cpp and scripts/{3_Game,4_World,5_Mission}/**/*.c enter
the PBO. mod.cpp is accepted original text, excluded from the PBO and copied to
@HollowCountry/mod.cpp. An optional exact $PBOPREFIX$ marker is excluded from data.
Absolute/traversal/Windows device/ADS paths, case collisions, symlinks, unknown
files, binary source, game assets, config.bin and keys are rejected. Do not add
addon README or game data to the mod root. ZIP mission files use an exact list:
the CE no-ops, authored policies, operator settings, and install/rollback guides.
No whole-checkout glob or runtime profile is packed.

The private handoff includes `mission/hollow-country/INSTALL_AND_ROLLBACK.md`,
`operator/settings.json`, all-off feature defaults, CE policies, and these helpers.
Full selected stock entries generated for a CE experiment remain local output;
they are not the committed empty CE defaults or a vanilla dump in the handoff.

## Native Windows smoke and synthetic checks

Run the parser/guard checks in Windows PowerShell (they need no Windows Python):

```powershell
powershell.exe -NoProfile -File tools/package/Test-NativePackage.ps1
```

This parses every package PowerShell script with the native AST parser and checks
WhatIf creates no runtime/build, existing/Steam targets are rejected, and missing
signing keys fail. Fixtures are explicitly synthetic non-executables/non-keys;
no DayZ process is launched. The repository CI owns its own native AST step.

After building the addon PBO, in native Windows PowerShell:

```powershell
$Python = 'C:\Path\To\Python310OrNewer\python.exe' # verify this actual installation
.\tools\package\Invoke-NativeSmoke.ps1 -Pbo D:\HollowCountryLocal\hollowcountry-dev.pbo -RuntimeRoot D:\HollowCountryLocal\native-smoke-001 -Python $Python -MaxSeconds 180 -WhatIf
.\tools\package\Invoke-NativeSmoke.ps1 -Pbo D:\HollowCountryLocal\hollowcountry-dev.pbo -RuntimeRoot D:\HollowCountryLocal\native-smoke-001 -Python $Python -MaxSeconds 180
```

The helper uses the installed native DayZServer_x64.exe and copies its mission
into the fresh external runtime. It never writes the Steam mission. Profiles and
storage stay separate from the checkout. It records PBO/server/config/log hashes,
compiler errors, the core initialization marker, exit/forced-stop state, and
PID-owned UDP/TCP socket samples (or errors). Requested gameplay 127.0.0.1 does
not isolate the process: Steam query may listen on 0.0.0.0. The default window is
180 seconds, configurable 15–300. Only its own launched process is stopped; use
-LeaveRunning explicitly to keep it. A forced stop does not test persistence.
The disposable smoke has signature verification/BattlEye off; never reuse that
configuration for a live server. No successful marker or live socket is
client, signature, CE merge, geometry, restart, gameplay or performance acceptance.

Actual DayZ compiler/core self-test/initialization runs have been observed under
Wine, including integrated gameplay source. This is separate from native Windows
execution and client/gameplay acceptance. Raw reports stay in local experiment
storage; attach sanitized summaries to the relevant tracking issue.

## Official Windows build/sign/verify controls

Build-Sign-Verify.ps1 uses the deterministic writer plus installed official
signing tools. In a source checkout, choose a fresh output and external key pair:

```powershell
.\tools\package\Build-Sign-Verify.ps1 -AddonRoot .\mods\HollowCountry -OutputRoot D:\HollowCountryLocal\build-dev-001 -Python $Python -Unsigned
.\tools\package\Build-Sign-Verify.ps1 -AddonRoot .\mods\HollowCountry -OutputRoot D:\HollowCountryLocal\build-signed-001 -Python $Python -PrivateKey E:\PrivateKeys\HC.biprivatekey -PublicKey E:\PrivateKeys\HC.bikey
```

For an already built handoff PBO, the equivalent tested argument orchestration:

```powershell
& $Python .\tools\package\sign.py --pbo .\@HollowCountry\addons\hollowcountry.pbo --tools 'D:\SteamLibrary\steamapps\common\DayZ Tools' --private-key E:\PrivateKeys\HC.biprivatekey --public-key E:\PrivateKeys\HC.bikey --out D:\HollowCountryLocal\signed-001
```

The installed tools' actual command forms are:

```powershell
& "$Tools\Bin\DsUtils\DSSignFile.exe" $PrivateKey $Pbo
& "$Tools\Bin\DsUtils\DSCheckSignatures.exe" $AddonsDirectory $PublicKeysDirectory
```

DSSignFile defaults to v3 in this installed version. No guessed checker flags are
used. sign.py checks both exit statuses, requires the expected nonempty bisign and
an explicit positive checker result, rejects warnings/errors and a changed PBO,
and hashes public outputs/tools. Unit tests exercise these commands using fake
tools and synthetic non-keys. Separate actual official-tool execution under Wine
positively verified an integrated source PBO; checker output is retained locally.
This does not
make the unsigned development ZIP signed or prove client signature enforcement.
Private keys are never read/copied into a package. Install the .bikey in server
keys and .bisign beside its PBO. The output remains signed-development and gated
for normal server/client, two-client, performance and destination acceptance.

For an official **build comparison**, use a fresh external source staging folder
with only config.cpp and scripts copied from the validated addon (omit mod.cpp),
then the installed AddonBuilder:

```powershell
$Tools = 'D:\SteamLibrary\steamapps\common\DayZ Tools'
$Stage = 'D:\HollowCountryLocal\official-source\HollowCountry'
$Out = 'D:\HollowCountryLocal\official-build'
New-Item -ItemType Directory -Path $Stage, $Out
Copy-Item -LiteralPath .\mods\HollowCountry\config.cpp -Destination $Stage
Copy-Item -LiteralPath .\mods\HollowCountry\scripts -Destination $Stage -Recurse
& "$Tools\Bin\AddonBuilder\AddonBuilder.exe" $Stage $Out -packonly -clear -prefix=HollowCountry
```

Set the GUI copy-direct list to include *.c if needed by the installed builder;
use native BankRev/Workbench to verify every staged script/config and prefix.
Official output may use different metadata/compression; the strict deterministic
parser intentionally validates only its own canonical stored subset. Then sign
and check using the official commands above, preserving logs/exit statuses.
These build instructions are a native control procedure, not an executed build.

## CE and verification

`coverage.py` prepares a full-file point candidate from a pinned diagnostic export.
It requires exact source/export/log hashes and rejects unrelated geometry/policy
changes; it never invents points or installs a coverage fix. Invoke `--help` for
the fresh-output CLI. The evidence contract and limits are documented in source.

`interior_catalog.py` validates pinned measured pilot layout and contextual
policy candidates and exports only to a fresh directory. No runtime catalog
loader, placement, CE allocation or engine eligibility is established. Its
`--help` and source describe the
strict source/evidence schema. The private handoff includes `LICENSE.md` and
`docs/PROVENANCE_AND_LICENSES.md`; original code remains all rights reserved.

`deploy.py` implements private development ZIP install, explicit upgrade,
interrupted recovery and targeted rollback. It preserves external profiles and
storage, rejects managed-tree drift and keeps exact prior package backups. Use
`plan` first; mutating commands require a stopped-server acknowledgement. This
does not migrate opaque DayZ saves or accept native gameplay. See
`docs/INSTALL_ROLLBACK.md` in the private repository for commands and crash limits.

See the packaged mission install/rollback guide for exact source-bound generation
and isolated install commands. Merge/default behavior and eligible geometry need
native experiments; no loot fix is claimed. Diagnostic logging is separate from
the ordinary baseline; restore its core bytes before matched performance trials.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_package.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_economy_contract.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
```

The experiment report records actual red/green commands, primary format sources,
installed byte observations, traceability and pending gates.
