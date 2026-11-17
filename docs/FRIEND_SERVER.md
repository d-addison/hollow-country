# Friend server: mods, build and ports

Status: procedure for the private 3–6-player friend server. Nothing here has been
exercised on that server yet; the owner's local session (`docs/LOCAL_ACCEPTANCE_V1.md`)
comes first. Server settings are in `mission/hollow-country/INSTALL_AND_ROLLBACK.md`
(Server configuration for the friend server).

## Mods each player needs

Only our own signed `@HollowCountry` is published, as an **Unlisted** Steam Workshop
item (Steam visibility value 3: hidden from Workshop search, visible to anyone with
the link). When a friend joins the server, the DayZ launcher subscribes to the
mods in the server's mod list automatically, so nobody copies folders by hand.
Third-party content is never published or bundled: SNAFU Weapons (2443122116),
Tactical Flava (2646817942), CF (1559212036), Dabs Framework (2545327648),
Expansion-Core (2291785308), Expansion-Animations (2793893086) and Expansion-AI
(2792982069) stay separate Workshop dependencies, referenced by id in
`tools/setup/workshop_mods.json`. `@HollowCountryExpansionAI` is a `-serverMod`
built locally on the server and is never published. This path is untested until
the owner has uploaded the item and a friend has joined through it. The fallback
is still to build and sign `@HollowCountry` locally (see
`docs/LOCAL_ACCEPTANCE_V1.md`, Build, sign and verify), install its public
`.bikey` under the server's `keys`, and give each player the same signed folder
for "Add local mod". Every player must run the same build as the server.

| Set | Server | Each player | Notes |
| --- | --- | --- | --- |
| Base | `@HollowCountry` in `-mod`, its key | the Unlisted `@HollowCountry` Workshop item (same build) | No third-party mod is required. CF is not needed for the base mod. |
| SNAFU subset (optional) | SNAFU Weapons in `-mod`, its key | subscribe to SNAFU Weapons | SNAFU does not depend on CF. |
| Tactical Flava subset (optional) | Tactical Flava in `-mod`, its key | subscribe to Tactical Flava | Tactical Flava does not depend on CF. |
| PvE patrols (optional) | CF, Dabs Framework, Expansion-Core, Expansion-Animations and Expansion-AI in `-mod`, each mod's key; `@HollowCountryExpansionAI` in `-serverMod` | subscribe to CF, Dabs Framework, Expansion-Core, Expansion-Animations and Expansion-AI | Only this set needs CF. Expansion is never repacked or bundled. Players do not load `@HollowCountryExpansionAI`. |

Load order in `-mod`: CF, then Dabs Framework, then the Expansion mods (Core, then
Animations, then AI), then SNAFU, then Tactical Flava, then `@HollowCountry`. Then
`-serverMod=@HollowCountryExpansionAI`. Every player's `-mod` list must match the
server's client-side list. A mismatch is refused at join.

## Publishing `@HollowCountry` (the owner)

The owner runs the upload and the login. The tools never ask for, store, log or pass a
Steam password; steamcmd's interactive login and Steam Guard handle that.

1. Build and sign `@HollowCountry` with DayZ Tools and your private key.
2. `python3 -B tools/package/workshop_publish.py prepare --mod <signed @HollowCountry> --out <empty dir> [--preview <png>] [--published-id N] [--change-note TEXT]`.
   It accepts only `addons/hollowcountry.pbo` with its `.bisign`, `keys/*.bikey`,
   `mod.cpp` and `meta.cpp`. It refuses private keys (`.biprivatekey`), extra PBOs,
   profiles, logs, source, symlinks and hard links. It stages a clean copy, writes a
   `workshop_build_item` VDF (appid 221100, `visibility "3"` Unlisted) and prints the
   command to run. Only `unlisted` is accepted for `--visibility`. Use `--path-style
   windows` if steamcmd runs on Windows and the paths are WSL paths.
3. Run the printed command yourself:
   `steamcmd +login <your_username> +workshop_build_item <vdf> +quit`. Type the
   password and the Steam Guard code into steamcmd when it asks.
4. After the first upload, note the Workshop id and run
   `python3 -B tools/package/workshop_publish.py record --mod <@HollowCountry> --published-id N`.
   It writes `publishedid = N;` into the mod's `meta.cpp` (the launcher uses it to
   map the mod to its Workshop item) and later `prepare` runs update the same item.
   Rebuild the VDF with `prepare` after recording so the staged copy has the new `meta.cpp`.
   Also record the id for the server tool: `--hollowcountry-id N`.

Alternative without steamcmd: the DayZ Tools **Publisher** (Steam, DayZ Tools,
Publisher). Choose the staged `content` folder that `prepare` wrote (it has already been
checked), set the visibility to Unlisted, upload, then run `record` with the id it shows.

## Server mod sync (the friend or the owner)

`tools/setup/workshop_sync.py` brings the mods the server needs into the server folder.
It reads `tools/setup/workshop_mods.json` (ids, folder names, load order, groups `base`,
`snafu`, `tactical_flava`, `pve_patrols`).

- `plan --server-root <dir> --groups base,pve_patrols [--workshop-content <dir>] [--steamcmd <path>]`
  lists the Workshop ids needed, which are already downloaded (a Steam client's or
  steamcmd's `steamapps/workshop/content/221100`) and what would be copied. It writes nothing.
- `fetch --server-root <dir> --groups ... --steam-user <login> [--install-dir <dir>]` runs
  `steamcmd +login <login> +workshop_download_item 221100 <id> validate ... +quit`. You type
  the password into steamcmd yourself; there is no password option. Each item is then
  checked for `addons/` and `keys/`.
- `install --server-root <dir> --groups ...` copies (never symlinks) each item into
  `<server-root>/@<Folder>` and its public `.bikey` files into `<server-root>/keys`. It copies
  only `addons/*.pbo` and `*.bisign`, `keys/*.bikey`, `mod.cpp` and `meta.cpp`, refuses
  private keys, symlinks and a different existing file, and checks everything before it writes.
  A re-run changes nothing. It refuses while a DayZ server process is running
  (`--assume-stopped` skips that check).
- `rollback --server-root <dir>` removes exactly what `install` added, using the receipt
  `hollow-country-workshop-receipt.json` in the server root. Files you changed since are left in place.

`install` and `plan` print the `-mod=` and `-serverMod=` lines in load order. Our own
`@HollowCountry` has no id in the manifest until it is published; pass
`--hollowcountry-id N` to fetch and install it too. `@HollowCountryExpansionAI` is built
locally, never fetched or published, and only appears in the `-serverMod=` line.

Port forwarding (the friend's router, UDP): the game port (`-port`, default 2302)
plus the next three ports (2303–2305), and `steamQueryPort` (27016 by default) so
the server shows up in the browser. Keep BattlEye and `verifySignatures = 2` on.
