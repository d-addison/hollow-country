# Layout and texture reference checks

Run from the repository root (Python standard library only):

```sh
python3 -B -m tools.validate.texture_index
python3 -B -m tools.validate.layout_lint
python3 -B -m unittest tests.unit.test_texture_index tests.unit.test_layout_lint
```

The index defaults to the installed client at
`/mnt/g/SteamLibrary/steamapps/common/DayZ/Addons` and writes only archive
basenames, sizes, modification times and virtual filenames to
`~/.cache/hollow-country/texture-index.json`. It reads PBO header tables, never
asset payloads, and handles compressed entries without decompressing them.
Archives without a prefix property use their filename stem; the index command
reports how many prefixes were assumed. Such mounts need native confirmation.
No Windows executable is invoked; no CLI flags for Bohemia executables are assumed.

Override installed locations or add Tools data if required:

```sh
python3 -B -m tools.validate.texture_index \
  --addons '/mnt/g/SteamLibrary/steamapps/common/DayZ/Addons' \
  --extra '/mnt/d/SteamLibrary/steamapps/common/DayZ Tools/dta'
```

`--extra` is optional and must name a directory that actually contains PBOs.
Rebuild after updating DayZ or changing indexed addons. The cache records archive
fingerprints but the lint command does **not** recheck their freshness or addon
load order. A corrupt/unreadable/missing index produces a clear notice and skips
unresolved external-file checks. Local missing files, packer exclusions, texture
extensions, procedural strings and existing layout checks still run. Use
`--no-texture-index` for an explicit offline run. `--texture-index PATH` selects
an existing alternate cache; generated installed indexes belong outside the repo.

## Coverage and severity

The linter preserves widget class, brace, name, layout-load and lookup checks,
including the data-driven borrowed-root declarations. It scans all
`mods/*/gui/**/*.layout`, GUI `.imageset` files, script `.c` files and
`config.cpp` texture fields. Texture names compare case-insensitively with slash
normalization, including Enforce's doubled backslashes. Authored files are mapped
using `tools.package.pbo.addon_prefix` and checked using its
`original_addon_name` shipping policy. A local asset's mere presence does not
mean the packer includes it.

It checks literal arguments to `LoadImageFile`, `SetImage`, `LoadMaskTexture`,
`SetTexture` and direct `ImageWidget` calls; numeric `SetImage` frame indexes are
ignored. Script texture-like literals in constants/arrays are also checked, so
paths passed through helpers such as `Pin` are covered. Imageset `File`, `Path`
and texture fields and scalar/array config texture fields are included. This is
a lexical check, not an Enforce or config preprocessor: generated paths, macros,
conditional builds and config inheritance need native review. Texture-looking
strings used for unrelated purposes can require manual review.

Missing indexed files, missing authored files, packer exclusions, unexpected
extensions (the checked runtime file formats are `.paa` and `.edds`) and malformed
color procedures are errors (exit 1). Dynamic texture arguments, `MapMarkerTypes`
lookups, procedural templates and symbolic `set:… image:…` references generate
warnings (exit 0 if there are no errors). Other runtime tables used as texture
arguments also warn; the tool does not evaluate their contents or track values
through functions. Symbolic sprite names and installed imageset contents are
not verified by a filename-only index. Warnings do not establish acceptance.

## Procedural grammar evidence

Locally inspected native 1.30.164289 scripts contain:

- `4_World/Entities/ExplosivesBase/RemoteDetonator.c`: five-argument
  `#(argb,8,8,3)color(0,0,0,1.0,co)`.
- `4_World/Entities/ItemBase.c`: uppercase `CO` in the documented generated color.
- `4_World/Classes/Hologram.c`: the same generator with `ca`.

The checker accepts those observed forms with four numeric channels and an
explicit `co`/`ca` suffix. Bohemia's general
[procedural texture documentation](https://community.bistudio.com/wiki/Procedural_Textures)
describes additional formats and an optional texture-type argument. It also
requires power-of-two dimensions, no whitespace and leading digits on fractional
numbers. Accordingly, syntactically valid documented color variants (including
four-argument colors) warn as needing DayZ confirmation; they are not declared
malformed solely because the suffix is absent. Other generators warn as
unverified. The parser rejects missing channels, broken delimiters, whitespace,
`.5` fractions and non-power-of-two dimensions. This is an evidenced grammar
subset, not an engine parser or a claim that all documented Arma variants work
in DayZ. No rendering experiment was run in this worker.

## Observed validation and remaining lead checks

On this worker's installed client, header scanning succeeded for 118 PBOs,
94,211 virtual filenames, and zero assumed prefixes. An in-memory lint against
that set found no missing authored or indexed texture references. Runtime-table
and variable-fed loads still require review. Existing layout/lookup checks also
passed at that point; the admin branch may change concurrently. No `mods/`
files or borrowed-root allowlists were changed.

Writing the default cache failed with filesystem errno 30 (read-only cache
mount). The focused tests use temporary synthetic PBOs and do not require that
mount. The lead should run the first two commands above in a writable session
to prove the normal persistent-cache workflow. No game process was started.

Then the lead must use the normal native compile/boot workflow and one server
plus at most one client, open the group map and admin overlay, exercise every
marker type and dynamic texture source, and inspect the resulting RPT for
texture errors, compile errors, crashes or stalls. Static filename success
cannot prove PAA/EDDS decoding, imageset sprite resolution, procedural rendering,
loaded-addon precedence or absence of a client texture-error flood. Multiplayer
and target-load performance remain unproven. This tooling change contains no
Enforce edits and does not require the Enforce lint/compile gates itself.

## Optional Workbench check (proposal only)

A future headless Workbench plugin could load each authored layout/imageset in
the actual project, capture resource-load errors and write a bounded report. Use
`tools/anim/workbench/HC_TxaBuild.c` as the existing integration pattern. First
observe Workbench's supported invocation and resource-load APIs; do not assume
that opening a layout exercises all images, procedural strings or runtime tables.
No plugin, command-line recipe or native acceptance is implemented by this round.
