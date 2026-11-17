"""Join taped-light probe observations with the config classification into the final matrix.

Inputs are the classification written by ``tools.audit.flashlight_matrix classify`` and the
observations JSON written by a native run of the probe staged by
``tools/setup/taped_light_probe.py``. Every host ends in exactly one verdict:

  qualified         the engine reported a native slot, the representative light attached in
                    it through the native call, the attachment is found in that slot and the
                    host model carries a selection, memory point or bone for the slot.
  geometry_missing  the engine reported no compatible native slot, refused the native attach,
                    or the attach has no model selection to render at (no proxy is invented).
  excluded          the classification excluded the class (reasons are kept).
  pending           the observation is missing, ambiguous, timed out, contradicts the config
                    classification or failed for an unexplained reason.

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
# Observation keys this module reads; a test proves the generated hook emits each of them.
CONSUMED_KEYS = (
    "schema", "kind", "status", "counters", "spawned", "deleted", "live_after_release", "residual_probe_types",
    "hosts", "lights", "class", "root", "group", "timed_out", "slots", "slot", "host_has_slot",
    "selection_on_model", "memory_point", "bone_index", "per_slot", "light", "light_fits", "can_add",
    "attach_ok", "found_type", "fits_native_slots", "fits")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _objects(value, what):
    _require(isinstance(value, list) and all(isinstance(item, dict) for item in value), f"{what} must be a list of objects")
    return value


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _slot_evidence(host_slot, light_slot):
    return {"host_has_slot": host_slot.get("host_has_slot") is True,
            "selection_on_model": host_slot.get("selection_on_model") is True,
            "memory_point": host_slot.get("memory_point") is True,
            "bone_index": host_slot["bone_index"] if _int(host_slot.get("bone_index")) else -1,
            "light_fits": light_slot.get("light_fits") is True,
            "can_add": light_slot.get("can_add") is True,
            "attach_ok": light_slot.get("attach_ok") is True}


def _evaluate_slot(light, evidence, light_slot):
    """Return (verdict, reason) for one compatible host/light/slot observation."""
    if not evidence["can_add"]:
        return "geometry_missing", "native_attach_refused"
    if not evidence["attach_ok"]:
        return "pending", "attach_create_failed"
    if light_slot.get("found_type") != light:
        return "pending", "attached_item_not_found_in_slot"
    if evidence["selection_on_model"] or evidence["memory_point"] or evidence["bone_index"] >= 0:
        return "qualified", "native_attach_with_model_selection"
    return "geometry_missing", "attached_without_model_selection"


def _combine(verdicts):
    if "qualified" in verdicts:
        return "qualified"
    if "pending" in verdicts:
        return "pending"
    return "geometry_missing"


def _evaluate_light(light, host_slots, light_entry, slot_names, preflight):
    """Verdict for one host x representative light from the host row's observations."""
    if preflight is None or preflight.get("spawned") is not True:
        return {"verdict": "pending", "reasons": ["light_not_spawned"], "slots": {}}
    if light_entry is None:
        return {"verdict": "pending", "reasons": ["light_not_observed"], "slots": {}}
    if light_entry.get("spawned") is not True:
        return {"verdict": "pending", "reasons": ["light_not_spawned"], "slots": {}}
    per_slot = {entry.get("slot"): entry for entry in _objects(light_entry.get("per_slot", []), "per_slot")}
    slots, reasons, verdicts = {}, set(), []
    for slot in slot_names:
        host_slot, light_slot = host_slots.get(slot), per_slot.get(slot)
        if host_slot is None or light_slot is None:
            slots[slot] = {"verdict": "pending", "reason": "slot_not_observed", "evidence": {}}
            verdicts.append("pending")
            reasons.add("slot_not_observed")
            continue
        evidence = _slot_evidence(host_slot, light_slot)
        if not (evidence["host_has_slot"] and evidence["light_fits"]):
            continue
        verdict, reason = _evaluate_slot(light, evidence, light_slot)
        slots[slot] = {"verdict": verdict, "reason": reason, "evidence": evidence}
        verdicts.append(verdict)
        reasons.add(reason)
    if not verdicts:
        return {"verdict": "geometry_missing", "reasons": ["no_compatible_native_slot"], "slots": slots}
    return {"verdict": _combine(verdicts), "reasons": sorted(reasons), "slots": slots}


def _host_slot_map(row):
    return {entry.get("slot"): entry for entry in _objects(row.get("slots", []), "slots")}


def _light_map(row):
    return {entry.get("light"): entry for entry in _objects(row.get("lights", []), "lights")}


def _evaluate_host(entry, rows, representatives, slot_names, preflights):
    base = {"class": entry["name"], "root": entry["root"], "group": entry["group"],
            "exclusion_reasons": list(entry.get("exclusion_reasons", [])), "lights": {}}
    if entry["group"] == "excluded":
        return dict(base, verdict="excluded", reasons=["classification_excluded"])
    if not rows:
        return dict(base, verdict="pending", reasons=["no_probe_row"])
    if len(rows) > 1 or rows[0].get("root") != entry["root"] or rows[0].get("group") != entry["group"]:
        return dict(base, verdict="pending", reasons=["ambiguous_probe_row"])
    row = rows[0]
    if row.get("spawned") is not True:
        return dict(base, verdict="pending", reasons=["host_not_spawned"])
    host_slots, light_entries = _host_slot_map(row), _light_map(row)
    has_native_slot = any(host_slots.get(slot, {}).get("host_has_slot") is True for slot in slot_names)
    for light in representatives:
        base["lights"][light] = _evaluate_light(light, host_slots, light_entries.get(light), slot_names,
                                                preflights.get(light))
    reasons = set()
    if row.get("timed_out") is True:
        reasons.add("class_timed_out")
    if has_native_slot != (entry["group"] == "slot_host"):
        reasons.add("config_probe_conflict")
    if reasons:
        return dict(base, verdict="pending", reasons=sorted(reasons))
    light_verdicts = [record["verdict"] for record in base["lights"].values()]
    if not has_native_slot:
        return dict(base, verdict="geometry_missing", reasons=["no_native_light_slot"])
    verdict = _combine(light_verdicts)
    detail = sorted({reason for record in base["lights"].values() if record["verdict"] == verdict
                     for reason in record["reasons"]})
    return dict(base, verdict=verdict, reasons=detail)


def _integrity(observations, unexpected, control_hits):
    issues = []
    if observations["status"] != "complete":
        issues.append("probe_status_partial")
    counters = observations.get("counters")
    clean = isinstance(counters, dict)
    if not clean:
        issues.append("counters_missing")
    else:
        if counters.get("spawned") != counters.get("deleted"):
            issues.append("spawned_not_equal_deleted")
            clean = False
        if counters.get("live_after_release") != 0:
            issues.append("live_after_release_nonzero")
            clean = False
        if counters.get("residual_probe_types") != 0:
            issues.append("residual_probe_types_nonzero")
            clean = False
    if control_hits:
        issues.append(f"control_light_attached_on_{len(control_hits)}_hosts")
    if unexpected:
        issues.append(f"unexpected_rows_{len(unexpected)}")
    return {"cleanup_clean": clean, "issues": issues, "unexpected_rows": unexpected}


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
    rows = _objects(observations.get("hosts"), "observation hosts")
    light_rows = _objects(observations.get("lights"), "observation lights")
    representatives = sorted(e["name"] for e in lights if e.get("probe_role") == "representative")
    controls = sorted(e["name"] for e in lights if e.get("probe_role") == "control")
    _require(representatives, "classification has no representative light")

    rows_by_class = {}
    for item in rows:
        rows_by_class.setdefault(item.get("class"), []).append(item)
    preflights = {}
    for item in light_rows:
        name = item.get("light")
        preflights[name] = None if name in preflights else item
    expected = {entry["name"] for entry in hosts if entry.get("group") != "excluded"}
    unexpected = sorted(str(name) for name in rows_by_class if name not in expected)

    host_records = [_evaluate_host(entry, rows_by_class.get(entry["name"], []) if entry["group"] != "excluded" else [],
                                   representatives, slot_names, preflights)
                    for entry in sorted(hosts, key=lambda e: (e["name"].casefold(), e["name"]))]
    control_hits = sorted({str(item.get("class")) for item in rows for light in _light_map(item).values()
                           if light.get("light") in controls
                           for slot in _objects(light.get("per_slot", []), "per_slot") if slot.get("attach_ok") is True})
    counts = Counter(record["verdict"] for record in host_records)
    pair_counts = Counter(light["verdict"] for record in host_records for light in record["lights"].values())
    reasons = Counter(reason for record in host_records for reason in record["reasons"])
    document = {
        "schema_version": 1, "kind": REPORT_KIND, "acceptance": "PENDING",
        "provenance": dict(provenance or {}),
        "probe": {key: observations.get(key) for key in ("status", "world", "version", "classes", "observed",
                                                         "hard_cap", "per_class_ms")},
        "representative_lights": representatives, "control_lights": controls, "native_light_slots": slot_names,
        "integrity": _integrity(observations, unexpected, control_hits),
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
