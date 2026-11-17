# Friend server: mods, build and ports

Status: procedure for the private 3–6-player friend server. Nothing here has been
exercised on that server yet; the owner's local session (`docs/LOCAL_ACCEPTANCE_V1.md`)
comes first. Server settings are in `mission/hollow-country/INSTALL_AND_ROLLBACK.md`
(Server configuration for the friend server).

## Mods each player needs

Only our own signed mods are published, each as its own **Unlisted** Steam Workshop
item (Steam visibility value 3: hidden from Workshop search, visible to anyone with
the link):

- `@HollowCountry`, Workshop item **3841628320**, which every player needs.
- `@HollowCountryExpansionAI`, Workshop item **3841637854**, "Hollow Country Expansion
  AI (server)". It is a server-side `-serverMod` addon for servers that run Expansion AI;
  players never load or subscribe to it.

`workshop_publish.py` knows both ids and refuses to prepare or record one item with the
other item's id, so an upload can never overwrite the wrong item.

When a friend joins the server, the DayZ launcher subscribes to the mods in the
server's `-mod` list automatically, so nobody copies folders by hand.
Third-party content is never published or bundled: SNAFU Weapons (2443122116),
Tactical Flava (2646817942), CF (1559212036), Dabs Framework (2545327648),
Expansion-Core (2291785308), Expansion-Animations (2793893086) and Expansion-AI
(2792982069) stay separate Workshop dependencies, referenced by id in
`tools/setup/workshop_mods.json`. This path is untested until
the owner has uploaded the items and a friend has joined through them. The fallback
is still to build and sign `@HollowCountry` locally (see
`docs/LOCAL_ACCEPTANCE_V1.md`, Build, sign and verify), install its public
`.bikey` under the server's `keys`, and give each player the same signed folder
for "Add local mod". Every player must run the same build as the server.

| Set | Server | Each player | Notes |
| --- | --- | --- | --- |
| Base | `@HollowCountry` in `-mod`, its key | the Unlisted `@HollowCountry` Workshop item (same build) | No third-party mod is required. CF is not needed for the base mod. |
| SNAFU subset (optional) | SNAFU Weapons in `-mod`, its key | subscribe to SNAFU Weapons | SNAFU does not depend on CF. |
| Tactical Flava subset (optional) | Tactical Flava in `-mod`, its key | subscribe to Tactical Flava | Tactical Flava does not depend on CF. |
| PvE patrols (optional) | CF, Dabs Framework, Expansion-Core, Expansion-Animations and Expansion-AI in `-mod`, each mod's key; `@HollowCountryExpansionAI` in `-serverMod` (its Workshop item once published, else the local signed build) | subscribe to CF, Dabs Framework, Expansion-Core, Expansion-Animations and Expansion-AI | Only this set needs CF. Expansion is never repacked or bundled. Players do not load `@HollowCountryExpansionAI`. |

Load order in `-mod`: CF, then Dabs Framework, then the Expansion mods (Core, then
Animations, then AI), then SNAFU, then Tactical Flava, then `@HollowCountry`. Then
`-serverMod=@HollowCountryExpansionAI`. Every player's `-mod` list must match the
server's client-side list. A mismatch is refused at join.

## Publishing `@HollowCountry` and `@HollowCountryExpansionAI` (the owner)

The owner runs the upload and the login. The tools never ask for, store, log or pass a
Steam password; steamcmd's interactive login and Steam Guard handle that.

`prepare` and `record` take `--item base` (the default, `@HollowCountry`) or
`--item addon` (`@HollowCountryExpansionAI`). Each item is a separate Workshop item
with its own allowlist, title and description. A base folder given as `--item addon`,
or the reverse, is refused.

1. Build and sign the mod with DayZ Tools and your private key.
2. `python3 -B tools/package/workshop_publish.py prepare [--item base] --mod <signed @HollowCountry> --out <empty dir> [--preview <png>] [--published-id N] [--change-note TEXT]`.
   For `base` it accepts only `addons/hollowcountry.pbo` with its `.bisign`,
   `keys/*.bikey`, `mod.cpp` and, optionally, `meta.cpp`. It refuses private keys
   (`.biprivatekey`), extra PBOs, empty files,
   profiles, logs, source, symlinks and hard links. It stages a clean copy, writes a
   `workshop_build_item` VDF (appid 221100, `visibility "3"` Unlisted) and prints the
   command to run. Only `unlisted` is accepted for `--visibility`. Use `--path-style
   windows` if steamcmd runs on Windows and the paths are WSL paths.
3. Run the printed command yourself:
   `steamcmd +login <your_username> +workshop_build_item <vdf> +quit`. Type the
   password and the Steam Guard code into steamcmd when it asks.
4. After the first upload, note the Workshop id and run
   `python3 -B tools/package/workshop_publish.py record --item base --mod <@HollowCountry> --published-id N`.
   It writes `publishedid = N;` into the mod's `meta.cpp` (the launcher uses it to
   map the mod to its Workshop item) and later `prepare` runs update the same item.
   Rebuild the VDF with `prepare` after recording so the staged copy has the new `meta.cpp`.
   The base item is already recorded in `tools/setup/workshop_mods.json` as 3841628320,
   so `workshop_sync.py` fetches it without extra options.

### The server-only addon item

Run the same steps with `--item addon` on the signed `@HollowCountryExpansionAI` folder:

```
python3 -B tools/package/workshop_publish.py prepare --item addon --mod <signed @HollowCountryExpansionAI> --out <empty dir> [--preview <png>]
steamcmd +login <your_username> +workshop_build_item <vdf> +quit
python3 -B tools/package/workshop_publish.py record --item addon --mod <@HollowCountryExpansionAI> --published-id N
```

- Allowlist: `addons/hollowcountryexpansionai.pbo` with its `.bisign`, `keys/*.bikey`,
  and optional `mod.cpp` and `meta.cpp`. Every refusal rule of the base item applies.
- The VDF carries the title "Hollow Country Expansion AI (server)" and a description
  saying this is a server-side `-serverMod` addon for Hollow Country servers that run
  Expansion AI, that players do not need it, and that Expansion, CF and Dabs Framework
  are separate Workshop items that are never bundled.
- `record` creates `meta.cpp` with that title as its `name` line when the folder has none.
- The first upload created item 3841637854, which `tools/setup/workshop_mods.json`
  records. Later uploads pass `--published-id 3841637854` (or a recorded `meta.cpp`).

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
mods with an id in the manifest are fetched and installed like the third-party ones:
`@HollowCountry` (3841628320) and `@HollowCountryExpansionAI` (3841637854) both have one.
`--hollowcountry-id N` only supplies an id for `@HollowCountry` if the manifest has none.
An own mod whose id is `null` is reported as unpublished and never fetched. It is a server-side mod: it only ever appears in
the `-serverMod=` line, never in `-mod=`.

Port forwarding (the friend's router, UDP): the game port (`-port`, default 2302)
plus the next three ports (2303–2305), and `steamQueryPort` (27016 by default) so
the server shows up in the browser. Keep BattlEye and `verifySignatures = 2` on.

## Friend bundle (the owner builds it, the friend unpacks it)

`tools/setup/friend_bundle.py` packs everything our side owns into one folder the
owner hands to the friend privately (zip it, then send it by a private channel). It
contains no Workshop or game content, so the friend still runs `workshop_sync.py fetch`
or the steamcmd lines in its `README.txt` for the dependencies.

```
python3 -B -m tools.setup.friend_bundle build \
  --mission <server>/mpmissions/dayzOffline.chernarusplus \
  --profiles <server profiles dir> \
  --mod <signed @HollowCountry> [--addon <signed @HollowCountryExpansionAI>] \
  --server-cfg <server>/serverDZ.cfg --out <new dir>
```

- `mpmissions/`: the installed mission without `storage_*` (player and world state),
  rollback copies (`*.backup`, `*.next`), receipts and logs.
- `profiles/`: an allowlist of Hollow Country and Expansion AI settings, enable
  markers and the interior template pack. It leaves out runtime state (event commits,
  group state, leases and search journals) and logs.
- `@HollowCountry/` and, with `--addon`, `@HollowCountryExpansionAI/` (signed PBOs
  only) plus `keys/` with the public `.bikey`.
- `start-server.bat`: the `-mod=` and `-serverMod=` lines in manifest load order.
  Without `--addon`, the PvE patrol set and the server mod are left out.
- `serverDZ-hollow-country.txt`: the values to merge into the friend's own
  `serverDZ.cfg` (camera, time acceleration, `enableCfgGameplayFile`, mission
  template). It never carries passwords or the hostname.
- `README.txt`: the steamcmd download line per Workshop dependency, the copy steps,
  `verifySignatures = 2` and the ports.
- `bundle-manifest.json`: SHA-256 for every file, so the friend can check the copy.

It refuses a private key or symlink anywhere in the inputs, an unsigned PBO, a missing
`.bikey` and an existing output directory. It has only run against the owner's local
server. A friend's real install and join are still untested.
