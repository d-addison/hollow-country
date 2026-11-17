"""Read-only aggregation of taped-light-probe-006 observations and report (stdlib only)."""
import collections
import json
import sys
from pathlib import Path

RUN = Path(sys.argv[1]).expanduser()
obs = json.loads((RUN / "observations.json").read_text())
hosts = obs["hosts"]
print("hosts", len(hosts))

c = collections.Counter()
lodsig = collections.Counter()
firearm_proxy_names = collections.Counter()
listing = {"listed": [], "not_listed": []}
for h in hosts:
    if not h.get("spawned"):
        c["not_spawned"] += 1
        continue
    attach = h.get("attach_slots", [])
    has_light_slot = any(s in attach for s in ("weaponFlashlight", "pistolFlashlight", "helmetFlashlight"))
    res = h.get("res_lods", [])
    any_listed = any(l.get("list_ok") for l in res)
    key = (h["root"], has_light_slot, any_listed)
    c[key] += 1
    lodsig[tuple(h.get("lod_names", []))] += 1
    (listing["listed"] if any_listed else listing["not_listed"]).append((h["class"], h["root"], has_light_slot))
    if has_light_slot:
        for p in h.get("proxies", []):
            if "light" in p["selection"]:
                firearm_proxy_names[p["selection"]] += 1

print("(root, has_native_light_slot, any_res_lod_listed) -> count")
for k, v in sorted(c.items(), key=str):
    print(" ", k, v)
print("top LOD name signatures")
for k, v in lodsig.most_common(12):
    print(" ", v, k)
print("light proxy selection names on slot hosts")
for k, v in firearm_proxy_names.most_common():
    print(" ", v, k)

print("\nCfgWeapons hosts whose resolution LODs listed:")
print(" ", [x[0] for x in listing["listed"] if x[1] == "CfgWeapons"][:40])
print("CfgVehicles light-slot hosts whose res LODs did NOT list:")
print(" ", [x[0] for x in listing["not_listed"] if x[1] == "CfgVehicles" and x[2]][:40])
print("CfgVehicles light-slot hosts whose res LODs listed:")
print(" ", [x[0] for x in listing["listed"] if x[1] == "CfgVehicles" and x[2]][:40])

# Light attach rows on light-slot hosts
print("\nlight-slot host attach outcomes (light, slot, can_add, attach_ok, found_type, proxy_after_attach)")
att = collections.Counter()
examples = {}
for h in hosts:
    if not h.get("spawned"):
        continue
    for l in h.get("lights", []):
        for s in l.get("per_slot", []):
            if s["slot"] in h.get("attach_slots", []):
                k = (l["light"], s["slot"], s["can_add"], s["attach_ok"], bool(s.get("found_type")), s.get("proxy_after_attach"))
                att[k] += 1
                examples.setdefault(k, h["class"])
for k, v in sorted(att.items(), key=str):
    print(" ", v, k, "e.g.", examples[k])

print("\nhost slot rows: bone_index / memory_point / selection_on_model where host_has_slot")
bc = collections.Counter()
for h in hosts:
    for s in h.get("slots", []):
        if s.get("host_has_slot"):
            bc[(s["slot"], s["selection"], s["bone_index"], s["memory_point"], s["selection_on_model"])] += 1
for k, v in bc.items():
    print(" ", v, k)

print("\nprereq variants")
pv = collections.Counter()
for h in hosts:
    v = h.get("prereq_variant", {})
    if v.get("performed"):
        rows = [(l["light"], [(s["slot"], s["can_add"], s["attach_ok"]) for s in l.get("per_slot", []) if s["slot"] == "weaponFlashlight"]) for l in v.get("lights", [])]
        pv[(v.get("slot"), v.get("handguard"), v.get("handguard_attached"), v.get("handguard_found_type"), v.get("handguard_rail_functional"), str(rows))] += 1
        examples[("pv",) + tuple(str(x) for x in (v.get("slot"), v.get("handguard_attached"), str(rows)))] = h["class"]
for k, v in pv.items():
    print(" ", v, k)

print("\nprereq rows on base host (slot owned, occupant)")
pr = collections.Counter()
for h in hosts:
    for p in h.get("prereq", []):
        if p.get("host_has_slot"):
            pr[(p["slot"], p["attached_type"], p["rail_functional"])] += 1
for k, v in pr.items():
    print(" ", v, k)

# UMP45 detail
for h in hosts:
    if h["class"] in ("UMP45", "AKM", "M4A1", "Glock19", "MP5K", "Mich2001Helmet"):
        print("\n==", h["class"], "lod_names", h.get("lod_names"), "res_lods", h.get("res_lods"))
        print("   selection_count", h.get("selection_count"), "matches", h.get("selection_matches"))
        for p in h.get("proxies", []):
            if "light" in p["selection"] or "flash" in p["selection"]:
                print("   proxy", json.dumps(p)[:900])
