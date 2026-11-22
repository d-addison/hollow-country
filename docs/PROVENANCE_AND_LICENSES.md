# Provenance and license inventory

Hollow Country's source is publicly viewable and all rights reserved. Original authored code belongs
to David Addison; no open reuse rights or ownership of Bohemia assets are granted.
The root [LICENSE.md](../LICENSE.md) records the notice. The owner made the source
repository public on 2026-11-17. Workshop publication and third-party bundling
remain separate decisions; repository visibility does not establish gameplay
or release acceptance.

This inventory records repository categories, not an assertion that every byte
has undergone an independent authorship or legal review. A hygiene pass cannot
approve third-party redistribution or satisfy DayZ runtime acceptance.

Historical commits, issue discussions, workflow logs and downloadable artifacts
are a separate review scope tracked in
[public-readiness issue #57](https://github.com/d-addison/hollow-country/issues/57).
Excluding local material from the current tree does not remove earlier versions.
CI continues to build and verify development containers. Its private-handoff
artifact upload is disabled for public repositories; this does not remove
previously uploaded artifacts or approve a public distribution package.

| Material | Location / origin | Treatment and remaining review |
| --- | --- | --- |
| Original project implementation | `mods/HollowCountry/`, `tools/`, authored mission deltas and configuration | David Addison's original material is all rights reserved. Source/API references do not transfer ownership of the underlying game. Review any subsequently copied third-party code separately. |
| Operator and developer documentation | `docs/` and repository guides | Original project documentation; source citations do not transfer ownership of third-party material. Internal specs, research and raw results remain local. |
| Synthetic test inputs and results | `tests/fixtures/`, behavioral tests | Explicitly synthetic fixtures; no game assets or real credentials may be embedded even as tests. Whole vanilla economy filenames are permitted only in the `tests/fixtures/ce/synthetic_*` scope. |
| Authored assets addon | `mods/HollowCountryAssets/` (`NOTICE.txt` ships inside the PBO) | Only original Hollow Country meshes, textures and clips are included; no vanilla files are copied. Config inheritance from DayZ classes and any derived data are subject to the DayZ EULA and the Bohemia ADPL-SA terms where they apply (owner decision 2026-11-22). Each member needs an admitted provenance verdict before the packer includes it. |
| Official documentation and public CE references | [Source register](https://github.com/d-addison/hollow-country/blob/main/docs/SOURCES.md) | References only are not dependency or redistribution approvals. The source register records the official CE repository's ADPL-SA notice; its terms apply to expressly covered upstream material, not automatically to the whole project. Rights/attribution review of any copied or derived material remains pending. |
| Installed game, official tools, extracted scripts and runtime state | External local installations and private caches | Not repository deliverables. Installed API inspection and hashes do not grant redistribution rights. No purchased assets, vanilla dumps, Workshop packages, private keys, credentials or local profiles belong in Git. |
| Optional community mods and examples | Leads listed in the source register above | No dependency approval or permission to bundle Northmen or other Workshop material. Obtain and record explicit applicable terms before incorporating any material. |
| SNAFU Weapons (Steam Workshop 2443122116, v1.28.1) | Optional server dependency, never bundled | DPL-ND terms (terms PDF sha256 2bb0e30c7b17c487e67151a0a7cf9fc094062b861ecb9e79ff277bfe86696daf). Nothing is copied, vendored or re-hosted. The repo holds only class names and our own economy numbers (`tools/package/snafu_allowlist.json`: 15 weapons, 6 magazines, 4 ammo). Use on a private noncommercial server; no repack or reupload; credit the SNAFU author when the dependency is named; monetisation needs the SNAFU team's written permission. Rights review: pending human review. Detail: `docs/FIREARMS.md` section 3. |
| Python execution | Python standard library and Git executable for repository discovery | No vendored Python dependency is introduced by the hygiene validator. GitHub workflow actions and installed official tools are separate execution dependencies; their presence is not project ownership. |
| NVIDIA FLIP port (LDR-FLIP) | `tools/validate/flip_diff.py`, a numpy port of [NVlabs/flip](https://github.com/NVlabs/flip) `src/cpp/FLIP.h` | BSD-3-Clause; the NVIDIA copyright notice, conditions and disclaimer are retained in the file header (SPDX BSD-3-Clause). Developer tooling only: never packed into a PBO or the friend bundle. Uses an installed numpy (not vendored). Numeric parity with the reference is not yet cross-checked; the 0.05 mean-FLIP budget is provisional. |

Before incorporating a dependency or publishing a package, record its exact
version, source, applicable license, redistribution permissions, required notices
and included assets. Resolve unclear rights before bundling. No legal or runtime
acceptance is inferred from this inventory.

Run `python3 -B -m tools.validate.hygiene` in the checkout to produce a bounded
working-tree inventory with SHA-256 and byte counts. The tool scans tracked files
and unignored candidates, including force-added ignored files. It checks required
governance documents, the rights notice, restricted paths and known binary
formats, precise private-key/GitHub credential formats, and local Markdown file
links. Findings contain rule codes, sanitized paths and line numbers only.

Ignored local state, Git history, generic passwords, arbitrary credential formats,
remote URLs, heading fragments and complex Markdown need separate review. A hash
binds scanned bytes; it does not certify authorship, asset rights or an external
file's provenance. Keep the checkout immutable during validation, particularly on
hosts without POSIX descriptor-relative no-follow reads.

## Optional V2 dependencies (EXP-D1, 2026-11-17, DayZ 1.30.164289)

Hollow Country never repacks, modifies or redistributes these. Operators subscribe to them on
the Workshop, and our overlays are generated from the operator's own installed copy at install
time. Our addons never ship their files.

| Dependency | Workshop id | Author | Installed metadata | Terms as recorded | Use in Hollow Country |
| :--- | :--- | :--- | :--- | :--- | :--- |
| DayZ Expansion AI | (pinned in the AI addon README) | DayZ Expansion team | 1.9.84, matching the pinned source commit `d84d3c7` | CC BY-NC-ND: no repack, no modification, no copying of sources | Optional AI addon only calls APIs it cites; GO |
| Ambient Animals Pack | 3114410963 | Hunterz | `meta.cpp` name "Ambient Animals Pack"; ships `AmbientAnimalsPack.pbo` and per-species pbos, signed by its author, with its own territory files | "no repacks"; needs territory and event edits by the operator | Default subscribed dependency; overlay generated from the installed copy when loaded; runtime acceptance pending |
| Community Online Tools (COT) | 1564026768 | Upstream COT authors | Installed item and `scripts.pbo` permission paths inspected locally | Original subscription only; no repack, copying or modification | Default after CF; private profile roles; see [COT permissions](COT_PERMISSIONS.md) |
| Expansion Navigation | 2792984722 | DayZ Expansion team | `meta.cpp` name "DayZ-Expansion-Navigation"; public `ExpansionGPS` in installed GPS config | Original subscription only; no repack, copying or modification | Default after Expansion AI; authored nominal-4 GPS CE policy |
| RaG_Core / RaG Immersive Vehicles | 3556131153 / 3105330157 | Upstream RaG authors | Both `meta.cpp` identities; installed `types/rag_immersive_vehicles.xml` | Original subscriptions only; no repack or addon modification | Default after the weapons packs; install-time types merge, stripped from friend exports |

The terms wording was read from the Workshop pages earlier in the session. A later re-check returned
HTTP 429, so the wording should be re-read before the friend bundle lists these dependencies. The
Expansion-Animations is intentionally not loaded; Expansion-AI brings its own AI animations. Retired 2026-11-22 and no longer used: DayZ-Bicycle (2971190303) and Survivor Animations (2918418331), both by Hunterz, "no repacks"; their files were never copied or distributed. Nothing here is observed in DayZ.
