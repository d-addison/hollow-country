# Research Sources and Verification Provenance

**Checked:** 2026-11-16. **Source status:** webpage/documentation research only; nothing has been validated inside a running game installation. **Priority:** official Bohemia documentation/changelogs > official source config repositories > community tools and opinions. Version-dependent details must be rechecked.

## Official Bohemia documentation / data (primary)

1. **[DayZ PC Stable Update 1.30 / DayZ Badlands Is Out Now](https://dayz.com/article/game-update/dayz-badlands-out-now)** — stable release page, associated Steam update 1.30.164289 on 2026-11-03. Verify exact version/build at work start. 1.30 patch notes address modding and Workbench changes, navigation/collision and sound-known issues.
2. **[DayZ 1.30 Experimental Steam Patch Notes](https://dayz.com/article/game-update/1-30-experimental-release/dayz-steam-patch-notes)** — detailed 1.30 feature list, Workbench, `-filePatching` known issue, `disableSimulation` for house-based entities, nav/physics/audio changes. The same features must be checked in *current stable*, not assumed solely from experimental notes.
3. **[Official DayZ Tools on Steam](https://store.steampowered.com/app/830640/DayZ_Tools/)** — Workbench, Addon Builder, Publisher, Terrain Builder, Object Builder and Central Economy Editor.
4. **[DayZ Modding Basics](https://community.bistudio.com/wiki/DayZ:Modding_Basics)** — Windows project drive, file patching, diagnostic game executable, basic mod and multiplayer diagnostic startup.
5. **[DayZ Modding Structure](https://community.bistudio.com/wiki/DayZ:Modding_Structure)** — `Addons`, `Keys`, `CfgPatches`, `CfgMods`, script module paths and mod metadata.
6. **[DayZ Workbench Script Debugging](https://community.bistudio.com/wiki/DayZ:Workbench_Script_Debugging)** — debugger connection to DayZDiag client/server and file-patching workflow.
7. **[DayZ Central Economy Configuration](https://community.bistudio.com/wiki/DayZ:Central_Economy_Configuration)** — economy file definitions and flags, `cfgeconomycore.xml`, limits, spawn settings and globals.
8. **[DayZ Central Economy Mission Files Modding](https://community.bistudio.com/wiki/DayZ:Central_Economy_mission_files_modding)** — custom `<ce folder=...>` append/override mechanism and supported file types.
9. **[DayZ Central Economy Setup for Custom Terrains](https://community.bistudio.com/wiki/DayZ:Central_Economy_setup_for_custom_terrains)** — mission file inventory including `mapgroupproto.xml`, positions, events and other CE sources.
10. **[BohemiaInteractive/DayZ-Central-Economy GitHub](https://github.com/BohemiaInteractive/DayZ-Central-Economy)** — official public CE reference files, release branch/tag history and license. **License is ADPL-SA** per repository. Prefer pinned release/hash and authored diffs to copying game data blindly.
11. **[DayZ Gameplay Settings](https://community.bistudio.com/wiki/DayZ:Gameplay_Settings)** — `cfggameplay.json` and `enableCfgGameplayFile=1` as well as exposed gameplay/config options.
12. **[DayZ Object Spawner](https://community.bistudio.com/wiki/DayZ:Object_Spawner)** — static mission-start object placement via gameplay JSON and Object Spawner JSON, transform data, custom string hook and explicit large-object-count performance warning.
13. **[DayZ Diagnostic Menu](https://community.bistudio.com/wiki/DayZ:Diag_Menu)** — CE Loot Spawn Edit, `mapgroupproto` export, CE debug limitations, profiler UI and script allocations/call counts.
14. **[DayZ Server Configuration](https://community.bistudio.com/wiki/DayZ:Server_Configuration)** — dedicated server config, file-patching permission, simulated player batching and logging/debug controls.
15. **[Bohemia Feedback Tracker](https://feedback.bistudio.com/)** — actual bug reports; search exact 1.30 navigation/audio issues before assuming an engine issue persists.
16. **[Bohemia Arma and DayZ Public License Share Alike](https://www.bohemia.net/community/licenses/arma-and-dayz-public-license-share-alike-adpl-sa)** — licensing for data expressly provided under ADPL-SA, including official CE repo; seek legal review where necessary.

## Optional third-party / community leads (NOT dependency approvals)

- **[InediaInfectedAI Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3031784065)** — player-facing descriptions of additional infected search, door and sound behaviors; verify 1.30 compatibility, mod rights, current feature list and performance locally.
- **[Zen's Zombie Door Bangers Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=2932842394)** — door interaction examples; verify current mod page, permissions and behavior independently.
- **[Dynamic Scavenging Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3682329748)** — existing searchable-furniture design reference; permissions/repacking restrictions mean not reusable source by default.
- **[DayZ Scripts Explorer](https://dayzexplorer.zeroy.com/)** — searchable script documentation for game classes such as `ZombieBase`, but source signatures must be compared against installed build.
- **[StarDZ DayZ Modding Wiki](https://stardz-team.github.io/DayZ-Modding-Wiki/en/)** — additional implementation discussion; lower authority than official docs.
- **[DayZ community Reddit](https://www.reddit.com/r/dayz/)** and **[DayZ Steam discussions](https://steamcommunity.com/app/221100/discussions/)** — qualitative complaints about near-empty apartments, poor loot location diversity, AI navigation, silent/inconsistent infected. Treat as user insight, not proof of exact engine mechanics or current server configs.

## Specific provenance cautions

- **Version:** As of 2026-11-16 the official PC stable DayZ patch is 1.30.164289 (2026-11-03), but next session must verify. New patches can invalidate experimental evidence, scripts or config fields.
- **Building example:** 'double white military barracks with bunk beds' is a user-described appearance; classname not yet verified. Locally identify class and actual geometry before editing `mapgroupproto.xml`.
- **AI crawling:** prior public script references suggest infected have leg-health/crawling transitions. This is still a **hypothesis** until examined in installed version 1.30 scripts and witnessed in game.
- **AI sound/path:** patch notes show relevant bugs exist, but do not establish that any given bug is fixable through Enforce Script.
- **Layout:** Object Spawner is static at mission startup; per-building RNG, layout identity and interactive depletion require other logic/data and careful performance validation.
- **No user-specific file or private GitHub repo was accessed** in this handoff. No prior Northmen files or source code are used or bundled.
