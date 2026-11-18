"""W1.3 installed evidence and actual offline TDD receipts.

The matrix is derived from the installed read-only config/probe data, not a
synthetic gameplay fixture. Every behavioral collaborator used by the tests is
explicitly synthetic. This record establishes no runtime acceptance.
The service reads the compiled HCTapedLightCatalog data; this review record is
kept outside the mission so it does not expand the portable package allowlist.
"""
import json

EVIDENCE = json.loads(r'''
{
  "schema_version": 1,
  "issue": "#56",
  "task": "W1.3",
  "acceptance": "PENDING",
  "qualification": "Tier S server_qualified only; client_pending for every pair",
  "game_build": "1.30.164289",
  "provenance": {
    "classification_sha256": "9d54882a47c096a27e8ec5ad0022a6f11673d7e4a8d43769e4d4524e90a8f6dd",
    "observations_sha256": "609722ff6e1463241257c7565b9d3842cf1f47505a7f757c1d79ca44c479fe88",
    "report_tool_sha256": "a8b90cc5c1650e4028b7b64707e39be615137863bae2726860baa95923e85c69",
    "classification_source_rows_sha256": "fefc20d0a3ec9628f56397c70797a197e1349cab23dc653374aae739118bc38c",
    "scripts_pbo_sha256": "09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a"
  },
  "inputs": {
    "classification": "~/.cache/hollow-country/experiments/taped-light-probe-004/classification.json",
    "observations": "~/.cache/hollow-country/experiments/taped-light-probe-006/observations.json"
  },
  "report_counts": {
    "server_qualified": 26,
    "geometry_missing": 0,
    "not_server_evidencable": 415,
    "excluded": 141,
    "pending": 2,
    "hosts": 584,
    "client_pending": 26,
    "out_of_v1_scope": 415,
    "host_light_pairs": {
      "geometry_missing": 28,
      "not_server_evidencable": 830,
      "pending": 2,
      "server_qualified": 26
    },
    "reasons": {
      "classification_excluded": 141,
      "native_attach_with_proxy_config_slot": 14,
      "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite": 12,
      "no_native_light_slot": 415,
      "pending_client": 2
    }
  },
  "integrity": {
    "cleanup_clean": true,
    "issues": [],
    "unexpected_rows": []
  },
  "pairs": [
    {
      "host": "AK101",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardAK",
      "prerequisite_class": "AK_RailHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardAK",
          "handguard": "AK_RailHndgrd",
          "found_type": "AK_RailHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "AK101_Black",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardAK",
      "prerequisite_class": "AK_RailHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardAK",
          "handguard": "AK_RailHndgrd",
          "found_type": "AK_RailHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "AK101_Green",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardAK",
      "prerequisite_class": "AK_RailHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardAK",
          "handguard": "AK_RailHndgrd",
          "found_type": "AK_RailHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "AK74",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardAK",
      "prerequisite_class": "AK_RailHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardAK",
          "handguard": "AK_RailHndgrd",
          "found_type": "AK_RailHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "AK74_Black",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardAK",
      "prerequisite_class": "AK_RailHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardAK",
          "handguard": "AK_RailHndgrd",
          "found_type": "AK_RailHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "AK74_Green",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardAK",
      "prerequisite_class": "AK_RailHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardAK",
          "handguard": "AK_RailHndgrd",
          "found_type": "AK_RailHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "AKM",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardAK",
      "prerequisite_class": "AK_RailHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardAK",
          "handguard": "AK_RailHndgrd",
          "found_type": "AK_RailHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "AKM_Gold",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardAK",
      "prerequisite_class": "AK_RailHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardAK",
          "handguard": "AK_RailHndgrd",
          "found_type": "AK_RailHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "ASVAL",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "Aug",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "Colt1911",
      "root": "CfgWeapons",
      "light": "TLRLight",
      "slot": "pistolFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "TLRLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_tlr.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:32"
    },
    {
      "host": "CZ75",
      "root": "CfgWeapons",
      "light": "TLRLight",
      "slot": "pistolFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "TLRLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_tlr.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:32"
    },
    {
      "host": "Engraved1911",
      "root": "CfgWeapons",
      "light": "TLRLight",
      "slot": "pistolFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "TLRLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_tlr.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:32"
    },
    {
      "host": "FNX45",
      "root": "CfgWeapons",
      "light": "TLRLight",
      "slot": "pistolFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "TLRLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_tlr.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:32"
    },
    {
      "host": "FNX45_arrow",
      "root": "CfgWeapons",
      "light": "TLRLight",
      "slot": "pistolFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "TLRLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_tlr.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:32"
    },
    {
      "host": "Glock19",
      "root": "CfgWeapons",
      "light": "TLRLight",
      "slot": "pistolFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "TLRLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_tlr.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:32"
    },
    {
      "host": "Glock19_Tan",
      "root": "CfgWeapons",
      "light": "TLRLight",
      "slot": "pistolFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "TLRLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_tlr.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:32"
    },
    {
      "host": "M4A1",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardM4",
      "prerequisite_class": "M4_RISHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardM4",
          "handguard": "M4_RISHndgrd",
          "found_type": "M4_RISHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "M4A1_Black",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardM4",
      "prerequisite_class": "M4_RISHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardM4",
          "handguard": "M4_RISHndgrd",
          "found_type": "M4_RISHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "M4A1_Green",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardM4",
      "prerequisite_class": "M4_RISHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardM4",
          "handguard": "M4_RISHndgrd",
          "found_type": "M4_RISHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "MP5K",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "weaponHandguardMP5",
      "prerequisite_class": "MP5_RailHndgrd",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": true,
        "route": "after_prerequisite_handguard",
        "evaluated_attempt": "variant",
        "base_attempt": {
          "can_add": false,
          "attach_ok": false,
          "found_type": "",
          "beam": null
        },
        "variant_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "prerequisite": {
          "slot": "weaponHandguardMP5",
          "handguard": "MP5_RailHndgrd",
          "found_type": "MP5_RailHndgrd",
          "rail_functional": true,
          "attached": true
        },
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "SCARH",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "SCARH_Black",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "SCARL",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "SCARL_Black",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_enumeration_failed",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "host": "UMP45",
      "root": "CfgWeapons",
      "light": "UniversalLight",
      "slot": "weaponFlashlight",
      "prerequisite_slot": "",
      "prerequisite_class": "",
      "evidence": {
        "host_has_slot": true,
        "selection": "",
        "selection_on_model": false,
        "memory_point": false,
        "bone_index": -1,
        "light_fits": true,
        "can_add": true,
        "attach_ok": true,
        "requires_prerequisite": false,
        "route": "direct",
        "evaluated_attempt": "base",
        "base_attempt": {
          "can_add": true,
          "attach_ok": true,
          "found_type": "UniversalLight",
          "beam": true
        },
        "variant_attempt": null,
        "prerequisite": null,
        "model_evidence": "proxy_config_slot",
        "proxy_selection": "proxy:/dz/weapons/attachments/light/weaponlight_universal.001",
        "resolution_status": "resolution_vertex_missing",
        "resolution_lod": null,
        "resolution_selection": null,
        "resolution_vertex": null,
        "proxy_bone_index": null,
        "proxy_bone_name": null,
        "proxy_bone_tried": null,
        "bone_object_matches_light": null,
        "client_pending": true,
        "client_required": false
      },
      "reason": "native_attach_with_proxy_config_slot",
      "switch_action": "ActionTurnOnWeaponFlashlight.c:27"
    }
  ],
  "unobserved_axes": {
    "beam": "pending",
    "switch": "pending",
    "two_client_presentation": "pending",
    "removal_by_hand": "pending",
    "tape_consumption": "pending",
    "persistence": "pending"
  },
  "source_policy": {
    "tape_units": 1,
    "max_distance": 2,
    "return_to": "native free cargo; refuse if full",
    "catalog": "HCTapedLightCatalog.c (compiled data read by service adapter)",
    "marker": "$profile:HollowCountry/acceptance/taped_light.disable",
    "production_qualified": false,
    "evidence_record": "tests/unit/test_taped_light_v1_evidence.py (source facts, not a synthetic observation)"
  },
  "tdd": {
    "red_command": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_v1 -v",
    "red_actual": "Ran 18 tests; FAILED (failures=2, errors=5). Cargo removal: 0 != 5; changed return policy: 3 != 0; missing native/catalog/action files.",
    "green": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_service tests.unit.test_taped_light_v1 -v: Ran 50 tests, OK.",
    "additional_red": [
      {
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_v1.V1NativeSelectionTests -v",
        "actual": "Ran 3 tests; FAILED (failures=1). Client reservation helper returned True; expected False."
      },
      {
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_v1.V1ReservedDestinationTests -v",
        "actual": "Ran 1 test; FAILED (failures=1). Reserved final free cargo cell was reselected and refused (False is not true)."
      }
    ],
    "focused_final": {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_service tests.unit.test_taped_light_v1 tests.unit.test_taped_light_report tests.unit.test_taped_light_probe",
      "actual": "Ran 366 tests in 11.972s; OK."
    },
    "required_checks": {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_script_syntax tests.unit.test_acceptance_markers",
      "actual": "Ran 44 tests in 1.180s; FAILED (failures=1). Sole failure: ChecklistTraceabilityTests.test_every_marker_in_current_source_is_in_the_checklist; missing the two new taped-light entries in docs/LOCAL_ACCEPTANCE_V1.md. All syntax checks pass.",
      "outside_scope_lead_action": true
    },
    "full_initial": {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit",
      "actual": "Ran 3625 tests in 274.575s; FAILED (failures=3, errors=2, skipped=1).",
      "failures": [
        "ChecklistTraceabilityTests.test_every_marker_in_current_source_is_in_the_checklist (outside scope; lead adds two entries)",
        "GetVersionSiteTests.test_every_get_version_site_feeds_the_shared_matcher (fixed by existing journal build reader)",
        "SourceScanTests.test_no_runtime_script_compares_or_stamps_the_build_literal (fixed by HCBuildIdentity.Matches/Canonical)"
      ],
      "errors": [
        "InstallRollback.test_handoff_includes_the_authored_gameplay_files (fixed: evidence moved from mission to owned test fixture)",
        "PackageBehavior.test_operator_settings_and_install_rollback_guide_are_packaged (fixed: evidence moved from mission to owned test fixture)"
      ]
    },
    "integration_green": {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_service tests.unit.test_taped_light_v1 tests.unit.test_build_identity tests.unit.test_gameplay_delta tests.unit.test_package",
      "actual": "Ran 131 tests in 2.291s; OK (skipped=1)."
    },
    "full_final": {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit",
      "actual": "Ran 3625 tests in 255.695s; FAILED (failures=1, skipped=1).",
      "sole_failure": "ChecklistTraceabilityTests.test_every_marker_in_current_source_is_in_the_checklist: docs/LOCAL_ACCEPTANCE_V1.md needs the marker and HCTapedLightAdmission.Qualified literals; outside W1.3 ownership.",
      "source_build_and_package_failures": "resolved; zero errors in final suite"
    }
  },
  "deferred": [
    "#58: non-native slots, backpacks, helmets and other guns",
    "Final-source DayZDiag/PBO compile, native mount/remove/tape and inventory races",
    "Two-client beam, switch and presentation",
    "Crash/save recovery and native reservation/replication behavior; journal readback is not fsync",
    "Target-load benchmark for 3\u20136 players"
  ],
  "missing_project_inputs": [
    "docs/SPECIFICATION.md",
    "docs/specs/001-survival-overhaul/spec.md"
  ],
  "native_api_cache": "~/.cache/hollow-country/native-scripts/scripts-1.30.164289",
  "native_api_evidence": [
    {
      "api": "IsServer",
      "file_line": "3_Game/Global/Game.c:1120",
      "declaration": "proto native bool\t\tIsServer();"
    },
    {
      "api": "GetVersion",
      "file_line": "3_Game/Global/Game.c:942",
      "declaration": "proto void\t\t\t\t\tGetVersion( out string version );"
    },
    {
      "api": "ConfigGetTextArray",
      "file_line": "3_Game/Global/Game.c:558",
      "declaration": "proto native void\t\tConfigGetTextArray(string path, out TStringArray values);"
    },
    {
      "api": "GetInventory",
      "file_line": "3_Game/Entities/EntityAI.c:1884",
      "declaration": "proto native GameInventory GetInventory();"
    },
    {
      "api": "FindAttachmentBySlotName",
      "file_line": "3_Game/Entities/EntityAI.c:1897",
      "declaration": "EntityAI FindAttachmentBySlotName(string slot_name)"
    },
    {
      "api": "GetHierarchyRootPlayer",
      "file_line": "3_Game/Entities/EntityAI.c:802",
      "declaration": "GetHierarchyRootPlayer().AddItemToDelete(this);"
    },
    {
      "api": "GetCompEM",
      "file_line": "3_Game/Entities/EntityAI.c:3409",
      "declaration": "ComponentEnergyManager GetCompEM()"
    },
    {
      "api": "GetPersistentID",
      "file_line": "3_Game/Entities/EntityAI.c:3374",
      "declaration": "proto void GetPersistentID( out int b1, out int b2, out int b3, out int b4 );"
    },
    {
      "api": "GetType",
      "file_line": "3_Game/Entities/Object.c:467",
      "declaration": "string GetType()"
    },
    {
      "api": "IsAlive",
      "file_line": "3_Game/Entities/Object.c:517",
      "declaration": "bool IsAlive()"
    },
    {
      "api": "IsDamageDestroyed",
      "file_line": "3_Game/Entities/Object.c:981",
      "declaration": "proto native bool   IsDamageDestroyed();"
    },
    {
      "api": "IsKindOf",
      "file_line": "3_Game/Entities/Object.c:511",
      "declaration": "bool IsKindOf(string type)"
    },
    {
      "api": "GetHealth01",
      "file_line": "3_Game/Entities/Object.c:1001",
      "declaration": "proto native float  GetHealth01(string zoneName, string healthType);"
    },
    {
      "api": "GetPosition",
      "file_line": "3_Game/Entities/Object.c:287",
      "declaration": "proto native vector GetPosition();"
    },
    {
      "api": "ConfigIsExisting",
      "file_line": "3_Game/Entities/Object.c:929",
      "declaration": "proto native bool\t\tConfigIsExisting(string entryName);"
    },
    {
      "api": "ConfigGetBool",
      "file_line": "3_Game/Entities/Object.c:887",
      "declaration": "bool ConfigGetBool(string entryName)"
    },
    {
      "api": "GetIdentity",
      "file_line": "3_Game/Entities/Man.c:21",
      "declaration": "proto native PlayerIdentity GetIdentity();"
    },
    {
      "api": "IsUnconscious",
      "file_line": "3_Game/Entities/Man.c:63",
      "declaration": "bool IsUnconscious();"
    },
    {
      "api": "GetGame",
      "file_line": "3_Game/gameplay.c:636",
      "declaration": "DayZGame GetGame() { return g_Game; }"
    },
    {
      "api": "GetId",
      "file_line": "3_Game/gameplay.c:368",
      "declaration": "proto string GetId();"
    },
    {
      "api": "GetItemInHands",
      "file_line": "4_World/Entities/ManBase/PlayerBase.c:6733",
      "declaration": "ItemBase GetItemInHands()"
    },
    {
      "api": "IsInVehicle",
      "file_line": "4_World/Entities/DayZPlayerImplement.c:468",
      "declaration": "bool IsInVehicle()"
    },
    {
      "api": "GetQuantity",
      "file_line": "4_World/Entities/ItemBase.c:3490",
      "declaration": "override float GetQuantity()"
    },
    {
      "api": "AddQuantity",
      "file_line": "4_World/Entities/ItemBase.c:3393",
      "declaration": "bool AddQuantity(float value, bool destroy_config = true, bool destroy_forced = false)"
    },
    {
      "api": "AddAction",
      "file_line": "4_World/Entities/ItemBase.c:255",
      "declaration": "void AddAction(typename actionName)"
    },
    {
      "api": "IsSwitchedOn",
      "file_line": "3_Game/tools/Component/ComponentEnergyManager.c:884",
      "declaration": "bool IsSwitchedOn()"
    },
    {
      "api": "GetEnergy",
      "file_line": "3_Game/tools/Component/ComponentEnergyManager.c:1246",
      "declaration": "float GetEnergy()"
    },
    {
      "api": "GetEnergySource",
      "file_line": "3_Game/tools/Component/ComponentEnergyManager.c:1324",
      "declaration": "EntityAI GetEnergySource()"
    },
    {
      "api": "EnumerateInventory",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:127",
      "declaration": "proto native bool EnumerateInventory(InventoryTraversalType tt, out array<EntityAI> items);"
    },
    {
      "api": "GetCurrentInventoryLocation",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:268",
      "declaration": "proto native bool GetCurrentInventoryLocation(out notnull InventoryLocation loc);"
    },
    {
      "api": "FindFreeLocationFor",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:276",
      "declaration": "proto native bool FindFreeLocationFor(notnull EntityAI item, FindInventoryLocationType flags, out notnull InventoryLocation loc);"
    },
    {
      "api": "CanAddAttachmentEx",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:246",
      "declaration": "proto native bool CanAddAttachmentEx(notnull EntityAI e, int slot);"
    },
    {
      "api": "FindAttachment",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:224",
      "declaration": "proto native EntityAI FindAttachment(int slot);"
    },
    {
      "api": "LocationCanMoveEntity",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:373",
      "declaration": "static proto native bool LocationCanMoveEntity(notnull InventoryLocation src, notnull InventoryLocation dst);"
    },
    {
      "api": "LocationCanMoveEntitySyncCheck",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:380",
      "declaration": "static bool LocationCanMoveEntitySyncCheck(notnull InventoryLocation src, notnull InventoryLocation dst)"
    },
    {
      "api": "LocationSyncMoveEntity",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:567",
      "declaration": "static proto native bool LocationSyncMoveEntity(notnull InventoryLocation src_loc, notnull InventoryLocation dst_loc);"
    },
    {
      "api": "HasInventoryReservation",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:787",
      "declaration": "static proto native bool HasInventoryReservation(EntityAI item, InventoryLocation dst);"
    },
    {
      "api": "AddInventoryReservation",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:717",
      "declaration": "static proto native bool AddInventoryReservation(EntityAI item, InventoryLocation dst, int timeout_ms);"
    },
    {
      "api": "ClearInventoryReservation",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:763",
      "declaration": "static proto native bool ClearInventoryReservation(EntityAI item, InventoryLocation dst);"
    },
    {
      "api": "GetType",
      "file_line": "3_Game/Systems/Inventory/InventoryLocation.c:43",
      "declaration": "proto native int GetType();"
    },
    {
      "api": "GetParent",
      "file_line": "3_Game/Systems/Inventory/InventoryLocation.c:52",
      "declaration": "proto native EntityAI GetParent();"
    },
    {
      "api": "GetSlot",
      "file_line": "3_Game/Systems/Inventory/InventoryLocation.c:71",
      "declaration": "proto native int GetSlot();"
    },
    {
      "api": "SetAttachment",
      "file_line": "3_Game/Systems/Inventory/InventoryLocation.c:131",
      "declaration": "proto native void SetAttachment(notnull EntityAI parent, EntityAI e, int slotId);"
    },
    {
      "api": "SetHands",
      "file_line": "3_Game/Systems/Inventory/InventoryLocation.c:172",
      "declaration": "proto native void SetHands(notnull EntityAI parent, EntityAI e);"
    },
    {
      "api": "GetSlotIdFromString",
      "file_line": "3_Game/Systems/Inventory/InventorySlots.c:42",
      "declaration": "static proto native int GetSlotIdFromString(string slot_name);"
    },
    {
      "api": "FileExist",
      "file_line": "1_Core/proto/EnSystem.c:397",
      "declaration": "proto bool FileExist(string name);"
    },
    {
      "api": "OpenFile",
      "file_line": "1_Core/proto/EnSystem.c:417",
      "declaration": "proto FileHandle\t\tOpenFile(string name, FileMode mode);"
    },
    {
      "api": "ReadFile",
      "file_line": "1_Core/proto/EnSystem.c:425",
      "declaration": "proto int ReadFile(FileHandle file, void param_array, int length);"
    },
    {
      "api": "CloseFile",
      "file_line": "1_Core/proto/EnSystem.c:443",
      "declaration": "proto void\t\tCloseFile(FileHandle file);"
    },
    {
      "api": "FPrint",
      "file_line": "1_Core/proto/EnSystem.c:462",
      "declaration": "proto void\t\tFPrint(FileHandle file, void var);"
    },
    {
      "api": "MakeDirectory",
      "file_line": "1_Core/proto/EnSystem.c:525",
      "declaration": "proto native bool MakeDirectory(string name);"
    },
    {
      "api": "FindFile",
      "file_line": "1_Core/proto/EnSystem.c:520",
      "declaration": "proto FindFileHandle FindFile(string pattern, out string fileName, out FileAttr fileAttributes, FindFileFlags flags);"
    },
    {
      "api": "FindNextFile",
      "file_line": "1_Core/proto/EnSystem.c:521",
      "declaration": "proto bool FindNextFile(FindFileHandle handle, out string fileName, out FileAttr fileAttributes);"
    },
    {
      "api": "CloseFindFile",
      "file_line": "1_Core/proto/EnSystem.c:522",
      "declaration": "proto native void CloseFindFile(FindFileHandle handle);"
    },
    {
      "api": "LoadData",
      "file_line": "3_Game/tools/JsonFileLoader.c:69",
      "declaration": "static bool LoadData(string string_data, out T data, out string errorMessage)"
    },
    {
      "api": "MakeData",
      "file_line": "3_Game/tools/JsonFileLoader.c:85",
      "declaration": "static bool MakeData(T inputData, out string outputData, out string errorMessage, bool prettyPrint = true)"
    },
    {
      "api": "Length",
      "file_line": "1_Core/proto/EnString.c:199",
      "declaration": "proto native int Length();"
    },
    {
      "api": "Trim",
      "file_line": "1_Core/proto/EnString.c:304",
      "declaration": "proto string Trim();"
    },
    {
      "api": "Contains",
      "file_line": "1_Core/proto/EnString.c:286",
      "declaration": "bool Contains(string sample)"
    },
    {
      "api": "Substring",
      "file_line": "1_Core/proto/EnString.c:113",
      "declaration": "proto string Substring(int start, int len);"
    },
    {
      "api": "IndexOf",
      "file_line": "1_Core/proto/EnString.c:240",
      "declaration": "proto native int IndexOf(string sample);"
    },
    {
      "api": "ToInt",
      "file_line": "1_Core/proto/EnString.c:20",
      "declaration": "proto native int ToInt();"
    },
    {
      "api": "Format",
      "file_line": "1_Core/proto/EnString.c:526",
      "declaration": "static proto string Format(string fmt, void param1 = NULL, void param2 = NULL, void param3 = NULL, void param4 = NULL, void param5 = NULL, void param6 = NULL, void param7 = NULL, void param8 = NULL, void param9 = NULL);"
    },
    {
      "api": "DistanceSq",
      "file_line": "1_Core/proto/EnConvert.c:210",
      "declaration": "proto static native float DistanceSq(vector v1, vector v2);"
    },
    {
      "api": "ToString",
      "file_line": "1_Core/proto/EnConvert.c:3",
      "declaration": "string ToString()"
    },
    {
      "api": "Max",
      "file_line": "1_Core/proto/EnMath.c:566",
      "declaration": "proto static float Max(float x, float y);"
    },
    {
      "api": "Count",
      "file_line": "1_Core/proto/EnScript.c:380",
      "declaration": "proto native int Count();"
    },
    {
      "api": "Find",
      "file_line": "1_Core/proto/EnScript.c:394",
      "declaration": "proto int Find(T value);"
    },
    {
      "api": "Insert",
      "file_line": "1_Core/proto/EnScript.c:407",
      "declaration": "proto int Insert(T value);"
    },
    {
      "api": "Clear",
      "file_line": "1_Core/proto/EnScript.c:385",
      "declaration": "proto native void Clear();"
    },
    {
      "api": "Cast",
      "file_line": "1_Core/proto/EnScript.c:94",
      "declaration": "proto static Class Cast(Class from);"
    },
    {
      "api": "Print",
      "file_line": "1_Core/proto/EnDebug.c:96",
      "declaration": "proto void Print(void var);"
    },
    {
      "api": "RegisterActions",
      "file_line": "4_World/Classes/UserActionsComponent/ActionConstructor.c:27",
      "declaration": "void RegisterActions(TTypenameArray actions)"
    },
    {
      "api": "SetActions",
      "file_line": "4_World/Entities/Firearms/Weapon_Base.c:2196",
      "declaration": "override void SetActions()"
    },
    {
      "api": "ActionCondition",
      "file_line": "4_World/Classes/UserActionsComponent/ActionBase.c:441",
      "declaration": "protected bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item) //condition for action"
    },
    {
      "api": "CreateConditionComponents",
      "file_line": "4_World/Classes/UserActionsComponent/ActionBase.c:245",
      "declaration": "void CreateConditionComponents() //Instantiates components, called once from ActionManager on actions construction"
    },
    {
      "api": "HasTarget",
      "file_line": "4_World/Classes/UserActionsComponent/ActionBase.c:259",
      "declaration": "bool HasTarget()"
    },
    {
      "api": "OnExecuteServer",
      "file_line": "4_World/Classes/UserActionsComponent/AnimatedActionBase.c:179",
      "declaration": "protected void OnExecuteServer( ActionData action_data )"
    },
    {
      "api": "class ActionSingleUseBase",
      "file_line": "4_World/Classes/UserActionsComponent/Actions/ActionSingleUseBase.c:29"
    },
    {
      "api": "class CCINonRuined",
      "file_line": "4_World/Classes/UserActionsComponent/ItemConditionComponents/CCINonRuined.c:1"
    },
    {
      "api": "class CCTNone",
      "file_line": "4_World/Classes/UserActionsComponent/TargetConditionsComponents/CCTNone.c:1"
    },
    {
      "api": "native weapon light switch and registration",
      "file_line": "4_World/Entities/Firearms/Weapon_Base.c:2203"
    },
    {
      "api": "weaponFlashlight toggle",
      "file_line": "4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnWeaponFlashlight.c:27"
    },
    {
      "api": "pistolFlashlight toggle",
      "file_line": "4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnWeaponFlashlight.c:32"
    },
    {
      "api": "native switch off",
      "file_line": "4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOffWeaponFlashlight.c:51"
    },
    {
      "api": "native rail prerequisite and slot list",
      "file_line": "4_World/Entities/ItemBase/Switchable_Base/UniversalLight.c:25"
    },
    {
      "api": "c_InventoryReservationTimeoutMS",
      "file_line": "3_Game/Systems/Inventory/Inventory.c:714"
    },
    {
      "api": "InventoryLocationType / FindInventoryLocationType",
      "file_line": "3_Game/Systems/Inventory/InventoryLocation.c:3"
    },
    {
      "api": "CMD_ACTIONMOD_ATTACHITEM",
      "file_line": "3_Game/dayzplayer.c:792"
    },
    {
      "api": "STANCEMASK_ERECT",
      "file_line": "3_Game/dayzplayer.c:633"
    },
    {
      "api": "STANCEMASK_CROUCH",
      "file_line": "3_Game/dayzplayer.c:634"
    }
  ],
  "lead_integration": {
    "core_registration": "none; ActionConstructor + Weapon_Base.SetActions are automatically compiled and dispatched",
    "acceptance_checklist_additions": [
      "$profile:HollowCountry/acceptance/taped_light.disable",
      "HCTapedLightAdmission.Qualified"
    ],
    "acceptance_checklist_file": "docs/LOCAL_ACCEPTANCE_V1.md",
    "reason": "Outside writer W1.3 file ownership; marker traceability test requires these literal entries.",
    "checklist_suggested_row": "| #56 | Taped flashlights | $profile:HollowCountry/acceptance/taped_light.disable; HCTapedLightAdmission.Qualified=false | Hold an evidenced weapon, owned off compatible light and tape; mount, native toggle off/on, remove into free cargo | One tape unit spent; same light and battery returned; no duplicates | Taped light | pending | pending | Tier S only; two-client and restart acceptance pending |"
  },
  "limits": {
    "operations_per_journal": 128,
    "journal_images": 768,
    "inventory_entries": 256,
    "on_full": "refuse; no automatic compaction",
    "on_uncertain": "quarantine/stop; no retry/refund/recovery spawn"
  },
  "bdd": [
    "Given an evidenced held weapon, compatible off light and at least one owned tape unit, mount consumes one unit and moves the same light to the exact native slot.",
    "Given a recorded mount, off light and free owned cargo cell, removal moves the same light into that cell without tape debit or spawning.",
    "Given no marker, unknown host/pair/build, wrong rail, other owner, replay drift or unresolved journal, refuse before inventory transfer."
  ],
  "plan_tasks": [
    {
      "task": "W1.3.1",
      "state": "authored",
      "output": "Exact Tier S matrix and pinned provenance; 26 pairs, all client_pending."
    },
    {
      "task": "W1.3.2",
      "state": "authored",
      "output": "Server action adapter, native reservations and exact destination, tape debit, native toggle reuse."
    },
    {
      "task": "W1.3.3",
      "state": "authored",
      "output": "Cached server-only opt-in and closed production qualification."
    },
    {
      "task": "W1.3.4",
      "state": "runtime-pending",
      "output": "DayZDiag, normal signed PBO, inventory/crash races and two-client presentation remain unobserved."
    }
  ],
  "refused_examples": [
    {
      "host": "R12",
      "reason": "report pending_client; proxy evidence does not qualify this pair"
    },
    {
      "host": "Mich2001Helmet",
      "reason": "post-v1 #58 and pending_client"
    },
    {
      "host": "Mosin9130",
      "reason": "no qualified v1 native pair"
    }
  ],
  "checks": {
    "diff_check": "git --no-optional-locks diff --check: exit 0",
    "enforce_source_scan": "No ternary or local/parameter identifiers equal to actual installed engine class/enum names; native comments and strings excluded. No leading logical operator and override parameter checks pass.",
    "no_runtime_claim": "No DayZ, Wine, network or git writes were used. Native compilation and gameplay acceptance remain pending."
  }
}
''')
