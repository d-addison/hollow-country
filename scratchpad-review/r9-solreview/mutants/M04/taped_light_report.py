"""Join taped-light probe observations with the config classification into the final matrix.

Inputs are the classification written by ``tools.audit.flashlight_matrix classify`` and the
observations JSON written by a native run of the probe staged by
``tools/setup/taped_light_probe.py``. Every host ends in exactly one verdict (fix round 8, Tier S):

  server_qualified  every server-observable requirement of Tier S holds and the client still has to confirm it
                    (always reported together with ``client_pending``; nothing is accepted): the host slot is
                    observed and the light fits it, the native CanAddAttachmentEx check allowed the light (directly, or
                    after the named rail handguard prerequisite, the route is recorded), the native create succeeded
                    and FindAttachment read the light back, a host GetSelectionList proxy normalises to a
                    CfgNonAIVehicles ``Proxy<basename>`` entry whose model equals the proxy path and whose
                    inventorySlot lists the slot, the light model has its beamStart/beamEnd memory points when they
                    were observed, and a native switch action addresses the slot (SWITCH_ACTIONS). Older evidence
                    (a slot selection, memory point or bone that the engine itself named) is the legacy route.
  geometry_missing  a real negative: the light does not fit any observed native slot, the native check refused the
                    attach for a reason the observation attributes to the host, or the host's complete proxy list
                    carries only light proxies of other slots (``proxy_belongs_to_other_slot``). Absence of a proxy
                    in Object.GetSelectionList is never negative evidence: the server model may not list it.
  not_server_evidencable
                    the host has no native light slot at all, so a dedicated server cannot evidence a native pair.
                    This is outside the v1 scope (config-slot reuse and backpack/helmet mounts are post-v1, issue #58),
                    not a failure; the host record carries a ``v1_scope`` note.
  excluded          the classification excluded the class (reasons are kept).
  pending           the observation is missing, mistyped, duplicated, ambiguous, timed out, contradicts the config
                    classification, the probe itself was not clean, or only the client can decide it
                    (``pending_client``, with ``client_required`` in the evidence).

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
  * Server qualification needs a clean probe: complete status, matching spawn/delete counters, no
    handles surviving release, a residual census that was complete (not truncated), the native
    slot set resolved and no control light attached anywhere.

Model evidence (probe-003: InventorySlots.GetSelectionForSlotId returns nothing natively, so the proxy join
is the evidence). The hook lists the host model's ``proxy:<path>.<nnn>`` selections with their
``CfgNonAIVehicles Proxy<basename>`` entry (exists, model, inventorySlot) and, per host, the resolution LODs: every
LOD that Object.GetLODS/GetLODName lists whose WHOLE name is a non-negative number ("0", "1", "1.000"), each with its
LOD.GetSelections list. Per proxy row and per resolution LOD the hook records the first selection whose whole normalised
path equals the model path and that selection's first vertex. Only numeric LODs are ever read: geometry, memory,
landContact, geometryView, geometryFire, view*, VIEW_PILOT and every other non-numeric LOD are never a substitute.
Superseded in round 8 (the resolution LOD requirement below is now a diagnostic). A slot had proxy evidence only when ALL of these held: the native attach was ok, a listed proxy has an existing entry,
an entry class equal to ``Proxy<basename>``, a ``model`` that equals the proxy path (case-insensitive, slashes and the
.p3d extension normalised), an inventorySlot list holding the slot, AND at least one resolution LOD whose selection scan
was complete holds a proxy selection ``proxy:<path>.<digits>`` equal to the model path as a whole (re-verified here)
with a finite first vertex. The per-LOD lookup is one result per model: rows of the same model that disagree on it are
malformed. The proxy name alone is never evidence. A contains-style match (AttachmentsOutOfReach.c reads view-LOD
selections with Contains()) is not used: a different model whose name merely contains the path, or a generic selection,
must not stand in for the proxy.

This proves a model proxy slot on the server-side model only (the resolution LODs of the host and the light model as the
dedicated server loads them). It says nothing about the beam render, the switch, two-client presentation, removal by
hand, tape consumption or persistence; those stay pending in every output.

  * Contradictory proxy evidence is malformed before any slot is matched: a name that is not exactly
    ``proxy:<path>.<digits>`` with a non-empty basename, two rows of one selection identity that read the config or the
    resolution lookup differently, two rows of one config entry that disagree, a mistyped field, or LOD/selection
    bookkeeping that contradicts itself (a non-numeric LOD name in the resolution list, a scan flag that disagrees with
    its counts, a selection claimed in a LOD whose list failed or is empty, a per-row LOD list that is not the host's).
    Malformed, missing or truncated proxy evidence is pending, never qualified.
  * Coherent aliases collapse: spellings that normalise to one identity (``proxy:/dz/.../x.001`` next to
    ``proxy:dz/.../x.001``, case and slash variants, identical copies) that read the same config entry and the same
    resolution lookup are ONE evidence identity, never malformed. The raw rows and ``proxy_count`` stay as read and the
    number of collapsed copies is reported per host as ``diagnostics.proxy_alias_collapsed``. Conflicting readbacks of
    one identity stay malformed in either order.
  * The hook lists at most eight inventory slots per proxy row and reports ``slot_count`` and ``slot_scan_complete``:
    a row that matches the model but dropped slots, with the slot not among those listed, is pending
    (``proxy_slot_list_truncated``). A listed slot still qualifies over a truncated tail.
  * The hook scans at most 16 resolution LODs and keeps at most 512 selections of each (``res_lod_count``,
    ``res_lods_scanned``, ``res_scan_complete`` per host, ``selection_count`` and ``scan_complete`` per LOD). One LOD whose
    scan was complete and that holds the proxy is enough, whatever another LOD reported. Otherwise the pending reasons,
    in the order they are decided: resolution_lod_evidence_missing (the row is from a round 4 to 6 producer that
    wrote view-LOD fields and no per-LOD list; consistent, but it proves nothing about resolution LODs),
    resolution_enumeration_failed (Object.GetLODS failed or listed too many LODs, or a LOD.GetSelections call reported
    failure, whatever its out array held), resolution_lod_absent (the list is ok and holds no numeric LOD),
    resolution_selection_mismatch (a scanned LOD names another model), resolution_vertex_missing and
    resolution_vertex_invalid (no first vertex, or not three finite numbers), resolution_evidence_truncated (a scan was
    cut at a cap, so the proxy may be in the part not read), resolution_proxy_missing (every numeric LOD was scanned
    completely and none holds the proxy selection). None of these is a negative finding. The qualified reasons are
    native_attach_with_resolution_lod_proxy_slot and, with the rail handguard variant,
    native_attach_with_resolution_lod_proxy_slot_and_rail_handguard_prerequisite. The evidence is source-level and
    server-side; it is not client rendering.
  * A truncated proxy list without a qualifying row is pending; a complete list without one is geometry_missing.

Fix round 8 (probe-006: qualified=0 because the server-side resolution selection lists were all unavailable):
  * LOD.GetSelections was called on a null script instance for 199 LODs, so no resolution selection list existed to
    join. Resolution-vertex membership is now a diagnostic only (``resolution_status``, ``resolution_lod``,
    ``resolution_selection``, ``resolution_vertex`` in the slot evidence) and never selects or blocks a verdict. An LOD
    whose instance was null is recorded as ``resolution_lod_instance_unavailable`` (``instance_ok`` false, ``native_count``
    -1), distinct from a genuine false or an empty list; the older statuses below keep their names as diagnostics.
  * Proxy names are normalised before the join: slashes and backslashes, case, the ``proxy:`` prefix and the ``.NNN``
    instance suffix. The proxy config entry (exists, ``Proxy<basename>``, model path, inventorySlot) is the join.
  * A positive legacy slot flag (selection, memory point or bone) needs the selection name that was queried; a flag
    with an empty or absent name is invalid evidence, and a name that disagrees with the top-level slot-to-selection
    mapping (or a mapping the engine did not know) is pending.
  * The slot evidence keeps the base and the prerequisite-variant attempts apart (``base_attempt``, ``variant_attempt``,
    ``prerequisite`` with the readback and rail flag, ``evaluated_attempt``, ``route``); the base facts are never
    overwritten. Optional stronger evidence (``proxy_bone_index``, ``bone_object_matches_light``) is recorded and never
    gates. A control spawn without ECE_IN_INVENTORY (``spawn_control``) and per-LOD selection counts (``lod_counts``) are
    carried as diagnostics.

Fix round 7 (probe-005: the dedicated server has no LOD named "view" on any of the hosts):
  * The LODs the server lists are the resolution LODs "0"/"1" (sometimes repeated), geometry, memory, landContact,
    geometryView and geometryFire, plus VIEW_PILOT on a few hosts. The earlier "view" LOD requirement came from a client
    inventory reachability helper (AttachmentsOutOfReach.IsAttachmentReachable, called only from 5_Mission/GUI/
    InventoryNew), not from the visible model, and is replaced by the resolution-LOD proxy requirement above. Rows of
    probe-004 and probe-005 have no per-LOD facts and come out pending (resolution_lod_evidence_missing), never
    qualified. ``view_lod_absent_on_server`` was the round-6 reason for the missing view LOD; no verdict uses it now.
  * ``view_by_name`` and the LOD names (``diagnostics.lod``) stay diagnostics only; they never select evidence. They must
    still agree with the resolution scan: the list flag, a count not below the scanned LODs, and the numeric names in the
    (at most eight) list being the leading numeric LODs the scan read, else the host is malformed.

Fix round 6 (probe-004: the dedicated server answered no view LOD on any host and no proxy config entry was found):
  * proxy_config_name_mismatch: the earlier producer derived the config class from the whole path ("Proxy" + the path,
    or "Proxy/dz/...") because it looked for the base name before normalising backslashes. A row from that producer (no
    ``cfg_tried`` facts) whose cfg_class is exactly that whole-path spelling is internally consistent and was never a
    config lookup of the real class: it is pending with this reason and the host is not trusted, not malformed. Any other
    class mismatch, and a whole-path class next to ``cfg_tried`` facts, stays malformed.
  * ``cfg_tried``/``cfg_tried_exists`` (at most four names, the first being cfg_class and its ConfigIsExisting answer)
    and ``sep_slash``/``sep_backslash`` (separator counts of the raw selection name) are validated when present.
  * The header ``diagnostics`` (string self-test, CfgNonAIVehicles scan) and the per-host LOD names, resolution scan
    and proxy-name facts are carried into the report as ``native_diagnostics`` and ``hosts[].diagnostics``. They never
    change a verdict.

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
VERDICT_ORDER = ("server_qualified", "geometry_missing", "not_server_evidencable", "excluded", "pending")
# Native switch actions that find a light by its slot name (the Tier S requirement that a switch can address the slot):
# ActionTurnOnWeaponFlashlight.c:27 (weaponFlashlight) and :32 (pistolFlashlight), ActionTurnOnHelmetFlashlight.c:40
# (helmetFlashlight); the TurnOff variants address the same slots. A test pins the table; a slot outside it is pending.
SWITCH_ACTIONS = {"weaponFlashlight": "ActionTurnOnWeaponFlashlight.c:27",
                  "pistolFlashlight": "ActionTurnOnWeaponFlashlight.c:32",
                  "helmetFlashlight": "ActionTurnOnHelmetFlashlight.c:40"}
V1_SCOPE_IN = "v1 covers native light-slot pairs: a vanilla light slot and proxy, directly or after a native rail handguard."
V1_SCOPE_OUT = ("Out of v1 scope, not a failure: no native light slot on this host. Config-slot reuse and backpack/helmet "
                "mounts are post-v1 (issue #58).")
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
    "res_enum_ok", "res_lod_count", "res_lods_scanned", "res_scan_complete", "res_lods", "name", "list_ok",
    "selection_count", "scan_complete", "vertex_ok", "vertex", "cfg_tried", "cfg_tried_exists", "sep_slash",
    "sep_backslash", "lod_list_ok", "lod_count", "lod_names", "lod_names_complete", "view_by_name", "diagnostics",
    "string_self_test", "cfg_nonai_scan", "selection_known", "beam_start", "beam_end", "instance_ok", "native_count",
    "proxy_bone_index", "proxy_bone_name", "proxy_bone_tried", "bone_object_checked", "bone_object_matches",
    "spawn_control", "spawn_flags", "selection_list_ok", "lod_counts", "lod_counts_total", "lod_counts_complete", "count")

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


def _slot_selections(observations):
    """{slot: (selection_known, selection)} from the top-level slot rows (InventorySlots.GetSelectionForSlotId), either value
    MISSING when mistyped. Unusable or duplicated rows are absent here; the integrity check reports them."""
    index, _problems = _keyed(observations.get("slots"), "slot")
    return {name: (_get(entry, "selection_known", "bool"), _get(entry, "selection", "str"))
            for name, entry in index.items() if entry is not None}


OPTIONAL_SLOT_KINDS = (("proxy_bone_index", "int"), ("proxy_bone_name", "str"), ("proxy_bone_tried", "int"))


def _host_slot_values(entry, name, top, reasons):
    """Typed evidence of one host slot row, or None when it is incomplete, mistyped or contradicts itself.

    The legacy flags (selection_on_model, memory_point, bone_index) are only evidence for the selection name that was
    queried: a positive flag with an empty or absent name is refused, and the name must agree with the top-level mapping
    when that row exists (a mapping the engine did not know is not an agreement). The optional proxy bone readback is
    typed when present and never required."""
    values = {"host_has_slot": _get(entry, "host_has_slot", "bool"), "selection_on_model": _get(entry, "selection_on_model", "bool"),
              "memory_point": _get(entry, "memory_point", "bool"), "bone_index": _get(entry, "bone_index", "int"),
              "selection": _get(entry, "selection", "str") if "selection" in entry else ""}
    optional = {key: (_get(entry, key, kind) if key in entry else None) for key, kind in OPTIONAL_SLOT_KINDS}
    if MISSING in values.values() or MISSING in optional.values():
        return None
    if values["selection_on_model"] or values["memory_point"] or values["bone_index"] >= 0:
        if not values["selection"]:
            reasons.add("slot_flag_without_selection_name")
            return None
        known = top.get(name)
        if known is not None and (known[0] is not True or known[1] is MISSING
                                  or known[1].casefold() != values["selection"].casefold()):
            reasons.add("slot_selection_disagree")
            return None
    return dict(values, **optional)


def _host_slots(row, slot_names, reasons, top):
    """Typed per-slot host evidence keyed by slot name; None marks an unusable slot entry."""
    index, problems = _keyed(row.get("slots"), "slot")
    if problems:
        reasons.add(_problem_reason("slot", problems))
    if set(index) != set(slot_names):
        reasons.add("slot_set_mismatch")
    result = {}
    for name, entry in index.items():
        values = None if entry is None else _host_slot_values(entry, name, top, reasons)
        if values is None:
            reasons.add("slot_evidence_invalid")
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
    return {"slot": slot, "attached": attached, "lights": index, "handguard": label, "found_type": found,
            "rail_functional": rail}


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


def _optional_pair(entry, first, second):
    """(first, second) when both bool keys are present, (None, None) when both are absent, else MISSING."""
    present = [key in entry for key in (first, second)]
    if not any(present):
        return None, None
    values = (_get(entry, first, "bool"), _get(entry, second, "bool"))
    return MISSING if not all(present) or MISSING in values else values


def _light_slot(entry):
    values = {key: _get(entry, key, "bool") for key in ("light_fits", "can_add", "attach_ok")}
    found = _get(entry, "found_type", "str")
    if MISSING in values.values() or found is MISSING:
        return None
    if values["attach_ok"] and not values["can_add"]:
        return None        # a create cannot succeed when the native check refused it: contradictory evidence
    if values["attach_ok"] != bool(found):
        return None        # the hook fills found_type only after a successful create and read-back
    beam = _optional_pair(entry, "beam_start", "beam_end")
    bone = _optional_pair(entry, "bone_object_checked", "bone_object_matches")
    if beam is MISSING or bone is MISSING or (bone[1] and not bone[0]):
        return None        # beam points and the bone-object readback are both-or-neither facts
    return dict(values, found_type=found, beam=None if beam[0] is None else beam[0] and beam[1],
                bone_object=bone[1] if bone[0] else None)


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
_NUMBER_TEXT = re.compile(r"-?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?")       # fullmatch only: "$" accepts a newline
_RES_LOD_NAME = re.compile(r"[0-9]+(?:\.[0-9]+)?")       # a whole name that is a non-negative number (fullmatch only)
PROXY_ROW_KINDS = (("selection", "str"), ("cfg_class", "str"), ("cfg_exists", "bool"), ("model", "str"),
                   ("inventory_slots", "list"), ("slot_count", "int"), ("slot_scan_complete", "bool"))
RES_HOST_KEYS = ("res_enum_ok", "res_lod_count", "res_lods_scanned", "res_scan_complete", "res_lods")
LOD_HOST_KEYS = ("lod_list_ok", "lod_count", "lod_names", "lod_names_complete", "view_by_name")
PROXY_HOST_KEYS = ("proxies", "proxy_count", "proxy_scan_complete") + RES_HOST_KEYS + LOD_HOST_KEYS
ROW_FACT_KEYS = ("cfg_tried", "cfg_tried_exists", "sep_slash", "sep_backslash")
MAX_LOD_NAMES = 8       # taped_light_probe.HCTL_LOD_NAMES (a test keeps both in step)
MAX_TRIED_NAMES = 4
MAX_RES_LODS = 16       # taped_light_probe.HCTL_RES_LODS: numeric LODs scanned per host
MAX_RES_SELECTIONS = 512       # taped_light_probe.HCTL_RES_SELECTIONS: selections kept per LOD


def _proxy_base(entry):
    """Typed config-side values of one proxy row, or None when a key is missing, mistyped or contradicts its bookkeeping."""
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


def _res_row(item, lod):
    """One row-side resolution entry against the host's LOD, or None when it is missing, mistyped or contradictory."""
    name, listed = _get(item, "name", "str"), _get(item, "list_ok", "bool")
    selection, vertex_ok = _get(item, "selection", "str"), _get(item, "vertex_ok", "bool")
    vertex = _get(item, "vertex", "list")
    if MISSING in (name, listed, selection, vertex_ok, vertex) or name != lod["name"] or listed != lod["list_ok"]:
        return None       # one entry per host LOD, in the host's order
    if selection and not (listed and lod["selection_count"] > 0):
        return None       # a selection cannot come out of a list that failed or holds nothing
    if (vertex_ok and not selection) or (not vertex_ok and vertex):
        return None       # a vertex needs the selection it belongs to, and is only listed when it was read
    return {"name": name, "selection": selection, "vertex_ok": vertex_ok, "vertex": tuple(vertex)}


def _proxy_row(entry, res):
    """Typed values of one proxy row against the host's resolution facts ``res``, or None when anything contradicts.

    ``res`` is None for a host from a round 4 to 6 producer: its rows must then carry no per-LOD list. A host with
    resolution facts needs exactly one entry per scanned LOD in every row."""
    values = _proxy_base(entry)
    if values is None:
        return None
    if res is None:
        return None if "res_lods" in entry else dict(values, res=None, res_key=None)
    rows = _get(entry, "res_lods", "list")
    if rows is MISSING or len(rows) != len(res["lods"]):
        return None
    found = [_res_row(item, lod) for item, lod in zip(rows, res["lods"])]
    if None in found:
        return None
    key = tuple((item["name"], item["selection"], item["vertex_ok"], item["vertex"]) for item in found)
    return dict(values, res=found, res_key=key)


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


def _lod_facts(row):
    """None for a legacy row without LOD facts, MISSING when they are partial, mistyped or contradictory, else the facts.

    These are the diagnostic LOD names (at most eight, with the count of every LOD the engine listed): they never select
    evidence. A failed list reports nothing, and the name count follows the cap."""
    present = [key in row for key in LOD_HOST_KEYS]
    if not any(present):
        return None
    listed, count, names = _get(row, "lod_list_ok", "bool"), _get(row, "lod_count", "int"), _get(row, "lod_names", "list")
    complete, by_name = _get(row, "lod_names_complete", "bool"), _get(row, "view_by_name", "bool")
    if not all(present) or MISSING in (listed, count, names, complete, by_name):
        return MISSING
    if not all(isinstance(name, str) for name in names) or count < 0 or len(names) > min(count, MAX_LOD_NAMES):
        return MISSING
    if complete != (count == len(names)) or (not listed and count):
        return MISSING
    return {"list_ok": listed, "count": count, "names": list(names), "names_complete": complete, "view_by_name": by_name}


def _res_lod(entry):
    """One host-side resolution LOD (name, list_ok, selection_count, scan_complete, instance_ok, native_count), or None when
    it contradicts itself.

    ``instance_ok`` and ``native_count`` (round 8) are both-or-neither. An LOD whose script instance was null
    (``instance_ok`` false) read nothing: no list, no count, ``native_count`` -1. They are None for an older producer."""
    name, listed = _get(entry, "name", "str"), _get(entry, "list_ok", "bool")
    total, complete = _get(entry, "selection_count", "int"), _get(entry, "scan_complete", "bool")
    if MISSING in (name, listed, total, complete) or not _RES_LOD_NAME.fullmatch(name) or total < 0:
        return None       # only a whole numeric LOD name is ever a resolution LOD
    if (not listed and total) or complete != (listed and total <= MAX_RES_SELECTIONS):
        return None       # a failed list counts nothing; a list above the cap was cut and is not complete
    instance, native = None, None
    present = [key in entry for key in ("instance_ok", "native_count")]
    if any(present):
        instance, native = _get(entry, "instance_ok", "bool"), _get(entry, "native_count", "int")
        if not all(present) or MISSING in (instance, native) or native < -1 or (instance and native < 0):
            return None
        if not instance and (listed or total or complete or native != -1):
            return None       # a null instance cannot list, count or complete anything
    return {"name": name, "list_ok": listed, "selection_count": total, "scan_complete": complete,
            "instance_ok": instance, "native_count": native}


def _res_host(row):
    """None for a host without resolution facts (a round 4 to 6 producer), MISSING when they are partial, mistyped or
    contradictory, else {"enum_ok", "count", "complete", "lods"} with the scanned numeric LODs in the engine's order.

    The hook scans at most MAX_RES_LODS numeric LODs: ``res_lods_scanned`` and the list are both min(count, cap); a
    failed enumeration scanned nothing; ``res_scan_complete`` means every numeric LOD was scanned and read completely."""
    present = [key in row for key in RES_HOST_KEYS]
    if not any(present):
        return None
    if not all(present):
        return MISSING
    enum_ok, count = _get(row, "res_enum_ok", "bool"), _get(row, "res_lod_count", "int")
    scanned, complete = _get(row, "res_lods_scanned", "int"), _get(row, "res_scan_complete", "bool")
    entries = _get(row, "res_lods", "list")
    if MISSING in (enum_ok, count, scanned, complete, entries) or count < 0 or scanned != len(entries) \
            or len(entries) != min(count, MAX_RES_LODS):
        return MISSING
    lods = [_res_lod(entry) for entry in entries]
    if None in lods or (not enum_ok and (count or lods or complete)):
        return MISSING
    if complete != (enum_ok and len(lods) == count and all(lod["scan_complete"] for lod in lods)):
        return MISSING
    return {"enum_ok": enum_ok, "count": count, "complete": complete, "lods": lods}


def _lods_agree(res, lod):
    """True when the diagnostic LOD list and the resolution scan describe one engine answer.

    The list flag matches, the LOD count is not below the scanned numeric LODs, and the numeric names in the (at most
    eight) name list are the leading numeric LODs the scan read (all of them when the name list is complete)."""
    if lod is None or lod["list_ok"] != res["enum_ok"] or lod["count"] < res["count"]:
        return False
    numeric = [name for name in lod["names"] if _RES_LOD_NAME.fullmatch(name)]
    scanned = [item["name"] for item in res["lods"]]
    return numeric == scanned if lod["names_complete"] else scanned[:len(numeric)] == numeric


def _whole_path_class(cfg_class, path):
    """True for exactly the earlier producer's mistake: "Proxy" + the whole path, with or without the leading slash."""
    return "/" in path and cfg_class.casefold() in ("proxy" + path, "proxy/" + path)


def _proxies(row):
    """Typed proxy evidence of a host row: ("missing",), ("malformed",), ("mismatch",) or
    ("ok", rows, truncated, res, conflict).

    Everything that makes the host's own read-back unreadable as a whole is malformed here, before any slot is matched:
    a malformed proxy name, resolution or LOD facts that contradict each other, a per-row LOD list that is not the host's,
    a row that contradicts its own bookkeeping. Copies of one identity that agree (a leading-slash alias, case and slash
    variants) collapse into one row. Copies that disagree (an identity read two ways, rows that read the same
    ``Proxy<basename>`` config entry differently or with different resolution results) are a *conflict*: ``conflict`` is
    None, or a dict with ``slots`` (every inventory slot any contradicting copy lists, exact names) and ``all`` (a copy's
    slot list was cut, so any slot may be implicated). The contradicting identities and config classes give no rows;
    ``_model_evidence`` withholds evidence from the implicated slots only."""
    if not any(key in row for key in PROXY_HOST_KEYS):
        return ("missing",)
    entries, count, complete = row.get("proxies"), _get(row, "proxy_count", "int"), _get(row, "proxy_scan_complete", "bool")
    if not isinstance(entries, list) or count is MISSING or complete is MISSING or not len(entries) <= count:
        return ("malformed",)
    res, lod = _res_host(row), _lod_facts(row)
    if res is MISSING or lod is MISSING or (res is not None and not _lods_agree(res, lod)):
        return ("malformed",)
    parsed, identities, lookups, mismatch = [], {}, {}, False
    conflict = {"slots": set(), "all": False, "names": set(), "classes": set()}

    def contradict(name, klass, *readings):
        conflict["names"].add(name)
        conflict["classes"].add(klass)
        for lookup in readings:
            conflict["slots"].update(lookup[2])
            conflict["all"] = lookup[3] > len(lookup[2])

    for entry in entries:
        values = _proxy_row(entry, res)
        name = _proxy_name(values["selection"]) if values else None
        if name is None:
            return ("malformed",)
        if values["cfg_class"].casefold() != ("Proxy" + name[0].rsplit("/", 1)[-1]).casefold():
            if values["cfg_tried"] is not None or not _whole_path_class(values["cfg_class"], name[0]):
                return ("malformed",)
            mismatch = True       # the earlier producer's whole-path class: consistent, but not a lookup of the real class
        klass = values["cfg_class"].casefold()
        lookup = (values["cfg_exists"], values["model"], tuple(values["inventory_slots"]), values["slot_count"],
                  values["res_key"])
        reading = (klass, lookup)
        known = identities.setdefault(name, reading)
        if known != reading:
            contradict(name, klass, known[1], lookup)
            conflict["classes"].add(known[0])
        elif lookups.setdefault(klass, (lookup, name))[0] != lookup:
            contradict(name, klass, lookups[klass][0], lookup)
            conflict["names"].add(lookups[klass][1])
        parsed.append((name, klass, dict(values, path=name[0]), known is reading))
    if mismatch:
        return ("mismatch",)
    rows = [item for name, klass, item, first in parsed
            if first and name not in conflict["names"] and klass not in conflict["classes"]]       # an alias adds no second row
    found = None
    if conflict["names"]:
        found = {"slots": frozenset(conflict["slots"]), "all": conflict["all"]}
    return ("ok", rows, count > len(entries) or not complete, res, found)


def _resolution_path(selection):
    """The whole proxy path a resolution selection names (lower case, forward slashes, no leading slash, no .p3d, the
    ``proxy:`` prefix and the all-digit ``.NNN`` instance suffix stripped), or None for any other spelling."""
    name = _proxy_name(selection)
    return name[0] if name else None


def _vertex(values):
    """Three finite numbers from the hook's number text, or None."""
    if len(values) != 3 or not all(isinstance(item, str) and _NUMBER_TEXT.fullmatch(item) for item in values):
        return None
    numbers = [float(item) for item in values]
    return numbers if all(math.isfinite(number) for number in numbers) else None


def _resolution_check(item, res):
    """(status, found) for one matching row: a diagnostic only, never a verdict input (fix round 8).

    ``found`` holds the LOD, selection and first vertex when a numeric LOD whose selection scan was complete holds the proxy
    selection whose whole normalised path equals the model path, with a finite first vertex; ``status`` is then "member".
    Otherwise ``found`` is None and ``status`` names why: resolution_lod_evidence_missing, resolution_enumeration_failed,
    resolution_lod_absent, resolution_lod_instance_unavailable (a null LOD instance: unavailable, not false),
    resolution_selection_mismatch, resolution_vertex_missing, resolution_vertex_invalid, resolution_evidence_truncated or
    resolution_proxy_missing."""
    if res is None:
        return "resolution_lod_evidence_missing", None       # a round 4 to 6 row: view-LOD fields, no per-LOD list
    if not res["enum_ok"]:
        return "resolution_enumeration_failed", None       # Object.GetLODS failed or listed too many LODs
    if not res["lods"]:
        return "resolution_lod_absent", None       # the list is ok and holds no numeric LOD; no other LOD stands in
    problem = None
    for lod, found in zip(res["lods"], item["res"]):
        if not lod["scan_complete"] or not found["selection"]:
            continue
        reason = None
        if len(item["model"]) <= 5 or _resolution_path(found["selection"]) != _path(item["model"]):
            reason = "resolution_selection_mismatch"       # the hook's claim is re-verified here, not trusted
        elif not found["vertex_ok"]:
            reason = "resolution_vertex_missing"
        elif _vertex(found["vertex"]) is None:
            reason = "resolution_vertex_invalid"
        else:
            return "member", {"lod": lod["name"], "selection": found["selection"], "vertex": _vertex(found["vertex"])}
        problem = problem or reason
    if any(lod["instance_ok"] is False for lod in res["lods"]):
        return "resolution_lod_instance_unavailable", None       # a null script instance: nothing could be read
    if not all(lod["list_ok"] for lod in res["lods"]):
        return "resolution_enumeration_failed", None       # LOD.GetSelections reported failure: that LOD may hold it
    if problem:
        return problem, None
    return ("resolution_evidence_truncated" if not res["complete"] else "resolution_proxy_missing"), None


def _host_diagnostics(row):
    """Per-host native facts for the reader: the LOD names, the resolution scan, what each proxy row tried and how many
    coherent aliases collapsed. Never read for a verdict."""
    facts, res = _lod_facts(row), _res_host(row)
    lod = {"status": "absent"} if facts is None else {"status": "malformed"} if facts is MISSING else facts
    if res is None or res is MISSING:
        resolution = {"status": "absent" if res is None else "malformed"}
    else:
        resolution = {"enum_ok": res["enum_ok"], "count": res["count"], "complete": res["complete"],
                      "lods": [dict(item) for item in res["lods"]]}
    names, seen, collapsed = [], set(), 0
    for entry in row.get("proxies") if isinstance(row.get("proxies"), list) else []:
        values = _proxy_base(entry)
        if values is None:
            continue
        identity = _proxy_name(values["selection"])
        if identity is not None:
            collapsed += identity in seen
            seen.add(identity)
        if values["cfg_tried"] is not None:
            names.append({"selection": values["selection"], "cfg_tried": list(values["cfg_tried"]),
                          "cfg_tried_exists": list(values["cfg_tried_exists"]), "sep_slash": values["sep_slash"],
                          "sep_backslash": values["sep_backslash"]})
    return {"lod": lod, "resolution": resolution, "proxy_names": names, "proxy_alias_collapsed": collapsed,
            "lod_counts": _lod_counts(row)}


MAX_LOD_COUNTS = 16       # taped_light_probe.HCTL_LOD_COUNTS: LODs whose native selection count the hook reads per host


def _lod_counts(row):
    """The per-LOD native selection counts (every LOD, not only the numeric ones), as a diagnostic.

    ``{"status": "absent"}`` for a row from an older producer, ``{"status": "malformed"}`` when a value is mistyped or
    contradicts its bookkeeping (a null instance reads -1, a usable one reads at least 0, ``complete`` means every listed LOD
    was counted), else the counts. Never read for a verdict."""
    if not any(key in row for key in ("lod_counts", "lod_counts_total", "lod_counts_complete")):
        return {"status": "absent"}
    entries, total, complete = _get(row, "lod_counts", "list"), _get(row, "lod_counts_total", "int"), \
        _get(row, "lod_counts_complete", "bool")
    if MISSING in (entries, total, complete) or not len(entries) <= min(total, MAX_LOD_COUNTS) or total < 0 \
            or complete != (total == len(entries)):
        return {"status": "malformed"}
    lods = []
    for entry in entries:
        name, count, instance = _get(entry, "name", "str"), _get(entry, "count", "int"), _get(entry, "instance_ok", "bool")
        if MISSING in (name, count, instance) or count < -1 or (instance and count < 0) or (not instance and count != -1):
            return {"status": "malformed"}
        lods.append({"name": name, "count": count, "instance_ok": instance})
    return {"status": "ok", "lods": lods, "total": total, "complete": complete}


def _spawn_control(observations):
    """The firearm control spawned without ECE_IN_INVENTORY (diagnostic): absent, malformed or the typed values."""
    if "spawn_control" not in observations:
        return {"status": "absent"}
    raw = observations["spawn_control"]
    if not isinstance(raw, dict):
        return {"status": "malformed"}       # a diagnostic of any other JSON type is malformed, never an abort
    kinds = (("class", "str"), ("spawned", "bool"), ("spawn_flags", "str"))
    values = {key: _get(raw, key, kind) for key, kind in kinds}
    optional = {key: _get(raw, key, kind) for key, kind in (("proxy_count", "int"), ("selection_list_ok", "bool"))
                if key in raw}
    if MISSING in values.values() or MISSING in optional.values() or optional.get("proxy_count", 0) < 0:
        return {"status": "malformed"}
    return dict({"status": "ok"}, **values, **optional)


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


def _implicated(proxies, slot):
    """True when proxy copies that contradict each other implicate this exact slot (never for an unrelated conflict)."""
    conflict = proxies[4] if proxies[0] == "ok" else None
    return conflict is not None and (conflict["all"] or slot in conflict["slots"])


def _model_evidence(host_slot, slot, proxies, slot_names):
    """Model evidence for one slot as a dict: ``source`` is one of

      selection         the engine named a selection for the slot and a legacy flag is positive (``selection``),
      proxy_config_slot a host proxy joined to its config entry names the slot (``selection`` is the proxy name,
                        ``resolution_status``/``resolution`` are the diagnostic resolution-LOD membership),
      other_slot        a complete proxy list carries only light proxies of other native light slots: a real negative,
      client            nothing the server can see decides it (no proxy for the slot, none against it),
      pending           ``detail`` is the pending reason.

    Malformed proxy evidence outranks every kind, because the host's read-back is then not trustworthy; so does an alias
    conflict that implicates this slot (``conflict`` is then True), and only such a slot. A proxy whose
    config entry is missing or whose lists were cut is pending, never negative."""
    if proxies[0] == "malformed" or _implicated(proxies, slot):
        return {"source": "pending", "detail": "proxy_evidence_malformed", "conflict": proxies[0] != "malformed"}
    if host_slot["selection_on_model"] or host_slot["memory_point"] or host_slot["bone_index"] >= 0:
        return {"source": "selection", "selection": host_slot["selection"]}
    if proxies[0] == "missing":
        return {"source": "pending", "detail": "proxy_evidence_missing"}
    if proxies[0] == "mismatch":
        return {"source": "pending", "detail": "proxy_config_name_mismatch"}
    _kind, rows, truncated, res, _conflict = proxies
    light_slots = set(slot_names)       # slot names are exact: only proxy paths and config class spellings are normalised
    slot_list_cut = other_slot = False
    for item in rows:
        if not item["cfg_exists"] or _path(item["model"]) != item["path"]:
            continue
        listed = set(item["inventory_slots"])
        if slot in listed:
            status, found = _resolution_check(item, res)
            return {"source": "proxy_config_slot", "selection": item["selection"], "resolution_status": status,
                    "resolution": found}
        if item["slot_count"] > len(item["inventory_slots"]):
            slot_list_cut = True       # the hook capped this row's slot list: the slot may be among the dropped ones
        elif listed & light_slots:
            other_slot = True
    if truncated:
        return {"source": "pending", "detail": "proxy_evidence_truncated"}
    if slot_list_cut:
        return {"source": "pending", "detail": "proxy_slot_list_truncated"}
    if any(not item["cfg_exists"] for item in rows):
        return {"source": "pending", "detail": "proxy_config_missing"}
    return {"source": "other_slot" if other_slot else "client"}


def _accepted(light, slot, model, attempt):
    """Verdict for an attach the native call allowed (can_add true); ``model`` is a _model_evidence result."""
    if not attempt["attach_ok"]:
        return "pending", "attach_create_failed"
    if attempt["found_type"] != light:
        return "pending", "attached_item_not_found_in_slot"
    source = model["source"]
    if source == "pending":
        return "pending", model["detail"]
    if source == "client":
        return "pending", "pending_client"
    if source == "other_slot":
        return "geometry_missing", "proxy_belongs_to_other_slot"
    if attempt["beam"] is False:
        return "pending", "light_beam_points_missing"       # observed and absent; an unobserved beam neither passes nor blocks
    if slot not in SWITCH_ACTIONS:
        return "pending", "no_native_switch_action_for_slot"
    if source == "proxy_config_slot":
        return "server_qualified", "native_attach_with_proxy_config_slot"
    return "server_qualified", "native_attach_with_model_selection"


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


def _attempt_record(attempt):
    """The raw facts of one attach attempt, as observed."""
    return {key: attempt[key] for key in ("can_add", "attach_ok", "found_type", "beam")}


def _evaluate_slot(light, slot, attempt, prerequisites, variant, slot_names, preflight, model):
    """Return the verdict record for one compatible host/light/slot observation.

    The record names the route (direct, or after the prerequisite handguard), keeps the base attempt and the variant attempt
    as separate facts, and marks which one was evaluated (``evaluated``); the base facts are never relabelled."""
    def outcome(verdict, reason, evaluated=attempt, route="direct", variant_attempt=None, prerequisite=None):
        return {"verdict": verdict, "reason": reason, "requires_prerequisite": route != "direct",
                "route": route, "evaluated": evaluated, "evaluated_attempt": "base" if evaluated is attempt else "variant",
                "base_attempt": _attempt_record(attempt),
                "variant_attempt": None if variant_attempt is None else _attempt_record(variant_attempt),
                "prerequisite": prerequisite}
    if model.get("conflict"):
        return outcome("pending", model["detail"])       # contradictory proxy copies outrank whatever the attach said
    if attempt["can_add"]:
        return outcome(*_accepted(light, slot, model, attempt))
    if light not in PREREQUISITE_LIGHTS:
        return outcome("geometry_missing", "native_attach_refused")
    if prerequisites is MISSING:
        return outcome("pending", "prerequisite_evidence_missing")
    owns_slot = any(has for has, _rail in prerequisites.values())
    if not owns_slot or any(rail for _has, rail in prerequisites.values()):
        return outcome("geometry_missing", "native_attach_refused")     # prerequisite not in play
    if variant is None:
        return outcome("pending", "refusal_may_depend_on_prerequisite")
    if variant is MISSING:
        return outcome("pending", "prerequisite_variant_invalid")
    if not variant["attached"]:
        return outcome("pending", "prerequisite_variant_failed")
    chosen, problem = _variant_attempt(variant["lights"].get(light, MISSING), slot, slot_names, preflight)
    if chosen is None:
        return outcome("pending", problem or "prerequisite_variant_incomplete")
    prerequisite = {"slot": variant["slot"], "handguard": variant["handguard"], "found_type": variant["found_type"],
                    "rail_functional": variant["rail_functional"], "attached": variant["attached"]}
    route = "after_prerequisite_handguard"
    if not chosen["can_add"]:
        return outcome("geometry_missing", "native_attach_refused_with_prerequisite", chosen, route, chosen, prerequisite)
    verdict, reason = _accepted(light, slot, model, chosen)
    if verdict == "server_qualified":
        reason = ("native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite"
                  if model["source"] == "proxy_config_slot" else "native_attach_with_rail_handguard_prerequisite")
    return outcome(verdict, reason, chosen, route, chosen, prerequisite)


def _combine(verdicts):
    for verdict in ("pending", "server_qualified", "geometry_missing"):
        if verdict in verdicts:
            return verdict
    return "not_server_evidencable"


def _pending(reason):
    return {"verdict": "pending", "reasons": [reason], "slots": {}}


def _slot_evidence(host_slot, attempt, result, model):
    """The evidence recorded for one evaluated slot: the host facts, both attempts, the route and the model join."""
    resolution = model.get("resolution") or {}
    evaluated = result["evaluated"]
    return {"host_has_slot": host_slot["host_has_slot"], "selection": host_slot["selection"],
            "selection_on_model": host_slot["selection_on_model"], "memory_point": host_slot["memory_point"],
            "bone_index": max(host_slot["bone_index"], -1), "light_fits": attempt["light_fits"],
            "can_add": evaluated["can_add"], "attach_ok": evaluated["attach_ok"],
            "requires_prerequisite": result["requires_prerequisite"], "route": result["route"],
            "evaluated_attempt": result["evaluated_attempt"], "base_attempt": result["base_attempt"],
            "variant_attempt": result["variant_attempt"], "prerequisite": result["prerequisite"],
            "model_evidence": model["source"],
            "proxy_selection": model["selection"] if model["source"] == "proxy_config_slot" else None,
            "resolution_status": model.get("resolution_status"), "resolution_lod": resolution.get("lod"),
            "resolution_selection": resolution.get("selection"), "resolution_vertex": resolution.get("vertex"),
            "proxy_bone_index": host_slot["proxy_bone_index"], "proxy_bone_name": host_slot["proxy_bone_name"],
            "proxy_bone_tried": host_slot["proxy_bone_tried"], "bone_object_matches_light": evaluated["bone_object"],
            "client_pending": result["verdict"] == "server_qualified",
            "client_required": result["reason"] == "pending_client"}


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
            model = _model_evidence(host_slot, slot, proxies, slot_names)
            result = _evaluate_slot(light, slot, attempt, prerequisites, variant, slot_names, preflight, model)
            verdict, reason = result["verdict"], result["reason"]
            evidence = _slot_evidence(host_slot, attempt, result, model)
        slots[slot] = {"verdict": verdict, "reason": reason, "evidence": evidence}
        verdicts.append(verdict)
        reasons.add(reason)
    if not verdicts:
        if not any(item and item["host_has_slot"] for item in host_slots.values()):
            return {"verdict": "not_server_evidencable", "reasons": ["no_native_light_slot"], "slots": slots}
        if any(item and item["host_has_slot"] and _implicated(proxies, name) for name, item in host_slots.items()):
            return _pending("proxy_evidence_malformed")       # the contradicted proxies name a slot this host owns
        return {"verdict": "geometry_missing", "reasons": ["no_compatible_native_slot"], "slots": slots}
    return {"verdict": _combine(verdicts), "reasons": sorted(reasons), "slots": slots}


# Host reasons that name one light's own evidence; the affected light is already pending on its own, and a
# missing or duplicated sibling alone does not invalidate an independently valid pair.
SIBLING_SCOPED_REASONS = frozenset({"duplicate_light_observation", "light_observation_missing", "proxy_alias_conflict"})


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
    host_slots = _host_slots(row, slot_names, reasons, context["slot_selections"])
    observed = {slot for slot, item in host_slots.items() if item and item["host_has_slot"]}
    base["v1_scope"] = {"in_scope": bool(observed), "note": V1_SCOPE_IN if observed else V1_SCOPE_OUT}
    configured = entry.get("native_light_slots")
    if not isinstance(configured, list) or observed != set(configured) or bool(observed) != (entry["group"] == "slot_host"):
        reasons.add("config_probe_conflict")
    light_entries, problems = _keyed(row.get("lights"), "light")
    if problems:
        reasons.add(_problem_reason("light", problems))
    prerequisites = _prerequisites(row)
    variant = _variant(row, prerequisites)
    proxies = _proxies(row)
    if proxies[0] == "ok" and proxies[4] is not None:
        reasons.add("proxy_alias_conflict")       # the host stays pending; only the implicated slots lose their evidence
    for light in context["representatives"]:
        base["lights"][light] = _evaluate_light(light, light_entries.get(light, MISSING), slot_names, host_slots,
                                                context["preflights"].get(light, MISSING), prerequisites, variant, proxies)
    for control in context["controls"]:       # control evidence must be complete even though it is not a verdict
        reasons |= _control_issues(light_entries, slot_names, control, context["preflights"].get(control, MISSING))
    invalidating = reasons - SIBLING_SCOPED_REASONS
    if invalidating:       # the host's evidence cannot be trusted, so neither can any pair derived from it
        _invalidate(base["lights"], invalidating, "host_evidence_invalid",
                    ("server_qualified", "geometry_missing", "not_server_evidencable"))
    if reasons:
        return dict(base, verdict="pending", reasons=sorted(reasons))
    records = list(base["lights"].values())
    if any(record["verdict"] == "pending" for record in records):
        detail = sorted({reason for record in records if record["verdict"] == "pending" for reason in record["reasons"]})
        return dict(base, verdict="pending", reasons=detail)
    if not observed:
        return dict(base, verdict="not_server_evidencable", reasons=["no_native_light_slot"])
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
    verdicts = ("server_qualified", "geometry_missing", "not_server_evidencable") if control_hits else ("server_qualified",)
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
               "preflights": _preflights(observations.get("lights"), slot_names, {e.get("name"): e for e in lights}),
               "slot_selections": _slot_selections(observations)}

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
        "schema_version": 1, "kind": REPORT_KIND, "acceptance": "PENDING", "tier": "S", "client_tier": "pending",
        "provenance": dict(provenance or {}),
        "probe": {key: observations.get(key) for key in ("status", "world", "version", "classes", "observed",
                                                         "hard_cap", "per_class_ms")},
        "representative_lights": representatives, "control_lights": controls, "native_light_slots": slot_names,
        "integrity": integrity, "native_diagnostics": _native_diagnostics(observations),
        "spawn_control": _spawn_control(observations),
        "control": {"unexpected_attachments": control_hits},
        "hosts": host_records,
        "denominators": dict({name: counts.get(name, 0) for name in VERDICT_ORDER}, hosts=len(host_records),
                             client_pending=counts.get("server_qualified", 0),
                             out_of_v1_scope=sum(1 for record in host_records
                                                 if record.get("v1_scope", {}).get("in_scope") is False),
                             host_light_pairs=dict(sorted(pair_counts.items())), reasons=dict(sorted(reasons.items()))),
        "unobserved_axes": {axis: "pending" for axis in UNOBSERVED_AXES},
        "note": "Dedicated-server observations only. server_qualified means Tier S: the observed native slot, the native "
                "attach call (directly or after the recorded rail handguard), the read-back, a host proxy joined to its "
                "CfgNonAIVehicles entry for the slot, the beam memory points where observed and a native switch action "
                "were seen on the server; every such pair is client_pending. Resolution-LOD membership is a diagnostic. "
                "Beam, switch, two-client presentation, removal by hand, tape consumption and persistence remain pending "
                "until runtime tests run. Hosts without a native light slot are not_server_evidencable and outside the "
                "v1 scope (post-v1, issue #58). Nothing here is accepted.",
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
