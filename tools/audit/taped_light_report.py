"""Join taped-light probe observations with the config classification into the final matrix.

Inputs are the classification written by ``tools.audit.flashlight_matrix classify`` and the
observations JSON written by a native run of the probe staged by
``tools/setup/taped_light_probe.py``. Every host ends in exactly one verdict:

  qualified         the engine reported a native slot, the representative light attached in
                    it through the native call, the attachment is found in that slot and the
                    host model carries geometry for the slot: a proxy selection whose
                    CfgNonAIVehicles entry exists, names the same model path, lists the slot
                    in inventorySlot and is present in the host's view LOD, or (older probes) a
                    slot selection, memory point or bone.
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
``CfgNonAIVehicles Proxy<basename>`` entry (exists, model, inventorySlot) and, per host, the view LOD
(Object.GetLODByName(LOD.NAME_VIEW) and LOD.GetSelections, the pattern 4_World/Systems/Inventory/AttachmentsOutOfReach.c
:97-135 reads) with the first view-LOD proxy selection whose whole normalised path equals the model path and its first
vertex. AttachmentsOutOfReach.c matches with Contains(); that heuristic is not used here, because a different model whose
name merely contains the path (``weaponlight_universal_extra``) or a generic selection must not stand in for the proxy. GetSelectionList alone does not establish view-LOD membership. A slot has proxy evidence only when a listed
proxy has an existing entry, an entry class equal to ``Proxy<basename>``, a ``model`` that equals the proxy path
(case-insensitive, slashes and the .p3d extension normalised), an inventorySlot list holding the slot, AND view-LOD
membership: a view LOD exists, its selection list call succeeded, a view proxy selection ``proxy:<path>.<digits>``
equals the model path as a whole (re-verified here) and has a finite first vertex. The view lookup is one result per
model: rows of the same model that disagree on it are malformed. The proxy name alone is never evidence.

  * Contradictory proxy evidence is malformed before any slot is matched: a name that is not exactly
    ``proxy:<path>.<digits>`` with a non-empty basename, a duplicate selection identity (even when the copies agree),
    two rows reading the same config entry differently, a mistyped field, or slot/view bookkeeping that contradicts
    itself. Malformed, missing or truncated proxy evidence is pending, never qualified.
  * The hook lists at most eight inventory slots per proxy row and reports ``slot_count`` and ``slot_scan_complete``:
    a row that matches the model but dropped slots, with the slot not among those listed, is pending
    (``proxy_slot_list_truncated``). A listed slot still qualifies over a truncated tail.
  * A view LOD that is absent, a missing, unmatched or truncated view selection scan, or a missing or non-finite first
    vertex is pending with its own reason (view_lod_missing, view_selection_missing, view_evidence_truncated,
    view_selection_mismatch, view_vertex_missing, view_vertex_invalid, and view_enumeration_failed when the
    selection list call itself reported failure, whatever its out array held), never qualified and never negative. The
    qualified reasons are native_attach_with_view_lod_proxy_slot and, with the rail handguard variant,
    native_attach_with_view_lod_proxy_slot_and_rail_handguard_prerequisite. This is source-level evidence of the native
    pattern; it does not prove client rendering, which stays pending with the other unobserved axes.
  * A truncated proxy list without a qualifying row is pending; a complete list without one is geometry_missing.

Fix round 6 (probe-004: the dedicated server answered no view LOD on any host and no proxy config entry was found):
  * view_lod_absent_on_server: the server listed its LODs (Object.GetLODS/GetLODName, ``lod_list_ok``) and none of them
    is named "view" (the script lookup Object.c:106-122 compares the lower-cased name). The names are reported per host
    under ``diagnostics.lod``; no other LOD is ever substituted for the view LOD. A failed or missing LOD list stays
    view_lod_missing. LOD facts that contradict each other (``view_lod`` against ``view_by_name`` or against a name list
    that is complete, a count below the listed names, more than eight names, a failed list that reports names) are
    malformed.
  * proxy_config_name_mismatch: the earlier producer derived the config class from the whole path ("Proxy" + the path,
    or "Proxy/dz/...") because it looked for the base name before normalising backslashes. A row from that producer (no
    ``cfg_tried`` facts) whose cfg_class is exactly that whole-path spelling is internally consistent and was never a
    config lookup of the real class: it is pending with this reason and the host is not trusted, not malformed. Any other
    class mismatch, and a whole-path class next to ``cfg_tried`` facts, stays malformed.
  * Finding, not a conclusion: every caller of AttachmentsOutOfReach.IsAttachmentReachable (the view-LOD pattern this join
    copies) is in 5_Mission/GUI/InventoryNew, the client inventory UI. A dedicated server therefore may simply not hold a
    view LOD; probe-004 measured a null GetLODByName(LOD.NAME_VIEW) but not why, and that stays open until the LOD names
    of a native run are read. Without a server-side view LOD this evidence axis can only be completed by a client run.
  * ``cfg_tried``/``cfg_tried_exists`` (at most four names, the first being cfg_class and its ConfigIsExisting answer)
    and ``sep_slash``/``sep_backslash`` (separator counts of the raw selection name) are validated when present.
  * The header ``diagnostics`` (string self-test, CfgNonAIVehicles scan) and the per-host LOD names and proxy-name facts
    are carried into the report as ``native_diagnostics`` and ``hosts[].diagnostics``. They never change a verdict.

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
import math
from pathlib import Path
import re
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
    "selection", "cfg_class", "cfg_exists", "model", "inventory_slots", "slot_count", "slot_scan_complete",
    "view_lod", "view_selection_count", "view_scan_complete", "view_list_ok", "view_selection", "view_vertex_ok",
    "view_vertex", "cfg_tried", "cfg_tried_exists", "sep_slash", "sep_backslash", "lod_list_ok", "lod_count",
    "lod_names", "lod_names_complete", "view_by_name", "diagnostics", "string_self_test", "cfg_nonai_scan")

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


def _proxy_name(selection):
    """(path, number) of a ``proxy:<path>.<nnn>`` selection, or None when the name is not exactly that shape.

    The prefix is matched case-insensitively, as the probe hook matches it. The instance suffix must be ASCII digits
    and the path must end in a non-empty basename; ``.garbage``, no suffix and an empty basename are all refused."""
    if selection[:len("proxy:")].lower() != "proxy:":
        return None
    stem, dot, number = selection[len("proxy:"):].replace("\\", "/").rpartition(".")
    if not dot or not number or not set(number) <= _ASCII_DIGITS or stem.endswith("/"):
        return None
    path = _path(stem)
    if not path or not path.rsplit("/", 1)[-1] or path.endswith("/"):
        return None
    return path, number


_ASCII_DIGITS = frozenset("0123456789")
_NUMBER_TEXT = re.compile(r"^-?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?$")
PROXY_ROW_KINDS = (("selection", "str"), ("cfg_class", "str"), ("cfg_exists", "bool"), ("model", "str"),
                   ("inventory_slots", "list"), ("slot_count", "int"), ("slot_scan_complete", "bool"),
                   ("view_selection", "str"), ("view_vertex_ok", "bool"), ("view_vertex", "list"))
VIEW_HOST_KEYS = ("view_lod", "view_selection_count", "view_scan_complete", "view_list_ok")
LOD_HOST_KEYS = ("lod_list_ok", "lod_count", "lod_names", "lod_names_complete", "view_by_name")
PROXY_HOST_KEYS = ("proxies", "proxy_count", "proxy_scan_complete") + VIEW_HOST_KEYS + LOD_HOST_KEYS
ROW_FACT_KEYS = ("cfg_tried", "cfg_tried_exists", "sep_slash", "sep_backslash")
MAX_LOD_NAMES = 8       # taped_light_probe.HCTL_LOD_NAMES (a test keeps both in step)
MAX_TRIED_NAMES = 4


def _proxy_row(entry):
    """Typed values of one proxy row, or None when a key is missing, mistyped or contradicts its own bookkeeping."""
    values = {key: _get(entry, key, kind) for key, kind in PROXY_ROW_KINDS}
    if MISSING in values.values() or not all(isinstance(item, str) for item in values["inventory_slots"]):
        return None
    listed = len(values["inventory_slots"])
    if values["slot_count"] < listed or values["slot_scan_complete"] != (values["slot_count"] == listed):
        return None       # the hook caps the slot list: a count above the listed slots is a truncated list
    values["cfg_tried"] = None       # legacy producer: the names it tried are unknown
    present = [key in entry for key in ROW_FACT_KEYS]
    if any(present):
        facts = _row_facts(entry, values)
        if facts is None:
            return None
        values.update(facts)
    return values


def _row_facts(entry, values):
    """The round-6 per-row facts, or None when a key is missing, mistyped or contradicts the row."""
    names, answers = _get(entry, "cfg_tried", "list"), _get(entry, "cfg_tried_exists", "list")
    slash, backslash = _get(entry, "sep_slash", "int"), _get(entry, "sep_backslash", "int")
    if MISSING in (names, answers, slash, backslash) or slash < 0 or backslash < 0:
        return None
    if not 1 <= len(names) <= MAX_TRIED_NAMES or len(answers) != len(names):
        return None
    if not all(isinstance(name, str) for name in names) or not all(isinstance(item, bool) for item in answers):
        return None
    if names[0] != values["cfg_class"] or answers[0] != values["cfg_exists"]:
        return None       # the first name tried is the row's class and its answer is cfg_exists
    return {"cfg_tried": tuple(names), "cfg_tried_exists": tuple(answers), "sep_slash": slash, "sep_backslash": backslash}


def _lod_facts(row, view_lod):
    """None for a legacy row without LOD facts, MISSING when they are partial, mistyped or contradictory, else the facts.

    The hook resolves the view LOD itself over every LOD the engine lists (the names are capped at eight for the report),
    so ``view_lod`` false with a successful list is a measured absence; a "view" name in the list (case-insensitive,
    as Object.c:106-122 compares) contradicts it, and a complete list without that name contradicts view_lod true."""
    present = [key in row for key in LOD_HOST_KEYS]
    if not any(present):
        return None
    listed, count, names = _get(row, "lod_list_ok", "bool"), _get(row, "lod_count", "int"), _get(row, "lod_names", "list")
    complete, by_name = _get(row, "lod_names_complete", "bool"), _get(row, "view_by_name", "bool")
    if not all(present) or MISSING in (listed, count, names, complete, by_name, view_lod):
        return MISSING
    if not all(isinstance(name, str) for name in names) or count < 0 or len(names) > min(count, MAX_LOD_NAMES):
        return MISSING
    named = any(name.casefold() == "view" for name in names)
    if by_name != view_lod or complete != (count == len(names)) or (not listed and (count or view_lod)):
        return MISSING
    if (named and not view_lod) or (view_lod and complete and not named):
        return MISSING
    return {"list_ok": listed, "count": count, "names": list(names), "names_complete": complete, "view_by_name": by_name}


def _whole_path_class(cfg_class, path):
    """True for exactly the earlier producer's mistake: "Proxy" + the whole path, with or without the leading slash."""
    return "/" in path and cfg_class.casefold() in ("proxy" + path, "proxy/" + path)


def _proxies(row):
    """Typed proxy evidence of a host row: ("missing",), ("malformed",), ("mismatch",) or ("ok", rows, truncated, view).

    Everything that makes the host's own read-back contradict itself is malformed here, before any slot is matched:
    a malformed proxy name, a duplicate selection identity (even when the copies agree), rows that read the same
    ``Proxy<basename>`` config entry differently or with different view results (the view lookup is one result per
    model, so the selection, the vertex flag and the vertex must agree too), a view selection claimed by a host without
    a view LOD or without a successful selection list."""
    if not any(key in row for key in PROXY_HOST_KEYS):
        return ("missing",)
    entries, count, complete = row.get("proxies"), _get(row, "proxy_count", "int"), _get(row, "proxy_scan_complete", "bool")
    view = {"lod": _get(row, "view_lod", "bool"), "count": _get(row, "view_selection_count", "int"),
            "complete": _get(row, "view_scan_complete", "bool"), "listed": _get(row, "view_list_ok", "bool")}
    if not isinstance(entries, list) or count is MISSING or complete is MISSING or not len(entries) <= count \
            or MISSING in view.values() or view["count"] < 0 \
            or (view["listed"] and not view["lod"]) or (not view["listed"] and (view["count"] or view["complete"])):
        return ("malformed",)       # no list without a LOD; a failed or skipped list has no selections and is not complete
    facts = _lod_facts(row, view["lod"])
    if facts is MISSING:
        return ("malformed",)
    view["absent"] = bool(facts and facts["list_ok"] and not view["lod"])       # measured: the server listed its LODs
    rows, identities, lookups, mismatch = [], set(), {}, False
    for entry in entries:
        values = _proxy_row(entry)
        name = _proxy_name(values["selection"]) if values else None
        if name is None:
            return ("malformed",)
        if values["cfg_class"].casefold() != ("Proxy" + name[0].rsplit("/", 1)[-1]).casefold():
            if values["cfg_tried"] is not None or not _whole_path_class(values["cfg_class"], name[0]):
                return ("malformed",)
            mismatch = True       # the earlier producer's whole-path class: consistent, but not a lookup of the real class
        lookup = (values["cfg_exists"], values["model"], tuple(values["inventory_slots"]), values["slot_count"],
                  values["view_selection"], values["view_vertex_ok"], tuple(values["view_vertex"]))
        if name in identities or lookups.setdefault(values["cfg_class"].casefold(), lookup) != lookup \
                or (values["view_selection"] and not (view["lod"] and view["count"] > 0)):
            return ("malformed",)
        identities.add(name)
        rows.append(dict(values, path=name[0]))
    if mismatch:
        return ("mismatch",)
    return ("ok", rows, count > len(entries) or not complete, view)


def _view_path(selection):
    """The whole proxy path a view selection names (lower case, forward slashes, no leading slash, no .p3d, the
    ``proxy:`` prefix and the all-digit ``.NNN`` instance suffix stripped), or None for any other spelling."""
    name = _proxy_name(selection)
    return name[0] if name else None


def _vertex(values):
    """Three finite numbers from the hook's number text, or None."""
    if len(values) != 3 or not all(isinstance(item, str) and _NUMBER_TEXT.match(item) for item in values):
        return None
    numbers = [float(item) for item in values]
    return numbers if all(math.isfinite(number) for number in numbers) else None


def _view_problem(item, view):
    """Pending reason when the row's view-LOD join does not hold up, else None. Nothing unknown is a pass."""
    if not view["lod"]:
        return "view_lod_absent_on_server" if view["absent"] else "view_lod_missing"
    if not view["listed"]:
        return "view_enumeration_failed"       # LOD.GetSelections reported failure: its output is unknown
    if not item["view_selection"]:
        return "view_selection_missing" if view["complete"] else "view_evidence_truncated"
    if len(item["model"]) <= 5 or _view_path(item["view_selection"]) != _path(item["model"]):
        return "view_selection_mismatch"       # the hook's claim is re-verified here, not trusted
    if not item["view_vertex_ok"]:
        return "view_vertex_missing"
    return None if _vertex(item["view_vertex"]) else "view_vertex_invalid"


def _host_diagnostics(row):
    """Per-host native facts for the reader: the LOD names and what each proxy row tried. Never read for a verdict."""
    facts = _lod_facts(row, _get(row, "view_lod", "bool"))
    lod = {"status": "absent"} if facts is None else {"status": "malformed"} if facts is MISSING else facts
    names = []
    for entry in row.get("proxies") if isinstance(row.get("proxies"), list) else []:
        values = _proxy_row(entry)
        if values and values["cfg_tried"] is not None:
            names.append({"selection": values["selection"], "cfg_tried": list(values["cfg_tried"]),
                          "cfg_tried_exists": list(values["cfg_tried_exists"]), "sep_slash": values["sep_slash"],
                          "sep_backslash": values["sep_backslash"]})
    return {"lod": lod, "proxy_names": names}


def _native_diagnostics(observations):
    """The header diagnostics (string self-test and CfgNonAIVehicles scan) when they are well formed.

    ``{"status": "absent"}`` for observations taken before the hook wrote them, ``{"status": "malformed"}`` when any
    value has the wrong type; nothing malformed is carried. They are measurements for the reader, not evidence."""
    if "diagnostics" not in observations:
        return {"status": "absent"}
    raw = observations["diagnostics"]
    if not isinstance(raw, dict):
        return {"status": "malformed"}
    result = {"status": "ok"}
    test = raw.get("string_self_test")
    if "string_self_test" in raw:
        if not isinstance(test, dict) or not isinstance(test.get("sample"), str) \
                or not all(_int(value) for key, value in test.items() if key != "sample"):
            return {"status": "malformed"}
        result["string_self_test"] = dict(test)
    scan = raw.get("cfg_nonai_scan")
    if "cfg_nonai_scan" in raw:
        children = scan.get("weaponlight_children") if isinstance(scan, dict) else None
        if not isinstance(scan, dict) or not isinstance(children, list) or len(children) > 8 \
                or not all(isinstance(child, dict) and isinstance(child.get("name"), str)
                           and isinstance(child.get("model"), str) for child in children) \
                or not all(_int(scan.get(key)) for key in ("child_count", "scanned", "proxy_named")) \
                or not isinstance(scan.get("complete"), bool):
            return {"status": "malformed"}
        result["cfg_nonai_scan"] = {"child_count": scan["child_count"], "scanned": scan["scanned"],
                                    "complete": scan["complete"], "proxy_named": scan["proxy_named"],
                                    "weaponlight_children": [dict(child) for child in children]}
    return result


def _model_evidence(host_slot, slot, proxies):
    """(source, detail, view) for one slot: source is selection, view_lod_proxy_slot, none or pending.

    ``detail`` is the pending reason, or the proxy selection of a view_lod_proxy_slot; ``view`` holds that row's view
    selection and first vertex. Selection, memory point and bone are the older evidence; proxy evidence is the join of
    a proxy selection to its config entry, and then to the host's view LOD (Object.GetLODByName(LOD.NAME_VIEW)). A
    row that would match the slot but has no view-LOD membership is pending, never qualified and never negative.
    Malformed proxy evidence outranks both kinds, because the row's evidence is then not trustworthy."""
    if proxies[0] == "malformed":
        return "pending", "proxy_evidence_malformed", None
    if host_slot["selection_on_model"] or host_slot["memory_point"] or host_slot["bone_index"] >= 0:
        return "selection", None, None
    if proxies[0] == "missing":
        return "pending", "proxy_evidence_missing", None
    if proxies[0] == "mismatch":
        return "pending", "proxy_config_name_mismatch", None
    _kind, rows, truncated, view = proxies
    wanted, pending, slot_list_cut = slot.casefold(), None, False
    for item in rows:
        if not item["cfg_exists"] or _path(item["model"]) != item["path"]:
            continue
        if wanted in {name.casefold() for name in item["inventory_slots"]}:
            problem = _view_problem(item, view)
            if problem is None:
                return "view_lod_proxy_slot", item["selection"], {"view_selection": item["view_selection"],
                                                                  "view_vertex": _vertex(item["view_vertex"])}
            pending = pending or problem
        elif item["slot_count"] > len(item["inventory_slots"]):
            slot_list_cut = True       # the hook capped this row's slot list: the slot may be among the dropped ones
    if pending:
        return "pending", pending, None
    if truncated:
        return "pending", "proxy_evidence_truncated", None
    if slot_list_cut:
        return "pending", "proxy_slot_list_truncated", None
    if any(not item["cfg_exists"] for item in rows):
        return "pending", "proxy_config_missing", None
    return "none", None, None


def _accepted(light, model, attempt):
    """Verdict for an attach the native call allowed (can_add true); ``model`` is a _model_evidence result."""
    if not attempt["attach_ok"]:
        return "pending", "attach_create_failed"
    if attempt["found_type"] != light:
        return "pending", "attached_item_not_found_in_slot"
    if model[0] == "pending":
        return "pending", model[1]
    if model[0] == "view_lod_proxy_slot":
        return "qualified", "native_attach_with_view_lod_proxy_slot"
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
        reason = ("native_attach_with_view_lod_proxy_slot_and_rail_handguard_prerequisite"
                  if model[0] == "view_lod_proxy_slot"
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
                            proxy_selection=model[1] if model[0] == "view_lod_proxy_slot" else None,
                            view_selection=(model[2] or {}).get("view_selection"),
                            view_vertex=(model[2] or {}).get("view_vertex"))
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
    base["diagnostics"] = _host_diagnostics(row)
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
        "integrity": integrity, "native_diagnostics": _native_diagnostics(observations),
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
