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
| Official documentation and public CE references | [Source register](https://github.com/d-addison/hollow-country/blob/main/docs/SOURCES.md) | References only are not dependency or redistribution approvals. The source register records the official CE repository's ADPL-SA notice; its terms apply to expressly covered upstream material, not automatically to the whole project. Rights/attribution review of any copied or derived material remains pending. |
| Installed game, official tools, extracted scripts and runtime state | External local installations and private caches | Not repository deliverables. Installed API inspection and hashes do not grant redistribution rights. No purchased assets, vanilla dumps, Workshop packages, private keys, credentials or local profiles belong in Git. |
| Optional community mods and examples | Leads listed in the source register above | No dependency approval or permission to bundle Northmen or other Workshop material. Obtain and record explicit applicable terms before incorporating any material. |
| SNAFU Weapons (Steam Workshop 2443122116, v1.28.1) | Optional server dependency, never bundled | DPL-ND terms (terms PDF sha256 2bb0e30c7b17c487e67151a0a7cf9fc094062b861ecb9e79ff277bfe86696daf). Nothing is copied, vendored or re-hosted. The repo holds only class names and our own economy numbers (`tools/package/snafu_allowlist.json`: 15 weapons, 6 magazines, 4 ammo). Use on a private noncommercial server; no repack or reupload; credit the SNAFU author when the dependency is named; monetisation needs the SNAFU team's written permission. Rights review: pending human review. Detail: `docs/FIREARMS.md` section 3. |
| Python execution | Python standard library and Git executable for repository discovery | No vendored Python dependency is introduced by the hygiene validator. GitHub workflow actions and installed official tools are separate execution dependencies; their presence is not project ownership. |

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
