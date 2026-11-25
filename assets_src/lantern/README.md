# Tin-can lantern #349 — original source, implemented-unverified

These sources do not establish engine behaviour. Native builds, texture and mesh
checks and server/client acceptance remain required.

## Shape, dimensions and LODs

Scale source: the owner's 2026-11-25 brief (about 100 mm wide and 130 mm tall),
not a claim about a measured commercial can. ops.v1 uses Blender metres, Z up;
export rotates (x,y,z) to DayZ (x,z,-y). Can diameter 100 mm; body height 75 mm;
handle tops out at 130 mm including its 2 mm radius. Candle diameter 30 mm,
height 33 mm; flame top 52 mm. A front window exposes the flame below the rim.
The tiny 0.1 mm centre bore avoids zero-radius lathe vertices. No downloaded
meshes, pixels, vanilla asset copies or generative-model assets are included.

`lod0.ops.json`, `lod1.ops.json`, `lod2.ops.json` author progressively coarser
can, rolled rim, U wire, candle and flame meshes. `finish.json` caps them at
1500/900/580 triangles and requires a **15 mm conservative Hausdorff upper bound**.
These are budgets, not observed Blender triangle counts or passed distance gates.
No LOD is accepted until the finisher passes. Current default Hausdorff work cap
may refuse them; do not raise it or weaken the distance gate just to ship.

`geometry.ops.json`, `view.ops.json`, `fire.ops.json` describe one closed convex
body hull; collision deliberately omits the thin wire and the can cavity.
`shadow.ops.json` has a lower-detail windowed body and wire. `build.finish`
uses the equivalent canonical box primitive for Geometry with 0.18 kg mass,
then explicitly adds View Geometry, Fire Geometry and Shadow via current
`finisher.clean`/`mlod.LOD` APIs. These are offline authored shapes, not proven
collision or shadow behaviour.

`materials.json` binds the rim into `can`; model.cfg exposes `can`, `handle`,
`candle`, `flame` in that order in config.cpp. model.cfg is generated with
`tools.assets.model_cfg.emit_model_cfg('hc_tincanlantern', [...])`.

## Native evidence (scripts-1.30.164289, read before implementation)

* `4_World/Entities/ItemBase/PortableGasLamp.c:34-55`: client creation, one `light`
  point, material swap, fade. `ChemLight.c:72-73` uses the same one-point attach.
* `4_World/Entities/ScriptedLightBase.c:165-192,227-244,350`: attachment,
  client-only creation and FadeOut. `PointLightBase.c:1-5` sets the point type.
* `PointLightBase/ChemlightLight.c:3-13`: 1.5 brightness, 7.5 m radius.
  `PointLightBase/PortableGasLampLight.c:8-19`: warm colour/flicker. Our 0.7,
  3 m candle is provisional and below the chemlight, not photometric evidence.
* `ItemBase/Flashlight.c:13-59`: hiddenSelection-index on/off material pattern.
  `ItemBase/Roadflare.c:94-108,138-145,190-199,454-461`: deletion fade,
  selection visibility, client light and native actions. Our static model uses
  simpleHiddenSelections for flame visibility (EntityAI.c:2876-2878 and
  ActionViewBinoculars.c:37,58), avoiding animation-based HideSelection.
* `ItemBase/Torch.c:141-185,204-211,761-765`: IsIgnited, CanBeIgnitedBy,
  native ignition hook and ActionLightItemOnFire. `ActionLightItemOnFire.c:70-129`
  calls the hooks from fire sources. `ActionTurnOffWhileInHands.c:47-52` uses
  SwitchOff. No custom action, RPC or per-tick controller is introduced.
* `3_Game/tools/Component/ComponentEnergyManager.c:181-202`: config energy keys.
  7200 units / 1 unit per second gives a provisional two-hour burn. No refill,
  crafting or world-economy entry is added in this wave.
* `4_World/Entities/ManBase/DayZPlayer/DayZPlayerCfgBase.c:1062` registers the
  PortableGasLamp one-handed torch workspace and GasLight IK profile (:962
  provides Roadflare). Config ancestry follows PortableGasLamp; no new hand
  memory names are invented. Inherited IK matching still requires a client check.
* Read-only installed PBO evidence: `gear_cooking.pbo/config.bin`,
  CfgVehicles/PortableGasLamp inherits Inventory_Base, weight 330, size 4x3,
  GasCanister attachment, glow/zbytek/glow_on/glow_off selections; patch
  DZ_Gear_Cooking. `gear_consumables.pbo/config.bin`, Roadflare: energyAtSpawn
  1200, usage 1, interval 10, convertEnergyToQuantity 1. Derived values only,
  no vanilla config dump committed. Read with tools.audit.pbo_config._Rap.
  Our DamageSystem overrides the inherited GasLight health-level material swaps
  with empty arrays so damage never introduces vanilla gas-lamp art.
* Read-only `gear_cooking.pbo/GasLight.p3d` Memory LOD (tools.audit.odol56):
  boundingbox_min/max, invview, light, ce_center, ce_radius,
  throwingimpulseposition. Our authored points use those names; coordinates
  are ours. `light` is at the flame in every visual recipe.

Paths in the light-source bullets are under
`4_World/Entities/ScriptedLightBase/`; action paths are under
`4_World/Classes/UserActionsComponent/Actions/` (Continuous/SingleUse).

## Original textures and provenance

`tools/assets/proc_textures.py` uses stdlib Random, seed 349, no image model and
no downloads. Each tin/wire/wax/flame candidate contains matching 256-square
base_color, normal, roughness, metallic and ao TGAs, the exact generator and
recipe, original-work CC0 evidence, a byte-pinned provenance.v2 record, manifest
and seal. All generated bytes live in build/. The existing packer's five-map
layout is unchanged. Its normal green convention remains unverified.

`provenance.source.json` records original recipe inputs without asserting
parent-only admission fields. The lead must retain toolchain/run evidence and
seal the final candidate, including the actual native outputs, at admission.
No `.rvmat` is committed. The lead-run material stage calls pbr_pack.pack and
pbr_pack.rvmat; it derives flame_on from the latter with an explicit checked
emmisive edit. Super shader/emissive rendering remains native-unverified.

Optional CC0 candidates for a later, independently pinned archive (unused here):
[Poly Haven rusty_metal_02](https://polyhaven.com/a/rusty_metal_02),
[Poly Haven rust_coarse_01](https://polyhaven.com/a/rust_coarse_01),
[ambientCG Metal038](https://ambientcg.com/view?id=Metal038) (scratched steel
for wire). These are catalogue IDs, not approved archives, hashes or dependencies.

## Files changed for settings/readiness/use

* `mods/HollowCountry/scripts/4_World/Assets/HCTinCanLantern.c`: item, light,
  HCModule registration and readiness from installed config; registers
  `TinCanLantern/lantern_lit` at boot, counts a guarded native server work-start
  observation only. No count comes from registration. The shared readiness
  line retains runtime=PENDING. Missing assets addon reports refusal.
* `mods/HollowCountry/scripts/3_Game/HCSettings.c`: default-on setting,
  absence fallback for old operator documents, compiled registry, diff logging.
* `tools/validate/shared_settings.json`: authoritative EnableTinCanLantern row.
* `config/hollow-country-settings.json` and
  `mission/hollow-country/operator/settings.json`: shipped default true.

No core readiness source, lifecycle source, economy or admin catalogue changed.
The admin catalogue generator's inputs exclude this addon, and its --check passed.

## Codec and release requirements

Do not treat the source-only lint run as texture or model acceptance.

1. mlod.virtual_path must admit HollowCountryAssets. Current finish preflight
   refuses `lantern.codec_assets_prefix_required`. This worker did not touch mlod.
2. pbr_pack.rvmat must admit the same owned prefix. Current materials preflight
   refuses `lantern.pbr_assets_prefix_required`. The five-map pack API is used
   unchanged; no new emissive API is assumed.
3. Finisher's default distance work cap (2,000,000) is likely too small for these
   LOD pairs. A bounded spatial acceleration or another reviewed implementation
   is needed if the native meshes hit finish.distance_work_limit. Keep the 15 mm
   upper bound gate; no acceptance evidence exists yet.
4. Smooth flags are recorded in `.shading.json`; neutral.v1 remains closed.
   The existing runner deletes its temporary sidecar. The lantern author stage
   reconstructs object face ranges from its named selections and persists them.
   Finisher currently emits flat normals. It needs an explicit sidecar ingestion
   contract/sharp-edge mapping from its owner; we do not assume a new parameter.
5. build_assets_addon presently rejects ODOL by calling mlod.read_mlod. The
   release/codec worker must support the observed Binarize result, source coverage,
   sealed plan creation and assets loading/signing integration. No bypass of the
   sealed-candidate gate is supplied here.
6. Native compile, mesh/material/texture lint, ImageToPAA, Binarize, one-client
   light/material/IK/open check, retail boot and [HC Use] proof remain outstanding.
   No release, in-game experiment or issue closure is authorised by this source.

## Lead commands, in order (fresh build directories)

These commands are a runbook, not a record of execution. The lead holds the shared
native host lock for native steps, serially, while the owner is not playing.
Set HC_BLENDER to the qualified Blender 5.2.4 executable. The existing runner uses
-b --factory-startup --disable-autoexec --python-exit-code 1; no render is requested.

```sh
python3 -B -m tools.assets.proc_textures --output build/lantern/textures --size 256 --seed 349
python3 -B -m assets_src.lantern.build author --output build/lantern/mesh
python3 -B -m assets_src.lantern.build finish --output build/lantern/mesh
python3 -B -m assets_src.lantern.build materials --output build/lantern/materials
```

Expected: four sealed texture candidates; seven neutral meshes and shading
sidecars; hc_tincanlantern.p3d plus its model.cfg after all finish gates; sixteen
packed TGAs, four off rvmats and flame_on.rvmat. At the current base the finish
and materials commands refuse the prefix blockers above. Do not skip them.

The lead stages P: (or the qualified work drive) as
`HollowCountryAssets\lantern`, placing the MLOD as hc_tincanlantern.p3d,
model.cfg in its parent `HollowCountryAssets`, plus the generated materials.
For each TGAs run the observed converter form below from PowerShell (variables
name the lead's installed tool and build directories; they are not credentials):

```powershell
Get-ChildItem -LiteralPath $MaterialDir -Filter '*.tga' | ForEach-Object {
    & "$DayZTools\Bin\ImageToPAA\ImageToPAA.exe" $_.FullName ([IO.Path]::ChangeExtension($_.FullName, '.paa'))
    if ($LASTEXITCODE -ne 0) { throw 'ImageToPAA refused' }
}
& "$DayZTools\Bin\Binarize\binarize.exe" -o "$BinarizedDir\lantern\hc_tincanlantern.p3d" "$ModelDir\lantern\hc_tincanlantern.p3d"
if ($LASTEXITCODE -ne 0) { throw 'Binarize refused' }
```

The -o output input form is read from the installed
`Bin/BinMake/binMakeRules.txt:6-10`; the invocation has NOT been exercised here.
Expected: sixteen PAAs with valid headers and a readable ODOL with all required
LODs/sections/memory/mass retained. Resolve every model/rvmat/config texture
against actual PAAs, installed DZ and loaded addon sources. Never equate a zero
exit code with model or engine acceptance. Preserve the exact tool/version/run
record in the lead's sealed build candidate.

After the release worker implements ODOL admission and creates the reviewed,
sealed `build/lantern/plan.json` (not present in this worker's source-only run):

```sh
python3 -B -m tools.package.build_assets_addon --plan build/lantern/plan.json --out build/lantern/unsigned
python3 -B - <<'PY_SIGN'
import os
from pathlib import Path
from tools.package.sign import sign_and_verify
sign_and_verify(Path('build/lantern/unsigned/addons/HollowCountryAssets.pbo'),
                Path(os.environ['HC_DAYZ_TOOLS']), Path(os.environ['HC_RELEASE_PRIVATE_KEY']),
                Path(os.environ['HC_RELEASE_PUBLIC_KEY']), Path('build/lantern/signed'))
PY_SIGN
agent-run --memory 12G -- python3 -B -m tools.release.compile_gate --tree .
```

Expected: build manifest/admission receipt, assets PBO, .bisign/.bikey and an exact
positive DSCheckSignatures receipt; compile gate reaches Mission. The current
asset packer emits assets-addon.json, not BUILD_MANIFEST.json: the release build
owner must supply the clean-commit BUILD_MANIFEST contract before shipping.

The lead's isolated server/client launch appends the signed assets addon to the
existing qualified mod list (never replace dependency mods):

```powershell
& $DayZServer "-config=$ServerConfig" "-profiles=$ServerProfiles" "-mod=$QualifiedMods;$SignedAssetsMod" -port=2302
& $DayZClient "-profiles=$ClientProfiles" "-mod=$QualifiedMods;$SignedAssetsMod" -connect=127.0.0.1 -port=2302
```

Use the existing admin spawn-by-class flow for HC_TinCanLantern, then ignite with
a native match/torch source, extinguish, relight, drop, pick up, cargo-switch-off,
deplete fuel and delete it. Check a restored item, late client arrival, hand pose,
inventory view and light at the flame. No economy spawning is added. Required
proof: one server plus at most one client, 0 VMEs/missing textures, working
material swaps/fade, readiness and `[HC Use] module=TinCanLantern
feature=lantern_lit` activity. Multiplayer is not proven by that experiment.

Run the actual MLOD lint before binarisation, with inventories derived from the
actual converter outputs (do not populate them with hoped-for paths):

```sh
python3 -B -m tools.validate.asset_lint build/lantern/mesh/hc_tincanlantern.p3d --model-cfg mods/HollowCountryAssets/model.cfg --config mods/HollowCountryAssets/config.cpp --sources build/lantern/mesh/hc_tincanlantern.sources.json --textures build/lantern/textures-index.json --rvmats build/lantern/rvmats-index.json --json
```

