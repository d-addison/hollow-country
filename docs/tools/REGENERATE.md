# Generated artefact checks

Run `python3 -B -m tools.package.regenerate_all --check` (also the default).
Preland runs this gate over the full tree, including with `--changed`.
The command never regenerates outputs; there is no `--write` mode.

Each generator prints one `PASS`, `FAIL` or `SKIP` line, followed by
`regenerate_all: pass|fail checked=N failed=N skipped=N`. Checked counts PASS
and FAIL; skipped inputs never count as current. Any FAIL exits nonzero.
`--require-installed` also exits nonzero for any SKIP. A permissive summary
of `pass` with skips means only the available checks passed.
Children have a 60-second timeout each (`--timeout` overrides it), and failure
diagnostics use the shared privacy filter.

The table in `tools/package/regenerate_all.py` covers admin world catalogue,
military loot, inventory sizes, firearms, loot-point preservation, both optional
weapon packs, GUI icons and new buildings. Its unit test discovers argparse
check modes, requiring an entry or a reasoned exclusion for each module.

Installed inputs are read-only. `--addons` defaults to the shared release
`ship_inputs.ADDONS` constant. `--source` selects a pristine stock mission;
its default is `mpmissions/dayzOffline.chernarusplus` beside Addons.
Inventory checks also need declared Workshop provider Addons directories
(`--workshop` overrides the generator's usual Workshop root).
Optional weapon-pack generation needs existing external verification reports:
`--snafu-report` and `--tactical-flava-report`. Missing installed inputs or
unsupplied reports produce SKIP. Invalid available inputs produce FAIL.

Loot preservation checks the committed `additions-interiors.json` against
read-only exports of revisions `335915c6` and `fa0c2ac8`, as documented in
`docs/LOOT_POINTS.md`. Only temporary input files are written. Missing historical
objects fail the check; fetch the relevant history before retrying.

The runner preserves the limits of existing check modes. Firearms and optional
weapon-pack `generate --check` validate generation without comparing committed
output bytes. New buildings checks the shipped layer against stock map inputs
without regenerating geometry. PASS means that generator's existing offline
check passed; it does not establish DayZ runtime behaviour or byte-for-byte
freshness beyond what that check implements. Findings must be reviewed through
the individual generator workflow; this command never repairs them.
