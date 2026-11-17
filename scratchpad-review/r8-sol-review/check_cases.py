"""Explicit synthetic review counterexamples; no engine behavior is inferred."""
import copy
import json
from tests.unit import test_taped_light_report as t
from tools.audit import taped_light_report as report


def evaluate(proxies, lights=None):
    rows = [t.row("AK74", "slot_host", t.gun_slots(False), lights or t.good_gun_lights(), proxies=proxies)]
    return report.build_report(t.classification([t.host("AK74", "slot_host")]), t.observations(rows))


def show(label, result):
    host = result["hosts"][0]
    light = host["lights"]["UniversalLight"]
    slot = light["slots"].get("weaponFlashlight", {})
    print(json.dumps(dict(case=label, host=host["verdict"], pair=light["verdict"], slot=slot.get("verdict"),
                          reason=slot.get("reason"), issues=result["integrity"]["issues"])))


positive = t.proxy()
negative = dict(t.proxy(), selection="proxy:" + t.LIGHT_PROXY_PATH[1:] + ".001", cfg_exists=False,
                model="", inventory_slots=[], slot_count=0)
show("same light-slot conflicting aliases, attach succeeds", evaluate([positive, negative]))
show("same light-slot conflicting aliases, attach refused", evaluate([positive, negative], t.refusal_lights()))
magazine = t.proxy(path="/dz/weapons/attachments/magazine/mag_stanag", slots=("magazine",))
mag_alias = dict(copy.deepcopy(magazine), selection=magazine["selection"].replace("proxy:/", "proxy:"))
show("unrelated coherent aliases", evaluate([positive, magazine, mag_alias]))
mag_alias["model"] = "\\dz\\other.p3d"
show("unrelated conflicting aliases", evaluate([positive, magazine, mag_alias]))
show("slot is weaponflashlight (case changed)", evaluate([t.proxy(slots=("weaponflashlight",))]))
show("slot is pistolFlashlight (different exact slot)", evaluate([t.proxy(slots=("pistolFlashlight",))]))

for raw in (None, 42, True):
    obs = t.observations([t.row("AK74", "slot_host", t.gun_slots(False), t.good_gun_lights(), proxies=[positive])])
    obs["spawn_control"] = raw
    try:
        built = report.build_report(t.classification([t.host("AK74", "slot_host")]), obs)
        print("spawn_control", repr(raw), built["spawn_control"])
    except Exception as error:
        print("spawn_control", repr(raw), type(error).__name__, str(error))
