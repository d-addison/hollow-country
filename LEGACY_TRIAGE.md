# Legacy suite triage — 9666daf7

PRODUCT-TOOL SUSPECTS: local-test-session rehearsal loses required travel XML; private development handoff omits a required Python helper. No gameplay/product-data bug is established by the quarantined translators. Both tool issues are left unresolved because this brief is report-only.

Counts: HARNESS_ROT 241; STALE_EXPECTATION 5; SUSPECT_PRODUCT 2. Successful file invocations: 61. Total: 309 isolated module invocations; 248 nonzero exits, matching the supplied baseline.

## Scope and method

Executed every tests/legacy/test_*.py file individually with timeout 300 python3 -B -m unittest tests.legacy.<name>, using four concurrent processes. Each process had a 2 GiB address-space cap (at most 8 GiB across the four principal processes). Full output was retained outside the worktree in /tmp/hc-legacy-triage; each captured result also contains the last 60 lines. No timeouts occurred. Git HEAD was checked read-only and remains 9666daf7.

No product, test, generator or tracked documentation was edited; no git write command was run. This report is the only worktree artifact. No tests were removed, rewritten, skipped or translated for this task. The package file already contains one skipped test, reported below without treating it as coverage. The two modules reporting NO TESTS RAN and the setUpClass failure are counted as HARNESS_ROT/nonzero, not successful tests.

Classifications are exclusive per failing FILE. A file containing translation/source-text failures and stale literal assertions is HARNESS_ROT unless an independently verified product-tool defect takes precedence. STALE_EXPECTATION is reserved here for the five files whose observed failures can be explained entirely by current content/contracts or cached admission. Some module invocations import tests defined elsewhere; these are invocation counts, not a deduplicated method-coverage total.

Offline Python outcomes do not overturn Build 148 native boot/readiness evidence, establish native behavior or multiplayer acceptance, or accept any deferred experiment. No generated artifact drift was established by these failures.

## SUSPECT_PRODUCT — most severe first

### 1. Local installer rehearsal drops a required travel input

File: tests/legacy/test_local_test_session.py. Verdict (a), SUSPECT_PRODUCT / product tooling; high confidence.

Failing tests, all in RealInstallers:

- test_a_changed_spawn_preset_refuses_rollback_before_anything_changes_and_the_retry_succeeds
- test_apply_and_rollback_leave_the_mission_and_profile_byte_identical
- test_the_real_interiors_installer_agrees_with_the_dry_run_when_a_profile_file_is_hard_linked
- test_the_real_interiors_pack_and_all_local_markers_install_and_roll_back_byte_identically
- test_the_real_loot_boost_is_on_by_default_installs_last_and_rolls_back_first_byte_identically
- test_the_real_snafu_and_tactical_flava_deltas_install_and_roll_back_byte_identically

Evidence: these tests expect CLI plan/apply to succeed before checking rollback/conservation. They instead return 2 with a refusal that the scratch mission lacks cfgeventspawns.xml. In tools/setup/local_test_session.py:1263, rehearse_deltas copies economy.INPUTS, optional coverage mapgroupproto.xml and loot_boost.INPUTS. It never includes travel.INPUTS when travel is selected, although it calls travel.install at line 1290. tools/package/travel.py:22 declares cfgeventspawns.xml as required, and install reads it at line 362. Neither the economy input tuple nor loot-boost inputs contains that XML.

Independent verification used disposable synthetic mission data and the real travel installer: supply a valid <eventposdef> document in the ORIGINAL mission; direct travel.install succeeds. Feed the same source to the real rehearse_deltas with travel=True and a valid synthetic economy profile; it fails because its SCRATCH mission lacks cfgeventspawns.xml. Only economy_delta profile selection was adapted in memory to use the existing small synthetic profile; economy generation/install, scratch copying and travel install remained real. The original positions file remained byte-identical. Thus adding the missing XML to the legacy fixture alone cannot cure this failure.

Impact: local_test_session plan/apply with a selected travel delta and economy can refuse even when the operator source mission contains valid required XML. Failure occurs during rehearsal; no evidence here of a damaging real mission install. The friend bundle uses a separate installation path, so this does not establish a Build 148 release-bundle defect. Suggested follow-up: derive rehearsal inputs from every selected installer, including travel.INPUTS, then rerun this module. No fix made.

Final result: Ran 174 tests; FAILED (failures=6).

### 2. Private development ZIP omits an unconditional helper dependency

File: tests/legacy/test_package.py; PackageBehavior.test_extracted_handoff_imports_the_overlay_remove_helper. Verdict (a), SUSPECT_PRODUCT / product tooling; high confidence.

Evidence: the test builds and verifies a handoff, extracts it, and launches isolated Python with only the extracted tree on its import path. Expected: ce_extensions._registrations() succeeds and prints ok. Actual: ImportError for tools.package.HCWildlife_habitats. tools/package/pbo.py:613 explicitly bundles optional_overlays.py and ce_extensions.py but omits HCWildlife_habitats.py. ce_extensions.py:9 imports optional_overlays, whose unconditional import at line 28 requires that omitted helper. The module exists in the repository. This is executable import-closure evidence, not an exact-content snapshot or an Enforce translation.

Impact: bundled CE helper operations that call this registration helper fail in an isolated private development handoff. The handoff is documented by tools/package/README.md and remains an offered tool path. tools/setup/friend_bundle.py:59 separately includes HCWildlife_habitats.py, so this result does not show it is missing from the published friend-release bundle. Suggested follow-up: include the actual transitive dependencies in both handoff generation and verification allowlists, then rerun this module. No fix made.

Final result: Ran 39 tests; FAILED (failures=1, skipped=1). The pre-existing skip provides no evidence.

## STALE_EXPECTATION verification

- tests/legacy/test_expansion_ai_event_reach.py: Expanded patrol catalog: two additional gap-coverage routes start near event anchors. Runtime spawn admission rejects nearby observers; the original reaching police routes remain. The test unnecessarily requires every reaching route to start at least MinPlayerDistance + 25 away.
- tests/legacy/test_hc53_dispositions.py: Exact four-file mission-interiors snapshot predates the current generated templates directory; it rejects legitimate template pack content before evaluating HC-53 audit integrity.
- tests/legacy/test_hc_furnishing.py: Assumes the first authored home layout has no measured prop boxes. Both requested prop classes now exist in interior_prop_boxes.json, so the builder correctly reports covered.
- tests/legacy/test_v2_leads.py: Expects string.printable (100 characters) to become a 105-character solo group key. SoloGroup now refuses identity lengths above 91 to respect the 96-character token limit.
- tests/legacy/test_w67_admintp.py: Pins destination order and expects a live filesystem-marker check in HCMove. Admission is now cached by HCStart/OnStart; the fixture bypasses startup and supplies m_Enabled=True despite its disabled marker.

Additional checks: the current patrol policy has 528 sites. The two rejected gap routes start about 61.77 m and 30.14 m from the respective event anchor; the test demands 225 m for every reaching patrol. Runtime SpawnProblem/MemberSpawnProblem in HCXAISiteRules.c enforce MinPlayerDistance and the perception ring, so the failure is not evidence of near-player spawning. The original police-komarovo and police-novaya-petrovka patrols remain. The furnishing first-layout props are StaticObj_Furniture_case_bedroom_b and StaticObj_Furniture_PaperBox_01_small_closed, both present in the current box database. HCLeadPolicy.SoloGroup explicitly refuses inputs longer than 91. HCAdminTeleport.HCStart checks the disable marker; HCMove uses cached m_Enabled.

## Complete failing-file inventory

Each entry includes the file classification, observed cause, failing method names (deduplicated across subtests), and its final unittest result. No product/test changes were made for any entry.

### tests/legacy/test_162_followups.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_empty_infected_is_transient_and_names_the_real_class_and_constraint, test_ineligible_infected_report_the_failed_constraint_and_measured_distance, test_police_anchors_exactly_match_stock_map_class_and_position, test_startup_empty_infected_does_not_declare_a_valid_anchor_impossible, test_startup_identifies_out_of_range_static_anchor_once_without_disabling_retries, test_unreadable_ground_still_identifies_the_wanted_class, test_unreadable_startup_query_is_unknown_rather_than_proof_of_bad_anchor.

Final result: Ran 11 tests in 0.064s; FAILED (failures=7); process exit 1.

### tests/legacy/test_acceptance_optins.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_only_the_nine_new_probes_were_added, test_literal_v1_lines_in_source_match_the_helper_exactly.

Final result: Ran 17 tests in 0.242s; FAILED (failures=2); process exit 1.

### tests/legacy/test_admin_lootmap.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_admin_job_is_bounded_filtered_readonly_and_exports_honest_counts.

Final result: Ran 2 tests in 0.620s; FAILED (errors=1); process exit 1.

### tests/legacy/test_admin_lootmap_ticks.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_every_tick_spends_at_least_the_row_floor_before_the_deadline_may_stop_it, test_row_deadline_remains_an_upper_bound_and_the_cap_is_sized_from_the_floor, test_slow_native_query_does_not_cost_a_second_tick_per_cell, test_slow_row_loop_still_finishes_because_the_row_floor_is_deterministic, test_worst_case_rows_still_fit_the_cap_with_slow_queries.

Final result: Ran 6 tests in 0.054s; FAILED (failures=5); process exit 1.

### tests/legacy/test_admin_lootmap_wiring.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_all_24_wire_layers_plus_lootmap_are_listed_and_the_late_ones_toggle, test_client_window_is_sized_from_the_budget_the_server_sent, test_export_failure_after_the_ack_is_a_final_reply_the_client_consumes, test_kept_marks_after_a_refused_final_reply_are_labelled_with_their_filter, test_kept_marks_of_an_unfiltered_run_are_still_labelled, test_ok_final_reply_with_no_matches_still_clears_the_previous_layer, test_refused_final_reply_keeps_the_previous_lootmap_marks_and_shows_the_reason, test_session_and_ticket_expire_with_the_sized_window, test_the_layer_list_row_carries_the_filter_and_the_previous_run_mark, test_the_menu_layer_list_shows_the_label_and_toggles_by_the_raw_layer_name.

Final result: Ran 24 tests in 1.087s; FAILED (errors=10); process exit 1.

### tests/legacy/test_admin_party_ownership.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_reserved_party_is_excluded_from_selection_and_start_until_release, test_start_rechecks_reservation_after_successful_selection.

Final result: Ran 2 tests in 0.122s; FAILED (errors=10); process exit 1.

### tests/legacy/test_admin_physical_hooks.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_visitor_request_keeps_durable_cooldown_and_reservation, test_director_startup_failure_stop_and_adapter_binding_publish_live_status, test_visit_tick_retains_budget_attendance_combat_and_expiry.

Final result: Ran 7 tests in 0.047s; FAILED (errors=4); process exit 1.

### tests/legacy/test_admin_start_refusals.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_valid_allowlist_publishes_ready_and_runs.

Final result: Ran 5 tests in 0.037s; FAILED (errors=1); process exit 1.

### tests/legacy/test_admin_test_kit.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_ages_only_the_oldest_pending_timer_and_requests_a_tick, test_save_refusal_is_reported, test_clears_only_the_tuned_channel_rate_limit_and_queues_it, test_failed_save_reports_a_reason, test_calm_sets_the_normal_calm_window_and_others_clear_it, test_clearing_ends_the_calm_the_override_started, test_each_profile_picks_a_day_whose_seed_draws_it, test_zero_clears_the_override.

Final result: Ran 48 tests in 0.340s; FAILED (errors=8); process exit 1.

### tests/legacy/test_admin_ui.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_new_catalog_integer_ranges_do_not_need_menu_changes, test_typed_values_clamp_and_malformed_values_never_become_zero.

Final result: Ran 20 tests in 0.353s; FAILED (errors=2); process exit 1.

### tests/legacy/test_ai_fresh_respawn.py — HARNESS_ROT

Includes apparently data-oriented cases, but DTO construction fails in test_expansion_ai_adapter.make while json.loads parses an Enforce initializer; other failures are missing synthetic collaborators.

Failing methods: test_depleted_group_waits_for_durable_clock_combat_and_every_observer, test_shipped_sites_use_short_timers_and_mirrors_match, test_timer_validation_is_bounded_and_zero_inherits, test_actual_publish_stage_and_catalog_yield_record_their_own_cost_owner, test_coastal_adapter_finds_land_and_retains_every_observer_gate, test_spawn_connector_checks_only_endpoint_and_rejects_partial_path, test_publish_started_from_phase_zero_is_charged_to_publish, test_replacement_advances_once_when_shared_pool_is_exhausted.

Final result: Ran 19 tests in 0.905s; FAILED (failures=1, errors=7); process exit 1.

### tests/legacy/test_ai_limits.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_sizes_are_stable_and_spread, test_shared_site_budget_refusal_logs_once_per_minute, test_site_problem_and_budget_refusals_share_per_patrol_minute_limiter, test_actual_site_and_adapter_admission_share_materializer_reservation, test_surveyed_adapter_uses_configured_stable_size_without_inventing_positions.

Final result: Ran 18 tests in 0.816s; FAILED (errors=5); process exit 1.

### tests/legacy/test_ai_ops_168.py — HARNESS_ROT

Policy tests fail in the Enforce DTO port, before Python policy validation or generated-profile checks can establish a product mismatch.

Failing methods: test_refused_factory_can_succeed_later_and_rollback_does_not_hammer, test_scope_two_table_factory_and_success_finishes_once, test_configured_raid_floor_and_short_respawn_lock_boundary, test_spawn_log_is_exact_one_rounded_xz_line, test_native_validation_rejects_bad_floors_and_scales, test_new_policy_keys_defaults_and_generated_profiles, test_python_policy_validation_types_ranges_and_absence, test_reader_rejects_bad_operator_policy_and_accepts_legacy_absence.

Final result: Ran 18 tests in 0.388s; FAILED (errors=8); process exit 1.

### tests/legacy/test_ai_respawn_defaults.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_fresh_copy_and_failed_backup_do_not_lose_profile, test_legacy_missing_keys_is_backed_up_and_adopted, test_unknown_newer_keys_and_same_schema_legacy_are_kept.

Final result: Ran 5 tests in 0.017s; FAILED (errors=3); process exit 1.

### tests/legacy/test_alert_chain.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_hops_attenuation_emitter_and_recipient_dedupe_inherit_root, test_missing_inherited_root_cannot_seed_fresh_root, test_native_adapter_explicitly_labels_seed_and_relay_as_heard, test_queue_hard_cap_16_root_cap_8_and_root_id_exhaustion, test_radius_strength_cooldown_geometry_and_dead_recipients_fail_closed, test_recipient_cap_12_work_limit_and_scan_limit_24, test_recipient_rotation_and_two_bounded_geometry_tests_remain, test_root_ttl_30_queue_window_2_and_no_lifetime_refresh, test_server_alive_noncalm_and_tracked_limit_are_required.

Final result: Ran 10 tests in 0.115s; FAILED (errors=14); process exit 1.

### tests/legacy/test_atmosphere.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: setUpClass, test_disabled_weather_preserves_range_without_sampling_environment, test_enabled_weather_shrinks_only_relay_range_at_frozen_source, test_authored_world_and_exact_engine_build_gate_are_cached, test_available_noise_system_keeps_relay_range_guards, test_dawn_boundary_restores_daytime_limits_once, test_daytime_start_leaves_limits_full_and_never_forces_a_forecast, test_delegation_probe_is_bounded_once_and_rejects_comment_spoofing, test_dusk_boundary_caps_storm_cloud_once_and_is_idempotent, test_dusk_callback_does_nothing_without_a_game_instance, test_enabled_executes_delegation_and_server_guards, test_missing_noise_system_preserves_vanilla_and_logs_once, test_native_range_is_sampled_at_emission_source_and_disabled_is_identity, test_night_forecasts_cap_cloud_rain_and_wind_even_with_lagging_storm_cloud, test_night_limits_are_server_only_and_need_the_started_chernarus_owner, test_owned_forecasts_use_only_the_requested_native_phenomenon, test_startup_at_night_during_a_storm_caps_actual_overcast_natively, test_startup_at_night_with_clear_sky_limits_without_forcing_a_change, test_startup_blocks_foreign_drivers_and_uses_synced_native_lighting_once, test_startup_registers_one_boundary_check_and_non_chernarus_registers_none, test_stock_disabled_weather_xml_and_absent_file_delegate_to_script, test_stop_uses_the_queue_category_that_scheduled_the_callback, test_stopped_owner_removes_the_dusk_callback_and_a_late_run_writes_nothing, test_volumetric_fog_delegates_when_unadmitted_and_bounds_native_writes.

Final result: Ran 51 tests in 0.755s; FAILED (failures=65, errors=3); process exit 1.

### tests/legacy/test_auditcarry_goods.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_ambiguous_move_is_not_replayed, test_carries_same_item_until_observed_home_then_deposits_once, test_full_crate_leaves_goods_on_actor_and_logs_once, test_native_custody_moves_the_house_item_without_replacing_primary, test_preflight_rechecks_visibility_lease_and_ownership, test_carry_cap_is_required_and_validated_in_the_shipped_survey, test_search_saves_receipt_before_native_commit_and_records_real_custody.

Final result: Ran 11 tests in 0.163s; FAILED (errors=10); process exit 1.

### tests/legacy/test_auditcot_binding.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_base_has_no_vendor_dependency_and_addon_factory_is_guarded.

Final result: Ran 6 tests in 0.055s; FAILED (failures=1); process exit 1.

### tests/legacy/test_auditdiag_behavior.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_manifest_diagnostic_names_characters_without_claiming_byte_size.

Final result: Ran 11 tests in 0.197s; FAILED (failures=1); process exit 1.

### tests/legacy/test_auditdiag_integration.py — HARNESS_ROT

No unittest cases discovered (exit 5); documentation/helper-style module is not an executable product test.

Failing methods: none discovered; module reports NO TESTS RAN.

Final result: Ran 0 tests in 0.000s; NO TESTS RAN; process exit 5.

### tests/legacy/test_auditleather_recipes.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_client_preview_does_not_depend_on_server_startup_state, test_finite_panels_and_native_kit_wear_without_whole_stack_destruction, test_preview_rejects_short_materials_ruined_tools_foreign_and_deleting_items, test_startup_audit_rejects_cached_debit_drift_and_missing_config.

Final result: Ran 5 tests in 0.050s; FAILED (errors=4); process exit 1.

### tests/legacy/test_auditleaves_runtime.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_existing_audit_expectations_updated_in_local_fixture_only.

Final result: Ran 9 tests in 0.046s; FAILED (failures=1); process exit 1.

### tests/legacy/test_auditlight_legacy_contracts.py — HARNESS_ROT

Tries to amend fixture copies at old tests/unit paths after suite relocation; missing test files are harness inputs, not missing shipped content.

Failing methods: test_amendments_accept_real_tests_after_lead_applies_patch, test_updated_legacy_contracts_in_explicit_fixture_copies.

Final result: Ran 2 tests in 0.002s; FAILED (errors=2); process exit 1.

### tests/legacy/test_auditlight_runtime.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_no_admitted_pair_cannot_publish_ready, test_shared_adapter_optout_closes_helmet_startup, test_shared_adapter_optout_closes_pack_startup_with_usable_slots, test_existing_operator_optout_survives_the_renamed_selector, test_unverified_wearables_do_not_fabricate_measurement_digest, test_mount_replay_remove_share_existing_finite_journal_and_debit.

Final result: Ran 13 tests in 0.438s; FAILED (errors=8); process exit 1.

### tests/legacy/test_auditpick_admission.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_a_remembered_clue_refuses_before_any_journal_write_then_expires, test_another_partys_live_run_is_named_by_the_world_cap, test_remembered_noise_on_the_route_refuses, test_with_runs_off_nothing_changes, test_opt_out_never_gates_on_need, test_the_same_stash_is_enough_in_summer_and_short_in_winter, test_unavailable_season_keeps_the_neutral_target_and_unreadable_stash_never_runs, test_lifecycle_refuses_a_small_party_once_by_name_and_rearms_later, test_member_bounds_and_the_recheck_interval_come_from_the_survey, test_combat_or_pending_spawn_is_not_an_idle_party, test_despawn_mid_trip_uses_loss_journal_without_item_copy_or_move, test_existing_step_visits_one_state_under_shared_budget, test_feature_off_client_or_site_cooldown_never_begins, test_lifecycle_passes_claimed_identity_actor_lease_once, test_missing_group_is_named_before_base_lifecycle_removes_state, test_missing_group_or_unsurveyed_route_refuses_once_by_name, test_per_party_receipt_survives_another_partys_journal, test_cooldown_cap_budget_and_real_home_position_precede_begin, test_idle_surveyed_party_starts_once_with_real_actor_and_lease, test_terminal_rearm_is_durable_and_quarantine_is_never_replayed.

Final result: Ran 22 tests in 1.208s; FAILED (errors=24); process exit 1.

### tests/legacy/test_auditpick_harness.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_policy_translates.

Final result: Ran 1 test in 0.007s; FAILED (errors=1); process exit 1.

### tests/legacy/test_auditpick_policy.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_a_run_needs_a_stash_below_the_seasonal_target_and_never_on_a_guess, test_need_target_scales_with_the_season_phase, test_season_phase_is_a_read_only_query_of_the_weather_owner, test_source_only_calls_the_read_accessor, test_unavailable_phase_keeps_the_neutral_scale, test_active_phases_count_as_runs, test_bounds_come_from_the_survey_not_the_code, test_named_world_and_camp_caps, test_two_to_six_members_are_admitted, test_a_clue_on_another_route_does_not_close_this_one, test_a_fresh_own_clue_refuses_then_expires, test_clue_table_is_capped_and_repeats_refresh_in_place, test_deferred_refusals_rearm_on_the_recheck_interval, test_no_live_player_position_is_ever_read, test_remembered_noise_at_a_waypoint_refuses_below_threshold_it_does_not, test_each_defect_is_named, test_opt_out_file_turns_the_runs_off, test_the_shipped_survey_is_usable, test_two_routes_in_one_camp_exceed_the_per_camp_cap, test_every_run_limit_is_present_and_a_missing_one_is_refused_by_the_loader_guard.

Final result: Ran 21 tests in 0.150s; FAILED (failures=1, errors=19); process exit 1.

### tests/legacy/test_auditpick_runs.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_a_party_below_the_minimum_ends_the_run_and_remembers_a_loss, test_combat_holds_then_aborts_after_the_survey_seconds_with_a_clue, test_opt_out_file_leaves_the_existing_single_item_trip_alone, test_short_combat_that_ends_resets_the_timer, test_unknown_membership_never_aborts, test_a_failed_commit_releases_the_token_and_is_not_counted, test_a_refused_reservation_skips_the_house_and_attempts_are_bounded, test_a_walk_that_never_arrives_gives_up_on_that_house, test_an_unbound_port_is_named_once_and_the_normal_run_continues, test_back_leg_that_never_arrives_aborts_without_a_teleport, test_nothing_starts_until_the_party_is_at_the_source, test_reserve_wait_commit_release_in_order_and_houses_are_capped, test_returning_leg_drops_any_token_and_runs_no_house_stage, test_visits_the_nearest_unvisited_house_first, test_lease_lost_mid_stage_releases_the_reservation, test_lost_lease_or_carrier_aborts_before_any_house_call, test_a_normal_run_still_acquires_after_the_house_stage, test_hold_does_nothing_and_abort_loses_the_trip_without_moving_cargo.

Final result: Ran 18 tests in 0.117s; FAILED (errors=19); process exit 1.

### tests/legacy/test_auditpose_cap.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_bounds_and_live_getter_fail_closed_when_owner_is_inactive, test_missing_key_defaults_but_explicit_zero_and_invalid_values_survive, test_nondefault_cap_is_shared_and_cleanup_does_not_need_a_slot, test_shipped_default_and_named_refusal_are_wired.

Final result: Ran 4 tests in 0.033s; FAILED (failures=1, errors=3); process exit 1.

### tests/legacy/test_auditpose_riser.py — HARNESS_ROT

Mixed missing HCHordeLimits fixture and obsolete only-sit admission/prose pins. Current animation pipeline documents poses 1–4 and the corresponding graph/clip sources.

Failing methods: test_dead_or_deleted_posed_body_still_releases_pose_without_resurrecting, test_posed_body_latches_idle_once_and_wake_releases_pose_and_idle_once, test_refusals_leave_the_body_a_normal_actor, test_config_posed_cadence_is_optional_defaulted_and_bounded, test_budget_refuses_the_thirteenth_pose, test_new_pose_cannot_interrupt_a_rise_but_cleanup_still_can, test_rise_length_follows_the_pose_being_left_and_reports_to_the_owner, test_shipped_sit_is_requestable_and_unshipped_poses_refuse_once_per_change, test_variety_hooks_route_to_the_request_path, test_missing_addon_class_or_opt_out_falls_back_to_the_native_variant, test_other_ordinals_keep_native_crawler_and_standing_variants, test_third_body_of_a_group_is_posed_through_the_addon_class, test_fresh_pose_is_cadenced_context_fitted_and_falls_back_to_shipped_sit, test_shipped_set_equals_graph_states_equals_clips, test_tier_c_admission_follows_only_shipped_assets.

Final result: Ran 17 tests in 0.142s; FAILED (failures=3, errors=12); process exit 1.

### tests/legacy/test_auditsearch_loops.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_recycle_and_compaction_each_progress_in_the_same_exhausted_tick.

Final result: Ran 1 test in 0.057s; FAILED (errors=1); process exit 1.

### tests/legacy/test_auditsearch_pickrefresh.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_human_revisit_keeps_the_same_refresh_behavior, test_picker_revisit_refreshes_new_stock_once_and_keeps_contention_lock, test_refresh_ownership_excludes_other_actors_and_selected_rows.

Final result: Ran 3 tests in 0.179s; FAILED (errors=3); process exit 1.

### tests/legacy/test_auditsearch_reservations.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_a_spent_shared_pool_still_binds_once_without_pre_spending_the_scan_unit, test_authority_loss_range_death_deadline_and_opt_out_refuse_without_move, test_full_inventory_or_changed_stock_does_not_grant, test_invalid_authority_site_or_identity_never_binds_stock, test_native_preflight_callback_revocation_cannot_move, test_one_shared_lock_and_one_real_transfer_with_no_replay, test_player_reservation_blocks_picker, test_release_and_expiry_do_not_consume_stock, test_restart_keeps_depletion_and_uncertain_move_is_not_replayed.

Final result: Ran 9 tests in 0.516s; FAILED (errors=9); process exit 1.

### tests/legacy/test_auditseason_phase.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_consumers_read_boundaries_from_the_existing_owner_without_advancing_it, test_off_paused_missing_unhealthy_and_nonserver_never_look_like_spring, test_start_logs_leaf_asset_boundary_once_without_blocking_clock.

Final result: Ran 4 tests in 0.037s; FAILED (failures=1, errors=2); process exit 1.

### tests/legacy/test_auditshelter_integration.py — HARNESS_ROT

Nested runs of translated legacy fixtures fail; their errors are not independent product evidence.

Failing methods: test_proposed_edits_accept_already_integrated_files, test_every_listed_module_derives_its_status_from_live_state, test_disabled_modules_get_no_baseline_so_indexes_follow_the_active_array, test_refresh_prints_one_late_ready_line_when_a_module_changes_after_boot, test_stop_and_restart_reset_the_change_baseline, test_updated_existing_behavioral_fixtures.

Final result: Ran 3 tests in 0.214s; FAILED (failures=2); process exit 1.

### tests/legacy/test_auditshelter_scenes.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_config_validation_rejects_missing_limits_and_access_overlap, test_real_batch_rollback_and_complete_only_publication, test_real_budget_advances_all_scenes_after_interiors_spends_twelve_units.

Final result: Ran 6 tests in 0.025s; FAILED (failures=2, errors=1); process exit 1.

### tests/legacy/test_auditwild_ecosystem.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_feature_off_and_budget_denial_do_no_damage_or_position_queries, test_positive_blood_damage_records_historical_point_and_actual_contact, test_zero_blood_damage_never_invents_blood_clues.

Final result: Ran 13 tests in 0.277s; FAILED (errors=3); process exit 1.

### tests/legacy/test_base_raid_adapter_guards.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_door_sighting_requires_compatible_door_component_and_live_claim, test_sense_bounds_snapshot_and_examines_one_object_per_tick, test_storage_requires_current_range_and_geometry_and_seen_rechecks_them, test_storage_seen_requires_camp_membership_and_live_unreserved_party, test_invalid_route_and_changed_group_do_not_replace_waypoints, test_raid_and_visit_interruptions_restore_original_route_and_behavior.

Final result: Ran 10 tests in 0.603s; FAILED (errors=22); process exit 1.

### tests/legacy/test_bases_native_paths.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_container_discovery_uses_native_identity_and_acknowledged_camp_store, test_container_tick_uses_its_shared_consumer_to_avoid_starvation, test_missing_probe_dispatch_does_not_spend_durable_cooldown.

Final result: Ran 10 tests in 0.061s; FAILED (errors=3); process exit 1.

### tests/legacy/test_bases_raid.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_operator_off_never_reads_provider_or_spends_work, test_failed_durable_warning_barrier_cancels_party_without_warning, test_missing_dispatch_and_no_sighting_spend_no_cooldown, test_status_is_derived_from_binding, test_success_persists_before_warning_then_arms_cooldown, test_warning_requires_online_recipient_and_real_reservation.

Final result: Ran 16 tests in 0.141s; FAILED (errors=6); process exit 1.

### tests/legacy/test_bases_round2.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_container_then_hearth_matches_hearth_only_binding_tier_and_respawn, test_overflow_candidates_are_retained_and_retried_one_per_budgeted_tick.

Final result: Ran 2 tests in 0.013s; FAILED (errors=2); process exit 1.

### tests/legacy/test_build_identity.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_fresh_journal_is_stamped_canonical_and_reloads_under_the_native_engine_string, test_legacy_native_stamp_still_loads_and_foreign_stamps_quarantine.

Final result: Ran 26 tests in 0.285s; FAILED (errors=2); process exit 1.

### tests/legacy/test_burn_loot_refusals.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_begin_while_disabled_is_reported_and_schedules_nothing, test_second_begin_is_reported_as_already_handed_over, test_start_after_stop_is_reported, test_unadmitted_search_marker_is_reported_at_start, test_begin_without_interior_action_data_records_session_reason, test_continue_refuses_a_moved_cursor_with_a_reason, test_continue_refuses_an_expired_session_with_a_reason, test_continue_refuses_an_unknown_action_with_a_reason, test_faulted_service_refuses_the_journal_with_a_storage_reason, test_second_commit_on_a_finished_site_is_refused_as_busy, test_start_with_unrestorable_layout_state_is_reported, test_start_without_a_manifest_is_reported, test_pilot_faulted_service_refuses_with_a_storage_reason, test_pilot_journal_without_a_valid_pin_refuses_with_a_storage_reason.

Final result: Ran 28 tests in 0.676s; FAILED (errors=14); process exit 1.

### tests/legacy/test_c1_infectedcfg.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_all_blocks_default_invalid_numeric_overrides, test_every_numeric_field_has_fallback_and_range, test_owner_normalization_publishes_and_logs_bad_input_once, test_profile_changes_door_reach_chain_and_conservative_lod_decisions, test_profile_changes_horde_reuse_and_invalid_falls_back, test_profile_changes_perception_memory_and_group_scaling.

Final result: Ran 6 tests in 1.231s; FAILED (errors=227); process exit 1.

### tests/legacy/test_c2_atmoscfg.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_client_sound_schedule_and_grade_strength_override.

Final result: Ran 7 tests in 1.757s; FAILED (errors=1); process exit 1.

### tests/legacy/test_c3_survivalcfg.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_profile_override_changes_signal_cooldown, test_profile_overrides_and_invalid_fallback_for_every_numeric_field, test_profile_override_changes_progression_gain_period.

Final result: Ran 11 tests in 0.608s; FAILED (failures=1, errors=2); process exit 1.

### tests/legacy/test_camp_theft_scan.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_empty_or_home_crates_are_skipped_but_global_faults_stop, test_ineligible_first_crate_does_not_hide_a_later_valid_crate, test_scan_stays_bounded_by_shared_work_and_reports_last_candidate_refusal.

Final result: Ran 3 tests in 0.013s; FAILED (failures=3); process exit 1.

### tests/legacy/test_cfgfu_220.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_memory_keeps_saved_grid_when_profile_changes, test_memory_legacy_start_validates_then_persists_empty_configured_grid, test_memory_legacy_unknown_grid_expires_heat_instead_of_rekeying, test_saved_grid_survives_json_roundtrip_and_invalid_metadata_refuses, test_vault_quartet_falls_back_together.

Final result: Ran 14 tests in 0.204s; FAILED (errors=6); process exit 1.

### tests/legacy/test_client_frame_costs.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_clear_drops_every_cached_widget_reference, test_empty_member_name_still_gets_its_team_prefix, test_name_change_and_scale_change_refresh_only_what_changed, test_steady_frames_do_no_widget_lookup_scale_or_text_writes.

Final result: Ran 19 tests in 1.270s; FAILED (errors=4); process exit 1.

### tests/legacy/test_convoy_runtime.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_every_refusal_has_a_named_reason, test_plans_car_to_destination_on_own_parents_and_stops_short_of_target, test_work_is_bounded_per_tick_and_refused_budget_makes_no_progress, test_board_timeout_dismounts_and_restores_the_whole_walking_route, test_boarding_waits_for_door_route_and_formation, test_claimed_or_missing_vehicle_keeps_the_walking_caravan_after_bounded_scans, test_contact_stall_foreign_crew_and_timeout_stop_then_dismount, test_dismount_holds_for_every_member_then_gives_up_after_the_bounded_window, test_full_journey_drives_stops_dismounts_and_walks_only_the_remainder, test_input_only_drives_in_drive_and_holds_brake_otherwise, test_player_taking_the_driver_seat_while_boarding_gets_the_car_at_once, test_player_taking_the_driver_seat_while_driving_gets_the_car_and_the_crew_leaves, test_release_while_driving_dismounts_without_rewriting_waypoints, test_seek_picks_nearest_qualified_world_car_and_walks_to_its_door.

Final result: Ran 26 tests in 0.394s; FAILED (errors=14); process exit 1.

### tests/legacy/test_core_lifecycle.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_empty_stop_and_nonserver_start_remain_noops, test_failed_start_retry_unwinds_before_selftest_or_config_rejection, test_normal_order_enabled_filter_and_reverse_shutdown_are_preserved, test_partial_stop_without_game_still_cleans_callbacks, test_retry_cleans_stale_modules_before_any_new_start, test_retry_cleanup_abort_does_not_admit_new_modules, test_start_abort_tracks_current_module_for_cleanup, test_stop_abort_removes_callback_before_call_and_next_stop_finishes, test_stop_unwinds_initial_partial_start_in_reverse_order, test_tick_times_each_module_in_registration_order.

Final result: Ran 11 tests in 0.112s; FAILED (failures=11); process exit 1.

### tests/legacy/test_craft_burn.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_every_admission_gate_sets_one_stable_reason, test_begin_names_capacity_and_duplicate_sessions, test_can_start_names_an_exhausted_or_unenrollable_wreck, test_enroll_failure_after_admission_is_named_and_adds_no_session, test_start_refusals_log_each_reason_once_until_it_changes_or_clears.

Final result: Ran 18 tests in 0.146s; FAILED (errors=5); process exit 1.

### tests/legacy/test_debug_map_layers.py — HARNESS_ROT

Python-port fixture signature/type assumptions no longer match the authored code; no real data/tool failure was observed.

Failing methods: test_a_crowded_notice_cuts_on_entry_boundaries_and_counts_what_it_dropped, test_a_crowded_notice_keeps_its_tail_and_stays_inside_the_byte_cap, test_a_notice_that_fits_has_no_more_marker, test_late_layer_is_not_starved_when_the_wire_is_full, test_layer_stats_carry_contributor_side_loss_in_total, test_light_snapshot_is_sent_whole, test_more_than_the_named_layer_cap_reports_unsent_layers_and_stays_at_caps, test_redistribution_never_exceeds_the_mark_cap_or_a_layers_own_rows, test_routes_stay_whole_within_the_layer_share, test_unplaced_counts_ride_in_the_notice_only_when_nonzero, test_unused_route_allowance_is_redistributed_to_layers_with_unsent_points.

Final result: Ran 75 tests in 0.880s; FAILED (errors=11); process exit 1.

### tests/legacy/test_e1_incidents.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_default_on_admission_line_and_honest_readiness, test_operator_opt_out_policy_fault_and_non_server_never_report_ready.

Final result: Ran 50 tests in 1.946s; FAILED (errors=2); process exit 1.

### tests/legacy/test_ecology_module.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_migration_uses_existing_module_lifecycle_after_observation_admission, test_start_passes_loaded_settings_world_and_fresh_session, test_enabled_settings_admit_the_module_without_closing_collection, test_tick_uses_engine_milliseconds_and_stop_stops.

Final result: Ran 10 tests in 0.285s; FAILED (failures=2, errors=2); process exit 1.

### tests/legacy/test_ecology_rules.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_all_rejected_is_atomic_and_success_applies_cooldown_hysteresis, test_commit_requires_current_authority_and_capability, test_directive_budget_no_duplication_and_exhaustion, test_full_assignment_table_requires_confirmed_retirement, test_hints_never_create_observations_and_only_annotate_matching_observed_zone, test_infected_require_their_native_navigation_capability, test_int32_cursor_normalized_before_addition, test_invalid_identity_time_budget_and_duplicate_data_roll_back, test_nested_lists_and_identifiers_are_bounded, test_new_proposals_reserve_remaining_assignment_slots_within_batch, test_null_future_entries_reject_without_mutation, test_old_context_directive_cannot_commit_into_new_context, test_operator_limits_have_hard_ceilings, test_partial_receipt_retains_confirmed_assignment_and_cursor, test_partial_second_confirmation_retains_its_cursor_and_rejects_replay, test_receipt_arrays_and_null_entries_fail_closed, test_receipt_is_detached_and_every_identity_field_is_bound, test_replayed_commit_does_not_mutate_state, test_retirement_cannot_free_slots_by_absence_or_elapsed_time_alone, test_retirement_generation_replay_and_clock_rollback_fail_closed, test_retirement_is_atomic_bounded_and_requires_authoritative_provider, test_retirement_never_bypasses_cooldown_or_zero_duration_tick_guard, test_retirement_rejects_wrong_generation_context_stale_or_unconfirmed, test_round_robin_fairness_across_actor_and_zone_budgets, test_server_authority_and_native_provider_capability_are_required, test_source_has_no_engine_mutation_or_production_hook, test_species_resource_and_population_eligibility_are_enforced, test_stale_unknown_depleted_expired_and_unreachable_observations_are_excluded, test_swapped_or_bad_late_receipt_is_atomic_even_when_earlier_accepted, test_world_session_and_observation_clock_cannot_regress, test_wrapped_deadlines_cannot_commit, test_zero_duration_cannot_propose_same_actor_twice_at_same_tick, test_zone_uniqueness_is_batch_local_not_native_occupancy.

Final result: Ran 33 tests in 0.089s; FAILED (errors=33); process exit 1.

### tests/legacy/test_ecology_runtime.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_a_cohort_smaller_than_the_window_is_sampled_whole_every_tick, test_begin_canonicalizes_world_before_token_and_native_world_checks, test_clock_world_or_authority_failure_stops_before_native_work, test_cycle_without_a_due_checkpoint_never_spends_a_save_tick, test_each_tick_samples_a_bounded_window_and_the_cursor_covers_every_entry, test_empty_live_tick_consumes_policy_but_never_commits_unsupported_provider, test_invalid_start_closes_prestart_cohort_without_stopping_live_duplicate, test_mixed_case_native_world_does_not_stop_live_observation, test_one_stage_per_module_tick_never_a_full_pass, test_periodic_failed_checkpoint_stops_future_work, test_periodic_store_fault_releases_all_live_bindings, test_probe_stage_spans_ticks_until_the_slices_finish_and_only_then_counts, test_scheduler_batch_never_exceeds_the_window, test_shutdown_closes_registration_and_flushes_once, test_startup_clock_admission_precedes_store_and_settings_io, test_stopped_service_never_probes_or_saves, test_subinterval_clock_rollback_stops_before_work, test_window_follows_a_configured_slice_and_a_shrunk_registry, test_a_native_path_probe_is_charged_so_a_slice_cannot_chain_probes, test_cursor_normalizes_after_removal_and_empty_cohorts, test_distant_pairs_do_no_resource_capacity_or_id_work, test_failed_queries_still_spend_the_per_tick_budget, test_invalid_empty_distant_or_dead_entries_cannot_issue_path, test_near_pairs_use_cached_ids_without_token_validation, test_one_slice_never_examines_more_pairs_than_the_unit_budget, test_pair_budget_resumes_exactly_and_covers_full_scattered_cohort, test_queries_bounded_and_zones_reserved_across_ticks, test_probe_yields_to_unit_budget_and_resumes_at_retained_cursor, test_checkpoint_of_another_world_neither_blocks_nor_is_touched, test_corrupt_oversized_wrong_world_and_replayed_session_are_preserved, test_empty_leftover_pending_is_archived_before_primary_or_fresh_admission, test_empty_store_initializes_all_required_fields, test_fresh_session_carries_only_diagnostic_counters, test_leftover_pending_loads_primary_and_reports_one_named_quarantine, test_leftover_pending_without_primary_takes_fresh_path_after_quarantine, test_pending_quarantine_does_not_admit_corrupt_primary, test_pending_quarantine_failures_refuse_preserving_source_without_loading_primary.

Final result: Ran 70 tests in 2.554s; FAILED (failures=19, errors=18); process exit 1.

### tests/legacy/test_event_director.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_blank_identity_and_unsupported_initial_namespace_are_rejected, test_deadline_must_fit_the_bounded_session_clock, test_definition_is_snapshotted_and_duplicate_proposal_is_rejected, test_discovery_does_not_enroll_players_or_skip_lifecycle, test_dto_members_do_not_shadow_native_world_type, test_finite_reservations_release_only_after_terminal_transition, test_invalid_definition_fields_never_reserve_capacity, test_live_capacity_is_bounded_while_empty_session_history_is_compacted, test_malformed_state_is_rejected_without_traversing_oversized_arrays, test_observed_completion_rejects_replay_and_double_completion, test_opt_out_and_deadline_are_explicit_without_inventory_operations, test_partial_progress_requires_contiguous_observation_sequence, test_pruned_floor_preserves_ids_and_old_context_cannot_replay, test_restart_cancels_live_records_and_rejects_session_reuse, test_revision_exhaustion_reserves_a_terminal_transition, test_rewards_remain_blocked_without_grant_adapter, test_server_authority_clock_and_stale_revision_fail_closed, test_source_has_no_gameplay_hooks_or_native_grant_operations, test_unobserved_or_unenrolled_progress_never_mutates_state.

Final result: Ran 19 tests in 0.192s; FAILED (failures=19); process exit 1.

### tests/legacy/test_event_integration.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_100_module_starts_announce_roster_with_bounded_retention, test_busy_stop_disables_admission_and_retains_until_unwound_and_gone, test_cleanup_quarantines_after_bounded_retries_and_fresh_start_rechecks_owner, test_failed_journal_never_reports_closed_even_if_provider_reports_gone, test_invalid_clock_keeps_original_session_for_later_cleanup, test_missing_game_retains_without_calling_native_provider_then_recovers, test_new_registry_instance_cannot_abandon_previous_cleanup_owner, test_observer_release_refusal_is_retained_like_ai_absence, test_quarantined_cleanup_completes_when_slow_confirmation_arrives, test_stop_request_return_value_and_status_require_confirmed_cleanup, test_unconfirmed_ai_stop_retains_owner_and_retries_without_new_groups, test_absent_game_or_client_start_has_no_side_effects, test_absent_provider_adds_no_ai_mission_and_no_code_seven_line, test_admitted_line_reports_the_reward_pool_state_accurately, test_ai_encounter_is_offered_only_when_the_provider_is_ready, test_empty_or_wrong_world_roster_still_exposes_honest_browse, test_failed_runtime_start_is_cleaned_and_can_retry, test_invalid_clock_stops_before_observation_and_can_restart, test_late_admission_is_logged_once_per_mission, test_not_admitted_line_names_the_mission_and_the_code, test_partial_rpc_start_failure_cleans_callback_and_runtime_then_retries, test_registry_repeated_registration_keeps_one_event_and_group, test_repeated_start_cleans_old_session_before_new_callback, test_restart_after_disabled_configuration_cleans_existing_session, test_roster_build_never_hard_codes_the_ai_flag, test_start_admission_is_not_reported_as_late, test_start_attaches_rpc_after_runtime_and_site_roster, test_start_summary_prints_the_admitted_count_plainly, test_stop_detaches_transport_before_runtime_and_is_idempotent, test_stop_without_game_detaches_callback_and_attempts_runtime_cleanup, test_stopping_unstarted_instance_preserves_live_singleton, test_tick_revokes_dead_rpc_peer_before_runtime_observes.

Final result: Ran 32 tests in 0.776s; FAILED (failures=32); process exit 1.

### tests/legacy/test_event_police.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_absent_native_stock_never_mints_replacement, test_disabled_gate_and_unreviewed_operator_changes_never_spawn, test_empty_native_cargo_stays_without_deletion_or_refill, test_existing_ce_binds_three_distinct_items_from_same_barrel, test_existing_stock_is_not_repositioned_to_navmesh, test_infected_clear_binds_through_dense_town_scenery, test_infected_clear_keeps_a_density_scaled_query_overflow_refusal, test_infected_clear_searches_the_ground_below_the_source_out_to_60_m, test_infected_clear_still_refuses_beyond_60_m_and_logs_no_candidate_once, test_infected_clear_with_unreadable_ground_refuses_with_a_reason_before_any_scan, test_infected_late_population_chooses_nearest_and_stable_id_tie, test_missing_stock_retries_keep_diagnostics_bounded, test_native_barrel_binding_does_not_write_inventory_state, test_native_stock_binding_does_not_write_grant_journal, test_partial_native_cargo_never_refills, test_police_objectives_require_carriage_or_attributed_delivery, test_registration_capacity_retry_and_missing_items_never_spawn_a_second_barrel, test_shared_budget_refuses_scan_and_allows_later_retry, test_stock_outside_site_radius_refuses_without_spending, test_two_sites_bind_separate_native_stock_without_spending_cache_pool, test_blocked_announcement_is_not_a_permanent_session_record, test_five_site_retry_is_one_pair_per_five_seconds_and_no_terminal_repeat.

Final result: Ran 22 tests in 0.225s; FAILED (failures=22); process exit 1.

### tests/legacy/test_event_runtime.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_explicit_disable_and_existing_invalid_config_never_overwritten, test_missing_config_generates_enabled_template_once, test_commit_drift_since_load_is_not_ignored, test_corrupt_latest_image_commit_and_missing_intent_refuse, test_drift_since_load_refuses_write_and_preserves_evidence, test_each_interrupted_write_refuses_latest_not_fallback, test_empty_roundtrip_and_deep_clone, test_legacy_image_loads_with_zero_retention_floors_without_reset, test_retention_is_bounded_and_deletion_failure_faults, test_revision_replay_and_foreign_future_intent_refused, test_store_quota_checked_before_any_intent, test_unsupported_schema_has_explicit_admission_error_and_preserves_bytes, test_wrong_world_and_noncanonical_or_unrelated_names_refuse, test_clock_context_uses_current_native_world_and_monotonic_session_seconds, test_disconnect_hook_preserves_native_chain_and_server_attribution, test_invalid_runtime_clock_stops_module_instead_of_silent_live_status, test_100_restarts_with_full_roster_keep_monotonic_bounded_journal, test_ai_cleanup_reservations_count_until_gone, test_ai_start_intent_is_durable_and_failure_never_claims_cleanup, test_clock_rollback_world_session_and_disabled_preference_refuse, test_corrupt_store_blocks_start_and_cannot_fall_back_to_fresh_state, test_enabled_preference_and_invalid_settings_fail_closed, test_expiry_cancel_and_cleanup_are_idempotent, test_failed_restart_uses_loaded_session_for_confirmed_cleanup, test_malformed_or_duplicate_site_configuration_refused, test_missing_observer_or_ai_disables_without_event_or_spawn, test_mission_world_numbers_and_rewards_are_validated, test_observation_completes_once_with_no_rewards_or_spawning, test_opt_out_disconnect_and_new_connection_need_explicit_join, test_optout_resets_provider_dwell_before_rejoin, test_participation_requires_native_identity_not_client_id, test_periodic_dead_handle_disconnects_without_rebinding_respawn, test_persistence_failure_prevents_publication_and_provider_start, test_post_start_save_failure_requests_owned_ai_stop_without_closed_claim, test_provider_cannot_mutate_owned_runtime_record, test_provider_reentrant_mutation_is_rejected, test_restart_cancels_without_respawn_and_requires_cleanup_confirmation, test_restart_closes_full_retention_before_first_announcement, test_retention_never_discards_unclosed_native_intent, test_roster_contains_all_four_noncombat_families_and_optional_ai, test_run_definition_mismatch_refused_before_start, test_shutdown_cancels_durably_even_when_preference_toggled_off, test_state_and_roster_snapshots_are_immutable_to_callers, test_terminal_cleanup_reclaims_subscription_capacity, test_wrong_session_lease_participant_and_replay_do_not_progress, test_dead_or_deleted_player_never_observed_and_optout_resets_dwell, test_delivery_and_static_salvage_use_distinct_locations, test_dwell_is_continuous_bounded_samples_and_handle_specific, test_exact_existing_handle_and_custody_required, test_foreign_lease_cannot_observe_and_cleanup_never_deletes_item, test_invalid_target_kind_ruin_owner_and_source_not_admitted, test_lease_without_session_separator_is_not_observed, test_same_target_cannot_be_registered_or_leased_twice.

Final result: Ran 56 tests in 0.433s; FAILED (failures=53); process exit 1.

### tests/legacy/test_event_sites.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_a_new_reason_for_the_same_mission_is_reported_again, test_delivery_destination_failures_name_the_container_not_the_item, test_infected_clear_retries_zero_then_accepts_multiple_candidates, test_more_than_one_candidate_is_reported_as_ambiguous, test_query_overflow_is_reported_once_however_often_it_is_retried, test_success_and_unrelated_refusals_log_nothing, test_the_report_set_is_bounded, test_zero_candidates_are_reported_as_no_candidate, test_absent_stock_never_retries_into_a_duplicate, test_discard_never_deletes_borrowed_native_stock, test_empty_native_cache_is_never_deleted_or_refilled, test_existing_cache_is_bound_by_same_handle_without_minting, test_existing_stock_does_not_depend_on_spawn_terrain, test_gate_server_and_mission_checks_precede_any_journal_or_spawn, test_physical_stock_needs_no_reward_journal, test_closed_gate_leaves_the_stock_template_and_open_gate_merges_in_memory_only, test_open_gate_merges_after_the_template_write_and_keeps_an_invalid_file_refused, test_bind_refuses_without_site_gate_or_with_physical_stock_opt_out, test_cache_missions_fail_closed_with_an_already_full_target_table, test_reach_the_site_needs_dwell_inside_the_reviewed_radius, test_recover_the_cache_binds_once_and_completes_only_when_carried, test_existing_sites_and_uncurated_rosters_are_unchanged, test_gate_closed_builds_no_curated_roster_even_with_events_admitted, test_reward_cache_is_valid_only_for_recovery_missions, test_roster_is_reach_the_site_and_recover_the_cache_only, test_sites_merge_is_bounded_idempotent_and_never_overrides_operator_sites, test_three_reviewed_unsurveyed_chernarus_sites_with_distinct_ids, test_commit_journals_before_returning_and_spends_the_site, test_foreign_or_unreadable_directory_fails_closed, test_invalid_site_ids_and_pools_are_refused, test_journal_failure_returns_no_plan_and_still_spends_the_site, test_latched_fault_blocks_every_later_grant_even_after_writes_recover, test_pool_is_finite_and_cap_is_per_boot, test_process_holder_creates_one_ledger_with_the_v1_pool, test_restart_starts_a_new_boot_prunes_old_files_and_never_replays_a_grant, test_v1_pool_is_finite_vanilla_and_valid, test_absent_marker_is_admitted_by_default_and_logs_once, test_disable_marker_is_not_admitted_and_logs_pending_once, test_marker_text_is_the_documented_opt_out_path, test_qualified_stays_false_and_marker_is_server_only_and_cached_once, test_cache_comment_does_not_overclaim_persistence, test_cache_creation_uses_only_the_verified_native_calls.

Final result: Ran 49 tests in 0.387s; FAILED (failures=42); process exit 1.

### tests/legacy/test_event_transport.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_any_session_or_request_id_is_refused_without_consumption, test_clock_rollback_resets_tracked_admission_baselines, test_deleted_native_identity_is_pruned_before_next_authentication, test_disabled_or_faulted_runtime_returns_empty_disabled_view, test_disconnect_tick_releases_peer_and_membership, test_durable_ids_beyond_32_are_never_projected_as_quest_slots, test_first_browse_is_empty_disabled_and_natively_targeted, test_global_budget_and_peer_capacity_are_independently_bounded, test_join_leave_and_repeats_are_refused_without_runtime_writes, test_malformed_fields_bounded_before_consumption, test_new_peer_during_nonfinite_clock_recovers_after_multiple_rate_windows, test_public_projection_has_no_accounts_private_positions_items_or_internal_refs, test_rate_limits_reject_without_consuming_and_clock_rollback_recovers, test_reconnect_discards_old_peer_admission_state, test_reconnect_new_handle_gets_new_wire_session_but_cannot_rejoin, test_refusal_projection_never_reads_runtime_snapshot, test_refusal_rate_limit_bounds_replies_without_any_quest_writes, test_refusals_sequence_replies_without_acknowledging_quest_intent, test_retired_payload_unread_and_other_rpc_or_missing_context_ignored, test_same_id_different_payload_never_replays_success, test_sender_player_identity_mismatch_drops_before_read, test_start_stop_register_exact_native_callback_once, test_unconscious_join_refused_without_side_effect.

Final result: Ran 23 tests in 0.181s; FAILED (failures=23); process exit 1.

### tests/legacy/test_event_ui.py — HARNESS_ROT

Mixed director translator failures and an exact input-action set that omits the current earplug and look-ping bindings.

Failing methods: test_all_legacy_operations_refused_and_public_state_empty, test_compatibility_lifecycle_and_frames_do_no_native_work, test_old_or_malformed_snapshots_never_publish_or_deserialize, test_retired_input_and_layout_removed_without_affecting_other_bindings.

Final result: Ran 6 tests in 0.029s; FAILED (failures=4); process exit 1.

### tests/legacy/test_expansion_ai_adapter.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_clock_rollback_quarantines_without_releasing_or_deleting, test_death_receipts_are_owned_once_and_attributed_without_target_positions, test_failed_journal_capacity_prune_does_not_publish_reservation, test_full_nonprunable_journal_rejects_without_publishing_reservation, test_gone_remains_true_when_cleanup_polls_after_same_tick_prune, test_history_recycles_clean_retirements_past_cap_without_entity_work, test_journal_prune_persists_shrink_and_failed_write_retains_runtime_history, test_null_handle_without_deletion_callback_is_not_gone, test_observer_reentry_cannot_repeat_native_creation, test_observer_veto_unknown_and_waiting_prevent_spawn_and_delete, test_partial_spawn_failure_keeps_confirmed_actor_and_reservations, test_pruned_id_cap_refusal_is_logged_once, test_pruned_id_memory_is_bounded_without_forgetting_cleanup_or_identity, test_pruned_lease_id_cannot_reissue_kill_receipt_identity, test_pruning_skips_open_retiring_ambiguous_and_faulted_leases, test_real_factory_group_waypoints_and_fairness_setters, test_reconciliation_does_not_make_old_open_intents_prunable, test_released_flag_alone_cannot_discard_ambiguous_actors, test_replay_after_world_or_capability_loss_does_not_claim_ready, test_reservations_include_retiring_work_and_history_is_not_reused, test_restart_at_cap_prunes_only_oldest_explicitly_confirmed_row, test_restart_at_hard_cap_is_bounded_and_duplicate_checks_precede_pruning, test_restart_cannot_promote_inconsistent_open_pruning_markers, test_restart_with_retained_fault_can_recycle_more_than_runtime_cap, test_start_arms_encounters_without_profile_or_receipt_and_logs_readiness_when_settled, test_start_callback_reentry_cannot_duplicate_identity_or_reservations, test_start_is_idempotent_and_binds_session_anchor_and_cap, test_stop_request_is_not_observed_absence_or_released_budget, test_tick_work_and_client_authority_are_bounded, test_timeout_retires_only_after_unobserved_gate, test_uncertain_intent_failure_retains_reserved_budget, test_uncertain_journal_intent_write_keeps_reservation_and_consumes_id, test_unconfirmed_receipt_closure_is_not_prunable, test_failed_stage_preserves_committed_bytes_and_retains_guard, test_guard_cleanup_failure_never_claims_committed_success, test_interrupted_publication_blocks_load_and_subsequent_writes, test_successful_write_verifies_staged_snapshot_and_clears_guard.

Final result: Ran 58 tests in 3.246s; FAILED (errors=37); process exit 1.

### tests/legacy/test_expansion_ai_encounters.py — HARNESS_ROT

Shipped-route case fails constructing HCXAISitePolicy through the Python port; source JSON is successfully decoded before that failure.

Failing methods: test_shipped_routes_bind_each_police_anchor_to_its_village_patrol.

Final result: Ran 14 tests in 0.710s; FAILED (errors=1); process exit 1.

### tests/legacy/test_expansion_ai_event_reach.py — STALE_EXPECTATION

Expanded patrol catalog: two additional gap-coverage routes start near event anchors. Runtime spawn admission rejects nearby observers; the original reaching police routes remain. The test unnecessarily requires every reaching route to start at least MinPlayerDistance + 25 away.

Failing methods: test_a_reaching_patrol_starts_beyond_the_player_spawn_distance.

Final result: Ran 3 tests in 0.026s; FAILED (failures=2); process exit 1.

### tests/legacy/test_expansion_ai_live_map.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_report_counts_groups_and_units_by_source_and_is_rate_limited, test_report_prints_zero_when_no_ai_is_alive.

Final result: Ran 9 tests in 0.112s; FAILED (errors=2); process exit 1.

### tests/legacy/test_expansion_ai_sites.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_loadout_provisioning_visits_beyond_64_catalog_rows, test_missing_loadouts_are_provisioned_once_and_operator_files_are_never_overwritten, test_policy_drift_names_a_stale_operator_policy_without_replacing_it, test_accumulated_site_budget_bounds_retries_on_all_unreachable_targets, test_cached_holdout_success_rebuilds_the_snapped_patrol_points, test_cached_outdoor_success_rebuilds_intermediate_points_after_sampling, test_chain_budget_refuses_moving_forever, test_closest_diagnostic_survives_a_later_retreat_and_stall, test_closest_diagnostic_uses_a_returned_end_even_when_it_retreats, test_closing_near_miss_keeps_stepping_and_closes_the_loop, test_closing_near_miss_never_moves_the_qualified_first_point, test_closing_refusal_uses_once_and_discards_partial_closing_geometry, test_disconnected_route_refusal_reports_original_leg_and_closest_end, test_false_findpath_result_cannot_qualify_even_with_output_points, test_holdout_partial_path_is_refused_on_first_call, test_holdout_refusal_never_samples_outdoors, test_holdout_skip_keeps_two_and_never_chains_a_far_partial_path, test_isolated_kept_pair_restarts_from_a_later_point_before_any_outdoor_retry, test_loop_closure_is_qualified_without_duplicate_first_patrol_point, test_minimum_counts_authored_points_not_continuation_endpoints, test_new_version_cached_refusal_still_prevents_retry, test_no_outdoor_ground_refuses_at_once_without_a_retry_chain, test_no_path_and_detour_refusals_skip_without_leaking_tentative_points, test_observed_holdout_mogilevka_near_miss_snaps_target_one, test_observed_mil_tisy_stall_skips_target_one, test_observed_police_berezino_isolated_kept_pair_requalifies_on_outdoor_ground, test_observed_police_berezino_stall_skips_target_two, test_observed_police_chernogorsk_isolated_kept_pair_requalifies_on_outdoor_ground, test_observed_police_chernogorsk_stall_skips_target_two, test_observed_police_elektrozavodsk_isolated_kept_pair_requalifies_on_outdoor_ground, test_observed_police_elektrozavodsk_stall_skips_target_one, test_observed_scav_novodmitrovsk_isolated_kept_pair_requalifies_on_outdoor_ground, test_observed_scav_novodmitrovsk_stall_skips_target_two, test_observed_scav_vybor_near_miss_snaps_target_two, test_outdoor_retry_happens_once_and_its_refusal_is_final, test_outdoor_retry_shares_the_site_budget, test_oversized_authored_array_is_refused_before_any_path_call, test_partial_calls_chain_from_actual_end_and_preserve_patrol_points, test_points_without_outdoor_ground_keep_their_navmesh_sample_in_the_retry, test_site_budget_refuses_before_findpath_call_97_even_for_closure, test_snap_keeps_the_current_path_end_not_an_earlier_closer_attempt, test_snap_that_never_left_the_last_kept_point_is_skipped_not_duplicated, test_summed_detour_refuses_short_final_call, test_unreachable_first_point_is_dropped_and_later_points_are_retried, test_unsnapped_tolerance_keeps_authored_target_and_next_start, test_admission_reports_the_first_unmet_live_check, test_cache_refills_only_after_looting_and_the_cooldown_with_nobody_near, test_cache_seeds_once_and_a_restart_never_reseeds, test_chain_detour_budget_is_for_the_entire_original_leg, test_chain_refuses_disconnected_stalled_and_exhausted_paths, test_despawn_waits_for_combat_to_end, test_duplicate_site_ids_are_refused, test_encounter_binds_only_a_qualified_owned_unbound_patrol_inside_its_activation_radius, test_encounter_session_token_is_per_process_and_refuses_unreconciled_sessions, test_every_member_spawn_point_needs_the_same_distance_and_sight_rules, test_holdout_needs_a_vanilla_cache_with_a_small_finite_table, test_holdout_route_text_covers_the_house_and_its_points, test_no_kind_can_reuse_success_without_regenerating_snaps_and_skips, test_outdoor_partial_path_continues_but_holdout_stays_strict, test_policy_refuses_budgets_above_the_ceiling_and_a_non_native_observer, test_policy_rejects_empty_perception_spawn_window, test_route_gap_is_the_nearest_qualified_patrol_point_to_the_anchor, test_route_legs_must_be_navmesh_paths_that_reach_the_waypoint, test_route_text_changes_with_build_and_points, test_route_version_invalidates_all_old_successes_and_refusals, test_shipped_policy_is_admissible_and_has_every_kind, test_site_ai_aims_worse_and_notices_less_than_stock_expansion, test_site_refuses_activation_inside_the_no_spawn_ring_and_long_legs, test_site_refuses_unknown_kind_faction_size_and_foreign_loadout, test_snap_boundaries_preserve_original_tolerance_and_holdout_strictness, test_snap_keeps_a_point_only_beyond_half_a_metre_of_the_last_kept_point, test_spawn_needs_budget_distance_and_no_line_of_sight, test_w5_group_scaling_rounds_and_caps_authored_counts, test_shipped_legacy_policy_fixture_upgrades_new_fields_and_loadouts_match, test_outdoor_sample_refuses_roofs_and_takes_the_nearest_ground_probe, test_outdoor_sample_takes_ground_at_the_terrain_point_first, test_outdoor_ground_filter_excludes_interiors_and_findpath_keeps_the_expansion_filter.

Final result: Ran 100 tests in 2.586s; FAILED (failures=4, errors=74); process exit 1.

### tests/legacy/test_fuel_siphon_behavior.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_client_never_probes_the_marker_or_the_gate, test_default_without_a_marker_is_open_and_logged_experimental, test_disable_marker_closes_the_fuel_admission, test_disable_marker_is_probed_once_per_process_whatever_it_answers, test_missing_game_is_closed, test_server_gate_truth_table, test_cancel_after_a_flushed_step_does_not_replay_it, test_cancel_with_nothing_pending_changes_nothing, test_invalidation_at_a_step_boundary_debits_nothing, test_invalidation_before_cancel_debits_nothing, test_receipt_mismatch_then_cancel_does_not_flush_again, test_repeated_cancel_is_idempotent, test_voluntary_cancel_flushes_exactly_the_pending_partial_step, test_client_cancel_flushes_prediction_only, test_client_invalid_state_is_still_not_a_mutation, test_client_only_advances_progress_and_never_mutates, test_client_prediction_is_capped_by_the_session, test_random_sessions_never_credit_more_than_the_exact_tank_loss, test_action_condition_client_needs_allowed_only_server_needs_gate, test_action_is_registered_after_super_on_the_native_registries, test_baseline_is_allowed, test_each_single_failure_refuses, test_empty_vessel_accepts_any_existing_liquid_type_and_gasoline_partial, test_null_arguments_refuse, test_reach_boundary_is_exclusive_and_squared, test_selection_scan_refuses_lists_over_32_entries, test_tank_liters_is_capacity_times_fraction_in_binary32, test_a_leak_that_removes_nothing_credits_nothing_and_stops, test_between_steps_nothing_is_mutated, test_completion_branch_flushes_and_reports_once, test_credit_is_below_what_the_tank_actually_lost, test_debit_is_step_milliliters_times_0_001_in_liters, test_each_step_is_exactly_one_leak_and_one_fill, test_garbage_tank_readback_stops_the_session_without_mutation, test_gate_closed_never_leaks_or_fills, test_receipt_mismatch_stops_without_retry_or_refund, test_remaining_session_shrinks_by_what_was_credited, test_server_progress_advances_by_credit_not_by_prediction, test_session_completion_never_steps_past_the_session, test_session_ends_when_the_tank_is_empty, test_session_ends_when_the_vessel_is_full, test_step_never_exceeds_the_remaining_session, test_step_never_exceeds_the_session_even_if_the_tank_or_vessel_grows_mid_session, test_step_uses_the_fresh_free_space_not_the_session_snapshot, test_step_uses_the_fresh_tank_not_the_session_snapshot, test_stopped_session_finishes_without_further_mutation, test_execute_and_cancel_without_player_are_errors_without_effect, test_setup_reuses_component_only_with_fresh_action_data, test_setup_session_is_tank_or_free_space_and_throughput_scales_rate, test_setup_without_target_or_vessel_leaves_a_dead_session, test_production_file_translates_and_world_builds.

Final result: Ran 56 tests in 5.998s; FAILED (errors=112); process exit 1.

### tests/legacy/test_group_batching.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_expired_marker_never_blocks_a_new_marker_before_the_flush, test_disconnect_flushes_pending_discovery_once, test_discovery_never_queues_the_same_visit_twice, test_discovery_queues_visits_without_clone_or_commit, test_flush_limit_backs_off_discovery_sixty_seconds, test_idle_batch_window_writes_nothing, test_marker_expiry_waits_for_the_batch_and_touches_once, test_stop_flushes_pending_discovery_before_teardown, test_stop_without_pending_discovery_writes_nothing, test_tick_commits_discovery_at_most_once_per_sixty_seconds, test_save_serialises_once_and_keeps_live_invitations.

Final result: Ran 11 tests in 0.050s; FAILED (errors=11); process exit 1.

### tests/legacy/test_group_client.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_changed_session_never_replays, test_invalid_handshakes, test_old_sync_after_completed_mutation, test_pending_survives_sync, test_private_frozen_retry, test_rate_reply_and_zero_floor_do_not_acknowledge_pending, test_recovery_can_lower_unconfirmed_client_counter, test_recovery_counter, test_recovery_rejects_colliding_ticket_and_confirmed_floor_rollback, test_retry_budget_retains_uncertainty, test_tick_rollback_executes_recover_without_losing_uncertainty, test_ticket_exhaustion_fails_closed_without_resetting_budget, test_unknown_session_quarantines_later_old_session_frames, test_unticketed_session_frames_cannot_replace_pending.

Final result: Ran 14 tests in 0.065s; FAILED (errors=14); process exit 1.

### tests/legacy/test_group_native_checks.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_fixture_calls_do_not_bind_native_step_attribute_constructor, test_opt_in_and_side_effect_contract, test_rejected_mutation_cannot_print_completion, test_step_budget_rejects_before_apply, test_success_executes_all_thirteen_ops_before_completion, test_unexpected_result_cannot_print_completion, test_wire_version_pin_cannot_silently_drift.

Final result: Ran 7 tests in 0.029s; FAILED (errors=7); process exit 1.

### tests/legacy/test_group_null_context.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_null_context_returns_one_invalid_refusal_without_mutating_state.

Final result: Ran 1 test in 0.006s; FAILED (errors=1); process exit 1.

### tests/legacy/test_group_persistence.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_actual_store_roundtrip_retains_acl_expiry_watermark_not_invites, test_corrupt_highest_image_or_receipt_is_rejected_without_fallback, test_partial_highest_transaction_never_restores_an_older_acl, test_preexisting_zero_watermark_migrates_without_resetting_acl, test_real_start_path_reopens_then_rejects_rollback_before_serving_peers, test_save_never_swaps_ref_arrays_the_native_compiler_rejects, test_unrecognized_paths_and_enumeration_over_budget_fail_closed.

Final result: Ran 7 tests in 0.034s; FAILED (errors=7); process exit 1.

### tests/legacy/test_group_round2.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_commit_evicts_offline_journal_before_byte_cap_write, test_discovery_evicts_inactive_when_explorer_slots_full, test_eight_members_eventually_get_rays_with_budget_seven, test_los_cache_is_bounded_under_many_sessions, test_negative_cache_expires_and_reconnect_invalidates_verdict, test_rotation_does_not_alias_two_second_position_cadence, test_M51_client_rejects_overfull_places, test_M52_client_rejects_invalid_role, test_legacy_explorer_migrates_ids_and_clears_metadata, test_native_names_truncates_with_log_and_bounded_reads, test_pin_reuses_texture_until_texture_changes, test_M03_officer_cannot_transfer, test_M04_officer_cannot_disband, test_M05_kicked_officer_rejoins_as_member, test_M06_departed_officer_rejoins_as_member, test_M12_owner_role_request_is_invalid, test_M13_nonmember_officer_journal_rejected, test_M14_owner_officer_journal_rejected, test_M15_member_inviter_journal_rejected, test_M18_explorer_admission_limit, test_M19_disabled_discovery_records_nothing, test_M21_discovery_never_shares_other_group, test_M23_union_of_member_discoveries_is_bounded, test_M24_disabled_discovery_lists_nothing, test_M56_radius_validation, test_M57_overfull_explorer_journal_rejected, test_M58_duplicate_journal_visit_rejected, test_M58_duplicate_legacy_visit_rejected, test_default_ray_budget_covers_eight, test_journal_stores_ids_and_resolves_current_catalog, test_wire_three, test_M30_unconscious_source_never_visible, test_M31_tick_resets_budget_and_rotates_start, test_M41_dead_peer_receives_no_places, test_M42_positions_never_include_places, test_M43_discovery_skips_dead_and_unconscious, test_M44_discovery_examined_bound, test_M61_snapshot_roster_roles, test_M62_start_refuses_bad_catalog, test_already_known_discovery_does_not_clone, test_equipment_once_per_peer_each_tick, test_eviction_preserves_grouped_and_online_explorers, test_far_discovery_does_no_clone_or_record, test_full_round_prevents_duplicate_positions, test_limit_discovery_backs_off_sixty_seconds, test_pair_los_cache_expires_and_is_bounded.

Final result: Ran 54 tests in 0.247s; FAILED (errors=46); process exit 1.

### tests/legacy/test_group_rpc.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_client_accepts_full_range_member_timestamp, test_clock_rollback_stops_before_mutation_or_disk_write, test_commit_reply_replay_and_disk_watermark_share_fresh_server_clock, test_mismatched_replay_and_prior_session_never_recommit_or_poison_receipt.

Final result: Ran 4 tests in 0.022s; FAILED (errors=4); process exit 1.

### tests/legacy/test_group_server.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_budget_rejection_has_no_store_write_or_state_replacement, test_caps_invalid_numbers_and_retention_are_enforced, test_commit_persists_authoritative_clock_and_refuses_rollback, test_corrupt_invitation_null_or_cross_group_authority_is_refused, test_corrupt_null_group_or_duplicate_entity_id_is_refused, test_create_invite_accept_and_account_membership, test_creating_own_group_cancels_pending_other_group_invitations, test_decline_expiry_outsider_and_duplicate_invites, test_disabled_policy_and_invalid_version_never_mutate, test_every_snapshot_kind_projects_floor_without_consuming_or_resetting_it, test_highest_revision_torn_write_or_length_hash_drift_never_rewinds, test_immutable_store_reads_are_bounded_and_latest_corruption_has_no_fallback, test_invitation_candidate_projection_never_reads_or_exposes_life_state, test_invitation_validation_rejects_stale_group_name, test_invite_expiry_reaches_max_and_overflow_is_rejected_before_mutation, test_leave_kick_owner_transfer_and_disband, test_marker_deadline_boundary_and_forever_at_final_second, test_marker_notes_crud_owner_creator_permissions_and_revision, test_marker_update_rejects_explicit_ttl_and_never_assigns_policy_to_forever_marker, test_marker_updates_preserve_original_deadline_as_server_time_advances, test_member_cannot_kick_transfer_disband_rename_or_invite, test_mismatched_replay_cannot_replace_cached_committed_result, test_missing_group_preferences_and_failed_start_are_reported, test_mutation_floor_bounds_and_invalid_internal_counter_never_emits, test_native_member_projection_never_publishes_dead_offline_or_forbidden_position, test_native_rpc_authority_targeting_and_lifecycle_are_explicit, test_offline_membership_capacity_is_not_concurrent_player_limit, test_other_member_cannot_edit_someone_elses_marker, test_persisted_acl_rejects_duplicate_members_or_missing_owner, test_rename_refreshes_pending_invitation_names_only_for_its_group, test_reply_projects_actual_floor_for_counterahead_conflict_and_all_errors, test_request_rate_clock_rejects_rollback_nan_and_infinity_without_admission, test_restart_clock_accepts_legacy_zero_but_rejects_rollback_of_commit, test_retention_increase_skips_absent_old_triple_but_delete_failure_faults, test_rule_expressions_keep_small_native_compiler_complexity_budget, test_settings_boundaries_finite_values_and_cross_field_staleness, test_sync_floor_is_observation_not_ack_and_later_reply_does_not_rewrite_it, test_validated_settings_reject_invalid_bounds, test_wire3_floor_schema_defaults_and_durable_schema_stays1, test_world_identity_is_required_and_cross_map_never_reused, test_additive_legacy_roles_and_transfer_cleanup, test_officer_matrix_and_owner_only_role_assignment, test_radio_matching_requires_a_shared_actual_frequency, test_required_native_and_privacy_wiring, test_visibility_settings_are_supported_and_bounded, test_visit_requires_actual_proximity_and_is_bounded_persistent_with_privacy_opt_out, test_one_bounded_discovery_pass_observes_six_players_with_one_commit, test_roles_visits_and_legacy_defaults_reopen_through_actual_journal, test_group_map_menu_closes_when_map_ownership_is_lost, test_member_projection_applies_real_radio_and_los_gates, test_client_can_send_role_assignment_without_changing_retry_payload, test_group_map_toggle_requires_map_ownership.

Final result: Ran 60 tests in 0.313s; FAILED (failures=1, errors=51); process exit 1.

### tests/legacy/test_group_ui.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_changed_or_deleted_marker_keeps_draft_and_reports_conflict, test_conflict_notice_survives_regular_status_updates, test_conflicted_update_never_sends, test_doubleclick_current_list_entry_explicitly_reloads, test_roster_selections_follow_ids_after_reorder, test_unrelated_revision_preserves_unsaved_note, test_clock_skew_cannot_change_update_ttl, test_create_and_note_boundary_use_server_limits, test_edit_preserves_metadata_without_renewing_deadline, test_layout_bindings_and_rebindable_gameplay_seam, test_menu_factory_preserves_native_dispatch_and_sets_custom_id, test_native_selection_edits_only_valid_marker_rows, test_unplaced_marker_cannot_send.

Final result: Ran 15 tests in 0.069s; FAILED (errors=13); process exit 1.

### tests/legacy/test_h1_helicopters.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_capacity_return_recovers_and_callback_promotes_survivor, test_non_helicopter_fuel_is_untouched, test_overflow_init_ce_delete_caps_fuel_and_recovers, test_stop_callbacks_getter_and_restart, test_no_provider_symbol_so_base_mod_loads_without_it, test_vehicle_hooks_chain_super_first.

Final result: Ran 17 tests in 0.231s; FAILED (failures=2, errors=4); process exit 1.

### tests/legacy/test_hc48_habitat_boot.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_invalid_settings_refusal_prints_once, test_migration_uses_existing_module_lifecycle_after_observation_admission, test_start_passes_loaded_settings_world_and_fresh_session, test_started_module_prints_the_habitat_receipt_once, test_counts_follow_the_loaded_manifest_not_copied_literals, test_disposition_counts_match_the_manifest, test_manifest_between_the_old_and_new_cap_still_reads, test_manifest_is_read_once_per_boot_inside_its_declared_byte_bound, test_manifest_over_the_cap_refuses_with_a_named_reason_and_its_size, test_manifest_stays_inert, test_missing_or_inconsistent_manifest_refuses_instead_of_claiming_counts, test_off_and_refused_admit_nothing, test_ready_line_carries_counts_dispositions_and_every_refusal_reason, test_ready_line_reports_manifest_chars_and_cap_before_the_runtime_tail, test_same_state_prints_once_and_unknown_state_is_refused, test_section_keys_tolerate_any_whitespace_around_the_colon, test_enabled_settings_admit_the_module_without_closing_collection, test_tick_uses_engine_milliseconds_and_stop_stops.

Final result: Ran 27 tests in 0.704s; FAILED (failures=14, errors=4); process exit 1.

### tests/legacy/test_hc53_dispositions.py — STALE_EXPECTATION

Exact four-file mission-interiors snapshot predates the current generated templates directory; it rejects legitimate template pack content before evaluating HC-53 audit integrity.

Failing methods: test_dispositions_stay_out_of_runtime_pack_and_remain_pending.

Final result: Ran 1 test in 0.010s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_ai_camps.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_finite_growth_single_home_raid_restart_and_observed_death, test_abandonment_and_last_death_release_unspent_supply_and_can_recover, test_fresh_epoch_and_failed_regeneration_save_cannot_fund_a_camp, test_party_killed_checks_identity_debits_one_and_removes_super_callback_binding, test_regeneration_uses_one_shared_watermark_and_persists_without_a_cache, test_reserve_noop_does_not_allocate_or_scan_a_home_snapshot, test_routine_step_prioritizes_upkeep_over_growth_and_alert_expiry, test_startup_refuses_legacy_and_corrupt_accepts_funded_and_refunded_images, test_terminal_refund_once_and_refounding_after_lockout.

Final result: Ran 12 tests in 3.169s; FAILED (errors=9); process exit 1.

### tests/legacy/test_hc_ai_custody.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_duplicate_lease_result_and_refilled_return_are_refused, test_each_foldback_failure_releases_finished_lease_once, test_failed_first_load_then_repaired_legacy_file_still_migrates, test_failed_first_migration_does_not_mark_start_successful, test_finished_callbacks_never_restore_budget_or_unfinish_history, test_finished_outcome_cools_then_recycles_without_two_live_copies, test_late_claim_result_with_no_active_lease_releases_budget, test_late_typed_result_after_finished_eviction_releases_only_old_budget, test_legacy_canonical_image_migrates_without_replaying_cargo_or_casualties, test_long_party_id_has_bounded_distinct_leases, test_module_stop_start_does_not_assume_process_body_absence, test_more_than_64_claims_and_bounded_finished_eviction, test_no_finished_eviction_can_remove_live_or_quarantined_identity, test_on_start_load_resolves_claims_and_late_result_releases_budget, test_refusal_releases_claim_and_reoffers_only_after_cooldown, test_restart_releases_quarantines_and_full_history_stays_evictable, test_save_failure_latches_budget_and_logs_once, test_stop_releases_unclaimed_reservation_before_same_process_start, test_unreadable_or_interrupted_restore_blocks_all_spawn_owners.

Final result: Ran 19 tests in 1.699s; FAILED (errors=25); process exit 1.

### tests/legacy/test_hc_ai_providers.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_recipe_new_fields_default_when_absent_and_validate.

Final result: Ran 12 tests in 0.021s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_ai_signals.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_authored_observer_consumes_wave_once_and_separates_warning_cooldown, test_bad_ledger_and_clock_rollback_refuse, test_betrayal_minute_cap_is_independent_bounded_and_resets, test_capacity_evicts_oldest_and_invalid_keys_do_not_close_signals, test_every_open_refusal_names_a_manual_step, test_expiry_prunes_on_open_and_remember_and_saves_only_changes, test_first_boot_discards_uncommitted_pending_and_opens, test_hit_and_kill_hooks_only_write_for_non_hostile_relations, test_kill_then_observed_surrender_preserves_defence_until_expiry, test_recovery_only_removes_guard_after_validating_committed_path, test_saved_grudge_survives_surrender_rejoin_and_restart, test_transient_clock_failure_refuses_only_event_and_keeps_ready, test_uncertain_store_refuses_without_retry, test_warn_then_kill_same_second_records_even_when_gesture_work_is_spent, test_warning_progresses_after_success_and_resets_when_observation_is_lost, test_wave_reply_then_weapon_warning_and_second_actor_escalate_within_30s, test_concrete_provider_installed_from_living_module_and_warning_escalates.

Final result: Ran 29 tests in 0.119s; FAILED (failures=1, errors=24); process exit 1.

### tests/legacy/test_hc_ai_trade.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_second_party_failure_restores_committed_cargo_without_replay.

Final result: Ran 2 tests in 0.546s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_building_claim.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_group_claim_lifecycle_quarantine_and_construction_specific_refusal.

Final result: Ran 1 test in 0.006s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_burn_events.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_good_reservation_save_logs_the_cooldown_and_publishes_no_fault, test_operator_off_and_local_opt_out_each_log_a_reason, test_bad_channel_roster_publishes_degraded_and_logs_once_per_minute_retry, test_channel_store_save_failure_refuses_start_with_its_own_reason, test_cooldown_or_clock_does_not_clear_a_standing_roster_refusal, test_recovered_roster_is_logged_again_when_it_breaks_again, test_sticky_journal_fault_and_unconfigured_start_name_a_reason_once, test_persistence_admission_failure_logs_one_line, test_restart_state_not_persisted_names_its_reason, test_restored_live_session_logs_one_line, test_start_refusals_carry_a_reason, test_startup_cleanup_unconfirmed_names_its_reason, test_recovered_admission_is_logged_again_when_it_refuses_again, test_request_flood_logs_one_rate_line_and_bad_clock_its_own, test_start_refusals_are_named_and_not_repeated, test_start_success_clears_an_earlier_refusal.

Final result: Ran 26 tests in 0.191s; FAILED (failures=15, errors=1); process exit 1.

### tests/legacy/test_hc_burn_infected.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_missing_mission_logs_why_atmosphere_did_not_start, test_building_rules_refusal_keeps_a_reason_the_summary_prints, test_missing_world_lighting_logs_and_does_not_start, test_lod_operator_preference_off_logs_its_reason, test_second_start_while_active_says_so, test_investigate_refusal_reason_is_logged_once_per_change, test_success_or_empty_reason_resets_so_a_repeat_is_logged_again, test_every_refusal_reports_its_reason_and_state_is_unchanged, test_no_ai_world_is_its_own_reason, test_refusal_log_is_bounded_per_reason, test_store_that_cannot_open_logs_a_scenes_reason, test_unusable_utc_clock_logs_why_scenes_did_not_start, test_missing_mission_publishes_refused_reason, test_unsupported_world_publishes_refused_reason, test_xml_weather_controller_publishes_refused_reason.

Final result: Ran 16 tests in 0.155s; FAILED (errors=15); process exit 1.

### tests/legacy/test_hc_camp_followups.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_visitor_refusal_logs_once_across_signal_changes_and_failed_commit.

Final result: Ran 4 tests in 0.061s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_camp_view_cache.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_cache_is_bounded_by_the_row_count, test_every_row_change_the_view_exposes_invalidates_the_cache, test_failed_snapshot_is_not_cached, test_two_steps_without_a_row_change_build_the_snapshot_once.

Final result: Ran 6 tests in 0.450s; FAILED (errors=4); process exit 1.

### tests/legacy/test_hc_caravan_handle_release.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_tick_releases_after_step_and_never_deletes.

Final result: Ran 6 tests in 0.095s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_causal_traces.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_duplicate_fact_cannot_materialize_second_trace_after_restart_or_cleanup.

Final result: Ran 1 test in 0.008s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_cellars.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_failed_stairs_never_accept_and_first_slice_stays_bounded.

Final result: Ran 1 test in 0.026s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_claim_round2.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_camp_lifecycle_drives_claims_before_gate_and_flushes_before_stop, test_native_commit_refusals_are_observable_without_condition_logs, test_native_construction_recipes_unregistered_on_every_peer, test_release_gates_actual_building_and_reports_server_refusal.

Final result: Ran 8 tests in 0.055s; FAILED (failures=2, errors=2); process exit 1.

### tests/legacy/test_hc_claim_round3.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_camp_fault_status_and_restart_clears_stale_claim_service, test_online_absence_survives_four_hour_restarts_for_31_days, test_visit_reset_downtime_hitch_legacy_and_bounds, test_refusal_reason_reaches_server_player_message.

Final result: Ran 5 tests in 0.035s; FAILED (failures=1, errors=3); process exit 1.

### tests/legacy/test_hc_client_controls.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_effective_off_cleans_scheduled_work_refuses_unknown_and_resumes_only_allowed, test_hints_keep_running_after_old_eleven_hint_mask_until_all_fourteen_are_shown.

Final result: Ran 8 tests in 0.039s; FAILED (errors=2); process exit 1.

### tests/legacy/test_hc_defaults_on.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_group_sharing_generated_default_and_explicit_opt_out, test_missing_keys_restore_on_but_explicit_false_survives_native_zero_fill.

Final result: Ran 4 tests in 0.075s; FAILED (failures=1, errors=1); process exit 1.

### tests/legacy/test_hc_defaults_round2.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_every_missing_baseline_field_refuses_and_preserves_bytes, test_explicit_false_baseline_booleans_are_kept_in_v2, test_malformed_and_invalid_never_rewrite, test_migration_write_failure_refuses_without_success_log, test_missing_key_restores_on_for_both_versions, test_only_named_compatibility_fields_can_default, test_pending_temporary_refuses_without_rewriting, test_v1_generated_false_migrates_to_current_schema_once, test_v2_false_keeps_opt_out_through_schema_migration, test_classify_yields_without_advancing_cursor_and_resumes, test_consumer_ids_keep_existing_assignments, test_herd_yields_whole_step_and_resumes_next_tick, test_legacy_missing_herds_migrates_to_schema3_once.

Final result: Ran 15 tests in 0.066s; FAILED (failures=5, errors=9); process exit 1.

### tests/legacy/test_hc_ecology_budget.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_overflow_save_resume_refusal_off_and_cost_attribution.

Final result: Ran 3 tests in 0.033s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_environmental_radio.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_folded_report_has_one_durable_channel_receipt_and_finite_factual_recipients, test_p1a_same_listener_three_channel_cycles_notified_once, test_p1b_far_fact_does_not_starve_newer_near_fact, test_p2a_range_is_horizontal_at_600m_altitude, test_p2b_faulty_legacy_files_allow_radio_without_legacy_cooldown, test_startup_without_vanilla_frequency_property_reaches_healthy_store.

Final result: Ran 6 tests in 0.102s; FAILED (failures=10); process exit 1.

### tests/legacy/test_hc_faction_outcomes.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_abstract_pressure_cannot_kill_and_observed_receipts_are_finite.

Final result: Ran 2 tests in 0.024s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_familiarity.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_death_resets_generation_reconnect_retains_and_legacy_maps_once.

Final result: Ran 1 test in 0.023s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_forage.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_travel_reclaims_only_expired_unowned_records_and_exact_pickup.

Final result: Ran 1 test in 0.026s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_forage_round2.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_byte_identical_archive_continues_and_mismatch_preserves_files, test_configurable_oldest_first_cap_and_absent_zero_default, test_default_candidate_materializes_reclaims_and_rewards_character_life, test_deferred_row_cannot_cross_an_observed_death_before_first_pickup, test_empty_startup_roster_persists_bounded_deferred_rows, test_first_living_pickup_maps_deferred_row_once_across_restart, test_inconsistent_deferred_state_still_fails_closed, test_legacy_archive_preserves_rows_and_maps_only_living_known_characters, test_lowered_cap_prunes_loaded_rows_and_persists_before_start, test_pickup_marks_dirty_then_interval_and_stop_flush, test_seasonal_content_and_existing_surface_distance_geometry_vetoes, test_stop_and_start_reset_deferred_even_when_disabled, test_zero_or_unavailable_character_id_skips_without_shared_row_and_logs_once.

Final result: Ran 13 tests in 0.534s; FAILED (failures=21); process exit 1.

### tests/legacy/test_hc_fuel_conservation.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_all_production_refusal_phases_keep_shared_reason_reports, test_cancel_flushes_only_owned_partial_step_and_restart_is_fresh, test_closed_vessel_cannot_debit_real_tank, test_competing_users_have_one_donor_lease, test_expired_or_stopped_session_cannot_reacquire_from_late_callback, test_geometry_guard_uses_both_native_channels_and_native_reach, test_native_end_hook_releases_and_slow_ticks_renew_only_live_lease, test_off_and_client_paths_have_no_inventory_writes_or_leases, test_partial_debit_credit_is_readback_bounded_and_noop_never_credits, test_post_debit_changes_or_abort_never_credit_or_replay, test_recipient_and_los_failures_never_debit, test_revalidation_on_cancel_discards_invalid_pending_credit, test_slowly_moving_car_is_not_a_stationary_donor, test_allowed_rejects_cheap_failures_before_any_raycast, test_crafting_start_calls_production_start_after_validation, test_crafting_stop_clears_live_siphon_leases, test_invalid_target_is_rejected_before_native_selection_lookup, test_live_empty_tank_or_full_vessel_finishes_quietly, test_production_stop_clears_every_lease, test_refusal_causes_have_distinct_messages_and_log_reasons, test_sub_spill_final_tank_readback_is_a_quiet_completion, test_tank_limited_session_completes_without_refusal_and_conserves, test_vessel_limited_session_completes_without_refusal_and_conserves.

Final result: Ran 23 tests in 5.596s; FAILED (errors=105); process exit 1.

### tests/legacy/test_hc_furnishing.py — STALE_EXPECTATION

Assumes the first authored home layout has no measured prop boxes. Both requested prop classes now exist in interior_prop_boxes.json, so the builder correctly reports covered.

Failing methods: test_themes_reach_runtime_only_as_measured_pack_slots_with_named_refusals.

Final result: Ran 1 test in 0.020s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_horde_routes.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_finite_observed_route_preserves_cohort_and_refuses_replay.

Final result: Ran 2 tests in 0.041s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_infected_doors.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_crawling_dead_and_unproven_human_ai_targets_refuse, test_heavy_native_lock_is_vulnerable_but_protected_locks_refuse, test_index_34_is_serviced_and_cooldown_survives_cursor_wrap, test_index_budget_yields_without_restarting_and_count_changes_are_safe, test_stop_off_and_restart_drop_all_transient_work.

Final result: Ran 5 tests in 0.038s; FAILED (errors=5); process exit 1.

### tests/legacy/test_hc_locality_rotation.py — HARNESS_ROT

Mixed port failures, source-expression pins and the stale literal 21-site count; current sites.json has 528 rows.

Failing methods: test_fair_pages_retain_failed_island_across_restart_and_sparse_caps, test_catalog_drift_keeps_removed_and_extra_operator_sites_eligible, test_clock_and_save_fault_handlers_fall_back_without_refusing_director, test_clock_or_save_fault_keeps_existing_patrol_and_enters_legacy_binding, test_extra_operator_site_alone_does_not_refuse_catalog, test_first_page_cycle_covers_all_21_sites_when_live_cap_fits, test_leftover_cursor_intent_recovers_primary_backup_or_fresh, test_legacy_fallback_does_not_rebind_or_recreate_retained_patrol, test_persisted_route_refusal_reloads_and_avoids_native_qualification, test_qualification_survives_until_next_visit_creates_patrol, test_route_outcome_saved_and_cached_refusal_survives_binding, test_site_less_pending_log_is_rate_limited, test_sites_within_live_cap_keep_empty_patrols_eligible_after_opportunity, test_smaller_cap_rotates_fairly_including_sites_in_same_locality, test_save_step_results_are_class_qualified, test_shipped_21_sites_are_armed_in_first_cycle_at_cap_21.

Final result: Ran 16 tests in 0.791s; FAILED (failures=2, errors=19); process exit 1.

### tests/legacy/test_hc_module_readiness.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_each_registered_module_has_one_conservative_readiness_line, test_settings_failure_prints_one_off_line_per_module_without_admission.

Final result: Ran 3 tests in 0.056s; FAILED (failures=2); process exit 1.

### tests/legacy/test_hc_module_readiness_wave16.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_every_listed_module_derives_its_status_from_live_state, test_disabled_modules_get_no_baseline_so_indexes_follow_the_active_array, test_refresh_prints_one_late_ready_line_when_a_module_changes_after_boot, test_stop_and_restart_reset_the_change_baseline.

Final result: Ran 11 tests in 0.072s; FAILED (failures=3, errors=7); process exit 1.

### tests/legacy/test_hc_native_incidents.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_one_lease_finite_native_stock_and_durable_disappearance_refusal.

Final result: Ran 1 test in 0.006s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_operational_snapshot.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_full_contributor_registry_attempts_once_and_reset_clears_refusals, test_status_authorizes_before_describing_and_rechecks_delivery, test_unauthorized_oversized_and_stale_cached_rows, test_start_registers_enabled_and_disabled_owners_and_reports, test_stop_marks_owner_before_callback_and_restart_discards_receipts, test_ticks_refresh_active_owner_past_source_ttl_with_bounded_work.

Final result: Ran 9 tests in 0.317s; FAILED (failures=3, errors=3); process exit 1.

### tests/legacy/test_hc_operational_status.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_cached_lifecycle_distinguishes_off_refused_ready_and_unknown_without_io.

Final result: Ran 3 tests in 0.019s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_perf_integration_w45.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_shared_save_off_refuses_world_and_embedded_owners_before_start, test_performance_scope_registered_and_mutations_detected.

Final result: Ran 4 tests in 0.030s; FAILED (failures=2); process exit 1.

### tests/legacy/test_hc_perf_w45.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_holdout_catalog_progresses_before_the_ten_second_simulation_deadline, test_scheduler_reports_only_new_peaks_over_the_configured_target, test_failed_snapshot_stage_is_not_advanced, test_snapshot_encoding_and_file_promotion_are_separate_ticks, test_staged_file_ports_preserve_verified_primary_and_retain_failed_intent, test_real_ecology_prune_uses_the_configured_cap_and_eventually_finishes, test_shared_save_off_does_not_disable_explicit_owner_flush.

Final result: Ran 10 tests in 0.171s; FAILED (failures=3, errors=4); process exit 1.

### tests/legacy/test_hc_picker_caches.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_crowded_native_scan_fails_closed_without_creating_duplicate_crate, test_custody_blocks_empty_or_gone_source_even_after_cooldown, test_default_endpoints_seed_finite_stock_and_real_trip_binds, test_each_authored_route_has_empty_home_and_finite_source, test_empty_or_gone_source_waits_for_cooldown_and_clear_radius, test_existing_cache_step_visits_one_endpoint_with_shared_budget, test_initial_creation_waits_for_players_at_either_endpoint, test_restart_adopts_identity_without_stock_replay_including_interrupted_seed, test_step_extends_existing_cache_scheduler_with_shared_budget.

Final result: Ran 13 tests in 0.393s; FAILED (failures=1, errors=8); process exit 1.

### tests/legacy/test_hc_picker_seed.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_mismatched_route_scheme_and_unknown_faction_are_not_seeded, test_caps_missing_repair_and_existing_row_is_never_rewritten, test_fresh_shipped_survey_restart_and_identity_resolution.

Final result: Ran 4 tests in 0.119s; FAILED (failures=2, errors=1); process exit 1.

### tests/legacy/test_hc_picker_starts.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_combat_or_pending_spawn_is_not_an_idle_party, test_despawn_mid_trip_uses_loss_journal_without_item_copy_or_move, test_existing_step_visits_one_state_under_shared_budget, test_feature_off_client_or_site_cooldown_never_begins, test_lifecycle_passes_claimed_identity_actor_lease_once, test_missing_group_is_named_before_base_lifecycle_removes_state, test_missing_group_or_unsurveyed_route_refuses_once_by_name, test_per_party_receipt_survives_another_partys_journal, test_cooldown_cap_budget_and_real_home_position_precede_begin, test_idle_surveyed_party_starts_once_with_real_actor_and_lease, test_terminal_rearm_is_durable_and_quarantine_is_never_replayed.

Final result: Ran 13 tests in 0.728s; FAILED (errors=15); process exit 1.

### tests/legacy/test_hc_picker_theft.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_daily_attempt_budget_survives_new_trip_and_clock_rollback, test_remote_busy_attended_and_uncertain_barriers_never_move, test_same_item_source_is_checkpointed_before_existing_trip_steps, test_theft_runs_existing_intents_and_quarantines_ambiguous_restart, test_deposit_completes_once_after_observer_leaves, test_observer_arrives_during_return_leg_trip_keeps_custody, test_persistent_observer_expires_through_normal_refusal, test_real_identity_loss_still_ends_trip_while_observed.

Final result: Ran 13 tests in 0.178s; FAILED (errors=15); process exit 1.

### tests/legacy/test_hc_picker_walk.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_provider_binds_once_and_waits_for_idle_without_replacing_active_port, test_clear_restores_patrol_before_releasing_inventory_handles, test_exact_outbound_and_return_legs_then_restore_patrol, test_group_change_does_not_command_a_replacement_party, test_terminal_checkpoint_restores_patrol_but_active_checkpoint_does_not.

Final result: Ran 11 tests in 0.134s; FAILED (errors=10); process exit 1.

### tests/legacy/test_hc_pickers_survey.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_tick_checkpoint_failure_refreshes_status_before_later_early_returns, test_a_route_without_its_route_id_is_still_refused, test_the_shipped_survey_with_cache_loot_rows_has_every_field.

Final result: Ran 24 tests in 0.466s; FAILED (failures=2, errors=1); process exit 1.

### tests/legacy/test_hc_postures.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_primary_owner_exposes_cached_degraded_posture_and_closes_on_stop, test_unsupported_transition_refuses_then_native_hold_wakes_once_and_queue_is_bounded.

Final result: Ran 2 tests in 0.027s; FAILED (errors=2); process exit 1.

### tests/legacy/test_hc_recovery.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_clean_stop_restart_admits_changed_images_without_receipts, test_corrupt_world_quarantines_only_world_healthy_stores_flush_on_stop, test_escalation_damage_is_local_and_world_off_needs_no_clock, test_group_empty_directory_is_fresh_and_partial_revision_still_refused, test_module_stops_flush_healthy_stores_before_last_intent_cleanup, test_partial_backup_and_regression_preserve_evidence_per_store.

Final result: Ran 16 tests in 3.797s; FAILED (errors=8); process exit 1.

### tests/legacy/test_hc_recovery_integrity.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_hc30_registration_and_boot_admission_report_once_on_every_path.

Final result: Ran 11 tests in 0.966s; FAILED (failures=9); process exit 1.

### tests/legacy/test_hc_s005_wave11.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_cellar_seed_missing_method_and_disposition_get_declared_defaults, test_missing_measured_prop_index_is_refused_before_native_parse, test_pending_locality_row_without_refusal_restores_the_declared_reason, test_infected_journal_without_schema_version_is_refused, test_legacy_interior_pilot_candidates_need_an_explicit_slot, test_settlement_state_without_version_is_refused.

Final result: Ran 9 tests in 26.166s; FAILED (failures=3, errors=3); process exit 1.

### tests/legacy/test_hc_s160_final_burn.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_a_complete_record_still_binds_and_reports_no_refusal, test_a_record_with_a_prop_missing_index_is_refused_with_a_named_reason, test_group_request_send_refuses_a_payload_without_color, test_retired_json_with_recent_count_opens, test_retired_json_without_recent_count_is_refused_with_a_reason, test_the_presence_guard_names_the_prop_depth_and_selector.

Final result: Ran 18 tests in 25.939s; FAILED (failures=4, errors=2); process exit 1.

### tests/legacy/test_hc_scavenge.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_single_custody_interruption_return_loss_and_restart.

Final result: Ran 1 test in 0.016s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_scene_upgrade.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_legacy_initializer_and_null_ports_already_pass_all_validators, test_migration_preserves_legacy_page_and_rejects_partial_or_migrated_corruption, test_open_constructs_defaults_before_loading_missing_story_fields, test_open_operator_off_gap_then_enable_migrates_once_and_reopens, test_refusals_identify_category_and_preserve_all_images.

Final result: Ran 5 tests in 0.045s; FAILED (failures=5); process exit 1.

### tests/legacy/test_hc_situations.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_independent_lifecycle_and_retired_quest_requests.

Final result: Ran 1 test in 0.016s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_status_review_round1.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_scene_barrier_save_failure_retains_fault_after_stop, test_decay_initialization_failure_never_reports_ready, test_decay_start_wait_world_initialize_then_runtime_fault.

Final result: Ran 7 tests in 0.084s; FAILED (failures=2, errors=1); process exit 1.

### tests/legacy/test_hc_story_module.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_empty_page_preserves_gap_check_then_returns_without_indexing, test_operator_off_stories_never_bind_the_situation_source, test_retired_release_reclaims_only_its_bounded_refusal_keys, test_start_wires_schedule_before_save_job_and_preserves_start_refusal, test_stop_does_not_reenter_when_heartbeat_flush_fails, test_bad_story_inputs_disable_only_stories_with_one_diagnostic, test_downtime_commit_is_seen_before_story_can_write_last_now, test_story_barriers_clear_flags_only_for_success_or_save_failure, test_tick_runs_work_before_story_and_skips_saved_or_stopped_slot.

Final result: Ran 10 tests in 0.149s; FAILED (failures=8, errors=8); process exit 1.

### tests/legacy/test_hc_story_schedule.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_independent_successors_migration_failed_start_and_restart_conservation, test_operator_off_legacy_state_saves_object_then_migrates_once.

Final result: Ran 2 tests in 0.016s; FAILED (failures=2); process exit 1.

### tests/legacy/test_hc_survival_alignment.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_retired_meal_heat_and_existing_travel_stamina.

Final result: Ran 1 test in 0.005s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_taped_default_on.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_helmet_mounts_are_admitted_unverified_by_default, test_helmet_native_slot_loss_is_degraded_not_ready, test_helmet_opt_out_file_is_a_named_off_reason, test_taped_light_publishes_an_honest_ready_from_its_admission, test_a_pack_pair_is_admitted_unverified_with_no_checked_receipt, test_no_admitted_pair_degrades_with_the_native_slot_reason, test_receipt_disabled_opts_one_pack_pair_out, test_setting_off_is_the_named_operator_opt_out, test_shipped_defaults_admit_the_pack_cross_pair_when_slots_exist, test_a_refused_file_degrades_the_module_and_admits_nothing, test_disabled_must_be_a_json_bool_or_the_file_is_refused, test_disabled_true_opts_the_pair_out_and_absent_means_admitted, test_shipped_receipt_sheet_loads_clean_with_nothing_disabled, test_unicode_escaped_receipt_keys_are_refused_with_a_named_reason, test_unicode_escapes_in_note_values_are_allowed, test_unknown_pair_and_malformed_file_still_refuse_everything, test_a_weapon_binding_is_allowed_only_for_an_admitted_exact_pair, test_boot_reports_pack_and_weapon_checked_counts_separately, test_checked_disabled_pairs_are_covered_but_never_admitted, test_every_weapon_pair_is_admitted_unverified_with_native_slots, test_missing_weapon_light_slot_is_one_named_line_and_the_module_stays_ready, test_one_summary_line_counts_admitted_unverified_pairs_not_one_line_per_pair, test_summary_checked_and_unchecked_use_only_the_covered_cohort, test_helmet_qualification_ready_follows_the_catalogue_admission_only.

Final result: Ran 36 tests in 10.007s; FAILED (failures=1, errors=23); process exit 1.

### tests/legacy/test_hc_taped_lights.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_full_cargo_refuses_before_intent_then_returns_same_light_and_battery, test_pack_pairs_refuse_before_custody_without_native_qualification, test_spent_last_tape_replay_acknowledges_without_a_new_debit_or_move, test_spent_tape_intent_fault_never_refunds_or_replays_on_reopen, test_helmet_manifest_refuses_unsupported_pairs_and_unqualified_binding, test_start_reports_all_pairs_and_r12_pending_even_when_off.

Final result: Ran 7 tests in 0.111s; FAILED (errors=6); process exit 1.

### tests/legacy/test_hc_taped_pack_loader.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_enabled_cross_slot_needs_its_native_slot_then_is_admitted_unverified, test_start_loads_once_and_publishes_off_while_setting_off, test_unreadable_or_invalid_manifest_degrades_with_reason.

Final result: Ran 10 tests in 14.617s; FAILED (errors=3); process exit 1.

### tests/legacy/test_hc_taped_pack_receipts.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_a_checked_receipt_is_only_a_record_and_a_disabled_row_opts_out, test_binding_is_allowed_only_for_an_admitted_pair, test_cross_pair_needs_cross_slot_and_permission, test_setting_off_admits_nothing_even_with_a_checked_receipt_and_native_slots, test_setting_on_admits_unverified_without_any_checked_receipt, test_shipped_catalogue_gate_keeps_the_verdict_at_zero_even_when_admitted, test_shipped_files_admit_nothing_with_the_setting_off, test_without_native_slots_the_pair_is_a_named_refusal_not_an_admission, test_impossible_calendar_days_are_refused, test_real_calendar_days_are_accepted, test_boot_line_degrades_with_the_limit_reason, test_a_string_value_spelled_checked_is_not_a_key, test_check_date_must_be_an_iso_date, test_checked_key_whitespace_variants_are_typed_by_the_literal, test_invalid_receipts_degrade_the_boot_line_with_the_reason, test_missing_key_refuses_for_every_field_and_grants_nothing, test_note_text_quoting_the_checked_key_is_not_a_typed_field, test_other_refusals_grant_nothing, test_oversize_receipt_file_is_refused_by_the_read_limit_with_a_named_reason, test_stop_clears_the_receipts_and_setting, test_unchecked_receipt_may_leave_the_date_empty_but_checked_may_not, test_unknown_pair_id_refuses_and_grants_nothing, test_valid_receipts_record_only_checked_pairs, test_wrongly_typed_checked_degrades_the_boot_line_with_the_reason, test_wrongly_typed_checked_refuses_with_a_named_reason_and_grants_nothing.

Final result: Ran 35 tests in 29.854s; FAILED (errors=25); process exit 1.

### tests/legacy/test_hc_taped_pair_ids.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_setting_off_keeps_the_file_unread_and_the_count_visible, test_shipped_sheet_loads_clean_with_zero_checked_and_nothing_disabled, test_a_checked_weapon_receipt_is_only_a_record_and_admits_no_pack_pair, test_a_checked_weapon_receipt_is_recorded_for_that_pair_only, test_a_pair_that_is_not_in_the_catalogue_is_refused_with_a_named_reason, test_checked_weapon_row_needs_a_real_date_and_note, test_duplicate_weapon_receipt_refuses_the_whole_file.

Final result: Ran 15 tests in 10.184s; FAILED (errors=7); process exit 1.

### tests/legacy/test_hc_team_ping.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_current_membership_receipts_and_refusals.

Final result: Ran 1 test in 0.007s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_template_pack.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_610_leaves_plus_16_pages_count_once_and_leaf_611_refuses, test_bounded_reader_rejects_count_mismatch_and_reads_cap_plus_one, test_complete_bounded_pack_refuses_damage_and_migrates_without_gameplay_changes, test_receipt_order_bounded_read_logs_and_single_strict_dispatch.

Final result: Ran 4 tests in 0.380s; FAILED (errors=5); process exit 1.

### tests/legacy/test_hc_threat_matrix.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_current_target_wall_native_refusal_and_off_matrix.

Final result: Ran 1 test in 0.013s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hc_threat_posture_wiring.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_forced_movement_refusal_skips_vault_backoff_and_navmesh_work, test_start_stop_reset_real_contact_budget_and_repeated_start_does_not_refill, test_diag_policy_failure_cannot_reopen_vision, test_healthy_infected_start_resets_then_observes_admission_and_stop_closes_first, test_quarantine_closes_vision_before_cleanup_and_unhealthy_start_never_admits, test_server_resets_before_modules_and_prints_effective_summary_once_per_start.

Final result: Ran 8 tests in 0.079s; FAILED (errors=8); process exit 1.

### tests/legacy/test_hc_tick_budget.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_infected_outside_a_core_tick_are_limited_only_by_their_own_cap, test_an_instance_outside_a_core_tick_gets_the_idle_budget_not_the_spent_core_one, test_during_a_core_tick_the_accessor_returns_the_shared_budget, test_no_hcserver_instance_returns_a_usable_budget_that_never_refuses, test_a_consumer_that_finds_budget_left_is_not_counted_as_starved, test_a_spent_budget_still_admits_each_consumers_first_item_once, test_exact_bound_is_limit_plus_one_forced_unit_per_later_consumer, test_reset_clears_forced_flags_so_the_next_tick_forces_again, test_window_report_has_the_perf_fields_once_per_window_and_stays_pending, test_tick_resets_the_shared_budget_marks_it_active_only_inside_and_prints_once_per_window, test_interiors_outside_a_core_tick_visit_every_site_once_per_tick, test_a_budget_larger_than_the_demand_forces_nothing_and_matches_the_old_per_module_totals, test_forced_units_are_counted_as_starved_in_the_window_report, test_infected_first_spends_its_cap_and_interiors_still_progress_every_tick, test_interiors_first_spends_the_budget_and_infected_still_progresses_every_tick.

Final result: Ran 19 tests in 0.322s; FAILED (failures=17, errors=1); process exit 1.

### tests/legacy/test_hc_tick_budget_fixes.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_charge_query_outside_a_core_tick_is_limited_only_by_its_own_cap, test_charge_query_takes_a_shared_unit_and_stays_inside_its_own_cap, test_charge_query_under_a_spent_pool_is_forced_once_per_tick, test_compact_settled_examines_one_forced_row_per_tick_and_resumes_at_the_refused_row, test_compact_settled_under_a_roomy_pool_examines_every_row_once_per_call, test_detached_loop_uses_its_own_consumer_id_and_the_bound_counts_it, test_the_detached_loop_releases_one_binding_per_tick_when_the_pool_is_spent, test_a_batch_larger_than_the_pool_resumes_and_refreshes_every_row_exactly_once, test_a_clock_that_went_backwards_faults_instead_of_saving, test_a_new_minute_arriving_mid_batch_is_held_until_the_batch_ends, test_a_roomy_pool_finishes_the_batch_in_one_tick_with_one_save, test_rows_not_yet_due_advance_the_cursor_without_a_save.

Final result: Ran 17 tests in 0.481s; FAILED (failures=5, errors=7); process exit 1.

### tests/legacy/test_hc_unit_budget.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_a_surviving_intent_faults_the_commit_and_keeps_recovery_files, test_a_synchronous_barrier_save_mid_flight_restarts_from_a_fresh_snapshot, test_backup_refresh_is_its_own_stage_and_leaves_no_intent, test_commit_writes_intent_replaces_reads_back_and_clears_the_intent_in_one_stage, test_external_edit_faults_before_any_write_and_preserves_the_files, test_fresh_store_without_a_current_image_skips_prior_and_backup, test_serialize_and_prior_compare_stages_never_write, test_synchronous_save_runs_the_same_stages_and_ends_with_the_original_files, test_scene_save_job_is_staged_and_clears_in_flight_before_stopping, test_store_serializes_through_one_encode_helper_and_commits_in_a_single_stage, test_commit_runs_in_one_tick_in_the_original_order_and_clears_the_intent, test_external_edit_refusal_fails_the_second_stage_before_any_write, test_fresh_world_skips_the_prior_read_and_backup, test_serialize_and_prior_compare_stages_never_touch_disk_writes, test_synchronous_save_is_the_same_three_stages_and_ends_with_identical_files, test_the_snapshot_is_taken_at_the_first_stage_not_at_commit, test_cheap_creation_attempts_keep_the_declared_three_per_tick, test_cheap_deferrals_are_not_reported_as_items_and_keep_their_count, test_heavy_creation_attempt_ends_the_tick_after_one_item, test_mid_cost_attempts_stop_once_the_measured_units_are_spent, test_a_completed_save_logs_stages_and_the_slowest_stage_in_raw_ticks, test_a_failed_stage_unregisters_the_job_without_retrying_every_tick, test_a_job_dropped_mid_save_does_not_leak_its_stage_counts_into_the_next_save, test_flush_gives_up_on_a_job_that_never_finishes, test_not_due_or_clean_jobs_are_never_stepped, test_one_stage_per_tick_and_an_in_flight_job_is_not_interleaved, test_save_line_prints_only_for_a_new_slowest_stage_per_job, test_single_step_job_behaves_exactly_like_the_old_whole_store_flush, test_synchronous_flush_finishes_every_remaining_stage, test_synchronous_flush_reports_a_failed_stage_and_a_clean_job_is_a_no_op, test_an_item_heavier_than_the_whole_budget_still_makes_progress_once_per_tick, test_costs_below_one_count_as_one_and_limits_below_one_become_one, test_items_are_admitted_until_the_units_are_spent, test_measured_charge_takes_the_larger_of_declared_and_measured_units, test_post_hoc_charge_closes_the_slice_and_ignores_non_positive_costs.

Final result: Ran 52 tests in 0.406s; FAILED (failures=19, errors=16); process exit 1.

### tests/legacy/test_hc_visual_seasons.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_owner_refusal_operator_off_and_unopened_store_are_safe_no_ops, test_restart_downtime_never_jumps_phase_and_all_four_boundaries, test_rollback_gap_and_checkpoint_lag_pause_without_crediting_time, test_staged_snapshot_stop_flushes_latest_and_failed_save_refuses_retry, test_four_forecasts_grade_continuity_and_snapshot_off_cleanup.

Final result: Ran 6 tests in 0.132s; FAILED (failures=8); process exit 1.

### tests/legacy/test_hc_wave15_core.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_the_cap_is_one_named_constant_and_the_bare_literal_appears_once, test_a_later_tick_callback_does_nothing_after_the_stop, test_an_ordinary_tick_still_runs_every_module_once_and_rolls_the_window, test_modules_after_a_stopping_module_are_not_ticked_and_the_window_is_not_rolled.

Final result: Ran 12 tests in 0.290s; FAILED (failures=4); process exit 1.

### tests/legacy/test_hc_wave16_cellevents.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_admission_is_admitted_unverified_not_closed, test_module_starts_ready_and_prints_one_unverified_receipt, test_unreadable_counts_degrade_with_a_named_reason, test_bound_source_with_missing_provider_stays_ready_with_one_named_line, test_director_defers_to_first_tick_and_reports_pending_at_boot, test_first_tick_without_a_bound_source_is_refused_by_name, test_operator_off_stays_off, test_scenes_startup_binding_drives_events_status_sequence, test_marker_present_still_starts_the_measurement, test_non_server_stays_off, test_server_without_marker_is_ready_idle_and_does_nothing.

Final result: Ran 11 tests in 0.162s; FAILED (errors=13); process exit 1.

### tests/legacy/test_hc_wildlife.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_aliases_share_one_native_owner_and_unsupported_commands_refuse.

Final result: Ran 1 test in 0.037s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_wreck_supply.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_two_actors_restart_never_replenish_compatible_finite_parts.

Final result: Ran 1 test in 0.020s; FAILED (failures=1); process exit 1.

### tests/legacy/test_hc_zero_fill.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_missing_scalars_are_zero_and_loaded_initializers_require_a_guard.

Final result: Ran 3 tests in 3.106s; FAILED (errors=1); process exit 1.

### tests/legacy/test_hcx_emotes_wave41.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_faction_memory_uses_existing_bounded_durable_store_and_expires, test_faction_receipt_is_written_by_observed_aggression_and_seen_by_other_group, test_startup_status_reflects_failed_store_or_provider_before_any_tick.

Final result: Ran 7 tests in 0.054s; FAILED (errors=4); process exit 1.

### tests/legacy/test_hcx_refusal_burn.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_bad_tokens_and_unqualified_route_and_unfair_faction_have_distinct_reasons, test_cap_anchor_group_and_capacity_refusals_log_once_per_reason_change, test_idempotent_restart_mismatch_names_a_reason_and_a_match_clears_it, test_reentrant_start_reports_busy_and_an_accepted_start_clears_the_reason, test_unconfirmed_journal_intent_and_group_failure_keep_their_state_and_reason.

Final result: Ran 17 tests in 0.396s; FAILED (errors=5); process exit 1.

### tests/legacy/test_hcx_self_defence.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_grudge_store_evicts_the_oldest_only_when_full, test_hostility_is_proportional_and_expires, test_infected_near_the_shooter_or_actor_excuses_the_shot, test_near_miss_classification, test_pass_by_stops_where_the_bullet_stops, test_rescue_hit_on_a_friendly_is_excused_once, test_shot_evaluations_are_rate_and_window_capped, test_threat_floor_only_with_an_active_grudge.

Final result: Ran 16 tests in 0.118s; FAILED (errors=8); process exit 1.

### tests/legacy/test_horde_stimulus.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_cohort_comparison_uses_category_then_recency_then_strength, test_expired_future_invalid_strength_and_hops_are_never_chosen, test_freeze_preserves_hops_including_the_two_hop_boundary, test_frozen_selection_never_refreshes_original_or_copy, test_individual_helper_and_cohort_wrapper_agree_for_same_inputs, test_live_observed_visual_beats_newer_sound_and_reports_reason, test_memory_is_explicit_but_never_promoted_to_observation, test_nonadmitted_heard_input_is_ignored_including_self_voice, test_sound_beats_expired_visual_or_unknown_retained_memory, test_source_slots_do_not_upgrade_wrong_provenance, test_stale_but_live_visual_beats_a_fresher_sound_by_deliberate_precedence.

Final result: Ran 11 tests in 0.145s; FAILED (errors=19); process exit 1.

### tests/legacy/test_house_search_flow.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_absent_journaled_handle_can_rebind_after_sixty_seconds_without_refill, test_binding_starts_without_placement_then_action_grants_exact_existing_item, test_changed_first_supply_does_not_block_later_transferable_row, test_depleted_site_can_report_empty_without_allocating_replacement_loot, test_empty_begin_reports_empty_and_never_creates_or_journals_supply, test_missing_marker_or_disabled_preference_cannot_be_armed, test_readiness_opens_healthy_journal_without_observing_or_binding_ce, test_stop_during_supply_selection_refuses_without_session_or_transfer, test_unhealthy_journal_is_never_reported_armed, test_template_pack_tick_reports_after_installing_owner_and_pilot_absence.

Final result: Ran 13 tests in 0.542s; FAILED (failures=1, errors=9); process exit 1.

### tests/legacy/test_infected_admission.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_default_preferences_are_requested_but_not_admitted_with_specific_reasons, test_explicit_false_is_a_hard_disable_even_if_qualified, test_hypothetical_qualified_path_is_admitted_alone, test_shipped_qualification_is_all_false, test_status_reports_requested_admitted_and_reason_for_every_path, test_stimulus_routes_require_admitted_pack_routes, test_admission_selects_the_restart_wrapper_when_either_journal_lifecycle_is_admitted, test_admission_selects_verbatim_loading_when_neither_journal_lifecycle_is_admitted, test_committed_active_states_load_as_unresolved_with_interrupted_route_and_kept_reservation, test_retired_state_is_kept_and_stage_one_becomes_conflicted_by_the_same_wrapper, test_started_admitted_lifecycle_sees_unresolved_state_and_does_not_replay_before_expiry, test_admitted_adoption_alone_never_retires_a_state_six_journal, test_admitted_recovery_keeps_unresolved_restart_reservation_past_lifetime, test_finish_sweep_does_not_advance_a_dormant_journal, test_shutdown_still_releases_owned_packs_without_touching_dormant_routes, test_startup_tick_and_shutdown_leave_dormant_journals_byte_for_byte_unchanged, test_unadmitted_recovery_does_not_retire_and_save_a_previously_pending_journal, test_release_attempt_limit_has_one_policy_source, test_release_quarantine_and_pending_count_are_logged_once_per_transition, test_visual_sampling_availability_is_false_until_observed_evidence_exists, test_visual_sampling_skips_call_and_observation_budget_while_unavailable, test_admitted_horde_work_without_the_hordes_setting_needs_no_extra_budget, test_admitted_native_routes_and_investigation_keep_the_eight_item_prerequisite, test_closed_capabilities_do_not_quarantine_native_only_startup_at_valid_core_budget, test_config_validity_no_longer_encodes_a_capability_dependency, test_each_admitted_horde_lifecycle_keeps_the_eight_item_prerequisite, test_existing_adoption_and_stimulus_budgets_still_apply_at_eight, test_explicit_pack_disable_does_not_quarantine_unqualified_stimulus_preference, test_explicit_pack_disable_with_hypothetical_stimulus_qualification_is_admission_not_invalid_config, test_generic_core_minimum_of_four_is_kept, test_startup_positive_control_default_budget_reaches_healthy, setUpClass, test_variant_map_diagnostic_matches_selection_and_logs_substitutions_once.

Final result: Ran 40 tests in 0.505s; FAILED (failures=1, errors=54); process exit 1.

### tests/legacy/test_infected_completion.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_chain_recipients_are_bounded_deduped_occluded_and_rate_limited, test_chain_root_lifetime_hops_and_strength_are_inherited, test_given_native_voices_when_chain_progresses_then_limits_and_dedupe_hold, test_given_surveyed_rooms_when_ordered_then_ties_are_deterministic, test_native_centroid_uses_supported_vector_multiplication, test_recovered_cohort_requires_complete_count_and_preserves_escrow, test_recovery_identity_never_uses_zero_or_partial_match, test_room_admission_needs_measurement_and_bounded_catalog, test_room_order_is_clue_first_then_distance_and_stable_id, test_root_dedupe_expires_without_extending_old_roots.

Final result: Ran 22 tests in 0.127s; FAILED (errors=10); process exit 1.

### tests/legacy/test_infected_contract.py — HARNESS_ROT

setUpClass fails on undefined HCHordeLimits before any test runs (exit 5).

Failing methods: setUpClass.

Final result: Ran 0 tests in 0.012s; FAILED (errors=1); process exit 5.

### tests/legacy/test_infected_death_selection.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_exhaustive_sweep_only_ever_upgrades_default_to_impulse, test_finishers_and_nondefault_native_types_are_never_rewritten, test_frontal_cone_boundary_is_inclusive_sixty_degrees, test_heavy_by_ammo_hit_animation_or_by_override_both_count, test_heavy_frontal_torso_or_head_kill_upgrades_default_to_impulse, test_leg_zones_keep_the_vanilla_fold, test_light_hits_stay_on_the_vanilla_default, test_nonfinite_direction_is_refused_to_vanilla, test_other_zones_and_empty_zone_stay_default, test_rear_and_side_kills_stay_on_the_vanilla_default, test_no_velocity_teleport_physics_health_or_deletion_calls.

Final result: Ran 21 tests in 0.084s; FAILED (failures=1, errors=10); process exit 1.

### tests/legacy/test_infected_defaults.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_empty_enabled_variant_template_is_valid_but_unqualified, test_maps_remain_explicit_bounded_and_validated_even_when_disabled, test_preferences_on_without_flipping_diagnostic_or_evidence_flags, test_registration_budget_is_shared_and_reset_by_the_core_tick, test_registration_budget_saturates_without_incrementing_at_int_max, test_tracking_returns_admission_never_duplicates_and_respects_capacity, test_unresolved_member_tombstones_are_not_recycled.

Final result: Ran 21 tests in 0.049s; FAILED (errors=7); process exit 1.

### tests/legacy/test_infected_doors.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_w6_variant_door_pressure_opens_bashes_and_refuses.

Final result: Ran 1 test in 0.008s; FAILED (errors=1); process exit 1.

### tests/legacy/test_infected_lod.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_safely_far_is_conservative_about_sample_age_and_speed, test_three_tiers_by_nearest_player_distance, test_per_tier_posed_room, test_tiered_budget_at_twelve_is_the_shipped_behaviour, test_config_and_store_caps, test_fold_never_removes_a_seen_fighting_alerted_or_claimed_body, test_members_are_wanted_only_near_players_and_within_caps, test_regrow_is_slow_and_only_while_fully_virtual, test_spawn_point_must_be_out_of_every_players_sight, test_materialize_uses_the_admin_sitter_spawn_path_out_of_sight.

Final result: Ran 17 tests in 0.084s; FAILED (failures=1, errors=9); process exit 1.

### tests/legacy/test_infected_lod_defaults.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_absent_legacy_herds_migrates_but_other_baseline_omissions_refuse, test_each_seed_cites_an_exact_existing_rural_or_woodland_anchor, test_empty_v2_migrates_once_and_logs_after_verified_save, test_explicit_nonempty_seeds_are_preserved, test_fresh_profile_gets_eight_bounded_unique_inland_seeds, test_invalid_null_and_current_partial_files_are_preserved, test_migration_write_failure_refuses_without_success_log, test_v2_operator_opt_out_survives_seed_migration.

Final result: Ran 8 tests in 0.072s; FAILED (errors=8); process exit 1.

### tests/legacy/test_infected_lod_followups.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_config_rejects_bands_outside_transition_and_sight_ranges, test_defaults_keep_the_documented_kilometre_bubble_in_simulation, test_dead_claimed_and_missing_members_are_reconciled_once, test_stop_preserves_living_heads_and_surviving_body_reservations, test_dead_slots_leave_live_capacity_and_archive_evicts_oldest, test_fold_retires_its_live_slot_before_native_deletion, test_unresolved_horde_evidence_is_not_evicted.

Final result: Ran 11 tests in 0.099s; FAILED (errors=7); process exit 1.

### tests/legacy/test_infected_memory_clock.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_admin_list_with_future_samples_never_changes_memory_or_clock, test_forward_heat_read_never_advances_any_watermark, test_forward_write_resumes_decay_after_clock_catches_up, test_large_skew_write_fails_once_and_preserves_samples, test_small_skew_new_cell_and_record_cap_use_retained_second, test_small_skew_record_preserves_samples_and_timestamp.

Final result: Ran 6 tests in 0.122s; FAILED (errors=11); process exit 1.

### tests/legacy/test_infected_pack_ownership.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_allocation_failure_preserves_owner_and_retries_within_budget, test_failed_remove_does_not_add_an_agent_still_owned_elsewhere, test_late_verified_fallback_ownership_can_complete_after_budget, test_missing_agent_is_unresolved_rather_than_a_successful_rehome, test_only_verified_members_are_removed_from_a_partial_release, test_partial_start_ungrouped_member_is_rehomed_even_without_old_group, test_release_does_not_forget_member_after_failed_fallback_add, test_retry_budget_quarantines_unresolved_members_without_more_mutations, test_unexpected_third_owner_is_not_confirmation_or_permission_to_steal, test_ungrouped_retry_confirms_the_same_expected_fallback.

Final result: Ran 10 tests in 0.103s; FAILED (errors=10); process exit 1.

### tests/legacy/test_infected_perception.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_retained_auditory_candidate_is_not_a_confirmed_visual_observation, test_unknown_visual_provenance_does_not_acquire_hidden_coordinates.

Final result: Ran 3 tests in 0.031s; FAILED (errors=3); process exit 1.

### tests/legacy/test_infected_persistence.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: setUpClass, test_actual_transfer_outcome_fails_closed_on_readback_or_partial_release, test_adoption_stages_reject_replay_and_abort_reactivation, test_prepared_reservation_can_only_commit_once_with_exact_ledger, test_record_stage_requires_unresolved_preparation_and_conflicted_abort, test_restart_never_replays_prepared_transfer, test_retiring_a_horde_refunds_capacity_for_a_third_admission, test_snapshot_schema_rejects_pre_intent_state, test_unqualified_adoption_writes_no_prepare_intent_and_reserves_nothing, test_actual_orchestration_persists_before_native_transfer_and_after_result.

Final result: Ran 10 tests in 0.063s; FAILED (failures=1, errors=9); process exit 1.

### tests/legacy/test_infected_production_rooms.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_17th_house_anchor_refused_directly, test_2049th_declared_class_refused_directly_before_config_scan, test_257th_total_anchor_refused_directly, test_65th_house_refused_directly, test_anchor_evidence_is_required_bounded_and_never_synthetic, test_anchor_id_above_64_refused, test_atomic_publish_ambiguous_house_and_owned_copy, test_build_refusal_logs_observed_build_bounded_and_printable, test_clear_resets_production_and_allows_one_new_read_and_log, test_client_has_no_profile_config_or_object_access, test_denominator_missing_unknown_duplicate_and_unknown_exclusion_fail_closed, test_direct_json_preflight_rejects_1mib_plus_one_before_scanning, test_document_and_runtime_on_same_unpinned_build_refused, test_duplicate_id_at_distinct_valid_positions_refused, test_evidence_fixture_marker_refused, test_evidence_native_prefix_required, test_evidence_run_id_minimum_eight_characters, test_evidence_selftest_marker_refused, test_header_wrong_runtime_build_and_wrong_world_are_specific, test_house_box_below_minus_512_refused, test_house_class_cap_reports_observed_counts_without_claiming_coverage, test_house_denominator_ignores_nonhouse_configs_and_reports_explicit_all_excluded, test_invalid_order_requests_do_not_load_and_moved_houses_are_not_used, test_io_json_refusals_are_logged_once_until_clear, test_json_fraction_requires_digits_before_native_parser, test_json_preflight_guards_native_load_path, test_local_position_below_room_min_refused, test_measured_box_room_bounds_pose_nonfinite_and_duplicates, test_native_full_engine_build_admits_the_canonical_document, test_native_read_failure_or_inconsistent_byte_count_does_not_parse, test_nonhouse_padding_cannot_replace_missing_house_class, test_normal_server_admits_data_once_and_reports_all_classes_without_routing, test_other_engine_builds_still_refuse_even_with_a_matching_document, test_owned_anchor_copies_all_evidence_fields, test_per_house_total_and_instance_caps, test_second_valid_bind_refused_and_publication_unchanged, test_spacing_below_one_with_distinct_ids_refused, test_strict_production_json_rejects_unknown_duplicate_missing_types_shapes_and_escapes, test_total_anchor_boundary_is_admitted_as_data, test_truncated_json_never_reads_beyond_string_and_integer_overflow_is_not_coerced, test_valid_production_order_never_loads_on_first_tick, test_world_name_compare_is_case_normalised, test_zero_anchor_house_refused_directly, test_zero_volume_room_containing_point_refused, test_anchor_cap_of_256_evicts_before_the_house_cap, test_bind_radius_binds_at_29_m_and_not_at_31_m, test_cap_still_holds_when_begin_tick_is_never_called, test_clue_binds_a_covered_house_lazily_and_converts_anchors_with_model_to_world, test_configured_radius_and_cap_obey_the_setting_bounds, test_conflict_evicts_a_template_cached_before_the_legacy_file_loaded, test_conflict_is_decided_before_the_query_quota, test_conflict_needs_no_query_at_all, test_house_pose_must_be_yaw_only_and_unambiguous, test_late_load_and_clear_reset_template_state_and_settings, test_legacy_alone_keeps_working_when_the_pack_is_not_loaded, test_legacy_claim_conflicts_refuse_the_house_for_both_sources, test_lru_keeps_at_most_64_houses_and_releases_the_least_recently_used, test_malformed_templates_are_refused_without_a_binding, test_non_house_candidates_and_dense_results_are_bounded, test_ordering_skips_a_conflicted_house_even_if_a_binding_survives, test_per_tick_query_cap_defers_extra_binds_to_the_next_tick, test_query_budget_follows_begin_tick_not_the_elapsed_clock, test_refusals_are_logged_once_per_reason_and_class, test_success_log_names_provisional_pending_state_and_class_counts_once, test_template_rooms_accept_nearly_level_and_refuse_excessive_or_nan_tilt, test_templates_without_the_legacy_file_work_and_legacy_still_orders_beside_them, test_two_rooms_order_the_clue_room_first_then_the_nearest, test_uncovered_or_unknown_classes_are_ignored.

Final result: Ran 76 tests in 0.919s; FAILED (errors=98); process exit 1.

### tests/legacy/test_infected_reach.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_batter_only_occupied_or_unreachable_topped_vehicle, test_elevated_strike_needs_band_reach_line_and_vanilla_failure, test_reach_sources_self_register_without_position_writes, test_unreachable_backoff_cycles_and_releases, test_vault_band_and_experiment_retires_without_landings.

Final result: Ran 5 tests in 0.045s; FAILED (errors=5); process exit 1.

### tests/legacy/test_infected_routes.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_admitted_migration_never_falls_back_for_an_incomplete_cohort, test_admitted_migration_submits_complete_cohorts_instead_of_the_ordinary_route, test_failed_geometry_spends_shared_slot_and_is_not_retried_for_free, test_given_consumed_first_cue_then_second_gets_path_attempt_before_expiry, test_native_retarget_charges_attempts_including_geometry_failure_only, test_progress_is_toward_waypoint_not_arbitrary_wandering, test_route_metadata_does_not_confuse_intent_with_completion, test_route_requires_every_surviving_member_to_arrive, test_without_the_migration_marker_the_ordinary_route_is_unchanged.

Final result: Ran 11 tests in 0.071s; FAILED (errors=9); process exit 1.

### tests/legacy/test_infected_sentinel_reads.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_each_loaded_row_requires_keys_and_keeps_explicit_zero_living.

Final result: Ran 1 test in 0.008s; FAILED (errors=1); process exit 1.

### tests/legacy/test_infected_tick_spread.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_adoption_tick_defers_queued_room_paths, test_extend_route_spends_at_most_one_path_per_call, test_one_queued_room_path_per_module_tick_spends_the_route_token, test_reached_final_point_releases_when_no_room_is_queued, test_reached_point_holds_while_rooms_wait_for_their_path, test_search_start_spends_one_path_and_queues_surveyed_rooms, test_adoption_boundary_rearms_the_save_half_an_interval_off, test_due_save_on_an_adoption_tick_moves_to_the_next_tick, test_periodic_save_never_shares_a_tick_with_adoption.

Final result: Ran 10 tests in 0.106s; FAILED (errors=9); process exit 1.

### tests/legacy/test_infected_variants.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_all_unsupported_map_is_valid_input_without_admitting_either_capability, test_disabled_preference_and_bad_stance_never_select_or_log, test_empty_map_keeps_native_fallback_even_when_other_map_is_populated, test_invalid_maps_fail_closed_without_scanning_or_changing_them, test_mixed_map_preserves_input_and_reports_actual_ordinary_substitution, test_one_unsupported_kind_is_logged_once_with_all_eight_slots_counted, test_stalker_and_heavy_maps_do_not_admit_unavailable_physical_variants, test_supported_descriptor_never_labels_a_substitution_as_stalker_or_heavy, test_supported_only_map_selects_requested_attention_policy_without_warning, test_w5_variety_caps_and_group_scaling_smoke.

Final result: Ran 10 tests in 0.079s; FAILED (errors=10); process exit 1.

### tests/legacy/test_infected_w28.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_default_hold_equals_the_shipped_failed_roll_cooldown, test_failed_roll_and_missing_agent_keep_the_failed_roll_cooldown, test_non_calm_crawler_is_held_for_the_configured_seconds, setUpClass, test_an_old_file_missing_both_keys_prints_one_line_listing_every_restored_key, test_missing_herd_world_restores_the_declared_default_and_names_the_key, test_missing_hold_restores_600_so_an_older_lod_json_still_loads, test_present_keys_are_left_alone_including_an_explicit_empty_world.

Final result: Ran 11 tests in 0.079s; FAILED (failures=4, errors=4); process exit 1.

### tests/legacy/test_infected_wave.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_all_seven_descriptors_and_explicit_unsupported_fallback, test_ambiguous_membership_cannot_expire_or_refund_even_with_recovery_admitted, test_confirmed_retirement_waits_for_release_then_refunds_only_once, test_missing_member_never_counts_as_confirmed_death, test_releasing_an_ambiguous_pack_does_not_resolve_its_membership, test_retarget_requires_live_fresh_owned_evidence_and_budget, test_v2_drift_never_reaches_ecology_v1_submission, test_variant_attention_and_search_are_bounded_and_injury_is_overlay, test_visible_evidence_has_priority_then_newer_then_stronger.

Final result: Ran 16 tests in 0.146s; FAILED (errors=12); process exit 1.

### tests/legacy/test_interior_measured_catalog.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_any_changed_import_bytes_refuse_publication, test_default_off_and_untrusted_profiles_never_publish, test_empty_path_components_are_rejected_before_native_split, test_live_house_must_be_unique_and_remain_at_the_exact_bound_pose, test_native_key_remap_preserves_trusted_embedded_json, test_only_pinned_base_and_observed_full_version_are_admitted, test_pinned_and_actual_use_the_one_shared_build_matcher, test_policy_caps_and_item_groups_filter_existing_finite_allocation, test_record_longer_than_one_native_substring_survives_the_key_remap, test_rejected_attempt_is_not_retried_until_explicit_clear, test_report_and_candidate_contradictions_are_not_acceptance, test_schema_guard_rejects_nested_unknown_duplicate_types_and_excess, test_survey_geometry_and_policy_validate_authored_denominators, test_trusted_profile_build_text_is_admitted_through_the_shared_matcher, test_unknown_duplicate_and_missing_profile_fields_are_rejected, test_valid_synthetic_assertions_load_once_and_return_defensive_layouts, test_wrong_build_world_pose_and_later_ambiguity_refuse_selection.

Final result: Ran 18 tests in 0.091s; FAILED (errors=21); process exit 1.

### tests/legacy/test_interior_templates_runtime.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_abandoned_history_and_every_catalog_prop_load_and_place, test_building_templates_keep_placements_and_refusals_with_one_resolve_query, test_cached_resolve_rechecks_live_pose_and_class, test_chunk_gap_and_pin_mismatch_refuse, test_class_chunk_longer_than_one_native_substring_reaches_the_engine_whole, test_door_gap_of_at_least_point_six_metres_is_admitted, test_door_keepout_and_clearance_block_slot, test_duplicate_furnish_instance_with_different_yaw_refuses_pack, test_duplicate_group_items_refuse, test_failed_pack_cannot_retry_or_publish_partial_rows, test_file_keys_reach_the_engine_as_FileName, test_group_items_cap_is_1024, test_group_items_need_not_be_presorted, test_group_loader_sorts_items_only_once_and_refuses_duplicates_in_every_list, test_heaviest_item_name_carries_the_resolve_query_size, test_large_pack_phase_boundaries_obey_budget_and_lookups_do_not_scan, test_legacy_claim_conflict_refuses_with_reason, test_legacy_only_load_does_not_touch_legacy_files, test_measured_claim_and_production_rooms_conflict, test_missing_pack_in_both_sources_refuses_without_reading, test_model_bounds_history_and_group_bindings_are_strict, test_module_tick_finishes_admission_and_stop_cancels_pending_load, test_multiple_template_rows_for_one_live_building_preserve_duplicate_refusals, test_native_box_logger_runs_once_per_created_type_without_spawning, test_nearly_level_house_places_at_full_model_transform, test_nested_unknown_and_duplicate_keys_refuse, test_nonfinite_or_over_limit_house_counts_tilt_refusal, test_operator_profile_pack_wins_over_shipped_pack, test_overall_cap_includes_already_owned_pilot_props, test_oversize_and_non_ascii_file_refuse, test_pack_covers_a_subset_of_engine_house_classes, test_per_house_cap_and_startup_once, test_props_cap_holds_and_never_reads_during_placement, test_provisional_build_and_denominator_refuse, test_read_totals_are_refused_before_publication, test_reader_propagates_job_refusal_and_clears_partial_admission, test_reader_stages_both_schemas_without_reloading_and_resets_on_stop, test_resolve_cache_is_bounded_separates_positions_and_resets_on_stop, test_room_zero_site_refuses_when_the_template_has_rooms, test_rooms_covered_class_still_requires_rooms, test_same_live_house_cannot_bypass_per_house_cap_with_nearby_rows, test_search_only_template_cannot_cover_furniture, test_search_only_template_without_rooms_is_admitted_for_search, test_status_publishes_one_selected_state_and_recognizes_legacy_owner, test_template_slot_count_obeys_setting, test_text_list_duplicate_detection_uses_one_sort_without_linear_searches, test_text_lists_preserve_validation_and_input_order, test_tilted_and_ambiguous_live_houses_refuse, test_unknown_duplicate_missing_keys_refuse_before_native_parse, test_valid_pack_publishes_exact_reader_api_once, test_workshop_route_reads_shipped_pack_from_pbo_when_profile_pack_absent.

Final result: Ran 54 tests in 0.455s; FAILED (failures=1, errors=97); process exit 1.

### tests/legacy/test_interiors_contract.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_completion_actual_pool_cannot_reopen_to_refund_spent_units, test_completion_actual_pool_rejects_overquota_and_aliased_owners, test_completion_actual_pool_restart_reconciles_missing_building_escrow, test_completion_actual_pool_two_consumers_cannot_share_one_unit, test_completion_interrupted_allocation_cannot_be_resumed_by_resetting_site_phase, test_authored_authority_requires_every_gate, test_identity_and_candidate_collisions_do_not_depend_on_object_order.

Final result: Ran 40 tests in 0.173s; FAILED (failures=2, errors=5); process exit 1.

### tests/legacy/test_interiors_profile.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_empty_optional_chunks_have_no_index_bindings_or_files, test_real_cli_pack_obeys_runtime_reader_admission_rules, test_search_only_class_passes_assemble_validation_and_the_reader.

Final result: Ran 83 tests in 33.978s; FAILED (errors=3); process exit 1.

### tests/legacy/test_item_compatibility_audit.py — HARNESS_ROT

Requires the source substring .Find( in ReadAncestry after the implementation moved to a visited-class map; source-expression pin only.

Failing methods: test_ancestry_is_config_based_bounded_and_cycle_checked.

Final result: Ran 25 tests in 0.023s; FAILED (failures=1); process exit 1.

### tests/legacy/test_local_test_session.py — SUSPECT_PRODUCT

Six real-installer integration cases fail with travel scratch-copy input loss; see suspect 1. Synthetic fixture limitations do not explain the independently reproduced loss of an existing source file.

Failing methods: test_a_changed_spawn_preset_refuses_rollback_before_anything_changes_and_the_retry_succeeds, test_apply_and_rollback_leave_the_mission_and_profile_byte_identical, test_the_real_interiors_installer_agrees_with_the_dry_run_when_a_profile_file_is_hard_linked, test_the_real_interiors_pack_and_all_local_markers_install_and_roll_back_byte_identically, test_the_real_loot_boost_is_on_by_default_installs_last_and_rolls_back_first_byte_identically, test_the_real_snafu_and_tactical_flava_deltas_install_and_roll_back_byte_identically.

Final result: Ran 174 tests in 18.857s; FAILED (failures=6); process exit 1.

### tests/legacy/test_loot_w46.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_real_binding_helper_handles_original_refresh_and_failed_provider, test_runtime_action_uses_instance_preview_and_keeps_server_authority, test_cache_pressure_preserves_in_flight_and_positive_entries, test_decorative_cabinets_cannot_starve_a_bound_cabinet, test_only_bound_instance_gets_a_server_known_preview, test_pilot_cache_keeps_shared_request_and_entry_bounds, test_pilot_request_round_trip_is_instance_bound_and_expires, test_same_pose_decoration_cannot_reuse_a_bound_object_reply, test_spoofed_instance_key_and_decorative_cabinet_return_no_sites, test_throttled_unsent_entries_cannot_starve_the_next_request, test_refusal_cursor_uses_loaded_rows_and_shared_budget.

Final result: Ran 12 tests in 0.961s; FAILED (errors=11); process exit 1.

### tests/legacy/test_map_layers.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_delivery_destination_is_never_promoted_to_a_pin, test_malformed_or_out_of_world_text_never_yields_a_pin, test_retained_legacy_parser_extracts_only_source_position, test_group_visits_share_by_default_and_operator_can_keep_them_private, test_unvisited_catalog_entries_are_never_listed_and_count_is_bounded, test_menu_routes_toggle_clicks_before_any_group_request_is_built.

Final result: Ran 21 tests in 0.126s; FAILED (failures=1, errors=10); process exit 1.

### tests/legacy/test_native_wiring_batch_a.py — HARNESS_ROT

Exact Enforce noise-emitter filename inventory excludes the later HCXAIThrowables emitter; source inventory is not native behavior evidence.

Failing methods: test_hc_never_creates_noise_targets_and_emits_noise_only_from_search.

Final result: Ran 12 tests in 0.081s; FAILED (failures=1); process exit 1.

### tests/legacy/test_ops_admin_controls.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_failed_commit_restores_in_memory_tier, test_tier_uses_normal_commit_and_no_world_facts.

Final result: Ran 8 tests in 0.082s; FAILED (errors=2); process exit 1.

### tests/legacy/test_package.py — SUSPECT_PRODUCT

Real extracted-archive dependency closure failure; see suspect 2.

Failing methods: test_extracted_handoff_imports_the_overlay_remove_helper.

Final result: Ran 39 tests in 0.547s; FAILED (failures=1, skipped=1); process exit 1.

### tests/legacy/test_perf_capture.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_ecology_in_the_top_n_prints_once_and_unobserved_pin_still_shows, test_ecology_line_is_pinned_last_when_outside_the_top_n, test_few_modules_all_print_and_calibrated_window_uses_ms, test_few_modules_with_ecology_do_not_duplicate, test_stop_prints_one_total_and_only_the_top_modules_sorted, test_maxima_sorted_names_slow_threshold_and_window_reset, test_module_capacity_restart_and_invalid_calibration.

Final result: Ran 61 tests in 0.555s; FAILED (failures=7); process exit 1.

### tests/legacy/test_perfboot_slices.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_many_leaves_progress_in_one_tick_and_stop_discards_cursor, test_row_encoder_preserves_json_shape_and_escapes, test_snapshot_encoder_yields_without_advancing_phase, test_snapshot_save_stops_at_deadline_and_retains_job.

Final result: Ran 7 tests in 0.083s; FAILED (errors=4); process exit 1.

### tests/legacy/test_refusal_report.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_production_siphon_closed_gate_reports_from_server_start.

Final result: Ran 14 tests in 0.088s; FAILED (errors=1); process exit 1.

### tests/legacy/test_room_catalog_completion.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_anchor_bounds_duplicates_nonfinite_and_capacity_reject, test_diagnostic_catalog_world_is_case_normalised_and_build_uses_the_shared_matcher, test_diagnostic_order_falls_through_to_production_only_when_a_template_pack_is_loaded, test_disabled_bad_version_identity_and_missing_records_fail_before_queries, test_duplicate_house_and_ambiguous_native_candidates_reject, test_existing_survey_checks_and_deep_copy_survive_loader, test_failed_reads_malformed_and_oversize_loads_are_once_until_clear, test_four_buildings_are_bounded_and_invalid_requests_do_not_load, test_given_valid_synthetic_catalog_when_build_order_then_load_once_and_bind, test_house_class_pose_and_finite_coordinates_are_required, test_manual_binding_is_preserved_and_moved_house_yields_no_points, test_normal_pbo_and_client_never_read_or_bind, test_null_building_record_fails_closed_without_dereference, test_staging_rejects_later_bad_record_without_partial_publication, test_strict_keys_reject_duplicates_unknown_missing_and_escaped_names.

Final result: Ran 15 tests in 0.394s; FAILED (errors=42); process exit 1.

### tests/legacy/test_runtime_settings.py — HARNESS_ROT

Mixed translator failure and stale settings list: removed EnableMealBuffs is still expected and optional EnableMelee is treated as required. Current validator derives optional flags from the shared settings registry.

Failing methods: test_density_scales_four_budgets_without_mutating_operator_choices, test_v1_settings_file_without_v2_preferences_loads_with_v2_defaults_on, test_wrong_schema_unknown_fields_and_missing_limits_fail.

Final result: Ran 15 tests in 0.443s; FAILED (failures=2, errors=1); process exit 1.

### tests/legacy/test_s2_tactics.py — HARNESS_ROT

Old tests/unit fixture path and Enforce source-regex pins; no shipped-data failure.

Failing methods: test_marker_is_listed_in_the_acceptance_docs_and_marker_test, test_perception_only_and_native_budgets.

Final result: Ran 50 tests in 0.578s; FAILED (failures=1, errors=1); process exit 1.

### tests/legacy/test_search_binding.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_after_placement_observes_late_ce_supply_then_binds_same_handles_once, test_binder_is_registered_before_interiors_in_the_same_registry, test_client_marker_and_settings_gates_never_prepare_or_schedule, test_empty_ce_refuses_after_three_equal_delays_and_never_reactivates, test_equivalent_wrapped_storage_yaw_keeps_the_placed_binding, test_existing_epoch_rebinds_without_new_initialization_or_refill, test_gate_loss_between_retries_stops_without_another_prepare, test_initialize_permission_is_passed_through_and_never_invented, test_no_unreviewed_geometry_context_or_fallback_radius, test_refused_economy_is_terminal_and_abandons_prepared_registry, test_review_uses_rotated_storage_bounds_and_deduplicated_context_classes, test_single_hook_follows_ready_placement_and_preserves_module_scope, test_stop_during_prepare_abandons_plan_without_binding, test_stop_removes_callback_and_late_delivery_cannot_prepare, test_unplaced_duplicate_or_changed_assignment_refuses_before_observation.

Final result: Ran 15 tests in 0.099s; FAILED (errors=15); process exit 1.

### tests/legacy/test_search_economy_houses.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_house_target_goes_to_the_service_and_other_targets_take_the_pilot_path, test_house_target_is_refused_while_the_service_is_stopped, test_pilot_search_target_is_never_taken_by_the_house_service, test_wrapper_site_has_the_real_interior_site_fields, test_a_house_with_a_live_session_is_never_released, test_idle_house_is_released_while_the_busy_one_stays, test_least_recently_used_idle_house_is_released_first, test_spent_binding_releases_outside_player_range_and_new_house_binds_at_cap, test_bind_queries_per_tick_are_capped, test_commit_before_six_seconds_does_nothing_and_second_commit_never_moves_again, test_continue_requires_the_same_site_and_player_in_range, test_depletion_persists_across_restart_and_never_replays, test_empty_scan_is_not_journaled_and_is_negatively_cached_for_sixty_seconds, test_first_search_binds_existing_ce_items_and_moves_one_without_creating, test_full_journal_refuses_a_new_site_before_any_scan, test_group_item_cap_is_1024_not_256, test_journal_cap_is_4096_entries, test_nothing_is_created_split_or_refunded_when_the_move_fails, test_player_with_hands_full_or_second_session_on_one_site_is_refused, test_site_cap_stops_new_sites_but_not_bound_ones, test_stop_forgets_sessions_and_handles_but_keeps_journal, test_class_not_marked_covered_tilted_house_and_bad_sphere_refuse, test_hit_inside_sphere_starts_and_hit_outside_refuses, test_house_search_accepts_nearly_level_and_refuses_excessive_or_nan_tilt, test_non_house_target_is_not_a_house_target, test_player_at_2_4_m_is_accepted_and_at_2_6_m_refused, test_refuses_when_the_template_pack_is_not_loaded, test_site_id_follows_the_contract_formula_and_rotated_house_keeps_local_frame, test_oldest_eviction_keeps_replay_barrier_after_snapshot_roundtrip.

Final result: Ran 32 tests in 1.507s; FAILED (errors=29); process exit 1.

### tests/legacy/test_search_economy_integration.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_each_call_schedules_a_fresh_array_never_prior_state, test_fully_created_layout_schedules_exactly_those_props_once_after_bookkeeping, test_other_refusals_never_schedule, test_refused_or_rolled_back_placements_never_schedule, test_reused_props_are_not_scheduled_and_nothing_is_scheduled_twice, test_aborted_stop_cannot_release_binding_until_cleanup_completes, test_binding_cannot_replace_existing_service_or_retry_failed_open, test_binding_rejects_missing_extra_reordered_sites_wrong_epoch_build_and_source, test_bound_manifest_accepts_explicit_context_group_class_not_pilot_allowlist, test_clean_stop_with_failed_restart_cannot_rebind, test_context_bounds_empty_opportunities_and_caller_mutation_after_bind, test_context_or_source_drift_and_unadmitted_classes_are_rejected_before_open, test_failed_open_stays_sticky_across_repeated_stop_and_actual_start, test_restarted_service_revalidates_fresh_source_and_context_before_open, test_successful_binding_clean_stop_actual_start_allows_one_fresh_bind, test_forget_compacted_preserves_persistent_revisited_history, test_full_timer_ledger_preserves_history_and_cap_instead_of_eviction.

Final result: Ran 47 tests in 1.477s; FAILED (failures=2, errors=34); process exit 1.

### tests/legacy/test_search_preview_sites.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_arbitrary_house_without_cached_site_never_previews, test_cache_bounds_include_pending_and_empty_replies, test_cached_geometry_matches_resolve_boundaries_parent_and_tilt, test_empty_reply_expires_sixty_seconds_after_receipt_and_recovers, test_expired_empty_entries_keep_global_request_bound, test_invalid_unsolicited_and_wrong_sender_replies_do_not_enable_prompt, test_one_request_in_flight_and_no_preview_until_reply, test_pilot_props_keep_existing_preview_without_requests, test_reply_sites_use_loaded_covered_shape_filter_and_first_24_rows, test_rotated_house_uses_model_hit_and_world_standing, test_server_bounds_per_sender_requests_and_peer_storage, test_rpc_registration_lifecycle_ids_and_enforce_locals.

Final result: Ran 12 tests in 0.984s; FAILED (failures=1, errors=17); process exit 1.

### tests/legacy/test_search_refusal_reasons.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_admitted_start_says_nothing, test_begin_without_a_session_is_never_silent, test_busy_site_tells_the_second_player, test_different_reason_in_same_window_is_reported, test_refusal_is_logged_with_reason_and_class_but_no_player_id, test_server_refusal_tells_the_player_why_once_per_window, test_service_fault_tells_the_player, test_accepted_pilot_cabinet_still_previews_by_reach, test_furnished_cabinet_does_not_offer_search_before_pilot_acceptance.

Final result: Ran 9 tests in 0.490s; FAILED (errors=9); process exit 1.

### tests/legacy/test_stamina_configuration.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_cfg_authentication, test_decode_failure, test_drop_and_reconnect, test_experimental_activation, test_invalid_native_receipts, test_invalid_weight_receipt_clears_active_client_and_logs_refusal, test_session_resets, test_weight_scale_accessor_uses_native_when_disabled_or_suspended, test_bounded_server_loader_and_operator_opt_in, test_existing_explicit_disable_or_invalid_file_is_never_overwritten, test_fresh_server_creates_enabled_moderate_profile_and_transports_values, test_invalid_weight_scale_refuses_profile_logs_and_falls_back_to_native, test_previous_shipped_default_is_upgraded_once_and_custom_values_kept, test_profile_creation_failure_does_not_activate_or_publish_defaults, test_schema_one_profile_missing_weight_scale_uses_half_without_rewrite, test_weight_scale_transport_round_trip_and_trusted_match.

Final result: Ran 19 tests in 0.189s; FAILED (failures=18, errors=8); process exit 1.

### tests/legacy/test_stamina_hud.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_adaptive_reference_handles_maximum_permitted_load, test_half_weight_penalty_text_and_floor_reference_use_effective_loss, test_large_valid_floor_reference_keeps_nonzero_weight_bar, test_native_cached_units_and_bar, test_native_hiding_is_immediate_and_resume_refreshes, test_oversized_reference_does_not_claim_capacity_is_at_floor, test_quickbar_hide_alone_does_not_hide_stamina, test_updates_are_bounded_without_catchup, test_weight_bar_uses_native_capacity_floor, test_zero_floor_reference_uses_labeled_display_scale, test_zero_penalty_has_explicit_display_scale, test_zero_weight_scale_displays_disabled_penalty.

Final result: Ran 18 tests in 0.120s; FAILED (errors=12); process exit 1.

### tests/legacy/test_stamina_integration.py — HARNESS_ROT

Translated NativeReceipt/StageClientReceipt raises Python string-plus-bool TypeError; no real installer or native serializer failure.

Failing methods: test_installer_requires_current_opted_in_native_configuration.

Final result: Ran 12 tests in 0.051s; FAILED (errors=1); process exit 1.

### tests/legacy/test_taped_light_service.py — HARNESS_ROT

Python-port fixture signature/type assumptions no longer match the authored code; no real data/tool failure was observed.

Failing methods: test_failed_release_quarantine_survives_authored_journal_load, test_native_port_allows_only_intent_before_custody, test_partial_or_unacknowledged_fault_write_cannot_recover_ready, test_positive_release_after_changed_snapshot_keeps_intent_quarantined, test_terminal_release_failure_with_failed_quarantine_intent, test_duplicate_active_mount_is_not_a_committed_history, test_mount_source_and_cost_are_validated_on_recovery, test_orphan_removal_is_not_a_committed_history, test_pending_history_cannot_have_later_operations, test_pending_key_is_never_acknowledged_as_committed, test_recovered_removal_preserves_mount_binding_identity, test_removal_cannot_have_tape_spent_phase_or_free_source, test_removal_rejects_changed_qualified_binding, test_replay_rejects_changed_qualified_binding, test_terminal_record_budget_is_not_recycled, test_changed_build_header_blocks_load, test_corrupt_highest_intent_cannot_load_payload, test_highest_intent_without_payload_blocks, test_native_full_and_canonical_build_headers_are_the_same_build, test_other_build_headers_still_block_load, test_valid_highest_pair_loads, test_battery_drift_is_not_repaired_or_refilled, test_false_move_even_after_arrival_is_quarantined, test_hand_removal_and_remount_requires_fresh_tape, test_intent_write_failure_never_spends, test_missing_observed_prerequisites_never_spends, test_mount_spends_once_preserving_light_and_battery, test_recovery_of_unfinished_intent_is_quarantined, test_reused_key_cannot_become_different_operation, test_ruined_host_or_light_and_missing_tape_never_spends, test_spent_tape_journal_failure_has_no_refund_or_retry, test_unproven_native_attachment_cannot_be_removed, test_binding_admits_the_native_full_build_against_a_canonical_binding, test_failed_intent_ack_never_acquires_custody, test_pending_history_blocks_new_key_before_any_custody, test_failed_move_or_release_never_arms_terminal_permission, test_failed_terminal_write_consumes_permission, test_terminal_needs_release_and_exact_move_record, test_terminal_receipt_is_single_use_for_both_operations.

Final result: Ran 39 tests in 0.253s; FAILED (errors=41); process exit 1.

### tests/legacy/test_taped_light_v1.py — HARNESS_ROT

Python-port fixture signature/type assumptions no longer match the authored code; no real data/tool failure was observed.

Failing methods: test_destination_policy_is_part_of_the_replay_binding, test_mount_then_remove_into_cargo_preserves_identity_and_spends_once.

Final result: Ran 13 tests in 0.111s; FAILED (errors=2); process exit 1.

### tests/legacy/test_taped_light_v1_evidence.py — HARNESS_ROT

No unittest cases discovered (exit 5); evidence/helper-style module is not an executable product test.

Failing methods: none discovered; module reports NO TESTS RAN.

Final result: Ran 0 tests in 0.000s; NO TESTS RAN; process exit 5.

### tests/legacy/test_v1_combined_flags.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_horde_and_chain_preferences_reach_infected_start_independently, test_all_256_combinations_reject_dependencies_or_start_exact_registry, test_atmosphere_owner_obeys_preference_after_core_start, test_reload_preserves_EnableAdminMap, test_reload_preserves_EnableAlertChains, test_reload_preserves_EnableAmbientLife, test_reload_preserves_EnableAtmosphere, test_reload_preserves_EnableCampRespawn, test_reload_preserves_EnableCamps, test_reload_preserves_EnableCrafting, test_reload_preserves_EnableDebugSnapshot, test_reload_preserves_EnableEncounters, test_reload_preserves_EnableForage, test_reload_preserves_EnableGrade, test_reload_preserves_EnableGroupScaling, test_reload_preserves_EnableGroups, test_reload_preserves_EnableHordes, test_reload_preserves_EnableInfected, test_reload_preserves_EnableInfectedVariety, test_reload_preserves_EnableInteriors, test_reload_preserves_EnableLeads, test_reload_preserves_EnableMelee, test_reload_preserves_EnableProgression, test_reload_preserves_EnableSearch, test_reload_preserves_EnableSignsOfLife, test_reload_preserves_EnableTapedPackMounts, test_reload_preserves_EnableTeamPing, test_reload_preserves_EnableTravel, test_reload_preserves_EnableVehicleFlip, test_reload_preserves_EnableWorld, test_start_stop_start_has_one_module_instance_and_one_tick_callback, test_all_modules_tick_within_shared_work_budget, test_combined_real_module_stops_detach_rpc_and_core_callbacks_then_restart, test_stop_removes_queued_interior_updates_as_well_as_core_tick.

Final result: Ran 35 tests in 8.137s; FAILED (failures=288, errors=1); process exit 1.

### tests/legacy/test_v1_combined_restart.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_groups_corrupt, test_groups_stale_temp, test_groups_truncate, test_groups_zero, test_infected_corrupt, test_infected_stale_temp, test_infected_truncate, test_infected_zero, test_interior_hold_corrupt, test_interior_hold_stale_temp, test_interior_hold_truncate, test_interior_hold_zero, test_interior_records_corrupt, test_interior_records_stale_temp, test_interior_records_truncate, test_interior_records_zero, test_corrupt_event_store_denies_runtime_start_without_new_ai_or_writes, test_ecology_corrupt, test_ecology_pending_corrupt, test_ecology_pending_stale_temp, test_ecology_pending_truncate, test_ecology_pending_zero, test_ecology_stale_temp, test_ecology_truncate, test_ecology_zero, test_events_corrupt, test_events_stale_temp, test_events_truncate, test_events_zero, test_migration_corrupt, test_migration_pending_corrupt, test_migration_pending_stale_temp, test_migration_pending_truncate, test_migration_pending_zero, test_migration_stale_temp, test_migration_truncate, test_migration_zero.

Final result: Ran 49 tests in 2.427s; FAILED (failures=21, errors=16); process exit 1.

### tests/legacy/test_v1_combined_rpc.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_groups_null_context, test_groups_oversized, test_groups_replayed_nonce, test_groups_truncated, test_groups_unauthenticated, test_groups_wrong_types, test_native_gameplay_sync_server_path_never_reads_any_payload, test_events_null_context, test_events_oversized, test_events_replayed_nonce, test_events_truncated, test_events_unauthenticated, test_events_wrong_types, test_handler_inventory_includes_only_two_mod_server_requests_and_native_sync.

Final result: Ran 14 tests in 0.133s; FAILED (failures=7, errors=7); process exit 1.

### tests/legacy/test_v1_crafting_diagnostic.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_metadata_ancestry_limit_reports_incomplete_without_unbounded_walk.

Final result: Ran 24 tests in 0.126s; FAILED (errors=1); process exit 1.

### tests/legacy/test_v1_ecology_migration.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_only_exact_bounded_owned_group_is_enrolled_and_submitted, test_decode_bounds_before_native_json_and_canonicalizes_world, test_enrollment_preserves_cadence_and_rejects_unavailable_animal_destination, test_other_persisted_cohort_reservations_share_the_ce_ceiling, test_qualification_ownership_ce_or_missing_clue_vetoes_before_writes, test_rejected_geometry_still_consumes_persisted_schedule, test_terminal_failure_blocks_after_exactly_one_move, test_write_ahead_of_native_move_and_terminal_receipt, test_write_failures_latch_fault_and_never_replay_ambiguous_movement, test_each_failure_poisoned_and_preserves_ambiguous_files, test_foreign_world_and_replayed_revision_have_no_writes, test_fresh_journal_uses_lowercase_paths_and_canonical_build, test_missing_schedule_counters_cannot_reset_attempts_or_reserved_capacity, test_pending_corrupt_world_clock_or_oversize_never_reinitializes, test_recovery_preserves_capacity_and_failed_write_quarantines, test_restart_resolves_ambiguous_attempt_durably_without_replay, test_write_order_and_readback_before_clear, test_wrong_or_missing_journal_build_and_live_build_refuse_without_writes.

Final result: Ran 29 tests in 0.894s; FAILED (failures=17, errors=1); process exit 1.

### tests/legacy/test_v1_ecology_sight.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_start_build_authority_and_marker_veto_before_journal_io, test_each_disposition_logged_once_with_its_reason.

Final result: Ran 8 tests in 0.275s; FAILED (failures=1, errors=1); process exit 1.

### tests/legacy/test_v1_events_behavior.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_completed_objective_roundtrips_real_authored_journal_and_restart, test_old_delivery_image_loads_missing_additive_fields_and_cancels_safely, test_blocked_mission_is_logged_once_per_mission_per_session, test_engine_world_case_never_blocks_lowercase_sites, test_failed_announcement_stays_retryable_and_start_clears_session_memory, test_far_participant_cannot_observe_a_delivery, test_item_moves_without_a_previous_carrier_skip_context_but_still_revoke, test_participant_cap_is_the_target_load_everywhere, test_pruned_terminal_missions_never_reannounce_with_five_or_more_sites, test_roster_copies_lowercase_world_and_refresh_and_binding_compare_lowercase, test_kill_callback_only_attributes_current_joined_mission, test_late_roster_discovery_never_reannounces_current_terminal_missions, test_module_qualification_rejection_never_starts_runtime_or_rpc, test_retired_projection_carries_no_briefing_or_identity, test_delivery_cannot_claim_someone_elses_item_or_skip_custody, test_delivery_requires_observed_custody_then_exact_container, test_direct_delivery_receipt_revoked_by_later_inventory_transition, test_enrolled_killer_gets_one_lease_bound_observation, test_infected_requires_bound_live_actor_and_participant_kill_receipt, test_legacy_delivery_without_container_remains_loadable_but_not_ready, test_presence_needs_live_bound_entity_and_area_reach, test_rebinding_unleased_target_does_not_replace_active_lease, test_bounded_source_reviewed_sites_are_not_claimed_surveyed, test_native_queries_bind_real_handles_and_delivery_uses_that_container, test_native_query_rejects_nonfinite_or_oversized_inputs_before_engine_call, test_native_selection_refuses_ambiguity_overflow_player_custody_and_unknown_economy, test_settings_rejects_oversized_binding_and_provenance_fields, test_unqualified_unsurveyed_sites_are_not_admitted.

Final result: Ran 35 tests in 0.318s; FAILED (failures=29); process exit 1.

### tests/legacy/test_v1_groups.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_additive_legacy_roles_and_transfer_cleanup, test_officer_matrix_and_owner_only_role_assignment, test_radio_matching_requires_a_shared_actual_frequency, test_required_native_and_privacy_wiring, test_visibility_settings_are_supported_and_bounded, test_visit_requires_actual_proximity_and_is_bounded_persistent_with_privacy_opt_out, test_one_bounded_discovery_pass_observes_six_players_with_one_commit, test_roles_visits_and_legacy_defaults_reopen_through_actual_journal, test_group_map_menu_closes_when_map_ownership_is_lost, test_member_projection_applies_real_radio_and_los_gates, test_client_can_send_role_assignment_without_changing_retry_payload, test_group_map_toggle_requires_map_ownership.

Final result: Ran 20 tests in 0.088s; FAILED (failures=1, errors=11); process exit 1.

### tests/legacy/test_v1_native_noise_vision.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_already_complete_repeat_is_silent, test_client_side_completion_emits_nothing, test_completing_commit_emits_exactly_once_after_the_commit, test_missing_module_commits_nothing_and_emits_nothing, test_refused_or_failed_commit_is_silent, setUpClass, test_given_held_item_without_inventory_or_attachments_then_unlit, test_given_lit_attachment_at_the_last_allowed_index_then_lit, test_given_lit_attachment_beyond_the_cap_then_never_seen, test_given_lit_headgear_and_empty_hands_then_lit, test_given_lit_headgear_with_unlit_hands_then_lit, test_given_lit_held_item_then_lit_without_looking_further, test_given_lit_weapon_attachment_on_unlit_held_item_then_lit_after_visiting_it, test_given_many_unlit_attachments_then_exactly_eight_are_visited, test_given_no_player_or_empty_hands_and_head_then_unlit, test_given_unlit_headgear_then_unlit, test_given_working_chemlight_or_gas_lamp_in_hand_then_lit, test_player_factor_combines_clothing_clock_and_light_reading_each_once, test_given_no_item_or_non_light_item_then_unlit_even_when_working, test_given_switched_off_light_of_every_native_kind_then_unlit, test_given_working_chemlight_then_lit_although_native_is_light_source_is_false, test_given_working_gas_lamp_then_lit_although_native_is_light_source_is_false, test_given_working_light_of_every_native_kind_then_lit, test_client_completion_stays_silent_even_when_the_site_completed, test_completed_search_emits_exactly_one_noise_at_the_actor, test_phase_of_reads_the_bound_site_or_minus_one, test_refusal_failure_repeat_cancel_stop_and_unbound_site_are_silent, test_client_falls_back_silently_with_zero_downstream_calls, test_config_path_constant_is_the_vanilla_reference, test_dead_null_missing_system_or_missing_game_are_silent, test_server_emits_once_with_config_path_actor_and_actor_position, test_admitted_server_multiplies_native_once_by_the_captured_target_factor, test_client_returns_exact_native_with_no_admission_and_no_factor, test_client_with_the_real_gate_never_probes_the_acceptance_marker, test_closed_server_gate_returns_exact_native_without_computing_a_factor, test_default_without_a_marker_admits_logs_experimental_and_probes_once, test_disable_marker_closes_the_gate_and_the_override_is_exactly_native, test_end_to_end_unlit_night_player_is_shorter_and_lit_chemlight_longer_than_native, test_missing_game_or_missing_captured_player_keeps_exact_native, test_the_target_is_the_player_captured_by_the_constructor.

Final result: Ran 49 tests in 0.277s; FAILED (errors=41); process exit 1.

### tests/legacy/test_v1_weather.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: setUpClass, test_authored_world_and_exact_engine_build_gate_are_cached, test_available_noise_system_keeps_relay_range_guards, test_dawn_boundary_restores_daytime_limits_once, test_daytime_start_leaves_limits_full_and_never_forces_a_forecast, test_delegation_probe_is_bounded_once_and_rejects_comment_spoofing, test_dusk_boundary_caps_storm_cloud_once_and_is_idempotent, test_dusk_callback_does_nothing_without_a_game_instance, test_enabled_executes_delegation_and_server_guards, test_missing_noise_system_preserves_vanilla_and_logs_once, test_native_range_is_sampled_at_emission_source_and_disabled_is_identity, test_night_forecasts_cap_cloud_rain_and_wind_even_with_lagging_storm_cloud, test_night_limits_are_server_only_and_need_the_started_chernarus_owner, test_owned_forecasts_use_only_the_requested_native_phenomenon, test_startup_at_night_during_a_storm_caps_actual_overcast_natively, test_startup_at_night_with_clear_sky_limits_without_forcing_a_change, test_startup_blocks_foreign_drivers_and_uses_synced_native_lighting_once, test_startup_registers_one_boundary_check_and_non_chernarus_registers_none, test_stock_disabled_weather_xml_and_absent_file_delegate_to_script, test_stop_uses_the_queue_category_that_scheduled_the_callback, test_stopped_owner_removes_the_dusk_callback_and_a_late_run_writes_nothing, test_volumetric_fog_delegates_when_unadmitted_and_bounds_native_writes.

Final result: Ran 29 tests in 0.496s; FAILED (failures=65, errors=1); process exit 1.

### tests/legacy/test_v1_weather_alerts.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_disabled_weather_preserves_range_without_sampling_environment, test_enabled_weather_shrinks_only_relay_range_at_frozen_source.

Final result: Ran 2 tests in 0.019s; FAILED (errors=2); process exit 1.

### tests/legacy/test_v2_admission.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_start_prints_the_v2_summary_before_the_initialized_line, test_the_summary_lists_every_v2_preference_from_the_settings_class.

Final result: Ran 7 tests in 0.028s; FAILED (failures=2); process exit 1.

### tests/legacy/test_v2_decay.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_monotone_persisted_decay_and_population_preserving_segment.

Final result: Ran 1 test in 0.005s; FAILED (failures=1); process exit 1.

### tests/legacy/test_v2_escalation.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_escalation_curves_are_monotone_capped_inputs_only, test_memory_fades_in_three_days_and_scales_existing_cohort_within_caps.

Final result: Ran 2 tests in 0.016s; FAILED (errors=2); process exit 1.

### tests/legacy/test_v2_holdouts.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_day_zero_occupancy_and_post_raid_world_upsert, test_publish_refusal_does_not_dirty_store_and_logs_only_reason_changes.

Final result: Ran 5 tests in 0.171s; FAILED (failures=1, errors=1); process exit 1.

### tests/legacy/test_v2_leads.py — STALE_EXPECTATION

Expects string.printable (100 characters) to become a 105-character solo group key. SoloGroup now refuses identity lengths above 91 to respect the 96-character token limit.

Failing methods: test_solo_identity_keys_are_token_safe_in_both_delivery_paths.

Final result: Ran 3 tests in 0.007s; FAILED (failures=1); process exit 1.

### tests/legacy/test_v2_loot_refresh.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_revisit_after_jittered_real_days_survives_timestamp_roundtrip.

Final result: Ran 1 test in 0.004s; FAILED (errors=1); process exit 1.

### tests/legacy/test_v2_materializer.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_caps_and_unpolled_proposal_becomes_private_place_trace.

Final result: Ran 2 tests in 0.045s; FAILED (errors=1); process exit 1.

### tests/legacy/test_v2_pins.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_death_counts_are_separate_on_client_and_server, test_interrupted_promotion_recovers_valid_pending_image_and_retries, test_legacy_death_ids_migrate_only_in_the_validated_death_store, test_named_place_lead_and_group_trail_cap, test_partial_staging_preserves_valid_primary_and_invalid_files_fail_closed, test_publish_uses_own_kind_and_shared_staged_save, test_unplaced_shelter_yields_no_trail_pin.

Final result: Ran 8 tests in 0.033s; FAILED (errors=7); process exit 1.

### tests/legacy/test_v2_polish.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_hint_spacing_and_character_memory.

Final result: Ran 2 tests in 0.004s; FAILED (errors=1); process exit 1.

### tests/legacy/test_v2_scenes.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_successful_scene_clears_refusal_after_optional_note_attempt.

Final result: Ran 3 tests in 0.027s; FAILED (errors=2); process exit 1.

### tests/legacy/test_v2_shelters.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_catalog_and_repeated_start_stop.

Final result: Ran 4 tests in 0.053s; FAILED (errors=1); process exit 1.

### tests/legacy/test_v2_signs_of_life.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_native_fire_selection_ordering_force_hints_and_caps.

Final result: Ran 1 test in 0.009s; FAILED (errors=1); process exit 1.

### tests/legacy/test_v2_weather_days.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_seeded_days_morning_lift_and_observed_storm_calm.

Final result: Ran 1 test in 0.032s; FAILED (failures=1); process exit 1.

### tests/legacy/test_variety_w40.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_existing_crawler_cluster_uses_room_catalog_without_relocation, test_role_change_invalidates_pose_once_and_same_role_keeps_it, test_native_handler_reapplies_role_only_on_a_calm_move_command, test_native_modes_admitted_but_custom_graphs_remain_unavailable, test_role_stances_cover_native_range_without_changing_mind_idle.

Final result: Ran 6 tests in 0.021s; FAILED (failures=3, errors=2); process exit 1.

### tests/legacy/test_w32_infected.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_loaded_routes_report_ready_not_degraded, test_operator_off_and_missing_data_stay_honest, test_each_route_endpoint_pair_binds_in_both_directions, test_shipped_manifest_admits_routes_through_the_authored_binder.

Final result: Ran 5 tests in 0.083s; FAILED (errors=4); process exit 1.

### tests/legacy/test_w36_trade.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_bounded_road_search_retains_cursor_and_waypoint_order, test_group_walk_uses_road_order_and_does_not_override_combat, test_restart_mid_journey_records_one_loss_without_creating_cargo.

Final result: Ran 11 tests in 0.119s; FAILED (errors=3); process exit 1.

### tests/legacy/test_w37_conflict.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_conflict_contributor_follows_snapshot_module_lifecycle, test_claimed_lease_prevents_far_roll_and_observed_result_waits_for_all_viewers, test_pending_site_receipt_rotates_without_stalling_other_sites.

Final result: Ran 12 tests in 0.069s; FAILED (errors=3); process exit 1.

### tests/legacy/test_w38_pinned_situations.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_road_threats_use_only_nearby_road_nodes_and_never_change_route, test_signal_scan_does_not_activate_visible_or_owned_smoke.

Final result: Ran 6 tests in 0.024s; FAILED (errors=2); process exit 1.

### tests/legacy/test_w38_situations.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_empty_incident_never_spends_its_durable_stock_lease, test_native_incident_never_claims_nearby_loose_loot, test_physical_stock_is_the_same_handle_and_empty_stock_is_not_refilled, test_policy_refuses_zero_nan_or_unbounded_override, test_profiles_default_on_and_empty_selection_retries, test_threat_creation_checks_visibility_and_shared_budget_before_each_body, test_reward_cache_exposes_real_stock_without_creating_inventory.

Final result: Ran 12 tests in 0.067s; FAILED (failures=1, errors=6); process exit 1.

### tests/legacy/test_w39_wildlife_providers.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_carcass_creation_checks_authority_hidden_and_journal_before_spawning, test_durable_site_claim_precedes_economy_and_creation_and_never_replays, test_hidden_check_refuses_overflow_or_any_visible_observer, test_config_bounds_and_explicit_default_preferences, test_service_is_wired_and_every_new_mission_file_is_named_for_integration.

Final result: Ran 10 tests in 0.241s; FAILED (failures=2, errors=3); process exit 1.

### tests/legacy/test_w43_seasons.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_four_routes_materialize_through_existing_finite_nodes, test_visible_candidate_cannot_materialize.

Final result: Ran 6 tests in 0.446s; FAILED (failures=2); process exit 1.

### tests/legacy/test_w57_claimtargets.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_bounded_native_storage_scan_requires_actual_cargo_and_budget.

Final result: Ran 9 tests in 0.118s; FAILED (errors=1); process exit 1.

### tests/legacy/test_w58_situations.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_budget_denial_has_finite_named_give_up, test_budget_refusal_defers_then_fires_same_leased_item_once, test_minimum_retry_policy_still_defers_the_initial_refusal, test_player_item_and_visible_stock_are_never_consumed, test_smoke_retries_publish_the_place_fact_only_once, test_wiped_or_destroyed_group_still_reaches_the_dead_outcome, test_wreck_query_refuses_radius_before_native_query, test_inventory_cursor_charges_before_each_step_and_retains_nested_smoke, test_only_captured_owner_can_drop_and_only_same_handle_is_activated.

Final result: Ran 13 tests in 0.087s; FAILED (errors=10); process exit 1.

### tests/legacy/test_w64_tickperf.py — HARNESS_ROT

Authored-code Python fixture lacks current Enforce symbols, state or collaborators; any accompanying source-text/value pins do not establish a product defect.

Failing methods: test_cursor_calls_share_one_tick_slice_instead_of_resetting_per_slot, test_holdout_tick_spreads_native_ports_and_visits_each_body_once, test_pack_parser_yields_and_matches_existing_strict_results, test_production_pack_adapter_reads_each_leaf_once_across_yields.

Final result: Ran 4 tests in 0.131s; FAILED (errors=16); process exit 1.

### tests/legacy/test_w67_admintp.py — STALE_EXPECTATION

Pins destination order and expects a live filesystem-marker check in HCMove. Admission is now cached by HCStart/OnStart; the fixture bypasses startup and supplies m_Enabled=True despite its disabled marker.

Failing methods: test_destination_builder_resumes_one_shared_row_per_tick, test_all_disable_paths_refuse_before_any_probe.

Final result: Ran 16 tests in 0.254s; FAILED (failures=2); process exit 1.

### tests/legacy/test_w68_spawnring.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_materializer_checks_every_observer_before_reserving, test_native_patrol_config_output_uses_custom_ring, test_readiness_refreshes_when_qualified_count_changes, test_site_adapter_uses_ring_even_when_scaled_down.

Final result: Ran 14 tests in 0.160s; FAILED (failures=1, errors=3); process exit 1.

### tests/legacy/test_w69_smokefire.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_expired_attempts_allow_new_houses_past_lifetime_cap, test_partial_transfer_retries_without_duplicate_fire_or_fuel, test_real_items_transfer_once_and_match_is_spent, test_reclamation_and_dispatch_progress_under_sustained_budget_exhaustion, test_reclamation_does_not_starve_funded_holdout_with_two_units_left.

Final result: Ran 18 tests in 0.158s; FAILED (failures=2, errors=3); process exit 1.

### tests/legacy/test_w70_roleplan.py — HARNESS_ROT

Enforce-to-Python translation produces invalid Python; any accompanying source-expression pins are not product evidence.

Failing methods: test_perceived_incident_preempts_a_new_role_pick, test_tick_opt_out_and_budget_refusal_touch_no_group, test_table_images_do_not_allow_zero_filled_missing_row_keys.

Final result: Ran 12 tests in 0.104s; FAILED (failures=1, errors=2); process exit 1.

### tests/legacy/test_wreck_enroll_reasons.py — HARNESS_ROT

Enforce source-text/regex, scalar-extraction or removed internal-method assertion; not executable shipped-data/tool evidence.

Failing methods: test_a_good_enroll_clears_the_enroll_cause, test_full_table_and_failed_save_are_two_named_reasons, test_missing_player_names_the_session_reason_and_logs_once, test_other_enroll_failures_keep_the_broad_storage_reason.

Final result: Ran 4 tests in 0.031s; FAILED (failures=4); process exit 1.

## Successful file invocations

- tests/legacy/test_admin_client_feedback.py: Ran 4 tests in 0.001s; OK.
- tests/legacy/test_auditkits.py: Ran 5 tests in 0.026s; OK.
- tests/legacy/test_auditpick_house_binding.py: Ran 3 tests in 0.001s; OK.
- tests/legacy/test_camera_mode_log.py: Ran 4 tests in 0.001s; OK.
- tests/legacy/test_caravan_status_publish.py: Ran 2 tests in 0.004s; OK.
- tests/legacy/test_ce_probe.py: Ran 58 tests in 6.785s; OK.
- tests/legacy/test_crafting_completion.py: Ran 14 tests in 1.431s; OK.
- tests/legacy/test_crafting_contract.py: Ran 13 tests in 0.559s; OK.
- tests/legacy/test_crafting_families.py: Ran 8 tests in 4.013s; OK.
- tests/legacy/test_crafting_families_native.py: Ran 13 tests in 0.026s; OK.
- tests/legacy/test_e1_sources.py: Ran 9 tests in 0.056s; OK.
- tests/legacy/test_ecology_native.py: Ran 12 tests in 0.256s; OK.
- tests/legacy/test_expansion_ai_lifecycle.py: Ran 10 tests in 0.172s; OK.
- tests/legacy/test_fuel_siphon_production.py: Ran 13 tests in 0.086s; OK.
- tests/legacy/test_fuel_transfer.py: Ran 10 tests in 0.009s; OK.
- tests/legacy/test_gameplay_delta.py: Ran 46 tests in 0.309s; OK.
- tests/legacy/test_group_clock.py: Ran 13 tests in 0.065s; OK.
- tests/legacy/test_hc_winter_terrain.py: Ran 1 test in 0.002s; OK.
- tests/legacy/test_infected_competence.py: Ran 47 tests in 4.766s; OK.
- tests/legacy/test_infected_variety_install.py: Ran 10 tests in 0.564s; OK.
- tests/legacy/test_infected_variety_routes.py: Ran 4 tests in 0.185s; OK.
- tests/legacy/test_infected_variety_w56.py: Ran 2 tests in 0.012s; OK.
- tests/legacy/test_infected_variety_w60.py: Ran 2 tests in 0.327s; OK.
- tests/legacy/test_interior_density_trim.py: Ran 4 tests in 0.017s; OK.
- tests/legacy/test_interior_sampler.py: Ran 201 tests in 63.413s; OK.
- tests/legacy/test_menu_input.py: Ran 3 tests in 0.015s; OK.
- tests/legacy/test_observer_transition.py: Ran 23 tests in 0.100s; OK.
- tests/legacy/test_probe_runtime.py: Ran 74 tests in 3.986s; OK.
- tests/legacy/test_s1_formations.py: Ran 47 tests in 0.656s; OK.
- tests/legacy/test_s3_carfix.py: Ran 30 tests in 0.026s; OK.
- tests/legacy/test_salvage_tools.py: Ran 8 tests in 0.208s; OK.
- tests/legacy/test_search_economy.py: Ran 9 tests in 0.118s; OK.
- tests/legacy/test_search_economy_native.py: Ran 6 tests in 0.212s; OK.
- tests/legacy/test_search_economy_policy.py: Ran 5 tests in 2.138s; OK.
- tests/legacy/test_search_economy_recovery.py: Ran 9 tests in 0.304s; OK.
- tests/legacy/test_search_supply_provider.py: Ran 80 tests in 4.178s; OK.
- tests/legacy/test_siphon_fuel_action.py: Ran 26 tests in 1.230s; OK.
- tests/legacy/test_stamina_policy.py: Ran 19 tests in 0.024s; OK.
- tests/legacy/test_stamina_transport_probe.py: Ran 11 tests in 0.035s; OK.
- tests/legacy/test_survival_ideas.py: Ran 1 test in 0.009s; OK.
- tests/legacy/test_taped_light_probe.py: Ran 125 tests in 14.002s; OK.
- tests/legacy/test_taped_light_proxy_slot_table.py: Ran 7 tests in 6.805s; OK.
- tests/legacy/test_tilt_rule.py: Ran 2 tests in 0.006s; OK.
- tests/legacy/test_utility_review.py: Ran 41 tests in 2.717s; OK.
- tests/legacy/test_v1_crafting.py: Ran 5 tests in 0.165s; OK.
- tests/legacy/test_v1_ecology_resources.py: Ran 5 tests in 0.100s; OK.
- tests/legacy/test_v2_camps.py: Ran 2 tests in 0.001s; OK.
- tests/legacy/test_v2_grade.py: Ran 1 test in 0.044s; OK.
- tests/legacy/test_v2_lighting.py: Ran 1 test in 0.033s; OK.
- tests/legacy/test_v2_morse.py: Ran 1 test in 0.001s; OK.
- tests/legacy/test_v2_observer_gate.py: Ran 1 test in 0.006s; OK.
- tests/legacy/test_v2_world.py: Ran 3 tests in 0.037s; OK.
- tests/legacy/test_v2_wreck_salvage.py: Ran 1 test in 0.007s; OK.
- tests/legacy/test_v2_xai_living.py: Ran 1 test in 0.001s; OK.
- tests/legacy/test_w39_wildlife_habitats.py: Ran 3 tests in 0.008s; OK.
- tests/legacy/test_w47_shelters.py: Ran 3 tests in 0.004s; OK.
- tests/legacy/test_w61_trade.py: Ran 3 tests in 0.026s; OK.
- tests/legacy/test_w65_claimselect.py: Ran 6 tests in 0.091s; OK.
- tests/legacy/test_weather_probe.py: Ran 50 tests in 0.538s; OK.
- tests/legacy/test_weather_report.py: Ran 134 tests in 0.543s; OK.
- tests/legacy/test_workshop_meta.py: Ran 3 tests in 0.108s; OK.

## Unresolved work

The two verified tooling suspects require fixes in their owning scope. The 241 harness classifications and five stale-expectation classifications remain quarantined and unchanged. This task does not migrate, repair or endorse the translated tests. No native compile, boot, client, gameplay, performance or multiplayer experiment was performed or accepted.
