# Offline content audits (T0)

These tools inventory supplied inputs. They do not establish live gameplay
behavior or complete the mod's item and crafting audit.

## Recipe and item-utility starting inventory

```sh
python3 -B -m tools.audit.crafting_audit --root PATH_TO_SCRIPT_TREE
python3 -B -m tools.audit.crafting_audit --root PATH_TO_SCRIPT_TREE --expect-manifest-sha256 HASH
python3 -B -m unittest tests.unit.test_crafting_audit
```

The crafting census scans every nested `.c`/`.C` file, rather than only a recipe
folder or Hollow Country's initial recipes. Its deterministic JSON includes raw
file hashes, source declarations, literal registration calls, commented-out
registrations, ingredient/output references and unresolved custom behavior.
Ambiguous inheritance and unregistered descendants remain in the candidate
inventory; they are never silently treated as resolved recipes. The complete
manifest hash can pin repeat scans. Inputs are read only, with bounded file,
tree, token and nesting budgets. No game assets are bundled.

UTF-8 decoding is strict by default. `--fallback-encoding cp1252` explicitly
permits legacy comments when auditing a known source snapshot; the report pins
both raw bytes and that decoding policy. JSON goes to stdout. Exit **0** means
the bounded source scan completed, **1** means an input/audit failure, and **2**
is command-line usage failure. Check the report's coverage and unresolved fields
even after exit 0.

A source registration call is not proof that a recipe is registered in the
running server. Preprocessor branches, invocation order, inheritance effects,
effective item configurations, cooking/actions, attachment geometry, conservation
and usefulness still require separate examination and native tests. Runtime
recipe counts and merged item counts remain unknown. This census is the starting
inventory for the full-content audit, not permission to declare three recipes or
a few attachment combinations feature-complete.

## Central Economy audit

Run from the project root with Python 3.11+; only the standard library is used:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.audit.ce_audit --mission PATH [--output PATH] [--known-types PATH]
```

JSON always goes to stdout. `--output` also writes identical JSON atomically;
its parent directory must exist. Input files, including declared CE files outside
this audit's coverage, are protected against accidental output overwrites.
Exit codes: **0** no errors (warnings may remain), **1** invalid audit inputs or
findings, **2** CLI usage or output failure. Audit/output failures produce JSON;
argparse usage errors use stderr.

## Inputs and discovery

Required inputs are `db/types.xml` (or mission-root `types.xml`),
`mapgroupproto.xml`, and `mapgrouppos.xml`. Both base types candidates existing
is an explicit ambiguity error. Missing inputs, bad roots and malformed XML are
errors, with no silent substitute. An absent optional `cfgeconomycore.xml`
produces `modular_types_not_checked`.

An existing `cfgeconomycore.xml` is parsed for direct
`<ce folder="..."><file name="..." type="types"/></ce>` declarations. Both slash
conventions work. Only explicitly registered `type="types"` files enter the
types inventory; there is no recursive mission scan. Declared types files must
exist. All other declared file kinds appear as `not_audited` with warnings;
in particular, map group files are not treated as generic modular merges.

Duplicate type names, including across declared sources, are errors. This is a
conservative ambiguity finding, not proof that an intentional override is
invalid in the engine. The audit does not compute effective merged types or
assume precedence. Duplicate prototype names also fail; their placement point
counts remain unknown. Multiple placements of the same prototype are expected.

`--known-types` supplies an authoritative catalog chosen by the caller: either
UTF-8 text (one classname per line, blank lines and full-line `#` comments
allowed) or a `<types><type name="..."/>...</types>` XML file. XML catalogs
should use `.xml`. An absent catalog means `catalog_status=not_supplied`; unknown
names cannot be assessed. An explicitly supplied missing, empty or malformed
catalog fails. Unknown **item type names** in base and modular types fail against
the catalog. This catalog does not verify building/model identities, nor does
this tool extract classnames from a game installation.

## Validation and coverage interpretation

The validator checks nonnegative integer `nominal`, `min`, `lifetime`, `restock`,
`cost`, supplied prototype count attributes (including `lootmax`), repeated
numeric fields, `min > nominal`, quantity ordering, and binary CE count flags.
Quantities allow the `-1` unspecified sentinel; other negative quantities fail.
Omitted fields in partial types entries are not defaulted. Point/placement
positions, supplied rotations and angles must be finite and have the correct
component count. Supplied point ranges/heights must be finite and nonnegative.
This is a bounded structural validator, not the full native CE schema.

`coverage.groups` lists the union of prototype and placement names, with
placement counts, container counts, raw direct `container/point` counts and
placement-weighted raw counts. The raw prototype total includes unplaced groups
and, on invalid inputs, repeated prototype definitions. Weighted totals require
exact, unique prototype matches. `resolved_placed_raw_point_count` is a subtotal;
`placed_raw_point_count` is null when inputs are unavailable or placed names
cannot be resolved. Missing file totals are null rather than invented zeros.
Check `valid`, `inputs_complete`, diagnostics and unresolved placements before
using results as an inventory.

Aliases are never resolved automatically. Case, path basename, `.p3d` suffix and
`Land_` differences only suggest `alias_candidates`; unmatched placements remain
errors. Explicit alias XML constructs produce an `unresolved_alias` warning.
Zero raw points is a warning, not a declaration that a building has no loot.
Points under `lootmax="0"` are still counted as raw XML points.

**Raw points are not engine eligible loot opportunities. Model/group names are
not verified building classes.** Accessibility, tags, container limits, dispatch
behavior, effective economy state and actual loot spawning need installed-engine
proof. `engine_eligible_loot_points` stays null and `building_classes_verified`
stays false. No production game scripts or mission edits are supplied.

## Determinism, provenance and bounds

Reports have schema version 1, sorted keys/records and no timestamp, absolute
mission root, hostname or environment values. Every read source has its logical
mission-relative path, byte length and SHA-256 of exact bytes (including files
that fail XML parsing). The external catalog is labeled `@known-types` to avoid
exposing its local path. Missing/denied sources have explicit diagnostics but no
invented hash. Authored names and relative paths remain report data; review them
before sharing. Hashes establish input identity, not engine validity.

Limits are 32 MiB per file, 128 MiB total admitted bytes, 128 source files,
128 CE declarations, 500,000 total XML element nodes and depth 64. File reads
are capped, and node/depth limits are enforced while building the XML tree.
DTD/entity declarations are rejected, including UTF-16 documents. Declared
absolute paths, traversal and symlinks escaping the mission fail. There is no
network access, game launch, dependency download or unbounded recursive scan.

## Tests and synthetic example

All fixture names and coordinates are invented; no proprietary CE data is
bundled. Run the scoped suite:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_ce_audit.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.audit.ce_audit --mission tests/fixtures/ce/synthetic_valid --known-types tests/fixtures/ce/synthetic_known_types.txt
```

The synthetic example has 2 item types, 3 placements, 4 raw prototype points
and 6 placement-weighted raw points. One placed group has zero raw points, so
it reports a warning. These numbers establish parser arithmetic only.
Run the audit regression suite for current results; captured output stays local.

XML shape references inspected during implementation:
[official group prototypes](https://github.com/BohemiaInteractive/DayZ-Central-Economy/blob/master/dayzOffline.chernarusplus/mapgroupproto.xml)
and [official economy core](https://github.com/BohemiaInteractive/DayZ-Central-Economy/blob/master/dayzOffline.chernarusplus/cfgeconomycore.xml).
These moving references are not a pinned installed-engine baseline. The handoff's
[mission extension documentation](https://community.bistudio.com/wiki/DayZ:Central_Economy_mission_files_modding)
returned HTTP 403 during this task; no supported merge behavior for other file
kinds is inferred from it.
