# Taped-light fix round 8 (issue #56): writer report

Worktree /code/hc-worktrees/taped-r8, branch hc/taped-r8, base 182db38. Nothing committed. No mods/ change.
Verdict semantics: `server_qualified` (Tier S) with `client_pending` on every pair; acceptance stays PENDING.

## Files changed (the four owned files only)
- tools/audit/taped_light_report.py
- tools/setup/taped_light_probe.py
- tests/unit/test_taped_light_report.py
- tests/unit/test_taped_light_probe.py
(tools/setup/probe_runtime.py untouched; the `_OUT_CALLS` lint passes: `probe.lint_hook(hook, explicit_numbers=True)` returns `[]`, max 8 `+` per statement.)

## RED (actual failures before implementation; scratchpad logs under /tmp/claude-1000/-code-dayzsa-mods/c2f49688-a754-49e7-ae80-940623b5a25a/scratchpad/)
- Report side (red-report.txt): `FAILED (failures=36, errors=5)` for the new Tier S / diagnostic-only / relabel / prerequisite-route / legacy-route tests.
- Probe side (red-probe.txt), RoundEightProbeTests: `Ran 15 tests ... FAILED (failures=4, errors=11)`; e.g. `ERROR: test_a_control_that_cannot_be_spawned_is_reported_not_skipped`, `ERROR: test_each_raw_proxy_name_variant_is_queried_for_the_slot_it_belongs_to`, `FAIL: test_one_firearm_control_is_spawned_without_the_inventory_flag_and_released`, `FAIL: test_a_vertex_is_read_in_the_scope_that_listed_its_selections`.
- Defect found while migrating old tests (red-watchdog.txt): `test_the_watchdog_ends_the_run_partial_releases_everything_and_queues_the_write` -> `json.decoder.JSONDecodeError: Expecting value: line 9 column 17 (char 1114)` / `FAILED (errors=1)`. Cause: my new `spawn_control` line was written as empty text when the run ended before the cursor-0 setup. Fixed in HCTLWriteResult (valid `{"class":"","spawn_flags":"","spawned":false}` default) and the test now also asserts that object.

## GREEN
- `cd /code/hc-worktrees/taped-r8 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_report tests.unit.test_taped_light_probe -v` -> `Ran 291 tests in 12.299s` / `OK`
- Full: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit > .../scratchpad/taped-r8-full.log 2>&1` -> `Ran 2417 tests in 101.663s` / `OK (skipped=1)`

Golden-hash test (`test_the_split_row_builders_produce_the_same_observation_text...`) re-recorded: earlier rounds kept the original hashes by stripping later-added facts, which no longer isolates round 8's changes. A structural json walk of the round 7 vs round 8 synthetic output showed only: spawn_control line, counters spawned/deleted 24->25 (control spawn), per-slot proxy_bone_*, per-light bone_object_*, lod_counts*, per-LOD instance_ok/native_count, and the TLRLight fixture gaining beamStart/beamEnd. Nothing else added, removed or changed.

## Rerun on probe-006 (observations of the 182db38 hook, so no round-8 probe facts in them)
`python3 -m tools.audit.taped_light_report --classification ~/.cache/hollow-country/experiments/taped-light-probe-003/classification.json --observations ~/.cache/hollow-country/experiments/taped-light-probe-006/observations.json --out .../scratchpad/report-r8-probe006.json`
`report: server_qualified=26 geometry_missing=0 not_server_evidencable=415 excluded=141 pending=2 hosts=584`
- acceptance PENDING, tier S, client_tier pending, integrity issues [], cleanup clean.
- out_of_v1_scope=415 (hosts without a native light slot, `not_server_evidencable`, reason `no_native_light_slot`), client_pending=26.
- Host-light pair totals: server_qualified 26, pending 2, geometry_missing 28 (UniversalLight on pistol hosts / TLRLight on rifle hosts: `no_compatible_native_slot`, real negatives), not_server_evidencable 830.
- Matches the Opus counterfactual exactly (26 server_qualified); no difference to explain.
- 26 server_qualified pairs (route): direct (14): ASVAL, Aug, SCARH, SCARH_Black, SCARL, SCARL_Black (UniversalLight/weaponFlashlight); Colt1911, CZ75, Engraved1911, FNX45, FNX45_arrow, Glock19, Glock19_Tan (TLRLight/pistolFlashlight); UMP45 (UniversalLight/weaponFlashlight, resolution diagnostic = vertex_missing).
  After the rail handguard prerequisite (12): AK101, AK101_Black, AK101_Green, AK74, AK74_Black, AK74_Green, AKM, AKM_Gold, M4A1, M4A1_Black, M4A1_Green, MP5K (UniversalLight/weaponFlashlight).
  Resolution LOD status for 25 of them is the diagnostic `resolution_enumeration_failed` (no longer gating).
- pending (pending_client, client_required): R12 (UniversalLight/weaponFlashlight), Mich2001Helmet (UniversalLight/helmetFlashlight).

## New default hook
size 98904 B, sha256 a8e8d7f3298a9c05905e2c54206a54a5c785d4a03c67ff69d5bca5dc5301931f (previous 87154 B, 3b838473f5d27f34fe007fba94186f6c1bbd0522ba4d64ecd45394a402c50e88). Size bound and compile-rule lints pass.

## What was implemented
Report: Tier S rule (slot observed + light fits, CanAddAttachmentEx true with route direct/after_prerequisite_handguard, create + FindAttachment read-back, host proxy normalised to a `Proxy<basename>` config entry whose model matches and whose inventorySlot holds the slot, beam points when observed, native switch action); resolution-vertex membership, GetBoneIndex/GetBoneObject, selection counts and the spawn control are diagnostics only; `no_native_light_slot` -> `not_server_evidencable` (+ v1_scope / `out_of_v1_scope`), `attached_without_model_selection` -> `pending_client`; `geometry_missing` only for real negatives; proxy-name normalisation; prerequisite route recorded; base attempt, variant attempt, handguard read-back and evaluated attempt retained separately; `client_pending` on every server_qualified pair.
Probe: GetBoneIndex per raw proxy-name variant (raw, no `proxy:`, lowercase, both; at most 4 distinct proxies per slot; also on the prerequisite variant host); GetBoneObject compared with the attached light after attach; GetSelectionCount for every LOD (`lod_counts`, bounded 16, null instance = -1); vertices read in the same scope as GetSelections; scanLod null guard around GetSelections/GetSelectionCount only (GetLODName outside); per-LOD `instance_ok`/`native_count`; one firearm control spawned with ECE_NOPERSISTENCY_WORLD|ECE_NOLIFETIME (no ECE_IN_INVENTORY), reported as `spawn_control` and released. Still exactly one `CreateObjectEx` and one `ObjectDelete` call sites.

## Review 008 findings
- P2-1 null scanLod guard / unavailable vs genuine false: FIXED (hook guard + `instance_ok`; report records "unavailable" apart from a genuine negative, self-consistency checks on instance-unavailable facts; tests `test_unavailable_is_recorded_apart_from_a_genuine_negative_resolution_scan`, `test_instance_unavailable_facts_must_be_self_consistent`, `test_a_null_lod_instance_is_reported_unavailable_and_never_called`). Runtime behaviour of a null LOD on the real engine is untested until the next native run.
- P2-2 R12 / Mich2001Helmet pending with client_required, not geometry_missing: FIXED (both pending_client in the probe-006 rerun).
- P2-3 legacy route: FIXED (positive flags with an empty selection name refused, queried selection name retained, agreement with the top-level slot mapping checked; tests `test_legacy_positive_flags_need_a_queried_selection_name`, `test_a_legacy_selection_name_must_agree_with_the_top_level_slot_mapping`).
- P3-4 mutation-surviving guards: FIXED for the listed cases (`1e999`, `"1\n"`, incomplete diagnostic name list with `1junk`, row/host list_ok disagreement while another LOD qualifies, hook/emulator side positive count with index -1 and zero count with valid index). Not re-mutation-tested in this session beyond the unit tests failing/passing.
- P3-5 retained attempts: FIXED (`base_attempt`, `variant_attempt`, handguard read-back and `evaluated_attempt` kept; raw base facts not overwritten).

## Remaining gaps
- All new probe facts (GetBoneIndex variants, GetBoneObject, GetSelectionCount, same-scope vertices, firearm control spawn) are unproven on the real engine until the next native probe run; the synthetic emulator proves only the hook logic and compile rules. The new hook has not been through the native compiler.
- Tier S rests on config-join evidence plus the native attach call; the verdict is server_qualified/client_pending, never accepted. Two-client and visibility evidence remain pending.
- HCTLTapedLightService/Qualification remain fail-closed by instruction; a product decision on non-native pairs is pending with the user (config-slot reuse and backpack/helmet mounts are post-v1, issue #58).
- The probe-006 observations predate the new hook, so spawn_control, lod_counts and proxy_bone_* show as absent in that rerun.
