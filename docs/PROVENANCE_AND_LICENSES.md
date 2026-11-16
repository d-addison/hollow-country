# Provenance and license inventory

On 2026-11-16 the user instructed: keep Hollow Country private, all rights
reserved; original authored code belongs to David Addison; grant no open reuse
rights and claim no ownership of Bohemia assets. The root [LICENSE.md](../LICENSE.md)
records this decision. Existing explicit private development and transfer
permissions remain in force. Public and Workshop publication are not authorized.

This inventory records repository categories, not an assertion that every byte
has undergone an independent authorship or legal review. A hygiene pass cannot
approve third-party redistribution or satisfy DayZ runtime acceptance.

| Material | Location / origin | Treatment and remaining review |
| --- | --- | --- |
| Original project implementation | `mods/HollowCountry/`, `tools/`, authored mission deltas and configuration | David Addison's original material is all rights reserved. Source/API references do not transfer ownership of the underlying game. Review any subsequently copied third-party code separately. |
| Project specifications, runbooks and research | `docs/`, `research/`, root guides; imported design handoff plus subsequent project work | Private project materials; preserve source citations and the distinction between design input, synthetic tests and observed runtime evidence. The notice does not establish authorship of third-party quotations or snippets. |
| Synthetic test inputs and results | `tests/fixtures/`, behavioral tests | Explicitly synthetic fixtures; no game assets or real credentials may be embedded even as tests. Whole vanilla economy filenames are permitted only in the `tests/fixtures/ce/synthetic_*` scope. |
| Official documentation and public CE references | [Source register in the private repository](https://github.com/d-addison/hollow-country/blob/main/docs/SOURCES.md) | References only are not dependency or redistribution approvals. The source register records the official CE repository's ADPL-SA notice; its terms apply to expressly covered upstream material, not automatically to the whole project. Rights/attribution review of any copied or derived material remains pending. |
| Installed game, official tools, extracted scripts and runtime state | External local installations and private caches | Not repository deliverables. Installed API inspection and hashes do not grant redistribution rights. No purchased assets, vanilla dumps, Workshop packages, private keys, credentials or local profiles belong in Git. |
| Optional community mods and examples | Leads listed in the source register above | No dependency approval or permission to bundle Northmen or other Workshop material. Obtain and record explicit applicable terms before incorporating any material. |
| Python execution | Python standard library and Git executable for repository discovery | No vendored Python dependency is introduced by the hygiene validator. GitHub workflow actions and installed official tools are separate execution dependencies; their presence is not project ownership. |

The existing [licensing checklist](https://github.com/d-addison/hollow-country/blob/main/docs/DECISIONS_AND_RISKS.md#licensing-and-publication-checklist)
retains the third-party and future-publication review work. Its earlier unresolved
source-license question is superseded by the user decision above. No legal or
runtime acceptance is inferred from this inventory.

Run `python3 -B -m tools.validate.hygiene` in the checkout to produce a bounded
working-tree inventory with SHA-256 and byte counts. The tool scans tracked files
and unignored candidates, including force-added ignored files. It checks required
governance documents, the private notice, restricted paths and known binary
formats, precise private-key/GitHub credential formats, and local Markdown file
links. Findings contain rule codes, sanitized paths and line numbers only.

Ignored local state, Git history, generic passwords, arbitrary credential formats,
remote URLs, heading fragments and complex Markdown need separate review. A hash
binds scanned bytes; it does not certify authorship, asset rights or an external
file's provenance. Keep the checkout immutable during validation, particularly on
hosts without POSIX descriptor-relative no-follow reads.
