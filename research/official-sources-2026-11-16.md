# Official DayZ CE source research — 2026-11-16

Status: **documentation only; not runtime evidence**. Research began at
2026-11-16T19:06:31Z; final source hash reads completed at
2026-11-16T19:09:52.547124+00:00. All timestamps below are UTC.

Scope: this report only. Read `docs/SPECIFICATION.md` and
`docs/specs/001-survival-overhaul/spec.md` before work. The active specification
confirms ChernarusPlus, local development/server testing and 3–6 players.
No game assets, full mission dump, downloaded XML, private profiles or upstream
source files were saved in the repository. Selected official blobs were decoded
and parsed in memory; this report retains summaries, identifiers and hashes.

## 1. Version and immutable source identity

The [official stable patch notes](https://dayz.com/article/game-update/dayz-badlands-out-now/dayz-steam-patch-notes)
identify **Steam Stable 1.30 Update 3, 1.30.164289, released 2026-11-03**.
The initial 1.30 section is Update 1, 1.30.164078, dated 2026-10-15.
Its modding notes introduce `disableSimulation` for house-based entities to reduce
unnecessary ticking. This establishes a documented config candidate, not its
syntax, suitability for our props, collision effects or measured savings.

The same page's Update 2 section (2026-10-21) lists absent footsteps on walls/small
props and absent audio for the head-washing and clothes-wetting actions. These
are historical known-issue entries on the cumulative page; they do not prove
those defects persist in Update 3 or affect our particular infected scenario.
Audio acceptance still needs observations with two clients.

[Official repository](https://github.com/BohemiaInteractive/DayZ-Central-Economy)
API observations:

- Default branch: `master`; the branches endpoint returned only `master`.
  **No branch named `1.30` was listed.**
- Release tag: [DZ_130](https://github.com/BohemiaInteractive/DayZ-Central-Economy/tree/DZ_130).
- Both resolve to commit
  [f220b2918b1d79a5055b1ee9be70c0ec1516e876](https://github.com/BohemiaInteractive/DayZ-Central-Economy/commit/f220b2918b1d79a5055b1ee9be70c0ec1516e876).
- Commit author/committer timestamp: `2026-10-16T12:33:11Z`;
  message concerns updated CE tool files.
- Commit tree: `6c6f45cb9fda77fd665a9184b6f237586fc0b886`;
  recursive tree response: `truncated=false`.
- Repository `pushed_at`: `2026-10-19T13:26:41Z`. This is repository metadata,
  not the commit timestamp or the game release date.

**Limit:** DZ_130 establishes the upstream 1.30 source association. This October
commit is not proof that its mission data matches every file shipped in November's
1.30.164289 server. Compare locally installed files/build manifests before using
it as a runtime baseline. Future references should use the commit, since branches
and tags can move.

## 2. License claim verified in source

The [pinned README](https://github.com/BohemiaInteractive/DayZ-Central-Economy/blob/f220b2918b1d79a5055b1ee9be70c0ec1516e876/README.md)
explicitly declares **Arma and Dayz Public License Share Alike (ADPL-SA)**.
It describes attribution, noncommercial use, restriction to Arma/DayZ and
share-alike conditions, and links the full license. Bohemia's
[official license text](https://www.bohemia.net/en/licenses/arma-and-dayz-public-license-share-alike-adpl-sa)
is available separately.

GitHub's repository API returned `license: null`, but that does **not** mean the
README contains no license. No separate LICENSE/COPYING-named entry appeared in
the complete recursive tree. The verified claim concerns the published repository
material; do not extend it to purchased game data, unrelated mods or proprietary
assets. No publication or upstream-source import is performed by this research.

## 3. Chernarus files, flags and aliases

All links in this section pin the same commit, under the exact case-sensitive
mission directory `dayzOffline.chernarusplus/`.

| Source | Observed role/content |
| --- | --- |
| [cfgeconomycore.xml](https://github.com/BohemiaInteractive/DayZ-Central-Economy/blob/f220b2918b1d79a5055b1ee9be70c0ec1516e876/dayzOffline.chernarusplus/cfgeconomycore.xml) | Root `economycore`; 10 root classes and 18 defaults. No `ce` extension declaration in this vanilla file. |
| [mapgroupproto.xml](https://github.com/BohemiaInteractive/DayZ-Central-Economy/blob/f220b2918b1d79a5055b1ee9be70c0ec1516e876/dayzOffline.chernarusplus/mapgroupproto.xml) | Root `prototype`; 436 groups, 831 containers, 11,074 raw `point` elements, 264 `proxy` elements. |
| [mapgrouppos.xml](https://github.com/BohemiaInteractive/DayZ-Central-Economy/blob/f220b2918b1d79a5055b1ee9be70c0ec1516e876/dayzOffline.chernarusplus/mapgrouppos.xml) | Root `map`; 11,679 group placements, 269 distinct names; group attributes include `name`, `pos`, `rpy`, `a`. |
| [db/types.xml](https://github.com/BohemiaInteractive/DayZ-Central-Economy/blob/f220b2918b1d79a5055b1ee9be70c0ec1516e876/dayzOffline.chernarusplus/db/types.xml) | 2,382 type entries. Fields include nominal/min/restock/lifetime, quantity bounds, cost, flags, category, tag, usage and value. |
| [cfglimitsdefinition.xml](https://github.com/BohemiaInteractive/DayZ-Central-Economy/blob/f220b2918b1d79a5055b1ee9be70c0ec1516e876/dayzOffline.chernarusplus/cfglimitsdefinition.xml) | 8 categories, 3 tags, 17 usage flags and 5 value flags. |
| [cfglimitsdefinitionuser.xml](https://github.com/BohemiaInteractive/DayZ-Central-Economy/blob/f220b2918b1d79a5055b1ee9be70c0ec1516e876/dayzOffline.chernarusplus/cfglimitsdefinitionuser.xml) | User-defined combinations of existing usage/value names; distinct from building-class aliases. |

`types.xml` flag attributes observed are `count_in_cargo`, `count_in_hoarder`,
`count_in_map`, `count_in_player`, `crafted`, and `deloot`; each has both 0
and 1 somewhere in this file. Presence is source evidence, not a test of counting,
storage ownership or dynamic-event behavior.

The limits definition includes tags `floor`, `shelves`, `ground`; usage names
include `Military`, `Town`, `Village`, `Office`, `School`, `Medic`;
values are `Tier1`–`Tier4` and `Unique`.
The user definitions contain:

| User-defined name | Referenced names |
| --- | --- |
| TownVillage | Town, Village |
| TownVillageOfficeSchool | Town, Village, Office, School |
| Tier12 / Tier23 / Tier34 | Tier1, Tier2 / Tier2, Tier3 / Tier3, Tier4 |
| Tier123 / Tier234 / Tier1234 | Tier1–3 / Tier2–4 / Tier1–4 |

Do not treat these names as additional standalone tiers or infer building
inheritance from them. No element with “alias” in its tag was found in the parsed
prototype/placement XML. The observed prototype proxies refer to item types and
transforms; their presence alone does not establish a building alias mechanism.
Native classname/inheritance resolution remains unverified.

The tree also lists `areaflags.map` (83,886,104 bytes, blob
`6f180c0c7d812c12f8948401dddeeb34f6c044d1`), which was **not downloaded**.
Bohemia's [custom-terrain CE documentation](https://community.bistudio.com/wiki/DayZ:Central_Economy_setup_for_custom_terrains)
describes spatial usage/value flags, default CE files and mission-path replacement.
Search-indexed official text was available; its older diagnostic instructions
should not be treated as current runtime observations. XML alone does not complete
an area-flag or effective loot-eligibility audit.

## 4. Building names are source candidates only

Counts below are direct XML counts: points are descendant `point` elements per
prototype; placements count exact matching group names. Containers are CE
definitions, not proof of physical searchable furniture. **No row identifies the
actual white barracks described by the user.**

| Candidate group name | lootmax attribute | Containers | Raw points | Placements |
| --- | ---: | ---: | ---: | ---: |
| Land_Tenement_Small | 0 | 3 | 0 | 132 |
| Land_Tenement_Big | 0 | 3 | 0 | 38 |
| Land_Mil_Barracks1 | 10 | 3 | 67 | 6 |
| Land_Mil_Barracks2 | 10 | 3 | 52 | 19 |
| Land_Mil_Barracks3 | 10 | 3 | 68 | 13 |
| Land_Mil_Barracks4 | 8 | 3 | 20 | 16 |
| Land_Mil_Barracks5 | 8 | 3 | 37 | 6 |
| Land_Mil_Barracks5_Basement | 23 | 4 | 56 | 1 |
| Land_Mil_Barracks6 | 25 | 3 | 258 | 1 |
| Land_Mil_Barracks6_Old | 25 | 3 | 258 | 2 |
| Land_Mil_Barracks_Round | 5 | 2 | 24 | 6 |
| Land_Tisy_Barracks | 25 | 3 | 131 | 2 |

Both tenement candidates have `Town` usage; the listed barracks candidates have
`Military`, and the basement additionally has `Medic`.
Zero raw tenement points is a useful source finding, not a complete diagnosis of
the installed map's effective loot. Nonzero barracks points do not prove that
points are reachable, eligible, occupied, visible, or reasonably replenished.
Next: identify the actual model/class and location in game, check transforms and
flags, then observe CE spawning against a native control.

## 5. Officially documented merge support and boundaries

Evidence: [Bohemia's CE mission-file modding page](https://community.bistudio.com/wiki/DayZ:Central_Economy_mission_files_modding).
Direct web fetch returned **HTTP 403**. The official-domain search result
returned the page's Usage and File specifics text (indexed approximately two weeks
earlier). This section is an indexed documentation summary, not a successful
live-page fetch or a verified 1.30 engine parser contract.

Additional files are declared through `ce`/`file` entries in
`cfgeconomycore.xml`; multiple folders/files are documented.

| Documented type | Target | Main limitation |
| --- | --- | --- |
| types | types.xml | Partial existing entries allowed; grouped fields such as flags require all components; usage/tag/value lists replace originals. |
| spawnabletypes | cfgspawnabletypes.xml | Partial entries allowed; redefining flags resets them; cargo/attachment definitions replace originals; default damage applies to new/redefined entries. |
| globals | globals.xml | Define every global attribute; preserve existing variable types. |
| economy | economy.xml | Define every flag for the affected element. |
| events | events.xml | Partial entries allowed; grouped fields complete; original children remain, may be changed or extended. |
| messages | messages.xml | Append only; existing messages cannot be overridden. |

The page does not document merge types for `mapgroupproto`, `mapgrouppos`,
`cfglimitsdefinition(user)`, `cfgeventspawns`, `cfggameplay`, or
`randompresets`. Treat those as **unsupported by this documented merge list**,
not proven impossible in every engine version. In particular, a “randompresets
since 1.28” claim was not verified in primary evidence here.

Do not invent `type="mapgroupproto"` or infer recursive merging for arbitrary XML.
The separate [official default-file mechanism](https://community.bistudio.com/wiki/DayZ:Central_Economy_setup_for_custom_terrains)
documents replacement using the correct mission-relative path/name. For files
outside the documented merge list, investigate a minimal replacement/export in an
isolated local mission; preserve the native control and test actual load behavior.
This report makes no mission edits, invokes no speculative APIs and changes no
persistence.

## 6. Source hash ledger

These are decoded upstream file bytes, not HTTP HTML or base64 text.
Git blob SHA-1 includes Git's NUL-terminated `blob <length>` header; SHA-256 covers file bytes
alone. Independently computed blob IDs matched the API/tree IDs.

| File (mission-relative except README) | Bytes | Git blob SHA-1 | SHA-256 | Verified at 2026-11-16 UTC |
| --- | ---: | --- | --- | --- |
| README.md (repository root) | 1546 | a89c0cfdfd78ffe0a309ac851b525f24d57a67e7 | c290782cb31459ea5c3659253c1f4c8a6dfe422e708f4f7a5db5afcee7a827a4 | 19:09:49.311011 |
| cfgeconomycore.xml | 2082 | a514ffb36634b6fb4d2b35dae04a0d644d310b65 | b5a88d6d5a79e8c1e272d63a608eb02107d444169aa993348430dd6c9f4dd503 | 19:09:49.677670 |
| mapgroupproto.xml | 1229651 | 248c2f410d47b5abf888a01fbf792058f6051952 | 44e70165da1b13de1ab2451aea43413955a7e81acd2d7016ba957787632585a6 | 19:09:50.275110 |
| mapgrouppos.xml | 1538112 | 1fed6da045c48299154765c1c68a39fee5016654 | 3eeaad9786a73c339f61f6e6ad203f0732e36b88f27333978cc8b4beece9cec4 | 19:09:51.274003 |
| db/types.xml | 1057471 | 7859d014847aed5c8f95288aff3839412a510ad3 | d477597418530c3e226fa18b296290eb9669210d9a37a301eaf7e3426e5e1040 | 19:09:51.847603 |
| cfglimitsdefinition.xml | 1280 | 37ee329de0d463ed20c5a6566708b2dedaf3cbbe | 07f4dedfb53e97b6150eb2374c539604b5800b8ec4c4ae243e26419aa77d4d26 | 19:09:52.197496 |
| cfglimitsdefinitionuser.xml | 1360 | f95065bc434335020868e46a7eba468ffcc7ea5b | 09a7c7d1b355c1bae72dda75d13db5d718af3508ce9797ec0c55b6cb41a9d9f8 | 19:09:52.547124 |

## 7. Commands, method and blockers

Exact metadata commands used, from `/code/dayzsa_mods`:

```sh
gh api repos/BohemiaInteractive/DayZ-Central-Economy --jq '{full_name,default_branch,pushed_at,license,html_url}'
gh api 'repos/BohemiaInteractive/DayZ-Central-Economy/branches?per_page=100' --jq '.[] | {name,sha:.commit.sha}'
gh api 'repos/BohemiaInteractive/DayZ-Central-Economy/tags?per_page=100' --jq '.[] | {name,sha:.commit.sha}'
gh api repos/BohemiaInteractive/DayZ-Central-Economy/commits/f220b2918b1d79a5055b1ee9be70c0ec1516e876 --jq '{sha,commit:{author:.commit.author,committer:.commit.committer,message:.commit.message,tree:.commit.tree},html_url}'
gh api 'repos/BohemiaInteractive/DayZ-Central-Economy/git/trees/f220b2918b1d79a5055b1ee9be70c0ec1516e876?recursive=1' --jq '{sha,truncated,entries:[.tree[] | select((.path|startswith("dayzOffline.chernarusplus/")) or (.path|test("(?i)license|copying|readme|economycore"))) | {path,type,sha,size}]}'
```

Exact final hash command (successful; does not write source files):

```sh
set -o pipefail
for blob in a89c0cfdfd78ffe0a309ac851b525f24d57a67e7 a514ffb36634b6fb4d2b35dae04a0d644d310b65 248c2f410d47b5abf888a01fbf792058f6051952 1fed6da045c48299154765c1c68a39fee5016654 7859d014847aed5c8f95288aff3839412a510ad3 37ee329de0d463ed20c5a6566708b2dedaf3cbbe f95065bc434335020868e46a7eba468ffcc7ea5b
do
  gh api "repos/BohemiaInteractive/DayZ-Central-Economy/git/blobs/$blob" --jq .content | python3 -c 'import base64,datetime,hashlib,sys; d=base64.b64decode(sys.stdin.read()); print(datetime.datetime.now(datetime.timezone.utc).isoformat(),len(d),hashlib.sha1(b"blob "+str(len(d)).encode()+b"\0"+d).hexdigest(),hashlib.sha256(d).hexdigest())' || exit
done
```

Content inspection used the same blob endpoints and in-memory standard-library
`base64.b64decode` → `xml.etree.ElementTree.fromstring`. Counts used
`root.findall("group")`, per-group `findall("container")` and
`findall(".//point")`; placement names were tallied with
`collections.Counter`. Source parse timestamps were
2026-11-16T19:08:10Z–19:08:42Z; proxy/alias follow-up completed before
2026-11-16T19:09:22Z. No offline count is called a native spawn observation.

Blockers and limits:

- Sandboxed GitHub reads intermittently returned “error connecting to
  api.github.com”. A piped README read initially returned shell status 0 despite
  that upstream failure; it was not counted as success. Retried using escalated
  `gh api` and used `set -o pipefail` for final pipelines.
- Wiki 403 was confirmed once in this task after the user's prior observation;
  no repeated direct/wiki-skin/API fetch attempts followed. Official search-index
  text was usable, but no wiki revision ID, current-page byte hash or live
  completeness claim is available.
- Patch notes and full-license HTML were read with web tools; no raw-response
  hashes were computed. Do not confuse their fetch date with an immutable pin.
- No installed-file comparison, DayZDiag, normal PBO/server run, building-model
  identification, two-client audio test or 3–6-player benchmark was performed.
  Their acceptance gates remain pending.

## 8. Traceability and verification

This bounded research follows the existing Banso specification; it creates no
separate lifecycle files or worker changes outside its assigned report.

| Research task | Requirement/acceptance link | Outcome |
| --- | --- | --- |
| Pin official CE revision and provenance | FR-003; LOOT native-first audit | Documented, hashes verified |
| Document merge inputs, flags and unknowns | FR-003 / AC-003 | Source findings recorded; no effective engine merge claim |
| Identify possible apartment/barracks source groups | FR-004; LOOT-03 / AC-004; CE-003/004 | Candidates only; in-game identification and spawn trials pending |
| Preserve distinction between sources and runtime | FR-011 / AC-010; NFR-006 | Documentation only; no capability promoted |
| License/import restraint | GOV-01; NFR-005 | README claim verified; no source import or publication |

A standard-library in-memory unittest was written and executed before creating
this file. Its first assertion required the requested report to exist; actual
red result at approximately 2026-11-16T19:09:22Z: exit 1,
`AssertionError: False is not true : requested official-source report is missing`,
`Ran 1 test`, `FAILED (failures=1)`.
The same report-contract check is reproduced below; its green rerun is recorded
after creation. It checks evidence coverage, not DayZ behavior.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
import unittest
class OfficialSourceReport(unittest.TestCase):
    def test_research_contract(self):
        p=Path('research/official-sources-2026-11-16.md')
        self.assertTrue(p.is_file(), 'requested official-source report is missing')
        text=p.read_text()
        for evidence in ('f220b2918b1d79a5055b1ee9be70c0ec1516e876','DZ_130','1.30.164289','ADPL-SA','mapgroupproto.xml','mapgrouppos.xml','cfgeconomycore.xml','cfglimitsdefinitionuser.xml','count_in_hoarder','403','documentation only','not runtime','white barracks','SHA-256','2026-11-16T','FR-003','FR-004'):
            with self.subTest(evidence=evidence): self.assertIn(evidence,text)
        for source in ('https://github.com/BohemiaInteractive/DayZ-Central-Economy/blob/f220b2918b1d79a5055b1ee9be70c0ec1516e876/','https://dayz.com/article/game-update/dayz-badlands-out-now/dayz-steam-patch-notes','https://community.bistudio.com/wiki/DayZ:Central_Economy_mission_files_modding'):
            with self.subTest(source=source): self.assertIn(source,text)
unittest.main(verbosity=2)
PY
```

Existing offline regression command:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v`.
Observed before report creation: exit 0, **109 tests passed in 5.934s**.
These tests use offline inputs; they establish no DayZ runtime behavior.

Green rerun of the exact report-contract command above at
2026-11-16T19:12:37Z: exit 0, `Ran 1 test in 0.000s`, `OK`.
Only this report was authored by this research task; no gameplay acceptance
criterion is marked complete.
