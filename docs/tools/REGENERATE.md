# Generated artefact checks

Run `python3 -B -m tools.package.regenerate_all --check` (also the default).
Preland runs this gate over the full tree, including with `--changed`.
Committed outputs are read-only: fresh generation uses temporary destinations or
in-memory bytes, and compares every declared committed output byte for byte.
There is no repair/write mode in this command. A mismatch is a finding to review
through the individual generator workflow, never an instruction to regenerate blindly.

Each generator prints one `PASS`, `FAIL` or `SKIP` line, followed by
`regenerate_all: pass|fail checked=N failed=N skipped=N`. Checked counts PASS
and FAIL; skipped inputs never count as current. Any FAIL exits nonzero.
`--require-installed` also exits nonzero for any SKIP. A permissive summary
of `pass` with skips means only the available checks passed.
Children have a 60-second timeout each (`--timeout` overrides it), and failure
diagnostics use the shared privacy filter. The existing validation CLI runs
first where available; a passing validation alone cannot establish freshness.

The `GENERATORS` table and `generated_digests.contracts()` cover admin world
catalogue, military loot, inventory sizing (both addon configs and the pack
size table), firearms, loot-point preservation, optional weapon packs, GUI
icons (PNGs, PAAs and their manifest), new buildings, economy delta, AI sites
and the animation addon config plus its generated variant policy. Tests reconcile the two inventories and discover
argparse check modes so a new checker needs an entry or a reasoned exclusion.
The admin catalogue and military-loot writers accept `--out` for disposable
regeneration; their default output and rendering remain unchanged.

Installed inputs are read-only. `--addons` defaults to the shared release
`ship_inputs.ADDONS` constant. `--source` selects a pristine stock mission;
its default is `mpmissions/dayzOffline.chernarusplus` beside Addons.
Inventory checks also need declared Workshop provider Addons directories
(`--workshop` overrides the usual root). Optional weapon packs need existing
external reports: `--snafu-report` and `--tactical-flava-report`.
Geometry regeneration needs the pinned `--reader` directory, full-client
Addons matching the recorded model evidence, and any original `--native-census`
inputs (repeatable). GUI conversion needs working Windows interop and
ImageToPAA (`--image-to-paa`). Missing installations or reports produce SKIP;
available but invalid inputs produce FAIL.

Loot preservation also uses read-only exports of revisions `335915c6` and
`fa0c2ac8`, as documented in `docs/LOOT_POINTS.md`. Their exact input hashes
enter the digest contract. Missing historical objects fail the check; fetch
the relevant history before retrying. Geometry generation can require a
larger explicit timeout than the default.

## Input-digest receipts

`config/generated-digests.json` records SHA-256 hashes of repository inputs,
the generator and its transitively imported repository source modules, the
comparison adapters, and each output. Repository JSON/XML policy data under
`config`, `mission/hollow-country` and `tools/package` are conservatively
shared inputs: changing, adding or removing a policy invalidates all receipts.
This intentionally prefers extra review over missing a composed policy input.
The receipt file itself is excluded. Files with generated and authored sections
also bind the complete current file as an input.

Installed content is never copied into this file. Stable identities record
stock input hashes, the pinned official CE URL, the inventory providers'
PBO/config-member file-list digest (including opaque EBO presence), geometry
reader/file-list hashes, addon hashes, converter hash, and verification report
hashes. Optional pack generators validate the build/file-list evidence inside
those reports when a receipt is updated. Installed locations are not recorded.

Run these commands after reviewing the generation workflow:

```sh
python3 -B -m tools.package.generated_digests --check
python3 -B -m tools.package.generated_digests --update
python3 -B -m tools.package.generated_digests --update --artefact admin_world_catalog
```

`--update` only replaces an artefact's receipt after fresh generation exactly
matches every committed output. Failed or unavailable artefacts retain their
previous receipt. Other artefacts can still update; any FAIL returns nonzero.
The same installed-input flags are available as in the aggregate. Pending
records (`verified: false`) contain current input/output hashes for inspection,
not certification, and always refuse release. A changed input with unchanged
fresh output can safely receive a new receipt; a stale output cannot.

The production boundaries are not one generator per similarly named file:

- Committed `mission/hollow-country/ce/types.xml` and its CE append file are
  authored travel/CE inputs (`travel.validate`, first introduced by `cedceebc`).
  `military_loot.regenerate` patches the committed types in place, preserving
  other authored rows; `7aa4c46b` refreshed those fields and `837c6e8d` later
  removed the Makarov rows. The checker reproduces this patch in a temporary
  destination and compares the final bytes. No later economy writer owns it.
- `economy.generate` selects the shipped `contextual-pilot` profile, roster and
  default item policy to build a separate install-time delta. The launcher
  (`local_test_session.economy_delta`) and `economy` installation/composition
  consume that delta alongside the authored CE, rather than replacing it.
  Comparing it to the authored travel types or append file is invalid. Its full
  external delta inventory comes from `economy.DELTA_FILES`.
- `ai_patrols sites` created the original seed. Subsequent authored route,
  tuning and HC43 edits are retained inputs. Since `175a4e12`, the final writer
  is `tools.audit.gapcov_regions --write`: it preserves legacy rows and rebuilds
  `gapcov-` rows plus regional metadata. The adapter copies repository mission
  inputs into a temporary tree and runs that final stage, comparing only its
  final sites bytes; localities/story companion writes also stay temporary.

Firearms and both optional weapon packs also generate install-time deltas
outside Git, rather than committed files in this tree. Their declared delta inventories and freshly
generated hashes are recorded under `external_outputs`; these entries do not
claim that a delta was committed, installed, or packaged. A successful aggregate
check for these generators means generation validation, not a committed-output
comparison. If these deltas become committed, extend the adapter with their
actual repository destinations before packaging them.

The release builder invokes the pinned commit's digest checker, with
`--require-installed`, before modifying its disposable worktree or packaging.
It prints the refusing artefact names. Missing receipts, pending receipts,
changed inputs/sources/outputs and unavailable installed inputs all refuse release.
No boot or native tools run as part of this check.

Local test builds may pass `friendcycle --local-test-waivers`. Then an artefact
whose installed inputs are absent on this host (a checker SKIP, e.g. no pinned
geometry reader) is printed as `WAIVER generated_digests <name>` and recorded under
`generated_digests.waived_unavailable` in BUILD_MANIFEST.json instead of refusing.
Missing or pending receipts, changed inputs and stale outputs still refuse. A
waiver is a listed gap, never a pass: `release_gate` refuses any bundle whose
manifest is not `generated_digests.strict: true` with no waivers.

For release inputs whose locations are not release-builder options, set
`HC_GENERATED_SOURCE`, `HC_GENERATED_READER`, `HC_GENERATED_SNAFU_REPORT`,
`HC_GENERATED_TACTICAL_FLAVA_REPORT`, and `HC_GENERATED_IMAGE_TO_PAA` as needed.
`HC_GENERATED_NATIVE_CENSUS` accepts a JSON array of census paths.
The digest CLI accepts the same environment defaults; explicit flags override
them. These paths stay local and must never be put into the receipt file.
Run the strict digest CLI with the exact intended installed inputs before a
release. Offline freshness does not establish DayZ runtime behaviour.

## Geometry validation versus regeneration

The original `loot_point_preserve --check` compares historical point-loss
receipts, and `new_buildings check` dry-runs the shipped layer against stock
mission XML. Neither loads an ODOL reader. These existing checks still run
first. A subsequent SKIP saying `existing validation passed; byte regeneration:
pinned geometry reader unavailable` means that validation passed but fresh
geometry generation could not run: the new stage needs `--reader` or
`HC_GENERATED_READER` in addition to the old checks' inputs. Installed Addons
alone do not configure a reader. This is not evidence that an installed reader
failed, nor a byte-freshness pass. Strict installed-input verification still
refuses it. Configure the pinned reader explicitly on the lead host to run the
additional stage; original native censuses must also be supplied if used.

Byte mismatches report entry additions/removals/changes and example names;
JSON also reports changed metadata paths. Zero changed entries can still fail
for stale metadata or serialization. Never update outputs or receipts solely
to silence these findings.
