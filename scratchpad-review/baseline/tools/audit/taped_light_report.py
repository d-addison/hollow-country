"""Join taped-light probe observations with the config classification into the final matrix.

Inputs are the classification written by ``tools.audit.flashlight_matrix classify`` and the
observations JSON written by a native run of the probe staged by
``tools/setup/taped_light_probe.py``. Every host ends in exactly one verdict:

  qualified         the engine reported a native slot, the representative light attached in
                    it through the native call, the attachment is found in that slot and the
                    host model carries a selection, memory point or bone for the slot.
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
PREREQUISITE_SLOTS = ("weaponHandguardAK", "weaponHandguardM4", "weaponHandguardMP5")
# Observation keys this module reads; a test proves the generated hook emits each of them.
CONSUMED_KEYS = (
    "schema", "kind", "status", "counters", "spawned", "deleted", "live_after_release", "residual_probe_types",
    "census_total", "census_scanned", "census_truncated", "census_complete", "observed",
    "hosts", "lights", "class", "root", "group", "timed_out", "slots", "slot", "host_has_slot", "valid",
    "selection_on_model", "memory_point", "bone_index", "per_slot", "light", "light_fits", "can_add",
    "attach_ok", "found_type", "fits_native_slots", "fits", "type", "prereq", "attached_type",
    "rail_functional", "prereq_variant", "performed", "handguard_attached")

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
    if slot is MISSING or attached is MISSING or _get(value, "handguard", "str") is MISSING \
            or _get(value, "lights", "list") is MISSING or prerequisites is MISSING \
            or not prerequisites.get(slot, (False, False))[0]:
        return MISSING
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


def _accepted(light, model_evidence, attempt):
    """Verdict for an attach the native call allowed (can_add true)."""
    if not attempt["attach_ok"]:
        return "pending", "attach_create_failed"
    if attempt["found_type"] != light:
        return "pending", "attached_item_not_found_in_slot"
    if model_evidence:
        return "qualified", "native_attach_with_model_selection"
    return "geometry_missing", "attached_without_model_selection"


def _evaluate_slot(light, slot, host_slot, attempt, prerequisites, variant, slot_names):
    """Return (verdict, reason, requires_prerequisite) for one compatible host/light/slot observation."""
    model = host_slot["selection_on_model"] or host_slot["memory_point"] or host_slot["bone_index"] >= 0
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
    entry = variant["lights"].get(light, MISSING)
    per_slot, problem = _per_slot(entry, slot_names) if entry not in (MISSING, None) else (None, "prerequisite_variant_incomplete")
    attempt = _light_slot(per_slot[slot]) if per_slot else None
    if attempt is None:
        return "pending", problem or "prerequisite_variant_incomplete", False
    if not attempt["can_add"]:
        return "geometry_missing", "native_attach_refused_with_prerequisite", True
    verdict, reason = _accepted(light, model, attempt)
    if verdict == "qualified":
        reason = "native_attach_with_rail_handguard_prerequisite"
    return verdict, reason, True


def _combine(verdicts):
    if "pending" in verdicts:
        return "pending"
    if "qualified" in verdicts:
        return "qualified"
    return "geometry_missing"


def _pending(reason):
    return {"verdict": "pending", "reasons": [reason], "slots": {}}


def _evaluate_light(light, light_entry, slot_names, host_slots, preflight, prerequisites, variant):
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
            verdict, reason, requires = _evaluate_slot(light, slot, host_slot, attempt, prerequisites, variant, slot_names)
            evidence = dict(host_slot, light_fits=attempt["light_fits"], can_add=attempt["can_add"],
                            attach_ok=attempt["attach_ok"], requires_prerequisite=requires)
            evidence["bone_index"] = max(host_slot["bone_index"], -1)
        slots[slot] = {"verdict": verdict, "reason": reason, "evidence": evidence}
        verdicts.append(verdict)
        reasons.add(reason)
    if not verdicts:
        return {"verdict": "geometry_missing", "reasons": ["no_compatible_native_slot"], "slots": slots}
    return {"verdict": _combine(verdicts), "reasons": sorted(reasons), "slots": slots}


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
    for light in context["representatives"]:
        base["lights"][light] = _evaluate_light(light, light_entries.get(light, MISSING), slot_names, host_slots,
                                                context["preflights"].get(light, MISSING), prerequisites, variant)
    for control in context["controls"]:       # control evidence must be complete even though it is not a verdict
        entry_c = light_entries.get(control, MISSING)
        if entry_c is MISSING or entry_c is None:
            reasons.add("control_light_not_observed")
        else:
            index, problem = _per_slot(entry_c, slot_names)
            if problem != "light_not_spawned" and (problem or any(_light_slot(item) is None for item in index.values())):
                reasons.add("control_light_evidence_invalid")
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
    """A host verdict is only as good as the probe that produced it."""
    if record["verdict"] == "qualified" or (control_hits and record["verdict"] == "geometry_missing"):
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
