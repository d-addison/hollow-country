# EXP-economy-implementation

2026-11-16. **Offline tooling implemented; runtime acceptance pending.**
Scope: mission/hollow-country/**; tools/package/**; test_package.py and
test_economy_contract.py; this report. No core/gameplay/CI files changed by this
worker. Read AGENTS.md, full SPECIFICATION.md handoff, current feature spec,
plan/tasks and RUNTIME_IMPLEMENTATION_CONTRACT.md. User steering authorizes source
and packaging before connection, keeps runtime gates pending, and assigns the
actual addon build to main after concurrent workers are stable.

## Concrete outputs and traceability

| Output | Existing Banso work | Implemented offline behavior; remaining gate |
| --- | --- | --- |
| tools/package/pbo.py | T004, T025; FR-002/012; NET-006/008 | Deterministic stored PBO, strict parser, private handoff and verification. Exact prefix HollowCountry. Native compile/load and signature acceptance pending. |
| tools/package/sign.py; Build-Sign-Verify.ps1 | T004, T025; AC-002/011 | Exact official signing/checker argument orchestration, error/positive-result checks. Unit tests use fake tools/non-keys. Real signing pending. |
| Invoke-NativeSmoke.ps1; Test-NativePackage.ps1 | T004; FR-002/011 | Bounded native Windows server initialization controls, actual socket samples, AST/synthetic guard checks. Native execution unobserved here. Main owns Windows CI integration. |
| tools/package/economy.py; mission policies | T011–T012; FR-003/004; CE-002/005–009/011/012 | Source-bound opt-in complete selected types and diagnostic config patch; isolated install/rollback. Engine merge, eligibility, supply and performance acceptance pending. |
| Committed CE empty types/append files | T010–T011; LOOT-03; CE-003/004 | No production CE changes. Apartment/barracks identification and eligible geometry remain pending; no loot-fix claim. |
| operator/settings.json; INSTALL_AND_ROLLBACK.md | T025; FR-012; NET-005/006/008 | All features off, explicit install/settings/rollback and private transfer procedure. Real restart, migration and destination tests pending. |

No task is promoted to runtime accepted by these outputs. No requirement is
removed: room/context allocation, coverage, soft high-tier exceptions, diversity,
world accounting, two credible observed acquisition routes, persistent depletion,
performance and destination transfer stay traceable to T010–T012/T015/T024–T025.

## CE safety and installed-source observations

Installed source read-only:
`/mnt/d/SteamLibrary/steamapps/common/DayZServer/mpmissions/dayzOffline.chernarusplus`.
The existing official-source ledger pins Bohemia CE commit
`f220b2918b1d79a5055b1ee9be70c0ec1516e876` / DZ_130. Re-read hashes:

| Input | SHA-256 |
| --- | --- |
| cfgeconomycore.xml | b5a88d6d5a79e8c1e272d63a608eb02107d444169aa993348430dd6c9f4dd503 |
| db/types.xml | d477597418530c3e226fa18b296290eb9669210d9a37a301eaf7e3426e5e1040 |
| cfglimitsdefinition.xml | 07f4dedfb53e97b6150eb2374c539604b5800b8ec4c4ae243e26419aa77d4d26 |
| mapgroupproto.xml | 44e70165da1b13de1ab2451aea43413955a7e81acd2d7016ba957787632585a6 |
| mapgrouppos.xml | 3eeaad9786a73c339f61f6e6ad203f0732e36b88f27333978cc8b4beece9cec4 |

Generation was exercised in memory for all three policies. Actual results:
baseline = 0 entries / 0 registrations / 0 diagnostic patches;
contextual-pilot = 5 complete entries / 1 registration / 0 diagnostic patches;
diagnostic = 0 entries / 0 registrations / 5 diagnostic patches.
All five installed input files were byte-identical after generation checks.
For all five contextual entries, nominal/min/lifetime/restock/quantmin/quantmax/
cost and all six flags were compared with stock and matched. The installer also
compares every retained XML field structurally with the hashed source.

The opt-in route additions are BandageDressing → Town/Village; Battery9V →
Town/Military; CanOpener → Hunting; DuctTape and SewingKit → Military. Existing
usages remain included. No new class, placement, supplementary spawn, count
multiplier, item transaction, horde population or client inventory is introduced.
Broader usage can redistribute stock supply; unchanged source fields do not
establish effective populations or a healthy economy.

**User revision applied:** committed `ce/types.xml` and
`cfgeconomycore.append.xml` are empty no-ops. Earlier usage-only candidate entries
were removed. Opt-in generation emits complete entries for selected changed
items from the exact installed source. Generated stock-derived entries are local
experiment output and are excluded from the private source handoff. No full
vanilla types dump is committed/distributed. Duplicate-entry merging, replacement
of usage lists and partial-field defaulting remain unobserved in the engine.

[Bohemia's CE mission-file documentation](https://community.bistudio.com/wiki/DayZ:Central_Economy_mission_files_modding)
describes ce/file registration and partial overrides, including replacement of
usage/tag/value lists. That documentation is design input, not an installed-build
observation. The generator supports only a types registration and a separate
allowlist of existing core logging defaults. It never invents arbitrary XML
merge types or mapgroupproto/mapgrouppos extensions.

Raw source findings reproduced: Land_Tenement_Small has lootmax=0, 0 raw points,
132 placements; Land_Tenement_Big has lootmax=0, 0 raw points, 38 placements.
Known barracks prototypes already have native points (see existing audit and
source ledger). The user's exact white barracks model/location is unverified.
Raw counts do not prove accessibility, area flags, eligibility, occupancy or spawn
outcomes. No coordinates/lootmax edits are invented; engine_eligible_loot_points
is null, engine_merge_semantics is unobserved and loot_fix_claim is false.

Install requires a stopped isolated mission copy outside Steam, checks source and
delta hashes and complete-entry semantics, and rejects symlinks, drift, unknown
files and existing extensions needing reconciliation. Core bytes/comments are
preserved except the explicit patch. A local receipt and core backup precede its
atomic switch. Synthetic rollback restores exact core bytes and rejects later
operator drift. This does not prove crash durability or restore world history;
actual save backup/restart/rollback tests remain pending.

## PBO format sources and observed bytes

[Bohemia PBO format reference](https://community.bistudio.com/wiki/PBO_File_Format)
describes contiguous NUL-terminated filename records, five little-endian 32-bit
fields, a terminating empty record and contiguous data. The implementation emits
a Vers property header with exact HollowCountry prefix, stored method 0 entries,
zero original/reserved/timestamp fields and a trailing zero plus SHA-1 of the
preceding bytes. It is a deliberately strict canonical subset, not a general PBO
extractor or an addon-signature implementation.

Independent local read of installed `DayZServer/dta/scripts.pbo` found header
words `(0x56657273, 0, 0, 0, 0)` and a zero-delimited trailer whose 20 bytes matched
SHA-1 of the entire preceding file body. Its SHA-256 was
`09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a`.
No native source/asset was copied by this worker. This verifies byte conventions,
not engine acceptance of our addon. Tests additionally use an independently
hand-constructed synthetic wire record, not only writer/reader agreement.

ZIP entries are sorted/stored with fixed time/mode; manifest SHA-256 covers every
payload and original PBO source. A strict allowlist rejects game assets, keys,
unknown files, binary sources, traversal/absolute/ADS/device paths, case collisions
and symlinks. mod.cpp remains original UTF-8 launcher metadata outside the PBO at
@HollowCountry/mod.cpp. Operator settings and both install/rollback guides are
included. Package verification checks paths, hashes, PBO trailer and source map;
checksums do not authenticate a sender. Release requests fail closed.

## Native Windows/signing procedure and limits

[Official DSSignFile documentation](https://community.bohemia.net/wiki/DSSignFile)
and [official DSCheckSignatures documentation](https://community.bohemia.net/wiki/DSCheckSignatures)
support private-key/file signing and checked-directory/keys-directory checking.
Installed executable strings independently confirm these forms; DSSignFile
explicitly defaults to v3 and accepts optional -v2. No checker -s/-n/-v flags are
invented. Installed tool hashes observed:

- DSSignFile.exe: 098f28b46bfe40ad4cf5c60dd3e570e984fe74ae423090b6d3f2da8d7c4e1e78.
- DSCheckSignatures.exe: 9bafbbbdce1e2792515039f99b7150ca1ce97adf16aab8cfc79bdc8938a8503c.

The [official Addon Builder reference](https://community.bistudio.com/wiki/Addon_Builder)
provides the native packing/prefix/copy-list control. Exact deterministic build,
official build comparison, signing and verification commands are in
[tools/package/README.md](../../tools/package/README.md). Official-build source
staging excludes mod.cpp; copy-list verification must establish all scripts were
retained. Official output may differ from our strict canonical stored format.

Native PowerShell commands, from the checkout, with a genuinely installed Windows
Python 3.10+ executable supplied as $Python:

```powershell
powershell.exe -NoProfile -File tools/package/Test-NativePackage.ps1
.\tools\package\Build-Sign-Verify.ps1 -AddonRoot .\mods\HollowCountry -OutputRoot D:\HollowCountryLocal\build-dev-001 -Python $Python -Unsigned
.\tools\package\Invoke-NativeSmoke.ps1 -Pbo D:\HollowCountryLocal\build-dev-001\hollowcountry.pbo -RuntimeRoot D:\HollowCountryLocal\native-smoke-001 -Python $Python -MaxSeconds 180
.\tools\package\Build-Sign-Verify.ps1 -AddonRoot .\mods\HollowCountry -OutputRoot D:\HollowCountryLocal\build-signed-001 -Python $Python -PrivateKey E:\PrivateKeys\HC.biprivatekey -PublicKey E:\PrivateKeys\HC.bikey
```

WSL interop is unavailable; Windows Python installation is unverified. Wrappers
explicitly discover/check Python before writes and reject WindowsApps aliases;
Linux source/package work can proceed. Native AST/synthetic tests need no Python.
This worker did not execute native PowerShell, AddonBuilder, DSSignFile,
DSCheckSignatures, DayZDiag or the normal server. Prior Wine32 BankRev missing
ntdll and Wine64 server missing-config/prelog failures do not establish native
compilation. Main cannot run native Windows scripts here because WSL interop is
blocked. Windows CI will run the native PowerShell AST/synthetic checks after
push; that does not execute the DayZ smoke. Main owns actual final packaging.

The smoke requests gameplay loopback, records actual PID-owned UDP/TCP listeners
or query errors, and makes no process-isolation claim: native Steam query may bind
0.0.0.0. Default timeout is 180 seconds (15–300 configurable), with bounded stop
attempts and explicit forced-stop evidence. Signature0/BattlEye0 are confined to
a fresh disposable smoke runtime, never the friend/live config. The initialization
marker is an observation only; all gameplay/client/persistence acceptance remains
pending. No real signature, production-ready package or accepted loot fix exists.

## Actual TDD evidence

Tests contain explicit synthetic original text, mini-CE definitions and fake
executables/non-keys; no game data fixture. Initial imports failed because the
implementation was absent. Empty stubs were then run to obtain behavioral red
assertions rather than claiming an import failure proved behavior.

| Recorded run in tools/package/ | Actual result |
| --- | --- |
| tdd-red-package.txt | 9 tests; 21 failures, 3 errors, including unsafe paths accepted and wrong wire roundtrip |
| tdd-red-economy.txt | 6 tests; 8 failures, 4 errors, including no core patch and missing policy validation |
| tdd-red-native.txt | 13 tests; 5 errors, including mod.cpp rejection and missing native/sign helpers |
| tdd-red-operator.txt | 14 tests; 1 error: missing packaged operator settings |
| tdd-red-guards.txt | 8 tests; 4 failures, 1 error: malformed stock budgets/flags accepted and profile path pending |
| tdd-red-complete-entries.txt | 9 tests; 2 failures: committed candidate was nonempty and generated fields missing |
| tdd-red-sockets.txt | 15 tests; 1 failure: unsupported process-wide loopback label |
| tdd-red-python.txt | 16 tests; 1 failure: missing native Python preflight |
| tdd-green-package.txt | 16 tests, OK |
| tdd-green-economy.txt | 9 tests, OK |

Exact scoped green commands:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_package.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_economy_contract.py' -v
```

Package tests cover deterministic bytes, independent wire fixture, corruption,
length/compression/header rejection, Windows path hazards, file allowlists,
symlinks, ZIP payload tampering, metadata placement, operator defaults/guides,
release rejection, mocked exact signing arguments and negative checker output.
Economy tests cover no-op defaults, complete retained stock fields, usage union,
profile/vocabulary/conflict rejection, source/output drift, symlink refusal,
exact install/rollback and malformed native budget/flags guards. PowerShell text
checks do not establish native syntax or execution. Main owns the subsequent
full discovery/BDD run after this scope is stable. Windows CI will run native
PowerShell AST/synthetic checks after push; execution is still pending.

No final addon PBO/ZIP was built from the actively edited shared root. Main will
build the unsigned development artifact after all workers stop writing and
record its exact hashes. This follows the integration source freeze.
