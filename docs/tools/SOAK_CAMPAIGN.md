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

During `run`, SIGTERM follows the same graceful shutdown path as Ctrl-C: stop the client and server, preserve
evidence in `last-run/`, then restore once every process is confirmed gone. A transient Windows interop failure
retries the `CloseMainWindow` request up to three times, ten seconds apart, checking for an already exited
process before each retry; close calls, delays and state queries are bounded to 1108 seconds per image,
followed by the existing bounded shutdown confirmation loop. A process still running leaves the stage in place
with the existing hand-stop/restore message. While waiting for the driver, 15 minutes without a new
`[HC Driver] step=` line together with zero-player `[HC Perf] players_max=0` samples spanning that whole interval
ends the driver wait early and logs `run: driver stalled minutes=<m> last_step=<id|none>; idling to the minimum duration`.
It then follows the budget-timeout idle path, waiting until the later of the minimum duration and the fallback
idle deadline; a normal final driver receipt retains its existing 120-second grace and minimum duration.

## The test addon

`mods/HollowCountryTest` (PBO prefix `HollowCountryTest`, file `hollowcountrytest.pbo`) holds the scripted client
driver and the setup fixtures. It is never shipped. `tools.package.pbo.TEST_PREFIX` is separate from `PREFIXES`, so
every shipped-bundle parse still refuses it; only `tools/testing/test_addon.py` opens `pbo.test_prefix_scope()`.
`test_addon build` packs it and signs it through the existing Wine flow (`tools/package/sign_wine.py`, the same
development key as the local build; this tool never reads, copies, prints or creates a key) into
`~/.cache/hollow-country/test-addon/@HollowCountryTest`, outside the repository. A unit test asserts that
`ship_inputs.signing_inputs` and the friend bundle file list never name it.

The lead can compile the test addon with the pinned runtime stack before staging a soak. The gate
loads the addon in its disposable server and checks for the Mission marker. The retail campaign
supplies the client and fixture evidence.

```sh
agent-run --memory 12G -- python3 -B -m tools.release.compile_gate --commit "$candidate_sha" --test-addon
```

## What `stage` writes (and `restore` removes)

Everything is a copy or a new file, except one in-place edit with a byte backup:

| where | what |
| --- | --- |
| server `soak-profiles/` | copy of the profile folders (not the loose root logs). `HollowCountry/settings.json` gets `EnableSmokeFixtures=true` and `FortifyBreachSeconds=20` (so one scripted barricade is breached inside the run); the `HollowCountry/measure-cellars` marker is added |
| server `hc-soak.cfg` | copy of `serverDZ.cfg` with a forage- and mushroom-season dusk start (2026/09/15 17:50, 1x: camp visitors and ecology water windows open, SignsOfLife's 18:00 threshold crossed after 10 minutes, daylight until about 19:00), `instanceId=99` (own storage folder, the real one is untouched) and no persistent time. Contents are never printed (passwords) |
| server `start-server-soak.bat` | copy of `start-server.bat` with `-config=hc-soak.cfg`, `-profiles=soak-profiles` and `@HollowCountryTest` appended to `-mod` |
| server `@HollowCountryTest` | the signed test addon (the existing dev-key public key already sits in the server keys folder) |
| mission `hollow-country-gameplay/gear/soak-test.json` | spawn gear: every item a default driver action needs (KitchenKnife, CamoNet, PersonalRadio, Mich2001Helmet, TortillaBag, UniversalLight x2, Flashlight, 9V batteries, DuctTape x2, Crowbar, Wrench, Pliers, Rag, Paper, Pen_Black) and an AKM with a full magazine and a spare |
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

After a lost launch reply, the process check polls every five seconds for 30 seconds. Any running image
confirms the launch; all images gone at that deadline permits the normal retry. If any image is still
unknown, polling continues for up to 180 additional seconds without another launch. During that extra
window, a retry requires all images to read gone for a full 30 seconds after the last unknown reading.
If no image is running and that confirmation has not completed before the extra deadline, the run refuses
with the hand-check/restore message. These polling windows exclude time spent querying process state.

## Phases (`soak_phases.json`)

`join`, `group`, `walk_ai`, `walk_zone`, `walk_town`, `fixtures`, `actions`, `scene`, `forest`, then `idle` (at least
125 minutes, longer than every 120-minute window; DebugSnapshot fires every 300 s). `soak_phases.json` maps every
module, and where one module spans phases a `features` override, so every counter in
`config/activity-expectations.json` and every `[HC Use]` registry literal in the sources has a phase. The only rows
that are not a phase are the two-player and subjective items: `TeamPing/ping_recipients` and
`TeamPing/ping_delivered` (friend playtest), `Cellars/visual_applied` (owner check, see below), and the non-counter
look rows (lighting, grade, audio: owner check; group sharing, team-ping delivery: friend playtest).
`tests/unit/test_soak_campaign.py` fails on any unmapped counter or module and on any manual row outside that list.
Adding a module or a counter to the sources means adding it to the phase file in the same change.

## Reach map

Every counter row also has a `reach` entry (`counter -> {phase, class, how}`) naming the concrete mechanism that
produces it in one scripted soak. `plan` prints one line per row and `unreached=<n>`; it fails when n is above 0,
and a unit test asserts the shipped map has `unreached=0`. A `how` is a list of tokens, each checked against the
checkout:

| token | meaning |
| --- | --- |
| `boot` | fires from the module start, no input |
| `timer:<N>m` | a background timer within the 125-minute idle (N from 1 to 125) |
| `step:<token>` | a driver step on or before the counter's phase (`walk:<source>`, `menu:<name>`, `admin:<cmd>`, `group:<op>`, `action:<name>`, `stand`, `sprint`, `wait`, `ping`) |
| `fixture:<fx_cmd>` | a setup-only fixture the driver sends; the command must exist in a source and be a step of the plan |
| `setting:<Key>` | a test-profile setting written by staging (`SOAK_SETTINGS`) |
| `gear:<Class>` | an item in the soak gear preset |
| `marker:measure-cellars` | the cellar-sampler marker file staged with the profile |
| `code:<File.c>` | the file holding the counter call; must exist under `mods` |

Every row needs at least one `code:` token and one trigger token (`boot`, `timer`, `step`, `fixture`, `setting` or
`marker`). Classes are `required` (default-on activity expectation) and `diagnostic` (optional counters).

New phases: `scene` walks to the Kamenka scene chain site, asks for its scene (`admin scene`), takes paper, reads the
lead notes and writes one; `forest` walks to the Bor South Rest barn point (a woodland waypoint from `travel/route-surveys.json`; the
catalog shelter there refuses terrain, and the phase never uses it), forces the forage tick
(`admin forage`), picks forage and stands under the trees for the wind loop. The `scene:<chain id>` waypoint source
reads the first stop of `events/scene-chains.json` (the other sources are `ai/sites.json`, `ai/zones.json` and
`travel/route-surveys.json`); the driver still walks there on foot.

Setup-only fixtures added in the test addon (`mods/HollowCountryTest/scripts/4_World/HCTestReachFixtures.c`, catalog
rows `fx_animal`, `fx_food`, `fx_cooking`, `fx_kit_place`, `fx_kit_refuse`, `fx_barricade`, `fx_melee`, `fx_shoot` in
`HCAdminCatalog.c`) log `[HC Fixture] cmd=<c> fixture=1 result=ok` and then the real code path runs: `fx_kit_place` and
`fx_kit_refuse` finish a real deploy action (Fortify placed and refused), `fx_barricade` presses an infected
against the barricade (breached after 20 s), `fx_food` and `fx_cooking` create a `_DON` food and a `CookZ_` pot
(FoodCompat guard, CookingCompat dish), `fx_animal` places an animal for the pack counter, `fx_shoot_held` fires the
requester's held weapon at the nearest HC AI (InfectedMemory heat, AITactics fire events, AISelfDefence hit
reaction; `fx_shoot` is retired and refuses: a world-weapon `Weapon.Fire` crashed the server natively in soak 201), and `fx_melee` calls `ProcessMeleeHitName` on a spawned infected (Melee hit, wall veto, parity
probe). No fixture bumps or credits a counter.

`Cellars/visual_applied` is an owner check: the client counter needs the player more than 2 m below terrain inside
a building, no repo file names a cellar, and a player may not be teleported, so there is no honest scripted
exercise (`r3_smoke_plan.json` records the same). The cellar sampler itself (`CellarSampler/class_measured`,
`Cellars/cellars_measured`) is scripted through the marker.

The `actions` phase crouches the player before world crafting, and the default craft, mount, salvage and flip items are
all in the soak gear preset (a unit test checks the preset against the action arguments).

## Report

`report` reads the kept server and client RPTs through the privacy filter (no ids, names or home paths), the
`[HC Driver]` lines and both `activity_check` audits, and writes a markdown table: source, counter, phase, result
(`active`, `zero`, `owner check`, `friend playtest`) and an evidence line. `zero` is broken or not exercised; it is
never relabelled. Exit code 8 when any row is zero. Counters are never bumped or faked by test code; setup-only fixtures
log `fixture=1` and the real feature code then runs.

## Known limits

- `Events/mission_radius_entered` requires foot travel across a live, published mission circle. The scripted
  `walk_zone` step resolves a static Balota guard zone. Its reach-map token verifies that the step exists, and
  the idle phase can outlast the driver, so a mission published during idle may have no movement at all.
  The client receives up to 16 expiring circles from committed missions already published to its map. The
  Hollow Country map needs ordinary map access and the mission layer enabled both in the group snapshot and
  in the client's layer controls. A visible circle within walking distance still depends on live mission
  publication, remaining time and traversable terrain. The driver accepts fixed destinations and cannot wait
  for a circle or replace a destination when one expires.
- For a focused leader-run check with one client, wait for a live circle to appear in the ordinary map. Pick one
  with enough time left to reach its edge on foot and hold on each side. Start outside, or first leave the circle
  if the character is already inside. Stay outside for more than one full sampling rotation, then walk across and
  stay inside the same circle through another rotation. The server samples at most one of up to 16 circles per
  two-second poll, so a full stable rotation is nominally up to 32 seconds. Shared work-budget deferrals can
  delay it. Use `[HC Use] module=Events feature=mission_radius_entered count=1` in this client's RPT as proof of
  the crossing. If no eligible circle appears, the circle expires or the counter stays at zero, leave the row
  unverified.
- Retail DayZ has no scripted client melee input: melee is started from the player's own input
  (native `3_Game/human.c`, the UAInput `SyncedOverride` exists only under `INPUT_OVERRIDE`), so the driver
  cannot press an attack. The Melee player-attacker counters are reached server-side by `fx_melee` calling the
  native `DayZPlayer.ProcessMeleeHitName` (native `3_Game/dayzplayer.c`). A real
  infected or AI hit on a player only raises the victim-side melee counters (poise, block, guard break, glance).
- `SettlementDecay`'s `w=` value is an upper bound on its window, not the time it takes: the first decay pass
  and the `admin decay` command in the `actions` phase produce the counters inside one soak.
