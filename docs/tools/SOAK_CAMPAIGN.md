# Soak campaign

One lead command that stages a local test profile, builds and signs the dev-only test addon, boots the local
server, launches the owner's local client with the same mods plus the test addon, feeds the client the scripted
driver steps, idles at least 125 minutes, ends with `activity_check --release`, and restores everything it staged.
It is local evidence ("diag evidence", below the retail boot); it never proves multiplayer.

```
python3 -B -m tools.testing.soak_campaign plan      # default; prints phases, counter map, staging; writes nothing
python3 -B -m tools.testing.soak_campaign stage     # build the test addon and stage the test profile
python3 -B -m tools.testing.soak_campaign run --yes # LEAD ONLY, owner not playing: the whole campaign
python3 -B -m tools.testing.soak_campaign restore   # put every staged byte back; no-op when nothing is staged
python3 -B -m tools.testing.soak_campaign report    # works/broken markdown table of the last run
```

Workers and tests never run `stage` against a real install or `run`. `run` needs `--yes`, takes the shared host lock
(`tools/release/host_lock.py`, holder `soak_campaign`), refuses when the DayZ server or client already runs (so no
player is connected), and stops the client and then the server only through the graceful `CloseMainWindow` path
(never Stop-Process or a kill). If a graceful stop fails the stage is left in place and the tool says to stop the
process by hand and then run `restore`. Run it with `agent-run` only if the memory cap needs it; the campaign itself
is a few MB of Python.

## The test addon

`mods/HollowCountryTest` (PBO prefix `HollowCountryTest`, file `hollowcountrytest.pbo`) holds the scripted client
driver and the setup fixtures. It is never shipped. `tools.package.pbo.TEST_PREFIX` is separate from `PREFIXES`, so
every shipped-bundle parse still refuses it; only `tools/testing/test_addon.py` opens `pbo.test_prefix_scope()`.
`test_addon build` packs it and signs it through the existing Wine flow (`tools/package/sign_wine.py`, the same
development key as the local build; this tool never reads, copies, prints or creates a key) into
`~/.cache/hollow-country/test-addon/@HollowCountryTest`, outside the repository. A unit test asserts that
`ship_inputs.signing_inputs` and the friend bundle file list never name it.

## What `stage` writes (and `restore` removes)

Everything is a copy or a new file, except one in-place edit with a byte backup:

| where | what |
| --- | --- |
| server `soak-profiles/` | copy of the profile folders (not the loose root logs). `HollowCountry/settings.json` gets `EnableSmokeFixtures=true`; the `HollowCountry/measure-cellars` marker is added |
| server `hc-soak.cfg` | copy of `serverDZ.cfg` with a forage-season date (2026/07/15 08:00, 1x so it stays daytime), `instanceId=99` (own storage folder, the real one is untouched) and no persistent time. Contents are never printed (passwords) |
| server `start-server-soak.bat` | copy of `start-server.bat` with `-config=hc-soak.cfg`, `-profiles=soak-profiles` and `@HollowCountryTest` appended to `-mod` |
| server `@HollowCountryTest` | the signed test addon (the existing dev-key public key already sits in the server keys folder) |
| mission `hollow-country-gameplay/gear/soak-test.json` | spawn gear: KitchenKnife, CamoNet, PersonalRadio, Mich2001Helmet, UniversalLight, 9V batteries, DuctTape, Crowbar, Wrench, AKM with a full magazine and a spare |
| mission `cfggameplay.json` | `PlayerData.spawnGearPresetFiles` points at the test preset (original bytes saved in the state folder receipt) |
| client `soak-client-profile/HollowCountry/acceptance/client_driver.json` | the step file from `tools.testing.driver_script.build_route` |

The admin allowlist is the existing local `profiles/HollowCountry/admins.json`, copied with the profile; staging
refuses if it is empty and never prints ids. The receipt and backups live in `~/.cache/hollow-country/soak-campaign`.
`restore` verifies the backup hash, restores the original bytes, removes only the paths the receipt names (a name
outside the fixed allowed set is refused), and keeps the run's RPT files in `last-run/` for `report`.

## Client launch

`DayZ_BE.exe 0 1 1 -exe DayZ_x64.exe -connect=127.0.0.1:2302:27016 -port=2302 -mod=... -profiles=...`, the normal
BattlEye launcher path. The `-mod` list is the server's exact list: own mods from the server root (same bytes as the
server), every other mod from the client's `!Workshop` folder matched by `meta.cpp` `publishedid`, then
`@HollowCountryTest`. A missing Workshop copy refuses the run. BattlEye, signature checks and Steam are never bypassed.

## Phases (`soak_phases.json`)

`join`, `group`, `walk_ai`, `walk_zone`, `walk_town`, `fixtures`, `actions`, then `idle` (at least 125 minutes, longer
than every 120-minute window; DebugSnapshot fires every 300 s). `soak_phases.json` maps every module, and where one
module spans phases a `features` override, so every counter in `config/activity-expectations.json` and every
`[HC Use]` registry literal in the sources has a phase. The only rows that are not a phase are the two-player and
subjective items: `TeamPing/ping_recipients` and `TeamPing/ping_delivered` (friend playtest), and the non-counter
look rows (lighting, grade, audio: owner check; group sharing, team-ping delivery: friend playtest).
`tests/unit/test_soak_campaign.py` fails on any unmapped counter or module and on any manual row outside that list.
Adding a module or a counter to the sources means adding it to the phase file in the same change.

## Report

`report` reads the kept server and client RPTs through the privacy filter (no ids, names or home paths), the
`[HC Driver]` lines and both `activity_check` audits, and writes a markdown table: source, counter, phase, result
(`active`, `zero`, `owner check`, `friend playtest`) and an evidence line. `zero` is broken or not exercised; it is
never relabelled. Exit code 8 when any row is zero. Counters are never bumped or faked by test code; setup-only fixtures
log `fixture=1` and the real feature code then runs.

## Known limits

- `plan` fails until `mods/HollowCountryTest` and `tools.testing.driver_script` (drv and fxsetup briefs) are in the checkout.
- `SettlementDecay` has a 1440-minute window, so its window rows cannot become active in one soak; they report zero.
- Counters no driver step reaches (for example Fortify, Notes, CookingCompat) report zero rather than pass.
