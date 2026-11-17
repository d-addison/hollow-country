"""Bounded, original declaration audit; never installs or qualifies a provider.

Hashes and observations are caller declarations, not authenticated evidence.
The reviewed human AI's built-in recovery can be explicitly allowed as a
declaration policy. This never authorizes arbitrary HC or infected relocation.
Native dependency leaves stop this graph's scope; this is not a complete
vanilla config or complete Workshop inventory.
"""
import json
import math
import re
import sys

MAX_INPUT_BYTES = 65536
SOURCE_PIN = "d84d3c73694969eba2f969e9178a1914e2f1b31d"
NATIVE_SCRIPTS_PIN = "09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a"
PACKAGE_PINS = {
    "2792982069": (SOURCE_PIN, frozenset((
        "DayZExpansion_AI_Scripts", "DayZExpansion_AI_Animations", "DayZExpansion_Sounds_AI"))),
    "2291785308": (SOURCE_PIN, frozenset((
        "DayZExpansion_Core_Scripts", "DayZExpansion_ModStorage_Scripts"))),
    "1559212036": ("0763e7e7548c9a0bed6626afff835de80693ebf3", frozenset(("JM_CF_Scripts",))),
    "2545327648": ("245190266b4e72bb0519fbfdd68bbed71c1edc1f", frozenset(("DF_Scripts", "DF_GUI"))),
}
DEPENDENCIES = {
    "DayZExpansion_AI_Scripts": ("DZ_Characters", "DayZExpansion_Core_Scripts"),
    "DayZExpansion_AI_Animations": ("DZ_Anims_Anm_Player", "DZ_Anims_Cfg", "DZ_Characters"),
    "DayZExpansion_Sounds_AI": ("DZ_Sounds_Effects",),
    "DayZExpansion_Core_Scripts": ("DayZExpansion_ModStorage_Scripts", "DF_Scripts"),
    "DayZExpansion_ModStorage_Scripts": ("JM_CF_Scripts",),
    "JM_CF_Scripts": ("DZ_Data",), "DF_Scripts": ("DZ_Scripts", "DF_GUI"),
    "DF_GUI": (), "DZ_Data": (), "DZ_Scripts": (), "DZ_Characters": (),
    "DZ_Anims_Anm_Player": (), "DZ_Anims_Cfg": (), "DZ_Sounds_Effects": (),
}
RELOCATION_EVIDENCE = (
    "https://github.com/salutesh/DayZ-Expansion-Scripts/blob/"
    + SOURCE_PIN
    + "/DayZExpansion/AI/Scripts/4_World/DayZExpansion_AI/Entities/AI/eAIBase.c"
)
KNOWN_FLAGS = ("coverage_known", "spectators_known", "optics_known",
               "native_combat_known", "proximity_known")
VETO_FLAGS = ("visibility_current", "visibility_recent", "in_native_combat", "near_observer")
ACTOR_KEYS = ("id group_id inventory_items reload_mask flanking_outside_combat invincible "
              "damage_multiplier damage_received_multiplier headshot_resistance "
              "ammunition_units loadout_sha256")
RECEIPT_KEYS = ("receipt_id actor_id session world_sha256 source_commit artifact_sha256 "
                "build_sha256 native_scripts_sha256 effective_state_sha256 "
                "observed_ms now_ms clear_since_ms proximity_bound_m deleted_observed "
                + " ".join(KNOWN_FLAGS + VETO_FLAGS))


class InvalidManifest(ValueError):
    """Fixed public reason code; invalid input values never enter the message."""


def _need(condition, code="schema-invalid"):
    if not condition:
        raise InvalidManifest(code)


def _walk(value, depth=0, budget=None):
    if budget is None:
        budget = [2048]
    budget[0] -= 1
    _need(budget[0] >= 0 and depth <= 10, "input-budget")
    kind = type(value)
    if kind is dict:
        _need(len(value) <= 64, "input-budget")
        for key, child in value.items():
            _need(type(key) is str and len(key) <= 256, "input-budget")
            _walk(child, depth + 1, budget)
    elif kind is list:
        _need(len(value) <= 64, "input-budget")
        for child in value:
            _walk(child, depth + 1, budget)
    elif kind is str:
        _need(len(value) <= 256, "input-budget")
    elif kind is int:
        _need(abs(value) <= 9007199254740991, "input-budget")
    elif kind is float:
        _need(math.isfinite(value), "nonfinite-number")
    else:
        _need(value is None or kind is bool)


def _keys(value, names):
    _need(type(value) is dict and set(value) == set(names.split()))


def _array(value, maximum=64):
    _need(type(value) is list and len(value) <= maximum)


def _bool(value, nullable=False):
    _need(type(value) is bool or (nullable and value is None))


def _integer(value, low, high, nullable=False):
    _need((nullable and value is None) or (type(value) is int and low <= value <= high))


def _number(value, low, high, nullable=False):
    _need((nullable and value is None) or
          (type(value) in (int, float) and math.isfinite(value) and low <= value <= high))


def _match(value, pattern):
    _need(type(value) is str and re.fullmatch(pattern, value) is not None)


def _hash(value, width=64, nullable=False):
    if not (nullable and value is None):
        _match(value, "[0-9a-f]{" + str(width) + "}")


def _token(value):
    _match(value, "[A-Za-z0-9_.:-]{1,128}")


def _unique(rows, field):
    seen = set()
    for row in rows:
        _need(row[field] not in seen, "duplicate-identity")
        seen.add(row[field])


def _validate(m):
    _walk(m)
    _keys(m, "schema_version provider experimental_opt_in source build world artifacts addons policy retirements")
    _integer(m["schema_version"], 1, 1)
    _need(m["provider"] == "expansion-ai", "provider-unsupported")
    _bool(m["experimental_opt_in"])
    s, b, w = m["source"], m["build"], m["world"]
    _keys(s, "repository commit version snapshot_sha256")
    _match(s["repository"], "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
    _hash(s["commit"], 40)
    _hash(s["snapshot_sha256"])
    _match(s["version"], r"[0-9]+(?:\.[0-9]+){2,3}")
    _keys(b, "version scripts_sha256 executable_sha256")
    _match(b["version"], r"[0-9]+(?:\.[0-9]+){2,3}")
    _hash(b["scripts_sha256"])
    _hash(b["executable_sha256"])
    _keys(w, "name definition_sha256 session")
    _token(w["name"])
    _token(w["session"])
    _hash(w["definition_sha256"])

    a = m["artifacts"]
    _keys(a, "status items")
    _need(a["status"] in ("unknown", "pinned"))
    _array(a["items"], 4)
    _need(a["status"] != "unknown" or not a["items"])
    artifact_names = set()
    for item in a["items"]:
        _keys(item, "workshop_id source_commit inventory_sha256 addons")
        _match(item["workshop_id"], "[0-9]{1,16}")
        _hash(item["source_commit"], 40)
        _hash(item["inventory_sha256"])
        _array(item["addons"], 16)
        for addon in item["addons"]:
            _keys(addon, "name pbo_sha256 signature_sha256")
            _token(addon["name"])
            _hash(addon["pbo_sha256"])
            _hash(addon["signature_sha256"])
            _need(addon["name"] not in artifact_names, "duplicate-identity")
            artifact_names.add(addon["name"])
    _unique(a["items"], "workshop_id")

    _array(m["addons"], 32)
    for row in m["addons"]:
        _keys(row, "name requires")
        _token(row["name"])
        _array(row["requires"], 32)
        for name in row["requires"]:
            _token(name)
        _need(len(row["requires"]) == len(set(row["requires"])), "duplicate-identity")
    _unique(m["addons"], "name")

    p = m["policy"]
    _keys(p, "provisional_diagnostic_bounds limits effective_state_sha256 global_reload_mask "
             "global_reload_all global_flanking_outside_combat actors allow_builtin_stuck_recovery")
    _bool(p["allow_builtin_stuck_recovery"])
    _need(p["provisional_diagnostic_bounds"] is True)
    limits = p["limits"]
    _keys(limits, "max_actors max_groups max_items max_tick_work observer_max_age_ms hysteresis_ms proximity_bound_m")
    # Parser/tool safety ceilings, not selected gameplay defaults or measurements.
    for key, high in (("max_actors", 64), ("max_groups", 32), ("max_items", 128),
                      ("max_tick_work", 32), ("observer_max_age_ms", 1000000000),
                      ("hysteresis_ms", 1000000000)):
        _integer(limits[key], 1, high)
    _number(limits["proximity_bound_m"], 0.001, 10000000)
    _hash(p["effective_state_sha256"], nullable=True)
    _integer(p["global_reload_mask"], 0, 2147483647, nullable=True)
    _bool(p["global_reload_all"], nullable=True)
    _bool(p["global_flanking_outside_combat"], nullable=True)
    _array(p["actors"])
    for actor in p["actors"]:
        _keys(actor, ACTOR_KEYS)
        _token(actor["id"])
        _token(actor["group_id"])
        _integer(actor["inventory_items"], 0, 1000000)
        _integer(actor["ammunition_units"], 0, 1000000, nullable=True)
        _integer(actor["reload_mask"], 0, 2147483647, nullable=True)
        for key in ("flanking_outside_combat", "invincible"):
            _bool(actor[key], nullable=True)
        for key in ("damage_multiplier", "damage_received_multiplier", "headshot_resistance"):
            _number(actor[key], 0, 100, nullable=True)
        _hash(actor["loadout_sha256"], nullable=True)
    _unique(p["actors"], "id")

    _array(m["retirements"], 32)
    for row in m["retirements"]:
        _keys(row, RECEIPT_KEYS)
        for key in ("receipt_id", "actor_id", "session"):
            _token(row[key])
        for key in ("world_sha256", "artifact_sha256", "build_sha256",
                    "native_scripts_sha256", "effective_state_sha256"):
            _hash(row[key])
        _hash(row["source_commit"], 40)
        for key in ("observed_ms", "now_ms", "clear_since_ms"):
            _integer(row[key], 0, 9007199254740991)
        _number(row["proximity_bound_m"], 0.001, 10000000)
        for key in KNOWN_FLAGS + VETO_FLAGS + ("deleted_observed",):
            _bool(row[key], nullable=True)
    _unique(m["retirements"], "receipt_id")
    _unique(m["retirements"], "actor_id")


def _graph_reasons(rows):
    graph = {row["name"]: set(row["requires"]) for row in rows}
    visiting, visited = set(), set()

    def visit(name):
        _need(name not in visiting, "dependency-cycle")
        if name in visited:
            return
        visiting.add(name)
        for child in sorted(graph[name]):
            if child in graph:
                visit(child)
        visiting.remove(name)
        visited.add(name)

    for name in sorted(graph):
        visit(name)
    reasons = []
    if any(child not in graph for children in graph.values() for child in children):
        reasons.append("dependency-missing")
    if graph != {name: set(deps) for name, deps in DEPENDENCIES.items()}:
        reasons.append("dependency-pin-mismatch")
    return reasons


def _base_report():
    return dict(schema_valid=False, status="rejected", diagnostic_only=True,
                runtime_qualified=False, production_enabled=False, artifact_bytes_verified=False,
                artifact_pin_status="unknown", reasons=[], declared_clear_retirements=[],
                recovery_relocation_allowed=False,
                recovery_relocation_scope="reviewed-human-ai-built-in-stuck-recovery-only",
                recovery_relocation_source_pin=SOURCE_PIN,
                source_blocker_evidence=dict(url=RELOCATION_EVIDENCE,
                                            lines=["7205-7211", "7667-7689"]),
                dependency_scope="required-provider-subset-with-native-leaves",
                qualification="pending; declarations are not native or artifact proof")


def evaluate(manifest):
    """Return declaration diagnostics; a candidate never qualifies runtime use."""
    result = _base_report()
    try:
        _validate(manifest)
        reasons = _graph_reasons(manifest["addons"])
    except InvalidManifest as exc:
        result["reasons"] = [str(exc)]
        return result
    result.update(schema_valid=True, status="blocked")
    m, s, b, w, p = (manifest, manifest["source"], manifest["build"],
                      manifest["world"], manifest["policy"])
    limits = p["limits"]
    reviewed = (s["repository"] == "salutesh/DayZ-Expansion-Scripts"
                and s["commit"] == SOURCE_PIN and s["version"] == "1.9.84")
    recovery_allowed = reviewed and p["allow_builtin_stuck_recovery"]
    result["recovery_relocation_allowed"] = recovery_allowed
    if not reviewed:
        reasons.append("source-unreviewed")
    elif not recovery_allowed:
        reasons.append("source-teleport-unsupported")
    if not m["experimental_opt_in"]:
        reasons.append("experimental-opt-in-disabled")
    if b["version"] not in ("1.30.164289", "1.30.164289.70"):
        reasons.append("build-unreviewed")
    if b["scripts_sha256"] != NATIVE_SCRIPTS_PIN:
        reasons.append("native-scripts-pin-mismatch")
    if w["name"] != "chernarusplus":
        reasons.append("world-unreviewed")

    items = {item["workshop_id"]: item for item in m["artifacts"]["items"]}
    artifact_ok = m["artifacts"]["status"] == "pinned"
    result["artifact_pin_status"] = "declared" if artifact_ok else "unknown"
    if not artifact_ok:
        reasons.append("artifact-pins-missing")
    if set(items) != set(PACKAGE_PINS):
        reasons.append("artifact-package-closure")
        artifact_ok = False
    for wid, item in items.items():
        expected = PACKAGE_PINS.get(wid)
        if expected is None:
            artifact_ok = False
            continue
        commit, names = expected
        if item["source_commit"] != commit:
            reasons.append("artifact-source-pin-mismatch")
            artifact_ok = False
        if {row["name"] for row in item["addons"]} != names:
            reasons.append("artifact-addon-closure")
            artifact_ok = False

    actors = p["actors"]
    if not actors:
        reasons.append("actor-state-missing")
    if len(actors) > limits["max_actors"]:
        reasons.append("actor-budget-exceeded")
    if len({a["group_id"] for a in actors}) > limits["max_groups"]:
        reasons.append("group-budget-exceeded")
    if sum(a["inventory_items"] for a in actors) > limits["max_items"]:
        reasons.append("item-budget-exceeded")
    effective = ("effective_state_sha256", "global_reload_mask",
                 "global_reload_all", "global_flanking_outside_combat")
    if any(p[key] is None for key in effective):
        reasons.append("effective-state-unknown")
    if p["global_reload_all"] is True or p["global_reload_mask"] not in (None, 0):
        reasons.append("unlimited-ammunition")
    if p["global_flanking_outside_combat"] is True:
        reasons.append("outside-combat-flanking")
    for actor in actors:
        if any(actor[key] is None for key in (
                "reload_mask", "flanking_outside_combat", "invincible", "damage_multiplier",
                "damage_received_multiplier", "headshot_resistance", "ammunition_units",
                "loadout_sha256")):
            reasons.append("actor-state-unknown")
        if actor["reload_mask"] not in (None, 0):
            reasons.append("unlimited-ammunition")
        if actor["flanking_outside_combat"] is True:
            reasons.append("outside-combat-flanking")
        if (actor["invincible"] is True
                or actor["damage_multiplier"] not in (None, 1)
                or actor["damage_received_multiplier"] not in (None, 1)
                or actor["headshot_resistance"] not in (None, 0)):
            reasons.append("actor-damage-policy")

    receipt_work_ok = len(m["retirements"]) <= limits["max_tick_work"]
    if not receipt_work_ok:
        reasons.append("retirement-work-budget-exceeded")
    actor_ids = {a["id"] for a in actors}
    provider_hashes = {row["pbo_sha256"] for row in
                       items.get("2792982069", {}).get("addons", [])
                       if row["name"] == "DayZExpansion_AI_Scripts"}
    for row in m["retirements"]:
        vetoes = [] if receipt_work_ok else ["retirement-work-budget-exceeded"]
        if (not artifact_ok or not reviewed or row["actor_id"] not in actor_ids
                or row["session"] != w["session"]
                or row["world_sha256"] != w["definition_sha256"]
                or row["source_commit"] != s["commit"]
                or row["build_sha256"] != b["executable_sha256"]
                or row["native_scripts_sha256"] != b["scripts_sha256"]
                or row["effective_state_sha256"] != p["effective_state_sha256"]
                or row["artifact_sha256"] not in provider_hashes):
            vetoes.append("retirement-binding-mismatch")
        if (any(row[key] is not True for key in KNOWN_FLAGS)
                or any(row[key] is None for key in VETO_FLAGS)):
            vetoes.append("observer-inputs-unknown")
        if any(row[key] is True for key in VETO_FLAGS):
            vetoes.append("observer-retirement-veto")
        clear, observed, now = (row["clear_since_ms"], row["observed_ms"], row["now_ms"])
        if not clear <= observed <= now:
            vetoes.append("observer-clock-order")
        if now - observed > limits["observer_max_age_ms"]:
            vetoes.append("observer-stale")
        if observed - clear < limits["hysteresis_ms"]:
            vetoes.append("observer-hysteresis")
        if row["proximity_bound_m"] != limits["proximity_bound_m"]:
            vetoes.append("observer-bound-mismatch")
        if row["deleted_observed"] is not True:
            vetoes.append("retirement-deletion-unconfirmed")
        if not vetoes:
            result["declared_clear_retirements"].append(row["receipt_id"])
        reasons.extend(vetoes)
    result["reasons"] = sorted(set(reasons))
    if not result["reasons"] and m["experimental_opt_in"]:
        result["status"] = "candidate"
    return result


def decode_manifest(payload):
    """Strict bounded UTF-8 JSON object, with no duplicate keys or NaN coercion."""
    _need(type(payload) is bytes and len(payload) <= MAX_INPUT_BYTES, "input-budget")

    def pairs(entries):
        obj = {}
        for key, value in entries:
            _need(key not in obj, "duplicate-json-key")
            obj[key] = value
        return obj

    def integer(token):
        _need(len(token.lstrip("-")) <= 20, "integer-token-budget")
        return int(token)

    def constant(_token):
        raise InvalidManifest("nonfinite-number")

    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=pairs,
                           parse_int=integer, parse_constant=constant)
        _walk(value)
        _need(type(value) is dict)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise InvalidManifest("invalid-json") from None


def main():
    """stdin -> JSON; exit 1 valid diagnostic, 2 malformed. Never enables."""
    try:
        result = evaluate(decode_manifest(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)))
    except InvalidManifest as exc:
        result = _base_report()
        result["reasons"] = [str(exc)]
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 1 if result["schema_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
