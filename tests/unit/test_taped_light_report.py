"""Offline tests for the taped-light matrix report. Every fixture is explicit and synthetic.

Nothing here establishes DayZ behavior: the report only joins what a native probe run wrote
with the config classification, and these tests prove only that join logic.
"""
import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from tools.audit import taped_light_report as report
from tools.setup import taped_light_probe as probe

SLOTS = ["helmetFlashlight", "pistolFlashlight", "weaponFlashlight"]
LIGHTS = ["Flashlight", "TLRLight", "UniversalLight"]
FITS = {"UniversalLight": {"helmetFlashlight", "weaponFlashlight"}, "TLRLight": {"pistolFlashlight"}, "Flashlight": set()}


PREREQ_SLOTS = ["weaponHandguardAK", "weaponHandguardM4", "weaponHandguardMP5"]


def host(name, group, reasons=(), root="CfgWeapons", role="gun_candidate"):
    return {"id": f"{root}:{name}", "root": root, "name": name, "role": role, "group": group,
            "native_light_slots": ["weaponFlashlight"] if group == "slot_host" else [], "scope": 2,
            "exclusion_reasons": list(reasons)}


def classification(hosts):
    return {"schema_version": 1, "kind": probe.CLASSIFICATION_KIND, "native_light_slots": SLOTS,
            "probe_lights": LIGHTS, "hosts": hosts,
            "lights": [{"name": "UniversalLight", "probe_role": "representative", "group": "mount_light",
                        "native_slots": sorted(FITS["UniversalLight"])},
                       {"name": "TLRLight", "probe_role": "representative", "group": "mount_light",
                        "native_slots": sorted(FITS["TLRLight"])},
                       {"name": "Flashlight", "probe_role": "control", "group": "handheld_battery_light",
                        "native_slots": []}]}


def slot_obs(slot, has=False, on_model=False, memory=False, bone=-1, selection=None):
    """``selection`` overrides the queried selection name (default: the slot name for a host slot, else empty)."""
    return {"slot": slot, "host_has_slot": has, "selection": (slot if has else "") if selection is None else selection,
            "selection_on_model": on_model, "memory_point": memory, "bone_index": bone, "bone_object": ""}


def per_slot(slot, light, fits=True, can_add=True, attach_ok=True, found=None, beam=None):
    """``beam`` is (beam_start, beam_end) as the hook reads MemoryPointExists after the attach; None writes neither key."""
    result = {"slot": slot, "light_fits": fits, "can_add": can_add, "attach_ok": attach_ok,
              "found_type": (light if attach_ok else "") if found is None else found, "proxy_after_attach": ""}
    if beam is not None:
        result.update(beam_start=beam[0], beam_end=beam[1])
    return result


def light_obs(light, slots, spawned=True):
    return {"light": light, "spawned": spawned, "can_add_any": any(s["can_add"] for s in slots), "per_slot": slots}


def prereq_obs(has=None, rail=False, attached=""):
    """Observed native prerequisite slots (UniversalLight.c:123-132); ``has`` names the one the host owns."""
    return [{"slot": s, "host_has_slot": s == has, "attached_type": attached if s == has else "",
             "rail_functional": bool(rail and s == has)} for s in PREREQ_SLOTS]


def variant_obs(slot, lights, guard="AK_RailHndgrd", guard_attached=True, found=None, occupied=None, rail=None):
    """Prerequisite variant observation. ``found``/``occupied``/``rail`` are what the hook read back from the slot."""
    return {"performed": True, "slot": slot, "handguard": guard, "handguard_attached": guard_attached,
            "handguard_found_type": (guard if guard_attached else "") if found is None else found,
            "handguard_slot_occupied": guard_attached if occupied is None else occupied,
            "handguard_rail_functional": guard_attached if rail is None else rail, "lights": lights}


LIGHT_PROXY_PATH = "/dz/weapons/attachments/light/weaponlight_universal"


def res_entry(name="1.000", selection="", list_ok=True, vertex_ok=None, vertex=("0.5", "0.25", "-1.5")):
    """One per-resolution-LOD entry of a proxy row: the LOD, whether its selection list call succeeded, the first
    selection whose whole normalised path equals the row's model path, and that selection's first vertex as text."""
    vertex_ok = bool(selection) if vertex_ok is None else vertex_ok
    return {"name": name, "list_ok": list_ok, "selection": selection, "vertex_ok": vertex_ok,
            "vertex": list(vertex) if vertex_ok else []}


def proxy(path=LIGHT_PROXY_PATH, number="001", slots=("weaponFlashlight",), exists=True, model=None, cfg_class=None,
          slot_count=None, slot_complete=None, res_selection=None, vertex_ok=None, vertex=("0.5", "0.25", "-1.5"),
          res=None):
    """One proxy row: the host model's proxy selection joined to its CfgNonAIVehicles entry.

    The probe lists ``proxy:/dz/.../weaponlight_universal.001`` style selections; the config entry is
    ``Proxy<basename>`` and carries the proxy ``model`` path (backslashes, leading slash, .p3d) and the slot list.
    ``slot_count``/``slot_complete`` are the hook's inventorySlot bookkeeping (the listed rows are capped at 8).
    ``res`` is the row's per-resolution-LOD list (one entry per numeric-named LOD of the host, see HOST_RES); by default
    the single LOD "1.000" holds the proxy selection of the ``.001`` instance, whose first vertex is ``vertex``. The lookup
    is one result per model, so it does not depend on the instance number of the row. ``res_selection`` replaces that
    selection ("" for none)."""
    base = path.rsplit("/", 1)[-1]
    default_model = "\\" + path.strip("/").replace("/", "\\") + ".p3d"
    listed = list(slots) if exists else []
    selection = "proxy:" + path + "." + number
    if res is None:
        found = ("proxy:" + path + ".001").lower() if res_selection is None else res_selection
        res = [res_entry("1.000", found, vertex_ok=vertex_ok, vertex=vertex)]
    return {"selection": selection, "cfg_class": "Proxy" + base if cfg_class is None else cfg_class,
            "cfg_exists": exists, "model": ("" if not exists else default_model) if model is None else model,
            "inventory_slots": listed, "slot_count": len(listed) if slot_count is None else slot_count,
            "slot_scan_complete": (slot_count is None or slot_count == len(listed)) if slot_complete is None else slot_complete,
            "res_lods": res}


def res_host(*lods, enum_ok=True, count=None, complete=None, empty=False):
    """The host-level resolution-LOD facts. ``lods`` are (name, selection_count) pairs or full dicts; the defaults are the
    one LOD "1.000" holding three selections, and ``empty`` is a host whose LOD list holds no numeric-named LOD."""
    entries = [dict(name=item[0], list_ok=True, selection_count=item[1], scan_complete=True) if isinstance(item, tuple) else item
               for item in ([] if empty else (lods or (("1.000", 3),)))]
    count = len(entries) if count is None else count
    if complete is None:
        complete = enum_ok and len(entries) == count and all(item["scan_complete"] for item in entries)
    return {"res_enum_ok": enum_ok, "res_lod_count": count, "res_lods_scanned": len(entries), "res_scan_complete": complete,
            "res_lods": entries}


LOD_FACTS = {"lod_list_ok": True, "lod_count": 2, "lod_names": ["1.000", "geometry"], "lod_names_complete": True,
             "view_by_name": False}
HOST_FACTS = dict(res_host(), **LOD_FACTS)       # what the hook writes per host next to the proxy rows


def row(name, group, slots, lights, spawned=True, timed_out=False, root="CfgWeapons", index=0, prereq=None,
        prereq_variant=None, proxies=None, proxy_count=None, facts=None):
    if not spawned:
        return {"i": index, "class": name, "root": root, "group": group, "spawned": False, "timed_out": False}
    result = {"i": index, "class": name, "root": root, "group": group, "spawned": True, "type": name,
              "own_slots": [], "attach_slots": [], "selection_count": 3, "selection_matches": [],
              "slots": slots, "prereq": prereq_obs() if prereq is None else prereq,
              "lights": lights, "timed_out": timed_out, "ms": 3,
              "prereq_variant": {"performed": False} if prereq_variant is None else prereq_variant}
    if proxies is not None:       # absent on probe-003 (taken before the hook emitted proxies)
        result["proxy_count"] = len(proxies) if proxy_count is None else proxy_count
        result["proxy_scan_complete"] = True
        result["proxies"] = proxies
        result.update(copy.deepcopy(HOST_FACTS) if facts is None else facts)
    return result


def no_slots():
    return [slot_obs(s) for s in SLOTS]


def gun_slots(weapon_model=True):
    return [slot_obs("helmetFlashlight"), slot_obs("pistolFlashlight"),
            slot_obs("weaponFlashlight", has=True, on_model=weapon_model)]


def refusal_lights():
    return [light_obs(name, [per_slot(s, name, fits=s in FITS[name], can_add=False, attach_ok=False) for s in SLOTS])
            for name in LIGHTS]


def good_gun_lights():
    result = []
    for name in LIGHTS:
        slots = []
        for slot in SLOTS:
            fits = slot in FITS[name]
            ok = name == "UniversalLight" and slot == "weaponFlashlight"
            slots.append(per_slot(slot, name, fits=fits, can_add=ok, attach_ok=ok))
        result.append(light_obs(name, slots))
    return result


def preflight(spawned=True):
    return [{"light": name, "spawned": spawned, "type": name,
             "fits_native_slots": [{"slot": s, "fits": s in FITS[name]} for s in SLOTS]} for name in LIGHTS]


def observations(rows, status="complete", counters=None, light_rows=None):
    base = {"spawned": 10, "deleted": 10, "timeouts": 0, "attach_ok": 1, "live_after_release": 0,
            "residual_probe_types": 0, "residual_other": 0, "census_total": 2, "census_scanned": 2,
            "census_truncated": False, "census_complete": True}
    base.update(counters or {})
    return {"schema": 1, "kind": probe.OBSERVATIONS_KIND, "status": status, "world": "chernarusplus",
            "version": "1.30", "begin_ms": 1, "end_ms": 9, "hard_cap": 600, "per_class_ms": 2000,
            "classes": len(rows), "observed": len(rows), "position": [1.0, 2.0, 3.0], "counters": base,
            "slots": slot_rows(), "lights": preflight() if light_rows is None else light_rows, "hosts": rows}


def slot_rows():
    """Top-level native slot lookups (HCTLObserveSlots): every classified slot must be valid."""
    return [{"slot": s, "id": 100 + i, "valid": True, "selection": s, "selection_known": True, "bone": "",
             "bone_known": False} for i, s in enumerate(SLOTS)]


def verdicts(result):
    return {h["class"]: h["verdict"] for h in result["hosts"]}


def by_class(result, name):
    return next(h for h in result["hosts"] if h["class"] == name)


class JoinTests(unittest.TestCase):
    def setUp(self):
        self.cls = classification([
            host("AK74", "slot_host"), host("Bat", "no_slot_host"), host("Ruined", "excluded", ["scope_below_2"])])

    def test_native_attach_with_model_selection_is_qualified_per_light_and_slot(self):
        result = report.build_report(self.cls, observations([
            row("AK74", "slot_host", gun_slots(), good_gun_lights()),
            row("Bat", "no_slot_host", no_slots(), refusal_lights(), index=1)]))
        ak = by_class(result, "AK74")
        self.assertEqual("server_qualified", ak["verdict"])
        self.assertEqual("server_qualified", ak["lights"]["UniversalLight"]["verdict"])
        self.assertEqual("server_qualified", ak["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]["verdict"])
        self.assertEqual("geometry_missing", ak["lights"]["TLRLight"]["verdict"])
        self.assertIn("no_compatible_native_slot", ak["lights"]["TLRLight"]["reasons"])
        self.assertEqual("PENDING", result["acceptance"])

    def test_host_without_any_native_slot_is_not_server_evidencable_not_invented(self):
        result = report.build_report(self.cls, observations([
            row("AK74", "slot_host", gun_slots(), good_gun_lights()),
            row("Bat", "no_slot_host", no_slots(), refusal_lights(), index=1)]))
        bat = by_class(result, "Bat")
        self.assertEqual("not_server_evidencable", bat["verdict"])
        self.assertIn("no_native_light_slot", bat["reasons"])

    def test_excluded_hosts_keep_their_reasons_and_never_become_pending(self):
        result = report.build_report(self.cls, observations([]))
        ruined = by_class(result, "Ruined")
        self.assertEqual("excluded", ruined["verdict"])
        self.assertEqual(["scope_below_2"], ruined["exclusion_reasons"])

    def test_missing_probe_rows_are_pending_never_qualified(self):
        result = report.build_report(self.cls, observations([]))
        self.assertEqual({"AK74": "pending", "Bat": "pending", "Ruined": "excluded"}, verdicts(result))
        self.assertIn("no_probe_row", by_class(result, "AK74")["reasons"])
        self.assertEqual(0, result["denominators"]["server_qualified"])

    def test_duplicate_rows_for_one_class_are_ambiguous_pending(self):
        rows = [row("AK74", "slot_host", gun_slots(), good_gun_lights()),
                row("AK74", "slot_host", gun_slots(), good_gun_lights(), index=1)]
        result = report.build_report(self.cls, observations(rows))
        self.assertEqual("pending", by_class(result, "AK74")["verdict"])
        self.assertIn("ambiguous_probe_row", by_class(result, "AK74")["reasons"])

    def test_row_identity_mismatch_is_ambiguous_pending(self):
        wrong = row("AK74", "slot_host", gun_slots(), good_gun_lights(), root="CfgVehicles")
        result = report.build_report(self.cls, observations([wrong]))
        self.assertIn("ambiguous_probe_row", by_class(result, "AK74")["reasons"])
        self.assertEqual("pending", by_class(result, "AK74")["verdict"])

    def test_unexpected_rows_are_listed_not_joined(self):
        extra = row("Stranger", "no_slot_host", no_slots(), refusal_lights(), index=5)
        result = report.build_report(self.cls, observations([extra]))
        self.assertEqual(["Stranger"], result["integrity"]["unexpected_rows"])
        self.assertNotIn("Stranger", verdicts(result))

    def test_timed_out_and_unspawned_rows_are_pending(self):
        rows = [row("AK74", "slot_host", gun_slots(), good_gun_lights(), timed_out=True),
                row("Bat", "no_slot_host", [], [], spawned=False, index=1)]
        result = report.build_report(self.cls, observations(rows))
        self.assertIn("class_timed_out", by_class(result, "AK74")["reasons"])
        self.assertEqual("pending", by_class(result, "AK74")["verdict"])
        self.assertIn("host_not_spawned", by_class(result, "Bat")["reasons"])

    def test_attach_without_model_selection_evidence_is_pending_for_the_client(self):
        # complete proxy evidence (one unrelated, fully configured proxy) that names no flashlight slot
        unrelated = proxy("/dz/weapons/attachments/magazine/mag_stanag", slots=("magazine",))
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights(), proxies=[unrelated])]
        result = report.build_report(self.cls, observations(rows))
        slot = by_class(result, "AK74")["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual("pending", slot["verdict"])
        self.assertEqual("pending_client", slot["reason"])
        self.assertEqual("pending", by_class(result, "AK74")["verdict"])

    def test_bone_or_memory_point_counts_as_geometry_evidence(self):
        for kwargs in ({"memory": True}, {"bone": 4}):
            slots = [slot_obs("helmetFlashlight"), slot_obs("pistolFlashlight"),
                     slot_obs("weaponFlashlight", has=True, **kwargs)]
            rows = [row("AK74", "slot_host", slots, good_gun_lights())]
            result = report.build_report(self.cls, observations(rows))
            self.assertEqual("server_qualified", by_class(result, "AK74")["verdict"], kwargs)

    def test_native_refusal_and_failed_create_are_distinct(self):
        for can_add, verdict, reason in ((False, "geometry_missing", "native_attach_refused"),
                                          (True, "pending", "attach_create_failed")):
            lights = good_gun_lights()
            lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=can_add, attach_ok=False)
            rows = [row("AK74", "slot_host", gun_slots(), lights)]
            result = report.build_report(self.cls, observations(rows))
            slot = by_class(result, "AK74")["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
            self.assertEqual((verdict, reason), (slot["verdict"], slot["reason"]))

    def test_found_type_must_match_the_attached_light(self):
        lights = good_gun_lights()
        lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", found="Other")
        result = report.build_report(self.cls, observations([row("AK74", "slot_host", gun_slots(), lights)]))
        slot = by_class(result, "AK74")["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("pending", "attached_item_not_found_in_slot"), (slot["verdict"], slot["reason"]))

    def test_config_and_probe_disagreement_is_pending(self):
        slot_host_without_slot = row("AK74", "slot_host", no_slots(), refusal_lights())
        no_slot_host_with_slot = row("Bat", "no_slot_host", gun_slots(), good_gun_lights(), index=1)
        result = report.build_report(self.cls, observations([slot_host_without_slot, no_slot_host_with_slot]))
        for name in ("AK74", "Bat"):
            self.assertEqual("pending", by_class(result, name)["verdict"], name)
            self.assertIn("config_probe_conflict", by_class(result, name)["reasons"])

    def test_unspawned_light_preflight_makes_light_pairs_pending(self):
        rows = [row("AK74", "slot_host", gun_slots(), good_gun_lights())]
        result = report.build_report(self.cls, observations(rows, light_rows=preflight(spawned=False)))
        self.assertEqual("pending", by_class(result, "AK74")["lights"]["UniversalLight"]["verdict"])
        self.assertIn("light_not_spawned", by_class(result, "AK74")["lights"]["UniversalLight"]["reasons"])
        self.assertEqual("pending", by_class(result, "AK74")["verdict"])

    def test_control_light_attaching_anywhere_is_flagged_not_qualified(self):
        lights = good_gun_lights()
        lights[0]["per_slot"][2] = per_slot("weaponFlashlight", "Flashlight", fits=False, can_add=True, attach_ok=True)
        result = report.build_report(self.cls, observations([row("AK74", "slot_host", gun_slots(), lights)]))
        self.assertEqual(["AK74"], result["control"]["unexpected_attachments"])
        self.assertTrue(any("control" in issue for issue in result["integrity"]["issues"]))
        self.assertNotIn("Flashlight", by_class(result, "AK74")["lights"])

    def test_partial_status_and_dirty_cleanup_are_reported(self):
        dirty = {"deleted": 7, "live_after_release": 2, "residual_probe_types": 1}
        result = report.build_report(self.cls, observations([], status="partial", counters=dirty))
        issues = " ".join(result["integrity"]["issues"])
        self.assertIn("probe_status_partial", issues)
        self.assertFalse(result["integrity"]["cleanup_clean"])
        self.assertIn("spawned_not_equal_deleted", issues)
        self.assertIn("residual", issues)

    def test_denominators_partition_every_host(self):
        rows = [row("AK74", "slot_host", gun_slots(), good_gun_lights())]
        result = report.build_report(self.cls, observations(rows))
        counts = result["denominators"]
        self.assertEqual(counts["hosts"], counts["server_qualified"] + counts["geometry_missing"] + counts["excluded"]
                         + counts["pending"])
        self.assertEqual({"server_qualified": 1, "geometry_missing": 0, "excluded": 1, "pending": 1, "hosts": 3}, {
            k: counts[k] for k in ("server_qualified", "geometry_missing", "excluded", "pending", "hosts")})

    def test_unobserved_axes_are_always_pending(self):
        result = report.build_report(self.cls, observations([]))
        self.assertEqual("PENDING", result["acceptance"])
        for axis in ("beam", "switch", "two_client_presentation", "persistence"):
            self.assertEqual("pending", result["unobserved_axes"][axis])

    def test_invalid_inputs_are_refused(self):
        good = observations([])
        for bad_cls in (None, [], {"kind": "x"}):
            with self.assertRaises(ValueError):
                report.build_report(bad_cls, good)
        for bad_obs in (None, [], dict(good, kind="other"), dict(good, schema=2), dict(good, hosts="x"),
                        dict(good, status="running")):
            with self.assertRaises(ValueError):
                report.build_report(self.cls, bad_obs)

    def test_output_is_deterministic_and_ascii_json(self):
        rows = [row("AK74", "slot_host", gun_slots(), good_gun_lights())]
        first = json.dumps(report.build_report(self.cls, observations(rows)), sort_keys=True)
        second = json.dumps(report.build_report(self.cls, observations(list(rows))), sort_keys=True)
        self.assertEqual(first, second)
        self.assertTrue(first.isascii())


def baseline():
    """One slot host (AK74) whose UniversalLight attach is fully, consistently observed."""
    cls = classification([host("AK74", "slot_host")])
    obs = observations([row("AK74", "slot_host", gun_slots(), good_gun_lights())])
    return cls, obs


def host_result(alter):
    cls, obs = baseline()
    alter(cls, obs)
    result = report.build_report(cls, obs)
    return result, result["hosts"][0]


class EvidenceCompletenessTests(unittest.TestCase):
    """Sol P1-3: complete typed evidence for every expected light and slot, else pending."""

    def assert_pending(self, label, alter):
        _result, record = host_result(alter)
        self.assertEqual("pending", record["verdict"], label)

    def test_baseline_is_qualified(self):
        _result, record = host_result(lambda c, o: None)
        self.assertEqual("server_qualified", record["verdict"])

    def test_missing_rows_slots_fields_and_types_are_pending_never_geometry_missing(self):
        def row_of(o):
            return o["hosts"][0]
        cases = {
            "missing TLRLight row": lambda c, o: row_of(o)["lights"].pop(1),
            "missing control row": lambda c, o: row_of(o)["lights"].pop(0),
            "missing helmet slot observation": lambda c, o: row_of(o)["slots"].pop(0),
            "missing can_add": lambda c, o: row_of(o)["lights"][2]["per_slot"][2].pop("can_add"),
            "string can_add": lambda c, o: row_of(o)["lights"][2]["per_slot"][2].update(can_add="true"),
            "missing attach_ok": lambda c, o: row_of(o)["lights"][2]["per_slot"][2].pop("attach_ok"),
            "missing found_type": lambda c, o: row_of(o)["lights"][2]["per_slot"][2].pop("found_type"),
            "missing light_fits": lambda c, o: row_of(o)["lights"][2]["per_slot"][2].pop("light_fits"),
            "missing host_has_slot": lambda c, o: row_of(o)["slots"][2].pop("host_has_slot"),
            "integer host_has_slot": lambda c, o: row_of(o)["slots"][2].update(host_has_slot=1),
            "string bone_index": lambda c, o: row_of(o)["slots"][2].update(bone_index="4"),
            "boolean bone_index": lambda c, o: row_of(o)["slots"][2].update(bone_index=True),
            "missing selection_on_model": lambda c, o: row_of(o)["slots"][2].pop("selection_on_model"),
            "missing per-slot entry": lambda c, o: row_of(o)["lights"][2]["per_slot"].pop(2),
            "light spawned missing": lambda c, o: row_of(o)["lights"][2].pop("spawned"),
            "host spawned missing": lambda c, o: row_of(o).pop("spawned"),
            "timed_out missing": lambda c, o: row_of(o).pop("timed_out"),
            "null host slots": lambda c, o: row_of(o).update(slots=None),
            "null host lights": lambda c, o: row_of(o).update(lights=None),
            "null light per_slot": lambda c, o: row_of(o)["lights"][2].update(per_slot=None),
            "non-object slot entry": lambda c, o: row_of(o)["slots"].append("weaponFlashlight"),
        }
        for label, alter in cases.items():
            with self.subTest(label):
                self.assert_pending(label, alter)

    def test_empty_observations_never_mean_no_slots(self):
        def alter(c, o):
            c["hosts"][0].update(group="no_slot_host", native_light_slots=[])
            o["hosts"][0].update(group="no_slot_host", slots=[], lights=[])
        _result, record = host_result(alter)
        self.assertEqual("pending", record["verdict"])
        self.assertNotIn("no_native_light_slot", record["reasons"])

    def test_pending_takes_precedence_over_qualified(self):
        def alter(c, o):
            o["hosts"][0]["lights"].pop(1)          # TLRLight not observed; UniversalLight stays qualified
        _result, record = host_result(alter)
        self.assertEqual("server_qualified", record["lights"]["UniversalLight"]["verdict"])
        self.assertEqual("pending", record["verdict"])

    def test_pending_light_beats_geometry_missing_on_a_no_slot_host(self):
        cls = classification([host("Bat", "no_slot_host")])
        lights = refusal_lights()
        lights[1]["spawned"] = False
        obs = observations([row("Bat", "no_slot_host", no_slots(), lights)])
        self.assertEqual("pending", report.build_report(cls, obs)["hosts"][0]["verdict"])

    def test_malformed_host_evidence_does_not_abort_the_report(self):
        cls = classification([host("AK74", "slot_host"), host("Bat", "no_slot_host")])
        broken = row("AK74", "slot_host", None, "oops")
        obs = observations([broken, row("Bat", "no_slot_host", no_slots(), refusal_lights(), index=1)])
        result = report.build_report(cls, obs)
        self.assertEqual({"AK74": "pending", "Bat": "not_server_evidencable"}, verdicts(result))


class AmbiguityTests(unittest.TestCase):
    """Sol P1-4: duplicates and conflicts are pending; every raw control row is scanned."""

    def test_duplicate_or_conflicting_keys_are_pending(self):
        def row_of(o):
            return o["hosts"][0]
        cases = {
            "duplicate host slot": lambda c, o: row_of(o)["slots"].insert(0, slot_obs("weaponFlashlight")),
            "duplicate light": lambda c, o: row_of(o)["lights"].insert(0, light_obs("UniversalLight", [], False)),
            "duplicate per-slot": lambda c, o: row_of(o)["lights"][2]["per_slot"].insert(
                0, per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False)),
            "identical duplicate per-slot": lambda c, o: row_of(o)["lights"][2]["per_slot"].append(
                dict(row_of(o)["lights"][2]["per_slot"][2])),
            "two preflight rows": lambda c, o: o["lights"].append(dict(o["lights"][2])),
            "three preflight rows": lambda c, o: o["lights"].extend([dict(o["lights"][2]), dict(o["lights"][2])]),
        }
        for label, alter in cases.items():
            with self.subTest(label):
                _result, record = host_result(alter)
                self.assertEqual("pending", record["verdict"], label)

    def test_control_attachment_is_found_in_every_raw_row_even_when_a_later_row_is_negative(self):
        cls = classification([host("AK74", "slot_host"), host("M4A1", "slot_host")])
        first = row("AK74", "slot_host", gun_slots(), good_gun_lights())
        first["lights"][0]["per_slot"][2]["attach_ok"] = True
        second = row("M4A1", "slot_host", gun_slots(), good_gun_lights(), index=1)
        result = report.build_report(cls, observations([first, second]))
        self.assertEqual(["AK74"], result["control"]["unexpected_attachments"])

    def test_control_attachment_hidden_behind_a_duplicate_light_entry_is_still_flagged(self):
        def alter(c, o):
            o["hosts"][0]["lights"][0]["per_slot"][2]["attach_ok"] = True
            o["hosts"][0]["lights"].append(light_obs("Flashlight", [
                per_slot(s, "Flashlight", fits=False, can_add=False, attach_ok=False) for s in SLOTS]))
        result, record = host_result(alter)
        self.assertEqual(["AK74"], result["control"]["unexpected_attachments"])
        self.assertEqual("pending", record["verdict"])

    def test_control_attachment_on_an_unexpected_or_duplicate_row_is_flagged(self):
        cls = classification([host("AK74", "slot_host")])
        good = row("AK74", "slot_host", gun_slots(), good_gun_lights())
        stranger = row("Stranger", "no_slot_host", no_slots(), refusal_lights(), index=1)
        stranger["lights"][0]["per_slot"][0]["attach_ok"] = True
        twin = row("AK74", "slot_host", gun_slots(), good_gun_lights(), index=2)
        twin["lights"][0]["per_slot"][1]["attach_ok"] = True
        result = report.build_report(cls, observations([good, stranger, twin]))
        self.assertEqual(["AK74", "Stranger"], result["control"]["unexpected_attachments"])

    def test_control_hit_also_demotes_geometry_missing_hosts(self):
        cls = classification([host("Bat", "no_slot_host"), host("AK74", "slot_host")])
        bat = row("Bat", "no_slot_host", no_slots(), refusal_lights())
        ak = row("AK74", "slot_host", gun_slots(), good_gun_lights(), index=1)
        ak["lights"][0]["per_slot"][2]["attach_ok"] = True
        result = report.build_report(cls, observations([bat, ak]))
        self.assertEqual({"AK74": "pending", "Bat": "pending"}, verdicts(result))


class IdentityTests(unittest.TestCase):
    """Sol P1-5: spawned types, preflight types, preflight/host agreement and the slot set must match."""

    def test_identity_mismatches_are_pending(self):
        cases = {
            "wrong spawned host type": lambda c, o: o["hosts"][0].update(type="OtherHost"),
            "missing spawned host type": lambda c, o: o["hosts"][0].pop("type"),
            "wrong preflight type": lambda c, o: o["lights"][2].update(type="OtherLight"),
            "preflight fits nothing": lambda c, o: o["lights"][2].update(
                fits_native_slots=[{"slot": s, "fits": False} for s in SLOTS]),
            "preflight slot set short": lambda c, o: o["lights"][2].update(fits_native_slots=[]),
            "preflight fits disagree with host": lambda c, o: o["lights"][2]["fits_native_slots"][1].update(fits=True),
            "host light_fits disagree with preflight": lambda c, o: o["hosts"][0]["lights"][2]["per_slot"][2].update(
                light_fits=False),
            "config slot differs from observed": lambda c, o: c["hosts"][0].update(native_light_slots=["pistolFlashlight"]),
            "config lists an extra slot": lambda c, o: c["hosts"][0].update(
                native_light_slots=["weaponFlashlight", "helmetFlashlight"]),
            "config light slots differ from preflight": lambda c, o: c["lights"][0].update(native_slots=["pistolFlashlight"]),
            "top-level slot row missing": lambda c, o: o["slots"].pop(),
            "top-level slot invalid": lambda c, o: o["slots"][2].update(valid=False),
            "top-level slot extra": lambda c, o: o["slots"].append(dict(o["slots"][0], slot="extraSlot")),
            "host reports an extra slot": lambda c, o: o["hosts"][0]["slots"].append(slot_obs("extraSlot")),
            "host reports a renamed slot": lambda c, o: o["hosts"][0]["slots"][0].update(slot="otherSlot"),
        }
        for label, alter in cases.items():
            with self.subTest(label):
                _result, record = host_result(alter)
                self.assertEqual("pending", record["verdict"], label)


class PrerequisiteTests(unittest.TestCase):
    """Sol P1-6: UniversalLight.CanPutAsAttachment (4_World/Entities/ItemBase/Switchable_Base/UniversalLight.c:25-45)
    refuses when the parent owns a handguard slot (:123-132) without a rail-capable attachment in it."""

    def test_prerequisite_slots_match_the_native_slot_list_and_the_probe(self):
        self.assertEqual(PREREQ_SLOTS, sorted(report.PREREQUISITE_SLOTS))
        self.assertEqual(PREREQ_SLOTS, sorted(slot for slot, _item in probe.PREREQUISITE_HANDGUARDS))

    def refused(self, prereq, variant=None, light="UniversalLight"):
        lights = good_gun_lights()
        lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False)
        cls = classification([host("AK74", "slot_host")])
        result = report.build_report(cls, observations([row(
            "AK74", "slot_host", gun_slots(), lights, prereq=prereq, prereq_variant=variant)]))
        return result["hosts"][0]["lights"][light]["slots"]["weaponFlashlight"], result["hosts"][0]

    def test_refusal_with_an_unmet_prerequisite_is_pending_not_geometry_missing(self):
        slot, record = self.refused(prereq_obs(has="weaponHandguardAK"))
        self.assertEqual(("pending", "refusal_may_depend_on_prerequisite"), (slot["verdict"], slot["reason"]))
        self.assertEqual("pending", record["verdict"])

    def test_refusal_without_prerequisite_evidence_is_pending(self):
        slot, _record = self.refused([])
        self.assertEqual(("pending", "prerequisite_evidence_missing"), (slot["verdict"], slot["reason"]))
        slot, _record = self.refused(prereq_obs()[:2])
        self.assertEqual("pending", slot["verdict"])

    def test_refusal_on_a_host_without_prerequisite_slots_is_a_native_refusal(self):
        slot, record = self.refused(prereq_obs())
        self.assertEqual(("geometry_missing", "native_attach_refused"), (slot["verdict"], slot["reason"]))
        self.assertEqual("geometry_missing", record["verdict"])

    def test_refusal_with_the_prerequisite_satisfied_is_a_native_refusal(self):
        slot, _record = self.refused(prereq_obs(has="weaponHandguardAK", rail=True, attached="AK_RailHndgrd"))
        self.assertEqual(("geometry_missing", "native_attach_refused"), (slot["verdict"], slot["reason"]))

    def variant_lights(self, can_add=True, attach_ok=True, found=None):
        lights = good_gun_lights()
        lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=can_add,
                                            attach_ok=attach_ok, found=found)
        return lights

    def test_variant_accepting_the_light_with_a_rail_handguard_qualifies_with_its_own_reason(self):
        variant = variant_obs("weaponHandguardAK", self.variant_lights())
        slot, record = self.refused(prereq_obs(has="weaponHandguardAK"), variant)
        self.assertEqual(("server_qualified", "native_attach_with_rail_handguard_prerequisite"),
                         (slot["verdict"], slot["reason"]))
        self.assertTrue(slot["evidence"]["requires_prerequisite"])
        self.assertEqual("server_qualified", record["verdict"])

    def test_variant_that_still_refuses_is_geometry_missing(self):
        variant = variant_obs("weaponHandguardAK", self.variant_lights(can_add=False, attach_ok=False))
        slot, _record = self.refused(prereq_obs(has="weaponHandguardAK"), variant)
        self.assertEqual(("geometry_missing", "native_attach_refused_with_prerequisite"),
                         (slot["verdict"], slot["reason"]))

    def test_variant_failures_stay_pending(self):
        prereq = prereq_obs(has="weaponHandguardAK")
        cases = {
            "handguard not attached": variant_obs("weaponHandguardAK", [], guard_attached=False),
            "variant light rows missing": variant_obs("weaponHandguardAK", []),
            "create failed": variant_obs("weaponHandguardAK", self.variant_lights(attach_ok=False)),
            "wrong found type": variant_obs("weaponHandguardAK", self.variant_lights(found="Other")),
            "wrong slot named": variant_obs("weaponHandguardM4", self.variant_lights()),
            "performed not boolean": dict(variant_obs("weaponHandguardAK", self.variant_lights()), performed="yes"),
        }
        for label, variant in cases.items():
            with self.subTest(label):
                slot, _record = self.refused(prereq, variant)
                self.assertEqual("pending", slot["verdict"], label)

    def test_lights_without_a_native_prerequisite_rule_keep_the_plain_refusal(self):
        lights = good_gun_lights()
        lights[1]["per_slot"][1] = per_slot("pistolFlashlight", "TLRLight", can_add=False, attach_ok=False)
        cls = classification([host("Pistol", "slot_host")])
        cls["hosts"][0]["native_light_slots"] = ["pistolFlashlight"]
        slots = [slot_obs("helmetFlashlight"), slot_obs("pistolFlashlight", has=True, on_model=True),
                 slot_obs("weaponFlashlight")]
        for entry in lights:
            for item in entry["per_slot"]:
                item.update(can_add=False, attach_ok=False, found_type="")
        result = report.build_report(cls, observations([row("Pistol", "slot_host", slots, lights)]))
        self.assertEqual("geometry_missing", result["hosts"][0]["verdict"])


class IntegrityGateTests(unittest.TestCase):
    """Qualification needs a trustworthy probe; the residual census must say whether it was complete."""

    def test_incomplete_or_missing_census_refuses_clean_certification_and_blocks_qualification(self):
        cases = {
            "truncated census": {"census_truncated": True, "census_complete": False, "census_total": 900,
                                  "census_scanned": 512},
            "complete flag false": {"census_complete": False},
            "scanned below total": {"census_total": 9, "census_scanned": 2},
            "census never ran": {"census_total": None},
        }
        for label, counters in cases.items():
            with self.subTest(label):
                cls, obs = baseline()
                for key, value in counters.items():
                    if value is None:
                        obs["counters"].pop(key)
                    else:
                        obs["counters"][key] = value
                result = report.build_report(cls, obs)
                self.assertFalse(result["integrity"]["cleanup_clean"], label)
                self.assertTrue(any("census" in issue for issue in result["integrity"]["issues"]), label)
                self.assertEqual("pending", result["hosts"][0]["verdict"], label)

    def test_counters_must_be_typed_integers(self):
        for key, value in (("spawned", "10"), ("deleted", None), ("live_after_release", False),
                           ("residual_probe_types", 0.0)):
            with self.subTest(key):
                cls, obs = baseline()
                if value is None:
                    obs["counters"].pop(key)
                else:
                    obs["counters"][key] = value
                result = report.build_report(cls, obs)
                self.assertFalse(result["integrity"]["cleanup_clean"], key)
                self.assertEqual("pending", result["hosts"][0]["verdict"], key)

    def test_partial_status_dirty_cleanup_and_control_attachment_demote_qualified(self):
        for label, alter in {
                "partial": lambda c, o: o.update(status="partial"),
                "dirty": lambda c, o: o["counters"].update(deleted=9, residual_probe_types=1),
                "live after release": lambda c, o: o["counters"].update(live_after_release=1),
                "control": lambda c, o: o["hosts"][0]["lights"][0]["per_slot"][2].update(
                    attach_ok=True, can_add=True, found_type="Flashlight")}.items():
            with self.subTest(label):
                result, record = host_result(alter)
                self.assertEqual("pending", record["verdict"], label)
                self.assertIn("probe_integrity_failed", record["reasons"], label)
                self.assertTrue(result["integrity"]["issues"], label)

    def test_observed_count_must_match_the_rows(self):
        cls, obs = baseline()
        obs["observed"] = 5
        result = report.build_report(cls, obs)
        self.assertIn("observed_count_mismatch", result["integrity"]["issues"])

    def test_clean_probe_keeps_qualified_and_reports_clean(self):
        result, record = host_result(lambda c, o: None)
        self.assertTrue(result["integrity"]["cleanup_clean"])
        self.assertEqual([], result["integrity"]["issues"])
        self.assertEqual("server_qualified", record["verdict"])


def pair_counts(result):
    return result["denominators"]["host_light_pairs"]


def nested_verdicts(record):
    """Every light and slot verdict of one host record."""
    found = [light["verdict"] for light in record["lights"].values()]
    found += [slot["verdict"] for light in record["lights"].values() for slot in light["slots"].values()]
    return found


class InvalidationPropagationTests(unittest.TestCase):
    """Sol re-review P1: probe-level and host-level invalidation reaches every nested verdict and the pair counts."""

    CASES = {
        "partial status": lambda c, o: o.update(status="partial"),
        "dirty cleanup": lambda c, o: o["counters"].update(deleted=9, residual_probe_types=1),
        "live after release": lambda c, o: o["counters"].update(live_after_release=1),
        "control attached": lambda c, o: o["hosts"][0]["lights"][0]["per_slot"][2].update(attach_ok=True, can_add=True, found_type="Flashlight"),
        "wrong host type": lambda c, o: o["hosts"][0].update(type="OtherHost"),
        "config slot mismatch": lambda c, o: c["hosts"][0].update(native_light_slots=["pistolFlashlight"]),
        "class timed out": lambda c, o: o["hosts"][0].update(timed_out=True),
        "census truncated": lambda c, o: o["counters"].update(census_truncated=True, census_complete=False),
    }

    def test_no_nested_verdict_or_pair_count_stays_qualified(self):
        for label, alter in self.CASES.items():
            with self.subTest(label):
                result, record = host_result(alter)
                self.assertEqual("pending", record["verdict"], label)
                self.assertNotIn("server_qualified", nested_verdicts(record), label)
                self.assertEqual(0, pair_counts(result).get("server_qualified", 0), label)

    def test_a_control_hit_also_takes_geometry_missing_out_of_the_nested_verdicts_and_pair_counts(self):
        cls = classification([host("AK74", "slot_host")])
        obs = observations([row("AK74", "slot_host", gun_slots(), good_gun_lights())])
        obs["hosts"][0]["lights"][0]["per_slot"][2].update(attach_ok=True, can_add=True, found_type="Flashlight")
        result = report.build_report(cls, obs)
        self.assertNotIn("geometry_missing", nested_verdicts(result["hosts"][0]))
        self.assertEqual(0, pair_counts(result).get("geometry_missing", 0))

    def test_a_missing_sibling_light_alone_does_not_invalidate_an_independently_valid_pair(self):
        result, record = host_result(lambda c, o: o["hosts"][0]["lights"].pop(1))
        self.assertEqual("pending", record["verdict"])
        self.assertEqual("server_qualified", record["lights"]["UniversalLight"]["verdict"])
        self.assertEqual("pending", record["lights"]["TLRLight"]["verdict"])
        self.assertEqual({"pending": 1, "server_qualified": 1}, pair_counts(result))

    def test_a_duplicated_sibling_light_row_alone_does_not_invalidate_the_independently_valid_pair(self):
        result, record = host_result(lambda c, o: o["hosts"][0]["lights"].append(dict(o["hosts"][0]["lights"][1])))
        self.assertEqual("pending", record["verdict"])
        self.assertIn("duplicate_light_observation", record["reasons"])
        self.assertEqual("pending", record["lights"]["TLRLight"]["verdict"])
        self.assertEqual("server_qualified", record["lights"]["UniversalLight"]["verdict"])

    def test_an_invalid_host_does_not_taint_a_different_valid_host(self):
        cls = classification([host("AK74", "slot_host"), host("M4A1", "slot_host")])
        bad = row("AK74", "slot_host", gun_slots(), good_gun_lights())
        bad["type"] = "OtherHost"
        good = row("M4A1", "slot_host", gun_slots(), good_gun_lights(), index=1)
        result = report.build_report(cls, observations([bad, good]))
        self.assertEqual({"AK74": "pending", "M4A1": "server_qualified"}, verdicts(result))
        self.assertEqual({"pending": 2, "server_qualified": 1, "geometry_missing": 1}, pair_counts(result))


class ControlEvidenceTests(unittest.TestCase):
    """Sol re-review P2: the control needs exactly one spawned typed preflight and full, consistent per-slot evidence."""

    CASES = {
        "missing control preflight": lambda c, o: o["lights"].pop(0),
        "duplicate control preflight": lambda c, o: o["lights"].append(dict(o["lights"][0])),
        "wrong-type control preflight": lambda c, o: o["lights"][0].update(type="OtherLight"),
        "control preflight not spawned": lambda c, o: o["lights"][0].update(spawned=False),
        "control preflight fit contradicts the classification": lambda c, o: o["lights"][0]["fits_native_slots"][1].update(
            fits=True),
        "control spawn failed on the host": lambda c, o: o["hosts"][0]["lights"][0].update(spawned=False),
        "control light_fits contradicts the preflight": lambda c, o: o["hosts"][0]["lights"][0]["per_slot"][1].update(
            light_fits=True),
        "control per-slot entry missing": lambda c, o: o["hosts"][0]["lights"][0]["per_slot"].pop(),
        "control can_add missing": lambda c, o: o["hosts"][0]["lights"][0]["per_slot"][0].pop("can_add"),
        "control found_type missing": lambda c, o: o["hosts"][0]["lights"][0]["per_slot"][0].pop("found_type"),
        "control row duplicated": lambda c, o: o["hosts"][0]["lights"].append(dict(o["hosts"][0]["lights"][0])),
        # Sol review 003 P2: the producer fills found_type only after a successful create and read-back.
        "control found_type set although the create failed": lambda c, o: o["hosts"][0]["lights"][0]["per_slot"][2].update(
            found_type="Flashlight"),
        "control create succeeded without a read-back type": lambda c, o: o["hosts"][0]["lights"][0]["per_slot"][2].update(
            attach_ok=True, can_add=True, found_type=""),
    }

    def test_every_control_defect_makes_the_host_and_its_pairs_pending(self):
        for label, alter in self.CASES.items():
            with self.subTest(label):
                result, record = host_result(alter)
                self.assertEqual("pending", record["verdict"], label)
                self.assertTrue(any(reason.startswith("control") for reason in record["reasons"]), (label, record["reasons"]))
                self.assertEqual(0, pair_counts(result).get("server_qualified", 0), label)

    def test_a_complete_spawned_consistent_control_keeps_the_host_qualified(self):
        _result, record = host_result(lambda c, o: None)
        self.assertEqual("server_qualified", record["verdict"])


def variant_report(variant, light_alter=None):
    """AK74 whose plain UniversalLight attach is refused (rail prerequisite unmet) with ``variant`` as evidence."""
    lights = good_gun_lights()
    lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False)
    result = report.build_report(classification([host("AK74", "slot_host")]), observations([row(
        "AK74", "slot_host", gun_slots(), lights, prereq=prereq_obs(has="weaponHandguardAK"), prereq_variant=variant)]))
    return result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"], result["hosts"][0], result


class VariantEvidenceTests(unittest.TestCase):
    """Sol re-review P2: variant attempts pass the same checks as base attempts and the handguard is proven."""

    def variant(self, **kwargs):
        lights = good_gun_lights()
        return variant_obs("weaponHandguardAK", [lights[2]], **kwargs)

    def test_the_handguard_map_matches_the_probe(self):
        self.assertEqual(dict(probe.PREREQUISITE_HANDGUARDS), dict(report.PREREQUISITE_HANDGUARDS))

    def test_a_correct_variant_still_qualifies(self):
        slot, record, _result = variant_report(self.variant())
        self.assertEqual(("server_qualified", "native_attach_with_rail_handguard_prerequisite"), (slot["verdict"], slot["reason"]))
        self.assertEqual("server_qualified", record["verdict"])

    def test_a_variant_light_fit_that_disagrees_with_the_preflight_is_pending(self):
        variant = self.variant()
        variant["lights"][0]["per_slot"][2]["light_fits"] = False
        slot, record, _result = variant_report(variant)
        self.assertEqual("pending", slot["verdict"])
        self.assertEqual("pending", record["verdict"])

    def test_a_variant_fit_disagreement_on_another_slot_is_pending_too(self):
        variant = self.variant()
        variant["lights"][0]["per_slot"][0]["light_fits"] = False
        slot, _record, _result = variant_report(variant)
        self.assertEqual("pending", slot["verdict"])

    def test_a_contradictory_variant_attempt_is_pending(self):
        variant = self.variant()
        variant["lights"][0]["per_slot"][2].update(can_add=False, attach_ok=True)
        slot, _record, _result = variant_report(variant)
        self.assertEqual("pending", slot["verdict"])

    def test_a_wrong_or_unproven_handguard_does_not_keep_the_rail_qualification(self):
        cases = {
            "plastic label and type": self.variant(guard="AK_PlasticHndgrd"),
            "label says rail but the slot holds plastic": self.variant(found="AK_PlasticHndgrd", rail=False),
            "label says rail, found type is plastic, rail flag still true": self.variant(found="AK_PlasticHndgrd"),
            "found type belongs to another slot": self.variant(found="M4_RISHndgrd"),
            "slot not occupied": self.variant(occupied=False),
            "found rail handguard but rail property false": self.variant(rail=False),
            "found type empty": self.variant(found=""),
        }
        for label, variant in cases.items():
            with self.subTest(label):
                slot, record, _result = variant_report(variant)
                self.assertEqual("pending", slot["verdict"], label)
                self.assertEqual("pending", record["verdict"], label)

    def test_variant_evidence_keys_must_be_present_and_typed(self):
        for key in ("handguard_found_type", "handguard_slot_occupied", "handguard_rail_functional"):
            for label, alter in (("missing", lambda v, k=key: v.pop(k)), ("mistyped", lambda v, k=key: v.update({k: 1}))):
                with self.subTest(key=key, how=label):
                    variant = self.variant()
                    alter(variant)
                    slot, _record, _result = variant_report(variant)
                    self.assertEqual("pending", slot["verdict"])


class RangeAndRelationTests(unittest.TestCase):
    """Sol re-review P2: contradictions and impossible counter values are pending, never a verdict."""

    def pending_without_qualified_pairs(self, label, alter):
        result, record = host_result(alter)
        self.assertEqual("pending", record["verdict"], label)
        self.assertEqual(0, pair_counts(result).get("server_qualified", 0), label)
        return result

    def test_can_add_false_with_attach_ok_true_is_pending(self):
        self.pending_without_qualified_pairs(
            "contradiction", lambda c, o: o["hosts"][0]["lights"][2]["per_slot"][2].update(can_add=False))

    def test_the_contradiction_is_not_read_as_a_native_refusal(self):
        _result, record = host_result(lambda c, o: o["hosts"][0]["lights"][2]["per_slot"][2].update(can_add=False))
        slot = record["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual("pending", slot["verdict"])
        self.assertEqual("pending", record["lights"]["UniversalLight"]["verdict"])

    def test_negative_or_out_of_range_counters_are_pending(self):
        cases = {
            "negative spawned and deleted": {"spawned": -1, "deleted": -1},
            "negative deleted with matching spawned": {"spawned": -3, "deleted": -3},
            "negative live_after_release": {"live_after_release": -1},
            "negative residual_probe_types": {"residual_probe_types": -1},
            "negative census total and scanned": {"census_total": -2, "census_scanned": -2},
            "negative scanned": {"census_scanned": -1},
            "scanned above total": {"census_total": 2, "census_scanned": 3},
            "scanned above the scan cap": {"census_total": probe.CENSUS_SCAN_LIMIT + 5,
                                            "census_scanned": probe.CENSUS_SCAN_LIMIT + 5},
            "zero total with scanned": {"census_total": 0, "census_scanned": 1},
        }
        for label, counters in cases.items():
            with self.subTest(label):
                result = self.pending_without_qualified_pairs(label, lambda c, o, k=counters: o["counters"].update(k))
                self.assertFalse(result["integrity"]["cleanup_clean"], label)

    def test_the_scan_cap_matches_the_probe(self):
        self.assertEqual(probe.CENSUS_SCAN_LIMIT, report.CENSUS_SCAN_LIMIT)

    def test_a_full_scan_at_the_cap_is_still_accepted(self):
        result, record = host_result(lambda c, o: o["counters"].update(
            census_total=probe.CENSUS_SCAN_LIMIT, census_scanned=probe.CENSUS_SCAN_LIMIT))
        self.assertEqual("server_qualified", record["verdict"])
        self.assertTrue(result["integrity"]["cleanup_clean"])


class ProbeContractTests(unittest.TestCase):
    def test_every_key_the_report_reads_is_emitted_by_the_generated_hook(self):
        targets = {"hosts": [{"class": "AK74", "root": "CfgWeapons", "group": "slot_host", "index": 0}],
                   "lights": LIGHTS, "slots": SLOTS, "excluded_not_probed": 0}
        hook = probe.render_hook(targets).decode()
        emitted = set(re.findall(r'HCTLKey\("([a-z_]+)"\)', hook))
        emitted |= set(re.findall(r'HCTLWriteRows\(handle, "([a-z_]+)"', hook))  # top-level row sections
        self.assertTrue(report.CONSUMED_KEYS)
        self.assertEqual(set(), set(report.CONSUMED_KEYS) - emitted)

    def test_report_kinds_match_the_probe(self):
        self.assertEqual(probe.OBSERVATIONS_KIND, report.OBSERVATIONS_KIND)
        self.assertEqual(probe.CLASSIFICATION_KIND, report.CLASSIFICATION_KIND)


class ReadbackContradictionTests(unittest.TestCase):
    """Sol review 003 P2: found_type is filled only after a successful create, so the two must agree everywhere."""

    def one(self, alter):
        lights = good_gun_lights()
        alter(lights)
        result = report.build_report(classification([host("AK74", "slot_host")]),
                                     observations([row("AK74", "slot_host", gun_slots(), lights)]))
        record = result["hosts"][0]
        return record["lights"]["UniversalLight"]["slots"].get("weaponFlashlight"), record, result

    def test_a_representative_found_item_without_a_successful_attach_is_pending_not_a_refusal(self):
        slot, record, _result = self.one(lambda lights: lights[2]["per_slot"].__setitem__(
            2, per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False, found="UniversalLight")))
        self.assertEqual(("pending", "slot_evidence_invalid"), (slot["verdict"], slot["reason"]))
        self.assertEqual("pending", record["verdict"])

    def test_a_successful_attach_without_a_read_back_type_is_pending(self):
        slot, record, _result = self.one(lambda lights: lights[2]["per_slot"].__setitem__(
            2, per_slot("weaponFlashlight", "UniversalLight", found="")))
        self.assertEqual(("pending", "slot_evidence_invalid"), (slot["verdict"], slot["reason"]))
        self.assertEqual("pending", record["verdict"])

    def test_a_contradictory_read_back_on_another_slot_still_invalidates_the_pair(self):
        slot, record, result = self.one(lambda lights: lights[2]["per_slot"][0].update(found_type="UniversalLight"))
        self.assertEqual("pending", record["lights"]["UniversalLight"]["verdict"])
        self.assertEqual(0, pair_counts(result).get("server_qualified", 0))

    def test_a_variant_found_item_without_a_successful_attach_is_pending_not_a_refusal(self):
        variant_lights = good_gun_lights()
        variant_lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False,
                                                    found="UniversalLight")
        slot, record, _result = variant_report(variant_obs("weaponHandguardAK", [variant_lights[2]]))
        self.assertEqual("pending", slot["verdict"])
        self.assertNotEqual("native_attach_refused_with_prerequisite", slot["reason"])
        self.assertEqual("pending", record["verdict"])

    def test_a_variant_successful_attach_without_a_read_back_type_is_pending(self):
        variant_lights = good_gun_lights()
        variant_lights[2]["per_slot"][2]["found_type"] = ""
        slot, record, _result = variant_report(variant_obs("weaponHandguardAK", [variant_lights[2]]))
        self.assertEqual("pending", slot["verdict"])
        self.assertEqual("pending", record["verdict"])

    def test_the_probe_003_shape_stays_consistent(self):
        """Every probe-003 attempt had found_type '' when attach_ok was false and the light type when true."""
        slot, record, _result = self.one(lambda lights: None)
        self.assertEqual("server_qualified", slot["verdict"])
        self.assertEqual("server_qualified", record["verdict"])


class ProxySlotEvidenceTests(unittest.TestCase):
    """Fix round 3: probe-003 showed GetSelectionForSlotId returns nothing natively, so the model evidence for a slot
    is a host proxy selection joined to its CfgNonAIVehicles Proxy<basename> entry (config exists, model path matches
    the proxy path, inventorySlot lists the slot). Fixtures are probe-003 shapes written out explicitly."""

    def attach(self, proxies, proxy_count=None, mutate=None, slots=None):
        lights = good_gun_lights()
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False) if slots is None else slots, lights,
                    proxies=proxies, proxy_count=proxy_count)]
        if mutate:
            mutate(rows[0])
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        record = result["hosts"][0]
        return record["lights"]["UniversalLight"]["slots"]["weaponFlashlight"], record, result

    def test_a_proxy_with_an_existing_config_matching_model_and_slot_qualifies(self):
        slot, record, result = self.attach([proxy()])
        self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot"), (slot["verdict"], slot["reason"]))
        self.assertEqual("proxy_config_slot", slot["evidence"]["model_evidence"])
        self.assertEqual("proxy:" + LIGHT_PROXY_PATH + ".001", slot["evidence"]["proxy_selection"])
        self.assertEqual("server_qualified", record["verdict"])
        self.assertEqual("PENDING", result["acceptance"])

    def test_probe_003_selection_and_model_spellings_are_normalised(self):
        for model in ("\\dz\\weapons\\attachments\\light\\weaponlight_universal.p3d",
                      "dz/weapons/attachments/light/weaponlight_universal.P3D",
                      "\\DZ\\Weapons\\Attachments\\Light\\WeaponLight_Universal.p3d",
                      "/dz/weapons/attachments/light/weaponlight_universal"):
            with self.subTest(model=model):
                slot, _record, _result = self.attach([proxy(model=model)])
                self.assertEqual("server_qualified", slot["verdict"])

    def test_the_proxy_prefix_is_matched_case_insensitively_like_the_hook_does(self):
        for prefix in ("Proxy:", "PROXY:", "pRoXy:"):
            with self.subTest(prefix=prefix):
                item = proxy()
                item["selection"] = prefix + item["selection"][len("proxy:"):]
                slot, _record, _result = self.attach([item])
                self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot"), (slot["verdict"], slot["reason"]))

    def test_a_selection_without_the_proxy_prefix_is_malformed_evidence_not_a_match(self):
        item = proxy()
        item["selection"] = "xproxy:" + item["selection"][len("proxy:"):]
        slot, _record, _result = self.attach([item])
        self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]))

    def test_a_qualifying_proxy_among_other_rows_and_a_truncated_list_still_qualifies(self):
        rows = [proxy("/dz/weapons/attachments/magazine/mag_stanag", slots=("magazine",)), proxy()]
        slot, _record, _result = self.attach(rows, proxy_count=40)
        self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot"), (slot["verdict"], slot["reason"]))

    def test_a_proxy_that_names_a_different_slot_does_not_qualify(self):
        slot, record, _result = self.attach([proxy(slots=("pistolFlashlight",))])
        self.assertEqual(("geometry_missing", "proxy_belongs_to_other_slot"), (slot["verdict"], slot["reason"]))
        self.assertNotEqual("server_qualified", record["verdict"])

    def test_the_slot_must_be_in_the_list_not_a_substring_of_it(self):
        slot, _record, _result = self.attach([proxy(slots=("weaponFlashlightExtra",))])
        self.assertNotEqual("server_qualified", slot["verdict"])

    def test_a_missing_config_entry_is_pending_never_inferred_from_the_proxy_name(self):
        slot, record, _result = self.attach([proxy(exists=False)])
        self.assertEqual(("pending", "proxy_config_missing"), (slot["verdict"], slot["reason"]))
        self.assertEqual("pending", record["verdict"])

    def test_a_row_that_says_the_config_is_absent_never_qualifies_even_with_a_model_and_slots_filled_in(self):
        item = dict(proxy(), cfg_exists=False)       # contradictory read-back: absent entry that still names data
        slot, record, _result = self.attach([item])
        self.assertEqual(("pending", "proxy_config_missing"), (slot["verdict"], slot["reason"]))
        self.assertEqual("pending", record["verdict"])

    def test_a_model_path_that_differs_from_the_proxy_path_does_not_qualify(self):
        slot, record, _result = self.attach([proxy(model="\\dz\\weapons\\attachments\\light\\weaponlight_tlr.p3d")])
        self.assertEqual(("pending", "pending_client"), (slot["verdict"], slot["reason"]))
        self.assertNotEqual("server_qualified", record["verdict"])

    def test_an_empty_model_with_an_existing_entry_does_not_qualify(self):
        slot, _record, _result = self.attach([proxy(model="x")])
        self.assertNotEqual("server_qualified", slot["verdict"])
        slot, _record, _result = self.attach([dict(proxy(), model="")])
        self.assertNotEqual("server_qualified", slot["verdict"])

    def test_malformed_proxy_evidence_is_pending(self):
        def entry(**changes):
            return lambda r: r["proxies"][0].update(changes)

        def drop(key):
            return lambda r: r["proxies"][0].pop(key)
        cases = {
            "proxies not a list": lambda r: r.update(proxies={"selection": "x"}),
            "proxy entry not an object": lambda r: r.update(proxies=["proxy:/a/b.001"]),
            "selection missing": drop("selection"),
            "selection not a string": entry(selection=7),
            "selection without the proxy prefix": entry(selection="/dz/weapons/attachments/light/weaponlight_universal.001"),
            "cfg_exists not a bool": entry(cfg_exists="true"),
            "cfg_exists missing": drop("cfg_exists"),
            "model not a string": entry(model=None),
            "model missing": drop("model"),
            "inventory_slots not a list": entry(inventory_slots="weaponFlashlight"),
            "inventory_slots with a non-string": entry(inventory_slots=["weaponFlashlight", 4]),
            "cfg_class missing": drop("cfg_class"),
            "cfg_class disagrees with the selection": entry(cfg_class="Proxymagazine_stanag"),
            "proxy_count missing": lambda r: r.pop("proxy_count"),
            "proxy_count not an int": lambda r: r.update(proxy_count="1"),
            "proxy_count a bool": lambda r: r.update(proxy_count=True),
            "proxy_count below the listed rows": lambda r: r.update(proxy_count=0),
            "proxy_scan_complete missing": lambda r: r.pop("proxy_scan_complete"),
            "proxy_scan_complete not a bool": lambda r: r.update(proxy_scan_complete=1),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                slot, record, result = self.attach([proxy()], mutate=mutate)
                self.assertEqual("pending", slot["verdict"], label)
                self.assertEqual("proxy_evidence_malformed", slot["reason"], label)
                self.assertEqual("pending", record["verdict"], label)
                self.assertEqual(0, pair_counts(result).get("server_qualified", 0), label)

    def test_a_proxy_count_without_the_list_is_malformed_not_missing(self):
        slot, _record, _result = self.attach([proxy()], mutate=lambda r: r.pop("proxies"))
        self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]))

    def test_a_scan_that_did_not_complete_is_pending_without_a_qualifying_row(self):
        slot, _record, _result = self.attach([proxy(slots=("pistolFlashlight",))],
                                             mutate=lambda r: r.update(proxy_scan_complete=False))
        self.assertEqual(("pending", "proxy_evidence_truncated"), (slot["verdict"], slot["reason"]))
        slot, _record, _result = self.attach([proxy()], mutate=lambda r: r.update(proxy_scan_complete=False))
        self.assertEqual("server_qualified", slot["verdict"])

    def test_absent_proxy_evidence_is_pending_and_never_qualified(self):
        """The probe-003 shape: neither proxy_count nor proxies, and every slot selection field empty."""
        slot, record, result = self.attach(None)
        self.assertEqual(("pending", "proxy_evidence_missing"), (slot["verdict"], slot["reason"]))
        self.assertEqual("pending", record["verdict"])
        self.assertEqual(0, result["denominators"]["server_qualified"])

    def test_a_truncated_list_without_a_qualifying_row_is_pending(self):
        slot, _record, _result = self.attach([proxy(slots=("pistolFlashlight",))], proxy_count=30)
        self.assertEqual(("pending", "proxy_evidence_truncated"), (slot["verdict"], slot["reason"]))

    def test_an_empty_complete_proxy_list_is_pending_for_the_client_not_a_negative_finding(self):
        slot, _record, _result = self.attach([])
        self.assertEqual(("pending", "pending_client"), (slot["verdict"], slot["reason"]))

    def test_the_selection_memory_and_bone_evidence_stays_an_alternative(self):
        slot, _record, _result = self.attach(None, slots=gun_slots(weapon_model=True))
        self.assertEqual(("server_qualified", "native_attach_with_model_selection"), (slot["verdict"], slot["reason"]))
        self.assertEqual("selection", slot["evidence"]["model_evidence"])
        slot, _record, _result = self.attach([proxy(slots=("pistolFlashlight",))], slots=gun_slots(weapon_model=True))
        self.assertEqual("server_qualified", slot["verdict"])

    def test_malformed_proxy_evidence_outranks_selection_evidence(self):
        slot, record, _result = self.attach([proxy()], mutate=lambda r: r.update(proxy_count="x"),
                                            slots=gun_slots(weapon_model=True))
        self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]))
        self.assertEqual("pending", record["verdict"])

    def test_the_prerequisite_variant_uses_its_own_reason(self):
        lights = good_gun_lights()
        lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False)
        variant = variant_obs("weaponHandguardAK", [good_gun_lights()[2]])
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), lights, prereq=prereq_obs(has="weaponHandguardAK"),
                    prereq_variant=variant, proxies=[proxy()])]
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        slot = result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite"),
                         (slot["verdict"], slot["reason"]))
        self.assertTrue(slot["evidence"]["requires_prerequisite"])
        self.assertEqual("proxy_config_slot", slot["evidence"]["model_evidence"])
        rows[0]["proxies"] = [proxy(slots=("pistolFlashlight",))]
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        slot = result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("geometry_missing", "proxy_belongs_to_other_slot"), (slot["verdict"], slot["reason"]))
        for key in ("proxies", "proxy_count", "proxy_scan_complete", *HOST_FACTS):
            del rows[0][key]
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        slot = result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("pending", "proxy_evidence_missing"), (slot["verdict"], slot["reason"]))

    def test_beam_and_the_other_axes_stay_pending(self):
        _slot, _record, result = self.attach([proxy()])
        self.assertEqual({axis: "pending" for axis in report.UNOBSERVED_AXES}, result["unobserved_axes"])

    def test_the_consumed_keys_name_the_proxy_fields(self):
        for key in ("proxies", "proxy_count", "selection", "cfg_class", "cfg_exists", "model", "inventory_slots",
                    "slot_count", "slot_scan_complete", "res_enum_ok", "res_lod_count", "res_lods_scanned",
                    "res_scan_complete", "res_lods", "name", "list_ok", "selection_count", "scan_complete", "vertex_ok",
                    "vertex"):
            self.assertIn(key, report.CONSUMED_KEYS)


class ProxyIdentityTests(unittest.TestCase):
    """Fix round 4 (hc-taped-light-review-004): contradictory or malformed proxy rows are judged before any slot match,
    so a positive row cannot be selected from a host whose own read-back disagrees with itself."""

    def judge(self, proxies, **extra):
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights(), proxies=proxies, **extra)]
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        return result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"], result

    def assert_pending_malformed(self, proxies, label="", **extra):
        slot, result = self.judge(proxies, **extra)
        self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]), label)
        self.assertEqual(0, pair_counts(result).get("server_qualified", 0), label)

    def test_one_selection_identity_with_conflicting_readbacks_is_malformed_in_either_order(self):
        negative = dict(proxy(), cfg_exists=False, model="", inventory_slots=[], slot_count=0)
        for order in ((proxy(), negative), (negative, proxy())):
            self.assert_pending_malformed(list(order), "conflicting duplicate")

    def test_each_conflicting_field_of_a_duplicate_identity_is_caught(self):
        for field, value in (("model", "\\dz\\other.p3d"), ("inventory_slots", ["pistolFlashlight"]),
                             ("cfg_class", "Proxyweaponlight_universal2"), ("slot_count", 3),
                             ("res_lods", [res_entry("1.000", "", vertex_ok=False)])):
            with self.subTest(field=field):
                self.assert_pending_malformed([proxy(), dict(proxy(), **{field: value})], field)

    def test_agreeing_aliases_of_one_identity_collapse_into_one_evidence_identity_and_still_qualify(self):
        """Review 007 P3a: ``proxy:/dz/..x.001`` and ``proxy:dz/..x.001`` (FNX45 natively) normalise to one identity. Copies
        that read the same config entry and the same resolution lookup are one piece of evidence, never malformed;
        case, slash and leading-slash spellings all count as the same identity."""
        slashed = proxy()
        bare = dict(proxy(), selection="proxy:" + LIGHT_PROXY_PATH[1:] + ".001")
        shouted = dict(proxy(), selection="PROXY:\\DZ\\Weapons\\Attachments\\Light\\WeaponLight_Universal.001")
        for label, proxies in (("identical copies", [proxy(), proxy()]), ("leading slash pair", [slashed, bare]),
                               ("reverse order", [bare, slashed]), ("case and slash variant", [proxy(), shouted]),
                               ("three spellings", [slashed, bare, shouted])):
            with self.subTest(label):
                slot, result = self.judge(proxies)
                self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot"),
                                 (slot["verdict"], slot["reason"]), label)
                self.assertEqual([], result["integrity"]["issues"], label)

    def test_aliases_keep_their_raw_rows_and_the_collapsed_count_as_diagnostics(self):
        bare = dict(proxy(), selection="proxy:" + LIGHT_PROXY_PATH[1:] + ".001")
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights(), proxies=[proxy(), bare])]
        rows[0]["proxy_count"] = 2
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        diagnostics = result["hosts"][0]["diagnostics"]
        self.assertEqual(2, rows[0]["proxy_count"])
        self.assertEqual(1, diagnostics["proxy_alias_collapsed"])
        self.assertEqual([proxy()["selection"], bare["selection"]], [item["selection"] for item in rows[0]["proxies"]])
        rows[0]["proxies"] = [proxy(number="001"), proxy(number="002")]       # two instances are two identities
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        self.assertEqual(0, result["hosts"][0]["diagnostics"]["proxy_alias_collapsed"])

    def test_conflicting_aliases_of_one_identity_stay_malformed_in_either_order(self):
        """The same identity read two ways is contradictory evidence, whichever spelling comes first."""
        bare = dict(proxy(), selection="proxy:" + LIGHT_PROXY_PATH[1:] + ".001")
        conflicts = {"model": dict(bare, model="\\dz\\other.p3d"),
                     "slots": dict(bare, inventory_slots=["pistolFlashlight"]),
                     "slot count": dict(bare, slot_count=9, slot_scan_complete=False),
                     "config exists": dict(bare, cfg_exists=False, model="", inventory_slots=[], slot_count=0),
                     "resolution selection": dict(bare, res_lods=[res_entry("1.000", "", vertex_ok=False)]),
                     "resolution vertex": dict(bare, res_lods=[res_entry("1.000", bare["res_lods"][0]["selection"],
                                                                         vertex=("9", "8", "7"))]),
                     "resolution lod name": dict(bare, res_lods=[dict(bare["res_lods"][0], name="0")])}
        for label, second in conflicts.items():
            for order in ((proxy(), second), (second, proxy())):
                with self.subTest(label, first=order[0]["selection"]):
                    self.assert_pending_malformed(list(order), label)

    def test_two_instances_of_one_proxy_that_read_the_same_config_differently_are_malformed(self):
        self.assert_pending_malformed([proxy(number="001"), proxy(number="002", slots=("pistolFlashlight",))], "slots")
        self.assert_pending_malformed([proxy(number="001"), proxy(number="002", exists=False)], "exists")
        slot, _result = self.judge([proxy(number="001"), proxy(number="002")])
        self.assertEqual("server_qualified", slot["verdict"])

    def test_a_malformed_proxy_name_is_never_qualified(self):
        for label, selection in (("non-numeric suffix", "proxy:" + LIGHT_PROXY_PATH + ".garbage"),
                                 ("no suffix", "proxy:" + LIGHT_PROXY_PATH),
                                 ("empty suffix", "proxy:" + LIGHT_PROXY_PATH + "."),
                                 ("signed suffix", "proxy:" + LIGHT_PROXY_PATH + ".-1"),
                                 ("unicode digit suffix", "proxy:" + LIGHT_PROXY_PATH + ".٣"),
                                 ("empty basename", "proxy:/dz/weapons/attachments/light/.001"),
                                 ("empty path", "proxy:.001"),
                                 ("slashes only", "proxy://.001"),
                                 ("no prefix", LIGHT_PROXY_PATH + ".001")):
            with self.subTest(label):
                self.assert_pending_malformed([dict(proxy(), selection=selection)], label)

    def test_a_raw_trailing_slash_before_the_instance_is_malformed_even_with_a_coherent_config_row(self):
        """The coherent counterexample: the basename is empty in the selection but the config row agrees with the
        normalised path, so only the raw trailing-slash guard of the name parser refuses it (review 005 mutant)."""
        item = proxy(path="/dz/weapons/attachments/light", number="001", cfg_class="Proxylight")
        item["selection"] = "proxy:/dz/weapons/attachments/light/.001"
        self.assert_pending_malformed([item], "empty basename, coherent row")

    def test_an_empty_basename_hidden_behind_the_p3d_extension_is_malformed_even_with_a_coherent_row(self):
        """Review 007 P3b: ``.../light/.p3d.001`` has no raw trailing slash, and only after the extension is stripped is the
        basename empty. The config row, the model path and the resolution selection all agree with that empty basename, so
        only the two normalised-path guards of the name parser refuse it (the combined deletion mutant)."""
        selection = "proxy:/dz/weapons/attachments/light/.p3d.001"
        item = proxy(path="/dz/weapons/attachments/light/", cfg_class="Proxy",
                     model="\\dz\\weapons\\attachments\\light\\.p3d", res_selection=selection)
        item["selection"] = selection
        self.assertEqual("Proxy", item["cfg_class"])
        self.assert_pending_malformed([item], "empty basename behind the extension, coherent row")
        self.assertIsNone(report._proxy_name(selection))
        for other in ("proxy:/dz/weapons/attachments/light/.P3D.007", "proxy:\\dz\\weapons\\attachments\\light\\.p3d.1"):
            self.assertIsNone(report._proxy_name(other), other)

    def test_a_malformed_name_in_any_row_makes_the_host_pending_even_with_a_valid_matching_row_present(self):
        self.assert_pending_malformed([proxy(), dict(proxy(path="/dz/x/muzzle"), selection="proxy:/dz/x/muzzle.garbage")])

    def test_slot_bookkeeping_must_be_typed_and_consistent(self):
        for label, change in (("slot_count missing", lambda r: r.pop("slot_count")),
                              ("slot_count a bool", lambda r: r.update(slot_count=True)),
                              ("slot_count a string", lambda r: r.update(slot_count="1")),
                              ("slot_count below the listed slots", lambda r: r.update(slot_count=0)),
                              ("slot_scan_complete missing", lambda r: r.pop("slot_scan_complete")),
                              ("slot_scan_complete not a bool", lambda r: r.update(slot_scan_complete=1)),
                              ("complete although slots were dropped", lambda r: r.update(slot_count=9)),
                              ("incomplete although every slot is listed", lambda r: r.update(slot_scan_complete=False))):
            with self.subTest(label):
                item = proxy()
                change(item)
                self.assert_pending_malformed([item], label)


class AliasConflictScopeTests(unittest.TestCase):
    """Fix round 9 (Sol review of round 8, P2-1/P2-2/P2-3 and the R02/R03 survivors).

    A host whose proxy copies of one identity contradict each other stays pending whatever the native attach said, and the
    contradiction withholds evidence only from the light slots its copies implicate: an unrelated alias conflict (a
    magazine proxy) leaves an independently valid light pair alone. Coherent aliases collapse into one evidence row."""

    MAG = "/dz/weapons/attachments/magazine/mag_stanag"

    def conflicting_light(self):
        first = proxy()
        return first, dict(first, selection="proxy:" + LIGHT_PROXY_PATH[1:] + ".001", cfg_exists=False, model="",
                           inventory_slots=[], slot_count=0)

    def magazine(self, conflict):
        first = proxy(self.MAG, slots=("magazine",))
        bare = dict(first, selection="proxy:" + self.MAG[1:] + ".001")
        return first, dict(bare, model="\\dz\\other.p3d") if conflict else bare

    def build(self, proxies, lights=None, group="slot_host", slots=None, **extra):
        rows = [row("AK74", group, gun_slots(weapon_model=False) if slots is None else slots,
                    good_gun_lights() if lights is None else lights, proxies=proxies, **extra)]
        return report.build_report(classification([host("AK74", group)]), observations(rows))

    def assert_pending_for_conflict(self, result, label, pair="UniversalLight", reason="proxy_evidence_malformed"):
        record = result["hosts"][0]
        self.assertEqual("pending", record["verdict"], label)
        self.assertIn("proxy_alias_conflict", record["reasons"], label)
        self.assertEqual("pending", record["lights"][pair]["verdict"], label)
        self.assertEqual([], result["integrity"]["issues"], label)
        for slot in record["lights"][pair]["slots"].values():
            self.assertEqual(("pending", reason), (slot["verdict"], slot["reason"]), label)

    def refusal_cases(self):
        def refused():
            lights = good_gun_lights()
            lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False)
            return lights
        variant_lights = good_gun_lights()
        variant_lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False)
        accepted = good_gun_lights()
        failed = good_gun_lights()
        failed[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=True, attach_ok=False)
        return {
            "direct refusal": dict(lights=refused()),
            "attach accepted": dict(lights=accepted),
            "accepted attach that failed to create": dict(lights=failed),
            "refusal with a satisfied prerequisite": dict(lights=refused(), prereq=prereq_obs(
                has="weaponHandguardAK", rail=True, attached="AK_RailHndgrd")),
            "refusal with an unmet prerequisite and no variant": dict(lights=refused(), prereq=prereq_obs(has="weaponHandguardAK")),
            "refusal with missing prerequisite evidence": dict(lights=refused(), prereq=[]),
            "prerequisite variant refused": dict(lights=refused(), prereq=prereq_obs(has="weaponHandguardAK"),
                                                 prereq_variant=variant_obs("weaponHandguardAK", variant_lights)),
        }

    def test_a_light_alias_conflict_keeps_the_pair_pending_whatever_the_attach_outcome_in_either_order(self):
        first, second = self.conflicting_light()
        for label, extra in self.refusal_cases().items():
            for order in ((first, second), (second, first)):
                with self.subTest(label, cfg_exists_first=order[0]["cfg_exists"]):
                    result = self.build(list(order), **extra)
                    self.assert_pending_for_conflict(result, label)
                    self.assertNotIn("geometry_missing", {slot["verdict"] for slot in
                                                          result["hosts"][0]["lights"]["UniversalLight"]["slots"].values()})

    def test_a_light_alias_conflict_keeps_a_light_that_fits_no_host_slot_pending(self):
        """TLRLight fits only the pistol slot; the host owns only the weapon slot, so its pair is a native
        no_compatible_native_slot refusal. The conflict implicates the weapon slot the host owns, so the pair is pending."""
        first, second = self.conflicting_light()
        plain = self.build([first])
        self.assertEqual(("geometry_missing", ["no_compatible_native_slot"]),
                         (plain["hosts"][0]["lights"]["TLRLight"]["verdict"],
                          plain["hosts"][0]["lights"]["TLRLight"]["reasons"]))
        for order in ((first, second), (second, first)):
            result = self.build(list(order))
            self.assertEqual("pending", result["hosts"][0]["verdict"])
            self.assertEqual("pending", result["hosts"][0]["lights"]["TLRLight"]["verdict"])
            self.assertIn("proxy_evidence_malformed", result["hosts"][0]["lights"]["TLRLight"]["reasons"])

    def test_a_host_without_a_native_light_slot_stays_pending_for_the_conflict(self):
        first, second = self.conflicting_light()
        for order in ((first, second), (second, first)):
            result = self.build(list(order), group="no_slot_host", slots=no_slots(), lights=refusal_lights())
            self.assertEqual("pending", result["hosts"][0]["verdict"])
            self.assertIn("proxy_alias_conflict", result["hosts"][0]["reasons"])

    def test_an_implicated_slot_is_withheld_even_when_the_model_names_a_selection_for_it(self):
        first, second = self.conflicting_light()
        slots = gun_slots(weapon_model=True)
        result = self.build([first, second], slots=slots)       # the weapon slot is implicated: malformed outranks selection
        self.assert_pending_for_conflict(result, "implicated slot with a selection")

    def test_an_unrelated_alias_conflict_keeps_the_host_pending_and_an_independent_light_pair_valid(self):
        light = proxy()
        for conflict in (False, True):
            first, second = self.magazine(conflict)
            for order in ((light, first, second), (first, second, light), (second, first, light)):
                with self.subTest(conflict=conflict, order=[item["selection"] for item in order]):
                    result = self.build(list(order))
                    record = result["hosts"][0]
                    pair = record["lights"]["UniversalLight"]
                    self.assertEqual("server_qualified", pair["verdict"])
                    self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot"),
                                     (pair["slots"]["weaponFlashlight"]["verdict"], pair["slots"]["weaponFlashlight"]["reason"]))
                    self.assertEqual([], result["integrity"]["issues"])
                    self.assertEqual("pending" if conflict else "server_qualified", record["verdict"])
                    self.assertEqual(conflict, "proxy_alias_conflict" in record["reasons"])

    def test_copies_that_disagree_about_the_slot_implicate_every_slot_either_copy_lists(self):
        """One copy of the identity lists only a magazine slot, the other the weapon light slot: the favourable copy is
        never chosen, so the weapon light slot is withheld even though an independent proxy also lists it."""
        listed = proxy(self.MAG, slots=("weaponFlashlight",))
        quiet = dict(proxy(self.MAG, slots=("magazine",)), selection="proxy:" + self.MAG[1:] + ".001")
        for order in ((proxy(), listed, quiet), (proxy(), quiet, listed), (quiet, listed, proxy())):
            result = self.build(list(order))
            self.assert_pending_for_conflict(result, "slot disagreement")

    def test_a_copy_with_a_truncated_slot_list_implicates_every_light_slot(self):
        filler = tuple("unrelated%d" % number for number in range(8))
        cut = proxy(self.MAG, slots=filler, slot_count=12)
        other = dict(proxy(self.MAG, slots=("magazine",)), selection="proxy:" + self.MAG[1:] + ".001")
        for order in ((proxy(), cut, other), (other, cut, proxy())):
            result = self.build(list(order))
            self.assert_pending_for_conflict(result, "truncated conflicting copy")

    def test_two_identities_reading_one_config_class_two_ways_implicate_the_slots_of_both(self):
        first = proxy(self.MAG, slots=("magazine",))
        second = proxy(self.MAG, number="002", slots=("weaponFlashlight",))
        for order in ((first, second), (second, first)):
            result = self.build([proxy(), *order])
            self.assert_pending_for_conflict(result, "one class read two ways")

    def test_coherent_aliases_collapse_into_exactly_one_parsed_evidence_row(self):
        """Review R02: aliases that agree are one piece of evidence; two parsed rows would double count it."""
        bare = dict(proxy(), selection="proxy:" + LIGHT_PROXY_PATH[1:] + ".001")
        shouted = dict(proxy(), selection="PROXY:\\DZ\\Weapons\\Attachments\\Light\\WeaponLight_Universal.001")
        for label, proxies, rows in (("identical", [proxy(), proxy()], 1), ("leading slash", [proxy(), bare], 1),
                                     ("three spellings", [proxy(), bare, shouted], 1),
                                     ("two instances", [proxy(number="001"), proxy(number="002")], 2),
                                     ("two paths", [proxy(), proxy(self.MAG, slots=("magazine",))], 2)):
            with self.subTest(label):
                built = row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights(), proxies=proxies)
                parsed = report._proxies(built)
                self.assertEqual("ok", parsed[0])
                self.assertEqual(rows, len(parsed[1]), label)

    def test_proxy_slot_membership_is_exact_and_case_sensitive(self):
        """Review P2-3: owner rule C. ``weaponflashlight`` is not the exact slot ``weaponFlashlight``; only proxy paths and
        config class spellings are normalised."""
        for spelling in ("weaponflashlight", "WEAPONFLASHLIGHT", "WeaponFlashlight", " weaponFlashlight", "weaponFlashlight "):
            with self.subTest(spelling):
                result = self.build([proxy(slots=(spelling,))])
                slot = result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
                self.assertEqual(("pending", "pending_client"), (slot["verdict"], slot["reason"]))
                self.assertEqual(0, pair_counts(result).get("server_qualified", 0))
        slot = self.build([proxy(slots=("weaponFlashlight",))])["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual("server_qualified", slot["verdict"])

    def test_another_light_slot_is_recognised_only_by_its_exact_name(self):
        """A proxy listing ``PistolFlashlight`` (case changed) names no native light slot, so it is not a real negative for
        the weapon slot; the exact ``pistolFlashlight`` is."""
        slot = self.build([proxy(slots=("PistolFlashlight",))])["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("pending", "pending_client"), (slot["verdict"], slot["reason"]))
        slot = self.build([proxy(slots=("pistolFlashlight",))])["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("geometry_missing", "proxy_belongs_to_other_slot"), (slot["verdict"], slot["reason"]))


class SlotListTruncationTests(unittest.TestCase):
    """Fix round 4: the hook lists at most eight inventory slots per proxy row; a slot beyond the cap is unknown."""

    FILLER = tuple("unrelated%d" % number for number in range(8))

    def judge(self, proxies):
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights(), proxies=proxies)]
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        return result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"], result

    def test_a_truncated_slot_list_without_the_slot_is_pending_not_negative(self):
        slot, result = self.judge([proxy(slots=self.FILLER, slot_count=9)])
        self.assertEqual(("pending", "proxy_slot_list_truncated"), (slot["verdict"], slot["reason"]))
        self.assertEqual(0, result["denominators"]["server_qualified"])

    def test_a_listed_slot_still_qualifies_when_the_list_is_truncated(self):
        slot, _result = self.judge([proxy(slots=self.FILLER[:7] + ("weaponFlashlight",), slot_count=12)])
        self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot"), (slot["verdict"], slot["reason"]))

    def test_a_complete_slot_list_without_the_slot_is_pending_for_the_client_unless_it_names_another_light_slot(self):
        slot, _result = self.judge([proxy(slots=self.FILLER)])
        self.assertEqual(("pending", "pending_client"), (slot["verdict"], slot["reason"]))
        slot, _result = self.judge([proxy(slots=self.FILLER[:3] + ("pistolFlashlight",))])
        self.assertEqual(("geometry_missing", "proxy_belongs_to_other_slot"), (slot["verdict"], slot["reason"]))

    def test_only_a_truncated_row_that_could_hold_the_slot_keeps_the_slot_pending(self):
        other = proxy(path="/dz/weapons/attachments/magazine/mag_stanag", slots=self.FILLER, slot_count=20)
        slot, _result = self.judge([proxy(slots=("pistolFlashlight",)), other])
        self.assertEqual(("pending", "proxy_slot_list_truncated"), (slot["verdict"], slot["reason"]))
        mismatched = proxy(slots=self.FILLER, slot_count=20, model="\\dz\\weapons\\attachments\\light\\other.p3d")
        slot, _result = self.judge([mismatched])
        self.assertEqual(("pending", "pending_client"), (slot["verdict"], slot["reason"]))

    def test_the_older_selection_evidence_is_not_overridden_by_a_truncated_slot_list(self):
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=True), good_gun_lights(),
                    proxies=[proxy(slots=self.FILLER, slot_count=9)])]
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        slot = result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("server_qualified", "native_attach_with_model_selection"), (slot["verdict"], slot["reason"]))


def facts_of(res, extra=("geometry",)):
    """Host facts as the hook writes them for a resolution scan ``res`` (a res_host result): the diagnostic LOD name list is
    the numeric names followed by ``extra`` (non-resolution LODs), cut at eight names like the hook's list."""
    listed = res["res_enum_ok"]
    names = [item["name"] for item in res["res_lods"]] + list(extra)
    count = max(res["res_lod_count"], len(res["res_lods"])) + len(extra) if listed else 0
    shown = names[:8] if listed else []
    return dict(copy.deepcopy(res), lod_list_ok=listed, lod_count=count, lod_names=shown,
                lod_names_complete=len(shown) == count, view_by_name=False)


def legacy_proxy(**changes):
    """A proxy row as the round-4 to round-6 hook wrote it: view-LOD fields, no per-resolution-LOD list."""
    item = {key: value for key, value in proxy(**changes).items() if key != "res_lods"}
    return dict(item, view_selection="", view_vertex_ok=False, view_vertex=[])


LEGACY_HOST = {"view_lod": False, "view_selection_count": 0, "view_scan_complete": False, "view_list_ok": False,
               "lod_list_ok": True, "lod_count": 2, "lod_names": ["1.000", "geometry"], "lod_names_complete": True,
               "view_by_name": False}
SELECTION = "proxy:" + LIGHT_PROXY_PATH + ".001"
GOOD = ("server_qualified", "native_attach_with_proxy_config_slot")


class ResolutionLodEvidenceTests(unittest.TestCase):
    """Round 7 (taped-light-probe-005): the dedicated server has no LOD named "view" (a client inventory helper's LOD), so the
    model-proxy evidence is the resolution LODs, whose names are numeric ("0", "1", "1.000"). A proxy qualifies only when the
    native attach was ok, the Proxy<basename> class exists with the proxy's own model, the slot is listed, and a numeric LOD
    whose selection scan was complete holds that proxy selection. Anything unknown is pending. This is source-level evidence
    of a model proxy slot on the server-side model only; it says nothing about beam render, the switch, two-client
    presentation, removal by hand, tape consumption or persistence."""

    def judge(self, proxies=None, facts=None, **extra):
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights(),
                    proxies=[proxy()] if proxies is None else proxies, facts=facts)]
        rows[0].update(extra)
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        record = result["hosts"][0]
        return record["lights"]["UniversalLight"]["slots"]["weaponFlashlight"], record, result

    def verdict(self, *args, **kwargs):
        slot, _record, _result = self.judge(*args, **kwargs)
        return slot["verdict"], slot["reason"]

    def status(self, *args, **kwargs):
        """Round 8: resolution membership is a diagnostic. (slot verdict, resolution_status) of the AK74 weaponFlashlight pair."""
        slot, _record, _result = self.judge(*args, **kwargs)
        return slot["verdict"], slot["evidence"]["resolution_status"]

    def test_a_resolution_lod_holding_the_proxy_selection_qualifies_and_the_evidence_is_reported(self):
        slot, record, result = self.judge()
        self.assertEqual(GOOD, (slot["verdict"], slot["reason"]))
        evidence = slot["evidence"]
        self.assertEqual("proxy_config_slot", evidence["model_evidence"])
        self.assertEqual(SELECTION, evidence["proxy_selection"])
        self.assertEqual(("1.000", SELECTION, [0.5, 0.25, -1.5]),
                         (evidence["resolution_lod"], evidence["resolution_selection"], evidence["resolution_vertex"]))
        self.assertEqual("server_qualified", record["verdict"])
        self.assertEqual("PENDING", result["acceptance"])
        self.assertEqual({axis: "pending" for axis in report.UNOBSERVED_AXES}, result["unobserved_axes"])

    def test_no_label_keeps_the_view_lod_name(self):
        slot, _record, result = self.judge()
        self.assertNotIn("view_lod", json.dumps(result))
        self.assertNotIn("view_selection", json.dumps(slot))

    def test_without_the_proxy_selection_in_a_complete_resolution_lod_the_pair_still_qualifies_and_the_status_names_why(self):
        failed_list = dict(name="1.000", list_ok=False, selection_count=0, scan_complete=False)
        cut_scan = dict(name="1.000", list_ok=True, selection_count=900, scan_complete=False)
        many = [str(number) for number in range(16)]
        cases = {
            "no numeric lod": (facts_of(res_host(empty=True), extra=("geometry", "memory")), [proxy(res=[])],
                               "resolution_lod_absent"),
            "proxy not in the lod, complete scan": (None, [proxy(res_selection="")], "resolution_proxy_missing"),
            "lod list failed": (facts_of(res_host(enum_ok=False, empty=True)), [proxy(res=[])],
                                "resolution_enumeration_failed"),
            "selection list failed on the only lod": (facts_of(res_host(failed_list)),
                                                      [proxy(res=[res_entry("1.000", "", list_ok=False)])],
                                                      "resolution_enumeration_failed"),
            "selection list failed on one of two lods": (facts_of(res_host(("0", 4), dict(failed_list, name="1"))),
                                                         [proxy(res=[res_entry("0", ""), res_entry("1", "", list_ok=False)])],
                                                         "resolution_enumeration_failed"),
            "scan cut, selection missing": (facts_of(res_host(cut_scan)), [proxy(res_selection="")],
                                            "resolution_evidence_truncated"),
            "selection found in a cut scan": (facts_of(res_host(cut_scan)), [proxy()], "resolution_evidence_truncated"),
            "more numeric lods than scanned": (facts_of(res_host(*[(name, 3) for name in many], count=20)),
                                               [proxy(res=[res_entry(name, "") for name in many])],
                                               "resolution_evidence_truncated"),
            "selection names another model": (None, [proxy(res_selection="proxy:/dz/other/thing.001")],
                                              "resolution_selection_mismatch"),
            "no first vertex": (None, [proxy(vertex_ok=False)], "resolution_vertex_missing"),
            "vertex not three numbers": (None, [proxy(vertex=("1", "2"))], "resolution_vertex_invalid"),
            "vertex not numeric": (None, [proxy(vertex=("1", "x", "3"))], "resolution_vertex_invalid"),
            "vertex not finite": (None, [proxy(vertex=("1", "nan", "3"))], "resolution_vertex_invalid"),
            "vertex infinite": (None, [proxy(vertex=("1", "inf", "3"))], "resolution_vertex_invalid"),
        }
        for label, (facts, proxies, reason) in cases.items():
            with self.subTest(label):
                slot, record, result = self.judge(proxies, facts=facts)
                self.assertEqual(GOOD, (slot["verdict"], slot["reason"]), label)       # diagnostic only, never a gate
                self.assertEqual(reason, slot["evidence"]["resolution_status"], label)
                self.assertEqual("server_qualified", record["verdict"], label)
                self.assertEqual(1, result["denominators"]["server_qualified"], label)

    def test_one_complete_resolution_lod_holding_the_proxy_is_enough(self):
        facts = facts_of(res_host(("0", 5), ("1", 7)))
        for label, res in (("second lod", [res_entry("0", ""), res_entry("1", SELECTION)]),
                           ("first lod", [res_entry("0", SELECTION), res_entry("1", "")]),
                           ("first lod without a vertex", [res_entry("0", SELECTION, vertex_ok=False),
                                                           res_entry("1", SELECTION)]),
                           ("first lod names another model", [res_entry("0", "proxy:/dz/x/y.001"),
                                                              res_entry("1", SELECTION)])):
            with self.subTest(label):
                self.assertEqual(GOOD, self.verdict([proxy(res=res)], facts))
        repeated = facts_of(res_host(("1", 5), ("1", 5)))       # the engine repeats a resolution name on some hosts
        self.assertEqual(GOOD, self.verdict([proxy(res=[res_entry("1", ""), res_entry("1", SELECTION)])], repeated))
        both = [res_entry("0", "proxy:/dz/x/y.001"), res_entry("1", SELECTION, vertex_ok=False)]
        self.assertEqual(("server_qualified", "resolution_selection_mismatch"), self.status([proxy(res=both)], facts))
        self.assertEqual(("server_qualified", "member"), self.status([proxy(res=[res_entry("0", ""), res_entry("1", SELECTION)])], facts))

    def test_only_numeric_named_lods_count_and_any_other_lod_name_is_malformed_evidence(self):
        selection = SELECTION
        for name in ("0", "1", "1.000", "10", "0.5", "01"):
            with self.subTest(accepted=name):
                self.assertEqual(GOOD, self.verdict([proxy(res=[res_entry(name, selection)])], facts_of(res_host((name, 3)))))
        for name in ("geometry", "memory", "view", "View", "VIEW_PILOT", "landContact", "geometryView", "geometryFire", "",
                     "-1", "1e3", "1.", ".5", "0x10", " 1", "1 ", "1.0.0", "٣", "1\n"):
            with self.subTest(refused=name):
                self.assertEqual(("pending", "proxy_evidence_malformed"),
                                 self.verdict([proxy(res=[res_entry(name, selection)])], facts_of(res_host((name, 3)))))

    def test_a_view_lod_never_stands_in_for_a_resolution_lod(self):
        facts = dict(facts_of(res_host(empty=True), extra=("view", "geometry")), view_by_name=True)
        self.assertEqual(("server_qualified", "resolution_lod_absent"), self.status([proxy(res=[])], facts))
        facts = dict(facts_of(res_host()), view_by_name=True, lod_names=["1.000", "view"])
        self.assertEqual(("server_qualified", "resolution_proxy_missing"), self.status([proxy(res_selection="")], facts))
        self.assertEqual(GOOD, self.verdict([proxy()], facts))       # view_by_name and the names are diagnostics only

    def test_the_lod_name_list_and_the_resolution_facts_must_not_contradict_each_other(self):
        two = facts_of(res_host(("0", 3), ("1", 3)))
        proxies = [proxy(res=[res_entry("0", ""), res_entry("1", SELECTION)])]
        cases = {
            "list flag disagrees": dict(two, lod_list_ok=False, lod_count=0, lod_names=[]),
            "complete name list misses a numeric lod": dict(two, lod_names=["0", "geometry", "memory"], lod_count=3),
            "complete name list holds another numeric lod": dict(two, lod_names=["0", "1", "2"], lod_count=3),
            "numeric names in another order": dict(two, lod_names=["1", "0", "geometry"], lod_count=3),
            "count below the numeric lods": dict(two, lod_count=1, lod_names=["0"], lod_names_complete=True),
        }
        for label, facts in cases.items():
            with self.subTest(label):
                self.assertEqual(("pending", "proxy_evidence_malformed"), self.verdict(proxies, facts), label)
        self.assertEqual(GOOD, self.verdict(proxies, two))
        lod_less = {key: value for key, value in two.items() if key not in report.LOD_HOST_KEYS}
        self.assertEqual(("pending", "proxy_evidence_malformed"), self.verdict(proxies, lod_less))

    def test_malformed_host_resolution_facts_are_pending_malformed_evidence(self):
        def host_with(**changes):
            return dict(copy.deepcopy(HOST_FACTS), **changes)

        def lod(**changes):
            return host_with(res_lods=[dict(HOST_FACTS["res_lods"][0], **changes)])
        cases = {"res_enum_ok not a bool": host_with(res_enum_ok=1),
                 "res_lod_count not an int": host_with(res_lod_count="1"),
                 "res_lod_count a bool": host_with(res_lod_count=True),
                 "res_lod_count negative": host_with(res_lod_count=-1),
                 "res_lods_scanned differs from the list": host_with(res_lods_scanned=2),
                 "res_scan_complete not a bool": host_with(res_scan_complete="yes"),
                 "res_scan_complete claimed with a cut lod": lod(scan_complete=False, selection_count=900) | {"res_scan_complete": True},
                 "res_scan_complete denied with everything scanned": host_with(res_scan_complete=False),
                 "res_lods not a list": host_with(res_lods={"name": "1.000"}),
                 "res_lods entry not an object": host_with(res_lods=["1.000"]),
                 "lod name not text": lod(name=1),
                 "lod list_ok not a bool": lod(list_ok=1),
                 "lod selection_count not an int": lod(selection_count="3"),
                 "lod selection_count a bool": lod(selection_count=True),
                 "lod selection_count negative": lod(selection_count=-1),
                 "lod scan_complete not a bool": lod(scan_complete="yes"),
                 "lod scan_complete after a failed list": lod(list_ok=False, selection_count=0),
                 "lod selections counted after a failed list": lod(list_ok=False, selection_count=3, scan_complete=False),
                 "lod scan_complete above the selection cap": lod(selection_count=report.MAX_RES_SELECTIONS + 1),
                 "lod scan incomplete within the cap": lod(scan_complete=False),
                 "failed enumeration with lods": host_with(res_enum_ok=False, res_scan_complete=False),
                 "failed enumeration with a count": host_with(res_enum_ok=False, res_lods=[], res_lods_scanned=0,
                                                              res_lod_count=2, res_scan_complete=False),
                 "count above the listed lods within the cap": host_with(res_lod_count=3),
                 "more lods than the cap": res_host(*[(str(number), 1) for number in range(report.MAX_RES_LODS + 1)]),
                 "lods above the count": host_with(res_lod_count=0)}
        for key in report.RES_HOST_KEYS:
            cases["only some res keys: " + key + " missing"] = {k: v for k, v in HOST_FACTS.items() if k != key}
        for label, facts in cases.items():
            with self.subTest(label):
                facts = dict(facts)
                facts.update({k: v for k, v in LOD_FACTS.items() if k not in facts})
                slot, _record, result = self.judge([proxy()], facts=facts)
                self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]), label)
                self.assertEqual(0, result["denominators"]["server_qualified"], label)

    def test_malformed_row_resolution_entries_are_pending_malformed_evidence(self):
        good = res_entry("1.000", SELECTION)
        cases = {
            "res_lods missing": {k: v for k, v in proxy().items() if k != "res_lods"},
            "res_lods not a list": dict(proxy(), res_lods={"name": "1.000"}),
            "entry not an object": dict(proxy(), res_lods=["1.000"]),
            "no entry for the host lod": dict(proxy(), res_lods=[]),
            "an extra entry": dict(proxy(), res_lods=[good, res_entry("1.000", "")]),
            "name differs from the host lod": dict(proxy(), res_lods=[dict(good, name="2.000")]),
            "name missing": dict(proxy(), res_lods=[{k: v for k, v in good.items() if k != "name"}]),
            "list_ok differs from the host lod": dict(proxy(), res_lods=[dict(good, list_ok=False)]),
            "list_ok missing": dict(proxy(), res_lods=[{k: v for k, v in good.items() if k != "list_ok"}]),
            "selection not text": dict(proxy(), res_lods=[dict(good, selection=7)]),
            "selection missing": dict(proxy(), res_lods=[{k: v for k, v in good.items() if k != "selection"}]),
            "vertex_ok not a bool": dict(proxy(), res_lods=[dict(good, vertex_ok="true")]),
            "vertex_ok missing": dict(proxy(), res_lods=[{k: v for k, v in good.items() if k != "vertex_ok"}]),
            "vertex not a list": dict(proxy(), res_lods=[dict(good, vertex="0.5,0.25,-1.5")]),
            "vertex missing": dict(proxy(), res_lods=[{k: v for k, v in good.items() if k != "vertex"}]),
            "vertex entries claimed without vertex_ok": dict(proxy(), res_lods=[dict(good, vertex_ok=False)]),
            "vertex_ok without a selection": dict(proxy(), res_lods=[dict(good, selection="")]),
            "selection claimed in a lod without selections": None,
        }
        empty_lod = dict(res_host(("1.000", 0)))
        for label, item in cases.items():
            with self.subTest(label):
                if item is None:
                    slot, _record, _result = self.judge([proxy()], facts=facts_of(empty_lod))
                else:
                    slot, _record, _result = self.judge([item])
                self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]), label)

    def test_a_selection_claimed_while_the_lod_selection_list_failed_is_malformed(self):
        failed = dict(name="1.000", list_ok=False, selection_count=0, scan_complete=False)
        self.assertEqual(("pending", "proxy_evidence_malformed"),
                         self.verdict([proxy(res=[res_entry("1.000", SELECTION, list_ok=False)])], facts_of(res_host(failed))))

    def test_one_model_cannot_have_two_different_resolution_results_in_either_order(self):
        """The resolution lookup is one result per model and host: rows of one model that disagree are contradictory reads,
        even when one row would qualify on its own."""
        cases = {
            "missing selection": dict(proxy(number="002"), res_lods=[res_entry("1.000", "")]),
            "different vertex": proxy(number="002", vertex=("10", "20", "30")),
            "different selection": proxy(number="002", res_selection="proxy:" + LIGHT_PROXY_PATH + ".002"),
            "vertex flag only": dict(proxy(number="002"), res_lods=[res_entry("1.000", SELECTION, vertex_ok=False)]),
        }
        for label, second in cases.items():
            for order in ((proxy(number="001"), second), (second, proxy(number="001"))):
                with self.subTest(label, first=order[0]["selection"]):
                    slot, _record, result = self.judge(list(order))
                    self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]))
                    self.assertEqual(0, result["denominators"]["server_qualified"])

    def test_two_instances_that_share_one_resolution_result_still_qualify(self):
        self.assertEqual(GOOD, self.verdict([proxy(number="001"), proxy(number="002")]))

    def test_slash_case_and_instance_spellings_are_normalised_before_the_whole_path_is_compared(self):
        for selection in ("PROXY:\\DZ\\WEAPONS\\ATTACHMENTS\\LIGHT\\WEAPONLIGHT_UNIVERSAL.001",
                          "proxy:/dz/weapons/attachments/light/weaponlight_universal.007",
                          "proxy:dz/weapons/attachments/light/weaponlight_universal.12"):
            with self.subTest(selection):
                self.assertEqual(GOOD, self.verdict([proxy(res_selection=selection)]))

    def test_only_the_same_proxy_model_is_evidence_never_a_coincidental_name(self):
        base = "/dz/weapons/attachments/light/weaponlight_universal"
        for label, selection in (("longer model name", "proxy:" + base + "_extra.001"),
                                 ("version suffix", "proxy:" + base + "_v2.001"),
                                 ("longer directory", "proxy:/xx" + base + ".001"),
                                 ("generic named selection", "label" + base),
                                 ("generic selection with an instance", "label" + base + ".001"),
                                 ("no proxy prefix", base + ".001"),
                                 ("no instance suffix", "proxy:" + base),
                                 ("non-numeric instance suffix", "proxy:" + base + ".garbage"),
                                 ("empty instance suffix", "proxy:" + base + "."),
                                 ("only the basename", "proxy:weaponlight_universal.001"),
                                 ("a trailing component", "proxy:" + base + "/child.001")):
            with self.subTest(label):
                self.assertEqual(("server_qualified", "resolution_selection_mismatch"),
                                 self.status([proxy(res_selection=selection)]), label)       # a diagnostic, never a stand-in

    def test_a_row_that_would_not_match_the_slot_is_not_judged_for_resolution_evidence(self):
        unrelated = proxy(path="/dz/weapons/attachments/magazine/mag_stanag", slots=("magazine",), res_selection="")
        self.assertEqual(GOOD, self.verdict([proxy(), unrelated]))
        self.assertEqual(("geometry_missing", "proxy_belongs_to_other_slot"),
                         self.verdict([proxy(slots=("pistolFlashlight",), res_selection="")]))

    def test_the_prerequisite_variant_keeps_resolution_membership_as_a_diagnostic(self):
        lights = good_gun_lights()
        lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False)
        variant = variant_obs("weaponHandguardAK", [good_gun_lights()[2]])
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), lights, prereq=prereq_obs(has="weaponHandguardAK"),
                    prereq_variant=variant, proxies=[proxy(res_selection="")])]
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        slot = result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite"),
                         (slot["verdict"], slot["reason"]))
        self.assertEqual("resolution_proxy_missing", slot["evidence"]["resolution_status"])
        rows[0]["proxies"] = [proxy()]
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        slot = result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite"),
                         (slot["verdict"], slot["reason"]))

    def test_rows_from_the_view_lod_producers_carry_no_resolution_evidence_and_say_so_as_a_diagnostic(self):
        """probe-004 and probe-005 (rounds 4 to 6) wrote view-LOD fields and no per-resolution-LOD list. Those rows are
        consistent but prove nothing about the resolution LODs; the proxy config join still decides, and the diagnostic says
        resolution_lod_evidence_missing whatever the old fields say."""
        legacy_views = (LEGACY_HOST,
                        dict(LEGACY_HOST, view_lod=True, view_selection_count=3, view_scan_complete=True, view_list_ok=True,
                             lod_names=["1.000", "view"], view_by_name=True))
        for index, facts in enumerate(legacy_views):
            with self.subTest(index):
                slot, record, result = self.judge([legacy_proxy()], facts=facts)
                self.assertEqual(GOOD, (slot["verdict"], slot["reason"]))
                self.assertEqual("resolution_lod_evidence_missing", slot["evidence"]["resolution_status"])
                self.assertEqual("server_qualified", record["verdict"])
        slot, _record, _result = self.judge([legacy_proxy(slots=("pistolFlashlight",))], facts=LEGACY_HOST)
        self.assertEqual(("geometry_missing", "proxy_belongs_to_other_slot"), (slot["verdict"], slot["reason"]))
        slot, _record, _result = self.judge([], facts=LEGACY_HOST)
        self.assertEqual(("pending", "pending_client"), (slot["verdict"], slot["reason"]))

    def test_resolution_rows_next_to_a_host_without_resolution_facts_are_malformed(self):
        slot, _record, _result = self.judge([proxy()], facts=LEGACY_HOST)
        self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]))

    def test_the_module_documents_the_evidence_source_and_what_it_does_not_prove(self):
        doc = report.__doc__
        for text in ("resolution LOD", "numeric", "model proxy slot", "server-side model", "view_lod_absent_on_server",
                     "resolution_lod_absent", "resolution_proxy_missing", "resolution_enumeration_failed",
                     "beam render", "two-client presentation", "removal by hand", "tape consumption", "persistence"):
            with self.subTest(text):
                self.assertIn(text, doc)
        self.assertNotIn("native_attach_with_view_lod", doc)
        for reason in ("resolution_lod_absent", "resolution_proxy_missing", "resolution_enumeration_failed",
                       "resolution_lod_evidence_missing", "resolution_evidence_truncated", "resolution_selection_mismatch",
                       "resolution_vertex_missing", "resolution_vertex_invalid"):
            self.assertIn(reason, doc)


def tried(item, names=None, exists=None, sep_slash=5, sep_backslash=0):
    """The round-6 per-row facts as the new hook writes them: the first tried name is the row's cfg_class."""
    names = [item["cfg_class"], item["cfg_class"][5:]] if names is None else names
    exists = [item["cfg_exists"], False] if exists is None else exists
    return dict(item, cfg_tried=names, cfg_tried_exists=exists, sep_slash=sep_slash, sep_backslash=sep_backslash)


class RoundSixNativeFactsTests(unittest.TestCase):
    """Fix round 6 (probe-004): the proxy rows carried a whole-path cfg_class and the LOD names were unknown. The report names
    each cause with its own pending reason and carries the native self-test and LOD names through. Synthetic rows only;
    nothing here establishes DayZ behavior."""

    def judge(self, proxies=None, facts=None, **extra):
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights(),
                    proxies=[proxy()] if proxies is None else proxies, facts=facts)]
        rows[0].update(extra)
        result = report.build_report(classification([host("AK74", "slot_host")]), observations(rows))
        record = result["hosts"][0]
        return record["lights"]["UniversalLight"]["slots"]["weaponFlashlight"], record, result

    def verdict(self, *args, **kwargs):
        slot, _record, _result = self.judge(*args, **kwargs)
        return slot["verdict"], slot["reason"]

    def test_contradictory_lod_name_facts_are_malformed_never_a_clean_absence_or_presence(self):
        cases = {
            "more than eight names": dict(LOD_FACTS, lod_names=["a"] * 9, lod_count=9, lod_names_complete=True),
            "count below the listed names": dict(LOD_FACTS, lod_count=1),
            "complete flag against count": dict(LOD_FACTS, lod_count=5),
            "incomplete flag with every name listed": dict(LOD_FACTS, lod_names_complete=False),
            "failed list with names": dict(LOD_FACTS, lod_list_ok=False, lod_count=0),
            "failed list with a count": dict(LOD_FACTS, lod_list_ok=False, lod_names=[]),
            "a name that is not text": dict(LOD_FACTS, lod_names=["1.000", 2]),
            "count not an integer": dict(LOD_FACTS, lod_count="2"),
            "view_by_name not a bool": dict(LOD_FACTS, view_by_name=0),
        }
        for label, lod in cases.items():
            with self.subTest(label):
                self.assertEqual(("pending", "proxy_evidence_malformed"),
                                 self.verdict([proxy()], dict(copy.deepcopy(HOST_FACTS), **lod)), label)
        for key in report.LOD_HOST_KEYS:
            with self.subTest("only some lod keys: " + key + " missing"):
                self.assertEqual(("pending", "proxy_evidence_malformed"),
                                 self.verdict([proxy()], {k: v for k, v in HOST_FACTS.items() if k != key}), key)

    def test_a_truncated_lod_name_list_is_honest_and_a_listed_name_that_contradicts_it_is_malformed(self):
        names = ["res%d" % number for number in range(8)]
        cut = dict(copy.deepcopy(HOST_FACTS), lod_count=11, lod_names=names, lod_names_complete=False)
        self.assertEqual(GOOD, self.verdict([proxy()], cut))
        wrong = dict(cut, lod_names=["0", "1"] + names[:6])
        self.assertEqual(("pending", "proxy_evidence_malformed"), self.verdict([proxy()], wrong))

    def test_the_old_producers_whole_path_class_is_a_name_mismatch_not_malformed(self):
        """probe-004 rows: HCTLProxyBase kept the whole path, so cfg_class was "Proxy" + the path (and "Proxydz/..." when
        the path had no leading slash). The row is consistent and comes from a faulty derivation: it is pending with its
        own reason, and the native config was never read for the real class."""
        forms = {"leading slash": "Proxy" + LIGHT_PROXY_PATH, "no leading slash": "Proxy" + LIGHT_PROXY_PATH[1:]}
        for label, cfg_class in forms.items():
            item = proxy(exists=False, cfg_class=cfg_class, res_selection="")
            with self.subTest(label):
                self.assertEqual(("pending", "proxy_config_name_mismatch"), self.verdict([item]), label)
                legacy = {k: v for k, v in item.items() if k != "res_lods"}
                self.assertEqual(("pending", "proxy_config_name_mismatch"), self.verdict([legacy], LEGACY_HOST), label)

    def test_other_class_mismatches_and_a_mixed_host_stay_malformed(self):
        wrong = proxy(cfg_class="Proxymagazine_stanag")
        old = proxy(exists=False, cfg_class="Proxy" + LIGHT_PROXY_PATH, res_selection="")
        other = proxy(path="/dz/a/b", exists=False, cfg_class="Proxy/dz/a/c", res_selection="")
        self.assertEqual(("pending", "proxy_evidence_malformed"), self.verdict([wrong]))
        self.assertEqual(("pending", "proxy_evidence_malformed"), self.verdict([old, wrong]))
        self.assertEqual(("pending", "proxy_evidence_malformed"), self.verdict([other]))
        slash_only = proxy(exists=False, cfg_class="Proxy/", res_selection="")
        self.assertEqual(("pending", "proxy_evidence_malformed"), self.verdict([slash_only]))

    def test_a_row_from_the_new_producer_with_the_whole_path_class_is_malformed(self):
        """The new hook derives the class from the basename; a whole-path class next to cfg_tried is contradictory."""
        item = tried(proxy(exists=False, cfg_class="Proxy" + LIGHT_PROXY_PATH, res_selection=""))
        self.assertEqual(("pending", "proxy_evidence_malformed"), self.verdict([item]))

    def test_a_name_mismatch_is_reported_at_host_level_and_never_qualifies(self):
        item = proxy(exists=False, cfg_class="Proxy" + LIGHT_PROXY_PATH, res_selection="")
        _slot, record, result = self.judge([item])
        self.assertEqual("pending", record["verdict"])
        self.assertIn("proxy_config_name_mismatch", record["reasons"])
        self.assertEqual(0, result["denominators"]["server_qualified"])
        self.assertEqual(1, result["denominators"]["reasons"].get("proxy_config_name_mismatch"))

    def test_the_new_row_facts_are_validated_and_a_good_row_still_qualifies(self):
        self.assertEqual(GOOD, self.verdict([tried(proxy())]))
        base = tried(proxy())
        bad = {
            "tried not a list": dict(base, cfg_tried="Proxyweaponlight_universal"),
            "tried entry not text": dict(base, cfg_tried=["Proxyweaponlight_universal", 3]),
            "exists not a bool list": dict(base, cfg_tried_exists=[1, 0]),
            "lengths differ": dict(base, cfg_tried_exists=[True]),
            "first name is not the class": dict(base, cfg_tried=["Proxyother", "weaponlight_universal"]),
            "first answer is not cfg_exists": dict(base, cfg_tried_exists=[False, False]),
            "more than four tried names": dict(base, cfg_tried=["Proxyweaponlight_universal"] * 5,
                                               cfg_tried_exists=[True] * 5),
            "negative separator count": dict(base, sep_slash=-1),
            "separator count not an integer": dict(base, sep_backslash="0"),
            "only some new keys": {k: v for k, v in base.items() if k != "sep_slash"},
        }
        for label, item in bad.items():
            with self.subTest(label):
                self.assertEqual(("pending", "proxy_evidence_malformed"), self.verdict([item]), label)

    def test_each_spawned_host_carries_its_lod_resolution_and_proxy_name_diagnostics_and_the_header_is_carried_through(self):
        item = tried(proxy(res_selection=""), sep_slash=0, sep_backslash=5)
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights(), proxies=[item])]
        data = observations(rows)
        data["diagnostics"] = {
            "string_self_test": {"sample": "proxy:/dz/a/b.001", "first_slash": 6, "last_slash": 11, "last_dot": 13},
            "cfg_nonai_scan": {"child_count": 2, "scanned": 2, "complete": True, "proxy_named": 2,
                               "weaponlight_children": [{"name": "Proxyweaponlight_universal", "model": "/dz/x.p3d"}]}}
        result = report.build_report(classification([host("AK74", "slot_host")]), data)
        diagnostics = result["hosts"][0]["diagnostics"]
        self.assertEqual({"list_ok": True, "count": 2, "names": ["1.000", "geometry"], "names_complete": True,
                          "view_by_name": False}, diagnostics["lod"])
        self.assertEqual({"enum_ok": True, "count": 1, "complete": True,
                          "lods": [{"name": "1.000", "list_ok": True, "selection_count": 3, "scan_complete": True,
                                  "instance_ok": None, "native_count": None}]},
                         diagnostics["resolution"])
        self.assertEqual([{"selection": item["selection"], "cfg_tried": item["cfg_tried"],
                           "cfg_tried_exists": item["cfg_tried_exists"], "sep_slash": 0, "sep_backslash": 5}],
                         diagnostics["proxy_names"])
        native = result["native_diagnostics"]
        self.assertEqual("ok", native["status"])
        self.assertEqual(data["diagnostics"]["string_self_test"], native["string_self_test"])
        self.assertEqual(data["diagnostics"]["cfg_nonai_scan"], native["cfg_nonai_scan"])

    def test_legacy_observations_report_absent_diagnostics_and_malformed_ones_are_dropped_not_trusted(self):
        _slot, record, result = self.judge([legacy_proxy()], facts={})
        self.assertEqual({"status": "absent"}, result["native_diagnostics"])
        self.assertEqual({"status": "absent"}, record["diagnostics"]["lod"])
        self.assertEqual({"status": "absent"}, record["diagnostics"]["resolution"])
        self.assertEqual([], record["diagnostics"]["proxy_names"])
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights(), proxies=[proxy()])]
        scan = {"child_count": 1, "scanned": 1, "complete": True, "proxy_named": 0, "weaponlight_children": [3]}
        cases = {"not an object": [], "self test not an object": {"string_self_test": 3},
                 "value not a number": {"string_self_test": {"sample": "x", "last_slash": "11"}},
                 "scan child not an object": {"cfg_nonai_scan": scan}}
        for label, value in cases.items():
            data = observations(rows)
            data["diagnostics"] = value
            with self.subTest(label):
                result = report.build_report(classification([host("AK74", "slot_host")]), data)
                self.assertEqual({"status": "malformed"}, result["native_diagnostics"])
                self.assertEqual("server_qualified", result["hosts"][0]["verdict"])       # diagnostics never change a verdict

    def test_the_new_keys_are_consumed_and_the_new_reasons_are_documented(self):
        for key in ("cfg_tried", "cfg_tried_exists", "sep_slash", "sep_backslash", "lod_list_ok", "lod_count",
                    "lod_names", "lod_names_complete", "view_by_name", "diagnostics", "string_self_test",
                    "cfg_nonai_scan"):
            self.assertIn(key, report.CONSUMED_KEYS)
        for reason in ("view_lod_absent_on_server", "proxy_config_name_mismatch"):
            self.assertIn(reason, report.__doc__)


def unavailable_lod(name="0"):
    """A resolution LOD whose script instance was null (probe-006: 'NULL pointer to instance. Variable scanLod')."""
    return {"name": name, "list_ok": False, "selection_count": 0, "scan_complete": False, "instance_ok": False,
            "native_count": -1}


def unavailable_facts():
    """probe-006 host facts: both numeric LODs listed by name, neither instance usable, so no selection list at all."""
    facts = res_host(unavailable_lod("0"), unavailable_lod("1"), complete=False)
    facts.update(lod_list_ok=True, lod_count=4, lod_names=["0", "1", "geometry", "memory"], lod_names_complete=True,
                 view_by_name=False)
    return facts


def unavailable_proxy(**changes):
    return proxy(res=[res_entry("0", "", list_ok=False), res_entry("1", "", list_ok=False)], **changes)


class TierSTests(unittest.TestCase):
    """Fix round 8 (probe-006: qualified=0 because server-side resolution selection lists are unavailable, null scanLod).

    Tier S: observed slot + native CanAddAttachmentEx + attach and read-back + a host proxy whose CfgNonAIVehicles entry
    names the light model and the slot + beam memory points + a native switch action. Resolution-vertex membership is a
    diagnostic. The verdict is server_qualified with client_pending; nothing here is accepted."""

    CLS = classification([host("AK74", "slot_host")])

    def build(self, proxies, slots=None, lights=None, facts=None, prereq=None, variant=None, mutate=None):
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False) if slots is None else slots,
                    good_gun_lights() if lights is None else lights, proxies=proxies,
                    facts=unavailable_facts() if facts is None else facts, prereq=prereq, prereq_variant=variant)]
        obs = observations(rows)
        if mutate:
            mutate(obs)
        result = report.build_report(self.CLS, obs)
        record = result["hosts"][0]
        return record["lights"]["UniversalLight"]["slots"]["weaponFlashlight"], record, result

    def test_a_proxy_config_join_qualifies_when_the_resolution_lods_are_unavailable(self):
        slot, record, result = self.build([unavailable_proxy()])
        self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot"), (slot["verdict"], slot["reason"]))
        self.assertEqual("server_qualified", record["verdict"])
        self.assertEqual("proxy_config_slot", slot["evidence"]["model_evidence"])
        self.assertEqual("proxy:" + LIGHT_PROXY_PATH + ".001", slot["evidence"]["proxy_selection"])
        self.assertTrue(slot["evidence"]["client_pending"])
        self.assertEqual("resolution_lod_instance_unavailable", slot["evidence"]["resolution_status"])
        self.assertEqual("PENDING", result["acceptance"])
        self.assertNotIn("qualified", {h["verdict"] for h in result["hosts"]})

    def test_unavailable_is_recorded_apart_from_a_genuine_negative_resolution_scan(self):
        complete = res_host(("0", 3), ("1", 3))
        complete.update(lod_list_ok=True, lod_count=2, lod_names=["0", "1"], lod_names_complete=True, view_by_name=False)
        empty = [res_entry("0", ""), res_entry("1", "")]
        slot, _record, _result = self.build([proxy(res=empty)], facts=complete)
        self.assertEqual("server_qualified", slot["verdict"])
        self.assertEqual("resolution_proxy_missing", slot["evidence"]["resolution_status"])
        slot, _record, _result = self.build([unavailable_proxy()])
        self.assertEqual("resolution_lod_instance_unavailable", slot["evidence"]["resolution_status"])
        legacy = unavailable_facts()
        for lod in legacy["res_lods"]:
            del lod["instance_ok"], lod["native_count"]       # probe-006 wrote no instance fields: a failed list, not unavailable
        slot, _record, _result = self.build([unavailable_proxy()], facts=legacy)
        self.assertEqual("server_qualified", slot["verdict"])
        self.assertEqual("resolution_enumeration_failed", slot["evidence"]["resolution_status"])

    def test_resolution_membership_is_recorded_but_never_required(self):
        slot, _record, _result = self.build([proxy()], facts=HOST_FACTS)
        self.assertEqual("server_qualified", slot["verdict"])
        self.assertEqual("member", slot["evidence"]["resolution_status"])
        self.assertEqual("1.000", slot["evidence"]["resolution_lod"])
        self.assertEqual([0.5, 0.25, -1.5], slot["evidence"]["resolution_vertex"])

    def test_vertex_text_that_is_not_three_finite_numbers_is_only_a_diagnostic(self):
        for vertex in (("1e999", "0", "0"), ("1\n", "0", "0"), ("1", "0"), ("nan", "0", "0"), (" 1", "0", "0")):
            with self.subTest(vertex=vertex):
                slot, _record, _result = self.build([proxy(vertex=vertex)], facts=HOST_FACTS)
                self.assertEqual("server_qualified", slot["verdict"])
                self.assertEqual("resolution_vertex_invalid", slot["evidence"]["resolution_status"])

    def test_the_proxy_path_must_still_be_the_whole_light_model(self):
        wrong = "\\dz\\weapons\\attachments\\light\\weaponlight_tlr.p3d"
        slot, _record, _result = self.build([unavailable_proxy(model=wrong)])
        self.assertNotEqual("server_qualified", slot["verdict"])
        slot, _record, _result = self.build([unavailable_proxy(slots=("pistolFlashlight",))])
        self.assertEqual(("geometry_missing", "proxy_belongs_to_other_slot"), (slot["verdict"], slot["reason"]))

    def test_raw_proxy_names_are_normalised_before_the_join(self):
        for raw in ("proxy:\\dz\\weapons\\attachments\\light\\weaponlight_universal.001",
                    "PROXY:/DZ/Weapons/Attachments/Light/WeaponLight_Universal.012",
                    "proxy:dz/weapons/attachments/light/weaponlight_universal.100"):
            with self.subTest(raw=raw):
                item = unavailable_proxy()
                item["selection"] = raw
                slot, _record, _result = self.build([item])
                self.assertEqual("server_qualified", slot["verdict"])
                self.assertEqual(raw, slot["evidence"]["proxy_selection"])

    def test_no_light_proxy_on_the_host_is_pending_for_the_client_not_geometry_missing(self):
        other = proxy("/dz/weapons/attachments/magazine/mag_stanag", slots=("magazine",),
                      res=[res_entry("0", "", list_ok=False), res_entry("1", "", list_ok=False)])
        for proxies in ([other], []):
            with self.subTest(proxies=len(proxies)):
                slot, record, _result = self.build(proxies)
                self.assertEqual(("pending", "pending_client"), (slot["verdict"], slot["reason"]))
                self.assertTrue(slot["evidence"]["client_required"])
                self.assertEqual("pending", record["verdict"])
        slot, _record, _result = self.build(None, facts=dict(HOST_FACTS))
        self.assertEqual("pending", slot["verdict"])

    def test_a_host_without_any_proxy_evidence_stays_missing_not_negative(self):
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights())]
        result = report.build_report(self.CLS, observations(rows))
        slot = result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual(("pending", "proxy_evidence_missing"), (slot["verdict"], slot["reason"]))

    def test_direct_route_records_the_base_attempt_and_no_variant(self):
        slot, _record, _result = self.build([unavailable_proxy()])
        evidence = slot["evidence"]
        self.assertEqual("direct", evidence["route"])
        self.assertEqual("base", evidence["evaluated_attempt"])
        self.assertEqual({"can_add": True, "attach_ok": True, "found_type": "UniversalLight", "beam": None},
                         evidence["base_attempt"])
        self.assertIsNone(evidence["variant_attempt"])
        self.assertIsNone(evidence["prerequisite"])

    def refused_with_variant(self, **variant_changes):
        refused = good_gun_lights()
        refused[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False)
        variant_lights = good_gun_lights()
        variant_lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", beam=(True, True))
        variant = variant_obs("weaponHandguardAK", variant_lights, **variant_changes)
        return self.build([unavailable_proxy()], lights=refused, prereq=prereq_obs(has="weaponHandguardAK"),
                          variant=variant)

    def test_prerequisite_route_keeps_base_and_variant_facts_apart(self):
        slot, record, _result = self.refused_with_variant()
        self.assertEqual(("server_qualified", "native_attach_with_proxy_config_slot_and_rail_handguard_prerequisite"),
                         (slot["verdict"], slot["reason"]))
        evidence = slot["evidence"]
        self.assertEqual("after_prerequisite_handguard", evidence["route"])
        self.assertEqual("variant", evidence["evaluated_attempt"])
        self.assertEqual({"can_add": False, "attach_ok": False, "found_type": "", "beam": None}, evidence["base_attempt"])
        self.assertEqual({"can_add": True, "attach_ok": True, "found_type": "UniversalLight", "beam": True},
                         evidence["variant_attempt"])
        self.assertEqual({"slot": "weaponHandguardAK", "handguard": "AK_RailHndgrd", "found_type": "AK_RailHndgrd",
                          "rail_functional": True, "attached": True}, evidence["prerequisite"])
        self.assertTrue(evidence["requires_prerequisite"])
        self.assertTrue(evidence["can_add"])       # the evaluated (variant) attempt; the raw base fact is in base_attempt
        self.assertEqual("server_qualified", record["verdict"])

    def test_a_refused_prerequisite_variant_keeps_both_attempts_on_the_pending_or_negative_slot(self):
        refused = good_gun_lights()
        refused[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False)
        variant = variant_obs("weaponHandguardAK", refused)
        slot, _record, _result = self.build([unavailable_proxy()], lights=refused, prereq=prereq_obs(has="weaponHandguardAK"),
                                            variant=variant)
        self.assertEqual("geometry_missing", slot["verdict"])
        self.assertFalse(slot["evidence"]["base_attempt"]["can_add"])
        self.assertFalse(slot["evidence"]["variant_attempt"]["can_add"])

    def test_beam_memory_points_are_required_when_observed_and_unknown_when_absent(self):
        for beam, verdict, reason in (((True, True), "server_qualified", "native_attach_with_proxy_config_slot"),
                                      ((True, False), "pending", "light_beam_points_missing"),
                                      ((False, True), "pending", "light_beam_points_missing"),
                                      ((False, False), "pending", "light_beam_points_missing")):
            with self.subTest(beam=beam):
                lights = good_gun_lights()
                lights[2]["per_slot"][2] = per_slot("weaponFlashlight", "UniversalLight", beam=beam)
                slot, _record, _result = self.build([unavailable_proxy()], lights=lights)
                self.assertEqual((verdict, reason), (slot["verdict"], slot["reason"]))
        slot, _record, _result = self.build([unavailable_proxy()])
        self.assertIsNone(slot["evidence"]["base_attempt"]["beam"])       # not observed: not a pass, not a block
        for partial in ({"beam_start": True}, {"beam_end": True}, {"beam_start": "yes", "beam_end": True}):
            lights = good_gun_lights()
            lights[2]["per_slot"][2].update(partial)
            slot, _record, _result = self.build([unavailable_proxy()], lights=lights)
            self.assertEqual("pending", slot["verdict"], partial)

    def test_a_slot_without_a_native_switch_action_is_not_qualified(self):
        self.assertEqual({"weaponFlashlight": "ActionTurnOnWeaponFlashlight.c:27",
                          "pistolFlashlight": "ActionTurnOnWeaponFlashlight.c:32",
                          "helmetFlashlight": "ActionTurnOnHelmetFlashlight.c:40"}, report.SWITCH_ACTIONS)
        with mock.patch.dict(report.SWITCH_ACTIONS, clear=True):
            slot, _record, _result = self.build([unavailable_proxy()])
        self.assertEqual(("pending", "no_native_switch_action_for_slot"), (slot["verdict"], slot["reason"]))

    def test_instance_unavailable_facts_must_be_self_consistent(self):
        cases = {
            "instance down but list ok": {"list_ok": True},
            "instance down with a count": {"selection_count": 2},
            "instance down with a native count": {"native_count": 5},
            "instance flag mistyped": {"instance_ok": 0},
            "native count below minus one": {"native_count": -2},
            "native count mistyped": {"native_count": "5"},
        }
        for label, changes in cases.items():
            with self.subTest(label):
                facts = unavailable_facts()
                facts["res_lods"][0].update(changes)
                slot, record, _result = self.build([unavailable_proxy()], facts=facts)
                self.assertEqual("pending", slot["verdict"], label)
                self.assertEqual("pending", record["verdict"], label)

    def test_row_and_host_list_flags_must_agree_on_every_lod_even_when_another_lod_qualifies(self):
        facts = res_host(("0", 3), ("1", 3))
        facts.update(lod_list_ok=True, lod_count=2, lod_names=["0", "1"], lod_names_complete=True, view_by_name=False)
        held = "proxy:" + LIGHT_PROXY_PATH + ".001"
        for index in (0, 1):
            item = proxy(res=[res_entry("0", held if index else ""), res_entry("1", held if not index else "")])
            item["res_lods"][index]["list_ok"] = False       # the host row says this LOD listed fine
            slot, record, _result = self.build([item], facts=facts)
            self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]))
            self.assertEqual("pending", record["verdict"])

    def test_resolution_lod_names_are_whole_numbers_and_an_incomplete_name_list_never_decides(self):
        facts = res_host(("1", 3))
        facts.update(lod_list_ok=True, lod_count=6, lod_names=["1junk", "geometry"], lod_names_complete=False,
                     view_by_name=False)
        slot, _record, _result = self.build([proxy(res=[res_entry("1", "")])], facts=facts)
        self.assertEqual("server_qualified", slot["verdict"])       # "1junk" is not a LOD the scan could have read
        facts = res_host(dict(name="1junk", list_ok=True, selection_count=3, scan_complete=True))
        facts.update(lod_list_ok=True, lod_count=6, lod_names=["1junk", "geometry"], lod_names_complete=False,
                     view_by_name=False)
        slot, _record, _result = self.build([proxy(res=[res_entry("1junk", "")])], facts=facts)
        self.assertEqual(("pending", "proxy_evidence_malformed"), (slot["verdict"], slot["reason"]))

    def test_legacy_positive_flags_need_a_queried_selection_name(self):
        for flags in ({"on_model": True}, {"memory": True}, {"bone": 3}):
            for name in ("", None):
                with self.subTest(flags=flags, name=name):
                    selection = slot_obs("weaponFlashlight", has=True, selection=name, **flags)
                    if name is None:
                        del selection["selection"]
                    slots = [slot_obs("helmetFlashlight"), slot_obs("pistolFlashlight"), selection]
                    slot, record, _result = self.build([unavailable_proxy()], slots=slots)
                    self.assertEqual("pending", slot["verdict"])
                    self.assertEqual("pending", record["verdict"])
                    self.assertIn("slot_flag_without_selection_name", record["reasons"])
        selection = slot_obs("weaponFlashlight", has=True, on_model=True)
        slots = [slot_obs("helmetFlashlight"), slot_obs("pistolFlashlight"), selection]
        slot, _record, _result = self.build([], slots=slots)
        self.assertEqual(("server_qualified", "native_attach_with_model_selection"), (slot["verdict"], slot["reason"]))
        self.assertEqual("weaponFlashlight", slot["evidence"]["selection"])

    def test_a_legacy_selection_name_must_agree_with_the_top_level_slot_mapping(self):
        slots = [slot_obs("helmetFlashlight"), slot_obs("pistolFlashlight"),
                 slot_obs("weaponFlashlight", has=True, on_model=True)]

        def top(**changes):
            return lambda obs: next(item for item in obs["slots"] if item["slot"] == "weaponFlashlight").update(changes)
        cases = {"different name": top(selection="otherSelection"), "empty known name": top(selection=""),
                 "unknown mapping": top(selection_known=False), "mistyped known flag": top(selection_known="yes")}
        for label, mutate in cases.items():
            with self.subTest(label):
                slot, record, _result = self.build([unavailable_proxy()], slots=slots, mutate=mutate)
                self.assertEqual("pending", slot["verdict"], label)
                self.assertIn("slot_selection_disagree", record["reasons"], label)
        slot, _record, _result = self.build([unavailable_proxy()], slots=slots, mutate=top(selection="WEAPONFLASHLIGHT"))
        self.assertEqual("server_qualified", slot["verdict"])       # same name, case-insensitive like the engine's lookup

    def test_hosts_without_a_native_light_slot_are_outside_the_v1_scope_not_failures(self):
        cls = classification([host("Bat", "no_slot_host"), host("AK74", "slot_host")])
        rows = [row("Bat", "no_slot_host", no_slots(), refusal_lights(), index=0),
                row("AK74", "slot_host", gun_slots(), good_gun_lights(), index=1)]
        result = report.build_report(cls, observations(rows))
        bat = by_class(result, "Bat")
        self.assertEqual("not_server_evidencable", bat["verdict"])
        self.assertIn("no_native_light_slot", bat["reasons"])
        self.assertFalse(bat["v1_scope"]["in_scope"])
        self.assertIn("#58", bat["v1_scope"]["note"])
        self.assertTrue(all(light["verdict"] == "not_server_evidencable" for light in bat["lights"].values()))
        self.assertTrue(by_class(result, "AK74")["v1_scope"]["in_scope"])
        denominators = result["denominators"]
        self.assertEqual(1, denominators["not_server_evidencable"])
        self.assertEqual(1, denominators["out_of_v1_scope"])
        self.assertNotIn("geometry_missing", {record["verdict"] for record in result["hosts"]})

    def test_a_slot_host_whose_light_does_not_fit_keeps_the_real_negative(self):
        result = report.build_report(self.CLS, observations([row("AK74", "slot_host", gun_slots(), good_gun_lights())]))
        light = by_class(result, "AK74")["lights"]["TLRLight"]
        self.assertEqual(("geometry_missing", ["no_compatible_native_slot"]), (light["verdict"], light["reasons"]))

    def test_denominators_and_note_say_client_pending_and_accept_nothing(self):
        slot, record, result = self.build([unavailable_proxy()])
        denominators = result["denominators"]
        self.assertEqual(1, denominators["server_qualified"])
        self.assertEqual(1, denominators["client_pending"])
        self.assertEqual({"geometry_missing": 1, "server_qualified": 1}, denominators["host_light_pairs"])
        self.assertEqual("S", result["tier"])
        self.assertEqual("pending", result["client_tier"])
        self.assertEqual(("server_qualified", "geometry_missing", "not_server_evidencable", "excluded", "pending"),
                         report.VERDICT_ORDER)
        self.assertIn("client_pending", result["note"])
        self.assertIn("Nothing here is accepted", result["note"])

    def test_pending_and_integrity_failures_still_outrank_server_qualified_and_not_server_evidencable(self):
        slot, record, result = self.build([unavailable_proxy()], mutate=lambda obs: obs["counters"].update(deleted=3))
        self.assertEqual("pending", slot["verdict"])
        self.assertEqual("pending", record["verdict"])
        cls = classification([host("Bat", "no_slot_host")])
        rows = [row("Bat", "no_slot_host", no_slots(), refusal_lights())]
        obs = observations(rows, counters={"deleted": 3})       # a dirty cleanup withholds qualification, not a no-slot label
        self.assertEqual("not_server_evidencable", by_class(report.build_report(cls, obs), "Bat")["verdict"])
        lights = refusal_lights()
        lights[0]["per_slot"][2] = per_slot("weaponFlashlight", "Flashlight", fits=False, can_add=True, attach_ok=True)
        obs = observations([row("Bat", "no_slot_host", no_slots(), lights)])
        self.assertEqual("pending", by_class(report.build_report(cls, obs), "Bat")["verdict"])

    def test_the_optional_stronger_bone_evidence_is_recorded_and_never_gates(self):
        lights = good_gun_lights()
        lights[2]["per_slot"][2].update(proxy_after_attach="UniversalLight", bone_object_checked=True,
                                        bone_object_matches=True)
        slots = gun_slots(weapon_model=False)
        slots[2].update(proxy_bone_index=7, proxy_bone_name="proxy:\\dz\\weapons\\attachments\\light\\weaponlight_universal.001",
                        proxy_bone_tried=3)
        slot, _record, _result = self.build([unavailable_proxy()], slots=slots, lights=lights)
        self.assertEqual("server_qualified", slot["verdict"])
        self.assertEqual(7, slot["evidence"]["proxy_bone_index"])
        self.assertTrue(slot["evidence"]["bone_object_matches_light"])
        lights[2]["per_slot"][2].update(bone_object_matches=False)
        slots[2].update(proxy_bone_index=-1)
        slot, _record, _result = self.build([unavailable_proxy()], slots=slots, lights=lights)
        self.assertEqual("server_qualified", slot["verdict"])       # a missing bone link is not a negative on a server
        self.assertFalse(slot["evidence"]["bone_object_matches_light"])
        slot, _record, _result = self.build([unavailable_proxy()])
        self.assertIsNone(slot["evidence"]["proxy_bone_index"])
        self.assertIsNone(slot["evidence"]["bone_object_matches_light"])
        bad = gun_slots(weapon_model=False)
        bad[2].update(proxy_bone_index="7")
        slot, _record, _result = self.build([unavailable_proxy()], slots=bad)
        self.assertEqual("pending", slot["verdict"])       # mistyped optional evidence is invalid, never ignored

    def test_the_spawn_control_and_lod_counts_are_carried_as_diagnostics_only(self):
        def control(obs):
            obs["spawn_control"] = {"class": "AK74", "spawned": True, "spawn_flags": "no_inventory_flag", "proxy_count": 4,
                                    "selection_list_ok": True}
        slot, _record, result = self.build([unavailable_proxy()], mutate=control)
        self.assertEqual("server_qualified", slot["verdict"])
        self.assertEqual("ok", result["spawn_control"]["status"])
        self.assertEqual("no_inventory_flag", result["spawn_control"]["spawn_flags"])
        _slot, _record, result = self.build([unavailable_proxy()])
        self.assertEqual({"status": "absent"}, result["spawn_control"])
        _slot, _record, result = self.build([unavailable_proxy()], mutate=lambda obs: obs.update(spawn_control={"class": 4}))
        self.assertEqual({"status": "malformed"}, result["spawn_control"])

    def test_a_mistyped_spawn_control_is_malformed_and_never_aborts_the_report(self):
        """Review P2-4: the control is a diagnostic; whatever JSON type it has, the report is written and the pair verdict
        is the one the unchanged proxy evidence gives."""
        base, _record, _result = self.build([unavailable_proxy()])
        good = {"class": "AK74", "spawned": True, "spawn_flags": "no_inventory_flag"}
        for label, value in (("null", None), ("number", 42), ("float", 1.5), ("true", True), ("false", False),
                             ("string", "AK74"), ("empty string", ""), ("list", [good]), ("empty list", []),
                             ("class not a string", dict(good, **{"class": 4})), ("spawned not a bool", dict(good, spawned="yes")),
                             ("flags missing", {"class": "AK74", "spawned": True}),
                             ("proxy count negative", dict(good, proxy_count=-1)),
                             ("selection flag not a bool", dict(good, selection_list_ok=1))):
            with self.subTest(label):
                slot, record, result = self.build([unavailable_proxy()], mutate=lambda obs: obs.update(spawn_control=value))
                self.assertEqual({"status": "malformed"}, result["spawn_control"])
                self.assertEqual((base["verdict"], base["reason"]), (slot["verdict"], slot["reason"]))
                self.assertEqual("server_qualified", record["verdict"])
        _slot, _record, result = self.build([unavailable_proxy()], mutate=lambda obs: obs.update(spawn_control=good))
        self.assertEqual("ok", result["spawn_control"]["status"])
        facts = unavailable_facts()
        facts.update(lod_counts=[{"name": "0", "count": -1, "instance_ok": False}, {"name": "geometry", "count": 12,
                                                                                    "instance_ok": True}],
                     lod_counts_total=2, lod_counts_complete=True)
        _slot, record, _result = self.build([unavailable_proxy()], facts=facts)
        self.assertEqual(2, len(record["diagnostics"]["lod_counts"]["lods"]))
        self.assertTrue(record["diagnostics"]["lod_counts"]["complete"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        cls = classification([host("AK74", "slot_host"), host("Ruined", "excluded", ["scope_below_2"])])
        (self.root / "cls.json").write_text(json.dumps(cls))
        rows = [row("AK74", "slot_host", gun_slots(), good_gun_lights())]
        (self.root / "obs.json").write_text(json.dumps(observations(rows)))

    def args(self, out="report.json"):
        return ["--classification", str(self.root / "cls.json"), "--observations", str(self.root / "obs.json"),
                "--out", str(self.root / out)]

    def test_writes_a_new_report_once_and_never_overwrites(self):
        self.assertEqual(0, report.main(self.args()))
        document = json.loads((self.root / "report.json").read_text())
        self.assertEqual("server_qualified", {h["class"]: h["verdict"] for h in document["hosts"]}["AK74"])
        self.assertEqual(64, len(document["provenance"]["classification_sha256"]))
        self.assertEqual(64, len(document["provenance"]["observations_sha256"]))
        before = (self.root / "report.json").read_bytes()
        self.assertEqual(1, report.main(self.args()))
        self.assertEqual(before, (self.root / "report.json").read_bytes())

    def test_output_inside_the_checkout_is_refused(self):
        inside = Path(report.__file__).resolve().parents[2] / "taped-report-should-not-exist.json"
        self.assertEqual(1, report.main(self.args(out=str(inside))))
        self.assertFalse(inside.exists())

    def test_malformed_input_returns_failure_without_output(self):
        (self.root / "obs.json").write_text("not json")
        self.assertEqual(1, report.main(self.args()))
        self.assertFalse((self.root / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
