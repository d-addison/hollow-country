# Opus analysis of taped-light probe-006 (#56) — input to fix round 8

Source: Opus 5.5 investigator, read-only, at 182db38. [V] verified in source/run data, [I] inferred.
NS = ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
Run archive: ~/.cache/hollow-country/experiments/taped-light-probe-006/ (observations.json, report-182db38.json)
Reviewer analyzers (read-only, run with `python3 -I <script> ~/.cache/hollow-country/experiments/taped-light-probe-006`):
/code/hc-worktrees/taped-r7/scratchpad-review/opus/aggregate.py and counterfactual.py (+ their .log outputs).

## Root cause of qualified=0
Mainly a report-rule defect, plus probe defects. Server-side evidence is not impossible.

[V] Firearm resolution LODs: LOD.GetSelections false on all for 25/26 light-slot firearms; UMP45 lists but vertex read fails.
[V] Object.GetSelectionList (NS/3_Game/Entities/Object.c:382) on all 26 firearm slot hosts contains the light proxy,
e.g. `proxy:\dz\weapons\attachments\light\weaponlight_universal.001` / `...weaponlight_tlr.001`. Joins exactly to
config: ProxyWeaponlight_universal -> inventorySlot weaponFlashlight; ProxyWeaponlight_TLR -> pistolFlashlight.
[V] On CfgVehicles hosts the list is empty even for slots that certainly render (Chemlight, WalkieTalkie, Backpack_1):
missing proxy there is NOT negative evidence.
[V] InventorySlots.GetSelectionForSlotId / GetBoneNameForSlotId return "" for the three light slots.

Rule defect (tools/audit/taped_light_report.py): `_model_evidence` (~641) accepts only slot selection/memory/bone evidence
(always fed "") or resolution-LOD membership with vertices. `_accepted` (680-692) and `_evaluate_host` (~889) then label
missing evidence geometry_missing (415 no-slot hosts + Mich2001Helmet + R12).

Probe defects (tools/setup/taped_light_probe.py):
(a) HCTLHostSlots (998-1053) / HCTLObserveLight (1055-1130) call GetBoneIndex/MemoryPointExists/HasSelection with "" only;
    proxy_after_attach is always "". Entity.GetBoneIndex (NS/3_Game/Entities/Entity.c:35-39) takes a proxy selection
    name, which should come from GetSelectionList.
(b) HCTLResolutionScan (604-666) never records LOD.GetSelectionCount() (NS/3_Game/gameplay.c:215); "refused" and
    "empty" look the same. Skips geometryView/geometryFire.
(c) Vertices read out of scope: scan clears lodSelections (661); HCTLResRow (716-770) reads vertices after return.
    Native code keeps LOD/Selection use in one scope: ActionEnterLadder.c:31,36,71,90; WoodBase.c:335-344.
(d) Hosts spawn with ECE_IN_INVENTORY (~288); effect on LOD data untested [I].

Prerequisite chain: already handled at 182db38 [V]. HCTLPrereqVariant (1225-1268) fits the rail handguard
(CreateAttachmentEx, readback, rail flag) on a fresh host copy and re-tests; all 12 handguard hosts passed.

Counterfactual [V] — the rule below applied to probe-006 data yields 26 pairs:
- UniversalLight/weaponFlashlight after AK_RailHndgrd: AK101, AK101_Black, AK101_Green, AK74, AK74_Black, AK74_Green, AKM, AKM_Gold
- after M4_RISHndgrd: M4A1 x3; after MP5_RailHndgrd: MP5K
- direct: ASVAL, Aug, SCARH, SCARH_Black, SCARL, SCARL_Black, UMP45
- TLRLight/pistolFlashlight direct: Colt1911, CZ75, Engraved1911, FNX45, FNX45_arrow, Glock19, Glock19_Tan
Mich2001Helmet and R12 attached and read back but have no proxy in the list -> pending, not geometry_missing.

## Recommended rule: Tier S (server), all required
1. Host in classification and HasAttachmentSlot holds.
2. Light fits the slot.
3. CanAddAttachmentEx true; record direct vs after the named prerequisite (with its readback and rail flag).
4. CreateAttachmentEx succeeds and FindAttachment reads back the light's type.
5. A host GetSelectionList proxy normalizes (backslash/forward-slash/case, `proxy:` prefix, `.NNN` suffix) to a
   CfgNonAIVehicles entry whose model matches and inventorySlot == slot. Proves a native proxy exists; nothing invented.
6. Light has beamStart and beamEnd memory points (Object.c:452-454).
7. A native switch action finds the slot by name (ActionTurnOnWeaponFlashlight.c:27,32; helmet ActionTurnOnHelmetFlashlight.c:40, TurnOff :59).
8. Optional, stronger: GetBoneIndex(raw proxy name) >= 0 and GetBoneObject returns the attached light (server use [I]).

Labels: Tier S pass = `server_qualified` + `client_pending`, never accepted. HCTapedLightQualification.Ready()/Resolve
stay closed (HCTapedLightService.c:328-333) until a client tier passes. Resolution-vertex membership is dropped from
the rule (diagnostic only). no_native_light_slot -> not_server_evidencable. attached_without_model_selection ->
pending_client. geometry_missing only for real negatives (only proxy belongs to another slot, or config entry missing).

Client-only [V]: beam created only when !IsServer || !IsMultiplayer (UniversalLight.c:47-56, TLRLight.c:29-34,
Flashlight.c:13-18); drawn position/alignment/second-client view.

## Next change
1. Report (no new run needed): `_model_evidence` adds the proxy-config-slot route; resolution fields diagnostic only.
   `_accepted`/`_evaluate_slot` emit server_qualified/client_pending with prerequisite route, beam points, switch-action
   slot. `_evaluate_host` relabels. `_host_slots` (214-231) normalizes proxy name variants.
2. Probe (needs a new server run): HCTLHostSlots/HCTLObserveLight/HCTLPrereqVariant call GetBoneIndex with each raw proxy
   name for the slot (with/without `proxy:`, lowercase; record each); after attach compare GetBoneObject with the light.
   HCTLResolutionScan/HCTLResRow record GetSelectionCount() for every LOD incl. memory/geometry/geometryView/geometryFire,
   and read vertices in the same scope as GetSelections. One firearm control spawned without ECE_IN_INVENTORY.
   Keep the _OUT_CALLS lint (tools/setup/probe_runtime.py:168-170).
3. Gameplay: no change (product decision pending on non-native pairs).
