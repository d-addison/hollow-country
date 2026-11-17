"""Join taped-light probe observations with the config classification into the final matrix.

Inputs are the classification written by ``tools.audit.flashlight_matrix classify`` and the
observations JSON written by a native run of the probe staged by
``tools/setup/taped_light_probe.py``. Every host ends in exactly one verdict:

  qualified         the engine reported a native slot, the representative light attached in
                    it through the native call, the attachment is found in that slot and the
                    host model carries geometry for the slot: a proxy selection whose
                    CfgNonAIVehicles entry exists, names the same model path and lists the slot
                    in inventorySlot, or (older probes) a slot selection, memory point or bone.
  geometry_missing  the engine reported no compatible native slot, refused the native attach
                    for a reason the observation can attribute to the host, or the attach has
                    no model selection to render at (no proxy is invented).
  excluded          the classification excluded the class (reasons are kept).
  pending           the observation is missing, mistyped, duplicated, ambiguous, timed out,
                    contradicts the config classification, or the probe itself was not clean.

Evidence rules (the report never fills a gap with a favourable default):

  * Every expected host, light, slot and per-slot entry must be present exactly once with the
    expected JSON types. A missing key, a wrong type or an empty list is pending, never a
    negative finding. Duplicates are pending even when they agree.
  * Pending takes precedence over qualified at every level.
  * Identity must agree: spawned host type, preflight light type, preflight versus host slot
    fit, the native slot set versus the classification, and the host's observed native slots
    versus the classification's per-host slot list.
  * A native refusal is only a negative finding when the observation can show that a known
    prerequisite is not involved. UniversalLight.CanPutAsAttachment
    (4_World/Entities/ItemBase/Switchable_Base/UniversalLight.c:25-45, slot list at :123-132)
    refuses when the parent owns a handguard slot (weaponHandguardM4/AK/MP5) but holds no
    attachment with hasRailFunctionality. A refusal on such a host is pending unless the probe's
    prerequisite variant (a fresh host with the matching rail handguard created in that slot)
    observed the light on the same host.
  * Qualification needs a clean probe: complete status, matching spawn/delete counters, no
    handles surviving release, a residual census that was complete (not truncated), the native
    slot set resolved and no control light attached anywhere.

Model evidence (probe-003: InventorySlots.GetSelectionForSlotId returns nothing natively, so the proxy join
is the evidence). The hook lists the host model's ``proxy:<path>.<nnn>`` selections with their
``CfgNonAIVehicles Proxy<basename>`` entry (exists, model, inventorySlot). A slot has proxy evidence only when
a listed proxy has an existing entry, an entry class equal to ``Proxy<basename>``, a ``model`` that equals the
proxy path (case-insensitive, slashes and the .p3d extension normalised) and an inventorySlot list holding the
slot. The proxy name alone is never evidence. Missing or malformed proxy evidence is pending, never qualified;
a truncated proxy list without a qualifying row is pending; a complete list without one is geometry_missing.

Attachment read-back must be self-consistent everywhere: found_type is filled only after a successful create,
so a non-empty found_type with attach_ok false, or attach_ok true with an empty found_type, is contradictory
evidence and makes the attempt (base, variant or control) invalid.

Beam, switch, two-client presentation, removal by hand, tape consumption and persistence are
never observable from a dedicated-server probe and stay pending in every output.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

CLASSIFICATION_KIND = "flashlight_host_light_classification"
OBSERVATIONS_KIND = "taped-light-probe-observations"
REPORT_KIND = "taped_light_matrix_report"
MAX_INPUT_BYTES = 32 * 1024 * 1024
VERDICT_ORDER = ("qualified", "geometry_missing", "excluded", "pending")
UNOBSERVED_AXES = ("beam", "switch", "two_client_presentation", "removal_by_hand", "tape_consumption",
                   "persistence")
# Native prerequisite: UniversalLight.c:25-45 (rule) and :123-132 (slot list). The probe creates the
# matching rail handguard per slot (taped_light_probe.PREREQUISITE_HANDGUARDS); a test keeps both in step.
PREREQUISITE_LIGHTS = ("UniversalLight",)
# Handguard the probe's variant creates per slot; a variant only counts when exactly this type was read back
# from that slot (a wrong label such as AK_PlasticHndgrd must not keep the rail qualification).
PREREQUISITE_HANDGUARDS = {"weaponHandguardAK": "AK_RailHndgrd", "weaponHandguardM4": "M4_RISHndgrd",
                           "weaponHandguardMP5": "MP5_RailHndgrd"}
PREREQUISITE_SLOTS = tuple(sorted(PREREQUISITE_HANDGUARDS))
# The hook scans at most this many near objects (taped_light_probe.CENSUS_SCAN_LIMIT; a test keeps both in step).
CENSUS_SCAN_LIMIT = 2048
# Observation keys this module reads; a test proves the generated hook emits each of them.
CONSUMED_KEYS = (
    "schema", "kind", "status", "counters", "spawned", "deleted", "live_after_release", "residual_probe_types",
    "census_total", "census_scanned", "census_truncated", "census_complete", "observed",
    "hosts", "lights", "class", "root", "group", "timed_out", "slots", "slot", "host_has_slot", "valid",
    "selection_on_model", "memory_point", "bone_index", "per_slot", "light", "light_fits", "can_add",
    "attach_ok", "found_type", "fits_native_slots", "fits", "type", "prereq", "attached_type",
    "rail_functional", "prereq_variant", "performed", "handguard_attached", "handguard", "handguard_found_type",
    "handguard_slot_occupied", "handguard_rail_functional", "proxy_count", "proxy_scan_complete", "proxies",
    "selection", "cfg_class", "cfg_exists", "model", "inventory_slots")

MISSING = object()   # absent or wrongly typed evidence


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _objects(value, what):
    _require(isinstance(value, list) and all(isinstance(item, dict) for item in value), f"{what} must be a list of objects")
    return value


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


_KINDS = {"bool": lambda v: isinstance(v, bool), "int": _int, "str": lambda v: isinstance(v, str),
          "list": lambda v: isinstance(v, list)}


def _get(entry, key, kind):
    """Typed lookup: the value, or MISSING when the key is absent or has the wrong JSON type."""
    value = entry.get(key, MISSING) if isinstance(entry, dict) else MISSING
    return value if value is not MISSING and _KINDS[kind](value) else MISSING


def _keyed(entries, key):
    """Return (index, problems). A key seen twice maps to None; non-list input is a problem."""
    if not isinstance(entries, list):
        return {}, {"missing"}
    index, problems = {}, set()
    for entry in entries:
        name = _get(entry, key, "str")
        if name is MISSING:
            problems.add("malformed")
        elif name in index:
            problems.add("duplicate")
            index[name] = None
        else:
            index[name] = entry
    return index, problems


def _problem_reason(label, problems):
    if "duplicate" in problems:
        return f"duplicate_{label}_observation"
    return f"{label}_observation_malformed" if "malformed" in problems else f"{label}_observation_missing"


# --- host slot, prerequisite and preflight evidence -------------------------------------------------


def _host_slots(row, slot_names, reasons):
    """Typed per-slot host evidence keyed by slot name; None marks an unusable slot entry."""
    index, problems = _keyed(row.get("slots"), "slot")
    if problems:
        reasons.add(_problem_reason("slot", problems))
    if set(index) != set(slot_names):
        reasons.add("slot_set_mismatch")
    result = {}
    for name, entry in index.items():
        values = None if entry is None else {
            "host_has_slot": _get(entry, "host_has_slot", "bool"), "selection_on_model": _get(entry, "selection_on_model", "bool"),
            "memory_point": _get(entry, "memory_point", "bool"), "bone_index": _get(entry, "bone_index", "int")}
        if values is None or MISSING in values.values():
            reasons.add("slot_evidence_invalid")
            values = None
        result[name] = values
    return result


def _prerequisites(row):
    """{slot: (host_has_slot, rail_functional)} for every native prerequisite slot, or MISSING."""
    index, problems = _keyed(row.get("prereq"), "slot")
    if problems or set(index) != set(PREREQUISITE_SLOTS):
        return MISSING
    result = {}
    for name, entry in index.items():
        has, rail = _get(entry, "host_has_slot", "bool"), _get(entry, "rail_functional", "bool")
        if has is MISSING or rail is MISSING or _get(entry, "attached_type", "str") is MISSING:
            return MISSING
        result[name] = (has, rail)
    return result


def _variant(row, prerequisites):
    """The prerequisite variant observation: None (not performed), a dict, or MISSING (unusable)."""
    value = row.get("prereq_variant")
    performed = _get(value, "performed", "bool")
    if performed is MISSING:
        return MISSING
    if not performed:
        return None
    slot, attached = _get(value, "slot", "str"), _get(value, "handguard_attached", "bool")
    label, found = _get(value, "handguard", "str"), _get(value, "handguard_found_type", "str")
    occupied, rail = _get(value, "handguard_slot_occupied", "bool"), _get(value, "handguard_rail_functional", "bool")
    if MISSING in (slot, attached, label, found, occupied, rail) or _get(value, "lights", "list") is MISSING \
            or prerequisites is MISSING or not prerequisites.get(slot, (False, False))[0]:
        return MISSING
    if occupied != attached:
        return MISSING
    if attached and not (found == label == PREREQUISITE_HANDGUARDS.get(slot) and rail):
        return MISSING        # the slot must hold the rail handguard bound to this very slot, with the rail property
    index, problems = _keyed(value["lights"], "light")
    if problems and attached:
        return MISSING
    return {"slot": slot, "attached": attached, "lights": index}


def _preflights(light_rows, slot_names, classification_lights):
    """{light: {"spawned", "fits"}} from the preflight rows; None marks a duplicate or inconsistent row."""
    index, _problems = _keyed(light_rows, "light")
    result = {}
    for name, entry in index.items():
        spawned = _get(entry, "spawned", "bool")
        if spawned is False:
            result[name] = {"spawned": False, "fits": {}}
            continue
        fits_rows, problems = _keyed(entry.get("fits_native_slots") if entry else None, "slot")
        fits = {slot: _get(item, "fits", "bool") for slot, item in fits_rows.items() if item is not None}
        declared = classification_lights.get(name, {}).get("native_slots")
        consistent = (entry is not None and spawned is True and _get(entry, "type", "str") == name and not problems
                      and set(fits) == set(slot_names) and MISSING not in fits.values()
                      and (declared is None or sorted(declared) == sorted(s for s, v in fits.items() if v)))
        result[name] = {"spawned": True, "fits": fits} if consistent else None
    return result


def _light_slot(entry):
    values = {key: _get(entry, key, "bool") for key in ("light_fits", "can_add", "attach_ok")}
    found = _get(entry, "found_type", "str")
    if MISSING in values.values() or found is MISSING:
        return None
    if values["attach_ok"] and not values["can_add"]:
        return None        # a create cannot succeed when the native check refused it: contradictory evidence
    if values["attach_ok"] != bool(found):
        return None        # the hook fills found_type only after a successful create and read-back
    return dict(values, found_type=found)


def _per_slot(light_entry, slot_names):
    """(per-slot index, problem reason) for one observed light."""
    spawned = _get(light_entry, "spawned", "bool")
    if spawned is MISSING:
        return None, "light_evidence_invalid"
    if not spawned:
        return None, "light_not_spawned"
    index, problems = _keyed(light_entry.get("per_slot"), "slot")
    if problems:
        return None, _problem_reason("per_slot", problems)
    if set(index) != set(slot_names):
        return None, "per_slot_set_mismatch"
    return index, None


# --- slot, light and host verdicts -------------------------------------------------------------------


def _path(text):
    """Comparable model/proxy path: lower case, forward slashes, no leading slash, no .p3d extension."""
    parts = [part for part in text.replace("\\", "/").lower().split("/") if part]
    path = "/".join(parts)
    return path[:-4] if path.endswith(".p3d") else path


def _proxy_path(selection):
    """Path of a ``proxy:<path>.<nnn>`` selection (the trailing .nnn dropped), or None for any other selection.

    The prefix is matched case-insensitively, as the probe hook matches it."""
    if selection[:len("proxy:")].lower() != "proxy:":
        return None
    text = selection[len("proxy:"):].replace("\\", "/")
    stem, dot, _number = text.rpartition(".")
    return _path(stem if dot and "/" not in _number else text)


def _proxies(row):
    """Typed proxy evidence of a host row: ("missing",), ("malformed",) or ("ok", rows, truncated)."""
    if "proxies" not in row and "proxy_count" not in row and "proxy_scan_complete" not in row:
        return ("missing",)
    entries, count, complete = row.get("proxies"), _get(row, "proxy_count", "int"), _get(row, "proxy_scan_complete", "bool")
    if not isinstance(entries, list) or count is MISSING or complete is MISSING or not len(entries) <= count:
        return ("malformed",)
    rows = []
    for entry in entries:
        values = {"selection": _get(entry, "selection", "str"), "cfg_class": _get(entry, "cfg_class", "str"),
                  "cfg_exists": _get(entry, "cfg_exists", "bool"), "model": _get(entry, "model", "str"),
                  "inventory_slots": _get(entry, "inventory_slots", "list")}
        if MISSING in values.values() or not all(isinstance(item, str) for item in values["inventory_slots"]):
            return ("malformed",)
        path = _proxy_path(values["selection"])
        if path is None or values["cfg_class"].casefold() != ("Proxy" + path.rsplit("/", 1)[-1]).casefold():
            return ("malformed",)
        rows.append(dict(values, path=path))
    return ("ok", rows, count > len(entries) or not complete)


def _model_evidence(host_slot, slot, proxies):
    """(source, detail) for one slot: source is selection, proxy_slot, none or pending (detail names the reason).

    Selection, memory point and bone are the older evidence; proxy evidence is the join of a proxy selection to its
    config entry. Malformed proxy evidence outranks both, because the row's evidence is then not trustworthy."""
    if proxies[0] == "malformed":
        return "pending", "proxy_evidence_malformed"
    if host_slot["selection_on_model"] or host_slot["memory_point"] or host_slot["bone_index"] >= 0:
        return "selection", None
    if proxies[0] == "missing":
        return "pending", "proxy_evidence_missing"
    for item in proxies[1]:
        if item["cfg_exists"] and _path(item["model"]) == item["path"] \
                and slot.casefold() in {name.casefold() for name in item["inventory_slots"]}:
            return "proxy_slot", item["selection"]
    if proxies[2]:
        return "pending", "proxy_evidence_truncated"
    if any(not item["cfg_exists"] for item in proxies[1]):
        return "pending", "proxy_config_missing"
    return "none", None


def _accepted(light, model, attempt):
    """Verdict for an attach the native call allowed (can_add true); ``model`` is a _model_evidence result."""
    if not attempt["attach_ok"]:
        return "pending", "attach_create_failed"
    if attempt["found_type"] != light:
        return "pending", "attached_item_not_found_in_slot"
    if model[0] == "pending":
        return "pending", model[1]
    if model[0] == "proxy_slot":
        return "qualified", "native_attach_with_proxy_slot"
    if model[0] == "selection":
        return "qualified", "native_attach_with_model_selection"
    return "geometry_missing", "attached_without_model_selection"


def _variant_attempt(entry, slot, slot_names, preflight):
    """(attempt, problem) for the variant's observation of one light: the same checks as a base attempt."""
    if entry in (MISSING, None):
        return None, "prerequisite_variant_incomplete"
    per_slot, problem = _per_slot(entry, slot_names)
    if problem:
        return None, problem
    for name in slot_names:
        attempt = _light_slot(per_slot[name])
        if attempt is None:
            return None, "slot_evidence_invalid"
        if attempt["light_fits"] != preflight["fits"][name]:
            return None, "preflight_variant_disagree"
    return _light_slot(per_slot[slot]), None


def _evaluate_slot(light, slot, host_slot, attempt, prerequisites, variant, slot_names, preflight, model):
    """Return (verdict, reason, requires_prerequisite) for one compatible host/light/slot observation."""
    if attempt["can_add"]:
        return _accepted(light, model, attempt) + (False,)
    if light not in PREREQUISITE_LIGHTS:
        return "geometry_missing", "native_attach_refused", False
    if prerequisites is MISSING:
        return "pending", "prerequisite_evidence_missing", False
    owns_slot = any(has for has, _rail in prerequisites.values())
    if not owns_slot or any(rail for _has, rail in prerequisites.values()):
        return "geometry_missing", "native_attach_refused", False     # prerequisite not in play
    if variant is None:
        return "pending", "refusal_may_depend_on_prerequisite", False
    if variant is MISSING:
        return "pending", "prerequisite_variant_invalid", False
    if not variant["attached"]:
        return "pending", "prerequisite_variant_failed", False
    attempt, problem = _variant_attempt(variant["lights"].get(light, MISSING), slot, slot_names, preflight)
    if attempt is None:
        return "pending", problem or "prerequisite_variant_incomplete", False
    if not attempt["can_add"]:
        return "geometry_missing", "native_attach_refused_with_prerequisite", True
    verdict, reason = _accepted(light, model, attempt)
    if verdict == "qualified":
        reason = ("native_attach_with_proxy_slot_and_rail_handguard_prerequisite" if model[0] == "proxy_slot"
                  else "native_attach_with_rail_handguard_prerequisite")
    return verdict, reason, True


def _combine(verdicts):
    if "pending" in verdicts:
        return "pending"
    if "qualified" in verdicts:
        return "qualified"
    return "geometry_missing"


def _pending(reason):
    return {"verdict": "pending", "reasons": [reason], "slots": {}}


def _evaluate_light(light, light_entry, slot_names, host_slots, preflight, prerequisites, variant, proxies):
    """Verdict for one host x representative light from the host row's observations."""
    if preflight is MISSING:
        return _pending("preflight_missing")
    if preflight is None:
        return _pending("preflight_invalid")
    if not preflight["spawned"]:
        return _pending("light_not_spawned")
    if light_entry is MISSING:
        return _pending("light_not_observed")
    if light_entry is None:
        return _pending("duplicate_light_observation")
    per_slot, problem = _per_slot(light_entry, slot_names)
    if problem:
        return _pending(problem)
    slots, reasons, verdicts = {}, set(), []
    for slot in slot_names:
        host_slot, attempt = host_slots.get(slot), _light_slot(per_slot[slot])
        if host_slot is None or attempt is None:
            verdict, reason, evidence = "pending", "slot_evidence_invalid", {}
        elif attempt["light_fits"] != preflight["fits"][slot]:
            verdict, reason, evidence = "pending", "preflight_host_disagree", {}
        elif not (host_slot["host_has_slot"] and attempt["light_fits"]):
            continue
        else:
            model = _model_evidence(host_slot, slot, proxies)
            verdict, reason, requires = _evaluate_slot(light, slot, host_slot, attempt, prerequisites, variant, slot_names,
                                                       preflight, model)
            evidence = dict(host_slot, light_fits=attempt["light_fits"], can_add=attempt["can_add"],
                            attach_ok=attempt["attach_ok"], requires_prerequisite=requires, model_evidence=model[0],
                            proxy_selection=model[1] if model[0] == "proxy_slot" else None)
            evidence["bone_index"] = max(host_slot["bone_index"], -1)
        slots[slot] = {"verdict": verdict, "reason": reason, "evidence": evidence}
        verdicts.append(verdict)
        reasons.add(reason)
    if not verdicts:
        return {"verdict": "geometry_missing", "reasons": ["no_compatible_native_slot"], "slots": slots}
    return {"verdict": _combine(verdicts), "reasons": sorted(reasons), "slots": slots}


# Host reasons that name one light's own evidence; the affected light is already pending on its own, and a
# missing or duplicated sibling alone does not invalidate an independently valid pair.
SIBLING_SCOPED_REASONS = frozenset({"duplicate_light_observation", "light_observation_missing"})


def _control_issues(light_entries, slot_names, control, preflight):
    """Host-level reasons for one control light; empty when it has a spawned typed preflight and full evidence."""
    if preflight is MISSING:
        return {"control_preflight_missing"}
    if preflight is None:
        return {"control_preflight_invalid"}          # duplicate, wrong type or fit contradicting the classification
    if not preflight["spawned"]:
        return {"control_light_not_spawned"}
    entry = light_entries.get(control, MISSING)
    if entry is MISSING:
        return {"control_light_not_observed"}
    if entry is None:
        return {"control_light_duplicate"}
    index, problem = _per_slot(entry, slot_names)
    if problem == "light_not_spawned":
        return {"control_light_not_spawned"}
    if problem:
        return {"control_light_evidence_invalid"}
    for slot in slot_names:
        attempt = _light_slot(index[slot])
        if attempt is None:
            return {"control_light_evidence_invalid"}
        if attempt["light_fits"] != preflight["fits"][slot]:
            return {"control_preflight_host_disagree"}
    return set()


def _invalidate(lights, reasons, slot_reason, verdicts):
    """Demote nested light and slot verdicts in ``verdicts`` to pending; pending is never promoted."""
    for record in lights.values():
        for slot in record["slots"].values():
            if slot["verdict"] in verdicts:
                slot["verdict"], slot["reason"] = "pending", slot_reason
        if record["verdict"] in verdicts:
            record["verdict"] = "pending"
            record["reasons"] = sorted(set(record["reasons"]) | set(reasons) | {slot_reason})


def _evaluate_host(entry, rows, context):
    base = {"class": entry["name"], "root": entry["root"], "group": entry["group"],
            "exclusion_reasons": list(entry.get("exclusion_reasons", [])), "lights": {}}
    if entry["group"] == "excluded":
        return dict(base, verdict="excluded", reasons=["classification_excluded"])
    if not rows:
        return dict(base, verdict="pending", reasons=["no_probe_row"])
    if len(rows) > 1 or rows[0].get("root") != entry["root"] or rows[0].get("group") != entry["group"]:
        return dict(base, verdict="pending", reasons=["ambiguous_probe_row"])
    row, slot_names = rows[0], context["slots"]
    spawned = _get(row, "spawned", "bool")
    if spawned is MISSING:
        return dict(base, verdict="pending", reasons=["invalid_probe_row"])
    if not spawned:
        return dict(base, verdict="pending", reasons=["host_not_spawned"])
    reasons = set()
    if _get(row, "type", "str") != entry["name"]:
        reasons.add("spawned_type_mismatch")
    timed_out = _get(row, "timed_out", "bool")
    if timed_out is MISSING:
        reasons.add("invalid_probe_row")
    elif timed_out:
        reasons.add("class_timed_out")
    host_slots = _host_slots(row, slot_names, reasons)
    observed = {slot for slot, item in host_slots.items() if item and item["host_has_slot"]}
    configured = entry.get("native_light_slots")
    if not isinstance(configured, list) or observed != set(configured) or bool(observed) != (entry["group"] == "slot_host"):
        reasons.add("config_probe_conflict")
    light_entries, problems = _keyed(row.get("lights"), "light")
    if problems:
        reasons.add(_problem_reason("light", problems))
    prerequisites = _prerequisites(row)
    variant = _variant(row, prerequisites)
    proxies = _proxies(row)
    for light in context["representatives"]:
        base["lights"][light] = _evaluate_light(light, light_entries.get(light, MISSING), slot_names, host_slots,
                                                context["preflights"].get(light, MISSING), prerequisites, variant, proxies)
    for control in context["controls"]:       # control evidence must be complete even though it is not a verdict
        reasons |= _control_issues(light_entries, slot_names, control, context["preflights"].get(control, MISSING))
    invalidating = reasons - SIBLING_SCOPED_REASONS
    if invalidating:       # the host's evidence cannot be trusted, so neither can any pair derived from it
        _invalidate(base["lights"], invalidating, "host_evidence_invalid", ("qualified", "geometry_missing"))
    if reasons:
        return dict(base, verdict="pending", reasons=sorted(reasons))
    records = list(base["lights"].values())
    if any(record["verdict"] == "pending" for record in records):
        detail = sorted({reason for record in records if record["verdict"] == "pending" for reason in record["reasons"]})
        return dict(base, verdict="pending", reasons=detail)
    if not observed:
        return dict(base, verdict="geometry_missing", reasons=["no_native_light_slot"])
    verdict = _combine([record["verdict"] for record in records])
    detail = sorted({reason for record in records if record["verdict"] == verdict for reason in record["reasons"]})
    return dict(base, verdict=verdict, reasons=detail)


# --- probe integrity ---------------------------------------------------------------------------------


def _integrity(observations, unexpected, control_hits, slot_names, row_count):
    issues = []
    if observations["status"] != "complete":
        issues.append("probe_status_partial")
    counters = observations.get("counters")
    clean = isinstance(counters, dict)
    if not clean:
        issues.append("counters_missing")
    else:
        values = {key: _get(counters, key, "int")
                  for key in ("spawned", "deleted", "live_after_release", "residual_probe_types")}
        if MISSING in values.values():
            issues.append("counters_invalid")
            clean = False
        else:
            if min(values.values()) < 0:
                issues.append("counters_out_of_range")
                clean = False
            if values["spawned"] != values["deleted"]:
                issues.append("spawned_not_equal_deleted")
                clean = False
            if values["live_after_release"] != 0:
                issues.append("live_after_release_nonzero")
                clean = False
            if values["residual_probe_types"] != 0:
                issues.append("residual_probe_types_nonzero")
                clean = False
        total, scanned = _get(counters, "census_total", "int"), _get(counters, "census_scanned", "int")
        truncated, complete = _get(counters, "census_truncated", "bool"), _get(counters, "census_complete", "bool")
        if MISSING in (total, scanned, truncated, complete):
            issues.append("census_missing")
            clean = False
        elif not 0 <= scanned <= total or scanned > CENSUS_SCAN_LIMIT:
            issues.append("census_out_of_range")
            clean = False
        elif truncated or not complete:
            issues.append("census_incomplete")
            clean = False
        elif scanned != total:
            issues.append("census_inconsistent")
            clean = False
    slot_rows, problems = _keyed(observations.get("slots"), "slot")
    if problems or set(slot_rows) != set(slot_names) or any(_get(item, "valid", "bool") is not True for item in slot_rows.values()):
        issues.append("native_slot_set_mismatch")
    if _get(observations, "observed", "int") != row_count:
        issues.append("observed_count_mismatch")
    if control_hits:
        issues.append(f"control_light_attached_on_{len(control_hits)}_hosts")
    if unexpected:
        issues.append(f"unexpected_rows_{len(unexpected)}")
    return {"cleanup_clean": clean, "issues": issues, "unexpected_rows": unexpected}


def _control_hits(rows, controls):
    """Classes whose raw rows show a control light attached anywhere (every row, every duplicate)."""
    hits = set()
    for item in rows:
        for light in item.get("lights") if isinstance(item.get("lights"), list) else []:
            if isinstance(light, dict) and light.get("light") in controls and isinstance(light.get("per_slot"), list):
                if any(isinstance(slot, dict) and slot.get("attach_ok") is True for slot in light["per_slot"]):
                    hits.add(str(item.get("class")))
    return sorted(hits)


def _demote(record, control_hits):
    """A host verdict, and every light, slot and pair verdict under it, is only as good as the probe."""
    verdicts = ("qualified", "geometry_missing") if control_hits else ("qualified",)
    _invalidate(record["lights"], ("probe_integrity_failed",), "probe_integrity_failed", verdicts)
    if record["verdict"] in verdicts:
        return dict(record, verdict="pending", reasons=sorted(set(record["reasons"]) | {"probe_integrity_failed"}))
    return record


def build_report(classification, observations, provenance=None):
    _require(isinstance(classification, dict) and classification.get("kind") == CLASSIFICATION_KIND,
             "a flashlight host/light classification is required")
    _require(isinstance(observations, dict) and observations.get("kind") == OBSERVATIONS_KIND
             and observations.get("schema") == 1 and _int(observations.get("schema")),
             "taped-light probe observations (schema 1) are required")
    _require(observations.get("status") in ("complete", "partial"), "observations status must be complete or partial")
    hosts = _objects(classification.get("hosts"), "classification hosts")
    lights = _objects(classification.get("lights"), "classification lights")
    slot_names = sorted(classification.get("native_light_slots") or [])
    _require(slot_names, "classification lists no native light slots")
    _require(all(isinstance(e.get("name"), str) and isinstance(e.get("root"), str) and isinstance(e.get("group"), str)
                 for e in hosts), "classification hosts need string name, root and group")
    _require(len({e["name"] for e in hosts}) == len(hosts), "classification host names must be unique")
    rows = _objects(observations.get("hosts"), "observation hosts")
    representatives = sorted(e["name"] for e in lights if e.get("probe_role") == "representative")
    controls = sorted(e["name"] for e in lights if e.get("probe_role") == "control")
    _require(representatives, "classification has no representative light")

    rows_by_class = {}
    for item in rows:
        rows_by_class.setdefault(item.get("class"), []).append(item)
    expected = {entry["name"] for entry in hosts if entry.get("group") != "excluded"}
    unexpected = sorted(str(name) for name in rows_by_class if name not in expected)
    context = {"slots": slot_names, "representatives": representatives, "controls": controls,
               "preflights": _preflights(observations.get("lights"), slot_names, {e.get("name"): e for e in lights})}

    host_records = [_evaluate_host(entry, rows_by_class.get(entry["name"], []) if entry["group"] != "excluded" else [],
                                   context)
                    for entry in sorted(hosts, key=lambda e: (e["name"].casefold(), e["name"]))]
    control_hits = _control_hits(rows, controls)
    integrity = _integrity(observations, unexpected, control_hits, slot_names, len(rows))
    if integrity["issues"]:
        host_records = [_demote(record, control_hits) for record in host_records]
    counts = Counter(record["verdict"] for record in host_records)
    pair_counts = Counter(light["verdict"] for record in host_records for light in record["lights"].values())
    reasons = Counter(reason for record in host_records for reason in record["reasons"])
    document = {
        "schema_version": 1, "kind": REPORT_KIND, "acceptance": "PENDING",
        "provenance": dict(provenance or {}),
        "probe": {key: observations.get(key) for key in ("status", "world", "version", "classes", "observed",
                                                         "hard_cap", "per_class_ms")},
        "representative_lights": representatives, "control_lights": controls, "native_light_slots": slot_names,
        "integrity": integrity,
        "control": {"unexpected_attachments": control_hits},
        "hosts": host_records,
        "denominators": dict({name: counts.get(name, 0) for name in VERDICT_ORDER}, hosts=len(host_records),
                             host_light_pairs=dict(sorted(pair_counts.items())), reasons=dict(sorted(reasons.items()))),
        "unobserved_axes": {axis: "pending" for axis in UNOBSERVED_AXES},
        "note": "Dedicated-server observations only. Qualified means the native attach call and a model selection "
                "were observed; beam, switch, two-client presentation, removal by hand, tape consumption and "
                "persistence remain pending until runtime tests run. Nothing here is accepted.",
    }
    return document


def _read(path):
    with open(path, "rb") as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    _require(len(data) <= MAX_INPUT_BYTES, f"{path} exceeds its byte budget")
    return data


def _checkout_root():
    return Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Join taped-light probe observations with the classification.")
    parser.add_argument("--classification", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--out", required=True, help="new output file outside the source checkout")
    args = parser.parse_args(argv)
    try:
        out = Path(args.out).absolute()
        checkout = _checkout_root()
        _require(out != checkout and checkout not in out.parents, "report output must be outside the source checkout")
        raw_classification, raw_observations = _read(args.classification), _read(args.observations)
        document = build_report(json.loads(raw_classification), json.loads(raw_observations), {
            "classification_sha256": hashlib.sha256(raw_classification).hexdigest(),
            "observations_sha256": hashlib.sha256(raw_observations).hexdigest()})
        encoded = json.dumps(document, indent=1, sort_keys=True, ensure_ascii=True, allow_nan=False)
        with open(out, "x", encoding="ascii") as stream:
            stream.write(encoded + "\n")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"taped_light_report: {error}", file=sys.stderr)
        return 1
    counts = document["denominators"]
    print("report: " + " ".join(f"{name}={counts[name]}" for name in VERDICT_ORDER) + f" hosts={counts['hosts']} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
