"""Read-only review reproductions using explicitly synthetic unit fixtures."""
import copy
import json
from pathlib import Path
import tempfile
from unittest import mock
from tests.unit import test_taped_light_report as f
from tests.unit import test_taped_light_probe as p
from tools.audit import taped_light_report as report
from tools.setup import taped_light_probe as probe


def baseline():
    cls = f.classification([f.host("AK74", "slot_host")])
    cls["hosts"][0]["native_light_slots"] = ["weaponFlashlight"]
    obs = f.observations([f.row("AK74", "slot_host", f.gun_slots(), f.good_gun_lights())])
    return cls, obs


def show(label, alter):
    cls, obs = baseline()
    alter(cls, obs)
    try:
        result = report.build_report(cls, obs)
        host = result["hosts"][0]
        print(label + ": " + json.dumps({"verdict": host["verdict"], "reasons": host["reasons"],
              "integrity": result["integrity"],
              "UniversalLight": host["lights"].get("UniversalLight")}, sort_keys=True))
    except Exception as exc:
        print(label + ": " + type(exc).__name__ + ": " + str(exc))


show("baseline", lambda c, o: None)
show("missing TLRLight row", lambda c, o: o["hosts"][0]["lights"].pop(1))
show("missing helmet slot observation", lambda c, o: o["hosts"][0]["slots"].pop(0))
show("missing can_add field", lambda c, o: o["hosts"][0]["lights"][2]["per_slot"][2].pop("can_add"))
show("conflicting host slot duplicate", lambda c, o: o["hosts"][0]["slots"].insert(0, f.slot_obs("weaponFlashlight")))
show("conflicting light duplicate", lambda c, o: o["hosts"][0]["lights"].insert(0, f.light_obs("UniversalLight", [], False)))
show("conflicting per-slot duplicate", lambda c, o: o["hosts"][0]["lights"][2]["per_slot"].insert(0,
     f.per_slot("weaponFlashlight", "UniversalLight", can_add=False, attach_ok=False)))
show("three duplicate preflights", lambda c, o: o["lights"].extend([copy.deepcopy(o["lights"][2]), copy.deepcopy(o["lights"][2])]))
show("wrong spawned host type", lambda c, o: o["hosts"][0].update(type="OtherHost"))
show("wrong preflight type and incompatible slots", lambda c, o: o["lights"][2].update(type="OtherLight", fits_native_slots=[]))
show("different config slot", lambda c, o: c["hosts"][0].update(native_light_slots=["pistolFlashlight"]))
show("partial overall status", lambda c, o: o.update(status="partial"))
show("dirty cleanup", lambda c, o: o["counters"].update(deleted=9, residual_probe_types=1))
show("control attaches", lambda c, o: o["hosts"][0]["lights"][0]["per_slot"][2].update(attach_ok=True))
def hidden_control(c, o):
    o["hosts"][0]["lights"][0]["per_slot"][2]["attach_ok"] = True
    o["hosts"][0]["lights"].append(f.light_obs('Flashlight', [f.per_slot(s, 'Flashlight', fits=False,
                                           can_add=False, attach_ok=False) for s in f.SLOTS]))
show("control attachment hidden by duplicate", hidden_control)
show("null host slots", lambda c, o: o["hosts"][0].update(slots=None))
show("null light per_slot", lambda c, o: o["hosts"][0]["lights"][2].update(per_slot=None))

def missing_no_slot(c, o):
    c["hosts"][0].update(group="no_slot_host", native_light_slots=[])
    o["hosts"][0].update(group="no_slot_host", slots=[], lights=[])
show("no-slot host with all evidence omitted", missing_no_slot)

targets = probe.select_targets(p.classification())
hook = probe.render_hook(targets)
cache = Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
print('native compile-shape lint:', probe.lint_hook(hook.decode(), native_types=probe.native_type_names(cache)))
print('deterministic hook:', hook == probe.render_hook(targets), 'sha256:', probe.sha256(hook))
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    source = p.make_source_runtime(root / 'vanilla')
    plan = probe.stage(source, root / 'vanilla-p0-001.', p.classification(),
                       battleye_sha256=p.SYNTH_BE_SHA, _wsl_parent=root)
    print('verified-runtime trailing-dot alias: ACCEPTED; runtime_root=' + plan['runtime_root'])

for part in ("serverDZ.cfg", "battleye/BEServer_x64.dll", "launch-plan.json"):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = p.make_source_runtime(root / "vanilla")
        original = source / part
        linked = root / (original.name + '.external')
        original.rename(linked)
        original.symlink_to(linked)
        try:
            probe.stage(source, root / "taped-light-test", p.classification(),
                        battleye_sha256=p.SYNTH_BE_SHA, _wsl_parent=root)
            print('symlink ' + part + ': ACCEPTED')
        except Exception as exc:
            print('symlink ' + part + ': ' + type(exc).__name__ + ': ' + str(exc))

for scenario in ('config changes after verification', 'sensitive mission file added after verification'):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = p.make_source_runtime(root / 'vanilla')
        prepare = probe._prepare_mission
        def changed(mission, destination, hook):
            if scenario.startswith('config'):
                (source / 'serverDZ.cfg').write_bytes(b'SYNTHETIC-UNVERIFIED-CONFIG')
            else:
                (mission / 'credentials.json').write_bytes(b'SYNTHETIC-SECRET-MATERIAL')
            return prepare(mission, destination, hook)
        with mock.patch.object(probe, '_prepare_mission', side_effect=changed):
            plan = probe.stage(source, root / 'taped-light-test', p.classification(),
                               battleye_sha256=p.SYNTH_BE_SHA, _wsl_parent=root)
        dest = root / 'taped-light-test'
        if scenario.startswith('config'):
            print(scenario + ': ACCEPTED; staged=' + (dest / 'serverDZ.cfg').read_text())
        else:
            copied = dest / 'mpmissions/dayzOffline.chernarusplus/credentials.json'
            print(scenario + ': ACCEPTED; copied_sensitive=' + str(copied.exists()))
