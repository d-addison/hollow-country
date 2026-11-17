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


def host(name, group, reasons=(), root="CfgWeapons", role="gun_candidate"):
    return {"id": f"{root}:{name}", "root": root, "name": name, "role": role, "group": group,
            "native_light_slots": [], "scope": 2, "exclusion_reasons": list(reasons)}


def classification(hosts):
    return {"schema_version": 1, "kind": probe.CLASSIFICATION_KIND, "native_light_slots": SLOTS,
            "probe_lights": LIGHTS, "hosts": hosts,
            "lights": [{"name": "UniversalLight", "probe_role": "representative", "group": "mount_light"},
                       {"name": "TLRLight", "probe_role": "representative", "group": "mount_light"},
                       {"name": "Flashlight", "probe_role": "control", "group": "handheld_battery_light"}]}


def slot_obs(slot, has=False, on_model=False, memory=False, bone=-1):
    return {"slot": slot, "host_has_slot": has, "selection": slot if has else "", "selection_on_model": on_model,
            "memory_point": memory, "bone_index": bone, "bone_object": ""}


def per_slot(slot, light, fits=True, can_add=True, attach_ok=True, found=None):
    return {"slot": slot, "light_fits": fits, "can_add": can_add, "attach_ok": attach_ok,
            "found_type": (light if attach_ok else "") if found is None else found, "proxy_after_attach": ""}


def light_obs(light, slots, spawned=True):
    return {"light": light, "spawned": spawned, "can_add_any": any(s["can_add"] for s in slots), "per_slot": slots}


def row(name, group, slots, lights, spawned=True, timed_out=False, root="CfgWeapons", index=0):
    if not spawned:
        return {"i": index, "class": name, "root": root, "group": group, "spawned": False, "timed_out": False}
    return {"i": index, "class": name, "root": root, "group": group, "spawned": True, "type": name,
            "own_slots": [], "attach_slots": [], "selection_count": 3, "selection_matches": [],
            "slots": slots, "lights": lights, "timed_out": timed_out, "ms": 3}


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
            "residual_probe_types": 0, "residual_other": 0}
    base.update(counters or {})
    return {"schema": 1, "kind": probe.OBSERVATIONS_KIND, "status": status, "world": "chernarusplus",
            "version": "1.30", "begin_ms": 1, "end_ms": 9, "hard_cap": 600, "per_class_ms": 2000,
            "classes": len(rows), "observed": len(rows), "position": [1.0, 2.0, 3.0], "counters": base,
            "slots": [], "lights": preflight() if light_rows is None else light_rows, "hosts": rows}


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
        refused = [light_obs("UniversalLight", [per_slot("weaponFlashlight", "UniversalLight", can_add=False,
                                                         attach_ok=False)])]
        failed = [light_obs("UniversalLight", [per_slot("weaponFlashlight", "UniversalLight", can_add=True,
                                                        attach_ok=False)])]
        for lights, verdict, reason in ((refused, "geometry_missing", "native_attach_refused"),
                                         (failed, "pending", "attach_create_failed")):
            rows = [row("AK74", "slot_host", gun_slots(), lights)]
            result = report.build_report(self.cls, observations(rows))
            slot = by_class(result, "AK74")["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
            self.assertEqual((verdict, reason), (slot["verdict"], slot["reason"]))

    def test_found_type_must_match_the_attached_light(self):
        lights = [light_obs("UniversalLight", [per_slot("weaponFlashlight", "UniversalLight", found="Other")])]
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
