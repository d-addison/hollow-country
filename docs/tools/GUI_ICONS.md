# Original Hollow Country map icons

Issue #329: stock MapMarkerTypes texture references failed on DayZ 1.30.
These ten original, procedurally authored 64×64 RGBA icons are available for a
later map integration. This change does not wire any layout or script to them.
The concurrent map rework uses ExpansionIcons.Get(name) on the Expansion M-map
and a tinted vanilla imageset circle for the base HCMark widget.

| Category / filename stem | Outer shape | Dark detail |
| --- | --- | --- |
| ai_group | triangle | dot |
| police | diamond | cross |
| event | triangle | horizontal bar |
| loot | square | cross |
| wreck | cross | dot |
| vehicle | square | horizontal bar |
| shelter | triangle | doorway |
| group_member | circle | dot |
| player | diamond | dot |
| poi | circle | cross |

Faces are white for runtime tinting, with dark outlines/details for light map
backgrounds and transparent padding. Fixed 4× coverage sampling softens edges.
The generator writes PNG directly with Python's standard library (`zlib`); it
does not require Pillow, downloads, copied game textures, or image generation
services. All image content originates in `tools/package/gui_icons.py`.

## Build and verify

Run from the repository root in WSL:

```sh
python3 -B -m tools.package.gui_icons build
python3 -B -m tools.package.gui_icons check
python3 -B -m unittest tests.unit.test_gui_icons
```

The default converter is the installed tool:
`D:\SteamLibrary\steamapps\common\DayZ Tools\Bin\ImageToPAA\ImageToPAA.exe`.
Override its filesystem path when necessary:

```sh
python3 -B -m tools.package.gui_icons build --image-to-paa '/mnt/d/SteamLibrary/steamapps/common/DayZ Tools/Bin/ImageToPAA/ImageToPAA.exe'
```

`--root <checkout>` selects another checkout. On Windows Python, supply native
Windows paths for `--root` and `--image-to-paa`. On WSL the tool uses `wslpath -w`
and the existing bounded `tools.setup.winproc` PowerShell helper. Native tool
output is captured rather than echoed, avoiding local path leakage. Only the
short-lived converter is started; no game, server or Workbench process is used.

To regenerate sources without Windows:

```sh
python3 -B -m tools.package.gui_icons render
```

`build` renders `art/gui-icons/*.png`, converts into a temporary directory,
then publishes all ten successful outputs under
`mods/HollowCountry/gui/icons/map/`. It records repo-relative paths, SHA-256
hashes for every source/output pair and the converter executable in
`art/gui-icons/manifest.json`. Failed conversion preserves the previous output
set and manifest; newly rendered sources can then fail `check` until rebuilt.
Publication of the successful set is sequential, not crash-atomic: an interrupted
write is detected by `check` and repaired by rerunning `build`.

`check` requires exactly all ten source/PAA pairs, matching hashes and PNG bytes
matching the current procedural recipe. It rejects extra PNG/PAA filenames,
missing files, symlinks and redirected manifest paths. It needs no converter or
Windows install and never regenerates outputs. Hash provenance establishes file
identity, not engine texture compatibility. If conversion is unavailable, keep
sources and rerun the build command on the lead machine; do not invent PAA bytes
or update the manifest to claim successful conversion.

The repository normally ignores `.paa`. A scoped `.gitignore` in the map icon
folder explicitly includes this original generated set. The packer excludes
that metadata file and permits binary PAA only under `gui/icons/map/`, with a
bounded size and the observed DXT5 texture header. Other binary paths stay refused.

## PBO paths and later integration

`tools/package/pbo.py` uses prefix `HollowCountry`; entries are
`gui/icons/map/<category>.paa`. Thus the engine resource path is
`HollowCountry\gui\icons\map\player.paa`. Source PNGs and the provenance manifest
live outside the addon and do not enter the PBO.

The following is a future integration example, not a change included here:

```c
ImageWidget mark = ImageWidget.Cast(root.FindAnyWidget("HCMark"));
if (mark)
{
    mark.LoadImageFile(0, "HollowCountry\\gui\\icons\\map\\player.paa");
    mark.SetImage(0);
    mark.SetColor(ARGB(255, 255, 255, 255));
}
```

The installed 1.30 scripts use `LoadImageFile(0, path)` in
`3_Game/Client/Notifications/NotificationUI.c` and
`3_Game/GUI/Hints/UiHintPanel.c`. Native widget loading of these particular
textures still requires client observation.

For the base pin, replace only HCMark's `image0` in
`mods/HollowCountry/gui/layouts/hc_group_icon.layout` with the desired resource
path (for example `HollowCountry\gui\icons\map\group_member.paa`) and preserve
layer tinting. Per-category pins can call `LoadImageFile(0, path)` after widget
creation. Do not replace solid panel styles with textures.

For the Expansion map, keep `HCXAdminMapLayers.HCXIconName(int)` as the single
category mapping owner. In a later change map each existing layer to its matching
filename from the table, and have its consumer use that resource path directly.
The current `ExpansionIcons.Get(name)` resolves registered symbolic names; do not
assume passing an arbitrary PAA path into that lookup works. Either bypass the
lookup for HC paths after inspecting the installed marker API, or register names
through an observed Expansion API. Numeric layer IDs and a registration API are
not assumed by this pipeline. Preserve existing marker state, colours and layer
visibility rules.

## Observed evidence and pending lead checks

Observed on 2026-11-21:

- Installed `ImageToPAA.exe -help` exits 1 and reports
  `pal2pace [options] <source> [<destination>]`, with `-size=<n>`.
- Actual PNG-to-PAA conversion through Windows PowerShell accepted both explicit
  source and destination paths translated by WSL, including the checkout paths.
  All ten outputs are 5,625 bytes with DXT5 header bytes `05 ff`.
- Offline provenance and focused Python tests cover altered/missing pairs,
  failed conversion, PNG alpha, and PBO round-trip byte preservation/prefix.

For the lead, at the resulting committed checkout:

```sh
python3 -B -m tools.package.gui_icons check
python3 -B -m unittest tests.unit.test_gui_icons
```

After the later layout/script integration, run the required gates:

```sh
python3 -B -m tools.validate.enforce_lint --native-scripts ~/.cache/hollow-country/native-scripts/scripts-1.30.164289
tools/release/compile_gate.sh
```

Use the lead's normal release bundle/boot workflow from that clean commit. On
one server with at most one client, open the base group map and Expansion M-map,
exercise each mapped category, zoom levels and layer tints, and inspect the
client RPT for texture loading errors. Confirm the expected PBO contains all ten
entries before that boot. Exact game launch arguments depend on the lead's
chosen profile and mod list; no new launch command is assumed here.

Pending: engine PAA decoding, alpha/contrast at actual marker sizes, actual
widget and Expansion marker integration, absence of texture errors in a native
client RPT, and release boot/readiness. No engine experiment or multiplayer
behaviour is accepted by the offline checks. These icons only guarantee that
matching authored files can be included at the documented PBO paths.

Handoff note: the root `.gitignore` currently excludes `docs/tools/`. The lead
must allow this requested documentation path before Banso collects changes;
this worker owns neither the root ignore file nor git metadata.
