"""Read-only counterfactual over probe observations (stdlib only).

Counts host/light/slot triples that meet a server-observable rule WITHOUT any resolution-LOD vertex:
  native slot on host, light fits slot, CanAddAttachmentEx true (directly or after the native rail handguard),
  CreateAttachmentEx returned the light and FindAttachment(slot) read back the same type, and the host's
  Object.GetSelectionList holds a proxy selection whose CfgNonAIVehicles entry exists with inventorySlot == slot.
"""
import collections
import json
import sys
from pathlib import Path

RUN = Path(sys.argv[1]).expanduser()
obs = json.loads((RUN / "observations.json").read_text())


def proxy_slots(host):
    found = collections.defaultdict(list)
    for p in host.get("proxies", []):
        if p.get("cfg_exists"):
            for s in p.get("inventory_slots", []):
                found[s].append(p["selection"])
    return found


def attempts(host, light_rows, via):
    out = []
    for l in light_rows:
        for s in l.get("per_slot", []):
            out.append((l["light"], s["slot"], s.get("light_fits"), s.get("can_add"), s.get("attach_ok"),
                        s.get("found_type") == l["light"], via))
    return out


rows = []
for h in obs["hosts"]:
    if not h.get("spawned"):
        continue
    slots = proxy_slots(h)
    tries = attempts(h, h.get("lights", []), "direct")
    v = h.get("prereq_variant", {})
    if v.get("performed") and v.get("handguard_attached") and v.get("handguard_rail_functional"):
        tries += attempts(h, v.get("lights", []), "after_" + v.get("handguard", "?"))
    for light, slot, fits, can_add, ok, readback, via in tries:
        if slot not in h.get("attach_slots", []):
            continue
        rows.append({
            "host": h["class"], "root": h["root"], "light": light, "slot": slot, "via": via,
            "fits": fits, "can_add": can_add, "attach_ok": ok, "readback": readback,
            "proxy_for_slot": slots.get(slot, []),
        })

ok = [r for r in rows if r["attach_ok"] and r["readback"] and r["proxy_for_slot"]]
attached_no_proxy = [r for r in rows if r["attach_ok"] and r["readback"] and not r["proxy_for_slot"]]
print("host/light/slot attempts on native-slot hosts:", len(rows))
print("attach+readback+slot proxy in GetSelectionList:", len(ok), "hosts", len({r['host'] for r in ok}))
for r in ok:
    print("  ", r["host"], r["light"], r["slot"], r["via"], r["proxy_for_slot"][0])
print("attach+readback but NO slot proxy in GetSelectionList:", len(attached_no_proxy))
for r in attached_no_proxy:
    print("  ", r["host"], r["light"], r["slot"], r["via"])
refused = collections.Counter((r["light"], r["slot"], r["fits"], r["via"].startswith("after")) for r in rows if not r["can_add"])
print("refused (light, slot, light_fits, after_prereq):")
for k, n in sorted(refused.items(), key=str):
    print("  ", n, k)
