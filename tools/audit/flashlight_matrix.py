"""Bounded #56 config candidate matrix; pure Python, no files or engine calls.

Input is the native row schema after upstream manifest/hash validation. This
function does not perform that validation. Config/script ancestry, observed slot
tokens and gameplay eligibility are distinct; no pair is accepted or rejected
as gameplay compatible. Non-candidates remain in the class denominator.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

MAX_ROWS = 16384
MAX_FIELDS = 96
MAX_VALUES = 128
MAX_ANCESTORS = 64
MAX_PAIRS = 65536
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_JSON_NODES = 8000000
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,511}\Z")
# Exact native script declarations inspected in installed 1.30.164289:
# ItemBase/{Flashlight,PortableGasLamp,Roadflare,Torch,ChemLight,Spotlight,
# Blowtorch}.c, Switchable_Base/{UniversalLight,TLRLight}.c and
# Clothing/Headtorch_ColorBase.c. Matching CONFIG ancestry is only a hint;
# it does not establish that the associated script class executes for a row.
LIGHT_CONFIG_ANCHORS = frozenset((
    "Flashlight", "UniversalLight", "TLRLight", "Headtorch_ColorBase",
    "Chemlight_ColorBase", "PortableGasLamp", "Roadflare", "Torch",
    "Spotlight", "Blowtorch"))
HOST_ROLES = ("gun_candidate", "backpack_candidate", "headgear_candidate",
              "ambiguous_equipment_candidate")
UNKNOWN_AXES = ("native_eligibility", "improvised_eligibility", "geometry",
                "proxies", "beam", "power", "switch", "held_worn_stored", "replication")


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _copy_json(value, budget, depth=0):
    """Copy bounded JSON data before classification; cycles hit the depth cap."""
    budget[1] -= 1
    _require(depth <= 12 and budget[1] >= 0, "input_structure_budget")
    if isinstance(value, dict):
        _require(len(value) <= 128, "mapping_budget")
        out = {}
        for key, child in value.items():
            _require(type(key) is str and len(key) <= 128, "invalid_json_key")
            budget[0] -= len(json.dumps(key, ensure_ascii=True)) + 2
            out[key] = _copy_json(child, budget, depth + 1)
        budget[0] -= 2
    elif type(value) in (list, tuple):
        _require(len(value) <= MAX_ROWS, "array_budget")
        out = [_copy_json(child, budget, depth + 1) for child in value]
        budget[0] -= len(out) + 2
    else:
        _require(type(value) in (str, int, float, bool, type(None)), "non_json_value")
        if type(value) is str:
            _require(len(value) <= 4096 and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
                     "string_budget_or_surrogate")
        if type(value) is int:
            _require(value.bit_length() <= 63, "integer_budget")
        if type(value) is float:
            _require(math.isfinite(value), "nonfinite_value")
        budget[0] -= len(json.dumps(value, ensure_ascii=True, allow_nan=False))
        out = value
    _require(budget[0] >= 0, "input_byte_budget")
    return out


def _digest(value, limit):
    digest, size = hashlib.sha256(), 0
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False)
    for text in encoder.iterencode(value):
        data = text.encode("ascii")
        size += len(data)
        _require(size <= limit, "serialized_byte_budget")
        digest.update(data)
    return digest.hexdigest()


def _identifier(value):
    return type(value) is str and IDENTIFIER.fullmatch(value) is not None


def _prepare(rows):
    identities = set()
    for row in rows:
        _require(isinstance(row, dict) and _identifier(row.get("ConfigRoot"))
                 and _identifier(row.get("ItemClass")), "invalid_class_identity")
        identity = (row["ConfigRoot"].casefold(), row["ItemClass"].casefold())
        _require(identity not in identities, "duplicate_class_identity")
        identities.add(identity)
        ancestors, fields = row.get("ConfigAncestors"), row.get("Fields")
        _require(type(ancestors) is list and len(ancestors) <= MAX_ANCESTORS
                 and all(_identifier(v) for v in ancestors), "invalid_config_ancestry")
        _require(type(fields) is list and len(fields) <= MAX_FIELDS, "field_budget_or_shape")
        seen = set()
        for field in fields:
            _require(isinstance(field, dict) and type(field.get("ConfigPath")) is str
                     and 0 < len(field["ConfigPath"]) <= 512, "invalid_field_path")
            key = field["ConfigPath"].casefold()
            _require(key not in seen, "duplicate_config_field")
            seen.add(key)
            for values in field.values():
                if isinstance(values, list):
                    _require(len(values) <= MAX_VALUES, "field_array_budget")
        fields.sort(key=lambda f: (f["ConfigPath"].casefold(), f["ConfigPath"]))
    rows.sort(key=lambda r: (r["ConfigRoot"].casefold(), r["ItemClass"].casefold()))


def _captured(field):
    return (isinstance(field, dict) and type(field.get("ValueCaptured")) in (int, bool)
            and field["ValueCaptured"] == 1)


def _tokens(field):
    if not _captured(field):
        return [], False
    if field.get("ReadAs") == "text_array" and field.get("ConfigTypeName") == "CT_ARRAY":
        values = field.get("TextValues")
    elif field.get("ReadAs") == "text" and field.get("ConfigTypeName") == "CT_STRING":
        values = [field.get("ValueText")]
    else:
        return [], False
    if not isinstance(values, list) or not all(type(v) is str and len(v) <= 512 for v in values):
        return [], False
    return sorted(set(v for v in values if v)), True


def _scope(field):
    if not _captured(field) or field.get("ReadAs") != "number":
        return None
    key = {"CT_INT": "ValueInt", "CT_FLOAT": "ValueFloat"}.get(field.get("ConfigTypeName"))
    value = field.get(key) if key else None
    return value if type(value) in (int, float) else None


def _classify(row):
    root, name = row["ConfigRoot"], row["ItemClass"]
    root_key = root.casefold()
    fields = {f["ConfigPath"].casefold(): f for f in row["Fields"]}
    slots, slot_readable = _tokens(fields.get("inventoryslot"))
    attachments, attachment_readable = _tokens(fields.get("attachments"))
    family = {v.casefold() for v in row["ConfigAncestors"] + [name]}
    roles, reasons = [], []
    if root_key == "cfgweapons":
        roles.append("gun_candidate")
        reasons.append("weapon_root_not_proof_of_firearm_or_item_eligibility")
    if root_key == "cfgvehicles":
        if "Back" in slots:
            roles.append("backpack_candidate")
        if "Headgear" in slots:
            roles.append("headgear_candidate")
        if not slots and family.intersection(("clothing", "clothing_base")):
            roles.append("ambiguous_equipment_candidate")
            reasons.append("clothing_config_family_without_usable_category_hint")
    if root_key in ("cfgvehicles", "cfgweapons"):
        if family.intersection(a.casefold() for a in LIGHT_CONFIG_ANCHORS):
            roles.append("light_candidate")
            reasons.append("named_config_light_family_not_script_execution_proof")
        if any(path.startswith("energymanager ") for path in fields):
            if "light_candidate" not in roles:
                roles.append("light_candidate")
            reasons.append("energy_metadata_does_not_prove_light")
    if slots or attachments:
        reasons.append("slot_tokens_not_verified_attachment_eligibility")
    if "inventoryslot" in fields and not slot_readable:
        reasons.append("unusable_inventorySlot")
    if "attachments" in fields and not attachment_readable:
        reasons.append("unusable_attachments")
    status = "CANDIDATE_UNKNOWN" if roles else "UNRESOLVED"
    if root_key not in ("cfgweapons", "cfgvehicles"):
        status = "AUDIT_SCOPE_EXCLUDED"
        reasons.append("root_outside_equipment_endpoint_selection_not_gameplay_incompatibility")
    if not roles and status == "UNRESOLVED":
        reasons.append("no_relevant_metadata_hint_category_and_light_role_unknown")
    selected = {"model", "clothingtypes male", "clothingtypes female", "scope",
                "inventoryslot", "attachments", "hasrailfunctionality"}
    metadata = [f for f in row["Fields"] if f["ConfigPath"].casefold() in selected
                or f["ConfigPath"].casefold().startswith("energymanager ")]
    return {"id": root + ":" + name, "root": root, "name": name,
            "config_ancestors": row["ConfigAncestors"],
            "config_parent": row.get("ParentClass"), "script_ancestry": "UNKNOWN",
            "scope": _scope(fields.get("scope")), "roles": sorted(roles),
            "status": status, "reasons": sorted(reasons), "metadata": metadata,
            "inventory_slot_tokens": slots, "attachment_tokens": attachments}


def build_matrix(rows, provenance):
    """Return deterministic class/pair candidates from already validated rows.

    Limits reject invalid/oversized inputs with ValueError. Pair overflow retains
    every class plus a deterministic prefix, exact denominators and a partial
    flag. No I/O, manifest verification, native API calls or gameplay mutations.
    Provenance is copied, not authenticated. Slots are always unverified here.
    """
    _require(type(rows) in (list, tuple) and len(rows) <= MAX_ROWS, "row_budget_or_shape")
    _require(type(provenance) is dict, "provenance_shape")
    copied = _copy_json({"rows": rows, "provenance": provenance},
                        [MAX_INPUT_BYTES, MAX_JSON_NODES])
    rows, provenance = copied["rows"], copied["provenance"]
    _prepare(rows)
    classes = [_classify(row) for row in rows]
    hosts = [c for c in classes if any(role in c["roles"] for role in HOST_ROLES)]
    lights = [c for c in classes if "light_candidate" in c["roles"]]
    possible = len(hosts) * len(lights)
    pairs = []
    # Only visit the bounded prefix, not the full Cartesian product.
    for host in hosts:
        if len(pairs) >= MAX_PAIRS:
            break
        for light in lights[:MAX_PAIRS - len(pairs)]:
            pairs.append({"host": host["id"], "light": light["id"],
                          "observed_slot_overlap": sorted(set(host["attachment_tokens"])
                                                          & set(light["inventory_slot_tokens"])),
                          "slot_evidence": "UNVERIFIED",
                          **dict.fromkeys(UNKNOWN_AXES, "UNKNOWN")})
    counts = {"input_classes": len(classes), "candidate_hosts": len(hosts),
              "candidate_lights": len(lights), "possible_pairs": possible,
              "emitted_pairs": len(pairs), "omitted_pairs": possible - len(pairs),
              "by_root": dict(sorted(Counter(c["root"] for c in classes).items())),
              "by_status": dict(sorted(Counter(c["status"] for c in classes).items())),
              "by_role": dict(sorted(Counter(r for c in classes for r in c["roles"]).items()))}
    result = {"schema_version": 1, "kind": "flashlight_candidate_matrix",
              "provenance": provenance, "source_rows_sha256": _digest(rows, MAX_INPUT_BYTES),
              "upstream_manifest_validation": "NOT_PERFORMED_BY_THIS_FUNCTION",
              "anchor_policy_native_snapshot": "1.30.164289",
              "full_coverage": False, "full_feature_pass": False,
              "pair_enumeration_complete": len(pairs) == possible,
              "stop_reason": "pair_budget" if len(pairs) != possible else "",
              "denominators": counts, "classes": classes, "pairs": pairs,
              "required_behavior": {"removal_tool_required": False, "tape_consumed": True,
                                    "tape_refunded": False, "fresh_tape_each_remount": True,
                                    "conserve": ["host", "light", "battery", "condition"],
                                    "tape_quantity": "UNMEASURED", "acceptance": "PENDING"},
              "unknowns": list(UNKNOWN_AXES) + ["script_ancestry", "unclassified_items",
                                                "array_element_types", "inventory_atomicity"],
              "limits": {"rows": MAX_ROWS, "pairs": MAX_PAIRS,
                         "input_bytes": MAX_INPUT_BYTES, "output_bytes": MAX_OUTPUT_BYTES}}
    _digest(result, MAX_OUTPUT_BYTES)
    return result


# ---------------------------------------------------------------------------
# Host / light classification (config evidence only; geometry stays unobserved)
# ---------------------------------------------------------------------------

CLASSIFICATION_KIND = "flashlight_host_light_classification"
# CfgSlots names found as attachments[]/inventorySlot[] tokens in the private
# native-035 capture: weapons carry weaponFlashlight/pistolFlashlight, one helmet
# carries helmetFlashlight, UniversalLight/TLRLight carry the matching inventory slots.
NATIVE_LIGHT_SLOTS = ("helmetFlashlight", "pistolFlashlight", "weaponFlashlight")
PROBE_CONTROL_LIGHT = "Flashlight"
_FLAME_FAMILY = frozenset(("torch", "chemlight_colorbase", "roadflare", "portablegaslamp", "blowtorch"))
_TEST_NAME = re.compile(r"(?:^|_)test(?:bed)?(?:$|_)", re.I)
_BASE_NAME = re.compile(r"(?:^|_)base$|[a-z0-9]Base$")


def _text_value(field):
    if not _captured(field) or field.get("ReadAs") != "text" or field.get("ConfigTypeName") != "CT_STRING":
        return None
    value = field.get("ValueText")
    return value if type(value) is str and len(value) <= 512 else None


def _number_value(field):
    if not _captured(field) or field.get("ReadAs") != "number":
        return None
    key = {"CT_INT": "ValueInt", "CT_FLOAT": "ValueFloat"}.get(field.get("ConfigTypeName"))
    value = field.get(key) if key else None
    return value if type(value) in (int, float) else None


def _common_exclusions(entry):
    """Reasons shared by hosts and lights; every applicable one is kept."""
    reasons = []
    fields = {f["ConfigPath"].casefold(): f for f in entry["metadata"]}
    scope = entry["scope"]
    if scope is None:
        reasons.append("scope_unreadable")
    elif scope < 2:
        reasons.append("scope_below_2")
    if _BASE_NAME.search(entry["name"]):
        reasons.append("base_class_name")
    if "ruined" in entry["name"].casefold():
        reasons.append("ruined_variant")
    if _TEST_NAME.search(entry["name"]):
        reasons.append("test_variant")
    model = _text_value(fields.get("model"))
    if model is None:
        reasons.append("model_unreadable")
    elif not model.strip():
        reasons.append("model_empty")
    return reasons


def _host_record(entry):
    role = next(r for r in HOST_ROLES if r in entry["roles"])
    slots = sorted(set(entry["attachment_tokens"]) & set(NATIVE_LIGHT_SLOTS))
    reasons = _common_exclusions(entry)
    if "light_candidate" in entry["roles"]:
        reasons.append("energy_device_not_a_host")
    if role == "ambiguous_equipment_candidate":
        reasons.append("no_host_category")
    group = "excluded" if reasons else ("slot_host" if slots else "no_slot_host")
    return {"id": entry["id"], "root": entry["root"], "name": entry["name"], "role": role,
            "group": group, "native_light_slots": slots, "scope": entry["scope"],
            "exclusion_reasons": sorted(reasons)}


def _energy_model(entry):
    attachments = entry["attachment_tokens"]
    fields = {f["ConfigPath"].casefold(): f for f in entry["metadata"]}
    if any(token.startswith("Battery") for token in attachments):
        return "battery_slot"
    if "GasCanister" in attachments:
        return "fuel_canister"
    if "Rags" in attachments:
        return "rags_fuel"
    if _number_value(fields.get("energymanager convertenergytoquantity")):
        return "consumed_charge"
    if _number_value(fields.get("energymanager plugtype")) == 2 or "energymanager cordlength" in fields:
        return "mains_cord"
    return "unclassified"


def _light_record(entry):
    family = {v.casefold() for v in entry["config_ancestors"] + [entry["name"]]}
    slots = sorted(set(entry["inventory_slot_tokens"]) & set(NATIVE_LIGHT_SLOTS))
    reasons = _common_exclusions(entry)
    if entry["name"].casefold() == "raycaster":
        reasons.append("raycaster_tool_not_a_light")
    if reasons:
        group = "excluded"
    elif slots:
        group = "mount_light"
    elif "headtorch_colorbase" in family:
        group = "worn_light"
    elif family & _FLAME_FAMILY:
        group = "flame_or_chemical_light"
    elif "spotlight" in family:
        group = "mains_light"
    elif "flashlight" in family:
        group = "handheld_battery_light"
    else:
        group = "energy_device_not_light"
    role = ""
    if group == "mount_light":
        role = "representative"
    elif group == "handheld_battery_light" and entry["name"] == PROBE_CONTROL_LIGHT:
        role = "control"
    return {"id": entry["id"], "root": entry["root"], "name": entry["name"], "group": group,
            "native_slots": slots, "inventory_slot_tokens": entry["inventory_slot_tokens"],
            "energy_model": _energy_model(entry), "scope": entry["scope"],
            "exclusion_reasons": sorted(reasons), "probe_role": role}


def classify_matrix(matrix):
    """Group candidate hosts (slot/no slot/excluded) and lights from a build_matrix result.

    Every candidate host and light stays in the output with its group and reasons so the
    denominators are exact. Groups are CONFIG evidence: a slot host still needs a native
    attach observation and a no-slot host has no native proxy to reuse.
    """
    _require(type(matrix) is dict and matrix.get("kind") == "flashlight_candidate_matrix"
             and type(matrix.get("classes")) is list, "not_a_flashlight_matrix")
    hosts, lights = [], []
    for entry in matrix["classes"]:
        if any(role in entry["roles"] for role in HOST_ROLES):
            hosts.append(_host_record(entry))
        if "light_candidate" in entry["roles"]:
            lights.append(_light_record(entry))
    hosts.sort(key=lambda h: h["id"].casefold())
    lights.sort(key=lambda l: l["id"].casefold())
    counts = {"hosts": len(hosts), "lights": len(lights),
              "slot_host": sum(1 for h in hosts if h["group"] == "slot_host"),
              "no_slot_host": sum(1 for h in hosts if h["group"] == "no_slot_host"),
              "excluded": sum(1 for h in hosts if h["group"] == "excluded"),
              "by_role": {"%s/%s" % key: value for key, value in
                          sorted(Counter((h["role"], h["group"]) for h in hosts).items())},
              "exclusion_reasons": dict(sorted(Counter(r for h in hosts for r in h["exclusion_reasons"]).items())),
              "light_groups": dict(sorted(Counter(l["group"] for l in lights).items())),
              "light_exclusion_reasons": dict(sorted(Counter(r for l in lights
                                                             for r in l["exclusion_reasons"]).items()))}
    return {"schema_version": 1, "kind": CLASSIFICATION_KIND,
            "provenance": matrix.get("provenance"), "source_rows_sha256": matrix.get("source_rows_sha256"),
            "native_light_slots": list(NATIVE_LIGHT_SLOTS),
            "probe_lights": sorted(l["name"] for l in lights if l["probe_role"]),
            "hosts": hosts, "lights": lights, "denominators": counts,
            "acceptance": "PENDING",
            "note": "config classification only; geometry, attach result and presentation are unobserved"}


def load_manifest_rows(manifest, sha256):
    """Admit a pinned native capture manifest and return its rows (private data stays outside Git)."""
    try:
        from . import item_compatibility as native
    except ImportError:  # executed as a script from tools/audit
        import item_compatibility as native
    admitted = native.scan_manifest(manifest, sha256)
    directory, _ = native.parent_handle(manifest)
    state = {"bytes": 0, "nodes": 0, "pins": []}
    rows = []
    for entry in admitted["files"]:
        raw = native.read_file(directory, entry["file"], native.MAX_CHUNK_BYTES, state)
        document = native.strict_json(raw, state)
        if entry["file"] != "manifest.json":
            rows.extend(document["Rows"])
    return rows


def _checkout_root():
    return Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classify flashlight mount hosts and lights from a native capture.")
    commands = parser.add_subparsers(dest="command", required=True)
    classify = commands.add_parser("classify", help="write the host/light classification JSON")
    source = classify.add_mutually_exclusive_group(required=True)
    source.add_argument("--rows", help="JSON list of already admitted native rows")
    source.add_argument("--manifest", help="pinned native item-audit manifest.json (private data)")
    classify.add_argument("--manifest-sha256", help="pinned manifest SHA-256 (required with --manifest)")
    classify.add_argument("--out", required=True, help="new output file outside the source checkout")
    args = parser.parse_args(argv)
    if args.manifest and not args.manifest_sha256:
        parser.error("--manifest requires --manifest-sha256")
    try:
        out = Path(args.out).absolute()
        checkout = _checkout_root()
        if out == checkout or checkout in out.parents:
            raise ValueError("classification output must be outside the source checkout")
        if args.rows:
            with open(args.rows, "rb") as stream:
                data = stream.read(MAX_INPUT_BYTES + 1)
            _require(len(data) <= MAX_INPUT_BYTES, "rows_file_budget")
            rows, provenance = json.loads(data), {"source": "rows-file"}
        else:
            rows = load_manifest_rows(args.manifest, args.manifest_sha256)
            provenance = {"source": "native-manifest", "manifest_sha256": args.manifest_sha256}
        document = classify_matrix(build_matrix(rows, provenance))
        encoded = json.dumps(document, indent=1, sort_keys=True, ensure_ascii=True, allow_nan=False)
        with open(out, "x", encoding="ascii") as stream:
            stream.write(encoded + "\n")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"flashlight_matrix: {error}", file=sys.stderr)
        return 1
    counts = document["denominators"]
    print(f"classification: hosts={counts['hosts']} slot={counts['slot_host']} "
          f"no_slot={counts['no_slot_host']} excluded={counts['excluded']} lights={counts['lights']} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
