# Firearms roster, datamine census and optional SNAFU subset (issue #30)

Status: offline tooling and proposals only. Nothing here is enabled in production, nothing was observed
in DayZ, and every count is a proposal for 3-6 players. Static file checks never establish game behaviour.
The v1 test candidate spawns the datamined rows below at rare counts; each one is marked
`acceptance: pending-local` until the owner accepts it (or switches it off) in a local session.

Owner decision for #30: a curated, minimal wood-stock and conventional-modern vanilla roster; a datamine
of unfinished or non-spawning vanilla weapons proposed as candidates only; and an allowlisted subset of
SNAFU Weapons as an optional dependency. Nothing futuristic.

## 1. Curated vanilla roster

`tools/package/firearms_roster.json` is the curated class list (the only firearm data committed).
`tools/package/firearms.py` turns it into a minimal Central Economy delta:

```
python3 -m tools.package.firearms generate --source <stock mission copy> --out <new delta dir>
python3 -m tools.package.firearms install  --delta <delta dir> --target <stopped private mission copy>
python3 -m tools.package.firearms rollback --target <that mission copy>
```

- Generate reads installed stock `types.xml`, copies each rostered type verbatim and changes only
  `nominal`, `min`, `lifetime`, `restock`, `usage` and `value`. Flags, cost and quantities stay stock.
  Only changed entries are written, to the managed folder `hollow-country/ce/types.xml`, registered by one
  `<ce folder>` line in `cfgeconomycore.xml`. No placement files are touched.
- Install refuses the Steam path, symlinks, drifted stock and any candidate that changes a field outside
  the allowed set. Rollback restores `cfgeconomycore.xml` byte for byte (tested, including on a copy of the
  real stock files).
- `economy.install(..., mutable=...)` gained an additive keyword; the default (usage only) is unchanged.

Roster: 37 weapons (12 conventional modern, 15 wood-stock vanilla-spawning and 10 datamined wood-stock
rows), 18 magazines and 12 ammunition types. Owner decision 2026-11-17: scarcity is "double generous, 2x for
now". Weapon nominals total 342 (306 without the datamined rows; the first proposal was 164), no weapon
exceeds nominal 28, and the min/nominal ratios of the first proposal are kept. Each entry carries a role
(`wood` or `modern`), a tier (`common`, `uncommon`, `rare`) and a justification.

Final weapon counts (nominal / min):

| Class | Role | Tier | Nominal / min | Note |
| --- | --- | --- | --- | --- |
| `Mosin9130` | wood | common | 24 / 18 | |
| `Mosin9130_Woodland` | wood | uncommon | 10 / 6 | |
| `SKS` | wood | uncommon | 12 / 8 | |
| `SKS_Woodland` | wood | rare | 6 / 4 | |
| `Izh18` | wood | common | 28 / 22 | |
| `Izh18Shotgun` | wood | common | 20 / 16 | |
| `Izh43Shotgun` | wood | uncommon | 16 / 12 | |
| `Repeater` | wood | uncommon | 16 / 12 | |
| `Winchester70` | wood | uncommon | 10 / 8 | |
| `CZ527` | wood | common | 16 / 12 | |
| `CZ527_Woodland` | wood | uncommon | 10 / 8 | |
| `B95` | wood | uncommon | 10 / 8 | |
| `Mp133Shotgun` | wood | uncommon | 8 / 6 | |
| `Magnum` | wood | uncommon | 10 / 8 | |
| `AKM` | wood | rare | 4 / 2 | |
| `Colt1911` | modern | uncommon | 16 / 12 | |
| `MakarovIJ70` | modern | common | 16 / 12 | |
| `P1` | modern | common | 12 / 10 | |
| `Glock19` | modern | uncommon | 12 / 10 | |
| `FNX45` | modern | rare | 6 / 4 | |
| `CZ75` | modern | uncommon | 8 / 6 | |
| `Ruger1022` | modern | common | 12 / 8 | |
| `M16A2` | modern | rare | 4 / 2 | |
| `AK74` | modern | rare | 6 / 4 | |
| `MP5K` | modern | rare | 6 / 4 | |
| `Saiga` | modern | rare | 4 / 2 | |
| `SVD` | modern | rare | 4 / 2 | |
| `LeeEnfield` | wood | uncommon | 12 / 8 | datamined, `acceptance: pending-local` |
| `MP18` | wood | rare | 4 / 2 | datamined, `acceptance: pending-local` |
| `Luger` | wood | rare | 6 / 4 | datamined, `acceptance: pending-local` |
| `SKS_Black`, `SKS_Desert`, `SKS_Green`, `SKS_Winter` | wood | rare | 2 / 1 each | datamined, `acceptance: pending-local` |
| `Mosin9130_Black`, `Mosin9130_Winter` | wood | rare | 2 / 1 each | datamined, `acceptance: pending-local` |
| `SVD_Wooden` | wood | rare | 2 / 1 | datamined, `acceptance: pending-local` |

Magazines and ammunition are scaled by the same factor. The datamined magazines `Mag_LeeEnfield_10Rnd`
(8 / 4), `Mag_MP18_Drum32Rnd` (4 / 2) and `Mag_Luger_8Rnd` (8 / 4) carry the same marker.

### Datamined rows and the single switch

Owner decision 2026-11-17: datamined vanilla guns (stock nominal 0 or absent: Lee-Enfield, MP18, Luger and
the finished skin variants) spawn at rare counts in the v1 test candidate. Each such roster entry has
`"datamined": true` and `"acceptance": "pending-local"` (the two fields must appear together, and a
non-datamined weapon may not depend on a datamined magazine). The generated report lists every such class
under `datamined` with its `acceptance`.

One switch turns them all off: `--no-datamined` on `firearms generate` (API: `generate(...,
include_datamined=False)`). The delta is then built from the non-datamined rows only, so the owner can accept
or drop them in the local session without editing the roster. Accepting a row means changing its marker after
local spawn, fire and ammo trials; nothing here records that acceptance.

Nine finished variants that are absent from stock `types.xml` (`MakarovPB`, `Winchester70_Black`,
`Winchester70_Green`, `B95_Black`, `B95_Green`, `CZ527_Camo`, `CZ527_Green`, `CZ527_desert`,
`CZ527_winter`) stay under `deferred_datamined`. The generator only overrides stock entries (install refuses
a class that stock does not define), so enabling them needs a new-type-entry install path; that is deferred.

### Optics extension point

Both `firearms_roster.json` and `snafu_allowlist.json` carry `"optics": {"status":
"deferred-pending-owner-decision", "entries": []}`. Validation accepts the block only in exactly that empty
form, so no optic can be added by accident; a later owner decision extends the schema (and the validators)
deliberately. No optic is rostered or allowlisted now.

### Install and rollback hardening

Install and rollback treat every managed or staging path (`core.backup`, `core.next`, `receipt.json`,
`ce/types.xml`, `verification.json`) as hostile until checked: it must be a regular file (not a symlink,
FIFO or directory), have `st_nlink == 1` and resolve inside the mission. Staging files are unlinked and
created fresh (`O_EXCL`, `O_NOFOLLOW`), then moved into place with `os.replace`, so a hard link to an outside
file is never written through. Unexpected entries in the managed folder refuse rollback. Tests assert the
outside file stays byte for byte identical.

## 2. Datamine census

`tools/audit/firearm_census.py` (with `tools/audit/pbo_config.py`, a bounded streaming PBO and
rapified-config reader) classifies every `scope=2` weapon class by cross-referencing `types.xml`,
`cfgspawnabletypes`, `cfgrandompresets`, event files and `db/events.xml`, and checks model, hand-animation
and magazine presence. Inputs are read only; the full output goes outside Git:

```
python3 -m tools.audit.firearm_census --addons LABEL=<dir> [--addons ...] --mission <mission dir> \
        --out ~/.cache/hollow-country/firearm-census-<date>
```

The tool refuses any output directory inside a Git checkout. The 2026-11-17 run (static evidence only):

| Classification | Classes |
| --- | --- |
| spawning | 61 |
| nominal-zero (finished, stock nominal 0) | 43 |
| missing-from-types | 32 |
| scope-not-public | 5 |
| event-only | 0 |
| unknown | 0 |

141 weapon classes plus 69 abstract scope-0 bases. Two classes are flagged as suspected unfinished
(`SV98`, `DartGun`) and are not proposed.

Datamined classes enabled at rare counts, pending local acceptance: `LeeEnfield`, `MP18`, `Luger`, `SKS_Black`,
`SKS_Desert`, `SKS_Green`, `SKS_Winter`, `Mosin9130_Black`, `Mosin9130_Winter` and `SVD_Wooden` (see section 1).
The nine variants missing from stock types remain deferred (`deferred_datamined`); `MakarovPB` also needs its
magazine added. Every datamined candidate needs spawn, firing and ammo trials on a local server with one client.

## 3. Optional SNAFU Weapons subset

Item: SNAFU Weapons, Steam Workshop 2443122116 (about 3.66 GB, version 1.28.1, last updated 2026-10-18).
Code: `tools/package/snafu_optional.py`; data: `tools/package/snafu_allowlist.json`.

### Rights inventory

Primary source: the installed terms file `Readme_Terms/Mod_Terms_Of _Use_DPL_ND.pdf` (6 pages, sha256
`2bb0e30c7b17c487e67151a0a7cf9fc094062b861ecb9e79ff277bfe86696daf`), the DayZ Public License - No
Derivatives (DPL-ND). Relevant clauses:

- Section 2(a)(1): the license grants rights to "reproduce and Share the Licensed Material ... for
  NonCommercial and DAYZOnly purposes only" and to produce but "not Share Adapted Material".
- Section 3(a): sharing requires attribution, a notice that refers to the license and "indicate if You
  modified the Licensed Material"; "You do not have permission under this Public License to Share Adapted
  Material."
- Section 2(a)(5)(b): "No downstream restrictions".

Secondary sources (the web page is read after the installed PDF):

- Workshop page https://steamcommunity.com/sharedfiles/filedetails/?id=2443122116 and the Steam API record
  https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/ (item 2443122116; the page
  itself was rate-limited, so the API description was read). The description repeats the DPL-ND text and
  adds author conditions: use on a server "provided it is not repackaged or redistributed"; monetized
  servers and commercial use "only with prior written permission"; no modification, repackaging or
  redistribution of PBO content; "You are permitted to create override configuration files for your server
  pack"; "Do not reupload this mod to the Steam Workshop or any other platform", including bundled packs.

Consequences for this project (the stricter reading is applied; this is engineering notes, not legal advice):

- Hollow Country is private, noncommercial and DayZ only. Using the Workshop copy on our own server is the
  intended use.
- No SNAFU file is bundled, copied, vendored, re-hosted or committed: no PBOs, models, textures, vendor
  XML, class dumps, keys or the terms PDF. The repository holds only class names and our own XML numbers
  (an override-style economy delta).
- The delta never ships SNAFU material, so there is no "Adapted Material" to share. Do not add SNAFU files
  to any Hollow Country package, and do not publish a Workshop collection that re-hosts them. A Workshop
  dependency listing (a link) is not a repack.
- Keep the SNAFU author credited if our own pages ever name the optional dependency.
- Monetization of a server using SNAFU needs the SNAFU team's written permission; ours is not monetized.
- If the terms PDF changes, the verifier reports `terms-changed-since-review` and generation stays
  closed until the terms are re-read and the hash in the allowlist is updated on purpose.

### Allowlist (conservative seven, WW2 SMGs, modern military handful)

`snafu_allowlist.json` declares `"status": "unverified"` permanently; verification is per install and lives
in a report outside Git. Owner decision 2026-11-17: keep the conservative seven, add the WW2 submachine guns,
and add a handful of modern high-tier military arms alongside the native M4A1 and friends. The subset is
15 weapons, 6 magazines and 4 SNAFU-specific ammunition types (25 entries).

Conservative seven (unchanged):

| Class | Role | Why |
| --- | --- | --- |
| `SNAFUMarlin1895` | wood, rare | Wood-stock lever rifle; `SNAFU_Ammo_45_70mm` |
| `SNAFUSWM629` | modern, rare | S&W 629 revolver; `SNAFU_Ammo_44` |
| `SN_M870` | wood, uncommon | Pump shotgun on the vanilla 12 gauge pool |
| `SN_USP` | modern, uncommon | Service pistol, vanilla .45 ACP plus `SN_USP_Mag` |
| `SNAFU_M48` | wood, uncommon | Wood-stock bolt rifle (WW2 pack folder, conventional); vanilla .308 |
| `SNAFU_Trenchgun` | wood, rare | Wood-stock pump shotgun (WW2 pack folder); vanilla 12 gauge |
| `GCGN_M1Garand` | wood, rare | Wood-stock semi-auto; `GCGN_Ammo_3006` |

Added by the owner decision (all `Military` usage, `Tier3`/`Tier4` value only, rare, nominal 2 / min 1,
lifetime 7200, restock 1800; no civilian usage):

| Class | Role | Magazines | Ammunition |
| --- | --- | --- | --- |
| `SNAFUThompsonMk2` | WW2 SMG | `SNAFUThompsonMk2_30rdMag` | vanilla `Ammo_45ACP` |
| `SNAFUPPSh` | WW2 SMG | `SNAFUPPSh_71rdMag` | `SNAFU_Ammo_762x25` (6 / 4) |
| `SNAFUSten` | WW2 SMG | `SNAFUSten_32rdMag` | vanilla `Ammo_9x19` |
| `SNAFU_AK103A` | modern rifle | vanilla AKM magazines | vanilla `Ammo_762x39` |
| `HK416_Gun` | modern carbine | vanilla STANAG | vanilla `Ammo_556x45` |
| `SCAR_Gun` | modern rifle | vanilla STANAG | vanilla `Ammo_556x45` |
| `SNAFU_MPX_GUN` | modern SMG | `SNAFU_MPX_30rnd_Mag` | vanilla `Ammo_9x19` |
| `SNHK417_Gun` | modern battle rifle | `SNHK417_Mag` | vanilla `Ammo_308Win` |

The five new SNAFU magazines are rare 3 / 2 (lifetime 14400). Nothing futuristic is allowlisted.
`excluded` in the file records what stays out and why: futuristic and modular tactical rifles and PDWs (ACR,
AUG, TAR-21, Vector, P90, KH9), anti-materiel and heavy snipers, machine guns, the other pack automatics
(PPSKN, Uzi, M1A, M14), exotic or novelty weapons (Alligator, TP-82, Vikhr, VSS, Lynx), reskins of vanilla
weapons (SN_AKM, SN_Glock19, SNAFU_SKS, SN_M9), `SNAFU_M70` (magazine array includes `Mag_AKM_Drum_TEST`) and
the modern arms considered but not chosen (`GCGN_HK416`, `MK18_Gun`, `SNAFU_CZ805_Gun`, `SNAFUSA80`,
`SNAFU_G3A3` and `SG552_Gun` which are not in the vendor types list, `GCGN_MP7` and `SNAFU_KAC_Gun` which need
a second foreign ammunition economy, `GCGN_Vityaz`, `SNAFU_SR25_Gun`).

### Verifier and fail-closed generation

```
python3 -m tools.package.snafu_optional verify --install <SNAFU Workshop folder> \
        --out ~/.cache/hollow-country/snafu-verify-<date>/verification.json
python3 -m tools.package.snafu_optional generate --source <stock mission copy> \
        --report <verification.json> --out <new delta dir>
```

`verify` is read only and bounded (64 PBOs, header and `config.bin` members only, 8 MiB limits on the
terms file and vendor XML; symlinks refused). Per class it checks: defined in the right `Cfg*` root;
defined in exactly one PBO; `scope` resolves to 2 or more; the model exists in a PBO; the class is in the
vendor `XML_and_Clasnames/SNAFU_types.xml`; every allowlisted magazine is accepted and verified; every
listed ammunition is in `chamberableFrom` and (for SNAFU ammunition) has a defined bullet class. Install
level checks: `meta.cpp` `publishedid`, at least one PBO, terms hash. Result per class is `verified`,
`missing` (not defined) or `unverified` (defined, check failed, with reasons).

`generate` refuses unless the report is for this exact allowlist hash, has no install problems, a matching
terms hash and every class individually `verified`. It writes complete new `types.xml` entries (flags and
category set from our own template, usage/value from the allowlist) into the separate managed folder
`hollow-country-snafu/ce`. It refuses classes that stock or the vanilla roster already define.

Real-install result (2026-11-17, `~/.cache/hollow-country/snafu-verify-2026-11-17-r2/verification.json`, 11
PBOs, `publishedid` 2443122116, terms hash matches): 25 of 25 verified, 0 missing, 0 unverified. For the eight
added weapons: each is defined in one `CfgWeapons` class with `scope` 2, its model path exists in a PBO, it is
listed in the vendor `SNAFU_types.xml`, every allowlisted magazine is defined with `scope` 2 and is accepted
by the weapon, and every listed ammunition is in `chamberableFrom`. `GCGN_M1Garand` carries the note
`empty-magazine-entry-ignored` (its magazine array is `['']`). Negative controls (a class absent from the
install, a wrong ammunition, a changed terms hash) turn the report `unverified` and generation refuses.
This is static: it shows the names, scope, models and ammo links exist in the installed files, not that a
weapon fires, loads, spawns or balances.

### Dependency, install, update and rollback

- Required on the server and every client that joins: subscribe to SNAFU Weapons (about 3.66 GB) and load
  it alongside Hollow Country. Players who skip it cannot load a server that requires it, and the items
  cannot work without it; signature behaviour with a signed server is unobserved. The base Hollow Country addon never references SNAFU and works
  without it (enforced by a test); running without SNAFU simply means not installing the delta.
- Install is offline and private: generate, then `install --delta <dir> --target <stopped private mission
  copy>`. Install requires the stock files to match the report sources, and works on top of the roster delta.
- Rollback is last in first out: `snafu_optional rollback` first, then `firearms rollback`. An out of order
  roster rollback is refused (core drift). Rollback restores the previous `cfgeconomycore.xml` byte for
  byte (tested, and on a copy of the real stock files).
- Update: when the Workshop item updates, re-run `verify` on the server copy; if any class is not `verified`
  do not regenerate. Remove the delta (`rollback`) if a class disappears, then re-curate the allowlist.

## 4. Pending, honestly

- No native/local acceptance for any roster or SNAFU entry: normal PBO/server load, CE spawn and error
  trials, firing and ammo acceptance per weapon, 3-6 player counts.
- Every datamined row (`acceptance: pending-local`) needs local acceptance before any production use, or the
  owner switches them off with `--no-datamined`. The nine variants missing from stock types are not enabled.
- Optics are undecided; only the empty extension point exists.
- The 2x counts are a deliberate owner choice for now; the effective spawn totals are unobserved.
- The roster nominals are proposals; effective CE merging and world totals are unobserved.
- The SNAFU class list rests on one version (1.28.1); the verifier must be re-run on the real server copy.
- Signed packaging of the roster/SNAFU deltas and signature handling for a signed server are pending.
- The census can see no event-only classes from files; event/carrier activity at runtime is unobserved.
- Offline checks never establish DayZ behaviour; no two-client behaviour was exercised.
