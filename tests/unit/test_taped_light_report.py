"""Offline tests for the taped-light matrix report. Every fixture is explicit and synthetic.

Nothing here establishes DayZ behavior: the report only joins what a native probe run wrote
with the config classification, and these tests prove only that join logic.
"""
import json
from pathlib import Path
import re
import tempfile
import unittest

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


def slot_obs(slot, has=False, on_model=False, memory=False, bone=-1):
    return {"slot": slot, "host_has_slot": has, "selection": slot if has else "", "selection_on_model": on_model,
            "memory_point": memory, "bone_index": bone, "bone_object": ""}


def per_slot(slot, light, fits=True, can_add=True, attach_ok=True, found=None):
    return {"slot": slot, "light_fits": fits, "can_add": can_add, "attach_ok": attach_ok,
            "found_type": (light if attach_ok else "") if found is None else found, "proxy_after_attach": ""}


def light_obs(light, slots, spawned=True):
    return {"light": light, "spawned": spawned, "can_add_any": any(s["can_add"] for s in slots), "per_slot": slots}


def prereq_obs(has=None, rail=False, attached=""):
    """Observed native prerequisite slots (UniversalLight.c:123-132); ``has`` names the one the host owns."""
    return [{"slot": s, "host_has_slot": s == has, "attached_type": attached if s == has else "",
             "rail_functional": bool(rail and s == has)} for s in PREREQ_SLOTS]


def variant_obs(slot, lights, guard="AK_RailHndgrd", guard_attached=True):
    return {"performed": True, "slot": slot, "handguard": guard, "handguard_attached": guard_attached,
            "lights": lights}


def row(name, group, slots, lights, spawned=True, timed_out=False, root="CfgWeapons", index=0, prereq=None,
        prereq_variant=None):
    if not spawned:
        return {"i": index, "class": name, "root": root, "group": group, "spawned": False, "timed_out": False}
    return {"i": index, "class": name, "root": root, "group": group, "spawned": True, "type": name,
            "own_slots": [], "attach_slots": [], "selection_count": 3, "selection_matches": [],
            "slots": slots, "prereq": prereq_obs() if prereq is None else prereq,
            "lights": lights, "timed_out": timed_out, "ms": 3,
            "prereq_variant": {"performed": False} if prereq_variant is None else prereq_variant}


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
        self.assertEqual("qualified", ak["verdict"])
        self.assertEqual("qualified", ak["lights"]["UniversalLight"]["verdict"])
        self.assertEqual("qualified", ak["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]["verdict"])
        self.assertEqual("geometry_missing", ak["lights"]["TLRLight"]["verdict"])
        self.assertIn("no_compatible_native_slot", ak["lights"]["TLRLight"]["reasons"])
        self.assertEqual("PENDING", result["acceptance"])

    def test_host_without_any_native_slot_is_geometry_missing_not_invented(self):
        result = report.build_report(self.cls, observations([
            row("AK74", "slot_host", gun_slots(), good_gun_lights()),
            row("Bat", "no_slot_host", no_slots(), refusal_lights(), index=1)]))
        bat = by_class(result, "Bat")
        self.assertEqual("geometry_missing", bat["verdict"])
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
        self.assertEqual(0, result["denominators"]["qualified"])

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

    def test_attach_without_model_geometry_is_geometry_missing(self):
        rows = [row("AK74", "slot_host", gun_slots(weapon_model=False), good_gun_lights())]
        result = report.build_report(self.cls, observations(rows))
        slot = by_class(result, "AK74")["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
        self.assertEqual("geometry_missing", slot["verdict"])
        self.assertEqual("attached_without_model_selection", slot["reason"])
        self.assertEqual("geometry_missing", by_class(result, "AK74")["verdict"])

    def test_bone_or_memory_point_counts_as_geometry_evidence(self):
        for kwargs in ({"memory": True}, {"bone": 4}):
            slots = [slot_obs("helmetFlashlight"), slot_obs("pistolFlashlight"),
                     slot_obs("weaponFlashlight", has=True, **kwargs)]
            rows = [row("AK74", "slot_host", slots, good_gun_lights())]
            result = report.build_report(self.cls, observations(rows))
            self.assertEqual("qualified", by_class(result, "AK74")["verdict"], kwargs)

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
        self.assertEqual(counts["hosts"], counts["qualified"] + counts["geometry_missing"] + counts["excluded"]
                         + counts["pending"])
        self.assertEqual({"qualified": 1, "geometry_missing": 0, "excluded": 1, "pending": 1, "hosts": 3}, {
            k: counts[k] for k in ("qualified", "geometry_missing", "excluded", "pending", "hosts")})

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
        self.assertEqual("qualified", record["verdict"])

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
        self.assertEqual("qualified", record["lights"]["UniversalLight"]["verdict"])
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
        self.assertEqual({"AK74": "pending", "Bat": "geometry_missing"}, verdicts(result))


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
        self.assertEqual(("qualified", "native_attach_with_rail_handguard_prerequisite"),
                         (slot["verdict"], slot["reason"]))
        self.assertTrue(slot["evidence"]["requires_prerequisite"])
        self.assertEqual("qualified", record["verdict"])

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
                "control": lambda c, o: o["hosts"][0]["lights"][0]["per_slot"][2].update(attach_ok=True)}.items():
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
        self.assertEqual("qualified", record["verdict"])


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
        self.assertEqual("qualified", {h["class"]: h["verdict"] for h in document["hosts"]}["AK74"])
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
